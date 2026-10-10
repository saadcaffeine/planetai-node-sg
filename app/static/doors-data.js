'use strict';
/* DATA — every raw reading this node holds, drawn. One metric at a time; every sensor that reads it is one ruled row
   (Zendesk status rows, Square devices), all on one scale capped at the 98th percentile so one spike cannot flatten
   the rest; a reading above the cap is printed. Then the issues over seven days, the models, the Index cells, the ledger. */
let METRIC = 'pm25';
/* Names and units are the node's own words (GET /issues → metrics); a metric the node has no word for keeps its key. */
const MNAME0 = { pm25: 'PM2.5', pm10: 'PM10', pm1: 'PM1', temp: 'temperature', humidity: 'humidity', pressure: 'pressure', gas_resistance: 'gas resistance',
  bme_iaq: 'indoor air index', noise: 'noise', light: 'light', aqi: 'AQI (US EPA)', pm25_raw: 'PM2.5 uncorrected', wind_speed: 'wind', precipitation: 'rain' };
const MNAME = new Proxy({}, { get: (_, m) => labelOf(m), has: (_, m) => m in MNAME0 });

/* THE INDEX (R45, 7 Oct 2026; frontend-design within the node's layer and Set up's reference lock). Every kind of
   reading this house holds, as a table of specimens by family: each tile its short symbol in the mono, the node's
   own name, the unit, how many sources read it, the median of their 15-minute means now (GET /stats, open), and,
   with the token, the 24-hour trace of the hourly medians (GET /aggregates). Press one to draw every source.
   The sections run down one page with Set up's list beside them; the list follows the scroll. */
const FAMILY = [
  ['Air', ['pm25', 'pm10', 'pm1', 'pm25_raw', 'aqi', 'bme_iaq', 'iaq', 'gas_resistance', 'o3', 'no2', 'co', 'dust', 'aod', 'pm25_model', 'pm10_model']],
  ['Weather', ['temp', 'humidity', 'pressure', 'wind_speed', 'wind_direction', 'precipitation', 'uv_index', 'temp_model', 'humidity_model', 'pressure_model']],
  ['Sound and light', ['noise', 'light']],
  ['Sea', ['sea_surface_temp', 'wave_height_m', 'wave_period_s', 'wave_direction', 'swell_height_m', 'swell_period_s']],
  ['Radio', ['lora_util_pct', 'lora_channel_pct']]];
/* a word for a key the node has no label for; the node's own label (GET /issues → metrics) always wins */
const WORD = { pm25_raw: 'PM2.5, uncorrected', bme_iaq: 'indoor air index', iaq: 'indoor air index', gas_resistance: 'gas resistance', o3: 'ozone',
  no2: 'nitrogen dioxide', co: 'carbon monoxide', dust: 'dust', aod: 'aerosol optical depth', pm25_model: 'PM2.5, modelled', pm10_model: 'PM10, modelled',
  temp_model: 'temperature, modelled', humidity_model: 'humidity, modelled', pressure_model: 'pressure, modelled', uv_index: 'UV index',
  sea_surface_temp: 'sea surface', wave_height_m: 'wave height', wave_period_s: 'wave period', wave_direction: 'wave direction',
  swell_height_m: 'swell height', swell_period_s: 'swell period', lora_util_pct: 'LoRa airtime', lora_channel_pct: 'LoRa channel use' };
const mWord = m => (D.metrics[m] || {}).label || WORD[m] || labelOf(m);
const SYM = { pm25: 'PM2.5', pm10: 'PM10', pm1: 'PM1', pm25_raw: 'PM2.5ʳ', aqi: 'AQI', bme_iaq: 'IAQ', iaq: 'IAQ', gas_resistance: 'Ω', o3: 'O₃', no2: 'NO₂', co: 'CO',
  dust: 'Dst', aod: 'AOD', pm25_model: 'PM2.5ᵐ', pm10_model: 'PM10ᵐ', temp: 'T', humidity: 'RH', pressure: 'P', wind_speed: 'W', wind_direction: 'Dir',
  precipitation: 'R', uv_index: 'UV', temp_model: 'Tᵐ', humidity_model: 'RHᵐ', pressure_model: 'Pᵐ', noise: 'dB', light: 'lx', sea_surface_temp: 'SST',
  wave_height_m: 'Hs', wave_period_s: 'Tp', wave_direction: 'Dw', swell_height_m: 'Sw', swell_period_s: 'Ts', lora_util_pct: 'LoRa', lora_channel_pct: 'Ch' };
