# insight

Three rules that turn the node's own history into sentences. No Python: Postgres has `corr()` built in.

**`digest`**, in every report — inside, outside, model, 24h mean and peak, trend. Not an alert since v0.37:
`contributes: report` puts its numbers in each report under `digest` in the bundle, so its cadence is the
report's (`REPORT_EVERY`).

**`agreement`**, daily — Pearson r between indoor and outdoor, outdoor and the CAMS model, indoor and the model;
how much of the street the house holds back; the model's bias. Needs 48 overlapping hours.

**`rhythm`**, daily — the street's worst and cleanest hours this week, local time, checked against the one thing
that can say why: the street's own noise. It needs a local outdoor noise sensor and stays silent without one — see
below.

**Where the numbers came from.** Written against seven days at Kuta Selatan, 5 September 2026, from six Smart Citizen
kits in one account plus CAMS: indoor tracks outdoor at r = 0.55 with the house filtering ~30%; two indoor kits agree
at r = 0.73; the model tracks the street at r = 0.51 and reads 2–3 µg/m³ high, overstating peaks by ~60%; the model
tracks indoor air at r = −0.18. The street peaked at 18:00 and 06:00 WITA; the model was flat all day.

**These pooled figures are dated 5 September 2026 and are kept for the record, not as current guidance.** The
r = 0.55 above is a pooled figure: every indoor kit averaged together, every outdoor sensor averaged together,
then the two averages correlated. It is not a reading of any one house against any one street.

Measured pairwise instead, `sc-19880` (indoor, Kuta Selatan, -8.8271, 115.15709) against `sc-19874` (outdoor,
Ungasan, -8.82008, 115.16669) gives r = 0.20 over 134 overlapping hours for the same seven-day window. The two
sites are 1.3 km apart — one house against one street, a different question from the pooled figure, not a smaller
version of it.

A pooled figure can move that far from a pairwise one because of what sits inside the pool. `sc-19849` shares its
coordinates exactly with two other indoor kits, `sc-19880` and `sc-19897` — 0 m apart, same room — yet reads about
1.5x either of them there, measured ratios 1.508 and 1.426. Its coverage also comes and goes, so the indoor
average moves when it reconnects, not when the air changes. Prefer the pairwise figure; the paragraph above stays
as the record of what the pack originally shipped with and why it changed.

**Why `rhythm` no longer blames traffic.** The rule used to end "that is the burning and the traffic, not the
weather" — an evening PM2.5 peak, so traffic felt like the obvious other half. `sc-19236`, the one kit in the fleet
with a noise sensor, said otherwise once anyone read it: it sits 250 m from the node, local under both the 500 m
default and the 1500 m radius node #1's operator has chosen. Over the same seven days its hour-of-day means show
the street loudest across the late morning and afternoon and at its quietest overnight. PM2.5 has two peaks over
the same week: 18:00 (14.7 µg/m³) and a smaller one at 06:00-07:00 (10.0-10.5 µg/m³) — the loud hours are the
clean hours. Pearson r between PM2.5 and noise across 169 hourly buckets is negative.

The 06:00-07:00 peak is consistent with the 9 am burn peak `docs/sensors.md` already documents for Bali — the
timing lines up, though that document is about the UTC/local day boundary, not about this node. The 18:00 peak is
not covered by `docs/sensors.md` at all: it is this node's own finding, supported by its own noise and light
channels. See `docs/archive/reviews/INSIGHTS_DESIGN_2026-09.md` for the readings behind it. An evening pollution peak
arriving as the street quiets down and the light goes is not what traffic looks like. `rhythm` now says that and
stops naming a cause its own data argued against.

**A node with no local outdoor noise sensor gets no `rhythm` alert.** The SQL cross-joins a `loud` CTE built from
local outdoor noise readings; with none, that CTE is empty and the whole rule returns nothing. That is deliberate.
The old rule asserted a cause with no evidence for it in either direction — no message is better than a wrong one.
