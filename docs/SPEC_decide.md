# Deciding, and being able to tell whether it worked

*Proposed, 22 September 2026, from Tomas: "it is not specifying which decisions are made, or by whom.
I think we need to be able to provide insights on the behaviour of the data in the observation layer,
at different scales and dimensions, and then have the option for the node owner to decide something…
creates an action or options of actions that then can be measured depending on when and where they
executed and how impact the readings again."*

**Status: nothing here is built.** This is the document to argue with before any code is written.

The honest headline: about two-thirds of this already exists and is unreachable from the page.

## 1 · What this is not

- **Not a second ρ.** ρ has a specification of its own (`docs/SPEC_rho.md`) and one meaning. Nothing
  here changes what it counts.
- **Not advice.** The node does not tell a household what to do about its air. It can say what
  changed, and it can hold you to what you said you would do.
- **Not a workflow.** No assignees, no due dates, no statuses beyond the three the ledger already
  has. A decision is one sentence and one thing to watch.
- **Not dependent on a model.** The agent container is optional (`profiles: ["agent"]`). Every word
  below works on a node that has never run one.

## 2 · What is already built

Worth being exact about, because it is most of the loop:

| | where | what it does |
|---|---|---|
| the ask | `alerts` | a rule fires and a row exists: `rule_id`, `sensor_id`, `level`, `text` |
| the decision | `POST /actions` | `stage` · `actor` (80 chars) · **`note`, 500 characters in the keeper's own words** |
| the measurement | `app/index.py::_funnel` | **derived, never posted** |
| the hand | MCP `act(alert_id, note, agent)` | what the local model already uses |

`POST /actions` is guarded by `ACT_TOKEN`, deliberately weaker than the admin token, so somebody in
the house can close a loop without being handed the key to `/settings/raw`.

**The measurement is the part worth admiring, and it is already right.** Nothing writes a `measured`
row. `run_rules` re-fires an alert the moment its cooldown expires and the condition still holds, so
an act followed by `MEASURED_WINDOW_MIN` (2,880 minutes — 48 hours) of silence *from the same rule on
the same sensor* is the condition having stopped being true. It is evidence of whether, never of
when, and `latency_minutes.measured` is `null` on purpose. It works retroactively, on every node,
with nobody asked to learn a new habit. **This is already "how it impacts the readings again."**

## 3 · What is missing

Three things, smallest first.

**The page cannot act.** In seven thousand lines of `dashboard.js` the only write is `/settings`. The
page draws a funnel counting acted and measured and offers no way to make either. Every act on node #1
was made over Telegram, MCP or curl. This costs nothing to close: a note field and two buttons on each
open ask in Act, posting to an endpoint that already exists and already takes a note.

**A decision must be a reply to a rule that already fired.** `POST /actions` 404s without a valid
`alert_id`. Somebody who reads Observe, sees something, and decides to do something has no row to
write.

**Nothing proposes options.**

And the framing problem underneath: Observe has fourteen sections. Decide has three — claims, grain,
trust — and all three answer *at what grain may this be said*, not *what is the data doing and what
should I do about it*. The loop is named as four stages and built as one.

## 4 · An insight

An insight is not a number. It is **a number that changed, at a stated grain, against a stated
comparison** — and this page already refuses to draw a number without a comparison (T4 counts the
ones that try). So an insight carries four things or it is not one:

- **the claim** — what moved
- **the grain** — which stop of the dial, or which of the four distances. An insight at resolution 4
  and the same insight at resolution 10 are different claims, and this page is the one thing on the
  network that already knows how to say so.
- **the window** — over what stretch of time
- **what it is measured against** — its own history, the line, or the same variable at another
  distance

Three kinds the node can derive today, from views it already has:

- **against itself.** `stats` carries `mean_15m`, `mean_1h`, `mean_24h` per sensor and metric. The
  short mean pulling away from the long one is the whole of "something is happening now".
