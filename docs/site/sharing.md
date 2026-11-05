# Sharing and security
<!-- checked: v0.91.0 -->

Read this page before you open the node to anyone else: a wall screen in the house, a phone, a neighbour's
network, a parent node. It says what a reader without a token may see, which token opens what, what leaves the
machine and how coarse it is when it does, and whose code the node will run. The rule underneath it is the
first refusal in the repository: "No raw readings leave the instance that recorded them."

## Before you open it

1. Check what listens on your network ([below](#what-listens-on-the-network)). Only the API answers without a
   password, and what it answers is decided by `SHARE_LEVEL`.
2. Choose `SHARE_LEVEL`. At `off`, the default, a screen with no token sees the dashboard shell and little else. At
   `open`, anyone on your network reads the whole read API, including the house's usual day ([the notes
   below](#share-level)).
3. Give each token to the device that needs it and no other, knowing what each one opens ([The tokens](#the-tokens)).
4. Read [what leaves the machine](#what-leaves-the-machine-and-how-coarse). Each line there has the setting that
   turns it off.
5. To reach the node from outside the house, use Tailscale and nothing else ([Reaching it from
   elsewhere](#reaching-it-from-elsewhere)).

## What listens on the network

| port | what | who may use it |
|---|---|---|
| `8080` (`APP_PORT`) | the API and the dashboard, on every interface | anyone on the network, within `SHARE_LEVEL`; a token for the rest |
| `1883` | the MQTT broker, with the `mqtt` profile (`planetai meshtastic`, `planetai broker`) | a client with the broker's user and password; anonymous clients are refused |
| `4001` | the IPFS swarm, with the `ipfs` profile | the IPFS network, which sees only the daily export |
| `4242` | Reticulum, with the `reticulum` profile | Sideband, NomadNet and other nodes on the LAN or tailnet |
| `3000` (`GRAFANA_PORT`) | Grafana, with the `grafana` profile, on loopback unless `GRAFANA_BIND` says otherwise | whoever signs in to Grafana, who reads every table but `settings` ([Grafana](grafana.md)) |

Postgres (`5432`), the IPFS API (`5001`, `8085`) and the Reticulum bridge's API (`4243`) bind `127.0.0.1` only.
The API is on every interface because the things that read it are on the network: the NAS that pulls backups, the
phones and the wall screen, Home Assistant, and an agent's MCP client on the tailnet. A token guards every write
and every secret read.

## `SHARE_LEVEL`

`SHARE_LEVEL` says who on your network may read the node without a token, and it never sends anything
anywhere. Change it in Set up, with `planetai config set SHARE_LEVEL open`, or over MCP; it is live within 20
seconds.

There are two levels. `cell` and `means` are named in the setting's help and refused until they exist.

| level | a request with no token, from another machine, may read |
|---|---|
| `off` (default) | 11 paths and the static files: `/` and `/ui` (the dashboard shell), `/workbench` (the sensors workbench, a shell like `/ui`) and `/tester` (which sends you to it), `/health` with the centre of the node's resolution-8 cell, `/llms.txt`, `/settings` reduced to the layout and the sharing level, the daily CC BY 4.0 `/export`, `/presence`, `/nodes` (the programme's public list of nodes), `/offers` (what the household chose to lend or give), and anything under `/static/`. Everything else is refused with a sentence naming the setting. |
| `open` | 41 paths and 5 prefixes: the `off` list, and `/sensors` and `/stats` (the household's own sensors at the point `/health` publishes, the rest to three decimals, metadata cut to the provenance keys), `/observations`, `/alerts`, `/series`, `/sparks`, `/rho`, `/cells`, `/packs`, `/packs/all`, `/trust`, `/nearby`, `/forecast`, `/earth`, `/earth/change.png`, `/earth/year.png`, `/earth/frame.png`, `/report/latest`, `/readings`, `/reach`, `/shape`, `/effect`, `/history`, `/exports`, `/sources`, the ask pane's `/ask`, `/ask/status` and `/docs/search`, `/geo/cell` without the fields that place a cell relative to the node (`is_node`, `cells_from_node`, `ring_polar`, `children_polar`), `/learned/place` (what the node learned is usual for the outdoor sensors, never the house), and anything under `/exports/`, `/issues`, `/sources/` and `/ground/`. What a wall screen or a phone with no token needs. |

A refused request gets 403 and a sentence. For a path that `open` would answer it ends "Set SHARE_LEVEL to open in
the dashboard's Set up view to let anything on your network read it." For a path no level opens it ends "No share
level opens this one, so it always needs a token from anywhere but the node itself." The dashboard shows the
sentence on its refused page.

To watch the boundary move:

1. **Ask from another machine at `off`.** `curl http://<node>:8080/rho` answers 403 with `{"error": "this node is
   set to SHARE_LEVEL=off, so /rho answers only this machine or a request carrying a token. Set SHARE_LEVEL to open
   in the dashboard's Set up view to let anything on your network read it."}`. The node is up and keeping ρ to
   itself.
2. **Open it.** On the node, `planetai config set SHARE_LEVEL open` prints `SHARE_LEVEL is now open, on this node,
   within 20 s`. After those 20 seconds the same `curl` returns the ρ document. Every screen on your network can now
   read the node without a token, and nothing has been sent anywhere.
3. **Ask for a path no level opens.** `curl http://<node>:8080/actions` still answers 403, with the second
   sentence. The record of what people did stays behind a token. `planetai config set SHARE_LEVEL off` closes the
   rest again.

Weigh what `open` gives a reader before you set it on a network you share:

- `/shape` is the house's usual day: one mean per local hour, indoor against outdoor, over the whole record. It is
  also a pattern of when the kitchen is in use.
- `/issues` carries the alert events with their rooms (under the neutral names below), the stage and time of the
  last answer, each issue's usual day and an open event's rooms hour by hour. `/issues/days` gives up to 90 days of
  the hourly series, indoor rooms included. That is the household's rhythm over three months. It never carries the
  text the node sent, who answered or what they wrote.
- `/forecast` and `/earth` carry the node's exact coordinates. [The API](api.md) says what every route returns.

`/sources` is on the `open` list because it is a copy of a public registry, the same on every node in a release,
and says nothing about the house.

### Rooms and sensor names stay in the house

At every level, a screen without a token never reads what the house calls its rooms or its sensors. Every answer
it gets has the house's own labels swapped for neutral ones, "Room A" for a room and "Sensor 1" for a sensor's own
name, the same on every route, so the page can still tell one room from another. The sentences of past alerts,
written under the names of their day, are left out instead. A token reads the real names.

## What needs a token at every level

These are on neither list: `/place/geojson` (the shape of your building and what is around it), the `/geo/` routes
other than `/geo/cell` (each one locates the node), `/machine` and `/storage`, `/settings/raw`, `/settings/phone`,
`/backups` and `/backups/<name>`, `/report/bundle`, `GET /aggregates`, `GET /actions` and the whole of
`/captures`. So is every write, and `/mcp` checks the admin token itself.

Two writes pass the sharing check because their path is on a list for reading, and their handler refuses them
instead: `POST /readings` at `open`, and `PUT /settings` at every level. Without the admin token both are refused.
`POST /aggregates` and `POST /events`, what a child sends its parent, pass at every level and check
`AGGREGATE_TOKEN` themselves.

A request from the machine itself is trusted without a token. That means `127.0.0.1` inside the container: the
node's own MCP tools and a shell in the container. A browser on the host is not loopback, because it arrives from
Docker's bridge, so it is treated as a machine on the network.

`GET /actions` is the record of what people did about the alerts: which alert, which stage, who, and the note they
wrote. The note is the household's own words about its own house. `planetai snapshot` blanks every note before it
writes its file.

`/captures` is the household's own pictures. Its routes refuse every token but `ACT_TOKEN` and `ADMIN_TOKEN`, so the
read-only `BACKUP_TOKEN` cannot read a picture. The row keeps the exact point, and the file is cleaned of EXIF and
GPS. No capture goes into `/export`, `/exports`, `/aggregates`, `/readings` or a parent push.

> **Careful.** `GET /actions` and `/place/geojson` have no token check of their own. Any of the three household
> tokens opens them: the admin token, the backup token on the NAS and the act token on a phone. Give each knowing it
> reads the household's notes and the plan of its building. `AGGREGATE_TOKEN`, which every child node holds as its
> `PARENT_TOKEN`, opens neither.

## The tokens

All travel as `Authorization: Bearer <token>` and are compared in constant time. There is no query-string form.

| token | opens | where it comes from | give it to |
|---|---|---|---|
| `ADMIN_TOKEN` | every write and secret read: `PUT /settings`, `/settings/raw`, `/settings/phone`, `POST /readings`, `/report/now`, `/test-alert`, `POST /packs/install`, the whole of `/mcp`, and what `BACKUP_TOKEN` and `ACT_TOKEN` open. Not `POST /aggregates` or `POST /events`, which take `AGGREGATE_TOKEN` only | made by the installer; `planetai ui` prints it | yourself and your agent. Treat it like a password |
| `BACKUP_TOKEN` | read-only pulls: `/backups`, `/backups/<name>`, `/report/bundle`. It cannot read `/settings/raw` | made by `update.sh` when blank; `planetai ui` prints it (`planetai storage` says only whether it is set) | a NAS |
| `ACT_TOKEN` | `POST /actions` from off the machine: an act, an acknowledgement, a decision or an answer to an alert event (`event_id`) or a pack's button (`alert_id` and `choice`). It cannot read a secret or change a setting | `planetai ui` makes it; Set up › This screen shows it to the admin as a QR code for a phone | a phone, the dashboard's forms in a browser you trust, the Reticulum bridge |
| `AGGREGATE_TOKEN` | what this node demands on `POST /aggregates` and `POST /events`; unset, the node accepts no children | you set it | your children, as their `PARENT_TOKEN` |
| `PARENT_TOKEN` | sent with this node's hourly pushes to `PARENT_API_URL` | your parent's operator | the node itself |

Any of the three household tokens (admin, backup, act) passes the sharing check at every level, so each reads the
whole read API. The aggregate token does not. Every child holds it, and a child is another household, so it pushes
to `POST /aggregates` and `POST /events` and reads only what a stranger reads. Routes with a check of their own then
apply it: a backup token cannot change a setting, and an act token cannot fetch a backup. The optional `X-Agent`
header names the caller in the audit trail. The dashboard keeps the token it was given in the browser's local
storage and sends the admin token first, then the act token.

`.env` is mode 600 and never committed. Backups leave out the `settings` table, so a Telegram token saved from Set
up never travels to a NAS or a remote. The node never logs the Telegram URL, because the token is in it.

## What leaves the machine, and how coarse

| what | to whom | how exact |
|---|---|---|
| the node's position | `/health`, `/export`, and `/sensors` and `/stats` for the household's own sensors, to a reader without a token | the centre of the resolution-8 cell (about 500 m to an edge); this machine or a token gets three decimals |
| hourly means and alert timestamps | a parent node, hourly, if `PARENT_API_URL` is set | values and timestamps; never where, never text, never who |
| the daily export | anyone (CC BY 4.0) | your own sensors by role (`indoor-1`, `outdoor-2`), no raw rows, no chat ids |
| a presence announce | the Reticulum network, every half hour, only with `RETICULUM_PRESENCE=1` | the H3 cell rounded up to `RETICULUM_PRESENCE_RES` (3), with a floor of resolution 6 that no setting goes under |
| the node's coordinates | Open-Meteo, for weather and the CAMS air model, with `OPENMETEO_ENABLED=1` | rounded to three decimals for the current weather and the current CAMS reading |
| a request for the fab lab directory | gitlab.fabcloud.org (`MAKE_SOURCE=archive`) or api.fablabs.io (`live`), only with `MAKE_ENABLED=1` and `PACKS_ALLOW_CODE=1` | no coordinates: the whole directory comes down and the node works out the distances |
| fires nearby | firms.modaps.eosdis.nasa.gov, at most every three hours, only with `FIRE_ENABLED=1` and `PACKS_ALLOW_CODE=1` | the name of a regional file; with `FIRMS_MAP_KEY`, a box `FIRE_REGION_KM` (150) round the node, to three decimals |
| the ground's heat | planetarycomputer.microsoft.com, anonymously, once a day, with the `surface-heat` pack on and `PACKS_ALLOW_CODE=1` | the node's own point, unrounded, in each scene search |
| a request for the current version | planetai.fab.city, every hour, with `UPDATE_CHECK=on` (the default) | one file. Fab City's host sees this house's internet address and that a node lives there. `off` means the node never asks |
| a request for the list of nodes | raw.githubusercontent.com (`registry.json` on the repository's main), every hour, with `UPDATE_CHECK=on` | one file, as above. `off` means the node never asks |
| a request for the list of wild packs | raw.githubusercontent.com (`packs.json` in fabcity/planetai-wild-packs), every hour, with `UPDATE_CHECK=on`, and when Set up › Packs is opened | one file, as above. `off` means the loop never asks |
| a request for the workbench's firmware | planetai.fab.city (Meshtastic) and makingsense.fablabbali.com (the Bayu), every six hours, with `UPDATE_CHECK=on` | files that every node asks for, as above. `off` means the node never asks |
| the node's ground, for the next three days | Open-Meteo, for its weather and the CAMS air, and for the sea while the `coast` pack is on, with `FORECAST_OPENMETEO=1` (off by default) and `PACKS_ALLOW_CODE=1`, every six hours | the node's own point unrounded and the centres of the cells round it, 7 points on a community node and 19 on a city or region node, and a wind field of 65 points within `FORECAST_WIND_KM` (30) |
| a species name | api.gbif.org, when a plant or animal in an image is given a scientific name, with `SPECIES_MATCH=on` (off by default) | the scientific name only, never the picture or where it was taken. GBIF sees this house's internet address and the names asked |
| the country's list of introduced and invasive species | api.gbif.org and the checklist's archive host, weekly, with `SPECIES_MATCH=on` and the `eyes` pack on | which country's GRIIS checklist to read (the country comes from `NODE_TZ`) |
| the open records others made nearby | api.gbif.org, weekly, with `SPECIES_MATCH=on` and the `eyes` pack on | the shape of each of the node's seven resolution-8 cells, which places the node to within about 2 km. Only counts come back, from CC0 and CC BY records |
| who lives here, in an alert | the household's own Telegram chats, only for an act-level heat or air alert that weighs on someone ticked in Node › What it remembers | one line naming who ("a child under five"), never a name or an age; never over the mesh, Reticulum or Home Assistant, and never in the stored alert text |
| the ground's height | copernicus-dem-30m.s3.amazonaws.com, once, only when somebody runs `planetai run terrain fetch` and `TERRAIN_DEM_PATH` is blank | the one to four 1° tiles the square touches, and the parts of them that hold the node's square, `TERRAIN_RADIUS_M` (5000) round it |
| the square the node's own map covers | build.protomaps.com and OpenAerialMap (`planetai run place basemap`) or Earth Engine under the node's own project (`planetai run earth-engine basemap`), once, only when somebody runs the command | the tiles, the finest of them `GROUND_RADIUS_KM` (12) round the node; afterwards the node serves the map at `/ground/*` and sends nothing |
| the square being looked at | a tile server, per tile, only with `MAP_TILES=on` | the tile's own square; `off` (the default) draws from the node's local copy of OpenStreetMap |
| a question to the bot | an online model, only if you gave it a key and changed `AGENT_PREFER` from its default, `private` | the question and the tool results the model asked for |
| a question in the dashboard's ask pane | the model Set up names: this machine, one on your network, or an online provider only with `AGENT_PREFER` set to `fallback` or `strongest` | the question and the page's own sentences and numbers, with no position, name or id; the node keeps no transcript |
| an offer | anyone, while the `things` pack is on: `GET /offers` at every level, and the daily export | only a thing the household marked lend or give: its class, name, condition and count, at the node's own resolution-8 cell, with a link to the node's Telegram bot. Never a note, a photo, how often it is used or a point |
| raw readings | nobody | nothing |
| a `private` reading | nobody: not the export, a parent, the report bundle or any agent, and on this machine's raw routes only the admin token | it is used on the page, by rules and by cells; Home Assistant discovery, the household's own automation, still receives it |

At `AGENT_PREFER=private`, the default, the ask pane's model is on this machine or your network and the
conversation never leaves: a remote model at an address outside your network is not used. An online model is a choice somebody here makes in Set up, and the pane says so on every
answer. A remote agent gets the MCP surface instead, which rounds, refuses and audits. See [Ask the node](ask.md).

> **Gap in v0.91.0.** The `coast` pack, the `forecast` pack when `FORECAST_OPENMETEO=1`, and the first start's 92 days
> of CAMS history send the node's full-precision coordinates to Open-Meteo; only the weather adapter in
> `app/sources.py` and the `air-quality` pack's current reading round them. The first start also sends them to NASA
> POWER and OSM Nominatim. The containers run as root.

## Signed updates

A node runs the code it is sent, so what it trusts is part of its boundary. `install`, and `planetai update` on a
node installed from the tarball, download the release, check its published SHA256, and then check an `ssh-keygen
-Y` signature against one key: principal `fabcity`, namespace `planetai-node`. The public line is built into
`install`, `update.sh` and `bin/planetai`, so a node can check an update before it has one, and it is published in
[tools/allowed_signers](../../tools/allowed_signers). The checksum proves the bytes arrived whole. The signature
names who built them, with a key that is not on the web server.

A download that does not verify is not installed. The node says `this download is not signed by the PLANETAI
release key. Nothing was installed and nothing on this machine changed.`, then asks you to try again on a network
you trust and to tell us if it happens twice.

`planetai version` prints what this node trusts, and `planetai doctor` says whether the last update checked:

```
planetai-node v0.91.0  ·  a Fab City project  ·  <name> @ <city>
  updates signed by  fabcity  SHA256:OrUQK/jsjNjpei1U8B5tyuEWY36/gwYWXrgVF+5ycIY
```

Compare that fingerprint from a machine that is not the node. If they disagree, something replaced the node's copy
of the CLI, and the CLI is not the thing to ask. Every release is published twice from the same bytes with the same
signature, at `planetai.fab.city/node0/get` and as a GitHub Release, and `PLANETAI_GET` points an install at the
second. `PLANETAI_UNSIGNED=1` installs a tarball nobody signed, with a red warning, and the doctor's signature row
stays red until a signed update. How to report a security problem is in [SECURITY.md](../../SECURITY.md).

## Reaching it from elsewhere

Use Tailscale. `planetai mesh` joins the tailnet under the node's name, and your devices reach the node at its
MagicDNS name, `<name>.<your-tailnet>.ts.net` (recorded as `MESH_NAME`), with no open port, encrypted by the
tailnet. The node has no TLS of its own, so never put it behind a port forward, ngrok or a public reverse proxy.
[Networking](networking.md) has the setup, and the self-hosted alternative to Tailscale's coordinator.

There is no loopback-only level. On a network the household does not trust, keep `SHARE_LEVEL` at `off` and give
tokens only to your own devices; the NAS pull, the phones, Home Assistant and MCP all read over the LAN.

## Where this leads

With the boundary set, the node can take its place in a district: [Federation](federation.md) is what a child sends
its parent and what the parent refuses. To hand the node to an agent without handing it the house, read
[Agents](agents.md).
