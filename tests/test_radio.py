"""Offline tests for tools/radio.py: the slot arithmetic, the fleet file, the channel URL, the role profiles, the
host gateway's packet → JSON mapping (fed straight into app/sources.py, which must not need to change), the
federation filter and the broker bridge blocks. No radio, no broker.
Run: PYTHONPATH=/tmp/stub:app:tools python3 tests/test_radio.py   (the provision checks run anywhere; the rest needs
the meshtastic package: it has the protobufs)"""
import base64
import json
import os
import tempfile
from pathlib import Path

import radio

# ---- provision, without a radio and without the meshtastic package (these run in CI). Firmware 2.7.26 kept a write
# only when it travelled alone, and the readback on the same connection was the API's cache (node #1, 19 Oct 2026).
fleet = {"region": "SG_923", "preset": "LONG_FAST", "slot": 19,
         "primary": {"name": "planetai", "psk": base64.b64encode(bytes(range(32))).decode(), "position_precision": 32},
         "fabcity": {"name": "fabcity", "psk": base64.b64encode(bytes(range(32, 64))).decode(), "position_precision": 13}}
prof = {"owner": "Mesh test Ungasan", "owner_short": "MTU", "channel_url": "https://meshtastic.org/e/#SECRET",
        "config": {"device": {"role": "SENSOR", "serialEnabled": True},
                   "position": {"fixedPosition": True, "gpsMode": "NOT_PRESENT"},
                   "lora": {"region": "SG_923", "usePreset": True, "modemPreset": "LONG_FAST", "channelNum": 19}},
        "module_config": {"telemetry": {"environmentMeasurementEnabled": True, "environmentUpdateInterval": 900}},
        "location": {"lat": -8.81902, "lon": 115.16736, "alt": 0}}
steps = radio.provision_steps(prof, fleet, gateway=False)
assert steps[0] == ["--set-owner", "Mesh test Ungasan", "--set-owner-short", "MTU"] and steps[1][0] == "--seturl"
sets = [s for s in steps if s[0] == "--set"]
assert [s[1].split(".")[0] for s in sets] == ["device", "position", "lora", "telemetry"], "one call per section: a call that wrote two sections was a transaction, and 2.7.26 lost it"
assert all(len({x.split(".")[0] for x in s[1::3]}) == 1 for s in sets)
assert sets[0] == ["--set", "device.role", "SENSOR", "--set", "device.serialEnabled", "true"]
assert steps.index(["--setlat=-8.81902", "--setlon=115.16736", "--setalt=0"]) > steps.index(sets[1]), \
    "the pin comes after the position section, with `=` for a south latitude"
ch0, ch1 = steps[-2:]
assert ch1[:2] == ["--ch-index", "1"] and "--ch-add" not in ch1, "by index: --ch-add refuses a radio that already has fabcity"
assert ch1[ch1.index("psk") + 1] == "base64:" + fleet["fabcity"]["psk"] and ch1[ch1.index("module_settings.position_precision") + 1] == "13"
assert ch0[:2] == ["--ch-index", "0"] and ch0[ch0.index("module_settings.position_precision") + 1] == "32", \
    "channel 0 again by index: the Tracker read precision 0 after a --seturl that carried 32 (19 Oct)"
assert ch1[ch1.index("uplink_enabled") + 1] == "false" and radio.provision_steps(prof, fleet, gateway=True)[-1][ch1.index("uplink_enabled") + 1] == "true"
assert not [s for s in steps if s[0] == "--reboot"], "provision reboots after reading the boot count, not inside the steps"
# what is printed never carries a key: not the psk, not the URL (it holds both keys), not a WiFi or broker password
for s in steps + [["--set", "network.wifiPsk", "hunter22"], ["--set", "mqtt.password", "pw"]]:
    out = radio.shown(s)
    assert fleet["fabcity"]["psk"] not in out and "SECRET" not in out and "hunter22" not in out and " pw" not in out, out
