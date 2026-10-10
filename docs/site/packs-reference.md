# Packs that ship
<!-- checked: v0.80.10 -->

Seventeen core packs ship in `packs/` in v0.80: ten data packs and seven code packs. Wild packs, written for one
place and kept by their authors, are listed at [fabcity/planetai-wild-packs](https://github.com/fabcity/planetai-wild-packs) and added with `planetai packs add`. Between them they hold
everything the node knows about a place. No rule in `app/` says what PM2.5 means for a household, what a hot night is, where
the sea starts or where the nearest fab lab is; the air, the heat, the coast, the land, the repair commons and
the nearest workshop are all in here, as SQL and YAML, and in seven cases as an adapter too. How a pack is
built, loaded and linted is on [Packs](packs.md); this page is what each shipped pack does in v0.80.

A pack is `data` if its folder has no `adapter.py`, and `code` if it has one. The `kind:` line in `pack.yaml`
is documentation; the presence of the file is what the loader reads. Code packs load only with
`PACKS_ALLOW_CODE=1`, and `make` also needs `MAKE_ENABLED=1`.

| pack | kind | domain | rules | report | cells | scripts | settings |
|---|---|---|---|---|---|---|---|
| `air-quality` | data | air | 4 act, 2 warn; and the event engine's 3 act, 1 warn | — | 3 | — | — |
| `heat` | data | heat | 2 act, 1 info; and the event engine's 3 act | — | 1 | — | — |
| `nearby` | data | air | 1 act, 1 info | `alone` | — | `stations` `status` `verify` `backfill` | `BAD_*` |
| `season` | data | air | 1 info | `record` | — | `window` | — |
| `insight` | data | cross-domain | 2 info | `digest` | — | — | — |
| `trust` | data | cross-domain | 3 info | — | — | — | — |
| `cold-start` | data | cross-domain | 3 info | — | — | — | — |
| `forecast` | code | weather | none | `ahead` | — | `fetch` `status` `verify` `windfield` | `FORECAST_*` |
| `coast` | code | coast | 2 info | — | 1 | — | `COAST_MAX_KM` |
| `earth` | code | land | none | — | 1 | `fetch` `change` `frames` `status` `verify` `similar` | `EARTH_*` |
| `earth-engine` | code | land | none | — | 1 | `timelapse` `verify` `basemap` | `EE_*`, `GROUND_SAT_WIDE_KM` |
| `place` | code | place | 1 info | — | 1 | `refresh` `gaps` `verify` `basemap` | `PLACE_*`, `GROUND_*` |
| `make` | code | make | none | the nearest-lab line | — | — | `MAKE_*` |
| `open-data-health` | data | governance | 1 warn | — | 2 | — | `CKAN_PORTALS` (core adapter) |
| `thingdata` | code | repair | 1 warn | — | 2 | — | `THINGDATA_*` |
| `example-cooking-hours` | data | (none) | 1 info | — | — | — | — |

That is 33 rules with a message (26, and the 7 the event engine reads), 4 report contributors and 12 cells. Every rule with a message carries `en`,
`id` and `es`, and so do the two core rules in `config/rules.yml`; Spanish reached every alert template in
v0.63. The node picks `message[ALERT_LOCALE]` and falls back to `en`. Cooldowns below are in minutes, per
`(rule, sensor_id)`.

> **Note.** `example-cooking-hours` is the worked example, and `season`, `thingdata` and `make` arrived in
> v0.61 and v0.65. `xiaomi-air` and `posidonia` are wild packs, listed at [fabcity/planetai-wild-packs](https://github.com/fabcity/planetai-wild-packs).

## air-quality

The first domain pack, and the one that proves the core is domain-blind. PM2.5 rules built around the decision a
household faces (is the room better or worse than the street, should the windows be open or shut) and
three Index cells. Learned at Kuta Selatan, Bali, September 2026, against Smart Citizen Kit 19880 and the public
picture from Bali Air Dispatch; the README notes the burning pattern there peaks around 9am and climbs again after
dark.

| | |
|---|---|
| Kind | data |
| Domain | `air` |
| Requires node | `>=0.2.0` |
| Metrics | `pm25`, `pm10`, `pm1`, `humidity` |
| Scales | community, city |
| Needs | a low-cost PM sensor at the address, and at least two public outdoor sensors within range for the comparison rules |
| Scripts | none |

The comparison rules pick an ambient reference in a fixed order: the node's own outdoor sensors first, then the
three nearest public outdoor sensors (`NOT local`, `kind='sensor'`, silent under 120 minutes), then the CAMS
model (`observations` where `sensor_id='cams-point'` and `metric='pm25_model'`). Thresholds are US EPA / WHO 2021:
35.5 µg/m³ is unhealthy for sensitive groups, 15 µg/m³ is the WHO 24-hour guideline.

### Rules

| rule | level | cooldown | fires when | languages |
|---|---|---|---|---|
| `indoor_pm25_high` | act | 120 | a local indoor sensor's 15-minute PM2.5 mean is over 35.5 | en, es, id |
| `outside_worse_keep_shut` | act | 180 | the best ambient reference is over 35.5 and more than 1.5 times the indoor 1-hour mean | en, es, id |
| `inside_worse_ventilate` | act | 180 | the indoor 1-hour mean is over 15 and more than 1.5 times the best ambient reference | en, es, id |
| `outdoor_pm25_high` | act | 180 | a local outdoor sensor's 1-hour mean is over 55.5 | en, es, id |
| `indoor_spike` | warn | 90 | an indoor 15-minute mean is at least 12 and at least 2.5 times the greater of its 24-hour mean and 2 | en, es, id |
| `outdoor_spike` | warn | 90 | an outdoor sensor (local, or within about 0.03° of the node) silent under 60 minutes has a 15-minute mean of at least 15 and at least 2.5 times the greater of its 24-hour mean and 2 | en, es, id |

Two rules declare `watch:`: `indoor_pm25_high` watches `pm25` over 35.5 and `outdoor_pm25_high` watches
`pm25` over 55.5, so `GET /effect` can say how long after somebody acted the hourly mean came back under the
line. The other four carry none: the two comparison rules fire on a relation between inside and outside, and
the two spike rules on a ratio to the sensor's own day.

The pack also carries four rules with a `kind:`, which only the event engine reads ([Alerts](alerts.md#the-event-engine)).
Under `ALERT_ENGINE=rules` they are skipped. Under `shadow` and `events` they write no `alerts` row; each returns
`value`, `line`, `over` and `where` (`inside` or `outside`), and the engine folds them into one `air` event. Their
messages are the one line the engine tells the story with. Cooldown 60 for each; the numbers are starting values
from the replay of node #1's month.

| rule | kind | level | `over` when |
|---|---|---|---|
| `air_spike` | spike | warn | a local sensor's latest 15-minute mean is at least 12 above the mean of the preceding hour and at least 10 above this room's 90th percentile for the local hour (a row from a rise of 7 keeps an open event open) |
| `air_unusual` | unusual | act | every 15-minute mean of the last hour is at least 15 above this room's usual 90th percentile for the hour (a row from an hourly mean 10 above keeps an open event open) |
| `air_sustained` | sustained | act | the 15-minute means over the last hour are all at least 35 µg/m³ (rows from a mean of 30 keep it open) |
| `air_extreme` | danger | act | the latest 15-minute mean is at least 125.5 µg/m³ (rows from 115 keep it open) |

### Cells

| cell | unit | state | min_buckets | what the SQL counts |
|---|---|---|---|---|
| `Environmental\|Community` | µg/m³ PM2.5 (24h mean, sensors in this node's custody) | live | 12 | mean of `readings_1h.mean` over 24 hours for sensors where `sensors.custody` |
| `Environmental\|Community` | % of days over the WHO 24h PM2.5 guideline (30d, local outdoor) | partial | 20 | of the days with at least 12 hourly buckets from custody outdoor sensors, the share whose day mean is over 15 |
| `Environmental\|City` | µg/m³ PM2.5 (24h mean, public reference stations) | partial | — | 24-hour mean over sensors that are `NOT local AND NOT indoor AND kind='sensor'` |

The first cell is declared `live` but the core demotes it to `partial` until it has 12 hourly buckets and enough
in-custody sensors. The third is never `live`: the cells file says so, because those stations are not the node's
measurement.

### Settings

None of its own. The SQL reads the `planetai.lat` and `planetai.lon` GUCs and whichever sources the node polls.

### Know this

The README says "Fork it": the numbers that matter in Kerobokan are not the numbers that matter in Poblenou, and the
sentence that gets someone to close a window is different in every language and every building. Copy the folder,
change the thresholds and the wording, publish it as `planetai-pack-air-<yourplace>`, and list it at
[fabcity/planetai-wild-packs](https://github.com/fabcity/planetai-wild-packs) so other nodes can add it.

## heat

Turns the temperature and humidity the node already stores into three sentences about heat and one Index cell.
Apparent temperature is Steadman's no-wind form as published by the Australian Bureau of Meteorology,
`AT = T + 0.33·e − 4.0`, with `e` the vapour pressure in hPa. Written for Kuta Selatan, Bali: a humid tropical
house, 8°S, sea level, roughly 26–31 °C and 50–75% RH all year. The README says every threshold is that place's,
and a temperate node must move them.

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

| rule | level | cooldown | fires when | languages |
|---|---|---|---|---|
| `heat_stress_now` | act | 240 | a local indoor sensor's 15-minute temperature and humidity give an apparent temperature of 35 °C or more | en, es, id |
| `heat_danger` | act | 120 | the same, at 40 °C or more | en, es, id |
| `night_no_relief` | info | 1440 | over the last 12 hours, in the local hours outside 07–21, a local indoor sensor's hourly minimum never fell to 28 °C, with at least 5 buckets | en, es, id |

40 °C is the heat-index "danger" line and 28 °C overnight is the WHO ceiling for restorative sleep; the README calls
both "other people's numbers, not ours". 35 °C is the pack's own and was measured, not chosen: the rule shipped
at 32 °C, which in Kuta Selatan is the year-round baseline. Against node #1's two indoor kits over 2–7 September
2026, a line at 32 fired 20 times in 48 hours, ten of them at night; 35 °C is the hot room's p90 and fired eight
times in five days, never at night. The README records why the fix was the threshold and not a longer cooldown, a
duration gate or a trend.

The pack also carries three rules with a `kind:`, read only by the event engine ([Alerts](alerts.md#the-event-engine)):
skipped under `ALERT_ENGINE=rules`, and under `shadow` and `events` they write no `alerts` row and fold into one
`heat` event. They read `recent_15m`'s `apparent` and `usual_by_hour`, indoor sensors only, and leave out a sensor
whose `temp` channel is declared as something other than ambient (a Meshtastic radio's own box). Cooldown 60 each.

| rule | kind | level | `over` when |
|---|---|---|---|
| `heat_unusual` | unusual | act | every 15-minute mean apparent temperature of the last hour is at least 2 °C above this room's usual 90th percentile for the hour (a row from an hourly mean 1 °C above keeps an open event open) |
| `heat_sustained` | sustained | act | the room has been at 35 °C or more for at least 3 hours, and for more than its usual number of such hours (a row from a latest mean of 34 keeps an open event open) |
| `heat_extreme` | danger | act | the latest 15-minute mean is at least 40 °C (rows from 39 keep it open) |

This is how the engine says "dangerously hot" only at 40 °C and not at an ordinary 35 °C afternoon.

### Cells

| cell | unit | state | min_buckets | what the SQL counts |
|---|---|---|---|---|
| `Social\|Community` | hours in 30d with indoor apparent temperature ≥ 32 °C | live | 12 | custody indoor hourly buckets with AT at or above 32, divided by the number of distinct sensors |

The cell keeps 32 °C where the rule moved to 35. The README's reason: 32 is right for a count of exposure, which is
what a cell is, and wrong for an interruption, which is what a rule is.

### Know this

Every rule and the cell read local indoor sensors only, because the no-wind Steadman form is the indoor form and
the line was measured indoors. A node whose only local sensors are outdoors gets no heat alerts, which the README
calls the right answer rather than a wrong number. The pack does not know radiant heat or airflow, and its
calibration rests on five dry-season days at one house with a maximum AT of 36.5 °C: it has set the line above
the normal and has not yet met the abnormal. To move it, change the one `>= 35` in `heat_stress_now` to near the
90th percentile of your hottest indoor sensor.

## nearby

The ring: other people's air sensors around this node, from Bali Air Dispatch. One kit cannot tell a fire in the
lane from a haze over the whole island; the ring can. Learned at Kuta Selatan, September 2026, against the
archive's 87 stations.

| | |
|---|---|
| Kind | data |
| Domain | `air` |
| Requires node | `>=0.40.0` |
| Metrics | `pm25`, `pm25_raw`, `pm10`, `pm1`, `temp`, `humidity` |
| Scales | community |
| Sources | `environmental/community/bali-air-dispatch` |
| Needs | network to `baliairdispatch.com`; at least two public outdoor stations within `BAD_RADIUS_KM`; for `only_here`, a local outdoor sensor |

The ring is every sensor with `sensors.source='baliairdispatch'` that is not local, is outdoor and has reported in
the last 120 minutes. The thresholds at the top of `rules.yml`: a 10 µg/m³ floor, a 1.6 ratio, comparison
against the ring's 75th percentile, 35.5 for "everywhere", and at least two stations.

### Rules

| rule | level | cooldown | fires when | languages |
|---|---|---|---|---|
| `only_here` | act | 2880 | the ring has at least 2 stations and a local outdoor sensor's 1-hour mean is at least 10 over the ring's p75 and more than 1.6 times the ring's median | en, es, id |
| `everywhere` | info | 2880 | the ring has at least 2 stations and its median is over 35.5 | en, es, id |
| `alone` | — | — | report contributor: when the ring has fewer than 2 stations or the nearest is more than 10 km away, it puts `stations` and `nearest_km` in the report. Never sent | none |

`only_here` first asked the ring to "agree with itself" with a p25–p75 spread under 5 µg/m³. Node #1's six
neighbours in clean air are 9.3 µg/m³ apart, because they sit 4 to 15 km apart across the Bukit and south
Denpasar. The rule now asks the node to clear the top of the ring by the floor instead: a wide ring demands a
bigger excursion, a tight one fires sooner. Replayed over 2–7 September none of the three fired, which the README
calls the right answer; the case is pinned in `tests/test_nearby.py`.

### Cells

No cells, by design. `live` means measured here, and the ring is measured by other people through a third-party
aggregation. `Environmental|City` already exists in `packs/air-quality/cells.yml` as `partial` over exactly these
stations, and a second number for the same thing with different provenance is the duplication this pack exists
to refuse.

### Scripts

- `planetai run nearby stations`: every station in the archive, its distance, and `included` or `excluded: <reason>`. It comes from the same function the adapter uses, so the audit cannot drift from what the node stores.
- `planetai run nearby status`: the ring now: who is reporting, how far, how long ago.
- `planetai run nearby verify`: every exclusion fires, nothing external is stored as `local`, the ring recomputes. Exit 1 on failure.
- `planetai run nearby backfill [days]`: each station's hourly PM2.5 history. Off by default (`BAD_BACKFILL_DAYS=0`); asked for, not scheduled.

### Settings

The pack declares no `env:` of its own; its scripts and the adapter in the core read these from `.env`.

| setting | default | meaning |
|---|---|---|
| `BAD_RADIUS_KM` | `15` | ring radius. 15 is the tightest radius that clears the two-station floor at node #1 with room to spare; 25 km reaches Canggu, a different airshed |
| `BAD_MIN_SEPARATION_M` | `150` | anything closer to the node than this is excluded as the node's own kit |
| `BAD_EXCLUDE` | — | station ids excluded by hand |
| `BAD_INCLUDE_INDOOR` | `0` | `1` keeps stations the archive marks `suspected_indoor` |
| `BAD_BACKFILL_DAYS` | `0` | history to pull on `backfill` |
| `BAD_ENABLED` | `1` in `.env.example`, `0` when absent | whether the core polls the archive at all |
| `NODE_LAT`, `NODE_LON` | — | the point the ring is measured from |
| `SC_USER`, `SC_DEVICES`, `AIRGRADIENT_HOSTS` | — | read to know which devices this node already polls (the identity exclusion) |

### Know this

The pack has no adapter. The fetch lives in `app/sources.py` and has since v0.11; a second one would put every
station in the node twice. Keeping the node's own kit out of its own ring is also done there, by four rules:
identity (a device this node polls, at any distance), proximity (within `BAD_MIN_SEPARATION_M`), by hand
(`BAD_EXCLUDE`), and one-device-two-networks (23 AirGradient units mirrored by OpenAQ, collapsed on same name within
the separation radius). Ownership is not the test; whether this node already measures that device is.

There is no `channels.yml` either: the pack adds no metric, and Bali Air Dispatch's channels are already declared
in `config/channels.yml`. Elsewhere the same three rules want an OpenAQ v3 backend behind the same shape.
Attribution: Bali Air Dispatch, baliairdispatch.com, and the network named in each row's `source`.

## season

The other half of `nearby`. That pack asks where the bad air is coming from, right now, across space. This one
asks across time: is this week worse than the weeks before it, or is this what the air here does? A data pack,
two SQL rules and a script, with no fetch of its own: it reads the Bali Air Dispatch ring the core already
stores. Written for Bali, from the archive's daily record January 2025 to 16 September 2026.

| | |
|---|---|
| Kind | data |
| Domain | `air` |
| Requires node | `>=0.40.0` |
| Metrics | `pm25` |
| Scales | community |
| Sources | `environmental/community/bali-air-dispatch` |
| Needs | the core's Bali Air Dispatch source on (`BAD_ENABLED=1`) and 68 days of the ring in this node's own database. `planetai run nearby backfill 90` fetches that depth from the archive once |

The comparison is paired: each ring station's last 7 days against its own preceding 60, and the median of
those differences. A station counts only if it holds at least 4 days in the week and 20 in the baseline. The
README's reason is the archive's growth, from 2 stations with usable daily rows in January 2025 to 79 in
September 2026: an unpaired comparison over that record would measure which networks joined, not what the air
did.

### Rules

| rule | level | cooldown | fires when | languages |
|---|---|---|---|---|
| `turning` | info | 4320 | at least 3 stations pair, the median paired step is 8 µg/m³ or more, and the median of the week is 20 µg/m³ or more | en, es, id |
| `record` | — | — | report contributor: `stations`, `week`, `usual`, `step` and `baseline_days` whenever one station pairs, whether or not the line was crossed. Never sent | none |

+8 µg/m³ is the top of what the record calls an ordinary week: the paired step's p90 was +8.2 across Bali and
+6.3 on node #1's 15 km ring. The week must also reach 20 µg/m³, because a step from 6 to 14 changes nobody's
afternoon. Three paired stations is the floor for saying anything. Replayed over the record, `turning` fires on
19 of 177 days across Bali, some eight episodes. The README is plain about scope: "These are Bali's numbers."

### Cells

No cells, for the same reason as `nearby`: `live` means measured here, and these are other people's stations
through a third-party archive.

### Scripts

- `planetai run season window`: every paired station, its week, its baseline and the step. The summary line
  runs the pack's own `record` rule, so the audit cannot drift from the report.

### Settings

None of its own. The ring is the one `nearby` describes, so the `BAD_*` settings shape it.

### Know this

It is not a climatology. The same days last year held two stations in the archive, so year over year is a
record that does not exist yet. The message says "its own last two months", never "normal for this time of
year". A node that has held the ring for less than four weeks pairs nothing, and `record` returns no row rather
than a number built on four days.

## insight

Three rules that turn the node's own history into sentences. No Python: Postgres has `corr()` built in. Written
against seven days at Kuta Selatan, 5 September 2026, from six Smart Citizen kits in one account plus CAMS.
Nothing leaves the machine.

| | |
|---|---|
| Kind | data |
| Domain | `cross-domain` |
| Requires node | `>=0.9.0` |
| Scales | community |
| Needs | nothing beyond what the node already holds; `rhythm` needs a local outdoor `noise` sensor |
| Scripts | none |

### Rules

| rule | level | cooldown | fires when | languages |
|---|---|---|---|---|
| `digest` | — | — | report contributor: inside (`n_in`), outside (own outdoor sensors, else the 3 nearest public), modelled (CAMS), `day_mean`, `day_peak` and `trend` (rising, falling or steady, last 3 hours against the prior 3, ±3). Returns a row only when inside is not NULL. Never sent | none |
| `agreement` | info | 1440 | 7 days of hourly indoor, outdoor and model give at least 48 indoor and 48 outdoor hours; reports `r_in_out`, `r_out_model`, `r_in_model`, `shield`, `model_bias`, `filtered_pct` | en, es, id |
| `rhythm` | info | 1440 | the week's worst and best outdoor hours (local time), and the loudest hour from a local outdoor `noise` sensor. `quiet_hr` holds the loudest hour; the name is pinned by tests | en, es, id |

### Cells

No cells. The pack describes how the node's sources agree with each other, which is not a fact about the place.

### Settings

None. The README: copy the folder and change `cooldown_minutes` to change the cadence; that is the whole
configuration.

### Know this

A node with no local outdoor noise sensor gets no `rhythm` alert. The SQL cross-joins a `loud` CTE built from
local outdoor noise readings; with none, the whole rule returns nothing. This is deliberate. The rule used to end
"that is the burning and the traffic, not the weather"; the one kit in the fleet with a noise sensor showed the
loud hours are the clean hours, so it stopped naming a cause its own data argued against.

The README keeps its original pooled correlations (r = 0.55 indoor to outdoor, the house filtering about 30%)
dated 5 September 2026 "for the record, not as current guidance". Measured pairwise, one indoor kit against one
outdoor kit 1.3 km apart gives r = 0.20. Prefer the pairwise figure.

## trust

Whether the node's own sensors are telling it the truth: coverage over the last week, channels that have stopped
changing under a kit that still reports, and collocated sensors that disagree about the level. Written from node
#1, Ungasan, after it sent that household three warnings on Telegram on 7 September 2026 at 21:17 and all three
were wrong.

| | |
|---|---|
| Kind | data |
| Domain | `cross-domain` |
| Requires node | `>=0.35.0` |
| Scales | community |
| Needs | local sensors with at least seven days of readings on this node |
| Scripts | none |
| Settings | none |

Every rule joins the same `seasoned` gate: a sensor whose first reading in the last 30 days is more than seven days
old. A statement about an instrument needs a week; a day says more about the weather and the hour than about the
sensor. All three rules are `info` with a seven-day cooldown, so the pack speaks in the week's instrument paragraph
rather than interrupting a household in the evening.

### Rules

| rule | level | cooldown | fires when | languages |
|---|---|---|---|---|
| `channel_dead` | info | 10080 | a local `kind='sensor'` channel with role `ambient` or `enclosure` has all 24 of the last 24 hourly buckets present and flat (`max − min = 0`), the flat value is not 0, the kit reported within 2 hours, and another ambient channel on the same kit moved | en, es, id |
| `coverage_low` | info | 10080 | a seasoned local ambient comparable channel reported for under 60% of the 168 hours in 7 days | en, es, id |
| `peer_disagreement` | info | 10080 | two seasoned local ambient comparable sensors within 50 m, each with at least 100 buckets in 7 days, have a 7-day mean ratio outside 0.85–1.15 and an absolute difference at or above a per-metric floor (5.0 for `pm1`, `pm25`, `pm10`; 2.0 for `temp`; 5.0 for `humidity`; 0.3 kPa for `pressure`; else 15% of the pair mean). One row per pair, `sensor_id = a\|b` | en, es, id |

`channel_dead` looks at values, not timestamps: Smart Citizen's per-reading `recorded_at` is null on every kit
node #1 reads, so a frozen channel still gets a fresh timestamp on every poll. Its first form (six flat buckets of
24) fired at dusk on every kit with a light channel; a full day of flat buckets is longer than any night in Kuta
Selatan, so no metric-specific exception is needed. The absolute floors in `peer_disagreement` come from the
instruments: 5 µg/m³ is Plantower's own ±10 µg/m³ below 100 µg/m³, halved.

### Cells

No cells, by design. A trust score is a fact about the node's instruments, not about the place; the README
says a cell that "scores our own competence invites us to optimise it rather than fix the sensor".
`channels.yml` is present and empty, to say plainly that the pack declares no metric of its own.

### Know this

`peer_disagreement` cannot tell a badly sited sensor from a badly calibrated one, which is why its message asks
the reader to swap the two units' positions for a day rather than naming which is wrong. The pack does not yet see
PurpleAir's `channel_disagreement` (node #1 has no PurpleAir hardware) or Meshtastic's `altitude_m`, which is
written outside `MESH_METRICS` and never gets a role. None of the thresholds has met a burn season.

## cold-start

Makes a node useful on day one with no hardware: a modelled air line, today against 40 years of climatology, and,
once a sensor arrives, how far it sits from the model. The README calls it a scaffold, not a foundation: delete the
folder when your own sensors carry the story.

| | |
|---|---|
| Kind | data |
| Domain | `cross-domain` |
| Requires node | `>=0.3.0` |
| Scales | community, planet |
| Sources | `environmental/planet/open-meteo`, `environmental/planet/nasa-power` |
| Needs | the `BOOTSTRAP` step on first start (92 days of CAMS hourly history, NASA POWER monthly normals) and the `open-meteo` and `open-meteo-cams` adapters. All free, key-free, global |
| Scripts | none |
| Settings | none |

The rules read `observations`, not `stats`.

### Rules

| rule | level | cooldown | fires when | languages |
|---|---|---|---|---|
| `modelled_air_today` | info | 10080 (`long_cooldown_ok`) | a `cams-point` / `pm25_model` observation exists. The daily reports carry the model reading now, so this is weekly | en, es, id |
| `hotter_than_normal` | info | 4320 | `om-point` / `temp_model` differs from `power-point` / `temp_norm` for this month by more than 3 | en, es, id |
| `sensor_vs_model` | info | 10080 | the 24-hour mean of local outdoor PM2.5 differs from CAMS by more than 15 | en, es, id |

### Cells

No cells. Nothing here is ever eligible for a `live` cell, because none of it is a measurement of your place.

### Know this

The README on `sensor_vs_model`: a big gap is not an error, it is the local signal the global model cannot see,
which is the entire argument for hyperlocal nodes.

## forecast

Official and model weather for this point over the next day, wind direction and rain, as context for reading the
node's own air. It fetches; it does not predict; it never sends an alert. Written for node #1 with BMKG,
Indonesia's meteorological agency, as the source that is on.

| | |
|---|---|
| Kind | code |
| Domain | `weather` |
| Requires node | `>=0.40.0` |
| Metrics | `fc_temp`, `fc_humidity`, `fc_wind_speed`, `fc_wind_direction`, `fc_cloud`, `fc_rain`, `fc_lead_hours`, `fc_temp_gap`, `fc_wind_speed_gap` |
| Scales | community |
| Needs | `PACKS_ALLOW_CODE=1`; network to `api.bmkg.go.id` and `api.open-meteo.com`; correct node coordinates; for BMKG, a village code |

### Rules

| rule | level | cooldown | fires when | languages |
|---|---|---|---|---|
| `ahead` | — | — | report contributor: the next 24 hours from `readings` of `kind='model'` with `source IN ('forecast-bmkg','forecast-om')`, giving `wind_kmh`, `wind_from_deg`, `rain_mm`, `rain_from`, `lead_hours`. Never sent | none |

`tests/test_forecast.py` fails if any rule here grows a level or a message. The README's reason is the same
evening as `trust`: three wrong warnings on 7 September. Forecasts are wrong often, wrong about tomorrow rather
than now, and there is no action a household takes at 9pm because of rain predicted for tomorrow that it would not
take by looking out of the window.

### Cells

No cells. A forecast is not measured here and is nobody's Index cell.

### Scripts

- `planetai run forecast verify`: the `adm4` code resolves to somewhere near the node (province, regency, district, village and distance printed; past 10 km the card says so), units are as documented, BMKG's `analysis_date` is under 18 hours old. Exit 1 on failure.
- `planetai run forecast fetch`: fetch now instead of waiting for the poll; writes to `sensors` and `readings`.
- `planetai run forecast status`: the next day: wind, rain, temperature, and when it was issued.
- `planetai run forecast windfield`: refresh the wind field now (below). Refuses unless `FORECAST_OPENMETEO=1`.

### Settings

| setting | default | meaning |
|---|---|---|
| `FORECAST_BMKG` | `1` | poll BMKG. 3-hourly, three days, no key. `ws` is km/h, `wd_deg` is where the wind comes from, `tp` is rain in mm for the step |
| `FORECAST_BMKG_ADM4` | empty | the Permendagri village code for this point. Node #1 is `51.03.05.2002`, Kuta Selatan / Ungasan, 194 m from the node. Without a code the pack logs one line and idles |
| `FORECAST_OPENMETEO` | `0` | poll Open-Meteo, hourly, anywhere. Off because its free tier is non-commercial only; that is the operator's decision |
| `FORECAST_POLL_HOURS` | `6` | BMKG allows 60 requests a minute per IP and enforces it; it publishes twice a day, so anything faster asks a cache the same question |
| `FORECAST_WIND_N` | `8` | points a side of the wind field: 8 × 8 |
| `FORECAST_WIND_KM` | `30` | half-width of the wind field's square, in km |

Also reads `NODE_LAT` and `NODE_LON`.

### Know this

Every channel in `channels.yml` is `role: derived`, `comparable: false`, for sources `forecast-bmkg`, `forecast-om`
and `forecast-gap`. A forecast must never pool with a sensor's ambient reading; the `fc_` prefix is the second
guard. Every value is stored at its valid time with `fc_lead_hours` beside it. Open-Meteo publishes no model run
time, so the node records when it fetched and labels it `fetched`, not `issued`. When both sources are on, a third
derived channel records how far apart they are on temperature and wind for the same hour. With Open-Meteo on, each
poll also keeps its hourly 10 m wind for the next day over the node's square, and the node's own point, in one
request, as `out/ground/wind.json`, served at `GET /ground/wind` for the map to draw. It asks with
`cell_selection=nearest`, because the default moves a sea point to the nearest land cell, up to 12 km off. It is a
model's field, not a reading: it reaches no cell, no alert and no report. Attribution: BMKG must
be named inside the application and is, on the card and in the export; Open-Meteo is CC BY 4.0.

## coast

Waves, swell and sea-surface temperature at the nearest ocean grid cell, every poll, from Open-Meteo's Marine API.
Free, key-free, global. Learned at Kuta Selatan, 5 September 2026, where the nearest cell was 5 km off the Bukit;
the README says Barcelona's Mediterranean would set the thresholds lower.

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

The adapter writes one sensor, `marine-point`, with `source='open-meteo-marine'`, `kind='model'`,
`scale='bioregion'`, `local=False`, cadence `PT1H`. The API snaps to the nearest ocean cell however far that is;
the adapter measures the distance and raises if it is over `COAST_MAX_KM`, so a node in Ubud does not receive the
weather of a sea it cannot see.

### Rules

| rule | level | cooldown | fires when | languages |
|---|---|---|---|---|
| `heavy_swell` | info | 720 | `swell_height_m` is at least 2.5 and `swell_period_s` at least 12: the combination that means strong currents on exposed beaches | en, es, id |
| `sea_warm_anomaly` | info | 1440 | the current sea-surface temperature is at least 1.0 °C above its own mean over days 7 to 60 back | en, es, id |

### Cells

| cell | unit | state | min_buckets | what the SQL counts |
|---|---|---|---|---|
| `Environmental\|Bioregion` | sea surface temperature, 7d mean, °C (nearest ocean cell) | partial | — | 7-day mean of `sea_surface_temp` on `marine-point`. Never `live`: it is a model |

### Settings

| setting | default | meaning |
|---|---|---|
| `COAST_MAX_KM` | `30` | refuse to report if the nearest ocean cell is further away than this, in km |

### Know this

The wild `posidonia` pack reads this pack's `sea_surface_temp`; without `coast` enabled it has nothing to read.
Attribution: Open-Meteo Marine API (CC BY 4.0), carrying Copernicus Marine / MeteoFrance MFWAM model data.

## posidonia (wild)

Now a wild pack, listed at [fabcity/planetai-wild-packs](https://github.com/fabcity/planetai-wild-packs) (`planetai packs add posidonia`). Thermal stress on *Posidonia oceanica*, the seagrass the Balearic coast is built on, read from the sea-surface
temperature the `coast` pack already fetches. No new source, no key, no metric of its own. Written for Menorca,
Illes Balears, by Lucas Marangoni (Fab City Foundation). Add with:

```bash
planetai packs add posidonia
```

28.4 °C is Marbà & Duarte (2010), *Global Change Biology* 16:2366–2375: six years of seawater temperature and shoot
demography at Cabrera Archipelago National Park, about 90 km from Menorca, above which the meadow loses more
shoots than it recruits. 27 °C is the watch level from the thermal-tolerance literature.

## earth

The node's own copy of Google's AlphaEarth Satellite Embedding layers for its square of the planet, and the
year-over-year per-pixel change computed here from them: cosine distance at 10 m. Downloaded once on command, kept
as files, compared with arithmetic. It says something changed, never what. Calibrated on one 10 km square of Kuta
Selatan.

| | |
|---|---|
| Kind | code |
| Domain | `land` |
| Requires node | `>=0.33.0` |
| Metrics | `land_change_yoy`, `land_change_since_2017`, `years_cached` |
| Scales | city |
| Sources | `environmental/city/alphaearth-satellite-embedding` |
| Needs | `PACKS_ALLOW_CODE=1`; `planetai packs install` for `rasterio` and `numpy`; network to `storage.googleapis.com` on the first fetch only. No key, no account, no cloud project. Disk: 64 MB per year cached, 576 MB for all nine |

The adapter writes `earth-point` (`kind='model'`, `scale='city'`) and reads only what is already cached under
`out/earth/<node>/`: `<year>.npy`, `meta.json`, `change_<A>_<B>.png` and `.json`, `year_<YYYY>.png`. Nothing is
downloaded on a poll. The directory is named for the node but matched on its `meta.json`: the point it was read
around, within the move tolerance, and the radius. So a directory written under an earlier `NODE_NAME` is
adopted as it stands. Node #1's rename to `bayu-ungasan` once cost a full re-read of nine years for that
reason. `planetai run earth status` names any directory that no longer matches, with its size and point, and
nothing is deleted.

### Rules

No rules, by design. The README: any threshold that fires in Kuta Selatan, where the land is being built
on, also fires in Boston every year for reasons nobody there can act on (snow and leaf-off between two annual
composites is the likeliest explanation for Boston's 3.26% "changed"), and this node does not send messages a
household would ignore. When there is a way to tell a season from a bulldozer, the alert can come back.

### Cells

| cell | unit | state | min_buckets | what the SQL counts |
|---|---|---|---|---|
| `Environmental\|City` | land change: mean per-pixel cosine distance between consecutive annual AlphaEarth embeddings (0 = unchanged) | partial | 1 | the latest `land_change_yoy` observation on `earth-point` |

It stays `partial` however good it is: the node did the arithmetic, but the input is a model's description of a
place, not a measurement anyone here could repeat. `air-quality` also contributes an `Environmental|City` cell;
two cells under one key is how this node already works and `/cells` lists both.

### Scripts

- `planetai run earth fetch [year ...] [--force]`: every year the dataset has (or `EARTH_YEARS`); `--force` re-reads a cached one. About 103 MB and 150 seconds per year; all nine is roughly 22 minutes, so run it from a shell rather than over MCP.
- `planetai run earth change [A B | --all] [--force]`: the two latest consecutive cached years, any two, or every consecutive pair plus the oldest-to-newest span. Read the span first, then the years.
- `planetai run earth frames [--refit]`: one grey picture of the place per cached year for the card to animate. Not photographs: the first principal component of the embedding. `--refit` redoes the projection, which a moved square needs and a new year does not.
- `planetai run earth status`: years, bytes, comparisons, what the cell reports.
- `planetai run earth verify`: seven checks: the dataset's claims against the files (unit-length vectors after de-quantising), and whether the reading landed.
- `planetai run earth similar [year] [--out FILE]`: the four pilots in `presets/` compared with each other and their own tiles. A regional search (one UTM tile, about 82 km a side), not a global one.

### Settings

| setting | default | meaning |
|---|---|---|
| `EARTH_RADIUS_M` | `5000` | half-width of the square around the node, in metres. 5000 is a 10 km square: 64 MB on disk and about 103 MB pulled, per year |
| `EARTH_YEARS` | empty | which years to fetch, comma separated. Blank means every year the dataset has (2017–2025) |

Also reads `NODE_LAT`, `NODE_LON`, `NODE_NAME`, `PACK_OUT` and `DATABASE_URL`. No padding after `=` in `.env`: a
value pasted after spaces makes the line `VAR= value`, which shell reads as a command.

### Know this

`CHANGED = 0.15` is one constant at the top of `packs/earth/change.py`, the only number in the pack that was chosen
rather than measured; at node #1 it sits at about the 99th percentile of a consecutive-year comparison. The
number is not comparable between places: for 2024→2025 the mean is 0.0414 in Kuta Selatan, 0.0404 in Boston,
0.0164 in Barcelona, 0.0151 in Santiago. Change the coordinates or the radius and `fetch` re-reads every cached
year; a correction under 1% of the radius (never less than 25 m) is recorded as `point_drift_m` and leaves the
cache alone. Attribution travels with every derivative: "The AlphaEarth Foundations Satellite Embedding dataset is
produced by Google and Google DeepMind. CC BY 4.0."

## earth-engine

What the land within a kilometre of the node did last year, from Google Earth Engine's public catalog: tree, built,
crop and water fractions (Dynamic World), annual median NDVI (Sentinel-2, clouds masked), the latest night-lights
radiance (VIIRS). A code pack with a dependency and a credential; the README calls it the worked example of both.
Computed server-side, stamped mid-year; a daily fetch inserts nothing new after the first.

| | |
|---|---|
| Kind | code |
| Domain | `land` |
| Requires node | `>=0.10.0` |
| Metrics | `tree_frac`, `built_frac`, `crop_frac`, `water_frac`, `ndvi_median`, `night_lights` |
| Scales | bioregion |
| Needs | `PACKS_ALLOW_CODE=1`; `planetai packs install` for `earthengine-api`; a Google Earth Engine project (free for research and non-commercial use) and a service-account key mounted read-only at `config/ee-key.json` |

The adapter writes `ee-point` (`source='earth-engine'`, `kind='model'`, `scale='bioregion'`). Until configured the
pack logs one line and idles. Setup is five steps in the README: register the project, create a service account
with Earth Engine Resource Viewer and Service Usage Consumer (Resource Writer for timelapse images), copy the JSON
key, `planetai packs install` and `planetai restart`, then `verify`.

### Rules

No rules. The `land_change_score` metric and the `land_changed` alert that used to live here moved to `earth` in
v0.33.1 (see below).

### Cells

| cell | unit | state | min_buckets | what the SQL counts |
|---|---|---|---|---|
| `Environmental\|Bioregion` | tree-cover fraction within 1 km (Dynamic World, last complete year) | partial | — | the latest `tree_frac` reading on `ee-point` |

### Scripts

- `planetai run earth-engine verify`: library, settings, key file, credentials, a real query, the datasets. Names the step that failed.
- `planetai run earth-engine timelapse [--years a,b,c | --n 4 --gap 5] [--km 2] [--px 1024] [--source landsat|sentinel] [--lat --lon] [--dry-run]`: annual-median frames of clear pixels; Landsat by default (the only archive reaching 2010 with one instrument family), Sentinel-2 for 2016 onward at 10 m. PNGs and a side-by-side page land in `out/`.
- `planetai run earth-engine basemap [--months 12] [--dry-run]`: the median of every clear Sentinel-2 pass over the last twelve months, built in the node's own Earth Engine project and kept as tiles at zoom 8–15 in `out/ground/imagery.mbtiles`, served at `GET /ground/imagery`. Earth Engine learns the two squares, once, and the script says so before it runs.

### Settings

| setting | default | meaning |
|---|---|---|
| `EE_PROJECT` | empty | the project id, e.g. `planetai-node-472103`, not the service account's 21-digit number; Earth Engine reports that mistake as "project not found". Blank reads it from the key file |
| `EE_SERVICE_ACCOUNT` | empty | blank is fine; the key file names it |
| `EE_KEY_FILE` | `/app/config/ee-key.json` | the JSON key, copied to `config/ee-key.json` on the node. `config/` is mounted read-only |
| `GROUND_SAT_WIDE_KM` | `60` | `basemap`: half-width of the wide context square, in km. The close square is `place`'s `GROUND_RADIUS_KM` |

### Know this

The folder ships one cell and no `rules.yml`; land change is not here. The `earth` pack's README records why: the Earth Engine score (1 − cosine similarity of the
mean embedding over 1 km, behind a key) and the per-pixel distance over 10 km from the public bucket are different
quantities that did not agree (0.037 against 0.041 at node #1), so the Earth Engine one was retired and the
`land_changed` alert moved with it. `earth-engine` keeps what only Earth Engine can give: Dynamic World, Sentinel-2
and VIIRS. The adapter's own comments say it has not yet been run against a live account.

Node #1 for 2025 per the README: 91% built, 9% trees, no crops, NDVI 0.51, night lights 14.5. Dynamic World is a
classifier, and a kilometre around a house is mostly other people's land; the cell is `partial`, always.

## place

What is around the node, from OpenStreetMap, kept in PostGIS on the node and summarised once a month: buildings and
how much ground they cover, shops and warungs, schools, clinics, temples, roads, green, and the walk to the nearest
of each. Structure and change, not behaviour. At node #1 in September 2026: 2,904 buildings, 540 road segments,
37 mapped places, two health, no school. The README says that last number is OpenStreetMap coverage on the Bukit,
not the Bukit.

| | |
|---|---|
| Kind | code |
| Domain | `place` |
| Requires node | `>=0.26.0` |
| Metrics | 22, among them `buildings`, `built_share`, `commercial_share`, `businesses_per_km2`, `poi_food`, `poi_retail`, `poi_education`, `poi_health`, `poi_worship`, `poi_lodging`, `poi_services`, `roads_km`, `green_share`, `nearest_school_m`, `nearest_health_m`, `nearest_market_m`, `nearest_worship_m`, and the satellite half `sat_buildings`, `sat_confidence`, `osm_building_coverage`, `sat_buildings_yearly`, `sat_height_m_yearly` |
| Scales | community |
| Sources | `economic/community/openstreetmap` (the registry files OpenStreetMap once) |
| Needs | `PACKS_ALLOW_CODE=1`; `planetai packs install`; network to the Overpass API; PostGIS in the node's database image. For the optional Open Buildings half, the `earth-engine` pack's credentials |

The adapter writes `place-point` (`kind='map'`, `scale='community'`) and creates the tables `place_features`,
`place_runs`, `place_yearly` and `place_buildings_sat` after `CREATE EXTENSION postgis`. The first poll fetches
everything within `PLACE_RADIUS_M` from Overpass; later polls recompute from what is stored; every
`PLACE_REFRESH_DAYS` it fetches again. It also notices a moved node (more than 1% of the radius, never less than
25 m) and refetches, clearing the satellite footprints and yearly series that described the old circle.

### Rules

| rule | level | cooldown | fires when | languages |
|---|---|---|---|---|
| `place_around` | info | 43200 (`long_cooldown_ok`) | the `place-point` observations have `buildings > 0`: one message a month describing the circle | en, es, id |

### Cells

| cell | unit | state | min_buckets | what the SQL counts |
|---|---|---|---|---|
| `Economic\|Community` | businesses per km² within the radius | partial | 1 | the latest `businesses_per_km2` observation on `place-point` |

Business density is the proxy until a fab lab's machine log and a market's stall count exist, which is why the cell
says `partial`.

### Scripts

- `planetai run place refresh`: force a fetch from Overpass. Edits to the map reach the node within minutes this way.
- `planetai run place gaps`: the mapping briefing: untyped buildings, empty categories, named places without hours, unnamed streets, written to `out/place-gaps.md` for a mapping afternoon at the lab.
- `planetai run place verify`: PostGIS, OpenStreetMap, Earth Engine, Open Buildings, each step named; names the mismatch while a moved node lasts.
- `planetai run place basemap [--only vector|drone] [--dry-run]`: keeps a map of the place on the node's disk, in `out/ground/`, served at `GET /ground/*`: OpenStreetMap vector tiles cut out of Protomaps' daily build, in three rings to zoom 15, with the label fonts; and any OpenAerialMap drone mosaic (CC BY 4.0) that crosses the drone ring. Protomaps and OpenAerialMap learn the square, once, and the script says so before it runs.

`planetai run place satellite` also appears in the script list, because `satellite.py` is a non-adapter `.py` in
the folder. It is a module the adapter imports, not a command.

### Settings

| setting | default | meaning |
|---|---|---|
| `PLACE_RADIUS_M` | `1000` | radius around the node to describe, in metres |
| `PLACE_REFRESH_DAYS` | `30` | how often to re-fetch from OpenStreetMap |
| `GROUND_RADIUS_KM` | `12` | `basemap`: half-width of the street-level square, in km |
| `GROUND_DRONE_RADIUS_KM` | `4` | `basemap`: the ring a drone mosaic must cross, in km |
| `GROUND_DRONE_MAXZ` | `18` | `basemap`: the finest zoom kept for a drone mosaic |

Also reads `OVERPASS_URL` (default `https://overpass-api.de/api/interpreter`) and, for Open Buildings,
`EE_KEY_FILE`, `EE_PROJECT` and `EE_SERVICE_ACCOUNT`.

### Know this

Zeroes mean unmapped, and every message and label says so. If the map is wrong about your place, fix the map,
never from Google Maps or Google imagery. With the `earth-engine` credentials in place, the monthly refresh also
fetches Google Open Buildings V3 footprints (confidence at or above 0.65) and the Temporal dataset's yearly building
count and mean height for 2016–2023; `GET /history?sensor_id=place-point&metric=sat_buildings_yearly` is the series.
After a move it takes `planetai restart`, `planetai run place refresh` and a dashboard reload. Attribution:
© OpenStreetMap contributors, ODbL, via Overpass; Google Open Buildings (CC BY 4.0) via Earth Engine.

## make

Where somebody can go to make or fix something: the active fab labs nearest this node, from the Fab Lab
Network directory, with what each one can do. This pack is the first thread from a reading to a place that can
make or fix something. In v0.80 it names the place and stops there: no node has handed a job to a workshop,
and nothing in the code sends one.

| | |
|---|---|
| Kind | code |
| Domain | `make` |
| Requires node | `>=0.64.0` |
| Metrics | none |
| Scales | community |
| Sources | `economic/community/fablabs-io`, `economic/community/fablabs-network-data-archive` |
| Needs | `PACKS_ALLOW_CODE=1` **and** `MAKE_ENABLED=1`; network to `gitlab.fabcloud.org` (the default) or `api.fablabs.io`; `NODE_LAT` and `NODE_LON` |

It is off unless `MAKE_ENABLED=1`, and `MAKE_ENABLED` ships as `0`. The pack has its own switch because an
empty `PACKS_ENABLED` means every pack, and v0.65 turned this one on at update on a node that already allowed
code packs. Set `MAKE_ENABLED=1` in `.env`, then `planetai restart`. `planetai doctor` says which state the
node is in: `make: off (MAKE_ENABLED=0 — the directory it reads is not openly licensed, see packs/make/README.md)`,
or `make: <n> fab lab(s) within 50 km · fablabs.io @ <snapshot> · read <date>`, or
`make: no fab lab within 50 km of this node yet`.

### What it stores

Places, not numbers. One `sensors` row per active lab inside `MAKE_RADIUS_KM`: `sensor_id` `lab-<slug>`,
`kind='facility'`, `scale='community'`, `local=False`, `source='fablabs-io'`, cadence `P30D`, and **no
readings**. `meta` holds the slug, the capabilities, the kind, the city, the country, the distance, the lab's
own URL, the registry id, the snapshot and when it was read. It never holds an email or a telephone number,
although most upstream records carry them. A facility reaches no metric, no cell and no alert: `rules.yml` is
comments only, there is no `cells.yml`, and `custody` is generated as `kind='child' OR (local AND
kind<>'peer')`, so a lab can never make an Index cell say `live`.

### What it says

Near the end of the report, after what happened and before the to-do lines, one sentence:

```
Nearest place to make or fix something: <lab>, <km> km (<up to three capabilities>).
```

in Indonesian and Spanish too, capability names included (`laser cutting`, `pemotongan laser`, `corte láser`). A
lab under 0.05 km away prints as `<0.1 km`. The same sentence travels in `GET /issues` as `asks.where`, and the
dashboard draws it in Act, under the record of what was asked and answered. With the pack off, the dashboard shows the help text the node
publishes for `MAKE_ENABLED` instead.

### Settings

| setting | default | meaning |
|---|---|---|
| `MAKE_ENABLED` | `0` | the pack's own on-switch. Read the licence note below first |
| `MAKE_RADIUS_KM` | `50` | how far to look for a lab, in km |
| `MAKE_SOURCE` | `archive` | `archive` reads the Fab Foundation's dated monthly snapshots at `gitlab.fabcloud.org/fl-management/fablab-network-data`; `live` reads `api.fablabs.io/0/labs.json`, whose own root page says it has been removed |
| `MAKE_SNAPSHOT` | empty | which dated snapshot to read, e.g. `2026.07.31_labs.json`. Blank takes the newest and logs that it did. A pin makes every node on it answer the same way |
| `MAKE_REFRESH_DAYS` | `30` | how often to re-read. The archive is monthly |

One read is about 5.3 MB and the publisher ignores every query parameter, so the pack checks staleness before
it fetches, and a node that already has its labs does nothing. Active labs with no coordinates cannot be
placed; the adapter counts them and logs the number on every read (179 network-wide on 2026-09-20).

### Licence

> **Careful.** From `packs/make/README.md`, as it stands: "The directory is **not openly licensed**. Each lab
> retains copyright in its own record (fablabs.io Terms of Use §8.1) and no data licence is published; §7.4
> restricts bulk collection and §7.5 restricts commercial use. Fab City Foundation decided on 2026-09-20 that
> PLANETAI may read it and accepted responsibility for that, pending a Terms of Use clause. **That decision
> covers the Foundation, not each node's operator** — every operator is a separate party to those terms. The
> full reading is in `data/sources/data/economic/community/fablabs-io.yaml`. If that matters to you, leave
> this pack off."

## open-data-health

Turns a CKAN portal's maintenance state into a `Governance|City` cell: how much of a city's open data was touched
in the last 90 days. The README: a portal nobody updates is an archive, not open data. Written from the Index
registry, which lists four CKAN portals under `governance|city`, not from a deployment.

| | |
|---|---|
| Kind | data |
| Domain | `governance` |
| Requires node | `>=0.3.0` |
| Scales | city, region |
| Sources | `governance/city/open-data-bcn`, `governance/city/analyze-boston`, `governance/city/datos-gob-cl`, `governance/city/bali-satu-data` |
| Needs | the core `ckan` adapter, with `CKAN_PORTALS` set in `.env`; a CKAN portal with a public `package_search` endpoint |
| Scripts | none |

### Rules

| rule | level | cooldown | fires when | languages |
|---|---|---|---|---|
| `portal_gone_stale` | warn | 10080 | a `kind='portal'` observation of `datasets_fresh_pct` is under 10 | en, es, id |

### Cells

| cell | unit | state | min_buckets | what the SQL counts |
|---|---|---|---|---|
| `Governance\|City` | % of published datasets updated in the last 90 days | partial | — | mean of the latest `datasets_fresh_pct` per portal, over portals read in the last 7 days |
| `Governance\|City` | open datasets published | partial | — | sum of the latest `datasets_total` per portal, over portals read in the last 7 days |

### Settings

None of its own. The `ckan` adapter it depends on reads `CKAN_PORTALS`.

### Know this

The README says where it was learned: nowhere yet. It runs, but the 10% "stale" threshold is a guess until someone
watches a real portal for a quarter and corrects it. Dataset count is a vanity number; the share touched in 90 days
says whether anyone is home. Socrata and ArcGIS portals need their own adapters; the cell SQL would not change,
only the source.

## thingdata

Reads one or more ThingData servers, the reuse-city repair-knowledge protocol, and turns each catalogue into
observations: how many things are described, how many have a repair guide or story, and whether anyone is still
writing. The README says where it was learned: nowhere yet. It was written against the reference
implementation's source, not a deployment.

| | |
|---|---|
| Kind | code |
| Domain | `repair` |
| Requires node | `>=0.10.0` |
| Metrics | `things_total`, `guides_total`, `stories_total`, `things_documented_pct`, `knowledge_fresh_90d_pct` |
| Scales | city, region |
| Needs | `PACKS_ALLOW_CODE=1`; a ThingData server with the v0.1.3 public read API (`GET /api/v1/{things,guides,stories,relationships}`, no auth) |
| Scripts | none |

The adapter writes one sensor per server, `thingdata-<slug>`, with `kind='portal'`, `local=False`, the scale
from `THINGDATA_SCALE`, cadence `P1D` and no coordinates. There is no count endpoint, so it pages the whole
catalogue, 100 rows a request, and refuses above `THINGDATA_MAX` rather than report a truncated total. A thing
counts as documented when a guide or story names it, or a relationship from one points at it. The freshness
figure is the share of guides and stories written or revised in the last 90 days. With `THINGDATA_INSTANCES`
blank the pack idles.

### Rules

| rule | level | cooldown | fires when | languages |
|---|---|---|---|---|
| `repair_commons_quiet` | warn | 10080 (`long_cooldown_ok`) | a `kind='portal'` observation of `knowledge_fresh_90d_pct` is under 10 | en, es, id |

The 10% line is the guess `open-data-health` makes about portals, carried over unchanged, and it has never been
watched against a real ThingData deployment.

### Cells

| cell | unit | state | min_buckets | what the SQL counts |
|---|---|---|---|---|
| `Economic\|City` | % of catalogued things with a repair guide or story | partial | — | mean of the latest `things_documented_pct` per server, over servers read in the last 7 days |
| `Economic\|City` | repair guides and stories published | partial | — | sum of the latest `guides_total` and `stories_total` per server, over servers read in the last 7 days |

The cell keys are literals and say City. The comment in `cells.yml` says a node whose server covers a region
should edit both to `Economic|Region`.

### Settings

| setting | default | meaning |
|---|---|---|
| `THINGDATA_INSTANCES` | empty | the servers to read, `slug=url`, comma separated. Blank, the pack idles |
| `THINGDATA_SCALE` | `city` | the scale of what those servers cover, `city` or `region` |
| `THINGDATA_MAX` | `5000` | refuse to count a collection larger than this |

### Know this

ThingData entities carry no coordinates, so a server three continents away counts the same as the one down
the road. The pack does not know whether a guide is any good, whether anyone followed it, or whether a thing was
repaired.

## example-cooking-hours

The worked example: don't shout about indoor PM2.5 during normal cooking hours, say it once, after. Two files,
`pack.yaml` and `rules.yml`, and no README.

| | |
|---|---|
| Kind | data |
| Domain | none declared in `pack.yaml`; `docs/PACKS.md` places it under the `air` issue |
| Requires node | `>=0.1.1` |
| Scales | community |
| Needs | a local indoor PM2.5 sensor |
| Scripts | none |
| Settings | none |

### Rules

| rule | level | cooldown | fires when | languages |
|---|---|---|---|---|
| `post_cooking_summary` | info | 1440 | between 20:00 and 23:59 local time, a local indoor sensor's 15-minute PM2.5 mean is over 35.5; one row per sensor with its `peak` | en, es, id |

### Cells

No cells. It is an example of a rule, not a contribution to the Index.

### Know this

The `kind: data` line in its `pack.yaml` carries the comment that explains the distinction for every pack: data
means rules and cells only, no code; code means the folder ships `adapter.py`.

## Where this leads

A pack that reads an outside source names it in `sources:`, and that id has to be an entry in the network's
registry first. The entries nobody has written a pack or an adapter for yet are listed on
[the source registry](sources.md); how to write the one your place needs is on [Packs](packs.md).
