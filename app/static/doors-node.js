'use strict';
/* NODE — this node: who runs it and where; what comes in and what goes out, stepped at the pace things arrive
   (motion named after its datum, stepped never tweened, none under reduced motion); the nodes around it; setup;
   the five refusals. The central hexagon with its labelled spokes follows Memotron's graph, drawn in the layer.

   PHASE 4a (Tomas, 14–15 Oct 2026; the review's findings). The plan:
   8. Lead with a verdict, the node's sentence: "Working. Last reading 19:50; 6 of 6 sensors, 13 of 23 stations heard in
      the last hour." From /health and /stats, and with the token the doctor's GET /health/sources (#249): a stale poll,
      a failing loop, a silent sensor of its own or a fundamental source not running turns it into "Needs a look: …".
   9. Under 700 px the flow is drawn vertically (in above the hexagon, out below), the screen's own width, never wider.
   10. What it remembers: the counts line first; the diary shows 14 entries, and the rest on "show more".
   11. The nodes around it: the list first ("1 listed · 0 heard by radio"), the globe at most a third of the screen.
   12. The refusals in plain words, each with a link to where it can be checked. */
let FLOWOBS = null;
/* the verdict: Working, or Needs a look and why. Heard is a reading in the last hour (/stats silent_minutes); a poll is
   stale after 15 minutes of /issues' as_of, the Wall's rule, so a capture is judged at its own time. */
function verdict(D, src) {
  const h = D.health, heard = s => Object.values(D.stats15[s.sensor_id] || {}).some(v => v[1] != null && v[1] <= 60);
  const own = D.sensors.filter(s => s.local && s.kind === 'sensor'), pub = D.sensors.filter(s => !s.local && s.kind === 'sensor');
  const nOwn = own.filter(heard).length, nPub = pub.filter(heard).length, age = (Date.parse(D.as_of) - Date.parse(h.last_poll || '')) / 60e3;
  const bad = [!(age < 15) && (h.last_poll ? `the last reading was at ${hhmm(h.last_poll)}, ${ago(age)} before this page` : 'no reading since the restart'),
    ...Object.keys(h.errors || {}).map(k => `the ${k} loop failed on its last run`),
    own.length > nOwn && `${own.length - nOwn} of its ${own.length} sensors not heard in the last hour`,
    /* the doctor's fundamentals, as Set up lists them to finish setting up: each one not running, by its name */
    ...((src && src.sources) || []).filter(r => r.ok === false).map(r => `${r.name.replace(/^./, c => c.toLowerCase())} ${r.state === 'missing' ? 'is not set up' : 'is quiet'}`)].filter(Boolean);
  if (bad.length) return { ok: false, head: 'Needs a look', text: bad.join('; ').replace(/^./, c => c.toUpperCase()) + '.' };
  return { ok: true, head: 'Working', text: `Last reading ${hhmm(h.last_poll)}; ${own.length ? `${nOwn} of ${own.length} sensors` : 'no sensors of its own'}, ${nPub} of ${pub.length} stations heard in the last hour.` };
}
VIEWS.node = function () {
  FLOWOBS && FLOWOBS.disconnect(); CLOCK.off('node-flow');
  const R = D.registry, h = D.health;
  const say = src => { const v = verdict(D, src);
    return `<h1 class="verdict ${v.ok ? '' : 'bad'}">${v.head}.</h1><p class="vline said" data-role="sentence">${esc(v.text)}`
      + `${src && src.missing ? ` <a href="#setup">To finish setting up →</a>` : ''}</p>`; };
  $('#nodehead').innerHTML = `<div class="k">Node · ${esc(R.name)}, in ${esc(R.place)}</div><div id="verdict">${say(null)}</div>
    <p class="lede mono">planetai-node ${esc(h.version)} · up ${fmt(h.uptime_s / 3600, 1)} h · ${h.ingested.toLocaleString('en')} readings since the restart · cell ${esc(h.cell.id)} · ${esc(h.tz)}</p>`;
  /* asked once a draw, read by the flow and by Running: how many readings the node keeps (GET /storage, token-only)
     and what this home offers (GET /offers, open at every SHARE_LEVEL and in the daily export) */
  const kept = doorsFetch('/storage').then(x => x.ok ? x.json() : null).catch(() => null),
    offers = fetch('/offers').then(x => x.ok ? x.json() : null).catch(() => null);
  doorsFetch('/health/sources').then(r => (r.ok ? r.json() : null)).catch(() => null).then(src => { const el = $('#verdict'); if (src && el) el.innerHTML = say(src); });
  flow(kept, offers); cellsBlock(); around(); running(kept); remember();
  /* #node/<id> (a refusal's proof) scrolls to that part once it is drawn; #node/remember is remember()'s own */
  const at = location.hash.slice(1).split('/')[1];
  if (at && at !== 'remember') setTimeout(() => { const t = document.getElementById(at); if (t) t.scrollIntoView({ block: 'start' }); }, 60);
};

/* THE INDEX CELLS this node holds (GET /cells), under the flow that counts them; moved from Data (phase 4b, 15 Oct).
   #node/cells lands here, and so does Data's old #data/cells. */
