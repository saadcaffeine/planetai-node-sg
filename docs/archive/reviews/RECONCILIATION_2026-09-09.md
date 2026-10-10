# Reconciliation — the September reviews against HEAD

Reconciled at `4f96a38` (main, `v0.41.2-92-g4f96a38`), clean tree, 10 September 2026.

> **Update, 10 September.** The plan was blocked on the missing review. Tomas's answer was to write it
> rather than reconstruct or fabricate it, so `docs/archive/reviews/CODE_REVIEW_2026-09-10_second_pass.md` now
> exists — 28 findings at `4f96a38`, with the ten IDs this brief pinned keeping their numbers. The section
> below is left as written, because how a missing document was established still matters; the 54-row table
> is superseded and says so.

## What this document could not do, and why

The task named two reviews and 79 findings. **Only one review exists.**

`docs/archive/reviews/CODE_REVIEW_2026-09.md` is here — 25 findings, F1–F25, written at `9d0ac57`, committed as
`b075471` ("docs: code review, September 2026"). Those 25 are reconciled below, line by line.

`docs/archive/reviews/CODE_REVIEW_2026-09-09_omarchy.md` — the 54 findings A1–A15 · S1–S17 · P1–P12 · D1–D10 — is
not in this repository, in any branch, in any remote, or anywhere on this machine. Searched:

```
$ find . -iname '*omarchy*' -not -path './.git/*'                      (nothing)
$ git log --all --oneline --name-only -- 'docs/archive/reviews/*omarchy*'      (nothing)
$ git fetch --all --tags && git log --all -- 'docs/archive/reviews/*'
    e3f6e1e  docs/archive/reviews/AGENT_READY_2026-09.md
    b075471  docs/archive/reviews/CODE_REVIEW_2026-09.md
    3ed7a1a  docs/archive/reviews/INSIGHTS_DESIGN_2026-09.md
    7e4b2b9  docs/archive/reviews/BETA_READINESS_2026-09.md
$ grep -rlE "^### (A[0-9]+|S[0-9]+|P[0-9]+|D[0-9]+) ·" --include="*.md" ~/Documents   (nothing)
$ git branch -a         (11 local, 8 remote — none holds it)
$ git stash list        (empty)
```

So 54 of the 79 rows below say **UNRECONCILED · text not found**. Nothing was invented to fill them. Ten of
the 54 are partly known because the task itself describes them (A1, A2, A3, A5, A6, D2, P1, P5, S3, S8);
eight of those ten were reproduced and are recorded in full. The other 44 have no text, so they have no
file, no line, no claim and no proposed fix — there is nothing to check against HEAD.

**`docs/archive/plans/IMPROVEMENT_PLAN_2026-09.md` was not written on the 9th, for these reasons.** Its structure comes from the missing
review's §6 (the six group headings), its "do not touch" list comes from both reviews' over-engineering
sections, and 54 of the findings its PRs must close are unknown. A plan built on 44 invented findings, in a
repository whose rule is that every claim carries the line that proves it, would be worse than no plan.

One further correction to the brief: **v0.42 is not tagged.** `CHANGELOG.md:3` carries the
`## v0.42 — 2026-09-10` entry and `39a8688` wrote it, but after `git fetch --all --tags` the newest tag is
`v0.41.2` and `git tag -l 'v0.42*'` is empty. `git describe` reads `v0.41.2-92-g4f96a38`, which is also why
F21's badge check still compares against the wrong thing.

---

## Part 1 — the 79 findings at HEAD

### The 25 that exist: F1–F25

`git diff --stat b075471..HEAD` touches 34 files. It does **not** touch `app/main.py`, `docker-compose.yml`,
`app/static/index.html`, `app/sources.py`, `init.sql`, `packs/`, `tools/bundle.sh`, `backup.sh` or
`.github/workflows/lint.yml` — which is most of this table in one line.

