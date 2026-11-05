-- The whole schema, in one idempotent file.
-- Postgres runs this automatically only when the data volume is first created. `./update.sh` applies the SAME file
-- to an existing database on every update — that is why every statement here must be safe to run twice.
-- Rules: CREATE TABLE IF NOT EXISTS · ALTER TABLE ADD COLUMN IF NOT EXISTS · DROP VIEW then CREATE (column
-- lists change between versions, and CREATE OR REPLACE VIEW cannot reorder columns).

CREATE TABLE IF NOT EXISTS sensors (
  sensor_id TEXT PRIMARY KEY,           -- 'sc-19880' | 'bad-pa-46949' | 'ag-<serial>' ...
  source    TEXT NOT NULL,              -- 'smartcitizen' | 'baliairdispatch' | 'airgradient' ...
  name      TEXT,
  lat       DOUBLE PRECISION,
  lon       DOUBLE PRECISION,
  indoor    BOOLEAN NOT NULL DEFAULT FALSE,
  local     BOOLEAN NOT NULL DEFAULT FALSE,   -- TRUE = this node's own instrument, here. Set by the adapter, narrowed by LOCAL_RADIUS_M.
  kind      TEXT NOT NULL DEFAULT 'sensor',   -- sensor | portal | model | survey | child | peer | facility  (how the number was produced,
                                        -- or, for 'facility', that there is no number: a place with a name and a point. packs/make)
  scale     TEXT NOT NULL DEFAULT 'community',-- community | city | region | bioregion | planet  (what the number describes)
  cadence   TEXT,                             -- 'PT5M' | 'P1D' | 'P1Y' — how often it can meaningfully change
  meta      JSONB
);
-- additive for nodes created before v0.3
ALTER TABLE sensors ADD COLUMN IF NOT EXISTS kind    TEXT NOT NULL DEFAULT 'sensor';
ALTER TABLE sensors ADD COLUMN IF NOT EXISTS scale   TEXT NOT NULL DEFAULT 'community';
ALTER TABLE sensors ADD COLUMN IF NOT EXISTS cadence TEXT;

-- CUSTODY: may this row's numbers roll up and make an Index cell say `live`? (docs/SPEC_custody.md)
--
-- Not the same question as `local`, which is geography-and-ownership: a child node's hourly means are in
-- this node's chain and four hundred metres down the lane, and a stranger's sensor may be across the street
-- and in nobody's chain but their own. `local` was written on 2 September 2026 for a node that was a house.
-- `kind` and the child push arrived the next day and nothing reconciled them. That is how a community node
-- aggregating ten homes counted zero local buckets and could never say `live`.
--
-- Generated, not written: no adapter sets it, nothing can make it disagree with `local` and `kind`, and it
-- costs one word in a WHERE clause instead of the same two-clause predicate repeated in fifteen statements.
ALTER TABLE sensors ADD COLUMN IF NOT EXISTS custody BOOLEAN
  GENERATED ALWAYS AS (kind = 'child' OR (local AND kind <> 'peer')) STORED;

CREATE TABLE IF NOT EXISTS readings (
  ts        TIMESTAMPTZ NOT NULL,
  sensor_id TEXT NOT NULL REFERENCES sensors(sensor_id),
  metric    TEXT NOT NULL,              -- pm25 | pm25_raw | pm10 | pm1 | temp | humidity | pressure | aqi ...
  value     DOUBLE PRECISION NOT NULL,
  UNIQUE (sensor_id, metric, ts)        -- polling twice never duplicates
);
CREATE INDEX IF NOT EXISTS readings_lookup ON readings (sensor_id, metric, ts DESC);

CREATE TABLE IF NOT EXISTS alerts (
  id        BIGSERIAL PRIMARY KEY,
  ts        TIMESTAMPTZ NOT NULL DEFAULT now(),
  rule_id   TEXT NOT NULL,
  sensor_id TEXT,
  level     TEXT,
  text      TEXT
);
ALTER TABLE alerts ADD COLUMN IF NOT EXISTS id BIGSERIAL;
-- the buttons a rule offered with this alert (app/buttons.py normalizes them before they are stored)
ALTER TABLE alerts ADD COLUMN IF NOT EXISTS buttons JSONB;
CREATE INDEX IF NOT EXISTS alerts_cooldown ON alerts (rule_id, sensor_id, ts DESC);