function cellsBlock() {
  $('#cells').innerHTML = `<h2>Fab City Index cells, ${new Set(D.index_cells.map(c => c.cell)).size} of 20</h2><p class="fine">Computed by this node from its hourly buckets, ${esc(wdhm(D.as_of))}; each row says its word.</p><table class="tbl"><tr><th>cell</th><th class="n">value</th><th class="hide">unit</th><th>word</th></tr>`
    + D.index_cells.map(c => `<tr><td>${esc(c.cell.replace('|', ' · '))}</td><td class="n">${fmt(c.value, 2)}</td><td class="hide">${esc(c.unit)}</td><td>${prov(c.state)}</td></tr>`).join('') + `</table>`;
}

/* WHAT IT REMEMBERS (Tomas, 14 Oct: the diary split between Now and Node; Now keeps Yesterday and Did it work). The
   record, private and never leaving: the counts, the diary as a table with its written entry in a dialog and a search,
   what is usual, what worked as a table with its cases in a dialog, and who lives here. Tables by default, long text
   only in a dialog. The admin token only, because entries and cases carry the household's notes: a screen without it
   is told that the record exists and where to unlock it, and is shown none of it. #node/remember scrolls here,
   #node/remember/day/<date> opens that entry, #node/remember/who the household's form. */
const LSTATUS = { holding: 'holding', weakening: 'weakening', too_early: 'too early to say', gone: 'no longer watched' };
const VERDICT_W = { helps: 'helps', no_clear_difference: 'no clear difference', worse: 'seems to make it worse', too_early: 'too early to say', gone: 'no longer watched' };
let REM = { scale: 'day', rows: [], all: false };
async function remember() {
  const el = $('#remember'), at = location.hash.slice(1).split('/');
  const go = () => { if (at[1] === 'remember') setTimeout(() => (document.getElementById(at[2] === 'who' ? 'remember-who' : 'remember') || el).scrollIntoView({ block: 'start' })); };
  const l = await doorsFetch('/learned').then(r => r.ok ? r.json() : null).catch(() => null);
  if (!l) {
    el.innerHTML = `<h2>What it remembers</h2><p class="lede">A diary of every day, week, month and year, what is usual in this house and what worked here. It is the household’s and never leaves this machine, so only a screen holding the admin token reads it: unlock this one in ${UNLOCK_AT}.</p>`;
    return go();
  }
  const L = l.learnings || [], K = l.digests || {}, nK = Object.values(K).reduce((a, b) => a + b, 0), by = s => L.filter(x => x.status === s).length;
  const scales = ['day', 'week', 'month', 'year'].filter(x => K[x]).map(x => `${K[x]} ${x}${K[x] === 1 ? '' : 's'}`).join(', ');
  el.innerHTML = `<h2>What it remembers</h2><p class="lede">${num('remember.digests', nK, 'diary entries this node keeps')} diary entr${nK === 1 ? 'y' : 'ies'} kept${scales ? ` (${scales})` : ''}; `
    + `${num('remember.holding', by('holding') + by('weakening'), `of ${L.length} learnings`)} learnings holding, ${num('remember.early', by('too_early'), `of ${L.length} learnings`)} too early to say, ${num('remember.gone', by('gone'), `of ${L.length} learnings`)} no longer watched`
    + `${l.checked ? `, checked ${esc(when(l.checked))}` : ''}. All of it stays on this machine and never leaves.</p>`
    + `<h3>Diary</h3><div class="rbar"><div class="rseg" role="group" aria-label="Entries by">${['day', 'week', 'month', 'year'].map(x => `<button data-sc="${x}" class="${x === REM.scale ? 'on' : ''}">${x.toUpperCase()}</button>`).join('')}</div>`
    + `<form class="rfind" data-f="find"><input data-f="q" aria-label="search the diary" placeholder="smoke, purifier, October"><button>Search</button></form></div><div id="rdiary"></div>`
    + `<h3>What is usual</h3><div id="rusual"></div><h3>What worked</h3><div id="rworked"></div><h3 id="remember-who">Who lives here?</h3><div id="rwho"></div>`;
  el.querySelectorAll('[data-sc]').forEach(b => b.onclick = () => { REM.scale = b.dataset.sc; REM.all = false; el.querySelectorAll('[data-sc]').forEach(o => o.classList.toggle('on', o === b)); diaryTable(); });
  el.querySelector('[data-f=find]').onsubmit = e => { e.preventDefault(); diaryTable(el.querySelector('[data-f=q]').value.trim()); };
  if (at[2] && ['day', 'week', 'month', 'year'].includes(at[2])) REM.scale = at[2];
  el.querySelectorAll('[data-sc]').forEach(o => o.classList.toggle('on', o.dataset.sc === REM.scale));
  usualBlock(L, $('#rusual')); workedTable(L, $('#rworked')); $('#rwho').innerHTML = await whoForm();
  await diaryTable('', at[3]); go();
}
/* the diary as a table: one row per entry, the columns its own numbers; the written entry opens in a dialog */
async function diaryTable(words, open) {
  const el = $('#rdiary');
  const u = words ? `/learned/search?q=${encodeURIComponent(words)}&limit=50` : `/learned/search?scale=${REM.scale}&limit=50`;
  const j = await doorsFetch(u).then(r => (r.ok ? r.json() : null)).catch(() => null);
  const rows = REM.rows = (j && j.results) || [];
  const v = (x, g, f) => { const n = ((x.numbers || {})[g] || {})[f]; return n == null ? '—' : fmt(n, 1); };
  const al = (x, f) => !(x.numbers && x.numbers.alerts) ? '—' : Object.values(x.numbers.alerts).reduce((a, y) => a + y[f], 0);
  const done = x => ((x.text || '').match(/What was done: (.*?)\.(?: Against the|$)/) || [])[1] || '';
  /* fourteen entries, newest first, and the rest on a press: the record, not a wall of rows */
  const SHOW = 14, shown = words || REM.all || (open && rows.findIndex(x => String(x.period_start).slice(0, 10) === open) >= SHOW) ? rows : rows.slice(0, SHOW);
  el.innerHTML = !rows.length ? `<p class="fine">${words ? 'Nothing mentions that.' : 'No entries yet: the node writes them in the first hour of each day.'}</p>`
    : `<div class="tscroll"><table class="tbl diary"><tr><th>${words ? 'found' : REM.scale}</th><th class="n">PM2.5 inside</th><th class="n hide">peak</th><th class="n">outside</th><th class="n hide">feels-like inside</th><th class="n">alerts</th><th class="n">acted</th><th class="hide">what was done</th></tr>`
      + shown.map((x, i) => `<tr><td><button class="link" data-i="${i}">${esc(x.label)}</button>${x.source === 'learning' ? ' <span class="x">· learning</span>' : ''}</td>`
        + `<td class="n">${v(x, 'indoor-pm25', 'mean')}</td><td class="n hide">${v(x, 'indoor-pm25', 'max')}</td><td class="n">${v(x, 'outdoor-pm25', 'mean')}</td>`
        + `<td class="n hide">${v(x, 'indoor-heat', 'mean')}</td><td class="n">${al(x, 'raised')}</td><td class="n">${al(x, 'acted')}</td><td class="hide said done">${esc(done(x))}</td></tr>`).join('')
      + `</table></div>${shown.length < rows.length ? `<button class="more" data-more>Show ${rows.length - shown.length} more</button>` : ''}<p class="fine">PM2.5 is the period’s mean and its worst hour in µg/m³, from this house’s own sensors inside and out; feels-like is the mean inside in °C. Press an entry to read it as the node wrote it.</p>`;
  const show = x => cardDialog(x.label, `<p class="said">${esc(x.text)}</p><p class="fine">${x.source === 'learning' ? 'A learning, in the node’s own words.' : `The node’s ${esc(x.scale)} entry, written from its own numbers and your notes. It never leaves this machine.`}</p>`);
  el.querySelectorAll('[data-i]').forEach(b => b.onclick = () => show(rows[+b.dataset.i]));
  const more = el.querySelector('[data-more]'); if (more) more.onclick = () => { REM.all = true; diaryTable(words); };
  const hit = open && rows.find(x => String(x.period_start).slice(0, 10) === open);
  if (hit) show(hit);
}
/* what worked, per alert: acted and its change inside, not answered and its change, the node's verdict, and the cases
   in a dialog; who it matters to is said once, above the table, from the rows' own for_whom */
