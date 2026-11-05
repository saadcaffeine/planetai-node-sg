# `planetai radio`: one command per radio, the node as the gateway, nodes federated over MQTT
<!-- drafted 16 Oct 2026 against main at 1b0ab45 (v0.81.0); landed on main after aa8e019 the same day. Code and tests pass offline (82 of 82 suites); nothing has touched a radio yet. -->

A node operator plugs a radio into USB, types one line, and the radio is a member of the node's mesh with the
right region, the right frequency slot, the node's channel keys and the settings its job needs. A radio left on
the node's own USB port makes the node the gateway: packets reach the node's broker, alerts go back out, and the
`fabcity` channel reaches other nodes over the tailnet. No public broker, no shared keys between nodes, nothing
finer than a 2.9 km cell leaves a node, and never a reading.

## What exists today, what this changes

| | today (v0.81.0) | with `planetai radio` |
|---|---|---|
| provisioning | the old mesh-provision.sh script, positional args, six `--set` calls, six reboots, env vars for the gateway | `planetai radio provision <role> "<name>" <SHORT> --port …`: one DeviceProfile, written one section per CLI call, one reboot, a readback over a new connection (19 Oct: the single transaction did not hold on firmware 2.7.26) |
| what a radio is told | region, preset, name, role, telemetry, then a channel URL, then MQTT, then WiFi, one at a time | the same, from five role files in `tools/radio_profiles/` and one fleet file; `render` shows it before anything is written |
| the fleet's keys | `~/planetai-mesh.url`, one primary channel | `config/radio/fleet.yaml` (mode 600, gitignored): a primary `planetai` channel and a secondary `fabcity` channel, each with its own 256-bit key, plus region, preset and slot |
| the gateway | an ESP32 on WiFi with JSON output on; nRF52 boards cannot do it | still supported (`gateway-wifi`), and now any board on the node's USB (`gateway-host`): the node runs `planetai radio gateway`, which publishes the same JSON an ESP32 would. `app/main.py` and `app/sources.py` change by zero lines |
| region in Bali | `SG_923`, slot hashed from the channel name, which can fall outside Indonesia's 920–923 MHz | `SG_923` with the slot pinned inside 920–923 (slot 19, 921.625 MHz by the firmware's arithmetic); `doctor` checks it |
| other nodes | nothing: each mesh is an island; the docs say hourly means go over Tailscale | `planetai radio federate`: Mosquitto bridges, node to node over the tailnet, carrying `fabcity/<node>/{text,alerts,presence}` and nothing else |
| the command | `planetai meshtastic` is a wizard that sets the broker up and prints what to type into the phone | stays as it is. `planetai mesh` is Tailscale and keeps its name. The new verbs live under `planetai radio` |

## Decisions taken on 16 Oct 2026

1. **Home: `planetai-node`.** A `tools/radio.py` and five profile files, a test suite, this spec. Not a separate
   repo, not a page. The CLI dispatches `planetai radio …` to the Python file; the Bash stays Bash.
2. **Config only.** Firmware comes from `github.com/meshtastic/firmware/releases` as `docs/MESHTASTIC.md` already
   says. The tool never flashes. Flashing is two commands that differ by chip and the official flasher does them.
3. **The node is the gateway through a radio on its own USB port.** The bridge runs on the host, not in compose:
   macOS does not pass a USB port into a container and node #1 is a Mac mini. `planetai radio gateway --install`
   writes a launchd plist or a systemd user unit. The ESP32 WiFi gateway stays as a second way in.
4. **Two channels, both keyed per node.** Channel 0 `planetai` is the household's: telemetry and position travel
   on the primary and only there (the 5 Sep lesson). Channel 1 `fabcity` is what crosses to other nodes. Its
   position precision is capped at 13 bits (2.9 km), coarser than the resolution-8 cell the site rule allows.
   Nodes never share a key: federation decodes on one side and re-sends as text on the other.
5. **What crosses: text on the fabcity channel, the node's own alerts, a presence line.** Never a reading, never
   a position, never anything from channel 0. `Federation.outbound` enforces it in code and the bridge
   configuration enforces it again at the broker (`fabcity/#` only; `msh/#` never leaves).
6. **Node to node over the tailnet, no hub, no public broker.** `RADIO_PEERS=menorca=<tailnet host>:1883:<their
   MQTT_PASS>,…` in `.env`; `federate --write` renders the Mosquitto bridge blocks. A Fab City hub broker, if one
   is ever wanted, is one more peer, not a different design. `mqtt.meshtastic.org` is ruled out: zero-hop policy,
   no control over what is kept, and the data-sovereignty line the site takes.