- **against the other distances.** The room against the wall outside against the street against the
  model — the stack the lead already draws. A room worse than its own street is a different problem
  from a street worse than its model, and only the comparison says which you have.
- **against the grain.** The flat run `grain` already finds: past some resolution, finer stops stop
  telling you anything new. An insight drawn finer than the flat run begins is precision with no
  information in it, and the page should refuse to offer a decision at a grain it has already proved
  is empty.

The catalogue is open. The four things an insight must carry are not.

## 5 · A decision is a prediction

*Decided 22 September: a decision names what it expects to stop being true.*

This is the only shape in which the node can tell you whether you were right, and the reason is the
measurement in §2: `measured` is derived from **a named rule going quiet on a named sensor**. A
free-text decision about nothing in particular can be recorded and can never be closed, because the
mechanism has nothing to watch.

So a decision is two sentences from a person and one thing for the node to watch:

> *I closed the windows on the north side.*
> *I expect PM2.5 at the wall outside to be under 25 within two days.*

The second sentence is a **watch**, and a watch is an ordinary rule: metric, sensor, comparator,
threshold, window. Note which way round it is written — the watch is the condition the keeper expects
to **stop** being true, because silence is what the funnel reads. "Under 25" and "the watch *at or
above 25* goes quiet" are the same statement, and only one of them is measurable.

**From a template, never from a keeper's SQL.** A rule is SQL over the `stats` view. Nobody is going
to type that, and a form that accepts SQL is a hole even read-only. The node composes the statement
from five values; the keeper picks a metric, a station, a direction and a number.

**The evaluator does not change by one line.** `run_rules` iterates whatever `packs.load_rules()`
returns, and runs each statement through `index.run_ro` **as `planetai_ro`** — SELECT on every table
but settings, no writes. A watch that joins that list is already sandboxed by machinery that exists.

**The cooldown is the window.** Set it to the decision's own window and the watch fires at most once
per window: one message per two days, not noise, and the funnel reads it exactly as it reads every
other act-level alert. It has to be act level, because `_funnel` counts `level='act'` and nothing
else.

### Where a watch lives, and why not in `config/`

`docker-compose.yml` mounts `./config:/app/config:ro`. Read-only, on purpose. A container serving a
page to a household LAN must not be able to rewrite its own rule set on disk, and the only writable
path in the whole service is `./out`, which is for artefacts a pack makes.

So **a watch is a row in Postgres**, and `load_rules()` gains a third source beside core and packs.
The node already has a database; a watch is a record, not a config file.

### A watch is retired, never deleted

`_live_rule_ids()` exists for a reason that bites here. A rule that has been renamed or deleted can
never fire again, so its silence is not evidence of anything — and counting it would turn every
retired rule into a success. The node found three of those on a live database and the funnel's real
number was 5, not 8.

A keeper deleting a watch would therefore **retroactively convert every decision made against it into
a success.** So: `retired_at`, and the derivation keeps ignoring anything not currently live. This is
the single sharpest constraint in this document and it is not negotiable.

## 6 · The decision is the record, and the action may never come

*From Tomas, 22 September: "it is important to record the decision… If there is no act, then it
should be taken as no action, so the process is recorded but does not affect further down, it is as
an action that never happens. But an action coming from a decision and it never happened, it should
show that the decision was made."*

This splits something the ledger currently runs together. `actions` has three stages —
`acknowledged`, `acted`, `measured` — and the *decision* is not among them. Today a decision only
exists as the note attached to an act, so a decision that was made and never carried out leaves no
trace at all: the ask simply stays open, as though nobody had thought about it.

So a decision is its own record, and an act is a separate thing that may or may not follow it:

| | what it means | what it does downstream |
|---|---|---|
| **decided** | somebody thought about this and said what they would do | **nothing** |
| **acted** | it was done | the funnel's `acted`, and the watch starts earning its answer |
| **measured** | the condition stopped being true | derived, as now |

