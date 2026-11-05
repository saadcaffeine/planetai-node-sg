# SPEC: Next days

Status: design approved by Tomas, 3 Nov 2026. Not built. Piece 1 of three agreed with Tomas on 3 Nov: (1) the stored future and a Next
days view on Now, (2) hazard outlooks for storm, flood and fire, (3) correlations between indicators that are not
usually read together. Pieces 2 and 3 read what this one stores. They get their own specs.

## 1. Why

Tomas, 3 Nov: the node should help make future decisions, "storms coming, risk of flood, fire (if too dry for too
long)", "a climate intelligence machine". Now answers what is happening. Nothing on the page answers what is coming,
although the node already asks several models about the next day and throws most of the answer away.

Tomas, 3 Nov, on what makes it worth having: "I dont want to replicate a home weather station, or an existing app,
it is the amount of data that the node process that makes it interesting." A forecast app already shows tomorrow's
temperature. Next days earns its place by putting the forecasts beside what only this node holds: its own sensors'
usual hours, the issues' lines, the fires around it, the water on its land, the surf at its spots, and later the
crops, the orchard and the panels on its roof. And it reads the node's whole territory at the node's scale, not one
point.

The first decisions it serves are the household's own, a day or two ahead: whether to surf tomorrow, whether the air
will be bad tonight, whether the heat will peak, whether to bring things in before wind and rain.

## 2. Goals, non-goals, anti-goals

Goals
- The node keeps the next 72 hours from every model it already reads, and a newer forecast replaces an older one for
  the same hour.
- Now has a Next days part. It shows today (the rest of it), tomorrow and the day after, one row per
  thing the node watches, with the day's number, a word for its state against the issue's own line where it has
  one, and where the number comes from.