assert radio.shown(sets[0]) == "--set device.role SENSOR --set device.serialEnabled true"
# the channel hash: name XOR key; node #1's fleet reads planetai 0xfe, fabcity 0xe7
assert radio.channel_hash("ab", bytes([1, 2])) == ord("a") ^ ord("b") ^ 1 ^ 2 and radio.channel_hash("", b"") == 0
# differences(): the radio as read back over a new connection (MessageToDict, defaults included) against the profile
def snap_of(**over):
    s = {"id": "!8f501a20", "lat_i": -88190200, "lon_i": 1151673601, "alt": 0, "owner": "Mesh test Ungasan", "owner_short": "MTU", "reboot_count": 7,
         "config": {"device": {"role": "SENSOR", "serialEnabled": True, "rebroadcastMode": "ALL"},
                    "position": {"fixedPosition": True, "gpsMode": "NOT_PRESENT"},
                    "lora": {"region": "SG_923", "usePreset": True, "modemPreset": "LONG_FAST", "channelNum": 19}},
         "module_config": {"telemetry": {"environmentMeasurementEnabled": True, "environmentUpdateInterval": 900}},
         "channels": {0: {"role": "PRIMARY", "name": "planetai", "psk": base64.b64decode(fleet["primary"]["psk"]), "uplink": False, "downlink": False, "position_precision": 32},
                      1: {"role": "SECONDARY", "name": "fabcity", "psk": base64.b64decode(fleet["fabcity"]["psk"]), "uplink": False, "downlink": False, "position_precision": 13},
                      2: {"role": "DISABLED", "name": "", "psk": b"", "uplink": False, "downlink": False, "position_precision": 0}}}
    s.update(over)
    return s
assert radio.differences(prof, fleet, snap_of(), gateway=False) == [], radio.differences(prof, fleet, snap_of(), gateway=False)
# what 19 Oct's sensor held after --configure: owner and primary channel set, every config section at its default
bad = snap_of(config={"device": {"role": "CLIENT", "serialEnabled": False}, "position": {"fixedPosition": False, "gpsMode": "DISABLED"},
                      "lora": {"region": "UNSET", "usePreset": True, "modemPreset": "LONG_FAST", "channelNum": 0}},
              module_config={"telemetry": {"environmentMeasurementEnabled": False, "environmentUpdateInterval": 0}})
bad["channels"] = dict(bad["channels"]); bad["channels"].pop(1)
p = radio.differences(prof, fleet, bad, gateway=False)
assert "device.role is CLIENT, wants SENSOR" in p and "position.fixedPosition is False, wants True" in p
assert any(x.startswith("lora.region is UNSET, wants SG_923 (a radio with no region") for x in p) and "lora.channelNum is 0, wants 19" in p
assert "telemetry.environmentUpdateInterval is 0, wants 900" in p
assert "channel 1 is missing (no role), wants 'fabcity' hash " + f"{radio.channel_hash('fabcity', base64.b64decode(fleet['fabcity']['psk'])):#04x} (SECONDARY)" in p, p
# the gateway's 18–19 Oct state: the right names, an old primary key. Said by hash, never by key
old = snap_of(); old["channels"] = dict(old["channels"]); old["channels"][0] = dict(old["channels"][0], psk=bytes(32))
p = radio.differences(prof, fleet, old, gateway=False)
assert len(p) == 1 and p[0].startswith("channel 0 is 'planetai' hash ") and fleet["primary"]["psk"] not in p[0], p
assert radio.differences(prof, fleet, snap_of(owner_short="MT"), gateway=False) == ["owner_short is 'MT', wants 'MTU'"]
nopos = snap_of(); nopos["channels"] = dict(nopos["channels"]); nopos["channels"][0] = dict(nopos["channels"][0], position_precision=0)
assert radio.differences(prof, fleet, nopos, gateway=False) == ["channel 0 position precision is 0, wants 32"], "0 = no position on the household channel"
assert radio.differences(prof, fleet, snap_of(), gateway=True)[0] == "channel 0 uplink/downlink is False/False, wants True"
# int64 fields come back as text from MessageToDict; a password is never compared or said
wifi = dict(prof, config=dict(prof["config"], network={"wifiEnabled": True, "wifiPsk": "hunter22"}))
ws = snap_of(); ws["config"] = dict(ws["config"], network={"wifiEnabled": True, "wifiPsk": ""})
assert radio.differences(wifi, fleet, ws, gateway=False) == []
# the sensor role turns air-quality telemetry on. The firmware has it off, so a PM, CO2 or formaldehyde sensor on a
# radio sent nothing at all (20 Oct 2026). It travels in the telemetry section's one call and is read back by name.
sens = radio.load_profiles()["sensor"]["module_config"]["telemetry"]
assert sens["airQualityEnabled"] is True and sens["airQualityInterval"] == 900
aq = dict(prof, module_config={"telemetry": {**prof["module_config"]["telemetry"], "airQualityEnabled": True, "airQualityInterval": 900}})
tele = [st for st in radio.provision_steps(aq, fleet, gateway=False) if st[0] == "--set" and st[1].startswith("telemetry.")]
assert len(tele) == 1 and tele[0][-6:] == ["--set", "telemetry.airQualityEnabled", "true", "--set", "telemetry.airQualityInterval", "900"], tele
held = snap_of(module_config={"telemetry": {"environmentMeasurementEnabled": True, "environmentUpdateInterval": 900, "airQualityEnabled": True, "airQualityInterval": 900}})
assert radio.differences(aq, fleet, held, gateway=False) == []
lost = snap_of()   # MessageToDict with defaults: a radio that dropped the write reads False and 0
lost["module_config"]["telemetry"].update(airQualityEnabled=False, airQualityInterval=0)
assert radio.differences(aq, fleet, lost, gateway=False) == ["telemetry.airQualityEnabled is False, wants True",
                                                            "telemetry.airQualityInterval is 0, wants 900"]
