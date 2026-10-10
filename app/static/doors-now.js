'use strict';
/* NOW — the moment, its decision, who reads around the house (the ledger is Data's, Tomas 7 Oct). Married to the node's rules:
   every part is one of the four card kinds (data-kind), names its learn mark, the routes it reads and its stage;
   every figure carries its comparison; the node's words are never shouted; provenance is a pill in ink.
   The first thing is the ladder, and under it the lead (learn: lead). */
VIEWS.now = function () {
  rail($('#rail')); rows(); drawNow();
  aroundMap($('#rose'));
};
function drawNow() {
  dayWeek({ el: $('#svg'), issue: S.issue, head: $('#fighead'), scale: $('#figline'), pick: j => { S.i = j; drawNow(); } });
  readout();
}

/* The ladder, compact: rungs res 2 to 12, this node's rung filled; the node's own rule for the rest — rungs that may
   leave the machine dotted, rungs finer than the node says where it is struck through (design.md, Colour). */
function rail(el) {
  const G = D.geometry.grain, L = D.geometry.ladder.filter(l => l.res >= 2 && l.res <= 12);
  el.innerHTML = L.map(l => { const g = G.find(x => x.res === l.res) || {};
    return `<span class="rung ${l.res === 8 ? 'on' : ''} ${g.may_leave ? 'leave' : ''} ${g.finer_than_published ? 'finer' : ''}" title="res ${l.res}, about ${l.edge_m >= 1000 ? fmt(l.edge_m / 1000, 1) + ' km' : l.edge_m + ' m'} a side">${l.res}</span>`; }).join('')
    + `<a href="#place" class="mono">${D.health.cell.edge_m} m · ${fmt(D.geometry.ladder.find(l => l.res === D.health.cell.res).own_area_m2 / 1e6, 2)} km² ›</a>`;
}

function readout() {
  const k = S.issue, it = D.issues[k], i = S.i, b = D.buckets[i], dp = it.dp, U = it.unit, isNow = i === D.now;
  const w = (it.provenance || {})[it.hero_distance] || 'model';
  $('#kick').innerHTML = `${said(it.name)} · ${isNow ? 'now' : dLabel(dayOf(b))} · at ${hhmm(b)} ${prov(w)} <span class="x">${isNow ? '· the node’s own sentence' : `· ${D.now - i} h before the capture`}</span>`;
  $('#back').hidden = isNow;
  const v = val(k, it.hero_distance, i), over = it.line != null && v != null && v > it.line;
  const cmp = it.line != null ? `against the line, ${fmt(it.line, dp)} ${U}` : 'this issue has no line';
  const n = x => num(`${k}.${it.hero_distance}`, x, cmp, `<b class="numf">${esc(x)}</b>`);
  let s, tag = '';
  if (isNow) {
    /* the split, same as the wall's: the title is the sentence's qualitative head — no number, no
       indicator — and the tagline explains it, smaller and not bold. Older nodes send no title:
       the sentence stands in, its first figure marked as before. */
    s = esc(it.title || it.sentence).replace(/(\d+(?:\.\d+)?)(?=\s*(?:°C|µg|%|m\b))/, (m0) => n(m0));
    tag = it.tagline || '';
  }
  else if (v == null) s = `<span class="gone">Nothing was recorded in the house at ${hhmm(b)}.</span>`;
  else {
    /* a past hour has no trend verb, so the qualitative head is the line relation — was it over or
       under — and the reading moves to the tagline: first what it meant, then what it measured. */
    s = (k === 'heat' ? 'In the house it was' : 'The air in the house was') + ` ${over ? 'over' : 'under'} the line.`;
    tag = (k === 'heat' ? `At ${hhmm(b)} it felt like` : `At ${hhmm(b)} it read`) + ` ${fmt(v, dp)} ${U}.`;
  }
  $('#sentence').innerHTML = (it.pix ? `<svg class="pix" aria-hidden="true"><use href="${NODE}signs.svg#${it.pix}"/></svg>` : '') + `<span class="said">${s}${tag ? `<span class="ntag">${esc(tag)}</span>` : ''}</span>`;
  $('#ladder').innerHTML = ['room', 'yard', 'ring', 'region'].map(dk => {
    const x = isNow ? (it.stack[dk] || {}).value : val(k, dk, i);
    const pw = (it.provenance || {})[dk] || ((it.stack[dk] || {}).provenance), hourly = (it.series || {})[dk];
    return `<div class="col ${x == null ? 'none' : ''}"><div class="k">${said(D.labels[dk])}</div>`
      + `<div class="v">${x == null ? '—' : num(`${k}.${dk}`, fmt(x, dp), cmp)}${x == null ? '' : `<small>${said(U)}</small>`}</div>`
      + (x == null ? `<span class="gap">${hourly ? 'not recorded' : (isNow ? 'none' : 'no hours here')}</span>` : prov(pw)) + `</div>`;
  }).join('');
  decision(); rowsValues();
}

