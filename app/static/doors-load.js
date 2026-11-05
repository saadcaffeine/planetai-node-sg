'use strict';
/* DOORS, the loader. The five doors (docs/decisions/2026-10-07-doors.md) draw from one object, D, and this builds it
   from the node's own answers: the routes are read as they are, and buildD() only renames and pivots. It computes
   nothing a route did not say. A route that refuses this screen (403: a token-only route at this SHARE_LEVEL)
   leaves its part null, and the door that draws it says what it is not drawing and why.
   buildD() is pure, so tests/test_doors.py runs it on node #1's capture (fixtures/node1-2026-10-06-figures.json). */

/* the same token every page of this node carries (dashboard.js, auth_), read from the same two keys */
const DOORS_TOKEN = () => { try { return localStorage.getItem('planetai_admin') || localStorage.getItem('planetai_act') || ''; } catch (e) { return ''; } };
const DOORS_AUTH = () => (DOORS_TOKEN() ? { authorization: 'Bearer ' + DOORS_TOKEN() } : {});
if (typeof window !== 'undefined') window.PAI_AUTH = DOORS_AUTH;
/* The routes no SHARE_LEVEL opens to a screen without a token (main._SHARE_OPEN), and /alerts, whose texts name the
   rooms and which /issues' asks stand in for. Asked without a token they are a 403 every time: noise in the node's log
   and the console, and nothing drawn. So a screen holding no token at all does not ask; it gets a stand-in 403 and
   each caller draws what it draws locked. With any token the page asks as before, and the node decides. */
const DOORS_LOCKED = /^\/?(health\/sources|aggregates|actions|alerts|geo\/(planet|measure|rings|grid)|things|learned(?!\/place)|captures|species|household|machine|storage|place\/geojson)\b/;
const doorsFetch = (p, init = {}) => !DOORS_TOKEN() && DOORS_LOCKED.test(p) ? Promise.resolve(new Response('{}', { status: 403 }))
  : fetch(p, { ...init, headers: { ...DOORS_AUTH(), ...(init.headers || {}) } });
/* A wire time in the node's own zone (/health tz) as 'YYYY-MM-DDTHH:MM'. /health and /issues' as_of are written in
   UTC, the hourly buckets in the node's offset; slicing the string printed both as local, and node #1 showed "as of
   11:52" beside "at 19:00" (14 Oct). A string with no offset, or no zone yet, keeps its own clock. */
const DOORS_TZF = {};
function doorsLocal(iso, tz) {
  const s = String(iso ?? '');
  if (!tz || !/(Z|[+-]\d\d:?\d\d)$/.test(s) || Number.isNaN(Date.parse(s))) return s.slice(0, 16);
  const f = DOORS_TZF[tz] ||= new Intl.DateTimeFormat('en-CA', { timeZone: tz, year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hourCycle: 'h23' });
  const p = Object.fromEntries(f.formatToParts(new Date(s)).map(x => [x.type, x.value]));
  return `${p.year}-${p.month}-${p.day}T${p.hour}:${p.minute}`;
}

const DOORS_ROUTES = {
  issues: 'issues', days: 'issues/days?days=7', health: 'health', rho: 'rho', earth: 'earth', reach: 'reach',
  sensors: 'sensors', observations: 'observations', cells: 'cells', stats: 'stats', settings: 'settings',
  /* token-only (doorsFetch): a screen without the token gets null and says so */
  readings_1h: 'aggregates?hours=24', actions: 'actions?limit=2000', alerts: 'alerts?limit=500',
};

