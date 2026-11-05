#!/usr/bin/env bash
# The host gateway against a real Mosquitto and a fake radio: packets from the "radio" reach the broker as the JSON
# app/main.py subscribes to; the node's downlink reaches the radio as sendText; a peer's fabcity line is re-sent on
# channel 1; a peer's position is not. Also: the bridge blocks `federate` writes are a config Mosquitto accepts.
# Run: bash tests/test_radio_gateway.sh    (needs mosquitto on PATH and the meshtastic + paho-mqtt packages)
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
command -v mosquitto >/dev/null || { echo "radio gateway: skipped (no mosquitto on PATH)"; exit 0; }
python3 -c 'import meshtastic, paho.mqtt' 2>/dev/null || { echo "radio gateway: skipped (no meshtastic / paho-mqtt package)"; exit 0; }
T=$(mktemp -d); trap 'kill $(cat $T/pid 2>/dev/null) 2>/dev/null; rm -rf $T' EXIT
# a free port, not a fixed one: a broker left over from an interrupted run must not answer for this one
P=$(python3 -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1",0)); print(s.getsockname()[1])')
P2=$(python3 -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1",0)); print(s.getsockname()[1])')
printf 'listener %s 127.0.0.1\nallow_anonymous true\n' "$P" > $T/m.conf
mosquitto -c $T/m.conf >$T/m.log 2>&1 & echo $! > $T/pid; sleep 1
kill -0 "$(cat $T/pid)" 2>/dev/null || { echo "radio gateway: mosquitto did not start on $P"; cat $T/m.log; exit 1; }
export RADIO_TEST_PORT=$P
export PLANETAI_ROOT=$T; mkdir -p $T/config/radio; printf 'NODE_NAME=testnode\nNODE_CITY=bali\nMQTT_USER=\nMQTT_PASS=\n' > $T/.env
python3 tools/radio.py init >/dev/null

PYTHONPATH=tools python3 - <<'EOF'
import json, os, threading, time, sys
import paho.mqtt.client as mqtt
from pubsub import pub
import radio
import meshtastic.serial_interface

sent = []
class FakeIface:
    def __init__(self, port): pass
    def getMyNodeInfo(self): return {"num": 0x0A1B2C3D, "user": {"id": "!0a1b2c3d"}}
    # the radio's NodeDB, as the Python API holds it: itself, and a stranger's radio heard on the channel
    nodes = {"!0a1b2c3d": {"num": 0x0A1B2C3D, "user": {"id": "!0a1b2c3d", "longName": "testnode gateway", "shortName": "GATE", "hwModel": "SEEED_XIAO_S3"}},
             "!99999999": {"num": 0x99999999, "user": {"id": "!99999999", "longName": "a stranger", "shortName": "STR"}}}
    def sendText(self, text, channelIndex=0, **kw): sent.append((channelIndex, text))
    def close(self): pass
meshtastic.serial_interface.SerialInterface = FakeIface

got = []
w = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="watcher")
w.on_message = lambda c, u, m: got.append((m.topic, m.payload))
P = int(os.environ["RADIO_TEST_PORT"])
w.connect("127.0.0.1", P); w.subscribe([("msh/#", 0), ("fabcity/#", 0)]); w.loop_start()

fleet = radio.load_fleet()
gw = threading.Thread(target=radio.gateway, args=("/dev/fake", fleet, f"127.0.0.1:{P}"), daemon=True); gw.start()
time.sleep(2)

def pkt(portnum, channel=0, **decoded):
    return {"from": 0xDEADBEEF, "fromId": "!deadbeef", "to": 4294967295, "id": 77, "channel": channel, "rxTime": 1760600000, "decoded": {"portnum": portnum, **decoded}}
pub.sendMessage("meshtastic.receive", packet=pkt("TELEMETRY_APP", telemetry={"environmentMetrics": {"temperature": 29.4, "relativeHumidity": 71.2}}), interface=None)
pub.sendMessage("meshtastic.receive", packet=pkt("TEXT_MESSAGE_APP", channel=1, text="hello from Bali"), interface=None)
pub.sendMessage("meshtastic.receive", packet=pkt("POSITION_APP", channel=1, position={"latitudeI": -88004527, "longitudeI": 1151766378}), interface=None)
time.sleep(1)
# at start the gateway says the names it holds for itself and the fleet's radios; its own nodeinfo never comes up USB
names = [json.loads(p)["payload"]["longname"] for t, p in got if t.startswith("msh/") and json.loads(p)["type"] == "nodeinfo"]
assert names == ["testnode gateway"], names
topics = [t for t, _ in got]
assert "msh/SG_923/2/json/planetai/!0a1b2c3d" in topics, topics
tele = [json.loads(p) for t, p in got if t.endswith("/planetai/!0a1b2c3d")][0]
tele = [json.loads(p) for t, p in got if t.endswith("/planetai/!0a1b2c3d") and json.loads(p)["type"] == "telemetry"][0]
assert tele["payload"]["relative_humidity"] == 71.2 and tele["payload"]["block"] == "environment" and tele["sender"] == "!deadbeef"
assert "msh/SG_923/2/json/fabcity/!0a1b2c3d" in topics, "channel-1 text is still stored locally"
assert "fabcity/testnode/text" in topics and json.loads(dict(got)["fabcity/testnode/text"])["text"] == "hello from Bali"
assert not any(t == "fabcity/testnode/text" and b"latitude" in p for t, p in got), "position never federates"
assert "fabcity/testnode/presence" in topics, "presence retained on the broker"

# the node's own alert, exactly as app/main.py mesh_send publishes it
w.publish("msh/SG_923/2/json/mqtt/", json.dumps({"from": 169090125, "type": "sendtext", "payload": "PM2.5 high, close windows", "channel": 0}))
# a peer's line, as the bridge delivers it; and a peer's own echo of ours must not come back to the air
w.publish("fabcity/menorca/text", json.dumps({"node": "menorca", "id": 5, "text": "hola desde Menorca"}))
w.publish("fabcity/testnode/text", json.dumps({"node": "testnode", "id": 77, "text": "hello from Bali"}))
time.sleep(1.5)
assert (0, "PM2.5 high, close windows") in sent, sent
assert (1, "[menorca] hola desde Menorca") in sent, sent
assert len(sent) == 2, sent
assert "fabcity/testnode/alerts" in [t for t, _ in got], "the node's alert is also offered to peers"
# an unplugged radio: the gateway exits, so launchd or systemd starts it again
pub.sendMessage("meshtastic.connection.lost", interface=None)
gw.join(5)
assert not gw.is_alive(), "the gateway outlived its radio"
print("radio gateway: ok")
EOF

# the bridge config parses: start a second broker with it and see it log the bridge, not an error
printf 'RADIO_PEERS=menorca=127.0.0.1:%s:nopass\n' "$P" >> $T/.env
python3 tools/radio.py federate --write >/dev/null
printf 'listener %s 127.0.0.1\nallow_anonymous true\ninclude_dir %s/config/mosquitto/bridges\n' "$P2" "$T" > $T/b.conf
timeout 3 mosquitto -c $T/b.conf -v > $T/b.log 2>&1 || true
# the bridge connected to the peer and subscribed to the peer's fabcity/ topics only: config accepted and working
grep -q "Received CONNACK on connection local.planetai-testnode-to-menorca" $T/b.log \
  && grep -q "Topic: fabcity/menorca/#" $T/b.log && ! grep -q "Topic: msh/" $T/b.log \
  && echo "radio federate: bridge connects, fabcity/ only" || { cat $T/b.log; exit 1; }