7. **Inbound lines are deduplicated and rate-limited** (6 a minute, 200 bytes, prefixed `[node]`). A broker
   delivers a thousand lines a second; a LoRa channel carries a few. The limit is the node's, not the peer's.
8. **The fleet file is a credential**, next to `config/mosquitto/passwd`, and `init --force` means every radio is
   re-provisioned, because the keys and therefore the URL change. The existing Bali fleet re-provisions once.

## The pieces

```
tools/radio.py                  672 lines, Python 3.9, needs `pip3 install --user meshtastic paho-mqtt` on the host
tools/radio_profiles/_base.yaml   serialEnabled on, device telemetry every 15 min
tools/radio_profiles/sensor.yaml  SENSOR, GPS on, environment telemetry every 15 min
tools/radio_profiles/relay.yaml   ROUTER, no GPS, screen off; roof or mast only
tools/radio_profiles/shelf.yaml   CLIENT, Bluetooth on, no position; the household's radio
tools/radio_profiles/gateway-wifi.yaml   ESP32: MQTT to the node's broker, JSON on, WiFi last
tools/radio_profiles/gateway-host.yaml   any board on the node's USB: radio MQTT off, Bluetooth off
tests/test_radio.py             slot arithmetic, fleet, URL round trip, profiles, packet → sources.py, federation, bridges
tests/test_radio_gateway.sh     the gateway against a real Mosquitto and a fake radio; the bridge config loads
config/radio/fleet.yaml         written by `init`; gitignored
config/mosquitto/bridges/       written by `federate --write`; gitignored; `include_dir` added to mosquitto.conf
```

The channel URL is built from the fleet file in Python (`apponly_pb2.ChannelSet`): both channels, the uplink and
downlink bits (on for gateways), the position cap on `fabcity`, and the LoRa config with the pinned slot. The same
URL is what the phone app imports, so a radio provisioned by phone and one provisioned by USB land in the same place.

The profile is a DeviceProfile in meshtastic's camelCase YAML (`render` prints it). `provision` writes it with the
stock CLI, each call a single write: the owner; `--seturl` (channel 0 and the LoRa config); one `--set` call per
config or module section; `--setlat= --setlon= --setalt=` for a pinned radio (the `=` because a south latitude starts
with a minus); then each channel again by `--ch-index N --ch-set …` (2.7.26 lost channel 1 from the URL, and the
Tracker read channel 0's precision 0 after a URL that carried 32). It waits 25 s after each, reads
`myInfo.reboot_count` over a new connection, sends `--reboot`, waits for the count to rise (an ESP32) or the USB port
to drop and return (an nRF52, whose count stays 0), and compares the radio, read over another new
connection, with the profile: every config field, owner, both channels' names and keys (said only as the one-byte
hash, name XOR key), roles, uplink bits and the position cap. Whatever did not hold is written again (only those
steps), rebooted and read back, at most twice: on the sensor XIAO a channel 0 write emptied channel 1, while the same
write kept it on the gateway and the Tracker. It exits non-zero on any difference left.