/* The decision of the moment: Decide's card, condensed (learn: buttons). The three answers are the node's own words. */
function decision() {
  const k = S.issue, it = D.issues[k], evs = evAt(k, S.i), B = D.buttons;
  if (!evs.length) {
    $('#decide').innerHTML = `<div class="k">decide · nothing is asked at this hour</div><p class="dq">No event was open for ${said(it.name.toLowerCase())}.</p>`
      + `<p class="dm">${it.line != null ? `the line ${fmt(it.line, it.dp)} ${said(it.unit)} · ${said(it.line_source || '')}` : 'this issue has no line: it informs, it never asks'}</p>`;
    return;
  }
  const e = evs[0], a = answerWords(e.answer), on = { acted: 'done', acknowledged: 'not_now', dismissed: 'doesnt_fit' }[(e.answer || {}).stage];
  /* an answer is taken only for an event still open, at the live hour: a past hour is read, never answered */
  const live = S.i === D.now && !e.cleared_at;
  $('#decide').innerHTML = `<div class="k">decide · ${said(it.name)} · ${esc(e.kind)} since ${hhmm(e.opened_at)}${e.cleared_at ? ` · cleared ${hhmm(e.cleared_at)}` : ' · still open'}`
    + `${e.peak != null ? ` · peak ${num(`${k}.event.peak`, fmt(e.peak, it.dp), `the line ${fmt(it.line, it.dp)} ${it.unit}`)} ${said(it.unit)}` : ''}</div>`
    + `<p class="dq">${said(e.action || 'The node asked for nothing specific.')}</p>`
    + `<div class="ans" role="group" aria-label="Answer">${['done', 'not_now', 'doesnt_fit'].map(b => `<button class="${on === b ? 'on' : ''}" data-ev="${e.id}" data-stage="${ANSWER_STAGE[b]}" ${live ? '' : 'disabled title="this event is not open at this hour"'}>${said(B[b])}</button>`).join('')}</div><p class="dm" id="answered" role="status"></p>`
    + `<p class="dm">${sign(a.closed ? 'sign-rho-closed' : 'sign-rho-open', a.closed ? 'closed' : '')} ${esc(a.w)}${(e.rooms || []).length ? ` · ${e.rooms.length} room${e.rooms.length === 1 ? '' : 's'}: ${said(e.rooms.map(r => r.trim()).join(', '))}` : ''}</p>`;
}

/* Done, Not now, Doesn't fit: POST /actions with the event's id, the same write the dashboard makes (answerEvent).
   The node takes it from this machine, or with the act or admin token; its own sentence is printed when it refuses. */
