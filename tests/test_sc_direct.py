"""Offline tests for the Smart Citizen wire-format parser (packs/smartcitizen/hooks.py since 22 Oct 2026): a kit or a
Making Sense Bali DIY node publishing to this node's own broker instead of mqtt.smartcitizen.me. Payload shapes are the
ones the two firmwares send today (fablabbcn/smartcitizen-kit-21 esp/src/SckESP.cpp; makingsensebali
hardware/diy-node/firmware). And what the node does with them: stored, counted for /health, queued to forward.
Run: PYTHONPATH=/tmp/stub:app python3 tests/test_sc_direct.py"""
import importlib.util
import json
import os
import time

import settings

ROWS = {"SC_FORWARD": ""}
settings._cache = {"at": time.time() + 1e9, "rows": ROWS}
_spec = importlib.util.spec_from_file_location("sc_hooks", "packs/smartcitizen/hooks.py")
sources = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(sources)   # the parser kept its names

TOKEN = "a1b2c3"
SID = sources.sc_sensor_id(TOKEN)

# the token is a credential: it never appears in the sensor id, and the id is stable
assert SID.startswith("sck-") and TOKEN not in SID and len(SID) == 12 and SID == sources.sc_sensor_id(TOKEN)

# DIY node v3/v4: Smart Citizen's `readings` JSON, catalogue ids for BME68X + HM-3301
diy = {"data": [{"recorded_at": "2026-10-07T04:10:00Z", "sensors": [
    {"id": 237, "value": 28.31}, {"id": 238, "value": 71.2}, {"id": 239, "value": 100.83}, {"id": 240, "value": 47658.0},
    {"id": 241, "value": 52.0}, {"id": 233, "value": 4.0}, {"id": 234, "value": 9.0}, {"id": 235, "value": 11.0}]}]}
s, r, info = sources.smartcitizen_mqtt(f"device/sck/{TOKEN}/readings", json.dumps(diy).encode())
m = {k: v for _, _, k, v in r}
assert s[0]["sensor_id"] == SID and s[0]["local"] and s[0]["kind"] == "sensor" and s[0]["source"] == "smartcitizen-direct"
assert m == {"temp": 28.31, "humidity": 71.2, "pressure": 100.83, "gas_resistance": 47658.0, "bme_iaq": 52.0, "pm1": 4.0, "pm25": 9.0, "pm10": 11.0}
assert r[0][0].isoformat() == "2026-10-07T04:10:00+00:00", "the device's own timestamp, not the poll time"
assert s[0]["indoor"] is False and s[0]["name"] == f"kit {SID[4:]}", "no meta yet: outdoor, named by id"
assert info["kind"] == "readings" and info["sensor_id"] == SID

# SCK 2.1 firmware: `readings/raw`, pseudo-JSON with the urban board's ids
raw = b"{t:2026-10-07T04:11:00Z,55:28.3,56:66,58:100.9,14:120,53:41.5,87:12,88:14,89:9,10:97,0:5}"
s, r, info = sources.smartcitizen_mqtt(f"device/sck/{TOKEN}/readings/raw", raw)
m = {k: v for _, _, k, v in r}
assert m == {"temp": 28.3, "humidity": 66.0, "pressure": 100.9, "light": 120.0, "noise": 41.5, "pm25": 12.0, "pm10": 14.0, "pm1": 9.0, "battery_pct": 97.0}
assert r[0][0].isoformat() == "2026-10-07T04:11:00+00:00" and info["kind"] == "readings/raw"

# a retained meta message names the device and says where it is; it carries no readings
meta = {"name": "Balai Banjar Serangan", "site": "warung wall, north side", "height_m": 2.5, "indoor": True, "hardware": "msb-diy-node", "fw": "v4"}
s, r, info = sources.smartcitizen_mqtt(f"device/sck/{TOKEN}/meta", json.dumps(meta).encode())
assert r == [] and info["kind"] == "meta" and info["meta"]["indoor"] is True
assert s[0]["name"] == "Balai Banjar Serangan" and s[0]["indoor"] is True and s[0]["meta"]["height_m"] == 2.5 and s[0]["meta"]["hardware"] == "msb-diy-node"
assert "token" not in json.dumps(s[0]) and TOKEN not in json.dumps(s[0])

