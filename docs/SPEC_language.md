# The node's language

How the node speaks, in three layers, and the rules every string in it obeys. This document is the authority for `app/issues/*.yml` sentence templates, the `PLAIN_WORDS` family in `app/issues/__init__.py` **[changed: that is where it lives]**, the agent prompts in `agent_loop.py`, and any future surface that addresses a household. When a string and this document disagree, the string is wrong.

**[new]** In full, the authority covers every word table in `app/issues/__init__.py` (`PLAIN_WORDS`, `REASON_WORDS`, `CMP_WORDS`, `SPAN_WORDS`, `NOUN_WORDS`, `PROMPT_WORDS`, `SIMPLE_WORDS`) and all three prompts that speak for the node: `SYSTEM` (the Telegram bot), `PANE_SYSTEM` (the ask pane), and the Wall's "thinking aloud" prompt, which today sits in `app/static/doors-wall.js:73`.

The first reader of every sentence is a person standing in a kitchen, looking at a wall. Not a scientist, not a dashboard, not a journalist. The node reads instruments so the person does not have to; the language repays that trust by speaking like a neighbour who just checked them.

## The three layers

Every surface speaks in up to three layers, in this order. Each layer has one job.

**1. Headline — words only.** What is happening, where, and why it matters, in plain verbs. No numbers, no units, no terminology. "The air is getting worse in the kitchen, and the source is inside the house." A person who reads only this layer lives correctly.

**2. Reading — the number, with its unit, attached.** The measurement behind the headline, shown where the eye can take it or leave it: the hero numeral on the doors, the `plain` sentence under it, the second clause of an alert. "— 42 µg/m³, climbing." Numbers are never the opening act.

**3. Supporting — the meaning, taught once.** What the metric is, what the line is, whose line it is. It lives in the issue's `about` text, on the learn pages, and in the bot's answers when a person asks. It never pushes itself into a headline.

**[changed]** The pattern is progressive disclosure. The hero already draws the numeral big, and the `plain` sentence already carries the figures in household words. This document moves the number out of the headline, which until now opened with it. That reverses a page decision: `dashboard.js` repeated the number inside the sentence in mono and marked it red when it crossed the line. **The crossed mark moves with the number**: it now marks the figure in `plain` that is over the line.

## The lead/full split

`sentence` becomes the headline: words only. The yml `verbs` become intransitive — they must stand without a number after them.

```yaml
sentences:
  en:
    verbs:
      rising:  "getting worse"      # was "Climbing to"
      steady:  "holding"            # was "Holding at"
      falling: "clearing"           # was "Falling to"
    attribution:
      clear:         "The air is {verb} {where}, under the line. {cmp}"
      inside:        "The air is {verb} {where}, and the source is inside the house. {cmp}"
      everywhere:    "The air is {verb} {where}, and the whole area reads the same. {cmp}"
      outside_worse: "The air is {verb} {where}. The house is keeping the street out. {cmp}"
      mixed:         "The air is {verb} {where}. {cmp}"
      unknown:       "The air is {verb} {where}. {cmp}"
```

**[changed: all six attributions shown, since the schema test requires every class.]** `{cmp}` for a sensed issue is already words only ("Level with the street and the model"), so it stays.

**[new] Context issues.** Coast and land have no line and no comparison, and today their whole headline is a number ("1.3 % of the square this node watches changed between 2024 and 2025"). Their `state.context` template becomes a word headline about direction: "The ground this node watches keeps changing, year on year." The figures, `{span}` and `{since}` move to `plain`. A context issue's `{cmp}` (its readouts, which carry numbers) moves to `plain` too.

**[new] The headline is assembled from clauses, not one template.** The attribution templates keep their prose shapes, but three slots are filled by the engine, never written into a template:

- `{line}` — the live relation of the headline value to the issue's line, computed from the value itself (`over · near · under`, near within a tenth below). A template can therefore never assert "under the line" on a day the reading is past it, and each issue's yml names its own line: "the WHO line" for air, "this house's own line" for heat.
- `{event}` — the clause for the day it crossed and came back ("It crossed the line earlier today"), filled only for reason codes that certainly happened today and only while the reading is back under the line. The state band and the sentence then agree instead of reading as a contradiction.
- `{cmp}` — each issue may carry its own `cmp_words`: air says "cleaner than the street", heat says "cooler than the street". The shared table is the fallback, not the voice. One skeleton per issue was the flatness the review found; heat's templates are not air's with the noun swapped.

`plain` becomes the reading layer and gains the numeral distance, which today it omits: "The room reads 42, the yard 31, the street 38. Two are over the line (15)." **[changed]** On the doors, where the numeral is drawn directly above, the page may drop that first clause; everywhere else it stays.

