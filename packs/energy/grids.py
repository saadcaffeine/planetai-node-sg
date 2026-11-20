"""Grid definitions and ring assignment from packs/energy/grids.yml.

Point-in-polygon is ray casting in stdlib, with no shapely. Vertices in grids.yml are [lon, lat] pairs.
"""
from __future__ import annotations

from pathlib import Path

import yaml

GRIDS_PATH = Path(__file__).with_name("grids.yml")


def load(path: Path | None = None) -> list[dict]:
    """Load the grid entries from grids.yml."""
    return yaml.safe_load((path or GRIDS_PATH).read_text()) or []


def inside(lat: float, lon: float, polygon: list) -> bool:
    """Ray-casting point-in-polygon for a ring of [lon, lat] vertices."""
    if not polygon:
        return False
    hit = False
    n = len(polygon)
    j = n - 1
    for i in range(n):
        xi, yi = polygon[i][0], polygon[i][1]
        xj, yj = polygon[j][0], polygon[j][1]
        if ((yi > lat) != (yj > lat)) and (lon < (xj - xi) * (lat - yi) / (yj - yi) + xi):
            hit = not hit
        j = i
    return hit


def bbox(polygon: list) -> tuple[float, float, float, float]:
    """Bounding box (s, w, n, e) of a [lon, lat] polygon."""
    lons = [p[0] for p in polygon]
    lats = [p[1] for p in polygon]
    return min(lats), min(lons), max(lats), max(lons)


def grid_for(lat: float, lon: float, gs: list[dict]) -> dict | None:
    """Return the first grid whose polygon contains (lat, lon), or None."""
    for g in gs:
        if inside(lat, lon, g.get("polygon") or []):
            return g
    return None


def ring_for(lat: float, lon: float, g: dict) -> str:
    """Return 'city' if (lat, lon) lies in g's city ring, else 'region' (links carry their own 'beyond')."""
    rings = g.get("rings") or {}
    if inside(lat, lon, rings.get("city") or []):
        return "city"
    return "region"
