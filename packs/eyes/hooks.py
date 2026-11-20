"""area(cells, bbox): how many open records GBIF holds of each species in the selection (spec 2026-11-10 §2).

The weekly count in routes.py (check_others) asks per cell of the node's seven; the area pull asks once for the whole
selection, with the same licence filter (OTHERS_LICENCES), counts only, nothing kept but the answer, cached a day per
selection. Only with SPECIES_MATCH on, the household's yes to asking GBIF; off, eyes answers nothing.

GBIF is sent the selection's outline, one POLYGON or MULTIPOLYGON from the union of its cells (h3.cells_to_geo),
counter-clockwise as GBIF asks, and nothing else. The search is a GET, so an outline past WKT_MAX characters is
refused with a sentence rather than sent: the request line stays under 8 KB, the usual server limit.
"""
from __future__ import annotations

import importlib.util
import time
from datetime import datetime, timezone
from pathlib import Path

import h3
import httpx

import settings

_spec = importlib.util.spec_from_file_location("planetai_pack_eyes_routes_for_hooks", Path(__file__).with_name("routes.py"))
R = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(R)  # type: ignore[union-attr]

GBIF_OCC = "https://api.gbif.org/v1/occurrence/search"
# ponytail: GBIF's docs could not be read when this was written (no network); 5000 keeps the URL-encoded line under
# 8 KB. Raise it once GBIF's own limit is known.
WKT_MAX = 5000
FACET_LIMIT = 1000
DAY = 86400
AREA_SWITCH = ("SPECIES_MATCH", "on")    # POST /area reads it too, to say "off on this node" rather than "nothing here"
_cache: dict = {}


def _ring(pts, ccw: bool) -> str:
    """One ring as WKT, turned counter-clockwise (an outer ring) or clockwise (a hole) by the shoelace sign."""
    pts = [tuple(p) for p in pts]
    if pts[0] == pts[-1]:
        pts = pts[:-1]
    if (sum((x2 - x1) * (y2 + y1) for (x1, y1), (x2, y2) in zip(pts, pts[1:] + pts[:1])) > 0) == ccw:
        pts.reverse()
    return "(" + ",".join(f"{x:.6f} {y:.6f}" for x, y in pts + pts[:1]) + ")"


def _wkt(cells) -> str:
    g = h3.cells_to_geo(list(cells))
    polys = [g["coordinates"]] if g["type"] == "Polygon" else g["coordinates"]
    parts = ["(" + ",".join(_ring(r, i == 0) for i, r in enumerate(p)) + ")" for p in polys]
    return "POLYGON" + parts[0] if len(parts) == 1 else "MULTIPOLYGON(" + ",".join(parts) + ")"


def area(cells, bbox):
    if settings.get(AREA_SWITCH[0], "off") != AREA_SWITCH[1]:
        return None
    key, now = tuple(sorted(cells)), time.time()
    hit = _cache.get(key)
    if hit and now - hit[0] < DAY:
        return hit[1]
    wkt = _wkt(key)
    if len(wkt) > WKT_MAX:
        return {"pack": "eyes", "error": "This area's outline is too long to send to GBIF. Choose a smaller or simpler area."}
    try:
        with httpx.Client(timeout=60) as hc:
            r = hc.get(GBIF_OCC, params=[("geometry", wkt), *(("license", lc) for lc in R.OTHERS_LICENCES),
                                         ("limit", "0"), ("facet", "speciesKey"), ("facetLimit", str(FACET_LIMIT))])
            r.raise_for_status()
            d = r.json()
    except (httpx.HTTPError, ValueError) as e:
        return {"pack": "eyes", "error": f"GBIF did not answer ({type(e).__name__})."}
    rows = sorted(({"species_key": int(c["name"]), "records": c["count"]} for f in d.get("facets", []) for c in f["counts"]),
                  key=lambda x: -x["records"])
    out = {"pack": "eyes", "source": "GBIF occurrence records, api.gbif.org", "licence": " or ".join(R.OTHERS_LICENCES),
           "rows": rows, "as_of": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    if len(rows) >= FACET_LIMIT:
        out["note"] = f"The {FACET_LIMIT} species with most records; GBIF holds more here."
    for k in [k for k, v in _cache.items() if now - v[0] >= DAY]:
        del _cache[k]
    _cache[key] = (now, out)
    return out
