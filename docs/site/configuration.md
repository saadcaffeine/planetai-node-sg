# Configuration
<!-- checked: v0.91.0 -->

A setting is a decision the household makes about its node: which sensors count as its own, what it
watches first, when it may interrupt somebody, what a stranger on the WiFi may read, whether a question
may leave the house for an online model. This page lists every setting a node has, where its value comes
from and what it defaults to, grouped by what the node does with it. At v0.91.0 that is 62 runtime keys,
20 bootstrap keys, 42 keys declared by packs, and the keys read only from the environment.

## How a setting is read

The base is `.env` in the node's folder. `install.sh` writes it, it holds the tokens and the database password,
and it is never committed: keep it `chmod 600`. Docker hands the whole file to the `app` and `agent` containers and
to nothing else. The `reticulum` container gets eight named variables only: `LOG_LEVEL`, `NODE_NAME`,
`NODE_API_URL`, `RETICULUM_CONFIGDIR`, `RETICULUM_DATA`, `RETICULUM_ALERT_DESTINATIONS`, `RETICULUM_ANNOUNCE_S` and
`ACT_TOKEN`.

A **runtime** setting can be overridden in the database, from the dashboard's Set up view, `planetai config set`,
`PUT /settings` with the admin token, or the MCP `settings_set` tool. The database value wins over `.env` and the
node has it within about 20 seconds, with no restart. Saving a blank value deletes it, and the key falls back to
`.env`, then to the built-in default. `GET /settings` gives each value's source as `gui`, `env` or `default`, and
the `default` a fresh node gets, read from `data/env_defaults.yml` (generated from `.env.example`).

A **bootstrap** setting is read once, when Docker composes the containers or the process starts. The dashboard
shows these read-only; change one in `.env` and run `planetai restart`, or let `planetai config set` do both.

An **env only** key is read from the environment and nowhere else. `GET /settings` does not list it and
`planetai config set` says it is not a setting this node has: edit `.env` and restart.