| id | status | proof at HEAD | fixed in |
|---|---|---|---|
| F1 | **OPEN** · confirmed live | `../planetai/.assetsignore` still lists only `src/ functions/ wrangler.toml .assetsignore .git/ .gitignore *.sh README.md archive/`. Curled just now: `200 Makefile`, `200 docs/morning_review_punch_list.md`, `200 scripts/check_html.py`, `404 wrangler.toml`, `404 robots.txt` | — |
| F2 | **OPEN** | `docker-compose.yml:91` `env_file: .env` on `reticulum`, unchanged; `environment:` still holds only `NODE_API_URL` and `RETICULUM_CONFIGDIR` | — |
| F3 | **OPEN, worse** | `.github/workflows/lint.yml:29-32` still ends at `PYTHONPATH=/tmp/stub:app python3 tests/test_sources.py`; pip line is still `pip install pyyaml` (line 10). `make test` grew from 21 suites to **26** (`Makefile:30`, +5: `test_release_consistency`, `test_ship_gate`, `test_daemon_state`, `test_diagnose`, `test_ladder`). CI runs 1 of 26 | — |
| F4 | **PARTIAL — content fixed, gate absent** | Content: `0f4bba2` moved both comments above the key and added the explanation at `.env.example:150-152`. `python3 -c "re.search(r'^[A-Z_]+=[ \t]+#', ...)"` → no hits. **Gate: no.** `bin/planetai:541` still reads `'^[A-Z_]+=[[:space:]]+[^[:space:]#]'` — `#` is still excluded, which is the exclusion that permitted F4 — and it tests `.env`, never `.env.example`. Nothing in `make lint` reads `.env.example` for this | `0f4bba2` (content only) |
| F5 | **OPEN, MOVED** | `docker-compose.yml:95` still `ports: ["4242:4242"]`; `4243` published nowhere. Callers moved: `bin/planetai:821` (the 30-poll wait) and `bin/planetai:554` (the doctor row), was `:785`/`:518` | — |
| F6 | **OPEN** | `app/main.py:832` unchanged. AST of `export()`: `keys: ['t','sensor','metric','mean','min','max','n']`. The SQL at `:822` still selects `s.local, s.indoor, s.kind` | — |
| F7 | **OPEN** | `app/static/index.html:1090` still offers `en` and `id` only; `es` absent | — |
| F8 | **OPEN** | `grep -c 'data-card="'` → **18**; `grep -c "card('#"` → **3**, at lines 533, 534, 641. `refresh()` still one `try` at `:516` with one `catch` at `:644` | — |
| F9 | **OPEN, MOVED** | Three `chk()` still: `install.sh:496` (4 calls), `update.sh:136` (6), `bin/planetai:524` (16). Was `install.sh:363`/`bin/planetai:488` | — |
| F10 | **OPEN** → **RESERVED · prompt A** | `app/main.py:1260` `@app.post("/actions")`, `def action(body: dict)` — no `authorization` parameter, no `_admin`, no one-per-alert cap. Prompt A owns this route | — |
| F11 | **OPEN** → **RESERVED · prompt A** | `app/main.py:846` `def place_geojson(kinds: str = ..., tolerance: float = 0.00002)` — still the only numeric parameter with no `ge`/`le`. Prompt A owns `GET /place/geojson`, and the fix is that same signature line, so it must not be edited twice | — |
| F12 | **OPEN, MOVED** | `packs/heat/rules.yml:21` `... >= 35` (was `:22`), second threshold `>= 40` at `:41`. `grep heat_at_act` → nothing, in the rules or in `tools/check_docs.py` | — |
| F13 | **OPEN** | `app/main.py:474` `headers={"User-Agent": f"planetai-node/{NODE}"}`; `app/sources.py:372` and `:434` still `params={"latitude": lat, "longitude": lon, ...}`, no `round()` | — |
| F14 | **OPEN** | `packs/place/refresh.py:8` and `packs/place/verify.py:29` still `httpx.Client()`. The other seven call sites all carry a timeout | — |
| F15 | **OPEN, MOVED** | `bin/planetai:1004` `keep) envset BACKUP_KEEP "$val"; say ...` — no validation (was `:968`). `backup.sh:52` `find ... -mtime "+${KEEP}" -delete` unchanged | — |
| F16 | **OPEN, MOVED** | `grep -c "cut -d= -f2"` across the four scripts → **10**, unchanged. Three named readers (`bin/planetai:111`, `update.sh:48`, `backup.sh:16`) plus six inline in `install.sh` (`430, 443, 448, 500, 525, 528`) and one in a `bash -c` at `bin/planetai:463`. `install.sh:430` still uses `-f2` not `-f2-` and strips spaces but not quotes — the `DATA_DIR="/mnt/x"` case the finding names. `install.sh:528` still strips no comment | — |
| F17 | **OPEN, worse** | `grep -rn "111_320\|111320"` (py/html/yml, minus `docs/`) → **20 lines across 10 files**, up from 11. `grep -rn planetai_metres` → nothing in `init.sql`. New site since the review: `packs/place/satellite.py:54-55` | — |
| F18 | **OPEN** | `grep -n "^USER\|user:" app/Dockerfile app/Dockerfile.reticulum docker-compose.yml` → nothing | — |
| F19 | **OPEN** | `grep -niE "ntp\|timedatectl\|clock\|time sync" tools/preflight.sh bin/planetai` → nothing | — |
| F20 | **OPEN** | `install:4` still reads "downloads a signed tarball"; `grep -c "signed tarball" install` → 1 | — |
| F21 | **OPEN, worse** | `README.md:7` `alt="Version 0.31"`, `badge/version-0.31`; `git describe` → `v0.41.2-92-g4f96a38` and the CHANGELOG says v0.42. `README.md:54` names 5 packs, `README.md:100` names 11; `ls -d packs/*/` → **13**. `tools/check_docs.py` gained three gates in `cc5970d`/`845a0b2` (skill frontmatter, AGENTS.md routing, llms.txt links) and **not** this one: `:109` still only checks that a pack a doc names exists, never that the README names every pack, and nothing checks the badge | — |
| F22 | **OPEN, MOVED** | `grep -n cmd_backup bin/planetai` → definitions at `:1043` and `:1304`, case arms at `:1319` and `:1327`. The second definition still wins and still lacks `step` and `fail` (was `:1007`/`:1127`, arms `:1142`/`:1150`) | — |
| F23 | **OPEN** | `tools/bundle.sh:13` exclude is `^(\.github/\|tools/(package\|release\|bundle)\.sh\|tools/check_\|tests/\|docs/design/audit/)` — `tools/ship.sh`, `gen_floors.py`, `extract_strings.py`, `render_platforms.py`, `tools/hooks/` and `data/` are all still shipped | — |
| F24 | **OPEN** | `.github/workflows/lint.yml:12-13` `- name: docs match the code / run: python3 tools/check_docs.py`, still after `make lint` which ends in the same script | — |
| F25 | **OPEN** | `docker-compose.yml:76` `image: ipfs/kubo:latest`; `grep -c ":latest"` → 1 | — |

