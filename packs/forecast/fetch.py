"""Fetch the forecast now instead of waiting for the next poll.  planetai run forecast fetch"""
import os
import sys

import httpx
import psycopg

sys.path.insert(0, os.path.dirname(__file__))
import adapter as A  # noqa: E402
sys.path.insert(0, "/app")
import store  # noqa: E402

sensors, readings = A.fetch(httpx.Client(timeout=60), force=True)
if not sensors:
    sys.exit("forecast: nothing fetched. Is FORECAST_BMKG_ADM4 set, or FORECAST_OPENMETEO=1?")
with psycopg.connect(os.environ["DATABASE_URL"]) as con, con.cursor() as cur:
    for s in sensors:
        cur.execute("""INSERT INTO sensors (sensor_id, source, name, lat, lon, indoor, local, kind, scale, cadence, meta)
                       VALUES (%(sensor_id)s,%(source)s,%(name)s,%(lat)s,%(lon)s,%(indoor)s,%(local)s,%(kind)s,%(scale)s,%(cadence)s,%(meta)s)
                       ON CONFLICT (sensor_id) DO UPDATE SET name=EXCLUDED.name, lat=EXCLUDED.lat, lon=EXCLUDED.lon,
                         meta=EXCLUDED.meta, cadence=EXCLUDED.cadence""",
                    {**s, "meta": psycopg.types.json.Json(s.get("meta") or {})})
    store.insert_readings(cur, readings)
    con.commit()
print(f"forecast: {len(sensors)} source(s), {len(readings)} readings for the next {A.HOURS} hours.")
print("planetai run forecast status")
