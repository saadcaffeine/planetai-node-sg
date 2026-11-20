'use strict';
/* PLACE · the map workbench (R36, 7 Oct 2026). MapLibre draws the base, deck.gl draws the node's data over it.

   REFERENCE LOCK (Refero, docs in the R36 note):
   - Mapbox's cartographic rule: the map is neutral and the data is the only colour. One signal hue, the node's
     --cells blue, for the cell and focus; orange stays the satellite's alone. No second accent.
   - mono's 1 px rules and tracked mono labels.
   - The v2 drawing (SPEC_place_microgis §4, 4 Nov 2026), after Option A (15 Oct): the cake on the left as plain rows with
     switches (OneSoil's layer list; a dot until 17 Nov 2026), the screen black in both registers with its tools, scales and hour on it as
     chips, the tools in a menu on the top line (5 Nov 2026; the right column before), the inspector a status line under the screen and the marks around the house a list.

   SCALE. The H3 resolution drawn follows the zoom: the finest rung whose cell is at least 56 px to an edge on
   screen. The presets fly to the node's own cell at that rung, so a press and a scroll agree. Rungs 6 and coarser
   (cells that may leave the machine) are dotted, as on the node's ladder.

   THE NODE COMPUTES, THE PAGE DRAWS (R36.1, and R40 for every door). No h3-js and no distance here. The grid, the node's cell at each rung,
   the radio cell, the rings, every measured metre and every cell fact are answers from the node's GET /geo/*
   routes, asked with this screen's token (token-only at every SHARE_LEVEL); the plan is the node's own
   GET /place/geojson. Without the token the map says what it is not drawing, and why. */

