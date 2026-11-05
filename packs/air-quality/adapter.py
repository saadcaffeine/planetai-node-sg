"""The air this node reads before it has a sensor, and the correction a cheap sensor's PM2.5 needs.

A pack since 24 Oct 2026; until then this was app/sources.py and app/bootstrap.py, moved unchanged: the sensor id
(`cams-point`), the source name (`open-meteo-cams`), the metrics and the switch (OPENMETEO_ENABLED) are the same.

  fetch(hc)                 CAMS now, at the node's coordinates, every poll
  history(hc, lat, lon)     92 days of hourly CAMS, once, on the node's first start (app/bootstrap.py calls it)
  epa_2021_correct(x, rh)   the US EPA 2021 humidity correction, which packs/airgradient and packs/purpleair borrow

Contract: fetch(hc) -> (sensors, readings), like everything in app/sources.py.
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timezone

import httpx

sys.path.insert(0, "/app")
from sources import _iso  # noqa: E402


# ---------------------------------------------------------------- Open-Meteo Air Quality (CAMS) — zero-config
# Free, key-free, global. Copernicus Atmosphere Monitoring Service: satellite + model reanalysis, ~11 km grid.
# This is the adapter that makes a node useful before any hardware exists: modelled PM2.5 at your coordinates,
# anywhere on earth, from the first minute. It is a MODEL, not a measurement — kind='model', never 'live' in a cell,
# and it is the thing your sensor gets compared against, not the thing that replaces it.
# Attribution required: CAMS ENSEMBLE data provider and Open-Meteo. Carried in sensors.meta.
OM_AIR = "pm2_5,pm10,dust,aerosol_optical_depth,carbon_monoxide,nitrogen_dioxide,ozone,uv_index"
OM_AIR_MAP = {"pm2_5": "pm25_model", "pm10": "pm10_model", "dust": "dust", "aerosol_optical_depth": "aod",
              "carbon_monoxide": "co", "nitrogen_dioxide": "no2", "ozone": "o3", "uv_index": "uv_index"}
OM_AIR_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"


def _sensor(lat, lon):
    return {"sensor_id": "cams-point", "source": "open-meteo-cams", "name": "CAMS air quality (model point sample)",
            "lat": lat, "lon": lon, "indoor": False, "local": False, "kind": "model", "scale": "planet",
            "cadence": "PT1H",
            "meta": {"model": "Copernicus CAMS global/European ensemble via open-meteo.com",
                     "attribution": "CAMS ENSEMBLE data provider and Open-Meteo",
                     "note": "modelled, not measured — the baseline a local sensor is compared against"}}


def openmeteo_air(hc: httpx.Client, lat: float, lon: float):
    r = hc.get(OM_AIR_URL, params={"latitude": round(lat, 3), "longitude": round(lon, 3), "current": OM_AIR, "timezone": "UTC"})
    r.raise_for_status()
    cur = (r.json().get("current") or {})
    t = cur.get("time")
    ts = _iso(t if not t or str(t).endswith("Z") else f"{t}Z") or datetime.now(timezone.utc)
    readings = [(ts, "cams-point", m, float(cur[k])) for k, m in OM_AIR_MAP.items() if cur.get(k) is not None]
    return [_sensor(lat, lon)], readings


def fetch(hc: httpx.Client):
    if not os.getenv("NODE_LAT"):
        return [], []
    return openmeteo_air(hc, float(os.environ["NODE_LAT"]), float(os.environ["NODE_LON"]))


def history(hc: httpx.Client, lat: float, lon: float, days: int = 92):
    """Hourly CAMS PM2.5/PM10 for the past N days (92 is the API maximum). One call, ~4,400 rows (two metrics an hour)."""
    r = hc.get(OM_AIR_URL, params={"latitude": lat, "longitude": lon, "hourly": "pm2_5,pm10",
                                   "past_days": min(days, 92), "forecast_days": 0, "timezone": "UTC"})
    r.raise_for_status()
    h = r.json().get("hourly") or {}
    times = h.get("time") or []
    out = []
    for key, metric in (("pm2_5", "pm25_model"), ("pm10", "pm10_model")):
        for t, v in zip(times, h.get(key) or []):
            if v is None:
                continue
            ts = _iso(t if str(t).endswith("Z") else f"{t}Z")
            if ts:
                out.append((ts, "cams-point", metric, float(v)))
    return [_sensor(lat, lon)], out


def epa_2021_correct(pm_raw: float, rh: float) -> float:
    """US EPA 2021 humidity correction for Plantower-based sensors (PurpleAir, AirGradient, DIY PMS5003).
    Barkjohn et al. 2021, extended 2022. Same formula Bali Air Dispatch applies before publishing those networks.
    Do NOT apply to Smart Citizen (Seeed HM-3301) or Nafas/IQAir/AQICN, which are published as-supplied.
    Verify coefficients against https://www.epa.gov before relying on this for anything published."""
    x, h = pm_raw, rh
    if x <= 30:
        return 0.524 * x - 0.0862 * h + 5.75
    if x <= 50:
        w = x / 20 - 1.5
        return (0.786 * w + 0.524 * (1 - w)) * x - 0.0862 * h + 5.75
    if x <= 210:
        return 0.786 * x - 0.0862 * h + 5.75
    if x <= 260:
        w = x / 50 - 4.2
        return (0.69 * w + 0.786 * (1 - w)) * x - 0.0862 * h * (1 - w) + 2.966 * w + 5.75 * (1 - w) + 8.84e-4 * x * x * w
    return 2.966 + 0.69 * x + 8.84e-4 * x * x
