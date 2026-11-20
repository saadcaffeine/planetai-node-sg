# Singapore node

A [PlanetAI](https://github.com/fabcity/planetai-node) node in Geylang East, Singapore. It runs at home on a Windows
PC under Docker Desktop, reads one outdoor Smart Citizen kit, and takes its outdoor reference from Singapore's
national open data (NEA and PUB, via data.gov.sg) instead of a peer aggregator or a model alone.

This folder documents what is specific to this node. The node itself is the upstream `planetai-node` repository
(v0.75.8); nothing here replaces its own docs.

## At a glance

| | |
|---|---|
| Node name | `singapore-node` (home, community scale) |
| Location | 1.317, 103.885, about Geylang East Library; time zone Asia/Singapore |
| Alert language | English |
| Issues, in order | air, coast, heat, land (`NODE_ISSUES`) |
| Own sensor | Smart Citizen kit #18929, outdoors ("street"); no sensor in the house |
| Outdoor reference | NEA and PUB (`singapore-nea` pack), NEA beach water quality (`singapore-beach` pack), CAMS, Open-Meteo, NASA FIRMS (`fire-smoke` pack) |
| Bali Air Dispatch | off (`BAD_ENABLED=0`); it only covers Bali |
| Forecast | Open-Meteo on, BMKG off |
| Sharing | `SHARE_LEVEL=open` (alpha testing); Reticulum presence off; no LoRa hardware |
| Dashboard | http://localhost:8080 |

## What is different from other nodes

- **National open data as the outdoor reference.** The `singapore-nea` pack reads 14 data.gov.sg feeds: PM2.5 and PSI
  by region; air temperature, humidity, rainfall, wind speed and direction from the nearest station; island-wide UV;
  WBGT heat stress; PUB flood alerts; dengue clusters; and the 2-hour, 24-hour and 4-day forecasts.
- **Fire smoke.** The `fire-smoke` pack counts NASA FIRMS hotspots within `FIRE_RADIUS_KM` (500) by compass sector and
  warns when smoke is upwind, using NEA wind direction.
- **Rules written for this place.** Haze (PSI), heat stress (WBGT 31 °C and 33 °C), flooding, dengue clusters,
  sensor-versus-NEA disagreement, fire smoke upwind, and `wind_southeast_rising`: south-east wind (east-south-east to south-south-east, 101.25° to 168.75°) for
  at least 80% of the last three hours while its speed is up at least 1 knot, a pattern this node's keeper has seen precede
  worse air. The thresholds are a first guess to tune against a season of PSI.
  `wind_pm25_correlated` is the one that pages: over six hours, this node's own street PM2.5 correlates with the wind
  swinging into the south-east (r >= 0.6, wind alignment varying, PM2.5 up at least 3 µg/m³ and at least 15). It is act level,
  so at `ALERT_LEVEL=act` it ignores quiet hours (22:00 to 06:00); lower it to warn in `packs/singapore-nea/rules.yml` to keep
  it on the dashboard.
- **A borrowed heat line.** The 35 °C apparent-temperature line was measured indoors at the Bali node. It is kept here
  until this node has its own data, and the `singapore-nea` pack's heat readouts (its `pack.yaml`) say so.
- **Beach health.** The `singapore-beach` pack reads NEA's weekly Enterococcus banding (Band 1 Normal, 2 Elevated, 3 High) for East Coast and Changi, and the Coast card shows it, with rules for Band 2, Band 3, NEA's bacteria advisory and heavy rain.
- **Land and coast for an island city.** The `earth` pack uses a 5 km square (`EARTH_RADIUS_M=5000`); Earth Engine
  reports built and tree cover; the coast row reads the sea off the island.

## Layout

```
planetai-node/
  .env                          node settings (git-ignored; never share it)
  packs/singapore-nea/          NEA and PUB feeds, rules, tests; air and heat readouts in its pack.yaml (wild pack)
  packs/fire-smoke/             NASA FIRMS hotspots and upwind rules (wild pack)
  packs/singapore-beach/        NEA weekly beach water quality (East Coast, Changi); coast beach bands in its pack.yaml (wild pack)
  packs/tuya-indoor/            Smart Life room temperature and humidity through the Tuya Cloud API (wild pack)
  app/static/dashboard.js       the Singapore wall (sgair, sgcoast) on the classic layout, served at /
```

Sensor IDs from the NEA pack are stable, one per measure: `nea-pm25`, `nea-psi`, `nea-temp`, `nea-humidity`, `nea-rain`,
`nea-windspeed`, `nea-winddir`, `nea-wbgt`, plus `nea-rain-island`, `nea-wbgt-island`, `nea-uv`, `nea-flood`,
`nea-dengue`, `nea-fc2h-<area>`, `nea-fc24h` and `nea-fc4d`. The station or region a reading came from is in the
sensor's name and metadata.

## Settings that matter

Set these in `.env`. Secrets stay there and are never committed.

| Setting | Value here | Why |
|---|---|---|
| `NODE_LAT`, `NODE_LON` | 1.317, 103.885 | the house |
| `NODE_TZ` | Asia/Singapore | local hours |
| `PACKS_ALLOW_CODE` | 1 | the NEA and fire packs are code packs |
| `BAD_ENABLED` | 0 | Bali Air Dispatch does not cover Singapore |
| `FORECAST_BMKG` | 0 | BMKG is Indonesia's forecast |
| `FORECAST_OPENMETEO` | 1 | day-ahead wind and rain |
| `NEA_API_KEY` | blank (recommended) | a free data.gov.sg key raises the rate limit |
| `FIRMS_MAP_KEY` | set | NASA FIRMS key, 5000 requests per 10 minutes |
| `BEACH_AREAS` | East Coast,Changi | NEA beaches to follow |
| `NODE_ISSUES` | air,coast,heat,land | Air and Coast lead the dashboard |
| `FIRE_RADIUS_KM`, `FIRE_SOURCES` | 500, VIIRS_SNPP_NRT, VIIRS_NOAA20_NRT | fire-smoke pack |
| `TUYA_ACCESS_ID`, `TUYA_ACCESS_SECRET`, `TUYA_REGION`, `TUYA_DEVICES`, `TUYA_SECONDARY`, `TUYA_EVERY_MIN` | blank, blank, eu, blank, blank, 10 | tuya-indoor pack: Smart Life room sensors through the Tuya Cloud (Central Europe data centre for this account) |
| `SC_DEVICES` | 18929 | the Smart Citizen kit |
| `MAP_TILES` | on | live satellite and street tiles; each tile request tells the tile server which square of the map the page is looking at |
| `ALERT_LEVEL` | act | only act-level rules reach the phone |
| `SHARE_LEVEL` | open | alpha testing; the whole read API is open to anyone who can reach port 8080 |
| `EARTH_RADIUS_M` | 5000 | the AlphaEarth square around the house |

## Running it

From the `planetai-node` folder in PowerShell (Git Bash rewrites `/app/...` paths, so turn that off first):

```powershell
$env:MSYS_NO_PATHCONV = "1"
planetai status                       # is everything up
docker compose ps
docker compose logs app --tail 50     # look for "singapore-nea" and "fire-smoke" lines
docker compose restart app agent      # after a .env or pack change
docker compose up -d --build app      # after a change under app/ (issue files, code)
```

Then open http://localhost:8080. NEA feeds arrive a few at a time: the adapter requests at most 4 feeds per poll, waits
2.5 s between them, and stops a poll at the first 429, so the full set fills in over about 15 minutes.

Tests, without Docker:

```bash
python3 tests/test_singapore_nea.py
python3 tests/test_fire_smoke.py
PACKS_DIR=packs python3 tests/test_issues.py
```

`make lint` needs the project's full toolchain and has not been run on this node's changes.

## Known limits

- The NEA test payloads have the right shape but invented values; replace them with real captures.
- The dengue GeoJSON layout and the flood-alert record shape were not checked against live responses.
- The Heat "region" row still reads Open-Meteo. NEA temperature and humidity are separate sensors, and the heat row
  needs both on one sensor, which needs an engine change.
- No indoor sensor, so the Social heat-exposure cell cannot fill.
- Old NEA sensors with station names in the ID (`nea-temp-S109` and similar) stay in the database as stale rows.
- Anonymous data.gov.sg access is rate limited; without `NEA_API_KEY` some feeds can still get 429s.

## Open items

- [ ] Rebuild the app and confirm the Air region row and the Figures readouts on the live page.
- [ ] Get a data.gov.sg API key and set `NEA_API_KEY`.
- [ ] Put a sensor in the house.
- [ ] Measure a Singapore heat baseline (about fourteen days) and propose a local line.
- [ ] Send the NEA and fire-smoke packs, a Singapore preset (not written yet), and the issue drafts upstream.
- [ ] Decide on a Reticulum link, and whether to close port 4242, which is open on all interfaces.

## Attribution

Contains information from the National Environment Agency and PUB on data.gov.sg, under the Singapore Open Data
Licence. Fire data: NASA FIRMS. Land data: AlphaEarth Foundations Satellite Embedding (Google and Google DeepMind,
CC BY 4.0). Forecast and air models: Open-Meteo and CAMS. Smart Citizen: smartcitizen.me.

## Dashboard changes

These edit `app/static/dashboard.js` and `dashboard.css`, so they need `docker compose up -d --build app`.

- **Wall.** A "Singapore air, wind and rain" row (`sgair`) compares the house's PM2.5 (Smart Citizen, 1 h mean) with
  NEA's regional figure, and shows wind direction and speed and rain (Open-Meteo probability plus NEA's share of areas
  forecast wet). Explainers sit behind an "i" icon, and a pause button stops the dial when reduced motion is off.
