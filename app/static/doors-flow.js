'use strict';
/* FLOW — the node by scale (R37, 7 Oct 2026). One drawing for Node and the Wall: the node at the centre of its scales,
   readings falling inward from where they are read, summaries and alerts leaving outward to where they go.

   The scales are rings, not a ladder of hexagons: house, street, public stations, region, planet. A station sits at
   its true bearing, its distance on a square-root scale to 15 km (the rose's geometry, so Now and Node agree).
   Every packet is one real event from the capture, replayed: 2,769 readings, 30 alerts, 7 answers, 48 radio
   announcements, 24 Index updates and one export in the last 24 hours. A packet is a counted sign in transit: more
   events are more packets, never a bigger one.

   Colour keeps its one meaning: ink for a reading, red for an alert (a line was crossed), green for an answer (a loop
   closed), blue for the cell (the radio's announcement, the Index), orange for what only the satellite knows.

   Compute: deck.gl, already loaded for Place (R36), draws everything on the GPU in one canvas. The packets are one
   TripsLayer whose only changing prop is currentTime; static layers keep their data, so nothing is re-uploaded. The
   page's one clock drives it at ≤ 24 frames a second, stops when the tab is hidden or the drawing is off screen, and
   never starts under reduced motion — then the drawing holds the last half hour still and the hours step by hand.
   R38: the window is shorter. The last 6 hours by default (24 on a press); any window replays in --motion-replay-loop
   (30 s, PROPOSED), so six hours is 5 s an hour and a packet can be followed. An hour is the finest window: the
   counts are hourly, and a shorter one would only spread invented minutes.

   R38: the cells, as cells. Inside 5 km the drawing is flat and to scale (true bearing, distance linear), so the H3
   cells keep their shape: the node's res-8 cell, solid; the 49 res-8 cells of its res-6 parent, the finest cell that
   may leave the machine, as a hairline grid; that parent dotted (the ladder's rule for a rung that may leave).
   Beyond 5 km distance compresses on a square root to the stations' 15 km ring, so the region still fits. */
const FLOW = { data: null, inst: new Map() };
/* What moved through the node, hour by hour, over the hourly table's 24 hours: readings in (the most any one metric
   of a sensor counted that hour), alerts out, answers back. Read from the routes, never invented. The counts need
   GET /aggregates, which is token-only: without it `counted` is false, the counts are empty and the drawings say so;
   the alerts and the answers still come, from /issues' own asks. */
const flowData = async () => FLOW.data || (FLOW.data = flowFrom(D));
function flowFrom(D) {
  const counted = !!(D.raw && D.raw.buckets.length);
  const B = counted ? D.raw.buckets : D.buckets.slice(-24), at = new Map(B.map((b, i) => [b, i])), t0 = Date.parse(B[0]), h = ts => (Date.parse(ts) - t0) / 36e5;
  const counts = {};
  for (const r of counted ? D.raw.n : []) { const c = (counts[r.sensor_id] ||= B.map(() => 0)); const i = at.get(r.bucket); c[i] = Math.max(c[i], r.n || 0); }
  const inW = x => { const v = h(x.ts); return v >= 0 && v < B.length; };
  return { buckets: B, counts, counted,
    alerts: D.alerts.filter(inW).map(a => ({ h: +h(a.ts).toFixed(3), level: a.level ?? null, rule: a.rule_id, text: (a.text || '').split('\n')[0] })),
    answers: D.actions.filter(inW).map(a => ({ h: +h(a.ts).toFixed(3), stage: a.stage, actor: a.actor })) };
}
if (typeof module !== 'undefined') module.exports = { flowFrom };
const HOURS = 24, TRAVEL = 1.1, WINS = [6, 24];                                 // a packet's flight, in replay seconds
function rgba(v, a = 1) {
  const s = css(v);
  if (s.startsWith('#')) { const h = s.length === 4 ? s.slice(1).split('').map(c => c + c).join('') : s.slice(1, 7); return [0, 2, 4].map(i => parseInt(h.slice(i, i + 2), 16)).concat(Math.round(a * 255)); }
  const m = s.match(/[\d.]+/g) || [0, 0, 0]; return [+m[0], +m[1], +m[2], Math.round(a * 255 * (m[3] != null ? +m[3] : 1))];
}
let SEED = 7; const rnd = () => (SEED = (SEED * 16807) % 2147483647) / 2147483647;   // the same scatter on every draw