- A pack can put its own line in Next days (surf: tomorrow's spots and windows).
- Docs and the public site say what it is (standing rule of 24 Oct).

Non-goals
- Hazard outlooks (storm, flood, fire), levels, and any alert. That is piece 2, and so is the question of whether a
  forecast may ever reach a phone.
- Correlations (piece 3). Scoring how good past forecasts were.
- Forecasts beyond 72 hours. A new forecast source.

Anti-goals
- A forecast read as a measurement. Every forecast number says it comes from a model and which one, and never feeds
  a cell, the Index, `recent_15m`, `/issues`'s live values, the report's measured figures or rho.
- A forecast that sends anything. The forecast pack's rule stands: it fetches, it does not predict, it never sends
  (docs: packs/forecast/README.md, tests/test_forecast.py).
- A blank switch. Where a source is off or has no rows, the row says so in one line.

## 3. What the node keeps

### Territory and scale

A node has a scale (home, community, city, region; `NODE_SCALE` and its H3 cells). The forecasts are fetched for
the node's territory at that scale:

- home: the node's point, as today;
- community and larger: a grid over the node's own cells, in one multi-location request per source, the way the
  wind field already asks for 65 points in one call. Each grid point is a sensor (`forecast-om-<cell>` and so on)
  tagged with its H3 cell, so pieces 2 and 3 can ask "where in this territory" and not only "how much".

The view (§5) reads a territory the same way Now does: the value at the node's own cell first, and for a larger node
the worst cell and how much of the area is over the line ("over in 7 of 20 cells"). A cell here is a distinct model
grid point, the place Open-Meteo answered from, not a sensor: res-7 neighbours are ~2.5 km apart and the models are
10 to 44 km, so several sensors often share one point. `cells` and `cells_over` show only with two or more points. Node #1 is a community node
(`NODE_SCALE=community`; the valid values are community, city and region, default community), so it fetches the
7-point grid for Open-Meteo and CAMS. Open-Meteo counts each location as a call, so a 19-point city or region node
asks for 38 locations a poll for the weather and the air, about 150 a day at four polls, beside the 65-point wind
field and one point of sea. On node #1 (3 Nov) all 7 points of each answered from a single model cell.

### What it keeps, per source

All forecast data lives in the `forecast` pack (core, can be off), under `fc_` metrics, as future-timestamped rows,
which is how BMKG and Open-Meteo forecasts are kept today.

| sensor | from | metrics | every |
|---|---|---|---|
| `forecast-bmkg` (exists) | BMKG, 3-hourly | fc_temp, fc_humidity, fc_wind_speed, fc_wind_direction, fc_cloud, fc_rain | 6 h |
| `forecast-om` (exists) | Open-Meteo forecast, hourly | as today + fc_wind_gusts, fc_rain_prob, fc_shortwave, fc_et0, fc_soil_moisture | 6 h |
| `forecast-cams` (new) | Open-Meteo air quality (CAMS), hourly | fc_pm25, fc_uv | 6 h |
| `forecast-marine` (new) | Open-Meteo marine, hourly, at the sea point `coast` already snaps to | fc_wave_m, fc_swell_m, fc_swell_s, fc_swell_dir | 6 h, only while `coast` is on |

- `fc_shortwave` (solar radiation), `fc_et0` (evapotranspiration) and `fc_soil_moisture` are stored and not drawn
  yet. They are what a solar pack, an orchard or garden pack, crop cycles at community and region scale, and the
  fire and flood outlooks of piece 2 will read, and keeping them costs nothing: they ride in the same call.
- Horizon: 72 hours (`HOURS = 72`; the comments that already say "up to 48 h" are corrected). BMKG keeps what it
  publishes inside that.
- Open-Meteo's free tier is non-commercial, and the pack says using it is the operator's decision, so the three
  Open-Meteo forecasts are opt-in behind the existing `FORECAST_OPENMETEO` (§10). On node #1 they are on. Open-Meteo
  counts every location as a call, and a community node with Open-Meteo and the coast pack on asks, per due poll, 7
  locations for the weather, 65 for the wind field, 7 for the air and 1 for the sea. At four polls a day that is
  4 × (7 + 65 + 7 + 1) = 320 location-calls a day against the 10,000 per IP that node #1 already strains; the wind
  field is most of it and is unchanged here.
- `fc_lead_hours` stays, per source, and the new sources store it too.
- `channels.yml` declares every new metric the way the existing `fc_` ones are: `role: derived, comparable: false`,
  with units (my call, builder check: there is no `model` role and adding one touches core classification).
- Each source keeps its own stamp (the wind field too, `forecast.wind.last`), so one refused call (a 429) does not hold
  the others for six hours (my call). The stamp is written before the request, as the 30-minute retry mark, and
  replaced by the full wait once the source answered: an `out/` that cannot be written then stops the fetch before
  anything is asked, and never leaves a source due again on the next 300 s poll.

### Revisions

`readings` is `UNIQUE (sensor_id, metric, ts)` with `ON CONFLICT DO NOTHING`, so today the first forecast stored for
an hour wins and every later issue for that hour is dropped. From now on a row whose `ts` is in the future replaces
the stored value for that key (`ON CONFLICT … DO UPDATE SET value = EXCLUDED.value` when `EXCLUDED.ts > now()`). A row
at or before now keeps first-wins, so nothing about measured data changes. The rule is narrower than "any future
row": it applies only to `fc_` metrics (`EXCLUDED.metric LIKE 'fc\_%' AND EXCLUDED.ts > now()`), so a device whose
clock runs ahead never overwrites a measurement. It goes into one shared insert helper used by the poll insert and
`packs/forecast/fetch.py`; the MQTT, `/readings` and bootstrap paths store measurements and keep `DO NOTHING`
(my call, builder check).

### Keeping the future out of now

The `observations` view takes each sensor's newest row with no upper bound, so for a forecast sensor it returns the
furthest future hour (docs/SPEC_alerts.md says so). It gets `ts <= now()`, like `recent_15m`. Every reader of
`observations` is checked for a forecast sensor it meant to read ahead, and the list goes in the PR.

## 4. What the page reads

`GET /forecast` (packs/forecast/routes.py) grows. `hours` accepts up to 72 (it already does). The answer keeps
`point`, `sources`, `hours`, `attribution` and `far_from_node`, and adds `days`:

```json
"days": [
  {"date": "2026-11-03", "part": "rest", "rows": {
     "air":  {"value": 18, "unit": "µg/m³", "metric": "fc_pm25", "of": "mean", "peak": 31, "peak_at": "20:00",
              "source": "forecast-cams", "line": 15, "state": "over", "hours_over": 5},
     "heat": {"value": 36, "unit": "°C", "metric": "apparent", "of": "max", "source": "forecast-om",
              "line": 35, "state": "over", "hours_over": 3},
     "wind_rain": {"gust": 38, "rain_mm": 12, "rain_hours": "15:00–18:00", "source": "forecast-om"},
     "sea":  {"value": 1.4, "unit": "m", "metric": "fc_wave_m", "of": "max", "source": "forecast-marine"}}},
  {"date": "2026-11-04", "part": "day", "rows": {…}},
  {"date": "2026-11-05", "part": "day", "rows": {…}}
],
"lines": [ {"pack": "surf", "title": {…}, "days": {"2026-11-04": {…}, "2026-11-05": {…}}} ]
```

- Days are local (NODE_TZ). Today is from the next whole hour to midnight.
- Air and heat take their line, unit, margin and state words (over, near, under) from their issue, through the
  engine's own comparison, so the two views cannot disagree about what "over" means (my call, builder check).
  - Air: the line is a 24-hour mean (WHO 15), so the day's value is the mean of its hours, with the peak hour beside
    it. `hours_over` counts the hours above the line, and `n` the hours the value covers: a 3-hourly source (BMKG)
    counts each value as 3 hours, an hourly one as 1.
  - Heat: the line is on `apparent` as the heat issue computes it (Steadman's form from temperature and humidity,
    35 °C). The route computes it the same way from `fc_temp` and `fc_humidity` with the engine's own function,
    and the day's value is its maximum. Open-Meteo's own apparent temperature includes wind and sun and is not
    stored (the engine already warns against mixing the two).
- Wind and rain have no line (piece 2 decides one): gust is the day's highest, rain the day's total and the hours it
  is most likely.
- A row whose issue or source is off is left out of `rows`. A day with no rows for a source says so in `sources`.
- Where two sources give the same thing (BMKG and Open-Meteo temperature), the row uses Open-Meteo for hourly detail
  and the answer names the other in `also`. `forecast-gap` stays as it is.
- The answer is a new wire contract, `forecast-v0`, beside the others in `tests/data/wire/`. `tools/check_wire.py` pins its top-level keys
  (it reads `app/`; extend it to read `packs/forecast/routes.py` or move the builder into a function it can read),
  and a test pins the nested `days` and `lines` fields (my call, builder check).
- Shared at the same `SHARE_LEVEL` as `/forecast` today.

### A pack's line

A pack can add one line to Next days in its `pack.yaml`:

```yaml
ahead:
  id: surf
  title: { en: Surf, es: Olas, id: Ombak }
  sensor: surf                 # the sensor whose meta holds the text
  days: [ahead_en_d1, ahead_en_d2]   # meta keys for tomorrow and the day after, per locale (_en, _es, _id)
```

The node fills in the locale suffix itself (`ahead_<locale>_d1`, `_d2` for en, es and id), reads those meta keys of
that sensor's latest fetch, and serves all three locales in `lines` so the page picks its own. It serves them only
while the pack is on and the meta's `fetched` is today in NODE_TZ, so `_d1` is always tomorrow. The wild-packs
repo's registry check must accept `ahead:`, a small PR there; surf's `requires` floor is the same
release. The text is the pack's, at most 160 characters a day, escaped, with
no markup. Surf writes `ahead_<locale>_d1` and `_d2` as a short line, "Uluwatu 16:00–18:00 · Impossibles 16:00–18:00",
or "nothing looks good". `docs/PACKS.md` documents `ahead:` next to `sections:`.

## 5. The view

- A part of Now, under What to do, headed "Next days" and drawn with the rest of Now. `#now/next` scrolls to it so
  it can be linked. Until 4 Nov this was a switch at the top of Now, "Now · Next days"; Tomas found it read as a
  second tab bar under the doors, so the switch and the choice the browser kept are gone. The doors' own phone layout
  (≤480 px) gets it with the rest of Now. The separate phone page (`mobile.html`) gets it in a follow-up, after the
  doors version has run on node #1 (my call, builder check).
- Next days is one row card per thing, in the order of Now's rows (air, heat), then wind and rain, then the sea, then
  pack lines. Three columns: Today (rest), Tomorrow, the day after, headed by weekday and date.
- A cell holds the day's number with its unit and `data-num`, the state word against the line (in ink, never by
  hue), and for air and heat the hours over the line ("5 h over 15"). Wind and rain read "gusts 38 km/h · 12 mm,
  most 15:00–18:00". The sea reads "waves 1.4 m".
