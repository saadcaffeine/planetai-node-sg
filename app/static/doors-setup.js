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
const SETUP = { desc: null, packs: [], group: null, loaded: {}, drawnPacks: '', dirty: false, history: null };
const SETUP_GROUPS = {
  basics: ['Basics', 'This place: what it watches, in order, what kind of node it is, its language and how its page opens. Its name, city, position and time zone are read once at start: change them in .env on the node, then run planetai restart.'],
  sources: ['Sources', 'What the node reads: your sensors, your account, and the public stations and portals around you. Sources that come as packs are switched on and set under Packs.'],
  alerts: ['Alerts', 'Reports at the hours you choose, in this node’s own time zone; between them, only what you asked to be interrupted for; and how a loop is closed.'],
  model: ['Model', 'Which model answers, here and on Telegram alike. The strongest one the node can reach is used, and its keys are under Keys.'],
  packs: ['Packs', 'Which packs load, each with its own settings in its card. Code packs stay off until you allow them; read one before you do.'],
  keys: ['Keys', 'Every secret in one place. Each is masked once saved and never shown again.'],
  sharing: ['Sharing', 'Who may read this node, and everything it sends or announces beyond this machine. Readings stay here; hourly means, Index cells and ρ travel.'],
  system: ['System', 'Tuning numbers, and what is read once at start: the port, extra containers, backups, the poll interval. Change those in .env on the node, then run planetai restart.'],
};
const SETUP_BOOLS = /^(BAD_ENABLED|OPENMETEO_ENABLED|SENSOR_INDOOR|MESH_ALERTS|HA_DISCOVERY|EXPORT_ENABLED|IPFS_PUBLISH|QUIET_HOURS|BAD_INCLUDE_INDOOR|PACKS_ALLOW_CODE)$/;
/* What a screen without the token gets at each level: the node's own rule (app/main.py _SHARE_OFF / _SHARE_OPEN). */
const SHARE_WORDS = {
  off: ['Off', 'A screen on this network without the token gets the page, the node’s name and the daily open export. Nothing else.'],
  open: ['Open', 'Screens on this network read the issues, the stations, the models and the Index. The map, the cells, the hourly table and the household’s notes still need the token.'],
};
const sq = s => document.querySelector('#setupv2 ' + s), sqa = s => document.querySelectorAll('#setupv2 ' + s);
const sTitle = g => (SETUP_GROUPS[g] || [g.charAt(0).toUpperCase() + g.slice(1)])[0];
const sGroups = d => { const seen = []; for (const r of d.runtime || []) if (!seen.includes(r.group)) seen.push(r.group);
  for (const b of d.bootstrap || []) if (b.group && !seen.includes(b.group)) seen.push(b.group); return seen; };
const SECTIONS = () => [...(SETUP.desc ? sGroups(SETUP.desc) : []), 'machine', 'screen', 'updates'];
const sName = g => ({ screen: 'This screen', updates: 'Updates', machine: 'Machine' })[g] || sTitle(g);

VIEWS.setup = async function () {
  if (!SETUP.desc) await setupLoad();
  const want = location.hash.split('/')[1];                 /* #setup/<section> opens at that section */
  if (want && SECTIONS().includes(want) && want !== SETUP.group) { SETUP.group = want; SETUP.dirty = false; }
  setupDraw();
};

async function setupLoad() {
  const tok = (() => { try { return localStorage.getItem('planetai_admin') || ''; } catch (e) { return ''; } })();
  SETUP.desc = await fetch('/settings', { headers: tok ? { authorization: 'Bearer ' + tok } : {} }).then(r => r.json()).catch(() => null);
  SETUP.packs = await fetch('/packs', { headers: DOORS_AUTH() }).then(r => r.ok ? r.json() : []).catch(() => []);
  [SETUP.storage, SETUP.machine] = await Promise.all(['storage', 'machine'].map(r => fetch('/' + r, { headers: DOORS_AUTH() }).then(x => x.ok ? x.json() : null).catch(() => null)));
  SETUP.history = tok ? await fetch('/actions?stage=settings&limit=40', { headers: DOORS_AUTH() }).then(r => r.ok ? r.json() : null).catch(() => null) : null;
  const hash = location.hash.split('/')[1];
  if (hash && SECTIONS().includes(hash)) SETUP.group = hash;
  if (!SETUP.group || !SECTIONS().includes(SETUP.group)) SETUP.group = SETUP.desc && SETUP.desc.unlocked ? (sGroups(SETUP.desc)[0] || 'screen') : 'screen';
}

