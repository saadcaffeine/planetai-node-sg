# Design
<!-- checked: v0.91.0 -->

The design language every PLANETAI surface is drawn in: the colours and the one thing each means, the type, the four
card kinds, the signs and the motion. [The dashboard](dashboard.md), [the Wall](wall.md) and the phone page all follow
it, so a number reads the same, drawn the same way, on every node.

Every value comes from one table, `planetai-design/references/planetai-layer.md`, which the design repository turns
into `app/static/planetai-theme.css`. The node carries a pinned copy of that file, `signs.svg` and
`kilometre-cells.json`, and does not edit them: `tools/check_theme.py`, in `make lint`, holds each to the sha256 in
`data/frozen_layer.txt`. To change a value, change the table and regenerate. `tokens.css` is the Fab City foundation
the layer imports; the layer's own tokens are unprefixed and redefine no `--fc-` token.

## The plate

`--ground` is `#F9F5F2` on paper and `#171717` in the dark register, and `--ink` is the reverse. Everything drawn is
ink on ground: buildings, roads, labels, provenance. The register is one attribute on `<html>`, `data-theme="dark"`,
so a page carries both. The Paper / Dark switch is in the bar of the doors and the classic dashboard and in the phone
page's foot; the choice is kept per browser, and the doors and the phone follow the system's setting until one is
chosen. The Wall is always dark.

Corners are square. There are no gauges, no dials with needles and no rounded verdict: a reading is a number with its
comparison beside it.

## Colour

Four colours, one meaning each. A surface that uses one of them for anything else is wrong.

| token | paper | dark | what it means |
|---|---|---|---|
| `--cells` | `#20388D` | `#7FA5E8` | an H3 cell, and where a reading is from. On the doors it is also the keyboard focus |
| `--rings` | `#00A057` | `#00A057` | a loop closed: somebody was asked and somebody answered |
| `--signal-worse` | `#E62038` | `#E62038` | a reading got worse or crossed the line its issue declares. A mark, never small type |
| `--satellite-only` | `#DB7200` | `#FF931E` | what only the satellite knows |

`--loop-closed` and `--rho-closed` are both `var(--rings)`, so a closed ring is the same green in the ρ row as anywhere
else. Everything else is ink.

Contrast decides which register a colour may appear in, and the generator computes it. `#7FA5E8` is 2.29:1 on paper,
so it appears only in the dark block. `#20388D` is 1.72:1 on ink, so it never appears there. `#DB7200` is the paper
orange at 3.02:1; `#FF931E` is 2.05:1 on paper and 8.06:1 on ink. Neither crosses into the other's block.

### State and provenance are not colours

State is carried by weight, fill and dash, never by hue. On a map a live node is a 2.5 stroke, a registered one 1.5
dashed `5 4`, a pilot 1 at 45% opacity. On a page the same rule is type weight: a state word is set at 500 in the
muted ink, and `act` alone at 700 in full ink. Nothing in a table is tinted. The ladder follows it: rungs whose cell
may leave the machine are dotted, rungs that stay are plain, rungs finer than the node says where it is are struck
through, so a reader who cannot tell blue from grey still sees three zones.

