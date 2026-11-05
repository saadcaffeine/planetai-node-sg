# MCP server and tools
<!-- checked: v0.91.0 -->

This is the surface an agent holds. Any client that speaks MCP can read what the node read, ask how the place is
doing in the household's own words, and record that somebody acted, in that person's words. Nothing an agent does
through it takes a reading off the machine.

`app/agent.py` mounts it on the API at `/mcp`, streamable HTTP, with twenty-one tools over the node's own endpoints.
The tools call the API back on `127.0.0.1`, so they arrive as loopback; `report_now`, `settings_set`,
`report_bundle` and `learned` also carry the admin token. The same tools serve Claude Desktop or Claude Code on a
laptop across the tailnet, the household's own model on Telegram, the dashboard's ask pane and any other MCP client.

## Connecting

```bash
planetai agent
```

prints the tools by class, the endpoint on this machine (`http://localhost:8080/mcp`) and on the tailnet
(`http://<MESH_NAME>:8080/mcp`, the MagicDNS name `planetai mesh` records), the header every call must carry,
`Authorization: Bearer <ADMIN_TOKEN>`, and a block to paste into a client:

```json
{"mcpServers": {"planetai-bayu-ungasan": {"type": "http",
  "url": "http://bayu-ungasan:8080/mcp",
  "headers": {"Authorization": "Bearer <ADMIN_TOKEN>", "X-Agent": "kitchen-claude"}}}}
```

The `X-Agent` value is only a label, put your agent's own name there. [Bring your own agent](agents.md) goes through
it step by step with Claude Desktop, up to the first row an agent writes.

For Claude Code in a clone of the repository, `.mcp.json` is already there and reads its values from the shell:
`PLANETAI_MCP_URL` (default `http://localhost:8080/mcp`), `PLANETAI_ADMIN_TOKEN` and `PLANETAI_AGENT_NAME`, so
nothing secret is in the file. From anywhere else:

```bash
claude mcp add --transport http planetai "$PLANETAI_MCP_URL" \
  --header "Authorization: Bearer $PLANETAI_ADMIN_TOKEN" --header "X-Agent: $PLANETAI_AGENT_NAME"
```

Cursor does not expand `${VAR:-default}`, so paste the block from `planetai agent` instead. A local Ollama with an
MCP client (mcphost, oterm) uses the same URL on localhost.

The whole of `/mcp` needs the admin token and nothing else, whatever `SHARE_LEVEL` says. A missing or wrong token
gets `401 {"error": "the agent surface needs Authorization: Bearer <ADMIN_TOKEN>"}`. DNS-rebinding protection is
off, because the node is reached by LAN IP, `.local` name and tailnet name, so the Host header is not checked and
the token is the only gate. Reach it over the tailnet and never with a port forward.

## Read, act, admin

Every tool has one class, set in `app/tool_classes.py`:

| class | means | tools |
|---|---|---|
| `read` | asks the node a question; nothing changes | `status`, `health_check`, `sensors`, `context`, `readings`, `report_latest`, `report_bundle`, `history`, `alerts`, `settings_get`, `packs`, `cells`, `issues`, `series`, `export_day`, `learned` |
| `act` | records that a person did something, in their own words | `act` |
| `admin` | changes the node, runs code on it, or makes it speak to the household unprompted | `settings_set`, `run_pack_script`, `maintenance`, `report_now` |

A remote agent, driven by a person, has all twenty-one. The household's own model on the node gets the 17 `read`
and `act` tools and nothing else ([the bot](bot.md)). The dashboard's ask pane gets fewer still and runs only reads
([Ask the node](ask.md)). Four tools write: `act`, `report_now`, `settings_set` and `run_pack_script`.
`maintenance` is `admin` but writes nothing, it answers with a command for a person to run.

## The tools

Start with `health_check`, then `status`.

