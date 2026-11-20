'use strict';
/* NOW — the household's first screen, read in the order a person asks (Tomas, 15 Oct; the plan heads the markup in
   doors.html): right now, as one block (the sentence and its day); what to do; did it work, and yesterday; around the
   house. Married to the node's rules: every part is one of the four card kinds (data-kind), names its learn mark, the
   routes it reads and its stage; every figure carries its comparison; the node's words are never shouted; provenance
   is a pill in ink. The scales are Place's: the kicker links there and draws no rail. */
VIEWS.now = function () {
  rows(); drawDeclared(); drawAsks(); drawNow();
  aroundMap($('#rose')); thingsLine($('#nthings')); rememberLoad().then(() => decision()); drawBoard('now');   /* the usual hour joins "Nothing is asked now" */
  $('#ncityrow').innerHTML = indexScreen(D.index_place);   /* the city screen's readout, over the map (doors-place.js) */
  /* Next days (SPEC_next_days §5) is a part of Now; #now/next, the address the switch kept until 4 Nov, scrolls to it */
  $('#nexth').textContent = (NX[D.locale] || NX.en).next;
  drawNext().then(() => { if (location.hash === '#now/next' && !NEXT.shown) { NEXT.shown = true; $('#nexth').scrollIntoView(); } });
};
/* YESTERDAY and DID IT WORK: the short part of the diary (Tomas, 14 Oct: the diary split between Now and Node, whose
   "What it remembers" keeps the record). Under the decision and quiet: yesterday's day entry said plainly from its own
   numbers; then, for the issue on screen, the last time the node asked, what was done, what happened after and the
   node's verdict. Framed only while something is asked. The admin token only: the house's learnings never reach a
   screen without it (doorsFetch does not even ask), nor the Wall. Read once a visit; switching issue redraws. */
let NOWL = null;
const LEARN_PACK = { air: 'air-quality', heat: 'heat' };
const VERDICT = { helps: 'It helps here.', no_clear_difference: 'No clear difference here yet.', worse: 'So far it seems to make it worse here.', too_early: 'Too early to say.' };
async function rememberLoad() {
  const get = u => doorsFetch(u).then(r => r.ok ? r.json() : null).catch(() => null);
  const [l, d, h] = await Promise.all([get('/learned'), get('/learned/search?scale=day&limit=1'), get('/household')]);
  NOWL = l ? { rows: l.learnings || [], day: ((d || {}).results || [])[0] || null, people: h ? h.people || {} : null } : null;
  nowRemember();
}
/* the hour this issue is usually worst, from the node's own `usual` learnings (28 days); said beside "Nothing is asked now" */
function usualLine(k) {
  const u = NOWL ? NOWL.rows.filter(r => r.kind === 'usual' && r.issue === k && r.status === 'holding' && r.numbers) : [];
  return u.length ? `It is usually worst ${u.map(r => `around <span class="mono">${String(r.numbers.high_hour).padStart(2, '0')}:00</span> ${r.key.startsWith('outdoor') ? 'outside' : 'inside'} (${num(`${r.key}.usual.high`, fmt(r.numbers.high, 1), 'the median of that hour, 28 days')} ${said(r.numbers.unit)})`).join(' and ')}.` : '';
}
const firstSentence = s => String(s || '').split(/(?<=\.)\s/)[0];
/* yesterday's entry, condensed: for heat the feels-like inside, else the air inside against the line (its hours over
   the line are /issues/days' own count, at the house) and outside beside it; else the entry's own first sentences */
function yesterdayWords(e, k) {
  const n = e.numbers || {}, i = n['indoor-pm25'], o = n['outdoor-pm25'], h = n['indoor-heat'], A = D.issues.air || {};
  const today = dayOf(D.buckets[D.now]), y = new Date(Date.parse(today + 'T12:00:00Z') - 864e5).toISOString().slice(0, 10);
  const day = String(e.period_start).slice(0, 10), head = day === y ? 'Yesterday' : `On ${dLabel(day)}`;
  const lineName = /^WHO\b/.test(A.line_source || '') ? 'the WHO line' : 'the line', cmp = A.line != null ? `${lineName}, ${A.line} µg/m³` : 'no line';
  const pd = A.hero_distance === 'room' ? (A.per_day || []).find(p => p.date === day) : null;
  let s;
  if (k === 'heat' && h) s = `${head} it felt like ${num('yesterday.heat.mean', fmt(h.mean, 1), 'the day’s mean, inside')} °C inside on average, ${num('yesterday.heat.max', fmt(h.max, 1), 'the day’s hottest hour, inside')} at its hottest (${hhmm(h.max_at)}).`;
  else if (i || o) {
    s = head + (i ? ` the air inside averaged ${num('yesterday.inside.mean', fmt(i.mean, 1), cmp)} µg/m³, ${num('yesterday.inside.max', fmt(i.max, 1), cmp)} at its worst (${hhmm(i.max_at)})`
      + (pd ? (pd.over ? `, over ${lineName} for ${num('yesterday.inside.over', pd.over, `of ${pd.read} hours read`)} hour${pd.over === 1 ? '' : 's'}` : `, never over ${lineName}`) : '') : '')
      + (o ? `${i ? '; outside' : ' the air outside'} averaged ${num('yesterday.outside.mean', fmt(o.mean, 1), cmp)}${i ? (o.mean > i.mean ? ', worse' : o.mean < i.mean ? ', cleaner' : ', the same') : ' µg/m³'}` : '') + '.';
  } else s = esc(String(e.text || '').split(/(?<=\.)\s/).slice(1, 3).join(' ')) || 'No readings from this house’s own sensors.';
  const al = Object.values(n.alerts || {}), raised = al.reduce((a, x) => a + x.raised, 0), acted = al.reduce((a, x) => a + x.acted, 0);
  return s + (raised ? ` ${num('yesterday.alerts', raised, 'alerts sent that day')} alert${raised === 1 ? '' : 's'}, ${num('yesterday.acted', acted, `of ${raised} alerts`)} acted on.` : '');
}
function nowRemember() {
  const el = $('#nremember'), k = S.issue, it = D.issues[k] || {};
  el.hidden = !NOWL;
  if (!NOWL) return;
  const day = NOWL.day, pack = LEARN_PACK[k], wd = iso => `${dLabel(dayOf(iso))} at ${hhmm(iso)}`;
  const yest = day ? `<div><h3>Yesterday</h3><p>${yesterdayWords(day, k)} <a href="#node/remember/day/${esc(String(day.period_start).slice(0, 10))}">the whole entry ›</a></p></div>` : '';
  let h = '';
  /* an issue that never asks (no line) has nothing that could have worked */
  if (pack) {
    const rank = { holding: 0, weakening: 0, too_early: 1 };
    const w = NOWL.rows.filter(r => r.kind === 'worked' && r.issue === pack && r.status in rank).sort((a, b) => rank[a.status] - rank[b.status] || b.n - a.n)[0];
    const N = (w && w.numbers) || {}, C = N.cases || {}, U = N.unit || it.unit, [lo, hi] = N.after_hours || [];
    const c = [...(C.acted || []).map(x => ({ ...x, acted: true })), ...(C.unanswered || [])].sort((a, b) => Date.parse(b.at) - Date.parse(a.at))[0];
    const ev = D.events.filter(e => e.issue === k).sort((a, b) => Date.parse(b.opened_at) - Date.parse(a.opened_at))[0];
    /* asked now is the node's one answer (`asking`), said once, in What to do above; an event answered but not yet
       cleared asks nothing (it said "is asking now" beside a Decide card that said Done, 15 Oct) */
    const asked = ev && !ev.cleared_at ? ((it.asking || []).length ? `The node is asking now, since ${wd(ev.opened_at)}: see What to do, above.` : `The node last asked ${wd(ev.opened_at)}: see What to do, above.`) : ev ? `The node last asked ${wd(ev.opened_at)}${ev.action ? `: ${said(ev.action)}` : '.'} <span class="x">${esc(answerWords(ev.answer).w)}.</span>`
      : `The node has not asked about ${said(it.name.toLowerCase())} in the last seven days.`;
    const after = c ? `<p>${c.acted ? `Done ${wd(c.at)}${c.note ? `: “${esc(c.note)}”` : ''}` : `Not answered, ${wd(c.at)}`}. Inside went from `
      + `${num(`${k}.case.before`, fmt(c.before, 1), 'the hour before')} to ${num(`${k}.case.after`, fmt(c.after, 1), `the ${lo}–${hi} h after`)} ${said(U)} in the ${lo}–${hi} h after`
      + `${c.street == null ? '' : `; the street ${num(`${k}.case.street`, (c.street > 0 ? '+' : '') + fmt(c.street, 1), 'the street’s change over the same hours')}`}.</p>` : '';
    const verdict = w ? `<p><b>${VERDICT[N.verdict] || (w.status === 'too_early' ? VERDICT.too_early : '')}</b> ${said(firstSentence(w.statement))}${w.status === 'weakening' ? ' <span class="x">· weakening</span>' : ''}</p>`
      : `<p class="x">Nothing learned yet: the node checks once a day, and needs an alert somebody acted on.</p>`;
    const who = w && (w.for_whom || []).length ? `matters here: ${said(w.for_whom.join(', '))}`
      : NOWL.people && !Object.values(NOWL.people).some(Boolean) ? '<a href="#node/remember/who">who lives here? ›</a>' : '';
    h += `<div><h3>Did it work</h3><p>${asked}</p>${after}${verdict}`
      + `<p class="dm">${who ? `${who} · ` : ''}<a href="#node/remember">every case, on Node ›</a></p></div>`;
  }
  h += yest;
  el.innerHTML = h;
  el.hidden = !h;
}
// The things this home keeps, in one line (SPEC_inventory step 2), for a screen holding the admin token; nothing otherwise.
async function thingsLine(el) {
  const r = await doorsFetch('/things').catch(() => null);
  const s = r && r.ok ? ((await r.json().catch(() => null)) || {}).summary : null;
  el.hidden = !(s && s.things);
  if (!el.hidden) el.innerHTML = `<a href="#data/d-things">${s.things} things, ${s.idle} idle, ${s.repair} need${s.repair === 1 ? 's' : ''} repair ›</a>`;
}
let ENERGY = undefined;
function loadEnergy() {
  if (D && D.energy) { ENERGY = D.energy; return Promise.resolve(ENERGY); }
  if (ENERGY !== undefined) return Promise.resolve(ENERGY);
  ENERGY = null;
  return doorsFetch('/energy').then(r => r.ok ? r.json() : null).catch(() => null).then(e => {
    ENERGY = e; if (D) D.energy = e;
    if (S.issue === 'energy' && $('#energy')) drawEnergy($('#energy'), e);
    return e;
  });
}
function drawEnergy(el, E) {
  if (!el) return;
  if (!E || !Array.isArray(E.sources) || !E.sources.length || E.kind === 'none') {
    const msg = (((D && D.issues || {}).energy || {}).state === 'none' && D.issues.energy.sentence)
      || 'This node is on no grid the energy pack knows yet: add it to packs/energy/grids.yml.';
    el.innerHTML = `<p class="sent said">${esc(msg)}</p>`;
    return;
  }
  const sh = E.share || {}, measured = E.kind === 'measured' || sh.value != null;
  let head = '';
  if (measured) {
    const pct = Math.round((sh.value ?? 0) * 100) + '%';
    head = `<div class="hl"><span class="big" style="color:var(--d-energy)">${num('energy.share', pct, 'of the grid’s electricity from fossil fuels')}</span>`
      + `<span class="u">of the grid’s electricity from fossil fuels${E.months ? ` · last ${num('energy.months', String(E.months), 'trailing months measured')} months` : ''}`
      + `${sh.now != null ? ` · right now: <b style="color:var(--ink)">${num('energy.now', Math.round(sh.now * 100) + '%', 'against the trailing-year share')} fossil</b>` : ''}</span></div>`;
  } else {
    const lo = sh.low != null ? Math.round(sh.low * 100) : null, hi = sh.high != null ? Math.round(sh.high * 100) : null;
    const rng = lo != null && hi != null ? `${lo}–${hi}%` : lo != null ? `${lo}%` : '—';
    head = `<div class="hl"><span class="big" style="color:var(--d-energy)">${num('energy.share', rng, 'estimated fossil share of the grid')}</span>`
      + `<span class="u">of the grid’s electricity from fossil fuels · estimated</span></div>`;
  }
  const sub = E.sources.find(s => s.kind === 'substation'), plants = E.sources.filter(s => s.kind === 'plant'), links = E.sources.filter(s => s.kind === 'link' || s.kind === 'cable_head');
  const unknownImport = E.import_max === null || (E.bar || []).some(b => b.hatched && b.share == null);
  const parts = [];
  if (sub) parts.push(`The nearest substation is <b>${esc(sub.name)}</b>, ${num('energy.substation.km', fmt(sub.km, 1), 'from this node’s cell')} km away.`);
  if (plants.length) parts.push(`Generation on the grid is ${plants.slice(0, 3).map((p, i) => `<b>${esc(p.name)}</b> (${esc(p.fuel || p.kind)}${p.mw != null ? `, ${num('energy.plant.' + i + '.mw', fmt(p.mw, 0), 'installed MW')} MW` : ''}, ${num('energy.plant.' + i + '.km', fmt(p.km, 1), 'from this node’s cell')} km)`).join(', ')}.`);
  if (unknownImport) {
    const lk = links[0];
    parts.push(`The rest comes by <b>${esc((lk && lk.name) || 'a link to another grid')}</b>${lk && lk.km != null ? ` (${num('energy.link.0.km', fmt(lk.km, 1), 'from this node’s cell')} km)` : ''}; how much comes from Java is not known.`);
  } else if (links.length) {
    parts.push(`Linked by <b>${esc(links[0].name)}</b>${links[0].km != null ? ` (${num('energy.link.0.km', fmt(links[0].km, 1), 'from this node’s cell')} km)` : ''}.`);
  }
  const segCol = b => b.tone === 'sky' ? 'var(--d-water)' : b.fossil === false || b.tone === 'sun' ? 'var(--d-heat)' : 'var(--d-energy)';
  const barSegs = (E.bar || []).filter(b => (b.share != null && b.share > 0) || b.hatched).map(b => {
    const w = b.share != null ? Math.max(1, Math.round(b.share * 100)) : 12;
    return `<span class="${b.hatched ? 'hatch' : ''}" style="flex:${w};--seg:${segCol(b)}" title="${esc(b.label)}"></span>`;
  }).join('');
  const legend = (E.bar || []).map((b, idx) => {
    const pct = b.share != null ? num('energy.bar.' + idx, Math.round(b.share * 100) + '%', 'share of grid mix') : esc(b.note || 'share not published');
    return `<span><i class="sw${b.hatched ? ' hatch' : ''}" style="--seg:${segCol(b)}"></i>${esc(b.label)} · ${pct}${b.share != null && b.note ? ` (${esc(b.note)})` : ''}</span>`;
  }).join('');
  const srcRows = E.sources.map((s, idx) => {
    const dot = s.kind === 'substation' ? 'var(--ink)' : s.fossil === false ? 'var(--d-heat)' : s.fossil === true ? 'var(--d-energy)' : 'var(--d-water)';
    const kf = [esc(s.fuel || s.kind), s.mw != null ? `${num('energy.src.' + idx + '.mw', fmt(s.mw, s.mw < 10 ? 1 : 0), 'installed capacity')} MW` : ''].filter(Boolean).join(' · ');
    const dist = s.km != null ? `${num('energy.src.' + idx + '.km', fmt(s.km, 1), 'from this node’s cell')} km` : '';
    return `<div class="src"><i class="dot" style="--seg:${dot}"></i><span class="said">${esc(s.name)}</span><span class="mono">${kf}</span><span class="mono">${dist}</span>${s.ring ? `<span class="pill">${esc(s.ring)}</span>` : ''}</div>`;
  }).join('');
  const td = E.today || {}, hh = E.household;
  let todayCells = '';
  if (td.sun_kwh_m2 != null) todayCells += `<div><span class="k">Sun on this cell today</span><span class="v">${num('energy.today.sun', fmt(td.sun_kwh_m2, 1), 'shortwave radiation today')} <small>kWh/m²</small></span></div>`;
  /* no forecast of the sun today: the box keeps the house's use and says why the roof is missing (plan, Task 9) */
  else todayCells += `<div><span class="k">Sun on this cell today</span><span class="fine">No forecast of the sun today: the forecast pack reads it from Open-Meteo, with FORECAST_OPENMETEO=1</span></div>`;
  if (td.roof_kwh != null) todayCells += td.measured
    ? `<div><span class="k">The roof today</span><span class="v">${num('energy.today.roof', fmt(td.roof_kwh, 1), 'measured by Home Assistant')} <small>kWh</small></span></div>`
    : `<div><span class="k">${td.panel_kw != null ? `${fmt(td.panel_kw, 1)} kW of roof panels` : 'Roof panels'}</span><span class="v">≈ ${num('energy.today.roof', fmt(td.roof_kwh, 1), 'modelled from today’s sun, ENERGY_PANEL_KW and ENERGY_PANEL_PR')} <small>kWh today</small></span></div>`;
  if (td.use_kwh != null) todayCells += `<div><span class="k">The house uses about</span><span class="v">${num('energy.today.use', fmt(td.use_kwh, 1), 'ENERGY_HOUSE_KWH_DAY, set by hand')} <small>kWh a day</small></span></div>`;
  if (hh) {
    if (hh.roof_w != null) todayCells += `<div><span class="k">This house · roof now</span><span class="v">${num('energy.home.roof_w', fmt(hh.roof_w, 0), 'live solar power')} <small>W</small></span></div>`;
    if (hh.grid_w != null) todayCells += `<div><span class="k">This house · grid now</span><span class="v">${num('energy.home.grid_w', fmt(hh.grid_w, 0), 'live grid import')} <small>W</small></span></div>`;
    if (hh.fossil_pct != null) todayCells += `<div><span class="k">This house · fossil share</span><span class="v">${num('energy.home.fossil_pct', fmt(hh.fossil_pct, 0) + '%', 'against the grid mix')}</span></div>`;
  } else {
    todayCells += `<div><span class="k">This house</span><span class="fine">No roof panels or home meter connected</span></div>`;
  }
  const pw = measured ? (sh.stale ? 'cached' : 'live') : 'model';
  const attr = (E.attribution || []).map(esc).join(' · ');
  el.innerHTML = head
    + `<p class="sent said">${parts.join(' ')}</p>`
    + `<div class="mixbar" role="img" aria-label="Grid electricity mix">${barSegs}</div>`
    + `<div class="legend">${legend}</div>`
    + `<div class="sources">${srcRows}</div>`
    + `<div class="today">${todayCells}</div>`
    + `<div class="provline">${prov(pw)}${attr ? `<span>${attr}</span>` : ''}<span>Nothing asked · context issue</span></div>`;
}
function drawNow() {
  /* a phone draws the day alone and the week as one row a day it can press (weekRows): 13 px cells are no target */
  const phone = innerWidth <= 480, isEnergy = S.issue === 'energy', ep = $('#energy');
  if (ep) ep.hidden = !isEnergy;
  $('#svg').style.display = isEnergy ? 'none' : '';
  if (isEnergy) {
    $('#week').hidden = true;
    $('#fighead').textContent = ''; $('#figline').innerHTML = '';
    if (ep) drawEnergy(ep, (D && D.energy) || ENERGY);
    loadEnergy();
  } else {
    dayWeek({ el: $('#svg'), issue: S.issue, head: $('#fighead'), scale: $('#figline'), week: !phone, pick: j => { S.i = j; drawNow(); } });
    $('#week').hidden = !phone; if (phone) weekRows($('#week'));
  }
  readout(); nowRemember();
}

