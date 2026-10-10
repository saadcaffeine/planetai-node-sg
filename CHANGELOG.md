# Changelog

## Unreleased

## v0.80.10 — 2026-10-10 — The boot screen is the loading screen

- **No dead shell before the asking face, on either face of the node.** The doors and the classic dashboard
  used to paint their chrome — the nav, the register buttons, the empty middle — for a breath or two before
  any script arrived to open the asking overlay. Both overlays now ship already on: the first paint is the
  asking face, whose brand, frame and blink are CSS and move before a line of JS runs, and the glyph globe
  joins when the page's own `open()` wires the canvas over it (its `on` is a JS flag, so the pre-shown face
  does not stop it). Every path out closes it as before, and a browser with scripting off gets the shell
  instead of a spinner that would lie (`@media (scripting: none)` — not a `noscript` style tag, which the
  page architecture forbids and check_ui would rightly trip on).

## v0.80.9 — 2026-10-10 — The split reaches the Now door's hour scrubber

- **The Now door titles with the split, live hour and past.** v0.80.8 split the hero and the wall but missed
  the doors Now door's own sentence line: the live hour still drew the whole sentence bold, and a past hour
  still opened with the reading — "At 04:00 the air in the house read 8 µg/m³, under the line." The live hour
  now draws `title` + `tagline` like every other surface, and a past hour splits the same way on the page's
  own words: the title is what it meant ("The air in the house was under the line."), the tagline what it
  measured ("At 04:00 it read 8 µg/m³.") — smaller, not bold, muted. First the meaning, then the instrument.

## v0.80.8 — 2026-10-10 — The title says what is happening; the readings arrive a beat later

- **The sentence splits into `title` + `tagline` (SPEC_language, the progressive-disclosure pattern applied to
  the title itself).** The headline a page shows is no longer the whole sentence: the title is the qualitative
  head — "The air is getting worse in the house" — with no number and no indicator in it, and the tagline is
  the explanation set smaller and muted beneath — "Under the WHO line. Level with the street, the ring and the
  region." A household reads the situation first and meets the instruments one line down; the numeral and
  `plain` stay where they were. The split is engine work (`_sentence_parts`, at the `{line}` clause), so it
  holds in en/id/es and for every issue, and templates without a `{line}` clause do not split. The full
  `sentence` stays on the wire for prose — the bot, the asks, the wall's thinking-aloud. The doors wall takes
  the same split, which is also its fix: release C's clause-headlines had grown the wall's sentence past its
  screen (the visual gate caught 1,113 px on a 1,080 px wall at release C and every commit since), and the
  title/tagline split brings the wall back to exactly its viewport — verified against the fixture render.
  v0.80.7 was tagged but never shipped: CI held it on exactly this wall failure, and this is the fix it was
  waiting for.

## v0.80.7 — 2026-10-10 — The loop closes from the phone, and the card says whose answer it carries

- **The answer carries the household's own words, and the page insists on a name.** The wire's `answer` now
  carries `note`, and the card draws it in quotes — `Doesn't fit · tomas · 13:20 — "opened the west side"` —
  so the reply to the bot's one question is visible where the answer lives. And the card's form no longer
  sends an anonymous answer: five nameless rows landed on node #1 the morning the card looked frozen — the
  presses worked, but the record could not say whose they were. (curl may still post an empty `actor`; a LoRa
  bridge may not know names, and the card says "somebody" for those. spec §4.2 amended.)
