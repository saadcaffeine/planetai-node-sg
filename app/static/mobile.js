'use strict';
/* mobile.js — the phone page (SPEC_mobile §5–§7): one scrollable page, Now / Place / Node. The data is D from
   doors-load.js (loadD with the phone's route subset); the page writes no household sentence — title, tagline,
   plain, the action and the button labels are the wire's, character for character.
   The eight one-line helpers are copied from doors-core.js, which boots the doors on load and cannot be imported. */
const $ = s => document.querySelector(s);
const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const hhmm = iso => iso ? doorsLocal(iso, D && D.tz).slice(11, 16) : '';   /* in the node's zone (doors-load.js) */
const fmt = (v, dp) => v == null || Number.isNaN(+v) ? '—' : (+v).toFixed(dp);
const NODE = '/static/';
const said = x => `<span class="said">${esc(x)}</span>`;
const sign = (id, cls = '') => `<svg class="sg ${cls}" aria-hidden="true"><use href="${NODE}signs.svg#${id}"/></svg>`;
const PROV = ['live', 'partial', 'model', 'cached', 'example'];
const prov = w => PROV.includes(w) ? `<span class="pill">${sign('sign-prov-' + w)}${w}</span>` : `<span class="gap">${esc(w)}</span>`;
const num = (key, v, cmp, inner) => `<span data-num="${esc(key)}" data-cmp="${esc(cmp)}">${inner ?? esc(v)}</span>`;
const ago = m => m < 90 ? `${Math.round(m)} min` : m < 48 * 60 ? `${Math.round(m / 60)} h` : `${Math.round(m / 1440)} days`;   /* a declared band's age (declaredBand, doors-load.js) */
const ANSWER_STAGE = { done: 'acted', not_now: 'acknowledged', doesnt_fit: 'dismissed' };

/* the phone's subset (SPEC_mobile §8): never the token-only three, never rho/cells */
const MOBILE_ROUTES = {
  issues: 'issues', days: 'issues/days?days=7', health: 'health', settings: 'settings',
  stats: 'stats', sensors: 'sensors',
};

let D = null, leadKey = null, refusedSentence = null, refusedHealth = null;

/* the QR code Set up draws (§6.3) opens this page at #act=<token>: keep it, then take it out of the address bar */
if (location.hash.startsWith('#act=')) {
  try { localStorage.setItem('planetai_act', decodeURIComponent(location.hash.slice(5))); } catch (e) { /* no storage here */ }
  history.replaceState(null, '', location.pathname + location.search);
}
/* either token unlocks the phone, as DOORS_TOKEN reads them: a phone unlocked with the admin token is not locked */
const hasToken = () => !!DOORS_TOKEN();
const bootOff = () => { const a = $('#asking'); if (a) a.remove(); };

async function boot() {
  /* an explicit ?layout=mobile is remembered in this browser (§4.2); storage that throws remembers nothing */
  try {
    const q = new URLSearchParams(location.search);
    if (q.get('layout') === 'mobile') localStorage.setItem('planetai_layout', 'mobile');
  } catch (e) { /* no storage here */ }
  const foot = $('#fulldoors'); if (foot) foot.href = '/?layout=doors' + (location.hash || '');
  try {
    D = await loadD(MOBILE_ROUTES);
    leadKey = D.lead;
    drawAll();
  } catch (e) {
    /* /issues refused this screen (the default SHARE_LEVEL=off): the node's own sentence, then the unlock field */
    const [h, r] = await Promise.all([
      fetch('/health').then(x => x.ok ? x.json() : ({})).catch(() => ({})),
      doorsFetch('/issues').then(async x => x.ok ? null : (await x.json().catch(() => ({}))).error || null).catch(() => null),
    ]);
    refusedHealth = h; refusedSentence = r || e.message;
    drawRefused();
  }
  bootOff();
}

/* the node's name, then where it is: two words apart, never "bayu-ungasanbali" (audit 15 Oct, item 25) */
const who = (name, place) => `${esc(name || 'this node')}${place ? `<small> · ${esc(place)}</small>` : ''}`;

function drawAll() {
  const h = D.health || {};
  document.documentElement.lang = h.locale || 'en';
  $('#who').innerHTML = who(D.node.name || h.node, D.node.place);
  $('#asof').textContent = `as of ${hhmm(D.as_of)}`;
  drawNow(); drawNode(h);
}

