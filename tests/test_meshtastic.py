"""Offline tests for the Meshtastic MQTT parser, against payload shapes as Meshtastic 2.x publishes them with
JSON output on. Run: PYTHONPATH=/tmp/stub:app python3 tests/test_meshtastic.py"""
import json
import sources

T = "msh/SG_923/2/json/LongFast/!a1b2c3d4"     # gateway !a1b2c3d4, region topic as Bali would set it
def pkt(kind, payload, sender="!deadbeef", ts=1756800000):
    return json.dumps({"channel": 0, "from": int(sender[1:], 16), "id": 1, "payload": payload,
                       "sender": sender, "timestamp": ts, "to": 4294967295, "type": kind}).encode()

# environment telemetry from a Tracker L1 + BME680
s, r, info = sources.meshtastic_message(T, pkt("telemetry", {"temperature": 29.4, "relative_humidity": 71.2, "barometric_pressure": 1008.3, "gas_resistance": 47658.0, "iaq": 52}))
m = {k: v for _, _, k, v in r}
assert s[0]["sensor_id"] == "msh-deadbeef" and s[0]["local"] and s[0]["kind"] == "sensor"
assert m["temp"] == 29.4 and m["humidity"] == 71.2 and abs(m["pressure"] - 100.83) < 0.01 and m["gas_resistance"] == 47658.0
assert info["root_topic"] == "msh/SG_923" and info["gateway"] == "!a1b2c3d4"

# air quality telemetry (HM3301 / SEN5x): standard fields map to the node's pm names
s, r, _ = sources.meshtastic_message(T, pkt("telemetry", {"pm10_standard": 4, "pm25_standard": 9, "pm100_standard": 11, "voltage": 3.98, "battery_level": 87}))
m = {k: v for _, _, k, v in r}
assert m["pm1"] == 4 and m["pm25"] == 9 and m["pm10"] == 11 and m["battery_pct"] == 87

# a USB-powered radio reports battery_level 101: a sentinel, not a percentage. Neither it nor its voltage is stored.
s, r, _ = sources.meshtastic_message(T, pkt("telemetry", {"battery_level": 101, "voltage": -0.001, "air_util_tx": 0.05}))
assert {k for _, _, k, _ in r} == {"lora_util_pct"}, "sentinel battery values must be dropped"

# position: GPS on the Tracker L1 places the sensor
s, r, _ = sources.meshtastic_message(T, pkt("position", {"latitude_i": -88004527, "longitude_i": 1151766378, "altitude": 42}))
assert abs(s[0]["lat"] - (-8.8004527)) < 1e-6 and abs(s[0]["lon"] - 115.1766378) < 1e-6
assert [x for x in r if x[2] == "altitude_m"][0][3] == 42.0

# nodeinfo names it
s, r, _ = sources.meshtastic_message(T, pkt("nodeinfo", {"id": "!deadbeef", "longname": "Subak edge", "shortname": "SBK", "hardware": 46}))
assert s[0]["name"] == "Subak edge" and s[0]["meta"]["hardware"] == 46 and r == []

# indoor flag by node id
s, _, _ = sources.meshtastic_message(T, pkt("telemetry", {"temperature": 30.0}), indoor_ids={"!deadbeef"})
assert s[0]["indoor"] is True

# text message: the parser hands the node the whole message (it stores and forwards; the sensor row keeps only 200 chars)
s, r, info = sources.meshtastic_message(T, json.dumps({"channel": 0, "from": 3735928559, "id": 77, "sender": "!deadbeef",
    "timestamp": 1756800000, "to": 4294967295, "type": "text", "payload": {"text": "anyone near Geylang?"}}).encode())
t = info["text"]
assert t["id"] == 77 and t["from"] == "!deadbeef" and t["text"] == "anyone near Geylang?" and t["gateway"] == "!a1b2c3d4"
# relayed through our gateway: the origin is "from", not "sender"
_, _, info = sources.meshtastic_message(T, json.dumps({"from": 2086328928, "id": 78, "sender": "!a1b2c3d4", "type": "text",
    "timestamp": 1756800000, "to": 4294967295, "payload": {"text": "relayed"}}).encode())
assert info["text"]["from"] == "!7c4f4560" or info["text"]["from"] == f"!{2086328928:08x}"
assert info["text"]["from"] != info["gateway"]
assert "text" not in sources.meshtastic_message(T, pkt("telemetry", {"temperature": 25.0}))[2]

# protobuf topic (JSON output off) is ignored, not an error
assert sources.meshtastic_message("msh/SG_923/2/e/LongFast/!a1b2c3d4", b"\x08\x01") == ([], [], {})

# unknown field is tolerated
s, r, _ = sources.meshtastic_message(T, pkt("telemetry", {"temperature": 25.0, "future_metric_xyz": 1.0}))
assert len(r) == 1

# downlink: right topic, small payload, truncation
topic, payload = sources.meshtastic_downlink("msh/SG_923", 2712847316, "Keep the windows shut. " * 20)
assert topic == "msh/SG_923/2/json/mqtt/"
d = json.loads(payload)
assert d["type"] == "sendtext" and d["from"] == 2712847316 and len(d["payload"].encode()) <= 200

