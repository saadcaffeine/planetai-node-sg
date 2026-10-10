# Code review — second pass, September 2026

Reviewed at `4f96a38` (main, `v0.41.2-92-g4f96a38`, the tree the v0.42 CHANGELOG entry describes), clean
tree, 10 September 2026, on this Mac and on `pai-clean` (Lima, Ubuntu 24.04.4, aarch64, Docker 29.8.0)
running a node built from that commit.

## What this document is, and what it is not

The improvement-plan brief names a second review — `CODE_REVIEW_2026-09-09_omarchy.md`, 54 findings across
A/S/P/D, written at `b075471`. **That document does not exist** and never has; the search is recorded in
`docs/archive/reviews/RECONCILIATION_2026-09-09.md`. This is a second pass written to stand in its place. It is not
a reconstruction of it and does not pretend to be one: different author, different day, different commit,
and 25 findings' worth of the first review already fixed nothing in between.

Two things follow, and they matter for anyone reading the plan built on top of this:

**The ten IDs the brief pinned by content keep their numbers and their claims** — A1 (quiet hours), A2 (a
pack rule with no message), A3 (the local radius), A5 (AirGradient), A6 (the LXMF inbox), S3 (a truncated
tarball), S8 (`planetai setup` on a running node), P1 (`nearest_health_m`), P5 (nearby's
`baliairdispatch`), D2 ("I did this" then Cancel). Eight of those ten were reproduced on `pai-clean` before
this was written; the transcripts are in the reconciliation, not repeated here.

