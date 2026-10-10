# Beta readiness review, 6 September 2026

Reviewed: `fabcity/planetai-node` at v0.30 (a5a67bb), the site at planetai.fab.city, node #1 (read only). Method:
every file in the brief read; a clean-machine rehearsal (Lima, Ubuntu 24.04 arm64, no Docker, no credentials) with the
Santiago and Barcelona presets; every subcommand and endpoint exercised on the clean node; 48 hours of node #1 logs; a
security audit and a site inventory by two subagents (their reports are in the session scratchpad; the facts are
carried here). Fixes are one per commit, gates green, on `main`, released as **v0.31** (tag `v0.31`); the same commits sit on branch `beta-review-2026-09`.

Multipass, OrbStack and a fresh macOS account all need administrator rights this laptop does not have, so the macOS
first-run path was not rehearsed. Everything else in the brief was.

## The three decisions only Tomas can make

1. **What a tester installs.** `curl planetai.fab.city/install | bash` fetches `install` from `main` on GitHub and
   clones `main`: testers run whatever was last pushed, and `planetai update` follows `main` HEAD. The tarball fallback at
   `/node0/get/` is **v0.12** with a checksum beside it. Options: (a) accept `main` as the beta channel and refresh the
   tarball with `tools/bundle.sh` + a site deploy; (b) pin `PLANETAI_REF` to a tag in the site's `/install` stub and
   change `update.sh` to follow tags (a code change, not made). The site footer links the private repo
   `github.com/fabcity/planetai` on all four pages (404 for the public); pointing it at `planetai-node` is a one-line
   site change.
2. **Raspberry Pi.** No arm64 build of `postgis/postgis` exists (checked: 16-3.4-alpine, 16-3.4, 16-3.5 are amd64 only).
   On any arm64 Linux machine the database container dies with `exec format error`. Either pick another image
   (`imresamu/postgis` is multi-arch; or `postgres:16` + `postgresql-16-postgis-3` from apt in a small Dockerfile) — a
   dependency change — or keep the docs' new wording ("not yet") and drop the Pi from the site. Switching node #1's image
   later means an alpine→debian collation change; do it on a fresh volume via backup/restore, not in place.
3. **Who may write to a node on the LAN, and what leaves in a dump.** `POST /readings` needs no token: on the clean
   VM a curl from the LAN created a "local, indoor" sensor at 999 µg/m³ and two act-level alerts went out within a
   minute. `POST /actions` needs no token because the household's *I did this* button must work on any phone; a stranger
   on the WiFi can therefore raise ρ. `pg_dump` includes the `settings` table, which on node #1 holds the Telegram bot
   token; dumps go to the NAS and any rclone remote, and STORAGE.md said they held no tokens (corrected). Three
   choices: token on `/readings` (nothing ships that uses it yet); leave `/actions` open (my recommendation for the
   beta, now that it rejects unknown alerts and foreign stages); `pg_dump --exclude-table-data=settings` (dashboard
   settings would then not survive a restore) or encrypt at rest.

