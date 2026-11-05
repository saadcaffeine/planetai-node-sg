# Install
<!-- checked: v0.91.0 -->

This page puts the node itself on a machine: two containers, a database on this disk, and the loops that read
your place every five minutes. Once it is done the node has pulled the air model and the climate normals for
your coordinates, answers on port 8080, and keeps every reading it takes on this machine. Nothing has reached
a phone yet; that is the [next page](first-ten-minutes.md).

> **The short way.** Six commands, in order, each one waiting for the one before:
> 1. `curl -fsSL https://planetai.fab.city/preflight | bash` checks the machine.
> 2. `curl -fsSL https://planetai.fab.city/install | bash` asks four questions and installs the node. Near the end it
>    offers to fetch the map of your place; say `y`, or run `planetai run place basemap` later.
> 3. `planetai doctor` shows every check, and under **Data sources** what is left, each with its fix. If the
>    terminal says `planetai: command not found`, open a new one: the installer adds the command to the PATH of
>    new terminals.
> 4. `planetai telegram` connects your phone.
> 5. `planetai test-alert` sends a real alert.
> 6. `planetai act <id>` answers it, and the loop is closed.
>
> The rest of this page and the [next](first-ten-minutes.md) explain each step.

## 1. Check the machine

```bash
curl -fsSL https://planetai.fab.city/preflight | bash
```

It reads the machine in a few seconds and installs nothing. It prints one table, a row each for OS,
architecture, memory, free disk, container runtime, whether the disk can be written, `python3`, egress and
ports, and every failing row carries the command that fixes it on that machine. The last line and the exit
code are the verdict:

| exit | verdict line | what to do |
|---|---|---|
| `0` | `This machine can run a node.` | install |
| `1` | `<N> checks failed. Each line above carries the fix. Nothing was installed.` | fix the named rows and run it again |
| `2` | `No container runtime can be installed on <OS>.` | the OS is below every runtime's floor; the preflight prints two routes, Linux in a virtual machine or Linux on the metal ([Platforms](platforms.md), [Revive a laptop](revive-a-laptop.md)) |

Never continue past `2`. The node needs 4 GB of memory (8 GB under WSL2) and 3 GB of free disk. The installer
runs the same preflight first and stops on `1`; on `2` it prints the verdict and exits without an error, because
that is an answer.

## 2. Run the install line

```bash
curl -fsSL https://planetai.fab.city/install | bash
```

`/install` is a small stub. It looks up the released version and fetches the `install` script, and the preflight,
from exactly that commit, so everything you receive belongs to one release. The script prints the logo with the
published version under it, runs the preflight, downloads the node's tarball from `planetai.fab.city/node0/get`,
checks its checksum and its signature, unpacks it into `~/planetai` keeping any `.env` already there, links the
command to `~/.local/bin/planetai`, and hands over to `planetai setup`. Before the questions the screen shows:

```
>> downloading the node from https://planetai.fab.city/node0
>> checksum verified
>> signature verified
```

