"""GET /earth, /earth/change.png, /earth/year.png: what the earth pack holds of this node's AlphaEarth square.

Routes of this pack since 23 Oct 2026; until then app/main.py, moved with their answers unchanged. The node mounts
them from here (app/packs.py::routers) and answers 404 while this pack is off. Which directory holds the square, and
the comparisons in it, are adapter.py's own cache() and changes(): app/main.py kept a copy of that rule because the
core does not import a pack, and the copy is gone. `earth()` is also what /issues reads for land's region column
(app/issues/api.py::_earth), so it stays a plain function the route wraps.
"""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

import packs
import settings

router = APIRouter()

_spec = importlib.util.spec_from_file_location("planetai_pack_earth_adapter_for_routes", Path(__file__).with_name("adapter.py"))
pack = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pack)  # type: ignore[union-attr]


def _latest() -> dict | None:
    """The newest comparison, preferring a year-over-year pair over a longer span."""
    out = pack.changes()
    if not out:
        return None
    yoy = [c for c in out if c.get("year_b", 0) - c.get("year_a", 0) == 1]
    return (yoy or out)[-1]


def _imagery(source: str) -> list[int]:
    """The years of the other record, the earth-engine pack's Sentinel-2 or Landsat frames, while that pack is on."""
    mod = packs.module("earth-engine", "routes")
    return sorted(mod.frames(source)) if mod else []


@router.get("/earth")
def earth():
    """What the earth pack has: the years of AlphaEarth embeddings cached for this node's square, and the
    latest year-over-year comparison it computed from them. Empty until `planetai run earth fetch`; never an
    error, so the dashboard card can say what is missing instead of showing a blank box."""
    d = pack.cache()
    years = sorted(int(p.stem) for p in d.glob("*.npy") if p.stem.isdigit()) if d.is_dir() else []
    size = sum(p.stat().st_size for p in d.glob("*")) if d.is_dir() else 0
    frames = sorted(int(f.stem[5:]) for f in d.glob("year_*.png") if f.stem[5:].isdigit()) if d.is_dir() else []
    changes = pack.changes()
    latest = _latest()
    for c in changes:                       # so a NAS, or anything else, can fetch each map without guessing
        c["png_url"] = f"/earth/change.png?pair={c['year_a']}_{c['year_b']}"
    # The other record, if the earth-engine pack has ever run: real imagery, brightness-matched,
    # `partial` wherever it is drawn. Named separately from `frames` because they are different
    # things and a page that merges them is telling a reader a model output is a photograph.
    body = {"node": pack.node(), "enabled": True, "years": years, "bytes": size, "latest": latest,
            "changes": changes, "frames": frames, "dir": str(d),
            "imagery": {"sentinel": _imagery("sentinel"), "landsat": _imagery("landsat"),
                        "credit": ["Contains modified Copernicus Sentinel data, processed by "
                                   "Google Earth Engine.",
                                   "Landsat courtesy of the U.S. Geological Survey."]},
            "png": "/earth/change.png" if latest and (d / str(latest.get("png", ""))).is_file() else None,
            "lat": float(os.getenv("NODE_LAT", 0) or 0), "lon": float(os.getenv("NODE_LON", 0) or 0),
            "radius_m": int(settings.get("EARTH_RADIUS_M", "5000") or 5000),
            "attribution": "The AlphaEarth Foundations Satellite Embedding dataset is produced by Google and "
                           "Google DeepMind. CC BY 4.0."}
    if not years:
        body["hint"] = "no satellite record yet: planetai run earth fetch"
    elif not latest:
        body["hint"] = f"{len(years)} year(s) cached, nothing compared yet: planetai run earth change"
    elif not frames:
        body["hint"] = f"{len(years)} year(s) cached; for the year-by-year pictures: planetai run earth frames"
    return body


@router.get("/earth/change.png")
def earth_change_png(pair: str = Query("", pattern=r"^(\d{4}_\d{4})?$")):
    """A land-change map the earth pack drew: the latest, or `?pair=2023_2025`. The file name always comes
    from the pack's own JSON, never from the request — the pair only chooses among the comparisons this node
    actually computed — and only a .png inside this node's own earth directory is served."""
    want = _latest() if not pair else next(
        (c for c in pack.changes() if f"{c.get('year_a')}_{c.get('year_b')}" == pair), None)
    name = Path(str((want or {}).get("png", ""))).name
    p = pack.cache() / name
    if not (name.endswith(".png") and p.is_file()):
        raise HTTPException(404, "no such land-change map: planetai run earth change")
    return FileResponse(p, media_type="image/png", filename=name)


@router.get("/earth/year.png")
def earth_year_png(year: int = Query(..., ge=1900, le=2200)):
    """One year of the square as the earth pack drew it. The year is an integer and the name is built here,
    so nothing from the request reaches the filesystem as a path."""
    p = pack.cache() / f"year_{year}.png"
    if not p.is_file():
        raise HTTPException(404, f"no frame for {year}: planetai run earth frames")
    return FileResponse(p, media_type="image/png", filename=p.name)
