# Dashboard figures, part B: the page — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The dashboard draws each issue's day once, as one interactive figure (every distance, the usual band, the
line and the hours over it, the event and its answer, the event's own rooms, a readout in words), adds strips of
hours (seven days on Now, every day the node holds on Historical), gives each station row a drawing that answers a
pointer, keeps stations that stopped in a fold, and counts hours over the line in Measure.

**Architecture:** Two vendored files, `static/d3.min.js` and `static/plot.umd.min.js`, load before `dashboard.js`.
A figures kit in `dashboard.js` (`fig`, `mountFigs`, `dayFigure`, `strips`, `spark` and five pure helpers) is
exported on `window.K`, because sections are separate closures. A section's `render` still returns an HTML string:
`fig()` puts a placeholder in it and keeps a draw function, and `route()` calls `mountFigs()` after it has replaced
the page. The page fetches `GET /issues/days` (part A) for the strips and Measure.

**Tech stack:** Vanilla JS in one file (`app/static/dashboard.js`), Observable Plot 0.6.17 with d3 7.9.0 (ISC),
CSS (`app/static/dashboard.css`), plain-`assert` Python tests that run page code in node
(`tests/test_dashboard.py`), the Playwright visual gate (`tests/visual/gate.sh`).

**Spec:** `docs/SPEC_dashboard_figures.md` §4. Part A (`docs/plans/2026-10-06-dashboard-figures-part-a.md`) must be
merged first: this plan reads `usual`, `usual_absent`, `events.open[].series`, `stations_silent`, `last_heard` and
`GET /issues/days`. The figures kit below ran without a console error on node #1's data at 1200 and 390 px and in
both registers (planetai-design, branch `day-figure-prototype-2026-10-06`, `prototypes/day-figure/harness/`).

## Global constraints

