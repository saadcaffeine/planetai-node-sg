# The report
<!-- checked: v0.80.10 -->

The report is the node telling the household what the ground is doing, in their language, on a schedule. The
repo's own sentence for a node ends there: "It tells the people there in plain sentences, on Telegram, and passes
upward what the models of a bioregion and a planet cannot see from above: what the ground is doing." The node
writes it itself, from SQL against its own tables, so a node with no model reachable anywhere still gets it. With
the `make` pack on, it can also end on a place: the nearest workshop that can make or fix something, the first
thread from a reading to somewhere nearby where a person can do something about it.

`app/report.py` holds both halves: `bundle()`, every number the node has about the window, and `sheet()`, the
report.

## When

`REPORT_EVERY` takes 3, 4, 6, 8, 12 or 24: each divides 24, so the rhythm does not walk round the clock, and
anything else falls back to 6. `REPORT_ANCHOR` is the local hour it counts from (0–23). The defaults are 6 and
6: 06:00, 12:00, 18:00 and 00:00 where the node is. `planetai report every 12` and `planetai report at 7`
change it without a restart; so does the dashboard's Set up view.

The rules loop checks once a minute. In the first twenty minutes of a due hour it writes the report, and the
`reports` row for that local hour is the lock: a container that restarts inside the window does not send
twice. A report due inside quiet hours is written and stored with `held_quiet` and not sent; the next report to go out folds every held hour in and opens with "Overnight and
this morning." A node that was off for a week reports two days (the cap is 48 hours), not a hundred and
sixty-eight.

## Read one now

1. **Run `planetai report`.** The node writes a report at once and sends it. The terminal prints the text,
   then `  written by node, sent.`, and Telegram, when it is connected, receives the same text after `ℹ️`.
   `written by node` means the node wrote every sentence itself, from its own tables, with no model. With no
   admin token in `.env` it stops at `no ADMIN_TOKEN in .env; run planetai ui`.
2. **Run `planetai report last`.** It prints the last report's text and one line under it,
   `<date> <time> · <hours> hours · written by node`, with `· HELD for quiet hours, folded into the next
   one` added when quiet hours kept it back. Before any report it prints `no report yet; the first one lands
   at the next due hour`. The report you just asked for is the last one, and the scheduled ones still come
   at their hours.

## The six parts

Deterministic, plain text, in `ALERT_LOCALE` (English, Bahasa Indonesia or Spanish), each part a sentence or
two, an empty part left out:

1. **Where the place stands.** Heat first if an open act-level alert comes from the `heat` pack: "dangerously hot"
   only when it is `heat_danger` (feels like 40 °C or more), otherwise "It is hot inside: it feels like 35 °C or more." (35 °C is an
   ordinary afternoon in Kuta Selatan, not a danger); else the worst
   indoor PM2.5 against 35 (unhealthy) and 15 (the clean line); or that there is no sensor inside yet, so what
   follows is the district and not the rooms.
2. **What changed.** Up to two of the node's own sensors whose window was unusual: "{place}: the air ran
   higher than usual".
3. **What only the models know.** One clause if its rule is loaded and crossed: a heavy swell, or the satellite
   model reading the district over 35.
4. **What happened after this window's act alerts.** For each rule with a threshold: "{place} is back under {n}"
   or "is still above {n}", at most two. Then, when the node knows one, **the nearest place to make or fix
   something** (below).
5. **The one thing to do before the next report.** A room still over the line; a sensor gone quiet; the first
   failing health check's own fix; or "👉 Nothing needs doing before the next report."
6. **The invitation.** "Ask me anything about the air, the heat, the sea or what is around here."

Parts 2 and 3 share a paragraph; 4 and 5 share another. The sheet is written to stay under a hundred words; the
make line, when it is there, adds to that.

## The nearest place to make or fix

When the bundle holds a `facility` row, the fourth paragraph gains one line after the outcomes and before the
to-do, so a person reads what happened first and only then where somebody could act on it. Its shape is:

```
Nearest place to make or fix something: {lab}, {distance} km ({up to three capabilities}).
```

The distance reads `<0.1` for a node inside a lab, and the capabilities are in the report's language. The row
comes from the `make` pack, which is off unless both `MAKE_ENABLED=1` and `PACKS_ALLOW_CODE=1` are set, and
which stores only the labs within `MAKE_RADIUS_KM` (50) that publish coordinates. The same line is offered on the
alerts in `GET /issues`, as `asks.where`. From v0.65 to v0.69 the line was silently absent on every node, because
the report looked for the pack in the wrong folder; it appears from v0.70.

> **Careful.** The pack's README states the licence this way: the Fab Lab Network directory "is **not openly
> licensed**. Each lab retains copyright in its own record (fablabs.io Terms of Use §8.1) and no data licence is
> published". Fab City Foundation decided on 2026-09-20 that PLANETAI may read it and accepted responsibility,
> pending a Terms of Use clause, and "**That decision covers the Foundation, not each node's operator**". Read
> [packs/make/README.md](../../packs/make/README.md) before turning it on; if that matters to you, leave it off.

## Two numbers behind it

