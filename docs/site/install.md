# Install
<!-- checked: v0.80.10 -->

This page puts the node itself on a machine: two containers, a database on this disk, and the loops that read
your place every five minutes. Once it is done the node has pulled the air model and the climate normals for
your coordinates, answers on port 8080, and keeps every reading it takes on this machine. Nothing has reached
a phone yet; that is the [next page](first-ten-minutes.md).

One line, four questions, two minutes. Before it, if the machine is old or you are not sure it qualifies,
run the preflight.

## 1. Check the machine

```bash
curl -fsSL planetai.fab.city/preflight | bash
```

It reads the machine in a few seconds and installs nothing. It prints one table, a row each for OS,
architecture, memory, free disk, container runtime, whether the disk can be written, `python3`, egress and
ports, and every failing row carries the one command that fixes it on that machine. One line and the
exit code are the verdict:

| exit | verdict line | what to do |
|---|---|---|
| `0` | `This machine can run a node.` | install |
| `1` | `<N> checks failed. Each line above carries the fix. Nothing was installed.` | fix the named rows and run it again |
| `2` | `No container runtime can be installed on <OS>.` | the OS is below every runtime's floor; the preflight prints two routes, Linux in a virtual machine or Linux on the metal ([Platforms](platforms.md), [Revive a laptop](revive-a-laptop.md)) |

Never continue past `2`. The node needs 4 GB of memory (8 GB under WSL2) and 3 GB of free disk. The
installer runs the same preflight first: it stops on `1`, and on `2` it prints the verdict and exits without
an error, because that is an answer.

## 2. Run the one line

```bash
curl -fsSL planetai.fab.city/install | bash
```

`/install` is a stub that fetches the current `install` script from the repository on every run. The script
prints the published version under the logo, runs the preflight, downloads the node's tarball from
`planetai.fab.city/node0/get`, checks it (below), unpacks it into `~/planetai` keeping any `.env` already
there, links the command to `~/.local/bin/planetai`, and hands over to `planetai setup`, which asks the four
questions. On screen, before the questions:

```
>> downloading the node from https://planetai.fab.city/node0
>> checksum verified
>> signature verified
```

To put a second node somewhere else on the same machine:

```bash
PLANETAI_HOME=~/somewhere bash -c "$(curl -fsSL planetai.fab.city/node0/install)"
```

### Signed installs and updates

The tarball is checked twice before anything is unpacked. The SHA256 checksum is served from the same place
as the tarball, so it proves only that the download arrived whole. The signature proves who built it: the
node runs `ssh-keygen -Y verify` with signer `fabcity` and namespace `planetai-node`, against a key that is
written into the installer and `update.sh` and is not on the web server. `planetai version` prints the key
this node trusts:

```
  updates signed by  fabcity  SHA256:1+MvZWJUBWisjY08E1KR77znXLs2lVWgVkh+Z++8IL4
```

`planetai update` makes the same two checks. When either fails it stops before touching the node, and these
are four of the things it says:

| it prints | what it means |
|---|---|
| `no ssh-keygen on this machine, so it cannot be checked who built this download.` | install it (`openssh-client` on Debian and Ubuntu, `openssh` on Arch; macOS has it) and run the same line again |
| `could not fetch …/planetai-node.tar.gz.sig, so it is not known who built this download.` | the site is reachable and that one file is not, usually a partial deploy; wait and try again |
| `this download is not signed by the PLANETAI release key. Nothing was installed and nothing on this machine changed.` | try once more on a network you trust; if it says it twice, do not look for a way past it, say so |
| `the download does not match its published checksum. Try again; if it repeats, tell us.` | the download was cut or altered on the way |

A refused update is the node doing its job. `docs/UPDATING.md` says so in those words, and the right answer
is to stop. Every install and update writes `.planetai-release`, `signed` or `unsigned` with the time, and
`planetai doctor` has a row for it: `release signature verified on last update`. `PLANETAI_UNSIGNED=1`
accepts an unsigned tarball and says so in red; it is for a throwaway test tarball, never a node anybody
relies on. `PLANETAI_GET` points the installer at the GitHub Release mirror of the same signed files. See
[Updating](updating.md).

