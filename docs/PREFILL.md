# What a node knows before it has a sensor
<!-- checked: v0.91.0 -->

On its first start, with an empty database, the node reads these for its own coordinates:

| source | what | span | cost |
|---|---|---|---|
| Copernicus CAMS (through Open-Meteo, the `air-quality` pack, while it is on) | hourly PM2.5, PM10, O₃, NO₂, dust and UV, on an 11 km grid | PM2.5 and PM10 for the last 92 days, then all of them live | free, no key |
| NASA POWER | monthly normals for sunlight, temperature, rain, humidity and wind | 1981 to now | free, no key |
| Open-Meteo | the weather now: temperature, humidity, wind, rain | live | free, no key |
| OpenStreetMap Nominatim | the place name | once | free |

So `planetai status` has something to say within minutes, anywhere: today's modelled air against three months of
history, and today's weather against normals since 1981. `BOOTSTRAP=0` skips it. The first start sends the node's
full coordinates to Open-Meteo, NASA POWER and Nominatim ([Sharing and security](site/sharing.md#what-leaves-the-machine-and-how-coarse)).

## The model against your first sensor

The model knows the district and a sensor knows the address, and the node can put a number on the difference the
day a sensor arrives. At node #1 the CAMS cell tracks the street at r = 0.51 and the room at r = −0.18.

## Nothing that needs an account

Nothing that needs a key or an account runs unless you turn it on. NASA FIRMS needs no key: it is the `fire` code
pack, off until `FIRE_ENABLED=1`, and the optional `FIRMS_MAP_KEY` only narrows what it downloads.

## Presets

`presets/<city>.env` exists for bali, barcelona, boston, santiago, menorca and delhi: coordinates, time zone, city
key, the open-data portal where there is one, and for Bali the public station feed. `planetai setup` picks one when
your place falls inside one of the four Index pilots (Bali, Barcelona, Boston, Santiago), and `./install.sh --preset
<city>` takes any of them.

## Not embedded

The node carries no copies of datasets, no model weights and no map tiles. It fetches what it needs when it needs it
and keeps only what it computed, so a node is a download of a few megabytes. Two things are exceptions. A 200 kB
outline of the world's land (Natural Earth, public domain) ships for the Node view. And map tiles are kept once you
ask for them: `planetai run place basemap` and `planetai run earth-engine basemap` store them in `out/ground/` (on
node #1, 6 MB of street map, 49 MB of drone imagery and about 12 MB of satellite), and nothing runs those commands
unless somebody types them.

## Attribution

Copernicus Atmosphere Monitoring Service (CC BY 4.0); NASA POWER; Open-Meteo (CC BY 4.0); OpenStreetMap (ODbL). The
model sensors carry their attribution or licence in `meta` on `/sensors`; the daily export states only its own
CC BY 4.0.

Next, give the node a sensor of its own: [Sensors and sources](site/sensors.md).
