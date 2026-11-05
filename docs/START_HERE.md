# Start here

> **Beta.** This is still an experiment and you are joining it. Things will break; what you report decides what gets fixed
> first. Write to **info@fab.city** with what broke, what helped, and what did not.

PLANETAI node is a small program that runs on a computer in your home, lab or community centre. It connects everything
that measures where you stand, from the sensor on the wall to the satellite overhead, into one picture of the place,
sharp enough to act on: what to do about the air, the heat, the sea, the land, today, here. It tells you in plain
sentences on Telegram, keeps the readings on your machine, and passes upward only what a city, a bioregion or a
planetary model needs from the ground.

Air is the first thing it watches, because that is the sensor most people already own. Heat, the coast and the land
ship too. Water, energy, noise and more are a folder of rules each.

## What you get

**Every scale in one picture.** The kitchen sensor, a radio in a field with no WiFi, the public station down the road,
the city's open data, the satellite model overhead. The gap between them is the signal no map has.

**Alerts you can act on.** Not "PM2.5 is 42." What is happening, what it means for the people in the house, and what to
do. "Inside is worse than outside. Something is cooking or burning. Open a window." English, Bahasa Indonesia or Spanish.

**A dashboard that reads like a sentence.** "Falling to 9 micrograms, under the ring, under the region, under the line."
Then the day as a chart, every source with a note, the sea, the land, the weather. On your phone or on a screen on the wall.

**A bot you can talk to.** Ask how the air is, how big the swell is, what the kitchen did overnight, or say you closed
the windows. A small model on your own machine answers; a bigger one on your network when it can reach it.

**A place that learns its own rhythm.** After a week the node knows when your street is worst and cleanest, and how much
of it your building keeps out. It tells you the hour to air the house.

**Your data, kept; your summary, shared.** The database never leaves the machine. Backups run nightly and a NAS can
collect them. What flows upward, if you point the node somewhere, is a daily summary: hourly means, Index cells, ρ.

**Nothing to buy.** An x86 Linux box first — an old laptop with Linux on it beats the mini PC you would
otherwise buy, and it is the machine this is designed for. A Mac works, and Windows through WSL2.
Raspberry Pi is untested (see `PLATFORMS.md`). Without a sensor it still knows your weather, the
satellite air model for your district and forty years of climate for your coordinates.

## Which machine

A node wants a computer that stays on. In order:

1. **An x86 Linux box.** A mini PC, or an old laptop you put Linux on — `REVIVE_A_LAPTOP.md` covers both
   Ubuntu Server (nobody uses it, it just runs) and Omarchy (somebody uses it, and it is also a node).
   The floor here does not move: Docker still supports Ubuntu 22.04, four years old.
2. **A Mac**, Apple Silicon or Intel, on macOS 13 or newer. It works. Be aware that every container
   runtime for macOS has raised its floor in the last two years, and an Intel Mac will meet that wall.
3. **Windows**, through WSL2 with Docker Desktop.

`curl -fsSL https://planetai.fab.city/preflight | bash` reads the machine in four seconds and tells you which
case you are in. It installs nothing.

## Install

```bash
curl -fsSL https://planetai.fab.city/install | bash
```

It asks four things: a name for the node, the place (type a town; it finds the coordinates), what the node is for (a
home, a business, a lab, a district), and your sensor if you have one. Two minutes later it is running.

The install ends with a checklist, the node's data sources, and *To finish setting up*: Telegram and the first backup
are on it on every new node, and a sensor if you have none yet; those come next. A cross next to *database* or
*node answers* means something is wrong; see [When it breaks](#when-it-breaks).

## Your first ten minutes

```bash
planetai telegram      # connects a bot: make one with @BotFather, paste the token, message it once
planetai test-alert    # a real alert arrives on your phone within a minute
planetai ui            # the dashboard's address, and the token for its settings pages
```

Open the dashboard. Set up → Sources is where you add or change sensors. Set up → Model is where the bot's brain lives.

When an alert arrives that you act on, tell the node: with the button on the dashboard, with `planetai act 12` in the
terminal, or by replying `/act 12 closed the windows` in Telegram once the bot runs (`planetai agent local`, below). The node keeps one score for itself: how many of its alerts led to someone doing something. That number is
called ρ, and it is the only one on the page that comes from a person.

## Talk to it

```bash
planetai agent local              # installs Ollama and starts the bot; it recommends a model and downloads none
planetai agent local pull <tag>   # downloads that model; the bot answers with it from then on
```

Then message your bot: "how is the air?", "how big is the swell?", "is the node healthy?". With a laptop or workstation
on your network running a bigger model, set its address under Set up → Model and the bot uses that when it can reach it.

## Everyday

```
planetai status      is it alive, what has it read, what fired
planetai doctor      every check, with the fix written next to any failure
planetai logs        what it is doing right now
planetai update      backup, fetch the latest version, migrate, rebuild, verify
planetai storage     where the data is, where the copies go
```

`planetai` on its own lists the rest: mesh radios, Home Assistant, packs, IPFS, restore.

A good week looks like this: a short report every six hours, a handful of alerts rather than dozens, one or two
that changed what you did, and a fresh file in `backups/`. Dozens of alerts a day means the thresholds are wrong for
your place; tell us which ones.

## What it will not do

It does not send your readings anywhere. It does not switch anything on or off; connect it to Home Assistant if you want
that. It does not replace a reference instrument; low-cost sensors drift and disagree, and the node says so where it
matters. It does not need the internet to keep working, only to send you messages.

## When it breaks

`planetai doctor` first. Everything below has happened to a real node.

| what you see | what to do |
|---|---|
| Nothing installs | Docker is not running. Open OrbStack or Docker Desktop, then run the line again. |
| `command not found: planetai` | Open a new terminal window. |
| `port is already in use` | `planetai config set APP_PORT 8081` — it writes `.env` and offers the restart. |
| No alerts at all | Normal when the air is fine. `planetai test-alert` proves the path works. |
| Alerts every few minutes | Thresholds wrong for your place. Tell us. |
| A sensor shows nothing | `planetai sensors`. A Smart Citizen kit must be publishing; an AirGradient is not polled in this version (`sensors.md`). |
| Telegram says nothing | Message the bot first; a bot cannot start a conversation. Then `planetai telegram` again. |
| The bot does not answer | `planetai logs agent`. The first lines say whether Telegram is set and which model it found. |
| Stopped after a power cut | The computer must boot and log in on its own. On a Mac: Login Items, and Energy → start after power failure. |
| A setting changed nothing | Settings made in the dashboard win over `.env`; the page says so next to them. |
| `planetai update` fails on `.DS_Store` | `find . -name .DS_Store -delete`, then update again. |

When you ask for help, write to **info@fab.city** with `planetai status`, `planetai doctor` and the last twenty lines of
`planetai logs`. Not `.env`: it holds your tokens. Tell us what you expected as well as what happened.

## Remove it

```bash
planetai remove              # containers, database, folder, cron entry, the command itself
planetai remove --keep-data  # the same, but the readings stay in their volume
```

It lists what will go — including how many readings, and any backups inside the folder — then asks twice:
once for yes, once for the node's name typed out. `planetai stop` is the gentler option: it stops the
containers and keeps everything.
