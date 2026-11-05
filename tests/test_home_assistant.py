"""packs/home-assistant: what it publishes, when it stays silent, and that no node loses it on update.

Home Assistant left the core on 22 Oct 2026. It hears the node through packs.emit at two points, after every stored
batch and with every alert, and it runs only while HA_DISCOVERY is 1. A node that lists its packs in PACKS_ENABLED
would lose it on that update, so update.sh step 5b adds it wherever its switch is on. Both halves are checked here:
the messages, against a fake MQTT publisher, and the update step, run for real by bash against a stubbed database.

    PACKS_DIR=packs PYTHONPATH=app python3 tests/test_home_assistant.py
"""
import json
import os
import subprocess
import sys
import tempfile
import time
import types

os.environ.update(MQTT_HOST="mosquitto", NODE_NAME="test-node", PACKS_DIR="packs")
sys.path.insert(0, "app")

SENT = []
paho = types.ModuleType("paho"); mqtt = types.ModuleType("paho.mqtt"); pub = types.ModuleType("paho.mqtt.publish")
pub.multiple = lambda msgs, **kw: SENT.extend(msgs)
pub.single = lambda *a, **kw: None
sys.modules.update({"paho": paho, "paho.mqtt": mqtt, "paho.mqtt.publish": pub})

import settings  # noqa: E402
import packs     # noqa: E402

ROWS = {"HA_DISCOVERY": "1", "PACKS_ENABLED": ""}
settings._cache = {"at": time.time() + 1e9, "rows": ROWS}


def fresh():
    SENT.clear()
    packs._HOOKS.update(at=0.0, on=[])


SENSORS = [{"sensor_id": "sc-1", "name": "Kitchen", "local": True, "kind": "sensor", "indoor": True, "source": "smartcitizen"},
           {"sensor_id": "bad-pa-9", "name": "Neighbour", "local": False, "kind": "sensor", "source": "baliairdispatch"}]
READINGS = [("2026-10-22T05:00:00+00:00", "sc-1", "pm25", 7.0), ("2026-10-22T05:05:00+00:00", "sc-1", "pm25", 8.5),
            ("2026-10-22T05:05:00+00:00", "sc-1", "temp", 31.2), ("2026-10-22T05:05:00+00:00", "bad-pa-9", "pm25", 40.0)]

# ---- 1. readings: one entity per local metric, announced once, its latest state; a public station is left out
fresh()
packs.emit("on_readings", SENSORS, READINGS)
topics = [m["topic"] for m in SENT]
assert "homeassistant/sensor/planetai_test_node_sc_1_pm25/config" in topics, topics
assert "homeassistant/sensor/planetai_test_node_sc_1_temp/config" in topics, topics
assert not any("bad_pa_9" in t or "bad-pa-9" in t for t in topics), "a public station became one of this house's entities"
state = {m["topic"]: m["payload"] for m in SENT if not m["topic"].endswith("/config")}
assert state == {"planetai/test-node/sc-1/pm25": "8.5", "planetai/test-node/sc-1/temp": "31.2"}, state
cfg = json.loads(next(m["payload"] for m in SENT if m["topic"].endswith("sc_1_pm25/config")))
assert cfg["unit_of_measurement"] == "µg/m³" and cfg["device_class"] == "pm25" and cfg["device"]["suggested_area"] == "Indoor", cfg
assert all(m.get("retain") for m in SENT), "Home Assistant must see them again after a restart"
SENT.clear()
packs.emit("on_readings", SENSORS, READINGS)
assert not any(m["topic"].endswith("/config") for m in SENT), "an entity was announced twice: the pack's module was reloaded"
print("home-assistant: local metrics as entities, announced once, latest state, public stations left out")

# ---- 2. an alert: one text sensor with its level and id
fresh()
packs.emit("on_alert", "act", "It is too hot inside.\nOpen the windows.", 42)
alert = {m["topic"]: m["payload"] for m in SENT}
assert alert["planetai/test-node/alert"] == "It is too hot inside.", alert
attrs = json.loads(alert["planetai/test-node/alert/attributes"])
assert attrs["level"] == "act" and attrs["alert_id"] == 42, attrs
print("home-assistant: the alert's first line, with level and id as attributes")

