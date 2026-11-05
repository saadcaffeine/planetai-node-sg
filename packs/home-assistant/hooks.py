"""Home Assistant, over MQTT discovery: this house's sensors as HA entities, and the latest alert as one text sensor.

A pack since 22 Oct 2026; the code is what app/main.py and then app/channels.py ran, moved unchanged. The node calls
it at two points (app/packs.py::emit): `on_readings` after every batch it stores, and `on_alert` with every alert it
sends. It runs only while its switch, HA_DISCOVERY, is 1 and a broker is set (MQTT_HOST). HA_DISCOVERY stays a core
setting for now, because a pack cannot yet mark a key as one that changes what leaves the machine, and this one does.
"""
import json
import logging
import os
from datetime import datetime, timezone

import settings

log = logging.getLogger("planetai")

NODE = os.getenv("NODE_NAME", "node")
MQTT_HOST = os.getenv("MQTT_HOST", "").strip()
MQTT_USER, MQTT_PASS = os.getenv("MQTT_USER", ""), os.getenv("MQTT_PASS", "")


def HA_DISCOVERY():
    return settings.get("HA_DISCOVERY", "0") == "1" and bool(os.getenv("MQTT_HOST", "").strip())
_ha_announced: set = set()


# ---------------------------------------------------------------- Home Assistant (MQTT discovery)
# HA's MQTT integration watches homeassistant/<component>/<id>/config. Publish one config per sensor metric and
# HA creates the entity, grouped under a device per physical sensor. Then publish states. Retained, so HA sees
# them on restart. We publish; HA automates. The node never addresses a device.
HA_UNITS = {"pm25": ("µg/m³", "pm25"), "pm10": ("µg/m³", "pm10"), "pm1": ("µg/m³", "pm1"), "pm25_model": ("µg/m³", "pm25"),
            "temp": ("°C", "temperature"), "temp_model": ("°C", "temperature"), "humidity": ("%", "humidity"),
            "humidity_model": ("%", "humidity"), "pressure": ("kPa", "atmospheric_pressure"), "co2": ("ppm", "carbon_dioxide"),
            "battery_pct": ("%", "battery"), "battery_v": ("V", "voltage"), "aqi": (None, "aqi"),
            "wind_speed": ("km/h", "wind_speed"), "precipitation": ("mm", "precipitation"), "uv_index": (None, None)}


def on_readings(sensors: list[dict], readings: list[tuple]) -> None:
    """Every batch the node stores: one entity per local sensor metric, announced once, then its latest state."""
    if not HA_DISCOVERY() or not readings:
        return
    try:
        import paho.mqtt.publish as publish
        auth = {"username": MQTT_USER, "password": MQTT_PASS} if MQTT_USER else None
        by_id = {s["sensor_id"]: s for s in sensors}
        latest: dict[tuple, tuple] = {}
        for ts, sid, metric, value in readings:
            if (sid, metric) not in latest or ts > latest[(sid, metric)][0]:
                latest[(sid, metric)] = (ts, value)
        msgs = []
        for (sid, metric), (ts, value) in latest.items():
            s = by_id.get(sid, {})
            if not s.get("local", False) and s.get("kind", "sensor") == "sensor":
                continue                                # reference stations are not this house's entities
            uid = f"planetai_{NODE}_{sid}_{metric}".replace("-", "_").replace("/", "_")
            state_topic = f"planetai/{NODE}/{sid}/{metric}"
            if uid not in _ha_announced:
                unit, dclass = HA_UNITS.get(metric, (None, None))
                cfg = {"name": metric.replace("_", " "), "unique_id": uid, "state_topic": state_topic,
                       "state_class": "measurement", "expire_after": 3600,
                       "device": {"identifiers": [f"planetai_{NODE}_{sid}"], "name": s.get("name") or s.get("default_name") or sid,
                                  "manufacturer": "PLANETAI node", "model": s.get("source", "sensor"),
                                  "suggested_area": "Indoor" if s.get("indoor") else "Outdoor"}}
                if unit: cfg["unit_of_measurement"] = unit
                if dclass: cfg["device_class"] = dclass
                msgs.append({"topic": f"homeassistant/sensor/{uid}/config", "payload": json.dumps(cfg), "retain": True})
                _ha_announced.add(uid)
            msgs.append({"topic": state_topic, "payload": f"{value:g}", "retain": True})
        if msgs:
            publish.multiple(msgs, hostname=MQTT_HOST, auth=auth)
    except Exception as e:  # noqa: BLE001
        log.warning("home assistant publish failed: %s", type(e).__name__)


def on_alert(level: str, text: str, alert_id: int | None) -> None:
    """One text sensor per node carrying the latest alert, with level and id as attributes."""
    if not HA_DISCOVERY():
        return
    try:
        import paho.mqtt.publish as publish
        auth = {"username": MQTT_USER, "password": MQTT_PASS} if MQTT_USER else None
        uid = f"planetai_{NODE}_alert".replace("-", "_")
        msgs = []
        if uid not in _ha_announced:
            msgs.append({"topic": f"homeassistant/sensor/{uid}/config", "retain": True, "payload": json.dumps({
                "name": "latest alert", "unique_id": uid, "state_topic": f"planetai/{NODE}/alert",
                "json_attributes_topic": f"planetai/{NODE}/alert/attributes", "icon": "mdi:bell-alert",
                "device": {"identifiers": [f"planetai_{NODE}"], "name": f"PLANETAI {NODE}", "manufacturer": "PLANETAI node"}})})
            _ha_announced.add(uid)
        msgs.append({"topic": f"planetai/{NODE}/alert", "payload": text.split("\n")[0][:255], "retain": True})
        msgs.append({"topic": f"planetai/{NODE}/alert/attributes", "retain": True,
                     "payload": json.dumps({"level": level, "alert_id": alert_id, "ts": datetime.now(timezone.utc).isoformat()})})
        publish.multiple(msgs, hostname=MQTT_HOST, auth=auth)
    except Exception as e:  # noqa: BLE001
        log.warning("home assistant alert publish failed: %s", type(e).__name__)