const DSECTIONS = [['d-readings', 'Readings'], ['issues7', 'Issues, 7 days'], ['models', 'Models and satellite'], ['cells', 'Index cells'],
  ['perday', 'Hours over the line'], ['ledger', 'Decisions'], ['api', 'API']];

/* #data/<sensor-id> (from a dot on Place) opens on a metric that station reads and scrolls to its row, once per link;
   #data/models opens at the models, #data/api at the API. */
let FOCUSED = '', DSPY = null, TILED = false;
VIEWS.data = function () {
  const S2 = D.raw ? D.raw.series : {}, FOCUS = decodeURIComponent(location.hash.split('/')[1] || '');
  if (FOCUS && FOCUS !== FOCUSED && S2[FOCUS] && !S2[FOCUS][METRIC]) {
    const has = Object.keys(S2[FOCUS]); METRIC = has.includes('pm25') ? 'pm25' : (FAMILY.flatMap(f => f[1]).find(m => has.includes(m)) || has[0] || METRIC);
  }
  const total = Object.values(S2).reduce((a, m) => a + Object.values(m).reduce((b, arr) => b + arr.filter(Boolean).length, 0), 0);
  $('#datahead').innerHTML = `<div class="k">Data · everything this node holds, as it reads it</div><h1>Every reading, drawn.</h1>
    <p class="lede">${D.raw ? `${total.toLocaleString('en')} hourly values from ${Object.keys(S2).length} sources over the last 24 hours` : 'The hourly values with the token'}, seven days of every issue at every distance, ${D.observations.length} model and satellite values, ${D.index_cells.length} Index cells and ${D.actions.length} decisions. Today’s open export, CC BY 4.0: <a class="mono" href="/export?day=${dayOf(D.buckets[D.now])}">GET /export?day=${dayOf(D.buckets[D.now])}</a>.</p>`;
  dataNav(); metricTiles();
  sensorsBlock(); issuesBlock(); modelsBlock(); cellsBlock(); ledgerBlock(); apiBlock();
  if (FOCUS && FOCUS !== FOCUSED) {
    FOCUSED = FOCUS;
    setTimeout(() => {                                          // after route() has scrolled to the top
      const el = document.querySelector(`.srow[data-sid="${CSS.escape(FOCUS)}"]`) || document.getElementById(FOCUS)
        || (['model', 'map'].includes((D.sens[FOCUS] || {}).kind) ? document.getElementById('models') : null);
      if (el) { el.scrollIntoView({ block: 'center' }); el.classList.add('focus'); }
    });
  }
};

/* the list beside the sections, Set up's own; it marks the section in view */
function dataNav() {
  $('#dnav').innerHTML = DSECTIONS.map(([id, t]) => `<a href="#data/${id}" data-s="${id}">${t}</a>`).join('');
  document.querySelectorAll('#dnav a').forEach(a => a.onclick = ev => { ev.preventDefault(); document.getElementById(a.dataset.s).scrollIntoView({ behavior: CLOCK.reduced() ? 'auto' : 'smooth', block: 'start' }); });
  if (DSPY) DSPY.disconnect();
  DSPY = new IntersectionObserver(es => { for (const e of es) if (e.isIntersecting) document.querySelectorAll('#dnav a').forEach(a => a.classList.toggle('on', a.dataset.s === e.target.id)); },
    { rootMargin: '-30% 0px -60% 0px' });
  DSECTIONS.forEach(([id]) => { const el = document.getElementById(id); el && DSPY.observe(el); });
}

