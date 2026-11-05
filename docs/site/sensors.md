# Sensors and sources
<!-- checked: v0.91.0 -->

This page connects the things that measure your place to the node. Once a sensor of yours is polled, the rules
have a room to fire on, and its hourly means can count toward this place's cell in the Fab City Index. Whether
they count is decided by two fields on the sensor's row, `local` and `custody`. What the node knows before any
sensor exists is on [Before a sensor](before-a-sensor.md).

## Connect a sensor

The steps use a Smart Citizen kit, the one sensor the node polls with nothing to install (the `smartcitizen` pack, on as soon as a kit is set). The same checks work
for any source on this page.

1. **Tell the node which kit is yours.** `planetai config set SC_DEVICES 19880` (your kit's id), or
   `SC_USER=<account>` to read every kit on an account. Set up → Sources on the dashboard sets the same keys. The
   terminal answers `SC_DEVICES is now 19880, on this node, within 20 s`, and from the next poll on the node
   treats the kit as yours.
2. **Wait one poll.** Polls run every `POLL_SECONDS` (300 by default). `planetai logs` shows a line
   `smartcitizen: <n> sensors, <n> readings`. A source that fails logs `source smartcitizen failed: …` and the
   others carry on. Polling twice never stores a reading twice.
3. **Check that it is yours and here.** `planetai sensors` prints one line per sensor: id, `kind`, `yours` or
   `reference`, `indoor` or `outdoor`, name. `yours` means `local`: the adapter claimed the kit and it stands
   within `LOCAL_RADIUS_M` (500 m) of the node. A kit on your account 1.2 km away prints `reference`, because it
   is not this node's measurement of this place.
4. **Check that it may be counted.** `planetai sensors --json` carries `"custody": true` on the same row. Every
   cell's claim to `live` depends on that field.
5. **Watch it become a cell.** `planetai cells` prints `Environmental|Community` with a value, a state and the
   unit `µg/m³ PM2.5 (24h mean, sensors in this node's custody)`. The state is `partial` until the node holds 12
   hourly buckets from sensors in its custody in the last 24 hours and enough of those sensors (one on a community
   node with no children, two otherwise), and `live` after that. That row is what a
   parent node and the Index read. The readings under it never leave the machine.

If step 3 says `outdoor` for a kit that is inside, fix it on the Smart Citizen platform. The adapter takes
`indoor` from each kit's own `exposure`, and every air rule depends on it.

## Flash and test a board

A sensor you build yourself, the Bayu or a Meshtastic radio, gets its firmware from the node. Data › Workbench on
the dashboard (`/#data/workbench`) flashes every one of these boards, tests a board over USB and draws the network
the node hears, with no internet. Use Chrome or Edge on a laptop. Phones, Safari and Firefox open the page but have
no Web Serial, so they cannot reach a board.

1. **Open the workbench where the browser allows USB.** On the node machine, `http://localhost:8080/#data/workbench`
   works as it is. From another laptop on the LAN, Chrome opens a USB port only for an address it was told to
   trust, and the Flash view says so in a dashed box with this node's address filled in. Do it once on that
   laptop: open `chrome://flags/#unsafely-treat-insecure-origin-as-secure`, paste the address exactly as the box
   shows it (`http://192.168.1.20:8080`), choose Enabled and press Relaunch. The box is gone and the buttons are
   live. The flag covers that one address, so a node that changes address needs the new one pasted, and a DHCP
   reservation on the router saves you that. Why a flag and not https on the node:
   [the decision](https://github.com/fabcity/planetai-node/blob/main/docs/decisions/2026-10-27-serial-on-the-lan.md).
2. **Flash.** In the Flash view, the Bayu card installs the newest Bayu firmware on a Seeed XIAO ESP32-S3 or an
   ESP32-C3 SuperMini. Plug the board in with a data cable (a charge-only cable shows no port), press Connect and
   flash, pick the port and let it run, about a minute. If no port appears, hold BOOT while you plug it in.
   Reflashing keeps the sensor's saved WiFi, token and name. The ESP32-S3 Meshtastic boards, the XIAO and the
   Heltec, flash the same way. The nRF52840 boards take a `.uf2` file instead: download it from their card,
   double-click the board's reset button, and copy the file onto the drive that appears. Keep every radio in a mesh
   on the same firmware version; radios on different versions stop hearing each other and nothing says so.
3. **Test.** In the Test view, press Connect a board by USB and pick the port that says USB JTAG/serial or
   usbmodem. The board appears as a card marked `port open`, with what it reads, Restart board and Disconnect.
   Save readings (CSV) keeps what it read on this laptop. Pulling the cable turns the card to `unplugged`.
4. **Find it on the network.** The Network view draws what the node knows: every sensor that publishes to it, every
   radio its gateway hears, the platforms and stations it reads, the nodes it lists, and the boards on this
   laptop's USB. A browser cannot scan a network, so a board the node has never heard from is not on the map yet.
   The reads behind it need the token on a node that is not open; the page asks for it.

A flashed Bayu still has to be told where to publish. On first boot it opens its setup portal, and to send its
readings to this node you type what `planetai broker` prints on the node machine (the DIY nodes row under
[What ships](#what-ships)). A Meshtastic radio takes its region and channel from the node, not from this page:
[Meshtastic, the LoRa mesh](channels.md#meshtastic-the-lora-mesh).

The flasher, ESP Web Tools 10.4.0, ships in the node, and the firmware is the node's own copy, refreshed every six hours while the node is online, with each Meshtastic binary checked against
its release's `SHA256SUMS`. Until that first copy is made the firmware comes from where planetai.fab.city reads it,
so a new node needs the internet once. The full workbench, with a demo, a log replay and the long explanations, is
at [planetai.fab.city/sensors](https://planetai.fab.city/sensors/), and the tab links to it when the node can
reach it.

## Who may be counted

`local` is two facts at once. The adapter says whether a sensor is yours, and the node checks whether it is here:
`sources.stamp_local` sets `local` to false for any claimed sensor farther than `LOCAL_RADIUS_M` from the node. It
only ever narrows. A sensor no adapter claimed never becomes local, whatever its coordinates. A claimed sensor with
no coordinates (a radio reaching the node through your own gateway, a purifier on the LAN) stays local, because
there is no distance to measure. A node with no coordinates of its own leaves every claim alone.

`custody` is a generated column, `kind = 'child' OR (local AND kind <> 'peer')`. No adapter writes it, so it
cannot disagree with `local` and `kind`. A child node's hourly means are in custody. A model point, a portal,
somebody else's station across the street, a peer's sensor and a fab lab are not, and none of them can make a cell
say `live`. A node that aggregates children needs in-custody sensors from at least two children before a cell may
say `live`. [Concepts](concepts.md) has the rest of the vocabulary.

## What ships

The poll loop asks `sources.enabled()` which adapters to run: the core ones, then every code pack's adapter. Code
packs run only with `PACKS_ALLOW_CODE=1`, which ships as `0`. The exception is an official pack that names its own
switch: it runs when that switch is on.

| source | turned on by | `kind` | `local` | what it reads |
|---|---|---|---|---|
| Smart Citizen | `SC_DEVICES=19880,…` or `SC_USER=name` (every kit on the account; `SC_EXCLUDE` drops some) | `sensor` | yes, then narrowed by `LOCAL_RADIUS_M` | The public API, no key. Metrics are mapped by measurement name, so SCK 2.1 and 2.3 both work. `indoor` comes from each kit's own `exposure`. No humidity correction: the Seeed HM-3301 is not a Plantower, and the EPA correction was not derived for it. |
| Open-Meteo and CAMS | `OPENMETEO_ENABLED=1` (default) | `model` | never | Weather now at the node's coordinates (core), and PM2.5, PM10, O₃, NO₂, dust and UV from the Copernicus model at 11 km, as `cams-point` (the `air-quality` pack, on the same key). Free, no key, anywhere. Never in an ambient average. |
| NASA POWER | the first-start bootstrap (`BOOTSTRAP=1`) | `model` | never | Forty years of monthly temperature, humidity and rain normals, as `power-point`. |
| CKAN portals | `CKAN_PORTALS=slug=url,…` (five of the six presets name one; `delhi` leaves it blank) | `portal` | never | A portal's upkeep (datasets in total, the share touched in 90 days) for the `open-data-health` pack's `Governance\|City` cell. Scale from `CKAN_SCALE` (`city`). |
| Meshtastic radios | `MQTT_HOST` (set by `planetai meshtastic`) | `sensor` | yes | Telemetry from radios through the gateway, on `msh/#`, each reading filed under the radio that measured it. `MESH_INDOOR_NODES=!id,!id` marks the indoor ones. A radio's own temperature, humidity and pressure are its box, not the street. [Radios](radios.md) has the setup and the metrics. DIY pods publish to `planetai/sensors/<id>/<metric>` on the same broker. |
| DIY nodes, direct | `planetai broker` (the same broker; the `smartcitizen` pack; `SC_FORWARD=<tokens>` passes messages on to smartcitizen.me) | `sensor` | yes (no coordinates, so it stays local) | A Making Sense Bali DIY node with a v4 portal publishes the platform's own topics to this node instead of the cloud: `device/sck/<token>/readings` and a retained `meta` (name, site, height, indoor). Stored with the device's own timestamp. Ids are `sck-<8 hex of the token's hash>`, and the token is never shown. `indoor` comes from `meta`, else outdoor. The parser also reads a Smart Citizen Kit's `readings/raw`, but a kit cannot send a password and this broker refuses anonymous clients, so kits stay on the cloud path. A forwarded device keeps its page on the platform; list its platform id in `SC_EXCLUDE` so the cloud adapter does not read it twice. |
| Bali Air Dispatch (`bali-air-dispatch` pack) | `BAD_ENABLED=1` (the Bali preset sets it; off elsewhere). Runs without `PACKS_ALLOW_CODE` | `sensor` | never | Other people's public stations within `BAD_RADIUS_KM` (15; the Bali preset says 8), the outdoor reference this node is read against. Drops stations the archive suspects are indoor or broken (`BAD_INCLUDE_INDOOR=1` keeps the indoor ones). Keeps this node's own kit out of its ring: the ids it already polls, anything within `BAD_MIN_SEPARATION_M` (150) of the node, and `BAD_EXCLUDE` by hand. See [Packs that ship](packs-reference.md#bali-air-dispatch). |
| Xiaomi purifiers (`xiaomi-air` wild pack, listed at [fabcity/planetai-wild-packs](https://github.com/fabcity/planetai-wild-packs)) | `planetai packs add xiaomi-air`, then `XIAOMI_PURIFIERS=Living Room@192.168.4.98=<token>,…` and `planetai packs install` (installs python-miio) | `sensor` | yes (no coordinates, so it stays local) | Mi Home purifiers read on the LAN over miio/MIoT, always `indoor`: `pm25`, `temp`, `humidity`, `filter_life`, and `pm10` where the model reports it. Ids are `xm-<mac6>`. You extract each unit's 32-hex token once with xiaomi-cloud-tokens-extractor; after that nothing talks to the Xiaomi cloud. The pack lists that line under `secrets:`, so Set up shows it masked once saved. No EPA correction, because the sensor is not a Plantower. |
| ThingData (`thingdata` pack) | `THINGDATA_INSTANCES=slug=url,…` | `portal` | never | A repair-knowledge server's catalogue: things described, guides, stories, and whether anyone is still writing. Scale from `THINGDATA_SCALE` (`city`). |
| Fab labs (`make` pack) | `MAKE_ENABLED=1` and `PACKS_ALLOW_CODE=1`; `MAKE_ENABLED` ships as `0` | `facility` | never | One row per active fab lab within `MAKE_RADIUS_KM` (50), from the Fab Lab Network directory, with no readings. `meta` holds the slug, capabilities, city, distance and the lab's URL, never an email or a phone number. The directory is not openly licensed; read [the report page](report.md#the-nearest-place-to-make-or-fix) before you turn it on. |
| Other code packs | the pack's own settings | as declared | as declared | `coast` (Open-Meteo Marine), `forecast` (BMKG, and Open-Meteo, CAMS air and the sea once `FORECAST_OPENMETEO=1`, which ships as `0`), `earth` (AlphaEarth embeddings), `earth-engine` (Dynamic World, Sentinel-2, VIIRS), `place` (OpenStreetMap into PostGIS), `terrain` (Copernicus DEM GLO-30), `fire` (NASA FIRMS, also `FIRE_ENABLED=1`), `surface-heat` (Landsat and MODIS through Planetary Computer). See [Packs that ship](packs-reference.md). |

**AirGradient and PurpleAir, on the LAN.** The `airgradient` pack reads each host in `AIRGRADIENT_HOSTS` at
`/measures/current`, and the `purpleair` pack each host in `PURPLEAIR_HOSTS` at `/json?live=true`, never through the
cloud. PM2.5 gets the EPA 2021 correction and the raw value is kept as `pm25_raw`; PurpleAir averages its two
Plantower channels first, and stores `channel_disagreement` when they drift apart, because one laser is failing.
`SENSOR_INDOOR=1` marks both kinds as indoors. Each pack is on whenever its hosts are set. Both were core adapters
that v0.16 dropped from the poll by accident, and up to v0.83.0 a host you listed was read by nothing.

The node also carries the network's list of everything that could be measured here, with the code that reads each
entry where any exists: `planetai sources`, or `GET /sources`. [The source registry](sources.md) explains it.

## Channel roles

One metric means different things from different devices. `config/channels.yml`, and a pack's own
`channels.yml`, declare what each `(source, metric)` is, and the node writes the declarations to `channel_roles`
at every start.

| role | meaning | examples |
|---|---|---|
| `ambient` | the air, water or land at a place; comparable between sensors there | Smart Citizen `pm25`, `temp`, `noise`; Bali Air Dispatch `pm25`; a radio's `pm25`; a Xiaomi purifier's `pm25`, `temp`, `humidity` |
| `enclosure` | the inside of the instrument's own box; never averaged as ambient | a radio's `temp`, `humidity`, `pressure`, `gas_resistance`: a BME680 sealed in a radio reports the box |
| `device_health` | the instrument talking about itself | `battery_pct`, `battery_v`, `lora_util_pct`, `lora_channel_pct`, a purifier's `filter_life` |
| `derived` | computed by the node from other readings | `open-meteo-cams` `pm25_model`; every `fc_*` forecast metric |
| `index` | a vendor's own composite, never pooled with anyone else's | `aqi`, `bme_iaq`, `eco2`, `tvoc_index`, `nox_index` |
| `private` | the house's own. The page, rules and cells use it. It stays out of the daily export, a parent's aggregates, the report bundle and every agent's read; `/readings`, `/history`, `/series` and `/sparks` give it to the admin token only, and readouts such as `/stats` to the admin or act token or this machine | a household's inventory counts |

`comparable` says whether two sensors' values of a metric may be compared (`pm25_raw` may not). `reference` names
the sensing element (`plantower`, `sc`, `bme680`). A role is set for a source and metric pair, so a node whose
hardware differs from an adapter's usual shape cannot override it for one device.

## Rules the node inherits

Several of these come from Bali Air Dispatch's methodology.

1. **Indoor sensors measure a room.** Never in an ambient average.
2. **Silence is a value that stops changing.** `stats` has `silent_minutes`, which is true per kit and false per
   channel. Smart Citizen's per-reading timestamp is empty on the kits node #1 reads, so the adapter stamps every
   channel with one kit-level time at each poll. A channel that has stopped producing new values still gets a
   fresh timestamp, and its frozen value is stored again under it. That pulls the 24-hour mean toward the frozen
   number and shrinks its variance, so a dying channel looks steadier. The core rule `trust/channel_dead`
   (`config/rules.yml`) looks at the value instead.
3. **A daily mean can be one reading.** Check `n` before trusting an aggregate.
4. **Instants are UTC, days are local.** Daily buckets use `NODE_TZ`. Bali's 9 am burning peak vanishes on a UTC
   day.
5. **Corrected and raw are both stored.** Raw is never overwritten.
6. **Gaps are real.** No fill, no zero, no interpolation. A gap in a series is a gap in the line.
7. **These are not reference instruments.** They are good for patterns and magnitudes, and the node labels them
   that way.
8. **Sensors in the same place disagree.** Three kits at one address read the same air and one runs about 1.5
   times the other two. Collocation is the cheapest calibration a node can run, and most nodes have it by accident.
   The core rule `trust/peer_disagreement` reads it.

## Where "outside" comes from

Your own outdoor sensors; if there are none, the three nearest public references; if there are none, the model.
The rules, the report's digest and the dashboard all use this order.

## The EPA 2021 humidity correction

Optical PM sensors over-read in humid air, and Bali runs at 45 to 70% RH. `epa_2021_correct(pm_raw, rh)` is the US
EPA 2021 Plantower correction: a raw 28 at Bali humidity becomes about 15. Near-zero raw values in dry air lift to 1
or 2, which is a property of the regression and means nothing for health. It is for Plantower lasers (PurpleAir,
AirGradient, a DIY PMS5003), and not for Smart Citizen, Xiaomi, IQAir, AQICN or Airly. It lives in the
`air-quality` pack, and its callers are the `airgradient` and `purpleair` packs, which borrow it even where
`air-quality` is off.

## Siting

Mount it three to six metres up, away from a kitchen exhaust, a chimney or a parking spot, in outdoor air sheltered
from horizontal rain, and within reach of 2.4 GHz WiFi. Name it after the place: the name becomes the sensor's name
on the page and in every message. For the box, the outdoor sensor enclosure is printable, and Fab Lab Bali
prints it.

## Thresholds the air rules use

| PM2.5 µg/m³ | scale | used for |
|---|---|---|
| 15 | WHO 2021, 24-hour | the "clean" line everywhere; the floor of `inside_worse_ventilate` |
| 35.5 | US EPA, unhealthy for sensitive groups | `indoor_pm25_high`, `outside_worse_keep_shut`, the "moderate" ceiling |
| 55.5 | US EPA, unhealthy | `outdoor_pm25_high` |

A spike is 2.5 times the day's mean and above 12 indoors or 15 outdoors. It says something changed before anything
is unhealthy. Thresholds written for Kuta Selatan are not thresholds for Barcelona, and a pack's README says which
place it was written for.

## Adding a source

An adapter is one function in `app/sources.py` (an open protocol the core speaks, such as CKAN) or in a pack's `adapter.py`
(a source that belongs to a domain, see [Packs](packs.md)), returning two lists:

```python
def my_source(hc: httpx.Client, ...) -> tuple[list[dict], list[tuple]]:
    sensors  = [{"sensor_id": "xx-123", "source": "my_source", "name": "...", "lat": .., "lon": ..,
                 "indoor": False, "local": True, "kind": "sensor", "scale": "community", "meta": {...}}]
    readings = [(ts_utc, "xx-123", "pm25", 12.3), ...]
    return sensors, readings
```

- Readings dedupe on `(sensor_id, metric, ts)`. `sensor_id` is a short source prefix plus the upstream id
  (`sc-19880`), and it is never reassigned.
- Set `local` and `indoor` to what is true. Every rule and every cell depends on them.
- `kind` says how the number was produced: `sensor`, `portal`, `model`, `survey`, `child`, `peer` or `facility` (a
  place with a name and a point, and no number). The `place` pack also writes `map` rows. Only `sensor` rows enter
  the `stats` view.
- Metric names are lowercase with no unit in the name: `pm25 pm25_raw pm10 pm4 pm1 temp humidity pressure aqi
  gas_resistance noise light eco2 tvoc co2 hcho tvoc_index nox_index`. Units are fixed: µg/m³, °C, %, kPa. The
  first pack to ship a metric names it.
- When its key or service is missing, the adapter logs once and returns nothing. It must never take the node down.

Test it against a saved payload from the real device before you open a pull request. Add its metrics' roles to a
`channels.yml`, and file the source in [`awesome-fabcity-data`](https://github.com/fabcity/awesome-fabcity-data) so
the registry, and with it the Index, knows it exists.

## Where this leads

For a sensor that has to stand where there is no WiFi, [Radios](radios.md) is next. Once the node has
something of its own to read, the [dashboard](dashboard.md) draws it against the ring and the region, the
[report](report.md) says it in sentences every few hours, and [alerts](alerts.md) is where the node starts asking
somebody to do something.
