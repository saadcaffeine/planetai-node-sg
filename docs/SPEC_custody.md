# SPEC — custody, and what `local` is actually for

**Status: approved 12 September 2026 and implemented in v0.50.** §3's open question was answered yes, as
recommended. §6 is the one part NOT built: its own trigger is "after Bali has published once", and Bali has
not. Everything else below describes the tree rather than proposing to it — where a sentence still reads as a
proposal, the code is what happened.

Two findings arrived on 10 September 2026 from two sessions that did not know about each other. Both are
correct. They point at the same column from opposite sides.

- **FCI ingestion map, gap 1.** `receive_aggregates()` stores a child's hourly means as `local=FALSE`,
  `kind='child'`. `app/index.py::_buckets()` counts only `WHERE s.local`. A community node aggregating ten
  homes therefore has **zero** local buckets, so every pack cell that wants `live` is demoted to `partial`.
  The roll-up path is built and cannot say `live`.
- **Peer-visibility §3.** `local=FALSE` is exactly the guard that keeps a stranger's node — `kind='peer'`,
  display-only — out of every Index cell, structurally rather than by convention. `/nearby` already stores
  other people's stations that way.

> **Provenance note** (rewritten 13 September, after searching properly).
>
> **`docs/proposals/peer-visibility.md` exists and is now in this repository.** It was written on
> 10 September into a *session scratchpad* — `/private/tmp/.../scratchpad/peer-visibility.md` — never into
> the repo, which is why the first version of this note said it was nowhere. I had searched the project
> tree and every git branch, and not `/private/tmp`. Recovered and committed unchanged, with an editor's
> note; its §3 and §9.4 say what this spec attributes to them.
>
> **The FCI ingestion map was not found, anywhere.** Not in any repo or branch, any scratchpad, any of the
> 28 session transcripts on this machine, or the home directory. The only file here that mentions an
> "ingestion map" is the transcript of the session that wrote this spec — i.e. the brief quoting it. So
> gap 1 is restated from the brief, not read from a document. It was nonetheless correct in every detail
> the code could check, which says nothing about the other four gaps.
>
> Everything below §1 is read from the tree, and §8's node #1 figures from node #1.

---

## §1 · The two meanings, with the lines

### What the core reads

`app/index.py:52`, the honesty check that decides whether any pack cell may say `live`:

```sql
SELECT count(*) AS n FROM readings_1h r JOIN sensors s USING (sensor_id)
WHERE s.local AND r.bucket > now() - interval '24 hours'
```

`packs/heat/cells.yml:13`, one pack cell, reading the same column directly:

```sql
JOIN sensors s ON s.sensor_id = t.sensor_id
WHERE s.local AND s.indoor AND t.metric = 'temp' AND t.bucket > now() - interval '30 days'
```

### What the column says it means

`init.sql:14–15`:

```sql
local     BOOLEAN NOT NULL DEFAULT FALSE,   -- TRUE = physically at this node (ours). FALSE = reference/context.
kind      TEXT NOT NULL DEFAULT 'sensor',   -- sensor | portal | model | survey | child   (how the number was produced)
```

`local` was written on 2 September 2026 in `74a8b64` ("planetai-node v0.1 — node #1 live"), when a node was a
house and nothing else existed. `kind` did not exist yet; it arrived the next day in `15785db` (v0.4.3,
"multi-scale ingestion"), the same commit that wrote `_buckets`'s `WHERE s.local` and the `child` push. So the
honesty check was written for a home node on the same afternoon the roll-up path was invented, and nobody
reconciled them. That is the whole bug, and it is a day old in the history.

### The correction the brief needs

The brief says `local` is carrying geography and custody at once. **Read the code: it is not carrying
geography alone, and it never was.** `app/sources.py:70`:

```python
def stamp_local(sensors, lat, lon, radius_m):
    """`local` is ours AND here. The adapter decides ours; distance decides here.

    Only ever narrows: a sensor an adapter did not claim never becomes local, whatever its coordinates."""
    for s in sensors:
        if not s.get("local"):
            continue                     # ← a peer is never promoted by being close
```

