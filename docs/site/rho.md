# ρ: the loop closed
<!-- checked: v0.91.0 -->

ρ (rho) is the share of the node's act-level asks (alerts and events it sent, and its children's alerts) that a
person answered within 24 hours. It is the node's
`Governance` cell in the Fab City Index, counted from the answers people give, each one a row in the `actions` table.

Once the node has asked ([alerts](alerts.md)) and heard back ([channels](channels.md)), ρ and the numbers beside
it say how often asking worked, how long the answer took, and whether the condition stopped afterwards.

## The definition

Over the last 30 days:

```
ρ = act-level asks whose first acknowledged-or-acted answer came within 24 hours
    ────────────────────────────────────────────────────────────────────────────
                            act-level asks that were sent
```

with `median_minutes`, the median time from the ask to that first answer, among the ones answered within 24
hours. `index.rho()` computes both. An ask is one of three things:

| ask | counted from | answered by |
|---|---|---|
| an act-level `alerts` row | its `ts` | an `acknowledged` or `acted` row in `actions` with its `alert_id` |
| an act-level event the event engine sent | its first sent `open` or `escalate` message | an `acknowledged` or `acted` row with its `event_id` (Done or Not now, on Telegram or the dashboard) |
| a child's act-level alert, pushed up to this node | its `raised_at` | the earlier of its `responded_at` and `acted_at` |

Only what was sent is asked. On `ALERT_ENGINE=events` the event engine speaks for the heat and air-quality packs,
and from its first sent message on, their `alerts` rows are written and never sent, so ρ leaves them out and counts
the event once instead. Packs the engine does not replace still send through rules and count as alerts. On a
`rules` or `shadow` node every act-level alert counts. A node with no children has an empty `events` table, so the
third row adds nothing.

![ρ: of the act-level asks sent, the share that got an answer within 24 hours](img/rho.svg "The first acknowledged or acted answer stops the clock. The figures are an example.")

> **Gap in v0.91.0.** A child pushes every `alerts` row to its parent, the unsent ones included, and none of its
> events. A parent's pooled ρ therefore counts a child on `ALERT_ENGINE=events` the old way.

`GET /rho` on node #1, an events node:

```json
{"window_days": 30, "days_ago": 0, "alerts_act": 157, "acted": 13, "rho": 0.083, "median_minutes": 73,
 "funnel": {"stages": {"asked": 157, "acknowledged": 2, "acted": 13, "measured": 6},
            "latency_minutes": {"acknowledged": null, "acted": 438, "measured": null},
            "measured_derived": true, "measured_window_minutes": 2880, "self_only": true}}
```

Of 157 asks in 30 days, 13 were answered within 24 hours, and among those 13 the median answer came 73 minutes
after the ask. `rho` and `median_minutes` are `null` when there is nothing to divide. `days_ago` moves the whole
window back; the report's bundle uses 7 to carry what ρ was a week ago.

`planetai status` and `planetai act` print ρ, and the `status` MCP tool carries it. The dashboard's *Whether it
worked* section draws it as "{closed} of {total} alerts answered · median {n} min", and the classic wall as its
row of rings. The doors' Wall does not show it.

## Read it on your node

1. **Run `planetai status`.** Its `rho` line reads, for example, `rho       0.083  (13/157 act-level alerts
   answered, 30d)`. Before the first act-level ask it reads `rho       not yet measured  (0/0 act-level alerts
   answered, 30d)`.