- Work in your own git worktree off `origin/main` after part A has merged; never in `planetai-node-main`.
- `make lint && make test` before every commit (the pre-commit hook runs both; allow 300000 ms; never `--no-verify`).
- **Separate closures.** Each `PAI_LOAD.push(function () {...})` is its own scope. A helper more than one section
  uses goes on `window.K` and is destructured in each closure that uses it (memory: "Dashboard sections are separate
  closures"). A helper defined in one closure is undefined in another, and the lifted-function tests cannot see that.
- **Nothing at load.** `tests/test_dashboard.py` loads the whole of `dashboard.js` in node. No top-level statement
  may touch `ResizeObserver`, `CSS`, `getComputedStyle`, `Plot`, `d3` or `document` beyond what the file already does.
- **The node computes, the page draws.** Every count printed is the node's (`per_day`), or a sum of the node's own
  counts. No median, mean, MAD or fence appears in the page.
- **Class names.** Every class the kit writes starts with `f-`. `.ev`, `.band`, `.line`, `.read`, `.legend`, `.over`
  and `.gone` already have unscoped rules in `dashboard.css`, and the theme binds `.ring`, `.cell`, `.sat` and `.label`.
- **Colour has one meaning.** Ink for readings, red (`--signal-worse`) for the line and hours over it, green
  (`--rings`) only for an answer that closed a loop (Done), blue (`--cells`) for the focus outline and the pointed
  cell. No other hue.
- **The frozen layer** (`planetai-theme.css`, `signs.svg`, `kilometre-cells.json`) is not edited.
- **The visual gate** runs here in about five minutes (memory: "Run the visual gate locally"):
  `PAI_DESIGN_REPO=../planetai-design bash tests/visual/gate.sh`. Run it before the last commit of each task that
  changes the page.
- Commit messages end with a blank line and `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Files

| file | what changes |
|---|---|
| `app/static/d3.min.js`, `app/static/plot.umd.min.js` (new) | the vendored library, byte for byte from jsDelivr |
| `app/static/licences/d3.txt`, `app/static/licences/plot.txt` (new) | their ISC licences |
| `data/vendor.sha256` (new), `Makefile` | the two hashes; `make lint` checks them |
| `app/main.py` | two `COMPANIONS` entries |
| `app/static/index.html` | two script tags before `dashboard.js` |
| `app/static/dashboard.js` | the figures kit and its export; `route()` mounts; `boot()`/`refresh()`/`route()` read `/issues/days`; `bind()` keeps silent stations apart; the `day`, `shape`, `sensors` and `measure` sections; `series`, `runs`, `barcode` and `graphic` deleted |
| `app/static/dashboard.css` | the figures block; the barcode and series rules deleted |
| `tests/test_dashboard.py` | the helpers, the cards, and the `runs` check replaced |
| `tools/build_learn.py`, `app/static/learn.json` | the `figure` and `strips` marks |
| `docs/site/dashboard.md`, `docs/site/design.md`, `docs/GUI.md`, `CHANGELOG.md`, `docs/SPEC_dashboard_figures.md` | the page as built |
| `app/issues/fixtures/node1-<date>-figures.json` (new), `tests/visual/gate.sh` | a capture with `issues_days`; the gate reads it |
| `tools/check_docs.py` | remove the vendored names from the spec's `PROPOSED` entry |

---

### Task 1: the vendored library

**Files:**
- Create: `app/static/d3.min.js`, `app/static/plot.umd.min.js`, `app/static/licences/d3.txt`,
  `app/static/licences/plot.txt`, `data/vendor.sha256`
- Modify: `Makefile` (`lint`), `app/main.py` (`COMPANIONS`), `app/static/index.html`, `tools/check_docs.py`

- [ ] **Step 1: Fetch the files.**

```bash
mkdir -p app/static/licences
curl -sfL -o app/static/d3.min.js https://cdn.jsdelivr.net/npm/d3@7.9.0/dist/d3.min.js
curl -sfL -o app/static/plot.umd.min.js https://cdn.jsdelivr.net/npm/@observablehq/plot@0.6.17/dist/plot.umd.min.js
curl -sfL -o app/static/licences/d3.txt https://cdn.jsdelivr.net/npm/d3@7.9.0/LICENSE
curl -sfL -o app/static/licences/plot.txt https://cdn.jsdelivr.net/npm/@observablehq/plot@0.6.17/LICENSE
```

- [ ] **Step 2: Pin them.** Create `data/vendor.sha256`:

```
f2094bbf6141b359722c4fe454eb6c4b0f0e42cc10cc7af921fc158fceb86539  app/static/d3.min.js
4358086467740777dd788d6b27a95cebdbaefdd50c730a3060117073bd7134cb  app/static/plot.umd.min.js
```

  Run: `shasum -a 256 -c data/vendor.sha256`
  Expected: `app/static/d3.min.js: OK` and `app/static/plot.umd.min.js: OK`. If either says `FAILED`, the download
  is not the file the plan was tested against: stop and report, do not update the hash.

- [ ] **Step 3: Hold them in lint.** In `Makefile`, the `lint:` recipe begins
  `bash -n install ... && python3 tools/check_floors.py && ...`. Insert directly after `python3 tools/check_theme.py`:
  `&& shasum -a 256 -c --quiet data/vendor.sha256`. A comment line above the `lint:` target:

```make
# data/vendor.sha256: the two vendored drawing libraries (docs/SPEC_dashboard_figures.md §4.1). Replacing one is a
# deliberate act: fetch the new version, rewrite its line, and say why in the commit.
```

- [ ] **Step 4: Serve them.** In `app/main.py`'s `COMPANIONS`, directly after the `"dashboard.css"` entry:

```python
    # The drawing library (docs/SPEC_dashboard_figures.md §4.1): Observable Plot and the d3 it is built on, vendored
    # for the same reason as the fonts. ISC; the licences are in app/static/licences/. data/vendor.sha256 pins both.
    "d3.min.js": (STATIC / "d3.min.js", "application/javascript"),
    "plot.umd.min.js": (STATIC / "plot.umd.min.js", "application/javascript"),
```

  In `app/static/index.html`, directly above `<script src="static/dashboard.js"></script>`:

```html
<script src="static/d3.min.js"></script>
<script src="static/plot.umd.min.js"></script>
```

  In `tools/check_docs.py`, remove `"app/static/d3.min.js", "app/static/plot.umd.min.js", "data/vendor.sha256"`
  from the `docs/SPEC_dashboard_figures.md` entry of `PROPOSED`. If the entry is then empty, delete it.

- [ ] **Step 5: Gates.**
  Run: `make lint`
  Expected: `ok`. `tools/check_ui.py` fails a script the page loads that `COMPANIONS` does not serve, so its
  silence is the check that the two lines agree.

- [ ] **Step 6: Commit.**

```bash
git add app/static/d3.min.js app/static/plot.umd.min.js app/static/licences data/vendor.sha256 Makefile app/main.py app/static/index.html tools/check_docs.py
git commit -m "static: vendor Observable Plot 0.6.17 and d3 7.9.0, pinned by hash, served by name

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: the figures kit

**Files:**
- Modify: `app/static/dashboard.js` (a new block directly above `window.K = {`; the export; `route()`)
- Modify: `app/static/dashboard.css` (a new block at the end)
- Test: `tests/test_dashboard.py`

**Interfaces:**
- Produces on `window.K`: `fig(id, draw, o) -> html`, `mountFigs(root)`, `boxOf(vals, line, pad?) -> {lo, hi} | null`,
  `offsetOf(iso) -> minutes`, `hhmmAt(ms, off) -> "HH:MM"`, `hourAt(ms, off) -> 0..23`, `dayAt(ms, off) -> "YYYY-MM-DD"`,
  `nearestIndex(ts, t) -> index`, `PLOT_STYLE`, `dayFigure(key, d, o) -> html`, `strips(key, D, o) -> html`.
  Tasks 3–6 use them. `dayFigure` and `strips` are added here so the whole kit is reviewed once; their callers come
  in Tasks 3 and 4.

- [ ] **Step 1: Write the failing test.** In `tests/test_dashboard.py`, directly above the final `print(...)`:

```python
# THE FIGURES KIT (docs/SPEC_dashboard_figures.md §4). The drawing needs Plot and a DOM; the arithmetic of where a
# drawing starts, which hour a bucket is, and which hour a pointer is nearest does not, so it is run here.
if shutil.which("node"):
    _kit = [re.search(p, _js, re.S) for p in (
        r"const boxOf = \(vals, line, pad = 0\.12\) => \{.*?\n\};",
        r"const offsetOf = iso => \{.*?\n\};",
        r"const hhmmAt = \(ms, off\) => [^\n]*;",
        r"const hourAt = \(ms, off\) => [^\n]*;",
        r"const dayAt = \(ms, off\) => [^\n]*;",
        r"function nearestIndex\(ts, t\) \{.*?\n\}")]
    assert all(_kit), "dashboard.js lost a figures-kit helper: " + str([bool(k) for k in _kit])
    _k = _node("\n".join(k.group(0) for k in _kit) + r"""
const t = Date.parse('2026-10-06T07:00:00+08:00');
console.log(JSON.stringify({
  air: boxOf([4, 5, 193, null, 6], 15), heat: boxOf([28.4, 35.6, null], 35), cold: boxOf([-2, 3], null),
  flat: boxOf([5, 5, 5], null), none: boxOf([null], null),
  off8: offsetOf('2026-10-06T07:00:00+08:00'), offZ: offsetOf('2026-10-06T07:00:00Z'), offN: offsetOf('2026-10-06T07:00:00-05:30'),
  hhmm: hhmmAt(t, 480), hour: hourAt(t, 480), day: dayAt(t - 8 * 3600e3, 480), dayUtc: dayAt(t - 8 * 3600e3, 0),
  near: nearestIndex([0, 10, 20, 30], 14), last: nearestIndex([0, 10, 20, 30], 99) }));""")
    assert _k["air"]["lo"] == 0 and _k["air"]["hi"] > 193, f"a concentration never draws a floor below zero: {_k['air']}"
    assert 27 < _k["heat"]["lo"] < 28.4 and _k["heat"]["hi"] > 35.6, f"heat keeps its own floor, not zero: {_k['heat']}"
    assert _k["cold"]["lo"] < -2, f"a quantity that goes negative may: {_k['cold']}"
    assert _k["flat"]["hi"] > _k["flat"]["lo"], f"a flat day still has a box: {_k['flat']}"
    assert _k["none"] is None
    assert (_k["off8"], _k["offZ"], _k["offN"]) == (480, 0, -330), _k
    assert (_k["hhmm"], _k["hour"]) == ("07:00", 7), "the node's hour, never the reader's"
    assert (_k["day"], _k["dayUtc"]) == ("2026-10-05", "2026-10-05"), _k
    assert (_k["near"], _k["last"]) == (1, 3), _k
```

- [ ] **Step 2: Run it and watch it fail.**
  Run: `python3 tests/test_dashboard.py`
  Expected: `AssertionError: dashboard.js lost a figures-kit helper: [False, False, False, False, False, False]`

- [ ] **Step 3: Add the kit.** In `app/static/dashboard.js`, directly above the line `window.K = { esc, fmt, sign, ...`,
  insert exactly this block. It uses `esc`, `fmt`, `reasonFor`, `noLine` and the kit's `let`s `S`, `ISS`, `DIST`, `LAB`
  and `LOC`, all defined above it in the same top-level kit:

```js
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
/* A bucket's own offset in minutes ("+08:00" is 480), so a label says the node's hour, never the reader's. */
const offsetOf = iso => {
  const m = /([+-])(\d\d):(\d\d)$/.exec(String(iso || ''));
  return m ? (m[1] === '-' ? -1 : 1) * (+m[2] * 60 + +m[3]) : 0;
};
const hhmmAt = (ms, off) => new Date(ms + off * 60000).toISOString().slice(11, 16);
const hourAt = (ms, off) => new Date(ms + off * 60000).getUTCHours();
const dayAt = (ms, off) => new Date(ms + off * 60000).toISOString().slice(0, 10);
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
  const B = d.buckets || [], T = B.map(b => Date.parse(b)), off = offsetOf(B[B.length - 1]);
  const now = Math.max(Date.parse(((S || {}).issues || {}).as_of) || 0, T[T.length - 1]);
  const hero = sets.includes(d.headline) ? d.headline : sets[0];
  const line = d.line ? d.line.value : null;
  const U = d.usual && d.usual.hours ? d.usual.hours : null;
  const band = U ? T.map(t => ({ t: new Date(t), ...(U[hourAt(t, off)] || {}) })) : [];
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
    return `<b>${esc(hhmmAt(T[i], off))}</b>`
      + sets.map(k => `<span class="f-d f-${k}${ser[k][i] == null ? ' f-gone' : ''}"><i></i>${esc(LAB[k])} `
        + `${ser[k][i] == null ? 'nothing recorded' : esc(fmt(ser[k][i], dp))}</span>`).join('')
      + (roomsOf && roomsOf.values[i] != null ? `<span class="f-d f-rooms"><i></i>${esc(roomsOf.rooms.join(', '))} `
        + `${esc(fmt(roomsOf.values[i], dp))}</span>` : '')
      + (band[i] && band[i].median != null ? `<span class="f-usual">usual ${esc(fmt(band[i].median, dp))} to `
        + `${esc(fmt(band[i].p90, dp))}</span>` : '')
      + (overAt(i) ? `<span class="f-over">over the line ${esc(fmt(line, dp))}</span>` : '')
      + (ev ? `<span class="f-ev">${esc(ev.e.kind)} open · ${ev.e.answer
        ? `<b class="${ev.e.answer.stage === 'acted' ? 'f-done' : ''}">${esc(ANSWER[ev.e.answer.stage] || ev.e.answer.stage)}</b>`
          + ` · ${esc(ev.e.answer.actor || '')} ${esc(hhmmAt(ev.a, off))}` : 'no answer'}</span>` : '');
  };
  const draw = (el, W) => {
    const narrow = W < 600, H = narrow ? 170 : 230, pad = (box.hi - box.lo) * 0.06, evY = box.hi - pad;
    const at = T.map(t => new Date(t));
    const rows = k => ser[k].map((v, i) => ({ t: at[i], v }));
    const lone = k => rows(k).filter((r, i, a) => r.v != null && (i === 0 || a[i - 1].v == null)
      && (i === a.length - 1 || a[i + 1].v == null));
    const late = x => (x.o - T[0]) / ((now - T[0]) || 1) > 0.8;
    const label = x => (narrow ? x.e.kind : `${x.e.kind} · ${hhmmAt(+x.o, off)}`);
    const ev = evs.map(x => ({ ...x, o: new Date(x.o), c: new Date(x.c), a: x.a == null ? null : new Date(x.a) }));
    const svg = Plot.plot({
      width: W, height: H, marginLeft: 8, marginRight: 8, marginTop: 18, marginBottom: 26, style: PLOT_STYLE,
      x: { type: 'time', domain: [new Date(T[0]), new Date(now)], label: null, tickSize: 0,
        ticks: at.filter(t => hourAt(+t, off) % (narrow ? 6 : 3) === 0), tickFormat: t => hhmmAt(+t, off) },
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
    + (evs.length ? `<span class="f-evl"><i></i>event, opened to cleared</span><span class="f-done"><i></i>answered Done</span>` : '');
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
      + evs.map(x => `${x.e.kind} ${hhmmAt(x.o, off)} to ${x.e.cleared_at ? hhmmAt(x.c, off) : 'now'}, `
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
  const T = D.buckets.map(b => Date.parse(b)), off = offsetOf(D.buckets[D.buckets.length - 1]);
  const days = [...new Set(T.map(t => dayAt(t, off)))];
  const cells = T.map((t, i) => ({ day: dayAt(t, off), hour: hourAt(t, off), t, v: vals[i] }));
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
          fontSize: 10.5, text: s => (perDay[s].over ? `${perDay[s].over} h over` : '·'),
          fill: s => (perDay[s].over ? 'var(--signal-worse)' : 'var(--dim)') }),
        narrow ? null : Plot.text(ev, { x: () => 23, y: e => dayAt(e.o, off), dx: 96, textAnchor: 'start', fontSize: 10.5,
          fill: 'var(--ink)', text: e => `${e.kind} ${hhmmAt(e.o, off)}–${e.cleared_at ? hhmmAt(e.c, off) : 'open'}` }),
        Plot.cell(cells, Plot.pointer({ x: 'hour', y: 'day', fill: 'none', stroke: 'var(--cells)', strokeWidth: 2 })),
      ].filter(Boolean),
    });
    el.append(svg);
    const read = document.getElementById(`${id}-read`);
    const idle = read ? read.innerHTML : '';
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
  const totals = (it.per_day || []).reduce((a, p) => ({ over: a.over + (p.over || 0), read: a.read + p.read,
    of: a.of + p.of }), { over: 0, read: 0, of: 0 });
  return `<div class="f-strips" data-kind="series" data-component="strips" id="${esc(id)}-card" data-ref="${esc(ref)}">`
    + `<p class="f-head"><span>${esc(name)} · ${esc(LAB[dist])} · ${D.days} days</span>`
    + `<span>shades ${esc(fmt(floor, dp))} to ${esc(fmt(hi0, dp))} ${esc(unit)}${line != null
      ? ` · <span class="f-line">the line ${esc(fmt(line, dp))}</span>` : ''}</span></p>`
    + fig(id, draw, { ref: `${id}-card`, component: 'stripsDrawing',
      label: `${name}, one row a day and one cell an hour over ${days.length} days` })
    + `<p class="f-read" id="${esc(id)}-read" aria-live="polite"><span data-num="${esc(key)}.days.over" data-cmp="`
    + `${esc(`of ${totals.read} hours read in ${days.length} days, ${totals.of - totals.read} not recorded`)}">`
    + `${totals.over} hours over the line</span><span class="f-gone">${totals.of - totals.read} not recorded · `
    + `point at a cell</span></p>`
    + `<p class="f-legend"><span class="f-lo"><i></i>low</span><span class="f-hi"><i></i>high, on this issue’s own scale</span>`
    + `<span class="f-red"><i></i>an hour over the line</span><span class="f-gap"><i></i>nothing recorded</span>`
    + `<span class="f-evc"><i></i>an alert event</span></p></div>`;
}
```

  Then add the new names to the export, so `window.K = { esc, fmt, ...` ends
  `..., evCard, evWord, fig, mountFigs, boxOf, offsetOf, hhmmAt, hourAt, dayAt, nearestIndex, PLOT_STYLE, dayFigure,
  strips };`.

- [ ] **Step 4: Mount after every render.** In `route()`, directly below `if (page) wireSat(page);`:

```js
  /* Figures are placeholders in the markup main() just wrote; the kit draws them now (kit 6 · figures). */
  if (page) window.K.mountFigs(page);
