'use strict';
/* WALL — a public screen in a living room or a lab, read from about 3 m by people who know nothing about air science
   (docs/site/dashboard.md, the Wall). Always dark, one viewport, operated by nobody.
   PLAN (Tomas's review of 14 Oct 2026, built 15 Oct; the walk, 16 Oct):
   - Type floor: nothing under --wf, 28 px at 1920×1080 and scaled by the viewport (doors.html, the WALL block). What
     did not survive the floor was cut, not shrunk.
   - THE WALK (Tomas, 16 Oct: "more interactivity, maybe similar to the phone version and have an automatic change of
     time and scale"; he picked option A of three, artifact NjPB3GjGuEJeSCZnobCJwM). The map walks out from the house a
     scale at a time, house → street → ring → region, as the phone's walk does (walk.js SCALES), framed on that scale's
     own H3 cell; the column beside it is that scale's page: the house's figures and its day; the street's, with its
     day replayed hour by hour against what the node learned is usual outside (GET /learned/place); the ring's, with
     the land around as a hundred squares and the places mapped, counted; the region's, with what the satellites see
     (fires, the ground's heat, the sky, the sea, and floods said to be not watched rather than invented).
   - Time and scale are stepped, never tweened: one hour of the day every WALL_TIME.HOUR_STEP(24) seconds, and when the
     day has been replayed, the next scale. Under reduced motion nothing moves: the street is held, at the last hour,
     the wind one still frame, and the rail's four scales are buttons.
   - Reading order: the time and the sentence (the hero, as the engine writes it) with what is asked now beside it →
     the map, its caption saying in words what its red discs mean against the house → the scale's page → the
     narration, only when there is text. 16 Oct (Tomas): the row of answered alerts is gone, and the rings with it.
   - Every figure says when it is from and one of the provenance words; a figure from /observations takes the engine's
     own rule for readouts (kind model is "model", any other is "partial"); what the node learned is derived, "partial".
   - Chrome (back, chips, the model's note) is .wchrome: invisible until a pointer is over it or the keyboard is in it;
     always shown on a touch screen, every control a 44 px target there. The back button stays first in keyboard
     order. The rail is not chrome: it is how a reader knows which scale is drawn. Pressing a scale holds it; pressing
     it again lets the walk go on.
   - On a phone, a small or a portrait screen the two columns stack, the map first, and the floor is 12 px.
   - The narration box sits under the scale's page, collapsed until a model's text arrives, and keeps the last text, in
     memory, while the next one is written. Its label says these are a model's words. */
let WVAR = 'pm25';
/* Every duration on the Wall, in one table named after the datum each one paces (the layer: motion only where the datum
   has a cadence, stepped, never tweened; nothing moves under reduced motion: the hours hold, the wind is a still frame,
   the model's text arrives whole). The replay loop itself is the layer's token, --motion-replay-loop. */
const WALL_TIME = {
  HOUR_STEP: win => (parseFloat(css('--motion-replay-loop')) || 30) / win,  /* s: one replayed hour, then the next; a scale holds one day of them */
  WIND_FRAME: 33,                                                           /* ms: one step of the wind's streaks */
  NARR_EVERY: 10 * 60e3,                                                    /* ms: a new reading by the node's model */
  NARR_CHAR: 1000 / 11,                                                     /* ms: one character typed, about two words a second */
  NARR_LINE: 3000,                                                          /* ms: one line of a story longer than its box, rolling */
  STALE: 15 * 60e3,                                                         /* ms: no poll this long and the readings are old */
};
/* Never a name on the wall (Tomas, 14 Oct 2026): anyone in the room reads it, and a sensor's name is a room, a kit or an
   address ("K ROOM - BAYU HOLES"); a kicker's reason names who answered. The house is one mark, a public station a disc;
   what is asked is the engine's own sentence (asking[].says), never the alert's text, which names the room. */
