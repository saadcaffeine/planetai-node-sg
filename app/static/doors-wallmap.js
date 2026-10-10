'use strict';
/* WALLMAP — the Wall's drawing, a living map (R42, 7 Oct 2026; Tomas: the flow by scale "does not work").
   Research: deck.gl's trips and scatterplot examples, mapbox/webgl-wind and earth.nullschool for air moving over a dark
   ground, AQICN's wind-against-PM2.5 study for the story: where the air is dirty, which way it is going, whether the
   house is inside it.

   The node's own dark street map (GET /ground/vector, as Place and Now draw it). Over it:
   - the wind, now: Open-Meteo's field for this hour (GET /ground/wind), a model, drawn as drifting streaks;
   - every station at its point, a disc whose area is that hour's mean of the chosen metric (GET /aggregates, the
     hourly table), so a dirtier hour swells and a cleaner one shrinks; red where PM2.5 is over the air line;
   - the house, and a ring that leaves it when an alert went out that hour (red) or an answer came back (green).
   The hours replay: the last 6 (or 24) in 30 s (--motion-replay-loop), the strip under the map says which.
   Without the token the hourly table, the map and the wind are not this screen's: it draws the 15-minute means now,
   held still, on the land's colour, and says so. Under reduced motion it holds the last hour still. */
const WALLMAP = { map: null, ov: null, wind: null, stop: null };

/* A wind engine for any map: particles moved by the field's hour, the screen fading behind them (Agafonkin's CPU
   version). ponytail: the Place door keeps its own copy inside doors-placemap.js; merge the two when Place changes. */
function windOn(map, F, hour, colour) {
  const cv = document.createElement('canvas'), x = cv.getContext('2d'), CELL = 18, K = 0.025;
  cv.className = 'windcv'; cv.setAttribute('aria-hidden', 'true'); map.getContainer().appendChild(cv);
  const n = F.n, uv = (s, from) => { const t = (from + 180) * Math.PI / 180; return [s * Math.sin(t), s * Math.cos(t)]; };
  const sample = (lng, lat) => {
    const fy = (lat - F.lats[0]) / (F.lats[n - 1] - F.lats[0]) * (n - 1), fx = (lng - F.lons[0]) / (F.lons[n - 1] - F.lons[0]) * (n - 1);
    if (!(fx >= 0 && fy >= 0 && fx <= n - 1 && fy <= n - 1)) return null;
    const x0 = Math.min(n - 2, Math.floor(fx)), y0 = Math.min(n - 2, Math.floor(fy)), tx = fx - x0, ty = fy - y0;
    const at = (j, i) => { const s = F.speed_kmh[hour][j][i], d = F.from_deg[hour][j][i]; return s == null || d == null ? null : uv(s, d); };
    const c = [at(y0, x0), at(y0, x0 + 1), at(y0 + 1, x0), at(y0 + 1, x0 + 1)];
    if (c.some(v => !v)) return null;
    return [0, 1].map(k => (c[0][k] * (1 - tx) + c[1][k] * tx) * (1 - ty) + (c[2][k] * (1 - tx) + c[3][k] * tx) * ty);
  };
  let w = 0, h = 0, cols = 0, cells = [], parts = [];
  const vel = (px, py) => (px < 0 || py < 0 || px >= w || py >= h) ? null : cells[Math.floor(py / CELL) * cols + Math.floor(px / CELL)];
  const spawn = p => { for (let k = 0; k < 12; k++) { p.x = Math.random() * w; p.y = Math.random() * h; if (vel(p.x, p.y)) break; }
    p.age = Math.floor(Math.random() * 160); p.max = 140 + Math.floor(Math.random() * 140); return p; };
  const resample = () => {
    const el = map.getContainer(), dpr = devicePixelRatio || 1; w = el.clientWidth; h = el.clientHeight;
    cv.width = w * dpr; cv.height = h * dpr; x.setTransform(dpr, 0, 0, dpr, 0, 0);
    cols = Math.ceil(w / CELL); const rows = Math.ceil(h / CELL); cells = new Array(cols * rows);
    for (let r = 0; r < rows; r++) for (let c = 0; c < cols; c++) {
      const ll = map.unproject([c * CELL + CELL / 2, r * CELL + CELL / 2]), v = sample(ll.lng, ll.lat);
      cells[r * cols + c] = v ? [v[0] * K, -v[1] * K] : null;
    }
    parts = Array.from({ length: Math.min(380, Math.round(w * h / 2200)) }, () => spawn({}));
    x.clearRect(0, 0, w, h);
  };
  const tick = () => {
    x.globalCompositeOperation = 'destination-in'; x.fillStyle = 'rgba(0,0,0,.92)'; x.fillRect(0, 0, w, h);
    x.globalCompositeOperation = 'source-over'; x.strokeStyle = colour; x.lineWidth = 1.2; x.beginPath();
    for (const p of parts) { const v = vel(p.x, p.y); if (!v || ++p.age > p.max) { spawn(p); continue; } x.moveTo(p.x, p.y); p.x += v[0]; p.y += v[1]; x.lineTo(p.x, p.y); }
    x.stroke();
  };
  resample();
  return { resample, tick, remove: () => cv.remove() };
}