If either check fails it stops before anything is unpacked. What each refusal says, and why the answer is to stop,
is on [Updating](updating.md#updates-are-signed).

To put a second node somewhere else on the same machine:

```bash
PLANETAI_HOME=~/somewhere bash -c "$(curl -fsSL https://planetai.fab.city/node0/install)"
```

## 3. Answer the four questions

`planetai setup` opens with **Let's set up a node.** and asks:

| | question | what it writes |
|---|---|---|
| 1 | A short name for this node (lowercase, dashes). The default is the hostname. | `NODE_NAME` |
| 2 | Where is it? Type a neighbourhood, town or city. It asks OpenStreetMap's Nominatim and Open-Meteo, lists the hits with their time zone, and asks `Is that the right place?` even when there is one. The list ends with a choice to type the place differently; if nothing matches, paste `lat,lon`. | `NODE_LAT`, `NODE_LON`, `NODE_TZ`, `NODE_CITY` |
| 3 | What is this node for? A home, a business, a community or lab node, or a district or region node. | `NODE_KIND`; a district also sets `NODE_SCALE=city` |
| 4 | Do you have a sensor? None yet, or a Smart Citizen kit, which asks for the kit number from its smartcitizen.me URL. | `SC_DEVICES` |

After the place, one line says what the node will use as its outdoor reference. Inside Bali it is the island's
public stations, the `bali-air-dispatch` pack, which the Bali preset turns on; everywhere else it is the global
CAMS model at your coordinates, with no key. A place inside Bali, Barcelona, Boston or Santiago also takes that
pilot's preset and files the node under the pilot's city key.

Then **Here's the plan** lists the name, place, time zone, city key, sensor and outdoor reference, and asks
`Install with these?`. Saying no changes nothing. Saying yes writes the answers to `.env` first, so a failure
later keeps them for the next run, and starts the seven steps below.

The place is the answer that matters most: it fixes the H3 cell the node stands in and the 500 m radius inside
which a sensor counts as this node's own. Without a sensor the node still knows your weather, the satellite air
model for your district and forty years of climate for your coordinates; see [Before a sensor](before-a-sensor.md).

> **Only Smart Citizen, for now.** The installer offers one kit. AirGradient and PurpleAir are read by their own
> packs, `airgradient` and `purpleair`, each on once `AIRGRADIENT_HOSTS` or `PURPLEAIR_HOSTS` is set in Set up ›
> Sources. Details on the [sensors](sensors.md) page.

### Without a terminal

An agent, CI or a provisioning script installs from a file. With no terminal, `planetai setup` prints this
example itself:

```bash
cat > node.json <<'JSON'
{"name": "my-node", "place": "Palma de Mallorca", "kind": "home", "sensor": {}}
JSON
planetai setup --answers node.json
```

`place` is geocoded with Open-Meteo, first hit, or replaced by `"lat"` and `"lon"`. `kind` is `home` (the default),
`business`, `community` or `district`. `sensor` is `{}` or one of `{"sc": "19880"}`, `{"sc_user": "name"}`,
`{"airgradient": "host"}`, `{"purpleair": "ip"}`; the last two set `AIRGRADIENT_HOSTS` and `PURPLEAIR_HOSTS`. The answers
become `install.sh` flags and the installer runs with `--yes`. It needs `python3`, standard library only, and ends
with `installed. planetai status --json for the state; planetai ui for the token.`

## What the installer does

It announces seven steps, and each one prints its elapsed time and a heartbeat at least every ten seconds. The
full log is in `.planetai-install.log`.

1. **Container runtime.** Detects OrbStack, Docker Desktop, Colima or a systemd Docker and starts it. On Linux
   without Docker it installs it: `pacman` on Arch; Docker's own Ubuntu repository on an Ubuntu derivative such
   as Mint or Pop!_OS, because Docker's script misreads those as Debian; `get.docker.com` everywhere else, plain
   Ubuntu included. It tells a daemon that is down apart from a socket you may not use yet, and carries on under
   the new `docker` group without asking you to log out. With Podman and no Docker it installs nothing and stops,
   printing the three lines that let Podman answer to `docker` (`podman-docker`, the user `podman.socket`, and
   `DOCKER_HOST`). No node has run on Podman yet.
2. **`.env`.** Copies `.env.example` (mode 600), applies the pilot preset if any, writes the answers, stamps
   `NODE_VERSION`, and generates `POSTGRES_PASSWORD` and `ADMIN_TOKEN`. It refuses to start without coordinates,
   and refuses a new database password over a database volume an earlier node left behind.
3. **Port and folders.** Checks that `APP_PORT` (8080) is free, and creates `backups`, `exports` and `out`.
4. **The database image.** Pulls `imresamu/postgis:16-3.4-alpine` (about 162 MB, amd64 and arm64) with visible
   progress.
5. **Build and start.** `docker compose up -d --build`: the `app` image on `python:3.12-slim`, then both
   containers.
6. **Schema.** Waits for Postgres and applies `init.sql`, the whole schema, idempotent, the same file a fresh
   volume and an update both run.
7. **Checks.** Modules in the image, database healthy, app answering, `backup.sh` executable.

Then it adds the nightly backup to your crontab (`17 3 * * *`), and a second line, checked every minute, that lets
Install on Set up › Packs reach this machine (`planetai packs cron`, [Packs](packs.md)). Unless `--no-bootstrap` was given, the first
start pulls about 4,500 rows of history for your coordinates: 92 days of hourly PM2.5 and PM10 from the Copernicus
air model, and NASA POWER's monthly normals, so `planetai status` has something to say within minutes. The
installer ends with one line you can paste into an issue, starting `install OK`, with the node's name, how long
the seven steps took and the port.

## When it finishes

`planetai setup` restarts the app with your settings and runs the [doctor](cli.md). A cross next to *database
answers* or *node answers on :8080* means something is wrong; see [Troubleshooting](troubleshooting.md). Below the
checks the doctor lists the node's **Data sources** and ends with **To finish setting up**: what is still missing,
most important first, each with the one thing to do. On a new node without a sensor, *Add your sensor* comes first,
with the address of the Set up page, and then:

```
  To finish setting up
   1. Connect Telegram, two minutes: planetai telegram
   2. No backup yet. One runs every night at 03:17; to have one now: planetai backup
   3. No map yet. Fetch it once, a few minutes: planetai run place basemap. build.protomaps.com and
      OpenAerialMap learn roughly where this node is (the square fetched); after that nothing is sent.
```

The weather and satellite models show a dash until the node's first poll, a few minutes after it starts.

Without a map yet, setup then offers **The map of this place**: OpenStreetMap streets, buildings and names, and
drone imagery where somebody flew, fetched once onto the node (up to tens of MB) and read from `out/ground/` after
that. It says first that build.protomaps.com and OpenAerialMap learn the squares within `GROUND_RADIUS_KM` (12 km)
of the node. `y` fetches it; Enter leaves it for later. The Place door and the Wall draw no streets without it.

The last screen is a box reading **● Your node is running.**, the dashboard's address on this machine and from
your phone on the same WiFi, and the settings token (`planetai ui` shows it again), then
`What now?  [o] open the dashboard   [t] connect Telegram   [Enter] stay in the terminal`. Run `./install.sh` on
its own, or `planetai update`, and it ends with the same doctor and map offer; with `--yes` or no terminal it only
prints.

## Re-running it

`~/planetai` with a `VERSION` file or a git checkout is an existing node, and the installer treats a re-run as an
update that keeps your `.env`. `planetai setup` on an existing node offers to update it, reconfigure it, make sure
it is running, or remove it. If an earlier setup stopped before the containers existed, it says
`A set-up here did not finish, but your answers were saved.` and offers to continue with them.

To start over, remove first:

```bash
planetai remove              # containers, database, folder, backup cron entry, the command itself; asks twice
planetai remove --keep-data  # the same, but the readings stay in their volume
```

The Docker volume outlives the folder, and every node's compose project is `planetai`, so a fresh install finds
the old database; the installer then refuses to give it a new password and names the two ways out
([Troubleshooting](troubleshooting.md)). `planetai remove` deletes the volumes by name and then checks. If the node will not start at all, `curl -fsSL https://planetai.fab.city/remove | bash -s -- --purge` finds the
containers, the four volumes, the folder, the symlink and the crontab line without running any of the node's
own code.

## Where things are

```
~/planetai/
  .env                   every setting; mode 600; never committed, never pasted
  backups/               nightly pg_dump, kept BACKUP_KEEP days
  exports/<node>/        the daily CC BY 4.0 export, one JSON a day
  out/                   what pack scripts write: land-change maps, timelapses, mapping briefs, the kept map (out/ground/), the workbench's firmware (out/firmware/)
  out/captures/          the household's pictures, unless CAPTURES_DIR says elsewhere
  packs/                 the rules; add a folder to add a domain
  config/rules.yml       the two domain-blind core rules and trust's three
  data/                  the pinned source registry and the platform floors, mounted read-only
  .planetai-release      signed or unsigned, and when, for the last install or update
  .planetai-setup.log    what setup and the CLI did
  .planetai-update.log   what the last update did
~/.local/bin/planetai    the command
```

## Machines that stay on

A node wants a computer that boots and logs in on its own after a power cut. An x86 Linux box first: a mini PC,
or an old laptop with Linux on it, which is often faster than the mini PC you would otherwise buy. A Mac works
([Mac mini](mac-mini.md) has the settings that stop it sleeping), and on Apple Silicon the database runs natively.
Windows through WSL2.

A Raspberry Pi passes the preflight, and its architecture row says it is untested on hardware. Nobody has run a
node on a Pi, a Jetson or a reComputer yet, and `docs/ARM64.md` is the test plan for whoever goes first. The floors, and where each number comes from, are on [Platforms](platforms.md).

## Where this leads

The node is reading. Next, give it a way to reach you and prove the whole path once:
[First ten minutes](first-ten-minutes.md).