**The count is what it is: 29, not 54.** Ten pinned, nineteen found (S11 was found on 10 September by running S-group's own verification on node #1, after the rest was written). Nothing was added to reach a number.
Where the brief pinned an ID and I found nothing beyond what an existing F-finding already says, the ID
carries a cross-reference rather than a new claim, and the numbering has no gaps invented to hide that.

The first review's 25 findings (`CODE_REVIEW_2026-09.md`) are **not** repeated here. Twenty-four are still
open at this commit; where a finding below overlaps one, it says so and defers to it.

## What this is

A single-machine climate observatory installed at an address. Two containers: Postgres/PostGIS and one
Python process that polls a Smart Citizen kit on the WiFi, an AirGradient, a LoRa radio over MQTT, the
public stations nearby, a city's CKAN portal, CAMS and Open-Meteo point samples and Earth Engine's view of
the land into one `readings` table with one schema from the room to the planet. SQL rules in
`config/rules.yml` and thirteen pack folders read that table as a read-only role and write `alerts`. A
report scheduler writes one deterministic sheet every N hours in three languages. Alerts reach Telegram,
Home Assistant, a LoRa mesh and an LXMF address. A one-file dashboard reads the same public API a NAS and an
MCP agent read. The number the project exists to produce is ρ — the share of act-level alerts a person
answered.

Read for this pass, in full or in the parts the findings touch: `app/main.py` (1,321), `app/index.py` (114),
`app/settings.py` (190), `app/sources.py` (538), `app/packs.py` (157), `bin/planetai` (1,350), `install`
(135), `install.sh` (531), `update.sh` (163), `backup.sh` (83), `app/static/index.html` (1,111),
`init.sql` (167), every `packs/*/rules.yml` and `packs/*/cells.yml`, `tools/check_docs.py`,
`tools/check_rules.py`, `tools/bundle.sh`, `docker-compose.yml`, the two Dockerfiles and both workflows.

## Gates, as run

```
$ make lint ; echo "LINT_EXIT=$?"
  17 floors, all sourced and dated
  init.sql + Dockerfile + compose mounts + no litter ok
  24 snippets checked, 0 would fail on Python 3.9
  50 documents check out
  GUI: script parses; every id, endpoint, field and asset resolves; ...
  - requirements resolve skipped (venv failed)          ← see S10
  39 rules and cells check out against init.sql
  app imports, 44 routes
ok
LINT_EXIT=0
```

**Finding zero, again, and it has got worse.** The first review's finding zero was that `make test` runs 17
suites and CI runs one. `make test` now runs **25** (`Makefile:30`; `v0.42` added
`test_release_consistency`, `test_ship_gate`, `test_daemon_state`, `test_diagnose`, `test_ladder`). CI still
runs one: `.github/workflows/lint.yml:29-32`, `tests/test_sources.py`. Every security assertion in
`tests/test_shipped.py` — including the four added in `v0.42` about the MCP session — runs only on a
developer's machine. And `make lint` above exited **0** with one gate that did not run.

Not run, and why:
- `.github/workflows/install-smoke.yml` — needs a clean amd64 Linux runner.
- A fresh `install.sh` from zero. `pai-clean6` has no node and no running Docker; `pai-clean` has a
  three-day-old node that the reproductions needed. S3 was run on `pai-clean` for that reason, stated there.
- `packs/earth-engine` and `packs/earth` — no Earth Engine key on either machine.

---

# §2 Findings

## A · the app, its boundaries and its loops

### A1 · one non-numeric character in a quiet-hours field, and the node stops telling anyone anything
`app/main.py:292`, `:301`, `:405` · **CONFIRMED on pai-clean** · rung 2: the safe reader is one file away

`_hours()` keeps only the digits-only tokens and `_quiet()` indexes `[0]`, so `QUIET_FROM=22:00` — which
`PUT /settings` accepts without a murmur — raises `IndexError` at `main.py:405`, the line that decides
whether to notify.

The alert row has already committed by then (`db()` is `autocommit=True`, `app/main.py:86`), so `/alerts`
grows and the dashboard shows it while `notify()` and `ha_alert()` never run. No Telegram, no mesh, no LXMF,
no Home Assistant. And `status.errors` holds `run_rules: list index out of range` for exactly one 60-second
turn before the rule's own cooldown makes the next turn clean and `loop()` pops it (`main.py:465`). One log
line is the only durable evidence.

**Shorter diff:** `settings.num("QUIET_FROM", 22)` and `settings.num("QUIET_TO", 6)` — `app/settings.py:142`
already exists and already does exactly this (`int(v) if v.isdigit() else default`), and `_hours` loses its
only two callers.
**Could break:** a node that had set `QUIET_FROM=22,23` expecting a list — no such node exists; `_hours`
splits on commas but both callers take `[0]`, so the list has never meant anything.
**Check:** in `tests/test_settings.py`, beside the existing ones —
`assert main._quiet.__code__.co_names.count("num")` is too clever; the honest one is a unit test that sets
the setting to `"22:00"` and asserts `_quiet("warn")` returns a bool rather than raising.

### A2 · one pack data file with no `message:` stops every alert on the node, permanently
`app/main.py:393`, `app/packs.py:4`, `:83-86` · **CONFIRMED on pai-clean** · the worst finding in this pass

`msg = rule["message"]` is a subscript, inside the row loop, outside the only `try` in `run_rules` (which
wraps `index.run_ro` alone at `:380-384`). A rule with no `message` raises `KeyError` out of the whole
function. Because such a rule usually returns a row every time, every turn dies at the same line: six turns
of the 60-second loop watched on `pai-clean`, `/alerts` frozen, `status.errors` permanently
`{"run_rules": "'message'"}`. **Every rule on the node** — the core's two and all thirteen packs' — is dead
for as long as the file is there.

`app/packs.py:4` calls `rules.yml` *"DATA — no code, safe to merge from anyone"*. It is the one file the
project invites strangers to contribute.

**The gate for this exists and did not help.** `tools/check_rules.py:101` already refuses it:
`"no message and no contributes: — this rule can fire and reach nobody"`. That is a build-time gate on the
repository, and a pack folder dropped onto a running node never passes through `make lint`. The guard has to
be at runtime.

**Shorter diff:** in `app/packs.py:86` — the function whose docstring already describes this exact failure —
`return [r for r in rules() if not r.get("contributes") and (r.get("message") or _warn_once(r))]`, or more
simply filter and log. One line, and it fixes A8's sibling shape too if the same discipline is applied there.
**Could break:** a pack that relied on a message-less rule being silently skipped — none ship.
**Check:** `tests/test_packs.py` — load a rule dict with no `message` through `packs.alerts()` and assert it
is not returned.

### A3 · "500m" in the local-radius field freezes every source
`app/main.py:103`, `:133` · **CONFIRMED on pai-clean** · same shape as A1, different loop

`float(settings.get("LOCAL_RADIUS_M") or 500)` sits in `poll_once` **outside** the per-source
`try/except` at `:95-100`, which catches only `fn()`. So it is not one source failing, it is the loop:
`polls` and `last_poll` frozen for 210 seconds under observation, `status.errors` permanently
`{"poll_sources": "could not convert string to float: '500m'"}`, and `/health.ok` still `true`. The
identical line at `:133` kills MQTT ingest the same way.

`app/settings.py:36` labels the field "Local radius, m". It is in `PUBLIC`, not in `CHOICES`, so it is free
text by design.

**Shorter diff:** see A4 — this needs the float reader that does not exist yet.
**Check:** the same unit test shape as A1.

### A4 · `settings.num` is int-only, so every float setting in the tree does a bare cast
`app/settings.py:142`, and 40-odd call sites · rung 2: the helper exists, half-built

`num(key, default: int) -> int` is the one numeric-safe reader and it cannot return a float. So every float
setting bypasses it:

```
$ grep -rnE "(int|float)\((os\.getenv|os\.environ|settings\.get)" app/*.py packs/*/*.py | grep -v settings.num | wc -l
44
```

The ones that are runtime settings, editable from the dashboard's own free-text fields, and reached from a
loop or a route:

| setting | line | what a typo does |
|---|---|---|
| `LOCAL_RADIUS_M` | `main.py:103`, `:133` | A3 — every source and MQTT ingest stop |
| `BAD_RADIUS_KM` | `sources.py:343`, `main.py:723` | `sources.enabled(hc)` is evaluated in the `for` header at `main.py:94`, **before** the try — so this is A3 again, through a different key; and `/nearby` 500s |
| `BAD_MIN_SEPARATION_M` | `sources.py:344`, `main.py:745` | the same two |
| `MESH_GATEWAY_NODE_NUM` | `main.py:62` | `mesh_send` raises, is caught at `:201`, and the log line prints only `type(e).__name__` — "mesh send failed: ValueError", with no value and no key. Alerts stop reaching the mesh, undiagnosably |
| `POLL_SECONDS` | `main.py:47` | at module scope, no guard: the app does not start. `.env`-only, but the wizard writes it and hands are edited |

**Shorter diff:** `def real(key, default: float) -> float` beside `num`, four lines, using the same
`try/except ValueError` shape; then the five sites above. Not the other 39 — `NODE_LAT`/`NODE_LON` are set
by the wizard from geocoding and a bad one should be loud.
**Could break:** nothing; every caller currently raises on the same input.
**Check:** in `make lint`, an AST assert that no `float(settings.get(...))` remains in `app/` — the same
shape as F11's assert, in the same place.

### A5 · the AirGradient adapter is dead code, and the dashboard sells it
`app/sources.py:264`, `:320-357`, `app/settings.py:28` · **CONFIRMED on pai-clean**

`sources.airgradient(hc, hosts, lat, lon, indoor)` is a complete forty-line adapter. `sources.enabled()`
never appends it. The only two reads of `AIRGRADIENT_HOSTS` (`sources.py:340`, `main.py:738`) use it to
build a **skip** set — the station ids to exclude from `baliairdispatch`, a source that is off by default.

```
$ grep -rn "airgradient(" app/ packs/
app/sources.py:264:def airgradient(...)          ← the definition, and nothing else
$ docker compose exec app python3 -c "import httpx,sources; print([n for n,_ in sources.enabled(httpx.Client(timeout=5))])"
['open-meteo', 'open-meteo-cams']                 ← with AIRGRADIENT_HOSTS set
```

`app/settings.py:28` offers the household *"AirGradient hosts — Hostnames or IPs on your WiFi,
comma-separated. Read directly, no cloud."* Somebody types their sensor's hostname, saves, and waits.
Nothing in `/sensors`, nothing in `status.errors`, nothing in the log, because nothing was asked to run.
`tests/test_sources.py:51` tests the adapter, which is why no gate noticed.

**Shorter diff:** two lines in `enabled()`, in the shape of the four beside it:
```python
ag = [h for h in settings.get("AIRGRADIENT_HOSTS", "").replace(" ", "").split(",") if h]
if ag: out.append(("airgradient", lambda: airgradient(hc, ag, _lat, _lon, SENSOR_INDOOR())))
```
**Could break:** a node with a stale `AIRGRADIENT_HOSTS` value now starts polling a host that is not there;
the per-source `try` at `main.py:95` catches it and names it in `status.errors`, which is the right outcome.
**Check:** in `tests/test_packs.py` or `test_sources.py` — every adapter function in `sources.py` is either
reachable from `enabled()` or named in an allowlist of deliberate exceptions. That assert would have caught
this on the commit that added it.

### A6 · the LXMF bridge terminates strangers' traffic and holds the database password
`docker-compose.yml:91`, `:95`, `app/reticulum_bridge.py` · **pinned ID; overlaps F2 and F5**

`ports: ["4242:4242"]` is a deliberate LAN/tailnet listener so Sideband and NomadNet can reach the node —
and `env_file: .env` hands that same container `POSTGRES_PASSWORD`, `ADMIN_TOKEN`, `TELEGRAM_BOT_TOKEN`,
`AGGREGATE_TOKEN`, `BACKUP_TOKEN` and the AI keys, of which the bridge reads six variables, none of them
secret. That is F2, still open, and it is worth more than F2's rank because of what this container is: the
one process in the compose file that parses input from people the household has never met.

Nothing new to add and no separate PR: **F2 is the fix** (delete `env_file`, pass the six through), and F5's
missing `127.0.0.1:4243:4243` belongs in the same diff since it is the same three lines.

### A7 · `GET /sensors` publishes the household's device hostnames, firmware and exact coordinates, unauthenticated — **RESERVED · prompt A**
`app/main.py:606-608` · **CONFIRMED on pai-clean**

```python
@app.get("/sensors")
def sensors_():
    return q("SELECT * FROM sensors ORDER BY local DESC, name")
```

`SELECT *`, no token. `sensors.meta` is a JSONB the adapters fill: `sources.py:273` (AirGradient) stores
`{"host": host, "firmware": ..., "model": ...}`, `:299` (PurpleAir) the same, `:494` (Meshtastic)
`{"mesh_node":…, "gateway":…, "channel":…, "root_topic":…}`. Run on the VM with a row shaped the way the
AirGradient adapter shapes one:

```
$ curl -s localhost:8080/sensors        # no Authorization header
  ag-84fce6 | Living room | lat,lon: 41.38742 2.16861 |
     meta: {"host": "airgradient_84fce6.local", "model": "I-9PSL", "firmware": "3.1.9"}
```

The room's name, the device's hostname on the household's WiFi, its firmware version and its position to
five decimals. Meanwhile, on the same unauthenticated request:

```
$ curl -s localhost:8080/settings
  AIRGRADIENT_HOSTS = ••••  set
  MESH_GATEWAY_NODE_NUM = ••••  set
```

`app/settings.py:79-81` says why it masks them: *"Chat ids, sensor hosts, account names and remote URLs are
not secrets, but they are the household's, and GET /settings answers anyone on the WiFi (found 6 Sep
2026)."* The thing `/settings` was taught to hide, `/sensors` hands over — the same host string, the other
route. `/export` (`main.py:817`) is careful about exactly this: *"Your own sensors are named by role
(indoor-1, outdoor-1), not by their device id."*