assert {radio.problem_key(x) for x in radio.differences(aq, fleet, lost, gateway=False)} == {radio.step_key(tele[0])}, "a lost one is written again"
assert radio.differences(dict(prof, module_config={"telemetry": {"environmentUpdateInterval": 900}}), fleet,
                         snap_of(module_config={"telemetry": {"environmentUpdateInterval": "900"}}), gateway=False) == []
# the pin itself, not only fixedPosition: on the XIAO a later write put the position back to its defaults (19 Oct)
assert radio.differences(prof, fleet, snap_of(lat_i=None, lon_i=None), gateway=False) == ["position.pin is none,none,0 m, wants -8.81902,115.16736,0 m"]
assert radio.differences(prof, fleet, snap_of(lon_i=None), gateway=False)[0].startswith("position.pin is -8.81902,none"), "one coordinate missing is a difference, not a crash"
assert radio.differences(prof, fleet, snap_of(lat_i=-88190300), gateway=False), "10 m off is off: compared at the stored 1e-7 degrees"
assert radio.differences(prof, fleet, snap_of(alt=12), gateway=False) == ["position.pin is -8.81902,115.1673601,12 m, wants -8.81902,115.16736,0 m"]
assert radio.problem_key("position.pin is none,none,0 m, wants -8.81902,115.16736,0 m") == "position"
assert radio.differences(dict(prof, location=None), fleet, snap_of(lat_i=None, lon_i=None), gateway=False) == [], "no --fixed, no pin wanted"
# a difference names the step that repairs it: provision writes again only what did not hold (a ch0 write once
# emptied ch1 on a XIAO, 19 Oct)
keys = {radio.step_key(s) for s in steps}
for q in radio.differences(prof, fleet, bad, gateway=False) + radio.differences(prof, fleet, nopos, gateway=False) + ["owner_short is 'MT', wants 'MTU'"]:
    assert radio.problem_key(q) in keys, (q, radio.problem_key(q), keys)