/* ---- Now (§5.1) ---- */
function drawNow() {
  const it = D.issues[leadKey] || D.issues[D.lead] || {};
  const hd = it.hero_distance || 'region';
  const hero = (it.stack || {})[hd] || {};
  const cmp = it.line != null ? `against the line, ${fmt(it.line, it.dp)} ${it.unit}` : 'this issue has no line';
  let s = `<div aria-live="polite">`
    + `<p class="t">${it.pix ? `<span class="pix" aria-hidden="true">${sign(it.pix)}</span> ` : ''}${said(it.title || it.sentence || '')}</p>`
    + (it.tagline ? `<p class="tag">${esc(it.tagline)}</p>` : '') + `</div>`
    + `<div class="hero"><span class="v">${num(`${it.metric}.${hd}`, hero.value, cmp, `<b>${esc(fmt(hero.value, it.dp))}</b>`)}</span>`
    + `<span class="u">${esc(it.unit || '')}</span> ${prov(hero.provenance)}`
    + `<p class="cmp">${it.line != null ? `against the line, ${esc(fmt(it.line, it.dp))} <span class="unit">${esc(it.unit || '')}</span>` : esc(cmp)}</p>`
    + (it.plain ? `<p class="plain">${said(it.plain)}</p>` : '') + `</div>`;
  /* the four distances are the walk's, below: its rail on the map and one chapter each */
  /* a pack's declared bands (doors-load.js), each beside its stage as on the doors' Now: decide and act under the card,
     observe under the other issues; the phone has no Did it work, so measure closes Now */
  const bands = declaredBands(D.sections);
  s += decideHTML(it) + (bands.decide || '');
  /* the other issues, one row each */
  const others = D.order.filter(k => k !== leadKey && D.issues[k]);
  if (others.length) {
    s += `<div class="rows">` + others.map(k => {
      const o = D.issues[k], ohd = o.hero_distance || 'region', ov = (o.stack || {})[ohd] || {};
      return `<button class="rowb" data-lead="${esc(k)}"><span class="rh"><span class="n">${said(o.name)}</span>`
        + `<span class="st${o.state === 'act' ? ' act' : ''}">${esc(stateWord(o.state || ''))}</span>`
        + (ov.value != null ? `<span class="v">${esc(fmt(ov.value, o.dp))} ${esc(o.unit || '')}</span>` : '')
        + `</span><span class="t2">${said(o.title || o.sentence || '')}</span></button>`;
    }).join('') + `</div>`;
  }
  s += (bands.observe || '') + (bands.measure || '') + captureHTML();
  $('#now-v').innerHTML = s;
}

/* ---- Add an image (SPEC_eyes step 1) ----
   One button under the rows, on an unlocked phone only — the POST needs the act token, so a locked phone gets
   the same offer the Decide card makes. The form asks for the picture, its kind and an optional note; where it
   was taken is the picture's own GPS (read by the node), else the phone's geolocation if allowed, else the node's cell. */
const CAPTURE_KINDS = ['phone', 'camera', 'microscope', 'drone', 'balloon'];
function captureHTML() {
  if (!hasToken()) return '';
  let actor = ''; try { actor = localStorage.getItem('planetai_actor') || ''; } catch (e) { /* no storage here */ }
  /* one button: it opens the library straight away, and the details ask only once an image is chosen (Tomas, 12 Oct) */
  return `<div class="capture" id="capture"><button class="sbtn" id="capopen">Add an image</button>`
    + `<input type="file" id="capfile" accept="image/jpeg,image/png,image/heic,image/heif,image/webp" hidden>`
    + `<form id="capf" hidden><p class="mut" id="capname"></p>`
    + `<label class="k" for="capkind">What took it</label>`
    + `<select id="capkind">${CAPTURE_KINDS.map(k => `<option value="${k}"${k === 'phone' ? ' selected' : ''}>${k}</option>`).join('')}</select>`
    + `<label class="k" for="capnote">A note, if it needs one</label>`
    + `<input id="capnote" maxlength="500" placeholder="what the image answers">`
    + (actor ? '' : `<label class="k" for="capactor">Your name</label><input id="capactor" autocomplete="name" required>`)
    + `<label class="mut"><input type="checkbox" id="capseen" checked> Describe it with the image model, on the node</label>`
    + `<button type="submit" class="sbtn primary">Keep it on the node</button><button type="button" class="sbtn" id="capcancel">Cancel</button>`
    + `<p class="dm">Where it was taken is the image's own location, else this phone's if you allow it, else the node's own cell. The node cleans the file of EXIF and GPS and keeps it; only a screen holding a token can see it.</p></form>`
    + `<p class="dm" id="capout" role="status"></p></div>`;
}

function captureClose() {
  $('#capfile').value = ''; $('#capnote').value = ''; $('#capf').hidden = true; $('#capopen').hidden = false;
}

