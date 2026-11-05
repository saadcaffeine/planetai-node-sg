'use strict';
/* SET UP — a page of its own (R43, 7 Oct 2026), opened by the gear in the bar. How this node was told to behave.

   Design (refero-design, reference-locked): mono.frm.fm's architectural grid owns the canvas — 1px ink rules, square
   corners, outlined controls, tracked mono labels, colour only where the node's rules give it a meaning; Linear's
   preferences own the structure — a sticky list of sections on the left, rows of label and help with the control on
   the right; Arcade's privacy settings own the share level — two options, each saying what a screen without the
   token gets; Enode's developer settings own the save — explicit, saying what it will change, with what crosses the
   house's edge set apart. The one move to remember: every setting that changes what leaves this machine says so,
   and the save bar counts them before anything is written.

   Behaviour is the dashboard's Set up pane (dashboard.js, "the Set up pane"), carried over rule for rule because
   each rule was learned on node #1: a save sends only what changed; a key that moved on the node while this page
   was open is not overwritten until the keeper has seen it; the node's own refusal is printed beside its field; a
   key with choices offers only them; a secret is write-only; the pack switches write PACKS_ENABLED; what is read at
   start is shown and never sent. ponytail: the group words are copied from dashboard.js (GROUPS) because four suites
   read that pane out of that file by name; one copy when / becomes the doors. */
const SETUP = { desc: null, packs: [], listed: [], wild: null, job: null, sources: null, group: null, loaded: {}, drawnPacks: '', dirty: false, history: null };
const SETUP_GROUPS = {
  basics: ['Basics', 'This place: what it watches, in order, what kind of node it is, its language and how its page opens. Its name, city, position and time zone are read once at start.'],
  sources: ['Sources', 'What the node reads: your sensors, your account, and the public stations and portals around you. Sources that come as packs are switched on and set under Packs.'],
  alerts: ['Alerts', 'Reports at the hours you choose, in this node’s own time zone; between them, only what you asked to be interrupted for; and how a loop is closed.'],
  model: ['Model', 'Which model answers, here and on Telegram alike. The strongest one the node can reach is used, and its keys are under Keys.'],
  packs: ['Packs', 'Which packs load, each with its own settings in its card. Code packs stay off until you allow them; read one before you do.'],
  keys: ['Keys', 'Every secret in one place. Each is masked once saved and never shown again.'],
  sharing: ['Sharing', 'Who may read this node, and everything it sends or announces beyond this machine. Raw readings stay here; only hourly averages, Index scores and the share of alerts answered leave.'],
  system: ['System', 'Tuning numbers, and what is read once at start: the port, extra containers, backups, the poll interval.'],
};
/* The menu in five categories, each section with one line on what it holds (Tomas, 24 Oct 2026: "group by categories,
   and make a hover explainer of what the menu contains, it is difficult to grasp"). A group a pack or a newer node
   declares that no category names goes to the last one, so nothing a node declares is ever left out of the menu. */
const SETUP_CATS = [
  ['This place', ['basics', 'rooms']],
  ['What it reads', ['sources', 'packs']],
  ['How it speaks', ['alerts', 'model']],
  ['Who can see it', ['sharing', 'keys', 'screen']],
  ['The machine', ['system', 'machine', 'updates']],
];
const SETUP_TIPS = {
  basics: 'This place: what it watches and in which order, its language, and how its page opens.',
  rooms: 'The room each of your own sensors is in. Alerts and every page use these names.',
  sources: 'Your sensors and accounts, and the public stations and global models around you.',
  packs: 'Which packs this node loads, and each pack’s own settings.',
  alerts: 'When the reports come, what is allowed to interrupt you, and how a loop is closed.',
  model: 'Which model answers questions, here and on Telegram.',
  sharing: 'Who on your network can read this node, and what leaves it.',
  keys: 'Every secret: tokens and API keys. Masked once saved, never shown again.',
  screen: 'Unlock this screen with the admin token to change settings, or lock it again.',
  system: 'Tuning numbers, Grafana, and what is read once at start.',
  machine: 'The computer the node runs on: its disk, and how long the space lasts.',
  updates: 'Which version runs, whether a newer one is out, and how to update.',
};
const SETUP_BOOLS = /^(OPENMETEO_ENABLED|SENSOR_INDOOR|MESH_ALERTS|HA_DISCOVERY|EXPORT_ENABLED|IPFS_PUBLISH|QUIET_HOURS|PACKS_ALLOW_CODE)$/;
/* What a screen without the token gets at each level: the node's own rule (app/main.py _SHARE_OFF / _SHARE_OPEN). */
const SHARE_WORDS = {
  off: ['Off', 'A screen on this network without the token gets the page, the node’s name and the daily open export. Nothing else.'],
  open: ['Open', 'Screens on this network read the issues, the stations, the models and the Index. The map, the cells, the hourly table and the household’s notes still need the token.'],
};
const sq = s => document.querySelector('#setupv2 ' + s), sqa = s => document.querySelectorAll('#setupv2 ' + s);
const sTitle = g => (SETUP_GROUPS[g] || [g.charAt(0).toUpperCase() + g.slice(1)])[0];
const sGroups = d => { const seen = []; for (const r of d.runtime || []) if (!seen.includes(r.group)) seen.push(r.group);
  for (const b of d.bootstrap || []) if (b.group && !seen.includes(b.group)) seen.push(b.group); return seen; };
const SECTIONS = () => sCats().flatMap(([, secs]) => secs);
/* the categories as this node has them: a declared group in its category, any other one in the last */
const sCats = () => {
  const have = new Set([...(SETUP.desc ? sGroups(SETUP.desc) : []), 'rooms', 'machine', 'screen', 'updates']);
  const named = new Set(SETUP_CATS.flatMap(([, secs]) => secs));
  const cats = SETUP_CATS.map(([t, secs]) => [t, secs.filter(x => have.has(x))]);
  cats[cats.length - 1][1].push(...[...have].filter(x => !named.has(x)));
  return cats.filter(([, secs]) => secs.length);
};
/* what a section holds, for its explainer: its settings' names, or its packs' */
const sHolds = g => {
  const d = SETUP.desc || {}, rows = (d.runtime || []).filter(r => r.group === g && !r.pack);
  const names = g === 'packs' ? (SETUP.packs || []).map(p => p.name || p.id) : rows.map(r => r.label);
  if (!names.length) return '';
  return names.length > 6 ? `${names.slice(0, 6).join(', ')} and ${names.length - 6} more` : names.join(', ');
};
const sName = g => ({ screen: 'This screen', updates: 'Updates', machine: 'Machine', rooms: 'Rooms' })[g] || sTitle(g);

VIEWS.setup = async function () {
  if (!SETUP.desc) await setupLoad();
  const want = location.hash.split('/')[1];                 /* #setup/<section> opens at that section */
  if (want && SECTIONS().includes(want) && want !== SETUP.group) { SETUP.group = want; SETUP.dirty = false; }
  setupDraw();
};

