# Bring your own agent
<!-- checked: v0.80.10 -->

An agent is a guest on the machine, never a part of it. It can read everything the node knows and help the
person in front of it operate the node; it drafts, and a person dispatches. The architecture puts it in one
line: "Agents *draft, never dispatch*; every dispatch is a human approval written to a ledger", and its
refusals include "No agent dispatches without a human row in `actions`." A node with an agent on it can be
installed, diagnosed and asked about in plain language. The loop still closes only when a person says what
they did.

The repository is written for that. `AGENTS.md` at its root is the front door: its first section is a table
that routes an agent to one of eight skills, and the rest of it is what an agent must not break. `llms.txt`
indexes every document for an agent arriving from outside. `make lint` fails if a skill names a command or a
path that does not exist.

Paste this to your agent and nothing else:

> You are helping me with a PLANETAI node — an open-source program that turns a spare computer in my home or
> lab into a hyperlocal environmental monitor. Start by reading
> https://raw.githubusercontent.com/fabcity/planetai-node/main/AGENTS.md — its first section is a table
> that routes you to the right skill for what I am asking, and the rest of it is what you must not break.
> Read that skill before you tell me to run anything. Never ask me for the contents of my `.env` file, and
> never suggest exposing the node to the internet; the answer to reaching it from elsewhere is Tailscale.

## Connect Claude Desktop over the tailnet

1. **Put the node on your tailnet.** On the node, `planetai mesh`. It says that afterwards "the node is
   reachable by name from any of your devices, wherever they are, with no ports opened on any router." The
   name is recorded as `MESH_NAME`.
2. **Get the snippet.** On the node, `planetai agent`. It prints the twenty tools by class (read, act,
   admin), the address on this machine (`http://localhost:8080/mcp`) and from the tailnet
   (`http://<MESH_NAME>:8080/mcp`), the header every call must carry, `Authorization: Bearer <ADMIN_TOKEN>`
   with the real token in it, and a ready-made block for
   `mcp.json` or `claude_desktop_config.json`:

   ```json
   {"mcpServers": {"planetai-bayu-ungasan": {"type": "http",
     "url": "http://bayu-ungasan:8080/mcp",
     "headers": {"Authorization": "Bearer <ADMIN_TOKEN>", "X-Agent": "tomas-claude"}}}}
   ```

   Put it into Claude Desktop's configuration on a machine that is on the same tailnet. The token in it is
   the admin token: treat the file like a password.
3. **Tell the agent its name.** The audit trail records the name passed in each write tool's `agent`
   argument, not the `X-Agent` header in the snippet. Say it once: "your name for this node is
   tomas-claude; pass it as `agent` on every write." Nothing answers yet: the name first comes back as
   `"by": "tomas-claude"` in the answer to the first write (step 5). A write that leaves it out is recorded
   as `agent`, and the ledger then cannot say which agent it was.
4. **Ask for status.** "Call `health_check`, then `status`." You should get back `ok` and a list of checks,
   each failing one with its fix, then the node's name, version, last poll, per-loop errors and ρ. The agent
   can now read the node.
5. **Ask it to record an act.** "I closed the north windows about alert 361." The agent calls `act` with
   `alert_id` 361, your words as `note` and its name as `agent`, and the tool answers
   `{"recorded": true, "alert_id": 361, "by": "tomas-claude"}`. Asked to record an act with no words, or with
   `acted`, `done` or `ok`, the tool refuses and tells the agent to ask you what you did. On a node set to
   `DECISION_REQUIRED=1` it is refused with 409 until somebody records a decision on the dashboard.
6. **Find the row.** On the dashboard, Act → "What was decided, and by whom" now shows `tomas-claude` with
   `acted` at the top. The `alerts` tool shows the alert's `acted_at` filled in. The row is in `actions`,
   written because a person said it happened, and it counts in ρ.

The same node answers Claude Code, Codex and any client that speaks MCP over HTTP; [MCP](mcp.md) has the
other clients and every tool.

## The eight skills

| the person says | skill | what it makes the agent do |
|---|---|---|
| "help me install this", "will it run on my old laptop?" | `skills/setup-node` | Run the preflight first and read its exit code; never continue past exit 2. Install with the one line or `planetai setup --answers`. Then Telegram, the test alert (the only end-to-end proof), the dashboard, the doctor. Never a machine that sleeps, never print `.env`, never tune a threshold during setup, never pip on the host. |
| "it stopped working", "no alerts since Tuesday", here is a log | `skills/troubleshoot-node` | Ask for exactly `planetai doctor --json`, `status --json` and twenty lines of logs; `sensors --json` if it is a sensor. Never `.env`; if one arrives, tell them to revoke the bot token. It may read, restart, update, back up; it may not change a threshold, record an action, move the database or edit `.env` without consent. "A node that is quiet because you raised its threshold is lying." |
| "connect this to Claude / Codex", "reach it from outside" | `skills/connect-agent` | Get the URL, token and snippet from `planetai agent`. Tailscale, never a port forward, ngrok or a public reverse proxy. Name yourself in every write's `agent` argument. Call `health_check` first, then `status`. |
| "put our city on the Fab City Index" | `skills/publish-to-index` | Establish the tier first: one node per pilot writes, a home node never does. `planetai cells --json`; the state must be honest. The writer lives with the Index and needs a per-pilot token issued by hand. See [Federation](federation.md). |
| "I want a pack for my city", "share our pack" | `skills/write-a-pack` | Decide the tier first: a pack for one place is wild, in its own repository, never a fork of this one. Start from a core pack of the same kind; `id` equals the folder; keys under `secrets:`, never a value. Test with `tools/check_rules.py` and `planetai packs` on the person's node, then list it at fabcity/planetai-wild-packs from their account. See [Packs](packs.md). |
| you are about to change this repository | `skills/preflight` | `tools/session.sh preflight` first. Your own worktree, your own branch; never the one holding `main`. |
| you are cutting a release | `skills/release-docs` | Re-read every page of this site against the code, fix what changed, and move each page's checked stamp to the release; `make lint` refuses the release until every page is done. |
| you are about to end a session that changed this repository | `skills/land` | `tools/session.sh land`. Nothing exists only on this machine, and the gates ran, not were assumed. |

