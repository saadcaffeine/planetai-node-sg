# Insight generation on the node — exploratory design

Written 7 September 2026 against v0.32.1. Exploration only; nothing here is implemented, and no code was written.
Decisions taken by Tomas before this was drafted: insight generation is **layered** (features → rules → narration),
the **first layer is data integrity** (drift, gaps, agreement), and the design must be **source-agnostic** rather than
written against today's six kits.

Everything numeric below was measured on 7 September 2026 from the Smart Citizen public API: 7 days of hourly rollups
(169 buckets) for the six kits on account `tomasdiez` that have published in the last three days. It was not read from
node #1's Postgres, so coverage figures are what the *upstream* holds, which is the ceiling on what the node can hold,
not necessarily what it does hold. Confirming the two against `readings_1h` on `bayu-2` is the first job of any build.

---

## 1. What the fleet actually is

Six kits publish. `smartcitizen_account()` filters on `max_age_days=3`, so those six are the fleet; the other ten on
the account are 2016–2021 relics and correctly excluded.

| kit | name | exposure | lat, lon | channels | PM hardware signature |
|---|---|---|---|---|---|
| 19236 | Ungasan Kit - TEST | outdoor | -8.81983, 115.16657 | 21 | SEN5x / SPS30 class (PN counts, PM4.0, typical size) |
| 19874 | BAYU NEW ENCLOSURE | outdoor | -8.82008, 115.16669 | 8 | PM + BME680 |
| 19849 | SENX ALL IN ONE | indoor | -8.8271, 115.15709 | 8 | SEN55 (VOC Index, NOx Index, PM4.0) |
| 19880 | Bayu 2 - Indoor | indoor | -8.8271, 115.15709 | 8 | PM + BME680 |
| 19897 | NEW FIRMWARE TEST | indoor | -8.8271, 115.15709 | 8 | PM + BME680 |
| 19898 | Ulu Garden - Making Sense Bali | indoor | -8.81654, 115.09338 | 8 | PM + BME680 |

Four of the six are the sensor Tomas described as the Bali bay node: a Plantower-class PM head plus a BME680, which
publishes as PM1 / PM2.5 / PM10 / Air Temperature / Relative Humidity / Barometric Pressure / Gas Resistance / AQI.
`Bosch BME68X - AQI` is the literal sensor name in the API, so the AQI channel is the BME680's own internal index, not
a PM-derived AQI. Nothing in the node treats it as such; the `aqi` metric is mapped and stored as if it were an air
quality index. That is a mislabel worth fixing before any insight leans on it.

**The fleet is an accidental collocation experiment, and nobody is reading it as one.** Computed pairwise distances:

```
19880 ↔ 19849 ↔ 19897 :    0 m   (three indoor kits, same coordinates)
19236 ↔ 19874          :   31 m   (two outdoor kits, same site)
19898                  : 7.0 km   (alone)
```

Three kits in one room and two on one pole is the exact configuration an air-quality lab pays for. It exists here by
accident, because these are test units. It is the single most valuable asset in the data and the insight layer should
be built on top of it.

---

## 2. What seven days of it say

### 2.1 Coverage is the biggest error source, and the node cannot see it

| kit | hourly buckets / 168 | coverage | PM2.5 mean | median | p95 | max | sd |
|---|---|---|---|---|---|---|---|
| 19236 | 169 | 100% | 8.71 | 7.93 | 14.35 | 22.6 | 3.23 |
| 19849 | 169 | 100% | 9.65 | 7.51 | 18.48 | 191.3 | 14.95 |
| 19874 | 160 | 95% | 8.24 | 7.75 | 12.90 | 16.9 | 2.53 |
| 19880 | 143 | 85% | 6.04 | 5.05 | 9.87 | 84.4 | 7.09 |
| 19897 | 76 | 45% | 6.49 | 4.27 | 8.52 | 138.2 | 15.35 |
| 19898 | 5 | 3% | 10.47 | 8.05 | 9.08 | 21.3 | 5.52 |

Kit 19898 reported `last_reading_at = 2026-09-07T06:21:48Z`, minutes before the query, and holds **five of 168 hours**.
The kit is alive and its data is 97% absent. `docs/sensors.md` states the rule — *latest held is not latest measured* —
and the node implements it at kit level via `stats.silent_minutes`. That check cannot fire here, because the kit keeps
speaking.