function workedTable(L, el) {
  const rows = L.filter(x => x.kind === 'worked'), who = [...new Set(rows.flatMap(x => x.for_whom || []))];
  const name = k => { const [p, r] = k.split('/'); return r === 'events' ? `every ask about ${p === 'air-quality' ? 'the air' : p}` : r.replace(/_/g, ' '); };
  const ch = g => !g || !g.n ? '—' : `${g.n} · ${(g.change > 0 ? '+' : '') + fmt(g.change, 1)}`;
  if (!rows.length) { el.innerHTML = `<p class="fine">Nothing yet: the node checks once a day, and needs an alert someone acted on.</p>`; return; }
  el.innerHTML = `<p class="fine">For each alert, what the air or the heat inside did after someone here acted, beside the times nobody answered and the street. Your own before and after, not an experiment: the night or the weather can do the same.${who.length ? ` <b>Matters here: ${esc(who.join(', '))}.</b>` : ''}</p>`
    + `<div class="tscroll"><table class="tbl worked"><tr><th>alert</th><th class="n">acted · change</th><th class="n">not answered · change</th><th>the node says</th></tr>`
    + rows.map((x, i) => { const N = x.numbers || {}, nc = ((N.cases || {}).acted || []).length + ((N.cases || {}).unanswered || []).length;
      return `<tr><td>${nc ? `<button class="link" data-w="${i}">${esc(name(x.key))}</button>` : esc(name(x.key))}</td><td class="n">${ch(N.acted)}</td><td class="n">${ch(N.unanswered)}</td>`
        + `<td>${esc(VERDICT_W[N.verdict] || LSTATUS[x.status] || x.status)}${x.status === 'weakening' ? ' · weakening' : ''}</td>`
        + `</tr>`; }).join('') + `</table></div><p class="fine">How many times, and the median change inside over the hours after: µg/m³ for the air, °C for heat. Press an alert for the node’s sentence and every case.</p>`;
  const cases = (c, u, acted) => !c.length ? '' : `<table class="tbl"><tr><th>${acted ? 'acted' : 'not answered'}</th><th class="n">before</th><th class="n">after</th><th class="n">street</th>${acted ? '<th>note</th>' : ''}</tr>`
    + c.slice().reverse().map(k => `<tr><td class="mono">${esc(when(k.at))}</td><td class="n">${fmt(k.before, 1)}</td><td class="n">${fmt(k.after, 1)} ${esc(u)}</td>`
      + `<td class="n">${k.street == null ? '–' : (k.street > 0 ? '+' : '') + fmt(k.street, 1)}</td>${acted ? `<td class="said">${esc(k.note || '')}</td>` : ''}</tr>`).join('') + `</table>`;
  el.querySelectorAll('[data-w]').forEach(b => b.onclick = () => { const x = rows[+b.dataset.w], N = x.numbers || {}, C = N.cases || {};
    cardDialog(name(x.key), `<p class="said">${esc(x.statement)}</p>${cases(C.acted || [], N.unit || '', true)}${cases(C.unanswered || [], N.unit || '', false)}`); });
}
/* WHAT IS USUAL HERE (SPEC_learn step 2): the shape of a day from this house's own sensors, the week against the three
   before, and the alerts that are mostly not answered, said as what would change them. The node changes nothing. */