```

- [ ] **Step 5: The figures' style.** Append to `app/static/dashboard.css`:

```css
/* ================================================================= figures (kit 6 · docs/SPEC_dashboard_figures.md §4)
 * Every class here starts with f-: .ev, .band, .line, .read, .legend, .over and .gone already mean something on
 * this page. Ink for readings, red for the line and the hours over it, green only for an answer that closed a loop,
 * blue only for focus and the pointed cell. */
.f-day, .f-strips { margin: 12px 0 20px }
.f-head { display: flex; justify-content: space-between; gap: 12px; flex-wrap: wrap; margin: 0 0 2px;
  font: 500 12px var(--mono); color: var(--mute) }
.f-head .f-line { color: var(--signal-worse) }
.f-fig { position: relative; outline: none }
.f-fig:focus-visible { outline: 2px solid var(--cells); outline-offset: 2px }
.f-fig svg { display: block; max-width: 100%; height: auto }
.f-in { position: relative }
.f-hair { position: absolute; top: 0; bottom: 26px; width: 0; border-left: 1px solid var(--ink); opacity: .6;
  pointer-events: none }
.f-read { display: flex; flex-wrap: wrap; gap: 4px 16px; align-items: baseline; min-height: 20px; margin: 4px 0;
  font: 500 12.5px var(--mono); font-variant-numeric: tabular-nums }
.f-read .f-over { color: var(--signal-worse) }
.f-read .f-gone, .f-legend .f-gone { color: var(--dim) }
.f-read .f-usual { color: var(--mute) }
.f-read .f-done { color: var(--rings) }
.f-legend { display: flex; flex-wrap: wrap; gap: 4px 14px; margin: 2px 0 0; font: 500 10.5px var(--mono);
  letter-spacing: .04em; color: var(--mute) }
.f-legend i, .f-read i { display: inline-block; width: 12px; height: 0; border-top: 2px solid var(--ink);
  vertical-align: middle; margin-right: 5px }
