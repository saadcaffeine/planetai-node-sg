# Code review — September 2026

Reviewed at `9d0ac57` (main, v0.41.2-52), clean tree. A +24-line hunk appeared in `bin/planetai`
mid-review and was withdrawn again before it ended; it is read in §5 because it will be back, but it is
not in the tree and no line number here depends on it.

## What this is

A single-machine climate observatory you install at an address. Two containers: Postgres/PostGIS and one
Python process that polls everything measuring one place — a Smart Citizen kit on the WiFi, an AirGradient,
a LoRa radio over MQTT, the public stations nearby, a city's CKAN portal, CAMS and Open-Meteo point samples,
Earth Engine's view of the land — into one `readings` table with one schema from the room to the planet.
SQL rules in `config/rules.yml` and in thirteen pack folders read that table as a read-only role and write
`alerts`; a report scheduler writes one deterministic sheet every N hours in the node's own time zone, in
three languages, and the `reports` row is the lock rather than a timer. Alerts go to Telegram, Home Assistant,
a LoRa mesh and an LXMF address. A one-file dashboard reads the same public API a NAS and an MCP agent read.
The number the project actually cares about is ρ — the share of act-level alerts a person answered — which is
the one figure that cannot be measured from orbit, and the reason `POST /actions` exists at all.
Raw readings never leave; hourly means, cells, alerts and ρ leave as a daily CC-BY export. A `planetai` CLI
in Python-3.9-stdlib-only bash does setup, preflight, doctor, update, backup, restore and the radios.
Distribution is a tarball on a Cloudflare site, verified by checksum, with `install`/`preflight` as stubs
that fetch from `main` so a fix ships without a deploy. The whole thing is written as if every bug had a
tester's name attached, and most of the comments are that tester's name.

## Gates, as run

Run on this Mac (arm64, macOS 15, Docker/OrbStack up), not a Linux VM — see "not run" below.

```
$ make lint
  17 floors, all sourced and dated; oldest read 1 days ago (runtimes.orbstack, 2026-09-08), limit 180
  floors in tools/preflight.sh match data/platform_floors.yml
  docs/PLATFORMS.md matches data/platform_floors.yml
  111 strings inventoried in data/strings/en.yml
  init.sql + Dockerfile + compose mounts + no litter ok
  24 snippets checked, 0 would fail on Python 3.9
  44 documents check out
  GUI: script parses; every id, endpoint, field and asset resolves; ...
  requirements resolve on python 3.12 ok
  every pack script that needs a pack library says how to install it
  39 rules and cells check out against init.sql
  app imports, 44 routes
ok
LINT_EXIT=0

$ make test
  ... 180 lines, every suite passing, ending:
  all earth pack tests pass
TEST_EXIT=0
```

**Finding zero: both gates are green, and that is the problem.** `make test` runs 17 suites here and
CI runs one of them (§F3). A green local gate is not a green build.

Not run, and why:
- `.github/workflows/install-smoke.yml` — needs a clean amd64 Linux VM; this machine is arm64 macOS.
- The app against a live database — no `.env` and no node on this machine; `make import-check` covers the
  import path only, and did (44 routes).
- `tools/preflight.sh` on anything but this Mac. Its Linux branches are read, not executed.
- Nothing was deployed, shipped, committed or pushed.

`floors-are-data` **is already merged** — `3e7e11c`, "Merge pull request #6", 9 September 10:36, +1,933/−206.
There is no branch left to review before merging; the branch's content is reviewed here as part of main,
and §5 covers what should have been caught on it.

---

## Findings

Ranked by risk × size of the diff that fixes it.

### F1 · `planetai.fab.city` serves eleven internal working documents
`../planetai/.assetsignore` · **rung 1: this should not exist on the public origin at all**

Verified live, just now:

```
200  https://planetai.fab.city/Makefile
200  https://planetai.fab.city/docs/morning_review_punch_list.md
200  https://planetai.fab.city/scripts/check_html.py
404  https://planetai.fab.city/wrangler.toml     (correctly ignored)
404  https://planetai.fab.city/src/index.js      (correctly ignored)
```

`wrangler.toml` sets `[assets] directory = "./"` — the whole repository is the document root. `.assetsignore`
excludes `src/ functions/ wrangler.toml .assetsignore .git/ .gitignore *.sh README.md archive/` and **not**
`docs/`, `scripts/` or `Makefile`. `docs/` holds eleven files including one headed "thinking note for the
internal review", one naming a colleague's private review of the Spanish text, a funder pre-submission
checklist, a landing-page pivot proposal, and a punch list written in the second person about the author's
own night. Nothing links to them and there is no `robots.txt` (404), so they are crawlable and not
discoverable — the worst pair.

**Shorter diff:** add `docs/`, `scripts/`, `Makefile`, `*.md` to `.assetsignore`; keep an explicit allow for
any `.md` the site actually serves (`core-ideas-paper.md` is linked).
**Could break:** a page linking a doc under `docs/` — grep found none in `*.html` outside `archive/`.
**Check:** `curl -s -o /dev/null -w '%{http_code}' https://planetai.fab.city/docs/pre_submission_checklist.md` → `404`.

### F2 · the reticulum container is handed the whole `.env`
`docker-compose.yml:91` · **rung 1: a container gets the secrets it uses, or none**

From a real `docker compose config`:

```
reticulum   75 env keys; user=<root>
   secrets visible to reticulum: ADMIN_TOKEN, AGENT_ONLINE_KEY, AGENT_REMOTE_KEY,
   AGGREGATE_TOKEN, BACKUP_TOKEN, EE_KEY_FILE, PARENT_TOKEN, POSTGRES_PASSWORD,
   TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_IDS
```

`app/reticulum_bridge.py` reads exactly six: `LOG_LEVEL`, `NODE_NAME`, `NODE_API_URL`, `RETICULUM_DATA`,
`RETICULUM_ALERT_DESTINATIONS`, `RETICULUM_ANNOUNCE_S`, `RETICULUM_CONFIGDIR`. It is also the one container
that terminates untrusted traffic from strangers on a Reticulum network (`ports: 4242`), so it is the worst
place in the compose file to keep the database password.

**Shorter diff:** delete `env_file: .env`; add those six to the existing `environment:` block as
`${VAR:-}` pass-throughs.
**Could break:** `RETICULUM_ALERT_DESTINATIONS` set only in `.env` stops reaching the bridge if it is
omitted from the list — it must be one of the six.
**Check:** `docker compose --profile reticulum config | python3 -c "import sys,yaml;e=yaml.safe_load(sys.stdin)['services']['reticulum']['environment'];assert 'POSTGRES_PASSWORD' not in e and len(e)<10, e"`