function setupDraw() {
  const d = SETUP.desc, el = $('#setupv2');
  if (!d) { el.innerHTML = `<p class="fine">GET /settings did not answer this screen.</p>`; return; }
  const unlocked = !!d.unlocked, rows = d.runtime || [], g = SETUP.group;
  const setHere = k => rows.filter(r => r.group === k && r.source === 'gui').length;
  el.innerHTML = `<header class="sh"><div class="k">Set up · ${esc(D.node.name)}</div><h1>How this node was told to behave.</h1>`
    + `<p class="lede">Everything here is live within about twenty seconds; nothing needs a restart. A blank field hands the setting back to <code>.env</code>, and a value set here overrides it.</p></header>`
    + `<div class="sgrid"><nav class="snav" aria-label="Set up sections">${SECTIONS().map(s => `<a href="#setup/${s}" class="${s === g ? 'on' : ''}" data-s="${s}">`
      + `<span>${esc(sName(s))}</span>${s === 'screen' ? `<i>${unlocked ? 'unlocked' : 'locked'}</i>` : s === 'updates' ? (D.health.release || {}).newer ? '<i>new</i>' : '' : s === 'machine' ? (SETUP.storage && SETUP.storage.days_left != null ? `<i>${sDays(SETUP.storage.days_left)}</i>` : '') : setHere(s) ? `<i>${setHere(s)} set</i>` : ''}</a>`).join('')}</nav>`
    + `<section class="spane" aria-live="polite">${g === 'screen' ? sScreen(unlocked) : g === 'updates' ? sUpdates() : g === 'machine' ? sMachine() : sGroup(g, unlocked)}</section></div>`
    + `<div class="sbar" id="sbar" hidden><span id="scount"></span><span class="sp"></span><button type="button" class="sbtn" id="sdiscard">Discard</button><button type="button" class="sbtn primary" id="ssave">Save changes</button></div>`;
  sqa('.snav a').forEach(a => a.onclick = ev => {
    ev.preventDefault();
    if (SETUP.dirty && !confirm('This section has a change you have not saved. Leave it and lose the change?')) return;
    SETUP.group = a.dataset.s; SETUP.dirty = false; history.replaceState(null, '', '#setup/' + a.dataset.s); setupDraw(); window.scrollTo(0, 0);
  });
  SETUP.drawnPacks = sPackSwitches(); SETUP.loaded = sValues(); SETUP.dirty = false; sCount();
  const tokForm = sq('#sunlock'); if (tokForm) tokForm.onsubmit = sUnlock;
  const lockB = sq('#slock'); if (lockB) lockB.onclick = () => { try { localStorage.removeItem('planetai_admin'); localStorage.removeItem('planetai_act'); } catch (e) { /* none */ } location.reload(); };
  sq('#ssave').onclick = sSave; sq('#sdiscard').onclick = () => { SETUP.dirty = false; setupDraw(); };
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
  if (SETUP_BOOLS.test(r.key)) {
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
      return `<section class="pcard"><div class="ph"><button type="button" role="switch" class="sw ${live ? 'on' : ''}" aria-checked="${live}" data-pack="${esc(p.id)}" aria-label="${esc(p.name)}"${unlocked ? '' : ' disabled'}><span>${live ? 'on' : 'off'}</span></button>`
        + `<div><b>${esc(p.name || p.id)}</b><div class="sm">${esc(p.kind || '')}${p.domain ? ` · ${esc(p.domain)}` : ''} · v${esc(p.version || '')} · ${esc(p.author || '')}</div><p class="help">${esc(p.description || '')}</p></div></div>`
        + rows.filter(r => r.pack === p.id).map(r => sRow(r, unlocked)).join('') + `</section>`; }).join('')}</div>` + body;
  }
  const boot = (d.bootstrap || []).filter(b => (b.group || 'system') === g).map(b => `<div class="srow ro"><div class="sl"><label>${esc(b.label)}</label><div class="sm"><code>${esc(b.key)}</code> · read at start</div>`
    + `<p class="help">Edit .env on the node, then run <code>planetai restart</code>.</p></div><div class="sc"><input type="text" readonly value="${esc(b.value || '')}" placeholder="not set"></div></div>`).join('');
  const changed = (SETUP.history || []).filter(a => rows.some(r => String(a.note || '').split(', ').includes(r.key))).slice(0, 5);
  return `<h2>${esc(sTitle(g))}</h2><p class="blurb">${esc((SETUP_GROUPS[g] || [])[1] || 'This node declares this group. planetai config shows the same keys.')}</p>${gate}`
    + `<div class="rows">${body}${boot}</div>`
    + (changed.length ? `<div class="hist"><div class="k">changed lately</div>${changed.map(a => `<p><span class="mono">${esc(wdhm(a.ts))}</span> · ${esc(a.actor || 'someone')} · ${esc(a.note || '')}</p>`).join('')}</div>` : '');
}

function sScreen(unlocked) {
  return `<h2>This screen</h2><p class="blurb">A token is kept in this browser only and sent only to this node. <code>planetai ui</code> on the node prints both.</p>`
    + `<div class="rows"><div class="srow"><div class="sl"><label>State</label><p class="help">${unlocked ? 'Unlocked with the admin token: it draws everything the node holds and can change any setting.'
      : DOORS_TOKEN() ? 'Holding the token for closing a loop: it can answer the node, and read what it reads, but cannot change a setting.' : `Locked: it reads what SHARE_LEVEL=${esc(D.share || 'off')} gives a screen on this network.`}</p></div>`
    + `<div class="sc"><span class="state">${unlocked ? 'unlocked' : DOORS_TOKEN() ? 'act token' : 'locked'}</span>${DOORS_TOKEN() ? ' <button type="button" class="sbtn" id="slock">Lock</button>' : ''}</div></div></div>`
    + `<form class="unlock2" id="sunlock"><label>Admin token<input type="password" id="stok" autocomplete="off" placeholder="changes settings, reads everything"></label>`
    + `<label>Token for closing a loop<input type="password" id="sact" autocomplete="off" placeholder="answers alerts, changes nothing"></label>`
    + `<div><button type="submit" class="sbtn primary">Unlock this screen</button></div></form>`;
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
    ['Database', `${esc(M.database.version)} · up since ${esc((M.database.since || '').slice(0, 16).replace('T', ' '))} · ${M.database.connections} connections`],
    ['The node', `${esc(h.version)} · ${(h.polls || 0).toLocaleString('en')} polls and ${(h.ingested || 0).toLocaleString('en')} readings since its restart · last poll ${esc((h.last_poll || 'none yet').slice(11, 16))} UTC`
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

async function sSave() {
  const body = sDiff(), keys = Object.keys(body), auth = DOORS_AUTH();
  sqa('.err').forEach(e => { e.textContent = ''; e.hidden = true; });
  if (!keys.length) return;
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