/* The week on a phone: one button a day, its 24 hours a strip (over the line red, a missing hour left empty) and
   its hours over the line, the count /issues/days gives. Pressing a day moves the moment to that day, same hour. */
function weekRows(el) {
  const k = S.issue, it = D.issues[k], sd = (it.series || {})[it.hero_distance] || [], h0 = hourOf(D.buckets[S.i]), cur = dayOf(D.buckets[S.i]);
  const lo = d3.min(sd) ?? 0, top = Math.max(it.line ?? 0, d3.max(sd) ?? 0), span = top - lo || 1;   /* shaded from the week's own low, as the drawing's strip */
  el.innerHTML = D.dates.map(dt => {
    const pd = (it.per_day || []).find(p => p.date === dt), cells = d3.range(24).map(h => { const j = D.at[dt + '|' + h], v = j == null ? null : sd[j];
      const over = it.line != null && v > it.line;   /* over the line: an ink cell with a red tick, never a red fill */
      return v == null ? '' : `<rect x="${h * 10 + .5}" y="0" width="9" height="14" fill="currentColor" opacity="${over ? .9 : (.1 + .75 * (v - lo) / span).toFixed(2)}"/>`
        + (over ? `<rect x="${h * 10 + .5}" y="0" width="9" height="3" fill="var(--signal-worse)"/>` : ''); }).join('');
    return `<button data-d="${dt}" aria-pressed="${dt === cur}"><span>${esc(dLabel(dt).split(' ').slice(0, 2).join(' ').replace(',', ''))}</span><svg viewBox="0 0 240 14" preserveAspectRatio="none" aria-hidden="true">${cells}</svg>`
      + `<span class="o">${pd ? num(`${k}.over.${dt}`, pd.over ? `${pd.over} h` : '0', `hours over the line, of ${pd.read} read`) : ''}</span></button>`;
  }).join('');
  el.querySelectorAll('button').forEach(b => b.onclick = () => {
    const d = b.dataset.d, js = d3.range(24).map(h => D.at[d + '|' + h]).filter(j => j != null);
    const j = D.at[d + '|' + h0] ?? js[js.length - 1]; if (j != null) { S.i = j; drawNow(); }
  });
}

