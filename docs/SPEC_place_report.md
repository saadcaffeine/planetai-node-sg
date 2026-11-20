# SPEC: the Place report, a sheet and a few pages to print

*Asked, 11 November 2026, by Tomas: "I want to build a tool for the place section to provide the options for people to
download their place analysis similarly to this tool that is published online here: https://urban-scan.ildar.space/app.
I also want for the place section to be able to provide the download of reports, similarly as we do in the index page
per city, when we allow people to download a report as pdf." Of the two scopes offered, he chose the small one: "Spec the
one page". It goes in v0.92.*

**Status: proposed 11 November 2026, its four open questions decided by Tomas the same day (§10). Steps 1 to 3, the sheet,
the report pages and asking for it, are built, from 16 November 2026. The reading (§11) is built from 17 November 2026. The pane tool is `place_report`: a function call
cannot carry a dot, so the Tools menu's `place.report` is spelled with an underscore there.**
Each step in §9 is its own pull request, run on node #1 before it merges.

## 1 · What it serves

Place already lets a household download what is on its screen: a PNG with the scale and the credits drawn into it, and
each of its named maps as GeoJSON, KML and DXF (SPEC_place_microgis §4). None of that is something you can hand to the
neighbours, the banjar, a council or a funder. The Fab City Index has that for a city: a report page that prints, or
saves as a PDF, from the browser (index.fab.city/report).

This spec gives Place the same. One page on the node, opened from the Download menu, holds:

- **the sheet**, the map on the screen drawn as a plan, with a frame, a grid in metres, a scale bar, a north arrow, a
  legend, the coordinates and the credits;
- **the report**, a few pages after it, with the place in figures, what the node holds about its place and what it
  does not, what changed year on year, and the sources with how to cite them.

The browser's own print turns it into paper or a PDF. The node's server gets nothing new, and no PDF library comes in.

## 2 · What urban:SCAN does, and what this takes

urban:SCAN (urban-scan.ildar.space) is a site analysis tool in four steps: territory, analysis, graphics,
download. Its Graphics step is the reference here, because what you set on its map is what its PDF uses.

| urban:SCAN, Graphics | Here |
|---|---|
| Thirteen graphic styles (Neon, Paper, Nolli, Noir…) | Two registers: **Paper**, the node's light palette (`PAL.light`, already in doors-placemap.js), and **Screen**, the black one Place draws in. Paper is the default because it prints. |
| Layers on, off and in order | The cake's switches as they are on the screen. The sheet draws what the screen draws. |
| Grid, frame, scale bar, north arrow, legend, coordinates | All of them, fixed, always on. There are no switches for them. |
| Markers with captions | Already on Place: the drawing keys (marker, line, area, note) and the named maps. |
| Colour editor | Left out. |
| Sun path | Left out until Sun and shade is a tool (SPEC_place_analyses step 3). |
| 3D scheme, exploded layers | Left out. It needs a 3D view Place does not have (the map is flat, `maxPitch: 0`) and its own spec. |
| PDF, SVG, PNG, TIFF, KMZ | PDF through the browser's print. PNG, GeoJSON, KML and DXF stay where they are. SVG, TIFF and KMZ are left out: KML already opens in Google Earth, and a GeoTIFF is a raster the node does not compute. |
| Its analyses (heat island, flows, housing value…) | Not taken. SPEC_place_analyses decided which analyses Place runs and turned the others down under the open rule. Each one that lands later adds its colour ramp to the legend (§4). |

## 3 · The page

**Where it opens.** The Download menu on the screen's right edge gets one more line, under Everything on the screen:
**Report, to print or save as PDF**. It opens `#place/report`, a view inside doors.html, so the page keeps the node's
data, its token and its helpers.

**What happens on the press.** The page takes the picture first, then opens the view:

1. It switches the map to the register chosen (Paper the first time), waits for the map's `idle`, and keeps a copy of
   the canvas, the drawings included, as the PNG download already does (`screenImage()`, without its dark strip).
2. It puts the map back in the black register, so Place looks the same when you come back.
3. It opens `#place/report` with that picture and the map's bounds, zoom and scale rung.

The sheet is whatever the screen was showing: the rung in view (Street, Block, Cell, Village, District), the layers on,
the satellite or the streets, and the maps shown. There is no separate extent picker. To print the seven cells, go to
Village and press Report.