function usualBlock(L, el) {
  const usual = L.filter(x => x.kind === 'usual'), asks = L.filter(x => x.kind === 'asks');
  el.innerHTML = `<p class="fine">From this house's own sensors, up to a year back: when in the day each is usually highest and lowest, weekdays against weekends, and this week against the three before. Outside is about the place; inside stays with the house.</p>`
    + (usual.length ? usual.map(x => `<div class="gh k">${esc(x.key.replace('-', ' '))} · ${esc(LSTATUS[x.status] || x.status)}${x.scope === 'place' ? ' · about the place' : ''}</div><p>${esc(x.statement)}</p>${dayStrip((x.numbers || {}).by_hour, x.metric === 'pm25' && D.issues[x.issue])}`).join('')
      : `<p class="fine">Nothing yet: the node checks once a day.</p>`)
    + (asks.length ? `<div class="gh k">alerts that may not fit</div><p class="fine">The last 30 days of each act-level alert. Where most go unanswered, the node says what would change it; it changes nothing itself.</p>`
      + asks.map(x => `<p><b>${esc(x.key)}</b> · ${esc(x.statement)}</p>`).join('') : '');
}
// Who is in the house (SPEC_learn step 4): yes or no answers, kept here and nowhere else, that rank what the node
// learned and say why a learning matters here. They change no threshold.
async function whoForm() {
  const h = await doorsFetch('/household').then(r => (r.ok ? r.json() : null)).catch(() => null);
  if (!h) return '';
  setTimeout(() => { const f = $('[data-f=who]'); if (!f) return;
    f.onchange = async () => {
      const people = Object.fromEntries([...f.querySelectorAll('input')].map(i => [i.name, i.checked]));
      const r = await fetch('/household', { method: 'PUT', headers: { ...DOORS_AUTH(), 'content-type': 'application/json' }, body: JSON.stringify({ people }) }).catch(() => null);
      f.querySelector('[role=status]').textContent = r && r.ok ? 'Kept. What worked follows it from the next look.' : 'Not kept.';
    }; }, 0);
  return `<form class="household" data-f="who"><p class="fine">Yes or no, kept on this machine, never a name or an age. It decides which of these matter most here, and a heat or air alert that matters to someone you tick says so in its Telegram message ("you said there is a child under five"), so that line reaches Telegram. It changes no threshold.</p>`
    + Object.entries(h.choices).map(([k, w]) => `<label class="tick"><input type="checkbox" name="${esc(k)}"${h.people[k] ? ' checked' : ''}> ${esc(w)}</label>`).join(' ')
    + `<p class="fine" role="status"></p></form>`;
}

/* What comes in, what goes out (R35's hub, back on Node in R38; the Wall keeps the flow by scale, js/flow.js).
   R38: every link says its own count over the hourly table's last 24 hours (flowData, doors-flow.js); answers come back on a link of
   their own, green; the centre is the node's res-8 cell inside its res-6 parent at true scale, so the cell reads
   against the finest cell that may leave; each square steps at its link's real mean rate, on the Wall's pace
   (--motion-replay-loop: six hours in 30 s), so the two doors run one clock speed. */
/* the flow on a phone (Tomas, 15 Oct: an 840 px drawing inside 358, "what goes out" off-screen): vertical, in above the
   hexagon and out below, at the screen's own width. Each link runs down its own rail in the left margin, 3 px apart,
   and turns to the hexagon at its own height, so no line crosses another or a word. Pure: tests/test_doors.py holds it. */
