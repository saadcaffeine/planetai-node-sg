# Nodes finding each other

*Proposed, 22 September 2026, from Tomas: "it is interesting for nodes to choose to be discoverable,
which does not mean accessible or sharing data, just sharing I am in X cell, and can say hi to other
nodes, and also see them. So someone can choose for their node to be visible in the network or not."*

Not built. This is the specification; nothing in it ships until it is read and argued with.

**Tailscale first, Reticulum after** — decided 22 September. Sections 2–5 are the tailnet, which is
what gets built. Section 6 is the radio, which is the same announcement over a different wire and
waits its turn. Section 7 is what comes after seeing, which is not specified yet and says so.

## 1 · The three things this is not

Discovery is a small idea that attracts large ones. It is worth writing down what it refuses before
what it does.

- **Discoverable is not accessible.** A node that says it exists has not opened its API. `SHARE_LEVEL`
  is untouched by this and stays the only thing that decides who may read what. A node can be
  discoverable at `SHARE_LEVEL=off`, and that combination is the expected one.
- **Discoverable is not sharing data.** Nothing here carries a reading, an alert, a sensor, a
  household's sentence, or a position. Nothing here rolls up into a cell or a count.
- **Discoverable is not being listed by somebody else.** There is no registry, no rendezvous server,
  no bootstrap host, nothing to sign up to and nothing to be removed from. A node answers for itself
  or it does not answer.

## 2 · What a node says

Exactly what `GET /presence` already returns, plus one field saying which wires it is visible on.
Node #1 today, with the addition:

```json
{"enabled": true, "on": ["tailnet"], "node": "bayu-ungasan", "cell": "8395a4fffffffff", "res": 3,
 "version": "v0.71", "kind": "home"}
```

A name the keeper chose, a **coarse H3 cell**, the resolution it was coarsened to, the version, and
what kind of place it is. The cell is the node's own res-8 cell rounded **up** to res 3 — about sixty
kilometres across, which names an island rather than an address. Resolution 6 — about three
kilometres — is the finest anything may ever be announced at, and it is a constant in `app/main.py`
rather than a setting, because "which neighbourhood am I in" is not a thing a person should be able
to publish by typing a number into a box.

**`version` stays** (confirmed 22 September). "A `community` node three cells away is on v0.66" is how
help gets offered, and a version number is also the first thing anyone asks when something is broken.
`kind` rides on the same argument and the same footing: both are a fingerprint, and both are worth it.
If either goes, say so and it goes from the announcement, not from a flag.

Off, it answers `{"enabled": false}` and stops. Not a 403, not silence: the honest answer to "are you
there" is "yes, and I am not saying".

**Distance between two nodes is the distance between two cell centres,** and neither of them ever
published a position. Two nodes in the same res-3 cell know they are within about sixty kilometres of
each other and nothing more precise than that, ever, by construction.

## 3 · Two switches, one per wire

`/presence` is gated today on `RETICULUM_PRESENCE`, which is a **radio** setting: it turns on a
broadcast over LoRa and Reticulum to anyone within reach. Being visible to the four machines on your
own tailnet is a different decision from broadcasting to an open radio network, and neither should
imply the other. So there are two switches and a keeper picks either, both, or neither:

| setting | default | what it turns on |
|---|---|---|
| `DISCOVERY` | `0` | this node answers `/presence` to other machines on the tailnet, and looks for them |
| `RETICULUM_PRESENCE` | `0` | this node announces the same body over the radio, as now |

Both live under Set up → Node, side by side, with one sentence each. Neither is enabled by an update.

**The endpoint stays the one place the policy lives.** The bridge (`reticulum_bridge.py`, fabcity/planetai-reticulum) does not compute the
cell or read the settings; it calls `GET /presence` on localhost and announces whatever comes back
(`announce_presence`, and its own comment: *"asking keeps the policy in one place"*). That
stays true. `/presence` answers:

- to **localhost** — always, with `on` listing every wire that is enabled. The bridge announces when
  `on` contains `radio`, and otherwise does nothing, which is what it does today.