The terminal side of all this, `planetai config` and its shortcuts, is on [the command line](cli.md#change-it).

### Keys the packs declare

A pack lists its keys under `env:` in its `pack.yaml`, with a comment above each. `GET /settings` shows the keys
of every installed pack, switched on or not, in the group `packs`, so you can see a pack's switch before you turn
it on. They are set like runtime keys, and `PUT /settings` answers 400 only for a key nothing declares. Because a
pack reads its keys from the environment, the node puts the database value there too, and the pack has it at its
next run. A key the pack also lists under `secrets:` is masked once saved, like the node's own tokens.
`planetai packs install` appends the keys a `.env` is missing, under a dated marker.

`COAST_MAX_KM`, `EE_PROJECT` and `EE_KEY_FILE` are pack keys and runtime keys at once. `GET /settings` lists each
once, in `packs`, with the pack's name beside it.

### Public, outward, secret

An anonymous `GET /settings` sees the value of a **public** key only; every other value shows as `•••• set` until
the admin token is presented. At `SHARE_LEVEL=off`, a caller who is neither on this machine nor carrying a token sees
only `UI_LAYOUT` and `SHARE_LEVEL`. A **secret** is masked for everyone, always; `GET /settings/raw` with the admin
token is the one unmasked read, and it covers runtime keys only.

An **outward** key changes what leaves the machine. Set up asks before saving a change to one, and before saving
`PACKS_ALLOW_CODE=1` (`runs_code` in `GET /settings`), in a panel that quotes the setting's own help.

Most settings are free text, so a typo does not stop the node. Thirteen keys accept only the values in their
Values column below, and `PUT /settings` answers 400 for anything else: `REPORT_EVERY`, `REPORT_ANCHOR`,
`REPORT_DEPTH`, `LEARN_PUSH`, `ALERT_ENGINE`, `UI_MODE`, `AGENT_PREFER`, `SHARE_LEVEL`, `UI_ASK`, `UI_GROUND`,
`MAP_TILES`, `UPDATE_CHECK` and `SPECIES_MATCH`. `GET /settings` lists them under `choices`, so the dashboard and
`planetai config` offer the values instead of a text box.

### Rules of the `.env` file

- No space after `=`. `VAR= value` is a shell command, not an assignment.
- A comment goes above a key that ships blank, never after it: `KEY=   # note` hands the container `# note` as the
  value.
- A number left blank keeps the code default. `update.sh` copies new keys into your `.env` with the value
  `.env.example` gives them, and the `REPORT_*` keys ship blank so an updating node keeps the rhythm it had.
- `planetai doctor` checks for stray spaces, and `update.sh` refuses to run until they are gone.

An older `.env` may still hold these, and nothing reads them:

| key | what happened to it |
|---|---|
| `BRIEFINGS`, `BRIEF_MORNING`, `BRIEF_EVENING`, `BRIEF_HOUR` | Replaced by the report rhythm. A node that had `BRIEF_MORNING=7` was set once to `REPORT_EVERY=12`, `REPORT_ANCHOR=7`. You can delete them. |

## Reference

Kind is `runtime`, `bootstrap`, `pack` or `env only`, as above. `public`, `outward` and `secret` are as above;
`restart` means `GET /settings` flags the key as needing a restart. Where `.env.example` ships a different value
from the code's default, both are given.

## Place

| Setting | Default | Values | Meaning | Kind |
|---|---|---|---|---|
| `NODE_NAME` | `node`; `.env.example` `bayu-2` | lowercase, dashes | The node's name, in `/health`, `/export`, MQTT and Home Assistant ids, pushes to a parent and the `out/earth/<name>` folder. | bootstrap |
| `NODE_KIND` | `home` | `home`, `business`, `community`, `district` | What the node is for, which is not its Index scale. `planetai setup` sets `NODE_SCALE=city` for a district. See [Known gaps](#known-gaps). | runtime · public |
| `NODE_SCALE` | `community` | `community`, `city`, `region` | The Full Stack Metrics scale: stamped on sensors that declare none, sent to a parent, in `/export`, and the scale of the `Governance\|<Scale>` cell. | bootstrap |
| `NODE_CITY` | `unknown`; `.env.example` `bali` | pilot key or slug | The city key in Index cells, `/health` and `/export`, and what `planetai sources` filters the registry by. `planetai setup` sets `bali`, `barcelona`, `boston` or `santiago` inside those boxes, else a slug of the place. | bootstrap |
| `NODE_LAT`, `NODE_LON` | `0`; `.env.example` `-8.8271`, `115.15709` | decimal degrees | The node's position. Published as the centre of its resolution-8 cell in `/health`, `/export` and an untrusted `/sensors` and `/stats`; three decimals to this machine or a token; unrounded in `/forecast`, `/earth` and `/place/geojson`. `install.sh` refuses to start without them. | bootstrap |
| `NODE_TZ` | `UTC`; `.env.example` `Asia/Makassar` | IANA name | The database session time zone, so local midnight and local hours in rules, reports, quiet hours and `/shape`. Also the agent container's `TZ`. | bootstrap |
| `NODE_ISSUES` | blank = every issue; `.env.example` `air,heat,land,coast` | comma list of `air`, `heat`, `land`, `coast`, `water` | What this place watches, most important first. The dashboard starts at the first; the one with something to say takes the top. An unknown name is dropped with a line in the log. Your preset guessed this, so change it. | runtime · public |
| `NODE_VERSION` | written by `install.sh` and `update.sh` | string | `git describe`, the `VERSION` file, or `dev`. Shown in `/health`, `/presence` and `/export`. | env only |
| `LOCAL_RADIUS_M` | `500` | metres | How far from the node a sensor can be and still count as its own. A kit of yours further away stays out of the ambient average and out of every `live` claim. | runtime · public |

## Who may read it

| Setting | Default | Values | Meaning | Kind |
|---|---|---|---|---|
| `SHARE_LEVEL` | `off` | `off`, `open` | What a request with no token may read. `off`: the dashboard shell, `/health` with the position rounded, the daily export, the layout, `/nodes`, and `/offers` while the `things` pack is on. `open`: the whole read API to anything on your network, so a wall screen or a phone works without a token, with rooms and sensors named Room A and Sensor 1; writes still need a token. A request with a token reads everything at either level. See [Sharing and security](sharing.md). | runtime · public · outward |
| `ADMIN_TOKEN` | blank; `install.sh` makes one | hex string | Opens `PUT /settings`, `/settings/raw`, `/settings/phone`, `POST /readings`, `/report/now`, `/test-alert` and all of `/mcp`, and works wherever `BACKUP_TOKEN` or `ACT_TOKEN` would. `planetai ui` creates and prints it. | env only · secret |
| `BACKUP_TOKEN` | blank; `update.sh` makes one | string | Read-only: lets a NAS fetch `/backups`, `/backups/<name>` and `/report/bundle`, and nothing secret. | runtime · secret |
| `POSTGRES_PASSWORD` | `change-me`; `install.sh` replaces it | string | The database password. | env only · secret |
| `DATABASE_URL` | set by `docker-compose.yml` | URL | The app's database connection. Nothing to set by hand. | env only |
| `LOG_LEVEL` | `INFO` | Python logging level | Log level of the app and the Reticulum bridge. | env only |

## The dashboard

| Setting | Default | Values | Meaning | Kind |
|---|---|---|---|---|
| `UI_MODE` | `advanced` | `simple`, `advanced`, `learn` | What the page opens as. `simple` answers what a person in the house asks; `advanced` shows every section; `learn` adds a question mark at each part that quotes this documentation. A reader can switch from the header, and only their browser remembers it. | runtime · public |
| `UI_ASK` | `on` | `on`, `off` | `on` puts a toggle on the dashboard for the ask pane, which asks the model chosen under Model about what the page shows and changes nothing. See [Ask the node](ask.md). | runtime · public |
| `UI_GROUND` | `svg` | `svg`, `map` | How the ground is drawn. `map` uses MapLibre and deck.gl in the browser, so it pans and zooms; it needs WebGL2 and falls back to `svg`, saying why. The two libraries (3.2 MB as served) load only in this mode. Neither value changes what leaves the house. | runtime · public |
| `UI_LAYOUT` | blank | JSON | Order and visibility of the dashboard's cards, written by Arrange mode. Blank restores the default. Every screen can read it at every level. | runtime · public |
| `MAP_TILES` | `off` | `off`, `on` | `on` draws live satellite and street tiles, and each tile request tells a tile server which square of the planet this house looks at. `off` uses the node's own copy of OpenStreetMap. | runtime · public · outward |
| `UPDATE_CHECK` | `on` | `on`, `off` | Every hour, asks planetai.fab.city which release is current; when one is newer, the page's top bar, `planetai doctor` and Telegram (once per version) say so. Nothing is installed. The same switch reads the programme's list of nodes (`registry.json`) hourly for `GET /nodes`. The request carries nothing about the house but shows its internet address; `off` asks neither. | runtime · public · outward |
| `SPECIES_MATCH` | `off` | `on`, `off` | `on` asks `api.gbif.org` which taxon a typed scientific name is (GBIF Backbone, CC BY 4.0), sending only the name. Weekly it also reads this country's GRIIS list of introduced and invasive species (the country from `NODE_TZ`) and counts open records in the node's seven cells, which tells GBIF an area about 2 km across. The weekly reads run only while the `eyes` pack is on. See [Sharing and security](sharing.md). | runtime · public · outward |
| `STATIONS_SHOWN` | `3` | integer, `0` = all | How many neighbourhood stations the dashboard lists, nearest first. Your own hardware is always listed and not counted. To collect fewer stations, lower the station pack's radius instead. | runtime · public |

## What it reads

| Setting | Default | Values | Meaning | Kind |
|---|---|---|---|---|
| `SC_DEVICES` | blank | comma-separated kit ids | Smart Citizen kits read from the cloud API, the number in `smartcitizen.me/kits/<id>`. Always yours, at this address. | runtime |
| `SC_USER` | blank | username | Reads every kit on a Smart Citizen account instead; indoor or outdoor comes from each kit. Also used by `/nearby?audit=1`. | runtime |
| `SC_EXCLUDE` | blank | comma-separated kit ids | Account kits that belong to another site. | runtime |
| `AIRGRADIENT_HOSTS` | blank | hostnames or IPs | AirGradient ONE or Open Air units on your WiFi, read by the `airgradient` pack whenever this is set. | runtime |
| `PURPLEAIR_HOSTS` | blank | IPs | PurpleAir units on your WiFi, read by the `purpleair` pack whenever this is set; use the IP, the `.local` name is unreliable. | runtime |
| `SENSOR_INDOOR` | `0` | `1`, `0` | Whether the LAN sensors above are indoors. See [Known gaps](#known-gaps). | runtime · public |
| `OPENMETEO_ENABLED` | `1` | `1`, `0` | Open-Meteo weather at the node's coordinates, and the CAMS air model through the `air-quality` pack, whose switch this is. Free, no key, anywhere. Context only, never rolled into an Index cell. | runtime · public |
| `BOOTSTRAP` | `1` | `1`, `0` | On first start, fills the database with 92 days of CAMS history (while the `air-quality` pack is on) and NASA POWER climatology at these coordinates. Skipped once there is CAMS history older than two days. | env only |
| `CKAN_PORTALS` | blank | `slug=url,slug=url` | CKAN open-data portals to watch, for the `Governance\|City` cell. The presets fill this per city. | runtime · outward |
| `CKAN_SCALE` | `city` | scale | The scale stamped on CKAN observations. | env only |
| `POLL_SECONDS` | `300` | seconds | How often the source loop polls. | bootstrap |
| `MESH_INDOOR_NODES` | blank | `!hex` ids | Meshtastic radios that are indoors, e.g. `!8f491db0,!64e0bfd1`. Mesh sensors are outdoor otherwise. | runtime |
| `MQTT_HOST` | blank | hostname | The broker. When set, the node subscribes to `msh/#`, `planetai/sensors/#` and the topics its packs read (`device/sck/#`, with `smartcitizen` on). `planetai meshtastic` and `planetai broker` set it. | bootstrap |
| `MQTT_USER`, `MQTT_PASS` | blank | strings | Broker credentials, generated by `planetai meshtastic`. | env only · secret |
| `SC_FORWARD` | blank | device tokens | Kits and DIY nodes publishing to this broker whose messages are passed on to smartcitizen.me unchanged, through a queue that survives an outage. See [Sensors](sensors.md). | runtime · secret · outward |
| `SOURCES_DIR` | `/app/data/sources` | path in the container | Where `GET /sources` reads the vendored source registry. | env only |

Sources that come as packs (stations, forecast, earth and place data, fab labs) are set with the
[pack keys](#pack-keys).

## Alerts and channels

| Setting | Default | Values | Meaning | Kind |
|---|---|---|---|---|
| `TELEGRAM_BOT_TOKEN` | blank | BotFather token | Alerts and reports to Telegram; blank sends them to the log only. `planetai telegram` sets it. | runtime · secret · outward |
| `TELEGRAM_CHAT_IDS` | blank | comma-separated ids | Who receives them. A chat not listed here is told once that the bot answers its household only, with its id to add. | runtime · outward |
| `TELEGRAM_BUTTONS` | `0` | `1`, `0` | The bot sets this to `1` on start, so event messages carry Done, Not now and Doesn't fit, and a pack rule's own buttons go to Telegram as a keyboard, only while somebody answers them. Leave it alone. | runtime |
| `ALERT_LEVEL` | `act` | `act`, `warn`, `info` | What interrupts you between reports: only what needs doing, also what changed, or everything. All of it is recorded. | runtime · public |
| `QUIET_HOURS` | `1` | `1`, `0` | Between the hours below only act-level alerts are sent, and a report due then is folded into the next. | runtime · public |
| `QUIET_FROM`, `QUIET_TO` | `22`, `6` | local hour | When quiet hours start and end. | runtime · public |
| `ALERT_ENGINE` | `rules` | `rules`, `shadow`, `events` | `rules`: every rule sends on its own. `shadow`: the event engine records what it would send in `event_messages` and sends nothing. `events`: the engine sends the heat and air messages, one per event, with the buttons when the bot runs; the old heat and air rules still record alerts but do not send. On `shadow` and `events` an issue's state on the dashboard follows its event. | runtime |
| `ALERT_MAX_PER_DAY` | `4` | whole number | With the event engine, pushes a day outside danger. Danger is never held. | runtime |
| `HOME_HAS` | blank | `purifier`, `ac`, `fan`, `windows` | What this home has; the event engine suggests only these. | runtime |
| `ALERT_LOCALE` | `en` | `en`, `id`, `es` | Language of the alerts, the reports, the test alert and the bot. The dashboard and terminal stay in English. | runtime · public |
| `HA_DISCOVERY` | `0` | `1`, `0` | Publishes local sensors and alerts as Home Assistant entities over MQTT, through the `home-assistant` pack, whose switch this is. `planetai homeassistant` sets it. | runtime · public · outward |
| `MESH_ALERTS` | `0` | `1`, `0` | Sends the first line of act-level alerts back over the LoRa mesh. Needs downlink on the gateway's channel. | runtime · public · outward |
| `MESH_TG_FORWARD` | `1` | `1`, `0` | `1` forwards each text message heard on the mesh to the Telegram bot; `0` only logs it. Either way it is appended to `out/mesh-messages.jsonl`, and the dashboard shows only the seen and sent counts. | runtime · private · inward |
| `MESH_GATEWAY_NODE_NUM` | `0` | decimal | The gateway radio's node number, the sender for downlink. | runtime |
| `RADIO_PEERS` | blank | `name=host:1883:password,…` | Other nodes this broker bridges to with `planetai radio federate`. Only `fabcity/` topics cross, never a reading. | env only |
| `RETICULUM_URL` | blank; `planetai reticulum` sets `http://reticulum:4243` | URL | The LXMF bridge. When set, act alerts go to its `/send`. | env only |
| `RETICULUM_ALERT_DESTINATIONS` | blank | LXMF hashes | Where the bridge delivers act alerts, addresses from Sideband with no spaces. Set it in `.env`: see [Known gaps](#known-gaps). | runtime · outward |
| `RETICULUM_PRESENCE` | `0` | `1`, `0` | Announces the node's name and a coarse cell every half hour, so other nodes see it exists and how far away. Nothing else, and nothing at all while `0`. | runtime · public · outward |
| `RETICULUM_PRESENCE_RES` | `3` | H3 resolution `0` to `6` | How exactly the announce places the node. `3` is cells about 60 km a side, the island; `4` about 22 km; `5` about 8 km. A value finer than `6` is treated as `6`. | runtime · public · outward |
| `RETICULUM_ANNOUNCE_S` | `1800` | seconds | The bridge's announce interval. | env only |

## Reports

One report every `REPORT_EVERY` hours in the node's time zone, counted from `REPORT_ANCHOR`, written in the first
20 minutes of the due hour.

| Setting | Default | Values | Meaning | Kind |
|---|---|---|---|---|
| `REPORT_EVERY` | blank = `6` | `3`, `4`, `6`, `8`, `12`, `24` | Hours between reports; each divides 24. Also the default window of `/report/bundle`. | runtime · public |
| `REPORT_ANCHOR` | blank = `6` | `0` to `23` | The local hour the rhythm starts from. With `6` and `6`: 06, 12, 18 and 00. | runtime · public |
| `REPORT_DEPTH` | blank = `auto` | `auto`, `brief`, `standard`, `deep` | How much a report says. See [Known gaps](#known-gaps). | runtime · public |
| `LEARN_PUSH` | blank = `all` | `all`, `week`, `off` | The morning memory on Telegram. `all`: the first report each day carries yesterday's diary entry, last week's on Mondays, last month's on the 1st, last year's on 1 January, and what the learnings changed. `week`: only week, month and year. `off`: never; `/learned` still answers. See [The report](report.md). | runtime · public |

## Closing a loop

| Setting | Default | Values | Meaning | Kind |
|---|---|---|---|---|
| `ACT_TOKEN` | blank; `planetai ui` makes one | string | Lets someone record that they acted on an alert (`POST /actions`) from another device without the admin token; it cannot read a secret or change a setting. Set up shows it as a QR code for a phone. | runtime · secret |
| `DECISION_REQUIRED` | `0` | `0`, `1` | `1` refuses an act (409) unless a decision was recorded on the same alert first, on every way in. Meant for a node that acts for a street, where everybody answering has a screen to decide on. | runtime |

## Models

The agent loop in the `agent` container builds its ladder of models from these keys and re-reads them every minute,
so a change on Set up, Model reaches the bot within a minute even though `GET /settings` flags them `restart`. The
ask pane reads the same keys on every question. See [The bot](bot.md) and [Ask the node](ask.md).

| Setting | Default | Values | Meaning | Kind |
|---|---|---|---|---|
| `AGENT_PREFER` | `private` | `private`, `fallback`, `strongest` | `private` never uses the online model, or a remote one at an address outside your network, so nothing leaves it. `fallback` tries your remote model, then online, then local. `strongest` puts online first. | runtime · public · outward · restart |
| `AGENT_ONLINE_URL` | blank | `https://api.anthropic.com/v1`, `https://api.openai.com/v1`, … | An OpenAI-compatible online endpoint, the URL and nothing else. Use an `https` address: the key travels in the `Authorization` header. A value not starting with `http` is skipped. | runtime · outward · restart |
| `AGENT_ONLINE_MODEL` | `claude-sonnet-4-6` | model id | Pick one from `GET $AGENT_ONLINE_URL/models`; a retired model answers 404, which looks like a bad key. | runtime · public · outward · restart |
| `AGENT_ONLINE_KEY` | blank | secret | The one thing that lets household data leave your network. | runtime · secret · outward · restart |
| `AGENT_REMOTE_URL` | blank | `http://<host>:8082/v1` | A bigger model on another machine of yours, OpenAI-compatible. An address outside your network counts as online. | runtime · restart |
| `AGENT_REMOTE_MODEL` | `gpt-oss-120b` | model id | e.g. `gpt-oss-120b` or `qwen3:8b`. | runtime · public · restart |
| `AGENT_REMOTE_KEY` | blank | secret | If that server asks for one. | runtime · secret · restart |
| `EYES_MODEL` | blank = off | Ollama model id | A vision model in this machine's Ollama that describes each image and files what it sees under the [flows](https://planetai.fab.city/vocab/flows/1.0/) classes. The picture never leaves the machine and the model is never asked about people. On 16 GB, `qwen2.5vl:7b`. | runtime · public |
| `OLLAMA_URL` | `http://host.docker.internal:11434` | URL | Ollama on this machine, the `local` rung. `planetai agent local` sets `http://172.17.0.1:11434` on Linux. | env only |
| `AGENT_MODEL` | `qwen3:4b` | Ollama model | The local rung's model; it must do tool calling. `planetai agent local pull <tag>` sets it. | env only |
| `AGENT_NAME` | `local-model` | string | How the agent's actions appear in the audit trail. | env only |
| `MCP_URL` | `http://app:8080/mcp` | URL | Where the loop reaches the node's MCP. Set by compose. | env only |

## Parent and children

A node with a parent posts the hourly means of its own sensors to `PARENT_API_URL/aggregates` and alert timestamps to
`PARENT_API_URL/events`, with `PARENT_TOKEN` as Bearer and `NODE_SCALE` as `scale`. Values and times go up;
where, what was said and who said it stay. See [Federation](federation.md).

| Setting | Default | Values | Meaning | Kind |
|---|---|---|---|---|
| `PARENT_API_URL` | blank = none | `http://<district>:8080` | The parent node. | runtime · outward |
| `PARENT_TOKEN` | blank | string | What this node presents to its parent. | runtime · secret |
| `AGGREGATE_TOKEN` | blank | string | What this node demands from its children on `POST /aggregates` and `POST /events`, and all it opens. Without it the node accepts no children (403). | runtime · secret |

## Storage

Read by `docker-compose.yml` and `backup.sh`. `planetai storage` shows each and `planetai storage set` changes the
backups and the pictures folder. See [Storage](storage.md).

| Setting | Default | Values | Meaning | Kind |
|---|---|---|---|---|
| `DATA_DIR` | blank = the Docker volume `db` | path | Where the live database lives. A local disk or partition only, never a NAS. | bootstrap |
| `CAPTURES_DIR` | `./out/captures` | path | Where the household's pictures live. A NAS share is fine. A capture is refused, and the doctor goes red, when the folder is missing or not writable. | bootstrap |
| `BACKUP_DIR` | `./backups` | path | Where the nightly dumps go. A mount point must be mounted, or the backup refuses. | bootstrap |
| `BACKUP_KEEP` | `30` | days | Days of dumps kept. | bootstrap |
| `BACKUP_REMOTE` | blank | rclone `remote:path` | Off-machine copy after each backup (S3, B2, R2, Drive, SFTP, WebDAV and more). Run `rclone config` once. | bootstrap |
| `EXPORT_ENABLED` | `1` | `1`, `0` | Each night writes yesterday's `exports/<node>/YYYY-MM-DD.json`: hourly means, cells, alerts and ρ, never raw. | bootstrap |
| `IPFS_PUBLISH` | `0` | `1`, `0` | Adds each export to IPFS and records the CID in `exports/<node>/CIDS.txt`. `planetai ipfs` turns it on. | bootstrap |
| `APP_PORT` | `8080` | port | The host port, on every interface. Change it if 8080 is taken. | bootstrap |
| `COMPOSE_PROFILES` | blank | `mqtt`, `agent`, `ipfs`, `reticulum`, `grafana` | Which optional containers run. Set by `planetai meshtastic`, `agent local`, `ipfs`, `reticulum` and `grafana`; leave it alone. | bootstrap |
| `GRAFANA_BIND` | `127.0.0.1` | address | Where Grafana listens. `0.0.0.0` opens it to the network; set `GRAFANA_ADMIN_PASSWORD` first. Set up › System shows it. See [Grafana](grafana.md). | bootstrap |
| `GRAFANA_PORT` | `3000` | port | Grafana's port. | bootstrap |
| `GRAFANA_ADMIN_PASSWORD` | blank = `admin` | text | The password of Grafana's `admin` login. Set up says only whether it is set. | bootstrap, secret |

## Packs

| Setting | Default | Values | Meaning | Kind |
|---|---|---|---|---|
| `PACKS_ENABLED` | blank = every pack in `packs/` | pack ids | Which packs load. | runtime · public |
| `PACKS_ALLOW_CODE` | `0` | `1`, `0` | Data packs always load. Code packs (`adapter.py`) run Python with the node's privileges: read them, then set `1`. An official pack with its own `switch:` runs on that switch alone. | runtime · public |
| `PACKS_DIR` | `/app/packs` | path in the container | The pack directory. | env only |
| `PACK_OUT` | `/app/out` | path in the container | Where packs write, mounted from `./out`. | env only |
| `RULES_PATH` | `/app/config/rules.yml` | path in the container | The core rules file. | env only |
| `CHANNELS_PATH` | `/app/config/channels.yml` | path in the container | The channel-role declarations. | env only |
| `ENV_DEFAULTS` | `/app/data/env_defaults.yml` | path in the container | Where `GET /settings` reads each key's default. | env only |

## Pack keys

Every key a `pack.yaml` declares, with the default it ships. All are kind `pack`. A code pack reads them only with
`PACKS_ALLOW_CODE=1`, except `bali-air-dispatch`, an official pack with its own switch, which runs on `BAD_ENABLED=1`
alone.

| Setting | Pack | Default | Meaning |
|---|---|---|---|
| `BAD_ENABLED` | bali-air-dispatch | `0`; bali preset `1` | The island's public stations as this node's ring of neighbours. Bali only. |
| `BAD_RADIUS_KM` | bali-air-dispatch | `15`; bali preset `8` | How far out the ring reaches. Also `/nearby.radius_km`. |
| `BAD_MIN_SEPARATION_M` | bali-air-dispatch | `150` | A station closer than this is taken to be the node's own hardware. |
| `BAD_EXCLUDE` | bali-air-dispatch | blank | Station ids that are ours and the rules above missed. |
| `BAD_INCLUDE_INDOOR` | bali-air-dispatch | `0` | `1` keeps stations the archive suspects are indoors. |
| `MAKE_ENABLED` | make | `0` | Off on purpose: the Fab Lab Network directory it reads is not openly licensed. Read [packs/make/README.md](../../packs/make/README.md) first. Needs `PACKS_ALLOW_CODE=1`. |
| `MAKE_RADIUS_KM` | make | `50` | How far to look for a fab lab, in km. |
| `MAKE_SOURCE` | make | `archive` | `archive` reads the dated monthly snapshots; `live` reads api.fablabs.io, which says it has been removed. |
| `MAKE_SNAPSHOT` | make | blank = newest | Pins a snapshot, e.g. `2026.07.31_labs.json`. |
| `MAKE_REFRESH_DAYS` | make | `30` | How often to re-read, about 5.3 MB each time. |
| `THINGDATA_INSTANCES` | thingdata | blank | ThingData servers, `slug=url`, comma-separated. Blank and the pack idles. |
| `THINGDATA_SCALE` | thingdata | `city` | `city` or `region`. |
| `THINGDATA_MAX` | thingdata | `5000` | Refuses to count a larger collection rather than report a truncated total. |
| `FORECAST_BMKG` | forecast | `1` | Reads BMKG, Indonesia's meteorological agency. |
| `FORECAST_BMKG_ADM4` | forecast | blank | The village code BMKG needs. `planetai run forecast verify` checks it is near the node. |
| `FORECAST_OPENMETEO` | forecast | `0` | Reads Open-Meteo, which works anywhere but whose free tier is non-commercial only, so it is your call. One switch for its weather, the CAMS air and, with `coast` on, the sea; [Next days](next-days.md) draws them. |
| `FORECAST_POLL_HOURS` | forecast | `6` | How often to ask each source; one that fails is asked again after 30 minutes. `planetai run forecast fetch` asks now. |
| `FORECAST_WIND_N` | forecast | `8` | The map's wind field, points a side (64 points). Only with `FORECAST_OPENMETEO=1`. |
| `FORECAST_WIND_KM` | forecast | `30` | The wind field's half-width, in km. |
| `EARTH_RADIUS_M` | earth | `5000` | Half-width of the square around the node. 5000 is about 64 MB on disk and 103 MB pulled per year. |
| `EARTH_YEARS` | earth | blank = all | Which years to fetch; the dataset has 2017 to 2025. |
| `PLACE_RADIUS_M` | place | `1000` | The radius described from OpenStreetMap. Also `/place/geojson.radius_m`. |
| `PLACE_REFRESH_DAYS` | place | `30` | How often to fetch from Overpass again; a moved node fetches at once. |
| `GROUND_RADIUS_KM` | place | `12` | Half-width in km of the street map kept on disk by `planetai run place basemap`; the earth-engine basemap uses it too. |
| `GROUND_DRONE_RADIUS_KM` | place | `4` | How far round the node to look for OpenAerialMap drone imagery, in km. |
| `GROUND_DRONE_MAXZ` | place | `18` | The finest zoom of drone tiles kept. |
| `EE_PROJECT` | earth-engine | blank = from the key file | Earth Engine project id, not the service account number. Also a runtime key. |
| `EE_SERVICE_ACCOUNT` | earth-engine | blank = from the key file | The Earth Engine service account. |
| `EE_KEY_FILE` | earth-engine | `/app/config/ee-key.json` | The service-account key; copy it to `config/ee-key.json`. Also a runtime key. |
| `GROUND_SAT_WIDE_KM` | earth-engine | `60` | Half-width in km of the wide Sentinel-2 square for `planetai run earth-engine basemap`. |
| `FIRE_ENABLED` | fire | `0` | Off for the bandwidth: without a key it downloads NASA FIRMS's regional file, 1 to 2 MB a satellite, whenever it changes. Read [packs/fire/README.md](../../packs/fire/README.md). Needs `PACKS_ALLOW_CODE=1`. |
| `FIRE_LOCAL_KM` | fire | `25` | The local ring, burning near enough to smell. |
| `FIRE_REGION_KM` | fire | `150` | The regional ring, smoke that travels. |
| `FIRE_POLL_HOURS` | fire | `3` | How often to ask; an unchanged file costs one HEAD request. |
| `FIRE_SATELLITES` | fire | `noaa-20,noaa-21` | VIIRS satellites: `noaa-20`, `noaa-21`, `suomi-npp`. |
| `FIRMS_MAP_KEY` | fire | blank | Optional free NASA FIRMS key, so the pack fetches only the regional box. Masked once saved. |
| `SURFACE_HEAT_RING_KM` | surface-heat | `3` | Outer edge of the ring the node's cell is compared with, in km; it starts at 1 km. |
| `SURFACE_HEAT_MIN_CLEAR` | surface-heat | `0.5` | The share of cell and ring that must be clear land for a scene to count. |
| `TERRAIN_RADIUS_M` | terrain | `5000` | Half-width of the square around the node, in metres. Water from further uphill is not counted. Needs `PACKS_ALLOW_CODE=1`. |
| `TERRAIN_DEM_PATH` | terrain | blank | A GeoTIFF of your own (a drone survey, a national LiDAR), used instead of Copernicus DEM GLO-30. |
| `TERRAIN_DEM_LICENCE` | terrain | blank | That file's licence, in words. Blank and the node computes from it and shows nothing. |
| `COAST_MAX_KM` | coast | `30` | Refuses to report if the nearest ocean grid cell is further than this. Also a runtime key (public), and it moves the dashboard's drawn footprint too. |

Two pack settings are read but declared in no `pack.yaml`, so they are env only: `OVERPASS_URL` (default
`https://overpass-api.de/api/interpreter`, the place pack's Overpass endpoint) and `BAD_BACKFILL_DAYS` (default
`0`, the size of the one-off `planetai run nearby backfill`, whose argument overrides it).

The Reticulum bridge's own paths, `RETICULUM_DATA` (`/data`), `RETICULUM_CONFIGDIR` (`/etc/reticulum`) and
`NODE_API_URL` (`http://app:8080`), are set by `docker-compose.yml`. Nothing to set by hand.

## Presets

A preset is a file in `presets/` that `install.sh --preset` copies into `.env` before it applies its flags, so
coordinates given on the command line win. `planetai setup` picks one when the place falls inside the bali,
barcelona, boston or santiago box. Bali, Barcelona, Boston and Santiago are Fab City Index pilots; Delhi and Menorca
are not. Every preset guesses `NODE_ISSUES`: change it, since what matters here is for the people who live here to
decide.

| Key | bali | barcelona | boston | delhi | menorca | santiago |
|---|---|---|---|---|---|---|
| `NODE_CITY` | `bali` | `barcelona` | `boston` | `delhi` | `menorca` | `santiago` |
| `NODE_LAT` | `-8.6500` | `41.3874` | `42.3601` | `28.6139` | `39.8885` | `-33.4489` |
| `NODE_LON` | `115.2167` | `2.1686` | `-71.0589` | `77.2090` | `4.2658` | `-70.6693` |
| `NODE_TZ` | `Asia/Makassar` | `Europe/Madrid` | `America/New_York` | `Asia/Kolkata` | `Europe/Madrid` | `America/Santiago` |
| `ALERT_LOCALE` | `id` | `es` | `en` | `en` | `es` | `es` |
| `BAD_ENABLED` | `1` | not set | not set | not set | not set | not set |
| `BAD_RADIUS_KM` | `8` | not set | not set | not set | not set | not set |
| `CKAN_PORTALS` | `bali-satu-data=https://balisatudata.baliprov.go.id` | `open-data-bcn=https://opendata-ajuntament.barcelona.cat/data` | `analyze-boston=https://data.boston.gov` | blank | `menorca=https://intranet.caib.es/opendatacataleg` | `datos-gob-cl=https://datos.gob.cl` |
| `NODE_ISSUES` | `air,heat,land,coast` | `heat,air` | `heat,air` | `air,heat` | `coast,heat,air,land` | `air,heat` |

## Known gaps

> **Gap in v0.91.0.** `REPORT_DEPTH` is declared, validated and offered in Set up, and nothing reads it.

> **Gap in v0.91.0.** Three runtime keys are stored and shown as in force when set from the dashboard, and a reader
> ignores the database value. `/presence`, the only reader of `NODE_KIND`, reads the environment. The Reticulum
> bridge reads `ACT_TOKEN` and `RETICULUM_ALERT_DESTINATIONS` from its own environment (the app itself does read the
> `ACT_TOKEN` override). Set these in `.env` and restart.

## Where this leads

The settings that decide what leaves the machine are on [Sharing and security](sharing.md), with what each one sends
and how coarse. The sensors the first groups point at are on [Sensors](sensors.md).
