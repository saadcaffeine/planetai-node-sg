# forecast

**What it adds:** the next 72 hours of weather for the node's ground, from the meteorological agency that covers it,
and with Open-Meteo on, the air too, and the sea while the `coast` pack is on. Now draws them under Next days
([docs/site/next-days.md](../../docs/site/next-days.md)). It answers the question that follows "is the air bad": is it
arriving or leaving. A reading of 40 µg/m³ with the wind turning offshore and rain at four means something different
from the same 40 with still air all night.

**It fetches. It does not predict.** Forecasting is the upstream tiers' job. This pack asks BMKG and Open-Meteo
what they already published, stores it beside the node's own readings, and stops.

## It never sends anything

One rule, `ahead`, with `contributes: report` and no message. It gives the daily report one line: where the wind
is coming from and when rain is expected. Nothing here can reach a phone.

That is deliberate and it is the whole design. On 7 September three wrong warnings reached node #1's Telegram at
21:17. A forecast pack that starts talking is the next batch of them: forecasts are wrong often, they are wrong
about the next day rather than about right now, and there is no action a household takes at 9pm because of rain
predicted for tomorrow that it would not take by looking out of the window. `tests/test_forecast.py` fails if any
rule here grows a level or a message.

**No cell, either.** A forecast is not measured here and is nobody's Index cell.

## The point, and proving it is this one

BMKG is addressed by `adm4`, a Permendagri 100.1.1-6117/2022 village code. Six digits of opaque: the only check
worth anything is where BMKG says the code is.

For node #1 it is **`51.03.05.2002`** — Bali / Badung / **Kuta Selatan / Ungasan**, −8.82548 / 115.15773, which
is **194 m** from the node. Note that Kuta Selatan is `51.03.05`, not `51.03.01`; `51.03.01` is Kuta, and its
nearest desa is 7 km away up the isthmus.

`planetai run forecast verify` resolves whatever code you set, prints the province, regency, district and village
it belongs to, and the distance from this node. Past 10 km the card says so on its face: a forecast for another
place is still a forecast, but it is not this address's.

BMKG allows 60 requests a minute per IP and it enforces it — finding the code above cost a `429` that took several
minutes to clear. `FORECAST_POLL_HOURS=6` is far inside it; BMKG publishes twice a day, so anything faster is
asking a cache the same question. Each source keeps its own stamp (`out/forecast.<source>.last`): one that fails is
asked again after 30 minutes, not on the next 300 s poll, and the others are not held back. The stamp is written before
the request, so an `out/` that cannot be written stops the fetch before anything is asked. The wind field has its own
stamp (`out/forecast.wind.last`), behind the same `FORECAST_OPENMETEO` switch, so a refused field never asks the points again.

## The sources, and which of them are on

Every source is kept for the next 72 hours (`HOURS = 72`). A newer fetch replaces the stored value for an hour that is
still ahead, so the node always holds the latest run, and an hour that has passed is never rewritten.

**BMKG** (`FORECAST_BMKG=1`, Indonesia). 3-hourly, three days, no key. `ws` is km/h, `wd_deg` is the direction the
wind comes **from**, `tp` is rain in millimetres for the step. BMKG publishes no probability, so the node does not
invent one. Attribution is required and is on the card and in the export.

**Open-Meteo** (`FORECAST_OPENMETEO=0`, anywhere). Hourly, no key, CC-BY 4.0. It is the portable half — it is what
makes this pack work for nodes #2 in Barcelona and #3 in Santiago, where BMKG does not. **Its free tier is
non-commercial use only.** That is the operator's decision and not ours, so it is off until it is turned on.

**CAMS air and the sea** (also `FORECAST_OPENMETEO=1`, one switch for all three Open-Meteo sources). `forecast-cams` is
PM2.5 and the UV index for the next 72 hours, `forecast-marine` is wave height and swell height, period and direction. The
sea is asked only while the `coast` pack is on, at the node's own point; Open-Meteo snaps it to the nearest sea cell,
the sensor sits at that cell, and one farther than `COAST_MAX_KM` (30) is refused, as the coast pack refuses it.