`SELECT *` is also why this will happen again: any column added to `sensors` is published the day it lands.

**Reserved.** This is a leak on an unauthenticated route and the brief gives those to prompt A. No PR here.
The shape of the fix, for that session: name the columns, and put `meta` behind the token or filter it to
the keys that are provenance (`licence`, `attribution`, `model`, `dataset`) rather than plumbing.

### A8 · one word in a pack's `cells.yml` returns 500 from `/cells` and `/export`
`app/index.py:80` · **CONFIRMED on pai-clean**

`need = int(c.get("min_buckets", 0))` sits inside the `for c in defs` loop but **outside** its only `try`,
which wraps `run_ro` at `:73-76`. A pack shipping `min_buckets: many` raises `ValueError` out of `cells()`:

```
$ curl -s -o /dev/null -w "%{http_code}" localhost:8080/cells      500
$ curl -s -o /dev/null -w "%{http_code}" localhost:8080/export?day=2026-09-10   500
app-1  |   File "/app/index.py", line 80, in cells
app-1  | ValueError: invalid literal for int() with base 10: 'many'
```

So the daily CC-BY export — the one thing that reaches the commons and the Index — stops, and the report
path with it (`report.py:284` calls `cells`). Same class as A2, same file type, same "safe to merge from
anyone".

**Shorter diff:** move `:79-86` inside the existing `try`, which is a two-space indent change and no new
code. That covers `state`, `min_buckets` and `notes` in one move.
**Could break:** a pack whose cell currently half-works — none.
**Check:** in `tools/check_rules.py`, beside the cell checks it already makes: `min_buckets` must be an
integer if present. Build-time, and unlike A2 that is enough here only for repository packs — so take the
`try` indent as well.

### A9 · three rows claim `Governance|City`, and which one survives is append order
`app/index.py:47`, `:61-95`, `packs/open-data-health/cells.yml`, `packs/air-quality/cells.yml`
· **CONFIRMED on pai-clean**

`_row()` does no key validation and `cells()` does no de-duplication. On a `NODE_SCALE=city` node with
`open-data-health` enabled:

```
$ curl -s localhost:8080/cells
  row count per cell key:
    Governance|City -> 3
  the Governance|City rows, in order:
    value=42.0   state=partial  src=planetai-node · pack:open-data-health  unit=% of published datasets updated…
    value=517.0  state=partial  src=planetai-node · pack:open-data-health  unit=open datasets published
    value=1.0    state=partial  src=planetai-node actions ledger           unit=rho — share of act-level alerts…

   rows in: 3   rows kept by a spine keyed on cell: 1
   Governance|City kept: 1.0 — rho
```

Two of the three are lost. The core's own `Governance|{SCALE}` (`index.py:91`) collides with the pack's two,
and it survives here only because the core appends last. Reorder `cells()` and **ρ is the one lost** — the
number the project exists to produce, dropped by a pack's data file.

This is broader than the one pack: `packs/air-quality/cells.yml:3` and `:13` both key
`Environmental|Community` — a 24h PM2.5 mean claiming `live`, and a "% of days over the WHO guideline"
claiming `partial`. Air-quality is the flagship pack and both cells compute a value on any node with twelve
hourly buckets, which is every working node. See P2.

**Shorter diff:** `Governance|<scale>` is the core's, so reserve it: `packs.cells()` refuses a pack cell
whose key starts `Governance|`, and the two duplicate pairs get distinct keys or fold into `notes`.
**Could break:** a pack legitimately contributing a governance metric — `open-data-health` is exactly that,
which is why this needs the decision in §5.
**Check:** `tools/check_rules.py` fails on a duplicate cell key within a pack, and on any pack cell keyed
`Governance|*`. One dict and two lines, in the file that already parses every cells.yml.

### A10 · ρ's median is measured over a different population from its numerator
`app/index.py:104-114` · rung 6

```sql
count(f.alert_id) FILTER (WHERE f.t - a.ts < interval '24 hours') AS acted,
percentile_cont(0.5) WITHIN GROUP (ORDER BY extract(epoch FROM f.t - a.ts)/60) AS median_minutes
```

`acted` counts only actions inside 24 hours. `median_minutes` has no such bound — it is the median over
every matched action, including the ones that took a week and therefore did not count. The two numbers then
appear in one sentence, in the cell that goes to the Index (`index.py:94`):
`"{acted}/{alerts_act} acted; median detect-to-act {median_minutes} min"`.

A node with two act alerts, one answered in 5 minutes and one in 8 days, publishes "1/2 acted; median 5,762
min" — a median dominated by the alert that was not counted as answered.

**Shorter diff:** the same bound in the aggregate:
`percentile_cont(0.5) WITHIN GROUP (ORDER BY …) FILTER (WHERE f.t - a.ts < interval '24 hours')`.
**Could break:** `median_minutes` becomes NULL on a node whose only actions were late; the formatter at
`index.py:114` already handles NULL.
**Check:** `tests/test_logic.py` is the pure-function suite; ρ's SQL is not pure. The honest check is in the
report suite with two synthetic rows — or one `psql` assert in `install-smoke.yml`, which already has a
database up.

### A11 · the mesh gateway's broker password grants what the admin token guards on the HTTP side
`config/mosquitto/mosquitto.conf`, `app/main.py:158-175` · rung 4: mosquitto does ACLs

`POST /readings` was gated on 6 September for a reason its docstring states plainly
(`main.py:1278-1281`): *"a posted reading becomes a local, indoor sensor whose values fire act-level alerts
and enter live cells, so anyone on the WiFi could otherwise wake the household with 999 µg/m³ from a
curl."*

The MQTT path does the same insert. `main.py:166-174` takes `planetai/sensors/<id>/<metric>`, invents
`pod-<id>` with `"local": True`, and stores `float(body["value"])` at whatever metric name the topic
carried. The broker is not open — `allow_anonymous false` and a `password_file` — so this is not the same
exposure. But there is **no `acl_file`**, and `planetai meshtastic` creates one credential which is then
written into an ESP32's config on the household WiFi. Whoever can read that radio's config can publish
`local: true` readings at arbitrary metrics, and can subscribe to `msh/#` and read every alert the node
sends over the mesh.