**A decision alone moves nothing.** It does not close an ask, it does not enter ρ, it does not count
as `acted`, and it does not make a cell or a count say anything different. In Tomas's words it is
*an action that never happens* — and the point of recording it is precisely that the node can tell
the difference between a household that never looked and a household that looked, decided, and did
not manage it. Those are opposite facts and today they are the same blank.

**And it stays visible.** A decision with no act is not a failure to be tidied away. Where an ask
shows as open, it shows *what was decided about it and when*, and the page says plainly that the
thing was not done. That is the one place this spec asks the page to be blunt: the honest sentence
is "decided on the 14th, not done", not a quiet omission.

Two consequences worth writing down now:

- **A decision needs no watch.** §5's prediction is what makes an *act* measurable. A decision that
  never becomes an act has nothing to measure and needs nothing, so nothing in §5 gates §6. The
  watch is created when the act is recorded, not when the decision is.
- **The stage goes in the same table, and there is already a precedent for adding one.**
  `actions.stage` is a CHECK constraint that `init.sql:135` drops and re-adds with **four** values —
  `acknowledged`, `acted`, `measured` and `settings`. That fourth one is the node recording its own
  configuration changes: `alert_id` NULL, no ask, counted by nothing. `_funnel` selects the three it
  names and ignores it, which is exactly the treatment `decided` needs. So this is a fifth value by
  the same two lines of migration, and every existing consumer ignores it without being told. What
  must **not** happen is `decided` counting anywhere `acted` counts, which is the whole of §6.

## 7 · At this scale, one person. At the next, consensus

*From Tomas: "at this scale is individual, but as we keep developing the node, it will be collective,
depending on the scale of the decision. If I decide to do something about my street, maybe need to
build consensus with other neighbors."*

Not built, and not designed here — but the shape of §6 has to leave room for it, so:

**A decision carries the scale it is about.** This node already has the vocabulary and uses it for
everything else it says: the four distances (room · wall outside · street · model) and the eleven
grains of the rail. A decision about the room is one person's and needs nobody. A decision about the
street is about ground this node shares with nodes it can already see — §4 of `SPEC_discovery.md`
gives it the list — and one household recording it does not make it true for the street.

So the field exists from the first version and the consensus does not. A decision at room scale is
complete when one person makes it. A decision at street scale is **recorded by whoever made it and
marked as one household's**, and what turns several of those into a decision the street has taken is
the question the collective version answers. It is a real question — who is asked, what counts as
agreement, what a node does when its neighbours disagree, and whether a decision can bind anyone who
did not answer — and none of it should be guessed at while there are two nodes on the network.

What matters now is only that a decision recorded today at street scale is still legible when that
arrives, rather than being an individual decision with a bigger word on it.

## 8 · How a decision reaches the node

*From Tomas, 22 September: "how it can 'talk' to the node (telegram?), does the decision need to come
via telegram? or there is a text interface in the decision section (I was expecting that)… or the
node just decides for the user, it is an informed decision based on observation, and that the user
can validate or not."*

**Not Telegram, and the node was already telling people it was.** `act_hint()` composes the line the
page prints under every ask — *"Reply /act 361 on Telegram"*, or `planetai act 361` on a node with no
bot — because until 22 September the page was the one surface that could not close a loop. That
sentence is still right in a Telegram message and wrong on a screen with the button on it.

**And the node already decides.** This is the part that needed finding rather than designing. Every
rule in `config/rules.yml`, and every pack rule, ends its message with a line beginning 👉:

> 🔥🪟 Inside is worse than outside at S ROOM.
> Something in the house is making smoke or fine dust: cooking, incense, a candle, a mosquito coil.
> **👉 Open a window or two and let it through. It clears faster than a purifier can catch it.**

That is an informed recommendation from an observation, written by whoever wrote the rule, shipped in
every language the node speaks, and on the wire today in `open_asks[].text`. **No model is involved**
— a node with no agent running shows the same words. The page was rendering `text.split("\n")[0]`,
the symptom, and throwing the recommendation away.

