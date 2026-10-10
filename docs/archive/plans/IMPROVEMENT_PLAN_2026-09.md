# Improvement plan — September 2026

Written against `4f96a38` (main, `v0.41.2-92-g4f96a38`, the tree the v0.42 CHANGELOG entry describes),
10 September 2026. It closes the 24 open findings of `docs/archive/reviews/CODE_REVIEW_2026-09.md` and the 29 of
`docs/archive/reviews/CODE_REVIEW_2026-09-10_second_pass.md`, minus the four reserved for prompt A.
Status of every finding at this commit: `docs/archive/reviews/RECONCILIATION_2026-09-09.md`.

**28 pull requests, about 10 working days (≈75 h) of honest work.** Of that, 2 days are blocked on a
decision and 3½ on `docs/SPEC_custody.md` being accepted, so roughly 4½ days can start immediately after
PR 1 and PR 1 is a day on its own.

**PR 1 is the multiplier and nothing lands before it.** `make test` runs 25 suites, CI runs one, and
`make lint` exited 0 on this tree with a gate that did not run. Every PR below is gated; a gate that a
build does not run is a comment.

**Node #1 is not on v0.30 and the brief was wrong about it — checked on the machine, 10 September.** It is
`bayu-ungasan` on `mini`, a **git checkout already at `4f96a38`**, healthy on port 8081, 31 polls, no
errors. So it does not "update to v0.44": being a checkout on main, it takes every merge as soon as it
pulls, which makes it the beta channel in the most literal sense and means **PRs 6, 7 and 8 reach it before
any tag does**. Do not merge those on a Friday. **Its backup cron is now on and verified** — see below.

**The cron went on today, and installing it found a bug (S11).** cron runs with `/usr/bin:/bin`, node #1's
docker is at `/opt/homebrew/bin`, so the line `install.sh:510` writes fails with
`docker: command not found` — while `planetai doctor` reports `✓ nightly backup scheduled`, because that
row greps the crontab for a line rather than for a line that works. With a `PATH=` line prepended the same
test produced a real 2.1 MB dump and a fresh `LAST_OK`. Node #1 is fixed; PR 9 fixes the installer.

**Node #2 — Lucas, Menorca, v0.41.2 from the tarball — must not run `planetai update` until PR 16.**
Today, if the published `SHA256` is unreachable for any reason, `update.sh` skips the checksum silently,
fails to untar a truncated download, and prints *"updated. Nothing was lost"* with exit 0 having installed
nothing. Reproduced. PR 16 is one hour and it is the release gate for his machine.

---

## Do not touch

Everything here looks over-engineered and is not. Both reviews checked it; a PR that "simplifies" any of it
is a regression, and the reason is in `CODE_REVIEW_2026-09.md` §"Looks over-engineered, isn't" and
`CODE_REVIEW_2026-09-10_second_pass.md` §4.

- `report.py`'s `T` dict rather than gettext — three languages, one placeholder set, one gate, no build step.
- `_bearer_ok`'s loop with no early return — an early return leaks which token matched, through timing.
- `update.sh` copying itself to `/tmp` and re-execing — the naive version deleted `.env` in v0.30.
- `hb_line`'s `|| true` — an empty log makes grep exit 1 and kills the install under `set -euo pipefail`.
- `index.run_ro`'s `_ro["missing"]` latch — without it, one warning per rule per minute forever.
- `gen_floors.py` generating bash into `preflight.sh` — preflight runs through `curl | bash` on a machine
  that may have no Python; it has to be one self-contained file.
- The two distance *functions* in `sources.py` (`km` haversine, `metres` equirectangular) — different jobs
  at different scales. The nine **copies** are F17 and are real; the functions are not.
- `data/platform_floors.yml`'s vendor URL and read date on every floor, and the 180-day expiry — a version
  floor is a fact about someone else's product, and without the date it silently becomes a lie.
- `tools/check_docs.py`'s word-to-integer table for the MCP tool count — the count drifted unnoticed once.
- The three new `check_docs.py` gates from v0.42 — skill frontmatter shape, `AGENTS.md` routing to every
  skill, `llms.txt` links resolving. **They are in. Do not re-add them in the hygiene group.**
- `agent: build: ./app` + `image: planetai-app` — not a second image; it names the one `app` already built.
- Three separate `.env` reader *functions* in `install.sh`, `update.sh` and `backup.sh` — each must work
  alone inside a tarball with no shared library. F16 is `install.sh`'s **seven inline copies**, which are a
  different thing.
- `cmd_remove`'s 118 lines — every one of them is a thing that went wrong once.
- `update.sh`'s `cp -p` on the `.before-update` copies — `.env` is 0600 and the copy must not be world-readable.
- `layoutSave`'s two-case toast — it is honest about where the layout went. D3 is that its sibling is not.

And the standing constraints, which are decisions and not debt. No PR may reverse one: the CLI stays bash +
Python 3.9 stdlib on Apple's `/bin/bash` 3.2 (no `declare -A`, no `mapfile`, no `${var,,}`); the dashboard
is one file with no build step and no dependency it cannot live without offline; raw readings never leave
the node; secrets never logged; the live database never on a network mount; two containers; `main` is the
beta channel; tarball plus published checksum is the distribution; every sudo announces itself on the line
before; and `install`, `install.sh`, `update.sh` and `backup.sh` each work alone inside a tarball.

