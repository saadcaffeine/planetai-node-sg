# Design
<!-- checked: v0.80.10 -->

What a PLANETAI surface is made of, and why each part is the way it is. This page is the programme layer
written out: the colours and what each one means, the type, the four card kinds, the signs, every motion with
the datum that drives it, and the refusals that hold at every stage. It is the reference behind
[the dashboard](dashboard.md) and [the wall](wall.md), so that a number read on either means the same
thing, drawn the same way, on every node.

Every value here comes from one table, `planetai-design/references/planetai-layer.md`, which the design
repository's generator turns into `app/static/planetai-theme.css`. The node carries a copy and does not edit
it. To change a value you change the table and regenerate; there is nowhere else to change it.

> **Note.** This page says nothing the layer does not. Where the layer records a value as unsettled, this
> page says so and names the item. Nothing below is an aspiration.

## How the copy is held

Three files under `app/static/` belong to the design repository: `planetai-theme.css`, `signs.svg` and
`kilometre-cells.json`. `tools/check_theme.py` runs in `make lint` and checks each against the sha256 recorded
in `data/frozen_layer.txt`, with the design commit they were copied from, on every machine. Where a
`planetai-design` checkout is present it also compares the files byte for byte against that pinned commit,
not against whatever branch the checkout is on. One difference is forgiven and named: the theme declares the
mono at `fonts/jetbrains-mono-latin.woff2`, and the node serves it at the flat name, so that one `src:` line
is reported rather than failed. `python3 tools/check_theme.py --update` rewrites the pin, and refuses unless
the design repository is there and the files match it.

`tokens.css` is the Fab City foundation the layer imports; the programme layer's own tokens are unprefixed
and redefine no `--fc-` token.

## The plate

Paper by day, dark on a wall and by a reader's switch. `--ground` is `#F9F5F2` on paper and `#171717` in the
dark register; `--ink` is the reverse. Everything drawn is ink on ground (buildings, roads, labels,
provenance), and the register is one attribute on `<html>`, `data-theme="dark"`, so a page carries both and
no drawing is exported twice. The Paper / Dark switch sits in the dashboard's header and the choice is kept
per browser; the wall is always dark.

Corners are square, and the page draws no gauges, no dials with needles and no rounded verdict: a reading is a
number with its comparison beside it.

## Colour is argument, never decoration

Four colours, one meaning each. A surface that uses one of them for anything else is wrong, and that is the
whole of the rule.

| token | paper | dark | what it means, and nothing else |
|---|---|---|---|
| `--cells` | `#20388D` | `#7FA5E8` | an H3 cell. Also data and identity, which are the same claim: this is where the reading is from |
| `--rings` | `#00A057` | `#00A057` | a loop closed: somebody was asked and somebody answered |
| `--signal-worse` | `#E62038` | `#E62038` | a signal got worse, or crossed a line the issue declares |
| `--satellite-only` | `#DB7200` | `#FF931E` | what only the satellite knows, and nothing else |

`--loop-closed` and `--rho-closed` are both `var(--rings)`: a closed ring means the same thing in the ρ row
as it does anywhere else, so it is the same green by name rather than by coincidence.

**State is carried by weight, fill and dash, never by hue.** A live node is a 2.5 stroke, a registered one
a 1.5 dashed `5 4`, a pilot a 1 at 45% opacity. On the dashboard the same rule reads as type weight: the
state word is set at 500 in the muted ink, and `act` alone at 700 in full ink. Nothing in a table is tinted.
The ladder follows it too: rungs that may leave the machine are dotted, rungs that stay are plain, rungs
finer than the node says where it is are struck through. A reader who cannot separate blue from grey still
sees three zones.

Provenance is ink only and square (`--prov` is `var(--ink)`), never a coloured pill. The words are `live`,
`partial`, `model`, `cached` and `stale`; see [Concepts](concepts.md).

### Two numbers that are rules

Contrast decides which register a colour may appear in, and the generator computes it.

- `#7FA5E8` measures **2.29:1** on paper. It may appear only inside the dark block.
- `#20388D` measures **1.72:1** on ink. It may never appear inside it. A dark export still carrying
  `#20388D` is a stale asset, not a style choice.