/* one line that ends on a word: the first sentence, cut at a word under `max` characters ("If somethin…", 14 Oct) */
const oneLine = (s, max = 90) => {
  s = String(s || '').trim(); const f = s.match(/^.*?[.!?](?=\s|$)/); s = f ? f[0] : s;
  return s.length <= max ? s : s.slice(0, max + 1).replace(/\s+\S*$/, '').replace(/[\s,;:–—-]+$/, '') + '…';
};
/* What is asked now is the node's one answer (/issues asking), the same Now's Decide card reads: an alert still open
   whose reading came back is not asked of anybody now, and the Wall said it was while Now said nothing was (14 Oct). */
function wallAsk(it) {
  const a = it.asking || [], says = a.length ? oneLine(a[0].says) : '';
  if (!a.length) return '<span class="wsay">Nothing is asked now.</span>';
  const count = a.length === 1 ? 'One thing is asked of this house.' : `${a.length} things are asked of this house.`;
  return `<span class="wsay said">${esc(says || count)}</span><span class="wtel">${says ? count + ' ' : ''}Answer on Telegram, not here.</span>`;
}
/* The map's caption: its red discs in words against the house, now, so a clean headline beside red discs is not a
   contradiction left to the reader; it reads the hour the discs are drawn at ("This house is under the clean-air line now; 3 stations nearby, in red, are over it"). */
function wallCaption(house, near, line, when = 'now') {
  if (line == null) return '';
  const n = near.filter(v => v != null && v > line).length, st = n === 1 ? 'one station nearby, in red, is' : `${n} stations nearby, in red, are`;
  if (house == null) return n ? `${st[0].toUpperCase() + st.slice(1)} over the clean-air line ${when}.` : `Every station nearby is under the clean-air line ${when}.`;
  if (house > line) return n ? `This house is over the clean-air line ${when}, and ${st} too.` : `This house is over the clean-air line ${when}; no station nearby is.`;
  return n ? `This house is under the clean-air line ${when}; ${st} over it.` : `This house and every station nearby are under the clean-air line ${when}.`;
}
/* `stale` only when the node's readings are old: no poll in the last 15 minutes (three at the 300 s default), or none
   since the restart. /health's last_error is not read: one failing portal of twenty sets it while the rest are fresh. */
const wallStale = h => !(Date.now() - Date.parse(h.last_poll || '') < WALL_TIME.STALE);
/* THE WALK: the four scales, as the phone's walk names them (walk.js SCALES) and the H3 resolution each is framed on */
const WALL_SCALES = [{ k: 'room', res: 10 }, { k: 'yard', res: 9 }, { k: 'ring', res: 6 }, { k: 'region', res: 3 }];
const WALK = { sc: null, held: false, t0: 0, hour: null, place: [], placeAt: 0 };
const wpw = w => `<span class="wpw">${esc(w)}</span>`;
/* when a figure is from: the hour if today, the day if this year, the month and year if older */
function wallWhen(ts) {
  const t = new Date(ts); if (!ts || Number.isNaN(+t)) return '';
  const f = o => new Intl.DateTimeFormat('en-GB', { timeZone: D.tz, ...o }).format(t), now = new Date();
  const same = o => f(o) === new Intl.DateTimeFormat('en-GB', { timeZone: D.tz, ...o }).format(now);
  return same({ year: 'numeric', month: 'numeric', day: 'numeric' }) ? hhmm(ts) : same({ year: 'numeric' }) ? f({ day: 'numeric', month: 'short' }) : f({ month: 'short', year: 'numeric' });
}
/* one observation, newest: its value, when, and the engine's provenance word for it */
function wallObs(sid, metric) {
  const o = (D.observations || []).filter(r => r.sensor_id === sid && r.metric === metric && r.value != null).sort((a, b) => Date.parse(b.ts) - Date.parse(a.ts))[0];
  return o ? { v: o.value, ts: o.ts, word: o.kind === 'model' ? 'model' : 'partial' } : null;
}
/* a source in the Wall's own words, never a sensor's name: a name can be a room, a kit or a point ("Sea, 5 km off
   (-8.79, 115.13)"); a count of sensors is said as it is, a model by the service, anything else as "a model" */
