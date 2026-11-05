# Command line
<!-- checked: v0.91.0 -->

`planetai` is how the person who keeps a node looks after it from the machine it runs on: install it, check
it is alive, record what somebody did about an alert, change a setting, update it and keep its data safe.
The commands that read or change a running node do it over its [API](api.md) on `localhost:$APP_PORT`, with the
tokens in `.env`, so what they print is what the node is doing now. A few work without one: `planetai preflight`
runs before there is a node, and `planetai sources` reads the pinned registry when the node does not answer.

It is one bash script, `bin/planetai`, linked into `~/.local/bin`. It needs only the Python the machine already
has (Apple's 3.9 on a Mac, standard library only). `planetai` on its own prints the command list. A word the node
does not know gets "there is no `planetai <word>` in this node", the node's version, and the advice to run
`planetai update`, because new commands arrive with releases.

> **Gap in v0.91.0.** The list `planetai` prints leaves out four commands that exist: `preflight`, `sources`,
> `config unset` and `agent local pull`. The tables below are complete.

Only three things ask for `sudo`: `mesh` (to install and join Tailscale), `agent local` on a machine with
`systemctl` where Ollama is not already answering, and `setup` when the installer has to install or start
Docker. The installer says what each `sudo` is for before it asks.

## Set up and remove

| command | what it does |
|---|---|
| `planetai preflight [--json]` | Checks whether this machine can run a node. Installs nothing. Exit `0` go, `1` something you can fix (each ✗ says how), `2` no container runtime can run on this OS version. |
| `planetai setup` | Runs the preflight, asks four questions (name, place, what the node is for, a Smart Citizen kit or none) and installs, with the city's [preset](configuration.md#presets) for a place in Bali, Barcelona, Boston or Santiago. Where a node exists it offers update, reconfigure, nothing or remove, and after an unfinished install it offers to carry on. |
| `planetai setup --answers node.json` | The same install with no terminal, from a JSON file: `{"name": "my-node", "place": "Palma de Mallorca", "kind": "home", "sensor": {}}`. `lat` and `lon` can replace `place`; `sensor` is `{}` or one of `{"sc": "19880"}`, `{"sc_user": "you"}`, `{"airgradient": "host"}`, `{"purpleair": "ip"}`. See [Install](install.md). |
| `planetai geocode <place>` | What the setup wizard would find for a place name, without installing anything. |
| `planetai version` (`-v`, `--version`) | The version, the node's name and city, and the key it takes updates from: `updates signed by  fabcity  <fingerprint>`. |
| `planetai remove [--keep-data]` (`uninstall`) | Asks twice (yes, then the node's name), removes the containers, the database (kept with `--keep-data`), the folder with any backups in it, the crontab line and the command, then checks nothing is left. |

## Check on it

| command | what it does |
|---|---|
| `planetai status [--json]` | Version, uptime, last poll and error, sensors, the last three alerts and ρ. |
| `planetai doctor [quiet\|--guide\|--json]` | Every check, each failure with its fix, then the node's data sources. |
| `planetai logs [service]` | Follows a container's log: `app` by default, or `db`, `agent`, `reticulum`, `mosquitto`. |
| `planetai start` · `stop` · `restart` | `docker compose up -d`; `down`, data kept; recreate the app container, which is how a change in `.env` takes effect. |

The doctor checks that Docker runs, the containers are up, the database answers, the node answers on its port and
can log in to the database, the coordinates are set, `.env` has no space after an `=`, the backup folder is mounted,
the captures folder is writable, the crontab line that lets Install on Set up › Packs reach the node is there, a nightly
backup is scheduled and more than 1 GB is free. With the `mqtt` profile
it checks the broker and that mesh packets arrive; with `reticulum`, the bridge. A few rows state a fact rather than
pass or fail:

| row | what it says | when it is not green |
|---|---|---|
| `release signature verified on last update` | the last `planetai update` checked who built the tarball | red when that update ran with `PLANETAI_UNSIGNED=1` or predates signed releases. A git checkout has no such row. |
| `source registry: N entries · awesome-fabcity-data @ <sha> · synced <date>` | which snapshot of the [source registry](sources.md) this node carries | red when `data/sources/REGISTRY_VERSION` is missing, amber when the pin is over 180 days old. Amber does not fail the run. |
| `PLANETAI <version> is out` | a newer release exists | amber, never red. Absent when `UPDATE_CHECK` is off. |
| `make: …` | `off` with the licence reason, or how many fab labs lie within `MAKE_RADIUS_KM`, from which snapshot | never. Shown only when the `make` pack is installed and `PACKS_ALLOW_CODE=1`. |

Under the checks, **Data sources** lists what every node needs for its basic job, from
[`GET /health/sources`](api.md), most important first. Each row is ✓, ✗ with its fix, or a dash when it does not
apply or has not had its first poll:

```
  Data sources
  ✓ Your own sensors                         4 min ago · inside only; one outside would tell the house from the street
  ✗ Alerts on your phone (Telegram)          not set up
      → Connect Telegram, two minutes: planetai telegram
  ✓ Air stations nearby                      12 min ago
  ✓ Weather (Open-Meteo)                     12 min ago
  ✓ Nightly backup                           9 h ago
  ✓ The map of this place                    fetched 19 Oct 2026
```

A cross here never changes the doctor's exit code, because a node without a sensor yet is still being set up. The
map's fix is `planetai run place basemap`.

`quiet`, which install, update and `planetai setup` use, ends with **To finish setting up**: the crosses again, each
with its fix or the Set up address (`http://localhost:8080/#setup/sources`). `--guide` also offers, in a terminal, to
do the first one. `--json` prints `{"ok": …, "checks": [{"check", "ok", "warn", "fix"}], "sources": [...]}`.

## Reading the node

| command | what it does |
|---|---|
| `planetai report` (`report now`) | Writes a report now, sends it, and prints it. |
| `planetai report last` | The last report, when it was written, over how many hours, and whether quiet hours held it. |
| `planetai act <id> [note]` | Records that you acted on alert `<id>`, with your login name as the actor, and prints ρ. Every word after the id is the note, quoted or not. |
| `planetai sensors [--json]` | Every sensor the node reads, yours or reference, indoor or outdoor. |
| `planetai cells [--json]` | The Index cells the node can fill, with value, state and unit. |
| `planetai snapshot [--out FILE]` | One JSON file of what the node answers, read with the admin token, for a design round or a bug report. |

`planetai act` is the terminal's way of closing a loop, and the note is the only record of what was done. Write it:

```bash
planetai act 42 "closed the kitchen window and ran the purifier"
```

> **Careful.** With no note, `planetai act` records the word `acted`. The MCP `act` tool and Telegram's `/act`
> refuse that word and ask for the person's own; the command line does not. On a node with `DECISION_REQUIRED=1`
> an act with no decision recorded first is refused, and the command only says the node did not record it and asks
> whether the alert id is real.

`planetai snapshot` reads `/health`, `/issues`, `/stats`, `/alerts?limit=200`, `/rho`, `/cells`, `/observations`,
`/sensors`, `/trust`, `/report/latest`, `/nearby`, `/forecast`, `/actions?limit=2000`, `/aggregates?hours=24`,
`/reach`, `/earth`, `/shape`, `/effect` and `/issues/days?days=7`. The means from `/aggregates` land under
`readings_1h`, joined with each sensor's `indoor`, `local` and `kind`. Every `note` in the actions is removed,
since it is the household's own words, and a route that does not answer is listed under `provenance.refused`. The
file, `snapshot-<node>-<YYYY-MM-DDTHHMM>.json` by default, holds no raw readings and no token.

## Change it

| command | what it does |
|---|---|
| `planetai config` | A guided walk through the setting groups. Changes are staged; `s` saves them, `q` cancels, `b` goes back. Needs a terminal. |
| `planetai config --section G` | Straight into one group: `basics`, `sources`, `alerts`, `model`, `packs`, `keys`, `sharing`, `system` or `bootstrap`. |
| `planetai config list [--section G]` | Every setting, the value in force and where it came from. Red when `.env` holds something else and is being ignored. |
| `planetai config get KEY` | One setting: its help, the value in force, its source, and whether it needs a restart. |
| `planetai config set KEY VALUE` | A runtime or pack key goes to the database and is live within 20 seconds. A bootstrap key goes to `.env`, and the command offers the restart. |
| `planetai config unset KEY` | Removes the database value, so the key goes back to `.env` or the built-in default. |
| `planetai config edit` | Opens `.env` in `$EDITOR` (nano by default), then offers a restart. |
| `planetai report every N` | Hours between reports (`REPORT_EVERY`): 3, 4, 6, 8, 12 or 24. |
| `planetai report at H` | The local hour the report rhythm counts from (`REPORT_ANCHOR`), 0 to 23. |
| `planetai report level act\|warn\|info` | What interrupts you between reports (`ALERT_LEVEL`). |
| `planetai ui` (`dashboard`) | The dashboard's addresses, the `#wall` one included, the sharing level and the admin, backup and act tokens. Creates `ADMIN_TOKEN` and `ACT_TOKEN` if missing. |
| `planetai test-alert` | Fires one act-level alert through every channel and waits up to 90 seconds for it. It adds a rule that fires within a minute and removes it as soon as its alert appears, so one message arrives. |

The settings themselves, and what each one does, are on [Configuration](configuration.md).

## Update and back up

| command | what it does |
|---|---|
| `planetai update` | Backs up, fetches the release, checks its checksum and signature, migrates, rebuilds and verifies. Refuses at once when no container runtime is running. See [Updating](updating.md). |
| `planetai backup` | Dump, export, remote copy and IPFS now, the job cron runs nightly at 03:17. |
| `planetai restore <dump.sql.gz>` | Asks for the node's name, takes a safety backup, replaces the database with the dump and re-applies `init.sql`. Settings saved from Set up are not in a dump, so the node goes back to `.env`. With no file, lists the newest dumps. |
| `planetai storage` | Where the database, backups, pictures, remote copy and exports are, and their state. |
| `planetai storage set backups <dir>` | Where new dumps go (`BACKUP_DIR`). The folder must be mounted and writable. Dumps already made stay in the old folder, so keep it until you have copied them. |
| `planetai storage set captures <dir>` | Moves where new pictures go (`CAPTURES_DIR`), checked the same way, then restarts the app. A NAS share is fine. Pictures already taken stay where they are. |
| `planetai storage set remote <remote:path>` | After each backup, copies the dumps and exports off the machine with rclone (`BACKUP_REMOTE`). |
| `planetai storage set keep <days>` | Days of dumps kept (`BACKUP_KEEP`). |
| `planetai storage set data` | Refuses, and explains why the database stays on an internal disk. |
| `planetai ipfs` | Starts Kubo (profile `ipfs`) and turns on publishing of each day's export; CIDs land in `exports/<node>/CIDS.txt`. |
| `planetai grafana` | Starts Grafana (profile `grafana`) on loopback, with a read-only database login and a starter dashboard: your own panels over the node's readings. [Grafana](grafana.md). |
| `planetai grafana off` | Stops it, takes it out of `COMPOSE_PROFILES` and drops its database login. Your own dashboards stay in the `grafana` volume. |

Where the data lives, and why never on a network mount: [Storage](storage.md).

## Channels and the network

| command | what it does | sudo |
|---|---|---|
| `planetai telegram` | Checks the bot token, waits up to two minutes for your first message to learn the chat id, saves both, sends a hello and restarts the app. | no |
| `planetai homeassistant` (`ha`) | Starts the broker if there is none, sets `HA_DISCOVERY=1`, and prints what to enter in Home Assistant's MQTT integration. On a node that lists its packs in `PACKS_ENABLED`, add `home-assistant` there too. | no |
| `planetai mesh [up\|status\|down]` | Installs Tailscale and joins your tailnet under the node's name, then prints how to reach it. `TS_AUTHKEY` in the environment joins without a browser. Records `MESH_NAME`. | yes |
| `planetai reticulum` | Downloads the LXMF bridge from fabcity/planetai-reticulum at the commit `RETICULUM_REF` pins, builds it, starts it (profile `reticulum`), and prints the node's address and how to reach it from Sideband. | no |
| `planetai hello [--remove]` | Lists this node on every node's map. It shows the entry a stranger would see (name, the centre of its cell, the place, who runs it, an optional contact) and opens the pull request to `registry.json` with `gh`, or prints the entry and the edit link. It first brings your fork's `main` up to fabcity's with `gh repo sync`, so an old fork does not undo other entries, and stops with that command to run if your `main` has commits of its own. A node already listed sends `registry: update <name>`. Once merged, nodes see it within the hour. `--remove` takes the node off. | no |

See [Channels](channels.md) and [Federation](federation.md).

## Radios and DIY nodes

| command | what it does |
|---|---|
| `planetai meshtastic` | Starts the MQTT broker (profile `mqtt`), writes its password, prints the gateway radio's settings for your region, and waits up to three minutes for the first packet. |
| `planetai broker` | Starts the same broker and prints what to type into a Smart Citizen Kit's shell or a DIY node's setup portal so it publishes here. Waits up to three minutes for the first message. |
| `planetai radio` | On its own, a guide: each step ticked or not, the radios on USB now, and the next command. |
| `planetai radio init [--region R] [--slot N] [--preset P] [--force]` | Writes the fleet file `config/radio/fleet.yaml`: two channel keys, the region from `NODE_CITY` and, in Bali, a frequency slot pinned inside Indonesia's 920 to 923 MHz. A city with no known region is refused until you pass `--region`. `--force` makes new keys, so every radio must be provisioned again. |
| `planetai radio render <role> "<name>" <SHORT>` | Prints the settings `provision` would apply. |
| `planetai radio provision <role> "<name>" <SHORT> --port P [--wifi SSID:PSK] [--mqtt ADDR USER PASS] [--fixed LAT,LON]` | Applies a role (`sensor`, `relay`, `shelf`, `gateway-wifi`, `gateway-host`) one settings section at a time, reboots the radio and reads it back over a new connection; the exit is non-zero if anything differs. `--fixed` pins a radio with no GPS, south latitudes as written (`--fixed -8.8,115.1`). |
| `planetai radio url [--json]` | How to put a phone on the mesh: the channel link, and a QR when `qrencode` is installed. |
| `planetai radio gateway --port P [--broker HOST:PORT] [--install] [--once]` | Makes a radio on this machine's USB the node's gateway. `--install` keeps it running as a service. |
| `planetai radio federate [--write]` | Prints, and with `--write` installs, the broker's bridges to the nodes in `RADIO_PEERS`. Only `fabcity/` topics cross. |
| `planetai radio list [--port P]` | The fleet file and, with a port, what that radio sees. |
| `planetai radio doctor [--port P]` | The usual reasons nothing arrives, checked one by one. |

`planetai radio` talks to radios from the host, so it needs `python3 -m pip install --user meshtastic paho-mqtt`
there; it prints the exact line for your Python when they are missing. See [Radios](radios.md).

## Packs and sources

| command | what it does |
|---|---|
| `planetai packs` | What is loaded (or on disk, when the node is down), core and wild apart, where each wild pack came from, and whether `packs install` has work to do. |
| `planetai packs add <id>` | Fetches a wild pack from the list at fabcity/planetai-wild-packs, at the commit it was listed at, into `packs/<id>`, then runs `packs install` for it. A node with packs chosen in Set up gets it added to that list. |
| `planetai packs add <owner>/<repo>[/<folder>][@<ref>]` | The same for any pack on GitHub, pinned to the commit the ref names. Refuses an id a core pack already has. |
| `planetai packs install` | Adds every pack's missing `env:` keys to `.env` under a dated marker, records their `pip:` lists and rebuilds the image once. |
| `planetai packs cron` | Adds the crontab line that checks every minute for an Install pressed on Set up › Packs and runs `planetai packs pending`, which fetches that commit of a listed wild pack and installs it. The installer and `planetai update` add it too. Only the admin token on the page can ask. |
| `planetai run` | Lists every pack script with its first line. |
| `planetai run <pack> <script> [args]` | Runs it inside the app container, with `PACK_OUT=/app/out` and the pack keys saved from Set up in its environment. |
| `planetai sources [--all] [--pillar P] [--scale S] [--cell 'Pillar\|Scale'] [--json]` | What the source registry lists for this place: entries relevant to `NODE_CITY` or `global`, or all of them with `--all`. Reads the node, or `data/sources/index.json` when the node is down. |

Each line is a slug, status, licence, the pilots it matters to, and the code that reads it (`core:ckan`, `pack:coast`,
or blank when nothing on this node does). The counts below the list cover the whole registry, or one cell with
`--cell`. With the snapshot v0.91.0 carries (`awesome-fabcity-data` at `7bf12a4`, 284 entries, synced 2026-11-04):

```
  across 19 cells: capable 12 / reviewed 17 / candidate 55
  capable = live with an adapter. reviewed = live, backed by an adapter or a usable review. candidate = verified, unread.
```

`--cell 'Governance|City' --all` lists 32 entries, `capable 4 / reviewed 4 / candidate 0`. With `--all` a last line
names what no count includes: `8 deprecated, 1 paywalled, 3 planned, 4 stale`. The same list is `GET /sources`; see
[The source registry](sources.md) and [Packs](packs.md).

## Agents

| command | what it does |
|---|---|
| `planetai agent` (`agents`, `mcp`) | The MCP endpoint on this machine and the tailnet, the twenty-one tools by class (read, act, admin), the header to send and a ready `mcp.json` block. See [MCP](mcp.md). |
| `planetai agent local` | Installs and starts Ollama, and starts the `agent` container that answers on Telegram ([The bot](bot.md)) and serves the ask pane ([Ask the node](ask.md)). It downloads no model, it names one: `qwen3.5:9b` (6.6 GB) at 16 GB of memory or more, else `qwen3.5:4b` (3.4 GB). |
| `planetai agent local pull <tag>` | `ollama pull <tag>`, sets `AGENT_MODEL` to it and restarts the `agent` container. Without a tag it prints the recommended one. |
| `planetai agent stop` | Stops the `agent` container. |

A person driving an agent gets all twenty-one tools. The model on this machine, the `local` rung, gets the read and
act tools only. [docs/MODELS.md](../../docs/MODELS.md) lists the model tags.

`planetai status --json`, `doctor --json`, `sensors --json`, `cells --json`, `sources --json` and `preflight --json`
print JSON for scripts and agents, and `planetai setup --answers` installs without a terminal. The MCP tool
`maintenance` hands back the commands for `update`, `backup`, `restore`, `restart`, `logs`, `doctor` (as
`planetai doctor --json`), `storage`, `ui` and `telegram` as text to run on the host, because the container has no
Docker and no git.

## Not commands

There is no `planetai publish`, `share`, `rho`, `model`, `decide` or `decisions`. `status` and `act` print ρ.
`/model` is a command for the Telegram bot. The Index's own writer publishes to the Index, never a node
([Federation](federation.md)). Sharing is a setting, `SHARE_LEVEL`. A decision is recorded from the dashboard's
Decide form; the terminal has no form for it.

## Where this leads

[Configuration](configuration.md) is where the household decides what the node reads, when it speaks and what it
lets out. If no sensor of yours is answering yet, [Sensors](sensors.md) is the next part to add.