Ranked low on purpose: it needs the gateway's credential, and the credential is on a device inside the
house. It is here because the asymmetry is unintentional — one path was hardened and its twin was not.

**Shorter diff:** an `acl_file` next to the `password_file`, two topic lines: the gateway user may write
`msh/#` and read `msh/#`; `planetai/sensors/#` gets its own user, or is dropped until something uses it.
**Could break:** an existing Meshtastic gateway if the ACL is wrong; `planetai meshtastic` writes both files
so it can write a correct pair.
**Check:** `tests/test_meshtastic.py` asserts the config's shape today; add the ACL file to what it asserts.

### A12 · `GET /health` returns the node's name and its exact coordinates to anyone — **RESERVED · prompt A**
`app/main.py:588-590` · **CONFIRMED on pai-clean**

```
$ curl -s localhost:8080/health
{"ok":true,"node":"lima-fresh",…,"lat":41.3874,"lon":2.1686,"city":"bali",…,
 "cell":{"id":"8839446033fffff","res":8,"edge_m":525,"caption":"… THE CELL THIS NODE STANDS IN"}}
```

`/export` rounds to 3 decimals (`main.py:838`) and F13 makes the same argument about outbound requests.
Reserved by the brief; no PR here.

---

## S · the scripts, the CLI and the release path

### S1 · `version_gap` still runs before the preflight, which the first review said to fix before committing
`bin/planetai:261` vs `:267-272` · one line

`CODE_REVIEW_2026-09.md`, §"The withdrawn hunk", left exactly one instruction on this code while it was
still uncommitted:

> **One thing to change before committing:** it runs *before* `tools/preflight.sh` (line 242). A machine
> below the floor now makes a network call and is offered an upgrade to a node it cannot run, before being
> told it cannot run one … Move `version_gap` below the `pf` block.

It landed above it. The S8 transcript is the proof in operation: the network fetch and the
`curl … | bash` offer print first, and only then does preflight say the machine has the wrong architecture
and too little memory.

**Shorter diff:** move `bin/planetai:261` to after the `fi` on `:272`.
**Could break:** nothing — `version_gap` returns early on a `.git` checkout and makes no state change.
**Check:** `tests/test_preflight.sh` — assert the line number of the `version_gap` call is greater than the
line number of the `bash tools/preflight.sh` call. A relative-order assert, the shape
`tests/test_sudo_prompt.sh` was converted to in `v0.42`.

### S2 · four unannounced `sudo` calls in `bin/planetai`, and the test that forbids them reads only `install.sh`
`bin/planetai:700`, `:715`, `:724`, `:1268`; `tests/test_sudo_prompt.sh` · rung 2

"Every sudo announces itself on the line before" is a standing constraint, and there is a test for it. The
test names one file, in every check it makes:

```
tests/test_sudo_prompt.sh:21   grep -q '^sudo_first() {' install.sh
tests/test_sudo_prompt.sh:29   src = open("install.sh").read()
tests/test_sudo_prompt.sh:83   awk '…' install.sh > /tmp/dockerbranch.$$
tests/test_sudo_prompt.sh:93   grep -q 'sudo -n -v' install.sh
```

`bin/planetai` has no `sudo_first`, no announcement helper, and four executed sudos:

```
700:    down) sudo tailscale down && say "left the mesh …"
715:        sudo brew services start tailscale >>"$LOG" 2>&1 || true
724:  sudo tailscale up $SSH_FLAG --hostname "$name" …
1268:   elif command -v systemctl …; then sudo systemctl enable --now ollama >>"$LOG" 2>&1 || (…)
```

`:715` and `:1268` are the sharp ones: both send output to the log and both end in `|| true` or a fallback,
so a refused password is silent and the command that needed it simply did not happen.

**Shorter diff:** lift `install.sh`'s `sudo_first` into `bin/planetai` — it cannot be shared, both files
must stand alone in a tarball (see §4) — and call it once at the top of `cmd_mesh` and `cmd_agent_local`.
**Could break:** `planetai mesh` on a machine where sudo is passwordless now prints one extra line.
**Check:** parameterise `tests/test_sudo_prompt.sh` over both files. The walk at its `:58-65` is already
file-agnostic; it is the four `open("install.sh")` calls that are not.

### S3 · a truncated tarball, an unreachable checksum, and `update.sh` says "Nothing was lost"
`update.sh:79-85` vs `install:87-92` · **CONFIRMED on pai-clean** · the finding that gates node #2

Served a 100-byte `planetai-node.tar.gz` from a local site with the `SHA256` file returning 404:

```
$ PLANETAI_SITE=http://127.0.0.1:8099/node0 ./update.sh </dev/null; echo "EXIT=$?"
   doctor:
     ✓ all modules in image      ✓ db healthy        ✓ app answering
     ✓ readings intact           ✓ views rebuilt     ✓ packs loaded
   >> schema 0.23 → 0.23
   >> updated. Nothing was lost: 6216 readings, 7 alerts, 8 actions.
EXIT=0
$ cat VERSION      v0.42-HEAD-4f96a38      # unchanged. No new code arrived.
```

