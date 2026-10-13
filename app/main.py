"""planetai-node. One process:
  poll sources → postgres   (every POLL_SECONDS)
  run rules.yml (SQL) → telegram/log   (every 60s, cooldown enforced in SQL against the alerts table)
  write one report every REPORT_EVERY hours from REPORT_ANCHOR, in local time; the `reports` row is the lock
  push hourly aggregates to PARENT_API_URL if set   (every hour)
  answer HTTP: /health /sensors /readings /stats /observations /alerts /aggregates /cells /rho /packs
              /report/latest · /report/bundle (read-only token) · POST /report/now (admin token)
              POST /aggregates (parent side, token) · POST /actions (ρ) · POST /readings (downstream contributors, admin token)
"""
from __future__ import annotations

import collections
import json
from zoneinfo import ZoneInfo
import logging
import os
import re
import secrets
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx
import psycopg
import yaml
from fastapi import FastAPI, Header, HTTPException, Query, Request
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

import bootstrap
import agent
import actions as _act
import events_pg
import ground
import index
import issues.api
from issues import geometry as _geo
import packs
import registry
import report
import settings
import sources

log = logging.getLogger("planetai")
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)s %(message)s")
# httpx logs every request URL at INFO. Telegram carries the bot token IN THE URL, so that would put a live
# credential in the logs, in `docker compose logs`, and in every screenshot anyone pastes for support. Off.
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

DB = os.environ["DATABASE_URL"]
NODE = os.getenv("NODE_NAME", "node")
POLL = int(os.getenv("POLL_SECONDS", "300"))
def TG():
    """Token and chat ids, read at send time so the GUI can change them without a restart."""
    return settings.get("TELEGRAM_BOT_TOKEN", "").strip(), [c for c in settings.get("TELEGRAM_CHAT_IDS", "").replace(" ", "").split(",") if c]
def LOCALE():
    return settings.get("ALERT_LOCALE", "en")
def PARENT():
    return settings.get("PARENT_API_URL", "").strip()
MQTT_HOST = os.getenv("MQTT_HOST", "").strip()                 # set by `planetai meshtastic`; empty = no MQTT thread
MQTT_USER, MQTT_PASS = os.getenv("MQTT_USER", ""), os.getenv("MQTT_PASS", "")
def MESH_INDOOR():
    return {x.strip() for x in settings.get("MESH_INDOOR_NODES", "").split(",") if x.strip()}
def MESH_ALERTS():
    return settings.get("MESH_ALERTS", "0") == "1"
def MESH_GATEWAY_NUM():
    return int(settings.get("MESH_GATEWAY_NODE_NUM", "0") or 0)
def SC_FORWARD():
    return {t.strip() for t in settings.get("SC_FORWARD", "").split(",") if t.strip()}
def AGG_TOKEN():
    return settings.get("AGGREGATE_TOKEN", "").strip()
def SHARE_LEVEL():
    return (settings.get("SHARE_LEVEL", "off") or "off").strip().lower()
def ACT_TOKEN():
    return settings.get("ACT_TOKEN", "").strip()
def PARENT_TOKEN():
    return settings.get("PARENT_TOKEN", "").strip()
def HA_DISCOVERY():
    return settings.get("HA_DISCOVERY", "0") == "1" and bool(os.getenv("MQTT_HOST", "").strip())
_ha_announced: set = set()
RETICULUM_URL = os.getenv("RETICULUM_URL", "").strip()       # the reticulum bridge, e.g. http://reticulum:4243
mesh_state = {"root_topic": None, "gateway": None, "packets": 0, "last": None, "seen": 0, "sent": 0}
# Text messages heard on the mesh: appended to one JSON-lines file (out/ is the one writable mount, so it survives a
# rebuild), counted as seen (from other nodes) or sent (from this node's own gateway radio). The dashboard shows the
# two counts and nothing else; the text itself goes to the Telegram bot (MESH_TG_FORWARD) and the file.
MESH_LOG = Path(os.getenv("MESH_LOG", "/app/out/mesh-messages.jsonl"))
_mesh_ids: collections.deque = collections.deque(maxlen=500)     # packet ids already logged: one packet arrives once per gateway
_mesh_fwd: collections.deque = collections.deque(maxlen=20)      # monotonic times of recent forwards, to cap the rate
_mesh_lock = threading.Lock()


def MESH_TG_FORWARD():
    return settings.get("MESH_TG_FORWARD", "1") == "1"


def mesh_counts_load() -> None:
    """Counts survive a restart because the file does."""
    try:
        with MESH_LOG.open(encoding="utf-8") as f:
            for line in f:
                try:
                    mesh_state["sent" if json.loads(line).get("dir") == "sent" else "seen"] += 1
                except ValueError:
                    pass
    except OSError:
        pass


def mesh_text(t: dict, gateway: str | None) -> None:
    """Log one text message, count it, and pass a received one to Telegram. Our own radio's messages are
    logged as sent and never forwarded (no loop, no echo of what the household typed)."""
    mid = t.get("id")
    with _mesh_lock:
        if mid is not None:
            if mid in _mesh_ids:
                return
            _mesh_ids.append(mid)
        direction = "sent" if gateway and t.get("from") == gateway else "seen"
        mesh_state[direction] += 1
        try:
            MESH_LOG.parent.mkdir(parents=True, exist_ok=True)
            with MESH_LOG.open("a", encoding="utf-8") as f:
                f.write(json.dumps({**t, "dir": direction}, ensure_ascii=False) + "\n")
        except OSError as e:
            log.warning("mesh message log not writable: %s", type(e).__name__)
        forward = direction == "seen" and MESH_TG_FORWARD() and t.get("text")
        if forward:
            now = time.monotonic()
            if len(_mesh_fwd) == _mesh_fwd.maxlen and now - _mesh_fwd[0] < 60:
                forward = False                       # more than 20 a minute is a flood, not a conversation: logged, not forwarded
            else:
                _mesh_fwd.append(now)
    if forward:
        threading.Thread(target=telegram, args=(f"📡 {t.get('from')}: {t['text']}",), daemon=True).start()

# Kits and DIY nodes publishing Smart Citizen's own wire format to this node's broker (sources.smartcitizen_mqtt).
# `queued` is what still has to reach smartcitizen.me for the devices in SC_FORWARD.
sc_state = {"devices": 0, "messages": 0, "last": None, "forwarded": 0, "forward_failed": 0, "queued": 0}
sc_meta: dict[str, dict] = {}          # token -> the device's last retained meta message, kept in memory only
sc_seen: set[str] = set()              # tokens heard since start; only their count is ever reported
# ponytail: in memory, bounded at two days of one device a minute; a restart during an internet outage drops it.
# A table if a forwarded minute ever matters that much. appendleft on failure evicts the newest, not the oldest.
sc_queue: "collections.deque[tuple[str, bytes, str]]" = collections.deque(maxlen=2880)
SC_PLATFORM_HOST, SC_PLATFORM_PORT = "mqtt.smartcitizen.me", 8883
# What the Reticulum bridge says about itself, refreshed on its own thread. /health is called every
# twenty seconds by every screen in the house, so it must never make an outbound request of its own:
# a bridge that is down would turn the node's own health check into a timeout.
reticulum_state = {"ok": False, "address": None, "destinations": 0, "announce_s": None,
                   "announcing": False, "peers": [], "last": None}
STARTED = time.time()
state = {"polls": 0, "last_poll": None, "last_error": None, "ingested": 0}


NODE_TZ = os.getenv("NODE_TZ", "").strip() or "UTC"


def db():
    # Rules and cells use `current_setting('TimeZone')` to find local midnight and local hours. Postgres defaults
    # to UTC, which put day boundaries and "evening" eight hours out in Bali. Set the session timezone from
    # NODE_TZ, in the connection options so it costs no extra round trip.
    # also hand the node's coordinates to SQL as custom settings, so rules can rank references by distance
    lat, lon = os.getenv("NODE_LAT", "0") or "0", os.getenv("NODE_LON", "0") or "0"
    return psycopg.connect(DB, row_factory=dict_row, autocommit=True,
                           options=f"-c timezone={NODE_TZ} -c planetai.lat={lat} -c planetai.lon={lon}")


# ---------------------------------------------------------------- ingest
def poll_once(hc: httpx.Client) -> None:
    errors: list[str] = []
    with db() as con:
        for name, fn in sources.enabled(hc):
            try:
                sensors, readings = fn()
            except Exception as e:  # noqa: BLE001
                errors.append(f"{name}: {str(e).splitlines()[0]}")
                log.warning("source %s failed: %s", name, e)
                continue
            lat_env, lon_env = os.getenv("NODE_LAT"), os.getenv("NODE_LON")
            sources.stamp_local(sensors, float(lat_env) if lat_env else None, float(lon_env) if lon_env else None,
                                 float(settings.get("LOCAL_RADIUS_M") or 500))
            with con.cursor() as cur:
                for s in sensors:
                    cur.execute(
                        """INSERT INTO sensors (sensor_id, source, name, lat, lon, indoor, local, kind, scale, cadence, meta)
                           VALUES (%(sensor_id)s, %(source)s, %(name)s, %(lat)s, %(lon)s, %(indoor)s, %(local)s,
                                   %(kind)s, %(scale)s, %(cadence)s, %(meta)s)
                           ON CONFLICT (sensor_id) DO UPDATE SET name=EXCLUDED.name, lat=EXCLUDED.lat, lon=EXCLUDED.lon,
                             indoor=EXCLUDED.indoor, local=EXCLUDED.local, kind=EXCLUDED.kind, scale=EXCLUDED.scale,
                             cadence=EXCLUDED.cadence, meta=EXCLUDED.meta""",
                        {"kind": "sensor", "scale": os.getenv("NODE_SCALE", "community"), "cadence": None,
                         **s, "meta": Jsonb(s.get("meta") or {})},
                    )
                if readings:
                    cur.executemany(
                        "INSERT INTO readings (ts, sensor_id, metric, value) VALUES (%s,%s,%s,%s) ON CONFLICT DO NOTHING",
                        readings,
                    )
                    state["ingested"] += cur.rowcount if cur.rowcount and cur.rowcount > 0 else 0
            log.info("%s: %d sensors, %d readings", name, len(sensors), len(readings))
            ha_publish(sensors, readings)
    state["polls"] += 1
    state["last_poll"] = datetime.now(timezone.utc).isoformat()
    state["last_error"] = " | ".join(errors) if errors else None   # clears when every source succeeds


# ---------------------------------------------------------------- MQTT ingest (Meshtastic gateway, DIY pods)
def _store(sensors, readings) -> None:
    lat_env, lon_env = os.getenv("NODE_LAT"), os.getenv("NODE_LON")
    sources.stamp_local(sensors, float(lat_env) if lat_env else None, float(lon_env) if lon_env else None,
                         float(settings.get("LOCAL_RADIUS_M") or 500))
    with db() as con, con.cursor() as cur:
        for s in sensors:
            cur.execute("""INSERT INTO sensors (sensor_id, source, name, lat, lon, indoor, local, kind, scale, cadence, meta)
                           VALUES (%(sensor_id)s,%(source)s,%(name)s,%(lat)s,%(lon)s,%(indoor)s,%(local)s,%(kind)s,%(scale)s,%(cadence)s,%(meta)s)
                           ON CONFLICT (sensor_id) DO UPDATE SET
                             name = COALESCE(EXCLUDED.name, sensors.name),
                             lat = COALESCE(EXCLUDED.lat, sensors.lat), lon = COALESCE(EXCLUDED.lon, sensors.lon),
                             indoor = EXCLUDED.indoor, local = EXCLUDED.local, meta = sensors.meta || EXCLUDED.meta""",
                        {**s, "meta": Jsonb(s.get("meta") or {})})
        if readings:
            cur.executemany("INSERT INTO readings (ts, sensor_id, metric, value) VALUES (%s,%s,%s,%s) ON CONFLICT DO NOTHING", readings)
            state["ingested"] += max(cur.rowcount or 0, 0)      # rowcount, not len: duplicates are dropped
    ha_publish(sensors, readings)


def mqtt_thread() -> None:
    """Subscribe to everything under msh/ (Meshtastic) and planetai/ (DIY pods) and store what parses."""
    import paho.mqtt.client as mqtt

    def on_connect(c, u, flags, rc, props=None):
        c.subscribe([("msh/#", 0), ("planetai/sensors/#", 0), ("device/sck/#", 1)])
        log.info("mqtt: connected to %s, subscribed msh/#, planetai/sensors/# and device/sck/#", MQTT_HOST)

    def on_message(c, u, msg):
        try:
            if msg.topic.startswith("msh/"):
                sensors, readings, info = sources.meshtastic_message(msg.topic, msg.payload, MESH_INDOOR())
                if info.get("root_topic"):
                    mesh_state.update({"root_topic": info["root_topic"], "gateway": info.get("gateway"),
                                       "packets": mesh_state["packets"] + 1, "last": datetime.now(timezone.utc).isoformat()})
                if info.get("text"):
                    mesh_text(info["text"], info.get("gateway"))
                if sensors or readings:
                    _store(sensors, readings)
            elif msg.topic.startswith("planetai/sensors/"):
                # planetai/sensors/<id>/<metric>  {"value": 12.3, "ts": "...", "indoor": false}
                _, _, sid, metric = msg.topic.split("/", 3)
                body = json.loads(msg.payload)
                ts = datetime.fromisoformat(str(body["ts"]).replace("Z", "+00:00")) if body.get("ts") else datetime.now(timezone.utc)
                _store([{"sensor_id": f"pod-{sid}", "source": "mqtt", "name": f"pod {sid}", "lat": None, "lon": None,
                         "indoor": bool(body.get("indoor", False)), "local": True, "kind": "sensor", "scale": "community",
                         "cadence": None, "meta": {"topic": msg.topic}}],
                       [(ts, f"pod-{sid}", metric, float(body["value"]))])
            elif msg.topic.startswith("device/sck/"):
                # a Smart Citizen Kit or a DIY node pointed at this broker: the platform's own topics and bytes
                token = msg.topic.split("/")[2]
                sensors, readings, info = sources.smartcitizen_mqtt(msg.topic, msg.payload, sc_meta.get(token))
                if info.get("kind") == "meta" and "meta" in info:
                    sc_meta[token] = info["meta"]
                if sensors or readings:
                    _store(sensors, readings)
                    sc_seen.add(token)
                    sc_state.update({"messages": sc_state["messages"] + 1, "last": datetime.now(timezone.utc).isoformat(), "devices": len(sc_seen)})
                if info.get("kind") != "meta" and token in SC_FORWARD():
                    sc_queue.append((msg.topic, bytes(msg.payload), token)); sc_state["queued"] = len(sc_queue)
        except Exception as e:  # noqa: BLE001
            log.debug("mqtt message on %s ignored: %s", msg.topic, e)

    while True:
        try:
            c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"planetai-{NODE}")
            if MQTT_USER:
                c.username_pw_set(MQTT_USER, MQTT_PASS)
            c.on_connect, c.on_message = on_connect, on_message
            c.connect(MQTT_HOST, 1883, keepalive=60)
            c.loop_forever(retry_first_connection=True)
        except Exception as e:  # noqa: BLE001
            log.warning("mqtt: %s — retrying in 15s", e)
            time.sleep(15)


def sc_forward_thread() -> None:
    """Pass each queued message to smartcitizen.me exactly as the device sent it: same topic, same bytes, the
    device's token as the MQTT identity (what both firmwares do), QoS 1 as the platform asks, and the platform's
    certificate actually checked, which the DIY firmware cannot afford to do. One connection per message: at a
    message a minute per device that is nothing, and it keeps the per-token identity simple."""
    import ssl
    import paho.mqtt.publish as publish
    while True:
        if not sc_queue:
            time.sleep(1); continue
        topic, payload, token = sc_queue.popleft(); sc_state["queued"] = len(sc_queue)
        try:
            publish.single(topic, payload, qos=1, hostname=SC_PLATFORM_HOST, port=SC_PLATFORM_PORT, client_id=token,
                           auth={"username": token, "password": ""}, tls={"cert_reqs": ssl.CERT_REQUIRED}, keepalive=30)
            sc_state["forwarded"] += 1
        except Exception as e:  # noqa: BLE001
            sc_queue.appendleft((topic, payload, token)); sc_state["queued"] = len(sc_queue)
            sc_state["forward_failed"] += 1
            log.warning("sc-direct: forward to %s failed (%s: %s) — %d queued, retrying in 30s", SC_PLATFORM_HOST, type(e).__name__, e, len(sc_queue))
            time.sleep(30)


def mesh_send(text: str) -> None:
    """Send `text` over the LoRa mesh via the gateway's MQTT downlink. Needs a root topic learned from an uplink."""
    if not (MQTT_HOST and MESH_ALERTS() and mesh_state["root_topic"]):
        return
    try:
        import paho.mqtt.publish as publish
        topic, payload = sources.meshtastic_downlink(mesh_state["root_topic"], MESH_GATEWAY_NUM(), text)
        publish.single(topic, payload, hostname=MQTT_HOST, auth={"username": MQTT_USER, "password": MQTT_PASS} if MQTT_USER else None)
        log.info("mesh -> sent %d bytes on %s", len(payload), topic)
    except Exception as e:  # noqa: BLE001
        log.warning("mesh send failed: %s", type(e).__name__)


# ---------------------------------------------------------------- Home Assistant (MQTT discovery)
# HA's MQTT integration watches homeassistant/<component>/<id>/config. Publish one config per sensor metric and
# HA creates the entity, grouped under a device per physical sensor. Then publish states. Retained, so HA sees
# them on restart. We publish; HA automates. The node never addresses a device.
HA_UNITS = {"pm25": ("µg/m³", "pm25"), "pm10": ("µg/m³", "pm10"), "pm1": ("µg/m³", "pm1"), "pm25_model": ("µg/m³", "pm25"),
            "temp": ("°C", "temperature"), "temp_model": ("°C", "temperature"), "humidity": ("%", "humidity"),
            "humidity_model": ("%", "humidity"), "pressure": ("kPa", "atmospheric_pressure"), "co2": ("ppm", "carbon_dioxide"),
            "battery_pct": ("%", "battery"), "battery_v": ("V", "voltage"), "aqi": (None, "aqi"),
            "wind_speed": ("km/h", "wind_speed"), "precipitation": ("mm", "precipitation"), "uv_index": (None, None)}