Worse, `data.recorded_at` is **null on all six kits**, so `smartcitizen()` falls back to the kit-level
`last_reading_at` and stamps *every channel on the kit with one timestamp*. Three consequences:

1. A single dead channel is invisible. The kit is fresh, so the channel looks fresh.
2. If a channel freezes while the kit-level timestamp advances, the frozen value is re-inserted under new timestamps.
   `UNIQUE (sensor_id, metric, ts)` does not stop it, because `ts` is new each time. The frozen value then pulls the
   24-hour mean toward itself and collapses the variance — the reading looks *more* stable as it dies.
3. Channels with genuinely different cadences are recorded as simultaneous.

This is not a Smart Citizen problem to solve upstream. It is the general case: **every source will eventually report a
kit-level heartbeat over a channel-level silence**, and the trust layer has to assume it.

### 2.2 Same air, different numbers: the inter-unit scale factor is 1.5×

The three indoor kits sit at the same coordinates and breathe the same room.

| pair | r | mean difference | ratio |
|---|---|---|---|
| 19849 vs 19880 | 0.981 | +3.06 µg/m³ | **1.508** |
| 19849 vs 19897 | 0.974 | +2.76 µg/m³ | **1.426** |
| 19880 vs 19897 | 0.981 | −0.45 µg/m³ | 0.930 |
| 19236 vs 19874 (outdoor, 31 m) | 0.971 | +0.37 µg/m³ | 1.045 |

Read the columns separately, because they say different things. **r says the units agree about the shape of the day**
(0.97–0.98 everywhere; these are good sensors). **Ratio says they disagree about the level**, and the disagreement
tracks hardware: the two PM+BME680 units agree within 7%, and the SEN55 reads about 45–50% higher than either of them
in the same room. Outdoors, where both units are again different classes, they agree within 5%.

So 19849 is either differently scaled or differently sited within that room — a metre from a kitchen, a doorway, a
laptop fan. Its peaks are the tell: max 191.3 against 84.4 for a kit at the same coordinates, and sd 14.95 against
7.09. A collocated pair cannot distinguish "reads high" from "sits closer to the source" without moving one unit. That
is a one-afternoon field test and it should happen before this number is used for anything.

What matters for the insight layer either way: **the indoor fleet average is currently weighted by which hardware
happened to be online in that hour.** `packs/insight/rules.yml` computes
`avg(mean) FILTER (WHERE s.local AND s.indoor)` before it correlates or thresholds anything. With 19897 at 45%
coverage and 19849 reading 1.5× the others, the indoor average moves when a kit reconnects. The air did not change.
The mix changed.

That also explains a discrepancy in our own published numbers. `packs/insight/README.md` records indoor tracking
outdoor at r = 0.55 for 5 September. Measured pairwise for the same 7-day window, 19880 against 19874 gives
**r = 0.204** over 134 overlapping hours. Both can be arithmetically correct. Only one of them is a statement about a
house and a street; the other is a statement about a pooled average of mixed hardware with holes in it.

**A mean over sensors that disagree by 50% is not a measurement. It is a mixing ratio.**

### 2.3 Humidity is not the dominant error here

r(PM2.5, own RH) per kit: 0.317 (19236), 0.277 (19897), 0.214 (19874), 0.117 (19849), 0.054 (19880).

`docs/sensors.md` is right not to apply the EPA 2021 correction to Smart Citizen, and the data does not argue for it.
At this site's levels (means of 6–10 µg/m³) the humidity coupling is weak. The Fieldguide calls a humidity-corrected
PM model "the single most valuable model to build". On this evidence it is not — **the inter-unit scale factor is
about five times larger than anything humidity is doing.** Fix the units against each other first; revisit humidity
when the fleet runs through a burn season at 40–60 µg/m³, where the regression actually bites.

### 2.4 Fifteen channels are discarded, and only three of them are worth having

Kit 19236 publishes 21 channels. `SC_METRICS` maps 6 of them. Unmapped: `PM4.0`, `PN0.5`, `PN1.0`, `PN2.5`, `PN4.0`,
`PN10.0`, `Typical Particle Size`, `VOC Index`, `NOx Index`, `UVA`, `UVB`, `UVC`, `battery`, `RSSI`,
`SD-Card Presence`. (`Noise Level` and `Light` *are* in `SC_METRICS`, but only 19236 emits them, and no rule or cell
reads either one.)

