# HTTP API
<!-- checked: v0.91.0 -->

Every node exposes the same API on port 8080. The dashboard, the `planetai` command, the MCP tools, a NAS pulling backups, Home Assistant and a parent node are all clients of it, and none of them has a private path in. A request carries a token as `Authorization: Bearer <token>` or carries nothing, and the `SHARE_LEVEL` setting decides what a request with nothing may read.

The port is published on every interface of the host (`APP_PORT`, default 8080); Postgres listens on `127.0.0.1:5432` only. The node speaks plain HTTP, the tailnet encrypts the hop, and the [sharing page](sharing.md) says what to do on a network that is not a tailnet. Answers are JSON unless a route says otherwise. A request that asks for gzip, as every browser does, gets JSON, scripts and styles above 1 kB compressed; `/mcp`, the `/ask` stream, the backups and the images are sent as they are.

## Access rules

A request is trusted when it comes from loopback or carries a household token: `ADMIN_TOKEN`, `BACKUP_TOKEN` or `ACT_TOKEN`. An untrusted request is checked against the allowlist for the current `SHARE_LEVEL` and gets 403 when its path is not on it. The handler then makes its own token check, if it has one. Each route below names its class.

| Class | Who is answered |
|---|---|
| `public` | Anyone, at every `SHARE_LEVEL`. |
| `open` | Loopback or a household token; anyone else only at `SHARE_LEVEL=open`. |
| `token` | Loopback or a household token. |
| `admin` | `ADMIN_TOKEN` only, from loopback too. |
| `pull` | `ADMIN_TOKEN` or `BACKUP_TOKEN`, the read-only token for a NAS. |
| `act` | Loopback with no token; from anywhere else `ACT_TOKEN` or `ADMIN_TOKEN`. |
| `children` | `AGGREGATE_TOKEN`, which a parent gives its children. It opens `POST /aggregates` and `POST /events` and nothing else. |

The `off` allowlist, the default, is `/`, `/ui`, `/workbench`, `/tester`, `/health`, `/llms.txt`, `/settings`, `/export`, `/presence`, `/nodes`, `/offers` and anything under `/static/`. The `open` allowlist adds `/stats`, `/sensors`, `/observations`, `/alerts`, `/series`, `/sparks`, `/rho`, `/cells`, `/packs`, `/packs/all`, `/trust`, `/nearby`, `/forecast`, `/earth`, `/earth/change.png`, `/earth/year.png`, `/earth/frame.png`, `/report/latest`, `/readings`, `/reach`, `/shape`, `/effect`, `/history`, `/exports`, `/sources`, `/ask`, `/ask/status`, `/docs/search`, `/geo/cell`, `/learned/place`, and anything under `/exports/`, `/issues`, `/sources/` or `/ground/`. The pack routes among them (`/offers`, `/nearby`, `/forecast` and the `/earth` paths) are put there by their pack's `pack.yaml` (`share:`). Any other value counts as `off`. The lists match the path whatever the method, so at `open` an anonymous `POST /readings` reaches the handler and gets 401. A path with no route also gets 403.

Tokens travel in the `Authorization` header only, never in a query string, and are compared in constant time. `ADMIN_TOKEN` is in `.env`, the other three in settings, and `planetai ui` prints them. An optional `X-Agent` header names the caller; `PUT /settings` writes it to the ledger.

Loopback is the socket's peer address, never a header: `X-Forwarded-For` is not read, so a proxy in front of the node does not make its clients loopback. Inside Docker that is the node's own MCP tools and a shell in the container. A browser on the machine hosting the node arrives from the Docker bridge and is treated like any other client on the network.

An untrusted caller gets less, in four ways:

- Room names: each local sensor's `room`, `name` and `source_name` become `Room A`, `Room B`, `Sensor 1` and so on, in every field and sentence. Alert sentences written under older names are left out: `/alerts` answers `text: null` and `buttons: null`, and so do the alert texts in `/issues`.
- Positions: nothing finer than the node's resolution-8 cell: `/health` and `/export` carry its centre, the household's own sensors in `/sensors` and `/stats` stand there (a child's at its own cell's centre), and other sensors are rounded to 3 decimals. `/forecast` and `/earth` carry the exact point and are `open`, while `/place/geojson` and most `/geo/` routes are `token`.
- Private values: a channel a pack declares `private`, such as the counts of what a home keeps, is in `/readings`, `/history`, `/series`, `/sparks` and `/observations` only for `ADMIN_TOKEN`, and in `/stats` for `ADMIN_TOKEN`, `ACT_TOKEN` or loopback. A request carrying `X-Agent` never gets one.
- Who answered: the `actor` and `note` of every answer in `/issues` are null.

Timestamps are ISO 8601 with an offset: `NODE_TZ` for what comes from the database, UTC for what the node stamps itself (`last_poll`, `generated`, `as_of`, `observed_at`).

## Errors

The middlewares answer `{"error": "..."}`. A share-level 403 names the level and the path, and says the fix when there is one:

```json
{"error": "this node is set to SHARE_LEVEL=off, so /alerts answers only this machine or a request carrying a token. Set SHARE_LEVEL to open in the dashboard's Set up view to let anything on your network read it."}
```

For a path no level opens it ends "No share level opens this one, so it always needs a token from anywhere but the node itself." `/mcp` without the admin token is 401 `{"error": "the agent surface needs Authorization: Bearer <ADMIN_TOKEN>"}`.

Some routes are a pack's, served from `packs/<id>/routes.py`: `/forecast` (forecast), `/nearby` (nearby), `/earth`, `/earth/change.png` and `/earth/year.png` (earth), `/earth/frame.png` (earth-engine), every `/captures` route and `/species` (eyes), and `/things` and `/offers` (things). While its pack is off on the node, such a route answers 404 `{"detail": "the <pack> pack is off on this node"}`.

