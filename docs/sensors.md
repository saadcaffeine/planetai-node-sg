# Sensors and sources

How readings enter a node, and the rules that keep the numbers right. Several rules come from Bali Air Dispatch's
methodology, and are credited where used.

## The adapter contract

One function in `app/sources.py` (or a pack's `adapter.py`):

```python
def my_source(hc: httpx.Client, ...) -> tuple[list[dict], list[tuple]]:
    sensors  = [{"sensor_id": "xx-123", "source": "my_source", "name": "...", "lat": .., "lon": ..,
                 "indoor": False, "local": True, "kind": "sensor", "scale": "community", "meta": {...}}]
    readings = [(ts_utc, "xx-123", "pm25", 12.3), ...]
    return sensors, readings
```

Readings dedupe on `(sensor_id, metric, ts)`, so polling twice is harmless. `local` means yours. `indoor` must be
correct; the rules depend on it. `kind` is `sensor`, `portal`, `model`, `survey`, `child`, `peer` or `facility`, and the
`place` pack also writes `map` rows; only `sensor` enters `stats`.

`local` is two facts at once: an adapter says whether a sensor is *yours*, and the node checks whether it is
*here*. A kit on your account 1.2 km away is yours and is not this node's measurement. `LOCAL_RADIUS_M` (500 m by
default) is the line. A sensor with no coordinates that arrives over your own gateway stays local.

Metrics: `pm25 pm25_raw pm10 pm1 temp humidity pressure bme_iaq iaq gas_resistance noise light eco2 tvoc`. Units: µg/m³, °C, %, kPa.

## What ships

**Smart Citizen** (`SC_USER=you`, or `SC_DEVICES=19880,...`). Public API, no key. With a username every kit on the
account is read as yours; indoor/outdoor from each kit's own `exposure`. `SC_EXCLUDE` drops kits at another site.
Metrics are mapped by measurement name, since sensor ids differ between kit generations. Not humidity-corrected: the
Seeed HM-3301 is not a Plantower and the EPA correction was not derived for it.

**AirGradient** (`AIRGRADIENT_HOSTS=airgradient_abc.local`). Read on the LAN, never through the cloud. Plantower inside:
EPA 2021 correction applied, raw kept as `pm25_raw`.

**PurpleAir** (`PURPLEAIR_HOSTS=192.168.1.50`). LAN, `/json`. Two Plantower channels averaged; corrected; raw kept.

> **Not polled in this version.** Both adapters are written and tested, but `sources.enabled()` does not register
> them, so a host you set is used only to keep your own kit out of the Bali Air Dispatch ring. A regression to be
> fixed, not a decision; until then the sensors a node reads on its own are a Smart Citizen kit, Meshtastic radios and,
> through the `xiaomi-air` wild pack, Xiaomi purifiers.

**Meshtastic** (`planetai meshtastic`). Telemetry from radios via the gateway's MQTT uplink. `MESH_INDOOR_NODES` marks the
indoor ones. DIY pods publish to `planetai/sensors/<id>/<metric>` on the same broker.

