'use strict';
/* PLANETAI node — the five doors (R34–R41 in planetai-design, docs/decisions/2026-10-07-doors.md), over the node's own
   answers (doors-load.js). Served at /doors beside the dashboard while it is tried.
   core: helpers, the one moment (S), the router, the register, Ask the node with Learn inside it. */
const $ = s => document.querySelector(s);
const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const WD = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'], MO = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
/* Every wire time is read in the node's own zone (doorsLocal, doors-load.js): a UTC string and a local one say the same
   hour on the page. `when` is a time as a row of a table says it, 'YYYY-MM-DD HH:MM'. */
const loc = iso => doorsLocal(iso, D && D.tz);
const dayOf = iso => loc(iso).slice(0, 10), hourOf = iso => +loc(iso).slice(11, 13), hhmm = iso => loc(iso).slice(11, 16), when = iso => iso ? loc(iso).replace('T', ' ') : '';
const dLabel = d => { const t = new Date(d + 'T12:00:00Z'); return `${WD[t.getUTCDay()]}, ${t.getUTCDate()} ${MO[t.getUTCMonth()]}`; };
const wdhm = iso => `${dLabel(dayOf(iso)).split(',')[0]} ${hhmm(iso)}`;
const fmt = (v, dp) => v == null || Number.isNaN(+v) ? '—' : (+v).toFixed(dp);
/* a line's name on a drawing (Tomas, 14 Oct: "the WHO line in graphics as reference"): the issue's own value, named the WHO's where its source is the WHO, else "line". The look is .linep */
const lineLab = it => `${/^WHO\b/.test(it.line_source || '') ? 'WHO' : 'line'} ${fmt(it.line, it.dp)}`;
const plain = s => String(s ?? '').replace(/[\p{Extended_Pictographic}\u{FE0F}\u{200D}]/gu, '').replace(/\s+/g, ' ').trim();
/* the node's own Sentinel-2 annual median for a year (GET /earth/frame.png, open) */
const SAT = y => `/earth/frame.png?year=${y}&source=sentinel`;
const km = ([lon1, lat1], [lon2, lat2]) => d3.geoDistance([lon1, lat1], [lon2, lat2]) * 6371;
const css = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();

/* ---- the node's rules, as helpers (docs/site/design.md, tools/check_ui.py) ---- */
const NODE = '/static/';                           // the node's own frozen layer: theme, tokens, signs, learn.json, fonts
// The node's own words are never uppercased (µ uppercases to M): anything the node wrote goes in .said.
const said = x => `<span class="said">${esc(x)}</span>`;
// Where a screen is unlocked: Set up › This screen, as a link wherever a door says it is locked.
const UNLOCK_AT = '<a href="#setup/screen">Set up › This screen</a>';
// A sign from the node's signs.svg; counting signs repeat, never grow, and never draw under --sign-floor (12 px).
const sign = (id, cls = '') => `<svg class="sg ${cls}" aria-hidden="true"><use href="${NODE}signs.svg#${id}"/></svg>`;
// Provenance is ink only and square: the glyph, then one of the five words. Anything else is an absence, not a provenance.
const PROV = ['live', 'partial', 'model', 'cached', 'example'];
const prov = w => PROV.includes(w) ? `<span class="pill">${sign('sign-prov-' + w)}${w}</span>` : `<span class="gap">${esc(w)}</span>`;
// Every numeral carries its comparison: data-num names it, data-cmp says against what (the visual gate reads both).
const ago = m => m < 90 ? `${Math.round(m)} min` : m < 48 * 60 ? `${Math.round(m / 60)} h` : `${Math.round(m / 1440)} days`;   /* an age in minutes, said the way the Node door and Now's declared bands say it */
const num = (key, v, cmp, inner) => `<span data-num="${esc(key)}" data-cmp="${esc(cmp)}">${inner ?? esc(v)}</span>`;
const unitOf = m => (D.metrics[m] || {}).unit || '';
const labelOf = m => (D.metrics[m] || {}).label || m.replace(/_/g, ' ');

/* One clock for the whole page (design.md, Motion): surfaces subscribe; it stops when the tab is hidden or nobody
   is subscribed, and it never starts under reduced motion. Transform and opacity only. */
