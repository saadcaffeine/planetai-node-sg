# heat

Turns the temperature and humidity the node already stores into three sentences about heat, and one Index cell.

**Written for Kuta Selatan, Bali** — a humid tropical house, 8°S, sea level, roughly 26–31 °C and 50–75% RH all year.
Every threshold below is that place's. A temperate node must move them; see the last section.

**What it adds**
- `heat_stress_now` — apparent temperature ≥ 35 °C at any local sensor (Steadman, no-wind form). Act-level: what to
  do, and who to check on.
- `heat_danger` — ≥ 40 °C apparent. Heatstroke territory.
- `night_no_relief` — overnight indoor minimum above 28 °C, the WHO ceiling for restorative sleep. Once a day,
  ending in the only thing that helps long-term: shade or airflow, not a bigger fan.
- `Social|Community` — hours per sensor in the last 30 days with indoor apparent temperature ≥ 32 °C. The Social
  column of the Index is empty across the whole registry; this is one number for it. 32 is right for a count of
  exposure, which is what a cell is; it is wrong for an interruption, which is what a rule is.

**Where the numbers come from.** Steadman's apparent temperature as published by the Australian Bureau of
Meteorology (AT = T + 0.33·e − 4.0, e in hPa). The no-wind form fits indoors. 40 °C is the heat-index "danger"
line and 28 °C overnight is WHO's; both are other people's numbers, not ours.

**35 °C is ours, and it is measured, not chosen.** `heat_stress_now` shipped at 32 °C — the bottom of the
heat-index "extreme caution" band. In Kuta Selatan that whole band is the baseline. Node #1 (bayu-2), 2–7 September
2026, its own two reporting local sensors:

| | indoor AT | median | p90 | max | share of time ≥ 32 °C | lowest reading |
|---|---|---|---|---|---|---|
| `sc-19880` | the hot room | 33.6 °C | 35.7 °C | 36.5 °C | 86% | 28.7 °C |
| `sc-19849` | the cooler room | 31.8 °C | 33.7 °C | 34.2 °C | 43% | 30.8 °C |

The hot room was above 32 °C in *every* hour of the day, coolest hour included: at 04:00 its mean AT was 33 °C. A
line at 32 fired 20 times in 48 hours, ten of them between 22:00 and 06:00, and act-level alerts are the ones that
ignore quiet hours. 35 °C is the hot room's p90: above every overnight minimum and above an ordinary afternoon,
reached on the hot days only. Over the same record it fires eight times in five days, none of them at night, and
nothing at all on the two days the weather eased.

**Why it is the threshold and not the cooldown, the trend or a duration.** All four were measured against the same
record, replaying the rule's real per-sensor cooldown:

| change | fires in 5 days | why not |
|---|---|---|
| threshold 32 → 35 °C | 36 → **8** | this one. Moves the line above the baseline. |
| duration: 4 readings in a row over 32 | 36 → 36 | no effect whatsoever. The house is over 32 continuously; a duration gate suppresses spikes, and this is not a spike. |
| require AT rising by 1 °C or more in the hour | 36 → 19 | fires on the ordinary morning warm-up every day, and goes silent on a flat hot night — the case that actually hurts people. |
| cooldown 240 → 1440 min | 36 → 8 | same count as the threshold fix, but every one of the eight is still a false alarm. It rations the wrong signal instead of correcting it. |

At 35 °C the cooldown stopped mattering in that week (8 fires at 240 min, 7 at 360), so it stayed at 240.

**October 2026: the line held, the repeats did not (14 Oct).** Thirty days later the same line meant something
else. The hot room's median AT was 34.7 °C, its p90 36.7, and it felt 35 °C or more in 44% of all hours; the cooler
room 16%. The rule fired 171 times in 30 days across three rooms, 5.7 a day, 21 at night, and two were acted on
(the node's own learning, SPEC_learn step 2). Replaying the last 30 days of hourly AT with the per-room cooldown:

| line | cooldown | fires in 30 days | a day | at night |
|---|---|---|---|---|
| 35 °C | 240 min | 138 | 4.6 | 14 |
| 35 °C | **1440 min** | **56** | **1.9** | **0** |
| 36 °C | 240 min | 65 | 2.2 | 3 |
| 36 °C | 1440 min | 32 | 1.1 | 0 |
| 37 °C | 240 min | 17 | 0.6 | 0 |

(Hourly means, so a little under what the 15-minute rule sees.) The September argument was that a cooldown rations a
wrong signal. In October the signal is right: the hot room is genuinely over the line for hours on end, and raising
the line to the new p90 would call a sustained exposure normal. What was wrong is the repetition: the same true
sentence every four hours, including at night, which is how an alert becomes background. So the line stays at 35
and the cooldown becomes 1440 minutes, once a room a day. `heat_danger` (40 °C, 120 minutes) still interrupts as
often as it must. A node on `ALERT_ENGINE=events` already sends one message per episode and is unchanged; this
matters to nodes on `rules`, the default.

**What it assumes.** A local sensor reporting both `temp` and `humidity` (Smart Citizen, AirGradient, and a BME680
on a Tracker all do). Indoor for all of it. The night rule, the cell and the stress rules all read local indoor
sensors, because the no-wind Steadman form is the indoor form and the apparent-temperature line was measured
indoors. A node whose only local sensors are outdoors gets no heat alerts, which is the right answer rather than
a wrong number.

**What it does not know.** Radiant heat (a tin roof at 14:00) and airflow (a fan on you). Apparent temperature
underestimates the first and ignores the second. It is a floor, not a full comfort model. And the calibration above
rests on five days of one dry-season week at one house, two sensors, with a maximum AT of 36.5 °C — there is no
genuine heat event in it. It sets the line above the normal; it has not yet been tested against the abnormal.

**Moving it for your place.** One number, the `>= 35` in `heat_stress_now`. Take a week of your own `temp` and
`humidity`, compute AT, and put the line near the 90th percentile of your hottest indoor sensor — high enough that
an ordinary night is under it. In a temperate flat that lands back near 32 °C, which is why the pack shipped there.
A Balinese kitchen and a Barcelona flat do not share a comfort line.
