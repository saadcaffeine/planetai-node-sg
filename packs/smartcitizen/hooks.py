"""Smart Citizen, direct: kits and Making Sense Bali DIY nodes that publish to this node's own broker.

A pack since 22 Oct 2026, with packs/smartcitizen/adapter.py (the kits read from api.smartcitizen.me). Until then the
parser was app/sources.py and the rest app/main.py, moved here unchanged: the sensor ids (`sck-` + a hash of the
token), the source name (`smartcitizen-direct`), the forward to the platform (SC_FORWARD) and /health's `direct` key.

The node calls it at three points (app/packs.py): it subscribes to MQTT_TOPICS on its broker, hands every message on
them to `on_mqtt`, which returns what to store, and merges `status()` into /health. It runs whenever a kit is
configured or a broker is set (`switch: [SC_USER, SC_DEVICES, MQTT_HOST]` in pack.yaml), the condition the core used.
SC_FORWARD stays a core setting, because a pack cannot yet mark a key as one that changes what leaves the machine.
"""
from __future__ import annotations

import collections
import json as _json
import logging
import os
import sys
import threading
import time
from datetime import datetime, timezone

sys.path.insert(0, "/app")
import settings  # noqa: E402
from sources import _iso  # noqa: E402

log = logging.getLogger("planetai.sc-direct")

MQTT_TOPICS = [("device/sck/#", 1)]

# A Smart Citizen Kit (`mqtt -host <node> -port 1883` in its USB shell) or a Making Sense Bali DIY node (v4 portal)
# can publish to this node's Mosquitto instead of mqtt.smartcitizen.me. Same topics, same bytes, so no device needs a
# second firmware, and the node can forward the message on to the platform unchanged (SC_FORWARD, below).
#   device/sck/<token>/readings       {"data":[{"recorded_at":"...","sensors":[{"id":237,"value":28.3}]}]}   DIY node
#   device/sck/<token>/readings/raw   {t:2026-10-07T04:10:00Z,55:28.3,56:71}                                 SCK 2.x
#   device/sck/<token>/meta           {"name":..,"site":..,"height_m":..,"indoor":true,"hardware":..}       DIY v4, retained
#   device/sck/<token>/hello | info   the device announcing itself; nothing in them is a reading
# Sensor ids are the platform's catalogue numbers. A kit generation changes them, so this names the ones our hardware
# publishes and logs any other once. The token is a credential (anyone holding it publishes as that device), so it
# never becomes an id, a name or a meta field: the sensor is `sck-` + the first 8 hex of sha256(token).
SC_WIRE_IDS = {
    # Making Sense Bali DIY node: the BME68X and HM-3301 catalogue rows its firmware publishes
    233: "pm1", 234: "pm25", 235: "pm10", 237: "temp", 238: "humidity", 239: "pressure", 240: "gas_resistance", 241: "bme_iaq",
    # SCK 2.1 / 2.2 / 2.3 urban board (fablabbcn/smartcitizen-kit-21, lib/Sensors/Sensors.h). Pressure is kPa there too.
    10: "battery_pct", 14: "light", 53: "noise", 55: "temp", 56: "humidity", 58: "pressure", 227: "pressure",
    112: "eco2", 113: "tvoc", 87: "pm25", 88: "pm10", 89: "pm1",
    182: "pm1", 183: "pm25", 185: "pm10", 193: "pm1", 194: "pm25", 196: "pm10", 158: "co2",
}
_SC_WIRE_UNKNOWN: set = set()


def sc_sensor_id(token: str) -> str:
    import hashlib
    return "sck-" + hashlib.sha256(token.encode()).hexdigest()[:8]


