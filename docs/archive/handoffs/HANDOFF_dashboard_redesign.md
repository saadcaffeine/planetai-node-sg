# Handoff — the dashboard redesign

Branch `dashboard-redesign-2026-09`, 35 commits from `f01b3e0` to `39dab39`, on top of v0.70.
Prompts 1–6 of `docs/design/PROMPTS_dashboard_build_2026-09-20.md` are in. Prompt 7 is this file,
the plates, the changelog and `docs/GUI.md`. **Nothing is tagged and no pull request is open.**

Read §2 first. **T2 was re-set on 22 September** — Tomas's call, on the numbers in §2 — and the
argument is recorded as Part four of `docs/design/DIRECTIONS_2026-09.md`. The branch is ready for a
tag; one target is still missed and §2 says which.

## 1 · What shipped

| prompt | what it put on the page |
|---|---|
| 1 | six views, four stages, three modes, two registers, and a page that reflows at 390 · 768 · 1440 |
| 2 | the grain rail as the top instrument, with a log rule under it, and the lead beneath |
| 3 | Observe · Decide · Act · Measure — the matrix, the day, the sources, the request ledger, the barcode, the grain that holds, the ask ledger, the funnel, the care label, the Figures ledger |
| 4 | Historical (reach per source), Network (the registry), Set up (the section list), Arrange, Wall |
| 5 | learn mode: seventeen marks, each quoting `docs/site` verbatim, built into `app/static/learn.json` |
| 6 | three motion tokens, one animation loop, the `asking` loading state, and the layer published as `docs/site/design.md` |

Twenty sections across nine packs, sixty distinct `data-component` values, four card kinds.

## 2 · The measurement, and the target it missed