`local` is already **claim ∧ proximity**. The adapter asserts "this is ours"; `LOCAL_RADIUS_M`
(`app/settings.py:53`, default 500 m) can only take that claim away. A peer across the street is `local=FALSE`
because no adapter claimed it — not because of its distance. That matters, because it means the fix is one
disjunct, not a new column, and the existing rows need no migration.

The one thing `local` genuinely cannot express is a **child**: in this node's chain, may roll up, and 400 m
down the lane.

### Every kind of row the `sensors` table holds today

One representative row per shape, as it is actually written. `kind` is the literal value in the column, not a
category name — there is no `'own'` kind and there is no `'peer'`, `'external'` or `'nearby'` kind.

| the row | written by | `kind` | `local` | in custody? | may reach a cell? |
|---|---|---|---|---|---|
| `sc-19874` "BAYU NEW ENCLOSURE" — the house's own kit | `sources.smartcitizen` → `main.py:115` | `sensor` | **TRUE** | yes | **yes, may be `live`** |
| `pod-<id>` — a Meshtastic/MQTT pod, no coordinates | `main.py:182` (`_store`) | `sensor` | **TRUE** | yes | yes, `live` |
| a phone or contributor `POST /readings` | `main.py:182` | `sensor` | **TRUE** | yes | yes, `live` |
| `mahon1/sc-19874` — a child's hourly mean | `main.py:1625` (`receive_aggregates`) | `child` | **FALSE** | **yes** | **yes — and this is what is broken** |
| `bad-46949` — a Bali Air Dispatch station, 300 m away | `sources.baliairdispatch` (`sources.py:243`) | `sensor` | FALSE | no | `partial` only, as `Environmental\|City` |
| a stranger's node, heard over Reticulum today | `main.py:554` — **in memory only, no `sensors` row** | — | — | no | **never** |
| a stranger's node, once `docs/proposals/peer-visibility.md` §9.4 lands | not written yet | `peer` | FALSE | no | **never** |
| `openmeteo-point`, `marine-point`, `earth-point`, `ee-point` | `sources.py:379,426`, `bootstrap.py:62` | `model` | FALSE | no | `partial` only, never `live` |
| a CKAN dataset row | `sources.py:404` | `portal` | FALSE | no | `partial` only |
| `place-point` — OSM footprints around the node | `packs/place/adapter.py:268` | `map` | FALSE | no | `partial` only |
| a survey response | declared in `init.sql:15`, **never written** | `survey` | — | (yes, when it exists) | `partial` |

Read the two bold rows together and the whole argument is there: **`child` is the only in-custody row that is
not `local`, and that is the only reason `_buckets` is wrong.** Everything else the table holds is already
classified correctly by `local` alone.

> **This table was wrong when it was written, and the correction is worth more than the table.** It was built by
> reading `app/` and `init.sql`, and it missed `kind='map'` — written by a *pack*, `packs/place/adapter.py`, and
> present on node #1 the whole time. `kind` is not a closed set the core owns: any code pack can invent one.
>
> So the rule cannot rest on enumerating kinds, and this is the invariant that actually carries it:
> **`local=TRUE` is only ever written alongside `kind='sensor'`** — `sources.py:127,271,297,492`, `main.py:181`.
> Every other kind a pack or an adapter writes, `map` and `model` and `portal` included, sets `local=False`.
> That is why `s.local AND kind <> 'peer'` is safe against kinds nobody has invented yet, and why a table of
> today's kinds was never the load-bearing part.

---

## §2 · The change, smallest form

### Recommended: no new column, no migration, one disjunct

```
custody  ≡  s.local OR s.kind = 'child'
```

`local` keeps the meaning `stamp_local` already gives it — *this node's own instrument, here*. It stops being
the custody test and becomes one of its two terms. `_buckets` and the cell SQL read custody; nothing else
changes.

**Why not `kind IN ('own','child')`, which the brief recommends.** It cannot be written: there is no `'own'`
kind. The nearest real spelling is `kind IN ('sensor','child')`, and that is **wrong on every `/nearby` row**.
`sources.baliairdispatch` writes other people's stations with `local=False` and no `kind`, so `main.py:123`'s
default fills in `kind='sensor'` — identical to the house's own kit. Node #1 holds up to 87 of these. Under
`kind IN ('sensor','child')` the entire Bali Air Dispatch ring becomes in-custody, `Environmental|Community`
starts averaging the island into the house's number, and the honesty check counts a stranger's data as proof
this node is measuring. That is a worse bug than the one being fixed.