function flowGeometry(S, big) {
  const small = S < 500, cx = S / 2, cy = S / 2, R = S / 2 - (big ? 100 : small ? 30 : 104), P = D.point;
  const D0 = 5, a0 = .74 * R / Math.sqrt(15 * D0), REG = .88 * R, PLA = R;   // to scale inside D0 km; square root from there to 15 km at .74 R
  const rr = k => k <= D0 ? a0 * k : a0 * D0 * Math.sqrt(Math.min(k, 15) / D0);
  const at = (r, a) => [cx + r * Math.sin(a), cy - r * Math.cos(a)], deg = d => d * Math.PI / 180;
  /* Placed by the node's own metres and bearing (GET /geo/measure each, /geo/cell polar): the page only squeezes the
     radius past 5 km, which is the drawing's scale, not a distance it works out. */
  const NG = D.ngeo, pol = (m, d) => at(rr(m / 1000), deg(d));
  const src = {}, models = D.sensors.filter(s => s.kind === 'model' && s.sensor_id !== 'marine-point');
  for (const s of D.sensors) {
    const q = NG && NG.dist[s.sensor_id]; if (!q) continue;
    if (s.kind === 'sensor') src[s.sensor_id] = { p: pol(q.m, q.deg), local: s.local, kind: 'sensor', name: s.name };
    if (s.sensor_id === 'marine-point') src[s.sensor_id] = { p: pol(q.m, q.deg), kind: 'model', name: 'the sea model' };
  }
  models.forEach((m, i) => { src[m.sensor_id] = { p: at(REG, deg(214 + i * 12)), kind: 'model', name: m.name }; });
  // the cells: every vertex inside D0, where the drawing is flat, so an edge stays straight
  const warp = row => { const r = polarRing(row).map(([m, d]) => pol(m, d)); return r.concat([r[0]]); };
  const cell = NG ? NG.c8.id : D.health.cell.id, parW = NG ? warp(NG.c6.ring_polar) : [];
  const cells = NG ? { cell, par: NG.c6.id, own: warp(NG.c8.ring_polar), parent: parW,
      grid: NG.c6.children_polar.filter(r => r[0] !== cell).map(warp),
      n6: NG.c6.children_n, n3: NG.c3.children_n, a8: NG.c8.area_m2, a6: NG.c6.area_m2, a3: NG.c3.area_m2 }
    : { cell, none: true, own: [], parent: [], grid: [] };
  const edge = !parW.length ? at(.5 * PLA, deg(18)) : parW.reduce((a, p) => Math.abs(Math.atan2(p[0] - cx, cy - p[1]) - deg(18)) < Math.abs(Math.atan2(a[0] - cx, cy - a[1]) - deg(18)) ? p : a);
  src['msh-8f491db0'] = { p: at(rr(.25), deg(200)), local: true, kind: 'sensor', name: 'the mesh' };
  const dest = {
    phone: { p: at(rr(1.6), deg(140)), t: small ? 'phone' : 'the household’s phone', role: 'alert' },
    index: { p: at(PLA, deg(48)), t: small ? 'Index' : 'Fab City Index', role: 'cell' },
    commons: { p: at(PLA, deg(100)), t: small ? 'commons' : 'the commons', role: 'export' },
    community: { p: edge, t: small ? 'not set' : 'community node · res 6 · not set', role: 'none' },   // it would gather the res-6 cells: it sits on that cell's edge
  };
  return { small, cx, cy, R, rr, REG, PLA, at, deg, src, dest, cells, sat: at(PLA, deg(305)) };
}

