# The past hour speaks the node's words — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** When the Now door's hour scrubber goes back in time, the sentence comes from the engine, the same as at the
live hour. The page stops writing English of its own. The past hour gets the same pattern as the live one: first
what happened, in words, then the reading, a beat later.

**Why:** `docs/SPEC_language.md` makes the engine the only author of a household sentence ("when a string and this
document disagree, the string is wrong"). v0.80.9 broke that for one surface. `app/static/doors-now.js` `readout()`
writes the past hour itself:

- **English only.** The live hour is localized on the wire, but a scrubbed hour is not.
- **The line is in the title.** "The air in the house was under the line." puts an indicator in the title. That is
  the thing Tomas asked to keep out ("no numbers/indicators in the titles … introduce slowly the readings").
- **Its own arithmetic.** The page decides over or under with `v > line`. It has no `near`, and the engine's `{line}`
  clause has one (within a tenth below the line). The two surfaces can disagree about the same hour.
- **Two issues hardcoded.** `k === 'heat' ? … : 'The air in the house was'` calls every issue that is not heat
  "the air".

**Architecture:** One new wire key, `hours`, and one new yml block, `past`. The engine renders one
`[title, tagline]` pair per bucket per locale, from the same helpers the live sentence uses: `_trend`, `_where`
and the `{line}` relation. The page indexes into it. Nothing on the page computes a judgment or writes a word.

**Spec:** `docs/SPEC_language.md`, "The three layers" and "The sentence splits into `title` + `tagline`". Read
both before Task 2.

## The pedagogy, in one table

The pattern is the same live and past: the title says what happened, in the household's words, and the tagline
meets the instrument.

| | title (words only) | tagline (the reading, a beat later) |
| --- | --- | --- |
| live, today | The air is getting worse in the house | Past the WHO line — and the source is inside the house. Cleaner than the street. |
| past, today (page) | The air in the house was under the line. | At 04:00 it read 8 µg/m³. |
| past, this plan | The air was clearing in the house | At 04:00 it read 8 µg/m³, under the WHO line. |
| no reading | Nothing was recorded in the house at 04:00. | — |

The past title takes a verb, the same three the live sentence has (getting worse, holding, clearing), from
`_trend` over the six hours up to that bucket. So scrubbing back through a night reads as a story ("was getting
worse … was holding … was clearing") instead of the same line relation repeated 24 times. The line moves into
the tagline, next to the number it judges, and names whose line it is (voice rule 10).

## Decision for Tomas before Task 2 (one question)

**Should the live title keep the "why"?** Today `_sentence_parts` cuts every template at `{line}`. In
`inside`, `everywhere` and `outside_worse` the qualitative clause comes *after* `{line}` in the template, so it
lands in the tagline:

- template: `The air is {verb} {where}, {line} — and the source is inside the house.`
- title today: "The air is getting worse in the house"
- tagline today: "Past the WHO line — and the source is inside the house."

The spec's own model headline is "The air is getting worse in the kitchen, **and the source is inside the
house**". Layer 1 is "what is happening, where, *and why it matters*". The source is words, not an indicator, so
by the spec it belongs in the title. The fix is yml only: move `{line}` to the end of the qualitative clause in the
three attributions × 2 issues × 3 locales. `_sentence_parts` does not change.

- **Recommended: yes.** Title "The air is getting worse in the house, and the source is inside." Tagline "Past
  the WHO line. Cleaner than the street."
- **No:** the title stays as short as it is today, and the why waits in the tagline.

This plan does it as Task 2 if yes, and skips Task 2 if no. The other tasks do not depend on it.

## Global constraints

- Work in worktree `planetai-node-pasthour`, on branch `past-hour-language-2026-10-11` off `origin/main`
  `a7f7b6a`. Ship from the worktree that holds main.
- The doors read English only (`docs/decisions/2026-10-07-doors.md`, SPEC_language migration step 8). This plan
  still renders all three locales, because the engine renders every key in every locale and the doors gaining
  locales should change nothing here. es and id strings carry the ASSISTANT-WRITTEN header until the native
  passes (step 9).
- `tools/check_wire.py` pins `/issues`' keys: adding `hours` is a deliberate wire change. Regenerate
  `tests/data/wire/issues-v0.json` in the same commit, and say so in the CHANGELOG.
- The visual gate reads captures. A capture made before this release has no `hours`. The page shows the
  "nothing recorded" line for a past hour on such a capture. That is acceptable for a capture, and it is not a
  reason for a page-side English fallback.
- Never import app `main` in a test. A test file ends with `sys.exit`: add checks above the last line.
- `make lint && make test` before every commit.

## Files

| file | change |
| --- | --- |
| `tests/test_issues_engine.py` | Task 1: pin the live split. Task 3: pin `hours` |
| `packs/air-quality/issue.yml`, `heat.yml` | Task 2 (if yes): `{line}` after the why. Task 3: a `past` block per locale |
| `app/issues/engine.py` | Task 3: `_line_key()` lifted out of `_sentence_parts`; `_hour_parts()`; `hours` on the wire |
| `tests/data/wire/issues-v0.json` | Task 3: regenerated |
| `app/static/doors-load.js` | Task 4: `hours: tr(it.hours)` |
| `app/static/doors-now.js` | Task 4: the past branch becomes an index into `it.hours`; the English goes |
| `docs/SPEC_language.md`, `docs/site/api.md`, `CHANGELOG.md` | Task 5 |

## Task 1 — pin what v0.80.8 shipped (it has no test)

No test reads `title` or `tagline`. A template edit that puts a number back into a title passes every gate today.

- [ ] In `tests/test_issues_engine.py`, for every sensed issue × every attribution × every locale × each of the
      three line relations, render with `_sentence_parts` and assert:
      - the title contains no digit and no line word (`line.over|near|under` strings of that locale);
      - `title` and `tagline` are both non-empty when the template has `{line}`;
      - the tagline starts with an upper-case letter and never with punctuation.
- [ ] `none` and `context` states: the title equals the sentence and the tagline is `""`.
- [ ] `make test`. These must pass on `main` as it is: a probe on 11 Oct rendered 2 issues × 3 locales × 6 attributions × 3 relations with no violation. If one fails now, a template changed since.

## Task 2 — the title keeps the why (only if Tomas says yes)

- [ ] air.yml and heat.yml, en/es/id: in `inside`, `everywhere` and `outside_worse`, move the qualitative clause
      in front of `{line}`. Example (en air `inside`):
      `"The air is {verb} {where}, and the source is inside the house. {line}. {cmp} {event}"`
      Check that `_fmt`'s space and punctuation cleanup still gives one full stop per sentence. Task 1's
      assertions are the gate.
- [ ] `test_shipped` pins sign-off on message text: re-pin deliberately, and say so in the commit.

## Task 3 — the engine renders the past hour

- [ ] Lift the relation out of `_sentence_parts` into `_line_key(d, n, line) -> "over" | "near" | "under" | ""`.
      `_sentence_parts` calls it. There is one definition of "near", and the page never gets one.
- [ ] yml, per locale, sensed issues only:
      ```yaml
      past:
        verbs: { rising: "was getting worse", steady: "was holding", falling: "was clearing" }
        title: "The air {verb} {where}"
        tagline: "At {hour} it read {n} {unit}, {line}."     # heat: "At {hour} it felt like {n} {unit}, {line}."
        none: "Nothing was recorded {where} at {hour}."
      ```
      `{line}` reuses the issue's existing `line:` words ("under the WHO line"), so whose line it is is said
      once, in one place.
- [ ] `_hour_parts(d, series, buckets, i, loc, line, compare, clock) -> [title, tagline]`: the verb is
      `_trend(series[:i + 1], compare)`, the value is `series[i]`, and the hour is `_hhmm` in the node's clock.
      With no value it returns `[none, ""]`.
- [ ] `compute()`: `"hours": {loc: [_hour_parts(...) for i in range(len(buckets))] for loc in LOCALES}` for
      sensed issues; `None` for context and unwatched ones. It uses the headline distance's series, the same as
      the hero.
- [ ] Tests: `len(hours[loc]) == len(buckets)`; no past title contains a digit; the last bucket's verb equals
      the live `verb_key`; a value at 0.95 × line gives the locale's `near` words; es and id differ from en.
- [ ] Regenerate `tests/data/wire/issues-v0.json`; `tools/check_wire.py` green.

**Ceiling:** 24 buckets × 3 locales × 2 sensed issues ≈ 150 short strings on `/issues`, a few KB beside the
series that already ship. If the window grows to a week, render only the requested locale.

## Task 4 — the page reads it

- [ ] `doors-load.js` `buildD`: `hours: tr(it.hours)`.
- [ ] `doors-now.js` `readout()`: the past branch becomes
      `const [s, tag] = (it.hours || [])[i] || [\`Nothing was recorded at ${hhmm(b)}.\`, ''];`
      Delete the `k === 'heat'` strings and the page's `over`. The live branch is unchanged.
- [ ] The visual gate: `PAI_STATIC=app/static PAI_OUT=/tmp/pai-gate PAI_DESIGN_REPO=../planetai-design bash
      tests/visual/gate.sh`, exit 0. Then on node #1, scrub back over the night and screenshot three hours.
      Check that the verb changes as the readings do.

## Task 5 — the record

- [ ] `SPEC_language.md`: the "Now door, hour scrubber" row becomes "past hour: `hours[i]` from the engine —
      the trend in the past tense as title, the reading and whose line in the tagline". Add `past` to the yml
      schema section. If Tomas said yes to Task 2, update the split paragraph's example.
- [ ] `docs/site/api.md`: document the `hours` key.
- [ ] `CHANGELOG.md`: one section. The wire gains `hours`, and the page's English is gone.

## Out of scope

- Localizing the rest of the doors (migration step 8): the kicker "now / h before the capture", the ladder labels
  and the decision card are still page English, by the 7 Oct decision.
- Past-hour `{cmp}` (cleaner than the street at 04:00). The series carry every distance, so it is possible.
  Add it only if the scrubbed tagline reads as too thin on node #1.
