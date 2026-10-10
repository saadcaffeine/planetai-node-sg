# The ground on MapLibre and deck.gl

**Question.** Should the ground under the cells be drawn by MapLibre GL JS (the base) and deck.gl (the cells and
stations), so it can pan and zoom, carry an offline vector base, and later carry wind, the earth pack's raster and
peers at scale? Phase 0 asks whether the two libraries are light enough and whether the class 0 bench can run
them. Phase 1 asks whether the map can match the svg ground before it gains anything new.

**Status.** Prototype, 6 October 2026, on branch `ground-map-proto-2026-10-06`. Phase 0 is answered and both of
its stop conditions pass. Phase 1 parity is built behind `UI_GROUND=map` (default `svg`), and the checklist
below says what holds and what does not yet. Phase 1b (the offline vector base) and Phase 2 (new layers) are not
built. Tomas has not decided anything here yet.

## Phase 0, measured

**Bytes.** The three vendored files, gzipped with `gzip -9`, measured on the files in `app/static/vendor/`:

| file | raw | gzipped |
|---|---:|---:|
| `maplibre-gl.js` 5.24.0 | 1,056,837 | 275,176 |
| `maplibre-gl.css` 5.24.0 | 70,024 | 10,094 |
| `deck.gl.min.js` 9.4.0 | 2,073,497 | 574,973 |
| **total** | **3,200,358** | **860,243** |

That is under the 1.5 MB stop line. **But the node serves `/static` uncompressed**: `app/main.py` has no
GZipMiddleware, and `curl -H 'Accept-Encoding: gzip'` on `/static/dashboard.js` comes back at its raw 580,609 bytes.
So the first load of the map ground is **3.2 MB on the wire**, not 860 kB, over a LAN. Adding gzip to `/static`
is a separate change that would cut that and the existing 580 kB `dashboard.js` alike. Every later load costs a
304 on each file (`no-cache, must-revalidate` with an ETag). The release tarball grows by about 860 kB.

MapLibre 6.x (current: 6.12.0) ships ES modules only, with no UMD build. The prompt asks for UMD and no build step,
so this pins **5.24.0, the last UMD release**. deck.gl 9.4.0's `MapboxOverlay` works with it, interleaved.

**WebGL2 on the class 0 bench.** Node #3 is the bench: `MacBookPro12,1` (early-2015 13-inch MacBook Pro), Intel
Iris Graphics 6100, Omarchy, default browser Google Chrome 153. Its Chrome reports `WEBGL2=true` with
`ANGLE (Intel, Mesa Intel(R) Iris(R) Graphics 6100 (BDW GT3), OpenGL ES 3.2)`, **without** `--ignore-gpu-blocklist`,
so the GPU is not blocklisted. Over Vulkan it reports `Vulkan 1.3.354 … Intel open-source Mesa driver`. Measured
headless over SSH. The desktop session itself was not driven.

**First paint on the class 0 bench.** A standalone page, served on the laptop from its own loopback: the vendored
libraries, node #1's plan (4,906 features), and the res-8 plate as deck.gl polygons, 600 × 600 px. It measures from
the first script to MapLibre's first `idle`. Three runs each:

| renderer | libraries parsed | first idle |
|---|---:|---:|
| Iris 6100, OpenGL ES 3.2 (ANGLE gl-egl) | 343–563 ms | 2,131–2,207 ms |
| Iris 6100, Vulkan (ANGLE) | 307–477 ms | 1,341–1,883 ms |
| SwiftShader (software, headless default) | 309–411 ms | 3,208–3,406 ms |

**Against the svg ground**, the whole dashboard was measured on this Mac rather than on the bench: node #1's live
page with this branch's `dashboard.js` swapped in by Playwright, Chromium on SwiftShader. Time from navigation to
the ground being drawn, eight runs per fixture (four widths × two registers):

| fixture | svg | map |
|---|---:|---:|
| `node1-2026-10-06-events` | 1,386–1,414 ms | 3,692–4,658 ms |
| `coast-led-2026-09-21` | 858–929 ms | 3,204–3,846 ms |

So the map ground costs about 2.5 s more under software GL. The svg ground's first paint on the bench itself was
not measured. That is the gap in this phase: a Playwright run on node #3 would close it.