The first four are for an agent operating a node, the fifth for one writing a pack with its author, and the last
three for an agent changing the code. The first
four end the same way: when a document and the skill disagree, the document wins and the skill has a bug.

## What each tool is allowed to be

Every one of the twenty MCP tools has a class in `app/tool_classes.py`, and `planetai agent` prints them:

| class | what it may do | tools |
|---|---|---|
| `read` | ask the node a question; nothing changes | `status`, `health_check`, `sensors`, `context`, `readings`, `report_latest`, `report_bundle`, `history`, `alerts`, `settings_get`, `packs`, `cells`, `issues`, `series`, `export_day` |
| `act` | record that a person did something, in their own words | `act` |
| `admin` | change the node, run code on it, or make it speak to the household unprompted | `settings_set`, `run_pack_script`, `maintenance`, `report_now` |

A person driving an agent over the tailnet gets all twenty, because somebody is reading what it proposes. The
model running unattended on the node gets `read` and `act` only.

`run_pack_script` runs every script of a core pack, but a wild pack's script only when that pack's `pack.yaml` lists it
under `agent_scripts:`. A wild pack can keep something off the readings on purpose, a camera's motion log for one, and
the refusal tells the agent to ask the person to run it from the node's terminal with `planetai run`.

## Two ways in

**MCP**, from this machine or anywhere on the tailnet: `http://<node>:8080/mcp`, header `Authorization:
Bearer <ADMIN_TOKEN>`. Start with `health_check`; every failing check names its fix.

**A shell on the node**, for what needs Docker or git:

```bash
planetai status --json      planetai doctor --json      planetai sensors --json      planetai cells --json
planetai report             planetai report last        planetai report every <h>   planetai report at <h>
planetai update             planetai backup             planetai restart             planetai logs
planetai setup --answers node.json
```

The `maintenance` MCP tool hands these back as commands with an explanation, because the container has no
Docker and no git. An agent with no shell tells the person which to run.

## A local model may already be running

`planetai agent local` puts Ollama on the node and a loop that answers the household on Telegram. It
downloads no model: it prints the recommendation for the machine's memory, `qwen3.5:4b` (3.4 GB) or
`qwen3.5:9b` (6.6 GB) at 16 GB and up, and `planetai agent local pull <tag>` fetches it. `docs/MODELS.md` is
the catalogue, and its first sentence is "A node needs none of this." That model gets 16 of the 20 tools, the
`read` and `act` ones, and appears in the audit trail as `local-model/<rung>`. A remote agent is not alone on
the node: read the alerts and the actions before acting, and do not undo what the household's own model did
without asking. See [The bot](bot.md).

`actions` also holds `decided` rows, written from the dashboard's Decide card. A decision records what
somebody said they would do and moves nothing: it closes no alert and is not in ρ. No MCP tool writes one.
The answers to an alert event (Done, Not now, Doesn't fit; `event_id`, no `alert_id`) are rows there too, and no MCP
tool writes one of those either.

## Invariants an agent must not break

- Raw readings stay on this machine. Exports and aggregates travel; rows never do.
- `.env` holds secrets. Never print it, never paste it, never commit it. A log containing
  `api.telegram.org/bot` is a leak.
- The database lives on a local disk. Never a network mount. Backups are how data reaches a NAS.
- A model or a portal is `partial`, whatever its quality. `live` means measured here.
- Alerts say what to do in one sentence and name the threshold's source. Do not add alerts a household would
  ignore.
- Nothing runs pip on the host. The CLI runs on Apple's Python 3.9 with the standard library only.
- The dashboard names no metric. Issues are declared in `app/issues/*.yml`, ordered by `NODE_ISSUES`, served
  at `GET /issues`. The node computes; the page draws.
- Do not put the node's database on IPFS. Only the daily export goes to the commons.
- Peers never roll up, and never drive an alert or a report line. Custody, a generated column
  (`kind='child' OR (local AND kind<>'peer')`), is the only thing a cell may count.
- State is never upgraded by aggregation. A parent's cell is `partial` if any input was.
- Exact place never leaves; a coarse cell may, and says how coarse. The Reticulum announce is an H3 cell
  never finer than resolution 6, roughly 3 km across.
- Exactly one node per pilot writes to the Index's spine.
- **`act` needs the person's own words.** It has no default note and refuses a placeholder. ρ is the share of
  act-level alerts a human answered, and a row written without anything a human said is a model measuring
  itself. If they did not tell you what they did, ask.

## Reading the node well

`status.errors` is per loop: a key present means that loop failed on its last run. `sensors[].local` means
the person's own **and** at this node. "Outside" means their own outdoor sensors, else the three nearest
public references, else the model, the same order everywhere. `cells[].state` is provenance: `live` is
measured here, `partial` is derived, modelled or not yet backed by enough data, and a cell with no source is
absent. Do not fill what cannot be measured.

`AGENTS.md` sets the tone: "Plain sentences. One at a time. Say what you know, say what you do not. The
person is not a user; they live here."

## Where this leads

[MCP](mcp.md) lists every tool with its arguments and what it records. [The bot](bot.md) is the model that
lives on the node and answers the household on Telegram.