.f-yard i { border-top-style: dashed }
.f-ring i { border-top-style: dotted }
.f-region i { border-top-style: dashed; opacity: .55 }
.f-rooms i { border-top-width: 3px }
.f-gone i { border-top-color: var(--dim) }
.f-band i { height: 8px; border: 0; background: var(--ink); opacity: .12 }
.f-over i { border-top-color: var(--signal-worse) }
.f-evl i { border-top-width: 5px; opacity: .25 }
.f-done i { width: 9px; height: 9px; border: 2px solid var(--rings); border-radius: 50% }
.f-lo i, .f-hi i, .f-red i, .f-gap i, .f-evc i { width: 9px; height: 9px; border: 0 }
.f-lo i { background: var(--ink); opacity: .15 }
.f-hi i { background: var(--ink) }
.f-red i { background: var(--signal-worse) }
.f-gap i { border: 1px solid var(--hair) }
.f-evc i { border: 1.5px solid var(--ink) }
.f-alt { font-size: 13px; color: var(--mute); line-height: 1.5; margin: 6px 0 0 }
@media (max-width: 600px) { .f-read { font-size: 11.5px; gap: 2px 12px } }
```

- [ ] **Step 6: Run the tests.**
  Run: `python3 tests/test_dashboard.py && make lint`
  Expected: the suite's final line, and lint `ok`. "THE PAGE LOADS" in the same suite is the check that nothing in
  the kit touches a browser global at load. If `tools/check_ui.py` objects to a rule in the new CSS block, follow its
  message without changing what a colour means.

- [ ] **Step 7: Commit.**

```bash
git add app/static/dashboard.js app/static/dashboard.css tests/test_dashboard.py
git commit -m "dashboard: the figures kit, Plot behind placeholders the shell mounts after every render

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: the day figure replaces the traces

**Files:**
- Modify: `app/static/dashboard.js` (the `day` section; the `measure` section's right column; delete `series`,
  `runs` and their `window.K` entry)
- Modify: `app/static/dashboard.css` (delete the series rules), `tests/test_dashboard.py` (the `runs` check, a new
  card check)

**Interfaces:**
- Consumes: `window.K.dayFigure` (Task 2).

- [ ] **Step 1: Write the failing test.** In `tests/test_dashboard.py`, replace the whole block that begins
  `# A hole in a series must be a hole in the line.` and ends with the `runs` assertions (the `if shutil.which("node"):`
  block that lifts `const runs`) with:

```python
# A hole in a series must be a hole in the line. Plot breaks a line at a null by itself (its lineY treats null as
# undefined), so the page keeps the nulls: what this holds is that the day figure hands the drawing the node's own
# 24 values, nulls and all, and says in words where the line breaks. See THE DAY FIGURE below.
```

  and, directly above the final `print(...)`, add:

```python
# THE DAY FIGURE AND THE STRIPS, as cards (docs/SPEC_dashboard_figures.md §4.2, §4.3). Built for node #1's 6 October
# capture, with /issues/days computed by the engine from the same capture, in the page loaded the way the browser
# loads it. The draw functions need Plot and a DOM and are not run; everything a reader can read without them is.
if shutil.which("node"):
    import datetime as _dt
    from issues import engine as _engine, load as _load

    class _Set:
        def get(self, k, d=""):
            return d

        def num(self, k, d):
            return d

    class _Cur:
        def __init__(self, snap):
            self.snap, self.rows = snap, []

        def execute(self, sql, args=()):
            if "current_setting('TimeZone')" in sql:
                self.rows = [{"tz": "Asia/Makassar"}]
            elif "FROM readings_1h" in sql:
                self.rows = [dict(r, bucket=_dt.datetime.fromisoformat(r["bucket"])) for r in self.snap["readings_1h"]
                             if _dt.datetime.fromisoformat(r["bucket"]) >= args[0]]
            elif "FROM alert_events" in sql:
                self.rows = []
            else:
                raise LookupError(sql[:60])

        def fetchall(self):
            return self.rows

        def fetchone(self):
            return self.rows[0] if self.rows else None

    _snap = json.loads((ROOT / "app/issues/fixtures/node1-2026-10-06-events.json").read_text())
    _rep = _engine.replay(json.loads(json.dumps(_snap)), _Set(), _load())
    _days = _engine.days(_Cur(_snap), _Set(), _load(), 1, now=_dt.datetime.fromisoformat(_snap["as_of"]))
    _over = sum(p["over"] for p in _days["issues"]["air"]["per_day"])
    _cards = _node(r"""(() => {
const fs = require('fs'), vm = require('vm');
globalThis.window = globalThis;
globalThis.localStorage = globalThis.sessionStorage = { getItem: () => null, setItem: () => {}, removeItem: () => {} };
globalThis.location = { search: '', hash: '', pathname: '/', href: 'http://node/' };
globalThis.document = { addEventListener: () => {}, getElementById: () => null, querySelector: () => null,
  querySelectorAll: () => [] };
globalThis.addEventListener = () => {};
globalThis.fetch = () => new Promise(() => {});
vm.runInThisContext(fs.readFileSync('app/static/dashboard.js', 'utf8'), { filename: 'dashboard.js' });
const I = """ + json.dumps(_rep, default=str) + r""", D = """ + json.dumps(_days, default=str) + r""";
globalThis.__I = I;
vm.runInThisContext("S = { issues: __I }; ISS = S.issues.issues; DIST = S.issues.distances; LAB = S.issues.labels.en; LOC = 'en';");
const K = window.K;
const air = K.dayFigure('air', I.issues.air), heat = K.dayFigure('heat', I.issues.heat);
const st = K.strips('air', D), none = K.strips('air', null), coast = K.strips('coast', D);
console.log(JSON.stringify({
  airFloor: /floor 0<\/span>/.test(air), airNeg: /floor -/.test(air), heatNotZero: /, not zero<\/span>/.test(heat),
  airDay: air.includes('data-num="air.day"'), events: (air.match(/(One event|\d+ events) in these hours/) || [''])[0],
  region: air.includes('region — no model'), usual: (air.match(/no usual band — [^<]*/) || [''])[0],
  keys: air.includes('tabindex="0"'), over: (st.match(/>(\d+) hours over the line</) || [])[1],
  stripsNum: st.includes('data-num="air.days.over"'), none, coast }));
})()""")
    assert _cards["airFloor"] and not _cards["airNeg"], "air draws from 0 and never below"
    assert _cards["heatNotZero"], "heat says its floor is not zero"
    assert _cards["airDay"] and _cards["keys"], "the day figure keeps air.day's comparison and can be read by keyboard"
    assert _cards["events"] == "2 events in these hours", _cards["events"]
    assert _cards["region"], "a distance with no source is named with its reason"
    assert _cards["usual"] == "no usual band — the usual could not be read", _cards["usual"]
    assert _cards["stripsNum"] and int(_cards["over"]) == _over, (_cards["over"], _over)
    assert "does not send its days yet" in _cards["none"], _cards["none"]
    assert "No hourly record of" in _cards["coast"], _cards["coast"]
```

- [ ] **Step 2: Run it.**
  Run: `python3 tests/test_dashboard.py`
  Expected: it passes already for the cards (Task 2 added the kit), and the `runs` check is gone. This step proves the
  test is wired before the section changes; Step 6 is where it guards the change.

- [ ] **Step 3: The `day` section draws the figure.** In the `day` module (`/* h/mods/day.js */`):
  - the destructuring line becomes `const { esc, dayFigure } = window.K;`
  - in `render`, replace `return barcode({ id: 'barcode', ref: 'days' })` and the `drawn.map(...)` that follows with:

```js
    return `<div class="days" id="days" data-ref="matrix-grid">`
      + drawn.map(k => `<div class="dayone" id="day-${esc(k)}" data-ref="days">`
        + `<p class="k">${esc(ISS[k].name[LOC])}</p>`
        + dayFigure(k, ISS[k], { id: `day-fig-${esc(k)}`, ref: `day-${esc(k)}` }) + `</div>`).join('')
      + `</div>`
```

    (keep the `silent` sentence after it unchanged). Task 4 adds the strips here and removes `barcode`.
  - the module's notes keep their text; replace the first note's text with: `'The trace says how high and the red
    ticks under it say how long. A brief spike and a long plateau can reach the same height, and only one of them is
    worth getting out of a chair for, so the hours over the line are counted in the line under the drawing. Point at an
    hour, or focus the drawing and use the arrow keys, to read every distance at that hour.'`

