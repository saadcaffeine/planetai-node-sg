'use strict';
/* The walk out from the house (SPEC_mobile §11.2), the phone page's middle: mobile.js loads MapLibre and this file
   when the walk nears the screen, so Now draws first. Five steps, house → street → ring → region → planet; the map
   flies out at each and draws that scale's cell heavy, the smaller ones faint inside it. Nothing here names an issue:
   the switch lists every issue /issues carries, in its order, and each issue is read at the scales it has. A scale
   with no reading stays in the walk and says so, so a pack's issue read only by a model starts at the region. */

const SCALES = [{ res: 10, k: 'room' }, { res: 9, k: 'yard' }, { res: 6, k: 'ring' }, { res: 3, k: 'region' }, { res: 1, k: null }];
const PLANET = { en: 'planet', id: 'planet', es: 'planeta' };
/* an issue's metric as a station spells it, where the two differ (heat is felt, a station reads the thermometer) */
const STATION_METRIC = { apparent: 'temp' }, SAID = { temp: 'the thermometer', apparent: 'feels-like' };

/* every issue with a reading at one scale or more, in the engine's order: pure, tests/test_doors.py runs it */
function walkOf(I) {
  return (I.order || Object.keys(I.issues)).map(k => [k, I.issues[k]]).filter(([, a]) => a && a.stack)
    .map(([k, a]) => ({ k, a, at: SCALES.slice(0, 4).map(s => (a.stack[s.k] && a.stack[s.k].value != null ? a.stack[s.k] : null)) }))
    .filter(w => w.at.some(Boolean));
}
if (typeof module !== 'undefined') module.exports = { walkOf };