**[new] The sentence splits into `title` + `tagline`.** The title is the qualitative head — the template up to the `{line}` clause, no number and no indicator in it: "The air is getting worse in the house." The tagline is the rest — the line, the comparison, the day's event — set smaller and muted beneath it: "Under the WHO line. Level with the street, the ring and the region." The title says what is happening; the readings arrive a beat later, in the tagline, the numeral and `plain`. This is the progressive disclosure pattern applied to the title itself: a household reads the situation first and meets the instruments one line down. Templates without a `{line}` clause (the none and context states) do not split. The full `sentence` stays on the wire for prose contexts — the bot, the asks, the wall's thinking-aloud. The split is engine work (`_sentence_parts`), so it holds in all three locales and for every issue, present and future.

The pair travels together. Every consumer renders `sentence` + `plain`, or states why not:

| Surface | Headline | Reading | Supporting |
| --- | --- | --- | --- |
| doors hero | `title` under the numeral, `tagline` smaller beneath **[changed]** | numeral + rule, `plain` beneath, crossed figure marked | learn mark on the issue page |
| doors wall **[new]** | `title` at sentence size, `tagline` smaller and muted | `plain` beneath | the ask, answer on Telegram |
| Now door, hour scrubber **[new]** | live hour: `title` + `tagline`; a past hour: the line relation as title | the reading in the tagline ("At 04:00 it read 8 µg/m³.") | the four distances below |
| Decide card **[new]** | issue, kind and rooms in words | the peak, with its comparisons (usual, outside, the line) | the evidence links |
| ask pane | in context (already: `sentence`, `plain`) | same | `about` in context when focused **[changed: to be added in `app/ask.py`]** |
| Telegram bot | answer's first line | one number when it drives the advice | when the person asks "what is…" |
| Wall, thinking aloud **[new]** | the whole paragraph is words | none: its prompt already bans units and allows at most two numbers | none |
| alerts (events) | first clause ("The air jumped in the kitchen") | second clause, naming whose line **[changed]** ("42 µg/m³ — the WHO line is 15, outside 12") | the action card |
| MCP / API | `hero.sentence` | `hero.plain`, `hero.value` | `about` in the issue document |

## The `about` key

Each issue gains one glossary text per locale, the whole of the supporting layer:

```yaml
about:
  en: "PM2.5 are particles fine enough to reach deep into the lungs. The line — 15 µg/m³ over a
       day — is the WHO's."
  es: "PM2.5 son partículas tan finas que llegan al fondo de los pulmones. El límite — 15 µg/m³
       en un día — es el de la OMS."
```

Heat's `about` explains apparent temperature ("'Feels like' counts humidity with the temperature, because wet air slows the sweat that cools you") and says the line is the place's own, measured here. **[new]** Coast and land's `about` say where the number comes from (the model, the satellite) and that the node never asks anything of them, the sentences `PLAIN_WORDS` carries today as `model` and `yearly`.

## The voice rules

These apply to every string and every prompt. They exist because every string so far was written by an assistant, and assistants share habits; the yml headers say so out loud.

1. **Speak like a neighbour who just checked the instruments.** "The air jumped in the kitchen", not "Air quality spiked". "The house is keeping the street out", not "the building is mitigating infiltration".
2. **Plain verbs, physical words.** Getting worse, holding, clearing. Not escalating, not deteriorating, not trending.
3. **No units in headlines, no lecturing anywhere.** The number follows the words; the lesson follows the number; nothing precedes its layer.
4. **No AI mannerisms.** No significance inflation ("a critical threshold"), no promotional adjectives ("optimal", "severe levels"), no copula avoidance ("serves as", "stands as"), no negative parallelism ("not just X, but Y"), no rule-of-three padding, no rhetorical questions answered immediately, no signposting ("let's look at"), no reassurance kickers ("and that's okay"), no corporate filler ("in order to", "at this point in time"), no "it is important to".
5. **Alarm is a register, not a volume.** DANGER appears at danger and nowhere else. **[changed]** The one exception is the end label of a hero's rule, which names the far end of the scale ("dangerous") rather than the present. Emoji mark events and bot answers (📈 😷 🚨 ✅) because they are the scan-language of a chat list; they never decorate prose.
6. **Advice is physical, specific, and keeps its reasons.** "Open the side where it started and run the purifier for 30 min: outside is cleaner (12 µg/m³)." The reason moves the hand. Never drop a safety clause for smoothness: "wet skin" and "do not leave anyone alone in it" stay.
7. **Uncertainty says itself.** "Say what you know and what you do not" is already in both prompts; it applies to templates too. An absent distance says why; it never fills with a guess.
8. **Each locale is written, not translated.** The es and id strings are read by native speakers before their ASSISTANT-WRITTEN header comes off. Calques count as bugs: "se siente como" is English wearing Spanish; "sensación de" is Spanish.

