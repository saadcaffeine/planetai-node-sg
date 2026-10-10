#!/usr/bin/env node
/* Visual baselines for the node dashboard. Not run by `make lint`: it needs a browser.
 *
 *   python3 tools/shots.py            # builds the bundles, then calls this
 *
 * The page is loaded over http:// from a routed origin rather than file://, because the renderer
 * asks for `/static/<name>` and `/issues/fixtures/<name>` and both of those are absolute. Nothing
 * is served from a port: every request is fulfilled by playwright from disk, so two sessions
 * running this at once cannot collide, and there is no node to stand up and no database behind it.
 *
 * The route mirrors app/main.py's COMPANIONS exactly, including its refusals: `/static/<name>`
 * takes a NAME, so `/static/fonts/jetbrains-mono-latin.woff2` 404s here as it does on a node. That
 * is the one dead reference this project has decided to live with, and a baseline that quietly
 * resolved it would be a baseline of a page no household has.
 */
// playwright lives in the sibling planetai-design checkout, not here: a node's tarball has no
// node_modules and is not going to grow one for a tool no household runs. ESM resolves packages
// from the importing file's own tree and ignores NODE_PATH, so the path is passed in.
const { chromium } = await import(process.env.PLAYWRIGHT_ENTRY);
import { readFileSync, existsSync, mkdirSync, writeFileSync, readdirSync } from 'node:fs';
import { extname, basename } from 'node:path';

const [BUNDLES, OUT, ROOT] = process.argv.slice(2);
const STATIC = `${ROOT}/app/static`;
const ORIGIN = 'http://node.invalid';
const WIDTHS = [375, 768, 1440, 1920];
// --url: a node that is actually running, instead of a fixture routed from disk. Same assertions,
// real network, and one extra pass with no token at all — at SHARE_LEVEL=off that is what a phone
// on the house WiFi gets, and the page is supposed to say so rather than go blank.
const LIVE = process.env.NODE_URL || '';
const TOKEN = process.env.PAI_TOKEN || '';

const TYPES = { '.html': 'text/html', '.js': 'application/javascript', '.css': 'text/css',
                '.svg': 'image/svg+xml', '.json': 'application/json', '.woff2': 'font/woff2',
                '.ttf': 'font/ttf', '.txt': 'text/plain' };

// COMPANIONS, as app/main.py has it: a flat name, resolved in app/static and then in its fonts/
// subdirectory. Anything with a slash in it is not a name and is refused.
function companion(name) {
  if (name.includes('/')) return null;
  for (const p of [`${STATIC}/${name}`, `${STATIC}/fonts/${name}`]) if (existsSync(p)) return p;
  return null;
}


/* Two more renders, through the page's own controls.
 *
 * Out to the wall and back. The wall hides the header (R6), so the way back is the wall's own NOW
 * button and not the nav — clicking a nav button that is display:none waits for it to become
 * visible and never returns, which is how this first hung.
 */
async function reRender(page) {
  await page.click('nav.views button[data-view="wall"]', { timeout: 4000 }).catch(() => {});
  await page.waitForTimeout(150);
  await page.click('.wall .exit', { timeout: 4000 }).catch(() => {});
  await page.waitForTimeout(250);
}

const browser = await chromium.launch();
const rows = [];
let bad = 0;