async function captureSubmit(ev) {
  ev.preventDefault();
  const out = $('#capout'), file = $('#capfile').files[0];
  if (!file) { out.textContent = 'Choose an image first.'; return; }
  const actorEl = $('#capactor');
  let actor = ''; try { actor = localStorage.getItem('planetai_actor') || ''; } catch (e) { /* no storage here */ }
  if (actorEl) {
    const n = actorEl.value.trim();
    if (!n) { out.textContent = 'The node records who took it — your name first.'; actorEl.focus(); return; }
    actor = n;
    try { localStorage.setItem('planetai_actor', n); } catch (e) { /* no storage here */ }
  }
  const send = ev.target.querySelector('button[type="submit"]');
  if (send.disabled) return;
  send.disabled = true;   /* before the first await: two taps would otherwise send the picture twice */
  out.textContent = 'Asking this phone where it stands…';
  const point = await new Promise(res => {
    if (!('geolocation' in navigator)) return res(null);
    navigator.geolocation.getCurrentPosition(
      p => res({ lat: p.coords.latitude, lon: p.coords.longitude }),
      () => res(null), { timeout: 8000, maximumAge: 60000 });
  });
  const fd = new FormData();
  fd.append('photo', file, file.name || 'picture.jpg');
  fd.append('kind', $('#capkind').value);
  fd.append('note', $('#capnote').value);
  fd.append('actor', actor);
  fd.append('describe', $('#capseen').checked ? '1' : '');
  if (point) { fd.append('lat', point.lat); fd.append('lon', point.lon); }
  out.textContent = 'Sending it to the node…';
  try {
    const r = await fetch('/captures', { method: 'POST', headers: { ...DOORS_AUTH() }, body: fd });
    const body = await r.json().catch(() => ({}));
    if (!r.ok) {
      out.textContent = r.status === 401 || r.status === 403 ? WORDS.locked : (body.detail || `the node refused it (${r.status})`);
      return;
    }
    const c = body.capture || {};
    out.textContent = (body.duplicate ? 'The node already had it' : 'The node kept it')
      + ` — ${c.kind || 'image'}${c.at_home ? ', taken at home' : ''}. The walk counts it below.`
      + (body.describing ? ' The image model is describing it; its findings show in Data.' : $('#capseen').checked && !body.duplicate ? ' No image model is set on the node, so it was not described.' : '');
    captureClose();
  } catch (e) { out.textContent = WORDS.noreply; } finally { send.disabled = false; }
}

/* ---- the Decide card (§6) ---- */
function decideHTML(it) {
  /* whether something is asked is the node's one answer (/issues asking), as on Now and the Wall: an alert still true
     that no event stands for is asked too, and answered on Telegram */
  const ask = (it.asking || [])[0], E = D.events || [];
  const e = ask ? E.find(x => ask.event_id != null && x.id === ask.event_id) : E.find(x => x.issue === leadKey && !x.cleared_at);
  if (ask && !e) {
    return `<div class="decide"><div class="k">decide · ${said(it.name)} · asked since ${hhmm(ask.since)} · still open</div>`
      + `<p class="dq">${said(ask.says || '')}</p>${ask.how ? `<p class="dm">${said(ask.how)}</p>` : ''}</div>`;
  }
  if (!e) {
    return `<div class="decide"><p class="dq">Nothing is asked now.</p>`
      + `<p class="dm">${it.line != null ? `${esc(fmt(it.line, it.dp))} <span class="unit">${esc(it.unit || '')}</span> · ${esc(it.line_source || '')}` : 'this issue has no line'}</p></div>`;
  }
  let s = `<div class="decide" id="decide"><div class="k">decide · ${said(it.name)} · ${esc(kindWord(e.kind))} since ${hhmm(e.opened_at)}`
    + `${e.last_seen_at ? ` · watching, last seen ${hhmm(e.last_seen_at)}` : ''}`
    + `${e.peak != null ? ` · peak ${esc(fmt(e.peak, it.dp))} <span class="unit">${esc(it.unit || '')}</span>` : ''}</div>`
    + `<p class="dq">${said(e.action || 'The node asked for nothing specific.')}</p>`;
  const B = D.buttons || {};
  if (e.asking && DOORS_TOKEN()) {
    s += `<div class="ans" role="group" aria-label="Answer">`
      + ['done', 'not_now', 'doesnt_fit'].map(b => `<button data-ev="${e.id}" data-stage="${ANSWER_STAGE[b]}">${said(B[b] || b)}</button>`).join('')
      + `</div>`;
  } else if (e.asking) {
    s += `<p class="dm">${e.message && e.message.sent
      ? 'The node sent this to Telegram. Answer there, or <a href="#unlock" data-unlock>unlock this phone</a> to answer here.'
      : '<a href="#unlock" data-unlock>Unlock this phone</a> to answer here.'}</p>`;
  }
  if (e.answer) {
    const a = e.answer, Bw = { acted: B.done, acknowledged: B.not_now, dismissed: B.doesnt_fit };
    s += `<p class="dm" role="status">answered: ${said(Bw[a.stage] || a.stage)}${a.actor ? ` by ${esc(a.actor)}` : ''} at ${hhmm(a.ts)}`
      + `${a.held_until ? ` · held until ${hhmm(a.held_until)}` : ''}${a.note ? ` · “${esc(a.note)}”` : ''}</p>`;
  }
  return s + `<p class="dm" id="answered" role="status"></p></div>`;
}

