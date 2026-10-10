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

-- Hourly means. A plain view is fine until this node holds millions of rows; then materialize it.
DROP VIEW IF EXISTS readings_1h CASCADE;
CREATE VIEW readings_1h AS
SELECT date_trunc('hour', ts) AS bucket, sensor_id, metric,
       avg(value) AS mean, min(value) AS min, max(value) AS max, count(*) AS n
FROM readings GROUP BY 1, 2, 3;

-- Rolling stats per sensor/metric, used by rules. One row per (sensor, metric).
DROP VIEW IF EXISTS stats CASCADE;
CREATE VIEW stats AS
SELECT r.sensor_id, r.metric, s.indoor, s.local, s.kind, s.scale, s.lat, s.lon, s.name,
       (array_agg(r.value ORDER BY r.ts DESC))[1]                          AS last,
       max(r.ts)                                                             AS last_ts,
       extract(epoch FROM now() - max(r.ts)) / 60                            AS silent_minutes,
       avg(r.value) FILTER (WHERE r.ts > now() - interval '15 minutes')      AS mean_15m,
       avg(r.value) FILTER (WHERE r.ts > now() - interval '1 hour')          AS mean_1h,
       avg(r.value) FILTER (WHERE r.ts > now() - interval '24 hours')        AS mean_24h
FROM readings r JOIN sensors s USING (sensor_id)
-- rolling stats are for sensors only; slow sources (portals, models) live in the `observations` view
WHERE r.ts > now() - interval '24 hours' AND s.kind = 'sensor'
GROUP BY r.sensor_id, r.metric, s.indoor, s.local, s.kind, s.scale, s.lat, s.lon, s.name;

-- Slow-moving numbers (a city statistic, a satellite point sample, a survey) don't belong in a 24h rolling view.
-- One row per source per metric per period, latest wins.
DROP VIEW IF EXISTS observations CASCADE;
CREATE VIEW observations AS
SELECT DISTINCT ON (r.sensor_id, r.metric)
       r.sensor_id, r.metric, r.value, r.ts, s.name, s.kind, s.scale, s.local, s.cadence, s.meta
FROM readings r JOIN sensors s USING (sensor_id)
WHERE s.kind <> 'sensor'
ORDER BY r.sensor_id, r.metric, r.ts DESC;

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
  role        TEXT NOT NULL CHECK (role IN ('ambient','enclosure','device_health','derived','index')),
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
-- sends the same "a new version is out" twice. Written by check_release() in app/main.py; nothing else reads it.
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
SELECT t.bucket, t.sensor_id, 'apparent',
       t.mean + 0.33 * (h.mean / 100.0 * 6.105 * exp(17.27 * t.mean / (237.7 + t.mean))) - 4.0
FROM b t JOIN b h ON h.sensor_id = t.sensor_id AND h.bucket = t.bucket AND h.metric = 'humidity'
WHERE t.metric = 'temp';

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
INSERT INTO schema_version (version) VALUES ('0.53') ON CONFLICT DO NOTHING;
