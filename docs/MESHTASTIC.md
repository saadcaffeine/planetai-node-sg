# Radios
<!-- checked: v0.91.0 -->

This page puts LoRa radios on the node with Meshtastic. Once they are on, a sensor can report from a field or a
roof with no WiFi, every reading is filed under the radio that measured it, and the node can send an alert to a
radio on the shelf when the internet is down. `planetai radio` does the setup and checks each step.

Two rules come first. Put the antenna on before power, always. And give every radio the same region, the same
frequency slot and the same channels, region first, or it never transmits.

## Which board does what

The firmware is the same for every job on a board. The job is in the settings, and `planetai radio provision`
writes them.

| board | chip | WiFi | GPS | job |
|---|---|---|---|---|
| XIAO ESP32-S3 + Wio-SX1262 | ESP32-S3 | yes | no | the gateway (one per node, carries the mesh to the node), or a sensor node with an I²C sensor, like the Bayu sensor from Fab Lab Bali. With no GPS, a sensor node is given `--fixed LAT,LON` |
| Wio Tracker L1 (L1, Lite, e-ink) | nRF52840 | no | yes | a field sensor: a 3.3 V sensor on the Grove port, on a battery, where there is no WiFi |
| Wio Tracker L1 Pro, SenseCAP T1000-E | nRF52840 | no | yes | a shelf radio, paired to a phone, that receives alerts when the internet is down |

The L1 variants are one board with different screens. The nRF52 boards have no WiFi, so they reach the node
through a gateway: the XIAO over WiFi, or any radio plugged into the node's own USB (`planetai radio gateway`).

## Firmware