function buildD(A, locale) {
  const I = A.issues, Y = A.days || {}, H = A.health || {};
  const L = (I.labels || {})[locale] ? locale : 'en';
  const tr = x => x == null ? null : typeof x === 'string' ? x : (x[L] ?? x.en ?? null);
  const issues = {};
  for (const [k, it] of Object.entries(I.issues || {})) {
    const y = (Y.issues || {})[k] || {}, hero = it.hero || {};
    issues[k] = {
      name: tr(it.name), state: it.state, unit: it.unit, dp: it.dp, metric: it.metric,
      line: (it.line || {}).value ?? null, line_source: (it.line || {}).source ?? null,
      sentence: tr(hero.sentence || it.sentence), plain: tr(hero.plain), pix: hero.pictogram || null,
      title: tr(it.title), tagline: tr(it.tagline), hours: tr(y.hours),
      reason_text: tr(it.reason_text), open_asks: it.open_asks || [],
      /* what is asked of the house now (engine _asking): Now's Decide card, the Wall and the phone read this, and only this */
      asking: (it.asking || []).map(a => ({ ...a, says: tr(a.says), how: tr(a.how) })),
      usual: (it.usual || {}).hours ? it.usual.hours.map(h => [h.median, h.p90]) : null,
      stack: Object.fromEntries(Object.entries(it.stack || {}).map(([d, s]) => [d, s && { value: s.value, provenance: s.provenance, source: s.source }])),
      hero_distance: y.distance ?? null, series: y.series || null, per_day: y.per_day || [], provenance: y.provenance || {},
    };
  }
  /* an alert's text, and what the household said to it, by id. /alerts and /actions are token-only; without the
     token /issues' own `asks` carries the same acts and stages, without the household's notes (engine.py drops them). */
  const asks = I.asks || {}, alertById = new Map((A.alerts || asks.acts || []).map(a => [a.id, a]));
  const actions = (A.actions || asks.actions || []).map(x => {
    const a = alertById.get(x.alert_id) || {};
    return { ...x, rule: a.rule_id ?? null, level: a.level ?? null, text: a.text ?? null };
  });
  const evs = I.events || {}, full = new Map([...(evs.open || []), ...(evs.recent || [])].map(e => [e.id, e]));
  const events = (Y.events || []).map(e => {
    const f = full.get(e.id) || {};
    return { ...e, action: (f.action || {}).text ?? null, peak: f.peak ?? null, rooms: f.rooms || [], answer: f.answer ?? null, asking: f.asking ?? !f.answer,
             last_seen_at: f.last_seen_at ?? null, message: f.message ?? null };   /* the phone's card reads both (SPEC_mobile §6) */
  });
  /* the hourly table, pivoted: series[sensor][metric][i] = [mean, min, max] */
  let raw = null;
  if (A.readings_1h) {
    /* forecast rows are timestamped up to 48 h ahead: the table read here stops at the hour /issues was computed */
    const upTo = Date.parse(I.as_of), rows = A.readings_1h.filter(r => Date.parse(r.bucket) <= upTo);
    const buckets = [...new Set(rows.map(r => r.bucket))].sort().slice(-24), at = new Map(buckets.map((b, i) => [b, i])), series = {};
    for (const r of rows) {
      if (!at.has(r.bucket)) continue;
      const m = ((series[r.sensor_id] ||= {})[r.metric] ||= buckets.map(() => null));
      m[at.get(r.bucket)] = [r.mean, r.min, r.max];
    }
    raw = { buckets, series, n: rows.filter(r => at.has(r.bucket)) };
  }
  const stats15 = {};
  for (const s of A.stats || []) (stats15[s.sensor_id] ||= {})[s.metric] = [s.mean_15m, s.silent_minutes];
  const E = A.earth || {}, G = I.geometry || {}, img = E.imagery || {};
  /* /settings is describe(): rows, never a flat map */
  const setting = k => { const r = ((A.settings || {}).runtime || []).find(x => x.key === k) || {}; return r.value || r.default || null; };
  return {
    /* locale is the node's own, for a pack's words (drawAsks); the issues' words fall back to en through L */
    as_of: I.as_of, tz: H.tz, locale, buckets: Y.buckets || [], order: I.order || [], lead: (I.lead || {}).issue ?? (I.order || [])[0],
    labels: (I.labels || {})[L] || {}, metrics: I.metrics || {}, issues, events, buttons: evs.buttons || {}, sent24: evs.sent_24h ?? null,
    node: { name: H.node, place: H.city }, registry: { name: H.node, place: H.city || H.node },
    share: setting('SHARE_LEVEL'), settings: A.settings || null, askOff: setting('UI_ASK') === 'off',   /* the keeper's switch for every ask, the dashboard's and the doors' */ rho: A.rho || {}, health: H,
    earth: A.earth ? { years: E.years || [], changes: E.changes || [], radius_m: E.radius_m, change: E.latest || null,
      sentinel: img.sentinel || [], landsat: img.landsat || [], credit: img.credit || [] } : null,
    reach: A.reach || [], sensors: A.sensors || [], observations: A.observations || [], index_cells: A.cells || [],
    geometry: { ladder: G.ladder || [], radio: G.radio || {}, grain: G.grain_table || [], publication: G.publication || {} },
    point: [H.lon, H.lat], stats15, raw, actions, alerts: A.alerts || asks.acts || [], notes: !!A.actions, asks,
    /* the ask pane's questions, written by the node from tonight's figures (/issues digest.prompts) */
    prompts: ((I.digest || {}).prompts || {})[L] || ((I.digest || {}).prompts || {}).en || [],
    /* the bands a pack declares in its pack.yaml, with the node's numbers in them (docs/PACKS.md, A declared section) */
    sections: (I.sections || []).map(x => ({ ...x, title: tr(x.title), note: tr(x.note),
      readouts: (x.readouts || []).map(r => ({ ...r, label: tr(r.label) })) })),
  };
}