const wallSrc = s => /^\d+ sensors?$/.test(s || '') ? s : /CAMS/i.test(s || '') ? 'CAMS' : /open-meteo/i.test(s || '') ? 'Open-Meteo' : 'a model';
/* the day at one distance: the last 24 hours of the air (or of the lead issue), one series, the line dashed red */
const DAYK = () => (D.issues.air ? 'air' : D.lead);
function wallDay(d, hi, usual) {
  const k = DAYK(), it = D.issues[k], v = ((it.series || {})[d] || []).slice(-24); if (!v.some(x => x != null)) return '';
  const Wd = 900, Hh = 220, line = it.line, all = v.concat(line ?? [], usual || []).filter(x => x != null);
  const top = Math.max(...all) * 1.1 || 1, x = i => 6 + (Wd - 12) * i / (v.length - 1), y = q => Hh - 8 - (Hh - 20) * q / top;
  const path = s => s.reduce((a, q, i) => (q == null ? a : a + (i && s[i - 1] != null ? 'L' : 'M') + `${x(i).toFixed(1)},${y(q).toFixed(1)}`), '');
  let g = usual ? `<path d="${path(usual)}" fill="none" stroke="var(--ink)" stroke-width="2" stroke-dasharray="1 6" stroke-linecap="round"/>` : '';
  if (line != null) g += `<line x1="0" x2="${Wd}" y1="${y(line)}" y2="${y(line)}" stroke="var(--signal-worse)" stroke-width="2" stroke-dasharray="10 6"/>`;
  g += `<path d="${path(v)}" fill="none" stroke="var(--ink)" stroke-width="3"/>`;
  if (hi != null && v[hi] != null) g += `<line x1="${x(hi)}" x2="${x(hi)}" y1="0" y2="${Hh}" stroke="var(--ink)" stroke-width="1"/><circle cx="${x(hi)}" cy="${y(v[hi])}" r="7" fill="var(--ink)"/>`;
  return `<svg class="wday" viewBox="0 0 ${Wd} ${Hh}" preserveAspectRatio="none" role="img" aria-label="${esc(it.name)}, the last 24 hours, ${esc(D.labels[d] || d)}">${g}</svg>`;
}
/* what the node learned is usual outside, at each of the day's hours (GET /learned/place, the place's own) */
function wallUsual() {
  const L = (WALK.place || []).find(l => l.issue === DAYK() && l.numbers && l.numbers.by_hour); if (!L) return null;
  return { L, by: D.buckets.slice(-24).map(b => L.numbers.by_hour[String(hourOf(b))] ?? null) };
}
const wallFig = (k, s, dp) => `<div class="wfig"><span class="wn">${esc(D.issues[k].name)}</span><b class="numf">${fmt(s.value, dp)}</b><span class="wu">${esc(D.issues[k].unit || '')}</span>`
  + `<span class="wsrc">${esc(wallSrc(s.source))} · ${hhmm(D.as_of)} ${wpw(s.provenance || 'partial')}</span></div>`;
function wallFacts(d, only) {
  const rows = (D.order.length ? D.order : Object.keys(D.issues)).filter(k => D.issues[k] && (!only || only.includes(k)))
    .map(k => [k, (D.issues[k].stack || {})[d]]).filter(([, s]) => s && s.value != null);
  return rows.length ? `<div class="wfacts">${rows.map(([k, s]) => wallFig(k, s, D.issues[k].dp ?? 0)).join('')}</div>` : '<p class="wsrc">Nothing is read at this scale here.</p>';
}
/* the land within 1 km as a hundred squares, one a hundredth, its kind by fill; the satellite's own, so stroked orange */
function wallHundred() {
  const P = [['built', 'built_frac', 'q-built'], ['trees', 'tree_frac', 'q-trees'], ['crops', 'crop_frac', 'q-crops'], ['water', 'water_frac', 'q-water']]
    .map(([w, m, c]) => ({ w, c, o: wallObs('ee-point', m) })).filter(p => p.o);
  if (!P.length) return '<p class="wsrc">No land cover from a satellite is read on this node.</p>';
  P.forEach(p => { p.n = Math.round(p.o.v * 100); });
  const sq = P.flatMap(p => Array(Math.max(0, p.n)).fill(p.c)), rest = Math.max(0, 100 - sq.length), o = P[0].o;
  return `<div class="whund" role="img" aria-label="${P.map(p => `${p.w} ${p.n}%`).join(', ')}">${sq.concat(Array(rest).fill('q-rest')).slice(0, 100).map(c => `<i class="${c}"></i>`).join('')}</div>`
    + `<p class="wkey">${P.filter(p => p.n).map(p => `<span><i class="${p.c}"></i>${p.w} <b>${p.n}%</b></span>`).join('')}${rest ? `<span><i class="q-rest"></i>other <b>${rest}%</b></span>` : ''}`
    + `<span class="wsrc">land cover, by satellite · ${wallWhen(o.ts)} ${wpw(o.word)}</span></p>`;
}
/* the places OpenStreetMap maps within 1 km, counted: one square a place; past 40 the figure alone (counted, not sized).
   The four kinds with the most places, so the page stays one screen wherever the map is dense. */
