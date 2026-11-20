# The Place door
<!-- checked: v0.92.0 -->

Place is the ground around the node as a small GIS, built like a layer cake: the sky at the top, the ground at the
bottom, and between them a map drawn from data the node keeps on its own disk and geometry it computes itself. It is
one of the five doors on the [dashboard](dashboard.md). Nothing from inside the house is listed or drawn here.

Five packs feed the ground. The `place` pack fetches everything within `PLACE_RADIUS_M` (1,000 m) from OpenStreetMap
into PostGIS and summarises it monthly: buildings and the ground they cover, shops, schools, clinics, kilometres of road,
the share of green, the walk to the nearest of each. With credentials, `earth-engine` adds Google Open Buildings
footprints and the yearly building count since 2016; `earth` adds the AlphaEarth year compare, `terrain` the
Copernicus DEM, and `surface-heat` the ground's heat from Landsat and MODIS. The `hydro` pack adds the rivers and
basins, the `energy` pack the power grid, and the `index` pack the city's row on the Fab City Index.

## Turn it on

The place pack runs code, so it needs the switch once. If Set up › Packs loads only some packs, keep `place` among
them first, or the commands below install libraries for a pack that never polls:

```bash
planetai config set PACKS_ALLOW_CODE 1   # or Set up › Packs, which asks once before saving a key that runs code here
planetai packs install                    # builds every loaded pack's libraries into the image, once
planetai restart
planetai run place verify                 # PostGIS, OpenStreetMap, Earth Engine, Open Buildings: each step named
planetai run place basemap                # the street map, kept on the node's disk
```

