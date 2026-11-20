"""What is around this node, from OpenStreetMap, kept in PostGIS, summarised once a month.

Fetches everything OSM knows inside PLACE_RADIUS_M of the node (default 1000 m): buildings, shops and amenities, roads,
green space. Stores the geometries in PostGIS (the node's own database, with the extension), then answers a fixed set
of questions in SQL: how many buildings and how much of the ground they cover; how many places of each kind (food,
retail, education, health, worship, lodging, services); what share of buildings are commercial; kilometres of road;
share of green; distance to the nearest school, clinic, market. The answers are readings on sensor `place-point`,
kind `map`, scale `community`, so they appear in /observations, the dashboard and the bot like the sea and the land.

What this is: structure, and change between refreshes. What it is not: behaviour. Nobody should read "three warungs"
as "a busy street"; the sensors say what the street is doing.

Refreshes every PLACE_REFRESH_DAYS (30). Between refreshes the metrics are recomputed from the stored features, so a new
node has numbers on its first poll and an old one does not hammer Overpass. Data © OpenStreetMap contributors, ODbL.
"""
from __future__ import annotations

import json
import logging
import math
import os
from datetime import datetime, timedelta, timezone

import sys

import psycopg
from psycopg.types.json import Jsonb

sys.path.insert(0, os.path.dirname(__file__))      # so `import satellite` works when the pack is loaded from packs/place

log = logging.getLogger("planetai.place")
OVERPASS = os.getenv("OVERPASS_URL", "https://overpass-api.de/api/interpreter")

# what counts as what. OSM tags → the node's categories. Kept short on purpose; the README explains the choices.
FOOD = {"restaurant", "cafe", "fast_food", "food_court", "bar", "pub", "ice_cream", "warung"}
EDU = {"school", "kindergarten", "college", "university", "childcare", "language_school"}
HEALTH = {"hospital", "clinic", "doctors", "dentist", "pharmacy"}
MARKET = {"supermarket", "marketplace", "convenience", "greengrocer", "general"}
SERVICES = {"bank", "atm", "post_office", "police", "townhall", "community_centre", "library", "fuel"}
COMMERCIAL_BUILDINGS = {"commercial", "retail", "office", "hotel", "warehouse", "industrial", "supermarket", "kiosk"}
GREEN_TAGS = {("leisure", "park"), ("leisure", "garden"), ("leisure", "nature_reserve"), ("leisure", "pitch"),
              ("landuse", "grass"), ("landuse", "forest"), ("landuse", "farmland"), ("landuse", "orchard"), ("landuse", "meadow"),
              ("landuse", "recreation_ground"), ("natural", "wood"), ("natural", "scrub"), ("natural", "grassland"), ("natural", "heath")}
ROAD_EXCLUDE = {"footway", "path", "steps", "cycleway", "pedestrian", "track", "bridleway", "corridor", "proposed", "construction"}

QUERY = """[out:json][timeout:90];
(
  way(around:{r},{lat},{lon})["building"];
  relation(around:{r},{lat},{lon})["building"];
  nwr(around:{r},{lat},{lon})["shop"];
  nwr(around:{r},{lat},{lon})["amenity"];
  nwr(around:{r},{lat},{lon})["office"];
  nwr(around:{r},{lat},{lon})["craft"];
  nwr(around:{r},{lat},{lon})["tourism"];
  nwr(around:{r},{lat},{lon})["healthcare"];
  way(around:{r},{lat},{lon})["highway"];
  way(around:{r},{lat},{lon})["leisure"];
  way(around:{r},{lat},{lon})["landuse"];
  way(around:{r},{lat},{lon})["natural"];
);
out geom;"""