## 3. Answer the four questions

| | question | what it writes |
|---|---|---|
| 1 | A short name for the node (lowercase, dashes; default: the hostname) | `NODE_NAME` |
| 2 | The place. Type a neighbourhood, town or city; it geocodes (Nominatim, then Open-Meteo), shows the hits, and asks you to confirm even when there is one. `lat,lon` is accepted. | `NODE_LAT`, `NODE_LON`, `NODE_TZ`, `NODE_CITY`; a pilot preset when the place falls inside Bali, Barcelona, Boston or Santiago; `BAD_ENABLED=0` outside Bali |
| 3 | What the node is for: a home · a business · a community or lab · a district or region | `NODE_KIND`; `district` also sets `NODE_SCALE=city` |
| 4 | Your sensor, if you have one: none · a Smart Citizen kit number · an AirGradient host (and whether it is indoors) · a PurpleAir IP (and whether it is indoors) | `SC_DEVICES` · `AIRGRADIENT_HOSTS` · `PURPLEAIR_HOSTS`, plus `SENSOR_INDOOR` |

After the fourth answer the installer runs its seven steps (below) and ends on a box reading **● Your node
is running.**, with the dashboard's addresses and the settings token under it, and in a terminal `What now?  [o] open the
dashboard   [t] connect Telegram   [Enter] stay in the terminal`. That box means the node exists on this
machine and is answering on its port. What the crosses above it mean is at the end of the next section.

The place is the answer that matters most: it fixes the H3 cell the node stands in and the 500 m radius
inside which a sensor counts as this node's own. Without a sensor the node still knows your weather, the
satellite air model for your district and forty years of climate for your coordinates; see
[Before a sensor](before-a-sensor.md).

> **Gap in v0.80.10.** The AirGradient and PurpleAir adapters exist in `app/sources.py` and are tested, but this
> version does not register them for polling; the AirGradient hosts you enter are used to keep your own kit out of the
> Bali Air Dispatch ring and for nothing else. A Smart Citizen kit is read. Details on the [sensors](sensors.md)
> page.

### Without a terminal

An agent, CI or a provisioning script installs from a file:

```bash
planetai setup --answers node.json
```

```json
{"name": "bayu-ungasan", "place": "Kuta Selatan", "kind": "home", "sensor": {"sc": "19880"}}
```

`place` is geocoded (Open-Meteo, first hit) or replaced by `"lat"` and `"lon"`; `kind` defaults to `home`;
`sensor` is one of `{"sc": "19880"}`, `{"sc_user": "name"}`, `{"airgradient": "host"}`, `{"purpleair": "ip"}`
or absent. The answers become `install.sh` flags and the installer runs with `--yes`. It needs `python3` on
the machine, standard library only. It ends with `installed. planetai status --json for the state; planetai
ui for the token.`

> **Careful.** This path does not set `BAD_ENABLED=0` outside Bali the way question 2 does, so a headless
> node keeps `.env.example`'s `BAD_ENABLED=1`. Outside Bali, set it to `0` afterwards.

## What the installer does

Seven named steps, each printing its elapsed time and a heartbeat at least every ten seconds:

1. **Container runtime.** Detects OrbStack, Docker Desktop, Colima or a systemd Docker and starts it. On
   Linux without Docker it installs it: `pacman` on Arch; Docker's own Ubuntu repository on an Ubuntu
   derivative such as Mint or Pop!_OS, because Docker's script misreads those as Debian; `get.docker.com`
   everywhere else, plain Ubuntu included. It tells apart a daemon that is down and a socket you are not allowed
   to use. On Linux with Podman and no Docker it installs nothing and
   stops, printing the three lines that let Podman answer to `docker` (`podman-docker`, the user
   `podman.socket`, and `DOCKER_HOST`) and the words "No node has been run on Podman and no CI leg covers it,
   so you would be the first."
2. **`.env`.** Copies `.env.example` (mode 600), applies the preset for your pilot city if any, writes the
   answers, stamps `NODE_VERSION`, generates `POSTGRES_PASSWORD` and `ADMIN_TOKEN`. It refuses to start
   without coordinates, and refuses to generate a new database password over an existing database volume.
3. **Port and folders.** Checks `APP_PORT` (8080) is free; creates `backups`, `exports`, `out`.
4. **The database image.** Pulls `imresamu/postgis:16-3.4-alpine` (about 162 MB) with visible progress. It is
   published for amd64 and arm64.
5. **Build and start.** `docker compose up -d --build`: the `app` image on `python:3.12-slim`, then both
   containers.
6. **Schema.** Waits for Postgres and applies `init.sql`: the whole schema, idempotent, the same file a
   fresh volume and an update both run.
7. **Checks.** Modules in the image, database healthy, app answering, Telegram set, `backup.sh` executable.

Then it installs the nightly backup in your crontab (`17 3 * * *`), and, unless `--no-bootstrap`, the first
start pulls about 4,500 rows of history for your coordinates (92 days of hourly PM2.5 and PM10 from the
Copernicus air model, and NASA POWER's monthly normals), so `planetai status` has something to say within minutes. The installer prints one
line you can paste into an issue:

```
install OK — <name>, 7 steps in <s>s, on localhost:8080
```

`planetai setup` then restarts the app with your settings and runs the doctor. A cross next to *telegram
connected* and next to the backup rows is expected on a new node, and the setup says so: "The crosses above
are normal on a new node: Telegram is the next step, and the first backup runs tonight." A cross next to
*database answers* or *node answers on :8080* means something is wrong; see [Troubleshooting](troubleshooting.md). The
last screen is a box reading **Your node is running.**, the dashboard's addresses, and the settings token.

## Re-running it

`~/planetai` with a `VERSION` file or a git checkout is an existing node, and the installer treats a re-run
as an update that keeps your `.env`. `planetai setup` on an existing node offers to update, reconfigure, do
nothing or remove. To start over, remove first:

```bash
planetai remove              # containers, database, folder, cron entry, the command itself; asks twice
planetai remove --keep-data  # the same, but the readings stay in their volume
```

The Docker volume outlives the folder, and every node's compose project is `planetai`, so a fresh install in
the same folder re-attaches the old database unless the volumes were deleted. `planetai remove` deletes them
by name and then checks. If the node will not start at all, `curl -fsSL planetai.fab.city/remove | bash -s --
--purge` finds the containers, the four volumes, the folder, the symlink and the crontab line without running
any of the node's own code.

## Where things are

```
~/planetai/
  .env                   every setting; mode 600; never committed, never pasted
  backups/               nightly pg_dump, kept BACKUP_KEEP days
  exports/<node>/        the daily CC BY 4.0 export, one JSON a day
  out/                   what pack scripts write: land-change maps, timelapses, mapping briefs, the kept map (out/ground/)
  packs/                 the rules; add a folder to add a domain
  config/rules.yml       the two domain-blind core rules
  data/                  the pinned source registry and the platform floors, mounted read-only
  .planetai-release      signed or unsigned, and when, for the last install or update
  .planetai-setup.log    what setup and the CLI did
  .planetai-update.log   what the last update did
~/.local/bin/planetai    the command
```

## Machines that stay on

A node wants a computer that boots and logs in on its own after a power cut. An x86 Linux box first: a mini
PC, or an old laptop with Linux on it; the ten-year-old laptop is faster than the mini PC you would otherwise
buy. A Mac works ([Mac mini](mac-mini.md) has the settings that stop it sleeping), and on Apple Silicon the
database runs natively. Windows through WSL2.

A Raspberry Pi passes the preflight since v0.63, because the database image is now published for arm64, and
the preflight row says `arm64 (untested on hardware — docs/ARM64.md)`. Untested is the word that
matters. Nobody has run a node on a Pi, a Jetson or a reComputer yet, and `docs/ARM64.md` is the test
plan for whoever goes first. If that is you: 64-bit Raspberry Pi OS, 8 GB, and boot from an NVMe hat or a USB
SSD, never an SD card, because Postgres writes on every commit and an SD card dies under that within a year.
The floors, with where each number comes from, are on [Platforms](platforms.md).

## Where this leads

The node is reading. Next, give it a way to reach you and prove the whole path once:
[First ten minutes](first-ten-minutes.md).
