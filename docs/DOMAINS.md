# Domains
<!-- checked: v0.91.0 -->

The core measures nothing in particular. It polls sources, stores readings, runs rules and fills Index cells. Which
readings, which rules and which cells is a pack's business. `grep pm25 app/packs.py`, the loader, returns
nothing.

## Issues: what a domain is called in the house

A domain is what a pack declares. An issue is what a household calls it, and there are fewer of them: air, heat,
land, coast and water. An issue is something a place can be better or worse at, that somebody living there recognises by
name.

Not every domain is an issue. Weather feeds air and heat (wind for working out where a smell came from, the
forecast for the days ahead), but nobody asks how the weather is doing as a quality of their place. Place is the
ground everything else sits on. Governance is the loop and the Index. Trust is the node's own instruments, and the core's. Repair
is a catalogue of what can be fixed, kept by people. Make is where the nearest workshop is, a line on the report
and on an ask, never a number.

| issue | packs | kind | the line, and where it comes from |
|---|---|---|---|
| air | `air-quality`, `nearby`, `season`, `fire`, `bali-air-dispatch`, `smartcitizen`, `airgradient`, `purpleair` | sensed | 15 µg/m³, the WHO 2021 24-hour mean |
| heat | `heat`, `surface-heat` | sensed | 35 °C apparent, measured at node #1: this place's line, not a global one |
| land | `earth` (the change), `earth-engine` (built, trees) | context | none, because a year-over-year change is not a threshold |
| coast | `coast`, and the wild pack `posidonia` | context | none |
| water | `terrain` | context | none yet: it waits for a household to say how much rain is too much here |

| pack | domain | what it is to the issues |
|---|---|---|
| `forecast` | weather | feeds air and heat |
| `place` | place | the ground, with its own band on the dashboard |
| `open-data-health` | governance | the loop and the Index |
| `thingdata` | repair | a catalogue of repair knowledge somebody maintains |
| `make` | make | the nearest fab labs, as places; no metric, no rule, no cell |
| `home-assistant` | none | carries what the node stores and sends; no rule, no cell |
| `things` | things | what the home keeps and offers; no rule, no cell |
| `eyes` | species | the household's pictures and what is in them; no rule, no cell |
| `insight`, `cold-start` | cross-domain | each rule belongs to the issue it names |
| `example-cooking-hours` | none | its one rule belongs to air |

A sensed issue has eyes on it and rules that can ask somebody to do something. A context issue informs and never
asks: it has no act-level rules, and land's cadence is a year.

The declarations are one `issue.yml` per issue, in the pack that watches it: `packs/air-quality/issue.yml`, `packs/heat/issue.yml`, `packs/coast/issue.yml`, `packs/earth/issue.yml` (land) and `packs/terrain/issue.yml` (water). An issue is read while its pack is on. Each holds the issue's name in three languages, its
metric and unit, its line and that line's source, which packs feed it, how each of the four distances is computed
(`room`, `yard`, `ring` and `region`, printed on the page as house, street, ring and region), and its sentence
templates, each marking with `|` where its title ends and its tagline begins. A sixth issue is a sixth file plus a
pack that declares its domain. `tests/test_issues.py` checks that by loading a synthetic tap-water issue, and it also
checks that every enabled pack's alerts reach an issue or the pack is named as deliberately not one, so a new alert
cannot arrive unmapped.

`NODE_ISSUES` is the keeper's order, most important first. The presets guess per place (Bali
`air,heat,land,coast`; Menorca `coast,heat,air,land`; Barcelona and Boston `heat,air`; Delhi and Santiago
`air,heat`), and every preset says to change it. What matters in Serangan is for the people in Serangan to decide,
whichever pack was written first. An issue the keeper has not declared is still shown, greyed, so a stranger can
see what the node could report.

`GET /issues` is where all of it comes out, and the `issues` MCP tool returns the same object, so an agent and the
household describe the same evening in the same words.

## The shape of any domain

Every domain has the same four parts:

1. **Sources**: sensors you own, public references nearby, a model as fallback. The adapter contract is on the
   sensors page.
2. **A local number**: what your sensors say, indoor and outdoor kept apart.
3. **A comparison**: yours against the street, the street against the model. The gap is the local signal.
4. **A decision**: one sentence someone can act on, with the threshold's source named.

Air came first because Bali has the sensors and the burning season. Every other domain follows the same shape.

## Running

| domain | packs | what it reads |
|---|---|---|
| air | `air-quality`, `nearby`, `season`, `bali-air-dispatch` | PM2.5 inside and outside, spikes, WHO and US EPA lines, the public stations around the node |
| air | `fire` | NASA FIRMS fires near the node, crossed with the wind |
| air | `smartcitizen`, `airgradient`, `purpleair` | this house's own kits and monitors |
| heat | `heat` | apparent temperature from temperature and humidity, heat stress, nights over 28 °C |
| heat | `surface-heat` | the ground's temperature from Landsat and MODIS |
| coast | `coast` | waves and sea temperature |
| land | `earth`, `earth-engine` | change, built-up, tree cover |
| water | `terrain` | where the next day's rain goes, from the ground's shape and the forecast |
| governance | `open-data-health`, and ρ in the core | the loop and the Index |
| trust | the core (`config/rules.yml`) | the node's own instruments: whether they are frozen, missing hours or disagreeing with a neighbour |

## Not written yet

Water quality, energy, noise and classroom CO₂ have the same shape and no pack yet. What each would watch and what it
needs is on [Packs](site/packs.md#packs-nobody-has-written-yet).

## Writing one

Copy `packs/heat`. Change the metrics, the thresholds and the messages. Say in the README where the thresholds
come from and which place you wrote for. Run `make lint`, and you have a domain pack.