**24 open, 1 partial, 0 closed with a gate.** Two of the 24 (F10, F11) are RESERVED for prompt A and must
get no PR here.

One aside from the first review's §5 **did** land, and it is the only fix in the set that came with its
gate: `tests/test_sudo_prompt.sh` no longer asserts a line number. It walks the file tracking whether
`sudo_first` has run and asserts every executed `sudo` appears after it (`tests/test_sudo_prompt.sh:24-26,
58-65`). That is the shape the review asked for.

### The 54 that do not exist: A1–A15 · S1–S17 · P1–P12 · D1–D10

**Superseded by a second pass, 10 September.** Tomas's instruction on reading the above was to write the
missing review rather than reconstruct it or fabricate it. That review is
`docs/archive/reviews/CODE_REVIEW_2026-09-10_second_pass.md`, written against `4f96a38` — this commit — so every
finding in it is by definition open, and there is nothing to reconcile. It carries **28** findings, not 54:
the ten IDs this brief pinned by content keep their numbers and their claims, eighteen were found in this
pass, and nothing was added to reach a number.

| ids | status |
|---|---|
| A1, A2, A3, A5, D2, P1, S3, S8 | **CONFIRMED** — pinned by the brief, reproduced on `pai-clean` before the second pass was written; transcripts below. Three of the eight behave worse than the brief's one-line summary describes, and the second pass says how |
| A6, P5 | **pinned, carried** — A6 is the LXMF inbox: real at HEAD (`docker-compose.yml:91`, `:95`), and its fix is F2+F5, so it gets no separate PR. P5 is nearby's `baliairdispatch`: half-answered at HEAD (its three parameters are already runtime settings), and the second pass records it as a design question with a named trigger rather than a defect |
| A4, A7–A12 | **new in the second pass** (7) — A4 the float-cast class behind A1/A3; A7 `/sensors` publishes the household's device hostnames (RESERVED · prompt A); A8 one word in a `cells.yml` 500s `/cells` and `/export`; A9 three rows claim one cell key; A10 ρ's median is a different population from its numerator; A11 the broker has no ACL; A12 `/health`'s coordinates (RESERVED · prompt A) |
| S1, S2, S4–S7, S9, S10 | **new in the second pass** (8) — S1 `version_gap` before the preflight; S2 four unannounced sudos the test cannot see; S4 `planetai storage` prints the backup token; S5 two unvalidated `storage set` arms; S6 no update lock; S7 no whole-run transcript; S9 no `planetai support`; S10 `make test` is one `&&` chain |
| P2, P3 | **new / cross-referenced** — P2 two shipped packs define two cells with one key (confirmed live); P3 defers to F12 |
| D1, D3, D4 | **new / cross-referenced** — D1 defers to F8; D3 Reset does not reset (confirmed in a browser); D4 the admin token in `localStorage`, with the XSS hunt that found no execution recorded as carefully as a finding |
| A13–A15, S11–S17, P4, P6–P12, D5–D10 | **not used.** The brief's ID ranges implied 54 findings. There are 28. These numbers name nothing rather than something invented |

---

## The eight reproductions

Run on `pai-clean` (Lima, Ubuntu 24.04.4, aarch64, 4 vCPU, Docker 29.8.0), with HEAD's working tree rsynced
over the VM's node folder (`.env`, `data/`, `backups/` preserved), `docker compose up -d --build`, and
`init.sql` reapplied. Node `lima-fresh`, 6210 readings, db healthy. `VERSION` stamped `v0.42-HEAD-4f96a38`.

`make lint` on the dev Mac at HEAD: **LINT_EXIT=0** (see Part 4 item 2 — it exited 0 with one gate not run).

---

### A1 · QUIET_FROM=22:00 → **CONFIRMED**, and the finding's own instruction understates it

`PUT /settings` accepts `"22:00"` with no validation. `app/main.py:292` is
`_hours(key, default) -> [int(x) for x in (...).split(",") if x.strip().isdigit()]`; `"22:00".isdigit()` is
false, so the list is empty, and `app/main.py:301` indexes `[0]`.