DDL = """
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE TABLE IF NOT EXISTS place_features (
  osm_id    BIGINT PRIMARY KEY,
  osm_type  TEXT NOT NULL,
  kind      TEXT NOT NULL,                 -- building | poi | road | green | other
  category  TEXT,                          -- food | retail | education | health | market | worship | lodging | services | other
  name      TEXT,
  tags      JSONB NOT NULL,
  geom      geometry(Geometry, 4326) NOT NULL,
  fetched_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS place_features_geom ON place_features USING GIST (geom);
CREATE INDEX IF NOT EXISTS place_features_kind ON place_features (kind);
CREATE TABLE IF NOT EXISTS place_runs (
  run_at TIMESTAMPTZ PRIMARY KEY, radius_m INT NOT NULL, n_features INT NOT NULL, source TEXT NOT NULL
);
-- where the fetch was centred. Without it nothing could tell that the node had moved and every geometry below
-- described the previous address. Additive for nodes that ran before v0.33.4.
ALTER TABLE place_runs ADD COLUMN IF NOT EXISTS lat DOUBLE PRECISION;
ALTER TABLE place_runs ADD COLUMN IF NOT EXISTS lon DOUBLE PRECISION;
"""


def _category(tags: dict) -> str:
    a, s = tags.get("amenity"), tags.get("shop")
    if a in FOOD or s in {"bakery", "coffee"}: return "food"
    if a in EDU: return "education"
    if a in HEALTH or tags.get("healthcare"): return "health"
    if s in MARKET: return "market"
    if a == "place_of_worship": return "worship"
    if tags.get("tourism") in {"hotel", "guest_house", "hostel", "apartment", "chalet", "motel"}: return "lodging"
    if a in SERVICES or tags.get("office"): return "services"
    if s or tags.get("craft"): return "retail"
    return "other"


def _geojson(el: dict):
    """Overpass `out geom` → GeoJSON. Nodes are points; closed ways with area tags are polygons; open ways are lines;
    relations use their outer ways (an approximation that is right for the questions asked here)."""
    t = el["type"]
    if t == "node":
        return {"type": "Point", "coordinates": [el["lon"], el["lat"]]}
    if t == "way":
        pts = [[p["lon"], p["lat"]] for p in el.get("geometry") or []]
        if len(pts) < 2: return None
        tags = el.get("tags") or {}
        closed = pts[0] == pts[-1] and len(pts) >= 4
        area_like = "building" in tags or "landuse" in tags or "natural" in tags or (tags.get("leisure") and tags.get("leisure") != "track") or tags.get("area") == "yes"
        if closed and area_like:
            return {"type": "Polygon", "coordinates": [pts]}
        return {"type": "LineString", "coordinates": pts}
    if t == "relation":
        rings = []
        for m in el.get("members") or []:
            if m.get("role") == "outer" and m.get("geometry"):
                pts = [[p["lon"], p["lat"]] for p in m["geometry"]]
                if len(pts) >= 4 and pts[0] == pts[-1]: rings.append([pts])
        if not rings: return None
        return {"type": "MultiPolygon", "coordinates": rings}
    return None


def _kind(tags: dict, geom: dict) -> str:
    if "building" in tags: return "building"
    if "highway" in tags and geom["type"] == "LineString": return "road"
    if any((k, tags.get(k)) in GREEN_TAGS for k in ("leisure", "landuse", "natural")) and geom["type"] in ("Polygon", "MultiPolygon"): return "green"
    if any(k in tags for k in ("shop", "amenity", "office", "craft", "tourism", "healthcare")): return "poi"
    return "other"


# Everything this pack stores is a circle around one point, so changing NODE_LAT/NODE_LON in .env makes the whole
# cache describe somewhere else. The tolerance keeps a corrected decimal from costing an Overpass fetch: 1% of the
# radius, never under 25 m (0.0002 degrees of latitude is 22 m, the scale of a hand-typed correction).
MOVE_FRAC, MOVE_MIN_M = 0.01, 25.0


def metres(lat_a: float, lon_a: float, lat_b: float, lon_b: float) -> float:
    """Metres between two points, flat-earth approximation: exact enough well inside one degree."""
    dy = (lat_b - lat_a) * 111320.0
    dx = (lon_b - lon_a) * 111320.0 * math.cos(math.radians((lat_a + lat_b) / 2))
    return math.hypot(dx, dy)