const ANSWER_STAGE = { done: 'acted', not_now: 'acknowledged', doesnt_fit: 'dismissed' };
document.addEventListener('click', async ev => {
  const b = ev.target.closest && ev.target.closest('#decide .ans button[data-ev]');
  if (!b || b.disabled) return;
  const out = $('#answered'); b.disabled = true;
  let actor = ''; try { actor = localStorage.getItem('planetai_actor') || ''; } catch (e) { /* no storage here */ }
  try {
    const r = await fetch('/actions', { method: 'POST', headers: { 'content-type': 'application/json', ...DOORS_AUTH() },
      body: JSON.stringify({ event_id: Number(b.dataset.ev), stage: b.dataset.stage, actor, note: '' }) });
    const said_ = r.ok ? '' : ((await r.json().catch(() => ({}))).detail || `the node refused it (${r.status})`);
    if (!r.ok) { out.textContent = r.status === 401 || r.status === 403 ? `${said_} · unlock this screen under Node with the act token.` : said_; b.disabled = false; return; }
    out.textContent = b.dataset.stage === 'acknowledged' ? 'Not now. The node holds this for three hours, unless it reaches danger.' : 'Recorded.';
    D = await loadD().then(d => Object.assign(d, { learn: D.learn, dates: D.dates, at: D.at, now: D.now, sens: D.sens, ngeo: D.ngeo })); VIEWS.now();
  } catch (e) { out.textContent = `The node did not answer: ${e.message}`; b.disabled = false; }
});

function rows() {
  $('#rows').innerHTML = D.order.map(k => {
    const it = D.issues[k], drawn = ISSUES_DRAWN(k);
    return `<button class="row" data-k="${k}" data-kind="readout" ${drawn ? '' : 'disabled'} aria-pressed="false"><span><span class="n">${said(it.name)}</span><span class="state ${it.state === 'act' ? 'act' : ''}">${esc(it.state)}</span></span>`
      + `<span class="v" data-v></span><span class="sub" data-s></span></button>`;
  }).join('');
  document.querySelectorAll('#rows .row:not([disabled])').forEach(b => b.onclick = () => { S.issue = b.dataset.k; drawNow(); });
}
function rowsValues() {
  const date = dayOf(D.buckets[S.i]);
  document.querySelectorAll('#rows .row').forEach(r => {
    const k = r.dataset.k, it = D.issues[k];
    r.setAttribute('aria-pressed', String(k === S.issue));
    if (!ISSUES_DRAWN(k)) {
      const g = it.stack.region || {};
      r.querySelector('[data-v]').innerHTML = `${num(`${k}.region`, fmt(g.value, 1), 'no line: it informs, it never asks')}<small>${said(it.unit)}</small>`;
      r.querySelector('[data-s]').innerHTML = `region only ${prov(g.provenance || 'model')} changes yearly, no hours`;
      return;
    }
    const v = val(k, it.hero_distance, S.i), pd = (it.per_day || []).find(p => p.date === date);
    r.querySelector('[data-v]').innerHTML = `${num(`${k}.${it.hero_distance}`, fmt(v, it.dp), `against the line, ${fmt(it.line, it.dp)} ${it.unit}`)}<small>${said(it.unit)}</small>`;
    r.querySelector('[data-s]').innerHTML = pd ? `${pd.over ? '<span class="over" aria-hidden="true"></span>' : ''}${num(`${k}.over.day`, pd.over, `of ${pd.read} hours read, ${pd.of - pd.read} not recorded`)} h over the line ${date === dayOf(D.buckets[D.now]) ? 'today' : 'on ' + dLabel(date).split(',')[0]} · ${pd.read} of ${pd.of} h read` : 'no count for this day';
  });
}

/* Who reads around this house, now, on the node's own street map (MapLibre for the base, deck.gl for the stations,
   as on Place). Each station at the point /sensors gives this screen, its 15-minute mean beside it (GET /stats, as the
   wall reads it); the house's own sensors as one dot at the node's point with their range. Over the air line, a red
   square. A station pressed opens it in Data. Without WebGL it falls back to the rose. */