- [ ] **Step 4: Measure stops drawing a second copy.** In the `measure` module, its `render` ends
  `+ \`</div>${funnel()}${careLabel()}</div>\` + \`<div>${series(hk, ISS[hk])}</div></div>\`;`. Replace the second
  part with `+ \`<div id="measure-over-slot" data-ref="rho"></div></div>\`;` (Task 6 fills it) and remove `hk` and
  `series` from that closure if nothing else there uses them.

- [ ] **Step 5: Delete what nothing draws.** Delete `const runs = ...` and `function series(...)` (the block under
  `/* --------------------------------------------------------------------------- 3 · series */`, keeping
  `noLine` and `reasonFor`, which the figure uses), and remove `series` from the `window.K` export. In
  `app/static/dashboard.css`, delete the rules that style only `.series` and its children; keep `.legend` and `.alt`
  if any other selector still uses them (`grep -n 'class="legend"\|class="alt"' app/static/dashboard.js`).

- [ ] **Step 6: Run the tests and the gate.**
  Run: `python3 tests/test_dashboard.py && make lint && PAI_DESIGN_REPO=../planetai-design bash tests/visual/gate.sh`
  Expected: the suite passes; lint `ok`; the gate either passes or fails only on its two height/empty baselines,
  which Task 7 re-records on a new capture. Any other gate failure (a numeral with no comparison, a component with no
  link, "did not render") is a defect in this task: fix it here.

- [ ] **Step 7: Commit.**