- to **anyone else** — the body when `DISCOVERY=1`, and `{"enabled": false}` when it is not.

So a node running the radio today keeps announcing over the radio, unchanged, and goes **quiet on the
tailnet** until somebody turns `DISCOVERY` on. The update makes exactly one node quieter and no node
louder, which is the only direction an update is allowed to move this.

**One switch, both directions, per wire.** A node that is not discoverable on the tailnet does not
look for others on the tailnet either. The alternative — seeing without being seen — is the shape of
a thing that watches, and it is not what this is. If you want to know who is out there, be someone
they can know about.

## 4 · How a node finds the others

Tailscale already knows every machine on the tailnet; the node does not need a directory because the
tailnet is one.

**The host reads the peer list. The node never talks to `tailscaled`.** `planetai mesh` already
installs and joins Tailscale on the host, and `bin/planetai` already runs there. A new
`planetai mesh peers` runs `tailscale status --json`, takes each peer's name and tailnet address, and
writes that list into the node.

The obvious alternative is mounting `/var/run/tailscale/tailscaled.sock` into the container so the
node refreshes itself. **Refused.** That socket is the Tailscale LocalAPI, and it can bring the
tailnet up and down, read the whole network map and rewrite routes. A container serving a page to a
household LAN should not hold it. A list of names and addresses is the whole of what discovery needs,
and it is the whole of what it gets.

Then the node, on a slow loop — hourly, not every poll, because a neighbour appearing is not urgent —
does `GET http://<peer>:8080/presence` on each. That is the entire protocol. There is no write, no
handshake, no registration, no heartbeat.

**Saying hi is answering.** Both nodes probe, so both see each other, and neither had to tell anyone
anything. A node that has not answered is simply not listed.

**A tailnet is not all nodes.** It has laptops and phones, and probing port 8080 on each is a scan of
your own network — one request per machine per hour, but still worth being exact about. A reply only
counts when it is JSON carrying `enabled`, and when true a `cell` and a `node`. Anything else is a
machine that is not a node, and the node records nothing about it at all: not that it was probed, not
that it refused, not that it exists.

## 5 · What a keeper sees

On **Network**, beside the map of what this node hears by radio, a row per node that answered:

> `mahon` · home · v0.67 · **340 km away** · answered 4 minutes ago

and, when this node is not discoverable, one line instead of a list: this node is not looking, here is
the setting, and here is what turning it on would say about you — the name, the cell, the version, the
kind, and the sixty kilometres.

The list is drawn from what came back and is never cached into a claim: a node that stops answering
leaves the list, it does not become a node that "was" there. Nothing here enters `sensors`, `cells`,
`custody` or any count. It is not a source and it is not a peer in the `kind='peer'` sense — those are
readings, and this is not readings.

## 6 · The same thing over the radio, later

The radio already carries this. The bridge announces a `planetai.presence` destination
with the body from section 2, and a `PresenceHandler` remembers every node it hears. What changes when
Reticulum's turn comes is small and mostly honesty:

- the two lists become one on Network, each row saying which wire it came in on;
- a node heard by radio has no address you can fetch, so it is a name and a cell and nothing else,
  which is the floor anyway;
- the announcement gains `on`, so a node heard over the radio can say it is also reachable on a
  tailnet you may or may not share.

A node can be visible on the radio and invisible on the tailnet, or the reverse. That is the whole
point of two switches, and the radio is the case where it matters most: LoRa reaches people who are
not on your tailnet and never will be.

## 7 · After seeing: overlap, comparison, aggregation

*From Tomas, 22 September: "for peer exchange of nodes, we can see ways in which they can compare
data, see overlaps, and become aggregators of each other at specific cells."*

Seeing each other is where **discovery** stops. This is the next thing to specify, and it is three
steps, each one costing more than the last. Nothing below is designed yet; what follows is the shape
it has to fit into and the questions that decide it.

