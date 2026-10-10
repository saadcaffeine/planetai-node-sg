# HTTP API
<!-- checked: v0.80.10 -->

Every node exposes the same API on port 8080. The dashboard, the `planetai` command, the MCP tools, a NAS pulling backups, Home Assistant and a parent node are all clients of it, and none of them has a private path in. A request either carries a token as `Authorization: Bearer <token>` or carries nothing, and a request carrying nothing is judged by the `SHARE_LEVEL` setting. The container publishes `${APP_PORT:-8080}:8080` on every host interface; Postgres is published on `127.0.0.1:5432` only. There is no TLS on the node itself: the tailnet encrypts the hop, and the [sharing page](sharing.md) says what to do on a network that is not a tailnet.

This page was read from the code at v0.80. Where an older document disagrees, the code wins.

## Access rules

Two middlewares run before any handler. The first registered checks `/mcp` against `ADMIN_TOKEN`, and the second passes `/mcp` straight through. Everything else is checked by the second. A request is *trusted* when it comes from loopback or carries any of the four node tokens, and a trusted request reaches every handler. An untrusted request is looked up against the allowlist for the current `SHARE_LEVEL` and refused with 403 if its path is not on it. The handler then applies its own token check, if it has one. The pages on this site name the result with one of these classes.

| Class | Who is answered |
|---|---|
| `public` | On the `off` allowlist. Answers anyone, at every `SHARE_LEVEL`, with no token. |
| `open` | On the `open` allowlist only. Without a token, answers only when `SHARE_LEVEL=open`. Always answers loopback or any node token. |
| `token` | On neither allowlist. Answers loopback or a request carrying any of the four node tokens (`ADMIN_TOKEN`, `BACKUP_TOKEN`, `AGGREGATE_TOKEN`, `ACT_TOKEN`); then the handler's own check, if any. |
| `admin` | The handler requires `ADMIN_TOKEN`, whatever the allowlists let through. |
| `pull` | `token`, then the handler requires `ADMIN_TOKEN` or `BACKUP_TOKEN`. The read-only token for a NAS. |
| `act` | `token` at the middleware. Loopback then needs nothing more; from anywhere else the handler requires `ACT_TOKEN` or `ADMIN_TOKEN`. |
| `children` | `token`, then the handler requires `AGGREGATE_TOKEN`. What a parent demands of a child. |

The `off` allowlist (the default) is exactly: `/`, `/ui`, `/health`, `/llms.txt`, `/settings`, `/export`, `/presence`, and any path under `/static/`.

The `open` allowlist is the `off` list plus 27 paths: `/stats`, `/sensors`, `/observations`, `/alerts`, `/series`, `/sparks`, `/rho`, `/cells`, `/packs`, `/trust`, `/nearby`, `/forecast`, `/earth`, `/earth/change.png`, `/earth/year.png`, `/earth/frame.png`, `/report/latest`, `/readings`, `/reach`, `/shape`, `/effect`, `/history`, `/exports`, `/sources`, `/ask`, `/ask/status`, `/docs/search`. It also takes any path under `/static/`, `/exports/`, `/issues` or `/sources/`. That is 34 exact paths and 4 prefixes in all.

A `SHARE_LEVEL` value that is neither `off` nor `open` is treated as `off`. The allowlist matches the path whatever the method, so it governs writes as well as reads. `POST /readings` shares its path with `GET /readings`, so at `SHARE_LEVEL=open` an anonymous post gets past the middleware and is refused by the handler with 401. `PUT /settings` shares its path with `GET /settings`, which is on the `off` list, so the same happens at every level. `/actions` is on neither list, so an anonymous `POST /actions` or `GET /actions` is refused by the middleware at both levels. A path the node has no route for is refused with 403 too, not 404, when the caller is untrusted.

**How a token travels.** In the `Authorization` header only, as `Bearer <token>`. There is no query parameter and no `X-Token` form. The node strips one `Bearer `, then compares the rest against every candidate token in constant time, without returning early, so the time taken does not say which token matched. `ADMIN_TOKEN` is read from the environment (`.env`). The other three come from settings, which the dashboard may overlay on `.env`. An optional `X-Agent` header names the caller: `PUT /settings` writes it into the `actions` ledger and defaults it to `gui`.

**What loopback means.** The peer address of the socket, never a header: `X-Forwarded-For` is not read and uvicorn runs without `--proxy-headers`. Inside Docker, loopback is true for the node's own MCP tools (they call `http://127.0.0.1:8080`) and for a shell inside the container. It is false for a browser on the machine that hosts the node, which arrives as the Docker bridge gateway. On a Docker that forwards through a VM, a LAN client arrives as the gateway too, so trusting it would trust the whole network. A browser on the host is treated like any other client on the network and must carry a token or be let in by `SHARE_LEVEL=open`.

**The refusal shapes.** The middlewares answer with `{"error": ...}`. The 403 from the share check has two endings, and the node picks the one that is true for the path asked:

- A path that `SHARE_LEVEL=open` would answer: `{"error": "this node is set to SHARE_LEVEL=off, so /alerts answers only this machine or a request carrying a token. Set SHARE_LEVEL to open in the dashboard's Set up view to let anything on your network read it."}`
- A path no level answers: `{"error": "this node is set to SHARE_LEVEL=off, so /actions answers only this machine or a request carrying a token. No share level opens this one, so it always needs a token from anywhere but the node itself."}`
- 401 from `/mcp`: `{"error": "the agent surface needs Authorization: Bearer <ADMIN_TOKEN>"}`.

The level and the path in the 403 are filled in from the request.

Handlers answer with FastAPI's default `{"detail": "..."}`. The handler checks and their texts:

| Check | Missing on the node | Wrong or absent in the request |
|---|---|---|
| `admin` | 403 ``ADMIN_TOKEN is not set in .env; run `planetai ui` to create one`` | 401 `bad or missing admin token` |
| `pull` | 403 `no BACKUP_TOKEN or ADMIN_TOKEN set on this node` | 401 `bad or missing token` |
| `act` | 403 ``no ACT_TOKEN or ADMIN_TOKEN set on this node; run `planetai ui` to create one`` | 401 `closing a loop from off this machine needs Authorization: Bearer <ACT_TOKEN>` |
| `children` | 403 `this node accepts no children: set AGGREGATE_TOKEN in .env and give it to them` | 401 `bad or missing Authorization: Bearer <AGGREGATE_TOKEN>` |

Timestamps are ISO 8601 strings with an offset. A timestamp the node read from the database carries the offset of `NODE_TZ`, because every connection sets the session time zone from it; one the node stamped itself (`last_poll`, `generated`, `as_of`, `observed_at`) is UTC. A reader the node does not know (not this machine, no token) never gets a position finer than the node's resolution-8 cell: `/health` and `/export` carry the centre of that cell, and so do the household's own sensors (`custody`) in `/sensors` and `/stats`; other sensors there are rounded to 3 decimals. A trusted caller gets `/health` at 3 decimals and the other two unrounded. `/forecast`, `/earth` and `/place/geojson` are unrounded and are never readable without a token or `SHARE_LEVEL=open`.

## Status

What a screen asks first: is the node up, which version, which cell.

### GET /health
Access: public

What every screen in the house polls. Answers at every `SHARE_LEVEL` and never makes an outbound request of its own.