function readout() {
  const k = S.issue, it = D.issues[k], i = S.i, b = D.buckets[i], dp = it.dp, U = it.unit, isNow = i === D.now, hd = it.hero_distance || 'region';
  const w = (it.provenance || {})[hd] || ((it.stack || {})[hd] || {}).provenance || 'model';
  $('#kick').innerHTML = isNow ? `Right now · ${said(it.name)} at <span class="mono">${hhmm(b)}</span> ${prov(w)}`
    : `${said(it.name)} · ${esc(dLabel(dayOf(b)))} at <span class="mono">${hhmm(b)}</span> ${prov(w)} · ${D.now - i} hour${D.now - i === 1 ? '' : 's'} ago`;
  $('#back').hidden = isNow;
  const cell = D.health.cell || {}, rung = D.geometry.ladder.find(l => l.res === cell.res);
  $('#cellink').innerHTML = cell.edge_m && rung ? `${cell.edge_m} m · ${fmt(rung.own_area_m2 / 1e6, 2)} km² ›` : '';
  const cmp = it.line != null ? `against the line, ${fmt(it.line, dp)} ${U}` : 'this issue has no line';
  const n = x => num(`${k}.${hd}`, x, cmp, `<b class="numf">${esc(x)}</b>`);
  let s, tag = '';
  if (isNow) {
    /* the split, same as the wall's: the title is the sentence's qualitative head — no number, no
       indicator — and the tagline explains it, smaller and not bold. Older nodes send no title:
       the sentence stands in, its first figure marked as before. */
    s = esc(it.title || it.sentence).replace(/(\d+(?:\.\d+)?)(?=\s*(?:°C|µg|%|m\b))/, (m0) => n(m0));
    tag = it.tagline || '';
  }
  else {
    /* a past hour speaks the engine's words too (hours[i]): what it was doing, then the reading and whose
       line. A capture older than the hours key has none, and says only that nothing is here to read. */
    const h = (it.hours || [])[i];
    s = h ? esc(h[0]) : `<span class="gone">Nothing was recorded at ${hhmm(b)}.</span>`;
    tag = h ? h[1] : '';
  }
  $('#sentence').innerHTML = (it.pix ? `<svg class="pix" aria-hidden="true"><use href="${NODE}signs.svg#${it.pix}"/></svg>` : '') + `<span class="said">${s}${tag ? `<span class="ntag">${esc(tag)}</span>` : ''}</span>`;
  /* the four distances, one quiet line: the drawing above already draws three of them */
  /* the four distances as an encoder bank (Field Synthesizer variation, after the export's "spatial ladder"): a dial a
     distance, its sweep the figure against a scale shared by all four, a red tick where the line is, the sweep red
     only past it. The stroke is the figure's own: the house solid, the street dashed, the ring dotted, the region
     sparse. Same numbers, same words, same provenance as the line it replaces. */
  const DK = ['room', 'yard', 'ring', 'region'], xs = DK.map(dk => isNow ? (it.stack[dk] || {}).value : val(k, dk, i));
  const KS = Math.max(it.line != null ? it.line * 1.5 : 0, ...xs.filter(v => v != null).map(v => v * 1.15), 1);   /* the dials' shared scale */
  const R = 38, A0 = 135, SW = 270, pt = f => { const a = (A0 + SW * f) * Math.PI / 180; return [50 + R * Math.cos(a), 50 + R * Math.sin(a)]; };
  const arc = f => { const [x0, y0] = pt(0), [x1, y1] = pt(Math.max(.001, Math.min(1, f))); return `M${x0.toFixed(1)},${y0.toFixed(1)} A${R},${R} 0 ${SW * f > 180 ? 1 : 0} 1 ${x1.toFixed(1)},${y1.toFixed(1)}`; };
  const DASH = { room: '', yard: '7 3', ring: '2.5 3', region: '1.5 6' };
  $('#ladder').innerHTML = DK.map((dk, n) => {
    const x = xs[n], st = it.stack[dk] || {}, pw = (it.provenance || {})[dk] || st.provenance, hourly = (it.series || {})[dk], over = it.line != null && x != null && x > it.line;
    const tick = it.line != null ? (() => { const [a, c] = [pt(it.line / KS), [50 + (R - 7) * Math.cos((A0 + SW * it.line / KS) * Math.PI / 180), 50 + (R - 7) * Math.sin((A0 + SW * it.line / KS) * Math.PI / 180)]]; return `<line x1="${a[0].toFixed(1)}" y1="${a[1].toFixed(1)}" x2="${c[0].toFixed(1)}" y2="${c[1].toFixed(1)}" stroke="var(--signal-worse)" stroke-width="2"/>`; })() : '';
    return `<div class="knob d ${x == null ? 'none' : ''}"><span class="kh"><span class="x">${said(D.labels[dk])}</span>${x == null ? `<span class="gap">${hourly ? 'not recorded' : (isNow ? 'none' : 'no hours')}</span>` : prov(pw)}</span>`
      + `<svg viewBox="0 0 100 100" aria-hidden="true"><path d="${arc(1)}" fill="none" stroke="var(--wire)" stroke-width="7"/>`
      + (x == null ? '' : `<path d="${arc(x / KS)}" fill="none" stroke="${over ? 'var(--signal-worse)' : `var(--d-${{ air: 'air', heat: 'heat', coast: 'sea', land: 'ground', water: 'water', energy: 'energy' }[k] || 'air'})`}" stroke-width="7" stroke-dasharray="${DASH[dk]}"/>`) + tick
      + `<text x="50" y="54" text-anchor="middle" font-family="JetBrains Mono, monospace" font-size="17" font-weight="600" fill="var(--ink)">${x == null ? '—' : fmt(x, dp)}</text>`
      + `<text x="50" y="68" text-anchor="middle" font-family="JetBrains Mono, monospace" font-size="9" fill="var(--mute)">${x == null ? '' : said(U)}</text></svg>`
      + `<span class="kf">${isNow && st.source ? said(st.source) : '&nbsp;'}</span></div>`;
  }).join('');
  /* the same four figures as the screen's header ramp (evolution variation): the distance and its word, the value and
     where it came from */
  /* the screen's readout strip (Field Synthesizer variation, after the export's VALUE PEAK / CURRENT readouts): the
     day's peak at the hero distance, the figure now, the line, and the hours over it today */
  const ramp = $('#nramp'), day = dayOf(b), sd = (it.series || {})[hd] || [];
  if (ramp) {
    let pk = null, ph = null; for (let h = 0; h < 24; h++) { const j = D.at[day + '|' + h], v = j == null ? null : sd[j]; if (v != null && (pk == null || v > pk)) { pk = v; ph = h; } }
    const xh = isNow ? (it.stack[hd] || {}).value : val(k, hd, i), sth = it.stack[hd] || {}, pd = (it.per_day || []).find(p => p.date === day);
    ramp.style.setProperty('--n', 4); ramp.innerHTML = rampHTML([
      ['peak · today', pk == null ? '—' : fmt(pk, dp), pk == null ? '' : said(U), said(D.labels[hd]), ph == null ? '' : `at ${String(ph).padStart(2, '0')}:00`, it.line != null && pk != null && pk > it.line ? 'warm' : ''],
      [`${isNow ? 'now' : hhmm(b)} · ${said(D.labels[hd])}`, xh == null ? '—' : fmt(xh, dp), xh == null ? '' : said(U), esc((it.provenance || {})[hd] || sth.provenance || ''), isNow && sth.source ? said(sth.source) : '', it.line != null && xh != null && xh > it.line ? 'warm' : 'sig'],
      ['the line', it.line == null ? 'none' : fmt(it.line, dp), it.line == null ? '' : said(U), 'it asks above it', it.line == null ? 'it only reports' : ''],
      ['over · today', pd ? String(pd.over) : '—', pd ? 'h' : '', 'hours read', pd ? `${pd.read} of ${pd.of}` : '', pd && pd.over ? 'warm' : '']]);
  }
  const info = $('#ninfo'), hw = (it.provenance || {})[hd] || ((it.stack[hd] || {}).provenance) || '';
  if (info) info.innerHTML = `<span>${isNow ? 'Now' : 'At'} · ${esc(D.node.name)} · ${esc(dLabel(dayOf(b)))} ${hhmm(b)}${hw ? ` · ${esc(hw)}` : ''}</span><span>${said(it.name)} · ${said(D.labels[hd] || '')}${it.line != null ? ` · the line ${fmt(it.line, dp)} ${said(U)}` : ''}</span>`;
  decision(); rowsValues();
}

/* WHAT TO DO: the decision of the moment (learn: buttons). The three answers are the node's own words. At the live
   hour, whether something is asked is the node's one answer (/issues asking), the one the Wall reads: an event still
   asking, else an alert still true. On 14 Oct this read the events alone and said "No event was open for air" beside a
   Wall showing an open ask. A past hour is history: the events open then. The frame (.decide) and the buttons are
   drawn only while something is asked; otherwise What to do is one plain line, with the hour it is usually worst. */
function decision() { decideLine(); stripFold(); }
function decideLine() {
  const k = S.issue, it = D.issues[k], B = D.buttons, live = S.i === D.now, ask = live ? (it.asking || [])[0] : null;
  const head = '<h2 class="nh">What to do</h2>', usual = live ? usualLine(k) : '';
  const line = `<p class="dm">${it.line != null ? `the line <span class="mono">${fmt(it.line, it.dp)}</span> ${said(it.unit)} · ${said(it.line_source || '')}` : 'There is no limit for this, so the node only reports it. It never asks you to act.'}</p>`;
  let evs = ask && ask.event_id != null ? D.events.filter(e => e.id === ask.event_id) : [];
  if (ask && !evs.length) {
    /* an alert still true that no event stands for (answered on Telegram), or an event this screen has no row for */
    /* the node's own words say when it was asked (Wall and phone say the same), so the head names only the issue */
    $('#decide').innerHTML = head + `<div class="decide"><p class="nk">${said(it.name)}</p>`
      + `<p class="dq">${ask.says ? said(ask.says) : `asked at <span class="mono">${hhmm(ask.since)}</span>`}</p>${ask.how ? `<p class="dm">${said(ask.how)}</p>` : ''}` + line + `</div>`;
    return;
  }
  if (!evs.length) evs = evAt(k, S.i);
  if (!evs.length) {
    $('#decide').innerHTML = head + (live ? `<p class="nothing">Nothing is asked now. ${usual ? `<span class="x">${usual}</span>` : ''}</p>`
      : `<p class="nothing">Nothing was asked about ${said(it.name.toLowerCase())} at <span class="mono">${hhmm(D.buckets[S.i])}</span>.</p>`);
    return;
  }
  const e = evs[0], a = answerWords(e.answer), on = { acted: 'done', acknowledged: 'not_now', dismissed: 'doesnt_fit' }[(e.answer || {}).stage];
  /* an answer is taken only for an event still open, at the live hour: a past hour is read, never answered */
  const asking = live && !e.cleared_at && (e.asking || !!ask);
  const what = `${said(it.name)} · ${esc(kindWord(e.kind))} since <span class="mono">${hhmm(e.opened_at)}</span>${e.cleared_at ? ` · cleared <span class="mono">${hhmm(e.cleared_at)}</span>` : e.answer ? ' · answered, watching until it clears' : ' · still open'}`
    + `${e.peak != null ? ` · peak ${num(`${k}.event.peak`, fmt(e.peak, it.dp), `the line ${fmt(it.line, it.dp)} ${it.unit}`)} ${said(it.unit)}` : ''}`;
  const told = `<p class="dm">${sign(a.closed ? 'sign-rho-closed' : 'sign-rho-open', a.closed ? 'closed' : '')} ${esc(a.w)}${(e.rooms || []).length ? ` · ${e.rooms.length} room${e.rooms.length === 1 ? '' : 's'}: ${said(e.rooms.map(r => r.trim()).join(', '))}` : ''}</p>`;
  if (!asking) {
    /* answered, cleared, or a past hour: nothing is asked now, so no frame and no buttons; the event is said quietly */
    $('#decide').innerHTML = head + (live ? `<p class="nothing">Nothing is asked now. ${usual ? `<span class="x">${usual}</span>` : ''}</p>` : '')
      + `<p class="dm">${what}: ${said(e.action || 'the node asked for nothing specific.')}</p>` + told;
    return;
  }
  $('#decide').innerHTML = head + `<div class="decide"><p class="nk">${what}</p>`
    + `<p class="dq">${said(e.action || 'The node asked for nothing specific.')}</p>`
    /* the buttons only while the node is still asking (e.asking, from the node): once somebody answered they go, and
       the line below says who and when. A past hour is read, never answered, so it shows none either. */
    + `<div class="ans" role="group" aria-label="Answer">${['done', 'not_now', 'doesnt_fit'].map(b => `<button class="${on === b ? 'on' : ''}" data-ev="${e.id}" data-stage="${ANSWER_STAGE[b]}">${said(B[b])}</button>`).join('')}</div>`
    + `<p class="dm" id="answered" role="status"></p>` + told + `</div>`;
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
    if (!r.ok) { out.textContent = r.status === 401 || r.status === 403 ? WORDS.locked : said_; b.disabled = false; return; }
    out.textContent = b.dataset.stage === 'acknowledged' ? 'Not now. The node holds this for three hours, unless it reaches danger.' : 'Recorded.';
    await nowAgain();
  } catch (e) { out.textContent = WORDS.noreply; b.disabled = false; }
});
/* after an answer, the node is asked again and Now redrawn; what this page worked out itself is kept */
async function nowAgain() {
  D = await loadD().then(d => Object.assign(d, { learn: D.learn, dates: D.dates, at: D.at, now: D.now, sens: D.sens, ngeo: D.ngeo })); VIEWS.now();
}

/* WHAT A PACK ASKS (app/buttons.py): a rule may send its alert with buttons, which the bot draws as a keyboard. Now
   draws the same answers under What to do and writes them the same way, POST /actions {alert_id, choice}. Still asked
   is an alert of the last 72 hours (after that the node answers 409, "this question has closed") with a row nobody
   answered: a row goes once anybody pressed one of its buttons, and an acknowledged button answers the whole alert,
   as on Telegram. /alerts and /actions are token-only, so a screen without the token draws nothing here. */
