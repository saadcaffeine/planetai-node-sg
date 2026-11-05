"""packs/smartcitizen: the household's own kits, read the same way, by every node that read them before.

Smart Citizen left the core on 22 Oct 2026. What must not change is what a node stores: `sc-<kit>`, source
`smartcitizen`, local, indoor or outdoor from the kit's exposure, the same metric names. And no node may miss a reading:
the pack has no on/off key of its own, so its switch is the condition the core used, a kit configured (SC_USER or
SC_DEVICES) or a broker set (MQTT_HOST, for the kits that publish straight to it), and a node that lists its packs gets
it added by update.sh.

    PACKS_DIR=packs PYTHONPATH=app python3 tests/test_smartcitizen.py
"""
import importlib.util
import os
import subprocess
import sys
import tempfile
import time

os.environ.update(PACKS_DIR="packs", NODE_LAT="", PACKS_ALLOW_CODE="0")
sys.path.insert(0, "app")
import settings  # noqa: E402
import packs     # noqa: E402
import sources   # noqa: E402

ROWS = {"PACKS_ENABLED": "", "OPENMETEO_ENABLED": "0", "PACKS_ALLOW_CODE": "0"}
settings._cache = {"at": time.time() + 1e9, "rows": ROWS}

spec = importlib.util.spec_from_file_location("sc_adapter", "packs/smartcitizen/adapter.py")
sc = importlib.util.module_from_spec(spec); spec.loader.exec_module(sc)


class R:
    def __init__(s, j): s.j = j
    def raise_for_status(s): pass
    def json(s): return s.j


KIT = {"name": "Bayu 2 - Indoor", "state": "has_published", "last_reading_at": "2026-09-02T03:11:31Z", "hardware": {"name": "Unknown"},
       "location": {"exposure": "indoor", "latitude": -8.8271, "longitude": 115.15709},
       "data": {"recorded_at": "2026-09-02T03:11:31Z", "sensors": [
           {"id": 234, "measurement": {"name": "PM2.5"}, "value": 7.0}, {"id": 237, "measurement": {"name": "Air Temperature"}, "value": 30.4},
           {"id": 238, "measurement": {"name": "Relative Humidity"}, "value": 63.5}, {"id": 241, "measurement": {"name": "AQI"}, "value": 55},
           {"id": 999, "measurement": {"name": "Unknown"}, "value": 1}]}}
NOW = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
ACCOUNT = {"devices": [{"id": 19880, "state": "has_published", "last_reading_at": NOW},
                       {"id": 19897, "state": "has_published", "last_reading_at": NOW},
                       {"id": 11111, "state": "never_published", "last_reading_at": None}]}


class HC:
    """api.smartcitizen.me: a user answers its account, a device answers KIT under its own id."""
    def __init__(s): s.urls = []
    def get(s, url, timeout=None):
        s.urls.append(url)
        return R(ACCOUNT if "/users/" in url else KIT)


# ---- 1. a kit is stored as it always was
s, r = sc.smartcitizen(HC(), [19880])
assert s[0]["sensor_id"] == "sc-19880" and s[0]["source"] == "smartcitizen" and s[0]["indoor"] and s[0]["local"], s[0]
# the Smart Citizen "AQI" channel is `Bosch BME68X - AQI`, the BME680's own gas index, not an air quality index.
assert {m for _, _, m, _ in r} == {"pm25", "temp", "humidity", "bme_iaq"}, r
print("smartcitizen: sc-<kit>, local, indoor from its exposure, the same metric names")

# ---- 2. fetch: listed kits and the account's recent ones, less the excluded, once each
ROWS.update(SC_DEVICES="19236, 19880", SC_USER="tomasdiez", SC_EXCLUDE="19897")
hc = HC(); s, _ = sc.fetch(hc)
assert sorted(x["sensor_id"] for x in s) == ["sc-19236", "sc-19880"], [x["sensor_id"] for x in s]
ROWS.update(SC_DEVICES="", SC_USER="", SC_EXCLUDE="")
assert sc.fetch(HC()) == ([], []), "no kit configured, nothing asked of the API"
print("smartcitizen: SC_DEVICES plus the account's recent kits, less SC_EXCLUDE")

# ---- 3. the switch is the core's old condition: a kit configured, with no PACKS_ALLOW_CODE
d = packs.PACKS_DIR / "smartcitizen"
for keys, want in (({"SC_USER": "tomasdiez"}, True), ({"SC_DEVICES": "19880"}, True), ({}, False),
                   ({"SC_USER": "", "SC_DEVICES": "0"}, False), ({"MQTT_HOST": "mosquitto"}, True)):
    ROWS.update(SC_USER="", SC_DEVICES="", MQTT_HOST=""); ROWS.update(keys)
    assert packs._official_on(d) is want, (keys, want)
assert not packs._official_on(packs.PACKS_DIR / "forecast"), "a pack with no switch still waits for PACKS_ALLOW_CODE"
ROWS["MQTT_HOST"] = ""
print("smartcitizen: on whenever a kit is configured or a broker is set, with no PACKS_ALLOW_CODE; off with neither")