- Pressing a row draws its 72 hours as a series card under it, with the line, and a "now" mark at the left.
- Under the rows, one line of provenance per source, as pills: "BMKG, issued 06:00", "Open-Meteo, fetched 08:12",
  "CAMS", "Open-Meteo Marine", and "10 km from this node" where `far_from_node` says so, and for the sea where its own source's `km_from_node` does
  (the sea is never in `far_from_node`, which the classic card reads as the weather point). Then one sentence: these
  come from models, the node does not forecast, and they never send anything.
- With the forecast pack off, Next days shows one line and a link to Set up to turn it on.
- Card kinds, signs, theme and every rule the visual gate measures apply. Nothing new in the frozen layer.

## 6. Tests and proof

- Revisions: a future row replaces, a past row is kept, in a test against the insert function and in the scratch
  PostGIS proof.
- `observations` with a future row returns the latest past one.
- The forecast adapters: 72 h kept, the new sources' variables and units, the throttle unchanged, each fetch is one
  call.
- `/forecast` days: local-day cuts in Asia/Makassar, rest-of-today, max and totals, hours over the line taken from
  the issue, a missing source left out. Wire contract.
- `ahead:` validation (missing keys, too long, a pack off, a stale `fetched`).
- The doors switch and the cells, with the existing doors test style; the visual gate run locally at 390 and 1440,
  paper and dark.
