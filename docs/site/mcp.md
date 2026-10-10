# MCP server and tools
<!-- checked: v0.80.10 -->

This is the surface an agent holds. With it, any client that speaks MCP can read what the node read, ask it
how the place is doing in the household's own words, and record, in a person's own words, that somebody
acted. The server's own instructions to a model describe the node as "a small computer that connects
everything measuring one place, from sensors on the wall to satellites overhead, decides where it stands, and
tells the people there what to do. Raw readings never leave it." Nothing an agent does through it takes a
reading off the machine.

`app/agent.py` mounts it on the API at exactly `/mcp`, streamable HTTP, twenty tools over the existing
endpoints. The tools call the node's own API back on `127.0.0.1`, so they arrive as loopback; `report_now`,
`settings_set` and `report_bundle` also carry the admin token. The same tools serve Claude Desktop or Claude
Code on a laptop across the tailnet, the household's own model on Telegram, the dashboard's ask pane, and any
other MCP client.

## Connecting

```bash
planetai agent
```

prints the tools by class, the endpoint on this machine (`http://localhost:8080/mcp`) and on the tailnet
(`http://<MESH_NAME>:8080/mcp`, the MagicDNS name recorded once `planetai mesh` has run), the header every
call must carry, `Authorization: Bearer <ADMIN_TOKEN>`, and a ready-made snippet:

```json
{"mcpServers": {"planetai-bayu-ungasan": {"type": "http",
  "url": "http://bayu-ungasan:8080/mcp",
  "headers": {"Authorization": "Bearer <ADMIN_TOKEN>", "X-Agent": "tomas-claude"}}}}
```

[Bring your own agent](agents.md) walks through it with Claude Desktop, from the snippet to the first row an
agent writes.

For Claude Code, from a clone of the repository, `.mcp.json` is already there and reads the values from the
shell: `PLANETAI_MCP_URL` (default `http://localhost:8080/mcp`), `PLANETAI_ADMIN_TOKEN` and
`PLANETAI_AGENT_NAME`, so nothing secret is in the file. Or from anywhere:

```bash
claude mcp add --transport http planetai "$PLANETAI_MCP_URL" \
  --header "Authorization: Bearer $PLANETAI_ADMIN_TOKEN" --header "X-Agent: $PLANETAI_AGENT_NAME"
```

Cursor does not expand `${VAR:-default}`; paste the snippet from `planetai agent` instead. A local Ollama
with an MCP client (mcphost, oterm) uses the same URL on localhost.

Access: the whole of `/mcp` needs the admin token and nothing else; it bypasses `SHARE_LEVEL`. A missing or
wrong token is `401 {"error": "the agent surface needs Authorization: Bearer <ADMIN_TOKEN>"}`. DNS-rebinding
protection is off on purpose, because the node is reached by LAN IP, `.local` name and tailnet name: the
token is the access control, not the Host header. Reaching it from off the tailnet is a port forward, and the
answer to that is no.

## Read, act, admin

Every tool has one class, in `app/tool_classes.py`:

| class | means | tools |
|---|---|---|
| `read` | asks the node a question; nothing changes | `status`, `health_check`, `sensors`, `context`, `readings`, `report_latest`, `report_bundle`, `history`, `alerts`, `settings_get`, `packs`, `cells`, `issues`, `series`, `export_day` |
| `act` | records that a person did something, in their own words | `act` |
| `admin` | changes the node, runs code on it, or makes it speak to the household unprompted | `settings_set`, `run_pack_script`, `maintenance`, `report_now` |

A remote agent, driven by a person, has all twenty. The household's own model on the node is handed the 16
`read` and `act` tools and nothing else (`app/agent_loop.py`); see [The bot](bot.md). The dashboard's
[ask pane](ask.md) calls in as `dashboard-chat` and runs 12 of the `read` tools, never `settings_get`,
`report_bundle` or `export_day`; `act` and the `admin` tools become cards a person presses, and the pane runs none of them. Four tools write:
`act`, `report_now`, `settings_set` and `run_pack_script`. `maintenance` is `admin` and writes nothing: it
answers with a command for a person to run.

## The tools

Start with `health_check`, then `status`.

