# Radios
<!-- checked: v0.80.10 -->

Three boards, three jobs. The board decides the job.

| board | chip | WiFi | GPS | job |
|---|---|---|---|---|
| XIAO ESP32-S3 + Wio-SX1262 | ESP32-S3 | yes | no | **gateway**: uplinks the mesh to the node over WiFi. One per node. |
| Wio Tracker L1 (L1, Lite, e-ink) | nRF52840 | no | yes | **field sensor**: a 3.3 V sensor on the Grove port, on a battery, where there is no WiFi. |
| Wio Tracker L1 Pro (cased, battery) | nRF52840 | no | yes | **shelf radio**: paired to a phone, receives alerts when the internet is down. |

The L1 variants are one board with different displays. nRF52 radios have no WiFi, so they reach the node only through
the gateway.

Two rules that cost hardware if ignored: **antenna on before power**, always. **Same region and same channel on every
radio**, and region first, or the radio never transmits.

## The fast way: a USB cable

```bash
pip3 install --user meshtastic adafruit-nrfutil
```

**Firmware.** Use the stable release from `github.com/meshtastic/firmware/releases`, not what the web flasher offers
first (it offered a 2.8.1 alpha that is not a release). All radios on one version.

Trackers: drag-to-drive fails on macOS 26 (error -36 / Input/output error, whatever the bootloader version: FSKit). Use
serial DFU. Double-click RST, then:

```bash
adafruit-nrfutil dfu serial --package firmware-seeed_wio_tracker_L1-<ver>-ota.zip -p /dev/cu.usbmodem1101 -b 115200 --singlebank
```

XIAO: the web flasher works (it is esptool, not UF2). Hold BOOT while plugging in if no port appears. Never use the phone
OTA app on these boards; Seeed says it can brick them.

**Provision** each radio with one command. The first run makes the fleet channel the **primary** channel with a random
key and saves its URL; every later run imports it:

```bash
tools/mesh-provision.sh /dev/cu.usbmodem1101 "Subak edge"    SBK SENSOR SG_923 ~/planetai-mesh.url
tools/mesh-provision.sh /dev/cu.usbmodem1101 "kitchen shelf"  SHF CLIENT SG_923 ~/planetai-mesh.url
GATEWAY=1 MQTT_ADDR=192.168.4.190:1883 MQTT_PASS=<from planetai meshtastic> WIFI_SSID=<ssid> WIFI_PSK=<pw> \
  tools/mesh-provision.sh /dev/cu.usbmodem1101 "bayu-ungasan gateway" GW CLIENT SG_923 ~/planetai-mesh.url
```

Primary matters: radios send telemetry and position on channel 0 only. A private channel added as secondary never
carries sensor data. Our gateway sat connected for a day publishing nothing because the channel was secondary.

Name field sensors for the **place**: the name becomes the sensor's name in the node. `~/planetai-mesh.url` holds the
fleet key; keep it with `.env`. Regions: Bali `SG_923`, Barcelona `EU_868`, Boston `US`.

Then on the node: `planetai meshtastic` starts the broker and waits for the first packet. Indoor radios go in
`MESH_INDOOR_NODES=!id,!id` in `.env`; a radio does not know which side of a wall it is on.

## The phone app

If you would rather tap. Bluetooth first, then the radio appears as `Meshtastic_xxxx`.

**PIN.** Radios with a screen show it. Radios without (L1 Lite, XIAO) use `123456`.

**Region.** *Radio configuration → LoRa → Region.* Do it before anything else. A radio with region unset does not transmit
and nothing tells you.

**Prove two radios see each other** on the default `LongFast` channel before creating a private one: a few metres apart,
the other appears under Nodes within a minute. If not: region on both, same firmware, antennas, distance.

**Then the channel.** Edit the **primary** channel (`LongFast`, index 0): rename it, generate a 256-bit key. Share by
QR to every other radio.

**Field sensor:** role `SENSOR`, GPS on, position every 30 min, *Telemetry → Environment* on at 15 min. Plug the Grove
sensor before power-up; I²C is scanned at boot.

**Gateway, in this order:** region, channel, name; then WiFi, last. On ESP32 turning WiFi on turns Bluetooth off; from
then on use the web client at the radio's IP, or USB. *Module → MQTT*: address from `planetai meshtastic`, JSON output
**on**, encryption **off**. *Channels → primary → uplink on, downlink on.*

## Sensors on radios

The Tracker's Grove port is **3.3 V**. A SEN54/SEN55 or any fan-driven PM sensor needs 5 V and simply does not appear.
Use BME280/BME680, SHT4x or AHT10 on Trackers. PM belongs on a mains-powered kit. The gateway can carry a sensor too
(same rules; keep its role `CLIENT`; mark it indoor).

## What went wrong, so you skip it

- Region `0` (unset) on both radios: they never saw each other for a week.
- The Tracker has a **physical power switch**. Lift it. Charge from a normal charger.
- `error -36` when a copy *works* is the drive vanishing on reboot; when it fails every time, it is FSKit. Serial DFU.
- The XIAO's serial console is off (`device.serial_enabled`), and newer firmware gates the debug log
  (`security.debug_log_api_enabled`). Turn both on to read the radio over USB:
  `stty -f /dev/cu.usbmodemXXX 115200 raw -echo; cat /dev/cu.usbmodemXXX`.
- `meshtastic --get lora.region` prints numbers: `0` unset, `18` SG_923. `device.role` `6` is SENSOR.

## Limits

A LoRa frame is about 200 bytes, a few a minute. Telemetry and one-line alerts. Hourly means between nodes go over
Tailscale (`NETWORKING.md`).
