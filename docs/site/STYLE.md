# How the documentation site is written

The pages in this folder are the source of `planetai.fab.city/docs`. `tools/build_docs.py` renders them,
together with a few pages taken as they are from `docs/`, into static HTML on the programme layer's tokens.
Nothing here is served by a node, with one exception: `tools/build_learn.py` cuts short quotes
out of these pages into `app/static/learn.json`, which the dashboard's learn mode shows in the ask pane, and
cuts every page at its `##` headings into `data/docs_site.json`, which `GET /docs/search` reads. Move one of
those spans, or edit any page, and `make lint` says so until `make learn` is run.

## What a page is for

A person reads these pages to build a node one part at a time. The node is the local unit of
PLANETAI, hyperlocal compute and intelligence for distributed production, and its purpose is fixed: clean
air, water and soil for the people and the other living things around it. It measures its place, acts on
what it measures, keeps its raw readings at home and sends upward only what a district, a bioregion and
the Fab City Index need. The canonical wording is the lead and "What it is for" in `introduction.md`;
the README, `llms.txt`, `AGENTS.md`, the dashboard's footer and the programme page quote it, and
`tools/check_site.py` checks that they still do. So every page that has steps says, in its first
lines, which part of the node the reader is adding and what the node can do once it is there. Steps are
numbered when the order matters, and each one says what to do, what the screen shows when it worked, and
what that means for the node. A step the reader cannot check is not a step. The page ends by naming the
next part to add.

The path the pages follow: run a node → connect what measures your place → read it → let it ask, and
answer → measure whether it worked → extend it with packs and sources → join the network → put an agent
on it.

## Voice

Written for the person installing at 9 pm with a sensor that just went quiet. Plain words. Say what to do.
Short declaratives mixed with longer ones; never a march of same-length sentences. Sentence case
everywhere; no emoji, no hype, no "simply", no "robust", no "seamless". No em dashes: a comma, a colon, a
full stop or a bracket does the work. No "it's not X, it's Y" unless a real misconception is being
corrected and the replacement is named. A page states what the node does in this version, not what it
will do. Where the code and an older document disagree, the code wins and the page says which version it
read. The mission is stated in specifics (what stays, what goes up, which cell, who may be counted), never
in slogans.

Only facts that are in the code or in the canonical documents (`ARCHITECTURE.md`, `SPEC.md`, `AGENTS.md`,
`docs/*.md`). No line numbers in the prose. A gap or a known bug is stated plainly: "In
v0.72.1 the AirGradient adapter exists and is tested but is not registered for polling."

The pages are Fab City's, and they read the way Tomas Diez writes: direct and warm, "you" for the reader, "we"
only where Fab City itself speaks (we run node #1, write to us), never "I". Clauses joined by commas rather than
chopped into fragments. Say each thing once, on the page where a reader would look for it, and link to it from
everywhere else.

What reads as written by a machine, and is cut on sight: framing sentences that announce what comes next, headline
titles and colon reveals, "X, not Y" pairs, tidy groups of three, false ranges ("from a sensor on the wall to a
satellite overhead"), claims of significance, a run of three-word fragments for drama, an `-ing` clause bolted on to
sound deep, "Note that", "It is important to", "simply".

What does not belong on these pages at all: the history of how a feature came to be ("since v0.72", "until v0.80 it
did"), dates of internal decisions and who took them, pull request and issue numbers, the names of the people and
agents who built a thing, and node #1's diary. The CHANGELOG keeps history. A page says what the node does now. Node
#1 may appear as a worked example, with numbers, when an example is clearer than a rule.

## Conventions the renderer understands

- One `# Title` per page, first line. The sidebar uses it.
- `## ` and `### ` headings make the right-hand "On this page" list. Keep them short.
- Endpoints are `### GET /path` (method in capitals, then the path). The renderer draws the method as a chip.
- The line right after an endpoint heading may be `Access: public` · `Access: open` · `Access: token` ·
  `Access: admin` · `Access: loopback or token` and so on. The renderer draws it as an ink chip.
- Settings, commands, files, metric names, cell names and values are in backticks.
- Tables are GitHub tables. A table is for parallel facts (settings, routes, rules); prose is for everything else.
- A note is a blockquote starting with a bold word: `> **Note.** …`, `> **Careful.** …`, `> **Gap in v0.72.1.** …`.
- Link to another page by its file name: `[the API](api.md)`. The renderer turns it into the right URL.
- Link to a repository file with its path from the repo root: `[init.sql](../../init.sql)`; the renderer
  turns paths that leave `docs/` into GitHub links at the built commit.
- Numbers, units and ids as the node writes them: `µg/m³`, `°C`, `pm25`, `Environmental|Community`.
