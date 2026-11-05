---
name: setup-node
description: Walk a person through installing a PLANETAI node on their own machine, from the preflight check to the first alert on their phone.
---

# Setting up a node

The person in front of you has no node yet. `docs/START_HERE.md` is the walk-through and it is written for
them, not for you: read it first, then use it. This file only says what order to do things in, and what
never to do.

## Read, in this order

1. `docs/START_HERE.md` — the whole install, the four questions, the first ten minutes.
2. `docs/PLATFORMS.md` — only if the preflight says the machine is a problem.
3. `docs/REVIVE_A_LAPTOP.md` (an old laptop, either route) or `docs/MAC_MINI.md` (a Mac that stays on).
4. `AGENTS.md` — before you touch anything on a node that is already running.

## The order of operations

**1. Read the machine before you promise anything.**

```bash
curl -fsSL https://planetai.fab.city/preflight | bash
```

It installs nothing and takes four seconds. `--json` if you want to parse it. Read the exit code, not
the prose:

| exit | what it means | what you do |
|---|---|---|
| 0 | this machine can run a node | install |
| 1 | checks failed and each printed its own fix | apply the fixes, run it again |
| 2 | below the floor: no container runtime can be installed on this OS | **stop**, and read the two routes it printed |

**Never talk a person into a machine the preflight refused.** Exit 2 is not a warning to work around. The
check already printed whether upgrading is a route on that exact model and two routes that do work
(Linux in a VM, or Linux on the metal); your job is to help with one of those, not to try the install
anyway "to see". A node that half-installs on an unsupported machine costs an evening and teaches nothing.

**2. Install.**

```bash
curl -fsSL https://planetai.fab.city/install | bash
```

Four questions: a name, the place, what the node is for, the sensor if they have one. The only sensor it offers
is a Smart Citizen kit: the node does not read an AirGradient or a PurpleAir yet, so do not suggest either until
the `air-sensors` pack reads them. If they cannot sit
at a terminal for it, `planetai setup --answers node.json` takes the same answers as a file — the JSON
shape is in `bin/planetai`.

The install ends with a checklist and *To finish setting up*. Telegram and the first backup on that list are expected
at this point, and a sensor if the person has none yet; walk them through it in that order. A cross next to
*database* or *node answers* is not: go to `troubleshoot-node`.

**3. Telegram, then a real alert.**

```bash
planetai telegram
planetai test-alert
```

They make the bot with @BotFather and must message it once themselves — a bot cannot open a conversation.
Do not skip `planetai test-alert`; it is the only proof the whole path works end to end.

**4. Hand them the node.**

```bash
planetai ui        # the dashboard's address and the token for its settings pages
planetai doctor    # every check, with the fix written next to any failure, then the node's data sources
```

If the home has sensors in more than one room, name each room in Set up › Rooms: every alert and report then says
"Kids" or "Kitchen", not the kit's own name, and a screen without the token still reads only "Room A".

Then say the three things `docs/START_HERE.md` says: what a good week looks like, that ρ only moves when a
person tells the node they acted, and that this is beta and info@fab.city wants to hear what broke.

## Never

- Never continue past preflight exit 2.
- Never install on a machine that sleeps. A sleeping machine is a stopped node; the preflight says how to
  stop that on their OS.
- Never print, paste or read back `.env`. It holds their tokens.
- Never set a threshold during setup to make the first hours quieter. The defaults are wrong for some
  places and that is information; a node tuned before it has measured anything is tuned to nothing.
- Never run `pip` on the host or add a Python dependency to the CLI. See the invariants in `AGENTS.md`.

## When a doc and this file disagree

The doc wins and this file has a bug. Say so, and open an issue.