```
$ curl -s -X PUT localhost:8080/settings -H "Authorization: Bearer $TOK" \
       -H 'content-type: application/json' -d '{"QUIET_FROM":"22:00"}'
{"changed":["QUIET_FROM"],"by":"gui","effective_within_s":20}

$ # a local sensor silent for 3 h, so rule sensor_silent (level warn) can fire
$ curl -s -X POST localhost:8080/readings ... --data @a1b.json
{"accepted":1}

$ # status.errors and the alert count, every 5 s
  5s  errors={}                                              alerts=5
 10s  errors={}                                              alerts=5
 15s  errors={"run_rules": "list index out of range"}         alerts=6
 20s  errors={"run_rules": "list index out of range"}         alerts=6
 ...
 65s  errors={"run_rules": "list index out of range"}         alerts=6
 70s  errors={}                                              alerts=6
 ...
210s  errors={}                                              alerts=6

$ planetai logs app
app-1  | run_rules failed: list index out of range
app-1  | Traceback (most recent call last):
app-1  |   File "/app/main.py", line 405, in run_rules
app-1  | IndexError: list index out of range
```

`main.py:405` is `send = floor.get(level,0) >= floor.get(...) and not _quiet(level)`.

Three things the run adds:

1. **The alert row survives; the notification does not.** `db()` is `autocommit=True` (`app/main.py:86`), so
   the `INSERT INTO alerts` at `:400` has already committed when `_quiet` raises at `:405`. Alerts go 5 → 6.
   `notify()` at `:410` and `ha_alert()` at `:411` never run — no Telegram, no mesh, no LXMF, no Home
   Assistant. The dashboard shows the alert; nobody is told.
2. **`status.errors` self-erases.** It holds the error for exactly one 60-second turn (15 s → 65 s) and is
   empty from 70 s on, because the rule's own `cooldown_minutes` means the next turn returns no rows and
   never reaches `_quiet`. `loop()`'s `state["errors"].pop(name, None)` on a clean turn (`main.py:465`) does
   the erasing. So the task's instruction "read `status.errors`" gives the wrong answer nine times out of
   ten: the durable evidence is one log line.
3. `/health.ok` stays `true` and `last_error` stays `null` throughout.

Blast radius is bounded and worth stating: `_hours` has exactly two callers, both on line 301
(`QUIET_FROM`, `QUIET_TO`). `_report_hours` uses `settings.num`, which is safe.

**The fix already exists beside it.** `app/settings.py:64-66`:
`num(key, default) -> int(v) if v.isdigit() else default`. `_quiet` should call
`settings.num("QUIET_FROM", 22)` and `settings.num("QUIET_TO", 6)` and `_hours` should lose its only two
callers.

---

### A2 · a pack rule with no `message:` → **CONFIRMED**. /alerts does not grow. Ever.

```
$ mkdir -p packs/x && cat > packs/x/rules.yml <<'YML'
- id: no_message
  level: info
  cooldown_minutes: 1
  sql: >-
    SELECT 'node' AS sensor_id, 1 AS n
YML
$ # pack.yaml written, PACKS_ENABLED set to "x", planetai restart

$ curl -s localhost:8080/packs
[{"name":"x","version":0.1,"description":"a pack whose rule forgot its message","id":"x",
  "path":"/app/packs/x","kind":"data"}]

 25s  errors={"run_rules": "'message'"}  alerts=6
 50s  errors={"run_rules": "'message'"}  alerts=6
 75s  errors={"run_rules": "'message'"}  alerts=6
100s  errors={"run_rules": "'message'"}  alerts=6
125s  errors={"run_rules": "'message'"}  alerts=6
150s  errors={"run_rules": "'message'"}  alerts=6

app-1  | Traceback (most recent call last):
app-1  | KeyError: 'message'
app-1  | run_rules failed: 'message'
app-1  | Traceback (most recent call last):
app-1  | KeyError: 'message'
```

`app/main.py:393` is `msg = rule["message"]` — a subscript, inside the `for row in rows:` loop, outside the
only `try` in that function (`:380-384`, which wraps `index.run_ro` alone). The `KeyError` leaves
`run_rules` entirely.

Unlike A1 this never clears: the rule returns a row on every turn, so every turn dies at the same line.
Six turns of the 60-second loop, and the alert count is frozen at 6. **Every rule in the node is dead** —
`config/rules.yml`'s two and all thirteen packs' — for as long as one data file sits in `packs/`.

`app/packs.py:4` calls `rules.yml` "DATA — no code, safe to merge from anyone". It is the one file the
project invites strangers to contribute, and one missing key in it silently stops every alert on the node.

**The gate for this already exists and did not help.** `tools/check_rules.py:101`:

```
errs.append(f"{where}: no message and no `contributes:` — this rule can fire and reach nobody")
```