Why this shape (node #1, firmware 2.7.26, CLI 2.7.11, 19 Oct 2026, on two XIAOs): `--configure` set the owner and the
primary channel and none of the config sections; the API transaction with a 2 s wait lost channel 1; a 20–25 s wait
held on the sensor and not on the gateway. The same writes as separate CLI calls held on both. A readback on the
same connection returns the API's cached `localConfig` (and cached uptime), which is how a wrong radio passed
verify for a day. `commitSettingsTransaction` does not reboot 2.7.26, so a new slot is not on air until a reboot.
The rendered profile repeats region, preset and slot in `config.lora` so that the readback checks them directly.

`planetai radio gateway` subscribes to the Python API's `meshtastic.receive`, turns each decoded packet into the
JSON an ESP32 gateway with JSON output publishes (camelCase to snake_case, the same topic
`msh/<REGION>/2/json/<channel>/<gateway id>`), and publishes it to the node's Mosquitto. `tests/test_radio.py`
feeds that output straight into `meshtastic_message` in `app/sources.py` and checks the readings come out: temperature,
humidity, pressure in kPa, the pm names, the battery-101 sentinel dropped by `sources`, position, nodeinfo. The
node learns `root_topic` and `gateway` from the first packet exactly as before, so `mesh_send` keeps working:
the gateway listens on `msh/<REGION>/2/json/mqtt/` for the node's own `sendtext` and calls `sendText`. nRF52
boards (T1000-E, Tracker L1) can be the host gateway, which the firmware's own MQTT module cannot do.

## What a new node operator types

```bash
pip3 install --user meshtastic paho-mqtt
planetai meshtastic                                   # the broker and its user, as today
planetai radio init                                   # region from NODE_CITY, slot pinned where an allocation is listed
planetai radio provision gateway-host "bayu radio" NODE --port /dev/cu.usbmodem1101
planetai radio gateway --port /dev/cu.usbmodem1101 --install
planetai radio provision sensor "Subak edge" SBK --port /dev/cu.usbmodem1101   # each field radio in turn
planetai radio provision sensor "Warung roof" WRG --port … --fixed -8.80045,115.17664   # a XIAO sensor node: no GPS, so pin it (south as written)
planetai radio provision shelf  "kitchen shelf" SHF --port /dev/cu.usbmodem1101
planetai radio url                                    # the QR for anyone joining by phone
planetai radio doctor --port /dev/cu.usbmodem1101
```

And for two nodes to talk: each puts the other in `RADIO_PEERS`, runs `planetai radio federate --write`, restarts
the broker. A line typed on a Bali shelf radio's fabcity channel shows up on Menorca's radios as `[bayu-ungasan] …`.

## Not yet done, and what needs a radio in hand

- **Nothing here has touched hardware.** The tests prove the arithmetic, the profile format (parsed by the real
  meshtastic CLI's own reader), the JSON contract with `sources.py`, the federation filter, and the gateway
  against a real broker with a fake radio. The first real run is `provision` on the XIAO and on a Tracker L1 with
  `--info` read back, then the gateway for an hour with `planetai sensors` showing a mesh row.
- **The slot formula is arithmetic, not a measurement.** `start + bw/2 + bw*(slot-1)` is the firmware's; the
  radio prints `freq=` on its serial console at boot. Read it once on SG_923 slot 19 and note it in
  `docs/MESHTASTIC.md`. Indonesia's 920–923 MHz is the AS923-2 plan as the node's own docs state it; the
  Kominfo text itself was not read for this. KR (920–923 exactly) was considered and not chosen: it carries
  Korean duty rules and would change the fleet Bali already runs.
- **Re-provisioning the Bali fleet.** New keys mean a new URL; every existing radio is re-provisioned once, and
  the ESP32 gateway last. Same for Menorca if it has radios.
- **A XIAO ESP32-S3 as a sensor node, not the gateway** (the FAB26 ones, Seeed's cased kit) is the same image and
  the `sensor` role; it has no GPS, so `--fixed LAT,LON[,ALT]` writes the DeviceProfile's `location` and sets
  `position.fixedPosition`; provision writes the pin with `--setlat=`, after the position section. `--fixed
  -8.8,115.1` is taken as written (argparse on Python 3.9 once read it as an option). A reading with no place never
  becomes `local` on the node, so the flag is not optional for a XIAO. Added 16 Oct 2026, tested through the
  CLI's own profile reader.
- **`ROUTER` for the relay profile** is the documented choice for a radio up high; the newer `ROUTER_LATE` role
  may be better for a single relay in a small mesh. Decide after the first relay is on a roof.
- **Presence sends no cell yet** (`cell: null`). The node's resolution-3 H3 cell from `NODE_LAT`/`NODE_LON` is a
  one-liner once the h3 package is on the host, or the gateway can ask `/health`. The Reticulum bridge already
  does the same thing at the same resolution; the two should share the rule.
- **The fabcity channel index** is looked up by name in the gateway radio's channel table at start, so a phone
  import that lands it at index 2 still works. The fake radio in the test has no channel table and falls back to
  1; the first real run should log `fabcity is channel 1`.
- **The `planetai doctor`** check `mesh packets arriving` already covers the host gateway, since the packets land
  on the same topic. A second check, "radio gateway service running", is one `launchctl list` / `systemctl
  --user is-active` line.
- `tests/all` runs both suites and declares their skips: a machine without the meshtastic package (or, for the
  gateway suite, mosquitto) skips them whole. A provisioning host should have both.

## Where it ships

Under `docs/NEXT_RELEASE.md` rule 3 this is a `tools/` + `tests/` + `docs/` change: no `app/static`, no pack, no
database. It ships alone. `tests/all` went from 80 to 82 suites on this one branch (rule 1). `docs/MESHTASTIC.md`
replaced its "fast way" with a browser section (`makingsense.fablabbali.com/flash`) and a `planetai radio` section,
and kept everything it learned the hard way; the old mesh-provision.sh script is deleted in the same change.