def moved(lat: float, lon: float, prev_lat, prev_lon, radius_m: int) -> bool:
    if prev_lat is None or prev_lon is None:
        return False                      # nothing to compare with; fetch() treats a run with no point as stale
    return metres(prev_lat, prev_lon, lat, lon) > max(radius_m * MOVE_FRAC, MOVE_MIN_M)


def refresh(con, hc, lat: float, lon: float, radius: int) -> int:
    # Overpass answers 406 to anonymous clients; say who we are, and where to write
    r = hc.post(OVERPASS, data={"data": QUERY.format(r=radius, lat=lat, lon=lon)}, timeout=120,
                headers={"User-Agent": "planetai-node/place (https://planetai.fab.city; info@fab.city)", "Accept": "application/json"})
    r.raise_for_status()
    els = r.json().get("elements") or []
    rows = []
    for el in els:
        tags = el.get("tags") or {}
        if not tags: continue
        g = _geojson(el)
        if not g: continue
        rows.append((el["id"] if el["type"] == "node" else (el["id"] * 10 + (1 if el["type"] == "way" else 2)), el["type"], _kind(tags, g),
                     _category(tags) if _kind(tags, g) in ("poi", "building") else None, tags.get("name"), Jsonb(tags), json.dumps(g)))
    with con.cursor() as cur:
        cur.execute("DELETE FROM place_features")
        cur.executemany("""INSERT INTO place_features (osm_id, osm_type, kind, category, name, tags, geom)
                           VALUES (%s,%s,%s,%s,%s,%s, ST_SetSRID(ST_GeomFromGeoJSON(%s),4326)) ON CONFLICT (osm_id) DO NOTHING""", rows)
        cur.execute("INSERT INTO place_runs (run_at, radius_m, n_features, source, lat, lon) VALUES (now(), %s, %s, 'overpass', %s, %s)",
                    (radius, len(rows), lat, lon))
    con.commit()
    log.info("place: %d features within %d m from Overpass", len(rows), radius)
    return len(rows)



YEARLY = ("sat_buildings_yearly", "sat_height_m_yearly")


def yearly_readings(years) -> list[tuple]:
    """The yearly series as readings on `place-point`, dated 1 July of each year: the place's growth as a time series."""
    out = []
    for year, count, h in years:
        ts = datetime(year, 7, 1, tzinfo=timezone.utc)
        out.append((ts, "place-point", "sat_buildings_yearly", float(count)))
        if h is not None:
            out.append((ts, "place-point", "sat_height_m_yearly", float(h)))
    return out


def satellite_refresh(con, lat: float, lon: float, radius: int) -> int:
    """The satellite's half of a refresh: Open Buildings footprints into place_buildings_sat, the yearly count and
    height into place_yearly. Returns the years stored. Raises when Earth Engine is not configured.

    The node keeps the first value it files for a reading (app/store.py overwrites only a forecast still to come) and
    the series is dated 1 July of each year, so the rows filed from an earlier count would outlive every recount.
    Here they are removed and the recount is written over whatever stands, in the one commit. A poll that read the
    old count while `planetai run place refresh` was recounting then finds the new rows and changes nothing. A node
    that has not filed its sensor yet has no rows to correct, and its next poll files the series. Node #1 held a
    count 64 times low this way (18 Nov 2026)."""
    import satellite as S
    ee = S.init_ee()
    S.footprints(ee, con, lat, lon, radius)
    years = S.yearly(ee, lat, lon, radius)
    with con.cursor() as cur:
        cur.execute("CREATE TABLE IF NOT EXISTS place_yearly (year INT PRIMARY KEY, buildings REAL, height_m REAL, fetched_at TIMESTAMPTZ DEFAULT now())")
        for year, count, h in years:
            cur.execute("INSERT INTO place_yearly (year, buildings, height_m) VALUES (%s,%s,%s) ON CONFLICT (year) DO UPDATE SET buildings=EXCLUDED.buildings, height_m=EXCLUDED.height_m, fetched_at=now()", (year, count, h))
        cur.execute("DELETE FROM readings WHERE sensor_id='place-point' AND metric = ANY(%s)", (list(YEARLY),))
        for row in yearly_readings(years):
            cur.execute("INSERT INTO readings (ts, sensor_id, metric, value) SELECT %s, %s, %s, %s WHERE EXISTS (SELECT 1 FROM sensors WHERE sensor_id='place-point') "
                        "ON CONFLICT (sensor_id, metric, ts) DO UPDATE SET value = EXCLUDED.value", row)
    con.commit()
    return len(years)

