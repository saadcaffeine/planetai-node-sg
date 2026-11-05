"""Sources. Each adapter is a function that returns (sensors, readings).

    sensors : list of dicts  {sensor_id, source, name, lat, lon, indoor, local, meta,
                              kind:  sensor | portal | model | survey   (how the number was produced)
                              scale: community | city | region | bioregion | planet (what it describes)
                              cadence: ISO-8601 duration, optional}
              kind and scale default to sensor/community — set them on anything that isn't a device at the address.
    readings: list of tuples (ts: datetime UTC, sensor_id, metric, value)

That's the whole contract. Add a source = add a function here + register it in SOURCES.
Core ships the global models and open portals. A vendor's device comes as a pack, on the LAN (packs/airgradient,
packs/purpleair) or through its cloud (packs/smartcitizen), and so does a network of public stations
(packs/bali-air-dispatch).
See docs/sensors.md to add another.
"""
from __future__ import annotations

import math
import os
from datetime import datetime, timedelta, timezone

import httpx

import settings

# ---------------------------------------------------------------- helpers

def _iso(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


def km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p = math.pi / 180
    a = 0.5 - math.cos((lat2 - lat1) * p) / 2 + math.cos(lat1 * p) * math.cos(lat2 * p) * (1 - math.cos((lon2 - lon1) * p)) / 2
    return 12742 * math.asin(math.sqrt(a))


# ---------------------------------------------------------------- is this sensor at this node?
# `packs/place/adapter.py` has its own metres(); core must not import from a pack, so this is the second copy.
# Equirectangular: within a metre of haversine at a kilometre, about nine metres at eight, and cheap. Measured on
# node #1's own four sensors. Exact enough for a radius that is a judgement call anyway.
def metres(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    dy = (lat2 - lat1) * 111_320.0
    dx = (lon2 - lon1) * 111_320.0 * math.cos(math.radians((lat1 + lat2) / 2))
    return math.hypot(dx, dy)


def stamp_local(sensors: list[dict], lat: float, lon: float, radius_m: float) -> list[dict]:
    """`local` is ours AND here. The adapter decides ours; distance decides here.

    Only ever narrows: a sensor an adapter did not claim never becomes local, whatever its coordinates. A public
    reference station across the street is not the node's own measurement. A sensor with no coordinates that an
    adapter claims (a Meshtastic pod reaching us over our own gateway) stays local, because we cannot measure a
    distance we do not have and the radio itself is the evidence. If the node itself has no coordinates yet
    (unset or half-configured), leave every claim alone rather than narrow the whole fleet to nothing."""
    if lat is None or lon is None:
        return sensors
    for s in sensors:
        if not s.get("local"):
            continue
        if s.get("lat") is None or s.get("lon") is None:
            continue
        s["local"] = metres(lat, lon, float(s["lat"]), float(s["lon"])) <= radius_m
    return sensors


# ---------------------------------------------------------------- Smart Citizen
# The cloud fetch is packs/smartcitizen since 22 Oct 2026. This stays: which kits in an account are this node's own,
# which packs/bali-air-dispatch and packs/nearby ask too.
def smartcitizen_account(hc: httpx.Client, user: str, max_age_days: int = 3, exclude: set[int] | None = None) -> list[int]:
    """The kits in a Smart Citizen account that have published recently. They are yours: every one is local, indoor
    or outdoor from the API's `exposure` field. Distance never decides ownership — an outdoor kit up the road is your
    outdoor sensor, not a public reference. SC_EXCLUDE drops kits that belong to another site."""
    r = hc.get(f"https://api.smartcitizen.me/v0/users/{user}")
    r.raise_for_status()
    cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)
    return [int(d["id"]) for d in r.json().get("devices") or []
            if d.get("state") == "has_published" and (_iso(d.get("last_reading_at")) or cutoff) > cutoff
            and int(d["id"]) not in (exclude or set())]


# ---------------------------------------------------------------- registry
def enabled(hc: httpx.Client):
    """Yield (name, fetch) for every configured source. Failures are per-source, never fatal.
    Core adapters first, then any from packs, core and wild (docs/PACKS.md)."""
    out = []
    if settings.get("OPENMETEO_ENABLED", "1") == "1" and os.getenv("NODE_LAT"):
        _lat, _lon = float(os.environ["NODE_LAT"]), float(os.environ["NODE_LON"])
        out.append(("open-meteo", lambda: openmeteo(hc, _lat, _lon)))
    portals = dict(p.split("=", 1) for p in settings.get("CKAN_PORTALS", "").split(",") if "=" in p)
    if portals:
        out.append(("ckan", lambda: ckan(hc, portals, settings.get("CKAN_SCALE", "city"))))
    try:
        import packs
        out += packs.adapters(hc)
    except Exception as e:  # noqa: BLE001  — a broken pack must never stop the core sources
        import logging; logging.getLogger("planetai").warning("packs: %s", e)
    return out


# ---------------------------------------------------------------- Open-Meteo (planet/bioregion context, anywhere)
# Free, key-free, global. A point sample of a global model — boundary conditions, not a measurement of your place.
# Per ARCHITECTURE §2, bioregion and planet publish context *downward*; they are never rolled up into an index cell.
# Set OPENMETEO_ENABLED=1. Works at any coordinates on earth, which is the point: this is the one adapter that
# needs nothing local at all, so a node in a city with no sensors still has something true to say.
OM_CURRENT = "temperature_2m,relative_humidity_2m,precipitation,wind_speed_10m,wind_direction_10m,surface_pressure"
OM_MAP = {"temperature_2m": "temp_model", "relative_humidity_2m": "humidity_model", "precipitation": "precipitation",
          "wind_speed_10m": "wind_speed", "wind_direction_10m": "wind_direction", "surface_pressure": "pressure_model"}


def openmeteo(hc: httpx.Client, lat: float, lon: float):
    r = hc.get("https://api.open-meteo.com/v1/forecast",
               params={"latitude": round(lat, 3), "longitude": round(lon, 3), "current": OM_CURRENT, "timezone": "UTC"})
    r.raise_for_status()
    d = r.json()
    cur = d.get("current") or {}
    ts = _iso(cur.get("time") + "Z" if cur.get("time") and not str(cur.get("time")).endswith("Z") else cur.get("time")) or datetime.now(timezone.utc)
    sid = "om-point"
    sensors = [{"sensor_id": sid, "source": "open-meteo", "name": "Open-Meteo (model point sample)",
                "lat": lat, "lon": lon, "indoor": False, "local": False, "kind": "model", "scale": "planet",
                "cadence": "PT1H", "meta": {"model": "ECMWF/GFS blend via open-meteo.com", "licence": "CC-BY 4.0",
                                            "note": "boundary condition; never aggregated upward into a cell"}}]
    readings = [(ts, sid, m, float(cur[k])) for k, m in OM_MAP.items() if cur.get(k) is not None]
    return sensors, readings


# ---------------------------------------------------------------- CKAN open-data portal (city/region governance)
# Four of the Index's governance|city sources are CKAN: Open Data BCN, Analyze Boston, datos.gob.cl, Bali Satu Data.
# One adapter reads all of them, and asks the question the Index actually needs answered about a portal:
# is it alive? Datasets published, and how many were updated in the last 90 days. That is a DIDO signal —
# a portal nobody maintains is not open data, it is an archive.
# Set CKAN_PORTALS=open-data-bcn=https://opendata-ajuntament.barcelona.cat/data,analyze-boston=https://data.boston.gov
def ckan(hc: httpx.Client, portals: dict[str, str], scale: str = "city"):
    from datetime import timedelta
    sensors, readings = [], []
    now = datetime.now(timezone.utc)
    cutoff = (now - timedelta(days=90)).strftime("%Y-%m-%dT%H:%M:%S")
    for slug, base in portals.items():
        base = base.rstrip("/")
        total = hc.get(f"{base}/api/3/action/package_search", params={"rows": 0}).json()["result"]["count"]
        fresh = hc.get(f"{base}/api/3/action/package_search",
                       params={"fq": f"metadata_modified:[{cutoff}Z TO NOW]", "rows": 0}).json()["result"]["count"]
        sid = f"ckan-{slug}"
        sensors.append({"sensor_id": sid, "source": "ckan", "name": f"{slug} (CKAN portal)", "lat": None, "lon": None,
                        "indoor": False, "local": False, "kind": "portal", "scale": scale, "cadence": "P1D",
                        "meta": {"portal": base, "registry_slug": f"governance/{scale}/{slug}"}})
        readings += [(now, sid, "datasets_total", float(total)),
                     (now, sid, "datasets_fresh_90d", float(fresh)),
                     (now, sid, "datasets_fresh_pct", 100.0 * fresh / total if total else 0.0)]
    return sensors, readings


# ---------------------------------------------------------------- Meshtastic (LoRa mesh, via the gateway's MQTT uplink)
# The gateway radio (an ESP32 with WiFi) uplinks the mesh to the node's Mosquitto. With "JSON output" enabled on the
# gateway, each packet arrives on   msh/<REGION>/2/json/<channel>/!<gateway>   as a JSON object with "type" and
# "payload". This is a pure function: one MQTT message in, sensors and readings out, so it is tested offline.
#   telemetry  -> readings (environment_metrics / air_quality_metrics / power fields flattened into payload)
#   position   -> the sensor's lat/lon (Tracker L1 boards carry GPS)
#   nodeinfo   -> the sensor's name
# Metric names follow the rest of the node; field names follow Meshtastic firmware 2.7.26, both as its own MQTT JSON
# writes them (MeshPacketSerializer.cpp) and as the host gateway snake-cases the protobuf. Keys are matched with their
# underscores taken out, because MessageToDict says rainfall1h where the firmware says rainfall_1h. If a future
# firmware renames a field the adapter logs the unknown key once rather than silently dropping it.
# Not filed, on purpose: an MLX90632 on a radio sends a surface's temperature as environment `temperature`, and the
# packet cannot say so; it would read as `temp`, which is already an enclosure reading never averaged as the street's
# (config/channels.yml). Do not fit an MLX90632 to a radio whose temperature matters. An MLX90614 sends its die
# temperature there and the object's in health_metrics, which the gateway does not uplink.
MESH_METRICS = {
    # environment_metrics
    "temperature": "temp", "relative_humidity": "humidity", "barometric_pressure": "pressure_hpa",
    "gas_resistance": "gas_resistance", "iaq": "iaq", "lux": "light", "white_lux": "white_light", "uv_lux": "uv_lux",
    "wind_speed": "wind_speed", "wind_direction": "wind_direction", "rainfall_1h": "rainfall_1h", "rainfall_24h": "rainfall_24h",
    "soil_moisture": "soil_moisture", "soil_temperature": "soil_temp",
    "distance": "distance", "weight": "weight", "radiation": "radiation",     # mm (RCWL-9620 water level), kg, µR/h
    "current": "current",                                                    # mA, an INA219/INA260 on the radio
    # air_quality_metrics (Plantower / SEN5x / HM3301 / SCD4x / SFA30), as the host gateway names them
    "pm10_standard": "pm1", "pm25_standard": "pm25", "pm40_standard": "pm4", "pm100_standard": "pm10",
    "pm10_environmental": "pm1_env", "pm25_environmental": "pm25_env", "pm100_environmental": "pm10_env",
    "co2": "co2", "pm_voc_idx": "tvoc_index", "pm_nox_idx": "nox_index", "form_formaldehyde": "hcho",   # hcho in ppb
    # ...and as the firmware's own MQTT JSON names them: its "pm10" is PM1.0 and its "pm100" is PM10
    "pm10": "pm1", "pm25": "pm25", "pm100": "pm10",
    # device health, useful for the dead-sensor rule and for battery planning
    "battery_level": "battery_pct", "voltage": "battery_v", "air_util_tx": "lora_util_pct", "channel_utilization": "lora_channel_pct",
}
# The same field in environment_metrics means something else: `voltage` there is an INA219/INA260's bus voltage, across
# whatever it is wired to (a panel, a pump line), not the radio's battery.
MESH_ENVIRONMENT = {"voltage": "voltage"}
_MESH_KEYS = {k.replace("_", ""): v for k, v in MESH_METRICS.items()}


def _mesh_metric(key: str, block: str):
    """The node's metric for one telemetry field of a `block` (device, environment, air_quality, power)."""
    return (block == "environment" and MESH_ENVIRONMENT.get(key)) or _MESH_KEYS.get(key.replace("_", ""))


_MESH_UNKNOWN: set = set()


def meshtastic_message(topic: str, payload: bytes, indoor_ids: set | None = None):
    """Parse one uplinked packet. Returns (sensors, readings, info) where info carries what the node needs to reply:
    the root topic and the gateway id, so alerts can go back down the same channel."""
    import json as _json
    import logging as _logging
    log = _logging.getLogger("planetai.meshtastic")
    parts = topic.split("/")
    if "json" not in parts:
        return [], [], {}            # protobuf topics: the gateway has JSON output off. planetai meshtastic says how to turn it on.
    j = parts.index("json")
    # msh/<REGION>/2/json/<channel>/!<gateway> : the "2" is the protocol version, not part of the root topic
    root = "/".join(parts[:j - 1]) if j >= 1 and parts[j - 1] == "2" else "/".join(parts[:j])
    channel, gateway = (parts[j + 1] if len(parts) > j + 1 else ""), (parts[j + 2] if len(parts) > j + 2 else "")
    try:
        m = _json.loads(payload)
    except Exception:  # noqa: BLE001
        return [], [], {}
    kind, p = m.get("type"), m.get("payload") or {}
    # `from` is the radio that sent the packet. The firmware's JSON sets `sender` to the GATEWAY that published it, so
    # reading `sender` filed every radio's readings under the gateway (node #1, 5 Sep to 19 Oct 2026).
    node = f"!{m['from']:08x}" if isinstance(m.get("from"), int) else m.get("sender")
    if not node:
        return [], [], {}
    sid = f"msh-{node.lstrip('!')}"
    ts = datetime.fromtimestamp(m["timestamp"], tz=timezone.utc) if isinstance(m.get("timestamp"), (int, float)) and m["timestamp"] > 1_600_000_000 else datetime.now(timezone.utc)
    indoor = bool(indoor_ids and (node in indoor_ids or sid in indoor_ids))
    # name None: only a nodeinfo names a radio. _store keeps the name it has and gives a new row default_name.
    sensor = {"sensor_id": sid, "source": "meshtastic", "name": None, "default_name": f"mesh {node}", "lat": None, "lon": None, "indoor": indoor, "local": True,
              "kind": "sensor", "scale": "community", "cadence": "PT15M",
              "meta": {"mesh_node": node, "gateway": gateway, "channel": channel, "root_topic": root}}
    readings = []
    if kind == "telemetry" and isinstance(p, dict):
        # battery_level 101 is Meshtastic's sentinel for "on external power, no battery"; the voltage that comes
        # with it is noise. A mains-powered gateway reports this every time. Drop both rather than store them.
        if isinstance(p.get("battery_level"), (int, float)) and p["battery_level"] > 100:
            p = {k: v for k, v in p.items() if k not in ("battery_level", "voltage")}
        # the host gateway names the block; the firmware's JSON does not, and its device block always carries
        # channel_utilization. Neither JSON puts `voltage` in an air-quality or power block.
        block = p.get("block") or ("device" if "channel_utilization" in p or "air_util_tx" in p else "environment")
        for k, v in p.items():
            if not isinstance(v, (int, float)):
                continue
            metric = _mesh_metric(k, block)
            if metric:
                if metric == "pressure_hpa":
                    readings.append((ts, sid, "pressure", float(v) / 10.0))   # hPa -> kPa, same unit as the rest of the node
                else:
                    readings.append((ts, sid, metric, float(v)))
            elif k not in _MESH_UNKNOWN:
                _MESH_UNKNOWN.add(k); log.info("meshtastic: unknown telemetry field %r (value %r) — add it to MESH_METRICS if it matters", k, v)
    elif kind == "position" and isinstance(p, dict):
        lat = p.get("latitude_i"); lon = p.get("longitude_i")
        if isinstance(lat, int) and isinstance(lon, int) and lat and lon:
            sensor["lat"], sensor["lon"] = lat / 1e7, lon / 1e7
        if p.get("altitude") is not None:
            readings.append((ts, sid, "altitude_m", float(p["altitude"])))
    elif kind == "nodeinfo" and isinstance(p, dict):
        sensor["name"] = p.get("longname") or p.get("shortname")
        sensor["meta"]["hardware"] = p.get("hardware")
    elif kind == "text":
        sensor["meta"]["last_text"] = str(p.get("text", ""))[:200] if isinstance(p, dict) else str(p)[:200]
        # "sender" in the gateway's JSON is the gateway that relayed the packet; "from" is the node that wrote it
        origin = f"!{m['from']:08x}" if isinstance(m.get("from"), int) else node
        text_msg = {"id": m.get("id"), "from": origin, "to": m.get("to"), "channel": channel, "gateway": gateway,
                    "ts": ts.isoformat(), "text": str(p.get("text", "") if isinstance(p, dict) else p)[:500]}
    else:
        return [], [], {"root_topic": root, "gateway": gateway}
    # a sensor row is only worth writing if it carries something new (name, position) or has readings
    if not readings and sensor["name"] is None and sensor["lat"] is None and kind != "text":
        return [], [], {"root_topic": root, "gateway": gateway}
    info = {"root_topic": root, "gateway": gateway, "channel": channel, "kind": kind, "node": node}
    if kind == "text":
        info["text"] = text_msg          # the node stores and forwards it (main.mesh_text); the dashboard only counts
    return [sensor], readings, info


def meshtastic_downlink(root_topic: str, gateway_node_num: int, text: str, channel: int = 0) -> tuple[str, bytes]:
    """The (topic, payload) to publish so the gateway transmits `text` on the mesh. Requires JSON output and
    downlink enabled on the gateway's channel. LoRa frames are small: ~200 bytes of text is the practical ceiling."""
    import json as _json
    text = text if len(text.encode()) <= 200 else text.encode()[:197].decode("utf-8", "ignore") + "..."
    return f"{root_topic}/2/json/mqtt/", _json.dumps({"from": gateway_node_num, "type": "sendtext", "payload": text, "channel": channel}).encode()