| tool | arguments | returns |
|---|---|---|
| `status` | none | node, version, schema, uptime, last poll, readings ingested, polls, per-loop errors, mesh, ρ (the `/rho` body), whether the last backup succeeded |
| `health_check` | none | `{ok, checks: [{check, ok, fix}]}`: polled in the last 15 minutes; no source errors; a backup in the last two days; no local sensor's ambient channel frozen; with a broker, LoRa radios heard in the last hour. Every failing check names its fix. Also `sources`, the fundamental sources from [`GET /health/sources`](api.md), each with its state and, when not running, its fix; they never make `ok` false |
| `issues` | `issue?` | the whole `/issues` object (the issues, `headline` and `headline_rule`, `labels`, `stations` and `stations_silent`, `metrics`, the `asks` ledger, `lead`, the `digest` with its four sentences, `simple` and `prompts`, `geometry`, the packs' `sections`, the alert `events`, each saying with `asking` whether it still asks), or one issue with `as_of` and `labels`: state, the four distances with provenance, the sentence, the open asks |
| `sensors` | none | one row per sensor from `/stats`: local, indoor, kind, the 15-minute mean per metric, minutes silent; local first |
| `context` | none | sea, weather, satellite air, place and land from `/observations`, labelled; or a note that the first poll fills this |
| `readings` | `sensor_id`, `metric`, `hours=24` (up to 168) | meant to return hourly means oldest first; see the gap below |
| `history` | `sensor_id`, `metric` | every `{ts, value}` oldest first, for slow series such as `place-point / sat_buildings_yearly` |
| `series` | `metric="pm25"`, `hours=24` (up to 168) | aligned hourly arrays: indoor, outdoor, model |
| `alerts` | `limit=10` (up to 100), `since_hours=0` | the most recent alerts: `id`, `ts`, `rule_id`, `sensor_id`, `level`, `text`, `buttons` (null unless the rule asked with buttons) and `acted_at`. With `since_hours`, `{since_hours, count, alerts}`: `count` is every alert in the window, `alerts` the newest `limit` with their text cut to 160 characters |
| `report_latest` | none | the last report row |
| `report_bundle` | `hours=6` (1 to 168) | every number the report was written from |
| `cells` | none | the Fab City Index cells with value, unit and state |
| `packs` | none | the loaded packs: id, kind, description |
| `export_day` | `day?` (default yesterday) | the open-data export for that day |
| `learned` | `query?`, `scale?` | with nothing, what the house learned: what worked, what is usual, the alerts that may not fit, each in the node's own sentence. With `query` (a few keywords) it searches those and the diary of days, weeks, months and years; `scale` narrows to one size, and alone gives the newest. Answers only while `AGENT_PREFER=private` and no model sits at an address outside your network, and says why otherwise |
| `settings_get` | none | every runtime setting with its group, help and value; the node's secrets and the keys a pack lists under `secrets:` are masked, bootstrap keys are read-only |
| `maintenance` | `task`: update, backup, restore, restart, logs, doctor, storage, ui, telegram | the `planetai` command to run on the node, what it does and where. It runs nothing |
| `act` | `alert_id`, `note` (required), `agent="agent"` | writes: records `stage: acted` for that alert with the agent as actor, and returns `{recorded, alert_id, by}` |
| `report_now` | `agent="agent"` | writes: a report, written and sent now |
| `settings_set` | `changes: {KEY: value}`, `agent="agent"` | writes: changes runtime settings, live within 20 seconds; a blank returns the key to `.env` |
| `run_pack_script` | `pack`, `script`, `args?`, `agent="agent"` | runs code: `packs/<pack>/<script>.py` inside the container (15-minute limit), and returns exit code, stdout, stderr and `by`. Every script of a core pack runs. A wild pack's script runs only if its `pack.yaml` lists it under `agent_scripts:`, otherwise the answer is an `error` pointing to `planetai run <pack> <script>` on the node's terminal. A pack's `adapter.py` is never a script here, and a pack the node does not load (left out of `PACKS_ENABLED`, or refused by its `requires:`) runs nothing |

> **Gap in v0.91.0.** `readings` answers with its error for every sensor. It looks the sensor up at the top level of
> `/sparks`, and the hourly means sit under `series`. Use `series` or `history` instead.

`act` refuses a blank note and the placeholders that stand in for a person's words (`acted`, `acknowledged`, `done`,
`ok`, `n/a`, `-`, `acted (via reticulum)`), and tells the agent to ask what the person did. On a node with
`DECISION_REQUIRED=1` it gets 409 until a decision has been recorded on the dashboard against the same alert. No
tool records a decision, and `act` always writes `acted`.

The read routes `GET /shape`, `GET /effect` and `GET /reach` have no tool of their own.

## The audit trail

The name that reaches the record is the tool's `agent` argument, and where it lands depends on the tool. `act`
sends it to `POST /actions` as the row's `actor`. `settings_set` sends it as the `X-Agent` header, and
`PUT /settings` writes it as the actor of an `actions` row with `stage='settings'`. `report_now` sends the header
too, but `POST /report/now` records no actor, and `run_pack_script` records nothing, it only echoes the name back as
`by`. No tool reads the `X-Agent` header a client sends on `/mcp` itself.

The default is `agent`, so ask your client to pass its own name, `kitchen-claude` for example, in that argument. The
household's bot shows up as `local-model/<rung>`, because its loop fills the argument in when the model leaves it
out. Two agents on one node should read each other's rows before acting.

## What the tools will not do

No tool prints `.env` or a token, and `settings_get` shows the node's own secrets as `•••• set`. A pack's key is
masked only when that pack lists it under `secrets:` in its `pack.yaml`. A key it does not list there is shown in
full, so a wild pack that holds a token should list it. The container has neither Docker nor git, which is why
`maintenance` hands the command back instead of running it. `act` records what a person said they did and makes up
nothing. The server's own instructions to a model ask for one clear sentence before a list, and never to reveal a
token.

## For a shell agent

`planetai status --json`, `doctor --json`, `sensors --json`, `cells --json`, and `planetai setup --answers
node.json` to install without a terminal. `planetai snapshot` writes one JSON of everything the node answers, for a
design round or a bug report. It asks with the admin token, so it holds more than a stranger sees (the alerts, the
ledger with its notes taken out, 24 hours of aggregates), and it holds no raw readings and no token.

## Where this leads

The household's own model uses a smaller set of the same tools on Telegram: [The bot](bot.md).