The deeper reason is worth writing down, because it is the same mistake twice: **`kind` answers *how the
number was produced*** — its own comment at `init.sql:15` says so. A Bali Air Dispatch station is produced
exactly the way our kit is. It *is* a sensor. Loading custody onto `kind` would overload a second column the
way `local` got overloaded, and the next session would write a third spec.

**Explicitly checked, as asked:**

- **`nearby`'s rows** — `kind='sensor'`, `local=FALSE`. Correctly **out** of custody under the recommended
  rule, with no migration. They stay in the `stats` view (`init.sql:74` filters `s.kind='sensor'`), which is
  what `packs/nearby/rules.yml:41` and air-quality's `Environmental|City` cell need. Changing their `kind`
  would drop them out of `stats` into `observations` and silently kill the ring.
- **Open-Meteo's `kind='model'` rows** — `local=FALSE`. Correctly out. A model must never make a cell `live`
  (`AGENTS.md`: "A model or a portal is `partial`, whatever its quality"). Note `bootstrap.py:62` writes
  `openmeteo-point` with `"local": False` explicitly, so even the first-run prefill is safe.
- **`portal` rows** — `local=FALSE`. Out. Same reasoning.
- **`child` rows** — `local=FALSE`, `kind='child'`. In, via the new disjunct. This is the fix.

### The one case that forces something more

A `kind='peer'` row written with `local=TRUE` — a stranger's node genuinely across the street, geographically
inside `LOCAL_RADIUS_M` — satisfies `s.local` and would reach a cell. Today no code path can create it, and
the reason is stronger than `stamp_local` only narrowing: **a peer has no database row at all.** Since #33 a
node hears other nodes over Reticulum and `main.py:554` keeps them in `reticulum_state["peers"]`, in memory,
as a name and a coarse H3 cell with no readings attached. Peer-visibility §9.4 would be the first time a
stranger's node got a `sensors` row, and that is the moment this stops being structurally impossible and
starts being a rule someone has to keep. A hand-edited row, a restore from another node's dump, or an adapter
that forgets could then do it.

Do not answer that by pasting `AND s.kind <> 'peer'` into fifteen SQL statements. `local` is read in 2 pack
cells, `_buckets`, and about a dozen rules; a predicate repeated fifteen times drifts within a month. Two
ways to say it once, both one line:

```sql
-- (a) recommended: the predicate lives in the schema, every SQL reads one word
ALTER TABLE sensors ADD COLUMN IF NOT EXISTS custody BOOLEAN
  GENERATED ALWAYS AS (kind = 'child' OR (local AND kind <> 'peer')) STORED;

-- (b) or refuse the row at the boundary and keep `local OR kind='child'` in the SQL
ALTER TABLE sensors ADD CONSTRAINT sensors_peer_not_local CHECK (NOT (local AND kind = 'peer'));
```

**Recommend (a).** It is a generated column, not a column anyone writes: no writer changes, no migration of
values, no way for it to disagree with `local` and `kind`. Postgres 16 (`docker-compose.yml:4`,
`imresamu/postgis:16-3.4-alpine`) has had generated columns since 12. `init.sql` is idempotent and re-applied
by `update.sh`, so this is additive in the way every other `ALTER ... IF NOT EXISTS` in that file is.

(b) is smaller but fails closed on an existing node: the `ALTER` is refused if a bad row already exists, which
turns a schema apply into a support ticket. (a) recomputes for every row and cannot fail.

**Kind values after this change:** `sensor | portal | model | survey | child | peer`. One added — `peer`, from
peer-visibility §9.4 — and `init.sql:15`'s comment updated to list it.

---

## §3 · What `live` means at each tier

`live` is `_buckets` ≥ a pack's `min_buckets` (`app/index.py:78–81`). Replacing `local` with custody changes
that sentence at exactly one tier.

**Home / Community node with its own kit — nothing changes.** Its sensors are `local`, `local` implies custody,
the count is the same count. Node #1's number does not move.