`tests/visual/measure.mjs`, both columns on the **same fixture** (`node1-2026-09-06`, the rig's own),
so the two are comparable. The shipped column is prompt 0's baseline at `d01330c` (v0.66).

| target | goal | shipped @1440 | built @1440 | shipped @390 | built @390 |
|---|---|---|---|---|---|
| **T1** five legs | all five | ✓✓✓✓✓ | ✓✓✓✓✓ | ✓✓✓✓✓ | ✓✓✓**✗**✓ |
| **T1b** index rows @1440 | present | **✗** idx 0 | **✗** idx 0 | — | — |
| **T2** empty share (read) | ≤ 30 % · ≤ 20 % | 59.6 % ✗ | **60.4 %** ✗ | 36.2 % ✗ | **46.2 %** ✗ |
| **T2** page in viewports | ≤ 4 · ≤ 8 | 5.2 ✗ | **9.2** ✗ | 8.1 ✗ | **14.5** ✗ |
| **T3** distinct `data-kind` | 4 | 2 ✗ | **4** ✓ | 2 ✗ | **4** ✓ |
| **T4** numerals with no comparison | 0 | 0 of 37 ✓ | **0 of 73** ✓ | 0 of 37 ✓ | **0 of 73** ✓ |
| **T5** components with no link | 0 | 0 of 47 ✓ | **0 of 70** ✓ | 0 of 47 ✓ | **0 of 69** ✓ |
| **T6** reading-order divergences | 0 | 9 ✗ | **6** | 2 ✗ | **1** |
| **T7** cap height @1920 | ≥ 9 mm ×4 | 18.4 · 39.7 · 10.2 · 10.1 ✓ | unchanged ✓ | — | — |
| **T9** SVGs named, axe, frozen motion | clean | ✓ | ✓ | — | — |
| **overflow** at 390 | 0 px | **85 px** ✗ | **0** ✓ | | |

On the current fixture (`node1-2026-09-21d`, a richer node) the built page reads 11.3 screens at 1440
and 18.4 at 390, and T1's ask leg passes at 390. The fixture changes the length; it does not change
the shape of the result.

**What was won.** T3 is four card kinds, which is what prompts 2–3 were for. T4 and T5 held at zero
through nearly twice as many numerals and components — every figure on the page still sits beside
what it is compared to, and nothing is drawn without a link in or out. T6 improved at both widths.
The 85 px of horizontal scroll a phone had is gone, and a gate now holds it at zero across 108
combinations of view, width, mode and register.

**What was lost.** **The page is 1.8× longer than the one it replaces, at both widths, and the empty
share is no better at 1440 and ten points worse at 390.** The cause is not a bug: prompts 3, 4 and 5
added eight sections and none took any away.

**T2 was re-set rather than met.** Four viewports at 1440 is 3,600 px against a 10,205 px page, and
folding or moving every foldable section reaches 7.1 — nothing short of deleting two thirds of the
bands gets to four, and each of them draws something the node measured. The target was written
against a page with two card kinds and none of those ledgers. Part four of
`docs/design/DIRECTIONS_2026-09.md` carries the arithmetic, the per-section table, and what replaces
it: T2a, the answer is on the first screen (this is T1, and it passes); T2b, the lead names the open
asks and links to the stage that holds them (it does); and T2c, the empty share, unchanged.

**T2c is the open miss, and it is now decomposed.** `node tests/visual/measure.mjs analyse air`
reuses `aTargets`' grid verbatim and attributes every empty cell to the part of the page it sits in;
it reproduces T2's own figure exactly, which is the only reason to trust what is under it.

**A third of the miss at 1440 is the page's own margin.** 1,160 px of column inside a 1,440 px
viewport leaves 140 px down each side that no page with a readable measure could fill, and T2 counts
every pixel of them as a failure — which is why the same page reads 42.5 % on a phone and 57.3 % at a
desk. Measured inside the column the page actually draws in: **47.0 % at 1440 and 36.8 % at 390**,
against goals of 30 % and 20 %. Still missed, and now actionable.

**The strip was the left column, and it is fixed.** It was not a gutter between the columns — the
gap is 40 px. It was the right-hand third of the left column, sized `1.45fr` and 663 px wide to hold
a sentence that stops at 404 and a why line that stops at 502. The column is now `minmax(0, 56ch)`,
the measure it carries, and the drawing takes the rest with a 340 px floor so no window is worse off
than before.

| | before | after |
|---|---|---|
| T2c at 1440, viewport | 57.3 % | **52.4 %** |
| T2c at 1440, inside the column | 47.0 % | **40.9 %** |
| the tenth at 720–864 | 79 % air | **43 %** |
| T6 divergences at 1440 | 6 | **4** |

**Still missed at 40.9 % against 30 %**, and what remains is spread rather than concentrated: 43 % of
the air is inside no named component at all, which is the spacing between parts. That is a rhythm
question for a round, not another one-line fix. Part four of `docs/design/DIRECTIONS_2026-09.md`
carries the tables and the widths from 900 to 1920.

## 3 · The contract, as it now stands

`SLOTS` and `ANATOMY` from the 14 September prompt are **gone** — they were tables in the page that
preceded this branch. What a pack has now is the registration contract in `app/static/dashboard.js`,
and one slot mechanism:

| field | what it does |
|---|---|
| `id` `pack` `stage` `title` | required. `stage` is one of observe · decide · act · measure |
| `order` | position within the stage. Lower first; default 50 |
| `needs` | globals it reads. Absent → the band prints one honest line and does not fail |
| `render(ctx)` | the body. Captions belong here; explanations do not |
| `lead(ctx)` | what it contributes to the lead. A section may have this instead of `render` |
| `wall(ctx)` | what it shows at three metres |
| `notes(ctx)` | the explanations, gathered into one folded band at the foot |
| `controls(ctx)` | a control strip for this section |
| `learn: [...]` | the learn marks it carries (prompt 5) |
| `level: 'simple'` | opts into the four-sentence digest |
| `anchor` | where its notes point when it draws no band of its own |

A pack could also fill a slot inside another section's card, through `contributions[]` on the issue
(`slot: 'stack.<distance>'`, `band.readout`, and an "unplaced" card for a slot the page lacked). No node
ever produced it; only the prototypes' synthetic data did. **It was removed on 2 October 2026**: a pack's
number on an issue is a readout (`readouts:` in its pack.yaml), a pack's own band is a declared section
(`sections:`), and no pack fills a distance column (docs/decisions/2026-10-01-packs.md, point 4).

### The twenty sections

| stage | order | id | pack | learn marks |
|---|---|---|---|---|
| observe | 0 | `ground` | place | tiles · cell |
| observe | 0 | `netmap` | core | — |
| observe | 5 | `reach` | core | — |
| observe | 10 | `matrix` | core | distances · states |
| observe | 12 | `day` | core | cards · raw |
| observe | 14 | `sources` | core | custody |
| observe | 20 | `sensors` | air-quality | — |
| observe | 30 | `satellite` | earth | — |
| observe | 40 | `reticulum` | reticulum | — |
| observe | 41 | `meshtastic` | meshtastic | — |
| observe | 45 | `hardware` | hardware | — |
| observe | 50 | `forecast` | forecast | — |
| observe | 60 | `requests` | place | share |
| observe | 60 | `registry` | core | — |
| decide | 10 | `claims` | core | — |
| decide | 20 | `grain` | core | containment |
| decide | 30 | `trust` | trust | — |
| act | 10 | `asks` | core | levels · current |
| measure | 10 | `measure` | core | rho · refusals |
| measure | 90 | `figures` | core | — |

Nine of them contribute to the wall. The shell itself carries the rail, the lead, the provenance pill
and the stages strip, and their four learn marks.

## 4 · Motion, and what a frame costs

Nine motions, each named after its datum, all in the frozen layer's table
(`planetai-design/references/planetai-layer.md`, design log R24) and published in
[`docs/site/design.md`](../../site/design.md). Three are new in prompt 6: `--motion-meter-fill` (40 ms),
`--motion-mark-float` (3.2 s) and `--motion-asking`, which is the word `until-data` because the
loading state lasts as long as the node takes to answer.

One `requestAnimationFrame` loop for the page (`window.PAI_RAF`). It stops when the tab is hidden,
when the element scrolls off, and when nobody is subscribed; under reduced motion it schedules
nothing and draws one still frame. No SVG `<animate>` anywhere, and `tools/check_ui.py` refuses it.

**Frame cost, measured.** `PAI_ASKING.probe(n)` draws n frames on demand and answers with the cost.

| where | canvas | mean | worst |
|---|---|---|---|
| this Mac, in-app browser | 1670 × 1076 (DPR 2) | **0.69 ms** | 5.30 ms (the first frame) |
| headless Chromium, the gate | 1440 × 900 (DPR 1) | **0.34 ms** | 1.40 ms |

**The budget is 4 ms on a 2015 MacBook Pro and that machine was not measured.** It is node #2's, in
Menorca, and it answers HTTP and nothing else from here. For 4 ms to be exceeded it would have to be
about six times slower than this one on canvas text, which is possible. If it is, the glyph count is
one constant — `N` in the `ASKING` module — and prompt 6's instruction is to halve it and record it.

## 5 · The plates

`docs/design/shots/redesign/`, 58 JPEGs, 8.9 MB, one device pixel, from `node1-2026-09-21d`:
five views at 390 · 768 · 1440 in both registers, the wall at four widths in dark, Now again in
simple and in learn at every width and register, and the empty and refused states at 390 and 1440.
Six are full-page; the rest are the fold, because the fold is what T1 and T2 are about and the whole
matrix at full height is twenty megabytes.

    PAI_DESIGN_REPO=../planetai-design PAI_STATIC=$PWD/app/static \
      PAI_Q="?fixture=node1-2026-09-21d" PAI_FIXTURE=node1-2026-09-21d \
      PAI_PLATES=$PWD/docs/design/shots/redesign \
      node tests/visual/measure.mjs plates

No two plates are byte-identical. That is asserted rather than assumed, and it is how three wrong
renders were caught — see §7.

## 6 · A stranger's pack

`node tests/visual/measure.mjs extend` registers four sections from a pack the page has never heard
of, at the moment a pack's own static file would, and checks what happens:

- `water` draws in its own stage at its own order, between `day` and `sources`
- `water-deep` declares a need this node does not have → one honest line, not a blank
- `water-bad` throws → it says it did not render, and sixteen bands still drew
- `water-fifth` draws a fifth `data-kind` → **the count sees it**, which is the assertion that fails
  when the page is too permissive rather than too strict

With all four on the page, T3 is still the four core kinds, T4 is 0 of 94 and T5 is 0 of 89.

**Prompt 7 asked to "prove T8 still holds" against a `water` pack fixture from the 14 September
prompt. Neither exists.** That prompt is not in this repository, not in `docs/`, and not anywhere on
this machine; the target tables in `DIRECTIONS_2026-09.md` run T1, T1b, T2, T3, T4, T5, T6, and PICK
adds T7 and T9. There is no T8 to hold. The check above is what that instruction was plainly about,
under its own name.

## 7 · Four things that were wrong and are not any more

Each was silent, and each had been silent for days.

1. **Every render of the Set up view threw.** `const LATE` sat near the foot of `main()` and
   `sectionsBox()` read it from the middle: a function declaration hoists, a `const` does not, so the
   view died on `Cannot access 'LATE' before initialization` from the moment that line was written in
   prompt 4. `main()` bailed before assigning `#page`, so the page that was already drawn stayed
   drawn and **the Set up view simply never appeared.** Mine, from `ab64fee`.
2. **The rig had never rendered Set up either**, for the same reason and without noticing: it pressed
   the button, screenshotted Now, and wrote the file under the Set up name. Caught because the
   plate was byte-identical to the Now plate beside it. `open()` now refuses a render whose view did
   not change, so the class is closed.
3. **A third-party pack's section could not appear on any view.** One registry serves three views
   through three hardcoded arrays of ids, and an id this file has never heard of was filtered out of
   all three — it registered, Set up listed it as `drawing`, and it was on no page. The contract's
   central promise ("the shell renders whatever registered", "adding a feature is adding a file") had
   been false since the Now/Network split on 15 September. Now is the default home for anything the
   two named lists do not claim.
4. **The `empty` renders were of the populated page.** `state: 'empty'` pointed the rig at a second
   container on `:8082` from the pai-clean review rig, which is not running anywhere; the document
   was served from disk regardless and every API call fell through to the snapshot. It now uses the
   page's own `?state=empty`, which is what the docs said all along.

## 8 · What is not verified, and cannot be from here

- **A real wall in a real room.** T7 says the four figures clear 9 mm of cap height at 1920. Nobody
  has stood three metres from a screen with this page on it.
- **A native `id` or `es` reader.** Every sentence on the page comes from the node in three languages
  and no first-language reader of either has read one. The `es` pluralisation and the Indonesian
  capability words are the likeliest to be wrong.
- **The Sentinel medians on node #1.** Historical draws nine years from `/earth`. The figures were
  read back from the node, not checked against Copernicus.
- **Node #2's screen.** `mahon` is on v0.67 and has never had this page on it. It is a 2015 MacBook
  on Linux Mint, which is also the machine the frame budget is about.
- **A poll landing inside the T9 audit window.** The window is 21 s and `POLL_SECONDS` is 300, so
  T9's weight leg is green because nothing was asked, not because a refresh is cheap.

## 9 · What a tester runs

The page needs a node on **v0.70 or later** — `asks.where`, `/rho.funnel` and the derived `measured`
stage are node-side and already released. The page itself is not released; it is on this branch.

```bash
ssh <the node> 'cd ~/planetai/planetai-node && ./update.sh'
```

On a node that runs from a git checkout rather than a tarball, as node #1 does, `update.sh` is not
the path — fast-forward and rebuild, and set `NODE_VERSION` yourself, because `/health` reads it from
`.env` and not from the code:

```bash
cd ~/planetai/planetai-node && git fetch --tags origin && git merge --ff-only origin/main \
  && sed -i.bak "s|^NODE_VERSION=.*|NODE_VERSION=$(git describe --tags --always)|" .env && rm -f .env.bak \
  && docker compose up -d --build app
```

## 10 · The URLs

Locally, with no database and no container, from this branch:

```bash
python3 tools/preview.py          # http://127.0.0.1:8123
```

| what | URL |
|---|---|
| the page, from the committed fixture | `http://127.0.0.1:8123/?fixture=node1-2026-09-21d` |
| the same, in learn mode | `…&mode=learn` |
| the same, dark | `…&register=dark` |
| the four-sentence answer | `…&mode=simple` |
| a node with nothing on it yet | `…&state=empty` |
| what a reader with no token sees | `…&state=refused` |
| the wall | `…#wall` |
| node #1 itself, over the tailnet | `http://100.90.223.47:8081/` |
| node #2, which is on v0.67 and does not have this page | `http://100.105.230.126:8080/` |

`?fixture=`, `?mode=`, `?register=` and `?state=` all remember nothing, so any of these can be sent
to somebody without changing their own page.

## 11 · The two sentences

**To Lucas**, whose node is three releases behind and is also the machine the frame budget is about:

> Mahon has been on v0.67 since the site stopped publishing — that is fixed and v0.70 is live, so an
> update will bring you four releases at once, including the line that tells you the nearest place to
> make or fix something. When you have a moment after that, I would like to know what the new page
> feels like on that 2015 MacBook: it draws one animated frame while it waits for the node, and that
> machine is the slowest one we have.

**To Vivanco**, on the Index:

> The node now measures the Governance cell end to end: it raises an act-level alert, records who
> answered and when, and draws ρ as the asks answered over the asks raised with the median minutes to
> the first answer — plus a fourth stage, `measured`, worked out from whether the condition stopped
> being true rather than typed in by anyone. On our node that is 5 of 30 where it read zero before.
> It is one node's Governance cell at community scale, and it is real.

## 12 · Three lines

- ✅ **done** — prompts 1–6; 58 plates; the T1–T9 table on a matched fixture; the stranger's-pack
  check; `make docs && make lint && make test` and the visual gate all green.
- ⚠ **open** — **T2c**, measured inside the page's own column: **40.9 % at 1440** and 36.8 % at 390
  against 30 % and 20 %. The concentrated part is closed; what is left is spacing between parts,
  which is a rhythm question for a round.
  T1b's index rows are still absent at 1440, and at 390 T1's ask leg falls below the fold on a sparse
  node. The wall carries two components with no link in or out.
- ⛔ **needs Tomas** — the tag, which no session takes; a `docs/site/design.md` pass in his own
  voice; the two sentences above, which are drafts of his words and not his words; and whether node
  #2 gets the page, which is Lucas's machine.

---

*Written by the prompt-7 session, 22 September 2026, on `dashboard-redesign-2026-09` at `39dab39`.
Measured with `tests/visual/measure.mjs` against `docs/design/fixtures/` and node #1 over the
tailnet. Sources: `docs/design/PROMPTS_dashboard_build_2026-09-20.md`,
`docs/design/PICK_2026-09-20.md`, `docs/design/DIRECTIONS_2026-09.md`,
`planetai-design/references/planetai-layer.md` and `decisions/design-log.md`.*
