# bali-air-dispatch

The island's public air stations around this node, from [Bali Air Dispatch](https://baliairdispatch.com/): eight
networks (Nafas, IQAir, PurpleAir, AQICN, OpenAQ, AirGradient, Smart Citizen, Airly) in one key-free archive. The
node stores them as **other people's stations**, never as the house's own, so one kit can tell a fire in the lane
from haze over the whole island. **Bali only.**

A **code pack** that runs on its own switch: `BAD_ENABLED=1` is enough, without `PACKS_ALLOW_CODE` (an official
pack that names a `switch:` in its `pack.yaml` runs its code when that switch is on; see docs/PACKS.md).

## Turning it on

`presets/bali.env` turns it on, so a node installed with the Bali preset (or placed in Bali by `planetai setup`)
has it from the first poll. By hand: Set up › Packs › Bali Air Dispatch, or `planetai config set BAD_ENABLED 1`.
It needs `NODE_LAT` and `NODE_LON`. A node inside Bali's box with it off is told so under "Air stations nearby" in
`planetai doctor` and Set up; a node anywhere else is told nothing.

## It used to be core

Until the release after v0.82.3 this was `baliairdispatch()` in `app/sources.py`. The move changed no id: the
sensors are still `bad-<station_id>`, `source='baliairdispatch'`, and the settings keep their names, so a node's
history carries on. On `planetai update`, a node that keeps a `PACKS_ENABLED` list (in `.env` or Set up) and has
`BAD_ENABLED=1` gets `bali-air-dispatch` added to that list, or it would lose the ring.

## What it reads, what it stores

`GET https://baliairdispatch.com/api/v1/latest` every poll (the archive is edge-cached 5 to 60 minutes). Each
station the ring keeps becomes a sensor `bad-<station_id>`, `local=false`, with `pm25` (as the archive publishes
it, EPA 2021 corrected for Plantower networks), `pm25_raw` where the archive has it, `pm10`, `pm1`, `temp`,
`humidity` and `aqi` (a vendor index, never pooled). Its `meta` carries the originating network, the distance and
the attribution.

## Which stations are the ring

`verdicts()` decides, and it is the one function `planetai run nearby stations`, `nearby verify` and
`GET /nearby?audit=1` also call. A station is left out when it is:

| rule | catches |
|---|---|
| identity | a device this node already polls (`SC_DEVICES`, the `SC_USER` account, `AIRGRADIENT_HOSTS`), at any distance |
| proximity | anything within `BAD_MIN_SEPARATION_M` (150 m) of the node: its own kit under another account |
| by hand | `BAD_EXCLUDE`, what the first two missed |
| beyond the radius | further than `BAD_RADIUS_KM` (15; the Bali preset says 8) |
| indoor, malfunctioning, stale | as the archive flags them; `BAD_INCLUDE_INDOOR=1` keeps the indoor ones |
| same device | one device under two networks' ids (23 AirGradient units mirrored by OpenAQ on 7 Sep 2026): same name within the separation radius, the owning network kept |

## What it does not do

No rule and no cell: peers never drive an alert (AGENTS.md), and `live` means measured here. `packs/nearby` asks
whether this address is worse than the ring, `packs/season` whether this week is worse than the ring's last two
months, and `packs/air-quality` files the ring as `Environmental|City`, `partial`.

## Attribution

Required by the archive: **Bali Air Dispatch, baliairdispatch.com**, and the originating network named in each
row's `source`. Readings remain subject to their own networks' terms. Registry entry
`environmental/community/bali-air-dispatch`.