The first poll fetches the kilometre from the Overpass API; later polls recompute from what is stored, and every
`PLACE_REFRESH_DAYS` (30) it fetches again. `planetai run place refresh` forces one, and counts the satellite's buildings again as well. Every command and
setting is in [the place pack](packs-reference.md#place).

## The head

The head gives the cell's id, resolution, edge and area, and the node's position for a
screen with the token. Under it is a line to ask the node about this place (press `/` to get there; `UI_ASK=off` removes it) and
**Tools**. Below that are the layers on the left and the screen beside them.

Once a Fab City Index place is chosen and read, the head has one more line: the place, its label and its FCI or range,
and **its figures**, which goes down to the full row in the place in figures.

## The layers

On the left is a list of what the node can show about the ground around the house.
The sky is at the top of the list and the ground at the bottom. Its headings, in order, are results, microclimate,
flows, built, animals, plants, soil, water, ground and frame, and each says how many of its rows are on, or none yet.
The list opens with a line that says what a press does. A row is one line with a switch, a name and a word for where
it comes from. The switch is filled, with its knob to the right, when the row is on, and hollow, with its knob to the
left, when it is off. A row that cannot switch has a dotted mark where the switch would be. That is a row this node
does not hold yet, with its source beside it, such as canopy, soil, terrain, geology, the flows log, or samples of soil
and water, and also a row that is not here or needs the live map. A row that waits for the token has a dashed mark. Under a row that is on, a slider marked opacity sets how strongly it is drawn.
Press a row to switch it on or off. The line under the screen then says what the row draws and where it comes from,
and if the row cannot draw, why: **token-only**, **not here**, **live map**, or **zoom in** and **zoom out**. Six rows
start on: this house's outdoor kit, the public stations, the species, the cell the node stands in, the street map
and the images. Once the hydro pack has fetched them (`planetai run hydro fetch`), two more rows wait under water:
Rivers draws them wider with each order and Basins the level-12 basins, the node's own brighter, and a tap on a
river gives its flow, the ground it drains and how far it runs to the sea. With the energy pack on, **Power grid**
waits under built: the grid's plants, sized by what they can make, its substations and cable heads, and the node's
seven cells with how many MW are made in each. Its line counts the plants and substations on the grid and says how
far the nearest one is. The points and the cells need the screen's token. Nothing from inside the house is listed or
drawn on Place, and neither are the rooms.

## The screen

In the middle is the map, on a black screen that stays black on the light page and the dark one. It
opens on the satellite where the node holds it, and a switch at the bottom right changes the base. The satellite is
Sentinel-2 at 10 m, so from Block scale in the street map takes over, with a drone flight on top where somebody flew
one. Zoomed out, a pin
marks each drone flight the node holds. The hour is a pill at the top, the node's last reading, or the wind's hour when
the wind is on. The scale rungs, street, block, cell, village and district, are at the bottom left and the credit at the
foot. A cell that may leave the machine is dotted. On the right edge are **Map only**, **Full screen**, back to the
node's cell and **Download**. The keys on the screen are 36 px with a mouse and 44 px on a touch screen. On a narrow
screen the rungs show only their number. Narrower still, the base switch moves above them and the hour above the zoom.

## Drawing

With the token, the keys on the screen's left edge are **Select** (V), **Marker** (M), **Line** (L),
**Area** (A), **Note** (N), **Image** (I) and **Undo** (⌘Z or Ctrl+Z). They stand under the word Draw, and each shows
its icon, its name and its letter, and Undo's is Ctrl+Z off a Mac. On a screen narrower than 760 px the names fold away and the letter sits in the
key's corner. Each press on the map adds a point, and a marker
or a note is done with one. A line ends on a double press, an area when you press its first corner again. Enter adds a
point at the map's centre, and Enter again without moving finishes the shape, so the keyboard alone can draw. Backspace
takes a point back, Esc drops the shape. The readout beside the keys is a small chip with the tool, the open map, a dot
in the colour and the length or the surface as you draw, then the node's own measure once it is kept. Press the chip
for the six colours and a line on what to do, and press it again or Esc to fold them. With Select, press a drawing
for its label, note, colour and image, and the colours open by themselves. Press a
point and then its new place to move it, or use the arrows, with `.` for the next point. An image stays on this node,
the map only says which one.

## Your maps

**Your maps** sit at the top of the left column. Every drawing goes into one, kept on this node, and each drawing,
change, download and share is a row in the ledger on Data. **Download** gives the screen as a PNG with its credit and a
scale bar, and the open map as GeoJSON for QGIS, KML for Google Earth, or DXF for CAD in metres, in the node's UTM zone.
**Everything on the screen** gives the PNG and each map on the screen in all three. **Share** sends a map to the node
upstream. The first press says what goes, every drawing at its exact place with its labels, notes and measures, and
who can see it upstream. Upstream the node is the map's owner, and who drew each drawing stays here. The second press sends it. If a drawing touches the cell the house stands in, a shared map stops sending until
you press Share again. **Stop sharing** ends it, and this node asks the node upstream to delete the map.

**A photo on a shared map** goes up as words. The node upstream gets what took it, its note, the words you gave it on
Data › Images and the day it was taken, and the picture stays here, with where it was taken and who took it. The node
upstream can ask for the picture. The ask reaches this node within the hour and sits at the top of your maps, with who
asked and for which drawing. **Send** gives them the picture once, **No** keeps it here, and both go in the ledger.
Unshare the map, take the image off the drawing or delete the photo, and the node upstream deletes its copy.

On a node that takes maps from others, a child's drawing with a photo says what the photo is, and **Ask for the photo**
asks for it. It comes when somebody there presses Send, and only the people with this node's token can see it.

To answer an issue from Now, open the drawing's form, choose the issue, say what you did in your own words and press
**Tie it**. The rain garden you drew then counts as what you did about it, as Done does on Now.

## Print the place, or save it as a PDF

At the foot of Place a block says what the report is and opens it: **Open the report** for the light sheet and
**Dark version** for the black one. **Report, to print or save as PDF**, the last line in **Download**, opens the place
as a sheet to print, with the pages of the report after it. **Place report** in Tools opens the same. The sheet is what the screen showed when you pressed it: the scale in view, the
layers that are on, the satellite or the streets, and the maps on the screen. To print the seven cells, go to Village
first.

The map sits in a black frame with a grid in metres, labelled from 0 m along its left and bottom edges, a scale bar
under it and a north arrow. Beside it are the node's name and the scale, each layer that is on under its part of the
layer list with where it comes from, your maps on the screen with their colours, the centre and id of the node's res-8
cell, the sheet's width, the grid's step and the credits.

The pages after the sheet are A4 upright, and each has a head line with the node's name and its page number.

1. The place in figures. These are the rows under the map on Place, with the yearly figures, Rivers and the city's Fab
   City Index row. Where the Index has read the city, a line gives the address of the city's own Index report.
2. What the node holds about its place. Each row of the layer list stands under its heading as held, held in part, not
   yet, or withheld without the token, with where it comes from and, for an empty row, the command that fills it.
3. What changed, year on year. The satellite then and now, the hectares that changed and the buildings the satellite
   counts, a bar a year. A node with no satellite years has no such page, and the pages are counted without it.
4. Sources and how to cite. Every credit the sheet and the pages owe, with its licence, then a line to cite the report
   by, with the node's name, its res-8 cell, the PLANETAI version and the date. When the map comes from OpenStreetMap,
   a line says that it is a Produced Work under the ODbL, so it carries the credit and nothing more.

Each figure keeps its word, live, partial, model or cached, as it has on Place.

You can also ask for it. Type "make me the place report" in Ask, on a screen holding the token, and the answer has a
button, **Open the Place report**, that opens it. Ask for it on Screen and it opens on Screen. You still press Print.

### The reading, and ways to improve the place

On a screen holding the token, two pages come before the figures.

**A reading of this place** says what kind of place this is, under five headings: the region it belongs to, what the
land allows, what people here need, how the place behaves, and the life of the street. Each sentence rests on a figure
the node holds, such as the basin the rain leaves by, how much of the grid's power is burned, the green ground within
a kilometre, or the buildings the satellite counts against the ones on the public map.

**Ways to improve it** lists four to six things worth doing here. Each has its reason, with the figures, a first step
that a household, a neighbourhood council or a lab can start this month, and the nearest lab when the node knows one. Under its title
each carries a layer of the Fab City Full Stack and one of its key actions: map and research, experiment, or rethink.
The page ends with what the reading cannot see and what fills each gap. A node that holds little is given four things
to map first.

Under each title a line says who wrote the page and when, and the block at the foot of Place says the same in one line. Every node writes its own reading from rules, with no model
and no network. When Set up › Model has a model on your own network, the report's bar shows **Write a fuller reading**
to a screen holding the admin token. Press it and the node asks that model, which takes a few minutes. The node keeps
the text only if every figure in it is one the node holds. If not, it says why, and its own reading stands. The node
does not send this to a model outside your network, and the small model on the node itself does not write it.

Distances in the reading are whole kilometres, and what comes from the public map covers a kilometre round the node,
so nothing in it is closer than the res-8 cell. A report opened without the token has no reading. The sources page
credits each pack the reading rests on.

**Paper** draws the map in the light palette, and the sheet starts there. **Screen** draws it black, as Place does.
Changing it goes back to the map for a moment to draw it again. **Print or save as PDF** opens the browser's print with
A4 already set, landscape for the sheet and upright for the pages, and Save as PDF there gives you a file. Nothing is sent anywhere. The browser makes the PDF on
your own machine. **Back to Place** returns to the map.

The house is blurred on the sheet, even with the token. Your outdoor kit, the model points and any image taken inside
the house's res-10 cell, about 130 m across, are drawn as that cell, filled, never at their points. The rings are left
off, because they are drawn around the house. Your drawings stay as you drew them. No text on the sheet is closer than
the res-8 cell the node publishes, on the sheet or on any page, and no page lists the species found here. Without the
token there is no map of the house, and the sheet says so where the map would be. The pages then carry what the screen
shows without the token: the layer list with its sources and the yearly figures.

## Folding

The layers fold by the arrow on their edge, or `[`, into a strip with their name. `\` or **Map only**
folds them and the screen takes the window, and **Full screen** or F takes the whole display. This browser remembers
the fold. On a phone the keys run along the bottom of the screen.

## What you selected

Under the screen one line says what is in view. Press a station, an image, a place to make or a cell and the line
gives its facts, and with the token how far it is from the node and which cell it is in. A station of this house says
it counts toward the cell; a public one is shown and never counted. Below it is the list around the house, nearest
first, with the distance in metres measured by the node (`GET /geo/measure`, and `GET /nearby` for public stations).

## The seven cells

The node stands in one resolution-8 cell, and six more touch it. Its own cells are the one it stands in, its home, and
the neighbours you claim. A sensor of yours counts as this node's own only inside them.

At Cell scale, with the token, the Node cell row draws the seven. Home and the held cells have a solid line, a claimed
cell a dashed one, and an open cell a grey dotted one. Press a neighbour and the line under the screen says its state,
with **Claim this cell** on an open one and **Release it** on one that is claimed or held. Home is always the node's
and has neither. A claimed cell is held once one of the node's own sensors has a reading in it in the last 24 hours,
and goes back to claimed after a day with none. The node works this out each time it is asked and never stores it.
A kit in a cell you claim counts from its next poll, and stops at its next poll after you release the cell.

The line under the screen also says how many of the seven are held, home among them. Each claim and release is a
row in the ledger on Data.

The first time a node runs with the seven, it claims each neighbour where one of its sensors stood within 500 m of it,
the old line, so no sensor that counted before stops counting.

## The tools

**Tools**, beside the ask line, opens a menu of what the node can do with this place. **Rings and
distance** draws the 2, 5 and 15 km rings from the node's point. **From the house** measures from the node's point to
any point you press. **Pull** asks the node what it holds about an area: press cells at the scale in view, press one
again to drop it, or choose one of your drawn areas, then press **Pull**, up to 500 resolution-8 cells. The answer
comes under the screen. First the node's own sensors, read only in its home and held cells, then the neighbouring
nodes' sensors, which no node sends yet, then one block for each pack that answers for an area. Hydro gives the rivers
and basins it keeps. Eyes, with `SPECIES_MATCH=on`, gives how many open records GBIF holds of each species there, and
sends GBIF the area's outline. Forecast, with `FORECAST_OPENMETEO=1`, gives the next 24 hours at the area's centre,
and sends Open-Meteo only that point. A block with nothing says why, and a pack that is off says so. **Place report** opens the sheet to print, as
Download's last line does. The four that run come first, and the rest carry a dotted **not yet**. Choosing one closes the
menu, and so do Esc and a press outside it. A screen without a token reads "Tools run on this node with a token.
Unlock this screen in Set up." in the menu. On a phone the layers open from a bar under the screen as a sheet, and Esc
closes it.

## What changed

Under the screen, across the whole page, is what changed year on year. The satellite then and now sit side by side,
large, with the hectares that changed between them and a bar a year for the buildings it counts. On a phone the two
pictures stack. Below that, **The place in figures** runs across the page, three to a row on a wide screen: land
and coast, the place's row on the Fab City Index, the Index cells, the rivers, and what is not here yet.

**Rivers** is there once the hydro pack has fetched them, with the screen's token. It says how far the nearest river
is, how much water it carries on average and how far it still runs to the sea, and the same for the largest river in
the square. **on the map ↑** turns on the Rivers and Basins rows and takes the map out to District scale, where the
nearest river is in view. Before the fetch the row says `planetai run hydro fetch`. The same seven figures are in
Data › Models and satellite, under "Rivers within 25 km".

**Fab City Index** is a row in that band, under land and coast. It names the place this node belongs to, which
`planetai place` chooses, with the label the Index gives its score (**Partial** or **Simulated**), and then the Index's own
number for it: the FCI, or, while no cell of the place is measured, a range. Under it come up to three of the place's
indicators, each with its year, its unit and its source line, cut before any link, because two of Barcelona's are both
called "Residual municipal waste per person" and only the source tells them apart. An indicator the Index sent without a
value is left out, and a figure it sent as empty is drawn as a dash. The small line says when the Index's file was read,
in this node's time zone, how many sources the registry files for the place, and links to the place on index.fab.city.
A read that failed says `last read` with the date of the file the node still holds, and when it tried. The numbers come
from the Index's own file for the place, which the `index` pack reads once a day and keeps on the node, so the page asks
the node and never index.fab.city. The node does not recompute them, and a range stays a range and is never drawn as a
score of 0. A portal's numbers are `partial` here, and `cached` when the last read failed; `live` is kept for what this
node measured. The count of sources is the registry's entries that name the place, and says nothing about whether this
node reads them. With no place chosen, or the pack not loaded, the row says **not chosen**, asks you to run
`planetai place` on the node, and links to how the Index counts a place (index.fab.city/method). With a slug the Index
does not track, a typo in Set up for one, the row says **not an Index place** with the slug and the same command. With a
place chosen and nothing read yet it shows the place's name, **not read** and **not read yet**. The row is the same at
every sharing level, and `GET /index/place` is where its source and registry details are.

## What needs the token

The grid, the rings and every distance are the node's own answers from `GET /geo/*`, and the plan is
`GET /place/geojson`; all of them need a token at every sharing level, because together they place the house. Without
the token, the house's marks say **withheld** where they would stand, the rows that need it say **token-only**, and the
map opens on the published cell. The street map comes from `/ground/*` once `planetai run place basemap` has run; until
then Set up lists **The map of this place** under what is left to finish.

## Images and species

**The Image key** (token only) adds a picture. Press the map, or Enter for its centre, and a marker holds the image you
choose from Data › Images or take as **A new photo**. With nothing pressed it also offers **A new photo** on its own.
A new photo opens a dialog with the file, what took it (phone, fixed camera, microscope, drone, balloon or kite), a
note and your name, and whether the image model on this node describes it. The image lands where its own GPS says it
was taken, else in the node's cell; the node strips EXIF and GPS from the file and keeps it.

**Species confirmed here** is the list under the species row: a table of what somebody here confirmed in an image,
how often, where, and GBIF's open records by others in the node's seven cells, token only.

## When the map is thin

Zeroes mean unmapped, not absent. Node #1 in September 2026 held 2,904 buildings, 540 road segments and 37 mapped
places within its kilometre, and no school, which is OpenStreetMap's coverage of the Bukit, not the Bukit.
`planetai run place gaps` writes `out/place-gaps.md`, a briefing for a mapping afternoon at the lab: the untyped
buildings, the categories with nothing, the named places without hours, the unnamed streets. StreetComplete, Every
Door and iD over Bing or Esri imagery fix the map, never Google's. `planetai run place refresh` brings the edits to
the node within minutes.

## Where this leads

The settings and commands behind this door are in [the place pack](packs-reference.md#place). What leaves the
machine, and at which sharing level, is in [Sharing](sharing.md); the answers the screen draws come from `/geo/*` and
`/place/geojson` in [the API](api.md). The other four doors and Set up are on [the dashboard](dashboard.md).