const CLOCK = { subs: new Map(), raf: 0,
  reduced: () => matchMedia('(prefers-reduced-motion: reduce)').matches,
  on(id, fn) { if (this.reduced()) return false; this.subs.set(id, fn); this.run(); return true; },
  off(id) { this.subs.delete(id); },
  run() { if (this.raf || !this.subs.size || document.hidden) return; const f = t => { this.raf = 0; if (!this.subs.size || document.hidden) return; this.subs.forEach(fn => fn(t)); this.raf = requestAnimationFrame(f); }; this.raf = requestAnimationFrame(f); } };
document.addEventListener('visibilitychange', () => CLOCK.run());

let D, S = { issue: null, i: 0 };
const ISSUES_DRAWN = k => D.issues[k].series && Object.values(D.issues[k].series).some(Boolean);
function val(k, dist, i) { const s = (D.issues[k].series || {})[dist]; return s ? s[i] : null; }
function evAt(k, i) {
  const t = D.buckets[i];
  const h = iso => loc(iso).slice(0, 13), th = h(t);
  return D.events.filter(e => e.issue === k && h(e.opened_at) <= th && (e.cleared_at == null || h(e.cleared_at) >= th));
}
/* an answer in the household's words: which button, who, when, and until when a Not now holds the node's question */
function answerWords(a) {
  if (!a) return { w: 'no answer yet', closed: false };
  const B = D.buttons || {}, said = { acted: B.done || 'Done', acknowledged: B.not_now || 'Not now', dismissed: B.doesnt_fit || 'Doesn’t fit' }[a.stage] || a.stage;
  return { w: `answered: ${said}${a.actor ? ` by ${a.actor}` : ''} at ${hhmm(a.ts)}${a.held_until ? `, asked again at ${hhmm(a.held_until)}` : ''}${a.note ? ` · “${a.note}”` : ''}`, closed: a.stage === 'acted' };
}
/* The last hour's mean of one metric at one sensor, from the raw hourly table. */
/* The last hour's mean of one metric at one sensor, from the raw hourly table (token-only); without it the 15-minute
   mean GET /stats gives every screen at `open`. */
function lastRaw(id, metric) {
  if (!D.raw) return ((D.stats15[id] || {})[metric] || [])[0] ?? null;
  const s = ((D.raw.series[id] || {})[metric]) || []; for (let i = s.length - 1; i >= 0; i--) if (s[i]) return s[i][0]; return null;
}