9) **One word per thing. [new]** A message the node sent is called the same thing on every surface; so is a map cell. The UX review found "ask", "alert" and "message" on one screen for one thing (`docs/design/UX_REVIEW_2026-09.md` §2.1).
10) **Every alert names whose line it is. [new]** This is an `AGENTS.md` invariant, restated here so the templates keep it: "the WHO line", "this house's own line".

## The prompts

**[changed]** `SYSTEM` in `agent_loop.py` already enforces plain text, brevity, no invented numbers, and one number only when it drives the advice. `PANE_SYSTEM` has the first three but not the one-number rule. Both gain:

- The one-number rule, in `PANE_SYSTEM` where it is missing.
- Speak the node's layers: headline in words first; the reading when it helps; the meaning when the person asks. The page context carries `sentence` and `plain` today, and `about` once `app/ask.py` adds it (migration step 3).
- Voice rules 4 and 6, verbatim, so a small local model does not drift into lecture mode.

**[new] The third prompt.** The Wall's "thinking aloud" prompt already speaks this way, and more strictly: no units at all, at most two numbers, comparisons instead of figures. It stays as strict as it is, because a wall is read from three metres. It moves from `doors-wall.js` to the node, as `WALL_SYSTEM` beside the other two, so the page holds no copy and one file holds every prompt.

## Migration

**[changed]** Strings in the yml files, four small engine changes, and the tests that pin the old shape. Under NEXT_RELEASE rules 2–3 the page part ships in its own release.

**Release A — the node's words (app/issues, engine, prompts, tests)**

1. air.yml, heat.yml: intransitive verbs, all six attributions without `{n} {unit}`, `about` per locale, event second clauses that teach the line once. **[new]** Strip units from every `say:` string (`{outside_temp} °C` becomes `{outside_temp}`), in the same commit as engine change 2c.
2. engine.py:
   1. `plain` names the numeral distance.
   2. Events and actions honour the issue's `dp` instead of rounding everything to one decimal (`app/actions.py:84`).
   3. `outside_*` values carry their units.
   4. **[new]** Context issues: `{span}`, `{since}` and the readouts move from `sentence` to `plain`.
3. coast.yml, land.yml: **[new]** word headlines for `state.context`, `about` per locale.
4. agent_loop.py and ask.py: the prompt rules above; `about` added to the pane context.
5. **[new] Tests.** `tests/test_issues_engine.py:369-371` checks the numeral in `plain`, not `sentence`, and adds a check that no sensed or context headline contains a digit. Line 98 checks the verb appears in the sentence rather than leading it. `tests/test_issues.py` greps `line`/`sql` and is unchanged.

**[new] Docs in Release A.** `docs/site/api.md:433` (what `sentence` and `plain` hold), `docs/GUI.md:40` (its example sentence), and `docs/site/dashboard.md:94,146`. Then `tools/build_learn.py` rebuilds `learn.json`, because learn mode quotes those pages word for word, and each page's checked stamp moves only after it has been re-read.

**Release B — the page (app/static)**

6. **[new]** `dashboard.js` `sentence()`: the crossed mark moves to the `plain` figure over the line. The "How a sentence is built" panel text describes the new three layers. Until B ships, A leaves the page correct but unmarked: the sentence simply has no number to colour.
7. **[new]** The Wall's prompt moves from `doors-wall.js` to the node as `WALL_SYSTEM`; the page asks for it by name.
8. **[new]** The doors read the node's English words only (`docs/decisions/2026-10-07-doors.md`). Locale work shows on the classic dashboard and the bot until the doors gain locales.

**After both**

9. Native passes: es by Tomas, id by Bayu. Each approved locale sheds its ASSISTANT-WRITTEN header.
10. This document joins the docs set at the next release, stamped like the rest.

## Decisions (Tomas, 9 October 2026)

1. On the doors, the page may drop `plain`'s first clause (the numeral drawn above); everywhere else the clause stays.
2. Context issues (coast, land) get word headlines; their figures move to `plain`. No exemptions.
3. The Wall's prompt moves from `doors-wall.js` to the node as `WALL_SYSTEM`, in the page release.
4. The Wall's no-units rule stays the Wall's: the bot and the pane keep "one number when it drives the advice".