METRICS_SQL = """
WITH here AS (SELECT ST_SetSRID(ST_MakePoint(%(lon)s, %(lat)s), 4326)::geography AS g),
b AS (SELECT count(*) AS n, coalesce(sum(ST_Area(geom::geography)),0) AS area,
             count(*) FILTER (WHERE (tags->>'building') = ANY(%(commercial)s) OR tags ? 'shop' OR tags ? 'office' OR tags->>'amenity' = ANY(%(food)s)) AS commercial
      FROM place_features WHERE kind='building'),
p AS (SELECT category, count(*) AS n FROM place_features WHERE kind='poi' GROUP BY category),
r AS (SELECT coalesce(sum(ST_Length(geom::geography)),0)/1000 AS km FROM place_features WHERE kind='road' AND NOT (tags->>'highway' = ANY(%(road_exclude)s))),
g AS (SELECT coalesce(sum(ST_Area(geom::geography)),0) AS area FROM place_features WHERE kind='green'),
d AS (SELECT
  (SELECT min(ST_Distance(f.geom::geography, here.g)) FROM place_features f, here WHERE f.category='education') AS school,
  (SELECT min(ST_Distance(f.geom::geography, here.g)) FROM place_features f, here WHERE f.category='health') AS health,
  (SELECT min(ST_Distance(f.geom::geography, here.g)) FROM place_features f, here WHERE f.category='market') AS market,
  (SELECT min(ST_Distance(f.geom::geography, here.g)) FROM place_features f, here WHERE f.category='worship') AS worship)
SELECT b.n AS buildings, b.area AS building_area_m2, b.commercial AS commercial_buildings, r.km AS roads_km, g.area AS green_area_m2,
       d.school, d.health, d.market, d.worship,
       (SELECT json_object_agg(category, n) FROM p) AS pois
FROM b, r, g, d;
"""