async function pass(label, { url, token, width, route, view }) {
  const ctx = await browser.newContext({ viewport: { width, height: 1100 },
                                         deviceScaleFactor: 1, reducedMotion: 'reduce' });
  const page = await ctx.newPage();
  const errors = [], missed = [];
  page.on('pageerror', e => errors.push(String(e)));
  page.on('console', m => { if (m.type() === 'error') errors.push(m.text()); });
  if (token) await ctx.addInitScript(t => localStorage.setItem('planetai_admin', t), token);
  if (route) await page.route('**/*', route(missed));
  else page.on('response', r => { if (r.status() >= 400) missed.push(`${r.status()} ${new URL(r.url()).pathname}`); });

  await page.goto(url, { waitUntil: route ? 'load' : 'networkidle' });
  await page.waitForSelector('[data-component]', { timeout: 10000 }).catch(() => {});
  await page.evaluate(() => document.fonts.ready);
  await page.waitForTimeout(400);

  /* Render again, twice, before looking at anything.
   *
   * The page refreshes every twenty seconds and re-renders on every view switch, and the FIRST
   * render is the only one a screenshot ever saw. It hid a bug that broke the page for everybody:
   * render() replaces five mount points with outerHTML, the replacements did not carry the mounts'
   * ids, and so the second render threw on a null and the page stopped updating — Set up opened
   * empty because the throw happened before loadSetup() could run. Nothing static could see it.
   *
   * Switching views is how a person triggers it, so that is what this does.
   */
  await reRender(page);
  // reRender leaves the page on Now, so a pass for any other view has to go back to it — the first
  // run after reRender landed shot the wall passes on the Now view without noticing.
  if (view && view !== 'now') {
    await page.click(`nav.views button[data-view="${view}"]`, { timeout: 4000 }).catch(() => {});
    await page.waitForTimeout(400);
  }

  const seen = await page.evaluate(() => ({
    // the five mounts index.html declares. Each must still be there after three renders.
    mounts: ['hero', 'index', 'bands', 'place', 'loop', 'figures'].filter(id => !document.getElementById(id)),
    // whichever view is on screen has to have drawn something into it. Network was four hard-coded
    // boxes that the renderer never filled, on every node, for a whole release.
    emptyView: [...document.querySelectorAll('section.view.on')]
      .filter(v => !v.querySelector('[data-component]')).map(v => v.id),
    notes: document.querySelectorAll('#now .index ~ .note, #index-note').length,
    components: [...document.querySelectorAll('[data-component]')].map(e => e.dataset.component),
    broken: [...document.querySelectorAll('[data-component][data-error="1"]')].map(e => e.dataset.component),
    bands: [...document.querySelectorAll('[data-band]')].map(e => e.dataset.band),
    sideways: document.documentElement.scrollWidth > window.innerWidth + 1,
    height: document.documentElement.scrollHeight,
    hero: ((document.querySelector('.hero p.big') || {}).textContent || '').trim().slice(0, 90),
  }));
  const name = `${label}.jpg`;
  mkdirSync(OUT, { recursive: true });
  await page.screenshot({ path: `${OUT}/${name}`, fullPage: true, type: 'jpeg', quality: 72 });
  await ctx.close();
  return { name, seen, errors, missed };
}

/* What a reader with no token gets — judged by what THIS node's SHARE_LEVEL actually promises.
 *
 * At `off` a node refuses nine endpoints, the browser logs each refusal as a console error, and the
 * page draws the node's own sentence about it. A refusal is an answer, so that pass is judged on the
 * sentence and nothing else.
 *
 * At `open` there is no refusal to find: a wall screen on the house WiFi is supposed to work with no
 * token, which is the whole point of the level. Asserting the refusal anyway is how this printed ✗
 * against node #1 — which has been `open` since somebody set it in Set up — on every live render,
 * for a page that was behaving exactly as configured. A check that cannot pass is not a check.
 *
 * The level is read from the node rather than assumed: `/settings` is on the `off` allowlist, so it
 * answers without a token at every level, and a value set in the GUI overrides the one in .env —
 * which is why reading the .env would have given the wrong answer here too.
 */
async function shareLevel(base) {
  try {
    const d = await fetch(`${base}/settings`).then(r => r.json());
    const row = (d.runtime || []).find(k => k.key === 'SHARE_LEVEL');
    return String(row?.value ?? d.SHARE_LEVEL ?? 'off').trim().toLowerCase() || 'off';
  } catch { return 'off'; }   // unreachable node: the pass below will fail on its own terms
}

