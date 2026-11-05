'use strict';
/* NOW — the household's first screen, read in the order a person asks (Tomas, 15 Oct; the plan heads the markup in
   doors.html): right now, as one block (the sentence and its day); what to do; did it work, and yesterday; around the
   house. Married to the node's rules: every part is one of the four card kinds (data-kind), names its learn mark, the
   routes it reads and its stage; every figure carries its comparison; the node's words are never shouted; provenance
   is a pill in ink. The scales are Place's: the kicker links there and draws no rail. */
VIEWS.now = function () {
  rows(); drawDeclared(); drawAsks(); drawNow();
  aroundMap($('#rose')); thingsLine($('#nthings')); rememberLoad().then(() => decision());   /* the usual hour joins "Nothing is asked now" */
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
  const yest = day ? `<h3>Yesterday</h3><p>${yesterdayWords(day, k)} <a href="#node/remember/day/${esc(String(day.period_start).slice(0, 10))}">the whole entry ›</a></p>` : '';
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
    h += `<h3>Did it work</h3><p>${asked}</p>${after}${verdict}`
      + `<p class="dm">${who ? `${who} · ` : ''}<a href="#node/remember">every case, on Node ›</a></p>`;
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
function drawNow() {
  /* a phone draws the day alone and the week as one row a day it can press (weekRows): 13 px cells are no target */
  const phone = innerWidth <= 480;
  dayWeek({ el: $('#svg'), issue: S.issue, head: $('#fighead'), scale: $('#figline'), week: !phone, pick: j => { S.i = j; drawNow(); } });
  $('#week').hidden = !phone; if (phone) weekRows($('#week'));
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
  const k = S.issue, it = D.issues[k], i = S.i, b = D.buckets[i], dp = it.dp, U = it.unit, isNow = i === D.now;
  const w = (it.provenance || {})[it.hero_distance] || 'model';
  $('#kick').innerHTML = isNow ? `Right now · ${said(it.name)} at <span class="mono">${hhmm(b)}</span> ${prov(w)}`
    : `${said(it.name)} · ${esc(dLabel(dayOf(b)))} at <span class="mono">${hhmm(b)}</span> ${prov(w)} · ${D.now - i} hour${D.now - i === 1 ? '' : 's'} ago`;
  $('#back').hidden = isNow;
  const cell = D.health.cell || {}, rung = D.geometry.ladder.find(l => l.res === cell.res);
  $('#cellink').innerHTML = cell.edge_m && rung ? `${cell.edge_m} m · ${fmt(rung.own_area_m2 / 1e6, 2)} km² ›` : '';
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
  else {
    /* a past hour speaks the engine's words too (hours[i]): what it was doing, then the reading and whose
       line. A capture older than the hours key has none, and says only that nothing is here to read. */
    const h = (it.hours || [])[i];
    s = h ? esc(h[0]) : `<span class="gone">Nothing was recorded at ${hhmm(b)}.</span>`;
    tag = h ? h[1] : '';
  }
  $('#sentence').innerHTML = (it.pix ? `<svg class="pix" aria-hidden="true"><use href="${NODE}signs.svg#${it.pix}"/></svg>` : '') + `<span class="said">${s}${tag ? `<span class="ntag">${esc(tag)}</span>` : ''}</span>`;
  /* the four distances, one quiet line: the drawing above already draws three of them */
  $('#ladder').innerHTML = ['room', 'yard', 'ring', 'region'].map(dk => {
    const x = isNow ? (it.stack[dk] || {}).value : val(k, dk, i);
    const pw = (it.provenance || {})[dk] || ((it.stack[dk] || {}).provenance), hourly = (it.series || {})[dk];
    return `<span class="d ${x == null ? 'none' : ''}"><span class="x">${said(D.labels[dk])}</span>`
      + `<span class="v">${x == null ? '—' : num(`${k}.${dk}`, fmt(x, dp), cmp)}${x == null ? '' : `<small>${said(U)}</small>`}</span>`
      + (x == null ? `<span class="gap">${hourly ? 'not recorded' : (isNow ? 'none' : 'no hours here')}</span>` : prov(pw)) + `</span>`;
  }).join('');
  decision(); rowsValues();
}

/* WHAT TO DO: the decision of the moment (learn: buttons). The three answers are the node's own words. At the live
   hour, whether something is asked is the node's one answer (/issues asking), the one the Wall reads: an event still
   asking, else an alert still true. On 14 Oct this read the events alone and said "No event was open for air" beside a
   Wall showing an open ask. A past hour is history: the events open then. The frame (.decide) and the buttons are
   drawn only while something is asked; otherwise What to do is one plain line, with the hour it is usually worst. */
function decision() {
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
      + answers.map(x => `<p class="dm">answered: ${esc(x.button ? packWord(x.button.text, lc) : x.choice)}${x.actor ? ` by ${esc(x.actor)}` : ''} at ${esc(hhmm(x.ts))}${x.note ? ` · “${esc(x.note)}”` : ''}</p>`).join('')
      + `<p class="dm" role="status"></p></div>`;
  }).join('');
}
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
  $('#rows').innerHTML = D.order.filter(ISSUES_DRAWN).map(k => {
    const it = D.issues[k];
    return `<button class="row" data-k="${k}" data-kind="readout" aria-pressed="false"><span><span class="n">${said(it.name)}</span><span class="state ${it.state === 'act' ? 'act' : ''}">${esc(stateWord(it.state))}</span></span>`
      + `<span class="v" data-v></span><span class="sub" data-s></span></button>`;
  }).join('');
  document.querySelectorAll('#rows .row').forEach(b => b.onclick = () => { S.issue = b.dataset.k; drawNow(); });
}
function rowsValues() {
  const date = dayOf(D.buckets[S.i]);
  document.querySelectorAll('#rows .row').forEach(r => {
    const k = r.dataset.k, it = D.issues[k];
    r.setAttribute('aria-pressed', String(k === S.issue));
    // now is the live reading the title and the legend say, not the running hour's mean (audit, 15 Oct: 17 beside 10)
    const v = S.i === D.now ? ((it.stack || {})[it.hero_distance] || {}).value : val(k, it.hero_distance, S.i), pd = (it.per_day || []).find(p => p.date === date);
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
