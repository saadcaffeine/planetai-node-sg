"""Check the place pack end to end on this node: PostGIS, OpenStreetMap, Earth Engine + Open Buildings.  planetai run place verify"""
import os, sys, time
import httpx, psycopg
sys.path.insert(0, os.path.dirname(__file__))
import adapter as A
lat, lon = float(os.environ["NODE_LAT"]), float(os.environ["NODE_LON"]); radius = int(os.getenv("PLACE_RADIUS_M", "1000"))
def step(n, ok, msg): print(f"  {'✓' if ok else '✗'} {n}: {msg}")
try:
    con = psycopg.connect(os.environ["DATABASE_URL"]); cur = con.cursor()
    cur.execute("CREATE EXTENSION IF NOT EXISTS postgis"); con.commit(); cur.execute("SELECT PostGIS_Version()"); step(1, True, f"PostGIS {cur.fetchone()[0]}")
except Exception as e:
    step(1, False, f"PostGIS: {e}. Did planetai update switch the database image? docker compose ps"); sys.exit(1)
# Before the refresh below fixes it: are the stored features from this point? A node whose coordinates changed
# in .env kept serving the previous neighbourhood, and computed distances from the new point to the old features.
try:
    cur.execute("SELECT run_at, radius_m, lat, lon FROM place_runs ORDER BY run_at DESC LIMIT 1"); last = cur.fetchone()
    if last is None:
        step(2, True, "nothing fetched yet; the next poll will fetch around this point")
    elif last[2] is None or last[3] is None:
        step(2, True, f"the run of {last[0]:%Y-%m-%d} predates point tracking; the next poll refetches and records it")
    else:
        d = A.metres(last[2], last[3], lat, lon)
        ok = not A.moved(lat, lon, last[2], last[3], radius)
        step(2, ok, f"the stored features are from {last[2]:.5f}, {last[3]:.5f} at {last[1]} m, {d:.0f} m from this node"
                    + ("" if ok else " — until a refresh, the plan and every distance describe the previous point: planetai run place refresh"))
except Exception as e:
    step(2, False, f"place_runs: {e}")
try:
    t0 = time.time(); n = A.refresh(con, httpx.Client(timeout=120), lat, lon, radius); step(3, True, f"OpenStreetMap: {n} features within {radius} m in {time.time()-t0:.0f}s")
except Exception as e:
    step(3, False, f"OpenStreetMap via Overpass: {e}")
try:
    import satellite as S
    ee = S.init_ee(); step(4, True, "Earth Engine credentials accepted")
    t0 = time.time(); n, conf = S.footprints(ee, con, lat, lon, radius); step(5, True, f"Open Buildings V3: {n} footprints, mean confidence {conf:.2f}, {time.time()-t0:.0f}s")
    # both count the same circle: a last year several times off the footprints is the count band misread (satellite.py yearly)
    t0 = time.time(); ys = S.yearly(ee, lat, lon, radius); ok = not ys or n / 3 <= ys[-1][1] <= n * 3
    step(6, ok, f"Open Buildings Temporal: {', '.join(f'{y}: {round(c)} bld, {h:.1f} m' if h else f'{y}: {round(c)} bld' for y, c, h in ys)} ({time.time()-t0:.0f}s)"
                + ("" if ok else f" — the last year is several times off the {n} footprints, so the series is misread and must not be shown"))
except Exception as e:
    step(4, False, f"Earth Engine / Open Buildings: {type(e).__name__}: {str(e)[:160]}. Configure the earth-engine pack first; the place pack reuses its key.")
print("\nNext: planetai run place gaps  — the mapping briefing.")