/* Every route at once. A 403 is this screen's SHARE_LEVEL speaking, not an error: the part stays null.
   The phone page passes its own subset (SPEC_mobile §8) and never asks for the token-only three. */
async function loadD(routes = DOORS_ROUTES) {
  const get = async p => {
    const t0 = (typeof performance !== 'undefined') ? performance.now() : Date.now();
    if (typeof ASKING !== 'undefined') ASKING.flight('/' + p);
    try {
      const r = await doorsFetch('/' + p);
      const ms = ((typeof performance !== 'undefined') ? performance.now() : Date.now()) - t0;
      if (typeof ASKING !== 'undefined') ASKING.saw('/' + p, ms, r.ok);
      if (!r.ok) return null;
      const data = await r.json();
      if (typeof ASKING !== 'undefined') {
        if (p === 'health') ASKING.placed(data);
        if (p === 'issues') ASKING.landed(data);
      }
      return data;
    } catch (e) {
      if (typeof ASKING !== 'undefined') ASKING.saw('/' + p, ((typeof performance !== 'undefined') ? performance.now() : Date.now()) - t0, false);
      return null;
    }
  };
  const FIX = (typeof location !== 'undefined') ? new URLSearchParams(location.search).get('fixture') : null;
  let A;
  if (FIX) {     /* a capture replayed: the bundle holds every route's answer under the route's own name */
    A = await get('issues/fixtures/' + encodeURIComponent(FIX)) || {};
    A.days = A.issues_days; A.settings = await get('settings');
    /* the capture holds token-only answers too; a screen without the token is shown what a node would show it */
    if (!DOORS_TOKEN()) for (const k of ['readings_1h', 'actions', 'alerts']) delete A[k];
  } else {
    const keys = Object.keys(routes), got = await Promise.all(keys.map(k => get(routes[k])));
    A = Object.fromEntries(keys.map((k, i) => [k, got[i]]));
  }
  if (!A.issues) throw new Error('GET /issues did not answer this screen: the doors have nothing to draw');
  return buildD(A, (A.health || {}).locale || 'en');
}

/* GET /forecast for Now's Next days (docs/SPEC_next_days.md §4), asked when Now is drawn and kept 30 minutes there
   (doors-now.js), never with the routes above. The node's answer; { off: true } when the forecast pack is off (the route is not there, 404);
   { locked: true } when this screen may not read it (401, 403); null when the node did not answer. */
const loadForecast = () => doorsFetch('/forecast?hours=72')
  .then(r => r.status === 404 ? { off: true } : r.status === 401 || r.status === 403 ? { locked: true } : r.ok ? r.json() : null).catch(() => null);

/* The household's words for the engine's own (pre-launch audit, 15 Oct): a state, an event's kind, and the two
   sentences a screen says when it cannot answer. One table for the doors and the phone, which both load this file. */