That is a build-time gate on the repository. A pack folder dropped onto a running node never passes through
`make lint`. The guard has to be at runtime — `rule.get("message")` and `continue`, or a filter in
`packs.alerts()`, which is already the function whose docstring (`app/packs.py:83-85`) describes this exact
failure: *"sending a rule with no message once printed the raw template, braces and all."*

---

### A3 · LOCAL_RADIUS_M=500m → **CONFIRMED**. Every source stops.

`POLL_SECONDS` was lowered from 300 to 45 for the duration so three minutes shows four polls. That is the
only deviation from the specified run.

```
$ # baseline, valid radius
  polls=1 last_poll=2026-09-10T09:14:01.998162+00:00 errors={}
  polls=2 last_poll=2026-09-10T09:14:48.789011+00:00 errors={}

$ curl -s -X PUT localhost:8080/settings ... -d '{"LOCAL_RADIUS_M":"500m"}'
{"changed":["LOCAL_RADIUS_M"],"by":"gui","effective_within_s":20}

  30s  polls=3 last_poll=2026-09-10T09:15:35.624340+00:00 errors={}
  60s  polls=3 last_poll=2026-09-10T09:15:35.624340+00:00 errors={"poll_sources": "could not convert string to float: '500m'"}
  90s  polls=3 last_poll=2026-09-10T09:15:35.624340+00:00 errors={"poll_sources": "could not convert string to float: '500m'"}
 120s  polls=3 last_poll=2026-09-10T09:15:35.624340+00:00 errors={"poll_sources": "could not convert string to float: '500m'"}
 150s  polls=3 last_poll=2026-09-10T09:15:35.624340+00:00 errors={"poll_sources": "could not convert string to float: '500m'"}
 180s  polls=3 last_poll=2026-09-10T09:15:35.624340+00:00 errors={"poll_sources": "could not convert string to float: '500m'"}
 210s  polls=3 last_poll=2026-09-10T09:15:35.624340+00:00 errors={"poll_sources": "could not convert string to float: '500m'"}

app-1  | ValueError: could not convert string to float: '500m'
app-1  | poll_sources failed: could not convert string to float: '500m'
```

`polls` and `last_poll` frozen for 210 s. `app/main.py:103` is
`float(settings.get("LOCAL_RADIUS_M") or 500)` inside `poll_once`, **outside** the per-source
`try/except` at `:95-100` — which catches only `fn()`. So it is not one source failing, it is the loop. The
identical line is at `app/main.py:133` in `_store`, so MQTT ingest dies the same way.

`LOCAL_RADIUS_M` is in `settings.PUBLIC` (`app/settings.py:82`) and not in `settings.CHOICES`, so it is free
text by design — and `app/settings.py:36` labels the field "Local radius, m", which is what invites "500m".

Unlike A1 this does not self-clear. Same fix, same helper: `settings.num("LOCAL_RADIUS_M", 500)`.

---

### A5 · AIRGRADIENT_HOSTS → **CONFIRMED**. The adapter is dead code and the settings page sells it.

```
$ curl -s -X PUT localhost:8080/settings ... -d '{"AIRGRADIENT_HOSTS":"airgradient_84fce6.local"}'
{"changed":["AIRGRADIENT_HOSTS"],"by":"gui","effective_within_s":20}

$ docker compose exec app python3 -c "import httpx,sources; print([n for n,_ in sources.enabled(httpx.Client(timeout=5))])"
['open-meteo', 'open-meteo-cams']

$ curl -s localhost:8080/sensors    # after the setting took effect and a poll ran
sensor_ids: ['cams-point', 'power-point', 'om-point']
ag-* rows: []

$ grep -rn "airgradient(" app/ packs/
app/sources.py:264:def airgradient(hc: httpx.Client, hosts: list[str], lat: float | None, lon: float | None, indoor: bool):
```

`sources.enabled()` (`app/sources.py:320-357`) never appends an `("airgradient", ...)` entry. The only two
places `AIRGRADIENT_HOSTS` is read are `app/sources.py:340` and `app/main.py:738`, and both use it to build
a **skip** set — the station ids to exclude from `baliairdispatch`. So the setting's only effect is to hide
a station from a source that is itself off by default (`BAD_ENABLED=0`).

`sources.airgradient` is a complete 40-line adapter called from exactly one place in the tree:
`tests/test_sources.py:51`. Meanwhile `app/settings.py:28` offers the field to the household as
*"AirGradient hosts — Hostnames or IPs on your WiFi, comma-separated. Read directly, no cloud."*

Somebody who owns an AirGradient types its hostname into the dashboard, saves, and waits. Nothing appears
in `/sensors`, nothing appears in `status.errors`, and nothing appears in the log — because nothing was
ever asked to run.

---

### S3 · a truncated tarball through update.sh → **CONFIRMED**, and it prints "Nothing was lost."

**Deviation:** run on `pai-clean`, not `pai-clean6`. `pai-clean6` has no installed node (no `VERSION`) and
its Docker daemon is down; `update.sh` needs `./backup.sh` and a `docker compose exec db psql` to succeed
before it reaches the download. `pai-clean` is the only VM with the shape this path requires — `VERSION`
present, no `.git`. Nothing in the node folder was overwritten by either variant (verified after each).

