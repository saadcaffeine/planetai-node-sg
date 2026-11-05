# Bring your own agent
<!-- checked: v0.91.0 -->

An agent is a guest on the machine, never a part of it. It can read everything the node knows and help the person in
front of it install, diagnose and run the node in plain language. It drafts and a person dispatches: no agent
dispatches without a human row in `actions`, and the loop closes only when a person says what they did.

The repository is written for agents. `AGENTS.md` at its root is the front door: its first section is a table that
routes an agent to one of eight skills, and the rest is what an agent must not break. `llms.txt` indexes every
document for an agent arriving from outside, and `make lint` fails if a skill names a command or a path that does not
exist.

Paste this to your agent and nothing else:

> You are helping me with a PLANETAI node, an open-source program that turns a spare computer in my home or lab into
> a hyperlocal environmental monitor. Start by reading
> https://raw.githubusercontent.com/fabcity/planetai-node/main/AGENTS.md. Its first section is a table that routes
> you to the right skill for what I am asking, and the rest of it is what you must not break. Read that skill before
> you tell me to run anything. Never ask me for the contents of my `.env` file, and never suggest exposing the node
> to the internet; to reach it from elsewhere, use Tailscale.

## Connect Claude Desktop over the tailnet

1. **Put the node on your tailnet.** On the node, run `planetai mesh`. When it is done the node is reachable by name
   from any of your devices, with no ports opened on any router, and the name is recorded as `MESH_NAME`.
2. **Get the snippet.** On the node, run `planetai agent`. It prints the twenty-one tools by class (read, act,
   admin), the address on this machine (`http://localhost:8080/mcp`) and on the tailnet
   (`http://<MESH_NAME>:8080/mcp`), the header every call carries, `Authorization: Bearer <ADMIN_TOKEN>` with the real
   token in it, and a block for `mcp.json` or `claude_desktop_config.json`:

   ```json
   {"mcpServers": {"planetai-bayu-ungasan": {"type": "http",
     "url": "http://bayu-ungasan:8080/mcp",
     "headers": {"Authorization": "Bearer <ADMIN_TOKEN>", "X-Agent": "kitchen-claude"}}}}
   ```

   Put it into Claude Desktop's configuration on a machine on the same tailnet, with your agent's name as `X-Agent`.
   The token in it is the admin token, so treat the file like a password.
3. **Tell the agent its name.** The audit trail records the name passed in each write tool's `agent` argument, and
   the `X-Agent` header does not reach it. Say it once: "your name for this node is kitchen-claude; pass it as
   `agent` on every write." A write that leaves it out is recorded as `agent`, and then the ledger cannot say which
   agent it was. You see the name come back in step 5.
4. **Ask for status.** "Call `health_check`, then `status`." You get `ok` and a list of checks, each failing one with
   its fix, then the node's name, version, last poll, per-loop errors and ρ. The agent can read the node.
5. **Ask it to record an act.** "I closed the north windows about alert 361." The agent calls `act` with `alert_id`
   361, your words as `note` and its name as `agent`, and the tool answers
   `{"recorded": true, "alert_id": 361, "by": "kitchen-claude"}`. With no words, or with `acted`, `done` or `ok`, the
   tool refuses and tells the agent to ask you what you did. On a node set to `DECISION_REQUIRED=1` it gets 409 until
   somebody records a decision on the dashboard.
6. **Find the row.** On the dashboard, Data › Ledger (on `?layout=classic`, Act → "What was decided, and by whom")
   shows `kitchen-claude` with `acted` at the top, and the `alerts` tool shows the alert's `acted_at` filled in. The
   row is in `actions` because a person said it happened, and it counts in ρ.

Claude Code, Codex and any client that speaks MCP over HTTP connect the same way; [MCP](mcp.md) has the other clients
and every tool with its class.

## The eight skills

| the person says | skill | what it makes the agent do |
|---|---|---|
| "help me install this", "will it run on my old laptop?" | `skills/setup-node` | Run the preflight first and read its exit code, and never continue past exit 2. Install with the one line or `planetai setup --answers`. Then Telegram, the test alert (the only end-to-end proof), the dashboard, the doctor. Never a machine that sleeps, never print `.env`, never tune a threshold during setup, never pip on the host. |
| "it stopped working", "no alerts since Tuesday", here is a log | `skills/troubleshoot-node` | Ask for exactly `planetai doctor --json`, `status --json` and twenty lines of logs, plus `sensors --json` for a sensor. Never `.env`; if one arrives, tell them to revoke the bot token. It may read, restart, update and back up; it may not change a threshold, record an action, move the database or edit `.env` without consent. |
| "connect this to Claude / Codex", "reach it from outside" | `skills/connect-agent` | Get the URL, token and snippet from `planetai agent`. Tailscale, never a port forward, ngrok or a public reverse proxy. Name yourself in every write's `agent` argument. Call `health_check` first, then `status`. |
| "put our city on the Fab City Index" | `skills/publish-to-index` | Establish the tier first: one node per pilot writes, a home node never does. `planetai cells --json`, and the state must be honest. The writer lives with the Index and needs a per-pilot token issued by hand. See [Federation](federation.md). |
| "I want a pack for my city", "share our pack" | `skills/write-a-pack` | Decide the tier first: a pack for one place is wild, in its own repository, never a fork of this one. Start from a core pack of the same kind; `id` equals the folder; keys go under `secrets:`, never a value. Test with `tools/check_rules.py` and `planetai packs` on the person's node, then list it at fabcity/planetai-wild-packs from their account. See [Packs](packs.md). |
| you are about to change this repository | `skills/preflight` | `tools/session.sh preflight` first. Your own worktree and your own branch, never the one holding `main`. |
| you are cutting a release | `skills/release-docs` | Re-read every page of this site against the code, fix what changed, and move each page's checked stamp to the release; `make lint` refuses the release until every page is done. |
| you are about to end a session that changed this repository | `skills/land` | `tools/session.sh land`: nothing exists only on this machine, and the gates ran. |