assert radio.problem_key("channel 1 is missing (no role), wants 'fabcity' hash 0xe7 (SECONDARY)") == "ch1"
assert [radio.step_key(s) for s in steps if radio.step_key(s) == "position"] == ["position", "position"], "the pin is rewritten with its section"
assert radio.step_key(steps[1]) == "--seturl" and "--seturl" not in {radio.problem_key(q) for q in radio.differences(prof, fleet, bad, gateway=False)}
# wait_rebooted: an ESP32's boot count rises with its port up; an nRF52's count stays 0 and its USB port drops and returns
real = (radio.read_radio, radio.os.path.exists, radio.time.sleep)
radio.time.sleep = lambda s: None
radio.read_radio = lambda port: snap_of(reboot_count=8)
radio.os.path.exists = lambda port: True
assert radio.wait_rebooted("/dev/x", 7)["reboot_count"] == 8, "ESP32: the count rose"
radio.read_radio = lambda port: snap_of(reboot_count=0)
seen = iter([True, True, False])
radio.os.path.exists = lambda port: next(seen, True)
assert radio.wait_rebooted("/dev/x", 0)["reboot_count"] == 0, "nRF52: the port dropped, the count stays 0"
radio.os.path.exists = lambda port: True
try:
    radio.wait_rebooted("/dev/x", 0, tries=2); raise AssertionError("no rise, no drop: not proven")
except SystemExit as e:
    assert "did not reboot" in str(e)
# a --set that prints no "Set" line landed in a reboot window and wrote nothing: it is sent again at once
calls, outs = [], iter(["Connected to radio\n", "Connected to radio\nSet role to SENSOR\nSet serial_enabled to true\n"])
real_cli, real_ready = radio.run_cli, radio.wait_ready
radio.run_cli = lambda port, *a, **k: (calls.append(a), next(outs, "") if a and a[0] == "--set" else "")[1]
radio.wait_ready = lambda port, tries=30: None
radio.read_radio = lambda port: snap_of(reboot_count=1)
radio.os.path.exists = lambda port: next(iter([False]))
radio.write_and_reboot("/dev/x", [sets[0]])
assert [c[0] for c in calls] == ["--set", "--set", "--reboot"], calls
outs = iter(["", "", ""])   # three times no "Set" line: a password write cannot be read back, so it stops
try:
    radio.write_and_reboot("/dev/x", [["--set", "network.wifiPsk", "hunter22"]]); raise AssertionError("an unconfirmed write passed")
except SystemExit as e:
    assert "did not take" in str(e) and "hunter22" not in str(e)
radio.run_cli, radio.wait_ready = real_cli, real_ready
radio.read_radio, radio.os.path.exists, radio.time.sleep = real
# a failed CLI call is reported without the values it was given: the CLI echoes "Set wifi_psk to …" before failing
real_run, real_cli = radio.subprocess.run, radio.meshtastic_cli
radio.meshtastic_cli = lambda: ["python3", "-m", "meshtastic"]
radio.subprocess.run = lambda *a, **k: type("R", (), {"returncode": 1, "stdout": "Set wifi_psk to hunter22\n", "stderr": "Error: base64 key AAAA lost"})()
for args in (["--set", "network.wifiPsk", "hunter22"], ["--ch-index", "1", "--ch-set", "psk", "base64:AAAA"]):
    try:
        radio.run_cli("/dev/x", *args); raise AssertionError("a failed call passed")
    except SystemExit as e:
        assert "hunter22" not in str(e) if "hunter22" in args else "AAAA" not in str(e), str(e)
radio.subprocess.run, radio.meshtastic_cli = real_run, real_cli
print("radio provision: ok")

try:
    import meshtastic  # noqa: F401  (the protobufs the channel URL and the profile reader need)
except ImportError:
    print("radio: skipped (no meshtastic package: pip3 install --user meshtastic)")
    raise SystemExit(0)
import sources

# ---- the frequency slot: SG_923 is 917–925, Indonesia allows 920–923, LONG_FAST is 250 kHz wide
assert radio.num_slots("SG_923") == 32
inside = radio.slots_inside("SG_923", (920.0, 923.0))
assert inside == list(range(13, 25)), inside
for s in inside:
    f = radio.slot_freq("SG_923", s)
    assert 920.0 <= f - 0.125 and f + 0.125 <= 923.0, (s, f)
assert radio.slot_freq("SG_923", 13) == 920.125 and radio.slot_freq("SG_923", 24) == 922.875
pinned = radio.slot_for("SG_923", "bali")
assert pinned in inside
assert radio.slot_for("EU_868", "menorca") is None, "no listed allocation: the channel name hashes the slot"