/* the name the answer carries (§6.1): one field in the card the first time, kept under planetai_actor */
function nameForm(evId, stage) {
  const d = $('#decide'); if (!d) return;
  d.insertAdjacentHTML('beforeend', `<form class="unlock" id="namef"><label for="nme">Your name</label>`
    + `<input id="nme" autocomplete="name" required><button class="sbtn primary" type="submit">Send the answer</button></form>`);
  $('#nme').focus();
  $('#namef').onsubmit = ev => {
    ev.preventDefault();
    const n = $('#nme').value.trim(); if (!n) return;
    try { localStorage.setItem('planetai_actor', n); } catch (e) { /* no storage here */ }
    answer(evId, stage);
  };
}

async function answer(evId, stage) {
  const out = $('#answered');
  let actor = ''; try { actor = localStorage.getItem('planetai_actor') || ''; } catch (e) { /* no storage here */ }
  if (!actor) { nameForm(evId, stage); return; }
  try {
    const r = await fetch('/actions', { method: 'POST', headers: { 'content-type': 'application/json', ...DOORS_AUTH() },
      body: JSON.stringify({ event_id: Number(evId), stage, actor, note: '' }) });
    if (!r.ok) {
      const detail = (await r.json().catch(() => ({}))).detail || `the node refused it (${r.status})`;
      if (out) out.textContent = r.status === 401 || r.status === 403 ? WORDS.locked : detail;
      return;
    }
    D = await loadD(MOBILE_ROUTES); drawAll();
  } catch (e) { if (out) out.textContent = WORDS.noreply; }
}

/* ---- Node (§5.3): /health only, so it always draws ---- */
function drawNode(h) {
  const mesh = h.mesh && h.mesh.root_topic, radio = h.reticulum && h.reticulum.announce_s;
  let s = `<div class="facts">`
    + `<div class="fact"><div class="l">The node</div>${esc(h.node || 'this node')}${h.city ? `, in ${esc(h.city)}` : ''}</div>`
    + `<div class="fact"><div class="l">Running</div>${hasToken() ? `planetai-node ${esc(h.version || '')} · schema ${esc(h.schema || '')}<br>` : ''}`
    + `up ${fmt((h.uptime_s || 0) / 3600, 1)} h · last poll ${hhmm(h.last_poll)} · ${(h.ingested || 0).toLocaleString('en')} readings since the restart</div>`
    + `<div class="fact"><div class="l">The mesh and the radio</div>mesh ${mesh ? 'on' : 'off'} · radio ${radio ? 'on' : 'off'}</div>`;
  if (h.release && h.release.newer) s += `<div class="fact">A newer release is out.</div>`;
  const share = D ? D.share : null;
  s += `<div class="fact"><div class="l">This phone</div>`
    + (hasToken() ? `unlocked · <a href="#lock" data-lock>Lock this phone</a>`
                  : `locked · ${share === 'open' ? 'it reads what the node shares, and cannot answer it' : 'this phone is not shown the readings'} · <a href="#unlock" data-unlock>Unlock this phone</a>`)
    + `</div></div>`;
  $('#node-v').innerHTML = s;
}

/* ---- the refused state (§5.4) and the unlock field (§6.3) ---- */
function drawRefused() {
  const h = refusedHealth || {};
  document.documentElement.lang = h.locale || 'en';
  $('#who').innerHTML = who(h.node, h.city);
  $('#asof').textContent = 'locked';
  for (const el of [$('#walk'), $('.down')]) if (el) el.remove();   /* nothing to walk through on a refused phone */
  const block = `<div class="refused"><p class="lede">${esc(refusedSentence || 'This node is not sharing its readings with this screen.')}</p>`
    + `<p class="mut">Unlock this phone with the token for closing a loop, or ask whoever set this node up to turn sharing on. <code>planetai ui</code> on the node prints the tokens.</p>`
    + unlockHTML() + `</div>`;
  $('#now-v').innerHTML = block;
  drawNode(h);
}

