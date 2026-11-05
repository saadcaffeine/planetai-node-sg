# Data schema
<!-- checked: v0.91.0 -->

Everything the node knows sits in one Postgres database, `planetai`, on the machine itself. A pack's rules and cells are SQL written against the tables and views on this page, and a person debugging a node at 9 pm reads the same ones with `psql`. The raw readings live in `readings` and stay here: "No raw readings leave the instance that recorded them" (ARCHITECTURE.md). What goes up to a parent is `readings_1h`, the hourly means, and the timestamps in `alerts` and `actions`.

`init.sql` is the whole schema, and it is written to be run twice: `CREATE TABLE IF NOT EXISTS`, `ALTER TABLE … ADD COLUMN IF NOT EXISTS`, and `DROP VIEW` then `CREATE VIEW`. Postgres runs it on its own only when the data volume is first created, so `update.sh` applies the same file to the existing database on every update, and `planetai restore` applies it after a restore. There are no other migration files. Schema changes are additive by rule (SPEC §5): no dropped columns, no renames, no destructive migrations, which is what makes a rollback a `git checkout <tag>` and a restart instead of a restore. The one column ever dropped is `events.cleared_at`, which nothing had written. `schema_version` records where a node is, and `/health` reports it.

`init.sql` holds 18 tables, 4 views, 1 materialized view, 1 trigger and 1 role, and the `place` pack adds four tables of its own.

## Tables

### `sensors`

One row per thing that produces readings, and per place the node was told about.