function asksFrom(alerts, actions, now) {
  return (alerts || []).flatMap(a => {
    if (!(a.buttons || []).length || now - Date.parse(a.ts) > 72 * 36e5) return [];
    const all = a.buttons.flat(), said = (actions || []).filter(x => x.alert_id === a.id && x.choice), hit = b => said.some(x => x.choice === b.value);
    if (all.some(b => b.stage === 'acknowledged' && hit(b))) return [];
    const rows = a.buttons.filter(r => !r.some(hit));
    return rows.length ? [{ alert: a, rows, answers: said.map(x => ({ ...x, button: all.find(b => b.value === x.choice) || null })) }] : [];
  });
}
/* a pack's words in the page's locale, else English, else the first it wrote (buttons.pick) */
function packWord(w, lc) {
  const x = w || {};
  return x[lc] || x.en || Object.values(x)[0] || '';
}
function drawAsks() {
  const el = $('#asks'), f = el.querySelector('form');
  /* the words somebody is typing outlive a redraw: Now redraws on every resize, and a phone's keyboard is one */
  if (f && (f.contains(document.activeElement) || f.note.value)) return;
  const lc = D.locale, asks = asksFrom(D.alerts, D.actions, Date.now());
  el.hidden = !asks.length;
  el.innerHTML = asks.map(({ alert: a, rows, answers }) => {
    const t = String(a.text || '').split('\n'), text = t.slice(0, 6).join('\n') + (t.length > 6 ? '\n…' : '');
    return `<div class="decide"><p class="nk">${said(String(a.rule_id || '').split('/')[0])} · asked ${esc(wdhm(a.ts))}</p>`
      + `<p class="said">${esc(text).replace(/\n/g, '<br>')}</p>`
      + rows.map(r => `<div class="ans" role="group" aria-label="Answer">${r.map(b => `<button data-al="${a.id}" data-v="${esc(b.value)}"${b.ask ? ` data-ask="${esc(packWord(b.ask, lc))}"` : ''}>${said(packWord(b.text, lc))}</button>`).join('')}</div>`).join('')
      /* a drawing tied to the alert on Place answers it as place.mark:<id> (app/maps.py tie): said in words */
      + answers.map(x => `<p class="dm">answered: ${esc(x.button ? packWord(x.button.text, lc) : /^place\.mark:/.test(x.choice) ? 'a drawing on Place' : x.choice)}${x.actor ? ` by ${esc(x.actor)}` : ''} at ${esc(hhmm(x.ts))}${x.note ? ` · “${esc(x.note)}”` : ''}</p>`).join('')
      + `<p class="dm" role="status"></p></div>`;
  }).join('');
  stripFold();
}
/* WHAT TO DO FOLDED (Tomas, 9 Nov: "the act should be just one line collapsed, and there should be a button to unfold
   and see the options to act"): the strip shows its head and one sentence; the button counts what can be answered
   (the Decide card's buttons, each pack ask) and opens the rest. Open or folded holds for the visit, through redraws. */
let NFOLD_OPEN = false;
function stripFold() {
  const s = $('.nstrip'), d = $('#decide'); if (!s || !d) return;
  const n = d.querySelectorAll('.ans').length + $('#asks').querySelectorAll('.decide').length;
  const more = n || d.querySelector('.dm') || !$('#ndecl-decide').hidden;
  s.classList.toggle('open', NFOLD_OPEN && !!more);
  const b = d.querySelector('.nfold') || d.appendChild(Object.assign(document.createElement('button'), { type: 'button', className: 'nfold' }));
  b.hidden = !more; b.setAttribute('aria-expanded', String(NFOLD_OPEN));
  b.textContent = NFOLD_OPEN ? 'Fold ↑' : n ? `Options to act · ${n} ↓` : 'More ↓';
}
document.addEventListener('click', ev => {
  if (!(ev.target.closest && ev.target.closest('#decide .nfold'))) return;
  NFOLD_OPEN = !NFOLD_OPEN; stripFold();
});
function actorHere() {
  try { return localStorage.getItem('planetai_actor') || ''; } catch (e) { return ''; }   /* no storage here */
}
/* one answer to a pack's alert, as the bot sends it; returns the node's refusal in words, or '' when it took it */
async function askAnswer(alertId, choice, note) {
  try {
    const r = await fetch('/actions', { method: 'POST', headers: { 'content-type': 'application/json', ...DOORS_AUTH() },
      body: JSON.stringify({ alert_id: Number(alertId), choice, actor: actorHere(), note }) });
    if (r.ok) return '';
    return r.status === 401 || r.status === 403 ? WORDS.locked : ((await r.json().catch(() => ({}))).detail || `the node refused it (${r.status})`);
  } catch (e) { return WORDS.noreply; }
}
/* an answer the node took, kept on the page until the next load brings it back from /actions: a redraw before then
   draws its row as answered */
function askTaken(alertId, choice, actor) {
  const a = (D.alerts || []).find(x => x.id === Number(alertId)), b = ((a && a.buttons) || []).flat().find(x => x.value === choice);
  D.actions = [{ ts: new Date().toISOString(), alert_id: Number(alertId), stage: (b && b.stage) || 'acted', actor, note: null, choice }, ...(D.actions || [])];
}
/* a press answers; a button that asks something then shows one line for the words, sent with the same choice */
document.addEventListener('click', async ev => {
  const b = ev.target.closest && ev.target.closest('#asks button[data-al]');
  if (!b || b.disabled) return;
  const box = b.closest('.decide'), out = box.querySelector('[role=status]'); b.disabled = true;
  const no = await askAnswer(b.dataset.al, b.dataset.v, '');
  if (no) { out.textContent = no; b.disabled = false; return; }
  askTaken(b.dataset.al, b.dataset.v, actorHere());
  if (b.dataset.ask == null) return nowAgain().catch(() => { out.textContent = WORDS.noreply; });
  box.querySelectorAll('.ans').forEach(g => g.remove());
  out.insertAdjacentHTML('beforebegin', `<p class="dm">${said(b.dataset.ask)}</p><form class="ans" data-al="${esc(b.dataset.al)}" data-v="${esc(b.dataset.v)}">`
    + `<input name="note" maxlength="500" aria-label="${esc(b.dataset.ask)}" required><button>Send</button></form>`);
  box.querySelector('form input').focus();
});
/* leaving Now leaves an unsent note behind: coming back draws from what the node said */
window.addEventListener('hashchange', () => { if (view() !== 'now') $('#asks').innerHTML = ''; });
document.addEventListener('submit', async ev => {
  const f = ev.target.closest && ev.target.closest('#asks form[data-al]');
  if (!f) return;
  ev.preventDefault();
  const out = f.closest('.decide').querySelector('[role=status]'), s = f.querySelector('button'); s.disabled = true;
  const no = await askAnswer(f.dataset.al, f.dataset.v, f.note.value.trim());
  if (no) { out.textContent = no; s.disabled = false; return; }
  f.remove();   /* sent: the redraw draws from the node again (a form left with its words would be kept) */
  await nowAgain().catch(() => { out.textContent = WORDS.noreply; });
});

/* BANDS A PACK DECLARES (docs/PACKS.md, A declared section): drawn by declaredBands() in doors-load.js, which the
   phone page shares. Each sits beside the part of Now of the same stage (Tomas, 31 Oct): observe under the issue rows,
   decide and act under What to do (Now has no act part of its own), measure under Did it work. */
function drawDeclared() {
  const at = declaredBands(D.sections);
  for (const m of ['observe', 'decide', 'measure']) { const el = $('#ndecl-' + m); el.innerHTML = at[m] || ''; el.hidden = !at[m]; }
  $('#alsoread').hidden = !at.observe;   /* the observe bands have a row of their own, under both columns */
}

/* Around the house: the issues drawn by the hour, one row each; a row moves the page to that issue. Land and Coast
   change yearly and have no hours, so they are not here: Place says them, beside the ground (doors-place.js). */
function rows() {
  $('#rows').innerHTML = D.order.filter(k => ISSUES_DRAWN(k) || (k === 'energy' && ((D.issues[k].stack || {}).region || {}).value != null)).map(k => {
    const it = D.issues[k];
    return `<button class="row" data-k="${k}" data-kind="readout" aria-pressed="false"><span><span class="n">${said(it.name)}</span><span class="state ${it.state === 'act' ? 'act' : ''}">${esc(stateWord(it.state))}</span></span>`
      + `<span class="v" data-v></span><span class="sub" data-s></span></button>`;
  }).join('');
  document.querySelectorAll('#rows .row').forEach(b => b.onclick = () => { S.issue = b.dataset.k; drawNow(); });
}
function rowsValues() {
  const date = dayOf(D.buckets[S.i]);
  document.querySelectorAll('#rows .row').forEach(r => {
    const k = r.dataset.k, it = D.issues[k], hd = it.hero_distance || 'region';
    r.setAttribute('aria-pressed', String(k === S.issue));
    // now is the live reading the title and the legend say, not the running hour's mean (audit, 15 Oct: 17 beside 10)
    const v = S.i === D.now || !it.hero_distance ? ((it.stack || {})[hd] || {}).value : val(k, hd, S.i), pd = (it.per_day || []).find(p => p.date === date);
    r.querySelector('[data-v]').innerHTML = `${num(`${k}.${hd}`, fmt(v, it.dp), `against the line, ${fmt(it.line, it.dp)} ${it.unit}`)}<small>${said(it.unit)}</small>`;
    r.querySelector('[data-s]').innerHTML = pd ? `${pd.over ? '<span class="over" aria-hidden="true"></span>' : ''}${num(`${k}.over.day`, pd.over, `of ${pd.read} hours read, ${pd.of - pd.read} not recorded`)} h over the line ${date === dayOf(D.buckets[D.now]) ? 'today' : 'on ' + dLabel(date).split(',')[0]} · ${pd.read} of ${pd.of} h read` : (k === 'energy' && (it.tagline || it.sentence) ? said(it.tagline || it.sentence) : 'no count for this day');
  });
}

/* Who reads around this house, now, on the node's own street map (MapLibre for the base, deck.gl for the stations,
   as on Place). Each station at the point /sensors gives this screen, its 15-minute mean beside it (GET /stats, as the
   wall reads it); the house's own sensors as one dot at the node's point with their range. Over the air line, a red
   square. A station pressed opens it in Data. Without WebGL it falls back to the rose. */
let NOWMAP = null;
async function aroundMap(el) {
  /* the register of the screen it sits on, when it sits on one (evolution variation), else the page's; its colours too */
  const rgba = (v, a = 1) => window.rgba(v, a, el);
  const theme = (el.closest('[data-theme]') || document.documentElement).dataset.theme || 'light', W = Math.min(360, el.parentNode.clientWidth), H = Math.round(W * 0.75);   /* a floor: the frame grows it to the day's screen (9 Nov: with the Index under it, 1.05 overran the screen) */
  if (!window.maplibregl || !window.deck || !window.groundBase) return rose(el, { size: W });
  const M = 'pm25', line = (D.issues.air || {}).line, now15 = id => ((D.stats15[id] || {})[M] || [])[0] ?? null;
  const all = D.sensors.filter(s => s.lat != null && s.lon != null && s.source !== 'openstreetmap');
  const house = all.filter(s => s.local && s.kind === 'sensor'), hv = house.map(s => now15(s.sensor_id)).filter(v => v != null);
  const out = all.filter(s => !s.local && (s.kind === 'sensor' || s.kind === 'facility'))
    .map(s => ({ ...s, p: [s.lon, s.lat], v: s.kind === 'sensor' ? now15(s.sensor_id) : null }));
  const sea = all.find(s => s.sensor_id === 'marine-point'), C = (k, a = 1) => rgba(k, a);
  const base = await window.groundBase(theme);
  if (!NOWMAP || NOWMAP.theme !== theme || !el.contains(NOWMAP.map.getContainer())) {
    if (NOWMAP) NOWMAP.map.remove();
    el.innerHTML = `<div class="aroundmap" style="width:${W}px;min-height:${H}px"></div>`;
    let map; try { map = new maplibregl.Map({ container: el.firstChild, style: base.style, center: D.point, zoom: 11, attributionControl: false,
      dragRotate: false, pitchWithRotate: false, touchPitch: false, scrollZoom: false, fadeDuration: 0, transformRequest: window.groundRequest }); } catch (e) { NOWMAP = null; return rose(el, { size: W }); }   /* no WebGL: the rose */
    map.touchZoomRotate.disableRotation();
    new ResizeObserver(() => map.resize()).observe(el.firstChild);   /* the frame stretches it to the screen beside it */
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
      const ask = q => doorsFetch('/' + q).then(r => r.ok ? r.json() : null).catch(() => null);
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
      getText: () => `this house · ${house.length} sensor${house.length === 1 ? '' : 's'}${hv.length ? ` · ${fmt(d3.min(hv), 0)}–${fmt(d3.max(hv), 0)} ${unitOf(M)}` : ''}` }),
  ] });
  NOWMAP.paint();
  /* one line (Tomas, 15 Oct): what is drawn and what a press does; faint is a station not heard in 15 minutes */
  $('#rosecap').innerHTML = `${said(labelOf(M))} now at ${out.filter(s => s.v != null).length} public stations and ${house.length} in this house; press one to open it in Data.`
    + (base.street ? ' <span class="x">Map: OpenStreetMap contributors · Protomaps.</span>' : ` <span class="x">Rings and cells: ${UNLOCK_AT}.</span>`);
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