function flowTrips(G, F, HS, h0) {
  SEED = 7; const T = [], c = [G.cx, G.cy], at = h => (h - h0) * HS;   // replay time of capture hour h
  for (const [id, n] of Object.entries(F.counts)) {
    const s = G.src[id]; if (!s) continue;                       // a source the drawing cannot place is counted in the words, not drawn
    n.forEach((k, h) => { if (h < h0) return; for (let j = 0; j < k; j++) { const t = at(h + (j + rnd()) / k); T.push({ path: [s.p, c], ts: [t, t + TRAVEL * (s.kind === 'model' ? 1.6 : 1)], kind: 'reading' }); } });
  }
  for (const a of F.alerts) if (a.h >= h0) T.push({ path: [c, G.dest.phone.p], ts: [at(a.h), at(a.h) + TRAVEL], kind: 'alert' });
  for (const a of F.answers) if (a.h >= h0) T.push({ path: [G.dest.phone.p, c], ts: [at(a.h), at(a.h) + TRAVEL], kind: 'answer' });
  for (let h = h0; h < HOURS; h++) T.push({ path: [c, G.dest.index.p], ts: [at(h + .08), at(h + .08) + TRAVEL * 1.6], kind: 'cell' });
  const midnight = F.buckets.findIndex(b => hourOf(b) === 0);
  if (midnight >= h0) T.push({ path: [c, G.dest.commons.p], ts: [at(midnight), at(midnight) + TRAVEL * 2], kind: 'export' });
  return T;
}

/* The key: the cells in words, and how many like this one make the radio's res-3 cell, the region, which is a ring. Areas are each cell's own, from the node (area_m2), not a resolution's average. */
function flowKey(C) {
  if (C.none) return `<div class="fkey"><div class="k">the cells</div><p>The cells and every distance are the node’s answers, token-only because together they place it (${esc(D.ngeoErr || 'no answer')}). Unlock this screen under Node to draw them.</p></div>`;
  /* every count and area here is the node's (GET /geo/cell children and area_m2), each cell's own, not a resolution's average */
  const n6 = C.n6, n3 = C.n3, A = { [C.cell]: C.a8, [C.par]: C.a6, r3: C.a3 }, r3 = 'r3', a = id => A[id] / 1e6;
  return `<div class="fkey"><div class="k">the cells</div>`
    + `<p><b>this cell</b> · res 8 · ${num('flow.key.cell', fmt(a(C.cell), 2), 'this cell\'s own area, km²')} km²</p>`
    + `<p><b>1 of ${num('flow.key.n6', n6, 'res-8 cells in one res-6 cell')}</b> · res 6 · ${num('flow.key.par', fmt(a(C.par), 0), 'the parent\'s own area, km²')} km² · may leave</p>`
    + `<p><b>1 of ${num('flow.key.n3', n3.toLocaleString('en'), 'res-8 cells in one res-3 cell, counted by the node')}</b> · res 3 · ${num('flow.key.r3', Math.round(a(r3)).toLocaleString('en'), 'the region cell\'s own area, km²')} km²</p></div>`;
}

