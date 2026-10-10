'use strict';
/* PLACE · the map workbench (R36, 7 Oct 2026). MapLibre draws the base, deck.gl draws the node's data over it.

   REFERENCE LOCK (Refero, docs in the R36 note):
   - Mapbox's cartographic rule: the map is neutral and the data is the only colour. One signal hue, the node's
     --cells blue, for the cell and focus; orange stays the satellite's alone. No second accent.
   - mono's architectural chrome: square corners, 1 px ink rules, tracked mono labels. Nothing rounded, no shadow.
   - OneSoil: scale selector floating top-centre over the map, a vertical tool stack on the right edge.
   - Mapbox Studio: the layer list IS the legend (a swatch per row); a status line under the map carries the
     cursor's coordinates, the zoom, the resolution and the cell under the pointer.

   SCALE. The H3 resolution drawn follows the zoom: the finest rung whose cell is at least 56 px to an edge on
   screen. The presets fly to the node's own cell at that rung, so a press and a scroll agree. Rungs 6 and coarser
   (cells that may leave the machine) are dotted, as on the node's ladder.

   THE NODE COMPUTES, THE PAGE DRAWS (R36.1, and R40 for every door). No h3-js and no distance here. The grid, the node's cell at each rung,
   the radio cell, the rings, every measured metre and every cell fact are answers from the node's GET /geo/*
   routes, asked with this screen's token (token-only at every SHARE_LEVEL); the plan is the node's own
   GET /place/geojson. Without the token the map says what it is not drawing, and why. */

