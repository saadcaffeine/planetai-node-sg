# An issue's state follows the events

*Approved in brainstorming with Tomas, 6 October 2026. Nothing here is built yet.*

On a node whose alert engine is `events` or `shadow`, an issue's state (`act`, `notable`, `quiet`) and its open asks
still come from the old rules' alerts, even though those alerts are no longer the asks. This spec makes the state, and
the asks the page, the ask pane and the bot read, follow the alert events. It follows `docs/SPEC_alerts.md` (events)
and `docs/SPEC_dashboard_events.md` (the page and `/issues.events`).

## 1. What node #1 shows (6 October 2026, `ALERT_ENGINE=events`, `main` 7a3a815)

- **The lead and Decide disagree.** The lead's kicker said heat was `act` ("asked at 09:38, and still true") while
  Decide showed no heat card, because no heat event was open. Heat's state came from an old `heat/heat_stress_now`
  alert, which counts as "current" whenever K ROOM is over 35 °C (`_state`, `ASK_CURRENT_HOURS`).
- **Nobody can close the old alerts.** Since #184 the old heat and air rules still record act-level alerts, but they
  no longer send. The page's buttons, and Plan 2's Telegram buttons, answer events, not alerts. So `open_asks` only
  grows: 247 on node #1, of which 240 belong to the packs the engine replaced.
- **The model hears about them too.** The ask pane (`app/ask.py`) and the bot's context (`app/agent_loop.py`) list
  `open_asks`, so both are told about dozens of open heat and air alerts that no one can answer.

## 2. Decisions

| question | answer |
|---|---|
| How far | **State, plus `open_asks`.** ρ is unchanged; ρ over events is Plan 2's decision record (alerts spec §7) |
| An answered open event | **Any answer makes it `notable`**, except a `danger` event, which stays `act` (Not now never holds danger) |
| Which nodes | `events` and `shadow`, the line #187 drew for `uncovered_asks`. A `rules` node is unchanged |

## 3. The change, in `engine.compute`

`compute` already receives the events block (`app/events_wire.py` live, or the block a fixture captured) and already
works out, for `uncovered_asks`, which packs the engine replaced: every pack that ships a kinded rule
(`packs.load_rules()`, as `run_rules` decides it in #184). Both changes below use that same set, worked out once,
before the issues are computed.

### 3.1 The replaced packs' alerts are not asks

On `shadow` and `events`, `_asks` leaves out every alert whose rule's pack is in the replaced set. That covers two
lists:
- **`open_asks`:** what the page draws as alert cards, what the ask pane and the bot read, and what simple mode's
  digest counts.
- **The last 24 hours of alerts:** what makes an issue `notable` with "a warn at 14:00, over now".

What is left are asks no event stands for, such as `nearby/only_here`. `uncovered_asks` becomes, in effect, every
open ask, since none of those is covered. Keep its computation as it is, so it stays right if Plan 2 links alerts to
events by `alerts.event_id`.

### 3.2 The state, in this order

1. `none` (no source) and `context` (an issue that only informs): as today.
2. **An open event for this issue** (one per issue per house, by construction):
   - **Act-level and unanswered, or `danger` whatever the answer** → `act`. Reason `event_open`, with the kind and
     the opened time.
   - **Answered (Done, Not now or Doesn't fit), or the warn-level air spike** → `notable`. Reason `event_answered`,
     with the answer's word, who, and when; for an unanswered spike, `event_open`.
3. **Open asks that remain** (other packs): `act` if current, `notable` if stale, as today.
4. **An event of this issue that cleared within the last 24 hours** (`NOTABLE_HOURS`) → `notable`. Reason
   `event_cleared`, with the clear time.
5. **Recent warn or act alerts that remain** (other packs) → `notable`, reason `alert_today`, as today.
6. **Over the line** → `notable`, `over_line`, as today. Otherwise `quiet`, `no_alert`.

The five state values, the headline rule (an open event's issue leads, then state, then movement) and `lead.by` do not
change. The headline still prefers an open event, even when it is answered and its issue now reads `notable`.

### 3.3 Three new reasons

`REASON_WORDS` in `app/issues/__init__.py` gains `event_open`, `event_answered` and `event_cleared`, in en, id and es,
in the voice of the existing lines. For example:
- "an event open since 13:21 (sustained)"
- "answered at 13:29 by Tomas Diez (done); the node is watching"
- "an event cleared at 09:59"

`_reason_text` formats today only `when`, `level`, `id`, `peak` and `peak_at`. It gains:
- `kind`: the event's kind, as the node writes it;
- `who`: the actor;
- `word`: the answer, taken from `events.buttons` in the household's language, so it matches the page and the bot.

## 4. What does not change

- **The wire.** No key is added or removed; `tools/check_wire.py` is untouched.
- **ρ, the funnel and `/effect.`** They are still counted from the alerts table.
- **A `rules` node,** and a node older than this, which sends no `events` block.
- **The engine:** what opens, escalates, clears and sends.

## 5. Who notices

- **The page:** the lead's kicker and the matrix's state words agree with Decide.
- **Simple mode's digest:** it counts open asks, so it stops saying "the node has asked N times" about alerts no one
  can close.
- **The ask pane and the bot:** their context lists only answerable asks.

## 6. Proof

- **Replay tests** on `node1-2026-09-21d` with an injected block, one case per rule in §3.2:
  - an unanswered act event gives `act`;
  - an answered one gives `notable`;
  - an answered `danger` event gives `act`;
  - an unanswered spike gives `notable`;
  - a clear within 24 hours gives `notable`.
  Also: `open_asks` holds no `heat/` or `air-quality/` alert on `events` and `shadow`, and holds all of them on
  `rules`.
- **Both timestamp shapes:** a live row (datetimes) and a captured row (strings) give the same state.
- **On node #1, after the merge:** with event 3 open and answered Done, heat reads `notable` ("answered … by Tomas
  Diez"); `open_asks` holds only the `nearby` asks; and the page's lead kicker agrees with Decide.
- **Milestone v0.78, `needs testing`.**

## 7. Not in this work

- **ρ over events,** and closing the old alerts. ρ is Plan 2's decision record. Old alerts could be closed by writing
  `alerts.event_id` and answering them with their event, also Plan 2.
- **The report's alert lines.** `app/report.py` reads the alerts table, and is Plan 4.