Provenance is ink only and square (`--prov` is `var(--ink)`): the word's sign, then the word.
The words are `live`, `partial`, `model`, `cached` and `example`, and the classic dashboard also prints `stale` when
the node stops answering; see [Concepts](concepts.md#provenance-words-on-the-page).

## Type

| role | face | where |
|---|---|---|
| display | Funnel Sans | headings, stage names, a section's title |
| body | Figtree | the node's own sentences: the lead, the reason, a caption |
| mono | JetBrains Mono (`--mono`) | every number, unit, timestamp, cell id and chip label |

All three are self-hosted and served by the node, because its page may be read on a network with no route out.
`--num-face` is the large numeral on the lead and the Wall. It defaults to `var(--mono)`; whether it should be Funnel
Sans is open item O13.

The node's own words are never uppercased, because `µ` uppercases to `M` and `µg/m³` becomes `MG/M³`, a thousandfold
error. Anything the node wrote is drawn inside `.said`, which turns uppercase off. On the classic dashboard
`tools/check_ui.py` fails a new uppercase rule, and a `µ` written outside `.said`.

The Wall has its own floor, `--wf`: 28 px at 1920×1080, scaled with the screen, and nothing on the Wall is smaller.

## Four card kinds and no fifth

Everything on a node's page is one of four things, and each part of the doors says which in `data-kind`.

| kind | what it is for |
|---|---|
| **readout** | one figure, with its comparison beside it |
| **stack** | the same quantity at several distances, on one scale |
| **series** | a quantity over time |
| **row** | a list of like things, counted in signs |

A drawing sits inside a card, it is not a fifth kind. A gap in a series is a gap in the line, never a ramp across a
line nobody measured. Every numeral carries its comparison (`data-num` names it, `data-cmp` says against what), and a
numeral with nothing to compare it to says so in words.

The figures are drawn with Observable Plot 0.6.17 and d3 7.9.0, served by the node (ISC, licences in
`app/static/licences/`) and pinned in `data/vendor.sha256`. Plot draws the marks and the rules above decide them: ink
for readings, red for the line and the hours over it, green only for an answer that closed a loop, blue only for a cell
or focus.

## Signs

`app/static/signs.svg` carries 25 counting signs and 4 pictograms, two families with two rules.

A **counting sign** is 24×24, fill only, `currentColor`. It is repeated to show quantity (more signs, never a bigger
sign), so it has to read at `--sign-floor`, 12 px, and tile in a row of ten without fusing. At that size the one
reliable difference is solid mass against hollow ring.

A **pictogram** (`pix-air`, `pix-heat`, `pix-land`, `pix-coast`) is 15×11, drawn once at hero size beside the issue it
names, and never repeated. An issue with no pictogram has none.

Distinctness is measured: every pair is rasterised at 12 px and compared cell for cell, and over 90% identical fails
unless the layer records it as an open item. Two pairs are recorded and wait for a redraw: O7 (`prov-cached` against
`prov-example`, 93.7%) and O12 (`cell` against `prov-example`, 93.9%).

## Motion

Every motion is named after the datum that drives it. A motion with no datum behind it is deleted: nothing counts up,
and nothing eases between two readings.

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

The doors add one token the layer does not carry yet, `--motion-replay-loop: 30s`, defined in `doors.html`: a
replayed window of 6 or 24 hours takes 30 s, on Node's flow and on the Wall's walk.

Only transform and opacity move. One `requestAnimationFrame` loop drives the whole page; surfaces subscribe to
it, and it stops when the tab is hidden or nobody is subscribed. Time and scale move in steps: there is no
place between resolution 7 and 8, so nothing morphs.

`--motion-asking` is a word, not a duration: the loading state lasts as long as the node takes to answer.
`--motion-asking-hold` puts a floor under it so the list of what the page asked can be read.

Under `prefers-reduced-motion: reduce` one block sets every timed token to `0s`, `--motion-asking-hold` included, and
every surface has to read frozen. The doors' clock never starts. `--motion-asking` is not restated there, so the
loading state still happens and stops moving. No page uses SVG `<animate>`, because reduced motion reaches CSS
animation and not SMIL.

## Refusals that hold at every stage

- No raw readings leave the instance that recorded them.
- No cell is upgraded from `mock` or `partial` to `live` by aggregation.
- No agent dispatches without a human row in `actions`.
- No layer requires a cloud provider to function.
- No scale is skipped: a city aggregator is built from nodes, not declared from above.

On the doors these close the Node door, "What this node will not do, at any stage", each in plain words beside a link
to where it can be checked. On the classic dashboard they are the care label, drawn as signs in Measure beside the
funnel. The longer form is [Architecture](architecture.md); what leaves the machine, and how coarse, is
[Sharing and security](sharing.md).

## What is unsettled

The theme carries 12 open items on 11 tokens, each written into the CSS as an `OPEN:` comment at the token it affects:
`--land-opacity`, `--cells`, `--prov`, `--cell-water-opacity`, `--state-pilot-opacity`, `--wall-line-opacity`,
`--sign-floor` (two items), `--num-face`, `--motion-reading-pulse`, `--motion-day-curve-step` and
`--motion-ring-closed`. They are values set by eye, on one screen or in one room, and not measured since. The list
lives in `planetai-design/references/planetai-layer.md`.

## Where this leads

[The dashboard](dashboard.md) is where these rules are read by a person at the page, and [Wall mode](wall.md) is the
dark register for a screen read from three metres.