# ---- the fleet file: two channels, two keys, never the same, 32 bytes each, pinned for Bali
f = radio.new_fleet("bayu-ungasan", "SG_923", "bali")
assert f["primary"]["name"] == "planetai" and f["fabcity"]["name"] == "fabcity"
assert len(base64.b64decode(f["primary"]["psk"])) == 32 and len(base64.b64decode(f["fabcity"]["psk"])) == 32
assert f["primary"]["psk"] != f["fabcity"]["psk"] and f["slot"] == pinned
assert f["fabcity"]["position_precision"] == 13, "2.9 km on the shared channel: coarser than a resolution-8 cell"
g = radio.new_fleet("menorca", "EU_868", "menorca")
assert g["slot"] is None and g["primary"]["psk"] != f["primary"]["psk"]
try:
    radio.new_fleet("x", "ID_923"); raise AssertionError("unknown region must refuse")
except SystemExit:
    pass
with tempfile.TemporaryDirectory() as d:
    p = Path(d) / "fleet.yaml"
    radio.save_fleet(f, p)
    assert oct(p.stat().st_mode)[-3:] == "600", "the fleet file holds keys"
    assert radio.load_fleet(p)["primary"]["psk"] == f["primary"]["psk"]

# ---- the channel URL carries both channels and the LoRa config; the gateway's differs by the uplink bits only
u = radio.channel_url(f)
d = radio.decode_url(u)
assert d["region"] == "SG_923" and d["preset"] == "LONG_FAST" and d["slot"] == pinned
assert [c["name"] for c in d["channels"]] == ["planetai", "fabcity"]
assert all(c["psk_len"] == 32 for c in d["channels"])
assert not d["channels"][0]["uplink"] and not d["channels"][0]["downlink"]
assert d["channels"][1]["position_precision"] == 13 and d["channels"][0]["position_precision"] == 32, \
    "full position on the household channel (Tomas, 19 Oct); 0 would mean a sensor never says where it stands"
assert f["primary"]["position_precision"] == 32
dg = radio.decode_url(radio.channel_url(f, gateway=True))
assert dg["channels"][0]["uplink"] and dg["channels"][0]["downlink"] and dg["channels"][1]["uplink"]
assert u.startswith("https://meshtastic.org/e/#") and "=" not in u

# ---- role profiles render to the --configure format; the base is merged under every role
profiles = radio.load_profiles(Path(__file__).resolve().parent.parent / "tools" / "radio_profiles")
assert {"sensor", "relay", "shelf", "gateway-wifi", "gateway-host"} <= set(profiles)
sp = radio.render_profile("sensor", "Subak edge", "SBK", f, profiles)
assert sp["owner"] == "Subak edge" and sp["owner_short"] == "SBK" and sp["channel_url"] == u
assert sp["config"]["device"]["role"] == "SENSOR" and sp["config"]["device"]["serialEnabled"] is True, "base merged"
assert sp["module_config"]["telemetry"]["environmentMeasurementEnabled"] is True
assert sp["module_config"]["telemetry"]["environmentUpdateInterval"] == 900 and sp["module_config"]["telemetry"]["deviceUpdateInterval"] == 900
assert sp["config"]["position"]["gpsMode"] == "ENABLED"
assert sp["config"]["lora"] == {"region": "SG_923", "usePreset": True, "modemPreset": "LONG_FAST", "channelNum": pinned, "hopLimit": 3, "txEnabled": True}, \
    "the lora section repeats the URL's region and slot: a seeded lora section must never put UNSET back"
mp = radio.render_profile("sensor", "Es Castell", "CAS", g, profiles)
assert mp["config"]["lora"]["region"] == "EU_868" and mp["config"]["lora"]["channelNum"] == 0, "no pinned slot: the name hashes it"
assert "mqtt" not in sp["module_config"]
rp = radio.render_profile("relay", "Roof", "RF", f, profiles)
assert rp["config"]["device"]["role"] == "ROUTER" and rp["config"]["position"]["gpsMode"] == "NOT_PRESENT"
try:
    radio.render_profile("gateway-wifi", "gw", "GW", f, profiles); raise AssertionError("wifi gateway without a broker must refuse")
