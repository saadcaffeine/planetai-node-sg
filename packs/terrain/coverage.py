"""Which elevation this node would use, before anything is downloaded.  planetai run terrain coverage"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import adapter as A                                                              # noqa: E402

lat, lon, radius = A.aoi()
cov = A.coverage()
print(f"terrain · {A.node()} · {lat}, {lon} · {2 * radius / 1000:.1f} km square")
print(f"  uses: {cov['kind']} — {cov['why']}")
for t in cov["tiles"]:
    print(f"    {t}")
for t in cov["missing"]:
    print(f"    {t}  (not in the bucket: read as sea)" if cov["kind"] != "none" else f"    {t}")
if cov["kind"] == "none":
    print("\n  Nothing to compute. A GeoTIFF of your own goes in TERRAIN_DEM_PATH, its licence in TERRAIN_DEM_LICENCE.")
    sys.exit(1)
print("\n  Next: planetai run terrain fetch")