- **Telegram buttons close the loop (SPEC_alerts §7, Plan 2's first half).** An event's message now carries
  Done / Not now / Doesn't fit when the bot in the agent container has announced itself (`TELEGRAM_BUTTONS=1`,
  set on startup; a node without the bot sends the same message bare). The press is the same `POST /actions`
  the dashboard makes — page and phone write one row — then the keyboard lifts and the chat carries the record
  (`Done · tomas`). *Doesn't fit* asks the one optional question and keeps the reply as the note: the dismissal
  is recorded at the press, a free-text line within ten minutes rides a second row, and the wire's latest answer
  is the one carrying the note. Labels are the wire's own in en/id/es. The learning from these answers (§5) and
  ρ over events (§7's decision record) are still owed. Tested live on node #1 the same morning: a press and a
  note landed as two rows, fourteen seconds apart, and the card showed both.
- **The Decide card says it is watching.** An open event's card now carries "watching — last seen …" in its
  header, from the wire's `last_seen_at`, ticking up on every poll: the visible proof the feed is alive while an
  event sits open for hours. The margin that keeps such events open on hot nights stays as written — the stillness
  was the card's, not the engine's (`docs/decisions/2026-10-10-heat-margin.md`, spec §4.2 amended).
- **`node_url()` replaces the `MCP_URL.replace("/mcp", …)` munge** at its three call sites (the Cowork audit's
  caveat): the bot's plain-HTTP URLs no longer depend on the letters "/mcp" being present in the setting.
- **The pre-commit hook adopts the brew `PATH` export and keeps its test gate.** The export was working-tree
  drift from a GUI-fired session (hooks inherit no shell profile); the drift's other half — `make test`
  commented out — was refused: a hook that skips the suite teaches `--no-verify`.

## v0.80.6 — 2026-10-10 — The alerts name whose line it is

Tagged at `aeb5a27`, the last commit whose tree holds no `app/static` change — Rule 2: page and packs ship in
separate releases, so "was it the page or the data" has one answer. The page half is v0.80.7.

- **Every threshold alert names whose line it is (release D of the language split).** The audit of
  releases A–C found the gap: `docs/SPEC_language.md` rule 10 was delivered in the event templates
  but not in the pack messages a household receives. The heat and air-quality act rules now say it —
  "this house's own line is {line} °C, measured here" for heat, "past the US EPA line ({line} µg/m³)"
  for air — filled from `watch.over` by `main.py`, so the number is never a second copy. `heat_stress_now`
  drops "dangerously" (danger is a register, not a volume; `heat_danger` keeps it, and keeps being the
  only place it appears). `tools/check_rules.py` fails any act/warn rule with a `watch.over` whose
  message skips the `{line}` clause, and any `{line}` with no `watch.over` to fill it — the gate that
  would have caught the gap. The sign-off pins in `tests/test_shipped.py` moved with Tomas's approval.
- **Headlines assembled from clauses (release C).** The review found the titles repetitive and flat:
  `{line}` (over · near · under, computed from the live value, named per issue), `{event}` ("It crossed
  the line earlier today"), and per-issue `cmp_words` ("cleaner than the street" for air, "cooler than
  the street" for heat). Heat's skeletons are its own; coast and land headlines dropped the jargon.

## v0.80.5 — 2026-10-09 — The page speaks the three layers, and the Wall's voice lives on the node

- **The page speaks the three layers, and the Wall's voice lives on the node.** The second half of
  the language split (`docs/SPEC_language.md`): the crossed mark moved out of the sentence (words
  only since the last release) and onto the figure inside `plain` when it is over the line; the
  wall card drops `plain`'s first clause, which only repeated the numeral drawn above it; and the
  Wall's thinking-aloud prompt moved from the page into the node as `WALL_SYSTEM` beside the other
  two prompts — the page asks for it by name (`prompt: 'wall'` on `/ask`), the node rotates the
  angle, and the scrubbed figures ride in the system prompt as they always did. The "How a
  sentence is built" panel now describes the three layers: the headline in words, `plain` the
  figures, `about` the meaning.
- Registry pin: `awesome-fabcity-data @ 851b8db` (269 entries; content unchanged, stamp current).

## v0.80.4 — 2026-10-09 — The headline speaks in words, and update says what blocks it

- **`planetai update` says what blocks it, and what "nothing moved" means.** A failed pull on a git
  install now names the dirty files and the local-only commits (git's own error does not), and a
  pull that moves nothing asks the channel: if the site serves a release whose tag has not landed
  on the branch yet, it says the release is still shipping instead of staying silent (node #1 ran
  three no-op updates in a day chasing v0.80.3). The Set up → Updates row now says *checked N h ago*
  instead of a bare date, so a stale "this node has it" reads stale. `.gitignore` now covers the
  operational files a git install writes (`.planetai-*`, `.env.before-*`,
  `config/rules.yml.before-update`) — a `git add -A` used to sweep them in, and a tracked update log
  made every later pull refuse.

- **the headline goes words-only, and `plain` carries the figures** (SPEC_language, release A). The
  lead sentence speaks in words — "The air is getting worse in the house, and the source is inside
  the house" — and the plain sentence under it holds the numbers: the numeral distance first, then
  the others, then the line. Context issues (coast, land) get word headlines; their figures move to
  `context_plain`. Each issue gains an `about` text — what the metric is and whose line it is — on
  `/issues` and in the ask pane. Alerts name whose line it is (the WHO's, or this house's own).
  Event figures honour the issue's `dp` (42, not 42.0) and `outside_*` values carry their units.
  The bot and the ask pane gain the layers rule and the no-lecture rule; the pane gains the
  one-number rule it lacked. The page half (the crossed mark, WALL_SYSTEM) follows in release B.

## v0.80.3 — 2026-10-08 — The doors open on a node that reads nothing yet

- **the doors dashboard no longer crashes on a node with no local sensors.** Since v0.80.1 made the doors
  the default page, `dayWeek` assumed every issue carries an hourly series for its hero distance. A node
  that reads the issue at no distance — a model-only node, and every fresh install until its first sensor —
  is answered `distance: null` with every band null by /issues/days, and `it.series[null]` threw before the
  page could draw. The boot's catch-all then showed the locked screen, telling a household whose node was
  sharing fine that "this node is not sharing its readings with this screen". The day now draws with no
  line, the node's own sentence carries the view, and the throw is gone. Found on a tester's node in
  Menorca; reproduced and verified against it live.

## v0.80.2 — 2026-10-08 — A reinstall over an old database is refused, and posidonia joins the wild packs

- **a reinstall over an earlier node's database is refused again.** Since v0.42 the install's old-database
  guard derived the Docker volume name from the folder's basename, but docker-compose.yml has always pinned
  `name: planetai`, so the volume is `planetai_db` whatever the folder is called. A reinstall in a folder
  named anything else (every tarball install: `planetai-node`) sailed past the guard with a fresh
  POSTGRES_PASSWORD, and the app was locked out of its own database: /health answered "pre-0.4 (run
  ./update.sh)", /rho answered 500, and only `planetai doctor` guessed why. The guard now checks the volume
  compose actually names. /health says "unreachable" for a login failure and keeps "pre-0.4" for a schema
  that predates schema_version, and the doctor's row names both with their different ways out. Install
  warnings now land in `.planetai-install.log` as well as on the screen.
- **posidonia is a wild pack.** The Posidonia seagrass meadow pack leaves core and is listed at
  `fabcity/planetai-wild-packs`. Only Mediterranean coastal nodes need it. **If you use it:** run
  `planetai packs add posidonia` after updating. A node that updates with git loses the folder on update;
  a node updated from a tarball keeps the folder, which `packs add` will not replace until `packs/posidonia`
  is deleted. Stored readings are untouched.

## v0.80.1 — 2026-10-08 — The doors view is the default dashboard

- **posidonia is a wild pack.** The Posidonia seagrass meadow pack leaves core and is listed at
  fabcity/planetai-wild-packs. Only Mediterranean coastal nodes need it. **If you use it:** run
  `planetai packs add posidonia` after updating. A node that updates with git loses the folder on
  update; a node updated from a tarball keeps the folder, which `packs add` will not replace until
  `packs/posidonia` is deleted.
- **The five doors layout is now the default dashboard**: root `/` serves `doors.html`; `/?layout=classic` serves the legacy dashboard (`index.html`). The footer link in `doors-core.js` now points to `/?layout=classic`.

## v0.80 — 2026-10-07 — The ground becomes a map, and the node opens five doors

- **v0.80 carries two page changes and two pack scripts, against `docs/NEXT_RELEASE.md` rules 2 and 3.** Tomas asked
  to pack the map and the five doors into one release. Both page changes are opt-in: the map ground draws only with
  `UI_GROUND=map`, and the doors only at `/?layout=doors`; `/` is the v0.79 dashboard on a node that changes nothing.
  So "was it the page or the data", and "which page", still have one answer each. Node #1 has run both since 7 October.
- **The five doors, on trial at `/?layout=doors`**: Now, Place, Data, Wall and Node,
  the redesign from planetai-design, drawn from the node's own routes with the screen's token. Without the token a
  door draws what `SHARE_LEVEL` gives and says what it is not drawing; the map, the cells, the distances and the
  hourly table stay token-only. Done, Not now and Doesn't fit and the ask pane write to the node as the dashboard
  does. The Wall's drawing is a living map: the node's dark street map, the wind now, and every station's hourly mean replayed as discs; Now draws the stations around the house on a map with the node's rings and cells. The Wall thinks aloud: every ten minutes, with a countdown, the node's model, the one chosen under Set up → Model, says in plain words what the figures mean and what the next hours may bring, and names itself. Set up is a page of its own behind a gear, and its Machine section reads two new token-only routes: `GET /machine` (processor, load, memory, temperature, uptime, system, database) and `GET /storage` (what the node keeps, the free disk, and the days it lasts at the last week's rate). The dashboard at `/` is unchanged. `docs/decisions/2026-10-07-doors.md`.
- **The map ground's half of rule 2, as v0.77 did.** The
  map ground changes `app/static`, and `place` and `earth-engine` gain a `basemap` script that the map's own bases
  read. The scripts only run when somebody types the command, and the map ground is off unless `UI_GROUND=map`, so
  "was it the page or the data" still has one answer on a node that has not opted in. The figures shipped alone in
  v0.79.
- **The ground can be a map** (`UI_GROUND=map`, default `svg`): MapLibre draws the base and deck.gl the cells and
  stations, so it pans and zooms. Without WebGL2 it draws the svg ground and says why. The two libraries are served
  by the node (860 kB gzipped) and fetched only when the ground is drawn this way. Simple mode and the wall keep
  the svg ground. `docs/decisions/2026-10-06-ground-map.md` holds the measurements.
- **A detailed map kept on the node.** `planetai run place basemap` keeps OpenStreetMap vector tiles (cut out of
  Protomaps' daily build, with the label fonts) and any OpenAerialMap drone mosaic (CC BY 4.0) that crosses the
  node's area; `planetai run earth-engine basemap` builds the node's own cloud-free Sentinel-2 picture of the last
  twelve months. Each says what it reveals before it runs, once. The map ground offers them as bases that send
  nothing: "street map, on this node", "satellite, on this node" and "drone, on this node".
- `GET /geo/grid`, `/geo/cell` (with `children` and `polar`), `/geo/measure` (with `each`), `/geo/rings` and
  `/geo/planet` answer the shapes and distances a map draws, so the page computes no H3 and no distance; `GET /ground/meta`, `/ground/{vector,drone,imagery}/{z}/{x}/{y}` and
  `/ground/glyphs/…` serve the kept map. All need a token or this machine, like `/place/geojson`.
  `tools/check_ui.py` now fails a page that imports h3-js or calls an H3 function.
- **The wind, as a field.** With `FORECAST_OPENMETEO=1` the forecast pack also keeps Open-Meteo's hourly 10 m wind
  for the next day at 8 × 8 points over ±30 km round the node, and the node's own point, in one request
  (`GET /ground/wind`, private; `planetai run forecast windfield` refreshes it now). It asks with
  `cell_selection=nearest`: the default moved sea points up to 12 km onto land. A model's field for drawing, never
  a reading.
- A Making Sense Bali DIY node can publish to this node's own broker instead of to smartcitizen.me: `planetai broker`
  prints what to type into the node's setup portal. The node keeps every reading with the device's own timestamp, the
  retained `meta` message gives the device its name and says whether it is indoors, and the tokens listed in
  `SC_FORWARD` are passed on to the platform unchanged, through a queue that waits out an internet outage. `/health`
  gains `direct` (devices, messages, forwarded, queued). The parser also reads a Smart Citizen Kit's own `readings/raw`
  format, but this node's broker still refuses a kit, because the kit's firmware cannot send a password.

## v0.79 — 2026-10-07 — The dashboard draws the day

- The dashboard draws each issue's day once, as one drawing you can point at: every distance, the usual for each hour,
  the hours over the line, the alert event and its answer, and the event's own rooms, with the hour read out in words
  (the arrow keys work too). Under it, a strip of the last seven days, one cell an hour; Historical draws every day
  the node holds. Each station row draws its day, and a station that stopped reporting is kept in a fold with when it
  was last heard. Measure counts the hours over the line. The drawings use Observable Plot, served by the node itself.
- `GET /issues` carries what the page's new drawings need: each issue's usual day (`usual`), an open event's own rooms
  hour by hour (`events.open[].series`), and, apart from `stations`, the stations that stopped reporting in the last
  30 days (`stations_silent.stations`), kept with when they were last heard (relays of kits that still report are
  left out). `GET /issues/days?days=7` (up to 90) gives the
  same hourly series over many days with the hours over the line counted per day, and `planetai snapshot` captures it.

## v0.78 — 2026-10-06 — The dashboard tells the bot's story

- The dashboard opens on what is happening now: each open alert event once, with the action the bot sent and Done,
  Not now and Doesn't fit, then the readings that explain it. Act is the record of what was asked and answered, and
  four sections about resolution and custody moved to Network. A node still on the old engine keeps its alert cards,
  with "I did this" on them.

- On a node whose alert engine is `shadow` or `events`, an issue's state follows its alert event: `act` while it is
  open and unanswered, `notable` once somebody answers, and for a day after it clears. The old heat and air alerts
  no longer count as open asks there, so the page's lead, the ask pane and the bot agree with what Decide shows.

## v0.77 — 2026-10-06 — Alert events: one message per story, with one action

- **2026-10-06 · The source registry is re-pinned to `awesome-fabcity-data` at `851b8db`** (from `88f5c73`), 269 entries: the Global Power Plant Database is filed as an Environmental|Region candidate (registry #79). `docs/NEXT_RELEASE.md` rule 4.
- `GET /issues` carries the alert events (`events`): what is open, its one action as it was sent, its latest answer, and the alerts it covers; an open event now leads the page. `POST /actions` takes an `event_id` with Done (`acted`), Not now (`acknowledged`) or Doesn't fit (`dismissed`), and `GET /actions?events=1` lists those answers. The page that draws them is v0.78; the Telegram buttons are Plan 2.
- **2026-10-05 · The report says "dangerously hot" only at real danger.** It opened with "🥵 It is dangerously hot
  inside" whenever any heat alert was open, so node #1's 13:00 report said it on an ordinary 35 °C afternoon, as the
  old alert did. Now "dangerously hot" is said only when `heat_danger` (feels like 40 °C or more) is open; the 35 °C
  line reads "🌡️ It is hot inside: it feels like 35 °C or more."

- **2026-10-05 · `ALERT_ENGINE=events` sends.** The event engine's heat and air messages go to Telegram, one per
  event, with quiet hours and a daily ceiling; the old heat and air rules still record their alerts (the dashboard,
  rho and Home Assistant read those) but stop sending. Every other alert and the reports are unchanged. No buttons yet:
  those, and learning which action worked, come next. Node #1 sent "dangerously hot" twice at 35.0 °C on an ordinary
  afternoon the day this was written; in events mode an ordinary afternoon sends nothing.

- **2026-10-05 · `planetai test-alert` finds its own alert.** It decided whether the test fired by counting the rows
  `GET /alerts` returned, which is at most 50 by default, so on any node with 50 or more alerts it said "no alert fired
  in 90 seconds" while the alert had reached Telegram, and the one-minute test rule fired a second time while it waited.
  It now looks for the run's own rule id and removes the rule the moment it is seen: one test message, and the right
  answer.

- **2026-10-05 · Alerts become events, in shadow** (docs/SPEC_alerts.md). Node #1 sent about 13 messages a day,
  "dangerously hot" on 14 of 14 ordinary days, and its household answered 2.5%. A new engine folds rule rows into one
  story per issue per house (open, escalate, clear), sends only danger in quiet hours, keeps a daily ceiling, and picks
  one action from inside against outside, the hour and what the home has. It runs only with `ALERT_ENGINE=shadow`,
  which records what it would send and sends nothing; the default, `rules`, is unchanged. On node #1's month it would
  have sent 4 a day instead of 9 (2 without all-clears), none at night, and no "dangerously hot" below 32 °C
  (docs/plans/2026-10-04-alert-events-replay.md). Three fixes from that replay: a Meshtastic radio's own box
  temperature is never read as a room; a room's usual for the hour is the fourteen complete days before today, so a
  long hot run does not raise its own bar; and air danger re-sends only when its value doubles, never within 30 min.

- **2026-10-05 · `uncovered_asks` leaves out the alerts of the packs the engine replaced.** The event engine runs only
  with `ALERT_ENGINE=shadow` or `events`, and only for heat and air-quality; their old rules' alerts are what the events
  stand for. On the dashboard, `GET /issues` includes the event engine's answers in `events.uncovered_asks`, but those
  answers now leave out the heat and air-quality alerts the events replaced, so a reader of the open asks sees one
  number instead of the old alerts plus the new events.

- **2026-10-03 · The docs site cannot fall behind a release again.** v0.76's site still described v0.75.3 on its
  packs pages: four pack.yaml fields, the wild tier and `requires` enforcement were in the code and in PACKS.md,
  and every gate was green. `make lint` now checks both directions: every CLI command, MCP tool, route, setting
  and pack.yaml field the code has must be on its docs page. And every page of the site carries
  `<!-- checked: vX -->`, the release it was last read against, which must equal the newest release in this file;
  the release pull request fails until each page has been read again (`skills/release-docs/`). Every page was
  read against v0.76 and main for this change; features on main and not in v0.76 say so where they are described.

- **2026-10-03 · xiaomi-air is a wild pack.** The Xiaomi purifier pack leaves the release and is listed at
  fabcity/planetai-wild-packs, with its test. Only a household with Mi Home purifiers needs it, and it installs
  python-miio, which is GPL-3.0-only. **If you use it:** after updating, run `planetai packs add xiaomi-air`. Your
  `XIAOMI_PURIFIERS` line stays. A node that updates with git loses the folder on update, and the purifiers go
  quiet until the pack is added. A node updated from a tarball keeps the old folder, which `packs add` will not
  replace: delete `packs/xiaomi-air` first. Stored readings are untouched.

- **2026-10-03 · Xiaomi purifier tokens are masked.** `XIAOMI_PURIFIERS` holds each purifier's device token, and the
  xiaomi-air pack did not list it under `secrets:`, so Set up and the agent's `settings_get` showed the tokens in full
  to anyone holding the admin token. The pack-secrets entry below was wrong to say no shipped pack holds a secret. It is listed
  now, and a test fails if any shipped pack key whose name or description says token, key or password is not.

- **2026-10-03 · A wild pack's scripts reach an agent only when it says so** (#168). The agent's `run_pack_script`
  ran any pack's script and handed back what it printed. A wild camera pack keeps motion off the readings on
  purpose, and its `events` script printed a year of the household's motion to whoever asked. A wild pack's
  scripts now reach an agent only when its pack.yaml lists them under `agent_scripts:`; the refusal says to run it
  from the node's terminal, where `planetai run` runs every script as before. Core packs are unchanged, except that
  an agent can no longer run a pack's `adapter.py` as if it were a script.

- **2026-10-03 · A pack's secrets are masked like the node's own.** Every key a pack declared reached Set up as
  plain text, so a pack's API key or token was shown to anyone holding the admin token, and through the agent's
  settings tool. A pack now lists its secret keys under `secrets:` in its pack.yaml, and Set up masks them once
  saved and never shows them again, as it does the Telegram token. Keys a pack does not list behave as before. No
  shipped pack holds a secret today; wild packs that do, such as a camera bridge token, should list it.

- **2026-10-02 · The page no longer describes a pack that does not exist.** Every node's Measure notes explained
  "a slot this page has no place for" with "the water pack's gauge" as the example. There is no water pack, and the
  contributions vocabulary behind the note, a pack filling a slot inside an issue's card, was built for the
  September prototypes' sample data and never produced by any node. It is removed. A pack's number on an issue is
  a readout, a pack's own band is a declared section, and no pack fills an issue's distance column
  (`docs/decisions/2026-10-01-packs.md`, point 4). Nothing a node draws today changes except that one note.

## v0.76 — 2026-10-02 — Wild packs: added from anywhere, drawn on the page, refused when too new

*Packs in this repository are core; every other pack is wild, listed at fabcity/planetai-wild-packs and added to a
node with `planetai packs add`, pinned to a commit, without git. A pack can now add readouts to an issue and
declare a section of the dashboard as data, drawn with the page's own cards and never with the pack's own code.
A pack written for a newer node is refused whole, and an update stops before it would overwrite a wild pack that
became core. Also: a node says when a new version is out, and the FAB26 experiment has a page.*

- **`planetai packs add` fetches a wild pack.** Packs in this repository are core; every other pack is
  wild, listed at fabcity/planetai-wild-packs (`docs/decisions/2026-10-01-packs.md`). `planetai packs add <id>` takes
  one from that list at the commit it was listed at; `planetai packs add <owner>/<repo>[/<folder>][@<ref>]` takes any
  pack on GitHub, and a branch or tag is pinned to the commit it names. It fetches with curl and tar, because a node
  installed the default way has no git, writes where the pack came from and at which commit to `packs/<id>/.wild`, and
  runs `packs install`. It never replaces a folder that did not come from it, so a core pack cannot be overwritten, and
  it refuses symbolic links, an id that is not the folder shape, and an id the list and the pack disagree on.
  `planetai packs` now lists core and wild apart. Removing one is deleting its folder.

- **A pack can add readouts to an issue.** A pack's `pack.yaml` can declare `readouts:` for an issue,
  in the shape an issue file uses, and the node adds them after the issue's own while the pack is enabled: rows in
  Figures, and words in a context issue's sentence. This is how a wild pack shows its numbers on Air, Heat or Coast
  without editing `app/issues/` (`docs/decisions/2026-10-01-packs.md`, point 4). It adds and never replaces: the same
  sensor and metric is not shown twice, and a readout naming no issue, or missing its unit or a label, is left out
  with a line in the log. No shipped pack declares readouts, so `/issues` on every node is unchanged.

- **A pack can declare a section of the dashboard.** A pack's `pack.yaml` can now list `sections:`, each
  a stage, a title and the readouts it shows. The node fills them with its own rows and serves them in `/issues` as
  `sections`, and the page draws each one as a band on Now with its own readout cards, and as columns on the wall
  when the pack asks. The pack ships no code for the page: a script there could read the admin token, so only core
  packs ship script (`docs/decisions/2026-10-01-packs.md`, point 5). A reading the node has no row for is not drawn,
  and the band says how many have not arrived. No shipped pack declares a section, so every node's page is unchanged.
  Also: a pack's malformed readout or section is now logged once, not on every `/issues` request.

- **A pack written for a newer node is not loaded.** Every pack's `requires: { node: ... }` is now
  enforced: a node that does not match leaves the pack out whole, rules and adapter alike, says so once in its log,
  and `planetai packs` lists it under "not loaded" with the reason (`it needs a node >=0.80.0 and this node is
  v0.75.8; planetai update first`). `planetai packs add` warns at once. A node that cannot name its release, such as
  a developer's checkout, loads everything. The rule is `app/requires.py`, shared by the loader and the CLI, which
  runs it on the node's own Python 3.9. Every shipped pack loads on v0.75.8, and a test keeps it that way.

- **`planetai update` stops for a promoted wild pack.** When the version arriving ships a core pack
  with the same id as a wild pack on the node (one `planetai packs add` fetched), the update stops before anything
  moves, names the wild copy and where it came from, and asks for it to be deleted. Without this, the tarball path
  unpacked the core pack's files over the wild copy and left a folder that was neither, and the git path refused the
  pull and blamed untracked files. The check runs after the release is downloaded and verified and before it is
  copied over the node, and on a git checkout after the fetch and before the pull. The backup has already been taken.

- **A node says when a new version is out.** Once a day the node asks planetai.fab.city which
  version is current. When a newer one is out, the page's header says so ("PLANETAI v0.75.8 is out · on the
  node: planetai update"), `planetai doctor` shows it as an amber line, and Telegram says it once per version,
  after quiet hours. Nothing is installed: `planetai update` stays the household's to run, and it backs up
  first. The request carries nothing about the house, but it shows this house's internet address to Fab
  City's host, so it is a setting under Set up → Sharing, `UPDATE_CHECK`, on by default. `off` means the node
  never asks. A node with no route out stays quiet and is not reported as broken. The Spanish and Bahasa
  message has not yet been read by a native speaker.
- **The FAB26 experiment has a page.** `docs/FAB26_EXPERIMENT.md` is the participant-facing
  instructions for the October–December workshop cohort experiment: the two all-hands calls, the biweekly
  check-in through the experiment bot (@planetai_exp_bot), the build track, and a section for the workshop
  sensor kit (XIAO ESP32-S3 + Wio-SX1262, Grove shield, BME680, HM3001) with the Making Sense Bali enclosure
  link and the warning that stock Meshtastic firmware reads the BME680 but not the HM3001.

- **Two command hints said nothing where they meant a word.** `planetai doctor` printed "a space after = makes
  the shell run the value, and a  after it hands the container the comment": the `#` was in backticks inside
  double quotes, so bash ran it as a command. `planetai agent` printed "note: command not found" the same way.
  Both are escaped now, and a search found no others.
- **A test no longer writes its git identity into the checkout it runs from.** `tests/test_ship_gate.sh` set a
  placeholder author after a `cd` it never checked; when the `cd` failed, the placeholder landed in the real
  repository's settings. The tests now take their identity from the environment and never write git config,
  and the suite checks the invoking repository's identity is unchanged.

## v0.75.8 — 2026-09-29 — Set up in eight tabs, and an ask pane that answers faster

*Set up is regrouped into the eight things you do when you set a node up, with every secret in one tab and each
pack's settings in its own card. The ask pane has its own surface, shows the node working while it answers, and
a question that needs a tool answers in seconds and counts right. Also: two dashboard bugs node #1 showed.*

- **The pane is its own surface, and its questions turn.** Everything the node says in the ask
  pane now sits on one grey surface: its answers, learn's quotes, and the globe while it works. The page's
  paper is only ever the data. It is a neutral, not a colour, because every colour on the page already means
  something about the data. Errors in the pane are ink beside a red rule, not red text, which was too faint
  to read. The three questions under the thread come from a bigger pool now, still written by the node from
  tonight's figures. After the three it opens with come the other issues, the two newest other open alerts,
  and each other issue's line. A new three shows each time the pane opens and after each answer, never one
  already asked. The new question's Bahasa and Spanish wording has not yet been read by a native speaker.
- **The pane shows the node working, and the loading screen fits a phone.** While the node works on
  an answer, the pane draws the loading screen's globe, small and turning, with which model was asked and how
  many seconds it has been. Each read the model makes appears as it finishes, not with the answer at the end;
  if a model fails after reading, the next one starts from nothing (`retry` in the stream). The loading screen
  says **PLANETAI loading**. On a phone and on any portrait screen, its list of reads was drawn over the bottom
  of the globe's frame, and on a phone the globe ran into its own caption. Now they stack cleanly.
- **Leaving learn closes what learn opened.** Turning learn off left its card in the ask pane,
  over a page that no longer drew the mark it quoted. Now the card goes, and the pane closes if learn opened
  it. A pane you opened yourself stays open with your conversation. The card itself sits on a grey panel,
  not in an ink frame, so it no longer reads as one more reading.
- **Set up is eight tabs, in the order you set a node up.** It was nine tabs in the code's own order:
  the tokens were in three of them, the settings for how the page looks sat beside the ones that decide who may
  read the node, and three pack settings appeared twice. Now: **Basics** (what this place watches, its kind,
  language, how the page opens, and its name, city, position and time zone read-only), **Sources**, **Alerts**,
  **Model**, **Packs** (one card per pack, with its own settings inside), **Keys** (every secret), **Sharing**
  (everything that reaches beyond this machine) and **System** (tuning numbers, and what is read once at
  start). There is no Bootstrap tab: those rows are read-only in Basics and System. `planetai config` walks
  the same groups in the same order. Nothing is renamed and no value moves.
- **A question that needs a tool answers in seconds, and counts right.** On node #1, "how many
  alerts in the last 24 hours" took 165 seconds and answered 17 with 18 in the table. The tool took 73 ms. The
  model then spent one to three minutes thinking in hidden text, counting a list that had been cut at 8,000
  characters without saying so. Now the answer after a tool result is written without thinking; a result that
  had to be cut says so; and `alerts` takes `since_hours` and answers with the count itself (`GET
  /alerts?since_hours=24` too). The same holds for the Telegram bot, which asks through the same code.
- **Act and Network draw what node #1 has.** Act failed with "asks did not render" on a node whose ledger keeps
  alerts from before packs named their rules; those alerts now draw as rows of their own. Network said "Index
  cells 10 of 20" by counting rows, and a cell can carry several values: it counts cells now, 6 of 20 on node #1.

## v0.75.7 — 2026-09-28 — the ask pane starts again when you want it to

*The ask pane's conversation never ended: it survived reloads, grew to 40 messages, and sent 24 of them back
with every question. Now it has a new conversation button, starts fresh after half an hour, and sends only
the last three exchanges. Also: the source registry is synced again.*

- **The ask pane starts again when you want it to.** The conversation stayed in the tab with no way
  to end it: a reload kept it, it grew to 40 messages, and every question sent the last 24 back to the model, so
  answers got slower and vaguer the longer it ran, most of all on a small model on the node. Now **new
  conversation** in the pane's header clears it; a thread nobody has added to for half an hour starts fresh, so
  the next person at a wall screen does not inherit it; only the question and the three exchanges before it are
  sent; and the tools an answer read fold into one line, **read 3 things**, that opens on a press.
- **The source registry, synced to `awesome-fabcity-data` at `88f5c73`** (from `1d12b7b` in v0.75.6): still
  268 entries. BPS Bali's household spending per capita now carries its first review, usable with caveats for
  Bali.

## v0.75.6 — 2026-09-28 — `planetai run` sees what Set up saved

*v0.75.5 made a pack's own settings save from Set up, and the pack's adapter read them, but a pack script
started from the terminal still read `.env` alone. It reads the saved settings now. Also: the source registry
is synced again.*

- **`planetai run` sees what Set up saved.** A pack script started with `planetai run <pack>
  <script>` is a new process in the container, and it read only `.env`: `planetai run earth-engine verify`
  called `EE_PROJECT` missing while Set up held it. The command now loads the node's settings before the
  script starts, so a pack key saved from Set up, the CLI or an agent is in its environment, the same as for
  the pack's adapter. With the database down it falls back to `.env`, as before.
- **The source registry, synced to `awesome-fabcity-data` at `1d12b7b`** (from `2b00195` in v0.75.5): still
  268 entries. IBGE SIDRA now names Recife and São Paulo among the places it covers, and the schema has the
  fields an agent uses to file a source together with the person responsible for it.

## v0.75.5 — 2026-09-28 — a pack's own settings save from Set up, and reach the pack

*Set up drew each pack's settings and sent them, and the node refused every one. It takes them now, and the pack
has the new value at its next run with no restart. Also: the source registry moves from 238 entries to 268.*

- **A pack's own keys save from Set up, and the pack reads them.** Since v0.75.3 Set up sent
  `MAKE_ENABLED`, `PLACE_RADIUS_M` and the other keys a `pack.yaml` declares, and the node answered each with
  400 `is not a runtime setting`. Now `PUT /settings`, Set up and `planetai config set` accept any key an
  installed pack declares, switched on or not, and still refuse a key nothing declares. Packs read their keys
  from the environment, so the node puts the saved value there too, and the pack has it at its next run with
  no restart. That also makes a saved `COAST_MAX_KM`, `EE_PROJECT` or `EE_KEY_FILE` reach its pack, which it
  never did. Not yet: a script started with `planetai run <pack> <script>` still reads only `.env`.
- **The source registry, synced to `awesome-fabcity-data` at `2b00195`** (from `1010aa0`, 22 September): 268
  entries, 30 more than before, with one removed. Most of the new ones are measured production, exports and
  household spending for the pilots: Idescat's trade, industrial turnover and material flow accounts for
  Catalonia, Statistikamt Nord for Hamburg, BPS tables for Bali, INE Chile for Santiago, and São Paulo and
  Recife. There are also Eurostat's waste and air-freight tables, and a `places` field that says which pilot
  each entry covers. `environmental/city/cdp-iclei-track` is gone: it is non-commercial only, and nothing in
  the node read it.

## v0.75.4 — 2026-09-28 — the Earth Engine check runs to the end, and the docs match v0.75.3

*`planetai run earth-engine verify` died at its last step on a setup that was fine. It finishes now. Also: every
page a reader acts on was read against the code, and the README shows the node as it is.*

- **`earth-engine verify` checks the datasets the pack reads.** Step 6 still named the AlphaEarth embeddings,
  which left this pack for `earth` in v0.33.1, so a correct setup ended in `AttributeError` instead of "Setup is
  good". It now checks Dynamic World, Sentinel-2 and VIIRS, the three the adapter uses. The pack's description
  and README stop promising a land-change score. `tests/test_packs.py` runs `verify.py` end to end against a
  fake Earth Engine and fails if it names anything the adapter does not have.
- **The docs, read against v0.75.3.** The README opens on node #1's Now view and lists the ask pane, the three
  modes, paper and dark, the model choice and node #2 in Menorca. Across `docs/`, the site pages, the pack
  READMEs and `llms.txt`, what a reader would act on now matches the code: the ask pane's model ladder, Set up
  saving only edited fields, the signer fingerprint, the licence decision of 25 September. One gap found on the
  way is written down, not fixed: Set up sends pack keys that `PUT /settings` refuses.

## v0.75.3 — 2026-09-27 — Set up saves what you changed, and nothing else

*Saving a Set up group used to write back every field in it, and in the packs group it wrote none of the
fields at all. Now a save sends exactly the fields somebody edited, in every group. Also: the node's lead
sentence now matches the programme page, and the docs say beta.*

- **Only what you changed is saved.** A save used to write back every field in the group, so a page opened
  earlier undid whatever the CLI, an agent or another screen had set since. On node #1 it put
  `AGENT_PREFER` back to `strongest` over a `private` chosen twenty minutes before, and the ask pane sent a
  question online. It also turned defaults into settings nobody chose. Now only an edited field is sent. If
  that same key changed on the node while the page was open, nothing is saved: the page says what the node
  holds now and who last changed it, and a second press replaces it. `GET /actions?stage=settings` reads that
  ledger.
- **The packs group saves its own settings.** Code packs could not be allowed (`PACKS_ALLOW_CODE`), and no
  pack's own keys could be set, from Set up: they were drawn, and a save sent only the pack switches. They
  are sent now. If you move a pack switch, it decides `PACKS_ENABLED`; otherwise the text field does, so an
  unrelated save no longer overwrites a list you typed.
- **One lead sentence.** The node now opens its docs, `/llms.txt` and the dashboard with the programme page's
  sentence: hyperlocal compute and intelligence for distributed production. `tools/check_site.py` fails if
  the two drift apart again.
- **Beta, where it still said alpha, and the licence on record.** `main` has been the beta channel since
  20 September, and every update is signed. The README, the docs, the install screen and llms.txt still said
  alpha. They now say beta, and they still say it is an experiment. Tomas's licence decision of 25 September is
  recorded in `docs/decisions/2026-09-25-licence.md`: AGPL-3.0-or-later once every contributor has consented,
  Apache-2.0 until then. `LICENSE` has not changed, and this release is Apache-2.0.

## v0.75.2 — 2026-09-26 — the ask pane answers from the model you choose, and says where it runs

*In v0.75 the pane only ever asked the small model on the node's own machine. It now asks the models Set up
names for the Telegram bot: a bigger one on a laptop on your network, or an online one if somebody here
chooses to, and every answer says which model gave it and where that model runs.*

- **One choice, under Set up → agent** (or `planetai config`), for the bot and the pane alike:
  `AGENT_REMOTE_URL` and `AGENT_REMOTE_MODEL` for a model on another machine of yours (Ollama on a laptop is
  `http://<laptop>.local:11434/v1`, with `OLLAMA_HOST=0.0.0.0` on the laptop), the `AGENT_ONLINE_*` keys for an
  online one, and `AGENT_PREFER` for the order. `private`, the default, never goes online.
- **The pane says where every answer came from.** The header names the model and `runs on this machine`,
  `runs on <host>, on your network` or `runs online at <host>`; when an online model is in the order it adds,
  in bold, that the question and the page's context leave your network. Each answer's ledger line names the
  model that gave it. When one does not answer the next is tried, and nothing the failed one produced reaches
  the page.
- **An online model is a choice to give up sovereignty over what is asked**, and the Set up help for
  `AGENT_PREFER` now says so for the pane too. What it would receive is the question and the page's own
  sentences and numbers: the pane removes positions, sensor names and ids before any model reads them.
- A node with no model of its own can answer from a laptop on its network: the pane no longer needs
  `planetai agent local` when a remote model is set.

## v0.75.1 — 2026-09-26 — the ask pane answers on a live node

*One fix. On v0.75 every question in the ask pane came back as "the node answered 500".*

- **A live node's timestamps are dates, not text.** The context the pane gives the model carries the open
  alerts, and on a running node their times arrive from the database as date objects that the JSON writer
  refused. The committed captures the tests replay hold the same times as text, so every test passed. The
  context and the answer stream now write dates as ISO text, and a test sends the route the live shape.
  Checked on node #1's own data, read-only: the context is built, and it carries none of its 31 sensor
  names or ids, nor its position.

## v0.75 — 2026-09-26 — the page draws what the node leads with, answers in three questions, and can be asked

*What your node measures did not change. The page did: the lead is drawn from whatever issue the node puts
first, simple mode is cut to what a person in the house asks, and a pane beside the page asks the node's own
model, on this machine, about what it shows. It reads, it changes nothing, and nothing asked there is kept.*

- **The lead draws the hero it is handed.** The numeral, its pictogram (or the issue's sign) and a rule
  under it all come from `issues[lead].hero` (v0.74), so the page no longer knows anything about air. The
  rule replaces the four meters in the lead: one line between the issue's own two ends, a dot per distance,
  and the line in red where the issue has one. Coast draws a rule with no line; land draws a date and no rule.
  The four distances in full stay in the matrix.
- **Simple is the three questions.** Is it fine, is anything changing, is there something to do. On Now it
  draws the lead with its plain sentence, the open alert with **I did this**, the ground with a one-line key,
  the node's own paragraph (`digest.simple`), and **also watched here**: press another issue to look at it,
  **back** to return to the node's pick. That choice is the reader's, kept until the page reloads. No ladder,
  no sections, no stage names; advanced is drawn exactly as before.
- **Ask the node.** A toggle right of the modes, or the foot on a phone, opens a pane that asks the model
  `planetai agent local` set up, on this machine only. It runs the read tools through `/mcp` as
  `dashboard-chat`; a setting change or an "I did this" it reaches for is a card the person presses, with the
  token the page already holds. Its context and every tool result carry no coordinate, sensor or station
  name, sensor id or `meta`. The thread lives in the browser tab and dies with it; the node writes no
  transcript, no row and no log line with a word in it. With no model, the pane searches the documentation
  and shows the two ways to give it a voice. New: `GET /ask/status`, `POST /ask`, `GET /docs/search`
  (`open` share level), `UI_ASK` (default `on`), `digest.prompts`. The app container can now reach Ollama on
  the host, like the agent container.
- **Learn lands in the pane.** The learn panel is gone. A pressed mark is a card in the pane's thread,
  quoting the documentation and citing its page by title; **next** walks the marks in the order the page
  draws them. Each mark carries two questions that become the pane's chips while its card is in focus.
- **New documentation page:** [Ask the node](docs/site/ask.md), 43 pages in all. `sharing.md` says what the
  pane never sends.

The Indonesian and Spanish words from v0.74 and this release (the plain line, the paragraph, the prompts,
the learn questions) are assistant-written and want a native reader.

## v0.74 — 2026-09-26 — the node says what leads, and why, in a shape any issue can fill

*A node release: nothing on the page moves yet. What changed is what `/issues` hands the page. Every issue
now says how it should be drawn when it leads, the node says which step of its rule picked the lead, and it
writes three new things in the household's words for the page to draw next release.*

- **The hero is a slot.** Each issue's `.yml` declares `hero:`: its sign and pictogram, which figure is the
  numeral, the rule under it (two ends, which distances sit on it, whether its line is drawn) and whether
  its stamp is a time or a date. The engine fills `issues[k].hero` with tonight's values. `make test`
  refuses a hero the page could not draw: a sign not in `signs.svg`, a numeral the issue does not have, a
  rule dot at a distance it lacks. An issue with no hero is watched and never leads.
- **`lead: {issue, by}`.** The same pick as `headline`, by the same rule (state, then what moved, then the
  order this place chose), and which of the three steps made it. The rule did not change.
- **Three things written in the household's words**, in English, Bahasa Indonesia and Spanish:
  `hero.plain`, one sentence of the other distances and the line; `hero.stamp`, when the numeral was read,
  or for land when the satellite looked and when it looks next; and `digest.simple`, a paragraph of three
  sentences (the house's own stations and the nearest others, the oldest open alert, how the last 30 days
  of asking went). The Indonesian and Spanish want a native reader.
- **The engine reads 30 days of act-level alerts.** It read the last 200 alerts of any level, which on
  node #1 reached back only ten days. It now reads every act-level alert of the last 30 days plus the last
  200 of anything. **The number of open alerts a node reports can rise**: an act-level alert from the last
  30 days that nobody answered now counts as open, where before it had fallen out of the read.
- **The headline tests run.** They sat below `sys.exit()` in `tests/test_issues_engine.py` from 18 Sep and
  never ran; they run now, with the no-hero case added.

## v0.73 — 2026-09-23 — the node says what it is for, and what it publishes is one press away

*What your node measures did not change. What changed is what it says about itself: why it exists, in
the programme page's words; where every number on its page came from, as a link you can open; and, for a
reader it does not know, nothing finer than the cell it stands in.*

- **The programme page is held to the node.** `tools/check_site.py` compares the site repo's
  `web/src/data.js` with this repository: the release it names, the pack counts by kind, the languages,
  the documentation's page count, ρ's label, and the purpose sentence, which must be the one
  `docs/site/introduction.md` carries (and the README, `llms.txt`, `AGENTS.md`, the dashboard and
  `/llms.txt` must quote). `make lint` runs it; `tools/release.sh` runs it with the version and refuses
  to tag while the page describes another release or a ρ read more than 30 days ago. It also fails when a
  retired word comes back in docs/site.
- **The node says what it is for.** The purpose the programme page leads with is now the lead of the
  documentation's introduction, and the README, `AGENTS.md`, `llms.txt`, `STYLE.md` and the dashboard
  quote it. Every view but the wall ends with a foot: that purpose, then the version and the doors a
  person or an agent needs (`GET /health`, `POST /mcp`, `/llms.txt`, the documentation, the programme).
  `/llms.txt` is a route of its own that answers at every sharing level and says nothing about the house,
  and `/health` carries `docs`, `mcp` and `llms`. ρ is named for what it counts: the share of act-level
  alerts somebody answered within 24 hours.
- **A stranger gets the cell, never the point.** A reader the node does not know (no token, not this
  machine) is handed the centre of the resolution-8 cell the node stands in, in `/health`, and for the
  household's own sensors in `/sensors` and `/stats`. `/export` carries the cell's centre for everyone,
  because that file is CC BY and meant to travel. This machine and a token keep three decimals, which is
  what the household's own plan is drawn from. `/health` says which
  it handed out (`position`), and the ground drops the house dot when it is the cell. `/stats` no longer
  hands out unrounded positions at `SHARE_LEVEL=open` (#113). **Exports already published keep their three
  decimals**: files under `exports/` written before this release are not rewritten, and anything that
  copied them has the finer position. The node directory, `registry.json`, names node #1 by its cell and
  the cell's centre instead of a point to seven decimals; the old figure stays in the repository's history.
- **One vocabulary with the programme page** (display only). What the node sends a person is an *alert*
  everywhere a person reads it, and one nobody has answered is an *open alert*. The resolution control is
  the *ladder* and each step a *rung*. The four distances are *house · street · ring · region*; Bahasa
  *rumah · jalan · sekitar · wilayah*, Spanish *casa · calle · alrededores · región*, both waiting for a
  native reader. Nothing a program reads changed: the wire keys `room`, `yard`, `ring` and `region`, every
  API field, id and class stay as they were, and captured fixtures keep the words they were captured
  with. `concepts.md` gains a "Words" table: the word, what it means, the key behind it, the word it retires.
- **Learn mode explains the whole page, not six dials.** It was 17 marks on one view; it is 44, every
  registered section carries at least one, and 22 of the 42 documentation pages are reachable from the
  node. The marks say why the node exists and what it publishes, and their `more` texts name the route
  each band reads. Back and Next walk the marks in the order the view drew them, and the panel cites a
  page by its title and section, not its path in the repository.
- **Every band says which routes it was drawn from.** The section contract gains `reads`, and all 24
  sections declare one. The shell prints them beside each band's title, small, in mono and in their own
  case, as links: `GET /effect`, `GET /issues`, `GET /actions`. `tools/check_ui.py` fails a section with no
  `reads` or one naming a route `app/main.py` does not define.
- **The figures band links the open data.** Under "Every figure on this page", one line: the day's export at
  `GET /export?day=…` (CC BY 4.0) and the days before it at `GET /exports`.
- **The registry band can be used, not only read.** The pin links to `awesome-fabcity-data` at that commit.
  The three counts the node computes per cell (#105) are on the band, added up over the cells the way
  `planetai sources` prints them: at `1010aa0`, 12 capable, 12 reviewed and 20 candidate across 19 cells.
  A line links to `GET /sources?status=live`, `?status=candidate`, `GET /cells` and the documentation's
  *Adding a source*. The licence row is unchanged. Its notes no longer describe an older pin, and the act
  kinds `repair` and `match` have words instead of bare tokens.
- **A refusal is the node's own sentence.** "I did this" and "Record the decision" print what the node
  wrote when it refuses: the whole DECISION_REQUIRED sentence on a 409 instead of "The node refused it
  (409)", the stage list on a 400, and a 401's `detail`, which the page used to drop. Before anybody
  presses, a line under both forms says what a browser on another device needs: the act token, which
  `planetai ui` prints and Set up → unlock holds. The 400 itself now names all three stages it accepts
  (`acknowledged, acted or decided`). The ledger's note "No stage for a decision yet" is gone: it has been
  false since the Decide card.
- **`stale` is a word, not an empty square.** `signs.svg` is the design layer's and has no sign for
  `stale`, so the pill drew a blank glyph beside the word. A provenance word the sprite has no sign for is
  now printed alone; the sign is owed by planetai-design.
- **The page and two alerts speak in their own voice.** The ground's notes give the page's reasons for
  the live bases instead of a person's; two air-quality alerts no longer say "I will tell you" in any of
  their three languages (and the one that promised a message when the outside air clears, which no rule
  sends, now says to keep shut until it does); the digest and the headline rule lose their em dashes.
- **The docs catch up with this release.** The reference is for v0.73. The ρ worked example is node #1's
  published figure of 19 September 2026: 29 of 137 act-level alerts answered, ρ 0.212, median 112
  minutes. The federation page and `registry.json` name node #1 `bayu-ungasan`. The gap notes this release
  closes (`/stats` positions, the ledger's decided note, the registry band's stale notes) are gone; the
  rest stand.
- **The docs site cannot fall behind the node again without a gate saying so.** It did: from v0.57 to
  v0.72.1, fifteen releases, `planetai.fab.city/docs` described a node nobody was running, and every
  check stayed green because none of them read `docs/site/`. Three changes. `tools/check_docs.py` now
  reads those pages for the commands, settings, paths and endpoints they name, like every other doc.
  `tools/build_docs.py --check`, in `make lint`, renders every page and fails on a NAV source that is
  gone, a page NAV never lists, a link to no page and an anchor to no heading; CI installs `markdown` so
  it never skips there. And `tools/ship.sh` rebuilds the site from the commit it ships and commits it
  beside the tarball, so a release carries its own documentation. `SHIP_WITHOUT_DOCS=1` skips that on
  purpose; `release.sh` asks `ship.sh --check-docs` before it tags, for the same reason it asks about the
  signing key.
- **The pages the site takes as they are from `docs/` and the root were read against the code too**,
  after `docs/site/` was: UPDATING's rollback now rebuilds the image it rolls back to, STORAGE says the
  backup token comes from `planetai ui`, COVERAGE shows node #1's real cells, PACK_IDEAS marks the three
  that were built, and README, START_HERE, AGENTS, SPEC and ARCHITECTURE lose the counts and names that
  had gone stale (four views, fourteen packs, Set up → Model, `X-Agent` on every write tool).
- **The cell numbers say what a node could actually use.** A cell now carries three counts —
  `capable`, `reviewed`, `candidate` — counted from each source's `feeds_cells` rather than from
  where it happens to be filed, and no `deprecated`, `stale`, `paywalled` or `planned` source counts
  in any of them. On the 1010aa0 pin that is **12 capable, 12 reviewed and 20 candidate** across 238
  registered entries, where the old single number read 238 for everything.
  `planetai sources --cell 'Governance|City'` shows 32 filed and 4 backed.
  The node also now carries the registry's `reviews/` and `cells/` trees when a pin has them.
- **Every page of the documentation site was re-read against the code**, about 2,500 claims checked and
  some 80 corrected, and rewritten for the person building a node one part at a time: each page says
  which part it adds and what the node can do once it is there. The source registry has a page of its own.

**For testers.** Lucas (node #2, Menorca), Tomas Vivanco (node #3) and Lars (node #4): after `planetai
update`, every view but the wall ends with a foot naming what the node is for and linking `/health`,
`/llms.txt` and the documentation. The page reads *alert* where it said *ask*, *ladder* and *rung* for the
resolution control, and *house · street · ring · region* for the four distances; the alerts your node sends
keep their wording, except the two air-quality messages above. Switch to Learn and every section has a mark,
with Back and Next walking the page. Each band names the routes it read; press one to see the JSON. A
phone on your WiFi without a token, at `SHARE_LEVEL=open`, now sees the centre of your cell rather than
your point, and the ground draws no house dot for it: that is the change working, not a bug. Lucas, the
Spanish distances are *casa · calle · alrededores · región*; say which of them reads wrong.

## v0.72.1 — 2026-09-23 — three things the page was drawing wrong

*Nothing about what your node measures changed. Three things the page was drawing wrong, all of them
reported by Tomas reading v0.72 on node #1.*

- **The scale under the resolution rail ran backwards.** The eleven stops go from coarse to fine
  left to right — 172 km at one end, 10 m at the other — and the little rule underneath them, the one
  that shows where each grain truly falls, was labelled the other way round: 10 m at the left edge,
  100 km at the right. So every tick sat under the stop at the opposite end of the row, and anybody
  checking a grain against the scale read it backwards. The numbers were always right; only the axis
  was reversed.

- **Act was using half its width.** The whole stage — the open asks, every rule and its rings, the
  nearest place to get something made — was squeezed into the left half of the band while the right
  half sat empty from the top of the section to the bottom of it. It had been asking for two columns
  and only ever filling one. The rings now run the full width of the page, so a rule that has asked
  fifty times is two rows instead of four.

- **Every explanation at the bottom of the page was labelled with the same words.** Open the fold for
  the satellite and you got five paragraphs about five different things, each one headed "What the
  satellite says" — the fold's own title, said again, five times over. Scanning for the one you
  wanted told you nothing. Each of the 84 notes now names its own subject: "What orange means",
  "Compacting the covering", "Brightness matched across years".

Two of these could have come back without anybody noticing, so each has a check behind it now. The
visual gate reads the rendered scale and fails if it does not descend left to right — nothing else
could see that fault, because every box was the right size and only the direction was wrong. And
`make lint` now fails a note that has not been given its own label, which is how the third one would
have returned: one note at a time, with the page rendering perfectly either way.

## v0.72 — 2026-09-23 — the loop closes on the page, and the node starts to learn

- **The source registry is at `1010aa0`** — 238 entries, up from 229. Synced before this tag, as every
  release must be: nothing checks that the pin is current, so it goes stale silently.

## v0.71.1 — 2026-09-22 — the link to the asks led nowhere

- **Pressing "in 3 Act" gave you a blank page.** The lead counts your open asks and offers to take
  you to them. It took you to an empty screen instead. Every link that points at a part of the page
  did the same — the ones at the bottom that take you back to the section a note explains, all
  eleven of them. Your node's address bar is how this page remembers which view you are on, so a
  link to a *place on the page* looked to it like a view that does not exist, and it drew that.

  It now knows the difference between the six views and everywhere else, and a link to somewhere on
  the page scrolls there without redrawing anything — so you keep your place, your open folds and
  whatever you were reading. Reported by Tomas on node #1 within the hour of v0.71.

- **Your node can tell you which of your actions actually work.** Under Measure, per rule, over its
  whole record: how many times somebody acted, and how many of those were followed by the condition
  stopping. On node #1 it immediately found the thing it exists to find — **thirteen acts on the heat
  alert and not one of them cleared**, because heat does not stop because you acted, while ventilating
  cleared four of nine. A household that reads that stops pressing one button and starts opening
  windows, and nothing else on this page could ever have told them.

  Two honest limits, both stated on the page. It says a condition *stopped* within 48 hours of
  somebody acting — never that the act stopped it; a window opened at nine and air that cleared by
  three may be the window or may be the night. And *how long* needs an indicator and a line to come
  back under, which only a rule that declares one has: the others fire on a relation ("inside is worse
  than outside"), where a number would be invented. Those say so rather than showing a zero.

- **Your node has started to learn the shape of your days.** Under Historical, a new section draws the
  day this place *usually* has: one line for inside, one for outside, hour by hour, averaged over
  every day your node has recorded. It is the first thing on this page that gets better the longer
  your node runs.

  On node #1, over 22 days, it found something worth knowing: **inside is worst around midday
  (16.1 µg/m³ against 7.7 outside) and outside is worst around six in the evening (14.3 against 9.4
  inside).** They do not peak together — so there are hours when opening a window helps and hours
  when it does the opposite. A single line averaging inside and outside would have hidden that
  completely.

  It refuses what it has not seen. A usual day needs a week behind it, so a node switched on
  yesterday is told how many more days it needs rather than shown an average of two. The week, the
  month and the year need two weeks, two months and a year, and your node decides which of those its
  own record supports. Asked for by Tomas.

- **Your node now says how often a decision came first, and can insist on one.** Every act in the
  ledger that had a decision recorded against the same ask beforehand says *decided first*, and the
  ledger's own line counts them: *"0 of 31 had a decision recorded first"* on node #1, which is true
  and is the honest starting point since deciding only became possible today.

  It is a measure and not a rule. Four of the five ways to record an act have no screen to decide
  on — a reply over the LoRa radio, the Telegram bot, the terminal, a script — and a node in a house
  should record *"I opened the window"* whether or not anybody deliberated first; demanding otherwise
  would make your node assert a deliberation that never happened. A node that acts for more than one
  household is a different case, and **`DECISION_REQUIRED`** under Set up → Node is where that
  community says so: turn it on and an act with no decision behind it is refused, whichever way it
  came in. Off by default. Proposed by Tomas, and this is the part of it that does not break the
  radio.

- **Decide has a decision in it.** The stage was named for it from the first sketch and carried three
  sections about grain, provenance and trust — at what resolution a thing may be said, never what to
  do about it. It now opens with the thing itself: what your node saw, **what your node suggests**,
  and somewhere to say what you decided.

  The suggestion is not new and not a model's. Every rule your node runs ends its message with a line
  beginning 👉 — *"Open a window or two and let it through. It clears faster than a purifier can
  catch it"* — written by whoever wrote the rule, in every language your node speaks. It was on the
  wire the whole time and the page was drawing only the first line, the symptom. Take its word and
  the box fills with your node's own sentence; or write your own. A rule with no recommendation says
  so, because this page does not invent advice about your air.

  **A decision moves nothing.** It does not close the ask, it does not enter ρ, it is not a stage in
  the funnel — your node keeps watching. What it changes is the record: a house that looked, decided
  and never managed it used to leave the same trace as one that never looked, which was none. When it
  is done, press *I did this* under Act. Asked for by Tomas, three times.

- **The six footprint cards under Decide are folded now.** Since the rail learned to say what one
  cell at a stop is worth, it carries the live version of the comparison those cards were making —
  and it moves when you turn the dial, which they never did. They keep what it does not have: the
  ground each covers, each source's own grain, how its covering was packed. One line above, the cards
  one press away.

- **You can see what was decided, and by whom.** Your node has recorded every answer anybody gave an
  alert since v0.21 — who, when, which ask, and the sentence they wrote — and the dashboard drew none
  of it. Node #1 had thirty-one answers on its own wire with twenty-three names in them, and the Act
  stage showed a count in a funnel and no account. There is now a ledger under the asks: newest
  first, behind one press.

  The sentences are treated as your node treats them. Who acted and when is published with the rest
  of the page; the note is not, because `GET /actions` answers a token or the machine itself — a note
  is your household's own words about what it did in its own house. Without a token the ledger says
  so and names the ask instead of the sentence. Reported by Tomas, who went looking for it on the Act
  stage and found nothing.

- **`planetai snapshot` no longer writes your household's notes into the file.** A snapshot is made
  to be sent — to a bug report, a design round, a repository — and it was capturing those sentences
  with the admin token and storing them verbatim, which walks around the very decision the node makes
  when it refuses them to a reader without one. They are removed now, and the file says how many were
  removed. Nothing in a replay reads them.

- **The loading animation kept still for two of its three seconds.** The glyph globe turns while
  your node has not answered and settles into your own cell when it does — and the turning fades out
  as it settles, over a fixed nine-tenths of a second. On a node that answers in a blink that meant
  it had finished moving before the first second was up, and then showed you a photograph for the
  rest of the hold. It now spreads the settle across whatever is left, so it is still moving when it
  goes. A node slower than the hold is not slowed down further. Reported by Tomas.

- **"I did this" does something now.** Every open ask has carried that button since this page
  shipped, and nothing was listening for it. The node has taken a closed loop since v0.21 — who
  acted, and a sentence in their own words — so every act on node #1 was recorded over Telegram, a
  terminal or curl, because the page you actually look at was the one surface that could not write
  one. Press it and it opens: your name, what you did, and Record it. The node takes it from there —
  it watches whether the rule goes quiet, and that is what the funnel's *measured* has always meant.

  It needs an act token, which is not a new rule: a browser is never treated as local, deliberately,
  because on a node whose Docker forwards through a VM the whole WiFi would arrive looking local.
  `planetai ui` prints the token and Set up holds it. Where the node refuses, the page now says the
  node's own reason rather than a guess.

- **The rail says what a grain is worth now, and the Decide cards stopped drawing something else.**
  The rail across the top is eleven stops and an edge length: it said which grain you were standing
  on and never what choosing it costs. Press *one cell here* in the key under it and it opens: three
  hexagons to true relative scale — the stop you are on, filled, against the one above and the one
  below — and a table of what each thing your node speaks for costs to cover at that grain, from the
  sea down to this room. Turn the dial with it open and the numbers move. At resolution 4 the sea
  takes five cells and your room takes one, and so does everything in between; that is the whole
  argument for grain, and nothing on the page had ever shown it.

  The six cards under *Whose word, over how much ground* each carried a drawing of their own
  footprint. Each one drew how the covering had been packed — a detail the striped bar on the same
  card already drew — beside a number counting cells at the rail's resolution, so the picture and
  the number were about different things and the picture did not move when the rail did. They are
  gone; the cards keep every number they had and the section is half the height. Reported by Tomas.

- **You can now see what your node was asked.** While the page waits for your node it draws what it
  is asking for, and how many milliseconds each answer took — your node's own speed, which is not
  shown anywhere else. On a healthy node that is over in a tenth of a second, so in practice nobody
  had ever seen it. It is held for three seconds now on a reload and when you press ↻. Not on the
  five-minute refresh, and not when a node that had stopped answering comes back — there you want
  the page, not the story of getting it. If you have asked your machine for less motion, there is no
  wait at all.

## v0.71 — 2026-09-22 — the page, rebuilt

*Your node's own page, taken apart and put back together. It needs nothing you do not already have:
update and it is there. Everything below is the same node saying the same things — what changed is
the order it says them in, and what it will no longer say.*

The dashboard has been taken apart and put back together. It is the same node saying the same things;
what changed is the order it says them in, and what it will no longer say.

- **It leads with how coarse the answer is, and then with the thing that matters.** The first
  instrument on the page is now a rail of eleven stops, one per grain the node knows — half a
  kilometre, five kilometres, a hundred and eighty — with the one you are standing on lit and a rule
  underneath showing where each truly falls. The stops that are coarse enough to leave your machine
  are textured, the ones finer than your node says where it is are struck through. Then the issue
  that matters, as a sentence, with its number beside it. Which issue that is, and why, is printed
  under it in your own language.

- **Every number sits beside what it is compared to, or it does not appear.** Ninety-odd figures on
  the page and not one of them is alone: the room against the line, the street against the room, the
  model against the street. Where there is nothing to compare a reading to, the page says so in
  words instead of drawing a bar that means nothing. Where a distance has no source at all, its
  place is left empty and the reason is written in it — "no kit on the wall outside", not a zero.

- **Three modes, and the third one teaches.** *Simple* is four sentences, one per stage, and the node
  writes all four. *Advanced* is the whole page. *Learn* is the whole page with a question mark at
  each part; press one and a panel quotes this node's own documentation for it, word for word, says
  which page the words came from, and walks you to the next. Seventeen marks. The quotes are built
  into the page, so learn mode works on a network with no way out to the internet.

- **Paper by day, dark on the wall.** The page is ink on paper by default and switches to the dark
  register from the header, and the wall is always dark because it is a screen in a room. Colour is
  argument and never decoration: blue means an H3 cell, green means a loop closed, red means a line
  crossed, orange means only the satellite knows. State is carried by weight, not colour, so it
  still reads if you cannot separate blue from grey, and it survives being printed.

- **It shows you what it asked of the world while you looked.** A section called *What this page
  asked of the world* counts it: the offline plan asks nothing, switching to satellite asks twelve
  times and tells that server which five kilometres of the planet you are looking at, and the node's
  own polls are counted separately because they happen whether or not anyone is at the screen. You
  can see the price of a map before you pay it.

- **You can change the order of the issues, and hide what you do not want.** *Arrange* is Now in
  another mode: each section grows three controls — move it within its stage, hide it, restore it —
  and Done saves the order to your node as `UI_LAYOUT`, for every screen in the house. The rail, the
  lead and the ground do not move, and the bar says so. To change which issues exist at all and in
  what order, that is `NODE_ISSUES` under Set up → Issues, most important first.

- **The wall says what it is before you read it.** A bar across the top: which node, which place,
  how open it is, how often the field turns, and what the numbers in it are. All of that used to be
  at the foot, which on a screen across a room is the last place you look. Four variables sit up
  there with it and the rest are one press away.

Also: the page no longer scrolls sideways on a phone, which it did by 85 px. Nothing moves on the
page that does not have a reading behind it, and everything stops if you have asked your machine for
less motion.

**The list of places to act got longer.** The registry this node carries is re-pinned — 225 sources
where there were 217, and sixteen of them now have code on this node that reads them where there
were fourteen. Sixteen are places to go rather than things to read: six directories of fab labs,
seven libraries of open designs, and four others. Your node shows what the registry wrote about each
one's licence and does not sort them into open or not on your behalf.

## v0.70 — 2026-09-22 — the node found you a workshop and never said so

Two things this node already knew and could not tell you. The interface redraw is still not in this
release.

- 2026-09-22 — **The nearest place to make or fix something has never once been mentioned, on any
  node.** Since v0.65 a node with the `make` pack switched on keeps the fab labs within
  `MAKE_RADIUS_KM` and is meant to end its report — and any ask it can answer — with one line:
  *Nearest place to make or fix something: …*

  The pack was doing its job. Our node has had Fab Lab Bali, 3.3 km away, on its books for days.
  What failed was the two places that ask the pack for its own wording: both went looking in
  `../packs`, and a node keeps its packs in `/app/packs`. Both were written to fail quietly, on the
  reasoning that a missing pack should never cost you a report — so the line was simply absent and
  nothing said why. On our node every open ask carried an empty `where`: all 94 of them.

  One function knows where a node's packs live now, and it is the one that already reads all of
  them. If you have the pack on, the line appears after this update. The report line has been
  missing since v0.65; the one on an ask has never worked since it arrived in v0.68.

- 2026-09-22 — **A saved snapshot was quietly dropping two of the land figures.** `planetai
  snapshot` copies everything your node is currently saying, so a problem can be looked at later or
  on somebody else's machine. It was not copying what the satellite says. Replaying that copy gave
  16 figures where the node itself had published 18 — the two missing being the comparison against
  the wider region and the credit line naming whose data it is.

  Nothing was wrong on the node; the record of it was short, which is worse, because a short record
  looks like a complete one. Snapshots carry it now. It is 10.6 kB against 465 kB for the rest, so
  nothing gets slower.
## v0.69 — 2026-09-21 — the last stage stops being a zero, and a refusal stops sending you in a circle

Two fixes to what the node says, and two to the machinery that is supposed to catch us saying it
wrong. The interface redraw is still not in this release.

- 2026-09-21 — **"Measured" was a stage nothing could ever reach.** Last release added the four
  stages an ask goes through — asked, acknowledged, acted, measured — and the last one read zero on
  every node in existence, including ones where people had been acting on alerts for months. Not
  because nobody checks their work: because there was no way to record it. The node accepted
  `acknowledged` and `acted` and nothing else, so `measured` could only ever be zero, on your node
  and on everyone's.

  It is worked out now instead of typed. Your node re-asks every rule on a cycle, so an alert that
  was acted on and then went quiet — the same rule, the same sensor, quiet for longer than that rule
  ever waits before asking again — is the thing having stopped being true. Nobody has to learn a new
  habit and it reads backwards through everything already in the ledger: our own node went from 0 to
  5 of 30 the moment it updated, having never recorded one.

  It says whether something worked, never how fast, so it is the one stage with no time beside it.
  And it is honest about the cases it cannot see: a rule that has been renamed or uninstalled can
  never ask again, so its silence proves nothing and does not count. Without that guard our node
  read 8 — three of them free, from two old test alerts and a rule that has since been renamed.

  On our node the heat alerts are 13 acted and 0 measured. Heat does not stop because you acted, and
  the page now says so rather than averaging it away.

- 2026-09-21 — **A refusal that told you to change a setting you had already changed.** When the
  node declines to answer something, it names the setting and offers to let you open sharing up. For
  most things that is the right advice. For a handful of them — the version, the backups — no
  sharing level opens them at all: they need a token from anywhere but the machine itself. Those
  refusals were still offering the setting, so you changed it, came back, and got the same refusal,
  now telling you to set it to what it already was.

  The message now only offers the setting when the setting would actually answer, and otherwise says
  a token is the only way in. The dashboard prints whatever your node said rather than its own copy
  of it, so the two can no longer drift apart.

- 2026-09-21 — **Our own tests stopped running on the build machine, and nobody noticed.** One test
  hands a JavaScript program to `node` as a command-line argument, and that program now includes
  every setting the node knows about. Linux refuses a single argument over 128 KB; macOS does not.
  Last release pushed it to 138 KB by adding the pack settings — so it kept passing on every
  developer's machine and stopped running on the build machine, with an error that said nothing
  about size. v0.68 went out with a red gate. The program goes in through the front door now, which
  has no such limit.

- 2026-09-21 — **And the release script waited for a verdict it never waited for.** It refuses to
  build when the checks have failed, and it refuses when they are still running. It did not refuse
  when they had not started yet — it said so and carried on — and since they start seconds after a
  push, that was the state every release was in. v0.68 was built and signed before its own failing
  check had finished. It now waits for that too.

## v0.68 — 2026-09-21 — what the node can say about itself, and what you can change

Six changes, all of them about what this node reports and what you can reach from Set up. Two of
them fix things that were simply not possible before. The interface redraw is still not in this
release; it ships on its own when it is finished.

- 2026-09-21 — **You can turn a pack on from Set up now.** A pack declares its own settings in its
  `pack.yaml` — how far the fab-lab pack looks, which snapshot it reads, whether it runs at all —
  and none of them ever reached the settings page. Not one. So the switch whose entire job is to
  turn a pack on was invisible, and the only way to touch any of it was to edit `.env` by hand.

  All of them are there now, in a Packs group, each with the explanation its pack wrote for it and
  the value it has if you never touch it. Including `MAKE_ENABLED`, which arrives with the sentence
  about the fab-lab directory not being openly licensed, because that is the sentence you should
  read before turning it on.

- 2026-09-21 — **Every setting says what it would be if you cleared it.** The page could tell you a
  value was the default; it could not tell you what the default was once you had changed it. Now
  every row carries both, so you can see what you are overriding.

- 2026-09-21 — **A fab lab is a place, and the page can finally say where it is.** With the `make`
  pack on, the node stores the labs near you — how far, what machines, which monthly snapshot it
  read. The page was being handed the name and nothing else, because the filter that hides your own
  sensors' hostnames and firmware was being applied to somebody else's public workshop as well.
  A lab publishes what a lab publishes; your own kit's network details are still cut.

  With it, the node now offers one sentence naming the nearest place you could get something made,
  in your own language — the pack writes it, and the page draws it under the ask it answers.

- 2026-09-21 — **How far your asks actually get.** Beside ρ, the node now counts them stage by
  stage: asked, acknowledged, acted, measured, with the usual wait between each. On our own node it
  reports 162 asked and 30 acted with none acknowledged first — which is a true thing about how this
  household works, and ρ alone could not show it. It is not a second ρ and will not agree with it:
  ρ asks whether anyone answered at all, this asks how far they went.

- 2026-09-21 — **How far back your record goes.** `GET /reach` says, per kind of source, when the
  oldest hourly reading is. On our node: the satellite record reaches 3,720 days, the models 447,
  and the sensors in the house 20. The Historical view draws those on one page and has never said
  they are different lengths of line.

- 2026-09-21 — **A pack with a broken `pack.yaml` says so.** It used to lose every setting it
  declared and the only symptom was a pack that seemed not to be installed. It is in the log now.

## v0.67 — 2026-09-21 — the node says more about itself, and says it correctly

Four changes, all of them about what this node reports rather than how the page draws it. Nothing
here needs you to do anything; two of them change numbers you may have written down.

The interface redraw is NOT in this release. It is still being built, and per `docs/NEXT_RELEASE.md`
it ships on its own when it is finished — so if you are running this, you have a node that answers
better and the page you already had.

- 2026-09-21 — **A snapshot you send us can be looked at again.** `planetai snapshot` writes one JSON
  of everything your node answers. Somebody working on the page opens it with `?fixture=<name>` and
  sees your node on their own screen — it is how a bug you report gets reproduced without anybody
  touching your machine. That has been broken for a while, and nothing said so.

  The fixture is drawn by the real engine, which reads five tables. The snapshot fetched three.
  `actions` — what a person did about an alert, and the note they wrote — and `readings_1h` — the
  hourly means every chart is drawn from — are not endpoints, so they were never captured. A missing
  table was then read as an empty one. The snapshot opened, drew a page, and showed no act ledger, no
  stages, no series and no barcode, exactly as if your node had none of those things.

  Now the node answers `GET /actions`, the hourly means are read off `/aggregates`, and `/alerts` is
  asked for the 200 rows the engine itself uses instead of 50. A snapshot still missing a table now
  refuses and names it, rather than drawing a quiet, wrong page.

  `/actions` is on neither sharing allowlist on purpose: the note you write when you close an alert
  is your own words about your own house, so it answers a token or the machine itself and nothing
  else. Nothing about what a snapshot contains has otherwise changed, and it still carries no raw
  readings and no token.

  If you sent a snapshot before today, it was thinner than your node. A new one is worth taking.

- 2026-09-21 — **The node writes a four-sentence summary of itself.** `GET /issues` carries a new
  `digest`: one sentence for each of the four stages — what is read here, at what grain, what has
  been asked, and whether it worked — in English, Indonesian and Spanish. Every figure in them is
  one the page already draws somewhere further down; nothing new is measured and nothing is
  estimated.

  It is written by the node because a sentence about your data is a claim about your data, and that
  is not a browser's to make. The dashboard's simple mode draws these four and nothing else, so on a
  phone, or for a visitor, or on a morning when you want the answer rather than the working, this is
  the whole page.

  One thing it deliberately does not say: rho. rho is measured over its own window and has its own
  row further down the page. A second one computed here from a different window would be a second
  rho, and two of them disagreeing on one page is worse than one of them being absent. The Measure
  sentence reports the same ledger the Act stage shows, and says that is what it is.

- 2026-09-21 — **The four distances have one set of words again.** The page labelled a column
  `YARD` above a sentence reading "on the wall outside", and `RING` above "on the street". Two names
  for one place, on one screen — and only in English, because the Indonesian and Spanish had been
  given the household's words from the start and English had been left on the system's.

  The headings are now the nouns the sentences use: room, wall outside, street, model. Nothing about
  what is measured changes, and nothing about the wire changes either — `room/yard/ring/region` are
  still the keys `/issues` publishes and still what a pack's `where:` block overrides. Only the
  words you read are different. If you have a screenshot from last week, the columns are renamed in
  it and nothing else is.

- 2026-09-21 — **A cell's edge is measured now, not looked up.** Where the node told you how big one
  cell is, it printed that cell's real area next to a number out of a table — the average edge of
  every cell at that resolution, anywhere on Earth. At node #1 those describe different hexagons:
  the cell covers 639,778 m², which is 496 m to an edge, and the table said 531.

  `/health` had measured its own cell correctly all along, so the node disagreed with itself
  wherever both were shown. It now measures in all of them, and the number you will see at
  resolution 8 on node #1 is 497 m where it used to say 531. Nothing moved; the ruler was wrong.

  This is about 7% at every resolution, so any figure you have written down from the grain table,
  the plates or the radio row is a little smaller now.

## v0.66 — 2026-09-20 — a correction, shipped the same day as the mistake

One change, and it exists because v0.65 told you something untrue. That release said the fab-lab
pack was off until you turned it on; on a node that already allowed code packs it turned itself on
at update. We found it on our own node minutes after shipping, and this is the fix rather than a
note explaining it away.

If you updated to v0.65 and wanted the pack, set `MAKE_ENABLED=1` and `planetai restart`. If you did
not, this turns it off for you and `planetai doctor` will say so. Nothing else changes.

- 2026-09-20 — **`make` is now off until you say so, and v0.65's note about it was wrong.** That
  release said the fab-lab pack was off until you turned it on. On a node that already allowed code
  packs it turned itself on at update and read the directory before anyone chose it — because an
  empty `PACKS_ENABLED` means *every* pack is enabled. We found it on our own node minutes after
  shipping.

  It now has its own switch, `MAKE_ENABLED`, which ships as `0`. If you updated to v0.65 and want
  the pack, set `MAKE_ENABLED=1` and `planetai restart`. If you did not want it, this update turns
  it off for you and `planetai doctor` will say so.

  Why a pack gets its own switch when no other one does: the Fab Lab Network directory it reads is
  not openly licensed, and Fab City Foundation's decision to read it covers the Foundation and not
  you. A pack in that position should not start on its own.

## v0.65 — 2026-09-20 — the node can say where to go, not only what is wrong

Two changes, one idea. The registry your node carries gains its first **act** sources — places to go
and designs to build, alongside the 209 that measure — and a new pack, `make`, turns the nearest of
them into a sentence: where the closest fab lab is and what it can do.

`make` is **off until you turn it on** (`PACKS_ALLOW_CODE=1`), and there is one thing to read before
you do. The Fab Lab Network directory it reads is not openly licensed: each lab keeps copyright in
its own record and no data licence is published. Fab City Foundation decided it may be read and took
responsibility for that — but that decision covers the Foundation, not you. `packs/make/README.md`
says so plainly, and if it matters where you are, leave the pack off. Everything else in this release
is inert until you do.

- 2026-09-20 — **your node can tell you where the nearest fab lab is.** A new pack, `make`, keeps the
  active fab labs within 50 km of you — their names, how far, and what each one can do — and the
  report ends with one line: "Nearest place to make or fix something: Fab Lab Bali, 17.2 km (laser
  cutting, 3D printing, CNC milling)." In English, Indonesian and Spanish, machine names included.

  **It is off unless you turn it on.** `make` runs code, so it needs `PACKS_ALLOW_CODE=1` like `coast`
  and `earth`. `planetai doctor` then shows how many labs are in your ring and which monthly snapshot
  they came from.

  **It stores places, not numbers.** No metric, no Index cell, no alert — a fab lab five kilometres
  away is not your node's measurement of anything, and the pack is built so it could not claim
  otherwise even by accident. It reads the Fab Foundation's own dated monthly snapshots by default,
  which you can pin with `MAKE_SNAPSHOT` so every node in a fleet answers identically.

  **Read `packs/make/README.md` before you enable it.** The Fab Lab Network directory is not openly
  licensed: each lab keeps copyright in its own record and no data licence is published. Fab City
  Foundation decided it may be read and took responsibility for that — but that decision covers the
  Foundation, not you. If that matters where you are, leave this pack off.

- 2026-09-20 — **your node now knows where people can go to make or fix something, not only
  what is wrong.** The registry it carries is re-pinned to `85a194c` and gains its first eight
  **act** sources — eight of 217, alongside the 209 that measure. `planetai sources` lists them
  like any other: two directories of fab labs, five libraries of open designs, and the list of
  pledged Fab Cities. Nothing here reads them yet, so nothing on your node changes today; this
  is the shelf being stocked before anything is taken off it.

  Worth knowing what they say about themselves, because the answers are uneven. Three carry a
  clear open licence — Appropedia, OSHWA and Things That Work. Five do not, including the Fab
  Lab Network directory itself, and each says so in its own entry rather than leaving a reader
  to assume. `planetai sources --json` carries the licence text if you want to read it.

## v0.64 — 2026-09-20 — the node stops repeating a claim it could not check

One change, and a small one. v0.63 went out this morning carrying four large ones at once and said so;
this is the opposite kind of release, and deliberately so — if something comes back wrong after it,
there is exactly one candidate.

- 2026-09-20 — **`planetai sources` now names the code that reads a source, instead of the word
  "wired".** v0.63 shipped the registry at `9303adc`, where `adapter` — a string like `core:ckan` or
  `pack:coast` — replaced a boolean typed by hand in another repository. This is the node catching up
  to it. The last column of `planetai sources` prints that string, which tells you where to start
  reading rather than only that somebody got there first, and nothing here reads the old boolean any
  more: not a `/cells` row, not `GET /sources?wired=`, not the CLI. The `wired` filter keeps its name,
  so anything you scripted against it still works.

  **Twelve rows change, and they change because the old answer was wrong.** 26 of the 209 entries were
  ticked `wired_in_planetai` by hand; 14 carry an `adapter` read out of the node's actual code. The
  twelve in between — the Atlas of Economic Complexity, GBIF, Metroverse, What a Waste and eight more —
  said something reads them and nothing does. They now say so. `GET /sources?wired=1` returns twelve
  fewer, and twelve `/cells` rows stop claiming an adapter they never had. That is the whole reason the
  boolean was replaced with a string somebody can check: a blank last column still means nobody has
  written an adapter for this one yet, and now it means it truthfully.

## v0.63 — 2026-09-20 — a Raspberry Pi can be a node, nothing leaves your network unasked, and the bot speaks Spanish

**This release carries more than one large change, and `docs/NEXT_RELEASE.md` rule 3 says it should not.**
Tomas shipped it knowing that. If your node comes back wrong after this update, the question "which one
was it" has four candidates and not one, so please say what you saw and `planetai doctor --json` will say
the rest. The four, in the order they are most likely to be noticed:

1. **the database image changed** — if your node is an Apple Silicon Mac, its database stops running
   under x86 translation for the first time;
2. **three languages** in every alert;
3. **the model on your node lost the ability to change your settings**, and `planetai agent local` stopped
   downloading several gigabytes without being asked;
4. **five documents gained a `schema` key**, which you will not see at all.

Everything below is one of those four.

- 2026-09-20 — the source registry is re-pinned to `9303adc`, still 209 entries. Upstream replaced a
  boolean nobody could check with `adapter` and `feeds_cells`, read from the node's own code rather than
  remembered, and the schema gained the fields to hold them. `planetai sources` and `GET /sources` answer
  from this. Eleven pack source ids still resolve.

- 2026-09-20 — **`planetai agent local` no longer downloads a model, and the model on your node can no
  longer change your settings.** Two changes, both in the same direction: the model is a guest on this
  machine, not a part of it.

  **Nothing is pulled unless you ask.** Setting up the local model used to fetch 2.5 GB — 5.2 GB on a
  16 GB machine — as part of the same command that installed it. It now prints what it recommends for
  your machine and its size, and stops: `planetai agent local pull qwen3.5:4b` does the downloading when
  you want it. The recommended tags move to `qwen3.5:4b` (3.4 GB) and `qwen3.5:9b` (6.6 GB) — both
  checked against Ollama's registry, both Apache-2.0. **Your node keeps the model it already has**; this
  changes what a new install recommends, not what an existing one runs. `docs/MODELS.md` is the new
  catalogue and its first line is that a node needs none of it.

  **The local model gets read and act.** It can read everything about your node and record that you acted
  on an alert. It can no longer change a setting, run a pack's code, or send you a report because it
  decided to. An agent *you* are driving — Claude Desktop over your tailnet — still has all twenty tools;
  the difference is that you are reading what it proposes. `planetai agent` prints every tool and which
  class it is in.

  **And it must use your words.** Recording that you acted used to accept the word "acted" as your
  explanation. It now needs what you actually said, and `/act 23` with no words asks you for them rather
  than inventing them. ρ — the share of alerts somebody answered — is built out of those sentences, and a
  model filling them in is a model measuring itself.
- 2026-09-19 — **the node's database image is now published for arm64, so a Raspberry Pi is no longer
  refused.** `postgis/postgis:16-3.4-alpine` is built for amd64 and nothing else, and that one fact is what
  the docs used to turn into "a Pi cannot be a node". The `db` service moves to
  `imresamu/postgis:16-3.4-alpine` — a docker-postgis co-maintainer's build of the same recipe, same Alpine
  base, same PostGIS 3.4, published for amd64 **and** arm64. **Your node updates straight through this**:
  same data directory, same Postgres 16, same libc, and it was tested both ways round — a database created
  by the old image opens on the new one with its tables, its geometry, its indexes and its text ordering
  intact. Nothing to do.

  **If your node is an Apple Silicon Mac, its database stops being emulated.** It has been running an
  x86 build under translation since the day it was installed. You may notice it is quicker; you should not
  notice anything else.

  Not yet true: nobody has run a node on a Pi, a Jetson or a reComputer. CI installs one end to end on
  arm64 every push, which proves the images resolve and the database comes up, and proves nothing about an
  SD card or a hot cupboard. `docs/HANDOFF_arm64.md` is the seven-day test for whoever goes first, and the
  short version is: 8 GB, and an SSD — never an SD card, which Postgres will kill inside a year.

  Also: `planetai preflight` stops failing on arm64 Linux, and the installer no longer installs Docker on
  a machine that already runs Podman — it prints the two commands that let Podman answer to `docker` and
  stops, because no node has been run on Podman and it would rather say so than pretend.
- 2026-09-19 — **five of the node's documents now say which document they are**, and nothing you will
  see changes. `GET /issues` (what your page draws), `GET /export` (the nightly open-data file that is
  pinned to IPFS forever), `GET /report/latest`, and the two hourly pushes a child node sends its parent
  each gain one key: `"schema": "issues-v0"`, `"export-v0"`, `"report-v0"`, `"aggregates-v0"`,
  `"events-v0"`. Until now only the Index cells carried a version and the rest were implicit.

  **Nothing stops working, in either direction.** A parent that has updated still accepts every push
  from a child that has not; a child that has updated still pushes to a parent that has not. A node
  reading a version it does not know processes the fields it recognises and writes one line in its log —
  it never refuses, because a parent one release behind refusing its children would stop a district's
  numbers and tell nobody. The same rule holds for your page: if it ever meets a version it does not
  know it prints one sentence and draws what it recognises, instead of going blank.

  One small fix alongside: `GET /report/latest` used to answer five keys when the node had no report yet
  and ten when it did, so anything reading it had to know which case it was in. It now answers the same
  keys either way, null until there is a report.

- 2026-09-19 — **a node that has never chosen a model preference now keeps everything on the network.**
  `AGENT_PREFER` shipped as `strongest`, which sends every question — and the 64 kB report bundle that
  goes with it: your numbers, your room names, your own sentences — to Anthropic's or OpenAI's API first
  and to the model on your own box last. It now ships as `private`, and a node with no value at all
  reads `private`. **Your node is unaffected if you ever chose one**, on the Model page or in `.env`; an
  update adds new keys and never rewrites one you hold. If you never chose, your node is now private and
  your morning brief comes from the local model — say `/model` to the bot to see the ladder, and set
  `strongest` or `fallback` on the Model page if that is what you want. Separately, the Reticulum bridge
  container is no longer handed the whole of `.env`: it reads eight variables and now receives eight,
  not every token and password the node holds.

- 2026-09-19 — the source registry is re-pinned to `c2d33f7`, still 209 entries. Six Seoul datasets
  that the city's portal now answers with a termination notice go from `live` to `deprecated`, and
  four sources that moved get their new addresses: the Atlas of Economic Complexity (Harvard moved
  it from CID to the Kennedy School, and its old API host no longer resolves at all), both Open
  Canada entries, and IHME GBD. `planetai sources` and `GET /sources` answer from this, so a node
  stops describing six dead datasets as live.

## v0.62 — 2026-09-19 — nothing you will see, and the reasons it exists anyway

**There is no change to your node's page, numbers or alerts in this release.** The one file in it
that a screen reads, `planetai-theme.css`, changed by two comment lines: the design repository closed
an open question about the rho row, so the header counts eleven open items instead of twelve. No
colour, size or rule moved. If your node looks different after this update, that is worth reporting,
because nothing here should have done it.

It exists because the site was eight commits behind `main` and a tester downloading in that state
gets an older node than the one the work is being done against. The eight are gates, tests and
documentation:

- The frozen design layer can be re-pinned again. The check that holds this repository's copy
  byte-identical to the design repository's could refuse a stale copy but could not accept a new one —
  it measured the new file against the pin it was replacing, which is the one comparison that cannot
  pass. Found within an hour of v0.61 by the first person who tried it.
- `tools/session.sh preflight` now lists the neighbouring worktrees on the same disk. Two sessions
  fixed that same one-line bug three minutes apart, each having checked every open pull request and
  every branch on the server and found nothing: the other's work was local and unpushed. Every
  question asked was a remote question about work that was not remote yet.
- `docs/NEXT_RELEASE.md` no longer asks anyone to rescue the September design work from one laptop.
  It was merged upstream days ago; the file had not been told.

## v0.61 — 2026-09-19 — the node carries the network's list of what can be measured, and four packs more to measure it with


*Staged together on purpose.* `docs/NEXT_RELEASE.md` asks that `app/static/*` and `packs/*` reach a
node in separate releases, so that "was it the page or the data" has one answer when something comes
back wrong. This release carries both: the satellite fix landed before the four packs did, and it
cannot be separated out now without reverting it. Tomas called it, knowing that. If a node reports
something odd after this update, that question has two candidates and not one — the dashboard change
is confined to the satellite section, which is where to look first.

- 2026-09-19 — the key your node checks an update against is published under the name `fabcity`, not
  an email address. `planetai version` prints it, and a refused update names it. v0.60's notes below
  say `release@planetai.fab.city`; that release never reached the site, and the name was settled
  before any key was issued, so `fabcity` is the only one that has ever signed anything.

- 2026-09-19 — your node now carries the network's registry of 209 data sources. `planetai sources`
  shows what is registered for your place and which of it your node already reads; a source with no
  `wired` beside it is one nobody has written an adapter for yet. `planetai doctor` says which
  snapshot you have. The list comes from `awesome-fabcity-data`, the whole network's, and it works
  with the node stopped and with the uplink down — it ships inside the node rather than being fetched.

- 2026-09-16 — new pack `season`: the other half of `nearby`. That one asks where the bad air is, across
  space; this asks whether the year has turned — the ring's last seven days against its own preceding
  sixty, paired per station so the archive's own growth from 2 stations to 79 cannot read as a change in
  the air. Thresholds measured over 177 days of the record, replayed in the test suite: one episode a
  season, not a weekly weather report. A data pack — two SQL rules and a script, no fetch.

- 2026-09-17 — new pack `xiaomi-air`: Xiaomi / Mi Home air purifiers read on the LAN (miio/MIoT) as indoor
  sensors — PM2.5, temp, humidity and filter life — plus a filter-low warning. Ships with MIoT mappings for
  the Elite (zhimi.airp.meb1) and 4 Compact (xiaomi.airp.cpa4), verified live on node #1.

- 2026-09-11 — the earth pack's cache is keyed on the place, not on the node's name.

**Renaming a node no longer re-downloads its square of the planet.** The earth pack's cache lives in
`out/earth/<NODE_NAME>/`, so when node #1 became `bayu-ungasan` the pack found an empty directory and
re-read all nine years of AlphaEarth embeddings: about 930 MB pulled for data already on the disk, and
555 MB under the old name that nothing reads. The name was never the right key — the embeddings describe
a *place*, and the same square is the same square whatever the machine is called. A directory is now
matched on what its `meta.json` says it holds: this point, within the tolerance a move already uses, at
this radius. A directory written under an earlier name is adopted as it stands; when several match, the
one named for the node wins, so nothing shifts under a live node. A real move still re-reads everything.

Nothing is deleted. `planetai run earth status` lists any directory under `out/earth/` that is not this
node's square, with its size and the point it was read around, and leaves it alone: nine years is an
expensive download, and removing half a gigabyte of a household's data is not the node's call.

- 2026-09-18 — the dashboard's satellite record plays again. The AlphaEarth years had no CSS of their
  own, so every year stacked at full width under the Sentinel strip instead of one at a time — a wall
  of squares — and the player's button and slider had been dead markup since the Phase 2 rewrite, five
  releases of controls that did nothing. The Sentinel strip is unchanged, byte for byte: four annual
  medians side by side are compared without moving the eye, which is what a strip is for.

- 2026-09-16 — new pack `thingdata`: a repair commons read as observations. It pages a
  thingdata-server's public API — things, guides, stories, relationships — and publishes five metrics
  as portal observations, two `Economic|City` cells, and one rule that fires when nothing has been
  written for a quarter. Idle unless `THINGDATA_INSTANCES` names one.

## v0.60 — 2026-09-18 — an update has to say who built it, and a node that refuses one is doing its job

Every node in this network has been taking code from one Cloudflare bucket on trust. `install` and
`update.sh` did check the tarball against a `SHA256` file — and that file is served from the same
place as the tarball. Whoever can write one writes the other, so the two agree because the same
person wrote both. What the check proved was that the download had not rotted in transit. What it
could not say, and printed "checksum verified" without saying, was who had put it there. One write
to `planetai.fab.city/node0/get` and every node takes it on its next `planetai update`.

**Updates are now signed.** The tarball is signed on the release machine with a key that is not on
the web server and has never been on it — `ssh-keygen -Y sign -n planetai-node`, an ed25519 key held
by the Foundation. Both stubs fetch `planetai-node.tar.gz.sig` after the checksum and verify it with
`ssh-keygen -Y verify` against one published signer, `release@planetai.fab.city`. That is OpenSSH
8.2, which macOS 13 and Debian 11 both ship; a machine without `ssh-keygen` is refused with the
`apt-get` and `pacman` line that installs it, the way a machine without `shasum` already was.

**If a node refuses an update, that is the node doing its job.** It means the download was not signed
by the key that node trusts, and nothing on the machine changed — the check sits in front of the
extract, which is the first thing there that touches anything. The right response is to stop and say
so, not to look for a way past it. `docs/UPDATING.md` has the four things it can print and what each
one means; `SECURITY.md` is where to say it.

**The public key is public on purpose.** `tools/allowed_signers` carries it, and so do `install`,
`update.sh` and `bin/planetai` — four copies, gated byte-identical by the test, because the first two
run before there is a tarball to read a file out of, and reading the key from the tarball is the
download vouching for itself. `planetai version` now prints the fingerprint the node trusts, so it
can be compared against `SECURITY.md` from a machine that is not the node. `planetai doctor` gets a
row saying whether the last update was verified.

**And the site is now a mirror rather than the source.** Every release also goes to a GitHub Release,
the same bytes with the same signature, where who published it and when is recorded and cannot be
quietly rewritten. A node reads either with one variable — `PLANETAI_GET`, because the site serves
the three files under `/get` and a release serves them flat. `install-smoke.yml` installs from a
mirror on every push, then tampers with that mirror the way somebody with write access actually
would — changing the tarball *and* rewriting its checksum to agree — and asserts the install refuses
and unpacks nothing.

Nodes older than this release update through it untouched: the first signed release still publishes
`SHA256`, and a v0.59 node knows nothing about signatures and does not need to.

The key does not exist yet, and could not be made here — a private key an agent generated is a
private key that was in a transcript. Until it is issued, the four copies carry a placeholder,
`tools/release.sh` refuses to sign against it, and a node carrying it refuses every tarball. That is
the safe direction to fail in. `docs/HANDOFF_signing.md` is the one screen that ends it.

## v0.59 — 2026-09-18 — the dial belongs to Now, and the hero leads with what moved

*Written from the tag's own message; the tag is the record of what a tester received.*

THE SCALE BAR was drawn under every view's header. On Now it is the control the page is built
around — the ground, the station groups, the claims and the grain all re-file when it turns. On
Network, Historical and Set up nothing answered to it: a control that looked live and did nothing.

Arrange keeps it, and that is not an exception but the same rule: Arrange draws Now's own sections
through the same list, so it is Now in another mode. Taking the dial off it left seven of those
sections pointing at a control that was not on the page — found by walking every view and listing
every link whose target was missing, which is also how the four dead ones below were found.

Four links that named something not on the page go with it, three of them made by this year's own
view splits: the dial's link out on Network still named the satellite, which moved to Historical two
releases ago; hardware named the stations, which stayed on Now; trust named hardware, which stayed
on Network. Six such links shipped in v0.58; two remain, and both are older.

THE HERO ranked on state alone — act, notable, quiet, context, none — with the household's declared
order as the only tie-break, so two issues saying equally much were separated by alphabet. It now
leads with the one that has moved most.

State still wins outright, and that is the load-bearing half: something that needs doing cannot be
pushed down the page by something that merely moved a lot. Change is the tie-break inside a state,
and an exact tie still goes to the order this place chose under Set up.

The size was already being computed and thrown away — the room's last three hours against the three
before, the same six buckets the trend word has always used. It is kept as a proportion of each
issue's own recent level, because micrograms and degrees are not comparable quantities and ranking
them by absolute magnitude would be arithmetic on a category error; and unsigned, because a reading
halving is as much news as one doubling.

A test failed on this, correctly: under the new rule the committed capture is not a tie at all — air
moved seven per cent in three hours and heat did not move — so air leads whichever order is typed.
That is the asked-for behaviour, measured rather than assumed, and the case now asserts it.

And the page says the rule again, in all three languages, under the grain line. v0.53 printed it;
the modular page carried neither the words nor a place for them, so for five releases a reader had
no way to check why one issue was at the top. Changing a ranking without saying it would have been
worse than leaving it alone.
-----BEGIN SSH SIGNATURE-----
U1NIU0lHAAAAAQAAADMAAAALc3NoLWVkMjU1MTkAAAAg6sj9JsuGTUxul4FahlZkcY553E
R6Y2R38tGoYPP33zkAAAADZ2l0AAAAAAAAAAZzaGE1MTIAAABTAAAAC3NzaC1lZDI1NTE5
AAAAQEwLT7uS/P/Q/bIecrgitmwu00De/p6GNKgaqSztBAL6lVE+885D7Rgr0vAD1ChZsI
ovEHrhFbPie1OKCNy8hAw=
-----END SSH SIGNATURE-----

## v0.58 — 2026-09-18 — the readings keep up with the node again

*Written from the tag's own message; the tag is the record of what a tester received.*

v0.53 ended its boot with `setInterval(refresh, 20000)`. The Phase 2 rewrite did not carry it, and
from v0.54 to v0.57 the only repeating timer in the page was the wall stepping its own dial: the
boot fetched its routes once and never again, while the page went on showing its `live` pill and
its "as of" stamp over figures that had stopped moving the moment the tab opened. An unattended
wall screen was not merely stale; it was asserting a freshness it did not have.

The page asks again at the node's own rate — POLL_SECONDS, 300 s on node #1, clamped either side —
and asks only for what moves on that rate: the issues, the health, and ρ. A keeper's setting, a
satellite year and the plan are a reload's business, not a poll's.

A re-render is not a re-fetch, which was v0.56's lesson: this fetches, re-binds through the same
path the boot uses, and only then redraws. Scroll position and open folds survive, because a poll
arriving while somebody is reading a note must not close it. It holds off while the tab is hidden,
while an unsaved setting is being typed, and on a replayed fixture, which cannot change.

And a poll that does not come back leaves the figures where they are — they were true when they
were read — while the pill stops saying `live` and the stamp says how long the node has been
silent. That is the whole of what was wrong: not that the numbers were old, but that the page
claimed they were not.

One thing this nearly shipped, and the reason the release took as long as it did: innerHTML queues
an image load the instant the markup exists, so the first working version re-asked the tile server
for all twelve tiles on every poll — none of them from cache, though they carry a week's max-age.
At one poll per five minutes that is some three and a half thousand requests a day from every open
page, each telling that server which square of the planet this house is looking at. The rule since
Phase 2 is that a press may only ever reduce what leaves the house; a poll multiplying it by three
hundred breaks the same rule from the other side. A poll now keeps the ground it already has: the
drawing is a function of the cell, the resolution, the base and the register, and a poll touches
none of them. Twelve tiles on first load, none on every poll after.
-----BEGIN SSH SIGNATURE-----
U1NIU0lHAAAAAQAAADMAAAALc3NoLWVkMjU1MTkAAAAg6sj9JsuGTUxul4FahlZkcY553E
R6Y2R38tGoYPP33zkAAAADZ2l0AAAAAAAAAAZzaGE1MTIAAABTAAAAC3NzaC1lZDI1NTE5
AAAAQHCVMAmaRJbu4KJJI++tXphIuHh5BWRtRTO3tBzkh8wkLO92iAmale+PamimL9W+A1
2y1qU0popCNDNrQ5FsiQ8=
-----END SSH SIGNATURE-----

## v0.57 — 2026-09-16 — the node is drawn at work again, and the notes say what they are for

*Written from the tag's own message; the tag is the record of what a tester received.*

THE NETWORK FIGURE IS BACK, at the top of the Network view where it belongs: three things this node
reads flowing in along their wires, three things that leave flowing out along theirs, and the node
breathing in the middle. This is the second time it has been lost to a rewrite and restored — v0.53
was the first — and the reason is the same both times. Drawn still, it reads as a diagram of a
thing. Drawn moving, it reads as a thing at work.

Restored rather than rewritten. Three things had gone with it and all three come back from v0.53 as
they were: the twenty-two strings of copy in the three languages this node answers in, because a
figure that is English-only on a node delivering every sentence in Indonesian is the fault the
September review closed; the /sensors and /cells reads, because GET /issues publishes only stations
that carry a coordinate and "the models" therefore read zero on a node running five of them; and the
blanket reduced-motion rule, because the frozen layer zeroes its own motion tokens but the wire and
the dot carry literal durations and would have kept moving.

The rule that lets any of it move is unchanged: a motion with no datum behind it is deleted. A wire
with nothing travelling on it is drawn dashed and still — the link exists, the traffic does not. On
a node with no parent, "hourly means → nowhere yet" sits quiet while the other five carry.

Under prefers-reduced-motion every animation stops and the figure still draws. That is why this is
CSS and never SMIL: SMIL ignores the setting, which is what retired the original.

THE NOTES BAND said "Notes · why the page says what it says", in the same grey as a pack id, and
nothing told a reader that those folds explained the page they had just scrolled through. It now has
a title that names the thing and a sentence saying what it is for, that it follows the order of the
page, and that nobody needs it in order to read the page.
-----BEGIN SSH SIGNATURE-----
U1NIU0lHAAAAAQAAADMAAAALc3NoLWVkMjU1MTkAAAAg6sj9JsuGTUxul4FahlZkcY553E
R6Y2R38tGoYPP33zkAAAADZ2l0AAAAAAAAAAZzaGE1MTIAAABTAAAAC3NzaC1lZDI1NTE5
AAAAQJ32NgCqwBL39HgbWEqz/rjM95t+aVThXqX0ZaloEFXmT68+LzVF49lqim6irVUDai
urbf4cxPzhZDqX5Fg6kA4=
-----END SSH SIGNATURE-----

## v0.56 — 2026-09-16 — the dial works, and the page has somewhere to put history

*Written from the tag's own message; the tag is the record of what a tester received.*

v0.55 made a press a re-render instead of a document load. It measured beautifully — no requests,
five milliseconds — and it did nothing at all: pressing the dial or a cell moved the URL and left
the page exactly as it was.

`const Q = new URLSearchParams(location.search)` sat at module scope. That was right for as long as
every press reloaded the document, because the module ran again and the capture WAS the new URL.
Once presses stopped reloading, it froze at whatever the page was first opened with, and where()
answered with the opening cell and the opening resolution for the rest of the session. ctx.Q is
rebuilt on every render, which is why the variable selector, the base layer and "show all" kept
working and only the dial and the cells looked dead.

The verification was the worse fault. v0.55's press was proved by a script that compared the URL and
counted requests and never once compared what the page said. Two guards now: measure.mjs gained a
`press` command that opens the page, presses a stop and is red unless the grain line, the dial's own
on-stop and the grouping of stations into cells all change — it fails against v0.55 as shipped — and
a rule in the test suite forbids any module-scope read of location.search but the fixture's.

NETWORK IS THE NETWORK AGAIN. Satellite was put at the top of it in v0.54 and is moved out: a
Sentinel annual median is not a neighbour. Network is who this node hears over radio, who hears it,
and the hardware doing the hearing.

A HISTORICAL VIEW holds what has a date on it — the satellite record, and trust, because a sensor's
coverage over seven days is a history of that sensor rather than a fact about now.

THE WALL IS NO LONGER AIR-ONLY. It has always drawn whatever ?var= named; it never had a way to say
so from the wall. Nine variables on node #1, and nothing in the strip knows the word "air": a water
or soil pack's metric appears there as soon as a station reads it.

SET UP OFFERS WHAT `planetai config` OFFERS. The packs tab rendered pack switches and returned, so
PACKS_ENABLED and PACKS_ALLOW_CODE were in the CLI and nowhere in the dashboard. Every group now
renders every key the node declares — 54 across 8 groups — and two tabs take the node's own word for
their group, Model to Agent and The tree to Node, because that is the word the CLI prints.
-----BEGIN SSH SIGNATURE-----
U1NIU0lHAAAAAQAAADMAAAALc3NoLWVkMjU1MTkAAAAg6sj9JsuGTUxul4FahlZkcY553E
R6Y2R38tGoYPP33zkAAAADZ2l0AAAAAAAAAAZzaGE1MTIAAABTAAAAC3NzaC1lZDI1NTE5
AAAAQIvlueaT+OiHWRidN0vXVmIcC/rydiif9BMW2Lmd1IFGi6fwYtQmK4V77soZlqQt4z
D3t4wGUWZBGox20k+DuQE=
-----END SSH SIGNATURE-----

## v0.55 — 2026-09-16 — turning the dial stops reloading the page

*Written from the tag's own message; the tag is the record of what a tester received.*

Four things a keeper found on node #1 the day after v0.54, all four real.

Every control on this page is a query link — the dial, a cell, the variable selector, the base
layer, "show all" — and a browser answers `<a href="?…">` by throwing the page away: the document,
the script, the stylesheets, the frozen layer, the ground, then /issues, /health, /settings, /rho,
/trust, /forecast and /earth, all fetched again. Seconds of waiting on a LAN to be handed the same
readings and re-file them under different cells. Turning the dial was the slowest thing the page
did and it changed nothing but the filing.

None of it was needed. route() has always re-rendered from memory and fetched nothing; it is how
the view buttons already worked. Measured against node #1's own data: a dial press was 10 requests
and a full reload, and is now 0 requests and 5 ms. Scroll position is kept.

The wall had no way back. The click handler has listened for `.wall .exit` since the redesign was
ported and nothing ever drew one, so the wall was a room with the door painted on — no nav, usually
no browser chrome, and no way out but the keyboard.

The Phase 1 wireframes shipped into Set up: grey bars for text and outlined boxes for controls,
captioned "Drawn, not built", printed under the built version of the same view. Gone, with the three
outlined boxes in the sections list that were never wired to anything. Each section now says whether
it is drawing or has nothing here yet.

Satellite and street map looked lost. They are gated on MAP_TILES, off by default, and the strip
hid them rather than showing them refused. They are drawn now, struck through and not pressable,
each saying which reason applies — the setting, or the resolution. Still no link and still no tile
request: a press may only ever reduce what leaves the house.
-----BEGIN SSH SIGNATURE-----
U1NIU0lHAAAAAQAAADMAAAALc3NoLWVkMjU1MTkAAAAg6sj9JsuGTUxul4FahlZkcY553E
R6Y2R38tGoYPP33zkAAAADZ2l0AAAAAAAAAAZzaGE1MTIAAABTAAAAC3NzaC1lZDI1NTE5
AAAAQIUk6LJ4XR3mfokoFje5KooBrMhLvDBdIDUiTyFGbbCT833N02qcxH6S67idxUBWhn
2RY+hInPOsmou93hhtYg4=
-----END SSH SIGNATURE-----

## v0.54 — 2026-09-16 — the dashboard becomes a loop a pack can join

*Written from the tag's own message; the tag is the record of what a tester received.*

The page was one renderer that knew every card it would ever draw. It is now a shell, a contract
and twelve sections, ordered by the logic the node actually runs: observe, decide, act, measure.
A section declares its stage, what it needs and what it says; a pack that a node does not have is
simply not there, and a section whose data is missing prints one honest line instead of a blank.
Adding a feature is adding a file. Proposing it back is sending the file.

What the node now publishes, and the page draws rather than computes: each station's own
15-minute mean beside the fenced median, so the street's number and the thing that number hides
are both on the page; the H3 geometry, 209 published cells across eleven resolutions, with the six
declared footprints and their coverings; the asks ledger; and the mesh. GET /issues gained no
endpoint and no dependency the image did not already declare.

Live map tiles are off until a keeper turns them on in Set up, and a press may only ever reduce
what leaves the house: the node's own plan is always available, live tiles never past resolution 8.
A node that has not been sited says its distances are unknown instead of measuring them from a
point in the Gulf of Guinea.

The station list draws this node's own hardware and the nearest three of everybody else's, with a
line saying how many it is not drawing and a press that draws them all. STATIONS_SHOWN sets the
number; 0 lists every one.

Proved on a live node before release, which is where the last defect was found: the grain section
carried node #1's own flat run as a literal and crashed on every other node. It reads the table now.

Still true and not fixed here: the mono webfont 404s on a live node, because the frozen theme names
fonts/jetbrains-mono-latin.woff2 and the node serves it flat. That predates this release.
-----BEGIN SSH SIGNATURE-----
U1NIU0lHAAAAAQAAADMAAAALc3NoLWVkMjU1MTkAAAAg6sj9JsuGTUxul4FahlZkcY553E
R6Y2R38tGoYPP33zkAAAADZ2l0AAAAAAAAAAZzaGE1MTIAAABTAAAAC3NzaC1lZDI1NTE5
AAAAQFzenN5iyhmP7aLQvP/jXEJUgpX/lgntbxUrvb9po7FamYznGNH/HusJB4f9yE6Wr5
Ahb9gQ1URKgqZGhGG0YQ8=
-----END SSH SIGNATURE-----

## v0.53 — 2026-09-14 — the page stops telling a household things the node never said

The dashboard was walked as the five people who open it and then measured as a drawing. Both readings
are in this repo: `docs/design/UX_REVIEW_2026-09.md` is the walk, 64 findings each with a screenshot
and a rule; `docs/design/UX_REVIEW_2026-09_skeleton.md` is the geometry, 26 more, every number out of
one committed script. The four P0s below are one fault in four shapes — the page asserting something
the node had not written — and they were all on screens a household reads without a keeper beside it.

**The hero and the wall printed `17 MG/M³` where the node had written `17 µg/m³`.** `.k` carries
`text-transform:uppercase`, and on one character an uppercase is a translation: `µ` becomes `M`.
Milligrams for micrograms, a factor of a thousand, on the Now hero, on every issue band head and on
the wall at 1920 where nobody can walk over and check — two lines above a sentence that had the unit
right. A household had two numbers and nothing on the page said which to believe. The page may shout
its own words and never the node's: the node's prose now sits in a class that opts out, and
`check_ui.py` fails if a new uppercasing rule appears without someone looking at it.

**A gap in the day was drawn as a line through it.** Two places filtered nulls out of a series and
joined what was left, so a sensor offline from 08:00 to 15:00 became a six-hour ramp that rose across
the WHO line the page judges against and came back. The polyline carried 17 points where the series
had 24, and the `aria-label` still said "2 traces over 24 hours". The chart stated a reading nobody
took, and the reading it stated was a threshold crossing. A hole in a series is a hole in the line now.

**The dashboard was English-only on every node, including the ones speaking Bahasa and Spanish.**
`/issues` carried no `locale` key at any level, so `mkCtx`'s check was always false and the page
pinned to `en` — with `ALERT_LOCALE=es` set on the node and every sentence being delivered in three
languages everywhere else. The node publishes the household's language now and the page reads it. The
first render in Bahasa and Spanish then showed several hundred lines of `WORDS` that had never been
drawn at all.

**At `SHARE_LEVEL=off` the wall was a black 1920×1080 screen and the Network view a blank white one.**
`render()`'s refused branch wrote `#hero` and returned before it reached `#wallbox` or `#netbody`, and
`body.wallview` hides `#hero`. The surface nobody is standing at is the one that went dark: a household
walking past read a dead node where the node had a sentence explaining itself. Every view's mount draws
the refusal now, and the header pill stopped saying `live` over readings that were all refused.

**The wall was one viewport plus two paddings, so the word `stale` fell off the bottom of it.**
`index.html` carried `class="wall"` on the section *and* on the mount inside it, and `.wall` sets
`min-height:100vh` and a padding, so both applied: the document measured **1,208 px on a 1,080 px
screen** and 1,167 on a 900 px one. A wall does not scroll. At 1440 — a laptop on a shelf, the
commonest wall in the field — the ρ caption, the node name, `As of HH:MM` and **`stale`** were all
below the fold, so a household read a number and was never shown the word saying it was old. The class
is on the mount alone now: 1,080 at 1920, the viewport exactly. A structural rule in `check_ui.py`
fails if a viewport-height class ever lands on an element and its own ancestor again.

**The ledger's message column was 52 pixels wide on a phone.** Below 640 px the row drops to two
columns and only the last of its four children was placed, so the message — the sentence the node
wrote — auto-placed into the 52 px *timestamp* column while the button answering it got 288. Fourteen
rows, 94 line boxes of six to twelve characters. It is also why the page was the length it was: the
loop band was **34.6 % of the whole phone page**, the tallest band on it, against the headline air
band's 17.7 %. One declaration moved the message to the column it belongs in: 288 px, worst line 47
characters, and the page fell from 9,290 px to 7,978.

**Smaller, and each one measured rather than read off the stylesheet:** `.note` was the one prose class
with no measure and ran to **141 characters a line** in the Network band, against the 60–75 a reader can
follow, and now takes the 52ch `.field .help` already used at the same size; the header's shape was a
function of `NODE_NAME` and `NODE_CITY` rather than of the width, reflowing at 500 and 730 px on one
node and at 590, 1040 and 1230 on another and growing taller as the viewport widened on four of six
node shapes, and now reflows at 800 and 1210 on every one of them and never grows; and the header
stopped moving 25 px under the reader when `/health` answered, because `#headprov` ships empty and the
row it fills is reserved. **axe reports zero violations** on every view, every state and every width,
against 57 serious and 11 critical when the review was written.

**A node on Arch could not say where it is, so Sideband was told to connect to nowhere.** `lan_ip()`
read `hostname -I`, which is net-tools and therefore Debian and Ubuntu; Arch ships inetutils, whose
`hostname` rejects the flag outright. Five callers printed a blank where the address goes, and the one
that matters — the only instruction the reticulum command gives — has no placeholder. `ip route get` is
iproute2, which is on every Linux that can run Docker.

**A working reticulum start said it had failed.** `cmd_reticulum()` and the doctor both poll
`localhost:4243/health`, and compose published only 4242 — so the poll could never succeed, every clean
start ended in "the bridge did not come up", and the LXMF address and the Sideband instructions, which
are the whole point of the command, were never printed. One line publishes 4243 on loopback only. The
guard is general: every `localhost:<port>` the CLI talks to must be published by some compose service.

**The make pack is specified, not built.** `docs/proposals/make-pack.md` — what can be made near a node
and who nearby can make it. The endpoint, the storage, the coordinates and the one real OKH id were read
live from the hosted OHM instance on 12 September rather than inferred.

**Two things this release does not fix, and says so rather than closing them quietly.** The wall still
shows a model estimate in 120 px type and never names a source or says `model`, because `ANATOMY.wall`
carries no `chips`. And at 1440 the wall's content needs 1,052 px on a 900 px screen, so its footer is
still off the bottom there — the double padding is gone, the composition is not. Both are decisions
about the most designed surface in the product and belong to a design round rather than to a fix.
Sixteen P2s from the walk stay open and are listed in the review.

## v0.52 — 2026-09-13 — the drawings stop arguing with the numbers beside them

The September design audit's evidence moved out of this repo and its findings were closed one at a time.
When the release opened the dashboard answered three of the eight checks a design round is judged by
cleanly, with a fourth passing except for one hole. It answers **seven of eight** now, and the eighth is
a design round rather than a bug. `docs/design/LANGUAGE_GAP.md` is the whole reading, written against
`planetai-design`'s 34 tokens and 12 OPEN items.

**The Fab City Index drew four gauges, and on node #1's own numbers they were inverted.** Each pillar's
arc was `stroke-dasharray` of 0, 87 or 198 against a circumference of 263.9 — three constants chosen by a
boolean, not a measurement. Environmental has **5** sources and drew the 87 arc; Social and Governance have
**1** each and drew 198. Anyone comparing the rings read the best-covered pillar as the worst served, while
the number contradicting the ring sat inside it. Both `<circle>` elements are gone and the count is the
mark, which is what "counted, not sized" has meant since R1's ρ row.

**The hero's ground was the dark export, shown on paper.** `node-ground.svg` carried `data-variant="dark"`
and is loaded as an `<img>` — deliberately, since inlining leaks its `:root` into the page — so no CSS on
the page could reach it and its cells drew `#7FA5E8` on both registers. The layer's guard is explicit: that
blue is 2.29:1 on paper and may appear only in the dark block. It was not a stale asset. `ground.svg()`
already took a `variant` and defaulted to `"dark"`, and `GET /static/node-ground.svg` called it without one,
so the live path and the pre-setup fallback were both dark everywhere. The register is now a query parameter,
coerced to one of two literals before it reaches markup. What came back is not only a contrast number: at
2.29:1 the six neighbours and seven res-9 children had been invisible, and A4's ground was one ghost outline.

**No register-following token can label that green.** `--rings` is `#00A057` in both registers and does not
flip, so `var(--ink)` measures 5.26:1 on paper and 3.14:1 on the wall, and `var(--ground)` is the exact
mirror. The `#fff` on the two act buttons was 3.41:1 in both — under AA for 13px text. The label is now a
fifth page-local token, `--on-rings`, declared once and never redefined: **5.26:1 either way.**

**Smaller, and each one measured rather than read off the stylesheet:** the provenance glyph was the only
sign anywhere under `--sign-floor` (11px against 12, on the pair O7 and O12 record as 93.7–93.9% identical
*at* 12) and now names the token; the wall stopped taking the orange off the satellite's own year, which
bought 16.54:1 against 8.06:1 and spent the one thing orange means; and the network halo, which *is* the
reading pulse — O4 says the token's 3s was lifted from this very keyframe — had drifted to 5s and now reads
`--motion-reading-pulse`. 13 of the 34 layer tokens are referenced, up from 11.

**`tools/shots.py` asserted a refusal an open node can never give.** Its no-token pass tested that the page
says the node is not sharing. That is what `SHARE_LEVEL=off` promises; node #1 is `open`, set in the GUI and
overriding its own `.env`, and `open` promises the opposite. The pass printed ✗ on every live render of a node
behaving exactly as configured. It reads the level from `/settings` now, and forgives exactly one refusal —
`/place/geojson`, which needs a token at every level because it is the shape of a household's buildings.

**The release script was being rewritten while bash was running it.** `ship.sh` fast-forwards main, and that
pull replaces `tools/ship.sh` under the shell executing it; bash reads incrementally and resumes at a byte
offset inside different content. It is also why the label fix in v0.51 could not govern its own release.

**Two documents claimed things that were never read from the node they described.** `SPEC_custody.md` reported
node #1's version from a different machine's `VERSION` file and enumerated a `kind` set that a pack had already
added to; the invariant that actually carries the rule is written down now. And `peer-visibility.md` was not
lost — it was written into a session scratchpad under `/private/tmp` and recovered byte-identical.

**The audit's 207 files of evidence left this repo.** 135 MB of design-review PNG in a repo households install
from is 135 MB every node pulls to run a dashboard. They live in `planetai-design` at `design/audit/2026-09/`;
`git rm --cached` and a `.gitignore` line, no history rewrite, so every old link still resolves.

## v0.51 — 2026-09-13 — `events.cleared_at` was a promise the schema could not keep

v0.50 shipped the `events` table with a `cleared_at` column and nothing to put in it. A node has no
notion of an alert clearing — only of cooldowns — so no child could ever have sent one, and
`push_events()` never did. It was specified, built, and always NULL.

Dropped, with `ALTER TABLE events DROP COLUMN IF EXISTS cleared_at`, which is idempotent and safe on a
node that already applied v0.50: rehearsed on Postgres 16 over a populated v0.50 database, applied twice,
zero errors, the existing row untouched. It comes back the day an alert learns it has stopped holding,
and on that day it arrives with the code that writes it.

`tools/check_sql.py` reported that `ALTER` as non-idempotent. Its own comment has said "DROP … IF EXISTS
is idempotent on its own" since it was written, but only the `CONSTRAINT` spelling was ever matched.
`DROP COLUMN IF EXISTS` carries the same guarantee and is now accepted — and a genuinely bare
`ALTER TABLE … ADD COLUMN` is still refused, checked both ways.

## v0.50 — 2026-09-13 — custody: the roll-up path can say `live`, and ρ comes up with it

**`local` was doing two jobs and failing one of them.** It was written on 2 September for a node that was a
house; `kind` and the child push arrived the next day and nothing reconciled them. So `index.py::_buckets()`
counted `WHERE s.local`, a child's hourly means are stored `local=FALSE, kind='child'`, and a community node
aggregating ten homes counted **zero** — every cell downgraded to `partial`, forever. The roll-up path has
been built since v0.4.3 and could never say `live`.

**Custody is now `local OR kind='child'`, as a generated column in `init.sql`.** No adapter writes it, nothing
can make it disagree with `local` and `kind`, and it costs one word in a `WHERE` clause instead of the same
two-clause predicate in fifteen statements. `local` keeps its own meaning — this node's own instrument, here —
and `packs/nearby`'s ring, which asks `NOT s.local`, is untouched.

The rule is not `kind IN ('sensor','child')`, which was the obvious form and is wrong: Bali Air Dispatch
stations are written with no `kind`, so the default fills in `'sensor'`, and node #1 would have taken all 87 of
them into its own custody. `kind` answers how a number was produced, and a neighbour's station is produced
exactly the way ours is.

**A `kind='peer'` row reaches nothing, even written `local=TRUE`.** `tests/test_custody.py` builds node #1
twice from its own 7 September dump, once with a peer 40 m away, and asserts every cell and the custody count
answer identically. It was written before the fix and run failing first: 192 → 204 buckets, and `packs/heat`'s
`Social|Community` 0.0 → 4.0.

**`live` needs instruments, not only hours.** At least two in-custody sensors, across at least two children
where there are children. One child reporting is one household's kitchen, and a cell that says `live` off one
kitchen is the same lie as a model claiming it. A home node with one kit is untouched.

**A child's metrics keep their names.** They arrived as `<metric>_1h` and no pack SQL anywhere matched
`pm25_1h`, so even a fixed custody count would have found nothing to average. The cadence has a column that
`receive_aggregates` already writes (`PT1H`, on the child's sensor row) and that is where it belongs.

**ρ rolls up: `POST /events`.** One row per alert a child raised — rule, level, and the four timestamps — and
**no message text, no actor, no sensor id, no note**. "Shut the bedroom windows" names a room and says somebody
was home to be told. The child never sends a ratio either: a mean of ten ratios is not the ratio of the pooled
counts, so the parent computes ρ and a change to its definition reaches every child's history with nothing to
re-push. A node with no children reads an empty table and gets exactly the number it had.

**A lint gate that had crashed was reporting itself as skipped.** `make lint`'s rule check was
`… && check_rules.py || echo 'skipped'`, so a checker that threw looked like one that was never installed —
and sqlglot throws on `GENERATED ALWAYS AS (expr) STORED`, which Postgres has accepted since 12. The clause is
now an `if/then/else`, proven to exit non-zero on a crashing checker, and `check_rules` parses with
`ErrorLevel.IGNORE` the way it already did for this file's `DO` block and its `GRANT`s.

Decided in `docs/decisions/2026-09-10-custody.md`, argued in `docs/SPEC_custody.md`. §6 of that spec — moving
the Index publisher into this repo — is **not** in this release: its trigger is Bali publishing once, and Bali
has not.

## v0.49 — 2026-09-12 — Menorca, and the network figure moves again

**Menorca has a preset, and the first pack written for it.** `presets/menorca.env` carries Maó's
coordinates, `Europe/Madrid`, Spanish alerts and the Govern de les Illes Balears CKAN catalogue
(14,731 datasets; `/api/3/action/package_search?rows=0` tested 2026-09-12). It is the sixth preset and
the second outside the pilot four.

**`packs/posidonia` reads the sea temperature the coast pack already fetches against the temperature
at which Posidonia oceanica starts losing shoots.** Two `info` rules and one `Environmental|Bioregion`
cell, no adapter, no key, no new metric. The 28.4 °C line is Marbà & Duarte (2010), measured over six
years at Cabrera — 90 km from Menorca, which makes it the rare threshold in this repository that was
measured in the same water as the node reading it. A node outside the western Mediterranean must not
keep it: the plant is endemic and the number does not travel.

**`presets/` is mounted into the app container.** `planetai run earth similar` reads the pilot sites'
coordinates from `/app/presets/*.env`, which docker-compose never mounted, so the script has been
crashing with `FileNotFoundError: /app/presets/bali.env` on every node since it shipped. Found by
running it on the Menorca node.

**The wires carry what they carry.** The figure in the Network view — this node in the middle, what
it reads on the left, what leaves on the right — draws its wires again, each one marching its
dashes and carrying a dot the way the data goes, with a slow halo around the node. The older page
had this and the port to the renderer in v0.47 left it still, where it read as a diagram of an
instrument rather than an instrument.

Ink for what arrives and blue for what leaves, which is the same rule the rest of the page follows:
what leaves is hourly means, Index cells and ρ, and blue is what data looks like here.

A machine asking for less motion gets none of it: the animation is CSS rather than the SVG kind the
old page used, and CSS is the kind a browser can switch off on that request.

## v0.48 — 2026-09-12 — a node can say "I am here"

**Two nodes can now see each other without sharing anything.** A node with the Reticulum bridge can
announce its name and a *coarse* map cell — nothing else, no readings, no address — and collect the
same from any other node that does. Lucas's node in Menorca shows up on node #1 as a name, a
distance and when it was last heard, and neither node published a position: the distance is between
two cell centres, and the cell is rounded to about sixty kilometres across.

**It is off until you turn it on**, under Set up → Integrations, because `SHARE_LEVEL` governs what a
node answers when asked and this is a node speaking unprompted. How exact the announced cell is, is
the whole of the privacy decision and it is a setting: res 3 puts the announced centre 46 km from
node #1's actual house, res 5 puts it 1.5 km away, and nothing finer than res 6 can be set at all.

Nothing scans anything. A node learns of another two ways and both are somebody deciding: you name
it under Set up → The tree, or both nodes turn presence on and hear each other.

**And the Network view shows the radios this node is on.** The Network view carries the radio networks this node is on. **Meshtastic** needed nothing new
collected: every packet the gateway uplinks already becomes a sensor carrying its mesh id, its name
and its channel, so the mesh is a group-by over what the node has. **Reticulum** appears through a
new `reticulum` key on `/health`, filled on its own loop so a bridge that is down cannot turn the
node's health check into a timeout.

Worth knowing, because it is half of something: a node with the Reticulum bridge has always
announced itself as `planetai <node>` every thirty minutes, across every transport it has, with no
data attached. Nothing collects what it hears, so no node has ever seen another that way. The card
says that plainly instead of leaving it as an absence.

## v0.47 — 2026-09-12 — the Network view draws

**The Network tab was empty on every node since v0.45.** The renderer filled Now and the wall; the
four cards in that view were markup nothing ever wrote to. It draws again — this node in the wider
instrument, the Fab City Index pillars it can answer for, and the machine in the corner — and it
gains a card naming the other PLANETAI nodes this one knows about: a parent it reports to, anything
that reports to it, and the radio it listens on. Nothing scans for nodes; a household network is not
a thing to go knocking on. The card says how to link one instead.

The figure carries its own labels, so on a phone it is given as text rather than as a drawing three
pixels tall.

Also: four page classes were colliding with the frozen layer's binding classes, which bind on any
element and not only inside an SVG. The Index numbers were inheriting green and the ring card's box
plot a green stroke.

## v0.46 — 2026-09-12 — what node #1 showed

v0.45 went onto node #1 and the plan came back wrong, which is what looking at a real node is for.

**The plan of the kilometre is legible again.** Every road was drawing as a filled black wedge over
the buildings: an SVG polyline with no fill declared is filled BLACK, the programme layer has no
class for a road, and the page had not declared one. Node #1 has 530 roads. While it was being
found, `dashboard.css` turned out to re-declare all eleven of the layer's binding classes and to
have drifted on two of them — vegetation drew in ink, so every park and field was the same colour
as the buildings. The copies are gone and the layer governs again; the page declares only the road.

**The place band stopped saying "nothing mapped around this node yet"** next to a plan holding four
thousand three hundred shapes. It carries the two counts as signs instead: what OpenStreetMap has,
and what only a satellite has seen — 2,699 against 1,599 at one sign per 250.

**The hero said the same sentence three times.** The kicker, the why line and the ask strip all
printed the reason. The why line now names the line the reading is judged against and who set it;
the ask strip carries the alert's own words, so the hero says which reading asked for something
rather than repeating when it asked.

**One comparison per relation.** Node #1 has a yard, so three distances answered "level" and the
hero read "Level with the wall outside, level with the street, level with the model" — five lines of
headline. It reads "Level with the wall outside, the street and the model."

**The emoji stay in Telegram** (§3), in the ledger, the ask strip and the report the node last
wrote. Also: the ρ row says what it counts, coast's three readouts name their one source once
instead of three times, a rule id sits under its message instead of welded to the full stop, and the
trust card stopped pushing a phone sideways when a sensor has a long name.

## v0.45 — 2026-09-12 — the dashboard draws

The other half of the redesign: the page. Proven on a VM with node #1's satellite record and
reviewed by Tomas; node #1 gets it first, and testers get it on their next `planetai update`.
Nothing here has been seen on a wall in a room yet.

**The page is three files.** `app/static/index.html` is a skeleton with four view shells and no
logic; `app/static/dashboard.css` is how it is arranged; `app/static/dashboard.js` draws all of it.
One function fetches, one function writes to the DOM, and every component in between is
`(data, ctx) => string` drawn inside its own guard — a component that throws draws its own box and
names itself in the console, and nothing else on the page goes dark. What each band shows is a list
you can edit.

**The node computes; the page draws.** There is no mean, no median, no apparent temperature and no
threshold left in the page's JavaScript. The MAD fence that trimmed the ring's axis is
`issues.engine.fenced_median` now, and `tests/test_dashboard.py` fails if a `mad` or a `fence` comes
back.

**The frozen layer is on the node**: `planetai-theme.css` byte-identical to the design repo,
`tokens.css` adapted and saying so at its top, `signs.svg` and `kilometre-cells.json` copied. Funnel
Sans, Figtree and JetBrains Mono are self-hosted with their SIL OFL licences beside them and named
in `NOTICE`. Circular Std is deliberately absent: a commercial face that must not go into a public
tarball. `tools/check_theme.py` holds the three copied files to the design repo and is blocking in
`make lint`.

**The ring card shows the ring's shape, not a second median.** The Stack owns "the street". On live
data the two read 14.6 and 13.9 and both said the street, which is one page saying two things about
one quantity. The card now shows lowest, the middle half, highest, where this node sits on that, how
many stations and how far the nearest is.

**Five of `check_ui.py`'s rules had been passing for weeks while checking nothing**, and are fixed
here: four keyed on colour tokens the layer had replaced, the orange rule exempted every use of the
token it was guarding because the token is *called* `--satellite-only`, and the markup half of the
file was "whatever follows `</style>`", which the skeleton does not have. New rule 9 covers the
stylesheets: a `url()` naming a file nothing serves, or an `@import` to a CDN — a node serves this
page on a LAN that may have no route out.

**`tools/shots.py` renders the page in a browser**, which had not happened until now. The first run
was wrong in five ways, all fixed: every paragraph rendered in the browser's default serif on white
(nothing set a body font, because tokens.css puts it on a `body.fc` class this page does not carry);
the hero's and the plan's ground drew at 900 px and pushed the page sideways on a phone; Figures did
the same; `?fixture=` still reached for `/settings`; and the wall carried the header, five buttons
on a screen across a room.

**The node says more with what it already has.** Land gives its history: which two years it
compared, and how much has changed since the first year it holds. Heat has a direction, warming or
cooling, the way air always had. A quiet issue names the day's high and the hour it landed instead
of saying nothing. Every reason line says what happened rather than which state it is in.

**Colour follows the node, not the page.** The hero's monument numeral turns red when a line has
been crossed — and which lines this place has crossed is the node's judgement, not a comparison the
page makes because it happens to hold two numbers. The first live render put a red 17 beside the
words `AIR QUIET · NOTHING TO SAY`, which on a model-only node is every evening.

**Every sensor card carries its 24 hours**, as the page before this did. Nothing is fetched for it:
`/issues` already sends the hours per distance, and one request to `/sparks` covers the ring's
stations.

**The satellite record draws, and it did not before.** Both of them, side by side, told apart by
their provenance pill: the node's own AlphaEarth layer, which is a model's description of every
10 m pixel and says so, and Sentinel-2 imagery with its credits. Two things were stopping it. The
frames 403'd for a reader who had unlocked the page — they need the node's token and a browser will
not put a header on an `<img>` — and they are fetched properly now, once, and animated from memory,
which is also what keeps a 7 MB loop out of a twenty-second refresh.

**Set up and `planetai config` are one menu.** Same groups, same order, same words for where a value
came from. The order is the node's, declared once in `app/settings.py`, and `issues` leads it: it is
the one setting that says what this place is for. Before, the dashboard kept its own list — so a
group the node gained was visible in the terminal and unreachable in the browser, with nothing
saying so.

**A bug that had been there since the renderer landed: the page stopped updating after its first
render.** Five mount points were replaced by markup that did not carry their ids, so every refresh
after the first threw. Nothing static could see it and every screenshot was a first render; the
tool that takes them renders three times now.

**The Bahasa and Spanish in the page's own strings are assistant-written** and have not been read by
a native speaker, like the ones in `app/issues/*.yml`. PR #1 (`es-messages`) is the review channel.

## v0.44 — 2026-09-11 — the node knows its issues

Nothing on any screen has changed. This is the half of the dashboard redesign that lives on the node,
merged first so the page can be rewritten against a real endpoint rather than against a plan.

**`GET /issues`** answers, for each issue this place watches: which state it is in and why, the same
quantity at four distances (room · yard · ring · region) with a source and a provenance word for
each, the line it is judged against and where that line came from, the open asks and whether each is
still true, twenty-four hours of series, and one sentence in English, Bahasa and Spanish. `issues`
is the twentieth MCP tool and returns the same object. `/stack` in Telegram prints it.

**`NODE_ISSUES`** is the new setting: the order of the issues this node reports, most important
first. Your preset guessed from a map — change it. Its pane in Set up arrives with the dashboard.

**`planetai snapshot`** writes one JSON of every answer the node gives, so a screen that looks wrong
can be looked at by somebody who is not standing in front of it.

**The Bahasa and Spanish strings in `app/issues/*.yml` are assistant-written and have not been read
by a native speaker.** Every file says so at its top. Two of four beta testers read Spanish first;
these want a pass from someone who speaks it before they are on a wall.

Two numbers moved, and both were wrong before:

- The street is a **fenced** median now. One station reading 152 while the rest read 5 to 12 is
  either a fire in that lane or a broken sensor, and either way it was becoming "the neighbourhood".
  The fence was in the dashboard's JavaScript, drawing a chart axis; it is arithmetic and belongs on
  the node.
- An alert somebody merely **saw** no longer counts as one they answered. `/alerts.acted_at` is the
  earliest of *acknowledged* and *acted*, so a glance closed an ask. ρ itself was never affected —
  it has always measured both stages together, deliberately — but the page would have gone quiet on
  a tap.

And one number stopped being shown: land no longer falls back to Earth Engine's `land_change_score`,
retired in v0.33.1. `observations` keeps the latest row per source per metric forever, so a node that
ran that pack before the retirement still holds one, and showing it would put a year-old number on
the wall as this year's answer. With no record, land says how to fetch one.

## v0.44.2 — 2026-09-11 — an update refuses a download it could not verify

**`planetai update` could report success it did not have.** The tarball path trusted the download whenever
the checksum could not be checked, and both ways it could not be checked were silent: `shasum` is macOS's
name for the tool and Debian ships `sha256sum`, and any hiccup fetching `SHA256` skipped the check too.
Then the extract was the **left** operand of an `&&` list, which `set -e` exempts — so a truncated download
installed nothing and the run carried on to the schema step, the rebuild and the doctor, and ended
`>> updated. Nothing was lost` with **exit 0 and six green rows**. The only clue was `>> now v0.41.2`
printed after the update, naming the version it already had.

`install` fixed these same three paths some time ago and its comment records that it once did not. This is
those five lines, copied, plus `|| die` on the extract. `update.sh` now refuses, says which of the three
reasons it refused for, and installs nothing.

This matters most for a node nobody here can see. Node #2 in Menorca is a tarball install on Linux Mint,
and it is `update.sh`'s first run somewhere none of us can look at the screen.

**One thing this cannot fix retroactively:** the `update.sh` that runs is the one already on the node. A
node still on an older release runs the old, fail-open script for its next update, and gets this one only
afterwards. For that hop, run `planetai version` after updating — if the version has not changed, the
update silently did nothing.

## v0.44.1 — 2026-09-11 — config navigates, it does not march

`planetai config` walked all sixty-six settings in a fixed order and asked about each one. To change a
single value you answered sixty-five prompts you did not come for. That is `planetai setup` — the flow that
walks everything once, at install, and already has `--answers` for doing it unattended — wearing the wrong
hat.

Now it navigates. Categories first, then the settings in the one you picked, then the setting:

```
  config  bayu-ungasan          1 unsaved

    1  agent           7 settings
    2  alerts         12 settings
    3  bootstrap      16 settings · .env, needs a restart
    …
  number to open · s save and exit · q quit
```

`b` goes back, `q` leaves, `s` saves — from anywhere, at any depth. `planetai config --section alerts` goes
straight in.

**Changes are staged rather than written as you go**, because otherwise "cancel" cannot mean anything. A
touched setting shows as `warn → act` wherever it appears, the header counts what is unsaved, `s` writes
them all in one call, and `q` asks before throwing them away. A staged change to a key that needs a restart
offers the restart once, at the end, rather than after each edit.

## v0.44 — 2026-09-11 — planetai config, and whose project this is

*Shipped in the same tag as the issues layer above: v0.44 is `fc6e9f7`, which sits on top of it.*

**`planetai config` replaces "open .env in nano".** A node keeps its settings in two places — the database,
which the dashboard writes and which is live within 20 seconds, and `.env`, which the container reads once
at start — and the database wins. Reading `.env` therefore tells you what somebody typed once, not what the
node is doing. That is how `planetai ui` came to announce `SHARE_LEVEL=off` to a household whose wall was
drawing at `open`.

So every listing shows the value **in force**, where it came from, and says in red when `.env` holds
something else and is being ignored:

```
planetai config                    guided, section by section  (--section alerts for one group)
planetai config list               every setting, its value, and its source
planetai config get KEY            one setting, its help, and whether .env is being ignored for it
planetai config set KEY VALUE      the database for a runtime key, .env for a bootstrap one
planetai config unset KEY          back to .env, or to the built-in default
planetai config edit               the raw file in $EDITOR, which is what this command used to be
```

The schema, labels, help and accepted values all come from `settings.RUNTIME` through `GET /settings`, so
the command cannot drift from the code it configures: add a setting and it appears here. A value the node
refuses now quotes that setting's own help instead of failing silently — `runtime_set` swallowed a 400, so
a typo in a key with a fixed set of values looked exactly like the node being unreachable.

**The logo says whose project this is, and which version is talking.** Under the blue PLANETAI, both in the
CLI and in the installer: `a Fab City project · v0.44`. The installer shows the version it is about to
fetch, with a three-second timeout so an offline machine is told by the preflight rather than by a hang.
One `version()` resolver now serves the banner and `planetai version`; there were two, and two drift.

## v0.43.2 — 2026-09-11 — planetai ui said off while the wall was drawing

`planetai ui` read `SHARE_LEVEL` from `.env` and announced *"SHARE_LEVEL is off, so a screen on your network
gets the dashboard and the node's status and no readings"* to a household whose wall screen was, at that
moment, drawing every card. The database overlays `.env` for every key in `settings.RUNTIME`, and the
dashboard's Set up view writes to the database and never touches `.env` — so `.env` holds what somebody
typed once, not what the node is doing. Found on bayu-ungasan.

A new `setting()` in `bin/planetai` asks the node for the value in force and falls back to `.env` only when
the node is not answering, which is the one time `.env` is the better answer. Two older status lines had the
same fault and now use it too: the report rhythm `planetai report` prints, and the warning that Telegram is
unconfigured, which fired at a node configured through the dashboard.

`tests/test_share.py` gains the rule behind it: a **secret** may be read from `.env` and only from `.env`,
because `GET /settings` masks secrets at every level and the API cannot answer with one; every other runtime
setting must come from the node. That distinction is what separates the three bugs above from the token
reads that are correct as they are.

## v0.43.1 — 2026-09-10 — the node's own commands carry the node's own token

**Fixes what v0.43 broke for anyone who kept the default.** `SHARE_LEVEL=off` judges a request by the address
the container sees, and Docker publishes the port through its bridge — so the node's *own* machine arrives as a
LAN client, not as loopback. Four of the node's own callers asked their own API with no token and were refused:

- `planetai update`'s doctor printed `✗ views rebuilt` and `✗ packs loaded` and ended `xx something is off`, on a
  node that was polling, storing and answering perfectly. Found on bayu-ungasan within an hour of v0.43.
- `planetai status`, `alerts`, `packs`, `rho`, `sensors` and `report last` all read through one helper, `api()`,
  which carried no token — so all six returned nothing.
- `planetai act <id>`, the command the test alert teaches a household to type, could not record an action.

All four now send the node's own token, which is what it is for: `api()` takes `ADMIN_TOKEN`, `planetai act`
takes `ACT_TOKEN` and falls back to the admin one, and the doctor takes `ADMIN_TOKEN`. Nothing about what a
*stranger* may read has changed — v0.43's whole point is intact, and a node already set to `open` never saw any
of this.

`tests/test_share.py` grows the check that would have caught all four: every `curl` any shipped script makes to
this node's own API must either hit a path on the `off` allowlist or carry a token — including calls through a
helper, where the path is a variable and so could be anything.

## v0.43 — 2026-09-10 — a stranger on the WiFi

**A stranger on your network can no longer read your sensors' hostnames or the shape of your building.**
Until today anyone on the house WiFi could `curl` this node and get back
`{"host": "airgradient_84fce6.local", "firmware": "3.1.9"}` next to a room name and your position to five
decimals — 1.1 m, the doorway — and `/place/geojson` handed them every building footprint and road within
`PLACE_RADIUS_M` of the address. `SPEC.md §4` said no packet crossed a network boundary; the compose file
had been publishing 8080 on every interface since v0.1.

**What to set to get the wall screen working again.** The new `SHARE_LEVEL` defaults to `off`, which answers
a request with no token the dashboard, the node's status and the layout — and no readings. That is the safe
default, not the useful one: **set `SHARE_LEVEL` to `open` in the dashboard's Set up view** and every screen
and phone in the house reads the sensors again with no token, which is what most nodes want. Writes still
need one, at either level. A request *carrying* a token is unchanged at both levels and from anywhere, so the
NAS pulling `/backups`, Home Assistant and the agent's MCP surface keep working untouched — nothing about
where the node listens has changed. `/place/geojson` is the exception: the shape of your building needs a
token at every level, and the dashboard's plan card now says so instead of going blank.

`/health` rounds the node's position to three decimals — 110 m — for every caller at every level, which is
the rounding `/export` has always used and changes no answer a consumer computes. `/sensors` names its
columns instead of `SELECT *`, so the next column added to the table stays private until someone publishes
it on purpose, and for a caller with no token it drops `host`, `firmware`, `mesh_node`, `gateway`, `channel`,
`root_topic` and `topic` while keeping the provenance that makes a reading citable.

**Closing a loop from a phone** now uses `ACT_TOKEN`, a second weaker token `planetai ui` prints beside the
admin one: it records that someone acted and reads the sensors, and it cannot read a secret or change a
setting. On the machine the node runs on, `POST /actions` is open with no token as before. And
`?tolerance=0` on `/place/geojson`, which skipped simplification and returned an unsimplified kilometre
against a docstring promising a few hundred KB, is bounded — as is every other numeric parameter in all 44
routes, checked by an AST walk in `tests/test_share.py`.

Also: `docs/design/planetai-theme.css` holds the dashboard's `:root` tokens as a committed fixture, and
`tools/check_theme.py` reports when the page and the fixture have drifted apart, so a changed colour shows
up in a review rather than on a wall screen. Report-only, on purpose.

## v0.42 — 2026-09-10 — an agent arrives knowing where to start

**The installer rebuild is in.** `planetai remove` removes, and says what it could not; a disk that has
gone read-only is diagnosed with the kernel's own words instead of a guess about the drive; the daemon is
no longer called dead while it is answering; stopping means the socket too; and the release check answers
about main from whatever branch you are on. Those merged over the last two days and are the reason this
release exists at all.

**And the repository now tells an agent where to begin.** Everything agent-facing here was written for an
agent already inside a running node — the invariants, the nineteen tools, what not to break. The four
people who actually turn up with an agent are somewhere else: no node yet, a node that went quiet at 9pm,
a wish to hold the node's tools, a city wanting to publish cells. `AGENTS.md` opens with a routing table
to four skills in `skills/` that answer exactly those; `llms.txt` indexes every document; `.mcp.json`
wires a clone to a node with nothing secret in the file; a README paragraph is the one thing to paste to
your agent; and a pull-request template says a person is responsible for every change, whatever wrote it.

Why now: an agent given a list of invariants and no starting point improvises, and we have already merged
nothing and lost an afternoon to a contribution that was confidently shaped wrong. `tools/check_docs.py`
now refuses to build when a skill names a command or a path that does not exist, when `AGENTS.md` fails to
route to a skill that exists, or when `llms.txt` links to a file that does not — because a prompt nobody
lints rots faster than the docs it replaced.

## v0.41.2 — 2026-09-08 — the traces say what hour it is

**Every small trace now has a time under it, and tells you the exact hour when you hover.** They were shapes with
no axis before: a bump with no way to ask when it happened. `/sparks` was sending values with no timestamps at
all, so the page could not have drawn an axis even if it wanted to — it now sends the hour of every bucket
alongside them.

Hovering any point on a trace names the day, the hour and the reading with its unit. It works with a keyboard and
with a screen reader, which a tooltip that chases the mouse does not.

**The neighbours are separate cards again.** They were touching, which read as one block of text rather than one
card per sensor. The forecast steps had the same problem.

**One wild neighbour no longer flattens the picture.** Node #1's card read "5 to 152 µg/m³" this morning: one
station was reading 152 while the rest read 5 to 12, and the axis stretched to fit it until the box was a smear
against the left edge. The axis now ends past the neighbours rather than past the worst one, and a station beyond
it is drawn as its own mark at the edge and named in the sentence — either something is burning there or that
sensor is wrong, and both are worth saying.

That fence is not the textbook one. Tukey's 1.5 × IQR fails on a small ring: with three stations reading 5, 10
and 152, the 152 *is* the upper quartile. It uses median absolute deviation instead, which holds at three
stations. The case it is most careful about is the opposite one — when every station reads high **and agrees**,
that is smoke over the whole area, and nothing is pinned away. That is the reading a household most needs to see.

## v0.41.1 — 2026-09-08 — one card cannot take the others down

**If your satellite cards went blank after updating to v0.41, this is the fix.** Nothing was deleted: the land,
the plan and the year-over-year pictures were still in the database the whole time. They were not being drawn.

The dashboard paints every card inside one `try`, and its `catch` only writes "node not answering" in the corner.
So anything that threw while drawing an early card silently cost every card below it — and the satellite cards
are drawn last, after the ring and the forecast that v0.41 added in front of them. A node whose `/nearby` or
`/forecast` returned a shape the new code mishandled would lose the land and the plan with no error anywhere.

Each card is drawn inside its own guard now. A card that cannot be drawn says so in its own box, names itself in
the browser console, and leaves every other card alone. Checked by breaking the ring card on purpose and watching
the earth card, the plan, the world tiles and the forecast all still render.

No data changed, no schema changed, and no pack changed. If your satellite cards were blank, they come back on
this update with the history they already had.

## v0.41 — 2026-09-08 — is this me, or is this everywhere

**For testers: two new packs, both quiet until you configure them, and neither one claims to know your city.**
`nearby` answers the only question that changes what you do when the air is bad — is it *your* address or is it
everywhere. `forecast` says where the wind is coming from and when rain is expected, and never sends anything at
all. Update with `./update.sh` as usual. This build also carries v0.40's trust-pack fix, which was tagged on
7 September but never reached the download.

### `nearby` — the ring of sensors around you

One kit cannot tell a fire in the lane from a haze over the island. Other people's sensors can. The pack reads
the public stations around this node from Bali Air Dispatch — which the node has fetched since v0.11 — and adds
three rules:

- **`only_here`** (act) when your address is well above a ring that is not. Go outside and use your nose; if
  something is burning, report it. It also says the enclosure might need a look, because that is the other cause.
- **`everywhere`** (info) when the ring reads it too. There is no fire nearby to find, and moving will not help.
- **`alone`** — no message, never sent. It is the line in your report that says this reading speaks for this
  address and nothing else, because fewer than two neighbours are reporting.

Two cards: where you sit inside the range your neighbours are reading, and who those neighbours are with their
distances. **Bali only for now**, because the archive is. Outside Bali the pack sits idle and says so.

**Your own kit is not in your own ring.** The archive republishes Smart Citizen devices, and this node polls Smart
Citizen directly, so the same box could arrive twice and every comparison would be the node arguing with itself.
Four rules stop it: devices this node already polls, anything within 150 m of the node, `BAD_EXCLUDE` by hand, and
one device arriving under two networks' ids. **`planetai run nearby stations`** prints every station in the
archive with its distance and the reason it is in or out. Read it once.

**The ring is thin here, and the pack says so rather than implying coverage it does not have.** At node #1, after
exclusions: one neighbour within 5 km, three within 10, six within 15. `BAD_RADIUS_KM` now defaults to 15.

**No Index cell**, deliberately. `live` means measured here, and the ring is measured by other people through a
third-party aggregation.

### `forecast` — what is arriving, and when

Wind, rain, temperature, humidity and cloud for the next day, from **BMKG** where the node is in Indonesia and
**Open-Meteo** anywhere. It fetches; it does not predict.

**It cannot send you anything.** One rule, no message, no level, no cell — it gives your daily report one line and
stops. After 7 September we are not shipping a pack that can start talking about tomorrow.

Set `FORECAST_BMKG_ADM4` to your point's village code and run **`planetai run forecast verify`**: it prints which
province, regency, district and village that code actually is, and how far it is from your node. Node #1 is
`51.03.05.2002` — Ungasan, Kuta Selatan — 194 m away. Open-Meteo is **off by default**: its free tier is
non-commercial only, and that is your call, not ours. With both on, the node records how far apart they disagree
and tells you, because neither of them is the truth.

Every value is stored with how far ahead of its own forecast it is, so a forecast that has quietly stopped
refreshing can be told from one that is right.

### new settings

```
BAD_RADIUS_KM=15            # was 8
BAD_MIN_SEPARATION_M=150    # closer than this to the node and a station is assumed to be your own hardware
BAD_EXCLUDE=                # station ids that are yours and the other rules missed
BAD_INCLUDE_INDOOR=0        # stations the archive suspects are indoors are dropped
LOCAL_RADIUS_M=500          # was read by the code and documented nowhere
FORECAST_BMKG=1
FORECAST_BMKG_ADM4=
FORECAST_OPENMETEO=0
FORECAST_POLL_HOURS=6
```

### fixed while we were in here

- Stations the archive suspects are **indoors or malfunctioning** are no longer stored as outdoor references.
- **One device, one row.** The archive does not dedupe OpenAQ against AirGradient: 23 of its 87 stations arrive
  twice under two networks' ids at identical coordinates, which weighted half the ring double.
- The ring was scoped by "not local", which counted **your own kits beyond `LOCAL_RADIUS_M`** as neighbours.
- Three gates were wrong and could not have caught any of it: two extracted a database view by matching to the
  first semicolon, and a semicolon inside a comment truncated it; and the channel-role check read only the core's
  sources, so a pack could never declare its own channels even though the docs tell it to.

## v0.40 — 2026-09-07 — the trust pack needs a week of data before it says anything

**For testers: the trust pack now speaks in the report, not in the alert stream.** At 21:17 tonight it sent node
#1's household three warnings on Telegram and all three were wrong. Every rule in it asked 24 hours and called the
answer an alert. All three now need seven days of a sensor before they will name it, and all three are `info` with
a seven-day cooldown, so what they find belongs in the week's instrument paragraph rather than in your evening.

Nothing else in the node changes: what it measures, when it speaks about the air, the heat, the sea and the land,
and what those alerts say are untouched. Update with `./update.sh` as usual.

**Your node will go quiet about its own sensors for a few days, and that is the fix.** A sensor with under seven
days of readings on this node is never named by this pack. Node #1's oldest local kit reaches a week on
9 September and the other four on 12 September; a node installed this week says nothing here until it has a week
of its own.

### what fired wrongly, and what each rule asks now

- **`channel_dead` fired at dusk on every kit with a light channel.** It asked for six flat hourly buckets out of
  the last 24 with the latest one flat too. Ungasan Kit's light channel reads 0 from dusk to dawn — eleven flat
  hours, ending in the latest bucket — so it matched every evening, as often as its 12-hour cooldown allowed. Any
  channel with a legitimate floor (light, uv, rain, noise) or a steady indoor value tripped it. It now needs a
  whole day: all 24 of the last day's hourly buckets present and flat, none of them moving, while another ambient
  channel on the same kit did move. A flat value of 0 is skipped, because a floor is not a freeze.
- **`peer_disagreement` said that 7.4 and 5.4 µg/m³ disagree, twice.** It compared 24-hour means on a ratio alone
  (0.85–1.15). At 7 µg/m³ that band is ±1 µg/m³, which is the integer resolution of a Plantower-class sensor and
  ten times inside its stated accuracy at low concentration; two identical units in clean air disagree by more
  than that most days. It also fired once for each unit in the pair, which is one fact twice. It now uses
  seven-day means, needs at least 100 of the week's 168 hours from both units, and needs the difference to clear
  an absolute floor as well as the band — 5 µg/m³ for PM, 2 °C for temperature, 5 points for humidity, 0.3 kPa for
  pressure. One alert per pair, naming both units and both numbers.
- **`coverage_low` had not fired yet and was about to.** 60% of 168 hours is unreachable for a node younger than
  about four days, so a new node would have said "missing most of the week" on day one. Same 60%, over seasoned
  sensors only.

### tests

The three rules are now run against node #1's own readings — the real series out of the 7 September dump, through
the rule SQL as it ships — so the light channel at dusk, the 7.4-against-5.4 pair and the four two-day-old kits
are regressions and not prose. See `packs/trust/README.md` for where every number comes from and what has still
never been exercised: none of these thresholds has met a burn season.

## v0.39 — 2026-09-07 — the node knows its version, writes its own report, and draws its own ground

Four parallel sessions of work, released once. v0.37 and v0.38 were written into this changelog but never
tagged and never bundled, and two more branches each wrote a v0.37 of their own — so nothing shipped under
either number and all four land here instead. Nodes update with `./update.sh` as usual.

**Known limitation, not fixed here.** A node still learns its new version one update late: `VERSION` is read
by the installer, not baked into the app image. Closing it means putting the stamp in the image.

### a node installed from the tarball knows which version it is

Every beta tester's node called itself `dev`. Testers install from the tarball, and the installer read the
version with `git describe`, which has nothing to read where there is no repository. A `VERSION` file sat in
the same folder saying `v0.36` and nothing looked at it.

- **`/health`, `planetai status` and the vitals row on the dashboard name the version the node runs.** A
  tester can say which version produced a problem.
- **`planetai version` prints a version.** On a tarball node it printed the node's name and place with an
  empty space where the version goes.
- The version is read from git, then from the `VERSION` file the tarball carries, then `dev`. `install.sh`,
  `update.sh` and `planetai version` had the same line; all three now read the file. A git clone reports what
  it always did.

**The update that brings this fix stamps `dev` one last time.** `update.sh` copies itself to a temporary file
and runs from there, so the script driving your update is the one you already had. Run `planetai update` a
second time and the version appears, or run `./install.sh` in the node folder, which is idempotent and reads
`VERSION` straight away. Nodes installed fresh from the tarball are correct from the first minute.

A household sees no change on the wall screen. This is release metadata: what the node measures, when it
speaks and what it says are untouched.

### one clock, and the node writes the report

Three schedules were sending messages from two containers and none of them knew about the others. Counted from
node #1's own `alerts` table over the 48 hours to 17:37 on 7 September, at the shipped `ALERT_LEVEL=warn`:

| | before | after |
|---|---|---|
| alert messages | 50 | 37 |
| scheduled reports | 2 | 6 sent, 2 written and held at midnight |
| from the agent container | 0 | 0 |
| **total** | **52** | **43** |

Thirteen of the fifty were warn-level — something changed, nothing to do — and they are report lines now.

**The `after` column needs one line from you.** `ALERT_LEVEL`'s *default* moves from `warn` to `act`, and a
default only reaches a fresh install: `update.sh` adds keys your `.env` is missing and never overwrites one it
already has, which is why nothing you chose has ever been changed by an update. Your `.env` says
`ALERT_LEVEL=warn`, so it will go on saying that. To take the thirteen:

```bash
planetai report level act        # or Set up → Alerts → Interrupt me for → "only when something needs doing"
```

The reports, the quiet midnight, the single clock and the act alerts that ask for nothing all arrive on their
own.

Two of those "before" numbers need saying out loud. **The agent container's 07:00 report has never arrived**, from
v0.30 to v0.36. `ask()` returns `(answer, rung)`; the line wrapped that in another tuple, so Telegram was handed
`"text": ["🌅 Good morning…", "local"]`, which the Bot API rejects because `text` must be a string. The handler
logged `brief failed: TelegramError` every morning after spending a full model round trip with tools on text it
threw away. Before v0.30 the unpacking was right and the copy did arrive, an hour after the node's own 06:00
report — which is the duplicate this release was written to remove, and which had already removed itself by
accident. And **`briefing/morning` fired once in five days**: the node's machine does not stay up, and a report
due in a window the node slept through was simply never written.

The 43 is still high because 21 of the 37 are `heat/heat_stress_now` at the 32 °C line node #1 still runs on
v0.34. v0.35 moved that line to 35 °C apparent and replayed 36 firings down to 8 over five days. A node on
v0.35 and this release, over the same two days: **about 27 messages, six of them reports, and nothing at all
between midnight and six.**

#### What a household gets

- **One report every `REPORT_EVERY` hours from `REPORT_ANCHOR`**, in the node's own time zone. Default 6 and 6:
  06:00, 12:00, 18:00, 00:00. `REPORT_EVERY` takes 3, 4, 6, 8, 12 or 24 and refuses the rest.
- **Six parts, under a hundred words**: where the place stands · what changed · anything only the models know ·
  what happened after this window's alerts · the one thing to do before the next report · ask me anything.
- **The node writes it, not a model.** SQL against its own tables. Most nodes have no model and get the same
  report. A model may rewrite it from v0.38, under a rule that refuses any number it was not given.
- **A report due inside quiet hours is written, stored and not sent.** It is on the dashboard the whole time,
  saying so, and the next one folds those hours in and opens with "Overnight and this morning". A node that was
  off for a week reports two days, not a hundred and sixty-eight hours.
- **`ALERT_LEVEL` is `act` by default**, where it was `warn`. Everything below the line is still recorded, still
  on the dashboard, and in the next report.
- **An act alert asks for nothing back.** No `#41` on the end, no button on the hero, no "Still waiting on you"
  in the report. From v0.39 the node watches what the sensors do after an alert and asks once, afterwards, what
  you did — with what it saw in the question.
- **The dashboard** has a new band under the hero: *Here — the last thing the node said*, with the report as you
  received it, the hours it covers, and a Report now button behind the settings token.
- **Spanish.** The report renders in `es` as well as `en` and `id`. It is the first Spanish anything on the node.
  Both the Spanish and the Bahasa Indonesia templates are assistant-written and no native reader has been through
  them; treat them as a draft.

#### If you want the old rhythm back

```bash
planetai report every 12 && planetai report at 6
```

Two reports a day, at six and six. For the warn-level messages as well, set *Interrupt me for* → "also when
something changed" in the dashboard under Set up → Alerts, or `ALERT_LEVEL=warn` in `.env`.

**Nothing you chose is deleted.** On the first start after the update, a node that had `BRIEFINGS`, `BRIEF_MORNING`
or `BRIEF_EVENING` set writes `REPORT_EVERY=12` and `REPORT_ANCHOR=<your old morning hour>` once, logs it, and
leaves the old keys where they are. A node with `BRIEF_MORNING=7` keeps seven o'clock and keeps speaking twice a
day. A fresh install gets 6 and 6.

#### Under it

- `app/report.py`: `bundle()` — every number the node has about a window, as one JSON document capped at 64 kB —
  and `sheet()`, the six parts, with one template dict per language and no wording anywhere in the code.
- **Notability**: a window's mean against the mean of the same local hours on each of the previous seven days, in
  standard deviations of that baseline; null under three days, so a node in its first week claims nothing. It
  decides which two places get a sentence.
- **Trend** is the digest's ±3 read across to each metric's units: 3 µg/m³ for PM2.5, half a degree for a room's
  temperature, 5% of the window's range otherwise. One degree and three micrograms are not the same size of change.
- `reports` table, schema 0.23. The row for the local hour is the scheduler's lock, so a container restarted inside
  the twenty-minute window sends nothing. The old briefings asked `alerts`, which every rule also writes to.
- `insight/digest` carries `contributes: report` and no message: its numbers are in every report and none of it
  interrupts anyone. `contributes:` is documented in `docs/PACKS.md`, and `make lint` refuses a rule with both a
  message and a contribution, or with neither.
- `GET /report/latest` · `GET /report/bundle?hours=` (read-only token) · `POST /report/now` (admin token).
  `/briefing` answers 301 to `/report/latest` for one release and goes in v0.38.
- MCP: `report_latest`, `report_now`, `report_bundle` replace `daily_report`. Nineteen tools.
- CLI: `planetai report`, `report last`, `report every <h>`, `report at <h>`.
- The agent container reads no wall clock at all, and a gate refuses one.
- `notify`'s `force` argument is gone. It never did anything.
- **The pre-commit hook now runs `make test` as well as `make lint`.** AGENTS.md has required both since v0.14 and
  the hook ran one, so a commit in this release removed a function and left `test_shipped.py` red with nothing
  listening. Re-copy it: `cp tools/hooks/pre-commit .git/hooks/`.

#### Not in this release

The 13:03 event on 7 September — one pot, three sensors in one room, six act alerts in five minutes — is still six
alerts. One event, one alert, and ρ measured from the sensors instead of asked for, are v0.39.


### local means here, not just yours

Node #1 moved to Ungasan in August. Three of its six Smart Citizen kits stayed behind at the old address, 1.2 km
away, and one sits 7.8 km away in another town — and every one of them still counted as this node's own
measurement, because `local` had only ever meant "on your account." A kit that measures a different building was
filling this node's indoor cells, feeding its heat alerts, and hiding in its coverage figures next to sensors that
are actually here. This release closes that, and adds a pack whose job is to say when the node's own numbers are
not to be trusted.

- **`local` now means ours *and* here.** A sensor still has to be on your account, and it now also has to sit
  within `LOCAL_RADIUS_M` of the node — 500 m by default. On a node whose sensors are not all at one address, this
  can change what counts as local: a rule or a cell that reads local sensors may change value, or go quiet, where
  it did not before. That is a correction, not a regression — `docs/COVERAGE.md` has always said the node does not
  fill what it cannot measure; now it actually stops. `LOCAL_RADIUS_M` cannot be set until a node has updated to
  this release. At the default 500 m, node #1 keeps only its two outdoor kits (`sc-19236`, `sc-19874`) as local
  and loses all three indoor ones — every indoor rule and the `Social|Community` cell go quiet. Node #1's operator
  has instead chosen 1500, wide enough to keep the old address's three indoor kits without reaching the kit 7.8 km
  away: at 1500 m node #1 keeps its three local indoor sensors and gains its two local outdoor ones, the first
  time it has had both. Nothing on node #1 goes quiet at the radius it is set to run at. If your own sensors sit
  at more than one address, check your radius before you update — the 500 m default may take more of your kits
  out of "local" than you expect.

- **Heat rules are indoor-only now.** The apparent-temperature formula both heat rules use — Steadman's, with no
  wind term — is the indoor form; there is no still air on a street. Both `heat_stress_now` and `heat_danger` now
  read indoor sensors only. A node whose only local sensors are outdoors gets no heat alerts. That is the right
  answer, not a wrong number: the formula, and the 35 °C line the previous release measured with it, were never
  valid for what an outdoor kit reads.

- **Smart Citizen's `aqi` channel is now `bme_iaq`.** It was never an air quality index: it is the BME680 gas
  sensor's own internal index, and it shared a metric name with Bali Air Dispatch's real, vendor-published AQI —
  averaging the two averaged two different quantities together. Four things are true of the change: existing
  `aqi` rows from Smart Citizen stay in `readings` as history; no migration deletes them; no rule reads them any
  longer; and the new `bme_iaq` metric starts fresh, with no history behind it yet. Bali Air Dispatch's `aqi` is
  untouched — it is a real index from a different source and was never the problem.

- **A `channel_roles` registry says what a metric IS**, not just what it is called (schema 0.22). Five roles cover
  it: `ambient` (the air, water or land at a place, comparable between sensors at the same spot), `enclosure` (the
  inside of the instrument's own box, never comparable), `device_health` (the instrument reporting on itself),
  `derived` (computed by us, carrying its inputs' provenance), and `index` (a vendor's own composite number, never
  pooled or averaged with anyone else's). A role is declared once per `(source, metric)` pair, so every sensor
  that comes from one adapter shares it — nothing to set per sensor.

- **A new `trust` pack** watches whether the node's own instruments are telling it the truth. It needs no
  configuration and writes no Index cell of its own — a score for our own equipment invites optimising the score
  instead of fixing the sensor. It says three things: a channel that has stopped moving for six or more of the
  last 24 hours while the rest of its kit keeps reporting (`channel_dead`); a local sensor that has reported for
  under 60% of the last seven days even though its latest reading still looks current (`coverage_low`); and two
  sensors within 50 m of each other whose 24-hour means disagree by more than 15% (`peer_disagreement`), which
  asks you to swap the two units for a day rather than guessing which one is wrong. Two things it cannot see yet,
  because nothing declares their role: PurpleAir's `channel_disagreement` (already computed in the PurpleAir
  adapter, waiting on a rule) and Meshtastic's `altitude_m` (written outside the metrics the registry knows about).

- **`rhythm` stops blaming traffic.** It used to end an evening PM2.5 peak with "that is the burning and the
  traffic, not the weather." The one kit in the fleet with a noise sensor said otherwise: the street is loudest
  through the late morning and afternoon and quietest overnight, while PM2.5 peaks in the evening and again near
  dawn — the loud hours are the clean ones. `rhythm` now reads that noise channel and names the contrast instead
  of guessing a cause. A node with no local outdoor noise sensor gets no `rhythm` alert at all; that is deliberate,
  not a bug.

- **`/trust`, a dashboard card, and a health check** put all of this somewhere you can see it. `/trust` returns one
  row per local sensor: its 7-day coverage, how many of its channels are currently frozen, and its age. The
  dashboard's new card shows only the sensors worth a second look, and says plainly when none need one. The
  agent's health check reads the same endpoint the card does, so the two never drift apart from each other, and it
  names the fix in plain language: power-cycle the kit, and if the number stays frozen, replace that sensor.

Two things this release has not done. The trust pack's three thresholds were chosen against one low-PM week at one
site (6–10 µg/m³, 1–7 September) and have never been tested against a burn season, when PM2.5 swings far wider and
disagreement between units may widen with it. And the new dashboard card has not been checked by eye at 375, 768
or 1440 px — only against the data it renders.


### the ground under the hero is the cell this node stands in

Since v0.36 a map cell has sat behind the sentence on the hero and on the wall. It was the same cell on every
node: node #1's, in Kuta Selatan. On a node anywhere else it looked like that node's own place and was not, so
the line naming it was cut and the drawing said nothing at all.

- **The node draws its own cell**, from the coordinates it was set up with. The resolution-8 cell it stands
  in, the seven smaller cells inside it, and its neighbours' edges running off the frame.
- **The cell is named again, under the hero and on the wall**: `8839446033fffff · RES 8 · 525 M EDGE · THE
  CELL THIS NODE STANDS IN`. That id is the node's place in the index, and it is now true wherever the node
  is. The edge is this cell's own, measured. H3 publishes 531 m for resolution 8; that is an average, and no
  cell is exactly it.
- **`/health` carries the cell**: id, resolution, mean edge in metres. Agents and `planetai status --json`
  read the same thing the screen shows.
- Change the node's coordinates and restart, and the ground follows.

The drawing is computed here, not fetched. A node on a LAN with no route out still draws its own cell. It is
the same picture `planetai-design` draws with d3-geo, to the last vertex, and a test redraws node #1's cell
and compares against the shipped file to keep the two together.

`planetai update` rebuilds the image, which now carries one more library, `h3`. A node that has not been told
where it stands keeps the picture it had, naming nothing.

## v0.36 — 2026-09-07 — the dashboard says what the colours mean

Six things on the dashboard were decoration wearing the clothes of information. They are gone, and a check now
fails the build if they come back.

- **The big green hexagon behind the number is gone.** In its place the node draws the map cell it stands in:
  the cell, the seven smaller cells inside it, and the edges of its neighbours running off the frame. It is
  drawn faint, behind the sentence, and it is computed geometry rather than a shape someone liked. The
  isometric mesh that used to cover the hero has gone with it.
- **The number is the same colour as the words, until it is not.** It used to be green whatever it said. Now
  it is ink, and it turns red when the reading is over the line the sentence names. Nothing else on the page
  is green except a loop that closed.
- **"I did this" is a green button.** Pressing it is the response, and that press is what ρ counts. Orange
  now appears in one place only: the buildings on the plan that the satellite can see and the map has not
  drawn.
- **Numbers are set in JetBrains Mono.** Digits line up between one reading and the next, so a column of
  readings can be compared by eye. The font is on the node, so it looks the same on a house with no internet.
- **The two glows drifting behind the page are gone.** So is every gradient.
- **The label beside the satellite section is a mark and a word, in ink.** It was a rounded blue pill, which
  looked like a verdict on the number next to it. It says where a number came from and nothing about whether
  the number is good.

A household on a wall screen will notice the page got quieter and the number got easier to read. Nothing about
what the node measures, when it speaks or what it says has changed.

Under it:

- `tools/check_ui.py` gained seven rules and fails on each: a six-sided `clip-path` wider than 24px, any hex
  from the website palette, any gradient, a control rounded past 8px or a card past 18px that is not on a dated
  legacy list, a provenance mark carrying a colour, orange anywhere but the satellite layer, and Fab Blue
  `#20388D` on the dark ground where it measures 1.72:1 and cannot be seen. The dark register's blue is
  `#7FA5E8` at 7.21:1.
- `tests/test_check_ui.py` breaks each of those rules against a copy of the real page and requires the check to
  name it. It runs in `make test`.
- The dashboard is still one HTML file with no build step. The two things it cannot hold, the ground and the
  font, are served by name from an allowlist in `app/main.py` and revalidate on every load, so an updated node
  never shows the previous design.

## v0.35 — 2026-09-07 — the heat rule was measuring Bali, not a heatwave

Two thirds of every message node #1's household received was one rule. `heat_stress_now` fired 20 times in the 48
hours of 5–7 September, always reporting 32.0–34.6 °C, and four of those arrived between one and five in the
morning — act-level alerts are the ones quiet hours do not hold. The reports-and-messages release moves
`ALERT_LEVEL` to `act`, which drops the eight warn-level messages and leaves all twenty of these; the quiet nights
it promises would not have arrived on node #1.

- **`heat_stress_now` fires at 35 °C apparent, not 32 °C.** 32 is the bottom of the heat-index "extreme caution"
  band, and in Kuta Selatan that band is the climate. Measured on node #1's own five days of `temp` and `humidity`:
  the hot room was above 32 °C for 86% of every reading, never fell below 28.7 °C, and averaged 33 °C at four in
  the morning — its coolest hour. 35 °C is that sensor's 90th percentile. Replayed over the same record with the
  rule's real cooldown it fires eight times in five days instead of thirty-six, none at night, and nothing at all
  on the two days the weather eased.
- The other three candidate fixes were replayed against the same data and rejected on it. A duration condition
  (over the line for four readings running) changes the count from 36 to 36 — the house is over 32 °C
  continuously, so there is no spike to suppress. Requiring AT to be rising fires on the ordinary morning warm-up
  every day and goes silent on a flat hot night, which is the case that hurts people. A cooldown of 1440 minutes
  reaches the same eight, but every one of the eight is still a false alarm. The cooldown stays at 240; at 35 °C it
  no longer matters.
- The Social cell keeps 32 °C. Counting hours of exposure is not interrupting someone, and 32 °C is the right line
  for a count.
- `packs/heat/README.md` now says which place the numbers were written for, as `docs/PACKS.md` requires, with the
  node #1 distribution the 35 °C came from and how to move it for a temperate flat.
- **New gate:** a pack README's unit-bearing thresholds must appear in that pack's own files. The README is the only
  place a household can learn why a number is that number, and nothing was checking that it still matched the SQL.

The alert texts are unchanged: this release changes when the rule fires, not what it says.
## v0.34 — 2026-09-07 — the years, as pictures you can play

The land card knew about one year pair. Nine years were on the disk beside it and it said nothing about them.

- **`planetai run earth frames`** draws one picture of the place per cached year: the strongest direction
  through the 64 embedding dimensions, mapped to grey. Dark water, bright land, roads and plots legible, the
  node ringed, a 1 km bar, and the year burnt into the corner so a frame that leaves the node still says
  when it is. About 780 kB a frame, nine years in a few seconds, from files already downloaded.
- **The card plays them.** A play button steps through the years, a slider stops on any one, and a second
  button switches to the change map. Pick 2019 and it stays 2019 — the page refreshes every half minute and
  no longer drags you back to the newest year.
- **The narrative now tells the whole record**: how many years are held, what the full span found, and a
  year-by-year list of the share that changed, so the shape of the history is visible. At node #1 that is
  eight years, 8.8 % of the square, 880 hectares — with the two quietest years in the record being
  2020→2021 and 2021→2022.
- **The images are named as files.** The card prints the directory they live in on the node and links the
  ones it is showing. A page cannot open a folder on the machine serving it; browsers do not allow that, so
  it says where they are instead of pretending to a button that cannot work.

**These are not photographs.** This pack has never downloaded imagery: it holds a model's 64-number
description of every 10 m pixel, and a frame is that description flattened to one number and drawn. It looks
like a panchromatic satellite image because the strongest thing in the embedding is the strongest thing in
such an image, but no camera saw these greys, and the card says so. For real Landsat and Sentinel-2 frames,
`planetai run earth-engine timelapse` downloads pictures and needs an Earth Engine key.

The projection is fitted once, over every year cached at the time, and then kept in `meta.json`. When next
year's layer arrives it is drawn through the same projection, so the new frame joins the sequence instead of
silently redrawing every frame before it. `planetai run earth frames --refit` redoes it, which is what a
moved square needs and a new year does not.

## v0.33.8 — 2026-09-07 — the whole satellite history in one command, and an argument it does not know is an error

Reported from node #1: `planetai run earth change --all` printed a perfectly ordinary result for the latest
year pair. The flag did not exist yet, and the way the arguments were read, anything that was not a
four-digit number was dropped — leaving an empty list, which meant "the default". A plausible answer to a
question nobody asked is worse than an error.

- **`planetai run earth change --all`** computes every consecutive cached pair and the span from the oldest
  cached year to the newest, then prints them as one table. Pairs already computed are skipped unless
  `--force`. With nine years cached that is nine comparisons in a couple of seconds; the download is the only
  slow part and it has already happened.
- **An argument the script does not recognise now stops it**, naming the argument and printing the usage.
  A mistyped year (`217`) or a single year does the same.
- **Read the span first.** At node #1 the eight-year span flags 8.80 % of the square and the eight yearly
  steps sum to 8.51 %, so the areas agree. What does not agree is the mean: the yearly means sum to 0.2991
  against the span's 0.0673, four fifths of it cancelling out year to year. The span's p95 sits at 3.65 times
  its median where every single year sits between 2.1 and 2.8, and 92 % of its flagged pixels lie inside
  patches against 82–89 % for the years. The span is the cleaner picture of what was built; the yearly rows
  say when. The pack's README carries the numbers.

## v0.33.7 — 2026-09-07 — one landmark emptied the kilometre

The plan of the kilometre went blank on node #1 the day it moved, and stayed blank through three releases that
each looked like the cause. It was neither the cache nor the coordinates: it was one feature.

- **A poi mapped as an open way stopped the whole plan drawing.** OpenStreetMap carries Garuda Wisnu Kencana as a
  way with a poi tag; the draw took `coordinates[0][0]` as a point, which for a LineString is a bare number, and
  threw. Because the draw is not awaited the rejection was unhandled: an empty band, no message, nothing in the
  node's log. A poi now draws from the first coordinate of any geometry, and each feature is drawn inside its own
  try, so one undrawable object costs that object and nothing else.
- The caption and legend now count what is drawn rather than what was read: it claimed 2,714 buildings where 2,699
  have outlines, because fifteen are mapped as nodes.

If a plan is missing after this, the band now says so instead of disappearing (v0.33.5) and the page follows the
node's version without a hard reload (v0.33.6).

## v0.33.6 — 2026-09-07 — the update reaches the screen

`GET /` sent no cache headers, so after `planetai update` a browser could keep serving the dashboard it already
had — with the bugs the update fixed. An ordinary reload does not always revalidate a document the server said
nothing about. This is why the plan-band fix in v0.33.5 appeared not to work: the node was serving it, the browser
was not running it.

- The dashboard is sent with `cache-control: no-cache, must-revalidate`. One hard reload is needed to get past a
  copy already in a browser; after that, a node's version and its page stay together.

## v0.33.5 — 2026-09-07 — the kilometre came back

The plan of the kilometre disappeared from a dashboard and stayed gone. Nothing was wrong with the node: it was
serving 4,906 features for its new point in 1.3 seconds.

- **The plan band no longer hides itself in silence.** One failed or interrupted `/place/geojson` was cached as
  "no features", and because the cache was then set, nothing refetched for the life of the page — the band vanished
  until a manual reload, with no message. A node whose coordinates had just changed was the way in: the refetch
  takes a while, and a page opened during it never recovered. Now the band stays and says which of the three things
  happened, and a failure is retried on the next refresh. A node whose place pack has never run keeps it hidden.
- **The dashboard no longer scrolls sideways on a phone.** The five buttons of the view switcher are 449 px wide
  with no shrink, so a 375 px screen slid the whole page. The row scrolls inside itself now. Present since v0.28;
  the beta review's "no overflow at 375/768/1440" was a false pass.
- The plan's caption said "1 buildings on the map. Uses: ." where a place has no mapped uses.

## v0.33.4 — 2026-09-07 — moving a node

Both location packs kept their caches when the node's coordinates changed. Found by asking how to regenerate the
plan after editing `NODE_LAT` / `NODE_LON` in `.env`.

- **`place`**: the staleness test read only the radius and the age, and `place_runs` never recorded where the fetch
  was centred. A moved node served the previous neighbourhood's geometry to the plan for up to thirty days while
  computing "nearest school" and "nearest clinic" from the new point against those old features. The run now records
  its point, a move refetches on the next poll and says so in the log, and the satellite footprints and the yearly
  series are cleared with it — they described the old circle and only the Earth Engine step refills them.
- **`earth`**: a moved point or a changed `EARTH_RADIUS_M` re-resolved the tiles but skipped every cached year as
  "already cached", so the node went on comparing a square around the previous address, with `meta.json` claiming
  the new one. Those years are now re-read, with the reason and the count printed first (about 103 MB a year).
- **`earth`, found while rehearsing the move**: a partial re-fetch used to leave one year from each square and
  `change` compared them, reporting the difference between two places as a year of change; and the old square's
  change map stayed on disk, where `/earth`, the dashboard card and the Index cell kept reading it. Both are removed
  with the square now, and `change` refuses a year that has no window recorded for the current square.
- **Both**: a correction smaller than 1% of the radius, never under 25 m, is not a move — retyping a decimal costs
  no download. `planetai run place verify` and `planetai run earth verify` now fail on a cache that belongs to
  another point; earth's step 5 claimed to check this and only measured the window's span.
- To move a node: edit `.env`, `planetai restart`, `planetai run place refresh`, then reload the dashboard. Both
  pack READMEs say it.

## v0.33.3 — 2026-09-07 — `planetai update` ships a pack's code, not its libraries, and now says so

From node #1, after updating to v0.33.2 and running `planetai run earth fetch`: 9 MB of tile index downloaded,
then `ModuleNotFoundError: No module named 'rasterio'` printed once per year, nine times, naming no fix. The
node had the pack and not its libraries, because `app/requirements-packs.txt` is gitignored and only
`planetai packs install` writes it. That split is deliberate — a listing should not rebuild your image — but
nothing told you which side of it you were on.

If you are on a node that has this now: **`planetai packs install`, then `planetai restart`.**

- **A pack script that needs a library it has not got says which command installs it, and stops before doing
  any work.** `planetai run earth fetch` on such a node now prints four lines and exits, instead of
  downloading the index and failing nine times.
- **The same hole existed in two older packs**: `planetai run earth-engine timelapse` and
  `planetai run place satellite` both crashed with a bare `ModuleNotFoundError` if `earthengine-api` was
  missing. Both now name the fix.
- **`planetai update` warns when a pack declares libraries or settings the image does not have**, so you find
  out at the end of the update rather than the first time you run something.
- **`make lint` refuses a pack script that imports something from its own `pip:` list without saying how to
  install it.** Run against the three scripts that had the hole, it names all three.

## v0.33.2 — 2026-09-07 — the satellite card showed a broken image before you fetched anything

Reported from node #1 straight after updating: the land card showed a broken-image box with its alt text
spilling across the card, above the sentence telling you to run `planetai run earth fetch`. Every node that
had not fetched satellite data yet looked like this.

The script hid the image correctly. The CSS did not let it: `#earth-img` sets `display:block`, and any
display rule of ours beats the `hidden` attribute, whose `display:none` comes from the browser's own
stylesheet. The comment one line above it in the same file warned about exactly this — it is how an empty
orange act strip once showed on every node with nothing to act on — and the rule was written anyway.

- **Fixed**: `#earth-img[hidden]` now cancels the display rule, and the empty state also drops the image's
  `src` so nothing is requested. Verified on a node in both states: with no data the image computes to
  `display:none` and occupies nothing; with data it renders the 1000 px map at 643 px inside its card.
- **`make lint` now catches this class of bug.** `tools/check_ui.py` checks that anything the script hides
  with `.hidden` is not un-hidden by a display rule on its id or any of its classes. Run against the two
  bugs that shipped — this one and the 2026 act strip — it names both.

Nothing else changed. The number, the map, the endpoint and the Index cell are the same as v0.33.1.

## v0.33.1 — 2026-09-06 — one number for the land, not two

Found on the way out of v0.33: the new `earth` pack and the older `earth-engine` pack both published a
year-over-year land-change number, both labelled `partial`, both described in words as "the land changed",
and they disagreed. On node #1 Earth Engine said 0.037 and the earth pack said 0.041. They were measuring
different things — Earth Engine took the cosine distance between two years' *mean* vectors over 1 km, the
earth pack takes the mean of the *per-pixel* distances over 10 km, and averaging vectors first cancels the
noise that averaging distances keeps — but nothing on any screen said so.

For a tester, what changes:

- **`earth-engine` no longer reports land change.** Its `land_change_score`, its second
  `Environmental|Bioregion` cell and its `land_changed` alert are gone. It keeps what only Earth Engine can
  give: tree cover and built-up fraction from Dynamic World, Sentinel-2 NDVI, VIIRS night lights.
- **The `land_changed` alert is gone and nothing replaces it yet.** It was going to move to the `earth`
  pack, and then the measurements said not to. Four pilot squares, 2024→2025: Kuta Selatan 0.041, Boston
  0.040, Barcelona 0.016, Santiago 0.015. Boston and Barcelona are at the same latitude and differ by two and
  a half times, and Boston's change is spread over built-up land rather than water, so the likeliest reason is
  snow and leaf-off between two annual composites — not 326 hectares of Boston rebuilt in a year. Any
  threshold that fires in Kuta Selatan, where the land really is being built on, fires in Boston every year
  for nothing. This node does not send messages a household would ignore, so it sends none: the map and the
  number are on the dashboard for a person to look at. If you ran `earth-engine` with a key you lose a
  message you had; that is the cost of not having one we can defend.
- **A NAS now archives what the earth pack computed.** `tools/nas/pull.py` fetches every `change_*.json` and
  its map. Not the embedding cache: that is 64 MB a year and `planetai run earth fetch` remakes any of it in
  about two and a half minutes from a public bucket. What cannot be remade once a node is gone is the record
  of what that node computed and when, and that is a few hundred kB a pair.
- **`GET /earth` lists every comparison, not just the latest**, and `GET /earth/change.png?pair=2023_2025`
  serves any of their maps. The pair only chooses among the comparisons the node actually computed; the file
  name still never comes from the request.

## v0.33 — 2026-09-06 — the node keeps its own square of the planet

Google publishes the AlphaEarth Foundations Satellite Embedding layers — 64 numbers describing every 10 m
pixel of the land surface, one layer a year since 2017 — as Cloud-Optimized GeoTIFFs in a public bucket under
CC BY 4.0. A new pack downloads the square around your node, keeps it on your disk, and compares two years
here. No account, no key, no cloud project. Two vectors for the same pixel point the same way if nothing
happened there and apart if something did, so the arithmetic is one dot product per pixel.

For a tester, what changes:

- **A new pack, `earth`, and it is off until you ask for it.** Like every code pack it needs
  `PACKS_ALLOW_CODE=1` and `planetai packs install`. Nothing downloads on a poll: the pack fetches only when
  you run `planetai run earth fetch`.
- **What it costs, measured, not estimated.** One year of a 10 km square around the node is **64 MB on your
  disk** and **about 103 MB pulled**, and takes **about two and a half minutes**. All nine years is 576 MB
  kept and 925 MB pulled. The first fetch also reads 9 MB of the dataset's tile index, once. Rehearsed at both
  pilot coordinates: Bali 2023-2025 in 359 s, Santiago 2024-2025 in 215 s.
- **What it does not measure.** Land surface and coastal water as seen from orbit. Not air, not water, not
  emissions. One layer a year, published after the year ends, so it is a record and not a warning. And it says
  *something* changed in a place, never *what* — a new building, a widened road, a cleared slope and a flooded
  field all move the number the same way. Someone who walks there can tell you which.
- **A card in the Region band and `GET /earth`.** The map, the year pair, the share of the square that changed
  and the hectares, with a `Derived` pill: this is a Google model's output that your node did arithmetic on,
  not something your node measured. One Index cell, `Environmental|City`, `partial` for good.
- **`planetai packs install` now adds about 250 MB to the image** when the earth pack is present, for
  `rasterio` and `numpy`. Measured on the Lima node: 458 MB → 710 MB, a nine-minute rebuild. That happens
  whether or not the pack is enabled, because the installer takes every pack's `pip:` list; if you do not want
  it, delete `packs/earth/` before you run it.
- **The app image gains `libexpat1`** (436 kB, every node). Without it `pip install rasterio` succeeds and
  `import rasterio` fails, so the installer would report success and the pack would die on its first run.

For someone working on the code: `make test` now runs `tests/test_earth.py`, which imports numpy without a
guard. A dev machine without numpy fails the suite instead of printing "skipped" — deliberately, because the
whole pack is arithmetic and the de-quantisation is easy to get wrong in a way that still looks plausible.

## v0.32.1 — 2026-09-06 — starting over on the same machine

Found while rehearsing v0.32 from the site's install line on a clean VM whose earlier node had been deleted: Docker
had kept the database volume, the new `.env` got a new password, and the app could not log in to its own database
while `pg_isready`, `/health` (200) and the install's doctor all looked fine. A tester who deletes the folder to
start again does exactly this.

- `install.sh` refuses to start a node whose fresh password cannot match an existing database (the `planetai_db`
  volume, or a `DATA_DIR` with a `PG_VERSION` file) and names the two ways out: put the earlier `.env` back, or
  `docker volume rm planetai_db`.
- `planetai doctor` gains "app logs in to the database" and names the same fix.

## v0.32 — 2026-09-06 — the review's open items, decided and closed

The beta review (v0.31) left a list; Tomas decided the three questions on it and this release does the work. Every
change was rehearsed on the Lima node from the review (`planetai update` v0.31 → v0.32, then each behaviour checked
by hand), then pushed to `main`, which is the beta channel.

For a tester, what changes:

- **Nobody on your WiFi can feed your node readings.** `POST /readings` needs the admin token. On the clean node a
  curl from the LAN had created an indoor sensor at 999 µg/m³ and two act-level alerts reached the phone within a
  minute. Nothing shipped used the endpoint without a token, so nothing you have breaks.
- **Dumps no longer carry your Telegram token.** `backup.sh` leaves the rows of the `settings` table out of every
  dump (the table itself stays, empty). Cost, said plainly: dashboard settings do not survive a restore; the node runs
  on `.env` and `planetai telegram` reconnects a bot that was set from the dashboard. `planetai restore` says so.
- **A pack cannot read your secrets.** Rules and cells from `packs/` run as a read-only database role
  (`planetai_ro`, schema 0.21): every table but `settings`, no writes. `planetai update` creates the role; a database
  that predates it is told once in the log and keeps working.
- **What anyone on the network can read of your settings is smaller.** Without the admin token, `GET /settings`
  masks the household's values (chat ids, sensor hosts, accounts, remote URLs) the way it already masked secrets;
  the node's own settings (alert level, hours, language, layout) stay readable so every screen in the house agrees.
  The dashboard's Set up view sends the token once unlocked and tells you at once if it is wrong.
- **Tokens are compared in constant time**, through one helper, on every gate (`/mcp`, `/settings/raw`, `/backups`,
  `PUT /settings`, `POST /test-alert`, `POST /readings`, `POST /aggregates`).
- **`planetai packs` only lists.** It used to append pack settings to `.env` and rebuild the image (350 MB of Earth
  Engine client) when asked what was loaded. `planetai packs install` is now the step that writes; the listing says
  when it is needed. The docs and the two pack READMEs say `packs install`.
- **Every container's log is capped.** `db`, `agent` and `ipfs` were not (the agent logs every tool call). The update
  recreates the `db` container once to apply the cap; the data volume is untouched.
- **`planetai doctor` checks the free space** on the disk the node lives on and names the fix under 1 GB.
- **Reports and the test alert say how to close the loop honestly**: `/act N` only when the bot runs
  (`planetai agent local`), `planetai act N` otherwise. Replying `/act` to a bot that was not there did nothing.
- **Terminal**: `planetai` lists every command (sensors, cells, geocode, version were missing); `planetai config`
  without a terminal says where `.env` is instead of "a: unbound variable"; `planetai telegram` finds your message
  even when the newest update is the bot being added to a group; `planetai run` shows each script's first docstring
  line, not its first import; the setup wizard stops offering "Sant Martí, Catalunya, ES" three times for Poblenou;
  `.planetai-setup.log` is trimmed past 1 MB; a `|`, `&` or `\` in a value no longer breaks the `.env` writer.
- **Gates** (`make test`): a POST that writes must check a token before it opens the database; no `!=` on a token;
  settings rows out of dumps; the read-only role and its use; a log cap on every service; the packs listing free of
  `docker compose build` and `>> .env`; the act hint through one function.

Decided and **not** in this release: the Raspberry Pi (no arm64 PostGIS image; the site stops promising it),
`POST /actions` stays open on the LAN for the household's button (it rejects unknown alerts and foreign stages since
v0.31), and `main` stays the channel `/install` fetches. Spanish for the alerts, the daily reports, the test alert and
the bot is on branch `es-messages` (PR #1) awaiting a native reader's pass before it ships.

## v0.31 — 2026-09-06 — what the beta rehearsal found

A clean Ubuntu machine, two presets (Santiago, Barcelona), no sensor, no credentials, the one line from the site. What
broke for that stranger is fixed here; what needs a decision is in `docs/reviews/BETA_READINESS_2026-09.md`.

For a tester, what changes:

- **The install finishes with the green screen** (dashboard address, token, `[o]`/`[t]`), not the red box. A new node
  always failed its own doctor (no Telegram yet, no backup yet) and the wizard treated that as a failure.
- **Linux, first run**: after installing Docker the script continues instead of dying on the docker socket with the fix
  buried in the log. `backups/` is created by you, not by Docker as root, so backups can be written.
- **Your node keeps its name** on Linux (every Linux node was called "Ubuntu"), and **"None yet" for the sensor no longer
  corrupts `NODE_KIND`**, which made `planetai update` fail and then **delete `.env`**. `update.sh` no longer executes
  `.env` as shell, and a failed update cannot remove it.
- **The 92-day history arrives** on a zero-hardware node: the first-start bootstrap was being killed by the wizard's own
  restart and then skipped for good.
- **`/export`, `/history`, `/readings` work** (they returned 500 on every call, so no nightly export was ever written);
  a negative limit is a 422, not a 500; an impossible export date is a 422.
- **Santiago and Barcelona nodes get their open-data portal**: the wizard now applies the pilot preset it detects.
- **`planetai doctor` checks that the nightly backup is scheduled** and prints the crontab line if it is not. Node #1
  had none.
- **The dashboard's empty orange bar is gone**; "Set up" no longer wraps on a phone.
- **`/settings/raw` needs the admin token**, not the NAS's read-only backup token. `POST /actions` accepts only
  `acknowledged`/`acted` for an alert that exists. The agent loop no longer logs the values a model passes to
  `settings_set`. The tarball update path verifies the published checksum; `.env.before-update` stays at 600.
- **Gates**: the app-import check in `make lint` had never run (a `$"` in the recipe) and could not fail; it does both
  now. `check_docs` compares every "N tools" in words with the code (seventeen, not fifteen).
- **Docs**: Raspberry Pi is marked *not yet* (no arm64 PostGIS image exists); dumps do contain the `settings` table;
  Telegram `/act` needs `planetai agent local`; nine packs; the database grows about 1 MB a day on node #1.
- New: `docs/BETA_TESTER_GUIDE.md`, `docs/reviews/BETA_READINESS_2026-09.md`, `docs/HANDOFF_beta_review.md`.

Not in this release, by decision: an arm64 database image; `POST /readings` still needs no token; dumps still carry
tokens; the `main` branch is still what `/install` fetches.

## v0.30 — 2026-09-06 — when the node speaks

Node #1 sent 60 messages in two days with no shape: "Good morning" at 13:02 (the daily pulse fired on a **UTC** hour),
heat stress fourteen times in an afternoon, the digest ten times. Replaced with a schedule.

- **Two reports a day**, at local hours (`BRIEF_MORNING` 6, `BRIEF_EVENING` 18): what the night or the day did, the
  peak indoors, what is still waiting for a decision with its `/act` number, which sensors have gone quiet. Written by
  the node from the same data the dashboard shows, so the two cannot disagree; the bot passes it through unchanged.
- **`ALERT_LEVEL`** decides what interrupts between reports: `act` only when something needs doing, `warn` also when
  something changed, `info` everything. Below the line an alert is still recorded, still on the dashboard, and summed
  up in the next report.
- **`QUIET_HOURS`** (22:00–06:00): only act-level alerts go out; the rest wait for the morning.
- All hours are the node's own (`NODE_TZ`), never UTC. `tests/test_briefing.py` asserts exactly the reported bug —
  06:00 UTC is 14:00 in Bali, so a "6" schedule must not fire then — plus the midnight-wrapping quiet window and the
  level floor.
- The old `daily_pulse` and the daily `modelled_air_today` are superseded by the reports; heat stress cools down for
  four hours instead of three.
- All of it editable in the dashboard's **Alerts** page: two hour pickers, what to be interrupted for, quiet hours.
  `GET /briefing?kind=morning|evening` returns the report as it would read right now; the bot has a `daily_report` tool.

## v0.29.1 — 2026-09-06

- **Fixed: `/place/geojson` returned nothing.** The app's cursors return rows as dicts; the endpoint indexed them as
  tuples and swallowed the `KeyError`. The plan never drew although the pack had stored 3,510 map features and 7,219
  satellite footprints. Rows read by name now; the endpoint reports its tables, counts and any error.
- **The yearly building series is held back until it is verified.** `verify` on node #1 reported 90→136 buildings for
  2016→2023 beside 7,219 footprints in the same circle: a 50× mismatch that means `yearly()` misreads the
  fractional-count band. The dashboard shows the growth sentence only when the series is within 3× of the footprint
  count; `verify` gained a sixth step that cross-checks against built area.

## v0.29 — 2026-09-06 — from where you stand, outward

The Now view reorganised by distance, which is also the Index's scale axis: **Here** (the sentence and the thing to do),
**Room** (feels like, each indoor sensor), **Street** (your kit outside, the public sensors, the wind, the day chart),
**Neighbourhood · 1 km** (the plan, what is here, what is unmapped, and a **Fix the map** button that opens the
OpenStreetMap editor at the node), **Region · 11 km and beyond** (the model, the land, the sea, the weather), and
**Act here** (ρ and the alerts). Each band names its distance. Cards sit at their natural height on fixed tracks; the
`1fr` rows that stretched short cards are gone. Measured at three widths: zero stretched cards in any band.

## v0.28.1 — 2026-09-06

- **Fixed: `planetai run place gaps` hung.** The satellite-versus-map comparison cast both geometries to geography, which
  bypasses the spatial index; every footprint was compared with every building, millions of distance calculations, in
  silence. Now in geometry with a degree tolerance (0.00003° ≈ 3 m), which the GiST index serves in seconds; the same
  fix in `/place/geojson`. `gaps` prints each step as it goes and gives up after two minutes instead of never.

## v0.28 — 2026-09-06 — the plan, the grid, and Arrange

- **The kilometre around you, drawn.** A figure-ground plan under the World band: buildings on the map in ink, roads as
  hairlines by class, green as green, each mapped use a coloured dot with its name on hover, the buildings only the
  satellite knows in orange, north up, a 200 m scale, the node pulsing at the centre. Legend toggles per layer. Drawn in
  the browser from `/place/geojson` (PostGIS, simplified); no tiles, works offline. Rendered from the real Bukit: 2,969
  shapes, 37 uses.
- **No more holes in the grid.** Explicit tracks instead of auto-fit: six on a desktop (hero two, four tiles), three on
  a laptop, one on a phone; dense flow; equal row heights; the World cards as a two-by-two beside the alerts.
- **Arrange.** A fifth button: every card gets ← → and ✕, hidden cards come back from a menu, Default resets, Done
  saves in the browser and on the node (`UI_LAYOUT`, when Set up is unlocked) so every screen in the house agrees.
  Exercised headlessly: move swaps, hide hides, restore lists.

## v0.27.1 — 2026-09-06 — the satellite's buildings, and the mapping briefing

- **Google Open Buildings** in the place pack, through the earth-engine pack's credentials: V3 footprints within the
  radius into PostGIS, and the Temporal dataset's yearly building count and mean height 2016–2023 as a series on
  `place-point`. The node can say how many buildings the satellite sees, how many the map has, and how the count grew.
  `/history` serves non-hourly series; the bot's `history` tool reads them; the dashboard card says "the satellite sees
  4,100; the map has 2,904 (71%). Since 2016 …".
- **`planetai run place gaps`**: the mapping briefing — satellite footprints with no building drawn, untyped buildings,
  categories with nothing on the map, named places without hours, unnamed streets — written to `out/place-gaps.md`, with
  how to fix it (StreetComplete, Every Door, iD; never Google). **`planetai run place verify`** checks PostGIS,
  Overpass, Earth Engine and both Open Buildings datasets, naming the step that fails.
- Not testable on the dev machine (no Docker, no Earth Engine key): the quadrant geometry and the OSM path are tested
  here; the PostGIS and Earth Engine paths are what `verify` is for, on the node.

## v0.27 — 2026-09-06 — place

**The node knows what is around it.** A `place` pack fetches everything OpenStreetMap has within a kilometre (buildings,
shops, warungs, schools, clinics, temples, roads, green), stores the geometries in **PostGIS** (the database image is now
`postgis/postgis:16-3.4`, same data directory) and answers a fixed set of questions in SQL: buildings and built share,
commercial share, businesses per km², places by category, road kilometres, green share, the walk to the nearest school,
clinic, market and place of worship. Readings on `place-point` (kind `map`), an `Economic|Community` cell (`partial`), a
monthly message, an "Around you" card in the World band, and the bot's `context` tool. Refreshes monthly; recomputes
from storage between. Tested against node #1's coordinates: 2,904 buildings, 540 road segments, 37 mapped places, no
school on the map. Every label says a zero often means unmapped. Google Maps is not a source: its terms forbid it. Open
Buildings and Overture are the next fetches into the same table.

## v0.26.1 — 2026-09-06 — act here

- **The act trigger is on the hero.** When an act-level alert is unanswered, an orange strip under the room's sentence
  names it, quotes its "what to do" line, and carries the **I did this** button. Every such button is now filled, in the
  page's hue. The alerts card is titled "Act here".
- The site's three node pages share the dashboard's tokens (type, eyebrows, pill buttons, radii, accents) and one nav.
  The headline is back to *Observe here. Decide here. Act here.*, and an "Act here" section shows the loop as it
  happens on a phone, beside ρ.

## v0.26 — 2026-09-06 — the frame, and the alpha notice

Air was the first pack and had become the product in every description. Reframed everywhere a person or an agent
reads what this is: **hyperlocal awareness for climate and local challenges, built on distributed design and
production.** The node connects everything measuring one place, from a particle sensor to a satellite, into one
picture sharp enough to act on at the scale of a house, a street, a city, and passes upward what bioregional and
planetary models cannot see from above. README, START_HERE, the agent's own instructions (`agent.py`, `agent_loop.py`,
`AGENTS.md`), the dashboard footer, the install bootstrap.

**Alpha, said plainly.** A band on every page of planetai.fab.city/node0, a note at the top of README and START_HERE,
an `alpha` pill in the dashboard header with the feedback address in the footer, a line on the screen after install, a
line in the install bootstrap: this is an experiment, installing a node makes you part of it, tell **info@fab.city** what
broke, what helped and what did not.

## v0.25 — 2026-09-05

- **The terminal shows its work.** A spinner with the elapsed time on every long step: the install, the image build,
  pulling a model, starting containers, waiting for the node's first answer. ✓ with the seconds when it finishes, ✗ with
  the last log lines when it does not. `planetai update` opens with the logo. Before this, "Installing" went silent for
  two minutes.
- **After the install, a screen.** The dashboard's address on this machine and from your phone, the settings token, the
  three terminal commands that matter, and one key: [o] opens the dashboard, [t] connects Telegram, Enter shows the
  command list.
- **Fixed: the Wall view.** It never laid out as designed (a `display:block` rule beat its flex layout), and reaching it
  from the button hid the header, leaving no way back. The button keeps the header; only `?kiosk=1` hides it, and then a
  small "exit wall" link remains.

## v0.24.1 — 2026-09-05 — the words, again

`README.md` and `docs/START_HERE.md` rewritten as product copy: what you get first (alerts you can act on, a dashboard
that reads like a sentence, a bot you can talk to, a house that learns its rhythm, your data kept, nothing to buy), then
install, the first ten minutes, everyday use, what it will not do, when it breaks. Instructions checked against the
CLI as it is today: the four dashboard views, `planetai agent local`, the Model page, `/act` in Telegram. The rest of
the docs swept for the phrases that read like a machine wrote them.

## v0.24 — 2026-09-05 — the dashboard, redesigned

The design is Tomas's PLANETAI_Node_v5 on the Fab City design system: a warm dark field, Figtree and Funnel Sans, the
brand hues as accents, grain and two slow glows, hexagon marks. Four views: **Now**, **Network**, **Set up**, **Wall**.
Every sentence the designer hand-wrote for one evening's data is now computed from the API: the room's number as a
sentence with its clauses judged against the street, the model and the WHO line; the verb from the last three hours;
a story under every sensor generated from its readings; the day chart annotated from the data ("someone cooked" when
the room beat the street); the sea, the land, the weather and the gap in prose; the Network view drawing flows only
along links that exist. Settings keep their logic (token gate, groups, secrets, packs, the Model page) in the new
markup. Verified headlessly at 1280 and 390: no overflow, no empty region, no `undefined`, fonts loaded.

## v0.23.3 — 2026-09-05

- **The terminal and the dashboard now write Telegram to the same place.** A value saved in the dashboard overrides
  `.env` by design, so `planetai telegram` (which wrote `.env` only) could change the file and change nothing. It now
  writes the dashboard's store too, through the same `/settings` call, with `planetai-cli` in the audit trail. The
  dashboard labels such values "set here · overrides .env" so a shadowed file edit is visible. This is also why a token
  changed in the dashboard did not reach the bot until the loop started reading settings (v0.23.1).

## v0.23.2 — 2026-09-05

- **The bot can now see the sea, the weather, the satellites and the land.** Asked for the swell, it said it had no such
  sensor: true, because no tool reached `/observations`. New tool `context` returns those, grouped and labelled in plain
  words (what the number means, its unit, when it was read); `readings` returns one sensor's hourly history; `sensors` now
  carries every metric a kit reports, not three. Fifteen tools. Tested on node #1's live data: "🌊 The swell is about 1.7 m
  right now, with a period around 11 s and coming from the southwest…"

## v0.23.1 — 2026-09-05 — a leak, closed

- **The agent loop logged a Telegram exception's text, which contains the bot token in its URL.** The token of node #1
  was exposed and has been revoked. Telegram calls now raise a `TelegramError` carrying a status code and advice
  (401: run `planetai telegram`; 409: something else is polling this bot), never the response or URL. `make lint` refuses
  any log call that interpolates a Telegram exception. The app's own `notify()` already followed this rule; the loop did not.
- The loop waits for the node to answer before reading settings, so it does not fall back to a stale `.env` token while
  the app is still starting.

## v0.23 — 2026-09-05 — how the node talks

**Every message rewritten**, both languages, to one shape: an emoji headline (the line the LoRa mesh carries), what is
happening, what it means for the people there, what to do. No means, peaks, correlations, percentages or counts; one
number where it drives the advice. The weekly `agreement` note says the house held back most of the street's air
instead of quoting r; the `digest` reads 🏠 🌳 🛰️ in three lines; the test alert explains itself. "Ask me for the numbers
if you want them" replaces the numbers. The bot's model speaks the same way: explain, emoji, plain text (Telegram shows
Markdown raw, so it is scrubbed too), under 100 words unless asked; the morning brief is a note to the household, not a
status report.

## v0.22.3 — 2026-09-05 — what v0.17 and v0.21–22 claimed, actually shipped

Two edit blocks failed silently on a mismatched anchor and the tool showed no error, so v0.17 shipped without the
compose changes (`DATA_DIR`, the `ipfs` service; `planetai ipfs` would have failed) and v0.21–22 shipped only
`agent_loop.py`: no `agent` service, no `AGENT_*` settings, no Model tab, no `planetai agent local`, no `.env` keys.
Lint passed because nothing inconsistent was present. All of it is in now, verified by count, and:

- **The model ladder is a runtime setting.** `/settings/raw` (admin token) serves unmasked runtime settings to the
  node's own processes; the loop re-reads its ladder from there every minute. The dashboard's **Model** page changes
  which model answers the bot, live, no restart.
- `tests/test_shipped.py` asserts every artifact each version promised, in `make test`.

## v0.22.2 — 2026-09-05

- **Fixed: the image failed to build on the node.** `uvicorn==0.30.*` and `fastapi==0.115.*` were pinned before `mcp` existed; `mcp` needs uvicorn ≥ 0.31.1. Both loosened to `>=x,<1`; the set resolves on Python 3.12 to FastAPI 0.141 and mcp 2.1.1, and the app imports and the MCP round trip pass under exactly that set. `tools/check_requirements.sh` now resolves `requirements.txt` under 3.12 in `make lint`, so a bad pin fails on the dev machine, not in `planetai update`.

## v0.22.1 — 2026-09-05

- `tools/remote-model.sh gptoss | qwen122b`: serve a big local model from a laptop as the node's `remote` rung. llama.cpp with `--jinja` (tool calls), an API key (the model is on the tailnet), the `.env` lines printed for the node. gpt-oss-120b tested through the node's tools: two-second answers, correct tool choice on every question, failures read off `health_check` and ordered.

## v0.22 — 2026-09-05 — a ladder of models

The Telegram bot uses the strongest model it can reach and falls back down: **online** (Anthropic or OpenAI, with a key;
the only rung that leaves your network), **remote** (a bigger local model on your tailnet: a laptop's Ollama, an exo
cluster; no key), **local** (Ollama on the node, always). `AGENT_PREFER=private` never uses online. A failing rung is
skipped for five minutes. `/model` in Telegram shows the ladder and pins one. Every write records `<agent>/<rung>`.
One protocol, OpenAI-compatible chat with tools, which all three serve. Tested: `qwen3:8b` on the remote rung read
three real failures off `health_check` and ordered them; with that rung broken, the loop fell to `qwen3:4b` in seconds.
This is where an AI credential belongs in `.env`, now with code that uses it: `AGENT_ONLINE_KEY`, a secret in the GUI's
Model page. `claude-sonnet-4-6` is the default online model; untested here, no key on this machine.

## v0.21 — 2026-09-05 — a local model runs the node

`planetai agent local`: Ollama on the node's own machine, `qwen3:4b` (or `qwen3:8b` on 16 GB), and `app/agent_loop.py`
in the `agent` compose profile. The model uses the node's thirteen MCP tools, answers the household on the Telegram bot
the node already has, records `/act 23 closed the windows` deterministically without the model, and sends a brief at
`BRIEF_HOUR`. No cloud, no key, no model anywhere but here. Its actions appear in the audit trail as `local-model`.
Tested on this laptop's Ollama against the node's tools: three questions, three correct tool choices, plain answers in
4–11 s. The final answer is requested as constrained JSON, because a 4B model narrates its reasoning as prose even with
thinking off and no instruction fixes that; a schema does. Gemma 3 does not do tool calls in Ollama; 1.7B is too weak
for multi-step tool use.

## v0.20 — 2026-09-05 — agents

**The node as tools for an AI agent.** `app/agent.py`: an MCP server mounted at `/mcp`, behind the admin token, with
thirteen tools over the existing API: status, health_check (each failure names its fix), sensors, alerts, act,
settings_get/set, packs, cells, series, export_day, run_pack_script, maintenance. A remote Claude reaches it over
Tailscale; a local model on the mini reaches it on localhost. Writes record the agent's name (`X-Agent`) in the
actions table; settings changes are audited there too (new stage `settings`). Host operations (update, backup,
restart) are returned as the exact command, since the container has no Docker or git.

- `--json` on `status`, `doctor`, `sensors`, `cells`. Doctor as JSON keeps the fix text and the exit code.
- `planetai setup --answers node.json`: install without a terminal. `install.sh` gained `--sc-user`, `--kind`, `--tz`.
- `planetai agent`: the endpoint, the token, a Claude Desktop/Code config snippet.
- `AGENTS.md` at the root (with `CLAUDE.md` pointing to it): the operating manual for an agent, with the invariants.
- No model on the node, no AI credentials in `.env`: the agent runs where the person already has one and holds the
  admin token. `UPSTREAM_MODEL_URL` returns the day a rule needs a model, with the code that uses it.
- Schema 0.20. `mcp>=2.0` in the image.

## v0.19 — 2026-09-05 — documentation cut by two thirds

29 documents, 28,900 words to 9,900. Plain sentences, no padding, no hedging. Same facts.

- Three Meshtastic guides became one (`MESHTASTIC.md`: radios and jobs, the USB way, the phone app, sensors on radios,
  what went wrong). `START_HERE.md` from 3,600 words to 780. `README.md` from 1,900 to 470.
- `STORAGE.md` and `MAC_MINI.md` now describe the actual setup: the mini keeps the database, TX-NAS-BALI pulls the dumps
  hourly with the read-only token, since 5 September 2026. `tools/nas/README.md` is the two-file recipe.
- The docs gate exempts the changelog from file-existence checks; it is a record and files move.

## v0.18.2 — 2026-09-05

- **Fixed: `planetai storage` stopped halfway** — before the exports, IPFS and the NAS token — on a node with no exports yet. `nex="$(ls exports/x/*.json | wc -l)"`: `ls` fails, `pipefail` fails the assignment, `set -e` ends the function silently. Counts use a `nullglob` array now. Verified by running the real function against a folder with no exports.

## v0.18.1 — 2026-09-05

- **Fixed: the backup check rejected good dumps.** `gunzip | grep -q` under `pipefail`: `grep -q` exits on the first match, `gunzip` gets a broken pipe, the pipeline reports failure, and a valid dump read as "no readings table" — which made `planetai update` refuse to run, correctly, for the wrong reason. Counting matches instead lets the pipeline finish. The same race was in the **mount check**, where it could have refused a real NAS mount, and in five other places across `update.sh`, `install.sh` and the CLI; all now capture the producer's output first and grep the string. `make lint` refuses `| grep -q` under `pipefail` from here on.

## v0.18 — 2026-09-05

**A NAS that pulls.** The node serves `/backups` and `/backups/<file>` behind a new read-only `BACKUP_TOKEN` (minted
by install and update, shown by `planetai storage`), and `/exports` openly. `tools/nas/pull.py` — 60 lines, stdlib,
one 128 MB container — runs on the NAS, asks hourly, fetches what it lacks, and opens every dump to confirm it is a
database before keeping it; nothing is ever deleted there. Pull rather than push: the schedule and the copies live on
the machine meant to survive, the node never holds NAS credentials or a mount, and no folder can silently turn out
to be local. Installed on TX-NAS-BALI for node #1.

## v0.17.1 — 2026-09-05

- **Fixed:** two `.DS_Store` files were committed with `git add -A`; the node had its own untracked copies and `git pull` refused to overwrite them, so `planetai update` failed. Removed from the repo, gitignored, blocked by the pre-commit hook and by `make lint`; `update.sh` sweeps Finder litter before pulling.
- **Fixed:** the schema version was read with `max(version)`, a text comparison, so `'0.4'` beat `'0.14'` and every update since v0.14 reported "schema 0.4 → 0.4" while the database was actually at 0.14. Now the latest applied version, in `update.sh` and `/health`.

## v0.17 — 2026-09-05 — storage

**Where the data lives, where copies go, and what the node gives away.** `docs/STORAGE.md`, `planetai storage`.

- **The live database stays on a local disk**, and the doc says why: Postgres over SMB/NFS corrupts on a power cut. `DATA_DIR` moves it to another internal disk or partition; a NAS is what backups are for.
- **`backup.sh` rewritten**: refuses if `BACKUP_DIR` is on an unmounted `/Volumes`, `/mnt` or `/media` path instead of creating a local folder with the drive's name (the same trap that bit Mosquitto); verifies the dump is a valid gzip containing a readings table before keeping it; `BACKUP_KEEP` days; `LAST_OK`. **Fixed a silent killer found while testing**: `env_get` on a key missing from `.env` made `grep` fail and `set -e` end the script with no output — the first new key would have stopped every nightly backup. The same helper pattern hardened in `update.sh` and the CLI.
- **`BACKUP_REMOTE`**: an rclone destination — S3, B2, R2, Drive, SFTP, WebDAV, Nextcloud — copied after each backup. One binary, no code of ours.
- **`/export?day=`**: one day as open data — hourly means/min/max per sensor and metric, cells, alerts, ρ. Your sensors named by role, not device id; node coordinates to three decimals; no raw, no secrets; CC BY 4.0 stated in the file. Written nightly to `exports/<node>/`. This is data in, data out, made literal.
- **IPFS** as the commons layer: an `ipfs` compose profile (Kubo), `planetai ipfs`, each export added and its CID recorded in `CIDS.txt`. Only exports go — everything on IPFS is public and nothing persists unpinned, which is exactly the right shape for aggregates and exactly the wrong one for backups.
- `planetai storage` (one screen: database size, backup destination and mount state, last run, remote, exports, IPFS; `set backups|remote|keep`), `planetai backup`, `planetai restore <dump>` (safety backup first, typed confirmation).
- `planetai doctor` checks the backup destination is mounted and a backup ran in the last two days.

## v0.16.1 — 2026-09-05 — after the first look

Seven things from seeing it rendered, in the order they mattered.

- **`MG/M³` was a bug**: `text-transform: uppercase` turned µ into M and micrograms into milligrams. The unit line is no longer transformed.
- **The rotated inscriptions are gone.** Outside and model readings are horizontal, right-anchored at the exposed vertices, at 36 and 24 px instead of 28 and 22. The geometry only admits that with a deeper offset (48/96 instead of 36/72), which also gives the stack more depth. Placement proven by pushing the true glyph corners through the SVG transform and testing point-in-polygon against all three hexagons, at three widths.
- **The phone cropped the world hexagon.** The overflow check measured element boxes, not SVG content spilling past them; the SVG now clips to its box and its viewBox carries a margin.
- **One threshold.** Good/moderate at 12 (US) contradicted the WHO 15 line drawn on the strip beneath it. WHO everywhere now: 15 and 35.
- An empty sensor tile said "–". It now says what it is waiting for.
- The world hexagon's mesh read as compression noise in dark mode; hairline, lighter, crisp-edged.
- The header shows the place, from `/health`.

## v0.16 — 2026-09-05

**The dashboard is a zoom: room, street, world.** Three hexagons of the same size offset behind one another: the
room fills and takes its colour; the outside reading runs along the street hexagon's exposed edge at 30°; the world
hexagon carries the isometric mesh inside it and the satellite model along its edge. Then three bands by distance —
each indoor sensor as a tile with a 24-hour trace (`/sparks`), your outdoor sensors and the nearest public ones with
their distance and the wind as an arrow, and the world: the sea with its swell arrow and a sentence about what it
means, the model and its gap to your street, the land as a built/green bar, the weather. The ocean, the land and the
weather were in a table on a second page called "slow sources"; now they have a place.

**Your account's outdoor kits are yours**, whatever their distance. `SC_LOCAL_KM` is gone; `SC_EXCLUDE` leaves out a
kit that belongs to another site. Public references are a separate class and are labelled with how far away they are.

Layout proven headlessly at 1280, 1024 (kiosk) and 390 px: fonts load, the inside texts sit within the room polygon,
the rotated outside and world readings sit inside their own hexagon's band and intrude on nothing (true rotated-glyph
corners, point-in-polygon), no overflow, 24 bars, every band populated. pyflakes joins `make lint`.

## v0.15.1 — 2026-09-05

Three things node #1 showed on a Saturday evening.

- **"Outside" now means your own outdoor sensors first**, then the three *nearest* public references, then the model — the same order in the air-quality rules, the insight digest and the dashboard, pinned by a test. Before, every station within 15 km was averaged equally, so an Uluwatu AirGradient reading 3 sat alongside the street's 15 and the dashboard said 6. The node's coordinates are handed to SQL as `planetai.lat`/`planetai.lon` so rules can rank by distance.
- **Account kits within 2 km are yours** (`SC_LOCAL_KM` default 0.5 → 2): a neighbourhood, not a doorstep. The outdoor kit 1.1 km up the road was being classed as someone else's. `BAD_RADIUS_KM` default 15 → 8.
- **Two spike rules**: `indoor_spike` and `outdoor_spike` fire when PM2.5 is 2.5× today's mean and above 12 (indoor) or 15 (outdoor) — *something changed*, before anything is unhealthy. Inside tripled from 5 to 15 at 18:00Z and only the inside-worse-than-outside rule spoke; a household wants to hear the jump.
- Mesh confirmed working: the gateway carries a BME680 and reports temperature, humidity, pressure, gas and IAQ every 15 minutes. The "silent 90 minutes" alert was the app outage.

## v0.15 — 2026-09-05

**The dashboard, designed.** The grid of six tiles is gone. In its place the Fab City module — a hexagon with its
outline offset behind — made literal: inside fills the hexagon and colours it, outside sits where the outline peeks
out, the model is a faint dashed third hexagon. One verdict sentence in Funnel Sans, one line of why, three quiet
stats that each end in a sentence. A real 24-hour strip from a new `/series` endpoint (hourly indoor bars, outdoor
line, model dashed, the WHO guideline drawn in). Alerts as plain sentences with a hexagon dot for level. Cells as a
honeycomb with the numbers inside. Set up restyled on the system: 8 px controls, switches, blue focus ring, the
token gate with a hexagon behind it. One motion moment on load; reduced-motion respected. Dark mode follows the OS.
Verified headlessly at 1280, 1024 (kiosk) and 390 px: fonts load, every hexagon text stays inside the hexagon,
nothing overflows, 24 bars render.

## v0.14.2 — 2026-09-05

- **Fixed: the app did not start after v0.14.** Turning `PARENT` into a settings-backed function left a module-level `PARENT.startswith(...)` check, which raised `AttributeError` at import and stopped uvicorn before it listened. Passed syntax checks and pyflakes because the name was defined. `TG()` was likewise called but never defined (the definition edit did not match), which would have broken every notification.
- **Fixed: the admin token was never generated.** `.env.example`'s line carried an inline comment, the merge copied it verbatim, and the "is there a value" check saw the comment as a value. The check now reads the value with comments stripped, and the comment moved above the line — the rule set yesterday after the same class of bug.
- **New gate:** import the app with its real dependencies, as uvicorn does, and count routes. In CI always; in `make lint` when the deps are installed.

## v0.14.1 — 2026-09-05

- **Fixed a latent hazard in every update since v0.4:** `update.sh` pulls new code while bash is still reading the file it is executing. Bash reads scripts incrementally, so after the pull it continues from a byte offset in a *different* file — steps skipped, garbage executed, whichever line happens to sit at that offset. Reproduced in a controlled test: the old script ran the new file's final step instead of its own. `update.sh` now copies itself to a temp file on entry and runs from the copy, which the pull cannot touch. This is the likely cause of the v0.14 update leaving the schema at 0.4 and the admin token empty.
- Token generation falls back to `/dev/urandom` if `openssl` is absent, and both `update.sh` and `planetai ui` refuse to continue with an empty token rather than printing a blank.

## v0.14 — 2026-09-05

**A dashboard.** One HTML file the node serves at `/`, on the Fab City design system, no build step.

- **Display**: six tiles that end in a sentence — inside and outside PM2.5, apparent temperature, the CAMS model with the gap to your street, ρ, and a 24-hour trend — plus the alert feed with an **I acted** button on unanswered act-level alerts (that button is how ρ is measured), the node's Index cells as a honeycomb, and vitals. `?kiosk=1` for a small display: big numbers only, 30-second refresh.
- **Sensors**: everything the node knows, yours first, and the slow sources.
- **Set up**, behind an admin token: sources, alerts and Telegram, packs (tick to enable; code packs behind one explicit switch), integrations, keys, the node's place in the tree, bootstrap read-only. A test-alert button. Live within ~20 s, no restart.
- **The settings layer that makes it possible**: a `settings` table overlays `.env`; runtime keys are read through `settings.get()` at use time, so the GUI's changes take effect on the next poll. Bootstrap keys stay in `.env` by design. `GET /settings` (secrets masked), `PUT /settings` (token), `POST /test-alert` (token). `/alerts` now returns each alert's id and whether it was acted on.
- `ADMIN_TOKEN` minted by the installer and added by `update.sh` to older nodes; `planetai ui` shows it and the URLs.
- `tools/check_ui.py`: the script parses, every element id the script touches exists, every API path it calls exists, every field it reads is a real column. Verified by breaking an id and watching it fail.
- Schema 0.14.

## v0.13 — 2026-09-05

**A node can be installed without access to this repository**, so beta testers need no GitHub account.

- `tools/bundle.sh` builds the tarball the website serves: everything git tracks minus CI, dev tooling and tests, plus a `VERSION` file. It refuses to emit a bundle containing `.git` or `.env`, and publishes a SHA-256 alongside.
- `install` now has two paths. With repository access it clones as before; without, it downloads the tarball from `planetai.fab.city/node0`, verifies the checksum, and unpacks it while keeping the operator's `.env`, backups and packs.
- `update.sh` does the same: a node with a `.git` pulls, a node with a `VERSION` re-fetches the published tarball.
- The public setup guide lives at `planetai.fab.city/node0/setup/` — what you need, the four questions, connecting alerts, the five everyday commands, and a troubleshooting table where every row is something that actually happened to a real node.

## v0.12.1 — 2026-09-05 — documentation audit

- **`tools/check_docs.py`**: checks every claim in the docs that a machine can check — files, `planetai` commands, environment variables, relative links, HTTP endpoints, pack names, size claims, and whether README's index matches `docs/`. Runs in `make lint` and CI. Verified by removing an entry from the index and watching it fail.
- **Corrected**: "two containers, four adapters, five rules" (now two containers by default, nine adapters, two domain-blind core rules plus packs); "about 700 lines" (about 1,400); ARCHITECTURE's Stage 0 description.
- **README's docs index** was missing `DEVELOPING.md` and had become a flat list of fifteen names; it is now grouped by what you are trying to do.
- **SPEC §6**: the fired triggers are struck through rather than deleted, `UPSTREAM_*` records why the settings were removed while the contract stands, and the notifier row notes that four channels now exist and the trigger was always an auth lifecycle, not a channel count.
- **`docs/DEVELOPING.md`** gained a table of what `make lint` checks and which real failure caused each gate, plus the two habits: test the artifact rather than a transcription of it, and break something on purpose before trusting a new gate.

## v0.12 — 2026-09-05

**Packs can make things you look at, not only numbers.**

- `out/` is mounted read-write into the app container as `/app/out` — the one writable path a pack has, for images, charts and briefs. Gitignored.
- **`planetai run <pack> <script> [args]`** runs a script a pack ships, inside the container where its dependencies are. With no arguments it lists what is available.
- **`packs/earth-engine/timelapse.py`**: four satellite images of the same place, five years apart, plus a side-by-side HTML page. Each frame is the annual median of clear pixels, so clouds are gone and what you see is the year. Landsat by default (the only archive reaching back far enough with one instrument family — 2010, 2015, 2020, 2025 out of the box); Sentinel-2 for 2016 onward at three times the resolution. `--years`, `--n`, `--gap`, `--km`, `--px`, `--lat/--lon`, `--dry-run`.
- Fixed while building it: `COPERNICUS/DEM/GLO30` in the verifier was an ImageCollection used as an Image, and deprecated. Replaced with SRTM, and a step 6 now probes the four datasets the pack actually reads.

## v0.11.5 — 2026-09-05

- **Fixed:** `planetai packs` treated a pack's `env:` comment lines as settings, so it appended four bare comments to `.env` and reported them as four added settings (the real settings were already present and correctly skipped). A comment now travels only with the setting it explains, and only when that setting is actually added.
- Verified by running the real function from `bin/planetai` against a temporary `.env`, not a retyped copy — retyping it the first time introduced an escaping bug that made the test lie.

## v0.11.4 — 2026-09-05

- **Fixed:** pack `env:` declarations padded the value column for alignment, so a value pasted after the padding produced `VAR=   value`. The shell reads that as "run `value` with VAR empty", and `update.sh` sources `.env` — so filling in the Earth Engine service account made `planetai update` try to execute an email address. Declarations now put the explanation on its own comment line and leave nothing after `=`.
- **Added:** `update.sh` checks `.env` for a space after `=` before sourcing it and names the offending line; `planetai doctor` checks the same thing. A file this central should not fail with "command not found".

## v0.11.3 — 2026-09-05

- **Fixed:** a pack's settings had no route into `.env`. The earth-engine pack documented `EE_PROJECT`, `EE_SERVICE_ACCOUNT` and `EE_KEY_FILE` in its README only, so they appeared in no config file and could not be found. Packs now declare `env:` in `pack.yaml` alongside `pip:`, and `planetai packs` appends the missing ones under a dated marker without overwriting anything. Also added to `.env.example` so a plain `planetai update` picks them up.
- `packs/earth-engine/verify.py`: checks library, settings, key file, credentials and a real query, and names the step that failed.

## v0.11.2 — 2026-09-05

- **Fixed:** `planetai packs` printed a `SyntaxError` instead of the pack list. The `json` helper wrapped snippets after a semicolon, where a `for` loop is a syntax error. The snippet now goes on its own line, so any statement works.
- **Fixed the gate that missed it:** `check_cli_python.py` compiled each snippet standalone, where `for p in d: print(...)` is perfectly valid. It now compiles them as the helper actually wraps them. Verified by injecting a broken snippet and watching the gate fail.

## v0.11.1 — 2026-09-05

- **Fixed:** `planetai packs` read `pack.yaml` with PyYAML, which a node's Apple Python does not have, so the command crashed on node #1. It now parses the one line it needs with awk. Nothing else in the CLI needed a third-party library and nothing should: `tools/check_cli_python.py` now fails the build if a CLI snippet imports one.
- **Fixed:** when the API did not answer, the command printed "(node not answering)" and carried on. It now says so as a warning, points at `planetai doctor`, and lists what is on disk while making clear that is not what is running.

## v0.11 — 2026-09-05

**Ten pack ideas, three built.** `docs/PACK_IDEAS.md` lists ten packs someone could write this month, each with its
Index cell, what it needs, its size and a natural author. Three ship as prototypes:

- **`heat`** (data): Steadman apparent temperature in SQL from any local temp + humidity; heat-stress and danger
  alerts; nights that never cool below 28 °C; a `Social|Community` cell of heat-exposure hours — one honest number for
  the Index's emptiest column.
- **`coast`** (code, key-free): waves, swell and sea temperature from Open-Meteo Marine at the nearest ocean cell,
  refusing to run if that cell is more than 30 km away. Tested live: 1.7 m at 11.8 s off the Bukit, sea 27.4 °C.
- **`earth-engine`** (code, needs a Google Earth Engine project): tree, built, crop and water fractions from Dynamic
  World, Sentinel-2 NDVI, VIIRS night lights, and a land-change score from consecutive AlphaEarth annual embeddings,
  all computed server-side over a 1 km buffer. The worked example of a pack with a dependency and a credential: it
  logs once and idles until configured, and cannot take the node down. Logic tested with a fake `ee`; not yet run
  against a live account.

**Mechanics that came with them**
- `pip:` in `pack.yaml` + `planetai packs`: code-pack Python dependencies are installed into the image once, on
  demand, never at runtime.
- `long_cooldown_ok: true` lets a rule declare a deliberately long cooldown to the rule checker, which otherwise
  flags anything over a fortnight (the test-alert bug).
- `tests/test_packs.py` covers both code packs offline.

## v0.10.1 — 2026-09-05

- **Fixed:** a Smart Citizen kit the node polls directly also arrived through Bali Air Dispatch as `bad-sc-<kit>`, so it was counted twice in the ambient average — and BAD's indoor/outdoor metadata disagreed with Smart Citizen's own on two of your kits. Kits read directly are now skipped from BAD. Seen on node #1 once account discovery was on.
- **Fixed:** `update.sh` pulled a named branch, which skips tags, so the version stamp stuck at `v0.7-N`. Tags are fetched first now.

## v0.10 — 2026-09-05

**The node reads your whole account, tells you more, and hands automations to Home Assistant.**

- **Smart Citizen account discovery** (`SC_USER`): every kit that has published recently, indoor from the API's `exposure` field, local if within `SC_LOCAL_KM` of the node, otherwise a reference station you own. Node #1's account turned out to hold six live kits; it was reading one.
- **`insight` pack**: `digest` every three hours (inside / outside / model / 24h mean / peak / trend); `agreement` daily (Pearson r between indoor, outdoor and CAMS, how much the house filters, the model's bias); `rhythm` daily (the street's worst and cleanest hours, when to open the windows). Pure SQL; Postgres has `corr()`.
- **Home Assistant** via MQTT discovery: local sensors and the latest alert appear as HA entities with no configuration on the HA side. `planetai homeassistant` sets it up. HA does automations; the node never addresses a device.
- **`NODE_KIND`** (`home | business | community | district`): a fourth setup question that sets defaults. Not an Index scale — a house is a Community-scale observation.
- **`docs/USE_CASES.md`**: three things node #1 can say today, with the real numbers from seven days of data: indoor tracks the street at r = 0.55 and the house filters ~30%; the CAMS model tracks the street at r = 0.51 and reads high; it tracks indoor air at r = −0.18. Also: one kit in the account has a dead PM sensor.

## v0.9 — 2026-09-05 — audit

Six defects found by auditing rather than by hitting them in the field. Each has a gate now.

**Wrong, silently**
- `POST /aggregates` stored a child's hourly means as `kind='sensor'`, so they entered the `stats` view and could be averaged into "nearby public sensors" as ambient reference. Children are `kind='child'` and belong in `observations`. Found before the district node made it matter.
- `NODE_TZ` was written by setup and **read by nothing**, while `.env` claimed daily buckets used it. Postgres defaulted to UTC, so `current_setting('TimeZone')` put local midnight and local hours eight hours out in Bali: the WHO exceedance-day cell split days at 08:00 WITA, and the cooking-hours rule fired at dawn. The database session timezone now comes from `NODE_TZ`.
- `packs/air-quality` declared its 24h-mean cell `partial` with a comment saying the core would promote it. The core only ever demotes. The cell could never be `live` while `COVERAGE.md` and `START_HERE.md` both promised it would be. It now declares `live` and is demoted until 12 hourly buckets exist.
- Any loop's exception overwrote `state["last_error"]`, which `poll_once` clears when its sources succeed — a permanently broken rules thread looked healthy. Each loop keeps its own key.
- The poll loop was an anonymous lambda, so its thread and every error it logged were named `<lambda>`.
- MQTT ingest counted every reading as new, including duplicates dropped by `ON CONFLICT`.

**Closed while it is free**
- `POST /aggregates` accepted anything that could reach the port. It now requires `Authorization: Bearer <AGGREGATE_TOKEN>` and refuses outright when no token is set. No child exists yet, so nothing breaks.

**Removed**
- `UPSTREAM_MODEL_URL` and `UPSTREAM_COMPUTE_URL` from `.env.example`: no code reads them. The contract stays described in `ARCHITECTURE.md`; the setting comes back with the code that uses it.

**New gates**
- `tools/check_rules.py`: parses `init.sql` for every table and view, then checks each rule and cell — unknown columns, message placeholders the SQL never returns, cells with no `value` column, and cooldowns over a fortnight. The last of those is exactly the bug that made `test-alert` report a dead node for 69 days. Verified against four deliberately broken rules.
- `tests/test_logic.py`: cell provenance (demote a `live` claim below `min_buckets`, never promote `partial`, show the shortfall in the note) and per-loop error isolation.
- Both run in `make lint` / `make test` and in CI.

## v0.8.2 — 2026-09-05

**First real packet from the gateway reached node #1**, and the day-long silence had one cause: the fleet channel was
a secondary, and radios send telemetry on the primary. `mesh-provision.sh` now makes the fleet channel the primary.
Also documented: enabling the XIAO's serial console and debug log to read the radio's own output over USB; the
Mosquitto config that was missing for a day; connection logging on the broker.

## v0.8.1 — 2026-09-04

**First radios provisioned; the failures documented.**

- `tools/mesh-provision.sh`: one command per radio over USB (region, preset, names, role, telemetry and position intervals, fleet channel; first radio creates the channel and saves its URL, the rest import it). No pairing, no PIN.
- `docs/MESHTASTIC_FLEET.md`: the laptop procedure, naming and roles, the channel file as a key, the CLI's enum values, and field notes: region `0` explained last week's silence; UF2 drag fails on macOS 26 (FSKit) regardless of bootloader version and serial DFU is the working path; the flasher offered a non-release 2.8.1, the fleet is on stable 2.7.26; Seeed's verified Grove list excludes the BME680.
- `docs/MESHTASTIC_APP.md`: Part 0 fast path; the -36 paragraph corrected (the earlier "update the bootloader" explanation was wrong for this case); a sensor on the gateway; two symptom rows.
- First Tracker L1 flashed to 2.7.26 over serial DFU and provisioned as `SENSOR` on channel `planetai`, `SG_923`.

## v0.8 — 2026-09-04

**Meshtastic and Reticulum ready.** Both behind compose profiles, off by default; node #1 stays two containers until
you turn one on.

- **`planetai meshtastic`**: creates broker credentials, starts Mosquitto (`mqtt` profile, password required, LAN-reachable on 1883), restarts the node with its MQTT thread on, prints the exact gateway settings (region for your city, address, credentials, JSON output on, uplink/downlink on), waits for the first packet, lists the sensors it saw.
- **Meshtastic adapter** (`sources.meshtastic_message`): pure function, tested offline against 2.x payload shapes. `telemetry` → readings (environment + air quality + battery/LoRa health), `position` → sensor coordinates from GPS, `nodeinfo` → name. Protobuf topics ignored; unknown fields logged once. Pressure converted hPa → kPa to match the rest of the node.
- **Alerts over the mesh**: `MESH_ALERTS=1` + the gateway's node number; act-level alerts go out on the downlink topic, first line only, capped at ~200 bytes.
- **DIY pods**: the same broker takes `planetai/sensors/<id>/<metric>` from anything on the WiFi.
- **`planetai reticulum`**: a bridge container with an LXMF address. Inbox: `act <id> [note]` from Sideband records the action (closing the loop with no internet). Outbox: act-level alerts to `RETICULUM_ALERT_DESTINATIONS`. TCP server on 4242 now; RNode LoRa is a commented block in `config/reticulum/config` plus a device mapping (Linux).
- `/health` gains `mesh` (root topic, gateway, packet count) when MQTT is on; doctor checks the broker, packets and bridge when their profiles are on.
- Found by the new tests: the root topic parse included the protocol version segment, which would have doubled `/2/` in every downlink. Fixed before it shipped.
- `docs/NETWORKING.md` and `docs/sensors.md` updated; SPEC §6 marks the MQTT trigger fired and splits Reticulum into shipped (bridge) and parked (node-to-node transport).

## v0.7 — 2026-09-03

- **`planetai mesh`**: joins the node to a Tailscale tailnet with its own name and Tailscale SSH on, so `ssh bayu-2` and `planetai update` work from anywhere with no ports opened and no keys managed. Uses the Homebrew daemon on macOS so a headless mini stays reachable with nobody logged in. `TS_AUTHKEY` for unattended joins. `MESH_NAME` recorded in `.env`.
- **`docs/NETWORKING.md`**: the three-layer evaluation. Tailscale for reachability (shipped, Headscale as the recorded exit). Meshtastic for sensors and alert delivery off-grid (next; it is the missing pipe in the FAB26 six-month program, and the gateway must point at the node's own broker, not the public default). Reticulum parked with a precise trigger.
- SPEC §6: the Tailscale and MQTT triggers are marked fired; Reticulum added with its trigger.

## v0.6 — 2026-09-03

**One command to a running node.** Applied the Omarchy install pattern: a URL that does everything, a form that
asks only what it cannot detect, phased steps logged to a file, a plain error screen, and one CLI so operators never
touch a Makefile, a flag list or a YAML file.

- `install`: `curl -fsSL planetai.fab.city/install | bash`. Gets git if missing, clones or updates `~/planetai`, hands off to `planetai setup`. Re-runnable.
- `bin/planetai setup`: three questions. Name. **A place name** (Open-Meteo geocoding, with OpenStreetMap as fallback for neighbourhoods and sub-districts) → coordinates, time zone, country, and whether the location falls inside one of the four pilot bounding boxes, which sets the city key and turns the Bali archive on or off. Sensor, or none. Then a summary, a confirm, and the install with a log.
- `planetai telegram`: validates the token with `getMe`, waits for your message, reads the chat id from `getUpdates` itself, writes `.env`, sends a hello, restarts. No JSON to read.
- `planetai test-alert`: a temporary pack with a rule that always fires; waits, removes itself, hands you the alert id. Your rules are untouched.
- `planetai act <id> [note]`: records the action and prints ρ.
- `planetai status | doctor | sensors | cells | logs | update | backup | config | start | stop | restart`. Doctor names the fix next to each failing check.
- `planetai geocode <place>` to try the lookup without installing.
- README and START_HERE now lead with the one-liner; the flag and by-hand routes remain below it.

## v0.5 — 2026-09-03

**Location independence.** Read the docs as someone setting up in Delhi or Santiago and most of it did not work.

- **Functional, not editorial:** the indoor/outdoor comparison, the flagship service, only fired in Bali. It looked for nearby public reference *sensors*, which exist in the node's data only where a network adapter supplies them. CAMS ships globally but lives in `observations`, so the rule could never fire elsewhere. The two comparison rules now resolve "outside" in order of preference (nearby public sensors, then the CAMS model point sample) and the message names which one it used. Added `outdoor_pm25_high` for nodes whose own sensor is outside.
- `docs/START_HERE.md` rebuilt around **your five inputs**: coordinates, time zone, city key, sensors or none, and what "outside" means where you are. Includes how to find each, how to test whether your city runs a CKAN portal, and what to expect when there are no `bad-` rows (everywhere except Bali). Bali is now a labelled worked example rather than the spine.
- `presets/delhi.env` — a non-pilot site, so the docs' own counter-example is real.
- Bali-specific claims corrected across README, `sensors.md`, `PREFILL.md`, `PLATFORMS.md`, `MAC_MINI.md` (the UPS advice now says where it applies), `ARCHITECTURE.md` (the cell table is labelled an example) and `PRODUCT.md` (states that its numbers are one market's and not portable).

## v0.4.3 — 2026-09-03

- **Security fix:** httpx logs every request URL at INFO, and Telegram carries the bot token in the URL path — so a live credential was written into the container logs, and therefore into any log someone pasted for support. Found when exactly that happened during node #1's update. httpx/httpcore loggers are now set to WARNING, the notifier logs `telegram -> <chat> ok` instead, and exception text is never interpolated (it contains the URL too).
- The installer and updater now scan the container logs for an exposed token and tell you to revoke it.
- `docs/START_HERE.md` gained a short section on treating the token as a password, and the "send this when you ask for help" block now says to scan the log first.

## v0.4.2 — 2026-09-03

- **Fixed:** `app/Dockerfile` listed modules explicitly (`COPY main.py sources.py index.py ./`), so `packs.py` (v0.2) and `bootstrap.py` (v0.4) were never in the image and the app crashed on import after updating. Now `COPY *.py ./`.
- **Added:** `make lint` fails if the Dockerfile enumerates modules; the installer and updater doctors compare the number of modules on disk with the number inside the running container, so a missing file is caught before "done" is printed rather than after.

## v0.4.1 — 2026-09-03

Both found by running `./update.sh` on node #1 — the update path's first real use.

- **Fixed:** a stray comment injected into the `stats` view's `FILTER (WHERE …)` clause swallowed a closing bracket, so the schema failed to apply on any node. Comments no longer sit inside SQL expressions.
- **Fixed:** `backup.sh` read `BACKUP_DIR` and `NODE_NAME` from `.env` without stripping inline comments, so the backup path became `./backups                   # or a NAS mount, e.g. …`. It now strips comments and quotes.
- **Added:** CI spins up a real Postgres and applies `init.sql` **twice**, then selects from every view. A schema that doesn't parse, or isn't idempotent, can no longer be released. The paren-balance check in `make lint` catches it earlier and offline.

## v0.4 — 2026-09-02

**Updating a running node actually works now.** Found while planning node #1's upgrade: Postgres runs `init.sql` only
when the data volume is created, so every schema change since v0.1 would have silently missed an existing node, and
`stats` could not be swapped with `CREATE OR REPLACE` because columns moved.

- `init.sql` is now the complete schema, fully idempotent, applied on both fresh install and update.
- **`update.sh`** — backup (refuses to continue if it fails) → preserve local `rules.yml`/`.env` → pull → apply schema → add new `.env` keys without overwriting yours → rebuild → verify readings/alerts/actions survived, with counts.
- `schema_version` table; `/health` reports code version and schema version, and says `pre-0.4 (run ./update.sh)` when they've diverged.
- `make bootstrap` backfills CAMS history and NASA POWER normals onto a node that predates v0.4.
- `docs/UPDATING.md` — the workflow, rollback, tarball updates, and why editing `config/rules.yml` is the wrong place to tune a threshold.

**A node is useful before it has a sensor.** Coordinates are the only requirement.

- **First-run bootstrap** (`app/bootstrap.py`): 92 days of hourly Copernicus CAMS PM2.5/PM10, NASA POWER monthly climatology (satellite-derived, 1981–present), and one OpenStreetMap reverse geocode so messages name a place. ~2,200 rows, about a minute, no key, anywhere on earth. Runs once when `readings` is empty; `BOOTSTRAP=0` opts out.
- **`openmeteo_air` adapter** — Copernicus CAMS current PM2.5, PM10, dust, aerosol optical depth, CO, NO₂, O₃, UV. Free, key-free, global, every poll.
- **`cold-start` pack** — three rules that need no hardware: today's modelled air, today vs 40 years of normals, and (once a sensor exists) the weekly sensor-vs-model gap. That gap is the local signal a global grid cell cannot see.
- **Site presets** — `--preset bali|barcelona|boston|santiago` sets coordinates, timezone, language and the city's CKAN portal in one flag. Anywhere else works with `--lat --lon`.
- **`docs/PREFILL.md`** — what arrives free, what needs a key (OpenAQ now requires one; Flood Hub and Sentinel need accounts), and what I refused to embed: static datasets that go stale in git, and any pre-seeded demo data.
- Installer now *requires* coordinates and no longer warns about a missing sensor as if it were a problem.

## v0.3 — 2026-09-02

**The node reaches past its own address.** Evaluated against the Fab City Index's 4 pillars × 5 scales using the
registry's own 32 sources; the node was filling one corner of it.

- **Schema:** `sensors.kind` (`sensor | portal | model | survey | child`), `sensors.scale`, `sensors.cadence`. Additive — a v0.2 node updates in place. New `observations` view (latest value per slow source); `stats` is now sensors-only, because a city statistic has no business in a 24-hour rolling mean.
- **`ckan` adapter** — reads any CKAN portal, which covers four of the registry's `governance|city` sources (Barcelona, Boston, Santiago, Bali) with one function. Publishes datasets total, updated-in-90-days, and the share.
- **`openmeteo` adapter** — global model point sample at the node's coordinates. Free, key-free, works anywhere on earth: a node with no sensors at all still has something true to say. Planet scale, boundary condition, never aggregated upward.
- **`open-data-health` pack** — turns portal maintenance into a `Governance|City` cell and warns when a portal goes quiet.
- **`docs/COVERAGE.md`** — the full matrix, what fills today, and the seven empty cells. Finding worth stating: `governance|community` has no source in the registry, and ρ is that source.

## v0.2 — 2026-09-02

**The core is now domain-blind.** Air moved out of `app/` and `config/` into `packs/air-quality/`.

- `config/rules.yml` keeps two rules that work whatever a node measures (dead sensor, daily pulse). The three PM2.5 rules are now `air-quality/indoor_pm25_high` etc.
- `app/index.py` no longer mentions PM2.5. It computes ρ (Governance, every node, every domain) and evaluates cell SQL that packs declare — policing provenance, including refusing a `live` claim before the data supports it (`min_buckets`).
- The test: no threshold, message or pillar mapping in `app/`. Adapters still name metrics, because devices do — that's a driver translating fields into the schema.
- New: `docs/DOMAINS.md` — what a node measures today, and what water, energy, fabrication, noise, comfort and soil packs would look like, with the decision each drives.
- **Updating a v0.1.1 node:** your three air rules move into the shipped `air-quality` pack and keep working; ids gain the `air-quality/` prefix, so existing alert cooldowns reset once. Nothing else changes.

## v0.1.1 — 2026-09-02 (same night as v0.1)

Fixes from the first live install at Fab Lab Bali, and the first two asks from the field.

**Fixed**
- `last_error` in `/health` now clears when every source succeeds on a poll. It used to show the last failure forever. Several failing sources are joined with ` | `.
- Installer: scripts shipped without exec bits; `COPY` syntax failed on Docker's legacy builder; `index.py` wasn't copied into the image; a port clash with another container failed ten seconds in instead of before building. All fixed; `APP_PORT` in `.env` moves the host port.
- `.env`: inline comments after empty values confused the parser (phantom `PARENT_API_URL`). Comments now sit on their own lines; values are stripped in code; a parent URL without `http(s)://` is ignored with a warning.
- Rules are mounted as a directory (`config/`) so editors that save-by-replace (TextEdit) don't break the mount.
- `make restart` applies `.env` changes; `daily_pulse` prints integers and says "no public sensors in range" instead of a dash.

**Added**
- **AirGradient** and **PurpleAir** adapters — both read directly over the LAN, no cloud. EPA 2021 correction applied; raw stored beside corrected. PurpleAir path reproduces Bali Air Dispatch's published Klungkung example.
- Installer flags `--airgradient`, `--purpleair`, `--indoor`, `--no-bad`; env `AIRGRADIENT_HOSTS`, `PURPLEAIR_HOSTS`, `SENSOR_INDOOR`.
- Linux: installer installs `make`/`curl` if missing. Windows: WSL2 detected; uses Docker Desktop's engine instead of trying to install one.
- `docs/PLATFORMS.md` — Linux, Raspberry Pi, Windows (WSL2), Intel Mac: only what differs.
- `docs/START_HERE.md` — choose-your-sensor, pre-flight checks for each, multi-sensor install examples.

**Added — packs (community extension point)**
- `app/packs.py`: scan `packs/`, merge `rules.yml` (ids namespaced), `cells.yml` (extra Index cells), and optionally load `adapter.py`. `GET /packs` lists what's loaded.
- **Data packs** (rules/cells, no code) load automatically. **Code packs** (`adapter.py`) stay off until `PACKS_ALLOW_CODE=1` — the node logs the file to read first.
- Worked example: `packs/example-cooking-hours/`. Model and tiers: `docs/PACKS.md`.

**Repository**
- `LICENSE` (Apache 2.0 full text), `NOTICE`, `CONTRIBUTING.md`, issue templates (node problem / new source), CI lint + offline adapter tests (`tests/test_sources.py`, `make test`), README rebuilt for the public repo, banner on the Fab City design system.
- Landing page for `planetai.fab.city/node0/` (in the planetai site repo, not here) — rebuilt v0.2 with the packs section.

**Not changed**
- Rules, schema, Index contract, ρ ledger. A v0.1 node updates in place: `git pull && docker compose up -d --build`.

## v0.1 — 2026-09-02

First running node. Smart Citizen 19880 + Bali Air Dispatch → Postgres → five SQL rules → Telegram. `GET /cells` (fci-cells-v0), `POST /actions` (ρ). Node #1: "Bayu 2 – Indoor", Kuta Selatan.
