/* The dashboard: a shell, a page contract, and ten sections a pack registers with it.
 *
 * The shell knows four things — the dial, the lead, the four stages of the PLANETAI loop
 * (observe · decide · act · measure) and the notes at the foot — and nothing about what its
 * sections are. A pack registers one with window.PAI (the contract is further down, verbatim from
 * the design repo's kit-page.js). Adding a feature is adding a section; a section a node does not
 * have simply is not there, and a section whose data is missing prints one honest line.
 *
 * Ported by hand, once, from planetai-design/prototypes/dashboard-directions — direction H, picked
 * by Tomas on 15 September 2026. Every part below is under a banner naming the file it came from,
 * and every edit made on the way across is marked `PORTED:` and listed in
 * .superpowers/sdd/2026-09-15-modular-dashboard/task-6-report.md.
 *
 * No build step, no framework, nothing loaded from anywhere but static/. A node serves this page to
 * a household LAN and may have no route out at all.
 *
 * WHAT IT READS, and the whole of it: GET /issues (or /issues/fixtures/<name> with ?fixture=),
 * /health, /settings, /rho, /earth, /place/geojson. The node computes; the page draws. A number
 * this page works out for itself is a bug.
 */
'use strict';

/* Every file ported below opens its own scope by reading a global — window.SNAP, window.H3,
 * window.PLAN, window.K — because in the prototype the data was on disk before the first line ran.
 * Here nothing exists until boot() has answered. So each scope is pushed onto this list and run, in
 * order, by init(). That is the one structural change made to the ported code: an IIFE became a
 * push and its `})();` became a `});`. Nothing inside any of them moved.
 */
const PAI_LOAD = [];

/* THE TEN GLOBALS, AND THE SHAPE OF EACH. Nothing else on this page is global.
 *
 * They exist because every module below was ported from a prototype that read its data off disk
 * before the first line ran (see the note above), and they are written here in one place because a
 * global whose shape is only discoverable by reading the code that writes it is how the page came
 * to assert, for a week, that live tiles were off on a node whose keeper had turned them on.
 *
 *   window.SNAP      what boot() fetched, normalised: { issues, health, base:{captured_utc}, rho,
 *                    funnel, peer, fixture }. `issues` is GET /issues' whole body.
 *   window.H3        the geometry and the readings the sections draw, assembled in boot() from that
 *                    body: { publication, ladder, nav:{chain,cells,plates}, grain_table, claims,
 *                    radio, settings, source, sensors:[station], metrics, asks,
 *                    node:{lat,lon,name} }. `geometry: null` from the node leaves only the last
 *                    four, and every section that needs the rest says so.
 *   window.SETTINGS  GET /settings — describe()'s { unlocked, runtime:[row], bootstrap:[row] } —
 *                    WITH every unmasked runtime key flattened onto it as KEY: value, so
 *                    window.SETTINGS.MAP_TILES is the string the keeper set. flatSettings() does it,
 *                    in boot(), and it is the only place that knows the endpoint's shape.
 *   window.EARTH     GET /earth, or null. window.TRUST, window.FORECAST: the same, from /trust and
 *                    /forecast.
 *   window.PLAN      GET /place/geojson projected to metres by plan(), or null.
 *   window.PAI       the section contract: { STAGES, register, render, wall, sections, problems,
 *                    has }. docs/PACKS.md is its documentation.
 *   window.K         kit.js: the four card kinds, the signs, esc/fmt, and — after initKit() — the
 *                    bound data S, ISS, ORDER, DIST, LAB, LOC, VIEW, STATE.
 *   window.KH        kit-h3.js: { H, address, grid, km2, edge, sited }. H is window.H3.
 *   window.KN        kit-nav.js: a position and the moves out of it ({ N, where, link, … }).
 *   window.KMAP      kit-map.js: the offline plan ({ map, caption, frameOf, MAX_SPAN_M }).
 *   window.GROUND    the ground module's own frame maths, for the sections that reuse it
 *                    ({ figure, frame, BASES, SIZE }); window.WALL is the wall's ({ render, start,
 *                    field, dial, grain }).
 */

/* ================================================================= kit.js — the four card kinds, the signs, and the two attributes ==== */
/* The four card kinds, the signs, and the attributes the targets are written in terms of.
 *
 * All three directions build from this and nothing else, so they differ in their organising idea
 * and not in their skin. If a rule about what a card IS ends up in a direction's own file, the
 * three have stopped being comparable and the comparison in DIRECTIONS_2026-09.md is worthless.
 *
 * These are drawings. There is no fetch here, nothing is arranged, no button does anything, and
 * every number comes out of window.SNAP — which is node #1 on 6 September replayed through the real
 * engine.
 *
 * The four kinds, and the whole of T3:
 *
 *   readout   one number, its unit, its comparison, its source line
 *   stack     the four distances on one scale
 *   series    a trace with an axis, a time origin, the line, and a text alternative
 *   row       a ledger, an index, a unit or a sensor row
 *
 * Everything else on any of the three pages — the hero, the ask, the plan, the satellite, the
 * funnel, the index — is composed from those four plus the sign library. A fifth kind is a STOP.
 *
 * Two attributes carry the two complaints:
 *
 *   data-num / data-cmp   a numeral and the thing it is compared against. Never one without the
 *                         other: where a pack declares no comparison, data-cmp carries the pack's
 *                         own reason and the page prints it, at the same size, in the same place.
 *   data-ref              a link to an id on this page. Every component except the header and the
 *                         hero has one in or one out.
 *
 * One honesty note about `cmp`. The node supplies the line, its source, each cell's source and age,
 * and the sentence's own comparison clause. The COMPARISON MODE — line, normal, ring, region,
 * last_period, none — is a declaration, and in Release 2 it arrives on the contribution. Here the
 * word is chosen from that declaration and the numbers in it are the node's. No arithmetic happens
 * in this file: `cmpText` reads values, it does not derive them.
 */
'use strict';

/* PORTED: the prototype read window.SNAP at load time, because a drawing has its snapshot on disk
 * before the first line runs. Here nothing exists until boot() has answered, so these are bound by
 * initKit(), which the boot sequence calls, and the language is the household's own from /health. */
let S, ISS, ORDER, DIST, LAB, LOC = 'en';

const esc = s => String(s ?? '').replace(/[&<>"']/g, c =>
  ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

/* The node already formatted every number it sent; this only sets the places the issue declared. */
const fmt = (v, dp = 0) => (v == null || isNaN(v) ? '—' : Number(v).toFixed(dp));

/* `tip` is the sign's name on hover. The signs are decorative to a screen reader (the row's own label says
   it), but a pointer reader had nothing: a ring and a hexagon looked like they meant something and said
   nothing. The same glyph means different things in different rows, so the name is the row's to give. */
const sign = (id, cls = '', tip = '') =>
  `<svg class="sg ${cls}" aria-hidden="true">${tip ? `<title>${esc(tip)}</title>` : ''}<use href="static/signs.svg#sign-${id}"/></svg>`;

/* Provenance is a glyph and a word, ink only, square. A fixture is a committed snapshot, so nothing
 * on it was measured just now: `live` is coerced to `cached`, exactly as the node's own page does. */
/* PORTED: the prototype coerced `live` to `cached` because every number in it came off a committed
 * snapshot. This page reads a live node OR a fixture and knows which, so the caller passes the word
 * and this prints it. `?fixture=` is what says `cached` (see lead()). */
/* THE WORDS signs.svg HAS A SIGN FOR. The sprite is the design layer's, frozen here byte for byte
 * (tools/check_theme.py), and it draws five provenance signs. A word outside them, `stale` above
 * all, is printed as the word alone: a <use> pointing at a symbol the sprite does not have draws an
 * empty square, and lending it another word's sign would make one glyph mean two things. The sign
 * for `stale` is owed by planetai-design, not drawn here. */
const PROV_SIGNS = new Set(['live', 'partial', 'model', 'cached', 'example']);
const pill = (word, note = '') => {
  if (!word) return '';
  const w = String(word);
  return `<span class="pill prov" title="${esc(note)}">`
    + (PROV_SIGNS.has(w)
      ? `<svg class="sg" aria-hidden="true"><use href="static/signs.svg#sign-prov-${esc(w)}"/></svg>`
      : '')
    + esc(w) + `</span>`;
};

/* Under both forms that post to /actions, before anybody presses: what a browser needs to be let
 * through. The node's own refusal says the same after the press; this says it before. */
const TOKEN_FINE = `<p class="fine">From another device this needs the act token: `
  + `<span class="mono">planetai ui</span> prints it on the node, and Set up \u2192 unlock holds it `
  + `in this browser.</p>`;

const age = m => m == null ? '' : m < 1 ? 'just now' : m < 60 ? `${Math.round(m)} min ago`
  : m < 1440 ? `${Math.round(m / 60)} h ago` : `${Math.round(m / 1440)} days ago`;

let seq = 0;
const uid = p => `${p}-${++seq}`;

/* --------------------------------------------------------------------------- the comparison */
/* What a numeral is measured against, in words, from what the node sent. Returns {text, none}. */
function cmpText(o) {
  const { mode, line, unit, dp, other, otherLabel, reason } = o;
  if (mode === 'none' || !mode) {
    return { none: true, text: reason ? `no comparison yet · ${reason}` : 'no comparison yet' };
  }
  if (mode === 'line' && line) {
    /* The line's SOURCE is named once, by the why line under the sentence. Repeating it in every
       column of a stack put twenty-eight words of WHO citation under four numbers and buried the
       one thing the column is for. The comparison is the number; whose number it is, is above. */
    return { none: false, text: `against the line, ${fmt(line.value, dp)} ${unit}` };
  }
  if (other != null) {
    return { none: false, text: `against ${otherLabel}, ${fmt(other, dp)} ${unit}` };
  }
  return { none: true, text: 'no comparison yet · nothing at that distance to compare with' };
}

/* --------------------------------------------------------------------------- 1 · readout */
function readout(o) {
  const id = o.id || uid('readout');
  const c = o.cmp || { none: true, text: 'no comparison yet' };
  return `<div class="readout" data-kind="readout"`
    + ` data-component="${esc(o.component || 'readout')}" id="${esc(id)}"`
    + `${o.ref ? ` data-ref="${esc(o.ref)}"` : ''}>`
    /* PORTED: .lab is shouted, and a readout's title can be a PACK's own words — the water pack's
     * "Dissolved solids" arrives as a contribution. `µ` uppercases to `M`, so the words go in .said
     * and only the page's own separator is left to shout. */
    + `<div class="lab"><span class="said">${esc(o.title)}</span>`
    + `${o.pack ? ` · <span class="said">${esc(o.pack)}</span>` : ''}</div>`
    /* data-num is a KEY, not a label: `water.tds`, not "Dissolved solids". A gate that walks
     * [data-num] has to be able to tell which issue a numeral belongs to, and a title cannot say. */
    + `<div class="v"><span class="num${o.crossed ? ' crossed' : ''}"`
    + ` data-num="${esc(o.num || o.title)}" data-cmp="${esc(c.text)}">`
    + `${esc(fmt(o.value, o.dp))}</span>`
    + `<small>${esc(o.unit || '')}</small></div>`
    + `<div class="cmp${c.none ? ' none' : ''}">${esc(c.text)}</div>`
    + `<div class="src"><span class="said">${esc(o.source || '')}</span>`
    + `${o.age != null ? `<span class="asof">${esc(age(o.age))}</span>` : ''}`
    + `${pill(o.prov)}</div></div>`;
}

/* --------------------------------------------------------------------------- 2 · stack */
/* The four distances, each with its value, what it is measured against, its source and its word.
 * An absent distance says why. Every column links to the source card that stands behind it. */
/* THE BRACKET METER is the Stack's mini variant, not a fifth card kind. Design log R15: the anatomy
 * is the Stack's — label, value, comparison, provenance — and only the VALUE'S DRAWING changes, from
 * a numeral to sixteen cells filled against one scale shared by all four distances, with the line
 * drawn as a tick at the same x on every row. Under the line and over it becomes a thing you see
 * rather than a thing you compute.
 *
 * Drawn in SVG and not in text. The sketch writes it `ROOM [▮▮▮▮▮▮▯▯▯▯▯▯▯▯▯▯] 6`, and the pack says
 * to check the glyphs before trusting them. Measured against the shipped subset: U+25AE and U+25AF
 * are not in it — jetbrains-mono-latin.woff2 is a latin subset — and both fall back at an advance of
 * 60.21 where every real glyph is 60. On this Mac that is a 0.35% error nobody would see; on a wall
 * screen with a different fallback it is a broken bar. Sixteen rects have no such question. */
const METER_CELLS = 16;

/* A motion token's value in MILLISECONDS, whichever unit the layer wrote it in.
 *
 * The table carries both — `--motion-reading-fade: 120ms` and `--motion-mark-float: 3.2s` — and
 * `parseFloat` answers 120 and 3.2 with no way to tell them apart. The satellite player got away
 * with multiplying by 1000 because its own token happens to be in seconds; the meter fill, at
 * `40ms`, came out as forty seconds and the bars sat empty. One reader for all of them.
 *
 * Zero is the answer under reduced motion, because that is what the frozen layer's one reduce block
 * sets every timed token to — so `if (!ms)` is how a caller asks "is motion off", and it is the same
 * question for every motion on the page. */
function msToken(name) {
  const raw = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  const n = parseFloat(raw);
  if (!Number.isFinite(n)) return 0;
  return /ms\s*$/.test(raw) ? n : n * 1000;
}

function meterBar(value, scale, line, dist, key, cap) {
  const W = 6, G = 1, H = 10, full = METER_CELLS * W;
  /* `cap` is how many cells may be lit yet — the loading state filling one per
     --motion-meter-fill. Absent, a bar draws the whole reading, which is every other caller. */
  const lit = Math.min(cap == null ? METER_CELLS : Math.max(0, cap),
    value == null ? 0
      : Math.max(0, Math.min(METER_CELLS, Math.round((value / scale) * METER_CELLS))));
  const cells = Array.from({ length: METER_CELLS }, (_, i) =>
    `<rect x="${i * W}" y="0" width="${W - G}" height="${H}" class="${i < lit ? 'on' : 'off'}"/>`)
    .join('');
  const tick = line == null || !(line > 0) || line > scale ? ''
    : `<rect x="${((line / scale) * full).toFixed(2)}" y="-1" width="1.2" height="${H + 2}"`
      + ` class="line"/>`;
  return `<svg class="meter" viewBox="-1 -1 ${full + 2} ${H + 2}" role="img" aria-hidden="true"`
    + ` preserveAspectRatio="none">${cells}${tick}</svg>`;
}

function stack(key, d, o = {}) {
  const id = o.id || `stack-${key}`;
  /* One scale for the four distances, so the four rows can be read against each other, with a
     little headroom so a full bar is not also the edge of the drawing. */
  const _vals = DIST.map(x => ((d.stack || {})[x] || {}).value).filter(v => v != null);
  const _line = d.line ? d.line.value : null;
  const _top = Math.max(0, ..._vals, _line == null ? 0 : _line);
  const meter = o.meter && _vals.length > 0 && _top > 0;
  const _scale = _top * 1.12;
  const cols = DIST.map(dist => {
    const c = (d.stack || {})[dist];
    const has = c && c.value != null;
    /* Every column is the issue's own quantity, in the issue's own unit, against the issue's own line. A pack
     * never fills one (docs/decisions/2026-10-01-packs.md, point 4): a pack's number is a readout beside it. */
    const unit = d.unit, dp = d.dp, line = d.line;
    const crossed = has && line && c.value > line.value;
    const room = ((d.stack || {}).room || {}).value;
    const cmp = !has ? { none: true, text: `nothing at this distance · ${reasonFor(d, dist)}` }
      : line ? cmpText({ mode: 'line', line, unit, dp })
        : dist === 'room' || room == null
          ? cmpText({ mode: 'none', reason: `${d.name[LOC]} has no line: ${noLine(d)}` })
          : cmpText({ mode: 'ring', other: room, otherLabel: 'the house', unit, dp });
    return `<div class="col" id="${esc(id)}-col-${dist}"`
      + ` data-ref="src-${esc(key)}-${dist}">`
      + `<div class="k">${esc(LAB[dist])}</div>`
      + `<div class="v">`
      + (meter ? meterBar(has ? c.value : null, _scale, _line, dist, key) : '')
      + `<span class="num${has ? '' : ' none'}${crossed ? ' crossed' : ''}"`
      + ` data-num="${esc(key)}.${dist}" data-cmp="${esc(cmp.text)}">`
      + `${has ? esc(fmt(c.value, dp)) : '—'}</span>`
      + (has ? `<small>${esc(unit || '')}</small>` : '') + `</div>`
      + `<div class="cmp${cmp.none ? ' none' : ''}">${esc(cmp.text)}</div>`
      + (has ? `<div class="src"><span class="said">${esc(c.source)}</span>`
        + `${c.age_minutes != null ? ' · ' + esc(age(c.age_minutes)) : ''}</div>` + pill(c.provenance)
        : '')
      + `</div>`;
  }).join('');
  /* The fifth column, for the matrix only. The four distances are readings and the line is not —
   * it is what they are read against — so it is drawn as a column rather than folded into each
   * cell's comparison, where the same threshold was being restated four times across a row. An
   * issue with no line says which kind of no it is: a context issue never asks, and an issue with
   * no threshold named here has simply not been given one. */
  const lineCol = !o.line ? '' :
    `<div class="col line" id="${esc(id)}-col-line" data-ref="src-${esc(key)}-line">`
    + `<div class="k">line</div><div class="v">`
    + `<span class="num${_line == null ? ' none' : ''}" data-num="${esc(key)}.line"`
    + ` data-cmp="${esc(_line == null ? `${d.name[LOC]} is read against nothing here`
        : `what the four readings left of this are read against`)}">`
    + `${_line == null ? '—' : esc(fmt(_line, d.dp))}</span>`
    + (_line == null ? '' : `<small>${esc(d.unit || '')}</small>`) + `</div>`
    + `<div class="cmp${_line == null ? ' none' : ''}">`
    + `${esc(_line == null ? noLine(d) : 'crossing it is what raises an alert')}</div>`
    + (_line == null ? '' : `<div class="src"><span class="said">${esc(d.line.source)}</span></div>`)
    + `</div>`;
  return `<div class="stack${meter ? ' meters' : ''}${o.line ? ' withline' : ''}" data-kind="stack"`
    + ` data-component="stack" id="${esc(id)}"`
    + ` role="group" aria-label="${esc(d.name[LOC])} at four distances`
    + `${o.line ? ', and the line it is read against' : ''}"`
    + `${o.ref ? ` data-ref="${esc(o.ref)}"` : ` data-ref="band-${esc(key)}"`}>${cols}${lineCol}</div>`;
}

const noLine = d => d.kind === 'context'
  ? 'it informs, it never asks' : 'no threshold has been named for it here';
const reasonFor = (d, dist) => ({
  room: 'no sensor in the house', yard: 'no kit outside on the street',
  ring: 'no public station reporting', region: 'no model for this point',
}[dist] || 'no source');

/* --------------------------------------------------------------------------- 4 · row */
function row(o) {
  const id = o.id || uid('row');
  const qty = (o.qty || []).map(q => q.value == null
    ? `<span class="none">—</span>`
    : `<span data-num="${esc(q.num)}" data-cmp="${esc(q.cmp)}">${esc(q.value)}</span>`).join('');
  const tag = o.href ? 'a' : 'div';
  return `<${tag} class="row ${o.cls || ''}" data-kind="row"`
    + ` data-component="${esc(o.component || 'row')}" id="${esc(id)}"`
    + `${o.ref ? ` data-ref="${esc(o.ref)}"` : ''}`
    + `${o.href ? ` href="${esc(o.href)}"` : ''}`
    + `${o.cols ? ` style="--row-cols:${o.cols}"` : ''}>`
    + (o.left || '')
    + (o.name ? `<span class="name">${esc(o.name)}</span>` : '')
    + (o.state ? `<span class="state${o.state === 'act' ? ' act' : ''}">${esc(o.state)}</span>` : '')
    + (o.line ? `<span class="line said"${o.lineRole ? ` data-role="${esc(o.lineRole)}"` : ''}>`
      + `${esc(o.line)}</span>` : '')
    + (o.signs ? `<span class="signs">${o.signs}</span>` : '')
    + (qty ? `<span class="qty">${qty}</span>` : '')
    + `</${tag}>`;
}

/* --------------------------------------------------------------------- the composites */
const kicker = (key, d) =>
  `<div class="k" data-component="kicker" id="kicker-${esc(key)}" data-ref="band-${esc(key)}">`
  + `<span class="issue" data-role="issue">${esc(d.name[LOC])}</span> `
  + `<span class="state${d.state === 'act' ? ' act' : ''}" data-role="state">${esc(d.state)}</span>`
  + (d.reason_text ? ` <span class="said">· ${esc(d.reason_text[LOC])}</span>` : '') + `</div>`;

/* The numeral inside the sentence is the monument, and it carries its comparison like every other
 * numeral on the page. The node formatted it; this finds it in its own sentence to set it. */
/* THE MONUMENT — the figure, its unit and the issue's pictogram, on one row, with the node's
 * sentence as prose beneath it. This is the sketch's central gesture and I had not built it: the
 * figure was inline inside the sentence, which is why it kept having to shrink. A 132px numeral
 * inside a paragraph decides where every line in that paragraph breaks, so it was traded down to
 * 107 and then fought the unit for a line. Out of the flow it can be the size it was drawn at.
 *
 * It carries `data-role="numeral"` and the id the why line points at, because it is the reading;
 * the copy inside the sentence is the sentence's own word for the same number. */
/* THE HERO IS A SLOT. The numeral, its unit, its places and the figure beside it are the issue's
 * `hero` on /issues, filled by the node from the issue's own declaration. Nothing here knows which
 * issue it is drawing, so a sixth issue leads the page with no line of this file changed. */
function monument(key, d, pix = '') {
  const h = d.hero || {};
  const n = h.value != null ? fmt(h.value, h.dp) : null;
  if (n == null) return '';
  const crossed = !!(d.line && h.numeral === d.headline && h.value > d.line.value
    && (d.state === 'act' || d.state === 'notable'));
  const cmp = d.line
    ? cmpText({ mode: 'line', line: d.line, unit: d.unit, dp: d.dp })
    : cmpText({ mode: 'none', reason: noLine(d) });
  return `<div class="num" data-component="monument" data-ref="sentence-${esc(key)}">${pix}`
    + `<b class="v${crossed ? ' crossed' : ''}" data-role="numeral" id="num-${esc(key)}"`
    + ` data-num="${esc(key)}.headline" data-cmp="${esc(cmp.text)}">${esc(n)}</b>`
    + `<span class="u">${esc(h.unit || '')}</span></div>`;
}

/* The pictogram the hero declares, at hero size; an issue with none gets its sign at hero size. Both
 * are <use> of a symbol already in signs.svg, and the validator refused any id that is not there. */
function heroPix(key, d) {
  const h = d.hero || {};
  const id = h.pictogram || h.sign;
  if (!id) return '';
  return `<svg class="pix${h.pictogram ? '' : ' sign'}" viewBox="${h.pictogram ? '0 0 15 11' : '0 0 24 24'}"`
    + ` data-component="pictogram" data-ref="num-${esc(key)}" role="img" aria-label="${esc(d.name[LOC])}">`
    + `<use href="static/signs.svg#${esc(id)}"/></svg>`;
}

/* THE RULE: one line from the hero's min to its max, a dot per distance the hero lets on it, and the
 * line where there is one. Ours is filled, the street's outlined, the ring's dashed. A reading past
 * either end sits on the end and says its real number. No rule in the contract, no rule here. The
 * numbers are HTML under the drawing so each carries its comparison like every numeral on the page. */
function heroRule(key, d) {
  const h = d.hero || {};
  const r = h.rule;
  if (!r) return '';
  const at = v => Math.max(0, Math.min(1, (v - r.min) / (r.max - r.min))) * 100;
  const kind = { room: 'own', yard: 'out', ring: 'ring', region: 'out' };
  const cmp = r.line ? v => `${fmt(v, h.dp)} against ${fmt(r.line.value, h.dp)}, the line`
    : () => `on a scale from ${fmt(r.min, h.dp)} to ${fmt(r.max, h.dp)}`;
  const marks = r.dots.map(x => `<i class="dot ${kind[x.distance] || 'out'}" style="left:${at(x.value).toFixed(2)}%"></i>`);
  const items = r.dots.map(x => ({ x: at(x.value), cls: x.distance === 'room' ? ' own' : '',
    num: `${key}.${x.distance}`, cmp: cmp(x.value), v: x.value, word: LAB[x.distance] || x.distance }));
  if (r.line) {
    marks.unshift(`<i class="ln" style="left:${at(r.line.value).toFixed(2)}%"></i>`);
    items.push({ x: at(r.line.value), cls: ' lnl', num: `${key}.line`, v: r.line.value,
      cmp: 'crossing it is what raises an alert', word: r.line.name[LOC] });
  }
  /* Readings a few units apart would print on top of each other, and on a phone the rule is 330 px.
     In order along the rule the labels alternate above and below, and one that would land within a
     quarter of the rule of its neighbour on the same side steps out to a second tier. */
  items.sort((p, q) => p.x - q.x);
  const last = {};
  const labels = items.map((it, i) => {
    const side = i % 2 ? 'lo' : 'hi';
    const prev = last[side];
    const tier = prev && prev.tier === 0 && it.x - prev.x < 25 ? 1 : 0;
    last[side] = { x: it.x, tier };
    const edge = it.x > 85 ? ' end' : it.x < 15 ? ' start' : '';
    return `<span class="dl ${side}${tier ? ' t1' : ''}${edge}${it.cls}" style="left:${it.x.toFixed(2)}%">`
      + `<b data-num="${esc(it.num)}" data-cmp="${esc(it.cmp)}">${esc(fmt(it.v, h.dp))}</b>`
      + ` ${esc(it.word)}</span>`;
  });
  const ends = r.ends[LOC] || r.ends.en;
  return `<div class="herorule" data-component="heroRule" id="rule-${esc(key)}" data-ref="num-${esc(key)}">`
    + `<div class="track" aria-hidden="true"><svg class="axis" viewBox="0 0 100 20" preserveAspectRatio="none">`
    + `<line x1="0" y1="10" x2="100" y2="10"/><line x1="0" y1="4" x2="0" y2="16"/>`
    + `<line x1="100" y1="4" x2="100" y2="16"/></svg>${marks.join('')}</div>`
    + `<div class="labels">${labels.join('')}</div>`
    + `<div class="ends"><span>${esc(fmt(r.min, h.dp))} \u00b7 ${esc(ends[0])}</span>`
    + `<span>${esc(fmt(r.max, h.dp))} \u00b7 ${esc(ends[1])}</span></div></div>`;
}

function sentence(key, d, cls = 'big') {
  /* The title is the sentence's qualitative head — no number, no indicator, the household's words
     for what is happening. The tagline explains it (the line, the comparison, the day's event) in a
     smaller font: the readings are introduced slowly, not shouted in the title. The full sentence
     stays for prose contexts. Older nodes send no title; the sentence stands in.
     Release A moved the numeral out of the headline: the sentence is words only, so it draws no
     figure and marks none. The crossed mark moved with the number — it marks the `plain` figure
     that is over the line, drawn where plain is rendered. */
  const t = d.title ? d.title[LOC] : '';
  const s = t || (d.sentence ? d.sentence[LOC] : '');
  const tag = cls === 'big' && d.tagline ? d.tagline[LOC] : '';
  return `<p class="${cls}" data-component="sentence" data-role="sentence" id="sentence-${esc(key)}"`
    + ` data-ref="stack-${esc(key)}">${esc(s)}`
    + (tag ? `<span class="tag said">${esc(tag)}</span>` : '') + `</p>`;
}

/* `rule` is the lead's only. It used to be a second paragraph of its own, and `.lead > .why` matched
 * both it and this one, so two elements landed in grid area `w` and printed on top of each other at
 * every width over 900 px — visible on the shipped page, and on every shot taken of it. One
 * paragraph cannot overlap itself. The sentence comes from `headline_rule` on /issues, in the
 * household's language: the node does the ranking, so the node says how it ranked. */
const why = (key, d, rule) => {
  const said = rule ? ` <span class="said rule">${esc(rule)}</span>` : '';
  /* The line's figure and the ranking rule are two sentences in one paragraph, so they need the
     separator every other pair of facts on this page gets. Without it they ran together as
     "…not a global one · 35.0 °C The issue with most to say leads —". */
  const sep = rule ? ' · ' : '';
  return d.line
    ? `<p class="why" data-component="why" id="why-${esc(key)}" data-ref="num-${esc(key)}">`
      + `${esc(d.line.source)} · ${esc(fmt(d.line.value, d.dp))} ${esc(d.line.unit || d.unit)}`
      + `${sep}${said}</p>`
    : `<p class="why" data-component="why" id="why-${esc(key)}" data-ref="sentence-${esc(key)}">`
      + `No line: ${esc(noLine(d))}${sep}${said}</p>`;
};

/* The ask, and the words that stand in for one. T1 asks for the open ask OR "nothing to do", and
 * the shipped page has neither when there is nothing to do — it renders a hidden div. A household
 * that has to infer "nothing to do" from an absence has not been told anything. */
/* PORTED: `ref` is new. The strip was only ever drawn in the lead, where `sentence-<key>` is on the
 * page; the act section draws one per issue with an open ask, and on a node whose headline is some
 * other issue that id does not exist — a component pointing at nothing, which is what T5 counts. */
function ask(key, d, ref) {
  const a = (d.open_asks || [])[0];
  const id = `ask-${key}`;
  if (!a) {
    /* Two different absences, and saying "nothing to do" for both is a contradiction a reader can
     * see: the kicker's own reason for `notable` is "over the line, and nobody has been asked to do
     * anything", and a strip underneath it reading "Nothing to do" says the opposite of the line
     * above it. An issue that is over its line with no rule asking for anything is not quiet — it
     * is unattended, and the page should say which. */
    const unattended = d.state === 'notable' || d.state === 'act';
    return `<div class="ask none" data-component="askStrip" data-role="ask" id="${esc(id)}"`
      + ` data-ref="${esc(ref || `sentence-${key}`)}"><div class="what">`
      + (unattended ? 'Nothing has been asked.' : 'Nothing to do.')
      + `<small>${esc(d.name[LOC])} is ${esc(d.state)}`
      + (unattended ? ', and no rule here asks anybody to do anything about it.'
        : ', and no reading here has asked for anything.')
      + `</small></div></div>`;
  }
  /* THE BUTTON DOES SOMETHING NOW. It was drawn on every open ask on every node from the day this
     page shipped and nothing listened for it — a promise the page made and did not keep, while the
     funnel beside it counted acts nobody could make from here. POST /actions has taken a stage, an
     actor and a 500-character note since v0.21; every act on node #1 was made over Telegram, MCP or
     curl because this was the only surface that could not.

     The form is in the markup and hidden rather than built on the press: a hidden child costs no
     height, and T1 reads this strip's own box. */
  return `<div class="ask" data-component="askStrip" data-role="ask" id="${esc(id)}"`
    + ` data-ref="${esc(ref || `sentence-${key}`)}">`
    + `<div class="what">${esc(a.text ? String(a.text).split('\n')[0] : a.says[LOC])}`
    /* NOT `a.how`. The node composes that line in act_hint(), and it offers Telegram or a terminal
       — "Reply /act 361 on Telegram" — because until the form below existed the page was the one
       surface that could not close a loop. It is still the right sentence for a Telegram message
       and the wrong one here, on a screen with the button on it. The node's words are unchanged;
       this surface says what this surface offers. */
    + `<small>${esc(a.says[LOC])}</small></div>`
    + didButton(a.id, a.seen) + `</div>`;
}

/* The one button the page offers on an open alert, and the form it opens. Shared by Decide's alert cards
 * and the ask row simple mode draws in the lead, so both write to the ledger the same way. */
const didButton = (id, seen) =>
  /* "Seen" records `acknowledged`: somebody has looked, nothing has been done. rho counts it as an answer
     but the alert stays open here, because seeing it is not doing anything (app/issues/schema.py). */
  (seen ? `<span class="seenmark" title="Somebody has acknowledged this alert. It stays open until somebody acts.">\u2713 Seen</span> ` : '')
  + (seen ? '' : `<button type="button" class="seen" data-seen="${esc(String(id))}" title="Record that you have looked at this alert. It stays open until somebody acts.">Seen it</button>`)
  + `<button type="button" class="go" data-did="${esc(String(id))}">I did this</button>`
  + `<form class="did" hidden data-alert="${esc(String(id))}">`
  + `<label><span>Who</span><input name="actor" maxlength="80" autocomplete="name"`
  + ` placeholder="your name"></label>`
  + `<label><span>What you did</span><input name="note" maxlength="500"`
  + ` placeholder="closed the windows on the north side"></label>`
  /* Shown only when the node refuses for want of a token. A browser is never "this machine" to the
     node (it arrives as the Docker gateway), so on a PC running the node the first press from the
     dashboard always needs the act token once; asking for it here, where the press failed, beats a
     toast that names a terminal command. Kept in this browser, the same key Set up -> unlock writes. */
  + `<label class="tokfield" hidden><span>Act token</span><input name="token" type="password"`
  + ` autocomplete="off" spellcheck="false" placeholder="ACT_TOKEN from planetai ui"></label>`
  + `<div class="btns"><button type="submit" class="pri">Record it</button>`
  + `<button type="button" class="cancel">Cancel</button></div>${TOKEN_FINE}</form>`;

/* SIMPLE MODE'S ASK ROW: the third of the three questions, is there something to do, answered in the
 * lead. The sign of the issue it belongs to, the alert's first line, its id, and the button. Act-level
 * only, because `open_asks` is act-level by construction. Advanced has no strip: Decide draws the cards. */
function askRow(key, d, a) {
  const h = d.hero || {};
  return `<div class="ask askrow" data-lv="simple" data-component="askRow" data-role="ask"`
    + ` id="askrow-${esc(String(a.id))}" data-ref="num-${esc(key)}">`
    + (h.sign ? `<svg class="sgn" viewBox="0 0 24 24" role="img" aria-label="${esc(d.name[LOC])}">`
      + `<use href="static/signs.svg#${esc(h.sign)}"/></svg>` : '')
    + `<div class="what">${esc(String(a.text || '').split('\n')[0])}<small>#${esc(String(a.id))}</small></div>`
    + didButton(a.id, a.seen) + `</div>`;
}

/* Hide a component in one mode and not the other, by marking its outermost tag. The CSS on
 * body[data-lv] does the hiding; nothing is deleted, so switching mode is a redraw and not a refetch. */
const lv = (html, level) => String(html || '').replace(/^<([a-z]+)/, `<$1 data-lv="${level}"`);

/* PORTED: `plan` is not an id on this page; the figure the caption belongs to is the ground map.
 * A node with no coordinates yet has no cell and no caption, and prints neither. */
const stamp = () => {
  const c = (S.health || {}).cell;
  const said = c ? c.caption : '';
  return said ? `<div class="stamp" data-component="stamp" id="stamp"`
    + ` data-ref="ground-figure">${esc(said)}</div>` : '';
};

/* PORTED: the prototype added eight hours because its fixture is node #1 and node #1 is on WITA. A
 * reading belongs to the place it was taken in, and GET /health publishes NODE_TZ for exactly this.
 * A node with no zone set says UTC rather than drawing the viewer's clock as if it were the node's. */
const asof = () => {
  const t = new Date(S.issues.as_of);
  const tz = S.health && S.health.tz;
  let when = `${String(t.getUTCHours()).padStart(2, '0')}:`
    + `${String(t.getUTCMinutes()).padStart(2, '0')} UTC`;
  if (tz) {
    try {
      when = new Intl.DateTimeFormat('en-GB', { timeZone: tz, hour: '2-digit', minute: '2-digit',
        hour12: false }).format(t);
    } catch { /* a zone this browser does not know: UTC, said as UTC */ }
  }
  /* A poll that did not come back does not blank the page — the figures were true when they were
     read — but it stops the stamp saying "as of" as though it had just heard. It says how long it
     has been since the node last answered, which is the one thing a reader needs in order to know
     whether to believe the number above it. */
  const st = window.STALE;
  if (st) {
    const mins = Math.max(1, Math.round((Date.now() - st.since) / 60000));
    return `<span class="asof stale" data-role="asof" id="asof">Read at ${esc(when)} \u00b7 `
      + `the node has not answered for ${mins} min</span>`;
  }
  return `<span class="asof" data-role="asof" id="asof">As of ${esc(when)} \u00b7 `
    + `${esc(String(S.base.captured_utc || '').slice(0, 10))}</span>`;
};

/* rho as a row of rings, answered first, with the caption naming reported against observed. */
/* PORTED: `ref` is new, for the same reason the ask strip's is. The row's link out was always the
 * funnel, and the wall has no funnel on it. */
function rhoRow(small, ref, actLink) {
  /* GET /rho may be slow, refused or absent, and this is called from the wall, which nobody is
   * standing at. A dereference here took the whole wall down before innerHTML was ever assigned. */
  if (!S.rho) {
    return `<p class="note" data-component="rhoRow" id="rho" data-ref="${esc(ref || 'header')}">`
      + `This node has not said how many of its alerts were answered: GET /rho did not come back.</p>`;
  }
  const r = S.rho, total = r.alerts_act, closed = r.acted;
  /* ONE RING PER ASK UNTIL THAT STOPS BEING A ROW. This drew `total` rings unconditionally, so the
   * height of the wall was a function of how long the node had been running: node #1 reached 164
   * asks and the row wrapped to 116 px, pushing the wall to 1,118 on a 1,080 px screen. Nobody can
   * count 164 of anything at three metres either, so it had stopped being a measurement twice over.
   *
   * Isotype's own answer is to change the unit and say which unit it is, never to shrink the sign
   * or cap the row silently. The caption carries it, and the exact counts are in the caption too,
   * so nothing is lost by rounding the drawing. */
  const UNIT = total <= 40 ? 1 : total <= 400 ? 10 : 100;
  const rings = Math.round(total / UNIT), full = Math.round(closed / UNIT);
  let s = '';
  for (let i = 0; i < rings; i++) {
    const said = i < full ? 'An answered alert' : 'An alert still open';
    const one = sign(i < full ? 'rho-closed' : 'rho-open', i < full ? 'closed' : '', said);
    /* Each ring is a way to the Act section, where the alerts themselves are: from the wall it leaves the
       wall for Now (data-act-link); on Now it scrolls to the stage (data-stage-go). */
    s += `<a class="rl" href="#act" ${actLink ? 'data-act-link' : 'data-stage-go="act"'} title="${said}: go to Act" aria-label="${said}: go to Act">${one}</a>`;
  }
  /* The row is a texture of signs and the CAPTION is the readable part of it, so the caption is
   * what carries the role and what the three-metre floor is measured against. A sign is measured
   * against --sign-floor; a cap height is measured against a distance. */
  return `<div class="rho${small ? ' small' : ''}" data-component="rhoRow"`
    + ` id="rho" data-ref="${esc(ref || 'funnel')}" role="group" aria-label="${closed} of ${total} alerts answered">${s}</div>`
    + `<p class="note" data-role="rho" data-num="rho"`
    + ` data-cmp="against the ${total} alerts this node sent in 30 days">`
    + `${closed} of ${total} alerts answered · median ${r.median_minutes} min`
    + `${UNIT > 1 ? ` · one ring per ${UNIT}` : ''}</p>`;
}

/* The four stages of the ledger, from GET /rho.funnel. Each bar is a share of `asked` and the count
 * is beside it, because a share nobody can count is a mood.
 *
 * THE NODE'S WORDS, NOT THE PROTOTYPE'S. This drew reached · acknowledged · deployed · closed over a
 * synthetic `S.funnel` from a fixture, beside a 2x2 whose four cells no endpoint computed — invented
 * for the drawing. The node publishes asked · acknowledged · acted · measured (v0.68), so those are
 * the words, and the 2x2 is gone rather than kept as the one thing on the page with no source.
 *
 * TWO STAGES READ ZERO ON A REAL NODE AND BOTH SAY WHY. `acknowledged` can be written and nobody has
 * — the Telegram flow posts `acted` directly — so it is drawn empty with that sentence, because a
 * stage that could be non-zero and is not is a true fact about the household. `measured` is derived
 * from rule silence rather than posted (app/index.py::_funnel), which is why it carries no latency:
 * the evidence is a window, so it says whether the loop closed and never how fast. */
function funnel() {
  const f = S.rho && S.rho.funnel;
  if (!f) return '';
  const st = f.stages, top = st.asked;
  const lat = f.latency_minutes || {};
  const mins = m => m == null ? '' : m < 120 ? `${m} min` : `${Math.round(m / 60)} h`;
  const KEYS = [
    ['asked', { en: 'asked', id: 'diminta', es: 'pedido' }, null],
    ['acknowledged', { en: 'acknowledged', id: 'dilihat', es: 'visto' }, 'acknowledged'],
    ['acted', { en: 'acted', id: 'dikerjakan', es: 'hecho' }, 'acted'],
    ['measured', { en: 'measured', id: 'terukur', es: 'medido' }, 'measured'],
  ];
  /* A zero says why it is a zero, or it reads as a household that does not bother. The two are
   * different zeros: nobody has acknowledged anything here, which is a fact about the house; and on
   * a node whose version cannot derive the last stage there is nothing that could ever write it,
   * which is a fact about the node and not about anyone in it. */
  const why = {
    acknowledged: st.acknowledged ? '' : 'nothing has been acknowledged on this node',
    measured: f.measured_derived
      ? `the rule stayed quiet for ${Math.round((f.measured_window_minutes || 0) / 60)} h after the act`
      : st.measured ? ''
      : 'this node does not work out whether the condition cleared, so nothing can record this stage',
  };
  const rows = KEYS.map(([k, label, gap]) => {
    const n = st[k] || 0;
    return `<div class="st${n ? '' : ' none'}"><span class="k">${esc(label[LOC] || label.en)}</span>`
      + `<span class="bar"><i style="width:${top ? (100 * n / top).toFixed(1) : 0}%"></i></span>`
      + `<span class="lat"><span data-num="funnel.${k}"`
      + ` data-cmp="against ${top} alerts the node sent">${n}</span>`
      + `${gap && lat[gap] != null ? ` · +${esc(mins(lat[gap]))}` : ''}</span>`
      + `${why[k] ? `<span class="m">${esc(why[k])}</span>` : ''}</div>`;
  }).join('');
  return `<div class="funnel" data-component="funnel" id="funnel" data-ref="rho">${rows}`
    + `<p class="note">This node's own alerts only, over ${S.rho.window_days} days. `
    + `${esc(why.measured ? 'The last stage is derived, not recorded: nobody types it.' : '')}</p></div>`;
}

/* A peer node: another node's number, and the sentence saying what it must never become. */
function peerRow() {
  const p = S.peer;
  return `<div class="peer" data-component="peers" id="peer" data-ref="rho">${sign('machine')}`
    + `<div><b>${esc(p.node)}</b>`
    + `<span class="note"><span data-num="peer.pm25" data-cmp="no comparison yet · a peer is never `
    + `compared with this node's own reading">${esc(fmt(p.value.value, p.value.dp))} `
    + `${esc(p.value.unit)}</span> ${pill(p.value.provenance)} · heard ${esc(age(p.heard_minutes_ago))}`
    + ` · about ${esc(String(p.km))} km away</span>`
    + `<span class="note">${esc(p.never[LOC])}</span></div></div>`;
}

/* The Phase 1 wireframes are gone from the shipped page.
 *
 * They were grey bars standing in for text and outlined boxes standing in for controls, with a note
 * reading "Drawn, not built" — a drawing of a view, printed underneath the built version of that
 * same view. On a prototype that was the whole point. In production it is a keeper scrolling past
 * their own settings into a sketch of their own settings, which is what Tomas found at the bottom
 * of Set up and could not work out the purpose of. There was none: it shipped by being ported.
 *
 * tests/visual/measure.mjs still renders wireframes, and that is a different thing entirely — it
 * draws one FROM the page, as a measurement. Nothing draws one INTO the page any more.
 */

/* --------------------------------------------------------------------- the page's own state */
/* PORTED: a direction captured its views with ?view=, because a drawing is captured and never
 * navigated. This page is navigated, so the view is the hash — #now, #network, #setup, #wall — the
 * way the page it replaces routed, and ?view= is still read so a render can be asked for one
 * directly. ?state= stays: it is how the empty node and the refused page are captured. */
let VIEW = 'now';
let STATE = 'populated';
/* THE HASH IS THE VIEW — AND ONLY WHEN IT NAMES ONE.
 *
 * It used to be taken as the view whatever it said, so `#stage-act` — which is the lead's own link
 * to the Act stage, and the first thing a reader presses when the page says "94 asks open · in
 * 3 Act" — became a view called `stage-act`. There is no such view, so main() fell through to the
 * branch that draws Set up and drew a band titled STAGE-ACT with nothing in it. A blank page,
 * reached from the page's own link, reported from node #1.
 *
 * Every in-page anchor had the same effect: the notes band links back to the section each note
 * explains, and so does the ask line. One unknown hash and the page emptied itself.
 *
 * So an unknown hash is what it looks like — a link to somewhere ON this page — and the view is
 * whatever it already was. `?view=` still works, and every saved link still lands. */
const VIEW_NAMES = new Set(['now', 'historical', 'network', 'wall', 'arrange', 'setup']);
function readView() {
  const q = new URLSearchParams(location.search);
  const h = (location.hash || '').replace(/^#/, '');
  /* A hash that names no view is an anchor on THIS page, so with no ?view= it keeps the view the
     reader is on (the header's nav wrote #network; `#grain` must not send them to Now). Only a first
     load, where VIEW is still its initial 'now', or an empty hash, falls through to 'now'. */
  VIEW = VIEW_NAMES.has(h) ? h : (q.get('view') || (h && VIEW ? VIEW : 'now'));
  STATE = q.get('state') || 'populated';
  if (window.K) Object.assign(window.K, { VIEW, STATE });
}

/* The empty node and the refused page, from the same drawing. A direction has to answer for the
 * tester's first hour and for the stranger with no token, and a drawing that only ever shows a full
 * node is a drawing that has not been asked the hard question. */
function emptySnapshot() {
  for (const k of Object.keys(ISS)) {
    const d = ISS[k];
    d.state = 'none'; d.open_asks = [];
    d.stack = { room: null, yard: null, ring: null, region: null };
    d.series = { room: null, yard: null, ring: null, region: null };
    d.readouts = []; d.provenance = [];
    d.reason_text = { en: 'no source yet', id: 'belum ada sumber', es: 'aún no hay fuente' };
    d.sentence = { en: emptyLine(k), id: emptyLine(k), es: emptyLine(k) };
  }
  S.issues.headline = ORDER[0];
  S.rho = { window_days: 30, alerts_act: 0, acted: 0, rho: null, median_minutes: null };
  S.peer = null;
}
const emptyLine = k => ({
  air: 'No air sensor here yet, and no model for this point.',
  heat: 'No temperature and humidity here yet.',
  coast: 'No marine model for this point yet.',
  land: 'No satellite record yet for this square.',
  water: 'No water probe here yet.',
}[k] || 'Nothing here yet.');

const REFUSED = {
  household: 'This node is not sharing its readings with the network.',
  /* Only used when a 403 arrives with no `error` key. It says the shape of the refusal and stops
     short of the remedy, because which remedy applies is the node's to say and not this file's. */
  node: 'This node answers /issues only to the machine it runs on, or to a request carrying a token.',
  todo: 'Ask whoever set this node up to turn sharing on, or open this page on the machine the node '
    + 'runs on.',
};

function refusedPage(said) {
  /* `said` is the node's own 403 body, captured at the fetch (see Refused()). Print it, never a copy:
   * the node decides what advice its refusal carries — for a path no share level opens it says a token
   * is the only way in, and a hardcoded paraphrase here sent that reader to change a setting and come
   * back to the same refusal. REFUSED.node is the fallback for a 403 with no `error` key at all. */
  return `<div class="refused" data-component="refused" id="refused" data-ref="header">`
    + `<p class="big" data-role="sentence">${esc(REFUSED.household)}</p>`
    + `<p class="why">${esc(said || REFUSED.node)}</p>`
    + `<p class="note">${esc(REFUSED.todo)}</p></div>`;
}

/* Every module reads these. The functions are bound now; the data and the view are bound by
 * initKit() once boot() has answered, because until then there is nothing to bind. */
/* Fill a {placeholder} sentence from the words table. Restored with the network figure, which
   is the only thing on this page whose copy is interpolated rather than assembled. */
const interp = (str, vals) => String(str || '')
  .replace(/\{(\w+)\}/g, (_, k) => (vals[k] == null ? '' : vals[k]));
/* The pack half of a `pack/rule` id, or '' for one from before packs named their rules: a node's ledger
   keeps those (node #1: `indoor_pm25_high`), and every section that names a rule's pack reads it here. */
const rulePack = id => { const s = String(id); return s.includes('/') ? s.split('/')[0] : ''; };

/* ALERT EVENTS (docs/SPEC_dashboard_events.md §4.2). One per issue per house, the way the bot tells them:
 * the node chose the action and wrote the message, and this draws them. Which of five states Decide is in is
 * the first thing every caller needs, and the five are different facts (spec §5). */
function evState() {
  const e = (S.issues || {}).events;
  if (e == null) return 'old';
  if (e.error) return 'error';
  return e.engine === 'shadow' || e.engine === 'events' ? e.engine : 'rules';
}
const evOpen = () => (((S.issues || {}).events || {}).open || []);
/* The event simple mode's row is about: the shown issue's, else the first open one. */
const evPick = (evs, hk) => evs.find(e => e.issue === hk) || evs[0];
/* The button word an answer's stage stands for, in the node's own labels (events.buttons). The same three
   the buttons wear, so an answer reads as the button that wrote it. */
function evWord(stage) {
  const B = ((S.issues || {}).events || {}).buttons || {};
  return stage === 'acted' ? B.done || 'Done' : stage === 'dismissed' ? B.doesnt_fit || 'Doesn’t fit'
    : B.not_now || 'Not now';
}
function evClock(iso) {
  const t = new Date(iso);
  if (isNaN(t)) return '';
  const tz = S.health && S.health.tz;
  if (tz) {
    try {
      return new Intl.DateTimeFormat('en-GB', { timeZone: tz, hour: '2-digit', minute: '2-digit',
        hour12: false }).format(t);
    } catch { /* a zone this browser does not know: say UTC */ }
  }
  return `${String(t.getUTCHours()).padStart(2, '0')}:${String(t.getUTCMinutes()).padStart(2, '0')} UTC`;
}
function evButtons(e) {
  const B = ((S.issues || {}).events || {}).buttons || {};
  const id = esc(String(e.id));
  return `<div class="evbtns">`
    + `<button type="button" class="evb pri" data-ev="${id}" data-stage="acted">${esc(B.done || 'Done')}</button>`
    + `<button type="button" class="evb" data-ev="${id}" data-stage="acknowledged">${esc(B.not_now || 'Not now')}</button>`
    + `<button type="button" class="evb" data-ev="${id}" data-stage="dismissed">${esc(B.doesnt_fit || 'Doesn’t fit')}</button>`
    + `</div>`
    + `<form class="evform" hidden data-ev="${id}"><input type="hidden" name="stage">`
    + `<label><span>Who</span><input name="actor" maxlength="80" autocomplete="name" placeholder="your name"></label>`
    + `<label class="instead"><span>What did you do instead?</span><input name="note" maxlength="500"`
    + ` placeholder="optional"></label>`
    + `<div class="btns"><button type="submit" class="pri">Record it</button>`
    + `<button type="button" class="cancel">Cancel</button></div>${TOKEN_FINE}</form>`;
}
/* The line an answered event wears: who pressed which button, when, and until when a Not now holds. Empty
   before an answer. Decide's card and simple mode's row both draw it. A Doesn't fit with a note carries the
   household's own words — the answer to the bot's one question, "what did you do instead?" */
function evAnswered(e) {
  const a = e.answer, done = a && a.stage === 'acted';
  return !a ? '' : `<p class="${done ? 'evdone' : 'evheld'}">`
    + `${done ? sign('rho-closed', 'closed') : ''}${esc(evWord(a.stage))} · ${esc(a.actor || 'somebody')}`
    + ` · ${esc(evClock(a.ts))}${a.held_until ? ` · held until ${esc(evClock(a.held_until))}`
      + ` unless it reaches danger` : ''}`
    + `${a.note ? `<span class="evnote"> — “${esc(a.note)}”</span>` : ''}</p>`;
}
/* `tail` is drawn inside the card, last: Decide puts the folded rule rows there (spec §4.2). */
/* The live stamp. Everything else on the card is event-scoped — peak, message, context — so an event that
 * stays open for hours (the margin doing its work on a hot night, docs/decisions/2026-10-10) reads as frozen
 * while the engine is stepping every minute. The wire already carries last_seen_at; the card says so, and the
 * age ticks up on every poll, which is the visible proof the feed is alive. No current value here: the hero's
 * value is not in the event's measure (heat's hero is air temperature, the event is apparent), and the card
 * will not mix the two. */
function evLive(e) {
  const t = new Date(e.last_seen_at || '');
  if (isNaN(t)) return '';
  return ` · <span class="m">watching — last seen ${esc(age((Date.now() - t.getTime()) / 6e4))}</span>`;
}
function evCard(e, tail = '') {
  const d = ISS[e.issue] || { name: {} }, h = d.hero || {}, dp = d.dp == null ? 1 : d.dp, unit = d.unit || '';
  const st = evState(), c = e.context || {}, a = e.answer;
  const n = v => (v == null ? null : fmt(v, dp));
  const out = c.outside == null ? null : `outside ${n(c.outside)}`
    + (c.outside_metric === 'temp' && d.metric !== 'temp' ? ' (air temperature)' : '')
    + (c.outside_from ? `, from ${c.outside_from}` : '');
  const cmp = [c.usual == null ? 'no usual for this hour yet' : `usual at this hour ${n(c.usual)}`,
    out || 'no outside reading', e.line == null ? 'no line' : `the line ${n(e.line)}`].join(' · ');
  const worse = e.line != null && e.peak != null && e.peak > e.line;
  const m = e.message;
  const said = !m ? '' : `<p class="evmsg"><span class="m">${st === 'shadow' ? 'would have sent'
    : m.sent ? 'sent' : 'held'} ${esc(evClock(m.ts))}</span><span class="said">${esc(m.text || '')}</span></p>`;
  const done = a && a.stage === 'acted', answered = evAnswered(e);
  const rows = (e.alerts || []).length;
  /* A link goes only to a section this page is drawing: `sensors` belongs to a pack a node may not run, and
     Arrange may have hidden any of them. */
  const drawn = id => window.PAI.sections.some(s => s.id === id && (s.needs || []).every(window.PAI.has))
    && !(window.PAI.isHidden && window.PAI.isHidden(id));
  const links = [drawn('matrix') && `<a href="#matrix">${esc(d.name[LOC] || e.issue)} at every distance</a>`,
    drawn('day') && `<a href="#day">the day</a>`, drawn('sensors') && `<a href="#sensors">the stations</a>`,
    rows && `<a href="#evrows-${esc(String(e.id))}">from ${rows} rule row${rows === 1 ? '' : 's'}</a>`]
    .filter(Boolean);
  return `<section class="ev${a && a.stage === 'acknowledged' ? ' held' : ''}" id="ev-${esc(String(e.id))}"`
    + ` data-kind="readout" data-component="event" data-role="ask" data-ref="decide">`
    + `<div class="evhead">${h.sign ? `<svg class="sgn" viewBox="0 0 24 24" role="img" aria-label="`
      + `${esc(d.name[LOC] || e.issue)}"><use href="static/signs.svg#${esc(h.sign)}"/></svg>` : ''}`
    + `<b>${esc(d.name[LOC] || e.issue)}</b> · ${esc(e.kind)} · since ${esc(evClock(e.opened_at))}`
    + `${(e.rooms || []).length ? ` · ${esc(e.rooms.join(', '))}` : ''}`
    + evLive(e)
    + `${st === 'shadow' ? `<span class="m">shadow — nothing was sent</span>` : ''}</div>`
    + `<p class="evcmp"><span class="evnum${worse ? ' worse' : ''}" data-num="ev.${esc(String(e.id))}.peak"`
    + ` data-cmp="${esc(cmp)}">${esc(n(e.peak))}</span> ${esc(unit)} peak <small>${esc(cmp)}</small></p>`
    + (e.action && e.action.text ? `<p class="evact said">${esc(e.action.text)}</p>`
      : `<p class="evact none">The node chose no action for this event, and this page will not invent one.</p>`)
    + answered + (done ? '' : evButtons(e)) + said
    + (links.length ? `<p class="evlinks">evidence: ${links.join(' · ')}</p>` : '')
    + tail + `</section>`;
}

/* --------------------------------------------------------------------------- 6 · figures */
/* Drawn with Observable Plot (static/plot.umd.min.js, with its d3 in static/d3.min.js), vendored so the page draws
 * on a LAN with no route out (docs/SPEC_dashboard_figures.md §4). The page is HTML strings and Plot makes DOM nodes,
 * so a figure is a placeholder in the string and a draw function kept here; route() calls mountFigs() after it has
 * replaced the page, and a figure redraws when its column changes width by more than 20 px.
 *
 * NOTHING HERE MAY TOUCH A BROWSER GLOBAL AT LOAD. tests/test_dashboard.py loads this whole file in node, where
 * there is no ResizeObserver, no CSS and no Plot; they are reached only inside functions a browser calls. */
const FIGS = new Map();
let FIG_RO = null;

function fig(id, draw, o = {}) {
  FIGS.set(id, draw);
  return `<div class="f-fig" id="${esc(id)}" data-kind="series" data-component="${esc(o.component || 'figure')}"`
    + ` data-ref="${esc(o.ref || '')}"${o.keys ? ' tabindex="0"' : ''} role="group"`
    + ` aria-label="${esc(o.label || '')}"></div>`;
}

function paintFig(el) {
  try {
    el.replaceChildren();
    el.__fig.draw(el, Math.max(280, el.__fig.w || 720));
  } catch (e) {
    el.innerHTML = `<p class="note" data-component="failed" id="${esc(el.id)}-failed" data-ref="${esc(el.id)}">`
      + `This drawing did not render: ${esc(String((e && e.message) || e))}. Its numbers are in the sentence `
      + `and the matrix beside it.</p>`;
  }
}

function mountFigs(root) {
  if (FIG_RO) FIG_RO.disconnect();
  FIG_RO = typeof ResizeObserver === 'function' ? new ResizeObserver(es => {
    for (const e of es) {
      const f = e.target.__fig, w = Math.round(e.contentRect.width);
      if (f && Math.abs(w - f.w) > 20) { f.w = w; paintFig(e.target); }
    }
  }) : null;
  for (const [id, draw] of FIGS) {
    const el = root.querySelector(`#${CSS.escape(id)}`);
    if (!el) continue;
    el.__fig = { draw, w: Math.round(el.clientWidth) };
    paintFig(el);
    if (FIG_RO) FIG_RO.observe(el);
  }
  FIGS.clear();
}

/* The box a drawing is read against: the data's own range, padded, and never below zero for readings that are all
 * non-negative. The trace printed "floor -20 µg/m³, not zero" on node #1 on 6 October: headroom under a floor that
 * does not exist. */
const boxOf = (vals, line, pad = 0.12) => {
  const all = vals.filter(v => v != null && Number.isFinite(v)).concat(line == null ? [] : [line]);
  if (!all.length) return null;
  const lo = Math.min(...all), hi = Math.max(...all), p = (hi - lo) * pad || Math.abs(hi * 0.1) || 1;
  return { lo: lo >= 0 ? Math.max(0, lo - p) : lo - p, hi: hi + p };
};
/* A time string's own offset in minutes ("+08:00" is 480), so a label says the node's hour, never the reader's. */
const offsetOf = iso => {
  const m = /([+-])(\d\d):(\d\d)$/.exec(String(iso || ''));
  return m ? (m[1] === '-' ? -1 : 1) * (+m[2] * 60 + +m[3]) : 0;
};
/* A wire time's local day, hour and hh:mm, read in that string's own offset (docs/SPEC_dashboard_figures.md §3.4,
 * §4.2): a bucket, an event, an answer and a last_heard each say their own hour, so a node that changes clock labels
 * both sides of the change right. Reading every bucket in the last one's offset drew a Madrid day before 25 October
 * an hour early. `ms` reads another instant in the string's offset (a station's empty hour, named by the bucket
 * before it; the node's now, in its latest bucket's offset). A time that does not parse is '—', never a throw. */
const localOf = (iso, ms = Date.parse(iso)) => {
  if (!Number.isFinite(ms)) return { day: '—', hour: null, hhmm: '—' };
  const s = new Date(ms + offsetOf(iso) * 60000).toISOString();
  return { day: s.slice(0, 10), hour: +s.slice(11, 13), hhmm: s.slice(11, 16) };
};
/* The register button restyles in place, and the strips' shade ramp is two literal colours read at draw time, so the
 * drawings on the page are painted again in the register now on. */
const repaintFigs = () => document.querySelectorAll('.f-fig').forEach(el => el.__fig && paintFig(el));
function nearestIndex(ts, t) {
  let b = 0;
  for (let i = 1; i < ts.length; i++) if (Math.abs(ts[i] - t) < Math.abs(ts[b] - t)) b = i;
  return b;
}
/* A token's value in the register on now, for the one place a colour has to be a colour and not a variable: the
 * strips' shade ramp, which d3 interpolates. */
const tokenOf = name => getComputedStyle(document.documentElement).getPropertyValue(name).trim();

const PLOT_STYLE = { background: 'transparent', color: 'var(--ink)', fontFamily: 'var(--mono)', fontSize: '11px',
  overflow: 'visible' };
const DASH = { room: null, yard: '4 3', ring: '1 5', region: '6 4' };
const ANSWER = { acted: 'Done', acknowledged: 'Not now', dismissed: 'Doesn’t fit' };
const USUAL_WHY = { unread: 'the usual could not be read', no_source: 'no source at this distance',
  no_history: 'not enough days at this hour yet', not_watched: 'not watched here' };

/* THE DAY FIGURE (docs/SPEC_dashboard_figures.md §4.2). One `series` card per issue: every distance, the usual band,
 * the line and the hours over it, the event that opened and its answer, the event's own rooms, and a readout that
 * says in words what the crosshair is on. It replaces the traces and Measure's second copy of them. */
function dayFigure(key, d, o = {}) {
  const id = o.id || `day-fig-${key}`, ref = o.ref || 'days';
  const ser = d.series || {};
  const sets = DIST.filter(x => Array.isArray(ser[x]) && ser[x].some(v => v != null));
  if (!sets.length) {
    return `<p class="note" id="${esc(id)}" data-ref="${esc(ref)}">The day it just had: nothing recorded yet at `
      + `any distance.</p>`;
  }
  const B = d.buckets || [], T = B.map(b => Date.parse(b)), L = B.map(b => localOf(b));
  const now = Math.max(Date.parse(((S || {}).issues || {}).as_of) || 0, T[T.length - 1]);
  const hero = sets.includes(d.headline) ? d.headline : sets[0];
  const line = d.line ? d.line.value : null;
  const U = d.usual && d.usual.hours ? d.usual.hours : null;
  const band = U ? T.map((t, i) => ({ t: new Date(t), ...(U[L[i].hour] || {}) })) : [];
  const E = ((S || {}).issues || {}).events || {};
  const evs = (E.open || []).concat(E.recent || []).filter(e => e.issue === key)
    .map(e => ({ e, o: Date.parse(e.opened_at), c: e.cleared_at ? Date.parse(e.cleared_at) : now,
      a: e.answer ? Date.parse(e.answer.ts) : null }))
    .filter(x => x.c >= T[0]);
  const roomsOf = evs.map(x => x.e.series).find(s => s && Array.isArray(s.values) && s.values.length === T.length);
  const box = boxOf(sets.flatMap(k => ser[k]).concat(band.flatMap(b => [b.median, b.p90]))
    .concat(roomsOf ? roomsOf.values : []), line);
  const overAt = i => line != null && sets.some(k => ser[k][i] != null && ser[k][i] > line);
  const over = T.filter((t, i) => overAt(i));
  const above = T.filter((t, i) => !overAt(i) && band[i] && band[i].p90 != null && ser[hero][i] != null
    && ser[hero][i] > band[i].p90);
  const unit = d.unit || '', dp = d.dp;
  const first = ser[hero].find(v => v != null), last = [...ser[hero]].reverse().find(v => v != null);
  const idle = `<b>24 h</b><span>${esc(LAB[hero])} opened the day at ${esc(fmt(first, dp))} and closed it at `
    + `${esc(fmt(last, dp))} ${esc(unit)}</span>`
    + (over.length ? `<span class="f-over">${over.length} of ${T.length} hours over the line</span>` : '')
    + (U ? `<span class="f-usual">${above.length} above the usual, under the line</span>` : '')
    + `<span class="f-gone">point at an hour, or focus the drawing and use ← →</span>`;
  const readAt = i => {
    const ev = evs.find(x => T[i] >= x.o && T[i] <= x.c);
    return `<b>${esc(L[i].hhmm)}</b>`
      + sets.map(k => `<span class="f-d f-${k}${ser[k][i] == null ? ' f-gone' : ''}"><i></i>${esc(LAB[k])} `
        + `${ser[k][i] == null ? 'nothing recorded' : esc(fmt(ser[k][i], dp))}</span>`).join('')
      + (roomsOf && roomsOf.values[i] != null ? `<span class="f-d f-rooms"><i></i>${esc(roomsOf.rooms.join(', '))} `
        + `${esc(fmt(roomsOf.values[i], dp))}</span>` : '')
      + (band[i] && band[i].median != null ? `<span class="f-usual">usual ${esc(fmt(band[i].median, dp))} to `
        + `${esc(fmt(band[i].p90, dp))}</span>` : '')
      + (overAt(i) ? `<span class="f-over">over the line ${esc(fmt(line, dp))}</span>` : '')
      + (ev ? `<span class="f-ev">${esc(ev.e.kind)} open · ${ev.e.answer
        ? `<b class="${ev.e.answer.stage === 'acted' ? 'f-done' : ''}">${esc(ANSWER[ev.e.answer.stage] || ev.e.answer.stage)}</b>`
          + ` · ${esc(ev.e.answer.actor || '')} ${esc(localOf(ev.e.answer.ts).hhmm)}` : 'no answer'}</span>` : '');
  };
  const draw = (el, W) => {
    const narrow = W < 600, H = narrow ? 170 : 230, pad = (box.hi - box.lo) * 0.06, evY = box.hi - pad;
    const at = T.map(t => new Date(t));
    const rows = k => ser[k].map((v, i) => ({ t: at[i], v }));
    const lone = k => rows(k).filter((r, i, a) => r.v != null && (i === 0 || a[i - 1].v == null)
      && (i === a.length - 1 || a[i + 1].v == null));
    const late = x => (x.o - T[0]) / ((now - T[0]) || 1) > 0.8;
    const label = x => (narrow ? x.e.kind : `${x.e.kind} · ${localOf(x.e.opened_at).hhmm}`);
    const ev = evs.map(x => ({ ...x, o: new Date(x.o), c: new Date(x.c), a: x.a == null ? null : new Date(x.a) }));
    const svg = Plot.plot({
      width: W, height: H, marginLeft: 8, marginRight: 8, marginTop: 18, marginBottom: 26, style: PLOT_STYLE,
      x: { type: 'time', domain: [new Date(T[0]), new Date(now)], label: null, tickSize: 0,
        ticks: at.filter((t, i) => L[i].hour % (narrow ? 6 : 3) === 0), tickFormat: t => (L[T.indexOf(+t)] || {}).hhmm },
      y: { domain: [box.lo, box.hi], axis: null },
      marks: [
        Plot.gridY({ ticks: 4, stroke: 'var(--hair)', strokeOpacity: 1 }),
        U ? Plot.areaY(band.filter(b => b.median != null && b.p90 != null),
          { x: 't', y1: 'median', y2: 'p90', fill: 'var(--ink)', fillOpacity: 0.1 }) : null,
        line == null ? null : Plot.ruleY([line], { stroke: 'var(--signal-worse)', strokeDasharray: '3 6', strokeOpacity: 0.85 }),
        Plot.ruleX(over.map(t => new Date(t)), { y1: box.lo, y2: box.lo + pad, stroke: 'var(--signal-worse)', strokeWidth: 2 }),
        Plot.ruleX(above.map(t => new Date(t)), { y1: box.lo, y2: box.lo + pad, stroke: 'var(--ink)', strokeOpacity: 0.6, strokeWidth: 2 }),
        ...sets.map(k => Plot.lineY(rows(k), { x: 't', y: 'v', stroke: 'var(--ink)', strokeWidth: 1.6,
          strokeOpacity: k === hero ? 1 : 0.55, strokeDasharray: DASH[k] || undefined })),
        ...sets.map(k => Plot.dot(lone(k), { x: 't', y: 'v', r: 1.8, fill: 'var(--ink)', fillOpacity: k === hero ? 1 : 0.55 })),
        roomsOf ? Plot.lineY(roomsOf.values.map((v, i) => ({ t: at[i], v })), { x: 't', y: 'v', stroke: 'var(--ink)', strokeWidth: 2.6 }) : null,
        Plot.ruleY(ev, { y: evY, x1: 'o', x2: 'c', stroke: 'var(--ink)', strokeWidth: 5, strokeOpacity: 0.22 }),
        Plot.text(ev.filter(x => !late(x)), { x: 'o', y: evY, text: label, textAnchor: 'start', dx: 4, dy: -9, fill: 'var(--mute)', fontSize: 10.5 }),
        Plot.text(ev.filter(late), { x: 'c', y: evY, text: label, textAnchor: 'end', dx: -4, dy: -9, fill: 'var(--mute)', fontSize: 10.5 }),
        Plot.ruleY(ev.filter(x => x.a && x.a > x.c), { y: evY, x1: 'c', x2: 'a', stroke: 'var(--ink)', strokeOpacity: 0.35, strokeDasharray: '1 3' }),
        Plot.dot(ev.filter(x => x.a && x.e.answer.stage === 'acted'), { x: 'a', y: evY, r: 4.5, stroke: 'var(--rings)', strokeWidth: 2, fill: 'var(--ground)' }),
        Plot.dot(ev.filter(x => x.a && x.e.answer.stage !== 'acted'), { x: 'a', y: evY, r: 4.5, stroke: 'var(--ink)', strokeWidth: 2, fill: 'var(--ground)' }),
        Plot.ruleX([new Date(now)], { stroke: 'var(--ink)', strokeOpacity: 0.35 }),
      ].filter(Boolean),
    });
    const inner = document.createElement('div'); inner.className = 'f-in';
    const hair = document.createElement('i'); hair.className = 'f-hair'; hair.hidden = true;
    inner.append(svg, hair); el.append(inner);
    const read = document.getElementById(`${id}-read`);
    const xs = svg.scale('x');
    let cur = null;
    const show = i => {
      cur = i;
      if (read) read.innerHTML = i == null ? idle : readAt(i);
      if (i == null) { hair.hidden = true; return; }
      const r = svg.getBoundingClientRect();
      hair.hidden = false;
      hair.style.left = `${(xs.apply(at[i]) * r.width) / W}px`;
    };
    svg.addEventListener('pointermove', e => {
      const r = svg.getBoundingClientRect();
      show(nearestIndex(T, +xs.invert(((e.clientX - r.left) * W) / r.width)));
    });
    svg.addEventListener('pointerleave', () => show(null));
    el.onkeydown = e => {
      if (e.key !== 'ArrowLeft' && e.key !== 'ArrowRight') return;
      e.preventDefault();
      show(cur == null ? T.length - 1 : Math.max(0, Math.min(T.length - 1, cur + (e.key === 'ArrowLeft' ? -1 : 1))));
    };
    el.onblur = () => show(null);
  };
  const gone = DIST.filter(x => !sets.includes(x));
  const legend = sets.map(k => `<span class="f-d f-${k}"><i></i>${esc(LAB[k])}</span>`).join('')
    + (roomsOf ? `<span class="f-d f-rooms"><i></i>the event’s own ${roomsOf.rooms.length === 1 ? 'room' : 'rooms'}</span>` : '')
    + gone.map(k => `<span class="f-gone"><i></i>${esc(LAB[k])} — ${esc(reasonFor(d, k))}</span>`).join('')
    + (U ? `<span class="f-band"><i></i>usual at this hour, last ${d.usual.window_days} days</span>`
      : `<span class="f-gone">no usual band — ${esc(USUAL_WHY[d.usual_absent] || 'this node does not send one yet')}</span>`)
    + (over.length ? `<span class="f-over"><i></i>hours over the line</span>` : '')
    + (evs.length ? `<span class="f-evl"><i></i>event, opened to cleared</span>` : '')
    + (evs.some(x => x.e.answer && x.e.answer.stage === 'acted') ? `<span class="f-done"><i></i>answered Done</span>` : '');
  const altCmp = line != null ? `against the line, ${fmt(line, dp)} ${unit} · ${d.line.source}`
    : `no comparison yet · ${noLine(d)}`;
  return `<div class="f-day" data-kind="series" data-component="dayFigure" id="${esc(id)}-card" data-ref="${esc(ref)}">`
    + `<p class="f-head"><span>${esc(fmt(box.hi, dp))} ${esc(unit)} top · floor ${esc(fmt(box.lo, dp))}`
    + `${box.lo === 0 ? '' : ', not zero'}</span>${line != null ? `<span class="f-line">the line ${esc(fmt(line, dp))}</span>` : ''}</p>`
    + fig(id, draw, { ref: `${id}-card`, component: 'dayDrawing', keys: true,
      label: `${d.name[LOC]}, the last 24 hours at every distance; focus and use the arrow keys to read an hour` })
    + `<p class="f-read" id="${esc(id)}-read" aria-live="polite">${idle}</p>`
    + `<p class="f-legend">${legend}</p>`
    + `<p class="f-alt"><span data-num="${esc(key)}.day" data-cmp="${esc(altCmp)}">${esc(LAB[hero])} opened the day at `
    + `${esc(fmt(first, dp))} and closed it at ${esc(fmt(last, dp))} ${esc(unit)}</span> — ${esc(altCmp)}.`
    + (evs.length ? ` ${evs.length === 1 ? 'One event' : `${evs.length} events`} in these hours: `
      + evs.map(x => `${x.e.kind} ${localOf(x.e.opened_at).hhmm} to ${x.e.cleared_at ? localOf(x.e.cleared_at).hhmm : 'now'}, `
        + `${x.e.answer ? `${(ANSWER[x.e.answer.stage] || x.e.answer.stage).toLowerCase()} by ${x.e.answer.actor}` : 'no answer'}`)
        .map(esc).join('; ') + '.' : '')
    + `</p></div>`;
}

/* THE STRIPS (docs/SPEC_dashboard_figures.md §4.3). One row a day, one cell an hour, newest at the bottom, from
 * GET /issues/days. Ink on the issue's own square-root scale; red over the line; an outlined empty cell where
 * nothing was recorded, never a pale cell that looks low. The right column is the node's own count. */
function strips(key, D, o = {}) {
  const id = o.id || `strips-${key}`, ref = o.ref || 'days';
  const it = D && D.issues ? D.issues[key] : null;
  const name = ((ISS[key] || {}).name || {})[LOC] || key;
  if (!D) {
    return `<p class="note" id="${esc(id)}" data-ref="${esc(ref)}">This node does not send its days yet `
      + `(GET /issues/days); the strips of ${esc(name)} wait for it.</p>`;
  }
  if (!it || !it.distance) {
    return `<p class="note" id="${esc(id)}" data-ref="${esc(ref)}">No hourly record of ${esc(name)} in these `
      + `${D.days} days.</p>`;
  }
  const dist = it.distance, vals = it.series[dist], line = it.line ? it.line.value : null;
  const T = D.buckets.map(b => Date.parse(b));
  /* The strips start at the first local day that holds a reading: a 90-day window on a node with 35 days of record
     drew 55 empty rows before it began (node #1, 6 October). An hour with nothing recorded after that still shows. */
  /* Each bucket in its own day and hour. ponytail: a fall-back day repeats 02:00, so its two buckets share one cell and
     the second paints over the first; per_day's `of: 25` beside the row still says the day had 25 hours. A row of 25
     cells is the upgrade if a household asks which 02:00 it was. */
  const every = D.buckets.map((b, i) => { const l = localOf(b); return { day: l.day, hour: l.hour, t: T[i], v: vals[i] }; });
  const firstDay = every.find(c => c.v != null).day;
  const cells = every.filter(c => c.day >= firstDay);
  const days = [...new Set(cells.map(c => c.day))];
  const trimmed = days.length < new Set(every.map(c => c.day)).size;
  const got = cells.filter(c => c.v != null);
  const lo0 = Math.min(...got.map(c => c.v)), hi0 = Math.max(...got.map(c => c.v));
  const floor = lo0 >= 0 && lo0 < hi0 * 0.2 ? 0 : lo0;
  const ev = (D.events || []).filter(e => e.issue === key).map(e => ({ ...e, o: Date.parse(e.opened_at),
    c: e.cleared_at ? Date.parse(e.cleared_at) : T[T.length - 1] }));
  const inEvent = c => ev.some(e => c.t >= e.o - 3600e3 + 1 && c.t <= e.c);
  const perDay = Object.fromEntries((it.per_day || []).map(p => [p.date, p]));
  const dp = (ISS[key] || {}).dp, unit = (ISS[key] || {}).unit || '';
  const wd = s => new Date(`${s}T00:00:00Z`).toUTCString().slice(0, 11);
  const draw = (el, W) => {
    const narrow = W < 600, rowH = narrow ? 11 : 13;
    const svg = Plot.plot({
      width: W, height: 26 + days.length * rowH, marginLeft: narrow ? 70 : 92, marginRight: narrow ? 64 : 220,
      marginTop: 20, marginBottom: 6, style: PLOT_STYLE,
      x: { type: 'band', domain: Array.from({ length: 24 }, (_, h) => h), axis: 'top', label: null, tickSize: 0,
        padding: 0.12, tickFormat: h => (h % (narrow ? 6 : 3) === 0 ? String(h).padStart(2, '0') : '') },
      y: { type: 'band', domain: days, label: null, tickSize: 0, padding: 0.18,
        tickFormat: (s, i) => (i === 0 || new Date(`${s}T00:00:00Z`).getUTCDay() === 1 ? wd(s) : '') },
      color: { type: 'sqrt', domain: [floor, hi0], range: [tokenOf('--ground'), tokenOf('--ink')] },
      marks: [
        Plot.cell(cells.filter(c => c.v == null), { x: 'hour', y: 'day', fill: 'none', stroke: 'var(--hair)' }),
        Plot.cell(got.filter(c => line == null || c.v <= line), { x: 'hour', y: 'day', fill: 'v' }),
        Plot.cell(got.filter(c => line != null && c.v > line), { x: 'hour', y: 'day', fill: 'var(--signal-worse)' }),
        Plot.cell(cells.filter(inEvent), { x: 'hour', y: 'day', fill: 'none', stroke: 'var(--ink)', strokeWidth: 1.4 }),
        Plot.text(days.filter(s => perDay[s]), { x: () => 23, y: s => s, dx: narrow ? 22 : 30, textAnchor: 'start',
          fontSize: 10.5, text: s => (!perDay[s].read ? '—' : perDay[s].over == null ? '' : perDay[s].over ? `${perDay[s].over} h over` : '·'),
          fill: s => (perDay[s].read && perDay[s].over ? 'var(--signal-worse)' : 'var(--dim)') }),
        narrow ? null : Plot.text(ev, { x: () => 23, y: e => localOf(e.opened_at).day, dx: 96, textAnchor: 'start', fontSize: 10.5,
          fill: 'var(--ink)', text: e => `${e.kind} ${localOf(e.opened_at).hhmm}–${e.cleared_at ? localOf(e.cleared_at).hhmm : 'open'}` }),
        Plot.cell(cells, Plot.pointer({ x: 'hour', y: 'day', fill: 'none', stroke: 'var(--cells)', strokeWidth: 2 })),
      ].filter(Boolean),
    });
    el.append(svg);
    const read = document.getElementById(`${id}-read`);
    svg.addEventListener('input', () => {
      const c = svg.value;
      if (!read) return;
      if (!c) { read.innerHTML = idle; return; }
      const e = ev.find(x => c.t >= x.o - 3600e3 + 1 && c.t <= x.c);
      read.innerHTML = `<b>${esc(wd(c.day))} ${esc(String(c.hour).padStart(2, '0'))}:00</b>`
        + `<span>${esc(LAB[dist])} ${c.v == null ? 'nothing recorded' : `${esc(fmt(c.v, dp))} ${esc(unit)}`}</span>`
        + (line != null && c.v != null && c.v > line ? `<span class="f-over">over the line</span>` : '')
        + (e ? `<span class="f-ev">${esc(e.kind)} open</span>` : '');
    });
  };
  const nd = `${days.length} day${days.length === 1 ? '' : 's'}`;
  const totals = (it.per_day || []).filter(p => p.date >= firstDay).reduce((a, p) => ({ over: a.over + (p.over || 0), read: a.read + p.read,
    of: a.of + p.of }), { over: 0, read: 0, of: 0 });
  /* With no line the node counts no hours over it (per_day.over is null), so the readout says what was read and nothing
     about over: a 0 there would be a count nobody made. */
  const gone = `<span class="f-gone">${totals.of - totals.read} not recorded · point at a cell</span>`;
  const idle = line == null ? `<span>${totals.read} hour${totals.read === 1 ? '' : 's'} read in ${nd}</span>${gone}`
    : `<span data-num="${esc(key)}.days.over" data-cmp="`
      + `${esc(`of ${totals.read} hour${totals.read === 1 ? '' : 's'} read in ${nd}, ${totals.of - totals.read} not recorded`)}">`
      + `${totals.over} hour${totals.over === 1 ? '' : 's'} over the line</span>${gone}`;
  return `<div class="f-strips" data-kind="series" data-component="strips" id="${esc(id)}-card" data-ref="${esc(ref)}">`
    + `<p class="f-head"><span>${esc(name)} · ${esc(LAB[dist])} · ${nd}${trimmed ? `, from ${esc(wd(firstDay))}, the first this node recorded` : ''}</span>`
    + `<span>shades ${esc(fmt(floor, dp))} to ${esc(fmt(hi0, dp))} ${esc(unit)}${line != null
      ? ` · <span class="f-line">the line ${esc(fmt(line, dp))}</span>` : ''}</span></p>`
    + fig(id, draw, { ref: `${id}-card`, component: 'stripsDrawing',
      label: `${name}, one row a day and one cell an hour over ${nd}` })
    + `<p class="f-read" id="${esc(id)}-read" aria-live="polite">${idle}</p>`
    + `<p class="f-legend"><span class="f-lo"><i></i>low</span><span class="f-hi"><i></i>high, on this issue’s own scale</span>`
    + (line != null ? `<span class="f-red"><i></i>an hour over the line</span>` : '') + `<span class="f-gap"><i></i>nothing recorded</span>`
    + `<span class="f-evc"><i></i>an alert event</span></p></div>`;
}

window.K = { esc, fmt, sign, pill, age, uid, cmpText, interp, rulePack, meterBar, METER_CELLS, msToken,
  readout, stack, row, kicker, sentence, why, ask, didButton, stamp, asof, rhoRow, funnel,
  peerRow, refusedPage, noLine, reasonFor, REFUSED, TOKEN_FINE,
  evState, evOpen, evPick, evClock, evButtons, evAnswered, evCard, evWord, fig, mountFigs, repaintFigs, boxOf, localOf, nearestIndex, PLOT_STYLE,
  dayFigure, strips };

/* The one place the page's data is bound. boot() has answered by now; nothing above this line ran
 * against a global that was not there. */
function initKit() {
  S = window.SNAP;
  /* the household's own language, off /health, which answers at every share level. /issues carries
     every sentence in all three and no way to choose between them. */
  LOC = ((S.health || {}).locale) || 'en';
  ISS = S.issues.issues;
  ORDER = S.issues.order;
  DIST = S.issues.distances;
  LAB = S.issues.labels[LOC] || S.issues.labels.en;
  readView();
  if (STATE === 'empty') emptySnapshot();
  Object.assign(window.K, { S, ISS, ORDER, DIST, LAB, LOC, VIEW, STATE });
}

/* ================================================================= kit-h3.js — an address and a grid ==== */
/* The H3 parts, shared by D, E and F, and by nothing else.
 *
 * `kit.js` holds the four card kinds and knows nothing about grids. This holds what the three
 * H3-navigated directions need on top: an address, a cell drawn inside its parent, a grid with
 * things placed in it, and the three sentences H3 forces the page to be honest about. It adds no
 * fifth card kind — a grid is a drawing inside a card, the way the plan and the day already are.
 *
 * Every id, edge, area and path comes from `h3.js`, which `make-h3.mjs` computed with h3-js from
 * the committed fixture's own coordinates. Nothing here knows what a hexagon is; it places paths
 * somebody else projected, which is the same division the node's dashboard already keeps with
 * `kilometre-cells.json`.
 *
 * THREE THINGS H3 MAKES THE PAGE SAY, and all three are measured rather than asserted:
 *
 *   1. A cell is not the thing. The node's three indoor sensors carry ONE coordinate, so they are
 *      in one cell at every resolution down to 15. H3 cannot tell the room from the wall outside
 *      here; custody can, and does. A page that navigates by cell has to say where the grid stops
 *      answering.
 *   2. Containment is exact in the index and approximate on the ground. Two of the seven res-9
 *      children of this node's cell reach 6 m past their own parent's furthest vertex, and all
 *      seven index to it exactly. A page that moves by parent and child should show that, not
 *      quietly round it off.
 *   3. The four distances are not four resolutions, and two of them are the wrong way round. The
 *      cell that contains the ring is res 4, 26 km to an edge; the cell that contains "the region"
 *      is res 5, 9.9 km. The ring is the bigger of the two. That is not a drawing problem — it is
 *      the vocabulary disagreeing with the geometry, and it was invisible until the grid was drawn.
 */
/* Wrapped, because these are classic scripts sharing one script scope: `kit.js` declares `esc` at
 * top level and a second top-level `const esc` here is "Identifier 'esc' has already been declared"
 * — which, being a parse error, takes this whole file with it and leaves `window.KH` undefined. */
PAI_LOAD.push(function () {
'use strict';

const H = window.H3;
const { esc, fmt, pill, row, readout, cmpText, sign } = window.K;

/* ------------------------------------------------------------------ reading a cell out loud */
/* Both branches group their thousands. They did not: the m² branch used toLocaleString and the km²
   branch toFixed, so one card read "639,778 m²" and the next "10857 km²" — the same helper writing
   a number two ways on one screen. */
const km2 = (m2) => {
  if (m2 < 1e6) return `${Math.round(m2).toLocaleString()} m²`;
  const dp = m2 >= 1e7 ? 0 : 2;
  return `${(m2 / 1e6).toLocaleString(undefined,
    { minimumFractionDigits: dp, maximumFractionDigits: dp })} km²`;
};
const edge = m => m >= 1000 ? `${(m / 1000).toFixed(m >= 10000 ? 0 : 1)} km` : `${Math.round(m)} m`;

/* An H3 id is fifteen characters and a household will never read it as a word. It is still the one
 * thing that makes a reading citable by anybody else, so it is printed in full, in the mono, once
 * per object — never repeated, never truncated into something that looks like a different id. */
const address = (id, res) =>
  `<span class="addr mono"><span class="res">res ${res}</span> ${esc(id)}</span>`;

/* PORTED: frame() is gone with the drawing it was for. */
/* ------------------------------------------------------------------ a grid with things in it */
/* Cells, and what is read in them. A cell that holds nothing is drawn and left empty rather than
 * dropped: "no station is reading there" is the answer to half the questions this page exists for.
 *
 * State is weight, fill and dash — never hue. The settled vocabulary: this node's own cell carries
 * the heavier stroke, a cell somebody else reads in carries a fill, a cell nobody reads in carries
 * a hairline.
 */
function grid(draw, opts = {}) {
  const own = new Set(opts.own || []);
  const read = new Set(opts.read || []);
  const box = draw.box;
  const cells = draw.cells.map(c => {
    const isOwn = own.has(c.id), isRead = read.has(c.id);
    return `<path d="${c.d}" fill="var(--cells)"`
      + ` fill-opacity="${isOwn ? 0.18 : isRead ? 0.07 : 0}"`
      + ` stroke="var(--ink)" stroke-opacity="${isOwn ? 0.7 : isRead ? 0.4 : 0.18}"`
      + ` stroke-width="${isOwn ? 2.5 : isRead ? 1.5 : 1}"`
      + `${isOwn || isRead ? '' : ' stroke-dasharray="4 4"'}><title>${esc(c.id)}</title></path>`;
  }).join('');
  const pts = (draw.points || []).map(p =>
    `<circle cx="${p.x}" cy="${p.y}" r="${p.local ? 5.5 : 3.5}"`
    + ` fill="${p.local ? 'var(--cells)' : 'var(--ground)'}" stroke="var(--ink)"`
    + ` stroke-width="${p.local ? 2 : 1.4}"><title>${esc(p.name || p.sensor_id)} · `
    + `${p.km == null ? 'distance unknown' : `${esc(String(p.km))} km`}</title></circle>`).join('');
  return `<svg class="hexgrid" viewBox="0 0 ${box} ${box}" role="img"`
    + ` aria-label="${esc(opts.label || 'the grid around this node')}">`
    + `<g class="cells">${cells}</g><g class="pts">${pts}</g></svg>`;
}

/* PORTED: rung(), the four HONEST sentences and leaving() are gone. They read h3.js fields a build
 * step computed for the drawings — truncation, disk, rungs, leaves, ring_reach_km — which GET
 * /issues does not publish, and nothing on this page called them. Code that reads a field the node
 * never sends is a trap, not a spare part.
 */
/* Has this node been sited? /health publishes lat and lon as float(os.getenv("NODE_LAT", 0) or 0),
 * so absent and unset both arrive as exactly 0 — the test is "both falsy", and the only place it
 * misreads is within about 55 m of where the equator meets the prime meridian, which is open water.
 *
 * It lives here, on the kit every module already reads, because it was private to the ground module
 * and the other three surfaces that draw a distance did not have it: the stations printed each
 * neighbour's distance from the Gulf of Guinea as fact, the grain line counted stations in a cell in
 * that water, the wall drew nineteen cells of it, and the claims were centred on it. One predicate,
 * read by all four. */
const sited = () => !!(H.node.lat || H.node.lon);

window.KH = { H, address, grid, km2, edge, sited };

});

/* ================================================================= kit-nav.js — a position, and the moves out of it ==== */
/* Navigation, when navigation is the grid. Shared by G, H and I, and by nothing else.
 *
 * `kit.js` holds the four card kinds. `kit-h3.js` holds an address, a frame and a grid, which D, E
 * and F hang off a page that is still a document. This holds the part those three do not have: a
 * position, and the moves out of it.
 *
 * THE WHOLE VOCABULARY OF MOVEMENT, and there is no other:
 *
 *   out      cellToParent          one resolution coarser, seven cells become one
 *   in       cellToChildren        one resolution finer, this cell becomes seven
 *   across   gridDisk(cell, 1)     the six that share an edge with this one
 *   home     latLngToCell          back to the cell this node stands in, at this resolution
 *
 * There is no back button, no breadcrumb of its own and no zoom slider, because each of those is a
 * second way of saying one of the four. The address in the bar is the H3 index, and the query string
 * is `?cell=<index>` — so a reader who copies the URL has copied a place, and a reader who reads
 * the URL out loud has said something another node can resolve exactly. That is the argument for
 * navigating this way at all: the address is portable and the four distances are not.
 *
 * WHAT A NODE WOULD PUBLISH. Not this file's eleven plates: one. The plate the reader is standing
 * on is 3.0 kB of JSON — the cell, the two steps around it, each one's parent, neighbours, area and
 * contents — and every move asks for the next one. `app/ground.py` already computes all of it
 * (latlng_to_cell, grid_disk, cell_to_children); what it does not do is publish it per cell.
 *
 * WHAT IT CANNOT DO, said on the page and not only here:
 *   · the plate ends. Two steps out from what the node published, there is no next cell — not
 *     because the grid stops but because this node has not been asked for it. A page that drew a
 *     door there would be drawing the planet.
 *   · a cell is not custody. At the grain a street is drawn at, this house's cell holds two of
 *     somebody else's sensors, and no amount of resolution fixes that: "mine" is not a place.
 */
PAI_LOAD.push(function () {
'use strict';

const H = window.H3;
const { esc, fmt, pill } = window.K;
const { address, km2, edge } = window.KH;
const N = H.nav;

/* ------------------------------------------------------------------ where the reader is */
/* READ AT CALL TIME, NEVER CAPTURED AT LOAD.
 *
 * This was `const Q = new URLSearchParams(location.search)` at module scope, and where() read the
 * cell and the resolution out of it. That was correct for as long as every press reloaded the
 * document — the module ran again, and the capture was the new URL. The moment presses became
 * re-renders (v0.55) it became a snapshot of the query the page was FIRST opened with, so the dial
 * and every cell link changed the URL and nothing else: same resolution, same cell, same grain
 * line, same groups. Reported from node #1 the same day, and it is the whole of that fault.
 *
 * ctx.Q is rebuilt inside main() on every render, which is why the variable selector, the base
 * layer and "show all" all kept working and only the dial and the cells looked dead — a difference
 * that made the bug look like a map problem rather than a stale-read problem.
 *
 * The rule this leaves behind: nothing in this file may read location at module scope. FIXTURE is
 * the one exception and is marked where it is declared — it is answered once, at boot, and a
 * re-render cannot change which snapshot the node replayed.
 */
const query = () => new URLSearchParams(location.search);

/* A direction names the resolution it opens at; the reader's own position wins over it. An id in
 * the query that this node never published is not an error to hide — it is the honest answer "that
 * is not a place I was told about", and the page says so. */
function where(defaultRes) {
  const Q = query();
  const asked = Q.get('cell');
  const res = Math.max(N.res_min, Math.min(N.res_max, +(Q.get('res') || defaultRes || 8)));
  const id = asked || N.chain[res];
  return { id, known: !!N.cells[id], res: N.cells[id] ? N.cells[id].res : res, asked: !!asked };
}

/* Every link keeps the view and the state it was pressed in. A wall that navigated itself back to
 * the Now view on the first press would be a wall nobody can use. */
function link(id, extra = {}) {
  const q = new URLSearchParams(location.search);
  q.set('cell', id);
  for (const [k, v] of Object.entries(extra)) v == null ? q.delete(k) : q.set(k, v);
  return '?' + q.toString();
}

/* ------------------------------------------------------------------ reading the plate */
const cell = id => N.cells[id] || null;
const plate = res => N.plates[res];

/* The children of a cell are the cells one plate finer whose parent is this one. They are not
 * stored: storing seven ids per cell for eleven resolutions was 25 kB of a file that says the same
 * thing twice, and the plate below already carries every `parent`. */
function childrenOf(id) {
  const c = cell(id);
  if (!c || c.res >= N.res_max) return [];
  return plate(c.res + 1).cells.filter(k => (N.cells[k] || {}).parent === id);
}

const sensorsIn = id => ((cell(id) || {}).sensors || []).map(i => H.sensors[i]);

/* Everything read inside a cell, as flat rows: a station, what it measures, and its 15-minute mean.
 * Nothing is averaged across stations. Two stations in one cell are two rows, because the whole
 * reason to draw cells is that they are not one number — and a mean of two strangers' sensors is a
 * number nobody measured. */
function readingsIn(id) {
  const out = [];
  for (const s of sensorsIn(id)) {
    for (const [metric, r] of Object.entries(s.read || {})) {
      out.push({ sensor: s, metric, ...r });
    }
  }
  return out.sort((a, b) => (a.sensor.local === b.sensor.local ? 0 : a.sensor.local ? -1 : 1)
    || a.metric.localeCompare(b.metric));
}

/* ------------------------------------------------------------------ the address bar */
/* Out, in, across and home, and the address between them. A move the node did not publish is drawn
 * as a dead control with the reason on it rather than left off: "there is nothing finer here" and
 * "I was not told about that" are different sentences, and a household deserves the second one. */
function bar(id, opts = {}) {
  const c = cell(id);
  if (!c) {
    return `<div class="navbar" id="navbar" data-component="navbar" data-ref="plate">`
      + `<div class="here"><span class="unknown">This node was not told about that cell.</span>`
      + `<div class="sub">${address(id, '?')}</div></div>`
      + `<a class="mv home" href="${link(N.chain[opts.res || 8])}">back to this node’s own cell</a>`
      + `</div>`;
  }
  const kids = childrenOf(id);
  const up = c.parent;
  const home = N.chain[c.res];
  const sensors = sensorsIn(id).length;
  return `<div class="navbar" id="navbar" data-component="navbar" data-ref="plate">`
    + (up
      ? `<a class="mv out" href="${link(up)}" data-move="out"><span class="cap">out</span>`
        + `<span class="to">resolution ${c.res - 1} · ${esc(km2(N.cells[up].area_m2))}</span></a>`
      : `<span class="mv out off"><span class="cap">out</span><span class="to">${c.parent_outside
        ? 'not published: the plate ends here' : 'the coarsest this node publishes'}</span></span>`)
    + `<div class="here" id="here">`
    + `<div class="a">${address(id, c.res)}</div>`
    + `<div class="sub"><span data-num="cell.area" data-cmp="against ${esc(km2(H.ladder[c.res]
      .own_area_m2))}, this node’s own cell at this resolution">${esc(km2(c.area_m2))}</span>`
    + ` · ${esc(edge(c.edge_m))} to an edge`
    + (id === home ? ' · this node stands here' : '')
    + (c.pentagon ? ' · a pentagon: one of the twelve, and it has five neighbours' : '')
    + `</div></div>`
    + (kids.length
      ? `<a class="mv in" href="${link(kids.find(k => (cell(k).sensors || []).length)
        || kids[0])}" data-move="in"><span class="cap">in</span>`
        + `<span class="to">${kids.length} of ${c.children_total} children · resolution `
        + `${c.res + 1}</span></a>`
      : `<span class="mv in off"><span class="cap">in</span><span class="to">${c.res >= N.res_max
        ? `resolution ${N.res_max} is as fine as this node publishes`
        : 'not published: the plate ends here'}</span></span>`)
    + `<div class="across" role="group" aria-label="the cells around this one">`
    + `<span class="cap">across</span>`
    + (c.neighbours.length
      ? c.neighbours.map((n, i) => {
        const nc = cell(n), has = (nc.sensors || []).length;
        return `<a class="nb${has ? ' has' : ''}" href="${link(n)}" data-move="across"`
          + ` title="${esc(n)}">${i + 1}${has ? `<i>${has}</i>` : ''}</a>`;
      }).join('')
      : `<span class="none">the plate ends here</span>`)
    + (c.neighbours.length < c.neighbours_total
      ? `<span class="none">${c.neighbours_total - c.neighbours.length} of `
        + `${c.neighbours_total} not published</span>` : '')
    + `</div>`
    + (id === home ? '' : `<a class="mv home" href="${link(home)}">home</a>`)
    + `<span class="count">${sensors
      ? `${sensors} ${sensors === 1 ? 'station' : 'stations'} here` : 'nothing reads here'}</span>`
    + `</div>`;
}

/* ------------------------------------------------------------------ the plate, drawn */
/* One drawing, three weights: where you are, where you can go, and what the node published around
 * it. State is weight, fill and dash — never hue, which is the rule the layer settled and the only
 * one that survives a wall at three metres in the dark. */
function plateSvg(id, opts = {}) {
  const c = cell(id);
  const res = c ? c.res : (opts.res || 8);
  const d = plate(res).draw;
  const kids = c ? new Set(c.neighbours) : new Set();
  const paths = d.cells.map(x => {
    const me = x.id === id, nb = kids.has(x.id);
    const has = ((cell(x.id) || {}).sensors || []).length;
    return `<path d="${x.d}" fill="var(--cells)"`
      + ` fill-opacity="${me ? 0.2 : has ? 0.08 : 0}"`
      + ` stroke="var(--ink)" stroke-opacity="${me ? 0.85 : nb ? 0.45 : 0.18}"`
      + ` stroke-width="${me ? 3 : nb ? 1.5 : 1}"`
      + `${me || nb ? '' : ' stroke-dasharray="4 4"'}><title>${esc(x.id)}</title></path>`;
  }).join('');
  const pts = (d.points || []).map(p =>
    `<circle cx="${p.x}" cy="${p.y}" r="${p.local ? 5.5 : 3.5}"`
    + ` fill="${p.local ? 'var(--cells)' : 'var(--ground)'}" stroke="var(--ink)"`
    + ` stroke-width="${p.local ? 2 : 1.4}"><title>${esc(p.name || p.sensor_id)}</title></circle>`)
    .join('');
  return `<svg class="hexgrid" viewBox="0 0 ${d.box} ${d.box}" role="img"`
    + ` aria-label="${esc(opts.label || `resolution ${res}: the cell this page is standing in, the `
      + `${c ? c.neighbours.length : 0} published around it, and every station inside them`)}">`
    + `<g class="cells">${paths}</g><g class="pts">${pts}</g></svg>`;
}

/* ------------------------------------------------------------------ what the moves cost to say */
const NAV_HONEST = {
  plateEnds: () => `This node published ${N.steps} steps around itself at each of `
    + `${N.res_max - N.res_min + 1} resolutions — ${N.cell_count} cells, ${'3.0'} kB for the one `
    + `you are standing on. Past that edge the grid carries on and this node does not: a dashboard `
    + `that drew a door there would be drawing the planet.`,
  /* The floor, as a position rather than a paragraph. */
  floor: () => `Everything finer than resolution ${H.settings.PRESENCE_RES_FLOOR} is this machine’s `
    + `own. That is the floor no settings box may pass — app/main.py — and this node announces `
    + `itself at resolution ${H.settings.RETICULUM_PRESENCE_RES}, `
    + `${km2(H.radio.area_m2)}, which is the whole of what a stranger on the radio learns `
    + `about where it is.`,
  perStation: () => `Each number here is one station’s own 15-minute mean. GET /issues publishes `
    + `the ring as a single fenced median and never a value per station, so a page that navigates `
    + `by cell is asking the node to publish something it currently does not.`,
};

window.KN = { N, where, link, cell, plate, childrenOf, sensorsIn, readingsIn, bar, plateSvg,
  NAV_HONEST };

});

/* ================================================================= kit-map.js — the ground under the grid ==== */
/* The ground under the grid: the real place, with the cells laid on top of it.
 *
 * Tomas read direction H and said the hexagons feel abstract — keep a map under the scales, with
 * the cells over the place the node actually stands in. This draws that, and it is the same drawing
 * the node's own dashboard already makes: `planetai-design/data/place.geojson`, which is
 * **OpenStreetMap** (ODbL) as the `place` pack keeps it on disk, plus the buildings one satellite
 * pass found that OSM does not have.
 *
 * NO TILE SERVER, and that is not a shortcut. A slippy map means a node fetching tiles, and a
 * household node that fetches tiles tells somebody else's machine where it is every time anybody
 * opens the page. Everything drawn here was fetched once by a pack and is on the node's own disk.
 * For photographic ground there are four real Sentinel passes of this same place, also on disk —
 * they are the satellite section, not a backdrop.
 *
 * IT FOLLOWS NODE_DASHBOARD_PLAN_SPEC.md, WHICH IS ALREADY SETTLED. Seven rules, and the four that
 * bite here:
 *
 *   1  project every vertex, never resample, never simplify. `make-plan.mjs` did it in the node's
 *      own local formula; this places what it computed. geoPath was measured dropping corners from
 *      855 of 2,713 buildings on this exact dataset.
 *   2  draw back to front: ground, kilometre edge, green, roads, buildings, satellite-only
 *      buildings, uses, the cells, the node. The grid sits OVER the town, not under it — the index
 *      is a thing laid on a place and the drawing should say so.
 *   3  colour is a role and comes from a token: buildings `--ink` at .82, roads `--ink`, green
 *      `--rings`, satellite-only `--satellite-only`, cells and the node `--cells`. Orange means
 *      what only the satellite knows, and nothing else.
 *   5  two of node #1's buildings are points, not footprints. They are counted and not drawn: the
 *      caption says 2,904 and 2,902 are on the map.
 *
 * THE FRAME IS THE CELLS, not the map. The dial decides the resolution, the resolution decides the
 * cells, and the cells decide how much ground is in view — so turning the dial zooms the map, and a
 * reader never has to line up two pictures. Past 20 km across the plan stops being drawn as
 * buildings and becomes the rectangle it actually is, because 26,311 vertices inside a 26 km
 * hexagon is a smudge, and a smudge that took 400 kB to draw.
 */
PAI_LOAD.push(function () {
'use strict';

const H = window.H3;
/* PORTED: the plan arrives from GET /place/geojson after boot() and may never arrive at all — the
 * place pack need not be installed, and the route is refused to anything but this machine or a
 * token. So it is read when it is drawn, never captured at load, and its absence is one line. */
const P = () => window.PLAN;
/* WHY, not just THAT. The plan is the one read that needs a token at every sharing level, because
   GET /place/geojson carries the shape of every building here and this node's exact position. A
   reader on another machine sees an empty base and, until now, no reason for it. */
const NOPLAN = ref => `<p class="note" data-component="absent" id="plan-absent" data-ref="${ref}">`
  + `This node has no plan of its own ground. GET /place/geojson is on no share allowlist at any `
  + `level — it is the exact building footprints within PLACE_RADIUS_M of the address — so it `
  + `needs a token, or this page open on the machine the node runs on. The place pack fetches it `
  + `once and keeps it on that machine's disk.</p>`;
const { esc } = window.K;
const { km2, edge } = window.KH;

/* Past this the plan is a rectangle with a sentence on it rather than three thousand buildings. */
const MAX_SPAN_M = 20000;

const ROAD_W = { motorway: 2.2, trunk: 2.2, primary: 1.8, secondary: 1.6, tertiary: 1.3,
  residential: 1.0, unclassified: 1.0, living_street: .9, service: .6, footway: .5, path: .5 };
window.KMAP_ROAD_W = ROAD_W;   // the map ground draws its roads at these same weights

const d2 = v => Math.round(v * 100) / 100;

/* A flat [x,y,x,y,…] ring in metres to an SVG path. No rounding beyond two decimals, no smoothing,
 * no dropping of short segments: every vertex make-plan.mjs kept is drawn. */
function ring(flatXY) {
  let s = 'M';
  for (let i = 0; i < flatXY.length; i += 2) s += `${d2(flatXY[i])},${d2(flatXY[i + 1])}` + (i + 2 < flatXY.length ? 'L' : '');
  return s + 'Z';
}
function line(flatXY) {
  let s = 'M';
  for (let i = 0; i < flatXY.length; i += 2) s += `${d2(flatXY[i])},${d2(flatXY[i + 1])}` + (i + 2 < flatXY.length ? 'L' : '');
  return s;
}
/* Cull by frame, because at resolution 11 the view is 100 m across and 2,902 buildings are not. */
const hits = (flatXY, f, off = 0) => {
  for (let i = off; i < flatXY.length; i += 2) {
    if (flatXY[i] >= f.x0 && flatXY[i] <= f.x1 && flatXY[i + 1] >= f.y0 && flatXY[i + 1] <= f.y1) return true;
  }
  return false;
};

function frameOf(cellsM, pad = 0.06) {
  let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
  for (const c of cellsM) {
    for (let i = 1; i < c.length; i += 2) {
      x0 = Math.min(x0, c[i]); x1 = Math.max(x1, c[i]);
      y0 = Math.min(y0, c[i + 1]); y1 = Math.max(y1, c[i + 1]);
    }
  }
  const w = x1 - x0, h = y1 - y0, m = Math.max(w, h) * pad;
  return { x0: x0 - m, y0: y0 - m, x1: x1 + m, y1: y1 + m, w: w + 2 * m, h: h + 2 * m,
    span: Math.max(w, h) + 2 * m };
}

/* ------------------------------------------------------------------ the map */
/* opts.satOnly draws the satellite's own buildings and nothing else, for the satellite section.
 * opts.cells is the set of cell ids to draw heavy; everything else in the plate is a hairline. */
function map(res, opts = {}) {
  const plate = H.nav.plates[res];
  if (!plate) return '';
  if (!P()) return NOPLAN(opts.ref || 'rail');
  const f = frameOf(plate.cells_m);
  const u = f.span / 620;                        // metres per nominal pixel at the drawn size
  const heavy = new Set(opts.cells || [plate.centre]);
  const coarse = f.span > MAX_SPAN_M;
  const id = `map-${res}${opts.satOnly ? '-sat' : ''}`;

  const cells = plate.cells_m.map(c => {
    const on = heavy.has(c[0]);
    return `<path d="${ring(c.slice(1))}" fill="${on ? 'var(--cells)' : 'none'}"`
      + ` fill-opacity="${on ? 0.1 : 0}" stroke="${on ? 'var(--cells)' : 'var(--ink)'}"`
      + ` stroke-opacity="${on ? 1 : 0.3}" stroke-width="${d2((on ? 2 : 0.5) * u)}"`
      + `><title>${esc(c[0])}</title></path>`;
  }).join('');

  let ground = '';
  if (coarse) {
    /* Everything this node has drawn of its own ground, to scale, inside a cell that dwarfs it. */
    const [bx0, by0, bx1, by1] = P().bbox_m;
    ground = `<rect x="${bx0}" y="${by0}" width="${bx1 - bx0}" height="${by1 - by0}"`
      + ` fill="var(--ink)" fill-opacity="0.12" stroke="var(--ink)" stroke-opacity="0.5"`
      + ` stroke-width="${d2(u)}"/>`;
  } else if (opts.satOnly) {
    ground = `<g>` + P().sat.filter(sat => hits(sat, f, 1)).map(sat =>
      `<path d="${ring(sat.slice(1))}" fill="var(--satellite-only)"`
      + ` fill-opacity="${d2(0.2 + 0.3 * sat[0])}" stroke="var(--satellite-only)"`
      + ` stroke-width="${d2(0.7 * u)}"/>`).join('') + `</g>`
      /* The town underneath, as a hairline, so a reader can tell the satellite's buildings from
       * empty ground rather than from nothing at all. */
      + `<g fill="none" stroke="var(--ink)" stroke-opacity="0.22" stroke-width="${d2(0.6 * u)}">`
      + P().buildings.filter(b => hits(b, f)).map(b => `<path d="${ring(b)}"/>`).join('') + `</g>`;
  } else {
    ground =
      `<circle cx="0" cy="0" r="1000" fill="none" stroke="var(--ink)" stroke-opacity="0.35"`
      + ` stroke-width="${d2(u)}" stroke-dasharray="${d2(4 * u)} ${d2(4 * u)}"/>`
      + `<g fill="var(--rings)" fill-opacity="0.26">`
      + P().green.filter(g => hits(g, f)).map(g => `<path d="${ring(g)}"/>`).join('') + `</g>`
      + `<g fill="none" stroke="var(--ink)" stroke-opacity="0.65">`
      + P().roads.filter(r => hits(r, f, 1)).map(r =>
        `<path d="${line(r.slice(1))}" stroke-width="${d2((ROAD_W[r[0]] || .8) * u)}"/>`).join('')
      + `</g>`
      + `<g fill="var(--ink)" fill-opacity="0.82">`
      + P().buildings.filter(b => hits(b, f)).map(b => `<path d="${ring(b)}"/>`).join('') + `</g>`
      + `<g fill="var(--satellite-only)" fill-opacity="0.35" stroke="var(--satellite-only)"` // sat
      + ` stroke-width="${d2(0.7 * u)}">`
      + P().sat.filter(sat => hits(sat, f, 1)).map(sat => `<path d="${ring(sat.slice(1))}"/>`).join('')
      + `</g>`
      + `<g fill="var(--cells)">`
      + P().poi.filter(p => p[0] >= f.x0 && p[0] <= f.x1 && p[1] >= f.y0 && p[1] <= f.y1)
        .map(p => `<circle cx="${p[0]}" cy="${p[1]}" r="${d2(4.5 * u)}"/>`).join('')
      + `</g>`;
  }

  /* Every station with a coordinate that falls in view, so the map answers "who is reading here"
     with the same marks the abstract drawings use. */
  const MK = Math.cos(H.node.lat * Math.PI / 180) * 111320;
  const pts = H.sensors.map(s => ({ s,
    x: (s.lon - H.node.lon) * MK, y: -(s.lat - H.node.lat) * 111320 }))
    .filter(p => p.x >= f.x0 && p.x <= f.x1 && p.y >= f.y0 && p.y <= f.y1)
    .map(p => `<circle cx="${d2(p.x)}" cy="${d2(p.y)}" r="${d2((p.s.local ? 5.5 : 3.5) * u)}"`
      + ` fill="${p.s.local ? 'var(--cells)' : 'var(--ground)'}" stroke="var(--ink)"`
      + ` stroke-width="${d2((p.s.local ? 2 : 1.4) * u)}">`
      + `<title>${esc(p.s.name || p.s.sensor_id)}</title></circle>`).join('');

  return `<svg class="planmap" id="${id}" viewBox="${d2(f.x0)} ${d2(f.y0)} ${d2(f.w)} ${d2(f.h)}"`
    + ` role="img" aria-label="${esc(opts.label
      || `the ground around this node at resolution ${res}: ${coarse
        ? `a cell ${edge(H.ladder[res].edge_m)} to an edge, with everything this node has mapped of `
          + `its own ground drawn to scale inside it`
        : `${P().counts.buildings_drawn} buildings, ${P().counts.roads} roads and the cells laid over `
          + `them`}`)}">`
    + `<rect x="${d2(f.x0)}" y="${d2(f.y0)}" width="${d2(f.w)}" height="${d2(f.h)}"`
    + ` fill="var(--ground)"/>`
    + ground
    + `<g>${cells}</g>`
    + pts
    + `<circle cx="0" cy="0" r="${d2(7 * u)}" fill="var(--cells)"/>`
    + `</svg>`;
}

/* The caption under a map, which has to say what a reader cannot see: where the shapes came from,
 * how wide the view is, and — when the cell has outgrown the map — that the map has stopped. */
function caption(res) {
  if (!P()) return `resolution ${res} · no plan on this node`;
  const f = frameOf(H.nav.plates[res].cells_m);
  const coarse = f.span > MAX_SPAN_M;
  const across = f.span >= 10000 ? `${Math.round(f.span / 1000)} km` : f.span >= 1000
    ? `${(f.span / 1000).toFixed(1)} km` : `${Math.round(f.span)} m`;
  return `resolution ${res} · ${across} across · `
    + (coarse
      ? `wider than the ${(P().span_m[0] / 1000).toFixed(1)} km this node has mapped, so the map is `
        + `its outline`
      : `${P().counts.buildings_drawn} of ${P().counts.buildings} buildings · ${P().counts.roads} roads`)
    + ` · OpenStreetMap, kept on this node’s disk`;
}

window.KMAP = { map, caption, frameOf, MAX_SPAN_M };

});

/* ================================================================= kit-page.js — the page contract ==== */
/* The page contract: a lead, four stages of one loop, and the notes.
 *
 *     observe → decide → act → measure → observe …
 *
 * This is the PLANETAI logic laid out as the page's own spine. A node OBSERVES its place — sensors,
 * the ground, the satellite, the radio. It DECIDES what may be said about it, and at what grain. It
 * ACTS by asking somebody to do something. It MEASURES whether that worked and how long it took, and
 * the loop closes. Every section on the page belongs to one stage, and the page is read in the order
 * the loop runs.
 *
 * WHY THIS IS A CONTRACT AND NOT A LAYOUT. Tomas asked for a structure a node can extend and then
 * propose back — Meshtastic and Reticulum today, an open hardware manager and local making next,
 * wild packs after that. So the page does not know what its sections are. Packs register them:
 *
 *     window.PAI.register({
 *       id: 'ground',            // unique; becomes the band's DOM id
 *       pack: 'place',           // the pack that owns it; 'core' for the renderer's own
 *       stage: 'observe',        // observe · decide · act · measure
 *       title: 'The ground',     // the band's kicker, in the house voice
 *       order: 10,               // position within its stage; lower first
 *       needs: ['PLAN'],         // globals it reads. Absent → the band says so and does not fail
 *       reads: ['/place/geojson', '/issues'],
 *                                // the node's routes this band's data comes from, first the one it
 *                                //   leans on most. The shell prints them beside the kicker as
 *                                //   links, so a reader can fetch what the band drew. Only routes a
 *                                //   GET without parameters answers: an image the band asks for by
 *                                //   year is reached through the route that lists the years.
 *                                //   tools/check_ui.py fails a section without one, or a route
 *                                //   app/main.py does not define
 *       controls(ctx) → html,    // optional: a control strip for this section (a toggle, a selector)
 *       render(ctx)   → html,    // the body. Captions belong here; explanations do not
 *       wall(ctx)     → html,    // optional: what it contributes to the wall at ctx.RES
 *       learn: ['states'],       // optional: the learn marks this section carries. A key the
 *                                //   layer does not have draws nothing; see tools/build_learn.py
 *       notes(ctx)    → [{ id, label, text }],  // the explanations, gathered at the bottom of the
 *                                             // page. `label` names what THIS note is about and is
 *                                             // the row's term; without one the row falls back to
 *                                             // the section title, which every row would repeat.
 *     });
 *
 * and the shell renders whatever registered, stage by stage. A section from a pack a node does not
 * have simply is not there; a section whose data is missing prints one honest line instead of a
 * blank. Adding a feature is adding a file. Proposing it back is sending the file.
 *
 * WHAT A SECTION MAY NOT DO. Invent a fifth card kind (readout · stack · series · row are the four,
 * and a drawing is a drawing inside a card). Colour a state by hue. Print a numeral without
 * `data-num`/`data-cmp`. Leave a component with no `data-ref` in or out. Put its explanation in its
 * body — that goes in `notes()`, and the shell puts every note at the bottom where Tomas asked for
 * them. None of this is enforced here; all of it is measured by tests/visual/measure.mjs.
 *
 * In Phase 2 this same shape is a pack's `dashboard` contribution, declared in its pack.yaml and
 * served by the node as one more static file. Nothing here is a framework: it is an array, a sort,
 * and a join.
 */
PAI_LOAD.push(function () {
'use strict';

const STAGES = [
  ['observe', 'Observe', 'what is read, seen and heard about this place'],
  ['decide', 'Decide', 'what to do about it'],
  ['act', 'Act', 'what has been asked, of whom'],
  ['measure', 'Measure', 'whether it worked, and how long it took'],
];
const STAGE_INDEX = Object.fromEntries(STAGES.map(([k], i) => [k, i]));

const sections = [];
const problems = [];

function register(mod) {
  /* `render` OR `lead`. A section must draw something, but the lead is drawn by the shell from every
     registered section that has one (see the fig/lead assembly), independently of which view is on —
     so a section whose whole contribution is the lead is a real thing, not a mistake. The ground is
     exactly that: a surface with a tab bar and no card, once its request ledger became its own
     section. Requiring `render` refused it and the map vanished with the ledger. */
  const missing = ['id', 'pack', 'stage', 'title'].filter(k => !mod[k]);
  if (!mod.render && !mod.lead) missing.push('render or lead');
  if (missing.length || !(mod.stage in STAGE_INDEX)) {
    problems.push(`${mod.id || '?'}: ${missing.length ? `missing ${missing.join(', ')}`
      : `unknown stage ${mod.stage}`}`);
    return;
  }
  if (sections.some(s => s.id === mod.id)) { problems.push(`${mod.id}: registered twice`); return; }
  /* `level` is the one field simple mode reads. Default `advanced`, so a section written before
     this existed, or by a pack that has never heard of it, keeps the behaviour it had: drawn on the
     full page, absent from the short answer. A section opts INTO simple; it is never opted in for
     it, because what belongs in a four-sentence answer is a judgement its author has to make. */
  sections.push({ order: 50, needs: [], level: 'advanced', learn: [], reads: [], ...mod });
}

/* SECTIONS A PACK DECLARES AS DATA. A wild pack ships no script (docs/decisions/2026-10-01-packs.md, point 5):
 * a page script reads the same storage the admin token is kept in, so a stranger's script on this page would hold
 * admin rights on every node that ran it. It declares its section in its pack.yaml instead, and the node serves it
 * in /issues as `sections`, with the node's own numbers already in it. This turns each one into a section of the
 * same shape as every other, drawn with the page's own readout card: the node computes, the page draws, and the
 * visual gate measures a declared section with the rest. Rebuilt on every render from what the node last said, into
 * the same two arrays, so a refresh never draws a section twice and a section the node stops serving goes. */
const fromNode = [];
const fromNodeProblems = [];

function declared(ctx) {
  const K = window.K || {}, L = (ctx && ctx.LOC) || K.LOC || 'en';
  const list = ((((ctx && ctx.S) || K.S || {}).issues || {}).sections) || [];
  fromNode.length = 0; fromNodeProblems.length = 0;
  const said = o => (o && (o[L] || o.en)) || '';
  for (const x of list) {
    if (!x || !x.id || !(x.stage in STAGE_INDEX)) { fromNodeProblems.push(`${(x && x.id) || '?'}: not a section the page can draw`); continue; }
    if (sections.some(s => s.id === x.id) || fromNode.some(s => s.id === x.id)) {
      fromNodeProblems.push(`${x.id}: the ${x.pack} pack declares an id the page already has`); continue;
    }
    const title = said(x.title) || x.id, rows = x.readouts || [], want = x.expected || rows.length;
    const missing = want - rows.length;
    const card = (r, i) => K.readout({
      id: `${x.id}-r${i}`, num: `${x.id}.${r.sensor_id || 'x'}.${r.metric}`, component: 'declaredReadout',
      ref: x.id, pack: x.pack, title: said(r.label) || r.metric, value: r.value, unit: r.unit, dp: r.dp,
      source: r.source, prov: r.provenance, age: r.age_minutes,
      cmp: K.cmpText({ mode: 'none', reason: `the ${x.pack} pack shows it beside nothing of this node’s` }),
    });
    fromNode.push({
      id: x.id, pack: x.pack, stage: x.stage, title, order: Number.isInteger(x.order) ? x.order : 50,
      needs: [], level: 'advanced', learn: ['cards', 'prov'], reads: ['/issues'], declared: true,
      render() {
        return `<div class="declared" data-component="declared" data-ref="${K.esc(x.id)}">${rows.map(card).join('')}`
          + (missing > 0 ? `<p class="note" id="${K.esc(x.id)}-waiting" data-component="declaredWaiting" data-ref="${K.esc(x.id)}">`
            + (rows.length
              ? `${missing} of the ${want} readings the ${K.esc(x.pack)} pack declares ${missing === 1 ? 'has' : 'have'} not arrived on this node yet.`
              : `None of the ${want} readings the ${K.esc(x.pack)} pack declares has arrived on this node yet.`) + `</p>` : '')
          + `</div>`;
      },
      wall: x.wall ? () => rows.map((r, i) => `<div class="col" id="wall-${K.esc(x.id)}-${i}" data-component="declaredCol"`
        + ` data-ref="wall-field"><h3>${K.esc(said(r.label) || r.metric)}</h3><div class="line">`
        + `<span class="num" data-num="${K.esc(`${x.id}.${r.sensor_id || 'x'}.${r.metric}`)}"`
        + ` data-cmp="${K.esc(`the ${x.pack} pack's figure, beside nothing of this node's`)}">${K.esc(K.fmt(r.value, r.dp))}</span>`
        + `<small>${K.esc(r.unit || '')} · ${K.esc(r.source || x.pack)}</small></div></div>`).join('') : null,
      notes() {
        return [{ id: `${x.id}-note`, label: title,
          text: (said(x.note) ? `${said(x.note)} ` : '') + `Declared by the ${x.pack} pack in its pack.yaml: the node `
            + `reads these numbers and the page draws them with its own cards; the pack ships no code for this page.` }];
      },
    });
  }
  return fromNode;
}

/* A global path like 'H3.nav.plates' resolves or does not. */
const has = path => path.split('.').reduce((o, k) => (o == null ? o : o[k]), window) != null;

function bandFor(ctx, s) {
  const { esc } = window.K;
  const absent = (s.needs || []).filter(n => !has(n));
  let body, controls = '';
  if (absent.length) {
    body = `<p class="note" data-component="absent" id="${esc(s.id)}-absent" data-ref="${esc(s.id)}">`
      + `The ${esc(s.pack)} pack has nothing here yet: ${esc(absent.join(', '))} `
      + `${absent.length === 1 ? 'is' : 'are'} not on this node.</p>`;
  } else {
    /* The control strip is inside the same try as the body. The contract promises a pack author
       that one section cannot take the page down, and controls() is a section's code like any
       other: thrown from here it escaped render() and route(), #page was never assigned, and the
       whole Now view was blank paper. It is the last hook that was outside a guard. */
    try {
      controls = s.controls ? (s.controls(ctx) || '') : '';
      body = s.render ? (s.render(ctx) || '') : '';
    }
    catch (e) {
      /* And the strip goes with it: a control pointing at a body that did not render is a link to
         an id that is not on the page, which is the thing T5 counts. */
      controls = '';
      body = `<p class="note" data-component="failed" id="${esc(s.id)}-failed" data-ref="${esc(s.id)}">`
        + `${esc(s.pack)} · ${esc(s.id)} did not render: ${esc(e.message)}. A failure is not an `
        + `answer, so the rest of the page is still here.</p>`;
    }
  }
  /* A lead-only section draws no band. Without this the ground contributed a heading with nothing
     under it — a title for a card that is not there, which reads as a section that failed. Its
     notes still appear: they explain the drawing the shell put at the top. */
  if (!body && !controls) return '';
  /* The marks a section declares, drawn at the band's top right. A section that declares none
     carries none; simple mode draws no bands at all, so there is nothing here to suppress. */
  const marks = (s.learn || []).map(k => (window.PAI_LEARN ? window.PAI_LEARN.mark(k, s.id) : ''))
    .join('');
  /* The routes the band's data came from, once per band, in their own case: the kicker shouts, and
     a route uppercased is a route a reader cannot type back. Links, so the JSON is one press away. */
  /* A route is a page the node answers, and pressing one used to replace the dashboard with raw JSON in
     the same tab, with no way back but the browser's. It opens beside the dashboard instead. Two cannot
     be opened by a page at all: /actions takes a POST, and /place/geojson is the exact footprint around
     the house, which the node never serves to a page without a token, so those say so rather than 403. */
  const routeLink = r => /^\/actions\b/.test(r)
    ? `<span class="route off" title="This route takes a POST, so there is no page to open">POST ${esc(r)}</span>`
    : /^\/place\/geojson\b/.test(r)
      ? `<span class="route off" title="Needs a token: it is the exact footprint around this house, and the node never serves it to a page without one">GET ${esc(r)} · token</span>`
      : `<a href="${esc(r)}" target="_blank" rel="noopener">GET ${esc(r)}</a>`;
  const reads = (s.reads || []).length
    ? `<span class="routes">${s.reads.map(routeLink).join('')}</span>`
    : '';
  return `<section class="band" id="${esc(s.id)}" data-band="${esc(s.stage)}:${esc(s.id)}"`
    + ` data-pack="${esc(s.pack)}" data-stage="${esc(s.stage)}">`
    + `<div class="k"><span>${esc(s.title)}</span>${reads}${marks}<span class="pack">${esc(s.pack)}</span></div>`
    + controls + body + `</section>`;
}

/* The page: the lead the shell passes in, then the four stages in loop order, then the notes. */
/* THE DIGEST: one sentence per stage, and the node writes every one of them.
 *
 * Simple mode is not a smaller page. It is a shorter answer, and an answer is a sentence. This page
 * does not compose it and must not: a sentence about what was observed is a claim about the data,
 * and the one rule the renderer has is that the node computes and the page draws. So `/issues`
 * carries `digest` — four stages, each a string per locale — and this draws them in stage order.
 *
 * A node that has not been updated yet sends none. Then this says so, names the version it is
 * talking to and points at the page that does exist, rather than printing a blank or, worse, four
 * sentences the browser made up. */
function digest(ctx) {
  const { esc } = window.K;
  const d = (ctx.S.issues || {}).digest;
  const line = key => {
    const s = d && d[key];
    if (!s) return '';
    return typeof s === 'string' ? s : (s[ctx.LOC] || s.en || '');
  };
  const got = STAGES.filter(([k]) => line(k));
  if (!got.length) {
    return `<div class="band" id="digest" data-component="digest" data-ref="header">`
      + `<p class="note" data-component="digestAbsent" id="digest-absent" data-ref="digest">`
      + `This node has not sent a digest. The four sentences are written by the node, not by this `
      + `page, and the node answering here (${esc((ctx.S.health || {}).version || 'unknown version')}) `
      + `does not write them yet. Switch to Advanced above to read the page it does have.</p></div>`;
  }
  return `<div class="band" id="digest" data-component="digest" data-ref="header">`
    + `<div class="digest" data-kind="stack" data-component="digestGrid" data-ref="digest">`
    + got.map(([k, name]) =>
      `<div class="d" data-ref="digestGrid"><span class="n">${STAGE_INDEX[k] + 1}</span>`
      + `<b>${esc(name)}</b><p class="said">${esc(line(k))}</p></div>`).join('')
    + `</div></div>`;
}

/* SIMPLE, UNDER THE LEAD: the node's own paragraph, then the other watched issues as buttons.
 *
 * The paragraph is `digest.simple`, three sentences the node writes; this page composes none of it.
 * The also line is the switcher: pressing an issue draws its hero in the lead, stamped so that nobody
 * mistakes a reader's choice for the node's. It is page state and nothing else, cleared on reload,
 * and a poll that lands in the meantime draws the same choice again. */
function simpleTail(ctx) {
  const { esc, fmt } = window.K;
  const dg = (ctx.S.issues || {}).digest || {};
  const said = dg.simple ? (dg.simple[ctx.LOC] || dg.simple.en || '') : '';
  const para = said
    ? `<p class="digestline" id="digest" data-component="digestSimple" data-ref="header">${esc(said)}</p>`
    : `<p class="note" data-component="digestAbsent" id="digest-absent" data-ref="header">This node has `
      + `not sent its short answer. It is written by the node, not by this page, and the node answering `
      + `here (${esc((ctx.S.health || {}).version || 'unknown version')}) does not write it yet.</p>`;
  const shown = window.PAI_HERO_SHOWN;
  const others = ctx.ORDER.filter(k => k !== shown && ctx.ISS[k] && ctx.ISS[k].watched !== false
    && ctx.ISS[k].hero);
  if (!others.length) return para;
  return para + `<div class="also" id="also" data-component="alsoLine" data-ref="header">`
    + `<span class="lbl">also watched here</span>`
    + others.map(k => {
      const d = ctx.ISS[k], h = d.hero, name = d.name[ctx.LOC];
      return `<button type="button" data-hero="${esc(k)}" aria-label="${esc(`show ${name}`)}">`
        + `<svg class="sgn" viewBox="0 0 24 24" aria-hidden="true"><use href="static/signs.svg#${esc(h.sign)}"/></svg>`
        + (h.value != null
          ? `<b data-num="${esc(k)}.hero" data-cmp="${esc(`${name}, ${(h.stamp || {})[ctx.LOC] || 'the node’s reading'}`)}">`
            + `${esc(fmt(h.value, h.dp))}</b> ${esc(h.unit)}`
          : `${esc(name)} \u00b7 nothing read`)
        + `</button>`;
    }).join('') + `</div>`;
}

function render(ctx, lead, opts = {}) {
  const { esc } = window.K;
  /* THE DIGEST IS NOW'S, AND ONLY NOW'S.
   *
   * It is four sentences about this hour — observe, decide, act, measure — written by the node. It
   * was being drawn on EVERY view in simple mode, so Historical and Network each answered "what is
   * the air doing right now" under a heading about the years and about the network, with no sections
   * under it because none of theirs opt into simple. 652 characters and not one of them about the
   * view the reader had asked for. A short answer to the wrong question is worse than a long one to
   * the right question. */
  const onNow = !opts.only || opts.only.includes('matrix');
  /* `only` is the whole of the Now/Network split: one registry, two views, and the notes band at
     the foot then lists the sections on the view a reader is actually on. */
  const keep = opts.only ? new Set(opts.only) : null;
  const simple = (window.PAI_MODE ? window.PAI_MODE() : 'advanced') === 'simple';
  /* The order the stages are DRAWN in. The loop runs observe, decide, act, measure and the mark in each
     head still says so; Now and Arrange put Decide first, because what asks for a person is read first. */
  const drawn = opts.stages || STAGES.map(s => s[0]);
  const at = st => drawn.indexOf(st) < 0 ? drawn.length : drawn.indexOf(st);
  const ordered = sections.concat(declared(ctx)).filter(s => (!keep || keep.has(s.id))
    && (!simple || s.level === 'simple')).slice().sort((a, b) =>
    at(a.stage) - at(b.stage) || a.order - b.order || a.id.localeCompare(b.id));
  /* Simple on Now is the three questions and nothing else: no sections, no stage names, no notes. */
  if (simple && onNow) return (lead || '') + simpleTail(ctx);
  let html = (lead || '') + (simple && onNow ? digest(ctx) : '');
  const present = new Set(ordered.map(s => s.stage));
  for (const [key, name, what] of drawn.map(k => STAGES[STAGE_INDEX[k]]).filter(Boolean)) {
    const mine = ordered.filter(s => s.stage === key);
    if (!mine.length) continue;
    html += `<div class="stage" id="stage-${key}" data-stage="${key}">`
      + `<div class="stagehead">`
      + `<h2>${esc(name)}</h2><span class="what">${esc(what)}</span>`
      /* THE FOUR SQUARES ARE THE LOOP'S MAP AND ITS NAVIGATION. A square for a stage this view draws is a
         link to that stage; one for a stage it does not (Simple hides most, and Historical and Network
         have only some) is greyed and says so, so the row never points at nothing. */
      + `<span class="loop" role="navigation" aria-label="The four stages">${STAGES.map(([k, nm]) => present.has(k)
        ? `<a class="sq${k === key ? ' on' : ''}" href="#stage-${k}" data-stage-go="${k}" title="${esc(nm)}"`
          + ` aria-label="${esc(nm)}"${k === key ? ' aria-current="true"' : ''}><i class="${k === key ? 'on' : ''}"></i></a>`
        : `<span class="sq off" title="${esc(nm)}: not on this view" role="img"`
          + ` aria-label="${esc(nm)}, not on this view"><i class="off"></i></span>`).join('')}</span>`
      /* One mark for the loop, on the first stage a view draws. The same mark on all four would be
         the same quote four times, which is a page repeating itself rather than explaining itself. */
      + (key === ordered[0].stage && window.PAI_LEARN
        ? window.PAI_LEARN.mark('stages', `stage-${key}`) : '') + `</div>`
      + mine.map(s => bandFor(ctx, s)).join('') + `</div>`;
  }
  /* SIMPLE ON HISTORICAL OR NETWORK HIDES ALMOST EVERYTHING, AND USED TO SAY NOTHING ABOUT IT. Only one
     section per view opts into simple, so a browser left on Simple (the choice is remembered) showed one
     panel under "Observe" and no sign that six more existed. Say how many are held back and offer the
     switch; the button sits in a `.seg.mode` group so the header's own mode handler takes the press. */
  if (simple && !onNow && keep) {
    const hidden = sections.filter(s => keep.has(s.id) && s.level !== 'simple').length;
    if (hidden) html += `<div class="modehint" data-component="modeHint" data-ref="stage-observe">`
      + `<p>Simple mode shows ${ordered.length} of ${ordered.length + hidden} sections on this view. `
      + `${hidden} more ${hidden === 1 ? 'is' : 'are'} hidden.</p>`
      + `<div class="seg mode" role="group" aria-label="Show more of this page">`
      + `<button type="button" data-mode="advanced">Show all sections</button></div></div>`;
  }
  html += notesBand(ctx, ordered);
  const allProblems = problems.concat(fromNodeProblems);
  if (allProblems.length) {
    html += `<p class="note" id="pai-problems">Registration problems: ${esc(allProblems.join('; '))}</p>`;
  }
  return html;
}

/* Every explanation on the page, in one place at the bottom, each pointing back at the section it
 * explains. The sections keep their captions and lose their paragraphs; a household that wants to
 * know why is one scroll from the answer and a household that does not is never interrupted. */
function notesBand(ctx, ordered) {
  const { esc } = window.K;
  const groups = [];
  for (const s of ordered) {
    if (!s.notes) continue;
    let ns = [];
    try { ns = s.notes(ctx) || []; } catch { ns = []; }
    ns = ns.filter(n => n && n.text);
    if (ns.length) groups.push({ section: s, notes: ns.map((n, i) => ({ ...n, id: n.id || `${s.id}-note-${i}` })) });
  }
  if (!groups.length) return '';
  /* One fold per section: its title, its pack and how many notes it holds, so a reader can tell
   * which fold holds what without opening all of them. Measured with every note open, the notes
   * were a third of the page — about 3,000 px of prose under a page meant to be read in a minute.
   * Folded they are one line each, still at the bottom, still one press from the answer. */
  const n = groups.reduce((a, g) => a + g.notes.length, 0);
  return `<section class="band notes" id="notes" data-band="notes"><div class="k">`
    + `<span>Where these numbers come from</span>`
    + `<span class="pack">${n} ${n === 1 ? 'note' : 'notes'}</span></div>`
    + `<p class="sub" id="notes-lead" data-component="notesLead" data-ref="notes">`
    + `Everything above, explained: one fold for each part of the page, in the order you just read `
    + `them. Open one to see what that part measured, where the figure came from, and what it does `
    + `not say. Nothing here is needed to read the page — it is here for when you want to check `
    + `it.</p>`
    /* `anchor` is where a fold points when the section's own id is not on the page. A lead-only
       section draws no band, so its notes linked to an id that does not exist and the fold was a
       component with no link out — which the gate counts. The ground points at its own drawing. */
    + groups.map(g => { const at = g.section.anchor || g.section.id; return `<details`
      + ` class="fold notefold" id="notes-${esc(g.section.id)}"`
      + ` data-component="notes" data-ref="${esc(at)}">`
      + `<summary><span class="t">${esc(g.section.title)}</span>`
      + `<span class="pack">${esc(g.section.pack)}</span>`
      + `<span class="n">${g.notes.length}</span></summary>`
      /* EVERY NOTE NAMES ITS OWN SUBJECT. The term used to be the section's title, printed once per
         note — so a fold of five notes was five rows reading "What the satellite says", "What the
         satellite says", "What the satellite says", beside five paragraphs about five different
         things. A term that is the same for every row in a list is not a term: it is the fold's
         heading said again, and it told a reader scanning for the note about compaction nothing
         about which row to stop at. `label` is the note's own, a few words for the thing it
         explains; the section title is the fallback for a note that has not been given one, which
         is at worst what every note said before. */
      + `<dl class="notelist">` + g.notes.map(n =>
        `<div class="noteitem" id="${esc(n.id)}"><dt><a href="#${esc(at)}">`
        + `${esc(n.label || g.section.title)}</a></dt><dd>${n.html ? n.text : esc(n.text)}</dd>`
        + `</div>`).join('')
      + `</dl></details>`; }).join('')
    + `</section>`;
}

/* The wall: whatever the registered sections say they can show at three metres, in loop order. */
function wall(ctx) {
  const ordered = sections.concat(declared(ctx)).sort((a, b) =>
    STAGE_INDEX[a.stage] - STAGE_INDEX[b.stage] || a.order - b.order);
  return ordered.filter(s => s.wall && (s.needs || []).every(has))
    .map(s => { try { return s.wall(ctx) || ''; } catch { return ''; } }).join('');
}

window.PAI = { STAGES, register, render, wall, sections, problems, has };
/* The kit's contract above, verbatim (tests/test_dashboard.py holds it), and one addition beside it rather than
   inside it: the sections the node serves from the packs' declarations, which the router places on Now. */
window.PAI.declared = declared;

});

/* ================================================================= h/mods/ground.js ==== */
/* The ground: the real place under the cells, from a tile server or from this node's own disk.
 *
 * Tomas looked at the offline plan and asked for the thing it deliberately is not — "actually
 * embedding live open street map with satellite view, which should change scales when we change it
 * in the interface automatically." He was told what that costs: a page that fetches tiles tells the
 * tile server which square of the planet is being looked at, every time anybody opens it. He said
 * build it. So this builds it, prints the cost beside the picture, and keeps the offline plan one
 * press away.
 *
 * THREE BASES, one control strip:
 *   sat    Sentinel-2 cloudless, EOX. A 2020 mosaic, not today's sky. Serves to zoom 18.
 *   osm    OpenStreetMap's own raster tiles. Serves to zoom 19. Their usage policy applies.
 *   plan   kit-map.js: OpenStreetMap kept on this node's disk. No request leaves the machine.
 *
 * THE FRAME IS STILL THE CELLS. The dial sets the resolution, the resolution sets the 19 cells of
 * the plate, and the zoom is the largest of 0..19 at which their bounding box fits in the square —
 * so turning the dial zooms the map and a reader never lines up two pictures. Integer zooms only:
 * a fractional zoom means resampling tiles, and a tile drawn at 1.3× is a blur with an argument.
 *
 * TILES ARE WEB MERCATOR. The offline plan is drawn in the node's own local frame — metres east and
 * north of the node, make-plan.mjs — and this is drawn in EPSG:3857 because that is the only frame a
 * tile server speaks. At 8.8° south Mercator's scale is within 1.2% of true and constant to a part
 * in a thousand across a 5 km frame, so the cells land on the same pixels either way; at resolution
 * 2 and 3 the frame is hundreds of kilometres and the difference is visible, and there the plan is
 * already a rectangle. Boundaries are drawn vertex to vertex, straight, the way kit-h3.js does.
 *
 * Nothing here fetches. Tiles are `<img>` elements the browser asks for on its own, with the
 * browser's default referrer, which OpenStreetMap requires — measured: the same tile with no
 * Referer is a 403 "Access blocked" placeholder, with one it is the map. Do not set
 * referrerpolicy="no-referrer" on these.
 */
PAI_LOAD.push(function () {
'use strict';

const H = window.H3;
const { esc, row } = window.K;
const { edge } = window.KH;

const TILE = 256;
const SIZE = 600;                   // logical px of the lead's square; the wall passes its own
const FILL = 0.9;                   // the cells may take this much of the square
const EQUATOR_M = 40075016.686;     // Web Mercator's circumference, metres

/* THE OFFLINE PLAN LEADS. It was third of three, after the two that leave the house — so the first
 * thing offered was the one with a cost, and the one that costs nothing was the afterthought. The
 * node's own map is the default from resolution 9 in and it is the only base that sends no request
 * anywhere; it goes first, and the other two say what they would cost before they are pressed. */
const BASES = {
  plan: { name: 'plan, offline', host: null, credit: 'OpenStreetMap, kept on this node\u2019s disk' },
  sat: { name: 'satellite', host: 'tiles.maps.eox.at', maxZ: 18,
    url: (z, x, y) => `https://tiles.maps.eox.at/wmts/1.0.0/s2cloudless-2020_3857/default/g/${z}/${y}/${x}.jpg`,
    credit: 'Sentinel-2 cloudless by EOX IT Services GmbH (Contains modified Copernicus Sentinel data 2020)' },
  osm: { name: 'street map', host: 'tile.openstreetmap.org', maxZ: 19,
    url: (z, x, y) => `https://tile.openstreetmap.org/${z}/${x}/${y}.png`,
    credit: '© OpenStreetMap contributors' },
  /* THE NODE'S OWN MAPS, fetched once by `planetai run place basemap` and `planetai run earth-engine basemap`
     and served by this node at /ground/* (token or this machine, like the plan). They send nothing, so they are
     offered at every resolution — but only on the map ground (UI_GROUND=map), which can send the token with each
     tile; an <img> on the svg ground cannot. `own` names the /ground/meta key that says the node holds it. */
  street: { name: 'street map, on this node', host: null, own: 'vector', credit: '© OpenStreetMap contributors · Protomaps' },
  imagery: { name: 'satellite, on this node', host: null, own: 'imagery', minZ: 8, maxZ: 15, credit: 'Sentinel-2, Copernicus' },
  drone: { name: 'drone, on this node', host: null, own: 'drone', minZ: 14, maxZ: 18, credit: 'OpenAerialMap, CC BY 4.0' },
};
const isOwn = k => !!(BASES[k] || {}).own;
/* Offered only where it can be drawn and the node says it holds it. */
const ownAllowed = k => isOwn(k) && (window.SETTINGS || {}).UI_GROUND === 'map'
  && !(window.PAI_MODE && window.PAI_MODE() === 'simple')
  && !!(((window.GROUND_META || {}).on_disk || {})[BASES[k].own]);
/* Which base when nobody has pressed one. Tomas's rule: from resolution 9 inward, the plan. The
 * node's own map is about 3 km across; the res-9 plate is 1.6 km, so from 9 the plan fills the
 * frame edge to edge — the generated drawing is the better picture there and it sends nothing. At 8
 * the plate is 4.2 km and the plan covers the middle with paper round it, which Tomas looked at and
 * preferred the tiles for; coarser still the plan is a rectangle and the tiles take over. A pressed
 * base always wins over the rule. */
/* PORTED, and this is the node owner's own rule. Live tiles are OFF unless a keeper turns them on:
 * MAP_TILES is public, defaults to `off`, and only with it on does a tile ever appear — and then
 * only at resolution 8 and coarser, because from 9 inward the node's own plan fills the frame and
 * sends nothing. A pressed base still wins for that page view. */
const PLAN_FROM = 9;
/* ONE predicate, read in both places, so the strip can never offer what baseOf would refuse. */
const tilesAllowed = (res, settings) =>
  (settings || {}).MAP_TILES === 'on' && res < PLAN_FROM;
/* The node's own maps lead when it holds them: its own satellite picture where 10 m reads (coarser than resolution 9),
   its own street map from 9 inward, where 10 m blurs. Both send nothing. Then the old rule. */
const autoBase = (res, settings) => {
  if (res < PLAN_FROM && ownAllowed('imagery')) return 'imagery';
  if (ownAllowed('street')) return 'street';
  return tilesAllowed(res, settings) ? 'sat' : 'plan';
};
/* A PRESS MAY ONLY EVER REDUCE WHAT LEAVES THE HOUSE. The prototype's comment said the opposite —
 * "a pressed base always wins over the rule" — and it was written for a drawing, before MAP_TILES
 * existed. On a node it is not a preference: a link in a page cannot be allowed to override the
 * keeper's setting, because following it sends this household's own kilometre to somebody else's
 * machine. So `plan` is always pressable and the two live bases are honoured only where they are
 * also offered. */
const baseOf = (q, res) =>
  (q in BASES && (q === 'plan' || ownAllowed(q) || (!isOwn(q) && tilesAllowed(res, window.SETTINGS))))
    ? q : autoBase(res, window.SETTINGS);

/* ------------------------------------------------------------------ Web Mercator, in pixels */
/* World pixel coordinates at zoom z: the whole planet is 256·2^z px across. */
const px = z => TILE * Math.pow(2, z);
const lngX = (lng, z) => (lng + 180) / 360 * px(z);
const latY = (lat, z) => {
  const r = lat * Math.PI / 180;
  return (1 - Math.log(Math.tan(r) + 1 / Math.cos(r)) / Math.PI) / 2 * px(z);
};
/* Ground metres per pixel at this latitude and zoom — the caption's "across" comes from this. */
const mPerPx = (lat, z) => EQUATOR_M * Math.cos(lat * Math.PI / 180) / px(z);

/* Everything the mosaic and its caption need, computed once. `size` is the square's logical
 * width; the zoom is the largest at which the plate's bounding box fits FILL of it, capped by what
 * the base serves. */
function frame(res, size = SIZE, base = 'sat') {
  const plate = H.nav.plates[res];
  const B = BASES[base];
  let lat0 = 90, lat1 = -90, lng0 = 180, lng1 = -180;
  for (const c of plate.cells_ll) {
    for (let i = 1; i < c.length; i += 2) {
      lat0 = Math.min(lat0, c[i]); lat1 = Math.max(lat1, c[i]);
      lng0 = Math.min(lng0, c[i + 1]); lng1 = Math.max(lng1, c[i + 1]);
    }
  }
  const maxZ = B.maxZ == null ? 19 : B.maxZ;
  let z = 0;
  for (let t = 0; t <= maxZ; t++) {
    const w = lngX(lng1, t) - lngX(lng0, t), h = latY(lat0, t) - latY(lat1, t);
    if (Math.max(w, h) <= size * FILL) z = t; else break;
  }
  const ox = lngX(H.node.lon, z) - size / 2, oy = latY(H.node.lat, z) - size / 2;
  /* Only the tiles the square touches. y is clamped to the planet; x wraps round it. */
  const n = Math.pow(2, z);
  const tiles = [];
  for (let ty = Math.floor(oy / TILE); ty * TILE < oy + size; ty++) {
    if (ty < 0 || ty >= n) continue;
    for (let tx = Math.floor(ox / TILE); tx * TILE < ox + size; tx++) {
      tiles.push({ x: ((tx % n) + n) % n, y: ty, left: tx * TILE - ox, top: ty * TILE - oy });
    }
  }
  const m = mPerPx(H.node.lat, z);
  return { res, size, base, z, ox, oy, tiles, plate,
    across_m: size * m, tile_m: TILE * m,
    X: lng => lngX(lng, z) - ox, Y: lat => latY(lat, z) - oy };
}

/* ------------------------------------------------------------------ the drawing */
const d1 = v => Math.round(v * 10) / 10;

/* The mosaic and the cells over it. Positions are percentages of the square so the same markup
 * scales to the lead's column and to a wall; the `size` only decides the zoom and the tile grid.
 * Each tile is drawn a pixel large so percentage rounding never opens a hairline seam.
 *
 * The tiles load eagerly. Every tile of the mosaic is on screen whenever the figure is, so lazy
 * loading defers them and saves nothing — measured: with loading="lazy" not one of twelve tiles
 * had arrived 600 ms after the load event, and the rendered page showed cells over bare paper. */
/* THE TILES A DATA POLL MUST NOT ASK FOR AGAIN.
 *
 * Assigning innerHTML queues an <img> load the instant the markup exists, before any code can put
 * an already-loaded element back — so a redraw goes to the network even for a tile the browser has
 * cached. Measured over CDP: twelve requests to tiles.maps.eox.at on every redraw, none served from
 * cache, though the tiles carry max-age of a week. At one poll per 300 s that is about 3,500 a day
 * from every open page, each one telling that server which square of the planet this house is
 * looking at. The Phase 2 rule is that a press may only ever REDUCE what leaves the house; a poll
 * multiplying it by three hundred breaks the same rule from the other side.
 *
 * `window.KEEP_GROUND` is up only across the route() inside a data redraw. The drawing is a
 * function of the cell, the resolution, the base and the register — all of them in the URL, none of
 * them touched by a poll — so there is nothing for a poll to redraw, and redraw() swaps the living
 * figure back into the hollow one this returns. A press changes the URL, sets no flag, and draws a
 * fresh ground.
 */
function figure(ctx, opts = {}) {
  if (window.KEEP_GROUND) return '';
  const res = opts.res || ctx.RES;
  const base = baseOf(opts.base || ctx.Q.get('base'), res);
  /* the node's own bases need the map ground; the svg ground draws the plan in their place */
  if (base === 'plan' || isOwn(base)) return ctx.KMAP.map(res);
  const f = frame(res, opts.size || SIZE, base);
  const B = BASES[base];
  const pc = v => `${(100 * v / f.size).toFixed(3)}%`;
  const tiles = f.tiles.map(t =>
    `<img src="${B.url(f.z, t.x, t.y)}" width="${TILE}" height="${TILE}" loading="eager" alt=""`
    + ` style="left:${pc(t.left)};top:${pc(t.top)};width:calc(${pc(TILE)} + 1px);`
    + `height:calc(${pc(TILE)} + 1px)" onerror="this.remove()">`).join('');

  /* State is weight and fill, never hue. On a photograph the only colours are ink and --cells, and
   * the hairlines get a --ground halo underneath so they survive a dark roof or a dark sea. */
  const path = c => {
    let s = 'M';
    for (let i = 1; i < c.length; i += 2) {
      s += `${d1(f.X(c[i + 1]))},${d1(f.Y(c[i]))}` + (i + 2 < c.length ? 'L' : '');
    }
    return s + 'Z';
  };
  const others = f.plate.cells_ll.filter(c => c[0] !== f.plate.centre).map(path).join('');
  const own = f.plate.cells_ll.find(c => c[0] === f.plate.centre);
  const cells = `<path d="${others}" fill="none" stroke="var(--ground)" stroke-opacity=".55"`
    + ` stroke-width="2.5"/>`
    + `<path d="${others}" fill="none" stroke="var(--ink)" stroke-opacity=".6" stroke-width=".75"/>`
    + (own ? `<path d="${path(own)}" fill="var(--cells)" fill-opacity=".1" stroke="var(--cells)"`
      + ` stroke-width="2.5"><title>${esc(own[0])}</title></path>` : '');

  const inFrame = (x, y) => x >= 0 && x <= f.size && y >= 0 && y <= f.size;
  const pts = H.sensors.map(s => ({ s, x: f.X(s.lon), y: f.Y(s.lat) }))
    .filter(p => inFrame(p.x, p.y))
    .map(p => `<circle cx="${d1(p.x)}" cy="${d1(p.y)}" r="${p.s.local ? 5.5 : 3.5}"`
      + ` fill="${p.s.local ? 'var(--cells)' : 'var(--ground)'}" stroke="var(--ink)"`
      + ` stroke-width="${p.s.local ? 2 : 1.4}"><title>${esc(p.s.name || p.s.sensor_id)}</title>`
      + `</circle>`).join('');

  return `<div class="groundmap" data-base="${base}" data-z="${f.z}">`
    + `<div class="tiles">${tiles}</div>`
    + `<svg viewBox="0 0 ${f.size} ${f.size}" role="img" aria-label="${esc(`resolution ${res} over `
      + `${B.name} tiles at zoom ${f.z}: the cell this node stands in, the ${f.plate.cells.length - 1}`
      + ` around it, and every station in view`)}">`
    + `<g>${cells}</g><g>${pts}</g>`
    + (H.node.position === 'cell' ? ''
      : `<circle cx="${d1(f.X(H.node.lon))}" cy="${d1(f.Y(H.node.lat))}" r="7" fill="var(--cells)"/>`)
    + `</svg></div>`;
}

/* ------------------------------------------------------------------ not sited yet */
/* A node that has just been plugged in has no coordinates. app/main.py's GET /health reads
 * NODE_LAT/NODE_LON out of the environment with `float(os.getenv("NODE_LAT", 0) or 0)` and rounds to
 * three decimals, so an unsited node publishes exactly 0 for both — absent and unset arrive the same
 * way. The test is therefore "both are falsy": 0, null and undefined all mean the same thing here,
 * and the only real place it would misread is within about 55 m of the point where the equator meets
 * the prime meridian, which is open water in the Gulf of Guinea.
 *
 * It matters because H3 answers for (0, 0) as readily as for anywhere else: without this the plate,
 * the cells and the map would all be drawn over that water and presented to a household as their own
 * ground. The page this replaces drew the computed H3 ground instead, and so does this — it is in
 * app/main.py's COMPANIONS and tools/check_ui.py names it as computed geometry. The register travels
 * in the URL because the drawing is an <img>, a document of its own that no stylesheet on this page
 * reaches: without it the ground drew the dark register's blue on the paper page at 2.29:1. */
const sited = window.KH.sited;

function unsited(ctx) {
  return `<figure class="gridwrap mapwrap" id="ground-figure" data-component="ground" data-ref="rail">`
    + `<img src="static/node-ground.svg?variant=${ctx.register}" alt="the resolution ladder as `
    + `hexagons, drawn by this node; it stands for no particular place until this one has been sited">`
    + `<figcaption class="cap">This node has not been sited yet, so there is no ground to draw. `
    + `Setting NODE_LAT and NODE_LON — <code>planetai setup</code>, or the Set up view — gives it a `
    + `cell, the stations near it, the plan of its own kilometre and every distance on this page. `
    + `Until then the drawing above is the grid itself and not this place.</figcaption></figure>`;
}

/* ------------------------------------------------------------------ the lead figure */
function lead(ctx) {
  if (!sited()) return unsited(ctx);
  const res = ctx.RES;
  const base = baseOf(ctx.Q.get('base'), res);
  /* Pressing the base the rule would have chosen anyway clears the choice, so the rule is back in
   * charge the next time the dial turns rather than a stale press outliving it. */
  /* Only what may be PRESSED is a link — a live base offered while tiles are off would be one click
     between a keeper's setting and this household's kilometre reaching a tile server, and the page
     offering it is the page arguing with the node.
     But a base that may not be pressed is still drawn, disabled, saying which of the two reasons it
     is: the setting, or the resolution. Hiding them made a keeper who had seen satellite and street
     in the prototype think production had lost them — reported 16 September. The whole cost of the
     rule is one setting away and a reader should be able to see what the rule is costing them. */
  const allowed = tilesAllowed(res, window.SETTINGS);
  const tilesOn = (window.SETTINGS || {}).MAP_TILES === 'on';
  const why = tilesOn
    ? `the plan fills the frame from resolution ${PLAN_FROM} in — step the ladder out to offer this`
    : 'live tiles are off on this node — turn MAP_TILES on under Set up';
  /* WHAT EACH BASE COSTS, in the tab, before it is pressed. The request count was at the foot of
     the panel and only ever described the base already showing — so the one number a reader needs
     in order to choose was the one they could only see after choosing. Each tile is this household's
     kilometre named to a tile server, so it is a price and it belongs on the thing being bought.
     The plan's is zero, and says so rather than being left blank. */
  const cost = (k) => {
    if (k === 'plan' || isOwn(k)) return 'sends nothing';
    try {
      const n = frame(res, SIZE, k).tiles.length;
      return `${n} request${n === 1 ? '' : 's'}`;
    } catch (e) { return ''; }
  };
  const strip = `<div class="ctlstrip" role="group" aria-label="the ground under the cells">`
    + Object.entries(BASES).filter(([k]) => !isOwn(k) || ownAllowed(k)).map(([k, b]) => {
      const price = cost(k);
      const inner = `${esc(b.name)}${price ? `<small>${esc(price)}</small>` : ''}`;
      return (k === 'plan' || (isOwn(k) ? ownAllowed(k) : allowed))
        ? `<a class="${k === base ? 'on' : ''}" href="${ctx.qlink({ base: k === autoBase(res, window.SETTINGS) ? null : k })}">${inner}</a>`
        : `<span class="off" aria-disabled="true" title="${esc(why)}">${inner}</span>`;
    }).join('')
    + `</div>`
    /* The rule the strip follows is a SENTENCE ABOUT the strip, not a fourth thing to press. Inside
       the bordered box it wrapped to three lines, made the strip 82px, and the ground panel is in
       the lead's right-hand column — which spans all six rows, so a taller panel pushes the left
       column apart and the as-of off the first screen. It sits under the box now. */
    + `<p class="ctlrule">${allowed
      ? `plan from resolution ${PLAN_FROM} · tiles coarser`
      : (window.SETTINGS || {}).MAP_TILES === 'on'
        ? `the plan fills the frame from resolution ${PLAN_FROM} in`
        /* One line, in this column, at this size. Two lines here cost 17px, and the map column
           spans all six rows of the lead — so the panel's height IS the lead's height, and the
           as-of line sits five pixels above the fold. The disabled tabs carry the same reason. */
        : 'live tiles are off · turn MAP_TILES on under Set up'
      }</p>`;

  let key, cap;
  if (isOwn(base)) {
    const m = ((window.GROUND_META || {}).layers || {})[BASES[base].own] || {};
    key = `<span><i class="own"></i>the cell this node stands in</span>`
      + `<span><i></i>${esc(BASES[base].name)}</span>`;
    cap = `resolution ${res} · kept on this node, sends nothing · ${esc(m.attribution || BASES[base].credit)}`
      + (base === 'drone' ? ` · ${esc(((m.mosaics || []).map(x => `${x.provider}, ${x.date}`)).join('; '))} · drone tiles from zoom 14: zoom in` : '');
  } else if (base === 'plan') {
    key = `<span><i class="own"></i>the cell this node stands in</span>`
      + `<span><i></i>buildings, roads, green — OpenStreetMap</span>`
      + `<span><i class="sat-only"></i>only the satellite knows</span>`;
    cap = esc(ctx.KMAP.caption(res));
  } else {
    const f = frame(res, SIZE, base), B = BASES[base];
    key = `<span><i class="own"></i>the cell this node stands in</span>`
      + `<span><i></i>the ${f.plate.cells.length - 1} cells around it</span>`
      + `<span><svg class="stn" viewBox="0 0 12 12" aria-hidden="true"><circle cx="6" cy="6" r="4.5"`
      + ` fill="var(--cells)" stroke="var(--ink)" stroke-width="1.5"/></svg>this node’s own station · `
      + `<svg class="stn" viewBox="0 0 12 12" aria-hidden="true"><circle cx="6" cy="6" r="3.5"`
      + ` fill="var(--ground)" stroke="var(--ink)" stroke-width="1.2"/></svg>another</span>`;
    cap = `resolution ${res} · <span data-num="ground.across" data-cmp="against one cell here, `
      + `${esc(edge(H.ladder[res].edge_m))} to an edge">${esc(edge(f.across_m))}</span> across · `
      + `zoom <span data-num="ground.zoom" data-cmp="against ${B.maxZ}, the finest ${esc(B.host)} `
      + `serves">${f.z}</span> · <span data-num="ground.tiles" data-cmp="against 0 for the offline `
      + `plan">${f.tiles.length}</span> tiles from ${esc(B.host)} · ${esc(B.credit)}`;
  }
  /* Simple's key is one sentence a household reads: its own station, and how many others are within a
     kilometre. The cell, the plan caption and the rule about resolutions are the keeper's. */
  const st = ctx.S.issues.stations || [];
  const own = st.filter(x => x.local).length;
  const near = st.filter(x => !x.local && x.km != null && x.km <= 1).length;
  const plainKey = `<p class="gridkey plainkey" data-lv="simple" data-component="groundKey" data-ref="ground-figure">`
    + `<span class="d me"></span>${own ? 'this house' : 'no station of this house\u2019s own yet'} \u00b7 `
    + `<span class="d"></span>${near ? `<b data-num="ground.near" data-cmp="stations not this house\u2019s, `
      + `within 1 km">${near}</b> other station${near === 1 ? '' : 's'} within a kilometre`
      : 'no other station within a kilometre'}</p>`;
  /* Simple draws no ladder, so the figure answers to the header there instead of pointing at nothing. */
  const up = (window.PAI_MODE && window.PAI_MODE() === 'simple' && ctx.VIEW === 'now') ? 'header' : 'rail';
  LAST = ctx;
  return `<figure class="gridwrap mapwrap" id="ground-figure" data-component="ground" data-ref="${up}">`
    + strip.replace('<p class="ctlrule">', '<p class="ctlrule" data-lv="adv">')
    + (mapOn() ? shell(res, base) : figure(ctx, { base, size: SIZE }))
    + `<div class="gridkey" data-lv="adv">${key}</div>` + plainKey
    + `<figcaption class="cap" data-lv="adv">${cap}</figcaption></figure>`;
}

/* ------------------------------------------------------------------ what this map sends out */
/* Two rows: the base in use, and the one it is measured against. Nothing here is a warning; it is
 * a count of requests and the name of the machine that receives them. */
function render(ctx) {
  if (!sited()) {
    return `<p class="note" data-component="groundOut" id="ground-out-plan" data-ref="requests-node">`
      + `Nothing is being fetched for a map, because there is no place to fetch one for. A sited `
      + `node draws its own plan from this machine's disk and sends nothing; live tiles, if a keeper `
      + `turns them on, send one request per tile to somebody else's machine.</p>`;
  }
  const res = ctx.RES;
  const base = baseOf(ctx.Q.get('base'), res);
  const cols = 'minmax(0,210px) minmax(0,1fr) auto';
  const who = (b, m) => `<span class="who"><b>${esc(b)}</b><span class="m">${esc(m)}</span></span>`;
  const live = (k, verb) => {
    const f = frame(res, SIZE, k), B = BASES[k];
    return row({
      id: `ground-out-${k}`, component: 'groundOut', ref: 'requests-node', cols,
      left: who(B.host, `${B.name} · zoom ${f.z}`),
      line: `${verb} one request per tile to ${B.host}, from the device this page is open on. Each `
        + `names a square of ground ${edge(f.tile_m)} wide, so the server learns which `
        + `${edge(f.across_m)} of the planet is being looked at, and from which address.`,
      qty: [{ num: `ground.requests.${k}`, value: `${f.tiles.length} requests`,
        cmp: 'against 0 for the offline plan' }],
    });
  };
  const plan = row({
    id: 'ground-out-plan', component: 'groundOut', ref: 'requests-node', cols,
    left: who('this node', 'plan, offline'),
    line: 'Every shape is on this machine’s disk, fetched once by the place pack. Opening the page '
      + 'asks nothing of anybody.',
    qty: [{ num: 'ground.requests.plan', value: '0 requests',
      cmp: `against the ${frame(res, SIZE, 'sat').tiles.length} the satellite base sends` }],
  });
  return (base === 'plan' || isOwn(base)) ? plan + live('sat', 'Switched on, the satellite base sends')
    : live(base, 'This view sends') + plan;
}

/* ------------------------------------------------------------------ the notes */
function notes(ctx) {
  if (!sited()) {
    return [{ id: 'ground-unsited', label: 'No coordinates',
        text: 'This node has no coordinates, so nothing on this page can '
      + 'say where it is. GET /health publishes lat and lon rounded to three decimals and an unsited '
      + 'node publishes zero for both, which is a real point in the Gulf of Guinea — so the page '
      + 'draws the grid itself rather than a map of open water labelled as this household’s ground.' }];
  }
  const base = baseOf(ctx.Q.get('base'), ctx.RES);
  const f = frame(ctx.RES, SIZE, (base === 'plan' || isOwn(base)) ? 'sat' : base);
  return [
    { id: 'ground-rule', label: 'Where the plan takes over',
        text: `From resolution ${PLAN_FROM} inward the ground is this node’s own `
      + 'plan unless a live base is pressed. The plan is about 3 km across and the resolution-9 '
      + 'plate is 1.6 km, so from 9 the plan fills the frame edge to edge; there it is the better '
      + 'drawing, every vertex is the node’s own, and it sends nothing. At 8 the plate is 4.2 km and '
      + 'the plan sits in the middle with paper round it, so the tiles show there and coarser, but '
      + `only when a keeper has set MAP_TILES to on, which on this node it `
      + `${(window.SETTINGS || {}).MAP_TILES === 'on' ? 'is' : 'is not'}. Off, the plan is the ground `
      + 'at every rung and the page sends nothing at all.' },
    { id: 'ground-why-live', label: 'Why a live base at all',
        text: 'The live bases show what the plan cannot: a real map, with a '
      + 'satellite view that rescales when the ladder moves. They cost what the plan does not: a page '
      + 'that fetches tiles tells the tile server which square of the planet is being looked at, '
      + 'every time anybody opens it. So they are off until a keeper turns them on, the cost is '
      + 'printed beside the picture, and the offline plan is one press away in the same strip.' },
    { id: 'ground-cost', label: 'What a tile costs',
        text: `What leaves: one request per tile, ${f.tiles.length} for this view, `
      + `from the device the page is open on to ${BASES[f.base].host}. Each request names a tile by `
      + `zoom, column and row, which is a square of ground ${edge(f.tile_m)} wide, and carries the `
      + `device's own address. The server does not learn that this is a PLANETAI node or where the `
      + `node itself stands beyond that square; it does learn that somebody at that address looks at `
      + `this ${edge(f.across_m)}${S.health.city ? ` of ${S.health.city}` : ''}, and how often. The `
      + `plan sends nothing.` },
    { id: 'ground-zoom', label: 'Zoom follows the ladder',
        text: 'The zoom follows the ladder because the frame is the cells, not the '
      + 'map. The ladder sets the resolution, the resolution sets the nineteen cells of the plate, and '
      + 'the zoom is the largest of 0 to 19 at which their bounding box fits nine tenths of the '
      + 'square. H3 steps by seven in area and a tile zoom by four, so one rung on the ladder moves the '
      + 'zoom by one or two levels, and the cell in the middle stays the same size on the page at '
      + 'every rung within a factor of two.' },
    { id: 'ground-frames', label: 'Two frames, one drawing',
        text: 'Tiles are Web Mercator, EPSG:3857, because that is the only frame a '
      + 'tile server speaks. The offline plan is drawn in the node\'s own local frame: metres east '
      + 'and north of the node, which make-plan.mjs computed and kit-map.js places. At 8.8° south '
      + 'Mercator\'s scale is within 1.2% of true and constant to a part in a thousand across a 5 km '
      + 'frame, so the cells fall on the same pixels either way. At resolution 2 and 3 the frame is '
      + 'hundreds of kilometres and the difference shows; there the plan is already a rectangle, and '
      + 'the tiles are the only base that is a picture at all.' },
    { id: 'ground-osm-policy', label: 'OpenStreetMap’s usage policy',
        text: 'OpenStreetMap\'s tiles come from volunteer-run servers under a '
      + 'usage policy: light use, attribution, a real browser referrer, no bulk downloading. One '
      + 'household opening one page is inside it; a fleet of nodes refreshing a map every minute '
      + 'would not be, and the same tile fetched without a referrer is refused with a placeholder '
      + 'that says so. The attribution is in the caption, and this page asks for tiles only when '
      + 'somebody opens it.' },
    { id: 'ground-s2', label: 'The satellite base',
        text: 'The satellite base is EOX\'s Sentinel-2 cloudless mosaic for 2020: '
      + 'many passes stitched into one cloud-free picture, six years old. It is a ground to read '
      + 'the cells against, not an observation of today — the sky, the season and the newest roofs '
      + 'in it are none of this week\'s. What this node\'s own satellite passes saw of the same '
      + 'ground is the satellite section, dated.' },
  ];
}

/* ------------------------------------------------------------------ the map ground, UI_GROUND=map */
/* The same ground, drawn by MapLibre (the base) and deck.gl (the cells and stations over it), so it
 * pans and zooms. Behind a setting, default svg, and the svg drawing is what anything that fails
 * here gets instead: never a blank.
 *
 * THE NODE STILL COMPUTES. Every ring drawn is a `cells_ll` the node sent in /issues' geometry; the
 * page turns [id, lat, lng, lat, lng, …] into [[lng, lat], …] and nothing more. No h3-js, no
 * H3HexagonLayer: deck.gl's hexagon layer would compute boundaries in this browser.
 *
 * THE COST IS STILL THE STRIP'S. `baseOf` already refused a live base MAP_TILES does not allow, so
 * the only tile URL that can reach MapLibre is one the strip priced. A live base cannot be dragged
 * or zoomed: every drag would be tiles nobody priced. The plan pans and zooms freely, because it is
 * one GeoJSON the page already holds and moving it asks nobody anything.
 *
 * The libraries are fetched from this node, once, the first time the ground is drawn this way, and
 * never on the wall or in simple mode. */
let LAST = null;
const mapOn = () => (window.SETTINGS || {}).UI_GROUND === 'map'
  && !(window.PAI_MODE && window.PAI_MODE() === 'simple');

function shell(res, base) {
  if (window.KEEP_GROUND) return '';
  return `<div class="groundmap groundgl" id="groundgl" data-base="${base}" data-res="${res}"`
    + ` role="img" aria-label="${esc(`resolution ${res} over the ${BASES[base].name}: the cell this `
      + 'node stands in, the cells around it, and every station in view')}"></div>`;
}

const webgl2 = () => {
  try { return !!document.createElement('canvas').getContext('webgl2'); } catch (e) { return false; }
};
let LIBS = null;
function libs() {
  if (LIBS) return LIBS;
  const add = (tag, attrs) => new Promise((ok, no) => {
    const el = Object.assign(document.createElement(tag), attrs);
    el.onload = ok;
    el.onerror = () => no(new Error(`static/${(attrs.src || attrs.href).split('/').pop()} did not load`));
    document.head.appendChild(el);
  });
  LIBS = Promise.all([
    add('link', { rel: 'stylesheet', href: 'static/maplibre-gl.css' }),
    add('script', { src: 'static/maplibre-gl.js' }).then(() => add('script', { src: 'static/deck.gl.min.js' })),
  ]);
  LIBS.catch(() => { LIBS = null; });
  return LIBS;
}

/* A token as [r, g, b], read from the element so it follows the register the page is in. */
const rgb = (el, name) => {
  const v = getComputedStyle(el).getPropertyValue(name).trim().replace('#', '');
  const h = v.length === 3 ? v.split('').map(c => c + c).join('') : v;
  return [0, 2, 4].map(i => parseInt(h.slice(i, i + 2), 16) || 0);
};
const hex = c => '#' + c.map(v => v.toString(16).padStart(2, '0')).join('');
const lnglat = c => { const r = []; for (let i = 1; i < c.length; i += 2) r.push([c[i + 1], c[i]]); return r; };

function fallback(el, why) {
  const f = document.querySelector('#ground-figure');
  if (!LAST || !el.isConnected) return;
  el.outerHTML = figure(LAST, { base: el.dataset.base, size: SIZE });
  if (f) f.insertAdjacentHTML('beforeend', `<p class="note" data-component="absent" id="groundgl-off"`
    + ` data-ref="ground-figure">The map ground did not draw here (${esc(why)}), so this is the drawn `
    + 'ground instead.</p>');
}

/* The node's own street map, satellite and drone, in the page's tokens: land is the ground, water and buildings are
   the ink at low strength, green is the rings green faint. Rasters sit over the street map and under its names. */
const mix = (a, b, t) => hex(a.map((v, i) => Math.round(v + (b[i] - v) * t)));
function ownStyle(base, T, style) {
  const G = (window.GROUND_META || {}).on_disk || {}, at = p => `${location.origin}/ground/${p}`;
  const any = l => ['in', ['get', 'kind'], ['literal', l]];
  const W = (h, m, n) => ['interpolate', ['exponential', 1.6], ['zoom'], 12, ['match', ['get', 'kind'], 'highway', h[0], 'major_road', m[0], n[0]],
    18, ['match', ['get', 'kind'], 'highway', h[1], 'major_road', m[1], n[1]]];
  const water = mix(T.ground, T.cells, 0.14), bldg = mix(T.ground, T.ink, 0.2), casing = mix(T.ground, T.ink, 0.16);
  const road = mix(T.ground, [255, 255, 255], 0.7), label = mix(T.ground, T.ink, 0.62);
  style.layers[0].paint['background-color'] = water;
  if (G.vector) {
    style.sources.v = { type: 'vector', tiles: [at('vector/{z}/{x}/{y}.pbf')], maxzoom: 15 };
    style.layers.push(
      { id: 'v-earth', type: 'fill', source: 'v', 'source-layer': 'earth', paint: { 'fill-color': hex(T.ground) } },
      { id: 'v-green', type: 'fill', source: 'v', 'source-layer': 'landuse', filter: any(['park', 'wood', 'forest', 'garden', 'grass', 'grassland', 'scrub', 'nature_reserve', 'golf_course', 'cemetery', 'meadow', 'pitch']),
        paint: { 'fill-color': mix(T.ground, T.rings, 0.14) } },
      { id: 'v-water', type: 'fill', source: 'v', 'source-layer': 'water', filter: ['==', ['geometry-type'], 'Polygon'], paint: { 'fill-color': water } },
      { id: 'v-casing', type: 'line', source: 'v', 'source-layer': 'roads', filter: any(['minor_road', 'major_road', 'highway']), minzoom: 12,
        layout: { 'line-cap': 'round', 'line-join': 'round' }, paint: { 'line-color': casing, 'line-width': W([2.4, 22], [1.8, 18], [0.9, 13]) } },
      { id: 'v-road', type: 'line', source: 'v', 'source-layer': 'roads', filter: any(['minor_road', 'major_road', 'highway']),
        layout: { 'line-cap': 'round', 'line-join': 'round' }, paint: { 'line-color': road, 'line-width': W([1.6, 19], [1.1, 15], [0.5, 10.5]) } },
      { id: 'v-bldg', type: 'fill', source: 'v', 'source-layer': 'buildings', minzoom: 13, paint: { 'fill-color': bldg } });
  }
  if (base !== 'street' && G[base]) {
    style.sources.photo = { type: 'raster', tiles: [at(`${base}/{z}/{x}/{y}.png`)], tileSize: TILE, minzoom: BASES[base].minZ, maxzoom: BASES[base].maxZ };
    style.layers.push({ id: 'photo', type: 'raster', source: 'photo', paint: { 'raster-fade-duration': 0 } });
  }
  if (G.vector && G.glyphs) {
    style.glyphs = at('glyphs/{fontstack}/{range}.pbf');
    const txt = { 'text-color': base === 'street' ? label : '#ffffff', 'text-halo-color': base === 'street' ? hex(T.ground) : 'rgba(0,0,0,.6)', 'text-halo-width': 1.3 };
    style.layers.push(
      { id: 'v-road-label', type: 'symbol', source: 'v', 'source-layer': 'roads', minzoom: 14.5, filter: ['has', 'name'],
        layout: { 'symbol-placement': 'line', 'text-field': ['get', 'name'], 'text-font': ['Noto Sans Regular'], 'text-size': 10.5 }, paint: txt },
      { id: 'v-place-label', type: 'symbol', source: 'v', 'source-layer': 'places', filter: ['has', 'name'],
        layout: { 'text-field': ['get', 'name'], 'text-font': ['Noto Sans Medium'], 'text-size': 12, 'text-max-width': 7 }, paint: txt });
  }
}

function draw(el) {
  const res = Number(el.dataset.res), base = el.dataset.base;
  const plate = H.nav.plates[res];
  const T = { ground: rgb(el, '--ground'), ink: rgb(el, '--ink'), cells: rgb(el, '--cells'),
    rings: rgb(el, '--rings'), sat: rgb(el, '--satellite-only') };
  const style = { version: 8, sources: {},
    layers: [{ id: 'paper', type: 'background', paint: { 'background-color': hex(T.ground) } }] };
  const B = BASES[base];
  if (isOwn(base)) {
    ownStyle(base, T, style);
  } else if (B.url) {
    style.sources.tiles = { type: 'raster', tiles: [B.url('{z}', '{x}', '{y}')], tileSize: TILE,
      maxzoom: B.maxZ, attribution: B.credit };
    style.layers.push({ id: 'tiles', type: 'raster', source: 'tiles' });
  } else if (window.PLAN_GJ) {
    /* kit-map.js's drawing, as MapLibre layers: the same kinds, the same tokens, the same weights. */
    style.sources.plan = { type: 'geojson', data: window.PLAN_GJ, attribution: B.credit };
    const kind = k => ['==', ['get', 'kind'], k];
    style.layers.push(
      { id: 'green', type: 'fill', source: 'plan', filter: kind('green'),
        paint: { 'fill-color': hex(T.rings), 'fill-opacity': 0.26 } },
      { id: 'roads', type: 'line', source: 'plan', filter: kind('road'),
        paint: { 'line-color': hex(T.ink), 'line-opacity': 0.65,
          'line-width': ['match', ['coalesce', ['get', 'highway'], ''],
            ...Object.entries(window.KMAP_ROAD_W || {}).flat(), 0.8] } },
      { id: 'buildings', type: 'fill', source: 'plan', filter: kind('building'),
        paint: { 'fill-color': hex(T.ink), 'fill-opacity': 0.82 } },
      { id: 'sat', type: 'fill', source: 'plan', filter: kind('sat'),
        paint: { 'fill-color': hex(T.sat), 'fill-opacity': 0.35 } },
      { id: 'sat-edge', type: 'line', source: 'plan', filter: kind('sat'),
        paint: { 'line-color': hex(T.sat), 'line-width': 0.7 } },
      { id: 'poi', type: 'circle', source: 'plan', filter: kind('poi'),
        paint: { 'circle-color': hex(T.cells), 'circle-radius': 4.5 } });
  }
  /* The frame is still the cells. Live tiles are frame()'s own: the zoom it picks for the 600 px
     square, scaled to this box exactly as the svg ground scales its percentages, so the same tiles are
     asked for and the count in the strip is the count sent. */
  const w = el.clientWidth || SIZE;
  const f = frame(res, SIZE, B.url ? base : 'sat');
  const live = !!B.url && !isOwn(base);
  const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;
  let asked = 0;
  /* The plan keeps kit-map's frame: the plate's bounding box with six per cent round it. */
  let lng0 = 180, lat0 = 90, lng1 = -180, lat1 = -90;
  for (const c of plate.cells_ll) {
    for (let i = 1; i < c.length; i += 2) {
      lat0 = Math.min(lat0, c[i]); lat1 = Math.max(lat1, c[i]);
      lng0 = Math.min(lng0, c[i + 1]); lng1 = Math.max(lng1, c[i + 1]);
    }
  }
  const view = live ? { center: [H.node.lon, H.node.lat], zoom: f.z - 1 + Math.log2(w / SIZE) }
    : { bounds: [[lng0, lat0], [lng1, lat1]], fitBoundsOptions: { padding: Math.round(w * 0.06 / 1.12) } };
  const map = new maplibregl.Map({
    container: el, style, ...view,
    interactive: !live, dragRotate: false, pitchWithRotate: false, touchPitch: false, maxPitch: 0,
    fadeDuration: reduce ? 0 : 150, attributionControl: false,   // the caption under the figure carries the credit, as it does for the svg ground
    /* The node's own tiles carry the token the page holds, as every other read does; anything else is counted. */
    transformRequest: url => {
      if (url.startsWith(location.origin + '/ground/')) return { url, headers: window.PAI_AUTH ? window.PAI_AUTH() : {} };
      if (/^https?:/.test(url) && !url.startsWith(location.origin)) asked++;
      return { url };
    },
  });
  if (!live) map.touchZoomRotate.disableRotation();
  /* A tile that fails is a gap in the base, as an <img> that fails is in the svg ground; anything
     else before the first frame is a map that is not going to draw, and the svg ground replaces it. */
  map.on('error', e => {
    if (e.sourceId || el.dataset.drawn) return;
    map.remove();
    fallback(el, (e.error && e.error.message) || 'the map failed');
  });

  const cells = plate.cells_ll.map(c => ({ id: c[0], own: c[0] === plate.centre, ring: lnglat(c) }));
  const claims = (H.claims || []).flatMap(c => (c.cells_ll || []).map(x => ({ id: x[0], claim: c.name, ring: lnglat(x) })));
  const stations = (H.sensors || []).filter(s => s.lat != null && s.lon != null);
  const D = window.deck;
  const px = { lineWidthUnits: 'pixels', radiusUnits: 'pixels' };
  /* Hairlines as each svg ground draws them: kit-map's thin ink over the plan, the haloed ones
     that survive a dark roof over a photograph. */
  const hair = live ? { a: 153, w: 1 } : { a: 64, w: 1 };   // under 1 px a WebGL line aliases into dashes
  const layers = [
    /* kit-map's kilometre: a circle of 1,000 m round the node, a radius in metres like the svg's r. */
    ...(live ? [] : [new D.ScatterplotLayer({ id: 'km', data: [H.node], getPosition: n => [n.lon, n.lat],
      radiusUnits: 'meters', getRadius: 1000, filled: false, stroked: true, lineWidthUnits: 'pixels',
      getLineColor: [...T.ink, 89], getLineWidth: 1 })]),
    new D.PolygonLayer({ id: 'claims', data: claims, getPolygon: d => d.ring, filled: false, ...px,
      getLineColor: [...T.ink, 40], getLineWidth: 0.5, pickable: true }),
    ...(live ? [new D.PolygonLayer({ id: 'cells-halo', data: cells.filter(c => !c.own), getPolygon: d => d.ring,
      filled: false, ...px, getLineColor: [...T.ground, 140], getLineWidth: 2.5 })] : []),
    new D.PolygonLayer({ id: 'cells', data: cells.filter(c => !c.own), getPolygon: d => d.ring,
      filled: false, ...px, getLineColor: [...T.ink, hair.a], getLineWidth: hair.w, pickable: true }),
    new D.PolygonLayer({ id: 'own', data: cells.filter(c => c.own), getPolygon: d => d.ring, ...px,
      filled: true, getFillColor: [...T.cells, 26], getLineColor: T.cells, getLineWidth: 2.5, pickable: true }),
    /* Own stations filled, everyone else's hollow, exactly as the svg ground draws them. */
    new D.ScatterplotLayer({ id: 'stations', data: stations, getPosition: s => [s.lon, s.lat], ...px,
      stroked: true, filled: true, getRadius: s => s.local ? 5.5 : 3.5,
      getFillColor: s => s.local ? T.cells : T.ground, getLineColor: T.ink,
      getLineWidth: s => s.local ? 2 : 1.4, pickable: true }),
  ];
  if (!live || H.node.position !== 'cell') {
    layers.push(new D.ScatterplotLayer({ id: 'node', data: [H.node], getPosition: n => [n.lon, n.lat], ...px,
      getRadius: 7, getFillColor: T.cells }));
  }
  /* An H3 id is printed in full, once per object, never truncated: the hover says which object. */
  const getTooltip = ({ object: o, layer }) => !o ? null
    : layer.id === 'stations' ? (o.name || o.sensor_id)
      : layer.id === 'claims' ? `${o.claim} · ${o.id}` : o.id;
  map.addControl(new D.MapboxOverlay({ interleaved: true, layers, getTooltip }));
  map.once('idle', () => {
    el.dataset.drawn = '1';
    const n = document.querySelector('[data-num="ground.tiles"]');
    if (live && n) n.textContent = String(asked);
  });
}

/* Called by route() after every render. A data poll swaps the living figure back in (redraw), so a
   map that is already drawn is never drawn twice and never asks a tile server again on a poll. */
async function mount() {
  const el = document.querySelector('#groundgl:not([data-mounted])');
  if (!el || window.KEEP_GROUND) return;
  el.dataset.mounted = '1';
  if (!webgl2()) return fallback(el, 'this browser has no WebGL2');
  try { await libs(); draw(el); } catch (e) { fallback(el, String((e && e.message) || e)); }
}

/* PORTED: this module's CSS is in dashboard.css, under a banner naming this file. */

window.GROUND = { figure, frame, BASES, SIZE, mount };

window.PAI.register({
  id: 'ground', pack: 'place', stage: 'observe', title: 'The ground', order: 0, learn: ['tiles', 'cell'],
  reads: ['/issues', '/place/geojson', '/settings', '/health'],
  needs: ['H3.nav'],
  anchor: 'ground-figure',   /* no band of its own, so its notes point at the drawing they explain */
  /* No `render`: the ledger that used to sit at this section's foot is its own section now (see
     below). The ground is a surface with a tab bar, like the wall — it is not a card and carries no
     data-kind — so what remains here is the drawing and the notes that explain it. */
  lead, notes,
});

/* What leaves this machine when somebody opens this page, and what leaves the node when nobody is
 * looking. Promoted out of the ground's foot, where it was a footnote to a map, because it is not
 * about the map: it is the one section that accounts for this page as a thing that reaches out.
 *
 * TWO HALVES, AND THE DIFFERENCE MATTERS. A tile request is made by the device you are reading on,
 * to somebody else's server, and it tells them which square of ground you are looking at and from
 * which address. A poll is made by the node, on your behalf, whether or not anyone is at the
 * screen. Rolling them into one count would say the same number means the same thing twice. */
window.PAI.register({
  id: 'requests', pack: 'place', stage: 'observe', order: 60, learn: ['share', 'dido'],
  reads: ['/health', '/sensors', '/settings', '/issues'],
  title: 'What this page asked of the world',
  needs: ['H3.nav'],
  render(ctx) {
    const h = ctx.S.health || {};
    const all = window.SENSORS || [];
    /* Whose machines the node itself polls, named from the rows they wrote. `source` and not
       `attribution`: /sensors carries the former and has never carried the latter, and reading a
       field that is not there is how this row silently drew nothing at all. Local kit is excluded —
       a sensor on this wall is not somebody the node reaches out to — and these are the node's own
       slugs rather than a prettier list kept here, so a pack that starts reading somewhere new
       appears without anyone remembering to add it. */
    const upstream = [...new Set(all.filter(x => !x.local && x.source).map(x => x.source))].sort();
    const cols = 'minmax(0,210px) minmax(0,1fr) auto';
    const who = (b, m) => `<span class="who"><b>${esc(b)}</b><span class="m">${esc(m)}</span></span>`;
    return render(ctx)
      + `<div class="reads" id="requests-node" data-ref="requests">`
      + row({ id: 'requests-poll', component: 'requestsPoll', ref: 'requests-node', cols,
        left: who('this node', 'polling, with nobody watching'),
        line: `The node fetches on its own cycle whether or not this page is open, which is how `
          + `there is a day to draw when you arrive. That reaching is the node's, not yours, and it `
          + `happens from this house rather than from the device you are reading on.`,
        qty: [{ num: 'requests.polls',
          value: `${h.polls == null ? '—' : h.polls} poll${h.polls === 1 ? '' : 's'}`,
          cmp: `${h.ingested == null ? 'an unknown number of' : h.ingested} readings taken in` }] })
      + (upstream.length ? row({ id: 'requests-upstream', component: 'requestsUp',
        ref: 'requests-node', cols,
        left: who('whose machines', 'named by the rows they wrote'),
        line: upstream.join(' · '),
        qty: [{ num: 'requests.upstream', value: String(upstream.length),
          cmp: `sources outside this house that this node reads` }] }) : '')
      + `</div>`;
  },
  notes(ctx) {
    return [
      { id: 'requests-poll', label: 'Two kinds of reaching',
        text: 'Two different kinds of reaching are counted here and they are '
        + 'not the same number twice. A tile request is made by the device you are reading on, to '
        + 'somebody else\u2019s server, and tells them which square of ground you are looking at and '
        + 'from which address. A poll is made by the node, from this house, whether or not anybody '
        + 'is at the screen \u2014 which is why there is a day already drawn when you arrive.' },
      { id: 'requests-upstream', label: 'Named by the rows they wrote',
        text: 'These are named by the rows they wrote, not by a list kept '
        + 'here, so a pack that starts reading somewhere new appears in this count without anyone '
        + 'remembering to add it. A sensor on this house\u2019s own wall is not in it: the node does '
        + 'not reach out to reach it.' },
    ];
  },
});

});

/* ================================================================= h/mods/figures.js ==== */
/* figures · core · measure
 *
 * Every figure on this page, once, with where it came from and what the node calls it. Eighteen
 * rows on node #1, and the node computed all of them — `issues[*].provenance[]` is the ledger, not
 * a summary the page assembles by walking its own DOM.
 *
 * WHY IT IS THE LAST THING. A reader who wants to check one number should not have to find the card
 * it came from: the whole page in one table, in loop order, is the citation list. It closes the page
 * the way the care label closes the loop — after everything, for the reader who is not taking it on
 * trust.
 *
 * NO NUMERAL HERE HAS A COMPARISON, and that is why they carry `data-figure` rather than `data-num`.
 * T4 counts numerals without a comparison, and it is right to: a figure on a card must say what it
 * is measured against. But this table is the provenance OF those figures, and the comparison is on
 * the card the row names. Repeating it eighteen times would be quoting the page at itself.
 */
PAI_LOAD.push(function () {
'use strict';

const { esc, fmt, pill, age } = window.K;

window.PAI.register({
  id: 'figures', pack: 'core', stage: 'measure', order: 90, learn: ['figures'],
  reads: ['/issues'],
  title: 'Every figure on this page, and where it came from',
  render(ctx) {
    const { ISS, ORDER } = ctx;
    const rows = (ORDER || []).flatMap(k => ((ISS[k] || {}).provenance || [])
      .map(e => ({ ...e, issue: k })));
    /* The same figures as a file anyone may take: the day's open export, and the days before it.
       GET /export needs a day, and the day is the node's own, off the reading this page drew. */
    const day = String(((ctx.S || {}).issues || {}).as_of || '').slice(0, 10);
    const exported = `<p class="cap" id="figures-export" data-ref="figures-table">Today\u2019s open `
      + `export, CC BY 4.0: `
      + (/^\d{4}-\d{2}-\d{2}$/.test(day)
        ? `<a class="mono" target="_blank" rel="noopener" href="/export?day=${esc(day)}">GET /export?day=${esc(day)}</a>`
        : `<span class="mono">GET /export?day=YYYY-MM-DD</span>`)
      + `. Past days: <a class="mono" target="_blank" rel="noopener" href="/exports">GET /exports</a>.</p>`;
    if (!rows.length) {
      return `<p class="note" id="figures-none" data-ref="care">This node sent no provenance for `
        + `its figures, so there is nothing to list. That is a gap in what it published, not an `
        + `empty page: every figure above came from somewhere.</p>` + exported;
    }
    return `<div class="figwrap" id="figures-table" data-ref="care">`
      + `<table class="figs"><thead><tr>`
      + `<th>figure</th><th>value</th><th>from</th><th>word</th><th>age</th>`
      + `</tr></thead><tbody>`
      + rows.map(e => `<tr id="fig-${esc(e.figure)}">`
        + `<td class="mono">${esc(e.figure)}</td>`
        + `<td class="mono num" data-figure="${esc(e.figure)}">`
        + `${e.value == null ? '\u2014' : esc(fmt(e.value, e.unit === '%' ? 1 : 2))}`
        + `<small> ${esc(e.unit || '')}</small></td>`
        + `<td><span class="said">${esc(e.source || '')}</span>`
        + `${e.n > 1 ? `<small> \u00b7 ${e.n} of them</small>` : ''}</td>`
        + `<td>${pill(e.provenance)}</td>`
        + `<td class="mono">${e.age_minutes == null ? '\u2014' : esc(age(e.age_minutes))}</td>`
        + `</tr>`).join('')
      + `</tbody></table>`
      + `<p class="cap">${rows.length} figures, in loop order. The node computed this list; the `
      + `page did not assemble it by reading itself.</p>${exported}</div>`;
  },
  notes(ctx) {
    const n = (ctx.ORDER || []).reduce((a, k) => a + (((ctx.ISS[k] || {}).provenance) || []).length, 0);
    return [
      { id: 'figures-table', label: 'The node’s ledger, not a summary',
        text: `Every figure on the page, once, with its source and the word the `
        + `node puts on it \u2014 ${n} of them here. It is the node's own ledger and not a summary this `
        + `page assembled: a page that walked its own numbers to build a citation list would be `
        + `citing itself. A reader checking one figure should not have to find the card it came `
        + `from, which is why the whole page is in one table at the end of it.` },
      { id: 'fig-air.room', label: 'Why these carry no comparison',
        text: 'These numerals carry no comparison, which every other numeral on '
        + 'the page must. That is deliberate: this is the provenance OF those figures, and what each '
        + 'is measured against is on the card the row names. Repeating it eighteen times would be '
        + 'the page quoting itself, so these are marked as figures rather than as numerals and the '
        + 'gate that counts uncompared numerals correctly ignores them.' },
    ];
  },
});

});

/* ================================================================= h/mods/matrix.js ==== */
/* matrix · core · observe
 *
 * Every issue this node carries, at every distance it can read, against the line it is read
 * against. Four issues down, five columns across: house · street · ring · region · line.
 *
 * WHY IT IS ONE CARD AND NOT FOUR. The lead says one number about one issue. This says the same
 * kind of number about all of them at once, and the whole point is the comparison DOWN a column:
 * whether the street is worse than the room is a different question from whether the air is worse
 * than the heat, and only a grid lets a reader ask both. Four separate cards would answer neither.
 *
 * EVERY EMPTY CELL SAYS WHY. A blank reads as a node that did not bother; `reasonFor` names which
 * absence it is — no sensor indoors, no kit on the wall outside, no public station reporting, no
 * model for this point. That is the sentence a keeper acts on, and it is the commonest cell here.
 *
 * The columns and their words are the node's (`issues.distances`, `issues.labels[loc]`), never this
 * file's: a heading and the sentence under it have to agree, and only one of them can be the source.
 */
PAI_LOAD.push(function () {
'use strict';

const { esc, stack, pill } = window.K;

window.PAI.register({
  id: 'matrix', pack: 'core', stage: 'observe', title: 'Every issue, at every distance', order: 10, learn: ['distances', 'states'],
  reads: ['/issues'],
  /* No `needs`. It resolves paths against `window`, and the issues are file-scope in the kit, not
     global — `needs: ['ISS']` would have drawn "the core pack has nothing here yet" on every node
     that has issues. A node with none is a real state and the render says so itself. */
  render(ctx) {
    const { ISS, ORDER } = ctx;
    const rows = ORDER.filter(k => ISS[k]);
    if (!rows.length) return `<p class="note" id="matrix-grid" data-ref="rail">This node carries no `
      + `issues in this capture.</p>`;
    return `<div class="matrix" id="matrix-grid" data-ref="rail">`
      + rows.map(k => {
        const d = ISS[k];
        return `<div class="mrow" id="mrow-${esc(k)}" data-ref="matrix-grid">`
          + `<p class="mname"><b>${esc(d.name[LOC])}</b>${d.watched ? '' : ' <span class="m">not '
            + 'watched</span>'} ${pill(d.state)}</p>`
          + stack(k, d, { id: `matrix-${esc(k)}`, line: true, ref: `mrow-${esc(k)}` })
          + `</div>`;
      }).join('')
      + `</div>`;
  },
  notes() {
    return [
      { id: 'matrix-grid', label: 'Why a grid and not a list',
        text: 'Four issues down, five columns across, and the column you can read '
        + 'down is the reason this is a grid. Whether the ring is worse than the house is a '
        + 'different question from whether the air is worse than the heat, and four separate cards '
        + 'would answer neither. The last column is the line — what the four readings to its left '
        + 'are read against — drawn once per row rather than repeated in every cell.' },
      { id: 'mrow-air', label: 'What an empty cell says',
        text: 'An empty cell is the commonest thing on this grid and it always says '
        + 'which absence it is: no sensor in the house, no kit outside on the street, no public station '
        + 'reporting, no model for this point. Those are four different jobs for whoever keeps this '
        + 'node, and a blank would have been none of them.' },
    ];
  },
});

});

/* ================================================================= h/mods/day.js ==== */
/* day · core · observe
 *
 * The day this place just had, for the two issues that have one. Each is one series with a trace
 * per distance, the line dashed red across it, and the hours it was over marked under the axis.
 *
 * WHY TWO AND NOT FOUR. A series needs a series: on this node Land and Coast have no hourly record
 * at any distance, so a card for them would be two empty boxes claiming to be drawings. They are
 * not hidden — the matrix above says what each of them has and does not have, at every distance,
 * which is the honest place for an absence. Here, a card appears when there is a day to draw.
 *
 * WHAT THE MARKS UNDER THE AXIS ARE FOR. The trace says how high; the marks say how long. Eight
 * marks under the heat trace is eight hours of this house being over the line, which is the thing
 * a person acts on, and it is not legible from the shape of a curve — a brief spike and a long
 * plateau can reach the same height.
 */
PAI_LOAD.push(function () {
'use strict';

const { esc, dayFigure, strips } = window.K;

/* An issue has a day when any distance carries a trace. The node decides what a trace is; this
   only asks whether one arrived. */
const hasDay = d => (window.K.DIST || []).some(x => Array.isArray((d.series || {})[x])
  && (d.series[x] || []).some(v => v != null));

window.PAI.register({
  id: 'day', pack: 'core', stage: 'observe', title: 'The day this place just had', order: 12, learn: ['cards', 'raw', 'figure'],
  reads: ['/issues', '/issues/days'],
  render(ctx) {
    const { ISS, ORDER } = ctx;
    const drawn = ORDER.filter(k => ISS[k] && hasDay(ISS[k]));
    if (!drawn.length) {
      return `<p class="note" id="day-none" data-ref="matrix-grid">No issue here has an hourly `
        + `record yet, so there is no day to draw. The matrix above says what each one has.</p>`;
    }
    const silent = ORDER.filter(k => ISS[k] && !hasDay(ISS[k]));
    return `<div class="days" id="days" data-ref="matrix-grid">`
      + drawn.map(k => `<div class="dayone" id="day-${esc(k)}" data-ref="days">`
        + `<p class="k">${esc(ISS[k].name[LOC])}</p>`
        + dayFigure(k, ISS[k], { id: `day-fig-${esc(k)}`, ref: `day-${esc(k)}` })
        + strips(k, window.DAYS, { id: `strips-${esc(k)}`, ref: `day-${esc(k)}` }) + `</div>`).join('')
      + `</div>`
      + (silent.length ? `<p class="note" id="day-silent" data-ref="days">No hourly record for `
        + `${esc(silent.map(k => ISS[k].name[LOC]).join(' or '))} at any distance in this capture, `
        + `so neither is drawn here — the matrix above says what each of them does have.</p>` : '');
  },
  notes(ctx) {
    return [
      { id: 'days', label: 'Height, and how long',
        text: 'The trace says how high and the red ticks under it say how long. A brief spike and a long '
        + 'plateau can reach the same height, and only one of them is worth getting out of a chair for, '
        + 'so the hours over the line are counted in the line under the drawing. Point at an hour, or '
        + 'focus the drawing and use the arrow keys, to read every distance at that hour.' },
      { id: 'day-silent', label: 'A day with nothing to draw',
        text: 'A card appears here when there is a day to draw. An issue with no '
        + 'hourly record at any distance would be an empty box claiming to be a drawing, so it is '
        + 'named in a sentence instead and the matrix above carries what it does have. That is the '
        + 'difference between a gap in the record and a gap in the page.' },
    ];
  },
});

});

/* ================================================================= h/mods/sources.js ==== */
/* sources · core · observe
 *
 * What this page is built out of, counted in signs. Isotype's rule: more is more signs, never a
 * bigger sign, so a row you can count is a measurement and a bar you have to read off an axis is
 * not. Six rows, and every one of them is a different kind of knowing.
 *
 * THE COUNTS COME FROM /sensors, NOT FROM /issues. /issues publishes only what has a coordinate;
 * the sensor table carries every kind the node knows. And the filters are `kind === 'sensor'` and
 * `kind === 'model'` throughout — a `facility` is a workshop somebody could walk to, not a station,
 * and it must never enter a count of what this node reads. There is one on node #1 today.
 *
 * ORANGE IS THE SATELLITE'S, and only the satellite's — the layer's rule. Built and trees are the
 * two rows nothing on the ground here measured: they are Earth Engine's reading of a square
 * kilometre, so they carry it and nothing else does.
 *
 * TWO GRAINS, SAID OUT LOUD. Stations and models are one sign each, because each is a thing you
 * could point at. Built and trees are twentieths of the ground, because a percentage is not a
 * count of anything. Houses are one sign per 250, because 2,713 signs is not a row. Each row says
 * which it is rather than leaving a reader to infer it from the number.
 */
PAI_LOAD.push(function () {
'use strict';

const { esc, row, sign } = window.K;

/* A run of the same sign, which is the whole grammar of a unit row. */
const many = (id, n, cls = '', tip = '') => Array.from({ length: Math.max(0, n) }, () => sign(id, cls, tip)).join('');

/* A percentage as twentieths of the ground: filled for the share, hollow for the rest, so the row
   is countable both ways and the total is always the same width. */
const of20 = (pct, cls = '') => Array.from({ length: 20 }, (_, i) =>
  sign('cell', i < Math.round((pct || 0) / 5) ? `on ${cls}` : 'off',
    i < Math.round((pct || 0) / 5) ? 'One twentieth of the ground: covered' : 'One twentieth of the ground: not covered')).join('');

window.PAI.register({
  id: 'sources', pack: 'core', stage: 'observe', title: 'What this page is made of', order: 14, learn: ['custody'],
  reads: ['/sensors', '/issues', '/place/geojson'],
  needs: ['SENSORS'],
  render(ctx) {
    const all = window.SENSORS || [];
    const own = all.filter(s => s.local && s.kind === 'sensor').length;
    const ring = all.filter(s => !s.local && s.kind === 'sensor').length;
    const models = all.filter(s => s.kind === 'model').length;
    const land = ((ctx.ISS.land || {}).readouts) || [];
    const pick = m => land.find(r => r.metric === m);
    const built = pick('built_frac'), trees = pick('tree_frac');
    const plan = window.PLAN;
    const R = o => row({ ...o, ref: 'sources-rows', component: 'unitRow',
      cols: 'minmax(0,210px) minmax(0,1fr) auto' });
    const lab = (b, m) => `<span class="who"><b>${esc(b)}</b><span class="m">${esc(m)}</span></span>`;

    let html = `<div class="reads units" id="sources-rows" data-ref="sources">`
      + R({ id: 'src-own', left: lab('This house\u2019s own', 'one sign, one station'),
        signs: many('sensor', own, '', 'One of this house\u2019s own stations'),
        qty: [{ num: 'sources.own', value: String(own),
          cmp: `against ${own + ring} stations this node reads` }] })
      + R({ id: 'src-ring', left: lab('Other people\u2019s', 'one sign, one station'),
        signs: many('sensor', ring, 'faint', 'One station that belongs to somebody else'),
        qty: [{ num: 'sources.ring', value: String(ring),
          cmp: `against ${own + ring} stations this node reads` }] })
      + R({ id: 'src-models', left: lab('Models', 'one sign, one model'),
        signs: many('planet', models, '', 'One model: an estimate, never counted as a station'),
        qty: [{ num: 'sources.models', value: String(models),
          cmp: `against ${own + ring} stations \u2014 a model is not a station and is never counted `
            + `as one` }] });

    /* Built and trees are the satellite's, and they are twentieths rather than counts. */
    for (const [k, r] of [['built', built], ['trees', trees]]) {
      if (!r) continue;
      html += R({ id: `src-${k}`,
        left: lab(r.label[LOC] || r.label.en, 'twentieths of the ground'),
        signs: of20(r.value, 'sat'),
        qty: [{ num: `sources.${k}`, value: `${esc(String(r.value))}${esc(r.unit || '')}`,
          cmp: `${r.source} \u2014 nothing on the ground here measured it` }] });
    }

    /* The plan needs a token at every share level, so a page without one draws no house row and
       says which fact is missing rather than quietly rounding the sources down to five. */
    html += plan && plan.counts
      ? R({ id: 'src-houses', left: lab('Houses', 'one sign per 250'),
        signs: many('house', Math.round(plan.counts.buildings / 250), '', 'About 250 buildings'),
        qty: [{ num: 'sources.houses', value: String(plan.counts.buildings),
          cmp: `buildings on the plan within this kilometre, drawn one sign per 250` }] })
      : `<p class="note" id="src-houses" data-ref="sources-rows">The buildings on this kilometre `
        + `are on the plan, and the plan needs a token at every share level. Without one this row `
        + `is absent rather than guessed.</p>`;
    return html + `</div>`;
  },
  notes() {
    return [
      { id: 'sources-more-signs', label: 'More is more signs',
        text: 'More is more signs, never a bigger sign. A row you can count is '
        + 'a measurement; a bar you have to read off an axis is a picture of one. Three units are '
        + 'mixed here and each row says which it is: a station is one sign because you could point '
        + 'at it, the ground is twentieths because a percentage counts nothing, and houses are one '
        + 'sign per 250 because 2,713 signs is not a row.' },
      { id: 'src-models', label: 'A model is not a station',
        text: 'A model is not a station and is never counted as one. Nor is a '
        + 'workshop: the `make` pack stores fab labs in the same table, and every count on this '
        + 'page filters to stations and models so that a place somebody could walk to never '
        + 'arrives as a reading of the air.' },
      { id: 'src-built', label: 'Built, and trees',
        text: 'Built and trees are the only rows here that nothing on the ground '
        + 'measured \u2014 they are a satellite\u2019s reading of this square kilometre. They carry orange '
        + 'and nothing else on the page does, because that is what orange means in this layer.' },
    ];
  },
});

});

/* ================================================================= h/mods/sensors.js ==== */
/* What the stations read — the sensor list, filed by the cell each station falls in at the dial.
 *
 * Tomas asked for "the sensor lists in now, with sensor graphics and ability to select what to
 * show (air, temperature, humidity and other sensor variables), as well as having links to the
 * sources of sensor data." This is that, as one module of the air-quality pack.
 *
 * WHAT IT SHOWS. Every station in the fixture that carries a coordinate — fourteen — grouped by the
 * H3 cell it falls in AT THE RESOLUTION THE DIAL STANDS AT. Turn the dial to 4 and all fourteen
 * are one group; turn it to 9 and they are nine. Nothing else about a row changes when the dial
 * moves: a station's number is its own 15-minute mean whatever cell it is filed under, which is
 * the point of filing rather than averaging.
 *
 * WHAT IT DOES NOT DO. Average across stations (GET /issues publishes the street as one fenced
 * median, and this page shows the thing the median hides). Draw a trace it does not have: the
 * capture carries an hourly series for two stations, both PM2.5, so two rows have a trace and the
 * rest have one tick at the value, at now. Compare a number with a line drawn for a different
 * quantity: the Air line is the WHO 24-hour guideline for PM2.5 and is not a PM10 line; the Heat
 * line is for apparent temperature and no station here reports that directly. Where the line does
 * not apply the row says "no comparison yet" and why, at the same size, in the same place.
 *
 * Sources are links, because a reading somebody else took is only citable if the reader can go
 * and look: a Smart Citizen kit to its public page, a Bali Air Dispatch station to the
 * observatory, whose attribution line is required and printed under the list.
 */
PAI_LOAD.push(function () {
'use strict';

const { esc, fmt, age, cmpText, noLine, fig, localOf, PLOT_STYLE } = window.K;
const DEFAULT_VAR = 'pm25';

/* The variable the reader chose, or PM2.5. A key the fixture does not know is not an error to
 * draw a blank for; it is the default. */
const chosen = (ctx, metrics) => {
  const v = ctx.Q.get('var');
  return v && metrics[v] ? v : DEFAULT_VAR;
};

/* Every variable at least one station carries, in the order the fixture declares them. A selector
 * that offered battery voltage when nothing here reports it would be a control that does nothing. */
const carried = H => Object.keys(H.metrics).filter(v => H.sensors.some(s => s.read[v]));

/* THE CAP. Fourteen stations is a list nobody reads to the end; three is a neighbourhood.
 * STATIONS_SHOWN (Set up → System, default 3) says how many of OTHER PEOPLE'S stations the list
 * draws, nearest first. This node's own hardware is never counted against it and never hidden: a
 * house putting its own sensors behind a press would be concealing the one thing it certainly may
 * show.
 *
 * Nothing is dropped from the capture and nothing stops being collected — the setting that
 * collects fewer stations is BAD_RADIUS_KM, and that is a different decision taken in a different
 * box. The list also never goes quiet about what it left out: the line under it counts the stations
 * it is not drawing, says how far out they reach, and one press draws them all. A page that
 * shortened itself silently would be doing the very thing the fenced median was built not to do.
 *
 * `0` means no cap. An unreadable value means the default rather than an empty list: a typo in a
 * settings box must not be able to empty the neighbourhood off the page.
 */
const STATIONS_DEFAULT = 3;
const capOf = (settings) => {
  const raw = String(((settings || {}).STATIONS_SHOWN) ?? '').trim();
  if (raw === '') return STATIONS_DEFAULT;
  const n = Number(raw);
  if (!Number.isInteger(n) || n < 0) return STATIONS_DEFAULT;
  return n === 0 ? null : n;          // null = every station, no cap
};

/* Which stations the list draws, and which it is holding back. `?stations=all` lifts the cap and is
 * a query key like every other control here, so the dial's position and the chosen variable survive
 * the press. H.sensors arrives sorted by distance with the unknowns last (engine.py's _stations),
 * so "nearest first" is simply the order it came in — and unsited, where every km is null, that
 * is publication order, and the line below says so rather than calling it nearness. */
function shown(ctx) {
  const all = ctx.H.sensors;
  const mine = all.filter(s => s.local), theirs = all.filter(s => !s.local);
  const n = capOf(window.SETTINGS);
  const lifted = ctx.Q.get('stations') === 'all';
  if (lifted || n == null || theirs.length <= n) return { ids: null, hidden: [], theirs, n, lifted };
  return { ids: new Set([...mine, ...theirs.slice(0, n)].map(s => s.sensor_id)),
           hidden: theirs.slice(n), theirs, n, lifted };
}

/* The cap's own line: what is not on the page, and the press that puts it there. Nothing at all
 * when the node has fewer stations than the cap — a page need not announce a limit that never
 * bit. */
function moreLine(ctx, cap) {
  const capped = cap.n != null && cap.theirs.length > cap.n;
  if (!cap.hidden.length && !(cap.lifted && capped)) return '';
  const press = (q, t) => `<a href="${esc(ctx.qlink({ stations: q }))}">${esc(t)}</a>`;
  const head = `<p class="more" id="sensors-more" data-component="stationsCap" data-ref="sensors-list">`;
  if (!cap.hidden.length) {
    return head + `<b data-num="sensors.shown" data-cmp="every station in this capture that is not `
      + `this node's own">all ${cap.theirs.length}</b> <span>of the neighbourhood’s stations `
      + `are listed</span> ${press(null, `show ${cap.n}`)}</p>`;
  }
  const kms = cap.hidden.map(s => s.km).filter(k => k != null);
  return head + `<b data-num="sensors.hidden" data-cmp="of ${cap.theirs.length} stations in this `
    + `capture that are not this node’s own">${cap.hidden.length} more</b> <span>`
    + (kms.length
      ? `${esc(fmt(Math.min(...kms), 1))}–${esc(fmt(Math.max(...kms), 1))} km out`
      : `distance unknown, this node has no coordinates`)
    + ` · still read, still inside the median, not drawn here</span> ${press('all', 'show all')}</p>`;
}

/* The line a variable may be measured against: the issue's line, and only when the issue's own
 * metric IS this variable. Fifteen micrograms is a PM2.5 line; printing it under PM10 would be a
 * comparison nobody declared. */
function lineFor(ctx, v) {
  const m = ctx.H.metrics[v];
  const iss = m && m.issue ? ctx.ISS[m.issue] : null;
  if (!iss) return { line: null, cmp: `no comparison yet · no issue on this page claims ${m ? m.label : v}` };
  if (!iss.line) return { line: null, cmp: `no comparison yet · ${noLine(iss)}` };
  if (iss.metric && iss.metric !== v) {
    return { line: null, cmp: `no comparison yet · the ${iss.name.en} line, `
      + `${fmt(iss.line.value, m.dp)} ${iss.line.unit || iss.unit}, is drawn for ${iss.metric}, not ${m.label}` };
  }
  return { line: iss.line,
    cmp: `${cmpText({ mode: 'line', line: iss.line, unit: m.unit, dp: m.dp }).text} · ${iss.line.source}` };
}

/* One value scale for every graphic in the section, so a tick in one row and a trace in another
 * are read against the same height. The node's values set the box; the line is in it when it
 * applies, so the headroom under the line is visible rather than implied. */
function scaleFor(H, v, line) {
  const vals = [];
  for (const s of H.sensors) {
    if (s.read[v]) vals.push(s.read[v].value);
    for (const b of s.series[v] || []) vals.push(b.min, b.max);
  }
  if (line) vals.push(line.value);
  /* A bucket with no reading has a null min and max, and Math.min counts a null as 0. */
  const fin = vals.filter(Number.isFinite);
  if (!fin.length) return null;
  let lo = Math.min(...fin), hi = Math.max(...fin);
  const pad = (hi - lo) * 0.08 || 1;
  /* A concentration does not go below zero, so the scale must not either: a box that opened at
   * -1.0 µg/m³ was drawing headroom under a floor. Temperature may. */
  lo = lo >= 0 ? Math.max(0, lo - pad) : lo - pad;
  hi += pad;
  return { lo, hi };
}

/* A station's own day, inside its row (docs/SPEC_dashboard_figures.md §4.4): the hourly mean as a line and the hour's
 * spread as a band, on the one scale every row of the section shares (scaleFor), the issue's line where it applies,
 * and one tick at now for a station with no hourly series. An hour the station did not report is a gap: the series
 * lists only the hours it has, so the grid below puts a null in every hour between them. Pointing at it says that
 * hour in the row's own words. */
function spark(s, v, m, sc, line, id, idle) {
  const ser = ((s.series || {})[v] || []).filter(b => b && b.t);
  const r15 = (s.read || {})[v];
  const T = ser.map(b => Date.parse(b.t));
  const grid = [];
  /* `iso` is the hour's own bucket, or for an hour the station did not report, the bucket before it: its offset names
     the empty hour. */
  for (let t = T[0], i = 0; ser.length && t <= T[T.length - 1]; t += 3600e3) {
    const b = T[i] === t ? ser[i++] : null;
    grid.push({ t: new Date(t), iso: ser[Math.max(0, i - 1)].t, mean: b ? b.mean : null, min: b ? b.min : null,
      max: b ? b.max : null });
  }
  const draw = (el, W) => {
    const w = Math.min(W, 320), tick = (sc.hi - sc.lo) * 0.08;
    const svg = Plot.plot({
      width: w, height: 48, marginLeft: 2, marginRight: 2, marginTop: 4, marginBottom: 4, style: PLOT_STYLE,
      x: grid.length ? { type: 'time', domain: [grid[0].t, grid[grid.length - 1].t], axis: null } : { domain: [0, 1], axis: null },
      y: { domain: [sc.lo, sc.hi], axis: null },
      marks: [
        line ? Plot.ruleY([line.value], { stroke: 'var(--signal-worse)', strokeDasharray: '3 5' }) : null,
        grid.length ? Plot.areaY(grid, { x: 't', y1: 'min', y2: 'max', fill: 'var(--ink)', fillOpacity: 0.1 }) : null,
        grid.length ? Plot.lineY(grid, { x: 't', y: 'mean', stroke: 'var(--ink)', strokeWidth: 1.5 }) : null,
        !grid.length && r15 ? Plot.ruleX([1], { y1: r15.value - tick, y2: r15.value + tick, stroke: 'var(--ink)', strokeWidth: 2 }) : null,
        grid.length ? Plot.ruleX(grid, Plot.pointerX({ x: 't', stroke: 'var(--ink)', strokeOpacity: 0.5 })) : null,
      ].filter(Boolean),
    });
    el.append(svg);
    const read = document.getElementById(`${id}-read`);
    svg.addEventListener('input', () => {
      const b = svg.value;
      if (!read) return;
      const at = b && localOf(b.iso, +b.t).hhmm;
      read.innerHTML = !b ? idle : b.mean == null ? `${esc(at)} nothing recorded`
        : `${esc(at)} ${esc(fmt(b.mean, m.dp))} (${esc(fmt(b.min, m.dp))} to `
          + `${esc(fmt(b.max, m.dp))}) ${esc(m.unit)}`;
    });
  };
  return fig(id, draw, { ref: `st-${s.sensor_id}`, component: 'stationDrawing',
    label: `${s.name || s.sensor_id}, ${m.label}: ${ser.length ? `${ser.length} hourly means` : 'one 15-minute mean at now'}` });
}

function station(ctx, s, v, m, sc, L, ref) {
  const r = s.read[v];
  /* PORTED: the drawing's stations carried `label`; GET /issues publishes the same thing as
     `source`, read off the sensor id the way app/sources.py assigns it. */
  const src = s.url
    ? `<a href="${esc(s.url)}" target="_blank" rel="noopener">${esc(s.source)}</a>` : esc(s.source);
  const silent = r && r.silent_minutes > 60
    ? ` · <span class="silent">silent</span> ${esc(age(r.silent_minutes))}` : '';
  const ser = s.series[v];
  const hi = ser && ser.length ? Math.max(...ser.map(b => b.max).filter(x => x != null)) : null;
  const said = ser && ser.length ? `opened the day at ${esc(fmt(ser[0].mean, m.dp))}, `
    + `closed at ${esc(fmt(ser[ser.length - 1].mean, m.dp))} ${esc(m.unit)} · high ${esc(fmt(hi, m.dp))}` : '';
  const alt = said ? `<span class="alt" id="spark-${esc(s.sensor_id)}-${esc(v)}-read">${said}</span>` : '';
  /* km is null when the node has no coordinates: the engine publishes unknown rather than a distance
     from (0, 0). Say unknown — a neighbour's distance from the Gulf of Guinea is not a fact. */
  const inEvent = (ctx.EVROOMS || new Set()).has(s.name);
  const meta = `${inEvent ? 'in the open event · ' : ''}${s.local ? 'this house' : s.km == null ? 'distance unknown'
    : `${esc(String(s.km))} km`} · ${s.indoor ? 'indoor' : 'outdoor'}`
    + ` · ${src}${silent}`;
  const key = `${m.issue || v}.${s.sensor_id}.${v}`;
  const crossed = r && L.line && r.value > L.line.value;
  const cmp = !r ? (Object.keys(s.read).length ? 'does not measure this' : 'nothing read in this capture')
    : L.cmp;
  return `<div class="row station${s.local ? ' mine' : ''}${r ? '' : ' quiet'}" data-kind="row"`
    + ` data-component="station" id="st-${esc(s.sensor_id)}" data-ref="${esc(ref)}">`
    + `<span class="who"><b>${esc(s.name || s.sensor_id)}</b><span class="m">${meta}</span>${alt}</span>`
    + `<span class="pic">${r && sc ? spark(s, v, m, sc, L.line, `spark-${s.sensor_id}-${v}`, said) : ''}</span>`
    + `<span class="qty">${r
      ? `<span class="num${crossed ? ' crossed' : ''}" data-num="${esc(key)}" data-cmp="${esc(cmp)}">`
        + `${esc(fmt(r.value, m.dp))}</span><small>${esc(m.unit)}</small>`
      : `<span class="none">—</span>`}</span>`
    + `<span class="cmp">${esc(cmp)}</span></div>`;
}

/* Stations by the cell they fall in at the dial's resolution: this node's own cell first, then by
 * distance. Two stations in one cell are two rows — the whole reason to draw cells is that they
 * are not one number. */
function groups(ctx, ids) {
  const by = new Map();
  for (const s of ctx.H.sensors) {
    /* '' is a station outside the two steps this node published at this resolution — not an error
       and not a cell, and the header for that group says so rather than printing a blank id. */
    const c = s.chain[ctx.RES] || '';
    if (!by.has(c)) by.set(c, []);
    by.get(c).push(s);
  }
  /* The rooms of an open event lead their cell (docs/SPEC_dashboard_figures.md §4.4): they are why a reader is here. */
  const rooms = ctx.EVROOMS = new Set((((ctx.S.issues || {}).events || {}).open || []).flatMap(e => e.rooms || []));
  const own = ctx.N.chain[ctx.RES];
  /* Unsited, every km is null: the groups keep the order the node sent and the header says the
     distance is not known rather than ordering the neighbourhood by a number that is not one. */
  const kms = ss => ss.map(s => s.km).filter(k => k != null);
  /* `n` is how many stations this node knows of in the cell; `ss` is how many the cap lets the list
     draw. The header prints both when they differ, so a shortened cell says that it is short. The
     distance range stays the whole cell's: that is a fact about the cell, not about how much of it
     is on the page. */
  return [...by.entries()].map(([cell, ss]) => ({
    cell, n: ss.length, own: cell === own,
    ss: ss.slice().sort((a, b) => (rooms.has(b.name) - rooms.has(a.name)) || (a.km ?? Infinity) - (b.km ?? Infinity))
      .filter(s => !ids || ids.has(s.sensor_id)),
    km: kms(ss).length ? Math.min(...kms(ss)) : null,
    kmMax: kms(ss).length ? Math.max(...kms(ss)) : null,
  })).filter(g => g.ss.length)
    .sort((a, b) => (a.own ? -1 : b.own ? 1 : 0) || (a.km ?? Infinity) - (b.km ?? Infinity));
}

const KM = g => g.own ? 'this node’s own cell'
  : g.km == null ? 'distance unknown — this node has no coordinates'
  : g.km === g.kmMax ? `${g.km} km` : `${g.km}–${g.kmMax} km`;
const CELLHEAD = (ctx, g) => g.cell ? ctx.KH.address(g.cell, ctx.RES)
  : `<span class="addr mono">outside the ${ctx.N.steps} steps this node published at resolution `
    + `${ctx.RES}</span>`;

/* The archive of silence (docs/SPEC_dashboard_figures.md §4.4, after Bali Air Dispatch). A station heard in the last
 * 30 days and not in the last day keeps a line here, with when it was last heard; the node has already left out a
 * relay of a kit that still reports. A node older than v0.79 sends no stations_silent, and this says nothing. */
function silentFold(ctx) {
  const st = (ctx.S.issues || {}).stations_silent;
  const gone = ctx.H.silent || [];
  if (!st) return '';
  if (!st.read) {
    return `<p class="cap" id="sensors-silent" data-ref="sensors-list">This node could not say which stations `
      + `stopped reporting in the last ${esc(String(st.within_days))} days.</p>`;
  }
  if (!gone.length) {
    return `<p class="cap" id="sensors-silent" data-ref="sensors-list">No station this node heard in the last `
      + `${esc(String(st.within_days))} days has gone quiet.</p>`;
  }
  return `<details class="silentfold" id="sensors-silent" data-component="silentStations" data-ref="sensors-list">`
    + `<summary><b data-num="sensors.silent" data-cmp="stations heard in the last ${esc(String(st.within_days))} days `
    + `and not in the last day">${gone.length}</b> no longer heard</summary>`
    + gone.map(s => { const lh = localOf(s.last_heard);
      return `<p class="row silent" data-kind="row" data-component="silentStation" id="st-gone-${esc(s.sensor_id)}"`
      + ` data-ref="sensors-silent"><span class="who"><b>${esc(s.name || s.sensor_id)}</b><span class="m">`
      + `${s.km == null ? 'distance unknown' : `${esc(String(s.km))} km`} · ${s.indoor ? 'indoor' : 'outdoor'} · `
      + `${s.url ? `<a href="${esc(s.url)}" target="_blank" rel="noopener">${esc(s.source)}</a>` : esc(s.source)}`
      + `</span></span><span class="said">${lh.hour != null
        ? `last heard ${esc(lh.day)} ${esc(lh.hhmm)}` : 'last heard: not known'}</span></p>`; }).join('')
    + `</details>`;
}


window.PAI.register({
  id: 'sensors', pack: 'air-quality', stage: 'observe', title: 'What the stations read', order: 20,
  reads: ['/issues', '/settings'],
  learn: ['counted'],
  needs: ['H3.sensors'],

  controls(ctx) {
    const v = chosen(ctx, ctx.H.metrics);
    return `<div class="ctlstrip" id="sensors-vars" data-component="varStrip" data-ref="sensors-list"`
      + ` role="group" aria-label="variable shown, ${esc(ctx.H.metrics[v].label)}">`
      + carried(ctx.H).map(k => `<a class="${k === v ? 'on' : ''}" href="${esc(ctx.qlink({ var: k }))}">`
        + `${esc(ctx.H.metrics[k].label)}</a>`).join('') + `</div>`;
  },

  render(ctx) {
    const H = ctx.H;
    if (!H.sensors.length) {
      return `<p class="note" id="sensors-list" data-ref="sensors">No station with a coordinate `
        + `in this capture.</p>`;
    }
    const v = chosen(ctx, H.metrics), m = H.metrics[v];
    const L = lineFor(ctx, v);
    const sc = scaleFor(H, v, L.line);
    const cap = shown(ctx);
    const gs = groups(ctx, cap.ids);
    let html = `<div class="stations" id="sensors-list">`;
    for (const g of gs) {
      const id = `sensors-cell-${g.cell || 'outside'}`;
      html += `<div class="cellhead" id="${id}" data-component="cellGroup" data-ref="rail">`
        + CELLHEAD(ctx, g)
        + `<span class="n"><b data-num="sensors.cell.${esc(g.cell || 'outside')}.n" data-cmp="against `
        + `${H.sensors.length} stations with a coordinate in this capture">${g.ss.length}`
        + `${g.n > g.ss.length ? ` of ${g.n}` : ''}</b> `
        + `${g.n === 1 ? 'station' : 'stations'} · ${KM(g)}</span></div>`
        + g.ss.map(s => station(ctx, s, v, m, sc, L, id)).join('');
    }
    html += moreLine(ctx, cap) + silentFold(ctx) + `</div>`;
    const carry = H.sensors.filter(s => s.read[v]).length;
    const traced = H.sensors.filter(s => (s.series[v] || []).length).length;
    const attrib = [...new Set(H.sensors.map(s => s.attribution).filter(Boolean))];
    html += `<p class="cap" id="sensors-cap" data-ref="sensors-list">`
      + `<span data-num="sensors.carry" data-cmp="against ${H.sensors.length} stations with a `
      + `coordinate in this capture">${carry} of ${H.sensors.length}</span> stations carry `
      + `${esc(m.label)} · <span data-num="sensors.traced" data-cmp="against ${carry} stations that `
      + `carry ${esc(m.label)}">${traced}</span> ${traced === 1 ? 'has' : 'have'} an hourly series; the `
      + `rest show one 15-minute mean as a tick at now — no hourly series in this capture`
      + (sc ? ` · one scale for every graphic, ${esc(fmt(sc.lo, m.dp))} to ${esc(fmt(sc.hi, m.dp))} `
        + `${esc(m.unit)}${L.line ? `, the line dashed at ${esc(fmt(L.line.value, m.dp))}` : ''}` : '')
      + ` · sources: ${attrib.map(esc).join(' · ')}</p>`;
    return html;
  },

  notes(ctx) {
    const H = ctx.H, v = chosen(ctx, H.metrics), m = H.metrics[v];
    const gt = r => H.grain_table.find(g => g.res === r) || {};
    const traced = H.sensors.filter(s => Object.keys(s.series).length);
    const quiet = H.sensors.filter(s => !Object.keys(s.read).length);
    const oldest = Math.max(0, ...H.sensors.flatMap(s => Object.values(s.read).map(r => r.silent_minutes || 0)));
    const air = ctx.ISS.air, heat = ctx.ISS.heat;
    return [
      { id: 'sensors-note-station', label: 'One station’s own mean',
        text: ctx.KN.NAV_HONEST.perStation() },
      { id: 'sensors-note-series', label: 'Which stations carry an hour',
        text: `${traced.length} of the ${H.sensors.length} stations carry `
        + `an hourly series in this capture — ${traced.map(s => `${s.name} (${s.local ? 'this house'
          : `${s.km} km`}, ${Object.keys(s.series).map(k => H.metrics[k].label).join(', ')})`).join(' and ')}`
        + ` — so those rows have a trace with its min–max band and the others have one tick at the `
        + `15-minute mean, drawn at now. No trace was drawn where none was recorded.` },
      { id: 'sensors-note-dial', label: 'The groups follow the ladder',
        text: `The groups follow the ladder: at resolution 4 all `
        + `${H.sensors.length} stations are in ${gt(4).occupied} cell, at 9 they are in `
        + `${gt(9).occupied}, and this node’s own ${gt(9).mine_in_my_cell} share one cell at every `
        + `resolution because they carry one coordinate. Regrouping changes which header a row sits `
        + `under and nothing in the row: a station’s number is its own, not its cell’s.` },
      { id: 'sensors-note-line', label: 'The line, and what it covers',
        text: `${air.name.en}’s line, ${fmt(air.line ? air.line.value : null,
        H.metrics.pm25.dp)} ${air.unit}, is ${air.line ? air.line.source : 'not declared'} and is drawn `
        + `against PM2.5 only. ${heat.name.en}’s line${heat.line ? `, ${fmt(heat.line.value, 1)} `
          + `${heat.line.unit || heat.unit}, is for ${heat.metric}, which no station here reports `
          + `directly` : ' is not declared'}. Every other variable prints “no comparison yet” with the `
        + `reason, at the same size, in the same place — the number is never left to look compared.` },
      { id: 'sensors-note-sources', label: 'Where each station links out',
        text: `Smart Citizen kits link to their public page on `
        + `smartcitizen.me. Stations that came through Bali Air Dispatch link to baliairdispatch.com, `
        + `whose attribution line — “Bali Air Dispatch, baliairdispatch.com” — is required and printed `
        + `under the list; each of those rows also names the network the station is on. `
        + (quiet.length ? `${quiet.length} of them (${quiet.map(s => s.name).join(', ')}) carry no `
          + `15-minute mean in this capture and are listed with a dash. ` : '')
        + `A station whose last reading is more than 60 minutes old is marked with the word “silent” `
        + `and the age — a word, not a colour. ${oldest > 60 ? '' : `None is in this capture; the oldest `
          + `reading is ${oldest} min.`}` },
      { id: 'sensors-note-mesh', label: 'The device with no cell',
        text: `The Meshtastic device in this house`
        + `${H.radio && H.radio.mesh_sensor ? ` (${H.radio.mesh_sensor.name})` : ''} carries no `
        + `coordinate, so it falls in no cell and is not in this list. It appears under the radio.` },
    ];
  },

  /* The wall: this node's own stations and the chosen variable, in the column grammar wall.js lays
   * its own numbers in, so the three sit on one line with them and read at three metres. */
  wall(ctx) {
    const H = ctx.H, v = chosen(ctx, H.metrics), m = H.metrics[v];
    const L = lineFor(ctx, v);
    return H.sensors.filter(s => s.local).map(s => {
      const r = s.read[v];
      return `<div class="col" id="wall-st-${esc(s.sensor_id)}"><h3>${esc(s.name || s.sensor_id)}</h3>`
        + `<div class="line">` + (r
          ? `<span class="num${L.line && r.value > L.line.value ? ' crossed' : ''}"`
            + ` data-num="${esc(`${m.issue || v}.${s.sensor_id}.${v}`)}" data-cmp="${esc(L.cmp)}">`
            + `${esc(fmt(r.value, m.dp))}</span><small>${esc(m.unit)} · ${esc(m.label)}, this house</small>`
          : `<span class="none">—</span><small>${esc(m.label)}: nothing read</small>`)
        + `</div></div>`;
    }).join('');
  },
});

/* PORTED: this module's CSS is in dashboard.css, under a banner naming this file. */

});

/* ================================================================= h/mods/satellite.js ==== */
/* satellite · earth · observe
 *
 * Four real Sentinel-2 passes of this place — about 3 km across, 10 m a pixel, 2016 to 2025 — and
 * the one thing the satellite has said about it that the map did not already know: 1,874 buildings.
 *
 * Decision 2 of 8 September governs the frames. They are brightness matched across years so that
 * the only thing differing between them is structure; they say so beside the year and carry a
 * permanent provenance word; nothing in green, red, blue or orange sits on the photograph. The
 * `land` issue itself has no reading in this capture, and the section says that rather than
 * implying a year-over-year number the earth pack has not produced here.
 */
PAI_LOAD.push(function () {
'use strict';

const { esc, fmt, pill, row } = window.K;
const { H, km2 } = window.KH;
const { map, caption } = window.KMAP;

/* PORTED, and this is the one section that could not be carried over as drawn. The prototype loaded
 * four Sentinel PNGs out of the design repository. A node serves nothing but the names in
 * app/main.py's COMPANIONS allowlist, so those files do not exist here — and the node's own earth
 * pack is the more honest source anyway: GET /earth names the years it has fetched, and
 * GET /earth/frame.png?year= serves one. They are annual medians from somebody else's cluster, so
 * they are `partial`, which is the word the route's own docstring uses. A node that has fetched
 * none says so in one line rather than showing four broken frames. */
const IMAGERY = () => ((window.EARTH || {}).imagery || {});
/* THE YEARS, AS ONE FRAME AT A TIME.
 *
 * Both records used to be a column of large stills — every Sentinel year at full width, and every
 * AlphaEarth year under it, because nothing styled .frames and so nothing hid the ones that were
 * not current. Historical was a very long scroll of near-identical squares, which is the worst way
 * to see what changed between them: the eye cannot hold two pictures a screen apart. Asked for
 * 18 September: keep the animation, drop the sequence.
 *
 * The controls were already in the markup and had been dead since the Phase 2 rewrite — Play, the
 * slider and the mode button were rendered and nothing listened to any of them. wireSat() below is
 * that wiring, restored from v0.53 against the markup this page actually draws.
 *
 * Hooked by `data-sat=` and never by id, because this component is drawn twice on the same page.
 */
function player(o) {
  const last = o.years[o.years.length - 1];
  return `<figure class="satplay" data-component="${esc(o.component)}" id="${esc(o.id)}"`
    + ` data-ref="${esc(o.ref)}" data-years="${o.years.join(',')}">`
    + `<div class="frames">` + o.years.map((y, i) =>
      `<img src="${o.url(y)}" data-sat="frame" data-i="${i}"${y === last ? ' class="on"' : ''}`
      + `${i === o.years.length - 1 ? '' : ' loading="lazy"'}`
      /* A frame that 404s must not delete its own figure: the caption still counts it, and a count
         with nothing under it is presence fabricated from absence. */
      + ` onerror="this.dataset.gone=1"`
      + ` alt="${esc(o.alt(y))}">`).join('') + `</div>`
    + `<div class="satctl">`
    + `<button type="button" data-sat="play" aria-pressed="false">Play</button>`
    + `<input type="range" data-sat="slider" min="0" max="${o.years.length - 1}"`
    + ` value="${o.years.length - 1}" aria-label="year">`
    + `<span class="yr" data-sat="label">${last}</span>`
    + (o.pill || '') + `</div>`
    + `<figcaption class="cap">${o.cap}</figcaption></figure>`;
}

const frameUrl = y => `/earth/frame.png?source=sentinel&year=${y}`;
const yearUrl = y => `/earth/year.png?year=${y}`;
const YEARS = () => (IMAGERY().sentinel || []);
const P = () => window.PLAN;

/* PORTED, and added back. Direction H's drawing showed somebody else's imagery and nothing of this
 * node's OWN satellite record — the AlphaEarth layer the earth pack keeps, a model's 64-number
 * description of every 10 m pixel flattened to one number and drawn in grey. GET /earth/year.png
 * serves one year of it and GET /earth names the years it has. app/main.py's own docstring is
 * emphatic that a page must never let a reader take one for the other, so they are two figures with
 * two provenance words, and this one says in its caption that it is a rendering of a model.
 *
 * The controls are hooked by data-sat=, never by ids: the same component is drawn more than once on
 * a page and an id cannot be. */
function record(ctx) {
  const years = (window.EARTH || {}).frames || [];
  const hint = (window.EARTH || {}).hint || '';
  if (!years.length) {
    return `<figure class="satown" data-component="satellite" id="sat-own" data-ref="sat-map">`
      + `<figcaption class="cap">This node has no record of its own yet: the earth pack fetches the `
      + `embeddings on command — <code>planetai run earth fetch</code>`
      + `${hint ? ` · ${esc(hint)}` : ''}</figcaption></figure>`;
  }
  /* The Years/change mode button is not carried over. v0.53's mode toggled to a "what changed"
     frame that this node does not compute, so it was a control with nothing behind it — and a
     control that does nothing is worse than no control. */
  return player({
    id: 'sat-own', component: 'satellite', ref: 'sat-map', years,
    url: yearUrl,
    alt: y => `this node's own AlphaEarth layer for ${y}, drawn in grey: a model's description of `
      + `every 10 m pixel, not a photograph`,
    pill: pill('model', 'a model’s description of every 10 m pixel, drawn in grey'),
    cap: `This node’s own AlphaEarth record, ${years.length} `
      + `${years.length === 1 ? 'year' : 'years'} · a rendering of a model, not a photograph · `
      + `<code>planetai run earth fetch</code> adds a year`,
  });
}

window.PAI.register({
  id: 'satellite', pack: 'earth', stage: 'observe', order: 30, learn: ['earth'],
  reads: ['/earth', '/issues', '/place/geojson'],
  /* Historical's short answer. The pack says the satellite loop leads this view, so it is what a
     reader gets when they ask for the short version of it — not Now's four sentences. */
  level: 'simple',
  title: 'What the satellite says',
  /* IT NEEDS THE SATELLITE, NOT THE PLAN.
   *
   * This said `['PLAN', 'H3.claims']`, and the plan comes from GET /place/geojson, which needs a
   * token at EVERY sharing level — it carries the shapes of the buildings and the node's exact
   * coordinates, and that is deliberate. So on any browser that has not unlocked Set up, window.PLAN
   * is null, this section's needs were unmet, and the whole of Historical's satellite view printed
   * "the earth pack has nothing here yet: PLAN is not on this node".
   *
   * Which was false. Node #1 has nine years of embeddings, four Sentinel passes and 589 MB on disk,
   * and every one of those images answers over the LAN. What needed the plan was ONE part of this
   * section — the claim about buildings a satellite pass found that OpenStreetMap does not have,
   * which compares against the plan's own count. A need declared for the section took out the view.
   *
   * Reported by Tomas from node #1 at v0.71: the satellite data is not loading. */
  needs: ['EARTH'],
  render(ctx) {
    const land = ctx.ISS.land;
    const region = H.claims.find(c => c.key === 'region');
    const res = Math.max(ctx.RES, 8);
    const years = YEARS();
    const frames = years.map(y =>
      `<figure class="frame" data-component="satFrame" id="sat-${y}" data-ref="sat-map">`
      /* A frame that 404s must not delete its own figure: the caption two lines down still counts
         it, and a count with nothing under it is presence fabricated from absence. The figure stays
         and says what is missing. */
      + `<img src="${frameUrl(y)}" loading="lazy"`
      + ` onerror="this.hidden=true;this.parentNode.classList.add('missing')"`
      + ` alt="Sentinel-2 annual median, ${y}, the square this node keeps; brightness matched `
      + `across the years so only structure differs between them">`
      + `<p class="note miss">This node no longer has the ${y} pass on disk.</p>`
      + `<figcaption><span class="yr">${y}</span>${pill('partial', 'an annual median from '
        + 'somebody else’s cluster, not a pass this node made')}</figcaption></figure>`).join('');
    /* The Sentinel years stay a strip, by Tomas's call on 18 September: four squares side by side
       are compared without moving the eye, which is what a strip is for and what a player takes
       away. The record below it is the one that animates — it had no CSS to hide the frames that
       were not current, so it stacked every year at full width, and that was the wall. */
    const strip = years.length
      ? `<div class="satstrip" id="sat-strip" data-component="satStrip" data-ref="sat-map">`
        + frames + `</div>`
        + `<p class="cap">Sentinel-2 annual medians · ${years.length} `
        + `${years.length === 1 ? 'year' : 'years'} · ${esc((IMAGERY().credit || []).join(' '))}</p>`
      : `<p class="note" id="sat-strip" data-component="satStrip" data-ref="sat-map">This node has `
        + `no satellite passes on disk yet, so there are none to show. `
        + `${esc((window.EARTH || {}).hint || 'The earth pack fetches them on command.')}</p>`;
    /* The plan is token-only, so this half may be absent on a page the rest of which is fine. It
       says which token and where to put it, rather than leaving a hole: a reader who can see nine
       years of satellite above this line has not been refused the satellite. */
    if (!P()) {
      return strip + record(ctx)
        + `<p class="note" data-component="absent" id="sat-claim-absent" data-ref="sat-strip">`
        + `The buildings only the satellite knows are drawn against the plan of this place, and the `
        + `plan needs a token: <code>GET /place/geojson</code> carries the shape of every building `
        + `here and this node's exact position, so it asks for one at every sharing level. Put the `
        + `admin token into this browser under Set up and it draws. Everything above this line is `
        + `the satellite record itself and needs no token.</p>`;
    }
    return strip + record(ctx)
      + `<div class="two-up">`
      + `<figure class="gridwrap mapwrap" id="sat-map" data-component="satMap" data-ref="sat-strip">`
      + map(res, { satOnly: true,
        label: `the ${P().counts.sat} buildings one satellite pass found that OpenStreetMap does not `
          + `have, over the outlines of the ones it does` })
      + `<div class="gridkey"><span><i class="sat-only"></i>only the satellite knows it is there`
      + `</span><span><i class="none"></i>on the map already</span></div>`
      + `<figcaption class="cap">${esc(caption(res))}</figcaption></figure>`
      + `<div class="reads">`
      + row({ id: 'sat-count', component: 'satCount', ref: 'sat-map',
        cols: 'minmax(0,210px) minmax(0,1fr) auto',
        left: `<span class="who"><b>Buildings only the satellite knows</b>`
          + `<span class="m">confidence 0.3 to 1.0</span></span>`,
        line: `Against ${P().counts.buildings.toLocaleString()} OpenStreetMap buildings on the same `
          + `ground.`,
        qty: [{ num: 'claim.sat.buildings', value: P().counts.sat.toLocaleString(),
          cmp: `against ${P().counts.buildings.toLocaleString()} the map already had` }] })
      + row({ id: 'sat-square', component: 'satSquare', ref: 'sat-map',
        cols: 'minmax(0,210px) minmax(0,1fr) auto',
        left: `<span class="who"><b>The square this node keeps</b>`
          + `<span class="m">EARTH_RADIUS_M=5000, 10 m a pixel</span></span>`,
        line: `packs/earth/pack.yaml · fetched once on command, compared with arithmetic.`,
        qty: [{ num: 'claim.region.km2', value: `${region.area_km2} km²`,
          cmp: `against the ${H.claims[0].area_km2} km² the widest source here covers` }] })
      /* `native` is null when the claim has no footprint: geometry.py's _claim() publishes an empty
         covering for a radius of zero or less rather than inventing a metre nobody declared, and
         EARTH_RADIUS_M=0 is a keeper's setting away. Dereferencing it turned this whole section into
         its "did not render" line, so the row says what the setting says instead. */
      + (region.native
        ? row({ id: 'sat-grain', component: 'satGrain', ref: 'sat-map',
          cols: 'minmax(0,210px) minmax(0,1fr) auto',
          left: `<span class="who"><b>At the resolution its own data has</b>`
            + `<span class="m">resolution ${region.native.res}</span></span>`,
          line: `${region.native.cells.toLocaleString()} cells; compactCells leaves `
            + `${region.native.compact.toLocaleString()} covering the same ground exactly.`,
          qty: [{ num: 'claim.region.saving', value: `${region.native.saving}×`,
            cmp: `smaller, for the same ground` }] })
        : `<p class="note" id="sat-grain" data-component="satGrain" data-ref="sat-map">`
          + `${esc(region.declared)} covers no ground, so there is no covering to compact and no `
          + `resolution to state.</p>`)
      /* `land_change_yoy` is a column in the observations table, not a thing to say to a household,
         and with no value it printed "land_change_yoy — %". The issue has a name and the node writes
         a source sentence for the figure; both are used instead, and a missing value says it is
         missing rather than drawing a dash after a column name. */
      + `<p class="cap">${esc((() => {
        if (land.state === 'none') return `land: ${land.reason_text[ctx.LOC]} in this capture`;
        const v = (land.stack.room || {}).value;
        const src = ((land.provenance || []).find(e => e.value === v) || {}).source || '';
        if (v == null) return `${land.name[ctx.LOC]}: this node has the square but no year-on-year `
          + `figure for it in this capture`;
        return `${land.name[ctx.LOC]} ${fmt(v, land.dp)} ${land.unit || ''}`
          + `${src ? ` \u2014 ${src}` : ''}`;
      })())}</p>`
      + `</div></div>`;
  },
  notes(ctx) {
    const region = H.claims.find(c => c.key === 'region');
    return [
      { id: 'sat-matched', label: 'Brightness matched across years',
        text: 'The frames are brightness matched across years. Measured on '
        + 'the passes as delivered, mean luminance ran 81, 116, 94, 108 and greenness flipped sign on '
        + '2019 — season and haze, not change — so a loop of the raw frames reads as something '
        + 'happening that did not. After matching every channel to 2016 the only thing that differs '
        + 'between frames is structure. That changes pixel values, which is why the page says so '
        + 'beside the year rather than passing the frames off as raw medians.' },
      { id: 'sat-colour', label: 'No colour on the photograph',
        text: 'Nothing in green, red, blue or orange sits on the photograph. The '
        + 'photograph is a ground, never a backdrop for coloured marks — on this page green means a '
        + 'loop closed, red means a signal got worse and orange means what only the satellite knows, '
        + 'and a green-and-brown image would borrow all three.' },
      { id: 'sat-orange', label: 'What orange means',
        text: `Orange means one thing on every page here: what only the satellite `
        + `knows. ${P().counts.sat.toLocaleString()} buildings on this ground are in a satellite pass `
        + `and not in OpenStreetMap, each with the confidence the pass gave it, drawn over the `
        + `hairline outlines of the ${P().counts.buildings.toLocaleString()} the map already had.` },
      { id: 'sat-compaction', label: 'Compacting the covering',
        text: region.native
        ? `EARTH_RADIUS_M=5000 at 10 m a pixel is resolution `
          + `${region.native.res}. polygonToCells on that square returns `
          + `${region.native.cells.toLocaleString()} cells and compactCells returns `
          + `${region.native.compact.toLocaleString()} covering exactly the same ground — `
          + `${region.native.saving} times smaller. This is the only place in three rounds where an H3 `
          + 'operation does something the node could not already do by hand, and it is the answer to '
          + 'how a covering this fine is ever published.'
        : `${region.declared} declares no ground, so this node has no covering of the square to `
          + 'compact and nothing to say about what compaction saves here.' },
      { id: 'sat-land', label: 'The land figure',
        text: ctx.ISS.land.state === 'none'
        ? 'The earth pack has no reading in this capture. What is in the section is what the '
          + 'satellite has already said about this place — the passes, and the buildings it found — '
          + 'and not a year-over-year number it has not produced here.'
        : 'The land_change_yoy figure is the earth pack’s own, computed on this node from the '
          + 'embeddings it keeps.' },
    ];
  },
});

});

/* ================================================================= h/mods/reach.js ==== */
/* reach · core · observe (Historical)
 *
 * How far back this node's own record goes, per kind of source. Three numbers, from the oldest
 * hourly bucket each kind has — `GET /reach`, added in v0.68, which is gap E of the data contract.
 *
 * WHY IT BELONGS TO HISTORICAL AND NOT TO NOW. Every other panel here says what is true now or what
 * changed; this says how much past there is to ask about at all. A reader who wants a year of
 * anything needs to know that on this node the sensors hold twenty days and the satellite holds ten
 * years, because the second question — "show me a year" — has a different answer for each.
 *
 * TWO THINGS PROMPT 4 ASKS FOR AND THIS NODE CANNOT ANSWER, recorded rather than drawn:
 *
 *   · The Isotype year rows, lighting in step with the satellite loop. They need per-year built and
 *     tree fractions. /earth carries nine years of embeddings, eight change pairs with their
 *     hectares over threshold, the Sentinel and Landsat years, and two credit lines — and no
 *     fraction of anything, per year or otherwise. The prompt says to read it first and omit if so.
 *   · A year of daily means. GET /issues/days carries the days, up to 90, and Historical's strips
 *     draw every day the node holds; the sensors here reach weeks, not a year. A year of bars from
 *     a few weeks of readings would be a drawing of nothing.
 *
 * Neither is stamped `example`. An absence that says which absence it is can be answered later; a
 * drawing of invented data cannot be un-seen.
 */
PAI_LOAD.push(function () {
'use strict';

const { esc, row } = window.K;

/* The node's own words for what each kind IS, because "map" and "model" are table values and not
   sentences. The node does not publish a gloss for them, so these name the kind and say plainly
   that the naming is this page's. */
const KINDS = {
  sensor: ['Kit in and around this house', 'what somebody here installed'],
  model: ['Models read for this point', 'somebody else computes them, this node reads them'],
  map: ['The satellite record', 'annual passes, kept on this machine'],
};

const day = iso => {
  const d = new Date(iso);
  return isNaN(d) ? String(iso).slice(0, 10)
    : d.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' });
};

window.PAI.register({
  id: 'reach', pack: 'core', stage: 'observe', order: 5, learn: ['reach'],
  reads: ['/reach'],
  title: 'How far back this node can be asked',
  needs: ['REACH'],
  render(ctx) {
    const rows = (window.REACH || []).slice()
      .sort((a, b) => (b.days || 0) - (a.days || 0));
    if (!rows.length) {
      return `<p class="note" id="reach-none" data-ref="sat-strip">This node has no hourly record `
        + `for any kind of source yet, so there is no past here to ask about.</p>`;
    }
    const most = rows[0].days || 1;
    return `<div class="reads" id="reach-rows" data-ref="sat-strip">`
      + rows.map(r => {
        const [name, what] = KINDS[r.kind] || [r.kind, 'a kind this page has no words for'];
        return row({ id: `reach-${esc(r.kind)}`, component: 'reachRow', ref: 'reach-rows',
          cols: 'minmax(0,210px) minmax(0,1fr) auto',
          left: `<span class="who"><b>${esc(name)}</b><span class="m">${esc(what)}</span></span>`,
          line: `Oldest hourly reading ${day(r.oldest)}, newest ${day(r.newest)} \u00b7 `
            + `${(r.buckets || 0).toLocaleString()} hours from ${r.sources} `
            + `${r.sources === 1 ? 'source' : 'sources'}.`,
          qty: [{ num: `reach.${esc(r.kind)}.days`,
            value: r.days >= 730 ? `${(r.days / 365).toFixed(1)} yr` : `${r.days} d`,
            cmp: `of record on this node \u00b7 against ${most >= 730
              ? `${(most / 365).toFixed(1)} years` : `${most} days`} for the longest of the three` }] });
      }).join('')
      + `</div>`
      + `<p class="cap" id="reach-cap" data-ref="reach-rows">Two things this view was asked for and `
      + `this node cannot answer, named rather than drawn: the year rows that would light in step `
      + `with the loop need a built and tree fraction per year, and <b>/earth carries none</b> \u2014 `
      + `nine years of embeddings, eight change pairs and two credit lines, no fractions. And a year `
      + `of daily means has no route: the hourly ones hold a day, and the kit here reaches twenty.</p>`;
  },
  notes() {
    return [
      { id: 'reach-rows', label: 'Three kinds of past',
        text: 'Three kinds of source and three different amounts of past. The '
        + 'satellite record reaches ten years because an annual pass is one row a year and this '
        + 'node kept them; the kit in the house reaches twenty days because that is how long it has '
        + 'been running. A question about a year has a different answer for each, and that is the '
        + 'thing this panel exists to say before anybody asks one.' },
      { id: 'reach-cap', label: 'Two things not drawn here',
        text: 'Prompt 4 asked for Isotype year rows lighting with the loop, and '
        + 'for a year of daily means. /earth has no per-year fractions, so the first is not on this '
        + 'node\u2019s wire. The days are, up to 90, and Historical\u2019s strips draw every one the node '
        + 'holds; the kit here does not reach a year. The instruction was to read the endpoint first '
        + 'and omit what it does not carry, which is what this is \u2014 not a stamp saying `example` '
        + 'over a drawing of numbers nobody computed.' },
    ];
  },
});

});

/* ================================================================= mods/netmap.js ==== */
/* netmap · core · observe
 *
 * THE FIGURE OF A NODE AT WORK, AND WHY IT MOVES.
 *
 * This is the old page's network map, brought back at Tomas's word on 16 September: three things
 * the node reads flowing IN along their wires, three things that leave flowing OUT along theirs,
 * and the node breathing in the middle. It was dropped by the Phase 2 rewrite, which is the second
 * time it has been lost and restored — the first was v0.53, for the same reason both times: drawn
 * still, it reads as a diagram of a thing; drawn moving, it reads as a thing at work.
 *
 * TWO RULES THE MOTION OBEYS, and they are the whole of why it is allowed to move at all.
 *
 * A motion with no datum behind it is deleted. `flowing` is the third element of every row, and it
 * is false when nothing actually travels that way — no parent, no Index cells, no asks. A wire with
 * nothing on it is still drawn, dashed and faint, because the LINK exists; what does not exist is
 * the traffic. A fresh node used to animate data moving outward to "nowhere yet", which is a page
 * telling a household something the node never said.
 *
 * The motion is CSS and never SMIL. `@media (prefers-reduced-motion: reduce)` at the foot of
 * dashboard.css turns every animation on this page off; it cannot touch an <animate> element, and
 * that is the other half of why the original SMIL version was removed.
 *
 * The figure and the list under it are two renderings of the same six facts and nothing else, so
 * they cannot come to disagree — and the list is what a phone gets, because a 1200-unit viewBox
 * scaled to 375 px renders an 11 px label at about three pixels.
 */
PAI_LOAD.push(function () {
'use strict';

const { esc, interp } = window.K;

/* The six facts, once. /sensors carries every kind the node knows (sensor, model, map, child) and
 * /issues does not — it publishes only what has a coordinate — which is why this reads the sensor
 * table rather than H3.sensors. */
function facts(ctx) {
  const all = window.SENSORS || [];
  const cells = window.CELLS || [];
  const rho = ctx.S.rho || {};
  const parent = ((window.SETTINGS_RAW || {}).runtime || []).find(r => r.key === 'PARENT_API_URL') || {};
  return {
    health: ctx.S.health || {},
    own: all.filter(s => s.local && s.kind === 'sensor').length,
    ring: all.filter(s => !s.local && s.kind === 'sensor').length,
    models: all.filter(s => s.kind === 'model').length,
    cells,
    /* /cells is one row per value, and a cell can carry several (node #1, 28 Sep 2026: 10 rows over 6
       cells, three packs feeding Environmental|Bioregion). "N of 20" counts cells, so it counts keys. */
    cellCount: new Set(cells.map(c => c.cell)).size,
    /* `set` is truthful at every share level even when the value is masked, so a screen with no
       token can say a parent exists without being told where it is. */
    parentName: parent.set && parent.value && !/^\u2022+/.test(parent.value) ? parent.value : '',
    acted: rho.acted || 0,
    asks: rho.alerts_act || 0,
  };
}

/* Each wire meets the node on its own point of the circle rather than all six on one: converging on
 * a single point pinched the figure into a bowtie and the top and bottom wires crossed. */
function wire(side, y) {
  const k = (y - 180) * 0.3, ey = 180 + k, dx = Math.sqrt(74 * 74 - k * k);
  return side === 'in' ? `M450 ${y} C 516 ${y} 548 ${ey} ${675 - dx} ${ey}`
                       : `M${675 + dx} ${ey} C 800 ${ey} 800 ${y} 858 ${y}`;
}

/* In-wires run label -> node and out-wires node -> label, so the dash march and the travelling dot
 * both go the way the data goes. Ink for what arrives, --cells for what leaves. */
function rows(side, items) {
  return items.map(([label, value, flowing], i) => {
    const y = 96 + i * 84;
    const x = side === 'in' ? 430 : 872;
    const d = wire(side, y), ink = side === 'in' ? 'var(--ink)' : 'var(--cells)';
    return `<text x="${x}" y="${y - 8}" text-anchor="${side === 'in' ? 'end' : 'start'}" class="mono label"`
      + ` font-size="11" letter-spacing=".1em" fill-opacity=".65">${esc(String(label).toUpperCase())}</text>`
      + `<text x="${x}" y="${y + 14}" text-anchor="${side === 'in' ? 'end' : 'start'}" class="fig"`
      + ` font-size="15" font-family="var(--fc-font-body)">${esc(value)}</text>`
      + `<path class="wire" d="${d}" fill="none" stroke="${ink}" stroke-width="1.6"`
      + ` stroke-opacity="${flowing ? '.55' : '.22'}"${flowing ? '' : ' stroke-dasharray="3 5"'}/>`
      + (flowing ? `<circle class="dot" r="3.5" fill="${ink}"`
                   + ` style="offset-path:path('${d}');animation-duration:${7 + i * 2.5}s"/>` : '');
  }).join('');
}

window.PAI.register({
  id: 'netmap', pack: 'core', stage: 'observe', order: 0, learn: ['parent'],
  reads: ['/sensors', '/cells', '/health', '/rho', '/settings'],
  /* Network's short answer, for the same reason: this view is this node in relation to the network,
     and the map of that relation is the whole of the short version. */
  level: 'simple',
  title: 'This node, and what moves through it',
  needs: ['SENSORS'],
  render(ctx) {
    const w = (window.W ? window.W() : {}).net || {};
    const d = facts(ctx), h = d.health;
    const n = (v, one, many) => `${v} ${v === 1 ? one : many}`;
    const IN = [[w.yours, n(d.own, w.sensor, w.sensors), d.own > 0],
                [w.street, n(d.ring, w.station, w.stations), d.ring > 0],
                [w.models, n(d.models, w.model, w.models_), d.models > 0]];
    const OUT = [[w.means, d.parentName || w.parentNowhere, !!d.parentName],
                 [w.cellsOut, interp(w.cellsN, { n: d.cellCount }), d.cellCount > 0],
                 [w.rhoOut, interp(w.rhoN, { closed: d.acted, total: d.asks }), d.asks > 0]];
    const kept = interp(w.kept, { n: (h.ingested || 0).toLocaleString() });

    const svg = `<svg class="net" viewBox="0 0 1200 380" role="img" aria-label="${esc(w.title || '')}">`
      + `<text x="430" y="36" text-anchor="end" class="mono label" font-size="11" letter-spacing=".12em">`
      + `${esc(String(w.reads || '').toUpperCase())}</text>`
      + `<text x="872" y="36" class="mono label" font-size="11" letter-spacing=".12em">`
      + `${esc(String(w.leavesShort || '').toUpperCase())}</text>`
      + rows('in', IN) + rows('out', OUT)
      + `<circle class="halo" cx="675" cy="180" r="74" fill="none" stroke="var(--ink)" stroke-opacity=".4"/>`
      + `<circle cx="675" cy="180" r="74" fill="var(--ground)" stroke="var(--ink)"/>`
      + `<text x="675" y="172" text-anchor="middle" class="fig" font-size="17"`
      + ` font-family="var(--fc-font-display)" font-weight="700">${esc(h.node || 'node')}</text>`
      + `<text x="675" y="196" text-anchor="middle" class="mono label" font-size="10.5"`
      + ` letter-spacing=".1em" fill-opacity=".65">${esc(String(h.kind || w.home || '').toUpperCase())}</text>`
      + `<text x="675" y="330" text-anchor="middle" class="mono label" font-size="11" fill-opacity=".65">`
      + `${esc(kept)}</text></svg>`;

    const list = side => side.map(([label, value]) =>
      `<div class="vit"><span>${esc(label)}</span><span>${esc(value)}</span></div>`).join('');
    const text = `<div class="netlist">`
      + `<div class="k">${esc(w.reads || '')}</div>${list(IN)}`
      + `<div class="netnode">${esc(h.node || 'node')} <span class="note">${esc(h.kind || w.home || '')}</span></div>`
      + `<div class="k">${esc(w.leaves || '')}</div>${list(OUT)}`
      + `<p class="note mt">${esc(kept)}</p></div>`;

    return `<div data-component="netMap" id="netmap-fig" data-ref="netmap">${svg}${text}`
      + `<p class="cap" id="netmap-cap" data-ref="netmap-fig">`
      + `<span data-num="netmap.kept" data-cmp="readings this node has taken and kept; none of them `
      + `leave it">${esc(String((h.ingested || 0).toLocaleString()))}</span> \u00b7 ${esc(w.sub || '')}</p></div>`;
  },
  notes(ctx) {
    const d = facts(ctx);
    const still = [['a parent', !!d.parentName], ['Index cells', d.cells.length > 0],
                   ['answered alerts', d.asks > 0]].filter(([, on]) => !on).map(([k]) => k);
    return [
      { id: 'netmap-motion', label: 'A wire with nothing on it',
        text: 'The wires carry a moving dot only where something actually '
        + 'travels. A dashed, faint wire is a link that exists with no traffic on it'
        + (still.length ? `, which on this node is ${still.join(' and ')}.` : ', of which this node '
          + 'has none right now \u2014 all six are carrying.')
        + ' A motion with no datum behind it would be the page telling this house something the node '
        + 'never said.' },
      { id: 'netmap-still', label: 'Reduce motion stops all of it',
        text: 'Every animation here is CSS, so the operating system\u2019s '
        + '"reduce motion" setting stops all of it. The original figure used SVG\u2019s own <animate>, '
        + 'which ignores that setting, and that is why it was rewritten rather than restored as it was.' },
      { id: 'netmap-what', label: 'What actually travels',
        text: `Readings stay on this machine \u2014 ${(d.health.ingested || 0)
        .toLocaleString()} of them so far, and not one leaves. What travels up to a community node is `
        + 'hourly means, Index cells and \u03c1: enough to see the place, never enough to see the house.' },
    ];
  },
});

});

/* ================================================================= h/mods/registry.js ==== */
/* registry · core · observe (Network)
 *
 * What this place COULD read, and where it could go: the whole registry, not just the part this
 * node has wired up. `GET /sources` at the pin in `data/sources`.
 *
 * WHY IT IS FETCHED LATE. /sources is 417 kB, which is nearly what /issues costs, to draw a handful
 * of numbers. Every other route the page reads is needed on the view a reader lands on; this one is
 * needed on Network and nowhere else, so it is asked for the first time somebody goes there and the
 * page redraws when it arrives. A reader who never opens Network never pays for it.
 *
 * THE THREE COUNTS ARE THE NODE'S. /sources carries `counts`, `{cell: {capable, reviewed,
 * candidate}}` from app/registry.py's cell_counts(), the same three every /cells row carries for
 * its own cell. This band adds them up over the cells the way `planetai sources` does ("across N
 * cells"), and decides nothing about what counts: the rule is in the node, in one place.
 *
 * THE PAGE DOES NOT JUDGE A LICENCE. The registry carries `license` as free text and publishes no
 * open/not flag, so the counts here are of what the rows SAY: how many state in the registry's own
 * words that no licence is published, against how many carry a licence text. Sorting "CC-BY-SA-4.0
 * (site default; proprietary licences on some pages)" into open or not-open is a judgement, and a
 * page that made it would be making it on the Foundation's behalf. The text is shown instead.
 */
PAI_LOAD.push(function () {
'use strict';

const { esc, row } = window.K;

/* Where the registry lives, and the documentation's steps for adding to it. The anchor is the
   heading "Adding a source" in docs/site/sources.md, slugged the way tools/build_docs.py does;
   tests/test_dashboard.py fails if the heading moves. */
const REGISTRY_REPO = 'https://github.com/fabcity/awesome-fabcity-data';
const ADD_A_SOURCE = 'https://planetai.fab.city/docs/sources/#adding-a-source';

/* The registry's own words for what a place to act IS. `act_kind` is a token; these name it. */
const ACT_WORDS = {
  /* [one, many, what it is]. Both forms are written out because the plurals are irregular: one
     directory, two directories; one library, two libraries. "1 lists of places that pledged" is
     what appending an s gets you. */
  facility: ['directory of fab labs', 'directories of fab labs', 'places with machines in them'],
  design: ['library of open designs', 'libraries of open designs',
    'things somebody has already worked out'],
  repair: ['directory of repair cafés', 'directories of repair cafés',
    'places where things get fixed'],
  match: ['matcher of designs to workshops', 'matchers of designs to workshops',
    'which workshop could build which design'],
  network: ['list of places that pledged', 'lists of places that pledged', 'who else is doing this'],
};

/* A row that says, in the registry's own words, that nothing is licensed. Matching the registry's
   OWN statement is reading; deciding whether "CC-BY-SA-4.0 (site default)" counts as open is not. */
const saysNoLicence = r => /^\s*(no licence published|not open\b)/i.test(String(r.license || ''));

/* The node's per-cell counts, summed over the cells, as `planetai sources` prints them. */
function totals(counts) {
  const cells = Object.values(counts || {});
  const t = { cells: cells.length, capable: 0, reviewed: 0, candidate: 0 };
  for (const c of cells) for (const k of ['capable', 'reviewed', 'candidate']) t[k] += Number(c[k]) || 0;
  return t;
}

window.PAI.register({
  id: 'registry', pack: 'core', stage: 'observe', order: 60, learn: ['registry'],
  reads: ['/sources'],
  title: 'What this place could read, and where it could go',
  needs: ['SOURCES'],
  render() {
    const d = window.SOURCES || {};
    const rows = d.sources || [];
    const reg = d.registry || {};
    if (!rows.length) {
      return `<p class="note" id="registry-none" data-ref="netmap-figure">The registry answered with `
        + `no entries, so there is nothing to say about what this place could read.</p>`;
    }
    const wired = rows.filter(r => r.adapter);
    const acts = rows.filter(r => String(r.role || '').includes('act'));
    const byKind = {};
    for (const r of acts) (byKind[r.act_kind] = byKind[r.act_kind] || []).push(r);
    const unlicensed = acts.filter(saysNoLicence).length;
    const kinds = Object.entries(byKind)
      .map(([k, v]) => `${v.length} ${(ACT_WORDS[k] || [k, k])[v.length === 1 ? 0 : 1]}`)
      .join(' · ');
    const codes = [...new Set(wired.map(r => r.adapter))].sort();
    /* The pin is a commit of the registry, so it links to the registry at that commit: the files
       this node carries, as they were when it was synced. */
    const pin = reg.sha || reg.short;
    const pinned = pin
      ? `<a class="mono" href="${esc(`${REGISTRY_REPO}/tree/${pin}`)}">pin ${esc(reg.short || pin)}</a>`
      : 'pin ?';
    const t = totals(d.counts);
    const cols = 'minmax(0,210px) minmax(0,1fr) auto';
    return `<div class="reads" id="registry-rows" data-ref="netmap-figure">`
      + row({ id: 'registry-read', component: 'sourcesRead', ref: 'netmap-figure', cols,
        left: `<span class="who"><b>Registered, and read</b>`
          + `<span class="m">${pinned} · synced ${esc(reg.synced || '?')}</span></span>`,
        line: `${rows.length} sources registered; ${wired.length} have code on this node that reads `
          + `them: ${codes.join(', ')}. The rest have no adapter yet, which is a thing nobody has `
          + `written rather than a thing this node refuses.`,
        qty: [{ num: 'sources.read', value: `${wired.length}/${rows.length}`,
          cmp: `registered sources this node has code for, at registry pin ${reg.short || '?'}` }] })
      + (d.counts ? row({ id: 'registry-counts', component: 'sourcesCounts', ref: 'netmap-figure',
        cols,
        left: `<span class="who"><b>What a cell could use</b>`
          + `<span class="m">across ${t.cells} cell${t.cells === 1 ? '' : 's'}</span></span>`,
        line: 'Capable: live, and code here reads it. Reviewed: live, and backed by that code or by '
          + 'a review that found it usable. Candidate: verified, and nobody has read it for a real '
          + 'place yet. Counted once for every cell an entry feeds; nothing deprecated, stale, '
          + 'paywalled or planned counts in any of them.',
        qty: [
          { num: 'sources.capable', value: `${t.capable} capable`,
            cmp: `summed over the ${t.cells} cells the registry counts, at pin ${reg.short || '?'}` },
          { num: 'sources.reviewed', value: `${t.reviewed} reviewed`,
            cmp: `against ${t.capable} capable, which it always includes` },
          { num: 'sources.candidate', value: `${t.candidate} candidate`,
            cmp: `against ${t.reviewed} reviewed: verified and not yet read` },
        ] }) : '')
      + row({ id: 'registry-act', component: 'sourcesAct', ref: 'netmap-figure', cols,
        line: `${kinds}. ${unlicensed} of them say, in the registry's own words, that no licence is `
          + `published; the rest carry a licence text. This page does not sort a licence into open `
          + `or not: it shows what the registry wrote.`,
        left: `<span class="who"><b>Places to act</b><span class="m">not things to read</span></span>`,
        qty: [{ num: 'sources.act', value: String(acts.length),
          cmp: `of ${rows.length} registered are somewhere to go rather than something to read` }] })
      + `</div>`
      /* Where to go from here: the two halves of the list the counts are made of, the per-cell
         rows this node computes, and how an entry gets into the registry at all. */
      + `<p class="cap" id="registry-how" data-ref="registry-rows">The live entries are at `
      + `<a class="mono" target="_blank" rel="noopener" href="/sources?status=live">GET /sources?status=live</a> and the candidates `
      + `at <a class="mono" target="_blank" rel="noopener" href="/sources?status=candidate">GET /sources?status=candidate</a>; each `
      + `row of <a class="mono" target="_blank" rel="noopener" href="/cells">GET /cells</a> carries the three counts for its own `
      + `cell. An entry is added by a pull request to the registry and a re-pin: `
      + `<a href="${ADD_A_SOURCE}">Adding a source</a>, in the documentation.</p>`
      /* COUNTED, NOT TYPED. This said "The eight" because there were eight at registry pin 85a194c.
         The pin moved and the number with it, and a fold that says eight over a list of sixteen is
         the page telling a reader something it can see is false. A number in prose about data
         that arrives over the wire is a number that will be wrong. */
      + `<details class="fold" id="registry-fold"><summary>All ${acts.length}, and what each one's `
      + `licence says</summary><dl class="notelist">`
      + acts.map(r => `<div class="noteitem" id="src-${esc(r.slug || '').replace(/[^a-z0-9-]/gi, '-')}">`
        + `<dt>${esc(r.name || r.slug)}<span class="m"> · `
        + `${esc((ACT_WORDS[r.act_kind] || [])[2] || r.act_kind || '')}</span></dt>`
        + `<dd><span class="said">${esc(r.license || 'the registry records no licence text at all')}`
        + `</span></dd></div>`).join('')
      + `</dl></details>`;
  },
  notes() {
    return [
      { id: 'registry-read', label: 'Could read, against does',
        text: 'The registry is what this place COULD read; the adapters are what '
        + 'it does. The gap between them is not a refusal: it is code nobody has written yet, and '
        + 'naming it is how somebody comes to write it. This row reads each entry’s adapter '
        + 'string and never infers one, so an adapter that exists here and is not yet named '
        + 'upstream is not counted until the registry names it and the pin moves.' },
      { id: 'registry-counts', label: 'Three counts, and why not one',
        text: 'One number per cell used to count every entry filed under it, '
        + 'deprecated and paywalled ones included, which made cells look answered that no node '
        + 'could fill. These three are counted from what an entry feeds, not where it is filed, '
        + 'and only live and candidate entries count at all. The node computes them; this page '
        + 'only adds them up over the cells.' },
      { id: 'registry-act', label: 'A place to act is not a source',
        text: 'A place to act is not a source of readings. They are directories '
        + 'of workshops and repair cafés, libraries of designs somebody has already worked out, '
        + 'a matcher between the two, and a list of places that pledged. What this page will not '
        + 'do is decide whether a licence is open: the registry carries free text, some of it '
        + 'plainly saying no licence is published and some of it a licence with conditions, and '
        + 'sorting the second kind into a yes or a no is a judgement made on somebody '
        + 'else’s behalf. The text is here instead.' },
    ];
  },
});

});

/* ================================================================= h/mods/reticulum.js ==== */
/* reticulum · reticulum · observe
 *
 * What this node says about where it is over the radio, and what it has heard other nodes say. The
 * whole of it is a cell: Reticulum announces the H3 cell this node stands in at
 * RETICULUM_PRESENCE_RES, never finer than PRESENCE_RES_FLOOR, never a coordinate. A peer is
 * therefore known as a cell and a rough distance — which is the privacy property the scheme exists
 * for, and the thing a drawing of it has to show rather than tidy away with a pin.
 *
 * This is the first pack section in the folder that is not the renderer's own: it registers with the
 * page contract exactly the way a Meshtastic section, an open hardware manager, or a wild pack
 * would, and the page knows nothing about it except what it declares here.
 */
PAI_LOAD.push(function () {
'use strict';

const { esc, fmt, age, row } = window.K;
const { H, address, km2, edge } = window.KH;
const R = H.radio;

window.PAI.register({
  id: 'reticulum', pack: 'reticulum', stage: 'observe', order: 40, learn: ['presence'],
  reads: ['/issues'],
  title: 'What leaves this house by radio',
  needs: ['H3.radio'],
  render(ctx) {
    const pr = ctx.S.peer;
    const cands = R.candidates.length;
    const drawing = `<figure class="gridwrap" id="radio-map" data-component="radioMap"`
      + ` data-ref="radio-rows">`
      /* PORTED: the drawing had a projected cell set of its own. GET /issues publishes the announce
         resolution's plate already — it is inside the two steps nav publishes at every resolution —
         so this draws the same cells from the node's own geometry rather than a second copy. */
      + ctx.KMAP.map(R.res, { cells: [R.mine].concat(R.candidates), ref: 'radio-rows',
        label: `the cell this node announces itself in at resolution ${R.res}, and the `
          + `${cands} cells a peer ${R.peer_km} km away could be in` })
      + `<div class="gridkey"><span><i class="own"></i>what this node announces</span>`
      + `<span><i class="read"></i>where the peer could be</span>`
      + `<span><i class="none"></i>heard nothing</span></div>`
      + `<figcaption class="cap">resolution ${R.res} · ${esc(edge(R.edge_m))} to an edge · `
      + `${esc(km2(R.area_m2))}</figcaption></figure>`;
    const rows = `<div class="reads" id="radio-rows" data-ref="radio-map">`
      + row({ id: 'radio-reticulum', component: 'announce', ref: 'radio-map',
        cols: 'minmax(0,210px) minmax(0,1fr) auto',
        left: `<span class="who"><b>What this node announces</b>`
          + `<span class="m">RETICULUM_PRESENCE_RES ${R.res}</span></span>`,
        line: `The cell, and nothing else. Never a coordinate, never finer than resolution `
          + `${H.settings.PRESENCE_RES_FLOOR}.`,
        qty: [{ num: 'nav.announce.km2', value: km2(R.area_m2),
          cmp: `against ${km2(H.ladder[H.publication.res].own_area_m2)}, the resolution GET /health rounds to` }],
      })
      + `<div class="sub-addr">${address(R.mine, R.res)}</div>`
      + (pr ? row({ id: 'radio-peer', component: 'peers', ref: 'radio-map',
        cols: 'minmax(0,210px) minmax(0,1fr) auto',
        left: `<span class="who"><b>${esc(pr.node)}</b><span class="m">heard `
          + `${esc(age(pr.heard_minutes_ago))}</span></span>`,
        line: `Announced, and this node was listening. A cell and a distance; read it as a direction `
          + `and a rough reach.`,
        qty: [{ num: 'peer.km', value: `${pr.km} km`,
          cmp: `between two cells ${edge(R.edge_m)} to an edge` },
        { num: 'peer.pm25', value: `${fmt(pr.value.value, pr.value.dp)} ${pr.value.unit}`,
          cmp: `no comparison yet · a peer is never compared with this node's own reading` }],
      }) : `<p class="cap" data-ref="radio-map">No other node has been heard.</p>`)
      + `</div>`;
    return `<div class="two-up">${drawing}${rows}</div>`;
  },
  wall(ctx) {
    const pr = ctx.S.peer;
    if (!pr) return '';
    return `<div class="col" data-component="peers" data-ref="wall-lead">`
      + `<h3 data-role="wall-issue">${esc(pr.node)}, heard</h3>`
      + `<div class="line"><span class="num" data-num="peer.km" data-cmp="a cell and a distance, `
      + `never a point">${pr.km}</span><small>km · resolution ${R.res}</small></div></div>`;
  },
  notes(ctx) {
    const pr = ctx.S.peer;
    return [
      { id: 'reticulum-cell', label: 'The cell it announces',
        text: `Reticulum announces the H3 cell this node is in at resolution `
        + `${R.res} — ${edge(R.edge_m)} to an edge, ${km2(R.area_m2)} — and nothing else. It is never `
        + `finer than resolution ${H.settings.PRESENCE_RES_FLOOR}, which is the floor no settings box `
        + 'may pass. That cell is the whole of what a stranger on the radio learns about where this '
        + 'node is.' },
      { id: 'reticulum-peer', label: 'Where the peer could be',
        text: `The fixture kept the peer’s resolution and its distance and not `
        + `the cell it announced, so the drawing shows all ${R.candidates.length} cells `
        + `${R.peer_km} km could be in. That is not a gap in the drawing — it is the shape of what a `
        + 'radio announce actually tells you. A page that put a pin at 61 km on a bearing it was never '
        + 'sent would be inventing the one thing the scheme refuses to send.' },
      ...(pr ? [{ id: 'reticulum-never', label: 'What the announce never carries',
        text: pr.never[ctx.LOC] }] : []),
      { id: 'reticulum-pack', label: 'A pack’s section, not the page’s',
        text: 'This section is a pack’s, not the page’s: it registered itself '
        + 'with the page contract the way any pack does, and the page knows nothing about Reticulum '
        + 'beyond what the section declares. A node without the reticulum pack has no such section; '
        + 'a node with a new radio adds a file.' },
    ];
  },
});

});

/* ================================================================= h/mods/meshtastic.js ==== */
/* meshtastic · meshtastic · observe
 *
 * The LoRa mesh in this house. One device, reporting over Meshtastic through a gateway on the WiFi;
 * it carries no coordinate at all, so it is in this node's cell because this node is, and it is on
 * no grid drawing in this folder for that reason. What it does carry — battery, gas, air quality
 * index, the LoRa channel's utilisation — is what a radio in a room actually knows.
 *
 * A pack section, registered the way any pack's is. The Meshtastic pack on the node parses the
 * gateway's JSON (app/sources.py, meshtastic_message); this is what that parsing is for.
 */
PAI_LOAD.push(function () {
'use strict';

const { esc, fmt, age, row } = window.K;
const { H } = window.KH;
const R = H.radio;

/* The device's own readings: it has no coordinate, so it is not in H3.sensors, and make-h3.mjs
 * carries its 15-minute means on the radio record instead. */
const READ = () => R.mesh_reads || [];

window.PAI.register({
  id: 'meshtastic', pack: 'meshtastic', stage: 'observe', order: 41, learn: ['mesh'],
  reads: ['/issues'],
  title: 'The mesh in this house',
  needs: ['H3.radio.mesh'],
  render(ctx) {
    const m = R.mesh, d = R.mesh_sensor;
    const last = age(Math.round((Date.parse(ctx.S.base.captured_utc) - Date.parse(m.last)) / 60000));
    const reads = READ();
    const shown = reads.filter(r => H.metrics[r.metric]).slice(0, 4);
    return `<div class="reads" id="mesh-rows" data-ref="radio-map">`
      + row({ id: 'mesh-gateway', component: 'mesh', ref: 'radio-map',
        cols: 'minmax(0,210px) minmax(0,1fr) auto',
        left: `<span class="who"><b>${esc(d ? d.name : 'the mesh')}</b>`
          + `<span class="m">${esc(m.root_topic)} · ${esc(m.gateway)}</span></span>`,
        line: `Reports over LoRa and carries no position: it is in this node's cell because this `
          + `node is. Last heard ${esc(last)}.`,
        qty: [{ num: 'nav.mesh.packets', value: String(m.packets),
          cmp: `packets since this node started` }],
      })
      + (shown.length ? shown.map(r => {
        const mt = H.metrics[r.metric];
        return row({ id: `mesh-${esc(r.metric)}`, component: 'meshReading', ref: 'mesh-gateway',
          cols: 'minmax(0,210px) minmax(0,1fr) auto',
          left: `<span class="who"><b>${esc(mt.label)}</b><span class="m">${esc(r.metric)}</span></span>`,
          line: `15-minute mean from the device in the house.`,
          qty: [{ num: `mesh.${esc(r.metric)}`, value: `${fmt(r.mean_15m, mt.dp)} ${mt.unit}`,
            cmp: mt.issue && ctx.ISS[mt.issue] && ctx.ISS[mt.issue].line
              ? `against the line, ${fmt(ctx.ISS[mt.issue].line.value, mt.dp)} ${ctx.ISS[mt.issue].unit}`
              : `no comparison yet · no line is declared for ${mt.label}` }],
        });
      }).join('') : '')
      + `</div>`;
  },
  notes() {
    const d = R.mesh_sensor;
    return [
      { id: 'mesh-noposition', label: 'No coordinate, no cell',
        text: `${d ? d.name : 'The mesh device'} carries no latitude or `
        + 'longitude, which is why it appears on no grid drawing here: a station with no coordinate '
        + 'has no cell of its own, and the page will not put it in one by assumption. It is in this '
        + 'node’s cell because this node is.' },
      { id: 'mesh-what', label: 'What a LoRa device knows',
        text: 'What a LoRa device in a room actually knows: its battery, a gas '
        + 'resistance, an air quality index, how busy its radio channel is. The Meshtastic pack turns '
        + 'the gateway’s JSON into readings the node can keep; a gateway with JSON output off is the '
        + 'commonest reason this section is empty on a new node, and `planetai meshtastic` says how '
        + 'to turn it on.' },
      { id: 'mesh-pack', label: 'A small pack on purpose',
        text: 'A pack section, and a small one on purpose: it shows the shape a '
        + 'pack’s section takes — a file that registers a title, a stage, what it '
        + 'needs, and what it says.' },
    ];
  },
});

});

/* ================================================================= h/mods/hardware.js ==== */
/* hardware · hardware · observe
 *
 * The devices this house actually runs, and the hook for the two things Tomas named as coming next:
 * an open hardware manager, and the capacity to make locally.
 *
 * What is real here is the list. Three Smart Citizen kits and one Meshtastic node are what node #1
 * has on its own ground, and everything said about them — source, indoors or out, what each
 * measures, when it last spoke — is in the fixture. Smart Citizen and Meshtastic are both open
 * hardware, which is a fact about the devices and not a claim this page makes for them.
 *
 * What is not real yet is the manager. The row that would link a device to its design files, its
 * firmware, its bill of materials and the nearest place that could make or mend it needs a pack
 * this node does not have, and the contract's answer to that is one honest line rather than a
 * blank: `needs: ['OHM']` on a second section that is not here. This file is the shape the
 * hardware pack's contribution takes; the manager is the pack.
 */
PAI_LOAD.push(function () {
'use strict';

const { esc, age, row } = window.K;
const { H, address } = window.KH;

/* The devices on this node's own ground: every station marked local, plus the mesh device, which
 * carries no coordinate and is therefore not in H3.sensors at all. */
function devices() {
  const own = H.sensors.filter(s => s.local).map(s => ({
    id: s.sensor_id, name: s.name || s.sensor_id, source: s.label, url: s.url,
    where: s.indoor ? 'indoors' : 'outdoors', metrics: Object.keys(s.read || {}),
    silent: Math.max(0, ...Object.values(s.read || {}).map(r => r.silent_minutes || 0)),
    cell: s.chain, open: s.source === 'smartcitizen',
  }));
  const m = H.radio && H.radio.mesh_sensor;
  if (m) own.push({
    id: m.sensor_id, name: m.name, source: 'Meshtastic', url: null,
    where: m.indoor ? 'indoors' : 'outdoors',
    metrics: (H.radio.mesh_reads || []).map(r => r.metric), silent: null, cell: null, open: true,
  });
  return own;
}

window.PAI.register({
  id: 'hardware', pack: 'hardware', stage: 'observe', order: 45, learn: ['siting'],
  reads: ['/issues'],
  title: 'The hardware in this house',
  needs: ['H3.sensors'],
  render(ctx) {
    const list = devices();
    const cols = 'minmax(0,210px) minmax(0,1fr) auto';
    /* `sensors` lives on Now and this section on Network, so the link named a section the reader
       cannot see. It points at its own absent-manager row instead, which is on this page and is
       the thing the list is actually about. */
    return `<div class="reads" id="hardware-rows" data-ref="hw-manager">`
      + list.map(d => row({
        id: `hw-${esc(d.id)}`, component: 'device', ref: 'hardware-rows', cols,
        /* The link lives in the left-hand block, which row() places as HTML; the line is text and
         * row() escapes it, so an anchor put there prints as angle brackets — measured, once. */
        left: `<span class="who"><b>${esc(d.name)}</b><span class="m">${esc(d.source)}`
          + `${d.open ? ' · open hardware' : ''}`
          + (d.url ? ` · <a href="${esc(d.url)}" target="_blank" rel="noopener">its page</a>` : '')
          + `</span></span>`,
        line: `${d.where} · measures ${d.metrics.length ? d.metrics.join(', ')
          : 'nothing this page lists'}`
          + (d.cell ? ` · ${d.cell[ctx.RES]}` : ' · no coordinate: in this node’s cell because this node is'),
        lineRole: 'device',
        qty: [{ num: `hardware.${esc(d.id)}.metrics`, value: String(d.metrics.length),
          cmp: d.silent == null ? 'metrics · no silence figure for a device with no coordinate'
            : d.silent > 60 ? `metrics · silent ${age(d.silent)}` : `metrics · heard ${age(d.silent)}` }],
      })).join('')
      + row({
        id: 'hw-manager', component: 'absent', ref: 'hardware-rows', cols, cls: 'absent',
        left: `<span class="who"><b>Open hardware manager</b><span class="m">not connected</span></span>`,
        line: 'Design files, firmware, bill of materials, and where nearby a device could be made or '
          + 'mended. A pack this node does not have; when it does, it registers here.',
        qty: [{ num: 'hardware.manager.devices', value: `0 of ${list.length}`,
          cmp: `devices with their design files on this node` }],
      })
      + `</div>`;
  },
  notes() {
    const list = devices();
    return [
      { id: 'hardware-real', label: 'What is real in this list',
        text: `What is real here is the list: ${list.length} devices on this `
        + 'node’s own ground, and everything said about them is in the fixture — source, indoors or '
        + 'out, what each measures, when it last spoke. Smart Citizen and Meshtastic are both open '
        + 'hardware, which is a fact about the devices and not a claim this page makes for them.' },
      { id: 'hardware-manager', label: 'The manager row',
        text: 'The manager row is a hook and nothing more: an open hardware '
        + 'manager and the capacity to make locally are the next packs, not this one. When they '
        + 'exist they register a section the way every section here did, and this row stops saying '
        + '"not connected". Until then the contract’s rule holds: a missing pack is one line that '
        + 'says so, never a blank.' },
      { id: 'hardware-shape', label: 'What a pack contributes',
        text: 'This is the shape a pack’s contribution takes: a '
        + 'title, a stage, what it needs, what it says, and its notes. A node that adds a device adds '
        + 'a row; a node that writes a pack adds a file; proposing either back is sending the file.' },
    ];
  },
});

});

/* ================================================================= h/mods/claims.js ==== */
/* claims · core · decide
 *
 * Whose word covers how much ground, and how coarse it is by the time it says it. This is the
 * section the dial exists for: a model that samples one point and a probe on a shelf both produce
 * one number, and at the grain the dial is standing on they cover 4,396 cells and 1. Resolution is
 * provenance, and this is where that stops being a footnote.
 *
 * Every footprint is a number a pack or a preset already declares — make-h3.mjs names the file each
 * came from — and the covering was computed at the grain the source itself has and then compacted.
 * The bar under each card is what compactCells left behind: mostly one grain in the middle, striped
 * at the rim.
 *
 * NO PICTURE PER CARD, since 22 September. Each card used to carry a drawing of its own compacted
 * covering — "119 cells, resolutions 5 to 7" — beside a number counting cells at the dial's
 * resolution. The two were about different things: the drawing showed how compactCells packed the
 * footprint, which the striped bar on the same card already showed, and it did not move when the
 * dial moved. Six of them, and not one answered the question its own card asks. The comparison they
 * were reaching for is the rail's, where turning the control is what changes the number, and that
 * is where the drawing went: the rail's fold, in the shell. Reported by Tomas.
 */
PAI_LOAD.push(function () {
'use strict';

const { esc } = window.K;
const { H, km2 } = window.KH;

function claimCard(ctx, c) {
  const RES = ctx.RES;
  const n = c.cells_at[RES];
  const mine = H.claims[H.claims.length - 1];
  const bars = Object.entries(c.drawn.by_res).sort((a, b) => a[0] - b[0]);
  const total = bars.reduce((a, [, v]) => a + v, 0);
  return `<section class="claim" id="claim-${esc(c.key)}" data-component="claim" data-ref="claims">`
    + `<div><h3>${esc(c.name)}</h3>`
    + `<p class="what">${esc(c.what)}</p>`
    + `<div class="facts">`
    + `<div class="fact"><span class="k">covers</span><span class="v">`
    + `<span data-num="claim.${esc(c.key)}.km2" data-cmp="against ${esc(String(mine.area_km2))} `
    + `km², the smallest thing this node says anything about">${esc(String(c.area_km2))}</span> `
    + `km²</span></div>`
    + `<div class="fact"><span class="k">cells at resolution ${RES}</span><span class="v">`
    + `<span data-num="claim.${esc(c.key)}.cells" data-cmp="against 1 cell, which is what a probe `
    + `in this house covers">${n.toLocaleString()}</span></span></div>`
    + (c.native ? `<div class="fact"><span class="k">its own resolution</span><span class="v">`
      + `<span data-num="claim.${esc(c.key)}.native" data-cmp="resolution ${c.native.res}, `
      + `${esc(km2(H.ladder[c.native.res].own_area_m2))} a cell">res ${c.native.res}</span>`
      + `</span></div>` : '')
    + `</div>`
    + `<div class="grainbar" role="img" aria-label="${esc(bars.map(([r, v]) =>
      `${v} cells at resolution ${r}`).join(', '))}">`
    + bars.map(([r, v]) => `<i style="width:${(100 * v / total).toFixed(1)}%;`
      + `background:color-mix(in srgb, var(--cells) ${Math.min(60, (r - 4) * 12)}%, transparent)"`
      + ` title="${v} cells at resolution ${r}"></i>`).join('') + `</div>`
    /* The bar's own caption, which used to sit under a drawing of the same fact. It is here rather
       than absent because a striped bar with nothing naming it is decoration, and the compaction is
       the only thing on this card the bar is about. */
    + `<p class="decl"><span class="cx">${c.drawn.compact} cells, resolutions `
    + `${bars[0][0]}–${bars[bars.length - 1][0]}</span>${esc(c.declared)} · ${esc(c.where)}</p>`
    + `</div></section>`;
}

window.PAI.register({
  id: 'claims', pack: 'core', stage: 'decide', order: 10, learn: ['claims'],
  reads: ['/issues'],
  title: 'Whose word, over how much ground',
  needs: ['H3.claims'],
  render(ctx) {
    /* Every footprint here is a circle or a square drawn around this node. With no coordinates they
       are six coverings of the Gulf of Guinea, and the card that says how much ground a word covers
       would be covering somebody else's water. The declarations are still true; where they sit is
       not known. */
    if (!ctx.KH.sited()) {
      return `<p class="note" id="claims-unsited" data-component="absent" data-ref="claims">This `
        + `node has no coordinates, so there is no ground for these claims to cover. The footprints `
        + `are still declared — ${H.claims.map(c => c.declared).join(' · ')} — and each gets its `
        + `covering as soon as NODE_LAT and NODE_LON are set.</p>`;
    }
    /* FOLDED, for the reason grain's table is: it is evidence and not reading, and since 22 September
       the rail's own fold carries the live version of the comparison these cards were making — what
       each footprint costs to cover at the stop you are standing on, redrawn every time the rail
       moves. The cards keep what the fold does not have: the ground each covers in km², each
       source's native grain, and how its covering was packed. That is a thing to look up, not a
       thing to read past on the way to deciding something. */
    const mine = H.claims[H.claims.length - 1], widest = H.claims[0];
    return `<p class="honest" id="claims-span" data-component="finding" data-ref="claims">`
      + `The widest thing this node says anything about covers `
      + `<span data-num="claim.span" data-cmp="against ${esc(String(mine.area_km2))} km², `
      + `${esc(mine.name.toLowerCase())}, the smallest">${esc(String(widest.area_km2))}</span> km² `
      + `and the narrowest covers ${esc(String(mine.area_km2))}. Both produce one number. What that `
      + `costs at the rung you are standing on is under the ladder, and it moves when the ladder does.`
      + `</p>`
      + `<details class="fold"><summary>All ${H.claims.length}, and the ground each covers</summary>`
      + `<div class="claimgrid">${H.claims.map(c => claimCard(ctx, c)).join('')}</div></details>`;
  },
  wall(ctx) {
    /* The comparison the dial exists to make, as four columns a wall can carry. */
    return H.claims.slice(0, 4).map(c =>
      `<div class="col" data-component="claim" data-ref="wall-lead">`
      + `<h3 data-role="wall-issue">${esc(c.name)}</h3>`
      + `<div class="line"><span class="num" data-num="claim.${esc(c.key)}.cells"`
      + ` data-cmp="cells of resolution ${ctx.RES}; a probe in this house covers 1">`
      + `${c.cells_at[ctx.RES].toLocaleString()}</span><small>cells · ${esc(c.declared)}</small>`
      + `</div></div>`).join('');
  },
  notes() {
    return [
      { id: 'claims-declared', label: 'Every footprint is declared',
        text: 'Every footprint here is a number a pack or a preset already '
        + 'declares — COAST_MAX_KM, BAD_RADIUS_KM, EARTH_RADIUS_M at 10 m a pixel, PLACE_RADIUS_M, '
        + 'LOCAL_RADIUS_M, and the three decimals GET /health rounds a coordinate to, which is about '
        + '110 m and the finest resolution anything from this node may be drawn at. Not one '
        + 'radius on this page was chosen by it.' },
      { id: 'claims-order', label: 'Widest ground first',
        text: 'The cards are ordered by the ground one word covers, widest '
        + 'first. Reading down them is reading from a model that speaks for the sea to a probe on a '
        + 'shelf, and the number that changes with the ladder — cells at this resolution — is how many '
        + 'cells of the rung you are standing on that word has to cover to say its one thing.' },
      { id: 'claims-note', label: 'What a source says of itself',
        text: H.claims.filter(c => c.note).map(c => `${c.name}: ${c.note}.`)
        .join(' ') },
      { id: 'claims-folded', label: 'Why the cards are folded',
        text: 'The six cards are folded for the reason the eleven-row resolution '
        + 'table is: they are evidence and not reading. The comparison they exist to make \u2014 what '
        + 'each of these words costs to cover at one rung \u2014 is under the ladder now, where turning '
        + 'the control is what changes it, which is the one thing these cards could never do.' },
      { id: 'claims-model', label: 'The one with no footprint',
        text: 'The one source with no declared footprint is the model point, '
        + `which covers ${H.claims[0].cells_at[8].toLocaleString()} cells at resolution 8 against `
        + 'the one a probe in this house covers. Nothing in the product says how big a model point’s '
        + 'word is, and the page will not guess for it.' },
    ];
  },
});

});

/* ================================================================= h/mods/grain.js ==== */
/* grain · core · decide
 *
 * What each stop of the dial is worth, end to end: what one cell of it holds, how many cells the
 * fourteen stations fall in there, and which side of the two lines the product already draws it is
 * on. The table is evidence and not reading, so it folds; the finding it produced is printed above
 * it, because that finding is the thing the dial was built to show and nothing in rounds one or two
 * could have shown it: resolutions 7 to 10 are one row repeated four times.
 */
PAI_LOAD.push(function () {
'use strict';

const { esc, fmt, readout, row } = window.K;
const { H, km2, edge } = window.KH;

function table(ctx) {
  const flat = new Set(flatRun(H).map(g => g.res));
  /* PORTED: the table is wider than 390 px and scrolls inside its own box. A box that scrolls and
     cannot be focused cannot be scrolled from a keyboard — the finding that put tabindex on the
     page before this one, re-made here. */
  return `<div class="tblwrap" tabindex="0" role="region" aria-label="all eleven rungs">`
    + `<table class="tbl" id="grain-table" data-component="grainTable" data-ref="grain-line">`
    + `<thead><tr><th>resolution</th><th>one cell</th><th>edge</th>`
    + `<th>cells the ${H.sensors.length} stations fall in</th><th>in this node's own cell</th>`
    + `<th></th></tr></thead><tbody>`
    + H.grain_table.map(g => `<tr class="${g.res === ctx.RES ? 'picked' : ''}${flat.has(g.res)
      ? ' flat' : ''}"><td class="mono">${g.res}</td><td class="mono">${esc(km2(g.area_m2))}</td>`
      + `<td class="mono">${esc(edge(g.edge_m))}</td><td class="mono">${g.occupied}</td>`
      + `<td class="mono">${g.in_my_cell}</td>`
      + `<td>${g.may_leave ? 'may leave' : ''}${g.finer_than_published
        ? 'finer than this node says where it is' : ''}</td></tr>`).join('')
    + `</tbody></table></div>`
    + `<p class="cap">Grey rows are the flat run. The row in bold is where the ladder stands.</p>`;
}

/* THE FLAT RUN, read off the table instead of written down.
 *
 * This was `H.grain_table.filter(g => g.occupied === 9)` — node #1's own flat run as a literal.
 * On that node, on 6 September, nine cells held something from one resolution inward and never
 * changed again. On any other node the filter matched nothing, `flat[0].res` threw, and the whole
 * decide stage printed "grain did not render". That is not a guess: it happened on a live node on
 * 16 September 2026, where the contract's try/catch caught it and the section was lost.
 *
 * What the sentence is about is the tail of the table where turning the dial finer stops telling
 * you anything — the run of rows at the fine end that all report the same number of occupied
 * cells. That is a property of the table, so it is read from the table.
 *
 * Two nodes have no flat run to speak of and each says so rather than being given one: a node whose
 * count is still changing at the finest resolution, and a node with no stations at all, where every
 * row is zero and "the answer never changes" would be true of an empty page. `occupied > 0` is what
 * separates the second from a real finding.
 */
function flatRun(H) {
  const t = (H && H.grain_table) || [];
  if (t.length < 2) return [];
  const last = t[t.length - 1];
  if (!last.occupied) return [];
  let i = t.length - 1;
  while (i > 0 && t[i - 1].occupied === last.occupied) i--;
  const run = t.slice(i);
  return run.length > 1 ? run : [];
}

/* THE GRAIN LINE, which used to be the lead's.
 *
 * It is a sentence about what the picked resolution is worth — one cell's area, how many cells this
 * node's stations fall in, how many are its own — and that is the Decide stage's question, not the
 * lead's. It sat in the lead because the rail sat under the header; with the rail at the top and the
 * lead carrying a monument numeral and four meters, it was six blocks deep and pushing the as-of
 * line off the first screen on a phone. T1's fifth leg, for a paragraph that was in the wrong stage.
 *
 * It keeps its id. It moved to Network with its section in v0.78, and the rail, which stays on Now, points
 * at the ground figure instead (the arm that named `grain-line` would land nowhere on Now). */
function grainLine(ctx) {
  const G = ctx.grain, t = H.grain_table || [], finest = t.length ? t[t.length - 1] : null;
  const n = (H.sensors || []).length;
  if (!window.KH.sited()) {
    return `<p class="why grainline" id="grain-line" data-component="grainLine" data-ref="grain">`
      + `At resolution ${ctx.RES} one cell is ${esc(km2(G.area_m2))}. Which cell this node stands in `
      + `is not known: it has no NODE_LAT/NODE_LON, so none of its ${n} stations has a cell yet and `
      + `the counts that would go here would be counts about open water.</p>`;
  }
  const same = t.filter(g => g.occupied === G.occupied && g.in_my_cell === G.in_my_cell);
  /* A READOUT, not a paragraph. The rail's whole job is to move this number, and a numeral buried
   * mid-sentence is a numeral a reader has to find before they can watch it change — which is the
   * one thing the rail exists to let them do. The sentence is not lost: it is the comparison, which
   * is where a readout keeps the words that qualify its figure. */
  return readout({
    id: 'grain-line', component: 'grainLine', ref: 'grain',
    title: `occupied cells at resolution ${ctx.RES}`,
    num: 'grain.occupied',
    /* "of N stations" and not "of every station this node reads": H.sensors is what /issues
       publishes, which is only what has a coordinate, and the sources rows count the sensor table,
       which is everything. Five of node #1's kits have no coordinate and so fall in no cell — two
       different true numbers on one page, and the shorter label made them look like a
       contradiction. */
    value: G.occupied, dp: 0, unit: `of ${n} with a coordinate`,
    source: 'this node\u2019s own resolution table',
    cmp: { text: `one cell is ${km2(G.area_m2)} here \u00b7 ${G.in_my_cell} station`
      + `${G.in_my_cell === 1 ? '' : 's'} sit in this node's own cell, of which `
      + `${G.mine_in_my_cell} ${G.mine_in_my_cell === 1 ? 'is' : 'are'} its own`
      + (same.length > 1 ? ` \u00b7 resolutions ${same[0].res} to ${same[same.length - 1].res} answer `
        + `this identically` : '')
      + ` \u00b7 against ${finest ? finest.occupied : 0} at resolution ${finest ? finest.res : '?'}, `
      + `the finest this node publishes` },
  });
}

/* The four grains the household actually lives at, side by side: how many cells hold something at
 * each. THE SKETCH STAMPED THIS `example` AND IT SHOULD NOT HAVE — every number is the node's own
 * grain table, computed from the stations it can see, and the stamp said the opposite.
 *
 * Seven to ten because that is where a person lives: a resolution-7 cell is a neighbourhood and a
 * resolution-10 cell is a building. Coarser than 7 and the answer is about an island; finer than 10
 * and, on this node, it has stopped changing — which is itself the finding, and the row says which
 * of the two it is rather than leaving four identical numbers to be read as a mistake. */
const GRAINS = [7, 8, 9, 10];

function fourGrain(ctx) {
  const t = H.grain_table || [];
  const got = GRAINS.map(res => t.find(g => g.res === res)).filter(Boolean);
  if (got.length < 2) return '';
  const vals = got.map(g => g.occupied);
  const flat = vals.every(v => v === vals[0]);
  const settles = got.findIndex((g, i) => i > 0 && vals.slice(i).every(v => v === g.occupied));
  return row({
    id: 'grain-four', component: 'fourGrain', ref: 'grain-line',
    cols: 'minmax(0,210px) minmax(0,1fr) auto',
    left: `<span class="who"><b>Cells with something in them</b>`
      + `<span class="m">resolutions ${got[0].res} to ${got[got.length - 1].res}</span></span>`,
    line: flat
      ? `The same answer at all four. From ${got[0].res} inward this node is buying precision it `
        + `cannot spend: each step is seven times finer and finds nothing new.`
      : settles > 0
        ? `It stops changing at ${got[settles].res}. Finer than that, each step is seven times `
          + `smaller and answers "who is near me" with the same cells \u2014 which is the resolution that `
          + `holds here, and it is a fact about how spread out this node's stations are, not about `
          + `H3.`
        : `Still changing at every step, so the finest resolution in this range is still earning its `
          + `precision on this node today.`,
    qty: got.map(g => ({
      num: `grain.occupied.${g.res}`, value: String(g.occupied),
      cmp: `cells holding a station at resolution ${g.res}, where one cell is `
        + `${edge(g.edge_m)} across`,
    })),
  });
}

/* What leaves this machine about WHERE it is, in the two channels that carry it, at the grain each
 * one is set to. Both numbers are decisions somebody made and can change, so both name the setting.
 *
 * WHY IT IS ON NOW AND THE RADIO CARD IS NOT A DUPLICATE OF IT. The reticulum section says the same
 * thing about the radio, and it lives on Network — so a reader who never leaves Now has until now
 * been told nothing at all about what this node says about its own position. This is the decide
 * stage's question in its plainest form: not what was read, but how coarsely this house is willing
 * to be located, and by whom.
 *
 * The sentences are the node's where the node has one. `publication.why` is written by app/main.py
 * and printed verbatim; the radio has no `why` on the wire, so this composes from the two settings
 * and names them both, which is the next most honest thing to quoting.
 */
function leaves(ctx) {
  const R = H.radio || {}, P = H.publication || {};
  const floor = (H.settings || {}).PRESENCE_RES_FLOOR;
  const pres = (H.settings || {}).RETICULUM_PRESENCE_RES;
  const cols = 'minmax(0,210px) minmax(0,1fr) auto';
  const who = (b, m) => `<span class="who"><b>${esc(b)}</b><span class="m">${esc(m)}</span></span>`;
  return `<div class="reads" id="leaves-rows" data-ref="grain-line">`
    + row({ id: 'leaves-radio', component: 'leaves', ref: 'grain-line', cols,
      left: who('Over the radio', `RETICULUM_PRESENCE_RES ${pres == null ? '\u2014' : pres}`),
      line: `A cell and nothing else \u2014 never a coordinate. A stranger listening learns which `
        + `${km2(R.area_m2)} of the planet this node is somewhere inside, and no settings box may `
        + `take it finer than resolution ${floor}: that floor is in app/main.py, not in a form.`,
      qty: [{ num: 'leaves.radio', value: edge(R.edge_m),
        cmp: `to an edge of the cell this node announces itself in, at resolution ${R.res}` }] })
    + row({ id: 'leaves-health', component: 'leaves', ref: 'grain-line', cols,
      left: who('In GET /health', `${P.decimals} decimals`),
      line: P.why || `Latitude and longitude are rounded before they are published.`,
      qty: [{ num: 'leaves.health', value: `${P.metres} m`,
        cmp: `how far the published coordinate may be from the real one \u00b7 about a resolution-`
          + `${P.res} cell` }] })
    + `</div>`;
}

/* The shape every issue's sentence takes, with this node's headline issue as the worked instance.
 *
 * WHY IT BELONGS TO DECIDE. This stage answers what may be said about a reading and at what grain.
 * The sentence is the answer — it is the one place the node commits to words — and a reader who can
 * see its grammar can parse any of the four, including the ones that read strangely because the
 * data is strange rather than because the sentence is wrong.
 *
 * NOTHING HERE IS COMPOSED IN THE BROWSER. The sentence is the node's, verbatim, in `.said`. What
 * this adds is the naming of its parts, which is the page's own job: the node writes the sentence,
 * the page says what kind of sentence it is. */
function template(ctx) {
  const k = S.issues.headline, d = ISS[k];
  if (!d || !d.sentence) return '';
  const cell = (d.stack || {})[d.headline] || {};
  const others = (DIST || []).filter(x => x !== d.headline && ((d.stack || {})[x] || {}).value != null);
  return `<div class="reads" id="template-rows" data-ref="grain-line">`
    + row({ id: 'sentence-shape', component: 'template', ref: 'grain-line',
      cols: 'minmax(0,210px) minmax(0,1fr) auto',
      left: `<span class="who"><b>How a sentence is built</b>`
        + `<span class="m">the same for all ${(ORDER || []).length}</span></span>`,
      line: `The headline speaks in words only (sentence), \`plain\` carries the figures, \`about\` says what the metric is.`,
      qty: [{ num: 'template.parts', value: `${2 + (others.length ? 1 : 0)} parts`,
        cmp: `state \u00b7 the ${LAB[d.headline]} reading`
          + `${others.length ? ` \u00b7 ${others.length} other distance`
            + `${others.length === 1 ? '' : 's'} compared` : ''}` }] })
    + `<p class="tmplex" id="sentence-example" data-ref="sentence-shape">`
    /* The issue's NAME is the node's word and must not be shouted with the rest of the label —
       `µ` uppercases to `M`, and a pack may name an issue anything. Page words shout, node words
       sit in .said, which is the rule check_ui holds every uppercase rule to. */
    + `<span class="k">as written now, for <span class="said">${esc(d.name[LOC])}</span></span>`
    + `<span class="said">${esc(d.sentence[LOC])}</span>`
    + `<span class="m">state <b>${esc(d.state)}</b> \u00b7 closest distance with a reading, the `
    + `<b>${esc(LAB[d.headline])}</b>, at <b>${esc(cell.value == null ? '\u2014'
      : fmt(cell.value, d.dp))} ${esc(d.unit || '')}</b>`
    + `${others.length ? ` \u00b7 against ${others.map(x => esc(LAB[x])).join(' and ')}` : ''}</span>`
    + `</p></div>`;
}

window.PAI.register({
  id: 'grain', pack: 'core', stage: 'decide', order: 20, learn: ['containment'],
  reads: ['/issues'],
  title: 'What each rung is worth',
  needs: ['H3.grain_table'],
  render(ctx) {
    const flat = flatRun(H);
    const rows = (H.grain_table || []).length;
    const finding = flat.length
      ? `<p class="honest" id="flat-run" data-component="finding" data-ref="grain-line">Resolutions `
        + `${flat[0].res} to ${flat[flat.length - 1].res} are one row repeated ${flat.length} times. `
        + `Each is seven times finer than the one above it — `
        + `<span data-num="grain.flat.ratio" data-cmp="the area ratio across ${flat.length - 1} steps `
        + `of seven">${Math.pow(7, flat.length - 1).toLocaleString()}</span> times smaller by area over `
        + `the ${flat.length} — and every one of them answers "who is near me" with the same `
        + `${flat[0].occupied} cells and the same ${flat[0].mine_in_my_cell} sensors.</p>`
      /* No flat run is not a failure and not a blank: it is a different node, and the table below is
         still worth reading. The two cases are named apart because they mean opposite things —
         nothing to file, against a grain that is still earning its precision at the finest stop. */
      : `<p class="honest" id="flat-run" data-component="finding" data-ref="grain-line">`
        + (H.sensors && H.sensors.length
          ? `On this node on this day the count of occupied cells is still changing at the finest `
            + `resolution in the table, so there is no flat run to report: every rung of the ladder is `
            + `still earning its precision. The table below is the whole of it.`
          : `No station on this node carries a coordinate, so every resolution files the same nothing `
            + `and there is no resolution to compare. The table below is still this node's own arithmetic: `
            + `what one cell is worth at each of the ${rows} rungs.`)
        + `</p>`;
    return grainLine(ctx) + fourGrain(ctx) + leaves(ctx) + template(ctx) + finding
      + `<details class="fold"><summary>All eleven rungs, and what each is worth</summary>`
      + table(ctx) + `</details>`;
  },
  notes() {
    const flat = flatRun(H);
    return [
      /* Every number in this note was node #1's, spelled out in words — "four stops", "the same
         nine cells", "the same three sensors". They are this node's now, and the note is only made
         at all where there is a flat run to make it about. */
      ...(flat.length ? [{ id: 'grain-flat', label: 'Where resolution stops saying anything',
        text: `Past resolution ${flat[0].res}, on this node on `
        + `this day, resolution is precision with no information in it. ${flat.length} rungs of the ladder, `
        + 'each seven times finer than the last, and the answer to "who is near me" does not change: '
        + `the same ${flat[0].occupied} cells hold something and the same ${flat[0].mine_in_my_cell} `
        + 'sensors sit in this node’s own cell. Nothing in the first two rounds of drawings could '
        + 'have shown this, because nothing in them varied the resolution.' }] : []),
      { id: 'grain-lines', label: 'The two marks on the ladder',
        text: `The two marks on the ladder are the product’s own lines, not this `
        + `page’s. Resolution ${H.settings.PRESENCE_RES_FLOOR} and coarser may leave this machine — `
        + `it is PRESENCE_RES_FLOOR in app/main.py, the finest any node may announce. Past resolution `
        + `${H.publication.res} is finer than this node is willing to say where it is: GET /health `
        + 'rounds a coordinate to three decimals, about 110 m, and no reading from it may be drawn '
        + 'finer than that.' },
      { id: 'grain-folded', label: 'Why the table is folded',
        text: 'The eleven-row table is folded because it is evidence and not '
        + 'reading. Measured, it was half a screen of a page that was already long, and the one '
        + 'sentence it exists to support is printed above it in full.' },
    ];
  },
});

});

/* ================================================================= h/mods/asks.js ==== */
/* asks · core · act
 *
 * What this node has asked of whom. The loop's third stage is the one a household actually feels:
 * a rule crossed a line, the node said so on Telegram, and somebody either did something or did
 * not. This section is the ledger of that — the open ask, the asks sent in the window, and the
 * funnel they went down — so that "act" is a thing on the page and not a verb in a slogan.
 *
 * The strip that used to sit above this is gone: the buttons are on Decide now, and this section is
 * only the record of what was asked and what was answered (docs/SPEC_dashboard_events.md §4.3).
 */
PAI_LOAD.push(function () {
'use strict';

const { esc, fmt, age, pill, row, sign, rulePack, evState, evClock, evWord } = window.K;

/* The alerts in the fixture that asked for something, most recent first. `level: act` is the rule
 * saying a person should do something; `info` and `warn` said something and asked nothing. They
 * come through h3.js, which make-h3.mjs fills from the fixture: the id, the rule, the first line. */
const A = () => (window.H3 && window.H3.asks) || { acts: [], actions: [], levels: {} };
const ACTS = () => A().acts.slice().sort((a, b) => b.ts.localeCompare(a.ts));

/* Which asks are still open, from the node's own answer and never from a copy of its rule.
 *
 * `CLOSED_STAGES` is ("acted", "measured") in app/issues/schema.py — acknowledged does NOT close an
 * ask — and the node has already applied it: an alert in an issue's `open_asks` is open and one
 * that is not is closed. So the ring reads membership, and this page holds no second copy of a rule
 * it does not own. Publishing `closed_stages` on /issues would have been the other way to do it,
 * and it would have been a field the node does not have for an answer the node already gives. */
const OPEN_IDS = () => new Set((ORDER || Object.keys(ISS))
  .flatMap(k => ((ISS[k] || {}).open_asks || []).map(a => a.id)));

/* One ring an ask, closed first, with the unit changed rather than the row silently truncated when
 * a rule has asked more times than a person can count. Same grammar as the \u03c1 row, same reason. */
function ringsFor(list, open) {
  const total = list.length, closed = list.filter(a => !open.has(a.id)).length;
  /* One ring an ask up to 80, because the strip has a grid row to itself and 52 of them fit on two
   * lines. It was 24, which put this node's busiest rule on a unit of ten — five rings for 52 asks,
   * and its one closed ask rounding to zero filled rings. The count beside it said 1/52 while the
   * drawing said nothing had been done, which is the failure a unit is supposed to prevent, not
   * cause. A node with hundreds still gets a unit rather than a wall of rings. */
  const UNIT = total <= 80 ? 1 : total <= 800 ? 10 : 100;
  const rings = Math.round(total / UNIT);
  /* Any progress shows. At a unit above one, a closed count smaller than the unit would round to no
   * filled rings at all — so it is floored at one ring, and the numeral beside it carries the exact
   * figure that a rounded ring cannot. */
  const full = closed > 0 ? Math.max(1, Math.round(closed / UNIT)) : 0;
  let out = '';
  for (let i = 0; i < rings; i++) {
    out += sign(i < full ? 'rho-closed' : 'rho-open', i < full ? 'closed' : '', i < full ? 'An answered alert' : 'An alert still open');
  }
  return { html: out, closed, total, unit: UNIT };
}

/* THE EVENTS ACT RECORDS: the node's open and recent ones, newest opened first. `recent` is sorted by clear
 * and `open` by seriousness, so neither order is the one a record reads in. An id in both is drawn once. */
function evLog(E) {
  const seen = new Set();
  return [...(E.open || []), ...(E.recent || [])].filter(e => !seen.has(e.id) && seen.add(e.id))
    .sort((a, b) => String(b.opened_at).localeCompare(String(a.opened_at)));
}
/* What was answered, in the button's word. `cleared_after_min` is the node's number, and only a Done that
 * was followed by a clear carries it, so it is said only then. */
function evAnswerText(e) {
  const a = e.answer;
  if (!a) return 'no answer';
  return a.stage !== 'acted' ? evWord(a.stage)
    : `${evWord(a.stage)} \u00b7 ${a.actor || 'somebody'}`
      + (e.cleared_after_min == null ? '' : ` \u00b7 cleared ${Math.round(e.cleared_after_min)} min after`);
}

/* WHERE TO GO, under the ask it answers.
 *
 * The `make` pack stores fab labs on /sensors as `kind === 'facility'` — a place, not a station, and
 * every count on this page filters them out. The SENTENCE is the pack's, from /issues.asks.where,
 * and it already names the nearest lab, the distance and the top three machines in the reader's
 * language. The page does not compose it and does not translate: `meta.capabilities` arrives as raw
 * tokens (`three_d_printing`) and CAPABILITY_WORDS lives in the pack, so drawing the tokens here in
 * English would be this file inventing a vocabulary it does not own. See the STOP in the handoff.
 *
 * `cached` and not `live` or `partial`: a monthly archive is neither. The date drawn is the SNAPSHOT
 * filename, not the day the node fetched it — what a reader needs to know is how old the directory
 * is, not how recently this machine copied it.
 *
 * With the pack off there is no row, and the section says so in the NODE'S OWN WORDS — the help
 * text /settings publishes for MAKE_ENABLED, which carries the licence sentence a keeper should
 * read before turning it on. Never this page's paraphrase of it. */
function whereToGo() {
  const labs = (window.SENSORS || []).filter(x => x.kind === 'facility');
  const said = ((A() || {}).where || {})[LOC];
  /* The learn mark for the thread from a reading to a place that makes things sits on this row
     rather than in Act's kicker: it is about this row, and the row is where the pack's sentence is.
     Drawn in both branches, because the pack being off is the case a reader most needs explained. */
  const mark = ref => (window.PAI_LEARN ? window.PAI_LEARN.mark('workshop', ref) : '');
  if (!labs.length) {
    const h = ((window.SETTINGS_RAW || {}).runtime || [])
      .find(r => r.key === 'MAKE_ENABLED') || {};
    return `<p class="note" id="where-off" data-ref="asks-rows">`
      + (h.help
        ? `No place to get something made is listed here. <span class="said">${esc(h.help)}</span>`
        : `No place to get something made is listed here, and this node does not say why: it `
          + `carries no MAKE_ENABLED setting, so its image predates the pack that would.`)
      + mark('where-off') + `</p>`;
  }
  const near = labs.slice().sort((a, b) =>
    ((a.meta || {}).distance_km ?? 1e9) - ((b.meta || {}).distance_km ?? 1e9))[0];
  const m = near.meta || {};
  return row({ id: 'where-to-go', component: 'whereToGo', ref: 'asks-rows',
    cols: 'minmax(0,210px) minmax(0,1fr) auto',
    href: m.url || null,
    left: `<span class="who"><b>${esc(near.name)}</b>`
      + `<span class="m mono">${m.distance_km == null ? '\u2014' : `${m.distance_km} km`}</span></span>`,
    /* No sentence is a real state and not a blank: the pack composes it and a node whose pack could
       not be loaded sends null, which is what this said on every node until packs.module() landed. */
    line: said || `${labs.length} place${labs.length === 1 ? '' : 's'} stored, and this node sent no `
      + `sentence for them \u2014 the facts are here and the wording is the pack's to write.`,
    qty: [{ num: 'where.km', value: esc(String(m.snapshot || 'no date')),
      cmp: `the dated archive this came from \u2014 not when this machine copied it`
        + `${m.attribution ? ` \u00b7 ${m.attribution}` : ''}` }] })
    + `<p class="note" id="where-prov" data-ref="where-to-go">${pill('cached')} A monthly archive `
    + `is neither live nor partial. ${labs.length > 1 ? `${labs.length} are stored; the nearest is `
      + `drawn.` : ''}${mark('where-to-go')}</p>`;
}

/* THE HOUSEHOLD'S OWN CAPACITY, where the node has any. A purifier's filter life is the first thing
 * this node knows about a machine the household owns rather than about the air — `device_health`,
 * never a measurement (packs/xiaomi-air/channels.yml says so and marks it `comparable: false`). It
 * is a row with its own sign and never a sensor tile, because a tile beside the air readings would
 * put a consumable on the same footing as a reading of the room. */
function capacity() {
  /* null when the node has no appliance to ask about, which is why /stats was never fetched (see
     boot). An empty row here would be the page claiming it looked. */
  const rows = (window.STATS || []).filter(r => r.metric === 'filter_life');
  if (!rows.length) return '';
  return rows.map(r => row({ id: `capacity-${esc(r.sensor_id)}`, component: 'capacity',
    ref: 'asks-rows', cols: 'minmax(0,210px) minmax(0,1fr) auto',
    left: `<span class="who"><b>${esc(r.name || r.sensor_id)}</b>`
      + `<span class="m">filter life</span></span>`,
    signs: sign('machine'),
    line: `What this household can still do about its own air without asking anybody. A filter is a `
      + `consumable, not a reading: it says how much of this machine is left, never how the room is.`,
    qty: [{ num: `capacity.${esc(r.sensor_id)}.filter`,
      value: `${fmt(r.last, 0)}%`,
      cmp: `of this filter's life remaining \u00b7 device health, and the node marks it not `
        + `comparable with anything else on this page` }] })).join('');
}

window.PAI.register({
  id: 'asks', pack: 'core', stage: 'act', order: 10, learn: ['levels', 'current'],
  reads: ['/issues', '/rho', '/sensors', '/settings', '/stats'],
  /* `workshop` is drawn by whereToGo() on the row it explains, not in the kicker. */
  title: 'What was asked, and what was answered',
  /* PORTED: the prototype also needed SNAP.funnel, which was one of its three synthetic
     contributions — no endpoint on this node computes a stage split or the 2x2. The ledger is the
     node's own (GET /issues publishes `asks`), so the section stands on that and draws the funnel
     only where there is one. */
  needs: ['H3.asks'],
  render(ctx) {
    const S = ctx.S, ISS = ctx.ISS, st = evState(), E = S.issues.events || {};
    const acts = ACTS();
    const open = OPEN_IDS();
    const byRule = {};
    for (const a of acts) (byRule[a.rule_id] = byRule[a.rule_id] || []).push(a);
    const rules = Object.entries(byRule).sort((a, b) => b[1].length - a[1].length);
    const captured = Date.parse(S.base.captured_utc);
    /* ONE COLUMN, FULL WIDTH. This was a `two-up` with a single child, so the grid reserved half the
       band for a second column that no branch of this render ever fills — every rule row was squeezed
       into the left half and the right half of Act was white. `two-up` is for the sections that
       genuinely draw two things; Act draws one list. THE STRIP IS GONE from every node: Decide holds the
       buttons now (spec §4.3), and this is the record of what was asked and answered. */
    const byRuleRows = () => rules.map(([rule, list]) => {
        /* A rule id is `pack/rule` today, but a node's ledger keeps alerts from before packs named their
           rules (node #1: `indoor_pm25_high`, `inside_worse_ventilate`), and splitting those left the rule
           undefined, which threw and took the whole section down on 28 Sep 2026. */
        const pack = rulePack(rule), id = pack ? rule.slice(pack.length + 1) : rule;
        const r = ringsFor(list, open);
        const latest = list[0];
        /* LEVEL IN WEIGHT, never hue: an `act` ask is one somebody was asked to do something about
           and a `warn` is one a keeper should know about, so the first is drawn at full weight and
           the rest quieter. The level is the node's, per alert. */
        return row({ id: `ask-rule-${esc(id)}`, component: 'askRule', ref: 'asks-rows',
          cls: latest.level === 'act' ? '' : 'quiet',
          cols: 'minmax(0,210px) minmax(0,1fr) auto',
          left: `<span class="who"><b>${esc(id.replace(/_/g, ' '))}</b>`
            + `<span class="m">${pack ? `${esc(pack)} · ` : ''}last ${esc(age(Math.round((captured
              - Date.parse(latest.ts)) / 60000)))}</span></span>`,
          /* RAW, not escaped: row() escapes `line` itself, so escaping here sends &quot; and &amp;
             through to the screen. Node #1's alert text has no such character today, which is why
             this survived — the effect section's own line, which has a quoted word in it, is where
             it showed. */
          line: String(latest.text || '').split('\n')[0].slice(0, 140),
          signs: r.html,
          qty: [{ num: `asks.${esc(id)}.sent`, value: `${r.closed}/${r.total}`,
            cmp: `closed of asked in the window \u2014 an alert closes when somebody acted or the `
              + `outcome was measured, never merely by being seen`
              + `${r.unit > 1 ? ` \u00b7 one ring per ${r.unit}` : ''}` }],
        });
      }).join('');
    /* ONE ROW AN EVENT, newest first, and the rings above them: closed when the event has an answer. The
       seven days are all the wire carries, so there is no fold. */
    const eventRows = () => {
      const log = evLog(E);
      if (!log.length) {
        return `<p class="note" id="asks-none" data-component="absent" data-ref="asks-rows">No event in the `
          + `last 7 days: nothing was asked, and nothing needed asking.</p>`;
      }
      const unanswered = new Set(log.filter(e => !e.answer).map(e => e.id));
      const r = ringsFor(log, unanswered);
      const head = row({ id: 'asks-events', component: 'askEvents', ref: 'asks-rows', cols: 'minmax(0,1fr)',
        left: `<span class="who"><span><span data-num="asks.events.n" data-cmp="alert events this node opened `
          + `in the last 7 days, open or cleared">${log.length}</span> event${log.length === 1 ? '' : 's'} in 7 `
          + `days \u00b7 <span data-num="asks.events.answered" data-cmp="of ${log.length}: events somebody `
          + `answered with Done, Not now or Doesn\u2019t fit">${r.closed}</span> answered</span></span>`,
        signs: r.html });
      return head + log.map(e => {
        const d = ISS[e.issue] || { name: {} };
        const key = esc(String(e.id));
        const mins = Math.round((captured - Date.parse(e.opened_at)) / 60000);
        return row({ id: `ask-ev-${key}`, component: 'askEvent', ref: 'asks-rows',
          cls: e.answer && e.answer.stage === 'acted' ? '' : 'quiet',
          cols: 'minmax(0,170px) minmax(0,1fr) auto',
          left: `<span class="who"><b>${esc(d.name[ctx.LOC] || e.issue)}</b>`
            + `<span class="m">${esc(e.kind)} \u00b7 ${esc(age(mins))}</span></span>`,
          line: `${evClock(e.opened_at)}\u2013${e.cleared_at ? evClock(e.cleared_at) : 'open'}`
            + `${(e.rooms || []).length ? ` \u00b7 ${e.rooms.join(', ')}` : ''}`
            /* The action is a sentence, so it rides the wrapping middle column: `qty` does not wrap. */
            + ` \u00b7 \u201c${e.action && e.action.text ? e.action.text : 'no action chosen'}\u201d`,
          qty: [{ num: `ev.${key}.answer`, value: evAnswerText(e),
            cmp: 'the answer a person gave, in the button\u2019s word; the clear time is the node\u2019s own' }] });
      }).join('');
    };
    const events = st === 'events' || st === 'shadow';
    return `<div>`
      + `<div class="reads" id="asks-rows" data-ref="funnel">`
      + (events ? eventRows()
        /* `error` says what the node said (spec §5), escaped; `rules` and `old` say the one sentence. */
        : `<p class="note" id="asks-engine" data-component="absent" data-ref="asks-rows">`
          + (st === 'error' ? esc(E.error) : 'This node sends alerts, not events.') + `</p>` + byRuleRows())
      + whereToGo()
      + capacity()
      + `</div>`
      + `</div>`;
  },
  wall(ctx) {
    const acts = ACTS();
    /* GET /rho is its own route and may be slow, refused or absent. The contract's per-section catch
       would swallow a throw here and the fragment would simply vanish from the wall, which is the
       silence this guard exists to remove: the count of asks is this section's own and is known
       either way, so it is printed, and the comparison says plainly what is not on this node. */
    const r = ctx.S.rho;
    return `<div class="col" data-component="asksCount" data-ref="wall-lead">`
      + `<h3 data-role="wall-issue">Alerts sent</h3>`
      + `<div class="line"><span class="num" data-num="asks.sent" data-cmp="${r
        ? `against ${r.acted} answered`
        : 'how many were answered is not on this node right now: GET /rho did not come back'}">`
      + `${acts.length}</span><small>${r ? `in ${r.window_days} days` : 'in the window'}`
      + `</small></div></div>`;
  },
  notes(ctx) {
    return [
      { id: 'asks-what', label: 'What an alert is',
        text: 'An alert is a rule crossing a line and the node saying so to a '
        + 'person, on Telegram. It is the only thing on this page that is addressed to somebody; '
        + 'everything else is addressed to nobody in particular. "Nothing has been asked" and '
        + '"nothing to do" are two different sentences, and Act says which one is true: a row for every event '
        + 'that was asked, or the sentence that there was none.' },
      { id: 'asks-rows', label: 'One ring, one event',
        text: 'On a node that tells events, one ring an event, closed when somebody answered it with Done, '
        + 'Not now or Doesn\u2019t fit, and a row under them for each of the last seven days\u2019 events: '
        + 'what the node asked for, in its own words, and the answer. \u201cCleared 40 min after\u201d is '
        + 'the node\u2019s own number, and appears only on a Done that a clear followed. On a node that '
        + 'sends alerts, one ring an alert, closed when somebody acted or the outcome was measured \u2014 '
        + 'which is the node\u2019s rule and not this page\u2019s \u2014 and a rule that has asked more '
        + 'times than a person can count gets a coarser unit and says which.' },
      { id: 'where-to-go', label: 'The nearest place to get it made',
        text: 'The nearest place you could get something made, under the alert it '
        + 'answers rather than as a tile of its own \u2014 the pack that stores it says the line belongs '
        + 'to the moment you have been told you need something made. The sentence is the pack\u2019s, '
        + 'including which lab and how far; the page draws it and does not compose it. The date is '
        + 'the archive\u2019s, not the day this machine copied it, because what matters is how old the '
        + 'directory is. `cached`, because a monthly archive is neither live nor partial. A lab is '
        + 'never a station: no count on this page includes it.' },
      { id: 'where-prov', label: 'Why that directory ships off',
        text: 'The directory this reads is not openly licensed, which is why the '
        + 'pack ships off and why the switch carries that sentence where a keeper will read it '
        + 'before turning it on. With the pack off this row does not exist and the node\u2019s own '
        + 'words say why \u2014 never this page\u2019s summary of them.' },
    ];
  },
});

/* ================================================================= h/mods/effect.js ==== */
/* effect · core · measure
 *
 * WHICH OF THIS HOUSEHOLD'S ACTIONS WORK. The node learning about itself rather than about the
 * weather: anybody can draw a year of PM2.5, and only this node can say which of the things done
 * about it were followed by the condition stopping.
 *
 * TWO QUESTIONS, TWO KINDS OF EVIDENCE, DRAWN APART.
 *
 *   cleared  — the funnel's own derivation, per rule: an act followed by a full window of silence
 *              from the same rule on the same sensor. Works for every rule, needs no threshold, and
 *              answers WHETHER. It cannot answer when: the rule re-fires the moment its cooldown
 *              expires while the condition holds, so one cooldown is the finest it can ever resolve.
 *   hours    — the other question, and it needs the readings and a line to come back under. Only a
 *              rule carrying `watch: {metric, over}` has one; the rest fire on a RELATION ("inside
 *              is worse than outside") where a threshold would be invented. Those say so.
 *
 * On node #1 this already found the thing it exists to find: thirteen acts on heat_stress_now and
 * NONE of them cleared, because heat does not stop because somebody acted, while ventilating cleared
 * four of nine. A household that reads that stops pressing the heat one and starts opening windows.
 */
PAI_LOAD.push(function () {
'use strict';

const { esc, row, rulePack } = window.K;

function name(id) { return String(id).split('/').pop().replace(/_/g, ' '); }

window.PAI.register({
  id: 'effect', pack: 'core', stage: 'measure', order: 20, learn: ['effect'],
  reads: ['/effect'],
  title: 'Which of these worked',
  needs: ['EFFECT.rules'],
  anchor: 'effect',
  render(ctx) {
    const E = window.EFFECT, rules = E.rules || [];
    if (!rules.length) {
      return `<p class="note" id="effect-none" data-component="absent" data-ref="measure">`
        + `Nobody has acted on an alert here yet, or not long enough ago to judge: this waits `
        + `${E.window_hours} hours after an act before asking whether the condition stopped. `
        + `Nothing is missing.</p>`;
    }
    const worst = rules.filter(r => r.acted >= 3 && r.cleared === 0)[0];
    const best = rules.slice().filter(r => r.acted >= 3 && r.cleared > 0)
      .sort((a, b) => (b.cleared / b.acted) - (a.cleared / a.acted))[0];
    /* The finding above the evidence, as everywhere else here. The one worth printing is a rule
       people keep answering that never clears — that is a household spending effort on something
       that does not respond, and nothing else on this page could ever have told them. */
    const finding = worst
      ? `<p class="honest" id="effect-finding" data-component="finding" data-ref="effect">`
        + `<b>${esc(name(worst.rule_id))}</b> has been acted on `
        + `<span data-num="effect.worst" data-cmp="times, and the condition did not stop within `
        + `${E.window_hours} hours on any of them">${worst.acted}</span> times and the condition did `
        + `not stop once.${best ? ` <b>${esc(name(best.rule_id))}</b> stopped ${best.cleared} of `
          + `${best.acted} times.` : ''} Acting is not the same as it working, and this is the only `
        + `place that says which.</p>`
      : '';
    return finding + `<div class="reads" id="effect-rows" data-ref="measure">`
      + rules.map(r => {
        const pct = r.acted ? Math.round((r.cleared / r.acted) * 100) : 0;
        /* `hours` is null on every rule with no watch, and on a watched rule whose acts all came too
           late or whose trigger is finer than the hourly record. Each says which. */
        const timed = !r.watch
          ? 'what "recovered" means here is a relation, not a line \u2014 nothing to time against'
          : r.hours != null ? `typically ${r.hours} h to come back under ${r.watch.over}`
            : r.already ? `${r.already} act${r.already === 1 ? '' : 's'} could not be timed: the `
              + `reading was already back under ${r.watch.over} at that hour`
              : 'no act on this one has been timed yet';
        return row({ id: `effect-${esc(name(r.rule_id).replace(/ /g, '-'))}`,
          component: 'effectRule', ref: 'effect-rows',
          cls: r.cleared ? '' : 'quiet',
          cols: 'minmax(0,210px) minmax(0,1fr) auto',
          left: `<span class="who"><b>${esc(name(r.rule_id))}</b>`
            + `<span class="m">${esc(rulePack(r.rule_id))}</span></span>`,
          line: timed,
          qty: [{ num: `effect.${esc(name(r.rule_id).replace(/ /g, '-'))}`,
            value: `${r.cleared}/${r.acted}`,
            cmp: `stopped within ${E.window_hours} hours of somebody acting, of the acts on this `
              + `rule \u2014 ${pct}%. Evidence that the condition ended, never that the act ended it` }],
        });
      }).join('') + `</div>`;
  },
  notes(ctx) {
    const E = window.EFFECT || {};
    return [
      { id: 'effect-not-cause', label: 'Stopped after, not stopped by',
        text: `This says a condition stopped within ${E.window_hours} hours `
        + 'of somebody acting. It does not say the act stopped it. A window opened at nine in the '
        + 'evening and air that cleared by three in the morning may be the window or may be the '
        + 'night, and this node cannot tell the two apart \u2014 so it reports the elapsed time and '
        + 'leaves the causation to the household that was there.' },
      { id: 'effect-two-evidences', label: 'Whether, and how long',
        text: 'Whether and how long are different questions with '
        + 'different evidence. Whether comes from the rule going quiet, which works for every rule '
        + 'and resolves no finer than one cooldown, because the rule re-fires as soon as its '
        + 'cooldown expires while the condition holds. How long needs an indicator and a line to '
        + 'come back under, which only a rule carrying `watch:` has \u2014 the others fire on a '
        + 'relation, where a threshold would be invented.' },
      { id: 'effect-coarser', label: 'When the history is coarser',
        text: 'Where a rule triggers on a fifteen-minute mean and the only '
        + 'history a node keeps is hourly, the timing is coarser than the trigger: a short spike can '
        + 'fire an alert without the hour it sits in ever crossing the line, and then there is '
        + 'nothing to time. Those acts are counted and named rather than folded in as an instant '
        + 'recovery, which is what a nought would have claimed.' },
      { id: 'effect-retired', label: 'A rule that can never fire',
        text: 'A rule that has been renamed or deleted is left out entirely. '
        + 'It can never fire again, so its silence is not evidence of anything \u2014 counting it '
        + 'turned three retired rules into successes on this node once, and made the funnel say '
        + 'eight where the true number was five.' },
    ];
  },
});

});

/* ================================================================= h/mods/shape.js ==== */
/* shape · core · historical
 *
 * THE DAY THIS PLACE USUALLY HAS — the first thing this node learns rather than reads.
 *
 * Every other section on this page says what is true now, or what was true at some moment. This one
 * says what is USUALLY true, which a node can only say once it has watched for a while, and which
 * gets better the longer it runs. It is the smallest honest piece of docs/SPEC_decide.md §11.
 *
 * WHAT MAKES IT HONEST IS THE REFUSAL, not the drawing. `GET /shape` returns `days` — how many
 * distinct local days this node's OWN stations have for this metric — and `windows`, which is what
 * that record can support. A node installed this morning gets one day and is told so; it is not
 * shown a week it has not seen. The temptation this section exists to resist is describing a pattern
 * from three points, and the node decides that question, not this page.
 *
 * INDOOR AND OUTDOOR ARE DRAWN APART because on node #1 they are anti-phased — inside peaks at meal
 * times, outside peaks in the evening — and at midday inside is twice outside while at six in the
 * evening it is the reverse. One line averaging both would describe neither and would hide the only
 * thing in here a household can act on.
 */
PAI_LOAD.push(function () {
'use strict';

const { esc, fmt, strips } = window.K;

/* Historical asks for its 90 days when it is first drawn (askDays90 in the shell), so for one render there is
   nothing yet. A live node that has not answered is pending; a capture (its days are set at boot), or a node that
   answered or refused (DAYS90_DONE), is not. */
const DAYS90_PENDING = () => !window.SNAP.fixture && !window.DAYS90_DONE;

/* The two hours worth naming: where each line is highest. A shape nobody reads off the drawing is a
   drawing; the sentence is the finding. */
function peak(hours, key) {
  const got = hours.filter(h => h[key] != null);
  if (!got.length) return null;
  return got.reduce((a, b) => (b[key] > a[key] ? b : a));
}
const hh = h => `${String(h).padStart(2, '0')}:00`;

window.PAI.register({
  id: 'shape', pack: 'core', stage: 'observe', order: 15, learn: ['shape', 'strips'],
  reads: ['/issues/days', '/shape'],
  title: 'The day this place usually has',
  needs: [],
  anchor: 'shape',
  render(ctx) {
    const S = window.SHAPE || {}, hours = S.hours || [];
    const D = window.DAYS90;
    /* The finding is an average and waits for a week; the strips are not an average and draw what there is. */
    const pin = peak(hours, 'indoor'), pout = peak(hours, 'outdoor');
    const finding = !S.windows || !S.windows.day
      ? `<p class="note" id="shape-young" data-component="absent" data-ref="reach">`
        + `This node has ${S.days === 1 ? 'one day' : `${S.days || 0} days`} of its own readings. `
        + `The usual hour of the worst air waits for seven \u2014 about ${Math.max(1, 7 - (S.days || 0))} more. `
        + `The days it has are drawn below as they were.</p>`
      : pin && pout
        ? `<p class="honest" id="shape-finding" data-component="finding" data-ref="shape">`
          + `Over ${S.days} days, the air in this house is worst around `
          + `<span data-num="shape.indoor.peak" data-cmp="against ${esc(fmt(pout.indoor, 1))} outside `
          + `at the same hour">${esc(hh(pin.hour))}</span> and the air outside is worst around `
          + `<span data-num="shape.outdoor.peak" data-cmp="against ${esc(fmt(pin.outdoor, 1))} inside `
          + `at the same hour">${esc(hh(pout.hour))}</span>`
          + `${pin.hour !== pout.hour ? ' \u2014 they do not peak together, so there are hours when '
            + 'opening a window helps and hours when it does not' : ''}.</p>`
        : '';
    if (DAYS90_PENDING()) {
      return finding + `<p class="note" id="shape-days" data-ref="shape">Asking the node for the days it holds\u2026</p>`;
    }
    return finding + `<div id="shape-strips" data-ref="shape">`
      + ctx.ORDER.filter(k => ctx.ISS[k] && ctx.ISS[k].watched !== false)
        .map(k => strips(k, D, { id: `hstrips-${esc(k)}`, ref: 'shape-strips' })).join('')
      + `</div>`;
  },
  notes() {
    const S = window.SHAPE || {};
    return [
      { id: 'shape-local-hours', label: 'The hours are this node’s own',
        text: 'The hours are this node\u2019s own, not UTC. Postgres answers '
        + '`extract(hour FROM ...)` in the session timezone and defaults to UTC, so the same query '
        + 'run outside the node\u2019s own connection moves this whole drawing by eight hours on a node '
        + 'in Bali and reports a midday cooking peak as a four-in-the-morning one. db() sets the '
        + 'timezone from NODE_TZ on every connection, and its comment records that this was found '
        + 'once before, in the day boundaries.' },
      { id: 'shape-two-lines', label: 'Why inside and outside are apart',
        text: 'The strips draw the house; the sentence above them compares inside and outside, '
        + 'which are apart because they are not the same day. On the node this was built against they are anti-phased: inside peaks when '
        + 'somebody is cooking and outside peaks in the evening, so at midday inside is about twice '
        + 'outside and at six in the evening it is the other way round. A single average over both '
        + 'would describe neither, and the difference is the only thing here anybody can act on.' },
      { id: 'shape-windows', label: 'How much record each window needs',
        text: `This is the day\u2019s shape, which needs a week behind it. The `
        + `week\u2019s, the month\u2019s and the year\u2019s need two weeks, two months and a year, and this `
        + `node has ${S.days == null ? 'no' : S.days} day${S.days === 1 ? '' : 's'} of its own `
        + 'readings. The node decides what its record supports and the page draws what it is told; '
        + 'a page that worked that out for itself would be the one place tempted to round up.' },
    ];
  },
});

});

/* ================================================================= h/mods/decide.js ==== */
/* decide · core · decide
 *
 * WHERE AN OBSERVATION BECOMES SOMETHING SOMEBODY DECIDED. The stage was named `decide` from the
 * first sketch and carried three sections about grain, provenance and trust — at what resolution a
 * thing may be said, never what to do about it. Reported by Tomas three times before it was built.
 *
 * THE NODE ALREADY DECIDES, AND THE PAGE WAS THROWING IT AWAY. Every rule in config/rules.yml and
 * every pack rule ends its message with a line beginning U+1F449 — "Open a window or two and let it
 * through. It clears faster than a purifier can catch it." Written by whoever wrote the rule, in
 * three languages, shipped, and on the wire in `open_asks[].text`. It is an informed recommendation
 * from an observation, which is exactly the thing this section exists to put in front of somebody.
 * `ask()` renders `text.split("\n")[0]` — the first line, the symptom — and the recommendation was
 * never drawn anywhere on this page.
 *
 * So: what was seen, what the node suggests, and a box. Accept its words or write your own, and the
 * decision is recorded whether or not anybody ever gets to it. `decided` moves nothing — not rho,
 * not the funnel, not an ask's open/closed — which is init.sql:135 and the whole of
 * docs/SPEC_decide.md section 6. Doing it is a separate press, in Act, where the ledger is.
 */
PAI_LOAD.push(function () {
'use strict';

const { esc, age, evState, evOpen, evCard, evClock } = window.K;
const { H } = window.KH;

/* The recommendation, which is the last paragraph and starts with the pointing hand. Absent on a
   rule whose author did not write one — and then this says so rather than inventing advice, which
   is not a thing this page is allowed to do. */
function suggestion(text) {
  const paras = String(text || '').split('\n').map(x => x.trim()).filter(Boolean);
  const hit = paras.filter(x => x.startsWith('\u{1F449}')).pop();
  return hit ? hit.replace(/^\u{1F449}\s*/u, '') : null;
}

/* The rule rows an event covers, folded inside its card (spec §4.2: id, rule, time). An id the ledger
   no longer holds says so rather than being dropped: /issues keeps the last 200 alerts. */
function rowsOf(ctx, e) {
  const ids = e.alerts || [];
  if (!ids.length) return '';
  const acts = (H.asks || {}).acts || [];
  const now = Date.parse(((ctx.S || {}).base || {}).captured_utc) || Date.now();
  const line = id => {
    const x = acts.find(a => a.id === id);
    return `<p class="m">#${esc(String(id))} \u00b7 `
      + (x ? `${esc(String(x.rule_id || 'a rule'))} \u00b7 ${esc(age(Math.round((now - Date.parse(x.ts)) / 60000)))}`
        : 'older than the 200 alerts this page reads') + `</p>`;
  };
  return `<details class="evrows" id="evrows-${esc(String(e.id))}"><summary>from ${ids.length} rule `
    + `row${ids.length === 1 ? '' : 's'}</summary>${ids.map(line).join('')}</details>`;
}

function card(ctx, key, d, a, did) {
  const sug = suggestion(a.text);
  const seen = String(a.text || '').split('\n')[0];
  const id = `decide-${esc(key)}`;
  /* THE OBSERVATION IS A LINE, NOT A PARAGRAPH. It is already on this page twice — in the lead and
     in Act's own strip — and drawn a third time at headline size it cost 91 px a card at 390 to say
     nothing new. What is new here is the suggestion, so that is what gets the room. */
  return `<section class="decide" id="${esc(id)}" data-component="decision" data-ref="asks-rows">`
    + `<div class="obs"><span class="k">what was seen</span>`
    + `<p>${esc(seen)}</p>`
    + `<span class="m">${esc(d.name[ctx.LOC] || key)} \u00b7 asked ${esc(age(a.age_minutes))}`
    + `${a.current ? '' : ' \u00b7 the reading has come back on its own'}</span></div>`
    + `<div class="sug"><span class="k">what this node suggests</span>`
    + (sug ? `<p>${esc(sug)}</p>`
      : `<p class="none">The rule that raised this does not carry a recommendation, so there is `
        + `nothing here. This page will not invent one.</p>`)
    + `</div>`
    + `<button type="button" class="open" data-decide="${esc(String(a.id))}"`
    + ` aria-expanded="false">Decide about this</button>`
    + `<form class="decided" hidden data-alert="${esc(String(a.id))}">`
    + `<label><span>Who is deciding</span><input name="actor" maxlength="80" autocomplete="name"`
    + ` placeholder="your name"></label>`
    + `<label><span>What will be done</span><input name="note" maxlength="500"`
    + ` placeholder="${esc(sug || 'in your own words')}"${sug
      ? ` data-suggest="${esc(sug)}"` : ''}></label>`
    + `<div class="btns">`
    + (sug ? `<button type="button" class="take">Take its word</button>` : '')
    + `<button type="submit" class="pri">Record the decision</button></div>`
    + `<p class="fine">This closes no alert and moves no number. When it is done, press `
    + `<b>I did this</b> on this card.</p>`
    + window.K.TOKEN_FINE
    + `</form>${did ? `<div class="ask">${window.K.didButton(a.id)}</div>` : ''}</section>`;
}

window.PAI.register({
  id: 'decide', pack: 'core', stage: 'decide', order: 5, level: 'simple',
  reads: ['/issues'],
  learn: ['events', 'buttons'],
  title: 'What to do about it',
  needs: ['H3.asks'],
  anchor: 'decide',
  render(ctx) {
    const ISS = ctx.ISS, st = evState(), E = ctx.S.issues.events || {};
    const asks = k => (ISS[k] && ISS[k].open_asks) || [];
    if (st === 'events' || st === 'shadow') {
      const unc = new Set(E.uncovered_asks || []);
      /* One card per issue, the way the fallback draws them: card() ids itself decide-<key>. */
      const left = ctx.ORDER.map(k => [k, asks(k).find(a => unc.has(a.id))]).filter(([, a]) => a)
        .map(([k, a]) => card(ctx, k, ISS[k], a, true));
      const open = evOpen();
      if (!open.length && !left.length) {
        const last = E.last_cleared;
        return `<p class="note evnone" id="decide-none" data-component="absent" data-ref="stage-decide">`
          + `Nothing open.${E.cleared_today ? ` ${E.cleared_today} cleared today`
            + `${last ? `, the last at ${esc(evClock(last.ts))} (${esc((ISS[last.issue] || { name: {} }).name[ctx.LOC]
              || last.issue)})` : ''}.` : ''}</p>`;
      }
      return open.map(e => evCard(e, rowsOf(ctx, e))).join('') + left.join('');
    }
    /* rules, a node older than v0.77, or an events block that could not be read: each says which, then
       draws the alert cards, because nothing that asks a person something may disappear. */
    const why = st === 'old' ? `This node is ${esc((ctx.S.health || {}).version || 'older than v0.77')}: it sends `
      + `alerts, not events.` : st === 'error' ? esc(E.error) : 'This node sends alerts, not events.';
    const open = ctx.ORDER.filter(k => asks(k).length);
    return `<p class="note" id="decide-engine" data-component="absent" data-ref="stage-decide">${why}</p>`
      + (open.length ? open.map(k => card(ctx, k, ISS[k], asks(k)[0], true)).join('')
        : `<p class="note" id="decide-none" data-component="absent" data-ref="stage-decide">Nothing is asking for `
          + `anything.</p>`);
  },
  notes() {
    return [
      { id: 'decide-events', label: 'What an event is',
        text: 'An event is the bot\u2019s own unit: one issue in one house, from when its rule first fires '
        + 'to when it clears, however many rule rows that took. The node chose the action and wrote the '
        + 'message, and this page draws them. Where a rule row is not covered by any event, it is drawn '
        + 'after the events as an alert, with I did this, so nothing that asks a person something '
        + 'disappears.' },
      { id: 'decide-buttons', label: 'What each button writes',
        text: 'Done, Not now and Doesn\u2019t fit each write one row to the node\u2019s record, by event: '
        + 'who pressed, when, and for Doesn\u2019t fit what was done instead. Done closes the loop; Not '
        + 'now holds the card until the time it names, unless the reading reaches danger. \u03c1 does not '
        + 'count events yet, so none of the three moves it.' },
      { id: 'decide-suggestion', label: 'The suggestion is the rule’s own',
        text: 'This is the alert card, which Decide draws on a node that sends alerts, not events, '
        + 'and on an older node or one whose events cannot be read. Its suggested action is the '
        + 'rule\u2019s own last line, the one '
        + 'that begins with a pointing hand, written by whoever wrote the rule and shipped in every '
        + 'language this node speaks. It is not generated here and it is not a model\u2019s: a node '
        + 'with no agent running shows exactly the same words. Where a rule carries no '
        + 'recommendation the card says so, because a page that invents advice about somebody\u2019s '
        + 'air is a page that cannot be trusted about anything. An event card has no such line: '
        + 'the node chose its action.' },
      { id: 'decide-moves-nothing', label: 'A decision moves nothing',
        text: 'On an alert card, which is the fallback for a node that sends alerts, not events, '
        + 'a decision moves nothing. It does not close the alert, it '
        + 'does not enter \u03c1, and it is not a stage in the funnel \u2014 the alert stays open and the '
        + 'node keeps watching. What it changes is the record: a household that looked, decided and '
        + 'never managed it used to leave the same trace as one that never looked, which was none.' },
      { id: 'decide-collective', label: 'One person, one node',
        text: 'This is one person deciding for one node. A decision about a '
        + 'street is not one household\u2019s to make, and what turns several households\u2019 decisions '
        + 'into a decision a community has taken \u2014 who is asked, what counts as agreement \u2014 is '
        + 'not on a node at all. docs/SPEC_decide.md says so and leaves it to the scale above.' },
    ];
  },
});

});

/* ================================================================= h/mods/ledger.js ==== */
/* ledger · core · act
 *
 * WHAT WAS DECIDED, AND BY WHOM. The one thing the loop records that the page never drew.
 *
 * `POST /actions` has taken a stage, an actor and a 500-character note since v0.21, and from
 * 22 September the page can write one. Nothing read them back: node #1 has 31 acts on its own wire
 * with 23 names in them and the page drew none of it, so "somebody closed this" was a count in a
 * funnel and never an account. Reported by Tomas, who could not find it on the Act stage.
 *
 * TWO SOURCES, AND THE SPLIT IS THE NODE'S, NOT THIS PAGE'S:
 *
 *   · the rows — who, when, which ask, which stage — come off `H3.asks.actions`, which /issues
 *     publishes to anyone the share level lets read it.
 *   · the WORDS come off GET /actions, which is on neither share allowlist on purpose: the note is
 *     the household's own sentence about what it did in its own house, and that route answers a
 *     token or the machine itself. `window.ACT_NOTES` is null for a reader without one, and this
 *     section says so once rather than drawing a column of blanks.
 *
 * This page does not widen that. Publishing the note on /issues would put those sentences on the
 * `open` allowlist, which is the opposite of what the node decided.
 */
PAI_LOAD.push(function () {
'use strict';

const { esc, row, age, evWord } = window.K;
const { H } = window.KH;

/* ALL OF IT FOLDED, and the head says how many. Eight rows and a five-line head were 1,029 px at 390
   and put the page past its length target; four were still 530. This is a record somebody consults
   — "what did we decide about the kitchen" — and not something to read on the way past, so it costs
   one line until it is wanted. The whole explanation of why the words may be missing is in this
   section's notes. */
const SHOWN = 0;

/* The ask a row answers, by id, off the act ledger /issues already carries. An act older than the
   200 alerts `_read` keeps has no ask to name, and says that rather than drawing an empty cell. */
function askOf(id) {
  return ((H.asks || {}).acts || []).find(a => a.id === id) || null;
}

/* THE DECISION AN ACT CAME FROM: the latest `decided` row on the same ask, recorded before it.
 *
 * A convention and not a foreign key, deliberately: `asks.actions` already carries alert_id, stage
 * and ts, so this needs nothing added to the schema, the endpoint or the wire. An act with none is
 * not a fault — four of the five ways to record one have no screen to decide on, and the LoRa reply
 * through the Reticulum bridge is the case that settles it — so this answers null, and the count in
 * the head says how often. */
function cameFrom(rows, act) {
  return rows.filter(x => x.alert_id === act.alert_id && x.stage === 'decided'
    && String(x.ts) < String(act.ts))
    .sort((a, b) => String(b.ts).localeCompare(String(a.ts)))[0] || null;
}

function line(x, ctx, all) {
  const a = askOf(x.alert_id);
  const from = x.stage === 'acted' ? cameFrom(all || [], x) : null;
  const notes = window.ACT_NOTES;
  const note = notes ? notes[`${x.alert_id}:${x.stage}`] : null;
  const when = new Date(x.ts);
  const mins = Math.round((Date.parse(ctx.S.base.captured_utc) - when.getTime()) / 60000);
  const name = String(x.actor || '').trim();
  return row({
    id: `act-${esc(String(x.alert_id))}-${esc(String(x.stage))}`,
    component: 'ledgerRow', ref: 'asks-rows',
    cls: x.stage === 'acted' ? '' : 'quiet',
    cols: 'minmax(0,170px) minmax(0,1fr) auto',
    left: `<span class="who"><b>${esc(name || 'somebody')}</b>`
      + `<span class="m">${esc(x.stage)} · ${esc(age(mins))}`
      + `${from ? ' · decided first' : ''}</span></span>`,
    /* The sentence if this reader may have it; otherwise the ask it answered, so the row still says
       what was closed. Never a blank and never a guess at what was written. */
    line: note || (a ? String(a.text || '').split('\n')[0].slice(0, 120)
      : 'the alert this answered is older than the ledger this node keeps'),
    qty: [],
  });
}

/* THE ANSWERS TO EVENTS: each open or recent event's latest answer, one row, newest first. The node keeps
   one answer an event that matters (the latest), so this reads `answer` and never replays the ledger. An id
   in both lists is read once. */
function evAnswers(E) {
  const seen = new Set();
  return [...(E.open || []), ...(E.recent || [])]
    .filter(e => e.answer && !seen.has(e.id) && seen.add(e.id))
    .map(e => ({ ts: e.answer.ts, event: e, answer: e.answer }))
    .sort((a, b) => String(b.ts).localeCompare(String(a.ts)));
}

function evLine(x, ctx) {
  const e = x.event, a = x.answer, d = ctx.ISS[e.issue] || { name: {} };
  const notes = window.ACT_NOTES;
  const note = notes ? notes[`ev${e.id}:${a.stage}`] : null;
  const mins = Math.round((Date.parse(ctx.S.base.captured_utc) - Date.parse(a.ts)) / 60000);
  return row({
    id: `act-ev${esc(String(e.id))}-${esc(String(a.stage))}`,
    component: 'ledgerRow', ref: 'asks-rows',
    cls: a.stage === 'acted' ? '' : 'quiet',
    cols: 'minmax(0,170px) minmax(0,1fr) auto',
    left: `<span class="who"><b>${esc(String(a.actor || '').trim() || 'somebody')}</b>`
      + `<span class="m">${esc(evWord(a.stage))} \u00b7 ${esc(age(mins))}</span></span>`,
    /* The sentence if this reader may have it; otherwise the issue it was about, so the row still says what
       was answered. */
    line: note || `${d.name[ctx.LOC] || e.issue} \u00b7 ${e.kind}`,
    qty: [],
  });
}

window.PAI.register({
  id: 'ledger', pack: 'core', stage: 'act', order: 20, learn: ['note', 'bot', 'actions'],
  reads: ['/issues', '/actions'],
  title: 'What was decided, and by whom',
  needs: ['H3.asks.actions'],
  anchor: 'ledger',
  render(ctx) {
    const rows = (((H.asks || {}).actions) || []).slice()
      .sort((a, b) => String(b.ts).localeCompare(String(a.ts)));
    /* Alert acts and event answers, in the order they happened. An event answer is a different row from an
       alert act and counts toward neither `decided first` nor the practice figure, which are alert acts'. */
    const items = rows.map(x => ({ ts: x.ts, html: line(x, ctx, rows) }))
      .concat(evAnswers(ctx.S.issues.events || {}).map(x => ({ ts: x.ts, html: evLine(x, ctx) })))
      .sort((a, b) => String(b.ts).localeCompare(String(a.ts)));
    if (!items.length) {
      return `<p class="note" id="ledger-none" data-component="absent" data-ref="asks-rows">`
        + `Nobody has answered an alert on this node yet. When somebody does \u2014 from this page, `
        + `from Telegram, or from a terminal \u2014 what they did and who they are is recorded here.`
        + `</p>`;
    }
    const words = window.ACT_NOTES;
    const said = words ? Object.keys(words).length : 0;
    /* One sentence about what this reader is being shown, because a ledger of names with no words
       looks like a ledger whose words are missing, and on most readings it is a ledger whose words
       this reader is not entitled to. */
    /* HOW OFTEN A DECISION CAME FIRST. A measure of practice and never a gate: on a node in a house
       this is honestly low and that is not a failing, and on a node acting for a street it should be
       all of them — and when it is not, the number says so. A refusal is one curl away; a number is
       not. Same shape as ρ, which never forces anybody to answer an alert and only counts whether
       they did. DECISION_REQUIRED under Set up is the switch for a community that wants the gate. */
    const acts = rows.filter(x => x.stage === 'acted');
    const led = acts.filter(x => cameFrom(rows, x)).length;
    const practice = acts.length
      ? ` <span data-num="ledger.decided" data-cmp="of ${acts.length} act${acts.length === 1 ? ''
        : 's'} on this node — a measure of practice and not a rule; DECISION_REQUIRED under Set up `
        + `is the rule">${led}</span> of ${acts.length} had a decision recorded first.`
      : '';
    const head = `<p class="why" id="ledger-head" data-component="ledgerHead" data-ref="ledger">`
      + `${items.length} answer${items.length === 1 ? '' : 's'} on this node.${practice} `
      + (words
        ? `${said} carr${said === 1 ? 'ies' : 'y'} the sentence somebody wrote.`
        : `The sentences need a token \u2014 a note is the household\u2019s own words about its own `
          + `house. Set up \u2192 unlock.`)
      + `</p>`;
    const first = items.slice(0, SHOWN).map(x => x.html).join('');
    const rest = items.slice(SHOWN);
    return head + `<div class="reads" id="ledger-rows" data-ref="asks-rows">${first}`
      + (rest.length
        ? `<details class="fold"><summary>${SHOWN ? `The other ${rest.length}`
          : `All ${rest.length}, newest first`}</summary>`
          + rest.map(x => x.html).join('') + `</details>`
        : '')
      + `</div>`;
  },
  notes() {
    return [
      { id: 'ledger-two-sources', label: 'Two answers, and what stays here',
        text: 'This ledger is drawn from two answers, and the line '
        + 'between them is the node\u2019s. Who acted, when, and on which alert are published with the '
        + 'rest of the page. The sentence they wrote is not: GET /actions is on neither sharing '
        + 'allowlist, because a note is what a household said about its own house, and it answers a '
        + 'token or this machine and nothing else.' },
    ];
  },
});

});

});

/* ================================================================= h/mods/measure.js ==== */
/* measure · core · measure
 *
 * Whether it worked, and how long it took. The loop's last stage and the one that makes it a loop:
 * ρ, the share of asks that were answered; the median minutes from ask to answer; and the hours the
 * house spent over the line, which is the reading coming back — or not — after somebody acted.
 *
 * Nothing here is a gauge. ρ is a row of rings, answered first, and the numeral beside it says the
 * same thing in words. The hours over the line are counted from the node's own per-day counts,
 * today and in the days the strips draw; the day itself is drawn once, under Observe.
 */
PAI_LOAD.push(function () {
'use strict';

const { esc, fmt, row, rhoRow, peerRow, funnel, sign, localOf } = window.K;

/* The care label: the refusals that hold across every stage, from ARCHITECTURE.md §7, drawn where the
 * loop closes because a refusal is the last thing a reader should meet, not the first.
 *
 * It is copied text, and deliberately so — these five sentences are the architecture's, not the page's,
 * and paraphrasing them here would make a sixth version of a promise that already has one home.
 *
 * SIGN DISCIPLINE. Each sign means its own sentence or there is no sign. The third row drew an empty
 * slot for a while rather than borrow `rho-closed`, which already means an answered ask twelve pixels
 * higher in this same card and would then have meant two things in one place. `person` exists for
 * this row now — its first pass measured 90.3% identical to `heat` at 12 px and went back for a
 * redraw, which is R23 in the design log. */
const REFUSALS = [
  ['house', 'No raw readings leave the instance that recorded them.'],
  ['cell', 'No cell is upgraded from mock or partial to live by aggregation.'],
  ['person', 'No agent dispatches without a human row in the actions ledger.'],
  ['machine', 'No layer requires a cloud provider to function.'],
  ['planet', 'No scale is skipped: a city aggregator is built from nodes, not declared from above.'],
];

function careLabel() {
  return `<div class="care" data-component="careLabel" id="care" data-ref="rho">`
    + `<p class="k">What this node will not do, at any stage</p>`
    + REFUSALS.map(([sg, text]) =>
      `<p class="rf"><span class="sg">${sg ? sign(sg) : ''}</span>${esc(text)}</p>`).join('')
    + `</div>`;
}

/* Hours over the line, counted (docs/SPEC_dashboard_figures.md §4.5, after Bali Air Dispatch): how long, not how
 * high, which is what a household acts on. Today and the days GET /issues/days covers, from the node's own per-day
 * counts; an hour with nothing recorded is named beside them and never counted as clean. */
function overRows(ctx) {
  const D = window.DAYS;
  if (!D) {
    return `<p class="note" id="measure-over" data-ref="rho">This node does not send its days yet, so the hours over `
      + `the line are not counted here.</p>`;
  }
  const I = D.issues || {};
  const keys = ctx.ORDER.filter(k => I[k] && I[k].distance && I[k].line);
  if (!keys.length) {
    return `<p class="note" id="measure-over" data-ref="rho">No issue here has a line to count hours against.</p>`;
  }
  const sum = ps => ps.reduce((a, p) => ({ over: a.over + (p.over || 0), read: a.read + p.read, of: a.of + p.of }),
    { over: 0, read: 0, of: 0 });
  /* The node's today: /issues' as_of (an instant, UTC on a live node) read in the offset of the latest bucket. A DAYS
     answered before local midnight, or kept after a failed fetch, ends on yesterday, and that is not today's count. */
  const today = localOf((D.buckets || []).slice(-1)[0], Date.parse(((ctx.S || {}).issues || {}).as_of)).day;
  return `<div class="reads" id="measure-over" data-ref="rho">` + keys.map(k => {
    const it = I[k], u = ctx.ISS[k], last = it.per_day.slice(-1);
    const t = last.length && last[0].date === today ? sum(last) : { over: 0, read: 0, of: 0 }, w = sum(it.per_day);
    return row({ id: `measure-over-${k}`, component: 'overCount', ref: 'measure-over',
      cols: 'minmax(0,210px) minmax(0,1fr) auto',
      left: `<span class="who"><b>${esc(u.name[LOC])}</b><span class="m">${esc(ctx.LAB[it.distance])} · over `
        + `${esc(fmt(it.line.value, u.dp))} ${esc(u.unit)}</span></span>`,
      line: `Hours over the line today, and in these ${D.days} days.`,
      qty: [{ num: `${k}.over.today`, value: t.read ? `${t.over} h` : null, cmp: `of ${t.read} hour${t.read === 1 ? '' : 's'} read today, ${t.of - t.read} not recorded` },
        { num: `${k}.over.days`, value: w.read ? `${w.over} h` : null, cmp: `of ${w.read} hour${w.read === 1 ? '' : 's'} read in ${D.days} days, ${w.of - w.read} not recorded` }],
    });
  }).join('') + `</div>`;
}

window.PAI.register({
  id: 'measure', pack: 'core', stage: 'measure', order: 10, learn: ['rho', 'refusals'],
  reads: ['/rho', '/issues', '/issues/days'],
  title: 'Whether it worked',
  needs: ['SNAP.rho'],
  render(ctx) {
    const { S } = ctx;
    const r = S.rho;
    return `<div class="two-up">`
      + `<div>${rhoRow()}`
      + `<div class="reads" id="measure-rows" data-ref="rho">`
      + row({ id: 'measure-median', component: 'median', ref: 'rho',
        cols: 'minmax(0,210px) minmax(0,1fr) auto',
        left: `<span class="who"><b>Alert to answer</b><span class="m">median, ${r.window_days} days`
          + `</span></span>`,
        line: r.median_minutes == null ? 'Nothing has been answered yet in this window.'
          : `Half the alerts that were answered were answered inside this.`,
        qty: [{ num: 'rho.median', value: r.median_minutes == null ? null
          : `${r.median_minutes} min`, cmp: `against ${r.acted} of ${r.alerts_act} alerts answered` }],
      })
      + row({ id: 'measure-rho', component: 'rhoValue', ref: 'rho',
        cols: 'minmax(0,210px) minmax(0,1fr) auto',
        left: `<span class="who"><b>ρ reported</b><span class="m">answered ÷ asked`
          + `</span></span>`,
        /* Two numbers are specified (SPEC_rho §4) and one exists. ρ_observed needs a `recovery:`
           block naming the metric and the threshold that would count as recovered, and no rule in the
           core or any pack carries one — so the words say so. A 0.00 beside ρ would read as a node
           that checked and found nothing, which is the opposite of what is true. */
        line: `The one number this node reports about itself to anybody. ρ observed: not yet — `
          + `no rule has said what recovery would look like.`,
        qty: [{ num: 'rho.value', value: r.rho == null ? null : fmt(r.rho, 2),
          cmp: `${r.acted} answered of ${r.alerts_act} asked in ${r.window_days} days` }],
      })
      + `</div>${funnel()}${careLabel()}</div>`
      + `<div>${overRows(ctx)}</div></div>`;
  },
  notes(ctx) {
    const r = ctx.S.rho;
    return [
      { id: 'measure-rho', label: 'ρ, and the one that does not exist',
        text: `ρ is the share of alerts answered — ${r.acted} of ${r.alerts_act} `
        + `in ${r.window_days} days here — and it is the one number a node reports about itself. It `
        + 'is drawn as a row of rings, answered first, because a row a person can count is a '
        + 'measurement and a dial needle is a mood. Its definition is not this page’s to touch. A '
        + 'second ρ is specified and does not exist: ρ observed would ask whether the reading came '
        + 'back under the line, and no rule has yet said what its own line is, so the page prints '
        + 'those words rather than a zero that would read as a node that looked and found nothing.' },
      { id: 'measure-over', label: 'How long, counted',
        text: 'A reading over the line for one hour and for nine are different days, and a curve does not say which. '
        + 'These rows count the hours the house was over the line, from the node’s own count per local day: today, '
        + 'and the days the strips under Observe draw. An hour nothing was recorded is named beside the count, never '
        + 'counted as clean, and a day with nothing recorded shows a dash, not a zero.' },
      { id: 'funnel', label: 'One thing counted four times',
        text: 'The funnel counts one thing four times: how many alerts the node sent, '
        + 'how many were acknowledged, how many led to something being done, and how many stopped '
        + 'coming back. Two of the four read zero here and each says why. Nobody has acknowledged '
        + 'anything on this node — the phone’s button records that something was done, which skips '
        + 'the middle stage — and that is a fact about the household, not a hole in the drawing. The '
        + 'last stage is not typed by anyone: the node re-asks every rule on a cycle, so an alert '
        + 'followed by a long silence from the same rule on the same sensor is the condition having '
        + 'stopped being true. It says whether the loop closed, never how fast, which is why it is '
        + 'the one stage with no time beside it.' },
      { id: 'care', label: 'The five refusals',
        text: 'The five refusals are copied from the architecture, not written here, '
        + 'because a promise repeated in a second place is a promise that can drift. They sit at the '
        + 'end of the loop rather than the top of the page: a reader meets what this node does '
        + 'first, and what it will not do once they have seen it. The row about the human row went '
        + 'without a sign until one was drawn for it: borrowing the answered-alert ring would have '
        + 'made that ring mean two things twelve pixels apart.' },
      { id: 'measure-loop', label: 'Where the loop closes',
        text: 'This is the stage that closes the loop. Observe put a number on '
        + 'the page; decide said how far that number may be trusted; act asked somebody to do '
        + 'something; measure is the reading coming back after they did, or did not, and how long it '
        + 'took. The next observation is the first section again.' },
    ];
  },
});

});

/* ================================================================= h/mods/trust.js ==== */
/* trust · trust · decide
 *
 * What this node doubts about its own sensors. Restored from the page this replaces, as a section
 * the trust pack registers: three rules exist (channel_dead, coverage_low, peer_disagreement) and
 * before that card nowhere on the node's own surfaces did a person see that a kit sat at 32% of the
 * week while reporting a fresh timestamp.
 *
 * WHY DECIDE, AND WHY THE NETWORK VIEW. Doubt is not an observation: a coverage figure is not a
 * reading of the air, it is a statement about how far a reading may be trusted, which is the decide
 * stage's whole question. And it is keeper's material rather than household material — somebody
 * fixes a kit, nobody opens a window because of it — so it sits with the radios and the hardware.
 *
 * `GET /trust` computes all of it. Nothing here counts anything: a sensor under seven days old is
 * young because the node says `age_hours < 168`, and the page prints that rather than deciding it.
 */
PAI_LOAD.push(function () {
'use strict';

const { esc, row } = window.K;

const T = () => window.TRUST || null;

window.PAI.register({
  id: 'trust', pack: 'trust', stage: 'decide', order: 30, learn: ['trust'],
  reads: ['/trust'],
  title: 'What the node doubts about its own sensors',
  needs: ['TRUST'],

  render(ctx) {
    const rows = (T() || {}).rows || T() || [];
    const all = Array.isArray(rows) ? rows : [];
    if (!all.length) {
      /* hardware-rows is on Network; trust has been on Historical since v0.56. Its own band is the
         one id guaranteed to be on the page with it — sat-map is not, because the satellite draws
         nothing without a plan and /place/geojson is refused at every share level. */
      return `<p class="note" data-component="trustCard" data-card="trust" id="trust-rows"`
        + ` data-ref="trust">No local sensor yet, so there is nothing to doubt.</p>`;
    }
    /* The node's own three conditions, read off the row rather than recomputed here. */
    const doubt = all.filter(r => r.age_hours < 168 || r.coverage_7d < 60 || r.frozen_channels > 0);
    const cols = 'minmax(0,210px) minmax(0,1fr) auto';
    const body = doubt.length
      ? doubt.map(r => {
        const young = r.age_hours < 168;
        return row({
          id: `trust-${esc(r.sensor_id)}`, component: 'trustRow', ref: 'trust-rows', cols,
          left: `<span class="who"><b>${esc(r.name || r.sensor_id)}</b>`
            + `<span class="m">${esc(r.sensor_id)}</span></span>`,
          line: young
            ? 'still gathering its first week, so its coverage is not a fault yet'
            : `${r.frozen_channels > 0 ? `${r.frozen_channels} frozen `
              + `${r.frozen_channels === 1 ? 'channel' : 'channels'}: the kit is alive and one of its `
              + `readings has not moved. ` : ''}Seven-day coverage is what the node has of it, not `
              + `what it sent.`,
          qty: [{ num: `trust.${esc(r.sensor_id)}.coverage`,
            value: young ? '—' : `${r.coverage_7d}%`,
            cmp: young ? 'under seven days old; the week is not up'
              : 'of the week, against 100% for a sensor that reported every hour' }],
        });
      }).join('')
      : `<p class="note">Every sensor reported all week.</p>`;
    const sub = doubt.length
      ? `${doubt.length} of ${all.length} sensors need a look.`
      : `${all.length} local sensors, seven-day coverage.`;
    return `<div class="reads" data-component="trustCard" data-card="trust" id="trust-rows"`
      + ` data-ref="trust"><p class="note">${esc(sub)}</p>${body}</div>`;
  },

  notes() {
    const all = ((T() || {}).rows || T() || []);
    return [
      { id: 'trust-what', label: 'Three things it can tell alone',
        text: 'Three things this node can tell about its own sensors without '
        + 'anybody looking: a channel that has stopped moving while the kit is still alive, a '
        + 'sensor that has reported for less than sixty per cent of the week, and two collocated '
        + 'kits that disagree. GET /trust computes all three; none of them is an alert, because a '
        + 'doubt is not something to interrupt a household about.' },
      { id: 'trust-young', label: 'A sensor under a week old',
        text: 'A sensor under seven days old has no seven-day coverage and is '
        + 'said to be still gathering its first week, not shown at some low percentage. Reading 0% '
        + 'as a fault on a kit plugged in yesterday is the page inventing a problem.' },
      { id: 'trust-stage', label: 'Why this is in decide',
        text: `This is in decide rather than observe because a coverage figure is `
        + `not a reading of the place: it is a statement about how far a reading may be trusted, `
        + `which is the question the decide stage exists for. `
        + `${Array.isArray(all) && all.length ? `${all.length} sensors are in it.` : ''}` },
    ];
  },
});

});

/* ================================================================= h/mods/forecast.js ==== */
/* forecast · forecast · observe
 *
 * The day this place is about to have: the wind, the rain, and the next eight hours of temperature.
 * Restored from the page this replaces, as a section the forecast pack registers.
 *
 * WHY OBSERVE, AND WHY NOW. A forecast is not this node's own measurement, but it is an observation
 * of this place that the node fetched and keeps — the same class of thing as the satellite's pass or
 * the street's median, which are both in observe. And it is the most household-facing thing on the
 * page after the lead: somebody checks it before hanging the washing out, so it is on Now.
 *
 * THE NODE FETCHES THIS; IT DOES NOT PREDICT. Printed on the card, because a household reading a
 * number on their own node's screen will otherwise assume the node worked it out.
 */
PAI_LOAD.push(function () {
'use strict';

const { esc, fmt, row } = window.K;

const COMPASS16 = ['N', 'NNE', 'NE', 'ENE', 'E', 'ESE', 'SE', 'SSE',
  'S', 'SSW', 'SW', 'WSW', 'W', 'WNW', 'NW', 'NNW'];
const compass16 = deg => deg == null ? '?' : COMPASS16[Math.round((deg % 360) / 22.5) % 16];
const hhmm = ts => {
  const d = new Date(ts);
  return `${String(d.getUTCHours()).padStart(2, '0')}:${String(d.getUTCMinutes()).padStart(2, '0')}`;
};

/* Top level, not nested: a function defined inside another one still parses and tools/check_ui.py
 * cannot see it. Same reason the page this replaces kept drawRing and drawForecast at the top. */
function drawForecast(ctx) {
  const d = window.FORECAST || {};
  /* /forecast always names both archives. The line after `||` is for a node whose forecast pack has
     never run, where the section exists and the endpoint's own credit does not. */
  const cite = ((d.attribution) || []).join(' · ')
    || 'BMKG, api.bmkg.go.id. Open-Meteo, open-meteo.com, CC-BY 4.0, when it is on.';
  const hours = d.hours || [];
  const card = (body, note) => `<div class="reads" data-component="forecast" data-card="forecast"`
    + ` id="forecast-rows" data-ref="band-${esc(ctx.S.issues.headline)}">`
    + `<p class="note">${esc(note)}</p>${body}`
    + `<p class="cap">${esc(cite)}</p>`
    + `<p class="cap">The node fetches this; it does not predict.</p></div>`;
  if (!hours.length) {
    return card('', 'No forecast yet. Set FORECAST_BMKG_ADM4 to this point’s village code, or turn '
      + 'on Open-Meteo, and the next day of wind and rain appears here. planetai run forecast verify '
      + 'finds the code.');
  }
  const now = Date.now();
  const all = hours.filter(h => new Date(h.ts).getTime() >= now - 3.6e6);
  const primary = all.some(h => h.source === 'forecast-bmkg') ? 'forecast-bmkg' : 'forecast-om';
  const fut = all.filter(h => h.source === primary);
  const gaps = all.filter(h => h.source === 'forecast-gap' && h.fc_temp_gap != null);
  const wind = fut.filter(h => h.fc_wind_speed != null);
  const rain = fut.filter(h => h.fc_rain > 0.2);
  const far = (d.far_from_node || [])[0];
  const w0 = wind[0];
  const note = [
    w0 ? `The wind comes from the ${compass16(w0.fc_wind_direction)} at `
      + `${fmt(w0.fc_wind_speed, 0)} km/h.` : '',
    rain.length
      ? `Rain expected from ${hhmm(rain[0].ts)}, `
        + `${fmt(fut.reduce((a, h) => a + (h.fc_rain || 0), 0), 1)} mm over the day.`
      : 'No rain expected in the next day.',
    far ? `The forecast point is ${fmt(far.km, 1)} km from this node, which is another place.` : '',
    gaps.length ? `The two forecasts differ by up to `
      + `${fmt(Math.max(...gaps.map(h => h.fc_temp_gap)), 1)} °C over the day; neither is the truth.` : '',
  ].filter(Boolean).join(' ');
  const steps = fut.slice(0, 8).map(h => row({
    id: `fc-${esc(String(h.ts))}`, component: 'forecastHour', ref: 'forecast-rows',
    cols: 'minmax(0,110px) minmax(0,1fr) auto',
    left: `<span class="who"><b>${esc(hhmm(h.ts))}</b></span>`,
    line: `wind from ${compass16(h.fc_wind_direction)} ${fmt(h.fc_wind_speed, 0)} km/h · `
      + (h.fc_rain > 0.2 ? `${fmt(h.fc_rain, 1)} mm rain` : 'dry')
      + (h.fc_cloud == null ? '' : ` · ${fmt(h.fc_cloud, 0)}% cloud`),
    qty: [{ num: `forecast.${esc(String(h.ts))}.temp`, value: `${fmt(h.fc_temp, 0)} °C`,
      cmp: 'a forecast for this point, not a reading taken here' }],
  })).join('');
  return card(steps, note);
}

window.PAI.register({
  id: 'forecast', pack: 'forecast', stage: 'observe', order: 14, learn: ['forecast'],
  reads: ['/forecast', '/issues'],
  title: 'The day it is about to have',
  needs: ['FORECAST'],
  render: drawForecast,
  notes() {
    const d = window.FORECAST || {};
    return [
      { id: 'forecast-not-a-reading', label: 'A forecast is not a reading',
        text: 'Every number here is a forecast for a point, fetched '
        + 'from an archive and kept on this node. None of it was measured here and none of it is '
        + 'this node’s own: the node fetches it, it does not predict it, and the card says so '
        + 'under the credit rather than leaving a household to assume otherwise.' },
      { id: 'forecast-two-archives', label: 'Two archives, both named',
        text: 'BMKG is Indonesia’s own service and Open-Meteo is '
        + 'the fallback; both are named on the card because both are required to be. Where the two '
        + 'disagree the section says by how much and that neither is the truth, rather than picking '
        + 'one and drawing it as if there were no second answer.' },
      { id: 'forecast-point', label: 'A point, not this address',
        text: `A forecast is for a point, and the nearest point an archive has `
        + `is not always this address. Where it is far enough to be another place the section says `
        + `how far${(d.far_from_node || []).length ? '' : '; on this node it does not, which means it '
        + 'is near enough'}.` },
    ];
  },
});

});

/* ================================================================= h/wall.js — the wall, and the dial turning by itself ==== */
/* The wall: a field of hexagons, and the dial turning by itself.
 *
 * A wall is read from three metres, in the dark, by somebody who did not open it. It has no mouse
 * and nobody scrolls it, so everything it says has to be on one screen. Tomas asked for a wall
 * "fully based in the hexagon system", so the wall IS the grid: the nineteen cells this node
 * published at the current resolution — its own and the two steps around it — drawn large enough
 * that a number sits inside each one, and every number is what is actually read in that cell. The
 * dial stands at one stop for eight seconds and then at the next, 2 to 12 and back, and the field
 * re-fills: at 4 every station this node hears is in one cell; at 6 they spread into five; from 7 to
 * 10 the picture does not change — which is finding 6, and this is the only surface on which a
 * household can watch it happen.
 *
 * WHY EIGHT SECONDS AND WHY NO TWEEN. The design log's rule on motion is that motion is bound to
 * the cadence of its own datum, and a motion with no datum behind it is deleted. The datum here is
 * the resolution, and a resolution is a step: there is no place between 7 and 8, so nothing here
 * morphs, slides or zooms between stops. The field is redrawn, the numbers are replaced, the stop is
 * filled. The clock is the dial itself; the thin bar under it is only that clock made visible.
 * Eight seconds is about how long it takes to read one stop out loud. Tomas asked for this
 * animation knowing the rule, and the rule is why it is a step and not a glide.
 *
 * WHAT A CELL SAYS. Nothing is averaged across stations — the reason to draw cells is that they are
 * not one number. A cell with one station shows that station's own 15-minute mean of the variable
 * the wall is set to (?var=, PM2.5 by default) and its name. A cell with several shows how many and
 * the range, low to high. This node's own cell shows its own stations' values, each one. An empty
 * cell is drawn and left empty, because "no station is reading there" is half of what a grid is for.
 * No map under the cells: at three metres a photograph behind a numeral is noise, and the hexagon
 * is the module the whole design system is built on.
 *
 * Under prefers-reduced-motion nothing turns. The wall stands at the stop it opened on and the
 * stops are still there to press. Pressing a stop, in either mode, turns the dial to it and holds it
 * for half a minute; pressing a cell names it and holds too. Arrow keys turn it.
 *
 * Modules may still contribute to the wall through the contract's wall(); their fragments sit in
 * one row under the field, the first five, with a count of the rest. At three metres ten small
 * columns are unreadable, and the field already carries the numbers that matter.
 */
PAI_LOAD.push(function () {
'use strict';

const H = window.H3;
const DWELL_MS = 8000;
const HOLD_MS = 30000;
const STILL = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
let WALL_PAUSED = false;   /* survives a re-render: the wall is redrawn whenever the route runs */
const MAX_FRAGMENTS = 8;   /* the two Singapore rows carry eight between them; the rest go to "more in Now" */

/* One hexagon, pointy-top, centred in a 100-unit box, for the dial's stops. A stop is pressed, it is
 * never pointed at: the strip is a control, not a gauge. */
const HEX = [30, 90, 150, 210, 270, 330].map(a => {
  const r = a * Math.PI / 180;
  return `${(50 + 45 * Math.cos(r)).toFixed(1)},${(50 + 45 * Math.sin(r)).toFixed(1)}`;
}).join(' ');

/* PORTED: the wall's CSS is in dashboard.css, under a banner naming this file, and style() with it. */

/* ------------------------------------------------------------------ the parts that turn */
const at = (ctx, res) => ({ ...ctx, RES: res,
  grain: H.grain_table.find(g => g.res === res),
  HERE: { ...ctx.HERE, res, id: ctx.N.chain[res] } });

const VAR = ctx => (ctx.Q.get('var') && H.metrics[ctx.Q.get('var')] ? ctx.Q.get('var') : 'pm25');

/* WHAT THE WALL MAY SHOW. The field has always drawn whatever `?var=` named and defaulted to PM2.5;
 * what it never had was a way to say so from the wall itself, so a wall was an air-quality wall and
 * nothing else — reported from node #1.
 *
 * The strip offers every variable at least one station on this node actually carries, in the order
 * the node declares them. It is not a list of air-quality variables and there is nothing here that
 * knows the word "air": when a water pack or a soil pack publishes a metric and a station reads it,
 * it appears in this strip because it appears in H.metrics, with no change to this file. That is the
 * whole of what "and eventually other categories" needs from the wall.
 *
 * A variable no station reads is not offered. A control that draws an empty field is a control that
 * lies about what this node measures. */
const carried = () => Object.keys(H.metrics).filter(v => (H.sensors || []).some(s => s.read && s.read[v]));

/* FOUR, AND THE REST REACHABLE. Tomas's call, 22 September.
 *
 * The sketch draws four chips; this node reads nine, and it will read more as packs land. Nine
 * chips wrapped to two rows and pushed the counts down — on a surface read at three metres, a strip
 * that long is a list rather than a control. So: the one being shown, then the node's own order, up
 * to four, and a link to the rest. `?vars=all` rather than a press-to-expand, because a wall screen
 * is not touched and a link still works from the phone somebody is holding.
 *
 * The current variable is always among the four, wherever it sits in the node's order — otherwise
 * the strip could be showing temperature with no chip saying so. */
const VARS_SHOWN = 4;
function vars(ctx) {
  const { esc } = ctx.K;
  const list = carried(), v = VAR(ctx);
  if (list.length < 2) return '';
  const all = ctx.Q.get('vars') === 'all';
  const order = [v, ...list.filter(k => k !== v)];
  const show = all ? list : order.slice(0, VARS_SHOWN);
  const hidden = list.length - show.length;
  return `<div class="wvars" id="wall-vars" data-component="wallVars" data-ref="wall-field"`
    + ` role="group" aria-label="what the cells show">`
    + show.map(k => `<a class="${k === v ? 'on' : ''}" href="${esc(ctx.qlink({ var: k }))}"`
      + `${k === v ? ' aria-current="true"' : ''}>${esc(H.metrics[k].label)}</a>`).join('')
    + (hidden > 0
      ? `<a class="more" href="${esc(ctx.qlink({ vars: 'all' }))}">+${hidden} more</a>`
      : all && list.length > VARS_SHOWN
        ? `<a class="more" href="${esc(ctx.qlink({ vars: null }))}">fewer</a>` : '')
    + `</div>`;
}

/* The centre of a projected cell: the mean of its path's vertices. make-h3.mjs wrote the path;
 * this reads it back rather than asking for a second field it would then have to ship. */
function centroid(d) {
  const pts = d.replace(/[MZ]/g, '').split('L').map(p => p.split(',').map(Number));
  const x = pts.reduce((a, p) => a + p[0], 0) / pts.length;
  const y = pts.reduce((a, p) => a + p[1], 0) / pts.length;
  return [x, y];
}

/* ------------------------------------------------------------------ the field */
/* Nineteen cells, and in each the thing read there. State is weight, fill and dash; the hue is the
 * layer's one accent and it means "this node's own". */
/* THE FADED LAND OUTLINE UNDER THE WALL'S CELLS. A public coastline that ships with the dashboard
 * (static/coast-outline.json, URA Master Plan 2014 via data.gov.sg, Singapore Open Data Licence), so it is offline, needs no token and
 * says nothing about the household: it is the island, not the place. It is fetched once, from this
 * node, and drawn behind the cells at low opacity so the numbers stay the loudest thing on the wall.
 * `?outline=off` hides it. The plate's own drawing space is a 600-unit box; the map from degrees to
 * that box is fitted from the plate's cells, which exist in both frames, so nothing is assumed about
 * how the node scaled them. */
let OUTLINE = null, LAYERS = null, OUTLINE_ASKED = false;
function outlineLoad() {
  if (OUTLINE_ASKED) return;
  OUTLINE_ASKED = true;
  fetch('static/coast-outline.json').then(r => r.ok ? r.json() : null).then(j => {
    if (!j || !Array.isArray(j.rings)) return;
    OUTLINE = j;
    /* Redraw the wall once, if it is what is on screen. */
    if (document.querySelector('#page #wall-lead') && window.PAI_ROUTE) window.PAI_ROUTE();
  }).catch(() => { /* no outline is a wall with no outline */ });
  /* The wider region and the event circuit are a second, optional file: without it the wall is the island alone. */
  fetch('static/wall-layers.json').then(r => r.ok ? r.json() : null).then(j => {
    if (!j) return;
    LAYERS = j;
    if (document.querySelector('#page #wall-lead') && window.PAI_ROUTE) window.PAI_ROUTE();
  }).catch(() => { /* no layers is a wall without them */ });
}
function outlineFit(plate) {
  const xs = [], ys = [], lons = [], lats = [];
  for (const ll of plate.cells_ll) {
    const dc = plate.draw.cells.find(c => c.id === ll[0]);
    if (!dc) continue;
    const nums = dc.d.replace(/[MZ]/g, '').split('L').map(p => p.split(',').map(Number));
    const n = Math.min(nums.length, (ll.length - 1) / 2);
    for (let i = 0; i < n; i++) { lats.push(ll[1 + 2 * i]); lons.push(ll[2 + 2 * i]); xs.push(nums[i][0]); ys.push(nums[i][1]); }
  }
  if (xs.length < 4) return null;
  const fit = (a, b) => {   /* least squares b = s*a + t */
    const n = a.length, ma = a.reduce((p, q) => p + q, 0) / n, mb = b.reduce((p, q) => p + q, 0) / n;
    let num = 0, den = 0;
    for (let i = 0; i < n; i++) { num += (a[i] - ma) * (b[i] - mb); den += (a[i] - ma) ** 2; }
    return den ? { s: num / den, t: mb - (num / den) * ma } : null;
  };
  const fx = fit(lons, xs), fy = fit(lats, ys);
  return fx && fy ? { fx, fy } : null;
}
/* Degrees to the plate's 600-unit box, as an SVG path. `close` joins the ends; `cull` drops a ring that never
   comes near the drawing, which keeps the wide region cheap at the finest resolutions. */
function outlinePath(f, plate, rings, close, cull) {
  const box = plate.draw.box, m = box * 0.5;
  let d = '';
  for (const r of rings) {
    /* Cull on the ring's own box, not on its vertices: a coast simplified to a vertex every few km can run
       straight across the drawing with none of its vertices in it, and was being dropped whole. */
    let s = '', x0 = Infinity, x1 = -Infinity, y0 = Infinity, y1 = -Infinity;
    for (let i = 0; i < r.length; i += 2) {
      const x = f.fx.s * r[i] + f.fx.t, y = f.fy.s * r[i + 1] + f.fy.t;
      if (x < x0) x0 = x; if (x > x1) x1 = x; if (y < y0) y0 = y; if (y > y1) y1 = y;
      s += `${i ? 'L' : 'M'}${x.toFixed(1)},${y.toFixed(1)}`;
    }
    if (!cull || (x1 > -m && x0 < box + m && y1 > -m && y0 < box + m)) d += s + (close ? 'Z' : '');
  }
  return d;
}
/* Behind the cells, back to front: the Southeast Asian mainland and islands (faint, lines only), then the
   island itself (a shallow-water halo, a little fill, the coast). */
function outlineSvg(ctx, plate) {
  outlineLoad();
  if (ctx.Q.get('outline') === 'off') return '';
  const f = outlineFit(plate);
  if (!f) return '';
  let out = '';
  const reg = LAYERS && Array.isArray(LAYERS.region) && ctx.Q.get('outline') !== 'island'
    ? outlinePath(f, plate, LAYERS.region, true, true) : '';
  if (reg) out += `<g class="region" aria-hidden="true"><path d="${reg}"/></g>`;
  /* The island's rings include its water (reservoirs, rivers, Marina Bay) as holes, so one even-odd path draws both. */
  const d = OUTLINE ? outlinePath(f, plate, OUTLINE.rings, true, true) : '';
  if (d) out += `<g class="outline" aria-hidden="true"><path class="shore" d="${d}"/><path d="${d}"/></g>`;
  return out;
}

/* THE CIRCUIT. While an international event is on, its street circuit is drawn in the role red over the
 * cells, with a short bright dash running round it. The dates are in static/wall-layers.json (`from` to
 * `to`), so the wall puts it up and takes it down on its own, and `?track=on` / `?track=off` overrides
 * that. It is a link to nothing: it is a drawing with a tooltip. The animation is CSS, so
 * prefers-reduced-motion and the wall's pause button both stop it. */
function trackSvg(ctx, plate) {
  const T = LAYERS && LAYERS.track, q = ctx.Q.get('track');
  if (!T || !Array.isArray(T.path) || q === 'off') return '';
  const today = new Date().toISOString().slice(0, 10);
  if (q !== 'on' && !(today >= T.from && today <= T.to)) return '';
  const f = outlineFit(plate);
  if (!f) return '';
  const d = outlinePath(f, plate, [T.path], true, true);
  if (!d) return '';
  const tip = window.K.esc(T.tip || T.name);
  /* The dash keeps its phase across the wall's redraws, which happen at every dial step. */
  const delay = -((Date.now() % 9000) / 1000).toFixed(2);
  return `<g class="track" tabindex="0" role="img" aria-label="${tip}"><title>${tip}</title>`
    + `<path class="hit" d="${d}"/><path class="line" d="${d}"/>`
    + `<path class="car" d="${d}" pathLength="100" style="animation-delay:${delay}s"/></g>`;
}

function field(ctx, sel) {
  const { esc, fmt } = ctx.K, { address, km2, edge } = ctx.KH, N = ctx.N;
  /* Unsited, the plate is nineteen cells of open water and the stations are placed in them. The wall
     is the surface nobody is watching, so it says what it does not know rather than drawing the Gulf
     of Guinea at three metres and labelling it this house. */
  if (!ctx.KH.sited()) {
    return `<p class="note">This node has no coordinates, so there is no ground to draw cells on. `
      + `Setting NODE_LAT and NODE_LON — planetai setup, or the Set up view — gives this node a cell `
      + `and puts its ${H.sensors.length} stations in the cells around it.</p>`;
  }
  const res = ctx.RES, plate = H.nav.plates[res], v = VAR(ctx), M = H.metrics[v];
  const line = M.issue && ctx.ISS[M.issue] && ctx.ISS[M.issue].line ? ctx.ISS[M.issue].line : null;
  const cmpFor = () => line ? `against the line, ${fmt(line.value, M.dp)} ${ctx.ISS[M.issue].unit}`
    : `no comparison yet · no line is declared for ${M.label}`;
  const d = plate.draw;
  /* Type is sized to the cell it sits in. The plate is nineteen cells in a 600-unit box whatever
   * the resolution, so a cell is about 120 units across at every stop; a numeral a third of that
   * fits with its caption, and a numeral of fixed size ran across three cells — measured, once. */
  const cw = (() => {
    const c0 = d.cells.find(c => c.id === plate.centre) || d.cells[0];
    const xs = c0.d.replace(/[MZ]/g, '').split('L').map(p => +p.split(',')[0]);
    return Math.max(...xs) - Math.min(...xs);
  })();
  const F = { big: (cw * 0.30).toFixed(1), mid: (cw * 0.21).toFixed(1), sm: (cw * 0.085).toFixed(1),
    nm: (cw * 0.095).toFixed(1), unit: (cw * 0.085).toFixed(1) };
  const dy = { top: -(cw * 0.19), base: cw * 0.10, bot: cw * 0.25 };
  const T = (x, y, cls, txt, extra = '') => `<text x="${x.toFixed(1)}" y="${y.toFixed(1)}" text-anchor="middle"`
    + ` class="${cls}" style="font-size:${F[cls]}px"${extra}>${txt}</text>`;
  const kmRange = st => { const ks = st.map(s => s.km).filter(k => k != null);
    if (!ks.length) return 'distance unknown';
    const lo = Math.min(...ks), hi = Math.max(...ks);
    return lo === hi ? `${lo} km` : `${lo}–${hi} km`; };
  /* Cells drawn back to front: empty, then read, then this node's own on top, so its stroke wins. */
  const order = d.cells.slice().sort((a, b) => {
    const ra = a.id === plate.centre ? 2 : (H.nav.cells[a.id].sensors.length ? 1 : 0);
    const rb = b.id === plate.centre ? 2 : (H.nav.cells[b.id].sensors.length ? 1 : 0);
    return ra - rb;
  });
  let cells = '', labels = '', reading = 0;
  for (const c of order) {
    const info = H.nav.cells[c.id];
    const own = c.id === plate.centre, isSel = c.id === sel;
    const st = info.sensors.map(i => H.sensors[i]);
    const has = st.length > 0;
    cells += `<path class="cel" data-cell="${esc(c.id)}" d="${c.d}" fill="var(--cells)"`
      + ` fill-opacity="${own ? 0.14 : has ? 0.06 : 0}" stroke="var(${isSel ? '--ink' : own ? '--cells' : '--ink'})"`
      + ` stroke-opacity="${own || isSel ? 1 : has ? 0.6 : 0.22}"`
      + ` stroke-width="${isSel ? 4 : own ? 3 : has ? 1.6 : 1}"`
      + `${own || has || isSel ? '' : ' stroke-dasharray="4 4"'}><title>${esc(c.id)}</title></path>`;
    if (!has) continue;
    const [x, y] = centroid(c.d);
    const vals = st.map(s => s.read[v] ? s.read[v].value : null).filter(x => x != null);
    if (vals.length) reading++;   // cells with a reading OF THIS VARIABLE, which is what is drawn
    if (own) {
      /* this node's own cell: each of its own stations' values, in a row */
      const mine = st.filter(s => s.local), theirs = st.filter(s => !s.local);
      const mv = mine.map(s => s.read[v] ? fmt(s.read[v].value, M.dp) : '—');
      labels += T(x, y + dy.top, 'sm', `this house · ${mine.length}${theirs.length ? ` · ${theirs.length} not ours` : ''}`)
        + T(x, y + dy.base, mv.length > 2 ? 'mid' : 'big', esc(mv.join(' · ')),
          ` data-num="wall.own.${esc(v)}" data-cmp="${esc(cmpFor())}"`)
        + T(x, y + dy.bot, 'unit', `${esc(M.unit)} · ${esc(M.label)}`);
    } else if (st.length === 1) {
      const s1 = st[0], r = s1.read[v];
      labels += T(x, y + dy.top, 'nm', esc((s1.name || s1.sensor_id).slice(0, 18)))
        + T(x, y + dy.base, 'big', r ? esc(fmt(r.value, M.dp)) : '—',
          ` data-num="wall.${esc(c.id)}.${esc(v)}" data-cmp="${esc(r ? cmpFor() : `does not measure ${M.label}`)}"`)
        + T(x, y + dy.bot, 'unit', `${r ? esc(M.unit) : 'not measured'} · `
          + `${s1.km == null ? 'distance unknown' : `${s1.km} km`}`);
    } else {
      const lo = vals.length ? Math.min(...vals) : null, hi = vals.length ? Math.max(...vals) : null;
      labels += T(x, y + dy.top, 'sm', `${st.length} stations · ${kmRange(st)}`)
        + T(x, y + dy.base, vals.length && lo !== hi ? 'mid' : 'big',
          vals.length ? (lo === hi ? esc(fmt(lo, M.dp)) : `${esc(fmt(lo, M.dp))}–${esc(fmt(hi, M.dp))}`) : '—',
          ` data-num="wall.${esc(c.id)}.${esc(v)}" data-cmp="${esc(vals.length
            ? `${vals.length} of ${st.length} measure ${M.label}; low to high, never a mean; ${cmpFor()}`
            : `none measures ${M.label}`)}"`)
        + T(x, y + dy.bot, 'unit', `${esc(M.unit)} · low–high`);
    }
  }
  const pts = (d.points || []).map(p =>
    `<circle cx="${p.x}" cy="${p.y}" r="${p.local ? 4 : 2.6}" fill="${p.local ? 'var(--cells)' : 'var(--ground)'}"`
    + ` stroke="var(--ink)" stroke-width="${p.local ? 1.6 : 1.1}"><title>${esc(p.name || p.sensor_id)}</title></circle>`)
    .join('');
  const G = ctx.grain;
  const selInfo = sel && H.nav.cells[sel] ? H.nav.cells[sel] : null;
  /* `reading` and not grain_table's `occupied`: occupied counts cells with any station at all, and
     the label used to claim those cells were reading this variable where the drawing plainly says
     they do not measure it. Count the thing that is drawn. */
  return `<svg viewBox="0 0 ${d.box} ${d.box}" role="img" aria-label="resolution ${res}: the nineteen cells `
    + `this node published, ${reading} of them with a station reading ${M.label}">`
    + outlineSvg(ctx, plate) + `<g class="cells">${cells}</g>` + trackSvg(ctx, plate) + `<g class="pts">${pts}</g><g class="labels">${labels}</g></svg>`
    + `<div class="cap"><span>${address(N.chain[res], res)}</span>`
    + `<span>one cell <b data-num="h3.res${res}.area" data-cmp="against ${esc(km2(H.ladder[res].own_area_m2))}, `
    + `this node's own cell at this resolution">${esc(km2(G.area_m2))}</b> · <b>${esc(edge(G.edge_m))}</b> to an edge</span>`
    + `<span>${selInfo ? `pressed: ${esc(sel)} · ${selInfo.sensors.length} ${selInfo.sensors.length === 1
      ? 'station' : 'stations'}`
      : `${esc(M.label)} · press a cell to name it`}</span></div>`;
}

/* Eleven stops. State is fill, weight and dash: the stop you are on is ink, the stops coarse enough
 * to leave this machine carry a light cells fill, the stops finer than this node says where it is
 * are dashed. */
/* The scale names from planetai.fab.city/nodes ("five scales, one code"): home about 1 km and one cell,
 * community about 5 km, city about 15 km, region about 100 km. The page names scales, not H3 resolutions,
 * so each rung takes the nearest scale by cell size; region is about 100 km and the ladder's coarsest
 * rung is res 4 (about 40 km across), so that rung is labelled as the nearest one. Finer than home, the
 * page says a home node "reads the room and the street", which is what the last two bands say. */
const SCALES = [
  { key: 'region', label: 'Region', hint: 'about 100 km, a partner cluster (nearest rung)', res: [2, 3, 4] },
  { key: 'city', label: 'City', hint: 'about 15 km, the host institution', res: [5] },
  { key: 'community', label: 'Community', hint: 'about 5 km, a lab\u2019s reach', res: [6, 7] },
  { key: 'home', label: 'Home', hint: 'about 1 km, one cell: where this node stands', res: [8] },
  { key: 'street', label: 'Street', hint: 'finer than home: the street', res: [9, 10, 11] },
  { key: 'room', label: 'Room', hint: 'finer than home: the room', res: [12, 13, 14] },
];
const scaleOf = r => SCALES.find(x => x.res.includes(r));
/* The strip of scale names under a row of stops, one grid column per stop, shared by the wall's dial and
   Now's rail so the same rung carries the same name everywhere. */
const scaleStrip = (table, cur) => {
  const e = t => String(t).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  return `<div class="scales" aria-hidden="true" style="grid-template-columns:repeat(${table.length},minmax(0,1fr))">`
    + SCALES.map(sc => {
      const idx = table.map((g, i) => sc.res.includes(g.res) ? i : -1).filter(i => i >= 0);
      if (!idx.length) return '';
      return `<span class="sc${sc.res.includes(cur) ? ' on' : ''}" title="${e(sc.hint)}"`
        + ` style="grid-column:${idx[0] + 1} / span ${idx.length}">${e(sc.label)}</span>`;
    }).join('') + `</div>`;
};
window.PAI_SCALES = { SCALES, scaleOf, scaleStrip };

function dial(ctx) {
  const { esc } = ctx.K, { km2, edge } = ctx.KH, N = ctx.N;
  const stops = H.grain_table.map((g, i) => {
    const on = g.res === ctx.RES;
    const above = H.grain_table[i - 1];
    const cmpEdge = above ? `against resolution ${above.res} above it, ${edge(above.edge_m)} to an edge`
      : 'the coarsest this node publishes; nothing above it here';
    return `<a class="stop${on ? ' on' : ''}${g.may_leave ? ' leaves' : ''}`
      + `${g.finer_than_published ? ' toofine' : ''}" href="${ctx.link(N.chain[g.res], { res: g.res })}"`
      + ` data-res="${g.res}"${on ? ' aria-current="true"' : ''}`
      + ` aria-label="resolution ${g.res}, one cell ${esc(km2(g.area_m2))}">`
      + `<svg viewBox="0 0 100 100" aria-hidden="true"><polygon points="${HEX}"`
      + ` fill="${on ? 'var(--ink)' : g.may_leave ? 'var(--cells)' : 'none'}"`
      + ` fill-opacity="${on ? 1 : g.may_leave ? 0.16 : 0}" stroke="var(--ink)"`
      + ` stroke-width="${on ? 3 : 1.6}"${g.finer_than_published && !on ? ' stroke-dasharray="7 5"' : ''}/>`
      + `<text x="50" y="52" text-anchor="middle" dominant-baseline="central"`
      + ` data-num="h3.res" data-cmp="against ${N.res_min} to ${N.res_max}, the resolutions this `
      + `node publishes">${g.res}</text></svg>`
      + `<span class="edge" data-num="h3.res${g.res}.edge" data-cmp="${esc(cmpEdge)}">`
      + `${esc(edge(g.edge_m))}</span>`
      + `</a>`;
  }).join('');
  const cur = H.grain_table.find(g => g.res === ctx.RES);
  return `<div class="dialhead" aria-hidden="true"><b>Resolution ladder</b>`
    + `<span>coarse (wide cells)<i>→</i>fine (small cells)</span></div>`
    + `<div class="stops" role="group" aria-label="resolution, ${N.res_min} to ${N.res_max}; `
    + `standing at ${ctx.RES}">${stops}</div>`
    + scaleStrip(H.grain_table, ctx.RES)
    + `<div class="dialnow" aria-hidden="true">you are here: resolution ${ctx.RES}${scaleOf(ctx.RES) ? ` · ${esc(scaleOf(ctx.RES).label)} scale` : ''}`
    + `${cur ? `, ${esc(edge(cur.edge_m))} to a cell edge` : ''}</div>`
    + `<div class="clock" id="wall-clock" data-component="clock" data-ref="wall-dial"`
    + ` aria-hidden="true"><i></i></div>`;
}

/* What this grain says, as three numbers re-derived from the stop. */
function grain(ctx) {
  const { esc } = ctx.K, G = ctx.grain, n = H.sensors.length;
  const finest = H.grain_table[H.grain_table.length - 1];
  /* The same three counts as the Now view's grain line, and unknown for the same reason: "in this
     node's own cell" is a question about a cell this node does not have yet. */
  if (!ctx.KH.sited()) {
    return `<div class="col" data-ref="wall-dial"><h3 data-role="wall-issue">Cells with a station`
      + `</h3><div class="line"><span class="num" data-num="grain.occupied" data-cmp="no comparison `
      + `yet · this node has no coordinates, so no station has a cell">—</span>`
      + `<small>of 19 drawn</small></div></div>`
      + `<div class="col" data-ref="wall-dial"><h3 data-role="wall-issue">In this node’s cell</h3>`
      + `<div class="line"><span class="num" data-num="grain.in_my_cell" data-cmp="no comparison yet `
      + `· this node has no cell until it is sited">—</span><small>of ${n} stations</small></div></div>`;
  }
  const num = (key, v, cmp) => `<span class="num" data-num="${esc(key)}" data-cmp="${esc(cmp)}">`
    + `${esc(String(v))}</span>`;
  return `<div class="col" data-ref="wall-dial"><h3 data-role="wall-issue">Cells with a station</h3>`
    + `<div class="line">${num('grain.occupied', G.occupied, `against ${finest.occupied} at resolution `
      + `${finest.res}, the finest here`)}<small>of 19 drawn</small></div></div>`
    + `<div class="col" data-ref="wall-dial"><h3 data-role="wall-issue">In this node’s cell</h3>`
    + `<div class="line">${num('grain.in_my_cell', G.in_my_cell, `against ${n} stations in all`)}`
    + `<small>of ${n} stations</small></div></div>`
    + `<div class="col" data-ref="wall-dial"><h3 data-role="wall-issue">Of them, its own</h3>`
    + `<div class="line">${num('grain.mine_in_my_cell', G.mine_in_my_cell,
      `against the ${G.in_my_cell} in this node’s cell`)}<small>this house’s</small></div></div>`;
}

/* The modules' row: the first few fragments the contract's wall() hands over, and a count of the
 * rest, because at three metres ten small columns are unreadable and the field already carries the
 * numbers that matter. */
function more(ctx) {
  let frags = [];
  try {
    const html = window.PAI ? window.PAI.wall(ctx) || '' : '';
    frags = html.split(/(?=<div class="col")/).filter(x => x.trim());
  } catch { frags = []; }
  const shown = frags.slice(0, MAX_FRAGMENTS), rest = frags.length - shown.length;
  return shown.join('') + (rest > 0 ? `<div class="rest">+${rest} more in Now</div>` : '');
}

/* ------------------------------------------------------------------ the wall */
function render(ctx, sel) {
  const { K } = ctx, { esc } = K;
  const hk = ctx.S.issues.headline, d = ctx.ISS[hk];
  /* PORTED: body.wall hides the header, so the wall has no heading at all and axe's
     page-has-heading-one fires on it. The node's name is the page's heading on every other view and
     it is the wall's too — read out, not drawn, because the wall already says it in the foot. */
  /* THE WAY BACK. The click handler at the foot of this file has always listened for `.wall .exit`
     and nothing ever drew one, so a wall was a room with the door painted on: the nav is hidden on
     this view (body.wall), the browser chrome is usually hidden too on the screen this is for, and
     a reader who pressed Wall had no way out but the keyboard. It is a button rather than a link
     because it changes the view and does not go anywhere, and it is drawn first so it is the first
     thing the keyboard reaches. */
  /* THE TOP BAR — the sketch's, 18–20 September, and the one part of that wall this page did not
     carry. Which node, which cell, how open it is, how often the field turns, and what the numbers
     in it are: at three metres those are the questions asked before any reading is read, and they
     were all in the foot, which on a 1080 px screen is the last place the eye arrives. The variable
     and its unit go at the right, because they are the caption for everything in the field. */
  const share = ((ctx.S.health || {}).share_level || 'off');
  const m = H.metrics[VAR(ctx)] || {};
  return `<div class="wallbox" id="wall-lead" data-band="wall">`
    + `<h1 class="vh">${esc(ctx.S.health.node)} · the wall</h1>`
    + `<div class="wtop" id="wall-top" data-component="wallTop" data-ref="wall-field">`
    + `<button type="button" class="exit" data-view="now" data-component="wallExit"`
    + ` data-ref="wall-field" id="wall-exit">back</button>`
    /* The chips ride the bar rather than taking a row of their own. Four of them fit beside the
       exit, and a row here is 48 px off the field — which is the one thing on this surface that
       wants every pixel. The wall's rule is that nothing falls below 1080, and that rule wins. */
    + vars(ctx)
    + `<span class="who">${esc(ctx.S.health.node)}<i>·</i>${esc(ctx.S.health.city || '')}`
    + `<i>·</i>#wall</span>`
    + `<span class="what">${esc(m.label || VAR(ctx))}<i>·</i>${esc(m.unit || '')}`
    + `<i>·</i>15-min means</span>`
    + (STILL ? '' : `<button type="button" class="wpause" id="wall-pause" data-component="wallPause" data-ref="wall-dial"`
      + ` aria-pressed="${WALL_PAUSED}">${WALL_PAUSED ? 'play' : 'pause'}</button>`)
    + `<details class="winfo" data-component="wallInfo" data-ref="wall-dial"><summary aria-label="About this wall" title="About this wall">i</summary>`
    + `<div class="winfo-body"><p>Answer on Telegram, not here.</p>`
    + `<p>The labels under the ladder (Region, City, Community, Home, Street, Room) are the scales from planetai.fab.city/nodes: home is about 1 km and one cell, community about 5 km, city about 15 km, region about 100 km. Street and room are finer than home. The faint island shape behind the cells, and the fainter outline of Southeast Asia around it, are public coastlines that ship with the dashboard, so they work offline (add ?outline=off to hide both, or ?outline=island to keep only the island). While the Singapore Grand Prix is on, the red loop is the Marina Bay street circuit; hover it for details, and the pause button stops its moving dash. The row of numbered hexagons is the resolution ladder: each hexagon is one rung, coarse on the left, fine on the right. The solid dark one, marked “you are here”, is the rung the map is showing. Lightly filled rungs are coarse enough to leave this machine; dashed rungs are finer than this node publishes.</p>`
    + `<p>${STILL ? 'Reduced motion is on, so the ladder stands still. Press a rung to move it.'
      : `The ladder moves by itself every ${DWELL_MS / 1000} s, with nothing interpolated between rungs. Under reduced motion it stands still.`}</p></div></details></div>`
    + `<div class="wgrid">`
    + `<figure class="wfield" id="wall-field" data-component="wallField" data-ref="wall-dial">`
    + field(ctx, sel) + `</figure>`
    + `<div class="wside">`
    + `<div id="band-${esc(hk)}">${K.kicker(hk, d)}${K.sentence(hk, d, 'big')}${K.why(hk, d)}${K.ask(hk, d)}</div>`
    /* The sketch puts this where an ask would be, in the column, rather than in the foot. It is the
       wall's own refusal and it answers the question the ask above it raises. */
    + `<div class="wdial" id="wall-dial" data-component="dial" data-ref="wall-field" role="group"`
    + ` aria-label="the ladder">${dial(ctx)}</div>`
    /* And the dial says how to read itself, under itself. The foot's caption is about the MOTION;
       this one is about the marks, and a reader looking at the stops should not have to look away. */
    + `<div class="wgrain" id="wall-grain" data-component="wallGrain" data-ref="wall-dial">${grain(ctx)}</div>`
    + `<div class="wrho">${K.rhoRow(false, 'wall-dial', true)}</div>`
    + `</div></div>`
    + `<div class="wmore" id="wall-more" data-component="wallMore" data-ref="wall-field">${more(ctx)}</div>`
    /* The node's name, the share level and the dial's cadence have gone to the top bar and the
       Telegram line into the column, so the foot is what is left: when this was true, which cell it
       is about, and whether the node has stopped answering. Nothing is said twice. */
    + `<div class="foot">${K.asof()}${K.stamp()}<span class="st">stale</span>`
    + `</div>`
    + `</div>`;
}

/* The clock. One interval, one stop per tick, and every tick checks the wall is still on the page
 * before it touches anything: the shell may have rendered something else since. */
function start(ctx) {
  /* #wall-lead is written by this file, not by index.html, so it is looked up under the one id
     the document itself owns. tools/check_ui.py's first rule compares getElementById against the
     markup, and a rendered id can never be in it. */
  const box = () => document.querySelector('#page #wall-lead');
  if (!box()) return;
  const N = ctx.N;
  let res = ctx.RES, sel = null, timer = null, holdUntil = 0;
  /* start() runs on every route(); without this each run stacked another interval and another pair of
     document listeners, so the dial stepped faster and pressed twice. */
  if (window.__wallOff) window.__wallOff();

  function show(r) {
    const b = box();
    if (!b) { clearInterval(timer); return; }
    res = r;
    const c = at(ctx, r);
    const fl = b.querySelector('#wall-field'), dl = b.querySelector('#wall-dial'),
      gr = b.querySelector('#wall-grain'), mo = b.querySelector('#wall-more');
    b.classList.toggle('paused', WALL_PAUSED);
    if (fl) fl.innerHTML = field(c, sel);
    if (dl) dl.innerHTML = dial(c);
    if (gr) gr.innerHTML = grain(c);
    if (mo) mo.innerHTML = more(c);
    if (Date.now() < holdUntil) { const k = b.querySelector('#wall-clock'); if (k) k.classList.add('held'); }
  }
  const step = dir => { sel = null; show(res + dir > N.res_max ? N.res_min : res + dir < N.res_min ? N.res_max : res + dir); };

  if (!STILL) {
    timer = setInterval(() => {
      if (!box()) { clearInterval(timer); return; }
      if (WALL_PAUSED || Date.now() < holdUntil) return;
      step(1);
    }, DWELL_MS);
  }

  /* A press turns the dial here, without a reload, and holds it for a while. The href still says
   * where it went, so the address bar and a copied link say the same stop the wall shows. A press on
   * a cell names it in the caption and holds the clock the same way. */
  function hold() {
    holdUntil = Date.now() + HOLD_MS;
    const k = box() && box().querySelector('#wall-clock'); if (k) k.classList.add('held');
  }
  const onClick = e => {
    if (!box()) return;
    const pz = e.target.closest && e.target.closest('#wall-pause');
    if (pz) {
      WALL_PAUSED = !WALL_PAUSED;
      pz.textContent = WALL_PAUSED ? 'play' : 'pause';
      pz.setAttribute('aria-pressed', String(WALL_PAUSED));
      const wb = box(); if (wb) wb.classList.toggle('paused', WALL_PAUSED);
      return;
    }
    const a = e.target.closest && e.target.closest('#wall-dial a.stop');
    if (a) {
      e.preventDefault(); e.stopImmediatePropagation();
      hold(); sel = null;
      show(+a.dataset.res);
      /* Keep the hash: the view IS the hash, and dropping it left the wall on the next route(). */
      const href = a.getAttribute('href');
      try { history.replaceState(null, '', href.includes('#') ? href : href + (location.hash || '#wall')); } catch { /* a file:// page */ }
      return;
    }
    const cel = e.target.closest && e.target.closest('#wall-field .cel');
    if (cel) { hold(); sel = cel.getAttribute('data-cell'); show(res); }
  };
  const onKey = e => {
    if (!box()) return;
    if (e.key === 'ArrowRight') { hold(); step(1); }
    else if (e.key === 'ArrowLeft') { hold(); step(-1); }
  };
  document.addEventListener('click', onClick, true);   /* capture: runs before the shell's ?-link handler */
  document.addEventListener('keydown', onKey);
  window.__wallOff = () => {
    clearInterval(timer);
    document.removeEventListener('click', onClick, true);
    document.removeEventListener('keydown', onKey);
  };
}

window.WALL = { render, start, field, dial, grain };

});

/* ================================================================= the shell — boot, the dial, the lead, and the four views ==== */
/* the shell: it runs at load, so it is not on PAI_LOAD. */
(function () {
'use strict';

/* The one load-time read of the URL that is allowed to be one: which snapshot the node replayed is
   answered once, at boot, and no re-render can change it. Everything else reads at call time — see
   query() and the note above where(). */
const FIXTURE = new URLSearchParams(location.search).get('fixture');

/* ------------------------------------------------------------------ the one thing that fetches */
const tok_ = () => localStorage.getItem('planetai_admin') || localStorage.getItem('planetai_act') || '';
const auth_ = () => (tok_() ? { authorization: 'Bearer ' + tok_() } : {});
window.PAI_AUTH = auth_;          /* the ask pane asks with the same token every other read carries */

/* At SHARE_LEVEL=off a reader with no token gets the shell, /health and nothing else. That is a
 * real state a phone on the house WiFi will be in, not an error: the node answers 403 with its own
 * sentence, and the page draws the refused page. A blank would be the node lying about being
 * broken. Carried over from the page this replaces, which had it right. */
function Refused(said) { const e = new Error(said); e.refused = said; return e; }

/* A node whose database is wedged does not answer 500 — it holds the request open, which is the
 * common unattended failure and the one that left a wall screen on blank paper indefinitely. Twenty
 * seconds is longer than /issues has ever taken to compute on node #1 and short enough that a
 * household gets a sentence instead of a blank page; the abort surfaces as the honest failure line
 * the terminal catch draws, the same as any other refusal to answer. */
const TIMEOUT_MS = 20000;

async function api(path) {
  let r;
  /* The loading state's account of what this page asked of the node is measured here, at the one
     place every read goes through, so it cannot come to disagree with what actually happened. It
     records a refusal and a timeout as readily as an answer: a list that only shows successes is a
     list that says nothing on the one occasion somebody is looking at it. */
  const t0 = performance.now();
  ASKING.flight(path);
  try {
    r = await fetch(path, { headers: auth_(), signal: AbortSignal.timeout(TIMEOUT_MS) });
  } catch (e) {
    ASKING.saw(path, performance.now() - t0, false);
    /* A hang and a dropped network arrive here the same way, and neither is an answer. Say which. */
    throw new Error(e && e.name === 'TimeoutError'
      ? `${path} did not answer within ${TIMEOUT_MS / 1000} seconds`
      : `${path} could not be reached: ${(e && e.message) || e}`);
  }
  if (r.status === 403) {
    ASKING.saw(path, performance.now() - t0, false);
    throw Refused((await r.json().catch(() => ({}))).error || 'refused');
  }
  if (!r.ok) {
    ASKING.saw(path, performance.now() - t0, false);
    throw new Error(`${path} answered ${r.status}`);
  }
  const body = await r.json();
  ASKING.saw(path, performance.now() - t0, true);
  return body;
}

/* ------------------------------------------------------------------ the plan */
/* GET /place/geojson projected in this browser with the node's own formula — metres east and south
 * of the node, NODE_DASHBOARD_PLAN_SPEC.md rule 1, the same eight lines make-plan.mjs runs. Every
 * vertex is kept: geoPath's adaptive resampling was measured on this exact dataset dropping corners
 * from 855 of 2,713 buildings, which is why nothing here resamples or simplifies. */
async function plan(health) {
  const gj = await api('/place/geojson');
  /* The map ground (UI_GROUND=map) hands this to MapLibre as it came, in degrees: no second request. */
  window.PLAN_GJ = gj;
  const LAT = health.lat, LON = health.lon;
  const K = Math.cos(LAT * Math.PI / 180) * 111320;
  const r1 = v => Math.round(v * 10) / 10;
  const px = ([lon, lat]) => [r1((lon - LON) * K), r1(-(lat - LAT) * 111320)];
  const flat = ring => ring.flatMap(px);
  /* The first coordinate of a feature, whatever its geometry. A point of interest mapped as an open
     way made the page this replaces destructure a number, and the whole kilometre came back blank
     with nothing said. The marker goes at the feature's first point either way. */
  const firstPt = g => { let c = g && g.coordinates; while (Array.isArray(c) && Array.isArray(c[0])) c = c[0]; return c; };
  const out = { buildings: [], roads: [], green: [], sat: [], poi: [],
    counts: { buildings: 0, buildings_drawn: 0, roads: 0, green: 0, sat: 0, poi: 0, vertices: 0 } };
  let skipped = 0;
  for (const f of (gj.features || [])) {
   try {
    const kind = (f.properties || {}).kind, g = f.geometry || {};
    const rings = g.type === 'Polygon' ? g.coordinates
      : g.type === 'MultiPolygon' ? g.coordinates.flat() : null;
    if (kind === 'building') {
      out.counts.buildings++;
      /* Rule 5: some of a node's buildings are points, not footprints. Counted, never drawn — the
         caption says both numbers rather than quietly rounding one into the other. */
      if (!rings) continue;
      out.counts.buildings_drawn++;
      for (const r of rings) out.buildings.push(flat(r));
    } else if (kind === 'sat') {
      out.counts.sat++;
      if (!rings) continue;
      for (const r of rings) out.sat.push([(f.properties.confidence == null ? 0 : f.properties.confidence), ...flat(r)]);
    } else if (kind === 'green') {
      out.counts.green++;
      if (!rings) continue;
      for (const r of rings) out.green.push(flat(r));
    } else if (kind === 'road') {
      out.counts.roads++;
      if (g.type !== 'LineString') continue;
      out.roads.push([f.properties.highway || 'service', ...flat(g.coordinates)]);
    } else if (kind === 'poi') {
      out.counts.poi++;
      out.poi.push([...px(firstPt(g)), f.properties.category || 'other']);
    }
   } catch (e) { skipped++; }          // one undrawable feature must not blank the kilometre
  }
  if (!out.buildings.length && !out.roads.length && !out.sat.length) return null;
  const all = [...out.buildings, ...out.green, ...out.sat.map(s => s.slice(1)), ...out.roads.map(r => r.slice(1))];
  let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
  for (const r of all) {
    for (let i = 0; i < r.length; i += 2) {
      x0 = Math.min(x0, r[i]); x1 = Math.max(x1, r[i]);
      y0 = Math.min(y0, r[i + 1]); y1 = Math.max(y1, r[i + 1]);
    }
    out.counts.vertices += r.length / 2;
  }
  out.counts.vertices += out.poi.length;
  out.counts.skipped = skipped;
  out.bbox_m = [Math.round(x0), Math.round(y0), Math.round(x1), Math.round(y1)];
  out.span_m = [Math.round(x1 - x0), Math.round(y1 - y0)];
  return out;
}

/* ------------------------------------------------------------------ boot */
/* The page's one fetch sequence. /issues carries everything the sections read; /health names the
 * node and its clock; /settings says what the keeper allowed; /rho is the node's own measurement of
 * itself; /earth names the satellite years it has on disk; /place/geojson is the plan. A failure
 * leaves the global null and the section whose `needs` names it prints one honest line — never a
 * blank, never a retry loop.
 *
 * THE TWO PATHS RETURN DIFFERENT SHAPES, and this is the one place that knows it. GET /issues
 * returns the computed body directly — {order, headline, as_of, issues, stations, metrics, asks,
 * mesh, geometry, …}. GET /issues/fixtures/<name> returns the WHOLE committed snapshot with that
 * same body nested under `.issues`, and the snapshot's own `health`, `rho`, `stats` and `alerts`
 * beside it. Both are normalised here, before anything else reads either.
 */
/* GET /settings answers with app/settings.py's describe(): { unlocked, runtime: [{key, value, secret,
 * …}], bootstrap: [...] } — a list of rows, not a map of keys. Every predicate on this page asks for
 * a key by name, so the rows are flattened onto the same object here, in the one place that knows
 * the endpoint's shape. Without this `window.SETTINGS.MAP_TILES` was undefined on every load, the
 * tiles feature could never be turned on, and two sentences told the keeper the opposite of the
 * setting they had just saved.
 *
 * A value the node MASKED is not a value. describe() writes "•••• set" for every secret and, for a
 * reader without the admin token, for every key outside PUBLIC — so a masked row is left off rather
 * than compared against, and reads as unset. MAP_TILES is in PUBLIC and so arrives unmasked at every
 * share level; unset is also the safe way round for the one setting that decides whether this
 * household's kilometre is named to somebody else's machine.
 *
 * `runtime` and `bootstrap` stay on the object: the Set up pane and readLayout() read the rows. */
const MASKED = '•••• set';
function flatSettings(d) {
  const flat = {};
  for (const r of ((d || {}).runtime || [])) {
    if (r && r.key && !r.secret && r.value !== MASKED) flat[r.key] = r.value;
  }
  return { ...(d || {}), ...flat };
}

/* The three answers, turned into the globals every section reads. boot() calls it once and
 * refresh() calls it again on every poll, so there is one shape and not two that drift. */
/* The one document this page draws is `issues-v0` (ARCHITECTURE.md §3). A node answering a version
   this page does not know is NOT a reason to draw nothing: the fields this page reads are almost
   certainly still there, and a blank screen on a wall tells a household less than a wrong number
   would. So it says one sentence and carries on — the same posture the node's own receivers take,
   for the same reason. A node with no `schema` at all predates the key and is read as issues-v0. */
const ISSUES_WIRE = 'issues-v0';
function wireNote(issues) {
  const said = (issues && issues.schema) || '';
  if (!said || said === ISSUES_WIRE) return null;
  return `This node answers ${said}, and this page draws ${ISSUES_WIRE}. It is showing what it `
    + `recognises; a number that is missing may be one this page has not learned to read yet. `
    + `Updating the page (planetai update) is the fix.`;
}

function bind(issues, health, rho) {
  window.WIRE_NOTE = wireNote(issues);
  window.SNAP = { issues, health, base: { captured_utc: issues.as_of },
    rho, peer: issues.peer || null, fixture: FIXTURE || null };
  const geo = issues.geometry || {};
  /* A station in stations_silent.stations stopped reporting (docs/SPEC_dashboard_figures.md §3.3). It is not a
     station this node reads now, so it is neither on the map nor in the groups; What the stations read lists it in a fold. */
  window.H3 = { ...geo, sensors: issues.stations || [], silent: (issues.stations_silent || {}).stations || [],
    metrics: issues.metrics || {},
    asks: issues.asks || null,
    radio: { ...(geo.radio || {}), mesh: issues.mesh || null,
      mesh_sensor: issues.mesh && issues.mesh.device, mesh_reads: issues.mesh ? issues.mesh.reads : [] },
    /* `position` is 'cell' when this reader was handed the centre of the node's resolution-8 cell
       rather than its point (GET /health, v0.73): then there is no house to put a dot on. */
    node: { lat: health.lat, lon: health.lon, name: health.node, position: health.position || 'point' } };
}

async function boot() {
  const answered = await api(FIXTURE ? `/issues/fixtures/${encodeURIComponent(FIXTURE)}` : '/issues');
  const snapshot = FIXTURE ? answered : null;
  const issues = FIXTURE ? answered.issues : answered;
  ASKING.landed(FIXTURE ? answered.issues : answered);
  const [health, settings] = await Promise.all([
    api('/health'),
    api('/settings').catch(() => ({})),
  ]);
  ASKING.placed(health);
  /* A fixture carries the ρ of the hour it was captured; a live node keeps it at /rho, which is the
     same route the page this replaces read. Neither is computed here. */
  const rho = (snapshot && snapshot.rho) || await api('/rho').catch(() => null);
  const earth = await api('/earth').catch(() => null);
  /* What the node doubts about its own sensors, and the day this place is about to have. Two routes
     the node already serves and the page it replaces already read. A refusal or a pack that has
     never run leaves the global null, and the section whose `needs` names it prints one line. */
  const [trust, forecast, sensors, cells, reach, notes, dayshape, effect, days] = await Promise.all([
    api('/trust').catch(() => null), api('/forecast').catch(() => null),
    /* The network figure's own two reads, restored with it. /issues publishes only stations that
       carry a coordinate, so `models` counted 0 on a node running five of them — the figure needs
       the whole sensor table, kinds and all, which is what /sensors has always been. /cells is the
       Index, and is what "Index cells" out of this node actually means. Both are routes the node
       already serves and the page this replaces already read; neither is new. */
    api('/sensors').catch(() => null), api('/cells').catch(() => null),
    /* /reach is three rows and joins the batch rather than costing a round trip of its own. Every
       node has one — unlike /stats, which is fetched only where there is an appliance to report —
       because every node has a record with a beginning, and Historical's first question is how far
       back it may be asked. */
    api('/reach').catch(() => null),
    /* THE LEDGER'S WORDS, and only the words. `asks.actions` on /issues already carries every act
       with its stage, its actor and its time — but NOT the note, which engine.py:183 drops. That is
       the right call and this does not change it: /issues is on the `open` share allowlist, and
       GET /actions is deliberately on neither, because `actor` and `note` are the household's own
       words about what they did in their own house. So the ledger draws from /issues for everyone
       and asks this route only for the sentences, which arrive for a reader holding a token and do
       not for anyone else. A 403 here is the node working. */
    api('/actions?events=1').catch(() => null),
    api('/shape').catch(() => null),
    api('/effect').catch(() => null),
    /* The strips and Measure's count (docs/SPEC_dashboard_figures.md §4.3, §4.5). A capture carries the 7 days it was
       taken with; a node older than v0.79 answers 404, and the strips say so. */
    FIXTURE ? Promise.resolve((snapshot && snapshot.issues_days) || null) : api('/issues/days?days=7').catch(() => null),
  ]);

  bind(issues, health, rho);
  window.SETTINGS = flatSettings(settings);
  /* describe()'s own body as well as the flat map: `set` is true for a key whose value is masked,
     which is the only way a screen with no token can say a parent exists without being told where
     it is. flatSettings() drops masked rows by design and cannot answer that. */
  window.SETTINGS_RAW = settings;
  readLayout(settings);
  window.EARTH = earth;
  window.SENSORS = sensors;
  window.CELLS = cells;
  window.REACH = reach;
  window.TRUST = trust;
  window.FORECAST = forecast;
  /* A map from alert id to the sentence somebody left, or null where the node would not say. The
     ledger section reads it opportunistically and is not in its `needs`: the rows exist for every
     reader and it is the words that are gated. */
  window.SHAPE = dayshape;
  window.EFFECT = effect;
  window.DAYS = days;
  window.DAYS_AT = Date.now();
  /* A capture holds one window; Historical draws what it holds. A live node is asked for 90 days on first use. */
  window.DAYS90 = FIXTURE ? days : null;
  window.ACT_NOTES = Array.isArray(notes)
    ? notes.reduce((m, x) => {
      /* ?events=1 adds the answers to events, which carry an event_id (an alert's answer carries an alert_id).
         A node older than v0.77 ignores the query and sends alert rows only. */
      if (x && String(x.note || '').trim()) {
        if (x.alert_id != null) m[`${x.alert_id}:${x.stage}`] = x.note;
        if (x.event_id != null) m[`ev${x.event_id}:${x.stage}`] = x.note;
      }
      return m;
    }, {})
    : null;
  /* /stats, and ONLY on a node that has an appliance to say anything about.
   *
   * The household's own capacity — a purifier's filter life — is `role: device_health` in
   * packs/xiaomi-air/channels.yml and deliberately absent from /issues, which publishes readings of
   * the place and not the state of a machine in it. So it is only on /stats, and /stats is a
   * thirteenth request on a page that makes twelve.
   *
   * Almost no node has a purifier — node #1 has XIAOMI_PURIFIERS empty — so paying that request
   * everywhere to draw a row almost nowhere is the wrong trade. /sensors is already in hand and
   * names its sources, so the page asks for /stats when there is an appliance whose health it
   * would report, and not otherwise. */
  window.STATS = (sensors || []).some(x => x && x.source === 'xiaomi-air')
    ? await api('/stats').catch(() => null) : null;
  window.PLAN = await plan(health).catch(() => null);
  /* What this node holds of its own map (planetai run place basemap): read only for the map ground, which can draw it. */
  window.GROUND_META = ((window.SETTINGS || {}).UI_GROUND === 'map') ? await api('/ground/meta').catch(() => null) : null;
}

/* ------------------------------------------------------------------ Arrange */
/* Ported from the page this replaces. `UI_LAYOUT` is still what app/settings.py says it is —
 * "Managed by the dashboard's Arrange mode" — and Arrange is still a mode over Now rather than a
 * view of its own: leaving Now ends it, which is the behaviour it should always have had.
 *
 * What moved: the old page arranged five fixed band mounts, and this one arranges the sections a
 * pack registered, so an order is a list of section ids and a hide is an id taken out of the view's
 * own list before anything is drawn. */
let LAYOUT = { order: [], hidden: [] };
let ARRANGING = false;

function readLayout(settings) {
  /* A fixture is a file, not a node: there is nowhere a saved arrangement could have come from, and
     reading one is what would stop `?fixture=` being renderable from the fixture alone. */
  if (FIXTURE) return;
  try {
    const r = ((settings || {}).runtime || []).find(x => x.key === 'UI_LAYOUT');
    if (r && r.value) LAYOUT = { order: [], hidden: [], ...JSON.parse(r.value) };
  } catch { /* an unreadable arrangement is no arrangement */ }
}

/* A band hidden in Arrange must actually be gone, not left holding its last content. The page this
 * replaces cleared five fixed mounts by hand and got it wrong on all five — the ✕ silently did
 * nothing — so here the view's own list is filtered before anything is drawn and a hidden section is
 * never emitted at all. */
const want = view => view.filter(id => !(LAYOUT.hidden || []).includes(id));

/* An arrangement is a position within a stage, which is what the registry already sorts by.
 *
 * `s.order` lives on the section object a pack registered, which is shared and long-lived, so this
 * must RESTORE and not merely skip: a version that only overwrote the ids an arrangement names left
 * every other section holding whatever an earlier press had given it, and Default — which empties
 * the order — then changed nothing at all until a hard reload. The order each section registered
 * with is captured once, before anything can have moved it. */
const REGISTERED_ORDER = new Map();
function rememberOrder() {
  for (const s of window.PAI.sections) {
    if (!REGISTERED_ORDER.has(s.id)) REGISTERED_ORDER.set(s.id, s.order);
  }
}
function applyOrder() {
  const o = LAYOUT.order || [];
  for (const s of window.PAI.sections) {
    const i = o.indexOf(s.id);
    s.order = i >= 0 ? i
      : REGISTERED_ORDER.has(s.id) ? REGISTERED_ORDER.get(s.id) : s.order;
  }
}

/* ------------------------------------------------------------------ the projection */
/* GET /issues publishes a cell as an id and its boundary in degrees — geometry.plates' `cells_ll`
 * and, since this task, geometry.claims' too. The kits below were written against a build step that
 * had already projected them, and no browser here has h3 or a projection library. So the projection
 * happens once, here, in the node's own formula (rule 1 again), and nothing downstream knows what a
 * hexagon is. This derives no number the node reports: it re-expresses degrees the node sent. */
const project = (rows, lat0, lon0) => {
  const K = Math.cos(lat0 * Math.PI / 180) * 111320;
  const r1 = v => Math.round(v * 10) / 10;
  return (rows || []).map(r => {
    const o = [r[0]];
    for (let i = 1; i < r.length; i += 2) o.push(r1((r[i + 1] - lon0) * K), r1(-(r[i] - lat0) * 111320));
    return o;
  });
};

/* …and the same metres fitted into one square box, which is the `draw` shape kit-h3's grid() and
 * the wall's field() read: {box, cells: [{id, d}], points}. Uniform scale on both axes, because a
 * hexagon squashed on one of them is a different shape. */
function drawOf(cellsM, stations, box = 600) {
  let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
  for (const c of cellsM) {
    for (let i = 1; i < c.length; i += 2) {
      x0 = Math.min(x0, c[i]); x1 = Math.max(x1, c[i]);
      y0 = Math.min(y0, c[i + 1]); y1 = Math.max(y1, c[i + 1]);
    }
  }
  if (!isFinite(x0)) return { box, cells: [], points: [] };
  const w = x1 - x0, h = y1 - y0, m = Math.max(w, h, 1) * 0.04;
  const s = box / (Math.max(w, h) + 2 * m);
  const cx = (x0 + x1) / 2, cy = (y0 + y1) / 2;
  const X = x => box / 2 + (x - cx) * s, Y = y => box / 2 + (y - cy) * s;
  const r1 = v => Math.round(v * 10) / 10;
  const cells = cellsM.map(c => {
    let d = 'M';
    for (let i = 1; i < c.length; i += 2) d += `${r1(X(c[i]))},${r1(Y(c[i + 1]))}` + (i + 2 < c.length ? 'L' : '');
    return { id: c[0], d: d + 'Z' };
  });
  const points = (stations || []).map(p => ({ ...p, x: r1(X(p.x)), y: r1(Y(p.y)) }))
    .filter(p => p.x >= 0 && p.x <= box && p.y >= 0 && p.y <= box);
  return { box, cells, points };
}

/* What the published geometry does not carry, derived here from what it does, once. */
function initGeometry() {
  const H = window.H3;
  const lat = H.node.lat, lon = H.node.lon;
  const K = Math.cos(lat * Math.PI / 180) * 111320;
  const xy = s => ({ ...s, x: (s.lon - lon) * K, y: -(s.lat - lat) * 111320 });
  const pts = (H.sensors || []).filter(s => s.lat != null && s.lon != null).map(xy);

  for (const res of Object.keys((H.nav || {}).plates || {})) {
    const p = H.nav.plates[res];
    p.cells_m = project(p.cells_ll, lat, lon);
    p.draw = drawOf(p.cells_m, pts);
  }
  for (const c of (H.claims || [])) {
    c.cells_m = project(c.cells_ll, lat, lon);
    c.draw = drawOf(c.cells_m, []);
  }

  /* A station's cell at each resolution. GET /issues publishes it the other way round — every cell
   * of the plate lists the stations in it — so this reads that back. A station further out than the
   * two steps the node published has no cell here at that grain, and the list says so in words
   * rather than filing it under a blank id: the plate ends, the grid does not. */
  for (const s of (H.sensors || [])) s.chain = {};
  for (const id of Object.keys((H.nav || {}).cells || {})) {
    const c = H.nav.cells[id];
    for (const i of (c.sensors || [])) if (H.sensors[i]) H.sensors[i].chain[c.res] = id;
  }
  /* The drawings called a station's origin `label`; the node publishes the same string as `source`. */
  for (const s of (H.sensors || [])) s.label = s.source;
}

/* ================================================================= singapore-wall (this node's own) ==== */
/* singapore-wall · singapore-nea · observe
 *
 * LOCAL TO THE SINGAPORE NODE. Not from the design repository: added on top of it, and a pack
 * contribution in the sense the contract above describes (register, `reads`, `wall`, `notes`).
 *
 * Five columns for the wall and one row for Now: this house's PM2.5 beside NEA's, how far apart they
 * are, the wind (from where, how hard), and the chance of rain. The node computes and the page draws:
 * nothing here is a new number, it is /stats and /observations and /forecast laid side by side. The one
 * subtraction, house minus NEA, is the gap the node's own rules already talk about.
 *
 * The comparison is like for like on purpose. This house's figure is the last HOUR's mean, not the wall's
 * 15-minute mean, because NEA's PM2.5 is an hourly figure for a region: a 15-minute mean beside an hourly
 * one would be the mistake air.yml warns about.
 *
 * It fetches its own three routes once a minute, because /issues carries neither the NEA wind nor the
 * rain forecast, and re-draws when they change. All three are on the `open` list at SHARE_LEVEL=open.
 */
PAI_LOAD.push(function () {
'use strict';

const REFRESH_MS = 60000;
const SG = { at: 0, busy: false, sig: '', obs: [], stats: [], fc: null, pm: [] };
const SE_FROM = 101.25, SE_TO = 168.75;       // ESE to SSE, the arc packs/singapore-nea watches
const COMPASS = ['N', 'NNE', 'NE', 'ENE', 'E', 'ESE', 'SE', 'SSE', 'S', 'SSW', 'SW', 'WSW', 'W', 'WNW', 'NW', 'NNW'];

const get = path => fetch(path, { headers: auth_(), signal: AbortSignal.timeout(15000) })
  .then(r => (r.ok ? r.json() : null)).catch(() => null);

function ensure() {
  if (SG.busy || Date.now() - SG.at < REFRESH_MS) return;
  SG.busy = true;
  Promise.all([get('/observations'), get('/stats'), get('/forecast?hours=6'),
    get('/readings?sensor_id=nea-pm25&metric=pm25&limit=60')]).then(([obs, stats, fc, pm]) => {
    SG.busy = false; SG.at = Date.now();
    const first = SG.sig === '';
    if (obs) SG.obs = obs;
    if (stats) SG.stats = stats;
    if (fc) SG.fc = fc;
    if (Array.isArray(pm)) SG.pm = pm;
    const sig = JSON.stringify([SG.obs, SG.stats, SG.fc, SG.pm]);
    if (first || sig !== SG.sig) { SG.sig = sig; if (window.PAI_ROUTE) window.PAI_ROUTE(); }
  });
}

const ob = (sid, metric) => SG.obs.find(o => o.sensor_id === sid && o.metric === metric);
const obAny = (prefix, metric) => SG.obs.find(o => o.sensor_id.startsWith(prefix) && o.metric === metric);
const num = v => (v == null || v === '' || isNaN(v) ? null : Number(v));
const compass = deg => COMPASS[Math.round((((deg % 360) + 360) % 360) / 22.5) % 16];
const clock = (ts, tz) => {
  const d = new Date(String(ts).replace(' ', 'T'));
  if (isNaN(d)) return '';
  try { return d.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit', timeZone: tz || undefined }); }
  catch { return d.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' }); }
};

/* What each column needs, read from the routes. Every value may be null; the column then says so. */
function read(ctx) {
  const air = (ctx.ISS || {}).air || {};
  const line = num(((air.line || {}).value)) ?? 15;
  const tz = (ctx.S.health || {}).tz;
  const kitRow = SG.stats.find(r => r.metric === 'pm25' && r.local && !r.indoor && r.kind === 'sensor');
  const kit = kitRow ? num(kitRow.mean_1h) : null;
  const nea = ob('nea-pm25', 'pm25');
  const neaV = nea ? num(nea.value) : null;
  const region = nea && nea.meta && nea.meta.region ? nea.meta.region : '';
  const dir = ob('nea-winddir', 'wind_dir'), spd = ob('nea-windspeed', 'wind_speed');
  const now = Date.now();
  const om = ((SG.fc || {}).hours || []).filter(h => h.source === 'forecast-om' && h.fc_rain_prob != null
    && new Date(String(h.ts).replace(' ', 'T')).getTime() > now - 3600e3
    && new Date(String(h.ts).replace(' ', 'T')).getTime() <= now + 3 * 3600e3);
  const prob = om.length ? Math.max(...om.map(h => Number(h.fc_rain_prob))) : null;
  const areas = obAny('nea-fc2h-', 'fc_rain_areas_pct'), wet = ob('nea-rain-island', 'rain_wet_pct');
  return { line, tz, kit, kitName: kitRow && kitRow.name, nea: neaV, neaTs: nea && nea.ts, region,
    dir: dir ? num(dir.value) : null, spd: spd ? num(spd.value) : null, windTs: (dir || spd || {}).ts,
    prob, areas: areas ? num(areas.value) : null, wet: wet ? num(wet.value) : null };
}

function cols(ctx) {
  const { esc } = window.K;
  const d = read(ctx);
  const n0 = v => (v == null ? '—' : Number(v).toFixed(0));
  const col = (id, title, big, small) => `<div class="col" id="sgw-${id}" data-component="sgwall" data-ref="wall-field">`
    + `<h3 data-role="wall-issue">${esc(title)}</h3><div class="line">${big}${small}</div></div>`;
  const val = (key, v, cmp, cls) => (v == null
    ? '<span class="none">—</span>'
    : `<span class="num${cls ? ' ' + cls : ''}" data-num="${esc(key)}" data-cmp="${esc(cmp)}">${esc(n0(v))}</span>`);
  const sm = t => `<small class="said">${esc(t)}</small>`;
  const out = [];

  out.push(col('house', 'PM2.5 · this house',
    val('sgwall.house.pm25', d.kit, `against NEA's ${n0(d.nea)} for the region, and the ${d.line} line`, d.kit != null && d.kit > d.line ? 'crossed' : ''),
    sm(d.kit == null ? 'nothing read from the kit in the last hour' : '\u00b5g/m\u00b3 · Smart Citizen, 1 h mean')));

  out.push(col('nea', `PM2.5 · NEA${d.region ? ' ' + d.region : ''}`,
    val('sgwall.nea.pm25', d.nea, `against ${n0(d.kit)} at this house, and the ${d.line} line`, d.nea != null && d.nea > d.line ? 'crossed' : ''),
    sm(d.nea == null ? 'no NEA reading yet' : `\u00b5g/m\u00b3 · hourly, region average${d.neaTs ? ' · ' + clock(d.neaTs, d.tz) : ''}`)));

  if (d.kit != null && d.nea != null) {
    const gap = d.kit - d.nea, pct = d.nea > 0 ? (gap / d.nea) * 100 : null;
    const sign = gap > 0 ? '+' : gap < 0 ? '−' : '±';
    const bigTxt = `<span class="num" data-num="sgwall.gap.pm25" data-cmp="this house's hour minus NEA's region, `
      + `against ${n0(d.kit)} and ${n0(d.nea)}">${esc(sign + Math.abs(gap).toFixed(0))}</span>`;
    out.push(col('gap', 'House against NEA', bigTxt,
      sm(`\u00b5g/m\u00b3${pct == null ? '' : ` · ${pct > 0 ? '+' : pct < 0 ? '−' : ''}${Math.abs(pct).toFixed(0)}%`} · the house reads `
        + `${gap > 0 ? 'higher' : gap < 0 ? 'lower' : 'the same'}`)));
  } else {
    out.push(col('gap', 'House against NEA', '<span class="none">—</span>', sm('needs both readings')));
  }

  const inArc = d.dir != null && d.dir >= SE_FROM && d.dir < SE_TO;
  out.push(col('wind', 'Wind',
    val('sgwall.wind.speed', d.spd, d.dir != null ? `from ${compass(d.dir)}, ${d.dir.toFixed(0)} degrees` : 'direction not read', inArc ? 'crossed' : ''),
    sm(d.dir == null && d.spd == null ? 'no NEA wind reading yet'
      : `${d.spd != null ? 'kn' : ''} · from ${d.dir == null ? '—' : compass(d.dir) + ' ' + d.dir.toFixed(0) + '°'}`
        + (inArc ? ' · south-east: the pattern to watch' : ''))));

  const haveProb = d.prob != null;
  const rainBig = haveProb ? val('sgwall.rain.chance', d.prob, 'the highest hourly chance in the next 3 h, Open-Meteo, at this point')
    : val('sgwall.rain.areas', d.areas, 'share of NEA forecast areas expecting rain in 2 h');
  const rainSmall = [haveProb ? '% chance, next 3 h (Open-Meteo)' : (d.areas != null ? '% of NEA areas expect rain, 2 h' : 'no rain forecast yet')];
  if (haveProb && d.areas != null) rainSmall.push(`NEA: ${n0(d.areas)}% of areas expect rain`);
  if (d.wet != null) rainSmall.push(`${n0(d.wet)}% of stations wet now`);
  out.push(col('rain', 'Rain', rainBig, rainSmall.map(sm).join('')));
  return out.join('');
}

window.PAI.register({
  id: 'sgair', pack: 'singapore-nea', stage: 'observe', title: 'Singapore air, wind and rain', order: -10,
  reads: ['/observations', '/stats', '/forecast'],
  render(ctx) {
    ensure();
    return `<div class="sgwall" data-component="sgwall" data-ref="sgair">${cols(ctx)}</div>`;
  },
  wall(ctx) { ensure(); return cols(ctx); },
  notes() {
    return [
      { id: 'sgair-compare', label: 'This house against NEA',
        text: 'This house’s figure is the mean of the last hour from the Smart Citizen kit, and NEA’s is its hourly PM2.5 '
          + 'averaged over the region the node sits in. They are put side by side on the same hour so the difference means '
          + 'something; a 15-minute mean beside an hourly one would not. The gap is this house minus NEA: positive means the '
          + 'street here reads higher than the region, which is usually the local source and not the haze.' },
      { id: 'sgair-wind', label: 'Wind',
        text: 'Speed in knots and the bearing the wind blows FROM, a 10-minute mean at the nearest NEA station. It is marked '
          + 'when it comes from east-south-east to south-south-east, the arc the node’s wind rules watch: south-east wind '
          + 'that settles in and strengthens tends to come before worse air here.' },
      { id: 'sgair-rain', label: 'Rain',
        text: 'The big figure is Open-Meteo’s highest hourly chance of rain in the next three hours at this point, a model '
          + 'probability. NEA does not publish a probability: its two-hour forecast says rain or no rain for each of 49 areas, '
          + 'so the share of areas expecting rain is shown beside it as a measure of how widespread rain is expected to be, '
          + 'and the share of gauges that are wet right now is what is actually falling.' },
    ];
  },
});

/* ---- the second row: beach water, fires, and the haze 24 hours on ----
 * Beach: NEA's weekly banding for the two followed beaches (singapore-beach pack), worst band large, each beach
 * named beneath. It is a week old by construction (a lab result), and the caption says which week.
 * Fires: NASA FIRMS hotspots within the pack's radius over the last 24 h, against the 24 h before that
 * (`fires_prev_24h`), so the change is like for like and needs no stored history.
 * Haze: FIRMS counts fires, not smoke, and NEA publishes no smoke count. What the node can say about smoke is what
 * reached the air, so this is NEA's regional PM2.5 now against the same hour yesterday, from /readings. */
const BEACHES = [['nea-beach-east-coast', 'East Coast'], ['nea-beach-changi', 'Changi']];
const H24 = 24 * 3600e3;
const tsMs = t => new Date(String(t).replace(' ', 'T')).getTime();

function readCoast(ctx) {
  const tz = (ctx.S.health || {}).tz;
  const beaches = BEACHES.map(([sid, name]) => {
    const b = ob(sid, 'beach_band'), a = ob(sid, 'beach_advisory'), e = ob(sid, 'beach_stretches_elevated');
    return { name, band: b ? num(b.value) : null, adv: a ? num(a.value) : null, elev: e ? num(e.value) : null, ts: b && b.ts };
  });
  const bands = beaches.map(b => b.band).filter(v => v != null);
  const fires = ob('firms-hotspots', 'fires_24h'), prev = ob('firms-hotspots', 'fires_prev_24h');
  const near = ob('firms-hotspots', 'fires_nearest_km'), radius = fires && fires.meta ? fires.meta.radius_km : null;
  const pm = (SG.pm || []).map(r => ({ t: tsMs(r.ts), v: num(r.value) })).filter(r => r.v != null && !isNaN(r.t));
  let haze = null;
  if (pm.length) {
    const nowRow = pm.reduce((a, b) => (b.t > a.t ? b : a));
    const target = nowRow.t - H24;
    const ago = pm.filter(r => Math.abs(r.t - target) <= 2 * 3600e3)
      .reduce((a, b) => (!a || Math.abs(b.t - target) < Math.abs(a.t - target) ? b : a), null);
    const day = pm.filter(r => r.t > nowRow.t - H24);
    haze = { now: nowRow.v, nowT: nowRow.t, ago: ago ? ago.v : null, peak: day.length ? Math.max(...day.map(r => r.v)) : null };
  }
  return { tz, beaches, worst: bands.length ? Math.max(...bands) : null, anyAdv: beaches.some(b => b.adv > 0),
    week: (beaches.find(b => b.ts) || {}).ts,
    fires: fires ? num(fires.value) : null, prev: prev ? num(prev.value) : null, firesTs: fires && fires.ts,
    near: near ? num(near.value) : null, radius: radius ? Math.round(radius) : null, haze };
}

function coastCols(ctx) {
  const { esc } = window.K;
  const d = readCoast(ctx);
  const sm = t => `<small class="said">${esc(t)}</small>`;
  const col = (id, title, big, small) => `<div class="col" id="sgw-${id}" data-component="sgwall" data-ref="wall-field">`
    + `<h3 data-role="wall-issue">${esc(title)}</h3><div class="line">${big}${small}</div></div>`;
  const numEl = (key, txt, cmp, cls) => `<span class="num${cls ? ' ' + cls : ''}" data-num="${esc(key)}" data-cmp="${esc(cmp)}">${esc(txt)}</span>`;
  const none = '<span class="none">—</span>';
  const sign = v => (v > 0 ? '+' : v < 0 ? '−' : '±') + Math.abs(v).toFixed(0);
  const out = [];

  const wk = d.week ? new Date(String(d.week).replace(' ', 'T')) : null;
  const wkTxt = wk && !isNaN(wk) ? wk.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', timeZone: d.tz || undefined }) : '';
  out.push(col('beach', 'Beach water · NEA',
    d.worst == null ? none : numEl('sgwall.beach.band', `${d.worst} of 3`, 'the worst band across the followed beaches, 1 is best', d.worst >= 2 || d.anyAdv ? 'crossed' : ''),
    sm(d.worst == null ? 'no NEA banding yet'
      : d.beaches.map(b => `${b.name} ${b.band == null ? '—' : b.band}`).join(' · ') + (d.anyAdv ? ' · advisory' : ''))
    + (d.worst == null ? '' : sm(`lower is better · week ending ${wkTxt || '—'}`))));

  if (d.fires == null) {
    out.push(col('fires', 'Fires · last 24 h', none, sm('no FIRMS count yet')));
  } else {
    const delta = d.prev == null ? null : d.fires - d.prev;
    const pct = d.prev ? (delta / d.prev) * 100 : null;
    out.push(col('fires', 'Fires · last 24 h',
      numEl('sgwall.fires.count', String(d.fires), `hotspots within ${d.radius || '—'} km in the last 24 h${d.prev != null ? `, against ${d.prev} in the 24 h before` : ''}`),
      sm(d.prev == null ? 'hotspots · no earlier day to compare yet'
        : `${sign(delta)}${pct == null ? '' : ' · ' + (pct > 0 ? '+' : pct < 0 ? '−' : '') + Math.abs(pct).toFixed(0) + '%'} on the 24 h before (${d.prev})`)
      + sm(`hotspots within ${d.radius || '—'} km${d.near != null ? ' · nearest ' + d.near.toFixed(0) + ' km' : ''}`)));
  }

  const h = d.haze;
  if (!h) {
    out.push(col('haze', 'Haze · PM2.5 on 24 h ago', none, sm('no NEA readings yet')));
  } else {
    const delta = h.ago == null ? null : h.now - h.ago;
    out.push(col('haze', 'Haze · PM2.5 on 24 h ago',
      delta == null ? none : numEl('sgwall.haze.delta', sign(delta), `NEA regional PM2.5 now, ${h.now.toFixed(0)}, against ${h.ago.toFixed(0)} at the same hour yesterday`, delta > 0 ? 'crossed' : ''),
      sm(delta == null ? 'no reading near this hour yesterday' : `\u00b5g/m\u00b3 · now ${h.now.toFixed(0)}, yesterday ${h.ago.toFixed(0)}`)
      + sm(`NEA regional${h.peak != null ? ' · peak ' + h.peak.toFixed(0) + ' in the 24 h' : ''}`)));
  }
  return out.join('');
}

window.PAI.register({
  id: 'sgcoast', pack: 'singapore-beach', stage: 'observe', title: 'Singapore beaches, fires and haze', order: -9,
  reads: ['/observations', '/readings'],
  render(ctx) {
    ensure();
    return `<div class="sgwall" data-component="sgwall" data-ref="sgcoast">${coastCols(ctx)}</div>`;
  },
  wall(ctx) { ensure(); return coastCols(ctx); },
  notes() {
    return [
      { id: 'sgcoast-beach', label: 'Beach water',
        text: 'NEA grades each beach stretch weekly by enterococci bacteria in the water, from band 1 (lowest) to band 3. The wall '
          + 'shows the worst band of the two beaches this node follows, East Coast and Changi. Lab results take about a week, so '
          + 'this describes the week ending on the date shown, not today; NEA’s own advisory, for example after heavy rain, is marked.' },
      { id: 'sgcoast-fires', label: 'Fires',
        text: 'NASA FIRMS satellite hotspots (VIIRS, low-confidence detections dropped) within the radius the fire-smoke pack is set to. '
          + 'The change compares the last 24 hours with the 24 hours before them. A hotspot is a fire seen by a satellite, not smoke: '
          + 'satellites pass several times a day, so a count can rise or fall with the passes as well as with the fires.' },
      { id: 'sgcoast-haze', label: 'Haze',
        text: 'Nothing measures smoke directly here. What the node can show is what reached the air: NEA’s regional PM2.5 now against the '
          + 'same hour yesterday. Regional PM2.5 rising while fires are up and the wind is from the south or south-east is the pattern '
          + 'the node’s wind rules watch for; a rise alone can have other causes.' },
    ];
  },
});
});

/* ------------------------------------------------------------------ init */
function init() {
  initKit();
  initGeometry();
  for (const f of PAI_LOAD) f();
  rememberOrder();
}

/* ------------------------------------------------------------------ writing a setting */
/* The one write this page makes, and the same request the page it replaces made for UI_LAYOUT: PUT
 * /settings behind the admin token, with X-Agent so the audit trail knows who acted. Task 7's tiles
 * switch is this call with { MAP_TILES: 'on' | 'off' }. */
async function setSetting(key, value) {
  const tok = localStorage.getItem('planetai_admin');
  if (!tok) throw new Error('that setting needs the admin token; unlock it under Set up');
  const r = await fetch('/settings', {
    method: 'PUT',
    headers: { 'content-type': 'application/json', authorization: 'Bearer ' + tok, 'X-Agent': 'dashboard' },
    body: JSON.stringify({ [key]: value }),
  });
  if (!r.ok) throw new Error(`the node refused that setting (${r.status})`);
  window.SETTINGS = { ...(window.SETTINGS || {}), [key]: value };
  if (window.PAI_SETUP) window.PAI_SETUP.toast('Saved. Live within about twenty seconds.');
  return true;
}
window.PAI_SETTINGS = { set: setSetting };
/* The Set up pane, ported from the page this replaces, reads these two rather than keeping its own
 * copy of either: one fetcher's headers, one re-render. */
window.PAI_AUTH = auth_;
window.PAI_ROUTE = () => route();

/* ------------------------------------------------------------------ the shell */
/* The header, shared by the page and by the refused page, because a household with no token still
 * has to be able to reach the other views. The node's name is an <h1>: the page had none at all
 * before that was found by looking, and page-has-heading-one fired on every view in every state. */
/* THE REGISTER: paper by day, dark on the wall and by a keeper's switch. Design log R13.
 *
 * Dark is not guessed from the operating system and it is not a time of day. It is the wall — where
 * a lit rectangle in a dark room is a lamp and nobody chose anything — or it is a switch somebody
 * pressed. Both set the same attribute the wall has always set, so every rule under
 * `:root[data-theme="dark"]` already covers the switch and no component carries a second palette.
 *
 * It lives here because `route()` cleared `data-theme` on every render and `main()` put it back for
 * the wall, so a keeper's choice survived exactly until the next view change. One function decides
 * the register now; the four places that used to set or clear the attribute ask it instead. */
const REGISTER_KEY = 'planetai_register';
function register() {
  /* `?register=dark` is read first and remembers nothing, for the same two reasons `?mode=` is:
     the measuring rig needs every combination without touching storage between renders, and one
     person can send another the page as they are looking at it. */
  const q = new URLSearchParams(location.search).get('register');
  if (q === 'dark' || q === 'paper') return q;
  /* A browser with site data blocked still has to render. It just cannot remember. */
  try { return localStorage.getItem(REGISTER_KEY) === 'dark' ? 'dark' : 'paper'; }
  catch (e) { return 'paper'; }
}
function applyRegister(view) {
  const root = document.documentElement;
  if (view === 'wall' || register() === 'dark') root.setAttribute('data-theme', 'dark');
  else root.removeAttribute('data-theme');
}

/* THE MODE: how much of the page is drawn. `simple` is the digest and nothing else, `advanced` is
 * every section, `learn` is advanced with a question mark at each part. The marks arrive with the
 * learn layer; until they do, `learn` draws exactly what `advanced` draws. The control still offers
 * all three, because the setting a keeper picks has to be a setting the page honours.
 *
 * Two sources, in this order: what this browser last chose, then what the node is set to. `UI_MODE`
 * is what the page OPENS as, chosen by the household; a reader who switches is switching their own
 * copy and nobody else's. Same bargain the register makes, for the same reason. */
const MODE_KEY = 'planetai_mode';
const MODES = [['simple', 'Simple'], ['advanced', 'Advanced'], ['learn', 'Learn']];
/* WHICH VIEWS HAVE A SHORT ANSWER TO GIVE.
 *
 * Simple is "the short version of what this view reports", and three views do not report: Set up is
 * a form, Arrange is a mode for moving sections about, and the Wall is already the short version —
 * it is one screen at three metres and it has no header to put a control in. Offering Simple on them
 * was a control that did nothing on Set up and took the sections away from Arrange, leaving its bar
 * with nothing to arrange.
 *
 * Learn stays on all of them: a question mark is worth having wherever there is something to explain,
 * and the marks are drawn per section rather than per view. */
const SHORT_VIEW = new Set(['now', 'historical', 'network']);
const isMode = m => MODES.some(([k]) => k === m);
function mode(view) {
  /* A view with no short answer draws the full one, whatever this browser last chose. Otherwise a
     reader who picked Simple on Now arrived at Arrange to find no sections and a bar offering to
     reorder them. The stored choice is not changed — going back to Now restores it. */
  if (view && !SHORT_VIEW.has(view) && modeRaw() === 'simple') return 'advanced';
  return modeRaw();
}

function modeRaw() {
  /* `?mode=simple` is read first and remembers nothing: it is how the measuring rig renders all
     three modes, and how one person sends another the short answer without changing their page. */
  const q = new URLSearchParams(location.search).get('mode');
  if (isMode(q)) return q;
  let mine = null;
  try { mine = localStorage.getItem(MODE_KEY); } catch (e) { /* see register() */ }
  if (isMode(mine)) return mine;
  const row = ((window.SETTINGS || {}).runtime || []).find(x => x.key === 'UI_MODE');
  const set = row && String(row.value == null ? '' : row.value).trim();
  return isMode(set) ? set : 'advanced';
}
/* The renderer asks without a view and gets the stored choice; chrome() and main() ask about the
   view they are drawing. VIEW is set by readView() before either runs. */
window.PAI_MODE = () => mode(VIEW);

/* ONE ANIMATION LOOP FOR THE WHOLE PAGE.
 *
 * Every surface that wants a frame asks here instead of calling requestAnimationFrame itself. Two
 * loops on one page cost twice the wake-ups and cannot be reasoned about together; one loop can be
 * stopped, and this one stops itself whenever there is nothing to draw:
 *
 *   · the tab is hidden          — `visibilitychange`, so a wall screen behind a screensaver is idle
 *   · the element is off-screen  — IntersectionObserver, so a canvas scrolled past costs nothing
 *   · nobody is subscribed       — the loop is not scheduled at all, rather than spinning on zero
 *
 * Under reduced motion it never schedules anything: the tick is called ONCE and the surface draws a
 * still. That is not a fallback, it is what the surface is meant to look like when somebody has
 * asked for nothing to move — every drawing this page makes has to read frozen.
 *
 * A subscriber that throws is dropped rather than throwing once a frame for the rest of the session.
 */
window.PAI_RAF = (function () {
  const subs = new Map();                 // element -> { tick, on }
  let raf = 0;
  const reduced = () => !!(window.matchMedia
    && window.matchMedia('(prefers-reduced-motion: reduce)').matches);
  /* No observer on this browser: assume every subscriber is on screen. Drawing a frame nobody can
     see is a waste; not drawing one somebody can see is a bug. */
  const io = typeof IntersectionObserver === 'function'
    ? new IntersectionObserver(es => {
      for (const e of es) { const s = subs.get(e.target); if (s) s.on = e.isIntersecting; }
      kick();
    }, { threshold: 0 })
    : null;

  const awake = () => !document.hidden && [...subs.values()].some(s => s.on);

  function frame(now) {
    raf = 0;
    for (const [el, s] of [...subs]) {
      if (!s.on) continue;
      try { s.tick(now, el); }
      catch (e) { subs.delete(el); if (io) io.unobserve(el); }
    }
    kick();
  }
  function kick() { if (!raf && awake()) raf = requestAnimationFrame(frame); }
  document.addEventListener('visibilitychange', kick);

  return {
    /* `tick(now, el)` runs once per frame while `el` is on screen and the tab is visible. */
    add(el, tick) {
      if (reduced()) { try { tick(performance.now(), el); } catch (e) { /* one still, or none */ } return; }
      subs.set(el, { tick, on: !io });
      if (io) io.observe(el);
      kick();
    },
    remove(el) {
      subs.delete(el);
      if (io) io.unobserve(el);
      if (!subs.size && raf) { cancelAnimationFrame(raf); raf = 0; }
    },
    reduced,
    /* For the tests: how many surfaces are asking for frames right now. */
    get size() { return subs.size; },
  };
}());

/* ASKING THE NODE — the loading state, and the only motion on this page with no reading behind it.
 *
 * What it says is what is happening: the page is reading a list of endpoints off one machine, and
 * each one either answers or does not. So it draws that list, and closes a ring per answer with the
 * milliseconds it took. The globe of glyphs is the sixteen characters an H3 index is written in,
 * turning inside this node's own cell — the one thing the page knows about where it is before the
 * node has said anything — and it settles into the plane of that cell when /issues lands.
 *
 * WHEN IT PLAYS, and this is a rule and not a preference: first paint, the header's ↻ ask the node
 * again, and reconnect after the pill has dropped `live`. NEVER ON A POLL. A poll re-reads /issues,
 * /health and /rho every POLL_SECONDS and redraws; covering a page somebody is reading with a
 * loading state every five minutes would make the node look broken while it is working perfectly.
 * The only motion a poll may cause is reading-fade on the numerals that changed.
 *
 * It is one canvas, one subscription to PAI_RAF, ≤ 600 glyphs, DPR capped at 2, sized to its own box
 * and never to the viewport. Under reduced motion PAI_RAF draws one still frame and never schedules
 * another; the reads still land as they answer, because their latencies are real and there is
 * nothing to compress.
 *
 * The latencies are the real ones: api() reports every read here, so this is the page's own account
 * of what it asked and how long each answer took — the same honesty the request ledger owes.
 */
const ASKING = (function () {
  const GL = '0123456789abcdef';
  const N = 560;                       // ≤ 600, the budget prompt 6 set
  const SPIN = 0.35;                   // rad/s
  /* THE SETTLE IS A FLOOR, NOT A DURATION — for the same reason the hold is. The glyphs turn while
     the node has not answered and settle into its cell when /issues lands, and the turning decays
     with the settle (`k = 1 - s` below), so a fixed 900 ms meant a fast node flattened by ~930 ms
     and then held a STILL FRAME for the other two seconds of the three-second floor. The rAF loop
     was running the whole time, drawing the same picture. Reported by Tomas, 22 September.
     `settleFor` is whatever is left of the floor when /issues lands, so the settle ends exactly as
     close() takes the overlay away; a node slower than the floor gets this minimum instead, because
     there the page arriving is the thing wanted and nothing should be stretched to meet it. */
  const SETTLE_MS = 900;
  let settleFor = SETTLE_MS;
  /* A fixed sphere, computed once: the globe is the same globe every time it is asked for, and
     scattering 560 points per open would be work for no difference anybody can see. */
  const pts = [];
  for (let i = 0; i < N; i++) {
    const u = Math.random() * 2 - 1, th = Math.random() * Math.PI * 2, r = Math.sqrt(1 - u * u);
    pts.push({ x: r * Math.cos(th), y: u, z: r * Math.sin(th), g: GL[i % 16] });
  }
  const hex = [];
  for (let k = 0; k < 6; k++) { const a = Math.PI / 180 * (60 * k - 30 + 8); hex.push([Math.cos(a), Math.sin(a)]); }

  let box, cv, on = false, t0 = 0, settle0 = 0, spec = null;
  /* A floor, not a duration. What this state says — the endpoints asked for and the milliseconds
     each took — is the page's own account of what it asked of the world, and on a fixture the node
     answers in under a tenth of a second, so nobody had ever read it. --motion-asking-hold is the
     shortest time it is held; the state still ends when the node answers if the node is slower, and
     the frozen layer zeroes the token under reduced motion, so a reader who asked for stillness
     gets the page as soon as it is ready. `held` is what open() asked for: a reload and the ↻ want
     the floor, a reconnect does not — there the page coming back IS the thing wanted. */
  let held = false;
  /* What a frame of this actually costs, measured rather than asserted. Prompt 6 set a budget of
     4 ms of main-thread work per frame on a 2015 MacBook Pro, and a budget nobody can read is a
     budget nobody keeps. PAI_ASKING.cost() answers in milliseconds. */
  const cost = { frames: 0, total: 0, worst: 0 };
  const reads = [];                    // { path, ms, ok } in the order they answered
  let asking = '';                     // the read in flight, for the tethered label

  const el = id => document.getElementById(id);
  const css = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();

  function size() {
    const r = cv.getBoundingClientRect();
    const dpr = Math.min(2, window.devicePixelRatio || 1);
    cv.width = Math.max(1, Math.round(r.width * dpr));
    cv.height = Math.max(1, Math.round(r.height * dpr));
    cv._dpr = dpr;
  }

  /* The cell and the glyphs, on any canvas: the loading state's own frame, and the ask pane's
     answer while the node is working on it. `every` thins the glyphs for a small canvas, where 560
     of them at 9 px would be one grey blot. */
  function globe(ctx, W, H, dpr, ang, k, s, every, px) {
    const cx = W / 2, cy = H / 2, R = Math.min(W, H) * 0.36;
    const ink = css('--ink') || '#171717', cells = css('--cells') || '#20388D';
    /* The cell this node stands in, in the one colour that means an H3 cell and nothing else. */
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

  /* The pane's globe: a PAI_RAF tick for a small canvas of its own. It only turns, because in the
     pane there is no /issues to settle into, only an answer that has not come yet. */
  const born = performance.now();
  function paneGlobe(now, el) {
    const r = el.getBoundingClientRect();
    const dpr = Math.min(2, window.devicePixelRatio || 1);
    const w = Math.max(1, Math.round(r.width * dpr)), h = Math.max(1, Math.round(r.height * dpr));
    if (el.width !== w || el.height !== h) { el.width = w; el.height = h; }
    const ctx = el.getContext('2d');
    ctx.clearRect(0, 0, w, h);
    globe(ctx, w, h, dpr, (now - born) / 1000 * SPIN * 2, 1, 0, 3, 7);
  }

  function draw(now) {
    const c0 = performance.now();
    const W = cv.width, H = cv.height, dpr = cv._dpr || 1;
    if (!W || !H) return;
    const ctx = cv.getContext('2d');
    const mute = css('--mute') || css('--muted') || '#6B6864', ink = css('--ink') || '#171717';
    ctx.clearRect(0, 0, W, H);
    const s = settle0 ? Math.min(1, (now - settle0) / settleFor) : 0;
    const k = 1 - s;                            // 1 = a globe, 0 = flat in the cell's plane
    const ang = (now - t0) / 1000 * SPIN * k;   // and it stops turning as it flattens
    /* The globe keeps out of the bottom strip, where the spec block is written: on a phone the frame
       is short enough that the two were drawn over each other. */
    const { cx, cy, R } = globe(ctx, W, H - 44 * dpr, dpr, ang, k, s, 1, 9);

    /* Two labels tethered from the frame's corners, naming the endpoint being read and the last one
       that answered. Not decoration: they are the only place on this surface that says what the
       delay is for. */
    const last = reads.length ? reads[reads.length - 1].path : '';
    const tether = [[asking, -0.55, -0.42, 0], [last, 0.52, 0.38, 1]];
    for (const [name, lx, ly, right] of tether) {
      /* The bottom-right label shares its corner with the spec block, and on a narrow frame there is
         not room for both. The list of reads under the frame says the same thing. */
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

    /* The spec block: what this node has published about where it is, which before /health answers
       is only the glyph count. It fills in rather than guessing. */
    ctx.fillStyle = mute; ctx.textAlign = 'left';
    ctx.font = `${(8.5 * dpr).toFixed(0)}px ${css('--mono') || 'ui-monospace, monospace'}`;
    const lines = [`GLYPHS 0-9 A-F · ${N} · ONE GLOBE, ONE CELL`].concat(spec || []);
    lines.forEach((line, i) => ctx.fillText(line, 24 * dpr, H - (16 + 12 * (lines.length - 1 - i)) * dpr));

    const ms = performance.now() - c0;
    cost.frames += 1; cost.total += ms; if (ms > cost.worst) cost.worst = ms;
  }

  /* The lead's own bars, capped as they fill.
     NOT the sketch's `[▮▮▮▯▯]`: meterBar's own comment records that U+25AE and U+25AF are absent
     from the shipped font subset and fall back at a different advance — a broken bar on any screen
     with a different fallback. That was measured once; writing it back in text here would have
     thrown the measurement away. Drawn twice is drawn once, in one function. */
  const CELLS = 16;
  function meters(rows, filled) {
    return rows.map(([name, value, scale, line]) =>
      `<span class="r"><span class="k">${window.K.esc(name)}</span>`
      + `${window.K.meterBar(value, scale, line, null, null, filled)}</span>`).join('');
  }

  function rows() {
    return reads.map(r =>
      `<div class="r"><span class="p">${window.K.esc(r.path)}</span>`
      + `<span class="ms">${r.ok ? `${Math.round(r.ms)} ms` : 'no answer'}</span></div>`).join('')
      + (asking ? `<div class="r wait"><span class="p">${window.K.esc(asking)}</span>`
        + `<span class="ms">asking…</span></div>` : '');
  }

  function paint() {
    if (!on) return;
    const e = el('ask-ep'); if (e) e.innerHTML = rows();
    const c = el('ask-count');
    if (c) c.textContent = `${reads.filter(r => r.ok).length} answered`;
  }

  return {
    /* `why` is what the header says while it is up, in the page's own words. */
    open(why, hold) {
      box = el('asking');
      if (!box || on) return;
      /* close() takes the canvas out of the tree, so opening puts one back. The id is in
         index.html — that is what tools/check_ui.py checks — and this is the same element by every
         name that matters; what it is not is a 1440x900x2 backing store kept alive for the rest of
         the session behind display:none. */
      cv = el('askcv');
      if (!cv) {
        cv = document.createElement('canvas');
        cv.id = 'askcv';
        (box.querySelector('.frame') || box).appendChild(cv);
      }
      on = true; reads.length = 0; asking = ''; settle0 = 0; spec = null;
      settleFor = SETTLE_MS;
      held = !!hold;
      /* Per episode, not per session: the cost of the frames drawn while the page was loading is
         not the cost of the frames drawn when somebody pressed ↻ twenty minutes later. */
      cost.frames = 0; cost.total = 0; cost.worst = 0;
      t0 = performance.now();
      box.classList.add('on'); box.setAttribute('aria-hidden', 'false');
      const w = el('ask-what'); if (w) w.textContent = why || 'Asking the node';
      const b = el('ask-big'); if (b) { b.textContent = '----'; b.className = 'big'; }
      const m = el('ask-meters'); if (m) m.innerHTML = '';
      const r = el('ask-rule');
      if (r) {
        r.textContent = 'The glyphs are the sixteen characters an H3 index is written in. They turn '
          + 'while the node has not answered and settle into this node’s own cell the moment '
          + '/issues lands. Nothing here is a reading.';
      }
      size();
      window.addEventListener('resize', size);
      window.PAI_RAF.add(cv, draw);
      paint();
    },
    /* Every read the page makes reports here, answered or not. api() is the only caller. */
    saw(path, ms, ok) {
      if (!on) return;
      reads.push({ path, ms, ok });
      if (asking === path) asking = '';
      paint();
    },
    /* The read in flight, for the tethered label. */
    flight(path) { if (on) { asking = path; paint(); } },
    /* /health answered: the spec block can stop being a glyph count. */
    placed(health) {
      if (!on || !health) return;
      const c = health.cell || {};
      const area = c.edge_m ? Math.round(2.59807621 * c.edge_m * c.edge_m).toLocaleString('en-GB') : null;
      spec = [
        `RES ${c.res == null ? '?' : c.res} · EDGE ${c.edge_m == null ? '?' : `${c.edge_m} M`}`
          + `${area ? ` · ${area} M²` : ''}`,
        `SHARE LEVEL ${String((health.share_level || 'off')).toUpperCase()} · RAW STAYS HOME`,
      ];
    },
    /* /issues landed. The numeral stops being four dashes and the meters fill a cell at a time. */
    landed(issues) {
      if (!on || !issues) return;
      settle0 = performance.now();
      /* Stretch the settle over what is left of the floor, so the glyphs are still moving when the
         overlay goes. `held` is still true here: close() is called after boot() resolves and this
         runs inside it. Under reduced motion the token is 0, so this is the minimum and the loop
         draws one frame anyway. */
      const floor = held ? window.K.msToken('--motion-asking-hold') : 0;
      settleFor = Math.max(SETTLE_MS, floor - (settle0 - t0));
      const hk = issues.headline, d = (issues.issues || {})[hk] || {};
      /* The reading the lead will carry, off the field the lead reads: stack.room. `readouts` is an
         empty list on this node's own wire and was never the numeral's source. */
      const room = ((d.stack || {}).room || {}).value;
      const b = el('ask-big');
      if (b && room != null) {
        b.innerHTML = `${window.K.esc(window.K.fmt(room, d.dp))}`
          + `<small>${window.K.esc(d.unit || '')}</small>`;
        b.className = 'big land pulse';
      }
      const m = el('ask-meters');
      if (!m) return;
      const st = d.stack || {};
      /* The distances and their words come off THIS payload, not off window.K: bind() has not run
         yet when the overlay is still up, which is the whole point of the overlay. */
      const loc = issues.locale || 'en';
      const labs = (issues.labels || {})[loc] || (issues.labels || {}).en || {};
      /* The lead's own scale, so the bars here and the bars on the page behind are one drawing of
         the same four numbers. */
      const vals = Object.values(st).map(x => x && x.value).filter(v => v != null);
      const scale = (vals.length ? Math.max(...vals) : 1) * 1.12;
      const line = d.line ? d.line.value : null;
      const rs = (issues.distances || ['room', 'yard', 'ring', 'region'])
        .map(k => [String(labs[k] || k), (st[k] || {}).value, scale, line]);
      /* One cell per --motion-meter-fill. Zero under reduced motion, which the frozen layer's one
         reduce block sets — so the meters arrive full, in one step. */
      const step = window.K.msToken('--motion-meter-fill');
      if (!step) { m.innerHTML = meters(rs, CELLS); return; }
      let i = 0;
      m.innerHTML = meters(rs, 0);
      const iv = setInterval(() => {
        i += 1;
        m.innerHTML = meters(rs, i);
        if (i >= CELLS || !on) clearInterval(iv);
      }, step);
    },
    close() {
      if (!on) return;
      /* Held open for the rest of the floor, and only for it: the page underneath is already drawn,
         so this delays nothing but the overlay leaving. A second close() while waiting is ignored —
         `on` is still true — which is what stops two timers racing to take the same canvas away. */
      const floor = held ? window.K.msToken('--motion-asking-hold') : 0;
      const left = floor - (performance.now() - t0);
      if (left > 0) { held = false; setTimeout(() => this.close(), left); return; }
      on = false;
      window.PAI_RAF.remove(cv);
      window.removeEventListener('resize', size);
      if (box) { box.classList.remove('on'); box.setAttribute('aria-hidden', 'true'); }
      if (cv && cv.parentNode) cv.parentNode.removeChild(cv);
      cv = null;
      /* The page underneath is drawn by now, so the reading it carries gets the two motions the
         layer names for a reading that has just arrived. */
      const v = document.querySelector('#page .num .v');
      if (v && !window.PAI_RAF.reduced()) { v.classList.remove('land', 'pulse'); void v.offsetWidth; v.classList.add('land', 'pulse'); }
    },
    /* For the tests and the rig: is it up, what did it see, and what did a frame cost.
       `probe(n)` draws n frames on the spot and answers with the cost. It exists for the same
       reason PAI_REFRESH.now() does — a thing that only happens on a timer, or only when a browser
       decides the tab is visible, cannot be measured — and the budget prompt 6 set (4 ms of
       main-thread work per frame) is a number somebody has to be able to read back. */
    probe(n) {
      if (!on || !cv) return null;
      cost.frames = 0; cost.total = 0; cost.worst = 0;
      const t = performance.now();
      for (let i = 0; i < (n || 60); i++) draw(t + i * 16.7);
      return this.cost();
    },
    up: () => on,
    globe: paneGlobe,
    reads: () => reads.slice(),
    cost: () => ({ frames: cost.frames, mean: cost.frames ? cost.total / cost.frames : 0,
      worst: cost.worst }),
  };
}());
window.PAI_ASKING = ASKING;

/* THE LEARN LAYER — the tester guide folded into the page.
 *
 * One or more marks on every registered section, and on the ladder, the lead and the foot. Each is a
 * question mark floating at the part of the page it explains; pressing one opens a panel that QUOTES
 * this node's own documentation for that part, names the page and the section the words come from by
 * their titles, links out, and walks to the next. The marks say what the node is FOR and what it
 * PUBLISHES as well as how to read the ladder: the purpose sits on the foot, on every view that has one.
 *
 * THE WALK FOLLOWS THE PAGE. Back and Next step through the marks in the order this view drew them,
 * top to bottom, foot last, so the next panel is the next thing a reader's eye would reach. The order
 * in learn.json is only the fallback, for a panel left open over a view that does not carry its mark.
 *
 * WHY THE QUOTE IS INLINE AND NOT A LINK. The node does not serve docs/site — the site build does,
 * onto planetai.fab.city — so there is nothing on this machine to fetch at read time and a link is
 * useless on a household LAN with no route out. tools/build_learn.py cuts the spans out of the
 * markdown at build time into app/static/learn.json, and `make lint` fails when that file is not
 * what the documentation says now. So the words in the panel are the documentation's, verbatim, and
 * the link is an offer rather than the answer.
 *
 * Fetched once, and only when somebody turns learn mode on: a reader who never does never pays for
 * it. Until it arrives the marks are simply not drawn — a question mark that cannot answer the
 * question is worse than no question mark. */
let LEARN = null, LEARN_ASKED = false, LEARN_AT = null;
function askLearn() {
  if (LEARN_ASKED || mode() !== 'learn') return;
  LEARN_ASKED = true;
  fetch('static/learn.json', { headers: { accept: 'application/json' } })
    .then(r => (r.ok ? r.json() : Promise.reject(new Error('HTTP ' + r.status))))
    .then(d => { LEARN = d; route(); })
    /* A node whose static file is missing says so in the bar rather than drawing marks that open
       nothing. `order` empty is how every other reader of LEARN tells the two apart. */
    .catch(e => { LEARN = { order: [], marks: {}, failed: String(e.message || e) }; route(); });
}

/* The stored quote is a span of markdown, because that is what the page it was cut from is. Four
   inline markers survive into it and are rendered here; nothing else is, and nothing is invented. */
function quoteHtml(q) {
  return window.K.esc(String(q).replace(/\s*\n\s*/g, ' '))
    .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1')
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/\*\*([^*]+)\*\*/g, '<b>$1</b>')
    .replace(/(^|[\s(])\*([^*]+)\*/g, '$1<i>$2</i>');
}
const plainly = s => String(s).replace(/`/g, '');

/* A mark, for a renderer that has a part to explain. `ref` is the id of the thing it is about: a
   component with no link in or out is what T5 counts, and a question mark floating beside nothing
   in particular is exactly that mistake in visible form. */
function qmark(key, ref) {
  const esc = window.K.esc;
  if (mode() !== 'learn' || !LEARN || !LEARN.marks[key]) return '';
  return `<button type="button" class="q" data-component="learnMark" data-learn="${esc(key)}"`
    + ` data-ref="${esc(ref)}" aria-expanded="false" aria-controls="askpane">`
    + `<span class="vh">What is ${esc(plainly(LEARN.marks[key].title))}?</span>`
    + `<span aria-hidden="true">?</span></button>`;
}

/* The bar under the header: where the words in the panels come from, and the way in for somebody
   who would rather be walked than hunt for question marks. */
function learnBar() {
  const esc = window.K.esc;
  if (mode() !== 'learn') return '';
  const box = s => `<div class="wrap"><div class="learnbar" id="learnbar"`
    + ` data-component="learnBar" data-ref="header">`
    + `<span class="qq" aria-hidden="true">?</span>${s}</div></div>`;
  if (!LEARN) return box(`<span>Asking this node for the marks&hellip;</span>`);
  if (!LEARN.order.length) {
    return box(`<span>This node did not answer for <code>static/learn.json</code>`
      + `${LEARN.failed ? ` (${esc(LEARN.failed)})` : ''}, so there are no marks on this page. The `
      + `page itself is unchanged — learn mode adds marks, it never hides anything.</span>`);
  }
  /* The count is filled in by learnSync() from the marks this VIEW actually drew, because the bar
     is built before the page under it is. Saying "all of them are on this page" on Network, where a
     third are, is the page telling a reader to look for something that is not there. The walk starts
     at the first mark this view drew, which is also only known once it has drawn. */
  return box(`<span class="ln">&nbsp;</span>`
    + `<button type="button" class="walk" data-learn-walk="1">Walk the page</button>`);
}

/* The marks this view drew, in the order a reader meets them: document order, top to bottom, the
   foot last. A key drawn twice counts once, at its first place. */
function learnWalk() {
  const seen = [];
  document.querySelectorAll('#page .q[data-learn], #foot .q[data-learn]').forEach(b => {
    const k = b.getAttribute('data-learn');
    if (LEARN && LEARN.marks[k] && !seen.includes(k)) seen.push(k);
  });
  return seen;
}

/* Every render rewrites the marks, so the one that is open has to be told again that it is. */
function learnSync() {
  /* Switching out of learn mode takes the marks away, so it takes the panel with them: a panel
     open over a page with nothing to point at is a thing the reader cannot get back to. */
  if (mode() !== 'learn') {
    if (LEARN_AT) learnClose();
    /* route() draws the pane straight after this, so the pane only has to change its state here. */
    if (window.PAI_ASK) window.PAI_ASK.learnOff();
    return;
  }
  const ln = document.querySelector('#learnbar .ln');
  if (ln && LEARN && LEARN.order.length) {
    const n = learnWalk().length;
    ln.innerHTML = (n
      ? `<b data-num="learn.here" data-cmp="learn.total ${LEARN.order.length}">${n}</b> mark`
        + `${n === 1 ? '' : 's'} on this view, of ${LEARN.order.length} across the views. Every one `
        + `quotes this node&rsquo;s own documentation, word for word, built in so it reads with no `
        + `route out. Press one and the words land in the pane, where the node answers questions `
        + `about them. Walking follows this view from the top.`
      : `No marks on this view. Walking starts at the first of the ${LEARN.order.length} and the `
        + `words come with it, so the panel reads the same from here.`);
  }
  if (!LEARN_AT) return;
  const at = document.querySelector(`.q[data-learn="${LEARN_AT}"]`);
  /* A mark that is not on the view the reader just moved to leaves the panel where it is: the
     words in it are a page of documentation, not a tooltip on a thing that has scrolled away. */
  if (at) at.setAttribute('aria-expanded', 'true');
}

function learnClose() {
  LEARN_AT = null;
  document.querySelectorAll('.q[aria-expanded="true"]')
    .forEach(b => b.setAttribute('aria-expanded', 'false'));
}

/* A pressed mark lands in the ask pane as a card: the documentation's words, this page's line about
 * them, where they come from by title, and Back and Next. The pane opens if it was closed; walking
 * replaces the card it is on rather than stacking forty-four of them. The walk is the page's own
 * order, read from the marks this view drew at the moment of the press. */
function learnOpen(key) {
  const m = LEARN && LEARN.marks[key];
  if (!m || !window.PAI_ASK) return;
  const walk = learnWalk();
  const ring = walk.includes(key) ? walk : LEARN.order;
  window.PAI_ASK.card(key, ring.indexOf(key) + 1, ring.length);
  LEARN_AT = key;
  document.querySelectorAll('.q').forEach(b =>
    b.setAttribute('aria-expanded', String(b.getAttribute('data-learn') === key)));
  const at = document.querySelector(`.q[data-learn="${key}"]`);
  if (at) at.scrollIntoView({ block: 'center', behavior: 'smooth' });
}

/* What the pane needs to draw a card: the mark, and the four inline markers rendered. */
window.PAI_LEARN_MARK = key => (LEARN && LEARN.marks[key]) || null;
window.PAI_LEARN_QUOTE = quoteHtml;

/* One listener, on the document, installed once — the marks are rewritten on every render and a
   listener bound to a button dies with it. */
document.addEventListener('click', e => {
  const t = e.target && e.target.closest ? e.target : null;
  if (!t) return;
  const close = t.closest('[data-learn-close]');
  if (close) { learnClose(); return; }
  const step = t.closest('[data-learn-step]');
  if (step && LEARN && LEARN.order.length) {
    /* The next mark on THIS view, in the order it drew them. A panel left open over a view that
       does not carry its mark steps through the whole list instead, from where it is. */
    const walk = learnWalk();
    const ring = walk.includes(LEARN_AT) || !LEARN_AT ? (walk.length ? walk : LEARN.order) : LEARN.order;
    const n = ring.length;
    const i = ring.indexOf(LEARN_AT);
    const d = Number(step.getAttribute('data-learn-step'));
    learnOpen(ring[i < 0 ? (d > 0 ? 0 : n - 1) : ((i + d) % n + n) % n]);
    return;
  }
  const walkStart = t.closest('[data-learn-walk]');
  if (walkStart && LEARN && LEARN.order.length) {
    learnOpen(learnWalk()[0] || LEARN.order[0]);
    return;
  }
  const q = t.closest('[data-learn]');
  if (!q) return;
  if (q.getAttribute('aria-expanded') === 'true') learnClose();
  else learnOpen(q.getAttribute('data-learn'));
});
document.addEventListener('keydown', e => { if (e.key === 'Escape') learnClose(); });

/* What the renderer inside PAI_LOAD can reach: a mark for a key, and the panel, by name. */
window.PAI_LEARN = { mark: qmark, bar: learnBar, open: learnOpen, close: learnClose };

/* Now first, then the three views that widen the frame in order — this hour, the years behind it,
   the network around it — then the wall, then the two that configure rather than report. The hash
   is the view id and none of those changed, so every link anybody has saved still lands. */
const VIEWS = [['now', 'Now'], ['historical', 'Historical'], ['network', 'Network'],
  ['wall', 'Wall'], ['arrange', 'Arrange'], ['setup', 'Set up']];
const askOn = () => {
  const row = ((window.SETTINGS || {}).runtime || []).find(x => x.key === 'UI_ASK');
  return !row || String(row.value || 'on').trim() !== 'off';
};
/* A newer release is out: /health carries what the node's daily check found (UPDATE_CHECK). News about
   this machine, not about the place, so it is ink and no colour: every colour on the page is a reading's.
   It stays until the node is updated, because the node only stops saying it once it is no longer true. */
function releaseBar(h) {
  const r = (h || {}).release || {};
  if (!r.newer || !r.latest) return '';
  const esc = window.K.esc;
  return `<div class="wrap"><p class="release" id="release"><b>PLANETAI ${esc(r.latest)} is out</b>`
    + `<span>this node runs ${esc(r.current || 'an older version')} \u00b7 on the node: <code>planetai update</code>`
    + ` (it backs up first)</span><a href="https://planetai.fab.city/docs/changelog/" rel="noreferrer">what changed</a></p></div>`;
}

function chrome(node, city, view, health) {
  const esc = window.K.esc;
  const reg = register(), md = mode(view);
  return `<header id="header"><div class="wrap">`
    + `<h1 class="brand"><b>${esc(node || 'PLANETAI')}</b><span>${esc(city || '')}</span></h1>`
    + `<nav class="views" aria-label="Views">` + VIEWS.map(([v, name]) =>
      `<button type="button" data-view="${v}" class="${v === view ? 'on' : ''}"`
      + `${v === view ? ' aria-current="page"' : ''}>${esc(name)}</button>`).join('')
    + `</nav>`
    + `<div class="seg mode" role="group" aria-label="How much of the page is shown">`
    + MODES.filter(([m]) => m !== 'simple' || SHORT_VIEW.has(view)).map(([m, name]) =>
      `<button type="button" data-mode="${m}" class="${m === md ? 'on' : ''}"`
      + ` aria-pressed="${m === md}">${esc(name)}</button>`).join('')
    + `</div>`
    + `<div class="seg register" role="group" aria-label="Register">`
    + [['paper', 'Paper'], ['dark', 'Dark']].map(([r, name]) =>
      `<button type="button" data-register="${r}" class="${r === reg ? 'on' : ''}"`
      + ` aria-pressed="${r === reg}">${esc(name)}</button>`).join('')
    + `</div>`
    /* Ask again. The page polls on the node's own cadence and says how old its figures are, but a
       reader who has just fixed something at the other end should not have to wait out an interval
       to find out it worked. This is also the only control that plays the loading state on purpose. */
    /* The ask pane's toggle, right of the modes. UI_ASK off draws none; a phone opens it from the foot. */
    + (askOn() ? `<button type="button" class="asktoggle" data-ask-toggle aria-pressed="false">`
      + `<i aria-hidden="true"></i>ask the node</button>` : '')
    + `<button type="button" class="reask" data-reask="1" title="Ask the node again">`
    + `<span aria-hidden="true">\u21bb</span><span class="vh">Ask the node again</span></button>`
    + `</div>${learnBar()}${releaseBar(health)}</header>`;
}

/* THE FOOT — what this machine is for, and where everything it publishes can be read.
 *
 * Every view but the wall ends here. Two lines, set small: the purpose, quoted from the lead of
 * docs/site/introduction.md and checked against it by tools/check_site.py, so the node says the
 * same thing the documentation and the programme page say; then the version and the four doors a
 * person or an agent needs: this node's own /health, its /mcp endpoint, its /llms.txt, and the
 * documentation. Before v0.73 none of them was named anywhere on the page, which left an agent
 * handed this node's address with nothing to find and a household with no way to the docs. */
const PURPOSE = 'PLANETAI is hyperlocal compute and intelligence for distributed production. '
  + 'Its purpose is fixed: clean air, water and soil for the people and the other living things '
  + 'around each node.';
const DOCS_URL = 'https://planetai.fab.city/docs/';
function foot(S) {
  const esc = window.K.esc, v = ((S && S.health) || {}).version || '';
  /* The foot is on every view but the wall, so its marks are the ones every view has: what the
     node is for, and the two doors an agent or a script needs first. In learn mode only. */
  const mark = (k, ref) => (window.PAI_LEARN ? window.PAI_LEARN.mark(k, ref) : '');
  return `<footer class="foot" id="foot" data-component="foot" data-ref="header"><div class="wrap">`
    + `<p class="why">${esc(PURPOSE)} Raw readings stay on this machine; only summaries leave.`
    + `${mark('production', 'foot')}${mark('purpose', 'foot')}</p>`
    + `<p class="doors"><span class="mono">${esc(v ? `planetai-node ${v}` : 'planetai-node')}</span>`
    + `<a class="mono" target="_blank" rel="noopener" href="/health">GET /health</a>${mark('health', 'foot')}`
    + `<span class="mono" title="Model Context Protocol, streamable HTTP; needs ADMIN_TOKEN">POST /mcp</span>`
    + mark('mcp', 'foot')
    + `<a class="mono" target="_blank" rel="noopener" href="/llms.txt">/llms.txt</a>`
    + `<a href="${DOCS_URL}">Documentation</a>`
    + `<a href="https://planetai.fab.city/">The programme</a></p>`
    + (askOn() ? `<p class="askfoot"><button type="button" class="asktoggle" data-ask-toggle aria-pressed="false">`
      + `<i aria-hidden="true"></i>ask the node</button></p>` : '')
    + `</div></footer>`;
}

/* SHARE_LEVEL=off and no token. /health still answers — it answers at every share level, which is
 * why the node's name and the nav are here at all — and every view draws the node's own sentence
 * about why. A blank would be the node lying about being broken, and a blank on the WALL is a black
 * shelf screen a household reads as a dead node. Both surfaces say it. */
let SAID = '';        /* the node's own words from the 403 that refused the page */

function drawRefused() {
  const el = document.getElementById('page');
  const v = (location.hash || '').replace(/^#/, '')
    || new URLSearchParams(location.search).get('view') || 'now';
  const said = window.K.refusedPage(SAID);
  applyRegister(v);
  if (v === 'wall') {
    document.body.className = 'wall wallview';
    el.innerHTML = `<div class="wallbox"><h1 class="vh">${window.K.esc(window.NODE_NAME || 'PLANETAI')}`
      + ` · refused</h1>${said}</div>`;
  } else {
    document.body.className = '';
    el.innerHTML = chrome(window.NODE_NAME, window.NODE_CITY, v) + `<div class="wrap">${said}</div>`;
  }
}
/* Globals the page fills only when a reader reaches the view that needs them, so the section list
 * can tell "this node does not have it" from "nobody has asked for it yet".
 *
 * OUT HERE, not inside main(), and that is the whole of a bug worth remembering. It was declared
 * near the foot of main() and read by sectionsBox() near the middle. A function declaration hoists;
 * a `const` does not. So sectionsBox() was callable and LATE was in its temporal dead zone, and
 * every render of the Set up view threw `Cannot access 'LATE' before initialization` from the
 * moment that line was written — main() bailed, #page kept whatever was on it, and the view simply
 * never appeared. Silent, because the page that was already drawn stayed drawn. */
const LATE = new Set(['SOURCES']);

function main() {
  const { S, ISS, ORDER, DIST, LAB, LOC, esc, fmt, pill, kicker, sentence, why, ask, asof,
    refusedPage, VIEW, STATE, evState, evOpen, evPick, evClock, evButtons, evAnswered } = window.K;
  const { H, km2, edge } = window.KH;
  const { N, where, link } = window.KN;
  const PAI = window.PAI;
  /* LAYOUT is this closure's; the kit's evCard asks whether a section was hidden in Arrange through this.
     Set here, not at the top of the shell: window.PAI does not exist until the kit's PAI_LOAD has run. */
  PAI.isHidden = id => (LAYOUT.hidden || []).includes(id);

  document.title = `PLANETAI · ${S.health.node || 'node'}`;

  /* The dial opens at resolution 8 — the grain GET /health already publishes, and the only stop on
     this dial that has ever left this machine. */
  const HERE = where(8);
  const RES = HERE.res;
  const Q = new URLSearchParams(location.search);

  /* Everything a module may read, in one object. A module that wants more asks for it here rather
     than reaching for a global, so the contract stays a list a reader can see. */
  const ctx = {
    RES, HERE, Q, VIEW, STATE,
    S, ISS, ORDER, DIST, LAB, LOC,
    H, N, P: window.PLAN,
    K: window.K, KH: window.KH, KN: window.KN, KMAP: window.KMAP,
    grain: H.grain_table.find(g => g.res === RES),
    /* Which register the page is in, for the one drawing that cannot be told by CSS: an <img> is a
       document of its own, so the ground asks for its palette in the URL. */
    register: document.documentElement.getAttribute('data-theme') === 'dark' ? 'dark' : 'paper',
    FLOOR: H.settings.PRESENCE_RES_FLOOR,
    PUB: H.publication,
    link,
    /* The same page with some query keys changed and the rest kept — a section's own controls
       (a base layer, a variable) must not lose the dial's position or the view. */
    qlink(extra) {
      const q = new URLSearchParams(location.search);
      for (const [k, v] of Object.entries(extra)) v == null ? q.delete(k) : q.set(k, v);
      return '?' + q.toString() + (location.hash || '');
    },
  };

  /* A learn mark from the shell rather than from a section: the rail, the lead, the provenance
     pill and the stages strip are drawn here and belong to nobody's pack. */
  const mark = (k, ref) => (window.PAI_LEARN ? window.PAI_LEARN.mark(k, ref) : '');

  /* The views are buttons and the URL is the hash, the way the page this replaces routed: one
     document served from /, no router, no build step. A span is a drawing; a button is a control. */
  /* THE DIAL IS NOW'S CONTROL AND NOBODY ELSE'S.
   *
   * It was drawn under the header of every view. On Now it is the control the page is built around
   * — the ground, the station groups, the claims and the grain all re-file when it turns. On
   * Network, Historical, Set up and Arrange nothing on the page answers to it, so it was a control
   * that looked live and did nothing: redundant, and distracting for being redundant. Reported
   * 16 September.
   *
   * The resolution still lives in the URL, so a link into any view at a given grain keeps that
   * grain — it simply cannot be changed from a page that does not vary by it. The wall keeps its
   * own dial, which is a different control on a different surface: it re-fills the wall's field as
   * it turns, which is what a wall is for. */
  const head = () => chrome(S.health.node, S.health.city, VIEW, S.health)
    + (window.WIRE_NOTE
      ? `<p class="note" data-component="wireNote" id="wire-note" data-ref="header">`
        + `${esc(window.WIRE_NOTE)}</p>`
      : '')
    + ((VIEW === 'now' && mode(VIEW) !== 'simple') || VIEW === 'arrange'
      /* Simple draws no ladder: the node picks the resolution and a household is not asked to. */
      /* Arrange draws Now's own sections — same registry, same want(NOW) — so it is Now in another
         mode and keeps the dial with them. Taking it away there left the ground, the station
         groups, the claims, the grain and the grain line all pointing at a control that was not on
         the page. */
      /* THE FOLD IS OUTSIDE THE STICKY BOX, deliberately. `.railwrap` is sticky because the rail is
         the control the whole of Now answers to and has to stay reachable; a fold inside it pinned
         566 px of a 1000 px viewport to the top of every screen the moment it was opened. Open, it
         belongs in the flow directly under the rail: it pushes the page down, it scrolls away as
         you read, and the strip itself stays where it was. */
      ? `<div class="railwrap"><div class="wrap">${rail()}</div></div>`
        + `<div class="wrap">${railfold()}</div>` : '');

  /* THE GRAIN RAIL — the top instrument, above the lead. Design log R14.
   *
   * It was a dial tucked under the header. It is the first thing on Now now, because the question
   * it answers — how coarse is what you are about to read — comes before the reading. Eleven stops,
   * resolution 2 to 12, every figure off `geometry.grain_table[]` and nothing worked out here.
   *
   * THE ZONES ARE TEXTURE, NOT HUE. Dotted where the cell may leave this machine, plain where it
   * stays, struck through where it is finer than the node says where it is. The cells blue keeps
   * its one meaning, a reader who cannot separate blue from grey still sees three zones, and the
   * rail survives being printed. Texture alone is not a label, so each stop also says which zone it
   * is in its accessible name — the key below says it once, in words, for everybody else.
   *
   * Pressing a stop still re-derives the whole page; that is what this control is for. */
  function rail() {
    const open = Q.get('worth') === '1';
    const zone = g => g.may_leave ? ', may leave this machine'
      : g.finer_than_published ? ', finer than this node says where it is' : '';
    const stops = H.grain_table.map(g => {
      const on = g.res === RES;
      return `<a class="${on ? 'on ' : ''}${g.may_leave ? 'leaves ' : ''}`
        + `${g.finer_than_published ? 'toofine' : ''}" href="${link(N.chain[g.res], { res: g.res })}"`
        + ` data-move="${g.res < RES ? 'out' : g.res > RES ? 'in' : 'here'}"`
        + `${on ? ' aria-current="true"' : ''}`
        + ` aria-label="resolution ${g.res}, ${esc(edge(g.edge_m))} to an edge, `
        + `one cell ${esc(km2(g.area_m2))}${zone(g)}">`
        + `<b class="r">${g.res}</b><small class="s">${esc(edge(g.edge_m))}</small></a>`;
    }).join('');
    /* The rail's link out is the sentence it re-derives. On Now that is the grain line; the arm
       that pointed at `satellite` died when the satellite moved to Historical in v0.56 and had been
       naming an id that was not on the page for two releases. A component pointing at an id that is
       not there is what T5 counts. */
    const ref = 'ground-figure';
    return `<div class="rail" id="rail" data-component="rail" data-kind="row" data-ref="${esc(ref)}"`
      + ` role="group" aria-label="resolution, ${N.res_min} to ${N.res_max}; `
      + `standing at ${RES}">${stops}</div>`
      + (window.PAI_SCALES ? window.PAI_SCALES.scaleStrip(H.grain_table, RES) : '')
      + `<div class="railkey" data-component="railKey" data-ref="rail">`
      /* THE FOLD'S TRIGGER IS THIS CHIP, and it is this chip because a fold of its own cost 33.5 px
         and T1 lost the ask and the as-of off the first screen at both 390 and 1440 — measured, on
         a gate that was green the render before. The key's last chip already names the fold's
         subject ("one cell here"), so making it the control adds nothing to lay out. */
      + `<a class="worth${open ? ' on' : ''}" href="${ctx.qlink({ worth: open ? null : '1' })}"`
      + ` aria-expanded="${open}">one cell here: <b data-num="rail.area" data-cmp="rail.res">`
      + `${esc(km2(ctx.grain.area_m2))}</b></a>${mark('dial', 'rail')}</div>`;
  }

  /* WHAT A STOP IS WORTH — the rail's own fold. Closed by default, in every mode, like the three
   * folds already on the page.
   *
   * The rail says which stop you are standing on and what one cell there is worth. It never said
   * what CHOOSING it costs, and the one fact about this ladder that no drawing on the page carried
   * is the step: each stop is about seven times the area of the one below it, so the cell you are
   * on is a shade over two and a half times across the one beneath and a bit over a third of the
   * one above. Three hexagons to true relative scale say that in one look; eleven evenly spaced
   * buttons cannot, which is what the ruler under them already concedes.
   *
   * The six footprints below came out of the claim cards in Decide, where each carried a drawing of
   * its own compacted covering beside a number counting cells at this rail's resolution — a picture
   * and a number about different things, under a control neither answered to. Here the number is
   * the thing that moves when the rail moves, which is the whole argument the cards were making.
   *
   * NOTHING IS WORKED OUT HERE THAT IS NOT DRAWING. The radii are a ratio of two areas the node
   * published, used to size a polygon, and the counts are `cells_at[res]` read off the wire. No
   * derived number is printed as a fact.
   */
  function railfold() {
    if (Q.get('worth') !== '1') return '';
    const i = H.grain_table.findIndex(g => g.res === RES);
    const near = [i - 1, i, i + 1].map(k => H.grain_table[k]).filter(Boolean);
    if (near.length < 2) return '';
    const top = near[0].area_m2;
    /* Coarsest first, so the finer cells are painted over it rather than under. */
    const hexes = near.map(g => {
      const R = 46 * Math.sqrt(g.area_m2 / top), on = g.res === RES;
      const pts = [30, 90, 150, 210, 270, 330].map(a => {
        const t = a * Math.PI / 180;
        return `${(50 + R * Math.cos(t)).toFixed(1)},${(50 + R * Math.sin(t)).toFixed(1)}`;
      }).join(' ');
      return `<polygon points="${pts}" fill="var(--cells)" fill-opacity="${on ? 0.18 : 0}"`
        + ` stroke="var(--ink)" stroke-opacity="${on ? 0.7 : 0.3}"`
        + ` stroke-width="${on ? 2.5 : 1}"${on ? '' : ' stroke-dasharray="4 4"'}>`
        + `<title>resolution ${g.res} · ${esc(km2(g.area_m2))}</title></polygon>`;
    }).join('');
    const fig = `<div class="pic gridwrap"><svg class="hexgrid" viewBox="0 0 100 100" role="img"`
      + ` aria-label="one cell at resolution ${RES} drawn to scale against `
      + `${near.filter(g => g.res !== RES).map(g => `resolution ${g.res}`).join(' and ')}">`
      + `${hexes}</svg><div class="cap">`
      + near.map(g => `<span class="${g.res === RES ? 'on' : ''}">res ${g.res} · `
        + `${esc(edge(g.edge_m))}</span>`).join('') + `</div></div>`;
    /* With no coordinates there is no ground for a footprint to cover, and the claims section says
       so in its own words. The drawing above is still true — a cell's size is not a question about
       where it is — so the fold keeps it and drops only the table. */
    const claims = (H.claims || []).length && ctx.KH.sited()
      ? `<div class="tblwrap" tabindex="0" role="region" aria-label="what each footprint costs to `
        + `cover at resolution ${RES}"><table class="tbl"><thead><tr><th>what speaks</th>`
        + `<th>declared</th><th>cells at resolution ${RES}</th></tr></thead><tbody>`
        + H.claims.map(c => `<tr${c.key === H.claims[H.claims.length - 1].key ? ' class="picked"' : ''}>`
          + `<td>${esc(c.name)}</td><td class="mono">${esc(c.declared)}</td>`
          + `<td class="mono">${(c.cells_at[RES] || 0).toLocaleString()}</td></tr>`).join('')
        + `</tbody></table></div>`
      : '';
    /* OPEN IS A QUERY KEY, not a DOM state, because a render throws an open fold away (the
       hashchange handler below says so in as many words) and the one control this exists to be read
       against — the rail — re-renders the page every time it is pressed. Opening it and turning the
       dial closed it, which is precisely the move it is for. `link()` copies the whole query, so
       every stop carries the key with no work and nothing has to listen for anything. */
    return `<div class="railfold" id="railfold" data-component="railFold" data-ref="rail">`
      + ruler()
      + `<div class="railkey" data-component="railKey" data-ref="rail">`
      + `<span><i class="leaves"></i>may leave this machine — resolution ${ctx.FLOOR} and coarser, `
      + `which is the <code>RETICULUM_PRESENCE_RES</code> setting</span>`
      + `<span><i class="fine"></i>finer than this node says where it is — past ${ctx.PUB.res}, `
      + `because ${esc(String(ctx.PUB.why || '').replace(/\s*—.*$/, ''))}</span>`
      + `</div>`
      + `<div class="rh"><h2>What one cell at resolution ${RES} is worth</h2>`
      + `<a href="${ctx.qlink({ worth: null })}">Close</a></div>`
      + `<div class="rf">${fig}<div class="rfx"><p>Each rung down is about seven times finer by `
      + `area than the one above it, and the drawing is to scale: the filled cell is the one you `
      + `are standing on.${claims ? ` The table is what each thing this node speaks for costs to `
      + `cover at it — the number that moves when this control moves.` : ''}</p>${claims}</div>`
      + `</div></div>`;
  }

  /* THE RULE under the rail: where each grain truly sits between 10 m and 200 km.
   *
   * The stops are evenly spaced because they are eleven buttons; the grains they name are not —
   * resolution 2 is 183 km to an edge and resolution 12 is 9. A linear row of equal boxes says the
   * step from 7 to 8 is the step from 11 to 12, and it is a factor of about 2.6 either way but on
   * numbers three orders of magnitude apart. This puts a tick where each one actually falls.
   *
   * IT RUNS THE WAY THE RAIL RUNS — coarse on the left, fine on the right. The rule was drawn the
   * other way round, 10 m at the left edge and 100 km at the right, under a rail whose first stop is
   * 172 km and whose last is 10 m. So every tick sat under the stop at the opposite end of the row:
   * the mark for the grain you were standing at appeared beside a number three orders of magnitude
   * from it, and a reader checking one against the other read the rule backwards. A rule under a row
   * has one job, which is to be the same axis as the row.
   *
   * Hidden below 860 px, where it would be drawing a distinction finer than the pixels it has. */
  function ruler() {
    const LO = 10, HI = 200000;
    const at = m => 100 - ((Math.log10(Math.max(LO, Math.min(HI, m))) - Math.log10(LO))
      / (Math.log10(HI) - Math.log10(LO))) * 100;
    const ticks = H.grain_table.map(g =>
      `<i class="${g.res === RES ? 'on' : ''}" style="left:${at(g.edge_m).toFixed(2)}%"></i>`).join('');
    const marks = [[10, '10 m'], [100, '100 m'], [1000, '1 km'], [10000, '10 km'],
      [100000, '100 km']].map(([m, name]) =>
      `<span style="left:${at(m).toFixed(2)}%">${esc(name)}</span>`).join('');
    return `<div class="ruler" data-component="ruler" data-ref="rail" aria-hidden="true">`
      + `<div class="line">${ticks}</div><div class="marks">${marks}</div></div>`;
  }

  /* The lead is the shell's: the node's own headline, the ask, the grain line, the as-of — and the
     figure a module offers for it (the ground module offers the map). A household opens the page to
     be told something, and that sentence is not a module's to move. */
  function lead() {
    /* In simple a reader may be looking at another issue than the node's pick (the also line). The
       pick is page state; advanced always draws the node's own. */
    const simple = mode(VIEW) === 'simple', pick = window.PAI_HERO_PICK, nodePick = S.issues.headline;
    const hk = simple && pick && ISS[pick] && ISS[pick].hero ? pick : nodePick, d = ISS[hk];
    window.PAI_HERO_SHOWN = hk;
    const leads = PAI.sections.filter(s => s.lead && (s.needs || []).every(PAI.has));
    const fig = leads.map(s => { try { return s.lead(ctx) || ''; } catch { return ''; } }).join('');
    /* A lead-only section draws no band, so the marks it declares have nowhere to sit but beside
       the drawing it contributed. The ground is the only one today and it is the reason for this:
       without it the two marks about the map would have been registered and never drawn. */
    const figMarks = leads.filter(s => !s.render)
      .map(s => (s.learn || []).map(k => mark(k, s.anchor || s.id)).join('')).join('');
    /* THE ASK STRIP IS GONE FROM THE LEAD and lives in Act, where the ledger it belongs to is. It
       was the lead's fifth block and the only one a reader could act on, which made the lead a
       control panel as well as a sentence. The stamp line below says how many are open and where
       they are, which is what the lead owes a reader: the fact, and the way to it. */
    /* WHAT THE LAST LINE COUNTS follows the node. On events or shadow it is events, the way the bot tells
       them (docs/SPEC_dashboard_events.md §4.1); on a rules node, an older one or an unreadable block it is
       alerts, because that is what the node has. `open_asks` holds the alert rows themselves. */
    const st = evState(), evs = evOpen(), E = (S.issues || {}).events || {};
    const evMode = st === 'events' || st === 'shadow';
    /* On events or shadow an alert an open event covers is drawn as that event, so only the uncovered ones
       are left to count or pick, the same set Decide draws as cards: the two must say the same thing. */
    const unc = new Set(E.uncovered_asks || []);
    const asksOf = k => (ISS[k].open_asks || []).filter(a => !evMode || unc.has(a.id));
    const openAll = ORDER.reduce((n, k) => n + asksOf(k).length, 0);
    const nEv = evs.length, asEv = evMode && nEv > 0, nAsk = asEv ? nEv : openAll, e0 = evs[0] || {};
    const askLine = nAsk
      ? `<a class="askref" href="#stage-decide" data-role="ask" data-component="askRef"`
        + ` data-ref="stage-decide">`
        + (asEv
          ? `<b data-num="events.open" data-cmp="alert events open">${nEv}</b> event${nEv === 1 ? '' : 's'} open`
            + ` \u00b7 ${esc(String(e0.issue))} \u00b7 ${esc(String(e0.kind))} since ${esc(evClock(e0.opened_at))}`
            + `${st === 'shadow' ? ' \u00b7 shadow' : ''}`
          : `<b data-num="asks.open" data-cmp="alerts open across ${ORDER.length} issues">${openAll}</b>`
            + ` alert${openAll === 1 ? '' : 's'} open`)
        + ` \u00b7 in Decide</a>`
      : `<span class="askref none" data-role="ask" data-component="askRef" data-ref="stage-decide">`
        + `nothing open${evMode && E.cleared_today ? ` \u00b7 ${E.cleared_today} cleared today` : ''}</span>`;
    /* THE ISSUE'S PICTOGRAM. One per issue, drawn once, at hero size, and never repeated to show
       quantity — that is the whole difference between this family and the counting signs, and it is
       why it is 15x11 rather than on the 24-unit grid. A <use> of a symbol already in signs.svg, so
       nothing is redrawn per reading. An issue with no pictogram yet simply has none: the lead is
       not going to invent a mark for it. */
    const pix = heroPix(hk, d);
    const stamp = ((d.hero || {}).stamp || {})[LOC] || '';
    const plain = ((d.hero || {}).plain || {})[LOC] || '';
    /* The plain figure gets the crossed mark when over the line (same rule as monument). Extract
       numerals from plain and wrap them; if plain has no numeral, render unchanged. */
    const cell = (d.stack || {})[d.headline];
    const plainCrossed = !!(d.line && cell && cell.value != null && cell.value > d.line.value
      && (d.state === 'act' || d.state === 'notable'));
    const markedPlain = plain && cell && cell.value != null
      ? esc(plain).replace(esc(fmt(cell.value, d.dp)),
          `<b class="${plainCrossed ? 'crossed ' : ''}mono">${esc(fmt(cell.value, d.dp))}</b>`)
      : esc(plain);
    /* Simple's eyebrow: the issue and when it was read, in words, with no state word in capitals. */
    const eb = `<div class="eb" data-lv="simple" data-component="heroEyebrow" data-ref="num-${esc(hk)}">`
      + `<b>${esc(d.name[LOC])}</b>${stamp ? ` \u00b7 ${esc(stamp)}` : ''}`
      + (hk !== nodePick
        ? `<span class="pin">you are looking at this \u00b7 the node\u2019s pick is `
          + `${esc(ISS[nodePick].name[LOC])}</span><button type="button" class="back" data-hero="">back</button>`
        : '') + `</div>`;
    const askAt = asksOf(hk).length ? hk : ORDER.find(k => asksOf(k).length);
    /* SIMPLE'S OPEN ROW on events or shadow is the open event's action and its three buttons (spec §4.4),
       with the shown issue's sign. `data-ref` is the lead's own numeral (hk), which monument() ids
       `num-<hk>`; the event's issue can differ, and the sign is the event's. */
    const evRow = (e, key, n) => {
      const ed = ISS[e.issue] || { name: {} }, sg = (ed.hero || {}).sign;
      return `<div class="ask askrow evrow" data-lv="simple" data-component="eventRow" data-role="ask"`
        + ` id="evrow-${esc(String(e.id))}" data-ref="num-${esc(key)}">`
        + (sg ? `<svg class="sgn" viewBox="0 0 24 24" role="img" aria-label="${esc(ed.name[LOC] || e.issue)}">`
          + `<use href="static/signs.svg#${esc(sg)}"/></svg>` : '')
        + `<div class="what">${e.action && e.action.text ? esc(e.action.text)
          : `${esc(e.kind)}${(e.rooms || []).length ? ` \u00b7 ${esc(e.rooms.join(', '))}` : ''}`}`
        + `${st === 'shadow' ? `<span class="m">shadow \u2014 nothing was sent</span>` : ''}</div>`
        + evAnswered(e) + (e.answer && e.answer.stage === 'acted' ? '' : evButtons(e))
        + (n > 1 ? `<p class="evmore" data-lv="simple">and ${n - 1} more open \u00b7 in advanced</p>` : '') + `</div>`;
    };
    return `<section class="lead" id="band-${esc(hk)}" data-band="lead">`
      + lv(`<div class="leadk">${kicker(hk, d)}${mark('lead', `sentence-${esc(hk)}`)}</div>`, 'adv')
      + eb + monument(hk, d, pix) + sentence(hk, d, 'big')
      + lv(why(hk, d, (S.issues.headline_rule || {})[LOC] || ''), 'adv')
      + (plain ? `<p class="plain" data-lv="simple" data-component="heroPlain" data-ref="sentence-${esc(hk)}">`
        + `${markedPlain}</p>` : '')
      /* The rule the hero declares, where the four meters were. They drew every issue on a scale
         worked out from tonight's numbers; the rule's ends are the issue's own, so a reading of 12
         looks the same size tomorrow as tonight. The four distances in full are in the matrix. */
      + heroRule(hk, d)
      + (asEv ? evRow(evPick(evs, hk), hk, nEv) : askAt ? askRow(askAt, ISS[askAt], asksOf(askAt)[0]) : '')
      /* WHY THIS ONE IS AT THE TOP is in the why line above, not in a paragraph of its own. The
         words are the node's now (`headline_rule` on /issues) rather than three strings in this file:
         v0.59 changed the ranking on 18 September and the page's copy of the explanation had no way
         of knowing. A ranking a reader cannot check is the one thing this page does not do. */
      + `<div class="whenline">${stamp ? `<span class="stamp" data-lv="adv" data-component="heroStamp"`
        + ` data-ref="num-${esc(hk)}">${esc(stamp)}</span>` : ''}${asof()}`
      + lv(askLine, 'adv')
            + lv(`${window.K.stamp()}`, 'adv')
      + lv(S.fixture ? pill('cached', 'a committed snapshot, replayed through this node’s own engine')
        : window.STALE ? pill('stale', 'the last reading this node gave; it has stopped answering')
        : pill('live', 'measured by this node, and kept up to date'), 'adv')
      + mark('prov', `band-${esc(hk)}`) + `</div>`
      + fig + (figMarks ? `<div class="figmarks">${figMarks}</div>` : '') + `</section>`;
  }

  /* Decision of 15 September: Now carries the ground, the stations, the asks and the measure; the
     satellite, the two radios and the hardware are the Network view. One registry serves both, and the
     notes band follows each view's own sections. The claims, the grain, the sources and the requests moved
     to Network in v0.78 (docs/SPEC_dashboard_events.md §4.1): they are about what this node may say and
     send, which is the node in relation to the network. */
  const NOW = ['ground', 'matrix', 'day', 'sensors', 'forecast', 'decide',
    'asks', 'ledger', 'measure', 'effect', 'figures'];
  /* Network is this node in relation to the network, and nothing else: who it hears over radio, who
     hears it, and what hardware does the hearing. Satellite was put here on 15 September and moved
     out on 16 September at Tomas's word — a Sentinel annual median is not a neighbour, it is a
     record of this ground in past years, and it belongs with the other things that have a date on
     them rather than at the top of the page about the network.
     Trust moves with it for the same reason: a sensor's coverage over seven days and the hours since
     it last spoke are a history of that sensor, not a fact about now. */
  const NETWORK = ['netmap', 'registry', 'reticulum', 'meshtastic', 'hardware', 'sources', 'requests', 'claims',
    'grain'];
  const HISTORICAL = ['shape', 'satellite', 'reach', 'trust'];
  /* NOW IS THE DEFAULT HOME, AND WITHOUT THIS LINE THE CONTRACT IS A LIE.
   *
   * The three lists above are how one registry serves three views, and they are lists of ids this
   * file knows. A pack's section is an id this file has never heard of — that is the whole point of
   * the contract, and the docstring at the top of this file promises it: "the shell renders whatever
   * registered", "adding a feature is adding a file". From the Now/Network split on 15 September
   * until this line, a registered section whose id was not typed into one of those three arrays was
   * filtered out of every view and drawn nowhere. It registered, it appeared in Set up's list of
   * sections as `drawing`, and it was on no page. Found by rendering a stranger's pack — see
   * `measure.mjs extend`, which is the only thing that ever asked.
   *
   * So the two named lists are the exceptions and Now is the rest. Network and Historical stay
   * closed, because what belongs on them is a judgement about the frame those views draw; Now is
   * the page about this place now, which is where a section about this place goes unless somebody
   * has said otherwise. Order is untouched: render() sorts by stage, then order, then id. */
  const placed = new Set([...NOW, ...NETWORK, ...HISTORICAL]);
  const homeless = PAI.sections.concat(PAI.declared(ctx)).map(s => s.id).filter(id => !placed.has(id));
  applyOrder();

  const el = document.getElementById('page');
  document.body.classList.toggle('wallview', VIEW === 'wall');
  /* What the CSS hides by: `simple` only on Now, where simple is the three questions. */
  document.body.dataset.lv = VIEW === 'now' && mode(VIEW) === 'simple' ? 'simple' : 'adv';
  applyRegister(VIEW);
  if (VIEW === 'wall') {
    document.body.classList.add('wall');
    /* PAI.render() wraps every section so one that throws prints that it did and the rest of the
       page stands. The wall had no such guard, and it is the one surface nobody is watching: a throw
       before innerHTML was assigned showed a black shelf screen and said nothing. */
    let box;
    if (STATE === 'refused') box = `<div class="wallbox">${refusedPage()}</div>`;
    else {
      try { box = window.WALL ? window.WALL.render(ctx) : `<div class="wallbox">${PAI.wall(ctx)}</div>`; }
      catch (e) {
        box = `<div class="wallbox"><h1 class="vh">${esc(S.health.node || 'this node')} · the wall</h1>`
          + `<p class="note" data-component="failed" id="wall-failed" data-ref="header">The wall did `
          + `not render: ${esc(String((e && e.message) || e))}. A failure is not an answer, so this `
          + `screen says so rather than going black.</p></div>`;
      }
    }
    el.innerHTML = box;
    if (window.WALL && window.WALL.start && STATE !== 'refused'
        && el.querySelector('#wall-lead')) window.WALL.start(ctx);
  } else if (STATE === 'refused') {
    el.innerHTML = head() + `<div class="wrap">${refusedPage(SAID)}</div>` + foot(S);
  } else if (VIEW === 'now' || VIEW === 'arrange') {
    ARRANGING = VIEW === 'arrange';
    el.innerHTML = head() + `<div class="wrap">`
      + `${PAI.render(ctx, lead(), { only: want([...NOW, ...homeless]),
        stages: ['decide', 'observe', 'act', 'measure'] })}</div>`
      + foot(S) + (ARRANGING ? arrbar() : '');
    if (ARRANGING) { arrangeControls(); fillRestore(); }
  } else if (VIEW === 'network') {
    el.innerHTML = head() + `<div class="wrap">${PAI.render(ctx, '', { only: want(NETWORK) })}</div>` + foot(S);
  } else if (VIEW === 'historical') {
    el.innerHTML = head() + `<div class="wrap">${PAI.render(ctx, '', { only: want(HISTORICAL) })}</div>` + foot(S);
  } else {
    /* Set up, in the modular page, gains one box the drawings did not have: the sections this node
       runs, by pack, drawn from the real registry — so the list is what this node has and not a
       sketch of one, and each row says whether that section is drawing or has nothing here yet. */
    const setup = VIEW === 'setup' && window.PAI_SETUP ? window.PAI_SETUP.markup() : '';
    const sections = VIEW === 'setup' ? sectionsBox() : '';
    el.innerHTML = head() + `<div class="wrap"><section class="band" id="view-${esc(VIEW)}">`
      + `<div class="k"><span>` + esc(VIEW) + `</span>`
      + (VIEW === 'setup' ? mark('settings', `view-${esc(VIEW)}`) : '') + `</div>`
      + setup + sections + `</section></div>` + foot(S);
    /* The pane draws itself locked, then asks the node what this reader may see. */
    if (VIEW === 'setup' && window.PAI_SETUP) window.PAI_SETUP.load();
  }

  /* The bar. Sticky at the foot, because the mode's instructions, its Default and its Done all sat
     nine screens below the fold on the page this replaces and a keeper who pressed Arrange saw three
     unexplained buttons appear beside every band and no way to finish. */
  function arrbar() {
    return `<div class="arrbar" id="arrbar" role="region" aria-label="Arrange">`
      + `<span>Arrange: ← and → move a section within its stage, ✕ hides it. `
      /* The three that do not move, said rather than left to be discovered by trying. They carry no
         controls because they are not sections — the rail is the page's one instrument, the lead is
         its answer, and the ground is the surface both stand on — and a reader who cannot see why a
         band has no arrows will assume the arrows are broken. */
      + `<b>The ladder, the lead and the ground are fixed</b> and carry no controls: the first is this `
      + `page's instrument, the second its answer, the third the surface both stand on.</span>`
      + `<label class="vh" for="arr-restore">Put a hidden section back</label>`
      + `<select id="arr-restore"><option value="">Restore a hidden section…</option></select>`
      + `<button type="button" class="btn ghost" id="btn-arr-reset">Default</button>`
      + `<button type="button" class="btn" id="btn-arr-done">Done</button></div>`;
  }

  /* The menu that puts a hidden section back. It was markup and nothing else on the page this
     replaces — `#arr-restore` appeared once and was never referenced — so the only way back from a
     hidden band was Default, which discards every other choice too. */
  function fillRestore() {
    const sel = document.querySelector('#page #arr-restore');
    if (!sel) return;
    const hidden = LAYOUT.hidden || [];
    const name = id => (PAI.sections.find(s => s.id === id) || {}).title || id;
    sel.innerHTML = `<option value="">Restore a hidden section…</option>`
      + hidden.map(id => `<option value="${esc(id)}">${esc(name(id))}</option>`).join('');
    sel.disabled = !hidden.length;
  }

  /* Three controls on every section, and a sentence after each press saying what happened. */
  function arrangeControls() {
    const bands = [...document.querySelectorAll('#page section.band[data-band]')]
      .filter(el => el.dataset.band.includes(':'));
    const ids = bands.map(el => el.dataset.band.split(':')[1]);
    const stageOf = id => (PAI.sections.find(s => s.id === id) || {}).stage;
    bands.forEach((el, i) => {
      if (el.querySelector(':scope > .arr')) return;
      const id = ids[i];
      const bar = document.createElement('div');
      bar.className = 'arr';
      bar.innerHTML = `<button type="button" data-move="-1" aria-label="Move up">←</button>`
        + `<button type="button" data-move="1" aria-label="Move down">→</button>`
        + `<button type="button" data-hide="1" aria-label="Hide">✕</button>`;
      bar.onclick = ev => {
        const b = ev.target.closest('button');
        if (!b) return;
        const title = (PAI.sections.find(s => s.id === id) || {}).title || id;
        if (b.dataset.hide) {
          LAYOUT.hidden = [...(LAYOUT.hidden || []), id];
          say(`${title} hidden. Put it back from the menu at the foot of the page.`);
        } else {
          const from = ids.indexOf(id), to = from + Number(b.dataset.move);
          /* Across a stage boundary is not a move: the loop's order is the page's argument, not a
             preference. Saying so beats a button that looks broken. */
          if (to < 0 || to >= ids.length || stageOf(ids[to]) !== stageOf(id)) {
            say(`${title} is already ${Number(b.dataset.move) < 0 ? 'first' : 'last'} in its stage.`);
            return;
          }
          const next = [...ids];
          next.splice(to, 0, next.splice(from, 1)[0]);
          LAYOUT.order = next;
          say(`${title} moved ${Number(b.dataset.move) < 0 ? 'up' : 'down'}.`);
        }
        route();
      };
      el.prepend(bar);
    });
  }

function sectionsBox() {
    const byPack = {};
    for (const s of PAI.sections) (byPack[s.pack] = byPack[s.pack] || []).push(s);
    const packs = Object.entries(byPack).sort(([a], [b]) => (a === 'core') - (b === 'core') || a.localeCompare(b));
    return `<div class="wf" data-component="sectionsBox" id="wf-sections" data-ref="view-setup">`
      + `<div class="box"><div class="cap">Sections on this node, by pack · ${PAI.sections.length} `
      + `registered · drag to reorder within a stage, switch off to hide, propose to send</div>`
      + packs.map(([pack, list]) =>
        `<div class="cap">${esc(pack)}${pack === 'core' ? ' · the renderer’s own' : ''}</div>`
        + list.map(s => `<div style="display:grid;grid-template-columns:minmax(0,1fr) auto;`
          + `gap:8px;align-items:center;padding:4px 0" data-component="sectionRow" id="wfs-${esc(s.id)}"`
          + ` data-ref="wf-sections"><span class="said" style="font-size:12.5px">${esc(s.title)}`
          + ` <span class="mono" style="color:var(--mute);font-size:10.5px">· ${esc(s.stage)}`
          + `${(s.needs || []).length ? ` · needs ${esc(s.needs.join(', '))}` : ''}</span></span>`
          + `<span class="mono" style="font-size:10.5px;color:var(--mute)">`
          /* Three states, not two. A need that is fetched on the view the section lives on is not
             absent from the node — it has not been asked for yet, and calling that "nothing here
             yet" on Set up says a section is dataless when opening its own view would fill it. */
          + `${(s.needs || []).every(PAI.has) ? 'drawing'
            : (s.needs || []).every(n => LATE.has(n)) ? 'asked for on its own view'
              : 'nothing here yet'}</span></div>`).join(''))
        .join('')
      + `<div class="cap">Reordering and hiding a section is Arrange, on its own view. Proposing one `
      + `back — the section’s file, its notes and this node’s renders, sent as one bundle for `
      + `another node to try — is not built on this node yet, and this line is the whole of what `
      + `exists. A pack a node does not have shows above as one line saying what it needs, never as `
      + `a blank.</div></div></div>`;
  }
}

/* ------------------------------------------------------------------ the views, in the URL */
/* The hash and not a path: this page is one document served from /, it has no router and no build
 * step, and a path would need the node to serve every view's URL back as the same file. A re-render
 * is cheap here — every section draws from globals already in memory and nothing is fetched again —
 * so a view change is a render, not a fetch. */
/* /sources is 417 kB — nearly what /issues costs — to draw three numbers, and it is wanted on
 * Network and nowhere else. So it is asked for the first time somebody goes there, once, and the
 * page redraws when it arrives; a reader who never opens Network never pays for it. The flag is set
 * before the fetch, so a reader who switches away and back does not ask twice, and a refusal leaves
 * SOURCES null and the section prints the line its `needs` gives it. */
let SOURCES_ASKED = false;
function askSources() {
  /* Asked in fixture mode too: the registry is a pinned FILE this repository carries in
     data/sources, identical on every node at a given pin, so it is not something a capture of one
     node has or lacks. The rig and tools/preview.py both answer it from registry.load(). */
  if (SOURCES_ASKED || VIEW !== 'network') return;
  SOURCES_ASKED = true;
  api('/sources').then(d => { window.SOURCES = d; route(); }).catch(() => { window.SOURCES = null; });
}

/* Historical's strips reach as far back as the node holds, up to 90 days. Asked the first time Historical is drawn,
 * not at boot: a household that never opens Historical never pays for it. */
let DAYS90_ASKED = false;
function askDays90() {
  if (DAYS90_ASKED || FIXTURE || VIEW !== 'historical') return;
  DAYS90_ASKED = true;
  /* DAYS90_DONE is set either way, so a refusal draws the strips' own "does not send its days yet" line instead of
     "asking" for good. */
  api('/issues/days?days=90')
    .then(d => { window.DAYS90 = d; window.DAYS90_DONE = true; redraw(); })
    .catch(() => { window.DAYS90 = null; window.DAYS90_DONE = true; redraw(); });
}

function route() {
  readView();
  askSources();
  askDays90();
  askLearn();
  document.body.className = '';
  main();
  /* main() has just replaced the page, so any player on it is fresh markup with no listeners and
     any timer from the last render is pointing at elements that are gone. */
  const page = document.getElementById('page');
  if (page) wireSat(page);
  /* Figures are placeholders in the markup main() just wrote; the kit draws them now (kit 6 · figures). */
  if (page) window.K.mountFigs(page);
  /* The map ground (UI_GROUND=map) mounts the same way, once per fresh figure; a poll swaps the living one back. */
  if (window.GROUND && window.GROUND.mount) window.GROUND.mount();
  learnSync();
  /* The pane lives outside #page and keeps its thread; it only needs telling the body was reset. */
  if (window.PAI_ASK) window.PAI_ASK.draw();
  /* The renderer has just replaced #page, so the browser's own jump to an anchor happened against
     markup that no longer exists. Do it again, now that the thing being linked to is on the page. */
  const anchor = (location.hash || '').replace(/^#/, '');
  const target = anchor && !VIEW_NAMES.has(anchor) ? document.getElementById(anchor) : null;
  if (target) target.scrollIntoView({ block: 'start' });
  else window.scrollTo(0, 0);
}

/* Saying something, wherever the pane that says things is. */
function say(msg, bad) {
  if (window.PAI_SETUP) window.PAI_SETUP.toast(msg, bad);
}

/* Reset writes the same empty UI_LAYOUT that Done writes, so it survives a reload instead of coming
 * back from the node on the next read. */
async function layoutSave(reset) {
  if (reset) LAYOUT = { order: [], hidden: [] };
  const body = (LAYOUT.order.length || LAYOUT.hidden.length) ? JSON.stringify(LAYOUT) : '';
  try {
    await setSetting('UI_LAYOUT', body);
    say(reset ? 'Back to the default order.' : 'Saved on the node.');
  } catch (e) {
    say(String((e && e.message) || e), true);
  }
  history.pushState({ view: 'now' }, '', location.pathname + location.search);
  route();
}

/* CLOSING A LOOP FROM THE PAGE. The ledger has taken this since v0.21 and the page could not write
   it: `POST /actions` with a stage, an actor and a note, guarded by ACT_TOKEN — deliberately weaker
   than the admin token, so somebody in the house can close a loop without holding the key to
   /settings/raw. `auth_()` already sends whichever of the two Set up has stored.

   A capture is refused rather than posted. `open_asks` carries the alert ids of the node the
   capture came FROM, so a press while reading one would close somebody else's loop with this
   reader's name on it. `refresh()` guards itself the same way and for the same reason. */
/* What the node said when it refused, in its own words. The share middleware answers `{error}`;
   an HTTPException in app/main.py answers `{detail}`, a string for every refusal POST /actions
   makes. A 422 from a body the schema refused carries a list, and its messages are joined. */
async function nodeSaid(r) {
  const b = await r.json().catch(() => null);
  const d = b && (b.error || b.detail);
  if (typeof d === 'string') return d.trim();
  if (Array.isArray(d)) return d.map(x => (x && x.msg) || '').filter(Boolean).join('; ');
  return '';
}

async function didThis(form, force) {
  const btn = form.querySelector('button[type="submit"]');
  const alert_id = Number(form.getAttribute('data-alert'));
  /* Which form it is IS which stage it writes. Decide records what somebody said they would do and
     moves nothing; Act records that it was done. Two surfaces, one endpoint, and the difference is
     the whole of docs/SPEC_decide.md section 6. */
  const ack = force === 'acknowledged';
  const decision = !ack && form.classList.contains('decided');
  const stage = ack ? 'acknowledged' : decision ? 'decided' : 'acted';
  const val = n => String((form.elements[n] || {}).value || '').trim();
  const actor = val('actor') || (() => { try { return localStorage.getItem('planetai_actor') || ''; } catch (e) { return ''; } })();
  if (!ack && !val('note')) {
    say(decision ? 'Say what will be done — that sentence is the decision.'
      : 'Say what you did — that sentence is the whole of the record.', true);
    return;
  }
  btn.disabled = true;
  const seenBtn = form.closest('.ask') && form.closest('.ask').querySelector('.seen');
  if (seenBtn) seenBtn.disabled = true;
  /* A token typed into the form is kept in this browser before the request, so the press that needed it
     is also the last one that does. */
  const typedTok = val('token');
  if (typedTok) { try { localStorage.setItem('planetai_act', typedTok); } catch (e) { /* this press only */ } }
  try {
    const r = await fetch('/actions', {
      method: 'POST',
      headers: { 'content-type': 'application/json', ...auth_() },
      body: JSON.stringify({ alert_id, stage, actor, note: ack ? (val('note') || 'seen') : val('note') }),
    });
    /* THE NODE'S OWN SENTENCE FIRST. Proved on pai-clean: a browser is never `_is_local` — it
       arrives as the bridge gateway, deliberately, so trusting it would trust the whole WiFi — and
       a node at SHARE_LEVEL=off answers 403 with a better sentence than any this page could
       compose, naming the setting and where to change it. So the page adds only what the node
       cannot know: where the token comes from. */
    const said = r.ok ? '' : await nodeSaid(r);
    if (r.status === 401 || r.status === 403) {
      /* Ask for the token where the press failed, instead of naming a terminal command and leaving the
         record unwritten. A wrong token comes back here too, so the field is cleared and shown again. */
      const tf = form.querySelector('.tokfield');
      if (ack) form.hidden = false;
      if (tf) {
        if (typedTok) { try { localStorage.removeItem('planetai_act'); } catch (e) { /* nothing kept */ } }
        tf.hidden = false;
        if (tf.querySelector('input')) { tf.querySelector('input').value = ''; tf.querySelector('input').focus(); }
        say(typedTok ? 'The node did not accept that token. Check ACT_TOKEN (planetai ui prints it) and try again.'
          : 'Nothing is recorded yet: this node needs its act token from a browser. Paste ACT_TOKEN in the new '
            + `field and press ${ack ? 'Seen it' : 'Record it'} again; it is kept in this browser after that.`, true);
      } else {
        say(`${said || 'This node will not take that from here.'} \u00b7 \`planetai ui\` prints the `
          + `act token; Set up \u2192 unlock holds it.`, true);
      }
    } else if (r.status === 404) {
      say('This node has no such alert any more. Reload and look again.', true);
    } else if (r.status === 409 || r.status === 400) {
      /* The node's own sentence and nothing else. A 409 is DECISION_REQUIRED, and the node's
         sentence says what to do first; a 400 names the stages it takes. "Refused (409)" said
         neither, to the one person standing at the screen wanting to know. */
      say(said || `The node refused it (${r.status}).`, true);
    } else if (!r.ok) {
      say(said ? `${said} (${r.status})` : `The node refused it (${r.status}).`, true);
    } else {
      if (actor) { try { localStorage.setItem('planetai_actor', actor); } catch (e) { /* this press only */ } }
      if (ack) {
        say('Recorded as seen. It stays open until somebody acts on it.');
        const row = form.closest('.ask');
        if (row) {
          const sb = row.querySelector('.seen'); if (sb) sb.remove();
          const w = row.querySelector('.what');
          if (w) w.insertAdjacentHTML('afterbegin', `<span class="seenmark">\u2713 Seen${actor ? ' by ' + window.K.esc(actor) : ''}</span> `);
        }
        await refresh();
        return;
      }
      say(decision
        ? 'Decided. Nothing has moved — press "I did this" on this card when it is done.'
        : 'Recorded. The node watches what happens next.');
      if (!decision) {
        form.hidden = true;
        /* Mark the row as acted now, in place, before the redraw takes it off the list: the page used to
           say "Recorded" in a toast and leave the ask looking exactly as it had. */
        const row = form.closest('.ask');
        if (row) {
          row.classList.add('done');
          const w = row.querySelector('.what');
          const who = val('actor');
          if (w) w.insertAdjacentHTML('afterbegin', `<span class="actedmark">\u2713 Marked as acted${who ? ' by ' + window.K.esc(who) : ''}: ${window.K.esc(val('note'))}</span> `);
          const go = row.querySelector('.go'); if (go) go.hidden = true;
        }
      } else { form.reset(); }
      await refresh();
    }
  } catch (e) {
    say(`The node did not answer: ${String((e && e.message) || e)}`, true);
  } finally { btn.disabled = false; const sb2 = form.closest('.ask') && form.closest('.ask').querySelector('.seen'); if (sb2) sb2.disabled = false; }
}

/* Done, Not now and Doesn't fit on an alert EVENT. The id is the event's, not an alert's; the node
   answers with the event's own refusals, so the sentences are the ones didThis prints. Returns true
   only when the node took it, so the form can close on a yes and stay open, with what was typed, on a no. */
async function answerEvent(id, stage, actor, note) {
  try {
    const r = await fetch('/actions', {
      method: 'POST',
      headers: { 'content-type': 'application/json', ...auth_() },
      body: JSON.stringify({ event_id: Number(id), stage, actor: String(actor || ''), note: String(note || '') }),
    });
    const said = r.ok ? '' : await nodeSaid(r);
    if (r.status === 401 || r.status === 403) {
      say(`${said || 'This node will not take that from here.'} · \`planetai ui\` prints the `
        + `act token; Set up → unlock holds it.`, true);
    } else if (r.status === 404) {
      say('This node has no such event any more. Reload and look again.', true);
    } else if (!r.ok) {
      say(said || `The node refused it (${r.status}).`, true);
    } else {
      try { if (actor) localStorage.setItem('planetai_actor', String(actor)); } catch { /* no storage here */ }
      say(stage === 'acted' ? 'Recorded.' : stage === 'acknowledged'
        ? 'Not now. The node holds this for three hours, unless it reaches danger.' : 'Noted: it doesn’t fit.');
      await refresh();
      return true;
    }
  } catch (e) {
    say(`The node did not answer: ${String((e && e.message) || e)}`, true);
  }
  return false;
}

document.addEventListener('submit', async ev => {
  const form = ev.target.closest && ev.target.closest('form.did, form.decided, form.evform');
  if (!form) return;
  ev.preventDefault();
  if (FIXTURE || STATE !== 'populated') {
    say('This is a capture, not a live node — its alerts belong to the node it came from.', true);
    return;
  }
  if (!form.classList.contains('evform')) { didThis(form); return; }
  const val = n => String((form.elements[n] || {}).value || '').trim();
  if (!val('actor')) {
    /* ρ is built out of who answered. The buttons post at once only when this browser already knows a name;
       the form is where a name is given, and it does not send an anonymous one. Five nameless rows landed on
       node #1 the morning the card looked frozen — presses that worked but could not say whose they were.
       (The node still takes an empty actor from curl — a LoRa bridge may not know names — and the card says
       "somebody"; the page is where households press, so the page is where the name is insisted on.) */
    say('A name first, so the record says who.', true);
    form.elements.actor.focus();
    return;
  }
  const sub = form.querySelector('button[type="submit"]');
  if (sub) sub.disabled = true;
  try {
    /* The note is Doesn't fit's alone: one typed there and cancelled must not ride on a later Done. */
    const note = val('stage') === 'dismissed' ? val('note') : '';
    if (await answerEvent(form.dataset.ev, val('stage'), val('actor'), note)) form.hidden = true;
  } finally { if (sub) sub.disabled = false; }
});

document.addEventListener('click', ev => {
  if (ev.target.id === 'btn-arr-reset') return layoutSave(true);
  if (ev.target.id === 'btn-arr-done') return layoutSave(false);
  /* The also line and its way back. Page state, never a setting: nothing is stored or sent. */
  const hb = ev.target.closest && ev.target.closest('[data-hero]');
  if (hb) {
    window.PAI_HERO_PICK = hb.getAttribute('data-hero') || null;
    redraw();
    const lead = document.querySelector('.lead');
    if (lead && lead.getBoundingClientRect().top < 0) lead.scrollIntoView();
    return;
  }
  const sn = ev.target.closest && ev.target.closest('.ask .seen');
  if (sn) {
    if (FIXTURE || STATE !== 'populated') { say('This is a capture, not a live node — its alerts belong to the node it came from.', true); return; }
    const f = sn.parentElement.querySelector('form.did');
    if (f) didThis(f, 'acknowledged');
    return;
  }
  /* An alert event's three buttons. Done and Not now post at once when this browser has a name;
     with none, and always for Doesn't fit, the card's form opens so the name (and the note) can be said. */
  const evb = ev.target.closest && ev.target.closest('.evb');
  if (evb) {
    const card = evb.closest('.ev, .evrow'), form = card && card.querySelector('form.evform');
    if (!form) return;
    const stage = evb.getAttribute('data-stage');
    let who = '';
    try { who = localStorage.getItem('planetai_actor') || ''; } catch { /* no storage here */ }
    if (stage === 'dismissed' || !who) {
      form.hidden = false;
      form.elements.stage.value = stage;
      if (!form.elements.actor.value) form.elements.actor.value = who;
      const inst = form.querySelector('.instead');
      if (inst) inst.hidden = stage !== 'dismissed';
      if (stage !== 'dismissed') form.elements.note.value = '';
      (stage === 'dismissed' && form.elements.actor.value ? form.elements.note : form.elements.actor).focus();
      return;
    }
    if (FIXTURE || STATE !== 'populated') {
      say('This is a capture, not a live node — its alerts belong to the node it came from.', true);
      return;
    }
    evb.disabled = true;
    answerEvent(evb.getAttribute('data-ev'), stage, who, '').finally(() => { evb.disabled = false; });
    return;
  }
  const evc = ev.target.closest && ev.target.closest('form.evform .cancel');
  if (evc) { evc.closest('form.evform').hidden = true; return; }
  const go = ev.target.closest && ev.target.closest('.ask .go');
  if (go) {
    const form = go.parentElement.querySelector('form.did');
    form.hidden = !form.hidden;
    go.setAttribute('aria-expanded', String(!form.hidden));
    if (!form.hidden) form.elements.note.focus();
    return;
  }
  const dec = ev.target.closest && ev.target.closest('.decide .open');
  if (dec) {
    const f = dec.parentElement.querySelector('form.decided');
    f.hidden = !f.hidden;
    dec.setAttribute('aria-expanded', String(!f.hidden));
    if (!f.hidden) f.elements.note.focus();
    return;
  }
  const take = ev.target.closest && ev.target.closest('form.decided .take');
  if (take) {
    const f = take.closest('form.decided'), i = f.elements.note;
    i.value = i.getAttribute('data-suggest') || i.placeholder || '';
    i.focus();
    return;
  }
  const cancel = ev.target.closest && ev.target.closest('.ask form.did .cancel');
  if (cancel) {
    const form = cancel.closest('form.did');
    form.hidden = true;
    const b = form.parentElement.querySelector('.go');
    if (b) { b.setAttribute('aria-expanded', 'false'); b.focus(); }
    return;
  }
});
document.addEventListener('change', ev => {
  if (ev.target.id !== 'arr-restore' || !ev.target.value) return;
  const id = ev.target.value;
  LAYOUT.hidden = (LAYOUT.hidden || []).filter(x => x !== id);
  const s = window.PAI.sections.find(x => x.id === id);
  say(`${(s && s.title) || id} is back.`);
  route();
});

/* An in-page anchor is not a navigation. Re-rendering for one throws away the scroll position, the
   open folds and the learn panel, and rebuilds a page that did not change — so when the view is the
   same, this only goes to the anchor. */
addEventListener('hashchange', () => {
  const before = VIEW;
  readView();
  if (VIEW === before) {
    const a = (location.hash || '').replace(/^#/, '');
    const el = a && !VIEW_NAMES.has(a) ? document.getElementById(a) : null;
    if (el) { el.scrollIntoView({ block: 'start' }); return; }
  }
  route();
});
addEventListener('popstate', route);

/* A square in a stage header scrolls to that stage. It is a scroll and not a navigation, so the address keeps
   the view it is on (#historical must stay #historical). */
document.addEventListener('click', ev => {
  const a = ev.target.closest && ev.target.closest('a[data-stage-go]');
  if (!a) return;
  ev.preventDefault();
  const el = document.querySelector(`#page [data-stage="${a.getAttribute('data-stage-go')}"]`);
  if (el) { el.scrollIntoView({ block: 'start' }); const h = el.querySelector('h2'); if (h) { h.setAttribute('tabindex', '-1'); h.focus({ preventScroll: true }); } }
});

/* A ring on the wall goes to Act: the wall's view is the hash, so this leaves it for Now and then scrolls to
   the Act stage. In Simple mode there is no Act stage, and the first open ask in the lead is the next best. */
document.addEventListener('click', ev => {
  const a = ev.target.closest && ev.target.closest('a[data-act-link]');
  if (!a) return;
  ev.preventDefault();
  history.pushState({ view: 'now' }, '', location.pathname + location.search);
  route();
  setTimeout(() => {
    const el = document.querySelector('#page [data-stage="act"]') || document.querySelector('.ask') || document.getElementById('page');
    if (el) el.scrollIntoView({ block: 'start' });
  }, 80);
});

/* EVERY CONTROL ON THIS PAGE IS A QUERY LINK, AND EVERY ONE OF THEM RELOADED THE DOCUMENT.
 *
 * The dial, a cell, the variable selector, the base layer, "show all" — all of them are
 * `<a href="?…">`, which the browser answers by throwing the page away and fetching index.html,
 * dashboard.js, dashboard.css, the frozen layer, the ground, and then /issues, /health, /settings,
 * /rho, /trust, /forecast and /earth all over again. Seconds of waiting, on a LAN, to be handed
 * the same readings and re-file them under different cells.
 *
 * Nothing about that was necessary. route() has always re-rendered from globals already in memory
 * and fetched nothing — it is how the view buttons have worked all along — and main() rebuilds its
 * ctx from location.search on every call. So a press only ever needed to put the new query in the
 * URL and call route(). That is this handler, and turning the dial is now a render.
 *
 * What is deliberately NOT intercepted, because each is a different intention: a modified click
 * (cmd, ctrl, shift, alt, or the middle button) which the reader is asking to open elsewhere; a
 * link with a target, which says where it wants to go; and any href that is not a query on this
 * same document — a station's link to its own public page must leave, and does.
 */
document.addEventListener('click', ev => {
  if (ev.defaultPrevented || ev.button !== 0 || ev.metaKey || ev.ctrlKey || ev.shiftKey || ev.altKey) return;
  const a = ev.target.closest && ev.target.closest('a[href]');
  if (!a || a.target || a.hasAttribute('download')) return;
  const href = a.getAttribute('href') || '';
  if (!href.startsWith('?')) return;
  ev.preventDefault();
  /* The hash carries the view, and a query link keeps whichever view it was pressed in — pressing
     the dial on Network must not land on Now. qlink() already appends the current hash; a bare
     '?…' from link() does not, so it is kept here rather than dropped. */
  const url = href.includes('#') ? href : href + (location.hash || '');
  if (url === location.search + location.hash) return;   // the stop already under the finger
  /* route() scrolls to the top, which is right for a view change and wrong for a control: a reader
     who presses "show all" half way down the station list wants to still be looking at it. */
  const y = window.scrollY;
  history.pushState({ view: VIEW }, '', url);
  route();
  window.scrollTo(0, y);
});
document.addEventListener('click', ev => {
  if (ev.target.id === 'btn-back') {
    history.pushState({ view: 'now' }, '', location.pathname + location.search);
    return route();
  }
  const rb = ev.target.closest && ev.target.closest('.register button');
  if (rb && rb.dataset.register) {
    ev.preventDefault();
    try { localStorage.setItem(REGISTER_KEY, rb.dataset.register); } catch (e) { /* see register() */ }
    /* Not a re-render: the register is one attribute and every rule under it is already written, so
       toggling in place restyles the whole page without scrolling it back to the top. */
    applyRegister(VIEW);
    window.K.repaintFigs();
    rb.parentNode.querySelectorAll('button').forEach(x => {
      const on = x === rb;
      x.classList.toggle('on', on);
      x.setAttribute('aria-pressed', String(on));
    });
    return;
  }
  const ra = ev.target.closest && ev.target.closest('[data-reask]');
  if (ra) {
    ev.preventDefault();
    askAgain();
    return;
  }
  const mb = ev.target.closest && ev.target.closest('.seg.mode button');
  if (mb && mb.dataset.mode) {
    ev.preventDefault();
    try { localStorage.setItem(MODE_KEY, mb.dataset.mode); } catch (e) { /* see register() */ }
    /* Learn opens the pane: a mark's quote lands in the thread, and the reader asks after it. */
    if (mb.dataset.mode === 'learn' && window.PAI_ASK) window.PAI_ASK.learnOn();
    /* Unlike the register, this one IS a re-render: which sections draw is the whole of the mode,
       and that is decided in render(), not in a stylesheet. */
    return route();
  }
  const b = ev.target.closest && ev.target.closest('nav.views button, .wall .exit');
  if (!b || !b.dataset.view) return;
  ev.preventDefault();
  /* pushState and not `location.hash =`: assigning the hash makes the browser jump to whatever
     element carries that id, which is the bug the page this replaces fixed the same way. */
  const v = b.dataset.view;
  history.pushState({ view: v }, '', v === 'now' ? location.pathname + location.search : '#' + v);
  route();
});

/* ------------------------------------------------------------------ and go */
/* ---------------------------------------------------------------- the readings keep up
 *
 * THE PAGE STOPPED UPDATING IN THE PHASE 2 REWRITE. v0.53 ended its boot with
 * `setInterval(refresh, 20000)` and the rewrite did not carry it, so from v0.54 to v0.57 the only
 * repeating timer in this file was the wall stepping its own dial. boot() fetched nine routes once
 * and never again — while the page went on showing its `live` pill and its "as of" stamp over
 * figures that had stopped moving the moment the tab opened. An unattended wall screen was not
 * merely stale; it was asserting freshness it did not have. Reported 18 September 2026.
 *
 * WHAT IS RE-FETCHED, AND WHAT IS NOT. /issues, /health and /rho move on the node's own poll.
 * /settings, /place/geojson, /earth, /sensors and /cells do not move on that cadence — a keeper
 * changing a setting or a pack fetching a new satellite year is a reload's business, not a poll's —
 * and fetching them every cycle would be three quarters of the traffic for none of the change. The
 * old page refreshed everything; this does not.
 *
 * THE CADENCE IS THE NODE'S. POLL_SECONDS, read from GET /settings, is how often the node itself
 * goes and looks: 300 s on node #1. Asking more often than that fetches the same answer again, so
 * the page asks at the node's own rate and not at a number typed here. Clamped either side because
 * a node with POLL_SECONDS=1 must not turn every open page into a load generator.
 *
 * A RE-RENDER IS NOT A RE-FETCH. route() redraws from globals and asks the node nothing — that is
 * v0.56's whole dial fix. So this fetches first, re-binds through the same bind() and initKit()
 * boot uses, and only then re-renders. PAI_LOAD is deliberately NOT re-run: the sections are
 * already registered and the contract rejects a second registration of the same id.
 *
 * AND IT DOES NOT FIGHT THE READER. It holds off while a tab is hidden, while a Set up group has an
 * edit nobody has saved, and on the synthetic ?state= pages. A committed fixture is never
 * refreshed at all: it cannot change, and the measuring rig replays one.
 */
const REFRESH_FLOOR_S = 20, REFRESH_CEIL_S = 600, REFRESH_DEFAULT_S = 60;
let REFRESH_TIMER = null;

function refreshEvery() {
  const rows = ((window.SETTINGS_RAW || {}).bootstrap) || [];
  const n = Number(((rows.find(r => r.key === 'POLL_SECONDS') || {}).value) || '');
  const secs = Number.isFinite(n) && n > 0 ? n : REFRESH_DEFAULT_S;
  return Math.min(REFRESH_CEIL_S, Math.max(REFRESH_FLOOR_S, Math.round(secs))) * 1000;
}

/* What the page says when a poll does not come back. The figures on screen stay — they were true
 * when they were read, and blanking them would lose the last thing the node actually said — but the
 * stamp stops calling them live and says how long ago they were read instead. */
window.STALE = null;

async function refresh() {
  if (FIXTURE || STATE !== 'populated') return;         // a snapshot cannot change
  if (document.hidden) return;                          // nobody is looking
  /* Reconnect, and only reconnect. The pill has dropped `live` and this is the read that may bring
     it back, which is a thing worth showing; the five minutes of polls before it were not, and
     covering the page for each of them would make a working node look broken. */
  const wasStale = !!window.STALE;
  const mine = wasStale && !ASKING.up();
  if (mine) ASKING.open('The node stopped answering. Asking again');
  if (VIEW === 'setup' && window.PAI_SETUP && window.PAI_SETUP.dirty && window.PAI_SETUP.dirty()) return;
  let issues, health, rho;
  try {
    [issues, health] = await Promise.all([api('/issues'), api('/health')]);
  } catch (e) {
    window.STALE = { since: (window.STALE && window.STALE.since) || Date.now(),
      why: String((e && e.message) || e) };
    redraw({ keepGround: true });                       // the stamp has something new to say
    if (mine) ASKING.close();                           // still not answering: give the page back
    return;
  }
  /* ρ is the node measuring itself and is the slowest of the three. It failing is not a reason to
     throw away a good reading of the air, so the last one stands and the page says nothing new. */
  rho = await api('/rho').catch(() => (window.SNAP || {}).rho || null);
  /* The strips move by an hour at a time, so the days are read again at most every 15 minutes, not on every poll. */
  if (Date.now() - (window.DAYS_AT || 0) > 15 * 60e3) {
    window.DAYS = await api('/issues/days?days=7').catch(() => window.DAYS || null);
    window.DAYS_AT = Date.now();
  }
  window.STALE = null;
  ASKING.landed(issues);
  bind(issues, health, rho);
  initKit();
  initGeometry();
  redraw({ keepGround: true });
  if (mine) ASKING.close();
}

/* ---------------------------------------------------------------- the year players
 *
 * Restored from v0.53, which the Phase 2 rewrite dropped: the Play button, the slider and the year
 * label were rendered on every satellite record and nothing had listened to any of them since
 * v0.54. Dead controls, for five releases.
 *
 * The cadence is the frozen layer's own --motion-satellite-year, which is 4s and goes to 0s under
 * prefers-reduced-motion. So reduced motion is not a second code path here: the token says zero,
 * the loop does not start, the record stands on its most recent year and the button says so.
 *
 * One timer per player, cleared before it is replaced, so a re-render — and this page re-renders on
 * every poll — cannot leave a second loop running behind the first. That is how a page ends up
 * flickering between two years at once.
 */
const SAT_LOOPS = new Map();

function wireSat(root) {
  /* Was `parseFloat(...) || 0` and multiplied by 1000 below, which is right only while this token
     stays in seconds. msToken reads the unit, so a layer that writes `4000ms` one day does not
     quietly turn this into a four-second page into a four-millisecond flicker. */
  const secs = window.K.msToken('--motion-satellite-year') / 1000;
  for (const [el, t] of SAT_LOOPS) { if (!root.contains(el)) { clearInterval(t); SAT_LOOPS.delete(el); } }
  root.querySelectorAll('.satplay[data-years]').forEach(el => {
    if (SAT_LOOPS.has(el)) { clearInterval(SAT_LOOPS.get(el)); SAT_LOOPS.delete(el); }
    const years = (el.dataset.years || '').split(',').filter(Boolean);
    const imgs = [...el.querySelectorAll('[data-sat="frame"]')];
    const label = el.querySelector('[data-sat="label"]');
    const slider = el.querySelector('[data-sat="slider"]');
    const play = el.querySelector('[data-sat="play"]');
    if (years.length < 2) { if (play) { play.disabled = true; play.textContent = 'one year'; } return; }
    let i = years.length - 1;
    const show = () => {
      imgs.forEach((im, n) => im.classList.toggle('on', n === i));
      if (label) label.textContent = years[i];
      if (slider) slider.value = String(i);
    };
    const stop = () => {
      const t = SAT_LOOPS.get(el);
      if (t) { clearInterval(t); SAT_LOOPS.delete(el); }
      if (play) { play.textContent = secs ? 'Play' : 'Motion off'; play.setAttribute('aria-pressed', 'false'); }
    };
    const run = () => {
      if (!secs) return;                       // reduced motion: stands on the most recent year
      SAT_LOOPS.set(el, setInterval(() => { i = (i + 1) % years.length; show(); }, secs * 1000));
      if (play) { play.textContent = 'Pause'; play.setAttribute('aria-pressed', 'true'); }
    };
    if (play) play.onclick = () => (SAT_LOOPS.has(el) ? stop() : run());
    if (slider) slider.oninput = () => { stop(); i = +slider.value; show(); };
    show();
    if (secs) run(); else stop();
  });
}

/* Re-render without throwing the reader out of their place: the scroll position and every open fold
 * survive, because a poll arriving while somebody is reading a note must not close it.
 *
 * AND WITHOUT ASKING A TILE SERVER ANYTHING. `keepGround` carries the whole of that. The ground is a
 * grid of <img> elements, and innerHTML replacement destroys and recreates them, which Chromium
 * answers by going back to the network — measured over CDP, twelve requests to tiles.maps.eox.at on
 * every redraw, none of them served from cache, despite the tiles being cacheable for a week. Before
 * the refresh loop that cost twelve requests per page load. With a poll every 300 s it would have
 * been about 3,500 a day from every open page, each one telling that server which square of the
 * planet this house is looking at. The Phase 2 rule is that a press may only ever REDUCE what leaves
 * the house; a poll quietly multiplying it by three hundred is the same rule broken from the other
 * side.
 *
 * So a data refresh keeps the ground it already has. It is allowed to, and only it is: the drawing
 * is a function of the cell, the resolution, the base and the register, every one of which lives in
 * the URL — and a poll does not touch the URL. A press does, and a press passes nothing here and
 * gets a fresh ground, which is exactly right. */
function redraw(opts) {
  const y = window.scrollY;
  const open = [...document.querySelectorAll('details[open]')].map(d => d.id).filter(Boolean);
  const ground = (opts && opts.keepGround) ? document.querySelector('#ground-figure') : null;
  /* The flag is up only across route(), so nothing else can ever see a hollow ground: the section
     reads it, draws the empty figure, and it is down again before the swap. */
  if (ground) window.KEEP_GROUND = true;
  try { route(); } finally { window.KEEP_GROUND = false; }
  if (ground) {
    const fresh = document.querySelector('#ground-figure');
    if (fresh && fresh !== ground) fresh.replaceWith(ground);
  }
  for (const id of open) { const d = document.getElementById(id); if (d) d.open = true; }
  window.scrollTo(0, y);
}

/* The loop's own handle, in the idiom this file already uses for PAI_SETUP, PAI_SETTINGS and WALL.
 * A poll that only ever fires on a 300-second timer cannot be tested, and untested is exactly how
 * the last one was lost for four releases — tests/visual/measure.mjs drives `now()` and watches what
 * the page asks the node for. It is also the honest way for a wall to force a read after somebody
 * has fixed whatever was wrong with the node. */
window.PAI_REFRESH = { now: () => refresh(), every: () => refreshEvery(), stale: () => window.STALE };

function startRefresh() {
  if (REFRESH_TIMER) clearInterval(REFRESH_TIMER);
  if (FIXTURE || STATE !== 'populated') return;
  REFRESH_TIMER = setInterval(refresh, refreshEvery());
  /* A tab that was hidden for an hour comes back to an hour-old page and should not have to wait
     out another full interval to be told so. */
  document.addEventListener('visibilitychange', () => { if (!document.hidden) refresh(); });
}

/* The header's ↻. Not `refresh()` with an overlay bolted on: the difference between this and a poll
   is the whole of the rule, so it is a function of its own with the overlay in it, and refresh()
   stays the thing the timer calls and draws nothing over the page. */
async function askAgain() {
  if (ASKING.up()) return;
  ASKING.open('Asking the node again', true);
  try { await refresh(); }
  finally { ASKING.close(); }
}

ASKING.open('Asking the node', true);
boot().then(() => { init(); route(); startRefresh(); ASKING.close(); }).catch(async e => {
  ASKING.close();
  if (e && e.refused) {
    SAID = e.refused;
    const h = await api('/health').catch(() => ({}));
    window.NODE_NAME = h.node; window.NODE_CITY = h.city;
    addEventListener('hashchange', drawRefused);
    document.addEventListener('click', ev => {
      const b = ev.target.closest && ev.target.closest('nav.views button');
      if (!b || !b.dataset.view) return;
      ev.preventDefault();
      const v = b.dataset.view;
      history.pushState({ view: v }, '', v === 'now' ? location.pathname + location.search : '#' + v);
      drawRefused();
    });
    drawRefused();
    return;
  }
  /* Through chrome() and the wall branch, the same two shapes drawRefused() draws and for the same
     reason: a reader whose node did not answer has lost the whole page, and the nav is how they
     reach Set up to do something about it. A bare paragraph took that away exactly when it was
     needed. /health is asked separately because it answers at every share level and often answers
     when nothing else does; when it does not, the header carries the product's own name. */
  const said = `This node did not answer: ${String((e && e.message) || e).replace(/[<>&]/g, '')}. `
    + `A failure is not an answer, so nothing is cached; reload to try again.`;
  const h = await api('/health').catch(() => ({}));
  const el = document.getElementById('page');
  const v = (location.hash || '').replace(/^#/, '')
    || new URLSearchParams(location.search).get('view') || 'now';
  applyRegister(v);
  if (v === 'wall') {
    document.body.className = 'wall wallview';
    el.innerHTML = `<div class="wallbox"><h1 class="vh">${window.K.esc(h.node || 'PLANETAI')}`
      + ` · no answer</h1><p class="note">${said}</p></div>`;
  } else {
    el.innerHTML = chrome(h.node, h.city, v) + `<div class="wrap"><p class="note">${said}</p></div>`;
  }
});

})();

/* ================================================================= the Set up pane — ported from app/static/dashboard.js at 685fe1a ==== */
/* the Set up pane: lifted from the page this replaces, at 685fe1a, with as few edits as the move
 * requires.
 *
 * WHY IT IS HERE. The modular shell's Set up view is the section registry; this is
 * the working surface the page before it carried. Without it a keeper cannot put a token into the
 * page, so nothing can be written — the tiles switch included. It is ported, not rewritten:
 * tests/test_settings.py, test_config.py, test_shipped.py and test_share.py read this code out of
 * the file, and they read the same names they always did.
 *
 * THE FOUR EDITS THE MOVE REQUIRED, and no others:
 *   1  the markup is rendered into #page by the Set up view rather than sitting in index.html, so
 *      every lookup is a querySelector under #page. tools/check_ui.py's first rule compares
 *      getElementById against index.html's own markup, and a rendered id can never be in it.
 *   2  the two words it took from the old renderer's language table (mkCtx().w) are a map of their
 *      own here, in the same three languages.
 *   3  refresh() became route(), which is this page's re-render.
 *   4  Arrange's own restore menu came out of the click and change handlers with the plan card's
 *      layer toggles: neither is on this page, and both belong to the view this pane is not.
 */
(function () {
'use strict';

const q = sel => document.querySelector('#page ' + sel);
const qa = sel => document.querySelectorAll('#page ' + sel);
const esc = s => window.K.esc(s);
const auth_ = () => window.PAI_AUTH();
const route = () => window.PAI_ROUTE();

/* The two words this pane took from the old renderer's language table. Three languages, as before;
 * the household's own comes off GET /health and window.K.LOC carries it. */
/* NET carries the words the network figure speaks. They lived in this table until the modular page
 * replaced it, and are lifted back from v0.53 unchanged, in the three languages the node delivers
 * every sentence in. A figure that is English-only on a node answering in Indonesian is the S-01
 * fault the September review closed; re-writing this copy here would have re-opened it. */
const WORDS = {
  en: { leavesMachine: 'leaves this machine',
    openOnAnotherScreen: 'Open this on another screen in the house:',
    net: { cellsN: '{n} of 20', cellsOut: 'Index cells', home: 'home', kept: '{n} readings kept, none of them leave', leaves: 'What leaves this house', leavesShort: 'what leaves', means: 'hourly means', model: 'model', models: 'the models', models_: 'models', parentNowhere: 'nowhere yet', reads: 'What this node reads', rhoN: '{closed} of {total}', rhoOut: 'answered alerts', sensor: 'sensor', sensors: 'sensors', station: 'public station', stations: 'public stations', street: 'the ring', sub: 'Readings stay here. What travels up to the community node is hourly means, Index cells and \u03c1: enough to see the place, never enough to see the house.', title: 'This house is one node of a much larger instrument.', yours: 'your sensors' }, },
  id: { leavesMachine: 'keluar dari mesin ini',
    openOnAnotherScreen: 'Buka ini di layar lain di rumah:',
    net: { cellsN: '{n} dari 20', cellsOut: 'sel Indeks', home: 'rumah', kept: '{n} bacaan disimpan, tidak satu pun keluar', leaves: 'Yang keluar dari rumah ini', leavesShort: 'yang keluar', means: 'rata-rata per jam', model: 'model', models: 'model', models_: 'model', parentNowhere: 'belum ke mana-mana', reads: 'Yang dibaca node ini', rhoN: '{closed} dari {total}', rhoOut: 'peringatan dijawab', sensor: 'sensor', sensors: 'sensor', station: 'stasiun publik', stations: 'stasiun publik', street: 'sekitarnya', sub: 'Bacaan tetap di sini. Yang naik ke node komunitas adalah rata-rata per jam, sel Indeks dan \u03c1: cukup untuk melihat tempatnya, tidak pernah cukup untuk melihat rumahnya.', title: 'Rumah ini satu node dari instrumen yang jauh lebih besar.', yours: 'sensor Anda' }, },
  es: { leavesMachine: 'sale de esta máquina',
    openOnAnotherScreen: 'Abre esto en otra pantalla de la casa:',
    net: { cellsN: '{n} de 20', cellsOut: 'celdas del \u00cdndice', home: 'casa', kept: '{n} lecturas guardadas, ninguna sale', leaves: 'Lo que sale de esta casa', leavesShort: 'lo que sale', means: 'medias horarias', model: 'modelo', models: 'los modelos', models_: 'modelos', parentNowhere: 'a ning\u00fan sitio todav\u00eda', reads: 'Lo que lee este nodo', rhoN: '{closed} de {total}', rhoOut: 'alertas respondidas', sensor: 'sensor', sensors: 'sensores', station: 'estaci\u00f3n p\u00fablica', stations: 'estaciones p\u00fablicas', street: 'los alrededores', sub: 'Las lecturas se quedan aqu\u00ed. Lo que sube al nodo de la comunidad son medias horarias, celdas del \u00cdndice y \u03c1: suficiente para ver el lugar, nunca suficiente para ver la casa.', title: 'Esta casa es un nodo de un instrumento mucho m\u00e1s grande.', yours: 'tus sensores' }, },
};
const W = () => WORDS[(window.K || {}).LOC] || WORDS.en;
window.W = W;

/* The skeleton, verbatim from the page this replaces (app/static/index.html at 685fe1a) minus its
 * own <section class="view"> and .wrap, which the shell draws. Every id the measuring rig and the
 * suites drive is the id it was: #gate, #tok, #acttok, #btn-unlock, #setup-body, #tabs, #pane. */
function markup() {
  return `<h2 class="t">How this node was told to behave.</h2>`
    + `<p class="sub">Everything here is live within about twenty seconds; nothing needs a restart. `
    + `A blank field hands the setting back to <code>.env</code>. A value set here overrides the `
    + `same key in it.</p>`
    + `<div class="gate card" id="gate">`
    + `<h3 class="t">Unlock</h3>`
    + `<p class="sub">Changing settings needs the admin token. <code>planetai ui</code> on the node `
    + `prints it, and the weaker one below it.</p>`
    + `<label class="sub" for="tok">Admin token</label>`
    + `<div class="reveal"><input type="password" id="tok" placeholder="admin token" autocomplete="off">`
    + `<button type="button" data-reveal="tok" aria-pressed="false">Show</button></div>`
    + `<p class="sub" id="acttok-help">Or the token for closing a loop only — it records that `
    + `someone acted, and reads the sensors, but cannot change a setting or read a secret.</p>`
    + `<label class="sub" for="acttok">Token for closing a loop</label>`
    + `<div class="reveal"><input type="password" id="acttok" placeholder="token for closing a loop"`
    + ` autocomplete="off" aria-describedby="acttok-help">`
    + `<button type="button" data-reveal="acttok" aria-pressed="false">Show</button></div>`
    + `<div class="row mt"><button class="btn" id="btn-unlock">Unlock</button>`
    + `<button class="btn ghost" id="btn-back">Back</button></div></div>`
    + `<div class="setup" id="setup-body" hidden>`
    + `<nav class="tabs" id="tabs"></nav>`
    + `<h3 class="t" id="ptitle"></h3>`
    + `<p class="sub" id="pblurb"></p>`
    + `<p class="sub addr" id="paddr" hidden></p>`
    + `<div id="pane"></div>`
    + `<div class="savebar"><button class="btn" id="btn-save">Save changes</button>`
    + `<span class="sub" id="savenote">Live within about twenty seconds.</span></div></div>`;
}

function toast(msg, bad) {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.classList.toggle('bad', !!bad);
  t.classList.add('on');
  setTimeout(() => t.classList.remove('on'), 4200);
}

const GROUPS = {
  basics: ['Basics', "This place: what it watches, in order, what kind of node it is, its language and how its page opens. Its name, city, position and time zone are read once at start: change them in .env on the node, then run planetai restart."],
  sources: ['Sources', "Sensors and data: what the node reads \u2014 your sensors, your account, and the public stations and portals around you. Sources that come as packs (Xiaomi purifiers, ThingData, forecasts) are switched on and set under Packs."],
  alerts: ['Alerts', "Alerts and reports: reports at the hours you choose, in this node's own time zone; between them, only what you asked to be interrupted for; and how a loop is closed."],
  model: ['Model', "Ask and model: which model answers, on the dashboard's ask pane and on Telegram alike. The strongest one the node can reach is used, and its keys are under Keys."],
  packs: ['Packs', 'Which packs load, each with its own settings in its card. Code packs stay off until you allow them; read one before you do.'],
  keys: ['Keys', 'Every secret in one place: the Telegram bot token, the model keys, and the tokens other machines present to this one. Each is masked once saved and never shown again.'],
  sharing: ['Sharing', 'Sharing and network: who may read this node, and everything it sends or announces beyond this machine. Readings stay here; hourly means, Index cells and \u03c1 travel.'],
  system: ['System', 'Tuning numbers, the layout Arrange mode saves, and what is read once at start: the port, extra containers, backups, the poll interval. Change those in .env on the node, then run planetai restart.'],
};
let GROUP = null, DESC = null, PACKS = [];
// Whether this pane holds an edit nobody has saved. Changing tab used to re-render the pane from the
// last describe(), so a typed value vanished with no warning and no way back.
let DIRTY = false;
/* What every field in the open group read when it was drawn. A save sends only what differs from it.
 * It used to send every field, so a form opened at 18:00 and saved at 18:31 to change AGENT_REMOTE_URL
 * also wrote back the AGENT_PREFER it had drawn: node #1, 26 September 2026, `strongest` over the
 * `private` somebody had set at 18:07, and the ask pane sent a question online. */
let LOADED = {};
// What the pack switches read when the packs group was drawn.
let DRAWN_PACKS = '';

/* The pack switches as a PACKS_ENABLED value: blank when every pack is on. */
function packSwitches() {
  const all = [...qa('[data-pack]')];
  const on = all.filter(c => c.classList.contains('on')).map(c => c.dataset.pack);
  return on.length === all.length ? '' : on.join(',');
}

/* What the open group's fields say, key by key, read the same way when it is drawn and when it is
 * saved, so the difference is exactly what somebody changed. A secret left blank says nothing.
 *
 * The packs group used to return PACKS_ENABLED from the switches and nothing else, so its own
 * fields — PACKS_ALLOW_CODE and every key a pack declares — were drawn and never sent: a keeper
 * could not allow code packs or set a pack's key from here, though `planetai config` offers both.
 * PACKS_ENABLED has two controls there, the switches and the text field; the switches win when
 * somebody moved one, and otherwise the field says what it says. */
function formValues() {
  const out = {};
  qa('[data-key]').forEach(el => {
    const k = el.dataset.key;
    if (el.dataset.bool) out[k] = el.classList.contains('on') ? '1' : '0';
    else if (el.type === 'password') { if (el.value) out[k] = el.value; }
    else out[k] = el.value;
  });
  if (GROUP === 'packs' && packSwitches() !== DRAWN_PACKS) out.PACKS_ENABLED = packSwitches();
  return out;
}

/* The keys the node now holds differently from the describe() the form was drawn from. */
function movedSince(before, after, keys) {
  const row = (d, k) => ((d && d.runtime) || []).find(r => r.key === k) || {};
  return keys.filter(k => row(before, k).value !== row(after, k).value || row(before, k).set !== row(after, k).set);
}

/* The groups this node has, in the order it declares them, with bootstrap last because it is the
 * one that is read at start and cannot be changed from here. */
function groupsOf(desc) {
  const seen = [];
  for (const r of (desc.runtime || [])) if (!seen.includes(r.group)) seen.push(r.group);
  /* The settings read once at start are shown read-only in the tab they belong to (settings.BOOTSTRAP_GROUP),
     not in a tab of their own: a keeper looks for the time zone under Basics, not under "Bootstrap". */
  for (const b of (desc.bootstrap || [])) if (b.group && !seen.includes(b.group)) seen.push(b.group);
  return seen;
}
const groupTitle = g => (GROUPS[g] || [g.charAt(0).toUpperCase() + g.slice(1)])[0];
const groupBlurb = g => (GROUPS[g] || [])[1]
  || 'This node declares this group and the dashboard has no words for it yet. planetai config shows the same keys.';

const BOOLS = /^(BAD_ENABLED|OPENMETEO_ENABLED|SENSOR_INDOOR|MESH_ALERTS|HA_DISCOVERY|EXPORT_ENABLED|IPFS_PUBLISH|QUIET_HOURS|BAD_INCLUDE_INDOOR|PACKS_ALLOW_CODE)$/;

function unlock() {
  const t = q('#tok').value.trim();
  if (t) localStorage.setItem('planetai_admin', t);
  const a = q('#acttok').value.trim();
  if (a) localStorage.setItem('planetai_act', a);
  loadSetup();
}
function lock() {
  localStorage.removeItem('planetai_admin');
  localStorage.removeItem('planetai_act');
  loadSetup();
}

async function loadSetup() {
  const tok = localStorage.getItem('planetai_admin') || '';
  try {
    DESC = await fetch('/settings', { headers: tok ? { authorization: 'Bearer ' + tok } : {} }).then(r => r.json());
    PACKS = await fetch('/packs', { headers: auth_() }).then(r => r.ok ? r.json() : []).catch(() => []);
  } catch (e) { toast('The node did not answer.', true); return; }
  // values stay masked without the token, so a wrong one shows here and not at save time
  if (tok && !DESC.unlocked) { toast('That token is not right.', true); lock(); return; }
  const unlocked = !!tok && DESC.unlocked;
  q('#gate').hidden = unlocked;
  q('#setup-body').hidden = !unlocked;
  if (!unlocked) return;

  const groups = groupsOf(DESC);
  // A tab that was open when the node's groups changed under it, or a first load: take the first.
  if (!groups.includes(GROUP)) GROUP = groups[0] || null;
  if (!GROUP) { q('#pane').innerHTML = `<p class="note">This node declares no settings.</p>`; return; }
  q('#tabs').innerHTML = groups
    .map(g => `<button type="button" class="${g === GROUP ? 'on' : ''}" data-group="${esc(g)}">${esc(groupTitle(g))}</button>`).join('')
    + `<span class="acts"><button type="button" class="btn ghost" data-lock="1">Lock</button></span>`;
  q('#ptitle').textContent = groupTitle(GROUP);
  q('#pblurb').textContent = groupBlurb(GROUP);
  // The address another screen in the house should open. `planetai ui` prints it in a terminal; the
  // interface the keeper is already looking at never did, so the path to a wall screen ran through
  // the CLI. location.host is the address THIS reader used, which is the one that works.
  const addr = q('#paddr');
  if (addr) {
    const show = GROUP === 'basics';
    addr.hidden = !show;
    if (show) addr.textContent = `${W().openOnAnotherScreen} http://${location.host}/`;
  }

  const pane = q('#pane');
  /* Read once at start, so read-only here and never sent: these fields carry no data-key. */
  const boot = (DESC.bootstrap || []).filter(b => (b.group || 'system') === GROUP).map(b =>
    `<div class="field"><div><label for="set-${esc(b.key)}">${esc(b.label)}<span class="src">read at start</span></label>`
    + `<div class="help">${esc(b.key)} \u00b7 edit .env on the node, then run planetai restart</div></div>`
    + `<div><input id="set-${esc(b.key)}" type="text" readonly value="${esc(b.value || '')}"`
    + ` placeholder="not set"></div></div>`).join('');
  /* The pack switches are an EXTRA, never a replacement. This branch used to render them and return,
     so PACKS_ENABLED and PACKS_ALLOW_CODE — the two settings the group actually declares, and the
     two `planetai config` offers under `packs` — could not be reached from the dashboard at all. A
     keeper who read the CLI and then went looking for them in Set up did not find them. Every group
     now renders every key the node declares, and the switches sit above the two they write. */
  const enabled = ((DESC.runtime || []).find(r => r.key === 'PACKS_ENABLED') || {}).value || '';
  const only = enabled ? enabled.split(',').map(x => x.trim()) : null;
  /* One card per pack: its switch, what it is, and its own settings under it. A pack whose keys the node
     publishes but which /packs does not list (it is off) still gets its card, without a switch to draw. */
  const packCard = (p, fields, switchable) => `<section class="packcard">`
    + `<div class="pack">${switchable ? `<button type="button" role="switch" class="switch ${!only || only.includes(p.id) ? 'on' : ''}"`
      + ` aria-checked="${!only || only.includes(p.id)}" aria-labelledby="pack-${esc(p.id)}"`
      + ` data-pack="${esc(p.id)}"><span class="tr"></span></button>` : '<span></span>'}`
    + `<div><b id="pack-${esc(p.id)}">${esc(p.name || p.id)}</b>${p.kind ? ` <span class="tag">${esc(p.kind)}</span>` : ''}`
    + (p.domain ? ` <span class="tag">${esc(p.domain)}</span>` : '')
    + `<div class="help">${esc(p.description || '')}</div></div></div>${fields}</section>`;
  /* One field. Every control here carries a name a screen reader can read and a label a pointer can
   * hit, which none of them did: axe found `label` critical eight times in the alerts group alone,
   * `button-name` critical on every toggle and `select-name` on the one select. A household keeper
   * setting up a node by voice or by keyboard heard "button" and could not tell on from off.
   *
   * A key that declares CHOICES gets them. app/settings.py has always refused a value outside them —
   * that is where `'5' is not a value REPORT_EVERY accepts` comes from — so the page was letting
   * somebody type a value the node had already decided to reject. The node knows; the node says;
   * the page draws the answer.
   */
  const rows = (DESC.runtime || []).filter(r => r.group === GROUP);
  const field = r => {
    const id = 'set-' + r.key, lbl = 'lbl-' + r.key;
    const src = `<span class="src">${r.source === 'gui' ? 'set here · overrides .env' : r.source === 'env' ? 'from .env' : 'default'}</span>`;
    // The node says which settings change what leaves this machine (settings.OUTWARD). They were in
    // the same box as "Coast: max distance to sea, km": the one that decides whether the whole read
    // API answers a stranger on the WiFi looked exactly like the one that says how far the sea is.
    const out = r.outward ? `<span class="tag out">${esc(W().leavesMachine)}</span>` : '';
    const left = `<div><label id="${lbl}" for="${id}">${esc(r.label)}${out}${src}</label>`
      + `<div class="help" id="help-${r.key}">${esc(r.help)}</div></div>`;
    // Where the node's refusal is written when it refuses. Empty until then, and aria-live so a
    // reader who is not looking at this field still hears why the save did not take.
    const err = `<p class="err" id="err-${r.key}" role="alert" hidden></p>`;
    if (BOOLS.test(r.key)) {
      const on = r.value === '1';
      return `<div class="field">${left}<div><button type="button" role="switch" aria-checked="${on}"`
        + ` aria-labelledby="${lbl}" aria-describedby="help-${r.key}" id="${id}" class="switch ${on ? 'on' : ''}"`
        + ` data-key="${esc(r.key)}" data-bool="1"><span class="tr"></span></button>${err}</div></div>`;
    }
    const opts = r.key === 'ALERT_LOCALE'
      ? [['en', 'English'], ['id', 'Bahasa Indonesia'], ['es', 'Español']]
      : (r.choices || []).map(v => [v, v]);
    if (opts.length) {
      // A key at its own default has chosen nothing, and saying "6" here would be the page inventing
      // a fact it does not have: the defaults live at the call sites, not in RUNTIME. So it offers
      // the values and says plainly that none of them is set.
      const unset = !r.set;
      return `<div class="field">${left}<div><select id="${id}" aria-describedby="help-${r.key}" data-key="${esc(r.key)}">`
        + (unset ? `<option value=""${' selected'}>— not set; the node's own default applies —</option>` : '')
        + opts.map(([v, l]) => `<option value="${esc(v)}"${r.value === v ? ' selected' : ''}>${esc(l)}</option>`).join('')
        + `</select>${err}</div></div>`;
    }
    return `<div class="field">${left}<div><input id="${id}" aria-describedby="help-${r.key}" data-key="${esc(r.key)}"`
      + (r.secret
        ? ` type="password" placeholder="${r.set ? 'Set — type to replace' : 'Not set'}"`
        : ` type="text" value="${esc(r.value)}" placeholder="${r.source === 'default' ? "not set; the node's own default applies" : ''}"`)
      + ` autocomplete="off">${err}</div></div>`;
  };
  let body = rows.filter(r => !r.pack).map(field).join('');
  if (GROUP === 'packs') {
    const listed = PACKS.map(p => p.id);
    body += PACKS.map(p => packCard(p, rows.filter(r => r.pack === p.id).map(field).join(''), true)).join('')
      + [...new Set(rows.filter(r => r.pack && !listed.includes(r.pack)).map(r => r.pack))]
        .map(id => packCard({ id }, rows.filter(r => r.pack === id).map(field).join(''), false)).join('');
  }
  body += boot;              /* read-only, so after what can be set: Basics still opens on what this place watches */
  pane.innerHTML = body || `<div class="empty">Nothing to set in this group.</div>`;
  DRAWN_PACKS = packSwitches();
  LOADED = formValues();
  DIRTY = false;
}

async function saveSettings() {
  const tok = localStorage.getItem('planetai_admin');
  const now = formValues(), body = {};
  for (const k of Object.keys(now)) if (now[k] !== LOADED[k]) body[k] = now[k];
  const keys = Object.keys(body);
  qa('#pane .err').forEach(e => { e.textContent = ''; e.hidden = true; });
  if (!keys.length) { toast('Nothing to save: no setting here was changed.'); return; }
  /* The CLI, an agent over MCP and another browser write the same keys. Before this page overwrites
   * one, it asks the node whether that key moved since the form was drawn, and if it did, it says
   * so beside the field and writes nothing. Pressing Save again replaces it: the keeper has seen. */
  const auth = { authorization: 'Bearer ' + tok };
  const fresh = await fetch('/settings', { headers: auth }).then(x => x.ok ? x.json() : null).catch(() => null);
  const moved = fresh && fresh.unlocked ? movedSince(DESC, fresh, keys) : [];
  if (moved.length) {
    const ledger = await fetch('/actions?stage=settings&limit=200', { headers: auth })
      .then(x => x.ok ? x.json() : []).catch(() => []);
    for (const k of moved) {
      const r = fresh.runtime.find(x => x.key === k);
      const last = (Array.isArray(ledger) ? ledger : []).find(a => String(a.note || '').split(', ').includes(k));
      const who = last ? ` The last change the ledger has: ${last.actor}, ${window.K.age((Date.now() - Date.parse(last.ts)) / 60000)}.` : '';
      const was = r.secret ? (r.set ? 'It is set now.' : 'It is cleared now.') : `It is now "${r.value}".`;
      const box = q('#err-' + k);
      if (box) {
        box.textContent = `${k} changed on the node after this page drew it. ${was}${who} `
          + `Save again to replace it with what you chose, or reload the page to keep the node's.`;
        box.hidden = false;
      }
    }
    DESC = fresh;   // the keeper has now been shown these; a second press writes
    toast(`Nothing was saved. ${moved.join(', ')} changed on the node while this was open.`, true);
    return;
  }
  const r = await fetch('/settings', {
    method: 'PUT',
    headers: { 'content-type': 'application/json', authorization: 'Bearer ' + tok, 'X-Agent': 'dashboard' },
    body: JSON.stringify(body),
  });
  if (r.status === 401) { toast('That token is not right.', true); lock(); return; }
  if (r.status === 403) { toast('The node has no admin token yet. Run planetai ui.', true); return; }
  /* The node writes a sentence and the page used to throw it away. A keeper who typed 5 into "Report
   * every" got `Could not save (400).` — a status code, no field named, nothing marked, and the bad
   * value still sitting there — while the node had answered "'5' is not a value REPORT_EVERY accepts.
   * Hours between reports: 3, 4, 6, 8, 12 or 24. Default 6, which is four a day." app/settings.py
   * writes that refusal by quoting the key's own help text rather than keeping a second copy of it,
   * so it is the best sentence anybody has; it belongs beside the field it is about. */
  if (!r.ok) {
    const detail = await r.json().then(j => j && j.detail).catch(() => null);
    const said = typeof detail === 'string' ? detail : '';
    const which = Object.keys(body).find(k => said.includes(k));
    const box = which && q('#err-' + which);
    if (box) {
      box.textContent = said;
      box.hidden = false;
      const field = q('#set-' + which);
      if (field) field.focus();
      toast('Nothing was saved. The node said why, next to the setting.', true);
    } else {
      toast(said || ('Could not save (' + r.status + ').'), true);
    }
    return;
  }
  toast('Saved. Live within about twenty seconds.');
  DIRTY = false;
  loadSetup(); route();
}

document.addEventListener('input', ev => { if (ev.target.closest('#pane')) DIRTY = true; });

// the Set up pane's own clicks: unlock, save, reveal, tabs, switches, lock
//
// RESTORED. The first three of these lived in the shell's global click listener on the page this
// replaces, and carrying the pane across without them left every entry point into the token path
// drawn and dead: unlock() and saveSettings() were defined and unreachable, the gate never opened,
// and PAI_SETTINGS.set() could only ever throw for want of a token nothing could store.
document.addEventListener('click', ev => {
  if (ev.target.id === 'btn-unlock') return unlock();
  if (ev.target.id === 'btn-save') return saveSettings();
  /* A token is long, typed once, and often on a phone. Without this there is no way to check what
   * you typed before submitting it, and a wrong one only says so after a round trip. */
  const rev = ev.target.closest('[data-reveal]');
  if (rev) {
    const f = q('#' + rev.dataset.reveal);
    if (!f) return;
    const shown = f.type === 'text';
    f.type = shown ? 'password' : 'text';
    rev.setAttribute('aria-pressed', String(!shown));
    rev.textContent = shown ? 'Show' : 'Hide';
    return;
  }
  const g = ev.target.closest('[data-group]');
  if (g) {
    // An unsaved edit is the keeper's work. It used to go without a word.
    if (DIRTY && !confirm('This group has a change you have not saved. Leave it and lose the change?')) return;
    GROUP = g.dataset.group; return loadSetup();
  }
  if (ev.target.closest('[data-lock]')) return lock();
  const sw = ev.target.closest('.switch');
  if (sw) {
    sw.classList.toggle('on');
    sw.setAttribute('aria-checked', String(sw.classList.contains('on')));   // the state, not just the paint
    DIRTY = true;
  }
});

/* `dirty` is read by refresh(): a poll must never re-render a group with a typed value in it. */
window.PAI_SETUP = { markup, load: loadSetup, toast, dirty: () => DIRTY };

})();

/* ================================================================= h/ask.js — the ask pane ==== */
/* A person reading the page asks the node's own model, on this machine, about what the page shows.
 *
 * It is drawn OUTSIDE #page, once, so a poll that redraws the page never wipes a thread somebody is
 * in the middle of. The thread lives in sessionStorage and dies with the tab; the node keeps nothing
 * (GET /ask/status says `stored: false`, and tests/test_ask.py holds it to that). The model reads and
 * changes nothing: a change it reaches for arrives as a `proposal` event and is drawn as a card the
 * person presses, with the token the page already holds, the same way Set up and "I did this" write.
 *
 * Every figure and sentence in an answer is the model's; every word around it is this page's. */
(function () {
'use strict';
const esc = s => window.K.esc(s);
const OPEN = 'planetai_ask_open', THREAD = 'planetai_ask_thread', AT = 'planetai_ask_at';
/* 'learn' when learn mode opened the pane, so leaving the mode can close what it opened and nothing
   the person opened themselves. */
const BY = 'planetai_ask_by';
/* Where the composer's three questions start in the node's pool. It moves when the pane opens and when an
   answer lands, and at nothing else: a poll redraws the pane every few minutes, and a chip that changed
   under a finger on its way to it would be pressed as the wrong question. */
const ROT = 'planetai_ask_rot';
const turn = () => ss.set(ROT, String(Number(ss.get(ROT) || 0) + 3));
/* A thread nobody has added to for half an hour is over: the next person at a wall screen does not inherit the
   last one's conversation. It still survives a reload and every poll, which is why it is in sessionStorage. */
const IDLE_MS = 30 * 60 * 1000;
/* How many exchanges go back to the model with a question. Every one of them is read again on every question,
   so a long thread made each answer slower and vaguer, most of all on a small local model. */
const TURNS = 3;
const ss = {
  get(k) { try { return sessionStorage.getItem(k); } catch (e) { return null; } },
  set(k, v) { try { sessionStorage.setItem(k, v); } catch (e) { /* a browser that stores nothing still asks */ } },
};
let STATUS;              /* undefined: not asked yet · {ok, ...}: /ask/status answered · {missing, ...}: 404 */
let BUSY = false;
let ASKED_AT = 0;        /* when the question in flight was sent, for the seconds under the globe */
let GLOBE = null;        /* the canvas the globe is turning on, so a redraw can hand it over */
const forget = () => { ss.set(THREAD, '[]'); ss.set(AT, ''); };
const thread = () => {
  const at = Number(ss.get(AT) || 0);
  if (at && Date.now() - at > IDLE_MS) { forget(); return []; }
  try { return JSON.parse(ss.get(THREAD) || '[]'); } catch (e) { return []; }
};
const keep = t => { ss.set(THREAD, JSON.stringify(t.slice(-40))); ss.set(AT, String(Date.now())); };
/* What is sent: the last TURNS exchanges and the question, starting at a question of the person's. */
const recent = t => {
  const m = t.filter(x => x.content && x.role !== 'card').map(x => ({ role: x.role, content: x.content }))
    .slice(-(2 * TURNS + 1));
  while (m.length && m[0].role !== 'user') m.shift();
  return m;
};
const loc = () => (window.K && window.K.LOC) || 'en';
const docsUrl = h => `https://planetai.fab.city/docs/${String(h.page || '').replace(/\.md$/, '')}/`
  + (h.anchor ? `#${h.anchor}` : '');

/* UI_ASK off: no toggle, and the pane never draws. The wall has no header, so it never has one. */
function enabled() {
  const row = ((window.SETTINGS || {}).runtime || []).find(x => x.key === 'UI_ASK');
  return !row || String(row.value || 'on').trim() !== 'off';
}
function isOpen() {
  if (new URLSearchParams(location.search).get('ask') === '1') return true;   /* the rig's switch; remembers nothing */
  return ss.get(OPEN) === '1';
}
function view() { return (window.K && window.K.VIEW) || 'now'; }

async function status() {
  try {
    const r = await fetch('/ask/status', { headers: (window.PAI_AUTH ? window.PAI_AUTH() : {}) });
    if (r.status === 404) {
      const j = await r.json().catch(() => ({}));
      STATUS = { missing: true, ...((j && typeof j.detail === 'object') ? j.detail : {}) };
    } else if (!r.ok) {
      const j = await r.json().catch(() => ({}));
      STATUS = { refused: true, said: (j && (j.error || j.detail)) || `refused (${r.status})` };
    } else STATUS = { ok: true, ...(await r.json()) };
  } catch (e) { STATUS = { missing: true }; }
  draw();
}

/* Where a model runs, in the pane's words. Set up → Model decides which models the pane may ask (the same
   settings as the Telegram bot); the pane's job is to say, every time, which one answered and where. */
const whereWords = w => (!w || !w.where || w.where === 'this machine') ? 'runs on this machine'
  : w.where === 'your network' ? `runs on ${w.host}, on your network` : `runs online at ${w.host}`;
function leaves(s) {
  const out = (s.rungs || []).find(r => r.where === 'online');
  if (!s.leaves || !out) return '';
  return `<span class="m out">${s.where === 'online'
    ? `your question and this page’s context leave your network, to ${esc(out.host)}`
    : `if the models before it do not answer, your question and this page’s context go online, to ${esc(out.host)}`}`
    + ` · Set up → Model decides</span>`;
}
function head() {
  const s = STATUS || {};
  const who = s.ok ? `${esc(s.model)} · ${esc(whereWords(s))}`
    : s.missing ? 'no model on this node yet' : s.refused ? 'not answering this page' : 'asking the node…';
  return `<div class="ah"><div><b>ask the node</b><span class="m"><i class="${s.ok && s.running ? '' : 'none'}"></i>`
    + `${who}</span>${s.ok ? leaves(s) : ''}<span class="m">reads the page · records what you did · changes nothing</span></div>`
    + `<span class="hx">${thread().length && !BUSY
      ? `<button type="button" class="x" data-ask-new>new conversation</button>` : ''}`
    + `<button type="button" class="x" data-ask-toggle aria-label="close the pane">close</button></span></div>`;
}

function search() {
  return `<form class="askfind" data-ask-find><label class="vh" for="ask-find">search this node's documentation</label>`
    + `<input id="ask-find" name="q" minlength="2" maxlength="80" placeholder="search the documentation" autocomplete="off">`
    + `<button type="submit">search</button></form><div class="askhits" id="ask-hits"></div>`;
}

function nomodel() {
  const s = STATUS || {};
  const rec = s.recommend || {};
  const url = `${location.protocol}//${location.host}${s.mcp || '/mcp'}`;
  const mcp = `claude mcp add --transport http planetai "${url}" \\\n  --header "Authorization: Bearer $PLANETAI_ADMIN_TOKEN"`;
  const card = (title, lead, code) => `<div class="card"><div class="ch"><span>${esc(title)}</span></div>`
    + `<p class="more">${esc(lead)}</p><pre>${esc(code)}</pre>`
    + `<div class="bt"><button type="button" data-copy="${esc(code)}">copy</button></div></div>`;
  const first = s.running === false
    ? `<p class="plead">${esc(s.model || 'The model')} is on this node and not answering: ${esc(s.why || 'Ollama is down')}. `
      + `On the node, <code>planetai doctor</code> says why. Until then this pane searches the documentation.</p>`
    : `<p class="plead">This node has no model to ask yet. The documentation still answers from here, and either `
      + `of the two cards below gives it a voice.</p>`;
  return `<div class="nomodel">${first}${search()}`
    + (s.running === false ? '' :
      card('a model on this machine', `${rec.tag ? `${rec.tag}, ${rec.size || ''} on disk, is what this node suggests for its memory. ` : ''}`
        + 'On the node:', rec.pull || 'planetai agent local')
      + `<p class="or">or</p>`
      + card('a model on another machine of yours', 'Under Set up \u2192 Model, the remote model\u2019s address '
        + 'and tag. Ollama on a laptop on this network:', 'AGENT_REMOTE_URL=http://<laptop>.local:11434/v1')
      + `<p class="or">or</p>`
      + card('your own agent, over MCP', 'From your own machine. `planetai agent` on the node prints the token.', mcp))
    + `</div>`;
}

function ledger(m, live) {
  const ts = m.ledger || [];
  if (!ts.length && !m.done) return '';
  /* The tools an answer used, folded to one line: they are there to be checked, not read on every answer.
     Open while the node is still working, because then they are the only news there is. */
  return `<div class="ledger">${ts.length ? `<details${live ? ' open' : ''}><summary>read ${ts.length} thing${ts.length === 1 ? '' : 's'}</summary>`
      + ts.map(t => `<span><b>${esc(t.tool)}</b> ${esc(String(t.ms))} ms</span>`).join('') + `</details>` : ''}`
    + (m.done ? `<span class="${m.done.where === 'online' ? 'out' : ''}"><i></i>${esc(m.done.model)} · `
      + `${esc(whereWords(m.done))}</span>` : '') + `</div>`;
}

function proposal(p, i) {
  if (p.tool === 'act') {
    const id = (p.args || {}).alert_id;
    return `<div class="card ask" data-component="askProposal"><div class="ch"><span>record what you did</span>`
      + `<span>#${esc(String(id))}</span></div><p class="more">Say it in your own words; the node keeps them `
      + `as yours.</p>${id != null && window.K.didButton ? window.K.didButton(id) : ''}</div>`;
  }
  if (p.tool !== 'settings_set' || !p.setting) {
    return `<div class="card" data-component="askProposal"><div class="ch"><span>${esc(p.tool)}</span></div>`
      + `<p class="more">The model reached for ${esc(p.tool)}. The pane does not run it; Set up or the node's `
      + `own shell does.</p></div>`;
  }
  const tok = (() => { try { return localStorage.getItem('planetai_admin') || ''; } catch (e) { return ''; } })();
  const pick = p.proposed != null ? `<b>${esc(p.proposed)}</b>`
    : `<select name="v" aria-label="the value">${(p.choices || []).map(c =>
      `<option${c === p.current ? '' : ' selected'}>${esc(c)}</option>`).join('')}</select>`;
  return `<form class="card" data-ask-set="${esc(p.setting)}" data-proposed="${esc(p.proposed || '')}"`
    + ` data-component="askProposal"><div class="ch"><span>a setting</span><span>${esc(p.setting)}</span></div>`
    + `<div class="kv"><span>now</span><b>${esc(p.current || 'blank')}</b><span>proposed</span>${pick}`
    + `<span>what leaves</span><span>${esc((p.leaves || {})[loc()] || (p.leaves || {}).en || '')}</span>`
    + `<span>undo</span><span>${esc((p.undo || {})[loc()] || (p.undo || {}).en || '')}</span></div>`
    + (tok ? '' : `<p class="more">needs your token · <code>planetai ui</code> prints it</p>`
      + `<label class="vh" for="ask-tok-${i}">admin token</label><input id="ask-tok-${i}" name="tok" type="password" `
      + `autocomplete="off" placeholder="admin token">`)
    + `<div class="bt"><button type="submit" class="pri">turn it on</button>`
    + `<button type="button" data-ask-setup="${esc(p.group || '')}">open Set up → ${esc(p.group || '')}</button></div>`
    + `<p class="said" hidden></p></form>`;
}

const plain = s => String(s || '').replace(/`/g, '');
/* The mark whose card is the latest thing in the thread is the part in focus: its questions are the
   chips, and a question asked now is sent with it, so the node reads that part's documentation too. */
function focusKey() {
  const t = thread();
  const last = t[t.length - 1];
  return last && last.role === 'card' ? last.key : null;
}
function learnCard(c) {
  const m = window.PAI_LEARN_MARK ? window.PAI_LEARN_MARK(c.key) : null;
  if (!m) return '';
  return `<div class="card mark" data-component="learnCard" data-learn-card="${esc(c.key)}">`
    + `<div class="ch"><span>${esc(plain(m.title))}</span><span>${esc(String(c.i))} of ${esc(String(c.n))}</span></div>`
    + `<blockquote class="qt">${window.PAI_LEARN_QUOTE ? window.PAI_LEARN_QUOTE(m.quote) : esc(m.quote)}</blockquote>`
    + `<p class="more"><span class="who">This page:</span> ${esc(m.more)}</p>`
    + `<p class="src">From <a href="${esc(m.url)}" rel="noreferrer">${esc(plain(m.page_title || m.page))}`
    + `${m.section ? ` \u00b7 ${esc(plain(m.section))}` : ''}</a>.</p>`
    + `<div class="bt"><button type="button" data-learn-step="-1">previous</button>`
    + `<button type="button" class="pri" data-learn-step="1">next</button></div></div>`;
}

/* While the node is working: the page's own globe, turning, with which model was asked and for how
   long. It is the loading state's drawing, not a spinner: the same glyphs and the same cell. */
function waiting() {
  const s = STATUS || {};
  return `<div class="thinking"><canvas class="askglobe" aria-hidden="true"></canvas>`
    + `<span class="m">asking ${esc(s.model || 'the node')} · <b data-ask-clock>${clock()}</b></span></div>`;
}
const clock = () => `${Math.max(0, Math.round((Date.now() - ASKED_AT) / 1000))} s`;

function msg(m, i, all) {
  if (m.role === 'card') return learnCard(m);
  if (m.role === 'user') return `<div class="msg you"><div class="who"><b>you</b></div><div class="bd">${esc(m.content)}</div></div>`;
  const live = BUSY && i === all.length - 1;
  return `<div class="msg node"><div class="who"><b>the node</b></div><div class="bd" id="ask-m-${i}">`
    + (live && !m.content && !m.error ? waiting() : esc(m.content || (m.error ? '' : '…')))
    + `${m.error ? `<p class="err">${esc(m.error)}</p>` : ''}</div>`
    + (m.proposals || []).map(proposal).join('') + ledger(m, live) + `</div>`;
}

/* A redraw replaces the pane's markup, so the globe's canvas is a new element each time: the loop
   lets go of the old one and takes the new one, and lets go of both when the answer is in. */
function spin() {
  const cv = document.querySelector('#askpane canvas.askglobe');
  if (cv === GLOBE) return;
  if (GLOBE) window.PAI_RAF.remove(GLOBE);
  GLOBE = cv;
  if (cv && window.PAI_ASKING) window.PAI_RAF.add(cv, window.PAI_ASKING.globe);
}

/* Three of the node's questions, from where the rotation stands, leaving out any already asked in this
   conversation. A learn mark in focus puts its own two first. */
function chipsFor(mine) {
  const d = ((window.K && window.K.S && window.K.S.issues) || {}).digest || {};
  const pool = (d.prompts || {})[loc()] || (d.prompts || {}).en || [];
  const asked = new Set(thread().filter(m => m.role === 'user').map(m => m.content));
  const left = pool.filter(q => !asked.has(q) && !(mine || []).includes(q));
  const from = left.length ? left : pool;
  const r = from.length ? Number(ss.get(ROT) || 0) % from.length : 0;
  return [...(mine || []).slice(0, 2), ...from.slice(r), ...from.slice(0, r)].slice(0, 3);
}

function composer() {
  const fm = focusKey() && window.PAI_LEARN_MARK ? window.PAI_LEARN_MARK(focusKey()) : null;
  const chips = chipsFor(fm && fm.questions ? (fm.questions[loc()] || fm.questions.en) : null);
  const fixture = new URLSearchParams(location.search).get('fixture');
  return `<form class="compose" data-ask-send>`
    + `<div class="chips">${chips.map(c => `<button type="button" data-ask-chip="${esc(c)}">${esc(c)}</button>`).join('')}</div>`
    + `<div class="box"><label class="vh" for="ask-q">ask the node</label>`
    + `<input id="ask-q" name="q" maxlength="4000" autocomplete="off" placeholder="ask about what this page shows"${BUSY ? ' disabled' : ''}>`
    + `<button type="submit"${BUSY ? ' disabled' : ''}>ask</button></div>`
    + `<p class="fine">${fixture ? '<b>This page is a capture, and the pane asks the live node</b>: its answers are about '
      + 'tonight, not about what is drawn here. ' : ''}This conversation lives in this tab. It is gone when you close it, `
      + `press new conversation, or ask nothing for half an hour. `
      + `<b>The node keeps no transcript.</b>${(STATUS || {}).leaves ? ' An online model keeps what its provider’s own '
        + 'terms say it keeps.' : ''}</p></form>`;
}

function draw() { paint(); spin(); }

function paint() {
  const on = enabled() && isOpen() && view() !== 'wall';
  document.body.classList.toggle('askopen', on);
  document.querySelectorAll('[data-ask-toggle]').forEach(b => {
    if (!b.classList.contains('x')) b.setAttribute('aria-pressed', String(on));
  });
  const el = document.getElementById('askpane');
  if (!el) return;
  el.hidden = !on;
  if (!on) return;
  if (STATUS === undefined) { el.innerHTML = head(); status(); return; }
  const t = thread();
  const cards = t.filter(m => m.role === 'card');
  const fm = focusKey() && window.PAI_LEARN_MARK ? window.PAI_LEARN_MARK(focusKey()) : null;
  el.innerHTML = head() + (STATUS.ok && STATUS.running
    ? `<div class="thread" id="ask-thread">${t.map((m, i) => msg(m, i, t)).join('')}</div>${composer()}`
    : STATUS.refused ? `<p class="plead">${esc(STATUS.said)}</p>`
    /* Without a model the card stands alone, and the chips search the documentation for its title. */
    : `<div class="askbody">`
      + (cards.length ? learnCard(cards[cards.length - 1]) : '')
      + (fm ? `<div class="chips"><button type="button" data-ask-find-q="${esc(plain(fm.title))}">`
        + `search the documentation for \u201c${esc(plain(fm.title))}\u201d</button></div>` : '')
      + nomodel() + `</div>`);
  const th = el.querySelector('#ask-thread');
  if (th) th.scrollTop = th.scrollHeight;
}

async function send(text) {
  if (BUSY || !text.trim()) return;
  const t = thread();
  t.push({ role: 'user', content: text.trim() });
  const me = { role: 'assistant', content: '', ledger: [], proposals: [] };
  t.push(me);
  keep(t); BUSY = true; ASKED_AT = Date.now(); draw();
  const i = t.length - 1;
  const ticking = setInterval(() => {
    const c = document.querySelector('#askpane [data-ask-clock]');
    if (c) c.textContent = clock();
  }, 1000);
  try {
    const r = await fetch('/ask', {
      method: 'POST',
      headers: { 'content-type': 'application/json', ...(window.PAI_AUTH ? window.PAI_AUTH() : {}) },
      body: JSON.stringify({
        messages: recent(t),
        view: view(), mode: window.PAI_MODE ? window.PAI_MODE() : 'advanced',
        focus: t.filter(m => m.role === 'card').map(m => m.key).pop() || null,
      }),
    });
    if (!r.ok || !r.body) throw new Error(`the node answered ${r.status}`);
    const rd = r.body.getReader(), dec = new TextDecoder();
    let buf = '';
    for (;;) {
      const { value, done } = await rd.read();
      if (done) break;
      buf += dec.decode(value, { stream: true });
      let cut;
      while ((cut = buf.indexOf('\n\n')) >= 0) {
        const block = buf.slice(0, cut); buf = buf.slice(cut + 2);
        const ev = (block.match(/^event: (.+)$/m) || [])[1];
        const data = JSON.parse((block.match(/^data: (.+)$/m) || [])[1] || '{}');
        if (ev === 'token') {
          const first = !me.content;
          me.content += data.text;
          const box = document.querySelector(`#ask-m-${i}`);
          /* The first word takes the globe away, which is a redraw; the rest only add text. */
          if (first) draw(); else if (box) box.textContent = me.content;
          continue;
        }
        /* A model that fell over after reading something: the next one starts from nothing. */
        if (ev === 'retry') me.ledger = [];
        else if (ev === 'tools') me.ledger.push(data);
        else if (ev === 'proposal') me.proposals.push(data);
        else if (ev === 'done') me.done = data;
        else if (ev === 'error') me.error = data.message;
        keep(t); draw();
      }
    }
  } catch (e) {
    me.error = `The node did not answer: ${String((e && e.message) || e)}`;
  } finally {
    clearInterval(ticking);
    me.content = me.content.trim();
    turn();
    BUSY = false; keep(t); draw();
  }
}

async function setIt(form) {
  const key = form.dataset.askSet;
  const v = form.dataset.proposed || (form.elements.v && form.elements.v.value);
  const typed = form.elements.tok && form.elements.tok.value;
  if (typed) { try { localStorage.setItem('planetai_admin', typed); } catch (e) { /* kept for this press only */ } }
  const tok = typed || (() => { try { return localStorage.getItem('planetai_admin') || ''; } catch (e) { return ''; } })();
  const said = form.querySelector('.said');
  const say = s => { said.textContent = s; said.hidden = false; };
  if (!tok) return say('needs your token');
  const r = await fetch('/settings', {
    method: 'PUT',
    headers: { 'content-type': 'application/json', authorization: 'Bearer ' + tok, 'X-Agent': 'dashboard' },
    body: JSON.stringify({ [key]: v }),
  }).catch(() => null);
  if (!r) return say('The node did not answer.');
  if (r.status === 401) return say('That token is not right.');
  const j = await r.json().catch(() => ({}));
  if (!r.ok) return say((j && j.detail) || `The node refused it (${r.status}).`);
  say(`${key} is ${v} now. It takes effect within 20 seconds.`);
}

document.addEventListener('click', ev => {
  const t = ev.target && ev.target.closest ? ev.target : null;
  if (!t) return;
  if (t.closest('[data-ask-new]')) {
    if (!BUSY) { forget(); draw(); const q = document.querySelector('#askpane #ask-q'); if (q) q.focus(); }
    return;
  }
  if (t.closest('[data-ask-toggle]')) {
    ev.preventDefault();
    if (!isOpen()) turn();
    ss.set(OPEN, isOpen() ? '0' : '1');
    ss.set(BY, '');
    return draw();
  }
  const fq = t.closest('[data-ask-find-q]');
  if (fq) {
    const f = document.querySelector('#askpane [data-ask-find]');
    if (f) { f.elements.q.value = fq.getAttribute('data-ask-find-q'); f.requestSubmit(); }
    return;
  }
  const chip = t.closest('[data-ask-chip]');
  if (chip) return send(chip.getAttribute('data-ask-chip'));
  const cp = t.closest('[data-copy]');
  if (cp) {
    const text = cp.getAttribute('data-copy');
    (navigator.clipboard ? navigator.clipboard.writeText(text) : Promise.reject()).then(
      () => { cp.textContent = 'copied'; }, () => { cp.textContent = 'select it and copy'; });
    return;
  }
  const su = t.closest('[data-ask-setup]');
  if (su) { history.pushState({ view: 'setup' }, '', '#setup'); window.dispatchEvent(new PopStateEvent('popstate')); }
});
document.addEventListener('submit', async ev => {
  const f = ev.target;
  if (f.matches && f.matches('[data-ask-send]')) {
    ev.preventDefault();
    const q = f.elements.q.value; f.elements.q.value = '';
    return send(q);
  }
  if (f.matches && f.matches('[data-ask-set]')) { ev.preventDefault(); return setIt(f); }
  if (f.matches && f.matches('[data-ask-find]')) {
    ev.preventDefault();
    const box = document.querySelector('#askpane #ask-hits');
    const r = await fetch('/docs/search?q=' + encodeURIComponent(f.elements.q.value)).catch(() => null);
    const hits = r && r.ok ? await r.json() : [];
    box.innerHTML = hits.length ? hits.map(h => `<a class="hit" href="${esc(docsUrl(h))}">`
      + `<b>${esc(h.title)}</b><span>${esc(h.snippet)}</span></a>`).join('')
      : `<p class="more">${r && r.ok ? 'Nothing in the documentation says that.' : 'The node did not answer.'}</p>`;
  }
});

/* The page tells the pane when it has drawn, so a toggle drawn by chrome() picks up the pane's state. */
function card(key, i, n) {
  const t = thread();
  const c = { role: 'card', key, i, n };
  if (t.length && t[t.length - 1].role === 'card') t[t.length - 1] = c; else t.push(c);
  keep(t);
  if (!isOpen()) ss.set(BY, 'learn');
  ss.set(OPEN, '1');
  draw();
  const el = document.querySelector('#askpane [data-learn-card]');
  if (el) el.scrollIntoView({ block: 'nearest' });
}

/* Learn mode opens the pane, and leaving it takes back what it brought: its cards come out of the
   thread, and the pane closes if learn is what opened it. Before this, turning learn off left the
   documentation's card standing in the pane over a page that no longer had the mark it quoted. */
function learnOn() {
  if (!isOpen()) { ss.set(BY, 'learn'); turn(); }
  ss.set(OPEN, '1');
  draw();
}
function learnOff() {
  const t = thread();
  if (t.some(m => m.role === 'card')) keep(t.filter(m => m.role !== 'card'));
  if (ss.get(BY) === 'learn') { ss.set(OPEN, '0'); ss.set(BY, ''); }
}

window.PAI_ASK = { draw, card, learnOn, learnOff };
})();
