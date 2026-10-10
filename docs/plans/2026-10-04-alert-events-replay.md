# Replay: node #1's month through both engines (4 October 2026)

The numbers for the shadow-mode decision (`docs/SPEC_alerts.md` §9). Both engines ran over the same readings:
today's heat and air-quality rules, and the event engine on branch `alert-events-engine-2026-10-04`. Nothing on the
node was changed. The readings stayed in a scratch directory outside the repository. Rooms are called Room A–D and
the two outdoor kits Outdoor 1 and 2. No sensor ids appear here.

## How it was run

- **Data.** `tools/fetch_replay.sh` (read-only: each `psql` session starts with
  `SET default_transaction_read_only = on`, and the only statements are `\copy (SELECT …) TO STDOUT`). It fetched
  31 days of temp, humidity and PM2.5 from the 26 `kind = 'sensor'` kits: 195,373 readings, 3 Sep 22:22 to
  4 Oct 22:19 local. It also fetched node #1's own `alerts` rows for the window (602 rows, used for calibration)
  and its `channel_roles`. The node's roles for every source in the fetch match `config/channels.yml`, which is
  what the replay uses.
- **Window.** 30 whole local days, 4 Sep 00:00 to 4 Oct 00:00 WITA, after a one-hour warm-up.
- **Settings** (node #1's own, except `ALERT_LEVEL`): quiet hours 22–06, `ALERT_LEVEL=warn`, `ALERT_MAX_PER_DAY=4`,
  `HOME_HAS=ac,purifier`. `ALERT_LEVEL=warn` for the whole month is an assumption: the settings history is not recorded. The coordinates are `NODE_LAT`/`NODE_LON` from the node's bootstrap settings, which
  `GET /settings` returns unmasked.
- `python3 tools/replay_alerts.py --data <scratch> --days 30 --quiet 22,6 --max-per-day 4 --alert-level warn
  --home-has ac,purifier --lat … --lon …`, with the default step of 5 minutes. It took **652 s**. The replay tool
  did not need a fix.
- **Not replayed:** `air-quality/inside_worse_ventilate` and `air-quality/outside_worse_keep_shut`. Both read
  `observations`, which the DuckDB replay does not have. The old side covers the heat and air-quality packs only.

## Calibration: the replayed old engine against what node #1 recorded

A real push is estimated the way `app/main.py` decides at `ALERT_LEVEL=warn`: an `act` row at any hour, or a `warn`
row outside 22:00–06:00. These counts cover heat/* and air-quality/* only.

| 30 days, heat + air | pushes | median/day | max/day | 22:00–06:00 |
|---|---|---|---|---|
| node #1, recorded | 361 | 12.5 | 27 | 19 |
| node #1, recorded, without the two rules the replay cannot run | 310 | 10.5 | 22 | 16 |
| replayed old engine | 284 | 9.0 | 19 | 11 |

The replay is 21% under the recorded total. Two causes explain about all of the gap, with small residuals (about +5 replayed air pushes before 8 Sep, −6 after):

1. **The two `observations` rules.** They made 51 pushes: `inside_worse_ventilate` 44 and `outside_worse_keep_shut` 7.
2. **The heat rule changed on 7 September** (`fd8b0c1`, "the heat rule fired on Kuta Selatan's ordinary weather"). From
   5 to 7 September node #1 ran the older, lower rule, and `heat_stress_now` fired 25 times. Today's rule does not fire
   on those days.

From 8 September, when node #1 ran the same rule text the replay runs, every rule matches:

| 8 Sep – 3 Oct, per rule | recorded | replayed |
|---|---|---|
| heat/heat_stress_now | 128 | 125 |
| air-quality/indoor_spike | 69 | 66 |
| air-quality/indoor_pm25_high | 44 | 42 |
| air-quality/outdoor_spike | 20 | 20 |
| air-quality/outdoor_pm25_high | 2 | 1 |
| **runnable rules, total** | **263** | **254 (−3.4%)** |
| runnable rules, 22:00–06:00 | 11 | 11 |

The old side is calibrated. The new side runs on the same rows, so its numbers below can be trusted.
(§1's "about 390, 13 a day, 23 at night" counts every pack. This table counts heat and air only.)

## The §9 table

| measure | old engine (replayed) | new engine | target | met? |
|---|---|---|---|---|
| pushes per day, median (max) | 9 (19) | **4 (9)** all pushes; **2 (5)** opens + escalates | ≤ 3 | **missed** counting all-clears; met for opens + escalates |
| pushes, total: opens + escalates / all-clears | 284 / 0 | 67 / 49 (116) | – | – |
| non-danger pushes 22:00–06:00 | 11 (recorded: 19) | **0** (no danger sent at night either) | 0 | **met** |
| events carrying contradictory advice | recorded: 43 of 44 "open a window" alerts fell within 60 min of a "keep shut / purifier" alert (`outside_worse_keep_shut` or `indoor_pm25_high`), in 26 distinct hours | **1** cross-issue pair within 60 min (example 3). No single message carries two opposite actions | 0 | **missed** (1) |
| "dangerously hot" with indoor air < 32 °C | **128 of 128** `heat_stress_now` pushes, on 28 of 30 days. Highest indoor air 31.6 °C, median feels-like 35.1 | **0**. No heat event reached `danger` | 0 | **met** |
| PM2.5 hourly rises > 10 µg/m³ caught | 36 of 38 rise-hours (recorded alerts: 37 of 38) | **36 of 38** rise-hours had an air event open. 33 of 38 were sent; 3 were held | all | **missed** (2) |
| sustained or unusual heat runs reported | – | 7 of 9 runs longer than the room's usual got a heat event; 12 of 15 heat events were sent once, 2 twice and 1 three times | every one, once | **missed** (2 runs; 3 events sent more than once) |
| bursts (3+ pushes in 60 min) | 30 bursts, 146 pushes | 2 bursts, 6 pushes | – | – |

Held by the new engine (not pushed): **quiet 10, ceiling 2, level 0**. Old per-day pushes ran from 1 to 19. New
per-day pushes ran from 0 to 9; the days with 7–9 are cooking days with a danger event plus its all-clear.

How the measures were counted:

- **Rises.** A rise is a local kit's hourly PM2.5 mean more than 10 above its previous hour. There were 65
  kit-hours in 38 distinct hours (§1 counted 31 on a different window). "Caught" means an air event was open
  between the start of that hour and 15 minutes after its end. For the same kit, 61 of 65 kit-hours were caught.
  The misses were rises from 7.6 to 20.2, 13.4 to 29.8, 12.8 to 26.4 and 5.1 to 15.3. All four ended under 30 µg/m³
  and under `air_spike`'s `p90 + 10`.
- **Heat runs.** A heat run is a stretch where an indoor kit's 15-minute feels-like stayed at 35 or above for at
  least 3 hours, broken by any bucket under 35. There were 36 such runs. "Longer than usual" compares each run with
  the room's usual hours at that point: hours whose p75 is 35 or more, over the 14 days before the run, as
  `heat_sustained` counts them. 9 runs were longer than usual. Of the 27 runs within the usual, 4 got an `unusual`
  event and 23 got nothing, by design. Room A's usual hot spell grows from 0 hours to 11 by the end of the month. Its sustained event therefore
  needs 12 hours.

## Ten example pairs

Each old line is the first line of the message (the full text is the rule's template). Each new message is shown in
full. Times are local.

**1. 22 Sep, cooking: 8 old pushes, 3 new.**
Old 12:25–12:30: three "😷 The air inside at Room B / Room A / Room C is unhealthy right now", three "📈🏠 Something
just changed the air at Room C / B / A", "📈🌫️ The outside air at Outdoor 2 just got worse", and "🥵 It is
dangerously hot at Room B: it feels like 35.2 °C".
New:
> 12:20 📈 The air jumped in Room B: 51.7 µg/m³ PM2.5. Outside is 17.1. 👉 Open the side where it started and run the purifier for 30 min: outside is cleaner (17.1).
> 12:25 🚨😷 DANGER: the air in Room B, Room C is very unhealthy: 209.8 µg/m³ PM2.5. 👉 (same)
> 12:30 🚨😷 DANGER: the air in Room A, Room B, Room C, Outdoor 2 is very unhealthy: 1033.5 µg/m³ PM2.5. 👉 (same, "outside is cleaner (26.4)")

This is one of the two new bursts. Danger escalates on value at every step. The last message says "outside is
cleaner" while an outdoor kit inside the same event reads 1033.

**2. 15 Sep morning: 7 old pushes, 1 new.**
Old 08:25–09:10: two "Something just changed the air" (Room B, Room A, then Room C at 09:10), two "The outside air
at Outdoor 2 / Outdoor 1 just got worse", and two "The air inside at Room B / Room A is unhealthy right now".
New:
> 08:25 📈 The air jumped in Outdoor 2: 76.8 µg/m³ PM2.5. Outside is 20.2. 👉 Keep windows and doors shut and run the purifier until outside clears.

**3. 11 Sep: 6 old pushes, 2 new, with opposite advice 35 minutes apart.**
Old 10:55–11:05: three "The air inside … is unhealthy", three "Something just changed the air".
New:
> 10:55 🚨😷 DANGER: the air in Room B, Room C is very unhealthy: 233.8 µg/m³ PM2.5. 👉 Open the side where it started and run the purifier for 30 min: outside is cleaner (13.8).
> 11:30 🌡️ Hotter than usual in Room D: it feels like 31.1 °C, well above this room's normal for the hour. 👉 Keep it shut and shaded: outside (29.7 °C) is hotter than inside for now.

Room D's temperature channel is declared `enclosure` on node #1, not `ambient`.

**4. 17 Sep, cooking: 7 old pushes, 3 new.**
Old 12:45–13:45: five air messages across Rooms A–C, and "It is dangerously hot at Room A: 35.8 °C" and "… at
Room B: 35.1 °C".
New:
> 12:45 📈 The air jumped in Room B: 25.9 µg/m³ PM2.5. Outside is 5.7. 👉 Open the side where it started and run the purifier for 30 min: outside is cleaner (5.7).
> 12:50 🚨😷 DANGER: the air in Room B, Room C is very unhealthy: 244.8 µg/m³ PM2.5. 👉 (same)
> 14:15 ✅ The air in Room B, Room C is back to normal.

**5. 20 Sep: 7 old pushes, 1 new.**
Old 13:30–14:10: five air messages across Rooms A–C, and two "It is dangerously hot" (Room A 35.3, Room B 35.1).
New:
> 13:30 📈 The air jumped in Room B: 63.0 µg/m³ PM2.5. Outside is 8.0. 👉 Open the side where it started and run the purifier for 30 min: outside is cleaner (8.0).

**6. 27 Sep, outdoor smoke: 6 old pushes, 1 new.**
Old 06:30–07:20: "The outside air at Outdoor 2 / Outdoor 1 / a nearby station just got worse", "The air inside at
Room B is unhealthy", "Something just changed the air at Room B", and "🌫️🚨 The air outside at Outdoor 2 is
unhealthy for everyone".
New:
> 06:20 📈 The air jumped in Outdoor 1, Outdoor 2: 44.0 µg/m³ PM2.5. Outside is 24.2. 👉 Keep windows and doors shut and run the purifier until outside clears.

**7. 13 Sep, 01:40: 1 old push at night, none new.**
Old: "🥵 It is dangerously hot at Room A: it feels like 35.0 °C." It was act level, so it went out in quiet hours.
New: nothing. Room A at 35.0 is within its usual for 01:00.

**8. 13 Sep afternoon: 2 old pushes, 1 new.**
Old 16:35 and 16:40: "It is dangerously hot at Room B: 35.4 °C" and "… at Room A: 36.4 °C".
New:
> 16:50 🥵 Room A, Room B, Room C, Room D has been hot for hours: it feels like 36.8 °C, longer than this room usually stays there. 👉 Keep it shut and shaded: outside (30.4 °C) is hotter than inside for now.
> 19:45 ✅ Room A, Room B, Room C, Room D has cooled back to its usual.

**9. 28 Sep, cooking: 6 old pushes, 2 new.**
Old 10:00–10:45: five air messages across Rooms A–C, and "It is dangerously hot at Room A: 35.0 °C".
New:
> 10:00 📈 The air jumped in Room B: 79.7 µg/m³ PM2.5. Outside is 17.0. 👉 Open the side where it started and run the purifier for 30 min: outside is cleaner (17.0).
> 10:05 🚨😷 DANGER: the air in Room A, Room B, Room C is very unhealthy: 196.0 µg/m³ PM2.5. 👉 (same)

**10. 24 Sep, 22:55: an all-clear held for quiet hours.**
Old: nothing. New, held (quiet): "✅ Room B, Room C has cooled back to its usual." It waits for the first report
after 06:00.

## Recommendations: starting values and design (none applied here)

Each change below needs a re-run of the replay. The targets stay as they are.

1. **All-clears are 49 of 116 pushes (42%).** They are why the median is 4 and not 2. Push an all-clear only for
   `danger` and `sustained` events, and fold the rest into the next report. Or count all-clears against
   `ALERT_MAX_PER_DAY`. This is a change to the clear path in `app/events.py`. With either change the median falls
   to 2–3.
2. **Danger re-sends on value every 5 minutes.** There were 16 danger sends: 7 opens and 9 escalations. Some came
   one step apart: 12:25 and 12:30 on 22 Sep, 07:50 and 07:55 on 18 Sep. Raise `ESCALATE_STEP["air"]` for danger
   (25 → about 100, or a ratio such as ×2), or apply a short gap of about 30 minutes to danger escalations on value.
   Escalations on kind would stay immediate. Direction: fewer.
3. **`air_extreme` fires on every big cooking peak.** There were 14 danger events, all in the daytime, with peaks
   from 131 to 1033. Seven opened as a spike and became danger 5–15 minutes later, which made 2 pushes per cooking
   event. Require the 125.5 line to hold for 2 buckets (30 min) before an event becomes `danger`. Direction: longer,
   not lower.
4. **PM2.5 rises missed (2 of 38 hours).** All four missed kit-hours ended under 30 µg/m³. To catch every rise,
   lower `air_spike`'s usual margin from `p90 + 10` to `p90 + 5`, or drop the p90 condition for indoor kits.
   Direction: down. This costs some events; the re-run will say how many.
5. **Heat rules read an enclosure temperature.** 4 of 15 heat events included Room D, 2 of them Room D alone. Room
   D's temperature channel is declared `enclosure`. The kinded heat rules should keep only `ambient` temperature
   channels (`channel_roles`), as the action context already does. This is a fix to the rule SQL, not a threshold.
6. **`heat_sustained` measures a run against a usual that already contains it.** `usual_by_hour` covers the last
   14 days including today, so on a node with little history a long run raises its own bar. The two missed runs
   were Room A on 4 Sep (6.8 h) and 8 Sep (5.8 h), in the first five days of data. Count the usual from the days
   before today, or use the fixed 3 h until 7 days of history exist.
7. **Opposite advice across issues (1 case).** An air event said "open the side … run the purifier", and a heat event
   said "keep it shut and shaded" 35 minutes later. The action choice should see the other open event: while air is
   open with a ventilate action, heat should use `heat/water_and_rest`, or the reverse. Three heat events also changed
   between shut (day) and open (night) across their own messages. Those changes were hours apart and followed
   conditions, so they are not counted as contradictions.
8. **"Outside" in the air message is an hourly mean of the outdoor kits.** In example 1 it said 26.4 while one outdoor
   kit in the same event read 1033. When an outdoor kit is in the event, the advice should not be "outside is
   cleaner".
9. **Copy.** "Room A, Room B, Room C, Room D has been hot … longer than this room usually stays there" needs a plural
   form. Two heat events stayed open more than 24 hours (the longer one 53 h). Consider a daily boundary.

## Shadow mode

The new engine meets three targets on node #1's month: no non-danger pushes at night, no "dangerously hot" below
32 °C, and pushes at a median of 2 a day excluding all-clears (4 including them). It cuts bursts from 30 to 2. It misses on all-clear volume,
one cross-issue contradiction, 2 of 38 PM2.5 rise-hours, and 2 of 9 long heat runs.

Shadow mode sends nothing. It would record how these rules behave on live data while recommendations 1–7 are made
and replayed. Moving node #1 to `events` should wait until the re-run meets every target. Both decisions are
Tomas's.

## Addendum, 5 Oct 2026: three rule fixes, re-replayed

The three changes the recommendations above put first:
- **Box temperature:** the kinded heat rules read room air only, so a sensor whose `temp` channel is declared
  non-ambient (Room D's radio box) is never a room.
- **Usual excludes today:** `usual_by_hour` is the fourteen complete local days before today.
- **Danger repeats:** a danger already sent repeats only when its value doubles (air), or rises by `ESCALATE_STEP`
  (heat), and never within 30 minutes. Climbing into danger still sends at once.

The same 30 days, the same settings:

| measure | before | after |
|---|---|---|
| heat events that include Room D | 4 of 15 | 0 of 16 |
| long heat runs reported (longer than the room's usual) | 7 of 9 | 9 of 9 |
| air danger messages | 16 | 14 |
| pushes, total (openings and escalations / all-clears) | 116 (67 / 49) | 116 (66 / 50) |
| pushes per day, median / max | 4 / 9 | 4 / 9 |
| non-danger pushes 22:00–06:00 | 0 | 0 |
| bursts of 3 or more within 60 min | 2 | 1 |

Of the 16 danger messages before, 7 were events climbing *into* danger, which is meant to send at once. Only 2 were
true repeats, so the cooking-peak re-sending was smaller than the text above suggests. The total is unchanged because
the two long heat runs that were hidden are now reported, while Room D's events and the danger repeats are gone.

Still open from the targets: 4 a day once all-clears are counted, the one cross-issue pair (air "open up", heat "keep
shut" 35 minutes later) and 2 of 38 PM2.5 rises.
