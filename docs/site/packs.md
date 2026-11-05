# Packs
<!-- checked: v0.91.0 -->

A pack is how a place teaches its node what to watch and what to say about it. The core names no metric: what
`pm25` means, which line matters in this house, and the sentence a person should read at 9 pm are all written in a
pack. A data pack is SQL and words. A code pack also fetches, adding a source the core does not read.

There are two tiers:

| | core | wild |
|---|---|---|
| lives in | `packs/` in the node's repository, twenty-five of them | its author's own repository, or a folder in [fabcity/planetai-wild-packs](https://github.com/fabcity/planetai-wild-packs) |
| reaches a node | with every release | Install in Set up › Packs, or `planetai packs add` |
| checked by | the node's `make lint` and tests, on every commit | the wild-packs repository's CI, against the node's `main`, every week |
| kept by | the node's maintainers | its author |

What the core packs do is on [Packs that ship](packs-reference.md). This page is the contract as `app/packs.py`
reads it, how to add a wild pack, and one small data pack built step by step.

```
packs/<id>/
  pack.yaml     id, name, description, version, requires, domain, sources:, pip:, env:, secrets:, switch:, share:, footprint:, readouts:, sections:, ahead:
  rules.yml     alerts: SQL that returns rows, one message per row; or a contribution to the report
  cells.yml     Index cells: SQL that returns one `value`
  issue.yml     the dashboard issue this pack ships, read while the pack is on (see Issues)
  channels.yml  what the pack's own metrics ARE: ambient, enclosure, device_health, derived, index, private
  adapter.py    a new source; its presence makes this a code pack
  hooks.py      on_readings and on_alert, what the pack does with what the node stores and sends; MQTT_TOPICS and on_mqtt, what it reads off the broker; also code
  routes.py     the pack's own HTTP routes, mounted at start for a core pack and 404 while it is off; also code
  *.py          scripts, run with `planetai run <pack> <script>`
  README.md     where the thresholds came from, which place they were written for, what the pack does not know
```

## Add a wild pack

### From the page

1. **Open Set up › Packs and unlock the screen** with the admin token. Every pack this node could run is there:
   the core packs and the wild packs on its disk, each with its switch, and under *On the wild list, not here yet*
   every listed pack this node does not have. A pack that is on but does not run says why on its line: a code pack
   waiting for Allow code packs, or one written for a newer node. A pack that is new on the list is marked *new*,
   and the household was told on its channels, once, the way a new release is told.
2. **Press Install.** Nothing is fetched yet. The node reads the pack's `pack.yaml` at the commit it would install,
   and shows who wrote it, whether anyone who keeps the list has reviewed it, the repository and the commit (with a
   link to read the code there), what it reads, whether it runs code on this machine, the Python libraries it adds
   and the settings it will ask for. A pack that would not load on this node cannot be installed.
3. **Press Install again.** The card says *Asked. The node picks it up within a minute.*, then what the node is
   doing: fetching it, building its libraries into the image when it has any (a few minutes), restarting. When it
   says *Installed*, the pack is in the list above, switched on, with its settings in its card. A code pack runs
   once Allow code packs is on.

Only the admin token can install, at every share level, and an agent cannot. The page never fetches anything
itself: it writes the request into `out/requests/`, and a crontab line that `planetai packs cron` adds (the
installer and every update add it) runs `planetai packs pending` on the node, which reads the wild list again and
installs only that pack at the commit the page showed. If the list moved since, it refuses and says so. If the card
says the request was not picked up, run `planetai packs pending` on the node, then `planetai packs cron`. A failed
install leaves nothing behind and the card quotes why; the whole log is `out/requests/pack-add.log`.

The page installs only packs on the wild list. To update a wild pack, or to add one that is not listed, use the
terminal. To remove one: in the node's folder, `rm -rf packs/<id>`, then `planetai restart`. Its card says the same.

### From the terminal

1. **Run `planetai packs add <id>`** with an id from the wild list, such as `posidonia`,
   or `planetai packs add <owner>/<repo>[/<folder>][@<ref>]` for any pack on GitHub. The node fetches the
   commit, pins it, and prints `● <id>: added, a data pack, from <source> at <commit>`. It warns when the pack is
   not on the list, or is listed and not yet reviewed, and when it is a code pack. Then it adds any settings the
   pack declares to `.env` and its Python libraries to the image, as `planetai packs install` does. If the
   packs this node loads were chosen in Set up › Packs, the new one joins that list; if it cannot write the list,
   it says so and prints the command that does.
2. **Run `planetai restart`, then `planetai packs`.** The pack is under `wild:` with where it came from, the
   commit and the day it was added, and which of its scripts an agent may run. Run `planetai packs add` again to
   update it. To remove it, delete `packs/<id>` and restart.

A wild pack never replaces a core pack or a folder you put there by hand.

## How packs load

Every folder under `packs/` with a `pack.yaml` is a pack, in sorted order. `PACKS_ENABLED` filters that list:
blank means every pack, otherwise a comma list of ids. The loader reads the folders on every pass, and `packs/` is
mounted into the app container, so a folder you add is seen within a minute without a restart. A folder that
`planetai packs add` put there carries a `.wild` file beside its `pack.yaml`; any other folder counts as core.

A pack is a code pack if its folder has any `.py` file. The loader sets `kind` from that and ignores the
`kind:` line in `pack.yaml`. An adapter or hooks runs with the node's privileges and network access, so it runs only
with `PACKS_ALLOW_CODE=1`: read it first. Without that setting the node logs `pack <id> ships code; set
PACKS_ALLOW_CODE=1 to run it (read <path> first)` and loads the pack's rules and cells anyway.

Because blank `PACKS_ENABLED` means every pack, a pack that must stay off by default has its own setting. `make`
waits for `MAKE_ENABLED=1`, because it reads a directory that is not openly licensed, and `fire` for
`FIRE_ENABLED=1`, for the bandwidth; both also need `PACKS_ALLOW_CODE=1`. `bali-air-dispatch` names `BAD_ENABLED` as
its `switch:`, and a core pack with a switch runs its adapter and hooks when the switch is `1`, without
`PACKS_ALLOW_CODE`; `air-quality`, `home-assistant`, `smartcitizen`, `airgradient` and `purpleair` have one too.

A `pack.yaml`, `rules.yml`, `cells.yml` or adapter that does not parse is logged and skipped, and the rest of the
node carries on. Every installed pack's `env:` keys, enabled or not, appear in Set up → Packs with their help text
and default. Rule ids are namespaced `<pack>/<id>`; the core's rules in `config/rules.yml` keep the ids written there.

## Your first data pack

Five steps, each with something to check. The pack watches temperature, because most kits report it. If your
sensors do not, pick a metric they do report and change `temp` in both files.

**1. See what your node measures.** Run `planetai sensors`. The rows marked `yours` are the ones a rule written
with `local` will read. A pack teaches the node about readings it already holds; it adds no sensor.

**2. Make the folder.** In the node's directory (`~/planetai` on an installed node), create
`packs/my-room/pack.yaml`:

```yaml
id: my-room
name: My room
description: How warm the rooms this node measures have been, as one alert a day and one Index cell.
version: 0.1.0
requires: { node: ">=0.72.0" }
domain: heat
```

Within a minute `planetai packs` lists it under `loaded now:`, in `core:`, as `my-room          data  How warm the
rooms…`. If it does not appear and `PACKS_ENABLED` is not blank, add `my-room` to that list. `domain: heat` puts
the pack's alerts under the heat issue on the dashboard.

**3. Teach it one thing to say.** Create `packs/my-room/rules.yml`. The line is set low on purpose, so it fires now
and you see the whole path; step 5 moves it.

```yaml
- id: room_warm
  level: info
  cooldown_minutes: 1440
  sql: |
    SELECT sensor_id, name, mean_1h FROM stats
    WHERE local AND metric = 'temp' AND mean_1h > 20
  message:
    en: "🌡️ {name} has averaged {mean_1h:.1f} °C over the last hour.\n\n👉 Open a window on the shaded side, or switch on a fan."
    id: "🌡️ Suhu rata-rata {name} {mean_1h:.1f} °C selama satu jam terakhir.\n\n👉 Buka jendela di sisi yang teduh, atau nyalakan kipas angin."
    es: "🌡️ {name} ha promediado {mean_1h:.1f} °C durante la última hora.\n\n👉 Abre una ventana del lado de la sombra, o enciende un ventilador."
```

Rules run every 60 seconds. Run `planetai status`: under `alerts` it prints the time and the start of your
message, with your sensor's name and its last hour filled in. That row is in the `alerts` table under the id
`my-room/room_warm`, and it will not repeat for that sensor for 1440 minutes. At the default `ALERT_LEVEL=act` an
`info` alert is recorded, shown on the dashboard and carried by the next report, and interrupts nobody (see
[Alerts](alerts.md)). If nothing appears, `planetai logs | grep my-room` shows `rule my-room/room_warm failed: …`
with Postgres's reason.

**4. Say which Index cell it becomes.** Create `packs/my-room/cells.yml`:

```yaml
- cell: "Environmental|Community"
  unit: "°C (24h mean, sensors in this node's custody)"
  state: live
  min_buckets: 12
  notes: "my-room: every temperature channel in custody, hourly means, last 24 h"
  sql: |
    SELECT avg(mean) AS value FROM readings_1h r JOIN sensors s USING (sensor_id)
    WHERE s.custody AND r.metric = 'temp' AND r.bucket > now() - interval '24 hours'
```

Run `planetai cells`. A new `Environmental|Community` row carries your value, its state and your unit.
`planetai cells --json` shows the full row, with `source: "planetai-node ·
pack:my-room"` and a note ending in `<have>/12 hourly buckets`. The state reads `partial` until the node holds 12
hourly buckets from sensors in its custody and enough of those sensors report (see [Cells](#cells)). A row like
this, a mean with its provenance, is the only form in which a place's measurements reach the Fab City Index (see
[Federation](federation.md)).

**5. Move the line to your place.** Change `20` in the SQL to the temperature this room should not pass, and say in
a `README.md` where that number came from. To make it an alert that asks for something, set `level: act`, keep
`cooldown_minutes` at or under 2880, add `watch: {metric: temp, over: <the same number>}` so the node can time how
long an action took to work, and add `{line}` to the message so it names the line. The cooldown still counts from
the `info` alert of step 3, so the first `act` alert comes once those 1440 minutes have passed with the room still
over the line. Then a 🔴 message reaches Telegram if it is connected, the heat issue's state is `act`, and the
lead's last line counts the alert (`1 alert open · in Decide` when it is the only one). What a person records
against it counts in [ρ](rho.md).

On a checkout of the repository, `python3 tools/check_rules.py` (it needs `sqlglot`) parses every pack against
`init.sql` and prints `55 rules and cells check out against init.sql`, two more with your folder added. A
`{placeholder}` the SQL does not return is refused here and named; on a running node the same mistake sends the
raw template, braces and all.

## Fields in pack.yaml

| field | used for |
|---|---|
| `id` | the pack's name; defaults to the folder |
| `name` | what a person calls it; the Packs card in Set up shows it, and falls back to `id` |
| `description` | shown by `planetai packs` and `GET /packs` |
| `kind: data` | `data` or `code`; the loader overwrites it: `code` when the pack ships any `.py` file (an adapter, hooks or a script), `data` when it ships none |
| `version: 0.1.0` | the pack's own version, returned in `GET /packs`; nothing compares it |
| `requires: {node: ">=0.76"}` | the node versions the pack loads on. A node outside the range does not load it, says so once in its log, and lists it under "not loaded" in `planetai packs`. Declare at least `>=0.76` for `readouts` or `sections`, which an older node ignores without a word |
| `domain` | which dashboard issue the pack feeds (`air`, `heat`, `land`, `coast`, …). A cross-domain pack's rules are claimed one by one in an `issue.yml`. A pack that reaches no issue, is not one of the domains outside them (`weather`, `place`, `governance`, `repair`) and ships an alert no issue claims fails `tests/test_issues.py`. See [Issues](issues.md) |
| `sources: [environmental/community/bali-air-dispatch]` | the registry ids of the data sources it reads. `make lint` runs `tools/check_registry.py`, which fails and names any id that is not an entry in the registry the node carries. See [The source registry](sources.md) |
| `pip: [earthengine-api]` | libraries `planetai packs install` builds into the image, once, as the union of the lists of the packs this node loads (every folder, when the node is down) |
| `footprint:` | where the pack's word reaches, drawn on the page as the cells that cover it: `key`, `name`, `what`, the `setting` that holds the radius with its `default` and `unit` (`km` or `m`), `shape` (`circle` or `square`), `base_res`, and `native_m` when the source has a grain of its own (earth's 10 m). Read while the pack is on; coast, earth and place declare one |
| `share: {open: [/path]}` | the paths this pack's `routes.py` serves that join the `open` share list, or with `"off"` (quoted, since YAML reads a bare `off` as false) every share level. A wild pack's are ignored. `forecast`, `nearby`, `earth` and `earth-engine` declare `open`, `things` declares `"off"` |
| `env: ["# comment", "KEY=default"]` | settings `planetai packs install` appends to `.env` under a dated marker when the key is absent; a comment line travels with the key under it. No space after `=` |
| `secrets: [CAMERA_WYZE_BRIDGE_TOKEN]` | which of its `env` keys are secrets. Set up and the agent's `settings_get` mask them once saved, like the node's own tokens; a key not listed here is shown to anyone holding the admin token |
| `switch: BAD_ENABLED` | the pack's own on-switch, usually one of its `env` keys. A core pack that names one runs its `adapter.py` and `hooks.py` when the switch is `1`, without `PACKS_ALLOW_CODE`; a wild pack still needs the flag. It may be a list of keys, on when any is set and not 0 (`smartcitizen`: `[SC_USER, SC_DEVICES, MQTT_HOST]`). Set up draws any pack's `…_ENABLED` key as a switch |
| `stations: {source, prefix, radius, box, url, attribution}` | a network of other people's stations the pack reads, for "Air stations nearby", `GET /nearby` and the ring on the map. `box` (south, north, west, east) is where the network has stations; `radius` names the key that sets how far the ring reaches |
| `agent_scripts: [verify]` | which of a wild pack's scripts a connected agent may run through `run_pack_script`. Leave it out and none do; a core pack's are all open, and `planetai run` runs every script either way. No agent can run `adapter.py` as a script |
| `readouts: {air: [ … ]}` | numbers the pack adds to an issue, in the shape an issue file uses; shown in Figures, and in the sentence of a context issue. It adds and never replaces. See [PACKS.md](https://github.com/fabcity/planetai-node/blob/main/docs/PACKS.md#readouts-on-an-issue) |
| `sections: [ … ]` | a band the pack declares on the dashboard as data, drawn with the page's own readout cards. See [A dashboard section](#a-dashboard-section) |
| `ahead: {id, title, sensor, days}` | one line the pack adds to [Next days](next-days.md), the three-day view on Now: the `sensor` whose meta holds a text for tomorrow and for the day after, and the two meta keys. Served in `GET /forecast` as `lines`. See [A line in Next days](https://github.com/fabcity/planetai-node/blob/main/docs/PACKS.md#a-line-in-next-days) |
| `needs: [api.bmkg.go.id]` | hosts the pack reaches, for people to read |
| `author`, `attribution` | who wrote it and answers for it; the licence line a source asks to be credited with |
| `metrics: [pm25, pm10]`, `scales: [community, city]` | what it measures and at which scales, for a reader choosing a pack. No code reads either: the channels a pack really produces are in `channels.yml`, and the cells it fills in `cells.yml` |
| `thresholds: US EPA / WHO 2021` | one line on where its numbers come from; the README says the rest |

## Rules

YAML only. A rule's SQL runs every 60 seconds as the read-only role `planetai_ro`: every table but `settings`, and
no writes, so a rule cannot read a token into an alert or change a row. Postgres does the maths, `corr()`
included. The first rule in `packs/air-quality/rules.yml`, with its message shortened:

```yaml
- id: indoor_pm25_high
  level: act
  cooldown_minutes: 120
  watch: {metric: pm25, over: 35.5}
  sql: |
    SELECT sensor_id, name, mean_15m FROM stats
    WHERE local AND indoor AND metric = 'pm25' AND mean_15m > 35.5
  message:
    en: "😷 The air inside at {name} is unhealthy right now … {line} µg/m³.\n\n…\n\nRun the purifier if you have one. …"
    id: "😷 Udara di dalam {name} sedang tidak sehat … {line} µg/m³.\n\n…\n\nNyalakan pembersih udara kalau ada. …"
    es: "😷 El aire dentro de {name} no es saludable ahora mismo … {line} µg/m³.\n\n…\n\nEnciende el purificador si tienes uno. …"
```

| field | required | meaning |
|---|---|---|
| `id` | yes | becomes `<pack>/<id>` |
| `sql` | yes | one `SELECT`; every returned row is a candidate alert. A `sensor_id` column keys the cooldown; without one the row is the node's |
| `level` | no (`info`) | `info`, `warn` or `act`; see [Alerts](alerts.md#levels) |
| `cooldown_minutes` | no (60) | per rule and sensor, checked against `alerts`. An `act` rule may not exceed 2880, the window after which the node counts a silent rule as cleared; `tests/test_share.py` fails a slower one |
| `long_cooldown_ok: true` | when cooldown > 20160 | tells the lint a cooldown over a fortnight is deliberate |
| `watch: {metric, over}` | no | the indicator and the line the rule is about, so `GET /effect` can time how long after an action the reading came back under it, and `{line}` in the message prints it. The lint fails if the metric or the number is missing from the SQL. Leave it out where the rule fires on a relation between two readings |
| `name` | no | what the household calls the alert in a learning ("unhealthy air inside"). Without one, the alert is named by its issue's `alert:`, then by its id |
| `line: {value, label}` | no | the line the report names when it says whether the reading came back under it after the alert; `label` is whose line it is (`line_epa`, `line_who`), a key of the report's own words. The test fails if the number is not in the SQL |
| `message` | unless `contributes` | a string or `{en, id, es}`, filled with the row by `str.format`; a `None` renders as a dash |
| `contributes: report` | instead of `message` | never sent; the first row lands in the report bundle under the rule's id |
| `kind`, `issue` | no | makes the rule the event engine's. `kind` is `ahead`, `unusual`, `spike`, `sustained` or `danger`; `issue` (default the issue the pack ships in its `issue.yml`, else the pack's id) is the story its rows fold into. Every row must carry `value`, `line` and, optionally, `over` (false for a row inside the margin, which keeps an open event open and never opens one). Under `ALERT_ENGINE=rules` the rule is skipped; under `shadow` and `events` it writes no `alerts` row. See [Alerts](alerts.md#the-event-engine) |

The node picks `message[ALERT_LOCALE]` and falls back to `en`. Every shipped rule carries all three languages, and
every `{placeholder}` in every language must be a column the top-level `SELECT` returns, or `{line}` with a
`watch:`, or `{act}`. The node fills `{act}` with the alert's own number as the household answers it, `/act 812`
where the Telegram bot runs and `planetai act 812` where it does not, so a message can say which number to answer.

A rule can also ask with buttons. Return a `buttons` column and the node stores them with the alert. With
`TELEGRAM_BUTTONS=1` they go to Telegram as a keyboard, and Now lists them under What to do. How to write them is
under [Buttons](https://github.com/fabcity/planetai-node/blob/main/docs/PACKS.md#buttons).

End a message with a paragraph that starts with 👉 and says what a person does; the classic dashboard's Decide
card shows it as "what this node suggests" (see [Alerts](alerts.md#what-an-alert-says)). A rule that treats indoor
sensors as ambient will not be merged, which is what `NOT s.indoor` is for.

`make lint` runs `tools/check_rules.py` (with sqlglot) over every rule and cell. Besides the limits in the table, it
refuses unknown tables and columns, a cell without a `value`, and a rule with both a message and a contribution or
with neither, which could fire and reach nobody.

What a rule may read:

| table or view | what it holds |
|---|---|
| `stats` | `sensor_id, metric, indoor, local, kind, scale, lat, lon, name, last, last_ts, silent_minutes, mean_15m, mean_1h, mean_24h`: the last 24 hours, sensors only |
| `readings_1h` | hourly `mean, min, max, n` over all history; a filter on `bucket` reads only the hours it asks for |
| `recent_15m` | quarter-hour means of the last 24 hours, with `apparent` |
| `usual_by_hour` | each room's own median, p75 and p90 for each local hour, from the fourteen complete days before today |
| `observations` | the latest value per slow source |
| `readings`, `sensors`, `channel_roles` | the raw tables |

The node's own position and time zone are Postgres settings: `current_setting('planetai.lat')`,
`current_setting('planetai.lon')`, `current_setting('TimeZone')`. `NODE_TZ` is the session time zone, so
`date_trunc('day', ts)` means the household's day.

A contributor has no level, no cooldown and no message:

```yaml
- id: digest
  contributes: report
  sql: SELECT round(avg(mean_1h)) AS inside FROM stats WHERE local AND indoor AND metric='pm25'
```

## Cells

```yaml
- cell: "Environmental|Community"
  unit: "µg/m³ PM2.5 (24h mean, sensors in this node's custody)"
  state: live                # live | partial | mock
  min_buckets: 12
  notes: "your own outdoor and indoor kits, hourly means, last 24 h"
  sql: SELECT avg(mean) AS value FROM readings_1h r JOIN sensors s USING (sensor_id)
       WHERE s.custody AND r.metric='pm25' AND r.bucket > now() - interval '24 hours'
```

`state` is provenance. `live` means measured here; `partial` means derived, from a model or a portal, whatever its
quality. Never claim `live` for a model. The core demotes `live` to `partial` when the in-custody hourly buckets in
24 hours are fewer than `min_buckets`, or when too few in-custody sensors report (two where the node has children
or is above community scale, one otherwise), and appends `have/need hourly buckets` to the note. A `NULL` value
leaves the cell out, so absent is never zero. The cell's source is recorded as `planetai-node · pack:<id>`, and the
core adds one cell of its own, `Governance|<Scale>` = [ρ](rho.md). Each row also carries `registered`, `reviewed`,
`candidate`, `capable` and `adapter` from [the source registry](sources.md), where `registered` means `reviewed`.

## Channel roles

A pack that adds a metric says what it is, keyed on `(source, metric)`:

```yaml
- { source: forecast-om, metric: fc_wind_speed, role: derived, comparable: false, unit: "km/h" }
```

Roles are `ambient`, `enclosure`, `device_health`, `derived`, `index` and `private`, defined on the
[sensors](sensors.md) page. The core's `config/channels.yml` is read first; a pack may not redeclare a pair the core
already claimed, and the duplicate is logged and dropped. A pack that adds no metric may ship `channels.yml` as `[]`
to say so.

## Code packs: adapters

`adapter.py` has `fetch(hc) -> (sensors, readings)`, the same contract as `app/sources.py`, and runs only as
described under [How packs load](#how-packs-load). Dependencies and settings go in `pack.yaml`. `planetai packs`
lists what is loaded and says when a dependency or a setting is missing, and `planetai packs install` adds the
missing `env:` keys to `.env` and rebuilds the image once with every pack's `pip:` list. A pack that needs a key or
a service must log once and return nothing when it is missing. `packs/earth-engine` is the worked example: a
dependency, a credential, several remote datasets, and it idles until configured. `packs/make` is a code pack that
stores places rather than numbers.

## Scripts

Things you ask for rather than things that run on a schedule:

```bash
planetai run                          # lists every script with its first line
planetai run earth change --all       # the land change for every consecutive year pair this node has cached
planetai run nearby stations          # every station in the ring, with the reason for each exclusion
planetai run place gaps               # a mapping brief: what is undrawn within the kilometre
planetai run season window            # every paired station, its week, its baseline, the step
```

They run inside the app container, where the dependencies are, with `PACK_OUT=/app/out`. `out/` is the one writable
path, and what they write there is yours to send anywhere. Every `*.py` in a pack except `adapter.py` and `hooks.py` is listed, so
a helper module shows up too (`place/satellite.py` does).

## A dashboard section

Any pack, wild or core, can declare a section in its `pack.yaml`, as data. The node reads each readout's latest
row and serves the section in `GET /issues` under `sections` (a core pack's section only once a row of it exists).
The page draws it as a band in its stage on Now, with the pack's name beside the title, using its own readout cards
and no code from the pack. On the doors it sits next to Now's own part of that stage: `observe` under the issue rows,
`decide` and `act` under What to do, `measure` under Did it work. The phone page draws the same band in its one
column. The pack's `note:`, when it has one, is folded under "How this is read", and the source is said once, under
the title:

```yaml
sections:
  - id: sg-air                          # unique on the page: lowercase letters, digits and hyphens
    stage: observe                      # observe · decide · act · measure
    title: { en: Singapore air, from NEA, id: Udara Singapura, dari NEA, es: Aire de Singapur, de NEA }
    order: 40                           # optional, default 50
    wall: true                          # optional: each reading is also a column on the wall
    readouts:
      - { metric: psi, sensor_id: nea-psi, unit: PSI, dp: 0, label: { en: NEA PSI, id: PSI NEA, es: PSI de NEA } }
```

A declared section draws readout cards only. A stack, a series or a row needs script, and script on this page is
for core packs only: it reads the same browser storage the admin token is kept in, so a pack's own script would hold
admin rights on every node that installed it. A core section registers one object with the page contract:

```js
window.PAI.register({
  id: 'meshtastic',            // required, unique; the band's DOM id
  pack: 'meshtastic',          // required
  stage: 'observe',            // required: observe · decide · act · measure
  title: 'The mesh in this house',  // required
  render(ctx) { … },           // render or lead is required; captions belong here, explanations do not
  order: 41,                   // within the stage, lower first (default 50)
  level: 'advanced',           // default; 'simple' keeps it in simple mode on Historical and Network (simple on Now draws no sections)
  needs: ['H3.radio.mesh'],    // dotted paths off window; absent → one honest line, never a blank
  learn: ['states'],           // learn marks this section carries
  controls(ctx) { … },         // optional control strip
  wall(ctx) { … },             // what this section contributes to the wall
  notes(ctx) { … },            // [{ id, label, text }]: the explanations, gathered at the foot of the page
});
```

A section may not invent a fifth card kind (readout · stack · series · row), colour a state by hue, print a numeral
without `data-num`, or put its explanation in its body. A scripted section lives inline in
`app/static/dashboard.js`, because the node serves its static files from a fixed allowlist, so it comes with the
pack's promotion to core. The page itself is on [Dashboard](dashboard.md).

## Sharing one

Do not fork the node to write a pack for your city. Make a repository that is the pack folder, develop it in
`packs/<id>` on your own node, and run `python3 tools/check_rules.py` from the node's folder. Say in the README where
the thresholds come from and which place you wrote for: thresholds for Kuta Selatan are not thresholds for
Barcelona. A source the pack reads has to be an entry in the registry first, so `sources:` can name it.

To let other nodes find it, add one entry to `packs.json` in
[fabcity/planetai-wild-packs](https://github.com/fabcity/planetai-wild-packs) by pull request. Its README lists the
fields, anyone may be listed, and an entry is marked `listed` until a maintainer has read it (for a code pack, its
adapter) and marks it `reviewed`. Any node then installs it with `planetai packs add <owner>/<repo>`. The same
repository can host the folder for you if you would rather not keep a repository of your own.

A pull request to the node's repository is for promotion to core. A reviewer asks that the pack is useful beyond
the place it was written for, or is the reference for a pilot city; that its data is openly licensed and its README
says under which licence; that it has offline tests registered in `tests/all`; and that a maintainer agrees to keep
it. The issue a new domain declares is explained on [Issues](issues.md).

## Packs nobody has written yet

Each of these would fill a gap the node has today. Take the one whose sensor you own and whose decision you face.

| pack | what it would watch | Index cell | what it needs |
|---|---|---|---|
| classroom | CO₂ over 1,200 ppm for 20 minutes: open the windows | `Social\|Community` | a CO₂ sensor the node reads (the `airgradient` pack reads an AirGradient monitor's, see [Packs that ship](packs-reference.md#airgradient)) |
| outage | grid up and down, as outage hours | `Economic\|Community` | a smart plug on the broker |
| water | turbidity, TDS and tank level: is the well safe, will the tank last to the rain | `Environmental\|Community` | a DIY probe on an ESP32, over MQTT |
| lab machines | hours run, jobs, material in and out | `Economic\|Community` | a fab lab's job log, from Fabman or a CSV |
| open-data portals | the Socrata and ArcGIS portals of cities such as Barcelona and Boston | `Governance\|Region` | nothing but the portal |
| noise | school-hours rules on sound levels | | a Smart Citizen kit, which already reports noise |

Smaller ones, an afternoon each: tides, pollen, procurement latency from public tender data (TED, ChileCompra,
LKPP), and a pack that is only messages translated into another language.

## Where this leads

A pack reads what the node already holds. When the thing your place needs measured is not held yet, the next page
is [the source registry](sources.md): what the network has filed as measurable at each pillar and scale, which of it
any code reads, and which is waiting for somebody to write the adapter.