-- The ρ instrument. A human (or an app on their behalf) records what happened after an alert.
-- stage: acknowledged (someone saw it) · acted (someone did the thing) · measured (the outcome was checked)
CREATE TABLE IF NOT EXISTS actions (
  ts        TIMESTAMPTZ NOT NULL DEFAULT now(),
  alert_id  BIGINT REFERENCES alerts(id),
  stage     TEXT NOT NULL CHECK (stage IN ('acknowledged','acted','measured')),
  actor     TEXT,
  note      TEXT
);
-- which of the alert's buttons was pressed; the note stays what the person said
ALTER TABLE actions ADD COLUMN IF NOT EXISTS choice TEXT;

-- Hourly means. Finished hours are kept in readings_1h_done; the view reads them and groups only the readings from
-- the table's last hour onward, live. Until 22 Oct 2026 the view grouped every reading ever stored on every read:
-- 434 ms for the last two hours on node #1, 2.7 s for ninety days. app/main.py::refresh_hourly fills the table: the
-- last 26 hours every hour (late child pushes, a radio that caught up), the whole of it on start and once a day
-- (a backfill, a deletion). The live half starts where the table ends, so an empty or stale table makes the view
-- slower, never shorter. Buckets are cut in the session's time zone, NODE_TZ, as the view always cut them.
CREATE TABLE IF NOT EXISTS readings_1h_done (
  bucket    TIMESTAMPTZ NOT NULL,
  sensor_id TEXT NOT NULL,
  metric    TEXT NOT NULL,
  mean      DOUBLE PRECISION,
  min       DOUBLE PRECISION,
  max       DOUBLE PRECISION,
  n         BIGINT,
  PRIMARY KEY (sensor_id, metric, bucket)
);
CREATE INDEX IF NOT EXISTS readings_1h_done_bucket ON readings_1h_done (bucket);
CREATE INDEX IF NOT EXISTS readings_ts ON readings (ts);    -- the live half reads only the last hour or two
DROP VIEW IF EXISTS readings_1h CASCADE;
CREATE VIEW readings_1h AS
SELECT d.bucket, d.sensor_id, d.metric, d.mean, d.min, d.max, d.n FROM readings_1h_done d
UNION ALL
SELECT date_trunc('hour', r.ts) AS bucket, r.sensor_id, r.metric,
       avg(r.value) AS mean, min(r.value) AS min, max(r.value) AS max, count(*) AS n
FROM readings r
WHERE r.ts >= (SELECT COALESCE(max(bucket) + INTERVAL '1 hour', '-infinity'::timestamptz) FROM readings_1h_done)
GROUP BY 1, 2, 3;

-- Rolling stats per sensor/metric, used by rules. One row per (sensor, metric). Aggregated on (sensor_id, metric) alone
-- and joined to the sensor after: grouping on all nine columns sorted every reading of the day by them, 320 ms on
-- node #1 (24 Oct 2026), 133 ms this way, the same rows. Rolling stats are for sensors only: slow sources (portals,
-- models) live in the `observations` view.
DROP VIEW IF EXISTS stats CASCADE;
CREATE VIEW stats AS
SELECT a.sensor_id, a.metric, s.indoor, s.local, s.kind, s.scale, s.lat, s.lon, s.name,
       a.last, a.last_ts, extract(epoch FROM now() - a.last_ts) / 60 AS silent_minutes,
       a.mean_15m, a.mean_1h, a.mean_24h
FROM (SELECT r.sensor_id, r.metric,
             (array_agg(r.value ORDER BY r.ts DESC))[1]                       AS last,
             max(r.ts)                                                          AS last_ts,
             avg(r.value) FILTER (WHERE r.ts > now() - interval '15 minutes')   AS mean_15m,
             avg(r.value) FILTER (WHERE r.ts > now() - interval '1 hour')       AS mean_1h,
             avg(r.value) FILTER (WHERE r.ts > now() - interval '24 hours')     AS mean_24h
      FROM readings r
      WHERE r.ts > now() - interval '24 hours'
        AND r.sensor_id IN (SELECT sensor_id FROM sensors WHERE kind = 'sensor')
      GROUP BY r.sensor_id, r.metric) a
JOIN sensors s ON s.sensor_id = a.sensor_id;

