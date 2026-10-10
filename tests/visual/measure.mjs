#!/usr/bin/env node
/* measure.mjs — the node dashboard, measured from computed layout rather than looked at.
 *
 * ORIGIN. This file is the September UX review's skeleton script, moved into the repo it measures
 * and extended. It was written for Part 2 of that review and lived at
 * `planetai-design/design/audit/2026-09/ux-review/skeleton/measure.mjs` on branch
 * `ux-review-2026-09`; every number in `docs/design/UX_REVIEW_2026-09_skeleton.md` came out of it.
 * Everything above the `TARGETS` section is that script, unchanged except where marked. There is
 * one of these and there must stay one of these: a second measuring script is two sets of numbers
 * that can disagree about the same page.
 *
 * WHAT IS NEW HERE, and why each one exists:
 *   · the page under test is an argument, not a constant. `PAI_STATIC` points at any `app/static`
 *     tree and `PAI_PAGE` at a standalone HTML file, so the shipped page, a redesign branch and a
 *     drawing that happens to be HTML are all measured by the same code on the same day.
 *   · `PAI_OUT` puts the renders somewhere other than beside this file.
 *   · COLLECT also reads the attributes the redesign's targets are written in terms of —
 *     data-num, data-cmp, data-ref, data-kind, aria-hidden, the accessible name of an SVG — and
 *     records DOM order, which T6 is about.
 *   · `targets` computes T1-T7 per render and prints one table. A target with no script behind it
 *     is an opinion.
 *
 * Per render it writes three things:
 *
 *   <name>.json         every visible element: tag, role, data-component, box, margin/padding/gap,
 *                       font-size/weight/line-height, z-index, position; plus every text line box.
 *   <name>_wire.png     a wireframe on a blank ground: text as grey bars at its real line boxes,
 *                       images/canvases/SVGs hatched, controls outlined, nothing else.
 *   <name>_guides.png   the same drawing with a 1 px guide at every left edge three or more
 *                       elements share.
 *
 * Nothing is written to either container. Every request for `/static/*` and for the document
 * itself is intercepted and fulfilled from `PAI_STATIC`, so what is measured is that tree's page
 * against the containers' live API. The refused state is produced by fulfilling `/issues` with the
 * exact 403 body `app/main.py` builds at SHARE_LEVEL=off — no setting on either node is touched.
 *
 * Usage:
 *   node measure.mjs render <job>...      one or more job names (or "all")
 *   node measure.mjs steps                320 -> 1920 in 20 px steps on Now and Wall
 *   node measure.mjs stall <job>          layout with the API stalled, then released
 *   node measure.mjs sheets               contact sheet per view from the wireframes
 *   node measure.mjs header               the header's shape against the node's own name and place
 *   node measure.mjs targets              T1-T7 per render, against the targets table
 *   node measure.mjs audit <job>...       T9: bytes per refresh, axe, named SVGs, motion
 *   node measure.mjs shots <job>...       JPEG, one device pixel: the fold and the whole page
 *   node measure.mjs analyse <table>      grid spacing rhythm lines align type headings order
 *                                         dist wall dom anatomy components stack
 *   node measure.mjs list                 the job table
 *
 * Env: PAI_STATIC   the app/static tree to serve (default: this repo's)
 *      PAI_PAGE     a standalone HTML file to measure instead of a node page (Phase 1 directions)
 *      PAI_OUT      where renders are written (default: beside this file)
 *      PAI_DESIGN_REPO  where playwright is installed (default: ../planetai-design)
 *      PAI_ADMIN_TOKEN, PAI_ACT_TOKEN   the setup-unlocked and arrange jobs only.
 *      Never printed, never written to any output file.
 *
 * Playwright is a DEV dependency of the sibling design repo and not of this one: a node installs
 * this repository and must never be asked for a browser. So it is resolved by path, and a machine
 * without it is told rather than crashed at.
 */
import fs from 'node:fs';
import path from 'node:path';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import { execFileSync } from 'node:child_process';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(HERE, '../..');
// path.resolve's second argument wins outright when it is already absolute, and is joined onto
// the first when it is not — so a caller who exports a relative PAI_DESIGN_REPO (gate.sh's own
// default, `../planetai-design`, relative to nothing in particular) still gets an absolute path,
// which is what createRequire() below demands; it throws ("must be a file URL or absolute path")
// rather than resolving a relative one itself, and that throw used to be gate.sh's whole failure.
const DESIGN = path.resolve(ROOT, process.env.PAI_DESIGN_REPO || '../planetai-design');
let chromium;
try {
  chromium = createRequire(path.join(DESIGN, 'package.json'))('playwright').chromium;
} catch (e) {
  console.error(`  - measure.mjs needs playwright, which is a dev dependency of ${DESIGN}\n`
    + `    (npm install there, or set PAI_DESIGN_REPO). Nothing was measured.`);
  process.exit(3);
}

/* The page under test. STATIC is the tree whose index.html, dashboard.js and dashboard.css are
 * served; PAGE overrides the document alone, for a drawing that carries its own everything. */
const STATIC = process.env.PAI_STATIC
  ? path.resolve(process.env.PAI_STATIC) : path.join(ROOT, 'app/static');
const PAGE = process.env.PAI_PAGE ? path.resolve(process.env.PAI_PAGE) : null;
const OUT = process.env.PAI_OUT ? path.resolve(process.env.PAI_OUT) : HERE;
fs.mkdirSync(OUT, { recursive: true });

const POP = 'http://127.0.0.1:8081';        // bootstrapped, SHARE_LEVEL=open
const EMPTY = 'http://127.0.0.1:8082';      // fresh install, BOOTSTRAP=0
/* Which snapshot the node routes answer from. PAI_Q is the page's own query string and may name a
 * fixture; PAI_FIXTURE is what serveNodeAPI serves. They are one fact, so PAI_Q wins when it names
 * one — gate.sh set only PAI_Q, and the page then asked for one capture while /sensors, /health and
 * /settings answered from another, which is a mismatch nothing would have printed. */
const _qFixture = (process.env.PAI_Q || '').match(/[?&]fixture=([a-z0-9][a-z0-9._-]{0,63})/);
const FIXTURE = (_qFixture && _qFixture[1]) || process.env.PAI_FIXTURE || 'node1-2026-09-06';

// The node's own refusal, from app/main.py:744, for SHARE_LEVEL=off on /issues.
const REFUSAL = p => JSON.stringify({ error:
  `this node is set to SHARE_LEVEL=off, so ${p} answers only this machine or a request carrying a `
  + `token. Set SHARE_LEVEL to open in the dashboard's Set up view to let anything on your network `
  + `read it.` });

const MIME = { '.css': 'text/css', '.js': 'text/javascript', '.svg': 'image/svg+xml',
  '.json': 'application/json', '.html': 'text/html', '.ttf': 'font/ttf', '.woff2': 'font/woff2' };

/* ------------------------------------------------------------------ the node, without a node
 *
 * `dashboard.js`'s own `snapshot()` reads `/issues` (or `/issues/fixtures/<name>` in fixture mode),
 * `/health`, `/settings` and `/place/geojson` before it draws anything. Getting a real answer to
 * those four used to mean a bootstrapped container was running at POP — heavy to stand up for a
 * rendering task, and the wrong container besides: this branch's `/issues` is not built yet, and
 * would not be in a container even if it were. So, when PAI_LIVE is not '1', this repo answers its
 * own node's endpoints instead of asking one — a render becomes hermetic: no node, no container, no
 * network. `PAI_LIVE=1` is unchanged: it still measures a running container with no interception at
 * all, which is the whole point of that flag.
 *
 * These seven are answered offline: the original four, plus `/earth`, `/trust` and `/forecast`,
 * which dashboard.js's `snapshot()` calls unconditionally AFTER the `if (FIXTURE)` branch — they
 * are not part of "the page would stop being renderable from a fixture alone" (that comment is
 * about `/issues` alone) and a fixture-mode render still asks for all three. Before these three
 * were intercepted, that request fell through `route.continue()` to whatever was listening at the
 * render origin: on the machine this file was written on, a local node, which answered them empty;
 * on a machine with nothing listening there, a connection that never gets accepted, caught by
 * dashboard.js's own `.catch(() => null)` into the same empty state — slower, and not hermetic,
 * but the same empty state either way, which is why the Sentinel strip, the AlphaEarth record, the
 * trust card and the forecast card have only ever been seen empty. Everything else `dashboard.js`
 * fetches (`/alerts`, `/rho`, `/sensors`, `/nearby`, `/cells`, `/sparks`, `/report/latest`) really
 * is never asked for in fixture mode: `snapshot()` takes a different branch entirely when
 * `?fixture=` is set and calls only `/issues/fixtures/<name>` for the snapshot itself.
 */

// The environment `settings` reads the fixture under. `app/settings.py`'s `get()` falls back straight
// to `os.environ` with no `.env` and no reachable database — checked directly (`settings.get(
// 'BAD_RADIUS_KM', '<none>')` prints `<none>` in a bare child) — and an empty environment is not a
// neutral one, it is a DIFFERENT node: BAD_RADIUS_KM defaults to 15 instead of node #1's own 8
// (presets/bali.env), NODE_ISSUES defaults to every issue in file order instead of the declared
// air/heat/land/coast, and NODE_LAT/NODE_LON default to 0. The fixture is node #1 — `bayu-2`, city
// `bali` — and is only a meaningful replay under the settings it was captured with, so the child gets
// the bali preset plus the coordinates and names the fixture's own `health` object carries (which
// win over the preset: they are the specific node, the preset is only the island it sits on). Nothing
// here writes a `.env` file or touches production code; it is one object handed to `execFileSync`.
function nodeEnv(health) {
  const env = {};
  const preset = path.join(ROOT, 'presets/bali.env');
  if (fs.existsSync(preset)) {
    for (const line of fs.readFileSync(preset, 'utf8').split('\n')) {
      const l = line.trim();
      if (!l || l.startsWith('#')) continue;
      const i = l.indexOf('=');
      if (i > 0) env[l.slice(0, i)] = l.slice(i + 1);
    }
  }
  const h = health || {};
  if (h.lat != null) env.NODE_LAT = String(h.lat);
  if (h.lon != null) env.NODE_LON = String(h.lon);
  if (h.city) env.NODE_CITY = h.city;
  if (h.node) env.NODE_NAME = h.node;
  return env;
}

// The fixture's own health object, read without the full replay below — nodeEnv() needs it before
// settings is even imported, so this is a second, cheap read of the same file rather than a chicken
// looking for its egg.
function fixtureHealth(name) {
  try {
    return JSON.parse(fs.readFileSync(
      path.join(ROOT, 'app/issues/fixtures', `${name}.json`), 'utf8')).health || {};
  } catch (e) { return {}; }
}

// One shell-out per fixture name, per run of this script — ONE child does both jobs, because a
// second subprocess that "receives the same env recipe" is not "the same child" (a review of round 1
// correctly called that comment false). It replays the snapshot exactly as `app/issues/api.py`'s
// `fixture()` route does, and reads GET /settings' own answer, in the one process, so a page reading
// both never sees two different nodes and there are not two copies of the env-building expression to
// drift apart. Cached per fixture name because a `render` command asks for the same fixture on every
// job, and a fresh Python process to recompute unchanged data would be the slow part of measuring
// four viewports.
//
// Returns `{ status: 200, snapshot, settings }` on success, or `{ status, error }` on failure — 404
// when the fixture file itself is missing (a real, supported state: a checkout need not carry every
// fixture), 500 when Python raised. There is no third shape that hands back an empty object: a
// child that fails and a child that answers "no issues, no health" must never look the same to
// whatever reads the response, or a broken rig measures a broken page and reports it as an empty one.
const REPLAY_FAILED = [];
process.on('exit', c => {
  if (REPLAY_FAILED.length && !c) {
    console.error(`measure.mjs: ${REPLAY_FAILED.length} fixture(s) never replayed `
      + `(${[...new Set(REPLAY_FAILED)].join(', ')}), so anything measured after that was measured `
      + `on a page with no data. Exiting non-zero rather than reporting it.`);
    process.exitCode = 1;
  }
});

const _nodeDataCache = new Map();
function computeNodeData(name) {
  if (_nodeDataCache.has(name)) return _nodeDataCache.get(name);
  const f = path.join(ROOT, 'app/issues/fixtures', `${name}.json`);
  let result;
  if (!fs.existsSync(f)) {
    result = { status: 404, error: `no such fixture in this checkout: app/issues/fixtures/${name}.json` };
  } else {
    // Matches app/issues/api.py's fixture() route: load the snapshot, then
    // snap["issues"] = engine.replay(snap, main.settings, load()). `main.settings` and the plain
    // `settings` module are the same import — `main.py` does `import settings` — so importing it
    // directly, without a running `main`, replays the same call. `settings.describe()` alongside it
    // is GET /settings' own body, for an anonymous or open-share reader (unlocked=False, the PUBLIC
    // keys unmasked) — this is a CHECKOUT's settings, not a running node's: there is no database
    // here for the GUI to have touched, so every value is settings.py's own shipped default under
    // the environment below.
    const script = `import json, sys
sys.path.insert(0, 'app')
import settings
from issues import load, engine
snap = json.load(open(${JSON.stringify(`app/issues/fixtures/${name}.json`)}))
snap['issues'] = engine.replay(snap, settings, load())
desc = settings.describe(unlocked=False, public=settings.PUBLIC)
admin = settings.describe(unlocked=True)
import packs
print(json.dumps({'snapshot': snap, 'settings': desc, 'settingsAdmin': admin, 'packs': packs.manifests()}, default=str))`;
    try {
      // maxBuffer, because the default is 1 MB and every snapshot taken from a node that has been
      // running a while is larger than that: node #1's 21 Sep fixture is 1.5 MB in and more out.
      // Without it execFileSync throws ENOBUFS, the page renders with no data at all, and `targets`
      // then prints a full table of crosses that reads as the page having broken.
      const out = execFileSync('python3', ['-c', script],
        { cwd: ROOT, maxBuffer: 512 * 1024 * 1024,
          env: { ...process.env, PACKS_DIR: 'packs', PYTHONPATH: 'app', ...nodeEnv(fixtureHealth(name)) } });
      result = { status: 200, ...JSON.parse(out.toString()) };
    } catch (e) {
      const msg = `python3 failed replaying fixture ${name}: ${e.message.split('\n')[0]}`;
      console.error(`measure.mjs: ${msg}`);
      REPLAY_FAILED.push(name);
      result = { status: 500, error: msg };
    }
  }
  _nodeDataCache.set(name, result);
  return result;
}

// The plan the `place` pack keeps, which this repo does not carry — it lives in the design repo,
// the same 5,376-feature file the pack itself stores. A checkout without the design repo (or with
// PAI_DESIGN_REPO pointed elsewhere) renders with no plan, which is a real, supported state: the
// page's own place code treats an absent plan as an absence, not a failure (app/static/dashboard.js
// checks `r.ok` and passes `null` on).
const PLACE_GEOJSON = path.join(DESIGN, 'data/place.geojson');

// Fulfils a route with the ONE shape a broken or missing fixture answers with: a non-200 whose body
// names the endpoint that asked and the error computeNodeData() recorded, so a Python failure reads
// as a Python failure — never as a page rendered against an empty node. `data.status` is 404 (no
// such fixture) or 500 (Python raised); either way the body says which endpoint and why.
function failNodeAPI(route, endpoint, data) {
  return route.fulfill({ status: data.status, contentType: 'application/json',
    body: JSON.stringify({ detail: `measure.mjs: ${endpoint} has no data — ${data.error}` }) });
}

/* /earth, /trust and /forecast used to fall through `route.continue()` to whatever happened to be
 * listening at the render origin — a local node, on the machine this file was written on, which
 * answered them empty. On a machine (or a CI runner) with nothing listening there, the same
 * `route.continue()` hangs on a connection that will never be accepted and then rejects, and
 * dashboard.js's own `.catch(() => null)` around each of the three (see snapshot(), further down
 * this file) turns that into the same empty state anyway — so every render anyone has looked at
 * has shown these three empty, by accident, slowly, and only because nothing crashed loudly enough
 * to notice. That is not hermetic (it still reaches out to the network, even if nothing answers)
 * and it is not fast. These three routes answer instead, deterministically and offline, so a
 * render never depends on what else happens to be running.
 *
 * The empty bodies below are not copied off a running node — the invariants in AGENTS.md say never
 * to touch app/ for this task, so `q()`'s SQL cannot be re-run, and main.py imports psycopg,
 * bootstrap and paho-mqtt at module scope, none of which this checkout may need installed just to
 * measure a page. Each is instead the shape main.py's own route hands back when there is nothing
 * in the database to find, read off that route's source rather than executed:
 *   /trust     (main.py:896)  one row per local sensor — with none, an empty list.
 *   /forecast  (main.py:1024) point + two empty lists + fixed attribution + far_from_node: null.
 *   /earth     (main.py:1193) the earth pack IS enabled in this checkout (packs/earth/pack.yaml
 *              exists and nothing in presets/bali.env restricts PACKS_ENABLED — verified by running
 *              app/packs.py's own manifests() against this repo's packs/ directory), so `enabled`
 *              is true and the honest empty state is "no years cached yet", not "pack missing". */
function emptyTrust() { return []; }

function emptyForecast(health) {
  return { point: { lat: (health || {}).lat ?? 0, lon: (health || {}).lon ?? 0 }, sources: [], hours: [],
    attribution: ["BMKG (Badan Meteorologi, Klimatologi, dan Geofisika), api.bmkg.go.id",
      "Open-Meteo, open-meteo.com, CC-BY 4.0 (free tier: non-commercial use only)"],
    far_from_node: null };
}

function emptyEarth(health) {
  const node = (health || {}).node || 'node';
  return { node, enabled: true, years: [], bytes: 0, latest: null, changes: [], frames: [],
    dir: `/app/out/earth/${node}`,
    imagery: { sentinel: [], landsat: [],
      credit: ["Contains modified Copernicus Sentinel data, processed by Google Earth Engine.",
        "Landsat courtesy of the U.S. Geological Survey."] },
    png: null, lat: (health || {}).lat ?? 0, lon: (health || {}).lon ?? 0, radius_m: 5000,
    attribution: "The AlphaEarth Foundations Satellite Embedding dataset is produced by Google and "
      + "Google DeepMind. CC BY 4.0.",
    hint: "no satellite record yet: planetai run earth fetch" };
}

/* The one populated case, gated behind PAI_RICH=1 rather than always on: nobody has ever seen the
 * Sentinel strip, the AlphaEarth record, the trust card and the forecast card populated at once,
 * because nothing before this served /earth, /trust or /forecast at all. tests/visual/rich-fixture
 * .json is a hand-written stand-in — see its own "_what_this_is" — read once and cached, same
 * reason computeNodeData() caches: a render command asks for the same fixture on every job.
 *
 * WHAT PAI_RICH DOES NOT SERVE, and a reader of a rich shot has to know it: three JSON bodies, and
 * no image bytes. The Sentinel strip's frames are <img src="/earth/frame.png?source=sentinel&year=…">,
 * which is not one of the routes above, so a rich render shows the strip POPULATED WITH YEARS AND EMPTY OF
 * PICTURES — every frame is the figure that says its image is missing, counted in the caption. That
 * is the rig being honest about what it has, not a regression in the page; a shot of the real strip
 * needs PAI_LIVE=1 against a node that has run `planetai run earth fetch`. The
 * forecast's hours are stored as offsets from render time, not baked-in timestamps, because
 * dashboard.js filters hours to `>= now - 1h` — a fixture with a fixed past date would silently
 * stop rendering any forecast the day after it was written. */
let _richFixture;
function richFixture() {
  if (_richFixture === undefined) {
    try {
      _richFixture = JSON.parse(fs.readFileSync(path.join(HERE, 'rich-fixture.json'), 'utf8'));
    } catch (e) { _richFixture = null; }
  }
  return _richFixture;
}
function richForecast() {
  const f = richFixture().forecast;
  const now = Date.now();
  return { ...f, hours: f.hour_offsets.map(h => ({ ...h, ts: new Date(now + h.offset_h * 3.6e6).toISOString() })) };
}

/* Answers the four endpoints above from this repo, offline. Returns true when it fulfilled the
 * route — the caller must not also route.continue() it. Shared by `open()`'s render path and
 * `stall()`'s stall path: both serve a page and both need the same four answers for the same
 * reason, so there is one function rather than two copies that can drift. */
/* The pinned registry, read by the node's own loader so the rig cannot drift from it. Cached: it is
 * a file on disk and 417 kB of JSON, and every job would otherwise pay for it again. */
let _registry;
function spawnRegistry() {
  if (_registry !== undefined) return _registry;
  const script = `import json, sys
sys.path.insert(0, 'app')
import registry
entries, ver = registry.load()
rows = registry.find() if entries else []
print(json.dumps({"registry": {k: ver.get(k) for k in ("sha","short","synced","entries")},
                  "count": len(rows), "sources": rows}))`;
  try {
    _registry = execFileSync('python3', ['-c', script],
      { cwd: ROOT, maxBuffer: 512 * 1024 * 1024,
        // SOURCES_DIR defaults to the container's /app/data/sources, so a checkout loads nothing.
        env: { ...process.env, PYTHONPATH: 'app', SOURCES_DIR: path.join(ROOT, 'data', 'sources') } }).toString();
  } catch (e) {
    console.error(`measure.mjs: the registry did not load: ${e.message.split('\n')[0]}`);
    _registry = null;
  }
  return _registry;
}

