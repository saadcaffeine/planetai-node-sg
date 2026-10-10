# Next release — collecting

> **Shipped through v0.76 (2 October 2026).** v0.63 to v0.66 took the arm64 database image, the
> wire-format version strings, `AGENT_PREFER=private` by default, the local model's read-and-act surface,
> Spanish (#67), the registry's `adapter`, the first act sources, `packs/make` and `MAKE_ENABLED`. v0.63
> broke rule 3 below and said so in its CHANGELOG. **v0.71 shipped item 1**, the interface redrawn
> (PR #106); v0.75 redrew the lead from `hero`, cut simple mode to three questions and added the ask pane.
> The other releases in between were work this page did not list. v0.76 (2 October) made packs core or wild
> (`docs/decisions/2026-10-01-packs.md`): `planetai packs add`, readouts, declared sections and `requires:`
> enforced; none of it was an item here. What is left on this page is what is still owed.

Changes asked for after v0.60 and not yet built. Tomas is collecting. Each item says what was asked,
what it touches, and what somebody picking it up needs to know that is not obvious from the code.

Add to the bottom. When a release goes out, move what shipped into its tag message and delete it from
here, so this file is only ever what is still owed.

---

## How two large changes are staged

Two things were coming that are larger than an item on this list: **the interface redrawn end to end**
(shipped in v0.71), and **new data sources**. They are staged differently on purpose, because they fail
differently, and the rules below still hold for any change to the page. A data
source that is wrong is one pack saying something false and can be switched off with a blank `.env` key;
a page that is wrong is every household reading it, on a wall, with no way back but an update.

Four rules for the queue while both are in flight:

1. **Only one branch at a time may change the suite count in `tests/all`.** That number is written by
   hand, git merges two bumps of it without a conflict and keeps one, and the result is a tree where
   every suite passes and the gate fails. Every new pack adds a suite. Merge them singly, in order.
2. **`app/static/*` and `packs/*` are merged in separate releases, never the same one.** When a node
   comes back wrong, the question "was it the page or the data" has to have one answer.
3. **A release ships one of the two, not both.** The tarball reaches Menorca and Bali before anyone here
   sees a screen; two large changes in one hop cannot be bisected by the person who has to report it.
4. **Sync the registry, then tag — in that order, every release.**

   ```bash
   git -C ../awesome-fabcity-data fetch -q origin
   tools/sync_registry.sh "$(git -C ../awesome-fabcity-data rev-parse origin/main)"
   ```

   Commit the diff with a CHANGELOG line, and only then tag. `data/sources/` is a pinned snapshot and
   **nothing checks that the pin is current** — `tools/check_registry.py` asks whether the snapshot is
   internally consistent, which is a different question and the right one: a node offline for a month
   must still pass its own lint. So the pin goes stale silently, and the only thing that catches it is
   somebody reading `data/sources/REGISTRY_VERSION` against upstream's sha.

   v0.62 is how this rule was learned. It shipped the registry at `5333ffa` — current when it was
   vendored that morning, three merges stale by the time the tarball was signed six hours later. A node
   on v0.62 reports six Seoul datasets as `live` that Seoul's own portal answers with a termination
   notice, and sends anyone following four sources to addresses that have moved. Nothing was broken and
   no reading was wrong; the node was simply repeating something that had stopped being true. Fixed in
   v0.62-2 by `tools/sync_registry.sh c2d33f7`.

   The pin is a sha because the script refuses a branch or a tag, which is the right refusal — a
   floating pin is a node whose answers change under it. That is also why this cannot be automated into
   the tag: vendoring is a commit somebody reviewed, not a fetch that happens during a release.

---

## 1. The interface, redrawn — shipped in v0.71

**Shipped in v0.71** (PR #106, "the page, rebuilt"), and redrawn again in v0.75. What is still owed from
this item is 1b and the Grafana question at its end; the rest is kept for how the layer is re-pinned.

**Asked, September 2026.** Direction H — the loop `observe · decide · act ·
measure`, one dial, every section a module — was chosen out of nine drawings and its shell shipped in
v0.54. The drawing itself, the graphic language the prototypes are in, landed in v0.71.

**Where the work already is — it is no longer on one laptop.** `dashboard-directions-2026-09` was
merged into `planetai-design`'s `main` as its PR #4 (`10b15fa`), and main has moved past it since. The
branch is gone locally and on origin, and its old head is an ancestor of main. That is the whole of
the redesign — H as a shell, `h/mods/` registered against `kit-page.js`, the wall as the grid, the
ground rule at resolution 9, the hardware section, and every state re-rendered — and it is safe.

**What holds the two repos together, and what it does not hold.** `tools/check_theme.py` is in
`make lint` and it *fails* rather than reports. Since 19 Sep it asks in two halves: the three frozen
files must hash to `data/frozen_layer.txt`, which runs everywhere including CI, and where
`planetai-design` is checked out they are also compared line by line against **the pinned commit**.
Before that it only did the second half, against whatever branch the sibling was on — so it answered
nothing in CI, which is the one place every pull request is checked. A token cannot drift onto a wall
screen now. What it does not hold is what the page *reaches for*.

**Re-pinning the frozen layer, when the layer moves.** Copy the three files from `planetai-design`
and run `python3 tools/check_theme.py --update`, which rewrites `data/frozen_layer.txt` and refuses
unless the design repo is present and agrees — so it can record a copy that was really made and never
bless a local edit. The gate warns when the pin falls behind, and that warning is the signal to do
this. It is an `app/static/*` change, so by rule 2 above it ships in a release of its own, never
alongside a pack.

*As of 19 September, straight after v0.61:* the pin was `8d79bf2` and `planetai-design` was 45 commits
past it, with `planetai-theme.css` differing by exactly one comment — its PR #5 closed OPEN item O8,
the rho row, so the header reads 11 OPEN instead of 12 and the `--rho-closed` note is gone. No token
value had moved, so that particular re-copy was a visual no-op. They will not all be.

`docs/design/LANGUAGE_GAP.md` is the reading of what the page reaches for: **13 of the layer's 34
tokens are referenced, 12 more are this surface's business and hard-coded instead** — `--rho-closed`
reached past to `--rings`, the ground's opacities baked into `node-ground.svg`, the wall's credit
lines using the page-local `--mute`. They resolve to the same pixel today. That is what makes it
quiet: when a token moves, the page will not. **Those counts are from 12 September, read against
`planetai-design` at `82e0f62`.** Main is far past that and O8 is one of the twelve, so re-read it
before trusting the list — starting 1b from stale numbers is how a re-tokening misses one.

**The staging, in the order it has to happen:**

- ~~**1a · Push `dashboard-directions-2026-09`.**~~ **Done** — merged as `planetai-design` PR #4,
  `10b15fa`. This was the only irreplaceable step on this item and it is no longer owed.
- ~~**1a½ · The scale spike, before the redrawing.**~~ **Written**, and it landed here as `81e3d45`
  (PR #73). `docs/design/SCALE_SPIKE_2026-09.md` names three sources — a city budget, a region's waste
  series, the planet's material footprint — and the five things about the page that each of them
  breaks. One fixture, four rungs, one place. Not a step any more; it is the thing the drawing is
  judged against, so read it before 1c and not after.
- **1b · Close the hard-coded tokens first, before any redrawing** (LANGUAGE_GAP says twelve; re-read
  it first, see above). Each is a one-line change from a literal to `var(--token)`, no visual change
  today, and `python3 tools/shots.py` proves it: the fixtures render identically at four widths or the
  change was not what it claimed. This is what turns the redesign from a rewrite into a re-tokening — after it, moving the language moves the page.
- ~~**1c · Port the modules, one section per PR, against the existing gates.**~~ **Moot** — the redraw
  shipped in v0.71. What follows stays true of any change to the page. `tools/check_ui.py` and
  `check_theme.py` stay in `make lint`; `docs/design/UX_REVIEW_2026-09.md` (64 findings) and
  `_skeleton.md` (26 more) are the acceptance list, and the four P0s v0.53 fixed are the regressions to
  watch for — a unit the page shouts into a different unit, a gap in a series drawn as a line through it,
  a locale the page claims the node did not send.
- ~~**1d · Two containers, not one.**~~ **Moot** since v0.71, and still how a page change is argued. The review rig on `pai-clean` runs the old and the new side by side
  on `:8081` and `:8082`. A screenshot of the new page alone proves nothing; the pair is the argument.
- ~~**1e · Node #1 last, and for a day before a tarball.**~~ **Moot** since v0.71. `planetai-design` is not a node and a fixture is
  not node #1: `docs/design/fixtures/` is what the page does with data somebody chose.

**Cost if wrong:** every household's page at once, including the wall at 1920 where nobody is standing
next to it to notice. It was the one on this list that had to ship alone.


### The open question inside this item: Grafana, and which surface it is for

**Asked, 18 September 2026.** Look at whether Grafana would show the data better than the drawings
this page makes by hand.

**Worth knowing before anyone starts — the node is closer to this than it looks:**

- `docker-compose.yml` already ships optional services behind profiles: `mqtt`, `agent`, `ipfs`,
  `reticulum`. A `grafana` profile is the established pattern, not a new idea, and it stays off on
  a household node that does not want it.
- `init.sql` already creates `planetai_ro`, a read-only Postgres role with SELECT on every table
  except `settings`. That is exactly the grant a Grafana datasource needs, and it exists.

**The real question, which is not technical.** Every number on this page carries provenance: it is
in `_provenance()`, it has a word — `live`, `partial`, `stale` — and the Figures band is generated
from that list, so a number with no row there cannot be drawn at all. Grafana queries Postgres
directly and would bypass all of it. A panel showing a 24-hour line has no way to say "this sensor
was silent for seven hours and the line is drawn across the hole", which is the exact fault the
September review found and v0.53 fixed.

So the question to answer is not "can we run Grafana" — we can, cheaply — but **which surface it
is for**:

- *For the household, on the dashboard*: it has to inherit the provenance rules, and today it
  cannot. This is the hard version.
- *For the keeper, beside the dashboard*: a separate Grafana at its own port, for somebody
  debugging a sensor or reading a month of data, with no claim to be the household's page. This is
  cheap, honest, and does not touch the dashboard's rules at all.

**Suggested first step:** stand it up behind a profile against `planetai_ro`, point it at node #1's
readings, and look at what it shows that the page cannot — then decide which of the two surfaces it
is. An evening's work to answer properly, and nothing shipped to households until it is answered.

---

## 2. New data sources

**Asked, September 2026.** More of what a node can read. Three were in flight when this was written and
they are the pattern, not the exception: `xiaomi-air` (LAN purifiers) and `thingdata` (a repair commons,
PR #70) shipped in v0.61, and `earth` (AlphaEarth, nine years a square) has shipped since.

**A source is a pack, and the pack contract is the whole of the discipline.** `pack.yaml` declares
`metrics`, `scales`, `requires: {node: ">=x"}`, its `env:` keys and, for a code pack, its `pip:` line;
`channels.yml` declares each channel's *role* — `ambient`, `enclosure`, `device_health`, `derived`,
`index` — which is what stops a radio's own warm box being pooled into the street's temperature;
`cells.yml` is what it may publish; `rules.yml` is what it may say. Nothing new is needed to add one.

These are the bars for a **core** pack, one that ships in the release. A pack for one place is wild: it clears its
own tests and the weekly check at fabcity/planetai-wild-packs, and is merged nowhere here.

**What a new source has to clear before it is merged, in this order:**

1. **A test file and the suite count.** `tests/test_<pack>.py`, a line in `tests/all`, and the count at
   the bottom of that file moved. One pack per release, per rule 1 above.
2. **Three languages.** Since #67 (v0.63), `tests/test_packs.py` fails any message that does not carry
   `en`, `id` and `es` with the same placeholders. Write all three when the rule is written; retrofitting a
   language across nine packs is what #67 was.
3. **`contributes: report` or an alert, never both and never neither.** `tests/test_packs.py` checks it.
   A number that belongs in the daily report is not an interruption.
4. **Provenance, or it cannot be drawn.** A number with no row in `_provenance()` cannot appear on the
   page at all, and `live` is not the pack's to claim: `s.local OR s.kind = 'child'`, ≥2 sensors across
   ≥2 children for a community node. A pack that wants a cell to say `live` is asking for custody, which
   is a decision, not a field.
5. **A timeout on every HTTP client.** `make lint` fails on `httpx.Client()` with no timeout, because
   httpx has no read timeout by default.
6. **Off by default.** A blank `env:` key idles the pack. A source that costs money, needs a token, or
   leaves the household's network says so in `needs:` and does nothing until somebody sets it.

**What is NOT decided and should be, before the queue gets long:** whether a source that has never run
against its real server ships to households at all. `thingdata`'s threshold is a guess carried over from
`open-data-health`'s guess about CKAN portals; `xiaomi-air` was verified live on node #1 and is the
better precedent. Proposal: a pack reaches a tarball only after one live run somewhere, and `pack.yaml`
carries the date and the node it ran on.

**Cost if wrong:** one pack says something false on one node, and a blank `.env` key switches it off.
That is why these can go out two or three to a release while item 1 cannot.

---

---

## 3. Drone imagery: choose the provider

**Asked, 7 October 2026.** Tomas, after seeing the Benoa mosaic on the map: drone imagery is a core part of the
node, and a node should be able to choose its drone imagery from other providers, not only the one
`planetai run place basemap` picked.

**What there is.** `packs/place/basemap.py` (`drone()`) queries OpenAerialMap's catalogue for open (CC BY) mosaics
crossing `GROUND_DRONE_RADIUS_KM`, newest first, and keeps their tiles in `out/ground/drone.mbtiles`;
`/ground/meta` lists the mosaics with provider, date and resolution. Node #1 found one (Saragis Multikencana, Benoa,
7 cm, December 2024); it stops 1.5 km east of the house.

**What is owed.**
- A list of the mosaics a node could take, with provider, date, resolution and licence, and a choice of which
  (Set up → Place, or `planetai run place basemap --drone <id,…>`). Today the newest wins where two overlap.
- Providers beyond OpenAerialMap's catalogue: a household's or a lab's own flight (a GeoTIFF dropped into the node,
  tiled locally), a city's open orthophoto service (WMTS/TMS with an open licence), other open catalogues. Each one
  answers the licence question before it is listed: the node keeps tiles, so the licence must allow keeping them.
- Credit per mosaic on the map, as now, and in `/ground/meta`.

**Touches** `packs/place/basemap.py`, `app/main.py` (`/ground/*`), the map ground in `app/static/dashboard.js`, and
Set up. A pack change and a page change: two releases under rule 2.

**Also owed from the same work.** The Sentinel-2 composite (`planetai run earth-engine basemap`) has not run on a
node yet; its first run is on node #1. The design prototype's Place door (planetai-design R36–R38) is where the
layers panel, scales and inspector were drawn; the node's map ground has the bases, not yet the panel.

---

## 4. The language split, what is left

**Asked, 9 October 2026; shipped in four releases.** A (words) in v0.80.4, B (page) in v0.80.5, C (headlines
from clauses) and D (every threshold alert names whose line) in v0.80.6 — C and D tagged at `aeb5a27` under
Rule 2, the packs side of the 10 October batch. What remains of
`docs/SPEC_language.md`'s migration: the doors read the node's English only — locale work shows on the
classic dashboard and the bot until the doors gain locales (migration item 8); the native passes — es by
Tomas, id by Bayu, each approved locale shedding its ASSISTANT-WRITTEN header (item 9); and
SPEC_language.md itself joining the stamped docs set (item 10).

## 5. Alert events and the Decide card, what is left

**State on 10 October 2026, after v0.80.7.** The week's arc: SPEC_alerts approved 5 Oct; the engine proven by
replay in shadow; v0.77 (events on the wire, `POST /actions`); v0.78 (the Decide card); v0.80.4–5 (its texts
in the three layers); v0.80.7 (the card's live stamp, the Telegram buttons closing the loop from the phone,
the answer carrying the household's note, the page insisting on a name). Node #1 runs `ALERT_ENGINE=events`
and was the test bed: a live Doesn't-fit press and its note landed as two rows, fourteen seconds apart, and
the card showed both. The heat margin stays at 1 °C (`docs/decisions/2026-10-10-heat-margin.md`): a sustained
event open through a hot Kuta Selatan night is the hysteresis describing the weather. Do not "fix" this by
tightening the margin or adding a daily auto-clear; the question was asked from the field and answered by
Tomas. The Cowork audit of 10 Oct landed two refinements in the same release: `node_url()` for the bot's
plain-HTTP URLs, and the note window recorded as knowingly process-memory (a bot restart inside the ten
minutes loses the question, never the dismissal; persistence comes with the learning work below, not before).

**Still owed, in the order that pays:**

1. **Learning from the answers** (SPEC_alerts §5): among actions whose `when:` holds, prefer the one that
   cleared fastest in this house (`cleared_after_min` is already recorded on every Done-then-clear), and
   mute an action for 30 days after two Doesn't-fits. The data exists; the ranking does not.
2. **Anticipation** (§6, Plan 3): the engine ranks `ahead` events but no pack ships an `ahead` rule — the
   morning plan, the unusual day ahead, the evening crossover. The measures (`usual_by_hour`, `ahead_12h`)
   are already there.
3. **ρ over events** (§7): ρ still counts alerts with the derived-measured trick; the switch needs its own
   `docs/decisions/` record because it changes a published number. The events carry `responded_at` and
   `acted_at`; the funnel's `measured` has no event-side notion yet.
4. **`alerts.event_id` back-link**: the wire matches covered rows by time window — the spec's own "until
   then" branch.
5. **Reports built from events** (§11 step 7, Plan 4): `REPORT_AT`, `REPORT_SKIP_EMPTY`, a report that
   opens with the morning plan.
