"""Check the pack against the server, the kept result and the node, and say which line failed.  planetai run hydro verify

Four checks: pyshp imports, HydroSHEDS answers for this node's region without a key, the kept result describes this
point (and its nearest river really is the closest line in it), and the reading reached the database.
"""
import os
import sys
import urllib.request
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))
import adapter as A                                                              # noqa: E402

fails = []


def step(n, ok, msg):
    print(f"  {'✓' if ok else '✗'} {n}: {msg}")
    if not ok:
        fails.append(f"{n}: {msg}")


try:
    import shapefile
    step(1, True, f"pyshp {shapefile.__version__}")
except ImportError as e:
    step(1, False, f"{e}. planetai packs install, then planetai restart")

r = A.result()
lat, lon, km = A.aoi()
region = r.get("region") or (A.candidates(lat, lon) or ["au"])[0]
url = A.RIVERS.format(r=region)
try:
    req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "planetai-node/hydro (+https://planetai.fab.city)"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        step(2, resp.status == 200, f"{url.rsplit('/', 1)[1]} answers, {int(resp.headers.get('Content-Length', 0)) / 1e6:.0f} MB")
except Exception as e:  # noqa: BLE001
    step(2, False, f"{url} did not answer ({type(e).__name__}: {e})")

step(3, bool(r), f"kept for this point: {len(r['rivers']['features'])} reaches, {len(r['basins']['features'])} basins, region "
     f"{r['region']}" if r else "nothing kept for this point and square: planetai run hydro fetch")
if r and r.get("nearest"):
    d = min(A.to_line(lat, lon, f["geometry"]["coordinates"]) for f in r["rivers"]["features"])
    step("3b", abs(d - r["nearest"]["dist_m"]) < 5, f"the nearest kept river is {d:.0f} m away, as the result says "
         f"({r['nearest']['dist_m']} m)" if abs(d - r["nearest"]["dist_m"]) < 5 else
         f"the nearest kept river is {d:.0f} m away, the result says {r['nearest']['dist_m']} m")

try:
    import psycopg
    with psycopg.connect(os.environ["DATABASE_URL"]) as con, con.cursor() as cur:
        cur.execute("SELECT metric, value, ts FROM observations WHERE sensor_id = 'hydro-point' ORDER BY metric")
        rows = cur.fetchall()
    t = r and datetime.fromisoformat(r["fetched_at"])
    mine = [(m, v) for m, v, ts in rows if t and ts == t]
    step(4, any(m == "river_m" for m, _ in mine), ", ".join(f"{m} {v:g}" for m, v in mine) if mine else
         "no hydro-point rows from this fetch yet: is hydro in PACKS_ENABLED, and has the node polled since?")
except Exception as e:  # noqa: BLE001
    step(4, False, f"the database did not answer ({type(e).__name__})")

print(f"\n{A.ATTRIBUTION}")
sys.exit(1 if fails else 0)