| column | type | meaning |
|---|---|---|
| `sensor_id` | text, primary key | `<source>-<upstream id>`: `sc-19880`, `bad-pa-46949`; a child's as `<child>/<sensor_id>`; a fab lab's as `lab-<slug>`. Never reassigned |
| `source` | text | the adapter that wrote it, for example `smartcitizen`, `airgradient`, `purpleair`, `meshtastic`, `open-meteo`, `open-meteo-cams`, `nasa-power`, `ckan`, `child` (a child's push), `contributor` (a `POST /readings` that names no source), `things`, or a pack's (`fablabs-io` for `make`, `baliairdispatch` for `bali-air-dispatch`) |
| `name` | text | the place, as the person named it: the `room` when the household set one, else the platform's name |
| `room` | text | the household's word for where the sensor is, set with `PATCH /sensors/{sid}`; a trigger makes it the `name` whatever writes the row |
| `source_name` | text | the platform's own name, kept while a `room` stands in for it |
| `lat`, `lon` | double | position; rounded before it leaves for a reader without a token |
| `indoor` | bool | measures a room; never in an ambient average |
| `local` | bool | the person's own **and** within `LOCAL_RADIUS_M` of the node |
| `kind` | text | `sensor` · `portal` · `model` · `survey` · `child` · `peer` · `facility`, as `init.sql` lists them; the `place` pack also writes `map` |
| `scale` | text | `community` · `city` · `region` · `bioregion` · `planet` |
| `cadence` | text | ISO 8601 duration: `PT5M`, `PT1H`, `P1D`, `P30D`, `P1Y` |
| `meta` | jsonb | free-form. A reader of `/sensors` without a token gets only `licence`, `attribution`, `model`, `dataset`, `network`, `note`, `corrected`, and for a `facility` row ten more keys that describe the lab |
| `custody` | bool, generated | `kind = 'child' OR (local AND kind <> 'peer')`. The only thing a cell may count |

The one `survey` row is `things:<node>`, the counts of the things a home keeps. Nothing writes `peer`; it is named in `init.sql` and in the `custody` expression.

A facility has no readings. `kind = 'facility'` is a place with a name and a point, and the `make` pack writes it: with `MAKE_ENABLED=1` it stores each active lab within `MAKE_RADIUS_KM` as one row, `sensor_id` `lab-<slug>`, `source` `fablabs-io`, `local` false, `scale` `community`, `cadence` `P30D`. Its `meta` holds `slug`, `capabilities`, `kind_name`, `city`, `country_code`, `distance_km`, `url`, `registry_slug`, `snapshot`, `fetched` and `attribution`. No `readings` row is written for it, so it is in neither `stats` nor `observations`; `/issues` reads it straight from `sensors`. Because `local` is false, `custody` is false, and a fab lab can never make an Index cell say `live`.

### `readings`

| column | type | |
|---|---|---|
| `ts` | timestamptz | a UTC instant |
| `sensor_id` | text → `sensors` | |
| `metric` | text | lowercase, no unit in the name |
| `value` | double | |

Unique on `(sensor_id, metric, ts)`, so polling twice is harmless. The one exception is a forecast: a newer run replaces the value of an `fc_` metric for an hour still ahead, and a past hour or a measurement is never rewritten. Indexed `(sensor_id, metric, ts desc)` and on `ts` alone.

### `alerts`

| column | | |
|---|---|---|
| `id` | bigserial | the number a person answers |
| `ts` | timestamptz | when the rule fired |
| `rule_id` | text | `<pack>/<id>`, or a bare core id |
| `sensor_id` | text | the row's sensor, or `node` |
| `level` | text | `info` · `warn` · `act` |
| `text` | text | the filled message |
| `event_id` | bigint → `alert_events.id` | the event the alert fed. Nothing writes it yet, so it is null on every row |
| `buttons` | jsonb | the buttons the rule offered with this alert, checked before they are stored; null when it offered none |

Indexed `(rule_id, sensor_id, ts desc)` for the cooldown check. An alert never clears, it only cools down; an [alert event](#alert-events) is the row that opens and clears.

### `actions`

The ρ instrument: what happened after an alert, one row per answer.

| column | | |
|---|---|---|
| `ts` | timestamptz | |
| `alert_id` | bigint → `alerts.id` | null for `settings` rows and for the answers to an alert event |
| `event_id` | bigint → `alert_events.id` | set only on an answer to an event, from `POST /actions` with an `event_id`; null on every other row |
| `stage` | text | checked: `acknowledged` · `acted` · `measured` · `settings` · `decided` · `dismissed` |
| `actor` | text | who: the name typed on the dashboard, the login name from `planetai act`, `lxmf:<hash>` from the radio bridge, an agent's name, or the `X-Agent` of a settings change |
| `note` | text | in the person's words |
| `choice` | text | the `value` of the alert's button that was pressed, from `POST /actions` with a `choice`; null on every other row |

The six stages do different things, and two of them are never posted by a person.

| stage | written by | what it moves |
|---|---|---|
| `acknowledged` | `POST /actions` | ρ, and `/alerts.acted_at` |
| `acted` | `POST /actions` | ρ, `acted_at`, and closes the alert |
| `decided` | `POST /actions` | Nothing. It records that somebody said what they would do: it is not in ρ or the funnel and closes no alert |
| `dismissed` | `POST /actions` with an `event_id`, never with an `alert_id` | Nothing. It is *Doesn't fit*, said of an alert event's advice |
| `measured` | nothing | `POST /actions` refuses it. The node derives `measured` from an `acted` alert whose rule stayed silent on the same sensor for 2880 minutes; see [ρ](rho.md). A `measured` row already in the table still counts |
| `settings` | `PUT /settings`, `planetai config set`, the `settings_set` tool | Nothing in ρ; it records who changed which keys |

An `acknowledged` or `acted` row with a `choice` answers a button of the alert's own, one row for each person's choice. An `acknowledged` or `acted` row with an `event_id` answers an alert event. On `ALERT_ENGINE=events`, ρ and its funnel count each event the engine sent at act level once, answered by a row with an `event_id`; the rows of the packs the engine replaced are left out from its first sent message on. `GET /effect` and the push to a parent read only rows with an `alert_id`.

With `DECISION_REQUIRED=1`, `POST /actions` refuses an `acted` row for an alert that has no `decided` row yet. The table itself does not enforce that.

### `reports`

| column | | |
|---|---|---|
| `id`, `ts` | | |
| `due_local` | timestamptz | the local due hour; the row is the scheduler's lock. Null for `POST /report/now` |
| `window_hours` | int | |
| `depth` | text | `sheet` on every row; `brief` · `standard` · `deep` are reserved |
| `rung` | text | `node` on every row; `local` · `remote` · `online` are reserved |
| `text` | text | what was sent. Both writers put the sheet here, so it equals `sheet` |
| `sheet` | text | the node's own six parts, always |
| `sent`, `held_quiet` | bool | a report due in quiet hours is written with `sent` false and `held_quiet` true, and folded into the next |
| `fallback_reason` | text | why `text` is the sheet and not a model's. Nothing writes it yet |
| `cells` | jsonb | the Index cells at the time of the report |
| `memory` | bool | it carried the morning memory on Telegram; one report a day does |

### `events`

ρ from below: one row per child alert, pushed hourly by children to `POST /events`.

| column | | |
|---|---|---|
| `child`, `alert_id` | text, primary key together | |
| `rule`, `level`, `kind`, `scale` | text | `kind` is the pack prefix |
| `raised_at`, `responded_at`, `acted_at`, `measured_at` | timestamptz | timestamps only: no text, no actor, no sensor |
| `received_at` | timestamptz | |

`measured_at` is null in practice: a child fills it from posted `measured` rows, and `POST /actions` does not take one. The parent's funnel in `/rho` is computed from its own alerts only, and says so with `self_only: true`.

### `alert_events`

The alert-event engine's stories ([Alerts](alerts.md#the-event-engine)): one row per issue per house, from the first candidate over its line to the all-clear. Written only under `ALERT_ENGINE=shadow` or `events`, and empty under `rules`. It is called `alert_events` because `events` is the parent's ledger above.

| column | | |
|---|---|---|
| `id` | bigserial | |
| `issue`, `kind`, `level` | text | the issue (`heat`, `air`), the highest kind seen (`ahead` · `unusual` · `spike` · `sustained` · `danger`), the highest level |
| `opened_at`, `last_seen_at`, `last_sent_at`, `cleared_at` | timestamptz | `cleared_at` is null while the event is open; an open event clears after 30 minutes with no candidate |
| `peak` | double | the highest value seen |
| `rooms`, `places` | text[] | the sensors' names, and where each was (`inside`, `outside`) |
| `ever_sent` | bool | whether any message for it went out; an all-clear is sent only if so |
| `action_id` | text | the action the last message carried |
| `told_kind`, `told_peak`, `told_level`, `told_held`, `last_emitted_at` | | what the last message said, sent or held, so a restart does not forget where the escalation was |

### `event_messages`

Every message the engine decided, sent or held.

| column | | |
|---|---|---|
| `id`, `ts` | | |
| `event_id` | bigint → `alert_events.id` | |
| `reason` | text | checked: `open` · `escalate` · `clear` |
| `kind` | text | the event's kind when this was decided; `danger` is never counted against the daily ceiling |
| `sent` | bool | in `shadow`, what would have been sent |
| `held` | text | why not: `quiet` · `ceiling` · `level`; null when sent |
| `mode` | text | `shadow` or `events` |
| `text` | text | the message as rendered, or null when it could not be |
| `action_id` | text | the action it carried; null for an all-clear or when none was chosen |

### `channel_roles`

What each `(source, metric)` is, written at every start from `config/channels.yml` and every pack's `channels.yml`: `role` (`ambient` · `enclosure` · `device_health` · `derived` · `index` · `private`), `comparable`, `unit`, `reference` and `declared_by`. A `private` reading is used on the page, by rules and by cells, and never in the export, a parent's aggregates, the report bundle or an agent's read.

### `settings`

`key`, `value`, `updated_at`: the runtime overlay over `.env`, written from Set up, `planetai config set`, `PUT /settings` and the `settings_set` tool. The rules' role cannot read it, and its rows are left out of every dump, so a saved token never travels.

### `schema_version`

`version`, `applied_at`; one row per schema step: 0.4, 0.14, 0.20 to 0.23, 0.50 to 0.52, and 0.54 to 0.61. There is no 0.53 row; the alert-event tables are created without one. An up-to-date node reports `0.61` at `/health`.

### `release_notices`

`version`, `told_at`: one row per release the node has told its household about, so a restart or the hourly re-check never sends "a new version is out" twice for the same one (`UPDATE_CHECK`). Written by `check_release()` in `app/main.py`. A row `pack:<id>` is a pack on the wild list it has told them about (`check_wild`), and `GET /packs/all` reads those to mark a pack new.

### `captures`

The pictures a household keeps ([`docs/SPEC_eyes.md`](../SPEC_eyes.md)): `id`, `ts` (when it was taken), `received_at`, `kind` (`microscope` · `phone` · `camera` · `drone` · `balloon`), `cell` (H3 res 10), `lat` and `lon` (the exact point, or null), `outside` and `at_home` (both computed once on arrival), `actor`, `note`, `file` (a name inside `CAPTURES_DIR`, never a path), `sha256` (unique), `bytes`, `mime`, `meta` (the household's key: value lines) and `analysis` (what the image model found, null until described). Written by `/captures`, the eyes pack's routes. The file is in `CAPTURES_DIR`, never in the database. Revoked from `planetai_ro`, and in no export, aggregate or push.

### `household`

Who is in the house ([`docs/SPEC_learn.md`](../SPEC_learn.md)): one row (`id` = 1), `people` (yes or no for `older`, `under5`, `lungs`, `pregnant`, `outdoor`) and `updated_at`. Written only by `PUT /household`. Revoked from `planetai_ro`, and named by no export, push or report.

### `digests`

The node's diary: `scale` (`day` · `week` · `month` · `year`) and `period_start` (the primary key together), `label`, `text`, `numbers`, `written_at`, and `tsv`, a generated full-text vector of label and text with a GIN index. `check_learn()` writes them in the first hour of each local day, for every completed period not yet kept, oldest first; `numbers.v` says which version wrote a row, and a row written by an older version is written again once. Never deleted. Revoked from `planetai_ro`, and named by no export, push or report.

### `learnings`

What the node learned: `kind` and `key` (the primary key together), `issue`, `metric`, `status` (`too_early` · `holding` · `weakening` · `gone`), `statement`, `numbers`, `n`, `scope` (`house` · `place`), `first_seen`, `checked_at`, and `status_since`, the local day its status last changed, which the morning memory reads to name what changed that day. `check_learn()` writes them once a day; a row is replaced, never deleted. Revoked from `planetai_ro`, and named by no export, push or report.

### `things`

What a home keeps ([`docs/SPEC_inventory.md`](../SPEC_inventory.md)): `id`, `added_at`, `class`, `name`, `count`, `used` (`weekly` · `monthly` · `yearly` · `never`), `condition` (`works` · `needs_repair` · `broken`), `offer` (`no` · `lend` · `give`), `capture_id` and `note`. Written by `/things`, the things pack's routes. Revoked from `planetai_ro`, so no pack SQL reads it, and named by no export or push. Its counts per class reach `readings` as the private `stock.<class>`, `idle.<class>` and `repair.<class>`.

### `readings_1h_done`

The finished hours behind the `readings_1h` view: `bucket, sensor_id, metric, mean, min, max, n`, one row per sensor,
metric and hour. The app fills it from `readings`, the last 26 hours every hour and the whole table on start and once a
day. Read `readings_1h`, never this table: the view adds the hours this table has not got to yet.

### Pack tables

The `place` pack creates `place_features` (OpenStreetMap features with a PostGIS geometry), `place_runs`, `place_yearly` and `place_buildings_sat` (Open Buildings). Tables a pack creates inherit the read-only role's `SELECT` through default privileges.

## Views

| view | rows | columns |
|---|---|---|
| `readings_1h` | hourly means over all readings: the finished hours from `readings_1h_done`, and the rest grouped live from where that table ends, so it is complete even when the table is behind | `bucket, sensor_id, metric, mean, min, max, n` |
| `stats` | one per (sensor, metric), last 24 h, `kind='sensor'` only | `sensor_id, metric, indoor, local, kind, scale, lat, lon, name, last, last_ts, silent_minutes, mean_15m, mean_1h, mean_24h` |
| `observations` | the latest row per (sensor, metric) for `kind <> 'sensor'`, as of now: a forecast hour still ahead is not an observation | `sensor_id, metric, value, ts, name, kind, scale, local, cadence, meta` |
| `recent_15m` | quarter-hour means of the last 24 h, `kind='sensor'` only, with `apparent` (the no-wind indoor feels-like) derived wherever `temp` and `humidity` share a bucket | `bucket, sensor_id, metric, mean` |
| `usual_by_hour` (materialized) | each room's own normal for each local hour, from the fourteen complete local days before today, for `temp`, `humidity`, `pm25` and `apparent` | `sensor_id, metric, hour, median, p75, p90, n` |

A rule with a `kind:` reads `recent_15m` and `usual_by_hour`, so it can ask "for how long" and "against what usual" without rebuilding either from raw readings every minute. `GET /issues` reads `usual_by_hour` too, for each issue's `usual`. `usual_by_hour` is created empty, and the app refreshes it at start and hourly in `NODE_TZ`; a rule that reads it before the first refresh fails, is logged, and runs again a minute later.

Sensors land in `stats`. Slow sources (portals, models, maps) land in `observations`, which keeps the latest row per source per metric forever, so a retired metric must not be read as this year's answer. A facility lands in neither, because it has no readings.

## The read-only role

`planetai_ro` is `NOLOGIN`, has `SELECT` on every table except `settings`, `captures`, `things`, `learnings`, `digests` and `household`, and writes nothing. Every rule and every cell runs as it, one statement at a time with `SET LOCAL ROLE`, so a rule cannot read a token into an alert text or change a row. Grafana's login, `planetai_grafana`, is a member of it, made by the `grafana-role` container and not by `init.sql` ([Grafana](grafana.md)).

## Time and place inside the database

The session time zone is `NODE_TZ`, so `date_trunc('day', ts)` and `extract(hour from ts)` mean the household's day and hour; readings themselves are UTC instants. The node's position is available to SQL as `current_setting('planetai.lat')` and `current_setting('planetai.lon')`. The app sets both on every connection it opens. A `psql` session does not go through the app, so there an hour-of-day query answers in the database's own time zone and `planetai.lat` is not set.

## The database image

The `db` service runs `imresamu/postgis:16-3.4-alpine`, Postgres 16 with PostGIS 3.4, which publishes `linux/amd64` and `linux/arm64` under the same tag. It stays on Alpine because an existing node's data directory was created by musl: opened with a glibc build, the node starts and its text indexes fail an integrity check, with no warning from Postgres. Postgres is published on `127.0.0.1:5432` only. [ARM64.md](../ARM64.md) has the arm64 detail.

## Backups and restore

`backup.sh` runs nightly at 03:17 from cron, or on demand with `planetai backup`.

1. It refuses a `BACKUP_DIR` under `/Volumes`, `/mnt` or `/media` that is not mounted, instead of creating a local folder with the NAS's name.
2. It runs `pg_dump` with the `settings` table's rows left out (the table stays in the dump, empty), gzips it to `<node>-<date>.sql.gz`, and keeps it only if it is a valid gzip holding a `readings` table.
3. It deletes dumps older than `BACKUP_KEEP` days (default 30).
4. It writes yesterday's `/export` to `exports/<node>/YYYY-MM-DD.json` when `EXPORT_ENABLED=1` (the default), and adds it to IPFS when `IPFS_PUBLISH=1`.
5. It copies the dumps and exports to `BACKUP_REMOTE` with rclone, if that is set.
6. It writes the time to `LAST_OK` in `BACKUP_DIR`.

`planetai restore <dump>` asks you to type the node's name, takes a safety backup with `backup.sh`, stops the app, drops and recreates the database, restores the dump, re-applies `init.sql` and starts the app. It prints the number of readings when it is done. The dump carries no settings rows, so a restored node runs on `.env` until Set up is saved again, and a Telegram bot connected from the dashboard needs `planetai telegram` once more.

The database stays on a local disk. SMB and NFS do not honour `fsync` and file locking, and a mount path that is not mounted becomes an empty local folder with the NAS's name. Backups are how the data reaches a NAS, and [Storage](storage.md) says where the copies go.

## Where this leads

The rows here reach screens and other nodes through the [API](api.md). A child's hourly push sends `readings_1h` to its parent's `POST /aggregates`, and the timestamps of `alerts` and `actions` to `POST /events`. [Federation](federation.md) is the page for pointing a child at a parent.