function wallPlaces() {
  const rows = [['food', 'poi_food'], ['shops', 'poi_retail'], ['lodging', 'poi_lodging'], ['services', 'poi_services'], ['schools', 'poi_education'], ['clinics', 'poi_health'], ['worship', 'poi_worship']]
    .map(([w, m]) => [w, wallObs('place-point', m)]).filter(([, o]) => o && o.v > 0).sort((a, b) => b[1].v - a[1].v).slice(0, 4);
  if (!rows.length) return '';
  const b = wallObs('place-point', 'buildings'), c = wallObs('place-point', 'commercial_share'), o = rows[0][1];
  const said = b && c ? `; it tags ${fmt(Math.round(b.v * c.v), 0)} of ${fmt(b.v, 0)} buildings as shops or offices, too few to tell homes from shops` : '';
  return `<div class="wplaces">${rows.map(([w, r]) => `<div><span>${w}</span><span class="wsq">${r.v <= 40 ? '<i></i>'.repeat(r.v) : ''}</span><b>${fmt(r.v, 0)}</b></div>`).join('')}</div>`
    + `<p class="wsrc">places mapped within 1 km, OpenStreetMap${said} · ${wallWhen(o.ts)} ${wpw(o.word)}</p>`;
}
/* what the satellites and the models see around: each row only where the node reads it; floods said, never invented */
function wallAround() {
  const COMPASS = ['N', 'NNE', 'NE', 'ENE', 'E', 'ESE', 'SE', 'SSE', 'S', 'SSW', 'SW', 'WSW', 'W', 'WNW', 'NW', 'NNW'];
  const F = m => wallObs('firms-fires', m), n = F('fires_region_24h'), up = F('fires_region_upwind'), near = F('fires_nearest_km'), br = F('fires_nearest_bearing');
  const lst = wallObs('surface-cell', 'lst'), night = wallObs('surface-modis', 'lst_night'), sky = wallObs('cams-point', 'pm25_model'), dust = wallObs('cams-point', 'dust'), sea = wallObs('marine-point', 'swell_height_m');
  const R = [
    n && ['Fires', 'NASA FIRMS, VIIRS, the last 24 h', n.v ? `<b>${fmt(n.v, 0)}</b> burning within 150 km, ${up && up.v ? `<b>${fmt(up.v, 0)}</b> upwind` : 'none upwind'}${near && br ? `; the nearest ${fmt(near.v, 0)} km ${COMPASS[Math.round(br.v / 22.5) % 16]}` : ''}` : 'none seen within 150 km', n, 'wbysat'],
    lst && ['Ground', `Landsat 30 m${night ? ', MODIS 1 km at night' : ''}`, `<b>${fmt(lst.v, 1)} °C</b> at the last clear pass${night ? `, ${fmt(night.v, 1)} °C at night` : ''}`, lst, 'wbysat'],
    sky && ['Sky', 'CAMS, a model', `<b>${fmt(sky.v, 0)} µg/m³</b> fine dust over the region${dust ? `, desert dust ${fmt(dust.v, 0)}` : ''}`, sky, ''],
    sea && ['Sea', 'Open-Meteo marine, a model', `<b>${fmt(sea.v, 1)} m</b> swell`, sea, ''],
  ].filter(Boolean);
  return `<table class="wexp">${R.map(([w, src, v, o, c]) => `<tr class="${c}"><th>${w}</th><td>${v}<span class="wsrc">${src} · ${wallWhen(o.ts)} ${wpw(o.word)}</span></td></tr>`).join('')}`
    + '<tr class="wnone"><th>Floods</th><td>not watched on this node yet</td></tr></table>';
}
/* the scale's page, at hour hi of the day (0–23) */
function wallPage(sc, hi) {
  const d = WALL_SCALES[sc].k, u = wallUsual(), B = D.buckets.slice(-24), k = DAYK(), unit = (D.issues[k] || {}).unit || '';
  if (sc === 0) return wallFacts(d) + `<h3>The day in the house</h3>${wallDay(d, hi)}`;
  if (sc === 1) {
    const at = ['room', 'yard', 'ring'].map(x => { const v = ((D.issues[k].series || {})[x] || []).slice(-24)[hi]; return v != null ? `${esc(D.labels[x] || x)} <b>${fmt(v, D.issues[k].dp ?? 0)}</b>` : ''; }).filter(Boolean);
    return wallFacts(d) + (at.length ? `<p class="wat">${esc(D.issues[k].name)} at <b>${hhmm(B[hi])}</b>: ${at.join(' · ')} <span class="wu">${esc(unit)}</span></p>` : '')
      + wallDay(d, hi, u && u.by)
      + `<p class="wsrc">solid: the street, hour by hour ${wpw('live')}${u ? ` · dotted: what this node learned is usual outside at that hour, over ${u.L.numbers.days} days, checked ${wallWhen(u.L.checked_at)} ${wpw('partial')}` : ''}${D.issues[k].line != null ? ` · red: the line, ${fmt(D.issues[k].line, D.issues[k].dp ?? 0)}` : ''}</p>`;
  }
  if (sc === 2) return wallFacts(d) + `<h3>The land within 1 km</h3>${wallHundred()}${wallPlaces()}`;
  return wallFacts(d, [k]) + `<h3>What the satellites see</h3>${wallAround()}`;
}
const wallRail = () => WALL_SCALES.map((s, i) => `<button data-sc="${i}" class="${i === WALK.sc ? 'on' : ''}" aria-pressed="${i === WALK.sc && WALK.held}">${esc(D.labels[s.k] || s.k)}</button>`).join('');
/* the day's hour i as an index into the hourly table the map's discs read, or null where this screen has none */
const rawHour = i => { if (!D.raw || i == null) return null; const t = Date.parse(D.buckets.slice(-24)[i]); const j = D.raw.buckets.findIndex(b => Date.parse(b) === t); return j < 0 ? null : j; };
function wallScale(i) {
  WALK.sc = i; WALK.hour = WALK.hour ?? 23;
  const r = $('#wrail'); if (r) { r.innerHTML = wallRail(); wallRailOn(); }
  const k = $('#wscale'); if (k) k.textContent = `${D.labels[WALL_SCALES[i].k] || WALL_SCALES[i].k} · scale ${i + 1} of 4`;
  const p = $('#wpage'); if (p) p.innerHTML = wallPage(i, WALK.hour);
  wallFit(); WALLMAP.api && WALLMAP.api.scale(i);
}
/* the narration takes the room the page leaves; where that is less than its box, it waits for the next scale rather
   than covering the page or running past the screen (node #1, 16 Oct). A stacked Wall scrolls, so there it always fits. */