async function setupLoad() {
  const tok = (() => { try { return localStorage.getItem('planetai_admin') || ''; } catch (e) { return ''; } })();
  SETUP.desc = await fetch('/settings', { headers: tok ? { authorization: 'Bearer ' + tok } : {} }).then(r => r.json()).catch(() => null);
  /* every pack this node could run: what is on its disk, and the wild list's packs that are not (app/wild.py) */
  const all = await doorsFetch('/packs/all').then(r => r.ok ? r.json() : null).catch(() => null);
  SETUP.packs = all ? all.packs.filter(p => p.installed) : []; SETUP.listed = all ? all.packs.filter(p => !p.installed) : []; SETUP.wild = all ? all.list : null;
  SETUP.job = tok ? await doorsFetch('/packs/install').then(r => r.ok ? r.json() : null).catch(() => null) : null;
  if (SETUP.job && /waiting|running/.test(SETUP.job.state)) sPoll();
  [SETUP.storage, SETUP.machine] = await Promise.all(['storage', 'machine'].map(r => doorsFetch('/' + r).then(x => x.ok ? x.json() : null).catch(() => null)));
  SETUP.history = tok ? await doorsFetch('/actions?stage=settings&limit=40').then(r => r.ok ? r.json() : null).catch(() => null) : null;
  SETUP.sources = tok ? await doorsFetch('/health/sources').then(r => r.ok ? r.json() : null).catch(() => null) : null;
  const hash = location.hash.split('/')[1];
  if (hash && SECTIONS().includes(hash)) SETUP.group = hash;
  if (!SETUP.group || !SECTIONS().includes(SETUP.group)) SETUP.group = SETUP.desc && SETUP.desc.unlocked ? (sGroups(SETUP.desc)[0] || 'screen') : 'screen';
}

function setupDraw() {
  const d = SETUP.desc, el = $('#setupv2');
  if (!d) { el.innerHTML = `<p class="fine">GET /settings did not answer this screen.</p>`; return; }
  const unlocked = !!d.unlocked, rows = d.runtime || [], g = SETUP.group;
  const setHere = k => rows.filter(r => r.group === k && r.source === 'gui').length;
  el.innerHTML = `<header class="sh" data-learn="settings" data-reads="/settings" data-pack="core"><div class="k">Set up · ${esc(D.node.name)}</div><h1>How this node was told to behave.</h1>`
    + `<p class="lede">Everything here is live within about twenty seconds; nothing needs a restart. A blank field hands the setting back to <code>.env</code>, and a value set here overrides it.</p></header>`
    + `<div class="sgrid" data-learn="setup-sections" data-reads="/settings /health/sources"><nav class="snav" aria-label="Set up sections">${sCats().map(([cat, secs]) => `<div class="scat" aria-hidden="true">${esc(cat)}</div>`
      + secs.map(s => { const holds = sHolds(s);
        return `<a href="#setup/${s}" class="${s === g ? 'on' : ''}" data-s="${s}" aria-describedby="tip-${s}">`
        + `<span>${esc(sName(s))}</span>${s === 'screen' ? `<i>${unlocked ? 'unlocked' : 'locked'}</i>` : s === 'updates' ? (D.health.release || {}).newer ? '<i>new</i>' : '' : s === 'machine' ? (SETUP.storage && SETUP.storage.days_left != null ? `<i>${sDays(SETUP.storage.days_left)}</i>` : '') : s === 'packs' && SETUP.listed.some(p => p.new) ? '<i>new</i>' : setHere(s) ? `<i>${setHere(s)} set</i>` : ''}`
        + `<span class="tip" role="tooltip" id="tip-${s}"><b>${esc(sName(s))}</b>${esc(SETUP_TIPS[s] || (SETUP_GROUPS[s] || [])[1] || '')}${holds ? `<em>Holds: ${esc(holds)}</em>` : ''}</span></a>`; }).join('')).join('')}</nav>`
    + `<section class="spane" aria-live="polite" data-learn="setup-save" data-reads="/settings /actions">${sTodo()}${g === 'screen' ? sScreen(unlocked) : g === 'updates' ? sUpdates() : g === 'machine' ? sMachine() : g === 'rooms' ? sRooms(unlocked) : sGroup(g, unlocked)}</section></div>`
    + `<div class="sbar" id="sbar" hidden><span id="scount"></span><span class="sp"></span><button type="button" class="sbtn" id="sdiscard">Discard</button><button type="button" class="sbtn primary" id="ssave">Save changes</button></div>`;
  sqa('.snav a').forEach(a => a.onclick = ev => {
    ev.preventDefault();
    if (SETUP.dirty && !confirm('This section has a change you have not saved. Leave it and lose the change?')) return;
    SETUP.group = a.dataset.s; SETUP.dirty = false; history.replaceState(null, '', '#setup/' + a.dataset.s); setupDraw(); window.scrollTo(0, 0);
  });
  SETUP.drawnPacks = sPackSwitches(); SETUP.loaded = sValues(); SETUP.dirty = false; sCount();
  const tokForm = sq('#sunlock'); if (tokForm) tokForm.onsubmit = sUnlock;
  const qrB = sq('#sqrb'); if (qrB) qrB.onclick = sQR;
  const lockB = sq('#slock'); if (lockB) lockB.onclick = () => { try { localStorage.removeItem('planetai_admin'); localStorage.removeItem('planetai_act'); } catch (e) { /* none */ } location.reload(); };
  sq('#ssave').onclick = () => sSave(); sq('#sdiscard').onclick = () => { SETUP.dirty = false; setupDraw(); };
  sqa('[data-room]').forEach(f => f.onsubmit = sRoom);
  /* a pack card opens on its own (Tomas, 24 Oct 2026: "Bali Air Dispatch itself", not the rows inside it); the pane's
     button opens or closes every card, and this browser remembers the choice */
  sqa('.px').forEach(b => b.onclick = () => { const card = b.closest('.pcard'), open = !card.classList.contains('open');
    card.classList.toggle('open', open); b.setAttribute('aria-expanded', String(open)); b.textContent = open ? '−' : '+'; });
  const all = sq('#sopenall'); if (all) all.onclick = () => { const on = !sOpenAll();
    try { localStorage.setItem('planetai_setup_packs_open', on ? '1' : ''); } catch (e) { /* a private window: this page only */ SETUP.openAll = on; }
    setupDraw(); };
  sqa('[data-install]').forEach(b => b.onclick = () => sInstall(b.dataset.install));
}
const sOpenAll = () => { try { return localStorage.getItem('planetai_setup_packs_open') === '1'; } catch (e) { return !!SETUP.openAll; } };

/* INSTALL A WILD PACK (docs/decisions/2026-10-27-pack-install-from-the-page.md). Before anything is fetched the keeper
   reads what the node read from the pack's pack.yaml at the commit it would install: who wrote it, where it comes
   from, whether it runs code here and what libraries it adds. Install sends that commit and nothing else; the host
   picks the request up within a minute and this page follows it through the fetch, a rebuild and the restart. */