async function serveNodeAPI(route, u) {
  const fx = u.pathname.match(/^\/issues\/fixtures\/([a-z0-9][a-z0-9._-]{0,63})$/);
  if (fx) {
    const name = decodeURIComponent(fx[1]);
    const data = computeNodeData(name);
    await (data.error ? failNodeAPI(route, `/issues/fixtures/${name}`, data)
      : route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(data.snapshot) }));
    return true;
  }
  /* GET /issues/days, from the capture (docs/SPEC_dashboard_figures.md §3.4). A capture taken before v0.78 has no
     issues_days, and the answer is the 404 a node without the route gives: the strips then draw their own empty
     state, which is the truth about that capture. */
  if (u.pathname === '/issues/days') {
    const data = computeNodeData(FIXTURE);
    if (data.error) { await failNodeAPI(route, u.pathname, data); return true; }
    const body = data.snapshot.issues_days;
    await (body == null
      ? route.fulfill({ status: 404, contentType: 'application/json',
          body: JSON.stringify({ detail: 'this snapshot carries no issues_days' }) })
      : route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) }));
    return true;
  }
  if (u.pathname === '/issues' || u.pathname === '/issues/') {
    const data = computeNodeData(FIXTURE);
    await (data.error ? failNodeAPI(route, '/issues', data)
      : route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(data.snapshot.issues) }));
    return true;
  }
  if (u.pathname === '/health') {
    const data = computeNodeData(FIXTURE);
    await (data.error ? failNodeAPI(route, '/health', data)
      : route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(data.snapshot.health) }));
    return true;
  }
  if (u.pathname === '/settings') {
    const data = computeNodeData(FIXTURE);
    // The unlocked body for the rig's own PAI_ADMIN_TOKEN, so setup-unlocked draws from a fixture and not
    // only against a live node. Any other token gets the anonymous body, as a node answers a wrong one.
    const t = process.env.PAI_ADMIN_TOKEN;
    const admin = t && route.request().headers().authorization === `Bearer ${t}`;
    await (data.error ? failNodeAPI(route, '/settings', data)
      : route.fulfill({ status: 200, contentType: 'application/json',
        body: JSON.stringify(admin ? data.settingsAdmin : data.settings) }));
    return true;
  }
  if (u.pathname === '/packs') {
    const data = computeNodeData(FIXTURE);
    await (data.error ? failNodeAPI(route, '/packs', data)
      : route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(data.packs || []) }));
    return true;
  }
  if (u.pathname === '/earth') {
    /* THE CAPTURE'S OWN EARTH WHEN IT HAS ONE. `planetai snapshot` did not fetch /earth until
     * 21 Sep, so every fixture was earthless and this route had only two things it could serve: an
     * empty stub or the design repo's rich one. A fixture that now CARRIES nine years of embeddings
     * and eight change pairs was still being handed the empty stub, so Historical reviewed as "this
     * node has no satellite passes on disk yet" while the node it was captured from has ten years
     * of them. The stubs stay for the fixtures that genuinely have none, and for PAI_RICH. */
    const snap = computeNodeData(FIXTURE).snapshot;
    const body = snap?.earth
      ?? (process.env.PAI_RICH === '1' ? richFixture().earth : emptyEarth(snap?.health));
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) });
    return true;
  }
  if (u.pathname === '/trust') {
    const body = process.env.PAI_RICH === '1' ? richFixture().trust : emptyTrust();
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) });
    return true;
  }
  if (u.pathname === '/forecast') {
    const health = computeNodeData(FIXTURE).snapshot?.health;
    const body = process.env.PAI_RICH === '1' ? richForecast() : emptyForecast(health);
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) });
    return true;
  }
  /* The rest of the snapshot, answered under the route the node answers it under.
   *
   * These were simply absent: a `?fixture=` page fetched /sensors and got nothing, so every section
   * that needs it drew "the core pack has nothing here yet" in review while working perfectly on a
   * real node. A rig that is LESS capable than the node reports a working section as broken, which
   * is the same false measurement as a rig that is more permissive reporting a broken one as fine.
   *
   * /trust and /forecast are NOT here: they have their own empty-vs-rich branches above, which is a
   * deliberate choice about what a review should see, not a gap. */
  const FROM_SNAPSHOT = {
    '/sensors': 'sensors', '/cells': 'cells', '/nearby': 'nearby', '/alerts': 'alerts',
    '/observations': 'observations', '/stats': 'stats', '/reach': 'reach', '/rho': 'rho',
    '/actions': 'actions', '/report/latest': 'report_latest',
    /* Added 23 September with the two learning routes. A capture taken before `planetai snapshot`
       fetched them carries neither key, and then `body === undefined` below answers 404 and the
       section draws its own absent line — which is the truth about that capture, not a fault. */
    '/shape': 'shape', '/effect': 'effect',
  };
  if (FROM_SNAPSHOT[u.pathname]) {
    const data = computeNodeData(FIXTURE);
    if (data.error) { await failNodeAPI(route, u.pathname, data); return true; }
    const body = data.snapshot[FROM_SNAPSHOT[u.pathname]];
    /* A key the snapshot does not carry is a 404, exactly as a node with that route switched off
       answers — never an empty array, which would be the snapshot claiming a fact it never took. */
    await (body == null
      ? route.fulfill({ status: 404, contentType: 'application/json',
          body: JSON.stringify({ detail: `this snapshot carries no ${FROM_SNAPSHOT[u.pathname]}` }) })
      : route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) }));
    return true;
  }
  if (u.pathname === '/sources') {
    /* From the pinned registry in data/sources, the same file app/main.py::sources_ reads — not
     * from the snapshot, which does not carry it and should not: the registry is identical on every
     * node at a given pin, so a capture of one node has no opinion about it. */
    const r = spawnRegistry();
    if (r == null) return route.fulfill({ status: 503, contentType: 'application/json',
      body: JSON.stringify({ detail: 'no source registry in this checkout' }) });
    await route.fulfill({ status: 200, contentType: 'application/json', body: r });
    return true;
  }
  /* THE ASK PANE'S THREE ROUTES, stood in for. The node's own answers are held by tests/test_ask.py;
     these only give the page something shaped like them to draw. PAI_ASK_MODEL set = a node with a
     model running; unset = a node with no loop, which answers 404 with what to pull. /ask streams one
     canned answer that reaches for MAP_TILES, so the page's proposal card can be looked at. */
  if (u.pathname === '/ask/status') {
    /* PAI_ASK_ONLINE=1: the node's Set up puts an online model first (AGENT_PREFER=strongest). */
    const online = process.env.PAI_ASK_ONLINE === '1';
    const top = online ? { rung: 'online', model: 'claude-x', host: 'api.anthropic.com', where: 'online' }
      : { rung: 'local', model: process.env.PAI_ASK_MODEL, host: 'host.docker.internal', where: 'this machine' };
    await (process.env.PAI_ASK_MODEL
      ? route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({
          model: top.model, rung: top.rung, where: top.where, host: top.host, leaves: online,
          rungs: online ? [top, { rung: 'local', model: process.env.PAI_ASK_MODEL, host: 'host.docker.internal', where: 'this machine' }] : [top],
          running: true, why: null, stored: false,
          tools: [{ name: 'issues', class: 'read' }, { name: 'act', class: 'act' }, { name: 'settings_set', class: 'admin' }] }) })
      : route.fulfill({ status: 404, contentType: 'application/json', body: JSON.stringify({ detail: {
          error: 'no model is set up on this node; `planetai agent local` sets one up', mcp: '/mcp', token_hint: 'planetai agent',
          recommend: { tag: 'qwen3.5:4b', size: '3.4 GB', memory_gb: 8, pull: 'planetai agent local pull qwen3.5:4b' } } }) }));
    return true;
  }
  if (u.pathname === '/ask') {
    const sse = (e, d) => `event: ${e}\ndata: ${JSON.stringify(d)}\n\n`;
    /* A model that takes its time, so the pane's waiting state can be looked at. */
    if (process.env.PAI_ASK_SLOW) await new Promise(r => setTimeout(r, Number(process.env.PAI_ASK_SLOW)));
    const words = 'I have put MAP_TILES on a card. Nothing changed; you decide.'.split(' ');
    await route.fulfill({ status: 200, contentType: 'text/event-stream', body:
      sse('tools', { tool: 'issues', ms: 12 })
      + sse('proposal', { tool: 'settings_set', args: { changes: { MAP_TILES: 'on' } }, setting: 'MAP_TILES',
          current: 'off', proposed: 'on', choices: ['off', 'on'], group: 'node',
          leaves: { en: 'Satellite and street view tiles from the internet. Each tile request tells a tile server which square of the planet this house is looking at.' },
          undo: { en: 'Set MAP_TILES back to off under Set up \u2192 sharing.' } })
      + words.map(w => sse('token', { text: w + ' ' })).join('')
      + sse('done', process.env.PAI_ASK_ONLINE === '1'
        ? { rung: 'online', model: 'claude-x', host: 'api.anthropic.com', where: 'online' }
        : { rung: 'local', model: process.env.PAI_ASK_MODEL || 'qwen3.5:4b', host: 'host.docker.internal', where: 'this machine' }) });
    return true;
  }
  if (u.pathname === '/docs/search') {
    const qq = (u.searchParams.get('q') || '').toLowerCase();
    const rows = JSON.parse(fs.readFileSync(path.join(ROOT, 'data/docs_site.json'), 'utf8'));
    const hits = rows.filter(r => (r.title + ' ' + r.text).toLowerCase().includes(qq)).slice(0, 20)
      .map(r => ({ page: r.page, anchor: r.anchor, title: r.title,
        snippet: r.text.slice(Math.max(0, r.text.toLowerCase().indexOf(qq) - 80)).slice(0, 240) }));
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(hits) });
    return true;
  }
  if (u.pathname === '/place/geojson') {
    await (fs.existsSync(PLACE_GEOJSON)
      ? route.fulfill({ status: 200, contentType: 'application/geo+json', body: fs.readFileSync(PLACE_GEOJSON) })
      : route.fulfill({ status: 404, contentType: 'application/json',
          body: JSON.stringify({ detail: 'no place plan in this checkout' }) }));
    return true;
  }
  return false;
}

const WIDTHS = [375, 390, 768, 1440];
/* `historical` was missing. The page has had that view since the tab order changed (dashboard.js
 * VIEWS), and the overflow check below has always covered it — but the job table did not, so
 * `render`, `shots` and `targets` could not be pointed at it and nothing on it has ever been
 * measured. Prompt 4 is largely about that view. */
const VIEWS = ['now', 'historical', 'network', 'setup', 'setup-unlocked', 'wall', 'arrange'];

/* ------------------------------------------------------------------ the job table */
function jobs() {
  const j = [];
  for (const v of VIEWS) for (const w of WIDTHS) j.push({ name: `${v}_populated_${w}`, view: v, w, state: 'populated' });
  j.push({ name: 'wall_populated_1920_dark', view: 'wall', w: 1920, state: 'populated', dark: true });
  for (const w of [390, 1440]) {
    j.push({ name: `now_empty_${w}`, view: 'now', w, state: 'empty', wireOnly: true });
    j.push({ name: `now_refused_${w}`, view: 'now', w, state: 'refused', wireOnly: true });
  }
  /* The live path, which is a different weight from the fixture path and is the one T9 is about.
   * `?fixture=` refetches the whole committed snapshot every refresh — one 75 kB file — where a
   * node makes thirteen small calls. Measuring only the fixture would report a budget failure the
   * household never pays, and measuring only the node would miss that a design round's own rig is
   * heavier than the thing it is reviewing. */
  for (const w of [390, 1440]) j.push({ name: `now_live_${w}`, view: 'now', w, state: 'live' });
  j.push({ name: 'wall_live_1920_dark', view: 'wall', w: 1920, state: 'live', dark: true });
  return j;
}

/* One name per render. PAI_LIVE measures different code; PAI_TAG captures the same drawing in a
 * different state. Either way it must never land on another render's filename. */
const tagged = j => ({ ...j,
  name: j.name + (process.env.PAI_LIVE === '1' ? '_live' : '')
    + (process.env.PAI_TAG ? '_' + process.env.PAI_TAG : '') });

/* ------------------------------------------------------------------ the browser */
async function open(job, opts = {}, stranger = null) {
  /* EMPTY was a second container on :8082 — a fresh install with BOOTSTRAP=0, from the pai-clean
     review rig. It is not running anywhere now, and nothing noticed: the document is fulfilled from
     PAI_STATIC whatever the origin, and every API call fell through to serveNodeAPI, which answers
     from the snapshot. So `state: 'empty'` rendered the POPULATED page from a dead origin, and had
     since that rig was taken down. The page has its own honest mechanism for this and the docs name
     it — `?state=empty` runs emptySnapshot() over the fixture — so that is what a capture uses. */
  const base = POP;
  const browser = await chromium.launch();
  /* `reducedMotion: 'reduce'` is the default here and has been since this file was written: a
     screenshot of a page mid-animation is a different picture every run, so every measurement in
     this file is of the page with motion off. `opts` is for the one check that is ABOUT motion —
     the loading state — which has to see both settings to say anything. */
  const ctx = await browser.newContext({
    viewport: { width: job.w, height: job.w >= 1920 ? 1080 : 900 },
    deviceScaleFactor: 1, colorScheme: 'light', reducedMotion: 'reduce', ...opts,
  });

  /* A drawing that happens to be HTML: one file, no fetch, no views to switch between. Measured by
   * exactly the same COLLECT as a node page, which is the only reason a direction's numbers can be
   * set beside the shipped page's.
   *
   * SERVED, not opened. From a file:// document Chromium refuses an external `<use href>` outright
   * ("Unsafe attempt to load URL"), so every sign is a 0x0 box, and tokens.css's faces fail their
   * CORS check, so Figtree and Funnel Sans fall back silently — measured: `document.fonts.check`
   * false for both, and the sign sprite's bounding box 0x0. A drawing judged on type size and signs
   * cannot be measured with neither. So the document is fulfilled at the node's own origin and
   * `/static/*` comes from STATIC, which means the drawing's markup carries the same paths the
   * node's page carries and is on the same frozen layer, byte for byte. */
  if (PAGE) {
    /* The whole prototype folder is served as a static site and the drawing is opened at its own
     * path inside it, so the same relative hrefs work here and under a plain
     * `python3 -m http.server` in that folder — which is how a person reads these. */
    const dir = path.dirname(PAGE);
    const root = path.dirname(dir);
    const at = '/' + path.basename(dir) + '/';
    await ctx.route('**/*', route => {
      const u = new URL(route.request().url());
      if (u.origin !== POP) return route.continue();
      const rel = u.pathname === at || u.pathname === at + 'index.html'
        ? PAGE : path.join(root, decodeURIComponent(u.pathname).slice(1));
      if (rel.startsWith(root) && fs.existsSync(rel) && fs.statSync(rel).isFile()) {
        return route.fulfill({ status: 200, body: fs.readFileSync(rel),
          headers: { 'content-type': MIME[path.extname(rel)] || 'application/octet-stream' } });
      }
      return route.fulfill({ status: 404, body: 'not part of this drawing' });
    });
    const page = await ctx.newPage();
    await page.goto(POP + at + (process.env.PAI_Q || ''), { waitUntil: 'load' });
    if (job.dark) await page.evaluate(() => document.documentElement.setAttribute('data-theme', 'dark'));
    await page.evaluate(() => document.fonts && document.fonts.ready);
    await page.waitForTimeout(600);
    return { browser, page };
  }

  // Serve PAI_STATIC's tree for the document and every companion file.
  await ctx.route('**/*', async route => {
    const u = new URL(route.request().url());
    if (u.origin !== base) return route.continue();
    /* PAI_LIVE=1 measures what the container actually serves instead of the PAI_STATIC tree.
       Used to re-measure a finding against the code as shipped. */
    let file = null;
    if (process.env.PAI_LIVE !== '1') {
      if (u.pathname === '/' || u.pathname === '/index.html') file = 'index.html';
      else if (u.pathname.startsWith('/static/')) file = u.pathname.slice(8);
    }
    if (file) {
      /* The node serves /static/<NAME> from an allowlist that takes a NAME and not a path — a path
       * parameter reaching the filesystem on a port open to a household LAN is the usual way that
       * goes wrong. So the four faces live under app/static/fonts/ and are asked for flat, and this
       * resolves a flat name into that directory the way the node's allowlist does.
       *
       * AND IT REFUSES A PATH, since 21 September 2026. It used to serve the directory layout too,
       * so `/static/fonts/x.woff2` — which 404s on every real node — resolved here and every render
       * in this repo showed a page with fonts the node could not load. That is how JetBrains Mono
       * went four months declared only in planetai-theme.css at `fonts/jetbrains-mono-latin.woff2`,
       * 404ing on hardware, with every number in ui-monospace, and no render ever saying so. A rig
       * more permissive than the thing it measures reports a page that does not exist. */
      const p = file.includes('/') ? null
        : fs.existsSync(path.join(STATIC, file)) ? path.join(STATIC, file)
          : path.join(STATIC, 'fonts', file);
      if (p === null) return route.fulfill({ status: 404, body: 'the node serves a name, not a path' });
      if (p && fs.existsSync(p)) return route.fulfill({
        status: 200, body: fs.readFileSync(p),
        headers: { 'content-type': MIME[path.extname(p)] || 'application/octet-stream' } });
    }
    if (job.state === 'refused' && !/^\/(static|health)/.test(u.pathname))
      return route.fulfill({ status: 403, contentType: 'application/json', body: REFUSAL(u.pathname) });
    // Offline node endpoints — see "the node, without a node" above. Tried after the refusal check
    // so a refused job still gets its 403 on /issues, /settings and /place/geojson exactly as
    // before; /health is carved out of that check above and lands here instead of on the network.
    if (process.env.PAI_LIVE !== '1' && await serveNodeAPI(route, u)) return;
    return route.continue();
  });

  const page = await ctx.newPage();
  /* A pack's dashboard contribution is one more static file the node serves, and it registers when
     it parses. A setter on window.PAI reproduces that timing exactly — the registration lands the
     moment dashboard.js assigns the contract, before route() has drawn anything — without the page
     being edited to expect a visitor. */
  if (stranger) {
    await page.addInitScript(`(() => { window.__pai_probe = 'installed'; let real;
      Object.defineProperty(window, 'PAI', { configurable: true, get: () => real,
        set: v => { real = v; if (v && v.register) {
          try { (${stranger.toString()})(); window.__pai_probe = 'fired'; }
          catch (e) { window.__pai_probe = 'threw: ' + (e && e.message); } } } }); })()`);
  }
  const q = [];
  // 'live' reads the node itself; 'empty' is the fixture with emptySnapshot() run over it
  if (job.state === 'populated' || job.state === 'empty') q.push(`fixture=${FIXTURE}`);
  if (job.state === 'empty' || job.state === 'refused') q.push(`state=${job.state}`);
  if (job.dark) q.push('theme=dark');
  /* The page has three modes and `?mode=` selects one without remembering it, which is exactly what
     a measuring rig wants: no localStorage to clear between renders, and the same URL a person can
     be sent. A job may name one; PAI_MODE sets it for a whole run. */
  const uiMode = job.mode || process.env.PAI_MODE;
  if (uiMode) q.push(`mode=${uiMode}`);
  /* gate.sh renders the fold open with `PAI_Q="$PAI_Q&worth=1"`; the URL is built from `q`, so PAI_Q's
     worth has to be carried over here or that render is the closed page under another tag. */
  if (/[?&]worth=1\b/.test(process.env.PAI_Q || '')) q.push('worth=1');
  if (job.register) q.push(`register=${job.register}`);
  /* `?ask=1` opens the ask pane without remembering it; a job may ask for it, PAI_ASK=1 for a run. */
  if (job.ask || process.env.PAI_ASK === '1') q.push('ask=1');
  await page.goto(base + '/' + (q.length ? '?' + q.join('&') : ''), { waitUntil: 'networkidle' });

  // ?theme=dark boots straight to the wall and body.wallview hides the header, so there is no nav
  // button to press (Part 1, H9). Every other view is reached from the nav.
  const already = await page.evaluate(() => document.body.classList.contains('wallview'));
  const target = job.view.startsWith('setup') ? 'setup' : job.view;
  if (!(already && target === 'wall') && target !== 'now') await page.click(`button[data-view="${target}"]`);

  /* THE VIEW IT ASKED FOR IS THE VIEW IT GOT.
   *
   * Nothing checked this, and it cost the Set up view: a temporal-dead-zone error in main() made
   * every render of it throw, main() bailed before assigning #page, and the page that was already
   * drawn stayed drawn — so the rig pressed Set up, screenshotted Now, and wrote the file under the
   * Set up name. Byte-identical to the Now shot beside it, which is how it was finally caught. Both
   * the shot and the measurement had been of the wrong page since the branch began.
   *
   * A render that silently measures a different page is worse than a render that fails, so this
   * fails. `body.wallview` is how the wall says it is on; every other view is its own id. */
  if (target !== 'now') {
    const got = await page.evaluate(t => (t === 'wall'
      ? document.body.classList.contains('wallview')
      : !!document.getElementById(`view-${t}`)
        || !!document.querySelector(`nav.views button[data-view="${t}"].on`)), target);
    if (!got) {
      const err = await page.evaluate(() => (window.__paiLastError || null));
      throw new Error(`pressed ${target} and the page did not go there`
        + `${err ? ` — the page threw: ${err}` : ''}`);
    }
  }

  // Arrange needs no token to enter: the bar and the per-band controls render for anyone, and only
  // Done refuses (Part 1, A8). Set up does, and it is the only job that reads one.
  if (job.view === 'setup-unlocked') {
    const t = process.env.PAI_ADMIN_TOKEN;
    if (!t) throw new Error('PAI_ADMIN_TOKEN not set — needed for ' + job.view);
    await page.fill('#tok', t);
    await page.click('#btn-unlock');
    await page.waitForSelector('#setup-body:not([hidden])', { timeout: 10000 });
    // The pane opens on Basics. Alerts is the widest form in the product — eight inputs, two toggles
    // and a select — and is what Part 1 shot, so it is what is measured. PAI_SETUP_TAB shoots another.
    await page.getByRole('button', { name: process.env.PAI_SETUP_TAB || 'Alerts', exact: true }).click();
    await page.waitForTimeout(400);
  }
  await page.waitForTimeout(1200);
  return { browser, page };
}