With the checksum published for the untruncated build, it fails closed correctly (`exit 1`, "the download
does not match its published checksum"). The open path is the guard's own condition:

```bash
if command -v shasum >/dev/null && curl -fsSL "${SITE}/get/SHA256" -o "$tmp/sha" 2>/dev/null; then
```

Two silent fail-open conditions, both behind `2>/dev/null`: `shasum` absent (it is macOS's name; Debian
ships `sha256sum`), and the checksum fetch failing for any reason. Then `tar xzf` fails as the **left**
operand of an `&&` list, which `set -e` exempts, and the script carries on to the schema step, the rebuild,
the doctor and the closing sentence.

`update.sh:79` calls this *"the same check the installer makes"*. It is not. `install:87-92` fails closed on
all three, and its comment records that it once did not:

```bash
# The checksum is not optional. This used to skip silently when `shasum` was missing (it is macOS's name;
# Debian ships `sha256sum`), so on some machines the tarball was simply trusted. It is the only path now.
local sum=""; command -v shasum >/dev/null && sum="shasum -a 256"; [[ -n "$sum" ]] || { command -v sha256sum >/dev/null && sum="sha256sum"; }
[[ -n "$sum" ]] || { rm -rf "$tmp"; die "no shasum or sha256sum on this machine, so the download cannot be verified. …"; }
curl -fsSL "${SITE}/get/SHA256" -o "$tmp/sha" || { rm -rf "$tmp"; die "could not fetch ${SITE}/get/SHA256, so the download cannot be verified."; }
```

**Shorter diff:** those five lines, in `update.sh`, replacing the `if` — and `|| die` on the `tar xzf`.
**Could break:** a node updating from a site whose SHA256 file is genuinely missing now refuses instead of
pretending. That is the point.
**Check:** `tests/test_release_consistency.sh` already reads both files. Assert `update.sh` contains
`sha256sum` and that no checksum branch in either file is conditional on `command -v shasum` alone. Then the
run above, on `pai-clean6`, as the PR's verification.

**Node #2 does not update until this lands.** Lucas's machine is `update.sh`'s first run somewhere nobody
here can see; today a momentary 404 on the checksum leaves him on v0.41.2 having been told he is current.

### S4 · `planetai storage` prints the backup token to the terminal
`bin/planetai:1038` · rung 6, and it contradicts an invariant

```bash
echo "  Pulled by a NAS    GET /backups and /backups/<file> with this read-only token:"
printf '                     %s%s%s\n' "$B" "$(envget BACKUP_TOKEN)" "$N"
```

`BACKUP_TOKEN` authorises `/backups` and `/backups/{name}` (`_pull_ok`, `main.py:1082`, `:1092`) — every
database dump the node has made. `AGENTS.md`: *"`.env` holds secrets. Never print it, never paste it."* And
`planetai storage` is precisely the command somebody pastes into an issue when their backups have stopped —
which is the failure F15 describes.

`planetai support`, in S9 below, is specified to strip `.env` values. It would strip this one and then
`storage` would print it anyway.

**Shorter diff:** print `set` / `not set`, and add the token to `planetai ui`'s output, which is already the
one place that deliberately prints a token to a person sitting at the machine.
**Could break:** somebody's routine for setting up a NAS; `planetai ui` is one command away and already
prints the admin token.
**Check:** in `tests/test_shipped.py`, beside the existing secret assertions — no `envget BACKUP_TOKEN`,
`envget ADMIN_TOKEN` or `envget TELEGRAM_BOT_TOKEN` inside a `printf`/`echo` in `bin/planetai` outside
`cmd_ui`.

### S5 · two of the four `planetai storage set` arms validate nothing, and one of them turns off the only off-machine copy
`bin/planetai:1004`, `:1002` · **generalises F15**

The four arms of one `case`:

```bash
backups)  [[ -n "$val" ]] || fail "usage: …"           # three checks: non-empty, mounted, writable
          mounted "$val" || fail "…"
          mkdir -p "$val" … || fail "$val is not writable"
remote)   envset BACKUP_REMOTE "$val"; …               # none. And $val may be empty.
keep)     envset BACKUP_KEEP "$val"; …                 # none.  ← F15
data)     fail "…"                                     # refuses on purpose
```

`keep` is F15, already open: a non-numeric value makes `backup.sh:52`'s `find -mtime +$KEEP` exit non-zero
under `set -euo pipefail`, after the dump and before the export, the IPFS pin, the rclone copy and
`LAST_OK` — so the local dump keeps appearing, the doctor stays green, and the only copy that survives a
house fire stops.

`remote` is the same shape with a shorter fuse: `planetai storage set remote` with the argument forgotten
sets `BACKUP_REMOTE` to empty and reports
`off-machine copies to '' after each backup` — which reads like success. The off-machine copy is now off.

Forty lines away, `cmd_report` validates five arguments with a regex each (`:641`, `:647`, `:653`, `:658`,
`:677`). The pattern is in the file; it was not applied to the two arms where the failure is silent data loss.

**Shorter diff:** two lines, in `cmd_report`'s shape:
`[[ "$val" =~ ^[0-9]+$ ]] || fail "days is a whole number"` and
`[[ -n "$val" ]] || fail "usage: planetai storage set remote <rclone remote:path>"`.
**Could break:** nothing.
**Check:** `tests/test_running_state.sh` runs the CLI; assert `planetai storage set keep abc` exits non-zero
and leaves `.env` unchanged.

### S6 · nothing stops two updates running at once
`update.sh` · rung 3: `mkdir` is atomic

`grep -n "flock\|mkdir.*lock\|LOCK" update.sh bin/planetai` → nothing. Two `planetai update` runs — a cron
line and a person, or an impatient second terminal — will both back up, both unpack a tarball over the same
folder, and both apply `init.sql`. The unpack is the dangerous one: `update.sh:84` untars into the live
folder while the other run's rebuild is reading it.

**Shorter diff:** `mkdir "$LOCK" 2>/dev/null || die "another update is running (…). If it is not, remove
$LOCK."`, with a `trap 'rmdir "$LOCK"' EXIT` beside the existing one at `:15`. `mkdir`, not `flock`:
`flock` is not on macOS.
**Could break:** an update killed with `-9` leaves the directory and the next run refuses until it is
removed. The die message says which directory and why, which is the whole reason not to use a PID file.
**Check:** `tests/test_release_consistency.sh` — assert the lock exists and is a `mkdir`, not `flock`.

### S7 · neither install nor update keeps a transcript of the whole run
`install.sh:23`, `update.sh:21` · rung 3

Both keep a log, and both are per-step: `spin` redirects each command into `$LOG`/`$ULOG` and prints eight
lines of tail on a failure. What is not captured is the run — the questions, the answers, the warnings
between steps, the doctor rows, the sentence at the end. That is what a tester pastes, and today they paste
a screenshot or the eight lines the last failure happened to show.

**Shorter diff:** at the top of both, once, in the shape of `update.sh`'s existing self-copy re-exec:
`[[ -z "${PLANETAI_TRANSCRIPT:-}" ]] && command -v script >/dev/null && exec env PLANETAI_TRANSCRIPT=1 script -qefc "$0 $*" .planetai-install-transcript.log`.
**Could break:** `script`'s flags differ between BSD and GNU — `-qefc` is GNU; macOS wants
`script -q file cmd args`. Both branches, the way `tools/bundle.sh:25-27` already tries and falls back on
tar's flags.
**Check:** `tests/test_diagnose.sh` — after a failed install in a sandbox, the transcript exists and
contains the first question.

### S8 · `planetai setup` on a running node refuses, quoting floors the node already survived
`bin/planetai:267-272` vs `:309-322` · **CONFIRMED on pai-clean**

On a machine running the node, `planetai setup` exits 1 during the preflight and never reaches the
Update / Reconfigure / Nothing / Remove menu:

```
$ docker compose ps -q | wc -l        2
$ ./planetai setup ; echo "exit=$?"
  arch          arm64      ✗   the node's database image … is published for linux/amd64 only
  memory        3 GB       ✗   4 GB is the container runtime's own minimum; this machine has 3 GB
  2 checks failed. Each line above carries the fix. Nothing was installed.
exit=1
```

The branch at `:309` is correct — `node_running` (`:281`) properly distinguishes a running node from an
install that stopped — and on a machine that passes preflight the menu appears. The bug is the gating:
`[[ $pf -eq 0 ]] || exit 1` at `:271` applies **install-time floors to a post-install menu**. On any machine
below them — arm64, under 4 GB, the revive-a-laptop cases `docs/REVIVE_A_LAPTOP.md` is written for — a node
that has been running for days can never be updated, reconfigured or removed through the command every
tester is told to type. This VM has run that node for three days with 6,210 readings in it.

The floors are not wrong, and I checked: `docker image inspect postgis/postgis:16-3.4-alpine` really is
`linux/amd64`, and `docker compose exec db uname -m` really is `x86_64` under emulation. It is a fair
warning about an install. It is not a verdict on a node.

**Shorter diff:** skip the preflight when `node_running` is 1 — the variable is computed at `:281`, eleven
lines below, so the two blocks swap order and the condition becomes
`if [[ "${PLANETAI_PREFLIGHT_OK:-0}" != 1 ]] && [[ $node_running -eq 0 ]]; then`. Fold S1's move into the
same diff; they are the same three lines.
**Could break:** a running node on a machine that has since lost Docker — `node_running` is false then, so
the preflight still runs, which is right.
**Check:** `tests/test_running_state.sh` already fakes a running node; assert `planetai setup` reaches the
string "What would you like to do?" with the preflight forced to fail.

### S9 · there is no one command that collects what a diagnosis needs
`bin/planetai` · rung 2: the four pieces all exist

`docs/TROUBLESHOOTING.md` (215 lines, new in `v0.42`) and `skills/troubleshoot-node/SKILL.md` both open by
asking for `planetai doctor --json`, `planetai status --json`, twenty lines of logs and the version — four
commands, and the skill has to say "never `.env`" because the obvious next thing a helpful person pastes is
`.env`.

`grep -n "support)" bin/planetai` → nothing.

**Shorter diff:** one arm and one function, calling what already exists:
`cmd_support() { cmd_version; cmd_doctor --json; cmd_status --json; docker compose logs --tail=200 app | sed -E 's/(TOKEN|KEY|PASSWORD)=[^ ]*/\1=<stripped>/g'; }`
plus the `.env` **keys** with every value replaced, which is the one thing not currently obtainable safely
and the thing most often needed.
**Could break:** nothing new; it is a composition of four existing commands.
**Check:** `tests/test_diagnose.sh` — run `planetai support`, assert the output contains the version and the
doctor rows and matches no value from `.env`. That last assert is the whole point of the command.

### S10 · `make test` is one `&&` chain, and `make lint` exits 0 with gates that did not run
`Makefile:30`, `Makefile` lint target · the multiplier

`Makefile:30` is 25 suites joined by `&&`. The first failure hides the other 24 and nothing counts what ran,
what failed or what skipped. `make lint` has the mirror problem: this pass's run printed
`- requirements resolve skipped (venv failed)` as one warning among twelve success lines and exited **0**.
Six suites print their own "skipped" lines that nobody tallies.

This is the reason F3 has stayed open through five releases: a green local gate is not a green build, and a
skip that reads as a pass is not even a green gate.

**Shorter diff:** `tests/all` — a runner that keeps going, counts pass/fail/skip, prints one line per suite
and exits non-zero if anything failed **or** if a skip was not on an expected-skip list. Then `make test`
calls it and `lint.yml` runs `make test` with `numpy` and `duckdb` on the pip line (F3).
**Could break:** the first green CI run will be red, because 25 suites have never all run on a clean
runner. That is the point of doing it first.
**Check:** the runner is its own check. `tests/all` with one suite forced to fail must exit non-zero and
still report the other 24.

### S11 · the backup cron the installer writes cannot find `docker`, and the doctor calls it green
`install.sh:509-510`, `bin/planetai:546` · **CONFIRMED on node #1, 10 September** · found by running S-group's own verification

`install.sh:510` writes:

```bash
( crontab -l 2>/dev/null; echo "17 3 * * * cd $(pwd) && ./backup.sh >/dev/null 2>&1 # planetai-backup" ) | crontab -
```

No `PATH`. cron runs with `/usr/bin:/bin`, and on every machine this project targets `docker` is somewhere
else — `/opt/homebrew/bin` for Colima or Homebrew, `/usr/local/bin` for Docker Desktop, `~/.orbstack/bin`
for OrbStack. Installed on node #1 and tested with a one-shot line two minutes out:

```
./backup.sh: line 44: docker: command not found
19:30 backup FAILED: pg_dump failed
```

And the row that names it went **green**, because `bin/planetai:546` is
`grep -q planetai-backup <<< "$(crontab -l 2>/dev/null)"` — it checks that a line exists, not that the line
can run. So installing the cron made the doctor greener and the backups no more likely. It is bounded:
`a backup in the last 2 days` (`:543`) goes red after 48 hours, so this is a two-day lie rather than a
permanent one — on the one thing protecting readings that exist nowhere else.

Also worth knowing for anyone writing a cron line here: **`%` is special in a crontab command field.** The
one-shot test's `date -u +%FT%TZ > /tmp/stamp` never wrote a stamp in either run, because cron read `%F` as
a newline. Escape it or avoid it; `backup.sh`'s own line has no `%` and is fine.

With `PATH=/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin` as the crontab's first line, the same test:

```
19:33 backup: ./backups/bayu-ungasan-2026-09-10.sql.gz (2.1M)
19:33 backup: export exports/bayu-ungasan/2026-09-09.json
LAST_OK  2026-09-10T11:33:02Z
```

**Shorter diff:** `install.sh` writes a `PATH=` line into the crontab, derived from where it just found
docker — it already resolves it during the install. Two lines, and `>/dev/null 2>&1` becomes a log file so
the next failure is readable.
**Could break:** a crontab that already has a `PATH` line for something else; write it only if absent, and
`crontab -l` is already read on the line above.
**Check:** in `tests/test_running_state.sh` — the crontab line `install.sh` writes must be preceded by a
`PATH=` containing the directory of `command -v docker`. And in `bin/planetai:546`, the doctor row checks
the same thing rather than the line's mere existence.

---

## P · the packs

### P1 · one unmapped clinic turns the monthly place report into its own source code
`packs/place/rules.yml:14`, `app/main.py:396-398` · **CONFIRMED on pai-clean**

```
$ psql -c "SELECT round((SELECT value FROM observations WHERE sensor_id='place-point' AND metric='nearest_health_m')) AS clinic_m"
 clinic_m
----------
          (NULL)

$ # format the shipped template the way main.py does
format raised: ValueError : Unknown format code 'f' for object of type 'str'
--- the alert text the household receives ---
🏘️ What is around you, this month.

About {buildings:.0f} buildings within a kilometre, {commercial_pct:.0f}% of them shops, offices or
hotels. On the map: {food:.0f} places to eat, {schools:.0f} schools, {health:.0f} clinics or pharmacies,
the nearest health care {clinic_m:.0f} m away. …
```

The chain is three lines in one place:

```python
try:
    text = tmpl.format(**{k: ("—" if v is None else v) for k, v in row.items()})
except (KeyError, ValueError, TypeError):
    text = tmpl
```

`round(NULL)` is NULL, the sentinel makes it the **string** `"—"`, `{clinic_m:.0f}` on a str raises, and the
`except` substitutes the raw template. Silently: no log line, no `status.errors` row.

**It is a class, not a rule.** The sentinel is incompatible with every `{x:.Nf}` in every message. A scan of
every shipped rule for such a slot fed by a nullable scalar subquery or aggregate:

```
packs/place/rules.yml  place_around: ['buildings', 'clinic_m', 'food', 'health', 'schools']
risky format slots: 5
```

Five today, all in the one rule, and any new rule inherits it. `tools/check_rules.py:105` already checks
that a placeholder appears in the SQL's output columns, which passes here because it does — a lint cannot
see a NULL.

**Shorter diff:** at the sentinel, so every caller is fixed at once — drop the format spec for the keys
whose value is None before formatting:
```python
vals = dict(row)
for k, v in row.items():
    if v is None:
        tmpl = re.sub(r"\{%s:[^}]*\}" % re.escape(k), "{%s}" % k, tmpl); vals[k] = "—"
text = tmpl.format(**vals)
```
Four lines, one place, `re` already imported.
**Could break:** a message that wanted the exception — none; the fallback prints braces at a household.
**Check:** `tests/test_report_templates.py` already asserts all three locales are complete; add one case
formatting `place_around`'s template with `clinic_m=None` and assert `"{" not in text`.

### P2 · two shipped packs define two cells with one key
`packs/air-quality/cells.yml:3`, `:13`; `packs/open-data-health/cells.yml:2`, `:9` · **CONFIRMED**, see A9

Air-quality is the flagship pack, enabled everywhere, and its two `Environmental|Community` cells both
compute a value on any node with twelve hourly buckets. One of the two is lost, and they carry different
units — "µg/m³ PM2.5 (24h mean)" and "% of days over the WHO 24h PM2.5 guideline" — so which one survives
changes what the cell *means*, not just its value.

**Shorter diff:** distinct keys where the Observations base has them, or fold the weaker of each pair into
`notes`. Four lines of YAML across two files.
**Check:** the `check_rules.py` gate in A9. It covers both.

### P3 · the heat thresholds are one street in Bali, and `presets/` ships four cities
`packs/heat/rules.yml:21`, `:41` · **cross-reference: this is F12, still open**

Nothing to add to F12's reading, which is correct and whose proposed plumbing (`current_setting` from the
session `options=` string, `app/main.py:87`) is right. Noted here only so the P group is not read as
complete without it, and because it is the finding §5's second decision blocks.