### F3 · CI runs one of seventeen test suites
`.github/workflows/lint.yml:29-32` · **rung 2: the suite already exists; run it**

`lint.yml` ends with `adapter unit tests (no network)` → `tests/test_sources.py`. Nothing else. Sixteen
suites — including every security assertion in `tests/test_shipped.py` ("write endpoints gated", "token
compares constant-time", "dumps carry no settings rows", "pack SQL runs read-only", "every container log
is capped") — run only on a developer's machine. `make import-check`, written after "a function called as
if it were a string took the node down for an hour (5 Sep)", is skipped in CI too: `lint.yml` installs
`pyyaml` and never `app/requirements.txt`, so the `if python3 -c 'import fastapi'` guard in the Makefile
falls through with `- import check skipped`.

**Shorter diff:** `pip install pyyaml numpy duckdb` on the existing pip line, then `- run: make test` in
place of the hand-rolled last step.
**Could break:** `tests/test_earth.py` imports `numpy` and `tests/trustdb.py` imports `duckdb`
unconditionally — both must be in that pip line. Nothing else in `make test` needs a network or a database
(it passed here with `- ground check skipped`).
**Check:** the CI log for a push shows `all earth pack tests pass` as the last test line.

### F4 · `.env.example` ships a setting whose value is its own comment
`.env.example:143` · **rung 6: one line, and it is the wrong one**

```
AGENT_REMOTE_URL=                      # a bigger local model on your tailnet, e.g. http://...
```

Docker Compose's `env_file` parser strips an inline comment only when there is a value in front of it. With
an empty value it takes the comment. Verified from `docker compose config`, resolved on the `app` service:

```
resolved values that are actually a COMMENT: 2
  AGENT_ONLINE_URL = '# https://api.anthropic.com/v1 or https://api.openai.com/v1 (secret ke'
  AGENT_REMOTE_URL = '# a bigger local model on your tailnet, e.g. http://100.107.91.18:8082'
```

`AGENT_ONLINE_URL` is harmless: `app/agent_loop.py:74` requires the key too, and that one is genuinely
empty. `AGENT_REMOTE_URL` is not — line 76 gates on the URL alone, so every fresh node with the agent
profile builds a ladder with a bogus `remote` rung above `local`. I ran the failure to see how far it goes:

```
$ python3 -c "...hc.post(f'{that_string}/chat/completions')"
raised: httpx.UnsupportedProtocol      is httpx.HTTPError: True
```

So it is caught at `agent_loop.py:190`, skipped for five minutes, and `local` answers. The cost is a wasted
round on the first message after every restart, a warning line every five minutes, and `/model` in Telegram
listing a rung that does not exist. Bounded, but the lint gate written for this exact class **permits it on
purpose**: `bin/planetai:505` tests `^[A-Z_]+=[[:space:]]+[^[:space:]#]`, excluding `#`.

**Shorter diff:** move both comments to their own line above the key.
**Could break:** nothing.
**Check:** one assert, in `make lint` — this is the smallest thing that would have caught it:
`python3 -c "import re;assert not re.search(r'^[A-Z_]+=[ \t]+#', open('.env.example').read(), re.M)"`

### F5 · `planetai reticulum` cannot succeed, and its doctor row is always red
`docker-compose.yml:95`, `bin/planetai:785`, `bin/planetai:518` · **rung 6**

Every published port, from `docker compose config` with all four profiles on:

```
8080, 5432, 4001, 5001, 8085, 1883, 4242
```

`4243` is not there and never has been (`git log -p -- docker-compose.yml` has no `4243` in any revision).
`app/reticulum_bridge.py:128` binds `0.0.0.0:4243` inside the container; `Dockerfile.reticulum:5` EXPOSEs it,
which publishes nothing. Both host-side callers use `localhost:4243`:

- `bin/planetai:785` polls it thirty times, then `fail "the bridge did not come up: planetai logs reticulum"`
- `bin/planetai:518` is the doctor's `reticulum bridge up` check

The app is fine — `RETICULUM_URL=http://reticulum:4243` (`bin/planetai:781`) is container-network. So the
bridge works and the CLI says it doesn't. `docs/archive/reviews/BETA_READINESS_2026-09.md:336` records the address
being read out of the log, not out of `/health`, which is consistent with the curl having failed then too.

**Shorter diff:** `ports: ["4242:4242", "127.0.0.1:4243:4243"]`.
**Could break:** nothing; `4243` on loopback only, matching the `db` and `ipfs` pattern.
**Check:** `planetai reticulum` prints an LXMF address instead of failing after 60 s.

### F6 · a stray `#` deleted three fields from the open-data export
`app/main.py:832` · **rung 6**

```python
rows = [{"t": r["bucket"], "sensor": name(r),   # q() already renders timestamps as ISO strings "local": r["local"], "indoor": r["indoor"], "kind": r["kind"],
         "metric": r["metric"], ...
```

`local`, `indoor` and `kind` are inside the comment. Parsed, not read by eye:

```
$ python3 -c "<ast walk over main.export>"
keys: ['t', 'sensor', 'metric', 'mean', 'min', 'max', 'n']
```

The SQL at line 822 still selects all three. A consumer of the CC-BY export therefore cannot tell a CAMS
model point-sample from a measured reading except by matching sensor-id strings — in a repository whose
provenance rule is that `live` and `derived` must never be confused. Introduced in `e2be884` (6 Sep), a
fix for "/export returned 500 on every call".

**Shorter diff:** move the comment to the end of the line; keep `kind` at minimum.
**Could break:** a consumer keyed on the current shape. `tools/nas/pull.py` and every test are indifferent.
**Check:** the AST assert above, in `tests/test_shipped.py`: `assert {"t","sensor","metric","kind"} <= keys`.

### F7 · the language dropdown silently resets a Spanish node to English
`app/static/index.html:1090` · **rung 6**

The select offers `en` and `id`. `es` is a real locale: `app/report.py:397` carries the full third dict,
`tests/test_report_templates.py` asserts all three, `presets/santiago.env` exists. With `ALERT_LOCALE=es`
neither option is `selected`, so the browser shows the first, and `save()` at line 1099 posts **every**
`[data-key]` in the open group — so opening Set up → Alerts and saving anything writes `ALERT_LOCALE=en`.

**Shorter diff:** one `<option value="es">`.
**Could break:** nothing. It does not make the alert rules Spanish — that is honestly documented at
`app/settings.py:50` and stays true.
**Check:** set `ALERT_LOCALE=es`, open Set up → Alerts, save, `planetai report last` is still Spanish.

### F8 · v0.41.1's guard covers three of eighteen cards, and they are the last three drawn
`app/static/index.html:452, 533, 534, 641` · **rung 2: the shared guard is right; it is not where the cards are**

The fix was the right shape — one `card(where, fn)` helper, not a `try` per card. But:

```
$ grep -c 'data-card="' app/static/index.html        18
$ grep -n "card('#" app/static/index.html            3   (lines 533, 534, 641)
$ sed -n '516,645p' | grep -cE "\$\('#[a-z0-9-]+'\)\.(innerHTML|textContent)"   28
```

`refresh()` is still one `try` (line 517) with one `catch` (line 644) that writes "node not answering" in
the corner. Twenty-eight paint statements sit inside it unguarded: the hero, the day chart, the room and
street tiles, the trust card, the alert list, ρ, the world tiles, the place card and the whole Wall view.
The three guarded calls are `#ring-sub` and `#fc-sub` (line 533-534, before all of them) and
`#earth-empty` (line 641, after all of them). So a throw anywhere in those twenty-eight still costs every
card below it — and the satellite card, the one the release is named after, is the last one and therefore
the first casualty again.

I checked the obvious repeat: `/series` is fetched with `.catch(()=>null)` (line 518) and `drawDay(null)`
is safe (line 786 guards). So this is a live shape, not a live bug.

**Shorter diff:** wrap each `$('#x').innerHTML=` group in the existing `card('#x', ()=>{...})`. Roughly
twelve two-token edits, no new code.
**Could break:** a card that currently relies on a later statement in the same `try` running.
**Check:** in `tools/check_ui.py` — the one assert: every `data-card` id appears in a `card('#...')`
argument, or the file names which do not.

### F9 · three doctors, and the check that matters is only in the one a tester does not run
`install.sh:363-370`, `update.sh:136-143`, `bin/planetai:488-522` · **rung 2**

Three `chk()` implementations, three different lists:

| where | checks |
|---|---|
| `install.sh:363` | 4 — modules in image, db healthy, app answering, telegram set |
| `update.sh:136` | 6 — the same three, plus readings/views/packs |
| `bin/planetai:488` | 13 + 3 conditional |

`chk "all modules in image"` is byte-identical in the first two. More to the point, `bin/planetai:503`
carries this:

> `# /health answers even when every database call fails; the schema field then carries the pre-0.4 text.`
> `# Seen after a reinstall over a leftover volume: pg_isready happy, the app locked out, the install's own doctor all green.`

The fix for that went into the CLI doctor. `install.sh`'s doctor — the one every fresh tester actually sees,
and the one that was all green while the app was locked out — still has the same four checks it had then.
`install.sh:297-308` guards the *cause* on the new-password path only; a reinstall that keeps the old
password reaches the same lockout.

**Shorter diff:** `install.sh` and `update.sh` call `./bin/planetai doctor quiet` (it exists, it is in the
tarball, and `finish_setup:429` already calls it). Net about −20 lines.
**Could break:** the CLI doctor needs `envget`, `mounted` and `crontab`; on a machine mid-install some rows
go red that today are simply absent. Both callers already treat red as a warning, not a failure.
**Check:** `bash tests/test_running_state.sh` still passes, and a reinstall over a stale volume now prints
`✗ app logs in to the database` from `install.sh`.

### F10 · `POST /actions` is the only unauthenticated write, and it is the one the Index reads
`app/main.py:1260` · **not lazy enough at a trust boundary**

Every other write is gated: `/report/now` `_admin`, `/settings` `_admin`, `/test-alert` `_admin`,
`/readings` `_admin`, `/aggregates` `AGGREGATE_TOKEN`. `/actions` takes a bare dict from anyone who can
reach the port and inserts into `actions`. Its sibling's docstring argues the case for it:

> `/readings`: "Admin token required: ... anyone on the WiFi could otherwise wake the household with
> 999 µg/m³ from a curl (found on the clean node, 6 Sep 2026)."

ρ is the number this project exists to produce, `index.rho` reads `actions`, and `index.cells` publishes it
as `Governance|<scale>` at state `live` once five rows exist. `rho()` takes `min(ts) GROUP BY alert_id`, so
ρ is capped at 1.0 rather than inflatable past it — the exposure is "anyone on the WiFi can set this node's
Index cell to 1.0", plus an unbounded insert (no rate limit; `note` truncated to 500 chars, `actor` to 80).

Not one line, because the dashboard's "I did this" button (`index.html:1049`) and `planetai act`
(`bin/planetai:649`) both post without a token, deliberately — `planetai ui:946` says the open pages are
open on purpose. See §7.
**Smallest honest fix now:** reject a second `acted` row for an `alert_id` that already has one, in the
same `cur.execute` that already checks the alert exists. Caps the writes at one per alert and makes ρ
inflation visible as "every alert acted", which the report already narrates.
**Check:** two identical POSTs to `/actions`; the second returns 409 and `select count(*) from actions` is 1.

### F11 · `tolerance` is the only unbounded numeric parameter in the API, on a public endpoint
`app/main.py:846` · **rung 6**

```
$ python3 -c "<ast: every int/float Query default without ge= or le=>"
  place_geojson(tolerance: float = 2e-05)  line 846
```

That is the whole list. Every other numeric parameter — `readings.limit`, `series.hours`, `alerts.limit`,
`sparks.hours`, `forecast.hours`, `history.limit`, `aggregates.hours`, `earth_year_png.year` — carries
`ge`/`le`. `?tolerance=0` skips `ST_SimplifyPreserveTopology` entirely and returns the unsimplified
kilometre; the docstring's promise is "a kilometre is a few hundred KB".

**Shorter diff:** `tolerance: float = Query(0.00002, ge=0.000001, le=0.01)`.
**Could break:** the dashboard never passes it (`index.html:960` fetches `/place/geojson` bare).
**Check:** the AST assert above, in `make lint`.

### F12 · the heat rules are calibrated to one street in Bali and there is no knob
`packs/heat/rules.yml:22, :41` · **the hardware rule**

```sql
-- 35, not the 32 of the heat-index "extreme caution" line: in Kuta Selatan 32 is the baseline, not an event.
-- Node #1, 2-7 Sep 2026: AT was over 32 for 86% of all readings and never once fell below 28.7.
WHERE (t + 0.33 * (rh/100.0 * 6.105 * exp(17.27*t/(237.7+t))) - 4.0) >= 35
```

Honest, sourced, and hardcoded. A node in Barcelona or Boston inherits Kuta Selatan's floor, and
`presets/` ships four cities. There is no per-node override and no sensor offset anywhere in the tree:

```
$ grep -rniE "calibrat|offset|_bias" --include=*.py --include=*.yml --include=*.example . | grep -v docs/
app/sources.py:41   epa_2021_correct(pm_raw, rh)      # PM only, Plantower only, coefficients fixed
packs/insight/rules.yml:70  model_bias                # reports the bias; does not correct it
```

So the particulate path has a correction and the temperature path has none, while the project's own
`docs/USE_CASES.md` records the CAMS model "reads high" and the trust pack exists because indoor kits
disagree with each other. A kit reading 4 °C high fires 🚨 DANGER at a real 31 °C, on an `act` rule, with
`cooldown_minutes: 120`.

**Shorter diff — the plumbing is already there.** `app/main.py:87` already injects
`-c planetai.lat= -c planetai.lon=` into the session, and five rule files already read them with
`current_setting('planetai.lat')`. Add `planetai.heat_at_act` and `planetai.heat_at_danger` from settings
in that same `options=` string, and replace `>= 35` with
`>= current_setting('planetai.heat_at_act')::float`. Two lines in `db()`, one per rule.
**Could break:** a node whose database predates the setting — `current_setting` raises unless called as
`current_setting(k, true)` with a coalesce. Use the two-argument form.
**Check:** `tools/check_rules.py` already parses every rule against `init.sql`; add
`assert "heat_at_act" in open("packs/heat/rules.yml").read()` beside the existing threshold check in
`tools/check_docs.py:163`, which already asserts the README's number is the rule's number.

### F13 · the node's name and its exact coordinates leave with every outbound request
`app/main.py:474`, `app/sources.py:372`, `app/sources.py:434` · **one line each**

```python
hc = httpx.Client(timeout=60, headers={"User-Agent": f"planetai-node/{NODE}"})     # main.py:474
params={"latitude": lat, "longitude": lon, ...}                                     # sources.py:372, :434
```

`lat`/`lon` are `float(os.environ["NODE_LAT"])` — full precision, five or more decimals, which is a
doorway. `/export` already rounds to 3 (`main.py:838`) and `/place/geojson` returns the exact centre only
to a caller on the LAN. Open-Meteo's grid is ~11 km; three decimals is 110 m and changes no answer.
Both callers round independently today, i.e. not at all — this is the one place a shared coordinate helper
would earn itself, and there is no such helper (see F16).

**Shorter diff:** `f"planetai-node"` in the User-Agent (matching the seven other places in the tree that
already spell it without the name), and `round(lat, 3)` in both `params`.
**Could break:** nothing. `sensors.lat/lon` are stored from the same variables — round in `params` only,
not in the sensor row, or the model point moves off the node.
**Check:** `python3 -c "import sources;assert 'planetai-node/' not in open('app/main.py').read()"`, and
`grep -c 'round(lat, 3)' app/sources.py` → 2.

### F14 · two pack scripts make an HTTP client with no timeout
`packs/place/refresh.py:8`, `packs/place/verify.py:29` · **rung 2**

```
$ grep -rn "httpx.Client(" packs/ app/
packs/place/refresh.py:8    httpx.Client()                                   ← no timeout
packs/place/verify.py:29    httpx.Client()                                   ← no timeout
packs/forecast/fetch.py:11  httpx.Client(timeout=60)
packs/forecast/verify.py:17 httpx.Client(timeout=60, headers={...})
packs/nearby/stations.py:21 httpx.Client(timeout=60, headers={...})
packs/nearby/verify.py:52   httpx.Client(timeout=60, headers={...})
packs/nearby/backfill.py:21 httpx.Client(timeout=120, headers={...})
app/main.py:474             httpx.Client(timeout=60, headers={...})
app/main.py:731             httpx.Client(timeout=30, headers={...})
```

`httpx` defaults to five seconds for connect and no limit for read. Both no-timeout clients call Overpass,
which routinely queues a request for minutes and sometimes never answers. `planetai run place refresh`
then hangs with no output and no way to tell it from working.

**Shorter diff:** `httpx.Client(timeout=120)` in both.
**Could break:** a legitimately slow Overpass query on a large radius now raises instead of hanging;
`verify.py:30` already catches and prints `✗ 3: OpenStreetMap via Overpass: <err>`.
**Check:** `python3 -c "assert 'httpx.Client()' not in ''.join(open(f).read() for f in __import__('glob').glob('packs/*/*.py'))"` in `make lint`.

### F15 · `planetai storage set keep abc` silently stops the off-machine backup
`bin/planetai:968`, `backup.sh:52` · **error handling that prevents data loss**

```bash
keep) envset BACKUP_KEEP "$val"; say "keeping $val days of dumps";;      # no validation
```

`backup.sh:52` is `find "$DIR" -name "..." -mtime "+${KEEP}" -delete`. A non-numeric `KEEP` makes `find`
exit non-zero; `set -euo pipefail` at line 13 ends the script there — **after** the dump is written and
**before** the export, the IPFS pin, the rclone copy and `LAST_OK`. So the local dump keeps appearing, the
doctor's `a backup in the last 2 days` stays green, and the only copy that survives a house fire quietly
stops. `planetai storage` would show it (`last run OK at` disappears) if anyone looked.

**Shorter diff:** `[[ "$val" =~ ^[0-9]+$ ]] || fail "days is a whole number"` — same shape as the four
validations already in `cmd_report`.
**Could break:** nothing.
**Check:** `planetai storage set keep abc; echo $?` → non-zero, and `grep BACKUP_KEEP .env` unchanged.

### F16 · one `.env` reader, written four times, with four different semantics
`bin/planetai:110`, `update.sh:48`, `backup.sh:16`, and seven inline copies in `install.sh` · **rung 2**

```
$ grep -rn "cut -d= -f2" install.sh update.sh backup.sh bin/planetai | wc -l
10
```

Three named functions:

```bash
bin/planetai:110  envget() { ... | cut -d= -f2- | sed 's/[[:space:]]*#.*$//' | tr -d '"'"'"' '; }
update.sh:48      envval() { ... | cut -d= -f2- | sed 's/[[:space:]]*#.*$//' | tr -d '" '; }
backup.sh:16      env_get(){ ... | cut -d= -f2- | sed 's/[[:space:]]*#.*$//' | tr -d '"'"'"' ' | head -1; }
```

`install.sh` has none, and seven inline copies (`301, 310, 315, 367, 392, 395`, plus one buried in a
`bash -c` string at `bin/planetai:427`). Two of them use `cut -d= -f2`, not `-f2-`, so a value containing
`=` is truncated. Line 301 strips spaces but not quotes, so `DATA_DIR="/mnt/x"` fails the `PG_VERSION`
test at line 302 and the reinstall-over-a-volume refusal — the guard whose absence cost a tester's data —
does not fire. Line 395 strips no comment at all: `POLL_SECONDS=300  # ...` prints the comment to the
tester.

**Shorter diff:** one `envget()` in `install.sh`, identical to `bin/planetai:110`; the seven inline copies
become calls. Net about −8 lines. Leave the other three functions alone — they must each stand alone in a
tarball.
**Could break:** `install.sh:315` and `:367` compute `PORT` and are on the critical path.
**Check:** `printf 'DATA_DIR="/tmp/x"\n' >> .env` then re-run `install.sh` on a machine with a stale
volume; it must refuse.

### F17 · the same distance, nine times, five of them in SQL
`app/sources.py:65`, `app/main.py:703`, `packs/nearby/rules.yml:37,69,93`, `packs/trust/rules.yml:127`,
`packs/place/adapter.py:142`, `packs/earth/adapter.py:69`, `app/static/index.html:522,976` · **rung 4: the database does it**

```
$ grep -rn "111_320\|111320" --include=*.py --include=*.html --include=*.yml . | grep -v docs/ | wc -l
11
```

Plus three haversines (`sources.py:38` at 12742 km, `packs/forecast/adapter.py:136` the same, and
`packs/coast/adapter.py:20` at 6371 — consistent, just written twice more). `app/sources.py:61` documents
the second Python copy honestly ("core must not import from a pack"), which is a real constraint. The five
SQL copies are not covered by that argument: they are the same four-line
`sqrt(power((lat-current_setting(...))*111320,2) + power(...*cos(radians(...)),2))` pasted five times, and
a pack author writing a sixth has nothing to copy from but another pack.

**Shorter diff:** one `CREATE OR REPLACE FUNCTION planetai_metres(float,float,float,float) RETURNS float
IMMUTABLE LANGUAGE sql` in `init.sql`, and the five SQL sites shrink from four lines to one.
**Could break:** `tools/check_rules.py` parses rule SQL with sqlglot against `init.sql` — a new function
must be visible to it, and `index.run_ro` runs rules as `planetai_ro`, which needs `EXECUTE` (default for
`PUBLIC` on functions, so nothing to grant).
**Check:** `make lint` (`39 rules and cells check out against init.sql`), then
`psql -c "select round(planetai_metres(-8.8271,115.157,-8.8281,115.157))"` → `111`.

### F18 · containers run as root, all six
`app/Dockerfile`, `app/Dockerfile.reticulum`, `docker-compose.yml` · **known debt, confirmed**

```
$ docker compose config | python3 -c "<print user per service>"
agent  user=<root>   app  user=<root>   db  user=<root>
ipfs   user=<root>   mosquitto user=<root>   reticulum user=<root>
```

No `USER` in either Dockerfile, no `user:` in any service. `app` runs uvicorn as root with `./out`
writable and `./packs` mounted, and `PACKS_ALLOW_CODE=1` runs pack Python in that process's container
(`app/agent.py:241`).

**Not a one-line fix, and I am not calling it one.** `USER 1000:1000` in `app/Dockerfile` breaks the
bind-mounted `./out`, `./backups` and `./exports` unless `install.sh:324`'s `mkdir -p` also chowns, and the
`db` image drops to `postgres` itself after initdb. The honest order: `reticulum` first (its only writable
path is a named volume, so `USER 1000` there is genuinely one line and it is the container facing
strangers), then `app` with the `mkdir` change, then leave `db`, `mosquitto` and `ipfs` to their images.
**Check:** `docker compose exec reticulum id -u` → `1000`, and `planetai reticulum` still prints an address.

### F19 · nothing anywhere checks the clock
`tools/preflight.sh`, `bin/planetai:488` · **the hardware rule**

```
$ grep -niE "ntp|timedatectl|clock|time sync" tools/preflight.sh bin/planetai
(nothing)
```

The report clock is the host clock: `report._local_now()`, `due_local` as the uniqueness lock
(`main.py:351`), quiet hours, and `main.py:348`'s `if now.hour not in _report_hours() or now.minute >= 20`.
That twenty-minute window is the sharp edge — a laptop in a cupboard whose clock has drifted past it
writes no report for that hour at all, and the next one folds it in silently, so the failure looks like a
setting rather than a clock. A real clock drifts; nothing here notices.

**Shorter diff:** one doctor row, using what is already installed:
`chk "clock within 2 minutes" "..."` comparing `date +%s` to the `Date:` header of
`curl -sI https://planetai.fab.city`.
**Could break:** a node with no egress goes red; make the row skip when the existing egress check failed.
**Check:** `date -s "+10 minutes"` on a throwaway VM, then `planetai doctor` shows the row red.

The other half of that debt item is already closed: every service in `docker-compose.yml` carries
`logging: max-size 10m/5m, max-file 3/2`, `tests/test_shipped.py` asserts it ("every container log is
capped"), and all three host-side logs are bounded (`bin/planetai:44` trims at 1 MB, `install.sh:23` and
`update.sh:21` truncate per run). A doctor log-size check would find nothing. Dropped.

### F20 · `install` promises a signature it does not check
`install:4` · **rung 6, and it is a security claim**

> `# Checks the machine, downloads a signed tarball, hands off to planetai setup`

Lines 88-93 fetch `SHA256` from the same origin as the tarball over HTTPS and compare. That is an
integrity check against a truncated or swapped download, not a signature — an attacker who can serve the
tarball can serve the checksum. The code is right and careful (it refuses when neither `shasum` nor
`sha256sum` exists, which it used to skip); only the word is wrong, and it is the word a security reviewer
will quote.

**Shorter diff:** "downloads the tarball and verifies its published checksum".
**Check:** `grep -c "signed tarball" install` → 0.

### F21 · README claims v0.31 and eleven packs; the repo is v0.41.2 with thirteen
`README.md:7`, `README.md:54`, `README.md:66` · **rung 6 ×3**

```
$ git describe --tags        v0.41.2-52-g9d0ac57
README.md:7   alt="Version 0.31" ... badge/version-0.31
README.md:54  "Air, heat, coast, land, place ... and open-data packs ship"        (5 of 13)
README.md:66  "air-quality · heat · insight · trust · cold-start · open-data-health
               · coast · earth-engine · earth · place · example"                 (11 of 13)
```

`nearby` and `forecast` — the two headline packs of v0.41, three days old — are in neither list.
`tools/check_docs.py` checks 44 documents, the MCP tool count in words, size claims, pack README
thresholds and *"README's docs index must match the directory"* (line 126) — the exact same idea, applied
to `docs/` and not to `packs/`, and not to the badge.

**Shorter diff:** fix the three lines, then extend `check_docs.py:126`'s directory comparison to `packs/`,
and assert the badge matches `git describe`. Two lines in a gate that already exists for this.
**Check:** `make lint` fails when a pack folder is added without touching the README.

### F22 · `cmd_backup` is defined twice and dispatched twice
`bin/planetai:1007` and `:1127`; case arms at `:1142` and `:1150` · **rung 1**

```
$ grep -n "cmd_backup" bin/planetai
1007:cmd_backup() { step "Backup"; ./backup.sh || fail "see above"; }      ← dead
1127:cmd_backup()  { chmod +x backup.sh; ./backup.sh; }                    ← wins
1142:  update) cmd_update;;  backup) cmd_backup;;                          ← wins
1150:  backup) cmd_backup;;                                                ← dead
```

The definition that survives is the one without the `step "Backup"` header and without the `fail` wrapper,
so `planetai backup` on a failure prints `backup.sh`'s own output and exits 0 through `set -e`'s absence
of a check. The intended one is the dead one.

**Shorter diff:** keep `cmd_backup() { step "Backup"; chmod +x backup.sh; ./backup.sh || fail "see above"; }`,
delete the other definition and the duplicate case arm. −2 lines.
**Could break:** `planetai backup` now exits 1 on failure. `cmd_restore:1015` calls `./backup.sh` directly
and is unaffected; `cmd_update:1126` calls `update.sh`, which calls `./backup.sh || die`.
**Check:** `planetai backup` with the database down prints `Set-up stopped.` and exits non-zero.

### F23 · the tester's tarball carries the release script and the developer's generators
`tools/bundle.sh:13` · **rung 1**

Built it to confirm rather than reading the regex:

```
$ bash tools/bundle.sh /tmp/plbundle
/tmp/plbundle/planetai-node.tar.gz  (v0.41.2-52-g9d0ac57, 1.0M, 214 files)
$ tar tzf ... | grep -E "tools/|data/"
tools/ship.sh              ← pushes to the site repo and runs `wrangler deploy`
tools/gen_floors.py        ← writes tools/preflight.sh
tools/extract_strings.py   ← writes data/strings/en.yml
tools/render_platforms.py  ← writes docs/PLATFORMS.md
tools/hooks/pre-commit
data/platform_floors.yml   ← input to gen_floors only
data/mac_ceilings.yml      ← input to gen_floors only
data/strings/en.yml        ← output of extract_strings only
```

Nothing in the runtime reads `data/*.yml`; the floors are generated *into* `preflight.sh`, which is why
`make lint` asserts they match. `ship.sh` in a tester's folder dies at its line 22 ("no site repo"), so
this is weight and confusion rather than danger — but `make lint` and `make test` are also in the tarball
and both fail there, because `tools/check_*` and `tests/` are excluded.

**Shorter diff:** extend the one exclude regex to `tools/(package|release|bundle|ship)\.sh|tools/(gen_floors|extract_strings|render_platforms)\.py|tools/hooks/|data/`.
**Could break:** `make check-floors` and `make lint` in a tarball — already broken there.
**Check:** `tar tzf planetai-node.tar.gz | grep -c "ship.sh\|platform_floors"` → 0.

### F24 · CI runs `check_docs.py` twice
`.github/workflows/lint.yml:11-13` · **rung 1**

`make lint` ends with `python3 tools/check_docs.py`. The next step runs it again under its own name.
`check_rules.py` is deliberately re-run (sqlglot is not installed when `make lint` runs, so `make lint`
skips it and prints `- rule check skipped`); `check_docs` has no such excuse.

**Shorter diff:** delete the `docs match the code` step. −3 lines.
**Check:** the CI log has one `44 documents check out`.

### F25 · `ipfs/kubo:latest`
`docker-compose.yml:76` · **rung 6**

The only unpinned image. `postgis/postgis:16-3.4-alpine`, `eclipse-mosquitto:2` and `python:3.12-slim` are
all pinned, and the db image's pin carries a comment explaining why. An IPFS node that changes its data
directory layout on a `docker compose pull` takes the CIDs with it.

**Shorter diff:** pin the tag currently running.
**Check:** `grep -c ":latest" docker-compose.yml` → 0.

---

## The delete list

Proven dead by grep across both repositories, the dashboard JS, the MCP tool list, the install scripts and
the docs. Everything below was checked in both repos; nothing here is live in one and dead in the other.

| what | where | the grep that proved it | lines |
|---|---|---|---|
| `cmd_backup()` (first definition) | `bin/planetai:1007` | `grep -n cmd_backup bin/planetai` → two definitions, second wins | 1 |
| `backup)` case arm (second) | `bin/planetai:1150` | same grep; `case` takes the first match at 1142 | 1 |
| `docs match the code` CI step | `.github/workflows/lint.yml:12-13` | `grep -n check_docs Makefile .github/workflows/lint.yml` → already in `make lint` | 3 |
| `tools/ship.sh` from the tarball | `tools/bundle.sh:13` exclude | `tar tzf` on a built bundle; `grep -rn ship.sh docs/ README.md` → developer-only | 57 shipped |
| `tools/gen_floors.py`, `extract_strings.py`, `render_platforms.py` from the tarball | same | `grep -rn` → called only from `Makefile`'s `lint`, which cannot run in a tarball | 254 shipped |
| `tools/hooks/pre-commit` from the tarball | same | `grep -rn hooks/ install install.sh bin/planetai` → nothing installs it | — |
| `data/platform_floors.yml`, `data/mac_ceilings.yml`, `data/strings/en.yml` from the tarball | same | `grep -rn "data/platform_floors\|data/strings"` → only `tools/*.py`; `preflight.sh` carries the generated copy | 310 shipped |
| `backups */` | `.gitignore:5` | `ls -d 'backups '*` → no matches; reads as a typo for `backups*/` | 1 |
| `{app,docs}/` empty directory | working tree only | `git ls-files \| grep -c "{app,docs}"` → 0; gitignored, local litter | 0 tracked |
| `local`, `indoor`, `kind` in `/export`'s SQL | `app/main.py:822` | AST of `export()` → the dict never uses them (F6) | 0 net — **fix, do not delete** |

Repository: **~7 lines removed.** Tester tarball: **~620 lines and 8 files no longer shipped.**

Nothing else came out dead. Specifically checked and found **live**:
- Every `.env.example` key is read somewhere (`for k in $(grep -oE "^[A-Z_]+" .env.example)` → no unused).
- Every CSS class in `app/static/index.html` is referenced after `</style>` — 94 classes, 0 dead
  (the four apparent misses are `fonts.googleapis`/`gstatic` URLs and two `g250`/`g260` gradient stops
  inside the style block itself).
- All 19 MCP tools in `app/agent.py` are listed in `bin/planetai:1050` and `docs/DEVELOPING.md:52`, and
  `tools/check_docs.py:155` gates the count in words. The "17" in the prompt is from
  `docs/archive/reviews/BETA_READINESS_2026-09.md`, which records v0.30 and is correct about v0.30.
- `settings.RETIRED` is not dead: `tools/check_docs.py:43` requires the changelog and the tester guide to
  keep naming those keys, on purpose.

## `ponytail:` comments

There are none, in either repository:

```
$ grep -rin "ponytail" . ../planetai | grep -v "/.git/"
(no matches)
```

So there is no list to give a verdict on, and the two ceilings the prompt names have arrived unmarked:

- **Open-Meteo now has five call sites, not one.** `app/sources.py:370` and `:433` in the app;
  `bin/planetai:135` (`tz_for`), `:164` (geocoding) and `:211` (the `--answers` path) in the CLI. Between
  them: four different timeouts, two spellings of the User-Agent header, and no shared coordinate
  rounding anywhere (F13). The ceiling for "two short functions, one `hc.get` each" was two callers.
- **Three nodes are installing, so `install.sh`'s inline `.env` parsing has passed its ceiling.** Seven
  copies, two of which are subtly wrong (F16).

The convention would have earned its keep in four places, where a real corner is cut with a known
upgrade path and the comment currently says it in prose or not at all:

```
app/sources.py:64    # ponytail: equirectangular, ~9 m error at 8 km. haversine (km(), above) past that.
app/index.py:31      # ponytail: one latch for a missing role; per-rule state if packs ever need it.
app/static/index.html:758  # ponytail: 6 MADs, floor 5 ug/m3, tuned on one 3-station ring. A setting if a
                     #           denser ring reads differently.
packs/heat/rules.yml:22    # ponytail: 35 C AT measured in Kuta Selatan. current_setting() per node when
                     #           the second climate installs.        (F12)
```

The last one is the load-bearing case: that ceiling is reached the moment a Barcelona or Boston node
installs, and `presets/` already ships both.

## The one-liners

One commit, one message: "the small ones". Each is a single line, none touches behaviour a test asserts.

```
1  .env.example:143,146       move the inline comment above the key            (F4)
2  install.sh:310             add the /dev/urandom fallback that line 296 has
3  docker-compose.yml:95      ports: ["4242:4242", "127.0.0.1:4243:4243"]      (F5)
4  docker-compose.yml:76      pin ipfs/kubo                                    (F25)
5  app/main.py:832            move the comment to the end of the line          (F6)
6  app/main.py:846            tolerance: float = Query(2e-5, ge=1e-6, le=1e-2) (F11)
7  app/main.py:474            drop /{NODE} from the User-Agent                 (F13)
8  app/sources.py:372,434     round(lat, 3), round(lon, 3) in params           (F13)
9  app/static/index.html:1090 <option value="es">Español</option>              (F7)
10 packs/place/refresh.py:8   httpx.Client(timeout=120)                        (F14)
11 packs/place/verify.py:29   httpx.Client(timeout=120)                        (F14)
12 bin/planetai:968           validate BACKUP_KEEP is digits                   (F15)
13 bin/planetai:1007,1150     delete the dead definition and the dead arm      (F22)
14 bin/planetai:505           stop excluding '#' from the stray-space check     (F4)
15 install:4                  "verifies its published checksum", not "signed"  (F20)
16 README.md:7,54,66          the version and the two pack lists               (F21)
17 .github/workflows/lint.yml delete the duplicate check_docs step             (F24)
18 .gitignore:5               `backups*/`, or delete the line
19 ../planetai/.assetsignore  add docs/ scripts/ Makefile                      (F1)
```

Item 2 is worth its own sentence: `install.sh:296` generates `POSTGRES_PASSWORD` with
`openssl rand -hex 16 || head -c 32 /dev/urandom | od ...`, and line 310 generates `ADMIN_TOKEN` with
`openssl rand -hex 16` and no fallback. On a machine without openssl the token becomes empty. It
**fails closed** — `_admin` (`main.py:1189`) and `_mcp_auth` (`main.py:562`) both 403/401 on an empty
token, and `planetai ui` regenerates it with the fallback — so this is a lockout, not a bypass. Still one
line, and the fallback is already written eleven lines above.

Then run: `make lint && make test`, and `bash tools/bundle.sh /tmp/x` to confirm item 19's neighbours.

## `floors-are-data` before merge

**It merged before this review started** — `3e7e11c`, 9 September 10:36, +1,933/−206 across 17 files.
There is no pre-merge decision left to make. Reviewed as landed:

**What it got right, and should not be undone:** the floors are data with a vendor URL and a read date
each; `check_floors.py` goes red at 180 days so a moved floor is a failed build rather than a wasted
evening; `gen_floors.py --check` and `render_platforms.py --check` mean `preflight.sh` and
`docs/PLATFORMS.md` cannot drift from the YAML. All four gates ran green here. That is the right shape and
it is cheap.

**What it should have carried and did not:** `data/platform_floors.yml`, `data/mac_ceilings.yml` and
`data/strings/en.yml` are generator inputs and outputs, and the branch added them to the tester's tarball
without adding them to `bundle.sh`'s exclude (F23). One line, on the branch that introduced them.

**Also merged in that window and worth naming:** `install-smoke.yml` grew from 162 lines to a real
end-to-end pipe test on a clean amd64 runner. That is the single best thing in this repository's CI, and
it makes F3 stranger: the install is now tested on a clean VM and the *unit* suites still are not.

### The withdrawn hunk, since it is in the security path

For ninety minutes `bin/planetai` was `M` in the working tree — +24 lines at line 238, a `version_gap()`
that compares
`cat VERSION` to the published `VERSION` and offers `exec bash -c "$(curl -fsSL .../install)"`. Read it
because it is a network path that runs code:

- Correct: it returns early on a `.git` checkout, guards the prompt with both `-t 1` and `</dev/tty`, and
  the fetched stub verifies the tarball checksum itself, so no verification is skipped.
- No infinite loop: after a successful reinstall `VERSION` matches and the function returns 0. A failed
  download leaves `there` empty, which also returns 0.
- **One thing to change before committing:** it runs *before* `tools/preflight.sh` (line 242). A machine
  below the floor now makes a network call and is offered an upgrade to a node it cannot run, before being
  told it cannot run one — which is the exact complaint the preflight-first ordering was built to answer
  ("a tester who answers four questions and only then hears that this machine cannot run a node has spent
  his evening for nothing", `bin/planetai:239`). Move `version_gap` below the `pf` block.
- `tests/test_sudo_prompt.sh` asserts `sudo_first is called at line 135`. This hunk is in `bin/planetai`,
  not `install.sh`, so that assert still passes — but it is a line-number assert, and this is the second
  file in three days to gain lines above a fixed offset. Worth converting to a relative-order assert while
  someone is in there.

**Mergeable as it stands: yes**, with the ordering line moved. `make lint` and `make test` were green
both with the hunk applied and after it was withdrawn; the run recorded above is the clean tree.

## Looks over-engineered, isn't

- **`tools/check_docs.py`, 44 documents and a word-to-integer table for the MCP tool count.** The count
  drifted fifteen → seventeen unnoticed; the table is why it is right at nineteen now.
- **`data/platform_floors.yml` with a URL and a date on every floor, and a 180-day expiry.** A version floor
  is a fact about someone else's product. Without the date it silently becomes a lie.
- **`gen_floors.py` generating bash into `preflight.sh` instead of `preflight.sh` reading YAML.** Preflight
  runs through `curl | bash` on a machine that may have no Python; it has to be one self-contained file.
- **Three separate `.env` reader functions in three scripts** (as opposed to the seven inline copies, which
  are F16). `install.sh`, `update.sh` and `backup.sh` each have to work alone inside a tarball with no
  shared library. The duplication is the constraint, not the debt.
- **`_bearer_ok` looping over every token with no early return.** An early return leaks which token matched
  through timing. The comment says so; leave it.
- **`update.sh` copying itself to `/tmp` and re-execing.** Bash reads a script as it runs and this one
  rewrites itself. The `COPY="${BASH_SOURCE[0]}"` on line 15 is not defensive noise — the naive version
  deleted `.env` in v0.30.
- **`hb_line`'s `|| true`.** Under `set -euo pipefail` an empty log makes grep exit 1 and kills the whole
  install silently. The comment is longer than the code because the code cost an evening.
- **`agent: build: ./app` + `image: planetai-app`.** Not a second image — it names the one `app` already
  built so the agent container is a `command:` override, not a second build.
- **`sources.py` having both `km()` (haversine) and `metres()` (equirectangular).** Different jobs at
  different scales; the equirectangular one is documented as measured against haversine on node #1's own
  sensors. The nine *copies* are F17; the two *functions* are correct.
- **`index.run_ro`'s `_ro["missing"]` latch.** On a database from before v0.21 the role does not exist.
  Without the latch every rule logs the same warning every minute forever.
- **`report.py`'s `T` dict rather than gettext.** One dict per language, identical keys, one gate asserting
  all three are complete. This is what the lazy answer looks like when it is right — three languages, one
  placeholder set, no `.po` files, no build step. Do not "improve" it.

## Would need a decision

Not relitigating anything carried forward. These three need a call before code:

1. **Whether `POST /actions` stays open (F10).** Gating it means the dashboard's "I did this" button and
   `planetai act` must carry the admin token, which contradicts `planetai ui:946` — "The Display and
   Sensors pages are open to anyone who can reach the node, like the API" — and makes ρ, the household's
   own number, something only a token-holder can record. The one-per-alert cap in F10 needs no decision and
   is worth taking either way. The open question is only whether "anyone in the house can close a loop"
   is a feature. If it is, say so in the docstring next to `/readings`', which currently reads as an
   oversight rather than a choice.

2. **Whether pack thresholds may be settings (F12).** Today a threshold lives in the rule's SQL with its
   evidence in a comment beside it, and `tools/check_docs.py:163` asserts the pack README quotes the same
   number. Making it a runtime setting breaks that chain: the README can no longer state the number,
   because there isn't one. The lazy compromise is a setting that *defaults* to the number in the SQL, with
   the gate asserting the default matches the README — but that is one more place a number can live, and
   this repository has been strict about not having two. Worth ten minutes and a decision, not a patch.

3. **Whether `install.sh` and `update.sh` may depend on `bin/planetai` (F9).** Collapsing three doctors
   into one is the obvious fix, and it makes the installer depend on the CLI it is about to install. Both
   are in the same tarball and `install.sh` already calls `./bin/planetai packs` (`update.sh:154`), so the
   dependency exists in one direction already. If the answer is no, the alternative is worse: copy the
   `app logs in to the database` check into both, and accept that the next such fix lands in one of three
   places again.

## Handoff

Do these on **node #1's own machine or any Linux VM with Docker** — not on the Mac this review ran on;
`install.sh`'s Linux branches and the `sg docker` re-exec are the parts most affected below.

Order, and it matters:

**First, before touching the node repo at all: F1.** One line in `../planetai/.assetsignore`, then
`make -C ../planetai deploy`, then curl the three URLs in F1 and confirm 404. Nothing else in this list is
public.

**Second: F3.** Add `numpy duckdb` to `lint.yml`'s pip line and `- run: make test`. Push and watch it go
red — it should not, but that is the point of doing it before the fixes and not after, so every fix below
lands against a CI that actually runs the suites.

**Third: the one-liners**, all nineteen, one commit. Then `make lint && make test` and
`bash tools/bundle.sh /tmp/x`. Item 3 (port 4243) needs a live check: `planetai reticulum` on a node with
the profile on.

**Fourth, one commit each, gate after each:** F2 (reticulum env — verify with the `docker compose config`
assert in F2, not by eye), F9 (three doctors → one; run `tests/test_running_state.sh` and a real reinstall
over a stale volume), F8 (wrap the twenty-eight paints; `python3 tests/test_check_ui.py` and
`tests/test_dashboard.py`), F19 (the clock row), F17 (`planetai_metres` in `init.sql`; `make lint`'s rule
check is the gate), F18 (reticulum only).

**Do not touch:** `report.py`'s `T` dict, `_bearer_ok`'s loop, `update.sh`'s self-copy, `hb_line`'s
`|| true`, `index.run_ro`'s latch, `gen_floors.py`'s generated bash, or the two distance *functions* in
`sources.py` — all in "looks over-engineered, isn't", all load-bearing. Do not fold the three standalone
`.env` readers together; only `install.sh`'s seven inline copies. Do not start on F10 or F12 without §7.
