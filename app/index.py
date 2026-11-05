"""Index brick. Domain-blind.

  cells()  -> fci-cells-v0 rows this node can honestly compute, each with its provenance state
  rho()    -> action latency: how fast an alert became a human action, from the actions ledger

The core knows nothing about what a node measures. Two things are always computable:
  · Governance|<scale> — rho, because every node has alerts and an actions ledger
  · whatever domain packs contribute via cells.yml (docs/PACKS.md)

The cell key is 'Pillar|Scale' (canonical, FCI Observations base). State is live | partial | mock and is
never upgraded here or downstream.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone

import learn
import packs
import registry
import settings

log = logging.getLogger("planetai.index")
CITY = os.getenv("NODE_CITY", "unknown")
SCALE = os.getenv("NODE_SCALE", "community").capitalize()


_ro = {"missing": False}


def run_ro(cur, sql: str, params=None) -> list:
    """Run one pack statement as planetai_ro (init.sql ≥ 0.21): SELECT on every table but settings, no writes. The role
    switch lives inside a transaction so it ends with the statement, whatever happens to it. On a database that has
    not been updated yet the role is missing: say so once and run as the owner, rather than silence every rule."""
    if not _ro["missing"]:
        try:
            with cur.connection.transaction():
                cur.execute("SET LOCAL ROLE planetai_ro")
                cur.execute(sql, params)
                return cur.fetchall()
        except Exception as e:  # noqa: BLE001
            if "planetai_ro" in str(e) and "does not exist" in str(e):
                _ro["missing"] = True
                log.warning("role planetai_ro is missing (schema before 0.21): pack SQL runs as the database owner until planetai update")
            else:
                raise
    cur.execute(sql, params)
    return cur.fetchall()


def _row(cell: str, value, unit: str, source: str, state: str, note: str = "") -> dict:
    # `registered` and `adapter` are what the network knows about this cell, from the snapshot at
    # data/sources (app/registry.py). Additive, and no new judgement: `state`, `value`, `unit` and
    # `source` are untouched and still mean exactly what they meant. They answer, on a row that is
    # already here, "is what I am showing the only thing there is" — 31 sources filed for
    # Governance|City is a different sentence from 1.
    #
    # WHAT THIS DOES NOT DO: the rows below are only the ones this node can COMPUTE — a pack cell
    # with a value, plus Governance|<scale>. A cell with a registered source and no adapter has no
    # row here at all, and does not get one: `cells-ingest` upserts every row it is handed, and a
    # node emitting twenty empty rows would write twenty empty rows into the Index. That question is
    # `GET /sources?cell=Social|City` and `planetai sources --cell`, which is the half of the 5
    # September table `/cells` structurally cannot answer.
    #
    # THE GROUPING DECISION, TAKEN. The comment that stood here asked whether these numbers should
    # say "something reads a source that FILLS this cell" rather than "…that is FILED under it", and
    # said it was a decision rather than a fix. It is taken: registry.cell_counts() groups by
    # `feeds_cells` and falls back to the path only when that key is absent, and it counts no
    # deprecated, stale, paywalled or planned entry at all.
    #
    # `registered` KEEPS ITS NAME AND CHANGES ITS MEANING, which is the one thing here that is not
    # purely additive. It was "entries filed under this cell, any status"; it is now the `reviewed`
    # count — live entries backed by an adapter or a usable review. Governance|City goes from 32 to
    # 4. The old number was not a smaller version of the new one, it was a different claim, and 32
    # was the number that made the Index look answered when it was not.
    c = registry.cell_counts().get(cell, {"capable": 0, "reviewed": 0, "candidate": 0})
    return {"city": CITY, "cell": cell, "value": None if value is None else round(float(value), 3), "unit": unit,
            "source": source, "observed_at": datetime.now(timezone.utc).isoformat(), "state": state, "notes": note,
            "registered": c["reviewed"], "adapter": c["capable"] > 0,
            "reviewed": c["reviewed"], "candidate": c["candidate"], "capable": c["capable"]}


def _buckets(cur) -> dict:
    """The core's honesty check for a pack cell that wants to claim `live`: how much in-custody data exists in
    the last 24h, counted three ways.

    In CUSTODY, not local. `local` is this node's own instrument, here; custody is `local OR kind='child'`, so a
    child's hourly means count and a peer's sensor across the street does not, whatever its coordinates. Before
    this the count was `WHERE s.local`, and a community node aggregating ten homes counted zero — the roll-up
    path was built and could never say `live`. The predicate itself lives in `init.sql` as a generated column,
    so it is one word here and cannot drift from the fifteen other places that ask the question.

    `sensors` and `children` are for `min_sensors` (see `cells`): one child reporting is one household's
    kitchen, and a cell that says `live` off one kitchen is the same lie as a model claiming it.
    """
    cur.execute("""SELECT count(*) AS n, count(DISTINCT r.sensor_id) AS sensors,
                          count(DISTINCT split_part(r.sensor_id, '/', 1))
                            FILTER (WHERE s.kind = 'child') AS children
                   FROM readings_1h r JOIN sensors s USING (sensor_id)
                   WHERE s.custody AND r.bucket > now() - interval '24 hours'""")
    row = cur.fetchone() or {}
    return {"buckets": int(row.get("n") or 0), "sensors": int(row.get("sensors") or 0),
            "children": int(row.get("children") or 0)}


def cells(cur) -> list[dict]:
    out: list[dict] = []

    # ---- domain cells, contributed by packs. The core evaluates the SQL and polices the provenance.
    try:
        import packs
        defs = packs.cells()
    except Exception as e:  # noqa: BLE001
        log.warning("packs unavailable: %s", e); defs = []
    counts = _buckets(cur) if defs else {"buckets": 0, "sensors": 0, "children": 0}
    have = counts["buckets"]
    # A node that aggregates may not say `live` off one instrument. Two in-custody sensors from two different
    # children is the smallest thing that is a place rather than a room — decided 12 September 2026, see
    # docs/decisions/2026-09-10-custody.md. A home node with one kit is a home node and is left alone: it
    # describes one address and its `unit` string says so.
    need_sensors = 2 if (counts["children"] or SCALE.lower() != "community") else 1
    thin = bool(counts["sensors"] < need_sensors or 0 < counts["children"] < 2)
    for c in defs:
        try:
            rows = run_ro(cur, c["sql"])
            row = rows[0] if rows else None
        except Exception as e:  # noqa: BLE001
            log.warning("pack cell %s failed: %s", c.get("cell"), e); continue
        if not row or row.get("value") is None:
            continue
        state = c.get("state", "partial")
        need = int(c.get("min_buckets", 0))
        if state == "live" and need and have < need:
            state = "partial"          # a pack may not claim live before the data supports it
        if state == "live" and thin:
            state = "partial"          # nor off too few instruments, however many hours they have filled
        note = c.get("notes", "")
        if need:
            note = (note + f" · {have}/{need} hourly buckets").strip(" ·")
        if counts["children"]:
            note = (note + f" · {counts['sensors']} sensors across {counts['children']} children").strip(" ·")
        out.append(_row(c["cell"], row["value"], c.get("unit", ""), f"planetai-node · pack:{c['pack']}", state, note))

    # ---- Governance|<scale>: is anyone acting on what this node says. Always computable, any domain.
    rr = rho(cur)
    if rr["alerts_act"]:
        out.append(_row(f"Governance|{SCALE}", rr["rho"],
                        "rho — share of act-level alerts answered within 24h (30d)",
                        "planetai-node actions ledger", "partial" if rr["acted"] < 5 else "live",
                        f"{rr['acted']}/{rr['alerts_act']} acted; median detect-to-act {rr['median_minutes']} min"))
    return out


def _replaced() -> list[str]:
    """The packs whose rule rows go unsent on this node, because the event engine speaks for them (learn.replaced)."""
    try:
        return sorted(learn.replaced(packs.load_rules(), settings.get("ALERT_ENGINE", "rules") or "rules"))
    except Exception as e:  # noqa: BLE001
        log.warning("cannot read the rule set, so every act-level alert row counts as sent: %s", e)
        return []


def rho(cur, days_ago: int = 0) -> dict:
    """rho over the last 30 days: share of level='act' alerts that got an 'acknowledged' or 'acted' row within 24h,
    plus median detect-to-act latency in minutes. The address-scale instrument for H0-A.

    THIS NODE'S ALERTS AND ITS CHILDREN'S TOGETHER. A child pushes one row per alert it raised, as timestamps
    and nothing else (main.py::push_events), and they pool here: an aggregator measures the action latency of
    the district it aggregates, not only of the alerts it happened to raise itself. A node with no children
    reads an empty `events` table and gets exactly the number it got before.

    The child never sends a ratio — a mean of ten ratios is not the ratio of the pooled counts. It sends the
    two timestamps and the definition of rho stays here, which is why a change to this query reaches every
    child's history at once with nothing to re-push.

    days_ago moves the whole 30-day window back, so the report can say whether the number moved this week without
    keeping a second copy of this query anywhere.

    ONLY WHAT WAS SENT IS ASKED. On ALERT_ENGINE=events the engine speaks for the packs it replaced, and from its
    first sent message on, those packs' `alerts` rows are written and never sent (learn.replaced, learn.silent). Counting
    them asked node #1 289 times in 30 days for 9 messages that went out, and published rho as 0.028 (20 Oct). So a
    replaced pack's row after the switch is left out, and each event the engine sent at act level is asked once, at
    its first sent message, answered by an `actions` row carrying its event_id. Packs the engine does not replace
    (nearby, a wild pack) still send through rules and still count as before; on a rules node nothing changes."""
    rep = _replaced()
    cur.execute("""WITH ref AS (SELECT now() - make_interval(days => %(back)s) AS t),
                        sw AS (SELECT min(ts) AS t FROM event_messages WHERE sent AND mode = 'events'),
                        a AS (SELECT ('self/' || id) AS id, ts FROM alerts, ref, sw
                              WHERE level='act' AND ts > ref.t - interval '30 days' AND ts <= ref.t
                                AND NOT (split_part(rule_id, '/', 1) = ANY(%(rep)s::text[]) AND sw.t IS NOT NULL AND ts >= sw.t)
                              UNION ALL
                              SELECT ('ev/' || e.id), min(m.ts) FROM alert_events e
                                JOIN event_messages m ON m.event_id = e.id AND m.sent AND m.mode = 'events'
                                                     AND m.reason IN ('open', 'escalate')
                              WHERE e.level = 'act'
                              GROUP BY e.id
                              HAVING min(m.ts) > (SELECT t FROM ref) - interval '30 days' AND min(m.ts) <= (SELECT t FROM ref)
                              UNION ALL
                              SELECT (e.child || '/' || e.alert_id), e.raised_at FROM events e, ref
                              WHERE e.level='act' AND e.raised_at > ref.t - interval '30 days' AND e.raised_at <= ref.t),
                        f AS (SELECT ('self/' || alert_id) AS id, min(ts) AS t FROM actions
                              WHERE stage IN ('acknowledged','acted') AND alert_id IS NOT NULL GROUP BY alert_id
                              UNION ALL
                              SELECT ('ev/' || event_id), min(ts) FROM actions
                              WHERE stage IN ('acknowledged','acted') AND event_id IS NOT NULL GROUP BY event_id
                              UNION ALL
                              SELECT (child || '/' || alert_id), least(responded_at, acted_at) FROM events
                              WHERE responded_at IS NOT NULL OR acted_at IS NOT NULL)
                   SELECT count(a.id) AS alerts_act,
                          count(f.id) FILTER (WHERE f.t - a.ts < interval '24 hours') AS acted,
                          percentile_cont(0.5) WITHIN GROUP (ORDER BY extract(epoch FROM f.t - a.ts)/60)
                            FILTER (WHERE f.t - a.ts < interval '24 hours') AS median_minutes
                   FROM a LEFT JOIN f ON f.id = a.id""", {"back": days_ago, "rep": rep})
    r = cur.fetchone() or {}
    n, acted = int(r.get("alerts_act") or 0), int(r.get("acted") or 0)
    out = {"window_days": 30, "days_ago": days_ago, "alerts_act": n, "acted": acted, "rho": round(acted / n, 3) if n else None,
           "median_minutes": round(float(r["median_minutes"])) if r.get("median_minutes") is not None else None}
    out["funnel"] = _funnel(cur, days_ago)
    return out


# How long a rule must stay silent after the act before its condition counts as cleared. It has to be at least the
# longest cooldown of any act-level rule, core or pack: a rule with a 3-day cooldown asked a 2-day question would be
# called measured while it was merely waiting its turn to fire again. Today the slowest is nearby/only_here at 2880.
# tests/test_share.py asserts no act-level rule outgrows this, so a pack that adds a slower one fails a check instead
# of quietly turning "we have not looked yet" into "it worked".
MEASURED_WINDOW_MIN = 2880

def _live_rule_ids() -> list[str]:
    """The rule ids this node still evaluates. A retired rule — renamed, uninstalled with its pack, or a one-off test
    id — cannot fire again whatever the household does, so its silence is not evidence that anything was fixed. On
    node #1 three of eight derived measurements were exactly this: two `_test/hello-<epoch>` alerts and one
    `indoor_pm25_high` from before pack ids were prefixed, each counted as a closed loop for free."""
    try:
        return [str(r["id"]) for r in packs.load_rules() if isinstance(r, dict) and r.get("id")]
    except Exception as e:  # noqa: BLE001
        log.warning("cannot read the rule set, so no measurement can be derived: %s", e)
        return []


def _funnel(cur, days_ago: int = 0) -> dict:
    """How far the asks got, stage by stage, and how long each step took.

    `measured` IS DERIVED, NOT POSTED. Nothing in the node writes a measured row — main.py::post_action takes
    acknowledged, acted and decided, and refuses measured — so counting posted rows would report a structural
    zero as a household that never checks its work. What the node does have is the rule itself: run_rules re-fires an alert as soon as its cooldown
    expires and the condition still holds. So an act followed by MEASURED_WINDOW_MIN of silence from the same rule on
    the same sensor is the condition having stopped being true, on every node, retroactively, with nobody asked to
    learn a new habit. A posted measured row still counts if one ever arrives.

    This is evidence of WHETHER, not of WHEN — see latency_minutes below.

    NOT A SECOND RHO, and the query above is untouched. rho is one number with a specification of
    its own (docs/SPEC_rho.md) and its `acted` means "acknowledged OR acted, within 24 hours" — a
    deliberately generous test of whether anybody answered at all. The funnel's `acted` is the
    literal stage. The two will not agree and are not meant to; they are different questions asked
    of the same ledger, which is why this is a separate query returning separate names.
    
    THIS NODE'S OWN ALERTS ONLY. rho pools its children's, because a child pushes the two timestamps
    that rho is defined on. It does not push stages — `events` carries `responded_at` and `acted_at`
    and no notion of `measured` — so a pooled funnel would report every child's ask as never reaching
    a stage the child cannot express. One node's ledger, honestly, beats a district's with a hole.

    The latencies are medians between CONSECUTIVE stages, each falling back to the last stage that
    actually happened: an ask acted on without being acknowledged first is measured from when it was
    asked, not from a timestamp that does not exist."""
    rep = _replaced()
    cur.execute("""WITH ref AS (SELECT now() - make_interval(days => %(back)s) AS t),
                        sw AS (SELECT min(ts) AS t FROM event_messages WHERE sent AND mode = 'events'),
                        a AS (SELECT id, ts, rule_id, sensor_id FROM alerts, ref, sw
                              WHERE level='act' AND ts > ref.t - interval '30 days' AND ts <= ref.t
                                AND NOT (split_part(rule_id, '/', 1) = ANY(%(rep)s::text[]) AND sw.t IS NOT NULL AND ts >= sw.t)),
                        s AS (SELECT alert_id, stage, min(ts) AS t FROM actions
                              WHERE stage IN ('acknowledged','acted','measured') GROUP BY alert_id, stage),
                        -- Derived: the rule had a full MEASURED_WINDOW_MIN after the act to fire again on the same
                        -- sensor and did not, so its condition stopped being true. main.py::run_rules re-fires a rule
                        -- the moment its cooldown expires and the condition still holds, so silence across a window
                        -- longer than any act-level cooldown is evidence, not absence of evidence.
                        der AS (SELECT a.id AS alert_id, act.t
                                FROM a
                                JOIN s act ON act.alert_id = a.id AND act.stage = 'acted'
                                CROSS JOIN ref
                                WHERE a.rule_id = ANY(%(live)s)
                                  AND ref.t > act.t + make_interval(mins => %(win)s)
                                  AND NOT EXISTS (SELECT 1 FROM alerts r
                                                  WHERE r.rule_id = a.rule_id
                                                    AND r.sensor_id IS NOT DISTINCT FROM a.sensor_id
                                                    AND r.ts > act.t
                                                    AND r.ts <= act.t + make_interval(mins => %(win)s))),
                        m AS (SELECT alert_id FROM s WHERE stage = 'measured'
                              UNION SELECT alert_id FROM der)
                   SELECT count(*) AS asked,
                          count(ack.t) AS acknowledged,
                          count(act.t) AS acted,
                          count(mea.alert_id) AS measured,
                          percentile_cont(0.5) WITHIN GROUP (
                            ORDER BY extract(epoch FROM ack.t - a.ts)/60) AS to_acknowledged,
                          percentile_cont(0.5) WITHIN GROUP (
                            ORDER BY extract(epoch FROM act.t - coalesce(ack.t, a.ts))/60) AS to_acted
                   FROM a
                   LEFT JOIN s ack ON ack.alert_id = a.id AND ack.stage = 'acknowledged'
                   LEFT JOIN s act ON act.alert_id = a.id AND act.stage = 'acted'
                   LEFT JOIN m mea ON mea.alert_id = a.id""",
                {"back": days_ago, "win": MEASURED_WINDOW_MIN, "live": _live_rule_ids(), "rep": rep})
    f = dict(cur.fetchone() or {})
    # the event engine's episodes sent at act level are asked too, answered by their event_id (see rho()). They have
    # no derived `measured`: that reads a rule firing again, and an episode does not; a posted measured row counts.
    cur.execute("""WITH ref AS (SELECT now() - make_interval(days => %(back)s) AS t),
                        e AS (SELECT e.id FROM alert_events e
                                JOIN event_messages m ON m.event_id = e.id AND m.sent AND m.mode = 'events'
                                                     AND m.reason IN ('open', 'escalate')
                              WHERE e.level = 'act' GROUP BY e.id
                              HAVING min(m.ts) > (SELECT t FROM ref) - interval '30 days' AND min(m.ts) <= (SELECT t FROM ref))
                   SELECT count(*) AS asked,
                          count(*) FILTER (WHERE EXISTS (SELECT 1 FROM actions x WHERE x.event_id = e.id AND x.stage = 'acknowledged')) AS acknowledged,
                          count(*) FILTER (WHERE EXISTS (SELECT 1 FROM actions x WHERE x.event_id = e.id AND x.stage = 'acted')) AS acted,
                          count(*) FILTER (WHERE EXISTS (SELECT 1 FROM actions x WHERE x.event_id = e.id AND x.stage = 'measured')) AS measured
                   FROM e""", {"back": days_ago})
    ev = cur.fetchone() or {}
    for k in ("asked", "acknowledged", "acted", "measured"):
        f[k] = int(f.get(k) or 0) + int(ev.get(k) or 0)
    rnd = lambda k: round(float(f[k])) if f.get(k) is not None else None      # noqa: E731
    return {
        "stages": {k: int(f.get(k) or 0) for k in ("asked", "acknowledged", "acted", "measured")},
        # `measured` has no latency on purpose. The derivation proves the condition stopped being true somewhere
        # inside the window, never when — a median of window-ends would be a near-constant 48h dressed up as a
        # measurement. It says whether the loop closed, not how fast.
        "latency_minutes": {"acknowledged": rnd("to_acknowledged"), "acted": rnd("to_acted"), "measured": None},
        "measured_derived": True,
        "measured_window_minutes": MEASURED_WINDOW_MIN,
        "self_only": True,
    }