**Verdict.** Both stop conditions pass. Phase 1 went ahead.

## What was built

- `UI_GROUND` (`svg` | `map`, default `svg`): a runtime, public setting in Set up → System, in `app/settings.py`,
  `.env.example` and `docs/site/configuration.md`.
- `app/static/vendor/` holds the three files and their licences, `NOTICE` names them, and `COMPANIONS` in
  `app/main.py` serves them by flat name: `/static/maplibre-gl.js`, `/static/maplibre-gl.css`,
  `/static/deck.gl.min.js`. `/static/vendor/…` and the licence files are 404, because the route takes a name.
- In `dashboard.js`'s ground module, `lead()` draws an empty `#groundgl` box when the setting is `map`.
  `route()` then calls `GROUND.mount()`, which checks for WebGL2, fetches the libraries once, and draws the map.
  - MapLibre draws the base. `plan` is `GET /place/geojson` as a GeoJSON source, drawn with kit-map's kinds,
    tokens and weights (`plan()` now keeps the raw body as `window.PLAN_GJ`, so there is no second request).
    `sat` and `osm` are raster sources on the same URL templates as `BASES`.
  - deck.gl draws over it with `MapboxOverlay`, interleaved: the plate's cells, the node's own cell, stations
    (own filled, others hollow), the node's point, kit-map's kilometre circle on the plan, and
    `geometry.claims`. Every ring is a `cells_ll` the node sent.
  - With no WebGL2, or a library that fails to load, or a map that errors before its first frame, the svg ground
    is drawn instead, with one line saying why.
- Gates: `tools/check_ui.py` fails a page that names `h3-js`, `H3HexagonLayer`/`H3ClusterLayer`, or calls an h3
  function, and it now sees `{ src: 'static/…' }` references written in script. `tests/test_check_ui.py` breaks
  all three on purpose. `tests/test_share.py` requires `/static` to serve exactly the three vendored files and
  refuse paths.

No route was added: `/issues` already sends every ring the map draws (`geometry.nav.plates[res].cells_ll`,
`geometry.claims[].cells_ll`), and `/place/geojson` already sends the plan in degrees.

## Parity checklist

Proved on node #1's live page (`http://192.168.4.190:8081/`), with this branch's `dashboard.js` and vendor files
routed in by Playwright, `/settings` amended to `UI_GROUND=map`, and the plan served from a copy of node #1's own
`/place/geojson`. Fixtures: `node1-2026-10-06-events` and `coast-led-2026-09-21` at 375, 768, 1440 and 1920 px, in
paper and dark. All 32 renders drew, and none sent a request off the node.

- [x] **The ladder re-derives the ground.** A press changes `?res=`, `route()` draws a fresh box, and the map
  mounts at the new plate. Seen at resolutions 7, 8 and 9. `?res=` survives because nothing here touches the URL.
- [x] **Struck and dotted rungs.** These belong to the ladder, which is not changed.
- [x] **plan / sat / osm and their cost labels.** The strip is unchanged and still priced by `frame()`. The live
  bases keep `frame()`'s zoom for its 600 px square, scaled to the box as the svg's percentages are, so the same
  tiles are asked for. Measured at resolution 7 on `sat`: **9 requests** to tiles.maps.eox.at at 768, 1440 and 1920
  px, the same as the svg ground and the label. **At 375 px the map asks for 4**, because MapLibre rounds to the
  coarser tile level. That is fewer than the label says, which the rule allows, but the label then overstates the
  cost. After the first frame the caption's tile count is replaced with the count actually sent.
- [x] **MAP_TILES gating.** `baseOf()` is unchanged, so a live base reaches MapLibre only when the strip offered it.
  A live base cannot be dragged or zoomed (`interactive: false`), because every drag would fetch tiles nobody
  priced. The plan pans and zooms freely.
- [x] **The plan needs a token.** Unchanged: the map reads the same `GET /place/geojson` body the svg ground read.
  Without it the plan has no buildings, and the svg ground's `NOPLAN` line is the answer there.
- [x] **The node-ground.svg fallback with no NODE_LAT/LON.** `lead()` returns `unsited()` before the setting is
  read, so an unsited node draws the svg grid as before and never loads the libraries.