**Community or City node aggregating children.** `live` becomes: *at least one in-custody sensor reported in
the last 24 h*, where in-custody now includes the children's hourly means. A banjar node with no instrument of
its own, aggregating ten homes, would be able to say `live`.

**Should it?** Two readings, and they disagree:

- *For:* the number **was** measured, by instruments in this node's chain, by households who agreed to push
  them. `live` means measured, not measured-by-this-box. `ARCHITECTURE.md §7` refuses upgrading a state by
  aggregation — it does not refuse an aggregate being `live` when every input was. Ten homes' PM2.5 is a
  better Community number than one kit's, and requiring the banjar to buy a kit to describe air it already
  has ten honest measurements of is a tax on the tier that needs the least hardware.
- *Against:* `live` is a claim someone stands behind, and a node with no instrument has nothing to inspect
  when the number is wrong. It cannot service a sensor, check an enclosure, or answer "is that real?"

**Recommendation: a community node does NOT need to own a sensor, with one condition.** `live` at Community
and City requires **≥ 2 distinct in-custody sensors** reporting in 24 h, from **≥ 2 distinct children** where
the node has children. One child reporting is one household's kitchen, and a cell that says `live` off one
kitchen is the same lie as a model claiming `live`. Two is the smallest number that is a place rather than a
room. A home node with one kit is unaffected — it is describing one address and says so in its `unit` string.

Concretely: keep `min_buckets` as the hours test and add `min_sensors` (default 1, set to 2 by the core when
`NODE_SCALE` is not `community`, or whenever any `child` row exists). One extra `count(DISTINCT sensor_id)` in
`_buckets`. **This is the one question in this spec that is Tomas's call, not the code's.**

---

## §4 · The child push

### The metric name

Today `receive_aggregates` (`app/main.py:1625–1631`) writes:

```python
sid = f"{child}/{r['sensor_id']}"
INSERT INTO sensors (...) VALUES (%s,'child',%s,FALSE,'child',%s,'PT1H')
INSERT INTO readings (ts, sensor_id, metric, value) VALUES (%s,%s,%s,%s)   # metric = f"{r['metric']}_1h"
```

So a child's PM2.5 lands as metric `pm25_1h`. **No pack SQL anywhere matches `pm25_1h`** — every cell and rule
asks for `metric = 'pm25'`, `'temp'`, `'humidity'`. The cadence was encoded in the metric string, and the
metric string is the join key. That is the second half of gap 1: even after custody is fixed, a parent's
`Environmental|Community` cell would find nothing to average.

**Recommended: keep the metric name. Drop the `_1h` suffix.**

```python
# app/main.py:1631
VALUES (%s, %s, %s, %s)      # r["metric"], not f"{r['metric']}_1h"
```

The cadence already has a column and `receive_aggregates` already writes it: `sensors.cadence = 'PT1H'`, on
the child's own sensor row, one line above. A consumer that needs to know these are hourly means joins
`sensors` and reads `cadence` — the same place it reads `kind` and `local`. Nothing needs the suffix, and
nothing ever read it.

The bucket timestamp keeps the rest honest: `readings.ts` is the child's `r["bucket"]`, so an hourly mean
enters as one reading on the hour, and `readings_1h` (`init.sql:57`, `avg(value)` grouped by
`date_trunc('hour', ts)`) averages one row — the mean of one number is that number. The child's hour survives
unchanged. `readings`' `UNIQUE (sensor_id, metric, ts)` makes a re-push idempotent, as it already is.

**Pack SQL that changes for the metric name: none.** That is the point of keeping the name. Every cell and
rule that reads `metric='pm25'` keeps matching.

**But three cell SQLs still have to change, and they are not optional.** `packs/air-quality/cells.yml:11`
and `:21` read `s.local AND s.kind = 'sensor'`. That `kind` clause was written to keep models and portals out
of an air number, which custody now does on its own — and left as it is, it keeps `kind='child'` out too, so
the roll-up would still not reach the cell that gap 1 is about. Swapping `s.local AND s.kind = 'sensor'` for
the custody predicate is the whole edit; `packs/heat/cells.yml:13` takes the same swap without a `kind`
clause to drop. `packs/air-quality/cells.yml:32` (`NOT s.local`, the `Environmental|City` reference cell)
keeps `s.kind = 'sensor'` and does not change: it is asking about the ring, not about custody, and the ring is
sensors.

