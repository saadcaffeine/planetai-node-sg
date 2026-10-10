# SPEC — alerts become events: fewer messages, each one worth acting on

*Asked, 4 October 2026, by Tomas: the bot's messages "feel more like spam than anything. It is registering the need
for actions in periods that do not make sense for the high temperature." He wants alerts for a real spike, for a
level that lasts long enough to be dangerous, and ahead of an event, with suggestions that fit what is happening.*

**Status: approved in conversation, 4 October 2026; nothing here is built.** Sections 1–6 and the settings were
agreed one at a time. The numbers marked *starting value* are set by the replay in §9, not by this page.

## 1. What node #1 shows (30 days to 4 October 2026, read-only)

- **About 390 messages were pushed, 13 a day.** 247 of them arrived in 41 bursts of three or more, up to 13 in one
  hour. One cooking event fires `indoor_spike`, `indoor_pm25_high` and `inside_worse_ventilate` on each of three
  rooms. Two of those give opposite advice: run the purifier and keep shut, or open a window because it is faster
  than a purifier.
- **"Dangerously hot" was sent on 14 of 14 days.** Indoor air never reached 32 °C and the outdoor model never passed
  29 °C. `heat/heat_stress_now` fires at an indoor apparent temperature of 35, and K ROOM spends 38% of its hours
  there. Its median trigger value was 35.1. It re-sends every 4.4 hours, which is its cooldown, and act level ignores
  quiet hours, so 17 went out between 00:00 and 06:00.
- **Indoor heat does not spike.** It is a smooth curve: the mean climbs from 33.1 at 04:00 to 36.0 at 17:00, and a
  run at 35 or above lasts 4.8 hours on average. There were no indoor rises above 3 °C in an hour. From 17:00 to
  08:00 the rooms are 4–5 °C warmer than outside, and no message says so.
- **PM2.5 detection works; it is the volume that fails.** 30 of 31 hourly rises above 10 µg/m³ were caught.
- **The household stopped answering.** 4 answers to 162 pushes in the last 14 days, none to any warn rule, and
  `measured` has never been recorded. The notes that exist describe something other than the advice: "ac on",
  "filter is on", and "closed windows" in reply to "open a window".
- **Reports go out with nothing in them.** About four a day at `REPORT_EVERY=6`, many ending "Nothing needs doing
  before the next report". Info and warn alerts are promised to "wait for the next report", but they never reach the
  text a household reads.
- **There is no forecast.** The forecast pack has no source configured on node #1.

The causes, in the code: act rules fire on `stats.mean_15m` (one to three polls) with no duration, no hysteresis
and no usual-for-this-hour baseline. The cooldown is the engine's only memory. There is no grouping across rules or
rooms. Each rule carries its own fixed 👉 line. The forecast pack is forbidden to send, and no rule reads it.

## 2. The shape

Rules stay SQL in packs. Between the rules and Telegram sits a new **event layer**:

```
rule rows ──► alerts (every row, as today) ──► events: one per issue per house ──► one message, one action
                                                   open · escalate · clear              buttons ──► actions
```

The model is not in this path. Whether to interrupt, and with what action, is decided in code and can be replayed.
A model may rephrase a message that has already been decided (§8). It cannot add one, remove one or change its
action.

## 3. Triggers

Each rule declares `kind:` and `issue:` in its `rules.yml` entry. `issue` defaults to the pack's `domain`.

| kind | fires when | default for heat (*starting values*) | default for air (*starting values*) |
|---|---|---|---|
| `spike` | a jump against the last hour that is also well above this room's usual for this hour | (indoor heat does not spike) | 15-min mean ≥ last hour + 12, and ≥ same-hour p90 + 10 µg/m³ |
| `sustained` | above a health line for long enough to matter, and longer than this room's usual run | apparent temperature ≥ 35 for ≥ 3 h, and longer than the room's usual (p75) run | ≥ 35 µg/m³ for ≥ 60 min |
| `unusual` | well above this room's own normal for this hour, even when under any fixed line | ≥ same-hour p90 + 2 °C for 1 h | ≥ same-hour p90 + 15 for 1 h |
| `danger` | past a true danger line, briefly; the only kind sent in quiet hours | apparent temperature ≥ 40 (NOAA "danger") | ≥ 125.5 µg/m³ (US EPA 2024 "very unhealthy") |
| `ahead` | the forecast or the room's own daily curve says it is coming within 12 h | §6 | §6 |
| none | never interrupts; reaches the report only | | |

A rule with no `kind:` is report-only. That is the safe default for every pack that has not been revised, and it
is how a lazy or legacy pack is still heard.