const DOORS = ['now', 'place', 'node', 'data', 'wall', 'setup'];   /* setup is a page, opened by the gear, not a door in the menu */
/* #data/<sensor-id> opens a door at one thing: the part after the slash is the door's to read */
const view = () => { const d = location.hash.slice(1).split('/')[0]; return DOORS.includes(d) ? d : 'now'; };
const VIEWS = {};
/* the reader's register: what they chose last on this screen, else what their system asks for */
let userTheme = (() => { try { const t = localStorage.getItem('planetai_theme'); if (t === 'light' || t === 'dark') return t; } catch (e) { /* no storage here */ }
  return matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'; })();
document.querySelectorAll('.bar .reg button').forEach(o => o.classList.toggle('on', o.dataset.r === userTheme));
function route() {
  const v = view();
  document.querySelectorAll('.view').forEach(el => { el.hidden = el.dataset.view !== v; });
  document.querySelectorAll('.doors a').forEach(a => a.classList.toggle('on', a.dataset.v === v));
  const gear = $('#gear'); if (v === 'setup') gear.setAttribute('aria-current', 'page'); else gear.removeAttribute('aria-current');   /* Set up is open */
  document.body.dataset.view = v;
  if (v !== 'wall' && typeof flowStop === 'function') { const w = $('#wfield'); w && flowStop(w); }
  if (v !== 'wall' && typeof WALLMAP !== 'undefined' && WALLMAP.stop) WALLMAP.stop();
  // the wall is the keeper's register: dark, always (Decision 15); every other door keeps the reader's choice
  document.documentElement.dataset.theme = v === 'wall' ? 'dark' : userTheme;
  const drawn = VIEWS[v]();
  learnList(); window.scrollTo(0, 0);
  if (drawn && drawn.then) drawn.then(() => learnList());   /* Set up and the Wall draw after they have asked the node */
}

const ASKING = (function () {
  const GL = '0123456789abcdef';
  const N = 560;
  const SPIN = 0.35;
  const SETTLE_MS = 900;
  let settleFor = SETTLE_MS;
  const pts = [];
  for (let i = 0; i < N; i++) {
    const u = Math.random() * 2 - 1, th = Math.random() * Math.PI * 2, r = Math.sqrt(1 - u * u);
    pts.push({ x: r * Math.cos(th), y: u, z: r * Math.sin(th), g: GL[i % 16] });
  }
  const hex = [];
  for (let k = 0; k < 6; k++) { const a = Math.PI / 180 * (60 * k - 30 + 8); hex.push([Math.cos(a), Math.sin(a)]); }

  let box, cv, on = false, t0 = 0, settle0 = 0, spec = null, held = false;
  const reads = [];
  let asking = '';

  const el = id => document.getElementById(id);

  function size() {
    if (!cv) return;
    const r = cv.getBoundingClientRect();
    const dpr = Math.min(2, window.devicePixelRatio || 1);
    cv.width = Math.max(1, Math.round(r.width * dpr));
    cv.height = Math.max(1, Math.round(r.height * dpr));
    cv._dpr = dpr;
  }

  function globe(ctx, W, H, dpr, ang, k, s, every, px) {
    const cx = W / 2, cy = H / 2, R = Math.min(W, H) * 0.36;
    const ink = css('--ink') || '#171717', cells = css('--cells') || '#20388D';
    ctx.beginPath();
    hex.forEach((pp, i) => {
      const x = cx + pp[0] * R * 1.18, y = cy + pp[1] * R * 1.18;
      if (i) ctx.lineTo(x, y); else ctx.moveTo(x, y);
    });
    ctx.closePath();
    ctx.strokeStyle = cells; ctx.lineWidth = (px < 9 ? 1.5 : 2) * dpr; ctx.globalAlpha = 0.9; ctx.stroke();
    ctx.globalAlpha = 1;

    const ca = Math.cos(ang), sa = Math.sin(ang);
    ctx.font = `${(px * dpr).toFixed(0)}px ${css('--mono') || 'ui-monospace, monospace'}`;
    ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
    for (let i = 0; i < N; i += every) {
      const pp = pts[i];
      const x = pp.x * ca + pp.z * sa, z = -pp.x * sa + pp.z * ca;
      const depth = (z + 1) / 2;
      ctx.globalAlpha = Math.min(1, (0.18 + 0.62 * depth) * (0.35 + 0.65 * k) + 0.25 * s);
      ctx.fillStyle = ink;
      ctx.fillText(pp.g, cx + x * R * (1 + 0.02 * k), cy + pp.y * R * (0.92 + 0.08 * k));
    }
    ctx.globalAlpha = 1;
    return { cx, cy, R };
  }

  function draw(now) {
    if (!cv) return;
    const W = cv.width, H = cv.height, dpr = cv._dpr || 1;
    if (!W || !H) return;
    const ctx = cv.getContext('2d');
    const mute = css('--mute') || '#6B6864', ink = css('--ink') || '#171717';
    ctx.clearRect(0, 0, W, H);
    const s = settle0 ? Math.min(1, (now - settle0) / settleFor) : 0;
    const k = 1 - s;
    const ang = (now - t0) / 1000 * SPIN * k;
    const { cx, cy, R } = globe(ctx, W, H - 44 * dpr, dpr, ang, k, s, 1, 9);

    const last = reads.length ? reads[reads.length - 1].path : '';
    const tether = [[asking, -0.55, -0.42, 0], [last, 0.52, 0.38, 1]];
    for (const [name, lx, ly, right] of tether) {
      if (!name || (right && W / dpr < 560)) continue;
      const px = cx + lx * R, py = cy + ly * R;
      const ex = right ? W - 24 * dpr : 24 * dpr, ey = right ? H - 24 * dpr : 24 * dpr;
      ctx.strokeStyle = ink; ctx.lineWidth = 1 * dpr; ctx.globalAlpha = 0.55;
      ctx.beginPath(); ctx.moveTo(ex, ey);
      ctx.lineTo(ex + (right ? -60 : 60) * dpr, ey); ctx.lineTo(px, py); ctx.stroke();
      ctx.globalAlpha = 1; ctx.fillStyle = ink;
      ctx.font = `bold ${(12 * dpr).toFixed(0)}px ${css('--mono') || 'ui-monospace, monospace'}`;
      ctx.textAlign = right ? 'right' : 'left';
      ctx.fillText(name, ex + (right ? -4 : 4) * dpr, ey + (right ? -10 : 10) * dpr);
    }

    ctx.fillStyle = mute; ctx.textAlign = 'left';
    ctx.font = `${(8.5 * dpr).toFixed(0)}px ${css('--mono') || 'ui-monospace, monospace'}`;
    const lines = [`GLYPHS 0-9 A-F · ${N} · ONE GLOBE, ONE CELL`].concat(spec || []);
    lines.forEach((line, i) => ctx.fillText(line, 24 * dpr, H - (16 + 12 * (lines.length - 1 - i)) * dpr));
  }

  function rows() {
    return reads.map(r =>
      `<div class="r"><span class="p">${esc(r.path)}</span>`
      + `<span class="ms">${r.ok ? `${Math.round(r.ms)} ms` : 'no answer'}</span></div>`).join('')
      + (asking ? `<div class="r wait"><span class="p">${esc(asking)}</span>`
        + `<span class="ms">asking…</span></div>` : '');
  }

  function paint() {
    if (!on) return;
    const e = el('ask-ep'); if (e) e.innerHTML = rows();
    const c = el('ask-count');
    if (c) c.textContent = `${reads.filter(r => r.ok).length} answered`;
  }

  return {
    open(why, hold) {
      box = el('asking');
      if (!box || on) return;
      cv = el('askcv');
      if (!cv) {
        cv = document.createElement('canvas');
        cv.id = 'askcv';
        (box.querySelector('.frame') || box).appendChild(cv);
      }
      on = true; reads.length = 0; asking = ''; settle0 = 0; spec = null;
      const seed = box.querySelector('.seed'); if (seed) seed.remove();   /* the globe takes the middle from here */
      settleFor = SETTLE_MS; held = !!hold;
      t0 = performance.now();
      box.classList.add('on'); box.setAttribute('aria-hidden', 'false');
      const w = el('ask-what'); if (w) w.textContent = why || 'Asking the node';
      const b = el('ask-big'); if (b) { b.textContent = '----'; b.className = 'big'; }
      const m = el('ask-meters'); if (m) m.innerHTML = '';
      const r = el('ask-rule');
      if (r) {
        r.textContent = 'Finding this place. The characters settle into the address of the node’s own area '
          + 'once it answers. Nothing here is a reading yet.';
      }
      size();
      window.addEventListener('resize', size);
      CLOCK.on('asking-globe', draw);
      paint();
    },
    saw(path, ms, ok) {
      if (!on) return;
      reads.push({ path, ms, ok });
      if (asking === path) asking = '';
      paint();
    },
    flight(path) { if (on) { asking = path; paint(); } },
    placed(health) {
      if (!on || !health) return;
      const c = health.cell || {};
      const area = c.edge_m ? Math.round(2.59807621 * c.edge_m * c.edge_m).toLocaleString('en-GB') : null;
      spec = [
        `RES ${c.res == null ? '?' : c.res} · EDGE ${c.edge_m == null ? '?' : `${c.edge_m} M`}`
          + `${area ? ` · ${area} M²` : ''}`,
        'RAW READINGS STAY HOME',
      ];
    },
    landed(issues) {
      if (!on || !issues) return;
      settle0 = performance.now();
      const floor = held ? 1200 : 0;
      settleFor = Math.max(SETTLE_MS, floor - (settle0 - t0));
      const hk = issues.headline, d = (issues.issues || {})[hk] || {};
      const room = ((d.stack || {}).room || {}).value;
      const b = el('ask-big');
      if (b && room != null) {
        b.innerHTML = `${esc(fmt(room, d.dp))}<small>${esc(d.unit || '')}</small>`;
      }
    },
    close() {
      if (!on) return;
      const floor = held ? 1200 : 0;
      const left = floor - (performance.now() - t0);
      if (left > 0) { held = false; setTimeout(() => this.close(), left); return; }
      on = false;
      CLOCK.off('asking-globe');
      window.removeEventListener('resize', size);
      if (box) { box.classList.remove('on'); box.setAttribute('aria-hidden', 'true'); }
      if (cv && cv.parentNode) cv.parentNode.removeChild(cv);
      cv = null;
    }
  };
}());
window.PAI_ASKING = ASKING;

ASKING.open('Asking the node', true);
Promise.all([loadD(), fetch(NODE + 'learn.json').then(r => r.json()).catch(() => ({ marks: {} }))]).then(async ([d, l]) => {
  D = d; D.learn = l.marks;
  D.dates = [...new Set(D.buckets.map(dayOf))];
  D.at = {}; D.buckets.forEach((b, i) => { D.at[dayOf(b) + '|' + hourOf(b)] = i; });
  /* Now opens on the lead when it is drawn by the hour; Land and Coast change yearly and live on Place (15 Oct) */
  S.issue = D.lead && ISSUES_DRAWN(D.lead) ? D.lead : D.order.find(ISSUES_DRAWN) || D.lead; S.i = D.buckets.length - 1; D.now = S.i;
  D.sens = Object.fromEntries(D.sensors.map(s => [s.sensor_id, s]));
  /* the cells and distances the flow, the Wall and Node draw are the node's answers (js/nodegeo.js) */
  await knownNodes(D); foot();
  if (D.askOff) $('#askbtn').hidden = true;                 /* UI_ASK off: no ask here either */
  $('#who').innerHTML = `${esc(D.node.name)}<small>${esc(D.node.place || '')}</small>`;
  $('#asof').textContent = `${new URLSearchParams(location.search).get('fixture') ? 'CAPTURE' : 'LIVE'} · as of ${hhmm(D.as_of)}${DOORS_TOKEN() ? '' : ' · locked'}`;   /* the version is in the footer (audit, 15 Oct) */
  const rel = D.health.release || {};                        /* a newer release: one small line in the bar, to Set up › Updates */
  $('#relnote').hidden = !rel.newer; $('#relnote').textContent = rel.newer ? `${rel.latest} is out` : '';
  try { D.ngeo = await nodeGeo(D); } catch (e) { D.ngeo = null; D.ngeoErr = e.message; }
  route();
  ASKING.close();
  window.addEventListener('hashchange', route);
  let t; window.addEventListener('resize', () => { clearTimeout(t); t = setTimeout(() => VIEWS[view()](), 120); });
}).catch(e => { ASKING.close(); refused(e); });

/* At SHARE_LEVEL=off a screen without the token is refused /issues, and the doors have nothing to draw. That is a real
   state a phone on the house's WiFi will be in, not an error: draw the node's name (/health answers at every level),
   the node's own sentence, and the one way in, the token. Without this the page stayed blank and could not be unlocked. */
async function refused(e) {
  const [h, r] = await Promise.all([fetch('/health').then(x => x.json()).catch(() => ({})),
    doorsFetch('/issues').then(async x => x.ok ? null : (await x.json().catch(() => ({}))).error || (await x.text().catch(() => ''))).catch(() => null)]);
  $('#who').innerHTML = `${esc(h.node || 'this node')}<small>${esc(h.city || '')}</small>`;
  $('#asof').textContent = 'locked';
  document.querySelectorAll('.view').forEach(el => { el.hidden = el.dataset.view !== 'setup'; });
  /* a Wall is a screen nobody operates: one line it can be read by from across the room, never a token form (audit, 15 Oct) */
  if (/^#wall/.test(location.hash)) {
    $('#setupv2').innerHTML = `<header class="sh"><h1>This screen needs sharing turned on.</h1><p class="lede">Whoever set up ${esc(h.node || 'this node')} can turn it on in Set up › Sharing. Then this screen shows the house by itself.</p></header>`;
    return;
  }
  $('#setupv2').innerHTML = `<header class="sh"><div class="k">${esc(h.node || 'this node')} · not sharing with this screen</div><h1>This node is not sharing its readings with this screen.</h1>`
    + `<p class="lede">${esc(r || e.message)}</p><p class="lede">Unlock this screen with a token, or ask whoever set this node up to turn sharing on (Set up → Sharing). <code>planetai ui</code> on the node prints the tokens.</p></header>`
    + `<form class="unlock2" id="sunlock"><label>Admin token<input type="password" id="stok" autocomplete="off" placeholder="changes settings, reads everything"></label>`
    + `<label>Token for closing a loop<input type="password" id="sact" autocomplete="off" placeholder="answers alerts, changes nothing"></label>`
    + `<div><button type="submit" class="sbtn primary">Unlock this screen</button></div></form>`;
  $('#sunlock').onsubmit = ev => { ev.preventDefault(); const t1 = $('#stok').value.trim(), t2 = $('#sact').value.trim();
    try { if (t1) localStorage.setItem('planetai_admin', t1); if (t2) localStorage.setItem('planetai_act', t2); } catch (x) { /* no storage here */ } location.reload(); };
}

document.querySelectorAll('.bar .reg button').forEach(b => b.onclick = () => {
  userTheme = b.dataset.r; try { localStorage.setItem('planetai_theme', userTheme); } catch (e) { /* no storage here */ }
  document.querySelectorAll('.bar .reg button').forEach(o => o.classList.toggle('on', o === b)); route(); });

/* ---------- Ask the node, and Learn inside it ----------
   Learn is the node's own learn mode (app/static/learn.json): every part names a mark, and the list says what the
   docs say about it, which routes the part reads, which pack drew it and which stage of the loop it belongs to.
   The questions offered are the marks' own. */
/* The docs' markdown, inline only: a quote is a cut of a page, so its backticks, bold and links arrive as written */
const quoted = q => esc(String(q).replace(/\s*\n\s*/g, ' ')).replace(/\[([^\]]+)\]\([^)]+\)/g, '$1')
  .replace(/`([^`]+)`/g, '<code>$1</code>').replace(/\*\*([^*]+)\*\*/g, '<b>$1</b>');
function learnList() {
  const v = view(), on = $('#learn').checked, pane = document.querySelector(`.view[data-view="${v}"]`);
  /* the parts a person can see, in the order they see them: the bar, the door's own parts, the foot. A tab, a view or
     a block the node has not filled yet is hidden, and is not a part of what is on the screen. */
  const shown = el => el.getClientRects().length > 0;
  const mine = pane ? [...pane.querySelectorAll('[data-learn]')].filter(shown) : [];
  const parts = [$('.bar'), ...mine, $('#foot')].filter(el => el && el.dataset.learn && shown(el));
  document.body.classList.toggle('learn', on);
  parts.forEach((el, n) => el.dataset.n = n + 1);
  $('#learnlist').innerHTML = on ? parts.map((el, n) => {
    const m = D.learn[el.dataset.learn] || {}, reads = (el.dataset.reads || '').split(' ').filter(Boolean);
    return `<li data-learn-item="${esc(el.dataset.learn)}"><i>${n + 1}</i><div><p><b>${esc(m.title || el.dataset.learn)}</b>${el.dataset.stage ? ` <span class="k">${esc(el.dataset.stage)}</span>` : ''}</p>`
      + (m.quote ? `<blockquote>${quoted(m.quote)}</blockquote>` : '') + (m.more ? `<p class="lm">${esc(plain(m.more))}</p>` : '')
      + `<span class="reads">${reads.map(r => `<code>GET ${esc(r)}</code>`).join(' ')}${el.dataset.pack ? ` <code>${esc(el.dataset.pack)}</code>` : ''}`
      + `${m.url ? `${reads.length || el.dataset.pack ? ' · ' : ''}<a href="${esc(m.url)}" target="_blank" rel="noopener">From ${esc(m.page_title || m.page)}${m.section ? ` · ${esc(plain(m.section).replace(/`/g, ''))}` : ''}</a>` : ''}</span></div></li>`;
  }).join('') : '';
  tryQs(on ? mine : []);
}
/* A door fills some parts after it is drawn (Did it work, a Data tab, Place's views): while learn is on, a part that
   appears or goes is counted again */