Before mapping them, I checked whether they carry information. Two honest negatives, which save the work:

- **Particle number counts are redundant.** r(PM2.5, PN0.5) = **0.999**. The firmware derives PM from PN, so the PN
  channels repeat PM2.5 at a different scale. Mapping five of them adds five columns and no knowledge.
- **Typical Particle Size is flat and uninformative at this site.** Range 40.35–52.08 over seven days, mean 44.32,
  r(PM2.5, size) = **−0.112**, r(PM10, size) = −0.09, r(size, RH) = −0.04. It does not separate dust from smoke here.
  It might in a burn season or a dust storm; it does nothing in an ordinary week. (Also note the value is not in µm as
  an SPS30 datasheet would suggest, so its unit needs establishing before anyone reports it.)

And one strong positive, which is the best new insight available today:

**Noise runs anti-phase to PM2.5, and that changes what the node is allowed to say.** Hour-of-day means in WITA:

```
hour   00    03    06    07    09    12    15    17    18    19    21    23
PM2.5  8.5   8.3  10.0  10.5   7.8   6.3   6.5   8.4  14.7  12.1  10.1   9.0
Noise 36.8  36.9  39.2  40.8  43.5  50.7  49.3  50.0  44.0  42.4  41.5  37.8
Light    —     —     —     —     —   high  high   —    low    —     —     —
```

r(PM2.5, Noise) = **−0.239**. The loud hours are the clean hours. PM2.5 peaks hard at 18:00 (14.7, nearly double the
midday 6.3) with a secondary peak at 06:00–07:00, while noise peaks 10:00–17:00 and is at its floor overnight.

`packs/insight/rules.yml` currently asserts, in the `rhythm` message, *"That is the burning and the traffic, not the
weather."* The noise channel we already collect and discard says the traffic half of that sentence is wrong. The
18:00 peak arrives as noise falls and daylight goes — after work, at sunset, when the wind drops. That is burning, and
possibly cooking. Traffic hours are the *cleanest* hours of the day at this site.

**One channel we already measure and throw away contradicts a claim the node already publishes.** That is the
argument for the trust layer in a single sentence.

---

## 3. What to build: four layers

Tomas chose features → rules → narration. Mapping that onto what the node already has:

```
L0  trust      per-channel liveness, coverage, inter-unit bias, drift.        new pack, mostly SQL + a little Python
L1  features   derived series written back as readings on synthetic sensors.  code packs, the `earth` pattern
L2  rules      thresholds and comparisons over L0/L1.                         rules.yml, unchanged contract
L3  narration  the agent turns rows into sentences, and refuses when L0 says no.  app/agent.py
```

Two things to preserve, because they are the good decisions already made: rules stay SQL over views, and provenance is
never upgraded on the way up. Add a third: **L3 may not narrate a number L0 has flagged.** The trust layer earns its
place by being able to silence the storyteller.

### L0 — the `trust` pack

Four numbers, per sensor and per channel, all of them SQL over `readings` and `readings_1h`:

| feature | definition | why |
|---|---|---|
| `coverage_7d` | distinct hourly buckets with n ≥ 1, over 168 | catches 19898 at 3% while its kit says "now" |
| `channel_silence` | hours since this `(sensor_id, metric)` last *changed value* | catches a frozen channel under a live kit |
| `flatline_hours` | consecutive hours where max − min = 0 | the freeze that a mean cannot see |
| `peer_ratio` | this sensor's mean over the collocated cluster's median, per metric | the 1.508 |

`peer_ratio` needs a definition of "collocated", which is the source-agnostic part (§4). Everything else is
per-channel arithmetic on data already stored.

`channel_silence` cannot be computed from a timestamp, because the timestamps lie. It has to be computed from **value
change**: how long since this channel produced a value different from the one before it. That is the only definition
that survives a kit-level heartbeat, and it should be the node's general rule for every source, not a Smart Citizen
patch.

Where the numbers live: one synthetic sensor row per node, `trust-<node>`, `kind='model'`, following `earth-point`
and `place-point`. No schema migration, no new table, and they show up in `/observations` and the dashboard for free.