# readings after meta carry the meta's name and indoor, so the upsert never flips a room back to outdoor
s, r, _ = sources.smartcitizen_mqtt(f"device/sck/{TOKEN}/readings", json.dumps(diy).encode(), meta=info["meta"])
assert s[0]["indoor"] is True and s[0]["name"] == "Balai Banjar Serangan" and len(r) == 8

# a reading with no usable time is stamped now, not dropped; an unknown id is skipped, not fatal
s, r, _ = sources.smartcitizen_mqtt(f"device/sck/{TOKEN}/readings", json.dumps({"data": [{"sensors": [{"id": 237, "value": 30}, {"id": 9999, "value": 1}]}]}).encode())
assert len(r) == 1 and r[0][2] == "temp" and (r[0][0].tzinfo is not None)

# the topics a device uses that carry no readings for this node, and things that are not Smart Citizen at all
for topic, payload in ((f"device/sck/{TOKEN}/hello", b"a1b2c3:Hello"), (f"device/sck/{TOKEN}/info", b'{"hw_ver":"2.1"}'),
                       ("device/inventory", b"{}"), ("msh/SG_923/2/json/LongFast/!a1", b"{}")):
    s, r, info = sources.smartcitizen_mqtt(topic, payload)
    assert s == [] and r == [], topic
assert sources.smartcitizen_mqtt(f"device/sck/{TOKEN}/hello", b"x")[2]["kind"] == "hello", "the kind is reported so the forwarder can pass it on"

# garbage never raises
for payload in (b"", b"{", b"null", b'{"data": "x"}', b"{t:bad,55:x}"):
    s, r, _ = sources.smartcitizen_mqtt(f"device/sck/{TOKEN}/readings", payload)
    s2, r2, _ = sources.smartcitizen_mqtt(f"device/sck/{TOKEN}/readings/raw", payload)
    assert r == [] and r2 == []

# ---- on_mqtt: what the node stores, what /health counts, what waits to be forwarded
hooks = sources
assert hooks.MQTT_TOPICS == [("device/sck/#", 1)], "QoS 1, as the platform asks"
assert hooks.on_mqtt("msh/SG_923/2/json/LongFast/!a1", b"{}") is None, "another topic is not this pack's"
s, r = hooks.on_mqtt(f"device/sck/{TOKEN}/meta", json.dumps(meta).encode())
assert r == [] and s[0]["indoor"] is True and hooks.state["messages"] == 1
s, r = hooks.on_mqtt(f"device/sck/{TOKEN}/readings", json.dumps(diy).encode())
assert s[0]["name"] == "Balai Banjar Serangan" and s[0]["indoor"] is True and len(r) == 8, "the kept meta names the readings"
assert hooks.state["devices"] == 1 and hooks.state["messages"] == 2 and hooks.state["queued"] == 0
assert not hooks._forwarder, "nothing to forward, no thread"
ROWS["SC_FORWARD"] = f"other, {TOKEN}"
hooks._forwarder.append(None)        # stand in for the thread, so the test reaches no network
hooks.on_mqtt(f"device/sck/{TOKEN}/meta", json.dumps(meta).encode())
assert hooks.state["queued"] == 0, "a meta message is never forwarded"
hooks.on_mqtt(f"device/sck/{TOKEN}/readings/raw", raw)
assert list(hooks._queue) == [(f"device/sck/{TOKEN}/readings/raw", raw, TOKEN)] and hooks.state["queued"] == 1, "the device's own bytes"
os.environ.pop("MQTT_HOST", None)
assert hooks.status() == {}, "no broker, no direct key"
os.environ["MQTT_HOST"] = "mosquitto"
assert hooks.status() == {"direct": hooks.state} and TOKEN not in json.dumps(hooks.status())

print("test_sc_direct: ok")