const LEARN_SEEN = new MutationObserver(() => { if ($('#learn').checked) { clearTimeout(LEARN_SEEN.t); LEARN_SEEN.t = setTimeout(learnList, 120); } });
document.querySelectorAll('.view').forEach(el => LEARN_SEEN.observe(el, { subtree: true, attributes: true, attributeFilter: ['hidden', 'data-pview', 'data-learn'] }));
/* The questions offered: with learn on, the marks' own for this door first; then the node's pool, written from
   tonight's figures, three at a time and turning after each answer so the same three never stand there all day.
   A press asks it. */
let TURN = 0;
const ASKED = new Set();
function tryQs(parts) {
  const L = (D.health || {}).locale || 'en';
  const mine = [...new Set(parts.flatMap(el => { const q = (D.learn[el.dataset.learn] || {}).questions || {}; return q[L] || q.en || []; }))].slice(0, 2);
  const pool = (D.prompts || []).filter(q => !ASKED.has(q) && !mine.includes(q)), r = pool.length ? TURN % pool.length : 0;
  const qs = [...mine, ...pool.slice(r), ...pool.slice(0, r)].slice(0, 3);
  $('#try').innerHTML = qs.map(q => `<button type="button">${esc(q)}</button>`).join('');
  document.querySelectorAll('#try button').forEach(b => b.onclick = () => { $('#q').value = b.textContent; $('#qform').requestSubmit(); });
}
/* Enter asks, Shift+Enter starts a new line, as in every chat box; a composition in progress (an IME) is left alone */
$('#q').addEventListener('keydown', ev => {
  if (ev.key === 'Enter' && !ev.shiftKey && !ev.isComposing && ev.keyCode !== 229) {   /* 229: Safari's IME commit */ ev.preventDefault(); $('#qform').requestSubmit(); }
});
$('#askbtn').onclick = () => { const open = $('#askpane').hidden; $('#askpane').hidden = !open; $('#askbtn').setAttribute('aria-expanded', String(open)); if (open) { learnList(); askMode(); $('#q').focus(); } };
$('#askclose').onclick = () => { $('#askpane').hidden = true; $('#askbtn').setAttribute('aria-expanded', 'false'); $('#learn').checked = false; learnList(); };
$('#learn').onchange = learnList;
/* the token is set and cleared on Set up → This screen (doors-setup.js), kept where the dashboard keeps it */
/* POST /ask, the node's own: it streams `event: token` blocks; only the words are drawn here, the dashboard's ask pane
   keeps the ledger of what it read. One question at a time, no thread. */
