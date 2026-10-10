# Start here: what the person in front of you is asking for

Eight situations bring somebody to this repository with an agent. Find theirs in the first column, read
that skill, then do the third column. If none of them fits, read the rest of this file — it is written
for an agent already inside a running node.

| the person says | read this skill | then do this |
|---|---|---|
| "help me install this", "I want a node", "will it run on my old laptop?" | `skills/setup-node/SKILL.md` | Run the preflight first and read its exit code. Never continue past exit 2. |
| "it stopped working", "no alerts since Tuesday", here is a log | `skills/troubleshoot-node/SKILL.md` | Ask for `planetai doctor --json`, `status --json` and twenty lines of logs. Never `.env`. |
| "connect this to Claude / Codex / my agent", "how do I reach it from outside?" | `skills/connect-agent/SKILL.md` | Get the URL and token from `planetai agent`. Tailscale, never a port forward. |
| "put our city on the Fab City Index", "how do we publish cells?" | `skills/publish-to-index/SKILL.md` | Establish the tier first. One node per pilot writes; a home node never does. |
| "I want a pack for my city", "add this sensor / source / threshold", "share our pack" | `skills/write-a-pack/SKILL.md` | A pack for one place is wild: its own repository, listed at fabcity/planetai-wild-packs. Never a fork of this repository, never a folder in `packs/` here. |
| you are about to change this repository — any task, any size | `skills/preflight/SKILL.md` | `tools/session.sh preflight` first. Your own worktree, your own branch; never the one holding `main`. |
| you are cutting a release, or `make lint` says a docs page was "checked against" an older release | `skills/release-docs/SKILL.md` | Re-read every page of the docs site against the code, fix it, then move its `<!-- checked: vX -->` stamp. Never move a stamp on a page you did not read. |
| you are about to end a session that changed this repository | `skills/land/SKILL.md` | `tools/session.sh land`. Nothing exists only on this machine, and the gates ran, not were assumed. |

The skills order the documents; they do not replace them. Everything below is what an agent operating a
node needs to know, and it is the authority.

# For the agent operating this node

You are working on a PLANETAI node: a small computer that connects everything measuring one place, from sensors on the
wall to satellites overhead, decides where it stands, and tells the people there what to do about the air, the heat,
the sea and the land. It is hyperlocal compute and intelligence for distributed production, and its
purpose is fixed: clean air, water and soil for the people and the other living things around it. Raw readings never leave it. Its own measurement is ρ, the share of act-level
alerts somebody answered. Your job is to keep it healthy, useful and truthful. This file is for you; the human docs are in `docs/`.

## A local model may already be running here

`planetai agent local` puts Ollama on the node and a loop (`app/agent_loop.py`) that answers the household on Telegram
using these same tools. It downloads no model: it prints the recommendation for the machine's memory and stops, and
`planetai agent local pull <tag>` fetches one when somebody asks. `docs/MODELS.md` is the catalogue, and its first line
is that a node needs none of it. The loop appears in the audit trail as `local-model/<rung>`.

**That local model gets `read` and `act` only.** It cannot change a setting, run a pack's code, or make the node
message the household by itself — `app/tool_classes.py` is the table and `app/agent_loop.py` derives the allow-list
from it. You, a remote agent driven by a person, have all twenty; the difference is that somebody is reading what you
propose. If you are a remote agent, you are not alone on this node; read `alerts` and the actions before acting, and do
not undo what the person's local model did without asking.

**The dashboard has a pane that asks the same models** (`POST /ask`, `app/ask.py`): the ladder Set up → Model and
`AGENT_PREFER` define for the Telegram bot, and it says on every answer which model answered and where it runs. It is
narrower still: it
runs the `read` tools except `settings_get`, `report_bundle` and `export_day`, through `/mcp` as `dashboard-chat`, and
an `act` or an admin tool it reaches for is not run at all. It becomes a card the person presses. Its context and every
tool result are scrubbed of coordinates, sensor and station names, sensor ids and `meta`, and nothing asked or answered
is kept anywhere, a log line included. If you change `app/ask.py` or `agent_loop.pane`, `tests/test_ask.py` holds you to
all three.

**`act` needs the person's own words.** It has no default `note` and refuses a placeholder. ρ is the share of act-level
alerts a human answered, and a row written without anything a human said is a model measuring itself. If somebody told
you they did a thing, record what they told you. If they did not, ask.

## Two ways in

