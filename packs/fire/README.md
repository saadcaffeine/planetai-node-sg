# fire

Fires that satellites saw near this node in the last day, from NASA FIRMS: how many, how far, in which
direction, and whether they are where the wind is coming from. A **code pack** (it ships `adapter.py`), so it
runs only with `PACKS_ALLOW_CODE=1`, and it is **off until `FIRE_ENABLED=1`**.

**It says where fires are. It does not predict smoke.** A hot pixel is not a plume. Smoke rides winds above the
ground and can take a day to arrive or miss you entirely. The pack counts what the satellites saw; the one rule
that asks somebody to act also needs the air outside to be rising.

## Turning it on

Under Set up → Packs, or in `.env`: `PACKS_ALLOW_CODE=1` (if it is not already) and `FIRE_ENABLED=1`, then
`planetai restart`. That is all it needs: no key, no account.

It is off by default for the bandwidth, not the licence. Without a key it reads FIRMS's regional file for each
satellite whenever that file has changed: 1.9 MB (NOAA-20) and 1.1 MB (NOAA-21) for South East Asia on
14 Oct 2026, Europe 35 KB in October. The first start takes the 7-day file once, about seven times that. A
free `FIRMS_MAP_KEY` (firms.modaps.eosdis.nasa.gov/api/map_key) makes every read the regional ring's box only,
a few kilobytes.

## What it reads

NASA FIRMS active fire detections, VIIRS 375 m, from NOAA-20 and NOAA-21 by default (`suomi-npp` can be added).
The public text files need no key and are named
`data/active_fire/<satellite>-viirs-c2/csv/<J1|J2|SUOMI>_VIIRS_C2_<Region>_<24h|7d>.csv`; each name was
checked on 14 Oct 2026. The region is picked from the node's position: `SouthEast_Asia` or `Europe` when the
whole regional ring fits inside the box that file's own detections covered that day, otherwise `Global`
(6.4 MB a satellite). Bali at 150 km and Menorca and Singapore at 500 km fit; Bali at 500 km reads Global.

**Licence.** NASA data are CC0. FIRMS asks to be cited as "NASA FIRMS", which the sensor's `meta` and the
pack's attribution do. Registry entry `environmental/bioregion/nasa-firms`.

**Polite polling.** At most every `FIRE_POLL_HOURS` (3). FIRMS's file server ignores `If-Modified-Since` and
`If-None-Match` (tested 14 Oct 2026: a 200 carrying the same ETag), so the pack asks with HEAD first and
downloads only when the ETag or Last-Modified changed; it still sends both headers on the GET. A file that has
not changed writes no new rows. What it remembers between polls lives in `out/fire/state.json`, because the
node imports a pack's adapter afresh on every poll.

## What it stores

One sensor, `firms-fires`, `source='firms'`, `kind='model'`, `scale='bioregion'`, `local=False`, no
coordinates. All about the 24 hours before the reading, counted as **burning places**: one per ~445 m cell,
however many satellites and passes saw it (NOAA-20 and NOAA-21 pass about 50 minutes apart and see the same
field). Low-confidence detections are dropped.

| metric | what |
|---|---|
| `fires_local_24h`, `fires_region_24h` | burning places in the local ring (`FIRE_LOCAL_KM`, 25) and the regional ring (`FIRE_REGION_KM`, 150) |
| `frp_local_mw`, `frp_region_mw` | their fire radiative power, summed, in MW |
| `fires_nearest_km`, `fires_nearest_bearing` | the nearest, and its compass bearing from the house; absent when there is none |
| `fires_local_upwind`, `fires_region_upwind` | the ones lying within 45° of where the wind comes from |
| `fires_upwind_km`, `fires_upwind_bearing` | the nearest of those |
| `fire_wind_from_deg` | the wind the upwind counts were reckoned with |

The wind is the node's own, best first: a measured local kit's `wind_direction`, then the core Open-Meteo point,
then the forecast pack's `fc_wind_direction`. Forecast rows are stored at their valid time, hours ahead, so the
wind is read with `ts <= now()`. With no wind in the last three hours, no upwind numbers are written at all. On
the first start the six days before are written too, once a day, without upwind.

Every channel is `derived` and not comparable (`channels.yml`); none is private, because fires are public data
and nothing here says where the house is. Five of them are a section of their own (`sections:` in `pack.yaml`,
stage observe, `wall: true`): fires nearby, in the region, upwind, the nearest fire's distance and its direction
in degrees from north. The Wall gives each a column and its narration reads them as satellite figures, because
the sensor's name says NASA FIRMS and VIIRS. Like any core pack's section it stays out of `/issues` until the
node holds a row of it, so a node that never turned fires on shows nothing. With no fire in the regional ring,
or no wind, the band says the nearest or the upwind count has not arrived: there is none to show.