# ---- 3. silent when its switch is off, or when this node's pack list leaves it out
fresh(); ROWS["HA_DISCOVERY"] = "0"
packs.emit("on_readings", SENSORS, READINGS); packs.emit("on_alert", "act", "x", 1)
assert not SENT, f"HA_DISCOVERY=0 and it still published {len(SENT)} messages"
fresh(); ROWS.update(HA_DISCOVERY="1", PACKS_ENABLED="air-quality,heat")
packs.emit("on_alert", "act", "x", 1)
assert not SENT, "a node whose PACKS_ENABLED leaves the pack out still published"
ROWS["PACKS_ENABLED"] = ""
print("home-assistant: silent with its switch off, and when the node's pack list leaves it out")

# ---- 4. a pack that fails never stops the node's own work
fresh()
mod = next(m for name, m in packs._hook_modules() if name == "home-assistant")
real, mod.on_alert = mod.on_alert, lambda *a: 1 / 0
packs.emit("on_alert", "act", "x", 1)          # must not raise
mod.on_alert = real
print("home-assistant: a hook that raises is logged, and the alert still goes out")

# ---- 5. update.sh step 5b: the pack joins a listed PACKS_ENABLED where its switch is on, and only there
src = open("update.sh").read()
block = src[src.index("# 5b."):src.index("# 6. rebuild and restart")]
STUB = r'''
docker() {   # docker compose exec -T db psql -U planetai -tAc "<sql>" planetai, against a key=value file
  local sql=""; for a in "$@"; do case "$a" in SELECT*|UPDATE*) sql="$a";; esac; done
  if [[ "$sql" == SELECT* ]]; then k="$(sed -E "s/.*key = '([A-Z_]+)'.*/\1/" <<< "$sql")"; sed -n "s/^${k}=//p" "$DB"
  else add="$(sed -E "s/.*\|\| ',([a-z-]+)'.*/\1/" <<< "$sql")"; sed -i.bak -E "s/^(PACKS_ENABLED=.+)$/\1,${add}/" "$DB"; rm -f "$DB.bak"; fi
}
'''


def run(db: str, env: str) -> tuple[str, str, str]:
    with tempfile.TemporaryDirectory() as d:
        open(os.path.join(d, "db"), "w").write(db)
        open(os.path.join(d, ".env"), "w").write(env)
        out = subprocess.run(["bash", "-c", STUB + block], cwd=d, env={**os.environ, "DB": os.path.join(d, "db")},
                             capture_output=True, text=True, check=True).stdout
        return out, open(os.path.join(d, "db")).read(), open(os.path.join(d, ".env")).read()


LIST = "PACKS_ENABLED=air-quality,heat\n"
out, db, _ = run("HA_DISCOVERY=1\n" + LIST, "")
assert "PACKS_ENABLED=air-quality,heat,home-assistant" in db, db
out2, db2, _ = run(db, "")
assert db2 == db and not out2.strip(), "a second update changed the list again"
_, _, env = run("", "HA_DISCOVERY=1\n" + LIST)
assert "PACKS_ENABLED=air-quality,heat,home-assistant" in env, env
_, db, env = run("HA_DISCOVERY=0\n" + LIST, LIST)
assert "home-assistant" not in db + env, "added with its switch off"
_, db, _ = run("HA_DISCOVERY=1\nPACKS_ENABLED=\n", "")
assert "home-assistant" not in db, "an empty list is every pack and must stay empty"
_, db, _ = run("BAD_ENABLED=1\nHA_DISCOVERY=1\n" + LIST, "")
assert "PACKS_ENABLED=air-quality,heat,bali-air-dispatch,home-assistant" in db, db
print("update.sh 5b: added where its switch is on and the node lists its packs, once; never to an empty list")
print("home-assistant: every check passed")