A local site on `127.0.0.1:8099` served `/node0/get/planetai-node.tar.gz` truncated to 100 bytes.

**Variant A — the SHA256 file is published (the true checksum of the untruncated build): fails closed,
correctly.**

```
$ PLANETAI_SITE=http://127.0.0.1:8099/node0 ./update.sh
>> backing up the database first
17:29 backup: ./backups/lima-fresh-2026-09-10.sql.gz (36K)
>> current schema: 0.23
>> updating from http://127.0.0.1:8099/node0
xx the download does not match its published checksum. Try again; if it repeats, tell us.
exit=1
```

**Variant B — the SHA256 file is unreachable (404). Same 100-byte tarball.**

```
$ curl -o /dev/null -w '%{http_code}' .../get/SHA256                 404
$ curl -o /dev/null -w '%{http_code} %{size_download}' .../get/planetai-node.tar.gz    200 100

$ PLANETAI_SITE=http://127.0.0.1:8099/node0 ./update.sh </dev/null; echo "EXIT=$?"
   ...
   doctor:
     ✓ all modules in image
     ✓ db healthy
     ✓ app answering
     ✓ readings intact
     ✓ views rebuilt
     ✓ packs loaded
   >> schema 0.23 → 0.23
   >> updated. Nothing was lost: 6216 readings, 7 alerts, 8 actions.
EXIT=0

$ cat VERSION          v0.42-HEAD-4f96a38      # unchanged. No new code was installed.
```

**Exit 0, six green doctor rows, and the last line the operator reads is "updated. Nothing was lost."** No
new code arrived. `update.sh:80`:

```bash
if command -v shasum >/dev/null && curl -fsSL "${SITE}/get/SHA256" -o "$tmp/sha" 2>/dev/null; then
  want=...; got=...; [[ "$want" == "$got" ]] || die "the download does not match its published checksum..."
fi
tar xzf "$tmp/n.tar.gz" -C "$tmp" && ( cd "$tmp/planetai-node" && tar cf - . ) | tar xf - --exclude=.env
say "now $(cat VERSION 2>/dev/null || echo '?')"
```

Two silent fail-open conditions, both `2>/dev/null`:
- `shasum` absent (it is macOS's name; Debian's is `sha256sum`) → the `if` is false, no check;
- the SHA256 fetch fails for any reason → the `if` is false, no check.

Then `tar xzf` fails as the **left** operand of `&&`, which `set -e` exempts, and the script continues to
the schema step, the rebuild, the doctor and the closing sentence.

The comment on `update.sh:79` says *"the same check the installer makes"*. It is not. `install:87-92`:

```bash
# The checksum is not optional. This used to skip silently when `shasum` was missing (it is macOS's name;
# Debian ships `sha256sum`), so on some machines the tarball was simply trusted. It is the only path now.
local sum=""; command -v shasum >/dev/null && sum="shasum -a 256"; [[ -n "$sum" ]] || { command -v sha256sum >/dev/null && sum="sha256sum"; }
[[ -n "$sum" ]] || { rm -rf "$tmp"; die "no shasum or sha256sum on this machine, so the download cannot be verified. ..."; }
curl -fsSL "${SITE}/get/SHA256" -o "$tmp/sha" || { rm -rf "$tmp"; die "could not fetch ${SITE}/get/SHA256, so the download cannot be verified."; }
[[ "$want" == "$got" ]] || { rm -rf "$tmp"; die "the download does not match its published checksum. ..."; }
```

`install` fails closed on all three, and its comment records that it once did not. The whole fix for
`update.sh` is those five lines, already written, eleven files away. Node #2 is `update.sh`'s first run on a
machine nobody here can see; this is the finding that decides when Lucas may type `planetai update`.

---

### S8 · `planetai setup` on a running node → **CONFIRMED**, conditionally. It exits 1 before the menu.

```
$ docker compose ps -q | wc -l          2        # the node is up and answering /health
$ timeout 60 script -qefc "./bin/planetai setup" /tmp/s8.log </dev/null; echo "exit=$?"
exit=1
```

Transcript, ANSI stripped:

```
◍ this folder holds v0.42-HEAD-4f96a38. The published version is v0.41.2-92-g4f96a38.
  What runs here is what is in this folder, so a fix released after you downloaded it is not in it.
  One line replaces the code and keeps your settings, your data and your answers:

    curl -fsSL planetai.fab.city/install | bash

  Do that now? [Y/n]
  ...
  node · observe here, decide here, act here

preflight  no questions, no changes, nothing installed

  os            Ubuntu 24.04.4 LTS                           ✓
  arch          arm64                                        ✗
                the node's database image (postgis/postgis:16-3.4-alpine) is
                published for linux/amd64 only. Not a Raspberry Pi yet: docs/PLATFORMS.md
  memory        3 GB                                         ✗
                4 GB is the container runtime's own minimum; this machine has 3 GB
  disk free     12 GB on /                                   ✓
  runtime       docker, running                              ✓
  writable      yes                                          ✓
  python3       present                                      ✓
  egress        site, github, registry, open-meteo           ✓
  ports         8080, 5432 free                              ✓

  2 checks failed. Each line above carries the fix. Nothing was installed.
```

