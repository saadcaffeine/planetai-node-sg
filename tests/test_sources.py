"""Offline adapter tests against saved payload shapes. Run: PACKS_DIR=packs PYTHONPATH=/tmp/stub:app python3 tests/test_sources.py
(stub httpx first: mkdir -p /tmp/stub && echo "class Client: pass" > /tmp/stub/httpx.py)"""
import sources

class R:
    def __init__(s, j): s.j = j
    def raise_for_status(s): pass
    def json(s): return s.j
class HC:
    def __init__(s, j): s.j = j
    def get(s, url, timeout=None): return R(s.j)

# Smart Citizen's cloud fetch is packs/smartcitizen since 22 Oct 2026: tests/test_smartcitizen.py. AirGradient and
# PurpleAir are packs too since the same day; their readers are checked here, their switch in tests/test_lan_air.py.
import importlib.util


def _pack(name):
    spec = importlib.util.spec_from_file_location(f"pack_{name}", f"packs/{name}/adapter.py")
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    return mod


ag = {"serialno": "84fce612a5b4", "rco2": 612, "pm01": 4, "pm02": 9, "pm10": 11, "atmp": 29.4, "rhum": 61, "tvocIndex": 98, "noxIndex": 1, "firmware": "3.1.9", "model": "I-9PSL"}
s, r = _pack("airgradient").airgradient(HC(ag), ["airgradient_84fce6.local"], -8.65, 115.22, False)
m = {k: v for _, _, k, v in r}
assert s[0]["sensor_id"] == "ag-84fce612a5b4" and m["pm25_raw"] == 9.0 and 4 < m["pm25"] < 7 and m["co2"] == 612

pa = {"SensorId": "84:f3:eb:12:34:56", "Geo": "PurpleAir-3456", "lat": -8.53, "lon": 115.40, "pm2_5_cf_1": 47.8, "pm2_5_cf_1_b": 46.9, "pm10_0_cf_1": 52.1, "current_humidity": 62, "current_temp_f": 94, "pressure": 1006.2}
s, r = _pack("purpleair").purpleair(HC(pa), ["192.168.1.60"], None, None, False)
m = {k: v for _, _, k, v in r}
assert s[0]["sensor_id"] == "pa-84f3eb123456" and 34 < m["pm25"] < 38, "EPA correction of ~47 raw @62% RH should land ~36 (BAD's Klungkung row)"
assert abs(m["temp"] - 34.4) < 0.1 and abs(m["pressure"] - 100.62) < 0.01

assert round(_pack("air-quality").epa_2021_correct(28, 65), 1) == 14.8   # BAD's worked example: raw 28 -> ~15

# `local` is ours AND here. An adapter says whether a sensor is ours; distance says whether it is at this node.
# Node #1 moved to Ungasan and kept three kits 1.2 km away marked local, so its "house" was three kits in
# another building and it had no local outdoor sensor at all.
assert round(sources.metres(-8.8190516, 115.1644423, -8.81983, 115.16657)) == 250, "sc-19236 is 250 m from node #1"
assert round(sources.metres(-8.8190516, 115.1644423, -8.8271, 115.15709)) == 1207, "the indoor cluster is 1.2 km away"
assert sources.metres(-8.8190516, 115.1644423, -8.8190516, 115.1644423) == 0.0

NODE = (-8.8190516, 115.1644423)
here     = {"sensor_id": "sc-19236", "local": True,  "lat": -8.81983, "lon": 115.16657}
far      = {"sensor_id": "sc-19880", "local": True,  "lat": -8.8271,  "lon": 115.15709}
theirs   = {"sensor_id": "bad-x",    "local": False, "lat": -8.81985, "lon": 115.16650}
nocoords = {"sensor_id": "msh-abc",  "local": True,  "lat": None,     "lon": None}
sources.stamp_local([here, far, theirs, nocoords], *NODE, 500)
assert here["local"] is True,  "250 m inside a 500 m radius stays local"
assert far["local"] is False,  "1.2 km away is ours but not here"
assert theirs["local"] is False, "a public station next door is still not ours"
assert nocoords["local"] is True, "a mesh pod on our own gateway has no coordinates and stays local"

# A node that does not know where it is must not decide that nothing is local. With no coordinates stamp_local
# leaves every claim alone: blanking the fleet on a half-configured node is worse than trusting the adapter.
unset = [{"sensor_id": "sc-19236", "local": True, "lat": -8.81983, "lon": 115.16657}]
sources.stamp_local(unset, None, None, 500)
assert unset[0]["local"] is True, "no node coordinates means no narrowing, not narrowing everything away"

print("all adapter tests pass")