async function sInstall(id) {
  let p = sq('#sinstall');
  if (!p) { p = document.createElement('div'); p.id = 'sinstall'; p.className = 'sconfirm'; p.setAttribute('role', 'alertdialog'); p.setAttribute('aria-labelledby', 'sinstall-h'); $('#setupv2').append(p); }
  const close = () => { p.hidden = true; const b = sq(`[data-install="${id}"]`); b && b.focus(); };
  p.onkeydown = e => { if (e.key === 'Escape') close(); };
  p.innerHTML = `<h3 id="sinstall-h">Reading ${esc(id)} at the commit it would be installed at…</h3>`; p.hidden = false;
  const r = await doorsFetch('/packs/preview?id=' + encodeURIComponent(id)).catch(() => null);
  const v = r ? await r.json().catch(() => ({})) : {};
  if (!(r && r.ok)) {
    p.innerHTML = `<h3 id="sinstall-h">Could not read ${esc(id)}</h3><p>${esc(typeof v.detail === 'string' ? v.detail : 'The node did not answer.')}</p><div class="acts"><button type="button" class="sbtn" data-a="back">Back</button></div>`;
    p.querySelector('[data-a=back]').onclick = close; p.querySelector('[data-a=back]').focus(); return;
  }
  const allow = ((SETUP.desc.runtime || []).find(x => x.key === 'PACKS_ALLOW_CODE') || {}).value === '1', stop = v.refused || v.loads_here;
  const li = (b, t) => `<li><b>${b}</b><p>${t}</p></li>`;
  p.innerHTML = `<h3 id="sinstall-h">Install ${esc(v.name)}?</h3><p>Nothing has been fetched yet. This is what the node read from its <code>pack.yaml</code> at the commit it would install.</p><ul>`
    + li('Who wrote it', `${esc(v.author || 'not said')}. ${v.status === 'reviewed' ? 'Reviewed: somebody who keeps the wild list has read it.' : 'Listed, not reviewed: nobody who keeps the wild list has read it.'}${v.licence ? ` ${esc(v.licence)}.` : ''}`)
    + li('Where it comes from', `<code>${esc(v.source)}</code> at commit <code>${esc(v.commit.slice(0, 12))}</code>. <a href="${esc(v.code_url)}" target="_blank" rel="noopener">Read its code at this commit</a>.`)
    + li('What it reads', `${esc(v.reads)}${v.metrics.length ? ` (${esc(v.metrics.join(', '))})` : ''}.${v.needs ? ` ${esc(v.needs)}` : ''}`)
    + (v.kind === 'code' ? li('<span class="why">runs code here</span>', `Its Python runs on this machine with the node’s privileges and everything it holds. It runs only while Allow code packs is on, ${allow ? 'which it is on this node' : 'which it is not on this node yet: that switch is above, once you have read the code'}.`) : '')
    + (v.pip.length ? li('Libraries it adds', `Installed into the node’s image, a rebuild of a few minutes: ${v.pip.map(x => `<code>${esc(x)}</code>`).join(' ')}`) : '')
    + (v.settings.length ? li('Settings it asks for', `${v.settings.map(x => `<code>${esc(x)}</code>`).join(' ')}, in its card here once it is installed.`) : '')
    + (stop ? li('It cannot be installed here', esc(v.refused || `It would not load on this node: ${v.loads_here}`)) : '')
    + `</ul><div class="acts"><button type="button" class="sbtn" data-a="back">Back</button>${stop ? '' : '<button type="button" class="sbtn primary" data-a="go">Install</button>'}</div>`;
  p.querySelector('[data-a=back]').onclick = close; p.querySelector('[data-a=back]').focus();
  const go = p.querySelector('[data-a=go]'); if (!go) return;
  go.onclick = async () => {
    go.disabled = true;
    const q = await fetch('/packs/install', { method: 'POST', headers: { 'content-type': 'application/json', ...DOORS_AUTH() }, body: JSON.stringify({ id, commit: v.commit }) }).catch(() => null);
    const j = q ? await q.json().catch(() => ({})) : {};
    if (!(q && q.ok)) { go.disabled = false; return toast2(typeof j.detail === 'string' ? j.detail : 'The node did not take the request.', true); }
    p.hidden = true; SETUP.job = { ...j, pip: v.pip.length > 0, waited_s: 0 }; sJobShow(); sPoll();
  };
}
function sJobLine(j) {
  const sha = (j.commit || '').slice(0, 12);
  if (j.state === 'waiting') return j.stuck ? `Asked ${Math.round(j.waited_s / 60)} minutes ago and not picked up: this node has no crontab line for it. On the node: planetai packs pending, then planetai packs cron so the next one is picked up by itself.`
    : 'Asked. The node picks it up within a minute.';
  if (j.state === 'running') return `${j.line}${j.pip && /fetching/.test(j.line || '') ? ', with a rebuild of a few minutes' : ''}…`;
  if (j.state === 'restarting') return 'The node is restarting to load it. This page keeps asking.';
  if (j.state === 'done') return `Installed at ${sha}. It is in the list above, switched on.`;
  if (j.state === 'failed') return `Not installed: ${j.line || 'the node did not say why'}. The whole log is out/requests/pack-add.log on the node.`;
  return '';
}
function sJobShow() { const el = SETUP.job && sq('#pjob-' + SETUP.job.id); if (el) el.textContent = sJobLine(SETUP.job); }
/* every four seconds while an install runs. The node goes away while it restarts, and that is said, not shown as an error */
function sPoll() {
  clearTimeout(SETUP.poll);
  SETUP.poll = setTimeout(async () => {
    const r = await doorsFetch('/packs/install').catch(() => null), was = SETUP.job || {};
    const j = r && r.ok ? await r.json().catch(() => null) : null;
    SETUP.job = j ? { ...j, pip: was.pip } : (/running|restarting/.test(was.state) ? { ...was, state: 'restarting' } : was);
    sJobShow();
    if (/waiting|running|restarting/.test(SETUP.job.state)) return sPoll();
    if (SETUP.job.state === 'done') { toast2(`${SETUP.job.id} is installed.`); if (!SETUP.dirty) { await setupLoad(); setupDraw(); } }
    if (SETUP.job.state === 'failed') toast2(`${SETUP.job.id} was not installed.`, true);
  }, 4000);
}

/* To finish setting up (15 Oct 2026): the node's fundamental sources that are not running, most important first, each
   with the node's own fix and a link to the section it is set in. The list and the words are GET /health/sources
   (app/fundamentals.py), the same the doctor prints after an install or an update; this page draws, it decides nothing. */
function sTodo() {
  const todo = ((SETUP.sources || {}).sources || []).filter(r => r.ok === false);
  if (!todo.length) return '';
  return `<div class="gate"><b>To finish setting up</b><ol>${todo.map(r => { const g = (r.setup || '').split('/')[1];
    return `<li><b>${esc(r.name)}.</b> ${esc(r.fix)}${g && g !== SETUP.group ? ` <a href="#setup/${esc(g)}" data-go="${esc(g)}">Go to ${esc(sName(g))}</a>` : ''}</li>`; }).join('')}</ol></div>`;
}

/* Rooms (Tomas, 14 Oct 2026): the household's word for where each of its own sensors is. The node makes it the
   sensor's name whatever its platform calls it (init.sql 0.61), so alerts, the report and every page say "Kids", not
   "K ROOM - BAYU HOLES". Each row saves on its own: a room is not a setting, and has no .env behind it. */