**MCP**, from anywhere on the tailnet or from this machine: `http://<node>:8080/mcp`, header
`Authorization: Bearer <ADMIN_TOKEN>`. Pass your name in every write tool's `agent` argument so the audit trail knows
who acted (`act` writes it as the action's `actor`, `settings_set` forwards it to the API as `X-Agent`, and
`report_now` and `run_pack_script` record no name; the header on `/mcp` itself is not read). Twenty tools:
`status`, `health_check`, `issues` (how the place is doing, in the household's own words), `sensors`,
`context` (sea, weather, satellite air, land), `readings`, `report_latest`,
`report_now`, `report_bundle`, `history`, `alerts`, `act`, `settings_get`, `settings_set`, `packs`, `cells`, `series`,
`export_day`, `run_pack_script`, `maintenance`. Start with `health_check`; every failing check names its fix.

**A shell on the node**, for what needs Docker or git:

```bash
planetai status --json      planetai doctor --json      planetai sensors --json      planetai cells --json
planetai report             planetai report last        planetai report every <h>   planetai report at <h>
planetai update             planetai backup             planetai restart             planetai logs
planetai packs              planetai packs add <owner>/<repo>[/<folder>][@<ref>]       planetai packs install
planetai setup --answers node.json      # install without a terminal; see the JSON shape in bin/planetai
```

`maintenance` over MCP returns these commands with an explanation. If you have no shell, tell the person which to run.

## Invariants. Do not break these.

- Raw readings stay on this machine. Exports and aggregates travel; rows never do.
- `.env` holds secrets. Never print it, never paste it, never commit it. Logs containing `api.telegram.org/bot` are a leak.
- The database lives on a local disk. Never a network mount. Backups are how data reaches a NAS.
- A model or a portal is `partial`, whatever its quality. `live` means measured here.
- Alerts say what to do in one sentence and name the threshold's source. Do not add alerts a household would ignore.
- Nothing runs pip on the host. The node's Python is Apple's 3.9 with the standard library only. The CLI must stay that way.
- The dashboard names no metric. Issues are declared in `app/issues/*.yml`, ordered by `NODE_ISSUES`, and
  served at `GET /issues`. The node computes; the page draws. A number the page works out for itself is a bug.
- Do not put the node's database on IPFS. Only the daily export goes to the commons.
- **Peers never roll up.** A `kind='peer'` row is display-only: it reaches no Index cell, no custody count, and
  no aggregate pushed to a parent, whatever its coordinates say. Custody is `local OR kind='child'`, it lives in
  `init.sql` as a generated column, and it is the only thing a cell may count.
- **Peers never drive an alert or a report line.** A node may show a neighbour's number and must never act on
  it. The ring in `packs/nearby` compares against peers; it does not alert about them.
- **State is never upgraded by aggregation.** A parent's cell is `partial` if any input was, and `live` needs
  in-custody measurement in the last 24h at the parent's own rung — from at least two sensors, across at least
  two children where there are children. One child reporting is one household's kitchen.
- **Exact place never leaves; a coarse cell may, and says how coarse.** Coordinates, room names, sensor ids and
  a household's own sentences stay on the machine that recorded them. Aggregates carry values and timestamps,
  the event push carries timestamps, and neither carries where. The Reticulum announce is the one thing that
  leaves, as an H3 cell rounded UP to a coarse parent with `res` beside it and a floor of res 6 no settings box
  can go under.
- **Exactly one node per pilot writes to the spine.** A pilot is a city in the Index's `ALLOWED_CITIES`. Every
  other node computes its cells, shows them, and passes them no further.
- When a document and a skill disagree, the document wins and the skill has a bug. Fix the skill, not the doc.

## Changing code

Development happens on a dev machine, not on the node. The node only runs `planetai update`.

A merge is not a release, and nothing reaches a tester without one. `/install` and `/preflight` are
stubs that read the published `node0/get/VERSION`, take the commit it names, and fetch their script
from exactly that commit — so the bootstrap, the preflight check and the node in the tarball all come
from one commit. They used to fetch from main every run, which meant a tester received two versions at
once: on 2026-09-08 a bootstrap that knew about `planetai remove` handed over a v0.41.2-23 node that
did not have it, and the tester was told to type a command their copy did not contain.

So a fix to the installer is not live when it merges. `make released` says whether the site is behind
main; `make ship` rebuilds the tarball, commits it in the site repo and deploys. To hand somebody an
unreleased fix without shipping, `PLANETAI_REF=main` still overrides the pin.

Before any commit: `make lint && make test`. Lint runs every gate that exists because something once shipped broken:
SQL idempotency, compose mounts, CLI snippets as Python 3.9, rules and cells against the schema, docs against the code,
the dashboard's ids, pyflakes, the app import. If you add a gate, break something on purpose first and watch it fail.
Test the file itself, not a copy typed into the test.

Adding a source, a rule or a cell is a pack: `docs/PACKS.md`, in the order `skills/write-a-pack/SKILL.md` gives.
For one place it is a wild pack in its own repository, not a pull request here; `planetai packs add` installs it on a
node and `planetai packs` lists core and wild apart, with any pack it refused under "not loaded". Say in the README
where the thresholds came from and which place they were written for.

## Reading the node

- `status.errors` is per loop. A key present means that loop failed on its last run.
- `sensors[].local` means the person's own **and** at this node; a kit of theirs further than `LOCAL_RADIUS_M` is theirs but not this node's measurement. `indoor` is what the rules use to tell the house from the street.
- `alerts[].acted_at` is null until someone acts. It is the person's note on what they did, not the node's own
  measurement: ask them, record it with `act` in their words, and never invent one.
- "Outside" means: the person's own outdoor sensors, else the three nearest public references, else the model. Same order
  everywhere.
- `cells[].state` is provenance, never a colour: `live` is measured here, `partial` is derived, modelled or not yet backed by enough data, and a cell with no source is absent. Do not fill what cannot be measured.

## Tone

Plain sentences. One at a time. Say what you know, say what you do not. The person is not a user; they live here.