except SystemExit:
    pass
wp = radio.render_profile("gateway-wifi", "bayu gateway", "GW", f, profiles, {"address": "192.168.4.190:1883", "username": "planetai", "password": "pw"}, ("subak", "secret"))
assert wp["module_config"]["mqtt"] == {"enabled": True, "address": "192.168.4.190:1883", "username": "planetai", "password": "pw",
                                       "encryptionEnabled": False, "jsonEnabled": True, "root": "msh"}
assert wp["config"]["network"] == {"wifiEnabled": True, "wifiSsid": "subak", "wifiPsk": "secret"}
assert radio.decode_url(wp["channel_url"])["channels"][0]["uplink"], "a gateway's URL has uplink on"
hp = radio.render_profile("gateway-host", "node radio", "NODE", f, profiles)
assert hp["module_config"]["mqtt"]["enabled"] is False and hp["config"]["bluetooth"]["enabled"] is False
assert hp["config"]["device"]["serialEnabled"] is True
# a XIAO sensor node has no GPS: --fixed pins its position in the profile and turns the GPS off
fp = radio.render_profile("sensor", "Warung roof", "WRG", f, profiles, fixed=(-8.8004527, 115.1766378, 12))
assert fp["location"] == {"lat": -8.8004527, "lon": 115.1766378, "alt": 12}, "the CLI reads location:, not fixed_position:"
assert fp["config"]["position"]["fixedPosition"] is True and fp["config"]["position"]["gpsMode"] == "NOT_PRESENT"
assert fp["config"]["position"]["positionBroadcastSecs"] == 1800, "the role's other position settings survive"
assert "location" not in sp, "no --fixed, no pin"
try:
    radio.render_profile("sensor", "x", "X", f, profiles, fixed=(91.0, 0.0, 0.0)); raise AssertionError("bad coordinate")
except SystemExit:
    pass
for bad in ("", "TOOLONG"):
    try:
        radio.render_profile("sensor", "x", bad, f, profiles); raise AssertionError("short name length")
    except SystemExit:
        pass
try:
    radio.render_profile("drone", "x", "DR", f, profiles); raise AssertionError("unknown role")
except SystemExit:
    pass

# ---- the host gateway: a decoded packet from the Python API becomes the JSON an ESP32 publishes, and
# app/sources.py reads it unchanged. Shapes as MessageToDict gives them (camelCase).
GW = "!a1b2c3d4"
def pkt(portnum, **decoded):
    return {"from": 0xDEADBEEF, "fromId": "!deadbeef", "to": 4294967295, "id": 77, "channel": 0, "rxTime": 1760600000,
            "decoded": {"portnum": portnum, **decoded}}