function wallFit() {
  const n = $('#wnarr'), r = $('.wr'); if (!n || !r) return;
  n.classList.remove('wnoroom'); if (!n.hidden && r.scrollHeight > r.clientHeight + 1) n.classList.add('wnoroom');
  else if (!n.hidden && !NARR.typing) narrRoll();        /* a story typed while the box had no room starts rolling when it does */
}
function wallHour(i) {
  WALK.hour = i; const p = $('#wpage'); if (p && (WALK.sc <= 1)) { p.innerHTML = wallPage(WALK.sc, i); wallFit(); }
  WALLMAP.api && WALLMAP.api.hour(rawHour(i));
}
function wallRailOn() {
  document.querySelectorAll('#wrail button').forEach(b => b.onclick = () => {
    const i = +b.dataset.sc; WALK.held = CLOCK.reduced() || !(WALK.held && WALK.sc === i); WALK.t0 = performance.now(); wallScale(i);
  });
}
/* the walk's one clock: an hour every HOUR_STEP(24) s; after the 24th, the next scale unless one is held */
function wallTick(now) {
  if (view() !== 'wall') return CLOCK.off('wall-walk');
  const HS = WALL_TIME.HOUR_STEP(24) * 1000; let i = Math.floor((now - WALK.t0) / HS);
  if (i >= 24) { WALK.t0 = now; i = 0; if (!WALK.held) wallScale((WALK.sc + 1) % WALL_SCALES.length); }
  if (i !== WALK.hour) wallHour(i);
}
VIEWS.wall = async function () {
  const k = D.lead, it = D.issues[k], still = CLOCK.reduced();
  const carried = Object.keys(D.metrics).filter(m => Object.values(D.stats15).some(x => x[m] && x[m][0] != null));
  const chips = [WVAR, ...carried.filter(m => m !== WVAR)].slice(0, 4);
  const at = new Intl.DateTimeFormat('en-GB', { timeZone: D.tz, hour: '2-digit', minute: '2-digit' }).format(new Date(D.as_of));
  /* the walk starts on the street at the day's first hour; reduced motion holds it there, at the last */
  if (WALK.sc == null) { WALK.sc = 1; WALK.held = still; WALK.hour = still ? 23 : 0; WALK.t0 = performance.now(); }
  $('#wallv').innerHTML = `
    <div class="wtop wchrome"><button class="wback" onclick="location.hash='#now'">← back</button>
      <span class="wchips">${chips.map(m => `<button class="${m === WVAR ? 'on' : ''}" data-m="${m}">${said(labelOf(m))}</button>`).join('')}</span>
      <span class="wnote said" id="wnote"></span></div>
    <div class="whead" data-learn="wall-sentence" data-reads="/issues /health" data-stage="decide" data-pack="core"><div class="wkick"><time>${at}</time>${wallStale(D.health) ? ' · <b>the readings are old</b>' : ''}</div>
      <p class="wsent">${it.pix ? `<svg class="pix" aria-hidden="true"><use href="${NODE}signs.svg#${it.pix}"/></svg>` : ''}<span class="said">${esc(it.title || it.sentence).replace(/(\d+(?:\.\d+)?)(?=\s*(?:°C|µg|%|m\b))/, m0 => num(`${k}.${it.hero_distance}`, m0, `against the line, ${it.line} ${it.unit}`, `<b class="numf">${m0}</b>`))}</span></p>
      <div class="wask">${wallAsk(it)}</div></div>
    <div class="wgrid">
      <section class="wl" data-kind="row" data-learn="wall-map" data-reads="/sensors /stats /geo/cell /ground/wind" data-stage="observe" data-pack="core"><div id="wfield" role="img" aria-label="The stations around this house on its own map, at one scale, their readings, and the wind now"></div>
        <div class="wrail" id="wrail" role="group" aria-label="Scale">${wallRail()}</div><p class="wcap said" id="wcap"></p></section>
      <section class="wr"><p class="wscale" id="wscale" data-learn="wall-walk"></p><div class="wpage" id="wpage" data-learn="wall-page" data-reads="/issues /observations /learned/place" data-stage="observe" data-pack="core"></div>
        <div class="wnarr" id="wnarr" hidden data-learn="wall-narration" data-reads="/ask/status /ask" data-stage="observe" data-pack="core"></div>
      </section>
    </div>`;
  document.querySelectorAll('.wchips button').forEach(c => c.onclick = () => { WVAR = c.dataset.m; VIEWS.wall(); });
  if (Date.now() - WALK.placeAt > 6 * 36e5) {          /* the node learns once a local day; a wall runs for weeks */
    WALK.placeAt = Date.now(); WALK.place = await doorsFetch('/learned/place').then(r => (r.ok ? r.json() : null)).then(j => (j && j.learnings) || []).catch(() => []); }
  if (view() !== 'wall') return;
  wallScale(WALK.sc); narrDraw();
  if (!NARR.busy && !NARR.typing && (!NARR.next || Date.now() >= NARR.next)) narrate(); else if (NARR.shown.length < NARR.text.length) narrType();
  if (!still) CLOCK.on('wall-walk', wallTick);          /* a redraw on a poll keeps the walk's clock: the scale and hour go on */
  /* the map follows the walk, and never holds it up: a slow tile or wind field leaves the pages stepping */
  wallMap({ el: $('#wfield'), cap: $('#wcap'), scales: WALL_SCALES, sc: WALK.sc, hour: still ? null : rawHour(WALK.hour) }).catch(() => {});
};
/* THE NODE, THINKING ALOUD (R44, 7 Oct 2026). A reading of the figures by the node's own model, in plain words for
   people who know nothing about air science, units or maps: what is happening inside, how it compares with the street and the
   neighbourhood, what it suggests for an ordinary day, and what the next hours may bring. It asks POST /ask, so the
   model is the one the keeper chose under Set up → Model (AGENT_PREFER): this machine, another on the house's network,
   or an online provider; the wall names the one that answered, and warns while it asks when the choice can go online.
   The context is /ask's own, scrubbed of every place, name and id; nothing is stored.
   Tomas, 7 Oct: twice as long, written at a slower pace, a new one every 10 minutes, and a countdown to the next.
   The model writes into a queue; the wall types it at a reading pace whatever the model's speed.
   The prompt lives on the node as WALL_SYSTEM; the page asks for it by name (prompt:'wall').
   15 Oct: the box is collapsed until there is text (an empty frame saying "asking its model" was the second-largest
   thing on the wall), and the last text stays up, whole, while the model writes the next; the new one is typed only
   once it has all arrived. Kept in memory, never stored. The label says these are a model's words; the model's name, a
   failure and why are chrome (#wnote), shown under a pointer or the keyboard. */