### P5 · nearby's `baliairdispatch` source is a named place in a domain-blind core
`app/sources.py:334-344`, `packs/nearby/` · **pinned ID**

What HEAD actually does: the source is off unless `BAD_ENABLED=1`, and its three parameters
(`BAD_RADIUS_KM`, `BAD_MIN_SEPARATION_M`, `BAD_INCLUDE_INDOOR`) are already runtime settings with defaults
in the code. So the configurability half of the concern is answered. What is not: the adapter, the
settings, the `sc-`/`ag-` skip logic and the `bad-` id prefix name one regional network inside
`app/sources.py`, which `ARCHITECTURE.md` describes as domain-blind, while `packs/nearby/` exists and is
where a regional network belongs.

I am not ranking this as a defect. It is the one finding in this pass that is a design question rather than
a bug, its cost today is zero, and moving an adapter that node #1 depends on to chase a layering rule is
the kind of change this repository is right to refuse until something asks for it. **The trigger to name:
the second regional network.** When a node in another city needs a second one of these, the adapter moves
to a pack and `sources.py` keeps only the generic ring.

---

## D · the dashboard

### D1 · v0.41.1's guard covers three of eighteen cards
`app/static/index.html:452`, `:533-534`, `:641` · **cross-reference: this is F8, still open**