function sRooms(unlocked) {
  const S = (D.sensors || []).filter(s => s.local && s.kind === 'sensor');
  if (!unlocked) return `<h2>Rooms</h2><p class="gate">Which room is which is the household’s: <a href="#setup/screen" data-go="screen">unlock this screen</a> with the admin token to name them.</p>`;
  return `<h2>Rooms</h2><p class="blurb">Name the room each of this home’s sensors is in. Every alert, the report and every page use the name you give; the Wall never shows one. Leave it empty to use the sensor’s own name again.</p>`
    + `<div class="rows">${S.map(s => `<form class="srow" data-room="${esc(s.sensor_id)}"><div class="sl"><label for="room-${esc(s.sensor_id)}">${esc(s.source_name || s.name || s.sensor_id)}</label>`
      + `<div class="sm"><code>${esc(s.sensor_id)}</code>${s.indoor ? ' · inside' : ' · outside'}</div></div>`
      + `<div class="sc"><input id="room-${esc(s.sensor_id)}" maxlength="40" value="${esc(s.room || '')}" placeholder="${esc(s.source_name || s.name || '')}"><button class="sbtn">Save</button></div>`
      + `<p class="err" role="status"></p></form>`).join('') || '<p class="fine">This node has no sensors of its own yet.</p>'}</div>`;
}
async function sRoom(ev) {
  ev.preventDefault();
  const f = ev.currentTarget, sid = f.dataset.room, say = f.querySelector('[role=status]');
  const r = await doorsFetch(`/sensors/${encodeURIComponent(sid)}`, { method: 'PATCH', headers: { ...DOORS_AUTH(), 'content-type': 'application/json' },
    body: JSON.stringify({ room: f.querySelector('input').value.trim() || null }) }).catch(() => null);
  const j = r ? await r.json().catch(() => ({})) : {};
  if (!(r && r.ok)) { say.textContent = `Not saved: ${j.detail || (r ? r.status : 'the node did not answer')}`; return; }
  const s = (D.sensors || []).find(x => x.sensor_id === sid); if (s) Object.assign(s, j.sensor);
  say.textContent = j.sensor.room ? `Saved: this sensor is “${j.sensor.room}” everywhere now.` : 'Saved: back to the sensor’s own name.';
}

/* one row: the label, the node's help and where its value comes from; the control on the right; the refusal under it */
function sRow(r, unlocked) {
  const id = 'set-' + r.key, dis = unlocked ? '' : ' disabled';
  const src = r.source === 'gui' ? 'set here' : r.source === 'env' ? 'from .env' : 'default';
  const out = r.outward ? `<span class="out" title="This setting changes what leaves this machine">↗ leaves this machine</span>` : '';
  const left = `<div class="sl"><label for="${id}">${esc(r.label)}</label><div class="sm"><code>${esc(r.key)}</code> · ${src}${out}</div><p class="help" id="help-${r.key}">${esc(r.help)}</p></div>`;
  const err = `<p class="err" id="err-${r.key}" role="alert" hidden></p>`;
  let ctl;
  if (r.key === 'SHARE_LEVEL') {
    ctl = `<div class="share" role="radiogroup" aria-labelledby="${id}">${Object.entries(SHARE_WORDS).map(([v, [t, s2]]) =>
      `<label class="opt ${(r.value || 'off') === v ? 'on' : ''}"><input type="radio" name="SHARE_LEVEL" value="${v}" data-key="SHARE_LEVEL" ${(r.value || 'off') === v ? 'checked' : ''}${dis}><b>${t}</b><span>${s2}</span></label>`).join('')}</div>`;
    return `<div class="srow wide">${left}${ctl}${err}</div>`;
  }
  if (SETUP_BOOLS.test(r.key) || (r.pack && /_ENABLED$/.test(r.key))) {   /* a pack's own on-switch, whichever pack */
    const on = r.value === '1';
    ctl = `<button type="button" role="switch" aria-checked="${on}" aria-labelledby="${id}" id="${id}" class="sw ${on ? 'on' : ''}" data-key="${esc(r.key)}" data-bool="1"${dis}><span>${on ? 'on' : 'off'}</span></button>`;
  } else {
    const opts = r.key === 'ALERT_LOCALE' ? [['en', 'English'], ['id', 'Bahasa Indonesia'], ['es', 'Español']] : (r.choices || []).map(v => [v, v]);
    if (opts.length) ctl = `<select id="${id}" aria-describedby="help-${r.key}" data-key="${esc(r.key)}"${dis}>`
      + (!r.set ? `<option value="" selected>— not set: the node’s default —</option>` : '')
      + opts.map(([v, l]) => `<option value="${esc(v)}"${r.value === v ? ' selected' : ''}>${esc(l)}</option>`).join('') + `</select>`;
    else ctl = `<input id="${id}" aria-describedby="help-${r.key}" data-key="${esc(r.key)}" autocomplete="off"${dis}`
      + (r.secret ? ` type="password" placeholder="${r.set ? 'set · type to replace' : 'not set'}"` : ` type="text" value="${esc(r.value)}" placeholder="${r.source === 'default' ? 'not set: the node’s default' : ''}"`) + `>`;
  }
  return `<div class="srow">${left}<div class="sc">${ctl}${err}</div></div>`;
}

