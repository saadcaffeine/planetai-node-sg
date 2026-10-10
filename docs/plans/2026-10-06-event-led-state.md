# An issue's state follows the events — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** On a `shadow` or `events` node, `open_asks` stops carrying the replaced packs' alerts, and each issue's
state follows its alert event, so the page's lead, the ask pane and the bot agree with Decide.

**Architecture:**
- **One computation, earlier in `compute`.** `app/issues/engine.py`'s `compute` works out the set of replaced packs
  once, before the per-issue loop. `uncovered_asks` already uses that set after the loop.
- **`_asks` and `_state` take this issue's events.** `_asks` filters out the replaced packs. `_state` takes the
  issue's open event and its last clear, and applies spec §3.2's order.
- **`_reason_text` learns three new codes,** with their words in `REASON_WORDS`.

Nothing else moves: not the wire, not ρ, not the engine.

**Tech stack:** Python 3.11; plain-`assert` test scripts run by `tests/all`.

**Spec:** `docs/SPEC_event_led_state.md`. Read §3 before Task 1.

## Global constraints

- Work in worktree `planetai-node-state`, on branch `issue-state-events-2026-10-06` off `origin/main` `9ef774b`.
- Only `shadow` and `events` change. A `rules` node, a node with no `events` block (`events is None`), and a fixture
  captured before v0.77 must give exactly today's `open_asks` and states.
- The replaced packs are every pack that ships a kinded rule:
  `{r["id"].split("/", 1)[0] for r in packs.load_rules() if r.get("kind")}`. That is the same expression as
  `uncovered_asks` and `run_rules`.
- An open event is `act` when `level == "act"` and it has no answer, or when `kind == "danger"` whatever the answer.
  It is `notable` when it has been answered, or for the warn-level spike. "Cleared recently" means `cleared_at`
  within `NOTABLE_HOURS` (24) of `now`.
- No change to `/issues`' keys (`tools/check_wire.py` stays green untouched), to ρ, `/effect` or the funnel, or to
  `app/events*.py`.
- Never import app `main` in a test. A test file ends with a print or `sys.exit`: add checks above the last line.
- `make lint && make test` before every commit (the pre-commit hook runs both, about 2 minutes).

## Files

