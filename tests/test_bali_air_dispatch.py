"""packs/bali-air-dispatch: the island's public stations, moved out of the core (after v0.82.3).

Run: PACKS_DIR=packs PYTHONPATH=/tmp/stub:app python3 tests/test_bali_air_dispatch.py
What the core adapter did, the pack does with the same ids; it runs on an official switch without PACKS_ALLOW_CODE;
and the core no longer names it.
"""
import glob
import importlib.util
import os
import re
import shutil
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("bad_adapter", ROOT / "packs/bali-air-dispatch/adapter.py")
B = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(B)

import packs  # noqa: E402
import settings  # noqa: E402


class R:
    def __init__(s, j): s.j = j
    def raise_for_status(s): pass
    def json(s): return s.j


class HC:
    def __init__(s, j): s.j = j
    def get(s, url, timeout=None): return R(s.j)


# ---- 1. the ring, as the core adapter stored it (moved from tests/test_sources.py)
bad = {"readings": [
    {"station_id": "pa-46949", "name": "Klungkung", "source": "PurpleAir", "latitude": -8.533623, "longitude": 115.39973, "observed_at": "2026-08-01T20:15:11.000Z", "stale": False, "pm25": 36.6, "pm25_raw": 47.8},
    {"station_id": "aq-1", "name": "Denpasar", "source": "AQICN", "latitude": -8.63, "longitude": 115.21, "observed_at": "2026-06-03T08:45:39.000Z", "stale": True, "pm25": 168},
    {"station_id": "iqs-x", "name": "Jimbaran villa", "source": "IQAir", "latitude": -8.79, "longitude": 115.16, "observed_at": "2026-09-02T02:00:00Z", "stale": False, "pm25": 22.0, "suspected_indoor": True}]}
s, r = B.ring(HC(bad), -8.8271, 115.15709, 15)
ids = {x["sensor_id"] for x in s}
assert "bad-aq-1" not in ids, "stale must be dropped"
assert "bad-pa-46949" not in ids, "42 km away must be outside a 15 km radius"
# a station the archive suspects is indoors is not the street, so it is dropped by default. It is still a real
# station someone may want, so BAD_INCLUDE_INDOOR=1 brings it back with the flag intact.
assert "bad-iqs-x" not in ids, "suspected_indoor is dropped by default"
s2, _ = B.ring(HC(bad), -8.8271, 115.15709, 15, include_indoor=True)
x = [x for x in s2 if x["sensor_id"] == "bad-iqs-x"][0]
assert x["indoor"] and x["source"] == "baliairdispatch" and x["local"] is False, "same id, same source, never local"

# a Smart Citizen kit the node polls itself must not come back a second time via BAD (it was: sc-19236 and
# bad-sc-19236 were both counted in the ambient average, with BAD's indoor flag disagreeing with Smart Citizen's)
bad2 = {"readings": [
    {"station_id": "sc-19236", "name": "Ungasan Kit", "source": "Smart Citizen", "latitude": -8.8198, "longitude": 115.1666, "observed_at": "2026-09-05T02:00:00Z", "stale": False, "pm25": 7.0},
    {"station_id": "sc-19760", "name": "Bayu Sensor", "source": "Smart Citizen", "latitude": -8.8100, "longitude": 115.1600, "observed_at": "2026-09-05T02:00:00Z", "stale": False, "pm25": 8.0}]}
s, r = B.ring(HC(bad2), -8.8271, 115.15709, 15, skip_station_ids={"sc-19236"})
ids = {x["sensor_id"] for x in s}
assert "bad-sc-19236" not in ids, "a kit this node reads directly must be skipped from BAD"
assert "bad-sc-19760" in ids, "someone else's kit still comes through BAD"

# ---- 2. fetch(): off unless BAD_ENABLED=1; on, the node's own kits are skipped as the core did
for k in ("BAD_ENABLED", "SC_DEVICES", "SC_USER", "AIRGRADIENT_HOSTS"):
    os.environ.pop(k, None)
os.environ.update(NODE_LAT="-8.8271", NODE_LON="115.15709")
assert B.fetch(HC(bad2)) == ([], []), "off by default: a node outside Bali asks nothing"
os.environ.update(BAD_ENABLED="1", SC_DEVICES="19236")
s, _ = B.fetch(HC(bad2))
assert [x["sensor_id"] for x in s] == ["bad-sc-19760"], s
assert [a["verdict"] for a in B.audit(HC(bad2))] == ["excluded: identity (this node polls it)", "included"]

# ---- 3. the loader: an official pack with its own switch runs its code without PACKS_ALLOW_CODE; a wild one does not
os.environ["PACKS_ALLOW_CODE"] = "0"
os.environ.pop("PACKS_ENABLED", None)
tmp = Path(tempfile.mkdtemp())
shutil.copytree(ROOT / "packs/bali-air-dispatch", tmp / "bali-air-dispatch")
packs.PACKS_DIR = tmp
assert [n for n, _ in packs.adapters(HC(bad2))] == ["bali-air-dispatch"], "official, switch on: it runs"
st = packs.stations()
assert st and st[0]["pack"] == "bali-air-dispatch" and st[0]["source"] == "baliairdispatch" and st[0]["on"] \
    and st[0]["prefix"] == "bad-" and st[0]["radius"] == "BAD_RADIUS_KM" \
    and st[0]["attribution"] == ["Bali Air Dispatch, baliairdispatch.com"], st   # one line, as /nearby always said it
os.environ["BAD_ENABLED"] = "0"
assert packs.adapters(HC(bad2)) == [], "switch off: it waits for PACKS_ALLOW_CODE like any code pack"
assert packs.stations()[0]["on"] is False
os.environ["BAD_ENABLED"] = "1"
(tmp / "bali-air-dispatch/.wild").write_text("")
assert packs.adapters(HC(bad2)) == [], "a wild pack never runs code on its own switch"
shutil.rmtree(tmp)

# ---- 4. its channels are its own, and the core no longer names it
core = (ROOT / "config/channels.yml").read_text()
assert "baliairdispatch" not in core and "baliairdispatch" in (ROOT / "packs/bali-air-dispatch/channels.yml").read_text()
for f in glob.glob(str(ROOT / "app/*.py")) + glob.glob(str(ROOT / "app/issues/*.py")):
    hit = re.search(r"baliairdispatch|BAD_[A-Z]|bad_verdicts|\"bad-\"", Path(f).read_text())
    assert not hit, f"{f} still names Bali Air Dispatch: {hit.group(0)}"
assert "BAD_" not in (ROOT / ".env.example").read_text(), "the pack declares its own settings"
for k in ("BAD_ENABLED", "BAD_RADIUS_KM", "BAD_MIN_SEPARATION_M", "BAD_EXCLUDE", "BAD_INCLUDE_INDOOR"):
    assert k not in settings.RUNTIME, k
os.environ["PACKS_DIR"] = str(ROOT / "packs")
assert {r["key"] for r in settings.pack_settings() if r["pack"] == "bali-air-dispatch"} == \
    {"BAD_ENABLED", "BAD_RADIUS_KM", "BAD_MIN_SEPARATION_M", "BAD_EXCLUDE", "BAD_INCLUDE_INDOOR"}, "Set up still shows all five"
assert settings.writable("BAD_EXCLUDE")

print("test_bali_air_dispatch: ok")