/* Which way the box answers: a model the node has set up, or, with none, the documentation itself, searched by the
   question's words (GET /docs/search). Asked once per page, when the pane first opens. */
let MODE = null;
async function askMode() {
  if (MODE) return;
  const r = await fetch('/ask/status', { headers: DOORS_AUTH() }).catch(() => null);
  MODE = r && r.ok ? 'model' : 'docs';
  $('#amode').textContent = MODE === 'model' ? 'Answers from the model set up for this node' : 'No model is set up here, so the box searches these docs';
  $('#q').placeholder = MODE === 'model' ? 'Ask about this place, its readings, or this page' : 'Search the docs: how do I add a sensor?';
}
/* The docs' answer: the sections that hold most of the question's words, each a link to the page it is from. */
async function docsHits(q, n) {
  const r = await fetch('/docs/search?q=' + encodeURIComponent(q.slice(0, 200)), { headers: DOORS_AUTH() }).catch(() => null);
  return r && r.ok ? (await r.json()).slice(0, n) : null;
}
function hitsHtml(hits) {
  const base = (D.health || {}).docs || 'https://planetai.fab.city/docs/';
  return `<ol class="hits">${hits.map(h => `<li><a href="${esc(base + String(h.page || '').replace(/\.md$/, '/') + (h.anchor ? '#' + h.anchor : ''))}" target="_blank" rel="noopener">${esc(h.title || h.page)}</a><p>${esc(h.snippet)}…</p></li>`).join('')}</ol>`;
}
async function docsAnswer(q, why, out) {
  const hits = await docsHits(q, 5);
  if (!hits) { out.textContent = WORDS.noreply; return; }
  out.innerHTML = (why ? `<p class="fine">${esc(why)}</p>` : '') + (hits.length ? hitsHtml(hits)
    : '<p>Nothing in the docs holds those words. Try other ones; the docs are in English.</p>');
}
/* Under a model's answer, the three sections of the docs that hold most of the question's words. */
async function docsAfter(q, out) {
  const hits = await docsHits(q, 3);
  if (hits && hits.length) out.insertAdjacentHTML('beforeend', `<p class="amode">In the docs</p>${hitsHtml(hits)}`);
}
/* One exchange in the thread: the question as the person's own line, the answer under it, the view kept at the newest.
   What is shown stays in this tab; only the new question is ever sent. */
