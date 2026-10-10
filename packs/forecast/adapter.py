"""Weather forecast for this point: BMKG where the node is in Indonesia, Open-Meteo anywhere.

Context for reading the node's own air, not a prediction of it. The node fetches what a meteorological agency
already published and stores it beside its own readings so a person can see whether the smoke is arriving or
leaving. Forecasting is the upstream tiers' job; this pack has no rules that speak and no cells.

Every value is stored at its VALID time with the issue time beside it, as `fc_lead_hours`. A forecast without
its issue time cannot be checked afterwards, and one that has quietly stopped refreshing looks exactly like one
that is right.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone

log = logging.getLogger("planetai.forecast")

BMKG = "https://api.bmkg.go.id/publik/prakiraan-cuaca"
OPEN_METEO = "https://api.open-meteo.com/v1/forecast"
HOURS = 24                      # what the card and the report need; the sources offer three days


def _utc(s: str | None) -> datetime | None:
    if not s:
        return None
    s = s.strip().replace(" ", "T")
    try:
        d = datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None
    return d.astimezone(timezone.utc) if d.tzinfo else d.replace(tzinfo=timezone.utc)


def _sensor(sid: str, name: str, lat, lon, meta: dict) -> dict:
    return {"sensor_id": sid, "source": sid, "name": name, "lat": lat, "lon": lon,
            "indoor": False, "local": False, "kind": "model", "scale": "community",
            "cadence": "PT3H", "meta": meta}


def bmkg(hc, adm4: str, node_lat: float, node_lon: float):
    """BMKG's 3-hourly forecast for one Permendagri village code. `ws` is km/h and `wd_deg` is the direction the
    wind comes FROM, both as documented. `tp` is rain in mm for the step, which the node stores as the amount —
    BMKG publishes no probability, so the node does not invent one."""
    r = hc.get(BMKG, params={"adm4": adm4}, headers={"user-agent": "planetai-node"})
    r.raise_for_status()
    d = r.json()
    loc = d.get("lokasi") or {}
    if not loc:
        log.info("forecast: BMKG has no data for adm4=%s", adm4)
        return [], []
    steps = [s for group in (d.get("data") or [{}])[0].get("cuaca") or [] for s in group]
    issued = _utc((steps[0] if steps else {}).get("analysis_date"))
    sid = "forecast-bmkg"
    sensors = [_sensor(sid, f"BMKG forecast — {loc.get('desa')}, {loc.get('kecamatan')}",
                       loc.get("lat"), loc.get("lon"),
                       {"adm4": adm4, "desa": loc.get("desa"), "kecamatan": loc.get("kecamatan"),
                        "kotkab": loc.get("kotkab"), "issued": issued.isoformat() if issued else None,
                        "km_from_node": None if loc.get("lat") is None else round(
                            _km(node_lat, node_lon, float(loc["lat"]), float(loc["lon"])), 2),
                        "attribution": "BMKG (Badan Meteorologi, Klimatologi, dan Geofisika), api.bmkg.go.id"})]
    cutoff = datetime.now(timezone.utc) + timedelta(hours=HOURS)
    readings = []
    for s in steps:
        ts = _utc(s.get("utc_datetime") or s.get("datetime"))
        if ts is None or ts > cutoff:
            continue
        for key, metric in (("t", "fc_temp"), ("hu", "fc_humidity"), ("ws", "fc_wind_speed"),
                            ("wd_deg", "fc_wind_direction"), ("tcc", "fc_cloud"), ("tp", "fc_rain")):
            if s.get(key) is not None:
                readings.append((ts, sid, metric, float(s[key])))
        if issued is not None:
            readings.append((ts, sid, "fc_lead_hours", round((ts - issued).total_seconds() / 3600, 1)))
    return sensors, readings


OM_HOURLY = ("temperature_2m,relative_humidity_2m,precipitation,precipitation_probability,wind_speed_10m,wind_direction_10m,"
             "cloud_cover")
OM_MAP = {"temperature_2m": "fc_temp", "relative_humidity_2m": "fc_humidity", "precipitation": "fc_rain",
          "precipitation_probability": "fc_rain_prob",
          "wind_speed_10m": "fc_wind_speed", "wind_direction_10m": "fc_wind_direction", "cloud_cover": "fc_cloud"}


def openmeteo(hc, lat: float, lon: float):
    """Open-Meteo's hourly forecast. `wind_speed_10m` is km/h by default, the same unit BMKG publishes, so the
    two are comparable without conversion — checked against the API's own `hourly_units` in verify.

    Open-Meteo publishes no issue time: there is no analysis_date in the response, and `generationtime_ms` is how
    long the request took, not when the model ran. The node records when IT fetched, and says so rather than
    dressing a fetch time up as a model run."""
    r = hc.get(OPEN_METEO, params={"latitude": lat, "longitude": lon, "hourly": OM_HOURLY,
                                   "forecast_days": 2, "timezone": "UTC"})
    r.raise_for_status()
    d = r.json()
    h = d.get("hourly") or {}
    times = h.get("time") or []
    fetched = datetime.now(timezone.utc)
    sid = "forecast-om"
    sensors = [_sensor(sid, "Open-Meteo forecast (model point sample)", d.get("latitude"), d.get("longitude"),
                       {"fetched": fetched.isoformat(), "issued": None,
                        "note": "Open-Meteo publishes no model run time; `fetched` is when this node asked.",
                        "licence": "CC-BY 4.0, free tier non-commercial only",
                        "attribution": "Open-Meteo, open-meteo.com"})]
    cutoff = fetched + timedelta(hours=HOURS)
    readings = []
    for i, t in enumerate(times):
        ts = _utc(t if str(t).endswith("Z") else f"{t}Z")
        if ts is None or ts < fetched - timedelta(hours=1) or ts > cutoff:
            continue
        for key, metric in OM_MAP.items():
            v = (h.get(key) or [None] * len(times))[i]
            if v is not None:
                readings.append((ts, sid, metric, float(v)))
        readings.append((ts, sid, "fc_lead_hours", round((ts - fetched).total_seconds() / 3600, 1)))
    return sensors, readings


WIND_N = int(os.getenv("FORECAST_WIND_N", "8"))            # points a side: 64, as Bali Air Dispatch draws its field
WIND_KM = float(os.getenv("FORECAST_WIND_KM", "30"))       # half-width of the square, km


def wind_grid(lat: float, lon: float, km: float = WIND_KM, n: int = WIND_N):
    """The n×n points of a square of half-width `km` round (lat, lon): latitudes south to north, longitudes west to
    east, so the page can draw the field without working out where a point is."""
    import math
    dlat, dlon = km / 110.574, km / (111.320 * math.cos(math.radians(lat)))
    step = lambda lo, hi, i: round(lo + (hi - lo) * i / (n - 1), 5)  # noqa: E731
    return [step(lat - dlat, lat + dlat, i) for i in range(n)], [step(lon - dlon, lon + dlon, i) for i in range(n)]


def wind_field(hc, lat: float, lon: float, km: float = WIND_KM, n: int = WIND_N) -> dict:
    """The wind over the node's square, for a map that draws it moving: Open-Meteo's hourly 10 m wind at n×n points,
    the next day, in one request. Speeds km/h, directions the way the wind comes FROM, as the point forecast stores
    them. Not readings: a model's field, kept as a file (out/ground/wind.json) for the map and nothing else."""
    lats, lons = wind_grid(lat, lon, km, n)
    pts = [(la, lo) for la in lats for lo in lons] + [(round(lat, 5), round(lon, 5))]   # the node's own point last
    r = hc.get(OPEN_METEO, params={"latitude": ",".join(str(p[0]) for p in pts), "longitude": ",".join(str(p[1]) for p in pts),
                                   "hourly": "wind_speed_10m,wind_direction_10m", "forecast_days": 2, "timezone": "UTC",
                                   "cell_selection": "nearest"})   # the default, "land", moves a sea point to the nearest land cell, 12 km off
    r.raise_for_status()
    d = r.json()
    d = d if isinstance(d, list) else [d]
    if len(d) != len(pts):
        raise ValueError(f"Open-Meteo answered {len(d)} points for {len(pts)} asked")
    fetched = datetime.now(timezone.utc)
    times = [f"{t}Z" for t in (d[0].get("hourly") or {}).get("time", [])]
    keep = [i for i, t in enumerate(times) if fetched - timedelta(hours=1) <= _utc(t) <= fetched + timedelta(hours=HOURS)]
    grid = lambda key: [[[(p.get("hourly") or {}).get(key, [None] * len(times))[i] for p in d[j * n:(j + 1) * n]]  # noqa: E731
                         for j in range(n)] for i in keep]
    me = (d[-1].get("hourly") or {})
    return {"source": "Open-Meteo, 10 m wind", "licence": "CC-BY 4.0, free tier non-commercial only",
            "attribution": "Open-Meteo, open-meteo.com", "fetched": fetched.isoformat(), "n": n, "km": km,
            "lats": lats, "lons": lons, "times": [times[i] for i in keep],
            "speed_kmh": grid("wind_speed_10m"), "from_deg": grid("wind_direction_10m"),
            # the readout's one number is the node's own point, asked as such, not a value the page picks off the grid
            "at_node": {"speed_kmh": [me.get("wind_speed_10m", [None] * len(times))[i] for i in keep],
                        "from_deg": [me.get("wind_direction_10m", [None] * len(times))[i] for i in keep]}}