function sGroup(g, unlocked) {
  const d = SETUP.desc, rows = (d.runtime || []).filter(r => r.group === g), mine = rows.filter(r => !r.pack);
  const gate = unlocked ? '' : `<p class="gate">This screen reads the settings the node makes public and cannot change any of them. <a href="#setup/screen" data-go="screen">Unlock it with the admin token</a> to change them.</p>`;
  let body = mine.map(r => sRow(r, unlocked)).join('');
  if (g === 'packs') {
    const on = ((d.runtime || []).find(r => r.key === 'PACKS_ENABLED') || {}).value || '', only = on ? on.split(',').map(x => x.trim()) : null;
    body = `<div class="packs">${SETUP.packs.map(p => { const live = !only || only.includes(p.id);
      const mine = rows.filter(r => r.pack === p.id), open = sOpenAll(), n = mine.length;
      /* why a pack that is on does not run: the node's words (GET /packs/all). Off says so on its switch. */
      const why = live && p.why && p.why !== 'switched off' ? ` · <b>${esc(p.why)}</b>` : '';
      return `<section class="pcard${open ? ' open' : ''}" id="pack-${esc(p.id)}"><div class="ph"><button type="button" role="switch" class="sw ${live ? 'on' : ''}" aria-checked="${live}" data-pack="${esc(p.id)}" aria-label="${esc(p.name)}"${unlocked ? '' : ' disabled'}><span>${live ? 'on' : 'off'}</span></button>`
        + `<div class="pt"><b>${esc(p.name || p.id)}</b><div class="sm">${p.tier === 'wild' ? 'wild · ' : ''}${esc(p.kind || '')}${p.domain ? ` · ${esc(p.domain)}` : ''} · v${esc(p.version || '')} · ${n ? `${n} setting${n === 1 ? '' : 's'}` : 'no settings'}${why}</div></div>`
        + `<button type="button" class="px" aria-expanded="${open}" aria-controls="pbody-${esc(p.id)}" aria-label="${esc(p.name || p.id)}: what it does and its settings">${open ? '−' : '+'}</button></div>`
        + `<div class="pbody" id="pbody-${esc(p.id)}"><p class="help">${esc(p.description || '')}</p><div class="sm">${esc(p.author || '')}</div>`
        + (p.tier === 'wild' ? `<p class="help">From ${esc(p.source || 'a repository')} at ${esc((p.commit || '').slice(0, 12))}, added ${esc(p.added || '')}. To update it, on the node: <code>planetai packs add ${esc(p.id)}</code>. To remove it, in the node’s folder: <code>rm -rf packs/${esc(p.id)}</code>, then <code>planetai restart</code>.</p>` : '')
        + mine.map(r => sRow(r, unlocked)).join('') + `</div></section>`; }).join('')}</div>` + body;
    /* the wild list's packs that are not on this disk (decision 2026-10-27): Install asks the host, which fetches it */
    const W = SETUP.wild || {};
    body += `<h3 class="sub2">On the wild list, not here yet</h3><p class="blurb">Packs other people wrote, each in its own repository and listed at fabcity/planetai-wild-packs. Install shows who wrote one, where it comes from and what it brings before anything is fetched. Then the node fetches it, installs it and restarts, in a minute or a few.</p>`
      + (W.read === false || !SETUP.wild ? `<p class="gate">This node could not read the wild list just now${W.error ? ` (${esc(W.error)})` : ''}, so only the packs on its disk are above.</p>` : '')
      + (SETUP.listed.length ? `<div class="packs">${SETUP.listed.map(p => `<section class="pcard" id="pack-${esc(p.id)}"><div class="ph">`
        + `<button type="button" class="sbtn" data-install="${esc(p.id)}"${unlocked ? '' : ' disabled title="Unlock this screen with the admin token to install"'}>Install</button>`
        + `<div class="pt"><b>${esc(p.name)}</b>${p.new ? '<i class="new">new</i>' : ''}<div class="sm">wild · ${esc(p.kind)} · ${p.status === 'reviewed' ? 'reviewed' : 'listed, not reviewed'} · ${esc(p.author)}</div></div>`
        + `<button type="button" class="px" aria-expanded="false" aria-controls="pbody-${esc(p.id)}" aria-label="${esc(p.name)}: what it reads">+</button></div>`
        + `<p class="pjob" id="pjob-${esc(p.id)}" role="status">${SETUP.job && SETUP.job.id === p.id ? esc(sJobLine(SETUP.job)) : ''}</p>`
        + `<div class="pbody" id="pbody-${esc(p.id)}"><p class="help">It reads ${esc(p.reads)}</p><div class="sm">${esc(p.source)} · ${esc(p.licence)} · tested with ${esc(p.tested_with)}</div></div></section>`).join('')}</div>`
        : W.read ? '<p class="fine">Every pack on the wild list is installed here.</p>' : '');
  }
  /* what is read once at start: one table, and the way to change it said once. Grafana's three keys are its own block. */
  const B = (d.bootstrap || []).filter(b => (b.group || 'system') === g && !/^GRAFANA_/.test(b.key));
  const boot = B.length ? `<h3 class="sub2">Read at start</h3><p class="blurb">Change these in <code>.env</code> on the node, then run <code>planetai restart</code>.</p>`
    + `<table class="tbl ro"><tr><th>setting</th><th class="hide">key</th><th>value</th></tr>${B.map(b => `<tr><td>${esc(b.label)}</td><td class="hide mono">${esc(b.key)}</td>`
      + `<td class="mono">${b.value ? esc(b.value) : '<span class="fine">not set</span>'}</td></tr>`).join('')}</table>` : '';
  const changed = (SETUP.history || []).filter(a => rows.some(r => String(a.note || '').split(', ').includes(r.key))).slice(0, 5);
  return `<div class="dh"><h2>${esc(sTitle(g))}</h2>${g === 'packs' && SETUP.packs.length ? `<button type="button" class="sbtn sdet" id="sopenall" aria-pressed="${sOpenAll()}">${sOpenAll() ? 'Close all packs' : 'Open all packs'}</button>` : ''}</div><p class="blurb">${esc((SETUP_GROUPS[g] || [])[1] || 'This node declares this group. planetai config shows the same keys.')}</p>${g === 'sources' ? '<p class="blurb">A sensor of your own: flash it, plug it in and watch each of its sensors read on <a href="/workbench#test">the workbench</a>.</p>' : ''}${gate}`
    + `<div class="rows">${body}</div>${g === 'system' ? sGrafana(d.bootstrap || []) : ''}${boot}`
    + (changed.length ? `<div class="hist"><div class="k">changed lately</div>${changed.map(a => `<p><span class="mono">${esc(wdhm(a.ts))}</span> · ${esc(a.actor || 'someone')} · ${esc(a.note || '')}</p>`).join('')}</div>` : '');
}

function sScreen(unlocked) {
  return `<h2>This screen</h2><p class="blurb">A token is kept in this browser only and sent only to this node. <code>planetai ui</code> on the node prints both.</p>`
    + `<div class="rows"><div class="srow"><div class="sl"><label>State</label><p class="help">${unlocked ? 'Unlocked with the admin token: it draws everything the node holds and can change any setting.'
      : DOORS_TOKEN() ? 'Holding the token for closing a loop: it can answer the node, and read what it reads, but cannot change a setting.' : `Locked: it reads what SHARE_LEVEL=${esc(D.share || 'off')} gives a screen on this network.`}</p></div>`
    + `<div class="sc"><span class="state">${unlocked ? 'unlocked' : DOORS_TOKEN() ? 'act token' : 'locked'}</span>${DOORS_TOKEN() ? ' <button type="button" class="sbtn" id="slock">Lock</button>' : ''}</div></div></div>`
    + `<form class="unlock2" id="sunlock"><label>Admin token<input type="password" id="stok" autocomplete="off" placeholder="changes settings, reads everything"></label>`
    + `<label>Token for closing a loop<input type="password" id="sact" autocomplete="off" placeholder="answers alerts, changes nothing"></label>`
    + `<div><button type="submit" class="sbtn primary">Unlock this screen</button></div></form>`
    + (unlocked ? `<div class="srow"><div class="sl"><label>A phone</label><p class="help">Scan this with the phone's camera. It opens the phone page `
      + `holding the token for closing a loop, so it can answer the node; it cannot change a setting. Anyone who scans it can answer, so show it to the household only.</p></div>`
      + `<div class="sc" id="sqr"><button type="button" class="sbtn" id="sqrb">Show the code</button></div></div>` : '');
}
/* the phone's unlock, drawn here only: GET /settings/phone answers the admin token, and the code is made in this page */
async function sQR() {
  const tok = (() => { try { return localStorage.getItem('planetai_admin') || ''; } catch (e) { return ''; } })();
  const r = await fetch('/settings/phone', { headers: { authorization: 'Bearer ' + tok } }).then(x => x.json().then(j => (x.ok ? j : { error: j.detail || j.error }))).catch(() => ({ error: 'the node did not answer' }));
  if (!r.act) { sq('#sqr').textContent = r.error || 'no token'; return; }
  if (!window.qrcode) await new Promise((ok, no) => { const s = document.createElement('script'); s.src = '/static/qrcode.js'; s.onload = ok; s.onerror = no; document.head.appendChild(s); });
  const far = /^(localhost|127\.|\[::1\])/.test(location.host) ? '<p class="help">This screen is on the node itself, so the code points at localhost, which a phone cannot reach. Open Set up at the address the phone uses.</p>' : '';
  const q = qrcode(0, 'M'); q.addData(location.origin + '/?layout=mobile#act=' + encodeURIComponent(r.act)); q.make();
  sq('#sqr').innerHTML = q.createSvgTag({ cellSize: 5, margin: 4, scalable: true }).replace('<svg ', '<svg style="width:220px;height:220px;background:#fff" ') + far;
}
async function sUnlock(ev) {
  ev.preventDefault();
  const t = sq('#stok').value.trim(), a = sq('#sact').value.trim();
  try { if (t) localStorage.setItem('planetai_admin', t); if (a) localStorage.setItem('planetai_act', a); } catch (e) { /* none */ }
  const d = await fetch('/settings', { headers: t ? { authorization: 'Bearer ' + t } : {} }).then(r => r.json()).catch(() => null);
  if (t && !(d && d.unlocked)) { try { localStorage.removeItem('planetai_admin'); } catch (e) { /* none */ } return toast2('That admin token is not right.', true); }
  location.reload();   /* every door reads again with the token */
}