/* ------------------------------------------------------------------ the measurement */
const COLLECT = () => {
  const sx = window.scrollX, sy = window.scrollY;
  /* Cap height and ascent, measured from the rasterised face rather than assumed from a ratio.
     actualBoundingBoxAscent of "H" IS the cap height in px; fontBoundingBoxAscent puts the
     baseline under a line box's top. Memoised per font shorthand. */
  const _mc = document.createElement('canvas').getContext('2d'), _mm = new Map();
  const metrics = (fw, fs, ff) => {
    const key = `${fw} ${fs}px ${ff}`;
    if (_mm.has(key)) return _mm.get(key);
    _mc.font = key;
    const h = _mc.measureText('H'), x = _mc.measureText('x');
    const m = { cap: Math.round(h.actualBoundingBoxAscent * 100) / 100,
      xh: Math.round(x.actualBoundingBoxAscent * 100) / 100,
      asc: Math.round(h.fontBoundingBoxAscent * 100) / 100,
      desc: Math.round(h.fontBoundingBoxDescent * 100) / 100 };
    _mm.set(key, m); return m;
  };
  const CTRL = new Set(['BUTTON', 'A', 'INPUT', 'SELECT', 'TEXTAREA', 'SUMMARY', 'LABEL']);
  const MEDIA = new Set(['SVG', 'CANVAS', 'IMG', 'VIDEO', 'PICTURE']);
  const els = [], lines = [];
  /* DOM order, which is what T6 compares position against. querySelectorAll is document order, so
   * the index a walk assigns IS the DOM order; it is recorded rather than reconstructed later,
   * because a later sort loses it. */
  let domIndex = 0;
  for (const el of document.querySelectorAll('*')) {
    domIndex++;
    const tag = el.tagName.toUpperCase();
    if (el.ownerSVGElement) continue;                    // svg internals draw as one hatched box
    if (tag === 'SCRIPT' || tag === 'STYLE' || tag === 'LINK' || tag === 'HEAD') continue;
    const cs = getComputedStyle(el);
    if (cs.display === 'none' || cs.visibility === 'hidden' || +cs.opacity === 0) continue;
    const r = el.getBoundingClientRect();
    if (r.width <= 0 || r.height <= 0) continue;
    const n = v => Math.round(parseFloat(v) * 100) / 100 || 0;
    els.push({
      tag, id: el.id || null,
      cls: (el.getAttribute('class') || '').split(/\s+/).filter(Boolean).slice(0, 4).join(' ') || null,
      role: el.getAttribute('role') || null,
      dc: el.getAttribute('data-component') || null,
      db: el.getAttribute('data-band') || null,
      dcard: el.getAttribute('data-card') || null,
      /* The four attributes the redesign's targets are written in terms of. They are read here
       * whether or not the page under test carries any of them: the shipped page carries none, and
       * a baseline of zero is a measurement. T3 counts data-kind; T4 pairs data-num with
       * data-cmp; T5 pairs data-component with data-ref. */
      dkind: el.getAttribute('data-kind') || null,
      drole: el.getAttribute('data-role') || null,
      dnum: el.hasAttribute('data-num') ? (el.getAttribute('data-num') || '') : null,
      dcmp: el.hasAttribute('data-cmp') ? (el.getAttribute('data-cmp') || '') : null,
      dref: el.getAttribute('data-ref') || null,
      dom: domIndex,
      /* Whether an SVG names itself. T9 asks that every one is named or hidden; the shipped page
       * was measured on this by axe and this records it per element rather than per page. */
      named: tag === 'SVG'
        ? (el.getAttribute('aria-hidden') === 'true' ? 'hidden'
          : (el.getAttribute('aria-label') || el.querySelector(':scope > title') ? 'named' : 'no'))
        : null,
      /* Inherited, not own: the hero's ground is an <img> inside <div class="bg" aria-hidden>, so
       * asking the image alone says it carries a reading when the page has said it does not. */
      hidden: !!el.closest('[aria-hidden="true"]'),
      x: Math.round((r.x + sx) * 100) / 100, y: Math.round((r.y + sy) * 100) / 100,
      w: Math.round(r.width * 100) / 100, h: Math.round(r.height * 100) / 100,
      mt: n(cs.marginTop), mr: n(cs.marginRight), mb: n(cs.marginBottom), ml: n(cs.marginLeft),
      pt: n(cs.paddingTop), pr: n(cs.paddingRight), pb: n(cs.paddingBottom), pl: n(cs.paddingLeft),
      rg: n(cs.rowGap), cg: n(cs.columnGap),
      fs: n(cs.fontSize), fw: cs.fontWeight, lh: cs.lineHeight === 'normal' ? 'normal' : n(cs.lineHeight),
      ff: (cs.fontFamily || '').split(',')[0].replace(/["']/g, ''),
      z: cs.zIndex, pos: cs.position, disp: cs.display,
      br: cs.borderRadius, minh: cs.minHeight,
      bw: [cs.borderTopWidth, cs.borderRightWidth, cs.borderBottomWidth, cs.borderLeftWidth]
        .map(v => Math.round(parseFloat(v) * 100) / 100 || 0).join(' '),
      gtc: cs.gridTemplateColumns && cs.gridTemplateColumns !== 'none' ? cs.gridTemplateColumns : null,
      kind: MEDIA.has(tag) ? 'media' : CTRL.has(tag) || el.getAttribute('role') === 'button' ? 'control' : 'box',
      depth: (() => { let d = 0, p = el; while ((p = p.parentElement)) d++; return d; })(),
      kids: el.children.length,
      hasText: [...el.childNodes].some(c => c.nodeType === 3 && c.nodeValue.trim()),
    });
  }
  // text line boxes, from the real ranges
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  while (walker.nextNode()) {
    const t = walker.currentNode, s = (t.nodeValue || '').replace(/\s+/g, ' ').trim();
    if (!s) continue;
    const p = t.parentElement; if (!p) continue;
    const cs = getComputedStyle(p);
    if (cs.display === 'none' || cs.visibility === 'hidden' || +cs.opacity === 0) continue;
    const range = document.createRange(); range.selectNodeContents(t);
    const rects = [...range.getClientRects()].filter(r => r.width > 0 && r.height > 0);
    if (!rects.length) continue;
    // characters per line: exact for a wrapping block, by finding the break offsets
    let cpl = null;
    if (rects.length > 1 && s.length >= 40) {
      cpl = []; let last = 0, line = 0;
      for (let i = 1; i <= t.nodeValue.length; i++) {
        const rr = document.createRange();
        rr.setStart(t, i - 1); rr.setEnd(t, i);
        const b = rr.getClientRects()[0]; if (!b) continue;
        const which = rects.findIndex(x => b.top >= x.top - 1 && b.bottom <= x.bottom + 1);
        if (which > line) { cpl.push(i - 1 - last); last = i - 1; line = which; }
      }
      cpl.push(t.nodeValue.length - last);
      cpl = cpl.map(c => Math.max(0, c));
    }
    const _fs = parseFloat(cs.fontSize);
    const _m = metrics(cs.fontWeight, _fs, cs.fontFamily);
    for (const r of rects) lines.push({
      x: Math.round((r.x + sx) * 100) / 100, y: Math.round((r.y + sy) * 100) / 100,
      w: Math.round(r.width * 100) / 100, h: Math.round(r.height * 100) / 100,
      cap: _m.cap, base: Math.round((r.y + sy + _m.asc) * 100) / 100,
      fs: Math.round(_fs * 100) / 100, fw: cs.fontWeight,
      lh: cs.lineHeight === 'normal' ? 'normal' : Math.round(parseFloat(cs.lineHeight) * 100) / 100,
      ff: (cs.fontFamily || '').split(',')[0].replace(/["']/g, ''),
      tt: cs.textTransform, chars: s.length, nlines: rects.length, cpl,
      owner: (p.tagName + (p.id ? '#' + p.id : '') + (p.className && typeof p.className === 'string' ? '.' + p.className.split(/\s+/)[0] : '')),
      text: s.slice(0, 90),
    });
  }
  // the accessibility heading outline, as the browser sees it
  const headings = [...document.querySelectorAll('h1,h2,h3,h4,h5,h6,[role="heading"]')]
    .filter(h => h.getBoundingClientRect().height > 0)
    .map(h => ({ lvl: +(h.getAttribute('aria-level') || h.tagName[1] || 0), tag: h.tagName,
      fs: parseFloat(getComputedStyle(h).fontSize), y: Math.round(h.getBoundingClientRect().y + sy),
      text: (h.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 70) }));
  const landmarks = [...document.querySelectorAll('header,nav,main,section,footer,aside,form,[role]')]
    .filter(l => l.getBoundingClientRect().height > 0)
    .map(l => ({ tag: l.tagName, role: l.getAttribute('role'), id: l.id || null,
      label: l.getAttribute('aria-label') || null }));
  return {
    doc: { w: document.documentElement.scrollWidth, h: document.documentElement.scrollHeight,
      vw: innerWidth, vh: innerHeight },
    els, lines, headings, landmarks,
  };
};

/* ------------------------------------------------------------------ the drawing */
function wireHTML(data, guides) {
  const { doc, els, lines } = data;
  const edges = guides ? sharedEdges(els) : [];
  const parts = [];
  for (const e of els) {
    if (e.kind === 'media') parts.push(
      `<i class="hatch" style="left:${e.x}px;top:${e.y}px;width:${e.w}px;height:${e.h}px"></i>`);
    else if (e.kind === 'control') parts.push(
      `<i class="ctrl" style="left:${e.x}px;top:${e.y}px;width:${e.w}px;height:${e.h}px"></i>`);
  }
  for (const l of lines) {
    const h = Math.max(2, Math.min(l.h * 0.62, l.fs * 0.72));
    parts.push(`<i class="bar" style="left:${l.x}px;top:${l.y + (l.h - h) / 2}px;width:${l.w}px;height:${h}px"></i>`);
  }
  for (const x of edges) parts.push(`<i class="guide" style="left:${x}px;height:${doc.h}px"></i>`);
  return `<!doctype html><meta charset="utf-8"><style>
  html,body{margin:0;padding:0;background:#fff}
  body{width:${doc.w}px;height:${doc.h}px;position:relative}
  i{position:absolute;display:block}
  .bar{background:#b4b4b4}
  .ctrl{border:1px solid #222;background:transparent}
  .hatch{border:1px solid #555;background:repeating-linear-gradient(45deg,#00000014 0 4px,#0000 4px 8px)}
  .guide{width:1px;top:0;background:#e0322f;opacity:.85}
  </style><body>${parts.join('')}</body>`;
}

function sharedEdges(els) {
  const c = new Map();
  for (const e of els) { const k = Math.round(e.x); c.set(k, (c.get(k) || 0) + 1); }
  return [...c.entries()].filter(([, n]) => n >= 3).map(([x]) => x).sort((a, b) => a - b);
}

async function draw(browser, data, file, guides) {
  const p = await browser.newPage({ viewport: { width: Math.min(data.doc.w, 2000), height: 900 },
    deviceScaleFactor: 1 });
  await p.setContent(wireHTML(data, guides), { waitUntil: 'load' });
  await p.screenshot({ path: file, fullPage: true });
  await p.close();
}

/* ------------------------------------------------------------------ commands */
async function render(names) {
  const all = jobs();
  const want = names[0] === 'all' ? all : all.filter(j => names.includes(j.name));
  if (!want.length) { console.error('no such job:', names.join(' ')); process.exit(2); }
  for (const j0 of want) {
    // A live render measures different code, so it must never land on the same filename.
    // PAI_TAG does the same for a drawing captured in more than one state.
    const job = tagged(j0);
    let h;
    try {
      h = await open(job);
      const data = await h.page.evaluate(COLLECT);
      data.job = { ...job, commit: '43d508d', fixture: job.state === 'populated' ? FIXTURE : null };
      if (!job.wireOnly) fs.writeFileSync(path.join(OUT, job.name + '.json'), JSON.stringify(data));
      await draw(h.browser, data, path.join(OUT, job.name + '_wire.png'), false);
      if (!job.wireOnly) await draw(h.browser, data, path.join(OUT, job.name + '_guides.png'), true);
      const sf = path.join(OUT, 'sizes.json');
      const sizes = fs.existsSync(sf) ? JSON.parse(fs.readFileSync(sf, 'utf8')) : {};
      sizes[job.name] = { w: data.doc.w, h: data.doc.h };
      fs.writeFileSync(sf, JSON.stringify(sizes, null, 1));
      console.log(`${job.name}  doc ${data.doc.w}x${data.doc.h}  els ${data.els.length}  lines ${data.lines.length}`);
    } catch (e) {
      console.error(`${job.name}  FAILED  ${e.message}`);
    } finally { if (h) await h.browser.close(); }
  }
}

/* Phase 1.3 — step the viewport and record every width at which the skeleton changes. */
async function steps() {
  const out = {};
  for (const view of ['now', 'wall']) {
    const job = { name: view, view, w: 1440, state: 'populated' };
    const h = await open(job);
    const rows = [];
    for (let w = 320; w <= 1920; w += 20) {
      await h.page.setViewportSize({ width: w, height: view === 'wall' ? 1080 : 900 });
      await h.page.waitForTimeout(70);
      rows.push({ w, ...await h.page.evaluate(() => {
        /* Only a RENDERED grid has resolved px tracks. On a hidden view getComputedStyle returns
           the specified value ("minmax(0, 1.5fr) minmax(0, 1fr)"), which counts as four tokens and
           reads as a phantom breakpoint. Rendered or nothing. */
        const cols = sel => {
          const e = document.querySelector(sel);
          if (!e || !e.getClientRects().length) return null;
          const v = getComputedStyle(e).gridTemplateColumns;
          return /px/.test(v) ? v.split(' ').filter(Boolean).length : null;
        };
        const wrap = document.querySelector('.view.on .wrap') || document.querySelector('.wall');
        const wr = wrap ? wrap.getBoundingClientRect() : null;
        const bands = [...document.querySelectorAll('[data-band],.band,.hero')]
          .filter(b => b.getBoundingClientRect().height > 0)
          .map(b => (b.getAttribute('data-band') || b.id || b.className.split(' ')[0]));
        const head = document.querySelector('header .wrap');
        return {
          hero: cols('.hero'), stack: cols('.stack'), sensors: cols('.sensors'),
          idx: cols('.index .row'), setup: cols('.setup'), row2: cols('.wall .row2'),
          cellrow: cols('.cellrow'), askstrip: cols('.askstrip'), unit: cols('.unit'),
          ledger: cols('.ledger .al'), bandhead: cols('.bandhead'),
          net: document.querySelector('svg.net') ? getComputedStyle(document.querySelector('svg.net')).display : null,
          headH: head ? Math.round(head.getBoundingClientRect().height) : null,
          headWrap: head ? (head.scrollHeight > head.clientHeight + 2 ? 'wrapped' : 'one-row') : null,
          brandS: document.querySelector('.brand .s') ? getComputedStyle(document.querySelector('.brand .s')).display : null,
          wrapW: wr ? Math.round(wr.width) : null, wrapX: wr ? Math.round(wr.x) : null,
          docH: document.documentElement.scrollHeight,
          bands: bands.join(','),
        };
      }) });
    }
    out[view] = rows;
    await h.browser.close();
  }
  fs.writeFileSync(path.join(OUT, 'steps.json'), JSON.stringify(out));
  // report only the widths where something changed
  for (const [view, rows] of Object.entries(out)) {
    const keys = Object.keys(rows[0]).filter(k => k !== 'w' && k !== 'docH' && k !== 'wrapW' && k !== 'wrapX');
    console.log(`\n--- ${view} ---`);
    for (let i = 1; i < rows.length; i++) {
      const ch = keys.filter(k => rows[i][k] !== rows[i - 1][k]);
      if (ch.length) console.log(`${rows[i].w}px  ` + ch.map(k => `${k}: ${rows[i - 1][k]} -> ${rows[i][k]}`).join('; '));
    }
  }
}

/* Phase 6.5 — layout with /issues stalled, then released. */
async function stall(name) {
  const job = jobs().find(j => j.name === name) || { name, view: 'now', w: 1440, state: 'populated' };
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: job.w, height: 900 },
    deviceScaleFactor: 1, reducedMotion: 'reduce' });
  let release;
  const gate = new Promise(r => { release = r; });
  await ctx.route('**/*', async route => {
    const u = new URL(route.request().url());
    if (u.origin !== POP) return route.continue();
    // PAI_LIVE=1 measures what the container serves, exactly as `render` does
    let file = null;
    if (process.env.PAI_LIVE !== '1') {
      if (u.pathname === '/' || u.pathname === '/index.html') file = 'index.html';
      else if (u.pathname.startsWith('/static/')) file = u.pathname.slice(8);
    }
    if (file) {
      const p = path.join(STATIC, file);
      if (p && fs.existsSync(p)) return route.fulfill({ status: 200, body: fs.readFileSync(p),
        headers: { 'content-type': MIME[path.extname(p)] || 'application/octet-stream' } });
    }
    // the document and its companions are not API calls and must not wait on the gate
    if (process.env.PAI_LIVE === '1' && (u.pathname === '/' || /^\/static\//.test(u.pathname)))
      return route.continue();
    await gate;                       // every API call waits
    // Offline node endpoints — see "the node, without a node" above, and open()'s own call site.
    // Served AFTER the gate, not before: stall measures what moves when these answers arrive late,
    // and answering early from here would be a different experiment from answering early from POP.
    if (process.env.PAI_LIVE !== '1' && await serveNodeAPI(route, u)) return;
    return route.continue();
  });
  const page = await ctx.newPage();
  await page.goto(POP + `/?fixture=${FIXTURE}`, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(1500);
  const before = await page.evaluate(BOXES);
  release();
  await page.waitForTimeout(2500);
  const after = await page.evaluate(BOXES);
  const moved = [];
  for (const [k, v] of Object.entries(before)) if (after[k]) {
    const d = Math.round(Math.abs(after[k].y - v.y));
    if (d > 0) moved.push({ el: k, before: Math.round(v.y), after: Math.round(after[k].y), dy: d });
  }
  const out = { job: job.name, before, after, moved: moved.sort((a, b) => b.dy - a.dy),
    beforeH: before.__docH, afterH: after.__docH };
  const suffix = process.env.PAI_LIVE === '1' ? '_live' : '';
  fs.writeFileSync(path.join(OUT, `stall_${job.name}${suffix}.json`), JSON.stringify(out));
  console.log(`doc height ${before.__docH} -> ${after.__docH}`);
  for (const m of moved.slice(0, 20)) console.log(`  ${m.el}: y ${m.before} -> ${m.after}  (${m.dy} px)`);
  await browser.close();
}
const BOXES = () => {
  const o = { __docH: document.documentElement.scrollHeight };
  for (const el of document.querySelectorAll('header,nav,main,section[id],.hero,.index,#bands,#place,#loop,#figures,.band')) {
    const r = el.getBoundingClientRect(); if (!r.height) continue;
    const k = el.tagName + (el.id ? '#' + el.id : '') + (el.className && typeof el.className === 'string' ? '.' + el.className.split(/\s+/)[0] : '');
    if (!o[k]) o[k] = { y: r.y + scrollY, h: r.height };
  }
  return o;
};

/* The header's shape against the node's own data (S-11).
 *
 * The header is a wrapping flex row, so it reflows where the CONTENT stops fitting, not at a width
 * anything declares. That makes its shape a function of the node's name and place string. This
 * steps 320 -> 1400 in 10 px steps for several node shapes and reports the widths at which the row
 * structure changes, and which of those changes make the header TALLER as the viewport widens.
 *
 * The name and place are set on the rendered page rather than on the node: they are the two strings
 * a node's own config supplies, and nothing on either container is touched.
 */
const HEADER_CASES = [
  ['node #1, as the fixture ships it', null, null],
  ["node #1's registry place, 37 chars", null, 'Ungasan, Badung, Bali, ID · community'],
  ['a long place line, 51 chars', null, 'Kelurahan Ungasan, Kabupaten Badung, Bali, Indonesia'],
  ['a very long place line, 78 chars', null,
    'Banjar Kelod, Kelurahan Ungasan, Kecamatan Kuta Selatan, Kabupaten Badung, Bali'],
  ['a longer node name', 'meaningful-design-rooftop', 'Ungasan, Badung, Bali, ID · community'],
  ['both long', 'meaningful-design-group-rooftop',
    'Kelurahan Ungasan, Kabupaten Badung, Bali, Indonesia'],
];
const HEADER_SHAPE = () => {
  const wrap = document.querySelector('header .wrap');
  const kids = [...wrap.children].map(e => {
    const b = e.getBoundingClientRect(); return { top: b.top, bot: b.bottom };
  });
  const lines = [];
  for (const k of kids.sort((a, b) => a.top - b.top)) {
    const l = lines.find(L => k.top < L.bot - 2 && k.bot > L.top + 2);
    if (l) { l.top = Math.min(l.top, k.top); l.bot = Math.max(l.bot, k.bot); } else lines.push({ ...k });
  }
  return { rows: lines.length, h: Math.round(wrap.getBoundingClientRect().height) };
};
async function header() {
  const browser = await chromium.launch();
  const rows = [];
  for (const [label, name, place] of HEADER_CASES) {
    const p = await browser.newPage({ viewport: { width: 1920, height: 900 }, deviceScaleFactor: 1 });
    await p.goto(POP + `/?fixture=${FIXTURE}`, { waitUntil: 'networkidle' });
    await p.waitForTimeout(1400);
    const place_ = await p.evaluate(([n, pl]) => {
      if (n) { const h = document.querySelector('.brand h1, #nodename'); if (h) h.textContent = n; }
      const s = document.getElementById('nodeplace');
      if (pl) s.textContent = pl;
      return { px: Math.round(s.getBoundingClientRect().width),
        clipped: s.scrollWidth > s.clientWidth, text: s.textContent.length };
    }, [name, place]);
    const flips = [], grew = [];
    let prev = null;
    for (let w = 320; w <= 1400; w += 10) {
      await p.setViewportSize({ width: w, height: 900 });
      await p.waitForTimeout(40);
      const r = await p.evaluate(HEADER_SHAPE);
      const key = `${r.rows}/${r.h}`;
      if (prev && key !== prev) {
        flips.push(w);
        if (r.h > +prev.split('/')[1]) grew.push(w);
      }
      prev = key;
    }
    rows.push([label, place_.text, place_.px + (place_.clipped ? ' clipped' : ''),
      flips.join(' ') || 'none', grew.join(' ') || '—']);
    await p.close();
  }
  console.log(tbl(['node', 'place chars', 'place px', 'the header reflows at', 'and grows at'], rows));
  await browser.close();
}

/* Contact sheet: one view at every measured width, side by side, at ONE scale so the widths can
 * be compared as widths. Drawn from the wireframes, not the screenshots. */
async function sheets() {
  const browser = await chromium.launch();
  const sizes = JSON.parse(fs.readFileSync(path.join(OUT, 'sizes.json'), 'utf8'));
  for (const v of VIEWS) {
    const names = WIDTHS.map(w => `${v}_populated_${w}`)
      .concat(v === 'wall' ? ['wall_populated_1920_dark'] : [])
      .filter(n => fs.existsSync(path.join(OUT, n + '_wire.png')));
    if (!names.length) continue;
    const sw = names.reduce((a, n) => a + sizes[n].w, 0);
    const mh = Math.max(...names.map(n => sizes[n].h));
    const sc = Math.min(2300 / sw, 4600 / mh);
    const html = `<!doctype html><meta charset="utf-8"><style>
      body{margin:0;background:#efefef;font:11px/1.4 ui-monospace,monospace;display:flex;gap:12px;
        padding:12px;align-items:flex-start}
      figure{margin:0;background:#fff;border:1px solid #999}
      img{display:block;width:100%}figcaption{padding:4px 6px;border-top:1px solid #999}
      </style><body>${names.map(n => `<figure style="flex:0 0 ${Math.round(sizes[n].w * sc)}px">`
        + `<img src="${n}_wire.png"><figcaption>${n} — ${sizes[n].w} x ${Math.round(sizes[n].h)} px`
        + ` (drawn at ${(sc * 100).toFixed(0)} %)</figcaption></figure>`).join('')}</body>`;
    const f = path.join(OUT, `_sheet_${v}.html`);
    fs.writeFileSync(f, html);
    const p = await browser.newPage({ viewport: { width: 2400, height: 900 }, deviceScaleFactor: 1 });
    await p.goto('file://' + f, { waitUntil: 'load' });
    await p.screenshot({ path: path.join(OUT, `${v}_contact.png`), fullPage: true });
    await p.close();
    fs.unlinkSync(f);
    console.log(`${v}_contact.png  ${names.length} widths at ${(sc * 100).toFixed(0)} %`);
  }
  await browser.close();
}

/* ======================================================================== ANALYSE
 * Every table in UX_REVIEW_2026-09_skeleton.md comes out of one of these. They read the JSON the
 * render step wrote and print a markdown table; nothing here touches the browser or the node.
 */
const VIEW_ORDER = ['now', 'network', 'setup', 'setup-unlocked', 'wall', 'arrange'];
const load = n => JSON.parse(fs.readFileSync(path.join(OUT, n + '.json'), 'utf8'));
const sets = () => fs.readdirSync(OUT)
  .filter(f => /_populated_\d+\.json$/.test(f) && !f.startsWith('stall_'))
  .map(f => f.replace(/\.json$/, ''))
  .sort((a, b) => {
    const [va, wa] = [a.replace(/_populated_.*/, ''), +a.match(/(\d+)/)[1]];
    const [vb, wb] = [b.replace(/_populated_.*/, ''), +b.match(/(\d+)/)[1]];
    return VIEW_ORDER.indexOf(va) - VIEW_ORDER.indexOf(vb) || wa - wb;
  });
const r1 = v => Math.round(v * 10) / 10;
const tbl = (head, rows) => [`| ${head.join(' | ')} |`,
  `|${head.map(() => '---').join('|')}|`, ...rows.map(r => `| ${r.join(' | ')} |`)].join('\n');
const has = (e, c) => e.cls && e.cls.split(' ').includes(c);
const pick = (d, c) => d.els.filter(e => has(e, c));
const one = (d, c) => pick(d, c)[0] || null;

/* 1.1 / 1.4 — the grid as rendered */
function aGrid() {
  const rows = [];
  for (const n of sets()) {
    const d = load(n), view = n.replace(/_populated_.*/, ''), w = +n.match(/(\d+)$/)[1];
    // the wall has no .wrap: it is its own padded box, so that is the container to measure
    const wraps = pick(d, 'wrap').filter(e => e.h > 0);
    const body = view === 'wall' ? d.els.find(e => has(e, 'wall') && e.tag === 'DIV')
      : (wraps.find(e => e.y > 40) || wraps[0]);
    const hdr = d.els.find(e => e.tag === 'HEADER');
    const main = d.els.find(e => e.tag === 'MAIN');
    // the view's primary grid
    const prim = { now: '.hero', network: '.grid', setup: '.gate', 'setup-unlocked': '.setup',
      wall: '.row2', arrange: '.hero' }[view];
    const g = d.els.find(e => has(e, prim.replace('.', '')) && e.gtc);
    const tracks = g ? g.gtc.split(/\s+(?![^(]*\))/).filter(Boolean) : [];
    rows.push([view, w,
      g ? tracks.length : '—',
      g ? tracks.map(t => Math.round(parseFloat(t))).join(' + ') : '—',
      g ? r1(g.cg) : '—',
      body ? r1(body.x + body.pl) : '—',
      body ? r1(body.w - body.pl - body.pr) : '—',
      hdr ? `${r1(hdr.h)} ${hdr.pos}` : '—',
      main ? r1(main.y) : '—',
      r1(d.doc.h)]);
  }
  console.log(tbl(['view', 'width', 'cols', 'track px', 'gutter', 'left margin', 'content w',
    'header h/pos', 'main top', 'doc h'], rows));
}

/* 2.1 — the spacing histogram */
function aSpacing(perView) {
  const all = new Map(), byView = new Map();
  const where = new Map();                     // value -> set of "view .class prop"
  for (const n of sets()) {
    const d = load(n), view = n.replace(/_populated_.*/, '');
    const m = byView.get(view) || new Map(); byView.set(view, m);
    for (const e of d.els) for (const [k, v] of [['mt', e.mt], ['mr', e.mr], ['mb', e.mb], ['ml', e.ml],
      ['pt', e.pt], ['pr', e.pr], ['pb', e.pb], ['pl', e.pl], ['rg', e.rg], ['cg', e.cg]]) {
      if (!v) continue;
      const val = Math.round(v * 10) / 10;
      all.set(val, (all.get(val) || 0) + 1); m.set(val, (m.get(val) || 0) + 1);
      const key = `${e.cls || e.tag.toLowerCase()}·${k}`;
      if (!where.has(val)) where.set(val, new Set());
      if (where.get(val).size < 6) where.get(val).add(key);
    }
  }
  const on4 = v => Math.abs(v - Math.round(v / 4) * 4) < 0.01;
  const vals = [...all.entries()].sort((a, b) => a[0] - b[0]);
  const off = vals.filter(([v]) => !on4(v));
  console.log(`distinct values: ${vals.length}; on the 4 pt measure: ${vals.length - off.length}; off it: ${off.length}`);
  console.log(`instances: ${[...all.values()].reduce((a, b) => a + b, 0)}, of which off-measure: ${off.reduce((a, b) => a + b[1], 0)}`);
  console.log('\n**Every distinct value, and how often it appears**\n');
  console.log(tbl(['px', 'n', 'on 4 pt', 'where (first few)'],
    vals.map(([v, n]) => [v, n, on4(v) ? '✓' : '✗', [...(where.get(v) || [])].join(', ')])));
  if (perView) {
    console.log('\n**Per view**\n');
    console.log(tbl(['view', 'distinct', 'off-measure distinct', 'off-measure instances'],
      [...byView.entries()].map(([v, m]) => {
        const vs = [...m.entries()], o = vs.filter(([x]) => !on4(x));
        return [v, vs.length, o.length, o.reduce((a, b) => a + b[1], 0)];
      })));
  }
}

/* 2.2 — the recurring vertical relationships */
function aRhythm() {
  const rel = new Map();
  const add = (name, view, w, px, what) => {
    const k = name; if (!rel.has(k)) rel.set(k, []);
    rel.get(k).push({ view, w, px: Math.round(px * 10) / 10, what });
  };
  for (const n of sets()) {
    const d = load(n), view = n.replace(/_populated_.*/, ''), w = +n.match(/(\d+)$/)[1];
    const by = c => pick(d, c);
    // band to band: the gap between one .band's bottom and the next .band's top
    const bands = d.els.filter(e => has(e, 'band') || has(e, 'hero')).sort((a, b) => a.y - b.y);
    for (let i = 1; i < bands.length; i++) {
      const g = bands[i].y - (bands[i - 1].y + bands[i - 1].h);
      if (g >= 0 && g < 200) add('band to band (box gap)', view, w, g, `${bands[i - 1].cls} -> ${bands[i].cls}`);
      // the real separation is the next band's own padding-top, not a margin between boxes
      add('band to band (the next band pads itself)', view, w, bands[i].pt, bands[i].id || bands[i].cls);
    }
    // kicker (.k) to the title/sentence under it, inside the same parent box
    for (const box of [...by('hero'), ...by('bandhead'), ...by('wall')]) {
      const k = d.els.find(e => has(e, 'k') && e.y >= box.y && e.y < box.y + box.h && e.x >= box.x);
      const big = d.els.find(e => has(e, 'big') && e.y > (k ? k.y : -1) && e.y < box.y + box.h);
      if (k && big) add('kicker to sentence', view, w, big.y - (k.y + k.h), box.cls);
      // only when the two stack: in a .bandhead above 900 the sub sits in column two, beside the
      // title, and the vertical distance between them is not a rhythm at all
      const why = d.els.find(e => has(e, 'why') && big && e.y > big.y && e.y < box.y + box.h
        && Math.abs(e.x - big.x) < 2);
      if (big && why) add('sentence to why', view, w, why.y - (big.y + big.h), box.cls);
    }
    // why/body to the source line under it
    for (const col of by('col')) {
      const v = d.els.find(e => has(e, 'v') && e.y >= col.y && e.y < col.y + col.h);
      const src = d.els.find(e => has(e, 'src') && e.y >= col.y && e.y < col.y + col.h);
      if (v && src) add('value to source line', view, w, src.y - (v.y + v.h), 'stack .col');
    }
    // card to card in a row
    const cards = by('card').concat(by('sensor')).sort((a, b) => a.y - b.y || a.x - b.x);
    for (let i = 1; i < cards.length; i++)
      if (Math.abs(cards[i].y - cards[i - 1].y) < 2) {
        const g = cards[i].x - (cards[i - 1].x + cards[i - 1].w);
        if (g >= 0 && g < 120) add('card to card in a row', view, w, g, cards[i].cls);
      }
    // hero to index
    const hero = one(d, 'hero'), idx = one(d, 'index');
    if (hero && idx) add('hero to index', view, w, idx.y - (hero.y + hero.h), '');
  }
  for (const [name, xs] of rel) {
    const vals = [...new Set(xs.map(x => x.px))].sort((a, b) => a - b);
    console.log(`\n**${name}** — ${vals.length} distinct value${vals.length === 1 ? '' : 's'}: ${vals.join(', ')} px`);
    const byVal = new Map();
    for (const x of xs) { const k = x.px; if (!byVal.has(k)) byVal.set(k, []); byVal.get(k).push(`${x.view}@${x.w}${x.what ? ' ' + x.what : ''}`); }
    console.log(tbl(['px', 'n', 'occurrences (first 5)'],
      [...byVal.entries()].sort((a, b) => a[0] - b[0])
        .map(([v, o]) => [v, o.length, o.slice(0, 5).join('; ')])));
  }
}

/* 2.3 — line length and line height on every wrapping block */
function aLines() {
  const rows = [];
  for (const n of sets()) {
    const d = load(n), view = n.replace(/_populated_.*/, ''), w = +n.match(/(\d+)$/)[1];
    const seen = new Set();
    for (const l of d.lines) {
      if (!l.cpl || l.cpl.length < 2) continue;
      const key = view + w + l.owner + l.text.slice(0, 20);
      if (seen.has(key)) continue; seen.add(key);
      const mx = Math.max(...l.cpl), md = Math.round(l.cpl.reduce((a, b) => a + b, 0) / l.cpl.length);
      const floor = w <= 560 ? [35, 60] : [60, 75];
      const lh = l.lh === 'normal' ? null : Math.round(l.lh / l.fs * 100) / 100;
      /* The brief scopes line-height to running prose: sentences, why-paragraphs, help lines and
         the report. A kicker, a chip, a numeral and a display sentence are not body text and a
         1.5 floor does not apply to them. */
      const PROSE = /\.(why|sub|help|note|rep|line|txt|story)\b/;
      const DISPLAY = /\.(big|k|chip|num|mono|state|iss|lab|t|yr|tally|pill|src|cap|when|st)\b/;
      const prose = !DISPLAY.test(l.owner)
        && (PROSE.test(l.owner) || /^(P|TD|LI)$/.test(l.owner.split('.')[0].split('#')[0]));
      rows.push([view, w, l.owner, l.cpl.length, md, mx,
        mx > floor[1] ? `over ${floor[1]}` : md < floor[0] ? `under ${floor[0]}` : 'in band',
        l.fs, lh === null ? 'normal' : lh,
        !prose ? 'n/a — not prose' : lh !== null && (lh < 1.5 || lh > 1.75) ? '✗' : '✓',
        l.text.slice(0, 44)]);
    }
  }
  console.log(tbl(['view', 'w', 'block', 'lines', 'med cpl', 'max cpl', 'line-length-control',
    'px', 'lh', 'line-height', 'text'], rows));
}

/* 3 — alignment */
function aAlign() {
  for (const n of sets()) {
    const d = load(n), view = n.replace(/_populated_.*/, ''), w = +n.match(/(\d+)$/)[1];
    const c = new Map();
    for (const e of d.els) { const k = Math.round(e.x); c.set(k, (c.get(k) || 0) + 1); }
    const shared = [...c.entries()].filter(([, k]) => k >= 3).sort((a, b) => b[1] - a[1]);
    if (!shared.length) { console.log(`\n### ${view} @ ${w} — no edge shared by three`); continue; }
    const dom = shared[0];
    console.log(`\n### ${view} @ ${w} — dominant left edge **${dom[0]} px** (${dom[1]} elements); ${shared.length} edges shared by three or more`);
    console.log('edges: ' + shared.sort((a, b) => a[0] - b[0]).map(([x, k]) => `${x}(${k})`).join(' '));
    // near-misses: an element within 12 px of the dominant edge but not on it
    const near = d.els.filter(e => { const dx = e.x - dom[0]; return dx !== 0 && Math.abs(dx) > 2 && Math.abs(dx) <= 12; })
      .map(e => [`${e.tag}${e.id ? '#' + e.id : ''}${e.cls ? '.' + e.cls.split(' ')[0] : ''}`,
        r1(e.x), r1(e.x - dom[0])]);
    if (near.length) {
      const byEl = new Map();
      for (const [k, x, dx] of near) if (!byEl.has(k)) byEl.set(k, [x, dx]);
      console.log('\n' + tbl(['element', 'actual x', 'delta from dominant'],
        [...byEl.entries()].map(([k, [x, dx]]) => [k, x, (dx > 0 ? '+' : '') + dx])));
    }
  }
}

/* 4.1 — the type scale actually in use */
function aType() {
  const combos = new Map();
  for (const n of sets()) {
    const d = load(n);
    for (const l of d.lines) {
      const lh = l.lh === 'normal' ? 'normal' : Math.round(l.lh * 10) / 10;
      const k = `${l.fs}|${l.fw}|${lh}|${l.ff}`;
      if (!combos.has(k)) combos.set(k, { fs: l.fs, fw: l.fw, lh, ff: l.ff, n: 0, who: new Set() });
      const c = combos.get(k); c.n++; if (c.who.size < 5) c.who.add(l.owner);
    }
  }
  const rows = [...combos.values()].sort((a, b) => b.fs - a.fs || a.fw - b.fw)
    .map(c => [c.fs, c.fw, c.lh, c.ff, c.n, [...c.who].join(', ')]);
  console.log(`**${rows.length} distinct size x weight x line-height x family combinations.**\n`);
  console.log(tbl(['px', 'weight', 'line-height', 'family', 'instances', 'on (first few)'], rows));
  // sizes that carry more than one weight, and weights that carry more than one size
  const bySize = new Map();
  for (const c of combos.values()) {
    if (!bySize.has(c.fs)) bySize.set(c.fs, new Set());
    bySize.get(c.fs).add(c.fw + '/' + c.ff);
  }
  console.log('\n**One size, more than one meaning**\n');
  console.log(tbl(['px', 'weight/family combinations on it'],
    [...bySize.entries()].filter(([, s]) => s.size > 1).sort((a, b) => b[0] - a[0])
      .map(([fs, s]) => [fs, [...s].join(', ')])));
}

/* 4.2 — heading outline as the browser sees it, against the visual outline */
function aHeadings() {
  for (const n of sets()) {
    const d = load(n), view = n.replace(/_populated_.*/, ''), w = +n.match(/(\d+)$/)[1];
    if (w !== 1440 && w !== 390) continue;
    const big = d.lines.filter(l => l.fs >= 20).sort((a, b) => a.y - b.y)
      .map(l => ({ y: Math.round(l.y), fs: l.fs, tag: l.owner.split('.')[0].split('#')[0], text: l.text.slice(0, 46) }));
    console.log(`\n### ${view} @ ${w}`);
    console.log('a11y outline: ' + (d.headings.length
      ? d.headings.map(h => `h${h.lvl}@${h.y} "${h.text.slice(0, 34)}"`).join(' · ') : '**none**'));
    console.log('\n' + tbl(['y', 'px', 'element', 'reads as a title'],
      big.slice(0, 14).map(b => [b.y, b.fs, b.tag,
        d.headings.some(h => Math.abs(h.y - b.y) < 40) ? 'yes — is a heading' : '**div/p, not a heading**'])));
  }
}

/* 4.3 / 4.4 — reading order and weight in the first viewport */
function aOrder() {
  for (const n of sets()) {
    const d = load(n), view = n.replace(/_populated_.*/, ''), w = +n.match(/(\d+)$/)[1];
    if (view !== 'now' || (w !== 390 && w !== 1440)) continue;
    const vh = d.doc.vh;
    const fold = d.els.filter(e => e.y < vh && e.y + e.h > 0 && e.w * e.h > 400);
    const named = fold.filter(e => e.hasText || e.kind !== 'box' || e.dc);
    const dom = named.map((e, i) => ({ ...e, dom: i }));
    // by position means the way a reader meets it: rows first, then left to right inside a row.
    // A two-pixel difference in y between two things on the same line is not an order.
    const bypos = [...dom].sort((a, b) => (Math.abs(a.y - b.y) <= 8 ? a.x - b.x : a.y - b.y));
    console.log(`\n### Now @ ${w} — the first ${vh} px, ${fold.length} elements`);
    console.log(tbl(['by position', 'element', 'DOM order', 'diverges'],
      bypos.slice(0, 16).map((e, i) => [i + 1,
        `${e.tag}${e.id ? '#' + e.id : ''}${e.cls ? '.' + e.cls.split(' ')[0] : ''} (${r1(e.y)})`,
        e.dom + 1, i === e.dom ? '' : '**yes**'])));
    /* Area clipped to the fold, and scaffold dropped: a box whose area is within 15 % of a box it
       contains is that box's wrapper, not a mark on the screen. */
    const ca = e => Math.max(0, Math.min(vh, e.y + e.h) - Math.max(0, e.y)) * Math.min(e.w, w);
    const SCAFFOLD = e => ['HTML', 'BODY', 'MAIN'].includes(e.tag)
      || has(e, 'wrap') || (e.tag === 'SECTION' && has(e, 'view'));
    const cand = fold.map((e, i) => ({ ...e, ca: ca(e), i })).sort((a, b) => b.ca - a.ca);
    const area = cand.filter(e => !SCAFFOLD(e) && !cand.some(o => o.i > e.i && o.ca >= e.ca * 0.85
      && o.x >= e.x - 1 && o.y >= e.y - 1
      && o.x + o.w <= e.x + e.w + 1 && o.y + o.h <= e.y + e.h + 1)).slice(0, 8);
    console.log('\n**Top elements by pixel area in the first viewport**\n');
    console.log(tbl(['element', 'w x h', 'px²', 'share of fold'],
      area.map(e => [`${e.tag}${e.id ? '#' + e.id : ''}${e.cls ? '.' + e.cls.split(' ')[0] : ''}`,
        `${r1(e.w)} x ${r1(e.h)}`, Math.round(e.ca),
        (100 * e.ca / (w * vh)).toFixed(1) + '%'])));
    // the largest piece of TEXT in the fold
    const t = d.lines.filter(l => l.y < vh).sort((a, b) => b.fs - a.fs)[0];
    if (t) console.log(`\nLargest type in the fold: **${t.fs} px** ${t.fw} on ${t.owner} — "${t.text.slice(0, 50)}"`);
  }
}

/* 5.1 / 5.2 / 5.3 — distribution and density */
function aDist() {
  const rows = [], dens = [];
  for (const n of [...sets(), 'wall_populated_1920_dark']) {
    const d = load(n), view = n.replace(/_populated_.*/, '') + (/dark/.test(n) ? ' (dark)' : '');
    const w = d.doc.vw;
    const vh = d.doc.vh, foldPx = w * vh;
    const hdr = d.els.find(e => e.tag === 'HEADER');
    const hero = one(d, 'hero');
    const idx = one(d, 'index');
    const firstBand = d.els.filter(e => has(e, 'band') && e.h > 0).sort((a, b) => a.y - b.y)[0];
    const clip = e => e ? Math.max(0, Math.min(vh, e.y + e.h) - Math.max(0, e.y)) * Math.min(e.w, w) : 0;
    /* Marked ground is the UNION of what is drawn, not the sum: a text line inside a bordered
       control is one mark, not two. Rasterised on a 4 px grid over the first viewport. */
    const G = 4, gw = Math.ceil(w / G), gh = Math.ceil(vh / G), grid = new Uint8Array(gw * gh);
    const mark = (x, y, ww, hh) => {
      for (let gy = Math.max(0, Math.floor(y / G)); gy < Math.min(gh, Math.ceil((y + hh) / G)); gy++)
        for (let gx = Math.max(0, Math.floor(x / G)); gx < Math.min(gw, Math.ceil((x + ww) / G)); gx++)
          grid[gy * gw + gx] = 1;
    };
    for (const l of d.lines) if (l.y < vh) mark(l.x, l.y, l.w, l.h);
    for (const e of d.els) if (e.y < vh && (e.kind === 'media' || e.kind === 'control')) mark(e.x, e.y, e.w, e.h);
    const ink = grid.reduce((a, b) => a + b, 0) * G * G;
    rows.push([view, w, (100 * clip(hdr) / foldPx).toFixed(1), (100 * clip(hero) / foldPx).toFixed(1),
      (100 * clip(idx) / foldPx).toFixed(1), (100 * clip(firstBand) / foldPx).toFixed(1),
      (100 * (1 - ink / foldPx)).toFixed(1)]);
    const words = d.lines.filter(l => l.y < vh).reduce((a, l) => a + l.text.split(/\s+/).length, 0);
    dens.push([view, w, d.els.filter(e => e.y < vh).length,
      (1000 * d.els.filter(e => e.y < vh).length / foldPx).toFixed(3), words,
      d.els.length, r1(d.doc.h), (1000 * d.els.length / (w * d.doc.h)).toFixed(3)]);
  }
  console.log('**5.1 — the first viewport, share of its pixels**\n');
  console.log(tbl(['view', 'w', 'header %', 'hero %', 'index %', 'first band %', 'unmarked ground %'], rows));
  console.log('\n**5.3 — density**\n');
  console.log(tbl(['view', 'w', 'els in fold', 'els / 1000 px² (fold)', 'words in fold',
    'els on page', 'doc h', 'els / 1000 px² (page)'], dens));
  // 5.2 band share of the whole page
  console.log('\n**5.2 — what each band takes of the whole page**\n');
  for (const w of [390, 1440]) {
    const d = load(`now_populated_${w}`);
    const bands = d.els.filter(e => has(e, 'band') || has(e, 'hero') || has(e, 'index'))
      .filter(e => e.h > 0).sort((a, b) => a.y - b.y);
    console.log(`\nNow @ ${w} — page ${r1(d.doc.h)} px\n`);
    console.log(tbl(['order', 'band', 'top', 'height', '% of page'],
      bands.map((b, i) => [i + 1, `${b.id ? '#' + b.id : ''}.${(b.cls || '').split(' ')[0]}`,
        r1(b.y), r1(b.h), (100 * b.h / d.doc.h).toFixed(1)])));
  }
}

/* 5.4 — the wall, measured in millimetres */
function aWall() {
  const d = load('wall_populated_1920_dark');
  const MM = 0.63;                            // 1 px at 1920 on a 55-inch 16:9 panel
  const seen = new Set(), rows = [];
  for (const l of d.lines.sort((a, b) => b.cap - a.cap)) {
    const k = l.owner + l.fs; if (seen.has(k)) continue; seen.add(k);
    const mm = l.cap * MM;
    rows.push([l.owner, l.fs, l.cap, mm.toFixed(1), (mm / 3).toFixed(1),
      mm >= 9 ? '✓ 3 m' : mm >= 6 ? `only ${(mm / 3).toFixed(1)} m` : `**only ${(mm / 3).toFixed(1)} m**`,
      l.text.slice(0, 40)]);
  }
  console.log('1920 px wide on a 55-inch 16:9 panel: 1 px = 0.63 mm. The floor is 3 mm of cap height per metre of viewing distance, so 9 mm at three metres.\n');
  console.log(tbl(['element', 'font px', 'cap px', 'cap mm', 'max distance m', 'at 3 m', 'text'], rows));
}

/* 6.1 — the DOM skeleton */
function aDom() {
  const rows = [];
  for (const n of sets()) {
    const d = load(n), view = n.replace(/_populated_.*/, ''), w = +n.match(/(\d+)$/)[1];
    if (w !== 1440) continue;
    const depth = Math.max(...d.els.map(e => e.depth));
    // a wrapper with no layout role: one child, no text of its own, no grid/flex, no border, no padding
    /* A wrapper with no layout role: one child, no text of its own, no grid or flex, no border,
       no padding, not positioned — and not a drawing. An <svg> with one <use> in it is a mark,
       not a box around something. */
    const wrap = d.els.filter(e => e.kind !== 'media' && e.kind !== 'control'
      && e.kids === 1 && !e.hasText && !/grid|flex/.test(e.disp)
      && e.bw === '0 0 0 0' && !e.pt && !e.pb && !e.pl && !e.pr && e.pos === 'static');
    console.log(`\n### ${view} @ ${w}`);
    console.log(`landmarks: ${d.landmarks.filter(l => ['HEADER', 'NAV', 'MAIN', 'FOOTER', 'ASIDE', 'FORM'].includes(l.tag))
      .map(l => l.tag.toLowerCase() + (l.id ? '#' + l.id : '') + (l.label ? ` "${l.label}"` : '')).join(', ') || '**none**'}`);
    console.log(`sections: ${d.landmarks.filter(l => l.tag === 'SECTION').length} · roles: ${[...new Set(d.landmarks.filter(l => l.role).map(l => l.role))].join(', ') || '—'}`);
    console.log(`elements ${d.els.length} · deepest nesting ${depth} · wrappers with no layout role **${wrap.length}**`);
    if (wrap.length) console.log('  ' + wrap.slice(0, 10).map(e => `${e.tag}${e.cls ? '.' + e.cls.split(' ')[0] : ''}@${Math.round(e.y)}`).join(' '));
  }
}

/* 6.2 — the anatomy actually rendered.
 * Ancestry is reconstructed from DOM order + depth: the parent of the element at index i is the
 * nearest earlier element with depth one less. That is exact, and it is the only way to tell a
 * component that BELONGS to a band from one that merely overlaps it on screen. */
function aAnatomy() {
  for (const n of sets()) {
    const d = load(n), view = n.replace(/_populated_.*/, ''), w = +n.match(/(\d+)$/)[1];
    if (w !== 1440) continue;
    const parent = new Array(d.els.length).fill(-1);
    const stack = [];
    d.els.forEach((e, i) => {
      while (stack.length && d.els[stack[stack.length - 1]].depth >= e.depth) stack.pop();
      parent[i] = stack.length ? stack[stack.length - 1] : -1;
      stack.push(i);
    });
    const bandOf = i => { let k = i; while (k >= 0) { const e = d.els[k];
      if (e.db) return e.db;
      if (e.id === 'wallbox' || e.id === 'netbody' || e.id === 'pane') return e.id;
      k = parent[k]; } return '(loose)'; };
    const byBand = new Map();
    d.els.forEach((e, i) => { if (!e.dc) return;
      const b = bandOf(parent[i] >= 0 ? parent[i] : i);
      if (!byBand.has(b)) byBand.set(b, []); byBand.get(b).push(e.dc); });
    console.log(`\n### ${view} @ ${w} — every data-component, in DOM order, by the band that owns it\n`);
    console.log(tbl(['band', 'rendered'], [...byBand.entries()].map(([k, v]) => [k, v.join(' → ')])));
  }
}

/* 6.3 — one component, measured in every view it appears in */
function aComponents() {
  const want = ['pill', 'chip', 'unit', 'card', 'k', 'stamp', 'sensor', 'num', 'btn', 'peer', 'tag'];
  const m = new Map();
  for (const n of sets()) {
    const d = load(n), view = n.replace(/_populated_.*/, ''), w = +n.match(/(\d+)$/)[1];
    if (w !== 1440) continue;
    for (const e of d.els) for (const c of want) if (has(e, c)) {
      const k = c + '|' + view;
      if (!m.has(k)) m.set(k, { c, view, n: 0, pad: new Set(), fs: new Set(), br: new Set(), h: new Set(), bw: new Set() });
      const r = m.get(k); r.n++;
      r.pad.add(`${e.pt} ${e.pr} ${e.pb} ${e.pl}`);
      r.fs.add(e.fs); r.br.add(e.br); r.h.add(Math.round(e.h)); r.bw.add(e.bw);
    }
  }
  const byC = new Map();
  for (const r of m.values()) { if (!byC.has(r.c)) byC.set(r.c, []); byC.get(r.c).push(r); }
  const rows = [];
  for (const [c, rs] of byC) {
    if (rs.length < 2) continue;
    for (const r of rs) rows.push([`.${c}`, r.view, r.n, [...r.pad].join(' / '),
      [...r.fs].join(', '), [...r.br].join(', '), [...r.h].sort((a, b) => a - b).join(', '),
      [...r.bw].join(' / ')]);
    const pads = new Set(rs.flatMap(r => [...r.pad])), fss = new Set(rs.flatMap(r => [...r.fs]));
    rows.push([`**.${c}**`, `**${rs.length} views**`, '', pads.size > 1 ? `**${pads.size} paddings**` : 'one padding',
      fss.size > 1 ? `**${fss.size} sizes**` : 'one size', '', '', '']);
  }
  console.log(tbl(['component', 'view', 'n', 'padding t r b l', 'font px', 'radius', 'heights', 'border w'], rows));
}

/* 6.4 — stacking */
function aStack() {
  const z = new Map(), rows = [];
  for (const n of sets()) {
    const d = load(n), view = n.replace(/_populated_.*/, ''), w = +n.match(/(\d+)$/)[1];
    for (const e of d.els) {
      if (e.z === 'auto' && e.pos === 'static') continue;
      const k = `${e.tag}${e.id ? '#' + e.id : ''}${e.cls ? '.' + e.cls.split(' ')[0] : ''}|${e.pos}|${e.z}`;
      if (!z.has(k)) z.set(k, { views: new Set(), pos: e.pos, zi: e.z, el: k.split('|')[0] });
      z.get(k).views.add(`${view}@${w}`);
    }
  }
  console.log('**Every positioned element and every z-index in use**\n');
  console.log(tbl(['element', 'position', 'z-index', 'seen in'],
    [...z.values()].sort((a, b) => (a.zi === 'auto' ? -1 : +a.zi) - (b.zi === 'auto' ? -1 : +b.zi))
      .map(v => [v.el, v.pos, v.zi, [...v.views].slice(0, 6).join(', ') + (v.views.size > 6 ? ` +${v.views.size - 6}` : '')])));
  // overlaps between positioned elements and ordinary content
  console.log('\n**Overlaps**\n');
  for (const n of sets()) {
    const d = load(n), view = n.replace(/_populated_.*/, ''), w = +n.match(/(\d+)$/)[1];
    const fixed = d.els.filter(e => e.pos === 'fixed' || e.pos === 'sticky');
    for (const f of fixed) {
      // its own children sit inside its box by definition; only content it covers counts
      const inside = e => e.x >= f.x && e.y >= f.y && e.x + e.w <= f.x + f.w && e.y + e.h <= f.y + f.h;
      const over = d.els.filter(e => e !== f && e.pos === 'static' && e.hasText && !inside(e)
        && e.x < f.x + f.w && e.x + e.w > f.x && e.y < f.y + f.h && e.y + e.h > f.y);
      if (over.length) rows.push([`${view}@${w}`,
        `${f.tag}${f.id ? '#' + f.id : ''}${f.cls ? '.' + f.cls.split(' ')[0] : ''} (${f.pos}, z ${f.z})`,
        over.length, over.slice(0, 3).map(e => `${e.tag}${e.cls ? '.' + e.cls.split(' ')[0] : ''}`).join(', ')]);
    }
  }
  console.log(rows.length ? tbl(['render', 'positioned element', 'elements under it', 'which'], rows)
    : 'no sticky or fixed element overlaps text at any measured width.');
}

/* ======================================================================== TARGETS
 * T1-T7 of the September redesign, each computed from the same JSON every table above reads.
 *
 * A target with no script behind it is an opinion, and the three complaints this redesign answers
 * — too much empty space, data not understandable, everything disconnected — are exactly the three
 * that sound like moods until somebody measures them. So: T2 is the empty share of the first
 * viewport, T4 is numerals with nothing to compare them to, T5 is components with no link in or
 * out. The other four are the reading they depend on.
 *
 * ROLES is the one place a target names a part of the page. A direction is a drawing and the
 * shipped page is a renderer, and both have to be measured by the same code, so each role is a
 * list of selectors tried in order and the table says which one answered. A role nothing answers
 * is reported as absent rather than skipped: the shipped page carries no data-kind at all, and
 * that zero is the baseline T3 is measured against.
 */
const ROLES = {
  sentence: ['[data-component="sentence"]', '[data-role="sentence"]', '.hero p.big', '.wall p.big'],
  /* The monument numeral. `b.mono` and not `p.big b`: ancestors are not checked, so a descendant
   * selector ending in a bare tag matched the header's own <b>. */
  numeral: ['[data-role="numeral"]', 'b.mono'],
  state: ['[data-component="kicker"] .state', '[data-role="state"]', '.hero .k .state', '.wall .k .state'],
  /* `[data-role="ask"]` FIRST, since 21 September 2026. role() returns the first selector with any
   * hit at all and stops, so while the ask strip lived in the lead the component name found it and
   * the chain never went further. The strip is in Act now and the lead carries a line saying how
   * many are open and where they are; a component-name match therefore finds Act's strips, which
   * are correctly far below the fold, and reports the first screen as having no ask on it. The
   * explicit role is the marker put there to be found, so it is asked first. */
  ask: ['[data-role="ask"]', '[data-component="askStrip"]', '.askstrip'],
  asof: ['[data-role="asof"]', '.asof', '#headprov .asof', '.wall .foot'],
  index: ['[data-component="index"]', '[data-role="index"]', '#index', '.index'],
  indexRow: ['[data-component="indexRow"]', '[data-role="index-row"]', '.index .row'],
  miniStack: ['[data-component="miniStack"]', '[data-role="mini-stack"]', '.stack.mini'],
  wallIssueLine: ['[data-component="wallIndex"] .ln', '[data-role="wall-issue"]', '.wall .wi .ln'],
  /* The readable part of the rho row is its caption: the row itself is a texture of signs, and
   * a sign is measured against --sign-floor, not against a cap height. */
  rho: ['[data-role="rho"]', '.rhocap', '[data-component="rhoRow"]'],
};

/* Does any element in `d` match this role, and is its box inside the first viewport?
 * Selectors are matched against what COLLECT recorded — tag, id, class, data-component,
 * data-role — rather than re-queried in a browser, so a target is answerable from a committed
 * JSON months after the render. Only the shapes ROLES actually uses are supported, and an
 * unsupported one throws rather than quietly matching nothing. */
function matches(e, sel) {
  const M = sel.match(/^\[data-component="([^"]+)"\](?:\s+(.+))?$/);
  if (M) {
    if (M[2]) return false;             // a descendant selector: handled by the caller's own pass
    return e.dc === M[1];
  }
  const R = sel.match(/^\[data-role="([^"]+)"\]$/);
  if (R) return e.drole === R[1];
  const parts = sel.trim().split(/\s+/);
  const last = parts[parts.length - 1];
  const bits = last.match(/^([a-z0-9]+)?((?:[.#][A-Za-z0-9_-]+)*)$/i);
  if (!bits) throw new Error('measure.mjs: ROLES selector not supported: ' + sel);
  /* Ancestors are not checked — COLLECT records elements, not a tree — so a descendant selector
   * whose last part is a bare tag would match that tag ANYWHERE. `.hero p.big b` reported the
   * header's own <b> as the hero's monument numeral, and a refused page with no numeral at all
   * passed T1's numeral leg. A descendant selector has to end in something distinctive. */
  if (parts.length > 1 && !bits[2]) return false;
  if (bits[1] && e.tag !== bits[1].toUpperCase()) return false;
  for (const b of (bits[2] || '').match(/[.#][A-Za-z0-9_-]+/g) || []) {
    if (b[0] === '#' && e.id !== b.slice(1)) return false;
    if (b[0] === '.' && !has(e, b.slice(1))) return false;
  }
  return true;
}
function role(d, name) {
  for (const sel of ROLES[name]) {
    const hit = d.els.filter(e => matches(e, sel));
    if (hit.length) return { sel, els: hit };
  }
  return { sel: null, els: [] };
}
const inFold = (e, d) => e.y < d.doc.vh && e.y + e.h > 0;
const yes = b => (b ? '✓' : '**✗**');

function aTargets() {
  const names = fs.readdirSync(OUT).filter(f => /\.json$/.test(f) && !/^stall_|^sizes/.test(f))
    .map(f => f.replace(/\.json$/, ''));
  const rows = [];
  for (const n of names.sort()) {
    const d = load(n);
    const w = d.doc.vw, vh = d.doc.vh;
    const wall = /wall/.test(n);

    /* T1 — is the first screen the whole answer? The sentence with its numeral, the state word,
     * the ask (or the words standing in for one), and when this was last true. */
    const sent = role(d, 'sentence'), num = role(d, 'numeral'), st = role(d, 'state');
    const ask = role(d, 'ask'), asof = role(d, 'asof');
    const t1 = {
      sentence: sent.els.some(e => inFold(e, d)),
      numeral: num.els.some(e => inFold(e, d)),
      state: st.els.some(e => inFold(e, d)),
      ask: ask.els.some(e => inFold(e, d) && e.h > 0),
      asof: asof.els.some(e => inFold(e, d)),
    };
    if (w >= 1440 && !wall) {
      t1.index = role(d, 'indexRow').els.filter(e => inFold(e, d)).length;
      t1.mini = role(d, 'miniStack').els.some(e => inFold(e, d));
    }
    /* T1b — what the index and the mini stack are FOR: the whole environmental picture on the first
     * screen. The literal legs above name the shipped page's own composition, and a direction that
     * dissolves the index into the page answers the question without carrying an index. Both are
     * reported: the legs, and the thing they exist to deliver.
     *
     * An issue is "named with a number" when a numeral in the fold is keyed `<issue>.<something>`.
     * That is how every direction marks them, and it needs no index. */
    /* Keys that are not issues. The H3-navigated directions key their geometry numerals `h3.*`,
     * `cell.*`, `disk.*`, and — from the third round, which navigates by grid and by nothing else —
     * `grain.*`, `claim.*`, `nav.*` and `surface.*`. Counting those as issues named on the first
     * screen would report a page as answering for five issues when it is answering for two and a
     * hexagon. */
    const NOT_ISSUE = ['funnel', 'peer', 'rho', 'place', 'satellite', 'h3', 'cell', 'disk',
      'grain', 'claim', 'nav', 'surface',
      /* the modular H: a section's own numerals are keyed by the section */
      'ground', 'mesh', 'asks', 'sensors', 'wall', 'view'];
    const issueOf = e => String(e.dnum).split('.')[0];
    const named = new Set(d.els.filter(e => e.dnum && inFold(e, d))
      .map(issueOf).filter(k => !NOT_ISSUE.includes(k)));
    /* The denominator is every issue the PAGE names, not every issue a band declares: a direction
     * that dissolves the index into the page carries no `data-band="issue:*"` outside its lead, and
     * counting those reported three issues out of one. */
    const allIssues = new Set(d.els.filter(e => e.dnum)
      .map(issueOf).filter(k => !NOT_ISSUE.includes(k)));
    /* A page that declares no numerals at all cannot be asked this question: the shipped page shows
     * four issues with numbers and marks none of them, and reporting "0 of 4" would read as a
     * failure of composition where it is an absence of declaration. */
    /* The LIST, not a ratio. A denominator derived from the page's own keys counts a readout's
     * metric as an issue, and "2 of 9" reads as a failure where "water air" is a fact anybody can
     * check against the screenshot. */
    const anyNum = d.els.some(e => e.dnum !== null);
    const t1b = !anyNum ? '— (no data-num)' : ([...named].sort().join(' ') || 'none');

    /* T2 — the empty share of the first viewport, and the whole page in viewports.
     * Marked ground is the UNION of what is drawn, rasterised on a 4 px grid: a line of text
     * inside a bordered box counts once. This is 5.1's own measure, reused verbatim. */
    const grids = { lit: null, read: null };
    for (const which of ['lit', 'read']) {
      const G = 4, gw = Math.ceil(w / G), gh = Math.ceil(vh / G), grid = new Uint8Array(gw * gh);
      const mark = (x, y, ww, hh) => {
        for (let gy = Math.max(0, Math.floor(y / G)); gy < Math.min(gh, Math.ceil((y + hh) / G)); gy++)
          for (let gx = Math.max(0, Math.floor(x / G)); gx < Math.min(gw, Math.ceil((x + ww) / G)); gx++)
            grid[gy * gw + gx] = 1;
      };
      /* T2 as written: a pixel is full when it is inside an element that CARRIES text, a mark, a
       * sign, an image or a control — and "padding inside such an element counts as full". So the
       * whole box of such an element is marked, not only its glyphs. `hasText` is a DIRECT text
       * child, which is what "carries" means: <body> contains every word on the page and carries
       * none of them.
       *
       * This is NOT the skeleton review's "unmarked ground", which rasterises line boxes and media
       * alone. That measure answers "how much ink is on the screen"; this one answers "how much of
       * the screen is occupied by things", which is the question the complaint asks. */
      for (const e of d.els) {
        if (e.y >= vh || !(e.hasText || e.kind === 'media' || e.kind === 'control')) continue;
        /* Two readings, because the literal target has a loophole worth naming. T2 counts a pixel
         * as full if it sits inside anything carrying "text, a mark, a sign, an image or a
         * control", and a decorative full-bleed background IS an image — so a page can pass T2 by
         * putting a picture behind everything and saying nothing. `lit` is the target as written;
         * `read` drops what the page itself has marked aria-hidden, which is the page's own
         * statement that the mark carries no reading. Both are reported; a gap between them is a
         * page whose emptiness is being filled by decoration. */
        if (which === 'read' && e.hidden) continue;
        mark(e.x, e.y, e.w, e.h);
      }
      /* Against the grid's own area, not the viewport's: at 390 the 4 px grid is 98 cells wide,
       * which is 392 px, and dividing by 390 reported a page as -0.5 % empty. */
      grids[which] = 100 * (1 - grid.reduce((a, b) => a + b, 0) / (gw * gh));
    }
    const empty = grids.lit, emptyRead = grids.read;
    const screens = d.doc.h / vh;

    /* T3 — how many card kinds the whole interface has. Four, named and counted. */
    const kinds = [...new Set(d.els.map(e => e.dkind).filter(Boolean))].sort();

    /* T4 — no orphan numeral. `nums` is what the page DECLARES as a numeral; `drawn` is what a
     * reader actually meets, so a page carrying no data-num at all reports 0 of 0 declared against
     * a real count, rather than a clean zero that means nothing was looked at. */
    const nums = d.els.filter(e => e.dnum !== null);
    const orphanNums = nums.filter(e => e.dcmp === null);
    const drawn = d.els.filter(e => has(e, 'num') || (e.tag === 'B' && has(e, 'mono'))).length;

    /* T5 — no orphan component. A link out is this component's own data-ref naming an id on the
     * page; a link in is somebody else's data-ref naming an id inside this component. Only the
     * header and the hero may stand alone. */
    const ids = new Set(d.els.map(e => e.id).filter(Boolean));
    const refs = d.els.map(e => e.dref).filter(Boolean);
    const comps = d.els.filter(e => e.dc && !['header', 'hero'].includes(e.dc));
    const orphanComps = comps.filter(c => {
      const out = c.dref && ids.has(c.dref.replace(/^#/, ''));
      const mine = new Set(d.els.filter(e => e.id && e.x >= c.x - 1 && e.y >= c.y - 1
        && e.x + e.w <= c.x + c.w + 1 && e.y + e.h <= c.y + c.h + 1).map(e => e.id));
      const into = refs.some(r => mine.has(r.replace(/^#/, '')));
      return !(out || into);
    });

    /* T6 — reading order = DOM order in the first viewport. Rows first, then left to right inside
     * a row; eight pixels of difference in y is the same line, not an order. */
    const fold = d.els.filter(e => inFold(e, d) && e.w * e.h > 400)
      .filter(e => e.hasText || e.kind !== 'box' || e.dc);
    const byPos = [...fold].sort((a, b) => (Math.abs(a.y - b.y) <= 8 ? a.x - b.x : a.y - b.y));
    /* Adjacent inversions, not rank differences. One element moved ten places up makes twenty ranks
     * differ, so a single swap was reporting as forty divergences and a page with one two-column
     * block looked catastrophic beside a page with ten. This counts the swaps: it is zero exactly
     * when reading order and DOM order agree, and it grows by one per place they actually disagree. */
    let diverge = 0;
    for (let i = 0; i + 1 < byPos.length; i++) if (byPos[i].dom > byPos[i + 1].dom) diverge++;

    /* T7 — the wall at three metres. 1 px = 0.63 mm at 1920 on a 55-inch 16:9 panel; the floor is
     * about 3 mm of cap height per metre, so 9 mm. */
    let t7 = '—';
    if (wall && w >= 1920) {
      const MM = 0.63;
      const want = [['sentence', sent], ['numeral', num], ['issue line', role(d, 'wallIssueLine')],
        ['rho row', role(d, 'rho')]];
      const parts = [];
      for (const [label, r] of want) {
        const caps = d.lines.filter(l => r.els.some(e => l.x >= e.x - 2 && l.x <= e.x + e.w + 2
          && l.y >= e.y - 2 && l.y + l.h <= e.y + e.h + 2)).map(l => l.cap * MM);
        if (!caps.length) { parts.push(`${label} **absent**`); continue; }
        const lo = Math.min(...caps);
        parts.push(`${label} ${lo.toFixed(1)}${lo < 9 ? ' **' : ' '}mm${lo < 9 ? '**' : ''}`);
      }
      t7 = parts.join('; ');
    }

    rows.push([n, w,
      `${yes(t1.sentence)}${yes(t1.numeral)}${yes(t1.state)}${yes(t1.ask)}${yes(t1.asof)}`
        + (t1.index === undefined ? '' : ` · idx ${t1.index} ${yes(t1.mini)}`),
      t1b,
      empty.toFixed(1) + ' / ' + emptyRead.toFixed(1) + ' %', screens.toFixed(1),
      kinds.length ? `${kinds.length}: ${kinds.join(' ')}` : '**0**',
      `${orphanNums.length} / ${nums.length} (${drawn} drawn)`,
      `${orphanComps.length} / ${comps.length}`,
      diverge, t7]);
  }
  console.log('T1 is sentence·numeral·state·ask·as-of in the first viewport (and at 1440 the index '
    + 'rows and the mini stack). T2 is the empty share of the first viewport and the page in '
    + 'viewports, counting every image as a mark (lit) and again ignoring aria-hidden '
    + 'decoration (read). T3 is distinct data-kind. T4 is [data-num] with no [data-cmp]. T5 is '
    + '[data-component] with no [data-ref] in or out. T6 is position-order divergences from DOM '
    + 'order. T7 is cap height at 1920 dark.\n');
  console.log(tbl(['render', 'w', 'T1', 'T1b issues named', 'T2 empty lit/read', 'T2 screens', 'T3 kinds', 'T4 orphan nums',
    'T5 orphan comps', 'T6 diverge', 'T7 wall'], rows));
}

/* The renders themselves. A wireframe is what a measurement looks like; this is what a person
 * looks at, and the rule for this round is that nothing is claimed to render that was not seen in
 * one. JPEG at one device pixel, the same as every capture in the September review, so a shot from
 * this round can be set beside one from that one.
 *
 * `full` shoots the whole document; without it the shot is the first viewport, which is the thing
 * T1 and T2 are about.
 */
async function shots(names) {
  const all = jobs();
  const want = names[0] === 'all' ? all : all.filter(j => names.includes(j.name));
  if (!want.length) { console.error('no such job:', names.join(' ')); process.exit(2); }
  for (const j0 of want) {
    const job = tagged(j0);
    let h;
    try {
      h = await open(job);
      for (const full of [false, true]) {
        const f = path.join(OUT, `${job.name}${full ? '_full' : '_fold'}.jpg`);
        await h.page.screenshot({ path: f, fullPage: full, type: 'jpeg', quality: 82 });
        console.log(`  ${path.basename(f)}  ${(fs.statSync(f).size / 1024).toFixed(0)} kB`);
      }
    } catch (e) {
      console.error(`${job.name}  FAILED  ${e.message}`);
    } finally { if (h) await h.browser.close(); }
  }
}

/* T9 — weight, axe, named SVGs, and whether the page reads frozen.
 *
 * Four things that can only be measured with the page running, so they are their own command
 * rather than an analysis of a committed JSON. The refresh window is one poll interval plus a
 * second: the renderer refreshes every 20 s and the satellite frames are fetched once for the life
 * of the document, so a window that starts after first paint measures what a wall screen actually
 * costs per day.
 */
async function audit(names) {
  const all = jobs();
  const want = names[0] === 'all' ? all : all.filter(j => names.includes(j.name));
  const axePath = path.join(DESIGN, 'node_modules/axe-core/axe.min.js');
  const haveAxe = fs.existsSync(axePath);
  const rows = [];
  for (const job of want) {
    let h;
    try {
      h = await open(job);
      const bytes = { n: 0, b: 0, paths: {} };
      h.page.on('response', async r => {
        const u = new URL(r.url());
        try {
          const len = +(r.headers()['content-length'] || 0)
            || (await r.body().catch(() => Buffer.alloc(0))).length;
          bytes.n++; bytes.b += len;
          bytes.paths[u.pathname] = (bytes.paths[u.pathname] || 0) + len;
        } catch (e) { /* a response the browser dropped is not a measurement */ }
      });
      await h.page.waitForTimeout(21000);              // one refresh at the renderer's own cadence

      const svg = await h.page.evaluate(() => {
        const all = [...document.querySelectorAll('svg')];
        const bad = all.filter(s => s.getAttribute('aria-hidden') !== 'true'
          && !s.getAttribute('aria-label') && !s.querySelector(':scope > title')
          && !s.closest('[aria-hidden="true"]'));
        return { all: all.length, unnamed: bad.length };
      });
      /* Reduced motion is set on the context, so this asks what is still moving under it — CSS
       * animations and transitions with a non-zero duration, and SMIL, which no media query can
       * reach and which is why the layer's rule is "deleted, not tuned". */
      const motion = await h.page.evaluate(() => {
        let css = 0;
        for (const el of document.querySelectorAll('*')) {
          const c = getComputedStyle(el);
          if (c.animationName !== 'none' && parseFloat(c.animationDuration) > 0) css++;
          if (parseFloat(c.transitionDuration) > 0) css++;
        }
        return { css, smil: document.querySelectorAll('animate,animateTransform,animateMotion,set').length };
      });

      let axe = 'not run';
      if (haveAxe) {
        await h.page.addScriptTag({ path: axePath });
        const r = await h.page.evaluate(async () => {
          const res = await window.axe.run(document, { resultTypes: ['violations'] });
          return res.violations.map(v => ({ id: v.id, impact: v.impact, n: v.nodes.length }));
        });
        const bad = r.filter(v => v.impact === 'serious' || v.impact === 'critical');
        axe = bad.length
          ? '**' + bad.map(v => `${v.id} ${v.impact} ×${v.n}`).join('; ') + '**'
          : `0 serious/critical (${r.length} minor/moderate)`;
      }
      const top = Object.entries(bytes.paths).sort((a, b) => b[1] - a[1]).slice(0, 3)
        .map(([p, b]) => `${p} ${(b / 1024).toFixed(0)} kB`).join(', ');
      rows.push([job.name, `${(bytes.b / 1024).toFixed(1)} kB / ${bytes.n} req`, top,
        svg.unnamed ? `**${svg.unnamed} of ${svg.all}**` : `0 of ${svg.all}`,
        motion.css || motion.smil ? `**css ${motion.css}, smil ${motion.smil}**` : '0'
      , axe]);
      console.error(`  ${job.name} audited`);
    } catch (e) {
      rows.push([job.name, 'FAILED', e.message.slice(0, 60), '', '', '']);
    } finally { if (h) await h.browser.close(); }
  }
  console.log('One 21-second window after first paint, which is one refresh at the renderer\'s own '
    + 'cadence. Reduced motion is on, so anything still moving is something the media query cannot '
    + 'reach.\n');
  console.log(tbl(['render', 'per refresh', 'the heaviest of it', 'SVGs unnamed', 'still moving',
    'axe serious/critical'], rows));
}

/* WHERE THE AIR IS — T2c, decomposed.
 *
 * T2's empty-share leg says the first screen at 1440 is 57 % air and does not say where. Prompt 7
 * guessed with a method of its own — unioning element boxes over a coarse grid — and got 20-40 %,
 * because a section's own container box marks everything inside it as used. That number was wrong
 * and the disagreement was the tell.
 *
 * So this uses aTargets' grid VERBATIM: the same 4 px cells, the same predicate (an element that
 * carries direct text, or is media, or is a control, marks its whole box), the same `read` variant
 * that drops what the page marked aria-hidden. Nothing here re-decides what full means. What it adds
 * is attribution: for every EMPTY cell, which part of the page it sits in.
 *
 * Three readings, because "where" has three useful answers:
 *
 *   · by part — the air inside each named component's own box, which is a layout question for that
 *     component, and the air inside no component at all, which is a spacing question between them.
 *   · down the page — the empty share of each 60 px stripe, which says whether the air is one hole
 *     or spread evenly.
 *   · across the page — the empty share of each tenth of the width, which is the question the lead's
 *     two-column grid raises: is one column carrying the whole screen.
 *
 * A cell is attributed to the SMALLEST named component containing it, so the lead's own box does not
 * swallow the air inside the meters. Scaffold is not a part: HTML, BODY, MAIN, .wrap and a view
 * SECTION are containers, not things on the screen, and attributing air to them says nothing.
 */
function aAir() {
  const G = 4;
  const SCAFFOLD0 = e => ['HTML', 'BODY', 'MAIN'].includes(e.tag) || has(e, 'wrap')
    || (e.tag === 'SECTION' && has(e, 'view'));
  for (const n of sets()) {
    const d = load(n), view = n.replace(/_populated_.*/, ''), w = +n.match(/(\d+)$/)[1];
    if (view !== 'now' || (w !== 390 && w !== 1440)) continue;
    const vh = d.doc.vh, gw = Math.ceil(w / G), gh = Math.ceil(vh / G);

    for (const which of ['lit', 'read']) {
      const grid = new Uint8Array(gw * gh);
      const mark = (x, y, ww, hh) => {
        for (let gy = Math.max(0, Math.floor(y / G)); gy < Math.min(gh, Math.ceil((y + hh) / G)); gy++)
          for (let gx = Math.max(0, Math.floor(x / G)); gx < Math.min(gw, Math.ceil((x + ww) / G)); gx++)
            grid[gy * gw + gx] = 1;
      };
      for (const e of d.els) {
        if (e.y >= vh || !(e.hasText || e.kind === 'media' || e.kind === 'control')) continue;
        if (which === 'read' && e.hidden) continue;
        mark(e.x, e.y, e.w, e.h);
      }
      const total = gw * gh;
      let air = 0;
      for (let i = 0; i < total; i++) if (!grid[i]) air += 1;
      if (which === 'lit') {
        console.log(`\n### Now @ ${w} — the first ${vh} px`);
        console.log(`\n${(100 * air / total).toFixed(1)} % air on the \`lit\` reading `
          + `(${air} of ${total} cells of ${G} px).`);
      } else {
        console.log(`${(100 * air / total).toFixed(1)} % on \`read\`, `
          + `which drops what the page marked aria-hidden.`);
        continue;                      // the two readings differ by very little; decompose `lit`
      }

      /* THE SAME AIR, MEASURED INSIDE THE PAGE'S OWN COLUMN.
       *
       * T2 counts the empty share of the VIEWPORT, and this page is a centred column with a
       * max-width — so at 1440 there are 140 px of margin down each side that no page with a
       * readable measure could ever fill. They are 19 % of the screen and T2 counts every pixel of
       * them as a failure. The wider the display, the worse the number, for a page that has not
       * changed. That is measuring a typographic virtue as a defect.
       *
       * So both are reported: against the viewport, which is T2 as written, and against the column
       * the page actually draws in, which is the number that can be acted on. */
      const col = d.els.filter(e => e.y < vh && e.w > w * 0.5 && e.w < w - 8 && !SCAFFOLD0(e))
        .sort((a, b) => b.w - a.w)[0];
      if (col) {
        const x0 = Math.floor(col.x / G), x1 = Math.ceil((col.x + col.w) / G);
        let e1 = 0, c1 = 0;
        for (let gy = 0; gy < gh; gy++)
          for (let gx = Math.max(0, x0); gx < Math.min(gw, x1); gx++) {
            c1 += 1; if (!grid[gy * gw + gx]) e1 += 1;
          }
        const margin = 100 * (1 - (c1 / total));
        console.log(`\n**${(100 * e1 / c1).toFixed(1)} % inside the page's own column** `
          + `(${r1(col.w)} px wide, ${r1(col.x)} px in). The margins either side are `
          + `${margin.toFixed(1)} % of the viewport and no page with a readable measure fills them; `
          + `T2 as written counts every pixel of them as empty.`);
      }

      /* the parts: named components, smallest first, so a child wins its own cells */
      const SCAFFOLD = e => ['HTML', 'BODY', 'MAIN'].includes(e.tag)
        || has(e, 'wrap') || (e.tag === 'SECTION' && has(e, 'view'));
      const parts = d.els
        .filter(e => e.y < vh && e.y + e.h > 0 && e.w > 8 && e.h > 8 && !SCAFFOLD(e))
        .filter(e => e.dc || e.dband || (e.id && e.tag === 'SECTION'))
        .map(e => ({ ...e, boxArea: e.w * e.h }))
        .sort((a, b) => a.boxArea - b.boxArea);
      const owner = new Int32Array(total).fill(-1);
      for (let pi = parts.length - 1; pi >= 0; pi--) {           // biggest first, smallest overwrite
        const e = parts[pi];
        for (let gy = Math.max(0, Math.floor(e.y / G)); gy < Math.min(gh, Math.ceil((e.y + e.h) / G)); gy++)
          for (let gx = Math.max(0, Math.floor(e.x / G)); gx < Math.min(gw, Math.ceil((e.x + e.w) / G)); gx++)
            owner[gy * gw + gx] = pi;
      }
      const tally = new Map();
      let loose = 0;
      for (let i = 0; i < total; i++) {
        if (grid[i]) continue;
        const pi = owner[i];
        if (pi < 0) { loose += 1; continue; }
        tally.set(pi, (tally.get(pi) || 0) + 1);
      }
      const name = e => `${e.dc ? e.dc : e.tag}${e.id ? ' #' + e.id : ''}`;
      const rows = [...tally.entries()].sort((a, b) => b[1] - a[1]).slice(0, 10).map(([pi, cells]) => {
        const e = parts[pi];
        const own = Math.ceil(e.w / G) * Math.ceil(e.h / G);
        return [name(e), `${r1(e.w)} x ${r1(e.h)}`, cells,
          (100 * cells / own).toFixed(0) + ' %', (100 * cells / air).toFixed(0) + ' %'];
      });
      rows.push(['**between the parts** — inside no component', '—', loose, '100 %',
        (100 * loose / air).toFixed(0) + ' %']);
      console.log('\n**Where it is, by part.** "air in it" is the share of that component\'s own box '
        + 'that is empty; the last column is its share of all the air on the screen.\n');
      console.log(tbl(['part', 'box', 'empty cells', 'air in it', 'share of all air'], rows));

      /* down the page */
      const STRIPE = 60, srows = [];
      for (let top = 0; top < vh; top += STRIPE) {
        let e0 = 0, c0 = 0;
        for (let gy = Math.floor(top / G); gy < Math.min(gh, Math.ceil((top + STRIPE) / G)); gy++)
          for (let gx = 0; gx < gw; gx++) { c0 += 1; if (!grid[gy * gw + gx]) e0 += 1; }
        const pc = 100 * e0 / (c0 || 1);
        srows.push([`${top}–${Math.min(vh, top + STRIPE)}`, pc.toFixed(0) + ' %',
          '`' + '█'.repeat(Math.round(pc / 4)) + '`']);
      }
      console.log('\n**Down the page**, in 60 px stripes.\n');
      console.log(tbl(['px from the top', 'air', ''], srows));

      /* across the page */
      const crows = [];
      for (let k = 0; k < 10; k++) {
        const x0 = Math.floor(k * gw / 10), x1 = Math.floor((k + 1) * gw / 10);
        let e0 = 0, c0 = 0;
        for (let gy = 0; gy < gh; gy++)
          for (let gx = x0; gx < x1; gx++) { c0 += 1; if (!grid[gy * gw + gx]) e0 += 1; }
        const pc = 100 * e0 / (c0 || 1);
        crows.push([`${Math.round(k * w / 10)}–${Math.round((k + 1) * w / 10)}`, pc.toFixed(0) + ' %',
          '`' + '█'.repeat(Math.round(pc / 4)) + '`']);
      }
      console.log('\n**Across the page**, in tenths of the width.\n');
      console.log(tbl(['px from the left', 'air', ''], crows));
    }
  }
}

const A = { grid: aGrid, spacing: () => aSpacing(true), rhythm: aRhythm, lines: aLines,
  align: aAlign, type: aType, headings: aHeadings, order: aOrder, dist: aDist, wall: aWall,
  dom: aDom, anatomy: aAnatomy, components: aComponents, stack: aStack,
  targets: aTargets, air: aAir };

/* DOES A PRESS ACTUALLY REDRAW?
 *
 * Every other check in this file measures ONE render. The page's controls are query links, and
 * since v0.55 a press is a re-render rather than a document load — which means a control can now
 * change the URL and nothing else, and every static measurement here would still pass. It did:
 * v0.55 shipped with the dial dead, because where() read the query captured at module scope when
 * the page first loaded, so the resolution never moved. The URL changed, the request count was
 * zero, and the page said exactly what it had said before.
 *
 * So this presses the dial and compares what the page SAYS, not where it thinks it is. Red if the
 * grain line, the dial's own on-stop, or the grouping of stations into cells comes back unchanged.
 */
async function press() {
  const job = tagged({ name: 'now_populated_1440', view: 'now', w: 1440, state: 'populated' });
  const h = await open(job);
  const read = () => h.page.evaluate(() => ({
    url: location.search,
    railOn: (document.querySelector('#rail a.on') || {}).textContent || null,
    /* The grain line moved to Network; the rail's area figure is on Now and changes with the dial. */
    grain: (document.querySelector('[data-num="rail.area"]') || {}).textContent || null,
    heads: [...document.querySelectorAll('[data-component="cellGroup"]')].map(e => e.textContent.trim()),
  }));
  const before = await read();
  const moved = await h.page.evaluate(() => {
    const a = document.querySelector('#rail a:not(.on)');
    if (!a) return false;
    a.click();
    return true;
  });
  if (!moved) { console.log('FAIL press: the dial has no stop to press'); await h.browser.close(); process.exit(1); }
  await h.page.waitForTimeout(700);
  const after = await read();
  const same = k => JSON.stringify(before[k]) === JSON.stringify(after[k]);
  const dead = ['railOn', 'grain', 'heads'].filter(same);
  const fails = [];
  if (before.url === after.url) fails.push('the URL did not change');
  if (dead.length) fails.push(`the press changed the URL and nothing else: ${dead.join(', ')} identical`);
  for (const f of fails) console.log('FAIL press:', f);
  if (!fails.length) console.log(`  press: ${before.railOn} -> ${after.railOn}, `
    + `${before.heads.length} cell group(s) -> ${after.heads.length}, and the grain line moved`);
  await h.browser.close();
  process.exit(fails.length ? 1 : 0);
}

/* ------------------------------------------------------------------ the page's own links
 *
 * Every `href="#…"` the page writes, followed. The hash is how this page routes, so a link to an
 * ANCHOR and a link to a VIEW are the same string in the same bar, and until 22 September the
 * router could not tell them apart: `#stage-act` — the lead's own link, pressed by anyone the page
 * tells "94 asks open · in 3 Act" — routed to a view of that name, found none, and drew an empty
 * band. A blank page, from the page's own link, in a shipped release.
 *
 * Nothing static could catch it: the id it lands on is built from a template, and the failure is in
 * the router at runtime. So this presses each one and asks the page three things afterwards — did
 * it stay on a real page, is the thing linked to actually there, and did it go to it.
 */
async function anchors() {
  /* PAI_VIEW=network runs the same walk on another view. An anchor there used to send the reader to
     Now, because readView() answered 'now' for any hash that was not a view name. */
  const view = process.env.PAI_VIEW || 'now';
  const job = tagged({ name: `${view}_populated_1440`, view, w: 1440, state: 'populated' });
  const h = await open(job);
  const links = await h.page.evaluate(() => [...new Set([...document.querySelectorAll('#page a[href^="#"]')]
    .map(a => a.getAttribute('href').slice(1)).filter(Boolean))]);
  const fails = [];
  const said = [];
  for (const id of links) {
    const r = await h.page.evaluate(async (anchor) => {
      location.hash = anchor;
      await new Promise(x => setTimeout(x, 500));
      const page = document.getElementById('page');
      const el = document.getElementById(anchor);
      const on = document.querySelector('nav.views button.on');
      return { chars: page.innerText.trim().length, bands: page.querySelectorAll('section.band').length,
        there: !!el, top: el ? Math.round(el.getBoundingClientRect().top) : null,
        view: on ? on.dataset.view : null };
    }, id);
    if (r.view !== view) fails.push(`#${id}: the link left the ${view} view for ${r.view}`);
    else if (!r.there) fails.push(`#${id}: nothing on the page carries that id`);
    else if (r.bands < 2 || r.chars < 2000) {
      fails.push(`#${id}: the page emptied — ${r.bands} band(s), ${r.chars} characters`);
    } else if (r.top > 200 || r.top < -200) {
      fails.push(`#${id}: it did not go there — the element is ${r.top}px from the top`);
    } else said.push(`#${id}`);
  }
  await h.browser.close();
  for (const f of fails) console.log('FAIL anchors:', f);
  if (!fails.length) {
    console.log(`  anchors: ${said.length} in-page link(s) followed, each one lands on its own `
      + `element with the page still drawn \u2014 ${said.join(' ')}`);
  }
  process.exit(fails.length ? 1 : 0);
}

/* ------------------------------------------------------------------ a stranger's pack
 *
 * WHAT THIS IS, AND WHY IT IS NOT CALLED T8. Prompt 7 asks to "run the third-party `water` pack
 * fixture from the 14 Sep prompt (1.4) and prove T8 still holds". Neither exists any more: the
 * 14 September prompt is not in this repository, not in `docs/`, and not anywhere on the machine
 * that wrote it, and with it went T8's definition — the target tables in
 * `docs/design/DIRECTIONS_2026-09.md` run T1, T1b, T2, T3, T4, T5, T6 and PICK adds T7 and T9.
 * There is no T8 to hold. So rather than invent a number and claim it was met, this proves the
 * thing that prompt and `DIRECTIONS` §"Where the new things land" were plainly about: the page
 * draws a section it has never heard of, and the targets survive it.
 *
 * HOW A STRANGER GETS IN. A pack's dashboard contribution is one more static file the node serves,
 * which calls `window.PAI.register` when it parses. Here that timing is reproduced exactly, with a
 * setter on `window.PAI`: the moment dashboard.js assigns it, the stranger registers — before
 * `route()` draws anything, and without the page having been edited to expect it.
 *
 * Four sections, because a stranger is not always well behaved:
 *   water        draws a stack of its own, with a unit per cell
 *   water-deep   declares a need this node does not have
 *   water-bad    throws
 *   water-fifth  draws a FIFTH card kind, which T3 says does not exist
 *
 * The first three are the contract's promises. The fourth is the one that must show up as damage:
 * if a stranger can add a fifth kind and nothing notices, "four card kinds and no fifth" is a
 * sentence in a document rather than a property of the page.
 */
const STRANGER = () => {
  const K = window.K;
  window.PAI.register({
    id: 'water', pack: 'water', stage: 'observe', order: 13,
    title: 'What the water is doing',
    render() {
      /* A unit per cell, which is the case DIRECTIONS names: the room is turbidity in NTU and the
         region is metres below a water table. Two quantities, so two scales and never one bar. */
      const rows = [['room', '4.2', 'NTU'], ['region', '11.8', 'm below']];
      return `<div class="stack" data-kind="stack" data-component="waterStack" id="water-stack"`
        + ` data-ref="water"><div class="col" id="water-col-room" data-ref="water-stack">`
        + rows.map(([k, v, u], i) =>
          `<div class="v"><span class="num" data-num="water.${k}"`
          + ` data-cmp="${K.esc(`${k}: ${v} ${u}, no line declared`)}">${K.esc(v)}</span>`
          + `<small>${K.esc(u)}</small></div>`).join('')
        + `</div></div>`;
    },
    notes: () => [{ id: 'water-note', text: 'A stranger wrote this section and this note.' }],
  });
  window.PAI.register({
    id: 'water-deep', pack: 'water', stage: 'observe', order: 14,
    title: 'The water table', needs: ['WATER_TABLE'], render: () => '<p>never drawn</p>',
  });
  window.PAI.register({
    id: 'water-bad', pack: 'water', stage: 'decide', order: 99,
    title: 'What the water pack cannot do',
    render() { throw new Error('a stranger threw'); },
  });
  window.PAI.register({
    id: 'water-fifth', pack: 'water', stage: 'observe', order: 15,
    title: 'A fifth kind',
    render: () => '<div data-kind="dial" data-component="waterDial" id="water-dial"'
      + ' data-ref="water-stack">a dial</div>',
  });
};

async function extend() {
  const job = tagged({ name: 'now_populated_1440', view: 'now', w: 1440, state: 'populated' });
  const h = await open(job, {}, STRANGER);
  const d = await h.page.evaluate(COLLECT);
  const bands = await h.page.evaluate(() => [...document.querySelectorAll('section.band')]
    .map(b => ({ id: b.id, pack: b.dataset.pack, stage: b.dataset.stage })));
  const probe = await h.page.evaluate(() => window.__pai_probe || 'never installed');
  const said = await h.page.evaluate(() => ({
    absent: (document.getElementById('water-deep-absent') || {}).textContent || null,
    failed: (document.getElementById('water-bad-failed') || {}).textContent || null,
    note: !!document.getElementById('water-note'),
  }));
  await h.browser.close();

  const has = (e, c) => (e.cls || '').split(/\s+/).includes(c);
  const kinds = [...new Set(d.els.map(e => e.dkind).filter(Boolean))].sort();
  const nums = d.els.filter(e => e.dnum !== null);
  const orphanNums = nums.filter(e => e.dcmp === null);
  const ids = new Set(d.els.map(e => e.id).filter(Boolean));
  const refs = d.els.map(e => e.dref).filter(Boolean);
  const comps = d.els.filter(e => e.dc && !['header', 'hero'].includes(e.dc));
  const orphanComps = comps.filter(c => {
    const out = c.dref && ids.has(c.dref.replace(/^#/, ''));
    const mine = new Set(d.els.filter(e => e.id && e.x >= c.x - 1 && e.y >= c.y - 1
      && e.x + e.w <= c.x + c.w + 1 && e.y + e.h <= c.y + c.h + 1).map(e => e.id));
    return !(out || refs.some(r => mine.has(r.replace(/^#/, ''))));
  });

  const fails = [];
  if (probe !== 'fired') fails.push(`the registration hook: ${probe}`);
  const water = bands.find(b => b.id === 'water');
  if (!water) fails.push('the stranger\'s section is not on the page at all');
  else {
    if (water.pack !== 'water') fails.push(`the band says pack="${water.pack}", not the pack that wrote it`);
    if (water.stage !== 'observe') fails.push(`it was drawn in ${water.stage}, not the stage it declared`);
    const obs = bands.filter(b => b.stage === 'observe').map(b => b.id);
    const i = obs.indexOf('water');
    if (i <= 0 || obs.indexOf('matrix') > i) fails.push(`observe order ignores it: ${obs.join(' ')}`);
  }
  if (!said.absent || !/water pack has nothing here yet/i.test(said.absent)) {
    fails.push('a declared need this node does not have did not print one honest line');
  }
  if (!said.failed || !/did not render/.test(said.failed)) {
    fails.push('a section that threw did not say so');
  }
  if (bands.length < 8) fails.push(`only ${bands.length} bands survived a stranger throwing`);
  if (!said.note) fails.push('the stranger\'s note is not in the notes band');
  if (orphanNums.length) fails.push(`${orphanNums.length} numeral(s) with no comparison`);
  if (orphanComps.length) fails.push(`${orphanComps.length} component(s) with no link in or out`);
  /* The fifth kind MUST show. This is the one assertion that fails when the page is too permissive
     rather than too strict, and it is the reason the stranger draws one. */
  if (!kinds.includes('dial')) {
    fails.push('a stranger drew data-kind="dial" and the count did not see it, so T3 is measuring '
      + 'nothing and a fifth kind could ship unnoticed');
  }
  const four = kinds.filter(k => k !== 'dial');
  if (four.length !== 4) fails.push(`the page's own kinds are ${four.join(' ')} — ${four.length}, not four`);

  for (const f of fails) console.log('FAIL extend:', f);
  if (!fails.length) {
    console.log(`  extend: a stranger's section draws in its own stage and order `
      + `(${bands.filter(b => b.stage === 'observe').map(b => b.id).join(' ')})`);
    console.log(`  extend: an absent need prints one line, a throw says so, ${bands.length} bands still drew`);
    console.log(`  extend: T3 ${four.join(' ')} + the stranger's fifth caught · `
      + `T4 ${orphanNums.length} of ${nums.length} · T5 ${orphanComps.length} of ${comps.length}`);
  }
  process.exit(fails.length ? 1 : 0);
}

/* ------------------------------------------------------------------ the baseline plates
 *
 * Every combination the page can be in, as a JPEG at one device pixel, kept as the baseline a later
 * round diffs against. Fifty-four renders: five views at three widths in both registers, Now again
 * in simple and in learn, the wall, and the empty and refused states.
 *
 * THE WALL IS DARK ONLY. Its register is not a choice — applyRegister() forces dark on that view
 * because it is a screen on a wall in a room — so rendering it "in paper" would write two identical
 * files under two names and claim the pair proved something.
 *
 * FOLD, NOT FULL, except for six. A full-page JPEG of Now at 1440 is 300 kB and the whole matrix
 * that way is twenty megabytes in a repository a tester clones. The fold is what T1 and T2 are
 * about, which is what a baseline is for; the six full pages are the ones somebody actually reads
 * end to end.
 */
function plates() {
  const P = [];
  const WIDE = [390, 768, 1440];
  for (const v of ['now', 'historical', 'network', 'arrange', 'setup']) {
    for (const w of WIDE) for (const r of ['paper', 'dark']) {
      P.push({ name: `${v}_${w}_${r}`, view: v, w, state: 'populated', register: r,
        full: v === 'now' && r === 'paper' });
    }
  }
  for (const w of WIDE) P.push({ name: `wall_${w}_dark`, view: 'wall', w, state: 'populated', dark: true });
  /* No `full` for the wall: it does not scroll, so the full page and the fold are the same
     picture, and the pair would be two files under two names proving nothing. */
  P.push({ name: 'wall_1920_dark', view: 'wall', w: 1920, state: 'populated', dark: true });
  for (const m of ['simple', 'learn']) {
    for (const w of WIDE) for (const r of ['paper', 'dark']) {
      P.push({ name: `now_${m}_${w}_${r}`, view: 'now', w, state: 'populated', mode: m, register: r,
        full: m === 'learn' && r === 'paper' && w === 1440 });
    }
  }
  for (const s of ['empty', 'refused']) {
    for (const w of [390, 1440]) for (const r of ['paper', 'dark']) {
      P.push({ name: `now_${s}_${w}_${r}`, view: 'now', w, state: s, register: r, wireOnly: true });
    }
  }
  return P;
}

async function plateShots(names) {
  const all = plates();
  const want = names[0] === 'all' ? all : all.filter(j => names.includes(j.name));
  if (!want.length) { console.error('no such plate:', names.join(' ')); process.exit(2); }
  const dir = process.env.PAI_PLATES ? path.resolve(process.env.PAI_PLATES) : OUT;
  fs.mkdirSync(dir, { recursive: true });
  let bytes = 0, made = 0, failed = 0;
  for (const job of want) {
    let h;
    try {
      h = await open(job);
      for (const full of job.full ? [false, true] : [false]) {
        const f = path.join(dir, `${job.name}${full ? '_full' : ''}.jpg`);
        await h.page.screenshot({ path: f, fullPage: full, type: 'jpeg', quality: 80 });
        bytes += fs.statSync(f).size; made += 1;
      }
    } catch (e) {
      console.error(`  ${job.name}  FAILED  ${e.message}`);
      failed += 1;
    } finally { if (h) await h.browser.close(); }
  }
  console.log(`  plates: ${made} JPEG(s) from ${want.length} render(s), `
    + `${(bytes / 1048576).toFixed(1)} MB, in ${path.relative(ROOT, dir) || dir}`);
  if (failed) { console.log(`FAIL plates: ${failed} render(s) did not complete`); process.exit(1); }
}

/* ------------------------------------------------------------------ the loading state
 *
 * Three claims about `asking` that nothing else can check, because all three are about the DOM at a
 * moment rather than about a drawing:
 *
 *   · it stops when the data is in. A loading state that keeps a rAF loop alive behind the page it
 *     was covering is a page that never goes idle, on a wall screen, for weeks.
 *   · the canvas LEAVES the tree. At 1440x900 and DPR 2 it is a 1670x1076 backing store, and it is
 *     also a surface something could draw on again by accident. display:none keeps both.
 *   · under reduced motion it draws ONE frame. Not zero — a reader who has asked for stillness is
 *     still owed the picture — and not a loop.
 *   · with motion on it is STILL MOVING when the floor ends, which is the one claim here that is
 *     about the drawing rather than the DOM, and the one that needed the canvas read.
 *
 * Driven through PAI_ASKING, which exists for this: a surface that only appears while a fetch is in
 * flight cannot be caught by a screenshot, and one that only animates when the browser says the tab
 * is visible cannot be timed from a headless run at all.
 */
async function asking() {
  const fails = [];
  const said = [];
  for (const reduce of [false, true]) {
    const job = tagged({ name: 'now_populated_1440', view: 'now', w: 1440, state: 'populated' });
    const h = await open(job, { reducedMotion: reduce ? 'reduce' : 'no-preference' });
    const r = await h.page.evaluate(async () => {
      const A = window.PAI_ASKING;
      if (!A) return { missing: true };
      A.open('probe');
      const had = !!document.getElementById('askcv');
      /* What the SCHEDULER drew, read before the probe resets the counter. Under reduced motion
         PAI_RAF calls the tick once and never subscribes, so this is exactly 1 and the subscription
         count is 0; with motion on nothing is drawn yet and the subscription is the claim. */
      const atOpen = A.cost().frames;
      const subscribed = window.PAI_RAF.size;
      const cost = A.probe(30);
      A.close();
      const after = { had, atOpen, subscribed, up: A.up(),
        canvas: !!document.getElementById('askcv'), subs: window.PAI_RAF.size, cost };
      /* THE FLOOR. What this state says is the page's own account of what it asked of the world,
         and on a fixture the node answers in under a tenth of a second — so without a floor nobody
         ever read it. Opened with the floor and closed at once: with motion on it must still be up,
         and under reduced motion it must be gone, because the layer zeroes that token there and a
         reader who asked for stillness did not ask for a three-second introduction. */
      A.open('floor', true);
      A.close();
      after.heldOpen = A.up();
      after.floor = window.K.msToken('--motion-asking-hold');
      return after;
    });
    const tag = reduce ? 'reduced motion' : 'motion on';
    if (r.missing) { fails.push(`${tag}: PAI_ASKING is not on the page`); await h.browser.close(); continue; }
    if (!r.had) fails.push(`${tag}: open() did not put a canvas in the frame`);
    if (r.up) fails.push(`${tag}: it is still up after close()`);
    if (r.canvas) fails.push(`${tag}: the canvas is still in the DOM once the data is in`);
    if (r.subs !== 0) fails.push(`${tag}: ${r.subs} surface(s) still asking PAI_RAF for frames`);
    if (reduce) {
      if (r.atOpen !== 1) fails.push(`${tag}: the scheduler drew ${r.atOpen} frame(s), not one still`);
      if (r.subscribed !== 0) fails.push(`${tag}: it subscribed to the loop instead of drawing one still`);
      if (r.floor !== 0) fails.push(`${tag}: --motion-asking-hold is ${r.floor}, not zeroed`);
      if (r.heldOpen) fails.push(`${tag}: it held the page for the floor anyway`);
    } else {
      if (r.subscribed !== 1) fails.push(`${tag}: it did not subscribe to the loop (PAI_RAF.size ${r.subscribed})`);
      if (!r.floor) fails.push(`${tag}: --motion-asking-hold is ${r.floor} — the account cannot be read`);
      if (!r.heldOpen) fails.push(`${tag}: it closed on the spot, so the reads it lists are never seen`);
    }
    /* THE FOURTH CLAIM, added 22 September: it is still moving when the floor ends.
     *
     * The settle decays the spin (`k = 1 - s` in draw()), so a fixed 900 ms settle meant a node
     * that answers in 30 ms flattened by ~930 ms and then showed a STILL FRAME for the other two
     * seconds of the three-second floor — the rAF loop running the whole time, drawing the same
     * picture. Reported by Tomas. Nothing above catches it: every other check here is about the DOM
     * at a moment, and `probe(30)` draws thirty frames without ever asking whether any two differ.
     *
     * So this one reads the canvas itself, twice, late, and requires the pixels to have changed.
     * Position-weighted rather than a plain alpha sum, because a rotation moves ink without
     * changing how much of it there is. */
    if (!reduce) {
      const moved = await h.page.evaluate(async () => {
        const A = window.PAI_ASKING, K = window.K;
        const sig = () => {
          const c = document.getElementById('askcv');
          if (!c) return null;
          const d = c.getContext('2d').getImageData(0, 0, c.width, c.height).data;
          let v = 0;
          for (let i = 3; i < d.length; i += 4) v = (v + d[i] * ((i >> 2) % 1013)) % 4294967296;
          return v;
        };
        const wait = ms => new Promise(res => setTimeout(res, ms));
        /* The floor probe above closed itself, and close() reschedules for the rest of the floor —
           so it is still `up`, and open() returns early on a surface that is already open. Wait for
           it to actually go before asking for a fresh episode, or this measures nothing and then
           reports on the previous episode's dying frames. */
        for (let i = 0; i < 60 && A.up(); i++) await wait(100);
        if (A.up()) return { stuck: true };
        A.open('moving', true);
        A.landed(K.S.issues);                    // the node answered at once, as a fixture does
        await wait(300);
        const early = sig();
        await wait(2300);                        // 2.6 s into a 3 s floor
        const late1 = sig();
        await wait(250);
        const late2 = sig();
        const upLate = A.up();
        A.close();
        return { early, late1, late2, upLate };
      });
      if (moved.stuck) {
        fails.push(`${tag}: the previous episode never closed, so this could not be measured`);
      } else if (moved.early === null || moved.late1 === null) {
        fails.push(`${tag}: the canvas drew nothing, so "still moving" cannot be read`);
      } else if (!moved.upLate) {
        fails.push(`${tag}: gone 2.85 s into a ${r.floor} ms floor`);
      } else if (moved.late1 === moved.late2) {
        fails.push(`${tag}: identical pixels at 2.6 s and 2.85 s — it settles early and holds a `
          + `still frame for the rest of the floor`);
      } else {
        said.push(`${tag}: still moving at 2.85 s of the ${r.floor} ms floor`);
      }
    }
    said.push(`${tag}: ${reduce ? 'one still frame, no subscription, no floor'
      : `subscribed to the one loop, held for ${r.floor} ms`}`
      + ` · ${r.cost.frames} probe frames, mean ${r.cost.mean.toFixed(2)} ms, `
      + `worst ${r.cost.worst.toFixed(2)} ms`);
    await h.browser.close();
  }
  /* THE LAYOUT, added 28 September: on a phone and on a portrait screen the frame and the list of reads
     stack, and the list starts below the frame. They used to overlap: the frame kept its 1.55 ratio under
     a max-height, its row came out shorter than it, and the heading and the first reads were drawn over
     its bottom edge (Tomas). And the screen says what it is, PLANETAI loading, before anything answers. */
  for (const [w, hgt] of [[390, 844], [768, 1024], [1080, 1920]]) {
    /* A real first paint, with motion on so the floor holds it up long enough to measure: opened by hand
       over a page that has already loaded, the phone's overlap did not happen, and the check passed on it. */
    const h = await open(tagged({ name: `asking_${w}`, view: 'now', w, state: 'populated' }), { reducedMotion: 'no-preference' });
    await h.page.setViewportSize({ width: w, height: hgt });
    await h.page.reload({ waitUntil: 'commit' });
    await h.page.waitForTimeout(1500);
    const g = await h.page.evaluate(() => {
      const r = s => document.querySelector(s).getBoundingClientRect();
      const up = window.PAI_ASKING && window.PAI_ASKING.up();
      const frame = r('#asking .frame'), aside = r('#asking .aside');
      return { up, frameBottom: frame.bottom, asideTop: aside.top, frameH: frame.height,
        brand: ((document.querySelector('#asking .brand') || {}).textContent || '').replace(/\s+/g, ' ').trim() };
    });
    await h.browser.close();
    if (!g.up) { fails.push(`at ${w}x${hgt} the loading state was already gone at 1.5 s, inside its floor`); continue; }
    if (g.asideTop < g.frameBottom - 0.5) fails.push(`at ${w}x${hgt} the reads start ${Math.round(g.frameBottom - g.asideTop)} px inside the frame`);
    if (g.frameH < 160) fails.push(`at ${w}x${hgt} the frame is ${Math.round(g.frameH)} px tall, too short for the globe`);
    if (!/^PLANETAI loading$/i.test(g.brand)) fails.push(`the loading state does not say PLANETAI loading: "${g.brand}"`);
  }
  said.push('the frame and the reads stack without overlapping at 390x844, 768x1024 and 1080x1920, under PLANETAI loading');
  for (const f of fails) console.log('FAIL asking:', f);
  if (!fails.length) said.forEach(s => console.log('  asking ·', s));
  process.exit(fails.length ? 1 : 0);
}

/* ------------------------------------------------------------------ T-overflow
 *
 * A page that scrolls sideways on a phone is the defect a household reports as "it is broken", and
 * it is invisible to every other check in this file: every box can be the right size and the
 * document still be wider than the screen, because one `1fr` track floored at its max-content and
 * pushed the rest along. So this asks the page itself, at the one width that matters and two that
 * catch it early, in every combination of view, mode and register the page can be in.
 *
 * NOT IN `make test`, and the prompt that asked for it wanted it there. It cannot be: Playwright
 * lives in planetai-design's node_modules, not this repo's, and tests/all must run on a node with
 * neither — the same reason gate.sh is not in it. It runs in gate.sh, before shipping, which is
 * where every other Playwright check in this repo runs. Raised for Tomas rather than either
 * breaking CI or quietly not doing it.
 *
 *   node tests/visual/measure.mjs overflow            every combination
 *   node tests/visual/measure.mjs overflow now wall   named views only
 */
/* PAI_OVER_W=1180 measures another width, e.g. the 340 px pane between 860 and 1279. */
const OVER_W = (process.env.PAI_OVER_W || '390,768,1440').split(',').map(Number);
const OVER_V = ['now', 'historical', 'network', 'wall', 'arrange', 'setup'];
const OVER_M = ['simple', 'advanced', 'learn'];
const OVER_R = ['paper', 'dark'];
/* The ask pane takes 400 px, 340 px or the bottom of the screen; every view it opens on is measured with it open too. */
const OVER_ASK = [false, true];

async function overflow(views) {
  const want = views && views.length && views[0] !== 'all' ? views : OVER_V;
  const bad = [];
  let n = 0;
  for (const view of want) {
    for (const w of OVER_W) for (const mode of OVER_M) for (const reg of OVER_R) for (const ask of OVER_ASK) {
      if (ask && view === 'wall') continue;             /* the wall has no header and never draws the pane */
      const job = { name: `overflow_${view}_${w}_${mode}_${reg}${ask ? '_ask' : ''}`, view, w,
        state: 'populated', mode, register: reg, ask };
      const { browser, page } = await open(job);
      try {
        const got = await page.evaluate(() => ({
          scroll: document.documentElement.scrollWidth,
          client: document.documentElement.clientWidth,
        }));
        n += 1;
        /* One pixel of slack: a sub-pixel layout can report 390.5 as 391 and that is a rounding
           artefact, not a page a thumb can push sideways. Two is a bug. */
        if (got.scroll > got.client + 1) {
          bad.push({ view, w, mode, reg, ask, over: got.scroll - got.client, scroll: got.scroll });
        }
      } finally { await browser.close(); }
    }
    process.stderr.write(`  ${view} \u00b7 ${view === 'wall' ? OVER_W.length * OVER_M.length * OVER_R.length : OVER_W.length * OVER_M.length * OVER_R.length * OVER_ASK.length} combinations\n`);
  }
  if (!bad.length) {
    console.log(`  no horizontal overflow in ${n} combinations `
      + `(${want.length} views \u00d7 ${OVER_W.join('/')} \u00d7 ${OVER_M.join('/')} \u00d7 paper/dark)`);
    return;
  }
  console.error(`  ${bad.length} of ${n} combinations scroll sideways:`);
  for (const b of bad) {
    console.error(`    ${b.view} @ ${b.w} \u00b7 ${b.mode} \u00b7 ${b.reg}${b.ask ? ' \u00b7 pane open' : ''}`
      + ` \u2014 document is ${b.scroll}px, ${b.over}px past the viewport`);
  }
  process.exit(1);
}

/* ------------------------------------------------------------------ simple, the three questions
 *
 * Simple on Now is the lead, the ask, the ground, the node's paragraph and the also line, and nothing
 * the keeper reads: no ladder, no matrix, no figures, no stage headings. Hiding them with CSS would
 * pass a screenshot and still hand a screen reader the whole advanced page, so this asks the DOM.
 * Then it presses the also line: the lead must become that issue's hero, say it is the reader's
 * choice and not the node's, survive a poll, and go back to the node's pick on `back`.
 * Horizontal scroll in simple at 390/768/1440 in both registers is `overflow`'s job, not this one's. */
async function simple() {
  const fails = [];
  for (const w of [390, 1440]) {
    const job = tagged({ name: `simple_${w}`, view: 'now', w, state: 'populated', mode: 'simple' });
    const h = await open(job);
    const got = await h.page.evaluate(() => ({
      lv: document.body.dataset.lv,
      banned: ['#rail', '.rail', '#matrix', '#figures', '.stagehead']
        .filter(q => document.querySelector(q)).join(' '),
      /* hidden by data-lv, not deleted: in the DOM, drawn nowhere */
      shown: ['.pill.prov', '.lead .leadk', '.lead .why', '.lead .askref', '.gridkey:not(.plainkey)', '.ctlrule']
        .filter(q => [...document.querySelectorAll(q)].some(e => e.getClientRects().length)).join(' '),
      lead: (document.querySelector('.lead') || {}).id || null,
      also: [...document.querySelectorAll('#also [data-hero]')].map(b => b.getAttribute('data-hero')),
    }));
    if (got.lv !== 'simple') fails.push(`${w}: body is data-lv=${got.lv}, not simple`);
    if (got.banned) fails.push(`${w}: simple still has ${got.banned} in the DOM`);
    if (got.shown) fails.push(`${w}: simple still draws ${got.shown}`);
    if (!got.also.length) { fails.push(`${w}: no also line to press`); await h.browser.close(); continue; }
    const want = got.also[0];
    await h.page.click(`#also [data-hero="${want}"]`);
    await h.page.waitForTimeout(400);
    const swapped = await h.page.evaluate(() => ({
      lead: (document.querySelector('.lead') || {}).id,
      pin: !!document.querySelector('.lead .eb .pin'),
      rule: !!document.querySelector('.lead .herorule'),
    }));
    if (swapped.lead !== `band-${want}`) fails.push(`${w}: pressing ${want} drew ${swapped.lead}`);
    if (!swapped.pin) fails.push(`${w}: the lead does not say it is the reader's choice`);
    await h.page.evaluate(() => window.PAI_REFRESH.now());
    await h.page.waitForTimeout(700);
    const polled = await h.page.evaluate(() => (document.querySelector('.lead') || {}).id);
    if (polled !== `band-${want}`) fails.push(`${w}: a poll undid the choice (${polled})`);
    await h.page.evaluate(() => { const b = document.querySelector('.lead .eb .back'); if (b) b.click(); });
    await h.page.waitForTimeout(400);
    const back = await h.page.evaluate(() => (document.querySelector('.lead') || {}).id);
    if (back !== got.lead) fails.push(`${w}: back drew ${back}, not the node's pick ${got.lead}`);
    if (!fails.length) console.log(`  simple @ ${w}: nothing of advanced in the DOM; ${got.lead} -> `
      + `band-${want}${swapped.rule ? ' (with its rule)' : ''}, held across a poll, back to ${back}`);
    await h.browser.close();
  }
  for (const f of fails) console.log('FAIL simple:', f);
  process.exit(fails.length ? 1 : 0);
}

/* ------------------------------------------------------------------ the ask pane
 *
 * Three things the page owes the pane, asked of the page itself: with no model it still searches the
 * documentation and shows the two ways to give it a voice; with one, a request that reaches for a
 * setting draws a card saying what it is now, what it would be, what leaves and how to undo it, and
 * asks for the token rather than writing; and nothing the pane does sends a write to /settings.
 * Horizontal scroll with the pane open is `overflow`'s, which runs every view and mode with it on. */
async function askpane() {
  const fails = [];
  delete process.env.PAI_ASK_MODEL;
  let h = await open(tagged({ name: 'askpane_none', view: 'now', w: 1440, state: 'populated', ask: true }));
  const none = await h.page.evaluate(async () => {
    const p = document.getElementById('askpane');
    const f = p && p.querySelector('[data-ask-find]');
    if (f) { f.elements.q.value = 'map_tiles'; f.requestSubmit(); }
    await new Promise(r => setTimeout(r, 400));
    return { shown: !!(p && !p.hidden && p.getClientRects().length), body: document.body.classList.contains('askopen'),
      cards: p ? p.querySelectorAll('.nomodel .card pre').length : 0, find: !!f,
      pull: p ? /agent local pull qwen3\.5:4b/.test(p.textContent) : false,
      mcp: p ? /claude mcp add/.test(p.textContent) : false,
      hits: p ? p.querySelectorAll('#ask-hits .hit').length : 0 };
  });
  await h.browser.close();
  if (!none.shown || !none.body) fails.push('with ?ask=1 the pane is not drawn');
  if (none.cards !== 3 || !none.pull || !none.mcp) fails.push(`the no-model state lacks its three cards: ${JSON.stringify(none)}`);
  if (!none.find || !none.hits) fails.push(`the no-model state's search found nothing for map_tiles: ${JSON.stringify(none)}`);

  process.env.PAI_ASK_MODEL = 'qwen3.5:4b';
  h = await open(tagged({ name: 'askpane_model', view: 'now', w: 1440, state: 'populated', ask: true }));
  const writes = [];
  h.page.on('request', r => { if (r.method() !== 'GET' && /\/settings|\/actions/.test(r.url())) writes.push(`${r.method()} ${r.url()}`); });
  const got = await h.page.evaluate(async () => {
    try { localStorage.removeItem('planetai_admin'); } catch (e) { /* none to remove */ }
    for (let i = 0; i < 20 && !document.querySelector('#askpane [data-ask-send]'); i++) await new Promise(r => setTimeout(r, 100));
    const f = document.querySelector('#askpane [data-ask-send]');
    if (!f) return { composer: false };
    const chips = f.querySelectorAll('[data-ask-chip]').length;
    f.elements.q.value = 'turn the satellite map on';
    f.requestSubmit();
    for (let i = 0; i < 30 && !document.querySelector('#askpane [data-ask-set]'); i++) await new Promise(r => setTimeout(r, 100));
    const card = document.querySelector('#askpane [data-ask-set]');
    const p = document.getElementById('askpane');
    return { composer: true, chips, head: /qwen3\.5:4b · runs on this machine/.test(p.textContent),
      card: card && card.dataset.askSet, text: card ? card.textContent : '',
      ledger: /on this machine/.test((p.querySelector('.ledger') || {}).textContent || ''),
      kept: (sessionStorage.getItem('planetai_ask_thread') || '').includes('turn the satellite map on'),
      answer: /Nothing changed/.test(p.textContent),
      folded: !!p.querySelector('.ledger details:not([open]) summary'),
      fresh: !!p.querySelector('[data-ask-new]') };
  });
  await h.page.screenshot({ path: path.join(OUT, 'askpane_model_1440.png') });
  // New conversation: one press, and the pane is as it was before the first question (Tomas, 28 Sep).
  const cleared = await h.page.evaluate(async () => {
    const b = document.querySelector('#askpane [data-ask-new]');
    if (!b) return null;
    b.click();
    await new Promise(r => setTimeout(r, 50));
    const p = document.getElementById('askpane');
    return { msgs: p.querySelectorAll('.msg').length, button: !!p.querySelector('[data-ask-new]'),
      composer: !!p.querySelector('[data-ask-send]'), stored: sessionStorage.getItem('planetai_ask_thread'),
      focus: document.activeElement && document.activeElement.id };
  });
  await h.page.screenshot({ path: path.join(OUT, 'askpane_cleared_1440.png') });
  /* While the node works on an answer the pane draws the loading state's globe, turning on the page's one
     loop, with the model and the seconds; when the answer lands the globe goes, and so does its frame. */
  process.env.PAI_ASK_SLOW = '1500';
  const wait = await h.page.evaluate(async () => {
    const f = document.querySelector('#askpane [data-ask-send]');
    /* The page's own loading state holds its floor with motion on, and leaving the loop mid-count
       would cancel the globe's one subscriber out. */
    for (let i = 0; i < 60 && window.PAI_ASKING.up(); i++) await new Promise(r => setTimeout(r, 100));
    const before = window.PAI_RAF.size;
    const chipsOf = () => [...document.querySelectorAll('#askpane [data-ask-chip]')].map(b => b.getAttribute('data-ask-chip'));
    const chips0 = chipsOf();
    document.querySelector('#askpane [data-ask-chip]').click();
    await new Promise(r => setTimeout(r, 1100));
    const cv = document.querySelector('#askpane .msg.node:last-child canvas.askglobe');
    const during = { globe: !!cv, drawn: !!(cv && cv.width > 1), subs: window.PAI_RAF.size - before, reduced: window.PAI_RAF.reduced(),
      says: ((document.querySelector('#askpane .thinking') || {}).textContent || '').trim() };
    for (let i = 0; i < 40 && document.querySelector('#askpane canvas.askglobe'); i++) await new Promise(r => setTimeout(r, 100));
    await new Promise(r => setTimeout(r, 50));
    return { chips0, chips1: chipsOf(), during, after: { globe: !!document.querySelector('#askpane canvas.askglobe'), subs: window.PAI_RAF.size - before,
      answer: /Nothing changed/.test(document.querySelector('#askpane .msg.node:last-child').textContent) } };
  });
  delete process.env.PAI_ASK_SLOW;
  await h.browser.close();
  if (!wait.during.globe || !wait.during.drawn) fails.push(`while the node worked the pane drew no globe: ${JSON.stringify(wait.during)}`);
  /* Under reduced motion PAI_RAF draws the globe once, still, and subscribes nothing: `drawn` above is that frame. */
  if (wait.during.subs !== (wait.during.reduced ? 0 : 1))
    fails.push(`the waiting globe has ${wait.during.subs} subscriber(s) on the page's loop with reduced motion ${wait.during.reduced ? 'on' : 'off'}`);
  if (!/^asking qwen3\.5:4b · \d+ s$/.test(wait.during.says)) fails.push(`the waiting line should say which model and how long: "${wait.during.says}"`);
  /* The three questions turn when an answer lands, and the one just asked is not offered again. */
  if (wait.chips1.length !== 3 || wait.chips1.includes(wait.chips0[0]) || wait.chips1.join('|') === wait.chips0.join('|'))
    fails.push(`after an answer the questions should turn and drop the one asked: before ${JSON.stringify(wait.chips0)}, after ${JSON.stringify(wait.chips1)}`);
  if (wait.after.globe || wait.after.subs !== 0 || !wait.after.answer)
    fails.push(`once the answer landed the globe should be gone and off the loop: ${JSON.stringify(wait.after)}`);
  if (!got.composer) fails.push('with a model running the pane draws no composer');
  else {
    if (got.chips !== 3) fails.push(`the composer should open with three of the node's questions, got ${got.chips}`);
    if (!got.head) fails.push('the header does not say which model and that it runs on this machine');
    if (got.card !== 'MAP_TILES' || !/off/.test(got.text) || !/on/.test(got.text) || !/tile server/.test(got.text)
      || !/Set MAP_TILES back to off/.test(got.text)) fails.push(`MAP_TILES did not become a card with now, proposed, what leaves and undo: ${got.text.slice(0, 200)}`);
    if (!/needs your token/.test(got.text)) fails.push('with no token held the card does not ask for one');
    if (!got.ledger || !got.answer) fails.push('the answer or its ledger line did not arrive');
    if (!got.kept) fails.push('the thread is not in sessionStorage, so a reload in this tab loses it');
    if (!got.folded) fails.push('the tools an answer read are not folded behind one line');
    if (!got.fresh) fails.push('a thread with an answer in it offers no new conversation');
    if (!cleared) fails.push('new conversation could not be pressed');
    else if (cleared.msgs || cleared.button || !cleared.composer || cleared.stored !== '[]' || cleared.focus !== 'ask-q')
      fails.push(`new conversation did not leave an empty pane ready for a question: ${JSON.stringify(cleared)}`);
  }
  if (writes.length) fails.push(`the pane wrote: ${writes.join(', ')}`);

  /* An online model first: the header, every answer's ledger line and the fine print must say so. */
  process.env.PAI_ASK_ONLINE = '1';
  h = await open(tagged({ name: 'askpane_online', view: 'now', w: 1440, state: 'populated', ask: true }));
  const on = await h.page.evaluate(async () => {
    try { sessionStorage.removeItem('planetai_ask_thread'); } catch (e) { /* none */ }
    for (let i = 0; i < 20 && !document.querySelector('#askpane [data-ask-send]'); i++) await new Promise(r => setTimeout(r, 100));
    const f = document.querySelector('#askpane [data-ask-send]');
    if (!f) return {};
    f.elements.q.value = 'how is it'; f.requestSubmit();
    for (let i = 0; i < 30 && !document.querySelector('#askpane .ledger .out'); i++) await new Promise(r => setTimeout(r, 100));
    const p = document.getElementById('askpane');
    return { head: (p.querySelector('.ah') || {}).textContent || '', ledger: (p.querySelector('.ledger') || {}).textContent || '',
      fine: (p.querySelector('.fine') || {}).textContent || '' };
  });
  await h.browser.close();
  delete process.env.PAI_ASK_ONLINE;
  if (!/runs online at api\.anthropic\.com/.test(on.head || '') || !/leave your network/.test(on.head || ''))
    fails.push(`with an online model first the header does not say so: ${(on.head || '').slice(0, 160)}`);
  if (!/claude-x · runs online at api\.anthropic\.com/.test(on.ledger || '')) fails.push(`the answer's ledger does not say it came from online: ${on.ledger}`);
  if (!/provider/.test(on.fine || '')) fails.push('the fine print does not say an online provider keeps what its terms say');
  delete process.env.PAI_ASK_MODEL;
  for (const f of fails) console.log('FAIL askpane:', f);
  if (!fails.length) console.log(`  askpane: no model = search (${none.hits} hits) and three cards; while it works, the globe turns; with one, MAP_TILES is a card `
    + 'with now, proposed, what leaves and undo, asking for the token; nothing written; an online model says so in the header, the ledger and the fine print');
  process.exit(fails.length ? 1 : 0);
}

/* ------------------------------------------------------------------ learn, walked in the pane
 *
 * Learn's marks land in the ask pane as cards. From the first mark, Next must visit every mark this
 * view drew in the order a reader meets them (document order, foot last), each card must cite its
 * page by title and never by a repository path, and there is no learn panel of its own any more. */
async function learnwalk() {
  const fails = [];
  delete process.env.PAI_ASK_MODEL;
  const h = await open(tagged({ name: 'learnwalk', view: 'now', w: 1440, state: 'populated', mode: 'learn' }));
  const got = await h.page.evaluate(async () => {
    for (let i = 0; i < 30 && !document.querySelector('#page .q[data-learn]'); i++) await new Promise(r => setTimeout(r, 100));
    const order = [];
    document.querySelectorAll('#page .q[data-learn], #foot .q[data-learn]').forEach(b => {
      const k = b.getAttribute('data-learn'); if (!order.includes(k)) order.push(k);
    });
    const walk = document.querySelector('[data-learn-walk]');
    if (!walk) return { order, visited: [], srcs: [], panel: !!document.getElementById('learnpanel') };
    walk.click();
    const visited = [], srcs = [];
    for (let i = 0; i < order.length; i++) {
      await new Promise(r => setTimeout(r, 60));
      const card = document.querySelector('#askpane [data-learn-card]');
      if (!card) break;
      visited.push(card.getAttribute('data-learn-card'));
      srcs.push((card.querySelector('.src') || {}).textContent || '');
      const next = card.querySelector('[data-learn-step="1"]');
      if (next) next.click();
    }
    const cards = document.querySelectorAll('#askpane [data-learn-card]').length;
    return { order, visited, srcs, cards, panel: !!document.getElementById('learnpanel'),
      pane: document.body.classList.contains('askopen') };
  });
  await h.page.waitForTimeout(800);
  await h.page.screenshot({ path: path.join(OUT, 'learnwalk_1440.png') });
  await h.browser.close();
  if (got.panel) fails.push('the learn panel is still in the markup');
  if (!got.pane) fails.push('pressing a mark did not open the pane');
  if (!got.order.length) fails.push('learn mode drew no marks on Now');
  if (JSON.stringify(got.visited) !== JSON.stringify(got.order)) {
    const i = got.visited.findIndex((k, j) => k !== got.order[j]);
    fails.push(`the walk left page order at step ${i + 1}: page ${got.order.slice(Math.max(0, i - 1), i + 2)}, `
      + `walk ${got.visited.slice(Math.max(0, i - 1), i + 2)} (${got.visited.length} of ${got.order.length} visited)`);
  }
  const bad = got.srcs.filter(t => /\.md\b|docs\/site|^From \.?$/.test(t.trim()));
  if (bad.length || got.srcs.some(t => !/^From .+\.$/.test(t.trim()))) fails.push(`a card cites a path, not a title: ${bad[0] || got.srcs.find(t => !/^From .+\.$/.test(t.trim()))}`);
  if (got.cards !== 1) fails.push(`walking stacked ${got.cards} cards; it should replace the one it is on`);

  /* Leaving learn takes back what it brought. Pressed through the mode buttons, as a person does: the
     job above pins ?mode=learn in the URL, and the URL's mode outranks a press. Each case runs twice,
     because a switch that works once and not on the way back in is the usual way this page breaks.
     A: learn opened the pane, so leaving closes it. B: the person opened it first, so it stays open,
     without the card. */
  const h2 = await open(tagged({ name: 'learnoff', view: 'now', w: 1440, state: 'populated' }));
  const off = await h2.page.evaluate(async () => {
    const wait = async f => { for (let i = 0; i < 40 && !f(); i++) await new Promise(r => setTimeout(r, 50)); return f(); };
    const press = m => document.querySelector(`.seg.mode button[data-mode="${m}"]`).click();
    /* Cards are counted in the thread, not the markup: a closed pane keeps its last drawing hidden. */
    const state = () => ({ open: document.body.classList.contains('askopen'),
      cards: JSON.parse(sessionStorage.getItem('planetai_ask_thread') || '[]').filter(m => m.role === 'card').length });
    const walk = async () => {
      press('learn');
      await wait(() => document.querySelector('[data-learn-walk]'));
      document.querySelector('[data-learn-walk]').click();
      await wait(() => state().cards);
      return state();
    };
    const out = {};
    for (const round of [1, 2]) {
      out[`A${round} in`] = await walk();
      press('advanced'); await wait(() => !state().open);
      out[`A${round} out`] = state();
    }
    document.querySelector('.asktoggle[data-ask-toggle]').click();
    for (const round of [1, 2]) {
      out[`B${round} in`] = await walk();
      press('advanced'); await wait(() => !state().cards);
      out[`B${round} out`] = state();
    }
    return out;
  });
  await h2.browser.close();
  for (const [k, v] of Object.entries(off)) {
    const want = k.endsWith(' in') ? { open: true, cards: 1 } : { open: k[0] === 'B', cards: 0 };
    if (v.open !== want.open || v.cards !== want.cards)
      fails.push(`${k} of learn: the pane is ${v.open ? 'open' : 'closed'} with ${v.cards} card(s); `
        + `it should be ${want.open ? 'open' : 'closed'} with ${want.cards}`);
  }
  for (const f of fails) console.log('FAIL learnwalk:', f);
  if (!fails.length) console.log(`  learnwalk: ${got.order.length} marks on Now, visited in page order from the first, `
    + 'each card cited by its page title; one card, replaced as it walks. Leaving learn closes the pane it '
    + 'opened and keeps one the person opened, without the card, twice each');
  process.exit(fails.length ? 1 : 0);
}

async function probe(expr) {
  const h = await open(tagged({ name: 'probe', view: 'now', w: 1440, state: 'populated' }));
  const errs = [];
  h.page.on('pageerror', e => errs.push(String(e)));
  await h.page.waitForTimeout(500);
  console.log(JSON.stringify(await h.page.evaluate(expr)), errs.join(' | '));
  await h.browser.close();
}

const [cmd, ...rest] = process.argv.slice(2);
if (cmd === 'render') await render(rest.length ? rest : ['all']);
else if (cmd === 'steps') await steps();
else if (cmd === 'stall') await stall(rest[0] || 'now_populated_1440');
else if (cmd === 'press') await press();
else if (cmd === 'simple') await simple();
else if (cmd === 'askpane') await askpane();
else if (cmd === 'learnwalk') await learnwalk();
else if (cmd === 'probe') await probe(rest.join(' '));
else if (cmd === 'asking') await asking();
else if (cmd === 'plates') await plateShots(rest.length ? rest : ['all']);
else if (cmd === 'extend') await extend();
else if (cmd === 'anchors') await anchors();
else if (cmd === 'plate-list') plates().forEach(j => console.log(j.name + (j.full ? '  (+full)' : '')));
else if (cmd === 'sheets') await sheets();
else if (cmd === 'header') await header();
else if (cmd === 'targets') aTargets();
else if (cmd === 'audit') await audit(rest.length ? rest : ['all']);
else if (cmd === 'shots') await shots(rest.length ? rest : ['all']);
else if (cmd === 'analyse') { const f = A[rest[0]]; if (!f) { console.error('analyse: ' + Object.keys(A).join(' ')); process.exit(2); } f(); }
else if (cmd === 'overflow') await overflow(rest);
else if (cmd === 'list') jobs().forEach(j => console.log(j.name));
else { console.error('usage: measure.mjs render|shots|plates|plate-list|steps|stall|press|asking|extend|anchors|sheets|header|targets|audit|overflow|analyse|list');
  process.exit(2); }