Confirmed unchanged at this commit: 18 `data-card` ids, 3 `card('#…')` calls, one `try` at `:516` and one
`catch` at `:644`. F8's reading and its `tools/check_ui.py` gate are right; nothing to add.

### D2 · pressing Cancel on "What did you do?" publishes ρ = 1.0
`app/static/index.html:1049` · **CONFIRMED in a browser against the node**

```js
const note = prompt('What did you do? A few words is enough.','') || 'acted';
const r = await fetch('/actions', {method:'POST', …});
```

`prompt()` returns `null` on Cancel; `null || 'acted'` is `'acted'`; the fetch runs. Driven with
`window.prompt` returning null, which is what the browser returns when the button is pressed:

```
promptCalls : 1
before      : { alerts_act: 1, acted: 0, rho: 0,    median_minutes: null }
after       : { alerts_act: 1, acted: 1, rho: 1,    median_minutes: 0 }
```

An empty submit does the same. ρ is the number this project exists to produce; `index.cells` publishes it as
`Governance|<scale>` at state `live` once five rows exist. A dialog the household dismissed becomes a
published claim that the loop was closed — and, per A10, drags the median with it.

**Shorter diff:** `const note = prompt(…); if (note === null) return;` — one clause, before the fetch. Keep
`|| 'acted'` for the empty string if an empty note should still count; that is a judgement, and recording
"acted" with no words is defensible where recording a cancellation is not.
**Could break:** nothing. The button's other path is unchanged.
**Check:** `tools/check_ui.py` parses the script; assert `act(` contains `=== null`. Crude but it is the
gate that exists, and `tests/test_dashboard.py` can assert the same string.

### D3 · Reset does not reset: the layout comes back from the node on the next reload
`app/static/index.html:1038` · **CONFIRMED in a browser against the node**

`layoutReset()` clears `localStorage` and the in-memory copy and does **not** clear `UI_LAYOUT` on the node.
`loadLayout()` (`:1016`) fetches the node's copy on every fresh page load and prefers it.

```
$ # a layout saved on the node, then Reset pressed
after Reset:  localStorage = null      node UI_LAYOUT = {"order":[],"hidden":["tile:the-street"]}
$ # reload
loadLayout() = { hidden: ["tile:the-street"], order: [] }
the-street tile:  still gone
```

So on a wall screen the sequence is: hide a card by accident, press Reset, watch it come back tomorrow.
Nothing in the interface says Reset is local-only, and `layoutSave` — which is honest about this in the
other direction, toasting "Saved in this browser only (401)" — is right beside it.

**Shorter diff:** in `layoutReset`, make the same PUT `layoutSave` already makes with an empty value when a
token is present, and toast the same two-case message. Four lines, reusing the call at `:1044`.
**Could break:** somebody using Reset deliberately as a per-screen override — the toast should say which
happened, which is the same four lines.
**Check:** `tests/test_dashboard.py` — assert `layoutReset` contains `UI_LAYOUT`.

### D4 · the admin token lives in `localStorage`, and it unmasks the Telegram and AI keys
`app/static/index.html:507`, `:1060`; `app/main.py:1074-1079` · design note, ranked low, stated once

`localStorage['planetai_admin']` holds the admin token for the life of the browser profile, and that token
opens `GET /settings/raw`, which returns every runtime setting **unmasked** — `TELEGRAM_BOT_TOKEN`,
`AGENT_ONLINE_KEY`, `AGENT_REMOTE_KEY`. So any script execution in the dashboard's origin is a full
credential compromise, not a defacement.

**I looked for the execution and did not find one**, and that is worth recording as carefully as a finding:
`esc()` (`:459`) escapes `& < > "` and is applied on every path I traced that carries external data —
`esc(r.name)`, `esc(r.story)`, `esc(r.url)`, `esc(t.note)`, `esc(a.acted_note)`,
`esc(a.rule_id)`. The unescaped interpolations are `${t.unit}`, `${t.label}`, `${w.unit}`, `${r.unit}`,
`${h.node}` and `${h.city}`: every `unit:` and `label:` in this file is a literal string, and `h.node` /
`h.city` are the household's own `.env`. `data-card="…${(r.name||'').toLowerCase().replace(/[^a-z]+/g,'-')}"`
strips everything but `a-z`.

Two things keep it on the list. `esc()` does not escape `'`, so any future interpolation into a
single-quoted attribute breaks out. And a pack's `cells.yml` `unit:` string is third-party data that reaches
`planetai cells` today and would reach a dashboard card the day someone renders `/cells` — which is a
natural next feature.