**Reserved for prompt A — no PR here:** F10 (`POST /actions` off loopback), F11 (`tolerance`'s bounds, which
is the same `place_geojson` signature line), A7 (`GET /sensors` is `SELECT *` and publishes the household's
device hostnames), A12 (`GET /health`'s exact coordinates). Prompt A lands before PR 1 and owns
`app/main.py`'s `/health` and `/place/geojson` routes, the bind, the `SHARE_LEVEL` allowlist and the
`PUBLIC` settings allowlist. From PR 1 onward this plan owns `app/main.py`; A is the one exception.

**No PR, by design: P5.** `app/sources.py` naming one regional network (`baliairdispatch`) inside a
domain-blind core is a layering question, not a defect: the source is off unless `BAD_ENABLED=1` and its
three parameters are already runtime settings, so its cost today is zero. Moving an adapter node #1 depends
on to satisfy a rule nothing is asking about is the kind of change this repository is right to refuse.
**The trigger: the second regional network.** When a node in another city needs one, the adapter moves to a
pack and `sources.py` keeps only the generic ring.

**Not in this plan, deliberately:** a per-command `bin/` split (the CLI is one file that must work alone in
a tarball); user hooks (nothing has asked); and a `migrations/` directory. **The trigger for `migrations/`:
the first once-only step that is not SQL** — a file to move, a container to rename, a setting to rewrite in
place. `init.sql` being idempotent covers every migration so far; the day one is not expressible as
idempotent SQL, that day the directory earns itself and not before.

---

# §1 · The multiplier

## PR 1 · a runner that counts what it skipped, and a build that runs all of it
**closes:** S10, F3
**touches:** `tests/all` (new), `Makefile:29-30`, `.github/workflows/lint.yml:10`, `:29-32`
**the change:** `tests/all` is a bash runner that loops over the suite list, runs each one, keeps going
after a failure, and counts pass / fail / skip — the shape `tools/preflight.sh` already uses for its own
rows. It exits non-zero if anything failed **or** if a skip is not on a declared expected-skip list, which
is what makes `make lint`'s silent `- requirements resolve skipped (venv failed)` a failure instead of a
line nobody reads. `Makefile:30`'s 25-term `&&` chain becomes `bash tests/all`. `lint.yml` gets `numpy` and
`duckdb` on its existing pip line and `- run: make test` in place of the hand-rolled last step.
**the gate:** the runner is its own gate. In `tests/all`, one line: with `PLANETAI_TEST_FAIL=test_logic.py`
forcing one suite to fail, the runner must exit non-zero **and** still report the other 24 —
`[ "$fail" -gt 0 ] && exit 1`, with the per-suite line printed before it.
**verify:** on `pai-clean`, `make test` prints 26 lines and a total; then push and read the CI log. Expect
red on the first push.
**could break:** the first CI run will fail, because 25 suites have never all run on a clean amd64 runner —
`tests/test_earth.py` needs `numpy`, `tests/trustdb.py` needs `duckdb`, and `test_ground.py` may want `h3`.
That is the point: find it now, once, rather than in every PR below.
**size:** a day. Most of it is whatever the clean runner reveals, not the runner.
**release:** no tag. This is infrastructure and ships nothing to a node. Node #1 is on v0.43 by now
(prompt A) and does not move.

---

# §2 · Data and boundary one-liners

## PR 2 · eleven internal working documents on the public origin
**closes:** F1
**touches:** `../planetai/.assetsignore` (10 lines, read in full)
**the change:** add `docs/`, `scripts/`, `Makefile` and `*.md` to the ignore list, with an explicit allow
for the one `.md` the site actually serves (`core-ideas-paper.md` is linked). `wrangler.toml` sets
`[assets] directory = "./"`, so the whole repository is the document root and the current list excludes
`src/ functions/ wrangler.toml .assetsignore .git/ .gitignore *.sh README.md archive/` and nothing else.
**the gate:** in `../planetai`'s own `make deploy` path, one line before the deploy:
`grep -q '^docs/' .assetsignore || { echo "docs/ must be ignored"; exit 1; }`.
**verify:** `make -C ../planetai deploy`, then
`for u in Makefile docs/pre_submission_checklist.md scripts/check_html.py; do curl -s -o /dev/null -w '%{http_code} '"$u"'\n' https://planetai.fab.city/$u; done` → three 404s. Verified 200/200/200 today.
**could break:** a page linking a doc under `docs/` — grep found none in `*.html` outside `archive/`.
**size:** under 1 h.
**release:** different repository, no node tag. **Do it today, before PR 1** — it is the only live public
exposure in either review, and it needs no node CI. Add `robots.txt` in the same commit; it is a 404 today.

## PR 3 · the small ones
**closes:** F4's missing gate, F6, F7, F13, F14, F20, F22, F25, S4, A10, and two from the first review's
one-liner list (`.gitignore:5`, `install.sh:310`'s missing `/dev/urandom` fallback)
**touches:** `bin/planetai:541`, `:1038`, `:1043`, `:1304`, `:1327`; `app/main.py:474`, `:832`;
`app/sources.py:372`, `:434`; `app/static/index.html:1090`; `app/index.py:109`;
`packs/place/refresh.py:8`, `packs/place/verify.py:29`; `docker-compose.yml:76`; `install:4`;
`install.sh:310`; `.gitignore:5`
**the change:** one commit, one message, twelve edits, none of them touching behaviour a test asserts
except where the assert is added here. F6: move the stray `#` to the end of the line so `local`, `indoor`
and `kind` come back into `/export`. F7: one `<option value="es">`. F13: drop `/{NODE}` from the User-Agent
and `round(lat, 3)` in both `params`. F14: `httpx.Client(timeout=120)` twice. F20: "verifies its published
checksum", not "signed". F22: delete the dead `cmd_backup` and the dead `backup)` arm. F25: pin
`ipfs/kubo`. S4: `planetai storage` prints `set` / `not set` instead of the backup token. A10: the same
`FILTER (WHERE f.t - a.ts < interval '24 hours')` on `percentile_cont` that `count` already has. F4's gate:
stop excluding `#` from `bin/planetai:541`'s stray-space check, and add the `.env.example` assert the
finding names.
**the gate:** four asserts, each in a file that already holds its kind — in `tests/test_shipped.py` the AST
walk `assert {"t","sensor","metric","kind"} <= keys` for F6 and `no envget BACKUP_TOKEN inside a printf
outside cmd_ui` for S4; in `make lint` the `.env.example` regex for F4 and
`assert 'httpx.Client()' not in packs/*/*.py` for F14.
**verify:** on `pai-clean`, `make lint && make test`; then `planetai storage` shows no token,
`curl /export?day=<today> | python3 -c 'assert "kind" in json.load(sys.stdin)["hourly"][0]'`, and
`planetai backup` with the database down exits non-zero.
**could break:** a consumer keyed on `/export`'s current `hourly` shape — `tools/nas/pull.py` and every test
are indifferent. `planetai backup` now exits 1 on failure, which is F22's whole point.
**size:** half a day, mostly the four asserts.
**release:** yes — tag it. Twelve visible fixes including a Spanish node that stops resetting itself to
English. Node #1 waits for PR 8.

## PR 4 · two cells with one key, and a gate that refuses the next one
**closes:** P2 · **lands after `docs/SPEC_custody.md` is accepted** — both air-quality cells filter `s.local`
**touches:** `packs/air-quality/cells.yml:3-23`, `packs/open-data-health/cells.yml:2-15`,
`tools/check_rules.py` (the cell loop it already has)
**the change:** `packs/air-quality/cells.yml` defines two `Environmental|Community` cells — a 24h PM2.5 mean
and a "% of days over the WHO guideline" — and `open-data-health` defines two `Governance|City`. A spine
keeps one row per cell, so one of each pair is silently lost, and because the units differ, which one
survives changes what the cell *means*. Give the weaker of each pair a distinct key where the Observations
base has one, or fold it into `notes`. Four lines of YAML.
**the gate:** in `tools/check_rules.py`, which already parses every `cells.yml`: one line —
`assert len(keys) == len(set(keys)), f"{pack}: duplicate cell key {dupes}"`.
**verify:** on `pai-clean`, `python3 tools/check_rules.py` fails before, passes after; then
`curl -s localhost:8080/cells | python3 -c "import sys,json;c=[r['cell'] for r in json.load(sys.stdin)];assert len(c)==len(set(c)), c"`.
**could break:** a consumer already reading the surviving row of either pair under the old key. Nobody is:
the Index ingest is not built yet and node #1's cells have never been published.
**size:** under 1 h. The gate is the work.
**release:** no. Ships with the next tag.

## PR 5 · Cancel means cancel, and Reset resets
**closes:** D2, D3, D4
**touches:** `app/static/index.html:459`, `:1038`, `:1049`, and the three `${…unit}` / `${…label}` sites at
`:562`, `:580`, `:628`
**the change:** D2 is one clause: `const note = prompt(…); if (note === null) return;`. Today `null ||
'acted'` means pressing Cancel posts the action anyway and ρ goes from 0 to 1 — confirmed in a browser
against the node. D3: `layoutReset` makes the same `PUT /settings` with an empty `UI_LAYOUT` that
`layoutSave` at `:1044` already makes, and toasts the same two-case message, so Reset survives a reload
instead of coming back from the node. D4: add `'` to `esc()`'s character class and route `unit` and `label`
through it — no behaviour change today, since every one is a literal, but a pack's `cells.yml` `unit:`
string is third-party data and reaches the dashboard the day anyone renders `/cells`.
**the gate:** in `tools/check_ui.py`, which already parses the script: one line —
`assert "=== null" in act_src, "act() must return when the prompt is cancelled"`, plus the companion assert
that `layoutReset` names `UI_LAYOUT`.
**verify:** on `pai-clean`, in a browser: with an act-level alert present, stub `window.prompt` to return
`null`, click "I did this", and `/rho` is unchanged. Then hide a card, press Reset, reload — the card is
back.
**could break:** somebody using Reset deliberately as a per-screen override; the two-case toast says which
happened, which is the same four lines.
**size:** under 1 h.
**release:** yes, with PR 3 if they land together. ρ is the number this project exists to produce and it is
currently inflatable by a dismissed dialog.

---

# §3 · Stop-the-node

## PR 6 · a pack data file can no longer stop every alert or every cell
**closes:** A2, A8
**touches:** `app/packs.py:83-86`, `app/index.py:71-86`, `app/main.py:393`
**the change:** two guards, same shape, same reason. `packs.alerts()` already exists to filter the rules
that can reach a household and its docstring already describes this exact failure — so filter there:
a rule with no `message` is dropped and logged once, instead of raising `KeyError` out of `run_rules` on
every 60-second turn forever. Confirmed on `pai-clean`: `/alerts` frozen for 150 s with
`errors={"run_rules": "'message'"}`, every rule on the node dead, from one file in `packs/`. In
`index.cells()`, move lines 79-86 inside the `try` that already wraps `run_ro` — a two-space indent, no new
code — so `min_buckets: many` no longer returns 500 from `/cells` and `/export`. Both confirmed.
**the gate:** one test, in `tests/test_packs.py`: a rule dict with no `message` is not returned by
`packs.alerts()`, and a cell dict with `min_buckets: "many"` is skipped rather than raising. One file, one
gate, both findings.
**verify:** on `pai-clean`, drop `packs/x/rules.yml` with a message-less rule and `packs/y/cells.yml` with
`min_buckets: many`, restart, and watch `/alerts` keep growing and `/cells` and `/export` keep answering
200 — with one warning line naming each bad file.
**could break:** a pack relying on a message-less rule being silently skipped — none ship, and
`tools/check_rules.py:101` has refused them in the repository since before this.
**size:** half a day, most of it the test.
**release:** yes. `rules.yml` is the file the project invites strangers to contribute.

## PR 7 · a settings field that is not a number keeps the node running
**closes:** A1, A3, A4
**touches:** `app/settings.py:142-147`, `app/main.py:62`, `:103`, `:133`, `:292`, `:301`, `app/sources.py:343-344`
**the change:** `settings.num` is the one numeric-safe reader and it is int-only, which is why every float
setting in the tree does a bare cast — 44 of them. Add `real(key, default: float) -> float` beside it, four
lines in the same `try/except ValueError` shape, then use the two helpers at the five sites that are
reachable from a loop or a route with a dashboard free-text field in front of them: `LOCAL_RADIUS_M`
(`main.py:103`, `:133` — confirmed to freeze every source and MQTT ingest for as long as it is wrong),
`BAD_RADIUS_KM` and `BAD_MIN_SEPARATION_M` (`sources.py:343-344`, evaluated in `poll_once`'s `for` header
before the try, so the same kill through a different key), `MESH_GATEWAY_NODE_NUM` (`main.py:62`), and
`QUIET_FROM`/`QUIET_TO` (`main.py:301`, where `_hours()[0]` on `"22:00"` raises `IndexError` at the line
that decides whether to notify — the alert commits and nobody is told, and `status.errors` erases itself
one turn later). `_hours` loses both callers and goes.
**the gate:** in `make lint`, the same AST-assert shape F11 uses: no bare `float(settings.get(...))` or
`int(settings.get(...))` remains anywhere in `app/`. That is the gate that keeps the other 39 honest as they
are touched, and it fails on this tree.
**verify:** on `pai-clean`, `PUT /settings` each of the five to a non-numeric value in turn; `/health`'s
`polls` and `last_poll` keep advancing, `errors` stays `{}`, and an act-level alert still reaches Telegram.
**could break:** a node that had set `QUIET_FROM=22,23` expecting a list — none can, because both callers
took `[0]` and the list has never meant anything.
**size:** half a day.
**release:** yes, and this is the one a household feels: today three of the dashboard's own fields can
silence the node with a typo and nothing says so for more than sixty seconds.

## PR 8 · the container that faces strangers stops holding the database password
**closes:** F2, F5, and A6's reading
**touches:** `docker-compose.yml:88-99` (the whole `reticulum` block, read in full),
`app/reticulum_bridge.py:1-40`, `bin/planetai:554`, `:821`
**the change:** delete `env_file: .env` from `reticulum` and pass through the six variables the bridge
actually reads — `LOG_LEVEL`, `NODE_NAME`, `NODE_API_URL`, `RETICULUM_DATA`,
`RETICULUM_ALERT_DESTINATIONS`, `RETICULUM_ANNOUNCE_S` — as `${VAR:-}` in the `environment:` block that is
already there. Today it gets 75 keys including `POSTGRES_PASSWORD`, `ADMIN_TOKEN`, `TELEGRAM_BOT_TOKEN`,
`AGGREGATE_TOKEN`, `BACKUP_TOKEN` and the AI keys, and it is the one process in the compose file that
parses input from people the household has never met (`ports: 4242`). In the same three lines, F5:
`ports: ["4242:4242", "127.0.0.1:4243:4243"]`, so `planetai reticulum` and the doctor's `reticulum bridge
up` row stop failing against a port that has never been published.
**the gate:** in `tests/test_shipped.py`, beside the container assertions it already makes — the
`docker compose --profile reticulum config` assert the finding names:
`assert 'POSTGRES_PASSWORD' not in env and len(env) < 10`.
**verify:** on `pai-clean` with the reticulum profile on, `planetai reticulum` prints an LXMF address
instead of failing after 60 s, and `planetai doctor` shows the bridge row green.
**could break:** `RETICULUM_ALERT_DESTINATIONS` set only in `.env` stops reaching the bridge if it is left
off the list — it must be one of the six.
**size:** under 1 h.
**release:** **yes — tag it v0.44.** Node #1 runs reticulum and holds a real `TELEGRAM_BOT_TOKEN`, so this
is the PR that matters most to it — but it is a git checkout on main and will already have taken PRs 6, 7
and 8 when it next pulls, tag or no tag. The tag is for node #2 and whoever installs next.

## PR 9 · three ways the backup quietly stops, and none of them show
**closes:** F15, S5, S11
**touches:** `bin/planetai:1002-1004`, `:546`, `backup.sh:52`, `install.sh:509-510`
**the change:** two lines, in the shape `cmd_report` uses five times forty lines away.
`[[ "$val" =~ ^[0-9]+$ ]] || fail "days is a whole number"` on `keep`, because a non-numeric
`BACKUP_KEEP` makes `backup.sh:52`'s `find -mtime +$KEEP` exit non-zero under `set -euo pipefail` **after**
the dump and **before** the export, the IPFS pin, the rclone copy and `LAST_OK` — so the local dump keeps
appearing, the doctor stays green, and the only copy that survives a house fire stops. And
`[[ -n "$val" ]] || fail "usage: planetai storage set remote <rclone remote:path>"`, because
`planetai storage set remote` with the argument forgotten sets it to empty and reports *"off-machine copies
to '' after each backup"*, which reads like success.
**the gate:** in `tests/test_running_state.sh`, which already runs the CLI: `planetai storage set keep abc`
exits non-zero and `.env` is unchanged.
**verify:** on `pai-clean`, the two commands above, then `planetai backup` and check `backups/LAST_OK` is
fresh.
**could break:** nothing.
**size:** under 1 h.
**release:** no. Ships with the next tag.

## PR 10 · the mesh gateway's credential cannot write readings any more
**closes:** A11
**touches:** `config/mosquitto/mosquitto.conf` (14 lines, read in full),
`config/mosquitto/acl` (new), `bin/planetai:750-808` (`cmd_meshtastic`), `app/main.py:158-175`
**the change:** the broker requires a password (`allow_anonymous false`, `password_file`) but has no
`acl_file`, so the one credential `planetai meshtastic` writes into an ESP32 on the household WiFi can both
publish to `planetai/sensors/#` — which `main.py:166-174` turns into a `local: true` sensor at an arbitrary
metric, the exact thing `POST /readings` was given the admin token to prevent on 6 September — and
subscribe to `msh/#` and read every alert the node sends over the mesh. Add an `acl_file` with two topic
lines beside the `password_file`, written by `cmd_meshtastic` which already writes the password, and give
`planetai/sensors/#` its own user or drop the branch until something uses it.
**the gate:** `tests/test_meshtastic.py` already asserts the config's shape; add the ACL file to what it
asserts, and one case that the gateway user's ACL does not include `planetai/sensors/#`.
**verify:** on `pai-clean` with the mqtt profile on: publish to `planetai/sensors/x/pm25` with the gateway
credential and get a permission error; publish to `msh/…` and see `mesh.packets` increment.
**could break:** an existing Meshtastic gateway if the ACL is wrong — `cmd_meshtastic` writes both files so
it can write a matching pair, and `planetai doctor`'s mesh row shows it immediately.
**size:** half a day.
**release:** no. Ranked low on purpose: it needs a credential that lives on a device inside the house. It is
here because one path was hardened and its twin was not.

## PR 11 · one card that throws stops costing every card below it
**closes:** F8, D1
**touches:** `app/static/index.html:516-645` (the whole of `refresh()`, read in full), `tools/check_ui.py`
**the change:** v0.41.1's fix was the right shape — one `card(where, fn)` helper — and it is applied to
three of eighteen cards, at `:533`, `:534` and `:641`. `refresh()` is still one `try` at `:516` with one
`catch` at `:644` that writes "node not answering" in the corner, and twenty-eight paint statements sit
inside it unguarded: the hero, the day chart, the room and street tiles, the trust card, the alert list, ρ,
the world tiles, the place card and the whole Wall view. So a throw anywhere still darkens everything below
it, and the satellite cards are drawn last. Wrap each `$('#x').innerHTML=` group in the existing
`card('#x', ()=>{…})` — about twelve two-token edits, no new code. It is grouped under stop-the-node
because on a wall screen a dark dashboard *is* the node stopping, as far as the household can see.
**the gate:** in `tools/check_ui.py`, the assert the finding names: every `data-card` id appears as a
`card('#…')` argument, or the file names the ones that do not. Fails on this tree (18 vs 3).
**verify:** on `pai-clean`, break the ring card on purpose in the served file and reload — that card says so
in its own box, names itself in the console, and every other card draws.
**could break:** a card relying on a later statement in the same `try` running. Twelve edits, so read each
group's end before wrapping it.
**size:** half a day.
**release:** yes. It is the third release in a row where a dashboard card took its neighbours down.

---

# §4 · Wrong-answer

## PR 12 · a NULL in a message no longer sends the household the template
**closes:** P1
**touches:** `app/main.py:396-398`, `packs/place/rules.yml:14`, `tests/test_report_templates.py`
**the change:** the sentinel at `main.py:396` turns a NULL into the **string** `"—"`, so `{clinic_m:.0f}`
raises `ValueError`, and the `except` at `:397` substitutes the raw template — confirmed, and the household
receives `About {buildings:.0f} buildings within a kilometre, {commercial_pct:.0f}% of them shops…`. Fix it
at the sentinel so every rule is fixed at once: strip the format spec for the keys whose value is None
before formatting, four lines, `re` already imported. A scan found five such slots today, all in
`place_around`, and any new rule with a nullable aggregate inherits it; `tools/check_rules.py:105` already
checks the placeholder exists in the SQL's output columns, which passes here, because a lint cannot see a
NULL.
**the gate:** in `tests/test_report_templates.py`, which already asserts all three locales are complete:
format `place_around`'s template with `clinic_m=None` and `assert "{" not in text`.
**verify:** on `pai-clean`, insert `place-point` observations for every metric except `nearest_health_m` and
let the rule fire; the alert reads "the nearest health care — m away".
**could break:** a message that wanted the exception — none. The current fallback prints braces at a person.
**size:** under 1 h.
**release:** yes. It is a wrong answer sent to a household in their own language.

## PR 13 · the heat thresholds stop being one street in Bali
**closes:** F12, P3 · **blocked on decision 2** (see below)
**touches:** `packs/heat/rules.yml:21`, `:41`, `app/main.py:87` (the session `options=` string),
`tools/check_docs.py:163`, `packs/heat/README.md`
**the change:** the plumbing exists. `main.py:87` already injects `-c planetai.lat= -c planetai.lon=` into
the session and five rule files already read them with `current_setting`. Add `planetai.heat_at_act` and
`planetai.heat_at_danger` from settings to that same string — two lines in `db()` — and replace `>= 35`
and `>= 40` with `>= current_setting('planetai.heat_at_act', true)::float`, two-argument form with a
coalesce so a database predating the setting does not raise. A node in Barcelona or Boston currently
inherits Kuta Selatan's floor, and `presets/` ships four cities.
**the gate:** the one that must survive is `tools/check_docs.py:163`, which asserts the pack README quotes
the rule's number. Whichever way decision 2 goes, the gate becomes "the README quotes the *default*", and
the default lives in one place — that is the whole content of the decision.
**verify:** on `pai-clean`, `PUT /settings` `HEAT_AT_ACT=32`, insert a reading at AT 33 °C, and the act rule
fires; set it back to 35 and it does not.
**could break:** a node whose database predates the setting — hence the two-argument `current_setting`.
**size:** half a day.
**release:** yes, and it is the release that makes a second climate installable.

## PR 14 · `Governance` is the core's key
**closes:** A9 · **blocked on the Governance decision below, and lands after `docs/SPEC_custody.md`**
**touches:** `app/index.py:47`, `:61-95`, `packs/open-data-health/cells.yml`, `tools/check_rules.py`
**the change:** `_row()` does no key validation and `cells()` does no de-duplication, so on a
`NODE_SCALE=city` node with `open-data-health` enabled **three rows claim `Governance|City`** — 42.0, 517.0
and ρ — and a spine that keeps one row per cell keeps one. Confirmed: three in, one kept. ρ survives today
only because the core appends last; reorder `cells()` and the number this project exists to produce is the
row that is lost. Reserve the prefix for the core, or move ρ to its own key — that is the decision. Then
de-duplicate in `packs.cells()` rather than trusting every pack.
**the gate:** in `tools/check_rules.py`, extending PR 4's assert: no pack cell may be keyed `Governance|*`
(or whatever the decision says), and no two cells across all enabled packs may share a key.
**verify:** on `pai-clean` with `NODE_SCALE=city` and `open-data-health` on,
`curl /cells | python3 -c "…assert len(c)==len(set(c))"` passes, and ρ is still there.
**could break:** `open-data-health` is a pack that exists precisely to contribute a governance metric. This
is why it needs the decision and not a patch.
**size:** half a day.
**release:** no. It ships with whatever tag follows.

## PR 15 · where a number came from, in PROV-JSON
**closes:** the PROV-O mapping and `GET /provenance` from the benchmark response
**touches:** `app/main.py` (one new route), `app/index.py:47` (`_row`'s `source` and `state` fields),
`docs/SPEC.md`
**the change:** vocabulary only, no RDF store and no new dependency. The node already carries every fact
PROV-O needs and calls them by other names: `sensors.kind` (`sensor | portal | model | survey | child`) is
the activity type, `sensors.meta` holds `attribution` and `licence`, `cells[].state`
(`live | partial | mock`) is the provenance claim, and `_row()` already stamps `source` and `observed_at`.
`GET /provenance` maps those onto `prov:Entity`, `prov:Activity`, `prov:Agent`, `prov:wasDerivedFrom` and
`prov:wasAttributedTo` and returns PROV-JSON. Nothing new is measured; an existing answer gets a
vocabulary an outside reader already has a parser for.
**the gate:** `/provenance` returns valid PROV-JSON for one synthetic row (`om-point`, a model) and one
external row (a `bad-` reference station) — one test in `tests/test_shipped.py` validating the document
shape against the PROV-JSON key set, no network.
**verify:** on `pai-clean`, `curl /provenance | python3 -m json.tool` and check the model point is a
`prov:Activity` of type `model` attributed to Open-Meteo with its licence.
**could break:** nothing; it is a new read-only route. It is unauthenticated, so it must go on prompt A's
`SHARE_LEVEL=open` read allowlist — coordinate that line, do not re-decide it.
**size:** a day. The mapping is the work, not the route.
**release:** yes — it is the answer to the benchmark, and the reports/funnel session (Release 3) starts
after this group merges.

---

# §5 · The stranger's first hour

## PR 16 · update.sh refuses a download it could not verify
**closes:** S3 · **this is the PR after which Lucas may run `planetai update`**
**touches:** `update.sh:79-85`, `install:87-92` (read in full, not changed),
`tests/test_release_consistency.sh`
**the change:** copy the five lines that already exist in `install`. Today `update.sh:80` is
`if command -v shasum >/dev/null && curl -fsSL "$SITE/get/SHA256" -o "$tmp/sha" 2>/dev/null; then`, which
fails open twice, both times silently: `shasum` absent (it is macOS's name; Debian ships `sha256sum`), and
the checksum fetch failing for any reason. Then `tar xzf` fails as the **left** operand of an `&&` list,
which `set -e` exempts, and the script carries on to the schema step, the rebuild, the doctor and
`>> updated. Nothing was lost: 6216 readings…` — **exit 0, six green doctor rows, and no new code
installed.** Reproduced. `install:87-92` fails closed on all three paths and its comment records that it
once did not. Take those lines, and put `|| die` on the `tar xzf`.
**the gate:** in `tests/test_release_consistency.sh`, which already reads both files: `update.sh` must
contain `sha256sum`, and no checksum branch in either file may be conditional on `command -v shasum` alone.
**verify:** on `pai-clean6`, serve a 100-byte tarball from a local site with `SHA256` returning 404 and run
`PLANETAI_SITE=… ./update.sh`; expect a non-zero exit and "the download cannot be verified" as the last
line. Then the same with a correct checksum and a real tarball, and expect a real update. A release PR: the
fresh-install rehearsal is `curl -fsSL planetai.fab.city/install | bash` on a clean `pai-clean6` after
`make ship`, followed by `planetai update` twice.
**could break:** a node updating from a site whose `SHA256` is genuinely missing now refuses instead of
pretending. That is the fix, not a side effect. Publish the checksum before shipping — `tools/ship.sh`
already writes it; add a `curl` check to `make released`.
**size:** under 1 h, and it is the highest value per hour in this plan.
**release:** **yes, tag it, and tell Lucas the same day.** He is on v0.41.2 from the tarball and his machine
is `update.sh`'s first run somewhere nobody here can see.

## PR 17 · the version check runs after the preflight, and a running node reaches its menu
**closes:** S1, S8
**touches:** `bin/planetai:255-285` (read in full), `tests/test_preflight.sh`,
`tests/test_running_state.sh`
**the change:** the same three lines, two findings. `version_gap` is called at `:261`, **before** the
preflight block at `:267-272` — which is exactly what `CODE_REVIEW_2026-09.md` said to change before that
hunk was committed, and it landed above anyway: a machine below the floor makes a network call and is
offered `curl … | bash` before being told it cannot run a node. Move the call below the `fi` at `:272`. And
`:271`'s `[[ $pf -eq 0 ]] || exit 1` applies install-time floors to a post-install menu, so on any machine
below them — arm64, under 4 GB, the revive-a-laptop cases — a node that has run for days can never be
updated, reconfigured or removed through `planetai setup`. Confirmed: exit 1 on a VM with 6,210 readings in
it. `node_running` is computed eleven lines below at `:281`; swap the two blocks and the condition becomes
`… && [[ $node_running -eq 0 ]]`.
**the gate:** in `tests/test_preflight.sh`, a relative-order assert in the shape `tests/test_sudo_prompt.sh`
was converted to in v0.42: the line calling `version_gap` is greater than the line calling
`tools/preflight.sh`. Plus, in `tests/test_running_state.sh`, which already fakes a running node:
`planetai setup` reaches "What would you like to do?" with the preflight forced to fail.
**verify:** on `pai-clean` — which is arm64 with 3 GB and therefore fails preflight — `planetai setup`
reaches the Update / Reconfigure / Nothing / Remove menu.
**could break:** a running node on a machine that has since lost Docker; `node_running` is false then, so
the preflight still runs, which is right.
**size:** under 1 h.
**release:** yes. It is the command every tester is told to type.

## PR 18 · an AirGradient on the WiFi is actually read
**closes:** A5
**touches:** `app/sources.py:320-357`, `app/settings.py:28`, `tests/test_sources.py`
**the change:** `sources.airgradient(hc, hosts, lat, lon, indoor)` is a complete forty-line adapter called
from nowhere but a test. `sources.enabled()` never appends it, and the only two reads of
`AIRGRADIENT_HOSTS` build a **skip** set for `baliairdispatch`, a source that is off by default. Confirmed:
with the setting set, `enabled()` returns `['open-meteo', 'open-meteo-cams']` and no `ag-*` row ever
appears. Meanwhile the dashboard offers the household *"AirGradient hosts — Hostnames or IPs on your WiFi,
comma-separated. Read directly, no cloud."* Two lines in `enabled()`, in the shape of the four beside it.
**the gate:** in `tests/test_sources.py`: every adapter function in `sources.py` is either reachable from
`enabled()` or named in an allowlist of deliberate exceptions. That assert would have caught this on the
commit that added it, and it is the gate that stops the next dead adapter.
**verify:** on `pai-clean`, set `AIRGRADIENT_HOSTS` to an unreachable hostname; within one poll,
`status.errors` names `airgradient` — which is the honest failure, and infinitely better than silence.
**could break:** a node with a stale value now polls a host that is not there; the per-source `try` at
`main.py:95` catches it and names it.
**size:** under 1 h.
**release:** yes. Somebody bought a sensor, typed its name in, and has been waiting.

## PR 19 · every sudo in the CLI announces itself, and the test reads both files
**closes:** S2
**touches:** `bin/planetai:700`, `:715`, `:724`, `:1268`, plus one new `sudo_first` near `:110`;
`tests/test_sudo_prompt.sh:21`, `:29`, `:83`, `:93`
**the change:** "every sudo announces itself on the line before" is a standing constraint with a test, and
the test names `install.sh` in every check it makes. `bin/planetai` has no announcement helper and four
executed sudos; `:715` (`sudo brew services start tailscale`) and `:1268`
(`sudo systemctl enable --now ollama`) both send output to the log and end in `|| true` or a fallback, so a
refused password is silent and the thing that needed it simply did not happen. Lift `install.sh`'s
`sudo_first` into `bin/planetai` — it cannot be shared, both files must stand alone in a tarball — and call
it once at the top of `cmd_mesh` and `cmd_agent_local`.
**the gate:** parameterise `tests/test_sudo_prompt.sh` over both files. Its walk at `:58-65` is already
file-agnostic; the four `open("install.sh")` calls are not. Fails on this tree.
**verify:** on `pai-clean`, `planetai mesh` prints the announcement before any password prompt, and
`bash tests/test_sudo_prompt.sh` passes for both files.
**could break:** `planetai mesh` on a passwordless-sudo machine prints one extra line.
**size:** half a day, mostly parameterising the test.
**release:** no.

## PR 20 · install and update keep a transcript, and two updates cannot run at once
**closes:** S6, S7
**touches:** `install.sh:1-30`, `update.sh:1-25`, `tests/test_release_consistency.sh`,
`tests/test_diagnose.sh`
**the change:** two additions to the same two files. The lock: `mkdir "$LOCK" 2>/dev/null || die "another
update is running (…). If it is not, remove $LOCK."` with a `trap 'rmdir "$LOCK"' EXIT` beside the existing
one at `update.sh:15`. `mkdir`, not `flock` — `flock` is not on macOS. Today two `planetai update` runs will
both back up, both untar over the same live folder and both apply `init.sql`. The transcript: both scripts
keep a per-step log already, and what is missing is the run — the questions, the answers, the warnings
between steps, the doctor rows, the closing sentence, which is what a tester actually pastes. One
`exec … script -qefc` at the top, guarded by an env var, in the shape of `update.sh`'s existing self-copy
re-exec, with a BSD/GNU fallback the way `tools/bundle.sh:25-27` already handles tar's flags.
**the gate:** in `tests/test_release_consistency.sh`: the lock exists in `update.sh` and is a `mkdir`, not
`flock`. In `tests/test_diagnose.sh`: after a failed install in a sandbox, the transcript file exists and
contains the first question.
**verify:** on `pai-clean6`, start `./update.sh`, and while it runs start a second one — the second dies
naming the lock directory. Then `cat .planetai-install-transcript.log` after an install and read the four
questions back.
**could break:** an update killed with `-9` leaves the directory and the next run refuses until it is
removed; the die message says which directory and why, which is the reason not to use a PID file. And
`script`'s flags differ between BSD and GNU — both branches, tested on both.
**size:** half a day.
**release:** yes, with PR 16 if they land close together — both are the tarball path.

## PR 21 · one command to paste when it is broken
**closes:** S9
**touches:** `bin/planetai` (one new function, one case arm), `docs/TROUBLESHOOTING.md`,
`skills/troubleshoot-node/SKILL.md`, `tests/test_diagnose.sh`
**the change:** `docs/TROUBLESHOOTING.md` and `skills/troubleshoot-node/SKILL.md` both open by asking for
four things — `planetai doctor --json`, `planetai status --json`, twenty lines of logs, the version — and
the skill has to say "never `.env`" because the obvious next thing a helpful person pastes is `.env`.
`planetai support` composes the four that exist and adds the one thing not currently obtainable safely and
most often needed: the `.env` **keys** with every value replaced. Logs filtered through
`sed -E 's/(TOKEN|KEY|PASSWORD)=[^ ]*/\1=<stripped>/g'`.
**the gate:** in `tests/test_diagnose.sh`: run `planetai support` and assert the output contains the version
and the doctor rows and **matches no value from `.env`**. That last assert is the whole point of the
command, and it is what makes S4's fix (PR 3) hold.
**verify:** on `pai-clean`, `planetai support > /tmp/s.txt` then
`for v in $(grep -oE '=[^ #]+' .env | cut -c2-); do grep -q "$v" /tmp/s.txt && echo LEAK "$v"; done` → silent.
**could break:** nothing new; it is a composition of four existing commands.
**size:** half a day.
**release:** yes. It is the command that makes every later bug report cheaper.

## PR 22 · one doctor, called from three places
**closes:** F9
**touches:** `install.sh:496-510`, `update.sh:136-150`, `bin/planetai:521-560`,
`tests/test_running_state.sh`
**the change:** three `chk()` implementations with three different lists — 4 checks in `install.sh`, 6 in
`update.sh`, 16 in the CLI. `bin/planetai:503` carries the comment about `/health` answering while every
database call fails, seen after a reinstall over a leftover volume where *"pg_isready happy, the app locked
out, the install's own doctor all green"* — and the fix for that went into the CLI doctor only, so
`install.sh`'s doctor, the one every fresh tester actually sees, still has the four checks it had then.
Both callers call `./bin/planetai doctor quiet` instead; it exists, it is in the tarball, and
`finish_setup:429` already calls it. Net about −20 lines. **This needs the third decision from the first
review's §7 and it has an answer: yes** — `update.sh:154` already calls `./bin/planetai packs`, so the
dependency exists in one direction, and both files ship in the same tarball.
**the gate:** `tests/test_running_state.sh` still passes, plus one new case: with a stale volume and the old
password, `install.sh` prints `✗ app logs in to the database`.
**verify:** on `pai-clean6`, a reinstall over a stale `_db` volume keeping the old password; the installer's
own doctor goes red on the row that matters.
**could break:** the CLI doctor needs `envget`, `mounted` and `crontab`; mid-install some rows go red that
today are simply absent. Both callers already treat red as a warning, not a failure.
**size:** half a day.
**release:** yes.

## PR 23 · the README says which version this is and which packs ship
**closes:** F21
**touches:** `README.md:7`, `:54`, `:100`, `tools/check_docs.py:126`
**the change:** the badge says 0.31, `git describe` says `v0.41.2-92` and the CHANGELOG says v0.42; line 54
names 5 packs and line 100 names 11, and there are 13 — `nearby` and `forecast`, the two headline packs of
v0.41, are in neither list. Fix the three lines, then extend `check_docs.py:126`'s
"README's docs index must match the directory" comparison to `packs/` — the same idea, already written,
applied to one directory and not the other — and assert the badge matches `git describe`.
**the gate:** that extension. `make lint` fails when a pack folder is added without touching the README.
Fails on this tree.
**verify:** `make lint`; then `mkdir packs/zzz && touch packs/zzz/pack.yaml && make lint` fails.
**could break:** the badge assert needs a tag to compare against, and **v0.42 is not tagged** — `git tag -l
'v0.42*'` is empty even after a fetch. Tag it, or compare against the CHANGELOG's top heading, which is the
more honest source anyway.
**size:** under 1 h.
**release:** no, but tag v0.42 while you are here.

---

# §6 · Hygiene

## PR 24 · the build stops repeating itself, and the tarball stops carrying the developer's tools
**closes:** F24, F23
**touches:** `.github/workflows/lint.yml:12-13`, `tools/bundle.sh:13`
**the change:** F24: delete the `docs match the code` step; `make lint` ends with the same script.
(`check_rules.py` is deliberately re-run because sqlglot is not installed when `make lint` runs;
`check_docs` has no such excuse.) F23: extend `bundle.sh:13`'s one exclude regex so the tester's tarball
stops carrying `tools/ship.sh` (which pushes to the site repo and runs `wrangler deploy`),
`gen_floors.py`, `extract_strings.py`, `render_platforms.py`, `tools/hooks/` and `data/` — about 620 lines
and 8 files, none of which the runtime reads.
**the gate:** `tests/test_release_consistency.sh`:
`tar tzf … | grep -c "ship.sh\|platform_floors"` → 0, and the CI log has one `50 documents check out`.
**verify:** `bash tools/bundle.sh /tmp/x` then the `tar tzf` assert; push and count the `check_docs` lines.
**could break:** `make check-floors` and `make lint` inside a tarball — already broken there, because
`tools/check_*` and `tests/` are already excluded.
**size:** under 1 h.
**release:** yes — it changes what a tester receives, so it needs a `make ship` and a fresh-install
rehearsal on `pai-clean6`.

## PR 25 · a clock that has drifted is a red doctor row
**closes:** F19
**touches:** `bin/planetai:521-560`, `tests/test_running_state.sh`
**the change:** one doctor row using what is already installed:
`chk "clock within 2 minutes"` comparing `date +%s` against the `Date:` header of
`curl -sI https://planetai.fab.city`. The report clock is the host clock —
`report._local_now()`, `due_local` as the uniqueness lock (`main.py:351`), quiet hours, and
`main.py:348`'s `if now.hour not in _report_hours() or now.minute >= 20`. That twenty-minute window is the
sharp edge: a laptop in a cupboard whose clock has drifted past it writes no report for that hour at all,
and the next one folds it in silently, so the failure looks like a setting. Nothing anywhere checks the
clock: `grep -niE "ntp|timedatectl|clock|time sync" tools/preflight.sh bin/planetai` → nothing.
**the gate:** the row is the gate. `tests/test_running_state.sh` asserts the row exists and skips cleanly
when the egress check has already failed.
**verify:** `date -s "+10 minutes"` on a throwaway VM, then `planetai doctor` shows the row red.
**could break:** a node with no egress goes red; make the row skip when the existing egress check failed.
**size:** under 1 h.
**release:** no.

## PR 26 · one `.env` reader in install.sh
**closes:** F16
**touches:** `install.sh:430`, `:443`, `:448`, `:500`, `:525`, `:528`, plus one new `envget` near the top;
`bin/planetai:463`
**the change:** `install.sh` has no `.env` reader function and six inline copies, plus one buried in a
`bash -c` string at `bin/planetai:463`. Two of them use `cut -d= -f2`, not `-f2-`, so a value containing
`=` is truncated. `:430` strips spaces but not quotes, so `DATA_DIR="/mnt/x"` fails the `PG_VERSION` test
and **the reinstall-over-a-volume refusal — the guard whose absence cost a tester's data — does not fire**.
`:528` strips no comment at all, so `POLL_SECONDS=300  # …` prints the comment to the tester. One `envget`,
identical to `bin/planetai:111`; the six inline copies become calls. Net about −8 lines. **Leave the three
standalone reader functions alone** — they are in the do-not-touch list for a reason.
**the gate:** in `tests/test_shipped.py`: `install.sh` contains no `cut -d= -f2` that is not `-f2-`, and
contains exactly one `envget()` definition.
**verify:** on `pai-clean6`, `printf 'DATA_DIR="/tmp/x"\n' >> .env` then re-run `install.sh` on a machine
with a stale volume — it must refuse.
**could break:** `:448` and `:500` compute `PORT` and are on the critical path. Read both before touching.
**size:** half a day, because of what is on that path.
**release:** yes — installer change, so `make ship` and a fresh-install rehearsal.

---

# §7 · Consolidation — optional, per item

## PR 27 · one function for the same distance, five times in SQL
**closes:** F17 · **lands after `docs/SPEC_custody.md` is accepted** — the five SQL sites are pack rules
**touches:** `init.sql`, `packs/nearby/rules.yml:37`, `:69`, `:93`, `packs/trust/rules.yml:127`,
`app/main.py:703`
**the change:** `grep -rn "111_320\|111320"` finds 20 lines across 10 files, up from 11 when the first
review counted. The five **SQL** copies are the same four-line
`sqrt(power((lat-current_setting(…))*111320,2) + power(…*cos(radians(…)),2))` pasted five times, and a pack
author writing a sixth has nothing to copy from but another pack. One
`CREATE OR REPLACE FUNCTION planetai_metres(float,float,float,float) RETURNS float IMMUTABLE LANGUAGE sql`
in `init.sql`, and each site shrinks from four lines to one. The two Python **functions** in `sources.py`
stay — they are in the do-not-touch list.
**the gate:** `make lint`'s existing `39 rules and cells check out against init.sql` — the new function
must be visible to `tools/check_rules.py`'s sqlglot schema, which is the gate that fails if it is not.
**verify:** on `pai-clean`, `make lint`, then
`psql -c "select round(planetai_metres(-8.8271,115.157,-8.8281,115.157))"` → `111`.
**could break:** `index.run_ro` runs rules as `planetai_ro`, which needs `EXECUTE` — default for `PUBLIC` on
functions, so nothing to grant. Verify it anyway on a node whose role predates the change.
**size:** half a day.
**release:** no. It is a schema addition, so it needs `update.sh`'s idempotent apply to have run — which is
why it is late.

## PR 28 · the container facing strangers stops running as root
**closes:** F18, first half only
**touches:** `app/Dockerfile.reticulum`, `docker-compose.yml` (the reticulum service)
**the change:** all six containers run as root; no `USER` in either Dockerfile and no `user:` in any
service. Do `reticulum` and only `reticulum`: its only writable path is a named volume, so `USER 1000:1000`
there is genuinely one line, and it is the container that terminates untrusted traffic from strangers on a
Reticulum network. `app` needs `install.sh:324`'s `mkdir -p` to chown the bind-mounted `./out`,
`./backups` and `./exports` first, which is a separate PR and not this one; `db`, `mosquitto` and `ipfs`
drop privileges in their own images and should be left alone.
**the gate:** in `tests/test_shipped.py`, beside the container assertions:
`docker compose config` shows `user: "1000:1000"` on `reticulum`.
**verify:** on `pai-clean` with the profile on, `docker compose exec reticulum id -u` → `1000`, and
`planetai reticulum` still prints an LXMF address.
**could break:** the reticulum named volume's existing files are root-owned on a node that has already run
it; the PR needs a one-line `chown` in the entrypoint or a documented `docker volume rm`. Say which in the
CHANGELOG.
**size:** half a day.
**release:** no.

---

# Part 3 · Decisions

## Taken (Tomas, 10 September) — recorded, not re-argued

**1 · `POST /actions` stays open on loopback; a session token is required once `SHARE_LEVEL != off`.**
*Cost of the answer given:* none in this plan. F10 was the PR that would have changed, and it is reserved
for prompt A, which implements exactly this. The dashboard's "I did this" button and `planetai act` keep
working with no token at `SHARE_LEVEL=off`, so PR 5's one-clause Cancel fix is the whole of what ρ's
integrity needs from this plan. What it does mean: the one-per-alert 409 cap the first review proposed as
"the smallest honest fix now" is **not** needed and should not be built — a session token above `off` and a
dialog that respects Cancel cover it, and a 409 would break a household legitimately recording two people
acting on one alert.

**3 · `GET /readings` and `/history` stay unauthenticated at `SHARE_LEVEL=off`, and are on a read-only
allowlist at `SHARE_LEVEL=open`.** *Cost of the answer given:* none in this plan; prompt A owns the
allowlist. One consequence for PR 15: `GET /provenance` is a new unauthenticated read route, so it goes on
that allowlist. Add the line; do not re-open the question.

**A new setting `SHARE_LEVEL` exists in intent:** `off` (today's loopback) | `open` (LAN bind plus the read
allowlist), with `cell` and `means` reserved, default `off`. Every route this plan adds or touches must say
which level it answers at. Prompt A defines it; this plan consumes it.

## Owed — and one of them blocks a PR

**Custody outranks both. `local` (geography, inside `LOCAL_RADIUS_M`) is not custody
(`kind IN ('own','child')` rolls up; peer, model, external and nearby never do).** Today `local = FALSE` is
simultaneously why a community node can never say `live` about its children and the guard that keeps a
stranger's node out of the Index. **Not designed here** — a separate session writes
`docs/SPEC_custody.md`, and touches only that file, `docs/decisions/` and `tests/test_custody.py`.
**No PR in this plan changes the meaning of `s.local`.** The PRs that read it and therefore land after
`SPEC_custody` is accepted: **PR 4** (both air-quality cells filter `s.local`), **PR 14** (`index._buckets`
at `index.py:55-56`, the honesty check every `live` claim passes through), **PR 27** (the five SQL sites are
pack rules), and **F6's `kind` field** in PR 3 — that one is the export's shape, so if `SPEC_custody`
changes what `kind` may contain, PR 3's assert changes with it. Nothing here touches
`push_aggregates()`, `receive_aggregates()` or `cells.yml`'s *semantics*; PR 4 edits two cell keys, not
what a cell means. Tier vocabulary is settled: `governance.tier` derives from `NODE_SCALE`.

**2 · May pack thresholds be settings, and how does `check_docs.py`'s README-quotes-the-number gate
survive?** *Blocks PR 13, and nothing else.* The two answers cost the same to build and differ in what they
promise. **Settings:** two lines in `db()`, one per rule, and the gate becomes "the README quotes the
*default*" — which means the number lives in two places (the SQL's `current_setting` default and the
README) where today it lives in one. **No:** the heat pack stays calibrated to one street in Bali, and every
node outside a tropical climate inherits a floor that is wrong for it, which is a wrong answer sent to a
household. My reading of the tree is that the second cost is the larger one and that the two-place problem
is answerable — put the default in `.env.example` and have the gate assert `.env.example`, the SQL and the
README all agree, which is three places compared but one source. That is a recommendation, not a decision.

**4 · Where does the dashboard layout live — node only, or browser too?** *Blocks nothing, and the code has
already answered it without anyone choosing.* `loadLayout` (`index.html:1016`) reads `UI_LAYOUT` from the
node and falls back to `localStorage` only when the node's copy is empty; `layoutSave` (`:1041-1046`) writes
both and toasts honestly about which one it managed. So today it is **both, with the node winning, and a
per-browser fallback for an unlocked screen** — which is a defensible design nobody wrote down. The
decision owed is therefore narrower than it looks: ratify that, or drop the `localStorage` half. PR 5 fixes
`layoutReset` to match whichever it is; if the answer is "node only", PR 5 gets two lines shorter.

**5 · New, from the second pass: may a pack contribute a `Governance|*` cell?** *Blocks PR 14.* Reserving
the prefix for the core's ρ is two lines and closes the collision, but `open-data-health` exists precisely
to contribute a governance metric about a city's open-data portal, and that is a real Index cell. The
options are a sub-key (`Governance|City|portal-freshness`, if the Observations base permits it), or moving
ρ to its own key and leaving `Governance|<scale>` to packs. The duplicate keys **within** a single pack
(PR 4) need no decision and go first regardless.

---

# Handoff — for the session that executes PR 1

Work on **`pai-clean`** for everything except `install.sh`, `update.sh` and `bundle.sh`, which go on
**`pai-clean6`**. Both are Lima VMs; `pai-clean` currently runs a node built from `4f96a38` with 6,216
readings and the reproduction artefacts from the second pass still in it — that is fine, and useful. It is
arm64 with 3 GB, so `tools/preflight.sh` exits 1 there by design; do not chase that.

PR 1 is two commits at most: `tests/all` plus the `Makefile` change, then `lint.yml`. After each, run
`make lint && make test` locally and read the **counts**, not the exit code — the whole point of the runner
is that a skip is visible. `make lint` on this tree prints `- requirements resolve skipped (venv failed)`
and exits 0; when your runner is right, that line fails the build or appears on a declared expected-skip
list with a reason beside it.

**Then push, and expect red.** Twenty-six suites have never all run on a clean amd64 runner. `test_earth.py`
imports `numpy`, `tests/trustdb.py` imports `duckdb`, `test_ground.py` may want `h3`, and some suite will
assume a file only a developer's machine has. That red build is the deliverable: it is the first honest
statement this repository has ever made about its own tests, and every one of the 27 PRs below depends on
it. Fix the runner's environment until it is green, and do not fix any *finding* in the same PR — a green
build that arrived by editing an assertion is worse than the red one.

Do not start PR 2 until CI is green on `main`.