const NARR = { text: '', shown: '', prev: '', at: 0, next: 0, busy: false, typing: false, model: null, where: null, err: null, timer: 0 };
let NARR_TYPE = 0;
function narrDraw() {
  const el = $('#wnarr'), note = $('#wnote'); if (!el) return;
  if (note) note.textContent = NARR.err || (NARR.model ? `the words are ${NARR.model}’s${NARR.where ? `, ${NARR.where}` : ''}` : '');
  const t = NARR.shown || NARR.prev;                  /* the text being typed, else the last one whole */
  el.hidden = !t;
  if (!t) { el.innerHTML = ''; return; }
  el.classList.toggle('busy', NARR.busy || NARR.typing);
  el.innerHTML = `<div class="nh"><span class="nl"><i class="dot" aria-hidden="true"></i>The node, thinking aloud</span>`
    + `<span>a model’s words from the node’s figures, never a reading${NARR.where === 'online' ? ' · written online' : ''}</span></div>`
    + `<div class="nw"><p class="nt said"><span id="ntext">${esc(t)}</span>${NARR.typing ? '<i class="caret" aria-hidden="true"></i>' : ''}</p></div>`;
  if (typeof wallFit === 'function') wallFit();
  if (!NARR.typing) narrRoll();
}
/* a story longer than its box rolls up, a line every NARR_LINE, in a loop with its start coming round again, once it
   is typed (Tomas, 21 Oct: the end was cut and the start never came back). A second copy follows the first so the loop
   has no seam; under reduced motion it stands still at its start. */
