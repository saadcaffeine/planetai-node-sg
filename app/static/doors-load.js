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

const DOORS_ROUTES = {
  issues: 'issues', days: 'issues/days?days=7', health: 'health', rho: 'rho', earth: 'earth', reach: 'reach',
  sensors: 'sensors', observations: 'observations', cells: 'cells', stats: 'stats', settings: 'settings',
  /* token-only at every SHARE_LEVEL: a screen without the token gets null and says so */
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
      title: tr(it.title), tagline: tr(it.tagline),
      reason_text: tr(it.reason_text), open_asks: it.open_asks || [],
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
    return { ...e, action: (f.action || {}).text ?? null, peak: f.peak ?? null, rooms: f.rooms || [], answer: f.answer ?? null };
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
    as_of: I.as_of, tz: H.tz, buckets: Y.buckets || [], order: I.order || [], lead: (I.lead || {}).issue ?? (I.order || [])[0],
    labels: (I.labels || {})[L] || {}, metrics: I.metrics || {}, issues, events, buttons: evs.buttons || {},
    node: { name: H.node, place: H.city }, registry: { name: H.node, place: H.city || H.node },
    share: setting('SHARE_LEVEL'), settings: A.settings || null, askOff: setting('UI_ASK') === 'off',   /* the keeper's switch for every ask, the dashboard's and the doors' */ rho: A.rho || {}, health: H,
    earth: A.earth ? { years: E.years || [], changes: E.changes || [], radius_m: E.radius_m, change: E.latest || null,
      sentinel: img.sentinel || [], landsat: img.landsat || [], credit: img.credit || [] } : null,
    reach: A.reach || [], sensors: A.sensors || [], observations: A.observations || [], index_cells: A.cells || [],
    geometry: { ladder: G.ladder || [], radio: G.radio || {}, grain: G.grain_table || [], publication: G.publication || {} },
    point: [H.lon, H.lat], stats15, raw, actions, alerts: A.alerts || asks.acts || [], notes: !!A.actions, asks,
  };
}

/* Every route at once. A 403 is this screen's SHARE_LEVEL speaking, not an error: the part stays null. */
async function loadD() {
  const get = async p => {
    const t0 = (typeof performance !== 'undefined') ? performance.now() : Date.now();
    if (typeof ASKING !== 'undefined') ASKING.flight('/' + p);
    try {
      const r = await fetch('/' + p, { headers: DOORS_AUTH() });
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
    const keys = Object.keys(DOORS_ROUTES), got = await Promise.all(keys.map(k => get(DOORS_ROUTES[k])));
    A = Object.fromEntries(keys.map((k, i) => [k, got[i]]));
  }
  if (!A.issues) throw new Error('GET /issues did not answer this screen: the doors have nothing to draw');
  return buildD(A, (A.health || {}).locale || 'en');
}

if (typeof module !== 'undefined') module.exports = { buildD };