function metricTiles() {
  const S2 = D.raw ? D.raw.series : {}, src = {}, now = {};
  for (const id in S2) for (const m in S2[id]) (src[m] ||= new Set()).add(id);
  for (const id in D.stats15) for (const m in D.stats15[id]) { (src[m] ||= new Set()).add(id); const v = D.stats15[id][m][0]; if (v != null) (now[m] ||= []).push(v); }
  /* a kind only models read goes to its own family, so what the house measures leads */
  const modelOnly = m => [...src[m]].every(id => (D.sens[id] || {}).kind === 'model');
  const known = new Set(FAMILY.flatMap(f => f[1])), fams = FAMILY.map(([t, ms]) => [t, ms.filter(m => src[m] && !modelOnly(m))])
    .concat([['Models', FAMILY.flatMap(f => f[1]).filter(m => src[m] && modelOnly(m))],
             ['Other', Object.keys(src).filter(m => !known.has(m) && !m.startsWith('fc_')).sort()]]).filter(f => f[1].length);
  if (!src[METRIC]) METRIC = (fams[0] || [, []])[1][0] || METRIC;
  /* the 24-hour trace: the median, hour by hour, of every source's hourly mean (the table, token-only) */
  const trace = m => {
    if (!D.raw) return '';
    const B = D.raw.buckets, med = B.map((_, i) => d3.median([...src[m]].map(id => ((S2[id] || {})[m] || [])[i]).filter(Boolean).map(v => v[0])));
    if (med.filter(v => v != null).length < 2) return '';
    const x = d3.scaleLinear([0, B.length - 1], [1, 99]), y = d3.scaleLinear(d3.extent(med.filter(v => v != null)), [22, 2]).nice();
    return `<svg class="tr" viewBox="0 0 100 24" preserveAspectRatio="none" aria-hidden="true"><path d="${d3.line().defined(v => v != null).x((v, i) => x(i)).y(v => y(v))(med)}"/></svg>`;
  };
  let k = 0;
  $('#metrics').innerHTML = fams.map(([t, ms]) => `<div class="fam"><div class="fh k">${t}<span><b>${ms.length}</b> kind${ms.length === 1 ? '' : 's'}</span></div><div class="tiles">${ms.map(m => {
    const n = src[m].size, md = now[m] && now[m].length ? d3.median(now[m]) : null, dp = Math.abs(md) >= 100 ? 0 : Math.abs(md) >= 10 ? 1 : 2;
    return `<button type="button" class="mt ${m === METRIC ? 'on' : ''}" data-m="${esc(m)}" aria-pressed="${m === METRIC}" style="--i:${k++}">`
      + `<span class="sym">${esc(SYM[m] || m.slice(0, 4))}</span><span class="mn said">${esc(mWord(m))}</span>${trace(m)}`
      + `<span class="mv">${md == null ? '<b>—</b>' : num(`metric.${m}.median`, fmt(md, dp), `median of ${now[m].length} sources’ 15-minute means`, `<b>${fmt(md, dp)}</b>`)} <span class="said">${esc(unitOf(m))}</span></span>`
      + `<span class="ms">${n} source${n === 1 ? '' : 's'}</span></button>`; }).join('')}</div></div>`).join('');
  if (!TILED) { $('#metrics').classList.add('enter'); TILED = true; } else $('#metrics').classList.remove('enter');
  document.querySelectorAll('#metrics .mt').forEach(b => b.onclick = () => { METRIC = b.dataset.m;
    document.querySelectorAll('#metrics .mt').forEach(x => { x.classList.toggle('on', x === b); x.setAttribute('aria-pressed', String(x === b)); });
    sensorsBlock(); document.getElementById('sensors').scrollIntoView({ behavior: CLOCK.reduced() ? 'auto' : 'smooth', block: 'start' }); });
}

/* THE API, from the documentation the node carries (data/docs_site.json, cut from docs/site/api.md by `make learn`):
   every route, its access, and whether this screen may read it; a curl line to copy; GET routes this screen can read
   open in place. The node's own words, never a second copy. */