async function wallMap(o) {
  if (WALLMAP.stop) WALLMAP.stop();
  const F = await flowData(), WIN = WINS.includes(o.win) ? o.win : WINS[0], LOOP = parseFloat(css('--motion-replay-loop')) || 30;
  const B = F.buckets, h0 = B.length - WIN, HS = LOOP / WIN, M = WVAR, line = M === 'pm25' ? (D.issues.air || {}).line : null;
  const replay = !!D.raw && !CLOCK.reduced();
  const meanAt = (id, h) => { const s = D.raw && (D.raw.series[id] || {})[M]; const v = s && s[h]; return v ? v[0] : null; };
  const now15 = id => ((D.stats15[id] || {})[M] || [])[0] ?? null;
  const all = D.sensors.filter(s => s.lat != null && s.lon != null && s.kind === 'sensor' && s.source !== 'openstreetmap');
  const pub = all.filter(s => !s.local), house = all.filter(s => s.local);
  /* one scale for the window: the disc's AREA is the value, so the radius is its square root; capped at the 98th
     percentile so one spike cannot shrink the rest, and a value past the cap is printed beside its disc */
  const vals = [];
  for (const s of all) for (let h = h0; h < B.length; h++) { const v = replay ? meanAt(s.sensor_id, h) : now15(s.sensor_id); if (v != null) vals.push(v); }
  vals.sort(d3.ascending);
  const cap = Math.max(d3.quantile(vals, .98) ?? 1, line ?? 0, 1e-9), big = o.size > 700, rMax = big ? 34 : 24, rad = v => v == null ? 0 : 3 + (rMax - 3) * Math.sqrt(Math.min(v, cap) / cap);
  const C = (k, a = 1) => rgba(k, a), mono = 'JetBrains Mono, monospace', f = big ? 1.35 : 1;

  const base = await window.groundBase('dark');
  o.el.innerHTML = `<div class="wallmap" style="width:${o.size}px;height:${o.size}px"></div><div class="wclock" aria-live="off"></div>`;
  const map = WALLMAP.map = new maplibregl.Map({ container: o.el.firstChild, style: base.style, center: D.point, zoom: 11, interactive: false,
    attributionControl: false, fadeDuration: 0, transformRequest: window.groundRequest });
  map.on('load', () => { for (const l of ['v-road-label', 'v-poi-label']) if (map.getLayer(l)) map.setLayoutProperty(l, 'visibility', 'none');
    if (map.getLayer('v-place-label')) map.setPaintProperty('v-place-label', 'text-opacity', .45); });
  const bb = new maplibregl.LngLatBounds(D.point, D.point); pub.forEach(s => bb.extend([s.lon, s.lat]));
  map.fitBounds(bb, { padding: big ? 70 : 40, duration: 0, maxZoom: 14 });
  const ov = WALLMAP.ov = new deck.MapboxOverlay({ interleaved: false, layers: [] }); map.addControl(ov);
  map.addControl(new maplibregl.ScaleControl({ maxWidth: big ? 120 : 80, unit: 'metric' }), 'bottom-left');

  /* the wind: this hour of the model's field, not the replayed hour (the field looks forward; the hours look back) */
  const W = await fetch('/ground/wind', { headers: DOORS_AUTH() }).then(r => r.status === 200 ? r.json() : null).catch(() => null);
  let wind = null;
  const windHour = W ? W.times.reduce((b, t, i) => Math.abs(Date.parse(t) - Date.now()) < Math.abs(Date.parse(W.times[b]) - Date.now()) ? i : b, 0) : 0;
  map.once('idle', () => { if (W) wind = WALLMAP.wind = windOn(map, W, windHour, 'rgba(249,245,242,.5)'); });
  const COMPASS = ['N', 'NNE', 'NE', 'ENE', 'E', 'ESE', 'SE', 'SSE', 'S', 'SSW', 'SW', 'WSW', 'W', 'WNW', 'NW', 'NNW'];
  const windWords = W && W.at_node.speed_kmh[windHour] != null ? `wind now ${Math.round(W.at_node.speed_kmh[windHour])} km/h from ${COMPASS[Math.round(W.at_node.from_deg[windHour] / 22.5) % 16]} · model` : 'no wind field on this screen';

  const hourOfT = t => Math.min(B.length - 1, h0 + Math.floor(t / HS));
  const layers = (t) => {
    const h = replay ? hourOfT(t) : B.length - 1, frac = replay ? (t / HS) % 1 : 1;
    const v = s => replay ? meanAt(s.sensor_id, h) : now15(s.sensor_id);
    const pts = pub.map(s => ({ s, p: [s.lon, s.lat], v: v(s) })).filter(d => d.v != null);
    const hv = house.map(v).filter(x => x != null), hmean = hv.length ? d3.mean(hv) : null;
    /* a ring leaves the house for each alert sent and each answer back in this hour, over the first 60% of it */
    const ev = replay ? [...F.alerts.filter(a => Math.floor(a.h) === h).map(() => 'alert'), ...F.answers.filter(a => Math.floor(a.h) === h).map(() => 'answer')] : [];
    const k = Math.min(1, frac / .6);
    return [
      new deck.ScatterplotLayer({ id: 'st', data: pts, getPosition: d => d.p, radiusUnits: 'pixels', getRadius: d => rad(d.v), stroked: true, filled: true,
        getFillColor: d => line != null && d.v > line ? C('--signal-worse', .5) : C('--ink', .16), getLineColor: d => line != null && d.v > line ? C('--signal-worse') : C('--ink', .85),
        lineWidthUnits: 'pixels', getLineWidth: 1.5, transitions: { getRadius: { duration: HS * 700, easing: d3.easeCubicInOut }, getFillColor: HS * 500 },
        updateTriggers: { getRadius: h, getFillColor: h, getLineColor: h } }),
      new deck.TextLayer({ id: 'st-v', data: pts, characterSet: 'auto', getPosition: d => d.p, getText: d => fmt(d.v, 0), getSize: 13 * f, fontFamily: mono, fontWeight: 600,
        getColor: C('--ink'), getPixelOffset: d => [rad(d.v) + 5, 0], getTextAnchor: 'start', getAlignmentBaseline: 'center', updateTriggers: { getText: h, getPixelOffset: h } }),
      ...ev.map((e, i) => new deck.ScatterplotLayer({ id: 'ev' + i, data: [D.point], getPosition: d => d, radiusUnits: 'pixels', getRadius: 10 + (90 + i * 18) * k * f,
        stroked: true, filled: false, getLineColor: e === 'alert' ? C('--signal-worse', .9 * (1 - k)) : C('--rings', .9 * (1 - k)), lineWidthUnits: 'pixels', getLineWidth: 2 })),
      new deck.ScatterplotLayer({ id: 'house', data: [D.point], getPosition: d => d, radiusUnits: 'pixels', getRadius: rad(hmean) || 7, stroked: true, filled: true,
        getFillColor: C('--ink'), getLineColor: C('--ground'), lineWidthUnits: 'pixels', getLineWidth: 2, transitions: { getRadius: HS * 700 }, updateTriggers: { getRadius: h } }),
      new deck.TextLayer({ id: 'house-l', data: [D.point], characterSet: 'auto', getPosition: d => d, getText: () => `this house${hmean != null ? ` · ${fmt(hmean, 0)} ${unitOf(M)}` : ''}`,
        getSize: 13 * f, fontFamily: mono, fontWeight: 600, getColor: C('--ink'), getPixelOffset: [0, (rad(hmean) || 7) + 14], getTextAnchor: 'middle',
        background: true, getBackgroundColor: C('--ground', .85), backgroundPadding: [4, 2], updateTriggers: { getText: h, getPixelOffset: h } }),
    ];
  };

  /* the words beside it and the clock on it: this hour's counts, then the window's */
  const tot = { in: Object.values(F.counts).reduce((a, n) => a + d3.sum(n.slice(h0)), 0), out: F.alerts.filter(a => a.h >= h0).length, back: F.answers.filter(a => a.h >= h0).length };
  let shown = -1;
  const words = t => {
    const h = replay ? hourOfT(t) : B.length - 1; if (h === shown) return; shown = h;
    const st = { in: Object.values(F.counts).reduce((a, n) => a + (n[h] || 0), 0), out: F.alerts.filter(a => Math.floor(a.h) === h).length, back: F.answers.filter(a => Math.floor(a.h) === h).length };
    o.el.querySelector('.wclock').innerHTML = `<b>${hhmm(B[h])}</b><span>${dLabel(dayOf(B[h])).split(',')[0]} · ${replay ? `the last ${WIN} hours, replayed` : 'now, held still'}</span><span>${esc(windWords)}</span>`;
    o.side && (o.side.innerHTML = `<div class="fwords"><div class="k">${hhmm(B[h])} · this hour, then the last ${WIN}</div>`
      + [['readings in', F.counted ? st.in : '—', F.counted ? tot.in : '—', 'ink', F.counted ? 'from every source on the map' : 'counted with the token'],
         ['alerts out', st.out, tot.out, 'red', 'a ring leaves the house'], ['answers back', st.back, tot.back, 'green', 'a loop closed']]
        .map(([t2, a, z, cls, s2]) => `<div class="fc ${cls}"><i></i><span>${t2}<small>${s2}</small></span>${num('wall.' + t2, a, `this hour; ${z} in ${WIN} hours`, `<b>${a}</b>`)}<em>${z}</em></div>`).join('')
      + `<p class="fine">A disc’s area is that hour’s mean of ${said(labelOf(M))} at that station, one scale for the window; red is over the air line. The streaks are the wind now, a model.</p></div>`);
    o.time && o.time.querySelectorAll('.h').forEach(x => x.classList.toggle('on', +x.dataset.h === h));
  };
  if (o.time) {
    o.time.innerHTML = `<div class="seg" role="group" aria-label="Window">${WINS.map(w2 => `<button data-w="${w2}" class="${w2 === WIN ? 'on' : ''}">${w2} h</button>`).join('')}</div>`
      + `<button class="play" aria-label="Pause">❚❚</button><div class="hours" style="grid-template-columns:repeat(${WIN},minmax(0,1fr))">${B.slice(h0).map((b, j) => { const i = h0 + j, al = F.alerts.filter(a => Math.floor(a.h) === i).length, an = F.answers.some(a => Math.floor(a.h) === i);
        return `<button class="h" data-h="${i}" title="${hhmm(b)}"><span>${WIN <= 6 || hourOf(b) % 6 === 0 ? hhmm(b) : ''}</span>${al ? `<i class="a" style="height:${Math.min(14, 3 + al * 2)}px"></i>` : ''}${an ? '<i class="b"></i>' : ''}</button>`; }).join('')}</div>`
      + `<span class="k">${replay ? `${WIN} hours in ${LOOP} s` : D.raw ? 'reduced motion: the last hour, held' : 'the hours replay with the token'} · red: alerts sent · green: answers back</span>`;
    o.time.querySelectorAll('.seg button').forEach(b => b.onclick = () => +b.dataset.w !== WIN && wallMap({ ...o, win: +b.dataset.w }));
  }
  let tHold = replay ? 0 : LOOP - HS * .5, t0 = performance.now(), paused = !replay, last = 0;
  const draw = t => { ov.setProps({ layers: layers(t) }); words(t); };
  const tick = now => {
    if (view() !== 'wall') return WALLMAP.stop && WALLMAP.stop();
    if (wind && now - last >= 33) wind.tick();                                  /* the wind moves even when the hours are paused */
    if (paused || now - last < 33) return; last = now;
    tHold = ((now - t0) / 1000) % LOOP; draw(tHold);
  };
  const play = () => { paused = false; t0 = performance.now() - tHold * 1000; o.time && (o.time.querySelector('.play').textContent = '❚❚'); };
  const pause = () => { paused = true; o.time && (o.time.querySelector('.play').textContent = '▶'); };
  if (o.time) {
    const pb = o.time.querySelector('.play'); pb.onclick = () => paused ? play() : pause(); if (!replay) { pb.disabled = true; pb.textContent = '▶'; }
    o.time.querySelectorAll('.h').forEach(b => b.onclick = () => { if (!replay) return; tHold = (+b.dataset.h - h0 + .5) * HS; t0 = performance.now() - tHold * 1000; draw(tHold); });
  }
  map.once('idle', () => draw(tHold));
  if (!CLOCK.reduced()) CLOCK.on('wall-map', tick);
  WALLMAP.stop = () => { CLOCK.off('wall-map'); if (wind) wind.remove(); map.remove(); WALLMAP.map = WALLMAP.ov = WALLMAP.wind = WALLMAP.stop = null; };
}