-- Slow-moving numbers (a city statistic, a satellite point sample, a survey) don't belong in a 24h rolling view.
-- One row per source per metric per period, latest wins. Found by walking readings_lookup, (sensor_id, metric,
-- ts DESC): each metric of each non-sensor, then its newest row. DISTINCT ON sorted every row those sources ever
-- wrote, 66,067 for 93 on node #1 (24 Oct 2026, 221 ms); this reads about one index entry per answer (6 ms).
DROP VIEW IF EXISTS observations CASCADE;
CREATE VIEW observations AS
WITH RECURSIVE m AS (
  SELECT s.sensor_id, (SELECT min(r.metric) FROM readings r WHERE r.sensor_id = s.sensor_id) AS metric
  FROM sensors s WHERE s.kind <> 'sensor'
  UNION ALL
  SELECT m.sensor_id, (SELECT min(r.metric) FROM readings r WHERE r.sensor_id = m.sensor_id AND r.metric > m.metric)
  FROM m WHERE m.metric IS NOT NULL
)
SELECT m.sensor_id, m.metric, l.value, l.ts, s.name, s.kind, s.scale, s.local, s.cadence, s.meta
FROM m JOIN sensors s ON s.sensor_id = m.sensor_id
CROSS JOIN LATERAL (SELECT r.value, r.ts FROM readings r WHERE r.sensor_id = m.sensor_id AND r.metric = m.metric
                      AND r.ts <= now()          -- a forecast hour is not an observation yet
                    ORDER BY r.ts DESC LIMIT 1) l
WHERE m.metric IS NOT NULL;

-- Where this node's schema is. Read by update.sh and reported at /health.
CREATE TABLE IF NOT EXISTS schema_version (version TEXT PRIMARY KEY, applied_at TIMESTAMPTZ NOT NULL DEFAULT now());
INSERT INTO schema_version (version) VALUES ('0.4') ON CONFLICT DO NOTHING;
INSERT INTO schema_version (version) VALUES ('0.14') ON CONFLICT DO NOTHING;

-- What a metric IS, as declared by whoever produces it. Integrity checks are written against roles, not against
-- metric names: `temp` from a kit is ambient, `temp` from a gateway's BME680 inside its own box is not, and
-- `bme_iaq` is a vendor index that must never be pooled. Keyed on the source because the role belongs to the
-- instrument, not to the word. Written at startup from config/channels.yml and every pack's channels.yml.
-- The key is per source and metric, not per device: every sensor from one adapter shares its role, so a node
-- whose hardware differs from that adapter's usual shape (e.g. a Meshtastic pod wired to an external probe)
-- cannot declare its own.
CREATE TABLE IF NOT EXISTS channel_roles (
  source      TEXT NOT NULL,
  metric      TEXT NOT NULL,
  role        TEXT NOT NULL CHECK (role IN ('ambient','enclosure','device_health','derived','index','private')),
  comparable  BOOLEAN NOT NULL DEFAULT FALSE,   -- may be compared between sensors at the same place
  unit        TEXT,
  reference   TEXT,                             -- instrument family, so peer comparison groups like with like
  declared_by TEXT NOT NULL,
  PRIMARY KEY (source, metric)
);
INSERT INTO schema_version (version) VALUES ('0.22') ON CONFLICT DO NOTHING;

