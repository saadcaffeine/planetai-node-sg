# Prompt A · share level, and the two leaks

**Branch:** `share-level-and-the-two-leaks` · **release:** v0.43 · **written against** `4f96a38`, 10 September 2026.

This is one pull request. It lands **before** PR 1 of `docs/archive/plans/IMPROVEMENT_PLAN_2026-09.md`, and it is the
only PR that may touch `app/main.py` until PR 6 — from PR 1 onward the improvement plan owns that file and
you are the exception. Do not do anything the plan lists; do not do anything this prompt does not list.

## What you own

Files, and nobody else touches them while you work:

- `app/main.py` — `GET /health`, `GET /sensors`, `GET /place/geojson`, `GET /settings`, `POST /actions`,
  and one new middleware beside `_mcp_auth` (`:555-565`)
- `app/settings.py` — the `PUBLIC` allowlist (`:79-82`) and two new keys
- `docker-compose.yml` — the `app` service's `ports:` line (`:38`) **only if** decision A2 below says so
- `bin/planetai` — `cmd_ui` (`:968-991`), one line
- `tests/test_share.py` — new
- `tools/check_theme.py` — new, report-only
- `docs/design/planetai-theme.css` — new, a committed fixture
- `SPEC.md` §4 (`:52-54`)

**Do not touch:** the dashboard's `:root` CSS token block or anything else under `docs/design/` (another
session owns those, and `check_theme.py` is deliberately report-only so you cannot collide). Any pack.
`app/index.py`. `Makefile` or `.github/workflows/` (that is PR 1). `tests/all` (does not exist yet, also
PR 1). And nothing in the improvement plan's "do not touch" list.

## Findings this closes

F10, F11, A7, A12, and SPEC's argument-from-absence. Full text and the transcripts:
`docs/archive/reviews/CODE_REVIEW_2026-09.md` (F10, F11) and
`docs/archive/reviews/CODE_REVIEW_2026-09-10_second_pass.md` (A7, A12). Do not re-derive them; they were
reproduced on `pai-clean` and the lines are current.

---

## What is actually true today — three corrections to the brief

Read these before you design anything. Each one was checked on the tree and on a running node, and each
changes what this PR should do.

**1 · The node is not on loopback. It never has been.** `docker-compose.yml:38` is

```yaml
ports: ["${APP_PORT:-8080}:8080"]     # host port; change APP_PORT in .env if 8080 is taken
```

— all interfaces. Two lines above, `db` is `ports: ["127.0.0.1:5432:5432"]`, and `ipfs` uses
`127.0.0.1:5001` and `127.0.0.1:8085`, so the loopback form exists in this file and the app does not use
it. `SPEC.md:54` says so too: *"Nothing listens on the network except `app:8080` (LAN)."*

So "`SHARE_LEVEL=off` (today's loopback)" describes a state that does not exist. Every unauthenticated
read is answerable by anyone on the WiFi **right now** — which is what makes A7 and A12 live rather than
theoretical.

**2 · Changing the bind to loopback would break four things, one of them the backup.** Node #1's NAS pulls
dumps hourly from `http://192.168.4.190:8081/backups` with the read-only `BACKUP_TOKEN`. That is the only
off-machine copy of readings that exist nowhere else. A loopback bind also takes out: any phone or wall
screen on the house WiFi, Home Assistant on another machine, and `planetai agent`'s MCP surface, which
`AGENTS.md` documents as reachable *"from anywhere on the tailnet"*. Shipping that as the **default** would
break every existing node on update.

**Therefore `SHARE_LEVEL` governs what an unauthenticated request may read, not where the socket binds.**
A request carrying a valid token is unchanged at every level, from anywhere — the NAS, MCP, an agent, Home
Assistant. That is the whole reason this can default to `off` safely.

**3 · The stale argument is in §4, not §6.** `SPEC.md:54` ends:

> No mesh, no auth, no TLS: because no packet crosses a network boundary yet. The moment node #2 exists on
> another network, §6 applies.

And §6's first table row already reads `~~node #2 exists on a different network~~ **fired, v0.7**`. So §6
is correct and already struck through; **§4 is the sentence arguing from an absence that ended two releases
ago.** Rewrite §4. Leave §6 alone except to add this PR's own row.

---

## The contract

One new setting, `SHARE_LEVEL`, in `app/settings.py`'s `RUNTIME` dict, group `node`, default `off`:

| level | what an **unauthenticated** request gets |
|---|---|
| `off` *(default)* | from **loopback**: everything it gets today. From anywhere else: `/health` (reduced, see below), `/`, `/ui`, `/static/*`, and `GET /settings` limited to `UI_LAYOUT`. Everything else 403 with one sentence naming the setting. |
| `open` | the **read allowlist** below, from anywhere. Writes still need a token. |

`cell` and `means` are reserved names and are **not implemented**: put them in the help text and in `CHOICES`
as refused values with a sentence saying what they will mean, so a node cannot be set to a level that does
nothing. A token-bearing request bypasses the whole middleware at every level.

**The read allowlist at `open`** — this is what a wall screen on the house WiFi needs, taken from the
twenty-one endpoints the dashboard actually fetches (`grep -oE "(api|fetch)\('/[a-z0-9/._{}-]+"
app/static/index.html`):

```
/  /ui  /static/*  /health  /stats  /sensors  /observations  /alerts  /series  /sparks
/rho  /cells  /packs  /trust  /nearby  /forecast  /earth  /report/latest  /readings  /history
/export  /exports  /exports/*  /settings
```

**Deliberately not on it**, and say so in the docstring of each:

- **`/place/geojson`** — the exact building footprints and roads within `PLACE_RADIUS_M` of the address.
  This is the doorway A12 is about, drawn. Loopback and token only, at every level. The dashboard's plan
  card is therefore blank on an unauthenticated LAN screen; make it say why, in the shape the dashboard
  already uses for an absent source, not by throwing.
- **`/backups`, `/backups/*`** — already `_pull_ok`; unchanged, and the middleware must not shadow it.
- **`/mcp`** — already admin-only via `_mcp_auth`; the new middleware runs after it and must not double-check.
- **`/settings/raw`** — admin only, returns the Telegram and AI keys unmasked. Never on any allowlist.

## The work

**1 · The middleware.** One `@app.middleware("http")` beside `_mcp_auth` at `app/main.py:555`. In order:
token present and valid → pass; path is `/mcp*` → pass (its own middleware has already decided);
`request.client.host` is loopback → pass; then the level's allowlist. A 403 body is one sentence naming
`SHARE_LEVEL` and how to change it, because the person reading it is usually the household. Reuse
`_bearer_ok` (`:1054`) — it is constant-time and takes `*tokens`, which is why the session token below is
three characters of work.

**2 · `GET /health` — A12.** Round `lat` and `lon` to 3 decimals, always, for every caller.
`/export` (`:838`) already does exactly this and `round(x, 3)` is 110 m, which changes no answer any
consumer computes. See decision A1 for the node name.

**3 · `GET /sensors` — A7.** Stop `SELECT *` (`:606-608`). Name the columns. For a caller that is neither
loopback nor token-bearing: round each sensor's `lat`/`lon` to 3 decimals, and filter `meta` to a
provenance allowlist — `licence`, `attribution`, `model`, `dataset`, `network`, `note`, `corrected` — which
drops `host`, `firmware`, `mesh_node`, `gateway`, `channel`, `root_topic` and `topic`. Confirmed on
`pai-clean` that an AirGradient row otherwise hands out
`{"host": "airgradient_84fce6.local", "model": "I-9PSL", "firmware": "3.1.9"}` with a room name and five
decimals of position. `SELECT *` is also why this recurs: any column added to `sensors` is published the
day it lands, so the named list is the fix, not the filter alone.