| file | change |
|---|---|
| `app/issues/engine.py` | `compute` (the replaced set worked out before the loop; each issue's events passed in); `_asks(..., owned)`; `_state(..., ev)`; `_reason_text` (`kind`, `who`, `word`) |
| `app/issues/__init__.py` | `REASON_WORDS`: `event_open`, `event_answered`, `event_cleared` and `someone`, in en, id and es |
| `tests/test_events_wire.py` | replay cases for every rule |
| `docs/site/dashboard.md`, `docs/site/api.md` (if it describes states), `CHANGELOG.md` | the states on an events node |

---

### Task 1: the replaced packs' alerts are not asks

**Files:** modify `app/issues/engine.py` (`compute`, around lines 1207–1290; `_asks`, around line 640); test in
`tests/test_events_wire.py`.

**Interfaces:**
- Produces: `_asks(d, alerts, actions, stack, line, domain_of, now, owned=frozenset())`. Inside `compute`, a local
  `owned: set[str]` is worked out before the per-issue loop.

- [ ] **Step 1: The failing test,** above the last `print` of `tests/test_events_wire.py`. `SNAP`, `DECLS`,
  `Settings`, `engine` and `json` already exist in the file.

```python
def _block(engine_name, open_=(), recent=()):
    return {"engine": engine_name, "buttons": {"done": "Done", "not_now": "Not now", "doesnt_fit": "Doesn't fit"},
            "open": list(open_), "recent": list(recent), "cleared_today": 0, "last_cleared": None}


def _replay(block):
    s = json.loads(json.dumps(SNAP))
    s["issues"]["events"] = block
    return engine.replay(s, Settings(), DECLS)


OWNED = ("heat/", "air-quality/")
base = engine.replay(json.loads(json.dumps(SNAP)), Settings(), DECLS)
all_asks = {k: [a["rule_id"] for a in (v.get("open_asks") or [])] for k, v in base["issues"].items()}
assert any(r.startswith(OWNED) for rs in all_asks.values() for r in rs), "21d has old heat/air asks to filter"
for eng in ("events", "shadow"):
    got = _replay(_block(eng))
    kept = [a["rule_id"] for v in got["issues"].values() for a in (v.get("open_asks") or [])]
    assert not [r for r in kept if r.startswith(OWNED)], (eng, kept)
    assert sorted(kept) == sorted(r for rs in all_asks.values() for r in rs if not r.startswith(OWNED)), eng
ruled = _replay(_block("rules"))
assert {k: [a["rule_id"] for a in (v.get("open_asks") or [])] for k, v in ruled["issues"].items()} == all_asks, \
    "on rules, open_asks is exactly today's"
print("  open_asks: on shadow and events the replaced packs' alerts are not asks; on rules and with no block, unchanged")
```

- [ ] **Step 2: Run it and watch it fail.** Run `PACKS_DIR=packs PYTHONPATH=app python3 tests/test_events_wire.py`.
  It fails on the `not [r for r in kept …]` assertion.
- [ ] **Step 3: The code.**
  - **In `_asks`,** add the parameter `owned=frozenset()`, and change the `mine` line to
    `mine = [a for a in alerts if _mine(d, a.get("rule_id", ""), domain_of) and str(a.get("rule_id") or "").split("/", 1)[0] not in owned]`.
    Add one docstring sentence: "`owned` is the packs the alert engine replaced (docs/SPEC_event_led_state.md §3.1):
    on a shadow or events node their alerts are what the events stand for, so they are not this issue's asks."
  - **In `compute`,** just after `domain_of = …`, work out the set once:

```python
    # The packs the alert engine replaced: any pack that ships a kinded rule (app/main.py run_rules, #184). On shadow
    # and events their old rules' alerts are what the events stand for, so they are not asks of their own: not in
    # open_asks, not in uncovered_asks, and not what an issue's state is read from (docs/SPEC_event_led_state.md).
    owned = ({r["id"].split("/", 1)[0] for r in packs.load_rules() if r.get("kind")}
             if events is not None and events.get("engine") in ("shadow", "events") else set())
```

  - **Pass it:** `_asks(d, data["alerts"], data["actions"], stack, line, domain_of, now, owned)`.
  - **In the `uncovered_asks` block after `_lead`,** delete its own `owned = …` lines and use the one above. Keep the
    rest of that block as it is, because spec §3.1 says to keep the computation.
- [ ] **Step 4: Run it and watch it pass.** Then run
  `PACKS_DIR=packs PYTHONPATH=app python3 tests/test_issues_engine.py` (no block in those fixtures, so nothing
  changes) and `python3 tools/check_wire.py`.
- [ ] **Step 5: Commit** (with `make lint && make test` via the hook):
  `issues: on shadow and events, the replaced packs' alerts are not an issue's asks`, then a blank line and
  `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

---

### Task 2: the state follows the open event, and three reasons say why

**Files:** modify `app/issues/engine.py` (`_state`, around line 676; `_reason_text`, around line 713; the `_state`
call in `compute`) and `app/issues/__init__.py` (`REASON_WORDS`); test in `tests/test_events_wire.py`.

**Interfaces:**
- Consumes: Task 1's `owned`, `_block` and `_replay`.
- Produces:
  - `_state(d, stack, open_asks, recent, line, ev=None)`, where
    `ev = {"open": <the issue's open event dict or None>, "cleared": <its latest event cleared within NOTABLE_HOURS, or None>}`;
  - the reason codes `event_open` (`at`, `kind`, `event_id`), `event_answered` (`at`, `kind`, `who`, `stage`,
    `event_id`) and `event_cleared` (`at`, `kind`, `event_id`).

- [ ] **Step 1: The failing test,** above the last `print`. It uses heat, which has no asks left once its pack is
  filtered out, so nothing outranks the event.

```python
AS_OF = dt.datetime.fromisoformat(SNAP["as_of"])
iso = lambda d: (AS_OF - d).isoformat()            # noqa: E731


def ev(kind="sustained", level="act", answer=None, opened=dt.timedelta(hours=1)):
    return {"id": 9, "issue": "heat", "kind": kind, "level": level, "opened_at": iso(opened), "cleared_at": None,
            "alerts": [], "answer": answer}


def heat(block):
    v = _replay(block)["issues"]["heat"]
    return v["state"], v["reason"]["code"], v["reason_text"]["en"]


st, code, _ = heat(_block("events", [ev()]))
assert (st, code) == ("act", "event_open"), (st, code)
ack = {"stage": "acknowledged", "actor": "Tomas Diez", "ts": iso(dt.timedelta(minutes=10)), "held_until": None}
st, code, said = heat(_block("events", [ev(answer=ack)]))
assert (st, code) == ("notable", "event_answered") and "Tomas Diez" in said and "Not now" in said, (st, code, said)
st, code, _ = heat(_block("events", [ev(kind="danger", answer=ack)]))
assert (st, code) == ("act", "event_open"), "an answered danger event stays act"
st, code, _ = heat(_block("events", [ev(kind="spike", level="warn")]))
assert (st, code) == ("notable", "event_open"), "the warn-level spike is notable"
gone = dict(ev(), cleared_at=iso(dt.timedelta(hours=3)))
st, code, said = heat(_block("events", recent=[gone]))
assert (st, code) == ("notable", "event_cleared") and said, (st, code)
old = dict(ev(), cleared_at=iso(dt.timedelta(hours=30)))
assert heat(_block("events", recent=[old]))[1] != "event_cleared", "a clear older than 24 h is not notable"
assert _replay(_block("rules", [ev()]))["issues"]["heat"]["reason"]["code"] != "event_open", "rules: today's state"
led = _replay(_block("events", [ev(answer=ack)]))
assert led["lead"] == {"issue": "heat", "by": "event"}, "an answered open event still leads"
for loc in ("en", "id", "es"):
    assert "{" not in _replay(_block("events", [ev(answer=ack)]))["issues"]["heat"]["reason_text"][loc], loc
print("  state: an open act event is act until answered (danger stays act); answered or a spike is notable; "
      "a clear within a day is notable; rules unchanged")
```

  `dt` is imported at the top of the file; check that, and import `datetime as dt` if it isn't. Note: on `rules`,
  `events_wire.build` drops open events, but an injected block can still carry one. `compute` must ignore `ev` there,
  because the `owned` set and the event rules apply only on `shadow` and `events`.
- [ ] **Step 2: Run it and watch it fail** (`KeyError` or an assertion on `event_open`).
- [ ] **Step 3: `REASON_WORDS`.** In `app/issues/__init__.py`, add four keys to each language's block:

```python
        # en
        "event_open":       "an event open since {when} ({kind})",
        "event_answered":   "answered at {when} by {who} ({word}); the node is watching",
        "event_cleared":    "an event cleared at {when}",
        "someone":          "someone",
        # id
        "event_open":       "kejadian terbuka sejak {when} ({kind})",
        "event_answered":   "dijawab pada {when} oleh {who} ({word}); node sedang mengamati",
        "event_cleared":    "kejadian selesai pada {when}",
        "someone":          "seseorang",
        # es
        "event_open":       "un evento abierto desde las {when} ({kind})",
        "event_answered":   "respondido a las {when} por {who} ({word}); el nodo lo vigila",
        "event_cleared":    "un evento terminó a las {when}",
        "someone":          "alguien",
```

- [ ] **Step 4: `_reason_text`.** It gains `kind`, `who` and `word`. `word` comes from `actions.BUTTONS`, the table
  the page and the bot use: acted → `done`, acknowledged → `not_now`, dismissed → `doesnt_fit`. Add `import actions`
  next to `import packs` (both live in `app/`). Change the return to:

```python
    stage_key = {"acted": "done", "acknowledged": "not_now", "dismissed": "doesnt_fit"}.get(reason.get("stage"), "")
    word = (actions.BUTTONS.get(loc) or actions.BUTTONS["en"]).get(stage_key, "")
    return words.get(code, "").format(when=_hhmm(reason.get("at")), level=reason.get("level", ""),
                                      id=reason.get("alert_id", ""), peak=reason.get("peak", ""),
                                      peak_at=reason.get("peak_at", ""), kind=reason.get("kind", ""),
                                      who=reason.get("who") or words.get("someone", ""), word=word)
```

- [ ] **Step 5: `_state`.** Add the parameter `ev=None`. Right after the `context` return, insert:

```python
    # docs/SPEC_event_led_state.md §3.2: on a shadow or events node the open event says whether something is asked.
    e = (ev or {}).get("open")
    if e:
        a = e.get("answer")
        if e.get("level") == "act" and (not a or e.get("kind") == "danger"):
            return "act", {"code": "event_open", "at": e.get("opened_at"), "kind": e.get("kind"),
                           "event_id": e.get("id")}
        if a:
            return "notable", {"code": "event_answered", "at": a.get("ts"), "kind": e.get("kind"),
                               "who": a.get("actor") or "", "stage": a.get("stage"), "event_id": e.get("id")}
        return "notable", {"code": "event_open", "at": e.get("opened_at"), "kind": e.get("kind"),
                           "event_id": e.get("id")}
```

  Then, after the `if open_asks:` (stale) return and before the `if loud:` block, insert:

```python
    c = (ev or {}).get("cleared")
    if c:
        return "notable", {"code": "event_cleared", "at": c.get("cleared_at"), "kind": c.get("kind"),
                           "event_id": c.get("id")}
```

- [ ] **Step 6: Pass `ev` from `compute`.** Before the per-issue loop, after `owned`:

```python
    ev_open, ev_cleared = {}, {}
    if owned:                       # shadow or events: the events say what is asked (SPEC_event_led_state §3.2)
        for e in events.get("open") or []:
            ev_open.setdefault(e.get("issue"), e)
        for e in events.get("recent") or []:
            t = _ts(e.get("cleared_at"))
            if t is not None and now - t <= timedelta(hours=NOTABLE_HOURS):
                if e.get("issue") not in ev_cleared or t > _ts(ev_cleared[e["issue"]]["cleared_at"]):
                    ev_cleared[e.get("issue")] = e
```

  Then the call becomes
  `state, reason = _state(d, stack, open_asks, recent, line, {"open": ev_open.get(key), "cleared": ev_cleared.get(key)})`.
  `_ts` already exists in `engine.py` and handles strings and datetimes.

  `owned` is empty on a node whose packs ship no kinded rules, even on `events`. There the engine has nothing to
  replace and no events open, so today's state is right. Say so in the comment.
- [ ] **Step 7: Run it and watch it pass.** Then run `tests/test_issues_engine.py` and the whole of
  `tests/test_events_wire.py`.
- [ ] **Step 8: Commit:** `issues: an issue's state follows its alert event on shadow and events nodes`, then the
  `Co-Authored-By` line.

---

### Task 3: docs and CHANGELOG

**Files:** `docs/site/dashboard.md` (the paragraph "`GET /issues` is the whole of what the page knows…", in "Issues,
states and distances"), any other docs page that defines the states (`grep -rn "something is asked" docs/`), and
`CHANGELOG.md` (`## Unreleased`).

- [ ] **Step 1: The paragraph.** After the definition of the five states, add:

```markdown
On a node whose alert engine is `shadow` or `events`, the state follows the alert events: `act` while an event is
open and unanswered (a `danger` event stays `act` whatever the answer), `notable` once somebody has answered it, for
the warn-level air spike, and for a day after an event clears. The old heat and air rules' alerts are not asks there,
so they are not in `open_asks`. See `docs/SPEC_event_led_state.md`.
```

- [ ] **Step 2: Other pages.** Fix any other page that defines `act` as "an open alert", with the smallest true edit.
  A sentence inside a learn span (`tools/build_learn.py` MARKS) must move its span with it. Then run `make learn`.
- [ ] **Step 3: The CHANGELOG line,** under `## Unreleased`:

```markdown
- On a node whose alert engine is `shadow` or `events`, an issue's state follows its alert event: `act` while it is
  open and unanswered, `notable` once somebody answers, and for a day after it clears. The old heat and air alerts
  no longer count as open asks there, so the page's lead, the ask pane and the bot agree with what Decide shows.
```

- [ ] **Step 4:** Run `python3 tools/check_docs.py`, `python3 tools/build_learn.py --check`,
  `make lint && make test`, then commit: `docs: an issue's state on an events node`.

---

### Task 4: the PR, then node #1

- [ ] **Step 1:** Push and open the PR against `main`, with milestone **v0.78** and `needs testing`, in the format of
  `.github/pull_request_template.md`. Name the spec, and end with the attribution line.
- [ ] **Step 2: After Tomas's merge,** update node #1 (`planetai update`, as in `docs/WORKFLOW.md`). Then read
  `/issues`:
  - with an event open and answered, its issue reads `notable` with `event_answered`;
  - unanswered, it reads `act`;
  - `open_asks` holds only rules no event owns;
  - the page's lead kicker agrees with Decide.
  Then label the PR `tested: node 1` and comment what was seen.
