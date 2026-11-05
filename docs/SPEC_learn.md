# SPEC: what the node learns

*Asked, 13–14 October 2026, by Tomas: "I want the node to learn from its data, how can we design something like a RAG
or daily/weekly/monthly/yearly learnings from the node?" Before building it he asked for the research on decisions
made by households, local businesses and organised communities, starting from MIT Space Enabled's EVDT framework.
Then: "yes, you can add a research note, and build the spec, lets go."*

**Status: steps 1–4 built in v0.82 (#230–#233); 5 waits on the community tier, 6 from Sep 2027. Proposed 14 October 2026.** Each step in §9 is its own pull request, run on node #1
before it merges. The research behind it is in the note linked in §10.

## 1 · What it serves

A household, a shop or a lab acts on what its node tells it, and the node already writes the act down. What nobody
knows, here or in the literature, is whether the act worked. Studies of feedback measure whether people *understood*
or *changed* on average; decision-support research measures whether officials found a tool useful. None we found
logs an alert, the action taken and the effect a sensor measured, home by home. So the first thing the node learns is
the household's own evidence:

> When you closed the windows during evening burning, indoor PM2.5 fell by half within two hours, 6 times out of 8.
> When the same alert went unanswered, it fell by a tenth.

Everything else (the usual shape of a day, a season, a year) is in service of that: it says what is ordinary, so the
node can tell what an action changed.

## 2 · Rules every learning keeps

1. **Code proves, a model only words.** A learning is a row the node computed: a statement, the numbers, how many
   cases, the query that made it. A model may rephrase a row; it may never add a number or a cause. This is the
   report's rule already ("never write a number that is not in it").
2. **Every learning shows its proof.** The page draws its cases; the bot can say how many and since when. A learning
   the household cannot inspect is one it will stop trusting (the learning thermostat's lesson).
3. **Few cases say so.** Under five, a learning is "too few to be sure", with its count, never a percentage.
4. **A learning is never deleted.** It is checked again at each period and marked `holding`, `weakening` or `gone`.
   "The Saturday smoke stopped in November" is a learning too.
5. **Describe and explain before predicting.** EVDT planned describe, explain, predict and reached the first two;
   this node does the same. Nothing here forecasts.
6. **The house's learnings stay home** (§7).

## 3 · What exists

- **The actions ledger.** Node #1, on 14 October: 55 `acted` rows since 2 September, 40 of them on an alert raised for
  one sensor (20 air, 15 heat), 15 answers to event buttons, and 13 `decided`. Each has the household's own words.
- **`measured`, derived:** an act followed by 48 hours in which the same rule does not fire again on the same sensor
  (`app/index.py::_funnel`). It says *whether* a condition ended, not by how much, and not because of the act.
- **The usual:** `usual_by_hour`, a materialized view of each hour's usual temperature, humidity, PM2.5 and
  apparent temperature over the last 14 days, which the rules read; the report compares against the same hours of
  the previous seven days.
- **The report chain:** every report reads the one before it (`reports`, 106 rows since 7 September on node #1).
- **The `private` role** (#224), and `/species` and `/things`, which already keep what is the house's at home.

## 4 · Learning one: what worked

For each `acted` row whose alert names a sensor and a metric, the node takes:

- **before**, the metric's mean in the hour before the act;
- **after**, its mean in a window after it: one to two hours for air, three to six for heat (the issue says which);
- **the outside**, the same two windows on the nearest outdoor sensor, so a change the whole street saw is not
  credited to the house (a difference of differences);
- **the unanswered**, alerts of the same rule nobody acted on, measured the same way from the alert's time.

Grouped by rule, a learning reads: acted N times, the median change inside against the median change outside, and
against the unanswered alerts' change. The household's notes for those cases are listed under it, so "closed the
windows" and "turned on the purifier" can be told apart by the person, not guessed by a model. Splitting a rule's
cases by what was done is a household's choice of words, offered as a filter, not a classifier.

What it does not claim: a cause. It is the household's own before and after, with the street and the unanswered
alerts beside it. That is more than any study we found records, and it says so in those words.

**The verdict** *(14 October 2026, design review of node #1)*. `holding` says the learning holds, not that acting
helps: node #1's air row read holding while acting had left the air worse than leaving it (+2.5 µg/m³ acted, −0.8
unanswered). So every `worked` row carries `numbers.verdict`, computed from its own medians: each group's change
inside net of the street's, acted against unanswered (no unanswered yet counts as no change). Acted lower than
unanswered by more than the metric's noise (3 µg/m³ for PM2.5, half a degree for heat, the report's trend step) is
`helps`; higher by as much is `worse`; between them `no_clear_difference`; under five acted cases `too_early`, and a rule that can no longer fire `gone`. `helps` also needs the house's own net change to be a fall. The statement
leads with it in plain words and the alert's household name, then keeps every number it came from: "After an air
alert, 9 times so far: acting on it seemed to make it worse than leaving it. Acted on 5 times: PM2.5 inside changed
+2.5 µg/m³ in the 1–2 h after, …". `GET /learned` serves `name` (`learn.alert_name`) and `verdict` (its words) beside
each row, so a page can show them as columns and the bot's `/learned` prints them first.

## 5 · Learning two: what is usual here

Daily, from `readings_1h`, per issue the household watches:

- the shape of an ordinary day (by hour), of a week (weekday against weekend), and of a month;
- what changed: this week against the usual, beyond its spread;
- a slow trend, once a series is long enough to have one (Theil–Sen, as EVDT used for night lights);
- the same date last year, once there is a last year (node #1's own sensors: from September 2027; its satellite
  series: now).

Each is a row in a `learnings` table: `kind`, `issue`, `statement` (a template with the numbers in it), `numbers`
(JSON), `n`, `since`, `status`, `first_seen`, `checked_at`, `scope` (`house` or `place`). Re-checked daily; a weekly
and a monthly pass do the slower kinds.

**Asks that do not fit.** Alerts dismissed with Doesn't fit, or left unanswered, are a learning about the alert
itself: "the night heat alert was dismissed 5 of 7 times". The node offers a card (quieter at night, a different
line); it never changes a rule by itself. This is the second loop: asking whether the alert, not the house, is wrong.

## 6 · Learning three: the digests, and asking them

In the first hour of each local day the node writes a **digest** per day, before the morning report; each Monday per week, on the 1st per month, on 1 January per
year. A digest is made from that period's learnings, its figures, its actions, and the previous digest at the same
scale, so the chain of reports becomes a memory at four scales. It is written by the node's template first; a model
may reword it under §2.1, as the report is.

Retrieval is the only part that is RAG. The ask pane and the bot get a `learned` tool that searches digests, learnings
and the household's action notes, by period and issue, with Postgres full-text search: "was this October smokier than
last?", "what did we do the last time the purifier filter ran out?". Embeddings from a model in the node's own Ollama
come only if words prove too weak. Telegram gets `/learned`, a template over the rows with no model, as `/stack` is. The first report each day carries the morning memory on Telegram (built 14 Oct 2026, on by default: `LEARN_PUSH`).

## 7 · What stays home

- `learnings` and `digests` are tables like `things`: revoked from pack SQL, in no export, push or report bundle.
- A learning with `scope = house` (anything built on the house's sensors, actions or notes) is read by the
  `learned` tool only while `AGENT_PREFER` is `private`, so it reaches a model on this house's own machines and no
  other. Otherwise the tool answers place learnings only, and says why.
- A learning with `scope = place` (the street's smoke on Saturday evenings, built on outdoor and public data only)
  is what a community node would want. It leaves only when the household offers it, with the community tier.

## 8 · Who is in the house

The commonest reason people ignore an alert is not feeling at risk. A short, private household profile (an older
person, a child under five, someone with asthma, a pregnancy, someone working outdoors) lets the node rank its
learnings and say "you said a child lives here". It is EVDT's *vulnerability*, filled in by the household instead
of estimated from a census. It changes no threshold by itself. *Amended 14 October 2026 (Tomas: "yes, add it to the alerts"):* an act-level heat
or air alert that weighs on someone listed carries one line saying so in its Telegram message, and only there.

## 9 · Steps

1. **What worked.** *Built 14 October 2026.* The `learnings` table, the daily job for §4 on air and heat, a Data door section "What worked
   here" with its cases, and `/learned`. Node #1 starts with 40 acted alerts.
2. **What is usual.** *Built 14 October 2026:* the day's shape, weekdays against weekends, the week against the three
   before and a trend from 60 days, and the asks that do not fit. The month's shape waits for months of data.
3. **Digests and asking them.** *Built 14 October 2026, written by the node's template only.* The `digests` table, the four scales, the `learned` tool for the pane and the bot.
4. **Who is in the house.** *Built 14 October 2026.* §8's profile, five yes-or-no answers that rank the learnings.
5. **Homes like yours.** Comparison with other homes, the strongest effect in the feedback studies, made from
   anonymous sums through the community tier. Waits for the upstream tiers.
6. **A year.** Same-date comparisons, as each node reaches its first year.

## 10 · Open

- The after-windows per issue, and whether they belong in the issue files.
- Whether five cases is the right floor, and how to show a spread on five.
- How an action note is grouped: by the household's own label, chosen once, or by the words as written.
- Whether a place learning goes upstream as a sentence, as numbers, or both.
- Research note, positioning this against EVDT and the household and community literature: [PLANETAI and the decision below policy](https://claude.ai/artifact/RvpHqtqGNigpbEDVuRExsk) (14 October 2026; private until shared).
