"""area(cells, bbox): the rivers and level-12 basins this pack already keeps, those that touch the selection's box.

The area pull (spec 2026-11-10 §2) calls it through app/packs.py::collect. No network: it reads the json
`planetai run hydro fetch` wrote. A feature that touches the box is kept whole, so a river is not cut at the box's
edge. Outside the square hydro keeps it answers nothing, because there it knows nothing, not that there is no river.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location("planetai_pack_hydro_adapter_for_hooks", Path(__file__).with_name("adapter.py"))
A = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(A)  # type: ignore[union-attr]


def _extent(geom: dict) -> tuple[float, float, float, float]:
    """west, south, east, north of a LineString or a Polygon."""
    c = geom["coordinates"]
    pts = c if geom["type"] == "LineString" else [p for ring in c for p in ring]
    return min(p[0] for p in pts), min(p[1] for p in pts), max(p[0] for p in pts), max(p[1] for p in pts)


def area(cells, bbox):
    r = A.result()
    if not r:
        return None
    sq = A.square(r["lat"], r["lon"], r["radius_km"])
    if not A.touches(bbox, sq):
        return None
    rows = [{**f, "properties": {**f["properties"], "layer": layer}}
            for layer, fs in (("river", r["rivers"]["features"]), ("basin", r["basins"]["features"]))
            for f in fs if A.touches(_extent(f["geometry"]), bbox)]
    out = {"pack": "hydro", "source": A.RELEASE, "licence": A.ATTRIBUTION, "rows": rows, "as_of": r["fetched_at"]}
    if not (sq[0] <= bbox[0] and sq[1] <= bbox[1] and bbox[2] <= sq[2] and bbox[3] <= sq[3]):
        out["note"] = f"Only the part within {r['radius_km']} km of the node: hydro keeps nothing further out."
    return out