if (LIVE) {
  const level = await shareLevel(LIVE);
  const r = await pass('live-refused-1440', { url: LIVE, token: '', width: 1440 });
  /* `off` promises a sentence; anything else promises a working page, so judge it like the rest —
   * with one refusal allowed, and only one. `/place/geojson` needs a token at EVERY level: it is the
   * exact shape of the buildings around a household, the one thing SHARE_LEVEL never hands out. The
   * plan card is built for that and draws its ground with a line saying which, so the 403 is the
   * design working. The browser still logs it, so it has to be named here or an `open` node can
   * never pass. Anything else refused at `open` is a finding. */
  const expected = m => m.endsWith('/place/geojson');
  const said = level === 'off'
    ? /not sharing/i.test(r.seen.hero)
    : r.errors.filter(e => !/\b403\b/.test(e)).length === 0 && r.missed.every(expected)
      && !r.seen.broken.length && !r.seen.sideways && !r.seen.mounts.length;
  if (!said) bad++;
  rows.push({ ...r, ok: said });
  console.log(`  ${said ? '✓' : '✗'} ${'live-refused-1440.jpg'.padEnd(34)} no token at SHARE_LEVEL=${level}, and the page `
    + (level === 'off' ? 'says why' : 'works — that is what open means'));
  for (const view of ['now', 'wall', 'network']) {
    for (const width of WIDTHS) {
      const r2 = await pass(`live-${view}-${width}`, {
        url: LIVE + (view === 'wall' ? '/?theme=dark' : '/'), token: TOKEN, width, view });
      const ok = !r2.errors.length && !r2.seen.broken.length && !r2.seen.sideways && !r2.missed.length
        && !r2.seen.mounts.length && r2.seen.notes <= 1 && !r2.seen.emptyView.length;
      if (!ok) bad++;
      rows.push({ ...r2, ok });
      console.log(`  ${ok ? '✓' : '✗'} ${r2.name.padEnd(34)} ${String(r2.seen.height).padStart(5)}px tall  `
        + `${[...new Set(r2.seen.components)].length} components  ${r2.seen.hero}`
        + (r2.seen.sideways ? '  SCROLLS SIDEWAYS' : '')
        + (r2.seen.broken.length ? `  BROKEN: ${r2.seen.broken.join(',')}` : '')
        + (r2.seen.mounts.length ? `  LOST MOUNT: ${r2.seen.mounts.join(',')}` : '')
        + (r2.seen.emptyView.length ? `  EMPTY VIEW: ${r2.seen.emptyView.join(',')}` : '')
        + (r2.seen.notes > 1 ? `  ${r2.seen.notes} index notes` : '')
        + (r2.missed.length ? `  ${[...new Set(r2.missed)].join(' | ')}` : '')
        + (r2.errors.length ? `  ERROR: ${r2.errors[0].slice(0, 90)}` : ''));
    }
  }
}

