"""The ground, kept on this node's disk (the base map): GET /ground/meta, /ground/wind, /ground/glyphs/..., /ground/{layer}/{z}/{x}/{y}.

`planetai run place basemap` (vector, fonts, drone mosaics) and `planetai run earth-engine basemap` (Sentinel-2)
fetch a detailed map of this place once into out/ground/, and the forecast pack writes the wind field there; these
routes serve it, so a map drawn from them asks nobody anything. On the `open` list: public data, centred no closer
than /health's rounded point (app/auth.py, `/ground/`).

A module of its own since 24 Oct 2026, moved unchanged out of app/main.py (review item 15); app/ground.py is the
hero's own cell drawing, a different thing. It stays in the core and
not in a pack because it serves three packs' files, and place, its main source, is core.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

from fastapi import APIRouter, HTTPException

router = APIRouter()

GROUND_LAYERS = {"vector": "application/x-protobuf", "imagery": "image/png", "drone": "image/png"}


OUT = Path(os.getenv("PACK_OUT", "/app/out"))      # the one writable mount, as app/main.py's OUT


def ground_dir() -> Path:
    return OUT / "ground"


@router.get("/ground/meta")
def ground_meta():
    """What the node holds of its own map: each layer's source, licence, attribution, tile count, bytes and when it
    was fetched, from out/ground/meta.json, and which layers are actually on disk. Never an error."""
    g = ground_dir()
    try:
        meta = json.loads((g / "meta.json").read_text())
    except (OSError, ValueError):
        meta = {}
    have = {k: (g / f"{k}.mbtiles").is_file() for k in GROUND_LAYERS}
    have["glyphs"] = (g / "glyphs").is_dir()
    have["wind"] = (g / "wind.json").is_file()
    return {"layers": meta, "on_disk": have,
            "fetch": {"vector": "planetai run place basemap --only vector", "drone": "planetai run place basemap --only drone",
                      "imagery": "planetai run earth-engine basemap", "wind": "planetai run forecast windfield"}}


@router.get("/ground/wind")
def ground_wind():
    """The wind over the node's square for a map to draw moving: the forecast pack's Open-Meteo field, n×n points,
    hourly for the next day (out/ground/wind.json, refreshed on each forecast poll). 204 when the node has none,
    which is every node with FORECAST_OPENMETEO=0."""
    from fastapi.responses import Response
    p = ground_dir() / "wind.json"
    if not p.is_file():
        return Response(status_code=204)
    return Response(p.read_bytes(), media_type="application/json", headers={"cache-control": "no-cache"})


@router.get("/ground/glyphs/{font}/{span}")
def ground_glyphs(font: str, span: str):
    """The label fonts the vector map draws names with, as MapLibre asks for them: one face, one range of 256."""
    from fastapi.responses import Response
    if not re.fullmatch(r"[A-Za-z ]{1,40}", font) or not re.fullmatch(r"\d{1,5}-\d{1,5}\.pbf", span):
        raise HTTPException(404, "no such glyphs")
    p = ground_dir() / "glyphs" / font / span
    if not p.is_file():
        return Response(status_code=204)
    return Response(p.read_bytes(), media_type="application/x-protobuf", headers={"cache-control": "max-age=86400"})


@router.get("/ground/{layer}/{z}/{x}/{y}")
def ground_tile(layer: str, z: int, x: int, y: str):
    """One tile of the node's own map, XYZ addressed (`y` may carry .pbf, .png or .jpg). 204 where the node holds
    none, which a map reads as empty ground rather than an error."""
    from fastapi.responses import Response
    import sqlite3
    if layer not in GROUND_LAYERS:
        raise HTTPException(404, "no such ground layer")
    try:
        yy = int(y.split(".")[0])
    except ValueError:
        raise HTTPException(422, "y must be a number") from None
    p = ground_dir() / f"{layer}.mbtiles"
    if not p.is_file() or not (0 <= z <= 22 and 0 <= x < 2 ** z and 0 <= yy < 2 ** z):
        return Response(status_code=204)
    con = sqlite3.connect(f"file:{p}?mode=ro", uri=True)
    try:
        row = con.execute("SELECT tile_data FROM tiles WHERE zoom_level=? AND tile_column=? AND tile_row=?",
                          (z, x, (1 << z) - 1 - yy)).fetchone()
    finally:
        con.close()
    if not row:
        return Response(status_code=204)
    data, head = row[0], {"cache-control": "max-age=3600"}
    if data[:2] == b"\x1f\x8b":
        head["content-encoding"] = "gzip"               # vector tiles are kept gzipped, as Protomaps ships them
    kind = GROUND_LAYERS[layer] if layer == "vector" else ("image/jpeg" if data[:2] == b"\xff\xd8" else "image/png")
    return Response(data, media_type=kind, headers=head)