Returns one object with: `ok` (true once a poll has run), `node`, `version` (`NODE_VERSION`, or `?`), `schema` (the latest applied schema version; `unreachable (the app cannot log in to its database — planetai doctor says why)` when the database is there but refuses the app — a wrong password after a reinstall over an earlier volume, or the database down — and `pre-0.4 (run ./update.sh)` only when the node predates the `schema_version` table), `uptime_s`, `lat` and `lon` (the centre of the node's resolution-8 cell for an untrusted caller, 3 decimals for this machine or a token), `position` (`cell` or `point`, saying which), `city`, `polls`, `last_poll`, `last_error`, `ingested`, `errors` (a map of loop name to its last error line), `bootstrap` (only if the first-start bootstrap ran in this process), `locale` (`ALERT_LOCALE`), `tz` (`NODE_TZ`), `cell` (`{id, res, edge_m, caption}` for the node's H3 cell at resolution 8, or null before setup), `docs` (the documentation's URL), `mcp` (`/mcp`), `llms` (`/llms.txt`), `mesh` (`{root_topic, gateway, packets, last}`, only when `MQTT_HOST` is set), `reticulum` (`{ok, address, destinations, announce_s, announcing, peers, last}`, only when `RETICULUM_URL` is set) and `release` (`{latest, current, newer, checked, asked}`, what the daily check against planetai.fab.city found earlier, not a request made now, plus `error` if its last attempt failed; only with `UPDATE_CHECK=on` and once the check has run). `newer` is true when `latest` is a later release than the one `current` is at; a git checkout ahead of a tag, such as `v0.75.7-14-gafc298a`, is at that tag's release.

```json
{"ok": true, "node": "bayu-ungasan", "version": "v0.73", "schema": "0.51", "uptime_s": 86121,
 "lat": -8.825, "lon": 115.159, "position": "cell", "city": "bali",
 "polls": 287, "last_poll": "2026-09-22T08:35:02+00:00", "last_error": null, "ingested": 41230,
 "errors": {}, "locale": "id", "tz": "Asia/Makassar",
 "cell": {"id": "...", "res": 8, "...": "..."},
 "docs": "https://planetai.fab.city/docs/", "mcp": "/mcp", "llms": "/llms.txt"}
```

### GET /llms.txt
Access: public

What this node is for and where its routes are, as plain text for an agent handed the node's address: the
purpose, the version, the read routes, `/mcp` and what it needs, and the documentation's URLs. Answers at every
`SHARE_LEVEL` and says nothing about the house. The repository's own `llms.txt`, for agents working on the
code, stays on GitHub.

### GET /presence
Access: public

What this node is willing to announce about itself on Reticulum. Public at every level on purpose: the Reticulum bridge is another container with no token and reads this to know what to announce.

Returns `{"enabled": false}` unless `RETICULUM_PRESENCE=1`. When enabled: `{enabled: true, node, cell, res, version, kind}`, where `cell` is the node's cell coarsened to resolution `res` (`RETICULUM_PRESENCE_RES`, default 3, clamped to 0..6; resolution 6 is the finest allowed) and `kind` is `NODE_KIND` or null.

### GET /
Access: public

### GET /ui
Access: public

The dashboard: `app/static/index.html`, one file, no build step, sent with `cache-control: no-cache, must-revalidate` so a wall screen follows the version after `planetai update`. With `?layout=doors` it sends `app/static/doors.html` instead, the five doors on trial, which read the same routes with the same token. A stub page if the file is missing. Hidden from the OpenAPI schema.

### GET /static/{name}
Access: public

The files the dashboard cannot inline: the ground SVG, the fonts, the renderer's script and stylesheets, the drawing library (Observable Plot and d3), the signs, the kilometre-cells JSON, the learn-mode quotes, the map ground's MapLibre and deck.gl, and the five doors' scripts, their world coastline and the documentation they draw the API from. Named one by one; a name that is not on the list is 404 `no such asset`. Sent with the same no-cache header.

| Name | Type | Default | Meaning |
|---|---|---|---|
| `name` | path | required | One of `node-ground.svg`, `jetbrains-mono-latin.woff2`, `FunnelSans-VariableFont_wght.ttf`, `Figtree-VariableFont_wght.ttf`, `Figtree-Italic-VariableFont_wght.ttf`, `dashboard.js`, `dashboard.css`, `d3.min.js`, `plot.umd.min.js`, `planetai-theme.css`, `tokens.css`, `signs.svg`, `kilometre-cells.json`, `learn.json`, `maplibre-gl.js`, `maplibre-gl.css`, `deck.gl.min.js`, `world-land-110m.json`, `docs_site.json`, and `doors-<name>.js` for `load`, `nodegeo`, `core`, `fig`, `now`, `placemap`, `place`, `data`, `flow`, `wallmap`, `wall`, `node` and `setup` |
| `variant` | string | `dark` | Register for `node-ground.svg`; anything but `paper` is treated as `dark` |

`node-ground.svg` is drawn live from `NODE_LAT` and `NODE_LON` when they are set, so the hero shows this node's own cell. Without coordinates the shipped file is served. `learn.json` holds the quotes `tools/build_learn.py` cuts out of this site for the dashboard's learn mode.

### GET /briefing
Access: token

A 301 redirect to `/report/latest`, kept for a dashboard left open in a browser through the update that removed the briefing in v0.38. Takes and ignores `kind`. Hidden from the OpenAPI schema.

> **Gap in v0.80.10.** `/briefing` is on neither allowlist. A stale dashboard with no token is refused with 403 by the middleware before it can be redirected, at both levels. The route works as intended only for loopback or a request with a token.


### GET /machine
Access: token

The machine under the node, as its containers see it: `arch`, `system`, `cores`, `load` (1, 5 and 15 minutes), `cpu_busy_pct` (sampled over a quarter second), `memory` (`total_bytes`, `available_bytes`, swap), `container_memory` (the app container's cgroup limit and use, null without one), `temperatures` (each thermal zone the system gives, empty without one), `uptime_s`, `python` and `database` (Postgres version, start time, connections). Read from `/proc` and `/sys`: on Linux that is the machine, on macOS the container engine's virtual machine, which `seen_as` says. Nothing is estimated.

### GET /storage
Access: token

How much room this node takes and how long what is left lasts: `database_bytes`, `readings`, `readings_last_7_days`, `bytes_per_reading` (the readings table with its indexes, per row), `growth_bytes_per_day` (the last seven days' readings times that), `out_bytes`, `exports_bytes`, `backups` (`bytes`, `dumps`, `keep_days` from `BACKUP_KEEP`, `bytes_when_full`), `disk` (the disk under `out/` as the container sees it: `total_bytes`, `used_bytes`, `free_bytes`) and `days_left`, the free space less what the backups will still take, divided by the daily growth; null with no growth to go on. Nothing is pruned, so the readings are what grows. The database's own disk is the container engine's: the same disk on Linux unless `DATA_DIR` moves it, the engine's virtual disk on macOS. `planetai doctor` checks the host's free space.

## Sensors and readings

These are the routes a screen, a script or a spreadsheet builds against to read what the node has measured: the sensors, their raw readings, hourly means, and how long the record is.

### GET /sensors
Access: open

Every sensor this node reads, its position, and where its numbers come from. One row per sensor with `sensor_id`, `source`, `name`, `lat`, `lon`, `indoor`, `local`, `custody`, `kind`, `scale`, `cadence`, `meta`, ordered by custody, then local, then name. The columns are named rather than `SELECT *`, so a column added to the table stays private until someone lists it here.

For a caller that is neither loopback nor carrying a token, `lat` and `lon` are the centre of the resolution-8 cell for the household's own sensors (`custody`) and rounded to 3 decimals for every other row, and `meta` is cut to the provenance keys `licence`, `attribution`, `model`, `dataset`, `network`, `note`, `corrected` (null if none remain). That drops a unit's `host`, `firmware`, `mesh_node`, `gateway`, `channel`, `root_topic` and `topic`. A row with `kind = 'facility'` (a fab lab the `make` pack stored) keeps ten more keys, because they describe somebody else's published building and not this household: `slug`, `capabilities`, `kind_name`, `city`, `country_code`, `distance_km`, `url`, `registry_slug`, `snapshot`, `fetched`. A trusted caller gets the full rows.

### GET /readings
Access: open

Raw readings, newest first.

| Name | Type | Default | Meaning |
|---|---|---|---|
| `sensor_id` | string | any | Only this sensor |
| `metric` | string | any | Only this metric |
| `limit` | int | 200 | 1..10000 |

Returns a list of `{ts, sensor_id, metric, value}`.

### POST /readings
Access: admin

A contributor on the LAN (a phone, a DIY pod) posts raw readings. The sensor is upserted as `local=TRUE`; on conflict only `lat`, `lon` and `indoor` are updated. Admin token because a posted reading becomes a local sensor whose values fire act-level alerts and enter live cells. The path is on the `open` list, so at `SHARE_LEVEL=open` a post with no token reaches this handler and gets 401 `bad or missing admin token`.

Body:

```json
{"sensor": {"sensor_id": "phone-abc", "source": "mobile", "name": "kitchen phone",
            "lat": -8.827, "lon": 115.157, "indoor": true, "meta": {}},
 "readings": [{"ts": "2026-09-22T08:30:00+00:00", "metric": "pm25", "value": 12.3}]}
```

`sensor.sensor_id` is required (422 `sensor.sensor_id is required` otherwise). `source` defaults to `contributor`, `name` to the id, `indoor` to false. Each reading needs `metric` and `value`; `ts` defaults to now. A duplicate `(sensor_id, metric, ts)` is ignored. Returns `{"accepted": <number of readings in the body>}`.

### GET /stats
Access: open

Rolling statistics per sensor and metric over the last 24 hours, sensors only (`kind = 'sensor'`). This is the `stats` view: `sensor_id`, `metric`, `indoor`, `local`, `kind`, `scale`, `lat`, `lon`, `name`, `last`, `last_ts`, `silent_minutes`, `mean_15m`, `mean_1h`, `mean_24h`. Ordered local first, then sensor and metric. Slow sources are in `/observations`.

Positions follow `/sensors`: for a caller that is neither loopback nor carrying a token, `lat` and `lon` are the centre of the resolution-8 cell for the household's own sensors and rounded to 3 decimals for every other row. Before v0.73 this route handed every reader at `SHARE_LEVEL=open` the positions `/sensors` had rounded (#113).

### GET /observations
Access: open

The latest value per slow-moving source and metric: a city statistic, a model point sample, a survey. The `observations` view: `sensor_id`, `metric`, `value`, `ts`, `name`, `kind`, `scale`, `local`, `cadence`, `meta`, for every sensor whose `kind` is not `sensor`. Ordered by scale, sensor and metric.

### GET /trust
Access: open

One row per local sensor, for the dashboard's trust card and the agent's health check, computed once here so the two never drift from `packs/trust/rules.yml`.

Returns a list of `{sensor_id, name, coverage_7d, frozen_channels, age_hours}`. `coverage_7d` is the percentage of the last 168 hourly buckets its comparable ambient channels reported in. `frozen_channels` counts channels flat for 6 or more of the last 24 hours, still flat in the latest bucket, while the kit itself still produced raw readings in the last 2 hours. `age_hours` is the time since its first reading, so a value under 168 explains a low coverage without a fault.

### GET /history
Access: open

Every reading of one metric from one sensor, oldest first. For series that are not hourly: a yearly building count, a monthly refresh.

| Name | Type | Default | Meaning |
|---|---|---|---|
| `sensor_id` | string | required | The sensor |
| `metric` | string | required | The metric |
| `limit` | int | 500 | 1..5000 |

Returns a list of `{ts, value}`.

### GET /series
Access: open

Hourly means as aligned arrays: local indoor sensors, everything outdoor (yours and the references), and the model (`cams-point`, metric `<metric>_model`).

| Name | Type | Default | Meaning |
|---|---|---|---|
| `metric` | string | `pm25` | The metric |
| `hours` | int | 24 | 1..168 |

Returns `{metric, hours, buckets, indoor, outdoor, model}`; the four arrays have one entry per bucket, null where there is no data.

### GET /sparks
Access: open

Per-sensor hourly means on the same buckets.

| Name | Type | Default | Meaning |
|---|---|---|---|
| `metric` | string | `pm25` | The metric |
| `hours` | int | 24 | 1..168 |

Returns `{hours: [bucket, ...], series: {sensor_id: [mean or null, ...]}}`; the buckets travel with the values so a trace can draw its own time axis.

### GET /reach
Access: open

How far back this node's own record goes, per kind of source, so a page drawing years of satellite record beside a node switched on last week can say where the node's line starts. Read from `readings_1h`, the hourly means every chart is drawn from.

Returns a list of `{kind, oldest, newest, buckets, sources, days}`, one per `sensors.kind`, ordered by kind. `sources` is the number of distinct sensors; `days` is `newest - oldest` rounded to whole days.

### GET /shape
Access: open

The day this place usually has: one mean per local hour of day, over the whole record, indoor apart from outdoor. Only this node's own sensors (`local`) count. The hours are local because every connection sets the session time zone from `NODE_TZ`.

| Name | Type | Default | Meaning |
|---|---|---|---|
| `metric` | string | `pm25` | The metric |

Returns `{metric, days, first, last, hours, windows}`. Each `hours` entry is `{hour, indoor, outdoor, n}`, with `n` the number of hourly means pooled into it. `days` is the number of distinct local days this node's own sensors have for the metric. `windows` says what that record can support, decided here so the page never draws a pattern the node has not seen: `day` is true from 7 days, `week` from 14, `month` from 60, `year` from 365.

> **Careful.** `/shape` is on the `open` list. At `SHARE_LEVEL=open` a caller with no token reads the hour-by-hour indoor means of this house's own sensors.

## Context

What surrounds the node's own numbers: other people's stations, the weather forecast, the satellite record and the buildings around the address.

### GET /nearby
Access: open

The ring: other people's stations around this node, and where this node sits inside it. Reads only what is stored, so the dashboard never waits on someone else's server. In v0.80 the ring is Bali Air Dispatch stations only (`source = 'baliairdispatch'`), within `BAD_RADIUS_KM`, that reported in the last 24 hours.

| Name | Type | Default | Meaning |
|---|---|---|---|
| `audit` | bool | false | Also call the archive and return a verdict for every station it lists, the same answer `planetai run nearby stations` prints |

Returns `{ring, stations, lowest, p25, median, p75, highest, nearest_km, mine, mine_sensors, radius_km, attribution, mine_minus_ring}`. Each `ring` row is `{sensor_id, name, lat, lon, indoor, network, km, pm25, silent_minutes, last_ts, reporting}`, nearest first; `reporting` is true when the station spoke in the last 120 minutes. `mine` is the mean of this node's own outdoor sensors and `mine_minus_ring` the difference from the ring's median, or null. With `?audit=1` the response also carries `audit: [{station_id, name, network, km, verdict}]`, or `audit_error` if the archive did not answer.

### GET /forecast
Access: open

Official and model weather for this point: wind, expected rain, and when the forecast was issued. Context for reading the node's own air. The node fetches the forecast and makes none of its own.

| Name | Type | Default | Meaning |
|---|---|---|---|
| `hours` | int | 24 | 1..72 hours ahead |

Returns `{point: {lat, lon}, sources: [{sensor_id, name, lat, lon, issued, fetched, km_from_node}], hours: [{ts, source, <metric>: value, ...}], attribution, far_from_node}`. The sources are the forecast sensors `forecast-bmkg`, `forecast-om` and `forecast-gap`. `far_from_node` lists any source more than 10 km away as `{sensor_id, km}`, or is null. `point` is the node's position, unrounded.

### GET /earth
Access: open

What the earth pack has: the years of AlphaEarth embeddings cached for this node's square, the comparisons it computed from them, and the frames the earth-engine pack fetched. Empty until `planetai run earth fetch`, and never an error, so the card can say what is missing.

Returns `{node, enabled, years, bytes, latest, changes, frames, dir, imagery: {sentinel, landsat, credit}, png, lat, lon, radius_m, attribution, hint}`. Each entry in `changes` is the pack's own JSON with a `png_url` added (`/earth/change.png?pair=<a>_<b>`). `frames` are the years with a `year_<year>.png`. `imagery.sentinel` and `imagery.landsat` are the years with real satellite frames, kept separate because a model output is not a photograph. `radius_m` is `EARTH_RADIUS_M` (default 5000). `hint` says the next command when something is missing. `lat` and `lon` are unrounded.

### GET /earth/change.png
Access: open

A land-change map the earth pack drew. The file name comes from the pack's own JSON, never from the request.

| Name | Type | Default | Meaning |
|---|---|---|---|
| `pair` | string | latest | `YYYY_YYYY`, one of the comparisons this node computed |

Returns a PNG, or 404 `no such land-change map: planetai run earth change`.

### GET /earth/year.png
Access: open

One year of the square as the earth pack drew it from the embeddings: a model's description flattened to grey, not a photograph.

| Name | Type | Default | Meaning |
|---|---|---|---|
| `year` | int | required | 1900..2200 |

Returns a PNG, or 404 `no frame for <year>: planetai run earth frames`.

### GET /earth/frame.png
Access: open

One year from the other record: a Sentinel-2 or Landsat annual median fetched through Earth Engine, brightness-matched across years. The file comes from a glob of `out/`; neither parameter reaches the filesystem as a path.

| Name | Type | Default | Meaning |
|---|---|---|---|
| `year` | int | required | 1972..2200 |
| `source` | string | `sentinel` | `sentinel` or `landsat` |

Returns a PNG, or 404 naming the years this node has, or the command that fetches them when it has none.

### GET /place/geojson
Access: token

The geometry the place pack stored: OpenStreetMap buildings, uses, green and roads within `PLACE_RADIUS_M` of the node, and the satellite footprints (`sat`) with no mapped building within 3 m, as one FeatureCollection for the dashboard's plan. Empty until the place pack has run, and never an error.

| Name | Type | Default | Meaning |
|---|---|---|---|
| `kinds` | string | `building,poi,green,road,sat` | Which feature kinds to include |
| `tolerance` | float | 0.00002 | Simplification tolerance in degrees, 0.000001..0.01 |

Returns `{type: "FeatureCollection", features, diag: {tables, rows, error, hint}, center: [lon, lat], radius_m}`. Each feature's properties are `{kind, category, name, building, highway}`, or `{kind: "sat", confidence}` for a satellite footprint.

This route is on no allowlist at any level: loopback or a token, and nothing else. It is the exact building footprints and roads around the address, drawn, and unlike a coordinate there is no rounded version of it that is safe to hand to the network. The dashboard's plan card is therefore empty on a screen with no token, and says so.

### GET /geo/grid
Access: token

The H3 cells covering a box at one resolution, one ring wider so a drawn grid runs off the frame, and the node's own cell at that resolution. The map workbench draws these instead of computing H3 in the browser.

| Name | Type | Default | Meaning |
|---|---|---|---|
| `bbox` | string | required | `west,south,east,north` in degrees |
| `res` | int | required | Resolution, 0..15 |

Returns `{res, may_leave, edge_m, node, cells_ll}`. `node` and each `cells_ll` row are `[id, lat, lng, …]`, the shape `/issues` geometry uses. `may_leave` is true at resolution 6 and coarser. A box that would hold more than 2,500 cells is refused with 422, not cut short.

### GET /geo/cell
Access: token

One cell's facts, named by `id`, or by `lat`, `lon` and `res`.

| Name | Type | Default | Meaning |
|---|---|---|---|
| `id` | string | none | An H3 cell id |
| `lat`, `lon`, `res` | float, float, int | none | The cell containing that point at that resolution, when there is no `id` |
| `children` | int | none | A finer resolution: adds `children_res`, `children_n`, and up to 400 child rings as `children_ll` |
| `polar` | bool | false | Adds each ring as distance and bearing from the node: `ring_polar`, and `children_polar` with `children` |

Returns `{id, res, area_m2, edge_m, parent, may_leave, is_node, cells_from_node, ring}`. `cells_from_node` counts grid steps from the node's own cell at the same resolution, or is null when h3 cannot walk that far. A polar row is `[id, metres, bearing, …]`, bearing in degrees clockwise from north.

### GET /geo/measure
Access: token

Distances along a path, great-circle, in metres.

| Name | Type | Default | Meaning |
|---|---|---|---|
| `path` | string | required | `lon,lat` points separated by `;`, 2 to 200 of them |
| `from_node` | bool | false | Start the path at the node |
| `each` | bool | false | Also give every later point's distance and bearing from the first |

Returns `{legs_m, total_m, points}`, and `each: [{m, deg}]` with `each`.

### GET /geo/planet
Access: token

Every H3 cell on the planet at resolution 0, 1 or 2 (122, 842 or 5,882), as `cells_ll` rows: the world grid a map of nodes is drawn on.

| Name | Type | Default | Meaning |
|---|---|---|---|
| `res` | int | 2 | 0, 1 or 2 |

Returns `{res, cells_ll}`.

### GET /geo/rings
Access: token

Circles round the node, as `[lat, lng]` rings.

| Name | Type | Default | Meaning |
|---|---|---|---|
| `km` | string | `2,5,15` | One to eight distances, each above 0 and at most 500 |

Returns `{rings: [{km, ring}]}`.

### GET /ground/meta
Access: token

What the node holds of its own map in `out/ground/`: for each layer (`vector`, `drone`, `imagery`) its source, licence, attribution, tile count, bytes and fetch time, which layers are on disk (`on_disk`, plus `glyphs` and `wind`), and the command that fetches each one, the wind field's included. Never an error.

### GET /ground/{layer}/{z}/{x}/{y}
Access: token

One tile of the node's own map, XYZ addressed. `layer` is `vector` (OpenStreetMap vector tiles from Protomaps' build, served gzipped with `Content-Encoding: gzip`), `drone` (OpenAerialMap mosaics, PNG) or `imagery` (this node's Sentinel-2 composite, PNG). `y` may carry an extension. Answers 204 where the node holds no tile, which a map reads as empty ground.

### GET /ground/glyphs/{font}/{span}
Access: token

The label fonts the vector map draws names with (Noto Sans, OFL), one face and one range of 256 per request, as MapLibre asks for them: `/ground/glyphs/Noto Sans Regular/0-255.pbf`. 204 for a range the node did not fetch.

### GET /ground/wind
Access: token

The wind over the node's square for a map to draw moving: the forecast pack's Open-Meteo field, `n`×`n` points (8 by default) over `km` each side, hourly for the next day. Returns `{source, licence, attribution, fetched, n, km, lats, lons, times, speed_kmh, from_deg, at_node}`; `lats` run south to north and `lons` west to east, and `speed_kmh[t][row][column]` is km/h, `from_deg` the direction the wind comes from; `at_node` is the same for the node's own point, asked as such. Refreshed on each forecast poll and by `planetai run forecast windfield`; 204 on a node with `FORECAST_OPENMETEO=0`.

`planetai run place basemap` fetches the vector tiles, the fonts and any drone mosaic; `planetai run earth-engine basemap` builds the satellite layer. Each says what it reveals before it runs. After that a map drawn from these routes asks nobody anything.

The five `/geo/` routes and the four `/ground/` routes are on no allowlist, like `/place/geojson`: the node's cell at a fine resolution, a ring centred on it, and a distance from it each give away the point `/health` rounds, and so does a tile pyramid centred on it.

## Issues

The one document a client draws. A page, a Telegram handler or a wall screen that wants the node's whole answer builds against `/issues` and does no arithmetic of its own.

### GET /issues
Access: open

Every issue this node declares, computed: state, stack by distance, the line it is compared against, attribution, a sentence in each locale, open alerts, series. The order is `NODE_ISSUES`; an issue not declared still appears with `watched: false`, so a stranger can see what the node could report. The node computes and the page draws: nothing in the response needs arithmetic to render and nothing in it came from a model. `/issues/` answers the same.

Returns `{schema, order, undeclared, dropped, headline, as_of, lead, headline_rule, distances, labels, issues, stations, stations_silent, metrics, asks, digest, mesh, geometry, sections, events}`, with `schema` set to `issues-v0`.

`events` is the alert events (see [Alerts](alerts.md)), one per issue per house, as the bot tells them: which engine the node runs (`rules`, `shadow` or `events`), the three button labels in the household's language, the `open` events (kind, rooms, peak, the issue's line, the numbers the action was chosen from, the action and the latest message word for word, the alerts each covers, and the latest answer with its `stage`, `actor`, and `note`), the events cleared in the last 7 days under `recent`, `cleared_today` and `last_cleared` (the issue and time of the latest one cleared today), and `uncovered_asks`: the open alerts no event covers; on `shadow` and `events`, leaving out the alerts of the packs the engine replaced. An open event's issue leads the page, and `lead.by` is then `event`. A node older than v0.77 sends no `events` key, and a node that could not read them sends `events.error`.

- `headline` is the key of the issue an open event belongs to; with no open event, the issue with the highest state. Within a state, the tie goes to the issue that has `moved` most, and an exact tie to the declared order. Only an issue that declares a hero can lead. `headline_rule` states that rule in `en`, `id` and `es`, so a page can print why that issue leads.
- `lead` is `{issue, by}`: the same issue as `headline`, and which step of the rule picked it over the runner-up, one of `event`, `state`, `moved` or `order`. It is `null` when no watched issue declares a hero.
- `digest` is keyed by stage, `observe`, `decide`, `act` and `measure`, and each stage holds one sentence per locale. `digest.prompts` is the ask pane's questions per locale, written from the bundle: the three it opens with, then up to nine more it rotates through (the other issues, the two newest other open alerts, and each other issue's line), in the same order in every locale. `digest.simple` is one paragraph per locale, three sentences: the house's own stations and the nearest others, the oldest open alert, and how many times the node asked in the last 30 days and how many were answered. The dashboard's simple mode draws `digest.simple`.
- Each entry of `issues` carries `state`, `watched`, `reason`, `reason_text`, `name`, `kind`, `metric`, `unit`, `dp`, `headline`, `stack`, `line`, `attribution`, `trend`, `moved`, `open_asks`, `series`, `buckets`, `readouts`, `provenance`, `sentence` (keyed by locale), `title` and `tagline` (the sentence's split, keyed by locale: the title is the qualitative head with no number and no indicator in it, the tagline the explanation set smaller beneath it — docs/SPEC_language.md; the page titles with these and speaks prose with `sentence`), `hero`, `usual` and `usual_absent`. On `shadow` and `events` an issue's `state` follows its alert event: `act` while an event is open and unanswered (a danger event stays `act` after an answer), `notable` once somebody answers it and for 24 hours after it clears, with `reason.code` `event_open`, `event_answered` or `event_cleared`; and `open_asks`, which the oldest open alert in `digest` is read from, leaves out the alerts of the packs the engine replaced. An enabled pack can add rows to `readouts` through `readouts:` in its `pack.yaml`; it adds and never replaces. The full key set is defined in `app/issues/engine.py`.
- `usual` is the issue's usual day at its hero distance: for each local hour 0–23, the mean over that distance's
  sensors of `usual_by_hour`'s median and 90th percentile for the issue's own metric, over the 14 complete days before
  today. It is `null` when the node cannot say, and `usual_absent` says why: `unread` (a capture from before v0.79, or
  a node that has not refreshed the view since it started), `no_source`, `no_history`, or `not_watched`.
- Each open event in `events.open` carries `series`: its own rooms, hour by hour on the issue's `buckets`, combined
  as the issue combines its house (air the mean of PM2.5, heat the median of each room's apparent temperature).
- `stations` holds the stations heard in the last day. `stations_silent` is `{read, within_days, stations}`: whether
  the stopped ones were read, how far back, and its `stations`, those heard in the last 30 days and not in the last
  day, with `read: {}`, `series: {}` and `last_heard`, leaving out a relay of a kit still heard at the same point.
  `digest` (the simple sentence, "observing N stations", the neighbours within a kilometre) and `geometry` (the grain
  table) count only `stations`.
- `hero` is what the page draws when that issue leads, and the page draws nothing else there: `sign` and `pictogram` (symbol ids in `signs.svg`; no pictogram means the sign at hero size), `numeral` (the distance or readout the number is), `value`, `unit`, `dp`, `sentence` (the headline: words only, no numbers — docs/SPEC_language.md), `plain` (the reading layer: the numeral distance first, then the others on the rule, and the line; a context issue's figures, then where its number comes from), `rule` and `stamp` (keyed by locale). `rule` is `null` or `{min, max, ends, dots, line}`: `ends` is two words per locale, `dots` is `[{distance, value}]` for the distances that have a value tonight, and `line` is `{value, name}` or `null`. `clock` says what `stamp` is: `time`, when the numeral was read, or `date`, when a yearly record looked and when it looks next. `hero` is `null` for an issue that declares none, and for one not watched here. Each issue also carries `about`: one glossary text per locale, what the metric is and whose line it is, taught once.
- `sections` is one entry per section an enabled pack declares under `sections:` in its `pack.yaml`: `{id, pack, stage, title, order, wall, note, expected, readouts}`. Each readout carries its `sensor_id` and `age_minutes`; a reading the node has no row for is left out, and `expected` says how many were declared. No shipped pack declares one, so it is `[]` on every node unless a wild pack adds one.

The whole `/issues` prefix is on the `open` list and never on the `off` list: a snapshot carries 15-minute means, alert texts and sensor names, which are the household's own data.

### GET /issues/fixtures
Access: open

Which committed snapshots this node ships, so a design round does not have to guess a name. Returns `{"fixtures": ["name", ...]}`.

### GET /issues/fixtures/{name}
Access: open

One committed snapshot with its issues recomputed at the hour it was captured, through the same engine the live route uses. The dashboard reads this with `?fixture=<name>`.

| Name | Type | Default | Meaning |
|---|---|---|---|
| `name` | path | required | Matches `^[a-z0-9][a-z0-9._-]{0,63}$`; a name, never a path |

Returns the snapshot JSON with `issues` replaced by the recomputation, or `{"error": ...}` in `issues` if the snapshot lacks a table the engine reads. 404 lists the names available.

### GET /issues/days
Access: open

`?days=` from 1 to 90, default 7. Each declared issue's hourly series over that many local days, by the same engine
as `/issues`, so one day of it is the 24 hours `/issues` draws. Buckets are every local hour of the window, oldest
first; an hour with nothing recorded is `null`. The hours are stepped in UTC and shown in the node's zone, so a day
with a daylight-saving change holds 25 or 23 hours, and `of` says so. For each issue: `distance` (the hero distance,
the nearest with data), `series` (room, yard, ring and region, each an array or `null`), `provenance` (the word for
each distance drawn), `per_day` (`date`, `over` the hours over the line at the hero distance, `read` the hours with a
value, `of` the hours of that day inside the window), and `line`. `events` lists the alert events opened or cleared in
the window, or still open. Wire format `days-v0`. It is under the `/issues` prefix, so it is readable exactly where `/issues` is.

## Alerts and answers

The node asks; a person answers. A phone app, a Telegram handler, the dashboard's "I did this" and `curl` all build against the same two routes: `GET /alerts` for the alerts and `POST /actions` for the answer. Each answer is a row in the `actions` ledger, and ρ is counted from that ledger.

### GET /alerts
Access: open

Alerts newest first, each with the id that `planetai act <id>` needs, and whether anyone has answered.

| Name | Type | Default | Meaning |
|---|---|---|---|
| `limit` | int | 50 | 0..1000 |
| `since_hours` | int | 0 | only the alerts of the last that many hours, 0..2160; 0 is no bound |

Returns a list of `{id, ts, rule_id, sensor_id, level, text, acted_at}`. `acted_at` is the time of the first `acknowledged` or `acted` row for that alert, or null. A `decided` row does not set it.

### GET /actions
Access: token

Every answer a person gave an alert, newest first: which alert, which stage, who, and the note they left. `/alerts` says only whether somebody answered; this says what they said.

| Name | Type | Default | Meaning |
|---|---|---|---|
| `limit` | int | 500 | 0..5000 |
| `events` | int | 0 | `0` or `1`. With 1, also returns the answers to alert events, with their `event_id`; works with or without `stage` |
| `stage` | str | | only this stage; `settings` returns the node's own rows instead |

Returns a list of `{ts, alert_id, stage, actor, note}`, and with `events=1` each row also carries `event_id`, which is null for an alert's answer and set, with a null `alert_id`, for an event's. The node's own `settings` rows are left out unless `stage=settings` asks for them: one row per `PUT /settings`, where `actor` is its `X-Agent` and `note` the keys it wrote, comma-separated. The route is on neither allowlist on purpose, because `actor` and `note` are the household's own words about what they did in their own house.

> **Careful.** The handler has no token check of its own, so any of the four node tokens reads it. That includes `BACKUP_TOKEN`, `ACT_TOKEN` and this node's `AGGREGATE_TOKEN`, which every child of this node holds.

### POST /actions
Access: act

A person closes the loop. A mobile app, a Telegram reply handler or `curl` all make the same call. From loopback it needs no token, so the MCP `act` tool and a shell in the container keep working. From anywhere else it needs `ACT_TOKEN` or `ADMIN_TOKEN`: the weaker token on purpose, so someone in the house can be given the ability to close a loop without the key to `/settings/raw`. The check is made by the handler even at `SHARE_LEVEL=off`, because `BACKUP_TOKEN` gets past the middleware and a read-only NAS token must not be able to write ρ. The dashboard's "I did this" posts here with the token saved in the browser, `planetai_admin` first and then `planetai_act`; a browser is never loopback.

Body:

```json
{"alert_id": 12, "stage": "acted", "actor": "ibu wayan", "note": "closed windows"}
```

| `stage` | What the row does |
|---|---|
| `acknowledged` | Somebody saw it. Counts for ρ and sets `/alerts.acted_at` |
| `acted` | Somebody did the thing. Counts for ρ, sets `acted_at`, closes the alert |
| `decided` | Somebody said what they would do. Moves nothing: not in ρ, not in `acted_at`, not a funnel stage, closes no alert |

Any other stage is 400 `stage must be acknowledged, acted or decided`. `measured` is refused: the node derives it (see [`/rho`](#get-rho)) and never takes it from a post. `settings` rows are written by the node itself. With `DECISION_REQUIRED=1`, an `acted` post for an alert that has no `decided` row yet is 409 `this node is set to DECISION_REQUIRED, so an act needs a decision recorded against the same alert first. Decide on the dashboard, then record what you did.` The default is `0`.

An alert event is answered the same way, by sending `event_id` instead of `alert_id` (the stored row's `alert_id` is null): `{"event_id": 3, "stage": "dismissed", "actor": "tomas", "note": "ran the AC instead"}`. The stage is the button: Done is `acted`, Not now is `acknowledged`, Doesn't fit is `dismissed`. Any other stage is 400 `an event's stage must be acknowledged, acted or dismissed`, sending both ids is 400 `send alert_id or event_id, not both`, an event this node does not have is 404 `no such event`, and the tokens are the same as for an alert. An event's answer is not in ρ yet, and `DECISION_REQUIRED` does not apply to it.

`actor` is cut to 80 characters, `note` to 500. 404 `no such alert` if the alert id is unknown. There is no one-action-per-alert cap: two people who both acted are both recording something true. Returns `{"ok": true}`.

### POST /test-alert
Access: admin

Fires one act-level alert now, through every configured channel, the same as `planetai test-alert`. Writes an alert with rule `gui/test` and sends it with a hint on how to close the loop. Returns `{"ok": true, "alert_id": <id>}`.

## Whether it worked

The measure stage. These two routes read the ledger back against the alerts and say how many alerts were answered, how fast, and which conditions stopped. ρ is measured here and nowhere else, because only the node holds both the alert and the answer.

### GET /rho
Access: open

Action latency over the last 30 days: the share of act-level alerts that got an `acknowledged` or `acted` row within 24 hours, pooled over this node's own alerts and the events its children pushed. The child never sends a ratio; it sends timestamps and the definition stays here. See [rho](rho.md).

Returns `{window_days: 30, days_ago: 0, alerts_act, acted, rho, median_minutes, funnel}`. `rho` is `acted / alerts_act` to 3 decimals, or null with no act-level alerts; `median_minutes` is the median detect-to-act time of the alerts answered within 24 hours, or null.

`funnel` is how far this node's own alerts got, stage by stage: `{stages: {asked, acknowledged, acted, measured}, latency_minutes: {acknowledged, acted, measured: null}, measured_derived: true, measured_window_minutes: 2880, self_only: true}`. `measured` is derived: an `acted` alert whose rule stayed silent on the same sensor for the next 2880 minutes (48 hours) counts as measured, because a rule re-fires as soon as its cooldown expires while its condition holds. Only a rule the node still evaluates can yield a derived `measured`; a `measured` row already in the ledger still counts. `measured` has no latency on purpose, because the silence proves the condition stopped and not when. The funnel is `self_only` because a child's events carry no stages. Its `acted` is the literal stage, so it will not agree with ρ's `acted`, which also counts `acknowledged`.

### GET /effect
Access: open

Per rule, whether the acts worked and how long recovery took, over this node's record. Two questions with two kinds of evidence, reported apart.

| Name | Type | Default | Meaning |
|---|---|---|---|
| `days` | int | 365 | 1..3650 |

Returns `{window_hours, days, rules}`, with `window_hours` 48. Each `rules` entry is `{rule_id, acted, cleared, watch, hours, measured, already}`:

- `acted` counts act-level alerts of that rule with an `acted` row whose 48-hour window has fully passed, and `cleared` those the rule did not re-fire on during the window.
- `watch` is the rule's own `watch: {metric, over}`, or null. Only a rule that declares one has a line to recover under. For it, `hours` is the median time from the act to the first hourly mean back under `over`, `measured` the number of acts with such an hour, and `already` the number of acts made when the reading was already back under the line. For a rule without `watch`, `hours` is null and both counts are 0.
- `hours` is elapsed time. Nothing here says the act caused the recovery.

Retired rules are left out. If the node cannot read its rule set, the answer is `{window_hours, rules: [], note: "this node could not read its rule set"}`.

## Reports

### GET /report/latest
Access: open

The last report this node wrote, sent or held. The MCP tool `report_latest` returns this body as it is, and `planetai report last` prints its `text` followed by one line, `<ts> · <window_hours> hours · written by <rung>`, with `· HELD for quiet hours, folded into the next one` added when `sent` is false. Ordered by write time, not by due hour, so a report written on request shows here.

Returns `{schema: "report-v0", id, ts, due_local, window_hours, depth, rung, text, sent, held_quiet, fallback_reason, note}`, the same keys whether or not a report exists. Before the first report every key but `schema` is null and `note` is `"no report yet; the first one lands at the next due hour"`. Once a report exists, `note` is null.

### GET /report/bundle
Access: pull

Every number the node has about a window, as one document: what a report is written from. Behind the read-only token because this is more of the household's data in one place than any other endpoint returns. SQL only; nothing is polled and nothing leaves the machine.

| Name | Type | Default | Meaning |
|---|---|---|---|
| `hours` | int | 0 | Window in hours, 0..168; 0 means `REPORT_EVERY` |

Returns the bundle from `app/report.py`: `meta` (node, locale, timezone, local time, window), `series`, `observations`, `now`, `alerts`, `open_act`, `sensors_quiet`, `rho`, `previous`, `cells`, `rules`, `facility`, `health`, plus one key per pack that contributes a report block. Series are dropped from the end if the document goes over the size cap, and `meta.truncated` counts them.

### POST /report/now
Access: admin

Write and send a report immediately, whatever the hour. `planetai report` and `/report` in Telegram call this. The row has no `due_local`, so the next scheduled report still happens. Returns `{id, text, depth: "sheet", rung: "node", sent: true}`.

## The Index contract

What the node computes for the Fab City Index, and what the network has registered as measurable. A cell ingester builds against `/cells`; someone asking what could fill an empty cell builds against `/sources`.

### GET /cells
Access: open

The Index cells this node can compute from data it holds, in the fci-cells-v0 row shape used by the FCI Observations base. Domain cells come from packs (`cells.yml`); the core evaluates their SQL as a read-only role and polices the provenance. A `Governance|<Scale>` row is appended only when there has been at least one act-level alert in the last 30 days; it is `partial` while fewer than 5 have been answered. A pack may not claim `live` before its `min_buckets` of in-custody hourly data exist, nor off too few instruments: a node with children needs two sensors from two different children.

Each row:

```json
{"city": "bali", "cell": "Environmental|Community", "value": 18.4,
 "unit": "µg/m³ PM2.5 (24h mean, sensors in this node's custody)",
 "source": "planetai-node · pack:air-quality", "observed_at": "2026-09-22T08:35:02+00:00",
 "state": "live", "notes": "this node's own sensors and its children's hourly means; indoor and outdoor kept separate by the rules · 24/12 hourly buckets",
 "registered": 4, "adapter": true}
```

`value` is rounded to 3 decimals or null; `state` is `live`, `partial` or `mock` and is never upgraded here or downstream; `source` is `planetai-node · pack:<id>` or `planetai-node actions ledger`. In v0.72.1 `registered` is how many registry entries are filed under that cell, and `adapter` is true when any of them names code that reads it. Both come from the registry this node carries and change nothing about `state` or `value`. A cell with registered sources and no adapter has no row here at all; `/sources?cell=` answers for it.

Since v0.73 the row ends with five registry fields, and the same row at pin `851b8db` ends:

```
 "registered": 2, "adapter": true, "reviewed": 2, "candidate": 0, "capable": 2}
```

`registered` keeps its name and now carries the `reviewed` count, so it is not the v0.72.1 number: `Governance|City` goes from 32 to 4. `adapter` is true when `capable` is above 0. `capable`, `reviewed` and `candidate` are the three counts `GET /sources` returns under `counts`, grouped by `feeds_cells` rather than by where an entry is filed; see [the source registry](sources.md).

### GET /sources
Access: open

The network's registry of what can be measured, as this node carries it: a pinned copy of `awesome-fabcity-data` under `data/sources/`, identical on every node in a release. In v0.80 the pin is `851b8db`, synced 6 October, with 269 entries. It says nothing about this house, which is why it is on the `open` list by name.

| Name | Type | Default | Meaning |
|---|---|---|---|
| `pillar` | string | any | Only this pillar |
| `scale` | string | any | Only this scale |
| `cell` | string | any | Only this cell, written as the Index names it |
| `pilot` | string | any | This pilot's entries and every entry relevant to `global` |
| `wired` | bool | any | `true`: only entries whose `adapter` names code that reads them; `false`: only those without |
| `status` | string | any | Since v0.73. `live`, `candidate`, `stale`, `deprecated`, `paywalled` or `planned`: only entries with that status |

Every filter is AND. `?cell=Social|City` lists what is filed for a cell this node may have no row for. Returns `{registry: {sha, short, synced, entries}, count, sources}`, with each entry as the registry writes it. Since v0.73 the answer also carries `counts`, `{cell: {capable, reviewed, candidate}}` for every cell the registry counts, whatever the filters: `capable` is live with an adapter, `reviewed` is live and backed by an adapter or a review whose verdict is `usable` or `usable-with-caveats`, `candidate` is status `candidate`. An entry counts against the cells in its `feeds_cells`, and against its own `cell` only when that key is absent. A `deprecated`, `stale`, `paywalled` or `planned` entry counts in none of them. At `851b8db` the counts cover 19 cells and sum to 12 capable, 17 reviewed and 51 candidate. 503 when the registry is missing: `no source registry on this node: <dir> is empty or unmounted. Vendor one with tools/sync_registry.sh <sha> and rebuild.`

### GET /sources/{pillar}/{scale}/{slug}
Access: open

One registry entry by its full slug, such as `economic/community/fablabs-io`. 404 `<pillar>/<scale>/<slug> is not in the registry this node carries (<short>). Ask /sources for the list.`

### GET /packs
Access: open

What this node has loaded beyond the core. Returns a list of pack manifests: each `pack.yaml` as parsed, with `id`, `path` and `kind` (`data` for rules and cells only, `code` for a pack with an `adapter.py`).

## Federation

What a child sends its parent, and what a parent asks of its children. Raw readings never travel this path: a child pushes hourly means and alert timestamps, and the parent computes the district's cells and ρ from them. See [federation](federation.md).

### GET /aggregates
Access: token

This node's hourly means from `readings_1h`, newest first. Not on the `open` list.

| Name | Type | Default | Meaning |
|---|---|---|---|
| `hours` | int | 24 | 1..2160 |

Returns a list of `{bucket, sensor_id, metric, mean, min, max, n}`.

### POST /aggregates
Access: children

The parent side. A child pushes its hourly means.

Body:

```json
{"schema": "aggregates-v0", "node": "bayu-ungasan", "scale": "community",
 "rows": [{"bucket": "2026-09-22T07:00:00+00:00", "sensor_id": "sc-1234", "metric": "pm25",
           "mean": 18.4, "min": 12.0, "max": 25.1, "n": 12}]}
```

The parent stores each row as one reading at the child's bucket under the namespaced sensor id `<node>/<sensor_id>`, and upserts that sensor with `source='child'`, `kind='child'`, `cadence='PT1H'`, `local=FALSE` and the body's `scale` (default `community`). The metric keeps its own name; the cadence is in the sensor row, not the key. A re-push of the same hour is ignored by the readings table's unique constraint. `min`, `max` and `n` are not stored. An unknown or missing `schema` is logged once and read anyway. Returns `{"accepted": <number of rows in the body>}`.

### POST /events
Access: children

The parent side of ρ. A child pushes one row per alert it raised, as timestamps only: no text, no actor, no sensor id, no note. The parent computes ρ over its own alerts and these together.

Body:

```json
{"schema": "events-v0", "node": "bayu-ungasan", "scale": "community",
 "rows": [{"alert_id": "812", "raised_at": "2026-09-22T06:12:00+00:00", "rule": "air-quality/indoor_pm25_high",
           "level": "act", "kind": "air-quality", "responded_at": null,
           "acted_at": "2026-09-22T06:40:00+00:00", "measured_at": null}]}
```

The parent stores `child`, `alert_id`, `rule`, `level`, `kind`, `scale`, `raised_at`, `responded_at`, `acted_at`, `measured_at` and `received_at`, upserting on `(child, alert_id)`, so a row re-sent with new timestamps is an update. Any other key in a row is dropped rather than stored. A row without `alert_id` or `raised_at` is skipped. An unknown or missing `schema` is logged once and read anyway. Returns `{"accepted": <rows kept>}`.

`measured_at` is null in practice: a child fills it from posted `measured` rows, and `POST /actions` no longer takes one.

## Open data and backups

What the node publishes, and how its dumps reach a NAS.

### GET /export
Access: public

One day of this node as open data, licensed CC BY 4.0: hourly means per sensor and metric, the Index cells, the alerts and ρ. Never raw readings, never secrets. The node's own sensors are named by role (`indoor-1`, `outdoor-1`), not by device id; public references and models keep their ids. `backup.sh` fetches this nightly over `http://localhost:${APP_PORT}` and writes `exports/<node>/YYYY-MM-DD.json`, which is why the route is on the `off` list.

| Name | Type | Default | Meaning |
|---|---|---|---|
| `day` | string | required | `YYYY-MM-DD`; 422 `day must be a real date, YYYY-MM-DD` otherwise |

Returns:

```json
{"schema": "export-v0", "node": "bayu-ungasan", "city": "bali", "scale": "community", "lat": -8.827, "lon": 115.157,
 "day": "2026-09-21", "generated": "2026-09-22T00:05:11+00:00", "version": "v0.72.1", "licence": "CC BY 4.0",
 "hourly": [{"t": "2026-09-21T00:00:00+08:00", "sensor": "indoor-1", "local": true, "indoor": true,
             "kind": "sensor", "metric": "pm25", "mean": 11.2, "min": 9.0, "max": 14.1, "n": 12}],
 "alerts": [{"t": "2026-09-21T06:12:00+08:00", "rule": "air-quality/indoor_pm25_high", "level": "act", "text": "..."}],
 "cells": [], "rho": {}}
```

`alerts[].text` is the first line only. `cells` and `rho` are the same shapes as `/cells` and `/rho`, computed at export time.

### GET /exports
Access: open

The daily exports on disk. Returns a list of `{node, name, bytes}` from `exports/*/*.json`, newest name first; `[]` if the directory is missing.

### GET /exports/{node}/{name}
Access: open

One export file as JSON. Path components are stripped from both parameters; the file must end in `.json`. 404 `no such export`.

### GET /backups
Access: pull

The database dumps this node has made, newest first, so a NAS can fetch the ones it lacks. Returns a list of `{name, bytes, mtime}` from `backups/*.sql.gz`; `[]` if the directory is missing.

### GET /backups/{name}
Access: pull

One dump as `application/gzip`. The name is taken as a basename only and must end in `.sql.gz`. 404 `no such backup`.

## Settings

### GET /settings
Access: public

Every runtime setting with its group, label, help and current value, plus the bootstrap keys read-only. Secrets are always masked as `•••• set`: the node's own, and every key a pack lists under `secrets:` in its `pack.yaml`. Without the admin token, every value outside the public set is masked too: chat ids, sensor hosts, account names and remote URLs are the household's. A wrong token reads as no token, with no error, so the dashboard's layout read keeps working on every screen.

At `SHARE_LEVEL=off`, a caller that is neither loopback nor carrying a token sees the values of `UI_LAYOUT` and `SHARE_LEVEL` only. Every other row is still present, masked, so the Set up view still renders and says what a token would show. A reader without the admin token sees the values of the public set when `SHARE_LEVEL=open`, from loopback, or with one of the other three node tokens (`REPORT_EVERY`, `ALERT_LEVEL`, `QUIET_HOURS`, `SHARE_LEVEL`, `NODE_ISSUES`, `MAP_TILES`, `UI_MODE`, `PACKS_ENABLED` and the rest of `settings.PUBLIC`).

Returns `{unlocked, runtime: [...], bootstrap: [{key, label, value, group}]}`. Each node row in `runtime` is `{key, group, label, secret, restart, help, value, set, source, choices, default, outward}`. `source` is `gui`, `env` or `default`; `choices` lists the accepted values where the key has a fixed set; `default` is the shipped default, or null when the image has no defaults file; `outward` marks a key that changes what leaves the machine.

After the node's own rows come the keys the installed packs declare in their `pack.yaml`, whether the pack is switched on or not: the shipped packs declare 26, and 23 of them are rows here. Each has `group: "packs"`, `restart: false` (the value reaches the pack at its next run), `choices: null`, the key as its `label`, the `default` the pack states, and a `pack` key naming the pack; `secret` is true only when the pack lists the key under `secrets:`. The other three, `COAST_MAX_KM`, `EE_PROJECT` and `EE_KEY_FILE`, are node keys too, already in group `packs`: each stays one row and gains the `pack` key.

### PUT /settings
Access: admin

Change runtime settings, and the keys an installed pack declares. Blank returns a key to its `.env` value. Effective within about 20 seconds (the settings cache TTL).

Body: `{"KEY": "value", ...}`. Header `X-Agent` names the caller (default `gui`).

400 `<KEY> is not a runtime setting, and no installed pack declares it` for a key outside `settings.RUNTIME` and every `pack.yaml`; 400 with the validation message for a value outside the key's choices. Every call writes one row to the `actions` ledger with `stage='settings'`, `actor` = the `X-Agent` value and `note` = the keys changed. Returns `{changed: [keys], by, effective_within_s: 20}`.

> **Note.** Every row `GET /settings` lists can be set here. A pack key is accepted whether or not its pack is switched on, so `MAKE_ENABLED` can turn the make pack on, and the node also puts the value into the environment the pack reads. A node that answers 400 `<KEY> is not a runtime setting` to a pack key is older than this; update it.

### GET /settings/raw
Access: admin

Every runtime setting unmasked, as `{KEY: value}`, for the node's own processes: the agent loop reads its model ladder here every minute. Admin token only, explicitly not `BACKUP_TOKEN`, so a NAS's read-only token cannot unmask the Telegram token or the AI keys. Never call this from a browser.

## The agent surface

### /mcp
Access: admin

The MCP server, over streamable HTTP at exactly `/mcp` (GET, POST and DELETE as the transport defines; no trailing-slash redirect). The whole surface needs `Authorization: Bearer <ADMIN_TOKEN>`, checked by its own middleware against the environment, because the tools can write as well as read; a missing or wrong token is 401 `{"error": "the agent surface needs Authorization: Bearer <ADMIN_TOKEN>"}`. It bypasses the `SHARE_LEVEL` check, which leaves the decision to that middleware. The tools call the API back on `http://127.0.0.1:8080`, so they arrive at every other route as loopback.

In v0.80 the tools are `status`, `health_check`, `sensors`, `context`, `readings`, `report_latest`, `report_now`, `report_bundle`, `history`, `alerts`, `act`, `settings_get`, `settings_set`, `packs`, `cells`, `issues`, `series`, `export_day`, `run_pack_script` and `maintenance`. Each is classed `read`, `act` or `admin` in `app/tool_classes.py`; `act` is the only `act` tool, and it refuses a `note` that is empty or a placeholder such as `done` or `ok`, because ρ counts what a person said they did. The [MCP page](mcp.md) describes each.

## The ask pane

The dashboard's pane asks the model Set up → Model names, the same one the Telegram bot uses, about what the page shows: the one on this machine, one on another machine of yours, or an online one when `AGENT_PREFER` allows it. It reads and changes nothing: an `act` or an admin tool comes back as a proposal the person presses. Nothing asked or answered is kept, on disk, in the database or in a log line.

### GET /ask/status
Access: open

`{model, rung, where, host, running, why, rungs, leaves, tools, stored}`: the model the pane asks first and its `rung` (`local`, `remote` or `online`, from Set up → Model and `AGENT_PREFER`), `where` it runs (`this machine`, `your network` or `online`) and its `host`, whether it is answering, why not when it is not, every model in the order it is tried as `{rung, model, host, where}`, `leaves` (true when an online model is in that order, so the question and the page's context may leave the network), the tools it is offered as `{name, class}`, and `stored`, which is always `false`. 404 when no model is set up at all: no loop on this machine (the `agent` profile, which `planetai agent local` adds), no remote model, and no online one that `AGENT_PREFER` allows; its `detail` carries `recommend` (`{tag, size, memory_gb, pull}`, the tag `planetai agent local` would suggest for this machine's memory), `mcp` and `token_hint`, for the page's no-model state. With Ollama installed and down, `running` is `false` and the tag is still named.

### POST /ask
Access: open

Takes `{messages, view, mode, focus?}`: the thread so far (at most 24 messages of 4,000 characters, `user` or `assistant`), the view and mode the page is in, and a learn mark's key when one is in focus. The browser sends no readings; the node builds the model's context itself from `/issues` (the lead and its hero, the digest, every watched issue's state and values, the open alerts) and the learn entry for `focus`. That context, and every tool result, carries no coordinate, no sensor or station name, no sensor id and no `meta`: they are dropped or replaced before the model reads them.

Answers `text/event-stream` with six events: `token` (`{text}`, the answer in pieces), `tools` (`{tool, ms}`, one per read the model made, sent the moment the read is done), `retry` (`{rung}`, a model that had already read something failed, so forget its `tools` before the next one starts), `proposal` (`{tool, args, setting, current, proposed, choices, group, leaves, undo}`, one per change it reached for; an `act` proposal carries only the alert's id, because what the person did is theirs to write, and a value the setting would refuse is `null` with its `choices`; `leaves` is the setting's own help text and `undo` says how to set it back, both per locale), `done` (`{rung, model, host, where}`, the model that answered and where it runs; when one fails the next is tried, and no proposal the failed one produced is sent) and `error` (`{message}`). The model is offered the `read` tools except `settings_get`, `report_bundle` and `export_day`, and it runs them through `/mcp` as `dashboard-chat`; it is also offered `act` and the admin tools, and calling one does nothing but emit a `proposal`. 404 when no model is set up, by the same test as `GET /ask/status`.

### GET /docs/search
Access: open

`?q=` (2 to 80 characters). A case-insensitive substring search over this node's documentation, with no model: the learn marks and `data/docs_site.json`, which `make learn` cuts out of `docs/site` at build time because the container does not carry `docs/`. Returns at most 20 `{page, anchor, title, snippet}`.

## Wire formats

Six documents travel between nodes or are kept for good, and each names its format in a `schema` key.

| `schema` | Document |
|---|---|
| `issues-v0` | `GET /issues` |
| `export-v0` | `GET /export`, and so the daily files `backup.sh` writes from it |
| `report-v0` | `GET /report/latest` |
| `aggregates-v0` | The body a child posts to `POST /aggregates` |
| `events-v0` | The body a child posts to `POST /events` |
| `days-v0` | `GET /issues/days` |

A receiver never refuses on this key. A parent one release behind keeps accepting a child one release ahead: an unknown value is logged once, the fields the parent knows are read, and the rest are dropped. A document with no `schema` predates the key and is read as `-v0`. `tools/check_wire.py` holds the top-level keys of each format to `tests/data/wire/<format>.json`, so changing one is two edits in the same commit.

## What the node calls out

The API is the read side. These are the requests the node makes of other machines.

| To | When | What travels |
|---|---|---|
| `POST {PARENT_API_URL}/aggregates` | Hourly, if `PARENT_API_URL` is set | `{schema, node, rows, scale}`: hourly means from the last 2 hours, with `Authorization: Bearer <PARENT_TOKEN>` if set |
| `POST {PARENT_API_URL}/events` | Hourly, if `PARENT_API_URL` is set and an alert was raised in the last 36 hours | `{schema, node, rows, scale}`: one row per alert from the last 36 hours as timestamps (`alert_id`, `rule`, `level`, `kind`, `raised_at`, `responded_at`, `acted_at`, `measured_at`), same header |
| Telegram `sendMessage` | Each alert at or above `ALERT_LEVEL` (quiet hours hold all but `act`), except that with `ALERT_ENGINE=events` the heat and air-quality alerts are not sent and each event's message is instead; each report not held by quiet hours, and once per newer release outside quiet hours, per chat id | The message text, to `api.telegram.org` with `TELEGRAM_BOT_TOKEN` |
| `GET https://planetai.fab.city/node0/get/VERSION` | Once a day, unless `UPDATE_CHECK=off` | Nothing about the house; the request shows the node's internet address to Fab City's host. The answer fills `/health`'s `release` |
| `POST {RETICULUM_URL}/send` | Each act-level alert, if `RETICULUM_URL` is set | `{"text": ...}` to the bridge container |
| MQTT publish | Each act-level alert (`MESH_ALERTS=1`), and Home Assistant discovery (`HA_DISCOVERY=1`) | The first line of the alert to the mesh downlink; discovery and state topics to the broker at `MQTT_HOST` |

The sources the node polls (Smart Citizen, Bali Air Dispatch, Open-Meteo, CKAN portals, packs) are on the [sensors page](sensors.md).

## Not in this version

- `/plan.png` and `/provenance` do not exist. Provenance travels inside `/cells` rows (`state`, `source`, `notes`) and in the `meta` of `/sensors` (`licence`, `attribution`, `model`, `dataset`, `network`, `note`, `corrected`).
- There is no decisions endpoint and no decisions table. A decision is `POST /actions` with `stage: "decided"`, read back through `GET /actions`.
- There is no query-parameter or `X-Token` form of authentication, and no per-route token other than the ones named above.
- `X-Forwarded-For` is never read; a proxy in front of the node does not make its clients loopback.

## Where this leads

The rows these routes return live in one Postgres database, and the [schema page](schema.md) says what each table and view holds. To point a child at a parent, read [federation](federation.md). To put an agent on the node through `/mcp`, read [MCP](mcp.md).