function flowLayout(W, nIn, nOut) {
  const R = 64, step = 40, tx = 8 + 3 * Math.max(nIn, nOut) + 10, cx = Math.max(tx + R + 24, W / 2);
  const inX = i => 8 + 3 * i, outX = j => 8 + 3 * (nOut - 1 - j), inY = i => 44 + step * i;
  const yName = inY(nIn - 1) + 15 + 34, yCell = yName + 16, cy = yCell + 18 + R, yB = [cy + R + 20, cy + R + 36, cy + R + 52];
  const yOutK = yB[2] + 34, outY = j => yOutK + 26 + step * j, yFoot = outY(nOut - 1) + 15 + 28;
  const inPath = i => { const x = inX(i), ye = cy - 4 - 2 * i; return `M${x},${inY(i) - 4}V${ye - 12}Q${x},${ye} ${x + 12},${ye}H${cx - R}`; };
  const outPath = j => { const x = outX(j), ye = cy + 4 + 2 * (nOut - 1 - j); return `M${cx - R},${ye}H${x + 12}Q${x},${ye} ${x},${ye + 12}V${outY(j) - 4}`; };
  return { W, H: yFoot + 3 * 14, R, cx, cy, tx, inX, outX, inY, outY, inPath, outPath, yName, yCell, yB, yInK: 20, yOutK, yFoot };
}
async function flow(kept, offers) {
  const [F, St, Of] = await Promise.all([flowData(), kept, offers]), el = $('#flow'), W = el.clientWidth || 900, narrow = W < 700;
  const grp = id => id.startsWith('msh') ? 'mesh' : (D.sensors.find(s => s.sensor_id === id) || {}).kind === 'model' ? 'models' : (D.sensors.find(s => s.sensor_id === id) || {}).local ? 'house' : 'public';
  const n24 = { house: null, public: null, models: null, mesh: null }; for (const [id, n] of Object.entries(F.counts)) n24[grp(id)] = (n24[grp(id)] || 0) + d3.sum(n);
  const loc = D.sensors.filter(s => s.local && s.kind === 'sensor'), pub = D.sensors.filter(s => !s.local && s.kind === 'sensor');
  const heard = pub.filter(s => lastRaw(s.sensor_id, 'pm25') != null).length, models = D.sensors.filter(s => s.kind === 'model').length, c24 = v => v == null ? 'counted with the token' : `${v.toLocaleString('en')} in 24 h`;
  const ret = D.health.reticulum || {}, perDay = ret.announce_s ? Math.round(86400 / ret.announce_s) : null;
  /* what reached a phone: the node's own count (/issues events.sent_24h), since an alerts row is written whether or not
     it was sent (below ALERT_LEVEL, or a pack the event engine speaks for); a node too old to say counts the rows */
  const sent = D.sent24, nOff = Of ? (Of.offers || []).length : null;
  // [title, words, events in 24 h (null: nothing travels), colour]
  const IN = [['Sensors in this house', `${loc.length} · ${c24(n24.house)}`, n24.house, ''], ['Public stations around it', `${heard} of ${pub.length} heard · ${c24(n24.public)}`, n24.public, ''],
    ['Models for this point', `${models} · ${c24(n24.models)}`, n24.models, ''], ['The mesh, by LoRa', n24.mesh == null ? (F.counted ? 'no mesh heard' : 'counted with the token') : `${n24.mesh.toLocaleString('en')} packets in 24 h`, n24.mesh, ''],
    ['Answers, from the household', `${c24(F.answers.length)} · Done, Not now, Doesn’t fit`, F.answers.length, 'green'], ['The satellite', D.earth ? `${D.earth.years.length} years · once a year` : 'not fetched on this node', null, 'sat']];
  const OUT = [['This page, on your network', '0 requests out · when you open it', null, ''], ['Alerts, to a phone', `${sent == null ? `${F.alerts.length.toLocaleString('en')} recorded in 24 h` : `${sent.toLocaleString('en')} sent in 24 h`} · ${D.rho.acted} acted on`, sent ?? F.alerts.length, 'red'],
    ['Its cell, by radio', ret.announce_s ? `res ${D.geometry.radio.res} · every ${Math.round(ret.announce_s / 60)} min · ${(ret.peers || []).length} heard` : 'no radio on this node', perDay, 'blue'], ['Fab City Index cells', `${new Set(D.index_cells.map(c => c.cell)).size} of 20 · hourly`, 24, 'blue'],
    ['Open export, CC BY 4.0', 'one file a day', 1, ''],
    ['What this home offers', nOff == null ? 'not read' : nOff ? `${nOff} thing${nOff === 1 ? '' : 's'} · open to anyone, and in the export` : 'nothing offered', nOff ? 1 : null, ''], ['Hourly means, to a community node', 'none set · nowhere yet', null, '']];
  const L = narrow ? flowLayout(W, IN.length, OUT.length) : null, H = L ? L.H : 500, cx = L ? L.cx : W / 2, cy = L ? L.cy : H / 2, R = L ? L.R : 96;
  const xIn = 300, xOut = W - 340, yAt = (i, n) => 46 + i * ((H - 110) / (n - 1));
  // the centre: the res-6 parent and its 49 res-8 cells, flat and to scale; this node's cell filled. Every hexagon is a real cell.
  /* the node's own answers (js/nodegeo.js): its res-8 cell, the res-6 parent and the parent's 49 children, as rings */
  const NG = D.ngeo, poly = row => ({ type: 'Polygon', coordinates: [llRing(row)] });
  const cellR = NG ? NG.c8.ring : null, parR = NG ? NG.c6.ring : null, cell = NG ? NG.c8.id : D.health.cell.id;
  const pa = NG ? d3.geoPath(d3.geoIdentity().reflectY(true).fitExtent([[cx - R, cy - R], [cx + R, cy + R]], poly(parR))) : null, kids = NG ? NG.c6.children_ll : [];
  const link = d3.linkHorizontal(), paths = [];
  let s = `<svg viewBox="0 0 ${W} ${H}" width="${W}" height="${H}" role="img" aria-label="What comes into this node and what goes out">`;
  const row = (id, d, e, c, x, y, dx, t, n, hollow) => `<path id="${id}" d="${d}" class="fl ${e == null ? 'empty' : ''}"/><circle cx="${x}" cy="${y - 4}" r="3" class="fd ${hollow && e == null ? 'hollow' : c}"/>`
    + `<text x="${dx}" y="${y}" class="ft">${esc(t)}</text><text x="${dx}" y="${y + 15}" class="fn">${esc(n)}</text>`;
  if (L) {
    s += `<text x="${L.tx}" y="${L.yInK}" class="fn">COMES IN</text><text x="${L.tx}" y="${L.yOutK}" class="fn">GOES OUT</text>`;
    IN.forEach(([t, n, e, c], i) => { s += row(`fi${i}`, L.inPath(i), e, c, L.inX(i), L.inY(i), L.tx, t, n); paths.push([`fi${i}`, e, c]); });
    OUT.forEach(([t, n, e, c], j) => { s += row(`fo${j}`, L.outPath(j), e, c, L.outX(j), L.outY(j), L.tx, t, n, true); paths.push([`fo${j}`, e, c]); });
  } else {
  IN.forEach(([t, n, e, c], i) => { const y = yAt(i, IN.length), d = link({ source: [xIn + 8, y], target: [cx - R, cy] });
    s += `<path id="fi${i}" d="${d}" class="fl ${e == null ? 'empty' : ''}"/><text x="${xIn}" y="${y - 6}" text-anchor="end" class="ft">${esc(t)}</text><text x="${xIn}" y="${y + 9}" text-anchor="end" class="fn">${esc(n)}</text><circle cx="${xIn + 8}" cy="${y}" r="3" class="fd ${c}"/>`;
    paths.push([`fi${i}`, e, c]); });
  OUT.forEach(([t, n, e, c], i) => { const y = yAt(i, OUT.length), d = link({ source: [cx + R, cy], target: [xOut - 8, y] });
    s += `<path id="fo${i}" d="${d}" class="fl ${e == null ? 'empty' : ''}"/><text x="${xOut}" y="${y - 6}" class="ft">${esc(t)}</text><text x="${xOut}" y="${y + 9}" class="fn">${esc(n)}</text><circle cx="${xOut - 8}" cy="${y}" r="3" class="fd ${e == null ? 'hollow' : c}"/>`;
    paths.push([`fo${i}`, e, c]); });
  }
  const km2 = which => NG ? fmt(NG[which].area_m2 / 1e6, which === 'c8' ? 2 : 0) : '—', tn = (k, v, c) => `<tspan data-num="${k}" data-cmp="${esc(c)}">${v}</tspan>`;   // num(), in SVG
  const centre = (!NG ? (L ? `<text x="${L.tx}" y="${cy - 26}" class="fn">the cells need the token: unlock below</text>` : `<text x="${cx}" y="${cy}" text-anchor="middle" class="fn">the cells need the token: unlock below</text>`)
    : kids.filter(k => k[0] !== cell).map(k => `<path d="${pa(poly(k))}" class="fgrid"/>`).join('') + `<path d="${pa(poly(parR))}" class="fpar"/><path d="${pa(poly(cellR))}" class="fhex"/>`);
  const keptW = St ? `about ${St.readings.toLocaleString('en')} readings kept` : `${D.health.ingested.toLocaleString('en')} readings since the restart`;
  const foot = 'raw readings stay here; what leaves is the cell, the means, the Index, the answers and what this home offers';
  if (L) {
    /* on a phone the words sit left, beside the rails, each line short enough for the screen */
    const lines = [], wds = foot.split(' '); let ln = '';
    for (const w of wds) { if ((ln + ' ' + w).length > 44 && ln) { lines.push(ln); ln = w; } else ln = ln ? ln + ' ' + w : w; } lines.push(ln);
    s += centre + `<text x="${L.tx}" y="${L.yName}" class="fname">${esc(D.registry.name)}</text><text x="${L.tx}" y="${L.yCell}" class="fn">${esc(cell)} · res 8 · ${tn('node.cell.km2', km2('c8'), 'this cell\'s own area')} km²</text>`
      + `<text x="${L.tx}" y="${L.yB[0]}" class="fn">1 of ${tn('node.cell.n6', NG ? NG.c6.children_n : '—', 'res-8 cells in its res-6 parent, counted by the node')} in its res-6 cell · ${tn('node.par.km2', km2('c6'), 'the parent\'s own area')} km²</text>`
      + `<text x="${L.tx}" y="${L.yB[1]}" class="fn">dotted: may leave</text><text x="${L.tx}" y="${L.yB[2]}" class="fn">${keptW} · none leave</text>`
      + lines.map((t, i) => `<text x="${L.tx}" y="${L.yFoot + i * 14}" class="fn">${esc(t)}</text>`).join('') + `<g id="dots"></g></svg>`;
  } else s += centre
    + `<text x="${cx}" y="${cy - R - 26}" text-anchor="middle" class="fname">${esc(D.registry.name)}</text><text x="${cx}" y="${cy - R - 10}" text-anchor="middle" class="fn">${esc(cell)} · res 8 · ${tn('node.cell.km2', km2('c8'), 'this cell\'s own area')} km²</text>`
    + `<text x="${cx}" y="${cy + R + 18}" text-anchor="middle" class="fn">1 of ${tn('node.cell.n6', NG ? NG.c6.children_n : '—', 'res-8 cells in its res-6 parent, counted by the node')} in its res-6 cell · ${tn('node.par.km2', km2('c6'), 'the parent\'s own area')} km² · dotted: may leave</text>`
    + `<text x="${cx}" y="${cy + R + 34}" text-anchor="middle" class="fn">${keptW} · none leave</text>`
    + `<text x="${cx}" y="${H - 6}" text-anchor="middle" class="fn">${foot}</text><g id="dots"></g></svg>`;
  el.innerHTML = s;
  // Stepped, named after its datum: one square per link takes one of eight steps per arrival, at the link's real mean
  // rate over 24 h, compressed to the Wall's pace. One clock, transform only, paused off screen, none under reduced motion.
  if (CLOCK.reduced()) { $('#flownote').textContent = 'Reduced motion: the links hold still and say their counts in words.'; return; }
  const g = el.querySelector('#dots'), STEPS = 8, perH = (parseFloat(css('--motion-replay-loop')) || 30) * 1000 / 6;   // ms for one capture hour
  const links = paths.filter(p => p[1]).map(([id, e, c]) => {
    const path = el.querySelector('#' + id), L = path.getTotalLength(), dot = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
    dot.setAttribute('width', 6); dot.setAttribute('height', 6); dot.setAttribute('x', -3); dot.setAttribute('y', -3); dot.setAttribute('class', 'fdot ' + c); g.appendChild(dot);
    const k = Math.floor(Math.random() * STEPS), every = Math.max(84, 24 * perH / e);   /* faster than two clock frames steps every two */
    const put = n => { const p = path.getPointAtLength(L * n / (STEPS - 1)); dot.setAttribute('transform', `translate(${p.x} ${p.y})`); };
    put(k); return { put, k, every, last: 0 };
  });
  const tick = t => { if (view() !== 'node') return CLOCK.off('node-flow'); for (const l of links) if (t - l.last >= l.every) { l.last = t; l.k = (l.k + 1) % STEPS; l.put(l.k); } };
  FLOWOBS = new IntersectionObserver(([e]) => e.isIntersecting ? CLOCK.on('node-flow', tick) : CLOCK.off('node-flow')); FLOWOBS.observe(el);
  $('#flownote').textContent = 'Each square steps once per arrival on its link, at that link’s real rate over the last 24 hours, six hours to 30 s, the Wall’s pace: the house’s readings race, the answers creep, the export takes two minutes. A dashed link carries nothing.';
}

