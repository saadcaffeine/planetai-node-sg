# Introduction
<!-- checked: v0.91.0 -->

PLANETAI is hyperlocal compute and intelligence for distributed production, and a node is its
unit: one computer per place, on hardware the place already owns. It reads your own sensors and the public
stations and models around them, tells the people there in plain sentences what to do, records what they did
and measures whether it worked. Raw readings stay on the machine that recorded them.

```bash
curl -fsSL https://planetai.fab.city/install | bash
```

The installer asks four questions and has the node running in about two minutes. After that, `planetai telegram`
connects the alerts to your phone and `planetai ui` opens the dashboard. [Install](install.md) walks through it,
and [First ten minutes](first-ten-minutes.md) takes you from a running node to a closed loop.

> **Note.** The node is beta. `main` is the beta channel and every update is signed, but installing one makes you
> part of an experiment: things will break, and what you report decides what gets fixed first. Write to
> **info@fab.city** with what broke and what helped. We run node #1, `bayu-ungasan`, in Kuta Selatan, Bali, and
> node #2 runs in Menorca.

## What it is for

Fab labs and makerspaces have spent twenty years building a distributed infrastructure for making things, and
since 2014 the cities of the Fab City pledge have committed to producing half of what they consume by 2054. That
infrastructure never had computing of its own, a machine at each place that reads the place, works out what it
needs and says why it should be made there instead of shipped in. A node is that machine. Its purpose is
fixed: clean air, water and soil for the people and the other living things around each node.

The rule it runs on is Fab City's rule for production, applied to data. Fab City calls the old pattern PITO,
product in, trash out, and the one it builds DIDO, data in, data out: materials stay in the city and knowledge
moves between cities. On a node, raw readings stay on the machine and only summaries travel: to a parent node if
you name one, into the daily open export, and from one city node per pilot to the
[Fab City Index](https://index.fab.city).

Today a node reads air and heat from the sensors in and around the house, and land and coast from public and
satellite sources. Two packs you turn on yourself read nearby fires and the ground's surface heat from
satellites, and a third, `terrain`, says where the next day's rain goes on the ground around the node. Soil has
no pack yet. The `make` pack names the nearest fab lab in a sentence, and no
node has handed a job to a workshop yet. What runs is the loop from a reading to a person acting and a
measured result; the loop from a reading to something made nearby is the direction.
[How it works](how-it-works.md#refusals-that-hold-at-every-stage) lists what the canon describes and the code
does not have. The programme behind it is at [planetai.fab.city](https://planetai.fab.city/).

## The loop

Sensors, public stations, open-data portals and Earth models feed the node. Everything after that is one loop
in four stages, observe, decide, act and measure, and the dashboard has a part for each. An alert says what is
happening, what it means and what to do. A person answers it on the dashboard, in Telegram or from the
terminal, and the node counts how many act-level alerts were answered. That share is [ρ](rho.md), and it can
only be measured where the alert is sent and the answer comes back.
[How it works](how-it-works.md) follows one reading through every stage.

![Sense feeds observe, decide, act and measure; an act-level alert sent and the answer that comes back are what ρ counts](img/loop.svg "Every act-level alert sent, and every answer that comes back within 24 hours, is what ρ counts.")

In learn mode the dashboard puts a question mark on each part of the page that quotes these pages for it, and
the [ask pane](ask.md) answers questions about what the page shows, with a model on this machine or your own
network unless someone here chooses an online one.

## What stays, and what goes up

Raw readings stay on the machine. A parent node, if you name one, gets hourly means and alert timestamps, and
the daily open export carries hourly means, the Index cells, the first line of each alert and ρ under CC BY 4.0.
By default no question goes to a model outside your network (`AGENT_PREFER=private`) and the dashboard fetches
no live map tiles (`MAP_TILES=off`). Every hour the node asks planetai.fab.city whether a newer version is out
and reads the programme's lists of nodes and of wild packs from GitHub. Every six hours it refreshes its own copy of
the workbench's firmware. All of them show the house's internet address and nothing else, and `UPDATE_CHECK=off`
stops them. The full list is in
[How it works](how-it-works.md#what-leaves-the-machine-and-what-never-does).

## What a node is not

It sends no raw reading anywhere, and it switches nothing on or off; connect it to Home Assistant for that. It
does not act for you: an agent may draft, but every act is a person's row in the `actions` table. Low-cost
sensors drift and disagree, so it does not replace a reference instrument, and the node says so where it
matters. It is also not a cloud service. It is two containers on a machine you own, with the database on a
local disk, and the internet is only how it reaches public stations, models and Telegram.

## Who it is for

A household with a sensor in the living room that still does not know whether to open the window. A fab lab
that wants its own address on the [Fab City Index](https://index.fab.city). A school or clinic with a duty of
care. A banjar or a desa that wants its own number on the island's map. And the people who keep the sensors
alive for all of them, which [`PRODUCT.md`](../../PRODUCT.md) describes as "someone whose job it is to keep the
sensor alive and the alerts correct".

## What these pages are

This is the reference for the node at v0.91, read from its code. Where a page and the code disagree, the code
wins and the page has a bug; the link at the foot of every page opens its source on GitHub. The sidebar follows
the order a node is built in:

| group | what is in it |
|---|---|
| Start here | this page, [How it works](how-it-works.md) and the words the other pages use, in [Concepts](concepts.md) |
| Get started | the machines it runs on, the install and the first ten minutes |
| Run a node | the CLI, settings, updates, backups, networking, sharing and troubleshooting |
| Sensors and sources | your own sensors, radios, the source registry and what a node reads before it has a sensor |
| Alerts and ρ | rules and levels, the channels alerts go out on, the report and how ρ is counted |
| Packs | how to write a pack, every field a pack can declare, and the issues a place watches |
| Dashboard | the page, the wall screen, the design rules behind both, and Grafana |
| Agents | the ask pane, agents on the node, the MCP tools and the Telegram bot |
| Reference | the [HTTP API](api.md), the [database](schema.md) and the [federation contracts](federation.md) |
| Project | the architecture and the spec the rest is measured against, how to develop the node, and the changelog |

## Where to go next

| you want to | read |
|---|---|
| know whether your machine can run it | [Platforms](platforms.md) |
| install it | [Install](install.md) |
| get from a running node to a closed loop | [First ten minutes](first-ten-minutes.md) |
| add a sensor | [Sensors and sources](sensors.md) |
| read the dashboard | [Dashboard](dashboard.md) |
| write a rule for your place | [Packs](packs.md) |
| join a district as a child node | [Federation](federation.md) |
| connect Claude, Codex or a local model | [Agents](agents.md) |