/* NOW · NEXT DAYS (docs/SPEC_next_days.md §5). GET /forecast?hours=72 (forecast-v0, packs/forecast/days.py) drawn as
   a row card per thing, in the order of Now's rows (air, heat), then wind and rain, the sea, then the packs' lines;
   three columns, the rest of today, tomorrow and the day after. A cell is the day's number with its comparison, the
   state word in ink, and for air and heat the hours over the line. A row pressed draws its 72 hours under it, with
   the line. The sources are pills, then one sentence: these are models. */
/* the page's words in the node's locale (/health locale); {x} is filled with HTML this file built */
const NX = {
  en: { now: 'Now', next: 'Next days', today: 'Today', tomorrow: 'Tomorrow', air: 'Air', heat: 'Heat', wind_rain: 'Wind and rain', sea: 'Sea',
    over: 'over', near: 'near', under: 'under', hover: '{h} h over {line}', peak: 'peak {v} at {t}', cells: 'over in {n} of {m} cells',
    gusts: 'gusts {v} km/h', rain: '{v} mm, most {t}', dry: 'no rain', waves: 'waves {v} m',
    issued: '{s}, issued {t}', fetched: '{s}, fetched {t}', ncells: '{n} cells', far: '{km} km from this node', absent: '{s}: nothing fetched yet',
    models: 'These come from models. The node does not forecast, and nothing here sends a message.',
    optin: 'Air, the sea and more hours come from Open-Meteo, which is off on this node. Turn it on in {setup}.',
    none: 'No forecast source answers for this place. Turn one on in {setup}.',
    waiting: 'No forecast has arrived on this node yet.', off: 'The forecast pack is off on this node. Turn it on in {setup}.',
    fail: 'The node gave no forecast just now. Try again, or look at the pack in {setup}.', h72: '{t}, the next 72 hours', nowmark: 'now' },
  es: { now: 'Ahora', next: 'Próximos días', today: 'Hoy', tomorrow: 'Mañana', air: 'Aire', heat: 'Calor', wind_rain: 'Viento y lluvia', sea: 'Mar',
    over: 'sobre', near: 'cerca', under: 'bajo', hover: '{h} h sobre {line}', peak: 'pico {v} a las {t}', cells: 'sobre la línea en {n} de {m} celdas',
    gusts: 'rachas {v} km/h', rain: '{v} mm, sobre todo {t}', dry: 'sin lluvia', waves: 'olas {v} m',
    issued: '{s}, emitido {t}', fetched: '{s}, descargado {t}', ncells: '{n} celdas', far: 'a {km} km de este nodo', absent: '{s}: nada descargado todavía',
    models: 'Esto viene de modelos. El nodo no pronostica, y nada de aquí envía un mensaje.',
    optin: 'El aire, el mar y más horas vienen de Open-Meteo, que está apagado en este nodo. Actívalo en {setup}.',
    none: 'Ninguna fuente de pronóstico responde para este lugar. Activa una en {setup}.',
    waiting: 'Todavía no ha llegado ningún pronóstico a este nodo.', off: 'El pack forecast está apagado en este nodo. Actívalo en {setup}.',
    fail: 'El nodo no dio un pronóstico ahora. Inténtalo de nuevo, o mira el pack en {setup}.', h72: '{t}, las próximas 72 horas', nowmark: 'ahora' },
  id: { now: 'Sekarang', next: 'Hari berikutnya', today: 'Hari ini', tomorrow: 'Besok', air: 'Udara', heat: 'Panas', wind_rain: 'Angin dan hujan', sea: 'Laut',
    over: 'di atas', near: 'dekat', under: 'di bawah', hover: '{h} jam di atas {line}', peak: 'puncak {v} pukul {t}', cells: 'di atas garis di {n} dari {m} sel',
    gusts: 'hembusan {v} km/h', rain: '{v} mm, terbanyak {t}', dry: 'tidak hujan', waves: 'ombak {v} m',
    issued: '{s}, terbit {t}', fetched: '{s}, diambil {t}', ncells: '{n} sel', far: '{km} km dari node ini', absent: '{s}: belum ada yang diambil',
    models: 'Ini berasal dari model. Node tidak membuat prakiraan, dan tidak ada yang di sini mengirim pesan.',
    optin: 'Udara, laut, dan lebih banyak jam berasal dari Open-Meteo, yang mati di node ini. Nyalakan di {setup}.',
    none: 'Tidak ada sumber prakiraan yang menjawab untuk tempat ini. Nyalakan satu di {setup}.',
    waiting: 'Belum ada prakiraan yang sampai di node ini.', off: 'Pack forecast mati di node ini. Nyalakan di {setup}.',
    fail: 'Node tidak memberi prakiraan sekarang. Coba lagi, atau lihat pack di {setup}.', h72: '{t}, 72 jam ke depan', nowmark: 'sekarang' },
};
const NX_SRC = { 'forecast-bmkg': 'BMKG', 'forecast-om': 'Open-Meteo', 'forecast-cams': 'CAMS', 'forecast-marine': 'Open-Meteo Marine' };
/* one day's cell of one row: every number a data-num with what it is against */
function nxCell(k, r, date, W) {
  const w = (s, o) => s.replace(/\{(\w+)\}/g, (m, x) => o[x] ?? m), id = `next.${k}.${date}`, t = x => `<span class="mono">${esc(x)}</span>`;
  if (k === 'sea') return w(W.waves, { v: num(id, fmt(r.value, 1), 'the day’s highest wave, no line') });
  if (k === 'wind_rain') return [r.gust != null ? w(W.gusts, { v: num(id + '.gust', fmt(r.gust, 0), 'the day’s highest gust, no line') }) : '',
    r.rain_mm ? (r.rain_hours ? w(W.rain, { v: num(id + '.rain', fmt(r.rain_mm, 1), 'the day’s total, no line'), t: t(r.rain_hours) })
      : `${num(id + '.rain', fmt(r.rain_mm, 1), 'the day’s total, no line')} mm`) : W.dry].filter(Boolean).join(' · ');
  const dp = k === 'air' ? 0 : 1, cmp = `the day’s ${r.of}, against the line, ${r.line} ${r.unit}`;
  return `<span class="v">${num(id, fmt(r.value, dp), cmp)}<small>${said(r.unit)}</small></span> <span class="state">${esc(W[r.state] || r.state)}</span>`
    + `<span class="sub">${r.hours_over ? '<span class="over" aria-hidden="true"></span>' : ''}`
    + w(W.hover, { h: num(id + '.over', r.hours_over, `of ${r.n} hours forecast`), line: num(id + '.line', r.line, `the ${k} issue’s line, ${r.unit}`) })
    + (r.peak != null ? ' · ' + w(W.peak, { v: num(id + '.peak', fmt(r.peak, dp), cmp), t: t(r.peak_at) }) : '')
    + (r.cells ? ' · ' + w(W.cells, { n: num(id + '.cells', r.cells_over, `of ${r.cells} cells`), m: num(id + '.of', r.cells, 'the cells this node forecasts') }) : '')
    + '</span>';
}
/* GET /forecast → what drawNext draws: { heads, rows, lines, sources, notes, empty }. `empty` is one line instead of
   the grid: the pack off ({ off: true }), a locked screen ({ locked: true }), no answer (null), or nothing forecast for
   this place yet */
function nextFrom(f, locale) {
  const W = NX[locale] || NX.en, w = (s, o) => s.replace(/\{(\w+)\}/g, (m, x) => o[x] ?? m);
  const setup = '<a href="#setup/packs">Set up → Packs → forecast</a>', none = { heads: [], rows: [], lines: [], sources: [], notes: [], empty: null };
  if (!f) return { ...none, empty: w(W.fail, { setup }) };
  if (f.off) return { ...none, empty: w(W.off, { setup }) };
  if (f.locked) return { ...none, empty: `${esc(WORDS.locked)} ${UNLOCK_AT}` };
  const days = (f.days || []).slice(0, 3), hours = f.hours || [], out = { ...none };
  out.heads = days.map((d, i) => ({ date: d.date, word: d.part === 'rest' ? W.today : i === 1 ? W.tomorrow : '', label: dLabel(d.date) }));
  for (const k of ['air', 'heat', 'wind_rain', 'sea']) {
    const first = days.map(d => (d.rows || {})[k]).find(Boolean);
    if (!first) continue;
    const mine = hours.filter(h => h.source === first.source);
    const metric = { air: 'fc_pm25', heat: 'apparent', sea: 'fc_wave_m' }[k] || (mine.some(h => h.fc_wind_gusts != null) ? 'fc_wind_gusts' : 'fc_rain');
    const pts = mine.filter(h => h[metric] != null).map(h => [h.ts, h[metric]]);
    out.rows.push({ key: k, title: W[k], src: NX_SRC[first.source] || first.source, cells: days.map(d => (d.rows || {})[k] ? nxCell(k, d.rows[k], d.date, W) : ''),
      series: pts.length > 1 ? { metric, unit: first.unit || { fc_wind_gusts: 'km/h', fc_rain: 'mm' }[metric], line: first.line ?? null, pts } : null });
  }
  out.lines = (f.lines || []).map(l => ({ id: l.id || l.pack, title: said(packWord(l.title, locale)),
    cells: days.map(d => (l.days || {})[d.date] ? said(packWord(l.days[d.date], locale)) : '') }));
  if (!out.rows.length && !out.lines.length) return { ...none, empty: (f.sources || []).length || f.openmeteo !== false ? W.waiting : w(W.none, { setup }) };
  const far = new Map((f.far_from_node || []).map(x => [x.sensor_id, x.km]));
  /* the sea is never in far_from_node (the classic card reads its first entry as the weather point), so its own distance comes from its source */
  const km = s => far.get(s.sensor_id) ?? (s.sensor_id === 'forecast-marine' && s.km_from_node > 10 ? s.km_from_node : null);
  out.sources = (f.sources || []).map(s => {
    const n = NX_SRC[s.sensor_id] || s.name || s.sensor_id, at = s.issued || s.fetched;
    if (s.absent) return `<span class="gap">${esc(w(W.absent, { s: n }))}</span>`;
    return `<span class="pill">${esc(at ? w(s.issued ? W.issued : W.fetched, { s: n, t: hhmm(at) }) : n)}`
      + `${s.cells > 1 ? ' · ' + w(W.ncells, { n: num(`next.cells.${s.sensor_id}`, s.cells, 'the cells this node forecasts') }) : ''}</span>`
      + (km(s) != null ? ` <span class="pill">${w(W.far, { km: num(`next.far.${s.sensor_id}`, Math.round(km(s)), 'more than 10 km is another place') })}</span>` : '');
  });
  out.notes = [W.models, ...(f.openmeteo === false ? [w(W.optin, { setup })] : [])];
  return out;
}
/* the forecast is kept 30 minutes, so Now's refresh does not ask again; no answer, a locked screen and the pack off are
   never kept, so the next drawing of Now asks again. `open` is the row whose 72 h show; `shown`, #now/next scrolled. */