**DIY nodes, direct** (`planetai broker`). A Making Sense Bali DIY node (its v4 portal asks where to publish) sends the
platform's own topics and bytes to this node's Mosquitto: `device/sck/<token>/readings`, plus a retained `meta` message
with the name, the site, the mounting height and whether it is indoors. The parser also reads a Smart Citizen Kit's
`readings/raw` (`{t:...,55:28.3}`, what `mqtt -host <node> -port 1883` in the kit's shell would send), but the kit's
firmware cannot send a password and this node's broker refuses anonymous clients, so a kit stays on the cloud path
until a later version adds a listener scoped to `device/sck/#`. The node stores them with the device's own timestamp, which the cloud API never gives
(rule 2 below). Ids are `sck-` + 8 hex of the token's hash: the token is a credential and is never shown. Without a
`meta` message a device is outdoor and named by its id. Tokens listed in `SC_FORWARD` are passed on to
smartcitizen.me unchanged, through a queue that outlives an internet outage, so the device keeps its page there;
add that device's platform id to `SC_EXCLUDE` or it is read twice, once direct and once from the cloud.

**Bali Air Dispatch** (`BAD_ENABLED=1`, Bali). The ring: other people's stations within `BAD_RADIUS_KM`, as the
outdoor reference this node is read against. Never `local`, at any distance. Three rules keep this node's own kit out
of its own ring — the ids it already polls, anything within `BAD_MIN_SEPARATION_M` of the node, and `BAD_EXCLUDE` by
hand — and one more keeps a single device from arriving twice under two networks' ids. Stations the archive suspects
are indoors or malfunctioning are dropped; `BAD_INCLUDE_INDOOR=1` keeps the indoor ones.
`planetai run nearby stations` prints the whole list with a reason for every exclusion.

**Open-Meteo, CAMS, NASA POWER**. Free, key-free, anywhere. Weather now; PM2.5, PM10, O₃, NO₂, dust, UV from the
Copernicus model at 11 km; climate normals. `kind='model'`, never in an ambient average.

**CKAN portals** (`CKAN_PORTALS=slug=url`). A portal's maintenance state → `Governance|City`.

## The rules we inherit

1. **Indoor sensors measure a room.** Never in an ambient average.
2. **Silence is defined by value change, not by a timestamp.** `stats` looks back 24 h and exposes
   `silent_minutes`, and that number is true per kit and false per channel. Smart Citizen's per-reading
   `data.recorded_at` is null on every kit node #1 reads, so the adapter stamps every channel with one
   kit-level `last_reading_at` at poll time. A channel that has stopped producing new values still gets a fresh
   timestamp on every poll, and its frozen value is re-inserted under that new timestamp — forever. That pulls
   the 24-hour mean toward the frozen number and shrinks its variance, so a dying channel's own statistics make
   it look steadier, not worse. A timestamp check would never catch this. `packs/trust`'s `channel_dead` rule
   looks at the value instead.
3. **A daily mean can be one reading.** Check `n` before trusting an aggregate.
4. **Instants are UTC; days are local.** Daily buckets use `NODE_TZ`. Bali's 9 am burn peak vanishes on a UTC day.
5. **Corrected ≠ raw.** Store both. Never overwrite raw.
6. **Gaps are real.** No fill, no zero, no interpolation.
7. **These are not reference instruments.** Good for patterns and magnitudes; the node labels them as such.
8. **Sensors in the same place disagree.** Three kits at one address read the same air and do not agree: one of
   them (`sc-19849`) runs about 1.5× the other two, measured ratios 1.508 against `sc-19880` and 1.426 against
   `sc-19897`. Collocation — more than one sensor at the same spot — is the cheapest calibration a node can run,
   and most nodes have it by accident rather than by design. `packs/trust`'s `peer_disagreement` rule is what
   reads it.

## "Outside" resolves in one order

Your own outdoor sensors; else the three nearest public references; else the model. The same order in the rules, the
digest and the dashboard. Averaging every station within 15 km once put an Uluwatu reading of 3 next to the street's 15.

## The EPA 2021 humidity correction

Optical PM sensors over-read in humid air. Bali runs 45–70% RH. `epa_2021_correct(pm_raw, rh)` implements the US EPA 2021
Plantower correction; raw 28 at Bali humidity → about 15. Near-zero raw in dry air lifts to 1–2: a property of the
regression, no health meaning. Apply to PurpleAir, AirGradient, DIY PMS5003. Do not apply to Smart Citizen, IQAir,
AQICN, Airly.

## Siting

Three to six metres up. Away from a kitchen exhaust, a chimney, a parking spot. Outdoor air, sheltered from horizontal
rain. 2.4 GHz WiFi. Name it after the place. For our own enclosures, the outdoor-sensor-enclosure work is the printable
answer; Fab Lab Bali prints it.

## When the node speaks

**One report every `REPORT_EVERY` hours**, counted from `REPORT_ANCHOR`, in the node's own time zone. The defaults are
6 and 6, so 06:00, 12:00, 18:00 and 00:00. `REPORT_EVERY` takes 3, 4, 6, 8, 12 or 24 — each divides 24, so the rhythm
does not walk round the clock — and refuses anything else rather than leaving a household with a schedule nobody chose.
`planetai report every 12` and `planetai report at 7` change it without a restart.

The report has six parts and is under a hundred words: where the place stands, what changed, anything only the models
know, what happened after this window's alerts, the one thing to do before the next report, and the invitation to ask.
The node writes it itself, from SQL against its own tables, so a node with no model reachable anywhere still gets it.
`app/report.py` holds both halves: `bundle()`, every number the node has about the window, and `sheet()`, the report.

Two numbers in it are worth knowing about. **Notability** is the window's mean against the mean of the same local hours
on each of the previous seven days, in standard deviations of that baseline; it is null until three days exist, so a
node in its first three days claims nothing. It decides which two places get a sentence, which is how the report can say "the
kitchen ran higher than usual" without anyone reading a chart. **Trend** is the digest's ±3 rule read across to each
metric's own units: 3 µg/m³ for PM2.5, half a degree for a room's temperature, 5% of the window's range for a metric
with no line of its own.

**A report due inside quiet hours is written and stored and not sent.** It appears on the dashboard, saying so, and the
next report to go out covers every hour that was held and opens with "Overnight and this morning". A node that was off
for a week reports two days, not a hundred and sixty-eight hours.

**Between reports the node speaks only when something needs doing.** `ALERT_LEVEL` is `act` by default — something needs
doing — and can be `warn` (also when something changed) or `info` (everything). Below that line an alert is still
recorded, still on the dashboard, and in the next report. `QUIET_HOURS` holds everything but `act` between 22:00 and
06:00. An act alert says what to do in one sentence and asks for nothing back: no id to quote, no button to press.

All of these are local hours, read from `NODE_TZ`. A report scheduled for 6 arrives at six in the morning where the node
is, which is the bug this replaced: the old daily pulse fired on a UTC hour and said "good morning" at one in the
afternoon in Bali.

`GET /report/latest` is the last report. `GET /report/bundle?hours=` is what it was written from, behind the read-only
token. `POST /report/now` writes one immediately, behind the admin token, and is what `planetai report` calls.

## Thresholds

| PM2.5 µg/m³ | scale | used for |
|---|---|---|
| 15 | WHO 2021 24-hour | "clean" line everywhere; `inside_worse_ventilate` floor |
| 35 | WHO interim target 1 | `indoor_pm25_high`, `outside_worse_keep_shut`, "moderate" ceiling |
| 55.5 | US EPA Unhealthy | reserved |

Spikes: 2.5× today's mean, above 12 indoors or 15 outdoors. That says "something changed" before anything is unhealthy.