**On screen**, the view has one bar at the top: **Paper · Screen**, **Print or save as PDF**, and **Back to Place**.
Under the bar are the pages, as sheets on a grey ground, as the Index's report shows them. A change of register goes
back to the map, takes the picture again and returns. On a phone the sheets fit the width and the bar wraps.

**In print**, the bar, the doors' top line, the side menu and the Ask pane are hidden. The sheet is A4 landscape and the
report pages are A4 portrait, through named pages (`@page sheet { size: A4 landscape }`, `page: sheet`). A browser
without named pages prints everything portrait and the sheet scales to fit, which is acceptable.

## 4 · The sheet

One page, laid out like urban:SCAN's Map tab: the map on the left in a black frame, a column on the right.

- **The map**, the picture from §3. It is north-up, because Place never rotates.
- **The grid in metres.** Lines across the map at a round step (1, 2, 2.5 or 5 × 10ⁿ m) that gives five to eight lines
  on the longer side. With 1, 2 and 5 alone, a side of 1.6 to 2 × 10ⁿ m has no such step. Each line is labelled from
  0 m along the left and the bottom edges, with a small cross where two lines meet. The metres come from the map's own figure for the zoom (`mPerPx`), already used for the scale bar.
- **The scale bar**, under the map: the same round length the PNG uses, drawn as alternating black and white blocks.
- **The north arrow**, fixed, because the map is north-up.
- **The legend**, in the right column, top to bottom:
  - the title, the node's name, then "Place" and the rung ("Cell, res 8");
  - each layer that is on, grouped under its cake section in the cake's order (doors-cake.js `cakeSections`), with
    its name and its source;
  - each named map shown, with its colour from the node's palette;
  - an analysis's colour ramp, its unit and its two ends, once Place has an analysis (none yet).
- **The coordinates line**, under the legend: the centre of the node's res-8 cell to four decimals (the point
  `/health` publishes), the sheet's width in kilometres, the grid step, and the cell's id.
- **The credits**: `creditList()`, the same words the screen and the PNG carry, plus "Made on PLANETAI <version>,
  <date>" and the node's name.

The sheet is drawn as HTML and one SVG over the picture (the grid, its labels, the crosses, the scale bar and the
arrow). The picture is the canvas at the screen's pixel ratio, about 150 to 200 dpi from a laptop screen. If a large print
looks soft, the next step is to render the canvas off-screen at print size.

## 5 · The report

Up to four pages after the sheet, each with a head line (node name · Place report · page n of N), as the Index's pages
have. A page with nothing to say is left out, so N is counted from what is there.

1. **The place in figures.** The rows of Place's lower band (`#pfigures`): the issues' yearly figures, Rivers, and the
   city's Fab City Index row with its link to the city's own Index report
   (`index.fab.city/report?locality=<place>`), which says the rest about the city. The rows come from the same
   functions that fill the band, called into the report. They are not copied as HTML.
2. **What the node holds about its place.** The cake, section by section (`cakeSections(LAYERS, PM.on)`): each row
   held, held in part or not yet, with its source and, where a row is empty, the command that fills it, as the cake
   says it on screen. This is the inventory, and it shows its gaps the way the Index's DIDO shows a city's.
3. **What changed, year on year.** The satellite then and now and the hectares that changed (`#pchange`, from
   `GET /earth`), and the buildings the satellite counts, a bar a year (`GET /history`). Left out on a node with no
   satellite years.
4. **Sources and how to cite.** Every credit the sheet and the pages owe, with its licence as the node already words
   it (`creditList()`, `D.earth.credit`, the hydro and Index lines). One short line says that a map made from
   OpenStreetMap is a Produced Work under the ODbL, so it carries the credit and nothing more. Then a citation line:
   "<node name>, Place report, cell <res-8 id>, PLANETAI <version>, made <date>."

Each figure keeps its provenance word (live, partial, model, cached) as `prov()` draws it on screen. A report that
dropped them would be making the numbers look surer than they are.

## 6 · Privacy

A report is made to leave the house, so it follows SPEC_eyes §2: the house's own res-10 cell blurs on anything that
leaves. It holds less than the PNG of the screen, which still draws the kit at its point.

- **With the token**, the sheet draws what the screen draws, except at the house. The outdoor kit, and any image taken
  inside the house's res-10 cell, are drawn as that cell, filled, never as points (Tomas, 11 November 2026: yes, blur
  it even with the token). The cell's outline comes from `GET /geo/cell?res=10`, since the page carries no h3-js.
  Drawings stay as they were drawn: a marker someone placed on the house is their own choice.