**4 · `POST /actions` — F10, decision 1 (taken).** Open on loopback, unchanged. Off loopback it requires a
token once `SHARE_LEVEL != off`. Use a **second, weaker token** rather than the admin one: a new
`ACT_TOKEN` in `RUNTIME`, checked with `_bearer_ok(auth, ACT_TOKEN, ADMIN_TOKEN)`, printed by
`planetai ui` beside the admin token, so a household member can be given the ability to close a loop
without being given the key to `/settings/raw`. That is what makes decision 1's "anyone in the house can
close a loop" survive a LAN bind. The dashboard's Unlock panel gets one more field.

Do **not** add the one-per-alert 409 cap the first review proposed as an interim: decision 1 supersedes it,
and it would break two people legitimately recording that they both acted.

**5 · `GET /place/geojson` — F11 and the allowlist.** Off the allowlist as above, and while you are in that
signature, bound the one unguarded numeric parameter in the API:
`tolerance: float = Query(0.00002, ge=0.000001, le=0.01)` (`:846`). `?tolerance=0` currently skips
`ST_SimplifyPreserveTopology` and returns the unsimplified kilometre against a docstring promising "a few
hundred KB". The dashboard never passes it (`:960` fetches bare).

**6 · The `PUBLIC` settings allowlist** (`app/settings.py:79-82`). It already holds — verified: 47 rows
returned unauthenticated, 28 with a value, every one of them in `PUBLIC`, and `AIRGRADIENT_HOSTS`,
`EE_KEY_FILE`, `AGENT_REMOTE_URL`, `AGENT_ONLINE_URL`, `MESH_GATEWAY_NODE_NUM` and `BACKUP_TOKEN` all read
`•••• set`. Two changes only: at `off`, a non-loopback unauthenticated caller sees `UI_LAYOUT` and nothing
else (the docstring at `:1197-1200` already promises the layout read keeps working for every screen in the
house, and it must); and `SHARE_LEVEL` itself joins `PUBLIC`, because a screen that is being refused needs
to be able to say why. `ACT_TOKEN` is a secret and joins the masked set.

**7 · `SPEC.md` §4.** Rewrite the last sentence. It should say what is true: the app listens on the LAN, the
database does not, a token guards every write and every secret read, `SHARE_LEVEL` decides what an
unauthenticated reader on that LAN may see, and the boundary §4 used to argue did not exist was crossed in
v0.7 — with the pointer to §6's struck-through row rather than a second copy of the claim. Add one row to
§6's table for this PR, naming the trigger that fired.

**8 · `tools/check_theme.py` and `docs/design/planetai-theme.css`.** Unrelated to the leaks and bundled here
because it is cheap and because it must exist before the design session edits the token block. Extract the
`:root` custom-property block from `app/static/index.html` into `docs/design/planetai-theme.css` verbatim as
a committed fixture, and write a script that reports the diff between the two. **Report-only: it prints and
exits 0**, and it is not in `make lint`. It exists so that when the design session changes a token, the
change is visible as a diff in a review rather than discovered on a wall screen. Say that in its docstring,
and say that turning it into a failing gate is the design session's call, not yours.

## The gate

`tests/test_share.py`, new, no network, no database — the shape `tests/test_shipped.py` uses (read the
file, assert on it) plus FastAPI's `TestClient` where a request is needed. It must fail on the tree before
this PR. Minimum:

- at `SHARE_LEVEL=off`, a non-loopback unauthenticated `GET /sensors` is 403, and the same request with a
  valid `ADMIN_TOKEN` is 200
- at `open`, `GET /sensors` unauthenticated returns rows whose `meta` contains no `host`, `firmware`,
  `mesh_node`, `gateway`, `channel`, `root_topic` or `topic`, and whose `lat`/`lon` have at most 3 decimals