if (typeof document !== 'undefined') (async () => {
  const $ = s => document.querySelector(s);
  const get = p => doorsFetch('/' + p).then(r => (r.ok ? r.json() : null)).catch(() => null);
  /* the walk reads what the phone page reads: whatever this node's SHARE_LEVEL answers, or everything with the token */
  const [I, D, H, N, M] = await Promise.all([get('issues'), get('issues/days?days=1'), get('health'), get('nodes'), get('ground/meta')]);
  /* refused: Now above already says why and offers the unlock */
  if (!I || !H) { $('#walk').remove(); return; }
  /* /ground and /geo/cell answer a phone with no token at SHARE_LEVEL=open; anywhere else the walk goes without the map */
  if (!M) $('#map').insertAdjacentHTML('afterend', '<p class="nomap">This node does not share its map with a phone that is not unlocked.</p>');
  const lang = 'en', L = (I.labels && I.labels[lang]) || {}, W = walkOf(I);
  const word = i => (SCALES[i].k ? L[SCALES[i].k] || SCALES[i].k : PLANET[lang]);
  const edge = r => (I.geometry.ladder.find(x => x.res === r) || {}).edge_m;
  const f = (v, dp) => (v == null ? '—' : (+v).toFixed(dp));
  /* the line as the doors draw it (.linep in doors.html) and name it (lineLab in doors-core.js): "WHO 15" for the air */
  const LINEP = 'stroke="var(--signal-worse)" stroke-width="1.5" stroke-dasharray="6 4"';
  const lineLab = a => `${/^WHO\b/.test(a.line.source || '') ? 'WHO' : 'line'} ${f(a.line.value, a.dp ?? 0)}`;
  /* the line's label beside a vertical line, turned to its left near the right edge so the drawing never clips it */
  const lineAt = (X, yy, a, Wd) => `<text x="${X > Wd - 80 ? X - 4 : X + 4}" y="${yy}" text-anchor="${X > Wd - 80 ? 'end' : 'start'}" style="fill:var(--ink)">${lineLab(a)}</text>`;
  let K = (W.find(x => x.k === location.hash.slice(1)) || W.find(x => x.k === (I.lead || {}).issue) || W[0] || {}).k, AT = 0;

  /* the 24 hours of one scale, from /issues/days; [] where the issue keeps no hours there */
  const hours = (k, d) => ((D && D.issues[k] && D.issues[k].series[d]) || []).slice(-24);

  /* one hue, ink: the series part by dash and weight, the house solid, the street dashed, the ring dotted and thinner */
  const STROKE = { solid: 'stroke-width="2"', dash: 'stroke-width="1.5" stroke-dasharray="4 2"', dot: 'stroke-width="1.25" stroke-dasharray="1 2.5" stroke-linecap="round"' };
  /* a: the issue whose line is drawn, or null for none */
  function chart(S, a, band) {
    const line = a ? a.line.value : null, Wd = 358, Hh = 120, P = 22, PR = 52, all = S.flatMap(s => s.v).concat(line == null ? [] : [line]).filter(v => v != null);
    if (!all.length) return '';
    const n = S[0].v.length, lo = Math.min(...all), hi = Math.max(...all), pad = (hi - lo || 1) * .08;
    const x = i => P + (Wd - P - PR) * i / (n - 1), y = v => Hh - 14 - (Hh - 28) * (v - lo + pad) / (hi - lo + pad * 2);
    const path = v => v.reduce((a, q, i) => (q == null ? a : a + (i && v[i - 1] != null ? 'L' : 'M') + `${x(i).toFixed(1)},${y(q).toFixed(1)}`), '');
    let g = '';
    if (band) { const [a, b] = band; for (let i = 0; i < n - 1; i++) {
      if ([a[i], b[i], a[i + 1], b[i + 1]].some(q => q == null)) continue;
      g += `<path d="M${x(i)},${y(a[i])}L${x(i + 1)},${y(a[i + 1])}L${x(i + 1)},${y(b[i + 1])}L${x(i)},${y(b[i])}Z" fill="var(--ink)" opacity=".08"/>`; } }
    if (line != null) g += `<line x1="${P}" x2="${Wd - PR}" y1="${y(line)}" y2="${y(line)}" ${LINEP}/><text x="${Wd - PR}" y="${y(line) - 4}" text-anchor="end" style="fill:var(--ink)">${lineLab(a)}</text>`;
    /* the end labels go a row apart when two series end close, so "house" and "street" never print as one word */
    const placed = [];
    S.forEach(s => { const li = s.v.length - 1; g += `<path d="${path(s.v)}" fill="none" stroke="var(--ink)" ${STROKE[s.d || 'solid']}/>`;
      if (s.v[li] == null) return;
      const ly0 = y(s.v[li]) + 4; let ly = ly0;
      for (let k = 1; placed.some(q => Math.abs(q - ly) < 12); k++) ly = ly0 + (k % 2 ? -12 : 12) * Math.ceil(k / 2);
      placed.push(ly);
      g += `<circle cx="${x(li)}" cy="${y(s.v[li])}" r="3.5" fill="var(${s.d ? '--ground' : '--ink'})" stroke="var(--ink)" stroke-width="1.5"/><text x="${x(li) + 6}" y="${ly}" style="fill:var(--ink)">${s.label}</text>`; });
    const B = (D && D.buckets.slice(-n)) || [];
    [0, 6, 12, 18].forEach(i => B[i] && (g += `<text x="${x(i)}" y="${Hh}" text-anchor="middle">${B[i].slice(11, 16)}</text>`));
    return `<svg class="g" viewBox="0 0 ${Wd} ${Hh + 4}" role="img" aria-label="the last 24 hours">${g}<text x="${x(n - 1)}" y="${Hh}" text-anchor="middle">now</text></svg>`;
  }

  /* every scale on one axis; the labels go one row each, so two close values never sit on each other */
  function ladder(w) {
    const Wd = 358, P = 16, rows = w.at.map((s, i) => s && { i, v: s.value }).filter(Boolean), line = w.a.line && w.a.line.value;
    const vs = rows.map(r => r.v).concat(line == null ? [] : [line]), lo = Math.min(...vs), hi = Math.max(...vs), pad = (hi - lo || 1) * .06;
    const x = v => P + (Wd - P * 2) * (v - lo + pad) / (hi - lo + pad * 2), dp = w.a.dp ?? 1;
    let g = `<line x1="${P}" x2="${Wd - P}" y1="20" y2="20" stroke="var(--hair)"/>`;
    if (line != null) g += `<line x1="${x(line)}" x2="${x(line)}" y1="6" y2="${28 + rows.length * 18}" ${LINEP}/>${lineAt(x(line), 10, w.a, Wd)}`;
    rows.sort((a, b) => a.v - b.v).forEach((r, j) => { const yy = 40 + j * 18, on = r.i === AT, X = x(r.v);
      g += `<circle cx="${X}" cy="20" r="${on ? 6 : 4}" fill="var(${on ? '--ink' : '--ground'})" stroke="var(--ink)"/><line x1="${X}" x2="${X}" y1="26" y2="${yy - 4}" stroke="var(--hair)"/>
        <text x="${X}" y="${yy}" text-anchor="${X > Wd - 100 ? 'end' : 'start'}" ${on ? 'style="fill:var(--ink)"' : ''}>${word(r.i)} ${f(r.v, dp)}</text>`; });
    return rows.length > 1 ? `<svg class="g ladder" viewBox="0 0 ${Wd} ${46 + rows.length * 18}">${g}</svg>` : '';
  }

  const metricOf = w => STATION_METRIC[w.a.metric] || w.a.metric;
  const outdoor = w => (I.stations || []).filter(s => !s.indoor && s.read && s.read[metricOf(w)] && s.lat != null);

  /* the stations around, each a dot on one axis, the house marked against them */
  function strip(w) {
    const st = outdoor(w), house = w.at[0] && w.at[0].value, line = w.a.metric === 'pm25' && w.a.line ? w.a.line.value : null;
    if (!st.length) return '';
    const Wd = 358, P = 16, vs = st.map(s => s.read[metricOf(w)].value).concat(house == null ? [] : [house], line == null ? [] : [line]);
    const lo = Math.min(...vs), hi = Math.max(...vs), pad = (hi - lo || 1) * .06, x = v => P + (Wd - P * 2) * (v - lo + pad) / (hi - lo + pad * 2);
    let g = `<line x1="${P}" x2="${Wd - P}" y1="24" y2="24" stroke="var(--hair)"/><text x="${P}" y="8">${f(lo, 0)}</text><text x="${Wd - P}" y="8" text-anchor="end">${f(hi, 0)}</text>`;
    st.forEach(s => (g += `<circle cx="${x(s.read[metricOf(w)].value)}" cy="24" r="4" fill="var(--ink)" opacity=".5"/>`));
    if (line != null) g += `<line x1="${x(line)}" x2="${x(line)}" y1="12" y2="36" ${LINEP}/>${lineAt(x(line), 20, w.a, Wd)}`;
    if (house != null) g += `<rect x="${x(house) - 1}" y="10" width="2" height="28" fill="var(--ink)"/><text x="${x(house)}" y="52" text-anchor="middle" style="fill:var(--ink)">${word(0)} ${f(house, w.a.dp ?? 1)}</text>`;
    const felt = metricOf(w) !== w.a.metric ? ` The stations read ${SAID[metricOf(w)] || metricOf(w)}; the ${word(0)} is ${SAID[w.a.metric] || w.a.metric}.` : '';
    return `<svg class="g" viewBox="0 0 ${Wd} 56">${g}</svg><p class="m">${st.length} outdoor stations, one dot each.${felt}</p>`;
  }

  function story() {
    const w = W.find(x => x.k === K), a = w.a, u = a.unit || '', dp = a.dp ?? 1, line = a.line && a.line.value;
    /* the line in every PM2.5 drawing (Tomas, 14 Oct); another issue's only in the house's own hours, as before */
    const ref = line != null ? a : null, pm = a.metric === 'pm25' ? ref : null;
    const [room, yard, ring] = ['room', 'yard', 'ring'].map(d => hours(K, d));
    const gap = w.at[0] && w.at[1] ? w.at[1].value - w.at[0].value : null;
    const pairs = room.map((v, i) => (v != null && yard[i] != null ? yard[i] - v : null)).filter(v => v != null);
    const nodes = (N && N.nodes) || [];
    const step = [
      { h: 'Inside the house', g: chart([{ v: room, label: word(0) }], ref), m: 'The last 24 hours.' },
      { h: 'Out on the street', p: gap == null ? '' : `The ${word(1)} reads ${f(Math.abs(gap), dp)} ${u} ${gap > 0 ? 'higher' : 'lower'} than the ${word(0)} now, and read higher in ${pairs.filter(v => v > 0).length} of the last ${pairs.length} hours.`,
        g: chart([{ v: yard, d: 'dash', label: word(1) }, { v: room, label: word(0) }], pm, [room, yard]),
        m: pairs.length ? `The ${word(1)} is the dashed line, the ${word(0)} the solid one; the shade is the gap between them.` : '' },
      { h: 'The ring around it', g: strip(w) + chart([{ v: ring, d: 'dot', label: word(2) }, { v: room, label: word(0) }], pm) },
      { h: 'The region', g: ladder(w), m: w.at.filter(Boolean).length < 2 ? '' : line != null ? 'Every scale on one line. The red dash is the line this house is held to.' : 'Every scale on one line.' },
      { h: 'The planet', p: `${nodes.length} node${nodes.length === 1 ? '' : 's'} listed in the programme${N && N.read ? `, the list read ${N.read.slice(0, 10)}` : ''}. Each reads its own house the same way, and none of them sends its rooms here.`,
        g: nodes.length ? '<p>' + nodes.map(x => `<b>${x.name}</b> · ${(x.place || '').split(',')[0]}`).join('<br>') + '</p>' : '', m: 'Not listed? <code>planetai hello</code>' }];
    $('#chs').innerHTML = step.map((t, i) => { const s = w.at[i], e = edge(SCALES[i].res);
      return `<div class="ch${i < 4 && !s ? ' unread' : ''}" data-i="${i}"><div class="k">${word(i)} · res ${SCALES[i].res}${e ? ` · ${Math.round(e * 2).toLocaleString('en')} <span class="unit">m</span> across` : ''}</div><h2>${t.h}</h2>`
        + (i < 4 ? (s ? `<div class="big">${f(s.value, dp)}<i>${u}</i></div><p>${s.source || ''}${s.provenance ? `, ${s.provenance}` : ''}.</p>` : `<span class="none">${(a.name && a.name[lang]) || K} is not read at the ${word(i)}</span>`) : '')
        + (t.p && (i > 3 || s) ? `<p>${t.p}</p>` : '') + (s || i > 3 ? t.g || '' : '') + (t.m && (s || i > 3) ? `<p class="m">${t.m}</p>` : '')
        + (i < 4 && caps[SCALES[i].res]
           ? `<button class="capcount" data-res="${SCALES[i].res}">${caps[SCALES[i].res].length} image${caps[SCALES[i].res].length === 1 ? '' : 's'} here</button><div class="capgrid" data-res="${SCALES[i].res}" hidden></div>`
           : '') + '</div>'; }).join('');
    /* the rail says where the reader is; it is read, not pressed (a 44 px target per scale would cover the map) */
    $('#rail').innerHTML = SCALES.map((s, i) => `<span><s></s>${word(i)}<em>${i < 4 ? f(w.at[i] && w.at[i].value, dp) : ''}</em></span>`).join('');
    document.querySelectorAll('.ch').forEach(c => io.observe(c));
    lit();
  }
  const lit = () => $('#rail').querySelectorAll('span').forEach((el, i) => el.classList.toggle('on', i === AT));
  const stationsGeo = () => { const w = W.find(x => x.k === K), m = metricOf(w);
    return { type: 'FeatureCollection', features: outdoor(w).filter(s => (s.km || 0) > 0.5)
      .map(s => ({ type: 'Feature', properties: { t: f(s.read[m].value, 0) }, geometry: { type: 'Point', coordinates: [s.lon, s.lat] } })) }; };

  const lat0 = 156543.03 * Math.cos(H.lat * Math.PI / 180);
  /* zero motion under prefers-reduced-motion: essential:true would otherwise fly anyway */
  const FLY = typeof matchMedia === 'function' && matchMedia('(prefers-reduced-motion: reduce)').matches ? 0 : 1400;
  function go(i) {
    AT = i; lit();
    const res = SCALES[i].res, w = W.find(x => x.k === K);
    map.setProjection({ type: i === 4 ? 'globe' : 'mercator' });
    map.setPaintProperty('cells', 'line-width', ['case', ['==', ['get', 'res'], res], 3, 1]);
    map.setPaintProperty('cells', 'line-opacity', ['case', ['==', ['get', 'res'], res], 1, 0.45]);
    map.setLayoutProperty('st', 'visibility', i === 2 || i === 3 ? 'visible' : 'none');
    if (map.getLayer('stt')) map.setLayoutProperty('stt', 'visibility', i === 2 ? 'visible' : 'none');
    map.setLayoutProperty('nd', 'visibility', i === 4 ? 'visible' : 'none');
    /* frame the scale's own cell, clear of the bar on top and the rail at the foot; the planet is the globe */
    const c = cells.find(x => x.properties.res === res);
    if (i === 4 || !c) map.flyTo({ center: [H.lon, H.lat], zoom: i === 4 ? 0.9 : Math.min(18.5, Math.log2(170 * lat0 / (edge(res) * 2))), duration: FLY, essential: true });
    else map.fitBounds(c.geometry.coordinates.reduce((b, p) => b.extend(p), new maplibregl.LngLatBounds(c.geometry.coordinates[0], c.geometry.coordinates[0])),
      { padding: { top: 70, bottom: 24, left: 24, right: 24 }, duration: FLY, essential: true });
    const l = document.querySelector('.ch[data-i="3"] .ladder'); if (l) l.outerHTML = ladder(w);
  }
  /* the step is the chapter crossing the band just under the 58vh map, the one being read; .ch's scroll-margin lands a jump there */
  const under = (($('.bar') || {}).offsetHeight || 0) + $('#top').offsetHeight + 8;
  const io = new IntersectionObserver(es => es.forEach(e => e.isIntersecting && +e.target.dataset.i !== AT && go(+e.target.dataset.i)),
    { rootMargin: `-${under}px 0px -${Math.max(0, innerHeight - under - 30)}px 0px` });

  if (!W.length) { $('#chs').innerHTML = '<p class="locked">No issue has a reading yet.</p>'; return; }
  $('#tg').innerHTML = W.map(w => `<button data-k="${w.k}" aria-pressed="${w.k === K}">${(w.a.name && w.a.name[lang]) || w.k}</button>`).join('');
  /* one issue for the page: the switch here, or a row in Now (window.WALK_ISSUE), which stays where it is */
  const pick = (k, jump) => { if (!W.some(x => x.k === k)) return; K = k;
    $('#tg').querySelectorAll('button').forEach(x => x.setAttribute('aria-pressed', x.dataset.k === k));
    map.getSource('st').setData(stationsGeo()); story(); start(jump); };
  $('#tg').querySelectorAll('button').forEach(b => (b.onclick = () => pick(b.dataset.k, true)));
  window.WALK_ISSUE = k => pick(k, false);
  /* a scale's count opens its grid; the pictures fetch as blobs, because an <img> cannot carry the token */
  document.addEventListener('click', async ev => {
    const b = ev.target.closest && ev.target.closest('.capcount'); if (!b) return;
    const grid = document.querySelector(`.capgrid[data-res="${b.dataset.res}"]`); if (!grid) return;
    if (!grid.hidden) { grid.hidden = true; return; }
    grid.hidden = false;
    if (grid.dataset.loaded) return; grid.dataset.loaded = '1'; grid.innerHTML = '';
    for (const c of (caps[+b.dataset.res] || []).slice(0, 12)) {
      const blob = await doorsFetch(`/captures/${c.id}/file`).then(r => (r.ok ? r.blob() : null)).catch(() => null);
      if (!blob) continue;
      const img = document.createElement('img');
      img.src = URL.createObjectURL(blob); img.alt = c.note || c.kind || 'a capture'; img.loading = 'lazy';
      grid.appendChild(img);
    }
    if (!grid.children.length) { grid.innerHTML = '<p class="m">The images answer a screen with a token only.</p>'; delete grid.dataset.loaded; }
  });

  /* the cell this node stands in, at each scale, from the node's own /geo/cell (R25: centres only, never the house) */
  const cells = (await Promise.all(SCALES.slice(0, 4).map(s => get(`geo/cell?lat=${H.lat}&lon=${H.lon}&res=${s.res}`)))).filter(c => c && c.ring)
    .map(c => { const q = []; for (let k = 1; k < c.ring.length; k += 2) q.push([c.ring[k + 1], c.ring[k]]); q.push(q[0]);
      return { type: 'Feature', properties: { res: c.res, id: c.id }, geometry: { type: 'LineString', coordinates: q } }; });
  /* the pictures the household kept (SPEC_eyes step 1): a count inside each scale's cell, token only — a locked
     phone's 403 answers null and the walk says nothing, the same silence the map keeps */
  const caps = {};
  for (const c of cells) { const rows = await get(`captures?cell=${encodeURIComponent(c.properties.id)}&limit=200`); if (rows && rows.length) caps[c.properties.res] = rows; }
  const V = M && M.layers && M.layers.vector, DR = M && M.layers && M.layers.drone, here = location.origin;
  /* the map in each register, as literals (MapLibre reads no CSS variable): paper is the phone's own, dark the doors'
     (doors-placemap.js PAL.dark); ink and paper are the layer's. The switch in the foot sets data-theme; the map follows */
  const PAL = { light: { bg: '#dfe6ea', earth: '#f3efe8', roads: '#cfc8bb', bld: '#e4ded3', label: '#5F5A54', halo: '#f3efe8', ink: '#171717', paper: '#F9F5F2', cell: '#20388D' },
    dark: { bg: '#0E1012', earth: '#17191D', roads: '#30353D', bld: '#2B2E34', label: '#A3A19F', halo: '#17191D', ink: '#F9F5F2', paper: '#171717', cell: '#7FA5E8' } };   /* cell: the layer's blue, one per register */
  const pal = () => PAL[document.documentElement && document.documentElement.dataset.theme === 'dark' ? 'dark' : 'light'], p = pal();
  const PAINT = [['bg', 'background-color', 'bg'], ['earth', 'fill-color', 'earth'], ['water', 'fill-color', 'bg'], ['roads', 'line-color', 'roads'],
    ['bld', 'fill-color', 'bld'], ['pl', 'text-color', 'label'], ['pl', 'text-halo-color', 'halo'], ['cells', 'line-color', 'cell'], ['st', 'circle-color', 'ink'],
    ['st', 'circle-stroke-color', 'paper'], ['stt', 'text-color', 'paper'], ['nd', 'circle-color', 'ink'], ['nd', 'circle-stroke-color', 'paper']];
  const map = new maplibregl.Map({ container: 'map', attributionControl: { compact: false }, center: [H.lon, H.lat], zoom: 18, interactive: false,
    transformRequest: url => (url.startsWith(here + '/ground/') ? { url, headers: DOORS_AUTH() } : { url }),
    style: { version: 8, ...(V && V.fonts ? { glyphs: here + '/ground/glyphs/{fontstack}/{range}.pbf' } : {}), sources: {
      ...(V ? { v: { type: 'vector', tiles: [here + '/ground/vector/{z}/{x}/{y}.pbf'], maxzoom: V.maxzoom || 15, attribution: '© OpenStreetMap' } } : {}),
      ...(DR ? { drone: { type: 'raster', tiles: [here + '/ground/drone/{z}/{x}/{y}.png'], tileSize: 256, minzoom: 14, maxzoom: 18, attribution: 'OpenAerialMap CC BY' } } : {}),
      cells: { type: 'geojson', data: { type: 'FeatureCollection', features: cells } },
      st: { type: 'geojson', data: { type: 'FeatureCollection', features: [] } },
      nd: { type: 'geojson', data: { type: 'FeatureCollection', features: ((N && N.nodes) || []).filter(x => x.ll).map(x => ({ type: 'Feature', properties: {}, geometry: { type: 'Point', coordinates: x.ll } })) } } },
    layers: [{ id: 'bg', type: 'background', paint: { 'background-color': p.bg } },
      ...(V ? [{ id: 'earth', type: 'fill', source: 'v', 'source-layer': 'earth', paint: { 'fill-color': p.earth } },
        { id: 'water', type: 'fill', source: 'v', 'source-layer': 'water', paint: { 'fill-color': p.bg } },
        { id: 'roads', type: 'line', source: 'v', 'source-layer': 'roads', paint: { 'line-color': p.roads, 'line-width': 1 } },
        { id: 'bld', type: 'fill', source: 'v', 'source-layer': 'buildings', paint: { 'fill-color': p.bld } }] : []),
      ...(DR ? [{ id: 'drone', type: 'raster', source: 'drone', paint: { 'raster-opacity': ['interpolate', ['linear'], ['zoom'], 14.5, 0, 15.5, 1] } }] : []),
      ...(V && V.fonts ? [{ id: 'pl', type: 'symbol', source: 'v', 'source-layer': 'places', filter: ['has', 'name'],
        layout: { 'text-field': ['get', 'name'], 'text-font': ['Noto Sans Medium'], 'text-size': 12 }, paint: { 'text-color': p.label, 'text-halo-color': p.halo, 'text-halo-width': 1.4 } }] : []),
      { id: 'cells', type: 'line', source: 'cells', paint: { 'line-color': p.cell, 'line-width': 1 } },
      /* a station is one fixed sign, ink on a paper edge: the same size near or far */
      { id: 'st', type: 'circle', source: 'st', paint: { 'circle-radius': 11, 'circle-color': p.ink, 'circle-opacity': 0.85, 'circle-stroke-color': p.paper, 'circle-stroke-width': 1 } },
      ...(V && V.fonts ? [{ id: 'stt', type: 'symbol', source: 'st', layout: { 'text-field': ['get', 't'], 'text-size': 12, 'text-font': ['Noto Sans Regular'] }, paint: { 'text-color': p.paper } }] : []),
      { id: 'nd', type: 'circle', source: 'nd', paint: { 'circle-radius': 6, 'circle-color': p.ink, 'circle-stroke-color': p.paper, 'circle-stroke-width': 2 } }] } });
  const repaint = () => { const q = pal(); PAINT.forEach(([id, k, c]) => map.getLayer(id) && map.setPaintProperty(id, k, q[c])); };
  if (typeof MutationObserver === 'function') new MutationObserver(repaint).observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });
  /* an issue not read at the house starts where it is first read (land and coast: the region) */
  const start = jump => { const i = Math.max(0, W.find(x => x.k === K).at.findIndex(Boolean));
    if (jump) document.querySelectorAll('.ch')[i].scrollIntoView(); go(i); };
  map.on('load', () => { map.getSource('st').setData(stationsGeo()); story(); start(false); window.WALK_READY = true; });
  window.WALK_GO = i => go(i);
})();