- No text on any page is closer than the res-8 cell: the coordinates line is the cell centre, never the house's point.
- **Without the token**, Place draws no map of the house (SPEC_place_microgis §8). The sheet says so in the node's own
  sentence, where the map would be, and the report pages carry what a tokenless screen sees: the cake's rows with
  their sources and the yearly figures.
- **Never on any page**: rooms, indoor sensors, the species list (token-only and the household's), the photos' own
  locations, `.env` values or the node's key. The node ID may appear, since `/health` publishes it.
- Nothing is sent anywhere. The PDF is made by the browser, on the household's own machine.

## 7 · What exists and is reused

- `app/static/doors-placemap.js`: `screenImage()`, `creditList()`, `mPerPx`, `SCALES`, `LAYERS`, `PAL.light` and
  `style(p)`, the Download menu (`dlMenu`).
- `app/static/doors-cake.js`: `cakeSections`.
- `app/static/doors-place.js`: the figure rows (`figures()`, `indexRow`, the hydro row), `layer()` for what changed.
- The Index's report (fci-3-prototype `report.html`, `js/report.js`, `css/report.css`) for the page layout and the print
  CSS: the sheets on screen, `break-after: page`, the head line on each page. Only the approach is copied: the node's
  CSS uses its own tokens.
- Nothing new on the server. No endpoint, no table, no schema change, no setting.

## 8 · Tests

- A lifted-function test under tests/, named for this page (test_place_report.py): the grid step for widths from 50 m to 40 km, which must give
  five to eight lines; the legend's rows and their order for a fixed `LAYERS` and `on`; the page count when pages are
  empty; that no page's text holds the house's point (node #1's capture as the fixture); and that the sheet's layers
  hold no kit or image point inside the house's res-10 cell, only the cell. The JSON goes in through
  stdin, never argv, because of the 128 KB limit on Linux CI. Its line goes in `tests/all` and the count goes up by one.
  Only one branch at a time may change that count (NEXT_RELEASE rule 1), and the energy and seven-cells branches both
  add suites, so this one waits its turn.
- The visual gate gets a `report` stage: `#place/report` with print media emulated, checked at A4 for the sheet's
  frame inside the page, the legend not clipped, and no page overflowing onto a blank one.
- Node #1 on the branch before merge (the standing rule): print it to PDF from its own screen, at Cell and at Village,
  on Paper and on Screen, with the satellite and with the streets, and once without the token.

## 9 · Steps

1. **The sheet.** The Download line and a Tools menu row (`place.report`, opening the same view), the register switch with the picture taken, `#place/report` with the sheet, the
   print CSS, the test, the visual gate stage, the docs.
2. **The report pages.** The four pages of §5 under the sheet, and the test's page-count cases.
3. **Asking for it.** "Make me the place report" in the Ask pane. Place's command registry (`GET /place/tools`,
   SPEC_place_microgis §6) is not built yet, so the first form is one pane tool, `place_report`, in
   `agent_loop.PANE_PAGES`: the pane's own tools that open a view of the page. It runs nothing on the node, so it is
   not on `/mcp` and has no `TOOL_CLASS`; `/ask/status` lists it as class `page`. It is offered only on a screen holding the token, takes the register
   (Paper unless asked otherwise), and answers with the link to `#place/report`, which the pane draws as a button. The
   person still presses Print: the agent never makes the PDF. When the registry lands, the tool moves into it. The
   Tools menu on Place lists it from step 1, with its id, so the command is visible before the agent can call it.

Each step lands with its line in the CHANGELOG, a section in `docs/site/place.md` ("Print the place, or save it as a
PDF") with a picture of the sheet taken from node #1, and the milestone v0.92.

The one non-goal line in SPEC_place_microgis §2 that said "no print layouts" now says what it meant: no layout
designer. Place has this one fixed sheet. A designer, if one is wanted, is the fab lab node's (SPEC_fablab).

## 10 · Decided, 11 November 2026

Tomas answered the four open questions of the first draft: "1. yes, 2 light, 3, yes, yes".

- **The house on a sheet that leaves:** blurred to its res-10 cell even with the token (§6).
- **The default register:** Paper, the light one (§3).
- **Asking for it:** yes, as step 3 (§9).
- **3D:** its own spec, later. urban:SCAN's 3D scheme is a tilted, exploded view of the layers; on the node it would be
  the cake's sections on deck.gl, then a PNG of it on a page of the report. Nothing in this spec waits for it.

## 11 · The reading (17 November 2026)

*Asked by Tomas, 17 November 2026: "We want the report to provide a human analysis beyond the machine readings, and to
suggest avenues to improve the locality, including inside the kind of actions we are mapping out as fab city." Decided
the same day: "Rules, then model", and "On the node, kept".*

Two pages come after the sheet and before the figures.

**A reading of this place** has five sections, always in this order: the region it belongs to, what the land allows,
what people here need, how the place behaves, and the life of the street. **Ways to improve it** has four to six
avenues. Each has a title, a reason with its figures, a first step, the nearest lab when the node knows one, and its
place in Fab City's frame for action: one of the seven layers of the Full Stack (infrastructure, learning,
value-generating projects, communities, place-based interventions, bioregional strategies, global networks), one of
the Implementation Guide's three key actions (map and research, experiment, rethink) and one of three signals
(socio-spatial, bioregional, asset). The page ends with what the reading cannot see, each gap with what fills it.

- **The facts.** `app/reading.py` gathers the place-scale figures the node holds into one document: what the place
  pack counts within a kilometre, the surface heat, the terrain, the rivers and basins, the grid's mix, the city on the
  Index, the labs within 50 km, the node's held cells, and the days its own outdoor sensors measured over the WHO
  guideline for a day (stated only with 30 measured days). A number in the reading comes from this document and from
  nowhere else. A figure older than 400 days counts as not held, except a yearly source, which has 800, and the
  terrain, which is computed once. The place pack writes the nearest school, clinic or market only when it finds one
  within its radius, so a distance older than the pack's last run is dropped, and none drawn within the radius is a
  finding the reading states, not a gap. The packs are read in process, and each held figure's pack is credited on the
  sources page.
- **Precision.** The report leaves the house, so §6 holds: every distance from the node's point is a whole kilometre,
  and the document carries no name and no point.
- **Rules.** `rules()` writes the reading on every node, with no model and no network. A rule whose facts are missing
  does not fire, and a sentence says no more than its figure does: a count from the public map says so where the map
  is thin, a yearly count carries its year and is held only when its last year is within three times the satellite's footprint count for the same circle, and the words fit any node anywhere. Where fewer than four avenues fire, the gaps supply the rest as things to map and research, which is
  where a place that is starting begins.
- **A fuller text.** `POST /place/reading`, with the admin token, asks a model for the same two pages. Only a model on
  the house's own network is asked, never an online one and never the small local one. The node keeps the text only
  with the five sections, four to six avenues in the frame, each resting on a figure, no person named, each part
  short enough for its page, no quantity in words, no figure that is not in the facts, and no section that gives back
  more than half of the sentences of the node's own reading (the model is handed that reading as findings, and on node #1 it first returned it word for word). A count from one to seven
  passes bare ("2 of its 7 cells") and never before a unit. The check reads whether a figure is the node's, not
  whether it is said of the right thing, which is why the page says a model wrote it. A text that fails is asked for once more, with the reason. If that fails too, the node stores the
  reason and its own reading stands. What the reading
  cannot see is always the rules' to say.
- **Kept.** A model's text is stored with the facts it was written from (`place_readings`, schema 0.66) and shown until
  another is written. The node's own reading is never stored, so it cannot disagree with the facts.
- **Who reads it.** `GET /place/reading` answers this machine or a token, like `/place/cells` and `/hydro`. A report
  opened without the token has no reading pages.
- **Who wrote it.** Under each title the page says so: this node, from its own figures, or a language model on the
  house's network, with its name, and the date. A page a model wrote never passes as a person's.
- **Its length.** A page is one A4 sheet. The node's own avenues fit with what it cannot see. A model's avenues past
  four go on a page of their own.

The thresholds in the rules are first guesses, tuned on node #1's own reading.

## 12 · The report, offered (17 November 2026)

*Asked by Tomas, 17 November 2026: "the report download should be more visible in the bottom of the place tab, explaining
what the report does (it is for consumption, so do not mention the names of experts behind it)."*

The last block of Place, after What changed and The place in figures, says what the report is and opens it. It has a
line on who the report is for, a line on what is in it, and a line on how it is made: the browser prints it, nothing is
sent anywhere, and the house is drawn as a blurred cell. **Open the report** opens it on Paper and **Dark version** on
Screen. A screen without the token reads, in place of the last line, the sentence the sheet itself uses for the map of
the house (§6). Beside the buttons, on a screen holding the token, one line says who wrote the reading and when (§11). The Download menu's line and the Tools row stay. The block is hidden with the rest of Place while the
report is open, and it is never printed.
