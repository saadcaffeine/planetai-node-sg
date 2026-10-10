# ρ: the loop closed
<!-- checked: v0.80.10 -->

ρ (rho) is the share of the node's act-level alerts that a person answered within 24 hours. It is the one
number on the page that comes from a person, the Fab City Index's `Governance` cell at the node's scale, and
the reason the `actions` table is the Index's instrument rather than an app feature. The architecture says it
plainly: "**ρ is the brick nobody else has.** Two generations of the Index measured a snapshot with ρ implicit at
1. The node measures ρ for real, because it's the thing sending the alert and the thing receiving the
acknowledgement." This page is the Measure stage: once the node has asked (alerts) and heard back (channels), it
can say how often asking worked, how long it took, and whether the condition stopped afterwards.

## The definition in this version

Over the last 30 days:

```
ρ = act-level alerts whose first acknowledged-or-acted action came within 24 hours
    ─────────────────────────────────────────────────────────────────────────────
                          act-level alerts raised
```

together with `median_minutes`, the median time from the alert to that first action, among the ones that were
answered within 24 hours. Both are computed by `index.rho()` from `alerts` joined to `actions`, pooled with the
`events` rows the node's children pushed up (`level='act'`, their `responded_at` or `acted_at`, whichever is
earlier). A node with no children reads an empty `events` table. `days_ago` shifts the whole window back; the
report's bundle uses 7 to carry what ρ was a week ago.

`GET /rho` on node #1 as published on 19 September 2026, with the funnel's counts left out:

```json
{"window_days": 30, "days_ago": 0, "alerts_act": 137, "acted": 29, "rho": 0.212, "median_minutes": 112,
 "funnel": {"stages": {"asked": ..., "acknowledged": ..., "acted": ..., "measured": ...},
            "latency_minutes": {"acknowledged": ..., "acted": ..., "measured": null},
            "measured_derived": true, "measured_window_minutes": 2880, "self_only": true}}
```

Of 137 act-level alerts in 30 days, 29 were answered within 24 hours; among those 29 the median answer came
112 minutes after the alert.

`rho` and `median_minutes` are `null` when there is nothing to divide. `planetai status` and `planetai act` print
ρ; the `status` MCP tool carries it; the dashboard's *Whether it worked* section draws it as "{closed} of {total}
alerts answered · median {n} min".

## Read it on your node

1. **Run `planetai status`.** Its `rho` line reads, for example, `rho       0.212  (29/137 act-level alerts
   answered, 30d)`: 29 of the 137 alerts of the last 30 days had an answer within 24 hours. Before the
   first act-level alert it reads `rho       not yet measured  (0/0 act-level alerts answered, 30d)`,
   because there is nothing to divide.