function narrRoll() {
  const w = $('#wnarr .nw'), p = w && w.querySelector && w.querySelector('.nt');
  if (!p || w.classList.contains('roll') || p.offsetHeight <= w.clientHeight) return;
  w.classList.add('roll');
  const twin = p.cloneNode(true); twin.setAttribute('aria-hidden', 'true'); twin.querySelector('[id]')?.removeAttribute('id'); w.appendChild(twin);
  const cs = getComputedStyle(p), h = p.offsetHeight + parseFloat(cs.marginBottom), line = parseFloat(cs.lineHeight) || 24;
  w.style.setProperty('--roll-h', `${h}px`);
  w.style.setProperty('--roll-s', `${(h / line) * WALL_TIME.NARR_LINE / 1000}s`);
}
/* the typist: one character at a time over the last text, all at once under reduced motion; then the next in ten minutes */
function narrType() {
  if (NARR_TYPE) return;
  NARR.typing = true; narrDraw();
  const step = () => {
    if (view() !== 'wall') { NARR_TYPE = 0; return; }
    const t = document.getElementById('ntext');
    if (NARR.shown.length < NARR.text.length) {
      NARR.shown = NARR.text.slice(0, CLOCK.reduced() ? NARR.text.length : NARR.shown.length + 1);
      if (t) t.textContent = NARR.shown; else narrDraw();     /* the first letter opens a box that had nothing yet */
      NARR_TYPE = setTimeout(step, CLOCK.reduced() ? 0 : WALL_TIME.NARR_CHAR);
    } else { NARR_TYPE = 0; NARR.typing = false; NARR.prev = NARR.text; NARR.next = Date.now() + WALL_TIME.NARR_EVERY; narrDraw();
      clearTimeout(NARR.timer); NARR.timer = setTimeout(narrate, WALL_TIME.NARR_EVERY); }
  };
  step();
}
const narrLater = () => { NARR.busy = false; NARR.at = Date.now(); NARR.next = Date.now() + WALL_TIME.NARR_EVERY; narrDraw(); NARR.timer = setTimeout(narrate, WALL_TIME.NARR_EVERY); };
async function narrate() {
  if (NARR.busy || NARR.typing || view() !== 'wall') return;
  clearTimeout(NARR.timer); NARR.err = null;
  if (D.askOff) { NARR.err = ''; NARR.next = 0; narrDraw(); return; }
  NARR.busy = true;
  const st = await doorsFetch('/ask/status').then(r => r.ok ? r.json() : r.status === 404 ? { none: true } : null).catch(() => null);
  if (!st || st.none) {
    NARR.err = '';
    return narrLater();
  }
  NARR.model = null; NARR.where = null; NARR.prev = NARR.shown || NARR.prev; NARR.text = ''; NARR.shown = ''; narrDraw();
  try {
    const r = await fetch('/ask', { method: 'POST', headers: { 'content-type': 'application/json', ...DOORS_AUTH() },
      body: JSON.stringify({ messages: [{ role: 'user', content: 'speak' }], view: 'wall', mode: 'advanced', focus: null, prompt: 'wall' }) });
    if (!r.ok || !r.body) throw new Error(`the node answered ${r.status}`);
    const rd = r.body.getReader(), dec = new TextDecoder(); let buf = '';
    for (;;) {
      const { value, done } = await rd.read(); if (done) break;
      buf += dec.decode(value, { stream: true }); let cut;
      while ((cut = buf.indexOf('\n\n')) >= 0) {
        const block = buf.slice(0, cut); buf = buf.slice(cut + 2);
        const ev = (block.match(/^event: (.+)$/m) || [])[1], data = JSON.parse((block.match(/^data: (.+)$/m) || [])[1] || '{}');
        if (ev === 'token') NARR.text += data.text;
        else if (ev === 'retry') NARR.text = '';
        else if (ev === 'done') { NARR.model = data.model || null; NARR.where = data.where || null; }
        else if (ev === 'error') throw new Error(data.message);
      }
    }
    NARR.text = NARR.text.trim();
    if (!NARR.text) throw new Error('it answered with nothing');
  } catch (e) { NARR.err = 'The story returns when the node can speak again.'; NARR.text = ''; }
  if (NARR.err) return narrLater();
  NARR.busy = false; NARR.at = Date.now(); narrType();     /* the typist replaces the last text, then sets the next ten minutes on */
}