function unlockHTML() {
  return `<form class="unlock" id="sunlock"><label for="sact">Token for closing a loop</label>`
    + `<input type="password" id="sact" autocomplete="off" placeholder="answers alerts, changes nothing">`
    + `<button type="submit" class="sbtn primary">Unlock this phone</button></form>`;
}

/* ---- the one click handler and the one submit handler ---- */
document.addEventListener('click', ev => {
  const t = ev.target;
  const ans = t.closest && t.closest('.decide .ans button[data-ev]');
  if (ans) { ev.preventDefault(); ans.disabled = true; answer(ans.dataset.ev, ans.dataset.stage); return; }
  const row = t.closest && t.closest('.rowb[data-lead]');
  if (row) { ev.preventDefault(); leadKey = row.dataset.lead; drawNow(); if (window.WALK_ISSUE) WALK_ISSUE(leadKey); $('#now-v').scrollIntoView(); return; }
  const un = t.closest && t.closest('a[data-unlock]');
  if (un) {
    ev.preventDefault();
    if (!$('#sunlock')) ( $('#node-v') || $('main') ).insertAdjacentHTML('beforeend', unlockHTML());
    $('#sunlock').scrollIntoView(); $('#sact').focus(); return;
  }
  const lock = t.closest && t.closest('a[data-lock]');
  if (lock) {
    ev.preventDefault();
    try { localStorage.removeItem('planetai_act'); localStorage.removeItem('planetai_admin'); } catch (e) { /* no storage here */ }
    location.reload();
    return;
  }
  const reg = t.closest && t.closest('.reg button[data-r]');
  if (reg) {
    document.documentElement.dataset.theme = reg.dataset.r;   /* walk.js repaints its map on this attribute */
    try { localStorage.setItem('planetai_theme', reg.dataset.r); } catch (e) { /* no storage here */ }
    regOn(); return;
  }
  if (t.id === 'capopen') { $('#capout').textContent = ''; $('#capfile').click(); return; }
  if (t.id === 'capcancel') captureClose();
});

document.addEventListener('change', ev => {
  if (ev.target.id === 'capfile') {
    const f = ev.target.files[0]; if (!f) return;
    $('#capname').textContent = `${f.name || 'the image'} (${Math.max(1, Math.round(f.size / 1024 / 1024))} MB)`;
    $('#capopen').hidden = true; $('#capf').hidden = false;
  }
});

document.addEventListener('submit', ev => {
  if (ev.target.id === 'capf') { captureSubmit(ev); return; }
  if (ev.target.id !== 'sunlock') return;
  ev.preventDefault();
  const t = $('#sact').value.trim();
  if (t) { try { localStorage.setItem('planetai_act', t); } catch (e) { /* no storage here */ } location.reload(); }
});

/* freshness (§7): no timer — a visible-again page older than five minutes asks again */
document.addEventListener('visibilitychange', async () => {
  if (document.hidden || !D || !D.as_of) return;
  if (Date.now() - Date.parse(D.as_of) > 5 * 60 * 1000) { try { D = await loadD(MOBILE_ROUTES); drawAll(); } catch (e) { /* keep what is drawn */ } }
});

/* the walk (§11.2) needs MapLibre, the one heavy library on this page: watched for only once Now has drawn, and
   fetched when the walk nears the screen, so Now comes first on a slow phone; then walk.js draws into #walk */
/* the switch in the foot shows the register the page is in, chosen or the system's */
const regOn = () => document.querySelectorAll('.reg button').forEach(b => b.setAttribute('aria-pressed', b.dataset.r === document.documentElement.dataset.theme));
regOn();

boot().then(() => {
  if ('IntersectionObserver' in window && $('#walk')) {
  const wio = new IntersectionObserver(es => {
    if (!es.some(e => e.isIntersecting)) return;
    wio.disconnect();
    const add = (tag, at) => new Promise(ok => { const e = document.createElement(tag); Object.assign(e, at, { onload: ok }); document.head.appendChild(e); });
    add('link', { rel: 'stylesheet', href: '/static/maplibre-gl.css' });
    add('script', { src: '/static/maplibre-gl.js' }).then(() => add('script', { src: '/static/walk.js' }));
  }, { rootMargin: '200px' });
  wio.observe($('#walk'));
} });
