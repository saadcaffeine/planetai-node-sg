# PLANETAI Node. Spec v0.1
<!-- checked: v0.80.10 -->

2 September 2026. Two containers. This document is the brick; `ARCHITECTURE.md` is the building. Everything here is
either a contract that must survive rewrites, or a retired piece with the condition that brings it back.

## 1. Contracts

These are the things node #7 needs to share with node #1. They cost nothing to keep and everything to lose.

**Sensor identity.** `sensor_id` is `<source>-<upstream id>`: `sc-19880`, `bad-pa-46949`, `ag-<serial>`. Stable, human-readable, never reassigned.

**Local vs reference.** `sensors.local = TRUE` means the sensor is physically at this node and we're responsible for it. `FALSE` means context pulled from a public network. Rules and pushes treat them differently; the distinction is the whole point of a node.

**Indoor.** `sensors.indoor` is carried on every sensor and honoured by every rule. Indoor sensors never enter an ambient average. Inherited from Bali Air Dispatch's `suspected_indoor`.

**Domain neutrality.** The core evaluates rules and cells; it does not know what a metric means. Thresholds, messages and pillar mappings live in packs; `app/main.py`, `app/index.py` and `app/packs.py` must name no domain metric. Adapters in `app/sources.py` do name metrics: they translate a device's fields into the schema, which is a driver's job, not a domain's.

**Metric names.** Lowercase, no units in the name. Air today: `pm25 pm25_raw pm10 pm1 temp humidity pressure aqi gas_resistance noise light eco2 tvoc co2 tvoc_index nox_index`. Other domains propose their own in `docs/DOMAINS.md`: first pack to ship a metric names it. Units are fixed: µg/m³, °C, %, kPa. `pm25` is the *published* value; if a correction was applied, the uncorrected figure sits next to it as `pm25_raw`. Never overwrite raw.

**Time.** Readings are UTC instants. Daily anything is a `NODE_TZ` calendar day (WITA in Bali), because the burn pattern has a 9am peak and an after-dark climb and a UTC day cuts the evening in half. Say which basis you're on.

**Rules.** A rule is SQL that returns rows plus a message template. Cooldown is enforced in SQL against the `alerts` table. No rules engine, no expression language. If Postgres can't express the condition, the condition is wrong.

**Up-link.** Child → parent is `POST /aggregates {schema, node, scale, rows:[{bucket, sensor_id, metric, mean, min, max, n}]}`, hourly. Raw never travels it. The parent stores rows as `<child>/<sensor_id>` with `sensors.cadence = 'PT1H'`, the metric under its own name (until v0.50 it was `<metric>_1h`).

**Registry.** `registry.json` in this repo. Fields: name, scale, operator, place, lat, lon, cell, sources, parent, since, contact. Adding a node is a PR. Approval is a merge.

**Cells.** `fci-cells-v0`: `{city, cell:"Pillar|Scale", value, unit, source, observed_at, state}`. Exactly the `FCI Observations` row (base `appmNQaDGEFE9VcYh`). `state` is never upgraded by aggregation.

**Actions.** `{alert_id, stage: acknowledged|decided|acted, actor, note}`. ρ is computed from these against `alerts`; `decided` enters no ρ, and `measured` is derived by the node, never posted. An alert event's answer is `{event_id, stage: acknowledged|acted|dismissed, actor, note}` instead (v0.77, `docs/SPEC_alerts.md`): one row with no `alert_id`, which no ρ query reads. This is the only place ρ can be measured, so this table is the Index's instrument, not an app feature.

**Scale vocabulary.** `community | city | region | bioregion | planet`: the Full Stack Metrics Framework's scales. A node has one. It's metadata, not code.

## 2. What runs

| | |
|---|---|
| `db` | `imresamu/postgis:16-3.4-alpine` (Postgres 16 and PostGIS 3.4, for amd64 and arm64). Bound to localhost. Volume `db`. Nightly `pg_dump` via `backup.sh`. |
| `app` | Python 3.12. Six timer threads (poll, rules, the hourly refresh of the usual-for-the-hour view, the aggregates and events pushes, and the release check), a seventh for Reticulum when it is on, + FastAPI on :8080. `app/main.py` is ~2,600 lines. |

`GET /health /sensors /readings /stats /alerts /aggregates /cells /rho` · `POST /aggregates` (parent) · `POST /actions` (ρ) · `POST /readings` (downstream contributors, admin token).