2. **Ask the node for the whole record.** `curl http://<node>:8080/rho` (at `SHARE_LEVEL=open`, or with
   `-H "Authorization: Bearer <token>"` carrying any of the node's tokens) returns the document above:
   `window_days`, `days_ago`, `alerts_act`, `acted`, `rho`, `median_minutes` and `funnel`. `alerts_act` and
   `acted` are the two counts the `status` line divides.
3. **Close one loop and look again.** `planetai act <id> "<what you did>"` ends with `rho is now <ρ>
   (<acted>/<alerts_act> alerts answered, median <n> min)`. If the alert was raised less than 24 hours ago
   and nobody had answered it yet, `acted` has gone up by one. That act is now in the number the node
   reports as its `Governance` cell.

## Stages

`actions.stage` is one of six:

| stage | meaning | written by | in ρ |
|---|---|---|---|
| `acknowledged` | somebody saw it | `POST /actions` | yes |
| `decided` | somebody said what would be done | the dashboard's Decide form, `POST /actions` | no |
| `acted` | somebody did the thing | the dashboard's *I did this*, `planetai act`, `/act` on Telegram, `act <id>` over LXMF, the MCP `act` tool, `POST /actions` | yes |
| `measured` | the condition stopped | never posted; derived in the funnel (below). A posted row would count, and `POST /actions` refuses one | no |
| `settings` | a setting was changed; an audit row with no alert | the node, on `PUT /settings` | no |
| `dismissed` | *Doesn't fit*, said of an alert event's advice; an event's row has an `event_id` and no `alert_id` | `POST /actions` with an `event_id` | no |

An event's three answers (`acted`, `acknowledged`, `dismissed`) are written with an `event_id` and no `alert_id`, and
ρ, the funnel and `GET /effect` all join `actions` to `alerts` on `alert_id`, so no event's answer is in any of them
in this release. Under `ALERT_ENGINE=events` the old heat and air rules still record their act-level alerts, which
ρ still counts, though the engine and not those rules is what messages the household about them. How events count
is not decided yet (v0.80.7). See [Alerts](alerts.md#the-event-engine).

For ρ, `acknowledged` and `acted` both count as a response. For the dashboard's alerts, only `acted` and `measured`
close one: "`acknowledged` means somebody saw it. Only these two mean somebody did something." There is no cap of
one action per alert; the first response is what the clock measures.

**A decision moves nothing.** A `decided` row is not in ρ, not a stage of the funnel, and closes no alert. The Act
stage's ledger (*What was decided, and by whom*) marks an act that had a decision recorded against the same alert
beforehand as *decided first*, and counts how many did. With `DECISION_REQUIRED=1` (Set up → Alerts, off by
default), `POST /actions` refuses an `acted` with a 409 unless a `decided` row exists for the same alert.

## The funnel

`GET /rho` carries `funnel`: this node's own act-level alerts of the same 30 days, counted at four stages,
asked · acknowledged · acted · measured, with the median minutes between consecutive stages. It is not a second
ρ. Its `acted` is the literal stage, and it does not pool the children, whose `events` carry no stages
(`self_only: true`).

`measured` is derived, not posted: an alert with an `acted` row, whose rule the node still evaluates, and which
that rule did not raise again on the same sensor for `MEASURED_WINDOW_MIN` (2880 minutes, 48 hours) after the
act. The window outlasts every act-level rule's cooldown, so silence across it means the condition stopped
being true. That says *whether*, never *when*, so `latency_minutes.measured` is always `null`. A retired rule is
left out: it can never fire again, and its silence is not evidence of anything.

## What worked, per rule

`GET /effect` (v0.72) asks the same question per rule over the node's whole record (365 days by default): how
many acts there were (`acted`) and how many were followed by the condition stopping (`cleared`, the same
derivation as `measured`). A rule that declares `watch: {metric, over}` also gets `measured` (acts after which
that sensor's hourly mean came back under the line), `already` (acts made when it was already back), and the
median `hours` to recovery. Two rules declare one, both in `packs/air-quality/rules.yml`: `indoor_pm25_high`
(`pm25` over 35.5) and `outdoor_pm25_high` (`pm25` over 55.5). Every other rule answers `hours: null`, because
it fires on a relation, such as inside worse than outside, where a threshold would be a fiction. The dashboard
draws it as *Which of these worked*.

It is elapsed time, not an effect. A window opened at 21:00 and air that cleared at 03:00 may be the window or
may be the night, and the node cannot tell.

## What ρ is not

ρ counts answers. It does not measure the place. The funnel's `measured` and `GET /effect` are the node's evidence
about the place, and both say whether a condition stopped, not that the act stopped it. A second number read from
the place's own recovery (ρ_observed, beside the reported ρ, with a `recovery:` block in the rules) is proposed in
`docs/SPEC_rho.md`. That spec is Phase 1, and these parts of it are not built: no rule carries a `recovery:` block, and
`rho()` still counts `acknowledged` as a response, which the spec's §4 would change.

## Where it goes

- **The Index.** `GET /cells` appends `Governance|<Scale>` with ρ as its value when there has been any act-level
  alert in 30 days: `partial` until five have been acted on, `live` from then.
- **A parent.** Every hour the node posts its alerts of the last 36 hours to the parent's `/events` as timestamps
  only (`raised_at`, `responded_at`, `acted_at`, `measured_at`, the rule, the level, the pack), never the text,
  the actor, the sensor or a ratio. `measured_at` is filled only from a posted `measured` row, so a parent
  receives `null` there. The parent computes ρ under whatever definition it runs.
- **The export.** The daily CC BY 4.0 export carries `rho` as `index.rho()` returns it when the export is
  written: the rolling 30-day figure, not a figure for that day.
- **The report.** The bundle carries ρ now and a week ago; no sentence of the report says it.

## Recording an action

From off the machine, `POST /actions` needs `ACT_TOKEN` or `ADMIN_TOKEN`; from loopback (the node's own MCP
tools, a shell in the container) it needs none. A browser is never loopback. The body is `{"alert_id": 12,
"stage": "acted", "actor": "tomas", "note": "closed the windows"}`; `actor` is at most 80 characters, `note` 500,
and an unknown alert is a 404.

Each way in, and what it writes:

| way in | actor | note when none is given |
|---|---|---|
| the dashboard's *I did this* (v0.72) | the name typed in the form | will not post; the form needs the act or admin token Set up holds |
| `planetai act <id> [note]` | `$(whoami)` | `acted` |
| Telegram `/act <id> <words>` | `<AGENT_NAME>/telegram` | nothing is written; the bot asks "What did you do about #<id>?" |
| the MCP `act` tool | its `agent` argument | refused, along with placeholders such as `acted`, `done` or `ok` |
| `act <id> [note]` over LXMF | `lxmf:<hash>` | `acted (via reticulum)` |

The note is supposed to be what the person said. The MCP tool and the Telegram bot refuse to write a row
without it; the terminal and the radio fill in a placeholder, and `POST /actions` itself accepts any note. `GET
/actions` lists every answer with its stage, actor and note, and answers only a token or the machine itself.
`planetai snapshot` leaves the notes out of the file it writes.

## Invariants

The invariants that ρ depends on are on the [federation](federation.md) page with the rest: peers never roll up
and never drive an alert; the note on an action and the chat ids never leave the node at any sharing level; state is never upgraded by aggregation; exactly one node
per pilot writes to the Index's spine.

## Where this leads

The loop is closed: the node senses, observes, asks, hears back and measures. Extend it next with
[packs](packs.md), which add rules, cells and sources for a domain, and the [source registry](sources.md). Then
[sharing](sharing.md) and [federation](federation.md) are how ρ travels up to a district, as timestamps and
nothing else.