**Pack SQL that would have changed under the alternative** (teach each pack about `_1h`): both
`packs/air-quality/cells.yml` cells, `packs/heat/cells.yml`, `packs/insight/rules.yml` ×4,
`packs/air-quality/rules.yml` ×6, trust's three in `config/rules.yml` — and every pack anyone writes afterwards.
Rejected on that count alone.

One consequence to state plainly: after this, `readings` at a parent holds hourly means and raw readings under
the same metric name, told apart only by their sensor row's `kind` and `cadence`. That is correct — a mean of
hourly means weights each child's hour equally, which is what a district number should do — but a pack that
wants raw-only must say `s.kind = 'sensor'`, exactly as `init.sql:74`'s `stats` view already does. The `stats`
view therefore continues to exclude children, and the rules that read `stats` are unaffected. Only the cells,
which read `readings_1h` directly, see them.

### ρ does not roll up, and must

`push_aggregates()` (`app/main.py:448–460`) sends one thing:

```python
cur.execute("SELECT bucket, sensor_id, metric, mean, min, max, n FROM readings_1h WHERE bucket > now() - interval '2 hours'")
httpx.post(f"{PARENT()}/aggregates", json={"node": NODE, "rows": rows, "scale": ...})
```

Readings only. So a parent's `Governance|<scale>` cell — `rho()` at `app/index.py:96`, computed from its own
`alerts` and `actions` tables — counts only alerts the parent raised itself. A City node that raised no alerts
has no ρ, while ten children below it are measuring ρ every day. ρ is, in `ARCHITECTURE.md §5`'s words, "the
brick nobody else has", and it currently stops at the address.

**Specify: a second push, events.** `POST /events`, same `AGGREGATE_TOKEN`, same hourly loop.

One row per alert, with exactly these fields:

| field | from | why |
|---|---|---|
| `alert_id` | `alerts.id`, namespaced `<child>/<id>` on arrival | so `actions` can point at it |
| `rule` | `alerts.rule_id` | which rule, so a parent can weigh `act` rules only |
| `level` | `alerts.level` | ρ counts `level='act'` alerts only (`index.py:106`) |
| `kind` | the alert's domain tag | so a parent can say ρ for air separately from ρ for heat |
| `raised_at` | `alerts.ts` | detect |
| `responded_at` | `min(actions.ts) WHERE stage='acknowledged'` | decide |
| `acted_at` | `min(actions.ts) WHERE stage='acted'` | deploy |
| `measured_at` | `min(actions.ts) WHERE stage='measured'` | measure |
| ~~`cleared_at`~~ | ~~when the condition stopped holding~~ | **cut in v0.51.** Specified here, built in v0.50, and never written: a node has no notion of an alert clearing, only of cooldowns, so no child could send one. A column that is always NULL is a promise the schema cannot keep. It returns the day an alert learns it has stopped holding, together with the code that writes it. |

**And nothing else. No `text`, no `note`, no `actor`, no `sensor_id`.**

`alerts.text` is the household's own sentence — "shut the bedroom windows" describes a bedroom, which room it
is, and that somebody was home to be told. Per peer-visibility §7 it does not leave the address, and
`AGENTS.md`'s "raw readings stay on this machine" is the same refusal one level up. `actions.actor` is a
person's name. `sensor_id` would let a parent locate the room. The timestamps carry every fact ρ needs and
none of the facts a household would mind travelling; that is why the list is timestamps.

**The parent computes ρ. The child never sends a ratio.** A child sending `rho: 0.7` would be a number the
parent cannot check, cannot recompute when the definition of ρ changes, and cannot combine correctly (a mean
of ten ratios is not the ratio of the pooled counts). The parent runs `index.py::rho()` over the pooled events
with whatever definition is current on the parent — which is also how a change to the 24 h window or the `act`
filter reaches every historical child at once, with no re-push.