def fetch(hc):
    lat, lon = float(os.environ["NODE_LAT"]), float(os.environ["NODE_LON"])
    radius = int(os.getenv("PLACE_RADIUS_M", "1000")); days = int(os.getenv("PLACE_REFRESH_DAYS", "30"))
    with psycopg.connect(os.environ["DATABASE_URL"]) as con:
        with con.cursor() as cur:
            cur.execute(DDL); con.commit()
            cur.execute("SELECT run_at, radius_m, lat, lon FROM place_runs ORDER BY run_at DESC LIMIT 1"); last = cur.fetchone()
        # Why a refresh happens, said out loud: the log line is how an operator who moved a node sees that the
        # features followed. A move is the one reason that also invalidates the satellite caches below.
        why, point_moved = None, False
        if last is None:
            why = "first run"
        elif last[1] != radius:
            why = f"radius {last[1]} to {radius} m"
        elif last[2] is None or last[3] is None:
            why = "the stored run did not record where it was fetched"
        elif moved(lat, lon, last[2], last[3], radius):
            why, point_moved = f"the node moved {metres(last[2], last[3], lat, lon):.0f} m", True
        elif last[0] < datetime.now(timezone.utc) - timedelta(days=days):
            why = f"older than {days} days"
        if why:
            log.info("place: refreshing (%s)", why)
            if point_moved:
                # These two tables hold the satellite's view of the OLD circle and are keyed by nothing but this
                # node. Only the Earth Engine step below refills them, and a node without a key has none: keeping
                # the rows would draw the previous neighbourhood's footprints around the new point. Names are
                # literals from this tuple, never input.
                with con.cursor() as cur:
                    for t in ("place_buildings_sat", "place_yearly"):
                        cur.execute("SELECT to_regclass(%s) IS NOT NULL", (t,))
                        if cur.fetchone()[0]:
                            cur.execute(f"DELETE FROM {t}")
                            log.info("place: cleared %s (it described the previous point)", t)
                con.commit()
            refresh(con, hc, lat, lon, radius)
            # the satellite's buildings, if Earth Engine is configured; a missing key is logged once, never fatal
            try:
                satellite_refresh(con, lat, lon, radius)
            except Exception as e:  # noqa: BLE001
                log.warning("place: Open Buildings skipped (%s: %s)", type(e).__name__, str(e)[:120])
        sat_n, sat_conf, yearly = 0, None, []
        with con.cursor() as cur:
            cur.execute("SELECT to_regclass('place_buildings_sat') IS NOT NULL")
            if cur.fetchone()[0]:
                cur.execute("SELECT count(*), avg(confidence) FROM place_buildings_sat WHERE source='open_buildings_v3'"); sat_n, sat_conf = cur.fetchone()
            cur.execute("SELECT to_regclass('place_yearly') IS NOT NULL")
            if cur.fetchone()[0]:
                cur.execute("SELECT year, buildings, height_m FROM place_yearly ORDER BY year"); yearly = cur.fetchall()
        with con.cursor() as cur:
            cur.execute(METRICS_SQL, {"lat": lat, "lon": lon, "commercial": list(COMMERCIAL_BUILDINGS), "food": list(FOOD), "road_exclude": list(ROAD_EXCLUDE)})
            m = dict(zip([d.name for d in cur.description], cur.fetchone()))
            cur.execute("SELECT run_at, n_features FROM place_runs ORDER BY run_at DESC LIMIT 1"); run_at, n_feat = cur.fetchone()
    area_km2 = math.pi * (radius / 1000) ** 2
    pois = m["pois"] or {}
    vals = {
        "buildings": m["buildings"], "built_share": (m["building_area_m2"] or 0) / (area_km2 * 1e6),
        "commercial_share": (m["commercial_buildings"] / m["buildings"]) if m["buildings"] else 0,
        "businesses_per_km2": sum(v for k, v in pois.items() if k in ("food", "retail", "market", "services", "lodging")) / area_km2,
        "poi_food": pois.get("food", 0), "poi_retail": pois.get("retail", 0) + pois.get("market", 0), "poi_education": pois.get("education", 0),
        "poi_health": pois.get("health", 0), "poi_worship": pois.get("worship", 0), "poi_lodging": pois.get("lodging", 0), "poi_services": pois.get("services", 0),
        "roads_km": m["roads_km"], "green_share": (m["green_area_m2"] or 0) / (area_km2 * 1e6),
        "nearest_school_m": m["school"], "nearest_health_m": m["health"], "nearest_market_m": m["market"], "nearest_worship_m": m["worship"],
    }
    sensor = {"sensor_id": "place-point", "source": "openstreetmap", "name": f"Around here, {radius} m",
              "lat": lat, "lon": lon, "indoor": False, "local": False, "kind": "map", "scale": "community", "cadence": f"P{days}D",
              "meta": {"attribution": "© OpenStreetMap contributors (ODbL), via Overpass", "radius_m": radius, "features": n_feat, "fetched": run_at.isoformat()}}
    if sat_n:
        vals["sat_buildings"] = sat_n; vals["sat_confidence"] = sat_conf
        vals["osm_building_coverage"] = min(1.0, (m["buildings"] or 0) / sat_n)
    readings = [(run_at, "place-point", k, float(v)) for k, v in vals.items() if v is not None]
    return [sensor], readings + yearly_readings(yearly)