(function () {
const PM = { map: null, overlay: null, res: 8, tool: 'select', measure: [], hover: null, pick: null,
  on: {}, alpha: {}, plan: null, land: null };

/* ---------------------------------------------------------------- the palette, by register */
const PAL = {
  light: { sea: '#DCE2E6', land: '#F1EFEB', green: '#E1E6DB', road: '#FFFFFF', casing: '#D5D1CA', bldg: '#CFCBC4',
    coast: '#B9B4AC', built: '#E9E6E1', sand: '#EEE9DE', farm: '#ECEDE5', label: '#5F5A54', lhalo: '#F1EFEB', major: '#FFFFFF', path: '#B9B4AC', ink: [23, 23, 23], mute: [95, 90, 84], cells: [32, 56, 141], sat: [219, 114, 0], halo: [241, 239, 235] },
  dark: { sea: '#0E1012', land: '#17191D', green: '#1A201C', road: '#30353D', casing: '#17191D', bldg: '#2B2E34',
    coast: '#3A3F47', built: '#1C1F23', sand: '#1E1F1C', farm: '#191C19', label: '#A3A19F', lhalo: '#17191D', major: '#3C424B', path: '#3A3F47', ink: [249, 245, 242], mute: [163, 161, 159], cells: [127, 165, 232], sat: [255, 147, 30], halo: [23, 25, 29] },
};
/* the screen is black in both registers (SPEC_place_microgis §4, Tomas 4 Nov 2026); Now's map keeps the page's (groundBase),
   and the sheet's picture on Paper takes the light one while it is taken (placeSheet) */
const P = () => (PM.sheet && PM.sheet.paper ? PAL.light : PAL.dark);

/* ---------------------------------------------------------------- scales: named rungs of the ladder */
/* the five rungs on the screen (SPEC_place_microgis §4); a scroll still reaches the island and the radio cell */
const SCALES = [[10, 'Street'], [9, 'Block'], [8, 'Cell'], [7, 'Village'], [6, 'District']];
const EDGE = r => (D.geometry.ladder.find(l => l.res === r) || {}).edge_m || 1;
const mPerPx = z => 40075016.686 * Math.cos(D.point[1] * Math.PI / 180) / (512 * 2 ** z);
const resFor = z => { for (let r = 12; r >= 2; r--) if (EDGE(r) / mPerPx(z) >= 56) return r; return 2; };
const mayLeave = r => r <= 6;

/* ---------------------------------------------------------------- the layer registry: one row per layer, by pack.
   A pack that grows a layer adds one entry here, in its section of the cake (doors-cake.js CAKE, SPEC_place_microgis §5).
   `empty` is a layer the pack would draw and cannot yet: the row stays, says so in the node's words, and cannot be
   switched on. `soon` is a row the node cannot fill at all yet: it stays, dotted, naming the source it would draw from.
   FIVE ON (Tomas, 15 Oct): the street, the node's cell, the outdoor kit, the public stations and the images. */
const LAYERS = [
  { id: 'own', cake: 'microclimate', pack: 'core', src: 'this house', name: 'Outdoor kit', sub: 'this house’s stations outside · filled', on: true },
  { id: 'public', cake: 'microclimate', pack: 'nearby', src: 'nearby', name: 'Stations', sub: 'hollow · display only, never alert', on: true },
  { id: 'wind', cake: 'microclimate', pack: 'forecast', src: 'Open-Meteo', name: 'Wind', sub: 'moving, Open-Meteo field round the node', on: false, need: 'wind', still: true },
  { id: 'models', cake: 'microclimate', pack: 'core', src: 'models', name: 'Models', sub: 'model points: sea, air, land, weather', on: false },
  { id: 'flowlog', cake: 'flows', pack: 'flows', src: 'flows', name: 'Flows', sub: 'the flows log: made, used, fixed and taken in, by class and ring', soon: true, empty: true },
  { id: 'labs', cake: 'flows', pack: 'make', src: 'fablabs.io', name: 'Labs', sub: 'places to make, from fablabs.io', on: false },
  { id: 'satonly', cake: 'built', pack: 'place', src: 'satellite', name: 'Satellite only', sub: 'buildings missing from OSM', on: false, minz: 12.5 },
  { id: 'radio', cake: 'built', pack: 'reticulum', src: 'res 3', name: 'Radio cell', sub: 'what leaves by radio: the res-3 cell it announces', on: false, maxz: 10 },
  /* the grid's plants (sized by MW), substations and cable heads the energy pack read from OSM (GET /energy), and the MW
     made inside each of the node's seven cells: stock, so built (energy-pack design §5.6). Points and cells are token-only. */
  { id: 'energy', cake: 'built', pack: 'energy', src: 'OSM', name: 'Power grid', sub: 'plants, substations and cable heads, OpenStreetMap', on: false, empty: true },
  /* the species somebody here confirmed in the household's images (SPEC_species §4), token-only: GET /species. GBIF's
     open records are a count per species (the list under this row), never points, so nothing hollow is drawn for them. */
  { id: 'species', cake: 'animals', pack: 'core', src: 'confirmed', name: 'Species', sub: 'confirmed here, at the image’s point', on: true },
  /* no shape on this map, whatever the node holds: the change is a picture in UTM metres with its own words burned in.
     packRows() says where it is instead. */
  { id: 'earth', cake: 'plants', pack: 'earth', src: 'AlphaEarth', name: 'Land change', sub: 'AlphaEarth, year on year', empty: true },
  { id: 'canopy', cake: 'plants', pack: 'place', src: 'Meta/WRI', name: 'Canopy', sub: 'Meta/WRI, 1 m', soon: true, empty: true },
  { id: 'soilgrids', cake: 'soil', pack: 'place', src: 'SoilGrids', name: 'Soil', sub: 'SoilGrids 2.0, 250 m', soon: true, empty: true },
  { id: 'soilsamples', cake: 'soil', pack: 'core', src: 'samples', name: 'Soil samples', sub: 'taken here', soon: true, empty: true },
  /* the rivers and basins the hydro pack kept (GET /hydro), token-only like the plan: about 500 m, a river you know by name */
  { id: 'rivers', cake: 'water', pack: 'hydro', src: 'HydroRIVERS', name: 'Rivers', sub: 'HydroSHEDS, traced at about 500 m', on: false, empty: true },
  { id: 'basin', cake: 'water', pack: 'hydro', src: 'HydroBASINS', name: 'Basins', sub: 'level 12, the one the node drains through drawn brighter', on: false, empty: true },
  { id: 'rain', cake: 'water', pack: 'terrain', src: 'terrain', name: 'Rain', sub: 'where the rain goes, the terrain pack', soon: true, empty: true },
  { id: 'watersamples', cake: 'water', pack: 'core', src: 'samples', name: 'Water samples', sub: 'taken here', soon: true, empty: true },
  { id: 'terrain', cake: 'ground', pack: 'terrain', src: 'GLO-30', name: 'Terrain', sub: 'GLO-30', soon: true, empty: true },
  { id: 'geology', cake: 'ground', pack: 'place', src: 'no source', name: 'Geology', sub: 'no open source chosen yet', soon: true, empty: true },
  /* the frame: the cell, the grid, the base maps, the household's own images (SPEC_eyes step 1). The street map carries
     its names: one row, not two. */
  { id: 'mine', cake: 'frame', pack: 'core', src: 'H3', name: 'Node cell', sub: 'the cell it stands in, at the resolution in view; at Cell scale the seven, held, claimed or open', on: true },
  { id: 'grid', cake: 'frame', pack: 'core', src: 'H3', name: 'H3 grid', sub: 'cells at this scale, dotted where a cell may leave', on: false },
  { id: 'street', cake: 'frame', pack: 'place', src: 'OSM', name: 'Street map', sub: 'OpenStreetMap, with its names, kept on this node', on: true, still: true },
  { id: 'imagery', cake: 'frame', pack: 'earth-engine', src: 'Sentinel-2', name: 'Satellite', sub: '10 m, Sentinel-2, composited by this node; from Block scale in, the street map and any drone flight', on: false, need: 'imagery' },
  { id: 'drone', cake: 'frame', pack: 'place', src: 'OAM', name: 'Drone', sub: 'drone imagery, OpenAerialMap, where somebody flew', on: false, need: 'drone', minz: 13 },
  { id: 'rings', cake: 'frame', pack: 'nearby', src: '2 · 5 · 15 km', name: 'Rings', sub: '2, 5 and 15 km', on: false },
  { id: 'images', cake: 'frame', pack: 'core', src: 'this house', name: 'Images', sub: 'what the household added', on: true },
  { id: 'peers', cake: 'frame', pack: 'reticulum', src: 'radio', name: 'Nodes nearby', sub: 'nodes heard by radio, their announced cells', empty: true },
];
LAYERS.forEach(l => { PM.on[l.id] = !!l.on && !l.empty; PM.alpha[l.id] = 1; });
const ON = () => LAYERS.filter(l => PM.on[l.id]).length;   // the status line's count
const OF = () => LAYERS.filter(l => !l.empty).length;
/* a species as a row says it: genus and epithet, without the author GBIF appends */
const short = t => String(t.name || '').split(' ').slice(0, t.rank === 'GENUS' ? 1 : 2).join(' ');
/* every confirmed living finding, at its image's point (the node's `at`); a model's guess is not one */
const speciesMarks = () => (PM.caps || []).filter(c => c.analysis && c.analysis.confirmed_by)
  .flatMap(c => (c.analysis.findings || []).filter(f => f.taxon || f.scientific).map(f => ({ c, t: f.taxon ? short(f.taxon) : f.scientific })));
/* after GET /captures and /species: none is a row that says so; a screen without the token is told why */
function imageRows() {
  const im = LAYERS.find(l => l.id === 'images'), sp = LAYERS.find(l => l.id === 'species'), C = PM.caps || [], S = (PM.species || {}).species || [];
  const kinds = d3.rollups(C, v => v.length, c => c.kind).map(([k, v]) => `${v} ${(KIND[k] || k).toLowerCase()}`).join(', ');
  im.locked = sp.locked = !PM.caps; im.empty = !C.length; sp.empty = !S.length;
  im.none = 'none yet · the Image key on the screen'; sp.none = 'none confirmed yet · confirm what an image shows in Data › Images';
  im.sub = `${C.length} · ${kinds}`; im.src = `${C.length} here`; sp.src = `${S.length} here`;
  sp.sub = `${S.length} confirmed · ${S.slice(0, 2).map(short).join(', ')}${S.length > 2 ? ', …' : ''}`;
  PM.on.images = !im.empty; PM.on.species = !sp.empty;
}

/* ---------------------------------------------------------------- asking the node */
const API = '/';
const ask = p => doorsFetch(API + p).then(async r => {
  if (r.ok) return r.json();
  const b = await r.json().catch(() => ({}));
  throw new Error(typeof b.detail === 'string' ? b.detail : `GET /${p.split('?')[0]} answered ${r.status}`);
});
const lngLat = s => [s.lon, s.lat];
/* a cells_ll row, [id, lat, lng, lat, lng, …], as the closed [lng, lat] ring deck.gl draws: a reorder, not a computation */
const loop = row => { const r = []; for (let i = 1; i < row.length; i += 2) r.push([row[i + 1], row[i]]); r.push(r[0]); return r; };
const fmtM = m => m >= 1000 ? `${(m / 1000).toFixed(m >= 10000 ? 1 : 2)} km` : `${Math.round(m)} m`;
const CELLS = new Map();
const cellFacts = id => { if (!CELLS.has(id)) CELLS.set(id, ask(`geo/cell?id=${id}`)); return CELLS.get(id); };
const cellAt = (lon, lat, r) => ask(`geo/cell?lat=${lat.toFixed(6)}&lon=${lon.toFixed(6)}&res=${r}`);
const fromNode = (lon, lat) => ask(`geo/measure?from_node=true&path=${lon},${lat}`).then(m => m.total_m);
/* one fact, one figure, one unit (Tomas, 15 Oct: "0.64 km²" beside "64.0 ha"): an area is always km², as the lede says it */
const area = m2 => `${(m2 / 1e6).toFixed(m2 >= 1e8 ? 0 : m2 >= 1e5 ? 2 : 3)} km²`;

/* The grid in view, asked again whenever the view settles. A slow answer for an old view is dropped. */
let GRID = null, GSEQ = 0, RINGS = null, RADIO = null;
async function loadGrid() {
  const b = PM.map.getBounds(), seq = ++GSEQ;
  const box = [b.getWest(), b.getSouth(), b.getEast(), b.getNorth()].map(v => v.toFixed(5)).join(',');
  try {
    const g = await ask(`geo/grid?res=${PM.res}&bbox=${box}`);
    if (seq !== GSEQ) return;
    GRID = { res: g.res, edge_m: g.edge_m, node: g.node[0], nodeRing: loop(g.node), cells: g.cells_ll.map(r => ({ id: r[0], path: loop(r) })) };
    offline(null);
  } catch (e) { if (seq === GSEQ) { GRID = null; offline(e.message); } }
  redraw(); if (!PM.pick && !MEASURING()) facts();
}
/* Said once, on the map, when the node does not answer: what is missing and why, never a blank grid. */
function offline(why) {
  PM.offline = why;
  let n = document.querySelector('.nonode');
  if (!why) { if (n) n.remove(); return; }
  /* locked, not broken: the margin and the inspector line already say so, and an overlay hid the scale rail (15 Oct) */
  if (!DOORS_TOKEN()) { if (n) n.remove(); return; }
  if (!n) { n = document.createElement('p'); n.className = 'nonode'; (PM.map ? PM.map.getContainer() : $('#map')).appendChild(n); }
  n.textContent = 'The node did not give this screen its map just now. Try again in a minute.';
  n.title = why;
}

/* ---------------------------------------------------------------- the base style: everything from the node's disk */
/* GET /ground/* (planetai-node): OpenStreetMap vector tiles cut from Protomaps' build, the label fonts, this node's
   own Sentinel-2 composite and any OpenAerialMap drone mosaic, fetched once by `planetai run place basemap` and
   `planetai run earth-engine basemap`. Nothing here asks a tile server. Without the vector tiles the plan from
   /place/geojson draws instead, as before. Rasters sit over the street map and under the names: a hybrid. */
const GREEN = ['park', 'wood', 'forest', 'garden', 'grass', 'grassland', 'scrub', 'nature_reserve', 'golf_course', 'cemetery', 'meadow', 'national_park', 'protected_area', 'recreation_ground', 'village_green', 'pitch', 'playground'];
const BUILT = ['industrial', 'commercial', 'retail', 'university', 'school', 'college', 'hospital', 'military', 'railway', 'airfield', 'aerodrome', 'runway', 'pedestrian', 'parking', 'platform'];
const SAND = ['beach', 'sand', 'bare_rock', 'scree'];
function style(p = P()) {
  const k = v => ['==', ['get', 'kind'], v], any = l => ['in', ['get', 'kind'], ['literal', l]], G = PM.ground || {}, V = !!G.vector;
  const W = (lo, hi) => ['interpolate', ['exponential', 1.6], ['zoom'], 12, lo, 18, hi];
  /* one zoom curve per kind: MapLibre wants the zoom outermost and the kind inside each stop */
  const WK = (h, m, n) => ['interpolate', ['exponential', 1.6], ['zoom'], 12, ['match', ['get', 'kind'], 'highway', h[0], 'major_road', m[0], n[0]],
    18, ['match', ['get', 'kind'], 'highway', h[1], 'major_road', m[1], n[1]]];
  const sources = { land: { type: 'geojson', data: PM.land },
    plan: { type: 'geojson', data: PM.plan || { type: 'FeatureCollection', features: [] } } };
  if (V) sources.v = { type: 'vector', tiles: [location.origin + API + 'ground/vector/{z}/{x}/{y}.pbf'], minzoom: 0, maxzoom: 15 };
  if (G.imagery) sources.imagery = { type: 'raster', tiles: [location.origin + API + 'ground/imagery/{z}/{x}/{y}.png'], tileSize: 256, minzoom: 8, maxzoom: 15 };
  if (G.drone) sources.drone = { type: 'raster', tiles: [location.origin + API + 'ground/drone/{z}/{x}/{y}.png'], tileSize: 256, minzoom: 14, maxzoom: 18 };
  const L = [
    { id: 'sea', type: 'background', paint: { 'background-color': p.sea } },
    { id: 'land-fill', type: 'fill', source: 'land', paint: { 'fill-color': p.land } },
    { id: 'land-edge', type: 'line', source: 'land', maxzoom: V ? 9 : 24, paint: { 'line-color': p.coast, 'line-width': 0.8 } },
  ];
  if (V) L.push(
    { id: 'v-earth', type: 'fill', source: 'v', 'source-layer': 'earth', filter: k('earth'), paint: { 'fill-color': p.land } },
    { id: 'v-farm', type: 'fill', source: 'v', 'source-layer': 'landuse', filter: any(['farmland', 'farm', 'orchard', 'vineyard', 'allotments']), paint: { 'fill-color': p.farm } },
    { id: 'v-green', type: 'fill', source: 'v', 'source-layer': 'landuse', filter: any(GREEN), paint: { 'fill-color': p.green } },
    { id: 'v-built', type: 'fill', source: 'v', 'source-layer': 'landuse', filter: any(BUILT), paint: { 'fill-color': p.built } },
    { id: 'v-sand', type: 'fill', source: 'v', 'source-layer': 'landuse', filter: any(SAND), paint: { 'fill-color': p.sand } },
    { id: 'v-water', type: 'fill', source: 'v', 'source-layer': 'water', filter: ['==', ['geometry-type'], 'Polygon'], paint: { 'fill-color': p.sea } },
    { id: 'v-stream', type: 'line', source: 'v', 'source-layer': 'water', filter: ['==', ['geometry-type'], 'LineString'], minzoom: 12, paint: { 'line-color': p.sea, 'line-width': W(0.6, 3) } },
    { id: 'v-coast', type: 'line', source: 'v', 'source-layer': 'water', filter: ['==', ['geometry-type'], 'Polygon'], minzoom: 9, paint: { 'line-color': p.coast, 'line-width': 0.6 } },
    { id: 'v-path', type: 'line', source: 'v', 'source-layer': 'roads', filter: any(['path', 'other']), minzoom: 14, paint: { 'line-color': p.path, 'line-width': 0.8, 'line-dasharray': [2, 1.5] } },
    { id: 'v-casing', type: 'line', source: 'v', 'source-layer': 'roads', filter: any(['minor_road', 'major_road', 'highway']), minzoom: 12, layout: { 'line-cap': 'round', 'line-join': 'round' },
      paint: { 'line-color': p.casing, 'line-width': WK([2.4, 22], [1.8, 18], [0.9, 13]) } },
    { id: 'v-road', type: 'line', source: 'v', 'source-layer': 'roads', filter: any(['minor_road', 'major_road', 'highway']), layout: { 'line-cap': 'round', 'line-join': 'round' },
      paint: { 'line-color': ['match', ['get', 'kind'], 'minor_road', p.road, p.major], 'line-width': WK([1.6, 19], [1.1, 15], [0.5, 10.5]) } },
    { id: 'v-bldg', type: 'fill', source: 'v', 'source-layer': 'buildings', minzoom: 13, paint: { 'fill-color': p.bldg, 'fill-opacity': ['interpolate', ['linear'], ['zoom'], 13, 0, 14, 1] } });
  else L.push(
    { id: 'plan-green', type: 'fill', source: 'plan', filter: k('green'), minzoom: 12, paint: { 'fill-color': p.green } },
    { id: 'plan-casing', type: 'line', source: 'plan', filter: k('road'), minzoom: 12, layout: { 'line-cap': 'round', 'line-join': 'round' }, paint: { 'line-color': p.casing, 'line-width': W(1.2, 14) } },
    { id: 'plan-road', type: 'line', source: 'plan', filter: k('road'), minzoom: 12, layout: { 'line-cap': 'round', 'line-join': 'round' }, paint: { 'line-color': p.road, 'line-width': W(0.6, 11) } },
    { id: 'plan-bldg', type: 'fill', source: 'plan', filter: k('building'), minzoom: 12.5, paint: { 'fill-color': p.bldg, 'fill-opacity': ['interpolate', ['linear'], ['zoom'], 12.5, 0, 13.5, 1] } });
  /* Sentinel-2's grain is 10 m and its tiles stop at zoom 15: past it a map would only enlarge them (Tomas, 6 Nov:
     "switch past Block"). So the satellite ends at SAT_MAX, the street map under it shows, and where somebody flew a
     drone its picture comes on above the streets (drone-close, the satellite's own row). */
  if (G.imagery) L.push({ id: 'imagery', type: 'raster', source: 'imagery', maxzoom: SAT_MAX, layout: { visibility: 'none' }, paint: { 'raster-fade-duration': 0 } });
  if (G.drone) L.push({ id: 'drone', type: 'raster', source: 'drone', minzoom: 13, layout: { visibility: 'none' }, paint: { 'raster-fade-duration': 0 } });
  if (G.imagery && G.drone) L.push({ id: 'drone-close', type: 'raster', source: 'drone', minzoom: SAT_MAX, layout: { visibility: 'none' }, paint: { 'raster-fade-duration': 0 } });
  L.push({ id: 'plan-sat', type: 'fill', source: 'plan', filter: k('sat'), minzoom: 12.5,
    paint: { 'fill-color': `rgb(${p.sat})`, 'fill-opacity': ['interpolate', ['linear'], ['zoom'], 12.5, 0, 13.5, 0.75] } });
  if (V && G.glyphs) {
    const txt = (size, color = p.label) => ({ 'text-color': color, 'text-halo-color': p.lhalo, 'text-halo-width': 1.4 });
    L.push(
      { id: 'v-road-label', type: 'symbol', source: 'v', 'source-layer': 'roads', minzoom: 14.5, filter: ['has', 'name'],
        layout: { 'symbol-placement': 'line', 'text-field': ['get', 'name'], 'text-font': ['Noto Sans Regular'], 'text-size': 10.5, 'text-letter-spacing': 0.02 }, paint: txt() },
      { id: 'v-poi-label', type: 'symbol', source: 'v', 'source-layer': 'pois', minzoom: 16, filter: ['has', 'name'],
        layout: { 'text-field': ['get', 'name'], 'text-font': ['Noto Sans Italic'], 'text-size': 10, 'text-max-width': 8 }, paint: txt() },
      { id: 'v-place-label', type: 'symbol', source: 'v', 'source-layer': 'places', filter: ['has', 'name'],
        layout: { 'text-field': ['get', 'name'], 'text-font': ['Noto Sans Medium'], 'text-max-width': 7, 'text-letter-spacing': 0.04,
          'text-transform': ['match', ['get', 'kind'], ['region', 'country'], 'uppercase', 'none'],
          'text-size': ['match', ['get', 'kind'], 'country', 13, 'region', 12, 'locality', 12.5, 11] }, paint: txt(12, p.ink ? `rgb(${p.ink})` : p.label) });
  }
  return { version: 8, glyphs: location.origin + API + 'ground/glyphs/{fontstack}/{range}.pbf', sources, layers: L };
}
/* which base style layers each registry row owns */
const OWNS = { street: ['land-fill', 'land-edge', 'v-earth', 'v-farm', 'v-green', 'v-built', 'v-sand', 'v-water', 'v-stream', 'v-coast', 'v-path', 'v-casing', 'v-road', 'v-bldg', 'plan-green', 'plan-casing', 'plan-road', 'plan-bldg',
    'v-road-label', 'v-poi-label', 'v-place-label'],
  imagery: ['imagery', 'drone-close'], drone: ['drone'], satonly: ['plan-sat'] };
const SAT_MAX = 15;   // the satellite's last zoom; Block (15.1) and Street draw the street map
function applyBase() {
  if (!PM.map) return;
  for (const [id, ls] of Object.entries(OWNS)) for (const l of ls) {
    if (!PM.map.getLayer(l)) continue;
    PM.map.setLayoutProperty(l, 'visibility', PM.on[id] || (id === 'street' && PM.on.imagery) ? 'visible' : 'none');
    const t = PM.map.getLayer(l).type;
    if (t === 'raster') PM.map.setPaintProperty(l, 'raster-opacity', PM.alpha[id]);
    if (l === 'plan-sat') PM.map.setPaintProperty(l, 'fill-opacity', ['interpolate', ['linear'], ['zoom'], 12.5, 0, 13.5, 0.75 * PM.alpha[id]]);
  }
}
/* What the node holds of its own map, and the credit each layer owes (ODbL, CC BY, Copernicus). */
function groundRows() {
  const m = (PM.meta && PM.meta.layers) || {}, mb = b => b ? `${(b / 1e6).toFixed(1)} MB` : '', G = PM.ground || {};
  /* no /ground/meta at all is this screen being refused it, not a node without a map: say which */
  const locked = !PM.meta;
  /* `part`: the node holds the layer in part, as the report's page 2 says it (SPEC_place_report §5) */
  const set = (id, sub, empty, why, part) => { const l = LAYERS.find(x => x.id === id); if (sub) l.sub = sub; l.empty = !!empty; l.why = why; l.part = !!part && !empty; l.locked = locked && !!empty; if (empty) PM.on[id] = false; };
  set('street', G.vector ? `OpenStreetMap ${(m.vector || {}).build ? `build ${m.vector.build.slice(0, 8)}` : ''} · ${mb((m.vector || {}).bytes)} on this node` : locked ? 'token-only · unlock this screen in Set up › This screen' : 'the plan from /place/geojson; no street map on this node yet: planetai run place basemap',
    false, 'planetai run place basemap', !G.vector && !locked);
  const im = m.imagery || {};
  /* the node's Sentinel-2 years (GET /earth) are the satellite's then and now on the screen, with or without the map layer */
  const yrs = ((D.earth || {}).sentinel || []).length;
  set('imagery', G.imagery ? `Sentinel-2, ${im.passes} passes, ${(im.from || '').slice(0, 7)} to ${(im.to || '').slice(0, 7)} · ${mb(im.bytes)}`
    : yrs ? `${yrs} Sentinel-2 years, then and now · no map layer yet: planetai run earth-engine basemap` : null, !G.imagery && !yrs, 'planetai run earth-engine basemap', !G.imagery);
  /* the satellite is the base wherever the node holds it (SPEC_place_microgis §4, Defaults); elsewhere the streets */
  if (G.imagery) PM.on.imagery = true;
  const dr = m.drone || {}, ms = dr.mosaics || [];
  const W = PM.wind;
  set('wind', W ? `Open-Meteo, ${W.n * W.n} points over ${W.km * 2} km, hourly · read ${hhmm(W.fetched)}` : null, !W,
    'FORECAST_OPENMETEO=1, then planetai run forecast windfield');
  set('drone', G.drone && ms.length ? `${ms.map(x => `${x.provider}, ${Math.round(x.gsd_m * 100)} cm, ${x.date}`).join(' · ')} · ${mb(dr.bytes)}` : null, !G.drone, 'planetai run place basemap --only drone');
}
/* The land change cannot draw: from what the page already holds, where the node's answer is instead of "the pack
   has nothing here yet", which said so beside a working What changed (14 Oct). */
function packRows() {
  const ea = LAYERS.find(l => l.id === 'earth'), nE = ((D.earth || {}).changes || []).length;
  ea.none = nE ? `${nE} comparison${nE === 1 ? '' : 's'} · a count, not a shape: Land, in the figures below` : null; ea.part = !!nE;
}
/* after GET /hydro: a node without the pack, or before its fetch, keeps both rows and says which */
function hydroRows() {
  const H = PM.hydro, rv = LAYERS.find(l => l.id === 'rivers'), bs = LAYERS.find(l => l.id === 'basin');
  const nR = ((H && H.rivers) || {}).features?.length || 0, nB = ((H && H.basins) || {}).features?.length || 0;
  rv.empty = !nR; bs.empty = !nB; rv.why = bs.why = 'planetai run hydro fetch';
  if (nR) { rv.src = `${nR} reaches`; rv.sub = H.sentence ? `nearest: ${H.sentence}` : rv.sub; }   // off at first: five on (Tomas, 15 Oct)
  if (nB) bs.src = `${nB} basins`;
  if (H && H.basin && H.basin.level4) bs.sub = `level 12 here; the node’s bioregion is level-4 basin ${H.basin.level4.pfaf_id}`;
}
/* after GET /energy: the built row's line, or why it draws nothing (pack off or unfetched, no grid, no token) */
function energyRows() {
  const E = PM.energy, l = LAYERS.find(x => x.id === 'energy'), S = (E && E.sources) || [], n = E && E.counts;
  l.empty = !S.some(s => s.lat != null); l.locked = !!S.length && l.empty; l.why = 'planetai run energy fetch';
  l.none = E && !E.grid ? 'on no grid the energy pack knows yet · add it to packs/energy/grids.yml' : null;
  if (!n) return;
  const km = S.filter(s => s.km != null).map(s => s.km), pl = (k, w) => `${k} ${w}${k === 1 ? '' : 's'}`;
  l.src = pl(n.plants, 'plant');
  l.sub = `${pl(n.plants, 'plant')}, ${pl(n.substations, 'substation')} on this grid${km.length ? ` · nearest ${Math.min(...km).toFixed(1)} km` : ''}`;
}
/* a cell's label: the MW of the plants in it, and the house's roof on its own cell when the admin token shows it */
const cellMW = (c, h) => (c.mw == null ? 'MW not tagged' : `${+c.mw.toFixed(1)} MW`) + (c.home && h && h.roof_w != null ? ` · roof ${(h.roof_w / 1000).toFixed(1)} kW` : '');
/* the credits each layer on the screen owes, the same words on the screen and burned into the PNG */
function creditList() {
  const m = (PM.meta && PM.meta.layers) || {}, c = [];
  const close = PM.map && PM.map.getZoom() >= SAT_MAX, sat = PM.on.imagery && !close;
  if ((PM.on.street || (PM.on.imagery && close)) && PM.ground && PM.ground.vector) c.push('© OpenStreetMap contributors · Protomaps');
  if (sat && m.imagery) c.push(m.imagery.attribution);
  if (PM.on.imagery && close && !PM.on.drone && m.drone) c.push((m.drone.mosaics || []).map(x => `${x.provider} via OpenAerialMap, CC BY 4.0`).join(' · '));
  if (PM.on.drone && m.drone) c.push((m.drone.mosaics || []).map(x => `${x.provider} via OpenAerialMap, CC BY 4.0`).join(' · '));
  if (PM.on.wind && PM.wind) c.push('wind: Open-Meteo, CC BY 4.0');
  if ((PM.on.rivers || PM.on.basin) && PM.hydro) c.push('rivers and basins: HydroSHEDS via HydroATLAS, CC BY 4.0');
  if (PM.on.energy && PM.energy) c.push('power grid: © OpenStreetMap contributors, ODbL, via Overpass');
  c.push('Natural Earth');
  return c.filter(Boolean);
}
function credits() { const el = $('#mapcredit'); if (el) el.textContent = creditList().join(' · '); }

/* ---------------------------------------------------------------- the data, drawn by deck.gl */
function layers() {
  const p = P(), Dk = deck, a = id => PM.alpha[id], z = PM.map.getZoom(), r = PM.res, A = (c, o) => [...c, Math.round(o * 255)];
  const vis = l => PM.on[l.id] && (l.minz == null || z >= l.minz) && (l.maxz == null || z <= l.maxz);
  const L = Object.fromEntries(LAYERS.map(l => [l.id, vis(l)]));
  const px = { lineWidthUnits: 'pixels', radiusUnits: 'pixels', widthUnits: 'pixels' }, out = [];   // PathLayer reads widthUnits
  const dashed = new Dk.PathStyleExtension({ dash: true });
  /* on a sheet (placeSheet) the house's own points and the images stand only outside its res-10 cell, as the node placed
     them; a point the node did not place is left off */
  const SH = PM.sheet, away = id => !!SH.home && !!id && id !== SH.home;
  const S = outside(D.sensors).filter(s => s.lat != null && (!SH || s.kind === 'facility' || (s.kind === 'sensor' && !s.local) || away(SH.cells.get(s.sensor_id))));
  const caps = PM.caps && PM.caps.filter(c => !SH || away(c.cell));
  const G = GRID, gr = G ? G.res : r, fine = SH && gr > 10;   // a cell of the node's finer than the house's is not drawn on a sheet

  /* the basins under the rivers: outlines, the one the node drains through drawn brighter */
  if (L.basin && PM.hydro && PM.hydro.basins) {
    out.push(new Dk.PathLayer({ id: 'basin', data: PM.hydro.basins.features.flatMap(f => f.geometry.coordinates.map(path => ({ path, f }))),
      getPath: d => d.path, ...px, pickable: true, getColor: d => A([110, 190, 255], (d.f.properties.here ? 0.9 : 0.35) * a('basin')),
      getWidth: d => (d.f.properties.here ? 2 : 1) }));
  }
  /* the rivers: wider with each Strahler order, so the river you know by name reads before its tributaries */
  if (L.rivers && PM.hydro && PM.hydro.rivers) {
    out.push(new Dk.PathLayer({ id: 'rivers', data: PM.hydro.rivers.features, getPath: f => f.geometry.coordinates, ...px, pickable: true,
      autoHighlight: true, highlightColor: [255, 255, 255, 120], getColor: A([110, 190, 255], 0.9 * a('rivers')),
      getWidth: f => Math.min(1 + f.properties.ord_stra * 0.8, 6), capRounded: true, jointRounded: true }));
  }
  /* the grid: the seven cells' outlines and MW, then the substations and cable heads hollow, the plants filled when
     fossil, each sized by its MW (--d-energy on the dark screen) */
  if (L.energy && PM.energy) {
    const E = PM.energy, EN = [242, 140, 40], P0 = (E.sources || []).filter(s => s.lat != null), C = E.cells || [];
    out.push(new Dk.PathLayer({ id: 'energy-cells', data: C, getPath: c => c.ring, ...px, getColor: A(EN, .5 * a('energy')), getWidth: 1 }));
    if (z >= 12) out.push(new Dk.TextLayer({ characterSet: 'auto', id: 'energy-mw', data: C, getPosition: lngLat, getText: c => cellMW(c, SH ? null : E.household),   // the house's roof is the household's: never on a sheet
      getSize: 11, fontFamily: 'JetBrains Mono, monospace', getColor: A(EN, a('energy')), background: true, getBackgroundColor: A(p.halo, .85), backgroundPadding: [3, 1] }));
    out.push(new Dk.ScatterplotLayer({ id: 'energy', data: P0, getPosition: lngLat, ...px, stroked: true, filled: true,
      getRadius: s => s.kind === 'plant' && s.mw ? 3 + Math.sqrt(s.mw) * 0.6 : 4, getLineWidth: 1.4, getLineColor: A(EN, a('energy')),
      getFillColor: s => s.kind === 'plant' ? A(EN, (s.fossil === false ? .3 : .85) * a('energy')) : A(p.halo, a('energy')) }));
    out.push(new Dk.TextLayer({ characterSet: 'auto', id: 'energy-l', data: P0, getPosition: lngLat, getText: s => s.name, getSize: 11, fontFamily: 'Figtree, sans-serif',
      getColor: A(p.ink, .8 * a('energy')), getTextAnchor: 'start', getPixelOffset: [12, 0], background: true, getBackgroundColor: A(p.halo, .85), backgroundPadding: [3, 1] }));
  }
  if (L.rings && RINGS && !SH) {
    out.push(new Dk.PathLayer({ id: 'rings', data: RINGS, getPath: d => d.path, ...px,
      getColor: A(p.ink, .45 * a('rings')), getWidth: 1, extensions: [dashed], getDashArray: [4, 4] }));
    out.push(new Dk.TextLayer({ characterSet: 'auto', id: 'rings-l', data: RINGS.map(x => ({ t: `${x.km} km`, p: x.path[0] })), getPosition: d => d.p, getText: d => d.t,
      getSize: 11, fontFamily: 'JetBrains Mono, monospace', getColor: A(p.mute, a('rings')), getPixelOffset: [0, -9], background: true, getBackgroundColor: A(p.halo, .9), backgroundPadding: [3, 1] }));
  }
  if (L.radio && RADIO) {
    out.push(new Dk.PathLayer({ id: 'radio', data: [RADIO], getPath: d => d.path, ...px, pickable: true,
      getColor: A(p.ink, .7 * a('radio')), getWidth: 1.5, extensions: [dashed], getDashArray: [1, 4], _kind: 'radio' }));
  }
  if (L.grid && G) {
    const cells = G.cells.filter(c => c.id !== G.node || fine);
    /* over a photograph the grid is drawn light on a dark edge, as the svg ground draws hairlines over tiles */
    const photo = (PM.on.imagery && PM.ground.imagery && z >= 8 && z < SAT_MAX) || (PM.on.drone && PM.ground.drone && z >= 13);
    const gc = photo ? A([255, 255, 255], .8 * a('grid')) : A(p.ink, (z >= 12.5 ? .3 : .22) * a('grid'));
    if (photo) out.push(new Dk.PathLayer({ id: 'grid-edge', data: cells, getPath: d => d.path, ...px, getColor: [0, 0, 0, Math.round(90 * a('grid'))], getWidth: 2.6 }));
    /* solid and dotted are two layers, not one with a switched extension: deck.gl cannot swap a layer's shader */
    out.push(mayLeave(gr)
      ? new Dk.PathLayer({ id: 'grid-dot', data: cells, getPath: d => d.path, ...px, pickable: true, autoHighlight: true, highlightColor: A(p.cells, .35),
        getColor: gc, getWidth: 1.2, extensions: [dashed], getDashArray: [1.5, 3] })
      : new Dk.PolygonLayer({ id: 'grid', data: cells, getPolygon: d => d.path, ...px, pickable: true, autoHighlight: true, highlightColor: A(p.cells, .06),
        filled: true, getFillColor: [0, 0, 0, 0], getLineColor: gc, getLineWidth: 1 }));
  }
  /* the seven at Cell scale (GET /place/cells, token-only): the cell the node stands in and the six touching it, by state.
     State by stroke, never a new hue (SPEC_place_microgis §4): home and held solid in the cells' blue, claimed dashed in
     it, open dotted in grey and unfilled. Home is drawn here, so 'mine' stands aside at res 8. */
  const seven = L.mine && PM.cells && gr === 8;
  if (seven) {
    out.push(new Dk.PolygonLayer({ id: 'seven', data: PM.cells.cells, getPolygon: d => loop(d.ring), ...px, pickable: true, autoHighlight: true,
      highlightColor: A(p.cells, .06), filled: true, getFillColor: d => A(p.cells, (d.state === 'home' ? .12 : d.state === 'held' ? .06 : 0) * a('mine')),
      getLineColor: d => A(d.state === 'open' ? p.mute : p.cells, a('mine')), getLineWidth: d => (d.state === 'home' ? 2.5 : 1.5),
      extensions: [dashed], getDashArray: d => SEVEN_DASH[d.state] }));
  }
  if (L.mine && G && !seven && !fine) {
    out.push(new Dk.PolygonLayer({ id: 'mine', data: [{ id: G.node, ring: G.nodeRing }], getPolygon: d => d.ring, ...px, pickable: true,
      filled: true, getFillColor: A(p.cells, .12 * a('mine')), getLineColor: A(p.cells, a('mine')), getLineWidth: mayLeave(gr) ? 0 : 2.5 }));
    if (mayLeave(gr)) out.push(new Dk.PathLayer({ id: 'mine-dot', data: [{ path: G.nodeRing }], getPath: d => d.path, ...px,
      getColor: A(p.cells, a('mine')), getWidth: 2.5, extensions: [dashed], getDashArray: [2, 2.5] }));
  }
  if (L.models) {
    const M = S.filter(s => s.kind === 'model' || s.kind === 'map');
    /* every model point sits on the node's point except the sea's: one square for the stack, one for the sea */
    const groups = d3.groups(M, s => `${s.lat.toFixed(4)},${s.lon.toFixed(4)}`).map(([, ss]) => ({ ss, p: lngLat(ss[0]) }));
    out.push(new Dk.TextLayer({ characterSet: 'auto', id: 'models', data: groups, getPosition: d => d.p, getText: () => '◇', getSize: 18, pickable: true,
      fontFamily: 'JetBrains Mono, monospace', getColor: A(p.ink, a('models')), getPixelOffset: d => d.ss.length > 1 ? [14, -14] : [0, 0] }));
  }
  if (L.labs) {
    const F = S.filter(s => s.kind === 'facility');
    out.push(new Dk.TextLayer({ characterSet: 'auto', id: 'labs', data: F, getPosition: lngLat, getText: () => '△', getSize: 16, pickable: true,
      fontFamily: 'JetBrains Mono, monospace', getColor: A(p.ink, a('labs')) }));
    out.push(new Dk.TextLayer({ characterSet: 'auto', id: 'labs-l', data: F, getPosition: lngLat, getText: s => s.name, getSize: 11, fontFamily: 'Figtree, sans-serif',
      getColor: A(p.ink, .8 * a('labs')), getTextAnchor: 'start', getPixelOffset: [12, 0], background: true, getBackgroundColor: A(p.halo, .85), backgroundPadding: [3, 1] }));
  }
  if (L.images && caps) {
    out.push(new Dk.TextLayer({ characterSet: 'auto', id: 'images', data: caps, getPosition: c => [c.at[1], c.at[0]],
      getText: () => '■', getSize: 14, pickable: true, fontFamily: 'JetBrains Mono, monospace', getColor: A(p.ink, a('images')),
      background: true, getBackgroundColor: A(p.halo, .9 * a('images')), backgroundPadding: [1, 1] }));
  }
  /* a species somebody here confirmed: filled, at its image's point; named in the list, never beside it (option A) */
  if (L.species && caps) {
    out.push(new Dk.TextLayer({ characterSet: 'auto', id: 'species', data: speciesMarks().filter(d => caps.includes(d.c)), getPosition: d => [d.c.at[1], d.c.at[0]], getText: () => '◆', getSize: 15,
      pickable: true, fontFamily: 'JetBrains Mono, monospace', getColor: A(p.ink, a('species')), getPixelOffset: [0, -13] }));
  }
  const st = S.filter(s => s.kind === 'sensor');
  if (L.public) {
    out.push(new Dk.ScatterplotLayer({ id: 'public', data: st.filter(s => !s.local), getPosition: lngLat, ...px, pickable: true, autoHighlight: true,
      highlightColor: A(p.cells, 1), stroked: true, filled: true, getRadius: 4.5, getFillColor: A(p.halo, a('public')),
      getLineColor: A(p.ink, a('public')), getLineWidth: 1.4 }));
  }
  if (L.own) {
    out.push(new Dk.ScatterplotLayer({ id: 'own', data: st.filter(s => s.local), getPosition: lngLat, ...px, pickable: true, autoHighlight: true,
      highlightColor: A(p.cells, 1), stroked: true, filled: true, getRadius: 5, getFillColor: A(p.ink, a('own')),
      getLineColor: A(p.halo, a('own')), getLineWidth: 1.5 }));
  }
  /* the node itself, always: a ring, not a dot, because /health publishes its cell's centre to strangers. On a sheet the
     house is its res-10 cell, filled (SPEC_place_report §6) */
  if (!SH) out.push(new Dk.ScatterplotLayer({ id: 'node', data: [{ p: D.point }], getPosition: d => d.p, ...px, stroked: true, filled: false,
    getRadius: 9, getLineColor: A(p.cells, 1), getLineWidth: 2 }));
  else if (SH.ring) out.push(new Dk.PolygonLayer({ id: 'house', data: [{ ring: SH.ring }], getPolygon: d => d.ring, ...px, filled: true, stroked: true,
    getFillColor: A(p.ink, .3), getLineColor: A(p.ink, 1), getLineWidth: 1.5 }));
  /* below the drone layer's zoom, each flight is a pin at its bbox's centre, named by its resolution and month; a press
     flies there (press()). The pin is the screen's chip, light on dark, never a drawing colour. */
  const fl = (((PM.meta || {}).layers || {}).drone || {}).mosaics || [];
  if ((PM.ground || {}).drone && z < 13 && fl.length) {
    const pins = fl.filter(x => x.bbox).map(x => ({ q: [(x.bbox[0] + x.bbox[2]) / 2, (x.bbox[1] + x.bbox[3]) / 2],
      t: ['drone', x.gsd_m && `${Math.round(x.gsd_m * 100)} cm`, x.date && d3.utcFormat('%b %Y')(new Date(x.date))].filter(Boolean).join(', ') }));
    out.push(new Dk.ScatterplotLayer({ id: 'drone-pins', data: pins, getPosition: d => d.q, ...px, pickable: true, stroked: true, filled: true,
      getRadius: 10, getFillColor: [20, 20, 20, 235], getLineColor: A(p.ink, 1), getLineWidth: 1.2 }));
    out.push(new Dk.TextLayer({ characterSet: 'auto', id: 'drone-pins-l', data: pins, getPosition: d => d.q, getText: d => d.t, pickable: true, getSize: 11,
      fontFamily: 'Figtree, sans-serif', getColor: [249, 245, 242, 255], getTextAnchor: 'start', getPixelOffset: [15, 0], background: true,   // light on its dark chip in both registers: Paper's ink printed dark on dark (node #1, 16 Nov)
      getBackgroundColor: [20, 20, 20, 235], backgroundPadding: [4, 2] }));
  }
  /* named in the list under the screen, "This house · 0 m": labels never sit on the house (Tomas, 15 Oct, option A) */
  if (PM.measure.length && !SH) {
    const path = PM.measure;
    /* each placed leg labelled with the node's own metres for it; the leg to the cursor is drawn, not measured */
    const legs = (PM.measured && PM.measured.points === PM.measure.length) ? PM.measured.legs_m : [];
    const lab = PM.measure.map((q, i) => ({ q, t: i ? (legs[i - 1] != null ? fmtM(legs[i - 1]) : '…') : PM.from ? '' : 'start' })).filter(d => d.t);
    out.push(new Dk.PathLayer({ id: 'measure', data: [{ path }], getPath: d => d.path, ...px, getColor: A(p.cells, 1), getWidth: 2, extensions: [dashed], getDashArray: [6, 3] }));
    out.push(new Dk.ScatterplotLayer({ id: 'measure-v', data: PM.measure, getPosition: q => q, ...px, getRadius: 3.5, getFillColor: A(p.halo, 1), stroked: true, getLineColor: A(p.cells, 1), getLineWidth: 2 }));
    out.push(new Dk.TextLayer({ characterSet: 'auto', id: 'measure-l', data: lab, getPosition: d => d.q, getText: d => d.t, getSize: 11, fontFamily: 'JetBrains Mono, monospace',
      getColor: A(p.ink, 1), getPixelOffset: [0, -14], background: true, getBackgroundColor: A(p.halo, .95), backgroundPadding: [4, 2] }));
  }
  if (PM.pull && PM.pull.cells.length) out.push(new Dk.PolygonLayer({ id: 'pull', data: PM.pull.cells, getPolygon: d => d.path, ...px, pickable: false,
    filled: true, getFillColor: A(p.ink, .10), getLineColor: A(p.ink, .9), getLineWidth: 2 }));
  return out.concat(drawLayers(p, Dk, px, dashed, A));
}
const SEVEN_DASH = { home: [0, 0], held: [0, 0], claimed: [5, 3], open: [1.5, 3] };   // [0, 0] is solid
const redraw = () => { if (PM.flat) flat(); else if (PM.overlay) PM.overlay.setProps({ layers: layers() }); margin(); };

/* ---------------------------------------------------------------- around the house (option A, Tomas 15 Oct 2026)
   Labels never sit on the house. Every mark in view of the house, its stations, images and species, the public stations
   and the model points, is a ruled row in the list under the screen: its sign, its name and its distance, nearest first
   (SPEC_place_microgis §4 gave the screen's sides to the cake and the tools, so the leaders went). Public stations off
   the map sit on its edge with their distance. Every metre is the node's: GET /nearby for the public stations,
   GET /geo/measure?each for the rest (token-only). Without the token the house's own rows say withheld, first. */
const WH = '<svg class="wh" width="14" height="14" viewBox="0 0 14 14" aria-hidden="true"><rect x="1.5" y="1.5" width="11" height="11"/><path d="M3 11L11 3"/></svg>';
const DIST = new Map();   // the node's metres from its own point, by mark
let NEAR = new Map();
function measureFrom(ms) {
  const need = ms.filter(m => m.key && !DIST.has(m.key)).slice(0, 199);
  if (!need.length || !DOORS_TOKEN()) return;
  need.forEach(m => DIST.set(m.key, null));
  ask(`geo/measure?from_node=true&each=true&path=${need.map(m => m.ll.map(v => v.toFixed(6)).join(',')).join(';')}`)
    .then(r => { r.each.forEach((e, i) => DIST.set(need[i].key, e.m)); margin(); }).catch(() => need.forEach(m => DIST.delete(m.key)));
}
function marks() {
  const st = outside(D.sensors).filter(s => s.lat != null), on = id => PM.on[id] && (!PM.flat || FLAT.includes(id)), out = [];
  const nm = s => plain(s.name || s.sensor_id);
  out.push({ house: true, name: 'This house', ll: D.point, sw: 'house', m: 0 });
  if (on('own')) st.filter(s => s.kind === 'sensor' && s.local).forEach(s => out.push({ pick: { kind: 'station', s }, name: nm(s), ll: lngLat(s), sw: 'pt-own', key: s.sensor_id, own: true }));
  if (on('public')) st.filter(s => s.kind === 'sensor' && !s.local).forEach(s => out.push({ pick: { kind: 'station', s }, name: nm(s), ll: lngLat(s), sw: 'pt-pub', key: s.sensor_id, pub: true,
    m: NEAR.has(s.sensor_id) ? NEAR.get(s.sensor_id) * 1000 : undefined }));
  if (on('models')) d3.groups(st.filter(s => s.kind === 'model' || s.kind === 'map'), s => `${s.lat.toFixed(4)},${s.lon.toFixed(4)}`)
    .forEach(([k, ss]) => out.push({ pick: { kind: 'model', ss, p: lngLat(ss[0]) }, name: ss.length > 1 ? `Model points, ${ss.length}` : nm(ss[0]), ll: lngLat(ss[0]), sw: 'pt-model', key: 'm' + k }));
  if (on('images') && PM.caps) PM.caps.forEach(c => out.push({ pick: { kind: 'image', c }, name: `${KIND[c.kind] || c.kind} image`, ll: [c.at[1], c.at[0]], sw: 'pt-img', key: 'c' + c.id }));
  if (on('species') && PM.caps) speciesMarks().forEach(x => out.push({ pick: { kind: 'image', c: x.c }, name: x.t, ll: [x.c.at[1], x.c.at[0]], sw: 'pt-sp', key: 'c' + x.c.id, dy: -13 }));
  return out;
}
function margin() {
  const el = $('#pmargin'); if (!el) return;
  const tok = !!DOORS_TOKEN(), map = PM.map, box = map && map.getContainer(), W = box ? box.clientWidth : 0, H = box ? box.clientHeight : 0;
  const all = marks().map(m => { const q = map ? map.project(m.ll) : null; return { ...m, x: q ? q.x : null, y: q ? q.y + (m.dy || 0) : null }; });
  const inView = m => m.x == null || (m.x >= 0 && m.x <= W && m.y >= 0 && m.y <= H);
  /* without the token the house's own stations stand at its published cell centre: their names and places are the household's */
  let rows = all.filter(m => inView(m) && !(m.own && !tok));
  const hy = all[0].y;
  if (!tok) rows.push({ held: 'This house’s stations', y: hy }, ...(PM.caps ? [] : [{ held: 'Images and species', y: hy }]));
  measureFrom(rows.filter(m => !m.house && !m.pub && !m.held));
  const far = m => m.held || m.house ? 0 : m.x == null ? (m.m ?? DIST.get(m.key) ?? 1e9) : Math.hypot(m.x - all[0].x, m.y - all[0].y);
  const MAX = 12, more = rows.length > MAX ? rows.length - (MAX - 1) : 0;
  if (more) rows = rows.sort((a, b) => far(a) - far(b)).slice(0, MAX - 1);
  rows.sort((a, b) => far(a) - far(b) || (a.held ? -1 : b.held ? 1 : 0));
  const dist = m => m.house ? '0 m' : m.m != null ? fmtM(m.m) : DIST.get(m.key) != null ? fmtM(DIST.get(m.key)) : tok ? '…' : '—';
  el.innerHTML = `<div class="pmh">around the house <b>nearest first</b></div>`
    + rows.map((m, i) => m.held ? `<div class="mr held">${WH}<span>${esc(m.held)}</span><b>withheld</b></div>`
      : `<button class="mr" data-i="${i}">${m.house ? sign('sign-house') : `<i class="sw ${m.sw}" aria-hidden="true"></i>`}<span class="said">${esc(m.name)}</span><b>${dist(m)}</b></button>`).join('')
    + (more ? `<div class="mr"><i></i><span>+ ${more} more, further from the house</span><b></b></div>` : '')
    + `<p class="fine">${tok ? 'Metres from the node’s own point, by the node (GET /geo/measure, /nearby).' : 'Where the house’s things are is the household’s, so distances here are from the cell’s centre. Unlock this screen in ' + UNLOCK_AT + '.'}</p>`;
  document.querySelectorAll('#pmargin button.mr').forEach(b => b.onclick = () => {
    const m = rows[+b.dataset.i]; PM.pick = m.pick || null; if (PM.map) popup(PM.pick); facts();
  });
  edges(all, inView, W, H);
}
/* while a shape is drawn and the map zooms or pans without the mouse moving (a wheel, a pinch, the + and − keys), the
   leg to the pointer keeps its end under the pointer, not at the map point it was over before */
function following() {
  const d = PM.draw; if (!DRAWING() || !d.state || !d.state.pts.length || !PM.lastPt || !PM.map || d.hover == null) return;   // a shape from the keyboard has no leg to the pointer
  const q = PM.map.unproject([PM.lastPt.x, PM.lastPt.y]); d.hover = [q.lng, q.lat];
  figureOnly(); if (PM.overlay) PM.overlay.setProps({ layers: layers() });
}
/* The margin is a list under the screen now (SPEC_place_microgis §4): no leaders. Public stations off the map: a hollow
   mark on the screen's edge, pointing at them, with the node's distance; the nearest six. They are DOM over the canvas,
   so they follow the map on every `move` (one frame at a time, below), not only when it settles: on node #1 they
   stayed where they were through a zoom and jumped at its end (5 Nov). */
function edges(all, inView, W, H) {
  const ed = $('#pedges'), map = PM.map;
  if (!ed || !map) { if (ed) ed.innerHTML = ''; return; }
  if (!all) {
    const box = map.getContainer(); W = box.clientWidth; H = box.clientHeight;
    all = marks().filter(m => m.pub).map(m => { const q = map.project(m.ll); return { ...m, x: q.x, y: q.y }; });
    inView = m => m.x >= 0 && m.x <= W && m.y >= 0 && m.y <= H;
  }
  const cx = W / 2, cy = H / 2, I = 26, IL = I, IR = 72;
  ed.setAttribute('viewBox', `0 0 ${W} ${H}`);
  ed.innerHTML = all.filter(m => m.pub && !inView(m) && m.m != null).sort((a, b) => a.m - b.m).slice(0, 6).map(m => {
    const dx = m.x - cx, dy = m.y - cy, t = Math.min(dx > 0 ? (W - IR - cx) / dx : dx < 0 ? (IL - cx) / dx : 1e9, dy > 0 ? (H - I - cy) / dy : dy < 0 ? (I - cy) / dy : 1e9);
    const ex = cx + dx * t, ey = cy + dy * t, a = Math.atan2(dy, dx) * 180 / Math.PI;
    return `<circle class="pub" cx="${ex.toFixed(1)}" cy="${ey.toFixed(1)}" r="4.5"/><path d="M8,-4L13,0L8,4" transform="translate(${ex.toFixed(1)},${ey.toFixed(1)}) rotate(${a.toFixed(0)})"/>`
      + `<text x="${(ex + (ex > cx ? -12 : 12)).toFixed(1)}" y="${(ey + (ey > cy ? -10 : 18)).toFixed(1)}" text-anchor="${ex > cx ? 'end' : 'start'}">${fmtM(m.m)}</text>`;
  }).join('');
}

/* ---------------------------------------------------------------- the cake (SPEC_place_microgis §4, §5)
   The left column: results, then the layers from the sky down to the ground, then the frame (doors-cake.js). A section is
   its name and how many of its rows are on; a row is one line, as in the v2 drawing: a switch (filled with the knob to the right on,
   hollow with the knob to the left off, a dotted mark where it cannot switch), the layer's name and a word for its source, or for why it cannot draw (token-only, not
   here, live map). The whole sentence, with its unlock link or its command, is the row's title and goes to the status
   line under the screen when the row is pressed. The wind's hour and a layer's opacity sit under their rows; the species
   confirmed here open under theirs (#spd, moved in, never redrawn). */
const BY = Object.fromEntries(LAYERS.map(l => [l.id, l]));
/* a layer as the cake says it: `off` cannot be switched, `brief` is the word on the row, `long` the sentence (html) */
function about(l) {
  const z = PM.map ? PM.map.getZoom() : 0, flatOff = PM.flat && !FLAT.includes(l.id), off = l.empty || flatOff;
  const hidden = PM.on[l.id] && !PM.flat && ((l.minz != null && z < l.minz) || (l.maxz != null && z > l.maxz));
  const zoom = hidden ? (l.minz != null && z < l.minz ? 'zoom in' : 'zoom out') : '';
  const long = l.soon ? `${esc(l.sub)} · not yet` : flatOff ? 'drawn on the live map only' : l.locked ? `withheld · unlock this screen in ${UNLOCK_AT}`
    : off ? l.none || `The ${l.pack} pack has nothing here yet${l.why ? ` · <code>${esc(l.why)}</code>` : ''}` : esc(l.sub) + (zoom ? ` · ${zoom} to see` : '');
  const brief = l.soon ? esc(l.src) : flatOff ? 'live map' : l.locked ? `${WH}token-only` : off ? 'not here' : zoom || esc(l.src);
  return { off, brief, long };
}
/* the cake as the report's page 2 says it (SPEC_place_report §5): each row held, held in part or not yet, its source, and
   where it is empty the command that fills it or the cake's own words for it. A withheld row's source is token-only, as
   the cake says it. Never a row's `sub`: the species row's names the species, which stay the household's. */
const placeCake = () => cakeSections(LAYERS, PM.on).map(s => ({ name: s.name, rows: s.rows.map(({ id }) => {
  const l = BY[id], gap = l.empty || l.part;
  return { name: l.name, src: l.locked ? 'token-only' : l.src, held: l.soon ? 'not yet' : l.locked ? 'withheld' : l.part ? 'held in part' : l.empty ? 'not yet' : 'held',
    fill: !l.soon && !l.locked && gap && l.why || null, none: !l.soon && !l.locked && gap && !l.why && l.none || null };
}) }));
function panel() {
  const spd = document.getElementById && document.getElementById('spd');
  const row = r => {
    const l = BY[r.id], a = about(l);
    return `<div class="lyr" data-l="${l.id}"><button class="ly ${r.state}${l.locked ? ' held' : ''}" aria-pressed="${r.state === 'on'}"${a.off ? ' aria-disabled="true"' : ''} title="${esc(`${l.name} · ${a.long.replace(/<[^>]+>/g, '')}`)}">`
      + `<i aria-hidden="true"></i><span>${esc(l.name)}</span><small>${a.brief}</small></button>`
      + (l.id === 'wind' && PM.on.wind && PM.wind ? `<label class="whr"><span>now</span><input type="range" min="0" max="${PM.wind.times.length - 1 - nowIdx()}" step="1" value="${PM.windStep}" aria-label="Hours ahead"><b>${PM.windStep ? `+${PM.windStep} h` : 'now'}</b></label>` : '')
      + (a.off || l.still || PM.flat ? '' : `<label class="opw"><span class="opl">opacity</span><input class="op" type="range" min="0" max="1" step="0.05" value="${PM.alpha[l.id]}" aria-label="${esc(l.name)} opacity" ${PM.on[l.id] ? '' : 'disabled'}></label>`)
      + (l.id === 'species' ? '<div data-slot="species"></div>' : '') + `</div>`;
  };
  const fo = document.activeElement && document.activeElement.dataset && document.activeElement.dataset.f;
  /* the head says what the column is and what a press does: the rows are switches, and read as text without it
     (Tomas, 17 Nov 2026) */
  $('#cake').innerHTML = '<header class="ckh"><h2>Layers</h2><p>Press a row to draw it on the map or take it off.</p></header>'
    + yourMaps() + cakeSections(LAYERS, PM.on).map(s => `<section class="ck" data-cake="${s.id}"><h2><span>${esc(s.name)}</span>`
    + `<b>${s.rows.length ? `${s.rows.filter(r => r.state === 'on').length} of ${s.rows.length} on` : 'none yet'}</b></h2>${s.rows.map(row).join('')}</section>`).join('');
  const slot = document.querySelector('#cake [data-slot="species"]'); if (spd && slot) slot.replaceWith(spd);
  document.querySelectorAll('#cake .lyr').forEach(w => {
    const id = w.dataset.l, b = w.querySelector('button.ly'), op = w.querySelector('.op'), wh = w.querySelector('.whr input');
    /* a press says the row's whole sentence in the status line; a row that can switch, switches */
    b.onclick = () => { PM.pick = { kind: 'layer', id }; if (about(BY[id]).off) facts(); else setLayer(id, !PM.on[id]); };
    if (wh) wh.oninput = () => { PM.windStep = +wh.value; w.querySelector('.whr b').textContent = PM.windStep ? `+${PM.windStep} h` : 'now'; windResample(); facts(); hourPill(); };
    if (op) op.oninput = () => { PM.alpha[id] = +op.value; applyBase(); redraw(); };
  });
  wireMaps();
  const f = fo && document.querySelector(`#ymaps [data-f="${fo}"]`); if (f) f.focus();   // a press in your maps keeps its focus
}
/* one switch, from the cake or from a tool (doors-place.js): the map, the cake, the credits and the tools follow it */
function setLayer(id, on) {
  const a = document.activeElement, inCake = !!(a && a.closest && a.closest('#cake'));
  PM.on[id] = on; applyBase(); redraw(); panel(); credits(); windSync(); facts(); hourPill(); baseSwitch();
  if (window.placeTools) window.placeTools();
  const b = inCake && document.querySelector(`#cake [data-l="${id}"] button`); if (b) b.focus();
}

/* ---------------------------------------------------------------- the scale selector and the tools */
function chrome() {
  $('#mapbar').innerHTML = `<div class="scales" role="group" aria-label="Scale">${SCALES.map(([r, n]) =>
    `<button data-r="${r}" class="${r === PM.res ? 'on' : ''} ${mayLeave(r) ? 'leave' : ''}" title="${esc(`${n}: resolution ${r}, about ${fmtM(EDGE(r))} to an edge${mayLeave(r) ? ' · coarse enough to leave the machine' : ''}`)}"><b>${n}</b><span>${r}</span></button>`).join('')}</div>`;
  document.querySelectorAll('.scales button').forEach(b => b.onclick = () => fly(+b.dataset.r));
  hourPill();
}
/* the hour the screen draws, top centre: the node's last reading, or the wind's hour ahead, stepped from here too */
function hourPill() {
  const el = $('#phour'); if (!el) return;
  const W = PM.on.wind && PM.wind, t = W ? PM.wind.times[windHour()] : D.as_of, max = W ? PM.wind.times.length - 1 - nowIdx() : 0;
  const had = el.contains(document.activeElement) && document.activeElement.dataset.d;   // innerHTML drops focus: put it back, as the cake does
  el.innerHTML = (W ? `<button data-d="-1" aria-label="An hour earlier"${PM.windStep ? '' : ' disabled'}>‹</button>` : '')
    + `<b>${esc(dLabel(dayOf(t)))} · ${hhmm(t)}${W && PM.windStep ? ` · +${PM.windStep} h` : ''}</b>`
    + (W ? `<button data-d="1" aria-label="An hour later"${PM.windStep < max ? '' : ' disabled'}>›</button>` : '');
  el.querySelectorAll('button').forEach(b => b.onclick = () => {
    PM.windStep = Math.max(0, Math.min(max, PM.windStep + +b.dataset.d)); windResample(); facts(); panel(); hourPill();
  });
  const f = had && el.querySelector(`button[data-d="${had}"]:not(:disabled)`) || (had && el.querySelector('button:not(:disabled)')); if (f) f.focus();
}
async function fly(r) {
  let c; try { c = await cellAt(D.point[0], D.point[1], r); } catch (e) { offline(e.message); return; }
  const bb = loop(c.ring).reduce((m, [x, y]) => [Math.min(m[0], x), Math.min(m[1], y), Math.max(m[2], x), Math.max(m[3], y)], [180, 90, -180, -90]);
  /* the zoom resFor() reads back as r: the rung's edge midway (geometrically) between 56 px, where r begins, and
     where r + 1 would take over. fitBounds with padding refused to move on any landscape map and landed a rung off
     elsewhere, so a button and a scroll now share one rule, whatever the map's shape. */
  const px = 56 * Math.sqrt(EDGE(r) / EDGE(r + 1));
  PM.map.easeTo({ center: [(bb[0] + bb[2]) / 2, (bb[1] + bb[3]) / 2], zoom: Math.log2(px * mPerPx(0) / EDGE(r)),
    duration: CLOCK.reduced() ? 0 : 700 });
}
/* The screen's right edge, top to bottom (SPEC_place_microgis §4): Map only and Full screen, back to this node's cell,
   and Download, whose menu holds the image of the screen and the open map in three formats. Zoom sits apart at the bottom
   right, with the base switch beside it. Measuring became the line key and Inspect became Select (the drawing keys,
   below); From the house is in the Tools menu on the top line (doors-place.js), and ends on a second press or Esc. */
const MEASURING = () => PM.tool === 'from';
const COL = [['wide', 'Map only', '\\'], ['full', 'Full screen', 'F'], ['fit', 'Back to this node’s cell'], ['dl', 'Download']];
function tools() {
  const el = document.createElement('div'), zm = document.createElement('div'), menu = PM.dlm = document.createElement('div'), base = PM.basesw = document.createElement('div');
  el.className = 'tools'; zm.className = 'zoom'; menu.className = 'dlmenu'; menu.id = 'dlmenu'; menu.hidden = true; base.className = 'pbase';
  menu.setAttribute('role', 'group'); menu.setAttribute('aria-label', 'Download'); base.setAttribute('role', 'group'); base.setAttribute('aria-label', 'Base map');
  /* Map only folds the left and grows the screen, Full screen is the browser's own on the screen (doors-place.js): its key is not drawn where
     the browser has no element full screen (Safari on iPhone) */
  const bench = document.querySelector('.bench'), both = !!bench && bench.classList.contains('mo');
  el.innerHTML = COL.filter(([k]) => k !== 'full' || document.fullscreenEnabled).map(([k, t, key]) => `<button type="button" data-t="${k}" class="${k === 'fit' || k === 'dl' ? 'gap' : ''}" aria-label="${t}" title="${key ? `${t} · ${key}` : t}"`
    + (k === 'wide' ? ` aria-pressed="${both}"` : k === 'full' ? ` aria-pressed="${!!document.fullscreenElement}"` : '')
    + (k === 'dl' ? ' aria-expanded="false" aria-controls="dlmenu"' : '')
    + `><svg viewBox="0 0 20 20" aria-hidden="true">${KEYICON[k]}</svg></button>`).join('');
  zm.innerHTML = [['in', '+', 'Zoom in'], ['out', '−', 'Zoom out']].map(([k, g, t]) => `<button data-t="${k}" title="${t}" aria-label="${t}"><span class="g" aria-hidden="true">${g}</span></button>`).join('');
  PM.dlb = el.querySelector('[data-t="dl"]');
  PM.setTool = k => {
    const d = PM.draw;
    PM.tool = k; PM.hover = null; d.state = null; d.hover = null; d.corner = null; d.err = '';
    PM.pull = k === 'pull' ? { cells: [], mark: null, ans: null, err: '', busy: false } : null;
    if (MEASURING()) { PM.measure = []; PM.measured = null; PM.from = true; } else if (PM.measure.length) { PM.measure = []; PM.measured = null; PM.from = false; }
    /* a double press finishes a line, so it zooms only while nothing is being drawn */
    PM.map.doubleClickZoom[k === 'select' || k === 'from' || k === 'pull' ? 'enable' : 'disable']();
    if (PM.keys) PM.keys.querySelectorAll('button[data-k]').forEach(b => { if (b.dataset.k !== 'undo') b.setAttribute('aria-pressed', String(b.dataset.k === k)); });
    if (k === 'image' && d.sel != null) picker(d.sel);
    readout(); drawForm(); redraw(); facts(); if (window.placeTools) window.placeTools();
  };
  el.onclick = e => {
    const k = e.target.closest('button')?.dataset.t; if (!k) return;
    if (k === 'in') PM.map.zoomIn(); else if (k === 'out') PM.map.zoomOut(); else if (k === 'fit') fly(8); else if (k === 'dl') dlMenu(menu.hidden);
    else if (k === 'wide') window.placeWide(); else if (k === 'full') window.placeFull();
  };
  zm.onclick = el.onclick;
  menu.onclick = e => { const k = e.target.closest('button')?.dataset.dl; if (k) download(k); };
  menu.onkeydown = e => { if (e.key === 'Escape') { e.stopPropagation(); dlMenu(false); if (PM.dlb) PM.dlb.focus(); } };
  base.onclick = e => { const b = e.target.closest('button')?.dataset.b; if (!b) return; PM.on.drone = b === 'drone'; setLayer('imagery', b === 'satellite'); };
  const box = PM.map.getContainer(); box.append(el, zm, menu, base); baseSwitch();
  /* the keys and the readout: only for a screen holding the token, since every drawing is the household's */
  if (!DOORS_TOKEN()) return;
  const keys = PM.keys = document.createElement('div'), pan = document.createElement('div');
  keys.className = 'dkeys'; keys.setAttribute('role', 'toolbar'); keys.setAttribute('aria-label', 'Draw'); keys.innerHTML = '<b class="dkh" aria-hidden="true">Draw</b>' + keysHTML();
  pan.className = 'dpanel'; pan.innerHTML = '<div id="dread" class="dread"></div><p id="dsaid" class="vh" aria-live="polite"></p><div id="dform" class="dform" hidden></div>';
  keys.onclick = e => { const b = e.target.closest('button[data-k]'); if (!b) return; if (b.dataset.k === 'undo') undo(); else { PM.setTool(b.dataset.k); toScreen(b.dataset.k); } };
  box.append(keys, pan);
  readout();
}

/* The base: satellite · streets · drone, each only where the node holds it. The rasters sit over the street map and
   under its names, so streets is both rasters off. */
function baseSwitch() {
  const el = PM.basesw, G = PM.ground || {}; if (!el) return;
  const now = PM.on.drone && G.drone ? 'drone' : PM.on.imagery && G.imagery ? 'satellite' : 'streets';
  const B = [G.imagery && 'satellite', 'streets', G.drone && 'drone'].filter(Boolean);
  el.hidden = B.length < 2;
  el.innerHTML = B.map(b => `<button type="button" data-b="${b}" aria-pressed="${b === now}">${b}</button>`).join('');
}
/* DOWNLOAD (§4, §11): the image of the screen is the canvas, drawings and all; the open map's GeoJSON, KML and DXF are
   the node's own files (GET /place/maps/{id}.ext, token-only, each one a ledger row), fetched with the token and handed
   to the browser under the node's name for them. Everything on the screen is the image and each map on the screen in
   its three formats, one download each: no zip. */
const slug = t => String(t || '').normalize('NFKD').replace(/[\u0300-\u036f]/g, '').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '');
const onScreen = () => (PM.maps || []).filter(m => !PM.mapOff.has(m.id));
function dlMenu(open) {
  const menu = PM.dlm; if (!menu) return;
  menu.hidden = !open; if (PM.dlb) PM.dlb.setAttribute('aria-expanded', String(open));
  if (!open) return;
  const m = openMap(), no = m ? '' : ' disabled', n = 1 + 3 * onScreen().length;
  const it = (k, t, f, x = '') => `<button type="button" data-dl="${k}" aria-label="${t} · ${f}"${x}><span>${t}</span><code>${f}</code></button>`;
  menu.innerHTML = `<p class="dlh">download ${m ? esc(m.name) : 'this screen'}</p>`
    + it('png', 'Image of the screen', 'PNG') + it('geojson', 'For upstream and QGIS', 'GeoJSON', no) + it('kml', 'For Google Earth, phones', 'KML', no) + it('dxf', 'For CAD, in metres', 'DXF', no)
    + `<hr><button type="button" data-dl="all" aria-label="Everything on the screen"><span>Everything on the screen</span><code>${n} file${n === 1 ? '' : 's'}</code></button>`
    + '<button type="button" data-dl="report" aria-label="Report, to print or save as PDF"><span>Report, to print or save as PDF</span><code>PDF</code></button>'
    + (PM.dlErr ? `<p class="err" role="status">${esc(PM.dlErr)}</p>` : '');
  const f = menu.querySelector('button'); if (f) f.focus();
}
const save = (href, name) => { const a = document.createElement('a'); a.href = href; a.download = name; a.click(); };
function png(m) {
  const name = `${slug(D.node.name) || 'node'}-${slug(m ? m.name : 'place') || 'map'}-${doorsLocal(new Date().toISOString(), D.tz).slice(0, 10)}.png`;
  PM.map.triggerRepaint(); PM.map.once('render', () => save(screenImage().toDataURL('image/png'), name));
}
/* the scale bar's length, the PNG's and the sheet's: the longest round length under 120 px */
const barLen = mpp => [1, 2, 5].flatMap(a => [1, 10, 100, 1e3, 1e4, 1e5].map(b => a * b)).sort((a, b) => a - b).filter(v => v / mpp <= 120).pop() || 1;
/* The map's canvas holds the base and the drawings; the scale bar and the credit are page elements, so the image would
   leave without its attribution (ODbL, CC BY, Copernicus: §4 puts both in the PNG). They are drawn onto a copy here,
   in a dark strip along the foot that reads on the satellite and on the black street map. */
function screenImage() {
  const src = PM.map.getCanvas(), k = src.width / (src.clientWidth || src.width) || 1, W = src.width / k;
  const cv = document.createElement('canvas'); cv.width = src.width; cv.height = src.height;
  const x = cv.getContext('2d'); x.drawImage(src, 0, 0); x.scale(k, k);
  /* the scale: the longest round length under 120 px, at the map's centre */
  const c = PM.map.getCenter(), mpp = 40075016.686 * Math.cos(c.lat * Math.PI / 180) / (512 * 2 ** PM.map.getZoom()), len = barLen(mpp);
  const bar = len / mpp, label = len >= 1000 ? `${len / 1000} km` : `${len} m`;
  /* the credit, wrapped at its own dots to fit beside the scale */
  x.font = '400 10px Figtree, sans-serif';
  const room = W - bar - 90, lines = [];
  for (const piece of creditList().join(' · ').split(' · ')) {
    const last = lines[lines.length - 1], next = last ? `${last} · ${piece}` : piece;
    if (last && x.measureText(next).width > room) lines.push(piece); else lines[lines.length ? lines.length - 1 : 0] = next;
  }
  const H = src.height / k, strip = 10 + 13 * Math.max(1, lines.length);
  x.fillStyle = 'rgba(20,20,20,.85)'; x.fillRect(0, H - strip, W, strip);
  x.fillStyle = '#F9F5F2'; x.strokeStyle = '#F9F5F2'; x.lineWidth = 1.5; x.textBaseline = 'middle';
  x.beginPath(); x.moveTo(10, H - strip / 2 - 3); x.lineTo(10, H - strip / 2 + 3); x.lineTo(10 + bar, H - strip / 2 + 3); x.lineTo(10 + bar, H - strip / 2 - 3); x.stroke();
  x.textAlign = 'left'; x.fillText(label, 16 + bar, H - strip / 2);
  x.textAlign = 'right'; lines.forEach((t, i) => x.fillText(t, W - 10, H - strip + 11.5 + 13 * i));
  return cv;
}
/* THE SHEET'S PICTURE (SPEC_place_report §3, §6): the screen in the register chosen, Paper being the light palette, with
   the house blurred to its res-10 cell (layers()), taken from the canvas once the map is idle, as the PNG's is but
   without its strip. Then the screen goes back to black. The house's cell and each point's are the node's answers
   (GET /geo/cell); the rings and the wind are left out of the legend, since the sheet does not draw them. */
const NOMAP = 'The map of the house stays on this house’s own screens, because where it stands is the household’s. Unlock this screen in Set up › This screen to print it.';
async function placeSheet(paper) {
  const date = doorsLocal(new Date().toISOString(), D.tz).slice(0, 10);
  if (!DOORS_TOKEN()) return { none: NOMAP, date };
  if (!PM.map) return { none: 'This browser gave the map no WebGL, so there is no picture of it to print.', date };
  /* loaded() is false while tiles are still coming, not only before the first load, and 'load' fires once: arriving from
     Place itself (Download, the Tools row, Ask) waited on it for ever. Idle comes after either, and the wait is bounded. */
  if (!PM.map.loaded()) await new Promise(r => { PM.map.once('idle', r); setTimeout(r, 15000); });
  const home = (D.geometry.ladder.find(l => l.res === 10) || {}).id || null;
  const pts = outside(D.sensors).filter(s => s.lat != null && (s.local || s.kind === 'model' || s.kind === 'map'));
  const [ring, ...ids] = await Promise.all([home ? cellFacts(home).then(c => loop(c.ring), () => null) : null,
    ...pts.map(s => cellAt(s.lon, s.lat, 10).then(c => c.id, () => null))]);
  PM.sheet = { paper, home, ring, cells: new Map(pts.map((s, i) => [s.sensor_id, ids[i]])) };
  try {
    PM.map.resize(); if (paper) { PM.map.setStyle(style(PAL.light)); applyBase(); }
    redraw();
    await new Promise(r => { PM.map.once('idle', r); PM.map.triggerRepaint(); setTimeout(r, 8000); });
    const cv = PM.map.getCanvas(), z = PM.map.getZoom(), mpp = mPerPx(z);
    return { img: cv.toDataURL('image/png'), w: cv.clientWidth, h: cv.clientHeight, mpp, bar: barLen(mpp), dark: !paper, res: PM.res, date,
      rung: (SCALES.find(([r]) => r === PM.res) || [])[1] || null, credits: creditList(), legend: sheetLegend(LAYERS, { ...PM.on, rings: false, wind: false }, z),
      maps: onScreen().map(m => ({ name: m.name, colours: [...new Set((MARKS[m.id] || []).map(k => k.colour))].map(n => (PM.palette || {})[n]).filter(Boolean) })) };
  } finally {
    PM.sheet = null; if (paper) { PM.map.setStyle(style()); applyBase(); }
    redraw();
  }
}
async function mapFile(m, ext) {
  try {
    const r = await doorsFetch(`${API}place/maps/${m.id}.${ext}?actor=${encodeURIComponent(actor())}`);
    if (!r.ok) { PM.dlErr = `${m.name}, ${ext}: ${refused({ ...(await r.json().catch(() => ({}))), status: r.status })}`; return; }
    const name = ((r.headers.get('content-disposition') || '').match(/filename="([^"]+)"/) || [])[1] || `${slug(m.name)}.${ext}`;
    const u = URL.createObjectURL(await r.blob()); save(u, name); setTimeout(() => URL.revokeObjectURL(u), 1000);
  } catch (e) { PM.dlErr = `The node did not answer: ${e.message}`; }
}
async function download(k) {
  const m = openMap(), all = k === 'all'; PM.dlErr = '';
  dlMenu(false); if (PM.dlb) PM.dlb.focus();
  if (k === 'report') { location.hash = '#place/report'; return; }   // the sheet takes its own picture (placeSheet)
  if (k === 'png' || all) png(m);
  for (const x of all ? onScreen() : k !== 'png' && m ? [m] : []) for (const ext of all ? ['geojson', 'kml', 'dxf'] : [k]) await mapFile(x, ext);
  if (PM.dlErr) dlMenu(true);   // a file the node refused says why, in the menu
}

/* ---------------------------------------------------------------- drawing, and your maps (SPEC_place_microgis §4, §8, §10)
   The keys on the screen's left edge, the readout beside them and, under it, a form for the drawing in hand. A drawing is
   a GeoJSON feature in one of the household's named maps (app/maps.py, token-only), drawn here as deck.gl layers in the
   same overlay as the rest, so the PNG holds it. While somebody draws, the readout's figure is the page's sphere
   (doors-draw.js); once kept, the measure is PostGIS's. Nothing needs a drag: a press adds a point, a press on a corner
   and then on its new place moves it, and the keyboard does all of it from the map's centre. Drawing colours are the
   node's palette (GET /place/maps), on the screen and in the table's swatches, never on the page around them. */
const MARKS = {};                 // map id → its drawings, as GET /place/maps/{id}/marks answers them
const UNDO = [];                  // what ⌘Z takes back, newest last: each one a call back to the node
PM.draw = { map: null, state: null, sel: null, colour: 1, corner: null, kc: 0, hover: null, via: null, edit: null, asked: null, naming: false,
  pick: null, err: '', mapErr: '', said: '', preview: null, focusLabel: false, open: false, auto: false };
PM.mapOff = new Set();
const DRAWS = ['marker', 'line', 'area', 'note'];
const DRAWING = () => DRAWS.includes(PM.tool);
const KEYNAME = { select: 'Select', marker: 'Marker', line: 'Line, with distance', area: 'Area, with surface', note: 'Note', image: 'Image' };
const TOOLWORD = { select: 'select', marker: 'marker', line: 'line', area: 'area', note: 'note', image: 'image', from: 'from the house', pull: 'pull' };
const KEYICON = { select: '<path d="M5 3l12 6-5 2-2 5z"/>', marker: '<path d="M10 18s-5-5.2-5-9a5 5 0 0110 0c0 3.8-5 9-5 9z"/><circle cx="10" cy="9" r="1.8"/>',
  line: '<circle cx="4" cy="15" r="1.6"/><circle cx="16" cy="5" r="1.6"/><path d="M5.3 13.8L14.7 6.2" stroke-dasharray="2 2"/>',
  area: '<path d="M4 6l7-3 5 5-3 8-9-2z"/>', note: '<path d="M4 4h12v9l-3 3H4z"/><path d="M13 16v-3h3"/>',
  image: '<rect x="3" y="5" width="14" height="10" rx="1"/><circle cx="8" cy="9" r="1.5"/><path d="M3 14l4-3 3 2 3-3 4 4"/>',
  undo: '<path d="M7 5L3 9l4 4"/><path d="M3 9h9a5 5 0 010 10h-2"/>',
  /* the screen's right column (Map only, Full screen, home, Download), from the mockup */
  wide: '<path d="M3 10h14M6 7l-3 3 3 3M14 7l3 3-3 3"/>', full: '<path d="M3 7V3h4M13 3h4v4M17 13v4h-4M7 17H3v-4"/>',
  fit: '<path d="M3 9l7-6 7 6v8H3z"/>', dl: '<path d="M10 3v10M6 9l4 4 4-4M4 17h12"/>' };
/* the mockup's READ words for the two keys doors-draw.js's figure() has no hint for */
const HINT_SEL = 'Press a drawing to change its colour, note or image.';
/* not the mockup's "its location is the drawing's": a photo's own GPS still wins on the node (packs/eyes) */
const HINT_IMG = 'The image stays on this node. The map only names which one it is, and the file never leaves.';
const MAPKEY = 'planetai_place_map';
const actor = () => { try { return localStorage.getItem('planetai_actor') || ''; } catch (e) { return ''; } };
const send = (method, p, body) => doorsFetch(API + p, { method, headers: body ? { 'content-type': 'application/json' } : {}, body: body ? JSON.stringify(body) : undefined })
  .then(async r => ({ ...(await r.json().catch(() => ({}))), ok: r.ok, status: r.status }))
  .catch(e => ({ ok: false, status: 0, detail: `The node did not answer: ${e.message}` }));
/* the node's sentence: a string, or {code, text} where the page acts on the code (the share warning) */
const refused = r => (typeof r.detail === 'string' ? r.detail : r.detail && typeof r.detail.text === 'string' ? r.detail.text : `The node refused it (${r.status}).`);
const mapById = id => (PM.maps || []).find(m => m.id === id) || null;
const openMap = () => mapById(PM.draw.map);
const mine = m => !!m && !m.agent && !m.from_node;
const markById = id => (id == null ? null : Object.values(MARKS).flat().find(k => k.id === id) || null);
const shownMarks = () => (PM.maps || []).filter(m => !PM.mapOff.has(m.id)).flatMap(m => MARKS[m.id] || []);
const geomOf = k => (PM.draw.preview && PM.draw.preview.id === k.id ? PM.draw.preview.geometry : k.geometry);
/* a drawing's points as they were pressed: an area's ring without its closing point */
const ptsOf = k => { const g = geomOf(k); return g.type === 'Point' ? [g.coordinates] : g.type === 'LineString' ? g.coordinates : g.coordinates[0].slice(0, -1); };
const centreOf = k => { const q = ptsOf(k); return [d3.mean(q, p => p[0]), d3.mean(q, p => p[1])]; };
const colourOf = n => (PM.palette && PM.palette[n] ? [1, 3, 5].map(i => parseInt(PM.palette[n].slice(i, i + 2), 16)) : P().ink);
const measureOf = k => (k.kind === 'area' && k.area_m2 != null ? fmtArea(k.area_m2).split(' · ')[0] : k.kind === 'line' && k.length_m != null ? fmtLen(k.length_m) : '—');
const remember = id => { PM.draw.map = id; try { localStorage.setItem(MAPKEY, String(id)); } catch (e) { /* no storage here */ } };
/* the issues asked on Now (engine _asking), each as the Done button carries it: an event, else an alert */
const openIssues = () => (D.order || []).flatMap(k => ((D.issues[k] || {}).asking || []).slice(0, 1)
  .map(a => ({ name: D.issues[k].name, issue: a.event_id != null ? { event_id: a.event_id } : { alert_id: a.alert_id } })));
const tiedTo = k => {
  if (k.alert_id == null && k.event_id == null) return '';
  const o = openIssues().find(x => (x.issue.event_id != null ? x.issue.event_id === k.event_id : x.issue.alert_id === k.alert_id));
  return o ? o.name : 'an issue';
};

/* the keys: six tools and Undo, each with its name and its letter beside the icon, the pressed one filled. Where the
   screen is narrow the names fold away and the letter goes back to the corner (doors.html) */
const UNDOKEY = typeof navigator !== 'undefined' && /Mac|iPhone|iPad/.test(navigator.platform || '') ? '⌘Z' : 'Ctrl+Z';   // the letter this machine's keyboard has
const keysHTML = () => KEYS.map(([k, l]) => `<button type="button" class="${k === 'marker' ? 'gap' : ''}" data-k="${k}" aria-label="${KEYNAME[k]}" aria-pressed="${PM.tool === k}" title="${KEYNAME[k]} · ${l}"`
  + (k === 'image' ? ' data-learn="place-image" data-reads="/captures" data-stage="observe" data-pack="core"' : '') + '>'
  + `<svg viewBox="0 0 20 20" aria-hidden="true">${KEYICON[k]}</svg><span class="kn">${KEYNAME[k].split(',')[0]}</span><kbd>${l}</kbd></button>`).join('')
  + `<button type="button" class="gap" data-k="undo" aria-label="Undo" title="Undo · ⌘Z or Ctrl+Z"><svg viewBox="0 0 20 20" aria-hidden="true">${KEYICON.undo}</svg><span class="kn">Undo</span><kbd>${UNDOKEY}</kbd></button>`;

/* the readout, folded to a chip (Tomas, 5 Nov 2026): the tool, the open map, the figure while it is drawn (the distance
   or the surface is the point of drawing) and a dot in the colour. A press on it opens the six colours and one line of
   what to do; a second press or Esc folds them. It opens by itself while a drawing of this house's is in hand, since
   the colours recolour it, and folds again when that drawing is let go, unless somebody opened it by hand. The figure
   follows the pointer, so it is hidden from a screen reader; the live region is #dsaid alone, written only when a
   drawing is kept (§10: the finished figure, not every mouse move). */
function figureNow() {
  const d = PM.draw, k = markById(d.sel), T = PM.tool;
  if (T === 'from') return { v: PM.measured ? fmtM(PM.measured.total_m) : '', hint: 'Press any point and the node measures it from its own point.' };
  if (T === 'pull') return { v: '', hint: PULL_HINT };
  if ((DRAWS.includes(T) || T === 'image') && !openMap()) return { v: '', hint: 'Make a map first with New map, at the top of the left column.' };
  if (k && d.corner != null) return { v: esc(k.label || k.kind), hint: 'Press the corner’s new place, or move it with the arrows.' };
  if (DRAWS.includes(T) && (!k || (d.state && d.state.pts.length))) {
    const f = figure(d.state || drawState(T), d.hover);
    /* the unit, then the rest of it apart: a narrow chip keeps "3120 m²" and the open panel says the rest */
    const [u, ...more] = f.unit.split(' · ');
    return { v: f.value ? `${esc(f.value)}<small>${esc(u)}</small>${more.length ? `<small class="more"> · ${esc(more.join(' · '))}</small>` : ''}` : '', hint: f.hint };
  }
  if (T === 'image' && !k) return { v: 'from Data › Images<small>or a new photo</small>', hint: HINT_IMG };
  /* the keyboard's point: the arrows move it, the full stop steps to the next (no mouse needed, §10) */
  const n = k && T === 'select' && mine(mapById(k.map_id)) ? ptsOf(k).length : 0;
  const keys = n > 1 ? ` Arrows move point ${d.kc % n + 1} of ${n}. Press . for the next point.` : n ? ' Arrows move it.' : '';
  return { v: k ? `${esc(k.label || k.kind)}<small>${esc(k.kind)} · ${esc(measureOf(k))}</small>` : '', hint: T === 'image' ? HINT_IMG : HINT_SEL + keys };
}
function readout() {
  const el = $('#dread'); if (!el || !PM.map || !DOORS_TOKEN()) return;
  const d = PM.draw, m = openMap(), k = markById(d.sel), f = figureNow(), cur = k ? k.colour : d.colour;
  if (d.auto && d.sel == null) { d.open = false; d.auto = false; }   // opened for a drawing that is no longer in hand
  const had = el.contains && el.contains(document.activeElement) && document.activeElement.classList && document.activeElement.classList.contains('dchip');
  el.innerHTML = `<button type="button" class="dchip" aria-expanded="${!!d.open}" aria-controls="dfull" title="${d.open ? 'Fold the colours' : 'The colours, and what to do'} · Esc folds">`
    + (PM.palette ? `<i class="dot" aria-hidden="true" style="background:${esc(PM.palette[cur])}"></i>` : '')
    + `<span class="t">${TOOLWORD[PM.tool] || ''}</span><span class="m">${m ? esc(m.name) : 'no map yet'}</span><span class="v" aria-hidden="true">${f.v}</span></button>`
    + `<div id="dfull" class="dfull"${d.open ? '' : ' hidden'}><div class="vf" aria-hidden="true">${f.v}</div>`
    + (PM.palette ? `<div class="dsw" role="group" aria-label="Colour">${[1, 2, 3, 4, 5, 6].map(n => `<button type="button" data-c="${n}" aria-label="Colour ${n}" aria-pressed="${n === cur}">`
      + `<i style="background:${esc(PM.palette[n])}"></i></button>`).join('')}<em>colour</em></div>` : '')
    + `<div class="hint">${esc(f.hint)}</div></div>${d.err ? `<p class="err">${esc(d.err)}</p>` : ''}`;
  const chip = el.querySelector && el.querySelector('.dchip');
  if (chip) { chip.onclick = () => { d.open = !d.open; d.auto = false; readout(); }; if (had) chip.focus(); }
  const live = $('#dsaid'); if (d.said && live) { live.textContent = d.said; d.said = ''; }
  el.querySelectorAll('[data-c]').forEach(b => b.onclick = () => {
    const n = +b.dataset.c, s = markById(PM.draw.sel);
    if (s && mine(mapById(s.map_id))) patch(s.id, { colour: n }); else { PM.draw.colour = n; readout(); redraw(); }
  });
}
/* only the figure and the hint, as the pointer moves */
function figureOnly() {
  const el = $('#dread'), f = figureNow(), h = el && el.querySelector && el.querySelector('.hint');
  ['.v', '.vf'].forEach(q => { const v = el && el.querySelector && el.querySelector(q); if (v && v.innerHTML !== f.v) v.innerHTML = f.v; });
  if (h && h.textContent !== f.hint) h.textContent = f.hint;
}

/* the form under the readout, for the drawing in hand: its label and note (saved as each changes), an image, Delete,
   and the issue it answers, which needs the person's own words (§8: tying writes the issue's acted step) */
function drawForm() {
  const el = $('#dform'); if (!el) return;
  const d = PM.draw, k = markById(d.sel), m = k && mapById(k.map_id);
  if (d.pick && markById(d.pick.id)) {
    const C = d.pick.caps;
    el.innerHTML = `<p>An image for ${esc(markById(d.pick.id).label || 'this drawing')}</p><div class="acts"><button type="button" data-a="newimg">A new photo</button><button type="button" data-a="back">Back</button></div>`
      + (C == null ? '<p>Asking the node for its images…</p>' : !C.length ? '<p>No image is on this node yet.</p>'
        : `<div class="caps">${C.map(c => `<button type="button" data-cap="${+c.id}">${esc(KIND[c.kind] || c.kind)} · ${esc(c.note || 'no note')} <small>${esc(when(c.ts))}</small></button>`).join('')}</div>`);
  } else if (!k && PM.tool === 'image') {
    /* the Image key with nothing in hand: a photo for no drawing goes where it was taken, the header's old button */
    el.innerHTML = `<p>${openMap() ? 'Press the map, or Enter for its centre, to pin an image there. Or add a photo on its own.' : 'Add a photo on its own.'} It lands where it was taken, else in the node’s cell.</p>`
      + '<div class="acts"><button type="button" data-a="newphoto">A new photo</button></div>';
  } else if (!k) { el.hidden = true; el.innerHTML = ''; return; }
  else if (!mine(m)) {
    el.innerHTML = `<p>${m && m.from_node ? `This map came from ${esc(m.from_node)}; it is read-only here.` : `This is ${esc(m && m.agent)}’s map.`}</p>`
      + (m && m.from_node && k.photo ? photoWords(k, m) : '');
  } else {
    const iss = openIssues(), tied = tiedTo(k);
    el.innerHTML = `<label>Label<input data-a="label" maxlength="80" value="${esc(k.label || '')}"></label>`
      + `<label>Note<textarea data-a="note" rows="2" maxlength="500">${esc(k.note || '')}</textarea></label>`
      + `<div class="acts"><button type="button" data-a="image">${k.capture_id ? 'Another image' : 'Add an image'}</button>`
      + (k.capture_id ? '<button type="button" data-a="noimage">Take the image off</button>' : '') + '<button type="button" data-a="delete">Delete it</button></div>'
      + (tied ? `<p>Tied to ${esc(tied)}. It counts as what you did.</p><div class="acts"><button type="button" data-a="untie">Untie it</button></div>`
        : iss.length ? `<label>The issue it answers<select data-a="issue"><option value="">none</option>${iss.map((x, i) => `<option value="${i}">${esc(x.name)}</option>`).join('')}</select></label>`
          + '<label>What you did<input data-a="words" maxlength="500" placeholder="in your own words"></label><div class="acts"><button type="button" data-a="tie">Tie it</button></div>'
        : '<p>Nothing is asked on Now, so there is no issue to tie it to.</p>');
  }
  el.hidden = false;
  const q = a => el.querySelector(`[data-a="${a}"]`), on = (a, f) => { const x = q(a); if (x) x.onclick = f; };
  ['label', 'note'].forEach(a => { const x = q(a); if (x) x.onchange = () => patch(k.id, { [a]: x.value }); });
  on('image', () => picker(k.id)); on('noimage', () => patch(k.id, { image: null })); on('delete', () => del(k.id));
  on('untie', () => patch(k.id, { issue: null }, false));
  on('tie', () => { const i = q('issue').value; if (i === '') { d.err = 'Choose the issue it answers first.'; readout(); return; }
    patch(k.id, { issue: openIssues()[+i].issue, words: q('words').value }, false); });
  on('back', () => { d.pick = null; drawForm(); });
  on('askphoto', () => askPhoto(k.id));
  const img = el.querySelector('img[data-photo]');
  if (img) doorsFetch(API + `place/marks/${k.id}/photo`).then(r => (r.ok ? r.blob() : null)).catch(() => null)
    .then(b => { if (b) { img.src = URL.createObjectURL(b); img.onload = () => URL.revokeObjectURL(img.src); } });
  on('newphoto', () => window.placeAddImage && window.placeAddImage());
  on('newimg', () => { const id = d.pick.id; window.placeAddImage && window.placeAddImage({ at: centreOf(markById(id)), done: c => { d.pick = null; patch(id, { image: c }); } }); });
  el.querySelectorAll('[data-cap]').forEach(b => b.onclick = () => { const id = d.pick.id; d.pick = null; patch(id, { image: +b.dataset.cap }); });
  if (d.focusLabel && q('label')) { d.focusLabel = false; q('label').focus(); }
}
/* §14: a child's photo comes up as words. Its file comes only if somebody here asks and somebody there presses Send */
function photoWords(k, m) {
  const ph = k.photo, a = ph.ask, st = a && a.state;
  const head = `<p>${esc(KIND[ph.kind] || ph.kind)} photo${ph.taken ? `, ${esc(ph.taken)}` : ''}${ph.note ? `: ${esc(ph.note)}` : ''}</p>`
    + Object.entries(ph.meta || {}).map(([x, v]) => `<p class="fine">${esc(x)}: ${esc(v)}</p>`).join('');
  if (st === 'sent') return head + `<img data-photo alt="The photo on ${esc(k.label || 'this drawing')}, sent by ${esc(m.from_node)}">`;
  if (st === 'asked') return head + `<p class="fine">Asked ${esc(dayOf(a.asked_at))}${a.asked_by ? ` by ${esc(a.asked_by)}` : ''}. It comes when somebody at ${esc(m.from_node)} presses Send.</p>`;
  return head + (st === 'no' ? `<p class="fine">${esc(m.from_node)} said no on ${esc(dayOf(a.answered_at))}.</p>` : st === 'gone' ? '<p class="fine">That photo is no longer shared.</p>' : '')
    + `<p class="fine">The picture itself stays at ${esc(m.from_node)} unless you ask and somebody there sends it.</p>`
    + '<div class="acts"><button type="button" data-a="askphoto">Ask for the photo</button></div>';
}
async function askPhoto(id) {
  const k = markById(id); if (!k) return;
  const r = await send('POST', `place/marks/${id}/ask`, { actor: actor() });
  if (!r.ok) { PM.draw.err = refused(r); after(); return; }
  const m = mapById(k.map_id);
  k.photo.ask = r.ask; PM.draw.said = `Asked. ${m ? m.from_node : 'That node'} hears it within the hour.`; after();
}
function picker(id) {
  const d = PM.draw; d.pick = { id, caps: null }; drawForm();
  ask('captures?limit=200').catch(() => []).then(c => { if (d.pick && d.pick.id === id) { d.pick.caps = c || []; drawForm(); } });
}
/* after a change, everything that shows it; the form keeps what somebody is typing in it */
function after() {
  const f = $('#dform');
  readout(); if (!(f && f.contains && f.contains(document.activeElement))) drawForm(); redraw(); panel();
}

/* ---- the node's side: keep, change, delete, each one undoable */
async function finish() {
  const d = PM.draw, s = d.state, m = openMap();
  if (!s || !canFinish(s) || !m) return null;
  d.state = null; d.hover = null;
  const r = await send('POST', `place/maps/${m.id}/marks`, { ...toFeature(s, { colour: d.colour }), actor: actor() });
  if (!r.ok) { d.err = refused(r); after(); return null; }
  (MARKS[m.id] ||= []).push(r.mark); m.marks += 1; remember(m.id);
  d.sel = r.mark.id; d.err = r.warn || ''; d.focusLabel = s.kind === 'note';
  d.said = `Kept in ${m.name}. ${r.mark.kind}${measureOf(r.mark) === '—' ? '' : `, ${measureOf(r.mark)}`}.`;
  UNDO.push(() => del(r.mark.id, false));
  after();
  return r.mark.id;
}
async function patch(id, body, undoable = true) {
  const k = markById(id); if (!k) return null;
  const was = { geometry: k.geometry, label: k.label, note: k.note, colour: k.colour, image: k.capture_id };
  const r = await send('PATCH', `place/marks/${id}`, { ...body, actor: actor() });
  PM.draw.preview = null;
  if (!r.ok) { PM.draw.err = refused(r); after(); return r; }
  const L = MARKS[k.map_id], i = L.findIndex(x => x.id === id); if (i >= 0) L[i] = r.mark;
  if (undoable) { const back = Object.fromEntries(Object.keys(body).map(x => [x, was[x]])); UNDO.push(() => patch(id, back, false)); }
  PM.draw.err = r.warn || ''; after(); return r;
}
async function del(id, undoable = true) {
  const k = markById(id), d = PM.draw; if (!k) return;
  const r = await send('DELETE', `place/marks/${id}?actor=${encodeURIComponent(actor())}`);
  if (!r.ok) { d.err = refused(r); after(); return; }
  MARKS[k.map_id] = MARKS[k.map_id].filter(x => x.id !== id); const m = mapById(k.map_id); if (m) m.marks -= 1;
  if (d.sel === id) d.sel = null;
  /* undone, it is drawn again: a new drawing with the same shape and words */
  if (undoable) UNDO.push(async () => {
    const b = await send('POST', `place/maps/${k.map_id}/marks`, { type: 'Feature', geometry: k.geometry, actor: actor(),
      properties: { kind: k.kind, label: k.label, note: k.note, colour: k.colour, image: k.capture_id } });
    if (b.ok && MARKS[k.map_id]) { MARKS[k.map_id].push(b.mark); if (m) m.marks += 1; d.sel = b.mark.id; } else if (!b.ok) d.err = refused(b);
    after();
  });
  after();
}
function undo() {
  const d = PM.draw;
  if (d.state && d.state.pts.length) { d.state = backPt(d.state); readout(); redraw(); return; }
  const u = UNDO.pop(); if (u) u();
}

/* ---- presses on the screen */
const pickOf = h => {
  const o = h && h.object, id = h && h.layer && h.layer.id;
  return !o ? null : (id === 'own' || id === 'public') ? { kind: 'station', s: o } : id === 'models' ? { kind: 'model', ss: o.ss, p: o.p }
    : id === 'labs' ? { kind: 'lab', s: o } : id === 'images' ? { kind: 'image', c: o } : id === 'species' ? { kind: 'image', c: o.c }
    : id === 'rivers' ? { kind: 'river', p: o.properties } : id === 'basin' ? { kind: 'basin', p: o.f.properties }
    : (id === 'grid' || id === 'grid-dot' || id === 'mine' || id === 'radio') ? { kind: 'cell', id: o.id } : id === 'seven' ? { kind: 'cell', id: o.cell } : null;
};
function select(id) {
  const d = PM.draw, k = markById(id); d.sel = id; d.corner = null; d.kc = 0; d.pick = null; PM.pick = null; popup(null);
  if (k && mine(mapById(k.map_id)) && !d.open) { d.open = true; d.auto = true; }   // the colours recolour the drawing in hand
  readout(); drawForm(); redraw();
}
function press(e) {
  const d = PM.draw, q = [e.lngLat.lng, e.lngLat.lat];
  const hit = PM.overlay.pickObject({ x: e.point.x, y: e.point.y, radius: 8 }), id = (hit && hit.layer && hit.layer.id) || '';
  const k = id.startsWith('draw-') && hit.object && hit.object.geometry ? hit.object : null;
  if (DRAWING()) { pressDraw(q, e.point); return; }
  if (id.startsWith('drone-pins') && hit.object) {
    if (!PM.on.drone) setLayer('drone', true);
    PM.map.easeTo({ center: hit.object.q, zoom: 16, duration: CLOCK.reduced() ? 0 : 900 }); return;
  }
  if (PM.tool === 'image') { if (k) { select(k.id); picker(k.id); } else imageAt(q); return; }
  if (id === 'draw-corner' && hit.object.k != null && hit.object.k === d.sel) { d.corner = hit.object.i; readout(); redraw(); return; }
  if (d.corner != null && d.sel != null) { moveCorner(q); return; }
  if (k) { select(k.id); return; }
  d.sel = null; d.corner = null; PM.pick = pickOf(hit); popup(PM.pick); facts(); readout(); drawForm(); redraw();
}
/* the image key on an empty place: a marker to carry the image, then the picker for it (Data's images, or a new photo).
   The picker opens only for the marker just kept: a refused one leaves nothing in hand to attach to */
function imageAt(q) {
  const d = PM.draw; if (!openMap()) { readout(); return; }
  d.sel = null; d.state = addPt(drawState('marker'), q); finish().then(id => { if (id != null) picker(id); });
}
function pressDraw(q, pt) {
  const d = PM.draw; if (!openMap()) { readout(); return; }
  const s = d.state || drawState(PM.tool);
  /* a press on the first corner closes an area: toFeature closes the ring, so that press is not a point of it */
  if (s.kind === 'area' && s.pts.length >= 3) { const f = PM.map.project(s.pts[0]); if (Math.hypot(f.x - pt.x, f.y - pt.y) <= 10) { finish(); return; } }
  d.state = addPt(s, q); d.via = 'click'; d.sel = null; d.corner = null;
  if (s.kind === 'marker' || s.kind === 'note') { finish(); return; }
  readout(); drawForm(); redraw();
}
/* Enter: with the keyboard the map's centre is the cursor. It adds a point there, and finishes once the shape can be
   one and the centre has not moved since the last point; after pressing with the mouse it finishes at once. */
function enter() {
  const d = PM.draw, s = d.state, c = PM.map.getCenter(), q = [c.lng, c.lat];
  if (PM.tool === 'image' && d.sel == null) { imageAt(q); return true; }   // the image key from the keyboard: at the map's centre
  if (!DRAWING()) return false;
  const last = s && s.pts[s.pts.length - 1];
  const a = last && PM.map.project(last), b = PM.map.project(q), still = !!a && Math.hypot(a.x - b.x, a.y - b.y) < 2;
  if (s && canFinish(s) && (d.via === 'click' || still)) { finish(); return true; }
  if (!openMap()) { readout(); return true; }
  d.state = addPt(s || drawState(PM.tool), q); d.via = 'key'; d.sel = null;
  if (PM.tool === 'marker' || PM.tool === 'note') finish(); else { readout(); redraw(); }   // one point is the whole of it
  return true;
}
/* a corner moves to a press, or by the arrows a few pixels at a time; the node keeps it half a second after the last */
function moveCorner(q) {
  const d = PM.draw, k = markById(d.sel); if (!k) return;
  const pts = ptsOf(k).map(p => [...p]); pts[d.corner] = q; d.corner = null;
  patch(k.id, { geometry: toFeature({ kind: k.kind, pts }).geometry });
}
function nudge(i, dx, dy) {
  const d = PM.draw, k = markById(d.sel); if (!k) return;
  const pts = ptsOf(k).map(p => [...p]), s = PM.map.project(pts[i]), ll = PM.map.unproject([s.x + dx, s.y + dy]);
  pts[i] = [ll.lng, ll.lat];
  d.preview = { id: k.id, geometry: toFeature({ kind: k.kind, pts }).geometry }; redraw();
  clearTimeout(d.nudged); d.nudged = setTimeout(() => d.preview && patch(k.id, { geometry: d.preview.geometry }), 500);
}
/* a drawing key hands the focus to the map, so the next Enter adds a point at its centre instead of pressing the
   button that had the focus again (node #1, 5 Nov: Tools, Esc, L, Enter reopened Tools) */
function toScreen(k) {
  const c = PM.map && PM.map.getCanvas();
  if (['marker', 'line', 'area', 'note'].includes(k) && c && c.focus) c.focus({ preventScroll: true });
}
/* the keys from the keyboard (V M L A N I, ⌘Z), Enter, Backspace, Esc, the arrows and the full stop; never while
   somebody types. With a drawing in hand the arrows move one of its points (a corner pressed, else the keyboard's point,
   the first to start) and `.` steps to the next: a drawing is edited without a mouse (§10). */
function onKey(e) {
  if (view() !== 'place' || !PM.map || !DOORS_TOKEN()) return;
  const t = e.target, d = PM.draw, k = e.key, within = sel => !!(t && t.closest && t.closest(sel));
  /* the download and Tools menus keep their keys: onKey listens in the capture phase, so a menu's own Esc cannot stop it */
  if (within('input, textarea, select, [contenteditable], dialog, .dlmenu')) return;
  /* the Tools button and its menu keep their keys while the menu is open; once it is shut, the button is any key on the page */
  if (within('.ptools') && $('#ptools').hidden === false) return;
  if ((e.metaKey || e.ctrlKey) && !e.shiftKey && (k === 'z' || k === 'Z')) { e.preventDefault(); undo(); return; }
  if (e.metaKey || e.ctrlKey || e.altKey) return;
  const key = (KEYS.find(([, l]) => l === k.toUpperCase()) || [])[0];
  if (key && k.length === 1) { e.preventDefault(); PM.setTool(key); toScreen(key); return; }
  if (k === 'Escape') {
    if (MEASURING() || PM.tool === 'pull') { PM.setTool('select'); return; }
    /* from inside the readout, Esc folds it and keeps the focus on its chip; elsewhere it folds last */
    if (d.open && within('.dpanel')) { d.open = false; d.auto = false; readout(); const c = $('#dread').querySelector('.dchip'); if (c) c.focus(); return; }
    if (d.state) d.state = null; else if (d.corner != null) d.corner = null; else if (d.pick) d.pick = null; else if (d.sel != null) d.sel = null;
    else if (d.open) { d.open = false; d.auto = false; } else return;
    readout(); drawForm(); redraw(); return;
  }
  if (k === 'Backspace' && d.state && d.state.pts.length) { e.preventDefault(); d.state = backPt(d.state); readout(); redraw(); return; }
  if (k === 'Enter' && !within('button, a')) { if (enter()) e.preventDefault(); return; }
  const held = PM.tool === 'select' && markById(d.sel), editable = held && mine(mapById(held.map_id));
  if (k === '.' && editable) { e.preventDefault(); d.corner = null; d.kc = (d.kc + 1) % ptsOf(held).length; readout(); redraw(); return; }
  const arrow = { ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowUp: [0, -1], ArrowDown: [0, 1] }[k];
  if (!arrow) return;
  if (editable) { e.preventDefault(); e.stopPropagation(); const n = e.shiftKey ? 10 : 2; nudge(d.corner != null ? d.corner : d.kc % ptsOf(held).length, arrow[0] * n, arrow[1] * n); return; }
  /* on a key of the screen the arrows pan, and anywhere while a shape is being drawn, since Enter adds at the map's
     centre (node #1, 5 Nov: after the L key the arrows scrolled the page and every point landed on the first);
     on the map's canvas MapLibre pans by itself */
  if (within('.maplibregl-canvas-container')) return;
  if (d.state || within('.mapc')) { e.preventDefault(); PM.map.panBy([arrow[0] * 80, arrow[1] * 80]); }
}

/* ---- the drawings, as deck.gl layers: an area filled at .28 with a 2 px edge, a line dashed with each leg's metres,
   pins, notes as labels; corners as small squares while drawing or in hand. The one in hand is ringed in the cells'
   blue, the screen's focus colour. */
function drawLayers(p, Dk, px, dashed, A) {
  /* deck.gl keeps a layer's state by id, so a layer that can be one of two kinds has an id for each */
  const d = PM.draw, ms = shownMarks(), sel = markById(d.sel), C = k => colourOf(k.colour), out = [];
  const of = kind => ms.filter(k => k.kind === kind), area = of('area'), line = of('line'), pin = of('marker');
  const mono = 'JetBrains Mono, monospace', sans = 'Figtree, sans-serif', white = [255, 255, 255, 255];
  if (sel && !PM.mapOff.has(sel.map_id)) {
    const g = geomOf(sel), ring = g.type === 'Polygon' ? g.coordinates[0] : g.type === 'LineString' ? g.coordinates : null;
    out.push(ring ? new Dk.PathLayer({ id: 'draw-focus-path', data: [{ ring }], getPath: x => x.ring, ...px, getColor: A(p.cells, 1), getWidth: 6 })
      : new Dk.ScatterplotLayer({ id: 'draw-focus-pin', data: [{ q: g.coordinates }], getPosition: x => x.q, ...px, stroked: true, filled: false, getRadius: 12, getLineColor: A(p.cells, 1), getLineWidth: 2 }));
  }
  out.push(new Dk.PolygonLayer({ id: 'draw-area', data: area, getPolygon: k => geomOf(k).coordinates[0], ...px, pickable: true, filled: true, stroked: true,
    getFillColor: k => A(C(k), .28), getLineColor: k => A(C(k), 1), getLineWidth: 2 }));
  out.push(new Dk.PathLayer({ id: 'draw-line', data: line, getPath: k => geomOf(k).coordinates, ...px, pickable: true, getColor: k => A(C(k), 1), getWidth: 2,
    extensions: [dashed], getDashArray: [6, 4] }));
  const legs = line.flatMap(k => { const c = geomOf(k).coordinates;
    return c.slice(1).map((q, i) => ({ q: [(c[i][0] + q[0]) / 2, (c[i][1] + q[1]) / 2], t: fmtLen(lengthM([c[i], q])), c: C(k) })); });
  out.push(new Dk.TextLayer({ characterSet: 'auto', id: 'draw-legs', data: legs, getPosition: x => x.q, getText: x => x.t, getSize: 10, fontFamily: mono,
    getColor: x => A(x.c, 1), getPixelOffset: [0, -9], background: true, getBackgroundColor: [0, 0, 0, 150], backgroundPadding: [3, 1] }));
  out.push(new Dk.ScatterplotLayer({ id: 'draw-pin', data: pin, getPosition: k => geomOf(k).coordinates, ...px, pickable: true, stroked: true, filled: true,
    getRadius: 6, getFillColor: k => A(C(k), 1), getLineColor: [0, 0, 0, 255], getLineWidth: 1.2 }));
  out.push(new Dk.TextLayer({ characterSet: 'auto', id: 'draw-note', data: of('note'), getPosition: k => geomOf(k).coordinates, getText: k => k.label || 'note',
    pickable: true, getSize: 11, fontFamily: sans, getColor: white, background: true, getBackgroundColor: [20, 20, 20, 235], getBorderColor: k => A(C(k), 1),
    getBorderWidth: 1, backgroundPadding: [6, 4] }));
  const lab = [...area, ...pin, ...line].filter(k => k.label || tiedTo(k)).map(k => ({ k, q: k.kind === 'marker' ? geomOf(k).coordinates : centreOf(k),
    t: [k.label, k.kind === 'area' && k.area_m2 != null ? measureOf(k) : '', tiedTo(k) && `for ${tiedTo(k)}`].filter(Boolean).join('\n') }));
  out.push(new Dk.TextLayer({ characterSet: 'auto', id: 'draw-label', data: lab, getPosition: x => x.q, getText: x => x.t, getSize: 11, fontFamily: sans,
    getColor: white, getPixelOffset: x => (x.k.kind === 'marker' ? [0, -18] : [0, 0]), background: true, getBackgroundColor: [0, 0, 0, 150], backgroundPadding: [3, 1] }));
  /* the shape being drawn, with the pointer as its next point */
  const s = d.state, c = colourOf(d.colour);
  if (s && s.pts.length) {
    const path = d.hover ? [...s.pts, d.hover] : s.pts;
    out.push(s.kind === 'area' && path.length >= 3
      ? new Dk.PolygonLayer({ id: 'draw-now-area', data: [{ path }], getPolygon: x => x.path, ...px, filled: true, stroked: true, getFillColor: A(c, .28), getLineColor: A(c, 1), getLineWidth: 2 })
      : new Dk.PathLayer({ id: 'draw-now-path', data: [{ path }], getPath: x => x.path, ...px, getColor: A(c, 1), getWidth: 2, extensions: [dashed], getDashArray: [6, 4] }));
  }
  const cs = s ? s.pts.map((q, i) => ({ q, i, c })) : sel && !PM.mapOff.has(sel.map_id) ? ptsOf(sel).map((q, i) => ({ q, i, k: sel.id, c: p.cells, on: i === (d.corner != null ? d.corner : d.kc % ptsOf(sel).length) })) : [];
  out.push(new Dk.TextLayer({ characterSet: 'auto', id: 'draw-corner', data: cs, getPosition: x => x.q, getText: () => '■', getSize: 14, fontFamily: mono,
    getColor: x => A(x.c, 1), pickable: true }));
  out.push(new Dk.TextLayer({ characterSet: 'auto', id: 'draw-corner-in', data: cs, getPosition: x => x.q, getText: () => '■', getSize: 7, fontFamily: mono,
    getColor: x => (x.on ? A(p.cells, 1) : [0, 0, 0, 255]) }));
  return out;
}

/* ---- your maps, the top of the left column: a row per map (a square dot, a layer's is round) that shows or hides it,
   its name opening what can be done to it, then New map. The open map is where new drawings go: the one last drawn in,
   remembered per browser. Deleting and sharing each ask once, in the row, and a second press does it. */
function yourMaps() {
  const M = PM.maps, d = PM.draw, tok = !!DOORS_TOKEN();
  const head = `<h2><span>your maps</span>${tok && M ? `<b>${M.length || 'none yet'}</b>` : ''}</h2>`, wrap = h => `<section id="ymaps" aria-label="Your maps">${head}${h}</section>`;
  if (!tok) return wrap('<p class="fine">Your maps are kept on this node. Unlock this screen in <a href="#setup/screen">Set up</a> to draw.</p>');
  if (!M) return wrap(PM.mapsErr ? '<p class="fine">The node did not give this screen its maps just now. Try again in a minute.</p>' : '');
  const row = m => { const on = !PM.mapOff.has(m.id);
    return `<div class="ly map${on ? '' : ' off'}${m.id === d.map ? ' open' : ''}" data-m="${m.id}">`
      + `<button type="button" class="ymd" data-f="d${m.id}" aria-pressed="${on}" aria-label="${esc(m.name)}, on the screen"><i aria-hidden="true"></i></button>`
      + `<button type="button" class="ymn" data-f="n${m.id}" aria-expanded="${d.edit === m.id}" title="${esc(m.name)}${m.id === d.map ? ' · new drawings go here' : ''}">`
      + `<span>${esc(m.name)}</span><small>${+m.marks} drawn</small></button></div>` + (d.edit === m.id ? editor(m) : ''); };
  return wrap(asksHere() + M.map(row).join('')
    + (d.naming ? `<div class="ynew"><input id="ynew" data-f="ynew" maxlength="80" aria-label="The new map’s name" placeholder="Garden plan"><button type="button" class="ybtn" data-a="keep">Keep</button></div>`
      : '<button type="button" class="ly new" data-f="new"><i aria-hidden="true"></i><span>New map</span></button>')
    + (d.mapErr ? `<p class="fine" role="status">${esc(d.mapErr)}</p>` : ''));
}
/* §14: the node upstream asks for a photo on a shared drawing. Only somebody here sends it, and only once */
function asksHere() {
  return (PM.asks || []).map(a => `<div class="yed yask" data-k="${+a.id}"><p>${esc(a.node)} asks for the photo on `
    + a.drawings.map(x => `${esc(x.label || x.kind)} (${esc(x.map)})`).join(', ') + `.${a.asked_by ? ` ${esc(a.asked_by)}, ${esc(dayOf(a.asked_at))}.` : ''}</p>`
    + `<p class="fine">Send gives them the picture once, No keeps it here, and both go in the ledger.</p>`
    + '<div class="yacts"><button type="button" class="ybtn" data-a="send">Send</button><button type="button" class="ybtn" data-a="no">No</button></div></div>').join('');
}
async function answerAsk(id, answer) {
  const d = PM.draw, r = await send('POST', `place/photos/asks/${id}`, { answer, actor: actor() });
  if (r.ok || r.status === 409) PM.asks = (PM.asks || []).filter(a => a.id !== id);
  d.mapErr = !r.ok ? refused(r) : answer === 'send' ? 'Sent. It goes up within the minute.' : 'Kept here. The node upstream hears no.';
  panel();
}
function editor(m) {
  const d = PM.draw, asked = kind => d.asked && d.asked.id === m.id && d.asked.kind === kind, f = a => `data-a="${a}" data-f="${a}${m.id}"`;
  if (!mine(m)) return `<div class="yed"><p class="fine">${m.from_node ? `This map came from ${esc(m.from_node)}; it is read-only here.` : `This is ${esc(m.agent)}’s map.`}</p></div>`;
  return `<div class="yed" data-m="${m.id}">` + (m.id === d.map ? '' : `<button type="button" class="ybtn" ${f('open')}>Draw in this map</button>`)
    + `<label>Name<input ${f('name')} maxlength="80" value="${esc(m.name)}"></label><label>Whose map<input ${f('owner')} maxlength="80" value="${esc(m.owner || '')}"></label>`
    + `<button type="button" class="ybtn" ${f('share')}>${m.shared && !m.held ? 'Stop sharing' : 'Share'}</button>`
    + (asked('share') || m.share_error ? `<p class="fine" role="status">${esc(asked('share') ? d.asked.text : m.share_error)}</p>` : '')
    + `<button type="button" class="ybtn" ${f('delete')}>Delete</button>`
    + (asked('delete') ? `<p class="fine" role="status">Delete ${esc(m.name)} and its ${+m.marks} drawing${m.marks === 1 ? '' : 's'}? Press Delete again.</p>` : '') + `</div>`;
}
function wireMaps() {
  const box = document.getElementById && document.getElementById('ymaps'), d = PM.draw; if (!box) return;
  const idOf = b => +b.closest('[data-m]').dataset.m;
  box.querySelectorAll('.ymd').forEach(b => b.onclick = () => { const id = idOf(b); if (!PM.mapOff.delete(id)) PM.mapOff.add(id);
    if (!MARKS[id]) placeMaps(); else { panel(); redraw(); } });
  box.querySelectorAll('.ymn').forEach(b => b.onclick = () => { const id = idOf(b); d.edit = d.edit === id ? null : id; d.asked = null; panel(); });
  const nw = box.querySelector('.ly.new'); if (nw) nw.onclick = () => { d.naming = true; panel(); const i = document.getElementById('ynew'); if (i) i.focus(); };
  const ni = document.getElementById('ynew');
  if (ni) { ni.onkeydown = e => { if (e.key === 'Enter') newMap(ni.value); if (e.key === 'Escape') { d.naming = false; panel(); } };
    box.querySelector('[data-a="keep"]').onclick = () => newMap(ni.value); }
  box.querySelectorAll('.yask').forEach(el => el.querySelectorAll('[data-a]').forEach(b => b.onclick = () => answerAsk(+el.dataset.k, b.dataset.a)));
  box.querySelectorAll('.yed[data-m]').forEach(ed => {
    const m = mapById(+ed.dataset.m), x = a => ed.querySelector(`[data-a="${a}"]`); if (!m) return;
    if (x('open')) x('open').onclick = () => { remember(m.id); after(); };
    x('name').onchange = async () => { const r = await mapPatch(m, { name: x('name').value }); if (!r.ok) d.mapErr = refused(r); after(); };
    x('owner').onchange = async () => { const r = await mapPatch(m, { owner: x('owner').value.trim() || null }); if (!r.ok) d.mapErr = refused(r); after(); };
    x('share').onclick = () => share(m); x('delete').onclick = () => mapDelete(m);
  });
}
async function mapPatch(m, body) {
  const r = await send('PATCH', `place/maps/${m.id}`, { ...body, actor: actor() });
  if (r.ok) { Object.assign(m, r.map); PM.draw.asked = null; PM.draw.mapErr = ''; }
  return r;
}
/* the first press brings back the node's own warning (409, code share_warning), shown in the row; the second sends
   it, exactly. Any other refusal is shown too, and arms nothing: the next press asks for the warning again. */
async function share(m) {
  const d = PM.draw, again = d.asked && d.asked.id === m.id && d.asked.kind === 'share' && d.asked.armed;
  const r = await mapPatch(m, m.shared && !m.held && !again ? { shared: false } : again ? { shared: true, confirm: 'exact' } : { shared: true });
  if (!r.ok) d.asked = { id: m.id, kind: 'share', text: refused(r), armed: !!r.detail && r.detail.code === 'share_warning' };
  panel();
}
async function mapDelete(m) {
  const d = PM.draw;
  if (!(d.asked && d.asked.id === m.id && d.asked.kind === 'delete')) { d.asked = { id: m.id, kind: 'delete' }; panel(); return; }
  const r = await send('DELETE', `place/maps/${m.id}?confirm=${encodeURIComponent(m.name)}&actor=${encodeURIComponent(actor())}`);
  d.asked = null;
  if (!r.ok) { d.mapErr = refused(r); panel(); return; }
  PM.maps = PM.maps.filter(x => x.id !== m.id); delete MARKS[m.id]; d.edit = null;
  if (d.sel != null && !markById(d.sel)) d.sel = null;
  if (d.map === m.id) d.map = PM.maps.length ? PM.maps[0].id : null;
  after();
}
async function newMap(name) {
  const d = PM.draw, r = await send('POST', 'place/maps', { name, actor: actor() });
  if (!r.ok) { d.mapErr = refused(r); panel(); return; }
  d.naming = false; d.mapErr = ''; PM.maps = [r.map, ...(PM.maps || [])]; MARKS[r.map.id] = []; remember(r.map.id);
  after();
}
/* the maps and the drawings of the ones on the screen, asked again: the left column, the lower band and the screen */
async function placeMaps() {
  const d = PM.draw;
  if (!DOORS_TOKEN()) { PM.maps = null; panel(); return; }
  try { const g = await ask('place/maps'); PM.maps = g.maps || []; PM.palette = g.palette || null; PM.mapsErr = null; } catch (e) { PM.maps = null; PM.mapsErr = e.message; }
  PM.asks = await ask('place/photos/asks').then(r => r.asks || []).catch(() => []);
  const M = PM.maps || [];
  let keep = null; try { keep = +localStorage.getItem(MAPKEY) || null; } catch (e) { /* no storage here */ }
  if (!mapById(d.map)) d.map = mapById(keep) ? keep : M.length ? M[0].id : null;
  await Promise.all(M.filter(m => !PM.mapOff.has(m.id) || m.id === d.map)
    .map(m => ask(`place/maps/${m.id}/marks`).then(r => { MARKS[m.id] = r.marks || []; }).catch(() => {})));
  Object.keys(MARKS).forEach(id => { if (!mapById(+id)) delete MARKS[id]; });
  panel(); readout(); drawForm(); redraw();
}
window.placeMaps = placeMaps;

/* ---------------------------------------------------------------- the inspector: one line under the map (option A)
   In view, the node's own cell as the lede says it; a mark, a margin row or a cell pressed says its facts in the same
   line, with the longer card on the map (popup()). Every figure is the node's answer: GET /geo/cell, /geo/measure. */
let FSEQ = 0;
async function facts() {
  const seq = ++FSEQ, o = PM.pick, r = PM.res, el = $('#facts');
  const row = (t, v) => `<span class="fi"><small>${esc(t)}</small><b>${v}</b></span>`, hint = h => `<span class="hint">${h}</span>`;
  const put = h => {
    if (seq !== FSEQ) return;
    el.innerHTML = h;
    const b = el.querySelector && el.querySelector('[data-claim]'); if (b) b.onclick = () => claimCell(b.dataset.claim, b.dataset.verb);
    if (el.querySelectorAll) el.querySelectorAll('[data-pull]').forEach(x => { x.onclick = () => pullDo(x.dataset.pull); });
  };
  /* one of the seven: its state in words, and Claim or Release on a neighbour (the node's routes; home is always its own) */
  const sevenTail = id => {
    const s = PM.cells && PM.cells.cells.find(x => x.cell === id); if (!s) return '';
    const verb = s.state === 'open' ? 'claim' : s.state === 'home' ? null : 'release';
    return row('of the seven', s.state) + `<span>${SEVEN_SAID[s.state]}</span>`
      + (verb ? `<button type="button" class="ptoolsb" data-claim="${esc(s.cell)}" data-verb="${verb}">${verb === 'claim' ? 'Claim this cell' : 'Release it'}</button>` : '')
      + (PM.said && PM.said.id === id ? `<span class="gap">${esc(PM.said.text)}</span>` : '');
  };
  try {
    const m = PM.measured && PM.measured.points === PM.measure.length && PM.measure.length > 1 ? PM.measured : null;
    if (PM.tool === 'from') {
      put(`<span class="k">From the house</span><b>${m ? fmtM(m.total_m) : '—'}</b>` + hint('tap any point: the node measures it from its own point (GET /geo/measure) · press the tool again, or Esc, when you have it'));
    } else if (PM.tool === 'pull' && PM.pull) {
      put(pullHTML());
    } else if (o && o.kind === 'station') {
      const s = o.s, v = lastRaw(s.sensor_id, 'pm25');
      const head = `<span class="k">${s.local ? 'This house’s station' : 'Public station'}</span><b class="said">${esc(plain(s.name || s.sensor_id))}</b>`;
      const pm = row('PM2.5, last hour', v == null ? '<span class="gap">not heard</span>' : `${fmt(v, 1)} µg/m³ ${prov(s.local ? 'live' : 'partial')}`);
      const tail = hint(s.local ? 'in this node’s custody: it counts toward the cell' : 'display only: never drives an alert here');
      put(head + pm + tail);
      if (!DOORS_TOKEN()) return;
      const [d, c] = await Promise.all([fromNode(s.lon, s.lat), cellAt(s.lon, s.lat, r)]);
      put(head + row('from this node', fmtM(d)) + pm + row('cell at res ' + r, c.id) + tail);
    } else if (o && o.kind === 'layer') {
      const l = BY[o.id]; put(`<span class="k">${esc(l.name)}</span><span>${about(l).long}</span>` + hint(`the ${esc(l.pack)} pack`));
    } else if (o && o.kind === 'model') {
      put(`<span class="k">Model points here · ${o.ss.length}</span>` + o.ss.map(x => `<span class="said">${esc(x.name)}</span>`).join('') + prov('model') + hint('a model is partial, whatever its quality'));
    } else if (o && o.kind === 'cell') {
      put(`<span class="k">Cell</span><b>${esc(o.id)}</b>` + sevenTail(o.id));
      const c = await cellFacts(o.id);
      put(`<span class="k">Cell · res ${c.res}</span><b>${c.id}</b>` + row('area', area(c.area_m2)) + row('edge', fmtM(c.edge_m))
        + (c.parent ? row('parent', c.parent) : '') + row('this node’s cell', c.is_node ? 'yes' : c.cells_from_node == null ? 'no' : `no · ${c.cells_from_node} cells away`)
        + sevenTail(o.id) + (c.may_leave ? hint('coarse enough to leave the machine') : ''));
    } else if (o && o.kind === 'image') {
      const c = o.c, head = `<span class="k">Image · ${esc(KIND[c.kind] || c.kind)}</span><b class="said">${esc(c.note || 'no note')}</b>`
        + row('taken', esc(when(c.ts))) + row('by', `<span class="said">${esc(c.actor || '—')}</span>`) + row('cell, res 10', esc(c.cell))
        + row('in the seven cells', c.outside ? 'no · outside' : 'yes');
      put(head);
      put(head + row('from this node', fmtM(await fromNode(c.at[1], c.at[0]))) + hint('kept on this node, cleaned of EXIF and GPS'));
    } else if (o && o.kind === 'river') {
      const p = o.p;
      put(`<span class="k">River · order ${p.ord_stra}</span><b>${fmt(p.dis_av_cms, p.dis_av_cms < 1 ? 2 : 1)} m³/s on average</b>`
        + row('from this node', fmtM(p.dist_m)) + row('drains', `${Math.round(p.upland_skm).toLocaleString()} km²`)
        + row(p.endorheic ? 'to where it ends inland' : 'to the sea', p.dist_dn_km < 1 ? 'here' : `${Math.round(p.dist_dn_km)} km`)
        + prov('model') + hint('HydroSHEDS, about 500 m: a model’s long-term average, not a gauge'));
    } else if (o && o.kind === 'basin') {
      const p = o.p;
      put(`<span class="k">Basin · level 12${p.here ? ' · the node’s own' : ''}</span><b>${Math.round(p.sub_area).toLocaleString()} km² of its own</b>`
        + row('with all upstream', `${Math.round(p.up_area).toLocaleString()} km²`) + row(p.coast ? 'drains' : 'drains to', p.coast ? 'straight to the sea' : `basin ${p.next_down}`)
        + prov('model') + hint('HydroBASINS, about 500 m'));
    } else if (o && o.kind === 'lab') {
      const head = `<span class="k">Place to make</span><b class="said">${esc(o.s.name)}</b>`;
      put(head + hint('from fablabs.io, a directory: shown, never counted'));
      put(head + row('from this node', fmtM(await fromNode(o.s.lon, o.s.lat))) + hint('from fablabs.io, a directory: shown, never counted'));
    } else {
      /* the node's own cell, as the lede says it: its edge and its own area, not the resolution's average */
      const h = D.health, own = (D.geometry.ladder.find(l => l.res === h.cell.res) || {}).own_area_m2;
      put(`<span class="k">In view</span><b>${esc(h.cell.id)}</b><span>res ${r} in view · cell res ${h.cell.res}</span>`
        + `<span>${h.cell.edge_m} m edge</span>${own ? `<span>${area(own)}</span>` : ''}`
        + `<span>${ON()} of ${OF()} layers on</span>`
        + (PM.cells ? `<span>${PM.cells.held} of ${PM.cells.of} cells held</span>` : DOORS_TOKEN() && PM.cellsErr ? `<span class="gap">${esc(PM.cellsErr)}</span>` : '')
        + (m ? row(PM.from ? 'from the house' : 'measured', fmtM(m.total_m)) : '') + windWords()
        + (PM.offline ? `<span class="gap">the grid is locked on this screen</span>` : '') + hint('tap a mark, or a row below, to inspect it'));
    }
  } catch (e) { offline(e.message); put(`<span class="k">Inspect</span>` + hint(`the node did not answer: ${esc(e.message)}`)); }
}

const SEVEN_SAID = { home: 'the cell the node stands in, always its own', held: 'claimed, and one of its own readings landed here in the last 24 h',
  claimed: 'claimed, with none of its own readings here in the last 24 h', open: 'touches the node’s cell, not claimed' };
/* GET /place/cells: the seven and how many are held. A refusal is kept to say, never a 0 of 7. */
const loadCells = () => ask('place/cells').then(x => { PM.cells = x; PM.cellsErr = null; }, e => { PM.cells = null; PM.cellsErr = e.message; });
async function claimCell(id, verb) {
  const r = await send(verb === 'claim' ? 'POST' : 'DELETE', `place/cells/${id}/claim?actor=${encodeURIComponent(actor())}`);
  PM.said = r.ok ? null : { id, text: refused(r) };
  if (r.ok) PM.cells = r;
  redraw(); facts();
}

/* ---------------------------------------------------------------- the area pull (POST /area, Tools › Pull)
   Tap cells at the scale in view (the node names each: GET /geo/cell), or choose one of the household's drawn areas, then
   Pull. The node answers three blocks: its own sensors (only in home and held cells), peers, and each open source with
   its words. Every figure is the node's; one it did not send is a dash, and an empty block says why in its sentence. */
const PULL_HINT = 'Tap cells on the map, or choose one of your drawn areas, then Pull.';
const pullAreas = () => shownMarks().filter(k => k.kind === 'area' && mine(mapById(k.map_id)));
async function pullPress(e) {
  const P = PM.pull, hit = PM.overlay.pickObject({ x: e.point.x, y: e.point.y, radius: 8 }), id = (hit && hit.layer && hit.layer.id) || '';
  const k = id.startsWith('draw-') && hit.object && hit.object.geometry ? hit.object : null;
  if (k && k.kind === 'area' && mine(mapById(k.map_id))) { pullDo('m' + k.id); return; }
  let c; try { c = await cellAt(e.lngLat.lng, e.lngLat.lat, PM.res); } catch (x) { P.err = x.message; facts(); return; }
  if (PM.pull !== P) return;
  const i = P.cells.findIndex(x => x.id === c.id);
  if (i >= 0) P.cells.splice(i, 1); else P.cells.push({ id: c.id, path: loop(c.ring) });
  P.mark = null; P.ans = null; P.err = ''; redraw(); facts();
}
async function pullDo(what) {
  const P = PM.pull; if (!P) return;
  if (what === 'clear') { P.cells = []; P.mark = null; P.ans = null; P.err = ''; }
  else if (what[0] === 'm') { P.mark = +what.slice(1); P.cells = []; P.ans = null; P.err = ''; }
  else if (what === 'go') {
    P.busy = true; P.err = ''; facts();
    const r = await send('POST', 'area', P.mark != null ? { mark_id: P.mark } : { cells: P.cells.map(x => x.id) });
    if (PM.pull !== P) return;
    P.busy = false; P.ans = r.ok ? r : null; P.err = r.ok ? '' : refused(r);
  }
  redraw(); facts();
}
const oldness = t => { const m = (Date.now() - Date.parse(t)) / 6e4; return isFinite(m) ? `${ago(Math.max(0, m))} old` : ''; };
const pullFigures = b => {
  const ms = Object.entries(b.metrics || {}), newest = ms.map(([, m]) => m.latest_at).filter(Boolean).sort().pop();
  return { age: newest ? ` · ${oldness(newest)}` : '', rows: ms.map(([k, m]) => `<span class="fi"><small>${esc(k)}</small><b>${fmt(m.latest, 1)}</b> · 24 h mean ${fmt(m.mean_24h, 1)}</span>`).join('') };
};
function pullHTML() {
  const P = PM.pull, A = P.ans, areas = pullAreas(), some = P.cells.length || P.mark != null;
  const sel = P.mark != null ? esc((markById(P.mark) || {}).label || `drawn area ${P.mark}`) : P.cells.length ? `${P.cells.length} cell${P.cells.length > 1 ? 's' : ''}` : '—';
  const btn = (k, t, on) => `<button type="button" class="ptoolsb" data-pull="${k}"${on == null ? '' : ` aria-pressed="${on}"`}>${t}</button>`;
  let h = `<span class="k">Pull</span><b>${sel}</b>` + areas.map(k => btn('m' + k.id, `<span class="said">${esc(k.label || `area ${k.id}`)}</span>`, P.mark === k.id)).join('')
    + (some ? btn('go', P.busy ? 'Pulling…' : 'Pull') + btn('clear', 'Clear') : `<span class="hint">${PULL_HINT}</span>`)
    + (P.err ? `<span class="gap">${esc(P.err)}</span>` : '');
  if (!A) return h;
  const o = A.own, pe = A.peers, f = pullFigures(o), g = pullFigures(pe);
  h += `<div class="pb"><span class="k">This node’s own</span><span>${o.sensors} of its sensors in ${o.cells.length} of its cells${f.age}</span>${f.rows}`
    + (o.why ? `<span class="gap">${esc(o.why)}</span>` : '')
    + (o.unplaced ? `<span class="gap">${o.unplaced} of its own sensors have no place, so none of them is read here</span>` : '')
    + (o.children_unplaced ? `<span class="gap">${o.children_unplaced} sensors of the nodes below have no place yet</span>` : '') + '</div>';
  h += `<div class="pb"><span class="k">Neighbours</span><span>${pe.sensors} of their sensors placed here${g.age}</span>${g.rows}`
    + (pe.why ? `<span class="gap">${esc(pe.why)}</span>` : '')
    + (pe.unplaced ? `<span class="gap">${pe.unplaced} heard with only a distance, so not placed</span>` : '') + '</div>';
  h += (A.open || []).map(x => `<div class="pb"><span class="k">${esc(x.pack)}</span>`
    + (x.why ? `<span${x.off ? '' : ' class="gap"'}>${esc(x.why)}</span>` : x.error ? `<span class="gap">${esc(x.error)}</span>`
      : `<span>${esc(x.source)} · ${esc(x.licence)}${x.as_of ? ` · ${oldness(x.as_of)}` : ''}</span><span class="fi"><small>items</small><b>${(x.rows || []).length}</b></span>`
        + (x.note ? `<span class="hint">${esc(x.note)}</span>` : '')) + '</div>').join('')
    || '<div class="pb"><span class="k">Open sources</span><span class="gap">No pack on this node answers for an area.</span></div>';
  return h;
}

/* ---------------------------------------------------------------- the wind, moving */
/* The forecast pack's field (GET /ground/wind): Open-Meteo's 10 m wind at 8 × 8 points over ±30 km, hourly for a day,
   and the node's own point beside it. Particles drift through it, as Bali Air Dispatch draws its 64 points over the
   island. Between four of the node's points the page blends them (bilinear, by east and north components), the way a
   map resamples a raster: the values are the node's, the blend is the drawing. Outside the square nothing moves,
   because the field says nothing there. One clock, stopped off the door; under reduced motion, still arrows. */
const WIND = { cv: null, ctx: null, cells: null, cell: 18, parts: [], moving: false, on: false };
PM.windStep = 0;
const COMPASS = ['N', 'NNE', 'NE', 'ENE', 'E', 'ESE', 'SE', 'SSE', 'S', 'SSW', 'SW', 'WSW', 'W', 'WNW', 'NW', 'NNW'];
function nowIdx() {
  const F = PM.wind; if (!F) return 0;
  let best = 0; F.times.forEach((t, i) => { if (Math.abs(Date.parse(t) - Date.now()) < Math.abs(Date.parse(F.times[best]) - Date.now())) best = i; });
  return best;
}
const windHour = () => Math.min(nowIdx() + PM.windStep, PM.wind.times.length - 1);
function windWords() {
  const F = PM.wind; if (!F || !PM.on.wind) return '';
  const h = windHour(), s = F.at_node.speed_kmh[h], d = F.at_node.from_deg[h];
  if (s == null || d == null) return '';
  return `<span class="wind">wind ${Math.round(s)} km/h from ${COMPASS[Math.round(d / 22.5) % 16]} · ${hhmm(F.times[h])}${PM.windStep ? ` · +${PM.windStep} h` : ''}</span>`;
}
/* east and north components, km/h, of the wind going TO (from + 180) */
const uv = (s, from) => { const t = (from + 180) * Math.PI / 180; return [s * Math.sin(t), s * Math.cos(t)]; };
function sample(lng, lat, h) {
  const F = PM.wind, n = F.n, fy = (lat - F.lats[0]) / (F.lats[n - 1] - F.lats[0]) * (n - 1), fx = (lng - F.lons[0]) / (F.lons[n - 1] - F.lons[0]) * (n - 1);
  if (!(fx >= 0 && fy >= 0 && fx <= n - 1 && fy <= n - 1)) return null;
  const x0 = Math.min(n - 2, Math.floor(fx)), y0 = Math.min(n - 2, Math.floor(fy)), tx = fx - x0, ty = fy - y0;
  const at = (j, i) => { const s = F.speed_kmh[h][j][i], d = F.from_deg[h][j][i]; return s == null || d == null ? null : uv(s, d); };
  const c = [at(y0, x0), at(y0, x0 + 1), at(y0 + 1, x0), at(y0 + 1, x0 + 1)];
  if (c.some(v => !v)) return null;
  return [0, 1].map(k => (c[0][k] * (1 - tx) + c[1][k] * tx) * (1 - ty) + (c[2][k] * (1 - tx) + c[3][k] * tx) * ty);
}
function windResample() {
  if (!WIND.cv || !PM.wind) return;
  const el = PM.map.getContainer(), w = el.clientWidth, h = el.clientHeight, dpr = devicePixelRatio || 1, C = WIND.cell, hr = windHour();
  WIND.cv.width = w * dpr; WIND.cv.height = h * dpr; WIND.ctx.setTransform(dpr, 0, 0, dpr, 0, 0); WIND.w = w; WIND.h = h;
  const cols = Math.ceil(w / C), rows = Math.ceil(h / C), K = 0.025;           // px per frame for each km/h: 14 km/h drifts about 21 px a second
  WIND.cols = cols; WIND.cells = new Array(cols * rows);
  for (let r = 0; r < rows; r++) for (let c = 0; c < cols; c++) {
    const ll = PM.map.unproject([c * C + C / 2, r * C + C / 2]), v = sample(ll.lng, ll.lat, hr);
    WIND.cells[r * cols + c] = v ? [v[0] * K, -v[1] * K, Math.hypot(v[0], v[1])] : null;
  }
  WIND.parts = Array.from({ length: Math.min(700, Math.round(w * h / 1000)) }, () => spawn({}));   // sparse: a field to read, not a texture
  WIND.ctx.clearRect(0, 0, w, h);
  if (CLOCK.reduced()) still();
}
const vel = (x, y) => (x < 0 || y < 0 || x >= WIND.w || y >= WIND.h) ? null : WIND.cells[Math.floor(y / WIND.cell) * WIND.cols + Math.floor(x / WIND.cell)];
function spawn(p) {
  for (let k = 0; k < 12; k++) { p.x = Math.random() * WIND.w; p.y = Math.random() * WIND.h; if (vel(p.x, p.y)) break; }
  p.age = Math.floor(Math.random() * 160); p.max = 120 + Math.floor(Math.random() * 120); return p;   // slower, so each lives longer
}
const ink = a => `rgba(249,245,242,${a})`;   // light on the black screen, and on a photograph
function tick() {
  if (view() !== 'place' || !PM.on.wind || !PM.wind) { CLOCK.off('place-wind'); WIND.on = false; return; }
  if (WIND.moving || !WIND.cells) return;
  const x = WIND.ctx;
  x.globalCompositeOperation = 'destination-in'; x.fillStyle = 'rgba(0,0,0,.95)'; x.fillRect(0, 0, WIND.w, WIND.h);
  x.globalCompositeOperation = 'source-over'; x.strokeStyle = ink(.5); x.lineWidth = 1.1; x.beginPath();
  for (const p of WIND.parts) {
    const v = vel(p.x, p.y);
    if (!v || ++p.age > p.max) { spawn(p); continue; }
    x.moveTo(p.x, p.y); p.x += v[0]; p.y += v[1]; x.lineTo(p.x, p.y);
  }
  x.stroke();
}
/* reduced motion: one still arrow per 54 px, its length the speed, pointing where the wind goes */
function still() {
  const x = WIND.ctx, S = 54; x.clearRect(0, 0, WIND.w, WIND.h); x.strokeStyle = ink(.55); x.lineWidth = 1.2;
  for (let py = S / 2; py < WIND.h; py += S) for (let px = S / 2; px < WIND.w; px += S) {
    const v = vel(px, py); if (!v) continue;
    const L = Math.min(22, 4 + v[2] * .9), a = Math.atan2(v[1], v[0]), ex = px + Math.cos(a) * L / 2, ey = py + Math.sin(a) * L / 2;
    x.beginPath(); x.moveTo(px - Math.cos(a) * L / 2, py - Math.sin(a) * L / 2); x.lineTo(ex, ey);
    x.lineTo(ex - Math.cos(a - .5) * 5, ey - Math.sin(a - .5) * 5); x.moveTo(ex, ey); x.lineTo(ex - Math.cos(a + .5) * 5, ey - Math.sin(a + .5) * 5); x.stroke();
  }
}
function windSync() {
  if (!WIND.cv) return;
  const want = !!(PM.on.wind && PM.wind && view() === 'place');
  WIND.cv.hidden = !want;
  if (!want) { CLOCK.off('place-wind'); WIND.on = false; return; }
  if (!WIND.cells) windResample();
  if (CLOCK.reduced()) { still(); return; }
  if (!WIND.on) WIND.on = CLOCK.on('place-wind', tick);
}

/* ---------------------------------------------------------------- a dot, named where it stands */
/* Every dot answers a click with what it is, in a card on the map, and the way to its readings in Data. The
   inspector on the right keeps the longer facts. */
const DOTS = ['own', 'public', 'models', 'labs', 'images', 'species'];
const KIND = { phone: 'Phone', camera: 'Fixed camera', microscope: 'Microscope', drone: 'Drone', balloon: 'Balloon or kite' };
/* an image answers the token only, so it is fetched as a blob: an <img src> cannot carry the header */
const imgBlob = id => doorsFetch(`/captures/${id}/file`).then(r => (r.ok ? r.blob() : null)).catch(() => null);
let POP = null;
function popup(o) {
  if (POP) { POP.remove(); POP = null; }
  if (!o || o.kind === 'cell' || o.kind === 'river' || o.kind === 'basin') return;   // a line or an outline: the inspector says it
  let at, h;
  if (o.kind === 'station') {
    const s = o.s, v = lastRaw(s.sensor_id, 'pm25');
    at = [s.lon, s.lat];
    h = `<div class="k">${s.local ? 'This house’s station' : 'Public station · display only'}</div><b class="said">${esc(plain(s.name || s.sensor_id))}</b>`
      + `<span class="mono">${esc(s.source || '')}</span>`
      + `<span>${v == null ? '<span class="gap">not heard this hour</span>' : `PM2.5 ${fmt(v, 1)} µg/m³ ${prov(s.local ? 'live' : 'partial')}`}</span>`
      + `<a href="#data/${encodeURIComponent(s.sensor_id)}">Its readings in Data →</a>`;
  } else if (o.kind === 'model') {
    at = o.p;
    h = `<div class="k">Model points · ${o.ss.length}</div>` + o.ss.map(x => `<span class="said">${esc(x.name)}</span>`).join('')
      + `<span>${prov('model')} a model is partial, whatever its quality</span><a href="#data/models">The models in Data →</a>`;
  } else if (o.kind === 'image') {
    const c = o.c; at = [c.at[1], c.at[0]];
    h = `<div class="k">Image · ${esc(KIND[c.kind] || c.kind)}</div><img class="pmimg" alt="${esc(c.note || KIND[c.kind] || 'an image')}">`
      + (c.note ? `<b>${esc(c.note)}</b>` : '') + (c.analysis ? `<span>${esc(c.analysis.summary || '')} <i>(${c.analysis.confirmed_by ? 'confirmed' : 'model'})</i></span>` : '') + `<span class="mono">${esc(when(c.ts))}${c.actor ? ' · ' + esc(c.actor) : ''}</span>`
      + `<span class="mono">${esc(c.cell)}${c.lat == null ? ' · no point, its cell' : ''}</span><a href="#data/d-images">Its details in Data →</a>`;
    imgBlob(c.id).then(b => { const el = POP && POP.getElement().querySelector('.pmimg'); if (b && el) { el.src = URL.createObjectURL(b); el.onload = () => URL.revokeObjectURL(el.src); } });
  } else if (o.kind === 'lab') {
    at = [o.s.lon, o.s.lat];
    h = `<div class="k">Place to make</div><b>${esc(o.s.name)}</b><span class="mono">listed on fablabs.io · shown, never counted</span>`;
  }
  POP = new maplibregl.Popup({ closeButton: true, closeOnClick: false, offset: 12, maxWidth: '260px', className: 'pmpop' })
    .setLngLat(at).setHTML(h).addTo(PM.map);
  POP.on('close', () => { POP = null; });
}

/* ---------------------------------------------------------------- without WebGL */
/* A browser or a kiosk with no WebGL threw at new maplibregl.Map and drew nothing, not even the list or the facts
   (Tomas's review, 15 Oct). Now the same answers are drawn still, the way Node draws its cell: the node's cell and its
   res-6 parent's cells (D.ngeo), the rings (GET /geo/rings), the stations, the images and the house, projected, never
   tiled. Without the token only the stations and the house: the cells and the rings place the node. */
const FLAT = ['grid', 'mine', 'own', 'public', 'rings', 'images', 'species'];
function flat() {
  const el = $('#map'), W = el.clientWidth || 600, H = el.clientHeight || W, NG = D.ngeo, on = id => PM.on[id];
  const st = outside(D.sensors).filter(s => s.kind === 'sensor' && s.lat != null), five = RINGS && RINGS.find(r => r.km === 5);
  let pts = five && on('rings') ? five.path : NG ? loop(NG.c6.ring) : st.filter(s => s.local).map(lngLat).concat([D.point]);
  if (pts.length < 2) pts = [D.point, [D.point[0] + .02, D.point[1] + .02]];
  const pr = d3.geoMercator().fitExtent([[60, 60], [W - 60, H - 60]], { type: 'MultiPoint', coordinates: pts });
  const xy = q => pr(q).map(v => v.toFixed(1)), d = ring => 'M' + ring.map(q => xy(q).join(',')).join('L') + 'Z';
  const T = (q, t, cls, dy = 0) => { const [x, y] = xy(q); return `<text x="${x}" y="${+y + dy}" class="${cls}">${esc(t)}</text>`; };
  let s = `<svg viewBox="0 0 ${W} ${H}" width="${W}" height="${H}" class="geo flatmap" role="img" aria-label="The node’s cell, the stations and the rings, drawn still">`;
  if (NG && on('grid')) s += NG.c6.children_ll.filter(k => k[0] !== NG.c8.id).map(k => `<path d="${d(loop(k))}" class="hex"/>`).join('');
  if (NG && on('mine')) s += `<path d="${d(loop(NG.c8.ring))}" class="mine"/>`;
  if (RINGS && on('rings')) s += RINGS.map(r => `<path d="${d(r.path)}" class="ringl"/>` + T(r.path[0], `${r.km} km`, 'rl', -4)).join('');
  if (on('public')) s += st.filter(x => !x.local).map(x => { const [cx, cy] = xy(lngLat(x)); return `<circle cx="${cx}" cy="${cy}" r="4.5" class="st"/>`; }).join('');
  if (on('own')) s += st.filter(x => x.local).map(x => { const [cx, cy] = xy(lngLat(x)); return `<circle cx="${cx}" cy="${cy}" r="5" class="st in"/>`; }).join('');
  if (PM.caps && on('images')) s += PM.caps.map(c => T([c.at[1], c.at[0]], '■', 'gl')).join('');
  if (PM.caps && on('species')) s += speciesMarks().map(m => T([m.c.at[1], m.c.at[0]], '◆', 'gl', -13)).join('');
  const [hx, hy] = xy(D.point);
  s += `<circle cx="${hx}" cy="${hy}" r="9" class="house"/></svg>`;   // named in the margin, never on the point
  el.innerHTML = s + `<p class="flatnote">${esc(PM.flat)}</p>`;
  if (PM.offline) offline(PM.offline);
}

/* ---------------------------------------------------------------- mount once; later calls re-skin */
async function placeMap() {
  if (PM.flat) { flat(); panel(); facts(); margin(); return; }
  if (PM.map) {
    PM.map.resize(); chrome(); panel(); facts(); windSync(); loadCells().then(() => { redraw(); facts(); }); return;
  }
  /* The plan is the node's own GET /place/geojson, centred where the node stands. Only when the node has none is the
     design kit's copy drawn, and the layer row says it is 1.2 km off. */
  PM.meta = await ask('ground/meta').catch(() => null);
  PM.wind = await doorsFetch(API + 'ground/wind').then(r => r.status === 200 ? r.json() : null).catch(() => null);
  PM.ground = (PM.meta && PM.meta.on_disk) || {};
  groundRows(); packRows();
  NEAR = new Map(((await doorsFetch('/nearby').then(r => (r.ok ? r.json() : null)).catch(() => null)) || {}).ring?.map(x => [x.sensor_id, x.km]) || []);
  [PM.caps, PM.species] = await Promise.all([ask('captures?limit=500').catch(() => null), ask('species').catch(() => null)]); imageRows();
  PM.hydro = await ask('hydro').catch(() => null); hydroRows();
  await loadCells();
  PM.energy = await ask('energy').catch(() => null); energyRows();
  const nodePlan = await ask('place/geojson').then(g => (g.features || []).length ? g : null).catch(() => null);
  PM.land = { type: 'FeatureCollection', features: [] }; PM.plan = nodePlan;
  if (!nodePlan && !PM.ground.vector && PM.meta) LAYERS.find(l => l.id === 'street').sub = 'the node sent no plan and holds no street map: planetai run place basemap';
  const el = $('#map'); el.innerHTML = '';
  panel();   /* the list first: the map takes its height, so it must be at its height before the map is centred */
  let map;
  try { map = PM.map = new maplibregl.Map({ container: el, style: style(), center: D.point, zoom: 13.6, minZoom: 5, maxZoom: 18.5,
    dragRotate: false, pitchWithRotate: false, touchPitch: false, maxPitch: 0, attributionControl: false, fadeDuration: 0, canvasContextAttributes: { preserveDrawingBuffer: true },
    /* the one guard that keeps the promise: nothing but this page's own origin is ever asked for a tile */
    transformRequest: url => (url.startsWith(location.origin + '/ground/') ? { url, headers: DOORS_AUTH() }
      : url.startsWith(location.origin) || url.startsWith('blob:') ? { url } : { url: 'data:,' }) }); } catch (e) {
    /* no WebGL here: the still drawing, and the list and the facts as always */
    PM.map = null; PM.res = 8;
    if (D.ngeo) GRID = { res: 8, edge_m: EDGE(8), node: D.ngeo.c8.id, nodeRing: loop(D.ngeo.c8.ring), cells: [] };
    console.warn('Place: no live map', e);
    PM.flat = `This browser gave the map no WebGL, so the node’s answers are drawn still: its cell, the stations, the rings and the images. Panning, the scales and measuring need the live map.`;
    flat(); panel(); facts(); credits(); margin(); placeMaps();
    if (!D.ngeo) offline(D.ngeoErr || 'no token');
    ask('geo/rings?km=2,5,15').then(x => { RINGS = x.rings.map(g => ({ km: g.km, path: g.ring.map(([la, ln]) => [ln, la]) })); flat(); }).catch(() => {});
    return;
  }
  map.touchZoomRotate.disableRotation();
  map.addControl(new maplibregl.ScaleControl({ maxWidth: 110, unit: 'metric' }), 'bottom-left');   // above the rungs: the zoom and the credit hold the right
  PM.overlay = new deck.MapboxOverlay({ interleaved: true, layers: [], pickingRadius: 8,
    onHover: info => { PM.hoverDot = !!(info.object && (DOTS.includes(info.layer.id) || info.layer.id.startsWith('draw-'))); },
    /* deck.gl owns the cursor in interleaved mode: a dot says it can be clicked, drawing and measuring keep the cross.
       A press is the map's own click (press(), below), which asks the overlay what is under it. */
    getCursor: ({ isDragging }) => isDragging ? 'grabbing' : MEASURING() || DRAWING() || PM.draw.corner != null ? 'crosshair' : PM.hoverDot ? 'pointer' : 'grab' });
  map.addControl(PM.overlay);
  /* luma.gl keeps the canvas's framebuffer at the size it first saw, and deck flips its y with that height, so after the
     screen grows taller (Full screen) every deck layer drew lower than the map by the difference (node #1, 5 Nov: the
     cell left its place). After each frame, a framebuffer that is not the canvas's size is let go and the map drawn
     again; luma learns the new size a frame or two after the resize, so this repeats until the two agree.
     ponytail: reaches into deck 9.4 / luma internals; drop it once deck's interleaved overlay follows a resize itself */
  map.on('render', () => {
    const c = PM.overlay._deck && PM.overlay._deck.device && PM.overlay._deck.device.canvasContext, f = c && c._framebuffer, cv = map.getCanvas();
    if (f && (f.width !== cv.width || f.height !== cv.height)) { c._framebuffer = null; map.triggerRepaint(); }
  });
  tools();
  WIND.cv = document.createElement('canvas'); WIND.cv.className = 'windcv'; WIND.cv.setAttribute('aria-hidden', 'true');
  WIND.ctx = WIND.cv.getContext('2d'); map.getContainer().appendChild(WIND.cv);
  map.on('movestart', () => { WIND.moving = true; if (WIND.ctx) WIND.ctx.clearRect(0, 0, WIND.w || 0, WIND.h || 0); });
  map.on('moveend', () => { WIND.moving = false; windResample(); windSync(); });
  map.on('resize', () => { windResample(); margin(); });
  /* the DOM on the screen follows the map while it moves, once a frame; the list, the grid and the panel wait for moveend */
  let moving = 0;
  map.on('move', () => { if (!moving) moving = requestAnimationFrame(() => { moving = 0; edges(); following(); }); });
  map.on('load', () => {
    applyBase(); PM.res = resFor(map.getZoom()); redraw(); chrome(); panel(); facts(); loadGrid(); credits(); windResample(); windSync();
    ask('geo/rings?km=2,5,15').then(x => { RINGS = x.rings.map(g => ({ km: g.km, path: g.ring.map(([la, ln]) => [ln, la]) })); redraw(); }).catch(() => {});
    cellFacts(D.geometry.radio.mine).then(c => { RADIO = { id: c.id, path: loop(c.ring) }; redraw(); }).catch(() => {});
  });
  map.on('moveend', () => { const r = resFor(map.getZoom()); if (r !== PM.res) { PM.res = r; chrome(); } redraw(); panel(); loadGrid(); credits(); });
  map.on('mousemove', e => { const d = PM.draw; PM.lastPt = e.point; if (DRAWING() && d.state && d.state.pts.length) { d.hover = [e.lngLat.lng, e.lngLat.lat]; figureOnly(); redraw(); } });
  map.on('click', e => {
    if (PM.dlm && !PM.dlm.hidden) { dlMenu(false); return; }   // a press that closes the menu does nothing else
    const tb = document.getElementById && document.getElementById('ptoolsb');
    if (tb && tb.getAttribute('aria-expanded') === 'true') return;   // nor one that closes Tools (doors-place.js closes it on the same press)
    if (PM.tool === 'from') {
      const q = [e.lngLat.lng, e.lngLat.lat]; PM.measure = [D.point, q]; PM.measured = null; redraw(); facts();
      fromNode(q[0], q[1]).then(d => { if (PM.measure[1] === q) { PM.measured = { points: 2, legs_m: [d], total_m: d }; redraw(); facts(); figureOnly(); } }).catch(x => offline(x.message));
      return;
    }
    if (PM.tool === 'pull') { pullPress(e); return; }
    press(e);
  });
  map.on('dblclick', e => {
    if (MEASURING()) { e.preventDefault(); PM.setTool('select'); return; }
    const d = PM.draw; if (!DRAWING() || !d.state) return;
    e.preventDefault();
    /* a double press is two presses and then this: the second press's point is the first one's again */
    const q = d.state.pts, a = q.length >= 2 && PM.map.project(q[q.length - 1]), b = a && PM.map.project(q[q.length - 2]);
    if (a && Math.hypot(a.x - b.x, a.y - b.y) < 6) d.state = backPt(d.state);
    finish();
  });
  document.addEventListener('keydown', onKey, true);   // capture: an arrow moving a corner must not also pan the map
  placeMaps();
}
window.placeMap = placeMap; window.placeLayer = setLayer; window.placeSheet = placeSheet; window.placeCake = placeCake; window.placeNoMap = NOMAP; window.__PM = PM;   // __PM for the rig
/* the figures' Rivers row: both hydro rows on, and out to District scale, where the nearest river is in view */
window.placeRivers = () => { setLayer('rivers', true); setLayer('basin', true); if (PM.map) fly(6); };
/* the Images panel added one: ask again, so its kind's row and its square appear */
window.placeImagesChanged = async () => { if (!PM.map && !PM.flat) return; [PM.caps, PM.species] = await Promise.all([ask('captures?limit=500').catch(() => null), ask('species').catch(() => null)]); imageRows(); panel(); redraw(); };
/* The same base for the doors' other maps (Now's "around this house"): the node's own street map and names when this
   screen may have them; without them only the land's colour, never a tile from anywhere else. */
window.groundBase = async theme => {
  if (!PM.meta) { PM.meta = await ask('ground/meta').catch(() => null); PM.ground = (PM.meta && PM.meta.on_disk) || {}; }
  PM.land = PM.land || { type: 'FeatureCollection', features: [] };
  const p = PAL[theme === 'dark' ? 'dark' : 'light'], s = style(p);
  s.layers = s.layers.filter(l => !['imagery', 'drone', 'drone-close', 'plan-sat'].includes(l.id));
  if (!PM.ground.vector) s.layers[0].paint['background-color'] = p.land;
  return { style: s, palette: p, street: !!PM.ground.vector };
};
window.groundRequest = url => (url.startsWith(location.origin + '/ground/') ? { url, headers: DOORS_AUTH() }
  : url.startsWith(location.origin) || url.startsWith('blob:') ? { url } : { url: 'data:,' });
})();