tp = radio.to_mqtt(pkt("TELEMETRY_APP", telemetry={"time": 1760600000, "environmentMetrics": {"temperature": 29.4, "relativeHumidity": 71.2, "barometricPressure": 1008.3, "gasResistance": 47658.0, "iaq": 52}}), GW, "SG_923", "planetai")
assert tp[0] == "msh/SG_923/2/json/planetai/!a1b2c3d4", tp[0]
m = json.loads(tp[1])
assert m["type"] == "telemetry" and m["sender"] == "!deadbeef" and m["from"] == 0xDEADBEEF and m["timestamp"] == 1760600000
assert m["payload"]["relative_humidity"] == 71.2 and m["payload"]["barometric_pressure"] == 1008.3, m["payload"]
s, r, info = sources.meshtastic_message(tp[0], tp[1])
vals = {k: v for _, _, k, v in r}
assert s[0]["sensor_id"] == "msh-deadbeef" and s[0]["local"] and vals["temp"] == 29.4 and vals["humidity"] == 71.2
assert abs(vals["pressure"] - 100.83) < 0.01 and vals["gas_resistance"] == 47658.0 and vals["iaq"] == 52
assert info["root_topic"] == "msh/SG_923" and info["gateway"] == GW, "the node learns where to send alerts back"
# air quality block → pm names; device metrics with the 101 sentinel are dropped by sources, not by us
tp = radio.to_mqtt(pkt("TELEMETRY_APP", telemetry={"airQualityMetrics": {"pm10Standard": 4, "pm25Standard": 9, "pm100Standard": 11}}), GW, "SG_923", "planetai")
s, r, _ = sources.meshtastic_message(*tp)
vals = {k: v for _, _, k, v in r}
assert vals == {"pm1": 4.0, "pm25": 9.0, "pm10": 11.0}, vals
tp = radio.to_mqtt(pkt("TELEMETRY_APP", telemetry={"deviceMetrics": {"batteryLevel": 101, "voltage": 4.9, "airUtilTx": 0.05}}), GW, "SG_923", "planetai")
s, r, _ = sources.meshtastic_message(*tp)
assert {k for _, _, k, _ in r} == {"lora_util_pct"}
assert json.loads(tp[1])["payload"]["block"] == "device"
# an INA219's voltage arrives in environmentMetrics; the block's name keeps it off battery_v (20 Oct 2026)
tp = radio.to_mqtt(pkt("TELEMETRY_APP", telemetry={"environmentMetrics": {"voltage": 12.6, "current": 340.0}}), GW, "SG_923", "planetai")
assert json.loads(tp[1])["payload"]["block"] == "environment"
assert {k: v for _, _, k, v in sources.meshtastic_message(*tp)[1]} == {"voltage": 12.6, "current": 340.0}
# SEN5x on 2.7.26, camelCase as MessageToDict gives it; rainfall24h has lost its underscore on the way
tp = radio.to_mqtt(pkt("TELEMETRY_APP", telemetry={"airQualityMetrics": {"pm40Standard": 8, "pmVocIdx": 101.0, "pmNoxIdx": 1.0, "formFormaldehyde": 12.5}}), GW, "SG_923", "planetai")
assert {k: v for _, _, k, v in sources.meshtastic_message(*tp)[1]} == {"pm4": 8, "tvoc_index": 101.0, "nox_index": 1.0, "hcho": 12.5}
tp = radio.to_mqtt(pkt("TELEMETRY_APP", telemetry={"environmentMetrics": {"rainfall1h": 1.5, "rainfall24h": 22.0}}), GW, "SG_923", "planetai")
assert {k: v for _, _, k, v in sources.meshtastic_message(*tp)[1]} == {"rainfall_1h": 1.5, "rainfall_24h": 22.0}
# an MLX90614's object temperature is healthMetrics: never uplinked, so never filed as the air's
assert radio.to_mqtt(pkt("TELEMETRY_APP", telemetry={"healthMetrics": {"temperature": 36.6}}), GW, "SG_923", "planetai") is None
# position and nodeinfo
tp = radio.to_mqtt(pkt("POSITION_APP", position={"latitudeI": -88004527, "longitudeI": 1151766378, "altitude": 42, "time": 1760600000}), GW, "SG_923", "planetai")
s, r, _ = sources.meshtastic_message(*tp)
assert abs(s[0]["lat"] + 8.8004527) < 1e-6 and abs(s[0]["lon"] - 115.1766378) < 1e-6
tp = radio.to_mqtt(pkt("NODEINFO_APP", user={"id": "!deadbeef", "longName": "Subak edge", "shortName": "SBK", "hwModel": "WIO_TRACKER_L1"}), GW, "SG_923", "planetai")
s, _, _ = sources.meshtastic_message(*tp)
assert s[0]["name"] == "Subak edge" and s[0]["meta"]["hardware"] == "WIO_TRACKER_L1"
# text; and what the node has no use for returns None rather than noise
tp = radio.to_mqtt(pkt("TEXT_MESSAGE_APP", text="smoke at the river"), GW, "SG_923", "planetai")
assert json.loads(tp[1])["payload"] == {"text": "smoke at the river"}
assert radio.to_mqtt(pkt("ROUTING_APP", routing={}), GW, "SG_923", "planetai") is None
assert radio.to_mqtt(pkt("TELEMETRY_APP", telemetry={"time": 1}), GW, "SG_923", "planetai") is None
# the node's downlink (sources.meshtastic_downlink) is what the gateway listens for: same topic, same shape
t, p = sources.meshtastic_downlink("msh/SG_923", 123456, "PM2.5 high, close windows")
assert t == "msh/SG_923/2/json/mqtt/" and json.loads(p)["type"] == "sendtext"