It never reaches the Update / Reconfigure / Nothing / Remove menu at `bin/planetai:309-322`. `cmd_setup`
runs `version_gap` (`:261`), then the preflight block (`:267-272`), whose last line is
`[[ $pf -eq 0 ]] || exit 1`. The menu is three sections further down and unreachable.

**State the condition honestly:** on a machine that passes preflight the menu does appear — the branch at
`:309` is `elif [[ -f .env ]] && [[ -n "$(envget NODE_NAME)" ]]`, and `node_running` (`:281`) correctly
skips the "did not finish" path. What is confirmed is narrower and still serious: **`planetai setup` gates a
post-install menu behind the install-time floors**, so on any machine below them — arm64, under 4 GB, the
revive-a-laptop cases `docs/REVIVE_A_LAPTOP.md` is written for — a node that has been running for days can
never be updated, reconfigured or removed through the one command a tester is told to type. This VM has
been running that node for three days with 6,210 readings in it.

Note also that the preflight rows are true, not stale: the db image really is amd64-only
(`docker image inspect postgis/postgis:16-3.4-alpine --format '{{.Os}}/{{.Architecture}}'` →
`linux/amd64`, and `docker compose exec db uname -m` → `x86_64` under emulation). It works, healthily, and
has served 6,210 readings. The floor is a fair warning about an install; it is not a verdict on a node.

---

### P1 · place_around with `nearest_health_m` absent → **CONFIRMED**. The household is sent the template.

```
$ docker compose exec db psql -U planetai planetai -tAc \
    "SELECT count(*) FROM observations WHERE sensor_id='place-point'"
0

$ # the exact scalar subquery from packs/place/rules.yml:14
$ docker compose exec db psql -U planetai planetai -c \
    "SELECT round((SELECT value FROM observations WHERE sensor_id='place-point' AND metric='nearest_health_m')) AS clinic_m"
 clinic_m
----------

(1 row)

$ # format the shipped template the way app/main.py:396-398 does
format raised: ValueError : Unknown format code 'f' for object of type 'str'
--- the alert text the household receives ---
🏘️ What is around you, this month.

About {buildings:.0f} buildings within a kilometre, {commercial_pct:.0f}% of them shops, offices or
hotels. On the map: {food:.0f} places to eat, {schools:.0f} schools, {health:.0f} clinics or pharmacies,
the nearest health care {clinic_m:.0f} m away. A zero here often means nobody h...
```

The chain, all in `app/main.py:396-398`:

```python
try:
    text = tmpl.format(**{k: ("—" if v is None else v) for k, v in row.items()})
except (KeyError, ValueError, TypeError):
    text = tmpl
```

`round(NULL)` is NULL → the sentinel makes it the **string** `"—"` → `{clinic_m:.0f}` on a str raises
`ValueError` → the `except` substitutes the raw template. One unmapped clinic in OpenStreetMap turns the
monthly place report into its own source code.

**This is a class, not a rule.** The `"—"` sentinel is incompatible with every `{x:.Nf}` in every message,
and the fallback is silent — no log line, no `status.errors` row, just a strange alert. A scan of every
shipped rule for a `:.Nf` slot fed by a nullable scalar subquery or aggregate:

```
packs/place/rules.yml  place_around: ['buildings', 'clinic_m', 'food', 'health', 'schools']
risky format slots: 5
```

Five today, all in one rule, and any new rule inherits it. `tools/check_rules.py:105` already checks that a
placeholder appears in the SQL's output columns — which passes here, because it does. A lint cannot see a
NULL. The shorter diff is at the sentinel: strip the format spec for the keys whose value is None before
formatting, in that one place, so all callers are fixed at once.

---

### D2 · "I did this", then Cancel → **CONFIRMED**. ρ goes from 0 to 1 on a cancelled dialog.

