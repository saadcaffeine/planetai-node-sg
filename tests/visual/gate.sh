#!/usr/bin/env bash
# The visual gate for the production dashboard: the same script that measured Phase 1, run against
# app/static with the committed fixture, and compared against numbers THIS rig measured against
# THIS page — never against docs/design/REDESIGN_2026-09_ground.md's Phase 1 numbers, which were
# captured against a container nobody can reconstruct and are not comparable to a hermetic render.
#
#   bash tests/visual/gate.sh
#
# Not in tests/all: Playwright lives in planetai-design's node_modules, not this repo's, so `make
# test` must not depend on it. CI runs it as its own job, `visual` in .github/workflows/lint.yml,
# against planetai-design at data/frozen_layer.txt's pin. Until 28 Sep 2026 nothing did, and it
# was red from v0.73 to v0.75.6 under a green release. Run it before shipping as well.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/../.."

# path.resolve(ROOT, PAI_DESIGN_REPO) in measure.mjs now resolves a relative PAI_DESIGN_REPO for
# that script — createRequire() there demands an absolute path and throws on a relative one, which
# used to be gate.sh's whole failure. This line does the same resolution here, so the -d check
# below (which runs before measure.mjs is ever started) checks the same directory measure.mjs will
# actually use, and this file is correct on its own rather than depending on the callee's fix.
DESIGN="$(cd "${PAI_DESIGN_REPO:-../planetai-design}" 2>/dev/null && pwd)" || DESIGN=""
[ -n "$DESIGN" ] && [ -d "$DESIGN/node_modules/playwright" ] || { echo "  playwright is not in ${PAI_DESIGN_REPO:-../planetai-design} (resolved: ${DESIGN:-<not found>}); npm install there"; exit 2; }

OUT="${PAI_OUT:-/tmp/pai-gate}"; mkdir -p "$OUT"
export PAI_STATIC="$PWD/app/static" PAI_OUT="$OUT" PAI_DESIGN_REPO="$DESIGN" PAI_Q="?fixture=node1-2026-10-06-figures"

# now_populated_390/1440: everything T1-T5 below is read off these two. wall_populated_1920_dark:
# T7 and the 1,080 px check. All three go through serveNodeAPI() in measure.mjs — no node, no
# container, no network; see that function's own comment for what changed on 2026-09 and why.
node tests/visual/measure.mjs render now_populated_1440 now_populated_390 >/dev/null
PAI_Q="?fixture=node1-2026-10-06-figures&view=wall" node tests/visual/measure.mjs render wall_populated_1920_dark >/dev/null
# The ruler is now inside the railfold and visible only with ?worth=1. PAI_TAG appends _worth1 to the
# output filename, so the measurement is stored as now_populated_1440_worth1.json, which the ruler check reads.
PAI_TAG=worth1 PAI_Q="$PAI_Q&worth=1" node tests/visual/measure.mjs render now_populated_1440 >/dev/null
node tests/visual/measure.mjs shots now_populated_1440 now_populated_390 wall_populated_1920_dark >/dev/null

# A press must redraw. Every check below this line measures one render, and since v0.55 a control
# is a re-render rather than a document load — so a dead control changes the URL, fires no request,
# and leaves every static number here exactly as it was. That is not hypothetical: v0.55 shipped
# with the dial dead and this gate was green. This presses it.
node tests/visual/measure.mjs press
# Simple is the three questions: nothing of advanced in the DOM, and the also line swaps the lead and back.
node tests/visual/measure.mjs simple
# The ask pane: with no model it searches and shows two ways in; with one, a change is a card, never a write.
node tests/visual/measure.mjs askpane
# Learn lands in the pane: the walk visits every mark in page order and each card cites its page by title.
node tests/visual/measure.mjs learnwalk

# The loading state: it stops when the data is in, the canvas leaves the tree, and reduced motion
# draws one still frame instead of subscribing to the loop. Prints what a frame cost, both ways.
node tests/visual/measure.mjs asking

# A pack this file has never heard of: does its section draw, in its own stage and order, and do the
# targets survive it. Also the one check that fails when the page is too PERMISSIVE — a stranger
# drawing a fifth card kind has to show up, or "four kinds and no fifth" is only a sentence.
node tests/visual/measure.mjs extend

# Every in-page link the page writes, followed. The hash is how this page routes, so an anchor and a
# view are the same string; `#stage-act` routed to a view of that name and drew a blank page in
# v0.71. Static checks cannot see it — the id is built from a template and the failure is the router.
node tests/visual/measure.mjs anchors
# The same walk on Network and Historical: an anchor there sent the reader back to Now, because the
# hash that replaced `#network` named no view and readView() fell through to 'now'.
PAI_VIEW=network node tests/visual/measure.mjs anchors
PAI_VIEW=historical node tests/visual/measure.mjs anchors

