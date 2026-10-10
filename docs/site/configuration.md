# Configuration
<!-- checked: v0.80.10 -->

A setting is a decision the household makes about its node: which sensors count as its own, what it
watches first, when it may interrupt somebody, what a stranger on the WiFi may read, whether a question
may leave the house for an online model. This page lists every setting a node has at v0.80, where its
value comes from, and what each group lets the node do. It was read against the code of v0.80: 63
runtime keys, 16 bootstrap keys, 26 keys declared by packs, and the keys read only from the environment.

## How a setting is read

The base is `.env` in the node's folder. `install.sh` writes it, it holds the tokens and the database
password, and it is never committed. Keep it `chmod 600`. Docker hands the whole file to the `app` and
`agent` containers at start, and to nothing else. The `reticulum` container gets eight named variables:
`LOG_LEVEL`, `NODE_NAME`, `NODE_API_URL`, `RETICULUM_CONFIGDIR`, `RETICULUM_DATA`,
`RETICULUM_ALERT_DESTINATIONS`, `RETICULUM_ANNOUNCE_S` and `ACT_TOKEN`. A process whose job is to speak to a
public radio mesh does not hold the Telegram token or the online model key, and `make lint` fails on a
compose file that hands the whole `.env` to any other service.

On top of `.env` sits the `settings` table in the database. A **runtime** setting can be overridden there
from four places: the dashboard's Set up view, `planetai config set`, `PUT /settings` with the admin token,
and the MCP `settings_set` tool. The override wins over `.env`, the node sees it within about 20 seconds
(the settings cache lives that long), and nothing needs a restart. Writing a blank value deletes the
override, and the node falls back to whatever `.env` says, then to the built-in default. `GET /settings`
reports the source of every value as `gui`, `env` or `default`, and `planetai config list` prints the
`.env` value in red when the database is overriding it, so the file is never silently wrong.

Every row of `GET /settings` also carries the `default` a fresh node gets. For the node's own keys it is
read from `data/env_defaults.yml`, which `tools/gen_defaults.py` generates from `.env.example`; `make lint`
fails when the two disagree. `ENV_DEFAULTS` points the app at another copy of the file.

A **bootstrap** setting is read once, by Docker when it composes the containers or by the process when it
starts: the node's name and position, the port, the compose profiles, the backup paths, the poll
interval. The dashboard shows these read-only. To change one, edit `.env` and run `planetai restart`.
`planetai config set` does the edit for you and offers the restart.

### Keys the packs declare

A pack lists its own keys under `env:` in its `pack.yaml`, with a comment above each. `GET /settings`
shows every installed pack's keys, whether the pack is switched on or not, in the group `packs`, with
the key as its label, the pack's default and help, and `restart: false`. They are there so a keeper can
see a pack's switch before turning it on. A key the pack also lists under `secrets:` in its `pack.yaml` is
masked like the node's own tokens, once saved and to everyone; every other pack key is shown in full to the
admin token and to the agent's `settings_get`. No pack that ships with the node lists one; a wild pack that holds a token or a key should.

They are set like a runtime key: from Set up, with `planetai config set`, or with `PUT /settings`, which
accepts any key an installed pack declares, switched on or not, and still answers 400 for a key nothing
declares. The save is one row in the actions ledger, the same as any other. A pack reads its keys from the
environment, so the node puts the database value there as well, and the pack has it the next time it runs,
within 20 s. Blank takes the key back to `.env`. A node that answers a pack key with 400 `<KEY> is not a runtime
setting` is older than this: update it, or set the key in `.env` and run `planetai restart`. `planetai packs install` appends the keys a `.env` is missing,
under a dated marker.

Three pack keys are also runtime keys: `COAST_MAX_KM`, `EE_PROJECT` and `EE_KEY_FILE`. `GET /settings` carries
each once, in `packs` with the pack's name beside it, so Set up draws it in that pack's card.

### Settings that take effect only at a restart

Some keys are runtime settings on paper and read with `os.getenv` by the code that acts on them, so a
dashboard override is stored, shown as in force, and ignored until the value is also in `.env` and the
container restarts:

| key | the reader that ignores the override |
|---|---|
| `NODE_KIND` | `/presence`, its only reader |
| `ACT_TOKEN`, `RETICULUM_ALERT_DESTINATIONS` | the Reticulum bridge, which reads its own environment. The app itself reads the `ACT_TOKEN` override |