# ---- federation: text on channel 1 leaves; readings and positions and channel 0 never do; inbound is deduplicated,
# rate-limited and never an echo
fed = radio.Federation("bayu-ungasan", max_per_minute=3)
assert fed.outbound(pkt("TEXT_MESSAGE_APP", text="hello from the household")) is None, "channel 0 stays home"
p1 = pkt("TEXT_MESSAGE_APP", text="hello from Bali"); p1["channel"] = 1
t, body = fed.outbound(p1)
assert t == "fabcity/bayu-ungasan/text" and json.loads(body) == {"node": "bayu-ungasan", "from": "!deadbeef", "id": 77, "text": "hello from Bali", "ts": 1760600000}
pp = pkt("POSITION_APP", position={"latitudeI": -88004527, "longitudeI": 1151766378}); pp["channel"] = 1
assert fed.outbound(pp) is None, "a position never crosses, whatever the channel"
pt = pkt("TELEMETRY_APP", telemetry={"environmentMetrics": {"temperature": 30}}); pt["channel"] = 1
assert fed.outbound(pt) is None, "a reading never crosses"
msg = json.dumps({"node": "menorca", "id": 5, "text": "hola desde Menorca"}).encode()
assert fed.inbound("fabcity/menorca/text", msg, now=1000) == "[menorca] hola desde Menorca"
assert fed.inbound("fabcity/menorca/text", msg, now=1001) is None, "duplicate id"
assert fed.inbound("fabcity/bayu-ungasan/text", json.dumps({"id": 9, "text": "me"}).encode(), now=1002) is None, "own echo"
assert fed.inbound("fabcity/menorca/presence", json.dumps({"id": 9, "text": "x"}).encode(), now=1003) is None, "presence is not relayed to the air"
assert fed.inbound("msh/EU_868/2/json/planetai/!1", b"{}", now=1004) is None
assert fed.inbound("fabcity/menorca/alerts", json.dumps({"id": 6, "text": "heat alert"}).encode(), now=1005) == "[menorca] heat alert"
assert fed.inbound("fabcity/boston/text", json.dumps({"id": 1, "text": "third"}).encode(), now=1006) == "[boston] third"
assert fed.inbound("fabcity/boston/text", json.dumps({"id": 2, "text": "fourth in the same minute"}).encode(), now=1007) is None, "rate limit"
assert fed.inbound("fabcity/boston/text", json.dumps({"id": 3, "text": "a minute later"}).encode(), now=1070) == "[boston] a minute later"
long = json.dumps({"id": 4, "text": "x" * 400}).encode()
assert len(fed.inbound("fabcity/boston/text", long, now=1200)) == 200, "LoRa frames are small"
t, body = fed.presence(3, "83a5f6fffffffff")
assert t == "fabcity/bayu-ungasan/presence" and json.loads(body)["radios"] == 3

# ---- broker bridges: only fabcity/ crosses, each direction named, over the tailnet
peers = radio.parse_peers("menorca=lucas-node.tail1234.ts.net:1883:s3cret, boston=fabhub.tail1234.ts.net:1883:pw2")
assert peers == {"menorca": {"address": "lucas-node.tail1234.ts.net:1883", "password": "s3cret"}, "boston": {"address": "fabhub.tail1234.ts.net:1883", "password": "pw2"}}
conf = radio.mosquitto_bridges("bayu-ungasan", peers, "planetai")
assert "connection fabcity-menorca" in conf and "address lucas-node.tail1234.ts.net:1883" in conf
assert "topic bayu-ungasan/# out 0 fabcity/ fabcity/" in conf and "topic menorca/# in 0 fabcity/ fabcity/" in conf
assert "msh/" not in conf, "readings never leave the node"
assert conf.count("connection ") == 2
try:
    radio.parse_peers("menorca=host"); raise AssertionError("malformed peer")
except SystemExit:
    pass
assert radio.parse_peers("") == {}

print("radio: ok")