Three rules fall straight out, and all three are things the fleet would have told us this week:

- `channel_dead` — a channel silent or flat for 6+ hours while its kit is fresh. Level `warn`.
- `coverage_low` — a local sensor under 60% of the last 7 days. Level `info`, daily. Names the kit.
- `peer_disagreement` — a collocated sensor whose ratio to its cluster median leaves 0.85–1.15 for 24 h. Level `warn`.

### L1 — features, and what the first two should be

The `earth` pack is the pattern to copy: a script computes, writes JSON to `out/` and readings to the database, and
`verify` exits non-zero with the failing line named. Two features first, both cheap, both with a decision attached:

**`fleet_reference`** — one honest outdoor number and one honest indoor number for the node, replacing the naive
average. Median rather than mean, restricted to channels L0 has not flagged, scaled to a declared reference unit by
`peer_ratio`, and carrying `n` and the set of contributing sensors. This is the number the Index cell should read.
The current cell reads an unweighted average across mixed hardware with holes in it, and it is the cell we publish as
`live`.

**`source_signature`** — for each PM event above the spike threshold, the co-movement of the channels that are already
being measured: noise, light, gas resistance, humidity, wind from Open-Meteo. Not a classifier. A row that says which
channels moved with the PM and which did not, so the narration can say "PM rose while noise stayed at its night floor
and light was gone" instead of asserting a cause. Attribution the node can defend is a *description of what
co-occurred*, never a named source.

### L2 and L3 — the discipline

Rules gain nothing new in contract. Two changes in practice: they read `fleet_reference` rather than raw averages, and
every rule that publishes a level states its `n` and its coverage in the row so L3 can qualify the sentence.

For L3, one addition to `app/agent.py`: `health_check()` already reports quiet radios. It should report quiet
*channels*, and the digest should refuse to state a fleet number when coverage is below the threshold, in the same
voice the empty states already use. A node that says "I do not have enough of the last day to tell you" is worth more
than one that averages two kits and calls it the house.

---

## 4. Source-agnostic, without building a framework nobody fills

Tomas picked the open registry over "today's sources only". Worth stating the risk once: the failure mode of a
registry is a schema that every pack has to satisfy and no pack benefits from. The way to avoid it is to declare only
what the integrity layer actually consumes, and to have the four L0 features be the only consumer at the start.

The minimum that is genuinely source-agnostic is **one new optional file per pack**, `channels.yml`, declaring what
each metric *is* rather than what it is called:

```yaml
- metric: pm25
  role: ambient            # ambient | enclosure | device_health | derived | index
  unit: "µg/m³"
  cadence: PT1M
  comparable: true         # may be compared across sensors at the same place
  reference: sen5x         # the instrument family, for peer_ratio grouping
- metric: aqi
  role: index              # a vendor index, not a measurement — never averaged, never a cell
  comparable: false
- metric: battery_pct
  role: device_health
  comparable: false
```

Four roles is all the trust layer needs. `ambient` channels can be compared between sensors at the same place;
`enclosure` channels (a BME680 reading the inside of its own box) can not, and confusing the two is how a radiation
shield's temperature becomes the neighbourhood's; `device_health` feeds liveness and never an average; `index` is a
vendor number that must never be pooled — which is exactly the `Bosch BME68X - AQI` mislabel from §1, caught by a
declaration instead of by someone remembering.

Collocation then has a generic definition with no source names in it: **two sensors are collocated for a metric when
both declare it `ambient` and `comparable`, and they are within `TRUST_COLLOCATION_M` (default 50 m) of each other.**
That covers the two clusters we have today, the Meshtastic pods when they arrive, a water probe, an AirGradient in a
classroom, and anything else that conforms to the adapter contract. No pack has to know about any other pack.

`reference` grouping is what lets `peer_ratio` say something useful rather than average away the very bias it is
measuring: compare within an instrument family first, then between families, and report the between-family ratio as
its own number. That is how the 1.508 becomes a fact about two instruments instead of noise in a mean.

Everything else a pack might want to declare, it should declare later, when a second consumer exists.

---

## 5. Satellite and open data: what they can honestly join