function exchange(q) {
  const th = $('#thread'), hello = $('#athello');
  if (hello) hello.remove();
  th.insertAdjacentHTML('beforeend', `<div class="msg me">${esc(q)}</div><div class="msg node answer said">…</div>`);
  const out = th.lastElementChild, sc = $('#ascroll');
  sc.scrollTop = sc.scrollHeight;
  return out;
}
$('#qform').onsubmit = async ev => {
  ev.preventDefault();
  const q = $('#q').value.trim(); if (!q || $('#qsend').disabled) return;
  const out = exchange(q); $('#q').value = ''; $('#qsend').disabled = true;
  try {
    await askMode();
    if (MODE === 'docs') { await docsAnswer(q, '', out); ASKED.add(q); TURN += 3; return; }
    const r = await fetch('/ask', { method: 'POST', headers: { 'content-type': 'application/json', ...DOORS_AUTH() },
      body: JSON.stringify({ messages: [{ role: 'user', content: q }], view: view(), mode: 'advanced', focus: null }) });
    if (!r.ok || !r.body) throw new Error((await r.json().catch(() => ({}))).detail || `the node answered ${r.status}`);
    const rd = r.body.getReader(), dec = new TextDecoder(); let buf = '', text = '';
    for (;;) {
      const { value, done } = await rd.read(); if (done) break;
      buf += dec.decode(value, { stream: true }); let cut;
      while ((cut = buf.indexOf('\n\n')) >= 0) {
        const block = buf.slice(0, cut); buf = buf.slice(cut + 2);
        const ev = (block.match(/^event: (.+)$/m) || [])[1], data = JSON.parse((block.match(/^data: (.+)$/m) || [])[1] || '{}');
        if (ev === 'token') { text += data.text; out.textContent = text; }
        else if (ev === 'retry') { text = ''; }
        else if (ev === 'error') throw new Error(data.message);
      }
    }
    if (!text) throw new Error('empty');
    out.innerHTML = `<p>${esc(text)}</p>`;
    if (!(D.prompts || []).includes(q)) await docsAfter(q, out);   /* the node's own questions are about tonight's readings, not the docs */
    ASKED.add(q); TURN += 3;
  } catch (e) { await docsAnswer(q, 'The model did not answer, so here is what the docs say.', out); }
  finally { $('#qsend').disabled = false; learnList(); const sc = $('#ascroll'); sc.scrollTop = sc.scrollHeight; $('#q').focus(); }
};