let APIDOC = null;
async function apiBlock() {
  const el = $('#api');
  if (!APIDOC) APIDOC = await fetch('/static/docs_site.json').then(r => r.ok ? r.json() : []).catch(() => []);
  const secs = APIDOC.filter(x => x.page === 'api.md' && /### (GET|POST|PUT|DELETE|PATCH) /.test(x.text || ''));
  const docs = D.health.docs || 'https://planetai.fab.city/docs/', tok = !!DOORS_TOKEN(), open = D.share === 'open';
  const can = a => a === 'public' || (a === 'open' && (open || tok)) || (tok && a !== 'public' && a !== 'open');
  const RX = /### (GET|POST|PUT|DELETE|PATCH) (\S+)\s+Access:\s*(\w+)\s*([\s\S]*?)(?=### (?:GET|POST|PUT|DELETE|PATCH) |$)/g;
  const first = t => t.split(/\s\|\s|\s#{2,} /)[0].replace(/`/g, '').replace(/\s+/g, ' ').trim().split(/(?<=\.)\s/).slice(0, 2).join(' ');
  const routes = secs.map(sec => ({ title: sec.title.replace(/^HTTP API · /, ''), rows: [...sec.text.matchAll(RX)].map(m => ({ method: m[1], path: m[2], access: m[3], say: first(m[4]) })) }))
    .filter(g => g.rows.length);
  const n = routes.reduce((a, g) => a + g.rows.length, 0);
  el.innerHTML = `<div class="dsh"><h2>API</h2><p class="blurb">Everything on these pages is one of ${n} routes on this node, at <span class="mono">${esc(location.origin)}</span>, each answering JSON. `
    + `A route marked token wants <span class="mono">Authorization: Bearer &lt;token&gt;</span>; <code>planetai ui</code> prints the tokens. `
    + `<a href="${esc(docs)}api/" target="_blank" rel="noopener">The full reference ↗</a> · <a href="/llms.txt">llms.txt</a> for agents · MCP at <span class="mono">/mcp</span> with the admin token.</p></div>`
    + `<label class="afind"><span class="k">find</span><input type="search" id="afind" placeholder="a route, a word: readings, alerts, cells…" autocomplete="off"></label>`
    + routes.map(g => `<div class="ag"><div class="agh k">${esc(g.title)}<span>${g.rows.length}</span></div>${g.rows.map(r => {
      const yes = can(r.access), path = r.path, curl = `curl ${location.origin}${path}${r.access === 'public' || (r.access === 'open' && open) ? '' : ' -H "Authorization: Bearer $TOKEN"'}`;
      const go = r.method === 'GET' && yes && !/[{]/.test(path);
      return `<details class="ar" data-q="${esc((r.method + ' ' + path + ' ' + r.say + ' ' + g.title).toLowerCase())}"><summary><span class="am">${r.method}</span><span class="ap mono">${esc(path)}</span>`
        + `<span class="aa ${r.access}">${esc(r.access)}</span><span class="ay ${yes ? 'yes' : ''}">${yes ? 'this screen reads it' : 'needs the token'}</span></summary>`
        + `<p class="as">${esc(r.say)}</p><div class="ac"><code>${esc(curl)}</code><button type="button" class="sbtn" data-copy="${esc(curl)}">copy</button>${go ? `<a class="sbtn" href="${esc(path)}" target="_blank" rel="noopener">open ↗</a>` : ''}</div></details>`; }).join('')}</div>`).join('');
  $('#afind').oninput = e => { const q = e.target.value.trim().toLowerCase();
    el.querySelectorAll('.ar').forEach(r => { r.hidden = !!q && !r.dataset.q.includes(q); });
    el.querySelectorAll('.ag').forEach(g => { g.hidden = ![...g.querySelectorAll('.ar')].some(r => !r.hidden); }); };
  el.querySelectorAll('[data-copy]').forEach(b => b.onclick = () => { navigator.clipboard && navigator.clipboard.writeText(b.dataset.copy).then(() => { b.textContent = 'copied'; setTimeout(() => { b.textContent = 'copy'; }, 1400); }); });
}

function sensorsBlock() {
  if (!D.raw) { $('#sensors').innerHTML = `<div class="dh"><h2>Every source, last 24 hours</h2></div><p class="fine">The hourly table, GET /aggregates, is the household’s own readings hour by hour, so the node gives it only to a screen holding the token. Unlock this screen under Node to draw it; the issues, the models, the Index and the ledger below are open.</p>`; return; }
  const B = D.raw.buckets, ids = Object.keys(D.raw.series).filter(id => D.raw.series[id][METRIC]);
  const rows = ids.map(id => ({ id, s: D.sens[id] || { name: id, local: false, kind: 'sensor' }, a: D.raw.series[id][METRIC] }))
    .map(r => ({ ...r, d: ((D.ngeo && D.ngeo.dist[r.id]) || { m: 0 }).m / 1000 /* the node's metres */, last: (r.a.filter(Boolean).pop() || [])[0] }))
    .sort((a, b) => (b.s.local - a.s.local) || (a.d - b.d));
  const vals = rows.flatMap(r => r.a.filter(Boolean).flatMap(v => [v[1], v[2]])).sort(d3.ascending);
  const lo = Math.min(0, d3.min(vals) ?? 0), cap = d3.quantile(vals, .98) ?? 1, top = METRIC === 'pm25' ? Math.max(cap, D.issues.air.line * 1.2) : cap;
  const line = METRIC === 'pm25' ? D.issues.air.line : null, W = 300, H = 34, x = d3.scaleLinear([0, B.length - 1], [2, W - 2]), y = d3.scaleLinear([lo, top], [H - 3, 3]).clamp(true);
  const spark = a => {
    const pts = a.map((v, i) => v ? [i, v] : null);
    const band = d3.area().defined(p => p).x(p => x(p[0])).y0(p => y(p[1][1])).y1(p => y(p[1][2]))(pts);
    const ln = d3.line().defined(p => p).x(p => x(p[0])).y(p => y(p[1][0]))(pts);
    const over = line != null ? pts.filter(p => p && p[1][0] > line).map(p => `<rect x="${x(p[0]) - 3}" y="${H - 3}" width="6" height="3" fill="var(--signal-worse)"/>`).join('') : '';
    const clip = pts.filter(p => p && p[1][2] > top).length ? `<text x="${W - 2}" y="9" text-anchor="end" class="lab">↑ ${fmt(d3.max(a.filter(Boolean), v => v[2]), 0)}</text>` : '';
    return `<svg viewBox="0 0 ${W} ${H}" width="${W}" height="${H}" class="sp"><path d="${band}" class="bandp"/><path d="${ln}" class="lnp"/>`
      + (line != null ? `<line x1="0" x2="${W}" y1="${y(line)}" y2="${y(line)}" class="linep"/>` : '') + over + clip + `</svg>`;
  };
  const grp = (t, rs) => rs.length ? `<div class="gh k">${t} · ${rs.length}</div>` + rs.map(r => `<div class="srow" data-sid="${esc(r.id)}"><span class="t">${esc(plain(r.s.name || r.id))}<small>${esc(r.s.source || '')}${r.s.lat != null ? ` · ${fmt(r.d, 1)} km` : ''}${r.s.indoor ? ' · inside' : ''}</small></span>${spark(r.a)}<span class="c">${num(r.id + '.' + METRIC, fmt(r.last, METRIC === 'pressure' ? 0 : 1), line != null ? `the line ${line}` : `one scale, ${fmt(lo, 0)} to ${fmt(top, 0)}`)}</span></div>`).join('') : '';
  $('#sensors').innerHTML = `<div class="dh"><h2>${said(labelOf(METRIC))}, every source, last 24 hours</h2><span class="k">one scale, ${fmt(lo, 0)} to ${fmt(top, 0)} ${said(unitOf(METRIC))} · band = the hour’s low to high · line = its mean${line != null ? ' · red: over the line' : ''}</span></div>`
    + grp('This house', rows.filter(r => r.s.local)) + grp('Around it', rows.filter(r => !r.s.local && r.s.kind !== 'model')) + grp('Models', rows.filter(r => r.s.kind === 'model'))
    + `<div class="axis"><span></span><span class="mono k">${hhmm(B[0])} yesterday → ${hhmm(B[B.length - 1])} today</span><span></span></div>`;
}

function issuesBlock() {
  const out = [];
  for (const k of D.order.filter(ISSUES_DRAWN)) for (const dk of ['room', 'yard', 'ring']) {
    const it = D.issues[k], s = it.series[dk]; if (!s) continue;
    const W = 360, H = 110, x = d3.scaleLinear([0, s.length - 1], [30, W - 6]), vs = s.filter(v => v != null).sort(d3.ascending);
    const top = Math.max(it.line ?? 0, d3.quantile(vs, .98)) * 1.1, lo = k === 'heat' ? Math.floor(vs[0] - 1) : 0, y = d3.scaleLinear([lo, top], [H - 16, 6]).nice(3);
    const ln = d3.line().defined(v => v != null).x((v, i) => x(i)).y(v => y(Math.min(v, y.domain()[1])))(s);
    const days = D.dates.map(dt => D.at[dt + '|0']).filter(j => j != null);
    out.push(`<figure class="sm"><figcaption><b>${said(it.name)}</b> · ${said(D.labels[dk])} ${prov((it.provenance || {})[dk] || 'model')}</figcaption><svg viewBox="0 0 ${W} ${H}" width="${W}" height="${H}">`
      + y.ticks(3).map(t => `<line x1="30" x2="${W - 6}" y1="${y(t)}" y2="${y(t)}" class="grid"/><text x="26" y="${y(t) + 4}" text-anchor="end">${fmt(t, 0)}</text>`).join('')
      + days.map(j => `<line x1="${x(j)}" x2="${x(j)}" y1="6" y2="${H - 16}" class="grid"/><text x="${x(j) + 3}" y="${H - 4}">${dayOf(D.buckets[j]).slice(8)}</text>`).join('')
      + (it.line != null ? `<line x1="30" x2="${W - 6}" y1="${y(it.line)}" y2="${y(it.line)}" class="linep"/>` : '') + `<path d="${ln}" class="lnp" style="stroke-width:${dk === 'room' ? 1.6 : 1.1}"/></svg></figure>`);
  }
  $('#issues7').innerHTML = `<h2>Every issue, every distance, seven days</h2><div class="sms">${out.join('')}</div><p class="fine">Hourly, from GET /issues/days. Each drawing keeps its own scale, capped at the 98th percentile; the red dash is the line. Day numbers mark local midnight.</p>`;
}

function modelsBlock() {
  const by = d3.group(D.observations, o => o.sensor_id), nm = { 'ee-point': 'Earth Engine, within 1 km', 'marine-point': 'Open-Meteo marine', 'om-point': 'Open-Meteo weather', 'cams-point': 'CAMS air quality', 'earth-point': 'AlphaEarth' };
  $('#models').innerHTML = `<h2>Models and the satellite</h2>` + [...by].map(([id, os]) => `<div class="gh k">${esc(nm[id] || id)} · ${os.length}</div>`
    + `<table class="tbl"><tr><th>metric</th><th class="n">value</th><th class="hide">cadence</th><th class="hide">as of</th></tr>`
    + os.map(o => `<tr><td>${esc(o.metric.replace(/_/g, ' '))}</td><td class="n">${fmt(o.value, Math.abs(o.value) < 1 ? 3 : 1)}</td><td class="hide mono">${esc(o.cadence || '')}</td><td class="hide mono">${esc((o.ts || '').slice(0, 16).replace('T', ' '))}</td></tr>`).join('') + `</table>`).join('');
}
function cellsBlock() {
  $('#cells').innerHTML = `<h2>Fab City Index cells</h2><table class="tbl"><tr><th>cell</th><th class="n">value</th><th class="hide">unit</th><th>word</th></tr>`
    + D.index_cells.map(c => `<tr><td>${esc(c.cell.replace('|', ' · '))}</td><td class="n">${fmt(c.value, 2)}</td><td class="hide">${esc(c.unit)}</td><td>${prov(c.state)}</td></tr>`).join('') + `</table>`;
}
function ledgerBlock() {
  const pd = D.order.filter(ISSUES_DRAWN).map(k => [k, D.issues[k]]);
  $('#perday').innerHTML = `<h2>Hours over the line, per day</h2><table class="tbl"><tr><th>day</th>${pd.map(([, it]) => `<th class="n">${esc(it.name)}</th>`).join('')}</tr>`
    + D.dates.map(dt => `<tr><td class="mono">${dLabel(dt)}</td>${pd.map(([, it]) => { const p = (it.per_day || []).find(x => x.date === dt); return `<td class="n">${p ? `${p.over} <span class="x">/ ${p.read} of ${p.of} h</span>` : '—'}</td>`; }).join('')}</tr>`).join('') + `</table>`;
  const A = [...D.actions].sort((a, b) => b.ts.localeCompare(a.ts));
  $('#ledger').innerHTML = `<h2>Every decision, ${A.length}</h2><table class="tbl"><tr><th>when</th><th>stage</th><th class="hide">who</th><th>what it answered</th></tr>`
    + A.map(a => `<tr><td class="mono">${wdhm(a.ts)}</td><td>${esc(a.stage)}</td><td class="hide">${esc(a.actor)}</td><td>${esc(plain(a.text) || a.rule || '')}</td></tr>`).join('') + `</table>`;
}