/* mount: o = { el, side, time, big, size, win } — el gets the canvas, side the counters, time the hour strip; win is 6 or 24 hours. */
async function flowMount(o) {
  const F = await flowData(), old = FLOW.inst.get(o.el); if (old) { old.stop(); old.deck.finalize(); }
  const WIN = WINS.includes(o.win) ? o.win : WINS[0], h0 = HOURS - WIN;
  const S = Math.round(o.size), big = !!o.big, LOOP = parseFloat(css('--motion-replay-loop')) || 30, HS = LOOP / WIN;
  const G = flowGeometry(S, big), trips = flowTrips(G, F, HS, h0), f = big ? 1.35 : 1;
  const C = { ink: rgba('--ink'), mute: rgba('--mute'), hair: rgba('--ink', .14), route: rgba('--ink', .09), ground: rgba('--ground'), cells: rgba('--cells'), red: rgba('--signal-worse'), green: rgba('--rings'), sat: rgba('--satellite-only') };
  const KIND = { reading: C.ink, alert: C.red, answer: C.green, cell: C.cells, export: C.ink };
  const ringPath = r => d3.range(0, 361, 4).map(a => G.at(r, G.deg(a)));
  const rings = G.small ? [[G.rr(2), '2 km'], [G.rr(15), '15 km'], [G.PLA, 'planet']]
    : [[G.rr(2), 'street · 2 km'], [G.rr(5), 'to scale inside 5 km'], [G.rr(15), 'stations · 15 km'], [G.REG, 'region · res 3'], [G.PLA, 'planet']];
  const dash = new deck.PathStyleExtension({ dash: true });
  const srcs = Object.values(G.src), dests = Object.values(G.dest);
  const mono = 'JetBrains Mono, monospace', body = 'Figtree, sans-serif', px = { widthUnits: 'pixels', widthMinPixels: 1 };
  const statics = [
    new deck.PathLayer({ id: 'rings', data: rings, getPath: d => ringPath(d[0]), getColor: C.hair, getWidth: 1, ...px, extensions: [dash], getDashArray: [3, 4] }),
    new deck.TextLayer({ id: 'ring-l', data: rings, characterSet: 'auto', getPosition: d => { const p = G.at(d[0], G.deg(180)); return [p[0], p[1] + 3]; }, getText: d => d[1], getSize: 10.5 * f, fontFamily: mono, getColor: C.mute, getTextAnchor: 'middle', getAlignmentBaseline: 'top',
      background: true, getBackgroundColor: C.ground, backgroundPadding: [4, 1] }),   // the grid runs under the inner labels
    new deck.PathLayer({ id: 'routes-in', data: srcs, getPath: d => [d.p, [G.cx, G.cy]], getColor: C.route, getWidth: 1, ...px }),
    new deck.PathLayer({ id: 'routes-out', data: dests, getPath: d => [[G.cx, G.cy], d.p], getColor: d => d.role === 'none' ? C.hair : rgba('--ink', .3), getWidth: 1, ...px, extensions: [dash], getDashArray: d => d.role === 'none' ? [2, 5] : [1, 3] }),
    new deck.ScatterplotLayer({ id: 'sources', data: srcs.filter(s => s.kind === 'sensor'), getPosition: d => d.p, radiusUnits: 'pixels', getRadius: (big ? 4.5 : 3.5), stroked: true, filled: true, getFillColor: d => d.local ? C.ink : C.ground, getLineColor: C.ink, lineWidthUnits: 'pixels', getLineWidth: 1.3 }),
    new deck.TextLayer({ id: 'models', data: srcs.filter(s => s.kind === 'model'), characterSet: 'auto', getPosition: d => d.p, getText: () => '◇', getSize: 15 * f, getColor: C.ink }),
    new deck.ScatterplotLayer({ id: 'sat', data: [G.sat], getPosition: d => d, radiusUnits: 'pixels', getRadius: 5 * f, getFillColor: C.sat }),
    new deck.TextLayer({ id: 'sat-l', data: [G.sat], characterSet: 'auto', getPosition: d => [d[0] + 9, d[1]], getText: () => G.small ? 'satellite' : 'the satellite · once a year', getSize: 10.5 * f, fontFamily: mono, getColor: C.mute, getTextAnchor: 'start' }),
    new deck.ScatterplotLayer({ id: 'dests', data: dests, getPosition: d => d.p, radiusUnits: 'pixels', getRadius: 4.5 * f, stroked: true, filled: true, getFillColor: C.ground, getLineColor: d => d.role === 'cell' ? C.cells : C.ink, lineWidthUnits: 'pixels', getLineWidth: 1.5 }),
    new deck.TextLayer({ id: 'dests-l', data: dests, characterSet: 'auto', getPosition: d => { const r = d.p[0] >= G.cx, k = G.small && d.p[0] > G.cx + G.R * .6 ? -1 : 1; return [d.p[0] + (r ? 9 : -9) * k, d.p[1] + (k < 0 ? 12 : 0)]; }, getText: d => d.t, getSize: 11.5 * f, fontFamily: body,
      getColor: d => d.role === 'none' ? C.mute : C.ink, getTextAnchor: d => { const r = d.p[0] >= G.cx, k = G.small && d.p[0] > G.cx + G.R * .6; return (r !== k) ? 'start' : 'end'; } }),
    new deck.TextLayer({ id: 'models-l', data: [G.at(G.REG, G.deg(214 + 2 * 12))], characterSet: 'auto', getPosition: d => [d[0] - 12, d[1]], getText: () => G.small ? '' : 'models · hourly', getSize: 10.5 * f, fontFamily: mono, getColor: C.mute, getTextAnchor: 'end' }),
    new deck.PathLayer({ id: 'grid', data: G.cells.grid, getPath: d => d, getColor: rgba('--cells', .2), getWidth: 1, ...px }),
    new deck.PathLayer({ id: 'parent', data: G.cells.none ? [] : [G.cells.parent], getPath: d => d, getColor: rgba('--cells', .85), getWidth: 1.5, ...px, extensions: [dash], getDashArray: [2, 3] }),
    new deck.PolygonLayer({ id: 'cell', data: G.cells.none ? [] : [G.cells.own], getPolygon: d => d, getFillColor: rgba('--cells', .13), getLineColor: C.cells, lineWidthUnits: 'pixels', getLineWidth: 2.5 }),
  ];
  const announce = d3.range(0, WIN * 2).map(i => i * HS / 2);
  const layers = t => {
    const last = announce.filter(a => a <= t).pop() ?? -9, k = (t - last) / (HS * .45);    // the radio's announcement, travelling out to its cell
    return [...statics,
      new deck.TripsLayer({ id: 'packets', data: trips, getPath: d => d.path, getTimestamps: d => d.ts, getColor: d => KIND[d.kind], currentTime: t, trailLength: big ? .1 : .08,
        fadeTrail: true, getWidth: big ? 3.5 : 2.6, ...px, capRounded: false, jointRounded: false }),
      ...(k >= 0 && k <= 1 ? [new deck.PathLayer({ id: 'announce', data: [1], getPath: () => ringPath(G.rr(.6) + (G.REG - G.rr(.6)) * k), getColor: rgba('--cells', .55 * (1 - k)), getWidth: 1.5, ...px })] : [])];
  };
  o.el.innerHTML = ''; o.el.style.width = S + 'px'; o.el.style.height = S + 'px'; o.el.style.position = 'relative';
  const dk = new deck.Deck({ parent: o.el, width: S, height: S, views: new deck.OrthographicView({ id: 'o' }), controller: false,
    initialViewState: { target: [S / 2, S / 2, 0], zoom: 0 }, layers: layers(LOOP - HS * .5), useDevicePixels: 1, /* hairlines and dashes need no retina fill; it halves the pixels on a wall */
    getCursor: () => 'default', style: { position: 'relative' } });
  if (!G.small) o.el.insertAdjacentHTML('beforeend', flowKey(G.cells));   // in the drawing's free corner
  if (o.side) o.side.innerHTML = `<div class="fwords"></div>`;
  const side = o.side && o.side.querySelector('.fwords');
  // the words beside the drawing: what crossed this hour, and in the whole day
  const hourStats = h => ({ in: Object.values(F.counts).reduce((a, n) => a + (n[h] || 0), 0), out: F.alerts.filter(a => Math.floor(a.h) === h).length, back: F.answers.filter(a => Math.floor(a.h) === h).length });
  const tot = { in: Object.values(F.counts).reduce((a, n) => a + d3.sum(n.slice(h0)), 0), out: F.alerts.filter(a => a.h >= h0).length, back: F.answers.filter(a => a.h >= h0).length };
  let shown = -1;
  const words = t => {
    const h = Math.min(HOURS - 1, h0 + Math.floor(t / HS)); if (h === shown) return; shown = h;
    const st = hourStats(h), b = F.buckets[h];
    side && (side.innerHTML = `<div class="k">${dLabel(dayOf(b)).split(',')[0]} ${hhmm(b)} · the last ${WIN} hours, replayed</div>`
      + [['readings in', st.in, tot.in, 'ink', 'from every source on the rings'], ['alerts out', st.out, tot.out, 'red', 'to the household’s phone'], ['answers back', st.back, tot.back, 'green', 'a loop closed'],
         ['announcements', 2, WIN * 2, 'blue', 'its res-3 cell, by radio, every 30 min'], ['Index updates', 1, WIN, 'blue', '6 of 20 cells, hourly'], ['hourly means to a community node', 0, 0, 'none', 'not set: nothing leaves']]
        .map(([t2, a, z, cls, s2]) => `<div class="fc ${cls}"><i></i><span>${t2}<small>${s2}</small></span>${num('flow.' + t2, a, `this hour; ${z} in ${WIN} hours`, `<b>${a}</b>`)}<em>${z}</em></div>`).join('')
      + `<p class="fine">This hour, then the last ${WIN}. One square is one event. Raw readings stop at the centre: what leaves is the cell, the hourly Index, the alerts and the daily file.</p>`);
    o.time && o.time.querySelectorAll('.h').forEach(x => x.classList.toggle('on', +x.dataset.h === h));
  };
  if (o.time) {
    o.time.style.maxWidth = S + 'px';
    o.time.innerHTML = `<div class="seg" role="group" aria-label="Window">${WINS.map(w => `<button data-w="${w}" class="${w === WIN ? 'on' : ''}">${w} h</button>`).join('')}</div>`
      + `<button class="play" aria-label="Pause">❚❚</button><div class="hours" style="grid-template-columns:repeat(${WIN},minmax(0,1fr))">${F.buckets.slice(h0).map((b, j) => { const i = h0 + j, al = F.alerts.filter(a => Math.floor(a.h) === i).length, an = F.answers.filter(a => Math.floor(a.h) === i).length;
      return `<button class="h" data-h="${i}" title="${hhmm(b)}"><span>${WIN <= 6 || hourOf(b) % 6 === 0 ? hhmm(b) : ''}</span>${al ? `<i class="a" style="height:${Math.min(14, 3 + al * 2)}px"></i>` : ''}${an ? '<i class="b"></i>' : ''}</button>`; }).join('')}</div>`
      + `<span class="k">${WIN} hours in ${LOOP} s · red: alerts sent · green: answers back</span>`;
    o.time.querySelectorAll('.seg button').forEach(b => b.onclick = () => +b.dataset.w !== WIN && flowMount({ ...o, win: +b.dataset.w }));
  }
  let t0 = performance.now() - (LOOP - HS * .5) * 1000, last = 0, paused = CLOCK.reduced(), tHold = LOOP - HS * .5;
  const draw = t => { dk.setProps({ layers: layers(t) }); words(t); };
  const tick = now => { if (paused) return; if (now - last < 42) return; /* ≤ 24 frames a second: a packet moves a few pixels a frame; more buys nothing */ last = now; const t = ((now - t0) / 1000) % LOOP; tHold = t; draw(t); };
  const id = 'flow-' + (o.big ? 'wall' : 'node');
  const play = () => { if (CLOCK.reduced()) return; paused = false; t0 = performance.now() - tHold * 1000; CLOCK.on(id, tick); o.time && (o.time.querySelector('.play').textContent = '❚❚'); };
  const pause = () => { paused = true; CLOCK.off(id); o.time && (o.time.querySelector('.play').textContent = '▶'); };
  if (o.time) {
    o.time.querySelector('.play').onclick = () => paused ? play() : pause();
    o.time.querySelectorAll('.h').forEach(b => b.onclick = () => { tHold = (+b.dataset.h - h0 + .5) * HS; t0 = performance.now() - tHold * 1000; draw(tHold); });
    if (CLOCK.reduced()) { o.time.querySelector('.play').disabled = true; o.time.querySelector('.play').textContent = '▶'; }
  }
  draw(tHold);
  const obs = new IntersectionObserver(([e]) => (e.isIntersecting && !paused) ? play() : CLOCK.off(id)); obs.observe(o.el);
  if (!paused) play();
  const inst = { deck: dk, stop: () => { CLOCK.off(id); obs.disconnect(); } };
  FLOW.inst.set(o.el, inst); return inst;
}
function flowStop(el) { const i = FLOW.inst.get(el); if (i) { i.stop(); i.deck.finalize(); FLOW.inst.delete(el); } }