Compute at node #1: an M-series Mac. Postgres and one Python process idle at about 230 MiB. No Pi has run a node yet; `docs/PLATFORMS.md` says what one would need.

## 3. Sources (adapters)

An adapter is a function returning `(sensors, readings)`. Two are described here; `docs/sensors.md` has the rest.

- `smartcitizen`: polls `api.smartcitizen.me/v0/devices/<id>`. Maps on measurement *name* so SCK 2.1 and 2.3 both work. Marks `indoor` from the kit's `exposure`. `local = TRUE`.
- `baliairdispatch`: polls `baliairdispatch.com/api/v1/latest`. Drops `stale`, `suspected_indoor` and `suspected_malfunctioning`, keeps stations within `BAD_RADIUS_KM`, and excludes this node's own hardware three ways (ids it polls, `BAD_MIN_SEPARATION_M`, `BAD_EXCLUDE`) plus one device arriving under two networks' ids. Stores `pm25` and `pm25_raw`. `local = FALSE`, always. Attribution: Bali Air Dispatch + the row's network.

## 4. Security, v0.43

`app:8080` is published on every interface, because the things that read this node are on the network: the NAS that pulls hourly dumps from `/backups` — the only off-machine copy of readings that exist nowhere else — the phones and wall screens in the house, Home Assistant, and the agent's MCP surface on the tailnet. Postgres is not: `db` binds `127.0.0.1:5432`, and so do IPFS's API and gateway ports (its swarm port, 4001, is public).

A token guards every write and every secret read. **`SHARE_LEVEL` decides what an unauthenticated reader on that LAN may see** — `off` by default, which answers such a reader the dashboard, `/health` with the node's position rounded to 110 m, `/presence`, `/llms.txt`, the daily CC-BY export and the layout, and refuses the rest with a sentence naming the setting; `open` answers the whole read API, which is what a wall screen with no token needs. A request carrying a token reads what it always read, from anywhere, at either level. The building's own geometry (`/place/geojson`), the map's routes (`/geo/*`, `/ground/*`) and the machine's (`/machine`, `/storage`) need a token at every level. `.env` is `chmod 600`, never committed.

There is no TLS. The boundary this section used to argue did not exist was crossed in v0.7 — see the first struck-through row in §6 — so it is deferred on its own terms now, not on an absence: the traffic that leaves this machine goes over Tailscale, which encrypts it, and a node reachable from outside the tailnet is what turns TLS from a checkbox into a requirement.

## 5. Update and rollback

`./update.sh`: backup → pull → apply schema to the live database → rebuild → verify. See [`docs/UPDATING.md`](docs/UPDATING.md).

The non-obvious part, and the one that bit us: Postgres runs `init.sql` **only when the data volume is first created**.
A running node never sees new columns or views unless something applies them. So `init.sql` is the whole schema, written
idempotently (`CREATE TABLE IF NOT EXISTS`, `ALTER TABLE ADD COLUMN IF NOT EXISTS`, `DROP VIEW` then `CREATE VIEW` -
because `CREATE OR REPLACE VIEW` cannot reorder columns), and both fresh installs and updates apply the same file.
`schema_version` records where a node is; `/health` reports it.

Schema changes are **additive only**. No dropped columns, no renames, no destructive migrations: which is what makes
rollback `git checkout <tag> && docker compose up -d --build` rather than a restore. Breaking that needs a major version
and a written migration.

## 6. Staged upgrades: retired pieces and their triggers

Each was built, audited, and cut on 2 September 2026. None is lost; each returns on its named condition, not on a
roadmap. Six triggers have since fired, and they are struck through below rather than deleted, so the record of
what was deferred and why stays legible.