/* Storage: the node's own answer (GET /storage, token-only). One bar for the disk, ruled not shaded: what this node
   keeps (solid), what else uses the disk (hatched), what is free (open); then the rows, and how long the free part
   lasts at the last seven days' rate. */
const sBytes = b => b == null ? '—' : b < 1e3 ? `${b} B` : b >= 1e12 ? `${(b / 1e12).toFixed(2)} TB` : b >= 1e9 ? `${(b / 1e9).toFixed(1)} GB` : b >= 1e6 ? `${(b / 1e6).toFixed(0)} MB` : `${Math.round(b / 1e3)} kB`;
const sDays = d => d >= 730 ? `${Math.round(d / 365)} years` : d >= 60 ? `${Math.round(d / 30)} months` : `${d} days`;
/* Machine: the machine under the node (GET /machine), the node on it (GET /health), and its storage (GET /storage).
   All three are the node's answers; the page only lays them out. */
function sMachine() {
  const S = SETUP.storage, M = SETUP.machine, h = D.health;
  if (!S || !M) return `<h2>Machine</h2><p class="gate">What the machine holds is the keeper’s: <a href="#setup/screen" data-go="screen">unlock this screen</a> with the admin token to read it.</p>`;
  const mem = M.memory || {}, used = mem.total_bytes && mem.available_bytes != null ? mem.total_bytes - mem.available_bytes : null;
  const upFor = s => s == null ? '—' : s >= 86400 ? `${Math.floor(s / 86400)} days ${Math.floor(s % 86400 / 3600)} h` : `${Math.floor(s / 3600)} h ${Math.floor(s % 3600 / 60)} min`;
  const meter = (v, T, label) => T ? `<div class="dbar thin" role="img" aria-label="${esc(label)}"><i class="mine" style="width:${Math.min(100, v / T * 100).toFixed(1)}%"></i></div>` : '';
  const load = M.load ? M.load.map(x => x.toFixed(2)).join(' · ') : '—';
  const hot = (M.temperatures || []).map(t => `${esc(t.zone)} ${t.celsius} °C`).join(' · ');
  const machineRows = [
    ['Processor', `${esc(M.arch)} · ${M.cores} core${M.cores === 1 ? '' : 's'} · ${M.cpu_busy_pct == null ? '—' : M.cpu_busy_pct + '% busy now'}`
      + `<small>load ${load} over 1, 5 and 15 minutes, against ${M.cores} cores</small>${meter(M.load ? M.load[0] : 0, M.cores, 'load against cores')}`],
    ['Memory', used == null ? '—' : `${sBytes(used)} used of ${sBytes(mem.total_bytes)} · ${sBytes(mem.available_bytes)} available${mem.swap_total_bytes ? ` · swap ${sBytes(mem.swap_total_bytes - mem.swap_free_bytes)} of ${sBytes(mem.swap_total_bytes)}` : ''}`
      + meter(used || 0, mem.total_bytes, 'memory used')],
    ['Temperature', hot || 'no thermal sensor this system gives the node'],
    ['Up for', `${upFor(M.uptime_s)} since the system started · the node’s app ${upFor(h.uptime_s)}`],
    ['System', `${esc(M.system)} · Python ${esc(M.python)}<small>${esc(M.seen_as)}</small>`],
    ['Database', `${esc(M.database.version)} · up since ${esc(when(M.database.since))} · ${M.database.connections} connections`],
    ['The node', `${esc(h.version)} · ${(h.polls || 0).toLocaleString('en')} polls and ${(h.ingested || 0).toLocaleString('en')} readings since its restart · last poll ${h.last_poll ? hhmm(h.last_poll) : 'none yet'}`
      + (() => { /* /health.errors is each source failing now, by name, with its first line; a source that recovers leaves it */
          const E = h.errors && typeof h.errors === 'object' ? Object.entries(h.errors) : [];
          return E.length ? `<small>${E.length} source${E.length === 1 ? '' : 's'} failing now: ${E.map(([k, v]) => `${esc(k)} (${esc(String(v).slice(0, 90))})`).join('; ')}</small>` : '<small>no source failing now</small>'; })()],
  ].map(([t, v]) => `<div class="srow"><div class="sl"><label>${t}</label></div><div class="sc txt">${v}</div></div>`).join('');
  return `<h2>Machine</h2><p class="blurb">The machine under this node, the node on it, and how long its disk lasts. Every figure is the node’s own answer (GET /machine, /health, /storage).</p>`
    + `<div class="rows">${machineRows}</div><h3 class="sub2">Storage</h3>` + sStorageBody(S);
}
function sStorageBody(S) {
  const k = S.disk || {}, mine = S.database_bytes + S.out_bytes + S.backups.bytes + S.exports_bytes, T = k.total_bytes || 1;
  const pc = v => `${Math.max(0, Math.min(100, v / T * 100)).toFixed(2)}%`;
  const bar = k.total_bytes ? `<div class="dbar" role="img" aria-label="${sBytes(mine)} this node, ${sBytes(k.used_bytes - mine)} other, ${sBytes(k.free_bytes)} free of ${sBytes(k.total_bytes)}">`
    + `<i class="mine" style="width:${pc(mine)}"></i><i class="other" style="width:${pc(k.used_bytes - mine)}"></i></div>`
    + `<div class="dkey"><span><i class="mine"></i>this node ${sBytes(mine)}</span><span><i class="other"></i>everything else ${sBytes(k.used_bytes - mine)}</span><span><i></i>free ${sBytes(k.free_bytes)}</span><span>of ${sBytes(k.total_bytes)}</span></div>` : '';
  const left = S.days_left == null ? 'not known yet: no readings in the last seven days' : `about ${sDays(S.days_left)} at the last seven days’ rate`;
  return `<p class="blurb">Nothing is ever pruned, so the readings are what grows.</p><div class="dhead"><b>${S.days_left == null ? '—' : sDays(S.days_left)}</b><span>before the disk under the node’s files is full, ${S.days_left == null ? 'once there is a rate to go on' : 'at the rate of the last seven days'}</span></div>${bar}<div class="rows">`
    + [['Database', `${sBytes(S.database_bytes)} · ${S.readings.toLocaleString('en')} readings, ${sBytes(S.bytes_per_reading)} each with its indexes`],
       ['Growth', `${sBytes(S.growth_bytes_per_day)} a day · ${S.readings_last_7_days.toLocaleString('en')} readings in the last seven days`],
       ['Backups', `${sBytes(S.backups.bytes)} in ${S.backups.dumps} dump${S.backups.dumps === 1 ? '' : 's'}; about ${sBytes(S.backups.bytes_when_full)} once ${S.backups.keep_days} days are kept (BACKUP_KEEP)`],
       ['Maps and pictures', `${sBytes(S.out_bytes)} in out/: the street map, the satellite and drone tiles, the wind, what packs drew`],
       ['Open exports', `${sBytes(S.exports_bytes)}, CC BY 4.0`],
       ['Room left', `${left}. When it runs short: <code>planetai storage set backups &lt;a dir on another disk&gt;</code> moves the backups, and a larger disk for DATA_DIR moves the database.`],
       ['Which disk', `the disk under ${esc(k.path || 'out/')}, as the node’s container sees it. On Linux the database is on it too unless DATA_DIR moves it; on macOS the database lives in the container engine’s own disk. <code>planetai doctor</code> checks the host’s.`]]
      .map(([t, v]) => `<div class="srow"><div class="sl"><label>${t}</label></div><div class="sc txt">${v}</div></div>`).join('') + `</div>`;
}