async function around() {
  const land = await geo('world', '/static/world-land-110m.json'), el = $('#world'), W = el.clientWidth || 900, H = Math.round(W * .48);
  // the nodes the programme lists (GET /nodes, js/nodegeo.js), not the ones this node's radio heard
  const N = KNOWN_NODES, NG = D.ngeo;
  // the whole-sphere H3 grid at resolution 2, as the landing draws it (planetai web, kit/h3/planet-states-web.svg): under
  // the coast, at half strength; each node lights its own res-2 cell. Edges as lines, so no ring winding can fill the globe.
  /* the planet's res-2 grid and each node's res-2 cell are the node's answers (GET /geo/planet, /geo/cell) */
  const g2 = NG ? NG.planet : [], lit = NG ? NG.lit.map(c => c.ring) : [];
  const pr = d3.geoEqualEarth().fitExtent([[6, 6], [W - 6, H - 6]], { type: 'Sphere' }), path = d3.geoPath(pr);
  let s = `<svg viewBox="0 0 ${W} ${H}" width="${W}" height="${H}" role="img" aria-label="The nodes the programme knows" class="geo"><path d="${path({ type: 'Sphere' })}" class="sphere"/>`
    + (g2.length ? `<path d="${path({ type: 'MultiLineString', coordinates: g2.map(llRing) })}" class="h3grid"/>` : '') + `<path d="${path(land)}" class="land"/>`;
  s += lit.map(c => `<path d="${path({ type: 'Polygon', coordinates: [llRing(c).reverse()] })}" class="h3lit"/>`).join('');
  /* an arc from this node to each other node with a point; one label per place, the nodes there by name */
  const me = N.find(x => x.me), far = N.filter(x => !x.me), places = d3.groups(N, x => x.ll.join(','));
  s += far.map(x => `<path d="${path({ type: 'LineString', coordinates: [me.ll, x.ll] })}" class="arc"/>`).join('');
  for (const x of N) { const [px, py] = pr(x.ll); s += `<circle cx="${px}" cy="${py}" r="${x.me ? 6 : 5}" class="nd"/>`; }
  for (const [, xs] of places) { const [px, py] = pr(xs[0].ll), at = xs[0];
    s += `<text x="${px + 10}" y="${py + 18}" class="lab">${esc(at.place.split(',')[0].trim())} · ${xs.map(x => esc(x.n)).join(' and ')}</text>`; }
  s += `</svg>`;
  el.innerHTML = s;
  const L = D.listed, ret = D.health.reticulum || {}, word = x => !(L && L.read) ? 'list not read' : x.listed ? 'listed' : 'not listed';
  const fine = (L && L.read ? `Listed: the programme’s registry.json, read at ${hhmm(L.read)}${L.error ? ', the last read failed (' + L.error + ')' : ''}. `
      : `The programme’s list has not been read yet${L && L.error ? ' (' + L.error + ')' : ''}. `)
    + 'A node joins it with planetai hello and a merged pull request; a node with no published point is not drawn. '
    + (ret.announce_s ? ((ret.peers || []).length ? `This node’s radio has heard ${ret.peers.length} other node${ret.peers.length > 1 ? 's' : ''}; they are not on this map yet.` : 'This node’s radio has heard no other node yet.') : 'This node has no radio announcing it.');
  /* the list first, its count in words (Tomas, 15 Oct: a 540 px globe with one dot) */
  const nL = N.filter(x => x.listed).length;
  $('#nodes').innerHTML = `<p class="lede">${num('node.listed', nL, 'nodes on the programme’s list with a point')} listed · ${ret.announce_s ? `${num('node.heard', (ret.peers || []).length, 'other nodes this node’s radio heard')} heard by radio` : 'no radio on this node'}</p>` + N.map(x => `<div class="lrow"><span class="t">${esc(x.n)}<small>${esc(x.place)}</small></span><span class="s">${esc(x.reads)}</span>`
    + `<span class="c"><span class="state">${word(x)}</span> ${x.me ? 'this node' : (NG && NG.dist['node:' + x.n] ? fmt(NG.dist['node:' + x.n].m / 1000, 0) + ' km' : '—')}</span></div>`).join('')
    + `<div class="lrow"><span class="t">A community node above it</span><span class="s">where this node’s hourly means would go, so a city can be built from nodes</span><span class="c x">not set</span></div>`
    + `<p class="fine">${esc(fine)}</p>`;
}