The `earth` pack holds nine years of AlphaEarth embeddings for `bayu-2` and computes year-over-year change. The air
record is days to weeks. Being blunt about the arithmetic: **nine annual land-change values against one week of air
supports no statistical claim whatsoever**, and no amount of framing changes that. The Kuta Selatan exhibit is right
to pair them in prose and refuse a correlation number.

Three joins that *are* defensible with what we hold:

1. **Siting, not correlation.** AlphaEarth change × `place` pack coverage × existing sensor positions answers "where
   should the next node go" — highest land change with no sensor within *n* km. That is a real use of a satellite
   layer, it is what an annual retrospective dataset is *for*, and it turns 19898's dead 7 km outpost into a decision
   rather than a gap.
2. **Explaining kit differences.** The `place` pack knows what is around the node from OpenStreetMap. It will not
   resolve the 19849/19880 question, because those two are metres apart and OSM has no opinion at that scale, but it
   will explain 19236/19874 against 19898.
3. **CAMS as a bias reference, per hour.** `insight`'s `agreement` rule already computes model bias. What it should
   compute is bias *by hour of day*, because a model that is flat all day against a street that peaks at 18:00 has an
   error that is a function of time, not a constant. One number hides that; twenty-four show it.

The open-data side (`balisatudata.baliprov.go.id` via CKAN) currently feeds portal freshness into `Governance|City`.
Nothing about air. Whether Bali Satu Data holds anything joinable at kecamatan scale is unexamined and worth an hour
before assuming it does.

---

## 6. What I would do first, in order

1. **Reconcile the API against the database.** Everything in §2 was measured upstream. Run the same seven-day window
   against `readings_1h` on `bayu-2` and confirm the coverage figures, the ratios and the noise anti-phase. If the DB
   disagrees with the API, that discrepancy is the first bug and everything else waits.
2. **Fix the timestamp.** Per-channel `ts` where the source gives one; where it does not, define silence by value
   change, not by timestamp. This is a change in `app/sources.py` and it precedes the trust pack, because L0 is
   worthless on top of a lying clock.
3. **The `trust` pack.** Four features, three rules, one synthetic sensor. No new tables.
4. **Move the 19849 unit two metres, for one day.** The cheapest experiment in this document, and it decides whether
   1.508 is a calibration factor or a siting artefact. Nothing downstream should assume either until it is run.
5. **Map `Noise Level` and `Light` into rules.** Already collected on 19236, already stored, currently read by
   nothing. Then correct the `rhythm` message.
6. **`channels.yml` and the collocation definition.** After the trust pack works against hardcoded sensor ids, lift
   it to the declaration. Building the registry first is how it becomes a framework nobody fills.
7. **`fleet_reference`, then repoint the `Environmental|Community` cell at it.** Only after L0 can flag what to leave
   out.

## 7. Open questions for Tomas

- **The 19849 gap.** Is that unit somewhere different in the room, or do we treat 1.5× as an instrument factor? The
  field test in step 4 answers it, and I would not design around either answer first.
- **Ulu Garden.** Kit 19898 is at 3% coverage and 7 km away, which makes it both the only geographic spread we have
  and the least trustworthy row in the fleet. Repair, relocate, or exclude?
- **Does data integrity belong in the Index?** A trust score is a fact about our instruments, not about the place.
  My instinct is that it stays on the node's own health surface and never becomes a cell, because a cell that measures
  our own competence invites us to optimise it. Worth a decision before the pack exists.
- **`aqi`.** The BME680's internal index is stored under a metric name that implies an air quality index. Rename it
  (`bme_iaq`) and break whatever reads it, or declare it `role: index` and leave the name? Renaming is honest and
  costs a migration note.
- **The burn season.** Every threshold and every correlation here comes from a 6–10 µg/m³ week. Kuta Selatan in burn
  season is a different regime, and the humidity question in §2.3 probably changes answer there. Do we hold the
  calibration work until we have those weeks, or calibrate now and revisit?

---

**What this document does not know.** It measured one week, at one site, on one account, through a cloud API rather
than the node's own store. Every number is a 7-day hourly rollup, so anything faster than an hour is invisible to it,
including the spike behaviour the air-quality rules fire on. The three-kit indoor cluster and the two-kit outdoor pair
are the only collocation evidence, both at low PM, both in one season. Nothing here has been run against a burn week,
a rain event, or a second site. And no line of it has been implemented.
