"""Fetch this node's rivers and basins once, keep what is near, delete the rest.  planetai run hydro fetch

Which HydroSHEDS region the node is in comes from the level-1 basins (1-3 MB each, one or two of them). Then three
downloads for that region: the level-12 and level-4 basins (up to 80 MB and 5 MB) and the rivers (50-110 MB). Each
is unpacked to disk, read with pyshp inside the square, and deleted, so the node keeps a few hundred KB. Run it again
only when the node moves or HYDRO_RADIUS_KM changes: HydroSHEDS v1 does not change.
"""
import json
import os
import shutil
import sys
import time
import urllib.request
import zipfile
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(__file__))
import adapter as A                                                              # noqa: E402

A.require("shapefile")
import shapefile                                                                 # noqa: E402

lat, lon, km = A.aoi()
box = A.square(lat, lon, km)
work = A.cache() / "download"
work.mkdir(parents=True, exist_ok=True)


def get(url: str) -> shapefile.Reader:
    """Download one zip, unpack its shapefile next to it, delete the zip, and open the shapefile."""
    name = url.rsplit("/", 1)[1]
    z = work / name
    t0 = time.time()
    req = urllib.request.Request(url, headers={"User-Agent": "planetai-node/hydro (+https://planetai.fab.city)"})
    with urllib.request.urlopen(req, timeout=60) as r, open(z, "wb") as f:
        shutil.copyfileobj(r, f, 1 << 20)
    mb = z.stat().st_size / 1e6
    d = work / name[:-4]
    with zipfile.ZipFile(z) as zf:
        zf.extractall(d)
    z.unlink()
    shp = next(d.rglob("*.shp"))
    print(f"  {name}: {mb:.0f} MB in {time.time() - t0:.0f} s")
    return shapefile.Reader(str(shp))


def containing(rd: shapefile.Reader, keep: tuple) -> dict | None:
    """The record whose polygon holds the node's point, or None (a point in the sea)."""
    for sr in rd.iterShapeRecords(bbox=[lon, lat, lon, lat]):
        if A.inside(lon, lat, A.rings_of(sr.shape)):
            return A.props(sr.record, keep)
    return None


try:
    # ---- the region: the level-1 basin that holds the point
    region = None
    for r in A.candidates(lat, lon):
        rd = get(A.BASINS.format(r=r, lev=1))
        hit = containing(rd, A.BASIN_KEEP)
        rd.close()
        if hit:
            region = A.PFAF_REGION.get(int(str(hit["pfaf_id"])[0]), r)
            break
    if not region:
        raise SystemExit(f"hydro: no HydroSHEDS land basin holds {lat}, {lon}. At sea, or on an island under the 15 "
                         f"arc-second coastline; nothing was written.")
    print(f"hydro · {A.node()} · region {region} · {2 * km} km square")

    # ---- the node's basins: its own at level 12 and level 4, and every level-12 basin in the square
    rd = get(A.BASINS.format(r=region, lev=4))
    b4 = containing(rd, A.BASIN_KEEP)
    rd.close()
    rd = get(A.BASINS.format(r=region, lev=12))
    b12, basins = None, []
    for sr in rd.iterShapeRecords(bbox=list(box)):
        rings = A.rings_of(sr.shape)
        p = A.props(sr.record, A.BASIN_KEEP)
        if A.inside(lon, lat, rings):
            b12, p["here"] = p, True
        basins.append({"type": "Feature", "properties": p,
                       "geometry": {"type": "Polygon", "coordinates": [A.rnd(x, 4) for x in rings]}})
    rd.close()

    # ---- the rivers in the square, and the nearest one
    rd = get(A.RIVERS.format(r=region))
    rivers, nearest = [], None
    for sr in rd.iterShapeRecords(bbox=list(box)):
        pts = sr.shape.points
        p = A.props(sr.record, A.RIVER_KEEP)
        p["dist_m"] = round(A.to_line(lat, lon, pts))
        if nearest is None or p["dist_m"] < nearest["dist_m"]:
            nearest = p
        rivers.append({"type": "Feature", "properties": p, "geometry": {"type": "LineString", "coordinates": A.rnd(pts)}})
    rd.close()
    largest = max((f["properties"] for f in rivers), key=lambda x: x["dis_av_cms"], default=None)
finally:
    shutil.rmtree(work, ignore_errors=True)

out = {"lat": lat, "lon": lon, "radius_km": km, "region": region, "fetched_at": datetime.now(timezone.utc).isoformat(),
       "release": A.RELEASE, "attribution": A.ATTRIBUTION, "nearest": nearest, "largest": largest, "basin": {"level12": b12, "level4": b4},
       "rivers": {"type": "FeatureCollection", "features": rivers},
       "basins": {"type": "FeatureCollection", "features": basins}}
A.result_file().write_text(json.dumps(out, separators=(",", ":")))

print(f"  kept {len(rivers)} river reaches and {len(basins)} level-12 basins, "
      f"{A.result_file().stat().st_size / 1e3:.0f} KB")
if nearest:
    print(f"  nearest river: {A.sentence(nearest)}")
    print(f"  largest river in the square: {A.sentence(largest)}")
else:
    print(f"  no HydroRIVERS reach within {km} km: rivers start where 10 km² drains, so a dry island or a plateau has none")
if b12:
    print(f"  its basin: level 12 #{b12['hybas_id']}, {b12['sub_area']:,.0f} km² of its own, {b12['up_area']:,.0f} km² with "
          f"everything upstream")
if b4:
    print(f"  its bioregion: level 4 basin {b4['pfaf_id']}, {b4['sub_area']:,.0f} km² (the one index.fab.city draws)")
print(f"\n  {A.ATTRIBUTION}")
