# Dashboard events, part B: the page tells the bot's story — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Now opens on the open alert events (one card each, with the action the bot sent and Done / Not now /
Doesn't fit), the rest of the page becomes the evidence, and the old engine's alert volume stops reaching the page.

**Architecture:**
- **One server task first** (Task 1, its own PR in v0.77): `uncovered_asks` stops counting the old alerts of the
  packs the engine replaced.
- **Everything else is the page.** That is `app/static/dashboard.js`, `dashboard.css`, and the docs and gates
  that describe the page (v0.78).
- **The event helpers go on `window.K`.** They are shared by the Decide section, the Act section and the lead (the
  sections are separate closures).
- **The posting function sits at column 0,** beside `didThis`, so `tests/test_dashboard.py` can lift it the same
  way.

**Tech stack:** vanilla JS in one file (no build step, no framework), CSS on the frozen programme layer's tokens,
Python gates (`tools/check_ui.py`, `tools/build_learn.py`), Node-run lifts in `tests/test_dashboard.py`, and
Playwright in `tests/visual/`.

**Spec:** `docs/SPEC_dashboard_events.md`. Part B is §4 and §5. §3 is the wire it reads, already on `main`
(#186, `9e732d7`). Read §4 and §5 in full before Task 2.

## What part A left that the page reads (on `main`)

`GET /issues` → `events`: `null` on a node older than v0.77, or

```
{engine: "rules"|"shadow"|"events", error?: str, buttons: {done, not_now, doesnt_fit},
 open:   [{id, issue, kind, level, opened_at, last_seen_at, cleared_at:null, peak, line, rooms, places,
           context: {usual, outside, outside_metric, outside_from}, action: {id, text}|null,
           message: {text, ts, sent}|null, alerts: [ids], answer: {stage, actor, ts, held_until}|null}],
 recent: [...the same, no context, cleared in 7 days, + cleared_after_min on a Done],
 cleared_today, last_cleared: {issue, ts}|null, uncovered_asks: [ids]}
```

- `lead.by` is `event` when an open event's issue leads.
- `POST /actions {event_id, stage: acted|acknowledged|dismissed, actor, note}`.
- `GET /actions?events=1` adds the event rows with `event_id`.

**Seen on the nodes, 5 Oct after the update:**
- Node #1 (`events`) had 0 open, 1 recent (air danger, covering 5 rows) and `uncovered_asks` 246.
- Node #3 (`shadow`) had 0 open, 1 recent, and `uncovered_asks` 94.

The 246 is the reason Task 1 exists.

## Rulings this plan makes (Tomas to confirm or overturn at review)

1. **`uncovered_asks` leaves out the old alerts of every pack that ships a kinded rule, on `shadow` and `events`.**
   Spec §4.2 meant uncovered asks to be the few that no event owns (`nearby/only_here`). Node #1 has 246, because the
   old heat and air rules' alerts from before any event existed are covered by none. Under decision 3 ("events
   replace alerts everywhere on the page"), they aren't asks on an events node.
   - If wrong: a shadow node's page stops showing the real alerts the old engine still sends. The bot still sends
     them.
2. **On a `rules` node, an older node, or a node whose events could not be read, Decide keeps today's card,
   including "Decide about this", and gains I did this.** Spec §4.2 removes the Decide form, but
   `DECISION_REQUIRED=1` would then make every alert act on such a node a 409 with nowhere to decide.
   - If wrong: those nodes keep one more button than the spec drew.
3. **The event card's evidence links jump to the sections, and don't mark the event's rooms inside them.**
   - If wrong: the stations section needs a marked state later.
4. **"What did you do instead?" is English.** The wire carries the three button labels, not the bot's question.
   - If wrong: one more key on `events.buttons`.
5. **The rail's `data-ref` moves from `grain-line` to `ground-figure`,** because "What each rung is worth" leaves Now.
   The ground is what the rail re-derives on Now.

## Global constraints

- Work in your own git worktree. This plan's is `planetai-node-page`, on branch `dashboard-events-page-2026-10-05`
  off `origin/main` `9e732d7`. Never use `planetai-node-main`.
- Task 1 is its own PR, with milestone **v0.77** and the `needs testing` label. Tasks 2–11 are one PR, with
  milestone **v0.78** and `needs testing`. `docs/NEXT_RELEASE.md` rule 2: page changes ship apart from packs.
- **Frozen layer.** Never edit `app/static/planetai-theme.css`, `signs.svg` or `kilometre-cells.json`.
- **Class names:** don't use the theme's SVG classes (`.ground .land .cell .chain .lit .ring .hair .fig .label .sat
  .veg`) or the page's existing ones for new markup. New classes in this plan are `ev`, `evhead`, `evnum`, `evcmp`,
  `evact`, `evbtns`, `evb`, `evform`, `evmsg`, `evlinks`, `evrows`, `evdone`, `evheld`, `evnone`, `evrow`, `evrec`
  and `evmore`. Check each against `grep -n "\.<name>\b" app/static/*.css` before use.
- **Closures:** a helper used by more than one section goes on `window.K`: define it beside `rulePack` (about
  line 928), add it to the `window.K = {…}` export, and destructure it where used.
- **Words from the node.** The action, the message, the button labels and the ρ figures come from the wire. The page
  computes no number and composes no advice. A number on the page carries `data-num` and `data-cmp` (the visual
  gate counts any that don't).
- **Absence has five shapes on Decide** (spec §5): an event open; nothing open; `rules`; older (`events` null);
  `events.error`. None of them is drawn as a zero or a blank.
- **Never uppercase the node's words.** A new `text-transform: uppercase` fails `check_ui` unless it is added to
  `UPPERCASE_KNOWN`. Don't add one.
- No `µ` in CSS, and none in `dashboard.js` outside a `.said` line. No SMIL anywhere.
- `make lint && make test` before every commit. The hook runs both, and a commit takes about two minutes.
- **Prove a change on a node, not only in the rig.** Serve the new `dashboard.js` from node #1, with read-only
  checks. A real button press needs Tomas's go.

## Files

| file | change |
|---|---|
| `app/issues/engine.py`, `tests/test_events_wire.py` | Task 1: `uncovered_asks` without the replaced packs' alerts |
| `app/static/dashboard.js` | Tasks 2–8 |
| `app/static/dashboard.css` | the event card, the record row, the held state, the compact rail |
| `tests/test_dashboard.py` | lifts for the new helpers and for `answerEvent` |
| `tests/visual/gate.sh`, `tests/visual/measure.mjs` | the ruler check reads the fold; the new baseline; the new fixture |
| `tools/build_learn.py`, `app/static/learn.json`, `data/docs_site.json` | the new marks, regenerated with `make learn` |
| `app/issues/fixtures/node1-<date>-events.json` | a capture with an open event (Task 10) |
| `docs/site/dashboard.md`, `docs/GUI.md`, `CHANGELOG.md` | the page as it now reads |

---

### Task 1: `uncovered_asks` leaves out the replaced packs' alerts (server, PR to v0.77)

**Files:** modify `app/issues/engine.py` (the `uncovered_asks` block in `compute`); test in
`tests/test_events_wire.py` (above its last `print`).

**Interfaces:**
- Produces: on `shadow` and `events`, `events.uncovered_asks` holds only open asks whose rule's pack ships no kinded
  rule.
- On `rules`, it is unchanged (there, no events stand in for anything).

- [ ] **Step 1: The failing test.** Replay `node1-2026-09-21d` with an injected block as Task 4 of part A did, with
  `engine: "events"` and `open: []`. Assert that `uncovered_asks` contains no id whose `rule_id` starts with
  `heat/` or `air-quality/`.
  - Assert that `engine: "rules"` still lists every open ask.
  - If the fixture's open asks are all heat and air, assert `uncovered_asks == []` under `events`.

```python
snap2 = json.loads(json.dumps(SNAP))
snap2["issues"]["events"] = {"engine": "events", "buttons": {}, "open": [], "recent": [], "cleared_today": 0,
                             "last_cleared": None}
ev = engine.replay(snap2, Settings(), DECLS)
rule_of = {a["id"]: a["rule_id"] for v in ev["issues"].values() for a in (v.get("open_asks") or [])}
owned = ("heat/", "air-quality/")
assert not [i for i in ev["events"]["uncovered_asks"] if rule_of[i].startswith(owned)], ev["events"]["uncovered_asks"]
snap2["issues"]["events"]["engine"] = "rules"
assert sorted(engine.replay(snap2, Settings(), DECLS)["events"]["uncovered_asks"]) == sorted(rule_of), "rules: all"
print("  uncovered_asks: on shadow and events, the replaced packs' old alerts are not asks; on rules they are")
```

- [ ] **Step 2: Run it and watch it fail.** Run `PACKS_DIR=packs PYTHONPATH=app python3 tests/test_events_wire.py`.
  It fails on the first new assert.
- [ ] **Step 3: The change.** In `compute`, replace the `uncovered_asks` comprehension with:

```python
        # The packs the engine replaced: any pack that ships a kinded rule. On shadow and events their old
        # rules' alerts are what the events stand for, so they are never asks of their own on the page.
        # app/main.py run_rules draws the same line when it stops those rules sending (#184).
        owned = ({r["id"].split("/", 1)[0] for r in packs.load_rules() if r.get("kind")}
                 if events.get("engine") in ("shadow", "events") else set())
        events = {**events, "uncovered_asks": [
            a["id"] for v in out.values() for a in (v.get("open_asks") or [])
            if a.get("id") is not None and a["id"] not in covered
            and str(a.get("rule_id") or "").split("/", 1)[0] not in owned]}
```

  `packs` is already imported in `engine.py`. Confirm with `grep -n "^import packs\|^from .* import packs"
  app/issues/engine.py`, and import it the way the module already does if it isn't.
- [ ] **Step 4: Run it and watch it pass.** Then run `make lint && make test`.
- [ ] **Step 5: Docs and the CHANGELOG.**
  - In `docs/site/api.md`, the `uncovered_asks` clause gains: "on `shadow` and `events`, leaving out the alerts of
    the packs the engine replaced".
  - In spec §3.1, the `uncovered_asks` bullet gets the same clause.
  - Add a CHANGELOG `Unreleased` line.
- [ ] **Step 6: Commit and open the PR** (milestone v0.77, `needs testing`). The commit message:
  `events: uncovered_asks leaves out the alerts of the packs the engine replaced`.
- [ ] **Step 7: After the merge,** update node #1. Read `/issues` and check that `events.uncovered_asks` falls from
  246 to the alerts of rules no event owns.

---

### Task 2: the event helpers on `window.K`

**Files:** modify `app/static/dashboard.js` (the kit, beside `rulePack`, about line 928, and the `window.K` export);
test in `tests/test_dashboard.py`.

**Interfaces (Produces):**
- `K.evState()`: `'events' | 'shadow' | 'rules' | 'old' | 'error'`, from `S.issues.events`. The value is `'old'`
  when the key is absent or null, and `'error'` when `events.error` is set.
- `K.evClock(iso)`: `HH:MM` in the node's zone (`S.health.tz`), using the same `Intl.DateTimeFormat` call as
  `asof()`. It falls back to `HH:MM UTC`.
- `K.evOpen()`: `S.issues.events.open`, or `[]`.
- `K.evButtons(e)`: the three buttons and the Doesn't-fit and name form, for an event row.
- `K.evCard(e)`: the whole event card (spec §4.2).

- [ ] **Step 1: The failing test.** In `tests/test_dashboard.py`, beside the `_pill` lift, lift `esc`, `fmt`,
  `evState`, `evClock`, `evButtons` and `evCard` by regex, the way `_pill` is lifted. Run them with a stub `S` and
  `ISS` and assert:
  - `evState()` gives `'old'` with no key, `'error'` with `{error: 'x'}`, and otherwise the engine.
  - `evCard` on an open `sustained` heat event with `context: {usual: 33.4, outside: 29.1, outside_metric: 'temp',
    outside_from: 'outside'}` and `line: 35`:
    - the markup holds `data-num="ev.<id>.peak"` with a `data-cmp` that names usual, outside and the line;
    - the action text appears as given;
    - there are three buttons whose text is `S.issues.events.buttons`;
    - the message text is escaped;
    - `would have sent` appears when the engine is `shadow`, and `sent` when it is `events` and `message.sent` is
      true.
  - With `answer: {stage: 'acted', actor: 'tomas', ts}`, the buttons are gone and `evdone` with `tomas` is present.
  - With `answer.stage: 'acknowledged'` and `held_until`, the card has `evheld` and the words `held until`, and the
    buttons are still there.
  - With `peak > line`, the numeral carries `class="evnum worse"`, and doesn't otherwise.
- [ ] **Step 2: Run it and watch it fail.** Run `PACKS_DIR=packs PYTHONPATH=app python3 tests/test_dashboard.py`.
  The regex finds no `evState`.
- [ ] **Step 3: Write the helpers.** Each one is a top-level `const` or `function` at column 0 in the kit, closed
  with `\n}` or `\n};`, so the lift regex works.

```js
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
function evCard(e) {
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
  const done = a && a.stage === 'acted';
  const answered = !a ? '' : `<p class="${done ? 'evdone' : 'evheld'}">`
    + `${done ? sign('rho-closed', 'closed') : ''}${esc(a.stage === 'acted' ? 'Done'
      : a.stage === 'dismissed' ? 'Doesn’t fit' : 'Not now')} · ${esc(a.actor || 'somebody')}`
    + ` · ${esc(evClock(a.ts))}${a.held_until ? ` · held until ${esc(evClock(a.held_until))}`
      + ` unless it reaches danger` : ''}</p>`;
  const rows = (e.alerts || []).length;
  return `<section class="ev${a && a.stage === 'acknowledged' ? ' held' : ''}" id="ev-${esc(String(e.id))}"`
    + ` data-component="event" data-role="ask" data-ref="num-${esc(e.issue)}">`
    + `<div class="evhead">${h.sign ? `<svg class="sgn" viewBox="0 0 24 24" role="img" aria-label="`
      + `${esc(d.name[LOC] || e.issue)}"><use href="static/signs.svg#${esc(h.sign)}"/></svg>` : ''}`
    + `<b>${esc(d.name[LOC] || e.issue)}</b> · ${esc(e.kind)} · since ${esc(evClock(e.opened_at))}`
    + `${(e.rooms || []).length ? ` · ${esc(e.rooms.join(', '))}` : ''}`
    + `${st === 'shadow' ? `<span class="m">shadow — nothing was sent</span>` : ''}</div>`
    + `<p class="evcmp"><span class="evnum${worse ? ' worse' : ''}" data-num="ev.${esc(String(e.id))}.peak"`
    + ` data-cmp="${esc(cmp)}">${esc(n(e.peak))}</span> ${esc(unit)} peak <small>${esc(cmp)}</small></p>`
    + (e.action && e.action.text ? `<p class="evact said">${esc(e.action.text)}</p>`
      : `<p class="evact none">The node chose no action for this event, and this page will not invent one.</p>`)
    + answered + (done ? '' : evButtons(e)) + said
    + `<p class="evlinks">evidence: <a href="#matrix">${esc(d.name[LOC] || e.issue)} at every distance</a>`
    + ` · <a href="#day">the day</a> · <a href="#sensors">the stations</a>`
    + (rows ? ` · <a href="#evrows-${esc(String(e.id))}">from ${rows} rule row${rows === 1 ? '' : 's'}</a>` : '')
    + `</p></section>`;
}
```

  Then add `evState, evOpen, evClock, evButtons, evCard` to the `window.K = { … }` export.
  - **Before using any id,** check it exists on Now: `matrix`, `day` and `sensors` are section ids
    (`<section class="band" id="${s.id}">`).
  - **Escape the unit:** `unit` is the node's, so it goes through `esc` (a `µ` in it is the node's word, not the
    stylesheet's).
  - **The `#evrows-<id>` anchor** is drawn by Task 4, inside the card. Until then the link points nowhere, which is
    harmless: the gate counts components, not hrefs.
- [ ] **Step 4: The CSS.** In `app/static/dashboard.css`, the card uses the readout's spacing and the existing tokens
  only:
  - `.evnum` is set like `.readout`'s numeral, in `var(--mono)`;
  - `.evnum.worse { color: var(--signal-worse) }`;
  - `.ev.held` sits at the muted ink;
  - `.evdone`'s ring sign is `var(--loop-closed)`;
  - `.evbtns` and `.evb` take the `.go` button's box, with `.evb.pri` ink-filled and the rest ink-outlined, none of
    them green;
  - `.evmsg .said` is `white-space: pre-line`, small.
  Copy the values from the rules the page already has for `.decide`, `.go` and `.readout`, and don't introduce a
  colour or a radius.
- [ ] **Step 5: Run the test and watch it pass,** then `make lint` (`check_ui`: no new uppercase, no `µ`, no new hex).
- [ ] **Step 6: Commit:** `dashboard: the event card and its helpers, on window.K`.

---

### Task 3: pressing a button

**Files:** modify `app/static/dashboard.js` (the shell, beside `didThis`, about line 7679); test in
`tests/test_dashboard.py`.

**Interfaces:**
- Consumes: `K.evButtons` markup (`.evb[data-ev][data-stage]`, `form.evform[data-ev]`).
- Produces: `async function answerEvent(id, stage, actor, note)` at column 0, plus the click and submit handlers.

**How it behaves:**
- **Done and Not now post at once** when the browser has a name (`localStorage planetai_actor`, read in try/catch).
  With no name stored, they open the form with only the name field.
- **Doesn't fit always opens the form,** with the optional "What did you do instead?" note.
- **After a post that the node accepts,** the name is stored. The page says "Recorded." for Done, "Not now. The node
  holds this for three hours, unless it reaches danger." for Not now, and "Noted: it doesn't fit." for Doesn't fit.
  Then it calls `await refresh()`.
- **Refusals print the node's own sentence:**
  - 401 and 403: `nodeSaid` plus the token hint, as `didThis` does;
  - 404: "This node has no such event any more. Reload and look again.";
  - 400: the node's sentence.
- **A fixture refuses,** as the existing `submit` listener does for `form.did`, with the same sentence.

- [ ] **Step 1: The failing test.** Copy the `_did` harness in `tests/test_dashboard.py` (around line 700) into a
  new `_ans` harness:
  - Lift `nodeSaid` and `answerEvent` by `re.search(r"async function answerEvent\(id, stage, actor, note\)
    \{.*?\n\}", _js_raw, re.S)`.
  - Stub `fetch`, `auth_`, `say`, `refresh`, and a `localStorage` with `getItem` and `setItem`.
  - Assert that the body posted is `{"event_id": 7, "stage": "acknowledged", "actor": "ana", "note": ""}`, a
    number id.
  - Assert that a 200 stores `ana`, and that 404, 401 and 400 print what is described above.
- [ ] **Step 2: Run it and watch it fail.**
- [ ] **Step 3: Write it,** at column 0 beside `didThis`:

```js
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
```

  **The handlers.**
  - In the existing `click` listener, before the `.ask .go` branch:
    - `.evb` reads the stored name. If the stage is `dismissed` or no name is stored, it shows its card's
      `form.evform`, sets the hidden `stage`, prefills `actor`, shows `.instead` only for `dismissed`, and focuses
      the first empty field.
    - Otherwise it refuses on a fixture (`FIXTURE || STATE !== 'populated'`, with the existing sentence), and if not,
      calls `answerEvent`.
    - `form.evform .cancel` hides the form.
  - In the `submit` listener, add `form.evform`. It gets the same fixture refusal, then
    `answerEvent(form.dataset.ev, form.elements.stage.value, actor, note)`, and on `true` hides the form.
  - Disable the pressed button while the post is in flight.
- [ ] **Step 4: Run it and watch it pass.** Then `make lint && make test`.
- [ ] **Step 5: Commit:** `dashboard: Done, Not now and Doesn't fit post to /actions by event`.

---

### Task 4: Decide is the open events

**Files:** modify `app/static/dashboard.js`, the `decide` section (about lines 4935–5060).

**Interfaces:**
- Consumes: `K.evState`, `K.evOpen` and `K.evCard` (Task 2), and `S.issues.events.uncovered_asks`.
- Produces: the `decide` section's render, in the five states.

- [ ] **Step 1: The test.** A source-level check in `tests/test_dashboard.py`: the `decide` section's render
  references `evCard(` and `uncovered_asks`, and no longer draws `Decide about this` outside the `rules`/`old`/`error`
  branch. Lifting the section needs the whole closure, so this one is a source check plus Task 11's live proof.
- [ ] **Step 2: Rewrite `render(ctx)`:**

```js
  render(ctx) {
    const ISS = ctx.ISS, st = evState(), E = ctx.S.issues.events || {};
    const asks = k => (ISS[k] && ISS[k].open_asks) || [];
    if (st === 'events' || st === 'shadow') {
      const unc = new Set(E.uncovered_asks || []);
      const left = ctx.ORDER.flatMap(k => asks(k).filter(a => unc.has(a.id)).map(a => card(ctx, k, ISS[k], a, true)));
      const open = evOpen();
      if (!open.length && !left.length) {
        const last = E.last_cleared;
        return `<p class="note evnone" id="decide-none" data-component="absent" data-ref="stage-decide">`
          + `Nothing open.${E.cleared_today ? ` ${E.cleared_today} cleared today`
            + `${last ? `, the last at ${esc(evClock(last.ts))} (${esc((ISS[last.issue] || { name: {} }).name[ctx.LOC]
              || last.issue)})` : ''}.` : ''}</p>`;
      }
      return open.map(e => evCard(e) + rowsOf(e)).join('') + left.join('');
    }
    const why = st === 'old' ? `This node is ${esc((ctx.S.health || {}).version || 'older than v0.77')}: it sends `
      + `alerts, not events.` : st === 'error' ? esc(E.error) : 'This node sends alerts, not events.';
    const open = ctx.ORDER.filter(k => asks(k).length);
    return `<p class="note" id="decide-engine" data-component="absent" data-ref="stage-decide">${why}</p>`
      + (open.length ? open.map(k => card(ctx, k, ISS[k], asks(k)[0], true)).join('')
        : `<p class="note" id="decide-none" data-component="absent" data-ref="stage-decide">Nothing is asking for `
          + `anything.</p>`);
  },
```

  **Changes around it:**
  - **`card(ctx, key, d, a, did)`** takes one more argument. When `did` is true it appends `window.K.didButton(a.id)`
    after the Decide form, so an alert can be answered on Decide now that the strip is gone (ruling 2).
  - **`rowsOf(e)`** is a new local function. It returns `<details class="evrows" id="evrows-<id>"><summary>from N rule
    rows</summary>…</details>`, one line per id in `e.alerts`, looked up in `(H.asks || {}).acts` (`#id · rule ·
    when`, using `age()`). An id it can't find prints `#id · older than the 200 alerts this page reads`. Destructure
    `H` from `window.KH`, as the ledger does.
  - **`level: 'simple'`** is dead (render returns early in simple on Now). Leave it.
  - **The learn marks:** `learn` becomes `['events', 'buttons']`. Task 9 writes the two marks.
  - **The notes** become three:
    - `decide-events`: what an event is;
    - `decide-buttons`: what each button writes, and that ρ does not count events yet;
    - `decide-collective`: kept.
    Drop `decide-suggestion` and `decide-moves-nothing`, because they describe the alert card that is now ruling 2's
    fallback. Keep their text in the `rules`-state note if you need it.
  - **Destructure** `evState, evOpen, evCard, evClock, esc, age` from `window.K`.
- [ ] **Step 3: Check it in the rig.**
  - `python3 tools/shots.py` (or the measure rig) on `node1-2026-09-21d` gives the `old` state, with today's cards
    plus I did this.
  - With a locally injected block (a copy of the fixture with `issues.events` set to one open event) it gives an
    event card.
- [ ] **Step 4: `make lint && make test`, then commit:** `dashboard: Decide draws the open events, in five states`.

---

### Task 5: Act is the record of answers; the strip goes

**Files:** modify `app/static/dashboard.js`: the `asks` section (about lines 4565–4690), the `ledger` section
(about lines 5069–5205), and `boot()`'s `/actions` read (about line 6143).

**The `asks` section** gets the title "What was asked, and what was answered".
- **On `events` and `shadow`, it draws:**
  - a row of rings, one per event in `open` and `recent`, closed when `answer` is set (reuse `ringsFor`, with the
    events as the list and the unanswered ids as the open set);
  - the count line `N events in 7 days · M answered`, with `data-num`/`data-cmp`;
  - then one `row()` per event, newest first:
    - `left` is the issue and the kind;
    - `line` is `opened–cleared` and the rooms;
    - `qty` is the action text, then the answer (`Done · actor · cleared 40 min after` from `cleared_after_min`;
      `Not now`; `Doesn't fit`; `no answer`).
  Seven days are shown. There is nothing older on the wire, so no fold is needed.
- **On `rules`, `old` and `error`:** today's per-rule rows, under one line: "this node sends alerts, not events".
- **On every node, the strip goes:**
  - delete the `ask(...)` calls at the top of `render`;
  - keep `whereToGo()` and `capacity()`;
  - the `ask` kit function stays (it is exported and used elsewhere; grep before removing anything).

**The `ledger` section.**
- `boot()` reads `api('/actions?events=1')`.
- `ACT_NOTES` gains keys `` `ev${event_id}:${stage}` `` beside `` `${alert_id}:${stage}` ``.
- The ledger adds the event answers from `events.open` and `events.recent` (each one's latest `answer`), as rows:
  who, the button word (from `events.buttons`), the issue, and how long ago.
- The note shows only when `ACT_NOTES` has it, as today.
- `decided first` and its count are unchanged for alert acts.

- [ ] **Step 1: Source checks in `tests/test_dashboard.py`:** `asks`'s render no longer calls `ask(`, and `boot()`
  reads `/actions?events=1`.
- [ ] **Step 2: Implement both.**
- [ ] **Step 3: `make lint` (`check_ui` checks that `/actions` is a known route) and `make test`, then commit:**
  `dashboard: Act is the record of what was asked and answered; the strip goes`.

---

### Task 6: Now's order, the stage heads, the lead's last line, four sections to Network

**Files:** modify `app/static/dashboard.js`: `render()` (about lines 1750–1785), `STAGES` (about line 1540), `lead()`
(about lines 7339–7410), and the `NOW` and `NETWORK` arrays (about lines 7416–7425).

- [ ] **Step 1: The stage order.** `render(ctx, lead, opts)` takes `opts.stages`, an array of stage keys in drawing
  order, defaulting to `STAGES.map(s => s[0])`.
  - The sort uses the index in that array.
  - The loop `for (const [key, name, what] of STAGES)` iterates `opts.stages` mapped to their `STAGES` entries.
  - The loop mark (`<span class="loop">`) still draws the four in loop order.
  - Now and Arrange pass `stages: ['decide', 'observe', 'act', 'measure']`.
- [ ] **Step 2: The stage heads lose their numbers.**
  - Delete `<span class="n">${STAGE_INDEX[key] + 1}</span>`.
  - `STAGES`' Decide line becomes `'what to do about it'`.
  - `grep -n "stagehead .n\|\.stagehead \.n" app/static/dashboard.css` and remove the rule if nothing else uses it.
  - `measure.mjs` and `gate.sh` may look for `.stagehead .n`: grep them and update.
- [ ] **Step 3: The lead's last line.** Replace the `openAll` branch with one that follows `evState()`:
  - **`events`/`shadow`, open:** `<b data-num="events.open" data-cmp="alert events open">${n}</b> event${n===1?'':'s'}
    open · ${issue} · ${kind} since ${evClock(opened_at)}${shadow?' · shadow':''} · in Decide`, linking to
    `#stage-decide`. Take `issue` and `kind` from `evOpen()[0]`.
  - **Nothing open:** `nothing open · ${cleared_today} cleared today`, or just `nothing open` when the count is 0.
  - **`rules`/`old`/`error`:** today's alert count, linking to `#stage-decide` and saying `in Decide`.
  Keep `data-role="ask"`, `data-component="askRef"` and the `.askref` class: T1's fourth leg and the simple-mode
  check look for them.
- [ ] **Step 4: Four sections move.**
  - Remove `'sources'`, `'requests'`, `'claims'` and `'grain'` from `NOW`, and add them to `NETWORK`.
  - Then grep the whole file for `href="#claims`, `#grain`, `grain-line`, `#sources` and `#requests`, and for
    `data-ref="grain-line"` and `data-ref="claims"`:
    - a `data-ref` from a component still on Now must point at an id on Now (ruling 5: the rail's ref becomes
      `ground-figure`);
    - an `href` to one of the four becomes a link to the Network view, through `ctx.link`/`qlink` with
      `view: 'network'` and the anchor.
  - Run `measure.mjs anchors` (Task 10) to catch any you miss.
- [ ] **Step 5: Observe in the order a decision reads it** (spec §4.1): every issue, then the day it just had,
  then the day it is about to have, then the stations. The `forecast` section is registered at `order: 50` and
  `sensors` at `order: 20`. Change `forecast` to `order: 14`, the slot `sources` leaves. Arrange's saved
  `UI_LAYOUT` still wins over this, as it should.
- [ ] **Step 6: `make lint && make test`, then commit:** `dashboard: Decide first on Now, numberless stage heads,
  the lead counts events, four sections to Network`.

---

### Task 7: the ladder in one row

**Files:** modify `app/static/dashboard.js`: `rail()` and `railfold()` (about lines 7195–7290); `tests/visual/gate.sh`
(the ruler check, about lines 205–230).

- [ ] **Step 1: The move.**
  - `rail()` returns the stops and a `.railkey` holding only the `worth` chip.
  - `ruler()` and the two key `<span>`s (`.leaves`, `.fine`) move to the top of `railfold()`'s output, which draws
    only with `?worth=1`.
  - The chip's text stays, so it is still the fold's trigger.
- [ ] **Step 2: The gate's ruler check.** In `tests/visual/gate.sh`, the ruler check loads the page with `&worth=1`
  added to its query, because the ruler is in the fold now.
- [ ] **Step 3: `make lint && make test`.** The gate runs in Task 10. Then commit: `dashboard: the ladder is one row;
  the ruler and the key are in its fold`.

---

### Task 8: simple mode answers with the action

**Files:** modify `app/static/dashboard.js`, `lead()`'s `askAt` line (about line 7385).

- [ ] **Step 1: The change.** On `events`/`shadow`, when `evOpen()` has an event, the lead draws a simple-only row
  for the event of the shown issue `hk`, or for the first open event if `hk` has none:
  - `<div class="ask askrow evrow" data-lv="simple" data-component="eventRow" data-role="ask"
    id="evrow-<id>" data-ref="num-<issue>">`;
  - then the issue's sign, `<div class="what">` with the action text (or the kind and rooms when there is no
    action), and `K.evButtons(e)`;
  - then, when more events are open, `<p class="evmore" data-lv="simple">and N more open · in advanced</p>`.
  Otherwise, today's `askRow` (rules, old, error).
  Destructure `evState`, `evOpen` and `evButtons` in `main()`'s closure.
- [ ] **Step 2: `measure.mjs simple` must still pass:** no `.stagehead` and no visible `.askref` in simple, plus the
  also-line swap.
- [ ] **Step 3: Commit:** `dashboard: simple mode's open row is the event's action and its three buttons`.

---

### Task 9: the docs and the learn marks

**Files:**
- `docs/site/dashboard.md`: A first read, steps 3 to 7; Views; Simple on Now; The lead; The sections table and its
  counts; Decide; Act; Measure.
- `docs/GUI.md`
- `tools/build_learn.py`: `MARKS`, `QUESTIONS`
- `app/static/learn.json`, `data/docs_site.json` (`make learn`)
- `CHANGELOG.md`

- [ ] **Step 1: Rewrite the prose to match the page as it now draws.** This covers:
  - the first read: the lead's event line, the event card, the three buttons, Act's record and the ledger;
  - the views table: Now's order;
  - the sections table: Decide holds one section on Now; Network gains four; recount the per-stage numbers from the
    registry, and don't copy them;
  - Decide and Act as spec §4.2 and §4.3 say;
  - the five absence states.
  Keep every sentence a learn span quotes, or move its start and end strings with it. `make lint` (`build_learn
  --check`) fails if one moves.
- [ ] **Step 2: Two new marks.**
  - `events` quotes Decide's paragraph on what an event is.
  - `buttons` quotes the three-buttons paragraph.
  Each needs a `MARKS` entry (page `dashboard.md`, its `##` heading, verbatim start and end strings of at most 60
  words) and `QUESTIONS[key]` with two questions in each of en, id and es.
  Remove `recommend`, `looked` and `agent` from `MARKS` and `QUESTIONS` only if nothing else references them. Run
  `grep -n "'recommend'\|'looked'\|'agent'" app/static/dashboard.js` first.
- [ ] **Step 3: Regenerate** with `make learn`, then `make lint && make test`.
- [ ] **Step 4: The CHANGELOG line** (for the household):

```markdown
- The dashboard opens on what is happening now: each open alert event once, with the action the bot sent and Done,
  Not now and Doesn't fit, then the readings that explain it. Act is the record of what was asked and answered, and
  four sections about resolution and custody moved to Network. A node still on the old engine keeps its alert cards,
  with "I did this" on them.
```

- [ ] **Step 5: Commit:** `docs: the dashboard as it now reads; the events and buttons marks`.

---

### Task 10: a fixture with an open event, and the visual gate

**Prerequisite:** node #1 has an open event. (On 5 October a read-only watch was running for one.)

- [ ] **Step 1: Capture it** while the event is open:
  `ssh mini '… planetai snapshot --out /tmp/node1-events.json'`, using the PATH line from `docs/WORKFLOW.md`. Copy the
  file to `app/issues/fixtures/node1-<YYYY-MM-DD>-events.json`.
  - Check that it carries `issues.events` with one `open` entry, and the five tables `tests/test_issues_engine.py`
    requires.
  - Check that its `actions` notes were removed by the snapshot itself (it does that), and read it for anything the
    household would not publish: room names are already on the `open` share level; sensor ids and positions are not
    new.
- [ ] **Step 2: Name it in the docs.** `docs/site/dashboard.md` "Looking at it without a node" lists the fixtures:
  add it.
- [ ] **Step 3: The gate's baseline.** In `tests/visual/gate.sh`:
  - `PAI_Q` becomes `?fixture=node1-<date>-events`.
  - Run the gate once, then copy the measured heights into `HEIGHT_SHIPPED` and the empty figures into
    `EMPTY_SHIPPED`, with a dated comment: "re-recorded for v0.78 on the events fixture: Decide first, the four
    sections on Network, the rail in one row".
  - The gate needs `../planetai-design/node_modules/playwright`. Install it there if it is missing; see the memory
    note on the visual gate's baseline.
- [ ] **Step 4: `measure.mjs`.** If `anchors`, `press` or `simple` fail because the page legitimately moved (Decide
  first, the strip gone), change those checks to the new page and say each change in the commit message. Never relax
  a check to make it pass. A missing `data-cmp`, or a component pointing at nothing, is a page bug.
- [ ] **Step 5: Commit:** `visual: the events fixture is the baseline; the ruler is read in its fold`.

---

### Task 11: prove it on node #1, then the PR

- [ ] **Step 1: Serve the new page from node #1 without merging,** read-only. This is the closures lesson: a lifted
  test misses scope.
  - Copy the branch's `app/static/dashboard.js` and `dashboard.css` into the running app container's static
    directory: `docker cp`, with the PATH line, and never importing `main`.
  - Open `http://localhost:18081/` through the SSH tunnel at 390 and 1440 px (headless Chrome works here; see the
    memory note), in advanced and simple.
  - Check the event card and the five states. Use `?fixture=` for the states node #1 can't show.
  - Restore the original files afterwards with `planetai restart`, or by copying them back.
- [ ] **Step 2: One press of each button on node #1, with Tomas's go.**
  - Check that `/issues` shows the answer and the hold.
  - Check that `GET /actions?events=1` lists the rows.
  - Check that `/rho` is unchanged.
- [ ] **Step 3: Open the PR:** milestone v0.78, `needs testing`. The body:
  - what changed for a household;
  - the five rulings above;
  - the gate's re-recorded baseline, with the reason;
  - screenshots at 390 and 1440 (advanced and simple) from node #1 and from the fixture.
  End with the attribution line.