let NOWMAP = null;
async function aroundMap(el) {
  const theme = document.documentElement.dataset.theme || 'light', W = Math.min(360, el.parentNode.clientWidth), H = Math.round(W * 1.05);
  if (!window.maplibregl || !window.deck || !window.groundBase) return rose(el, { size: W });
  const M = 'pm25', line = (D.issues.air || {}).line, now15 = id => ((D.stats15[id] || {})[M] || [])[0] ?? null;
  const all = D.sensors.filter(s => s.lat != null && s.lon != null && s.source !== 'openstreetmap');
  const house = all.filter(s => s.local && s.kind === 'sensor'), hv = house.map(s => now15(s.sensor_id)).filter(v => v != null);
  const out = all.filter(s => !s.local && (s.kind === 'sensor' || s.kind === 'facility'))
    .map(s => ({ ...s, p: [s.lon, s.lat], v: s.kind === 'sensor' ? now15(s.sensor_id) : null }));
  const sea = all.find(s => s.sensor_id === 'marine-point'), C = (k, a = 1) => rgba(k, a);
  const quiet = out.filter(s => s.kind === 'sensor' && s.v == null).length, fac = out.filter(s => s.kind === 'facility').map(s => s.name.trim());
  const base = await window.groundBase(theme);
  if (!NOWMAP || NOWMAP.theme !== theme || !el.contains(NOWMAP.map.getContainer())) {
    if (NOWMAP) NOWMAP.map.remove();
    el.innerHTML = `<div class="aroundmap" style="width:${W}px;height:${H}px"></div>`;
    let map; try { map = new maplibregl.Map({ container: el.firstChild, style: base.style, center: D.point, zoom: 11, attributionControl: false,
      dragRotate: false, pitchWithRotate: false, touchPitch: false, scrollZoom: false, fadeDuration: 0, transformRequest: window.groundRequest }); } catch (e) { NOWMAP = null; return rose(el, { size: W }); }   /* no WebGL: the rose */
    map.touchZoomRotate.disableRotation();
    /* the stations are what this map is for: the base's names step back, and the street names go */
    map.on('load', () => { if (map.getLayer('v-place-label')) map.setPaintProperty('v-place-label', 'text-opacity', .5);
      for (const l of ['v-road-label', 'v-poi-label']) if (map.getLayer(l)) map.setLayoutProperty(l, 'visibility', 'none'); });
    map.addControl(new maplibregl.ScaleControl({ maxWidth: 80, unit: 'metric' }), 'bottom-left');
    const ov = new deck.MapboxOverlay({ interleaved: true, layers: [], pickingRadius: 6,
      getCursor: ({ isDragging, isHovering }) => isDragging ? 'grabbing' : isHovering ? 'pointer' : 'grab',
      onClick: i => { if (i.object && i.object.sensor_id) location.hash = 'data/' + encodeURIComponent(i.object.sensor_id); } });
    map.addControl(ov);
    const b = new maplibregl.LngLatBounds(D.point, D.point); out.forEach(s => b.extend(s.p)); if (sea) b.extend([sea.lon, sea.lat]);
    map.fitBounds(b, { padding: 26, duration: 0, maxZoom: 14 });
    NOWMAP = { map, ov, theme, geo: [] };
    /* the rose's rings and the cells, now on the map: the node's own answers (GET /geo/rings, /geo/grid), token-only
       because together they place it. The grid is resolution 7 (about 1.2 km to an edge) over what the map shows;
       the node's own res-8 cell is the one drawn solid. */
    map.once('idle', async () => {
      const ask = q => fetch('/' + q, { headers: DOORS_AUTH() }).then(r => r.ok ? r.json() : null).catch(() => null);
      const bx = map.getBounds(), box = [bx.getWest(), bx.getSouth(), bx.getEast(), bx.getNorth()].map(v => v.toFixed(5)).join(',');
      const [rg, gr] = await Promise.all([ask('geo/rings?km=0.5,2,5,15'), ask(`geo/grid?res=7&bbox=${box}`)]);
      const loopLL = row => { const r = []; for (let i = 1; i < row.length; i += 2) r.push([row[i + 1], row[i]]); r.push(r[0]); return r; };
      const rings = rg ? rg.rings.map(g => ({ km: g.km, path: g.ring.map(([la, ln]) => [ln, la]) })) : [];
      const dash = new deck.PathStyleExtension({ dash: true }), mono = 'JetBrains Mono, monospace', px = { widthUnits: 'pixels', widthMinPixels: 1 };
      NOWMAP.geo = [
        ...(gr ? [new deck.PathLayer({ id: 'grid', data: gr.cells_ll.map(loopLL), getPath: d => d, getColor: rgba('--cells', .18), getWidth: 1, ...px })] : []),
        ...(D.ngeo ? [new deck.PolygonLayer({ id: 'cell8', data: [loopLL(D.ngeo.c8.ring)], getPolygon: d => d, getFillColor: rgba('--cells', .14), getLineColor: rgba('--cells'), lineWidthUnits: 'pixels', getLineWidth: 2 })] : []),
        new deck.PathLayer({ id: 'rings', data: rings, getPath: d => d.path, getColor: rgba('--ink', .45), getWidth: 1, ...px, extensions: [dash], getDashArray: d => d.km < 1 ? [2, 3] : [4, 4] }),
        new deck.TextLayer({ id: 'rings-l', data: rings, characterSet: 'auto', getPosition: d => d.path.reduce((a, q) => q[1] > a[1] ? q : a), getText: d => `${d.km} km`,
          getSize: 10.5, fontFamily: mono, getColor: rgba('--mute'), getTextAnchor: 'middle', getAlignmentBaseline: 'bottom', getPixelOffset: [0, -3],
          background: true, getBackgroundColor: rgba('--ground', .8), backgroundPadding: [3, 1] }),
      ];
      NOWMAP.cells = !!gr; NOWMAP.paint && NOWMAP.paint();
    });
  }
  const mono = 'JetBrains Mono, monospace', ink = C('--ink'), ground = C('--ground');
  NOWMAP.paint = () => NOWMAP.ov.setProps({ layers: [...NOWMAP.geo,
    new deck.ScatterplotLayer({ id: 'pub', data: out.filter(s => s.kind === 'sensor'), getPosition: d => d.p, radiusUnits: 'pixels', getRadius: 4.5,
      stroked: true, filled: true, getFillColor: ground, getLineColor: d => d.v == null ? C('--ink', .4) : ink, lineWidthUnits: 'pixels', getLineWidth: 1.5, pickable: true }),
    new deck.TextLayer({ id: 'fac', data: out.filter(s => s.kind === 'facility'), characterSet: 'auto', getPosition: d => d.p, getText: () => '◇', getSize: 15, getColor: ink, pickable: true }),
    new deck.ScatterplotLayer({ id: 'over', data: out.filter(s => line != null && s.v != null && s.v > line), getPosition: d => d.p, radiusUnits: 'pixels', getRadius: 2.5,
      getFillColor: C('--signal-worse'), getPixelOffset: [9, -6] }),
    new deck.TextLayer({ id: 'pub-v', data: out.filter(s => s.v != null), characterSet: 'auto', getPosition: d => d.p, getText: d => fmt(d.v, 0), getSize: 11.5,
      fontFamily: mono, getColor: ink, getTextAnchor: 'start', getAlignmentBaseline: 'center', getPixelOffset: [8, 0],
      background: true, getBackgroundColor: C('--ground', .78), backgroundPadding: [2, 0],
      fontWeight: 600 }),
    ...(sea ? [new deck.TextLayer({ id: 'sea', data: [sea], characterSet: 'auto', getPosition: d => [d.lon, d.lat], getText: () => '□ sea model', getSize: 11, fontFamily: mono, getColor: C('--mute'), getTextAnchor: 'start' })] : []),
    new deck.ScatterplotLayer({ id: 'house', data: [{ p: D.point }], getPosition: d => d.p, radiusUnits: 'pixels', getRadius: 6.5, getFillColor: ink, stroked: true, getLineColor: ground, lineWidthUnits: 'pixels', getLineWidth: 2 }),
    new deck.TextLayer({ id: 'house-l', data: [{ p: D.point }], characterSet: 'auto', getPosition: d => d.p, getPixelOffset: [0, 17], getTextAnchor: 'middle', getSize: 11, fontFamily: mono, getColor: ink,
      background: true, getBackgroundColor: C('--ground', .92), backgroundPadding: [3, 1],
      getText: () => `this house · ${house.length}${hv.length ? ` · ${fmt(d3.min(hv), 0)}–${fmt(d3.max(hv), 0)} ${unitOf(M)}` : ''}` }),
  ] });
  NOWMAP.paint();
  $('#rosecap').innerHTML = `${said(labelOf(M))}, the 15-minute mean, at ${out.filter(s => s.v != null).length} public stations and ${house.length} in this house; `
    + `${quiet} not heard in the last 15 minutes drawn faint. ${fac.length ? `The diamond${fac.length > 1 ? 's are' : ' is'} ${said(fac.join(', '))}. ` : ''}Press a station to open it in Data. `
    + (base.street ? 'Rings at 0.5, 2, 5 and 15 km and the resolution-7 cells are the node’s; the solid cell is its own. The street map is this node’s own, OpenStreetMap contributors · Protomaps.'
      : 'The node’s street map, its rings and its cells are token-only: unlock this screen under Node to draw them under the stations.');
}