- `#DB7200` is the paper register's satellite orange at **3.02:1**; `#FF931E` is **2.05:1** on paper,
  under the 3:1 floor for a graphical object, and **8.06:1** on ink. Neither crosses into the other's block.

## Type

Three faces, three jobs.

| role | face | where |
|---|---|---|
| display | Funnel Sans | headings, the stage names, a band's title |
| body | Figtree | the node's own sentences: the lead, the reason, a caption |
| mono | JetBrains Mono (`--mono`) | every number, unit, timestamp, cell id and chip label |

All three are self-hosted and served from the node, because a node serves its page to a household network
that may have no route out at all; a webfont from a CDN is a page with no typography.

`--num-face` is the one numeral big enough to be a piece of typography rather than a reading: the monument
figure on the lead. It defaults to `var(--mono)` and exists so that the open question, mono or Funnel Sans,
is one line either way. Recorded as **O13**.

**The node's own words are never uppercased.** `µg/m³` once became `MG/M³` on a hero, which is a
thousandfold error in a unit, on a wall, silently: `µ` uppercases to `M`. `tools/check_ui.py` keeps the list
of rules allowed to shout and fails on a new one, and fails on a `µ` written into the stylesheet or into the
page's markup outside a `.said` wrapper.

## Spacing

There is no spacing scale in this layer, and that is worth saying rather than leaving a reader to look for
one. The foundation tokens (`--fc-` prefixed, from the Fab City design system) carry the type scale; the
dashboard's own rhythm is `clamp()` in `app/static/dashboard.css`. The measuring rig in
`tests/visual/measure.mjs` renders the page at 375, 390, 768 and 1440 px, and the wall at 1920.

## Four card kinds and no fifth

Everything on a node's page is one of four things. A fifth would mean the page had learned a new way to be
read, which is a decision and not a detail.

| kind | what it is for |
|---|---|
| **readout** | one figure, with its comparison beside it |
| **stack** | the same quantity at several distances, on one scale |
| **series** | a quantity over time |
| **row** | a list of like things, counted in signs |

A drawing is a drawing *inside* a card, not a fifth kind. A gap in a series is a gap in the line, never a
ramp across a line nobody measured. Every numeral carries its comparison; a numeral with nothing to compare
it to says so in words.

## Drawn with Plot

The figures are drawn with Observable Plot 0.6.17 and the d3 7.9.0 it is built on, served by the node as two static
files (ISC; `app/static/licences/`), so the page draws on a network with no route out. `data/vendor.sha256` pins both
and `make lint` checks them. Plot draws marks; the layer's rules still decide them: ink for readings, red for the line
and the hours over it, green only for an answer that closed a loop, blue only for focus. A figure is a `series` card,
so the four card kinds stay four.

## Signs

Two families, two rules, and each is audited by its own. `app/static/signs.svg` carries 25 counting signs and
4 pictograms.

A **counting sign** is 24×24, fill only, `currentColor`. It is repeated to show quantity
(more signs, never a bigger sign), so it has to survive `--sign-floor`, which is **12 px**, and tile in a row
of ten without fusing. At that size the only discriminator that can be relied on is solid mass against hollow
ring. `person` was drawn for the care label's agent row.

A **pictogram** is 15×11, drawn once at hero size beside the issue it names: `pix-air`, `pix-heat`,
`pix-land`, `pix-coast`. It is never repeated to show quantity, and the 12 px floor is a rule about a use it
does not have. An issue with no pictogram has none; the lead does not invent one.

Distinctness is measured, not judged: every pair is rasterised at 12 px and compared cell for cell, and over
90% identical fails unless the layer records it as an open item. Two pairs are recorded: **O7**
(`prov-cached` against `prov-example`, 93.7%) and **O12** (`cell` against `prov-example`, 93.9%). Both are
redraws waiting to happen, not exceptions. `person` went back for a redraw after its first pass measured
90.3% identical to `heat`.

## Motion, and the datum behind each one