(function () {
const PM = { map: null, overlay: null, theme: null, res: 8, tool: 'inspect', measure: [], hover: null, pick: null,
  on: {}, alpha: {}, plan: null, land: null };

/* ---------------------------------------------------------------- the palette, by register */
const PAL = {
  light: { sea: '#DCE2E6', land: '#F1EFEB', green: '#E1E6DB', road: '#FFFFFF', casing: '#D5D1CA', bldg: '#CFCBC4',
    coast: '#B9B4AC', built: '#E9E6E1', sand: '#EEE9DE', farm: '#ECEDE5', label: '#5F5A54', lhalo: '#F1EFEB', major: '#FFFFFF', path: '#B9B4AC', ink: [23, 23, 23], mute: [95, 90, 84], cells: [32, 56, 141], sat: [219, 114, 0], halo: [241, 239, 235] },
  dark: { sea: '#0E1012', land: '#17191D', green: '#1A201C', road: '#30353D', casing: '#17191D', bldg: '#2B2E34',
    coast: '#3A3F47', built: '#1C1F23', sand: '#1E1F1C', farm: '#191C19', label: '#A3A19F', lhalo: '#17191D', major: '#3C424B', path: '#3A3F47', ink: [249, 245, 242], mute: [163, 161, 159], cells: [127, 165, 232], sat: [255, 147, 30], halo: [23, 25, 29] },
};
const P = () => PAL[PM.theme === 'dark' ? 'dark' : 'light'];

/* ---------------------------------------------------------------- scales: named rungs of the ladder */
const SCALES = [[10, 'Street'], [9, 'Block'], [8, 'Cell'], [7, 'Village'], [6, 'District'], [4, 'Island'], [3, 'Radio']];
const EDGE = r => (D.geometry.ladder.find(l => l.res === r) || {}).edge_m || 1;
const mPerPx = z => 40075016.686 * Math.cos(D.point[1] * Math.PI / 180) / (512 * 2 ** z);
const resFor = z => { for (let r = 12; r >= 2; r--) if (EDGE(r) / mPerPx(z) >= 56) return r; return 2; };
const mayLeave = r => r <= 6;

/* ---------------------------------------------------------------- the layer registry: one row per layer, by pack.
   A pack that grows a layer adds one entry here. `empty` is a layer the pack would draw and cannot yet: the row
   stays, says so in the node's words, and cannot be switched on. */
const LAYERS = [
  { id: 'street', group: 'Base', pack: 'place', name: 'Street map', sub: 'OpenStreetMap, kept on this node', sw: 'fill-land', on: true, still: true },
  { id: 'labels', group: 'Base', pack: 'place', name: 'Names', sub: 'places, streets, points of interest', sw: 'txt', on: true, still: true, need: 'glyphs' },
  { id: 'imagery', group: 'Base', pack: 'earth-engine', name: 'Satellite, 10 m', sub: 'Sentinel-2, composited by this node', sw: 'fill-photo', on: false, need: 'imagery' },
  { id: 'drone', group: 'Base', pack: 'place', name: 'Drone imagery', sub: 'OpenAerialMap, where somebody flew', sw: 'fill-photo', on: false, need: 'drone', minz: 13 },
  { id: 'grid', group: 'Grid', pack: 'core', name: 'H3 cells at this scale', sub: 'dotted where a cell may leave', sw: 'line-grid', on: true },
  { id: 'mine', group: 'Grid', pack: 'core', name: 'The cell it stands in', sub: 'at the resolution in view', sw: 'fill-cell', on: true },
  { id: 'radio', group: 'Grid', pack: 'reticulum', name: 'What leaves by radio', sub: 'the res-3 cell it announces', sw: 'line-dot', on: true, maxz: 10 },
  { id: 'own', group: 'Readings', pack: 'core', name: 'This house’s stations', sub: 'filled', sw: 'pt-own', on: true },
  { id: 'public', group: 'Readings', pack: 'nearby', name: 'Public stations', sub: 'hollow · display only, never alert', sw: 'pt-pub', on: true },
  { id: 'models', group: 'Readings', pack: 'core', name: 'Model points', sub: 'sea, air, land, weather', sw: 'pt-model', on: true },
  { id: 'rings', group: 'Readings', pack: 'nearby', name: 'Distance rings', sub: '2, 5 and 15 km', sw: 'line-ring', on: false },
  { id: 'satonly', group: 'Packs', pack: 'place', name: 'Only the satellite knows', sub: 'buildings missing from OSM', sw: 'fill-sat', on: true, minz: 12.5 },
  { id: 'wind', group: 'Packs', pack: 'forecast', name: 'Wind, moving', sub: 'Open-Meteo field round the node', sw: 'pt-wind', on: true, need: 'wind', still: true },
  { id: 'labs', group: 'Packs', pack: 'make', name: 'Places to make', sub: 'from fablabs.io', sw: 'pt-lab', on: true },
  { id: 'earth', group: 'Packs', pack: 'earth', name: 'Land change raster', sub: 'AlphaEarth, year on year', sw: 'fill-photo', empty: true },
  { id: 'index', group: 'Packs', pack: 'index', name: 'Fab City Index cells', sub: 'the 20 cells for this place', sw: 'fill-cell', empty: true },
  { id: 'peers', group: 'Packs', pack: 'reticulum', name: 'Nodes heard nearby', sub: 'their announced cells', sw: 'line-dot', empty: true },
];
LAYERS.forEach(l => { PM.on[l.id] = !!l.on && !l.empty; PM.alpha[l.id] = 1; });

/* ---------------------------------------------------------------- asking the node */
const API = '/';
const ask = p => fetch(API + p, { headers: DOORS_AUTH() }).then(async r => {
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
const area = m2 => m2 >= 1e6 ? `${(m2 / 1e6).toFixed(m2 >= 1e8 ? 0 : 2)} km²` : `${(m2 / 1e4).toFixed(1)} ha`;

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
  redraw(); if (!PM.pick && PM.tool !== 'measure') facts();
}
/* Said once, on the map, when the node does not answer: what is missing and why, never a blank grid. */
function offline(why) {
  PM.offline = why;
  let n = document.querySelector('.nonode');
  if (!why) { if (n) n.remove(); return; }
  if (!n) { n = document.createElement('p'); n.className = 'nonode'; PM.map.getContainer().appendChild(n); }
  n.textContent = `The node did not give this screen its map (${why}). The grid, the rings, the cell facts, every distance and the node’s own street map and satellite are token-only, because together they say where the node is. Unlock this screen under Node to draw them.`;
}

/* ---------------------------------------------------------------- the base style: everything from the node's disk */
/* GET /ground/* (planetai-node): OpenStreetMap vector tiles cut from Protomaps' build, the label fonts, this node's
   own Sentinel-2 composite and any OpenAerialMap drone mosaic, fetched once by `planetai run place basemap` and
   `planetai run earth-engine basemap`. Nothing here asks a tile server. Without the vector tiles the plan from
   /place/geojson draws instead, as before. Rasters sit over the street map and under the names: a hybrid. */
const GREEN = ['park', 'wood', 'forest', 'garden', 'grass', 'grassland', 'scrub', 'nature_reserve', 'golf_course', 'cemetery', 'meadow', 'national_park', 'protected_area', 'recreation_ground', 'village_green', 'pitch', 'playground'];
const BUILT = ['industrial', 'commercial', 'retail', 'university', 'school', 'college', 'hospital', 'military', 'railway', 'airfield', 'aerodrome', 'runway', 'pedestrian', 'parking', 'platform'];
const SAND = ['beach', 'sand', 'bare_rock', 'scree'];
function style() {
  const p = P(), k = v => ['==', ['get', 'kind'], v], any = l => ['in', ['get', 'kind'], ['literal', l]], G = PM.ground || {}, V = !!G.vector;
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
  if (G.imagery) L.push({ id: 'imagery', type: 'raster', source: 'imagery', layout: { visibility: 'none' }, paint: { 'raster-fade-duration': 0 } });
  if (G.drone) L.push({ id: 'drone', type: 'raster', source: 'drone', minzoom: 13, layout: { visibility: 'none' }, paint: { 'raster-fade-duration': 0 } });
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
const OWNS = { street: ['land-fill', 'land-edge', 'v-earth', 'v-farm', 'v-green', 'v-built', 'v-sand', 'v-water', 'v-stream', 'v-coast', 'v-path', 'v-casing', 'v-road', 'v-bldg', 'plan-green', 'plan-casing', 'plan-road', 'plan-bldg'],
  labels: ['v-road-label', 'v-poi-label', 'v-place-label'], imagery: ['imagery'], drone: ['drone'], satonly: ['plan-sat'] };
function applyBase() {
  for (const [id, ls] of Object.entries(OWNS)) for (const l of ls) {
    if (!PM.map.getLayer(l)) continue;
    PM.map.setLayoutProperty(l, 'visibility', PM.on[id] ? 'visible' : 'none');
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
  const set = (id, sub, empty, why) => { const l = LAYERS.find(x => x.id === id); if (sub) l.sub = sub; l.empty = !!empty; l.why = why; l.locked = locked && !!empty; if (empty) PM.on[id] = false; };
  set('street', G.vector ? `OpenStreetMap ${(m.vector || {}).build ? `build ${m.vector.build.slice(0, 8)}` : ''} · ${mb((m.vector || {}).bytes)} on this node` : locked ? 'token-only · unlock this screen under Node' : 'the plan from /place/geojson; no street map on this node yet');
  set('labels', null, !(G.vector && G.glyphs), 'planetai run place basemap --only vector');
  const im = m.imagery || {};
  set('imagery', G.imagery ? `Sentinel-2, ${im.passes} passes, ${(im.from || '').slice(0, 7)} to ${(im.to || '').slice(0, 7)} · ${mb(im.bytes)}` : null, !G.imagery, 'planetai run earth-engine basemap');
  const dr = m.drone || {}, ms = dr.mosaics || [];
  const W = PM.wind;
  set('wind', W ? `Open-Meteo, ${W.n * W.n} points over ${W.km * 2} km, hourly · read ${W.fetched.slice(11, 16)} UTC` : null, !W,
    'FORECAST_OPENMETEO=1, then planetai run forecast windfield');
  set('drone', G.drone && ms.length ? `${ms.map(x => `${x.provider}, ${Math.round(x.gsd_m * 100)} cm, ${x.date}`).join(' · ')} · ${mb(dr.bytes)}` : null, !G.drone, 'planetai run place basemap --only drone');
}
function credits() {
  const m = (PM.meta && PM.meta.layers) || {}, c = [];
  if (PM.on.street && PM.ground && PM.ground.vector) c.push('© OpenStreetMap contributors · Protomaps');
  if (PM.on.imagery && m.imagery) c.push(m.imagery.attribution);
  if (PM.on.drone && m.drone) c.push((m.drone.mosaics || []).map(x => `${x.provider} via OpenAerialMap, CC BY 4.0`).join(' · '));
  if (PM.on.wind && PM.wind) c.push('wind: Open-Meteo, CC BY 4.0');
  c.push('Natural Earth');
  const el = $('#mapcredit'); if (el) el.textContent = c.join(' · ');
}

/* ---------------------------------------------------------------- the data, drawn by deck.gl */
function layers() {
  const p = P(), Dk = deck, a = id => PM.alpha[id], z = PM.map.getZoom(), r = PM.res, A = (c, o) => [...c, Math.round(o * 255)];
  const vis = l => PM.on[l.id] && (l.minz == null || z >= l.minz) && (l.maxz == null || z <= l.maxz);
  const L = Object.fromEntries(LAYERS.map(l => [l.id, vis(l)]));
  const px = { lineWidthUnits: 'pixels', radiusUnits: 'pixels', widthUnits: 'pixels' }, out = [];   // PathLayer reads widthUnits
  const dashed = new Dk.PathStyleExtension({ dash: true });
  const S = D.sensors.filter(s => s.lat != null);
  const G = GRID, gr = G ? G.res : r;

  if (L.rings && RINGS) {
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
    const cells = G.cells.filter(c => c.id !== G.node);
    /* over a photograph the grid is drawn light on a dark edge, as the svg ground draws hairlines over tiles */
    const photo = (PM.on.imagery && PM.ground.imagery && z >= 8) || (PM.on.drone && PM.ground.drone && z >= 13);
    const gc = photo ? A([255, 255, 255], .8 * a('grid')) : A(p.ink, (z >= 12.5 ? .3 : .22) * a('grid'));
    if (photo) out.push(new Dk.PathLayer({ id: 'grid-edge', data: cells, getPath: d => d.path, ...px, getColor: [0, 0, 0, Math.round(90 * a('grid'))], getWidth: 2.6 }));
    /* solid and dotted are two layers, not one with a switched extension: deck.gl cannot swap a layer's shader */
    out.push(mayLeave(gr)
      ? new Dk.PathLayer({ id: 'grid-dot', data: cells, getPath: d => d.path, ...px, pickable: true, autoHighlight: true, highlightColor: A(p.cells, .35),
        getColor: gc, getWidth: 1.2, extensions: [dashed], getDashArray: [1.5, 3] })
      : new Dk.PolygonLayer({ id: 'grid', data: cells, getPolygon: d => d.path, ...px, pickable: true, autoHighlight: true, highlightColor: A(p.cells, .06),
        filled: true, getFillColor: [0, 0, 0, 0], getLineColor: gc, getLineWidth: 1 }));
  }
  if (L.mine && G) {
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
  /* the node itself, always: a ring, not a dot, because /health publishes its cell's centre to strangers */
  out.push(new Dk.ScatterplotLayer({ id: 'node', data: [{ p: D.point }], getPosition: d => d.p, ...px, stroked: true, filled: false,
    getRadius: 9, getLineColor: A(p.cells, 1), getLineWidth: 2 }));
  if (PM.measure.length) {
    const path = PM.measure.concat(PM.hover && PM.tool === 'measure' ? [PM.hover] : []);
    /* each placed leg labelled with the node's own metres for it; the leg to the cursor is drawn, not measured */
    const legs = (PM.measured && PM.measured.points === PM.measure.length) ? PM.measured.legs_m : [];
    const lab = PM.measure.map((q, i) => ({ q, t: i ? (legs[i - 1] != null ? fmtM(legs[i - 1]) : '…') : 'start' }));
    out.push(new Dk.PathLayer({ id: 'measure', data: [{ path }], getPath: d => d.path, ...px, getColor: A(p.cells, 1), getWidth: 2, extensions: [dashed], getDashArray: [6, 3] }));
    out.push(new Dk.ScatterplotLayer({ id: 'measure-v', data: PM.measure, getPosition: q => q, ...px, getRadius: 3.5, getFillColor: A(p.halo, 1), stroked: true, getLineColor: A(p.cells, 1), getLineWidth: 2 }));
    out.push(new Dk.TextLayer({ characterSet: 'auto', id: 'measure-l', data: lab, getPosition: d => d.q, getText: d => d.t, getSize: 11, fontFamily: 'JetBrains Mono, monospace',
      getColor: A(p.ink, 1), getPixelOffset: [0, -14], background: true, getBackgroundColor: A(p.halo, .95), backgroundPadding: [4, 2] }));
  }
  return out;
}
const redraw = () => PM.overlay && PM.overlay.setProps({ layers: layers() });

/* ---------------------------------------------------------------- the panel: layers as legend */
function panel() {
  const groups = d3.groups(LAYERS, l => l.group);
  const z = PM.map ? PM.map.getZoom() : 0;
  $('#layers').innerHTML = `<div class="lyh"><span class="k">Layers</span><span class="k">${LAYERS.filter(l => PM.on[l.id]).length} on</span></div>`
    + groups.map(([g, ls]) => `<div class="lyg"><div class="k">${g}</div>` + ls.map(l => {
      const hidden = PM.on[l.id] && ((l.minz != null && z < l.minz) || (l.maxz != null && z > l.maxz));
      return `<div class="ly ${l.empty ? 'empty' : ''} ${PM.on[l.id] ? 'on' : ''}" data-l="${l.id}">`
        + `<label><input type="checkbox" ${PM.on[l.id] ? 'checked' : ''} ${l.empty ? 'disabled' : ''} aria-label="${esc(l.name)}">`
        + `<i class="sw ${l.sw}" aria-hidden="true"></i><span class="nm">${esc(l.name)}<small>${l.empty ? (l.locked ? 'token-only · unlock this screen under Node' : `The ${l.pack} pack has nothing here yet${l.why ? ` · <code>${esc(l.why)}</code>` : ''}`) : esc(l.sub)}${hidden ? ` · ${l.minz != null && z < l.minz ? 'zoom in to see' : 'zoom out to see'}` : ''}</small></span>`
        + `<span class="pk">${esc(l.pack)}</span></label>`
        + (l.id === 'wind' && PM.on.wind && PM.wind ? `<label class="whr"><span>now</span><input type="range" min="0" max="${PM.wind.times.length - 1 - nowIdx()}" step="1" value="${PM.windStep}" aria-label="Hours ahead"><b>${PM.windStep ? `+${PM.windStep} h` : 'now'}</b></label>` : '')
        + (l.empty || l.still ? '' : `<input class="op" type="range" min="0" max="1" step="0.05" value="${PM.alpha[l.id]}" aria-label="${esc(l.name)} opacity" ${PM.on[l.id] ? '' : 'disabled'}>`)
        + `</div>`;
    }).join('') + `</div>`).join('');
  document.querySelectorAll('#layers .ly').forEach(row => {
    const id = row.dataset.l, cb = row.querySelector('input[type=checkbox]'), op = row.querySelector('.op');
    cb.onchange = () => { PM.on[id] = cb.checked; applyBase(); redraw(); panel(); credits(); windSync(); status(PM.cursor); };
    const wh = row.querySelector('.whr input');
    if (wh) wh.oninput = () => { PM.windStep = +wh.value; row.querySelector('.whr b').textContent = PM.windStep ? `+${PM.windStep} h` : 'now'; windResample(); status(PM.cursor); };
    if (op) op.oninput = () => { PM.alpha[id] = +op.value; applyBase(); redraw(); };
  });
}

/* ---------------------------------------------------------------- the scale selector and the tools */
function chrome() {
  $('#mapbar').innerHTML = `<div class="scales" role="group" aria-label="Scale">${SCALES.map(([r, n]) =>
    `<button data-r="${r}" class="${r === PM.res ? 'on' : ''} ${mayLeave(r) ? 'leave' : ''}" title="${esc(`${n}: resolution ${r}, about ${fmtM(EDGE(r))} to an edge${mayLeave(r) ? ' · coarse enough to leave the machine' : ''}`)}"><b>${n}</b><span>${r}</span></button>`).join('')}</div>`;
  document.querySelectorAll('.scales button').forEach(b => b.onclick = () => fly(+b.dataset.r));
}
async function fly(r) {
  let c; try { c = await cellAt(D.point[0], D.point[1], r); } catch (e) { offline(e.message); return; }
  const bb = loop(c.ring).reduce((m, [x, y]) => [Math.min(m[0], x), Math.min(m[1], y), Math.max(m[2], x), Math.max(m[3], y)], [180, 90, -180, -90]);
  const pad = Math.round(PM.map.getContainer().clientWidth * 0.36);
  PM.map.fitBounds([[bb[0], bb[1]], [bb[2], bb[3]]], { padding: pad, duration: CLOCK.reduced() ? 0 : 700 });
}
function tools() {
  const el = document.createElement('div'); el.className = 'tools';
  const T = [['in', '+', 'Zoom in'], ['out', '−', 'Zoom out'], ['fit', '⌖', 'Back to this node’s cell'], ['inspect', '↖', 'Inspect: click a feature'],
    ['measure', '⟷', 'Measure: click points, double-click to finish'], ['png', '⤓', 'Save this view as a PNG']];
  el.innerHTML = T.map(([k, g, t]) => `<button data-t="${k}" title="${t}" aria-label="${t}" class="${k === PM.tool ? 'on' : ''}">${g}</button>`).join('');
  el.onclick = e => {
    const k = e.target.closest('button')?.dataset.t; if (!k) return;
    if (k === 'in') PM.map.zoomIn(); else if (k === 'out') PM.map.zoomOut(); else if (k === 'fit') fly(8);
    else if (k === 'png') { const a = document.createElement('a'); a.download = `place-res${PM.res}.png`; PM.map.triggerRepaint(); PM.map.once('render', () => { a.href = PM.map.getCanvas().toDataURL('image/png'); a.click(); }); }
    else { PM.tool = k; if (k === 'measure') { PM.measure = []; PM.measured = null; } el.querySelectorAll('button').forEach(b => b.classList.toggle('on', b.dataset.t === PM.tool)); PM.map.getCanvas().style.cursor = k === 'measure' ? 'crosshair' : ''; redraw(); facts(); }
  };
  PM.map.getContainer().appendChild(el);
}

/* ---------------------------------------------------------------- the status line and the inspector */
/* The cell under the cursor is the node's answer, asked once the pointer rests for a moment. */
let STAT = 0;
function status(ll) {
  const z = PM.map.getZoom();
  $('#mapstatus').innerHTML = `<span>${ll ? `${ll[1].toFixed(5)}, ${ll[0].toFixed(5)}` : '—'}</span><span>z ${z.toFixed(1)}</span>`
    + `<span class="${mayLeave(PM.res) ? 'leave' : ''}">res ${PM.res} · ${fmtM(EDGE(PM.res))} edge</span>${windWords()}<span class="cid"></span>`;
  clearTimeout(STAT);
  if (ll && !PM.offline) STAT = setTimeout(() => cellAt(ll[0], ll[1], PM.res).then(c => { const el = $('#mapstatus .cid'); if (el && PM.cursor === ll) el.textContent = c.id; }).catch(() => {}), 140);
}
let FSEQ = 0;
async function facts() {
  const seq = ++FSEQ, o = PM.pick, r = PM.res, row = (t, v, sub) => `<div class="fr"><span>${esc(t)}${sub ? `<small class="said">${esc(sub)}</small>` : ''}</span><b>${v}</b></div>`;
  const put = h => { if (seq === FSEQ) $('#facts').innerHTML = h; };
  const said = `<p class="fine">Every figure here is the node’s answer: GET /geo/cell, /geo/measure.</p>`;
  try {
    if (PM.tool === 'measure') {
      const m = PM.measured && PM.measured.points === PM.measure.length && PM.measure.length > 1 ? PM.measured : null;
      put(`<div class="k">Measure</div><p class="big mono">${m ? fmtM(m.total_m) : '—'}</p>` + row('Points', PM.measure.length)
        + `<p class="fine">Click to add a point, double-click to finish, Esc to clear. The node measures the path, great-circle, leg by leg (GET /geo/measure).</p>`);
    } else if (o && o.kind === 'station') {
      const s = o.s, v = lastRaw(s.sensor_id, 'pm25');
      const head = `<div class="k">${s.local ? 'This house’s station' : 'Public station'}</div><h3 class="said">${esc(s.name || s.sensor_id)}</h3>` + row('Id', `<span class="said">${esc(s.sensor_id)}</span>`);
      put(head + row('From this node', '…'));
      const [d, c] = await Promise.all([fromNode(s.lon, s.lat), cellAt(s.lon, s.lat, r)]);
      put(head + row('From this node', fmtM(d))
        + row('PM2.5, last hour', v == null ? '<span class="gap">not heard</span>' : `${fmt(v, 1)} µg/m³ ${prov(s.local ? 'live' : 'partial')}`)
        + row('Cell at res ' + r, `<span class="mono">${c.id}</span>`)
        + `<p class="fine">${s.local ? 'In this node’s custody: it counts toward the cell.' : 'Display only: a public station never drives an alert or a report line here.'}</p>` + said);
    } else if (o && o.kind === 'model') {
      put(`<div class="k">Model points here</div>` + o.ss.map(x => row(x.name, prov('model'))).join('') + `<p class="fine">A model or a portal is partial whatever its quality: live means measured here.</p>`);
    } else if (o && o.kind === 'cell') {
      put(`<div class="k">Cell</div><p class="big mono">${esc(o.id)}</p>`);
      const c = await cellFacts(o.id);
      put(`<div class="k">Cell · res ${c.res}</div><p class="big mono">${c.id}</p>` + row('Area', area(c.area_m2)) + row('Edge', fmtM(c.edge_m))
        + (c.parent ? row('Parent', `<span class="mono">${c.parent}</span>`) : '')
        + row('This node’s cell?', c.is_node ? 'yes' : c.cells_from_node == null ? 'no' : `no · ${c.cells_from_node} cells away`)
        + (c.may_leave ? `<p class="fine">Coarse enough to leave the machine: the node may publish a cell at this resolution, never finer than 6 by radio.</p>` : '') + said);
    } else if (o && o.kind === 'lab') {
      const head = `<div class="k">Place to make</div><h3>${esc(o.s.name)}</h3>`;
      put(head + row('From this node', '…'));
      put(head + row('From this node', fmtM(await fromNode(o.s.lon, o.s.lat))) + `<p class="fine">From fablabs.io, a directory: shown, never counted.</p>`);
    } else {
      const sc = SCALES.find(([x]) => x === r), G = GRID && GRID.res === r ? GRID : null;
      const head = `<div class="k">In view · ${sc ? sc[1] : 'res ' + r}</div><p class="big mono">${G ? G.node : '—'}</p>`;
      const c = G ? await cellFacts(G.node) : null;
      put(head + row('Resolution', `${r}`, `about ${fmtM(G ? G.edge_m : EDGE(r))} to an edge`)
        + row('This node’s cell', c ? area(c.area_m2) : '<span class="gap">no node</span>')
        + row('Layers on', `${LAYERS.filter(l => PM.on[l.id]).length} of ${LAYERS.filter(l => !l.empty).length}`)
        + `<p class="fine">Scroll or press a scale: the grid follows the zoom, and the node draws it. Dotted cells are coarse enough to leave the machine. Click any cell, station or point to inspect it.</p>`);
    }
  } catch (e) { offline(e.message); put(`<div class="k">Inspect</div><p class="fine">The node did not answer: ${esc(e.message)}</p>`); }
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
  return `<span class="wind">wind ${Math.round(s)} km/h from ${COMPASS[Math.round(d / 22.5) % 16]} · ${F.times[h].slice(11, 16)} UTC${PM.windStep ? ` · +${PM.windStep} h` : ''}</span>`;
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
const ink = a => { const photo = (PM.on.imagery && PM.ground.imagery) || (PM.on.drone && PM.ground.drone && PM.map.getZoom() >= 13);
  return PM.theme === 'dark' || photo ? `rgba(249,245,242,${a})` : `rgba(23,23,23,${a})`; };
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
const DOTS = ['own', 'public', 'models', 'labs'];
let POP = null;
function popup(o) {
  if (POP) { POP.remove(); POP = null; }
  if (!o || o.kind === 'cell') return;
  let at, h;
  if (o.kind === 'station') {
    const s = o.s, v = lastRaw(s.sensor_id, 'pm25');
    at = [s.lon, s.lat];
    h = `<div class="k">${s.local ? 'This house’s station' : 'Public station · display only'}</div><b class="said">${esc(plain(s.name || s.sensor_id))}</b>`
      + `<span class="mono">${esc(s.source || '')}${s.indoor ? ' · inside' : ''}</span>`
      + `<span>${v == null ? '<span class="gap">not heard this hour</span>' : `PM2.5 ${fmt(v, 1)} µg/m³ ${prov(s.local ? 'live' : 'partial')}`}</span>`
      + `<a href="#data/${encodeURIComponent(s.sensor_id)}">Its readings in Data →</a>`;
  } else if (o.kind === 'model') {
    at = o.p;
    h = `<div class="k">Model points · ${o.ss.length}</div>` + o.ss.map(x => `<span class="said">${esc(x.name)}</span>`).join('')
      + `<span>${prov('model')} a model is partial, whatever its quality</span><a href="#data/models">The models in Data →</a>`;
  } else if (o.kind === 'lab') {
    at = [o.s.lon, o.s.lat];
    h = `<div class="k">Place to make</div><b>${esc(o.s.name)}</b><span class="mono">listed on fablabs.io · shown, never counted</span>`;
  }
  POP = new maplibregl.Popup({ closeButton: true, closeOnClick: false, offset: 12, maxWidth: '260px', className: 'pmpop' })
    .setLngLat(at).setHTML(h).addTo(PM.map);
  POP.on('close', () => { POP = null; });
}

/* ---------------------------------------------------------------- mount once; later calls re-skin */
async function placeMap() {
  const theme = document.documentElement.dataset.theme || 'light';
  if (PM.map) {
    if (theme !== PM.theme) { PM.theme = theme; PM.map.setStyle(style()); PM.map.once('styledata', () => { applyBase(); redraw(); }); }
    PM.map.resize(); chrome(); panel(); facts(); windSync(); return;
  }
  PM.theme = theme;
  /* The plan is the node's own GET /place/geojson, centred where the node stands. Only when the node has none is the
     design kit's copy drawn, and the layer row says it is 1.2 km off. */
  PM.meta = await ask('ground/meta').catch(() => null);
  PM.wind = await fetch(API + 'ground/wind', { headers: DOORS_AUTH() }).then(r => r.status === 200 ? r.json() : null).catch(() => null);
  PM.ground = (PM.meta && PM.meta.on_disk) || {};
  groundRows();
  const nodePlan = await ask('place/geojson').then(g => (g.features || []).length ? g : null).catch(() => null);
  PM.land = { type: 'FeatureCollection', features: [] }; PM.plan = nodePlan;
  if (!nodePlan && !PM.ground.vector && PM.meta) LAYERS.find(l => l.id === 'street').sub = 'the node sent no plan and holds no street map';
  const el = $('#map'); el.innerHTML = '';
  const map = PM.map = new maplibregl.Map({ container: el, style: style(), center: D.point, zoom: 13.6, minZoom: 5, maxZoom: 18.5,
    dragRotate: false, pitchWithRotate: false, touchPitch: false, maxPitch: 0, attributionControl: false, fadeDuration: 0, canvasContextAttributes: { preserveDrawingBuffer: true },
    /* the one guard that keeps the promise: nothing but this page's own origin is ever asked for a tile */
    transformRequest: url => (url.startsWith(location.origin + '/ground/') ? { url, headers: DOORS_AUTH() }
      : url.startsWith(location.origin) || url.startsWith('blob:') ? { url } : { url: 'data:,' }) });
  map.touchZoomRotate.disableRotation();
  map.addControl(new maplibregl.ScaleControl({ maxWidth: 110, unit: 'metric' }), 'bottom-left');
  PM.overlay = new deck.MapboxOverlay({ interleaved: true, layers: [], pickingRadius: 8,
    onHover: info => { PM.hoverDot = !!(info.object && DOTS.includes(info.layer.id)); },
    /* deck.gl owns the cursor in interleaved mode: a dot says it can be clicked, the measure tool keeps its cross */
    getCursor: ({ isDragging }) => isDragging ? 'grabbing' : PM.tool === 'measure' ? 'crosshair' : PM.hoverDot ? 'pointer' : 'grab',
    onClick: info => {
      if (PM.tool === 'measure') return;
      const o = info.object, id = info.layer && info.layer.id;
      PM.pick = !o ? null : (id === 'own' || id === 'public') ? { kind: 'station', s: o } : id === 'models' ? { kind: 'model', ss: o.ss, p: o.p }
        : id === 'labs' ? { kind: 'lab', s: o } : (id === 'grid' || id === 'grid-dot' || id === 'mine' || id === 'radio') ? { kind: 'cell', id: o.id } : null;
      popup(PM.pick); facts();
    } });
  map.addControl(PM.overlay);
  tools();
  WIND.cv = document.createElement('canvas'); WIND.cv.className = 'windcv'; WIND.cv.setAttribute('aria-hidden', 'true');
  WIND.ctx = WIND.cv.getContext('2d'); map.getContainer().appendChild(WIND.cv);
  map.on('movestart', () => { WIND.moving = true; if (WIND.ctx) WIND.ctx.clearRect(0, 0, WIND.w || 0, WIND.h || 0); });
  map.on('moveend', () => { WIND.moving = false; windResample(); windSync(); });
  map.on('resize', () => { windResample(); });
  map.on('load', () => {
    applyBase(); PM.res = resFor(map.getZoom()); redraw(); chrome(); panel(); facts(); status(null); loadGrid(); credits(); windResample(); windSync();
    ask('geo/rings?km=2,5,15').then(x => { RINGS = x.rings.map(g => ({ km: g.km, path: g.ring.map(([la, ln]) => [ln, la]) })); redraw(); }).catch(() => {});
    cellFacts(D.geometry.radio.mine).then(c => { RADIO = { id: c.id, path: loop(c.ring) }; redraw(); }).catch(() => {});
  });
  map.on('moveend', () => { const r = resFor(map.getZoom()); if (r !== PM.res) { PM.res = r; chrome(); } redraw(); panel(); status(PM.cursor); loadGrid(); });
  map.on('mousemove', e => { const ll = PM.cursor = [e.lngLat.lng, e.lngLat.lat]; status(ll); if (PM.tool === 'measure' && PM.measure.length) { PM.hover = ll; redraw(); } });
  map.on('mouseout', () => { PM.cursor = null; status(null); });
  map.on('click', e => {
    if (PM.tool !== 'measure') return;
    PM.measure.push([e.lngLat.lng, e.lngLat.lat]); redraw(); facts();
    if (PM.measure.length > 1) {
      const pts = PM.measure.slice();
      ask(`geo/measure?path=${pts.map(q => q.map(v => v.toFixed(6)).join(',')).join(';')}`)
        .then(m => { if (pts.length === PM.measure.length) { PM.measured = m; redraw(); facts(); } }).catch(e => offline(e.message));
    }
  });
  map.on('dblclick', e => { if (PM.tool !== 'measure') return; e.preventDefault(); PM.hover = null; PM.tool = 'inspect'; map.getCanvas().style.cursor = '';
    document.querySelectorAll('.tools button').forEach(b => b.classList.toggle('on', b.dataset.t === 'inspect')); redraw(); });
  document.addEventListener('keydown', e => { if (e.key === 'Escape' && PM.measure.length) { PM.measure = []; PM.measured = null; PM.hover = null; redraw(); facts(); } });
}
window.placeMap = placeMap; window.__PM = PM;   // for the rig
/* The same base for the doors' other maps (Now's "around this house"): the node's own street map and names when this
   screen may have them; without them only the land's colour, never a tile from anywhere else. */
window.groundBase = async theme => {
  if (!PM.meta) { PM.meta = await ask('ground/meta').catch(() => null); PM.ground = (PM.meta && PM.meta.on_disk) || {}; }
  PM.land = PM.land || { type: 'FeatureCollection', features: [] };
  const keep = PM.theme; PM.theme = theme; const s = style(), p = P(); PM.theme = keep;
  s.layers = s.layers.filter(l => !['imagery', 'drone', 'plan-sat'].includes(l.id));
  if (!PM.ground.vector) s.layers[0].paint['background-color'] = p.land;
  return { style: s, palette: p, street: !!PM.ground.vector };
};
window.groundRequest = url => (url.startsWith(location.origin + '/ground/') ? { url, headers: DOORS_AUTH() }
  : url.startsWith(location.origin) || url.startsWith('blob:') ? { url } : { url: 'data:,' });
})();
