"""Check the pack against the bucket, the arithmetic and the node, and say which line failed.  planetai run terrain verify

Five checks: the libraries import, the node's tile answers without a key, the kept result describes this point,
every land cell in it drains (the one check that fails if the fill breaks), and the reading reached the database.
"""
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))
import adapter as A                                                              # noqa: E402

fails = []


def step(n, ok, msg):
    print(f"  {'✓' if ok else '✗'} {n}: {msg}")
    if not ok:
        fails.append(f"{n}: {msg}")


try:
    import numpy as np
    import rasterio
    step(1, True, f"numpy {np.__version__}, rasterio {rasterio.__version__}")
except ImportError as e:
    step(1, False, f"{e}. planetai packs install, then planetai restart")
    sys.exit(1)

cov = A.coverage()
step(2, cov["kind"] != "none", f"{cov['kind']}: {cov['why']}")

r = A.result()
step(3, bool(r), "the kept result is around this point" if r else
     "nothing kept for this point and radius: planetai run terrain fetch")

if r and cov["kind"] != "none":
    z, sea, dx, dy, rc = A.read(cov)
    f = A.fill(z, sea)
    _, drop = A.steepest(f, dx, dy)
    n = A.stuck(f, sea, drop)
    step(4, n == 0, f"{n} land cells with nowhere to drain after the fill" if n else
         f"every one of {int((~sea).sum())} land cells drains to the edge or the sea")

try:
    import psycopg
    with psycopg.connect(os.environ["DATABASE_URL"]) as con, con.cursor() as cur:
        # Only rows of THIS fetch: the terrain rows carry the fetch's own timestamp, so an older fetch's rows
        # still in the database do not pass for this one.
        cur.execute("SELECT metric, value, ts FROM observations WHERE sensor_id = 'terrain-point' ORDER BY metric")
        rows = cur.fetchall()
    t = r and datetime.fromisoformat(r["computed_at"])
    mine = [(m, v) for m, v, ts in rows if t and (ts == t or (m in ("rain_24h_mm", "water_24h_m3") and ts > t))]
    step(5, any(m == "terrain_upslope_ha" for m, _ in mine), ", ".join(f"{m} {v:g}" for m, v in mine) if mine else
         "no terrain-point rows from this fetch yet: is terrain in PACKS_ENABLED, and has the node polled since?")
except Exception as e:  # noqa: BLE001
    step(5, False, f"the database did not answer ({type(e).__name__})")

print(f"\n{A.ATTRIBUTION}")
sys.exit(1 if fails else 0)