def smartcitizen_mqtt(topic: str, payload: bytes, meta: dict | None = None):
    """One message from a kit or DIY node on this node's broker -> (sensors, readings, info). Pure, tested offline.
    `meta` is the device's last retained meta message, if the caller kept one: it names the sensor and says whether
    it is indoors, and it travels with every readings message so the sensors upsert never flips a room to outdoor."""
    parts = topic.split("/")
    if len(parts) < 4 or parts[0] != "device" or parts[1] != "sck":
        return [], [], {}
    token, kind = parts[2], "/".join(parts[3:])
    sid = sc_sensor_id(token)
    meta = dict(meta or {})
    if kind == "meta":
        try:
            m = _json.loads(payload)
            meta = m if isinstance(m, dict) else {}
        except Exception:  # noqa: BLE001
            return [], [], {"kind": kind, "sensor_id": sid}
    sensor = {"sensor_id": sid, "source": "smartcitizen-direct", "name": (str(meta.get("name") or "").strip() or f"kit {sid[4:]}"),
              "lat": None, "lon": None, "indoor": bool(meta.get("indoor", False)), "local": True, "kind": "sensor",
              "scale": "community", "cadence": "PT1M",
              "meta": {k: meta[k] for k in ("site", "height_m", "hardware", "fw") if meta.get(k) not in (None, "")}}
    if kind == "meta":
        return [sensor], [], {"kind": kind, "sensor_id": sid, "meta": meta}
    if kind not in ("readings", "readings/raw"):
        return [], [], {"kind": kind, "sensor_id": sid}
    groups: list[tuple[datetime, dict]] = []      # (ts, {catalogue id: value})
    try:
        if kind == "readings":
            data = _json.loads(payload)["data"]
            for g in data if isinstance(data, list) else []:
                ts = _iso(g.get("recorded_at")) or datetime.now(timezone.utc)
                groups.append((ts, {int(x["id"]): float(x["value"]) for x in g.get("sensors") or []
                                    if isinstance(x, dict) and x.get("value") is not None}))
        else:
            items = [p.split(":", 1) for p in payload.decode("ascii", "ignore").strip().strip("{}").split(",") if ":" in p]
            kv = {k.strip(): v.strip() for k, v in items}
            ts = _iso(kv.pop("t", None)) or datetime.now(timezone.utc)
            groups.append((ts, {int(k): float(v) for k, v in kv.items() if k.isdigit()}))
    except Exception:  # noqa: BLE001  — a malformed message is ignored, never fatal to the thread
        return [], [], {"kind": kind, "sensor_id": sid}
    readings = []
    for ts, vals in groups:
        for cid, v in vals.items():
            metric = SC_WIRE_IDS.get(cid)
            if metric:
                readings.append((ts, sid, metric, v))
            elif cid and cid not in _SC_WIRE_UNKNOWN:
                _SC_WIRE_UNKNOWN.add(cid); log.info("sc-direct: catalogue id %s not in SC_WIRE_IDS (value %r) — add it if it matters", cid, v)
    return [sensor], readings, {"kind": kind, "sensor_id": sid}


# What /health reports as `direct`. `queued` is what still has to reach smartcitizen.me for the devices in SC_FORWARD.
state = {"devices": 0, "messages": 0, "last": None, "forwarded": 0, "forward_failed": 0, "queued": 0}
_meta: dict[str, dict] = {}            # token -> the device's last retained meta message, kept in memory only
_seen: set[str] = set()                # tokens heard since start; only their count is ever reported
# ponytail: in memory, bounded at two days of one device a minute; a restart during an internet outage drops it.
# A table if a forwarded minute ever matters that much. appendleft on failure evicts the newest, not the oldest.
_queue: "collections.deque[tuple[str, bytes, str]]" = collections.deque(maxlen=2880)
_forwarder: list[threading.Thread] = []
PLATFORM_HOST, PLATFORM_PORT = "mqtt.smartcitizen.me", 8883


def SC_FORWARD():
    return {t.strip() for t in settings.get("SC_FORWARD", "").split(",") if t.strip()}


def on_mqtt(topic: str, payload: bytes):
    """One message on this node's broker -> (sensors, readings) to store, or None when it is not this pack's."""
    if not topic.startswith("device/sck/"):
        return None
    token = topic.split("/")[2]
    sensors, readings, info = smartcitizen_mqtt(topic, payload, _meta.get(token))
    if info.get("kind") == "meta" and "meta" in info:
        _meta[token] = info["meta"]
    if sensors or readings:
        _seen.add(token)
        state.update({"messages": state["messages"] + 1, "last": datetime.now(timezone.utc).isoformat(), "devices": len(_seen)})
    if info.get("kind") != "meta" and token in SC_FORWARD():
        _queue.append((topic, bytes(payload), token)); state["queued"] = len(_queue)
        if not _forwarder:            # started on the first message to forward, never at import
            _forwarder.append(threading.Thread(target=_forward, daemon=True, name="sc-forward"))
            _forwarder[0].start()
    return sensors, readings


def status() -> dict:
    return {"direct": state} if os.getenv("MQTT_HOST", "").strip() else {}


def _forward() -> None:
    """Pass each queued message to smartcitizen.me exactly as the device sent it: same topic, same bytes, the
    device's token as the MQTT identity (what both firmwares do), QoS 1 as the platform asks, and the platform's
    certificate actually checked, which the DIY firmware cannot afford to do. One connection per message: at a
    message a minute per device that is nothing, and it keeps the per-token identity simple."""
    import ssl
    import paho.mqtt.publish as publish
    while True:
        if not _queue:
            time.sleep(1); continue
        topic, payload, token = _queue.popleft(); state["queued"] = len(_queue)
        try:
            publish.single(topic, payload, qos=1, hostname=PLATFORM_HOST, port=PLATFORM_PORT, client_id=token,
                           auth={"username": token, "password": ""}, tls={"cert_reqs": ssl.CERT_REQUIRED}, keepalive=30)
            state["forwarded"] += 1
        except Exception as e:  # noqa: BLE001
            _queue.appendleft((topic, payload, token)); state["queued"] = len(_queue)
            state["forward_failed"] += 1
            log.warning("sc-direct: forward to %s failed (%s: %s) — %d queued, retrying in 30s", PLATFORM_HOST, type(e).__name__, e, len(_queue))
            time.sleep(30)
