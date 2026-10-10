# Command line
<!-- checked: v0.80.10 -->

The command line is how the person who keeps a node looks after it: install it, ask whether it is alive,
record what somebody did about an alert, move its data somewhere safe. The repo names that person as the
product: "someone whose job it is to keep the sensor alive and the alerts correct." Every command below
runs on the machine the node lives on and reads the node's own answers, so what it prints is what the node
is doing, not what `.env` once said.

`planetai` is one bash script, `bin/planetai`, installed as a symlink in `~/.local/bin`. It runs on the
Python the machine already has (Apple's 3.9 with the standard library on a Mac, nothing installed by pip)
and talks to the node over its own [API](api.md) on `localhost:$APP_PORT` with the tokens in `.env`.
`planetai` on its own prints the command list from the top of the script. `planetai <word>` on a node that
predates the word says "there is no `planetai <word>` in this node", names the node's version and
suggests `planetai update`. Commands arrive in releases.

> **Gap in v0.80.10.** The list `planetai` prints leaves out four commands that exist: `preflight`, `sources`, `config unset` and `agent local pull`. The tables below are complete.

Nothing here needs `sudo` except `mesh` (installing and joining Tailscale), `agent local` on a machine with
`systemctl` where Ollama is not already answering, and, through the installer, `setup` when Docker has to
be installed or started. The installer says what each `sudo` is for on the line before it asks.

## Install and lifecycle

| command | what it does |
|---|---|
| `planetai preflight [--json]` | Can this machine run a node. Checks only, installs nothing. Exit `0` go, `1` fixable, `2` below the floor. |
| `planetai setup` | The four questions, then the installer. On an existing node offers update · reconfigure · nothing · remove. Detects a version gap against the published `VERSION` and an unfinished install. |
| `planetai setup --answers file.json` | Headless install from a JSON file; see [Install](install.md). |
| `planetai status [--json]` | `/health`, sensors, recent alerts and ρ on one screen. |
| `planetai doctor [quiet\|--json]` | Every check with its fix. Docker running, the containers up, the database answering, the node answering on its port, the app logged in to the database, coordinates set, no stray spaces in `.env`, the backup destination mounted, a backup in the last two days, the release signature verified on the last update (tarball nodes only), the source registry, whether a newer release is out (amber, never red; silent when `UPDATE_CHECK` is off), the `make` pack when it is installed and `PACKS_ALLOW_CODE=1`, Telegram connected, a backup exists, a nightly backup scheduled, more than 1 GB free; with profiles, the broker, mesh packets and the Reticulum bridge. |
| `planetai update` | Backup, fetch, check the checksum and the release signature, migrate, rebuild, verify; see [Updating](updating.md). Refuses at once when no container runtime is running. |
| `planetai start` · `stop` · `restart` | `docker compose up -d` · `down` (data kept) · recreate the app container, which is how `.env` changes take effect. |
| `planetai logs [service]` | Follow the container's log; `app` by default, `agent`, `db`, `reticulum` by name. |
| `planetai remove [--keep-data]` (`uninstall`) | Asks twice (yes, then the node's name typed) and removes containers, volumes, the folder, the crontab line and the command; then checks what is left. |
| `planetai version` (`-v`, `--version`) | Version, node name and city, then the key the node takes updates from: `updates signed by  fabcity  <fingerprint>`. |
| `planetai geocode <place>` | Run the setup wizard's geocoder on its own. |

Three of the doctor's rows say more than pass or fail. The last two are facts, and the fact is in the label:

| row | what it says | when it is not green |
|---|---|---|
| `release signature verified on last update` | the last `planetai update` checked who built the tarball | red when that update ran with `PLANETAI_UNSIGNED=1` or predates signed releases. A git checkout never fetches a release and has no such row. |
| `source registry: N entries · awesome-fabcity-data @ <sha> · synced <date>` | which snapshot of the source registry this node carries | red when `data/sources/REGISTRY_VERSION` is missing; amber when the pin is more than 180 days old. Amber does not fail the run. |
| `make: …` | `off` with the licence reason, or how many fab labs lie within `MAKE_RADIUS_KM`, from which snapshot, read on which date | never; it is a fact about the place |

`doctor --json` prints `{"ok": …, "checks": [{"check", "ok", "warn", "fix"}]}`, one object per check.

## Configuration

| command | what it does |
|---|---|
| `planetai config` | A guided walk through the setting groups; changes are staged, `s` saves, `q` cancels. |
| `planetai config --section G` | Straight into one group. |
| `planetai config list [--section G]` | Every setting, the value in force and where it came from; red when `.env` and the running value disagree. |
| `planetai config get KEY` | One setting and its source. |
| `planetai config set KEY VALUE` | A runtime key goes to the database and is live within 20 seconds; a bootstrap key goes to `.env` and the command offers the restart. A pack's key goes to the database too, and the pack has it at its next run: see [Configuration](configuration.md). |
| `planetai config unset KEY` | Back to `.env`, or to the built-in default. |
| `planetai config edit` | `$EDITOR` on `.env`, then the offer to restart. |
| `planetai ui` (`dashboard`) | The dashboard's addresses, including the `#wall` one; creates `ADMIN_TOKEN` and `ACT_TOKEN` if missing; prints the three tokens and the sharing level. |
| `planetai test-alert` | Fires one act-level alert through every channel and waits up to 90 seconds for it. It adds a temporary rule that fires within a minute, looks for that rule's own alert, and removes the rule the moment it sees it, so one message arrives, on a node with any number of alerts. |

The settings themselves are on [Configuration](configuration.md).

## Sources and channels

| command | what it does | needs sudo |
|---|---|---|
| `planetai telegram` | Validates the bot token, waits up to two minutes for your first message to learn the chat id, writes both to `.env` and to the running node's settings, sends a hello (in Spanish when `ALERT_LOCALE=es`), recreates the app. | no |
| `planetai mesh [up\|status\|down]` | Installs Tailscale and joins the tailnet under the node's name (`TS_AUTHKEY` optional); records `MESH_NAME`. | yes |
| `planetai meshtastic` | Starts the MQTT broker (compose profile `mqtt`), writes its password, prints the gateway radio's settings for your region, waits up to three minutes for the first packet. | no |
| `planetai broker` | Starts the MQTT broker if it is not running (compose profile `mqtt`, same user and password as `planetai meshtastic`) and prints what to type into a Smart Citizen Kit's shell or a DIY node's setup portal so it publishes here; waits up to three minutes for the first message. | no |
| `planetai reticulum` | Starts the LXMF bridge (profile `reticulum`), prints the node's address and the Sideband instructions. | no |
| `planetai homeassistant` (`ha`) | Ensures the broker, sets `HA_DISCOVERY=1`, prints the integration details. | no |

## Reading the node

| command | what it does |
|---|---|
| `planetai report` (`report now`) | Writes a report now and sends it; prints the text. |
| `planetai report last` | The last report. |
| `planetai report every N` | Hours between reports: 3, 4, 6, 8, 12 or 24. (The command's own usage line leaves out `12`; `12` is accepted.) |
| `planetai report at H` | The local hour the rhythm counts from. |
| `planetai report level act\|warn\|info` | What interrupts you between reports. |
| `planetai act <id> [note]` | Records that you acted on alert `<id>`, with your login name as the actor; prints ρ. |
| `planetai sensors [--json]` | Every sensor the node reads. |
| `planetai cells [--json]` | The Index cells the node can fill, with their state. |
| `planetai snapshot [--out FILE]` | One JSON of every answer the node gives, read with the admin token. The file carries no raw readings, no token, and no note a person wrote. |

`planetai act` is the terminal's way of closing a loop, and the note is the only record of what was
done. Write it:

```bash
planetai act 42 "closed the kitchen window and ran the purifier"
```

> **Careful.** With no note, `planetai act` records the word `acted` as the note. The MCP `act` tool and
> Telegram's `/act` refuse that word and ask for the person's own; the command line does not, so the rule
> holds only where the code enforces it. And on a node with `DECISION_REQUIRED=1`, an act with no decision
> recorded first is refused with 409, and the command prints only that the node did not record it and
> asks whether the alert id is real.

`planetai snapshot` asks nineteen routes: `/health`, `/issues`, `/stats`, `/alerts?limit=200`, `/rho`,
`/cells`, `/observations`, `/sensors`, `/trust`, `/report/latest`, `/nearby`, `/forecast`,
`/actions?limit=2000`, `/aggregates?hours=24`, `/reach`, `/earth`, `/shape`, `/effect` and `/issues/days?days=7`. The hourly means
land under `readings_1h`, joined with each sensor's `indoor`, `local` and `kind`. Every `note` in the
actions is set to null before the file is written, and `provenance` says how many were removed: the file is
made to be sent to a design round or a bug report, and a note is the household's own words about its own
house. A route that does not answer is recorded under `provenance.refused` rather than failing the file.
The default name is `snapshot-<node>-<YYYY-MM-DDTHHMM>.json`, and the command says what is in it:

```
  It carries means, alert texts and sensor names — the household's own data. No raw readings, no token.
```

## The agent

| command | what it does |
|---|---|
| `planetai agent` (`agents`, `mcp`) | The MCP endpoint, the twenty tools by class (read, act, admin), the header to send, and a ready-made `mcp.json` snippet; see [MCP](mcp.md). A person driving an agent gets all twenty; the local model gets read and act only. |
| `planetai agent local` | Installs Ollama if it is missing, starts it as a service, and starts the `agent` container that answers on Telegram; see [The bot](bot.md). The dashboard's ask pane can then use the same model on this machine; see [Ask the node](ask.md). It does not download a model: it prints the one it recommends for this machine's memory, `qwen3.5:9b` (6.6 GB) at 16 GB or more, else `qwen3.5:4b` (3.4 GB). |
| `planetai agent local pull <tag>` | `ollama pull <tag>`, sets `AGENT_MODEL` to it, recreates the `agent` container. Without a tag it prints the recommended tag and exits. |
| `planetai agent stop` | Stops the agent container. |

The model is a separate download on purpose: a node runs without one, and the weights are several
gigabytes on the machine a household may have revived for this. [docs/MODELS.md](../../docs/MODELS.md) lists the
tags.

## Packs and the source registry

| command | what it does |
|---|---|
| `planetai packs` | What is loaded (from the node) or on disk (when it is down), core and wild apart, where each wild pack came from, which of a wild pack's scripts an agent may run (its `agent_scripts:`) or that it runs none, and whether `packs install` has anything to do. |
| `planetai packs add <id>` | Fetches a wild pack from the list at fabcity/planetai-wild-packs, at the commit it was listed at, into `packs/<id>`, then runs `packs install`. |
| `planetai packs add <owner>/<repo>[/<folder>][@<ref>]` | The same for any pack on GitHub. A branch or tag is pinned to the commit it names. Refuses an id a core pack already has. |
| `planetai packs install` | Adds every pack's missing `env:` keys to `.env` under a dated marker, writes the union of their `pip:` lists, rebuilds the image once. |
| `planetai run` | Lists every pack script with its first line. |
| `planetai run <pack> <script> [args]` | Runs it inside the app container with `PACK_OUT=/app/out`, and with the pack keys saved from Set up in its environment. |
| `planetai sources [--all] [--pillar P] [--scale S] [--cell 'Pillar\|Scale'] [--json]` | What the source registry has filed for this place: the entries whose pilot relevance is `NODE_CITY` or `global`, or every entry with `--all`. Reads the node, or `data/sources/index.json` when the node is down. |

`planetai sources` answers "what could this place measure", which is the question somebody asks with the
containers down, so it works without them. Each line is a slug, a status, a licence, the pilots it is
relevant to, and the adapter string that reads it: `core:ckan` for an adapter in the node's own
`sources.py`, `pack:coast` for a pack. A blank last column is a dataset the registry lists that no code on
this node reads yet. The footer says so in the node's words:

```
  N of 269 entries. The last column is the code that reads it. A cell with sources and a blank column is one nobody has written an adapter for yet.
```

The snapshot at v0.80 is `awesome-fabcity-data` at `851b8db`, 269 entries, synced 2026-10-06. `N` is how many
of them are filed for your city or for everywhere. The same list is `GET /sources` on [the API](api.md).

Since v0.73 two more lines follow the footer: the three
counts, summed over every cell or, with `--cell`, for that one cell, and what they mean. The counts are for
the whole registry whatever the other filters, and are grouped by each entry's `feeds_cells`. At `851b8db`:

```
  across 19 cells: capable 12 / reviewed 17 / candidate 51
  capable = live with an adapter. reviewed = live, backed by an adapter or a usable review. candidate = verified, unread.
```

`planetai sources --cell 'Governance|City'` lists the entries filed under that cell (32 with `--all`) and prints
`Governance|City: capable 4 / reviewed 4 / candidate 0` in place of the first line. With `--all` a last line
names the statuses no count includes:

```
  counted nowhere: 8 deprecated, 1 paywalled, 3 planned, 4 stale. A node cannot call them, so they are in no cell number.
```

See [Packs](packs.md) and [Packs that ship](packs-reference.md).

## Storage and the commons

| command | what it does |
|---|---|
| `planetai storage` | Where the database is and how big; the backup folder, the last dump, the retention; the rclone remote; exports; IPFS; whether a backup token exists. |
| `planetai storage set backups <dir>` | Move the dumps; the folder must be a mounted, writable path. |
| `planetai storage set remote <rclone remote:path>` | Copy the last three days of dumps and every export off the machine after each backup. |
| `planetai storage set keep <days>` | Retention. |
| `planetai storage set data` | Refuses, and explains why the database must stay on an internal disk. |
| `planetai backup` | Dump now, export yesterday, copy to the remote, publish to IPFS if on. |
| `planetai restore <dump.sql.gz>` | Type the node's name; a safety backup; stop the app; drop and recreate; restore; re-apply `init.sql`; start. Dumps carry no `settings` rows. |
| `planetai ipfs` | Start Kubo (profile `ipfs`), turn publishing on; CIDs land in `exports/<node>/CIDS.txt`. |

Where the data lives, and why never on a network mount: [Storage](storage.md).

## Not commands

There is no `planetai publish`, `share`, `rho`, `model`, `decide` or `decisions`. ρ is printed by `status`
and `act`. `/model` is a Telegram command for the bot. Publishing to the Index is done by the Index's own
writer, not by a node ([Federation](federation.md)). Sharing is a setting, `SHARE_LEVEL`. A decision is
recorded from the dashboard's Decide form, which posts `stage: decided`; the terminal has no form for it.

## For scripts and agents

`planetai status --json`, `doctor --json`, `sensors --json`, `cells --json`, `sources --json` and
`preflight --json` print JSON, and `planetai setup --answers node.json` installs without a terminal. The
MCP tool `maintenance` hands back the host-side commands for `update`, `backup`, `restore`, `restart`,
`logs`, `doctor` (as `planetai doctor --json`), `storage`, `ui` and `telegram` as text to run, because the
container has no Docker and no git.

## Where this leads

The command line keeps the node running; [Configuration](configuration.md) is where the household decides
what it reads, when it speaks and what it lets out. If no sensor of yours is answering yet,
[Sensors](sensors.md) is the next part to add.
