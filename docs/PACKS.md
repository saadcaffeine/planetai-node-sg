# Packs

A pack is a folder in `packs/`. It carries rules, Index cells, or an adapter for a new source. The core knows nothing
about air, water or heat; the packs do. Eighteen ship in `packs/`.

```
packs/<id>/
  pack.yaml     id, name, description, kind (data | code), version, requires:, domain:, sources:, needs:, pip:, env:,
                secrets:, agent_scripts:, readouts:, sections:, (read by people only) author:, attribution:,
                metrics:, scales:, thresholds:
  rules.yml     alerts: SQL that returns rows, one message per row
  cells.yml     Index cells: SQL that returns one `value`
  adapter.py    a new source; code packs only
  channels.yml  what a pack's own metrics ARE — ambient, enclosure, index, etc.
  README.md     where the thresholds come from, what the pack assumes
```

## A pack does not have to live in this repository

The packs in this repository are **core**: they ship in the release and every gate runs on them. A pack kept
anywhere else is a **wild** pack ([decision](decisions/2026-10-01-packs.md)). The node loads every folder under
`packs/` that has a `pack.yaml` and does not care where the folder came from. `packs/` is a bind mount into the
container, so a wild pack is installed by putting it there.

Wild packs are listed in [fabcity/planetai-wild-packs](https://github.com/fabcity/planetai-wild-packs), which can
also host one for an author who would rather not keep a repository. Anyone may list a pack there by pull request;
each entry says whether a maintainer has read it, and every entry is checked against this repository's `main` once a
week.

From the node's folder:

```
planetai packs add <id>                                  # a pack on the wild list, at the commit it was listed at
planetai packs add <owner>/<repo>[/<folder>][@<ref>]      # any pack on GitHub; with no @<ref>, the default branch now
planetai restart
```

It always pins: a branch or tag is resolved to the commit it names, and that commit is written to `packs/<id>/.wild`
with where the pack came from. It refuses an id that is already a folder here and did not come from `packs add` (a
core pack, or one you put there by hand), an id that is not the folder shape, a pack with symbolic links, and, for a
pack from the list, an id the list and the pack disagree on. It runs `planetai packs install` afterwards. Running it
again on the same pack replaces it with the new commit. `planetai packs` lists core and wild apart and says where
each wild pack came from. To remove one, delete `packs/<id>` and restart. If a later release ships a core pack with
the same id (a wild pack promoted into the release), `planetai update` stops before it changes anything, names the
wild copy and where it came from, and asks you to delete it; run the update again and the core pack takes its place.

It fetches GitHub's archive of the commit with curl and tar, because a node installed the default way has no git.
On a node older than this command, do the same by hand. When the repository *is* the pack:

```
mkdir packs/<id>
curl -fsSL https://codeload.github.com/<owner>/<repo>/tar.gz/<commit> | tar xz -C packs/<id> --strip-components=1
planetai packs install      # its env: keys into .env, its pip: lines into the image (a rebuild)
```

When the pack is one folder, `<id>/`, at the top of a bigger repository, extract just that folder:

```
curl -fsSL https://codeload.github.com/<owner>/<repo>/tar.gz/<commit> | tar xz -C packs --strip-components=1 <repo>-<commit>/<id>
```

Use the full 40-character commit id. Both work with the tar on macOS and on Linux. On a node that has git,
`git clone` into `packs/<id>` works too, but then `planetai packs` counts it as core.

`planetai update` keeps it: the tarball is unpacked over the folder and the git path is a fast-forward pull, and
neither touches a folder it does not track. A code pack still runs only with `PACKS_ALLOW_CODE=1`, wherever it came
from.

So do not fork this repository to write a pack for your city. Make a repository that *is* the pack folder, develop it
in `packs/<id>` on your own node, and leave this repository as the released node it is. Run
`python3 tools/check_rules.py` from the node's folder and it checks your rules against the schema with the rest; an
offline test for an adapter imports it by path, the way `tests/test_earth.py` does, and can live in your repository.

A wild pack can add readouts to an issue (see [Readouts on an issue](#readouts-on-an-issue)) and declare a section
of the dashboard (see [A declared section](#a-declared-section)). Two things cannot travel this way, and come to this
repository as their own pull request: a section that needs script of its own, and any other change to an issue under
`app/issues/`. A preset for your city is one file in `presets/` and a pull request.

## Data packs

YAML only. Anyone can write one. Rules read `stats` (24-hour rolling, per sensor and metric), `readings_1h` (hourly
means, all history) and `observations` (portals and models). Postgres does the maths, including `corr()`. The SQL runs
as a read-only role (`planetai_ro`, in `init.sql`): every table but `settings`, and no writes, so a rule cannot read a
token into an alert text or change a row.

```yaml
- id: indoor_pm25_high
  level: act                 # info | warn | act
  cooldown_minutes: 120
  sql: SELECT sensor_id, name, mean_15m FROM stats WHERE local AND indoor AND metric='pm25' AND mean_15m > 35
  message:
    en: "Indoor PM2.5 at {name} is {mean_15m:.0f} µg/m³. Purifier on, windows shut."
    id: "PM2.5 dalam ruangan di {name} {mean_15m:.0f} µg/m³. Nyalakan pembersih udara, tutup jendela."
    es: "PM2.5 en interiores en {name}: {mean_15m:.0f} µg/m³. Purificador encendido, ventanas cerradas."
```

Every message carries `en`, `id` and `es` with the same placeholders; `make test` fails one that does not.
Every column the message uses must come from the SQL. `make lint` checks that, plus unknown columns, cells without a
`value`, and cooldowns over a fortnight (add `long_cooldown_ok: true` if that is deliberate).

A rule can compute something for the report instead of interrupting anyone:

```yaml
- id: digest
  contributes: report        # no level, no cooldown, no message: this is never sent
  sql: SELECT round(avg(mean_1h)) AS inside FROM stats WHERE local AND indoor AND metric='pm25'
```

Its first row lands in the report bundle under the rule's own id (`bundle.digest`), where the node's own report
reads it and a model, if one is reachable, may quote from it. A contributor has no message and is never sent;
`make lint` refuses a rule with both, and refuses a rule with neither, which could fire and reach nobody.

A cell:

```yaml
- cell: "Environmental|Community"
  unit: "PM2.5 µg/m³ 24h mean"
  state: live                # live | partial | mock. The core demotes live to partial below min_buckets.
  min_buckets: 12
  sql: SELECT avg(mean_24h) AS value FROM stats WHERE local AND indoor AND metric='pm25'
```

`state` is provenance, not confidence. `live` means measured here; `partial` means derived or a model; never claim `live`
for a model.

### Channel roles

A pack that adds a metric says what it IS in `channels.yml`, keyed on `(source, metric)`:

```yaml
- { source: my-sensor, metric: co2, role: ambient, comparable: true, unit: "ppm" }
```

Five roles: `ambient` (the air, water or land at a place — comparable between sensors there), `enclosure` (the
inside of the instrument's own box — a BME680 sealed inside a radio reports the box, not the street, so this is
never averaged as ambient), `device_health` (the instrument talking about itself, e.g. battery), `derived`
(computed by us from other readings), and `index` (a vendor's own composite number, never pooled with anyone
else's). `config/channels.yml` has the core declarations; `make lint` checks every metric against `app/sources.py`.
A role is keyed per source and metric, not per device: every sensor an adapter drives shares it, so a node whose
hardware differs from that adapter's usual shape (an external probe on a Meshtastic pod) cannot override it yet.

### Readouts on an issue

A pack can add numbers to an issue it has something to say about, in its own `pack.yaml`, in the shape an issue file
uses. A readout is one sensor's latest row, with a unit and a label in every locale:

```yaml
readouts:
  air:
    - { metric: psi, sensor_id: nea-psi, unit: PSI, dp: 0, label: { en: NEA PSI, id: PSI NEA, es: PSI de NEA } }
  coast:
    - { metric: beach_band, sensor_id: nea-beach-changi, unit: of 3, dp: 0,
        label: { en: Changi beach water band, id: pita air pantai Changi, es: banda del agua de Changi } }
```

They come after the issue's own readouts, in the order of the packs' ids, while the pack is enabled. Every issue
shows its readouts as rows in Figures; a context issue (`coast`, `land`) also reads them in its sentence. A pack adds
and never replaces: a readout for the same sensor and metric as one already shown is not shown twice, and one that
names no declared issue, or lacks a unit or a label, is left out with a line in the log. A readout whose sensor has
no row on the node shows nothing. A pack cannot change an issue's line, its distances, its hero or its sentences.
`tests/test_pack_readouts.py` holds this.

### Which node versions

`requires: { node: ">=0.40.0" }` says which nodes a pack was written for: one clause, or several joined by commas
(`">=0.40.0, <0.90.0"`), each one of `>=`, `>`, `<=`, `<` or `==` and a version. A node that does not match does not
load the pack at all, rules and adapter alike, says so once in its log, and lists it under "not loaded" in
`planetai packs` with the reason. `planetai packs add` says it at once. A node that cannot name its release (a
developer's checkout, `dev`) loads every pack; a `requires:` that is not a version range is refused. The rule is
`app/requires.py`, which the loader and the CLI both run, and `tests/test_requires.py` also checks that no core pack
asks for a node newer than the latest release.

## Code packs

`adapter.py` with `fetch(hc) -> (sensors, readings)`, the same contract as `app/sources.py`. Off unless
`PACKS_ALLOW_CODE=1`: a pack runs with the node's privileges, so read it first.

Dependencies and settings are declared in `pack.yaml`; `planetai packs` lists what is loaded and what is missing, and
`planetai packs install` installs the libraries into the image once and
adds the settings to `.env` under a dated marker:

```yaml
pip: [earthengine-api]
env:
  - "# earth-engine: project id, or blank to read it from the key file"
  - "EE_PROJECT="
```

No padding after `=`: a value pasted after spaces becomes `VAR= value`, which the shell runs as a command.

Every key a pack declares appears in its card under Set up → Packs. A key that is a secret (a token, a password, an
API key) is listed under `secrets:`, and Set up then treats it like the node's own tokens: masked once saved, and
never shown again, to the admin token or to the agent's settings tool. A key that is not listed is shown to anyone
holding the admin token.

```yaml
env:
  - "# camera: only if the bridge's API is protected"
  - "CAMERA_WYZE_BRIDGE_TOKEN="
secrets: [CAMERA_WYZE_BRIDGE_TOKEN]
```

A pack that needs a key or a service must log once and return nothing when it is missing. It must never take the node
down. `packs/earth-engine` is the worked example: a dependency, a credential, four remote datasets, and it idles until
configured.

## Scripts

A pack can ship scripts: things you ask for rather than things that run on a schedule.

```bash
planetai run earth-engine timelapse --n 4 --gap 5
```

They run inside the app container, where the dependencies are, and write to `out/`, the one writable path. `planetai run`
alone lists them.

A connected agent with the admin token can run them too, through the `run_pack_script` tool, and reads what they
print. A core pack's scripts are all open to it. A wild pack's are open only when its pack.yaml names them, because a
wild script may print what its pack keeps off the readings, and the node's own terminal is the one place that should
see it:

```yaml
agent_scripts: [verify]      # a wild pack: only these reach an agent; leave it out and none do
```

`planetai run` runs every script either way. A pack copied into `packs/` by hand, without `planetai packs add`, has no
`.wild` and counts as core here.

## A dashboard section

**What the page draws is `GET /issues`, and that document is `issues-v0`.** Every section reads off
globals bound from one fetch of it, so its top level is the contract a section is written against. It
carries `"schema": "issues-v0"`; `tools/check_wire.py` holds the top-level key list in
`tests/data/wire/issues-v0.json`, and a key cannot appear or vanish under a section without somebody
editing that file. If a node ever answers a version the page does not know, the page says one sentence
and draws what it recognises — it does not blank. A version bumps only on a breaking change, and the
bump is a `docs/decisions/` entry.

A core pack can put a scripted section on the dashboard (any pack can declare one as data: see
[A declared section](#a-declared-section)). It registers one object with the page contract and the
page renders it in the stage it belongs to — observe, decide, act, measure — in the order the loop
runs, and folds its explanations at the foot:

```js
window.PAI.register({
  id: 'meshtastic',        // required, unique; becomes the band's DOM id
  pack: 'meshtastic',      // required; your pack's id
  stage: 'observe',        // required; observe · decide · act · measure, nothing else
  title: 'The mesh in this house',   // required; the band's kicker, in the house voice
  render(ctx) { … },       // required; the body. Captions belong here, explanations do not
  order: 41,               // optional (default 50); position within the stage, lower first
  needs: ['H3.radio.mesh'],// optional (default none); globals this section reads off window
  controls(ctx) { … },     // optional: a control strip (a toggle, a selector)
  wall(ctx) { … },         // optional: what this section contributes to the wall at ctx.RES
  notes(ctx) { … },        // optional: the explanations, as [{ id, text }]
});
```

`id`, `pack`, `stage`, `title` and `render` are the ones the page actually checks for; leave one out,
or misspell a stage, and the section is dropped with a line under "Registration problems" rather
than drawn broken. `needs` is read against `window`: each string is a DOTTED PATH resolved from `window` one key at a
time, so `'H3.radio.mesh'` is `window.H3 && window.H3.radio && window.H3.radio.mesh`, and the test is
`!= null` — a path that resolves to `null` or `undefined` at any step counts as absent, and `0`,
`''` and `[]` do not. (A node whose geometry failed publishes `geometry: null`, so `'H3.nav'` is
absent there and the ground band says so.) When what a path names is not there, the band
prints one honest line — *"The `<pack>` pack has nothing here yet: `<what>` is not on this
node"* — never a blank and never a guess. When `render()` itself throws, the band prints *"`<pack>` ·
`<id>` did not render: `<message>`. A failure is not an answer, so the rest of the page is still
here"* and every other section still draws.

What a section may not do: invent a fifth card kind (readout · stack · series · row are the four,
and a drawing is a drawing inside a card); colour a state by hue; print a numeral without
`data-num`/`data-cmp`; leave a component with no `data-ref` in or out; put its explanation in its
body — that belongs in `notes()`, gathered at the bottom of the page where every note lives folded.
None of this is enforced by the contract itself; all of it is measured by `tests/visual/gate.sh`.

A section with script of its own lives inline in `app/static/dashboard.js`: the node serves a fixed list of static
files by name, and the twenty-four sections shipped there are the reference for the shape above. That is for core
packs only, and it stays that way: a script on this page reads the same browser storage the admin token is kept in, so
a pack's own script would hold admin rights on every node that installed it (docs/decisions/2026-10-01-packs.md,
point 5). Proposing a scripted section is sending the code with its `render()` and its `notes()`, and it is a reason to
promote the pack.

### A declared section

A wild pack declares its section as data in its `pack.yaml`, and the page draws it with its own readout card:

```yaml
sections:
  - id: sg-air                          # unique on the page: lowercase letters, digits and hyphens
    stage: observe                      # observe · decide · act · measure
    title: { en: Singapore air, from NEA, id: Udara Singapura, dari NEA, es: Aire de Singapur, de NEA }
    order: 40                           # optional, default 50: position within the stage
    wall: true                          # optional: each reading is also a column on the wall
    note: { en: NEA's regional figures., id: Angka regional NEA., es: Cifras regionales de NEA. }
    readouts:                           # the shape an issue's readouts use
      - { metric: psi, sensor_id: nea-psi, unit: PSI, dp: 0, label: { en: NEA PSI, id: PSI NEA, es: PSI de NEA } }
```

The node reads each readout's latest row, as it does an issue's, and serves the section in `/issues` as `sections`,
with the numbers already in it and each one's age. The page turns it into a band in its stage, on Now, with the
pack's name beside the title and `GET /issues` as its route. A reading the node has no row for is not drawn, and the
band says how many have not arrived. Its note, at the foot of the page, says which pack declared it and that the pack
ships no code for this page. A declared section draws readout cards only: a stack, a series or a row needs the
shell's own code. One that is not well formed, or whose id another pack already took, is left out with a line in the
log; one whose id the page already has is listed under "Registration problems". `tests/test_pack_sections.py` holds
this, on both sides.

## The hero

The lead of the page is a slot. Whichever issue the node's rule puts first, the page draws its
`hero` from `GET /issues` and nothing else there, so the page knows nothing about air, heat or the
sea. The contract belongs to the **issue**, not the pack: air is fed by three packs and has one hero.
A core issue declares it in its `app/issues/<issue>.yml`:

```yaml
hero:
  sign: sign-coast          # required; a symbol id in app/static/signs.svg
  pictogram: pix-coast      # optional; a symbol drawn at hero size. Absent: the sign, at hero size
  numeral: region           # optional; a distance or one of the issue's readouts. Default: the
                            #   nearest distance with a value, the same one the sentence leads with
  unit: m                   # required
  dp: 1                     # required; keep it the issue's own, or the sentence and the numeral
                            #   print the same reading two ways
  rule:                     # optional; absent means no rule under the numeral
    min: 0
    max: 4                  # the end of the drawing, not a limit; a reading past it sits on the end
    ends: { en: [flat, rough], id: [tenang, bergelombang], es: [en calma, picado] }
    dots: [region]          # the distances that may appear on the rule
    line: false             # true draws the issue's own line; it must declare one
  clock: time               # time · date. A yearly record says date, and the stamp prints when it
                            #   looked and when it looks next
```

The engine fills it every poll into `issues[<issue>].hero` with tonight's values, and names the
leader in `lead: {issue, by}`. **An issue with no `hero:` is watched, drawn in the matrix and listed
under the lead, and never leads**: the rule skips it. `make test` refuses a hero whose sign or
pictogram is not in `signs.svg`, whose numeral is neither a distance the issue fills nor one of its
readouts, whose rule dots name a distance the issue does not have, or whose rule draws a line the
issue does not declare.

A pack that brings an issue of its own will declare its hero the same way, in the `issue.yml` beside
its `pack.yaml`. The node does not load an issue from a pack yet; until it does, a new issue is a new
file in `app/issues/`.

## What ships

The `issue` column is which band of the dashboard a pack feeds. It comes from the pack's `domain:`,
except for a cross-domain pack, whose rules are claimed one by one in `app/issues/*.yml`. A pack that
reaches no issue and is not named as deliberately outside them fails `tests/test_issues.py` — see
[`DOMAINS.md`](DOMAINS.md).

| pack | kind | issue | what |
|---|---|---|---|
| air-quality | data | air | PM2.5 rules (inside/outside, spikes), cells |
| heat | data | heat | apparent temperature, heat stress, nights over 28 °C, a Social cell |
| insight | data | air (`agreement`, `rhythm`) | the air three ways, contributed to every report; daily agreement between indoor, street and model |
| nearby | data | air | the ring of other people's stations: is this address worse than everywhere, or is everywhere worse — no cell, by design |
| season | data | air | the same ring across time: is this week worse than its own preceding two months, paired per station — no cell, same reason as `nearby` |
| forecast | code | — feeds air and heat | wind and rain for the next day, from BMKG and Open-Meteo — context for the report, no alerts, no cell |
| trust | data | — the instruments | coverage, frozen channels, collocated disagreement — needs a week of a sensor before it names it; all three `info`, no cell, by design |
| cold-start | data | air (`modelled_air_today`, `sensor_vs_model`), heat (`hotter_than_normal`) | day one with no hardware: modelled air, normals |
| open-data-health | data | — the loop and the Index | a CKAN portal's maintenance state → Governance\|City |
| coast | code | coast | waves, swell, sea temperature (Open-Meteo Marine, key-free) |
| earth-engine | code | — Dynamic World, Sentinel-2, VIIRS | tree cover, built-up, NDVI, night lights (Google Earth Engine) |
| earth | code | land | this node's own copy of the AlphaEarth embeddings: the land change computed here, and a picture of the place for every year |
| place | code | — the ground, its own band | what is around the node from OpenStreetMap, in PostGIS: buildings, shops, schools, clinics, roads, green, walking distances |
| thingdata | code | — repair knowledge, its own catalogue | a ThingData server's things, guides and stories, and how much of the catalogue anyone has written down how to fix |
| make | code | — places, not numbers | the nearest active fab labs and what each can do, from the Fab Lab Network directory — display-only, no metrics, no cell and no alert, by design |
| example-cooking-hours | data | air | a worked example |

`make` is the only pack that stores no number at all. Its rows are `kind='facility'`: a place with
a name and a point, so an alert can end somewhere a person can go instead of on a reading. It has no
`cells.yml` and the reason is structural rather than a convention — `custody` is generated as
`kind='child' OR (local AND kind<>'peer')`, and a facility is `local=False`, so it could not reach an
Index cell even if somebody wrote the SQL. A fab lab down the road is not this node's measurement of
anything. Its `rules.yml` is empty for a matching reason: a lab opening is news on the scale of a
year, and the line it produces belongs in *other* packs' asks, at the moment somebody has just been
told they need something made.

Read [`packs/make/README.md`](../packs/make/README.md) before enabling it. The Fab Lab Network
directory is **not openly licensed** — each lab retains copyright in its own record and no data
licence is published — and the Foundation's decision to read it covers the Foundation, not each
node's operator.

Land's number is `earth`'s and only `earth`'s: the change this node computed itself, from embeddings
it downloaded. `earth-engine` contributes land's readouts (built and trees, from Dynamic World) but
not its change figure. It used to publish a `land_change_score`, and v0.33.1 retired it because it
was a second number for one idea with different provenance — the reason is in
[`packs/earth/README.md`](../packs/earth/README.md). Land does not fall back to it, and it does not
fall back to anything: `observations` keeps the latest row per source per metric forever, so a node
that ran the pack before the retirement still holds that row, and reading it would put a number
retired a year ago on the wall as this year's answer. With no record, land is `none` and says how to
fetch one.

Ten more ideas, with who might write them: [`PACK_IDEAS.md`](PACK_IDEAS.md).

## Contributing one

Start it in its own repository and develop it in `packs/<id>` on your node (see the top of this page). List it at
[fabcity/planetai-wild-packs](https://github.com/fabcity/planetai-wild-packs) by pull request so other nodes can find
it. Send it here only to promote it ([decision](decisions/2026-10-01-packs.md), point 3): useful beyond the place it
was written for or the reference for a pilot city, openly licensed, with offline tests registered in `tests/all`, and
a maintainer here who agrees to keep it. Then the pull request adds the folder and nothing else, and
`make lint && make test` run against it. The README must say where the thresholds came from and
what the pack does not know. Thresholds for Kuta Selatan are not thresholds for Barcelona; say which place you wrote for.
