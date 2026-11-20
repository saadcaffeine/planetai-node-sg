"""Today: what the sun gives this roof, beside what the household uses.

`read()` takes today's hourly `fc_shortwave` from the node's own Open-Meteo point (`forecast-om`) and, with Home
Assistant connected, today's `home_roof_kwh`, both from the node's database. `box()` turns them into the Today box.
No forecast rows is no sun and no roof line, never 0.
"""
from __future__ import annotations

import logging
import os

log = logging.getLogger("planetai.energy")

# ponytail: a typical performance ratio for a rooftop system (inverter, heat, dust, wiring); ENERGY_PANEL_PR is the
# knob for a roof that is known to do better or worse.
PR = 0.75

SQL = """SELECT metric, value FROM readings
         WHERE ((sensor_id = 'forecast-om' AND metric = 'fc_shortwave')
             OR (sensor_id = 'energy-home' AND metric = 'home_roof_kwh'))
           AND (ts AT TIME ZONE %s)::date = (now() AT TIME ZONE %s)::date
         ORDER BY ts"""


def setting(name: str, default: str) -> float | None:
    """A number from the pack's settings. Blank, or not a number, is None: no panels, no daily use, no line."""
    try:
        return float(os.getenv(name, default))
    except ValueError:
        return None


def box(sun_w_m2_hourly: list[float], panel_kw: float | None, use_kwh: float | None,
        roof_kwh_measured: float | None) -> dict:
    sun = round(sum(sun_w_m2_hourly) / 1000.0, 2) if sun_w_m2_hourly else None
    pr = setting("ENERGY_PANEL_PR", str(PR))
    if roof_kwh_measured is not None:
        roof = roof_kwh_measured
    elif sun is not None and panel_kw is not None and pr is not None:
        roof = round(panel_kw * sun * pr, 2)
    else:
        roof = None
    return {"sun_kwh_m2": sun, "roof_kwh": roof, "use_kwh": use_kwh, "measured": roof_kwh_measured is not None,
            "panel_kw": panel_kw}


def read() -> tuple[list[float], float | None]:
    """Today's hourly W/m² and the roof's measured kWh so far (None without HA rows), in the node's own day (NODE_TZ)."""
    tz = os.getenv("NODE_TZ", "").strip() or "UTC"
    try:
        import psycopg
        with psycopg.connect(os.environ["DATABASE_URL"], connect_timeout=5) as con, con.cursor() as cur:
            cur.execute(SQL, (tz, tz))
            rows = cur.fetchall()
    except Exception as e:  # noqa: BLE001 — no database to read is no sun figure, never no grid
        log.info("energy: no forecast sun to read (%s)", type(e).__name__)
        return [], None
    roof = [float(v) for m, v in rows if m == "home_roof_kwh"]
    return [float(v) for m, v in rows if m == "fc_shortwave"], (round(sum(roof), 3) if roof else None)