So the answer to all three of Tomas's options is one surface, and it is neither a blank box nor a
model:

1. **what was seen** — the observation, in the node's words
2. **what this node suggests** — the rule's own 👉 line, or, where a rule carries none, a sentence
   saying so. *This page does not invent advice about somebody's air.*
3. **a box** — take its word, which fills the box with the node's sentence, or write your own

Recording it writes `decided`, and §6 governs what that does: nothing. Doing it is a separate press,
under Act, and that writes `acted`.

**One card per issue, not per ask.** Four open asks about the same air are one decision, and a
household asked to decide four times about one room stops deciding.

## 9 · Two measurements, and only one of them exists

*From Tomas: "that action can be measured in two ways: when it happens, and how long it takes for the
action to take an effect in the observed indicator."*

The first exists. `actions.ts` is when somebody acted, and `_funnel` already reports medians from ask
to acknowledged to acted.

**The second does not, and cannot be got from the mechanism in §2.** The derivation proves the
condition stopped being true *somewhere inside* `MEASURED_WINDOW_MIN`, never when — which is why
`latency_minutes.measured` is `null` on purpose and why the comment there calls a median of
window-ends "a near-constant 48h dressed up as a measurement". Rule silence has no moment in it.

Getting Tomas's second number means leaving the rule and reading the readings: from the act's
timestamp, the first hour in `readings_1h` where the issue's own metric is back under its line. That
is a real query against data the node already keeps, and it answers a different and better question —
*how long did it take to work* — with an honest failure mode, because a condition that never comes
back under the line has no such hour and the answer is "not yet" rather than a number.

Two things it must not do. It must not be called ρ or fold into the funnel, which count whether. And
it must not be reported where the act and the effect have no causal link the household would
recognise: a window opened at 21:00 and air that cleared at 03:00 may be the window or may be the
night, and the node cannot tell. The number is *elapsed time to the indicator recovering*, stated as
that and not as an effect of the action.

## 10 · A private node and a community node are not the same node

*From Tomas: "an observation can be turned into an action. That action can come from a previous
decision or not in a private node, but in a community node it needs a previous decision, with
consensus mechanisms to be decided by each community. I guess there are features that belong to the
upper stream, rather than to a node that runs in a lab, a home or an office."*

This settles §7's shape and narrows what this node ever has to do:

- **On a private node** — a home, a lab, an office — an act needs no decision before it. Somebody saw
  something and did something, and the ledger records it. That is every node shipping today, and
  nothing above changes it: the decision is *offered*, never required.
- **On a community node**, an act that speaks for more than one household needs a decision before it,
  and what makes that decision legitimate is a consensus mechanism **each community chooses for
  itself**. A node in a house has no business holding one.

So the consensus machinery is **upstream, not here**, and this spec claims no part of it. What this
node owes the scale above is only that its own record is legible there: a decision that carries its
scale, its author, its time, and the observation it was about. One household's decision about its
street is a *contribution* to a community decision and never the decision itself — which is the same
refusal as `custody` and as "no scale is skipped: a city aggregator is built from nodes, not declared
from above".

The one thing that would be wrong to build here is a node that decides for a street because one
person pressed a button in one kitchen.

### Must an act wait for a decision?

*Asked by Tomas, 22 September: "what if we need a decision to register an action… an action does not
start running until a decision has been made."*

Evaluated, and the answer is **not by default, and a switch for the nodes that want it.**

The reason is that five things write an act and four of them have no screen to decide on:
the bridge's `on_message` (fabcity/planetai-reticulum) (a LoRa reply, from a device with no display, in a place with no
network), `app/agent.py:197` (the MCP `act` tool, and so Telegram), `bin/planetai:769` (the
terminal), the dashboard, and anything posting to the route — a phone, Home Assistant. The radio
settles it: that path exists for exactly the places a decision card cannot reach.

And node #1's own history says what refusing would cost: of 31 acts, **none** came from a surface
that could have shown a decision first.