# ---- 4. no missed reading: the poll still reads the kits, through the same sources.enabled() the core polls with
ROWS.update(SC_DEVICES="19880", SC_USER="")
names = [n for n, _ in sources.enabled(HC())]
assert names.count("smartcitizen") == 1, names
fetch = dict(sources.enabled(HC()))["smartcitizen"]
s, r = fetch()
assert [x["sensor_id"] for x in s] == ["sc-19880"] and r, "the poll lost the kit"
ROWS["PACKS_ENABLED"] = "air-quality,heat"
assert "smartcitizen" not in [n for n, _ in sources.enabled(HC())], "a node that lists its packs without it reads no kit"
ROWS["PACKS_ENABLED"] = ""
print("smartcitizen: the poll reads the kit through sources.enabled(), as the core did, once")

# ---- 5. update.sh step 5b: added wherever a kit is configured and the node lists its packs
src = open("update.sh").read()
block = src[src.index("# 5b."):src.index("# 6. rebuild and restart")]
STUB = r'''
docker() {   # docker compose exec -T db psql -U planetai -tAc "<sql>" planetai, against a key=value file
  local sql=""; for a in "$@"; do case "$a" in SELECT*|UPDATE*) sql="$a";; esac; done
  if [[ "$sql" == SELECT* ]]; then k="$(sed -E "s/.*key = '([A-Z_]+)'.*/\1/" <<< "$sql")"; sed -n "s/^${k}=//p" "$DB"
  else add="$(sed -E "s/.*\|\| ',([a-z-]+)'.*/\1/" <<< "$sql")"; sed -i.bak -E "s/^(PACKS_ENABLED=.+)$/\1,${add}/" "$DB"; rm -f "$DB.bak"; fi
}
'''


def run(db: str, env: str) -> tuple[str, str]:
    with tempfile.TemporaryDirectory() as t:
        open(os.path.join(t, "db"), "w").write(db); open(os.path.join(t, ".env"), "w").write(env)
        subprocess.run(["bash", "-c", STUB + block], cwd=t, env={**os.environ, "DB": os.path.join(t, "db")},
                       capture_output=True, text=True, check=True)
        return open(os.path.join(t, "db")).read(), open(os.path.join(t, ".env")).read()


LIST = "PACKS_ENABLED=air-quality,heat\n"
db, _ = run("SC_USER=tomasdiez\n" + LIST, "")
assert "PACKS_ENABLED=air-quality,heat,smartcitizen" in db, db
assert run(db, "")[0] == db, "a second update changed the list again"
_, env = run("", "SC_DEVICES=19880,19236\n" + LIST)
assert "PACKS_ENABLED=air-quality,heat,smartcitizen" in env, env
_, env = run("", "MQTT_HOST=mosquitto\n" + LIST)
assert "PACKS_ENABLED=air-quality,heat,smartcitizen" in env, "a node with a broker and no kit keeps its direct path"
db, env = run(LIST, LIST)
assert "smartcitizen" not in db + env, "added with no kit configured"
# node #1's own shape: an account, a Set up list of twenty, Bali Air Dispatch already in it
node1 = "SC_USER=tomasdiez\nBAD_ENABLED=1\nHA_DISCOVERY=0\nPACKS_ENABLED=air-quality,coast,heat,bali-air-dispatch\n"
db, _ = run(node1, "PACKS_ENABLED=\n")
assert "PACKS_ENABLED=air-quality,coast,heat,bali-air-dispatch,smartcitizen" in db, db
print("update.sh 5b: smartcitizen added where a kit is configured and the node lists its packs, once; never without a kit")
# ---- 6. the direct path: the node subscribes to the pack's topics and stores what its on_mqtt returns
TOKEN = "a1b2c3"
DIY = b'{"data":[{"recorded_at":"2026-10-22T04:10:00Z","sensors":[{"id":237,"value":28.3},{"id":234,"value":9}]}]}'
ROWS.update(SC_USER="", SC_DEVICES="", MQTT_HOST="mosquitto", HA_DISCOVERY="0"); packs._HOOKS["at"] = 0
assert packs.mqtt_topics() == [("device/sck/#", 1)], packs.mqtt_topics()
got = packs.collect("on_mqtt", f"device/sck/{TOKEN}/readings", DIY)
assert len(got) == 1 and {m for _, _, m, _ in got[0][1]} == {"temp", "pm25"}, got
assert got[0][0][0]["source"] == "smartcitizen-direct" and got[0][0][0]["sensor_id"].startswith("sck-"), "the same ids as in the core"
assert packs.collect("on_mqtt", "msh/x/2/json/LongFast/!a1", b"{}") == [], "a topic no pack reads stores nothing"
os.environ["MQTT_HOST"] = "mosquitto"
merged = {k: v for d in packs.collect("status") for k, v in d.items()}
assert merged["direct"]["messages"] == 1 and merged["direct"]["devices"] == 1, merged
ROWS["MQTT_HOST"] = ""; os.environ.pop("MQTT_HOST"); packs._HOOKS["at"] = 0
assert packs.mqtt_topics() == [] and packs.collect("on_mqtt", f"device/sck/{TOKEN}/readings", DIY) == [], "off: no topic, no dispatch"
src = open("app/main.py").read()
assert "device/sck" not in src.replace("packs/smartcitizen: device/sck/#", ""), "the core names no Smart Citizen topic"
assert 'packs.collect("on_mqtt"' in src and "packs.mqtt_topics()" in src and 'packs.collect("status")' in src
print("smartcitizen: device/sck/# subscribed, stored and counted through the pack, and only while it is on")
print("smartcitizen: every check passed")