Handlers answer `{"detail": "..."}`. The token checks:

| Check | Token not set on the node | Wrong or missing in the request |
|---|---|---|
| `admin` | 403 ``ADMIN_TOKEN is not set in .env; run `planetai ui` to create one`` | 401 `bad or missing admin token` |
| `pull` | 403 `no BACKUP_TOKEN or ADMIN_TOKEN set on this node` | 401 `bad or missing token` |
| `act` | 403 ``no ACT_TOKEN or ADMIN_TOKEN set on this node; run `planetai ui` to create one`` | 401 `closing a loop from off this machine needs Authorization: Bearer <ACT_TOKEN>` |
| `children` | 403 `this node accepts no children: set AGGREGATE_TOKEN in .env and give it to them` | 401 `bad or missing Authorization: Bearer <AGGREGATE_TOKEN>` |

## Status

The routes a screen asks first, to know whether the node is up and which version and cell it is.

### GET /health
Access: public

What every screen in the house polls. Answers at every `SHARE_LEVEL` and never makes an outbound request of its own.

Returns `ok` (true once a poll has run), `node`, `version`, `schema`, `uptime_s`, `lat`, `lon`, `position` (`cell` or `point`), `city`, `polls`, `last_poll`, `last_error`, `ingested`, `errors` (each loop's last error), `locale`, `tz`, `cell` (`{id, res, edge_m, caption}`, null before setup), `docs`, `mcp` and `llms`. With their features on it adds `mesh` (`MQTT_HOST`), `direct` (`MQTT_HOST` with the smartcitizen pack on), `reticulum` (`RETICULUM_URL`) and `release` (`{latest, current, newer, checked, asked}` from the hourly check, with `UPDATE_CHECK=on`). `schema` starts with `unreachable` when the database refuses the app, usually a wrong password after a reinstall; `planetai doctor` says why.

```json
{"ok": true, "node": "bayu-ungasan", "version": "v0.91.0", "schema": "0.61", "uptime_s": 86121,
 "lat": -8.825, "lon": 115.159, "position": "cell", "city": "bali", "polls": 287,
 "last_poll": "2026-10-20T08:35:02+00:00", "errors": {}, "locale": "id", "tz": "Asia/Makassar",
 "cell": {"id": "...", "res": 8}, "docs": "https://planetai.fab.city/docs/", "mcp": "/mcp", "llms": "/llms.txt"}
```

### GET /health/sources
Access: token

The sources every node needs, each running or not, and for each that is not, the one thing to do. `planetai doctor`, Set up and the MCP `health_check` all show it. The rows are `own-sensors`, `alerts` (Telegram), `nearby-stations`, `weather`, `satellite-air`, `backup` and `map`. `?backup_age=` passes the minutes since the newest dump where the backups really are (`-1` for none), as `planetai doctor` measures it on the host.

Returns `{ok, missing, sources: [{id, name, state, ok, minutes, age, detail, fix, setup, command, why}]}`. `state` is `ok`, `missing`, `quiet` (nothing inside its window), `waiting` (no poll finished yet), `na` or `elsewhere` (backups the container cannot see). A row with `ok: false` carries a `fix`, the Set up section it is in (`setup`) and the `planetai` command that does it.

### GET /llms.txt
Access: public

Plain text for an agent handed the node's address: the purpose, the version, the read routes, `/mcp` and what it needs, and the documentation's URLs. It says nothing about the house.

### GET /presence
Access: public

What the node announces about itself on Reticulum, read by the bridge container, which has no token. `{"enabled": false}` unless `RETICULUM_PRESENCE=1`, then `{enabled: true, node, cell, res, version, kind}`, with `cell` coarsened to `RETICULUM_PRESENCE_RES` (default 3, never finer than 6).

### GET /nodes
Access: public

The nodes the programme lists, from `registry.json` on the repository's `main`, read every hour. Returns `{read, from, nodes, error?}`, and each node has `name`, `place`, `scale`, `operator`, `since`, `cell` and `ll` (`[lon, lat]` to one decimal). `UPDATE_CHECK=off` reads nothing and serves an empty list.

### GET /machine
Access: token

The machine under the node, read from `/proc` and `/sys`: `arch`, `system`, `cores`, `load`, `cpu_busy_pct`, `memory`, `container_memory`, `temperatures`, `uptime_s`, `python` and `database`. On macOS that is the container engine's virtual machine, and `seen_as` says so.

### GET /storage
Access: token

How much room the node takes: `database_bytes`, `readings`, `readings_last_7_days`, `bytes_per_reading`, `growth_bytes_per_day`, `out_bytes`, `exports_bytes`, `backups` (with `keep_days` from `BACKUP_KEEP`), `disk` and `days_left`, the free space less what backups will take, divided by the daily growth. Nothing is pruned, so the readings are what grows.

## Pages and files

The dashboard and the files it loads, sent with `cache-control: no-cache` so a screen follows the new version after `planetai update`.

### GET /
Access: public

The dashboard, the same as `/ui`.

### GET /ui
Access: public

The dashboard: the five doors by default, the older dashboard with `?layout=classic`, the phone page with `?layout=mobile` (or `walk`). All of them read the same routes with the same token.

### GET /workbench
Access: public

The sensors workbench, a reduced copy of `planetai.fab.city/sensors/` that the dashboard shows as the Data door's Workbench tab (`/#data/workbench`, with `/flash`, `/test` or `/network` after it for one view). It flashes the Bayu and the Meshtastic radios, tests a board over USB, and draws the network this node hears from its `/health`, `/sensors`, `/readings` and `/nodes`, asking for the token when a read is refused. It runs with no internet: the flasher comes from `/static/vendor/esp-web-tools/`, and the firmware from the node's own copy under `/static/firmware/`, which the node refreshes every six hours while it is online. Until the first copy is made, the firmware comes from where the site reads it. Opened on its own, as the site's Connect button opens it, the page goes to `/#data/workbench` at the same view. Browsers only open a USB port where they count the page as secure, so flashing and USB tests work at `http://localhost:8080/` on the node machine. From another laptop on the LAN they work once that laptop's Chrome trusts the node's address: open `chrome://flags/#unsafely-treat-insecure-origin-as-secure`, paste the address exactly as the browser shows it (`http://192.168.1.20:8080`), choose Enabled and relaunch. The page shows this step with its own address filled in. Why this and not https: `docs/decisions/2026-10-27-serial-on-the-lan.md`. 404 when the build does not ship it.

### GET /tester
Access: public

The old address of the sensor bench. It redirects to `/workbench` (308).

### GET /static/{name}
Access: public

The files the dashboard cannot inline, by name only; any other name is 404 `no such asset`. The names are `node-ground.svg`, `jetbrains-mono-latin.woff2`, `FunnelSans-VariableFont_wght.ttf`, `Figtree-VariableFont_wght.ttf`, `Figtree-Italic-VariableFont_wght.ttf`, `dashboard.js`, `dashboard.css`, `d3.min.js`, `plot.umd.min.js`, `planetai-theme.css`, `tokens.css`, `signs.svg`, `kilometre-cells.json`, `learn.json`, `maplibre-gl.js`, `maplibre-gl.css`, `deck.gl.min.js`, `qrcode.js`, `mobile.html`, `mobile.js`, `walk.js`, `world-land-110m.json`, `docs_site.json`, and `doors-<name>.js` for `load`, `nodegeo`, `core`, `fig`, `now`, `placemap`, `place`, `data`, `flow`, `wallmap`, `wall`, `node` and `setup`. `node-ground.svg` is drawn from `NODE_LAT` and `NODE_LON` when they are set, and `?variant=paper` draws it in the paper register.

### GET /static/vendor/esp-web-tools/{name}
Access: public

ESP Web Tools 10.4.0 (Apache-2.0), the workbench's flasher, kept in the node so it flashes offline. A flat file name in that one folder; anything else is 404.

### GET /static/firmware/{path:path}
Access: public

The node's copy of the firmware the workbench flashes: `meshtastic/` as `planetai.fab.city/sensors/firmware/meshtastic/` publishes it, each binary checked against that release's `SHA256SUMS`, and `bayu/` as Making Sense Bali publishes it. Refreshed every six hours while the node is online (not at all with `UPDATE_CHECK=off`), and an old build is deleted once nothing names it. A path outside the copy is 404.

### GET /static/fonts/jetbrains-mono-latin.woff2
Access: public

The mono font, at the fixed path `planetai-theme.css` asks for.

## Sensors and readings

These routes read what the node has measured, from the sensor list down to raw readings and hourly means.

### GET /sensors
Access: open

Every sensor this node reads, its position, and where its numbers come from: `sensor_id`, `source`, `name`, `room`, `source_name`, `lat`, `lon`, `indoor`, `local`, `custody`, `kind`, `scale`, `cadence`, `meta`. An untrusted caller gets no `room` or `source_name`, and `meta` cut to `licence`, `attribution`, `model`, `dataset`, `network`, `note` and `corrected`. A `facility` row, a fab lab, keeps its public description too.

### PATCH /sensors/{sid}
Access: admin

Names the room a sensor is in: `{"room": "Kids"}`, at most 40 characters, or `null` to get the platform's own name back. The room becomes the sensor's `name` everywhere, the platform's name stays in `source_name`, and alerts already sent keep their words. Returns `{ok, sensor: {sensor_id, name, room, source_name}}`.

### GET /readings
Access: open

Raw readings, newest first, as `{ts, sensor_id, metric, value}`. Filters `?sensor_id=` and `?metric=`; `?limit=` 1 to 10000, default 200.

### POST /readings
Access: admin

A phone or a DIY pod on the LAN posts raw readings. The sensor becomes a local sensor, so its values can fire act-level alerts and enter live cells, and that is why this needs the admin token.

```json
{"sensor": {"sensor_id": "phone-abc", "source": "mobile", "name": "kitchen phone",
            "lat": -8.827, "lon": 115.157, "indoor": true, "meta": {}},
 "readings": [{"ts": "2026-10-20T08:30:00+00:00", "metric": "pm25", "value": 12.3}]}
```

Only `sensor.sensor_id` is required. `source` defaults to `contributor`, `indoor` to false, `ts` to now, and a duplicate `(sensor_id, metric, ts)` is ignored. Returns `{"accepted": <n>}`.

### GET /stats
Access: open

Rolling statistics per sensor and metric over 24 hours, for sensors only: `last`, `last_ts`, `silent_minutes`, `mean_15m`, `mean_1h` and `mean_24h`, with the sensor's `indoor`, `local`, `kind`, `scale`, `lat`, `lon` and `name`. Local first; slow sources are in `/observations`.

### GET /observations
Access: open

The latest value of each slow source and metric, up to now (a forecast hour still ahead is not one), such as a city statistic, a model point or a survey: `sensor_id`, `metric`, `value`, `ts`, `name`, `kind`, `scale`, `local`, `cadence`, `meta`.

### GET /trust
Access: open

One row per local sensor for the trust card: `{sensor_id, name, coverage_7d, frozen_channels, age_hours}`. `coverage_7d` is the share of the last 168 hours it reported in, and `frozen_channels` is how many of its channels the core rule `trust/channel_dead` names right now, from that rule's own SQL (a full day flat while the kit still talks, see [Alerts](alerts.md#trust)).

### GET /history
Access: open

Every reading of one metric from one sensor, oldest first, for series that are not hourly. `?sensor_id=` and `?metric=` are required, `?limit=` 1 to 5000 (default 500). Returns `[{ts, value}]`.

### GET /series
Access: open

Hourly means as aligned arrays: local indoor, everything outdoor, and the model (`cams-point`). `?metric=` (default `pm25`) and `?hours=` 1 to 168 (default 24). Returns `{metric, hours, buckets, indoor, outdoor, model}`, null where there is no data.

### GET /sparks
Access: open

Hourly means per sensor, on the same buckets and parameters as `/series`. Returns `{hours: [bucket, ...], series: {sensor_id: [mean or null, ...]}}`.

### GET /reach
Access: open

How far back the node's own record goes, per kind of source: `[{kind, oldest, newest, buckets, sources, days}]`, from `readings_1h`.

### GET /shape
Access: open

The day this place usually has: one mean per local hour of day, over the whole record, indoor apart from outdoor. Only this node's own sensors (`local`) count.

`?metric=` (default `pm25`). Returns `{metric, days, first, last, hours, windows}`, each hour `{hour, indoor, outdoor, n}`. `windows` says what the record can support: `day` from 7 days, `week` from 14, `month` from 60, `year` from 365.

> **Careful.** At `SHARE_LEVEL=open` anyone on the network reads this house's indoor hours here.

## Issues

The one document a client draws. A page, a Telegram handler or a wall screen reads `/issues` and does no arithmetic of its own. The whole `/issues` prefix is on the `open` list and not on `off`, because it carries 15-minute means and alert texts.

### GET /issues
Access: open

Every issue this node declares, computed: state, values by distance, the line, attribution, a sentence in each locale, open alerts and series. Nothing in it came from a model. The order is `NODE_ISSUES`, and an issue the node does not watch appears with `watched: false`.

Returns `{schema: "issues-v0", order, undeclared, dropped, headline, as_of, lead, headline_rule, distances, labels, issues, stations, stations_silent, metrics, asks, digest, mesh, geometry, sections, events}`. The full key set is in `app/issues/engine.py`.

- `headline` is the issue of an open alert event, or else the one with the highest state; `lead.by` says which step picked it (`event`, `state`, `moved` or `order`).
- Each issue carries `state`, `reason`, `name`, `metric`, `unit`, `line`, `stack`, `series`, `buckets`, `readouts`, `provenance`, `trend`, `open_asks`, `sentence`, `title` and `tagline` (by locale), `asking` (what the house is asked about it now), `hero` (what the page draws when it leads), `about`, and `usual` with `usual_absent`.
- `stations` is every station with a position: its `read` (the 15-minute mean per metric) and its hourly `series`, both only for the metrics in `metrics`, at two decimals.
- `asks` is the act ledger: `acts` (every act-level alert, first line, with its `level`), `actions`, `levels` and `where`.
- `digest` holds a sentence per stage and locale, the ask pane's `prompts` and the `simple` paragraph.
- `sections` are the readouts enabled packs declare under `sections:`, such as the shipped `fire` and `surface-heat`.
- `events` is the alert events (see [Alerts](alerts.md)): the engine (`rules`, `shadow` or `events`), the button labels, the `open` events with `asking`, the `recent` ones and `sent_24h`.

### GET /issues/days
Access: open

Each issue hour by hour over several local days, by the same engine. `?days=` 1 to 90 (default 7) and `?locale=` `en`, `id` or `es`. For each issue: `distance`, `series` (room, yard, ring and region), `hours` (a title and tagline per hour), `provenance`, `per_day` (`date`, `over`, `read`, `of`) and `line`, plus the `events` of the window. Wire format `days-v0`.

### GET /issues/fixtures
Access: open

The snapshots this node ships: `{"fixtures": ["name", ...]}`.

### GET /issues/fixtures/{name}
Access: open

One shipped snapshot recomputed at the hour it was captured, which the dashboard reads with `?fixture=<name>`. 404 lists the names.

## Alerts and answers

The node asks and a person answers. Every client uses the same two routes, `GET /alerts` and `POST /actions`. Each answer is a row in the `actions` ledger, and ρ is counted from it.

### GET /alerts
Access: open

Alerts newest first, with the id `planetai act <id>` needs: `[{id, ts, rule_id, sensor_id, level, text, buttons, acted_at}]`. `buttons` is null, or the rows of buttons the rule asked with (`{text, value, stage, ask}` each, `text` and `ask` by locale). `?limit=` 0 to 1000 (default 50) and `?since_hours=` up to 2160 (0 is no bound). `acted_at` is the time of the first `acknowledged` or `acted` answer.

### GET /actions
Access: token

Every answer a person gave, newest first: `[{ts, alert_id, stage, actor, note, choice}]`, where `choice` is the value of the button pressed, or null. `?limit=` up to 5000 (default 500), `?stage=` one stage (`settings` gives the node's own settings rows), and `?events=1` adds the answers to alert events with their `event_id`.

> **Careful.** The handler checks no token of its own, so `BACKUP_TOKEN` and `ACT_TOKEN` read the household's notes too.

### POST /actions
Access: act

A person closes the loop. From loopback it needs no token; from anywhere else `ACT_TOKEN` or `ADMIN_TOKEN`, so someone in the house can answer without the admin key and a NAS's token cannot write ρ.

```json
{"alert_id": 12, "stage": "acted", "actor": "ibu wayan", "note": "closed windows"}
```

| `stage` | What the row does |
|---|---|
| `acknowledged` | Somebody saw it. Counts for ρ |
| `acted` | Somebody did the thing. Counts for ρ and closes the alert |
| `decided` | Somebody said what they would do. Moves nothing |

An alert event is answered with `event_id` in place of `alert_id`: `{"event_id": 3, "stage": "dismissed", "actor": "made", "note": "ran the AC instead"}`. Done is `acted`, Not now `acknowledged`, Doesn't fit `dismissed`. Any other stage, or both ids, is 400, and an unknown alert or event is 404.

An alert that asked with buttons takes `{"alert_id": 12, "choice": "good", "actor": "ibu wayan", "note": ""}`, where `choice` is the `value` of one of its buttons. The button sets the stage, and a `stage` sent beside it is ignored. A `choice` the alert did not offer is 400, and an alert older than 72 hours is 409 `this question has closed`. Each person's choice on an alert is one row: a repeat press writes nothing, and a later note from the same person replaces the earlier one. The node derives `measured` itself (see [`/rho`](#get-rho)). With `DECISION_REQUIRED=1`, an `acted` post is 409 until the alert has a `decided` row. `actor` is cut to 80 characters and `note` to 500. Returns `{"ok": true}`.

### POST /test-alert
Access: admin

Fires one act-level alert now through every channel, as `planetai test-alert` does. Returns `{"ok": true, "alert_id": <id>}`.

## Whether it worked

Only the node holds both the alert and the answer, so ρ is measured here.

### GET /rho
Access: open

The share of act-level alerts in the last 30 days that got an `acknowledged` or `acted` answer within 24 hours, over this node's alerts and its children's. See [rho](rho.md). Returns `{window_days, days_ago, alerts_act, acted, rho, median_minutes, funnel}`. `funnel` counts this node's own alerts by stage (`asked`, `acknowledged`, `acted`, `measured`), where an `acted` alert whose rule stayed silent for the next 48 hours counts as `measured`.

### GET /effect
Access: open

Per rule, how many acts were followed by the condition stopping, and how long recovery took. `?days=` up to 3650 (default 365). Returns `{window_hours: 48, days, rules: [{rule_id, acted, cleared, watch, hours, measured, already}]}`. `hours` is elapsed time and says nothing about cause.

## Reports

### GET /report/latest
Access: open

The last report the node wrote, sent or held: `{schema: "report-v0", id, ts, due_local, window_hours, depth, rung, text, sent, held_quiet, fallback_reason, note}`. Before the first, every key but `schema` and `note` is null.

### GET /report/bundle
Access: pull

Every number the node has about a window, the document a report is written from. `?hours=` up to 168 (0, the default, means `REPORT_EVERY`). Returns `meta`, `series`, `observations`, `now`, `alerts`, `open_act`, `sensors_quiet`, `rho`, `previous`, `cells`, `rules`, `facility`, `health` and a key per pack that adds a block.

### POST /report/now
Access: admin

Writes and sends a report now; the next scheduled one still happens. Returns `{id, text, depth, rung, sent}`.

## Context

What surrounds the node's own numbers: other people's stations, the forecast, the satellite record, the buildings around the address.

### GET /nearby
Access: open

The ring of other people's stations around this node, from what is stored, so the page never waits on someone else's server. The stations come from every enabled pack that declares `stations:` (here `bali-air-dispatch`, within `BAD_RADIUS_KM`) and reported in the last 24 hours. Returns `{ring, stations, lowest, p25, median, p75, highest, nearest_km, mine, mine_sensors, radius_km, attribution, mine_minus_ring}`, each `ring` row with its `km`, `pm25` and `reporting`. `?audit=1` also asks each pack's archive for a verdict per station.

### GET /forecast
Access: open

Official and model weather for this point, from `forecast-bmkg`, `forecast-om`, `forecast-cams`, `forecast-marine` and `forecast-gap`. `?hours=` 1 to 72 (default 24). Returns `{point, sources, hours, attribution, far_from_node, days, lines, openmeteo, schema}`, where `far_from_node` lists any source more than 10 km away (the sea is left out), `days` and `lines` are what [Next days](next-days.md) draws, and `schema` is `forecast-v0`.

### GET /earth
Access: open

What the earth packs hold for this node's square: `{node, enabled, years, bytes, latest, changes, frames, dir, imagery, png, lat, lon, radius_m, attribution, hint}`, from the AlphaEarth years, the land-change comparisons and the Sentinel-2 or Landsat frames. Empty until `planetai run earth fetch`, never an error; `hint` names the next command.

### GET /earth/change.png
Access: open

A land-change map, `?pair=YYYY_YYYY` (default the latest). 404 `no such land-change map: planetai run earth change`.

### GET /earth/year.png
Access: open

One year drawn from the embeddings in grey, `?year=` required. 404 `no frame for <year>: planetai run earth frames`.

### GET /earth/frame.png
Access: open

One year of real imagery, `?year=` required and `?source=` `sentinel` (default) or `landsat`. 404 names the years the node has.

### GET /place/geojson
Access: token

The buildings, uses, green and roads the place pack stored within `PLACE_RADIUS_M`, plus satellite footprints (`sat`), as `{type: "FeatureCollection", features, diag, center, radius_m}`. `?kinds=` (default `building,poi,green,road,sat`) and `?tolerance=` in degrees. Token only, because these are the exact footprints around the address.

## Maps and cells

H3 cells and the node's own map tiles, so a browser map computes no H3 and asks nobody else. Every `/geo/` route but `/geo/cell` is `token`, since a fine cell or a ring centred on the node gives away its point.

### GET /geo/grid
Access: token

The cells covering `?bbox=west,south,east,north` at `?res=`, one ring wider, and the node's own cell: `{res, may_leave, edge_m, node, cells_ll}`. A box of more than 2,500 cells is 422.

### GET /geo/cell
Access: open

One cell's facts, by `?id=` or by `?lat=`, `?lon=` and `?res=`. `?children=` adds finer rings and `?polar=1` distances and bearings from the node. Returns `{id, res, area_m2, edge_m, parent, may_leave, is_node, cells_from_node, ring}`; an untrusted caller gets none of the fields relative to the node.

### GET /geo/measure
Access: token

Great-circle metres along `?path=lon,lat;lon,lat;…` (2 to 200 points), with `?from_node=` and `?each=`. Returns `{legs_m, total_m, points}`.

### GET /geo/planet
Access: token

Every cell on the planet at `?res=` 0, 1 or 2 (default 2), as `{res, cells_ll}`.

### GET /geo/rings
Access: token

Circles round the node, `?km=` up to eight distances (default `2,5,15`). Returns `{rings: [{km, ring}]}`.

### GET /ground/meta
Access: open

Which of the node's map layers (`vector`, `drone`, `imagery`, glyphs, wind) are in `out/ground/`, with source, licence, size and the command that fetches each.

### GET /ground/{layer}/{z}/{x}/{y}
Access: open

One tile of the node's own map: `vector` (OpenStreetMap, gzipped), `drone` (OpenAerialMap) or `imagery` (Sentinel-2). 204 where there is no tile.

### GET /ground/glyphs/{font}/{span}
Access: open

Label fonts for the vector map, as MapLibre asks for them: `/ground/glyphs/Noto Sans Regular/0-255.pbf`.

### GET /ground/wind
Access: open

The forecast pack's Open-Meteo wind field over the node's square, hourly for the next day: `{source, licence, attribution, fetched, n, km, lats, lons, times, speed_kmh, from_deg, at_node}`. `speed_kmh[t][row][column]` runs south to north and west to east, and `from_deg` is where the wind comes from. 204 with `FORECAST_OPENMETEO=0`.

## Images and things

A capture is one picture with the facts a reading has: when, which cell, who, with what. The file lives in `CAPTURES_DIR`, the row in the database. These routes are on no allowlist and `BACKUP_TOKEN` opens none of them, and no picture goes into an export, an aggregate or a parent push. The file is cleaned of EXIF and GPS on arrival.

### POST /captures
Access: act

Adds one picture as a multipart form: `photo` (jpeg, png, heic or webp, up to 40 MB), and optionally `kind` (`microscope`, `phone`, `camera`, `drone` or `balloon`), `lat` and `lon` or a resolution-10 `cell`, `note`, `taken_at`, `actor`, and `describe=1`. GPS in the picture wins over `lat` and `lon`; with neither, the capture stands in the node's own cell. A picture already there answers `duplicate: true` and writes nothing. Returns `{"ok": true, "capture": <row>}`; 503 when `CAPTURES_DIR` is missing or not writable.

### GET /captures
Access: act

The images, newest first, each with `at`, the point a map draws it at. `?cell=` at any resolution, `?kind=`, `?limit=` up to 500 (default 50).

### PATCH /captures/{cid}
Access: act

Changes an image's `note`, `kind` or `meta`. `{"confirm": true, "actor": "<name>"}` confirms the model's findings and `{"findings": [...]}` replaces them with a person's list; both are 409 before the image is described.

### POST /captures/{cid}/describe
Access: act

Asks the image model (`EYES_MODEL`, in this machine's Ollama) about one image now and keeps its `analysis`: a summary and `findings` by class. The model is told never to describe or count people. With `SPECIES_MATCH=on` a plant or animal gets GBIF's `taxon` and whether the country's GRIIS checklist lists it as introduced. 409 when no image model is set, 503 when Ollama does not answer.

### DELETE /captures/{cid}
Access: admin

Deletes an image and its file, from loopback or with `ADMIN_TOKEN`. Returns `{"ok": true, "deleted": <id>}`.

### GET /captures/{cid}/file
Access: act

The picture itself; `?w=` up to 1024 answers a JPEG thumbnail.

### GET /species
Access: act

The species people here confirmed in images, per taxon, most counted first: `{cell, species: [{key, name, rank, class, count, images, cells}]}`. `?cell=` narrows it to one cell.

### GET /things
Access: admin

What this home keeps: `{things, classes, choices, summary: {things, idle, repair, offered}}`. Each thing has `class`, `name`, `count`, `used` (`weekly`, `monthly`, `yearly`, `never`), `condition` (`works`, `needs_repair`, `broken`), `offer` (`no`, `lend`, `give`), `capture_id` and `note`.

### POST /things
Access: admin

Adds a thing; `class` and `name` are required. Every change to the things rewrites `stock.<class>`, `idle.<class>` and `repair.<class>` as `private` readings on the `things:<node>` sensor, and nothing sends those. Returns `{"ok": true, "thing": <row>}`.

### PATCH /things/{tid}
Access: admin

Changes a thing's fields. Returns `{"ok": true, "thing": <row>}`.

### DELETE /things/{tid}
Access: admin

Deletes a thing.

### GET /offers
Access: public

What this home chose to lend or give: `{node, cell, contact, offers: [{id, class, name, condition, offer, count, ask}]}`, never a note, a photo or a place finer than the resolution-8 cell. `contact` and `ask` open the node's Telegram bot ([the bot](bot.md)). The offers are also in the daily export.

## What the node learned

None of this changes a rule or a setting. An agent, a request with `X-Agent`, reads the house's learnings only while every model stays home: `AGENT_PREFER=private` and no model at an address
outside your network.

### GET /learned
Access: admin

`{learnings, digests, checked}`. A learning's `kind` is `worked` (per act-level rule, acted against unanswered, net of the street, with a `verdict`), `usual` (the house's and the street's usual hours) or `asks` (how often a rule asks and is answered, with a `suggest`). Each has a `status`, a `statement` the node wrote from its `numbers`, and `for_whom`. Checked again once a day.

### GET /learned/place
Access: open

The holding `usual` learnings of scope `place`, the outdoor sensors' usual hours, for the doors' Wall. It holds nothing about the house.

### GET /learned/search
Access: admin

The diary and the learnings, searched: `?q=` words, `?scale=` `day`, `week`, `month` or `year`, `?limit=` up to 50 (default 12). Returns `{q, results}`. The node writes one digest for each completed day, week, month and year.

### GET /household
Access: admin

Who is in the house, as the household said: `older` (over 65), `under5`, `lungs`, `pregnant` and `outdoor` (works outdoors), each true or false. It sets `for_whom` in `/learned` and adds one line to a matching heat or air alert on Telegram. It changes no threshold.

### PUT /household
Access: admin

`{"people": {...}}`, with only those keys and only true or false. An agent may not write it.

## The Index contract

What the node computes for the Fab City Index, and what the network has registered as measurable.

### GET /cells
Access: open

The Index cells this node can compute, in the `fci-cells-v0` row shape. Domain cells come from the packs' `cells.yml`, and a pack cannot claim `live` before its `min_buckets` of hourly data exist. A `Governance|<Scale>` row appears after an act-level alert in the last 30 days, `partial` while fewer than 5 were answered.

```json
{"city": "bali", "cell": "Environmental|Community", "value": 18.4,
 "unit": "µg/m³ PM2.5 (24h mean, sensors in this node's custody)",
 "source": "planetai-node · pack:air-quality", "observed_at": "2026-10-20T08:35:02+00:00",
 "state": "live", "notes": "...", "registered": 2, "adapter": true, "reviewed": 2, "candidate": 1, "capable": 2}
```

`state` is `live`, `partial` or `mock`, and nothing downstream upgrades it. The last five fields are the registry's counts for the cell (see `/sources`).

### GET /sources
Access: open

The network's registry of what can be measured, a pinned copy of `awesome-fabcity-data` in `data/sources/`; at v0.91.0, pin `7bf12a4` with 284 entries. Filters `?pillar=`, `?scale=`, `?cell=`, `?pilot=`, `?wired=` and `?status=`, combined with AND. Returns `{registry, counts, count, sources}`, where `counts` gives every cell its `capable`, `reviewed` and `candidate` numbers (12, 17 and 55 over 19 cells at this pin). See [the source registry](sources.md). 503 when the registry is missing.

### GET /sources/{pillar}/{scale}/{slug}
Access: open

One registry entry, such as `economic/community/fablabs-io`.

### GET /packs
Access: open

The packs this node has loaded: each `pack.yaml` as parsed, with `id`, `path` and `kind` (`data` or `code`).

### GET /packs/all
Access: open

Every pack this node could run: each pack folder on its disk and each pack on the wild list that is not, under
`packs`, with `tier` (`core` or `wild`), `installed`, `on` (in `PACKS_ENABLED`, or that list is empty), `loaded`, and
`why` when it is not loaded (`switched off`, a code pack waiting, a `requires:` it does not meet, `not installed`).
Wild packs carry `source`, `commit`, `added` and `status`. `list` says whether the wild list was read (once an hour).

### GET /packs/preview?id=
Access: admin token

What installing a listed wild pack would bring, read from its `pack.yaml` at the commit it would be installed at:
`author`, `status`, `source`, `commit`, `code_url`, `kind`, `metrics`, `needs`, `pip`, `settings`, and `loads_here`
(null, or why it would not load). Writes nothing.

### POST /packs/install
Access: admin token; refused to a request carrying `X-Agent`

`{"id": "<listed id>", "commit": "<the commit /packs/preview returned>"}`. Writes one request to `out/requests/` for
`planetai packs pending` on the host, which installs that commit only if the wild list still gives it, then restarts
the app. 409 while another install runs, or when the pack is here already. `GET /packs/install` (admin token) says how
it is going: `idle`, `waiting` (with `stuck` after three minutes), `running`, `done` or `failed`, with the node's `line`.

## Federation

A child sends its parent hourly means and alert timestamps. Raw readings do not travel this way. See [federation](federation.md).

### GET /aggregates
Access: token

This node's hourly means, newest first, without `private` channels: `[{bucket, sensor_id, metric, mean, min, max, n}]`. `?hours=` up to 2160 (default 24).

### POST /aggregates
Access: children

A child pushes the hourly means of its own sensors, each row saying whether it is indoors.

```json
{"schema": "aggregates-v0", "node": "bayu-ungasan", "scale": "community",
 "rows": [{"bucket": "2026-10-20T07:00:00+00:00", "sensor_id": "sc-1234", "metric": "pm25",
           "mean": 18.4, "min": 12.0, "max": 25.1, "n": 12, "indoor": false}]}
```

The parent keeps each mean as one reading of sensor `<node>/<sensor_id>`, of kind `child`. Returns `{"accepted": <n>}`.

### POST /events
Access: children

A child pushes one row per alert it raised, timestamps only: `alert_id`, `rule`, `level`, `kind`, `raised_at`, `responded_at`, `acted_at`, `measured_at`. No text, actor or sensor travels. The parent counts them in its ρ. Returns `{"accepted": <n>}`.

## Open data and backups

### GET /export
Access: public

One day of this node as open data under CC BY 4.0, for `?day=YYYY-MM-DD`: hourly means, the Index cells, the first line of each alert, ρ and, with the things pack on, the offers. Never raw readings, `private` channels or secrets, and the node's own sensors are named by role (`indoor-1`). `backup.sh` writes it every night to `exports/<node>/YYYY-MM-DD.json`.

```json
{"schema": "export-v0", "node": "bayu-ungasan", "lat": -8.825, "lon": 115.159, "day": "2026-10-19",
 "version": "v0.91.0", "licence": "CC BY 4.0",
 "hourly": [{"t": "2026-10-19T00:00:00+08:00", "sensor": "indoor-1", "metric": "pm25", "mean": 11.2, "n": 12}],
 "alerts": [], "cells": [], "rho": {}, "offers": []}
```

### GET /exports
Access: open

The daily exports on disk: `[{node, name, bytes}]`.

### GET /exports/{node}/{name}
Access: open

One export file.

### GET /backups
Access: pull

The database dumps, newest first, so a NAS can fetch the ones it lacks: `[{name, bytes, mtime}]`.

### GET /backups/{name}
Access: pull

One dump as `application/gzip`.

## Settings

### GET /settings
Access: public

Every runtime setting with its group, label, help and value, the bootstrap keys, and the keys the installed packs declare. Secrets are always masked, and without the admin token so is every value outside the public set (`settings.PUBLIC`). At `SHARE_LEVEL=off` an untrusted caller sees only `UI_LAYOUT` and `SHARE_LEVEL`. Returns `{unlocked, runtime, bootstrap}`; each row has `key`, `group`, `label`, `secret`, `restart`, `help`, `value`, `set`, `source`, `choices`, `default`, `outward` and `runs_code`, and a pack's key also has `pack`.

### PUT /settings
Access: admin

`{"KEY": "value", ...}` sets runtime settings and pack keys, in effect within about 20 seconds; a blank value goes back to `.env`. An unknown key or a value outside its choices is 400. Each call writes a `settings` row to the ledger under the `X-Agent` name (default `gui`). Returns `{changed, by, effective_within_s}`.

### GET /settings/phone
Access: admin

`{"act": <ACT_TOKEN>}`, which Set up draws as the QR code a phone unlocks with.

### GET /settings/raw
Access: admin

Every setting unmasked, for the node's own processes; `BACKUP_TOKEN` does not open it. Never call it from a browser.

## The agent surface

### /mcp
Access: admin

The MCP server over streamable HTTP at exactly `/mcp`, with `Authorization: Bearer <ADMIN_TOKEN>` on every call. Its tools call the API back on `http://127.0.0.1:8080`, as loopback. They are `status`, `health_check`, `sensors`, `context`, `readings`, `report_latest`, `report_now`, `report_bundle`, `learned`, `history`, `alerts`, `act`, `settings_get`, `settings_set`, `packs`, `cells`, `issues`, `series`, `export_day`, `run_pack_script` and `maintenance`. `act` refuses an empty note or a placeholder such as `done`. The [MCP page](mcp.md) describes each.

## The ask pane

The dashboard's pane asks the model in Set up → Model about what the page shows, and keeps nothing it was asked or answered. It changes nothing either: a write comes back as a proposal for the person to press. See [Ask](ask.md).

### GET /ask/status
Access: open

Which model the pane asks first, where it runs and whether it answers: `{model, rung, where, host, running, why, rungs, leaves, tools, stored}`. `leaves` is true when an online model is in the order. 404 when no model is set up, with the tag `planetai agent local` would pull.

### POST /ask
Access: open

One answer, streamed as `text/event-stream`. Takes `{messages, view, mode, focus?, prompt?}`, at most 24 messages. The node builds the model's context from `/issues` with no coordinate, sensor name or id in it, and `prompt: wall` builds the Wall's public context instead and offers the model no tools, so it answers from that context without thinking. The model reads `learned` only for the admin or act token or this machine. The events are `token`, `tools`, `retry`, `proposal`, `done` and `error`. 404 when no model is set up.

### GET /docs/search
Access: open

This documentation searched without a model, `?q=` of 2 to 200 characters: the whole query as a phrase first, then the sections that hold most of its words, a rare word weighing more than a common one. Returns at most 20 `{page, anchor, title, snippet}`.

## Wire formats

Each document that travels between nodes names its format in `schema`: `issues-v0`, `export-v0`, `report-v0`, `aggregates-v0`, `events-v0`, `days-v0` and `forecast-v0`. A receiver never refuses on it: an unknown value is logged once and the fields it knows are read.

## What the node calls out

| To | When | What travels |
|---|---|---|
| `POST {PARENT_API_URL}/aggregates` | Hourly, with a parent set | The last 2 hours of hourly means of its own sensors, with `PARENT_TOKEN` |
| `POST {PARENT_API_URL}/events` | Hourly, after an alert in the last 36 hours | Alert timestamps |
| Telegram | Each alert at or above `ALERT_LEVEL`, each report, once per newer release, and `getMe` once a day for the bot's name | The message, with `TELEGRAM_BOT_TOKEN` |
| `planetai.fab.city/node0/get/VERSION` | Hourly, unless `UPDATE_CHECK=off` | Nothing about the house |
| GitHub's `registry.json` | Hourly, unless `UPDATE_CHECK=off` | Nothing about the house |
| GBIF | With `SPECIES_MATCH=on` and the eyes pack on: each new scientific name, and weekly the country's checklist and the record counts for the seven cells | A name, a country, seven cells |
| `POST {RETICULUM_URL}/send` | Each act-level alert | The alert text |
| MQTT | Each act-level alert (`MESH_ALERTS=1`), Home Assistant discovery (`HA_DISCOVERY=1`) | The alert's first line, discovery and state topics |

The sources the node polls are on the [sensors page](sensors.md).

## Where this leads

The [schema page](schema.md) says what each table and view holds. [Federation](federation.md) points a child at a parent, and [MCP](mcp.md) puts an agent on the node.
