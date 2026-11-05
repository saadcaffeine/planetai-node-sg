# air-quality

The first domain pack, and the one that proves the core is domain-blind: nothing about PM2.5 lives in `app/`.

**What it adds** — six rules. Four are built around the decision a household actually faces (is the room or the street
unhealthy, is the room better or worse than the street, should the windows be open or shut); two say that the air just
jumped, before it is unhealthy. And three Index cells for `Environmental|Community` and `Environmental|City`.

**Where it was learned** — Kuta Selatan, Bali, September 2026, against Smart Citizen Kit 19880 and the public ambient
picture from Bali Air Dispatch. The burning pattern here peaks around 9am and climbs again after dark.

**What it assumes** — a low-cost PM sensor at the address. For "outside" the comparison rules take your own outdoor
sensors, else the three nearest public ones, else the CAMS model, and say which. Thresholds are US EPA / WHO 2021
(35.5 µg/m³ unhealthy for sensitive groups, 55.5 µg/m³ unhealthy for everyone, 15 µg/m³ WHO 24h).

**What it reads** — the Copernicus CAMS model at the node's point, through Open-Meteo, every poll while
`OPENMETEO_ENABLED` is 1, and 92 days of it on the node's first start, so the third tier of "outside" is there before
any sensor is. It is a model and lands as `kind='model'`, never `live`. The US EPA 2021 humidity correction lives here
too, in `adapter.py`; the AirGradient and PurpleAir packs borrow it. Both were core until 24 Oct 2026.

**Fork it.** The numbers that matter in Kerobokan are not the numbers that matter in Poblenou, and the sentence that
gets someone to close a window is different in every language and every building. Copy this folder, change the
thresholds and the wording, publish it as `planetai-pack-air-<yourplace>`.