# ---- 20 Oct 2026: readings filed under the radio that measured them, by the right name, with the right metric.
# A real line from node #1's broker (mosquitto_sub -v msh/#, 20 Oct 2026 04:06 UTC): the gateway's own device telemetry
# from the host gateway on main ca4e193, before the block was named. USB power, so 101 and its voltage are dropped.
REAL = ('msh/SG_923/2/json/planetai/!8f491db0', b'{"channel":0,"from":2403933616,"id":2180671082,"payload":{"battery_level":101,'
        b'"voltage":-0.001,"channel_utilization":0.0,"air_util_tx":0.107194446,"uptime_seconds":2406},"sender":"!8f491db0",'
        b'"timestamp":1792469161,"to":4294967295,"type":"telemetry"}')
s, r, _ = sources.meshtastic_message(*REAL)
assert s[0]["sensor_id"] == "msh-8f491db0" and {k for _, _, k, _ in r} == {"lora_util_pct", "lora_channel_pct"}, r
# a telemetry row never names the radio: only a nodeinfo does, and _store keeps that name (default_name is for a new row)
assert s[0]["name"] is None and s[0]["default_name"] == "mesh !8f491db0"

# and the outdoor sensor radio's BME680, the same capture (04:11 UTC): gas_resistance is kΩ, as the firmware divides it
REAL_SENSOR = ('msh/SG_923/2/json/planetai/!8f491db0', b'{"channel":0,"from":2404391456,"id":881465736,"payload":{"temperature":26.692438,'
               b'"relative_humidity":46.932587,"barometric_pressure":997.49945,"gas_resistance":236.28397,"iaq":52},"sender":"!8f501a20",'
               b'"timestamp":1792469475,"to":4294967295,"type":"telemetry"}')
s, r, _ = sources.meshtastic_message(*REAL_SENSOR)
m = {k: v for _, _, k, v in r}
assert s[0]["sensor_id"] == "msh-8f501a20" and s[0]["name"] is None
assert m == {"temp": 26.692438, "humidity": 46.932587, "pressure": 99.749945, "gas_resistance": 236.28397, "iaq": 52.0}, m

# The firmware's own MQTT JSON (MeshPacketSerializer.cpp, 2.7.26) sets `sender` to the GATEWAY's id and `from` to the
# radio that sent the packet. The same line as the firmware would publish a sensor's reading heard by the gateway:
FW = json.dumps({"channel": 0, "from": 0x8F501A20, "id": 9, "payload": {"temperature": 26.3, "relative_humidity": 51.4},
                 "sender": "!8f491db0", "timestamp": 1792469161, "to": 4294967295, "type": "telemetry"}).encode()
s, r, _ = sources.meshtastic_message(REAL[0], FW)
assert s[0]["sensor_id"] == "msh-8f501a20", "filed under the radio that measured it, not the gateway that heard it"

# voltage: the device block's is the battery, the environment block's is an INA219's bus (a panel, a pump)
s, r, _ = sources.meshtastic_message(T, pkt("telemetry", {"battery_level": 80, "voltage": 3.9, "channel_utilization": 1.2, "air_util_tx": 0.1}))
assert {k: v for _, _, k, v in r}["battery_v"] == 3.9
s, r, _ = sources.meshtastic_message(T, pkt("telemetry", {"voltage": 12.6, "current": 340.0}))          # firmware JSON: no block
assert {k: v for _, _, k, v in r} == {"voltage": 12.6, "current": 340.0}, r
s, r, _ = sources.meshtastic_message(T, pkt("telemetry", {"voltage": 12.6, "block": "environment"}))   # host gateway: block named
assert {k for _, _, k, _ in r} == {"voltage"}
s, r, _ = sources.meshtastic_message(T, pkt("telemetry", {"voltage": 4.1, "battery_level": 90, "block": "device"}))
assert {k for _, _, k, _ in r} == {"battery_v", "battery_pct"}

# SEN5x as firmware 2.7.26 names its fields (snake-cased by the host gateway), the other new fields, and the
# host gateway's rainfall1h (MessageToDict drops the underscore before a digit) beside the firmware's rainfall_1h
s, r, _ = sources.meshtastic_message(T, pkt("telemetry", {"pm10_standard": 3, "pm25_standard": 7, "pm40_standard": 8, "pm100_standard": 9,
                                                           "pm_voc_idx": 101.0, "pm_nox_idx": 1.0, "form_formaldehyde": 12.5, "block": "air_quality"}))
assert {k: v for _, _, k, v in r} == {"pm1": 3, "pm25": 7, "pm4": 8, "pm10": 9, "tvoc_index": 101.0, "nox_index": 1.0, "hcho": 12.5}, r
s, r, _ = sources.meshtastic_message(T, pkt("telemetry", {"distance": 812.0, "weight": 3.2, "radiation": 9.0, "white_lux": 410.0,
                                                           "rainfall1h": 1.5, "rainfall24h": 22.0, "block": "environment"}))
assert {k: v for _, _, k, v in r} == {"distance": 812.0, "weight": 3.2, "radiation": 9.0, "white_light": 410.0,
                                      "rainfall_1h": 1.5, "rainfall_24h": 22.0}, r
# the firmware's JSON names PM by size with no suffix, and its "pm10" is PM1.0
s, r, _ = sources.meshtastic_message(T, pkt("telemetry", {"pm10": 4, "pm25": 9, "pm100": 11}))
assert {k: v for _, _, k, v in r} == {"pm1": 4, "pm25": 9, "pm10": 11}, r
# no two firmware fields fold onto one key
assert len(sources._MESH_KEYS) == len(sources.MESH_METRICS)

print("all meshtastic tests pass")