/* Running, and a light reading of the machine under it (GET /machine, /storage: token-only; the full one is Set up →
   Machine). Meters are ink on a hairline, one per resource, so the state reads at a glance. */
async function running(kept) {
  const h = D.health, mesh = h.mesh && h.mesh.root_topic ? h.mesh : null, ret = h.reticulum;
  const [M, S] = await Promise.all([doorsFetch('/machine').then(x => x.ok ? x.json() : null).catch(() => null), kept]);
  const meter = (v, T) => T ? `<i class="nm"><b style="width:${Math.min(100, v / T * 100).toFixed(1)}%"></b></i>` : '';
  const gb = b => b == null ? '—' : b >= 1e9 ? `${(b / 1e9).toFixed(1)} GB` : `${Math.round(b / 1e6)} MB`;
  const mem = M && M.memory, used = mem && mem.total_bytes && mem.available_bytes != null ? mem.total_bytes - mem.available_bytes : null, k = S && S.disk;
  const years = d => d == null ? '—' : d >= 730 ? `${Math.round(d / 365)} years` : d >= 60 ? `${Math.round(d / 30)} months` : `${d} days`;
  const hw = M ? [
    ['Processor', `${M.arch} · ${M.cores} cores · load ${M.load ? M.load[0].toFixed(2) : '—'}${meter(M.load ? M.load[0] : 0, M.cores)}`, M.cpu_busy_pct == null ? '—' : `${M.cpu_busy_pct}% busy`],
    ['Memory', `${gb(used)} of ${gb(mem.total_bytes)}${meter(used || 0, mem.total_bytes)}`, `${gb(mem.available_bytes)} free`],
    ...(M.temperatures || []).slice(0, 1).map(t => ['Temperature', t.zone, `${t.celsius} °C`]),
    ...(k ? [['Disk', `${gb(S.database_bytes + S.out_bytes + S.backups.bytes + S.exports_bytes)} this node · ${gb(k.free_bytes)} free of ${gb(k.total_bytes)}${meter(k.used_bytes, k.total_bytes)}`, `${years(S.days_left)} left`]] : []),
  ] : [['The machine', 'its processor, memory and disk are the keeper’s: unlock this screen in Set up', '<a href="#setup/screen">unlock →</a>']];
  $('#running').innerHTML = [['Version', `planetai-node ${h.version} · schema ${h.schema}`, ''], ['Running for', 'since the last restart', `${fmt(h.uptime_s / 3600, 1)} h`],
    ['Readings taken in', h.last_poll ? `${h.polls} polls since the restart, the last at ${hhmm(h.last_poll)}` : 'no poll yet since the restart', h.ingested.toLocaleString('en')],
    ...hw,
    ['Mesh in the house', mesh ? `${mesh.root_topic} · gateway ${mesh.gateway}` : 'no mesh broker set', mesh ? `${mesh.packets} packets` : 'off'],
    ['Radio', ret && ret.announce_s ? `announces its cell every ${ret.announce_s / 60} min` : 'no radio bridge set', ret && ret.ok ? 'on' : 'off'],
    ['This screen', DOORS_TOKEN() ? 'holds a token: it draws the map, the cells and the counts' : `${D.share === 'open' ? 'shared openly on this network' : 'not shared with this network'}, without a key: the map, the cells and the counts stay on the node`,
      DOORS_TOKEN() ? 'unlocked' : 'locked']]
    .map(([t, s2, c]) => `<div class="lrow"><span class="t">${t}</span><span class="s">${t === 'The machine' || /class="nm"/.test(s2) ? s2.replace(/^([^<]*)/, m => esc(m)) : esc(s2)}</span><span class="c">${/^<a /.test(c) ? c : esc(c)}</span></div>`).join('')
    + `<p class="fine">${M ? 'The machine as the node’s containers see it. ' : ''}<a href="#setup/machine">Set up → Machine</a> has all of it, and how long the disk lasts.</p>`;
}