- [x] **No WebGL2.** With Chromium's `--disable-webgl2` the svg ground draws, one line says "this browser has no
  WebGL2", and neither library is fetched.
- [ ] **The three things the grid forces the page to say.** These are notes and are not changed. The map does not
  yet carry the svg ground's `<title>` per object: hover shows the station name, the cell id or the claim and cell
  id, but that is a pointer tooltip with no keyboard or screen-reader path. **Owed.**
- [x] **Fixtures.** Both fixtures draw in both registers at all four widths (above).
- [x] **POLL behaviour.** `redraw({ keepGround })` swaps the living figure back in, and `mount()` skips while
  `KEEP_GROUND` is up. Measured on `sat`: `PAI_REFRESH.now()` kept the same map element and sent **0** tile requests.
- [x] **Reduced motion.** MapLibre's tile fade is 0 under `prefers-reduced-motion`, and nothing animates the view.
- [x] **Simple mode and the wall.** Simple mode keeps the svg ground and its one-line key (`mapOn()` is false
  there). The wall does not draw the ground and loads nothing new.
- [ ] **Hatch and dot for state and zones.** The svg ground under the lead draws no cell state today, so there was
  nothing to match. `FillStyleExtension` is not used yet.
- [ ] **The kilometre circle is solid, not dashed.** deck.gl's `ScatterplotLayer` cannot dash. A dashed ring needs
  `PathStyleExtension` over a ring the page would have to compute, or a ring sent by the node. **Owed:** add the
  ring to `/issues` geometry, or keep it solid.
- [ ] **Claims are new on the ground.** The svg ground never drew `geometry.claims`, and the prompt asks for them.
  At 40/255 ink they read as faint extra hexagons beyond the plate. Tomas should look at them before this ships.
- [x] **`make lint && make test`** pass on this branch (64 suites), and so does `tests/visual/gate.sh`, run locally
  (no horizontal overflow in 198 combinations). The gate draws the default `svg` ground only. **Owed:** a gate
  pass with `UI_GROUND=map`.

## Routes added, 7 October

The redesign's Place door (planetai-design R36) first drew its grid with h3-js and measured in the page. Tomas asked
for that compute on the node, so four routes now answer it, from `app/issues/geometry.py`:

- `GET /geo/grid?bbox=&res=`: the cells covering a box, one ring wider, plus the node's own cell, as `cells_ll`
  rows. A box past 2,500 cells is refused with 422, not cut short.
- `GET /geo/cell?id=` (or `lat`, `lon`, `res`): area, own edge, parent, `may_leave`, and grid steps from the node.
- `GET /geo/measure?path=&from_node=`: great-circle metres, leg by leg.
- `GET /geo/rings?km=`: circles round the node.

All four are on no allowlist, like `/place/geojson`, because each locates the node more finely than `/health`
does. `tests/test_share.py` holds the gate, the shapes and the refusals. The prototype asks them through
`prototypes/instrument/serve.py`, and with them it makes no h3 call on Place, measured by wrapping `window.h3`.

## Not done

- **Phase 1b, the offline vector base** (`planetai ground fetch`, a Protomaps extract in `data/`, a `vector` tab
  with its cost said before it is pressed). The pmtiles reader is 7,956 bytes gzipped (4.5.0), so it does not
  move the Phase 0 verdict.
- **Phase 2.** Wind is possible: `packs/forecast` carries `fc_wind_speed` and `fc_wind_direction`. Its rows are
  timestamped up to 48 h ahead, so a wind layer must read `ts <= now()`. The earth raster and peers at scale are
  not started.
- `docs/site/dashboard.md` "The ground" is not rewritten and its checked stamp has not moved. No CHANGELOG entry
  yet. Not landed.

## Where the prompt and AGENTS.md meet

Nothing in AGENTS.md overrules the prompt. It names one more constraint on top of it: "The node computes; the page
draws. A number the page works out for itself is a bug." The map's view is the plate's bounding box, the same as
`frame()` and kit-map's `frameOf()`, so that is a viewport and not a figure. Its only distance is kit-map's
1,000 m circle, which is drawn as a radius in metres, the same primitive as the svg's `r="1000"`.
