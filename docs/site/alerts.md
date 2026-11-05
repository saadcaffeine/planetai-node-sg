# Alerts
<!-- checked: v0.91.0 -->

An alert is the node asking a person to do something. When a reading crosses a line, the node sends the household
one plain message, then records what somebody did about it. Every answer is a row in
`actions`, and [ρ](rho.md) is counted from those rows.

The node has two ways of turning rules into messages, chosen with `ALERT_ENGINE`:

| `ALERT_ENGINE` | what happens |
|---|---|
| `rules` | the default. Every rule sends on its own, each with its own cooldown. Anything else typed here behaves as `rules` |
| `shadow` | the rules keep sending, and the [event engine](#the-event-engine) runs beside them: it records each message it would send in `event_messages`, with the reason it was held, and sends nothing |
| `events` | the event engine sends the heat and air messages, one per event. The heat and air-quality rules still record their alerts (the dashboard and Home Assistant read those) but stop sending. Every other rule and the reports are unchanged |

## From a rule to a message

Every 60 seconds the rules loop runs each loaded rule (the five in `config/rules.yml` and every pack's
`rules.yml`) as the read-only database role `planetai_ro`, which can read every table but `settings` and write
nothing. Every row a rule's SQL returns is a candidate alert for the `sensor_id` in that row, or for `node` if the
row has none. A rule that declares a `kind:` belongs to the event engine and is skipped here. For each candidate:

1. **Cooldown.** If an `alerts` row for the same rule and sensor is newer than `cooldown_minutes` (default 60),
   nothing happens.
2. **Message.** The template for `ALERT_LOCALE` (falling back to English) is filled with the row's columns by
   Python's `str.format`, `{line}` with the rule's `watch.over`, and `{act}` with the alert's own answer line, `/act 812`
   where the bot runs and `planetai act 812` where it does not. A `None` renders as a dash. A template that
   does not fit its row is sent as the raw template.
3. **Record.** The alert is inserted into `alerts`, with its buttons if the rule offered valid ones, and handed to every pack's `on_alert` hook whatever its level
   (the `home-assistant` pack publishes it there). From here it is on the dashboard.
4. **Send.** It goes out through `notify()` only if its level reaches `ALERT_LEVEL` and quiet hours do not hold it.
   On `ALERT_ENGINE=events` a heat or air-quality alert is not sent at all; the engine sends instead.
   With `TELEGRAM_BUTTONS=1` the alert's buttons go with it to Telegram as a keyboard.

How to write a rule, with every key, the tables its SQL may read and the lint that checks it, is on
[Packs](packs.md#rules).

### Asking with buttons

A rule can return a `buttons` column: rows of buttons, each with its text in the languages it writes, a `value`, and
optionally a `stage` (`acted` by default, or `acknowledged`) and a question to ask when the button is pressed. The node
stores them with the alert. Telegram draws them as a keyboard when `TELEGRAM_BUTTONS=1`, and Now lists them under What
to do. A column that does not validate costs the alert its buttons and nothing else, with one warning in the log, and a
keyboard Telegram refuses is dropped and the message sent again without it.

Each press is one `POST /actions` with a `choice`, which sets the stage. The node refuses a choice the alert did not
offer (400) and an alert older than 72 hours (409, "this question has closed"). It keeps one row for each person's
choice on an alert, and a later note from the same person replaces the earlier one. When a button asks a question,
the reply from the person who pressed is kept as the note. An `acknowledged` button answers the whole alert. How to
write them is on [Packs](packs.md#rules).

## Levels

| level | meaning | under `rules` |
|---|---|---|
| `act` | something needs doing | always sent, even in quiet hours, and also to the LoRa mesh and Reticulum where they are set up |
| `warn` | something changed | sent only if `ALERT_LEVEL` is `warn` or `info` |
| `info` | everything else | sent only if `ALERT_LEVEL` is `info`; otherwise it waits for the next report |

`ALERT_LEVEL` (default `act`) is the floor for interrupting a person, and `planetai report level warn` lowers it
without a restart. Below the floor an alert is still recorded, still drawn on the dashboard, and still in the
bundle the next [report](report.md) is written from.

## Quiet hours

`QUIET_HOURS=1` (default) holds everything but `act` between `QUIET_FROM` (22) and `QUIET_TO` (6), local time
from `NODE_TZ`, wrapping midnight when the start is after the end. A report due inside quiet hours is stored with
`held_quiet` and not sent; the next one that goes out covers the held hours. The event engine is stricter: inside
quiet hours it sends only `danger`.

## The event engine

Under `rules` one cooking event or one hot afternoon can send a dozen messages. The event engine
(`docs/SPEC_alerts.md`) folds the rows of the rules that declare a `kind:`, today those of the `heat` and
`air-quality` packs, into one event per issue, and sends one message for the event as it opens, escalates and
clears.

An event is a row of `alert_events`. It opens at the first candidate over its line. A candidate under the line but
inside the margin keeps an open event open and never opens one. The event **escalates** when its kind climbs
(`ahead`, then `unusual` or `spike`, then `sustained`, then `danger`), when its level rises, or when its value is
clearly past what it last said (2 °C for heat, 25 µg/m³ for air). It does not escalate twice within three hours
unless it climbs into danger. Danger already said is said again only when the value is clearly worse (air doubles,
heat passes the peak by 2 °C), and never within 30 minutes. The event **clears** when no candidate has been seen
for 30 minutes, with an all-clear if it ever sent anything. These gaps replace the rules' cooldowns. Every
message, sent or held, is a row of `event_messages` with its reason (`open`, `escalate` or `clear`) and what held
it (`quiet`, `ceiling` or `level`).

Whether a message is sent:

| message | held by |
|---|---|
| `danger` | nothing: quiet hours, `ALERT_LEVEL` and the ceiling do not hold it |
| anything else | `ALERT_LEVEL`; quiet hours (`QUIET_HOURS`, `QUIET_FROM`, `QUIET_TO`); and the ceiling, once `ALERT_MAX_PER_DAY` messages (default 4) have gone out that local day |
| an all-clear | quiet hours only; it does not count against the ceiling |

A held message is still recorded, and the alerts the old rules record reach the next [report](report.md).

Each message is the story and, under 👉, one action chosen from the issue's own list by what is true now: inside
against outside, the hour, and what the home has (`HOME_HAS`: `purifier`, `ac`, `fan`, `windows`). An action the
home cannot use is not offered, and a reading the node does not have never makes an action eligible. With no
usable action the message is the story alone, and an all-clear carries none.

An event is answered with three buttons in `ALERT_LOCALE`: **Done** (`acted`), **Not now** (`acknowledged`) and
**Doesn't fit** (`dismissed`). Telegram draws them once the bot has announced itself (`TELEGRAM_BUTTONS=1`, see
[The bot](bot.md)), and the dashboard draws each open event once in Decide. Each press is one `POST /actions` with
an `event_id`. The buttons show while the event's `asking` is true: until somebody answers, and again after a Not
now once its three hours run out. On the dashboard the action is chosen again from the readings as they are now;
the message that was sent keeps its words.

On a node on `shadow` or `events`, an issue's state follows its event: `act` while the event is open and
unanswered (and for `danger`, answered or not), `notable` once somebody answers it, for the `warn`-level air
spike, and for 24 hours after it clears. The old heat and air alerts there no longer count as open asks.

## What an alert says

Three paragraphs separated by blank lines: what is happening, what it means for the people in the house, and what
to do. The first line opens with one emoji, and the level's icon is not added in front of it. From the heat pack,
whose `{line}` is the rule's own `watch.over`:

```
🚨 Dangerous heat at Kitchen: it feels like 41 °C, past the danger line here, 40 °C.

This is heatstroke territory. The body cannot shed heat at this level, and it goes wrong fast.

Cool the room or leave it. Wet skin, a fan, shade, water. Do not leave anyone alone in it.
```

A rule names its threshold's source in its pack's README, and the sentences carry the numbers its SQL returned. A
rule may not print a number its SQL did not compute.

On the classic dashboard, which is what a node on `rules` shows in Decide, a third paragraph that opens with 👉 is
drawn on its own on the alert card as "what this node suggests". The `trust/` and `nearby` rules, among others,
open it so. The `air-quality`, `heat` and `fire` rules do not, so their cards say there is no suggestion, and the
page does not invent one.

An alert asks for nothing back and carries no id, unless its message says `{act}` or its rule offers buttons. The test alert (`POST /test-alert`, `planetai test-alert`) is
the exception: it ends with `👉 Reply /act N to show me how you close the loop.` when the bot runs, or `👉 In the
terminal, planetai act N records that you closed the loop.` when it does not.

## Languages

`ALERT_LOCALE` is `en`, `id` or `es`. Every rule with a message carries all three: the five core rules and the 33
messaged rules in the packs that ship. The report, the test alert and the Telegram bot's own replies follow the
same setting; the bot's few fixed lines fall back to English for `id`. The presets set `id` for Bali, `es` for
Menorca, Barcelona and Santiago, and `en` for Boston and Delhi.

## Where alerts go

`notify()` sends to Telegram every alert that reaches it, prefixed with the level's icon (ℹ️ ⚠️ 🔴) unless the
text opens with its own sign. An `act` heat or air alert that weighs on someone ticked under *Who is in the house*
ends, in Telegram only, with one line such as "This matters more here: you said there is a child under five." That
line never goes to the mesh, Reticulum, Home Assistant or the stored text. An `act` alert also goes to the LoRa
mesh (first line only, with `MESH_ALERTS=1`) and to the Reticulum bridge for LXMF delivery. Home Assistant is the
`home-assistant` pack's `on_alert` hook, which hears every recorded alert whether it was sent or not. Setting each one up is on
[Channels](channels.md).

## The rules the core knows

The core names no metric. Its rules in `config/rules.yml` are about the instruments. Two say whether a sensor is
heard at all:

| rule | level | cooldown | fires when |
|---|---|---|---|
| `sensor_silent` | warn | 720 min | a local sensor's newest reading is more than 90 minutes old (`silent_minutes > 90`; `trust/channel_dead`, below, checks the values) |
| `daily_pulse` | info | 100000 min | once, on an old node. The report replaced it, and it stays so existing nodes lose nothing until they update |

and three, under [Trust](#trust), whether what it says can be believed. Every other rule
(`air-quality/indoor_pm25_high`, `heat/heat_danger`, `nearby/only_here` and the rest) is a pack's, and is listed with
its condition and cooldown on [Packs that ship](packs-reference.md).

## Trust

Whether the node's own sensors are telling it the truth: coverage over the last week, channels that have
stopped changing under a kit that still reports, and collocated sensors that disagree about the level.

Its three rules are the core's, at the end of `config/rules.yml`, and run on every node. They were the `trust` pack
until 22 October 2026 and keep its ids, `trust/channel_dead`, `trust/coverage_low` and `trust/peer_disagreement`, so
an alert already sent keeps its cooldown and its history. There is no cell: a trust score is a fact about the node's
instruments, and a cell for it would invite tuning the score instead of fixing the sensor.

Every rule joins the same `seasoned` gate, a sensor whose first reading in the last 30 days is more than seven
days old, because a day says more about the weather than about the instrument. All three rules are `info`
with a seven-day cooldown, so they speak in the week's instrument paragraph and never interrupt an evening.

| rule | level | cooldown | fires when |
|---|---|---|---|
| `trust/channel_dead` | info | 10080 | a local `kind='sensor'` channel with role `ambient` or `enclosure` has all 24 of the last 24 hourly buckets present and flat (`max − min = 0`), the flat value is not 0, the kit reported within 2 hours, and another ambient channel on the same kit moved |
| `trust/coverage_low` | info | 10080 | a seasoned local ambient comparable channel reported for under 60% of the 168 hours in 7 days |
| `trust/peer_disagreement` | info | 10080 | two seasoned local ambient comparable sensors within 50 m, each with at least 100 buckets in 7 days, have a 7-day mean ratio outside 0.85 to 1.15 and an absolute difference at or above a per-metric floor (5.0 for `pm1`, `pm25`, `pm10`; 2.0 for `temp`; 5.0 for `humidity`; 0.3 kPa for `pressure`; else 15% of the pair mean). One row per pair, `sensor_id = a\|b` |

`channel_dead` reads values, not timestamps, because Smart Citizen's per-reading `recorded_at` is null and a
frozen channel still gets a fresh timestamp on every poll. A full day of flat buckets is longer than any
night, so a light channel at dusk does not trip it. The PM floor in `peer_disagreement` is Plantower's own
±10 µg/m³ below 100 µg/m³, halved.

`GET /trust`, which the trust card and the agent's health check read, counts a sensor's frozen channels by running
`trust/channel_dead`'s own SQL, so the card and the alert say the same thing. Until 22 October 2026 it kept a copy
of the older test, six flat hours out of 24, and called a light channel frozen every night.

`peer_disagreement` cannot tell a badly sited sensor from a badly calibrated one, which is why its message asks
the reader to swap the two units for a day instead of naming the wrong one. They do not see PurpleAir's
`channel_disagreement` or Meshtastic's `altitude_m`, which never gets a role. None of the thresholds has met a
burn season.

## Answering an alert

An alert's `acted_at` is null until somebody answers it. An answer is a row in `actions` with a stage, an actor and
a note; the six stages, and which of them count in ρ, are on [ρ](rho.md#stages), and every way of recording one is
under [Recording an action](rho.md#recording-an-action).

`POST /actions` takes `acknowledged`, `acted` and `decided` for an `alert_id`, and refuses the rest with a 400. With a
`choice` instead of a stage it takes the stage from the alert's button.
Given an `event_id` instead (not both), it takes `acknowledged`, `acted` and `dismissed`, writes one row with the
`event_id` and no `alert_id`, and answers 404 for an event that does not exist. ρ and the funnel count an event's
answer; `GET /effect` does not, because it joins `actions` to `alerts`.

A `decided` row closes no alert and counts in neither ρ nor the funnel; the node keeps watching. It changes
the record: a household that looked, decided and did not manage it no longer leaves the same trace as one that
never looked. With `DECISION_REQUIRED=1` (Set up → Alerts, off by default), `POST /actions` answers an `acted` with
no earlier `decided` row for the same alert with a 409, whichever way the act came in. Turn it on only where
everybody answering has a screen to decide on, because the radio, the terminal and the bot have none. It does not
apply to an event's buttons.

## Conditions that are not events

A heat alert is a condition that holds for hours, and the ratio test between inside and outside cannot tell a
stopped stove from an opened door. Under `rules` every alert is an event with a cooldown: an `alerts` row has no
notion of clearing. The dashboard marks
an open act-level alert as *current* only while its condition still holds (the house over the line, or the
alert under two hours old), and otherwise says the reading came back on its own and the alert is still open.

The event engine does clear, but its events are rows of their own, in `alert_events`. For the old alerts, what the
node has is the derived `measured` stage and `GET /effect`, which counts per rule how many acts were followed by
the condition stopping. No rule carries a `recovery` block.

## Reading them

`GET /alerts?limit=50` lists the most recent with `id, ts, rule_id, sensor_id, level, text, buttons, acted_at`, and is where
an alert's id comes from. `GET /actions` lists every answer with its stage, actor, note and `choice`, and answers only a
token or the machine itself, because a note is a household's own words about its own house; `GET
/actions?events=1` adds the answers given to events, with their `event_id`. `GET /issues` carries the events as
`events`: what is open, its action chosen from now, the message it sent, its latest answer, whether it is still
`asking`, and the alerts it covers. `planetai status` shows the last three alerts and ρ.

On the dashboard, Decide (What to do on the doors) draws each open event once, and each open alert on a node on `rules`. *What was asked,
and what was answered* is the record of what was sent and answered, and *What was decided, and by whom* is the
ledger of answers. The report's second part says, per room, where the window's act alerts stand now.

## Where this leads

The node can now ask. Next, choose where the asking reaches people: [Channels](channels.md) sets up Telegram, the
LoRa mesh, Reticulum and Home Assistant. Then [ρ](rho.md) is how the node measures whether the asking worked.