Storage at the parent: one `events` table mirroring these columns, keyed `(child, alert_id)`, upserted.
`rho()`'s query changes from `FROM alerts … LEFT JOIN actions` to a union of the parent's own two tables and
`events`. That is the one function to edit.

---

## §5 · Many communities per city

Ubud, Denpasar and Canggu each run a community node. All three emit `Environmental|Community` under
`city: bali`. The spine holds **one row per `(city, cell)`** — `cells-ingest/README.md` step 5, "One row per
(city, cell), forever" — so the three overwrite each other, last write wins, and the Index shows whichever
node published most recently with no indication that two others exist.

**Recommended shape, from the ingestion map: the city node publishes the aggregated `*|Community` beside its
own `*|City`.**

The three community nodes push to the Denpasar city node, which is already the only `FCI_PUBLISHER=1` node in
Bali (`ingest.py:17`, `AGENTS.md:12`). It computes `Environmental|Community` over its in-custody sensors —
which, after §2 and §4, are the three communities' hourly means — and publishes that one row alongside
`Environmental|City` computed from Bali Satu Data and the reference stations.

What this preserves, and the reason to prefer it:

- **The Index keeps 20 cells.** `ingest.py:61` builds `VALID_CELLS` as the 4 × 5 product and drops anything
  else; `cells-worker` serves that shape. `README.md` records four rows already in the spine with invented
  scales (`Environmental|Beach`, `|Harbor`, `|Industrial`, `|Residential`) that are invisible to every
  surface. Nothing here adds a twenty-first.
- **`ALLOWED_CITIES` stays four strings** — `["barcelona", "boston", "santiago", "bali"]` (`ingest.py:56`),
  hardcoded on both sides. No `bali-ubud`.
- **One node per pilot writes** (`AGENTS.md:12`, the tier contract in `skills/publish-to-index/SKILL.md`).
  Three community nodes publishing into one city is that rule broken, whatever the mechanism.
- **Ubud does not vanish.** It keeps its own cells on its own dashboard and its own `GET /cells`, which is the
  architecture's position on every home node already. Denpasar's `notes` field carries "aggregated over 3
  community nodes, 14 sensors" — the sentence that tells a reader the number is a district, not a bedroom.

**The alternative, and why it is rejected.** Give each community node its own city key — `bali-ubud`,
`bali-denpasar`, `bali-canggu` — so each gets its own row. Rejected because it breaks three things at once:
`ALLOWED_CITIES` and `cells-worker`'s hardcoded list both grow without bound (a 404 on the read side for any
key added to only one of them); "one node per pilot writes" becomes unenforceable, since a pilot is no longer
a city; and the FCI methodology's Community **scale** would be re-encoded as a city **name**, so
`index.fab.city` would show four Balis and no Bali. The Community scale already exists as an axis; a second
encoding of it in the city column is the `Environmental|Beach` mistake with a different spelling.

---

## §6 · The publisher moves into this repo

Today `cells-ingest` lives in the private `fci-index` repo. `skills/publish-to-index/SKILL.md` therefore has
to end with "write to info@fab.city" and cannot show the command, and `BALI.md` — a real runbook — is
readable by nobody outside it.

**Specify: a `publish` subcommand of the node CLI, in this repo, refusing exactly what `ingest.py`
refuses today.** (Written here as a subcommand name rather than as a command line, because it is not one yet
and `tools/check_docs.py` is right to refuse a doc that pretends otherwise.)

- `FCI_PUBLISHER != 1` → refuse (`ingest.py:141`), with the same message: a home node feeds its parent.
- No `FCI_AIRTABLE_TOKEN` → refuse (`ingest.py:148`).
- `FCI_CITY` not in `ALLOWED_CITIES` → refuse (`ingest.py:138`).
- `--dry-run` works without either, prints the diff, writes nothing.
- The five steps unchanged, each of which can only lose rows: fetch, normalise against the 20 keys, collapse
  to newest per key, diff against the city's existing rows, PATCH-or-POST.

**Public: the code.** `ingest.py` is 200 lines of `urllib` over a documented eight-field row shape. Nothing in
it is a secret; the base id `appmNQaDGEFE9VcYh` is already in the file and is useless without a token. Making
it public means the `publish-to-index` skill can show a real command, a pilot can dry-run before asking for anything,
and the refusals become reviewable by the people they refuse.