/* The foot of every door but the Wall: what this is, where its words are, and who it belongs to. The links are the
   node's own (/health.docs, /llms.txt) and the programme's; the classic dashboard stays one press away while the
   doors are tried. */
function foot() {
  const h = D.health, docs = h.docs || 'https://planetai.fab.city/docs/', rel = h.release || {};
  $('#foot').innerHTML = `<div><b>This node</b><p>A home monitor for air, heat, sea and land, part of Fab City’s PLANETAI.</p><p>${esc(D.node.name)}${D.node.place ? ` · ${esc(D.node.place)}` : ''} · planetai-node ${esc(h.version || '')}</p>`
    + `<p>${rel.newer ? `${esc(rel.latest)} is out: <code>planetai update</code> on the node.` : 'A node of PLANETAI, the Fab City programme’s network of homes that read their place, decide and act.'}</p></div>`
    + `<div><b>Read</b><a href="${esc(docs)}" target="_blank" rel="noopener">Documentation</a><a href="${esc(docs)}dashboard/" target="_blank" rel="noopener">These pages, explained</a>`
    + `<a href="${esc(h.llms || '/llms.txt')}">For agents: llms.txt</a>${D.askOff ? '' : '<button class="linkish" type="button" id="footask">Ask the node</button>'}</div>`
    + `<div><b>This house</b><a href="#setup">Set up</a><a href="#setup/screen">Unlock this screen</a><a href="/export?day=${esc(dayOf(D.as_of))}">Today’s open data, CC BY 4.0</a></div>`
    + `<div><b>Fab City</b><a href="https://planetai.fab.city/" target="_blank" rel="noopener">PLANETAI</a><a href="https://fab.city/" target="_blank" rel="noopener">Fab City</a>`
    + `<a href="https://github.com/fabcity/planetai-node" target="_blank" rel="noopener">Source, Apache-2.0</a></div>`;
  if (!D.askOff) $('#footask').onclick = () => $('#askbtn').click();
}