def write_wind_field(hc, lat: float, lon: float):
    """Fetch the field and replace out/ground/wind.json whole, or leave the last one standing."""
    import json
    from pathlib import Path
    out = Path(os.getenv("PACK_OUT", "/app/out")) / "ground"
    f = wind_field(hc, lat, lon)
    out.mkdir(parents=True, exist_ok=True)
    tmp = out / "wind.json.part"
    tmp.write_text(json.dumps(f))
    tmp.replace(out / "wind.json")
    return f


def gap(a: list, b: list):
    """Where the two sources disagree, on the variables they both give. One derived channel, not a judgement:
    neither source is the truth, and a wide gap is the node saying so out loud."""
    def by(rows, metric):
        return {ts: v for ts, _sid, m, v in rows if m == metric}
    out = []
    for metric, name in (("fc_temp", "fc_temp_gap"), ("fc_wind_speed", "fc_wind_speed_gap")):
        x, y = by(a, metric), by(b, metric)
        for ts in sorted(set(x) & set(y)):
            out.append((ts, "forecast-gap", name, round(abs(x[ts] - y[ts]), 2))) 
    if not out:
        return [], []
    return [_sensor("forecast-gap", "BMKG against Open-Meteo", None, None,
                    {"note": "how far apart the two forecasts are for the same hour; neither is the truth"})], out