2. **Ask the node for the whole record.** `curl http://<node>:8080/rho` (at `SHARE_LEVEL=open`, or with
   `-H "Authorization: Bearer <token>"` and any of the node's tokens) returns the document above. `alerts_act`
   and `acted` are the two counts the `status` line divides.
3. **Close one loop and look again.** `planetai act <id> "<what you did>"` ends with `rho is now <ρ>
   (<acted>/<alerts_act> alerts answered, median <n> min)`. If the alert was raised less than 24 hours ago and
   nobody had answered it yet, `acted` has gone up by one, and so has the node's `Governance` cell.

## Stages

`actions.stage` is one of six:

| stage | meaning | written by | in ρ |
|---|---|---|---|
| `acknowledged` | somebody saw it | `POST /actions`, the bot's Not now | yes |
| `decided` | somebody said what would be done | the dashboard's Decide form, `POST /actions` | no |
| `acted` | somebody did the thing | the dashboard's *I did this* and Done, `planetai act`, `/act` on Telegram, `act <id>` over LXMF, the MCP `act` tool, `POST /actions` | yes |
| `measured` | the condition stopped | derived in the funnel (below); `POST /actions` refuses it | no |
| `settings` | a setting was changed, with no alert | the node, on `PUT /settings` | no |
| `dismissed` | *Doesn't fit*, said of an event's advice | `POST /actions` with an `event_id` | no |

An event's three answers (`acted`, `acknowledged`, `dismissed`) carry an `event_id` and no `alert_id`. ρ and the
funnel count them; `GET /effect` joins `actions` to `alerts` on `alert_id`, so no event's answer is in it. See
[Alerts](alerts.md#the-event-engine).

For ρ, `acknowledged` and `acted` both count as an answer. On the dashboard only `acted` and `measured` close an
alert. There is no cap of one action per alert; the clock stops at the first answer.

A `decided` row counts in neither ρ nor the funnel. The Act stage's ledger (*What was decided, and by whom*) marks
an act that had a decision recorded against the same alert beforehand as *decided first*. `DECISION_REQUIRED` is
under [Answering an alert](alerts.md#answering-an-alert).

## The funnel

`GET /rho` carries `funnel`: this node's own asks of the same 30 days, counted at four stages (asked,
acknowledged, acted, measured), with the median minutes between consecutive stages. Its `acted` is the literal
stage, so it will not match ρ's `acted`, which also counts an acknowledgement. It leaves out the children, whose
`events` rows carry no stages (`self_only: true`), and it leaves out the unsent rows the same way ρ does.

`measured` is derived from silence: an alert with an `acted` row, whose rule the node still evaluates, and which
that rule did not raise again on the same sensor for `MEASURED_WINDOW_MIN` (2880 minutes, 48 hours) after the act.
The window is longer than every act-level rule's cooldown, so silence across it means the condition stopped being
true. That says whether, never when, so `latency_minutes.measured` is always `null`. A retired rule is left out,
because a rule that can never fire again is silent whatever happened. An event has no derived `measured`; only a
posted row would count for it.

## What worked, per rule

`GET /effect` asks the same question per rule over the node's whole record (365 days by default): how many acts
there were (`acted`) and how many were followed by the condition stopping (`cleared`, derived as `measured` is). A
rule that declares `watch: {metric, over}` also gets `measured` (acts after which that sensor's hourly mean came
back under the line), `already` (acts made when it was already back), and the median `hours` to recovery. Four
rules declare one: `air-quality/indoor_pm25_high` (`pm25` over 35.5), `air-quality/outdoor_pm25_high` (`pm25` over
55.5), `heat/heat_stress_now` (`apparent`, the feels-like temperature, over 35) and `heat/heat_danger` (over 40).
Every other rule answers `hours: null`, because it fires on a relation such as inside worse than outside, where
there is no line to come back under. The dashboard draws it as *Which of these worked*.

It is elapsed time, not an effect. A window opened at 21:00 and air that cleared at 03:00 may be the window or
may be the night, and the node cannot tell.

## What ρ does not measure

ρ counts answers, it says nothing about the place. The funnel's `measured` and `GET /effect` are the node's evidence
about the place, and both say that a condition stopped, never that the act stopped it. A second number read from
the place's own recovery (ρ_observed, with a `recovery:` block in the rules) is proposed in `docs/SPEC_rho.md` and
not built: no rule carries a `recovery:` block, and `rho()` still counts `acknowledged` as an answer, which the
spec would change.

## Where it goes

- **The Index.** `GET /cells` adds `Governance|<Scale>` with ρ as its value once there has been any act-level ask
  in 30 days: `partial` until five have been answered, `live` from then.
- **A parent.** Every hour the node posts its alerts of the last 36 hours to the parent's `/events` as timestamps
  only (`raised_at`, `responded_at`, `acted_at`, `measured_at`, the rule, the level, the pack), never the text,
  the actor, the sensor or a ratio. `measured_at` is filled only from a posted `measured` row, so a parent
  receives `null` there. The parent computes ρ under its own definition.
- **The export.** The daily CC BY 4.0 export carries `rho` as `index.rho()` returns it when the export is written,
  the rolling 30-day figure.
- **The report.** The bundle carries ρ now and a week ago; no sentence of the report says it.

## Recording an action

From another machine `POST /actions` needs `ACT_TOKEN` or `ADMIN_TOKEN`; from loopback (the node's own MCP tools, a
shell in the container) it needs none. A browser is never loopback. The body is `{"alert_id": 12, "stage": "acted",
"actor": "made", "note": "closed the windows"}`, or `event_id` in place of `alert_id` for an event. `actor` is cut at
80 characters and `note` at 500, and an unknown alert or event is a 404. An alert a pack gave buttons takes a
`choice`, the button's value, in place of `stage`: the button sets the stage (`acted` or `acknowledged`), so its answer
counts in ρ like any other. A `choice` the alert did not offer is a 400, and an alert older than 72 hours a 409.

| way in | actor | when no note is given |
|---|---|---|
| the dashboard's *I did this* | the name typed in the form | the form will not post; it needs the act or admin token Set up holds |
| `planetai act <id> [note]` | `$(whoami)` | writes `acted` |
| Telegram `/act <id> <words>` | `<AGENT_NAME>/telegram` | writes nothing; the bot asks "What did you do about it?" |
| the MCP `act` tool | its `agent` argument | refuses, and refuses placeholders such as `acted`, `done` or `ok` |
| `act <id> [note]` over LXMF | `lxmf:<hash>` | writes `acted (via reticulum)` |

The note should be what the person said. The MCP tool and the Telegram bot will not write a row without one, the
terminal and the radio fill in a placeholder, and `POST /actions` takes any note. `GET /actions` lists every answer
with its stage, actor and note, and answers only a token or the machine itself. `planetai snapshot` leaves the
notes out of the file it writes.

The invariants ρ depends on are on the [federation](federation.md) page: peers never roll up and never drive an
alert, the note on an action and the chat ids never leave the node at any sharing level, state is never upgraded
by aggregation, and exactly one node per pilot writes to the Index's spine.

## Where this leads

The node now senses, asks, hears back and measures. Extend it with [packs](packs.md), which add rules, cells and
sources for a domain, and the [source registry](sources.md). [Sharing](sharing.md) and
[federation](federation.md) are how ρ travels up to a district, as timestamps and nothing else.