**Data › Workbench** on the node's dashboard (`/#data/workbench`) flashes the XIAO from Chrome or Edge over USB and
gives you the `.uf2` and `-ota.zip` files for the trackers, all from the one Meshtastic release every radio shares
(2.7.26). It needs no internet, because the node keeps its own copy of the firmware. The same workbench, with a demo
and the long explanations, is at **`planetai.fab.city/sensors/`**. Put every radio on that version. The workbench
leaves region and channel empty, because those come from the node in the next section. It also has firmware for the
Heltec V3, LilyGO T-Beam, RAK4631 and LilyGO T-Echo; the three boards above are the ones a node has run. Chrome opens
a USB port only on `localhost` or https, so from another laptop on the LAN follow the first step of
[Flash and test a board](site/sensors.md#flash-and-test-a-board).

A Tracker takes its file by drag and drop: double-click RST and copy the `.uf2` onto the drive that appears. On
macOS 26 the copy fails with error -36 (Input/output error) whatever the bootloader version, so use serial DFU
instead. Double-click RST, then:

```bash
pip3 install --user adafruit-nrfutil
adafruit-nrfutil dfu serial --package firmware-seeed_wio_tracker_L1-<ver>-ota.zip -p /dev/cu.usbmodem1101 -b 115200 --singlebank
```

If the XIAO shows no port, hold BOOT while you plug it in. Never use the phone app's over-the-air update on these
boards, Seeed says it can brick them.

## Your first radios, step by step

Run `planetai radio` at any point. It ticks what is done, lists the radios on USB right now, and ends with the next
command, port filled in. Everything below runs on the node's machine, with the radios plugged into it.

1. **The packages, once.** `planetai radio` names what to install for its own Python. On a Mac with Apple's Python
   3.9 that is `python3 -m pip install --user "pyobjc-core<12" "pyobjc-framework-Cocoa<12"
   "pyobjc-framework-CoreBluetooth<12" "pyobjc-framework-libdispatch<12" meshtastic paho-mqtt`.
2. **The broker.** `planetai meshtastic` gives the node an MQTT broker and a user for it. The gateway delivers what
   the radios hear there. You see the broker's address and password, and `planetai radio` ticks the step.
3. **The fleet.** `planetai radio init` makes one set of channel keys, region and frequency for every radio of this
   node, in `config/radio/fleet.yaml`. On a Bali node you see `region SG_923, slot 19 (921.625 MHz)`. If the node's
   city has no known region it stops and asks for `--region`. It never guesses, because a radio on another
   country's band is illegal there.
4. **The gateway radio.** Antenna on, plug a radio into the node's USB, and run the command `planetai radio`
   prints, for example `planetai radio provision gateway-host "bayu gateway" GATE --port /dev/cu.usbmodem1101`. It
   writes one settings section at a time, 25 s apart, reboots the radio and reads everything back over a new
   connection, about seven minutes in all. You see `>> ok. !abcd1234 booted on it (boot count 6) … channels
   planetai 0xfe and fabcity 0xe7` (your hashes differ). Anything else is a list of what the radio holds that it
   should not; run the command again.
5. **The gateway, always on.** `planetai radio gateway --port /dev/cu.usbmodem1101 --install` makes the gateway a
   service that starts with the machine. You see `the gateway runs as a service now`. Leave this radio plugged in.
   If it is unplugged, the gateway exits and the service starts it again, so it picks the radio up when it is back
   on the same port.
6. **Each other radio.** Plug it in, provision it, unplug it and take it where it goes. A field sensor is
   `planetai radio provision sensor "Subak edge" SBK --port …`. A Tracker has GPS; a XIAO sensor node needs its
   place, south latitudes as written: `--fixed -8.80045,115.17664`. A relay is `relay`, a shelf radio `shelf`. Name
   a sensor for the place where it stands, because that name becomes its name in the node.
7. **Phones.** `planetai radio url` prints the link and three steps (a QR too, if `qrencode` is installed): install
   the Meshtastic app, pair over Bluetooth, open the link and accept replacing the channels.
8. **Check it.** `planetai radio doctor --port …` goes through the usual reasons nothing arrives, one by one, and
   the Network view of the workbench, at `http://<this node>:8080/#data/workbench`, draws every radio the node hears. A sensor's first reading comes
   within its 15-minute interval.

If `planetai radio` lists no port, the cause is usually a charge-only cable, a Tracker with its power switch off, a
XIAO that needs BOOT held while you plug it in, or a USB hub in between.

### All the commands

```bash
planetai radio                                           # where you are, and the next command
planetai meshtastic                                      # the broker and its user
planetai radio init                                      # the fleet: region from NODE_CITY, slot, two channel keys
planetai radio list                                      # the fleet's radios
planetai radio render sensor "Subak edge" SBK            # print a profile without touching a radio
planetai radio provision gateway-host "bayu radio" NODE --port /dev/cu.usbmodem1101
planetai radio provision gateway-wifi "roof gateway" ROOF --port … --wifi SSID:PSK   # fills in the broker itself
planetai radio gateway --port /dev/cu.usbmodem1101 --install
planetai radio provision sensor "Subak edge" SBK --port /dev/cu.usbmodem1101             # a Tracker: it has GPS
planetai radio provision sensor "Warung roof" WRG --port … --fixed -8.80045,115.17664    # a XIAO sensor node: pin it
planetai radio provision shelf "kitchen shelf" SHF --port /dev/cu.usbmodem1101
planetai radio url                                       # for phones: the link, the QR, the three steps
planetai radio doctor --port /dev/cu.usbmodem1101
planetai radio federate --write                          # bridge the fabcity channel to other nodes
```

Provisioning writes one settings section per call, then reboots, then compares every setting and each channel's
key (by its one-byte hash) over a new connection. It works this way because firmware 2.7.26 can lose a settings
transaction when the port closes, and a readback on the same connection shows the library's cached copy instead of what the radio holds.

## The fleet

`config/radio/fleet.yaml` is mode 600 and gitignored, because it holds the keys. It has two channels, each with its
own 256-bit key.

- `planetai` is the primary channel, the household's. It carries telemetry and full position (precision 32).
  Radios send telemetry on channel 0 only, so a private channel added as secondary carries no sensor data.
- `fabcity` is secondary. It is the one that crosses to other nodes, with position capped at 13 bits (about
  2.9 km).

Regions: Bali `SG_923`, Barcelona and Menorca `EU_868`, Boston `US`, Santiago `ANZ`. Bali's slot is pinned inside
Indonesia's 920 to 923 MHz, because SG_923 spans 917 to 925 MHz and a slot hashed from the channel name can land
outside the allocation.

A radio set up with the old `mesh-provision.sh` script is on the old key and the hashed slot. Provision each one
again, the gateway last.

Indoor radios go in `MESH_INDOOR_NODES=!id,!id` in `.env`; a radio does not know which side of a wall it is on.

To reach other nodes, put `RADIO_PEERS=menorca=<tailnet host>:1883:<their MQTT_PASS>` in `.env` and run `planetai
radio federate --write`. It bridges this node's broker to theirs over the tailnet. Text and alerts on the `fabcity`
channel cross, at most six lines a minute; readings and positions never do. `docs/SPEC_radio.md`
has the design.

## What the node files from a radio

Every reading is filed under the radio that measured it, by the name it was given when it was provisioned; the
gateway only passes it on. The map is `MESH_METRICS` in `app/sources.py`, read against firmware 2.7.26.

![From a sensor radio over LoRa and the gateway to the node](site/img/radio-path.svg "The gateway only passes readings on; each one is filed under the radio that sent it.")

| on the radio | metrics |
|---|---|
| the radio itself | `battery_v`, `battery_pct`, `lora_util_pct`, `lora_channel_pct` |
| BME280, BME680, SHT4x, AHT10 | `temp`, `humidity`, `pressure`, and a BME680's `gas_resistance` in kΩ |
| SEN5x | `pm1`, `pm25`, `pm4`, `pm10`, `tvoc_index`, `nox_index` |
| Plantower, HM3301 | `pm1`, `pm25`, `pm10` |
| SCD4x | `co2` |
| SFA30 | `hcho`, in ppb |
| INA219, INA260 | `voltage` and `current`: what it is wired to, never the radio's battery |
| other environment sensors | `light`, `white_light`, `uv_lux`, `wind_speed`, `wind_direction`, `rainfall_1h`, `rainfall_24h`, `soil_moisture`, `soil_temp`, `distance` (mm, a water level), `weight` (kg), `radiation` (µR/h) |

The sensor profile turns on environment and air-quality telemetry every 15 minutes. The firmware leaves air quality
off, and without it a PM, CO2 or formaldehyde sensor sends nothing, so a sensor radio
provisioned without it needs provisioning again.

The Tracker's Grove port is 3.3 V. Seeed rates the Grove HM3301 for 3.3 V or 5 V, and its Grove SEN54 and SEN55
carry a regulator for a 3.3 V supply, so a PM sensor can go on a Tracker. A SEN54 on a Tracker once did not appear at
all and the reason was never found, so try one before fitting a batch. A PM sensor's fan runs whenever it measures,
which a battery feels. The gateway can carry a sensor too, under the same rules: keep its role `CLIENT` and mark it
indoor.

Do not fit an MLX90632. It sends the temperature of whatever it points at as the radio's `temperature`, nothing in
the packet says so, and the node would file a surface as `temp`. An MLX90614 is safe, because its object
temperature travels in a block the gateway does not pass on.

## The workbench

The Network view of Data › Workbench (`http://<this node>:8080/#data/workbench`) draws every device the node reads:
mesh radios through the gateway, sensors that publish to the node, the platforms and stations it reads, the nodes it
lists and any board on this laptop's USB. The Test view reads a board on USB, with each sensor animated and a
checklist for sensors found, WiFi, clock and publishing. USB needs the page on `localhost`, or on another address
that Chrome was told to trust once ([Sensors](site/sensors.md#flash-and-test-a-board)). `/tester`, the old address of
the bench, sends you to the workbench.

## With the phone app

`planetai radio url` is the quick way: region, slot and keys arrive together. The steps below are for a radio with
no node in reach.

Pair over Bluetooth first; the radio appears as `Meshtastic_xxxx`. A radio with a screen shows the PIN, one
without (L1 Lite, XIAO) uses `123456`.

1. **Region.** *Radio configuration → LoRa → Region*, before anything else. A radio with no region does not
   transmit, and nothing tells you.
2. **Prove two radios hear each other** on the default `LongFast` channel, a few metres apart: the other appears
   under Nodes within a minute. If it does not, check the region on both, the firmware version, the antennas and
   the distance.
3. **The channel.** Edit the primary channel (`LongFast`, index 0): rename it and generate a 256-bit key. Share it
   by QR to every other radio.
4. **A field sensor.** Role `SENSOR`, GPS on, position every 30 minutes, *Telemetry → Environment* on at 15
   minutes and *Telemetry → Air quality* on at 15 minutes. Plug the Grove sensor in before power-up, because I²C
   is scanned at boot.
5. **The gateway**, in this order: region, channel, name, then WiFi last. On an ESP32, turning WiFi on turns
   Bluetooth off; from then on use the web client at the radio's IP, or USB. *Module → MQTT*: the address from
   `planetai meshtastic`, JSON output on, encryption off. *Channels → primary*: uplink on, downlink on.

## When nothing arrives

- Region `0` (unset) on a radio means it never transmits. `meshtastic --get lora.region` prints a number: `0` is
  unset, `18` is SG_923. In `device.role`, `6` is SENSOR.
- The Tracker has a physical power switch. Lift it, and charge from a normal charger.
- `error -36` when a copy sometimes works is the drive vanishing on reboot; when it fails every time it is macOS
  26. Use serial DFU.
- To read a XIAO over USB, turn on its serial console (`device.serial_enabled`) and, on newer firmware, the debug
  log (`security.debug_log_api_enabled`), then `stty -f /dev/cu.usbmodemXXX 115200 raw -echo; cat
  /dev/cu.usbmodemXXX`.
- With the plain `meshtastic` CLI on 2.7.26, write one section per call, add `--reboot`, then read on a new
  connection and check that `myInfo.rebootCount` went up. A LoRa change takes effect only after that reboot, and
  `--info` or `--get` in the same session reads the CLI's own copy.
- The gateway service logs to `out/radio.log` on a Mac.

## Limits

A LoRa frame is about 200 bytes, and a radio sends a few a minute. That is enough for telemetry and one-line alerts.
Hourly means between nodes go over Tailscale ([Networking](NETWORKING.md)).
