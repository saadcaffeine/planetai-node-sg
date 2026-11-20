# energy

The pack says how much of the electricity on the node's grid is made from fossil fuels, where it is made and how far
away, and what the sun on the cell could make on a roof today. It is context and never asks the household to act.

Turn it on by adding `energy` to `PACKS_ENABLED` and `NODE_ISSUES` (it needs `PACKS_ALLOW_CODE=1`). Now gets an Energy
row and panel, Place a Power grid row, and `GET /energy` serves both. A node on a grid `grids.yml` does not hold says
so; add the grid there, with its polygon, its links and where its mix comes from.

With `ENERGY_HA_URL`, `ENERGY_HA_TOKEN` and the entity ids set, it also reads the house's own Home Assistant, read
only, every 5 minutes. Everything it keeps about the house is private.

## Sources and licences

### OpenStreetMap (via Overpass API)

- **What it provides:** power plants (`power=plant`), generators (`power=generator` with `generator:source`),
  substations (`power=substation`), and transmission lines and cables (`power=line|cable|minor_line`) inside the
  grid's polygon.
- **URL:** `https://overpass-api.de/api/interpreter`
- **Licence:** Open Data Commons Open Database License (ODbL 1.0). Attribution:
  `© OpenStreetMap contributors, ODbL, via Overpass`.
- **Registry entry:** `environmental/community/openstreetmap` (already in `data/sources/`).

### Ember Yearly Electricity Data (Indonesia proxy for the Java link, and thermal capacity factors)

- **What it provides:** Indonesia's yearly electricity generation and installed capacity by fuel. 2025 is the latest
  year: fossil generation was 444.713 TWh out of 528.207 TWh (`0.8419`, 84.2%), used as a proxy for the Java grid
  feeding the Gilimanuk submarine cable. 2025 has no capacity column yet, so the capacity factors below come from 2024
  (85.2% fossil that year).
- **URL:** `https://ember-energy.org/data/yearly-electricity-data/` (bulk CSV:
  `https://files.ember-energy.org/public-downloads/generation/outputs/release_generation_yearly_global.csv`)
- **Licence:** Creative Commons Attribution 4.0 International (`CC BY 4.0`). Exact wording on the dataset page:
  `"All content is released under a Creative Commons Attribution Licence (CC-BY-4.0)."`
- **Registry status:** owed in `awesome-fabcity-data` before the pack names it in `pack.yaml` `sources:`.

### Red Eléctrica de España (REE), the REData API (Balearic and peninsular mix)

- **What it provides:** generation by technology (`generacion/estructura-generacion`) and island link balance
  (`balance/balance-electrico`, `intercambios/enlace-baleares`) for the Balearic (`geo_limit=baleares`, `geo_ids=8743`)
  and peninsular (`geo_limit=peninsular`, `geo_ids=8741`) electrical systems.
- **URLs:**
  - API documentation: `https://www.ree.es/es/datos/apidatos`
  - Legal notice: `https://www.ree.es/es/aviso-legal`
  - Endpoint: `https://apidatos.ree.es/es/datos/generacion/estructura-generacion`
- **Licence:**
  - On `https://www.ree.es/es/datos/apidatos`:
    `"The REData API provides a simple REST service to allow third parties to access the backend data used in the REData application. By using this API, you will be able to retrieve data from the REData widgets and use them for your own purposes."`
  - On `https://www.ree.es/es/aviso-legal` (§5.1 *Propiedad intelectual e industrial o derechos de naturaleza análoga*):
    `"No obstante, el usuario podrá visualizar y obtener una copia privada temporal de los contenidos para su exclusivo uso personal y privado en sus sistemas informáticos (software y hardware) publicarlo en su página web o crear materiales corporativos o académicos siempre que sea con fines informativos y no con finalidad comercial."`
    subject to four conditions:
    `"I. Mencionar de forma clara y explícita a la Sociedad como fuente de la información y de los datos. II. No alterar ni desnaturalizar el sentido de la información ni de los datos. III. Mencionar la fecha de la última actualización de la información y los datos. IV. En ningún caso se autoriza la utilización de logotipos, marcas comerciales o signos distintivos de la Sociedad más allá de los utilizados por ésta en los contenidos."`
  - **Ruling (Tomas, 9 Nov 2026):** non-commercial, so it does not count as open. Menorca stays `measured` on the
    node, shown for information with REE named and the date of the data, and the registry entry says non-commercial.
    The figure stays out of the Index and exports.
- **API note (9 Nov 2026):** `generacion/estructura-generacion` answers HTTP 200 for `time_trunc=day`, `month` and
  `year`, and HTTP 400 (`"Los datos solicitados no están disponibles en este momento"`) for `time_trunc=hour` on all
  tested dates and regions (`demanda/evolucion` still answers 200 at `time_trunc=hour`). Also, REE's `ree.js` selector
  maps `geo_limit=baleares` to `geo_ids=8743` (`geo_ids=8` is Cantabria under `geo_limit=ccaa` and returns 502 with
  `geo_limit=baleares`).

### Bali grid boundaries, Nusa Penida, cable rating and capacity factors

- **Nusa Penida:** PLN operates the Nusa Penida / Lembongan / Ceningan system as an isolated microgrid (PLTD Kutampi
  diesel, PLTS Nusa Penida solar, and PLTB Nusa Penida wind turbines) with no submarine power cable to mainland Bali.
  `bali.polygon` in `grids.yml` is drawn around Bali's main island only, excluding Nusa Penida (and excluding Cable
  Head Ketapang on the Java shore).
- **Java–Bali cable rating and Bali average demand (`rated_mw: ~`, `demand_mw: ~`):** secondary reports (PLN press
  releases, news coverage, and engineering notes) describe four 150 kV submarine circuits between Ketapang and
  Gilimanuk with ~340–400 MW transfer capacity (~130 MVA / ~100 MW per circuit on circuits 3 & 4) and Bali peak load
  near 1,150–1,300 MW (~5,000+ GWh/year, ~570–650 MW average demand). Because no primary table under an open licence
  (CC BY 4.0 or public domain) was found when the pack was built (8 Nov 2026), both fields are recorded as `~` in `grids.yml`.
- **Capacity factors (`bali.capacity_factors`):**
  - `coal: 0.70`, `gas: 0.35`, `oil: 0.26`: derived from Indonesia's 2024 generation and installed capacity in Ember's
    Yearly Electricity Data (`CC BY 4.0`, `release_generation_yearly_global.csv`: coal 347.086 TWh / 56.69 GW = 0.699;
    gas 71.681 TWh / 23.58 GW = 0.347; other fossil / oil & diesel 13.316 TWh / 5.84 GW = 0.260).
  - `solar: 0.18`, `wind: 0.25`: marked **`assumed`** (typical tropical utility-scale PV and onshore wind capacity
    factors; Ember's 2024 Indonesia capacity column for solar and wind reflects partial-year additions and small samples).

## The Today box

The sun on the cell today comes from the forecast pack's own Open-Meteo point (`forecast-om`, `fc_shortwave`, hourly
W/m²). With no forecast rows for today there is no sun figure and no roof line. The roof is
`ENERGY_PANEL_KW × sun × ENERGY_PANEL_PR`, unless Home Assistant measured it (`home_roof_kwh`), and then the measured
kWh are shown.

The three settings are **placeholders**: `ENERGY_PANEL_KW=2` (the panels in the mockup), `ENERGY_HOUSE_KWH_DAY=9`
and `ENERGY_PANEL_PR=0.75` (a typical performance ratio). Set your own in Set up. Leave one blank and its line is left out.