for (const f of LIVE ? [] : readdirSync(BUNDLES).filter(n => n.endsWith('.json'))) {
  const fixture = basename(f, '.json');
  const body = readFileSync(`${BUNDLES}/${f}`, 'utf8');
  for (const view of ['now', 'wall', 'network']) {
    for (const width of WIDTHS) {
      // reducedMotion on every pass: the satellite loop is the only thing that moves, and a shot
      // taken mid-cut is a shot of nothing. The loop itself is proven by tests, not by a picture.
      const ctx = await browser.newContext({ viewport: { width, height: 1100 },
                                             deviceScaleFactor: 1, reducedMotion: 'reduce' });
      const page = await ctx.newPage();
      const errors = [];
      page.on('pageerror', e => errors.push(String(e)));
      page.on('console', m => { if (m.type() === 'error') errors.push(m.text()); });

      const missed = [];
      await page.route('**/*', route => {
        const url = new URL(route.request().url());
        if (url.origin !== ORIGIN) return route.abort();
        if (url.pathname === '/') {
          return route.fulfill({ contentType: 'text/html', body: readFileSync(`${STATIC}/index.html`, 'utf8') });
        }
        if (url.pathname === `/issues/fixtures/${fixture}`) {
          return route.fulfill({ contentType: 'application/json', body });
        }
        if (url.pathname.startsWith('/static/')) {
          const p = companion(url.pathname.slice('/static/'.length));
          if (!p) { missed.push(url.pathname); return route.fulfill({ status: 404, body: 'not a name this node serves' }); }
          // The ground follows the page's register, as app/main.py's static_file() does it. A node
          // draws it from NODE_LAT/NODE_LON; there are no coordinates here, so this is the shipped
          // file with its root attribute swapped — the same branch a node takes before setup.
          // Without this the fixture shots show a dark ground on the paper page, which is the bug
          // the variant exists to fix, and a design round would be looking at a stale picture.
          if (p.endsWith('node-ground.svg') && url.searchParams.get('variant') === 'paper') {
            return route.fulfill({ contentType: 'image/svg+xml',
              body: readFileSync(p, 'utf8').replace('data-variant="dark"', 'data-variant="paper"') });
          }
          return route.fulfill({ contentType: TYPES[extname(p)] || 'application/octet-stream', body: readFileSync(p) });
        }
        // Everything else is a request the fixture path is not supposed to make. Record it: a
        // renderer that reaches the network with ?fixture= set has stopped being renderable from a
        // fixture alone, which is the property that makes a design round possible.
        missed.push(url.pathname);
        return route.fulfill({ status: 404, body: 'no' });
      });

      // `&theme=dark` is how a wall screen boots (dashboard.js's boot()), so the wall is reached the
      // way a wall reaches it rather than by clicking the nav after the fact — which raced with
      // boot() and produced a page with two views' DOM in it.
      await page.goto(`${ORIGIN}/?fixture=${fixture}${view === 'wall' ? '&theme=dark' : ''}`, { waitUntil: 'load' });
      await page.waitForSelector('[data-component]', { timeout: 10000 }).catch(() => {});
      await page.evaluate(() => document.fonts.ready);
      await page.waitForTimeout(250);
      // Render twice more before looking — see the note in pass() above. The first render is the
      // only one a screenshot ever saw, and that is where the lost mounts hid.
      await reRender(page);
      if (view !== 'now') await page.click(`nav.views button[data-view="${view}"]`).catch(() => {});
      await page.waitForTimeout(400);

      const seen = await page.evaluate(() => ({
        mounts: ['hero', 'index', 'bands', 'place', 'loop', 'figures'].filter(id => !document.getElementById(id)),
    // whichever view is on screen has to have drawn something into it. Network was four hard-coded
    // boxes that the renderer never filled, on every node, for a whole release.
    emptyView: [...document.querySelectorAll('section.view.on')]
      .filter(v => !v.querySelector('[data-component]')).map(v => v.id),
        notes: document.querySelectorAll('#now .index ~ .note, #index-note').length,
        components: [...document.querySelectorAll('[data-component]')].map(e => e.dataset.component),
        broken: [...document.querySelectorAll('[data-component][data-error="1"]')].map(e => e.dataset.component),
        bands: [...document.querySelectorAll('[data-band]')].map(e => e.dataset.band),
        sideways: document.documentElement.scrollWidth > window.innerWidth + 1,
        height: document.documentElement.scrollHeight,
      }));
      // jpeg, like the shots already in docs/design/shots: these are committed so a review has
      // something to look at, and a full-page PNG of a 9800px page is megabytes in a tarball that
      // goes to households. The assertions above are what is actually checked; the picture is for
      // a person.
      const name = `${fixture}-${view}-${width}.jpg`;
      mkdirSync(OUT, { recursive: true });
      await page.screenshot({ path: `${OUT}/${name}`, fullPage: true, type: 'jpeg', quality: 72 });

      // The mono is expected to 404 at its nested path, by decision (docs/archive/handoffs/HANDOFF_issues.md §2).
      const unexpected = missed.filter(p => p !== '/static/fonts/jetbrains-mono-latin.woff2');
      const ok = !errors.length && !seen.broken.length && !seen.sideways && !unexpected.length
        && !seen.mounts.length && seen.notes <= 1 && !seen.emptyView.length;
      if (!ok) bad++;
      rows.push({ name, ok, height: seen.height, sideways: seen.sideways,
                  components: [...new Set(seen.components)].sort(), bands: seen.bands,
                  broken: seen.broken, errors, unexpected });
      console.log(`  ${ok ? '✓' : '✗'} ${name.padEnd(34)} ${String(seen.height).padStart(5)}px tall  `
        + `${[...new Set(seen.components)].length} components`
        + (seen.sideways ? '  SCROLLS SIDEWAYS' : '')
        + (seen.broken.length ? `  BROKEN: ${seen.broken.join(',')}` : '')
        + (seen.mounts.length ? `  LOST MOUNT: ${seen.mounts.join(',')}` : '')
        + (seen.emptyView.length ? `  EMPTY VIEW: ${seen.emptyView.join(',')}` : '')
        + (seen.notes > 1 ? `  ${seen.notes} index notes` : '')
        + (unexpected.length ? `  FETCHED: ${[...new Set(unexpected)].join(',')}` : '')
        + (errors.length ? `  ERROR: ${errors[0].slice(0, 90)}` : ''));
      await ctx.close();
    }
  }
}
await browser.close();
writeFileSync(`${OUT}/shots.json`, JSON.stringify(rows, null, 2) + '\n');
console.log(`\n  ${rows.length} shots in ${OUT}, ${bad} with something wrong`);
process.exit(bad ? 1 : 0);