```bash
git add app/static/dashboard.js app/static/dashboard.css tests/test_dashboard.py
git commit -m "dashboard: the day is drawn once, as one figure per issue with a readout in words

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: the strips, on Now and on Historical

**Files:**
- Modify: `app/static/dashboard.js` (`boot`, `refresh`, a lazy read beside `askSources`, `route`; the `day` and
  `shape` sections; delete `barcode`)
- Modify: `app/static/dashboard.css` (delete the `.barcode` rules)

**Interfaces:**
- Consumes: `window.K.strips` (Task 2); `GET /issues/days` and a capture's `issues_days` (part A).
- Produces: `window.DAYS` (7 days, refreshed at most every 15 minutes), `window.DAYS90` (up to 90 days, read the first
  time Historical is opened). Task 6 reads `window.DAYS`.

- [ ] **Step 1: Read the days in `boot`.** In `boot()`, the destructuring
  `const [trust, forecast, sensors, cells, reach, notes, dayshape, effect] = await Promise.all([` gains `days` at the
  end, and the array gains, after `api('/effect').catch(() => null),`:

```js
    /* The strips and Measure's count (docs/SPEC_dashboard_figures.md §4.3, §4.5). A capture carries the 7 days it was
       taken with; a node older than v0.79 answers 404, and the strips say so. */
    FIXTURE ? Promise.resolve((snapshot && snapshot.issues_days) || null) : api('/issues/days?days=7').catch(() => null),
```

  and below `window.EFFECT = effect;` add:

```js
  window.DAYS = days;
  window.DAYS_AT = Date.now();
  /* A capture holds one window; Historical draws what it holds. A live node is asked for 90 days on first use. */
  window.DAYS90 = FIXTURE ? days : null;
```

- [ ] **Step 2: Keep them fresh.** In `refresh()`, directly above `window.STALE = null;`:

```js
  /* The strips move by an hour at a time, so the days are read again at most every 15 minutes, not on every poll. */
  if (Date.now() - (window.DAYS_AT || 0) > 15 * 60e3) {
    window.DAYS = await api('/issues/days?days=7').catch(() => window.DAYS || null);
    window.DAYS_AT = Date.now();
  }
```

- [ ] **Step 3: Historical asks for 90 days once.** Directly below `function askSources() {...}`:

```js
/* Historical's strips reach as far back as the node holds, up to 90 days. Asked the first time Historical is drawn,
 * not at boot: a household that never opens Historical never pays for it. */
let DAYS90_ASKED = false;
function askDays90() {
  if (DAYS90_ASKED || FIXTURE || VIEW !== 'historical') return;
  DAYS90_ASKED = true;
  /* DAYS90_DONE is set either way, so a refusal draws the strips' own "does not send its days yet" line instead of
     "asking" for good. */
  api('/issues/days?days=90')
    .then(d => { window.DAYS90 = d; window.DAYS90_DONE = true; route(); })
    .catch(() => { window.DAYS90 = null; window.DAYS90_DONE = true; route(); });
}
```

  and in `route()`, below `askSources();`, add `askDays90();`.

- [ ] **Step 4: The strips on Now.** In the `day` module: destructure `strips` too
  (`const { esc, dayFigure, strips } = window.K;`), set `reads: ['/issues', '/issues/days']`, `learn: ['cards', 'raw',
  'figure']`, and in `render` add the strips under each figure:

```js
        + dayFigure(k, ISS[k], { id: `day-fig-${esc(k)}`, ref: `day-${esc(k)}` })
        + strips(k, window.DAYS, { id: `strips-${esc(k)}`, ref: `day-${esc(k)}` }) + `</div>`).join('')
```

  Then delete `function barcode(...)` and its comment block, remove `barcode` from the `window.K` export, and delete
  the `.barcode` rules in `dashboard.css`.

- [ ] **Step 5: The strips on Historical.** In the `shape` module:
  - destructure `strips` (`const { esc, fmt, strips } = window.K;`), set `reads: ['/issues/days', '/shape']`,
    `learn: ['shape', 'strips']`, and change `needs: ['SHAPE.hours']` to `needs: []`.
  - Replace the whole of `render(ctx) {...}` with:

```js
  render(ctx) {
    const S = window.SHAPE || {}, hours = S.hours || [];
    const D = window.DAYS90;
    /* The finding is an average and waits for a week; the strips are not an average and draw what there is. */
    const pin = peak(hours, 'indoor'), pout = peak(hours, 'outdoor');
    const finding = !S.windows || !S.windows.day
      ? `<p class="note" id="shape-young" data-component="absent" data-ref="reach">`
        + `This node has ${S.days === 1 ? 'one day' : `${S.days || 0} days`} of its own readings. `
        + `The usual hour of the worst air waits for seven — about ${Math.max(1, 7 - (S.days || 0))} more. `
        + `The days it has are drawn below as they were.</p>`
      : pin && pout
        ? `<p class="honest" id="shape-finding" data-component="finding" data-ref="shape">`
          + `Over ${S.days} days, the air in this house is worst around `
          + `<span data-num="shape.indoor.peak" data-cmp="against ${esc(fmt(pout.indoor, 1))} outside `
          + `at the same hour">${esc(hh(pin.hour))}</span> and the air outside is worst around `
          + `<span data-num="shape.outdoor.peak" data-cmp="against ${esc(fmt(pin.outdoor, 1))} inside `
          + `at the same hour">${esc(hh(pout.hour))}</span>`
          + `${pin.hour !== pout.hour ? ' — they do not peak together, so there are hours when '
            + 'opening a window helps and hours when it does not' : ''}.</p>`
        : '';
    if (DAYS90_PENDING()) {
      return finding + `<p class="note" id="shape-days" data-ref="shape">Asking the node for the days it holds…</p>`;
    }
    return finding + `<div id="shape-strips" data-ref="shape">`
      + ctx.ORDER.filter(k => ctx.ISS[k] && ctx.ISS[k].watched !== false)
        .map(k => strips(k, D, { id: `hstrips-${esc(k)}`, ref: 'shape-strips' })).join('')
      + `</div>`;
  },
```

  and above `window.PAI.register({` in that module add:

```js
/* Historical asks for its 90 days when it is first drawn (askDays90 in the shell), so for one render there is
   nothing yet. A live node that has not answered is pending; a capture (its days are set at boot), or a node that
   answered or refused (DAYS90_DONE), is not. */
const DAYS90_PENDING = () => !window.SNAP.fixture && !window.DAYS90_DONE;
```

  Delete the module's `plot()` function, which nothing draws now, and its `.shapeplot` CSS.
  Keep `peak`, `hh` and the three notes; replace the `shape-two-lines` note's first sentence with "The strips draw the
  house; the sentence above them compares inside and outside, which are apart because they are not the same day."

- [ ] **Step 6: Run the tests and the gate.**
  Run: `python3 tests/test_dashboard.py && make lint && PAI_DESIGN_REPO=../planetai-design bash tests/visual/gate.sh`
  Expected: as Task 3, Step 6. On the 6 October capture, which has no `issues_days`, Now draws each figure with the
  strips' "does not send its days yet" line under it; that is correct for that capture. Task 7 records one that has it.

- [ ] **Step 7: Commit.**

```bash
git add app/static/dashboard.js app/static/dashboard.css
git commit -m "dashboard: strips of hours, 7 days on Now and every day the node holds on Historical

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: the stations — a drawing per row, the event's rooms first, the stations that stopped

**Files:**
- Modify: `app/static/dashboard.js` (`bind`; the `sensors` module: `graphic` replaced by `spark`, `station`,
  `groups`, `render`, a fold)
- Modify: `app/static/dashboard.css` (the station row's drawing; the fold)

**Interfaces:**
- Consumes: `window.K.fig`, `offsetOf`, `hhmmAt`, `dayAt`, `PLOT_STYLE` (Task 2); `stations_silent`, `last_heard`,
  `events.open[].rooms` (part A).
- Produces: `window.H3.silent` (stations with `last_heard`); `window.H3.sensors` never contained them.

- [ ] **Step 1: Keep the stopped apart.** `stations` already holds only stations heard in the last day; the stopped
  ones arrive in `stations_silent.stations`. In `bind()`, `window.H3 = { ...geo, sensors: issues.stations || [], ...`
  keeps `sensors` unchanged and gains one key:

```js
  /* A station in stations_silent.stations stopped reporting (docs/SPEC_dashboard_figures.md §3.3). It is not a
     station this node reads now, so it is neither on the map nor in the groups; What the stations read lists it in a fold. */
  window.H3 = { ...geo, sensors: issues.stations || [], silent: (issues.stations_silent || {}).stations || [],
```

  (the rest of that object literal is unchanged).

- [ ] **Step 2: A drawing that answers a pointer.** In the `sensors` module, destructure
  `const { esc, fmt, age, cmpText, noLine, fig, offsetOf, hhmmAt, dayAt, PLOT_STYLE } = window.K;` and replace the
  whole of `function graphic(s, v, m, sc, line) {...}` (and its comment) with:

```js
/* A station's own day, inside its row (docs/SPEC_dashboard_figures.md §4.4): the hourly mean as a line and the hour's
 * spread as a band, on the one scale every row of the section shares (scaleFor), the issue's line where it applies,
 * and one tick at now for a station with no hourly series. An hour the station did not report is a gap: the series
 * lists only the hours it has, so the grid below puts a null in every hour between them. Pointing at it says that
 * hour in the row's own words. */
function spark(s, v, m, sc, line, id) {
  const ser = ((s.series || {})[v] || []).filter(b => b && b.t);
  const r15 = (s.read || {})[v];
  const T = ser.map(b => Date.parse(b.t)), off = offsetOf(ser.length ? ser[ser.length - 1].t : '');
  const grid = [];
  for (let t = T[0], i = 0; ser.length && t <= T[T.length - 1]; t += 3600e3) {
    const b = T[i] === t ? ser[i++] : null;
    grid.push({ t: new Date(t), mean: b ? b.mean : null, min: b ? b.min : null, max: b ? b.max : null });
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
    const idle = read ? read.innerHTML : '';
    svg.addEventListener('input', () => {
      const b = svg.value;
      if (!read) return;
      read.innerHTML = !b ? idle : b.mean == null ? `${esc(hhmmAt(+b.t, off))} nothing recorded`
        : `${esc(hhmmAt(+b.t, off))} ${esc(fmt(b.mean, m.dp))} (${esc(fmt(b.min, m.dp))} to `
          + `${esc(fmt(b.max, m.dp))}) ${esc(m.unit)}`;
    });
  };
  return fig(id, draw, { ref: `st-${s.sensor_id}`, component: 'stationDrawing',
    label: `${s.name || s.sensor_id}, ${m.label}: ${ser.length ? `${ser.length} hourly means` : 'one 15-minute mean at now'}` });
}
```

- [ ] **Step 3: The row uses it.** In `station(ctx, s, v, m, sc, L, ref)`:
  - the `alt` constant becomes (the day's high added, and an id the drawing writes into):

```js
  const hi = ser && ser.length ? Math.max(...ser.map(b => b.max).filter(x => x != null)) : null;
  const alt = ser && ser.length
    ? `<span class="alt" id="spark-${esc(s.sensor_id)}-${esc(v)}-read">opened the day at ${esc(fmt(ser[0].mean, m.dp))}, `
      + `closed at ${esc(fmt(ser[ser.length - 1].mean, m.dp))} ${esc(m.unit)} · high ${esc(fmt(hi, m.dp))}</span>` : '';
```

  - `<span class="pic">${r && sc ? graphic(s, v, m, sc, L.line) : ''}</span>` becomes
    `<span class="pic">${r && sc ? spark(s, v, m, sc, L.line, \`spark-${s.sensor_id}-${v}\`) : ''}</span>`
  - the event's rooms are named. Directly above `const meta = ...` add
    `const inEvent = (ctx.EVROOMS || new Set()).has(s.name);` and prefix `meta` with
    `${inEvent ? 'in the open event · ' : ''}`.

- [ ] **Step 4: The event's rooms first.** In `groups(ctx, ids)`, directly above `const own = ctx.N.chain[ctx.RES];`:

```js
  /* The rooms of an open event lead their cell (docs/SPEC_dashboard_figures.md §4.4): they are why a reader is here. */
  const rooms = ctx.EVROOMS = new Set((((ctx.S.issues || {}).events || {}).open || []).flatMap(e => e.rooms || []));
```

  and in the `ss:` sort, `.sort((a, b) => (a.km ?? Infinity) - (b.km ?? Infinity))` becomes
  `.sort((a, b) => (rooms.has(b.name) - rooms.has(a.name)) || (a.km ?? Infinity) - (b.km ?? Infinity))`.

- [ ] **Step 5: The stations that stopped.** In the `sensors` module, above `window.PAI.register({`:

```js
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
  const off = offsetOf((((ctx.ISS[ctx.ORDER[0]] || {}).buckets) || []).slice(-1)[0]);
  return `<details class="silentfold" id="sensors-silent" data-component="silentStations" data-ref="sensors-list">`
    + `<summary><b data-num="sensors.silent" data-cmp="stations heard in the last ${esc(String(st.within_days))} days `
    + `and not in the last day">${gone.length}</b> no longer heard</summary>`
    + gone.map(s => `<p class="row silent" data-kind="row" data-component="silentStation" id="st-gone-${esc(s.sensor_id)}"`
      + ` data-ref="sensors-silent"><span class="who"><b>${esc(s.name || s.sensor_id)}</b><span class="m">`
      + `${s.km == null ? 'distance unknown' : `${esc(String(s.km))} km`} · ${s.indoor ? 'indoor' : 'outdoor'} · `
      + `${s.url ? `<a href="${esc(s.url)}" target="_blank" rel="noopener">${esc(s.source)}</a>` : esc(s.source)}`
      + `</span></span><span class="said">last heard ${esc(dayAt(Date.parse(s.last_heard), off))} `
      + `${esc(hhmmAt(Date.parse(s.last_heard), off))}</span></p>`).join('')
    + `</details>`;
}
```

  and in `render`, `html += moreLine(ctx, cap) + \`</div>\`;` becomes
  `html += moreLine(ctx, cap) + silentFold(ctx) + \`</div>\`;`.

- [ ] **Step 6: Style.** In `dashboard.css`, below `.row.station .pic { min-width: 0 }`:

```css
.row.station .pic .f-fig { width: 100%; max-width: 240px }
.silentfold { margin: 10px 0 0; border-top: 1px solid var(--hair); padding-top: 8px }
.silentfold summary { cursor: pointer; font: 500 12px var(--mono); color: var(--mute) }
.silentfold .row.silent { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 12px; padding: 6px 0;
  border-bottom: 1px solid var(--hair); color: var(--mute) }
.silentfold .said { font: 500 12px var(--mono) }
```

- [ ] **Step 7: Run the tests and the gate.**
  Run: `python3 tests/test_dashboard.py && make lint && PAI_DESIGN_REPO=../planetai-design bash tests/visual/gate.sh`
  Expected: as Task 3, Step 6.

- [ ] **Step 8: Commit.**

```bash
git add app/static/dashboard.js app/static/dashboard.css
git commit -m "dashboard: each station row draws its day and answers a pointer; the stopped are kept in a fold

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: Measure counts the hours over the line

**Files:**
- Modify: `app/static/dashboard.js` (the `measure` module)

**Interfaces:**
- Consumes: `window.DAYS` (Task 4); `row`, `esc`, `fmt` from `window.K`.

- [ ] **Step 1: The rows.** In the `measure` module, above `window.PAI.register({`:

```js
/* Hours over the line, counted (docs/SPEC_dashboard_figures.md §4.5, after Bali Air Dispatch): how long, not how
 * high, which is what a household acts on. Today and the days GET /issues/days covers, from the node's own per-day
 * counts; an hour with nothing recorded is named beside them and never counted as clean. */
function overRows(ctx) {
  const D = window.DAYS;
  if (!D) {
    return `<p class="note" id="measure-over" data-ref="rho">This node does not send its days yet, so the hours over `
      + `the line are not counted here.</p>`;
  }
  const keys = ctx.ORDER.filter(k => D.issues[k] && D.issues[k].distance && D.issues[k].line);
  const sum = ps => ps.reduce((a, p) => ({ over: a.over + (p.over || 0), read: a.read + p.read, of: a.of + p.of }),
    { over: 0, read: 0, of: 0 });
  return `<div class="reads" id="measure-over" data-ref="rho">` + keys.map(k => {
    const it = D.issues[k], u = ctx.ISS[k];
    const t = sum(it.per_day.slice(-1)), w = sum(it.per_day);
    return row({ id: `measure-over-${k}`, component: 'overCount', ref: 'measure-over',
      cols: 'minmax(0,210px) minmax(0,1fr) auto',
      left: `<span class="who"><b>${esc(u.name[LOC])}</b><span class="m">${esc(ctx.LAB[it.distance])} · over `
        + `${esc(fmt(it.line.value, u.dp))} ${esc(u.unit)}</span></span>`,
      line: `Hours over the line today, and in these ${D.days} days.`,
      qty: [{ num: `${k}.over.today`, value: `${t.over} h`, cmp: `of ${t.read} hours read today, ${t.of - t.read} not recorded` },
        { num: `${k}.over.days`, value: `${w.over} h`, cmp: `of ${w.read} hours read in ${D.days} days, ${w.of - w.read} not recorded` }],
    });
  }).join('') + `</div>`;
}
```

  Make sure the module destructures `row`, `esc` and `fmt` from `window.K`, and that `ctx.LAB` exists; if the
  context does not carry `LAB`, use `window.K.LAB`.

- [ ] **Step 2: Draw them.** Replace the Task 3 placeholder `<div id="measure-over-slot" data-ref="rho"></div>` with
  `<div>${overRows(ctx)}</div>`, set the module's `reads` to `['/rho', '/issues', '/issues/days']`, and add one note:

```js
      { id: 'measure-over', label: 'How long, counted',
        text: 'A reading over the line for one hour and for nine are different days, and a curve does not say which. '
        + 'These rows count the hours the house was over the line, from the node’s own count per local day: today, '
        + 'and the days the strips above draw. An hour nothing was recorded is named beside the count, never counted as '
        + 'clean.' },
```

- [ ] **Step 3: Run the tests and the gate.**
  Run: `python3 tests/test_dashboard.py && make lint && PAI_DESIGN_REPO=../planetai-design bash tests/visual/gate.sh`
  Expected: as Task 3, Step 6.

- [ ] **Step 4: Commit.**

```bash
git add app/static/dashboard.js
git commit -m "dashboard: Measure counts the hours over the line, today and this week, from the node's own count

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: the docs, the learn marks, a capture, the gate, node #1, and the PR

**Files:**
- Modify: `docs/site/dashboard.md`, `docs/site/design.md`, `docs/GUI.md`, `CHANGELOG.md`, `docs/SPEC_dashboard_figures.md`
- Modify: `tools/build_learn.py`, `app/static/learn.json` (generated)
- Create: `app/issues/fixtures/node1-<date>-figures.json`; modify `tests/visual/gate.sh`

- [ ] **Step 1: `docs/site/dashboard.md`.** Add two sections directly before `## Issues, states and distances`:

```
## The day figure

Each issue with a day has one drawing of its last 24 hours. Every distance is a trace in ink, dashed by distance, and
an hour nothing was recorded is a gap in it, never a line drawn across. The grey band is the usual for each hour,
from the node's own last 14 days. The red dashed line is the issue's line and the red ticks under the drawing are the
hours over it. An alert event is a bar from when it opened to when it cleared, and its answer is a ring: green for
Done. When an event is open, its own rooms are a heavier trace beside the house. Point at an hour, or focus the
drawing and use the arrow keys, and the line under it says that hour in words.

## The strips

One row a day and one cell an hour, the newest day at the bottom: seven days on Now under each day figure, and every
day the node holds on Historical. A darker cell is a higher reading on that issue's own scale, a red cell is an hour
over the line, and an outlined empty cell is an hour nothing was recorded. The column on the right is the node's own
count of hours over the line that day. An alert event outlines the hours it was open.
```

  In `## The sections`, the sentence about "The day this place usually has" becomes: "\"The day this place usually
  has\" draws the strips of every day this node holds (up to 90, `GET /issues/days?days=90`), and above them, once it
  has 7 local days, the hour inside and the hour outside are worst (`GET /shape`)." Add one sentence to Measure's
  description: "Measure counts the hours over the line, today and this week, from the node's own count." Add one to
  What the stations read: "Each row draws its day and answers a pointer; a station that stopped reporting in the last
  30 days is listed in a fold, with when it was last heard."

- [ ] **Step 2: `docs/site/design.md`.** After the "Four card kinds and no fifth" section, add:

```
## Drawn with Plot

The figures are drawn with Observable Plot 0.6.17 and the d3 7.9.0 it is built on, served by the node as two static
files (ISC; `app/static/licences/`), so the page draws on a network with no route out. `data/vendor.sha256` pins both
and `make lint` checks them. Plot draws marks; the layer's rules still decide them: ink for readings, red for the line
and the hours over it, green only for an answer that closed a loop, blue only for focus. A figure is a `series` card,
so the four card kinds stay four.
```

- [ ] **Step 3: `docs/GUI.md`.** The bullet `**The day this place just had** — ...` becomes:
  `**The day this place just had** — one drawing per issue of the last 24 hours at every distance, with the usual for
  each hour, the hours over the line, and the alert event and its answer, and under it a strip of the last seven days,
  one cell an hour. Point at an hour to read it in words.`

- [ ] **Step 4: The learn marks.** In `tools/build_learn.py`, add to `MARKS`, directly after the `("shape", ...)`
  entry:

```python
    ("figure", "The day, drawn once", "dashboard.md", "The day figure",
     "Each issue with a day has one drawing", "that hour in words.",
     "The figure reads the node's own 24 hourly values for every distance, the usual for each hour from "
     "usual_by_hour, and the alert events from /issues. The page draws them and computes none of them."),
    ("strips", "One row a day, one cell an hour", "dashboard.md", "The strips",
     "One row a day and one cell an hour", "the hours it was open.",
     "The strips read GET /issues/days: the same hourly values the lead uses, over up to 90 days, with the node's "
     "own count of hours over the line for each day."),
```

  and to the questions table, directly after `'shape': {...},`:

```python
    'figure': {"en": ['What does the grey band mean?', 'Which hours were over the line today?'],
        "id": ['Apa arti pita abu-abu itu?', 'Jam berapa saja yang melewati garis hari ini?'],
        "es": ['¿Qué significa la banda gris?', '¿Qué horas pasaron la línea hoy?']},
    'strips': {"en": ['At what hour is the air usually worst here?', 'Which days were over the line?'],
        "id": ['Jam berapa udara biasanya paling buruk di sini?', 'Hari apa saja yang melewati garis?'],
        "es": ['¿A qué hora suele estar peor el aire aquí?', '¿Qué días pasaron la línea?']},
```

  Then run `python3 tools/build_learn.py` to rewrite `app/static/learn.json`.

- [ ] **Step 5: Correct the spec to what was built.** In `docs/SPEC_dashboard_figures.md`:
  - §4.4 "**Facets.** One Plot per variable, one row per station, …" becomes "**A drawing per row.** Each station row
    draws its day with Plot, on the one scale every row shares (the band is the hour's spread, the line the hourly
    mean, the issue's line where it applies), and answers a pointer. The tabs and the fold to eight stay."
  - §4.5 "hours over the line in the last 24 hours and the last seven days" becomes "hours over the line today (the
    node's local day) and in the days `/issues/days` covers", because the node counts per local day.
  - §4.3 "**Distance.** The hero distance by default; a switch lists the other distances that have data in the
    window." becomes "**Distance.** The hero distance, the one the lead's numeral reads. A switch to the street or the
    ring waits until a reader asks for it: `/issues/days` already carries every distance, so it is a page change only."
  - §4.1 "`make lint` checks that no class Plot emits matches a theme binding class" becomes "Every class the page
    writes for a figure starts with `f-`, and Plot's own are `plot-` and a hash, so neither can meet a theme binding
    class (`.ring`, `.cell`, `.sat`, `.label`)."

- [ ] **Step 6: `CHANGELOG.md`.** Under `## Unreleased`:

```
- The dashboard draws each issue's day once, as one drawing you can point at: every distance, the usual for each hour,
  the hours over the line, the alert event and its answer, and the event's own rooms, with the hour read out in words
  (the arrow keys work too). Under it, a strip of the last seven days, one cell an hour; Historical draws every day
  the node holds. Each station row draws its day, and a station that stopped reporting is kept in a fold with when it
  was last heard. Measure counts the hours over the line. The drawings use Observable Plot, served by the node itself.
```

- [ ] **Step 7: A capture with the days.** Part A is on node #1 by now. Take a capture and add it as a fixture:

```bash
ssh mini 'export PATH="/opt/homebrew/bin:/usr/local/bin:$HOME/.local/bin:$PATH"; cd ~/planetai/planetai-node && planetai snapshot --out /tmp/figures.json'
scp mini:/tmp/figures.json "app/issues/fixtures/node1-$(date +%Y-%m-%d)-figures.json"
python3 -c "import json,sys; d=json.load(open(sys.argv[1])); assert d.get('issues_days') and d['issues'].get('stations_silent'), 'not a v0.79 capture'; print(sorted(d['issues_days']['issues']))" app/issues/fixtures/node1-*-figures.json
```

  Expected: the declared issues printed. The snapshot already removes the households' notes; read the file's
  `provenance` block before committing it, as every committed fixture was.

- [ ] **Step 8: The gate reads it.** In `tests/visual/gate.sh`, replace the three `fixture=node1-2026-10-06-events`
  with the new fixture's name, run `PAI_DESIGN_REPO=../planetai-design bash tests/visual/gate.sh`, and read the two
  page heights and empty shares it reports. Set `HEIGHT_SHIPPED` and `EMPTY_SHIPPED` to them, and above those lines add
  one comment line in the file's own form: `// Previous, on node1-2026-10-06-events: 390: 13294 px / 44.7%, 1440:
  8728 px / 55.1%.` and one line saying what moved and why (the strips add seven rows per issue; the barcode and
  Measure's trace are gone). Run the gate again: it must pass.

- [ ] **Step 9: See it on node #1 before merging.** Serve the branch's page into node #1's live page and read every
  section for "did not render" (memory: "Dashboard sections are separate closures"). From the worktree, with node #1
  reachable at `192.168.4.190:8081`:

```bash
cat > /tmp/live-swap.mjs <<'EOF'
import { chromium } from '../planetai-design/node_modules/playwright/index.mjs';
import fs from 'fs';
const S = 'app/static', b = await chromium.launch(), p = await b.newPage({ viewport: { width: 1440, height: 1200 } });
const errors = []; p.on('pageerror', e => errors.push(e.message)); p.on('console', m => m.type() === 'error' && errors.push(m.text()));
for (const f of ['dashboard.js', 'dashboard.css', 'd3.min.js', 'plot.umd.min.js', 'learn.json'])
  await p.route(`**/static/${f}*`, r => r.fulfill({ body: fs.readFileSync(`${S}/${f}`), contentType: f.endsWith('.css') ? 'text/css' : f.endsWith('.json') ? 'application/json' : 'application/javascript' }));
await p.route(/:8081\/(\?.*)?$/, r => r.fulfill({ body: fs.readFileSync(`${S}/index.html`), contentType: 'text/html' }));
for (const v of ['now', 'historical']) {
  await p.goto(`http://192.168.4.190:8081/?view=${v}`); await p.waitForTimeout(4000);
  const text = await p.innerText('body');
  console.log(v, { didNotRender: /did not render/.test(text), figures: await p.locator('.f-fig svg').count() });
  await p.screenshot({ path: `/tmp/live-${v}.png`, fullPage: true });
}
console.log({ errors });
await b.close();
EOF
node /tmp/live-swap.mjs
```

  Expected: `didNotRender: false` on both views, a non-zero figure count, no errors. Look at both screenshots.

- [ ] **Step 10: Gates and commit.**
  Run: `python3 tools/build_learn.py --check && python3 tools/check_docs.py && make lint && make test && PAI_DESIGN_REPO=../planetai-design bash tests/visual/gate.sh`
  Expected: no `x`, lint `ok`, every suite passes, the gate passes.

```bash
git add docs CHANGELOG.md tools/build_learn.py app/static/learn.json app/issues/fixtures tests/visual/gate.sh
git commit -m "docs, learn marks and the visual gate for the day figure and the strips, on a v0.79 capture of node #1

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

- [ ] **Step 11: The pull request.** Push and open it against `main`, milestone `v0.79`, label `needs testing`. The
  body says what a household sees, names the spec and the plan, lists the gate's old and new baselines with the
  reason, attaches the two node #1 screenshots from Step 9, and ends with
  `🤖 Generated with [Claude Code](https://claude.com/claude-code)`. If `fabcity/planetai-node#176` (the Singapore
  dashboard fixes) merged first, rebase on it and run the gate again. Do not merge: Tomas merges.

- [ ] **Step 12: After Tomas merges, on node #1 and node #3** (`docs/WORKFLOW.md` §2): `planetai update` on both, then
  open each node's dashboard. Point at an hour of each figure; press Tab to a figure and use the arrow keys; switch to
  Historical and see the strips reach as far back as the node holds; switch the register to Dark. Swap the label to
  `tested: node 1` (and `node 3`) and leave one comment saying what you saw.
