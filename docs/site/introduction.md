# Introduction
<!-- checked: v0.80.10 -->

PLANETAI is hyperlocal compute and intelligence for distributed production, and a node is its
unit: one computer per place, on hardware the place already owns. It reads what measures that place, from a
particle sensor on the wall to a satellite overhead, tells the people there in plain sentences what to do
about it, records what they did, and measures whether it worked. Raw readings stay on the machine that
recorded them.

```bash
curl -fsSL planetai.fab.city/install | bash
```

Four questions, two minutes, running. Then `planetai telegram` for the alerts and `planetai ui` for the
dashboard. The walk-through is [Install](install.md); the ten minutes after it are
[First ten minutes](first-ten-minutes.md).

> **Note.** The node is beta: `main` is the beta channel and every update is signed. Installing one still makes
> you part of an experiment: things will break, some will surprise you, and what you report decides what gets
> fixed first. Write to **info@fab.city** with what broke, what helped and what did not. Node #1, `bayu-ungasan`, has run in Kuta Selatan, Bali, since 2 September
> 2026. Node #2 runs in Menorca.

## What it is for

Twenty years of fab labs and makerspaces built a distributed infrastructure for making things, and since 2014
the cities of the Fab City pledge have committed to producing half of what they consume by 2054. What that
infrastructure never had is computing of its own: a machine at each place that reads the place, works out what
it needs, and says why it should be made there rather than shipped in. A node is that machine. Its purpose is
fixed: clean air, water and soil for the people and the other living things around each node.

The rule it runs on is Fab City's rule for production, applied to data. Fab City calls the old pattern PITO,
product in, trash out, and the one it builds DIDO, data in, data out: materials stay in the city and knowledge
moves between cities. On a node, raw readings stay on the machine and only summaries travel, to a parent node
if you name one, to the [Fab City Index](https://index.fab.city), and to the models that need ground truth.

In v0.80 a node reads air and heat from the sensors in and around the house, and land and coast from public
and satellite sources. Water and soil have no pack yet. The `make` pack names the nearest fab lab in a
sentence, and no node has yet handed a job to a workshop. What runs today is the loop from a reading to a
person acting and to a measured result; the loop from a reading to something made nearby is the direction.
The programme behind it is at [planetai.fab.city](https://planetai.fab.city/).

## The loop a node runs

Sensors, public stations, open-data portals and Earth models feed the node; that is *sense*. Everything after
it is one loop in four stages, and the dashboard has a part for each; Now draws Decide first. The page describes
each stage in its own words:

| stage | what it holds |
|---|---|
| observe | what is read, seen and heard about this place |
| decide | what to do about it |
| act | what has been asked, of whom |
| measure | whether it worked, and how long it took |

The README says what the alerts are for: they "say what is happening, what it means, what to do. Then the
node measures whether anything changed: ρ, the share of act-level alerts somebody answered, a number the Index never had." ρ can
only be measured where the alert is sent and the answer comes back, which is here. [ρ](rho.md) has the
definition.

Since v0.72 the loop closes on the dashboard itself. An open act-level alert about one of the place's issues
shows under Decide, with the rule's own recommendation beside what was seen. A person records a decision there, then
presses **I did this** on the same card when it is done, and Measure shows ρ and, per rule, which acts were followed
by the condition clearing. A node on `ALERT_ENGINE=shadow` or `events` draws each open event once instead, with the
action the bot sent and Done, Not now and Doesn't fit. After a week of its own readings the node also draws "The day this place usually
has" on the Historical view. [How it works](how-it-works.md) follows a reading through every step.

The dashboard also explains itself and answers questions: learn mode puts a question mark at each part of the page, and pressing one quotes these pages for it in the pane beside the page. That pane asks the model Set up names about what the page shows: on this machine or on your own network, and online only when someone here chooses it ([Ask the node](ask.md)).

## What stays, and what goes up

Raw readings stay on the machine. A parent node, if you name one, receives hourly means and the timestamps of
this node's alerts. The daily open export carries hourly means with your own sensors named by role, the Index
cells, the first line of each alert and ρ, under CC BY 4.0. A node that nobody has told otherwise sends no
question to a model outside your network (`AGENT_PREFER=private` is the default), and the dashboard fetches no
live map tiles until a keeper sets `MAP_TILES=on`. Once a day it asks planetai.fab.city whether a newer version
is out, which shows the house's internet address and nothing else about it; `UPDATE_CHECK=off` stops that. The
full list is in
[How it works](how-it-works.md#what-leaves-the-machine-and-what-never-does).

## What a node is not

It sends none of your readings anywhere, and it switches nothing on or off; connect it to Home Assistant if
you want that. It does not act for you either. An agent may draft, but every act is a person's row in the
`actions` table. Low-cost sensors drift and disagree, so it does not replace a reference instrument, and the
node says so where it matters. Nor is it a cloud service: it is two containers on a machine you own, with a
database on a local disk and nothing that requires a provider to function. The internet is how it reaches public stations,
models and Telegram.

## What is not built

Some of what the canon describes is not in the code, and these pages do not pretend otherwise.
`ARCHITECTURE.md` has an Act layer that ends, when the decision is physical, in a fabrication ticket. No such
ticket exists: there is no `fabricate` stage, and no job has been handed to a workshop. The nearest the node
comes is the `make` pack, which names the closest fab lab in a sentence and is off until `MAKE_ENABLED=1`.
Nodes finding each other (`docs/SPEC_discovery.md`) is marked "Not built". A node as a key rather than a
name (`docs/SPEC_identity.md`) and the second ρ, the one that asks whether the reading recovered
(`docs/SPEC_rho.md`), are both "Phase 1. Nothing here is built." A decision on the dashboard is one person
deciding for one node; how several households' decisions become a street's is not on a node at all.

## Who it is for

A household with a sensor in the living room that still does not know whether to open the window. A fab lab
that wants its own address on the [Fab City Index](https://index.fab.city). A school or clinic with a duty of
care and a budget line for health and safety. A banjar or a desa that wants its own number on the island's map.
And the people who keep sensors alive for all of them, which is the part of this that is a service rather than
a program. The argument is in [`PRODUCT.md`](../../PRODUCT.md): "someone whose job it is to keep the sensor
alive and the alerts correct."

## What these pages are

This is the reference for the node at v0.80, read from the code of that version. The pages under *Get
started* and *Operate* are for the person running one. *Alerts, reports and ρ*, *Packs*, *Dashboard* and
*Agents* explain what the node does and how to change it. *Reference* is the [HTTP API](api.md), the
[database](schema.md) and the [federation contracts](federation.md). *Project* holds the architecture and the
spec, the canon the rest of this is measured against.

Where a page and the code disagree, the code wins and the page has a bug: the link at the foot of every page
opens its source on GitHub.

## Where to go next

The path runs in the order a node is built: run it, connect what measures your place, read it, let it ask and
answer, measure whether that worked, extend it, join the network, put an agent on it.

| you want to | read |
|---|---|
| know whether your machine can run it | [Platforms](platforms.md) |
| install it | [Install](install.md) |
| get from a running node to a closed loop | [First ten minutes](first-ten-minutes.md) |
| understand the words the rest of the pages use | [Concepts](concepts.md) |
| see what it does with a reading | [How it works](how-it-works.md) |
| add a sensor | [Sensors and sources](sensors.md) |
| read the six views and the three modes of the page | [Dashboard](dashboard.md) |
| write a rule for your place | [Packs](packs.md) |
| join a district as a child node | [Federation](federation.md) |
| connect Claude, Codex or a local model | [Agents](agents.md) |
| read its API | [HTTP API](api.md) |
