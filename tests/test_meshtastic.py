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

print("all meshtastic tests pass")