Three things a hard requirement would do:

- **Record a fiction.** Somebody smells smoke and opens a window; there was no deliberation. A node
  that demands a decision row first is asserting one that did not happen.
- **Get worked around, and then lie.** The refusal is one `curl` away for anyone who knows and, for
  everyone else, the act goes unrecorded. ρ falls toward zero and the funnel reports a household that
  stopped answering, when what stopped was form-filling.
- **Apply a community's rule to every home node** — the thing this section exists to refuse.

So, three parts instead:

1. **The link.** An act names the decision it came from: the latest `decided` on the same ask,
   recorded before it. A convention, not a foreign key — `asks.actions` already carries `alert_id`,
   `stage` and `ts`, so it needs nothing added to the schema, the endpoint or the wire.
2. **The measure.** *"N of M acts had a decision recorded first."* On a node in a house that is
   honestly low and is not a failing; on a node acting for a street it should be all of them, and
   when it is not, the number says so. A refusal is one `curl` away and a number is not. It is the
   same shape as ρ, which never forces anybody to answer an alert and only counts whether they did.
3. **`DECISION_REQUIRED`**, default `0`, under Set up → Node. Set to 1, `POST /actions` answers **409**
   to an act with no prior decision on that ask, whichever way it came in. That is the gate Tomas
   described, owned by the community that turns it on rather than by the software — which is what
   this section says consensus mechanisms should be.

The measure comes first in usefulness: it makes the practice visible on every node, including the
ones that will never turn the gate on, and it says whether a gate is needed before anybody commits
to one.

## 11 · Learning over time

*From Tomas: "I also want the nodes to learn as we evolve on time, generate more intelligent
insights, have weekly, monthly, yearly patterns."*

Named as a direction, not specified. Two notes so it is not built badly later:

- **The node already has the material and almost none of the reading.** `readings_1h` holds every
  hour, `reach` says how far back the record goes, and Historical draws it. What is missing is any
  statement of the form "this room is worse on Tuesdays" or "this is the third week running".
- **A pattern is an insight and §4 already governs it.** It carries a claim, a grain, a window, and
  what it is measured against — and a weekly or yearly pattern makes the *window* the interesting
  part rather than an afterthought. A node with three weeks of history cannot have a yearly pattern
  and must say so rather than drawing one from three points, which is the failure mode this whole
  page exists to refuse.

The honest sequence is: the decisions and their effects first, then the patterns — because a node
that knows what was decided and whether it worked has something to learn *from*, and one that only
knows its readings can only ever learn what the weather did.

### What a node actually has, measured

Node #1 on 23 September 2026, from `/reach`, and the split is the whole design:

| kind | oldest | days |
|---|---|---|
| **its own sensors** | 2 Sep 2026 | **21** |
| model | Jul 2025 | 449 |
| map (AlphaEarth) | Jul 2016 | 3,720 |

A weekly pattern is available now; a monthly one in about two months; a yearly one from this house's
own measurements in about eleven. The model and the map reach back years — but **a yearly claim drawn
from a model is a claim about a model**, and saying otherwise would be the largest provenance
failure this page could make.

**Nothing prunes.** There is no retention policy anywhere in the node, so the record only grows:
293,371 readings and 64 MB for 21 days is about 1.1 GB and ~5M rows a year, on an SD card in a Pi.
That is the right default — a node that forgets cannot learn — and it has a consequence.

**`readings_1h` is a plain `VIEW`** that re-aggregates the whole `readings` table on every touch.
Its own comment in `init.sql` already says *"A plain view is fine until this node holds millions of
rows; then materialize it."* Counting its buckets on node #1 takes 63 ms today over 44,738 of them.
**It stops being fine at roughly the moment the yearly patterns it exists for become possible**, so
materialising it is not an optimisation to do later — it is the prerequisite for the last window.

### The first window, built