**Decided by Tomas, 6 September (later the same day), and done in v0.32:** (1) `main` is the beta channel; the
tarball is refreshed by the release and the site footer points at `planetai-node`. (2) The Raspberry Pi is dropped
for the beta; the site stops promising it. (3) Token on `POST /readings` (d55e115), settings rows out of dumps
(058b60e), a read-only role for pack SQL (f8e638e); `POST /actions` stays open for the household's button. Spanish:
drafted by the assistant on branch `es-messages` (PR #1) for Tomas to read as a native speaker before it ships.

Smaller calls listed under the dimensions: the cell count to state publicly (node #1 reports 8 rows, 6 distinct
cells; COVERAGE.md says seven; the site says seven and "4 of 20"; the dashboard says 8/20); `daily_pulse` still in
`config/rules.yml` although v0.30 says the reports replaced it (deleting it is yours); the heat pack's Social cell
reporting 0.0 hours on a node with no indoor sensor (cell SQL); every site narrative change (diffs in §9).

## Can Vivanco and Lucas install tomorrow?

**Yes, with two conditions.** Condition one: they install from v0.31 (the release made by this review), not v0.30 —
on v0.30 a no-sensor install ends in a red "Something went wrong" box, is named "Ubuntu" on Linux, cannot update, and a
failed update deletes `.env`. Condition two: their machine is a Mac or an x86 Linux/WSL2 box, not a Raspberry Pi. Both
must be told plainly that nothing is in Spanish yet and that Telegram `/act` replies do nothing until they run
`planetai agent local`; `docs/BETA_TESTER_GUIDE.md` says both. Rehearsed on a clean machine: the v0.31 path reaches the
green screen in 258 s on a machine that had no Docker (23 s once the images exist).

## Scores

| dimension | v0.30 | after v0.31 | why |
|---|---|---|---|
| 1 Functions | 3 | 7 | Act loop, backup, MCP, update and rollback work; four endpoints 500'd, bootstrap never ran, update could delete `.env`. Restore into a second node: see §1. |
| 2 UI/UX | 6 | 7 | No overflow at 375/768/1440; first-run copy is good; an empty orange bar on every node, a wrapping nav label, low-contrast labels (10.5 px eyebrows, muted nav) remain a design call. |
| 3 Language | 2 | 2 | Nothing in Spanish; briefings and the test alert are English-only even for `id`; jargon (ρ, cell) explained once on the dashboard, `DIDO`/`PITO` nowhere. Inventory below; nothing machine-written. |
| 4 Setup | 2 | 7 | The stranger hit three walls in a row; all three fixed. Telegram guided setup not rehearsed with a real bot (no token available to me). |
| 5 Reliability | 7 | 7 | Restart, 10-minute network loss, dead reference API, disk at 99% all survived with no crash loop and no duplicate alerts; timezone correct for Santiago and Madrid; schema idempotent. Nightly backup was silently never scheduled on node #1 and never writable on Linux. |
| 6 Security | 4 | 6 | Read-only token unmasked every secret (fixed); LAN writes without a token remain by decision; pack SQL runs as DB owner; `.env` was executed as shell (fixed); pip-audit clean. |
| 7 Maintenance | 5 | 7 | Doctor names a fix for every failure and now checks the schedule; issue templates exist; `release.sh` called a script that did not exist (fixed). Log rotation missing on db/agent/ipfs containers. |
| 8 Documentation | 5 | 7 | START_HERE reaches the first alert; counts were stale in five places (fixed, gated); `/act` and Raspberry Pi promises corrected. |
| 9 Website | 4 | 4 | Not changed by this review (narrative). Contradictory cell counts, a legacy "four action agents / open hardware" block, an unverifiable ρ 0.67, mixed alpha/beta, the private repo in every footer, a v0.12 tarball. Diffs in §9. |

Severity: **blocker** = a tester cannot install, loses data or is misled about the node's state; **serious** = a tester
will hit it in the first week; **polish** = would embarrass, not break.

## 1. Functions

**Exercised on the clean node**: every subcommand (`planetai`, `nonsense`, `status`, `status --json`, `doctor`,
`doctor --json`, `sensors`, `cells`, `packs`, `storage`, `storage set`, `ui`, `agent`, `run`, `geocode`, `mesh status`,
`logs`, `config` (EDITOR=true), `telegram` (fake token → rejected), `test-alert`, `act`, `backup`, `update` (from v0.29,
with a forced build failure and the documented rollback, then for real, then again), `homeassistant`, `ipfs`,
`reticulum`, `meshtastic` (60 s), `agent local` (10-minute cap), `restore` (see below), `version`). Every GET route with
valid and invalid input; every POST with and without a token; MCP `tools/list` and one call per tool.

| # | severity | finding | evidence | status |
|---|---|---|---|---|
| 1.1 | blocker | Every Linux install is named **"Ubuntu"**: `install.sh` sourced `/etc/os-release`, which sets `NAME`, the variable holding `--name`. | both VMs: `NODE_NAME=Ubuntu` in `.env`; dashboard header "Ubuntu" | fixed 6cd6d3c |
| 1.2 | blocker | Choosing *None yet* for the sensor wrote the option text into `NODE_KIND` (`bin/planetai` reused `kind`). `.env` line: `NODE_KIND=None yet. Start with the global models…`. | both VMs; `planetai update` → `./.env: line 3: yet.: command not found`, exit 127 | fixed 8a1e050 |
| 1.3 | blocker | `update.sh` executed `.env` as shell (`set -a; . ./.env`) and, when that failed, its EXIT trap **deleted `.env`** (`BASH_SOURCE[0]` was the sourced file). | reproduced with the v0.30 script in a temp dir: folder left with only `update.sh` and the log; both VMs lost `.env` | fixed a840460, 86a5380 |
| 1.4 | blocker | `GET /export`, `/history`, `/readings` returned 500 on every call (`str.isoformat`; untyped NULL params). The nightly export was therefore never written; MCP `export_day`/`history` failed. | node #1: `curl /export?day=2026-09-05` → 500, `exports/` empty; VM: same; traceback `AttributeError: 'str' object has no attribute 'isoformat'` at main.py:611/673; `IndeterminateDatatype could not determine data type of parameter $1` | fixed e2be884 |
| 1.5 | blocker | The zero-hardware bootstrap (92 days CAMS + NASA normals) **never ran** on a wizard install: the wizard's `--force-recreate` killed the first container mid-bootstrap and every later start saw a non-empty table. | both VMs: only 14 rows after install; run by hand the same code fetched 4,416 + 60 rows in seconds | fixed 461d15a |
| 1.6 | serious | `if not PARENT:` tested a function; "push to parent failed: Request URL is missing an 'http://'" logged hourly on every node. | node #1 48 h log, once per hour; VM log | fixed db271a8 |
| 1.7 | serious | Wizard ignored `presets/`: Santiago and Barcelona nodes got no `CKAN_PORTALS`, so Governance\|City cannot fill. | both VMs: `CKAN_PORTALS=` | fixed 52fdc67 |
| 1.8 | serious | `planetai packs` (a listing command) rebuilds the image and appends settings to `.env`. | VM: "installing into the image: earthengine-api (rebuild…)" on a plain `planetai packs` | fixed 5ba16af: the listing only lists; `planetai packs install` writes |
| 1.9 | serious | `planetai reticulum` leaves the bridge container restart-looping on the clean node. | VM2: `planetai-reticulum-1 Restarting (1)` | open; log in §1 addendum |
| 1.10 | polish | `planetai run` lists scripts with garbled descriptions (first code line instead of a docstring). | VM: `planetai run place refresh  import os, sys` | fixed 31c21fb |
| 1.11 | polish | `planetai config` without a tty: `a: unbound variable`. `planetai telegram` `getUpdates` takes the last update even when it is not a message. | VM log | fixed 31c21fb |
| 1.12 | polish | `/alerts?limit=-1`, `/readings?limit=0`, `/export?day=2026-13-45` → 500. | VM | fixed e2be884, bbbae70 |
| 1.13 | polish | `backup.sh` reported an HTTP 500 from `/export` as "node not answering". | VM update log | fixed e32cba2 |
| 1.14 | polish | `release.sh` called `tools/package.sh`, which does not exist: the tag would be pushed and the script would fail. | `ls tools/` | fixed 6cefa6c |

**Act loop, end to end (VM1, v0.30 and v0.31):** `planetai test-alert` → alert #7 in 22 s → `planetai act 7 "closed the
windows"` → ledger row → `/rho` `{"alerts_act":4,"acted":1,"rho":0.25}` → dashboard "ρ — 4 asks in thirty days, 1
answered". Telegram leg not exercised (no bot token available to the reviewer; the code path is `notify()` →
`sendMessage`, identical to node #1's, which delivered 63 alerts).

**Zero-hardware start:** first alert within 60 s of install: `cold-start/modelled_air_today` ("🛰️ What the satellites
think your air is like today…"). Then `daily_pulse` ("🌅 Good morning from your node") fired at 19:59 local on the first
rules pass — the "good morning at the wrong hour" v0.30 says it removed (`config/rules.yml` still carries it; deletion is
yours).

**Update path (VM1):** v0.29 → forced build failure → node kept serving v0.29 (`ok True`), but `.env` already said the
new version, so `/health` lied after the documented rollback (`git checkout v0.29; planetai restart`). Fixed for future
updates (bbb19db: stamp after build). Real update: "Nothing was lost: 4511 readings, 7 alerts, 5 actions"; second
update idempotent (`schema 0.20 → 0.20`); `.env` and `.env.before-update` both 600.

**MCP:** 17 tools listed (`status health_check sensors context readings daily_report history alerts act settings_get
settings_set packs cells series export_day run_pack_script maintenance`); wrong token → 401; no token → 401. Per-tool
calls: see §1 addendum (VM2 run).

**Backup and restore into a second fresh node:** see §1 addendum.

**Every pack loaded; one rule fired:** `/packs` lists all nine on both VMs; rules fired on the VM: `cold-start`,
`daily_pulse`, `insight/digest`, `air-quality/indoor_pm25_high`, `air-quality/inside_worse_ventilate`, `_test`.

## 2. UI/UX

Measured with `document.documentElement.scrollWidth` against `innerWidth` in the Browser pane at 375, 768 and 1440,
on node #1 (populated) and on the VM nodes (first run). Screenshots inspected in the pane.

| # | severity | finding | evidence | status |
|---|---|---|---|---|
| 2.1 | serious | **An empty orange bar** rendered under the hero on every node with nothing to act on: `.actstrip{display:grid}` beat the `hidden` attribute. | screenshots node #1 @375, VM2 @375/1440; `#actstrip hidden:true display:grid` | fixed 7e4b2b9 |
| 2.2 | polish | "Set up" wrapped onto two lines at 375 px (button height 50 px vs 34). | JS measurement | fixed 7e4b2b9 |
| 2.3 | polish | Contrast: eyebrow labels at 10.5 px in `--mute` (≈2.4:1 by my calculation), nav buttons 14 px ≈2.4:1, the big hero number ≈1.8:1 on its glow. 21 text nodes under 11 px at 375. | JS computed styles (approximate: backgrounds are gradients) | open (design) |
| 2.4 | polish | Provenance pills: no element reads exactly "live/partial/mock" on the Now view; provenance is carried by colour (green measured, blue derived) and by the Network view's cell rings. A colour-blind tester cannot tell them apart. | DOM scan | open (design) |
| 2.5 | polish | Network view says "8/20 cells … 8 of the twenty Fab City Index cells have a source": it counts rows (three Environmental\|Bioregion rows), not cells (6). | node #1 Network view text | decision (cell count) |
| 2.6 | polish | `info@fab.city` is in the HTML footer twice but not in the Now view's visible text; the alpha pill is. | JS `innerText` | open |

Works as documented: first-run state ("No sensor yet. The model says 7 for this square of the map. … Add a sensor under
Set up and the room fills in."); Now/Network/Set up/Wall views; distance bands (Room · Street · a few hundred metres ·
1 km · Region · 11 km and beyond · Act here); act button appears with an open act-level alert and hides otherwise;
Arrange: hide a card → `localStorage planetai_layout {"hidden":["room"]}` → Done; node-side `UI_LAYOUT` via
`PUT /settings` applies to every browser (VM2); `?only=room` shows one band with header hidden; `?kiosk=1` opens Wall
(208 px number, 30 s refresh); `prefers-reduced-motion` rule present; no `<img>` (SVG only); 0 unlabeled buttons;
`lang="en"`. Telegram messages on a phone: not rendered (no bot); alert texts are 2–4 short lines plus `#id`, the
briefings 6–9 lines; both fit a phone screen by length.

## 3. Language

**Spanish: nothing at v0.31.** `ALERT_LOCALE` accepted `en | id` only (`app/settings.py:46`). Inventory of what a Santiago or
Poblenou tester reads. The first four rows have an `es` set on branch `es-messages` (PR #1, 6 Sep), written by the
assistant for Tomas's review; the rest stay English by decision:

| surface | strings | languages today |
|---|---|---|
| Alert templates (`packs/*/rules.yml` + `config/rules.yml`) | 23 (`indoor_pm25_high`, `outside_worse_keep_shut`, `inside_worse_ventilate`, `outdoor_pm25_high`, `indoor_spike`, `outdoor_spike`, `heavy_swell`, `sea_warm_anomaly`, `modelled_air_today`, `hotter_than_normal`, `sensor_vs_model`, `land_changed`, `post_cooking_summary`, `heat_stress_now`, `heat_danger`, `night_no_relief`, `digest`, `agreement`, `rhythm`, `portal_gone_stale`, `place_around`, `sensor_silent`, `daily_pulse`) | en + id |
| Morning/evening report (`app/main.py` `briefing()`) | 6 sentences | **en only, even when `ALERT_LOCALE=id`** |
| `POST /test-alert` text (dashboard button) | 1 | en only (`planetai test-alert` has en + id) |
| Telegram hello (`planetai telegram`), `/act` confirmation, "I ran out of steps", "No model answered" | 4 | en only |
| Bot system prompt (`agent_loop.py:108`) | answers in | en or id |
| CLI (`bin/planetai`: say/warn/echo/step/ask/choose/fail lines) | 174 | en |
| `install`, `install.sh`, `update.sh`, `backup.sh` messages | ≈60 | en |
| Dashboard (`app/static/index.html`, `lang="en"`) | ≈44 literal strings plus every computed sentence | en |
| Docs, site | all | en (site has `local-hubs/serangan` in id) |

Falls back to English cleanly (`msg.get(LOCALE()) or msg.get("en")`); never shows Bahasa to an `en` node.

**Jargon:** the dashboard explains ρ at first use ("ρ — 27 asks in thirty days, 14 answered. The only number here that
comes from a person") and "cell" implicitly ("an 11 km cell" is the model grid, a different sense from Index cell:
confusing). `DIDO`, `PITO` appear only on the site (`node0/more/index.html:279` "DIDO × (1 − PITO) × ρ") with no
definition on that page. "pack" appears in the CLI and docs, explained in PACKS.md; "node" is explained on the site and
START_HERE. **Terminology drift:** "reference" vs "public sensors" vs "the street"; "Set up" (dashboard) vs "settings"
(CLI copy "planetai settings → The tree" in the Network view, a command that does not exist).

**De-AI pass:** repo copy is clean of the banned words (`grep -rwiE 'genuinely|honestly|straightforward|seamless|robust|leverage'`
over docs/, README, CLI: 0 hits). Site: "honestly" ×2, "leverage" ×1, 39 em-dashes on the front page (§9).

## 4. Setup experience

Rehearsed as a stranger (transcripts in the session scratchpad: `vm_install_1_santiago.log`, `1c`, `1d`, `2b`, `3`).

| # | severity | finding | evidence | status |
|---|---|---|---|---|
| 4.1 | blocker | Linux first run: Docker installed, then **"permission denied while trying to connect to the docker API"**; the fix ("log out/in") only in `.planetai-setup.log`; `.env` left half-written. | 40–47 s into both first runs | fixed 7bb7273 (re-exec under the docker group) |
| 4.2 | blocker | Re-running the line after that failure: **"This machine already runs a node: Ubuntu (bali, -33.43, -70.60)"** with *Update* as the default. | transcript `1b`, `2b` | fixed 96186b3 |
| 4.3 | blocker | Every fresh install ended in the **red "Something went wrong" box** because a new node fails its own doctor (no Telegram, no backup). The green screen (dashboard URL, token, `[o]`/`[t]`) was never shown. | transcripts `1d`, `2c` | fixed 24a4a1b |
| 4.4 | blocker | arm64 Linux: `exec format error` from the database image. | transcripts `1c`, `2b`; `docker manifest inspect` | decision 2 |
| 4.4b | blocker (introduced and removed during the review) | The first version of the docker-group fix (7bb7273) lost every install flag on re-exec: a Linux first run produced a Bali node named `bayu-2`. | VM4 `.env`, `/health` `node bayu-2 lat -8.8271` | fixed 374acf7, re-rehearsed on VM5 |
| 4.5 | serious | Fresh macOS account: `install` appends PATH only to rc files that exist; `~/.zshrc` does not → `command not found: planetai` in every new terminal, and the docs' advice ("open a new terminal") does not help. | `install:101-102` | fixed d2522c6 |
| 4.6 | polish | "Poblenou, Barcelona" offers two identical choices ("Sant Martí, Catalunya, ES" twice). | transcript `2b` | fixed 31c21fb |
| 4.8 | serious (found 6 Sep, second pass) | Starting over on the same machine: folder deleted, Docker volume kept, new `.env`, new password. The app fails `password authentication failed` on every call while `pg_isready`, `/health` (200, `ok false`, schema `pre-0.4`) and the install's own doctor read fine. | VM6 rehearsal of v0.32: `docker logs planetai-db-1`, `/health` | fixed v0.32.1: `install.sh` refuses and names the way out; doctor check "app logs in to the database" |
| 4.7 | polish | The wizard's default name is the hostname (`lima-pai-clean`), fine; the hero says "Two minutes, four questions"; measured: 8 s of questions, 23 s of install with a warm image, 60–90 s cold. | transcripts | ok |

Timing on the clean VM, v0.31 path (`3`): see addendum. The what_next screen's `[o]` runs `xdg-open` (no browser on a
server: prints the URL); `[t]` runs `planetai telegram`. Laptop sleep: containers have `restart: unless-stopped`, Docker
Desktop/OrbStack resume them; the node then has a gap in readings (no fill, by design) and "polled N min ago" says so.

## 5. Reliability

Measured on VM2 (v0.30) and node #1's 48 h log.

- `docker restart app`: answering in 11 s. Host reboot (VM stop/start): containers back on their own.
- Reference API down (open-meteo blackholed): `last_error` set, `ok` stays true, `errors {}`, node serves.
- Sensor unreachable: same path (`source … failed` in `last_error`); dashboard "polled N min ago" continues.
- Network loss 10 min: 3 polls failed, no crash loop, alerts before/after 1/1 (no duplicates), recovered on its own.
- Disk at 99% (301 MB free): poll fine; backup failed for the Linux permission reason (§7), not for space. No disk check
  in doctor (polish).
- Node #1 48 h: 880 log lines, 0 tracebacks in the poll/rules loops, 0 WARNING lines apart from the hourly parent push
  and one `meshtastic: unknown telemetry field 'current'`; 65 dashboard refresh cycles; `errors: {}`.
- Timezone: app connection `timezone=America/Santiago`; `date_trunc('day', now())` = local midnight for Europe/Madrid;
  briefing header uses local date. ✓
- Schema idempotency: `init.sql` applied twice on a live database: NOTICE … skipping, no error; second `planetai update`
  in a row: `schema 0.20 → 0.20`.
- Footprint at idle: node #1 app 107 MiB, db 66 MiB, agent 60 MiB, mosquitto 3 MiB, CPU < 0.5 %; VM app 68 MiB, db 57 MiB;
  images 1.08 GB after `planetai packs` adds `earthengine-api`. Node #1 database 31 MB after four days (≈6,000
  readings/day ≈ 1 MB/day).

| # | severity | finding | status |
|---|---|---|---|
| 5.1 | serious | Log rotation: `app`, `mosquitto`, `reticulum` capped; **`db`, `agent`, `ipfs` uncapped** (the agent logs every tool call). | fixed 5c38ea1 |
| 5.2 | polish | Doctor has no disk-space check. | fixed f721e2a |
| 5.3 | polish | `planetai packs` grows the image by ~350 MB (Earth Engine client) for every node, enabled or not. | fixed 5ba16af: only `packs install` grows it |

## 6. Security

Full route/tool auth matrix, egress table and Docker notes in the subagent report (`security_audit.md`); `pip-audit`
over the resolved image set (fastapi 0.141.1, starlette 1.6.0, uvicorn 0.52.4, psycopg 3.2.13, httpx 0.27.2, pyyaml
6.0.3, mcp 2.1.1, cryptography 50.0.1, 38 packages): **no known vulnerabilities**.

**Ports.** `app` 8080 on 0.0.0.0 (LAN and tailnet: the dashboard on a phone needs it); `db` 127.0.0.1:5432; `mosquitto`
1883 on 0.0.0.0 with password auth (the gateway radio); `ipfs` 4001 swarm, API on loopback; `reticulum` 4242. Node #1
additionally has caddy on 8080 (its node is on 8081) and Ollama on 11434 loopback.

| # | severity | finding | evidence | status |
|---|---|---|---|---|
| 6.1 | blocker | `GET /settings/raw` accepted the read-only **`BACKUP_TOKEN`** and returned every secret unmasked (Telegram token, AI keys, all tokens). | `main.py:697-711`; VM: 200 with the backup token before, 401 after | fixed b94e2e8 |
| 6.2 | serious | `POST /readings` without a token creates a *local, indoor* sensor; the rules then fire act-level alerts to the phone and the value enters "live" cells. | VM: `{"accepted":1}`; two act alerts "at evil" within a minute | fixed d55e115 (admin token; decision 3, 6 Sep) |
| 6.3 | serious | `POST /actions` without a token; accepted `stage='settings'` and non-existent alerts (500). | VM before/after | partly fixed 04598b0 (stage whitelist, 404); openness = decision 3 |
| 6.4 | serious | Dumps include the `settings` table (Telegram token on node #1; `settings` keys on node #1: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_IDS`, …). Docs claimed otherwise. | node #1 `select key from settings` | doc 9c2aafb; rows excluded from dumps 058b60e (decision 3, 6 Sep) |
| 6.5 | serious | Pack rule/cell SQL runs as the DB owner: a "data pack, safe to merge" can `SELECT value FROM settings` into an alert text (`/alerts` is unauthenticated). | `main.py:373`, `index.py:50` | fixed f8e638e: `planetai_ro`, schema 0.21 (decision 3, 6 Sep) |
| 6.6 | serious | `update.sh` executed `.env` as shell (also code execution from a pack's `env:` line at next update). | see 1.3 | fixed a840460 |
| 6.7 | serious | Agent loop logged `settings_set` arguments (secrets) into the container log. | `agent_loop.py:178` | fixed b8e98d1 |
| 6.8 | serious | Supply chain: `/install` fetches `raw.githubusercontent.com/…/main/install` unpinned; tarball checksum optional at install and absent at update; `curl \| sh` for Docker, Tailscale, Ollama; `ipfs/kubo:latest`; `Dockerfile.reticulum` pip unpinned; `mcp>=2.0` unbounded. | `install:8-9`, `update.sh:77` | update checksum fixed 19c7e3b; rest = decision 1 / open |
| 6.9 | serious | `.env.before-update` copied with umask perms (world-readable secrets). | `update.sh:69` | fixed 19c7e3b |
| 6.10 | polish | `GET /settings` (unauthenticated) shows chat ids, LAN sensor hosts, remote URLs; secrets masked correctly (`•••• set`). | node #1, VM | fixed a80b604: masked without the admin token |
| 6.11 | polish | Token compares with `!=` (not constant-time); containers run as root; `reticulum` receives the whole `.env`; `envset` sed breaks on `\|`/`&`; `packs/_test` left behind on Ctrl-C (fixed 978b8ea); `cmd_act` JSON quoting (fixed 978b8ea). | audit | compares d4e0f41, envset ce89a4b; root containers and reticulum's whole `.env` open |
| 6.12 | ok | Secrets in logs: 48 h of node #1 logs contain no `api.telegram.org/bot<digits>:` and no token strings; `status --json`/`doctor --json` carry none; the CLI prints ADMIN_TOKEN/BACKUP_TOKEN/MQTT_PASS to the terminal by design and none of those go to `.planetai-setup.log`. | grep | ok |

**Egress (everything that leaves a node):** Telegram `sendMessage` (alert text, chat id; token in URL by Telegram's
design, never logged); Open-Meteo forecast/air/marine every 5 min with **full-precision coordinates and the node name in
the User-Agent** (polish: round, generic UA); NASA POWER and Nominatim once; Overpass monthly (place pack); Smart Citizen
(your account); Bali Air Dispatch; CKAN portals; `PARENT_API_URL/aggregates` hourly means with **device ids** (where
`/export` aliases them; polish); the daily export to IPFS if enabled; dumps to `BACKUP_REMOTE`. No raw rows leave on
any path except the dump (which is the point of a dump). The invariant holds for aggregates; the dump/secret point is
decision 3.

## 7. Maintenance

| # | severity | finding | evidence | status |
|---|---|---|---|---|
| 7.1 | blocker | On Linux, `backups/` was created by Docker as root: **no backup could ever be written** (`./backups is not writable`), and the nightly cron would fail silently. | VM1, VM2 | fixed 0a01dad |
| 7.2 | serious | **Node #1 has no backup cron** (`crontab -l`: none). Its daily dumps exist only because `planetai update` ran daily. Doctor said "a nightly one is scheduled" without checking. | ssh `crontab -l`; `backups/` dates = update dates | doctor check added 40afcbb; node #1's crontab is yours to add (`planetai doctor` now prints the line) |
| 7.3 | serious | Backup verification: `backup.sh` checks gzip validity and a `readings` table ✓; 30-day retention via `find -mtime +30` ✓; `LAST_OK` ✓. Restore rehearsed: see addendum. | | ok |
| 7.4 | serious | Rollback for a tester means `git checkout <tag>; planetai restart` (UPDATING.md). It does not rebuild, which is right, but `.env`'s version stamp lied until bbb19db. A tarball-installed node has no git and no rollback path at all. | VM1 update test | partly fixed; tarball rollback = decision 1 |
| 7.5 | polish | Doctor names a fix for every failure it detects ✓ (13 checks). Missing checks: disk space (added f721e2a), log size, time sync. | | partly fixed |
| 7.6 | polish | Issue templates exist (`node-problem.yml`, `new-source.yml`). `info@fab.city`: MX records point at Google Workspace; whether the alias routes to a person I cannot verify from here. | `dig MX fab.city` | verify |
| 7.7 | polish | `.planetai-setup.log` on node #1 is 600 KB and grows with every `planetai packs`/`update` (appends). | node #1 | fixed ce89a4b |

Disk growth over 30 days, from node #1's rate: ≈30 MB database + ≈30 dumps (28 KB–1 MB each, compressed) + container
logs capped at 30 MB (`app`) but uncapped for `db`/`agent`.

## 8. Documentation

| # | severity | finding | status |
|---|---|---|---|
| 8.1 | serious | Counts stale in five places: "fifteen tools" (17), "eight packs" (9), README badge 0.24, "three things" in the install stub, "Seven of twenty" vs 8 rows/6 cells. | fixed 9c2aafb, a6b8f2a (gate); cell count = decision |
| 8.2 | serious | START_HERE promised Telegram `/act 12` for every tester; it needs the bot (`planetai agent local`). The evening report also ends every waiting item with `→ /act N`. | doc 9c2aafb; report and test alert 27a8f42 |
| 8.3 | serious | PLATFORMS.md and START_HERE promised Raspberry Pi; "database grows around 50 MB a year" vs ≈1 MB/day measured. | fixed 9c2aafb |
| 8.4 | serious | STORAGE.md: "Dumps hold … not tokens" — false since v0.20. | fixed 9c2aafb |
| 8.5 | polish | Every documented command exists; commands not in `--help` or any doc: `start`, `restart`, `sensors`, `cells`, `version`, `geocode`, `dashboard`, `ha`, `agents`, `mcp` (aliases). | fixed 31c21fb (aliases stay unlisted) |
| 8.6 | polish | Install line: README/START_HERE/PLATFORMS/MAC_MINI say `/node0/install`; the site stub is `/install`. Both work; the `/node0/install` copy has already drifted (different banner). | decision 1 |
| 8.7 | polish | UPDATING.md said the tarball path "verifies its checksum": only the install did. | fixed 19c7e3b |
| 8.8 | ok | AGENTS.md invariants match observed behaviour except: "secrets never logged" (6.7, fixed) and "live means measured here" (holds: the heat cell claims live only at ≥12 buckets; but it reports 0.0 hours with no sensor — decision). | |

Can a stranger reach the first alert from START_HERE alone? Yes on v0.31: install → `planetai telegram` → `planetai
test-alert` → `planetai act`. On v0.30, no (4.3).

## 9. Website

Inventory and link check by script (`site_inventory.md`): live HTML equals the repo; **no horizontal overflow** at
375/768/1440 on `/` and `/node0/`; all internal links 200; `og:image` 200 (1200×630); all four `<img>` have alt text.

| # | severity | finding | file:line | proposed change |
|---|---|---|---|---|
| 9.1 | blocker | Footer "GitHub" → `github.com/fabcity/planetai` (private → 404 for the public) on all four pages. | index.html:1983, node0/index.html:406, more:594, setup:422 | point at `https://github.com/fabcity/planetai-node`, or make the site repo public |
| 9.2 | blocker | Tester tarball `/node0/get/planetai-node.tar.gz` is **v0.12** (VERSION file), SHA256 beside it. `update.sh` on a tarball node would install it over v0.31. | node0/get/ | `tools/bundle.sh && make deploy` after the release, or remove the tarball path from the docs |
| 9.3 | serious | Cell count contradicts itself: "seven of twenty cells" (index:1597) vs "4 of 20", "4 cells", "Four of twenty" (more:371, 400–404, 555). Node #1 today: 8 rows, 6 distinct. | | one number, from `planetai cells` on node #1, on both pages (decision) |
| 9.4 | serious | "**0.67** Node #1, last thirty days: twelve alerts that asked for something, eight answered" appears nowhere in the node's data (ρ was 0.385→0.519; 27 asks, 14 answered on 6 Sep). Reads as fact. | node0/index.html:318 | replace with the live number and date, or label it as an example |
| 9.5 | serious | Legacy grant material below the live node card: "One node per pilot; … a narrow set of action agents drafts measured responses into a queue" (1584); "PLANETAI Node v0 · Open hardware … CERN-OHL · OSHWA-track … Four narrow agents, one per pilot" with A1–A4 cards (1608–1645, 1657); 36-month pre-registered hypotheses (1417–1418, 1672–1692). None of it exists in the software. | index.html | flagged for your decision: remove, or move under a "The research programme (2026 proposal)" heading with a date |
| 9.6 | serious | Alpha/beta mixed: setup page eyebrow "Beta" (236, 392), "beta tester" (350), "This is an alpha" (394). Front page has no alpha banner (one word at 1600). | node0/setup/index.html, index.html | "Alpha" everywhere; add the alpha note to the front page's node card |
| 9.7 | serious | No software version anywhere on the site; screenshots carry none; `now.jpg` alt says "four headline tiles" (pre-v0.29 layout wording). | node0/index.html:278 | add "v0.31, 6 Sep 2026" under the screenshots; re-check `now.jpg` |
| 9.8 | polish | "Three questions" (more:486) vs four everywhere else; "Polling every 5 minutes" as static text with a live dot (more:350); "One node, one night" (more:556); two coordinate pairs for node #1 (more:351 vs 473). | | edit |
| 9.9 | polish | Meta: front page has no `og:*`, no favicon (`/favicon.ico` 404); more/ and setup/ reuse node0's `og:title` and `og:url`; no canonical anywhere; no robots.txt/sitemap. | | add |
| 9.10 | polish | Publicly served internal files: `/scripts/*.py`, `/docs/morning_review_punch_list.md`, `/.github/workflows/deploy.yml`, `/Makefile`, `/assets/_FC_Logo.ai`. No secrets in them. | `.assetsignore` | extend `.assetsignore` |
| 9.11 | polish | ~670 KB of unreferenced screenshots served; 1440-px JPEGs to phones (no `srcset`; `plan-narrow.jpg` unused); `street.jpg` is 8 KB at 1440×900 (likely blank). | node0/assets/ui | prune |
| 9.12 | polish | Voice: "honestly" (index:1752, 1803), "leverage" (1737), 39 em-dashes on the front page, em-dash chains at setup:288/334/376; "more/" is 3,464 words. Raspberry Pi promised on setup:254 with no SSD/arm64 caveat. | | edit |
| 9.13 | ok | `/install` served `text/plain`, `cache-control: public, max-age=300`, Cloudflare. | | |

Exact diffs for 9.1, 9.6, 9.8 (mechanical; the narrative ones above are for you to word):

```diff
--- a/index.html  (and node0/index.html:406, node0/more/index.html:594, node0/setup/index.html:422)
-<a href="https://github.com/fabcity/planetai">GitHub</a>
+<a href="https://github.com/fabcity/planetai-node">GitHub</a>
--- a/node0/setup/index.html
-Beta · set up a node
+Alpha · set up a node
-the single most useful thing a beta tester can report
+the single most useful thing a tester can report
--- a/node0/more/index.html
-Three questions, then it installs
+Four questions, then it installs
```

## Addendum: results from the later runs

**Restore into a second fresh node (VM1 → VM2, review build).** `planetai backup` on VM1 → `Ubuntu-2026-09-06.sql.gz`
(28 KB) → `planetai restore` on VM2 (confirm by typing the node name; safety backup taken first) → 8 seconds → counts on
VM2 `4511|7|5|4` (readings, alerts, actions, sensors), identical to VM1. The `settings` table travelled with the dump
(VM2 now holds VM1's `ALERT_LEVEL`), which is the point in decision 3.

**MCP, one call per tool (VM2, v0.30):** 17 tools listed; `status`, `health_check`, `sensors`, `context`, `readings`,
`alerts`, `cells`, `packs`, `series`, `settings_get` (secrets masked, none shown), `daily_report`, `export_day`,
`maintenance`, `run_pack_script` (`place verify` ran: PostGIS ✓, Overpass 504 that day), `settings_set` (recorded as
`beta-review`), `act` (recorded) all answered. `history` errored on v0.30 (the 500 fixed in v0.31). Wrong token → 401.

**`planetai reticulum`**: crash-looped on v0.30 (`OSError: Read-only file system: '/etc/reticulum/storage'`; the
config is mounted `:ro` and RNS writes under its configdir). Fixed in 5fd2f4c; on the review build the bridge comes up
in 24 s with an LXMF address and `bridge up: http :4243`.

**`planetai homeassistant`, `planetai ipfs`, `planetai meshtastic`**: all ran on the clean node (broker with password,
kubo node id, gateway instructions printed; `meshtastic` waits for a packet as documented).

**`planetai agent local` on a 3 GB VM**: Ollama installed, `qwen3:4b` pulled in 254 s, the agent container started,
ladder logged, "telegram: NOT configured" stated plainly. Works; the docs' "8 GB machine" is the honest minimum.

**Node-side layout**: `PUT /settings {"UI_LAYOUT": …}` hides a card for a fresh browser with no `localStorage`
(measured: `tile:wind` display none in a new tab). Arrange mode in the browser saves `planetai_layout` locally and
leaves arranging on Done. ✓

**Phase 3, the site path with the release build** (`curl -fsSL planetai.fab.city/install | PLANETAI_REF=… bash` on
clean VMs with amd64 emulation, as a Mac has):
- VM3, first run, no Docker: Docker installed, image built, node up (`install.sh` under the docker group) in 94 s, then the
  wizard's own compose call failed on the socket → fixed (7e5caa9: `finish_setup` re-entered under `sg`). Re-run: green
  screen, all checks, exit 0 in 23 s.
- VM4, first run, no Docker, Barcelona: **258 s** from the pasted line to the green screen (git and Docker installed, image
  built under emulation, node up, all doctor checks including "nightly backup scheduled", the *What now?* prompt shown),
  exit 0. **But** the node came up as `bayu-2` at Bali coordinates with `BAD_ENABLED=1`: my own docker-group re-exec in
  `install.sh` ran after the argument loop had shifted the flags away. Fixed in 374acf7 (arguments kept whole) and
  re-rehearsed on VM5 (below). A fix rehearsed once is not a fix.
- VM5, first run, no Docker, Barcelona, with 374acf7: **109 s** to the green screen and the *What now?* prompt, exit 0;
  `NODE_NAME=poblenou-test`, `NODE_LAT=41.4036418`, `NODE_KIND=home`, `CKAN_PORTALS=open-data-bcn=…`, `BAD_ENABLED=0`,
  `backups/` owned by the user, cron line present, bootstrap `cams_history 4416, power_climatology 60, place Sant Martí`.
- VM6, first run from `main` after the release, the exact documented line with no overrides, Santiago: **102 s** to the
  green screen and the *What now?* prompt, exit 0; `version v0.31`, `NODE_NAME=santiago-test`, `NODE_LAT=-33.43107`,
  `CKAN_PORTALS=datos-gob-cl=…`, `BAD_ENABLED=0`, cron present, bootstrap complete, `/readings` and `/export` 200.
- The `[o]`/`[t]` prompt never appeared through `curl | bash` on any version before 07e6f02 (`-t 0` on a pipe).