**Private: the token issuance.** Per-pilot Airtable PATs, scoped to one base, issued by hand by Tomas to a
named operator. No self-serve, no automation, no path from this repository to a token. That is the whole
access-control model and it does not move. `SKILL.md`'s last mile stays "write to info@fab.city" — what
changes is that everything before the last mile is now runnable.

Also public, and worth more than the script: BALI.md becomes docs/PUBLISHING.md, the runbook the second
pilot copies.

**Trigger (the file itself already names it — `SKILL.md`: "When three pilots are publishing, the ingest script
may move into `tools/`… Not yet"):** after Bali has published once from the Denpasar portal, and before
Vivanco's node reaches City tier. One pilot proves the path; the second must not need a private repo to walk
it. Not before Bali publishes — a tool that has never written a row is not a tool, it is a proposal.

---

## §7 · Invariants this adds to `AGENTS.md`

To be appended to "Invariants. Do not break these." as sentences:

- **Peers never roll up.** A `kind='peer'` row is display-only: it reaches no Index cell, no `_buckets` count,
  and no aggregate pushed to a parent, whatever its coordinates say.
- **Peers never drive an alert or a report line.** A node may show a neighbour's number and must never act on
  it. The ring in `packs/nearby` compares against peers; it does not alert about them.
- **State is never upgraded by aggregation.** A parent's cell is `partial` if any input was. `live` requires
  in-custody measurement in the last 24 h, at the parent's own tier. (This one exists at
  `ARCHITECTURE.md §7`; it belongs in `AGENTS.md` too, because it is the rule an agent is most likely to
  "fix".)
- **Exact place never leaves; a coarse cell may, and says how coarse.** Coordinates, room names, sensor ids
  and a household's own sentences stay on the machine that recorded them. Aggregates carry values and
  timestamps; the events push carries timestamps. Neither carries where. The one thing that does leave is the
  Reticulum announce, and it leaves as an H3 cell rounded UP to a coarse parent — default res 3, about 60 km,
  an island and not an address — with `res` travelling beside it so the far end can say how blunt it is, and a
  floor of res 6 that no settings box can go under (`main.py:735`, `PRESENCE_RES_FLOOR`). That floor is the
  invariant. "No geometry at any rung" would be a nicer sentence and it would be false.
- **Exactly one node per pilot writes to the spine.** A pilot is a city in `ALLOWED_CITIES`. Every other node
  computes its cells, shows them, and passes them no further.

---

## §8 · The migration, as a sketch

**Not run. Not written as a file. This is what it would have to do.**

If §2's recommendation is taken, there is almost nothing to migrate — that is the argument for it.

**Order.**

1. `init.sql` gains `peer` in the `kind` comment and, if (a) is chosen, the generated `custody` column. Both
   additive and idempotent, applied to a live database by `update.sh` the way every `ALTER … IF NOT EXISTS`
   in that file already is.
2. **No `UPDATE` of existing rows.** Every row is already correct: own kits and pods are `local=TRUE`,
   children are `kind='child'`, `/nearby` and models and portals are `local=FALSE`. The generated column
   computes itself on apply. The only rows whose classification changes are `child` rows, and they change
   from *wrongly excluded* to *included*, which is the fix.
3. `_buckets` and three cell SQLs read custody: `packs/air-quality/cells.yml:11` and `:21` (dropping their
   now-redundant `s.kind = 'sensor'`, which would otherwise keep children out) and `packs/heat/cells.yml:13`.
   Two pack files. `packs/air-quality/cells.yml:32`, `packs/nearby/rules.yml` and every rule that reads the
   `stats` view are untouched — they ask about the ring and want `local` in its own meaning.
4. `receive_aggregates` drops the `_1h` suffix (§4). Children that pushed before the change leave
   `<metric>_1h` rows behind; they are inert (no SQL matches them) and expire out of every window on their
   own. Delete them or don't.
5. `POST /events` and the parent-side `events` table (§4) — new, nothing to migrate.

**The query that proves nothing reached a cell that should not have.** Run on a node after the apply; it must
return zero rows.

