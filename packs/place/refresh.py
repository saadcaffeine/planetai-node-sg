"""Force a fetch from Overpass and a recount from Open Buildings now, instead of waiting for the monthly refresh. planetai run place refresh"""
import os, sys
sys.path.insert(0, os.path.dirname(__file__))
import httpx, psycopg
import adapter as A
lat, lon, radius = float(os.environ["NODE_LAT"]), float(os.environ["NODE_LON"]), int(os.getenv("PLACE_RADIUS_M", "1000"))
with psycopg.connect(os.environ["DATABASE_URL"]) as con:
    with con.cursor() as cur: cur.execute(A.DDL); con.commit()
    n = A.refresh(con, httpx.Client(timeout=120), lat, lon, radius)
    # The satellite's half too. A forced refresh restarts the monthly clock, so without it the count waits another month.
    try:
        sat = f"{A.satellite_refresh(con, lat, lon, radius)} years of Open Buildings recounted"
    except (Exception, SystemExit) as e:  # noqa: BLE001  init_ee leaves with SystemExit where earthengine-api is not installed
        sat = f"Open Buildings skipped ({type(e).__name__}: {(str(e).splitlines() or [""])[0][:120]})"
print(f"place: {n} features stored, {sat}. The next poll turns the features into readings.")
