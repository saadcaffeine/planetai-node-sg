# Handoff: the trust pack, after v0.40

Written 7 September 2026, for the session that owns `app/main.py`, `app/report.py` and `app/packs.py`. v0.40 fixed
the three trust rules inside `packs/trust/` only. Five things it could not reach from there.

**(a) A `min_history_days` rule key would replace the SQL gate.** All three rules now carry the same seven-line
`seasoned` CTE, three copies of one idea:

```sql
seasoned AS (
  SELECT sensor_id FROM readings
  WHERE ts > now() - interval '30 days'
  GROUP BY 1 HAVING min(ts) < now() - interval '7 days')
```

It lives in SQL because a data pack must not need a loader change to be safe, and v0.40 was not allowed to touch
the loader. The right home is a rule key — `min_history_days: 7` in `rules.yml`, enforced in `app/packs.py` or
where `run_rules` reads a row's `sensor_id` in `app/main.py` — which would let every pack declare it and would
delete the three copies. Nothing else in the node has this concept yet.

**(b) These findings belong in the report and in Set up, not in the alert stream.** All three rules are now `info`
with a seven-day cooldown, which under `ALERT_LEVEL=act` means recorded, shown on the dashboard, and never sent.
That is the right floor but it is not a home: nothing yet says "your instruments were like this, this week" in
prose. The shape it wants is a weekly instrument paragraph in Sunday morning's report (a `contributes: report`
rule is the existing mechanism, `docs/PACKS.md`) plus the same facts against each sensor in the Set up view, where
someone is already looking at the hardware.

**(c) `/trust`'s card no longer agrees with `channel_dead`.** `app/main.py`'s `/trust` endpoint recomputes the
frozen-channel count with the v0.35 definition — six flat buckets of the last 24, latest bucket flat — so from
this release the card and the health check will count Ungasan Kit's light channel as frozen every evening while
the rule stays quiet. The card needs the same three changes the rule got: 24 flat buckets, a moving sibling
channel, and skip a flat value of 0. `tests/test_shipped.py` still pins `/trust`'s `alive` CTE, which is
unchanged, so nothing fails today; the divergence is silent, which is why it is written down here.

**(d) `local` looks stale on node #1, or `LOCAL_RADIUS_M` is not what the dump implies.** The 21:43 dump has
`sc-19236` (Ungasan Kit) and `sc-19874` (BAYU NEW ENCLOSURE) as `local = false`, yet the live node named both at
21:17, which only a `local = true` row can do — every trust rule filters on it. Both kits are ~1.6 km from
`NODE_LAT/NODE_LON`. Worth checking two things: the `LOCAL_RADIUS_M` actually in effect on node #1, and whether
`local` is recomputed when that setting changes rather than only at the next poll of each source. `tests/data/
node1-sensors.tsv` carries all five kits as `local = true`, which is the state that produced tonight's alerts.

**(e) Node #1 still has `ALERT_LEVEL=warn` stored.** Two of tonight's three warnings were `warn`, and they reached
Telegram, which cannot happen under the v0.39 default of `act`. A stored setting overlays `.env`, so the node kept
the value it was configured with before the default moved. Nothing in v0.40 touches it; whoever next opens node
#1's Set up view should decide whether that is deliberate.