```sql
-- Every sensor now in custody that was not in custody before, and why.
-- Expect: only kind='child' rows. Anything else is a row this change silently promoted.
SELECT s.sensor_id, s.source, s.kind, s.local, s.scale,
       count(r.*) AS readings_24h, max(r.ts) AS last_seen
FROM sensors s LEFT JOIN readings r
  ON r.sensor_id = s.sensor_id AND r.ts > now() - interval '24 hours'
WHERE s.custody                 -- the new rule, as the generated column computes it
  AND NOT s.local               -- the old one
  AND s.kind <> 'child'         -- the intended change
GROUP BY 1,2,3,4,5;
```

And its mirror, which must also return zero — nothing that was in custody fell out:

```sql
SELECT sensor_id, source, kind, local FROM sensors
WHERE local AND NOT custody;
```

**What an older node needs.** `update.sh` applies `init.sql` to the live database on every update, so the
schema arrives on its own; any database from v0.4.3 onward already has `kind`, `scale` and `cadence`. Nothing
to do by hand.

**What node #1 actually did** — checked on the node, 13 September 2026, after it updated to `v0.51-1-gb8ec752`
(schema 0.51):

| | |
|---|---|
| own kits | 6, `local=TRUE`, `custody=TRUE` |
| ring stations (Bali Air Dispatch) | 14, `local=FALSE`, `custody=FALSE` |
| model points | 5, `custody=FALSE` |
| `place-point` (`kind='map'`) | 1, `custody=FALSE` |
| children, peers | none |
| hourly buckets in 24h, **by custody vs by local** | **1080 vs 1080** |

A genuine no-op, which is what it should be for a node with no children. Earlier drafts of this section said
node #1 was on v0.30 and had five kits: the first came from the brief and was never checked, the second from
`tests/data/node1-sensors.tsv`, a dump taken on 7 September. Neither was a reading from the node. The DuckDB
replay and the `pai-clean` rehearsal prove the change; only the node proves the node.

---

## §9 · The gate

`tests/test_custody.py` exists in this branch and **fails on `main` today**. It is written against the current
tree, not against the proposal, so it is the thing that says whether the proposal landed.

It builds two DuckDB nodes from `init.sql` and node #1's real sensors and readings
(`tests/data/node1-*.tsv`, the same fixtures `tests/trustdb.py` uses): one without a peer, one with a single
extra row —

```
peer-1 · source 'baliairdispatch' · kind='peer' · local=TRUE · indoor=TRUE · 40 m from the node
        · pm25, temp and humidity readings through the last three hours
```

— a peer across the street, geographically local, reporting right now. Then it asserts:

1. `_buckets`'s SQL, verbatim from `app/index.py:55`, returns the **same count** on both. **Fails today:**
   192 → 204.
2. Every `packs/*/cells.yml` SQL returns the **same value** on both, within floating-point tolerance.
   **Fails today:** `packs/heat/cells.yml`'s `Social|Community` goes 0.0 → 4.0.
3. Node #1's own five kits still count — the fix must not be "exclude everything".

Assertion 2 compares the two databases rather than naming packs, so a pack added next year that reads a peer
breaks it without anyone remembering this spec. Floating-point tolerance is not decoration:
`packs/air-quality/cells.yml`'s first cell changes in the 15th decimal purely from summation order, and an
exact comparison would report a leak that is not there.

**The file is not in `tests/all` yet, and must not be added until the implementation lands.** The runner
(`tests/all:126`) asserts it runs exactly 31 suites and fails the whole run on any skip not in
`EXPECTED_SKIPS`. So CI is green today because the suite is not in the list, not because the suite is lying.
The `CI=1` self-skip in the file is belt and braces for anyone who wires it early.

**What the implementation session does, in order:**

```
1. bash tests/test_custody.py          # watch it fail — 2 assertions, the numbers above
2. implement §2 and §4
3. bash tests/test_custody.py          # now passes
4. delete the CI=1 guard at the top of the file
5. add `test_custody|PYTHONPATH=app python3 tests/test_custody.py` to tests/all's SUITES
6. change tests/all's `-ne 31` to `-ne 32`, and the comment above it
```

Step 6 is the one people forget; the runner fails loudly if they do, which is why it is written that way.