Every motion is named after the thing that drives it. A motion with no datum behind it is deleted rather
than tokenised: there is no easing for its own sake anywhere on a PLANETAI surface, and nothing counts up,
nothing eases between two readings, nothing moves without a reason.

| token | datum | value |
|---|---|---|
| `--motion-reading-fade` | a reading lands | `120ms` |
| `--motion-reading-pulse` | a reading lands | `3s` |
| `--motion-ring-closed` | a person answered | `320ms` |
| `--motion-meter-fill` | a stack arrives | `40ms` per bracket cell |
| `--motion-day-curve-step` | the day curve steps | `3600s`, once an hour |
| `--motion-satellite-year` | the year changes | `4s` per frame, no tween |
| `--motion-land-change-yoy` | the datum changes once a year | `0s`, so it does not animate |
| `--motion-mark-float` | learn mode is on | `3.2s`, 4 px |
| `--motion-asking` | the node has not answered yet | `until-data` |
| `--motion-asking-hold` | the loading state is also a reading | `3s`, the shortest time it is held |

Transform and opacity only, never layout. One `requestAnimationFrame` loop for the whole page, which surfaces
subscribe to and which stops when the tab is hidden, when the element is off screen, and when nobody is
subscribed.

**A motion is not always a duration.** `--motion-asking` is a word: the loading state lasts as long as the
node takes to answer, which is a fact about the network and not a design decision. `--motion-asking-hold`
sets a floor under it, because on a fast node the list of what the page asked and how long each read took
was gone before anybody could read it. The dashboard holds it on a load and on **↻**, never on a poll.

**Reduced motion.** One `@media (prefers-reduced-motion: reduce)` block sets every *timed* token to `0s`,
`--motion-asking-hold` included, and every surface has to read frozen. `--motion-asking` is not restated
there: it has no number to remove, so under reduced motion the loading state still happens and stops
moving. There is no SVG `<animate>` anywhere on a node's page, and `tools/check_ui.py` fails the lint if one
appears: reduced motion reaches CSS animation and nothing else, so SMIL keeps moving after a household has
asked the machine to stop, and no stylesheet can switch it off.

## Refusals that hold at every stage

The layer is not only what a surface may draw. It is also what it may not.

- No raw readings leave the instance that recorded them.
- No cell is upgraded from `mock` or `partial` to `live` by aggregation.
- No agent dispatches without a human row in `actions`.
- No layer requires a cloud provider to function.
- No scale is skipped: a city aggregator is built from nodes, not declared from above.

On the dashboard these five are the care label, "What this node will not do, at any stage", drawn as signs
inside the Measure stage's "Whether it worked", beside the funnel, where the loop closes.

The longer form, with the staging from one node to a bioregion, is [Architecture](architecture.md); the
privacy half (what leaves the machine and how coarse) is [Sharing and security](sharing.md).

## What is unsettled

The theme carries 12 open items on 11 tokens, each emitted into the CSS as an `OPEN:` comment at the token it
affects, so a reader of the stylesheet sees them without coming here: `--land-opacity`, `--cells`, `--prov`,
`--cell-water-opacity`, `--state-pilot-opacity`, `--wall-line-opacity`, `--sign-floor` (two items), `--num-face`,
`--motion-reading-pulse`, `--motion-day-curve-step` and `--motion-ring-closed`. They are the values that were
set by eye, or on one screen, or in one room, and have not been measured since. The list lives in
`planetai-design/references/planetai-layer.md`; `O7`, `O12` and `O13` are named above.

## Where this comes from

- `planetai-design/references/planetai-layer.md`: the token table, the guards and the open items.
- `planetai-design/decisions/design-log.md`: which round settled what, and why.
- `app/static/planetai-theme.css`: generated from the first, held to its pin by `tools/check_theme.py`.

The node's page is `doors.html` (the five doors) or `index.html` (the classic dashboard at `/?layout=classic`) and the static files
the node serves beside it, and stays so.
`planetai.fab.city` may use a framework; the two never share code, and both read this layer.

## Where this leads

These rules are read on two surfaces. [The dashboard](dashboard.md) is where the ladder, the lead and the four
stages draw them for a person at the page, and [Wall mode](wall.md) is the dark register for a screen read
from three metres.