def ha_publish(sensors: list[dict], readings: list[tuple]) -> None:
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
                       "device": {"identifiers": [f"planetai_{NODE}_{sid}"], "name": s.get("name") or sid,
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


def ha_alert(level: str, text: str, alert_id: int | None) -> None:
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


# ---------------------------------------------------------------- rules → alerts
def _local_now() -> datetime:
    """The node's own clock. Everything a person is told about time uses this, never UTC: a 'good morning' that arrives
    at one in the afternoon is the bug this exists to prevent."""
    try:
        return datetime.now(ZoneInfo(NODE_TZ))
    except Exception:  # noqa: BLE001
        return datetime.now(timezone.utc)


def _hours(key: str, default: str) -> list[int]:
    return [int(x) for x in (settings.get(key, default) or default).replace(" ", "").split(",") if x.strip().isdigit()]


def _quiet(level: str) -> bool:
    """During quiet hours only act-level alerts go out; the rest wait for the next briefing. 22:00-06:00 by default."""
    if settings.get("QUIET_HOURS", "1") != "1" or level == "act":
        return False
    h = _local_now().hour
    a, b = _hours("QUIET_FROM", "22")[0], _hours("QUIET_TO", "6")[0]
    return (a <= h or h < b) if a > b else (a <= h < b)


def act_hint(alert_id) -> str:
    """How this household closes the loop on alert N. `/act N` is a reply to the Telegram bot, which exists only when the
    agent container runs (planetai agent local); on every other node the words are `planetai act N`. A tester who
    replied /act to a bot that was not there heard nothing back (BETA review, 8.2)."""
    bot = "agent" in os.getenv("COMPOSE_PROFILES", "")
    return f"/act {alert_id}" if bot else f"planetai act {alert_id}"


def _report_every() -> int:
    """Hours between reports. A value the scheduler cannot honour (one that does not divide 24, so the rhythm walks
    round the clock) falls back to six rather than making the node quiet: settings.set refuses those, but .env is
    edited by hand."""
    v = str(settings.num("REPORT_EVERY", 6))
    return int(v) if v in settings.CHOICES["REPORT_EVERY"] else 6


def _report_hours() -> list[int]:
    return report.due_hours(_report_every(), settings.num("REPORT_ANCHOR", 6))


def _held_hours(cur, due, every: int) -> int:
    """How many hours of held reports this one has to fold in. The window a household last actually read ended at
    the newest sent report; if none was ever sent, at the start of the oldest held one."""
    # coalesce(due_local, ts): a report written on request has no due hour, but it did go out and it did cover a
    # window, so it ends the held stretch. Without this a forced report at two in the morning left the night to be
    # folded into the six o'clock one as well, and the household read it twice.
    cur.execute("""SELECT coalesce(max(coalesce(due_local, ts)) FILTER (WHERE sent),
                            min(coalesce(due_local, ts)) FILTER (WHERE held_quiet) - make_interval(hours => %(every)s)) AS since
                     FROM reports""", {"every": every})
    return report.held_hours((cur.fetchone() or {}).get("since"), due, every)


def run_report(cur) -> None:
    """The node's one scheduled message. Called from run_rules, before the rules, every 60 seconds.

    The `reports` row is the lock, not a timer in memory: the node writes the row for this local hour and will not
    write a second one for the same hour, so a container that restarts inside the twenty-minute window does not
    send the report twice. That is what the old briefings got wrong in the other direction — they asked `alerts`,
    where every rule also writes.

    A report due inside quiet hours is written and stored and not sent. The next one covers both windows, so the
    night is in the morning's report rather than lost."""
    now = _local_now()
    if now.hour not in _report_hours() or now.minute >= 20:
        return
    due = now.replace(minute=0, second=0, microsecond=0)
    cur.execute("SELECT 1 FROM reports WHERE due_local = %s LIMIT 1", (due,))
    if cur.fetchone():
        return

    every = _report_every()
    held = _held_hours(cur, due, every)
    b = report.bundle(cur, every, held_hours=held)
    text = report.sheet(b, LOCALE())
    quiet = _quiet("info")
    cur.execute("""INSERT INTO reports (due_local, window_hours, depth, rung, text, sheet, sent, held_quiet, cells)
                   VALUES (%s, %s, 'sheet', 'node', %s, %s, %s, %s, %s) RETURNING id""",
                (due, every + held, text, text, not quiet, quiet, Jsonb(b.get("cells") or [])))
    rid = cur.fetchone()["id"]
    if quiet:
        log.info("report %d written and held for quiet hours: %d hours will be folded into the next one", rid, every + held)
        return
    notify("info", text)          # Telegram and Home Assistant. The mesh and Reticulum carry act alerts only.
    ha_alert("info", text, None)
    log.info("report %d sent: %d hours, %d words", rid, every + held, len(text.split()))


def refresh_usual() -> None:
    """usual_by_hour is materialized (init.sql): rebuild it hourly, in this connection's NODE_TZ, so a rule's
    "usual for this hour" is the household's hour. A plain REFRESH takes an ACCESS EXCLUSIVE lock, so a rule reading
    usual_by_hour waits for it (well under a second on a node). REFRESH CONCURRENTLY would need a unique index and
    fails on a never-populated view."""
    with db() as con, con.cursor() as cur:
        cur.execute("REFRESH MATERIALIZED VIEW usual_by_hour")


def run_rules() -> None:
    rules = packs.load_rules()
    mode = settings.get("ALERT_ENGINE", "rules") or "rules"
    if mode not in ("rules", "shadow", "events"):
        mode = "rules"                    # a typo behaves as rules: the household keeps its alerts
    # In events mode the engine speaks for the packs it has kinded rules for (heat, air-quality): their old rules
    # still record an alerts row (the dashboard, rho and Home Assistant read those) but no longer send. Every other
    # rule, core sensor_silent included, sends as before.
    replaced = {r["id"].split("/", 1)[0] for r in rules if r.get("kind")} if mode == "events" else set()
    cands = []
    with db() as con, con.cursor() as cur:
        try:
            run_report(cur)
        except Exception as e:  # noqa: BLE001
            log.warning("report failed: %s", e)
        for rule in rules:
            if rule.get("kind") and mode == "rules":
                continue                  # kinded rules belong to the event engine (docs/SPEC_alerts.md)
            try:
                rows = index.run_ro(cur, rule["sql"])      # as planetai_ro: a rule can read everything but settings, and write nothing
            except Exception as e:  # noqa: BLE001
                log.warning("rule %s failed: %s", rule.get("id"), e)
                continue
            if rule.get("kind"):
                # No alerts row, on purpose: an act-level row is an open ask on the dashboard and a row in rho's
                # denominator, and shadow must change neither. Linking them (alerts.event_id) is Plan 2's.
                cands += events_pg.candidates(rule, rows)
                continue                  # never through the old cooldown-and-send path
            for row in rows:
                sid = str(row.get("sensor_id", "node"))
                cur.execute(
                    "SELECT 1 FROM alerts WHERE rule_id=%s AND sensor_id=%s AND ts > now() - make_interval(mins => %s) LIMIT 1",
                    (rule["id"], sid, int(rule.get("cooldown_minutes", 60))),
                )
                if cur.fetchone():
                    continue
                msg = rule["message"]
                tmpl = msg.get(LOCALE()) or msg.get("en") if isinstance(msg, dict) else str(msg)
                # {line} is the one placeholder the row never carries: it is the rule's own line,
                # named by watch.over and printed bare (35, not 35.0), so an alert can say whose
                # line it is (docs/SPEC_language.md rule 10) without a second copy of the number.
                watch_over = (rule.get("watch") or {}).get("over")
                line_f = {"line": f"{float(watch_over):g}"} \
                    if isinstance(watch_over, (int, float)) else {}
                try:
                    text = tmpl.format(**line_f, **{k: ("—" if v is None else v) for k, v in row.items()})
                except (KeyError, ValueError, TypeError):
                    text = tmpl
                level = rule.get("level", "info")
                cur.execute("INSERT INTO alerts (rule_id, sensor_id, level, text) VALUES (%s,%s,%s,%s) RETURNING id", (rule["id"], sid, level, text))
                alert_id = cur.fetchone()["id"]
                # what interrupts a person: act always; warn if ALERT_LEVEL allows; info only in a briefing (it is
                # recorded either way, and appears on the dashboard). Quiet hours hold everything but act.
                floor = {"act": 2, "warn": 1, "info": 0}
                send = (rule["id"].split("/", 1)[0] not in replaced
                        and floor.get(level, 0) >= floor.get(settings.get("ALERT_LEVEL", "act"), floor["act"]) and not _quiet(level))
                if send:
                    # No id, and nothing asking to be told. The node watches what happens next (v0.39) instead of
                    # asking; a number a household is expected to quote back was a chore, and 15 of node #1's 37
                    # act alerts got an answer, nine of them in two dashboard batch-clicks a day later.
                    notify(level, text)
                ha_alert(level, text, alert_id)
        if mode in ("shadow", "events"):
            try:
                decided = events_pg.run(cur, cands, mode, _local_now())
            except Exception as e:  # noqa: BLE001
                log.warning("event engine failed: %s", e)
                decided = []
            if mode == "events":
                # after the engine's transaction has committed: a message is never sent for a step that rolled back
                for m, text in decided:
                    if m.send and text:
                        # The buttons ride only when the bot has announced itself (TELEGRAM_BUTTONS=1,
                        # set by agent_loop on startup): a node without the agent container sends the
                        # same message bare (SPEC_alerts §7).
                        kb = _event_keyboard(m.event.id, settings.get("ALERT_LOCALE", "en") or "en") \
                            if m.event.id and settings.num("TELEGRAM_BUTTONS", 0) else None
                        notify(m.event.level, text, keyboard=kb)


def notify(level: str, text: str, keyboard: list | None = None) -> None:
    icon = {"info": "ℹ️", "warn": "⚠️", "act": "🔴"}.get(level, "")
    log.info("ALERT [%s] %s", level, text)
    if level == "act":
        mesh_send(text.split("\n")[0])            # the mesh gets the first line only: LoRa frames are small
        if RETICULUM_URL:
            try:
                httpx.post(f"{RETICULUM_URL}/send", json={"text": text}, timeout=10)
            except Exception as e:  # noqa: BLE001
                log.warning("reticulum send failed: %s", type(e).__name__)
    telegram(f"{icon} {text}".strip(), keyboard)


def telegram(text: str, keyboard: list | None = None) -> None:
    """Send one message to every configured chat. Quiet when no bot is set up."""
    tok, chats = TG()
    if not tok or not chats:
        return
    for chat in chats:
        try:
            body = {"chat_id": chat, "text": text}
            if keyboard:
                body["reply_markup"] = {"inline_keyboard": keyboard}
            httpx.post(f"https://api.telegram.org/bot{tok}/sendMessage",
                       json=body, timeout=15).raise_for_status()
            log.info("telegram -> %s ok", chat)
        except Exception as e:  # noqa: BLE001
            # never interpolate the exception's URL: httpx puts the token in it
            log.warning("telegram -> %s failed: %s", chat, type(e).__name__)


def _event_keyboard(event_id: int, locale: str) -> list:
    """The three buttons under an event's message (SPEC_alerts §7). callback_data is the contract the bot in the
    agent container parses: ev:<event_id>:<stage>. Labels are the wire's own (actions.BUTTONS), so the page, the
    phone and the bot all say the same three words. Sent only when the bot has announced itself
    (TELEGRAM_BUTTONS=1): a button nobody answers is a broken promise under the message."""
    b = _act.BUTTONS.get(locale) or _act.BUTTONS["en"]
    return [[{"text": b["done"], "callback_data": f"ev:{event_id}:acted"},
             {"text": b["not_now"], "callback_data": f"ev:{event_id}:acknowledged"},
             {"text": b["doesnt_fit"], "callback_data": f"ev:{event_id}:dismissed"}]]


# ---------------------------------------------------------------- hourly push (child → parent)
def push_aggregates() -> None:
    if not PARENT():          # the function, not the setting: a bare PARENT is always truthy
        return
    with db() as con, con.cursor() as cur:
        cur.execute("SELECT bucket, sensor_id, metric, mean, min, max, n FROM readings_1h WHERE bucket > now() - interval '2 hours'")
        rows = [{**r, "bucket": r["bucket"].isoformat()} for r in cur.fetchall()]
    try:
        httpx.post(f"{PARENT()}/aggregates", json={"schema": AGGREGATES_V0, "node": NODE, "rows": rows, "scale": os.getenv("NODE_SCALE", "community")},
                   headers={"Authorization": f"Bearer {PARENT_TOKEN()}"} if PARENT_TOKEN() else {},
                   timeout=30).raise_for_status()
        log.info("pushed %d hourly rows to parent", len(rows))
    except Exception as e:  # noqa: BLE001
        log.warning("push to parent failed: %s", e)


# ---------------------------------------------------------------- hourly push (child -> parent): rho
def push_events() -> None:
    """Send the parent one row per alert this node raised, as timestamps and nothing else.

    ARCHITECTURE.md calls rho "the brick nobody else has", and until now it stopped at the address:
    push_aggregates() sends readings only, so a City node's Governance cell counted the alerts it raised
    itself while ten children below it measured rho every day.

    WHAT IS NOT SENT IS THE POINT. No alert text, no actor, no sensor id, no note. "Shut the bedroom windows"
    names a room, says somebody was home to be told, and describes a house. The timestamps carry everything
    rho needs and none of the facts a household would mind travelling.

    No ratio either. The child sends events, the parent computes rho: a mean of ten ratios is not the ratio of
    the pooled counts, the parent cannot check a number it did not derive, and a change to the definition of
    rho then reaches every historical child at once instead of needing a re-push.

    The window is 36 hours rather than 2. An alert raised yesterday can be acknowledged today, so the row has
    to be re-sent when its timestamps change; the parent's PRIMARY KEY (child, alert_id) makes that an update.
    """
    if not PARENT():
        return
    with db() as con, con.cursor() as cur:
        cur.execute("""SELECT a.id, a.rule_id, a.level, a.ts,
                              min(f.ts) FILTER (WHERE f.stage = 'acknowledged') AS responded_at,
                              min(f.ts) FILTER (WHERE f.stage = 'acted')        AS acted_at,
                              min(f.ts) FILTER (WHERE f.stage = 'measured')     AS measured_at
                       FROM alerts a LEFT JOIN actions f ON f.alert_id = a.id
                       WHERE a.ts > now() - interval '36 hours'
                       GROUP BY a.id, a.rule_id, a.level, a.ts""")
        rows = [{"alert_id": str(r["id"]), "rule": r["rule_id"], "level": r["level"],
                 # rule ids are namespaced <pack>/<id>, so the pack IS the domain tag and there is nothing
                 # to invent: a parent can weigh rho for air apart from rho for heat by reading it.
                 "kind": (r["rule_id"] or "").split("/")[0] or None,
                 "raised_at": r["ts"].isoformat(),
                 **{k: (r[k].isoformat() if r[k] else None)
                    for k in ("responded_at", "acted_at", "measured_at")}}
                for r in cur.fetchall()]
    if not rows:
        return
    try:
        httpx.post(f"{PARENT()}/events", json={"schema": EVENTS_V0, "node": NODE, "rows": rows, "scale": os.getenv("NODE_SCALE", "community")},
                   headers={"Authorization": f"Bearer {PARENT_TOKEN()}"} if PARENT_TOKEN() else {},
                   timeout=30).raise_for_status()
        log.info("pushed %d alert events to parent", len(rows))
    except Exception as e:  # noqa: BLE001
        log.warning("event push to parent failed: %s", e)


# ---------------------------------------------------------------- is there a newer release
# The file tools/ship.sh publishes beside the signed tarball: one line, the version a tester downloading now gets.
# It is not signed, and it need not be: the most a forged one can do is say a version is out, and `planetai update`
# still refuses a tarball the release key did not sign.
RELEASE_URL = "https://planetai.fab.city/node0/get/VERSION"
RELEASE_EVERY = 24 * 3600
RELEASE_WORDS = {
    "en": "PLANETAI {latest} is out; this node runs {here}. On the node: planetai update (it backs up first). "
          "What changed: https://planetai.fab.city/docs/changelog/",
    "es": "Ya está PLANETAI {latest}; este nodo tiene {here}. En el nodo: planetai update (antes hace una copia). "
          "Qué cambia: https://planetai.fab.city/docs/changelog/",
    "id": "PLANETAI {latest} sudah tersedia; node ini menjalankan {here}. Di node: planetai update (ia membuat cadangan "
          "dulu). Apa yang berubah: https://planetai.fab.city/docs/changelog/",
}


# The release a version string is at. It lives in requires.py because the packs loader and the CLI need it too,
# and nothing may import this module to get it (a second import starts a second MQTT client).
from requires import release_of  # noqa: E402


def check_release() -> None:
    """Once a day, ask which version is current; say so in /health, and once per version on Telegram, when it is
    newer than this node. Runs hourly so a message held back by quiet hours goes out the next morning, but asks
    the site only once in RELEASE_EVERY. UPDATE_CHECK=off asks nothing and forgets what it knew."""
    if settings.get("UPDATE_CHECK", "on") == "off":
        state.pop("release", None)
        return
    known = state.get("release") or {}
    if time.time() - known.get("asked", 0) >= RELEASE_EVERY:
        # Not raised: a node with no route out is a normal node, and a loop's error lands in /health's `errors`,
        # which the agent's health check reads as a broken source. Kept here instead, and asked again in an hour.
        try:
            r = hc.get(RELEASE_URL, timeout=15)
            r.raise_for_status()
            latest = r.text.strip()
            # A site that answers 200 with a page instead of the file must not become "v<html>" in a header.
            if not re.fullmatch(r"v\d+\.\d+(?:\.\d+)?", latest):
                raise ValueError("the answer is not a version")
        except Exception as e:  # noqa: BLE001
            state["release"] = {**known, "error": type(e).__name__, "asked": time.time() - RELEASE_EVERY + 3600}
            return
        here = os.getenv("NODE_VERSION", "")
        mine, theirs = release_of(here), release_of(latest)
        known = {"latest": latest, "current": here, "newer": bool(mine and theirs > mine),
                 "checked": datetime.now(timezone.utc).isoformat(timespec="seconds"), "asked": time.time()}
        state["release"] = known
    if not known.get("newer") or _quiet("info"):
        return
    # One row per version, and the row is the lock: two checks racing, or a restart, cannot send it twice.
    with db() as con, con.cursor() as cur:
        cur.execute("INSERT INTO release_notices (version) VALUES (%s) ON CONFLICT DO NOTHING RETURNING version",
                    (known["latest"],))
        first = cur.fetchone()
    if first:
        words = RELEASE_WORDS.get(settings.get("ALERT_LOCALE", "en"), RELEASE_WORDS["en"])
        notify("info", words.format(latest=known["latest"], here=known["current"] or "an older version"))


# ---------------------------------------------------------------- loops
def loop(fn, every: int, delay: int = 0):
    """Run fn forever. Each loop records its own last error under its own name: poll_once clears `last_error`
    when every source succeeds, so sharing that key would let a permanently broken rules thread look healthy."""
    name = getattr(fn, "__name__", "loop")
    state.setdefault("errors", {})

    def run():
        time.sleep(delay)
        while True:
            try:
                fn()
                state["errors"].pop(name, None)
            except Exception as e:  # noqa: BLE001
                state["errors"][name] = str(e).splitlines()[0]
                log.exception("%s failed: %s", name, e)
            time.sleep(every)

    threading.Thread(target=run, daemon=True, name=name).start()


hc = httpx.Client(timeout=60, headers={"User-Agent": "planetai-node"})


def bootstrap_once() -> None:
    """Fill the database from free global sources the first time this node starts. See app/bootstrap.py."""
    if os.getenv("BOOTSTRAP", "1") != "1" or not os.getenv("NODE_LAT"):
        return
    with db() as con, con.cursor() as cur:
        # "already bootstrapped" means model history exists, not "any row": the wizard recreates the app container
        # seconds after the first start, and a poll that landed before the kill left 14 rows that skipped this forever
        cur.execute("SELECT count(*) AS n FROM readings WHERE sensor_id='cams-point' AND ts < now() - interval '2 days'")
        if (cur.fetchone() or {}).get("n"):
            return
        log.info("first start: bootstrapping from global open data (no sensor needed)")
        state["bootstrap"] = bootstrap.run(con, hc, float(os.environ["NODE_LAT"]), float(os.environ["NODE_LON"]))
try:
    bootstrap_once()
except Exception as e:  # noqa: BLE001  — never block startup on it
    log.warning("bootstrap failed: %s", e)

try:
    _moved = settings.migrate_briefings()
    if _moved:
        log.info("moved off the old briefing settings: %s. BRIEFINGS, BRIEF_MORNING and BRIEF_EVENING stay in place and are ignored",
                 ", ".join(f"{k}={v}" for k, v in sorted(_moved.items())))
        # ALERT_LEVEL is not moved. An update adds keys a .env is missing and never overwrites one it has, which is
        # why nothing a household chose has ever changed underneath it — and it means the new `act` default reaches
        # only a fresh install. Say so once, with the one command, rather than deciding for them.
        if settings.get("ALERT_LEVEL", "act") == "warn":
            log.info("ALERT_LEVEL is still warn, so warn-level alerts still reach the phone between reports. "
                     "`planetai report level act` leaves them to the report; nothing is lost either way")
except Exception as e:  # noqa: BLE001  — never block startup on it
    log.warning("could not move off the old briefing settings: %s", e)

def load_channel_roles() -> int:
    """Declarations are the file's, not the database's: replace the table on every start so a removed pack's
    claims go with it."""
    rows = packs.channels()
    with db() as con, con.cursor() as cur:
        # db() is autocommit, so the delete and the reinsert must share one explicit transaction block —
        # otherwise the DELETE commits alone and a concurrent reader can see an empty table mid-restart.
        with con.transaction():
            cur.execute("DELETE FROM channel_roles")
            cur.executemany(
                """INSERT INTO channel_roles (source, metric, role, comparable, unit, reference, declared_by)
                   VALUES (%(source)s,%(metric)s,%(role)s,%(comparable)s,%(unit)s,%(reference)s,%(declared_by)s)""",
                rows)
    log.info("channel roles: %d declared", len(rows))
    return len(rows)


try:
    load_channel_roles()
except Exception as e:  # noqa: BLE001  — a node whose schema predates 0.22 has no channel_roles table yet
    log.warning("channel roles: %s", e)

if MQTT_HOST:
    mesh_counts_load()
    threading.Thread(target=mqtt_thread, daemon=True, name="mqtt").start()
    threading.Thread(target=sc_forward_thread, daemon=True, name="sc-forward").start()

def poll_sources() -> None:
    poll_once(hc)


def poll_reticulum() -> None:
    """Ask the bridge who it is. It announces itself on Reticulum every RETICULUM_ANNOUNCE_S — an
    "I am here, I am planetai <node>" with no data attached — and this is the node's only window
    onto whether that is actually happening."""
    if not RETICULUM_URL:
        return
    r = httpx.get(f"{RETICULUM_URL}/health", timeout=5).json()
    peers = []
    try:
        peers = httpx.get(f"{RETICULUM_URL}/peers", timeout=5).json().get("peers", [])
    except Exception as e:  # noqa: BLE001 — an older bridge has no /peers, which is not an error
        log.debug("reticulum: no peers from the bridge (%s)", e)
    reticulum_state.update({"ok": bool(r.get("ok")), "address": r.get("address"),
                            "destinations": r.get("destinations", 0),
                            "announce_s": int(os.getenv("RETICULUM_ANNOUNCE_S", "1800")),
                            "announcing": bool(r.get("announcing")),
                            "peers": _with_distance(peers),
                            "last": datetime.now(timezone.utc).isoformat()})


def _with_distance(peers: list[dict]) -> list[dict]:
    """How far each heard node is, from its coarse cell to ours. Neither end published a position.

    The distance is between two cell CENTRES, so it carries the coarseness of whichever cell is
    blunter — at res 3 two nodes in the same cell read 0 km and are somewhere within sixty. That is
    the point of it, and `res` travels with the answer so the page can say so.
    """
    here = _cell()
    out = []
    for p in peers or []:
        row = {k: p.get(k) for k in ("node", "cell", "res", "version", "kind", "first", "last", "hash")}
        row["km"] = None
        try:
            import h3  # noqa: PLC0415
            if here and here.get("id") and p.get("cell"):
                a = h3.cell_to_latlng(h3.cell_to_parent(here["id"], int(p["res"])))
                b = h3.cell_to_latlng(p["cell"])
                row["km"] = round(sources.km(a[0], a[1], b[0], b[1]))
        except Exception as e:  # noqa: BLE001 — a malformed cell from a stranger must not break the poll
            log.debug("reticulum: no distance for %s (%s)", p.get("node"), e)
        out.append(row)
    return sorted(out, key=lambda r: (r["km"] is None, r["km"] or 0))


loop(poll_sources, POLL, delay=2)
loop(run_rules, 60, delay=30)
loop(refresh_usual, 3600, delay=10)
loop(push_aggregates, 3600, delay=120)
loop(push_events, 3600, delay=150)
loop(check_release, 3600, delay=300)
if RETICULUM_URL:
    loop(poll_reticulum, 300, delay=20)

# ---------------------------------------------------------------- http
from contextlib import asynccontextmanager


@asynccontextmanager
async def _lifespan(app):
    # the MCP session manager must run for the life of the process
    async with agent.mcp.session_manager.run():
        yield


app = FastAPI(title="planetai-node", lifespan=_lifespan)


@app.middleware("http")
async def _mcp_auth(request, call_next):
    """/mcp is the agent surface. Reads through it are the same data the open API serves, but the tools can also write,
    so the whole surface needs the admin token. X-Agent names the caller for the audit trail."""
    if request.url.path.startswith("/mcp"):
        tok = os.getenv("ADMIN_TOKEN", "").strip()
        auth = request.headers.get("authorization", "")
        if not tok or not _bearer_ok(auth, tok):
            from fastapi.responses import JSONResponse
            return JSONResponse({"error": "the agent surface needs Authorization: Bearer <ADMIN_TOKEN>"}, status_code=401)
    return await call_next(request)


# What a request carrying no token may read at each SHARE_LEVEL: exact paths, plus the prefixes for the two routes that
# carry a wildcard. Anything not named here is refused — /place/geojson, /settings/raw, /backups, /aggregates and every
# write — so a route added next release is private until someone puts it on this list on purpose. That is the opposite
# of the SELECT * in /sensors, which published every new column the day it landed (A7).
#
# The `off` list is the dashboard's shell and the two reads that keep the node's own machinery running: /export, which
# backup.sh fetches over the published port to write the daily CC-BY file (already rounded to 3 dp and public by
# design), and /settings, reduced to UI_LAYOUT and SHARE_LEVEL by the route itself.
#
# The `open` list is what a wall screen on the house WiFi needs: the twenty-one paths the dashboard fetches
# (`grep -oE "(api|fetch)\('/[a-z0-9/._{}-]+" app/static/index.html`), less the three writes and /place/geojson, plus
# the two <img> routes that grep does not see (/earth/year.png at index.html:904, /earth/change.png from /earth's
# png_url) and the other-consumer reads /readings, /exports and /export.
# /sources is on the `open` list and named on purpose rather than left to default-private: it is a
# byte-identical copy of a public registry of public datasets, the same 209 rows on every node in a
# release. It says nothing about this house — not a sensor, not a reading, not a coordinate. /packs,
# already here, describes this node's own configuration and is more revealing than it is.
# /presence is here and not on the `open` list because the RETICULUM BRIDGE reads it, and the bridge
# is another container with no token: on the default SHARE_LEVEL=off it would be refused and presence
# would silently never announce. It is safe at every level by construction — it answers `{"enabled":
# false}` until a household turns announcing on, and after that it returns the same handful of facts
# the node is already broadcasting to every radio in reach.
_SHARE_OFF = (frozenset({"/", "/ui", "/health", "/llms.txt", "/settings", "/export", "/presence"}), ("/static/",))
_SHARE_OPEN = (_SHARE_OFF[0] | frozenset({
    "/stats", "/sensors", "/observations", "/alerts", "/series", "/sparks", "/rho", "/cells", "/packs", "/trust",
    "/nearby", "/forecast", "/earth", "/earth/change.png", "/earth/year.png", "/earth/frame.png",
    "/report/latest", "/readings", "/reach", "/shape", "/effect",
    "/history", "/exports", "/sources",
    # The ask pane. Its context and every tool result are scrubbed of positions, names and ids (app/ask.py), so
    # it tells a reader nothing /issues does not; it is here, and not on `off`, because it spends this machine's
    # CPU on whoever asks, and `open` is the household saying the WiFi may.
    "/ask", "/ask/status", "/docs/search",
}), ("/static/", "/exports/", "/issues", "/sources/"))
_SHARE = {"off": _SHARE_OFF, "open": _SHARE_OPEN}


def _node_tokens() -> list[str]:
    """Every token this node accepts. A request carrying one is not what SHARE_LEVEL is about: it is the NAS pulling
    /backups, the agent, Home Assistant, a parent node or someone in the house, and it reads exactly what it read
    before, from anywhere — which is the whole reason the setting can default to `off` without breaking a node on
    update. Each endpoint still checks its own token after this, so BACKUP_TOKEN getting past here does not unmask
    the Telegram token at /settings/raw."""
    return [t for t in (os.getenv("ADMIN_TOKEN", "").strip(), settings.get("BACKUP_TOKEN", "").strip(),
                        AGG_TOKEN(), ACT_TOKEN()) if t]


def _is_local(request: Request) -> bool:
    """The socket's own peer address, never a header: X-Forwarded-For would make this a one-line bypass, and uvicorn
    runs without --proxy-headers (app/Dockerfile:19) so nothing populates it here anyway.

    Inside Docker this is true for the app's own MCP tools (agent.py talks to 127.0.0.1) and for a shell in the
    container, and false for the browser on the machine hosting it, which arrives as the bridge gateway. That is
    deliberate rather than an oversight: on a node whose Docker forwards through a VM — Colima, Lima — a LAN client
    arrives as the gateway too, so trusting the bridge would trust the whole WiFi and this setting would do nothing.
    Fail closed and let the household set `open`, or carry a token."""
    return (getattr(request.client, "host", "") or "") in ("127.0.0.1", "::1", "localhost")


@app.middleware("http")
async def _share_level(request, call_next):
    """SHARE_LEVEL decides what a request with no token may read. The levels are in settings.RUNTIME["SHARE_LEVEL"];
    the allowlists are above. It governs what is answered, not where the socket binds: docker-compose.yml still
    publishes 8080 on every interface, because the NAS pulling hourly backups is the only off-machine copy of these
    readings, and the phones, the wall screens, Home Assistant and MCP are all on the network too.

    /mcp is passed straight through: _mcp_auth has already decided it, and checking the admin token twice would
    refuse an agent that authenticated correctly. That bypass is also why it does not matter which of the two
    middlewares Starlette ends up running first (it runs the last-registered outermost, i.e. this one).

    The 403 names the setting because the person reading it is usually the household, not a developer."""
    request.state.share_trusted = trusted = (
        _bearer_ok(request.headers.get("authorization", ""), *_node_tokens()) or _is_local(request))
    if request.url.path.startswith("/mcp") or trusted:
        return await call_next(request)
    level = SHARE_LEVEL()
    exact, prefixes = _SHARE.get(level, _SHARE_OFF)
    if request.url.path not in exact and not request.url.path.startswith(prefixes):
        from fastapi.responses import JSONResponse
        openable, open_prefixes = _SHARE_OPEN
        # Only offer the setting when changing it would actually answer THIS path. /version, /backups and the rest
        # are in no allowlist at any level, and telling their reader to set `open` sends them to change a setting,
        # come back, and get the same 403 — the advice has to know whether it is advice.
        fix = ("Set SHARE_LEVEL to open in the dashboard's Set up view to let anything on your network read it."
               if request.url.path in openable or request.url.path.startswith(open_prefixes)
               else "No share level opens this one, so it always needs a token from anywhere but the node itself.")
        return JSONResponse(status_code=403, content={"error":
            f"this node is set to SHARE_LEVEL={level}, so {request.url.path} answers only this machine or a request "
            f"carrying a token. {fix}"})
    return await call_next(request)


app.include_router(issues.api.router)  # GET /issues and /issues/fixtures/<name>; see app/issues/
import ask  # noqa: E402 — GET /ask/status, POST /ask, GET /docs/search: the dashboard's ask pane
app.include_router(ask.router)

for _r in agent.http_routes():        # MCP at exactly /mcp, no trailing-slash redirect
    app.router.routes.append(_r)


def q(sql: str, *args):
    with db() as con, con.cursor() as cur:
        cur.execute(sql, args)
        return [{k: (v.isoformat() if isinstance(v, datetime) else v) for k, v in r.items()} for r in cur.fetchall()]


@app.get("/health")
def health(request: Request):
    schema = None
    try:
        with db() as con, con.cursor() as cur:
            # latest applied, not the lexically largest: '0.4' > '0.14' as text
            cur.execute("SELECT version AS v FROM schema_version ORDER BY applied_at DESC, string_to_array(version,'.')::int[] DESC LIMIT 1")
            schema = (cur.fetchone() or {}).get("v")
    except psycopg.OperationalError:
        # The database is there but this app cannot use it — wrong password after a reinstall over an
        # earlier volume, db down, wrong host. That is a login problem, not a schema age: answering
        # "pre-0.4 (run ./update.sh)" here sent keepers running a migration against a database the
        # app could not log in to, while the real fix is in .env. `planetai doctor` reads this string.
        schema = "unreachable (the app cannot log in to its database — planetai doctor says why)"
    except Exception:  # noqa: BLE001 — a pre-0.4 node has no schema_version table until it updates
        schema = "pre-0.4 (run ./update.sh)"
    # A12, superseded by R25 (v0.73): see _published_position. Before v0.73 this was 3 decimals for every caller.
    # The rest of the old reasoning stands: round(x, 3) is
    # 110 m, which changes no answer a consumer computes from this — while five decimals is 1.1 m, i.e. the doorway.
    # `cell` is an H3 resolution 8 (~500 m edge), coarser than the rounding, so it does not put the position back.
    # `node` stays: /export publishes it under CC BY by design, /aggregates posts it to a parent, agent.py reads it
    # out of here, and the dashboard prints it in five places. If the name is ever sensitive it comes out of all of
    # them at once, which is a different change.
    return {"ok": state["last_poll"] is not None, "node": NODE, "version": os.getenv("NODE_VERSION", "?"),
            "schema": schema, "uptime_s": int(time.time() - STARTED),
            **_published_position(bool(getattr(request.state, "share_trusted", False))),
            "city": os.getenv("NODE_CITY", ""), **state,
            # The household's own language, so the page can be written in it. /issues carries every
            # sentence in all three and carries no way to choose — `snap.locale` was read by the
            # dashboard and set by nothing, so the test fell through to 'en' on every node, in every
            # view, whatever the household had set. It goes here rather than on /issues because
            # /health is the one read that answers at EVERY share level: a node at the default
            # SHARE_LEVEL=off refuses /issues and reduces /settings to two keys, and the page that a
            # refused household actually sees is the one that most needs to be in their language.
            # Not a secret: ALERT_LOCALE is already in settings.PUBLIC and /settings hands out its value.
            "locale": settings.get("ALERT_LOCALE", "en"),
            # And the clock the readings were taken on. The dashboard formatted every timestamp in the
            # VIEWER's timezone, so a Madrid node polling at 17:35 read "As of 11:40 PM" on a laptop in
            # Bali and nothing on the page named a zone. A reading belongs to the place it was taken in.
            "tz": os.getenv("NODE_TZ", ""),
            "cell": _cell(),
            # Where to read about this node and how to reach its tools, so a reader holding only this answer
            # can go further: the documentation, the MCP endpoint (token-gated) and this node's own /llms.txt.
            "docs": DOCS_URL, "mcp": "/mcp", "llms": "/llms.txt",
            **({"mesh": mesh_state, "direct": sc_state} if MQTT_HOST else {}),
            **({"reticulum": reticulum_state} if RETICULUM_URL else {})}


# Nothing finer than this may be announced. res 6 is roughly 3 km across; below that a node is
# telling an open radio network which neighbourhood it is in, and that is not a thing anyone should
# be able to do by typing a number into a settings box.
PRESENCE_RES_FLOOR = 6


def _presence_res() -> int:
    try:
        r = int(settings.get("RETICULUM_PRESENCE_RES", "3") or 3)
    except ValueError:
        return 3
    return max(0, min(r, PRESENCE_RES_FLOOR))


@app.get("/presence")
def presence():
    """What this node is willing to announce about itself, and whether it is announcing at all.

    The Reticulum bridge asks this — it has no h3 and no settings of its own — and announces exactly
    what comes back, or nothing when `enabled` is false. Open on purpose at every share level: when
    presence is on, this is the same handful of facts the node is already broadcasting to any radio
    within reach, and when it is off it answers with nothing but that.

    The cell is the node's own res-8 cell rounded UP to a coarse parent: at the default res 3 that is
    an area about sixty kilometres across, which names an island and not an address. Distance between
    two nodes is then two cell centres, and neither of them ever published a position.
    """
    on = settings.get("RETICULUM_PRESENCE", "0") == "1"
    if not on:
        return {"enabled": False}
    here = _cell()
    res = _presence_res()
    cell = None
    if here and here.get("id"):
        try:
            import h3  # noqa: PLC0415 — only this path needs it
            cell = h3.cell_to_parent(here["id"], res)
        except Exception as e:  # noqa: BLE001
            log.warning("presence: could not coarsen %s to res %d (%s)", here.get("id"), res, e)
    return {"enabled": True, "node": NODE, "cell": cell, "res": res,
            "version": os.getenv("NODE_VERSION", "?"), "kind": os.getenv("NODE_KIND", "") or None}


def _published_position(trusted: bool = False) -> dict:
    """The position this node hands to a reader it does not know: the centre of its resolution-8 cell, the same
    cell `/health` has always named. Decided 23 Sep 2026 (R25): nothing finer than that cell leaves the node for
    an untrusted reader or in the open export. Three decimals, which this route and /export carried before
    v0.73, is about 110 m, finer than the ~500 m cell the programme page promises. A trusted reader (a token,
    or this machine) still gets three decimals, because it can read /place/geojson anyway and the household's
    own plan is drawn from it. `position` says which one the reader got, so a page can say so.

    Without coordinates, or without h3 in an old image, it falls back to two decimals (~1.1 km), which is
    coarser than the cell rather than finer: failing toward the household."""
    lat, lon = float(os.getenv("NODE_LAT", 0) or 0), float(os.getenv("NODE_LON", 0) or 0)
    if trusted or not (lat or lon):
        return {"lat": round(lat, 3), "lon": round(lon, 3), "position": "point"}
    clat, clon = _coarse(lat, lon)
    return {"lat": clat, "lon": clon, "position": "cell"}


def _coarse(lat, lon):
    """A point snapped to the centre of its resolution-8 cell, three decimals; two decimals without h3."""
    if lat is None or lon is None:
        return lat, lon
    try:
        import h3  # noqa: PLC0415
        clat, clon = h3.cell_to_latlng(h3.latlng_to_cell(float(lat), float(lon), 8))
        return round(clat, 3), round(clon, 3)
    except Exception:  # noqa: BLE001
        return round(float(lat), 2), round(float(lon), 2)


def _cell() -> dict | None:
    """The H3 cell this node stands in: id, resolution, the mean edge of this cell in metres, and the
    line the dashboard prints under the hero. None before setup, when there is no place to name."""
    lat, lon = os.getenv("NODE_LAT", ""), os.getenv("NODE_LON", "")
    if not lat or not lon:
        return None
    try:
        return ground.facts(float(lat), float(lon))
    except Exception as e:  # noqa: BLE001
        log.warning("cell: %s: %s", type(e).__name__, e)
        return None


# What of a sensor's `meta` an untrusted caller sees: provenance, which is what makes a reading citable. Everything
# else in there describes the household's network rather than the measurement.
_META_PUBLIC = ("licence", "attribution", "model", "dataset", "network", "note", "corrected")

# A FACILITY IS NOT A SENSOR, and the list above was written about sensors. It drops `host`,
# `firmware`, `gateway`, `channel` and `topic` because those describe the household's own network —
# correct for a thing in this house, and meaningless for a fab lab, which is somebody else's
# building, published by name and coordinate in a public directory the node read it from.
#
# The effect until now: a facility row reached the page carrying `attribution` and nothing else, so
# the dashboard could name a place and could not say how far away it is or what is in it. The page
# runs in a browser on the LAN and is therefore untrusted, so this was not a corner case — it was
# every reader. Every key below describes the lab or the archive it came from; not one of them is a
# fact about this household that `lat`, `lon` and the node's own position do not already publish.
_META_PUBLIC_FACILITY = _META_PUBLIC + (
    "slug", "capabilities", "kind_name", "city", "country_code",
    "distance_km", "url", "registry_slug", "snapshot", "fetched")


@app.get("/sensors")
def sensors_(request: Request):
    """Every sensor this node reads, its position, and where its numbers come from.

    The columns are named rather than `SELECT *`, which is the actual fix for A7: the star published every column
    added to `sensors` on the day it landed, so the redaction below would have gone stale by itself. Add a column and
    it stays private until it is named here.

    For a caller that is neither on this machine nor carrying a token, the position of this household's own sensors
    (`custody`) is the centre of their resolution-8 cell and every other position is rounded to 3 decimals, and `meta` is cut to _META_PUBLIC. On a real node that drops `host`,
    `firmware`, `mesh_node`, `gateway`, `channel`, `root_topic` and `topic` — an AirGradient row otherwise hands a
    stranger on the WiFi `{"host": "airgradient_84fce6.local", "model": "I-9PSL", "firmware": "3.1.9"}` next to a
    room name and five decimals of position."""
    # `custody` travels with the row: it is the answer to "why is my cell partial", and a person looking at
    # /sensors should not have to rederive it from `local` and `kind`.
    rows = q("SELECT sensor_id, source, name, lat, lon, indoor, local, custody, kind, scale, cadence, meta FROM sensors ORDER BY custody DESC, local DESC, name")
    if getattr(request.state, "share_trusted", False):
        return rows
    for r in rows:
        # This household's own instruments stand in its house, so an untrusted reader gets the cell's centre
        # for them (R25). Everything else here is a public station, a model point or a lab, whose position is
        # public at its source; three decimals is what it always was.
        if r.get("custody"):
            r["lat"], r["lon"] = _coarse(r["lat"], r["lon"])
        else:
            for k in ("lat", "lon"):
                r[k] = round(r[k], 3) if r[k] is not None else None
        allow = _META_PUBLIC_FACILITY if r.get("kind") == "facility" else _META_PUBLIC
        r["meta"] = {k: v for k, v in (r["meta"] or {}).items() if k in allow} or None
    return rows


@app.get("/readings")
def readings(sensor_id: str | None = None, metric: str | None = None, limit: int = Query(200, ge=1, le=10000)):
    # the NULL parameters need a type or Postgres cannot plan the query (500 on every call since psycopg 3)
    return q("SELECT ts, sensor_id, metric, value FROM readings WHERE (%s::text IS NULL OR sensor_id=%s::text) AND (%s::text IS NULL OR metric=%s::text) ORDER BY ts DESC LIMIT %s",
             sensor_id, sensor_id, metric, metric, limit)


@app.get("/stats")
def stats(request: Request):
    """Rolling 15m/1h/24h — sensors only. Slow sources (portals, models, surveys) are in /observations.

    Positions follow /sensors (#113): unrounded for this machine or a token, and for anyone else the household's
    own sensors at their cell's centre and the rest at three decimals. Before v0.73 this route handed every
    reader at SHARE_LEVEL=open the positions /sensors had rounded."""
    rows = q("SELECT * FROM stats ORDER BY local DESC, sensor_id, metric")
    if getattr(request.state, "share_trusted", False):
        return rows
    own = {r["sensor_id"] for r in q("SELECT sensor_id FROM sensors WHERE custody")}
    for r in rows:
        if "lat" not in r:
            continue
        if r.get("sensor_id") in own:
            r["lat"], r["lon"] = _coarse(r.get("lat"), r.get("lon"))
        else:
            r["lat"] = round(r["lat"], 3) if r.get("lat") is not None else None
            r["lon"] = round(r["lon"], 3) if r.get("lon") is not None else None
    return rows


@app.get("/reach")
def reach():
    """How far back this node's own record goes, per kind of source.

    The Historical view draws years of satellite record beside a node that may have been switched on
    last week, and nothing on the page said which. A reader comparing 2017 to now deserves to know
    that the line under it starts in September — the satellite's reach and this node's are different
    lengths and the page was drawing them as if they were the same.

    Per kind, because the kinds reach back differently and for different reasons: this house's own
    sensors go back to the day somebody plugged them in, a model's point samples start when the pack
    was enabled, and a portal's history is whatever the portal chose to publish. One number for all
    of them would be the shortest of them, reported as if it were the record.

    `readings_1h` and not `readings`: the hourly means are what survives, and they are what every
    chart on the page is drawn from, so this is the reach of the thing actually shown.
    """
    return q("""SELECT s.kind,
                       min(r.bucket) AS oldest, max(r.bucket) AS newest,
                       count(*) AS buckets, count(DISTINCT r.sensor_id) AS sources,
                       round(extract(epoch FROM max(r.bucket) - min(r.bucket)) / 86400.0)::int AS days
                FROM readings_1h r JOIN sensors s USING (sensor_id)
                GROUP BY s.kind ORDER BY s.kind""")


@app.get("/trust")
def trust():
    """One row per local sensor, for the dashboard's trust card and the agent's health check — never both computing
    it themselves and drifting apart from packs/trust/rules.yml. coverage_7d is the percentage of the last 168
    hourly buckets its ambient channels reported in, same arithmetic as the coverage_low rule. frozen_channels
    counts its ambient/enclosure channels that match all three of channel_dead's conditions: flat for 6+ hours in
    the last 24, still flat in the latest bucket, AND the kit itself still producing raw readings in the last 2
    hours (the `alive` CTE below) — a channel whose kit has gone dark entirely is not "frozen", it is offline, and
    channel_dead would never fire for it. age_hours is how long since its first ever reading: under 168, the
    sensor has not lived a full week yet, so a low coverage_7d there is not a fault, just an incomplete week."""
    return q("""
        WITH ours AS (
          SELECT r.sensor_id, r.metric
          FROM readings_1h r JOIN sensors s USING (sensor_id)
          JOIN channel_roles c ON c.source = s.source AND c.metric = r.metric
          WHERE s.local AND s.kind = 'sensor' AND c.role IN ('ambient', 'enclosure')
          GROUP BY 1, 2),
        frozen_stat AS (
          SELECT o.sensor_id, o.metric,
                 max(r.bucket) AS last_bucket,
                 max(r.bucket) FILTER (WHERE r.max - r.min = 0) AS last_flat_bucket,
                 count(*) FILTER (WHERE r.max - r.min = 0) AS flat_hours
          FROM ours o JOIN readings_1h r ON r.sensor_id = o.sensor_id AND r.metric = o.metric
          WHERE r.bucket > now() - interval '24 hours'
          GROUP BY 1, 2),
        alive AS (
          SELECT sensor_id, max(ts) AS kit_ts FROM readings
          WHERE ts > now() - interval '2 hours' GROUP BY 1),
        frozen AS (
          SELECT fs.sensor_id, count(*) AS frozen_channels
          FROM frozen_stat fs JOIN alive a USING (sensor_id)
          WHERE fs.flat_hours >= 6 AND fs.last_bucket = fs.last_flat_bucket
          GROUP BY 1),
        have AS (
          SELECT r.sensor_id, count(DISTINCT r.bucket) AS hours
          FROM readings_1h r JOIN sensors s USING (sensor_id)
          JOIN channel_roles c ON c.source = s.source AND c.metric = r.metric
          WHERE s.local AND s.kind = 'sensor' AND c.role = 'ambient' AND c.comparable
            AND r.bucket > now() - interval '7 days'
          GROUP BY 1),
        age AS (SELECT sensor_id, extract(epoch FROM now() - min(ts)) / 3600 AS age_hours FROM readings GROUP BY 1)
        SELECT s.sensor_id, s.name,
               round(100.0 * coalesce(h.hours, 0) / 168) AS coverage_7d,
               coalesce(f.frozen_channels, 0) AS frozen_channels,
               round(coalesce(a.age_hours, 0)) AS age_hours
        FROM sensors s LEFT JOIN have h USING (sensor_id) LEFT JOIN frozen f USING (sensor_id) LEFT JOIN age a USING (sensor_id)
        WHERE s.local AND s.kind = 'sensor'
        ORDER BY s.name
    """)


@app.get("/nearby")
def nearby(audit: bool = False):
    """The ring: other people's stations around this node, and where this node sits inside it.

    `?audit=1` calls the archive and returns a verdict for every station it lists, which is the same answer
    `planetai run nearby stations` prints. Without it this reads only what is already stored, so the dashboard
    never waits on someone else's server.

    A station excluded after it was already stored keeps its row and stops getting readings, so `reporting` goes
    false and it leaves the ring's numbers within two hours on its own. The row is left alone rather than deleted:
    what it measured while it was in the ring was still measured.
    """
    ring = q("""
        SELECT s.sensor_id, s.name, s.lat, s.lon, s.indoor, s.meta->>'network' AS network,
               round((s.meta->>'km')::numeric, 2) AS km,
               round(st.mean_1h::numeric, 1) AS pm25,
               round(st.silent_minutes::numeric) AS silent_minutes, st.last_ts,
               (st.silent_minutes IS NOT NULL AND st.silent_minutes < 120) AS reporting
        FROM sensors s LEFT JOIN stats st
          ON st.sensor_id = s.sensor_id AND st.metric = 'pm25'
        WHERE s.source = 'baliairdispatch' AND NOT s.local
          -- a station excluded after it was stored keeps its row but stops getting readings. Drop it from the
          -- list after a day rather than leaving it on the card as a neighbour that never answers.
          AND st.last_ts > now() - interval '24 hours'
        ORDER BY (s.meta->>'km')::numeric NULLS LAST""")
    shape = q("""
        WITH ring AS (
          SELECT st.mean_1h AS pm,
                 sqrt(power((st.lat - current_setting('planetai.lat')::float) * 111320, 2)
                    + power((st.lon - current_setting('planetai.lon')::float) * 111320
                            * cos(radians(current_setting('planetai.lat')::float)), 2)) / 1000 AS km
          FROM stats st JOIN sensors sn USING (sensor_id)
          WHERE sn.source = 'baliairdispatch' AND NOT st.local AND NOT st.indoor AND st.kind = 'sensor' AND st.metric = 'pm25'
            AND st.mean_1h IS NOT NULL AND st.silent_minutes < 120 AND st.lat IS NOT NULL),
        mine AS (
          SELECT avg(mean_1h) AS pm, count(*) AS n FROM stats
          WHERE local AND NOT indoor AND kind = 'sensor' AND metric = 'pm25'
            AND mean_1h IS NOT NULL AND silent_minutes < 120)
        SELECT (SELECT count(*) FROM ring)                                                        AS stations,
               (SELECT round(min(pm)::numeric, 1) FROM ring)                                      AS lowest,
               (SELECT round(percentile_cont(0.25) WITHIN GROUP (ORDER BY pm)::numeric, 1) FROM ring) AS p25,
               (SELECT round(percentile_cont(0.5)  WITHIN GROUP (ORDER BY pm)::numeric, 1) FROM ring) AS median,
               (SELECT round(percentile_cont(0.75) WITHIN GROUP (ORDER BY pm)::numeric, 1) FROM ring) AS p75,
               (SELECT round(max(pm)::numeric, 1) FROM ring)                                      AS highest,
               (SELECT round(min(km)::numeric, 1) FROM ring)                                      AS nearest_km,
               (SELECT round(pm::numeric, 1) FROM mine)                                           AS mine,
               (SELECT n FROM mine)                                                               AS mine_sensors""")
    out = {"ring": ring, **(shape[0] if shape else {}),
           "radius_km": float(settings.get("BAD_RADIUS_KM", "15")),
           "attribution": ["Bali Air Dispatch, baliairdispatch.com",
                           "and the network named in each station's `network` field"]}
    m, med = out.get("mine"), out.get("median")
    out["mine_minus_ring"] = None if m is None or med is None else round(float(m) - float(med), 1)
    if audit:
        try:
            import sources
            hc = httpx.Client(timeout=30, headers={"user-agent": "planetai-node"})
            rows = hc.get(sources.BAD_LATEST).json().get("readings", [])
            ids = {int(x) for x in settings.get("SC_DEVICES", "").replace(" ", "").split(",") if x}
            if settings.get("SC_USER", "").strip():
                ids |= set(sources.smartcitizen_account(hc, settings.get("SC_USER").strip()))
            own = {f"sc-{i}" for i in ids}
            own |= {f"ag-{h.replace('.local', '').replace('airgradient_', '')}"
                    for h in settings.get("AIRGRADIENT_HOSTS", "").replace(" ", "").split(",") if h}
            byhand = {x for x in settings.get("BAD_EXCLUDE", "").replace(" ", "").split(",") if x}
            lat, lon = float(os.environ["NODE_LAT"]), float(os.environ["NODE_LON"])
            out["audit"] = [{"station_id": r["station_id"], "name": r.get("name"), "network": r.get("source"),
                             "km": None if r.get("latitude") is None else round(sources.km(lat, lon, r["latitude"], r["longitude"]), 2),
                             "verdict": v}
                            for r, v in sources.bad_verdicts(rows, lat, lon, out["radius_km"], own, byhand,
                                                             float(settings.get("BAD_MIN_SEPARATION_M", "150")),
                                                             settings.get("BAD_INCLUDE_INDOOR", "0") == "1")]
        except Exception as e:  # noqa: BLE001  — a source that is down must not take the endpoint down
            out["audit_error"] = f"{type(e).__name__}: {str(e)[:160]}"
    return out


@app.get("/forecast")
def forecast(hours: int = Query(24, ge=1, le=72)):
    """Official and model weather for this point: where the wind comes from, when rain is expected, and when the
    forecast was issued. Context for reading this node's own air. The node fetches it; it does not predict."""
    who = q("""SELECT sensor_id, name, lat, lon, meta FROM sensors
               WHERE source IN ('forecast-bmkg','forecast-om','forecast-gap') ORDER BY sensor_id""")
    rows = q("""SELECT sensor_id, ts, metric, value FROM readings
                WHERE sensor_id IN ('forecast-bmkg','forecast-om','forecast-gap')
                  AND ts > now() - interval '3 hours' AND ts < now() + make_interval(hours => %s)
                ORDER BY ts, sensor_id, metric""", hours)
    steps: dict = {}
    for r in rows:
        steps.setdefault((str(r["ts"]), r["sensor_id"]), {})[r["metric"]] = r["value"]
    lat, lon = float(os.getenv("NODE_LAT", 0) or 0), float(os.getenv("NODE_LON", 0) or 0)
    out = {"point": {"lat": lat, "lon": lon},
           "sources": [{"sensor_id": w["sensor_id"], "name": w["name"], "lat": w["lat"], "lon": w["lon"],
                        "issued": (w["meta"] or {}).get("issued"), "fetched": (w["meta"] or {}).get("fetched"),
                        "km_from_node": (w["meta"] or {}).get("km_from_node")} for w in who],
           "hours": [{"ts": k[0], "source": k[1], **v} for k, v in sorted(steps.items())],
           "attribution": ["BMKG (Badan Meteorologi, Klimatologi, dan Geofisika), api.bmkg.go.id",
                           "Open-Meteo, open-meteo.com, CC-BY 4.0 (free tier: non-commercial use only)"]}
    # a forecast for somewhere else is still a forecast, but the card has to say so rather than imply this point
    far = [w for w in out["sources"] if (w.get("km_from_node") or 0) > 10]
    out["far_from_node"] = [{"sensor_id": w["sensor_id"], "km": w["km_from_node"]} for w in far] or None
    return out


@app.get("/observations")
def observations():
    """Latest value per slow-moving source: city statistics, model point samples, survey results."""
    return q("SELECT * FROM observations ORDER BY scale, sensor_id, metric")


@app.get("/alerts")
def alerts(limit: int = Query(50, ge=0, le=1000), since_hours: int = Query(0, ge=0, le=2160)):
    """Alerts newest first, each with its id (what `planetai act <id>` and the GUI's Act button need) and whether
    anyone has already acted on it. `since_hours` keeps only those of the last that many hours; 0 is no bound."""
    return q("""SELECT a.id, a.ts, a.rule_id, a.sensor_id, a.level, a.text,
                       (SELECT min(x.ts) FROM actions x WHERE x.alert_id = a.id AND x.stage IN ('acknowledged','acted')) AS acted_at
                FROM alerts a WHERE %s = 0 OR a.ts > now() - make_interval(hours => %s)
                ORDER BY a.ts DESC LIMIT %s""", since_hours, since_hours, limit)


@app.get("/actions")
def actions(limit: int = Query(500, ge=0, le=5000), stage: str = "", events: int = Query(0, ge=0, le=1)):
    """Every answer a person gave an alert, newest first: which alert, which stage, who, and the note they left.

    `/alerts` says only *whether* somebody acted, as one timestamp. The stage is the thing the Act ledger and
    the funnel are counted from, and acknowledged, acted and measured are three different answers — collapsing
    them to "acted_at" loses the question. `issues/engine.py::_read` reads this table directly, so a snapshot
    that cannot fetch it replays with no act ledger, no stages and no funnel, and nothing says so at render
    time (docs/design/PICK_2026-09-20.md, gap J).

    On neither share allowlist, deliberately: `actor` and `note` are the household's own words about what they
    did in their own house. This answers a token or the machine itself, and nothing else.

    `stage` narrows it to one stage, and `stage=settings` is the only way to read the node's own rows: who changed
    which settings, and when. The dashboard's Set up reads them to say who moved a key while its form was open.

    events=1 adds the answers to alert events, with their event_id (docs/SPEC_dashboard_events.md §3.4).
    """
    if stage:
        if events:
            # With events=1 on a stage filter, include event rows with their event_id. Settings rows (both NULL)
            # must always be returned regardless of events flag.
            return q("SELECT ts, alert_id, event_id, stage, actor, note FROM actions WHERE stage = %s "
                     "ORDER BY ts DESC LIMIT %s",
                     stage, limit)
        # Default: exclude event rows (alert_id NULL, event_id set) but keep settings rows (both NULL)
        return q("SELECT ts, alert_id, stage, actor, note FROM actions WHERE stage = %s AND "
                 "(alert_id IS NOT NULL OR event_id IS NULL) ORDER BY ts DESC LIMIT %s",
                 stage, limit)
    if events:
        # the event answers too, with event_id; without it the v0.76 page never meets a row with no alert_id
        return q("SELECT ts, alert_id, event_id, stage, actor, note FROM actions "
                 "WHERE alert_id IS NOT NULL OR event_id IS NOT NULL ORDER BY ts DESC LIMIT %s", limit)
    return q("SELECT ts, alert_id, stage, actor, note FROM actions WHERE alert_id IS NOT NULL "
             "ORDER BY ts DESC LIMIT %s", limit)


@app.get("/series")
def series(metric: str = "pm25", hours: int = Query(24, ge=1, le=168)):
    """Hourly means for the dashboard's strip: local indoor, everything outdoor (yours and references), and the
    model, as three aligned arrays. What readings_1h already knows, shaped for a chart."""
    rows = q("""
        WITH h AS (SELECT generate_series(date_trunc('hour', now()) - make_interval(hours => %s - 1), date_trunc('hour', now()), interval '1 hour') AS bucket),
        r AS (SELECT r.bucket,
                     avg(r.mean) FILTER (WHERE s.local AND s.indoor) AS indoor,
                     avg(r.mean) FILTER (WHERE NOT s.indoor AND s.kind = 'sensor') AS outdoor
              FROM readings_1h r JOIN sensors s USING (sensor_id)
              WHERE r.metric = %s AND r.bucket > now() - make_interval(hours => %s) GROUP BY r.bucket),
        m AS (SELECT date_trunc('hour', ts) AS bucket, avg(value) AS model FROM readings
              WHERE sensor_id = 'cams-point' AND metric = %s || '_model' AND ts > now() - make_interval(hours => %s) GROUP BY 1)
        SELECT h.bucket, r.indoor, r.outdoor, m.model FROM h LEFT JOIN r USING (bucket) LEFT JOIN m USING (bucket) ORDER BY h.bucket""",
        hours, metric, hours, metric, hours)
    return {"metric": metric, "hours": hours, "buckets": [x["bucket"] for x in rows],
            "indoor": [x["indoor"] for x in rows], "outdoor": [x["outdoor"] for x in rows], "model": [x["model"] for x in rows]}


@app.get("/effect")
def effect(days: int = Query(365, ge=1, le=3650)):
    """Did the actions work, and how long did they take? Per rule, over this node's whole record.

    TWO DIFFERENT QUESTIONS WITH TWO DIFFERENT KINDS OF EVIDENCE, and they are reported apart because
    conflating them would overstate the second.

    `cleared` is the funnel's derivation, per rule: an act followed by a full MEASURED_WINDOW_MIN of silence from
    the same rule on the same sensor is the condition having stopped being true. It works for every rule, needs no
    threshold, and says WHETHER. It cannot say when: run_rules re-fires the moment a cooldown expires and the
    condition still holds, so the finest this evidence can ever resolve is one cooldown.

    `hours` is the other question and it needs the readings. Only a rule that declares `watch: {metric, over}` has an
    indicator and a line to recover under -- of node #1's seven act-level rules, two do; the rest fire on a RELATION
    ("inside is worse than outside"), where a threshold would be a fiction. For those the answer is null and the
    reason is published rather than a zero.

    AND IT IS ELAPSED TIME, NOT AN EFFECT. A window opened at 21:00 and air that cleared at 03:00 may be the window
    or may be the night, and this node cannot tell. Nothing here says the action caused the recovery.

    `already` IS NOT A NOUGHT-HOUR RECOVERY and has two causes, which is why it is counted apart rather than folded
    into the median. Node #1's five acts on indoor_pm25_high are all `already`, and reading them one by one shows
    both: people acted 2.0, 1.8 and 10.3 hours after the alert, by which time the air had come back on its own --
    and separately, the rule triggers on `mean_15m` while the only history a node keeps is hourly, so a
    fifteen-minute spike over 35.5 can fire without the hour ever crossing it (four of those five had an hourly mean
    of 14 to 22 when they fired). The measurement is therefore COARSER THAN THE TRIGGER, structurally, and the
    honest report is a count of the acts it cannot time rather than a number that pretends otherwise.

    Retired rules are excluded for the reason index.py::_live_rule_ids exists: a rule that can never fire again would
    have its silence counted as a cleared condition, which once made this node's own funnel report 8 where the true
    number was 5."""
    win = index.MEASURED_WINDOW_MIN
    live = index._live_rule_ids()
    if not live:
        return {"window_hours": round(win / 60), "rules": [], "note": "this node could not read its rule set"}
    rows = q("""WITH a AS (SELECT id, ts, rule_id, sensor_id FROM alerts
                            WHERE level = 'act' AND rule_id = ANY(%s)
                              AND ts > now() - make_interval(days => %s)),
                     act AS (SELECT alert_id, min(ts) AS t FROM actions WHERE stage = 'acted' GROUP BY alert_id),
                     -- only an act whose window has fully elapsed can be judged either way
                     j AS (SELECT a.rule_id, a.id, a.sensor_id, act.t AS acted_at,
                                  NOT EXISTS (SELECT 1 FROM alerts r
                                               WHERE r.rule_id = a.rule_id
                                                 AND r.sensor_id IS NOT DISTINCT FROM a.sensor_id
                                                 AND r.ts > act.t
                                                 AND r.ts <= act.t + make_interval(mins => %s)) AS cleared
                           FROM a JOIN act ON act.alert_id = a.id
                           WHERE now() > act.t + make_interval(mins => %s))
                SELECT rule_id, count(*) AS acted, count(*) FILTER (WHERE cleared) AS cleared
                FROM j GROUP BY rule_id ORDER BY count(*) DESC, rule_id""",
             live, days, win, win)
    watches = {r["id"]: r["watch"] for r in packs.load_rules()
               if isinstance(r, dict) and isinstance(r.get("watch"), dict)}
    out = []
    for r in rows:
        w = watches.get(r["rule_id"])
        item = {"rule_id": r["rule_id"], "acted": int(r["acted"]), "cleared": int(r["cleared"]),
                "watch": w, "hours": None, "measured": 0, "already": 0}
        if w:
            # The first hour, at or after the act, when that alert's own sensor is back under the line. `already`
            # is an act made when the reading had come back on its own, which is a real and common thing and not
            # a nought-hour recovery.
            h = q("""WITH a AS (SELECT id, ts, sensor_id FROM alerts
                                 WHERE level='act' AND rule_id = %s AND ts > now() - make_interval(days => %s)),
                          act AS (SELECT alert_id, min(ts) AS t FROM actions WHERE stage='acted' GROUP BY alert_id),
                          e AS (SELECT a.id, act.t AS acted_at,
                                       (SELECT min(x.bucket) FROM readings_1h x
                                         WHERE x.sensor_id = a.sensor_id AND x.metric = %s
                                           AND x.bucket >= date_trunc('hour', act.t) AND x.mean < %s) AS ok_at
                                FROM a JOIN act ON act.alert_id = a.id)
                     SELECT count(*) FILTER (WHERE ok_at IS NOT NULL
                                             AND ok_at > date_trunc('hour', acted_at)) AS measured,
                            count(*) FILTER (WHERE ok_at IS NOT NULL
                                             AND ok_at <= date_trunc('hour', acted_at)) AS already,
                            percentile_cont(0.5) WITHIN GROUP (
                              ORDER BY extract(epoch FROM ok_at - acted_at) / 3600.0)
                              FILTER (WHERE ok_at IS NOT NULL
                                      AND ok_at > date_trunc('hour', acted_at)) AS median_hours
                     FROM e""", r["rule_id"], days, w["metric"], w["over"])
            g = (h[0] if h else {}) or {}
            item["measured"] = int(g.get("measured") or 0)
            item["already"] = int(g.get("already") or 0)
            item["hours"] = round(float(g["median_hours"]), 1) if g.get("median_hours") is not None else None
        out.append(item)
    return {"window_hours": round(win / 60), "days": days, "rules": out}


@app.get("/shape")
def shape(metric: str = "pm25"):
    """The day this place usually has: one hour-of-day mean per hour, over the whole record, indoor against outdoor.

    THE HOURS ARE LOCAL, and that is not incidental. `extract(hour FROM bucket)` answers in the session timezone, and
    db() sets it from NODE_TZ on every connection for exactly this reason -- the comment there records the day
    boundaries and "evening" landing eight hours out in Bali once already. Read the same query in a psql session,
    which does not go through db(), and node #1's shape moves by eight hours and says the opposite thing: a midday
    cooking peak reads as a 4 a.m. one. Anything computing an hour-of-day here must go through db().

    INDOOR AND OUTDOOR ARE SEPARATE because on node #1 they are ANTI-PHASED -- inside peaks at meal times, outside
    peaks in the evening -- and one average over both is a number that describes neither and hides the only thing a
    household could act on.

    `days` is how many distinct local days this node's OWN stations have for this metric, and `windows` is what that
    record can honestly support. A node installed this morning has a day and says so; it does not draw a year from
    it. That refusal is the point: this is the one place a page is most tempted to describe a pattern it has not
    seen."""
    rows = q("""SELECT extract(hour FROM h.bucket)::int AS hour,
                       avg(h.mean) FILTER (WHERE s.indoor)     AS indoor,
                       avg(h.mean) FILTER (WHERE NOT s.indoor) AS outdoor,
                       count(*) AS n
                FROM readings_1h h JOIN sensors s USING (sensor_id)
                WHERE h.metric = %s AND s.local
                GROUP BY 1 ORDER BY 1""", metric)
    span = q("""SELECT count(DISTINCT date_trunc('day', h.bucket)) AS days,
                       min(h.bucket) AS first, max(h.bucket) AS last
                FROM readings_1h h JOIN sensors s USING (sensor_id)
                WHERE h.metric = %s AND s.local""", metric)
    d = (span[0] if span else {}) or {}
    days = int(d.get("days") or 0)
    # What the record supports, decided here and not on the page: the page draws what the node says it may.
    # A day's shape wants a week behind it before an hourly mean means anything; a week-on-week comparison wants two;
    # a month wants two months to compare; a year wants a year. Nothing here is a forecast and nothing extrapolates.
    return {"metric": metric, "days": days, "first": d.get("first"), "last": d.get("last"),
            "hours": [{"hour": r["hour"], "indoor": r["indoor"], "outdoor": r["outdoor"], "n": r["n"]} for r in rows],
            "windows": {"day": days >= 7, "week": days >= 14, "month": days >= 60, "year": days >= 365}}


@app.get("/export")
def export(day: str = Query(..., pattern=r"^\d{4}-\d{2}-\d{2}$")):
    """One day of this node as open data: hourly means per sensor and metric, the Index cells, the alerts, rho.
    What a parent node, the Index, a researcher or IPFS should receive. Never raw readings, never secrets.
    Your own sensors are named by role (indoor-1, outdoor-1), not by their device id."""
    try:
        datetime.strptime(day, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(422, "day must be a real date, YYYY-MM-DD")
    hourly = q("""SELECT r.bucket, r.sensor_id, s.local, s.indoor, s.kind, s.scale, r.metric, r.mean, r.min, r.max, r.n
                  FROM readings_1h r JOIN sensors s USING (sensor_id)
                  WHERE r.bucket >= %s::date AND r.bucket < %s::date + 1 ORDER BY r.bucket, r.sensor_id, r.metric""", day, day)
    alias, counts = {}, {"indoor": 0, "outdoor": 0}
    def name(row):
        if not row["local"]:
            return row["sensor_id"]                      # public references and models are public already
        if row["sensor_id"] not in alias:
            k = "indoor" if row["indoor"] else "outdoor"; counts[k] += 1; alias[row["sensor_id"]] = f"{k}-{counts[k]}"
        return alias[row["sensor_id"]]
    rows = [{"t": r["bucket"], "sensor": name(r), "local": r["local"], "indoor": r["indoor"], "kind": r["kind"],
             "metric": r["metric"], "mean": r["mean"], "min": r["min"], "max": r["max"], "n": r["n"]}   # q() renders timestamps as ISO strings
            for r in hourly]
    alerts_ = q("SELECT ts, rule_id, level, text FROM alerts WHERE ts >= %s::date AND ts < %s::date + 1 ORDER BY ts", day, day)
    with db() as con, con.cursor() as cur:
        cells_ = index.cells(cur); rho_ = index.rho(cur)
    _pos = _published_position()
    return {"schema": EXPORT_V0,
            "node": NODE, "city": os.getenv("NODE_CITY", ""), "scale": os.getenv("NODE_SCALE", "community"),
            # The cell's centre, never a point: this file is CC BY and meant to travel (R25, 23 Sep 2026).
            "lat": _pos["lat"], "lon": _pos["lon"],
            "day": day, "generated": datetime.now(timezone.utc).isoformat(), "version": os.getenv("NODE_VERSION", ""),
            "licence": "CC BY 4.0", "hourly": rows,
            "alerts": [{"t": a["ts"], "rule": a["rule_id"], "level": a["level"], "text": a["text"].split("\n")[0]} for a in alerts_],
            "cells": cells_, "rho": rho_}


@app.get("/place/geojson")
def place_geojson(kinds: str = "building,poi,green,road,sat", tolerance: float = Query(0.00002, ge=0.000001, le=0.01)):
    """The geometry the place pack stored: OpenStreetMap buildings, uses, green, roads, and the satellite's buildings
    (`sat`), as one GeoJSON FeatureCollection for the dashboard's plan. Simplified so a kilometre is a few hundred KB.
    Empty until the place pack has run; never an error.

    **On no SHARE_LEVEL allowlist, at any level: this machine or a token, and nothing else.** It is the exact building
    footprints and roads within PLACE_RADIUS_M of the address — the doorway A12 is about, drawn — and unlike a
    rounded coordinate there is no version of it that is safe to hand to the network. The dashboard's plan card is
    therefore empty on an unauthenticated screen and says so.

    `tolerance` carries bounds (F11): at 0 the query skipped ST_SimplifyPreserveTopology entirely and returned the
    unsimplified kilometre against a docstring promising a few hundred KB. The dashboard never passes it (:960)."""
    want = {k.strip() for k in kinds.split(",") if k.strip()}
    feats: list = []
    diag: dict = {"tables": {}, "rows": {}}
    try:
        with db() as con, con.cursor() as cur:
            one = lambda: next(iter(cur.fetchone().values()))        # rows are dicts in this app; take the single column  # noqa: E731
            for t in ("place_features", "place_buildings_sat", "place_runs"):
                cur.execute(f"SELECT to_regclass('{t}') IS NOT NULL AS ok"); diag["tables"][t] = bool(one())
                if diag["tables"][t]:
                    cur.execute(f"SELECT count(*) AS n FROM {t}"); diag["rows"][t] = one()
            if diag["tables"]["place_features"] and want - {"sat"}:
                cur.execute("""SELECT kind, category, name, tags->>'building' AS btype, tags->>'highway' AS hw,
                                      ST_AsGeoJSON(ST_SimplifyPreserveTopology(geom, %s), 6) AS g
                               FROM place_features WHERE kind = ANY(%s)""", (tolerance, list(want - {"sat"})))
                for r in cur.fetchall():
                    feats.append({"type": "Feature", "properties": {"kind": r["kind"], "category": r["category"], "name": r["name"], "building": r["btype"], "highway": r["hw"]}, "geometry": json.loads(r["g"])})
            if diag["tables"]["place_buildings_sat"] and "sat" in want:
                # only the satellite footprints with no mapped building within 3 m: the gap, drawn
                cur.execute("""SELECT ST_AsGeoJSON(ST_SimplifyPreserveTopology(s.geom, %s), 6) AS g, s.confidence FROM place_buildings_sat s
                               WHERE s.source='open_buildings_v3' AND NOT EXISTS (
                                 SELECT 1 FROM place_features f WHERE f.kind='building' AND ST_DWithin(f.geom, s.geom, 0.00003))""", (tolerance,))   # geometry: uses the GiST index
                for r in cur.fetchall():
                    feats.append({"type": "Feature", "properties": {"kind": "sat", "confidence": r["confidence"]}, "geometry": json.loads(r["g"])})
    except Exception as e:  # noqa: BLE001
        log.warning("place/geojson: %s", e)
        diag["error"] = f"{type(e).__name__}: {str(e)[:200]}"
    if not feats:
        diag["hint"] = ("the place pack has not stored anything yet: enable it (PACKS_ALLOW_CODE=1, planetai packs install, planetai restart) and let it poll, or planetai run place refresh"
                        if not diag["rows"].get("place_features") else "features exist but none matched; see error")
    return {"type": "FeatureCollection", "features": feats, "diag": diag,
            "center": [float(os.getenv("NODE_LON", 0) or 0), float(os.getenv("NODE_LAT", 0) or 0)],
            "radius_m": int(settings.get("PLACE_RADIUS_M", "1000") or 1000)}


def _earth_dir() -> Path:
    """The directory holding this node's AlphaEarth square.

    The pack names it for the node, but the embeddings describe a *place*, so the name is not the key: after
    node #1 was renamed `bayu-2` → `bayu-ungasan` there were two directories of the same square and the
    older one had stopped being readable by anything. A directory whose meta.json says it was read around
    this point, at this radius, answers for this node whatever it is called — the node's own name preferred
    when more than one does. `packs/earth/adapter.py:cache()` carries the same rule, because core does not
    import a pack; `app/sources.py:metres()` is already the second copy of the distance for the same reason.
    """
    root = OUT / "earth"
    mine = root / NODE
    lat, lon = os.getenv("NODE_LAT"), os.getenv("NODE_LON")
    if not (root.is_dir() and lat and lon):
        return mine
    radius = int(settings.get("EARTH_RADIUS_M", "5000") or 5000)
    tol = max(radius * 0.01, 25.0)          # the pack's move tolerance: 1% of the radius, floor 25 m
    for p in sorted(root.glob("*/meta.json"), key=lambda q: (q.parent != mine, q.parent.name)):
        try:
            m = json.loads(p.read_text())
            if m.get("radius_m") in (None, radius) and \
                    sources.metres(float(m["lat"]), float(m["lon"]), float(lat), float(lon)) <= tol:
                return p.parent
        except (OSError, ValueError, TypeError, KeyError):
            continue
    return mine


def _earth_changes() -> list[dict]:
    """Every comparison the earth pack computed here, oldest pair first. Small: about a kilobyte each, and a
    node has at most eight of them."""
    d = _earth_dir()
    if not d.is_dir():
        return []
    out = []
    for f in sorted(d.glob("change_*.json")):
        try:
            out.append(json.loads(f.read_text()))
        except Exception as e:  # noqa: BLE001
            log.warning("earth: %s is not readable json (%s)", f.name, e)
    return sorted(out, key=lambda c: (c.get("year_b", 0), c.get("year_a", 0)))


def _earth_latest() -> dict | None:
    """The newest comparison, preferring a year-over-year pair over a longer span."""
    out = _earth_changes()
    if not out:
        return None
    yoy = [c for c in out if c.get("year_b", 0) - c.get("year_a", 0) == 1]
    return (yoy or out)[-1]


# ---------------------------------------------------------------- the map workbench
# The redesign's Place door pans, zooms, inspects and measures. Every ring it draws and every distance it prints is
# answered here (app/issues/geometry.py), so the page computes no H3 and no distance: tools/check_ui.py holds it to
# that. **On no SHARE_LEVEL allowlist, like /place/geojson**: the node's cell at a fine resolution, rings centred on
# it and "metres from the node" each give away the point /health rounds on purpose. This machine or a token.


def _here() -> tuple[float, float]:
    lat, lon = float(os.getenv("NODE_LAT", 0) or 0), float(os.getenv("NODE_LON", 0) or 0)
    if not (lat or lon):
        raise HTTPException(409, "this node has no NODE_LAT and NODE_LON yet, so there is no place to draw")
    return lat, lon


def _floats(text: str, n: int | None, what: str) -> list[float]:
    try:
        out = [float(x) for x in text.split(",")]
    except ValueError:
        raise HTTPException(422, f"{what}: numbers separated by commas") from None
    if n is not None and len(out) != n:
        raise HTTPException(422, f"{what}: {n} numbers")
    return out


@app.get("/geo/grid")
def geo_grid(bbox: str, res: int = Query(..., ge=0, le=15)):
    """The cells covering `bbox` (west,south,east,north) at `res`, one ring wider, and the node's own cell at that
    resolution, as `cells_ll` rows ([id, lat, lng, …]). 422 rather than a truncated covering when the box is too big."""
    lat, lon = _here()
    try:
        return _geo.grid(*_floats(bbox, 4, "bbox"), res, lat, lon)
    except ValueError as e:
        raise HTTPException(422, str(e)) from None


@app.get("/geo/cell")
def geo_cell(id: str | None = None, lat: float | None = Query(None, ge=-90, le=90),
             lon: float | None = Query(None, ge=-180, le=180), res: int | None = Query(None, ge=0, le=15),
             children: int | None = Query(None, ge=1, le=15), polar: bool = False):
    """One cell's facts, named by `id` or by `lat`, `lon` and `res`: area, edge, parent, and how many cells from the
    node's own at the same resolution. `children=<res>` adds how many children it has there and, up to 400, their
    rings; `polar=true` adds every ring as distance and bearing from the node."""
    here = _here()
    if id is None:
        if lat is None or lon is None or res is None:
            raise HTTPException(422, "name a cell: id, or lat, lon and res")
        import h3
        id = h3.latlng_to_cell(lat, lon, res)
    try:
        return _geo.cell(id, *here, children=children, as_polar=polar)
    except ValueError as e:
        raise HTTPException(422, str(e)) from None


@app.get("/geo/measure")
def geo_measure(path: str, from_node: bool = False, each: bool = False):
    """Metres along `path`, lon,lat pairs separated by `;`, great-circle, each leg and the total. `from_node=true`
    starts the path at the node, which is how the inspector says how far a station is. `each=true` adds, for every
    point after the first, its distance and bearing from the first, in one answer."""
    pts = [tuple(_floats(p, 2, "each point")) for p in path.split(";") if p.strip()]
    if from_node:
        lat, lon = _here()
        pts = [(lon, lat)] + pts
    if not 2 <= len(pts) <= 200 or any(not (-180 <= x <= 180 and -90 <= y <= 90) for x, y in pts):
        raise HTTPException(422, "path: 2 to 200 lon,lat points in degrees")
    return {**_geo.measure(pts), **({"each": _geo.each(pts)} if each else {})}


@app.get("/geo/planet")
def geo_planet(res: int = Query(2, ge=0, le=2)):
    """Every H3 cell on the planet at resolution 0, 1 or 2, as cells_ll rows: the world grid a map of nodes is drawn
    on, so the page computes none of it."""
    _here()
    return {"res": res, "cells_ll": _geo.planet(res)}


@app.get("/geo/rings")
def geo_rings(km: str = "2,5,15"):
    """Circles round the node at each distance in `km`, as [lat, lng] rings. At most eight, none past 500 km."""
    kms = _floats(km, None, "km")
    if not 1 <= len(kms) <= 8 or any(not 0 < k <= 500 for k in kms):
        raise HTTPException(422, "km: one to eight distances, each above 0 and at most 500")
    return {"rings": _geo.rings(*_here(), kms)}


# ---------------------------------------------------------------- the ground, kept on this node's disk
# `planetai run place basemap` (vector, fonts, drone mosaics) and `planetai run earth-engine basemap` (Sentinel-2)
# fetch a detailed map of this place once into out/ground/; these routes serve it, so a map drawn from them asks
# nobody anything. Private like /place/geojson: a tile pyramid centred on the node says where it is.
GROUND_LAYERS = {"vector": "application/x-protobuf", "imagery": "image/png", "drone": "image/png"}


def _ground() -> Path:
    return OUT / "ground"


@app.get("/machine")
def machine():
    """The machine this node runs on, as the node's container sees it: processor, load, memory, temperature, how long
    it has been up, its system, and the database engine. Read from /proc and /sys, so on Linux (a Pi, a mini PC) it is
    the machine; on macOS it is the container engine's virtual machine, and says so in `seen_as`. A value the system
    does not give (no thermal sensor, no cgroup limit) is null, never a guess. Private like /storage."""
    import platform, time as _t
    def read(p):
        try:
            return Path(p).read_text()
        except OSError:
            return None
    mem = {}
    for line in (read("/proc/meminfo") or "").splitlines():
        k, _, v = line.partition(":")
        if k in ("MemTotal", "MemAvailable", "SwapTotal", "SwapFree") and v.split():
            mem[k] = int(v.split()[0]) * 1024
    def cpu_times():
        f = (read("/proc/stat") or "").splitlines()
        nums = [int(x) for x in f[0].split()[1:]] if f and f[0].startswith("cpu ") else []
        return (sum(nums), nums[3] + (nums[4] if len(nums) > 4 else 0)) if nums else None
    a = cpu_times(); _t.sleep(0.25); b = cpu_times()
    busy = round(100 * (1 - (b[1] - a[1]) / (b[0] - a[0])), 1) if a and b and b[0] > a[0] else None
    temps = []
    for z in sorted(Path("/sys/class/thermal").glob("thermal_zone*")):
        t = read(z / "temp")
        if t and t.strip().lstrip("-").isdigit():
            temps.append({"zone": (read(z / "type") or z.name).strip(), "celsius": round(int(t) / 1000, 1)})
    up = read("/proc/uptime")
    cg_max, cg_cur = read("/sys/fs/cgroup/memory.max"), read("/sys/fs/cgroup/memory.current")
    with db() as con, con.cursor() as cur:
        cur.execute("SELECT split_part(version(), ' on ', 1) AS v, pg_postmaster_start_time() AS since,"
                    " (SELECT count(*) FROM pg_stat_activity) AS conns")
        pg = cur.fetchone()
    return {
        "seen_as": "the Linux system the node's containers run on: the machine itself on Linux, the container engine's virtual machine on macOS",
        "arch": platform.machine(), "system": f"{platform.system()} {platform.release()}", "cores": os.cpu_count(),
        "load": [float(x) for x in (read("/proc/loadavg") or "").split()[:3]] or None, "cpu_busy_pct": busy,
        "memory": {"total_bytes": mem.get("MemTotal"), "available_bytes": mem.get("MemAvailable"),
                   "swap_total_bytes": mem.get("SwapTotal"), "swap_free_bytes": mem.get("SwapFree")},
        "container_memory": {"limit_bytes": int(cg_max) if cg_max and cg_max.strip().isdigit() else None,
                             "used_bytes": int(cg_cur) if cg_cur and cg_cur.strip().isdigit() else None},
        "temperatures": temps, "uptime_s": round(float(up.split()[0])) if up else None,
        "python": platform.python_version(),
        "database": {"version": pg["v"], "since": pg["since"].isoformat() if pg["since"] else None, "connections": pg["conns"]},
    }


@app.get("/storage")
def storage():
    """How much room this node takes, how much is left, and how long that lasts at the rate it has been growing.

    The node computes it so no page has to: the database's own size (Postgres), the files it keeps beside it (out/,
    the backups, the open exports), and the free space on the disk those files live on, as this container sees it.
    The rate is the readings written in the last seven days times what a reading row costs on disk, indexes and all,
    which is where nearly all of the growth is; nothing is ever pruned. The backups are counted as they will be once
    BACKUP_KEEP days of dumps sit there. `days_left` is null when the rate is zero or not yet known.

    The database's own disk is the container engine's: on Linux it is this disk unless DATA_DIR moves it; on macOS
    it is the engine's virtual disk, which this container cannot see. `planetai doctor` checks the host's.
    Private like /version: what the machine holds is the keeper's, not the network's."""
    import shutil
    def du(p: Path) -> int:
        try:
            return sum(f.stat().st_size for f in p.rglob("*") if f.is_file())
        except OSError:
            return 0
    with db() as con, con.cursor() as cur:
        cur.execute("SELECT pg_database_size(current_database()) AS db, pg_total_relation_size('readings') AS r,"
                    " (SELECT reltuples FROM pg_class WHERE relname = 'readings') AS n,"
                    " (SELECT count(*) FROM readings WHERE ts > now() - interval '7 days') AS week")
        row = cur.fetchone()
    per_row = (row["r"] / row["n"]) if row["n"] and row["n"] > 0 else None
    per_day = round(per_row * row["week"] / 7) if per_row else None
    backups = Path("/app/backups")
    dumps = sorted(backups.glob("*.sql.gz"), key=lambda f: f.stat().st_mtime) if backups.exists() else []
    keep = int(os.getenv("BACKUP_KEEP", "30") or 30)
    b_now = sum(f.stat().st_size for f in dumps)
    b_full = (dumps[-1].stat().st_size * keep) if dumps else 0
    disk = shutil.disk_usage(OUT) if OUT.exists() else None
    free = disk.free if disk else None
    room = (free - max(0, b_full - b_now)) if free is not None else None
    return {
        "database_bytes": row["db"], "readings": int(row["n"] or 0), "readings_last_7_days": row["week"],
        "bytes_per_reading": round(per_row) if per_row else None, "growth_bytes_per_day": per_day,
        "out_bytes": du(OUT), "exports_bytes": du(Path("/app/exports")),
        "backups": {"bytes": b_now, "dumps": len(dumps), "keep_days": keep, "bytes_when_full": b_full},
        "disk": ({"path": str(OUT), "total_bytes": disk.total, "used_bytes": disk.used, "free_bytes": disk.free} if disk else None),
        "days_left": (int(room / per_day) if room is not None and per_day else None),
        "rate": "readings written in the last 7 days x bytes per reading row; backups counted at BACKUP_KEEP dumps",
    }


@app.get("/ground/meta")
def ground_meta():
    """What the node holds of its own map: each layer's source, licence, attribution, tile count, bytes and when it
    was fetched, from out/ground/meta.json, and which layers are actually on disk. Never an error."""
    g = _ground()
    try:
        meta = json.loads((g / "meta.json").read_text())
    except (OSError, ValueError):
        meta = {}
    have = {k: (g / f"{k}.mbtiles").is_file() for k in GROUND_LAYERS}
    have["glyphs"] = (g / "glyphs").is_dir()
    have["wind"] = (g / "wind.json").is_file()
    return {"layers": meta, "on_disk": have,
            "fetch": {"vector": "planetai run place basemap --only vector", "drone": "planetai run place basemap --only drone",
                      "imagery": "planetai run earth-engine basemap", "wind": "planetai run forecast windfield"}}


@app.get("/ground/wind")
def ground_wind():
    """The wind over the node's square for a map to draw moving: the forecast pack's Open-Meteo field, n×n points,
    hourly for the next day (out/ground/wind.json, refreshed on each forecast poll). 204 when the node has none,
    which is every node with FORECAST_OPENMETEO=0."""
    from fastapi.responses import Response
    p = _ground() / "wind.json"
    if not p.is_file():
        return Response(status_code=204)
    return Response(p.read_bytes(), media_type="application/json", headers={"cache-control": "no-cache"})


@app.get("/ground/glyphs/{font}/{span}")
def ground_glyphs(font: str, span: str):
    """The label fonts the vector map draws names with, as MapLibre asks for them: one face, one range of 256."""
    from fastapi.responses import Response
    if not re.fullmatch(r"[A-Za-z ]{1,40}", font) or not re.fullmatch(r"\d{1,5}-\d{1,5}\.pbf", span):
        raise HTTPException(404, "no such glyphs")
    p = _ground() / "glyphs" / font / span
    if not p.is_file():
        return Response(status_code=204)
    return Response(p.read_bytes(), media_type="application/x-protobuf", headers={"cache-control": "max-age=86400"})


@app.get("/ground/{layer}/{z}/{x}/{y}")
def ground_tile(layer: str, z: int, x: int, y: str):
    """One tile of the node's own map, XYZ addressed (`y` may carry .pbf, .png or .jpg). 204 where the node holds
    none, which a map reads as empty ground rather than an error."""
    from fastapi.responses import Response
    import sqlite3
    if layer not in GROUND_LAYERS:
        raise HTTPException(404, "no such ground layer")
    try:
        yy = int(y.split(".")[0])
    except ValueError:
        raise HTTPException(422, "y must be a number") from None
    p = _ground() / f"{layer}.mbtiles"
    if not p.is_file() or not (0 <= z <= 22 and 0 <= x < 2 ** z and 0 <= yy < 2 ** z):
        return Response(status_code=204)
    con = sqlite3.connect(f"file:{p}?mode=ro", uri=True)
    try:
        row = con.execute("SELECT tile_data FROM tiles WHERE zoom_level=? AND tile_column=? AND tile_row=?",
                          (z, x, (1 << z) - 1 - yy)).fetchone()
    finally:
        con.close()
    if not row:
        return Response(status_code=204)
    data, head = row[0], {"cache-control": "max-age=3600"}
    if data[:2] == b"\x1f\x8b":
        head["content-encoding"] = "gzip"               # vector tiles are kept gzipped, as Protomaps ships them
    kind = GROUND_LAYERS[layer] if layer == "vector" else ("image/jpeg" if data[:2] == b"\xff\xd8" else "image/png")
    return Response(data, media_type=kind, headers=head)


@app.get("/earth")
def earth():
    """What the earth pack has: the years of AlphaEarth embeddings cached for this node's square, and the
    latest year-over-year comparison it computed from them. Empty until `planetai run earth fetch`; never an
    error, so the dashboard card can say what is missing instead of showing a blank box."""
    d = _earth_dir()
    years = sorted(int(p.stem) for p in d.glob("*.npy") if p.stem.isdigit()) if d.is_dir() else []
    size = sum(p.stat().st_size for p in d.glob("*")) if d.is_dir() else 0
    frames = sorted(int(f.stem[5:]) for f in d.glob("year_*.png") if f.stem[5:].isdigit()) if d.is_dir() else []
    changes = _earth_changes()
    latest = _earth_latest()
    enabled = "earth" in [m.get("id") for m in packs.manifests()]
    for c in changes:                       # so a NAS, or anything else, can fetch each map without guessing
        c["png_url"] = f"/earth/change.png?pair={c['year_a']}_{c['year_b']}"
    # The other record, if the earth-engine pack has ever run: real imagery, brightness-matched,
    # `partial` wherever it is drawn. Named separately from `frames` because they are different
    # things and a page that merges them is telling a reader a model output is a photograph.
    sentinel = sorted(_sentinel_frames("sentinel"))
    landsat = sorted(_sentinel_frames("landsat"))
    body = {"node": NODE, "enabled": enabled, "years": years, "bytes": size, "latest": latest,
            "changes": changes, "frames": frames, "dir": str(d),
            "imagery": {"sentinel": sentinel, "landsat": landsat,
                        "credit": ["Contains modified Copernicus Sentinel data, processed by "
                                   "Google Earth Engine.",
                                   "Landsat courtesy of the U.S. Geological Survey."]},
            "png": "/earth/change.png" if latest and (d / str(latest.get("png", ""))).is_file() else None,
            "lat": float(os.getenv("NODE_LAT", 0) or 0), "lon": float(os.getenv("NODE_LON", 0) or 0),
            "radius_m": int(settings.get("EARTH_RADIUS_M", "5000") or 5000),
            "attribution": "The AlphaEarth Foundations Satellite Embedding dataset is produced by Google and "
                           "Google DeepMind. CC BY 4.0."}
    if not enabled:
        body["hint"] = "the earth pack is not loaded; see docs/PACKS.md"
    elif not years:
        body["hint"] = "no satellite record yet: planetai run earth fetch"
    elif not latest:
        body["hint"] = f"{len(years)} year(s) cached, nothing compared yet: planetai run earth change"
    elif not frames:
        body["hint"] = f"{len(years)} year(s) cached; for the year-by-year pictures: planetai run earth frames"
    return body


@app.get("/earth/change.png")
def earth_change_png(pair: str = Query("", pattern=r"^(\d{4}_\d{4})?$")):
    """A land-change map the earth pack drew: the latest, or `?pair=2023_2025`. The file name always comes
    from the pack's own JSON, never from the request — the pair only chooses among the comparisons this node
    actually computed — and only a .png inside this node's own earth directory is served."""
    from fastapi.responses import FileResponse
    want = _earth_latest() if not pair else next(
        (c for c in _earth_changes() if f"{c.get('year_a')}_{c.get('year_b')}" == pair), None)
    name = Path(str((want or {}).get("png", ""))).name
    p = _earth_dir() / name
    if not (name.endswith(".png") and p.is_file()):
        raise HTTPException(404, "no such land-change map: planetai run earth change")
    return FileResponse(p, media_type="image/png", filename=name)


@app.get("/earth/year.png")
def earth_year_png(year: int = Query(..., ge=1900, le=2200)):
    """One year of the square as the earth pack drew it. The year is an integer and the name is built here,
    so nothing from the request reaches the filesystem as a path."""
    from fastapi.responses import FileResponse
    p = _earth_dir() / f"year_{year}.png"
    if not p.is_file():
        raise HTTPException(404, f"no frame for {year}: planetai run earth frames")
    return FileResponse(p, media_type="image/png", filename=p.name)


def _sentinel_frames(source: str = "sentinel") -> dict[int, Path]:
    """The frames `planetai run earth-engine timelapse` left in out/, by year.

    Matched by glob and not by name. The pack writes `<node>-<year>-<source>-<km>km.png`, and the
    node name in that filename is whatever the node was called the day the pack ran — on node #1 the
    files say `bayu-2` and NODE_NAME has since become `bayu-ungasan`, so building the name from NODE
    finds nothing. The km changes with the pack's own settings too. The year is the only part of the
    name this node can be sure of.
    """
    out = {}
    for f in sorted(OUT.glob(f"*-[0-9][0-9][0-9][0-9]-{source}-*.png")):
        try:
            out[int(f.stem.split("-")[-3])] = f
        except (ValueError, IndexError):        # a file that merely looks like one of ours
            continue
    return out


@app.get("/earth/frame.png")
def earth_frame_png(year: int = Query(..., ge=1972, le=2200),
                    source: str = Query("sentinel", pattern=r"^(sentinel|landsat)$")):
    """One year from the *other* satellite record: real imagery, brightness-matched across the years.

    This is not what /earth/year.png serves. That one is this node's own AlphaEarth layer — a model's
    64-number description of every 10 m pixel, flattened to one number and drawn in grey, never a
    photograph. These are Sentinel-2 (or Landsat) annual medians fetched through Earth Engine, so
    they are `partial`: somebody else's cluster made them, and they carry their own credit line.

    Both are on the Land band and on the wall, and the page must never let a reader take one for the
    other. Neither the year nor the source reaches the filesystem as a path: the year is an integer
    in range, the source is one of two words, and the file itself comes from a glob of out/.
    """
    from fastapi.responses import FileResponse
    have = _sentinel_frames(source)
    p = have.get(year)
    if not p:
        raise HTTPException(404, f"no {source} frame for {year}"
                                 + (f"; this node has {sorted(have)}" if have
                                    else ": planetai run earth-engine timelapse"))
    return FileResponse(p, media_type="image/png", filename=p.name)


@app.get("/report/latest")
def report_latest():
    """The last report this node wrote, sent or held. What the dashboard's Here band shows, and what the MCP tool
    `report_latest` returns. Open, like /alerts: it is the same sentences the household already received."""
    # by ts, not by due_local: a report written on request has no due hour, and ordering by that hid it here and
    # in `planetai report last` — the button said "sent" and the page went on showing the one before it.
    rows = q("""SELECT id, ts, due_local, window_hours, depth, rung, text, sent, held_quiet, fallback_reason
                  FROM reports ORDER BY ts DESC LIMIT 1""")
    # One shape, whether or not a report exists. Until v0.63 the empty case answered five keys and the
    # populated case answered ten, so a client that read `sent` had to know which case it was in — the
    # exact implicitness this release is about. Every key is present and null when there is no report,
    # and `note` is added rather than substituted.
    r = rows[0] if rows else {}
    out = {"schema": REPORT_V0,
           "id": r.get("id"), "ts": r.get("ts"), "due_local": r.get("due_local"),
           "window_hours": r.get("window_hours"), "depth": r.get("depth"), "rung": r.get("rung"),
           "text": r.get("text"), "sent": r.get("sent"), "held_quiet": r.get("held_quiet"),
           "fallback_reason": r.get("fallback_reason"),
           # in the literal, None when there is a report: a key added by subscript is a key of the
           # document that does not appear in it, which tools/check_wire.py refuses for the same
           # reason it refuses `**`.
           "note": None if rows else "no report yet; the first one lands at the next due hour"}
    return out


@app.get("/report/bundle")
def report_bundle(hours: int = Query(0, ge=0, le=168), authorization: str = Header("")):
    """Every number the node has about a window, as one document — what a report is written from. Behind the
    read-only token: this is more of the household's own data in one place than any other endpoint returns."""
    _pull_ok(authorization)
    with db() as con, con.cursor() as cur:
        return report.bundle(cur, hours or _report_every())


@app.post("/report/now")
def report_now(authorization: str = Header("")):
    """Write and send a report immediately, whatever the hour. `planetai report` and /report in Telegram call this.
    It does not take the scheduled hour's place: no `due_local`, so the next due report still happens."""
    _admin(authorization)
    with db() as con, con.cursor() as cur:
        every = _report_every()
        b = report.bundle(cur, every)
        text = report.sheet(b, LOCALE())
        cur.execute("""INSERT INTO reports (window_hours, depth, rung, text, sheet, sent, held_quiet, cells)
                       VALUES (%s, 'sheet', 'node', %s, %s, TRUE, FALSE, %s) RETURNING id""",
                    (every, text, text, Jsonb(b.get("cells") or [])))
        rid = cur.fetchone()["id"]
    notify("info", text)
    ha_alert("info", text, None)
    log.info("report %d sent on request: %d hours, %d words", rid, every, len(text.split()))
    return {"id": rid, "text": text, "depth": "sheet", "rung": "node", "sent": True}


@app.get("/briefing", include_in_schema=False)
def briefing_moved(kind: str = "morning"):
    """Gone in v0.38. A dashboard left open in a browser through the update still asks for this; answer it with
    where the report lives now rather than a 404 in a screen nobody is looking at."""
    from fastapi.responses import RedirectResponse
    return RedirectResponse("/report/latest", status_code=301)


@app.get("/history")
def history(sensor_id: str, metric: str, limit: int = Query(500, ge=1, le=5000)):
    """Every reading of one metric from one sensor, oldest first. For series that are not hourly: a yearly building count,
    a monthly refresh. `/sparks` is the hourly view; this is the raw one."""
    return [{"ts": r["ts"], "value": r["value"]} for r in            # q() already renders timestamps as ISO strings
            q("SELECT ts, value FROM readings WHERE sensor_id=%s AND metric=%s ORDER BY ts LIMIT %s", sensor_id, metric, limit)]


@app.get("/sparks")
def sparks(metric: str = "pm25", hours: int = Query(24, ge=1, le=168)):
    """Per-sensor hourly means, aligned to the same buckets, for small traces inside the dashboard's sensor tiles."""
    rows = q("""
        WITH h AS (SELECT generate_series(date_trunc('hour', now()) - make_interval(hours => %s - 1), date_trunc('hour', now()), interval '1 hour') AS bucket),
        ids AS (SELECT DISTINCT sensor_id FROM readings_1h WHERE metric = %s AND bucket > now() - make_interval(hours => %s))
        SELECT ids.sensor_id, h.bucket, r.mean
        FROM ids CROSS JOIN h LEFT JOIN readings_1h r ON r.sensor_id = ids.sensor_id AND r.bucket = h.bucket AND r.metric = %s
        ORDER BY ids.sensor_id, h.bucket""", hours, metric, hours, metric)
    # The buckets travel with the values. Without them a trace cannot draw its own time axis or say which hour
    # the reader is hovering over, and the dashboard was guessing the hours from the array's length.
    out: dict = {}
    hours: list = []
    seen = set()
    for x in rows:
        out.setdefault(x["sensor_id"], []).append(x["mean"])
        b = str(x["bucket"])
        if b not in seen:
            seen.add(b); hours.append(b)
    return {"hours": hours, "series": out}


# ---------------------------------------------------------------- backups and exports, for a machine that pulls them
BACKUPS = Path("/app/backups")
EXPORTS = Path("/app/exports")
OUT = Path(os.getenv("PACK_OUT", "/app/out"))      # the one writable mount; packs put their artifacts here


# ---------------------------------------------------------------- wire formats
# ARCHITECTURE.md §3 names the contracts that must not change casually. One of them was versioned
# (`fci-cells-v0`) and the rest were implicit: the nightly export is pinned to IPFS forever with a
# licence and no schema version, GET /issues is the one document a client draws, and the two pushes
# travel between nodes on different releases. Four nodes exist. The cost of saying which is a string.
ISSUES_V0, EXPORT_V0, AGGREGATES_V0, EVENTS_V0, REPORT_V0 = (
    "issues-v0", "export-v0", "aggregates-v0", "events-v0", "report-v0")

_wire_said: set = set()


def _wire_in(body: dict, expect: str) -> str:
    """What a received document says it is. Logged once per (format, value); never refused.

    A RECEIVER NEVER REFUSES ON THIS, and that is the rule the whole change rests on. A parent one
    release behind has to keep accepting a child one release ahead, or an operator updating their own
    node silently stops the district's numbers. So an unknown version is processed for the fields this
    node recognises and the rest are dropped — which is exactly what `receive_events` already did for
    unknown columns, and this only makes it say so. A document with no `schema` predates the key and
    is read as `-v0`, which is what it is.

    The log is once per distinct value and the set is capped, because the value comes off the wire
    from a child and an unbounded set keyed on a stranger's string is a slow leak.
    """
    said = ((body.get("schema") or "") if isinstance(body, dict) else "")
    said = said.strip()[:40] if isinstance(said, str) else "<not a string>"
    key = (expect, said)
    if key not in _wire_said and len(_wire_said) < 64:
        _wire_said.add(key)
        if not said:
            log.info("%s: a push arrived with no schema key; reading it as %s (legacy)", expect, expect)
        elif said != expect:
            log.info("%s: a push says schema=%r, which this node does not know; reading the fields it "
                     "recognises and dropping the rest", expect, said)
    return said or expect


def _bearer_ok(authorization: str, *tokens: str) -> bool:
    """True when the Authorization header carries one of `tokens`. Compared in constant time: `!=` returns at the first
    differing byte, which lets a caller on the LAN measure its way to a token one character at a time."""
    given = authorization.replace("Bearer ", "", 1).strip().encode()
    ok = False
    for t in tokens:
        if t and secrets.compare_digest(given, t.encode()):
            ok = True          # no early return: the time taken must not say which token matched
    return ok


def _pull_ok(authorization: str) -> None:
    """A read-only token for whoever collects backups (a NAS), separate from the admin token. Either works."""
    tokens = [t for t in (os.getenv("ADMIN_TOKEN", "").strip(), settings.get("BACKUP_TOKEN", "").strip()) if t]
    if not tokens:
        raise HTTPException(403, "no BACKUP_TOKEN or ADMIN_TOKEN set on this node")
    if not _bearer_ok(authorization, *tokens):
        raise HTTPException(401, "bad or missing token")


@app.get("/settings/raw")
def settings_raw(authorization: str = Header("")):
    """Runtime settings unmasked, for the node's own processes (the agent loop reads its model ladder here every minute,
    so the dashboard's Model page changes it live). Admin token required; never call this from a browser."""
    _admin(authorization)       # not _pull_ok: the NAS's read-only BACKUP_TOKEN must not unmask the Telegram token and the AI keys
    return {k: settings.get(k, "") for k in settings.RUNTIME}


@app.get("/backups")
def list_backups(authorization: str = Header("")):
    """Dumps this node has made, newest first, so a NAS can fetch the ones it lacks. Token required."""
    _pull_ok(authorization)
    if not BACKUPS.exists():
        return []
    files = sorted(BACKUPS.glob("*.sql.gz"), key=lambda p: p.stat().st_mtime, reverse=True)
    return [{"name": p.name, "bytes": p.stat().st_size, "mtime": datetime.fromtimestamp(p.stat().st_mtime, timezone.utc).isoformat()} for p in files]


@app.get("/backups/{name}")
def get_backup(name: str, authorization: str = Header("")):
    _pull_ok(authorization)
    from fastapi.responses import FileResponse
    p = BACKUPS / Path(name).name           # no path components, ever
    if not (p.exists() and p.suffix == ".gz" and p.name.endswith(".sql.gz")):
        raise HTTPException(404, "no such backup")
    return FileResponse(p, media_type="application/gzip", filename=p.name)


@app.get("/exports")
def list_exports():
    """The daily open-data exports. Public: they are CC BY 4.0 and contain nothing raw or secret."""
    if not EXPORTS.exists():
        return []
    return [{"node": p.parent.name, "name": p.name, "bytes": p.stat().st_size}
            for p in sorted(EXPORTS.glob("*/*.json"), key=lambda p: p.name, reverse=True)]


@app.get("/exports/{node}/{name}")
def get_export(node: str, name: str):
    from fastapi.responses import FileResponse
    p = EXPORTS / Path(node).name / Path(name).name
    if not (p.exists() and p.suffix == ".json"):
        raise HTTPException(404, "no such export")
    return FileResponse(p, media_type="application/json", filename=p.name)


# ---------------------------------------------------------------- the GUI and its settings
STATIC = Path(__file__).parent / "static"


@app.get("/", include_in_schema=False)
@app.get("/ui", include_in_schema=False)
def ui(layout: str = ""):
    """The dashboard: one HTML file, no build step, reads the same API everything else does. SINGAPORE NODE: the
    classic dashboard is the default here, because the Singapore wall, the NEA columns and the alert buttons live in
    it only; upstream serves the five doors layout (doors.html, docs/decisions/2026-10-07-doors.md) by default, and
    this branch keeps it at `?layout=doors`. The same shell route either way, so the same share rule, and both read
    the same routes with the same token.

    Sent with `cache-control: no-cache`. Without any cache header a browser is free to reuse this document for as
    long as it likes, and an ordinary reload does not always ask: after `planetai update` a screen kept running the
    previous dashboard, with the previous bugs, until someone thought to hard-reload. The node's whole update story
    depends on the page following the version."""
    from fastapi.responses import HTMLResponse
    f = STATIC / ("doors.html" if layout == "doors" else "index.html")   # singapore-node: classic is the default
    body = f.read_text() if f.exists() else "<h1>planetai-node</h1><p>GUI not shipped in this build.</p>"
    return HTMLResponse(body, headers={"cache-control": "no-cache, must-revalidate"})


# What this machine is for, in the words of docs/site/introduction.md; tools/check_site.py holds this, the
# dashboard's foot and the programme page to that one lead. /llms.txt is the door an agent handed this node's
# address knows to try first. It answers at every SHARE_LEVEL because it says nothing about the house: the
# purpose, the version, and where the documented routes are. Before v0.73 the node served no such file and
# `llms.txt` existed only on GitHub, so an agent pointed at a node found nothing to read.
PURPOSE = ("PLANETAI is hyperlocal compute and intelligence for distributed production. Its purpose is "
           "fixed: clean air, water and soil for the people and the other living things around each node.")
DOCS_URL = "https://planetai.fab.city/docs/"


@app.get("/llms.txt", include_in_schema=False)
def llms_txt():
    from fastapi.responses import PlainTextResponse
    v = os.getenv("NODE_VERSION", "?")
    body = f"""# planetai-node {v}

> {PURPOSE} Raw readings stay on this machine; only summaries leave.

This is one PLANETAI node. Every route below is relative to the address you reached this file at.

## Read it

- [GET /health](/health): alive or not, the version, the node's H3 cell (resolution 8), and the share level. Answers at every level.
- [GET /issues](/issues): the node's own reading of its place, one document, every sentence written by the node.
- [GET /export](/export): the daily open export, hourly means and the Index cells, CC BY 4.0.
- [GET /sources](/sources): the pinned source registry this node reads from.

What answers without a token depends on SHARE_LEVEL, which the household sets. A 403 names the setting.

## Work with it

- POST /mcp: the node's twenty tools over MCP (streamable HTTP). Needs `Authorization: Bearer <ADMIN_TOKEN>`,
  which `planetai ui` prints on the machine itself. Every write an agent makes is recorded under its name, and
  `act` needs the person's own words: an agent may draft, a person acts.

## Read about it

- Documentation: {DOCS_URL} (HTTP API: {DOCS_URL}api/ · MCP tools: {DOCS_URL}mcp/ · agents: {DOCS_URL}agents/)
- For agents working on the code: https://raw.githubusercontent.com/fabcity/planetai-node/main/AGENTS.md
- The programme: https://planetai.fab.city/
"""
    return PlainTextResponse(body, headers={"cache-control": "no-cache"})


# The two files index.html cannot hold. The dashboard is still one HTML document with no build step: the
# ground is an SVG whose own `:root` block would leak its paper variables into the page if it were inlined,
# and the mono is a font. Named one by one rather than served from a directory — this port is open to a
# household LAN, and a path parameter that reaches the filesystem is the usual way that ends badly.
COMPANIONS = {
    "node-ground.svg": (STATIC / "node-ground.svg", "image/svg+xml"),
    "jetbrains-mono-latin.woff2": (STATIC / "fonts" / "jetbrains-mono-latin.woff2", "font/woff2"),
    # Funnel Sans and Figtree, self-hosted for the same reason as the mono: a node serves this page
    # on a LAN that may have no route out, so a webfont from a CDN is a page with no typography.
    # Shipped as the variable .ttf the design system bundles — converting to woff2 would halve
    # 177 kB on a local network and cost a build step, which this repo does not have. SIL OFL 1.1;
    # the licences are beside the files in app/static/fonts/.
    "FunnelSans-VariableFont_wght.ttf": (STATIC / "fonts" / "FunnelSans-VariableFont_wght.ttf", "font/ttf"),
    "Figtree-VariableFont_wght.ttf": (STATIC / "fonts" / "Figtree-VariableFont_wght.ttf", "font/ttf"),
    "Figtree-Italic-VariableFont_wght.ttf": (STATIC / "fonts" / "Figtree-Italic-VariableFont_wght.ttf", "font/ttf"),
    # The renderer: a skeleton, its script, its layout, and the frozen layer it draws with. The
    # three .css files are copied from planetai-design and never edited here; tools/check_theme.py
    # holds them to the sibling repo. Flat names on purpose — this route takes a name, not a path,
    # because a path parameter that reaches the filesystem is the usual way a port open to a
    # household LAN ends badly. That is also why the mono stays at /static/jetbrains-mono-latin.woff2
    # rather than the fonts/ subdirectory planetai-theme.css names; check_theme knows about that one
    # line and reports it rather than failing on it.
    "dashboard.js": (STATIC / "dashboard.js", "application/javascript"),
    "dashboard.css": (STATIC / "dashboard.css", "text/css"),
    # The drawing library (docs/SPEC_dashboard_figures.md §4.1): Observable Plot and the d3 it is built on, vendored
    # for the same reason as the fonts. ISC; the licences are in app/static/licences/. data/vendor.sha256 pins both.
    "d3.min.js": (STATIC / "d3.min.js", "application/javascript"),
    "plot.umd.min.js": (STATIC / "plot.umd.min.js", "application/javascript"),
    "planetai-theme.css": (STATIC / "planetai-theme.css", "text/css"),
    "tokens.css": (STATIC / "tokens.css", "text/css"),
    "signs.svg": (STATIC / "signs.svg", "image/svg+xml"),
    "kilometre-cells.json": (STATIC / "kilometre-cells.json", "application/json"),
    # The wall's faded land outline: a public coastline (geoBoundaries, CC BY 4.0), not the household's own place.
    "coast-outline.json": (STATIC / "coast-outline.json", "application/json"),
    "wall-layers.json": (STATIC / "wall-layers.json", "application/json"),
    # The learn layer: the marks cut out of docs/site by tools/build_learn.py at build
    # time, because a node does not carry the documentation site. Fetched only when a reader
    # turns learn mode on, and the quotes are inline so the mode works on a LAN with no route out.
    "learn.json": (STATIC / "learn.json", "application/json"),
    # The map ground, UI_GROUND=map: MapLibre for the base, deck.gl for the cells and stations over it.
    # Pinned UMD builds, vendored so the page needs no CDN; fetched only when the ground is drawn that way.
    # Versions and licences are in NOTICE.
    "maplibre-gl.js": (STATIC / "vendor" / "maplibre-gl.js", "application/javascript"),
    "maplibre-gl.css": (STATIC / "vendor" / "maplibre-gl.css", "text/css"),
    "deck.gl.min.js": (STATIC / "vendor" / "deck.gl.min.js", "application/javascript"),
    # The five doors (/?layout=doors): the loader that builds their one object from the routes, then one file per door,
    # as planetai-design's prototype kept them. Natural Earth's coast for the Node door's world (NOTICE).
    **{f"doors-{n}.js": (STATIC / f"doors-{n}.js", "application/javascript")
       for n in ("load", "nodegeo", "core", "fig", "now", "placemap", "place", "data", "flow", "wallmap", "wall", "node", "setup")},
    "world-land-110m.json": (STATIC / "vendor" / "world-land-110m.json", "application/json"),
    # The documentation the node carries (`make learn` cuts it out of docs/site): the Data door draws the API from it.
    # ./data is mounted at /app/data in the container and sits beside app/ in a checkout, as ask.py reads it.
    "docs_site.json": (next((p for p in (STATIC.parent / "data" / "docs_site.json", STATIC.parent.parent / "data" / "docs_site.json")
                             if p.exists()), STATIC.parent / "data" / "docs_site.json"), "application/json"),
}
NO_CACHE = {"cache-control": "no-cache, must-revalidate"}


@app.get("/static/{name}", include_in_schema=False)
def static_file(name: str, variant: str = "dark"):
    """The dashboard's ground and its data face.

    Same `no-cache, must-revalidate` as index.html, and for the same reason: a wall screen that keeps the
    previous design after `planetai update` is the bug that header exists to stop, and a stale ground is that
    bug again. FileResponse sends an ETag, so revalidating costs a 304 and nothing on the wire.

    The ground is drawn here from NODE_LAT / NODE_LON rather than served from disk, so it is this
    node's own cell and the caption naming that cell is true. The file on disk is what a node with
    no coordinates yet gets: node #1's cell, with no caption, standing in for a place the node has
    not been told about.

    `?variant=` is the page saying which register it is in. The ground is an `<img>` — deliberately,
    see COMPANIONS above — so it is a document of its own and no CSS on the page can reach into it;
    asking for the register in the URL is the only way it can follow one. Without the parameter it
    is the dark register, which is what every caller got before this existed.

    The value is coerced to one of two literals rather than validated, because it is interpolated
    into `data-variant="..."` inside the SVG: anything that is not "paper" is "dark", so nothing a
    caller invents can reach the markup."""
    from fastapi.responses import FileResponse, Response
    if name == "node-ground.svg":
        svg = _ground_svg("paper" if variant == "paper" else "dark")
        if svg:
            return Response(svg, media_type="image/svg+xml", headers=NO_CACHE)
    hit = COMPANIONS.get(name)
    if not hit or not hit[0].exists():
        raise HTTPException(404, "no such asset")
    return FileResponse(hit[0], media_type=hit[1], headers=NO_CACHE)


def _ground_svg(variant: str = "dark") -> str | None:
    """This node's ground, or None to fall back to the file on disk: before setup there are no
    coordinates to draw, and an image built before h3 was a dependency has no h3. Neither is a
    reason to serve an empty hero.

    The shipped file is drawn in the dark register, so a node with no coordinates yet would put the
    lifted blue #7FA5E8 on the paper hero, where it measures 2.29:1 — the one thing the layer's
    guards say may never happen. Its <style> carries both registers and the root attribute picks
    one, so for paper the attribute is swapped and the text served. Dark still returns None and is
    served by FileResponse with its ETag, which is the common case."""
    lat, lon = os.getenv("NODE_LAT", ""), os.getenv("NODE_LON", "")
    if lat and lon:
        try:
            return ground.svg(float(lat), float(lon), variant)
        except Exception as e:  # noqa: BLE001
            log.warning("node-ground: %s: %s — serving the shipped file", type(e).__name__, e)
    if variant == "dark":
        return None
    shipped = STATIC / "node-ground.svg"
    if not shipped.exists():
        return None
    return shipped.read_text().replace('data-variant="dark"', f'data-variant="{variant}"', 1)


def _admin(authorization: str) -> None:
    tok = os.getenv("ADMIN_TOKEN", "").strip()
    if not tok:
        raise HTTPException(403, "ADMIN_TOKEN is not set in .env; run `planetai ui` to create one")
    if not _bearer_ok(authorization, tok):
        raise HTTPException(401, "bad or missing admin token")


@app.get("/settings")
def get_settings(request: Request, authorization: str = Header("")):
    """Every runtime setting with its group, help and current value, plus bootstrap keys read-only. Secrets are always
    masked. Without the admin token, so is everything that is the household's rather than the node's (chat ids, sensor
    hosts, account names, remote URLs; see settings.PUBLIC). A wrong token reads as no token: the dashboard's layout
    read must keep working for every screen in the house.

    At SHARE_LEVEL=off a caller that is neither on this machine nor carrying a token sees the value of UI_LAYOUT and
    SHARE_LEVEL only. The layout because of the promise in the paragraph above; SHARE_LEVEL because a screen that is
    being refused everything else needs to be able to name what is refusing it. Every other row is still there,
    masked, so the dashboard's Set up view still renders and still says what would be unlocked."""
    tok = os.getenv("ADMIN_TOKEN", "").strip()
    unlocked = bool(tok) and _bearer_ok(authorization, tok)
    reduced = not unlocked and not getattr(request.state, "share_trusted", False) and SHARE_LEVEL() == "off"
    return settings.describe(unlocked=unlocked, public={"UI_LAYOUT", "SHARE_LEVEL"} if reduced else settings.PUBLIC)


@app.put("/settings")
def put_settings(body: dict, authorization: str = Header(""), x_agent: str = Header("")):
    """Change runtime settings. {"KEY": "value", ...}. Blank returns a key to its .env value. Effective within ~20 s."""
    _admin(authorization)
    changed = []
    for k, v in body.items():
        if not settings.writable(k):       # RUNTIME, or a key an installed pack declares
            raise HTTPException(400, f"{k} is not a runtime setting, and no installed pack declares it")
        try:
            settings.set(k, str(v).strip())
        except ValueError as e:            # a key with a fixed set of values says so; a 500 would read as the node's fault
            raise HTTPException(400, str(e)) from None
        changed.append(k)
    who = x_agent or "gui"
    log.info("settings changed by %s: %s", who, ", ".join(changed))
    with db() as con, con.cursor() as cur:
        cur.execute("INSERT INTO actions (alert_id, stage, actor, note) VALUES (NULL, 'settings', %s, %s)", (who, ", ".join(changed)))
    return {"changed": changed, "by": who, "effective_within_s": settings.TTL}


@app.post("/test-alert")
def test_alert(authorization: str = Header("")):
    """Fire one act-level alert now, through every configured channel. Same as `planetai test-alert`."""
    _admin(authorization)
    es = LOCALE() == "es"
    text = ("🔔 Una prueba de tu nodo.\n\nSi lees esto, todo el camino funciona: una regla se disparó, el nodo escribió un mensaje y te llegó aquí. Los avisos reales se verán así: qué pasa, qué significa y qué hacer."
            if es else
            "🔔 A test from your node.\n\nIf you can read this, the whole path works: a rule fired, the node wrote a message, and it reached you here. Real alerts will look like this, with what is happening, what it means, and what to do.")
    with db() as con, con.cursor() as cur:
        cur.execute("INSERT INTO alerts (ts, rule_id, sensor_id, level, text) VALUES (now(), 'gui/test', 'node', 'act', %s) RETURNING id", (text,))
        alert_id = cur.fetchone()["id"]
    how = act_hint(alert_id)
    if es:
        closing = f"👉 Responde {how} para mostrarme cómo cierras el círculo." if how.startswith("/") else f"👉 En la terminal, {how} registra que cerraste el círculo."
    else:
        closing = f"👉 Reply {how} to show me how you close the loop." if how.startswith("/") else f"👉 In the terminal, {how} records that you closed the loop."
    notify("act", f"{text}\n\n{closing}")      # the hint already carries the number; a bare #id on the end taught nothing
    ha_alert("act", text, alert_id)
    return {"ok": True, "alert_id": alert_id}


# ---- Index contract (fci-cells-v0) and ρ ------------------------------------------------------
@app.get("/cells")
def cells():
    """Index cells this node can honestly compute. Same row shape as the FCI Observations base."""
    with db() as con, con.cursor() as cur:
        return index.cells(cur)


@app.get("/sources")
def sources_(pillar: str = "", scale: str = "", pilot: str = "", cell: str = "",
             wired: bool | None = None, status: str = ""):
    """The network's registry of what can be measured, as this node carries it (app/registry.py).

    `/cells` says what this node computes. This says what the network has registered — including for
    the cells no adapter fills yet, which have no `/cells` row at all. `?cell=Social|City` is the
    query the 5 September report did by hand.

    `?status=live` (or candidate, stale, deprecated, paywalled, planned) narrows to the registry's
    own word for what a source is. `counts` is the same three numbers per cell that a `/cells` row
    carries, for every cell rather than only the ones this node computes: capable is live with an
    adapter, reviewed is live backed by an adapter or a usable review, candidate is verified and
    unread. Nothing deprecated, stale, paywalled or planned is in any of them.

    Not to be confused with `app/sources.py`, which is the node's own sensor adapters. This serves
    rows somebody filed upstream; that reads instruments."""
    entries, ver = registry.load()
    if not entries:
        raise HTTPException(503, f"no source registry on this node: {registry.SOURCES_DIR} is empty or "
                                 "unmounted. Vendor one with tools/sync_registry.sh <sha> and rebuild.")
    rows = registry.find(pillar=pillar, scale=scale, pilot=pilot, cell=cell, wired=wired, status=status)
    return {"registry": {k: ver.get(k) for k in ("sha", "short", "synced", "entries")},
            "counts": registry.cell_counts(), "count": len(rows), "sources": rows}


@app.get("/sources/{pillar}/{scale}/{slug}")
def source_(pillar: str, scale: str, slug: str):
    e = registry.one(f"{pillar}/{scale}/{slug}")
    if not e:
        raise HTTPException(404, f"{pillar}/{scale}/{slug} is not in the registry this node carries "
                                 f"({registry.load()[1].get('short', 'none')}). Ask /sources for the list.")
    return e


@app.get("/packs")
def packs_():
    """What this node has loaded beyond the core. data packs are rules/cells only; code packs run Python."""
    return packs.manifests()


@app.get("/rho")
def rho():
    with db() as con, con.cursor() as cur:
        return index.rho(cur)


@app.post("/actions")
def action(body: dict, request: Request, authorization: str = Header("")):
    """A human closes the loop: {"alert_id": 12, "stage": "acted", "actor": "ibu wayan", "note": "closed windows"}.
    An event's button is {"event_id": 3, "stage": "dismissed", …}: acted, acknowledged or dismissed (Done, Not now, Doesn't fit).
    A mobile app, a Telegram reply handler, or curl — all the same call.

    F10: unchanged and open on this machine, so the MCP `act` tool and a shell in the container keep working with no
    token. From anywhere else it needs ACT_TOKEN or ADMIN_TOKEN — the weaker token on purpose, so someone in the
    house can be given the ability to close a loop without being given the key to /settings/raw. `planetai ui` prints
    both. Note this holds at SHARE_LEVEL=off too: `off` refuses this path in the middleware for a caller with no
    token at all, but BACKUP_TOKEN gets past that gate, and a read-only NAS token must not be able to write rho.

    Deliberately no one-action-per-alert cap: two people who both acted are both recording something true."""
    if not _is_local(request):
        tokens = [t for t in (ACT_TOKEN(), os.getenv("ADMIN_TOKEN", "").strip()) if t]
        if not tokens:
            raise HTTPException(403, "no ACT_TOKEN or ADMIN_TOKEN set on this node; run `planetai ui` to create one")
        if not _bearer_ok(authorization, *tokens):
            raise HTTPException(401, "closing a loop from off this machine needs Authorization: Bearer <ACT_TOKEN>")
    if body.get("event_id") is not None:
        # An event's buttons (docs/SPEC_dashboard_events.md §3.2): the same tokens, the same refusals, one row.
        if body.get("alert_id") is not None:
            raise HTTPException(400, "send alert_id or event_id, not both")
        with db() as con, con.cursor() as cur:
            try:
                events_pg.answer(cur, body["event_id"], body.get("stage"), body.get("actor"), body.get("note"))
            except ValueError as e:
                raise HTTPException(400, str(e)) from None
            except LookupError as e:
                raise HTTPException(404, str(e)) from None
        return {"ok": True}
    stage = body.get("stage")
    # `decided` is a record and not an answer: it closes nothing, enters no rho, and is not a funnel stage. A household
    # that looked at an observation, decided what to do and did not manage it leaves the same trace today as one that
    # never looked, and those are opposite facts. docs/SPEC_decide.md section 6.
    if stage not in ("acknowledged", "acted", "decided"):  # 'settings' rows are written by the node itself, never posted
        raise HTTPException(400, "stage must be acknowledged, acted or decided")
    with db() as con, con.cursor() as cur:
        cur.execute("SELECT 1 FROM alerts WHERE id = %s", (body.get("alert_id"),))
        if not cur.fetchone():
            raise HTTPException(404, "no such alert")
        # DECISION_REQUIRED is a community's switch and it is off by default, because the four other ways in here have
        # no screen to decide on: the Reticulum bridge (a LoRa reply from a device with no display), the MCP `act` tool,
        # the terminal, and curl. A node in a house records an act whether or not anybody deliberated -- somebody smells
        # smoke and opens a window -- and refusing that would make the node assert a deliberation that did not happen,
        # or push the act somewhere it is never recorded at all. A node acting for a street is the case this is for.
        if stage == "acted" and settings.num("DECISION_REQUIRED", 0):
            cur.execute("SELECT 1 FROM actions WHERE alert_id = %s AND stage = 'decided' LIMIT 1", (body.get("alert_id"),))
            if not cur.fetchone():
                raise HTTPException(409, "this node is set to DECISION_REQUIRED, so an act needs a decision recorded "
                                         "against the same alert first. Decide on the dashboard, then record what you did.")
        cur.execute("INSERT INTO actions (alert_id, stage, actor, note) VALUES (%s,%s,%s,%s)",
                    (body.get("alert_id"), stage, str(body.get("actor") or "")[:80], str(body.get("note") or "")[:500]))
    return {"ok": True}


@app.post("/readings")
def post_readings(body: dict, authorization: str = Header("")):
    """Downstream contributors (a phone, a DIY pod on the LAN) post raw readings. Admin token required: a posted
    reading becomes a *local, indoor* sensor whose values fire act-level alerts and enter live cells, so anyone on the
    WiFi could otherwise wake the household with 999 µg/m³ from a curl (found on the clean node, 6 Sep 2026).
    {"sensor": {"sensor_id": "phone-abc", "source": "mobile", "name": "...", "lat":..,"lon":.., "indoor": false},
     "readings": [{"ts": "...", "metric": "<name>", "value": 12.3}, ...]}   The sensor is local by definition."""
    _admin(authorization)
    s = body.get("sensor") or {}
    if not s.get("sensor_id"):
        raise HTTPException(422, "sensor.sensor_id is required")
    with db() as con, con.cursor() as cur:
        cur.execute("""INSERT INTO sensors (sensor_id, source, name, lat, lon, indoor, local, meta)
                       VALUES (%s,%s,%s,%s,%s,%s,TRUE,%s) ON CONFLICT (sensor_id) DO UPDATE SET lat=EXCLUDED.lat, lon=EXCLUDED.lon, indoor=EXCLUDED.indoor""",
                    (s["sensor_id"], s.get("source", "contributor"), s.get("name", s["sensor_id"]), s.get("lat"), s.get("lon"),
                     bool(s.get("indoor", False)), Jsonb(s.get("meta") or {})))
        cur.executemany("INSERT INTO readings (ts, sensor_id, metric, value) VALUES (%s,%s,%s,%s) ON CONFLICT DO NOTHING",
                        [(r.get("ts") or datetime.now(timezone.utc), s["sensor_id"], r["metric"], float(r["value"])) for r in body.get("readings", [])])
    return {"accepted": len(body.get("readings", []))}


@app.post("/events")
def receive_events(body: dict, authorization: str = Header("")):
    """Parent side. A child pushes one row per alert it raised, as timestamps: detect, decide, deploy, measure.
    The parent computes rho over its own alerts and these together (app/index.py::rho).

    Anything not in the column list is dropped on the floor here rather than stored and forgotten — a child on
    a newer version that starts sending `text` must not be able to put a household's sentence in this table.
    """
    if not AGG_TOKEN():
        raise HTTPException(403, "this node accepts no children: set AGGREGATE_TOKEN in .env and give it to them")
    if not _bearer_ok(authorization, AGG_TOKEN()):
        raise HTTPException(401, "bad or missing Authorization: Bearer <AGGREGATE_TOKEN>")
    _wire_in(body, EVENTS_V0)
    rows, child = body.get("rows", []), body.get("node", "?")
    scale = body.get("scale", "community")
    kept = 0
    with db() as con, con.cursor() as cur:
        for r in rows:
            if not r.get("alert_id") or not r.get("raised_at"):
                continue                      # a row with no identity or no detect time cannot measure latency
            cur.execute("""INSERT INTO events (child, alert_id, rule, level, kind, scale, raised_at,
                                               responded_at, acted_at, measured_at)
                           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                           ON CONFLICT (child, alert_id) DO UPDATE SET
                             rule=EXCLUDED.rule, level=EXCLUDED.level, kind=EXCLUDED.kind, scale=EXCLUDED.scale,
                             responded_at=EXCLUDED.responded_at, acted_at=EXCLUDED.acted_at,
                             measured_at=EXCLUDED.measured_at, received_at=now()""",
                        (child, str(r["alert_id"]), r.get("rule"), r.get("level"), r.get("kind"), scale,
                         r["raised_at"], r.get("responded_at"), r.get("acted_at"), r.get("measured_at")))
            kept += 1
    return {"accepted": kept}


@app.get("/aggregates")
def aggregates(hours: int = Query(24, ge=1, le=24 * 90)):   # ge: hours=-1 made make_interval walk forwards and the window empty
    return q("SELECT bucket, sensor_id, metric, mean, min, max, n FROM readings_1h WHERE bucket > now() - make_interval(hours => %s) ORDER BY bucket DESC", hours)


@app.post("/aggregates")
def receive_aggregates(body: dict, authorization: str = Header("")):
    """Parent side. Children push hourly means, stored as readings under the child's namespaced sensor ids.
    Raw readings never travel this path.

    The metric keeps its own name. Until v0.50 it arrived as '<metric>_1h', and no pack SQL anywhere matched
    `pm25_1h` — the cadence had been encoded in the join key, so a parent's Environmental|Community cell found
    nothing to average even once custody let the children in. The cadence has a column and this function
    already writes it: `sensors.cadence = 'PT1H'`, three lines down. A consumer that needs to know these are
    means reads it there, beside `kind` and `local`.

    `readings.ts` is the child's own bucket, so an hourly mean enters as one reading on the hour and the
    parent's `readings_1h` view averages a single row back to itself. The child's hour survives unchanged, and
    `readings`' UNIQUE (sensor_id, metric, ts) keeps a re-push idempotent."""
    if not AGG_TOKEN():
        raise HTTPException(403, "this node accepts no children: set AGGREGATE_TOKEN in .env and give it to them")
    if not _bearer_ok(authorization, AGG_TOKEN()):
        raise HTTPException(401, "bad or missing Authorization: Bearer <AGGREGATE_TOKEN>")
    _wire_in(body, AGGREGATES_V0)
    rows = body.get("rows", [])
    child = body.get("node", "?")
    with db() as con, con.cursor() as cur:
        for r in rows:
            sid = f"{child}/{r['sensor_id']}"
            cur.execute("""INSERT INTO sensors (sensor_id, source, name, local, kind, scale, cadence)
                           VALUES (%s,'child',%s,FALSE,'child',%s,'PT1H')
                           ON CONFLICT (sensor_id) DO UPDATE SET kind='child', scale=EXCLUDED.scale""",
                        (sid, sid, body.get("scale", "community")))
            cur.execute("INSERT INTO readings (ts, sensor_id, metric, value) VALUES (%s,%s,%s,%s) ON CONFLICT DO NOTHING",
                        (r["bucket"], sid, r["metric"], float(r["mean"])))
    return {"accepted": len(rows)}