Driven in a real browser against the node (Lima forwards 8080 to the Mac's loopback), with `window.prompt`
replaced by a function returning `null` — which is exactly what the browser returns when the user presses
Cancel.

```js
const before = await (await fetch('/rho')).json();
window.prompt = function(){ promptCalls++; return null; };   // Cancel
document.querySelector('button.act').click();                // "I did this"
const after  = await (await fetch('/rho')).json();
```

```
buttonFound : true
promptCalls : 1
before      : { alerts_act: 1, acted: 0, rho: 0,    median_minutes: null }
after       : { alerts_act: 1, acted: 1, rho: 1,    median_minutes: 0 }
```

`app/static/index.html:1049`:

```js
async function act(id){const note=prompt('What did you do? A few words is enough.','')||'acted';
  const r=await fetch('/actions',{method:'POST',...,body:JSON.stringify({alert_id:id,stage:'acted',actor:'gui',note})});
```

`prompt()` returns `null` on Cancel. `null || 'acted'` is `'acted'`, so the `fetch` runs regardless. An
empty submit does the same thing.

ρ is the one number this project exists to produce, `index.rho` reads `actions`, and `index.cells`
publishes it as `Governance|<scale>` at state **`live`** once five rows exist. A dialog the household
dismissed becomes a published claim that the loop was closed. The fix is `if(note===null)return;` —
one clause, before the fetch.

`POST /actions` is also the route F10 names and prompt A owns; the one-line JS guard is in
`app/static/index.html` and does not touch it.

---

## Part 4 — what else turned up

Three, with the run or the read that proves each.

### 1 · `version_gap` still runs before the preflight, which the September review told them to fix before committing

`bin/planetai:261` is `version_gap`; the preflight block is `bin/planetai:267-272`. The first review read
this hunk while it was uncommitted (`docs/archive/reviews/CODE_REVIEW_2026-09.md`, §"The withdrawn hunk") and left
one instruction:

> **One thing to change before committing:** it runs *before* `tools/preflight.sh` (line 242). A machine
> below the floor now makes a network call and is offered an upgrade to a node it cannot run, before being
> told it cannot run one … Move `version_gap` below the `pf` block.

It landed above it. The S8 transcript is the proof in operation: the network fetch and the
`curl … | bash` offer print first, and only then does preflight say this machine has the wrong
architecture and not enough memory.

```
$ grep -n "version_gap$" bin/planetai      261:  version_gap
$ grep -n "preflight.sh" bin/planetai      268:    local pf=0; bash tools/preflight.sh || pf=$?
```

Shorter diff: move line 261 to just after the `fi` on line 272. One line, no new code, and it also removes
one of the two reasons `planetai setup` misbehaves on a running node (S8).

### 2 · `make lint` exited 0 with a gate that did not run

At HEAD on the dev Mac:

```
$ make lint; echo "LINT_EXIT=$?"
  ...
  50 documents check out
  GUI: script parses; every id, endpoint, field and asset resolves; ...
  - requirements resolve skipped (venv failed)
  ...
  39 rules and cells check out against init.sql
  app imports, 44 routes
ok
LINT_EXIT=0
```

`- requirements resolve skipped (venv failed)` is one warning line among twelve success lines, and the
build is green. `make test` has the mirror problem in the other direction: `Makefile:30` is a single
`&&` chain of 25 suites, so the first failure hides the remaining 24, and nothing counts what ran, what
failed or what skipped. Six suites print their own "skipped" lines that no one tallies.

This is not a style complaint — it is the reason F3 has stayed open through five releases and the reason
the review's "finding zero" said a green local gate is not a green build. It is also exactly what the
`tests/all` runner the brief mandates is for: keep going, count failures **and skips**, and make a skip
visible as a skip rather than as an `ok`.

### 3 · `GET /health` returns the node's name and its exact coordinates, unauthenticated — **RESERVED · prompt A**

```
$ curl -s localhost:8080/health          # no Authorization header
{"ok":true,"node":"lima-fresh","version":"...","schema":"0.23","uptime_s":13,
 "lat":41.3874,"lon":2.1686,"city":"bali",...,
 "cell":{"id":"8839446033fffff","res":8,"edge_m":525,"caption":"... THE CELL THIS NODE STANDS IN"}}
```

Full-precision `lat`/`lon` (four decimals here, five or more on a real node), the node's name, and the H3
cell id, on the one route everything polls. `/export` already rounds to 3 (`app/main.py:838`) and F13 makes
the same argument about outbound requests. Listed here because the brief reserves `/health`'s coordinates
for prompt A; no PR should be written for it outside that session.

Checked and **not** a leak, so prompt A need not look at it: unauthenticated `GET /settings` honours the
`PUBLIC` allowlist. 47 rows returned, 28 with a visible value, every one of them in
`settings.PUBLIC` (`app/settings.py:79-83`); `AIRGRADIENT_HOSTS`, `EE_KEY_FILE`, `AGENT_REMOTE_URL`,
`AGENT_ONLINE_URL`, `MESH_GATEWAY_NODE_NUM` and `BACKUP_TOKEN` all read `•••• set`, and `unlocked` is
`false`.

---

## What the next session needs

The 25 that exist are reconciled and the eight reproductions are done; none of that changes when the
missing review turns up. What is blocked on it:

- 44 rows of Part 1 that have no text to check.
- The whole of Part 2. Its six group headings are the missing review's §6; its "do not touch" list is both
  reviews' over-engineering sections; 54 of the findings its PRs must close are unknown; and three of
  F8's, F9's and F11's proposed fixes are said to be corrected there, which changes what those PRs do.
- Part 3's decisions 2 and 4, which the brief leaves owed and which quote that review's F12/P5 and D-series.

Supply `docs/archive/reviews/CODE_REVIEW_2026-09-09_omarchy.md` and the rest follows from what is above.
