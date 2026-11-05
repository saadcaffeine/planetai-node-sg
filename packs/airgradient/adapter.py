"""AirGradient ONE and Open Air, read on the household's own WiFi, no cloud.

A pack since 22 Oct 2026; until then this was app/sources.py, moved unchanged: the sensor ids (`ag-<serial>`), the
source name (`airgradient`) and the settings (AIRGRADIENT_HOSTS, SENSOR_INDOOR) are the same, and the EPA 2021
correction is packs/air-quality's since 24 Oct 2026 (its epa_2021_correct, borrowed whether or not that pack is on).
Its readers were dropped from the poll in v0.16 (5 Sep 2026) by accident, while the setting and the installer's flag
stayed, so a node that set AIRGRADIENT_HOSTS read nothing from then until this pack.

It runs whenever AIRGRADIENT_HOSTS is set: `switch: [AIRGRADIENT_HOSTS]` in pack.yaml.

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

# Every AirGradient ONE / Open Air exposes http://airgradient_<serial>.local/measures/current on your WiFi.
# Fields (firmware 3.x): pm01 pm02 pm10 pm003Count rco2 atmp rhum tvocIndex noxIndex serialno model firmware.
# Newer firmware adds *Compensated fields; we take the raw pm02 and apply EPA 2021 ourselves so the audit trail is ours.
# Set AIRGRADIENT_HOSTS=airgradient_84fce6.local,192.168.1.52   (hostname or IP, comma-separated)
AG_METRICS = {"pm01": "pm1", "pm10": "pm10", "rco2": "co2", "atmp": "temp", "rhum": "humidity",
              "tvocIndex": "tvoc_index", "noxIndex": "nox_index"}


def airgradient(hc: httpx.Client, hosts: list[str], lat: float | None, lon: float | None, indoor: bool):
    sensors, readings = [], []
    ts = datetime.now(timezone.utc)
    for host in hosts:
        d = hc.get(f"http://{host}/measures/current", timeout=10).json()
        serial = str(d.get("serialno") or host.replace(".local", "")).lower()
        sid = f"ag-{serial}"
        sensors.append({"sensor_id": sid, "source": "airgradient", "name": f"AirGradient {d.get('model', '')} {serial}".strip(),
                        "lat": lat, "lon": lon, "indoor": indoor, "local": True,
                        "meta": {"host": host, "firmware": d.get("firmware"), "model": d.get("model"),
                                 "correction": "EPA 2021 applied to pm02 (Plantower)"}})
        for k, metric in AG_METRICS.items():
            if d.get(k) is not None:
                readings.append((ts, sid, metric, float(d[k])))
        if d.get("pm02") is not None:
            raw = float(d["pm02"])
            readings.append((ts, sid, "pm25_raw", raw))
            rh = float(d["rhum"]) if d.get("rhum") is not None else 50.0
            readings.append((ts, sid, "pm25", max(0.0, epa_2021_correct(raw, rh))))
    return sensors, readings


def fetch(hc):
    """Every host listed, with the node's own coordinates and SENSOR_INDOOR, as the core read them."""
    hosts = [h for h in settings.get("AIRGRADIENT_HOSTS", "").replace(" ", "").split(",") if h]
    lat = float(os.environ["NODE_LAT"]) if os.getenv("NODE_LAT") else None
    lon = float(os.environ["NODE_LON"]) if os.getenv("NODE_LON") else None
    indoor = settings.get("SENSOR_INDOOR", "0") == "1"
    return airgradient(hc, hosts, lat, lon, indoor) if hosts else ([], [])