## The territory, at the node's scale

Open-Meteo's weather and the CAMS air are asked for the node's ground at its `NODE_SCALE`, in one request per source.
`home` is one point, the node. `community`, the default, is 7 points, the node's resolution-7 H3 cell and the six
around it. `city` and `region` are 19 each, the resolution-6 or resolution-5 cell with two rings around it. The node's
own point keeps the node's coordinates and the plain sensor id (`forecast-om`, `forecast-cams`), the others sit at
their cells' centres as `forecast-om-<cell>` and `forecast-cams-<cell>`, and every sensor carries its `cell` in meta.
The sea and BMKG stay one point each. Open-Meteo counts each location as a call against its daily limit per IP, so
each poll on a community node sends 7 locations for the weather and 7 for the air, beside the wind field's 65 (8 × 8
and the node's own point) and, while `coast` is on, one for the sea.

## The gap between the two

When both are on, a third derived channel records how far apart they are on temperature and wind for the same hour.
Neither is the truth; a wide gap is the node saying so out loud rather than picking a favourite. It compares BMKG with
the node's own point only. The sources keep their own clocks, so the gap is made against the other source's last
stored hours (`out/forecast.<source>.rows.json`, future hours only) when only one was fetched.

## The issue time, stored per value

Every value is stored at its **valid** time with `fc_lead_hours` beside it: how far ahead of its own forecast it
is. A forecast without its issue time cannot be checked afterwards, and one that has quietly stopped refreshing
looks exactly like one that is right. `verify` fails if BMKG's `analysis_date` is more than 18 hours old, which
for a source that publishes twice a day means it has stalled.

Open-Meteo publishes no model run time. There is no `analysis_date` in its response and `generationtime_ms` is how
long the request took, not when the model ran. The node records when **it** fetched and labels it `fetched`, not
`issued`. Dressing a fetch time up as a model run would be inventing provenance.

## Channel roles

Every channel here is `derived`, none comparable — the same role `open-meteo-cams`' `pm25_model` carries in
`config/channels.yml`. A forecast is nobody's measurement of this place and must never pool with a sensor's
ambient reading. The `fc_` prefix is the second guard: no forecast metric shares a name with a measured one, so
even a mistake in the roles table cannot put a predicted temperature into an ambient average.

## What it assumes

That the node's coordinates are right, and — for BMKG — that the operator is in Indonesia and has set a code.
Without a code the pack logs one line and idles. A source that is down is never an alert.

## Scripts

```bash
planetai run forecast verify    # the code resolves to this point, units are as documented, the forecast is fresh
planetai run forecast fetch     # fetch now instead of waiting for the poll
planetai run forecast status    # the next day: wind, rain, temperature, and when it was issued
```

## Attribution

Weather forecast data from **BMKG** (Badan Meteorologi, Klimatologi, dan Geofisika), api.bmkg.go.id — BMKG must be
named as the data source inside the application, and is, on the card and in the export.
Model forecast from **Open-Meteo**, open-meteo.com, CC-BY 4.0. Air from the Copernicus Atmosphere Monitoring
Service (**CAMS**) and the sea from **Copernicus Marine**, both through Open-Meteo.

## The wind field

With `FORECAST_OPENMETEO=1`, each poll also keeps Open-Meteo's hourly 10 m wind for the next day at
`FORECAST_WIND_N` × `FORECAST_WIND_N` points (8 × 8) over `FORECAST_WIND_KM` (30 km) each side of the node, in one
request, as `out/ground/wind.json`; the node serves it at `/ground/wind` and the map draws it moving, the way Bali Air
Dispatch draws its 64 points over the island. It asks with `cell_selection=nearest`: the default moves a sea point
to the nearest land cell, up to 12 km off, which would draw the wind where it was not. It is a model's field, never
a reading: it reaches no cell, no alert and no report. `planetai run forecast windfield` refreshes it now.

