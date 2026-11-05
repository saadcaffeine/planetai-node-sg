"""GET /earth/frame.png: one year of the Sentinel-2 or Landsat record this pack's timelapse left in out/.

A route of this pack since 23 Oct 2026; until then app/main.py, moved with its answers unchanged. The node mounts it
from here (app/packs.py::routers) and answers 404 while this pack is off. `frames()` is also what the earth pack's
GET /earth lists as `imagery`.
"""
from __future__ import annotations

import os
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

router = APIRouter()


def frames(source: str = "sentinel") -> dict[int, Path]:
    """The frames `planetai run earth-engine timelapse` left in out/, by year.

    Matched by glob and not by name. The pack writes `<node>-<year>-<source>-<km>km.png`, and the
    node name in that filename is whatever the node was called the day the pack ran — on node #1 the
    files say `bayu-2` and NODE_NAME has since become `bayu-ungasan`, so building the name from NODE
    finds nothing. The km changes with the pack's own settings too. The year is the only part of the
    name this node can be sure of.
    """
    out = {}
    for f in sorted(Path(os.getenv("PACK_OUT", "/app/out")).glob(f"*-[0-9][0-9][0-9][0-9]-{source}-*.png")):
        try:
            out[int(f.stem.split("-")[-3])] = f
        except (ValueError, IndexError):        # a file that merely looks like one of ours
            continue
    return out


@router.get("/earth/frame.png")
def earth_frame_png(year: int = Query(..., ge=1972, le=2200),
                    source: str = Query("sentinel", pattern=r"^(sentinel|landsat)$")):
    """One year from the *other* satellite record: real imagery, brightness-matched across the years.

    This is not what /earth/year.png serves. That one is this node's own AlphaEarth layer — a model's
    64-number description of every 10 m pixel, flattened to one number and drawn in grey, never a
    photograph. These are Sentinel-2 (or Landsat) annual medians fetched through Earth Engine, so
    they are `partial`: somebody else's cluster made them, and they carry their own credit line.

    Both are on the Land band and on the wall, and the page must never let a reader take one for the
    other. Neither the year nor the source reaches the filesystem as a path: the year is an integer
    in range, the source is one of two words, and the file itself comes from a glob of out/.
    """
    have = frames(source)
    p = have.get(year)
    if not p:
        raise HTTPException(404, f"no {source} frame for {year}"
                                 + (f"; this node has {sorted(have)}" if have
                                    else ": planetai run earth-engine timelapse"))
    return FileResponse(p, media_type="image/png", filename=p.name)