The full list of what is declared and not read is under [Known gaps](#known-gaps-in-v080).

### Keys read only from the environment

`ADMIN_TOKEN`, `POSTGRES_PASSWORD`, `DATABASE_URL`, `OLLAMA_URL`, `AGENT_MODEL`, `MQTT_USER`, `MQTT_PASS`,
`RETICULUM_URL`, `OVERPASS_URL` and `BAD_BACKFILL_DAYS` are not runtime settings, not bootstrap settings and
not declared by any pack, so `GET /settings` does not list them and `planetai config set` says each is not a
setting this node has. Edit them in `.env` and restart. The tables below mark them `env only`.

### Validated values

Most settings are free text on purpose: a node has to keep running through a typo. Eleven keys refuse a
value they cannot honour, because a report interval the scheduler cannot keep would make the node silent
instead of wrong.

| Setting | Accepted |
|---|---|
| `REPORT_EVERY` | `3`, `4`, `6`, `8`, `12`, `24` |
| `REPORT_ANCHOR` | `0` to `23` |
| `REPORT_DEPTH` | `auto`, `brief`, `standard`, `deep` |
| `ALERT_ENGINE` | `rules`, `shadow`, `events` |
| `UI_MODE` | `simple`, `advanced`, `learn` |
| `AGENT_PREFER` | `private`, `fallback`, `strongest` |
| `SHARE_LEVEL` | `off`, `open` |
| `UI_ASK` | `on`, `off` |
| `UI_GROUND` | `svg`, `map` |
| `MAP_TILES` | `off`, `on` |
| `UPDATE_CHECK` | `on`, `off` |

`PUT /settings` answers 400 for anything else, and `GET /settings` publishes the list under `choices`, in
this order, so the dashboard and `planetai config` offer the values instead of a text box. `SHARE_LEVEL`
names `cell` and `means` in its help; both are reserved and refused today.

A number that ships blank in `.env` keeps the code default. `update.sh` copies new keys into your `.env`
with the value they carry in `.env.example`, and the `REPORT_*` keys ship blank so an updating node keeps
the rhythm it had.

### Public and outward

**Public** is the set of runtime keys whose value an anonymous `GET /settings` may see. Everything else
shows as `•••• set` until the admin token is presented. Chat ids, sensor hosts, account names and remote
URLs are not secrets, but they are the household's, and `GET /settings` answers anyone on the WiFi. At
`SHARE_LEVEL=off` a caller who is neither on this machine nor carrying a token sees the values of
`UI_LAYOUT` and `SHARE_LEVEL` only. A secret is masked for everyone, at every level; `GET /settings/raw`
with the admin token is the one unmasked read, and it covers the runtime keys only.

**Outward** marks the keys that change what leaves this machine, as opposed to what the node does with what
it keeps: who it speaks to, where it posts means, whether it announces itself on radio, whether the online
model is used at all. The node declares the set so every surface can draw those settings apart from the
one that says how far the sea is.

### Rules of the `.env` file

- No space after `=`. `VAR= value` is a shell command, not an assignment.
- A comment goes above a key that ships blank, never after it. Compose strips a trailing comment only when
  the key has a value, so `KEY=   # note` hands the container `# note` as the value. Node #1 once held the
  text of a comment in `AGENT_ONLINE_URL` this way. `make lint` fails on `.env.example` if it happens there.
- `planetai doctor` checks the file for stray spaces, and `update.sh` refuses to run until they are gone.

### Retired keys

`BRIEFINGS`, `BRIEF_MORNING`, `BRIEF_EVENING` and `BRIEF_HOUR` belonged to the two-briefings schedule.
Nothing reads them. Rows for them are left in `settings` and in `.env` so an updating node does not lose a
value it chose; a node that had `BRIEF_MORNING=7` is migrated once to `REPORT_EVERY=12`,
`REPORT_ANCHOR=7`, and a fresh install takes `6` and `6` from the defaults.

## The command line

`planetai config` works on the value in force: it reads `GET /settings`, so it sees the database overlay,
and falls back to `.env` when the node is down. Runtime keys are written through `PUT /settings` with
`X-Agent: planetai-cli`; bootstrap keys are written to `.env`.

| Command | What it does |
|---|---|
| `planetai config` | Guided walk: categories, then the settings in one. Changes are staged; `s` saves them in one call, `q` cancels, `b` goes back. Needs a terminal. |
| `planetai config --section G` | Straight into one category. The categories are the groups of `GET /settings`, in its order: `basics`, `sources`, `alerts`, `model`, `packs`, `keys`, `sharing`, `system`, and then `bootstrap`, which the dashboard shows read-only inside Basics and System instead. `packs` holds the two pack switches and every key the packs declare; every secret the node has is in `keys`, and a secret a pack declares stays in `packs`, masked. |
| `planetai config list [--section G]` | Every setting, its value in force and where it came from. Red means `.env` holds something else and is being ignored; a value set from the dashboard says so. |
| `planetai config get KEY` | One setting: its help, the value in force, its source, and whether `.env` disagrees. Says when a restart is needed. |
| `planetai config set KEY VALUE` | A runtime key goes to the database and the node has it within 20 s. A bootstrap key goes to `.env`, and the command offers `planetai restart`. A pack key goes to the database too, and the pack has it at its next run. |
| `planetai config unset KEY` | Removes the database override, back to `.env` or the built-in default. |
| `planetai config edit` | Opens `.env` in `$EDITOR` (nano by default) and offers a restart. This is what `planetai config` used to be. |

Shortcuts for the settings people change most:

| Command | Sets |
|---|---|
| `planetai report every N` | `REPORT_EVERY`, one of 3, 4, 6, 8, 12, 24. |
| `planetai report at H` | `REPORT_ANCHOR`, 0 to 23. |
| `planetai report level act\|warn\|info` | `ALERT_LEVEL`, what interrupts between reports. |
| `planetai telegram` | Validates the bot token with `getMe`, waits up to two minutes for you to message the bot, writes `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_IDS` to `.env` and to the runtime settings, sends a hello, recreates the app. |
| `planetai ui` | Creates `ADMIN_TOKEN` and `ACT_TOKEN` in `.env` if either is missing (and recreates the app), then prints the dashboard URLs, `SHARE_LEVEL` and the three tokens: admin, backup, act. |
| `planetai agent local pull <tag>` | `AGENT_MODEL`, after pulling the model, and recreates the `agent` container. |
| `planetai storage set backups DIR` · `set remote REMOTE:PATH` · `set keep DAYS` | `BACKUP_DIR` (checked to be a mount point and writable), `BACKUP_REMOTE`, `BACKUP_KEEP`. `set data` refuses and explains why `DATA_DIR` must be an internal disk. |
| `planetai packs install` | Appends the `env:` keys of every pack to `.env` under a dated marker, with their explanation lines, then rebuilds the app image. |

## Reference

Kind is `runtime` (database overlay, live within 20 s), `bootstrap` (read at start, edit `.env` and
restart), `pack` (declared in a `pack.yaml`, listed by `GET /settings`, set like a runtime key and put into
the pack's environment) or `env only` (read from the environment, not listed and not editable through the
API). `public` means an anonymous `GET /settings` may see the value; `outward` means the key changes what
leaves the machine; `secret` means the value is always masked; `restart` means `GET /settings` flags the key
as needing a restart.

The groups below follow what the node does with them: where it stands, who may read it, what it reads,
how it speaks, how it closes a loop, which model it thinks with, whom it reports to, where it keeps its
data, what it loads.

## Where it stands

| Setting | Default | Values | Meaning | Kind |
|---|---|---|---|---|
| `NODE_NAME` | `node`; `.env.example` ships `bayu-2` | lowercase, dashes | The node's name. Appears in `/health`, `/export`, the MQTT client id and Home Assistant ids, the pushes to a parent, and the `out/earth/<name>` folder. | bootstrap |
| `NODE_KIND` | `home` | `home`, `business`, `community`, `district` | What the node is for; not the Index scale. `planetai setup` sets `NODE_SCALE=city` for a district. Its only reader, `/presence`, reads the environment: set it in `.env` and restart. | runtime · public |
| `NODE_SCALE` | `community` | `community`, `city`, `region` | The Full Stack Metrics scale. Stamped on sensors that declare no scale, sent with pushes to a parent, in `/export`, and capitalised for the `Governance\|<Scale>` cell. | bootstrap |
| `NODE_CITY` | `unknown`; `.env.example` ships `bali` | pilot key or slug | The city key in Index cells, `/health` and `/export`, and the pilot `planetai sources` filters the registry by. `planetai setup` picks a pilot key by bounding box for bali, barcelona, boston and santiago, else a slug of the place. | bootstrap |
| `NODE_LAT`, `NODE_LON` | `0` | decimal degrees | The node's position. Handed to Postgres, used for local stamping, the first-start bootstrap, the presence cell and the ground map. Published as the centre of its resolution-8 cell in `/health`, `/export` and an untrusted `/sensors` and `/stats`; three decimals for this machine or a token; unrounded in `/forecast`, `/earth` and `/place/geojson`. `install.sh` refuses to start without them. | bootstrap |
| `NODE_TZ` | `UTC`; `.env.example` ships `Asia/Makassar` | IANA name | The database session time zone: local midnight and local hours in rules, reports, quiet hours and the hour-of-day pattern in `/shape`. Also `TZ` of the agent container; echoed in `/health`. | bootstrap |
| `NODE_ISSUES` | blank = every issue | comma list of `air`, `heat`, `land`, `coast` | What this place watches, most important first. The first is where the dashboard starts; the one with something to say takes the top. A name nothing declares is ignored with a line in the log. Your preset guessed for this place; change it. | runtime · public |
| `NODE_VERSION` | written by `install.sh` and `update.sh` | string | `git describe`, the `VERSION` file, or `dev`. Shown in `/health`, `/presence`, `/export`. | env only |
| `LOCAL_RADIUS_M` | `500` | metres | How far from the node a sensor can be and still count as this node's own. A kit of yours further than this is yours but not here: it stays out of the ambient average and out of every `live` claim. | runtime · public |

## Who may read it

| Setting | Default | Values | Meaning | Kind |
|---|---|---|---|---|
| `SHARE_LEVEL` | `off` | `off`, `open` | What a request with no token may read. `off` = the dashboard shell, `/health` with the position rounded, the daily export and the layout, and nothing else. `open` = the whole read API to anything on your network, so a wall screen or a phone works with no token; writes still need one. A request with a token reads everything at either level. See [Sharing and security](sharing.md). | runtime · public · outward |
| `ADMIN_TOKEN` | blank; `install.sh` generates one | hex string | Opens `PUT /settings`, `/settings/raw`, `POST /readings`, `/report/now`, `/test-alert` and the whole `/mcp`; also accepted where `BACKUP_TOKEN` or `ACT_TOKEN` would be. `planetai ui` creates and prints it. | env only · secret |
| `BACKUP_TOKEN` | blank; `update.sh` generates one | string | Read-only: lets a NAS fetch `/backups`, `/backups/<name>` and `/report/bundle`. Separate from the admin token and cannot read `/settings/raw`. `planetai ui` prints it; `planetai storage` reports whether it is set. | runtime · secret |
| `POSTGRES_PASSWORD` | `change-me`; `install.sh` replaces it | string | The database password, composed into `DATABASE_URL` by Docker. | env only · secret |
| `DATABASE_URL` | set by `docker-compose.yml` | URL | The database connection the app and the settings module use. Compose-internal; nothing to set by hand. | env only |
| `LOG_LEVEL` | `INFO` | Python logging level | Log level of the app and the Reticulum bridge. | env only |

## How the page draws it

| Setting | Default | Values | Meaning | Kind |
|---|---|---|---|---|
| `UI_MODE` | `advanced` | `simple`, `advanced`, `learn` | What the page opens as. `simple` = what a person in the house asks: is it fine, is anything changing, is there something to do. `advanced` = every section. `learn` = the advanced page with a question mark at each part; a pressed mark quotes the node's own documentation for it in the ask pane. Anyone reading can switch from the header; their browser remembers it and nothing changes for anybody else. | runtime · public |
| `UI_ASK` | `on` | `on`, `off` | `on` = a toggle on the dashboard opens the ask pane, which asks the model Set up → Model names about what the page shows, reads, changes nothing and keeps nothing. `off` = no toggle and no pane. See [Ask the node](ask.md). | runtime · public |
| `UI_GROUND` | `svg` | `svg`, `map` | How the ground is drawn. `svg` = the drawing the page has always made. `map` = MapLibre and deck.gl draw it in the browser, so it pans and zooms; it needs WebGL2 and falls back to `svg`, saying why, without it. The two libraries (860 kB gzipped, 3.2 MB as the node serves them) are fetched from the node only when the ground is drawn this way. Neither value changes what leaves the house: `MAP_TILES` decides that. | runtime · public |
| `UI_LAYOUT` | blank | JSON | Order and visibility of the dashboard's cards. Managed by the dashboard's Arrange mode; blank restores the default. Readable by every screen in the house at every level. | runtime · public |
| `MAP_TILES` | `off` | `off`, `on` | Live satellite and street tiles under the cells. Each tile request tells a tile server which square of the planet this house is looking at. `off` = tiles from the node's local copy of OpenStreetMap; `on` = live tiles. A keeper turns this on in Set up. | runtime · public |
| `UPDATE_CHECK` | `on` | `on`, `off` | Once a day, ask planetai.fab.city which version is current. When a newer one is out, the page's header, `planetai doctor` and Telegram (once per version, after quiet hours) say so. Nothing is installed: `planetai update` stays yours to run. The request carries nothing about the house, but it shows this house's internet address to Fab City's host; see [what leaves](sharing.md). `off` = the node never asks. | runtime · public · outward |
| `STATIONS_SHOWN` | `3` | integer, `0` = all | How many of the neighbourhood's stations the dashboard lists, nearest first. This node's own hardware is always listed and never counted. Nothing is discarded: the page says how many it is not listing. To collect fewer stations, turn `BAD_RADIUS_KM` down instead. | runtime · public |

## What it reads

| Setting | Default | Values | Meaning | Kind |
|---|---|---|---|---|
| `SC_DEVICES` | blank | comma-separated kit ids | Smart Citizen kits read directly from the cloud API, the number in `smartcitizen.me/kits/<id>`. Always treated as yours, at this address. Any id enables the adapter. | runtime |
| `SC_USER` | blank | username | Discover every kit on a Smart Citizen account instead of listing ids. Indoor or outdoor comes from each kit's own setting. Also used by `/nearby?audit=1`. | runtime |
| `SC_EXCLUDE` | blank | comma-separated kit ids | Account kits that belong to another site. | runtime |
| `AIRGRADIENT_HOSTS` | blank | comma-separated hostnames or IPs | AirGradient ONE or Open Air units on your WiFi. In v0.80 the key only keeps these units out of the Bali Air Dispatch ring; see [Known gaps](#known-gaps-in-v080). | runtime |
| `PURPLEAIR_HOSTS` | blank | comma-separated IPs | PurpleAir units on your WiFi. Use the IP; the `.local` name is unreliable. Nothing reads this key in v0.80. | runtime |
| `SENSOR_INDOOR` | `0` | `1`, `0` | Whether the LAN sensors above are indoors. Smart Citizen carries this itself. Nothing reads this key in v0.80. | runtime · public |
| `BAD_ENABLED` | `0`; `.env.example` and the bali preset ship `1` | `1`, `0` | Bali only: the island's public stations from Bali Air Dispatch as outdoor reference. Needs `NODE_LAT`. `planetai setup` sets `0` outside Bali. | runtime · public |
| `BAD_RADIUS_KM` | `15`; bali preset `8` | km | How far out the ring of other people's stations reaches. Also `/nearby.radius_km`. | runtime · public |
| `BAD_MIN_SEPARATION_M` | `150` | metres | A station closer than this to the node is assumed to be the node's own hardware, not a neighbour. | runtime · public |
| `BAD_EXCLUDE` | blank | comma-separated station ids | Stations that are ours and the identity and distance rules missed. | runtime · public |
| `BAD_INCLUDE_INDOOR` | `0` | `1`, `0` | `1` keeps stations the archive suspects are indoors. Off by default: they are not the ring. | runtime · public |
| `BAD_BACKFILL_DAYS` | `0` | days | Size of the one-off history fetch by `planetai run nearby backfill`. Off by default: it is a large fetch against someone else's server. The script's argument overrides it. | env only |
| `OPENMETEO_ENABLED` | `1` | `1`, `0` | Open-Meteo weather and CAMS air model point samples at the node's coordinates, two adapters. Free, key-free, anywhere. Context from the planet scale, never rolled into an index cell. Needs `NODE_LAT`. | runtime · public |
| `BOOTSTRAP` | `1` | `1`, `0` | On first start, fill the database from 92 days of CAMS history and NASA POWER climatology at these coordinates. Skipped once `cams-point` history older than two days exists. `0` starts empty. | env only |
| `CKAN_PORTALS` | blank | `slug=url,slug=url` | CKAN open-data portals to watch. One adapter reads any CKAN portal; feeds the `Governance\|City` cell. The presets fill this per city. | runtime · outward |
| `CKAN_SCALE` | `city` | scale string | The scale stamped on CKAN observations. | env only |
| `POLL_SECONDS` | `300` | seconds | How often the source loop polls. | bootstrap |
| `MESH_INDOOR_NODES` | blank | comma-separated `!hex` ids | Meshtastic radios that are indoors, e.g. `!8f491db0,!64e0bfd1`. Mesh sensors default to outdoor. | runtime |
| `MQTT_HOST` | blank | hostname | The broker. When set, the MQTT thread starts and subscribes to `msh/#`, `planetai/sensors/#` and `device/sck/#`. `planetai meshtastic` and `planetai broker` set it. | bootstrap |
| `SC_FORWARD` | blank | comma-separated device tokens | Kits and DIY nodes publishing to this node's broker whose messages are passed on to smartcitizen.me unchanged (QoS 1, TLS verified), through a queue that survives an internet outage. Blank forwards nothing. See [Sensors](sensors.md). | runtime · secret · outward |
| `MQTT_USER`, `MQTT_PASS` | blank | strings | Broker credentials. `planetai meshtastic` generates them and writes the broker's password file. | env only · secret |
| `SOURCES_DIR` | `/app/data/sources` | path inside the container | Where the app reads the vendored source registry that `GET /sources` serves. Mounted read-only from `./data`. | env only |

> **Gap in v0.80.10.** `SENSOR_INDOOR` and `PURPLEAIR_HOSTS` are read by nothing, and `AIRGRADIENT_HOSTS`
> only keeps those units out of the Bali Air Dispatch ring. The AirGradient and PurpleAir adapters exist
> and are tested; the node does not register them for polling.

The sources that come in packs (ThingData servers, the forecast, the earth and place
data, the nearest fab lab) are set with the pack keys in [What the packs declare](#what-the-packs-declare).

## How it speaks

| Setting | Default | Values | Meaning | Kind |
|---|---|---|---|---|
| `TELEGRAM_BOT_TOKEN` | blank | BotFather token | Alerts and reports to Telegram. Blank = they go to the log only. Never shown again once saved. `planetai telegram` sets it. | runtime · secret · outward |
| `TELEGRAM_CHAT_IDS` | blank | comma-separated ids | Recipients. Add the bot to a group, or let `planetai telegram` find yours. | runtime · outward |
| `TELEGRAM_BUTTONS` | `0` | `1`, `0` | `1` = an event's message carries Done / Not now / Doesn't fit, and the bot in the agent container records the press (the same row the dashboard's buttons write). The bot sets this on startup, so the buttons ride only while somebody answers them; leave it alone. | runtime |
| `ALERT_LEVEL` | `act` | `act`, `warn`, `info` | What interrupts you between reports. `act` = only when something needs doing; `warn` = also when something changed; `info` = everything. Everything is recorded regardless, on the dashboard and in the next report. | runtime · public |
| `QUIET_HOURS` | `1` | `1`, `0` | `1` = between the hours below only act-level alerts are sent; the rest wait for the morning report. A report due in quiet hours is held and folded into the next. | runtime · public |
| `QUIET_FROM` | `22` | local hour | When quiet hours start. | runtime · public |
| `QUIET_TO` | `6` | local hour | When quiet hours end. | runtime · public |
| `ALERT_ENGINE` | `rules` | `rules`, `shadow`, `events` | `rules` = every rule sends on its own. `shadow` = the event engine (`docs/SPEC_alerts.md`) records what it would send in `event_messages` and sends nothing; the rules keep sending. `events` = the engine sends the heat and air messages, one per event, with the three buttons when the bot runs (`TELEGRAM_BUTTONS`); the old heat and air rules still record their alerts but no longer send, and every other alert and the reports are unchanged. On `shadow` and `events`, an issue's state on the dashboard follows its alert event, and the old heat and air alerts are no longer open asks. | runtime |
| `ALERT_MAX_PER_DAY` | `4` | whole number | With the event engine: pushes a day outside danger. Beyond it an event is recorded and waits for the next report. Danger is never held. | runtime |
| `HOME_HAS` | empty | `purifier`, `ac`, `fan`, `windows`, comma-separated | What this home has. The event engine only suggests what is here to use. | runtime |
| `ALERT_LOCALE` | `en` | `en`, `id`, `es` | The language of the alert rules, the reports, the test alert and the bot's own replies; every `rules.yml` carries all three. The dashboard and the terminal stay in English. Anything else falls back to English. Echoed in `/health.locale`; read by the agent loop too. | runtime · public |
| `HA_DISCOVERY` | `0` | `1`, `0` | `1` publishes local sensors and alerts as Home Assistant entities over MQTT discovery. Needs `MQTT_HOST`. `planetai homeassistant` sets it. | runtime · public · outward |
| `MESH_ALERTS` | `0` | `1`, `0` | `1` sends the first line of act-level alerts back over the LoRa mesh through the gateway radio. Needs downlink enabled on the gateway's channel. | runtime · public · outward |
| `MESH_GATEWAY_NODE_NUM` | `0` | decimal integer | The gateway's node number, used as the sender for downlink. `planetai meshtastic` shows how to find it. | runtime |
| `RETICULUM_URL` | blank; `planetai reticulum` sets `http://reticulum:4243` | URL | The bridge. When set, act alerts are posted to its `/send` and the node polls it for `/health.reticulum`. | env only |
| `RETICULUM_ALERT_DESTINATIONS` | blank | comma-separated LXMF hashes | Where the bridge delivers act alerts. Addresses from Sideband, no spaces. The bridge reads it from its own environment: set it in `.env` and restart the bridge. | runtime · outward |
| `RETICULUM_PRESENCE` | `0` | `1`, `0` | `1` announces the node's name and a coarse map cell every half hour, so other PLANETAI nodes can see that it exists and how far away it is. No readings, no address, nothing else, and nothing at all while this is `0`. `SHARE_LEVEL` governs what the node answers; this is the node speaking unprompted. | runtime · public · outward |
| `RETICULUM_PRESENCE_RES` | `3` | H3 resolution `0` to `6` | How exactly the announce places this node, and the whole of the privacy decision. `3` is about 60 km across and says the island; `4` about 22 km; `5` about 8 km. Anything finer than `6` is clamped to `6`: a node announcing its street to an open radio network is not a thing to do by typing a number. | runtime · public · outward |
| `RETICULUM_ANNOUNCE_S` | `1800` | seconds | The bridge's announce interval; echoed in `/health.reticulum.announce_s`. | env only |
| `RETICULUM_DATA`, `RETICULUM_CONFIGDIR`, `NODE_API_URL` | `/data`, `/etc/reticulum`, `http://app:8080` | paths, URL | Bridge container internals, set by `docker-compose.yml`. Nothing to set by hand. | env only |

## When it reports

One report every `REPORT_EVERY` hours in the node's own time zone, starting from `REPORT_ANCHOR`. A report
is written in the first 20 minutes of a due hour; the `reports` row for that hour is the lock, so it is
written once.

| Setting | Default | Values | Meaning | Kind |
|---|---|---|---|---|
| `REPORT_EVERY` | blank = `6` | `3`, `4`, `6`, `8`, `12`, `24` | Hours between reports. `6` is four a day. Each accepted value divides 24, so the rhythm does not walk round the clock. Also the default window of `/report/bundle`. | runtime · public |
| `REPORT_ANCHOR` | blank = `6` | `0` to `23` | The local hour the rhythm starts from. With a 6-hour interval, `6` gives 06, 12, 18 and 00. | runtime · public |
| `REPORT_DEPTH` | blank = `auto` | `auto`, `brief`, `standard`, `deep` | How much the report says. `auto` lets the strongest model the node can reach decide. Nothing reads it in v0.80. | runtime · public |

> **Gap in v0.80.10.** `REPORT_DEPTH` is declared, validated and offered in Set up, and nothing reads it.
> Changing it changes nothing.

## How it closes a loop

| Setting | Default | Values | Meaning | Kind |
|---|---|---|---|---|
| `ACT_TOKEN` | blank; `planetai ui` generates one | string | Lets someone in the house record that they acted on an alert (`POST /actions`) from off this machine without holding the admin token. It cannot read a secret or change a setting. The dashboard's forms for recording an act or a decision send it, or the admin token, from the browser. The Reticulum bridge posts actions with the copy in its own environment. | runtime · secret |
| `DECISION_REQUIRED` | `0` | `0`, `1` | `0` records an act whenever somebody says they did something. `1` refuses an act (409) unless a decision was recorded against the same alert first, which is what a node acting for a street rather than a house usually wants. It applies to every way in: the dashboard, Telegram, the radio and the terminal. Turn it on only where everybody answering has a screen to decide on. | runtime |

## Which model it thinks with

Read by the agent loop in the `agent` container (compose profile `agent`), which builds its ladder of
models from `/settings/raw`, with the environment as fallback, and re-reads it every minute, so a change on
Set up → Model on the dashboard reaches the bot within about a minute although `GET /settings` flags these keys
`restart`. `planetai agent local` installs Ollama and starts the container. The dashboard's ask pane reads
the same keys in the app container on every question, so one choice governs both; the pane asks the model on
this machine only when `planetai agent local` set one up. See [Ask the node](ask.md).

| Setting | Default | Values | Meaning | Kind |
|---|---|---|---|---|
| `AGENT_PREFER` | `private` | `private`, `fallback`, `strongest` | `private` never uses the online model: nothing leaves your network, and it is what the node does until somebody here chooses otherwise. `fallback` tries your own remote model, then online, then the small local one. `strongest` puts online first, so every question goes to the online model whenever a key is set. | runtime · public · outward · restart |
| `AGENT_ONLINE_URL` | blank | `https://api.anthropic.com/v1`, `https://api.openai.com/v1`, … | An OpenAI-compatible online endpoint. The URL and nothing else; a value that does not start with `http` is not a rung, and the agent logs it and skips it. The rung exists only when the key is set too. | runtime · outward · restart |
| `AGENT_ONLINE_MODEL` | `claude-sonnet-4-6` | model id | Ask the key which models it can see (`GET $AGENT_ONLINE_URL/models`) and paste an id from that list. A retired model answers 404, which reads like a bad key. | runtime · public · outward · restart |
| `AGENT_ONLINE_KEY` | blank | secret | The only thing that lets household data leave your network. Your choice. | runtime · secret · outward · restart |
| `AGENT_REMOTE_URL` | blank | `http://<host>:8082/v1` | A bigger local model on your tailnet, OpenAI-compatible. | runtime · restart |
| `AGENT_REMOTE_MODEL` | `gpt-oss-120b` | model id | e.g. `gpt-oss-120b` or `qwen3:8b`. | runtime · public · restart |
| `AGENT_REMOTE_KEY` | blank | secret | If that server asks for one. | runtime · secret · restart |
| `OLLAMA_URL` | `http://host.docker.internal:11434` | URL | Ollama on this machine, the `local` rung. `planetai agent local` sets `http://172.17.0.1:11434` on Linux. | env only |
| `AGENT_MODEL` | `qwen3:4b` | Ollama model | The local rung's model, passed to the container as `MODEL`. `planetai agent local pull <tag>` pulls a model and sets this; `planetai agent local` recommends `qwen3.5:4b` below 16 GB of memory and `qwen3.5:9b` at 16 GB or more. It must do tool calling. | env only |
| `AGENT_NAME` | `local-model` | string | How the agent's actions appear in the audit trail, sent as `X-Agent`. | env only |
| `MCP_URL` | `http://app:8080/mcp` | URL | Where the loop reaches the node's MCP. Compose-internal. | env only |
| `COMPOSE_PROFILES` | blank | comma-separated `mqtt`, `agent`, `ipfs`, `reticulum` | Which optional containers run. Blank = the two base containers only. Set by `planetai meshtastic`, `agent local`, `ipfs` and `reticulum`; leave alone by hand. | bootstrap |

## Whom it reports to

A node with a parent posts hourly means to `PARENT_API_URL/aggregates` and alert timestamps to
`PARENT_API_URL/events`, with `PARENT_TOKEN` as Bearer and `NODE_SCALE` as `scale`. Values and
timestamps go up; where, what was said and who said it stay. A node that is a parent demands
`AGGREGATE_TOKEN` from its children. Leave all three empty on node #1.

| Setting | Default | Values | Meaning | Kind |
|---|---|---|---|---|
| `PARENT_API_URL` | blank = none | `http://<district>:8080` | The parent node. When set, hourly `POST /aggregates` and `POST /events` go there. | runtime · outward |
| `PARENT_TOKEN` | blank | string | What this node presents to its parent. | runtime · secret |
| `AGGREGATE_TOKEN` | blank | string | What this node demands from its children on `POST /aggregates` and `POST /events`. Without it the node accepts no children at all (403). Set it before pointing another node at this one. | runtime · secret |

## Where it keeps its data

All read by `docker-compose.yml` or `backup.sh`, the nightly cron job. `planetai storage` shows the state of
each and `planetai storage set` changes the first three.

| Setting | Default | Values | Meaning | Kind |
|---|---|---|---|---|
| `DATA_DIR` | blank = the Docker volume `db` | path | Where the live database lives. A path is a local disk or partition only; never a NAS. `planetai storage set data` refuses for that reason. | bootstrap |
| `BACKUP_DIR` | `./backups` | path | Where `pg_dump` files go. If it is a mount point it must be mounted, or the backup refuses. | bootstrap |
| `BACKUP_KEEP` | `30` | days | Days of dumps kept in `BACKUP_DIR`. | bootstrap |
| `BACKUP_REMOTE` | blank | rclone `remote:path` | Off-machine copy after each backup: S3, B2, R2, Drive, Dropbox, SFTP, WebDAV, Nextcloud. Run `rclone config` once. | bootstrap |
| `EXPORT_ENABLED` | `1` | `1`, `0` | Each night fetch `GET /export?day=` for yesterday and write `exports/<node>/YYYY-MM-DD.json`: hourly means, cells, alerts, rho, never raw. | bootstrap |
| `IPFS_PUBLISH` | `0` | `1`, `0` | `ipfs add` each export through the `ipfs` container and record the CID in `exports/<node>/CIDS.txt`. `planetai ipfs` turns it on and starts the container. | bootstrap |
| `APP_PORT` | `8080` | port | The host port, published on every interface. Change it if something else on this machine uses 8080. `backup.sh` and the CLI reach the node on `localhost:$APP_PORT`. | bootstrap |

## What it loads

| Setting | Default | Values | Meaning | Kind |
|---|---|---|---|---|
| `PACKS_ENABLED` | blank = every pack in `packs/` | comma-separated pack ids | Which packs load. | runtime · public |
| `PACKS_ALLOW_CODE` | `0` | `1`, `0` | Data packs (rules, cells) always load. Code packs (`adapter.py`) run Python with this node's privileges: read them first, then set `1`. | runtime · public |
| `PACKS_DIR` | `/app/packs` | path inside the container | The pack directory. | env only |
| `PACK_OUT` | `/app/out` | path inside the container | The writable folder for pack artifacts, mounted from `./out`. `planetai run` passes it to every script. | env only |
| `RULES_PATH` | `/app/config/rules.yml` | path inside the container | The core rules file. | env only |
| `CHANNELS_PATH` | `/app/config/channels.yml` | path inside the container | The channel-role declarations packs contribute to. | env only |
| `ENV_DEFAULTS` | `/app/data/env_defaults.yml` | path inside the container | The generated defaults each row of `GET /settings` reports. | env only |

## What the packs declare

Every key a `pack.yaml` declares, with the default it ships. All are kind `pack`: listed by
`GET /settings` in group `packs` and set like a runtime key; the pack's own code reads them from the
environment, where the node puts the database value. A code pack reads none of them until
`PACKS_ALLOW_CODE=1`.

| Setting | Pack | Default | Meaning |
|---|---|---|---|
| `MAKE_ENABLED` | make | `0` | The make pack's own switch, off by default and on purpose: the Fab Lab Network directory it reads is not openly licensed, each lab keeps copyright in its own record, and the Fab City Foundation's decision to read it covers the Foundation, not you. Read [packs/make/README.md](../../packs/make/README.md), then set `1`. It needs `PACKS_ALLOW_CODE=1` too. |
| `MAKE_RADIUS_KM` | make | `50` | How far to look for a fab lab, in km. 50 is a morning's travel in most places. `planetai doctor` reports how many lie inside it. |
| `MAKE_SOURCE` | make | `archive` | `archive` reads the dated monthly snapshots, which can be pinned; `live` reads api.fablabs.io, whose own root page says it has been removed. |
| `MAKE_SNAPSHOT` | make | blank = the newest | Which dated snapshot to read. Pin it to a filename like `2026.07.31_labs.json` and every node on this release answers the same question the same way. |
| `MAKE_REFRESH_DAYS` | make | `30` | How often to re-read. The archive is published monthly. One read is about 5.3 MB. |
| `THINGDATA_INSTANCES` | thingdata | blank | The ThingData servers to read, `slug=url`, comma-separated. Blank and the pack idles. |
| `THINGDATA_SCALE` | thingdata | `city` | The scale of what those servers cover, `city` or `region`. |
| `THINGDATA_MAX` | thingdata | `5000` | Refuse to count a collection larger than this (one page is 100 rows), rather than report a truncated total as a total. |
| `FORECAST_BMKG` | forecast | `1` | Read BMKG, Indonesia's meteorological agency. |
| `FORECAST_BMKG_ADM4` | forecast | blank | The village code BMKG needs for this point. `planetai run forecast verify` proves it resolves to somewhere near the node. |
| `FORECAST_OPENMETEO` | forecast | `0` | Read Open-Meteo. It works anywhere, but its free tier is non-commercial only, so it is the operator's decision. Off until you turn it on. |
| `FORECAST_POLL_HOURS` | forecast | `6` | Declared as how often to ask. Nothing reads it in v0.80. |
| `FORECAST_WIND_N` | forecast | `8` | The wind field for the map: points a side, so 64 points. Only with `FORECAST_OPENMETEO=1`. |
| `FORECAST_WIND_KM` | forecast | `30` | The wind field's half-width in km round the node. |
| `EARTH_RADIUS_M` | earth | `5000` | Half-width of the square around the node. 5000 is a 10 km square, about 64 MB on disk and 103 MB pulled per year. Also `/earth.radius_m`. |
| `EARTH_YEARS` | earth | blank = every year | Which years to fetch, comma-separated. The dataset has 2017 to 2025. |
| `PLACE_RADIUS_M` | place | `1000` | The radius around the node to describe from OpenStreetMap. Also `/place/geojson.radius_m`. |
| `PLACE_REFRESH_DAYS` | place | `30` | How often to fetch from Overpass again. A moved node refetches at once. |
| `GROUND_RADIUS_KM` | place | `12` | `planetai run place basemap`: half-width in km of the street-level square of vector tiles kept on disk. `planetai run earth-engine basemap` reads it too, for its detailed ring. |
| `GROUND_DRONE_RADIUS_KM` | place | `4` | `planetai run place basemap`: how far round the node to look for OpenAerialMap drone mosaics, in km. |
| `GROUND_DRONE_MAXZ` | place | `18` | The finest zoom of drone tiles kept. |
| `EE_PROJECT` | earth-engine | blank = read from the key file | Earth Engine project id, not the service account number. Also a runtime key. |
| `EE_SERVICE_ACCOUNT` | earth-engine | blank = the key file names it | The Earth Engine service account. |
| `EE_KEY_FILE` | earth-engine | `/app/config/ee-key.json` | The service-account JSON key; copy it to `config/ee-key.json` on the node. Also a runtime key. |
| `GROUND_SAT_WIDE_KM` | earth-engine | `60` | `planetai run earth-engine basemap`: half-width in km of the wide Sentinel-2 context square; the detailed one is `GROUND_RADIUS_KM`. |
| `COAST_MAX_KM` | coast | `30` | Refuse to report if the nearest ocean grid cell is further away than this, in km. Also a runtime key (public): the override moves both the dashboard's drawn footprint and the adapter's refusal. |

> **Gap in v0.80.10.** `FORECAST_POLL_HOURS` is declared and read by nothing.

`OVERPASS_URL` (default `https://overpass-api.de/api/interpreter`, the place pack's Overpass endpoint) is
read by the place pack but declared in no `pack.yaml`, so it is `env only`.

## Presets

A preset is a file in `presets/` that `install.sh --preset` copies into `.env` before it applies the
flags, so coordinates given on the command line override the preset's centre. Four are Fab City Index
pilots; Delhi and Menorca are not. Every preset sets exactly these keys and nothing else, and every
preset guesses `NODE_ISSUES`: change it, because what matters here is decided by the people who live here.

| Key | bali | barcelona | boston | delhi | menorca | santiago |
|---|---|---|---|---|---|---|
| `NODE_CITY` | `bali` | `barcelona` | `boston` | `delhi` | `menorca` | `santiago` |
| `NODE_LAT` | `-8.6500` | `41.3874` | `42.3601` | `28.6139` | `39.8885` | `-33.4489` |
| `NODE_LON` | `115.2167` | `2.1686` | `-71.0589` | `77.2090` | `4.2658` | `-70.6693` |
| `NODE_TZ` | `Asia/Makassar` | `Europe/Madrid` | `America/New_York` | `Asia/Kolkata` | `Europe/Madrid` | `America/Santiago` |
| `ALERT_LOCALE` | `id` | `es` | `en` | `en` | `es` | `es` |
| `BAD_ENABLED` | `1` | `0` | `0` | `0` | `0` | `0` |
| `BAD_RADIUS_KM` | `8` | not set | not set | not set | not set | not set |
| `CKAN_PORTALS` | `bali-satu-data=https://balisatudata.baliprov.go.id` | `open-data-bcn=https://opendata-ajuntament.barcelona.cat/data` | `analyze-boston=https://data.boston.gov` | blank | `menorca=https://intranet.caib.es/opendatacataleg` | `datos-gob-cl=https://datos.gob.cl` |
| `NODE_ISSUES` | `air,heat,land,coast` | `heat,air` | `heat,air` | `air,heat` | `coast,heat,air,land` | `air,heat` |

`planetai setup` picks the preset itself when the geocoded place falls inside the bali, barcelona, boston
or santiago bounding box.

## Known gaps in v0.80

- `AIRGRADIENT_HOSTS` and `PURPLEAIR_HOSTS` are declared and the adapters exist and are tested, but the
  node does not register them for polling. `AIRGRADIENT_HOSTS` is used only to keep those units out of
  the Bali Air Dispatch ring; `PURPLEAIR_HOSTS` is read by nothing.
- `SENSOR_INDOOR` has no reader anywhere in the app or the packs.
- `REPORT_DEPTH` is declared and validated but read by nothing outside the settings module.
- `FORECAST_POLL_HOURS` is declared by the forecast pack and read by nothing.
- `NODE_KIND` accepts a runtime override that `/presence`, its only reader, never sees. Set it in `.env`
  and restart.
- `ACT_TOKEN` and `RETICULUM_ALERT_DESTINATIONS` set from the dashboard do not reach the Reticulum bridge,
  which reads its own environment. Set them in `.env` and restart the bridge.
- `FCI_PUBLISHER`, `ALLOWED_CITIES` and `PEERS` are named in other documents and are not present in this
  code.

## Where this leads

The settings that decide what leaves the machine are on [Sharing and security](sharing.md), with what
each one sends and how coarse. The sensors the first groups point at are on [Sensors](sensors.md).