## What it says

| rule | level | cooldown | when |
|---|---|---|---|
| `fire_near` | info | 1440 | at least one fire in the local ring |
| `fire_upwind_near` | warn | 720 | at least one fire in the local ring is upwind |
| `smoke_arriving` | act | 1440 | 25 or more upwind in the regional ring, AND outdoor PM2.5 in the last 2 hours past the WHO line (15 µg/m³) and half again its level of the 6 hours before |

Outside, for the act rule, is the node's own and public outdoor sensors when any reported in the last 8 hours,
else the CAMS model, never both averaged. Each message says where: a distance and a compass direction from the
house, never a coordinate. In English:

> 🔥 Smoke from fires is probably reaching the house. The air outside has risen to 30 µg/m³, past the WHO line
> of 15 µg/m³, and satellites saw 30 fires in the last day on the side the wind comes from, the nearest 12 km
> north-east.

At the default `ALERT_LEVEL=act` the info and warn rules show on the dashboard and in the briefing and do not
interrupt anyone. The rules are not kinded: the event engine's kinds are about rooms, and a fire is not in one,
so they send the same way on every `ALERT_ENGINE`. No Index cell: a count of somebody else's satellite pixels is
not this place's measurement.

**Why a section, not an issue of its own.** An issue is something a place is better or worse at, and the thing
a household feels from a fire is the air: the pack's domain is `air`, so its rules belong to the air issue. A
`fire` issue would need a hero, four distances (there is no fire in the room) and sentences of its own, to say
what the air issue already says when smoke arrives. The numbers go in a declared section instead.

## Where the numbers come from

**Written for Kuta Selatan, Bali, from one day.** On 14 Oct 2026 (NOAA-20 and NOAA-21, about 17:15 UTC) the
Bukit had no fire within 25 km or 50 km; the nearest was 75 km north-west, in East Java; the 150 km ring held 51
burning places and 355 MW. With a south-east wind, the dry-season trade wind, 3 of them were upwind; a
north-west wind would have put 47 upwind. With Suomi NPP as well: 3 within 100 km, 61 within 150 km and 561
within 500 km. So 25 upwind is about half of everything in the ring that day, and the act rule also wants the air to
show it. **A first guess, not a calibration.** Tune it on a burning season of this node's own readings, and say
what you tuned it against.

## What it does not know

- Small fires. A rubbish fire down the lane is usually below what a 375 m pixel can see, so an empty local ring
  is not a clean neighbourhood.
- Cloud. A fire under cloud is not detected, so a low count is not a clear sky.
- What burns. VIIRS sees heat: field burning, peat, a kiln, a flare or a volcano look alike.
- The wind aloft. Upwind is reckoned with the ground wind, which smoke only roughly follows.
- Grid edges. One fire on the edge of a ~445 m cell counts twice.

## Settings

| setting | default | meaning |
|---|---|---|
| `FIRE_ENABLED` | `0` | the pack's own on-switch |
| `FIRE_LOCAL_KM` | `25` | the local ring, in km |
| `FIRE_REGION_KM` | `150` | the regional ring, in km. Singapore may want 500 |
| `FIRE_POLL_HOURS` | `3` | how often to ask |
| `FIRE_SATELLITES` | `noaa-20,noaa-21` | any of `noaa-20`, `noaa-21`, `suomi-npp` |
| `FIRMS_MAP_KEY` | empty | optional; a secret, masked under Set up. Rides in the URL path, so no error the pack raises carries a URL |

## Tests

`python3 tests/test_fire.py`, offline, in `tests/all`. Its fixtures in `packs/fire/tests/fixtures/` are real rows from the
public files read on 14 Oct 2026 (CC0, NASA FIRMS): NOAA-20 and NOAA-21 South East Asia around the Bukit and
NOAA-20 Europe around Menorca. It checks the ring maths, the directions, upwind across north, the 14 Oct numbers
above, HEAD-first polling and a 304, that a key never reaches an error, and that each rule speaks at its level.

The upwind idea, and the warning that FIRMS counts calendar days, come from saadcaffeine's wild `fire-smoke`
pack (fabcity/planetai-wild-packs PR #6), which needs a key and reads Singapore's NEA wind.
