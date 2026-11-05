# Grafana
<!-- checked: v0.91.0 -->

The dashboard draws the node the way this project decided to draw it. Grafana is for the person who keeps the node
and wants to look at their own data their own way: a month of one room, every sensor on one chart, the hours a sensor
went quiet, panels nobody here thought of. It runs beside the dashboard and never replaces it.

Grafana reads the database directly, raw readings included, and carries none of the dashboard's rules. It will not
mark a number `live`, `partial` or `stale`, and it draws a model's estimate the same way as a measurement unless you
tell it apart. The starter dashboard's title says so ("keeper's view · no provenance"), and the
[traps](#what-grafana-will-not-tell-you) further down are yours to keep in mind.

## Turn it on

```bash
planetai grafana
```

It adds `grafana` to `COMPOSE_PROFILES`, makes Grafana's database login, starts Grafana and prints its address,
`http://127.0.0.1:3000` unless you changed it. Sign in as `admin` with `GRAFANA_ADMIN_PASSWORD`, or `admin` until you
set one. The starter dashboard is in the PLANETAI folder.

Grafana listens on the node's own machine only. From a laptop, tunnel to it:

```bash
ssh -L 3000:localhost:3000 <the node's machine>
```

and open `http://localhost:3000` on the laptop. To open it to the house network instead, set `GRAFANA_ADMIN_PASSWORD`
first, then `GRAFANA_BIND=0.0.0.0`, and run `planetai grafana` again. Whoever signs in sees everything the next
section lists.

```bash
planetai grafana off
```

stops it, takes it out of `COMPOSE_PROFILES` and drops the database login. Your own dashboards stay in the `grafana`
volume, and come back the next time you turn it on.

| key | default | what it does |
|---|---|---|
| `GRAFANA_PORT` | `3000` | the port Grafana answers on |
| `GRAFANA_BIND` | `127.0.0.1` | the address it listens on; `0.0.0.0` is every interface |
| `GRAFANA_ADMIN_PASSWORD` | `admin` | the password of Grafana's `admin` login |

The three keys are read at start, so they are changed in `.env`, then `planetai grafana` again. Set up › System says
whether Grafana is running, at which address, whether its password is set (never the password) and how to open it
from a laptop.

## What it can read

Grafana signs in to the database as `planetai_grafana`, a login made by `config/grafana/role.sh` each time Grafana
starts. It belongs to `planetai_ro`, the role pack rules already run as, which can read every table except
`settings` and the household's own (`captures`, `things`, `learnings`, `digests`, `household`), and write none. On top of that:

- every session it opens is read-only;
- a query stops after 30 seconds, so a wide panel cannot slow the node down;
- it holds four connections at most;
- its session timezone is the node's `NODE_TZ`, as the app's own connections are;
- its password is generated into the `grafana-secret` volume. Nothing goes in `.env`.

What it can read is far more than the API gives a screen without a token. The rooms have their real names, the
household's sensors stand at their real points, and private channels (a home's counts of what it keeps) are there in
full. That is why Grafana listens on loopback by default, and why `GRAFANA_BIND` comes after a password.

The tables a panel usually wants are `readings` (`ts, sensor_id, metric, value`), `sensors` (who each sensor is, in
which room, and whether it is the household's) and `alert_events` (what the node said and when).

## The starter dashboard

It fills itself from this node's sensors: three pickers choose a metric, a room and an outside sensor, out of the ones
that reported in the last week.

| panel | what it shows |
|---|---|
| in every room and yard, hourly | the household's own sensors, the hourly mean of the raw readings, mean, max and 95th percentile beside each |
| a room by hour of day, one column per day | each cell is one hour's mean. A habit shows as a row, a bad day as a column |
| a room against outside | one dot per hour. Above the diagonal the room is worse than outside, so the source is indoors |
| when each sensor was heard | every one of the household's sensors, every three hours, red where it sent nothing. A sensor that never spoke is a red row |
| outside | every outdoor sensor the node reads, the neighbours' too, and the model, dashed |
| radios | how busy each Meshtastic radio's channel is. Empty on a node with no radio |

The node's alert events are drawn on the time charts, from when each opened to when it cleared, marked `sent` or
`held`.

The starter ships with the node and is replaced on every update, so Grafana will not save changes over it. Save as
makes a copy that is yours; edit that one.

## What Grafana will not tell you

### The forecast is stored in the future

The forecast pack writes each value at the hour it is for, days ahead, as
`fc_*` metrics with `fc_lead_hours` beside them. A query with no upper bound, or a time picker set past now, draws
tomorrow's forecast as if it had been measured. End every query on `readings` or `readings_1h` with `ts <= now()`
(`bucket <= now()` on `readings_1h`). The starter does.

### A silence is drawn as a line

Grafana joins the points it has. When a sensor sends nothing for seven hours there
are no rows for those hours, so the line runs straight across them. In a time series panel, set *Connect null values*
to *Never* and *Insert nulls* to a gap you care about (the starter uses three hours). The heatmap and the
when-heard panel show silence without being told.

### Hour of day is the session's

Grafana's own axis follows `NODE_TZ`. Inside SQL, use
`ts AT TIME ZONE current_setting('TimeZone')`, which is `NODE_TZ` for `planetai_grafana`. The same query pasted into
`psql` runs in UTC, eight hours off in Bali, unless you `SET TIME ZONE` first.

### Some rows are models

`sensors.kind` says what a row is: `sensor` measured it, `model` estimated it (the CAMS
point, Open-Meteo, the forecast), `map` counted it from OpenStreetMap or satellite. `sensors.local` is true for the
household's own; the rest are other people's stations the node reads.

### `$__timeGroup` is a number

For PostgreSQL it gives epoch seconds, not a timestamp, so it will not join a
`generate_series` of times. Wrap it in `to_timestamp(...)`, or build the bucket yourself as the when-heard panel does.

### Names change

A room renamed in Set up is renamed in `sensors`. An alert written before that keeps the old name
in its text.

Next, [Schema](schema.md): every table and view a panel can be built from.