/* Grafana (docs/site/grafana.md, Tomas 24 Oct 2026: "I don't see it in the set up menu"): whether it runs, where, and how
   to open it. It listens on the node's own machine unless GRAFANA_BIND opens it, so the way in from a laptop is a tunnel.
   Its keys are read at start; the password is only ever "set" or not (settings.BOOTSTRAP_SECRET). */
function sGrafana(B) {
  const v = k => (B.find(b => b.key === k) || {}).value || '';
  const on = v('COMPOSE_PROFILES').split(',').map(x => x.trim()).includes('grafana');
  const bind = v('GRAFANA_BIND') || '127.0.0.1', port = v('GRAFANA_PORT') || '3000', host = location.hostname || 'the node';
  const loop = bind === '127.0.0.1' || bind === 'localhost', docs = (D.health.docs || 'https://planetai.fab.city/docs/') + 'grafana/';
  const open = !on ? `Off. Turn it on with <code>planetai grafana</code> on the node; <code>planetai grafana off</code> stops it again.`
    : loop ? `On, on the node’s own machine only. From a laptop: <code>ssh -L ${esc(port)}:localhost:${esc(port)} &lt;the node’s machine&gt;</code>, then open <code>http://localhost:${esc(port)}</code>.`
    : `On, open to this network: <a href="http://${esc(host)}:${esc(port)}" target="_blank" rel="noopener">http://${esc(host)}:${esc(port)} ↗</a>`;
  return `<h3 class="sub2" id="grafana">Grafana</h3><p class="blurb">Your own charts over this node’s raw readings, beside this dashboard. It reads everything, room names and private counts included, and none of the dashboard’s rules: a model looks like a measurement unless you tell them apart.</p><div class="rows">`
    + [['State', open],
       ['Address', `<code>${esc(bind)}:${esc(port)}</code>${loop ? '' : ' · <b>every screen on the network can reach the sign-in</b>'}`],
       ['Password', v('GRAFANA_ADMIN_PASSWORD') ? 'set (<code>GRAFANA_ADMIN_PASSWORD</code>)' : `not set: Grafana’s <code>admin</code> login is <code>admin</code>. Set <code>GRAFANA_ADMIN_PASSWORD</code> in <code>.env</code> before you open it to the network.`],
       ['Read more', `<a href="${esc(docs)}" target="_blank" rel="noopener">Grafana: turning it on, what it can read, what it will not tell you ↗</a>`]]
      .map(([t, x]) => `<div class="srow"><div class="sl"><label>${t}</label></div><div class="sc txt">${x}</div></div>`).join('') + `</div>`;
}

function sUpdates() {
  const h = D.health, rel = h.release || {}, docs = h.docs || 'https://planetai.fab.city/docs/';
  /* the release check asks once a day, so its answer ages within the day — "checked 2026-10-08"
     said nothing at 23:00, and a stale "this node has it" read as "cannot update" (node #1). */
  const checkedAgo = iso => {
    const t = Date.parse(iso || '');
    if (!t) return 'not checked yet';
    const m = (Date.now() - t) / 60000;
    return m < 1 ? 'checked just now' : m < 60 ? `checked ${Math.round(m)} min ago`
      : m < 1440 ? `checked ${Math.round(m / 60)} h ago` : `checked ${Math.round(m / 1440)} days ago`;
  };
  return `<h2>Updates</h2><p class="blurb">A release tarball is checked against fabcity’s signature before anything is unpacked. A node run from a git checkout takes no tarball and has no signature to check.</p><div class="rows">`
    + [['Running', `planetai-node ${esc(h.version)} · schema ${esc(h.schema || '')}`], ['Latest release', rel.latest ? `${esc(rel.latest)}${rel.newer ? ' — newer than this node' : ' — this node has it'} · ${checkedAgo(rel.checked)}` : 'not checked yet'],
       ['To update', `<code>planetai update</code> on the node: a backup first, then fetch, check, migrate, rebuild and verify. The readings and the settings stay.`],
       ['Signatures', `<a href="${esc(docs)}install/#signed-installs-and-updates" target="_blank" rel="noopener">How releases are signed and checked ↗</a>`]]
      .map(([t, v]) => `<div class="srow"><div class="sl"><label>${t}</label></div><div class="sc txt">${v}</div></div>`).join('') + `</div>`;
}

/* what the fields say, read the same way when drawn and when saved, so the difference is what somebody changed */
function sPackSwitches() { const all = [...sqa('[data-pack]')]; const on = all.filter(c => c.classList.contains('on')).map(c => c.dataset.pack); return on.length === all.length ? '' : on.join(','); }
function sValues() {
  const out = {};
  sqa('[data-key]').forEach(el => {
    const k = el.dataset.key;
    if (el.type === 'radio') { if (el.checked) out[k] = el.value; }
    else if (el.dataset.bool) out[k] = el.classList.contains('on') ? '1' : '0';
    else if (el.type === 'password') { if (el.value) out[k] = el.value; }
    else out[k] = el.value;
  });
  if (SETUP.group === 'packs' && sPackSwitches() !== SETUP.drawnPacks) out.PACKS_ENABLED = sPackSwitches();
  return out;
}
const sDiff = () => { const now = sValues(), body = {}; for (const k of Object.keys(now)) if (now[k] !== SETUP.loaded[k]) body[k] = now[k]; return body; };
function sCount() {
  const body = sDiff(), keys = Object.keys(body), bar = sq('#sbar'); if (!bar) return;
  const out = keys.filter(k => ((SETUP.desc.runtime || []).find(r => r.key === k) || {}).outward).length;
  bar.hidden = !keys.length; SETUP.dirty = !!keys.length;
  sq('#scount').innerHTML = `${keys.length} change${keys.length === 1 ? '' : 's'}${out ? ` · <b class="out">↗ ${keys.length === 1 ? 'it changes' : `${out} of them change${out === 1 ? 's' : ''}`} what leaves this machine</b>` : ''}`;
}
document.addEventListener('input', ev => { if (ev.target.closest('#setupv2')) sCount(); });
document.addEventListener('change', ev => { if (ev.target.closest('#setupv2')) {
  if (ev.target.name === 'SHARE_LEVEL') sqa('.share .opt').forEach(o => o.classList.toggle('on', o.querySelector('input').checked));
  sCount(); } });
