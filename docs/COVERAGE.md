# Coverage: the node against the Fab City Index
<!-- checked: v0.80.10 -->

The Index is twenty cells: four pillars (Environmental, Economic, Social, Governance) by five scales (Community, City,
Region, Bioregion, Planet). A node fills cells at any scale; the kind of source changes, not the code.

## What a cell needs at each scale

| scale | describes | arrives as | cadence | `kind` |
|---|---|---|---|---|
| Community | this address, this lab | a device you own, or a nearby public sensor | minutes | `sensor` |
| City | a district, a municipality | an open-data portal, a municipal network | days | `portal` |
| Region | a province, a metro | statistical APIs, grid operators | months | `portal` |
| Bioregion | a watershed, a biome | hydrology, biodiversity, satellites | months to years | `portal`, `model` |
| Planet | boundary conditions | Earth models sampled at your coordinates | hours | `model` |

Two rules the node keeps. **Aggregation stops at Region**: Bioregion and Planet publish context downward and are never
rolled up. **`live` means measured here**; a model or a portal is `partial`, whatever its quality.

## Filled today, node #1

Re-read from `/cells` on 21 September 2026, node #1 at v0.69 with `LOCAL_RADIUS_M=500`, as recorded verbatim in
`app/issues/fixtures/node1-2026-09-21d.json`. PM2.5 and heat count sensors in the node's custody since v0.50.

| cell | from | state |
|---|---|---|
| Environmental \| Community | your sensors, PM2.5 24h mean; the share of days over the WHO line | live; partial |
| Environmental \| City | nearest public sensors; land change (the `earth` pack) | partial |
| Environmental \| Bioregion | sea temperature; days over the Posidonia line (when wild `posidonia` is added); tree cover (Earth Engine) | partial |
| Economic \| Community | mapped businesses per km² (OpenStreetMap, the `place` pack) | partial |
| Social \| Community | heat-exposure hours from indoor temp and humidity | live |
| Governance \| Community | ρ, alerts that led to action | partial → live at five actions |

Six of twenty. `planetai cells` shows them; the dashboard counts them on its map of what leaves the node. Two more
are one setting away: `Governance|City` from the `open-data-health` pack once `CKAN_PORTALS` names a portal, and
`Economic|City` from the `thingdata` pack once `THINGDATA_INSTANCES` names a server. Node #1 reads neither.

## Empty, and what would fill each

| cell | a source that exists | who would write the pack |
|---|---|---|
| Economic \| Community, properly | a fab lab's machine log (Fabman, a CSV), a market's stall count | a fab lab |
| Economic \| City | a business registry, KLEMS; a ThingData server (the `thingdata` pack reads one) | a city partner |
| Social \| City | a survey via the node's own Telegram bot | Making Sense |
| Governance \| Region | Socrata / ArcGIS portals (Barcelona, Boston) | a civic-tech group |
| Environmental \| Region | a grid operator's hourly mix | a regional partner |
| Economic \| Region, Bioregion | procurement feeds (TED, ChileCompra, LKPP); material-flow accounts | an institution |

`planetai sources --all --cell 'Social|City'` lists what the registry files for a cell, and ends with its three
counts. At the `851b8db` pin every row above counts capable 0, except Economic|Community, whose one is the
OpenStreetMap proxy the `place` pack reads.

The Social column has the fewest sources of any in the registry. Heat-exposure hours is the first number in it.

## Reading the map

A green cell is a measurement at an address. A blue one is derived or modelled. An empty one has no source, not a
missing feature. The node does not fill what it cannot measure, and says which is which.