-- Settings the GUI can change while the node runs. Overlays .env: a key here wins over the environment.
-- Bootstrap-only keys (ports, database, compose profiles) stay in .env; the app lists which is which.
CREATE TABLE IF NOT EXISTS settings (
  key        TEXT PRIMARY KEY,
  value      TEXT NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 'settings' rows record who changed what (actor = an agent's name or "gui"); alert_id is NULL for them and
-- rho ignores them. Idempotent: drop and re-add the check.
-- `decided` is the fifth, and it MOVES NOTHING. rho filters stage IN ('acknowledged','acted'),
-- index.py::_funnel selects the three it names, and CLOSED_STAGES in app/issues/schema.py is
-- ("acted","measured") -- so a decision does not close an ask, does not enter rho, and is not a
-- stage in the funnel. It is a record that somebody looked at an observation and said what they
-- would do, which today leaves exactly the same trace as never having looked: none. See
-- docs/SPEC_decide.md section 6.
-- `dismissed` is the sixth: "Doesn't fit" (docs/SPEC_alerts.md §7). Like `decided`, it moves nothing in rho's
-- alert-level funnel. It is widened HERE, in the one drop-and-add, and not by a second pair further down: this pair
-- runs on every apply, so a later pair would have it re-add the five-stage check over rows that already say
-- `dismissed`, and under ON_ERROR_STOP update.sh would stop with the constraint dropped.
ALTER TABLE actions DROP CONSTRAINT IF EXISTS actions_stage_check;
ALTER TABLE actions ADD CONSTRAINT actions_stage_check CHECK (stage IN ('acknowledged','acted','measured','settings','decided','dismissed'));
INSERT INTO schema_version (version) VALUES ('0.20') ON CONFLICT DO NOTHING;

-- Pack SQL (rules.yml, cells.yml) runs as planetai_ro: SELECT on every table except settings, no writes. A "data pack,
-- safe to merge" could otherwise SELECT a token out of settings into an alert text, and /alerts answers anyone on the
-- LAN. The app switches role for the one statement (SET LOCAL ROLE inside a transaction) and is itself again for the
-- INSERT that records the alert. Tables a pack creates later (place_*) inherit SELECT through the default privileges.
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'planetai_ro') THEN CREATE ROLE planetai_ro NOLOGIN; END IF;
END $$;
GRANT planetai_ro TO CURRENT_USER;
GRANT USAGE ON SCHEMA public TO planetai_ro;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO planetai_ro;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO planetai_ro;
REVOKE ALL ON settings FROM planetai_ro;
INSERT INTO schema_version (version) VALUES ('0.21') ON CONFLICT DO NOTHING;

-- Every report the node wrote, sent or held. One row per due hour, and the row IS the lock: `run_report` asks this
-- table whether the hour already has a report, so a container that restarts inside a due window does not send a
-- second one. (The old briefings asked `alerts`, which is also where every rule writes, and where a report the
-- household never saw still counted as sent.)
--   sheet            the node's own text. Always written, whatever else happens.
--   text             what was actually sent. Equal to `sheet` until a model rewrites it (v0.38).
--   sent             false when quiet hours held it: written, on the dashboard, folded into the next one.
--   fallback_reason  why `text` is the sheet and not the model's: a number it invented, a timeout, no agent.
CREATE TABLE IF NOT EXISTS reports (
  id              BIGSERIAL PRIMARY KEY,
  ts              TIMESTAMPTZ NOT NULL DEFAULT now(),
  due_local       TIMESTAMPTZ,           -- the local hour this report answers, so the lock is per hour, not per run
  window_hours    INT,                   -- how many hours it covers: REPORT_EVERY, or more when it folds a held one
  depth           TEXT,                  -- sheet | brief | standard | deep
  rung            TEXT,                  -- node | local | remote | online
  text            TEXT,
  sheet           TEXT,
  sent            BOOLEAN,
  held_quiet      BOOLEAN,
  fallback_reason TEXT
);
CREATE INDEX IF NOT EXISTS reports_due ON reports (due_local DESC);
INSERT INTO schema_version (version) VALUES ('0.22') ON CONFLICT DO NOTHING;

-- A cell's value is in the report only to say whether it moved, so the row that carried it has to keep it: nothing
-- else on the node stores what `Environmental|Community` was six hours ago. Additive, like every column added after
-- its table shipped.
ALTER TABLE reports ADD COLUMN IF NOT EXISTS cells JSONB;
INSERT INTO schema_version (version) VALUES ('0.23') ON CONFLICT DO NOTHING;

-- ρ from below. A child pushes one row per alert it raised. The parent computes ρ over its own alerts and
-- these together, so a City node measures the district's action latency and not only its own.
-- (docs/SPEC_custody.md §4)
--
-- WHAT IS NOT HERE IS THE POINT. No `text`, no `note`, no `actor`, no `sensor_id`. "Shut the bedroom windows"
-- names a room, says the household was home to be told, and describes a house. It does not leave the address.
-- Timestamps carry everything ρ needs and none of the facts a household would mind travelling.
--
-- The child never sends a ratio. A mean of ten ratios is not the ratio of the pooled counts, the parent could
-- not check it, and a change to the definition of ρ would have to be re-pushed by every child instead of
-- recomputed once here.
CREATE TABLE IF NOT EXISTS events (
  child         TEXT NOT NULL,           -- the pushing node's NODE name, as receive_aggregates uses it
  alert_id      TEXT NOT NULL,           -- the child's own alerts.id, unique only within that child
  rule          TEXT,                    -- alerts.rule_id — so a parent can weigh one rule, or ignore one
  level         TEXT,                    -- ρ counts level='act' only, same as the parent's own alerts
  kind          TEXT,                    -- the alert's domain tag: ρ for air apart from ρ for heat
  scale         TEXT,                    -- what the child said it was, so a parent can refuse a wrong rung
  raised_at     TIMESTAMPTZ NOT NULL,    -- detect
  responded_at  TIMESTAMPTZ,             -- decide   (first 'acknowledged')
  acted_at      TIMESTAMPTZ,             -- deploy   (first 'acted')
  measured_at   TIMESTAMPTZ,             -- measure  (first 'measured')
  received_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (child, alert_id)          -- re-pushing the same alert updates it, so a child may push an open alert for days
);
CREATE INDEX IF NOT EXISTS events_window ON events (raised_at DESC);
INSERT INTO schema_version (version) VALUES ('0.50') ON CONFLICT DO NOTHING;

-- v0.50 shipped this table with a `cleared_at` column and nothing to put in it. A node has no notion of an
-- alert clearing, only of cooldowns, so no child could ever have sent one and push_events never did. A column
-- that is always NULL is a promise the schema cannot keep. Dropped rather than left as scaffolding.
-- It comes back the day an alert learns it has stopped holding, and on that day it arrives with a writer.
ALTER TABLE events DROP COLUMN IF EXISTS cleared_at;
INSERT INTO schema_version (version) VALUES ('0.51') ON CONFLICT DO NOTHING;

-- The releases this node has told its household about, one row each, so a restart or an hourly re-check never
-- sends the same "a new version is out" twice. Written by check_release() in app/main.py. Rows `pack:<id>` are the
-- wild-list packs it has told them about (check_wild), and GET /packs/all reads those to mark a pack new.
CREATE TABLE IF NOT EXISTS release_notices (
  version  TEXT PRIMARY KEY,
  told_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
INSERT INTO schema_version (version) VALUES ('0.52') ON CONFLICT DO NOTHING;

-- The measures a kinded rule reads (docs/SPEC_alerts.md §3). A rule asks "for how long" and "against what usual"
-- here instead of rebuilding either from raw readings every minute.
--
-- recent_15m: quarter-hour means over the last 24 h, sensors only, with `apparent` (Steadman's no-wind indoor
-- form, the same arithmetic as packs/heat/rules.yml) derived wherever temp and humidity share a bucket.
DROP VIEW IF EXISTS recent_15m CASCADE;
CREATE VIEW recent_15m AS
WITH b AS (
  SELECT date_trunc('hour', r.ts) + CAST(floor(extract(minute FROM r.ts) / 15) AS INTEGER) * INTERVAL '15 minutes' AS bucket,
         r.sensor_id, r.metric, avg(r.value) AS mean
  FROM readings r JOIN sensors s ON s.sensor_id = r.sensor_id
  WHERE r.ts > now() - INTERVAL '24 hours' AND r.ts <= now() AND s.kind = 'sensor'
  GROUP BY 1, 2, 3)
SELECT bucket, sensor_id, metric, mean FROM b
UNION ALL
-- temp and humidity side by side in one grouping, not b joined to itself: Postgres guessed one sensor row where node #1
-- has 31, chose a nested loop, and compared 2.57 million pairs for 1,604 rows, 590 of the view's 645 ms, about nine
-- times a minute (21 Oct 2026). The same rows in 57 ms.
SELECT bucket, sensor_id, 'apparent', t + 0.33 * (h / 100.0 * 6.105 * exp(17.27 * t / (237.7 + t))) - 4.0
FROM (SELECT bucket, sensor_id, max(mean) FILTER (WHERE metric = 'temp') AS t,
             max(mean) FILTER (WHERE metric = 'humidity') AS h
      FROM b WHERE metric IN ('temp', 'humidity') GROUP BY 1, 2) p
WHERE t IS NOT NULL AND h IS NOT NULL;

-- usual_by_hour: this room's own normal for each local hour, from the fourteen complete local days before today
-- (date_trunc in the session's NODE_TZ). Today is left out on purpose: a long hot run must not raise the bar it is
-- measured against. Materialized,
-- because a percentile over two weeks is too much to recompute every minute; the app refreshes it hourly and at
-- start (app/main.py refresh_usual). Created empty: init.sql runs under psql in UTC, and a refresh from the app runs
-- in NODE_TZ, so only the app's refresh buckets hours the way the household lives them. A rule that reads it
-- before the first refresh fails and is logged, and runs again a minute later.
DROP MATERIALIZED VIEW IF EXISTS usual_by_hour;
CREATE MATERIALIZED VIEW usual_by_hour AS
WITH h AS (
  SELECT date_trunc('hour', r.ts) AS bucket, r.sensor_id, r.metric, avg(r.value) AS mean
  FROM readings r JOIN sensors s ON s.sensor_id = r.sensor_id
  WHERE r.ts >= date_trunc('day', now()) - INTERVAL '14 days' AND r.ts < date_trunc('day', now())
    AND s.kind = 'sensor' AND r.metric IN ('temp', 'humidity', 'pm25')
  GROUP BY 1, 2, 3),
a AS (
  SELECT bucket, sensor_id, metric, mean FROM h
  UNION ALL
  SELECT t.bucket, t.sensor_id, 'apparent',
         t.mean + 0.33 * (u.mean / 100.0 * 6.105 * exp(17.27 * t.mean / (237.7 + t.mean))) - 4.0
  FROM h t JOIN h u ON u.sensor_id = t.sensor_id AND u.bucket = t.bucket AND u.metric = 'humidity'
  WHERE t.metric = 'temp')
SELECT sensor_id, metric, CAST(extract(hour FROM bucket) AS INTEGER) AS hour,
       percentile_cont(0.5)  WITHIN GROUP (ORDER BY mean) AS median,
       percentile_cont(0.75) WITHIN GROUP (ORDER BY mean) AS p75,
       percentile_cont(0.9)  WITHIN GROUP (ORDER BY mean) AS p90,
       count(*) AS n
FROM a GROUP BY 1, 2, 3
WITH NO DATA;
GRANT SELECT ON recent_15m, usual_by_hour TO planetai_ro;

-- Alert events (docs/SPEC_alerts.md §4): one row per story, one issue at one house, from open to clear. Every alert
-- row still exists; the ones that fed an event point at it. event_messages is every message the engine decided,
-- sent or held, with the reason: in ALERT_ENGINE=shadow nothing is sent and this table is the comparison.
-- Named alert_events, not events: `events` is already the parent's ledger of what its children pushed (v0.50), and
-- CREATE TABLE IF NOT EXISTS would have skipped this one silently. The told_* columns and last_emitted_at are the
-- engine's escalation bookkeeping (what the last message said, sent or held); without them a restart forgets it.
CREATE TABLE IF NOT EXISTS alert_events (
  id              BIGSERIAL PRIMARY KEY,
  issue           TEXT NOT NULL,
  kind            TEXT NOT NULL,
  level           TEXT NOT NULL,
  opened_at       TIMESTAMPTZ NOT NULL,
  last_seen_at    TIMESTAMPTZ NOT NULL,
  last_sent_at    TIMESTAMPTZ,
  cleared_at      TIMESTAMPTZ,
  peak            DOUBLE PRECISION,
  rooms           TEXT[] NOT NULL DEFAULT '{}',
  places          TEXT[] NOT NULL DEFAULT '{}',
  ever_sent       BOOLEAN NOT NULL DEFAULT FALSE,
  action_id       TEXT,
  told_kind       TEXT,
  told_peak       DOUBLE PRECISION,
  told_level      TEXT,
  told_held       TEXT,
  last_emitted_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS alert_events_open ON alert_events (issue) WHERE cleared_at IS NULL;
CREATE TABLE IF NOT EXISTS event_messages (
  id        BIGSERIAL PRIMARY KEY,
  ts        TIMESTAMPTZ NOT NULL DEFAULT now(),
  event_id  BIGINT NOT NULL REFERENCES alert_events(id),
  reason    TEXT NOT NULL CHECK (reason IN ('open','escalate','clear')),
  kind      TEXT,           -- the event's kind when this was decided: danger is never counted against the daily ceiling
  sent      BOOLEAN NOT NULL,
  held      TEXT,
  mode      TEXT NOT NULL,
  text      TEXT,
  action_id TEXT            -- the action this message carried (SPEC_alerts §5), NULL for an all-clear or none chosen
);
ALTER TABLE event_messages ADD COLUMN IF NOT EXISTS action_id TEXT;
ALTER TABLE alerts  ADD COLUMN IF NOT EXISTS event_id BIGINT REFERENCES alert_events(id);
ALTER TABLE actions ADD COLUMN IF NOT EXISTS event_id BIGINT REFERENCES alert_events(id);
GRANT SELECT ON alert_events, event_messages TO planetai_ro;

-- A capture is one picture with the facts a reading has (SPEC_eyes §2): when, which cell, who, with what. The
-- file lives in CAPTURES_DIR, never in this database; `file` is a name inside that folder, never a client's path.
-- The exact point is kept (token only, like the file) and only the FILE is cleaned of EXIF/GPS: a tree or a dump
-- is worth its precise position. `outside` and `at_home` are computed once, on arrival (12 Oct 2026, Tomas).
CREATE TABLE IF NOT EXISTS captures (
  id          BIGSERIAL PRIMARY KEY,
  ts          TIMESTAMPTZ NOT NULL DEFAULT now(),   -- taken: the form's taken_at, else the file's own date, else now
  received_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  kind        TEXT NOT NULL CHECK (kind IN ('microscope','phone','camera','drone','balloon')),
  cell        TEXT NOT NULL,                        -- H3 res 10, the room, derived from the point or given
  lat         DOUBLE PRECISION,                     -- the exact point, nullable when the person gave none, token only
  lon         DOUBLE PRECISION,
  outside     BOOLEAN,                              -- the point is not in the node's seven res-8 cells
  at_home     BOOLEAN,                              -- the point is in the res-10 cell of NODE_LAT/NODE_LON
  actor       TEXT,                                 -- the name the phone keeps in planetai_actor
  note        TEXT,
  file        TEXT NOT NULL,                        -- a name inside CAPTURES_DIR, never a path from the client
  sha256      TEXT NOT NULL UNIQUE,
  bytes       BIGINT NOT NULL,
  mime        TEXT NOT NULL
);
-- The household's own words about an image beyond its note: key → value, edited from the Data door (PATCH /captures).
ALTER TABLE captures ADD COLUMN IF NOT EXISTS meta JSONB NOT NULL DEFAULT '{}'::jsonb;
-- What the image model found (SPEC_eyes step 2): {model, asked, at, summary, findings: [{category, name, count}],
-- confirmed_by}. NULL = not described yet. A finding is the model's until a person here confirms it.
ALTER TABLE captures ADD COLUMN IF NOT EXISTS analysis JSONB;
CREATE INDEX IF NOT EXISTS captures_cell ON captures (cell);
CREATE INDEX IF NOT EXISTS captures_ts ON captures (ts DESC);
-- Not readable by pack SQL: a rule's text reaches /alerts, which a LAN stranger may read, and a capture's exact
-- point must not ride out in one. Same reason settings is revoked (0.21); the default privileges granted it above.
REVOKE ALL ON captures FROM planetai_ro;
INSERT INTO schema_version (version) VALUES ('0.54') ON CONFLICT DO NOTHING;

-- 0.55: the `private` role (docs/decisions/2026-10-03-pack-design.md, point 2 (A)). A private reading is the house's:
-- used on the page, by rules and by cells, and never in the export, a parent's aggregates, the report bundle or an
-- agent's read (packs.public_sql). The CHECK is replaced, because a database made before 0.55 refuses the word.
ALTER TABLE channel_roles DROP CONSTRAINT IF EXISTS channel_roles_role_check;
ALTER TABLE channel_roles ADD CONSTRAINT channel_roles_role_check
  CHECK (role IN ('ambient','enclosure','device_health','derived','index','private'));
INSERT INTO schema_version (version) VALUES ('0.55') ON CONFLICT DO NOTHING;

-- 0.56: the things a home keeps (docs/SPEC_inventory.md). Kept as captures are: not in the export, not readable by
-- pack SQL; the page, rules and cells read the three private counts per class the node writes as readings
-- (stock.<class>, idle.<class>, repair.<class> on the `things:<node>` survey sensor, role private).
CREATE TABLE IF NOT EXISTS things (
  id          BIGSERIAL PRIMARY KEY,
  added_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  class       TEXT NOT NULL,                       -- a flows 1.0 physical class (THING_CLASSES in app/main.py)
  name        TEXT NOT NULL,                       -- the household's words: "cordless drill"
  count       INTEGER NOT NULL DEFAULT 1 CHECK (count >= 1),
  used        TEXT NOT NULL DEFAULT 'monthly' CHECK (used IN ('weekly','monthly','yearly','never')),
  condition   TEXT NOT NULL DEFAULT 'works' CHECK (condition IN ('works','needs_repair','broken')),
  offer       TEXT NOT NULL DEFAULT 'no' CHECK (offer IN ('no','lend','give')),   -- nothing leaves until step 4
  capture_id  BIGINT,                              -- the photo it came from, if any
  note        TEXT
);
REVOKE ALL ON things FROM planetai_ro;
INSERT INTO schema_version (version) VALUES ('0.56') ON CONFLICT DO NOTHING;

-- 0.57: what the node learns (docs/SPEC_learn.md). One row per learning, re-checked and never deleted: a learning
-- that stops holding is marked `weakening` or `gone`. Kept as things are: revoked from pack SQL, in no export, push
-- or report bundle; read by GET /learned with the admin token, and by an agent only while models stay home.
CREATE TABLE IF NOT EXISTS learnings (
  kind        TEXT NOT NULL,                 -- worked (step 1) · usual · asks (step 2)
  key         TEXT NOT NULL,                 -- what it is about: a rule id for `worked`
  issue       TEXT,
  metric      TEXT,
  status      TEXT NOT NULL CHECK (status IN ('too_early','holding','weakening','gone')),
  statement   TEXT NOT NULL,                 -- written by the node from `numbers`, never by a model
  numbers     JSONB NOT NULL DEFAULT '{}'::jsonb,
  n           INTEGER NOT NULL DEFAULT 0,
  scope       TEXT NOT NULL DEFAULT 'house' CHECK (scope IN ('house','place')),
  first_seen  TIMESTAMPTZ NOT NULL DEFAULT now(),
  checked_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (kind, key)
);
REVOKE ALL ON learnings FROM planetai_ro;
INSERT INTO schema_version (version) VALUES ('0.57') ON CONFLICT DO NOTHING;

-- 0.58: the digests (docs/SPEC_learn.md §6): one per completed day, week, month and year, written by the node from
-- its numbers, with the household's own words for what was done. Full-text searched by GET /learned/search; kept as
-- learnings are: revoked from pack SQL, in no export, push or report, never deleted.
CREATE TABLE IF NOT EXISTS digests (
  scale        TEXT NOT NULL CHECK (scale IN ('day','week','month','year')),
  period_start DATE NOT NULL,
  label        TEXT NOT NULL,
  text         TEXT NOT NULL,
  numbers      JSONB NOT NULL DEFAULT '{}'::jsonb,
  written_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  tsv          TSVECTOR GENERATED ALWAYS AS (to_tsvector('simple', label || ' ' || text)) STORED,
  PRIMARY KEY (scale, period_start)
);
CREATE INDEX IF NOT EXISTS digests_tsv ON digests USING gin (tsv);
REVOKE ALL ON digests FROM planetai_ro;
INSERT INTO schema_version (version) VALUES ('0.58') ON CONFLICT DO NOTHING;

-- 0.59: who is in the house (docs/SPEC_learn.md §8). One row of yes/no answers the household gives, so the node can say
-- which learnings matter most here. Never a name, an age or a count; changes no threshold; never leaves: revoked from
-- pack SQL, in no export, push or report, read by GET /household with the admin token.
CREATE TABLE IF NOT EXISTS household (
  id         INTEGER PRIMARY KEY DEFAULT 1 CHECK (id = 1),
  people     JSONB NOT NULL DEFAULT '{}'::jsonb,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
REVOKE ALL ON household FROM planetai_ro;
INSERT INTO schema_version (version) VALUES ('0.59') ON CONFLICT DO NOTHING;

-- 0.60: the morning message (docs/SPEC_learn.md §6). A learning keeps the local day its status last changed, so the
-- morning says what changed and nothing else; rows from before take their first day. A report row says whether it
-- carried the house's memory, so one report a day does, whatever restarts in between.
ALTER TABLE learnings ADD COLUMN IF NOT EXISTS status_since DATE;
UPDATE learnings SET status_since = first_seen::date WHERE status_since IS NULL;
ALTER TABLE reports ADD COLUMN IF NOT EXISTS memory BOOLEAN NOT NULL DEFAULT false;
INSERT INTO schema_version (version) VALUES ('0.60') ON CONFLICT DO NOTHING;

-- 0.61: rooms in the household's words (Tomas, 14 Oct 2026: node #1's K, L and S are Kids, Living Room and Studio). A
-- kit's platform names its sensors ("K ROOM - BAYU HOLES") and every poll writes that name back. A room the household
-- set (PATCH /sensors/{id}) becomes the name whatever writes the row, core or a pack, so the rules, the stats, the
-- report, the event messages and the pages all say the room; the platform's own name is kept in `source_name`.
ALTER TABLE sensors ADD COLUMN IF NOT EXISTS room TEXT;
ALTER TABLE sensors ADD COLUMN IF NOT EXISTS source_name TEXT;
CREATE OR REPLACE FUNCTION sensors_room_is_the_name() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF coalesce(NEW.room, '') <> '' THEN
    -- the incoming name is the platform's unless it is the room this row already had (a rename, not a poll)
    IF NEW.name IS DISTINCT FROM NEW.room AND (TG_OP = 'INSERT' OR NEW.name IS DISTINCT FROM OLD.room) THEN
      NEW.source_name := NEW.name;
    END IF;
    NEW.name := NEW.room;
  END IF;
  RETURN NEW;
END $$;
DROP TRIGGER IF EXISTS sensors_room ON sensors;
CREATE TRIGGER sensors_room BEFORE INSERT OR UPDATE ON sensors FOR EACH ROW EXECUTE FUNCTION sensors_room_is_the_name();
INSERT INTO schema_version (version) VALUES ('0.61') ON CONFLICT DO NOTHING;