`GET /shape` and the section on Historical: the day this place usually has, one hour-of-day mean per
hour over the whole record, **indoor drawn apart from outdoor**. Two things settled by building it:

- **The hours are local, and that is load-bearing.** `extract(hour FROM bucket)` answers in the
  session timezone; Postgres defaults to UTC and `db()` sets it from `NODE_TZ` on every connection,
  with a comment recording that day boundaries and "evening" landed eight hours out in Bali once
  already. Read outside that connection, node #1's midday cooking peak reads as a four-in-the-morning
  one — which is exactly the mistake this document's author made before checking.
- **Inside and outside are anti-phased on node #1**, and one average over both would have hidden it:
  inside peaks at 12:00 (16.1 µg/m³ against 7.7 outside), outside peaks at 18:00 (14.3 against 9.4
  inside). Cooking, then the evening. That difference is the only thing in the drawing a household
  can act on, and it is the shape of every later window too: **a pattern is worth drawing when it
  separates two things that were being averaged together.**

`windows` on that route — which of day, week, month, year the record supports — is decided by the
node and obeyed by the page. A page that worked it out for itself would be the one place tempted to
round up.

## 12 · Options of actions

The agent has the readings, the alerts, the issues and a model, and could offer two or three things a
household might do. It must not be load-bearing:

- the agent container is optional, and a node without one has to be able to decide;
- alerts deliberately do not pass through the model — *"the node sends them; the model answers
  questions about them"* (`app/agent_loop.py`);
- a proposal is a suggestion with a name on it, and the name is the model's, not the node's.

So: the form works with nothing proposed. Where an agent is running it may offer options, each one
pre-filling the same two sentences, each one editable, and each one marked as the model's suggestion
and not the node's finding. A decision recorded from a proposal records which rung answered — the
agent already stamps `X-Agent=<name>/<rung>` on every write.

## 13 · By whom

`actions.actor` is eighty characters of free text. Today the honest answer to "who decided" is
"whoever typed their name", and there is no identity behind it. That question belongs to
`docs/SPEC_identity.md` and should not be answered twice. What this spec adds is only that the field
must be *asked for* and not defaulted: an unattributed decision in a house with four people in it is
a record nobody can check.

## 14 · What it refuses

- No decision without something to watch, or it is a diary entry the funnel cannot count — and the
  page must say which of the two it is taking.
- No keeper SQL. A watch is five values and a template.
- No deletion of a watch. Retirement only.
- No watch finer than the grain the node has already proved is flat.
- No proposal presented as a finding.
- Nothing here writes a `measured` row. The derivation stays the only way that stage is reached.
- **A decision never counts as an act.** Not in the funnel, not in ρ, not in a cell, not in a count.
- **A decision that was never acted on is never hidden.** It shows, with its date, beside the ask it
  was about.
- No decision speaks for more people than the one who made it, whatever scale it names.

## 15 · Still open

- **What happens to a decision whose watch never fires.** If the condition is not true when you
  decide, there is no alert to act on and nothing to measure. Probably correct — you decide about
  what is happening — but it means the form has to refuse gracefully, and the words for that refusal
  are not written.
- **A decision about something the node cannot see.** "We moved the burning to the far field" is
  real, useful, and has no metric. §8 forbids counting it; it does not say whether to record it.
- **What a decision at a scale bigger than this house means before consensus exists.** §7 says it is
  recorded as one household's and that is all. Whether the page should say so every time, or only
  where a neighbour is visible to disagree, is not settled.
- **Whether an insight can be wrong.** The three kinds in §4 are arithmetic, not judgement. A sensor
  in the sun reads high and the arithmetic will call it an insight.

---

*Grounded in `init.sql` (`alerts`, `actions`), `app/main.py::run_rules` and `POST /actions`,
`app/index.py::_funnel`, `_live_rule_ids` and `run_ro`, `app/packs.py::load_rules`,
`docker-compose.yml`'s read-only `config` mount, `config/rules.yml`'s own format, and
`app/agent_loop.py`.*