const NX_FRESH = 30 * 60e3;
const NEXT = { p: null, at: 0, open: null, shown: false };
async function drawNext() {
  if (!NEXT.p || Date.now() - NEXT.at > NX_FRESH) { NEXT.p = loadForecast(); NEXT.at = Date.now(); }
  const f = await NEXT.p;
  if (!f || f.off || f.locked) NEXT.p = null;
  if (view() !== 'now') return;
  const el = $('#next'), x = nextFrom(f, D.locale);
  if (x.empty) { el.innerHTML = `<p class="nxempty">${x.empty}</p>`; return; }
  /* the heads are drawn for the eye; each cell says its own day to a screen reader */
  const day = x.heads.map(h => `<span class="vh">${esc(h.word ? `${h.word}, ${h.label}` : h.label)}: </span>`);
  const cols = cs => cs.map((c, i) => `<span class="nxc">${day[i] || ''}${c || '<span class="x">—</span>'}</span>`).join('');
  el.innerHTML = `<div class="nxhead" aria-hidden="true"><span></span>${x.heads.map(h => `<span>${h.word ? `<b>${esc(h.word)}</b> ` : ''}${esc(h.label)}</span>`).join('')}</div>`
    + x.rows.map(r => (r.series ? `<button class="row nrow" data-k="${r.key}" data-kind="readout" aria-pressed="${NEXT.open === r.key}">` : `<div class="row nrow decl" data-kind="readout">`)
      + `<span class="n">${esc(r.title)} <small class="nk">${esc(r.src)}</small></span>${cols(r.cells)}${r.series ? '</button>' : '</div>'}`
      + (r.series && NEXT.open === r.key ? nxSeries(r, el.clientWidth) : '')).join('')
    + x.lines.map(l => `<div class="row nrow decl" data-kind="readout"><span class="n">${l.title}</span>${cols(l.cells)}</div>`).join('')
    + `<p class="nxsrc">${x.sources.join(' ')}</p>` + x.notes.map(n => `<p class="fine">${n}</p>`).join('');
  /* a press redraws the grid; the focus stays on the row pressed, so a keyboard and a screen reader keep their place */
  el.querySelectorAll('button.nrow').forEach(b => b.onclick = () => { const k = b.dataset.k; NEXT.open = NEXT.open === k ? null : k;
    drawNext().then(() => { const n = el.querySelector(`button.nrow[data-k="${k}"]`); if (n) n.focus(); }); });
}
/* a row's 72 hours, under it: the series, its line dashed, "now" at the left, each local midnight a tick; an hour over
   the line a red tick on the floor (the mark carries the red, the words stay ink) */
function nxSeries(r, width) {
  const W = NX[D.locale] || NX.en, s = r.series, Wd = Math.max(280, width || 600), H = 150, L = 6, R = 6, T = 20, B = 22;
  const ts = s.pts.map(p => Date.parse(p[0])), vs = s.pts.map(p => p[1]), t0 = ts[0], t1 = ts[ts.length - 1];
  const hi = Math.max(...vs, s.line ?? -Infinity), lo = s.metric === 'apparent' ? Math.min(...vs, s.line ?? Infinity) - 2 : Math.min(0, ...vs);
  const x = t => L + (t - t0) / (t1 - t0 || 1) * (Wd - L - R), y = v => T + (hi - v) / (hi - lo || 1) * (H - T - B);
  const iPk = vs.indexOf(Math.max(...vs)), dp = s.metric === 'fc_wave_m' || s.metric === 'apparent' ? 1 : 0;
  let g = `<line x1="${L}" x2="${L}" y1="${T}" y2="${H - B + 4}" stroke="currentColor"/><text x="${L}" y="${H - 6}" class="lab">${esc(W.nowmark)}</text>`;
  g += s.pts.filter(p => hourOf(p[0]) === 0).map(p => { const X = x(Date.parse(p[0])).toFixed(1);
    return `<line x1="${X}" x2="${X}" y1="${T}" y2="${H - B + 4}" stroke="currentColor" stroke-opacity=".25"/>${X > L + 40 ? `<text x="${+X + 3}" y="${H - 6}">${esc(dLabel(dayOf(p[0])).split(',')[0])}</text>` : ''}`; }).join('');
  /* the line as the doors draw it everywhere: .linep, labelled by lineLab ("WHO 15" for the air) */
  if (s.line != null) g += `<line data-line class="linep" x1="${L}" x2="${Wd - R}" y1="${y(s.line).toFixed(1)}" y2="${y(s.line).toFixed(1)}"/>`
    + `<text x="${Wd - R}" y="${(y(s.line) - 4).toFixed(1)}" text-anchor="end" class="lab">${esc(lineLab({ ...((D.issues || {})[r.key] || {}), line: s.line }))}</text>`
    + s.pts.filter(p => p[1] > s.line).map(p => `<rect x="${(x(Date.parse(p[0])) - 1).toFixed(1)}" y="${H - B - 3}" width="2" height="3" fill="var(--signal-worse)"/>`).join('');
  g += `<path d="${s.pts.map((p, i) => `${i ? 'L' : 'M'}${x(ts[i]).toFixed(1)},${y(p[1]).toFixed(1)}`).join('')}" fill="none" stroke="currentColor" stroke-width="1.5"/>`
    + `<text x="${x(ts[iPk]).toFixed(1)}" y="${(y(vs[iPk]) - 5).toFixed(1)}" text-anchor="middle" class="num" data-num="next.${r.key}.max" data-cmp="${esc(s.line != null ? `the line ${s.line}` : 'no line')}">${fmt(vs[iPk], dp)}</text>`;
  const cap = W.h72.replace('{t}', r.title);
  return `<figure class="nxs" data-kind="series"><svg viewBox="0 0 ${Wd} ${H}" role="img" aria-label="${esc(cap)}">${g}</svg>`
    + `<figcaption class="fine">${esc(cap)} · ${esc(r.src)}${s.unit ? ` · ${said(s.unit)}` : ''}</figcaption></figure>`;
}

/* ============================================================================================================
   THE BOARD (Field Synthesizer variation, round 2, 7 Nov 2026). Tomas: "a grid where the empty spaces can be filled in
   with data feeds by having a + icon and selecting from a list of extra data coming from core or wild packs".
   A feed is any series this node holds, sensor by metric: the hourly means of the last 24 hours (D.raw, token) and the
   latest 15-minute mean (D.stats15), plus each reading a pack declares in a section (D.sections). Whatever pack wrote
   it, core or wild, it is drawn by the page's own four kinds below, so a wild pack still ships no script to this page
   and still gets a drawing, not only a number. Packs this node does not run are listed under them, greyed, with
   where to turn them on. The board is kept in this browser (localStorage); on a node it belongs in a setting, so the
   household shares one board.
   ============================================================================================================ */
const BOARD = { slots: { now: 8, node: 4, data: 4, place: 4 }, cat: null, pick: null };
/* what each door's board starts with: feeds the rest of that door does not draw. A slot whose feed this node lacks is a + */
const BDEF = {
  now: [['noise'], ['wind_speed'], ['precipitation'], ['lora_util_pct'], ['pressure'], ['light'], ['pm10']],   /* seven feeds and one +: a board, not a row of blanks */
  node: [['lora_util_pct'], ['lora_channel_pct'], ['battery_v', 'bme_iaq', 'pressure_model']],
  data: [['pm10'], ['pm1'], ['temp_model', 'humidity_model']],
  place: [['uv_index'], ['aod', 'dust'], ['precipitation']] };
const BDOM = m => /^(pm|aqi|iaq|bme_iaq|gas_|o3|no2|co$|dust|aod|fires|psi)/.test(m) ? 'air' : /^(temp|humid|dewpoint|apparent|wbgt)/.test(m) ? 'heat'
  : /^(precip|rain)/.test(m) ? 'water' : /^(sea|wave|swell|surf|beach)/.test(m) ? 'sea' : /^(wind|press|cloud|visib)/.test(m) ? 'wind'
  : /^noise/.test(m) ? 'noise' : /^(light|uv)/.test(m) ? 'light' : /^(lora|batt|solar|filter)/.test(m) ? 'energy' : /^(rice|land|built|green|tree|buildings|roads)/.test(m) ? 'ground' : 'biota';