**Overlap — do we cover the same ground?** Free, and already in the announcement: two nodes in the
same res-3 cell are within sixty kilometres, and that is the coarse answer. The sharp answer — *which
cells do we both have sensors in* — is a list of res-6 cells, and a list is a much sharper fingerprint
than a single cell. So the free version stays coarse and anything finer is a **read**, which makes it
`SHARE_LEVEL`'s business and not discovery's. That boundary is the one thing here that is already
decided.

**Comparison — do we agree?** The useful one, and the reason to bother. Two nodes measuring PM2.5 in
one cell can compare a **statistic** — a median over a window, per variable, per cell — without either
raw series moving. The payoff is calibration: a sensor reading 7 µg/m³ above a neighbour four hundred
metres away is probably drifting, and nothing else on a node can tell you that. It is a read of
derived numbers, so it is gated by `SHARE_LEVEL` and needs a token like everything else.

And it is a **question, not a verdict**. Two sensors legitimately disagree — one indoors, one beside a
road, one in the sun. A comparison shows two numbers and a distance. It never marks one wrong, and it
must never quietly correct anything.

**Aggregation — does one of us report for the cell?** This is the one with teeth, because it touches
`custody`, which is the only thing a cell may count:

```sql
custody := kind = 'child' OR (local AND kind <> 'peer')
```

Read "become aggregators of each other at specific cells" precisely and it resolves cleanly: **the
grant is per cell, not per node.** A grants B the cell where B has six sensors and A has one; B grants
A a different cell. Both are aggregators, neither is the other's parent, and there is no cycle —
because the invariant is **one cell, at most one aggregator**. Without it the same reading is counted
twice and the Index inherits the error silently, which is the worst failure available here.

Mechanically this is smaller than it sounds: it is `PARENT_API_URL` generalised from one parent to a
map of cell → aggregator. A row arriving from a peer is `kind='peer'` and counts for nothing, exactly
as now, until a grant makes it `kind='child'` **for that cell only**.

Three refusals survive intact and are not up for negotiation:

- **Aggregating does not upgrade a cell.** A cell is `live` because somebody measured in it, not
  because somebody totalled it. `ARCHITECTURE.md:217` already says so.
- **No raw reading leaves the instance that recorded it.** An aggregator receives what a child sends
  today, not a database.
- **No scale is skipped.** The Index counts nodes. An aggregator is a convenience between keepers, not
  a new authority, and it does not become a rung in the ladder by existing.

What is open: what a grant looks like to a third party, or whether it is nobody else's business; who
revokes it and how fast; what happens to a cell whose aggregator vanishes — which is survivable,
because nothing left the node that made it, but somebody still has to notice; and whether a grant is
symmetric by convention or two independent one-way decisions that happen to point at each other.

## 8 · What it refuses, at every stage

- No position, ever, at any resolution finer than the floor in the code.
- No reading, no alert, no sensor, no household sentence.
- No record of who probed this node. A node answers; it does not keep a visitors' book.
- No write endpoint. Discovery adds no way for another machine to change anything here.
- No central list, no bootstrap node, no service that has to be up for this to work.
- Nothing is enabled by an update. Both switches default to `0` on a node that already exists and on
  one installed tomorrow.

## 9 · Still open

- **The tailnet boundary, past the tailnet.** Everything in sections 2–5 assumes the people on one
  tailnet already trust each other enough to be seen. Section 6 is the answer for people who are not
  on it. What is still unanswered is the middle: two tailnets, no radio between them, both willing.
  There is no mechanism here for that and no plan to invent one.
- **All of section 7.** The shape is above; the design is not.

---

*Grounded in `app/main.py::presence` and `PRESENCE_RES_FLOOR`, the bridge in fabcity/planetai-reticulum (the
announce loop and `PresenceHandler`), `ARCHITECTURE.md:217` on aggregation, `docs/site/concepts.md`
on `custody`, `docs/site/federation.md` ("listening to other nodes as peers is proposed and not built
in this version"), and `docs/site/cli.md` on `planetai mesh`.*
