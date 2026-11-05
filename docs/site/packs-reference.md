# Packs that ship
<!-- checked: v0.91.0 -->

The twenty-five core packs in `packs/`, five data and twenty code, hold everything the node knows about a place, and no
rule in `app/` says what PM2.5 means for a household or where the nearest fab lab is. For each pack this page
says what it reads, what it says, its rules and where each threshold comes from, its settings, and what it does
not know. How a pack is built and loaded is on [Packs](packs.md). Wild packs, such as `xiaomi-air` and
`posidonia`, are listed at [fabcity/planetai-wild-packs](https://github.com/fabcity/planetai-wild-packs) and
added with `planetai packs add`.

A pack is `code` when its folder has any `.py` file, and a code pack's adapter and hooks run only with
`PACKS_ALLOW_CODE=1`; `make` also needs `MAKE_ENABLED=1` and `fire` `FIRE_ENABLED=1`. A pack that names its own
`switch:` runs on that switch alone: `bali-air-dispatch` on `BAD_ENABLED`, `home-assistant` on `HA_DISCOVERY`,
`smartcitizen`, `airgradient` and `purpleair` whenever their keys are set, and `air-quality` reads the CAMS model on
`OPENMETEO_ENABLED`, the key that ran it in the core. A pack's `routes.py` is mounted at start and answers 404 while
the pack is off.

| pack | kind | domain | rules | report | cells | scripts | settings |
|---|---|---|---|---|---|---|---|
| `air-quality` | code | air | 4 act, 2 warn; and the event engine's 3 act, 1 warn | | 3 | | `OPENMETEO_ENABLED` (declared by the core) |
| `heat` | data | heat | 2 act, 1 info; and the event engine's 3 act | | 1 | | |
| `bali-air-dispatch` | code | air | none | | | | `BAD_ENABLED`, `BAD_RADIUS_KM`, `BAD_MIN_SEPARATION_M`, `BAD_EXCLUDE`, `BAD_INCLUDE_INDOOR` |
| `home-assistant` | code | none | none | | | | `HA_DISCOVERY` (declared by the core) |
| `smartcitizen` | code | air | none | | | | `SC_USER`, `SC_DEVICES`, `SC_EXCLUDE` (declared by the core) |
| `airgradient` | code | air | none | | | | `AIRGRADIENT_HOSTS`, `SENSOR_INDOOR` (declared by the core) |
| `purpleair` | code | air | none | | | | `PURPLEAIR_HOSTS`, `SENSOR_INDOOR` (declared by the core) |
| `nearby` | code | air | 1 act, 1 info | `alone` | | `stations` `status` `verify` `backfill` | `BAD_BACKFILL_DAYS`; the ring's are `bali-air-dispatch`'s |
| `season` | code | air | 1 info | `record` | | `window` | |
| `insight` | data | cross-domain | 2 info | `digest` | | | |
| `cold-start` | data | cross-domain | 3 info | | | | |
| `forecast` | code | weather | none | `ahead` | | `fetch` `status` `verify` `windfield` | `FORECAST_*` |
| `coast` | code | coast | 2 info | | 1 | | `COAST_MAX_KM` |
| `surface-heat` | code | heat | none | `ground` | | | `SURFACE_HEAT_*` |
| `earth` | code | land | none | | 1 | `fetch` `change` `frames` `status` `verify` `similar` | `EARTH_*` |
| `terrain` | code | water | none | | | `coverage` `fetch` `verify` | `TERRAIN_*` |
| `earth-engine` | code | land | none | | 1 | `timelapse` `verify` `basemap` | `EE_*`, `GROUND_SAT_WIDE_KM` |
| `place` | code | place | 1 info | | 1 | `refresh` `gaps` `verify` `basemap` | `PLACE_*`, `GROUND_*` |
| `make` | code | make | none | the nearest-lab line | | | `MAKE_*` |
| `fire` | code | air | 1 act, 1 warn, 1 info | | | | `FIRE_*`, `FIRMS_MAP_KEY` |
| `open-data-health` | data | governance | 1 warn | | 2 | | `CKAN_PORTALS` (core adapter) |
| `thingdata` | code | repair | 1 warn | | 2 | | `THINGDATA_*` |
| `things` | code | things | none | | | | none (the Telegram bot's token, the core's) |
| `eyes` | code | species | none | | | | `CAPTURES_DIR`, `EYES_MODEL`, `SPECIES_MATCH` (declared by the core) |
| `example-cooking-hours` | data | (none) | 1 info | | | | |

That is 33 rules with a message (26, and the 7 only the event engine reads), 5 report contributors and 12
cells. Every message is in `en`, `id` and `es`; the node picks `message[ALERT_LOCALE]` and falls back to `en`.
Cooldowns below are in minutes, per `(rule, sensor_id)`. A report contributor (`contributes: report`) has no
message and is never sent: its row goes into the report bundle under the rule's id.

## air-quality

PM2.5 rules built around the decision a household faces, whether the room is better or worse than the street
and whether the windows should be open or shut, and three Index cells. It was written at Kuta Selatan, Bali,
against a Smart Citizen kit and the public stations from Bali Air Dispatch.

| | |
|---|---|
| Kind | code |
| Domain | `air` |
| Requires node | `>=0.83.0` |
| Metrics | `pm25`, `pm10`, `pm1`, `humidity`; from CAMS `pm25_model`, `pm10_model`, `dust`, `aod`, `co`, `no2`, `o3`, `uv_index` |
| Scales | community, city |
| Needs | a low-cost PM sensor at the address, and for the comparison rules at least one outdoor reference (below) |
| Scripts | none |
| Settings | `OPENMETEO_ENABLED` runs its adapter, the CAMS model at the node's point each poll; the SQL reads `planetai.lat` and `planetai.lon` and whatever sources the node polls |

### Rules

Thresholds are US EPA and WHO 2021 (`thresholds:` in `pack.yaml`): 35.5 µg/m³ is unhealthy for sensitive
groups, 55.5 µg/m³ unhealthy, and 15 µg/m³ the WHO 24-hour guideline. The comparison rules take the ambient
reference in a fixed order: the node's own outdoor sensors first, then the three nearest public outdoor
sensors (`NOT local`, `kind='sensor'`, silent under 120 minutes), then the CAMS model (`observations` where
`sensor_id='cams-point'` and `metric='pm25_model'`).

| rule | level | cooldown | fires when |
|---|---|---|---|
| `indoor_pm25_high` | act | 120 | a local indoor sensor's 15-minute PM2.5 mean is over 35.5 |
| `outside_worse_keep_shut` | act | 180 | the best ambient reference is over 35.5 and more than 1.5 times the indoor 1-hour mean |
| `inside_worse_ventilate` | act | 180 | the indoor 1-hour mean is over 15 and more than 1.5 times the best ambient reference |
| `outdoor_pm25_high` | act | 180 | a local outdoor sensor's 1-hour mean is over 55.5 |
| `indoor_spike` | warn | 90 | an indoor 15-minute mean is at least 12 and at least 2.5 times the greater of its 24-hour mean and 2 |
| `outdoor_spike` | warn | 90 | an outdoor sensor (local, or within about 0.03° of the node) silent under 60 minutes has a 15-minute mean of at least 15 and at least 2.5 times the greater of its 24-hour mean and 2 |

`indoor_pm25_high` and `outdoor_pm25_high` declare `watch:` on `pm25` at their own line, so `GET /effect` can
say how long after an act the hourly mean came back under it. The other four have no single line to watch.

Four more rules carry a `kind:` and only the event engine reads them ([Alerts](alerts.md#the-event-engine)):
skipped under `ALERT_ENGINE=rules`, and under `shadow` and `events` folded into one `air` event, each returning
`value`, `line`, `over` and `where` (`inside` or `outside`). Cooldown 60 each. The numbers are starting values
from a replay of node #1's first month.

| rule | kind | level | `over` when |
|---|---|---|---|
| `air_spike` | spike | warn | a local sensor's latest 15-minute mean is at least 12 above the mean of the preceding hour and at least 10 above this room's 90th percentile for the local hour (a rise of 7 keeps an open event open) |
| `air_unusual` | unusual | act | every 15-minute mean of the last hour is at least 15 above this room's usual 90th percentile for the hour (an hourly mean 10 above keeps an open event open) |
| `air_sustained` | sustained | act | the 15-minute means over the last hour are all at least 35 µg/m³ (a mean of 30 keeps it open) |
| `air_extreme` | danger | act | the latest 15-minute mean is at least 125.5 µg/m³ (115 keeps it open) |

### Cells

| cell | unit | state | min_buckets | what the SQL counts |
|---|---|---|---|---|
| `Environmental\|Community` | µg/m³ PM2.5 (24h mean, sensors in this node's custody) | live | 12 | mean of `readings_1h.mean` over 24 hours for sensors where `sensors.custody` |
| `Environmental\|Community` | % of days over the WHO 24h PM2.5 guideline (30d, local outdoor) | partial | 20 | of the days with at least 12 hourly buckets from custody outdoor sensors, the share whose day mean is over 15 |
| `Environmental\|City` | µg/m³ PM2.5 (24h mean, public reference stations) | partial | | 24-hour mean over sensors that are `NOT local AND NOT indoor AND kind='sensor'` |

The core demotes the first cell to `partial` until it has 12 hourly buckets and enough in-custody sensors. The
third is never `live`, because those stations are not the node's measurement.

### What it does not know

The thresholds and the wording are Bali's. For another place, copy the folder, change both, publish it as
`planetai-pack-air-<yourplace>` and list it at
[fabcity/planetai-wild-packs](https://github.com/fabcity/planetai-wild-packs).

## heat

Turns the temperature and humidity the node already stores into three sentences about heat and one Index cell.
Apparent temperature is Steadman's no-wind form as published by the Australian Bureau of Meteorology,
`AT = T + 0.33·e − 4.0`, with `e` the vapour pressure in hPa. It was written for a humid tropical house in Kuta
Selatan, 8°S at sea level, where it is about 26 to 31 °C and 50 to 75% RH all year, and every threshold is that
place's.

| | |
|---|---|
| Kind | data |
| Domain | `heat` |
| Requires node | `>=0.10.0` |
| Metrics | `temp`, `humidity` |
| Scales | community |
| Needs | a local indoor sensor reporting both `temp` and `humidity` (Smart Citizen, AirGradient and a BME680 on a Tracker all do) |
| Scripts | none |
| Settings | none |

### Rules

| rule | level | cooldown | fires when |
|---|---|---|---|
| `heat_stress_now` | act | 1440 | a local indoor sensor's 15-minute temperature and humidity give an apparent temperature of 35 °C or more |
| `heat_danger` | act | 120 | the same, at 40 °C or more |
| `night_no_relief` | info | 1440 | over the last 12 hours, in the local hours outside 07 to 21, a local indoor sensor's hourly minimum never fell to 28 °C, with at least 5 buckets |

40 °C is the heat-index "danger" line, and 28 °C overnight is the WHO ceiling for restorative sleep. 35 °C is
the pack's own, measured at node #1: the usual "extreme caution" line of 32 °C is the year-round baseline in
Kuta Selatan and fired twenty times in two days, while 35 °C is the hot room's 90th percentile. The cooldown
keeps it to once a room a day. Both act rules declare `watch:` on `apparent` at their own line.

Three more rules carry a `kind:` and fold into one `heat` event, as in `air-quality`. They read `recent_15m`'s
`apparent` and `usual_by_hour` for indoor sensors only, and leave out a sensor whose `temp` channel is not
declared ambient, such as a Meshtastic radio's own box. Cooldown 60 each.

| rule | kind | level | `over` when |
|---|---|---|---|
| `heat_unusual` | unusual | act | every 15-minute mean apparent temperature of the last hour is at least 2 °C above this room's usual 90th percentile for the hour (an hourly mean 1 °C above keeps an open event open) |
| `heat_sustained` | sustained | act | the room has been at 35 °C or more for at least 3 hours, and for more than its usual number of such hours (a latest mean of 34 keeps an open event open) |
| `heat_extreme` | danger | act | the latest 15-minute mean is at least 40 °C (39 keeps it open) |

### Cells

| cell | unit | state | min_buckets | what the SQL counts |
|---|---|---|---|---|
| `Social\|Community` | hours in 30d with indoor apparent temperature ≥ 32 °C | live | 12 | custody indoor hourly buckets with AT at or above 32, divided by the number of distinct sensors |

The cell keeps 32 °C where the rule moved to 35: 32 is right for counting exposure, which is what a cell does,
and wrong for interrupting a household, which is what a rule does.

### What it does not know

Every rule and the cell read local indoor sensors only, because the no-wind Steadman form is the indoor form;
a node whose only local sensors are outdoors gets no heat alerts. The pack knows nothing of radiant heat or
airflow, and its calibration rests on five dry-season days at one house, with a highest AT of 36.5 °C. To move
the line, change the `>= 35` in `heat_stress_now` to near the 90th percentile of your hottest indoor sensor.

## bali-air-dispatch

Reads the island's public air stations around the node from Bali Air Dispatch, one key-free archive of eight
networks (Nafas, IQAir, PurpleAir, AQICN, OpenAQ, AirGradient, Smart Citizen, Airly). It stores them as other
people's stations (`local=false`, at any distance), so the node can tell the lane from the island. It says
nothing itself: `nearby` and `season` read what it stores. Bali only.

| | |
|---|---|
| Kind | code, run by its own switch (`switch: BAD_ENABLED`) |
| Domain | `air` |
| Requires node | `>=0.82.3` |
| Metrics | `pm25`, `pm25_raw`, `pm10`, `pm1`, `temp`, `humidity`, `aqi` |
| Scales | community |
| Sources | `environmental/community/bali-air-dispatch` |
| Needs | network to `baliairdispatch.com`; `NODE_LAT` and `NODE_LON` |
| Rules and cells | none: peers never drive an alert (`thresholds:` in `pack.yaml` says so) |
| Attribution | Bali Air Dispatch, baliairdispatch.com, and the network named in each row's `source` |

The sensor ids are `bad-<station>` and the source is `baliairdispatch`. Its channels are in its own
`channels.yml`. It declares `stations:` in `pack.yaml` (`source`, `prefix`, `radius`, `box`, `url`,
`attribution`), which is how the "Air stations nearby" source, `GET /nearby` and the ring on the map find it
without naming it. A node inside the `box`, south Bali to north Bali, with the pack off is told to turn it on;
a node anywhere else is told nothing. On `planetai update`, a node that lists its packs in `PACKS_ENABLED` and
has `BAD_ENABLED=1` gets `bali-air-dispatch` added to the list.

### Settings

| setting | default | meaning |
|---|---|---|
| `BAD_ENABLED` | `0`; the bali preset `1` | the pack's switch. It runs the adapter without `PACKS_ALLOW_CODE` |
| `BAD_RADIUS_KM` | `15`; the bali preset `8` | ring radius in km. 15 is the tightest that leaves `nearby` its two-station floor at node #1 with room to spare |
| `BAD_MIN_SEPARATION_M` | `150` | a station closer to the node than this is excluded as the node's own kit |
| `BAD_EXCLUDE` | empty | station ids excluded by hand |
| `BAD_INCLUDE_INDOOR` | `0` | `1` keeps stations the archive marks `suspected_indoor` |

It also reads `SC_USER`, `SC_DEVICES`, `SC_EXCLUDE` and `AIRGRADIENT_HOSTS`, to know which devices this node
already polls.

### What it does not know

It keeps the node's own kit out of the ring by four tests: identity (a device this node polls, at any
distance), proximity (within `BAD_MIN_SEPARATION_M`), by hand (`BAD_EXCLUDE`), and one device on two networks
(an AirGradient unit mirrored by OpenAQ, collapsed on the same name within the separation radius). It cannot
know about a kit of yours it does not poll and that sits further away than the separation radius. One
function, `verdicts()`, decides, and `nearby`'s scripts and `GET /nearby?audit=1` call the same one.

## smartcitizen

Reads this node's own Smart Citizen kits from api.smartcitizen.me: the ones listed by id (`SC_DEVICES`), and the
ones in the household's account (`SC_USER`) that published in the last three days, less `SC_EXCLUDE`. Every one is
the house's own, so every one is stored `local`, indoor or outdoor from the kit's own `exposure`. And the kits and
DIY nodes that publish straight to this node's broker (`device/sck/#`, set up with `planetai broker`), stored as
`sck-<hash>` with source `smartcitizen-direct`, and passed on to smartcitizen.me for the tokens in `SC_FORWARD`.

| | |
|---|---|
| Kind | code, on whenever a kit is configured or a broker is set (`switch: [SC_USER, SC_DEVICES, MQTT_HOST]`) |
| Domain | `air` |
| Requires node | `>=0.83.0` |
| Sources | `environmental/community/smart-citizen` |
| Needs | network to `api.smartcitizen.me`, and to `mqtt.smartcitizen.me:8883` for the tokens in `SC_FORWARD` |
| Rules and cells | none: `air-quality` and `heat` decide what the readings mean |

The sensor ids are `sc-<kit>` and the source is `smartcitizen`, as they were in the core until 22 October 2026, and
the direct path keeps its `sck-` ids and its `direct` key in `/health`, so a node's history carries on. Its three
settings stay under Set up → Sources, where a household sets up its kits, and `SC_FORWARD` under Sharing, because it
changes what leaves the house. Which kits in an account are the node's own stays in the core
(`sources.smartcitizen_account`), because `bali-air-dispatch` and `nearby` ask it too. The direct path is `hooks.py`:
the node subscribes to its `MQTT_TOPICS` and hands it every message on them. On `planetai update`, a node that lists
its packs in `PACKS_ENABLED` and has `SC_USER`, `SC_DEVICES` or `MQTT_HOST` set gets `smartcitizen` added to the
list, so it keeps reading its kits.

## airgradient

Reads this node's own AirGradient ONE and Open Air monitors on the household's WiFi, each host in
`AIRGRADIENT_HOSTS` at `http://<host>/measures/current`, never through AirGradient's cloud. PM2.5 is the EPA 2021
correction of the raw Plantower value, which is kept beside it as `pm25_raw`. CO2, temperature, humidity, PM1, PM10
and the TVOC and NOx indexes are stored as the monitor gives them.

| | |
|---|---|
| Kind | code, on whenever a host is listed (`switch: [AIRGRADIENT_HOSTS]`) |
| Domain | `air` |
| Requires node | `>=0.83.0` |
| Sources | `environmental/community/airgradient` |
| Needs | the monitors' own addresses on this node's network |
| Rules and cells | none: `air-quality` and `heat` decide what the readings mean |

The sensor ids are `ag-<serial>` and the source is `airgradient`. The monitors take the node's own coordinates, and
`SENSOR_INDOOR=1` marks them as indoors. This was a core adapter until v0.16 dropped it from the poll by accident,
while the setting and the installer's `--airgradient` stayed; it reads again as a pack from 22 October 2026. On
`planetai update`, a node that lists its packs in `PACKS_ENABLED` and has `AIRGRADIENT_HOSTS` set gets
`airgradient` added to the list.

## purpleair

Reads this node's own PurpleAir sensors on the household's WiFi, each host in `PURPLEAIR_HOSTS` at
`http://<ip>/json?live=true`; use the IP, the `.local` name is unreliable. PM2.5 is the EPA 2021 correction of the
mean of the two laser channels, with the raw mean kept as `pm25_raw`, and a gap between the channels larger than
5 µg/m³ and 70% of the reading is stored as `channel_disagreement`, because one laser is failing. Temperature is
converted from °F, not corrected, and pressure from hPa to kPa.

| | |
|---|---|
| Kind | code, on whenever a host is listed (`switch: [PURPLEAIR_HOSTS]`) |
| Domain | `air` |
| Requires node | `>=0.83.0` |
| Needs | the sensors' own addresses on this node's network |
| Rules and cells | none: `air-quality` and `heat` decide what the readings mean |

The sensor ids are `pa-<sensor id>` and the source is `purpleair`. A sensor that reports its own coordinates keeps
them; otherwise it takes the node's. Like `airgradient`, it was a core adapter that v0.16 dropped from the poll, and
it reads again as a pack from 22 October 2026, added to a listed `PACKS_ENABLED` on update.

## home-assistant

Publishes this house's own sensors to Home Assistant as entities, one device per physical sensor, and the node's latest
alert as a text sensor, over MQTT discovery, retained. The node publishes and Home Assistant automates; it never
addresses a device. Setting it up is on [Channels](channels.md#home-assistant).

| | |
|---|---|
| Kind | code, run by its own switch (`switch: HA_DISCOVERY`); `hooks.py`, no `adapter.py` |
| Domain | none: it carries what the node stores and sends |
| Requires node | `>=0.83.0` |
| Needs | the MQTT broker (`MQTT_HOST`), which `planetai homeassistant` sets up |
| Rules and cells | none |

It hears the node through two hooks: `on_readings` after every batch the node stores, and `on_alert` with every alert
it records. `HA_DISCOVERY` is still declared by the core, so Set up keeps marking it as a setting that changes what
leaves the machine; a pack cannot declare that of a key yet. It was core code until 22 October 2026. On
`planetai update`, a node that lists its packs in `PACKS_ENABLED` and has `HA_DISCOVERY=1` gets `home-assistant`
added to the list, so it keeps publishing.

## nearby

This pack reads the ring, other people's air sensors around the node as `bali-air-dispatch` stores them. One kit cannot tell a
fire in the lane from a haze over the whole island, and the ring can. It says when the bad air is only here,
when it is everywhere, and in the report when there is no ring worth the name.

| | |
|---|---|
| Kind | code: its rules are data, and it ships scripts |
| Domain | `air` |
| Requires node | `>=0.40.0` |
| Metrics | `pm25`, `pm25_raw`, `pm10`, `pm1`, `temp`, `humidity` |
| Scales | community |
| Sources | `environmental/community/bali-air-dispatch` |
| Needs | the `bali-air-dispatch` pack on; at least two public outdoor stations within `BAD_RADIUS_KM`; for `only_here`, a local outdoor sensor |
| Cells | none: `live` means measured here, and `air-quality` already has `Environmental\|City` as `partial` over these same stations |
| Attribution | Bali Air Dispatch, baliairdispatch.com, and the network named in each row's `source` |

The ring is every sensor with `sensors.source='baliairdispatch'` that is not local, is outdoor and has
reported in the last 120 minutes.

### Rules

| rule | level | cooldown | fires when |
|---|---|---|---|
| `only_here` | act | 2880 | the ring has at least 2 stations and a local outdoor sensor's 1-hour mean is at least 10 over the ring's 75th percentile and more than 1.6 times the ring's median |
| `everywhere` | info | 2880 | the ring has at least 2 stations and its median is over 35.5 |
| `alone` | (report) | | the ring has fewer than 2 stations or the nearest is more than 10 km away; puts `stations` and `nearest_km` in the report |

`only_here` asks the node to clear the top of the ring by 10 µg/m³. Node #1's neighbours in clean air sit 4
to 15 km apart and differ by about 9 µg/m³, so a rule that waited for the ring to agree with itself would never
fire; this way a wide ring asks for a bigger excursion and a tight one fires sooner. 35.5 is the EPA line `air-quality` uses.

### Scripts

- `planetai run nearby stations`: every station in the archive, its distance, and `included` or `excluded: <reason>`, from the same function the adapter uses.
- `planetai run nearby status`: the ring now, who is reporting, how far, how long ago.
- `planetai run nearby verify`: every exclusion fires, nothing external is stored as `local`, the ring recomputes. Exit 1 on failure.
- `planetai run nearby backfill [days]`: each station's hourly PM2.5 history. Asked for, never scheduled.

### Settings

The pack declares no `env:` of its own. The ring's settings are `bali-air-dispatch`'s (`BAD_*`, above), and its
scripts read them too. One more is read by `backfill`:

| setting | default | meaning |
|---|---|---|
| `BAD_BACKFILL_DAYS` | `0` | history to pull on `backfill` when no number is given |

### What it does not know

The pack has no adapter and no `channels.yml`: the fetch and the channels are `bali-air-dispatch`'s, and a
second fetch would put every station in the node twice. Outside Bali the same three rules would need an OpenAQ
v3 backend behind the same shape, and there is none yet.

## season

`nearby` asks where the bad air is right now, across space; `season` asks across time whether this week is
worse than the weeks before it. It is two SQL rules and a script, with no fetch of its own, reading the ring
`bali-air-dispatch` stores. Written for Bali, from the archive's daily record since January
2025.

| | |
|---|---|
| Kind | code: its rules are data, and it ships a script |
| Domain | `air` |
| Requires node | `>=0.40.0` |
| Metrics | `pm25` |
| Scales | community |
| Sources | `environmental/community/bali-air-dispatch` |
| Needs | the `bali-air-dispatch` pack on and 68 days of the ring in this node's own database. `planetai run nearby backfill 90` fetches that depth once |
| Cells | none, for the same reason as `nearby` |
| Settings | none of its own; the `BAD_*` settings shape the ring |
| Attribution | Bali Air Dispatch, baliairdispatch.com, and the network named in each row's `source` |

The comparison is paired: each ring station's last 7 days against its own preceding 60, and the median of
those differences. A station counts only if it holds at least 4 days in the week and 20 in the baseline. The
archive grew from 2 stations with usable daily rows to 79 over its record, so an unpaired comparison would
measure which networks joined and not what the air did.

### Rules

| rule | level | cooldown | fires when |
|---|---|---|---|
| `turning` | info | 4320 | at least 3 stations pair, the median paired step is 8 µg/m³ or more, and the median of the week is 20 µg/m³ or more |
| `record` | (report) | | at least one station pairs: `stations`, `week`, `usual`, `step` and `baseline_days`, whether or not the line was crossed |

+8 µg/m³ is the top of an ordinary week in the record: the paired step's 90th percentile was +8.2 across Bali.
The week must also reach 20 µg/m³, because a step from 6 to 14 changes nobody's afternoon, and three paired
stations is the floor for saying anything.

### Scripts

- `planetai run season window`: every paired station, its week, its baseline and the step. The summary line runs the pack's own `record` rule, so the audit cannot drift from the report.

### What it does not know

It is not a climatology. The same weeks last year held two stations, so a year-over-year comparison does not
exist yet, and the message says "its own last two months", never "normal for this time of year". A node that
has held the ring for under four weeks pairs nothing, and `record` returns no row.

## insight

Three rules that turn the node's own history into sentences: a digest for the report, how well the node's
sources agree, and the shape of the week. It is all SQL, since Postgres has `corr()` built in, and nothing
leaves the machine.

| | |
|---|---|
| Kind | data |
| Domain | `cross-domain` |
| Requires node | `>=0.9.0` |
| Scales | community |
| Needs | nothing beyond what the node holds; `rhythm` needs a local outdoor `noise` sensor |
| Scripts | none |
| Cells | none: how the node's sources agree is not a fact about the place |
| Settings | none; to change the cadence, copy the folder and change `cooldown_minutes` |

### Rules

| rule | level | cooldown | fires when |
|---|---|---|---|
| `digest` | (report) | | inside (`n_in`), outside (own outdoor sensors, else the 3 nearest public), modelled (CAMS), `day_mean`, `day_peak` and `trend` (rising, falling or steady: the last 3 hours against the prior 3, ±3). A row only when inside is not NULL |
| `agreement` | info | 1440 | 7 days of hourly indoor, outdoor and model give at least 48 indoor and 48 outdoor hours; reports `r_in_out`, `r_out_model`, `r_in_model`, `shield`, `model_bias`, `filtered_pct` |
| `rhythm` | info | 1440 | the week's worst and best outdoor hours (local time), and the loudest hour from a local outdoor `noise` sensor, in `quiet_hr` |

### What it does not know

A node with no local outdoor noise sensor gets no `rhythm` alert, because the SQL joins a `loud` CTE built from
those readings. The rule names no cause for the bad hours, because the one kit with a noise sensor showed the
loud hours were the clean ones. The README's pooled correlations (r = 0.55 indoor to outdoor) are kept for the
record; measured pairwise, one indoor kit against one outdoor kit 1.3 km apart gives r = 0.20, and the pairwise
figure is the one to use.

## cold-start

Makes a node useful on day one with no hardware: a modelled air line, today against 40 years of climatology,
and once a sensor arrives, how far it sits from the model. The README calls it a scaffold, to delete when your
own sensors carry the story.

| | |
|---|---|
| Kind | data |
| Domain | `cross-domain` |
| Requires node | `>=0.3.0` |
| Scales | community, planet |
| Sources | `environmental/planet/open-meteo`, `environmental/planet/nasa-power` |
| Needs | the `BOOTSTRAP` step on first start (92 days of CAMS hourly history while `air-quality` is on, NASA POWER monthly normals), the core's `open-meteo` adapter and the CAMS model the `air-quality` pack reads. All free, key-free, global |
| Scripts | none |
| Settings | none |
| Cells | none: nothing here measures your place |

The rules read `observations`, the view where models and portals land.

### Rules

| rule | level | cooldown | fires when |
|---|---|---|---|
| `modelled_air_today` | info | 10080 (`long_cooldown_ok`) | a `cams-point` / `pm25_model` observation exists. The daily reports carry the model reading, so this is weekly |
| `hotter_than_normal` | info | 4320 | `om-point` / `temp_model` differs from `power-point` / `temp_norm` for this month by more than 3 °C |
| `sensor_vs_model` | info | 10080 | the 24-hour mean of local outdoor PM2.5 differs from CAMS by more than 15 µg/m³ |

### What it does not know

The README reads a big gap in `sensor_vs_model` as the local signal a global model cannot see, and not as a
sensor fault. Seeing that signal is the reason to run a node at all.

## forecast

Official and model weather for this point over the next 72 hours, as context for reading the node's own air.
It fetches and does not predict, and it never sends an alert. BMKG, Indonesia's meteorological agency, is the source
that is on by default; Open-Meteo works anywhere and is off until the operator turns it on. Now draws it under
[Next days](next-days.md).

| | |
|---|---|
| Kind | code |
| Domain | `weather` |
| Requires node | `>=0.40.0` |
| Metrics | `fc_temp`, `fc_humidity`, `fc_wind_speed`, `fc_wind_direction`, `fc_cloud`, `fc_rain`, `fc_wind_gusts`, `fc_rain_prob`, `fc_shortwave`, `fc_et0`, `fc_soil_moisture`, `fc_pm25`, `fc_uv`, `fc_wave_m`, `fc_swell_m`, `fc_swell_s`, `fc_swell_dir`, `fc_lead_hours`, `fc_temp_gap`, `fc_wind_speed_gap` |
| Scales | community |
| Needs | `PACKS_ALLOW_CODE=1`; network to `api.bmkg.go.id`, `api.open-meteo.com`, `air-quality-api.open-meteo.com` and `marine-api.open-meteo.com`; correct node coordinates; for BMKG, a village code |
| Cells | none: a forecast is not measured here |
| Attribution | BMKG must be named inside the application and is, on the card and in the export; Open-Meteo is CC BY 4.0, free tier non-commercial |

### Rules

| rule | level | cooldown | fires when |
|---|---|---|---|
| `ahead` | (report) | | the next 24 hours from `readings` of `kind='model'` with `source IN ('forecast-bmkg','forecast-om')`: `wind_kmh`, `wind_from_deg`, `rain_mm`, `rain_from`, `lead_hours` |

No rule here may grow a level or a message, and a test holds it to that. A forecast is wrong often, and wrong
about tomorrow; there is nothing a household does at 9 pm because of rain predicted for tomorrow that it would
not do by looking out of the window.

### Scripts

- `planetai run forecast verify`: the `adm4` code resolves to somewhere near the node (province, regency, district, village and distance printed; past 10 km the card says so), units are as documented, BMKG's `analysis_date` is under 18 hours old. Exit 1 on failure.
- `planetai run forecast fetch`: fetch now instead of waiting for the poll; writes to `sensors` and `readings`.
- `planetai run forecast status`: the next day's wind, rain and temperature, and when it was issued.
- `planetai run forecast windfield`: refresh the wind field now. Refuses unless `FORECAST_OPENMETEO=1`.

`planetai run forecast days` and `planetai run forecast territory` also show in the script list, because `days.py`
and `territory.py` are non-adapter `.py` files in the folder. They are modules `routes.py` and the adapter import, not
commands.

### Settings

| setting | default | meaning |
|---|---|---|
| `FORECAST_BMKG` | `1` | poll BMKG: 3-hourly, three days, no key. `ws` is km/h, `wd_deg` is where the wind comes from, `tp` is rain in mm for the step |
| `FORECAST_BMKG_ADM4` | empty | the Permendagri village code for this point, such as `51.03.05.2002` for Ungasan, Kuta Selatan. Without a code the pack logs one line and idles |
| `FORECAST_OPENMETEO` | `0` | poll Open-Meteo, hourly, anywhere: its weather, the CAMS air and, while `coast` is on, the sea. Off because its free tier is non-commercial only, which is the operator's decision |
| `FORECAST_POLL_HOURS` | `6` | how often the pack asks, whatever `POLL_SECONDS` is; each source keeps its own stamp in `out/forecast.<source>.last` across restarts, and one that fails is asked again after 30 minutes, and the wind field keeps a stamp of its own. Both publishers update a few times a day, and Open-Meteo's free tier is 10,000 calls a day per IP with each wind-field point counting as one |
| `FORECAST_WIND_N` | `8` | points a side of the wind field: 8 × 8 |
| `FORECAST_WIND_KM` | `30` | half-width of the wind field's square, in km |

It also reads `NODE_LAT`, `NODE_LON` and `NODE_SCALE`, which decides how many points Open-Meteo and CAMS are asked for: 7 at `community`, 19 at `city` and `region`.

### What it does not know

A forecast is often wrong, and the pack keeps it apart from what the node measures. Every channel in
`channels.yml` is `role: derived`, `comparable: false` (sources `forecast-bmkg`, `forecast-om`, `forecast-cams`,
`forecast-marine` and `forecast-gap`), and the `fc_` prefix is a second guard. Each value is stored at its valid time with
`fc_lead_hours` beside it. Open-Meteo publishes no model run time, so its rows say `fetched`, not `issued`. With
both sources on, `forecast-gap` records how far apart they are on temperature and wind for the same hour.

With Open-Meteo on, each fetch also keeps the next day's hourly 10 m wind over the node's square as
`out/ground/wind.json`, served at `GET /ground/wind` for the map. It asks with `cell_selection=nearest`, because
the default moves a sea point to the nearest land cell, up to 12 km off. The field reaches no cell, alert or
report.

## coast

Waves, swell and sea-surface temperature at the nearest ocean grid cell, every poll, from Open-Meteo's Marine
API, which needs no key and works anywhere. It was written at Kuta Selatan, where the nearest cell is 5 km off the Bukit; a
calmer sea such as Barcelona's would set the thresholds lower.

| | |
|---|---|
| Kind | code |
| Domain | `coast` |
| Requires node | `>=0.10.0` |
| Metrics | `wave_height_m`, `wave_direction`, `wave_period_s`, `swell_height_m`, `swell_period_s`, `sea_surface_temp` |
| Scales | bioregion |
| Sources | `environmental/bioregion/open-meteo-marine` |
| Needs | `PACKS_ALLOW_CODE=1`; network to Open-Meteo Marine; an ocean cell within `COAST_MAX_KM` |
| Scripts | none |
| Attribution | Open-Meteo Marine API (CC BY 4.0), model data from Copernicus Marine / MeteoFrance MFWAM |

The adapter writes one sensor, `marine-point`, with `source='open-meteo-marine'`, `kind='model'`,
`scale='bioregion'`, `local=False` and cadence `PT1H`. The API snaps to the nearest ocean cell however far it is,
so the adapter measures the distance and raises if it is over `COAST_MAX_KM`; a node in Ubud does not get the
weather of a sea it cannot see.

### Rules

| rule | level | cooldown | fires when |
|---|---|---|---|
| `heavy_swell` | info | 720 | `swell_height_m` is at least 2.5 and `swell_period_s` at least 12, the combination that means strong currents on exposed beaches |
| `sea_warm_anomaly` | info | 1440 | the current sea-surface temperature is at least 1.0 °C above its own mean over days 7 to 60 back |

### Cells

| cell | unit | state | min_buckets | what the SQL counts |
|---|---|---|---|---|
| `Environmental\|Bioregion` | sea surface temperature, 7d mean, °C (nearest ocean cell) | partial | | 7-day mean of `sea_surface_temp` on `marine-point`. Never `live`: it is a model |

### Settings

| setting | default | meaning |
|---|---|---|
| `COAST_MAX_KM` | `30` | refuse to report if the nearest ocean cell is further away than this, in km |

### What it does not know

The values are a wave model's at the nearest ocean grid cell, which may be kilometres off your beach, and the
thresholds are set for the Bukit's coast. The wild `posidonia` pack reads this pack's `sea_surface_temp`, and
without `coast` on it has nothing to read.

## surface-heat

How hot the ground in this node's own H3 resolution-8 cell got against the land 1 to 3 km around it, from
Landsat's surface temperature at 30 m, and how warm the ground stays at night, from MODIS at 1 km. It reads once a
day from Microsoft Planetary Computer, with no account. Nothing in it is specific to Bali.

| | |
|---|---|
| Kind | code |
| Domain | `heat` |
| Requires node | `>=0.81.0` |
| Metrics | `lst`, `lst_ring`, `lst_delta`, `lst_pctile`, `lst_night`, `lst_day` |
| Scales | city |
| Sources | none in `pack.yaml` yet; the registry entries are `environmental/city/landsat-c2-surface-temperature` and `environmental/city/modis-lst-mod11a1` |
| Needs | `PACKS_ALLOW_CODE=1`; network to planetarycomputer.microsoft.com and its blob storage, once a day: about 1.5 MB the first day, half a megabyte on a day with a new Landsat scene |
| Scripts | none |
| Cells | none: a satellite retrieval of the ground is not measured here |
| Attribution | Landsat courtesy of the U.S. Geological Survey, MODIS from NASA LP DAAC, both public domain, read through Microsoft Planetary Computer |

The adapter writes two sensors, both `kind='model'`, `scale='city'`, `local=False`: `surface-cell`
(`source='landsat-lst'`) from the newest clear Landsat 8/9 Collection 2 scene, and `surface-modis`
(`source='modis-lst'`) from MOD11A1 and MYD11A1 v061. Every reading is stamped with the satellite's pass, not
the poll. A scene counts when at least `SURFACE_HEAT_MIN_CLEAR` of the cell's land and of the ring's is clear
in `QA_PIXEL`; water is on neither side. It adds no library: it reads only the few tiles of each Cloud-Optimized
GeoTIFF around the node, with HTTP range requests, and remembers a scene in `out/surface-heat/state.json`.

Its `readouts:` add three lines to the heat issue: the cell's ground temperature, the cell minus the ring, and
the ground at night. Its `sections:` entry, `surface-heat` (stage observe, `wall: true`), shows four: those
three and the ring's own.

### Rules

| rule | level | cooldown | fires when |
|---|---|---|---|
| `ground` | (report) | | the last pass's `seen_at`, `ground_c`, `around_c`, `hotter_than_around_c`, `percentile_in_ring`, and `air_c` from the house's own outdoor sensor within half an hour of the pass, else the weather model's, with `air_from` saying which |

### Settings

| setting | default | meaning |
|---|---|---|
| `SURFACE_HEAT_RING_KM` | `3` | the outer edge of the ring, in km; it starts at 1 km |
| `SURFACE_HEAT_MIN_CLEAR` | `0.5` | the share of the cell's land, and of the ring's, that must be clear for a scene to count |

### What it does not know

A ground temperature is the skin of roofs, roads and canopy. A roof at 45 °C is not a room at 45 °C, which is
why the pack has no alert and no cell. Landsat gets one clear look every one to three weeks, at about 10:30.

## earth

The node's own copy of Google's AlphaEarth Satellite Embedding layers for its square of the planet, and the
year-over-year per-pixel change computed here from them: cosine distance at 10 m. The node downloads them once,
on command, keeps them as files and compares them with arithmetic. It says something changed, never what.

| | |
|---|---|
| Kind | code |
| Domain | `land` |
| Requires node | `>=0.33.0` |
| Metrics | `land_change_yoy`, `land_change_since_2017`, `years_cached` |
| Scales | city |
| Sources | `environmental/city/alphaearth-satellite-embedding` |
| Needs | `PACKS_ALLOW_CODE=1`; `planetai packs install` for `rasterio` and `numpy` (`pip:`); network to `storage.googleapis.com` on the first fetch only. No key, no account, no cloud project. Disk: 64 MB per year cached, 576 MB for all nine |
| Attribution | "The AlphaEarth Foundations Satellite Embedding dataset is produced by Google and Google DeepMind. CC BY 4.0.", carried with every derivative |

The adapter writes `earth-point` (`kind='model'`, `scale='city'`) and reads only what is already cached under
`out/earth/<node>/`: `<year>.npy`, `meta.json`, `change_<A>_<B>.png` and `.json`, `year_<YYYY>.png`. Nothing is
downloaded on a poll. The directory is matched on the point and radius in its `meta.json`, so one written under
an earlier `NODE_NAME` is adopted as it stands; `planetai run earth status` names any that no longer match and
deletes nothing.

### Rules

None. A threshold that fires in Kuta Selatan, where the land is being built on, also fires in Boston every
year for reasons nobody there can act on: snow and leaf-off between two annual composites. A season cannot yet
be told from a bulldozer, and the node does not send messages a household would ignore.

### Cells

| cell | unit | state | min_buckets | what the SQL counts |
|---|---|---|---|---|
| `Environmental\|City` | land change: mean per-pixel cosine distance between consecutive annual AlphaEarth embeddings (0 = unchanged) | partial | 1 | the latest `land_change_yoy` observation on `earth-point` |

It stays `partial`: the node did the arithmetic, but the input is a model's description of a place, which
nobody here could repeat as a measurement. `air-quality` also has an `Environmental|City` cell, and `/cells` lists
both.

### Scripts

- `planetai run earth fetch [year ...] [--force]`: every year the dataset has (or `EARTH_YEARS`); `--force` re-reads a cached one. About 103 MB and 150 seconds per year, roughly 22 minutes for all nine, so run it from a shell and not over MCP.
- `planetai run earth change [A B | --all] [--force]`: the two latest consecutive cached years, any two, or every consecutive pair plus the oldest-to-newest span. Read the span first, then the years.
- `planetai run earth frames [--refit]`: one grey picture of the place per cached year for the card to animate, the first principal component of the embedding (not photographs). `--refit` redoes the projection, which a moved square needs and a new year does not.
- `planetai run earth status`: years, bytes, comparisons, what the cell reports.
- `planetai run earth verify`: seven checks, the dataset's claims against the files (unit-length vectors after de-quantising) and whether the reading landed.
- `planetai run earth similar [year] [--out FILE]`: every pilot in `presets/` compared with the others and with its own tile. A regional search (one UTM tile, about 82 km a side).

### Settings

| setting | default | meaning |
|---|---|---|
| `EARTH_RADIUS_M` | `5000` | half-width of the square around the node, in metres. 5000 is a 10 km square: 64 MB on disk and about 103 MB pulled, per year |
| `EARTH_YEARS` | empty | which years to fetch, comma separated. Blank means every year the dataset has (2017 to 2025) |

It also reads `NODE_LAT`, `NODE_LON`, `NODE_NAME`, `PACK_OUT` and `DATABASE_URL`. Write `VAR=value` in `.env`
with no space after `=`: `VAR= value` is read by the shell as a command.

### What it does not know

`CHANGED = 0.15`, at the top of `packs/earth/change.py`, is the one number in the pack that was chosen; at node
#1 it sits at about the 99th percentile of a consecutive-year comparison. The number does not compare between
places: for 2024 to 2025 the mean is 0.0414 in Kuta Selatan, 0.0404 in Boston, 0.0164 in Barcelona and 0.0151
in Santiago. Change the coordinates or the radius and `fetch` re-reads every cached year; a correction under 1%
of the radius (never less than 25 m) is recorded as `point_drift_m` and leaves the cache alone.

## terrain

Where the next day's rain goes around the node. It reads its own square of Copernicus DEM GLO-30 once, on
command, fills the hollows (priority-flood) and routes water downhill (D8), with numpy and a heap and no hydrology
library. Each poll multiplies the ground that drains through the node's point by the next 24 hours of forecast
rain. Nothing in it is specific to Bali, and it has no threshold to tune.

| | |
|---|---|
| Kind | code |
| Domain | `water` |
| Requires node | `>=0.76` |
| Metrics | `terrain_upslope_ha`, `terrain_upslope_near_ha`, `terrain_hollow_m`, `rain_24h_mm`, `water_24h_m3` |
| Scales | city |
| Sources | `environmental/planet/copernicus-dem-glo30` |
| Needs | `PACKS_ALLOW_CODE=1`; `rasterio` and `numpy` (`pip:`, the same as `earth`); network to `copernicus-dem-30m.s3.amazonaws.com` (or `-90m`) on the fetch only, about half a megabyte for 10 km. No key. The `forecast` pack for the rain |
| Cells | none: a surface model is not measured here |
| Attribution | "produced using Copernicus WorldDEM-30 © DLR e.V. 2010-2014 and © Airbus Defence and Space GmbH 2014-2018 provided under COPERNICUS by the European Union and ESA; all rights reserved", and the licence's no-liability sentence, carried with every row |

The adapter writes `terrain-point` (`kind='model'`, `scale='city'`, `local=False`). The three terrain rows carry
the fetch's own timestamp; `rain_24h_mm` and `water_24h_m3` are stamped on the hour. The rain is `fc_rain` summed
over the rows timestamped in the next 24 hours, from one source only, BMKG if it has rows, else Open-Meteo:
adding both would double it. `water_24h_m3` is that rain on the upslope area, as if none of it soaked in. The pack
ships the `water` issue (`packs/terrain/issue.yml`): context, four readouts, no line and no hero, so it never
leads. Add `water` to `NODE_ISSUES` to draw it.

### Scripts

- `planetai run terrain coverage`: which elevation this point would use, before anything is downloaded: your own file, GLO-30, GLO-90 where the 30 m tile is not public (25 tiles in the Caucasus on AWS), or none.
- `planetai run terrain fetch`: read the square, fill, route, keep `out/terrain/<node>/terrain.json`. Run it again only when the node moves, the radius changes or the DEM changes.
- `planetai run terrain verify`: five checks, including that every land cell drains to the window's edge or the sea after the fill, and that rows from this fetch reached the database.

### Settings

| setting | default | meaning |
|---|---|---|
| `TERRAIN_RADIUS_M` | `5000` | half-width of the square, in metres. Water from further uphill than this is not counted |
| `TERRAIN_DEM_PATH` | empty | a GeoTIFF of your own (a drone survey, a national LiDAR), used instead of Copernicus |
| `TERRAIN_DEM_LICENCE` | empty | that file's licence, in words. Read on every poll: blank means the node computes from the file and sends no rows |

### What it does not know

GLO-30 is a surface model: roofs and canopy are in the heights, and a 30 m pixel is a street block, so the pack
speaks at region distance and never for the yard. It does not know the soil, the drains or the gutters. There is
no wetness index and no percentile: on a filled pixel the index is mostly its slope clip, and a percentile gives
every square a wettest tenth. At node #1 the house's own pixel drains 0.09 ha and the largest flow within 60 m
drains 0.6 ha. The AWS copy is the 2021 release; the newer Copernicus Data Space copies are licensed for
non-commercial use, and the pack does not read them.

## earth-engine

What the land within a kilometre of the node did last year, from Google Earth Engine's public catalog: tree,
built, crop and water fractions (Dynamic World), annual median NDVI (Sentinel-2, clouds masked) and the latest
night-lights radiance (VIIRS). Computed in Earth Engine and stamped mid-year, so a daily fetch inserts nothing
new after the first. It is the worked example of a code pack with a dependency and a credential.

| | |
|---|---|
| Kind | code |
| Domain | `land` |
| Requires node | `>=0.10.0` |
| Metrics | `tree_frac`, `built_frac`, `crop_frac`, `water_frac`, `ndvi_median`, `night_lights` |
| Scales | bioregion |
| Needs | `PACKS_ALLOW_CODE=1`; `planetai packs install` for `earthengine-api` (`pip:`); a Google Earth Engine project (free for research and non-commercial use) and a service-account key mounted read-only at `config/ee-key.json` |
| Rules | none; land change is the `earth` pack's |

The adapter writes `ee-point` (`source='earth-engine'`, `kind='model'`, `scale='bioregion'`), and until it is
configured the pack logs one line and idles. To set it up:

1. Register an Earth Engine project.
2. Create a service account with Earth Engine Resource Viewer and Service Usage Consumer (and Resource Writer for timelapse images).
3. Copy its JSON key to `config/ee-key.json` on the node.
4. Run `planetai packs install`, then `planetai restart`.
5. Run `planetai run earth-engine verify`; every step it names should pass.

### Cells

| cell | unit | state | min_buckets | what the SQL counts |
|---|---|---|---|---|
| `Environmental\|Bioregion` | tree-cover fraction within 1 km (Dynamic World, last complete year) | partial | | the latest `tree_frac` reading on `ee-point` |

### Scripts

- `planetai run earth-engine verify`: library, settings, key file, credentials, a real query, the datasets. Names the step that failed.
- `planetai run earth-engine timelapse [--years a,b,c | --n 4 --gap 5] [--km 2] [--px 1024] [--source landsat|sentinel] [--lat --lon] [--dry-run]`: annual-median frames of clear pixels; Landsat by default (the only archive reaching 2010 with one instrument family), Sentinel-2 from 2016 at 10 m. PNGs and a side-by-side page land in `out/`.
- `planetai run earth-engine basemap [--months 12] [--dry-run]`: the median of every clear Sentinel-2 pass over the last twelve months, built in the node's own Earth Engine project and kept as tiles at zoom 8 to 15 in `out/ground/imagery.mbtiles`, served at `GET /ground/imagery`. Earth Engine learns the two squares once, and the script says so before it runs.

### Settings

| setting | default | meaning |
|---|---|---|
| `EE_PROJECT` | empty | the project id, such as `planetai-node-472103`, and not the service account's 21-digit number; Earth Engine reports that mistake as "project not found". Blank reads it from the key file |
| `EE_SERVICE_ACCOUNT` | empty | blank is fine; the key file names it |
| `EE_KEY_FILE` | `/app/config/ee-key.json` | the JSON key, copied to `config/ee-key.json` on the node. `config/` is mounted read-only |
| `GROUND_SAT_WIDE_KM` | `60` | `basemap`: half-width of the wide context square, in km. The close square is `place`'s `GROUND_RADIUS_KM` |

### What it does not know

Dynamic World is a classifier, and a kilometre around a house is mostly other people's land, so the cell is
`partial` always. The Earth Engine land-change score that used to live here and the per-pixel distance in
`earth` measure different things and did not agree, so only `earth`'s is kept. The adapter's own comments say
it has not yet run against a live account.

## place

What is around the node, from OpenStreetMap, kept in PostGIS on the node and summarised once a month:
buildings and how much ground they cover, shops and warungs, schools, clinics, temples, roads, green, and the
walk to the nearest of each. It describes structure and change, and says nothing about behaviour.

| | |
|---|---|
| Kind | code |
| Domain | `place` |
| Requires node | `>=0.26.0` |
| Metrics | 22: `buildings`, `built_share`, `commercial_share`, `businesses_per_km2`, `poi_food`, `poi_retail`, `poi_education`, `poi_health`, `poi_worship`, `poi_lodging`, `poi_services`, `roads_km`, `green_share`, `nearest_school_m`, `nearest_health_m`, `nearest_market_m`, `nearest_worship_m`, and the satellite half `sat_buildings`, `sat_confidence`, `osm_building_coverage`, `sat_buildings_yearly`, `sat_height_m_yearly` |
| Scales | community |
| Sources | `economic/community/openstreetmap` (the registry files OpenStreetMap once) |
| Needs | `PACKS_ALLOW_CODE=1`; `planetai packs install` (`pip:` `earthengine-api`); network to the Overpass API; PostGIS in the node's database image. For the optional Open Buildings half, the `earth-engine` pack's credentials |
| Attribution | © OpenStreetMap contributors, ODbL, via Overpass; Google Open Buildings V3 and Temporal v1 (CC BY 4.0) via Earth Engine |

The adapter writes `place-point` (`kind='map'`, `scale='community'`) and creates the tables `place_features`,
`place_runs`, `place_yearly` and `place_buildings_sat` after `CREATE EXTENSION postgis`. The first poll fetches
everything within `PLACE_RADIUS_M` from Overpass, later polls recompute from what is stored, and every
`PLACE_REFRESH_DAYS` it fetches again. It also notices a moved node (more than 1% of the radius, never less
than 25 m) and refetches, clearing the satellite footprints and yearly series of the old circle.

### Rules

| rule | level | cooldown | fires when |
|---|---|---|---|
| `place_around` | info | 43200 (`long_cooldown_ok`) | the `place-point` observations have `buildings > 0`: one message a month describing the circle |

### Cells

| cell | unit | state | min_buckets | what the SQL counts |
|---|---|---|---|---|
| `Economic\|Community` | businesses per km² within the radius | partial | 1 | the latest `businesses_per_km2` observation on `place-point` |

Business density stands in until a fab lab's machine log or a market's stall count exists, which is why the
cell says `partial`.

### Scripts

- `planetai run place refresh`: force a fetch from Overpass, so edits to the map reach the node within minutes.
- `planetai run place gaps`: the mapping briefing, with untyped buildings, empty categories, named places without hours and unnamed streets, written to `out/place-gaps.md` for a mapping afternoon at the lab.
- `planetai run place verify`: PostGIS, OpenStreetMap, Earth Engine and Open Buildings, each step named; it names the mismatch after a move.
- `planetai run place basemap [--only vector|drone] [--dry-run]`: keeps a map of the place on the node's disk, in `out/ground/`, served at `GET /ground/*`: OpenStreetMap vector tiles cut from Protomaps' daily build, in three rings to zoom 15, with the label fonts, and any OpenAerialMap drone mosaic (CC BY 4.0) that crosses the drone ring. Protomaps and OpenAerialMap learn the square once, and the script says so before it runs.

`planetai run place satellite` also shows in the script list, because `satellite.py` is a non-adapter `.py`
in the folder. It is a module the adapter imports, not a command.

### Settings

| setting | default | meaning |
|---|---|---|
| `PLACE_RADIUS_M` | `1000` | radius around the node to describe, in metres |
| `PLACE_REFRESH_DAYS` | `30` | how often to re-fetch from OpenStreetMap |
| `GROUND_RADIUS_KM` | `12` | `basemap`: half-width of the street-level square, in km |
| `GROUND_DRONE_RADIUS_KM` | `4` | `basemap`: the ring a drone mosaic must cross, in km |
| `GROUND_DRONE_MAXZ` | `18` | `basemap`: the finest zoom kept for a drone mosaic |

It also reads `OVERPASS_URL` (default `https://overpass-api.de/api/interpreter`) and, for Open Buildings,
`EE_KEY_FILE`, `EE_PROJECT` and `EE_SERVICE_ACCOUNT`.

### What it does not know

A zero means unmapped, and every message and label says so: a circle with no school may only be a circle where
nobody has mapped one. If the map is wrong about your place, fix the map, and never from Google Maps or Google
imagery. With the `earth-engine` credentials in place, the monthly refresh also
fetches Google Open Buildings V3 footprints (confidence at or above 0.65) and the Temporal dataset's yearly
building count and mean height for 2016 to 2023; `GET /history?sensor_id=place-point&metric=sat_buildings_yearly`
is the series. After a move it takes `planetai restart`, `planetai run place refresh` and a dashboard reload.

## make

Where somebody can go to make or fix something: the active fab labs nearest the node, from the Fab Lab Network
directory, with what each one can do. It names the place and stops there: nothing in the code hands a job to a
workshop.

| | |
|---|---|
| Kind | code |
| Domain | `make` |
| Requires node | `>=0.64.0` |
| Metrics | none |
| Scales | community |
| Sources | `economic/community/fablabs-io`, `economic/community/fablabs-network-data-archive` |
| Needs | `PACKS_ALLOW_CODE=1` and `MAKE_ENABLED=1`; network to `gitlab.fabcloud.org` (the default) or `api.fablabs.io`; `NODE_LAT` and `NODE_LON` |
| Rules and cells | none: `rules.yml` is comments only and there is no `cells.yml` |

`MAKE_ENABLED` ships as `0`, and the pack has its own switch because an empty `PACKS_ENABLED` means every pack.
Set `MAKE_ENABLED=1` in `.env`, then `planetai restart`. `planetai doctor` says which state the node is in: off,
with the reason; `make: <n> fab lab(s) within 50 km · fablabs.io @ <snapshot> · read <date>`; or
`make: no fab lab within 50 km of this node yet`.

It stores one `sensors` row per active lab inside `MAKE_RADIUS_KM`, a `facility` with no readings; the row and
its `meta` are on [Data schema](schema.md). `meta` never holds an email or a telephone number, although most
upstream records carry them. A facility reaches no metric, cell or alert, and is never in custody.

Near the end of the report, after what happened and before the to-do lines, it adds one sentence:

```
Nearest place to make or fix something: <lab>, <km> km (<up to three capabilities>).
```

It is in Indonesian and Spanish too, capability names included (`laser cutting`, `pemotongan laser`, `corte
láser`). A lab under 0.05 km away prints as `<0.1 km`. The same sentence travels in `GET /issues` as
`asks.where`, and the dashboard draws it in Act, under the record of what was asked and answered. With the
pack off, the dashboard shows the help text the node publishes for `MAKE_ENABLED`.

### Settings

| setting | default | meaning |
|---|---|---|
| `MAKE_ENABLED` | `0` | the pack's own on-switch. Read the licence note below first |
| `MAKE_RADIUS_KM` | `50` | how far to look for a lab, in km |
| `MAKE_SOURCE` | `archive` | `archive` reads the Fab Foundation's dated monthly snapshots at `gitlab.fabcloud.org/fl-management/fablab-network-data`; `live` reads `api.fablabs.io/0/labs.json`, whose own root page says it has been removed |
| `MAKE_SNAPSHOT` | empty | which dated snapshot to read, such as `2026.07.31_labs.json`. Blank takes the newest and logs that it did. A pin makes every node on it answer the same way |
| `MAKE_REFRESH_DAYS` | `30` | how often to re-read. The archive is monthly |

One read is about 5.3 MB and the publisher ignores every query parameter, so the pack checks staleness before
it fetches, and a node that already has its labs does nothing.

### What it does not know

Active labs with no coordinates cannot be placed; the adapter counts them and logs the number on every read.

> **Careful.** The directory is not openly licensed. Each lab keeps copyright in its own record (fablabs.io
> Terms of Use §8.1), no data licence is published, and §7.4 and §7.5 restrict bulk collection and commercial
> use. Fab City Foundation decided that PLANETAI may read it and accepted responsibility for that, pending a
> Terms of Use clause. That decision covers the Foundation and not each node's operator, who is a separate
> party to those terms. The full reading is in `data/sources/data/economic/community/fablabs-io.yaml` and
> `packs/make/README.md`. If that matters to you, leave this pack off.

## fire

Fires that satellites saw near the node in the last day, from NASA FIRMS: how many, how far, in which
direction, and whether they lie where the wind is coming from. It says when a fire is near, when one is upwind,
and, only when the air outside is rising too, that smoke is probably arriving.

| | |
|---|---|
| Kind | code |
| Domain | `air` |
| Requires node | `>=0.81.0` |
| Metrics | `fires_local_24h`, `fires_region_24h`, `frp_local_mw`, `frp_region_mw`, `fires_nearest_km`, `fires_nearest_bearing`, `fires_local_upwind`, `fires_region_upwind`, `fires_upwind_km`, `fires_upwind_bearing`, `fire_wind_from_deg` |
| Scales | bioregion |
| Sources | `environmental/bioregion/nasa-firms` |
| Needs | `PACKS_ALLOW_CODE=1` and `FIRE_ENABLED=1`; network to `firms.modaps.eosdis.nasa.gov`; `NODE_LAT` and `NODE_LON` |
| Scripts | none |
| Cells | none |
| Attribution | NASA FIRMS, VIIRS 375 m active fire detections from NOAA-20, NOAA-21 and Suomi NPP, distributed by LANCE; NASA data are CC0 |

It is off unless `FIRE_ENABLED=1` because of the bandwidth. Without a key it reads FIRMS's public regional
file per satellite whenever that file changed, 1 to 2 MB a satellite for South East Asia, and the 7-day file
once at first start; it asks with HEAD first, at most every `FIRE_POLL_HOURS`, and an unchanged file writes
no rows. The region file is `SouthEast_Asia` or `Europe` when the whole regional ring fits it, else `Global`.
With `FIRMS_MAP_KEY` (listed under `secrets:`) it asks the keyed area API for the ring's box instead.

The adapter writes one sensor, `firms-fires` (`source='firms'`, `kind='model'`, `scale='bioregion'`,
`local=False`, no coordinates), and every channel is `derived`. Counts are burning places, one per ~445 m cell
a day however many satellites saw it, with low confidence dropped. Upwind is within 45° of where the wind comes
from, by the node's own wind: a local kit, then the core Open-Meteo point, then `fc_wind_direction` bounded
`ts <= now()`. Its `sections:` entry, `fire` (stage observe, `wall: true`), shows fires nearby, in the region
and upwind, and the nearest fire's distance and bearing; it stays out of `/issues` until the node holds a row
of it. The source line under the band says how far each ring reaches, from `FIRE_LOCAL_KM` and `FIRE_REGION_KM`.

### Rules

The rules are not kinded, so they send the same way on every `ALERT_ENGINE`. Each message gives the place as a
distance and a compass direction from the house. The thresholds were written from one day of FIRMS at Kuta
Selatan (`thresholds:` in `pack.yaml`).

| rule | level | cooldown | fires when |
|---|---|---|---|
| `fire_near` | info | 1440 | at least one fire in the local ring |
| `fire_upwind_near` | warn | 720 | at least one fire in the local ring is upwind |
| `smoke_arriving` | act | 1440 | 25 or more burning places upwind in the regional ring, and outdoor PM2.5 (outdoor sensors, else CAMS) over the last 2 hours past the WHO line of 15 µg/m³ and half again its level of the 6 hours before |

25 is about half of everything the 150 km ring held on the day the pack was written. It is a first guess
and has not been calibrated.

### Settings

| setting | default | meaning |
|---|---|---|
| `FIRE_ENABLED` | `0` | the pack's own on-switch |
| `FIRE_LOCAL_KM` | `25` | the local ring, in km: burning near enough to smell |
| `FIRE_REGION_KM` | `150` | the regional ring, in km: smoke that travels. Singapore may want 500 |
| `FIRE_POLL_HOURS` | `3` | how often to ask, in hours |
| `FIRE_SATELLITES` | `noaa-20,noaa-21` | any of `noaa-20`, `noaa-21`, `suomi-npp`, one file each |
| `FIRMS_MAP_KEY` | empty | optional, a secret: the keyed area API instead of the public files |

### What it does not know

A small rubbish fire is usually below what a 375 m pixel sees, and cloud hides fires, so an empty ring does not
mean clean air.

## open-data-health

Turns a CKAN portal's maintenance state into a `Governance|City` cell: how much of a city's open data was
touched in the last 90 days, since a portal nobody updates is an archive. It was written from the Index
registry, which lists four CKAN portals under `governance|city`.

| | |
|---|---|
| Kind | data |
| Domain | `governance` |
| Requires node | `>=0.3.0` |
| Scales | city, region |
| Sources | `governance/city/open-data-bcn`, `governance/city/analyze-boston`, `governance/city/datos-gob-cl`, `governance/city/bali-satu-data` |
| Needs | the core `ckan` adapter, with `CKAN_PORTALS` set in `.env`; a CKAN portal with a public `package_search` endpoint |
| Scripts | none |
| Settings | none of its own; the `ckan` adapter reads `CKAN_PORTALS` |

### Rules

| rule | level | cooldown | fires when |
|---|---|---|---|
| `portal_gone_stale` | warn | 10080 | a `kind='portal'` observation of `datasets_fresh_pct` is under 10 |

### Cells

| cell | unit | state | min_buckets | what the SQL counts |
|---|---|---|---|---|
| `Governance\|City` | % of published datasets updated in the last 90 days | partial | | mean of the latest `datasets_fresh_pct` per portal, over portals read in the last 7 days |
| `Governance\|City` | open datasets published | partial | | sum of the latest `datasets_total` per portal, over portals read in the last 7 days |

### What it does not know

The 10% line is a guess until someone watches a real portal for a quarter and corrects it. The dataset count
says little; the share touched in 90 days says whether anyone is home. Socrata and ArcGIS portals would need
their own adapters, and the cell SQL would stay the same.

## thingdata

Reads one or more ThingData servers, the reuse-city repair-knowledge protocol, and turns each catalogue into
observations: how many things are described, how many have a repair guide or story, and whether anyone is
still writing. It was written against the reference implementation's source and has not met a deployment yet.

| | |
|---|---|
| Kind | code |
| Domain | `repair` |
| Requires node | `>=0.10.0` |
| Metrics | `things_total`, `guides_total`, `stories_total`, `things_documented_pct`, `knowledge_fresh_90d_pct` |
| Scales | city, region |
| Needs | `PACKS_ALLOW_CODE=1`; a ThingData server with the v0.1.3 public read API (`GET /api/v1/{things,guides,stories,relationships}`, no auth) |
| Scripts | none |
| Attribution | ThingData Protocol server (reuse-city), github.com/reuse-city/thingdata-server |

The adapter writes one sensor per server, `thingdata-<slug>`, with `kind='portal'`, `local=False`, the scale
from `THINGDATA_SCALE`, cadence `P1D` and no coordinates. There is no count endpoint, so it pages the whole
catalogue, 100 rows a request, and refuses above `THINGDATA_MAX` instead of reporting a truncated total. A thing
counts as documented when a guide or story names it, or a relationship from one points at it. The freshness
figure is the share of guides and stories written or revised in the last 90 days. With `THINGDATA_INSTANCES`
blank the pack idles.

### Rules

| rule | level | cooldown | fires when |
|---|---|---|---|
| `repair_commons_quiet` | warn | 10080 (`long_cooldown_ok`) | a `kind='portal'` observation of `knowledge_fresh_90d_pct` is under 10 |

The 10% line is the guess `open-data-health` makes about portals, carried over unchanged.

### Cells

| cell | unit | state | min_buckets | what the SQL counts |
|---|---|---|---|---|
| `Economic\|City` | % of catalogued things with a repair guide or story | partial | | mean of the latest `things_documented_pct` per server, over servers read in the last 7 days |
| `Economic\|City` | repair guides and stories published | partial | | sum of the latest `guides_total` and `stories_total` per server, over servers read in the last 7 days |

The cell keys are literals and say City. A node whose server covers a region should edit both to
`Economic|Region`, as the comment in `cells.yml` says.

### Settings

| setting | default | meaning |
|---|---|---|
| `THINGDATA_INSTANCES` | empty | the servers to read, `slug=url`, comma separated. Blank, the pack idles |
| `THINGDATA_SCALE` | `city` | the scale of what those servers cover, `city` or `region` |
| `THINGDATA_MAX` | `5000` | refuse to count a collection larger than this |

### What it does not know

ThingData entities carry no coordinates, so a server three continents away counts the same as the one down
the road. The pack cannot tell whether a guide is any good, whether anyone followed it, or whether a thing was
repaired.

## things

The things this home keeps and the ones it offers: `GET /things`, `POST /things`, `PATCH` and `DELETE /things/{id}`
(the admin token only) and `GET /offers` (every share level, by the household's choice). One row per thing, with how
often it is used, whether it works and whether it is offered; three private counts per class (`stock`, `idle`,
`repair`) written as readings on the node's own survey sensor whenever one changes, so a readout, a rule or a cell can
use them and nothing sends them. An offer is a public line at the node's res-8 cell, with a link to the node's Telegram
bot, which passes one message on to the household.

| | |
|---|---|
| Kind | code: `routes.py`, no adapter |
| Domain | `things` |
| Requires node | `>=0.83.0` |
| Shares | `/offers` on every level (`share: {"off": [/offers]}`) |
| Rules and cells | none yet |

Core until 24 October 2026. The `things` table stays in `init.sql`, and the private role on the counts stays declared
by the core, so a node that switches this pack off keeps its readings private and loses no row. With the pack off,
`/things` and `/offers` answer 404 and the daily export carries no offers. On `planetai update`, a node that lists its
packs in `PACKS_ENABLED` gets `things` added, because every node had it.

## eyes

The pictures a household takes of its own place, and what is in them: `POST`/`GET /captures`, `PATCH`/`DELETE
/captures/{id}`, `GET /captures/{id}/file`, `POST /captures/{id}/describe` and `GET /species`. A picture is cleaned on
arrival (its location kept as a cell, never a point) and kept on its own disk. The image model on this house's own
network describes it as findings in the flows classes, the model's until a person confirms one. With `SPECIES_MATCH` on,
a finding's scientific name is asked of GBIF, and two weekly reads say whether this country lists it as introduced or
invasive (GRIIS) and how many open records others have made in the node's seven cells.

| | |
|---|---|
| Kind | code: `routes.py` and two weekly jobs (`check_griis`, `check_others`), no adapter |
| Domain | `species` |
| Requires node | `>=0.83.0` |
| Needs | a disk for the pictures; the image model on the house's network; `api.gbif.org` with `SPECIES_MATCH` on |
| Rules and cells | none: a finding is the model's until a person confirms it |

Core until 24 October 2026. The `captures` table stays in `init.sql` and the pictures stay where they are; the three
settings stay the core's, because two of them change what leaves the house. With the pack off, the routes answer 404,
the Data door says so, and the weekly reads do not run. On `planetai update`, a node that lists its packs in
`PACKS_ENABLED` gets `eyes` added, because every node had it.

## example-cooking-hours

The worked example: don't shout about indoor PM2.5 during normal cooking hours, say it once, after. It has two
files, `pack.yaml` and `rules.yml`, and no README.

| | |
|---|---|
| Kind | data |
| Domain | none declared in `pack.yaml`; `docs/PACKS.md` places it under the `air` issue |
| Requires node | `>=0.1.1` |
| Scales | community |
| Needs | a local indoor PM2.5 sensor |
| Scripts | none |
| Settings | none |
| Cells | none: it is an example of a rule |

### Rules

| rule | level | cooldown | fires when |
|---|---|---|---|
| `post_cooking_summary` | info | 1440 | between 20:00 and 23:59 local time, a local indoor sensor's 15-minute PM2.5 mean is over 35.5; one row per sensor with its `peak` |

### What it does not know

Cooking hours are fixed in the SQL, 20:00 to 23:59, and the pack cannot tell cooking from any other source of
indoor smoke at that hour. The comment on its `kind: data` line explains the distinction for every pack: data
means rules and cells only, and code means the folder ships `adapter.py`; the loader now counts any `.py` file.

## Where this leads

A pack that reads an outside source names it in `sources:`, and that id has to be an entry in the network's
registry first. The entries nobody has written a pack or an adapter for yet are listed on
[the source registry](sources.md); how to write the one your place needs is on [Packs](packs.md).
