"""OpenStreetMap power infrastructure parser and distance helper for the energy pack."""
from __future__ import annotations

import re
from math import asin, cos, radians, sin, sqrt

FOSSIL_FUELS = {"coal", "gas", "oil", "diesel"}
CLEAN_FUELS = {"solar", "wind", "hydro", "geothermal", "biomass"}

QUERY = """[out:json][timeout:90][bbox:{s},{w},{n},{e}];
(
  nwr["power"~"^(plant|substation)$"];
  nwr["power"="generator"]["generator:source"];
  nwr["power"~"^(line|cable|minor_line)$"];
);
out tags center;"""

_MW_RE = re.compile(r"^\s*([0-9]+(?:[.,][0-9]+)?)\s*(gw|mw|mwp|kw|kwp|w)?\s*$", re.IGNORECASE)


def mw(tag: str | None) -> float | None:
    """Parse an OSM capacity tag into MW. Returns None when absent, qualitative ('yes'), zero, or unrecognised."""
    if not tag or not isinstance(tag, str):
        return None
    m = _MW_RE.match(tag)
    if not m:
        return None
    val = float(m.group(1).replace(",", "."))
    if val <= 0:
        return None
    unit = (m.group(2) or "mw").lower()
    if unit == "gw":
        return val * 1000.0
    if unit in ("kw", "kwp"):
        return val / 1000.0
    if unit == "w":
        return val / 1_000_000.0
    return val


def km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in km (haversine, R = 6371 km)."""
    p1, p2, dl = radians(lat1), radians(lat2), radians(lon2 - lon1)
    return 6371.0 * 2.0 * asin(sqrt(sin((p2 - p1) / 2.0) ** 2 + cos(p1) * cos(p2) * sin(dl / 2.0) ** 2))


def _fuel(raw: str | None) -> tuple[str | None, bool | None]:
    if not raw or not isinstance(raw, str):
        return None, None
    token = raw.split(";")[0].strip().lower()
    if token in FOSSIL_FUELS:
        return token, True
    if token in CLEAN_FUELS:
        return token, False
    return None, None


def parse(doc: dict) -> list[dict]:
    """Extract plants, generators, substations and cable heads from an Overpass JSON response."""
    out: list[dict] = []
    for el in (doc or {}).get("elements") or []:
        tags = el.get("tags") or {}
        power = tags.get("power")
        if power not in ("plant", "generator", "substation"):
            continue
        center = el.get("center") or el
        lat, lon = center.get("lat"), center.get("lon")
        if lat is None or lon is None:
            continue
        name = tags.get("name") or tags.get("name:en") or tags.get("name:es") or tags.get("name:ca") or ""
        if power == "substation":
            kind = "cable_head" if name.startswith("Cable Head") else "substation"
            fuel, fossil, cap = None, None, None
        else:
            # A generator often sits inside a plant that already carries its MW: listed, never summed.
            kind = "plant" if power == "plant" else "generator"
            fuel, fossil = _fuel(tags.get("plant:source") or tags.get("generator:source"))
            cap = mw(tags.get("plant:output:electricity") or tags.get("generator:output:electricity"))
        out.append({
            "name": name,
            "kind": kind,
            "fuel": fuel,
            "fossil": fossil,
            "mw": cap,
            "lat": float(lat),
            "lon": float(lon),
        })
    return out


def near(sources: list[dict], lat: float, lon: float) -> list[dict]:
    """Return sources with 'km' from (lat, lon) added, sorted nearest first."""
    with_km = [dict(s, km=km(lat, lon, s["lat"], s["lon"])) for s in sources]
    with_km.sort(key=lambda s: s["km"])
    return with_km