const WORDS = {
  state: { act: 'act now', notable: 'worth a look', quiet: 'fine', context: 'background', none: 'not read' },
  kind: { spike: 'a sudden rise', unusual: 'higher than usual for this hour', sustained: 'high for an hour', danger: 'dangerous' },
  locked: 'This screen can’t answer yet. Ask whoever set up the node to unlock it, or answer on Telegram.',
  noreply: 'The node did not answer. Check this screen is on the home network, then try again.',
};
const stateWord = s => WORDS.state[s] || s, kindWord = k => WORDS.kind[k] || k;

/* BANDS A PACK DECLARES (docs/PACKS.md, A declared section). A wild pack ships no script, so it declares its band in
   its pack.yaml and the node serves it in /issues, with its numbers in it. The doors' Now and the phone page both draw
   them, so the drawing lives here, beside WORDS; esc, said, num, fmt, prov and ago are each page's own (doors-core.js,
   mobile.js). Readout rows only. A reading the node has no row for is not drawn, and the band says how many have not
   arrived; the pack's note is folded under it, "How this is read". Each band joins the part of Now of its stage, and act joins
   decide: neither page has an act part of its own. Returns { observe, decide, measure }, each the bands' HTML. */
const DECL_STAGES = ['observe', 'decide', 'act', 'measure'];
const DECL_AT = { observe: 'observe', decide: 'decide', act: 'decide', measure: 'measure' };
function declaredBands(sections) {
  const seen = new Set(), at = {}, ord = x => Number.isInteger(x.order) ? x.order : 50;
  (sections || []).filter(x => x && x.id && DECL_AT[x.stage] && !seen.has(x.id) && seen.add(x.id))
    .sort((a, b) => DECL_STAGES.indexOf(a.stage) - DECL_STAGES.indexOf(b.stage) || ord(a) - ord(b))
    .forEach(x => { at[DECL_AT[x.stage]] = (at[DECL_AT[x.stage]] || '') + declaredBand(x); });
  return at;
}
function declaredBand(x) {
  const rows = x.readouts || [], want = x.expected || rows.length, missing = want - rows.length, pk = esc(x.pack);
  /* where a reading comes from is said once, under the head, and again on a row only where it changes (4 Nov: the same
     source line under five rows was most of the band) */
  const from = r => `${esc(r.source || x.pack)}${r.provenance ? ` ${prov(r.provenance)}` : ''}${r.age_minutes != null ? ` · ${ago(r.age_minutes)} old` : ''}`;
  const subs = rows.map(from), card = (r, i) => `<div class="row decl" data-kind="readout"><span class="n">${said(r.label || r.metric)}</span>`
    + `<span class="v">${num(`${x.id}.${r.sensor_id || 'x'}.${r.metric}`, fmt(r.value, r.dp), `the ${x.pack} pack’s figure, beside nothing of this node’s`)}<small>${esc(r.unit || '')}</small></span>`
    + (i && subs[i] !== subs[i - 1] ? `<span class="sub">${subs[i]}</span>` : '') + '</div>';
  return `<section class="decl" id="decl-${esc(x.id)}" data-learn="now-bands" data-reads="/issues" data-stage="${esc(x.stage)}" data-pack="${pk}" data-kind="readout">`
    + `<h3 class="nh">${said(x.title || x.id)}</h3>${rows.length ? `<p class="fine src">${subs[0]}</p>` : ''}<div class="rows">${rows.map(card).join('')}</div>`
    + (missing > 0 ? `<p class="fine">${rows.length
      ? `${missing} of the ${want} readings the ${pk} pack declares ${missing === 1 ? 'has' : 'have'} not arrived on this node yet.`
      : `None of the ${want} readings the ${pk} pack declares has arrived on this node yet.`}</p>` : '')
    + (x.note ? `<details class="how"><summary>How this is read</summary><p class="in">${esc(x.note)}</p></details>` : '') + '</section>';
}

if (typeof module !== 'undefined') module.exports = { buildD, doorsLocal, doorsFetch, DOORS_LOCKED, WORDS, stateWord, kindWord };
