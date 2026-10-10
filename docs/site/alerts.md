# Alerts
<!-- checked: v0.80.10 -->

An alert is the node asking a person to do something. This is the Act stage, which the architecture describes
as the one that "turns an observation into a human decision", and it is "the only place ρ can be measured".
With rules running, the node can interrupt a household with one plain message when a reading crosses a line,
then record what somebody did about it. Every answer is a row in `actions`, and [ρ](rho.md) is counted from those
rows, pooled with the answers a node's children report as timestamps.

## From a rule to a message

Every 60 seconds the rules loop runs each loaded rule (the two domain-blind ones in `config/rules.yml` and every
pack's `rules.yml`) as the read-only database role `planetai_ro`, which can read every table but `settings` and
can write nothing. Every row a rule's SQL returns is a candidate alert for the `sensor_id` in that row, or for
`node` if the row has none. This is how every rule works under `ALERT_ENGINE=rules`, the default. A rule that
declares a `kind:` belongs to the [event engine](#the-event-engine) and is skipped here. For each candidate:

1. **Cooldown.** If an `alerts` row for the same rule and sensor is newer than `cooldown_minutes` (default 60),
   nothing happens.
2. **Message.** The template for `ALERT_LOCALE` (falling back to English) is filled with the row's columns by
   Python's `str.format`. A `None` renders as `—`. A template that does not fit its row falls back to the raw
   text rather than failing.
3. **Record.** The alert is inserted into `alerts` and published to Home Assistant whatever its level. It is on
   the dashboard from here on.
4. **Send.** It goes out through `notify()` only if its level reaches `ALERT_LEVEL` and it is not held by quiet
   hours. With `ALERT_ENGINE=events` it is also not sent when its pack is one the event engine speaks for (heat and
   air-quality): the alert is still recorded, and the engine sends instead.

## The rule contract

A rule is a few keys in a `rules.yml`. `app/packs.py` loads them, namespaces a pack's ids as `<pack>/<id>`, and
`run_rules` in `app/main.py` runs them. `tools/check_rules.py` checks every one against the schema in
`init.sql` without a database.

| key | what it does |
|---|---|
| `id` | the rule's name; a pack's becomes `<pack>/<id>` |
| `level` | `act`, `warn` or `info` (default `info`) |
| `cooldown_minutes` | how long the same rule stays quiet on the same sensor (default 60). Over a fortnight is refused unless `long_cooldown_ok: true` |
| `sql` | the condition. Every row it returns is a candidate alert; its columns are what the message may print |
| `message` | `{en, id, es}`, three paragraphs each. Every placeholder must be a column the SQL returns |
| `contributes: report` | instead of a message: the rule is never sent, and its first row lands in the report's bundle |
| `kind`, `issue` | the event engine's: `kind` is `ahead` (no shipped rule uses it yet), `unusual`, `spike`, `sustained` or `danger`, and `issue` (default: the pack's issue, `heat` or `air`) is the story the row folds into. Its rows carry `value`, `line` and `over` |
| `watch: {metric, over}` | since v0.72: the indicator and the line this rule is about, so `GET /effect` can say how long an act took to work. `over` must be a number the SQL uses |

Every shipped rule with a message carries all three languages. The full contract, with the variables a rule's
SQL may read, is on the [Packs](packs.md) page.

## Levels

| level | meaning | default behaviour |
|---|---|---|
| `act` | something needs doing | always sent, even in quiet hours; also goes to the LoRa mesh and Reticulum |
| `warn` | something changed | sent only if `ALERT_LEVEL` is `warn` or `info` |
| `info` | everything else | sent only if `ALERT_LEVEL` is `info`; otherwise waits for the next report |

`ALERT_LEVEL` (default `act`) is the floor for interrupting a person. `planetai report level warn` lowers it
without a restart. Below the floor an alert is still recorded, still drawn on the dashboard, and still in the
bundle the next [report](report.md) is written from.

## Quiet hours

`QUIET_HOURS=1` (default) holds everything but `act` between `QUIET_FROM` (22) and `QUIET_TO` (6), local
time from `NODE_TZ`, wrapping midnight when the start is after the end. A report due inside quiet hours is
written and stored with `held_quiet` and not sent; the next one to go out covers every hour that was held. The
event engine is stricter: inside quiet hours it sends only `danger`, and an all-clear is held.

## What an alert says

Three paragraphs separated by blank lines: what is happening, what it means for the people in the house, and
what to do, the third opening with 👉. From the air pack:

```
🏠😷 The air inside at Kitchen is unhealthy right now.

Fine particles are high enough to bother people with asthma, children and older people, and to tire
anyone over a few hours.

👉 Run the purifier if you have one. Before opening a window, check whether outside is any better;
often it is not.
```

The 👉 paragraph is the rule author's recommendation. Since v0.72 the dashboard also draws it on its own on the alert
card in Decide, as "what this node suggests"; that card is what a node on `ALERT_ENGINE=rules` shows. A rule without one gets a line saying so, and the
page does not invent advice.

An act alert says what to do and asks for nothing back: since v0.39 no id is appended, because a number a
household is expected to quote back was a chore. The API's test alert (`POST /test-alert`) is the exception. It
ends with `👉 Reply /act N to show me how you close the loop.` when the bot runs, or `👉 In the terminal, planetai
act N records that you closed the loop.` when it does not; `planetai test-alert` prints the id in the terminal
instead. The rules name the threshold's source in their README, and the sentences carry the numbers the SQL
returned. A rule may not print a number its SQL did not compute.

## Languages

`ALERT_LOCALE` is `en`, `id` or `es`. Since v0.63 every rule with a message carries all three, the two core rules
and all 35 messaged rules in the packs that ship (seven of them the event engine's). The report, the test alert and the Telegram bot's own replies follow the same
setting; the bot's few fixed lines fall back to English for `id`. A language a template lacks falls back to
English. The presets set `id` for Bali, `es` for Menorca, Barcelona and Santiago, and `en` for Boston and Delhi.

## Where alerts go

`notify(level, text)` sends to Telegram every alert that reaches it, prefixed with the level's icon (ℹ️ ⚠️ 🔴).
An `act` alert also goes to the LoRa mesh (first line only; a LoRa frame is about 200 bytes) and to the Reticulum
bridge for LXMF delivery. Home Assistant is a separate call, `ha_alert()`, made for every alert whether it was
sent or not; it becomes the state of one text entity. The set-up of each is on [Channels](channels.md).

## The event engine

Under `ALERT_ENGINE=rules` (the default) every rule sends on its own, so one cooking event or one hot afternoon can
send a dozen messages. The event engine (`docs/SPEC_alerts.md`) folds the rows of the rules that declare a `kind:`,
today those of the `heat` and `air-quality` packs, into one **event** per issue per house, and sends one message per
event:

| `ALERT_ENGINE` | what it does |
|---|---|
| `rules` | the engine does not run. Default; anything else typed here behaves as `rules` |
| `shadow` | the engine decides and records each message it would send in `event_messages`, with the reason it was held, and sends nothing. The rules keep sending |
| `events` | the engine sends the heat and air messages, one per event, and the old heat and air rules still record their alerts (the dashboard, ρ and Home Assistant read those) but stop sending. Every other alert and the reports are unchanged |

An event is a row of `alert_events`, from the first candidate over its line to the all-clear. A candidate under its
line but inside the margin keeps an open event open and never opens one. The event **escalates** when its kind
climbs (`ahead`, then `unusual` or `spike`, then `sustained`, then `danger`), when its level rises, or when its
value is clearly past what it last said (2 °C for heat, 25 µg/m³ for air), and not twice within three hours unless
it climbs into danger. Danger already said is said again only when the value is clearly worse (air must double, heat
must pass the peak by 2 °C), and never within 30 minutes. The event **clears**
when no candidate has been seen for 30 minutes, with an all-clear if it ever sent anything. Every message, sent or
held, is a row of `event_messages` with its reason (`open`, `escalate` or `clear`) and what held it (`quiet`,
`ceiling` or `level`).

Whether a message is sent:

- `danger` is always sent: quiet hours, `ALERT_LEVEL` and the ceiling do not hold it.
- Anything else is held by `ALERT_LEVEL`, held in quiet hours (`QUIET_HOURS`, `QUIET_FROM`, `QUIET_TO`), and held
  once `ALERT_MAX_PER_DAY` messages (default 4) have gone out that local day. A held message is still recorded in
  `event_messages`, and the alerts the old rules still record reach the next [report](report.md).
- An all-clear is not counted against the ceiling, but is held in quiet hours.

Each message is the story and, under 👉, one action chosen from the issue's own list by what is true now: inside
against outside, the hour, and what the home has (`HOME_HAS`: `purifier`, `ac`, `fan`, `windows`). An action the
home cannot use is not offered, and a reading the node does not have never makes an action eligible. A message with
no usable action is the story alone. An all-clear carries no action.

An event is answered with three buttons: **Done** (`acted`), **Not now** (`acknowledged`) and **Doesn't fit** (`dismissed`), in `ALERT_LOCALE`. Telegram does not draw them yet;
`POST /actions` with an `event_id` records one (below). An open event leads `GET /issues`, which carries the events
as `events`, and the dashboard draws each open one once in Decide with the three buttons. On a node on `shadow` or `events`, an issue's state follows
its event: `act` while the event is open and unanswered (and for `danger`, answered or not), `notable` once somebody
answers it, for the `warn`-level air spike, and for 24 hours after it clears. The old heat and air alerts there
no longer count as open asks.

## The two rules the core knows

The core names no metric. Its two rules in `config/rules.yml` are about the instruments:

| rule | level | cooldown | fires when |
|---|---|---|---|
| `sensor_silent` | warn | 720 min | a local sensor's newest reading is more than 90 minutes old (`silent_minutes > 90`, a timestamp; the `trust` pack's `channel_dead` checks values) |
| `daily_pulse` | info | 100000 min | once, on an old node; superseded by the report and kept so existing nodes lose nothing until they update |

Everything else (`air-quality/indoor_pm25_high`, `heat/heat_danger`, `nearby/only_here`) is a pack's, and is
listed with its condition and cooldown on [Packs that ship](packs-reference.md).

## Answering an alert

An alert's `acted_at` is null until somebody answers it. An answer is a row in `actions` with a stage, an actor
(at most 80 characters) and a note (at most 500). There are six stages:

| stage | what it records | written by | counts toward |
|---|---|---|---|
| `acknowledged` | somebody saw it | `POST /actions` | ρ, and the funnel |
| `decided` | what somebody said would be done | the dashboard's Decide form, `POST /actions` | nothing |
| `acted` | somebody did the thing | the dashboard's *I did this*, `planetai act`, Telegram `/act`, the MCP `act` tool, `act <id>` over LXMF, `POST /actions` | ρ, the funnel, and closes the alert |
| `measured` | the condition stopped | derived by the node, never posted: an `acted` alert followed by 48 hours (`MEASURED_WINDOW_MIN`, 2880) with no new alert from the same live rule on the same sensor | the funnel; the alert was already closed by its `acted` row |
| `settings` | a setting was changed; an audit row with no alert | the node, on `PUT /settings` | nothing |
| `dismissed` | *Doesn't fit*: the advice did not fit the house. An answer to an [event](#the-event-engine), never to an alert | `POST /actions` with an `event_id` | nothing |

`POST /actions` accepts `acknowledged`, `acted` and `decided` and refuses the rest with a 400. Given an `event_id` in
place of an `alert_id` (not both), it accepts `acknowledged`, `acted` and `dismissed`, writes one row with the
`event_id` and no `alert_id`, and answers 404 for an event that does not exist. Every ρ, funnel and effect query
joins `actions` to `alerts` on `alert_id`, so an event's answer changes no published number in this release.
`DECISION_REQUIRED` does not apply to it.

**A decision moves nothing.** It is not in ρ, not a stage of the funnel, and closes no alert; the node keeps
watching. What it changes is the record: a household that looked, decided and did not manage it no longer leaves
the same trace as one that never looked. With `DECISION_REQUIRED=1` (Set up → Alerts, off by default), `POST
/actions` answers an `acted` with no earlier `decided` row for the same alert with a 409, whichever way the act
came in. Turn it on only where everybody answering has a screen to decide on: the radio, the terminal and the
bot have none.

## Who has to use their own words

ρ is built out of these rows, so the note is supposed to be what the person said. Not every way in enforces it:

| way in | without a note |
|---|---|
| the dashboard's *I did this* and Decide forms | will not post; needs `ACT_TOKEN` or `ADMIN_TOKEN` from Set up |
| Telegram `/act <id> <words>` | `/act 23` alone is answered with "What did you do about #23?" and nothing is written |
| the MCP `act` tool | refuses an empty note and placeholders such as `acted`, `done` or `ok` |
| `planetai act <id> [note]` | records the note `acted` |
| `act <id>` over LXMF | records the note `acted (via reticulum)` |
| `POST /actions` directly | records whatever it is given |

An agent is expected to ask the person and record their answer, and the MCP tool's refusal is what holds an
agent to it.

## Conditions that are not events

A heat alert is a condition that holds for hours; the ratio test between inside and outside cannot tell a
stopped stove from an opened door. Under `ALERT_ENGINE=rules`, every rule is an event with a cooldown; there is no
`recovery` block and an `alerts` row has no notion of clearing, only of cooldowns. (The [event engine](#the-event-engine)
does clear, but its events are rows of their own, in `alert_events`.) The dashboard marks
an open act-level alert as *current* only while its condition still holds (the house over the line, or the
alert under two hours old), and otherwise says the reading came back on its own and the alert is still open.
Turning conditions into their own kind of rule, with a reminder at 30 minutes and at two hours and then
silence until the next report, is proposed in `docs/archive/handoffs/HANDOFF_reports.md` and not built; the event
engine's way of saying a condition went on and ended is a different one. What the node does
have is the derived `measured` stage above and `GET /effect`, which counts per rule how many acts were
followed by the condition stopping; neither is a `recovery` block.

## Reading them

`GET /alerts?limit=50` lists the most recent with `id, ts, rule_id, sensor_id, level, text, acted_at`, and is
where an alert's id comes from. `GET /actions` lists every answer with its stage, actor and note, and answers
only a token or the machine itself, because a note is a household's own words about its own house. `GET /issues`
carries the alert events as `events` (what is open, the action it sent, its latest answer, and the alerts it covers),
and `GET /actions?events=1` lists the answers given to events with their `event_id`; without `events=1` a row with
no `alert_id` is left out. `planetai status` shows the last three alerts and ρ. On the dashboard, Decide draws each
open event once, with its action and Done, Not now and Doesn't fit, and each open alert on a node still on the old
engine; *What was asked, and what was answered* is the record of what was sent and answered, and *What was decided,
and by whom* is the ledger of answers. The report's fourth part says what
happened after the window's act alerts.

## Where this leads

The node can now ask. Next, choose where the asking reaches people: [Channels](channels.md) sets up Telegram,
the LoRa mesh, Reticulum and Home Assistant. Then [ρ](rho.md) is how the node measures whether the asking
worked.