def _km(lat1, lon1, lat2, lon2):
    import math
    p = math.pi / 180
    a = 0.5 - math.cos((lat2 - lat1) * p) / 2 + math.cos(lat1 * p) * math.cos(lat2 * p) * (1 - math.cos((lon2 - lon1) * p)) / 2
    return 12742 * math.asin(math.sqrt(a))


def fetch(hc):
    """Both sources if both are configured, either alone, and nothing at all without complaint. A source that is
    down is never an alert: log once and return what we have."""
    lat, lon = float(os.environ["NODE_LAT"]), float(os.environ["NODE_LON"])
    sensors, readings, bm, om = [], [], [], []
    adm4 = os.getenv("FORECAST_BMKG_ADM4", "").strip()
    if os.getenv("FORECAST_BMKG", "1") == "1":
        if not adm4:
            log.info("forecast: FORECAST_BMKG_ADM4 is not set — `planetai run forecast verify` finds the code for this point")
        else:
            try:
                s, bm = bmkg(hc, adm4, lat, lon); sensors += s; readings += bm
            except Exception as e:  # noqa: BLE001
                log.warning("forecast: BMKG unreachable (%s); the pack idles until it answers", e)
    if os.getenv("FORECAST_OPENMETEO", "0") == "1":
        try:
            s, om = openmeteo(hc, lat, lon); sensors += s; readings += om
        except Exception as e:  # noqa: BLE001
            log.warning("forecast: Open-Meteo unreachable (%s)", e)
        try:                     # the field the map draws moving; same source, same switch, same cadence
            write_wind_field(hc, lat, lon)
        except Exception as e:  # noqa: BLE001
            log.warning("forecast: wind field not refreshed (%s); the last one stays", e)
    if bm and om:
        s, g = gap(bm, om); sensors += s; readings += g
    return sensors, readings