The first four are for an agent operating a node, the fifth for one writing a pack with its author, the last three
for one changing the code. When a document and a skill disagree, the document wins and the skill has a bug.

## Two ways in

Over MCP, from this machine or anywhere on the tailnet: `http://<node>:8080/mcp` with the header `Authorization:
Bearer <ADMIN_TOKEN>`. Start with `health_check`, every failing check names its fix. A person driving an agent gets
all twenty-one tools, because somebody reads what it proposes; [MCP](mcp.md) lists them.

A shell on the node, for what needs Docker or git:

```bash
planetai status --json      planetai doctor --json      planetai sensors --json      planetai cells --json
planetai report             planetai report last        planetai report every <h>   planetai report at <h>
planetai update             planetai backup             planetai restart             planetai logs
planetai setup --answers node.json
```

The container has no Docker and no git, so the `maintenance` tool hands these back as commands with an explanation.
An agent with no shell tells the person which one to run.

## A local model may already be running

`planetai agent local` puts Ollama on the node and a loop that answers the household on Telegram. That model gets the
17 `read` and `act` tools and shows up in the audit trail as `local-model/<rung>`. A remote agent is not alone on the
node, so it reads the alerts and the actions before acting, and does not undo what the household's own model did
without asking. See [The bot](bot.md).

`actions` also holds `decided` rows, written from the dashboard's Decide card. A decision records what somebody said
they would do and moves nothing: it closes no alert and is not in ρ. The answers to an alert event (Done, Not now,
Doesn't fit, with an `event_id` and no `alert_id`) are rows there too, and so is a press on a button a pack's rule put
under its alert, with an `alert_id` and a `choice`. No MCP tool writes any of these.

## Invariants an agent must not break

- Raw readings stay on this machine. Exports and aggregates travel, rows never do.
- `.env` holds secrets. Never print it, paste it or commit it. A log containing `api.telegram.org/bot` is a leak.
- The database lives on a local disk, never a network mount. Backups are how data reaches a NAS.
- A model or a portal is `partial`, whatever its quality. `live` means measured here.
- Alerts say what to do in one sentence and name the threshold's source. Do not add alerts a household would ignore.
- Nothing runs pip on the host. The CLI runs on Apple's Python 3.9 with the standard library only.
- The dashboard names no metric. Issues are declared in each pack's `issue.yml`, ordered by `NODE_ISSUES` and served at
  `GET /issues`. The node computes and the page draws.
- Do not put the node's database on IPFS. Only the daily export goes to the commons.
- Peers never roll up, and never drive an alert or a report line. Custody, a generated column
  (`kind='child' OR (local AND kind<>'peer')`), is the only thing a cell may count.
- State is never upgraded by aggregation. A parent's cell is `partial` if any input was.
- Exact place never leaves. A coarse cell may, and says how coarse. The Reticulum announce is an H3 cell never finer
  than resolution 6, roughly 3 km across.
- Exactly one node per pilot writes to the Index's spine.
- `act` needs the person's own words. It has no default note and refuses a placeholder. ρ is the share of act-level
  alerts a human answered, and a row written without anything a human said is a model measuring itself. If they did
  not tell you what they did, ask.

## Reading the node well

`status.errors` is per loop: a key present means that loop failed on its last run. `sensors[].local` means the
person's own and at this node, both. "Outside" means their own outdoor sensors, else the three nearest public
references, else the model, in that order everywhere. `cells[].state` is provenance: `live` is measured here,
`partial` is derived, modelled or not yet backed by enough data, and a cell with no source is absent. Do not fill
what cannot be measured.

The tone `AGENTS.md` asks for: "Plain sentences. One at a time. Say what you know, say what you do not."

## Where this leads

[MCP](mcp.md) lists every tool with its arguments and what it records. [The bot](bot.md) is the model that lives on
the node and answers the household on Telegram.
