"""PurpleAir, read on the household's own WiFi, no cloud.

A pack since 22 Oct 2026; until then this was app/sources.py, moved unchanged: the sensor ids (`pa-<serial>`), the
source name (`purpleair`) and the settings (PURPLEAIR_HOSTS, SENSOR_INDOOR) are the same, and the EPA 2021 correction
is packs/air-quality's since 24 Oct 2026 (its epa_2021_correct, borrowed whether or not that pack is on). Its readers
were dropped from the poll in v0.16 (5 Sep 2026) by accident, while the setting and the installer's flag stayed, so a
node that set PURPLEAIR_HOSTS read nothing from then until this pack.

It runs whenever PURPLEAIR_HOSTS is set: `switch: [PURPLEAIR_HOSTS]` in pack.yaml.

Contract: fetch(hc) -> (sensors, readings), like everything in app/sources.py.
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timezone

import httpx

sys.path.insert(0, "/app")
import settings  # noqa: E402
import packs  # noqa: E402

epa_2021_correct = packs.module("air-quality", on_only=False).epa_2021_correct

# Every PurpleAir sensor serves http://<ip>/json?live=true on its WiFi. Fields: pm2_5_cf_1, pm2_5_cf_1_b (two laser
# channels), pm2_5_atm, pm10_0_cf_1, current_humidity, current_temp_f, pressure, SensorId, lat, lon, Geo.
# EPA 2021 is defined on the A/B average of cf_1 — we do exactly that. Temp is °F and reads high; we convert, not correct.
# Set PURPLEAIR_HOSTS=192.168.1.60   (IP; the .local name is unreliable on PurpleAir)
def purpleair(hc: httpx.Client, hosts: list[str], lat: float | None, lon: float | None, indoor: bool):
    sensors, readings = [], []
    ts = datetime.now(timezone.utc)
    for host in hosts:
        d = hc.get(f"http://{host}/json?live=true", timeout=10).json()
        sid = f"pa-{str(d.get('SensorId') or host).replace(':', '').lower()}"
        sensors.append({"sensor_id": sid, "source": "purpleair", "name": f"PurpleAir {d.get('Geo') or sid}",
                        "lat": d.get("lat") or lat, "lon": d.get("lon") or lon, "indoor": indoor, "local": True,
                        "meta": {"host": host, "hardware": d.get("hardwarediscovered"), "correction": "EPA 2021 on mean(cf_1 A,B)"}})
        chans = [float(d[k]) for k in ("pm2_5_cf_1", "pm2_5_cf_1_b") if d.get(k) is not None]
        if chans:
            raw = sum(chans) / len(chans)
            rh = float(d.get("current_humidity", 50.0))
            readings.append((ts, sid, "pm25_raw", raw))
            readings.append((ts, sid, "pm25", max(0.0, epa_2021_correct(raw, rh))))
            if len(chans) == 2 and abs(chans[0] - chans[1]) > max(5.0, 0.7 * raw):
                readings.append((ts, sid, "channel_disagreement", abs(chans[0] - chans[1])))   # a laser is failing; rule on this later
        if d.get("pm10_0_cf_1") is not None:
            readings.append((ts, sid, "pm10", float(d["pm10_0_cf_1"])))
        if d.get("current_humidity") is not None:
            readings.append((ts, sid, "humidity", float(d["current_humidity"])))
        if d.get("current_temp_f") is not None:
            readings.append((ts, sid, "temp", (float(d["current_temp_f"]) - 32) * 5 / 9))
        if d.get("pressure") is not None:
            readings.append((ts, sid, "pressure", float(d["pressure"]) / 10))   # hPa → kPa
    return sensors, readings


def fetch(hc):
    """Every host listed, with the node's own coordinates and SENSOR_INDOOR, as the core read them."""
    hosts = [h for h in settings.get("PURPLEAIR_HOSTS", "").replace(" ", "").split(",") if h]
    lat = float(os.environ["NODE_LAT"]) if os.getenv("NODE_LAT") else None
    lon = float(os.environ["NODE_LON"]) if os.getenv("NODE_LON") else None
    indoor = settings.get("SENSOR_INDOOR", "0") == "1"
    return purpleair(hc, hosts, lat, lon, indoor) if hosts else ([], [])
