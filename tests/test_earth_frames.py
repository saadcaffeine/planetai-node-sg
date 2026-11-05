"""The two satellite records are two records, and the route finds the frames a real node has.

node #1 is why this exists. `planetai run earth-engine timelapse` wrote
`out/bayu-2-2016-sentinel-3km.png` when the node was called bayu-2; NODE_NAME is bayu-ungasan now,
and a route that builds the filename from NODE finds nothing at all. The km in the name moves with
the pack's settings too. The year is the only part of that filename this node can be sure of.

Run: PYTHONPATH=app python3 tests/test_earth_frames.py   (needs the app's own deps, like import-check)
"""
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.chdir(ROOT)
sys.path.insert(0, str(ROOT / "app"))

tmp = tempfile.mkdtemp()
os.environ.update(PACK_OUT=tmp, DATABASE_URL="postgresql://x:x@127.0.0.1:1/x", NODE_NAME="bayu-ungasan",
                  NODE_CITY="bali", NODE_LAT="-8.8", NODE_LON="115.1", PACKS_DIR=str(ROOT / "packs"))
import importlib.util  # noqa: E402
import time  # noqa: E402
import settings  # noqa: E402
settings._cache = {"at": time.time() + 1e9, "rows": {"PACKS_ENABLED": ""}}   # every pack on, no database
from fastapi import HTTPException  # noqa: E402


def _load(pack):  # the routes moved into their packs on 23 Oct 2026: packs/earth/routes.py, packs/earth-engine/routes.py
    spec = importlib.util.spec_from_file_location(f"t_{pack}_routes", ROOT / "packs" / pack / "routes.py")
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    return m


ER, EER = _load("earth"), _load("earth-engine")

fails = []
out = Path(tmp)
# exactly what node #1 has in out/, old node name and all
for n in ("bayu-2-2016-sentinel-3km.png", "bayu-2-2019-sentinel-3km.png",
          "bayu-2-2022-sentinel-3km.png", "bayu-2-2025-sentinel-3km.png",
          "bayu-2-2012-landsat-2km.png", "bayu-2-2025-landsat-2km.png",
          "bayu-2-timelapse-sentinel.html",          # not a frame
          "change_2024_2025.png", "notes-sentinel-x.png"):
    (out / n).write_bytes(b"\x89PNG")

got = EER.frames("sentinel")
if sorted(got) != [2016, 2019, 2022, 2025]:
    fails.append(f"sentinel frames found {sorted(got)}, expected [2016, 2019, 2022, 2025]")
if sorted(EER.frames("landsat")) != [2012, 2025]:
    fails.append(f"landsat frames found {sorted(EER.frames('landsat'))}, expected [2012, 2025]")
if any("timelapse" in p.name or p.name.startswith("change_") for p in got.values()):
    fails.append("the glob picked up something that is not a frame")

# the whole point: the filename carries the node's OLD name and must still be found
if not all("bayu-2-" in p.name for p in got.values()):
    fails.append("this test no longer exercises the renamed-node case")
if ER.pack.node() != "bayu-ungasan":
    fails.append("NODE is not the new name, so the case above is not being tested")

# The two records stay apart in /earth's body: `frames` is this node's own AlphaEarth layer,
# `imagery` is somebody else's photographs. A page that merged them would be calling a model output
# a photograph.
body = ER.earth()
if "imagery" not in body or sorted(body["imagery"]["sentinel"]) != [2016, 2019, 2022, 2025]:
    fails.append(f"/earth must publish which imagery years exist: {body.get('imagery')}")
if body["imagery"]["sentinel"] == body.get("frames"):
    fails.append("the two satellite records must not be the same list")
if not any("Copernicus" in c for c in body["imagery"]["credit"]):
    fails.append("the imagery must carry its credit line")

# the route refuses what it does not have, and says what it does
try:
    EER.earth_frame_png(year=1999, source="sentinel")
    fails.append("a year with no frame must 404")
except HTTPException as e:
    if "2016" not in str(e.detail):
        fails.append(f"the 404 must name the years this node has: {e.detail}")
try:
    EER.earth_frame_png(year=2016, source="sentinel")
except Exception as e:  # noqa: BLE001
    fails.append(f"2016 exists and must be served: {type(e).__name__}")

# with nothing rendered at all, the 404 says which command makes them
for f in out.glob("*sentinel*"):
    f.unlink()
try:
    EER.earth_frame_png(year=2016, source="sentinel")
    fails.append("with no frames at all, the route must 404")
except HTTPException as e:
    if "earth-engine timelapse" not in str(e.detail):
        fails.append(f"the empty 404 must name the command: {e.detail}")

# ---------------------------------------------------------------- and the AlphaEarth cache, same rename
# out/earth/<node>/ was keyed on NODE_NAME too, which cost node #1 a 930 MB re-download of its own square and
# left 555 MB nothing reads. The embeddings describe a place: a directory whose meta.json was written around
# this point, at this radius, is this node's square whatever it is called. the route reads the pack's own cache()
# since 23 Oct 2026, so the rule has one copy and it is checked here through the route's module.
earth = out / "earth"
(earth / "bayu-2").mkdir(parents=True)
(earth / "bayu-2" / "meta.json").write_text(json.dumps({"lat": -8.8, "lon": 115.1, "radius_m": 5000}))
if ER.pack.cache() != earth / "bayu-2":
    fails.append(f"/earth must read the square the node fetched under its old name, got {ER.pack.cache()}")
(earth / "bayu-2" / "change_2024_2025.json").write_text(json.dumps(
    {"year_a": 2024, "year_b": 2025, "mean": 0.041, "png": "change_2024_2025.png"}))
if [c["year_b"] for c in ER.pack.changes()] != [2025]:
    fails.append("the comparisons under the old name must reach /earth")

(earth / "bayu-ungasan").mkdir()
(earth / "bayu-ungasan" / "meta.json").write_text(json.dumps({"lat": -8.8, "lon": 115.1, "radius_m": 5000}))
if ER.pack.cache() != earth / "bayu-ungasan":
    fails.append("with both on disk — node #1 today — the node's own name must win, so nothing switches under it")

# a square read around somewhere else is never adopted, whatever it is called
for d in (earth / "bayu-2", earth / "bayu-ungasan"):
    for f in d.glob("*"):
        f.unlink()
    d.rmdir()
(earth / "santiago").mkdir()
(earth / "santiago" / "meta.json").write_text(json.dumps({"lat": -33.431, "lon": -70.6045, "radius_m": 5000}))
if ER.pack.cache() != earth / "bayu-ungasan":
    fails.append(f"another city's square must never answer for this node: {ER.pack.cache()}")

print("\n".join(f"  x {f}" for f in fails) or
      "  earth frames: the glob finds a renamed node's frames and its cache, keeps the two records "
      "apart, and both 404s say what to do")
sys.exit(1 if fails else 0)