**Shorter diff:** add `'` to `esc()`'s character class (one character), and route `unit` and `label` through
it (three call sites). No behaviour change today; it closes the class before the feature that opens it.
**Could break:** nothing — the literals contain none of those characters.
**Check:** `tools/check_ui.py` — every `${…}` inside a template literal assigned to `innerHTML` is either
`esc(…)`, a call to `fmt`/`spark`/`compass`, or a member of a named allowlist.

---

# §3 Checked and found clean

Recorded so nobody spends an evening re-finding them, and because two of them are the kind a reviewer
reports wrongly:

- **Path traversal on the three file-serving routes.** `/backups/{name}` (`main.py:1093`),
  `/exports/{node}/{name}` (`:1114`) and `/static/{name}` (`:1151`) all resolve through `Path(x).name`,
  check the suffix, and in the static case go through a `COMPANIONS` allowlist. `../` cannot escape.
- **`GET /settings` honours its allowlist.** 47 rows returned unauthenticated, 28 with a visible value,
  every one of them in `settings.PUBLIC`; `AIRGRADIENT_HOSTS`, `EE_KEY_FILE`, `AGENT_REMOTE_URL`,
  `AGENT_ONLINE_URL`, `MESH_GATEWAY_NODE_NUM` and `BACKUP_TOKEN` all read `•••• set`. The bug is that
  `/sensors` publishes what this route hides (A7) — not that this route is wrong.
- **No SQL injection.** The only interpolated SQL is `main.py:857`, `:859` and
  `packs/place/adapter.py:229`, and all three interpolate a hardcoded tuple of table names.
- **`tolerance` is still the only unbounded numeric parameter.** An AST walk over every route agrees with
  F11: one hit, `place_geojson`.
- **`cmd_remove` is right.** It counts what will go before it touches anything, handles the no-daemon case
  that orphaned a tester's volumes, asks twice, and makes you type the node's name. Do not simplify it.
- **`layoutSave` is honest.** It toasts "Saved in this browser. Unlock Set up to save for every screen." or
  "Saved in this browser only (401)". D3 is that its sibling is not.
- **`tests/test_sudo_prompt.sh`'s line-number assert is gone.** The first review asked for a relative-order
  assert; `v0.42` delivered one (`:24-26`, `:58-65`). It is the only fix in the 25 that arrived with its
  gate. S2 is that it reads one file.

---

# §4 Looks over-engineered, isn't

Carried forward from the first review unchanged and re-confirmed at this commit — `report.py`'s `T` dict,
`_bearer_ok`'s loop with no early return, `update.sh`'s self-copy and re-exec, `hb_line`'s `|| true`,
`index.run_ro`'s `_ro["missing"]` latch, `gen_floors.py` generating bash into `preflight.sh`, the two
distance *functions* in `sources.py`, `data/platform_floors.yml`'s dates and 180-day expiry,
`tools/check_docs.py`'s word-to-integer table, `agent: build: ./app` naming the image `app` already built.

Four to add:

- **Three separate `.env` reader functions in three scripts, and now four.** `install.sh`, `update.sh`,
  `backup.sh` and `bin/planetai` must each work alone inside a tarball with no shared library. The
  duplication is the constraint. F16 is `install.sh`'s **seven inline copies**, which are a different thing
  and are real.
- **`cmd_remove`'s length.** 118 lines to delete a node. Every one of them is a thing that went wrong once.
- **`v0.42`'s three new `check_docs.py` gates** — skill frontmatter shape, `AGENTS.md` routing to every
  skill, `llms.txt` links resolving. A prompt nobody lints rots faster than the docs it replaced. The
  hygiene group must not re-add these; they are in.
- **`update.sh`'s `.before-update` copies with `cp -p`.** The `-p` is there because `.env` is 0600 and the
  copy must not be world-readable. Not defensive noise.

---

# §5 Would need a decision

Three, and the first is the only one that blocks a PR in this pass.

1. **May a pack contribute a `Governance|*` cell (A9)?** Reserving the key for the core's ρ is two lines and
   closes the collision, but `open-data-health` exists precisely to contribute a governance metric about a
   city's open-data portal, and that is a real Index cell. The alternatives are a sub-key
   (`Governance|City|portal-freshness`, which the Observations base may not permit), or letting the core's ρ
   move to its own key and leaving `Governance|<scale>` to packs. **Blocks:** the A9/P2 PR. The duplicate
   keys *within* a single pack (P2) need no decision and can go first.

2. **May pack thresholds be settings (P3/F12)?** Unchanged from the first review's §7.2, and the tension is
   still `tools/check_docs.py:163` asserting the pack README quotes the rule's number. Carried, not
   re-argued.

3. **Does `sources.py` keep a named regional network (P5)?** Answered above as "yes, until the second one".
   Named here so the answer is a decision on the record rather than an omission.

---

# §6 The order to fix them in

Six groups. Inside a group the order is free; the groups are not, and the first one is not negotiable.

**1 · The multiplier.** S10, then F3. `tests/all` that keeps going and counts failures *and* skips; then CI
runs `make test` with `numpy` and `duckdb` installed. Nothing else lands first, because every fix below
needs a build that runs the suites, and the first push should be red.

**2 · Data and boundary one-liners.** The first review's nineteen one-liners, plus from this pass: A10
(ρ's median), P2 (duplicate cell keys within a pack, with the `check_rules.py` gate), S4 (stop printing the
backup token), D2 (Cancel returns), D3 (Reset resets), D4 (`'` in `esc()`). Each is one to four lines with
one assert.

**3 · Stop-the-node.** A2, A8, A3+A4, A1 — in that order, worst first. A2 and A8 are the same shape in two
files and share a gate. A4's `real()` helper is what A3 and A1 both consume, so it lands with them, not
before them. Then F2+F5 (A6's reading) and F15+S5 in one diff each.

**4 · Wrong-answer.** P1 (the NULL format class, at the sentinel), then A9 once §5.1 is answered, then the
PROV-O vocabulary and `GET /provenance` — vocabulary only, no RDF store, gated on `/provenance` returning
valid PROV-JSON for one synthetic and one external row. F6 (`kind` back in `/export`) belongs here and
touches the export shape, so it waits for `SPEC_custody`.

**5 · The stranger's first hour.** S3 first and alone — it is the release gate for node #2 and nothing
should ride with it. Then S1+S8 in one diff (the same three lines), S2, S6, S7, S9, F9, F20, F21.

**6 · Hygiene.** F24, F23, F25, F19, F22, F16, F1. The `check_docs.py` gates `v0.42` added are done; extend
that file for F21's pack-directory comparison and the badge, and do not re-add the three that are in.

**7 · Consolidation, optional per item.** F17 (`planetai_metres` in `init.sql`) and F18 (containers as root,
reticulum first). F17 touches pack SQL, so it lands after `SPEC_custody` is accepted.

**Touching `s.local`, and therefore waiting on `docs/SPEC_custody.md`:** A9's cell SQL only insofar as it
reads `s.local` through the packs; P2's air-quality cells (both filter `s.local`); `index._buckets`
(`index.py:55-56`), which is the honesty check every `live` claim passes through. No PR in this pass changes
what `s.local` means, and the three above are marked in the plan.

**Owned by prompt A and not by any PR here:** A7 and A12, plus F10 and F11.