const BWORD = m => ((D.metrics || {})[m] || {}).label || (typeof WORD !== 'undefined' && WORD[m]) || m.replace(/_/g, ' ');
const BUNIT = m => ((D.metrics || {})[m] || {}).unit || '';
function boardFeeds() {
  const out = [], seen = new Set(), sens = Object.fromEntries((D.sensors || []).map(s => [s.sensor_id, s])), ser = (D.raw || {}).series || {};
  const ids = new Set([...Object.keys(ser), ...Object.keys(D.stats15 || {})]);
  for (const id of ids) {
    const s = sens[id] || { sensor_id: id, name: id }, ms = new Set([...Object.keys(ser[id] || {}), ...Object.keys((D.stats15 || {})[id] || {})]);
    for (const m of ms) {
      if (/^fc_/.test(m)) continue;
      const v = (ser[id] || {})[m], series = v ? v.map(x => x ? x[0] : null) : null, now = (((D.stats15 || {})[id] || {})[m] || [])[0];
      out.push({ key: id + '|' + m, id, m, label: BWORD(m), unit: BUNIT(m), name: String(s.name || id).trim(), source: s.source || '',
        group: s.kind === 'model' ? 'Models for this point' : s.local ? 'This house' : 'Around it', prov: s.local ? 'live' : s.kind === 'model' ? 'model' : 'partial',
        series, now: now ?? (series ? series.filter(x => x != null).pop() : null), dom: BDOM(m) }); seen.add(id + '|' + m);
    }
  }
  /* what the models and the satellite say for this point, a value each (GET /observations): no hours, so a value tile */
  for (const o of D.observations || []) {
    const key = o.sensor_id + '|' + o.metric; if (seen.has(key) || typeof o.value !== 'number') continue; seen.add(key);
    out.push({ key, id: o.sensor_id, m: o.metric, label: BWORD(o.metric), unit: BUNIT(o.metric), name: String(o.name || o.sensor_id).trim(), source: '',
      group: 'Models for this point', prov: 'model', series: null, now: o.value, dom: BDOM(o.metric) });
  }
  for (const x of D.sections || []) for (const r of x.readouts || []) {
    const key = (r.sensor_id || x.id) + '|' + r.metric; if (seen.has(key)) { const f = out.find(o => o.key === key); if (f) f.group = 'Packs on this node', f.pack = x.pack; continue; }
    out.push({ key, id: r.sensor_id, m: r.metric, label: said(r.label || r.metric), unit: r.unit || '', name: said(x.title || x.pack), pack: x.pack, group: 'Packs on this node',
      prov: r.provenance || 'partial', series: null, now: r.value, dom: BDOM(r.metric) });
  }
  return out;
}
const BKIND = f => /precip|rain/.test(f.m) && f.series ? 'bars' : lineOf(f.m) != null && f.series ? 'dial' : f.series ? 'line' : 'value';
function lineOf(m) { for (const k of Object.keys(D.issues || {})) { const it = D.issues[k]; if (it.metric === m && it.line != null) return it.line; } return null; }
const bkey = door => 'planetai_board_v1_' + door;
function boardLoad(door) {
  const n = BOARD.slots[door] || 4; let b = null; try { b = JSON.parse(localStorage.getItem(bkey(door)) || 'null'); } catch (e) { b = null; }
  if (Array.isArray(b) && b.length === n) return b;
  const F = boardFeeds(), picked = [];
  for (const ms of BDEF[door] || []) { const f = ms.map(m => F.find(x => x.m === m && (x.series || x.now != null) && !picked.some(p => p && p.key === x.key))).find(Boolean); picked.push(f ? { key: f.key, kind: BKIND(f) } : null); }
  return picked.concat(Array(Math.max(0, n - picked.length)).fill(null)).slice(0, n);
}
function boardSave(door, b) { try { localStorage.setItem(bkey(door), JSON.stringify(b)); } catch (e) { /* this browser keeps nothing: the board lasts the visit */ } }
function tileSVG(f, kind, W = 300) {   /* W: a wide box draws at its own width, so its labels keep their size */
  const H = 120, s = (f.series || []).map(v => v == null ? null : +v), vv = s.filter(v => v != null), c = `var(--d-${f.dom})`, ln = lineOf(f.m);
  const mono = 'font-family="JetBrains Mono, monospace" font-size="11"';
  if (kind === 'value' || !vv.length) return `<svg viewBox="0 0 ${W} ${H}" aria-hidden="true"><text x="${W / 2}" y="${H / 2 + 8}" text-anchor="middle" font-family="JetBrains Mono, monospace" font-size="34" font-weight="600" fill="${c}">${f.now == null ? '—' : fmt(f.now, Math.abs(f.now) >= 100 ? 0 : 1)}</text><text x="${W / 2}" y="${H / 2 + 30}" text-anchor="middle" ${mono} fill="#A1A1AA">${esc(f.unit)}</text></svg>`;
  let lo = Math.min(...vv), hi = Math.max(...vv); if (ln != null) { lo = Math.min(lo, ln); hi = Math.max(hi, ln); } if (kind === 'bars') lo = Math.min(0, lo);
  const pad = (hi - lo || 1) * .12, y0 = lo - (kind === 'bars' ? 0 : pad), y1 = hi + pad, L = 8, R = 8, T = 14, B = 18, w = W - L - R, h = H - T - B;
  const x = i => L + i / Math.max(1, s.length - 1) * w, y = v => T + h - (v - y0) / (y1 - y0 || 1) * h;
  let o = `<svg viewBox="0 0 ${W} ${H}" aria-hidden="true" preserveAspectRatio="none">`;
  if (kind === 'dial') {
    const S = Math.max((ln ?? 0) * 1.5, hi * 1.15, 1), R0 = 44, cx = W / 2, cy = 62, A = f2 => { const a = (135 + 270 * Math.max(0, Math.min(1, f2))) * Math.PI / 180; return [cx + R0 * Math.cos(a), cy + R0 * Math.sin(a)]; };
    const arc = f2 => { const [a0, b0] = A(0), [a1, b1] = A(Math.max(.001, f2)); return `M${a0.toFixed(1)},${b0.toFixed(1)} A${R0},${R0} 0 ${270 * f2 > 180 ? 1 : 0} 1 ${a1.toFixed(1)},${b1.toFixed(1)}`; };
    const v = f.now ?? vv[vv.length - 1], over = ln != null && v > ln;
    o = `<svg viewBox="0 0 ${W} ${H}" aria-hidden="true"><path d="${arc(1)}" fill="none" stroke="#323236" stroke-width="8"/><path d="${arc(v / S)}" fill="none" stroke="${over ? 'var(--signal-worse)' : c}" stroke-width="8"/>`;
    if (ln != null) { const [a, b] = A(ln / S); o += `<circle cx="${a.toFixed(1)}" cy="${b.toFixed(1)}" r="3.5" fill="var(--signal-worse)"/><text x="${(a + 8).toFixed(1)}" y="${(b - 6).toFixed(1)}" ${mono} fill="#A1A1AA">line ${fmt(ln, 0)}</text>`; }
    return o + `<text x="${cx}" y="${cy + 6}" text-anchor="middle" font-family="JetBrains Mono, monospace" font-size="20" font-weight="600" fill="#F4F4F5">${fmt(v, Math.abs(v) >= 100 ? 0 : 1)}</text><text x="${cx}" y="${cy + 22}" text-anchor="middle" ${mono} fill="#A1A1AA">${esc(f.unit)}</text></svg>`;
  }
  if (ln != null) o += `<line x1="${L}" x2="${L + w}" y1="${y(ln)}" y2="${y(ln)}" stroke="var(--signal-worse)" stroke-dasharray="5 4" vector-effect="non-scaling-stroke"/>`;
  if (kind === 'bars') { const bw = w / s.length * .66; s.forEach((v, i) => { if (v != null && v > 0) o += `<rect x="${(x(i) - bw / 2).toFixed(1)}" y="${y(v).toFixed(1)}" width="${bw.toFixed(1)}" height="${(y(y0) - y(v)).toFixed(1)}" fill="${c}"/>`; });
    if (!vv.some(v => v > 0)) o += `<text x="${W / 2}" y="${H / 2}" text-anchor="middle" ${mono} fill="#A1A1AA">none in 24 h</text>`; }
  else { o += `<polyline points="${s.map((v, i) => v == null ? null : `${x(i).toFixed(1)},${y(v).toFixed(1)}`).filter(Boolean).join(' ')}" fill="none" stroke="${c}" stroke-width="1.8" vector-effect="non-scaling-stroke" stroke-linejoin="round"/>`;
    const li = s.map((v, i) => [v, i]).filter(p => p[0] != null).pop(); if (li) o += `<circle cx="${x(li[1])}" cy="${y(li[0])}" r="3" fill="${c}"/>`; }
  return o + `<text x="${L}" y="${H - 5}" ${mono} fill="#71717A">24 h ago</text><text x="${W - R}" y="${H - 5}" text-anchor="end" ${mono} fill="#71717A">now</text></svg>`;
}
function drawBoard(door) {
  const root = document.querySelector(`[data-board="${door}"]`); if (!root) return;
  const el = root.querySelector('.bgrid'), F = boardFeeds(), byKey = Object.fromEntries(F.map(f => [f.key, f])), b = boardLoad(door);
  root.querySelector('.bnote').textContent = door === 'now'
    ? `${F.length} feeds on this node, from its own sensors, the stations around it, its models and its packs. Press + to put one on the board; a feed keeps its own colour and its source’s word.`
    : `Any of this node’s ${F.length} feeds, beside this page. Press + to add one; each board keeps its own.`;
  el.innerHTML = b.map((t, i) => {
    const f = t && byKey[t.key];
    if (!f) return `<button type="button" class="tile add" data-slot="${i}" aria-label="Add a feed to slot ${i + 1}"><span class="plus" aria-hidden="true">+</span><span>Add a feed</span></button>`;
    const kinds = ['line', 'bars', 'dial', 'value'].filter(k => k === 'value' || (f.series && (k !== 'dial' || lineOf(f.m) != null)));
    return `<div class="tile" data-slot="${i}" style="--dk:var(--d-${f.dom})"><div class="th"><span class="led"></span><b title="${esc(f.label)}">${esc(f.label)}</b>${prov(f.prov)}<button type="button" class="tx" data-x="${i}" aria-label="Take ${esc(f.label)} off the board">×</button></div>`
      + `<div class="tb">${tileSVG(f, t.kind)}</div><div class="tf"><span class="tv">${f.now == null ? '—' : fmt(f.now, Math.abs(f.now) >= 100 ? 0 : Math.abs(f.now) < 1 ? 2 : 1)}<small>${esc(f.unit)}</small></span><span class="ts" title="${esc(f.name)}">${esc(f.name)}${f.pack ? ' · ' + esc(f.pack) : ''}</span></div>`
      + `<div class="tk"><span class="ts">${esc(f.group.toLowerCase())}</span>${kinds.length > 1 ? `<span class="kinds" role="group" aria-label="Draw it as">${kinds.map(k => `<button type="button" data-k="${k}" data-slot="${i}" aria-pressed="${k === t.kind}">${k}</button>`).join('')}</span>` : ''}</div></div>`;
  }).join('');
  el.querySelectorAll('.tile.add').forEach(x => x.onclick = () => boardPick(door, +x.dataset.slot));
  el.querySelectorAll('.tx').forEach(x => x.onclick = () => { const bb = boardLoad(door); bb[+x.dataset.x] = null; boardSave(door, bb); drawBoard(door); });
  el.querySelectorAll('.kinds button').forEach(x => x.onclick = () => { const bb = boardLoad(door), s = +x.dataset.slot; if (bb[s]) { bb[s].kind = x.dataset.k; boardSave(door, bb); drawBoard(door); } });
}
async function boardPick(door, slot) {
  BOARD.pick = { door, slot };
  if (!BOARD.cat) BOARD.cat = await doorsFetch('/static/board-catalog.json').then(r => r.ok ? r.json() : null).catch(() => null) || { core: [], wild: [] };
  const dlg = $('#feedpick'); $('#fpq').value = ''; boardList(''); if (!dlg.open) dlg.showModal(); $('#fpq').focus();
}
function boardList(q) {
  const { door } = BOARD.pick, F = boardFeeds(), took = new Set(BOARD.pick.took || boardLoad(door).filter(Boolean).map(t => t.key)), Q = q.trim().toLowerCase();
  const hit = s => !Q || String(s).toLowerCase().includes(Q);
  const spark = f => { const s = (f.series || []).filter(v => v != null); if (s.length < 2) return '<svg></svg>'; const lo = Math.min(...s), hi = Math.max(...s);
    return `<svg viewBox="0 0 80 20" preserveAspectRatio="none" aria-hidden="true"><polyline points="${f.series.map((v, i) => v == null ? null : `${(i / (f.series.length - 1) * 80).toFixed(1)},${(18 - (v - lo) / (hi - lo || 1) * 16).toFixed(1)}`).filter(Boolean).join(' ')}" fill="none" stroke="var(--d-${f.dom})" stroke-width="1.5" vector-effect="non-scaling-stroke"/></svg>`; };
  const groups = ['This house', 'Packs on this node', 'Around it', 'Models for this point'];
  let h = groups.map(g => { const fs = F.filter(f => f.group === g && !took.has(f.key) && (hit(f.label) || hit(f.name) || hit(f.m) || hit(f.pack || ''))).sort((a, b) => a.label.localeCompare(b.label) || a.name.localeCompare(b.name));
    return fs.length ? `<div class="fpg"><h3><span>${g}</span><span>${fs.length}</span></h3>${fs.map(f => `<button type="button" class="fpr" data-key="${esc(f.key)}" style="--dk:var(--d-${f.dom})"><span class="led"></span><span class="m">${esc(f.label)}</span><span class="s">${esc(f.name)}</span>${spark(f)}<span class="v">${f.now == null ? '—' : fmt(f.now, Math.abs(f.now) >= 100 ? 0 : Math.abs(f.now) < 1 ? 2 : 1)} ${esc(f.unit)}</span>${prov(f.prov)}</button>`).join('')}</div>` : ''; }).join('');
  /* the packs this node does not run: what each would bring, and where to turn it on. Nothing here is a feed yet */
  const runs = new Set([...F.map(f => f.source), ...F.map(f => f.pack)].filter(Boolean));
  const cat = [...(BOARD.cat.core || []).map(p => ({ ...p, tier: 'core' })), ...(BOARD.cat.wild || []).map(p => ({ ...p, tier: 'wild' }))]
    .filter(p => !runs.has(p.id) && (p.metrics || []).length && (hit(p.name) || hit(p.id) || (p.metrics || []).some(hit)));
  if (cat.length) h += `<div class="fpg"><h3><span>Packs you could add</span><span>${cat.length}</span></h3>` + cat.map(p => `<div class="fpr off" style="--dk:var(--d-${BDOM(String((p.metrics || [''])[0]).replace(/^fc_/, ''))})"><span class="led"></span><span class="m">${esc(p.name || p.id)}</span><span class="s">${esc((p.metrics || []).slice(0, 4).join(', '))}${(p.metrics || []).length > 4 ? '…' : ''}</span><span></span><span class="on">${p.tier === 'wild' ? 'wild pack' : 'core pack'}</span><a class="v" href="#setup/packs">${p.tier === 'wild' ? 'how to add ›' : 'turn on ›'}</a></div>`).join('') + '</div>';
  $('#fpbody').innerHTML = h || '<p class="fine">Nothing matches.</p>';
  $('#fpbody').querySelectorAll('.fpr[data-key]').forEach(x => x.onclick = () => { const f = F.find(y => y.key === x.dataset.key); if (BOARD.pick.onPick) { $('#feedpick').close(); BOARD.pick.onPick(f); return; } const bb = boardLoad(door); bb[BOARD.pick.slot] = { key: f.key, kind: BKIND(f) }; boardSave(door, bb); $('#feedpick').close(); drawBoard(door); });
  $('#fpbody').querySelectorAll('a[href="#setup/packs"]').forEach(a => a.onclick = () => $('#feedpick').close());
}
/* the other doors draw their board after their own view; the doors' scripts load after this one, so the hook is set
   once they all have */