/* Who reads around this house, now — a stack: one quantity at many distances, on one scale. True bearings; distance on
   a square-root scale to 16 km. The value is each station's 15-minute mean, as the wall reads it. */
function rose(el, o) {
  const big = !!o.big, W = o.size, H = W, cx = W / 2, cy = H / 2, R = W / 2 - (big ? 34 : 22), MAXK = 16, M = o.metric || 'pm25';
  const r = d => Math.sqrt(Math.min(d, MAXK) / MAXK) * R, P = D.point, line = D.issues.air.line;
  const now15 = id => ((D.stats15[id] || {})[M] || [])[0] ?? null;
  /* by the node's own metres and bearing (js/nodegeo.js); a station it has no answer for is not placed */
  const at_ = id => { const q = D.ngeo && D.ngeo.dist[id]; return q ? { d: q.m / 1000, az: q.deg * Math.PI / 180 } : null; };
  const pts = D.sensors.filter(s => s.lat != null && s.kind !== 'model' && s.source !== 'openstreetmap' && at_(s.sensor_id)).map(s => {
    const { d, az } = at_(s.sensor_id);
    return { ...s, d, x: cx + r(d) * Math.sin(az), y: cy - r(d) * Math.cos(az), v: now15(s.sensor_id) };
  });
  const sea = D.sensors.find(s => s.sensor_id === 'marine-point');
  const f = big ? 1.5 : 1, T = (x, y, t, c = '', a = 'start') => `<text x="${x}" y="${y}" class="${c}" text-anchor="${a}">${esc(t)}</text>`;
  let s = `<svg viewBox="0 0 ${W} ${H}" width="${W}" height="${H}" role="img" aria-label="Stations around this node, by bearing and distance, with ${esc(labelOf(M))} now" style="font-size:${11 * f}px">`;
  for (const k of [0.5, 2, 5, 15]) s += `<circle cx="${cx}" cy="${cy}" r="${r(k)}" fill="none" stroke="currentColor" stroke-opacity=".22" stroke-dasharray="${k === 0.5 ? '2 3' : '4 4'}"/>`
    + T(cx - r(k) * .71 - 4, cy - r(k) * .71 - 4, `${k} km`, 'mute', 'end');
  s += `<line x1="${cx}" y1="${cy - R - 8}" x2="${cx}" y2="${cy - R + 4}" stroke="currentColor"/>` + T(cx, cy - R - 12, 'N', 'lab', 'middle');
  if (sea && at_(sea.sensor_id)) { const { d, az } = at_(sea.sensor_id);
    const x = cx + r(d) * Math.sin(az), y = cy - r(d) * Math.cos(az); s += `<rect x="${x - 4}" y="${y - 4}" width="8" height="8" fill="none" stroke="currentColor"/>` + T(x - 8, y + 4, 'sea model', 'mute', 'end'); }
  const house = pts.filter(p => p.local && p.kind === 'sensor'), out = pts.filter(p => !p.local), used = [[cx + 40, cy + 20]];
  const free = (x, y) => !used.some(([a, b]) => Math.abs(a - x) < 22 * f && Math.abs(b - y) < 12 * f) && (used.push([x, y]), true);
  for (const p of out) {
    const quiet = p.v == null, over = M === 'pm25' && !quiet && p.v > line;
    s += p.kind === 'facility' ? `<rect x="${p.x - 4}" y="${p.y - 4}" width="8" height="8" transform="rotate(45 ${p.x} ${p.y})" fill="none" stroke="currentColor"/>`
      : `<circle cx="${p.x}" cy="${p.y}" r="${4 * f}" fill="var(--ground)" stroke="currentColor" stroke-width="1.5" ${quiet ? 'stroke-dasharray="2 2"' : ''}/>`;
    if (p.kind !== 'facility' && !quiet && free(p.x + 7, p.y)) s += (over ? `<rect x="${p.x + 6}" y="${p.y - 9}" width="5" height="5" fill="var(--signal-worse)"/>` : '')
      + `<text x="${p.x + (over ? 13 : 7)}" y="${p.y + 4}" class="num" data-num="${esc(p.sensor_id)}.${M}" data-cmp="${esc(M === 'pm25' ? `the line ${line}` : 'no line')}">${fmt(p.v, 0)}</text>`;
  }
  const hv = house.map(p => p.v).filter(v => v != null);
  s += `<circle cx="${cx}" cy="${cy}" r="${7 * f}" fill="currentColor"/>`;
  s += T(cx + 11 * f, cy + 16 * f, `this house · ${house.length} stations`, 'lab') + (hv.length ? `<text x="${cx + 11 * f}" y="${cy + 30 * f}" class="num said">${fmt(d3.min(hv), 0)}–${fmt(d3.max(hv), 0)} ${esc(unitOf(M))}</text>` : '');
  el.innerHTML = s + `</svg>`;
  const quiet = out.filter(p => p.v == null && p.kind === 'sensor').length, fac = out.filter(p => p.kind === 'facility').map(p => p.name.trim());
  if (o.cap !== false) $('#rosecap').innerHTML = `${said(labelOf(M))}, the 15-minute mean, at ${out.filter(p => p.v != null).length} public stations and ${house.length} in this house; ${quiet} not heard in the last 15 minutes drawn dashed. `
    + (D.ngeo ? `${fac.length ? `The diamond${fac.length > 1 ? 's are' : ' is'} ${said(fac.join(', '))}; ` : ''}the square, the sea model. Bearings are true; distance is drawn on a square-root scale to 16 km so the house stays visible beside stations 15 km away.`
      : 'The stations are placed by the node’s own distances and bearings, which together say where it is, so this screen needs the token to draw them.');
}


document.addEventListener('keydown', ev => {
  if (document.activeElement !== $('#svg')) return;
  const step = { ArrowLeft: -1, ArrowRight: 1, ArrowUp: -24, ArrowDown: 24 }[ev.key];
  if (ev.key === 'End') { S.i = D.now; drawNow(); $('#svg').focus(); ev.preventDefault(); return; }
  if (step == null) return;
  S.i = Math.max(0, Math.min(D.now, S.i + step)); drawNow(); $('#svg').focus(); ev.preventDefault();
});
$('#back').onclick = () => { S.i = D.now; drawNow(); };