**Notability** is the window's mean for a sensor and metric against the mean of the same local hours on
each of the previous seven days, in standard deviations of that baseline. It is null until three days
exist, so a node in its first three days claims nothing. It decides which two places get a sentence in part 2,
which is how the report can say "Kitchen: the air ran higher than usual" without anyone reading a chart.

**Trend** is the `insight` digest's ±3 rule read across to each metric's own units (3 µg/m³ for PM2.5, half a
degree for a room's temperature, 5% of the window's range for a metric with no line of its own), comparing the
second half of the window with the first.

## The bundle

Everything the sheet was written from, as one JSON document, SQL only, most of it run as the read-only role: `meta`
(node, locale, local time, window, held hours), `series` per sensor and metric (min, max, mean, n, trend,
notability, the usual value and how many baseline days), `observations` (sea, weather, satellite air, place,
land, with yesterday's value), `now` (the `stats` view), `alerts` in the window, `open_act` (unanswered act
alerts in 24 hours, at most five), `sensors_quiet`, `rho` now and a week ago, `previous` (the last sent
report), `cells` with what changed, `rules`, `health`, `facility` (the nearest lab, or null), and the first
row of every pack's `contributes: report` rule under its own id. A contributor may not use one of the names the
bundle owns (`RESERVED` in `app/report.py`); one that tries is skipped and logged. The bundle is trimmed to
64 kB by dropping the least notable series first.

`GET /report/bundle?hours=` returns it behind the read-only or admin token; the MCP tool `report_bundle`
reads it too. Numbers in any sentence about the node must come from here.

The bundle carries ρ now and a week ago, and no sentence of the report says it. A ρ sentence is proposed in
`docs/SPEC_rho.md`, whose status line reads "Phase 1. Nothing here is built."

## A model in the path

The schema is ready for one and this version ships without it. Every report row carries `sheet` (always the
node's own text) and `text` (equal to `sheet` until a model rewrites it), `depth` (`sheet` today; `brief`,
`standard`, `deep` reserved), `rung` (`node` today; `local`, `remote`, `online` reserved) and
`fallback_reason`, for the day a model's text is refused because it invented a number, timed out, or there was
no agent. `REPORT_DEPTH` takes `auto`, `brief`, `standard` or `deep`, and changes nothing yet. The rule when a
model comes: it is handed the bundle and the sheet, and anything it writes is checked against the numbers in
them before it is allowed out. The sheet is what the node falls back to.

## Delivery and endpoints

The report goes to Telegram, prefixed `ℹ️` like any info message, and to Home Assistant's *latest alert*
entity. The mesh and Reticulum do not carry it.

| | |
|---|---|
| `GET /report/latest` | the last report, always with the same keys: `schema` (`report-v0`), `id, ts, due_local, window_hours, depth, rung, text, sent, held_quiet, fallback_reason`, and `note`, which is null when a report exists and "no report yet; the first one lands at the next due hour" when none does. Open at `SHARE_LEVEL=open` |
| `GET /report/bundle?hours=` | what it was written from; read-only or admin token |
| `POST /report/now` | write one now and send it; admin token. Written without a `due_local`, so the scheduled one still happens |
| `planetai report` · `report last` · `report every N` · `report at H` · `report level act`, `warn` or `info` | the same from the command line; `level` sets `ALERT_LEVEL`, what may interrupt between reports |
| `report_latest` · `report_now` · `report_bundle` | the same over MCP |

## The digest on the page

A second summary lives in `GET /issues`, not in the report: `digest`, four sentences, one per stage (observe,
decide, act, measure), in English, Bahasa Indonesia and Spanish. Since v0.74 it also carries `simple`, the
paragraph simple mode draws on Now (the house's own stations and the nearest others, the oldest open alert,
how the last 30 days of asking went), and `prompts`, the ask pane's questions, the first three of which it opens with. Every figure in the four is one the page already draws further down, and the node writes them, not
the browser. The open alerts they count are the issues' open asks, so on a node whose alert engine is `shadow` or `events` they leave out the heat and air alerts, which an
event stands for. The measure sentence has the form "Of the {acts} alerts here that asked for something, {answered}
have been answered, and the usual wait was {median} minutes."

That sentence does not say ρ. ρ has its own window and its own query in `app/index.py`, which the
issues engine cannot make, and, in the code's words, "A second rho computed from a different window would be a
second rho, and two of them disagreeing on one page is worse than one of them being absent." The measure
sentence counts the Act stage's ledger instead: an alert counts as answered once it has an `acted` or `measured`
row.

## Contributing to it from a pack

A rule with `contributes: report` and no message is never sent; its first row lands in the bundle under the
rule's id, where the sheet may read it and a model may quote from it. Four ship:

| contributor | what it puts in the bundle |
|---|---|
| `insight/digest` | inside, outside, modelled, the day's mean and peak, the trend |
| `nearby/alone` | a ring of fewer than two stations, or none within 10 km |
| `forecast/ahead` | wind and rain for the next day |
| `season/record` | this week's PM2.5 around the node against the usual: each Bali Air Dispatch station's last 7 days against its own preceding 60, the median of the differences, and the station count, whether or not it crossed a line |

See [Packs](packs.md).

## Where this leads

The report says what the ground did. Between reports the node speaks only when a reading crosses a line:
[alerts](alerts.md) is how it asks, and [channels](channels.md) is where the asking reaches people.
