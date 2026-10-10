# Sensors and sources
<!-- checked: v0.80.10 -->

This page gives the node its senses. The repo's own sentence for what a node does is that it "connects
everything that measures where you stand, from a particle sensor on the wall to a satellite overhead, into one
picture sharp enough to act on", and a sensor of yours is the part of that picture nobody else has. Once one is
polled, the rules have a room to fire on, and its hourly means can count toward this place's cell in the Fab
City Index. Whether they count is decided by two fields on the sensor's row, `local` and `custody`. What the
node knows before any sensor exists is on [Before a sensor](before-a-sensor.md).

## Connect a sensor

The steps use a Smart Citizen kit, the one source that is polled from the core with nothing to install. The
same checks work for any source on this page.

1. **Tell the node which kit is yours.** `planetai config set SC_DEVICES 19880` (your kit's id), or
   `SC_USER=<account>` to read every kit on an account. Set up → Sources on the dashboard sets the same keys.
   The terminal answers `● SC_DEVICES is now 19880, on this node, within 20 s`. The node now asks Smart Citizen
   for that kit on every poll, and it has already decided the kit is *yours*.
2. **Wait one poll.** Polls run every `POLL_SECONDS` (300 by default). `planetai logs` shows a line
   `smartcitizen: <n> sensors, <n> readings`. A source that fails logs `source smartcitizen failed: …` and the
   others carry on. The readings are now rows in `readings`, and polling twice never duplicates one.
3. **Check that it is yours and here.** `planetai sensors` prints one line per sensor: id, `kind`, `yours` or
   `reference`, `indoor` or `outdoor`, name. `yours` is `local`: the adapter claimed the kit and it stands within
   `LOCAL_RADIUS_M` (500 m) of the node. A kit on your account 1.2 km away prints `reference`, because it is not
   this node's measurement of this place.
4. **Check that it may be counted.** `planetai sensors --json` carries `"custody": true` on the same row. Every
   pack cell's claim to `live` is gated on that one field.
5. **Watch it become a cell.** `planetai cells` prints `Environmental|Community` with a value, a state and the
   unit `µg/m³ PM2.5 (24h mean, sensors in this node's custody)`. The state reads `partial` until the node holds
   12 hourly buckets from sensors in its custody in the last 24 hours, and `live` from then. That row is what a
   parent node and the Index read. The readings under it never leave the machine.

If step 3 says `outdoor` for a kit that is inside, fix it on the Smart Citizen platform: the adapter takes
`indoor` from each kit's own `exposure`, and every air rule depends on it.

## Who may be counted

`local` is two facts at once. The adapter says whether a sensor is *yours*, and the node checks whether it is
*here*: `sources.stamp_local` sets `local` false for any claimed sensor farther than `LOCAL_RADIUS_M` from the
node. It only ever narrows. A sensor no adapter claimed never becomes local, whatever its coordinates. A claimed
sensor with no coordinates (a Meshtastic pod reaching the node over your own gateway, a purifier on the LAN)
stays local, because there is no distance to measure. A node with no coordinates of its own leaves every claim
alone.

`custody` is a generated column, `kind = 'child' OR (local AND kind <> 'peer')`. No adapter writes it and
nothing can make it disagree with `local` and `kind`. A child node's hourly means are in custody; a model point,
a portal, somebody else's station across the street, a peer's sensor and a fab lab are not, and none of them can
make a cell say `live`. A node that aggregates children needs in-custody sensors from at least two children
before a cell may say `live`. That is how a sensor in a living room becomes a row the Fab City Index can trust:
it is yours, it is here, and the node, not the adapter, decides whether it is counted. [Concepts](concepts.md)
has the rest of the vocabulary.

## The adapter contract

One function in `app/sources.py` (or a pack's `adapter.py`), returning two lists:

```python
def my_source(hc: httpx.Client, ...) -> tuple[list[dict], list[tuple]]:
    sensors  = [{"sensor_id": "xx-123", "source": "my_source", "name": "...", "lat": .., "lon": ..,
                 "indoor": False, "local": True, "kind": "sensor", "scale": "community", "meta": {...}}]
    readings = [(ts_utc, "xx-123", "pm25", 12.3), ...]
    return sensors, readings
```

Readings dedupe on `(sensor_id, metric, ts)`. `sensor_id` is a short source prefix and the upstream id (`sc-19880`) and is never reassigned.
`indoor` must be correct; the rules depend on it. `kind` says how the number was produced: `sensor`, `portal`,
`model`, `survey`, `child`, `peer` or `facility` (a place with a name and a point, and no number at all). The
`place` pack also writes `map` rows. Only `sensor` rows enter the `stats` view.

Metric names are lowercase with no unit in the name: `pm25 pm25_raw pm10 pm1 temp humidity pressure aqi
gas_resistance noise light eco2 tvoc co2 tvoc_index nox_index`. Units are fixed: µg/m³, °C, %, kPa. The first
pack to ship a metric names it.

A pack's adapter must log once and return nothing when its key or service is missing. It must never take the
node down.

## What ships

The poll loop asks `sources.enabled()` which adapters to run: the core ones below, then every code pack's
adapter. Code packs run only with `PACKS_ALLOW_CODE=1`, which ships as `0`. In v0.80:

| source | enabled by | `kind` | `local` | what it reads |
|---|---|---|---|---|
| **Smart Citizen** | `SC_DEVICES=19880,…` or `SC_USER=name` (every kit on the account; `SC_EXCLUDE` drops some) | `sensor` | yes, then narrowed by `LOCAL_RADIUS_M` | Public API, no key. Metrics mapped by measurement *name*, so SCK 2.1 and 2.3 both work. `indoor` from each kit's own `exposure`. Not humidity-corrected: the Seeed HM-3301 is not a Plantower and the EPA correction was not derived for it. |
| **Bali Air Dispatch** | `BAD_ENABLED=1` (the Bali preset; `planetai setup` sets `0` elsewhere) | `sensor` | never | The ring: other people's stations within `BAD_RADIUS_KM` (15; the Bali preset says 8), the outdoor reference this node is read against. Drops stations the archive suspects are indoor or malfunctioning (`BAD_INCLUDE_INDOOR=1` keeps the indoor ones). Keeps this node's own kit out of its own ring three ways: the ids it already polls, anything within `BAD_MIN_SEPARATION_M` (150) of the node, and `BAD_EXCLUDE` by hand; plus one rule against a single device arriving under two networks' ids. Stores `pm25` and `pm25_raw`. Attribution: Bali Air Dispatch and the row's network. |
| **Open-Meteo** and **CAMS** | `OPENMETEO_ENABLED=1` (default) | `model` | never | Weather now at the node's coordinates; PM2.5, PM10, O₃, NO₂, dust and UV from the Copernicus model at 11 km, as `cams-point`. Free, key-free, anywhere on Earth. Never in an ambient average. |
| **NASA POWER** | the first-start bootstrap (`BOOTSTRAP=1`) | `model` | never | Forty years of monthly temperature, humidity and rain normals, as `power-point`. |
| **CKAN portals** | `CKAN_PORTALS=slug=url,…` (five of the six presets name one; `delhi` leaves it blank) | `portal` | never | A portal's maintenance state (datasets total, share touched in 90 days) for the `open-data-health` pack's `Governance|City` cell. Scale from `CKAN_SCALE` (`city`). |
| **Meshtastic radios** | `MQTT_HOST` (set by `planetai meshtastic`) | `sensor` | yes | Telemetry from field radios through the gateway's MQTT uplink, `msh/#`. `MESH_INDOOR_NODES=!id,!id` marks the indoor ones. DIY pods publish to `planetai/sensors/<id>/<metric>` on the same broker. A radio's own temperature, humidity and pressure are its enclosure, not the street (see channel roles below). |
| **DIY nodes, direct** | `planetai broker` (the same broker; `SC_FORWARD=<tokens>` to pass messages on to smartcitizen.me) | `sensor` | yes (no coordinates, so it stays local) | A Making Sense Bali DIY node with a v4 portal publishes the platform's own topics and bytes to this node instead of the cloud: `device/sck/<token>/readings` and a retained `meta` (name, site, height, indoor). The parser reads a Smart Citizen Kit's `readings/raw` too, but the kit cannot send a password and this broker refuses anonymous clients, so kits stay on the cloud path for now. Stored with the device's own timestamp. Ids are `sck-<8 hex of the token's hash>`; the token itself is never shown. `indoor` comes from `meta`, else outdoor. Forwarded devices keep their page on the platform; list their platform id in `SC_EXCLUDE` so the cloud adapter does not read them a second time. |
| **Xiaomi purifiers** (`xiaomi-air` wild pack, listed at [fabcity/planetai-wild-packs](https://github.com/fabcity/planetai-wild-packs), core v0.61 to v0.76) | `planetai packs add xiaomi-air`, then `XIAOMI_PURIFIERS=Living Room@192.168.4.98=<token>,…` and `planetai packs install` (installs python-miio) | `sensor` | yes (no coordinates, so it stays local) | Mi Home purifiers read on the LAN over miio/MIoT, always `indoor`: `pm25`, `temp`, `humidity`, `filter_life`, and `pm10` where the model reports it. Ids are `xm-<mac6>`. Each unit's 32-hex token is extracted once with xiaomi-cloud-tokens-extractor; after that nothing talks to the Xiaomi cloud. The line that holds those tokens is listed by the pack under `secrets:`, so Set up shows it masked once saved. No EPA correction: the sensor is not a Plantower. |
| **ThingData** (`thingdata` pack) | `THINGDATA_INSTANCES=slug=url,…` | `portal` | never | A repair-knowledge server's catalogue: things described, guides, stories, and whether anyone is still writing. Scale from `THINGDATA_SCALE` (`city`). |
| **Fab labs** (`make` pack) | `MAKE_ENABLED=1` as well as `PACKS_ALLOW_CODE=1`; `MAKE_ENABLED` ships as `0` | `facility` | never | One row per active fab lab within `MAKE_RADIUS_KM` (50) from the Fab Lab Network directory, with no readings. `meta` holds the slug, capabilities, city, distance and the lab's URL, never an email or a telephone. The directory is not openly licensed; read [the report page](report.md#the-nearest-place-to-make-or-fix) before turning it on. |
| **Other code packs** | the pack's own settings | as declared | as declared | `coast` (Open-Meteo Marine), `forecast` (BMKG, Open-Meteo), `earth` (AlphaEarth embeddings), `earth-engine` (Dynamic World, Sentinel-2, VIIRS), `place` (OpenStreetMap into PostGIS). See [Packs that ship](packs-reference.md). |

> **Gap in v0.80.10.** Two LAN adapters are written and tested but not registered for polling. **AirGradient**
> (`AIRGRADIENT_HOSTS`, read on the LAN, EPA 2021 correction applied with raw kept as `pm25_raw`) and
> **PurpleAir** (`PURPLEAIR_HOSTS`, `/json`, two Plantower channels averaged and corrected) have functions in
> `app/sources.py` and rows in `config/channels.yml`, and `sources.enabled()` never calls them. The AirGradient
> hosts you set are used only to keep those units out of the Bali Air Dispatch ring. `SENSOR_INDOOR` appears under
> Set up → Sources and nothing reads it. The changelog records both adapters as shipped, so read this as a
> regression to be fixed rather than a decision. Today the one indoor PM2.5 source on the LAN that is polled is
> the `xiaomi-air` wild pack.

## What else this place could read

The node carries a pinned copy of the network's registry, `awesome-fabcity-data` (269 entries at `851b8db`,
synced 2026-10-06, in v0.80). `planetai sources` lists the entries for this node's pilot plus the global ones,
with the adapter that reads each where one exists; `--all`, `--pillar`, `--scale` and `--cell
'Environmental|City'` narrow or widen it. It answers from `data/sources` when the node is down. The same list is
`GET /sources`. A row with no adapter is a source the network knows about and no code reads yet. [The source
registry](sources.md) explains the entries and how one gets added.

## Channel roles

A metric means different things from different devices. `config/channels.yml`, and a pack's own
`channels.yml`, declare what each `(source, metric)` **is**, and the declarations are written to
`channel_roles` at every start:

| role | meaning | examples |
|---|---|---|
| `ambient` | the air, water or land at a place; comparable between sensors there | Smart Citizen `pm25`, `temp`, `noise`; Bali Air Dispatch `pm25`; a Meshtastic pod's `pm25`; a Xiaomi purifier's `pm25`, `temp`, `humidity` |
| `enclosure` | the inside of the instrument's own box; never averaged as ambient | a Meshtastic radio's `temp`, `humidity`, `pressure`, `gas_resistance`: a BME680 sealed in a radio reports the box, not the street |
| `device_health` | the instrument talking about itself | `battery_pct`, `battery_v`, `lora_util_pct`, `lora_channel_pct`, a purifier's `filter_life` |
| `derived` | computed by the node from other readings | `open-meteo-cams` `pm25_model`; every `fc_*` forecast metric |
| `index` | a vendor's own composite, never pooled with anyone else's | `aqi`, `bme_iaq`, `eco2`, `tvoc_index`, `nox_index` |

`comparable` says whether two sensors' values of that metric may be compared (`pm25_raw` is not); `reference`
names the sensing element (`plantower`, `sc`, `bme680`). A role is keyed per source and metric, not per
device, so a node whose hardware differs from an adapter's usual shape cannot override it yet.

## Rules the node inherits

Several of these come from Bali Air Dispatch's methodology.

1. **Indoor sensors measure a room.** Never in an ambient average.
2. **Silence is defined by value change, not by a timestamp.** `stats` exposes `silent_minutes`, and that
   number is true per kit and false per channel. Smart Citizen's per-reading timestamp is null on every kit
   node #1 reads, so the adapter stamps every channel with one kit-level time at poll. A channel that has
   stopped producing new values still gets a fresh timestamp on every poll, and its frozen value is
   re-inserted under it, forever. That pulls the 24-hour mean toward the frozen number and shrinks its
   variance, so a dying channel looks steadier, not worse. The `trust` pack's `channel_dead` rule looks at the
   value instead.
3. **A daily mean can be one reading.** Check `n` before trusting an aggregate.
4. **Instants are UTC; days are local.** Daily buckets use `NODE_TZ`. Bali's 9 am burn peak vanishes on a UTC
   day.
5. **Corrected ≠ raw.** Store both. Never overwrite raw.
6. **Gaps are real.** No fill, no zero, no interpolation. A gap in a series is a gap in the line.
7. **These are not reference instruments.** Good for patterns and magnitudes; the node labels them as such.
8. **Sensors in the same place disagree.** Three kits at one address read the same air and do not agree: one
   of them runs about 1.5× the other two. Collocation is the cheapest calibration a node can run, and most
   nodes have it by accident. The `trust` pack's `peer_disagreement` rule is what reads it.

## "Outside" resolves in one order

Your own outdoor sensors; else the three nearest public references; else the model. The same order in the
rules, the report's digest and the dashboard. Averaging every station within 15 km once put an Uluwatu
reading of 3 next to the street's 15.

## The EPA 2021 humidity correction

Optical PM sensors over-read in humid air; Bali runs 45–70% RH. `epa_2021_correct(pm_raw, rh)` implements
the US EPA 2021 Plantower correction: raw 28 at Bali humidity becomes about 15. Near-zero raw in dry air
lifts to 1–2, a property of the regression with no health meaning. It is for Plantower lasers (PurpleAir,
AirGradient, a DIY PMS5003), and not for Smart Citizen, Xiaomi, IQAir, AQICN or Airly. In v0.80 the only
callers are the AirGradient and PurpleAir functions in the gap above, so no polled source applies it.

## Siting

Mount it three to six metres up, away from a kitchen exhaust, a chimney or a parking spot, in outdoor air
sheltered from horizontal rain, and within reach of 2.4 GHz WiFi. Name it after the place: the name becomes the sensor's name on the page and in
every message. For an enclosure, the outdoor-sensor-enclosure work is the printable answer, and Fab Lab Bali
prints it.

## Thresholds the air rules use

| PM2.5 µg/m³ | scale | used for |
|---|---|---|
| 15 | WHO 2021, 24-hour | the "clean" line everywhere; the floor of `inside_worse_ventilate` |
| 35.5 | US EPA / WHO interim target 1 | `indoor_pm25_high`, `outside_worse_keep_shut`, the "moderate" ceiling |
| 55.5 | US EPA Unhealthy | `outdoor_pm25_high` |

Spikes: 2.5× the day's mean, above 12 indoors or 15 outdoors, which says "something changed" before anything
is unhealthy. Thresholds for Kuta Selatan are not thresholds for Barcelona; a pack's README says which place it
was written for.

## Adding a source

An adapter is one function returning `(sensors, readings)`. Test it against a saved payload from the real
device before opening a PR, and set `local` and `indoor` to what is true: every rule and every cell depends on them. A
source that belongs to a domain goes in a pack's `adapter.py` ([Packs](packs.md)); a device driver the core
should know goes in `app/sources.py`. Either way, add its metrics' roles to a `channels.yml`, and file the
source in [`awesome-fabcity-data`](https://github.com/fabcity/awesome-fabcity-data) so the registry, and with
it the Index, knows it exists.

## Where this leads

The node now has something of its own to read. Read it next: the [dashboard](dashboard.md) draws what the
sensors say against the ring and the region, and the [report](report.md) says it in sentences every few
hours. When a reading crosses a line, [alerts](alerts.md) is where the node starts asking somebody to do
something.