- at every level, `GET /health` unauthenticated has `lat`/`lon` with at most 3 decimals
- at every level, `/place/geojson` and `/settings/raw` unauthenticated from a non-loopback address are 403
- at `open`, `POST /actions` unauthenticated is 403 and with `ACT_TOKEN` is 200; at `off` from loopback it
  is 200 with no token
- one static assert: `"SELECT *" not in` the source of `sensors_()`, so the next column added to `sensors`
  cannot publish itself
- `tolerance` carries `ge=` and `le=` — the AST walk from F11, which today finds exactly one unguarded
  numeric parameter in 44 routes

Then the existing gates: `make lint && make test` before every commit. `tools/check_docs.py` will want
`SHARE_LEVEL` and `ACT_TOKEN` in `.env.example` and any doc that names them; that is the gate working.

## Verify, on pai-clean

The VM already runs a node built from `4f96a38` (`~/planetai`, `lima-pai-clean`, port 8080 forwarded to the
Mac's loopback). It has the second pass's reproduction artefacts in it, which is useful: an act-level alert
to press, and a sensor row shaped like an AirGradient's.

```bash
limactl start pai-clean
limactl shell pai-clean -- bash -lc 'cd ~/planetai && docker compose up -d --build'
# from the Mac, which reaches the VM's 8080 as a non-loopback client of the container:
curl -s localhost:8080/sensors | python3 -m json.tool | grep -E '"host"|"lat"'      # expect nothing, and 3 dp
curl -s localhost:8080/health  | python3 -c 'import sys,json;d=json.load(sys.stdin);print(d["lat"],d["lon"])'
curl -s -o /dev/null -w '%{http_code}\n' localhost:8080/place/geojson               # expect 403
curl -s -X PUT localhost:8080/settings -H "Authorization: Bearer $TOK" \
     -H 'content-type: application/json' -d '{"SHARE_LEVEL":"open"}'
curl -s -o /dev/null -w '%{http_code}\n' localhost:8080/stats                        # expect 200
```

Then open `http://127.0.0.1:8080/` in a browser and check the wall: every card draws except the plan, and
the plan card says why rather than being blank. That last check is the one that matters — the whole point
of the allowlist is that the house keeps its dashboard.

Do **not** verify on node #1. It is a git checkout on main and will take this the moment it pulls; let the
tag reach it, not the branch.

## Two decisions this prompt needs before you write the middleware

**A1 · Does `/health` keep the node's name?** The brief says "coordinates to 3 dp, no node name". The
coordinates are not in question. The name is: `/export` (`app/main.py:837`) already returns `"node": NODE`
in the daily CC-BY export **by design**, and the dashboard prints `Node ${h.node}` in its footer
(`index.html:640`). So removing it from `/health` hides a string that is deliberately public elsewhere and
costs the wall screen its footer. My reading: **keep the name, round the coordinates**, and if the name is
genuinely sensitive then it has to come out of `/export` too and that is a different PR. Ask Tomas; it is
one line either way.

**A2 · Does anything change the bind?** This prompt says no, for the four reasons in correction 2 above.
If Tomas wants a literal loopback option, it is a third level (`SHARE_LEVEL=none`) that a node opts into
knowing it loses the NAS pull, the phone, Home Assistant and MCP — never a default. Do not implement it in
this PR either way.

## Release

Yes: **tag v0.43** and `make ship`, with the fresh-install rehearsal on `pai-clean6`
(`curl -fsSL planetai.fab.city/install | bash`, then `planetai update` twice). The CHANGELOG entry goes
above v0.42 and should lead with what a household notices — that a stranger on the WiFi can no longer read
the house's sensor hostnames or the shape of its building — and then say what to set to get the wall screen
working on the house network again, because that is the question the first person to update will have.

Node #1 takes this on its next pull. Node #2 does **not** update at v0.43: S3 is still open, and
`update.sh` will tell Lucas it succeeded when it has not. That is PR 16 of the improvement plan.