- Node #1 on the branch: a real 6-hourly fetch, the view on the doors and the phone, surf's line from the surf pack.

## 7. Docs and visibility

`docs/site/` gets a page "Next days" (what it shows, where each number comes from, that it never sends), in NAV, and
the site is rebuilt and deployed after release. `docs/PACKS.md` documents `ahead:`. The forecast pack's README is
updated for the new sources and the 72 hours. CHANGELOG.

## 8. What this must serve later

Not built here; named so this piece stores what they will need:
- piece 2, outlooks: storm (gusts, rain rate), flood (rain over days against the terrain pack's water and soil
  moisture), fire (days since rain, humidity, wind, evapotranspiration, FIRMS hotspots);
- piece 3, correlations across everything the node holds, by cell;
- packs Tomas named on 3 Nov: home energy (solar production against `fc_shortwave`), a home orchard or garden, and
  crop and harvest cycles at community, city and region scale.

## 9. Calls made at the builder check

Marked "(my call, builder check)" above: `derived` role, per-source stamps, the narrow revision rule, air as a daily
mean and heat as computed apparent through the engine's own comparison, the wire check, the `ahead:` locale and date
rules, and the phone page later.

## 10. Tomas's call

Decided 3 Nov ("Approve, opt-in only"): the Open-Meteo forecasts (weather, CAMS air, marine) stay off by default,
as `FORECAST_OPENMETEO=0` is today; one switch turns all three on, in Set up and in `.env`. Node #1 turns it on. With
it off, Next days shows what BMKG gives (weather only, where BMKG covers the node) and one line saying the rest is off
and where to turn it on. Their free tier is non-commercial, and using it is the operator's decision.

## 11. Left to the builder

- How the adapters share the Open-Meteo call code.
- The exact `days` field names beyond those shown, as long as the wire contract pins them.
- Layout details inside the doors design and the visual gate.
- The surf pack's `ahead_*` meta wording, in the pack's existing register.