| tool | arguments | returns |
|---|---|---|
| `status` | none | node, version, schema, uptime, last poll, readings ingested, polls, per-loop errors, mesh, ρ (the `/rho` body), whether the last backup succeeded |
| `health_check` | none | `{ok, checks: [{check, ok, fix}]}`: polled in the last 15 minutes; no source errors; a backup in the last two days; no local sensor's ambient channel frozen; with a broker, LoRa radios heard in the last hour. Every failing check names its fix |
| `issues` | `issue?` | the whole `/issues` object (the issues, `headline` and `headline_rule`, `labels`, `stations` and `stations_silent`, `metrics`, the `asks` ledger, `lead`, the `digest` with its four sentences, `simple` and `prompts`, `geometry`, the packs' `sections`, the alert `events`), or one issue with `as_of` and `labels`: state, the four distances with provenance, the sentence, the open asks |
| `sensors` | none | one row per sensor from `/stats`: local, indoor, kind, the 15-minute mean per metric, minutes silent; local first |
| `context` | none | sea, weather, satellite air, place and land from `/observations`, labelled; or a note that the first poll fills this |
| `readings` | `sensor_id`, `metric`, `hours=24` (≤168) | meant to return hourly means oldest first. In v0.80 it returns its error for every sensor, because it looks the sensor up at the top level of `/sparks`, whose means sit under `series` |
| `history` | `sensor_id`, `metric` | every `{ts, value}` oldest first, for slow series such as `place-point / sat_buildings_yearly` |
| `series` | `metric="pm25"`, `hours=24` (≤168) | aligned hourly arrays: indoor, outdoor, model |
| `alerts` | `limit=10` (≤100), `since_hours=0` | the most recent alerts: `id`, `ts`, `rule_id`, `sensor_id`, `level`, `text` and `acted_at`. With `since_hours`, `{since_hours, count, alerts}`: `count` is every alert in the window, `alerts` the newest `limit` with their text cut to 160 characters |
| `report_latest` | none | the last report row |
| `report_bundle` | `hours=6` (1 to 168) | every number the report was written from |
| `cells` | none | the Fab City Index cells with value, unit and state |
| `packs` | none | the loaded packs: id, kind, description |
| `export_day` | `day?` (default yesterday) | the open-data export for that day |
| `settings_get` | none | every runtime setting with its group, help and value, the node's secrets and the keys a pack lists under `secrets:` masked; bootstrap keys read-only |
| `maintenance` | `task`: update, backup, restore, restart, logs, doctor, storage, ui, telegram | the `planetai` command to run on the node, what it does and where. It runs nothing |
| **`act`** | `alert_id`, `note` (required), `agent="agent"` | records `stage: acted` for that alert with the agent as actor, and returns `{recorded, alert_id, by}`. **Writes** |
| **`report_now`** | `agent="agent"` | writes and sends a report now. **Writes** |
| **`settings_set`** | `changes: {KEY: value}`, `agent="agent"` | changes runtime settings; live within 20 seconds; a blank returns the key to `.env`. **Writes** |
| **`run_pack_script`** | `pack`, `script`, `args?`, `agent="agent"` | runs `packs/<pack>/<script>.py` inside the container (15-minute limit) and returns exit code, stdout, stderr and `by`. Every script of a core pack runs; a wild pack's runs only if its pack.yaml lists it under `agent_scripts:`, and otherwise the answer is an `error` that points to `planetai run <pack> <script>` on the node's terminal. A pack's `adapter.py` is never a script here. **Runs code** |

`act` refuses a blank note and any of the placeholders the repository once used in place of a person's words
(`acted`, `acknowledged`, `done`, `ok`, `n/a`, `-`, `acted (via reticulum)`), and tells the agent to ask what
the person did. On a node with `DECISION_REQUIRED=1` it is refused with 409 until a decision has been
recorded on the dashboard against the same alert; no tool records a decision, and `act` always writes
`acted`.

The read routes `GET /shape`, `GET /effect` and `GET /reach` have no tool of their own.

> **Gap fixed in v0.80.7.** The `issues` tool's description now matches the code: an open alert event leads first,
> then the highest state, ties broken by which issue moved most in the last three hours, then declared order.
> `headline_rule` and `lead.by` in the answer say which.

## The audit trail

The name that reaches the record is the tool's `agent` argument, and how it lands depends on the tool.
`act` sends it to `POST /actions` as the row's `actor`. `settings_set` sends it as the `X-Agent` header, and
`PUT /settings` writes it as the actor of an `actions` row with `stage='settings'`. `report_now` sends the
header too, but `POST /report/now` records no actor, and `run_pack_script` records nothing: it only echoes
the name back as `by`. The `X-Agent` header a client sends on `/mcp` itself is not read by any tool.

The default is `agent`, so ask your client to pass its name, `tomas-claude` say, in that argument. The
household's bot appears as `local-model/<rung>` because its loop fills the argument in whenever the model leaves it out. Two
agents on one node read each other's rows before acting.

## What the tools will not do

No tool prints `.env` or a token; `settings_get` masks the node's own secrets as `•••• set`. A pack's key is masked
only when that pack lists it under `secrets:` in its `pack.yaml`; a key a pack does not list there is shown in
full, so a wild pack that holds a token should list it. The container has neither
Docker nor git, so `maintenance` hands the command back instead of running it. `act` records what a person
said they did and invents no action. Nor do the tools expose the node: the server's own instructions to a
model say to prefer one clear sentence to a list and never to reveal a token.

## For a shell agent

`planetai status --json`, `doctor --json`, `sensors --json`, `cells --json`, and `planetai setup --answers
node.json` to install without a terminal. `planetai snapshot` writes one JSON of everything the node answers,
for a design round or a bug report. It asks with the admin token, so it holds more than a stranger sees
(the alerts, the ledger with its notes taken out, 24 hours of aggregates), and it holds no raw readings and
no token.

## Where this leads

The tools are the same ones the household's own model uses on Telegram, with fewer of them: [The bot](bot.md).