node - <<'JS'
const fs = require('fs'), out = process.env.PAI_OUT;
const j = n => JSON.parse(fs.readFileSync(`${out}/${n}.json`, 'utf8'));
const fails = [];

// T1's five legs (sentence, numeral, state, ask, as-of), read the same way measure.mjs's own
// `targets` command reads them — see ROLES and role() there. A target with no script behind it is
// an opinion, so this duplicates that script's selectors rather than re-deciding what T1 means.
const ROLES = {
  sentence: ['[data-component="sentence"]', '[data-role="sentence"]', '.hero p.big', '.wall p.big'],
  numeral: ['[data-role="numeral"]', 'b.mono'],
  state: ['[data-component="kicker"] .state', '[data-role="state"]', '.hero .k .state', '.wall .k .state'],
  ask: ['[data-component="askStrip"]', '[data-role="ask"]', '.askstrip'],
  asof: ['[data-role="asof"]', '.asof', '#headprov .asof', '.wall .foot'],
};
function has(e, cls) { return (e.cls || '').split(/\s+/).includes(cls); }
function matches(e, sel) {
  const M = sel.match(/^\[data-component="([^"]+)"\](?:\s+(.+))?$/);
  if (M) return M[2] ? false : e.dc === M[1];
  const R = sel.match(/^\[data-role="([^"]+)"\]$/);
  if (R) return e.drole === R[1];
  const parts = sel.trim().split(/\s+/), last = parts[parts.length - 1];
  const bits = last.match(/^([a-z0-9]+)?((?:[.#][A-Za-z0-9_-]+)*)$/i);
  if (!bits) throw new Error('gate.sh: ROLES selector not supported: ' + sel);
  if (parts.length > 1 && !bits[2]) return false;
  if (bits[1] && e.tag !== bits[1].toUpperCase()) return false;
  for (const b of (bits[2] || '').match(/[.#][A-Za-z0-9_-]+/g) || []) {
    if (b[0] === '#' && e.id !== b.slice(1)) return false;
    if (b[0] === '.' && !has(e, b.slice(1))) return false;
  }
  return true;
}
const inFold = (e, d) => e.y < d.doc.vh && e.y + e.h > 0;

// The empty share of the first viewport — measure.mjs's own T2 "lit" reading (aTargets(), the
// `grids.lit` loop): a 4 px grid over the fold, a cell marked full when it sits inside anything
// that carries text, a mark, a sign, an image or a control. Duplicated rather than imported
// because this file has to run standalone from `node -`; the grid math itself is copied verbatim.
function emptyShare(d) {
  const w = d.doc.vw, vh = d.doc.vh, G = 4;
  const gw = Math.ceil(w / G), gh = Math.ceil(vh / G), grid = new Uint8Array(gw * gh);
  const mark = (x, y, ww, hh) => {
    for (let gy = Math.max(0, Math.floor(y / G)); gy < Math.min(gh, Math.ceil((y + hh) / G)); gy++)
      for (let gx = Math.max(0, Math.floor(x / G)); gx < Math.min(gw, Math.ceil((x + ww) / G)); gx++)
        grid[gy * gw + gx] = 1;
  };
  for (const e of d.els) {
    if (e.y >= vh || !(e.hasText || e.kind === 'media' || e.kind === 'control')) continue;
    mark(e.x, e.y, e.w, e.h);
  }
  return 100 * (1 - grid.reduce((a, b) => a + b, 0) / (gw * gh));
}

function t1legs(d) {
  const hit = name => d.els.filter(e => ROLES[name].some(sel => matches(e, sel)));
  return {
    sentence: hit('sentence').some(e => inFold(e, d)),
    numeral: hit('numeral').some(e => inFold(e, d)),
    state: hit('state').some(e => inFold(e, d)),
    ask: hit('ask').some(e => inFold(e, d) && e.h > 0),
    asof: hit('asof').some(e => inFold(e, d)),
  };
}

// Recorded by running this gate against the page as committed at 46018b0 (Task 8). Never
// docs/design/REDESIGN_2026-09_ground.md's Phase 1 numbers — those were measured against a
// prototype container nobody can reconstruct, and are not comparable to a hermetic render of the
// production page.
//   now_populated_390:  orphanNums 0, orphanComps 0, page height 8267 px, empty share 37.7%
//   now_populated_1440: orphanNums 0, orphanComps 0, page height 5261 px, empty share 61.3%
// HEIGHT_MARGIN (8%): a page that grew a whole section would clear it; a few px of font-metric
// drift between machines will not. EMPTY_MARGIN (+6 points): emptiness creeping up by a couple of
// points is layout noise (a line wrapping differently at a slightly different font); +6 points is
// roughly a whole section's worth of ground going unused, which is the H1 complaint this redesign
// exists to answer — a regression there is worth failing on, and a couple of rounding points is not.
// Re-recorded 21 Sep 2026, prompt 3's Observe stage, AND against a different fixture.
//
// THE FIXTURE CHANGED, which matters more than the numbers. This gate measured node1-2026-09-06,
// a capture with no `sensors`, no `issues`, no `forecast`, no `trust`, no `nearby` and no `reach` —
// so every section that reads one of those was never exercised here, and the wall was measured
// against a house with four stations when node #1 has six. It now measures node1-2026-09-21d: node
// #1 as it is today, on v0.69. The first thing that found was the wall at 1,107 px on a 1,080 px
// screen, which had been true on the real node for weeks under a green gate.
//
// Heights are up because Observe gained three sections on purpose — the matrix, the day and the
// sources — because the request ledger became a section of its own, because Decide gained the
// four-grain row, the two boundaries and the sentence template, because Act gained the ring strips
// and where-to-go, because Measure gained the Figures ledger — eighteen rows, the whole page cited
// once — and because the richer fixture draws more in the sections that were already there. The 8%
// margin refused every one of them, which is what it is for.
//
// 1440's emptiness is re-recorded DOWN, from 61.3 to 57.4: the redesign is meant to drive that
// number and locking in the gain is the point of recording it. 390's is NOT re-recorded. It is
// 42.6% against a 37.7% baseline — inside the +6 margin, but the wrong way, and writing 42.6 here
// would make that the new normal. It is a watch item, not a new standard.
//
// Previous, from 46018b0 on node1-2026-09-06: 390: 8267 px / 37.7%, 1440: 5261 px / 61.3%.
//
// Heights re-recorded 28 Sep 2026, against the page at v0.75.6 (ebefea8) on node1-2026-09-21d.
// The 15893 and 10051 above them were NEVER this fixture's numbers. d9a9316 measured them on
// node1-2026-09-21c, then in the same commit renamed the recapture to 21d and pointed PAI_Q at it
// without measuring again: d9a9316 on 21c is 15893 / 10051, and on 21d it is 16520 / 10205. So 627 px
// of the 390 "growth" was the fixture, and the gate started from a number it could not reproduce.
// The rest is the page, all of it on purpose: e0262ca's ledger of what was decided (+567), f9e50c9
// (-701), c46274f's effect per rule (+507), 04839d1's vocabulary, whose longer words wrap more at
// 390 (+255), and 3c3a20d's route line under every band (+352). 390 has been over the margin since
// v0.73 (17402), and nobody saw it because `make test` does not run this file. Emptiness is NOT
// re-recorded here; see above for why 390's stays at 37.7.
//
// Previous, from d9a9316 on node1-2026-09-21c: 390: 15893 px, 1440: 10051 px.
//
// 6 Oct 2026: re-recorded for v0.78 on the events fixture: Decide first, the four sections on
// Network, the rail in one row. The fixture is node1-2026-10-06-events, node #1 at 09:00 Bali with
// air event 2 open (danger), so the event card and the lead-by-event path are measured for the first
// time. Heights fall because four sections left Now for Network. 390's emptiness is re-recorded UP,
// from 37.7 to 44.7, and that is a decision, not noise: the first viewport is now Decide's event card
// and the one-row rail rather than the strip, and the old 37.7 was measured on another page and
// another fixture. 1440's falls from 57.4 to 55.1.
//
// Previous, from ebefea8 on node1-2026-09-21d: 390: 17357 px / 37.7%, 1440: 10764 px / 57.4%.
// 6 Oct 2026, v0.79: re-recorded for the day figure and the strips, on node1-2026-10-06-figures (a fresh
// capture of node #1 that carries issues_days). Each issue's day is one drawing with a strip of the last 168
// hours under it, eight local dates, so each issue gains eight rows; the barcode and Measure's second trace are gone, and the net is +509 px at
// 390 and +14 px at 1440 (the fixture also changed). Emptiness falls: 390's from 44.7 to 42.5 and 1440's from
// 55.1 to 52.7; both are lower, never higher, so no margin was spent.
// Previous, on node1-2026-10-06-events: 390: 13294 px / 44.7%, 1440: 8728 px / 55.1%.
const HEIGHT_SHIPPED = { now_populated_390: 13803, now_populated_1440: 8742 };
const EMPTY_SHIPPED = { now_populated_390: 42.5, now_populated_1440: 52.7 };
const HEIGHT_MARGIN = 1.08, EMPTY_MARGIN = 6;

for (const n of ['now_populated_1440', 'now_populated_390']) {
  const d = j(n);
  const legs = t1legs(d);
  const missing = Object.entries(legs).filter(([, ok]) => !ok).map(([k]) => k);
  if (missing.length) fails.push(`${n}: T1 leg(s) missing: ${missing.join(', ')}`);

  const orphanNums = d.els.filter(e => e.dnum && !e.dcmp).length;
  const ids = new Set(d.els.map(e => e.id).filter(Boolean));
  const inbound = new Set(d.els.filter(e => e.dref && ids.has(e.dref)).map(e => e.dref));
  const orphanComps = d.els.filter(e => e.dc && !(e.dref && ids.has(e.dref)) && !inbound.has(e.id)).length;
  const broken = (d.lines || []).map(x => typeof x === 'string' ? x : x.text || '').filter(x => /did not render|has nothing here yet/.test(x));
  if (orphanNums) fails.push(`${n}: ${orphanNums} numerals with no comparison`);
  if (orphanComps) fails.push(`${n}: ${orphanComps} components with no link in or out`);
  if (broken.length) fails.push(`${n}: ${broken.join(' | ')}`);

  const cap = HEIGHT_SHIPPED[n] * HEIGHT_MARGIN;
  if (d.doc.h > cap) fails.push(`${n}: page is ${d.doc.h} px, more than ${HEIGHT_MARGIN}x the ${HEIGHT_SHIPPED[n]} px this shipped at`);

  const empty = emptyShare(d);
  if (empty > EMPTY_SHIPPED[n] + EMPTY_MARGIN)
    fails.push(`${n}: ${empty.toFixed(1)}% empty, more than ${EMPTY_MARGIN} points over the ${EMPTY_SHIPPED[n]}% this shipped at`);
}

const w = j('wall_populated_1920_dark');
if (w.doc.h > 1080) fails.push(`wall is ${w.doc.h} px on a 1,080 px screen`);

// THE RULE UNDER THE RAIL RUNS THE SAME WAY THE RAIL DOES. The rail's stops go coarse to fine left
// to right — resolution 2 at 172 km first, resolution 12 at 10 m last. The rule shipped with its
// log scale the other way round, so 10 m sat at the left edge under the 172 km stop and every tick
// fell under the stop at the opposite end of the row. Nothing else here could see it: each box was
// the right size, the page did not overflow, and the numbers were correct — only the axis was
// backwards. Read off the rendered text lines inside the ruler's own box, so it checks the drawing
// rather than the source.
{
  const d = j('now_populated_1440_worth1');
  const r = d.els.find(e => (e.cls || '').split(/\s+/).includes('ruler'));
  if (!r) fails.push('no ruler under the rail');
  else {
    const M = { m: 1, km: 1000 };
    const marks = d.lines
      .filter(l => l.x >= r.x && l.x <= r.x + r.w && l.y >= r.y && l.y <= r.y + r.h)
      .map(l => ({ x: l.x, t: (l.text || '').trim() }))
      .map(l => ({ ...l, m: (l.t.match(/^([\d.]+)\s*(m|km)$/) || [])[1] * M[(l.t.match(/(m|km)$/) || [])[1]] }))
      .filter(l => l.m > 0).sort((a, b) => a.x - b.x);
    if (marks.length < 3) fails.push(`the ruler has ${marks.length} readable mark(s), not a scale`);
    else for (let i = 1; i < marks.length; i++)
      if (marks[i].m >= marks[i - 1].m)
        fails.push(`the ruler runs the wrong way: ${marks[i - 1].t} is left of ${marks[i].t}, `
          + 'and the rail above it goes coarse to fine');
  }
}

for (const f of fails) console.log('FAIL', f);
console.log(fails.length ? `${fails.length} regression(s)` : 'ok');
process.exit(fails.length ? 1 : 0);
JS

# A page that scrolls sideways on a phone is the defect a household reports as "it is broken", and
# every check above can be green while it is true: each box the right size, the document wider than
# the screen. This asks the page itself, in all 108 combinations of view, width, mode and register.
# It is last because it is the slowest thing here by a distance — a browser per combination.
node tests/visual/measure.mjs overflow