document.addEventListener('DOMContentLoaded', () => {
  const q = $('#fpq'); if (q) q.oninput = () => boardList(q.value);
  const c = $('#fpclose'); if (c) c.onclick = () => $('#feedpick').close();
  for (const door of ['node', 'place']) {
    const v = VIEWS[door]; if (typeof v !== 'function') continue;
    VIEWS[door] = function () { const r = v.apply(this, arguments); Promise.resolve(r).then(() => drawBoard(door), () => drawBoard(door)); return r; };
  }
});

/* ============================================================================================================
   PAGES OF THE HOUSEHOLD'S OWN (Field Synthesizer variation, round 4, 7 Nov 2026). Tomas: "create another entire page,
   like node, data, etc... full of data boxes from the data sources of the node. It should also have a + button."
   A + after the doors makes a page: a name, and what it starts with (empty, or the feeds of one group or one source).
   A page is a grid of boxes drawn by the board's own four kinds, wide or narrow, with a + box at its end. Kept in this
   browser; on a node, a setting the household shares. The limits are one line each: four pages keep the bar one line
   at a desk and the doors the way in; twenty-four boxes keep a page a page.
   ============================================================================================================ */
const PAGE_MAX = 4, TILE_MAX = 24, PAGE_KEY = 'planetai_pages_v1', SEED_MAX = 12;
const pagesLoad = () => { try { const p = JSON.parse(localStorage.getItem(PAGE_KEY) || '[]'); return Array.isArray(p) ? p.slice(0, PAGE_MAX) : []; } catch (e) { return []; } };
const pagesSave = p => { try { localStorage.setItem(PAGE_KEY, JSON.stringify(p)); } catch (e) { /* this browser keeps nothing: the page lasts the visit */ } };
const pageId = () => (location.hash.split('/')[1] || '');
function pagesNav() {
  const nav = document.querySelector('.bar .doors'); if (!nav) return;
  nav.querySelectorAll('.pg,.pgadd').forEach(x => x.remove());
  const P = pagesLoad(), here = view() === 'p' ? pageId() : null;
  for (const p of P) nav.insertAdjacentHTML('beforeend', `<a href="#p/${esc(p.id)}" data-v="p" data-pid="${esc(p.id)}" class="pg${p.id === here ? ' on' : ''}" title="${esc(p.name)}">${esc(p.name)}</a>`);
  nav.insertAdjacentHTML('beforeend', `<button type="button" class="pgadd" aria-label="Add a page" title="${P.length >= PAGE_MAX ? `${PAGE_MAX} pages is the most` : 'Add a page of your own'}">+</button>`);
  nav.querySelector('.pgadd').onclick = pageNew;
  /* the router marks every page link as on; only this one is */
  nav.querySelectorAll('a.pg').forEach(a => a.classList.toggle('on', a.dataset.pid === here));
}
/* what a new page can start with: a group of the node's feeds, or one source's (a pack, an account, a model) */
function pageStarts() {
  const F = boardFeeds(), by = (k, fn) => ({ k, fs: F.filter(fn) });
  const starts = [{ k: 'Empty', fs: [] }, by('Everything this house reads', f => f.group === 'This house'), by('The stations around it', f => f.group === 'Around it'), by('Models for this point', f => f.group === 'Models for this point')];
  const src = {}; for (const f of F) { const s = f.pack || f.source; if (s) (src[s] ||= []).push(f); }
  for (const [s, fs] of Object.entries(src).sort((a, b) => b[1].length - a[1].length)) starts.push({ k: `From ${s}`, fs });
  return starts.filter(s => s.k === 'Empty' || s.fs.length);
}
/* a page's first boxes: one a kind of reading, those with a day first, up to SEED_MAX */
function pageSeed(fs) {
  const seen = new Set(), out = [];
  for (const f of [...fs].sort((a, b) => (!!b.series - !!a.series) || a.label.localeCompare(b.label))) { if (seen.has(f.m)) continue; seen.add(f.m); out.push({ key: f.key, kind: BKIND(f), w: out.length < 2 && f.series ? 2 : 1 }); if (out.length >= SEED_MAX) break; }
  return out;
}
function pageNew() {
  const P = pagesLoad(), dlg = $('#pagenew'), body = $('#pnbody');
  if (P.length >= PAGE_MAX) {
    body.innerHTML = `<div class="pn"><p>You have ${PAGE_MAX} pages of your own, the most this screen keeps beside the five doors. Remove one to make another; its feeds stay on the node.</p><div class="row2"><button type="button" class="ghost" id="pnok">Close</button></div></div>`;
    dlg.showModal(); $('#pnok').onclick = () => dlg.close(); return;
  }
  const S = pageStarts();
  body.innerHTML = `<form class="pn" id="pnform"><label for="pnname">Its name, as it shows in the doors</label><input type="text" id="pnname" maxlength="24" placeholder="the garden, the studio, surf…" required>`
    + `<label>It starts with</label><div class="from">${S.map((s, i) => `<label><input type="radio" name="pnfrom" value="${i}" ${i === 1 ? 'checked' : ''}> ${esc(s.k)}<small>${s.k === 'Empty' ? 'add boxes with +' : `${Math.min(SEED_MAX, new Set(s.fs.map(f => f.m)).size)} boxes`}</small></label>`).join('')}</div>`
    + `<p class="lim">${PAGE_MAX - P.length} of ${PAGE_MAX} pages left on this screen. Up to ${TILE_MAX} boxes a page.</p>`
    + `<div class="row2"><button type="button" class="ghost" id="pncancel">Cancel</button><button type="submit" class="go">Make the page</button></div></form>`;
  dlg.showModal(); $('#pnname').focus();
  $('#pncancel').onclick = () => dlg.close();
  $('#pnform').onsubmit = e => {
    e.preventDefault(); const name = $('#pnname').value.trim().slice(0, 24); if (!name) return;
    const pick = S[+(new FormData(e.target).get('pnfrom') || 0)] || S[0], id = name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '').slice(0, 20) + '-' + Date.now().toString(36).slice(-4);
    const all = pagesLoad(); all.push({ id, name, tiles: pageSeed(pick.fs) }); pagesSave(all); dlg.close();
    location.hash = '#p/' + id; pagesNav();
  };
}
function pageTile(f, t, i) {
  const kinds = ['line', 'bars', 'dial', 'value'].filter(k => k === 'value' || (f.series && (k !== 'dial' || lineOf(f.m) != null)));
  return `<div class="tile${t.w === 2 ? ' w2' : ''}" style="--dk:var(--d-${f.dom})"><div class="th"><span class="led"></span><b title="${esc(f.label)}">${esc(f.label)}</b>${prov(f.prov)}`
    + `<button type="button" class="tw" data-w="${i}" aria-pressed="${t.w === 2}" title="Wide or narrow">${t.w === 2 ? 'wide' : 'narrow'}</button><button type="button" class="tx" data-x="${i}" aria-label="Take ${esc(f.label)} off this page">×</button></div>`
    + `<div class="tb">${tileSVG(f, t.kind, t.w === 2 ? 620 : 300)}</div><div class="tf"><span class="tv">${f.now == null ? '—' : fmt(f.now, Math.abs(f.now) >= 100 ? 0 : Math.abs(f.now) < 1 ? 2 : 1)}<small>${esc(f.unit)}</small></span><span class="ts" title="${esc(f.name)}">${esc(f.name)}${f.pack ? ' · ' + esc(f.pack) : ''}</span></div>`
    + `<div class="tk"><span class="ts">${esc(f.group.toLowerCase())}</span>${kinds.length > 1 ? `<span class="kinds" role="group" aria-label="Draw it as">${kinds.map(k => `<button type="button" data-k="${k}" data-i="${i}" aria-pressed="${k === t.kind}">${k}</button>`).join('')}</span>` : ''}</div></div>`;
}
VIEWS.p = function () {
  pagesNav();
  const P = pagesLoad(), id = pageId(), pg = P.find(p => p.id === id), el = $('#pagev');
  if (!pg) { el.innerHTML = `<p class="k">A page of your own</p><h1>This page is not on this screen.</h1><p class="lede">Pages are kept where they were made. <a href="#now">Back to Now</a>, or make one with the + after the doors.</p>`; return; }
  const F = boardFeeds(), byKey = Object.fromEntries(F.map(f => [f.key, f])), gone = pg.tiles.filter(t => !byKey[t.key]).length;
  const save = fn => { const all = pagesLoad(), me = all.find(p => p.id === id); if (!me) return; fn(me, all); pagesSave(all); VIEWS.p(); };
  el.innerHTML = `<div class="phd" data-reads="/stats /readings /observations" data-pack="core"><div><p class="k">A page of your own · ${pg.tiles.length} of ${TILE_MAX} boxes · kept on this screen</p><h1 id="pgname">${esc(pg.name)}</h1></div>`
    + `<div class="acts"><button type="button" id="pgren">Rename</button><button type="button" id="pgdel">Remove the page</button></div></div>`
    + (gone ? `<p class="fine">${gone} box${gone === 1 ? ' reads a feed' : 'es read feeds'} this node has not sent today; ${gone === 1 ? 'it is' : 'they are'} kept and drawn when ${gone === 1 ? 'it comes' : 'they come'} back.</p>` : '')
    + `<section class="board pboard" data-reads="/stats /readings /observations /packs" data-stage="observe" data-pack="core" data-kind="series" style="margin-top:0!important"><h2 class="nh">Its boxes · ${pg.tiles.length}</h2><div class="bgrid pgrid" id="pgrid">`
    + pg.tiles.map((t, i) => byKey[t.key] ? pageTile(byKey[t.key], t, i) : '').join('')
    + (pg.tiles.length < TILE_MAX ? `<button type="button" class="tile add" id="pgadd"><span class="plus" aria-hidden="true">+</span><span>Add a box</span></button>` : '') + `</div></section>`;
  const g = $('#pgrid');
  g.querySelectorAll('.tx').forEach(x => x.onclick = () => save(me => me.tiles.splice(+x.dataset.x, 1)));
  g.querySelectorAll('.tw').forEach(x => x.onclick = () => save(me => { const t = me.tiles[+x.dataset.w]; t.w = t.w === 2 ? 1 : 2; }));
  g.querySelectorAll('.kinds button').forEach(x => x.onclick = () => save(me => { me.tiles[+x.dataset.i].kind = x.dataset.k; }));
  const add = $('#pgadd'); if (add) add.onclick = async () => {
    BOARD.pick = { door: 'p', slot: null, took: pg.tiles.map(t => t.key), onPick: f => save(me => { if (me.tiles.length < TILE_MAX) me.tiles.push({ key: f.key, kind: BKIND(f), w: f.series ? 2 : 1 }); }) };
    if (!BOARD.cat) BOARD.cat = await doorsFetch('/static/board-catalog.json').then(r => r.ok ? r.json() : null).catch(() => null) || { core: [], wild: [] };
    $('#fpq').value = ''; boardList(''); $('#feedpick').showModal(); $('#fpq').focus();
  };
  $('#pgren').onclick = () => {
    $('#pgname').outerHTML = `<input id="pgname" maxlength="24" value="${esc(pg.name)}" aria-label="The page's name">`;
    $('#pgren').textContent = 'Keep the name'; const inp = $('#pgname'); inp.focus(); inp.select();
    const keep = () => { const v = inp.value.trim().slice(0, 24); if (v) save(me => { me.name = v; }); else VIEWS.p(); };
    $('#pgren').onclick = keep; inp.onkeydown = e => { if (e.key === 'Enter') keep(); if (e.key === 'Escape') VIEWS.p(); };
  };
  $('#pgdel').onclick = () => {
    $('.phd .acts').innerHTML = `<span class="sure">Remove “${esc(pg.name)}”? Its feeds stay on the node.</span><button type="button" id="pgno">Keep it</button><button type="button" id="pgyes">Remove</button>`;
    $('#pgno').onclick = () => VIEWS.p();
    $('#pgyes').onclick = () => { pagesSave(pagesLoad().filter(p => p.id !== id)); location.hash = '#now'; pagesNav(); };
  };
};
document.addEventListener('DOMContentLoaded', () => { pagesNav(); const c = $('#pnclose'); if (c) c.onclick = () => $('#pagenew').close(); window.addEventListener('hashchange', pagesNav); });