document.addEventListener('click', ev => {
  const sw = ev.target.closest && ev.target.closest('#setupv2 .sw');
  if (sw && !sw.disabled) { sw.classList.toggle('on'); const on = sw.classList.contains('on'); sw.setAttribute('aria-checked', String(on)); sw.firstChild.textContent = on ? 'on' : 'off'; sCount(); }
  const go = ev.target.closest && ev.target.closest('#setupv2 [data-go]');
  if (go) { ev.preventDefault(); SETUP.group = go.dataset.go; setupDraw(); }
});

/* THE CONSEQUENCES STEP (phase 4b, 15 Oct 2026). A change that sends something beyond this machine (the node's
   `outward`) or runs code here that is not the node's (`runs_code`, or a code pack switched on) looked like any other
   switch behind the same save bar. Now the save bar stops and says, in the setting's own help, what will leave or
   what will run, with Back and Save anyway, inside the page. Turning one of them off, or back to private, asks nothing. */
const sOff = v => v === '' || v === '0' || v === 'off' || v === 'private';
function sConsequences(body, desc, packs, drawn) {
  const rows = (desc && desc.runtime) || [], out = [];
  for (const [k, v] of Object.entries(body)) {
    if (k === 'PACKS_ENABLED') {                  /* '' is every pack, so a code pack can switch on by a list going empty */
      const ids = packs.map(p => p.id), was = drawn ? drawn.split(',') : ids, now = v ? v.split(',') : ids;
      for (const p of packs.filter(x => x.kind === 'code' && now.includes(x.id) && !was.includes(x.id)))
        out.push({ key: 'PACKS_ENABLED', label: p.name || p.id, to: 'on', code: true,
          help: `A code pack: its Python (an adapter, hooks or scripts) runs on this machine with the node’s privileges. ${p.description || ''}`.trim() });
      continue;
    }
    const r = rows.find(x => x.key === k) || {};
    if ((r.outward || r.runs_code) && !sOff(v)) out.push({ key: k, label: r.label || k, to: r.secret ? 'a new value' : v, leaves: !!r.outward, code: !!r.runs_code, help: r.help || '' });
  }
  return out;
}
function sConfirm(items) {
  let p = sq('#sconfirm');
  if (!p) { p = document.createElement('div'); p.id = 'sconfirm'; p.className = 'sconfirm'; p.setAttribute('role', 'alertdialog'); p.setAttribute('aria-labelledby', 'sconfirm-h'); $('#setupv2').append(p); }
  const leaves = items.some(i => i.leaves), runs = items.some(i => i.code);
  p.innerHTML = `<h3 id="sconfirm-h">Before this is saved</h3><p>${leaves && runs ? 'This sends something beyond this machine and runs code on it.' : leaves ? 'This sends something beyond this machine.' : 'This runs code on this machine that is not the node’s own.'} `
    + `Here is what each change does, in the node’s own words.</p><ul>${items.map(i => `<li><b>${esc(i.label)}</b><span class="to">→ ${esc(i.to)}</span>`
      + `${i.leaves ? '<span class="why">↗ leaves this machine</span> ' : ''}${i.code ? '<span class="why">runs code here</span>' : ''}<p>${esc(i.help)}</p><code class="fine">${esc(i.key)}</code></li>`).join('')}</ul>`
    + `<div class="acts"><button type="button" class="sbtn" data-a="back">Back</button><button type="button" class="sbtn primary" data-a="save">Save anyway</button></div>`;
  p.hidden = false;
  const close = () => { p.hidden = true; sq('#ssave') && sq('#ssave').focus(); };
  p.querySelector('[data-a=back]').onclick = close;
  p.querySelector('[data-a=save]').onclick = () => { p.hidden = true; sSave(true); };
  p.onkeydown = e => { if (e.key === 'Escape') close(); };
  p.querySelector('[data-a=back]').focus();
}

async function sSave(confirmed) {
  const body = sDiff(), keys = Object.keys(body), auth = DOORS_AUTH();
  sqa('.err').forEach(e => { e.textContent = ''; e.hidden = true; });
  if (!keys.length) return;
  if (confirmed !== true) { const c = sConsequences(body, SETUP.desc, SETUP.packs, SETUP.drawnPacks); if (c.length) return sConfirm(c); }
  /* a key that moved on the node since this page drew it is shown, not overwritten; a second press writes */
  const fresh = await fetch('/settings', { headers: auth }).then(x => x.ok ? x.json() : null).catch(() => null);
  const row = (d, k) => ((d && d.runtime) || []).find(r => r.key === k) || {};
  const moved = fresh && fresh.unlocked ? keys.filter(k => row(SETUP.desc, k).value !== row(fresh, k).value || row(SETUP.desc, k).set !== row(fresh, k).set) : [];
  if (moved.length) {
    for (const k of moved) { const r = row(fresh, k), box = sq('#err-' + k);
      if (box) { box.textContent = `${k} changed on the node after this page drew it. ${r.secret ? (r.set ? 'It is set now.' : 'It is cleared now.') : `It is now “${r.value}”.`} Save again to replace it, or Discard to keep the node’s.`; box.hidden = false; } }
    SETUP.desc = fresh; return toast2(`Nothing was saved: ${moved.join(', ')} changed on the node while this was open.`, true);
  }
  const r = await fetch('/settings', { method: 'PUT', headers: { 'content-type': 'application/json', ...auth, 'X-Agent': 'doors' }, body: JSON.stringify(body) });
  if (r.status === 401) return toast2('That token is not right.', true);
  if (r.status === 403) return toast2('The node has no admin token yet. Run planetai ui on the node.', true);
  if (!r.ok) {
    const said = await r.json().then(j => typeof j.detail === 'string' ? j.detail : '').catch(() => '');
    const which = keys.find(k => said.includes(k)), box = which && sq('#err-' + which);
    if (box) { box.textContent = said; box.hidden = false; const f = sq('#set-' + which); f && f.focus(); return toast2('Nothing was saved. The node said why, next to the setting.', true); }
    return toast2(said || `Could not save (${r.status}).`, true);
  }
  toast2('Saved. Live within about twenty seconds.');
  await setupLoad(); setupDraw();
}
function toast2(msg, bad) {
  let t = document.getElementById('stoast'); if (!t) { t = document.createElement('div'); t.id = 'stoast'; t.setAttribute('role', 'status'); document.body.appendChild(t); }
  t.textContent = msg; t.className = bad ? 'bad' : ''; t.hidden = false; clearTimeout(t._h); t._h = setTimeout(() => { t.hidden = true; }, 5200);
}