| piece | returns when | what it looks like |
|---|---|---|
| **Mesh (Tailscale)** | ~~node #2 exists on a different network~~ **fired, v0.7** | `planetai mesh`; `PARENT_API_URL` becomes a tailnet hostname. See `docs/NETWORKING.md` |
| **Headscale** (self-hosted control plane) | a partner's governance requires no third-party coordinator, or the free tier is exceeded | swap the login server; nothing else changes |
| **MQTT broker** | ~~the first sensor that publishes~~ **fired, shipped v0.8** | `mqtt` profile; `planetai meshtastic`; `msh/#` and `planetai/sensors/#` |
| **Reticulum** bridge (LXMF inbox/outbox) | ~~-~~ **shipped v0.8**: `planetai reticulum`, TCP today, RNode a config block | `reticulum` profile |
| **Reticulum** node-to-node data transport | a district and a community node with no internet between them | Transport-enabled node + store-and-forward; see `docs/NETWORKING.md §3` |
| **Node registry service + signed handshake** | `registry.json` PRs stop scaling: roughly 30 nodes or a second operator org | FastAPI + SQLite, Ed25519 identity, human approval |
| **Federated learning (Flower)** | a model exists whose parameters can't be averaged by the hourly push, *and* the sovereignty claim is being examined by someone outside the team | self-hosted SuperLink at the district, SuperNodes at hubs; FedAvg first, FedProx when climates diverge |
| **Local LLM (Ollama)** | ~~someone asks the node a question the alert doesn't answer~~ **fired, shipped v0.21**: `planetai agent local` | a `/brief` endpoint that turns 24h stats into a paragraph in the local language |
| **Edge role / MQTT bridge** | a real network partition between sensors and the hub | a Pi with a broker forwarding upstream |
| **TimescaleDB** | `readings` passes ~50M rows or `stats` takes over a second | swap the image, `create_hypertable`, the SQL is already compatible |
| **A loopback-only node** (`SHARE_LEVEL=none`) | a node is on a network its household does not trust, *and* it can afford to lose the NAS pull, the phones, Home Assistant and MCP — all four of which read over the LAN | a third level, opted into, never a default; the socket keeps binding `0.0.0.0` and the middleware answers nothing without a token |
| **Telegram reply → action** | ~~the first operator who says "I did it" in the chat instead of curl~~ **fired, shipped v0.21**: `/act <id> <what you did>` to the bot | a 20-line webhook that maps a reply to `#<alert_id>` into `POST /actions` |
| **Cells → Airtable / index.fab.city** | the Index surface wants to pull from a node rather than read Airtable | aggregator (or a cron) pushes `GET /cells` rows into `FCI Observations`; states preserved |
| **Upstream model / compute** | a rule or brief needs inference a Pi can't do | `UPSTREAM_MODEL_URL` (OpenAI-compatible) / `UPSTREAM_COMPUTE_URL`. Removed from `.env.example` in v0.9 because no code reads them: the names are the contract, the settings return with the code that uses them. The model half shipped in v0.22 as `AGENT_REMOTE_URL` / `AGENT_ONLINE_URL` (`app/agent_loop.py`, and `app/ask.py` from v0.75); `UPSTREAM_COMPUTE_URL` has no code yet |
| **Separate notifier service** | a second channel (WhatsApp Business) with its own auth lifecycle | until then, a function. Note: Telegram, the LoRa mesh, LXMF and Home Assistant are now four channels and all four are still functions, called from `notify()` and `ha_alert()`. The trigger is an auth lifecycle, not a channel count. |
| **Artifacts from packs** | ~~-~~ **shipped v0.12**: `out/` is mounted writable and `planetai run <pack> <script>` executes a pack's scripts | `packs/earth-engine/timelapse.py` is the worked example |
| **A native install, with no container runtime** | the database stops needing PostGIS — either an arm64/SQLite-able `place`, or `place` moved out of the app. Spiked and **dropped 8 September 2026**: `db` is a PostGIS image (`imresamu/postgis:16-3.4-alpine` from v0.63, `postgis/postgis:16-3.4-alpine` before it), and PostGIS is load-bearing outside the pack (`app/main.py` serves `/place/geojson` with `ST_AsGeoJSON`, `ST_SimplifyPreserveTopology` and `ST_DWithin` on a geography), so a native node is a SQL port, not a packaging change | uv-managed venv + launchd/systemd. Costed at 5–8 days plus a migration for the live nodes and a permanent second SQL dialect across 85 call sites, 17 psycopg importers, `config/rules.yml` and both lint gates. Not worth it while Colima installs with one command on every macOS ≥ 13.5 |
| **`place` as an optional pack, and the plan view with it** | a machine that must run a node and cannot run PostGIS — an arm64 database image (a Pi), or an operator who does not want the plan view. **Approved in principle 8 September 2026, not built**: with the native path dropped, nothing calls for it | `/place/geojson` returns 410 and the dashboard says which card is absent and why, the way it already does for a missing source |

The rule: a piece comes back when its trigger fires, with a PR that names the trigger. Not before.

## 7. What this spec refuses

Kubernetes. Cloud providers. Embedding cascades. Causal-inference machinery. Four continents at once. If the network reaches thirty live nodes with a paying operator behind each, reopen this section.