The core provides the measures the kinds need, so a rule does not reinvent them:

- `usual_by_hour`: a materialised view of each sensor and metric's median and p90 for each local hour over the last
  14 days, from `readings_1h`. It is refreshed hourly by the app; rules read it as `planetai_ro` like everything else.
- `recent_15m`: 15-minute means for the last 24 hours. A rule counts minutes above a line, or compares the last 15
  minutes with the hour before, from this view.
- Forecast rows read through a bounded view, `ahead_12h` (`ts > now() AND ts <= now() + interval '12 hours'`), never
  through `observations`, whose "latest" forecast row is tomorrow's.

## 4. Events and messages

**Grouping.** Every row a rule returns still writes an `alerts` row, as today. It no longer sends. The core folds it
into the open event for its `(issue, house)`: heat is one event whichever room fired it, and air is another. A new
`alert_events` table (an `events` table already existed) holds one row per event: `id, issue, kind, level, opened_at,
last_seen_at, last_sent_at, cleared_at, peak, rooms, places, ever_sent,
action_id, told_kind, told_peak, told_level, told_held, last_emitted_at` (`places` is the event's inside/outside places). `event_messages` holds one row per decided
message: `event_id, ts, reason, sent, held, mode, kind, text, action_id`. `alerts.event_id` and `actions.event_id` point
at the event. In shadow mode, kinded rules write no alerts row (an act-level row is an open ask on the dashboard and
enters ρ); recording them and linking alerts.event_id arrives with the release that sends events.

**Lifecycle.**
- **Open**: the first row sends one message.
- **Escalate**: sends again only when the kind climbs (unusual → sustained → danger) or the value clearly passes its
  peak, and never within 3 h of the last message. `danger` always sends.
- **Clear**: the condition has been false, with a margin, for 30 minutes (heat: 1 °C under the line, air: 5 µg/m³ under).
  If the event had been sent, the household gets one all-clear, held to the morning if it falls in quiet hours.
- **Match**: a new row that matches an open event updates it silently.

**Quiet hours** (`QUIET_HOURS`, `QUIET_FROM`, `QUIET_TO`): only `danger` sends. Anything else that opened overnight
leads the first report after quiet hours.

**Daily ceiling** (`ALERT_MAX_PER_DAY`, default 4): pushes outside `danger`, per house per local day. Beyond it, events
are still opened and cleared; they reach the next report instead of the phone.

**The message** is one story from a template per issue and kind, in `app/issues/<issue>.yml` under `events:`: what is
happening, in which rooms; how long, or how sudden, against what usual; one action (§5); and buttons (§7). The cooking
burst of 15 September, 13 messages, becomes:

> 🍳 Smoke inside — K, L and S rooms jumped to 59 µg/m³ in the last 20 minutes (usual at this hour: 9). Outside is 12.
> 👉 Open the kitchen side and run the purifier for 30 min. [Done] [Not now] [Doesn't fit]

and one all-clear 40 minutes later.

Home Assistant still receives every raw row. The rules keep their `message`, which still fills the `alerts` row and
the record, but their 👉 lines are removed: the action belongs to the event.

## 5. Actions, chosen from what is happening

Each issue keeps an ordered list of candidate actions in `app/issues/<issue>.yml` under `actions:`. A pack may add
actions to an existing issue in its `pack.yaml` under `actions:`. Each action has an `id`, a `when:` over the event's
context, and its sentence in en, id and es. The first action whose `when:` holds is sent, so one event carries
exactly one action and two rules can no longer give it contradictory advice.

**The context**, computed by the core for every event:
- inside against outside, for temperature and PM2.5: own outdoor kit first, then nearby stations, then the model,
  and the message names which it used;
- the local hour, and how outside has moved over the last hour;
- the next 12 hours from `ahead_12h`: rain, wind, temperature;
- what the home has (`HOME_HAS`, §10);
- what worked in this house before (below).

**Heat on node #1**, for example:
- outside cooler by ≥ 2 °C and outside air clean → "Open up now: outside is 24.9 °C, inside 29.3."
- outside hotter → "Keep it shut and shaded; outside drops below inside around 18:00."
- sustained, `HOME_HAS` includes AC, a sleeping room affected → "Cool the room you sleep in before 22:00."

**Air**: the spike is inside and outside is clean → "Open the kitchen side and run the purifier 30 min."; outside is
worse → "Keep shut, run the purifier."

**Learning from this house, deterministically.** Every message records the action id it sent.
- **Done** followed by a clear records how long that action took to clear the event. Among actions whose `when:`
  holds, the node prefers the one that cleared fastest here, and may say so: "last time the AC cleared it in 40 min".
- **Doesn't fit** twice for the same action mutes it for this house for 30 days.

The ranking only reorders actions whose conditions already hold. It cannot produce advice the conditions rule out.

## 6. Anticipation

**The house's own pattern** (nothing leaves the house). Each room's usual curve over the day (`usual_by_hour`) and
the usual hour at which inside becomes warmer than outside.

**Open-Meteo**, through the forecast pack's existing source, switched on for node #1 by Tomas's go. Before that, its
adapter rounds the coordinates it sends to two decimals (about 1 km), as the core adapters do; today it sends them
unrounded (`docs/site/sharing.md`).

What it sends:
- **The morning plan**, never a push: the first lines of the first report after quiet hours. "Hot 13–17 in K room, as
  usual; outside cooler from 18:00, open up then. Rain likely 15:00."
- **The unusual day ahead**, an `ahead` event and a push: only when the forecast clearly beats the room's own usual
  (*starting value*: forecast high ≥ usual + 2 °C, or a night forecast not to cool). "Tomorrow is forecast 3° hotter
  than usual. Shade the west side before 11:00."
- **The evening crossover**, at most once a day and only while a heat event is open: "Outside is now cooler than K
  room. Open up."
- **Air arriving**: outdoor PM2.5 rising for two consecutive hours, or a neighbouring station upwind rising, opens an
  `ahead` air event before the house's own sensors see it.

The forecast pack's own promise stays true: it supplies data and never sends. The heat and air packs own the `ahead`
rules.

## 7. Closing the loop

**Telegram buttons** on every event message, handled by the bot in the `agent` container, which already polls
Telegram. The app keeps sending, and the bot handles the replies. The app attaches the keyboard when the bot has
announced itself (`TELEGRAM_BUTTONS=1`, set by the bot on startup): a node without the `agent` container sends
the same message without buttons. `callback_data` is `ev:<event_id>:<stage>`, labels are the wire's own
(`actions.BUTTONS`), and the bot answers with the same `POST /actions` the dashboard makes — page and phone
write the same row. After a press the keyboard lifts and the chat carries the record: `Done · tomas`.
- **Done** → `acted`. A clear afterwards writes `measured`, with the time from Done to clear.
- **Not now** → `acknowledged`. The event sends nothing more for 3 h unless it reaches `danger`.
- **Doesn't fit** → a new stage, `dismissed`, which counts against that action for this house. The bot asks one
  optional question, "What did you do instead?", and keeps the answer as the note: the dismissal is recorded at
  the press, and a free-text line within ten minutes rides a second row (repeated answers are allowed on
  purpose — the wire keeps the latest, which is the one carrying the note).

**The dashboard's Decide card** shows the same open events with the same three buttons (v0.78, §11).

**ρ counts events.** ρ becomes the share of act-level events that somebody answered (any button), with the funnel
answered → acted → measured. Today one cooking event is nine unanswered alerts. Because this changes a published
number, it gets its own record in `docs/decisions/`. Existing rows stay readable.

## 8. Packs, and where a model fits

Every pack, core or wild, follows this contract. The core arbitrates, because a single daily ceiling only holds with
a single judge.
- A pack rule may join an existing issue (`heat`, `air`, `land`, `coast`) with a `kind:`. A rule for an issue the
  node does not know is report-only until that issue is core, because an issue's templates and actions live in
  `app/issues/`.
- A pack may add `actions:` to an existing issue, under the same `when:` rules.
- A rule with no `kind:` never interrupts.

A model is used in three places, none of which decides whether to interrupt:
- **writing a pack**: `skills/write-a-pack` helps an author choose kinds, lines and actions, and check them against
  their own house's history before listing;
- **phrasing**, optionally: rewording a decided message for the household, with the deterministic text as the
  fallback;
- **the report**, where it may summarise report-only rows.

## 9. Proof before shipping

`tools/replay_alerts.py` runs both engines, today's rules and the event layer, over the same 30 days of node #1,
five minutes at a time. It runs in a scratch Postgres loaded from a read-only dump that includes `actions`, the
rows `planetai snapshot` leaves out. Rules read the replay clock in place of `now()`. It prints one comparison table
and every message each engine would have sent, side by side.

| measure | today | target |
|---|---|---|
| pushes per day, median | ~13 | ≤ 3 |
| non-danger pushes 22:00–06:00 | 23 | 0 |
| events carrying contradictory advice | several bursts | 0 |
| "dangerously hot" with indoor air < 32 °C and nothing unusual | 78 in 14 days | 0 |
| PM2.5 hourly rises > 10 µg/m³ caught | 30 of 31 | 31 of 31 |
| sustained or unusual heat runs reported | – | every one, once |

A missed target changes the design, not the target. Tomas reads both message streams before anything merges.

**Shadow mode** (`ALERT_ENGINE=shadow`): the event layer writes events and the messages it would send, sends
nothing, and today's engine keeps sending. Node #1 runs shadow for several days before it switches to `events`.
Switching back is the same setting.

## 10. Settings

| key | status | meaning |
|---|---|---|
| `REPORT_AT` | new; replaces `REPORT_EVERY` and `REPORT_ANCHOR` | the local hours reports go out, any list (`7,19`; `7,13,19`). Empty means no reports, alerts only. Set up offers presets (morning; morning and evening; every 6 h; every 3 h) and a custom list. Existing `REPORT_EVERY`/`REPORT_ANCHOR` values convert once, the way retired keys convert today |
| `REPORT_SKIP_EMPTY` | new, default 1 | a report with nothing new is not sent. The first report after quiet hours always goes: it carries the morning plan and anything held overnight |
| `ALERT_MAX_PER_DAY` | new, default 4 | §4's ceiling; `danger` is never counted against it |
| `QUIET_HOURS`, `QUIET_FROM`, `QUIET_TO` | kept, meaning tightened | in quiet hours only `danger` sends (today, any act-level alert does) |
| `ALERT_LEVEL` | kept | act = only events with an action; warn = also spikes that are not unhealthy yet; info = everything |
| `HOME_HAS` | new | purifier, AC, fan, windows that open. Asked once in Set up and by the bot; feeds §5 |
| `ALERT_ENGINE` | new | `rules` (today), `shadow`, `events`. Retired once `events` is the default everywhere |
| `TELEGRAM_BUTTONS` | new, default 0; the bot sets it to 1 on startup | §7's keyboard rides event messages only while the bot that answers it is running. Nobody sets it by hand |
| `REPORT_DEPTH` | unchanged | still waits for a model |

A report built from events covers everything since the last one: events opened, cleared and still open; what was
done and how fast it cleared; what went over the ceiling and what was held overnight. The first report of the day
leads with the morning plan. With `REPORT_AT` empty there is no morning plan; held and over-ceiling events then wait
for the dashboard.

Not included: muting a whole issue ("never tell me about heat"). Unusual-only heat, Not now and Doesn't fit should
cover it; add it if the replay or shadow mode shows otherwise.

## 11. Order of work and releases

Each step is its own pull request, mergeable and harmless on its own:

1. Measures (`usual_by_hour`, `recent_15m`, `ahead_12h`) and the replay tool. **Done.**
2. The `alert_events` table, `alerts.event_id`, `actions.event_id`, the `dismissed` stage; grouping, escalation, clearing,
   quiet hours and the ceiling, in shadow only. **This changes `init.sql`, which `GOVERNANCE.md` says needs two
   maintainers.** **Done — except `alerts.event_id`: the wire still matches covered rows by time window.**
3. Actions per issue, the context resolver, `HOME_HAS`. **Done.**
4. Heat and air rules rewritten with kinds. The old rules are retired, not deleted, so their silence is never read as
   a cleared condition. `tests/test_shipped.py` pins the heat rule's text "needs Tomas's sign-off"; this spec is that
   sign-off once he approves the replay. **Done. The pins moved again 10 October with Tomas's approval: the act
   rules now name whose line it is (`{line}` filled from `watch.over`, gated by `tools/check_rules.py`).**
5. Telegram buttons, the bot's handling of them, and the ρ decision record. **Buttons and the bot shipped
   10 October (`TELEGRAM_BUTTONS`; the Doesn't-fit note rides a second row). The ρ decision record is still owed.**
6. Forecast coordinate rounding, the `ahead` rules, then Open-Meteo on node #1 (a setting on his node, by his go).
   **The `ahead` rules are still owed — the engine ranks the kind, no pack ships one.**
7. `REPORT_AT`, `REPORT_SKIP_EMPTY`, and reports built from events. **Still owed.**
8. Node #1 from `shadow` to `events`; then `events` as the default. **Node #1 runs `events`.**

`docs/NEXT_RELEASE.md` allows one large change per release and keeps `app/static/*` apart from `packs/*`. So **v0.77**
carries the engine, the packs, Telegram and the reports, and **v0.78** carries the dashboard's Decide card for events.
Until v0.78 the page shows open asks as it does today.

## 12. What this does not do

- No model decides whether to interrupt.
- No new container, and no change to how Telegram messages are sent.
- Nothing is deleted: `alerts` keeps every row, and retired rules stay retired.
- The forecast pack still never sends.