- **Beaches, fires and haze row.** A second wall row (`sgcoast`) shows NEA's worst beach band (East Coast, Changi), NASA
  FIRMS fire hotspots for the last 24 h with the change on the 24 h before, and NEA regional PM2.5 against the same hour
  yesterday. FIRMS counts fires, not smoke, so haze is the PM2.5 change; it needs 24 h of NEA history before it can show.
  The wall now carries up to eight of these columns before the rest go to "more in Now".
- **fire-smoke fix.** FIRMS's last URL segment is UTC calendar days, so `/1` returned only today and `fires_24h` fell to zero
  at 08:00 Singapore time. The pack now asks for three days, and publishes `fires_prev_24h` (the 24 h before) for the change.
- **Act.** "I did this" now asks for the act token in the form when the node refuses a browser (a browser is never "this
  machine" to the node), keeps it in the browser, and marks the alert as acted in place; the wall's alert rings link to
  the Act section; the rail's zone key is behind an "i" icon.
- **Stage squares.** The four squares in each stage header link to the stage they stand for (scrolling, so the address keeps
  its view), show the stage name on hover, and are greyed with "not on this view" for stages the view does not draw,
  as in Simple mode.
- **Icons and links.** Sign icons now name themselves on hover; rings on Now link to Act like the wall's; data routes open in a new tab, and routes that cannot be opened by a link (POST /actions, token-only /place/geojson) are shown as plain text saying why.
- **Seen it.** Each open alert has a "Seen it" button beside "I did this". It records `acknowledged` (the name is kept in this browser, the act token is asked for only if refused). rho counts it as an answer, the alert stays open and shows "Seen" until somebody acts. There is still no bulk version.
- **Wall layers.** Behind the cells the island now has a shallow-water halo as well as its coast, and a fainter outline of Southeast Asia sits around it (Natural Earth 1:50m, public domain, for the mainland and the Philippines; geoBoundaries gbOpen ADM0, Runfola et al. 2020, CC BY 4.0, for Malaysia and Indonesia, with the Johor and Riau coasts kept to about 50 m; `?outline=island` keeps only the island, `?outline=off` hides both). While the Singapore Grand Prix is on, the Marina Bay Street Circuit is drawn over the cells as a red loop with one dash running round it, with a hover tooltip about the track; the pause button and reduced-motion settings stop the dash. Dates and tooltip text live in `app/static/wall-layers.json` (`from`/`to`, so it appears 24 Sept and goes after 13 Oct 2026); `?track=on` or `?track=off` overrides. The circuit centreline is from bacinger/f1-circuits (`sg-2008.geojson`, the 4.93 km layout used since 2023); that repository publishes no licence file.
- **Room sensors.** The `tuya-indoor` pack reads two Smart Life temperature and humidity sensors through the Tuya Cloud API and records them as local indoor sensors, so the existing indoor heat rules use them. The air-conditioned living room is the reference; the sun-baked workshop is marked secondary (`TUYA_SECONDARY`), so it is drawn but is not the house's room number and raises no heat alerts. See `packs/tuya-indoor/README.md`.
- **Land outline.** A faint island outline sits behind the wall's cells at every resolution. It is a public coastline
  (`app/static/coast-outline.json`, from the URA Master Plan 2014 subzone boundaries, obtained through
  github.com/yinshanyang/singapore, with URA's SDCP Waterbody polygons cut out of it, so the reservoirs, the larger rivers
  and Marina Bay show as water; both are on data.gov.sg and contain information licensed under the Singapore Open Data
  Licence v1.0. Water narrower than about 60 m is left out so drains do not clutter it, and the outline is kept to about
  1 m around Marina Bay and the centre and about 7 m elsewhere. The waterbody layer is indicative and dates from 2012, so
  it is a backdrop and not a survey), served from the node itself, so it is offline, needs no token and reveals nothing about the household.
  Add `?outline=off` to the wall address to hide it.
- **Resolution ladder.** Scale labels from planetai.fab.city/nodes (Region, City, Community, Home, Street, Room) sit under
  the wall dial and Now's rail. Series charts mark the reading 24 h ago and the highest value in the 24 h drawn.
- **Fixes.** Pressing a wall dial rung no longer drops `#wall` from the address; Historical and Network say how many
  sections Simple mode hides, with a "Show all sections" button.
- **Rain probability.** The forecast pack now publishes Open-Meteo's `precipitation_probability` as `fc_rain_prob`.
