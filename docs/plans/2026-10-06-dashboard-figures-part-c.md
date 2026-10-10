# Dashboard figures, part C: Grafana for the keeper — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `planetai grafana on` starts a Grafana beside the node, bound to this machine only, reading Postgres as a
read-only login, with two provisioned dashboards (readings over 30 and 90 days with gaps kept as gaps, and the alert
events); `planetai grafana off` removes it. It is the keeper's view and never the household's page.

**Architecture:** One more optional compose service behind the `grafana` profile, the pattern `mqtt`, `ipfs` and
`reticulum` already use. A login role `planetai_grafana` that is a member of the existing `planetai_ro` (SELECT on
every table but `settings`), created by the CLI rather than `init.sql`, because its password lives in `.env`.
Provisioning files in `config/grafana/` are mounted read-only. Nothing in the app changes.

**Tech stack:** Docker Compose, `grafana/grafana:13.2.3` (multi-arch: amd64, arm64, arm), Postgres 16, bash
(`bin/planetai`).

**Spec:** `docs/SPEC_dashboard_figures.md` §5. Independent of parts A and B; it may land first.

## Global constraints

- Work in your own git worktree off `origin/main`, never in `planetai-node-main`.
- `make lint && make test` before every commit (the pre-commit hook runs both; allow 300000 ms; never `--no-verify`).
- **No `env_file`** on the new service: `make lint` fails if any service but `app` and `agent` has one. It reads
  exactly the keys listed under its `environment:`.
- **Bound to this machine:** `127.0.0.1:${GRAFANA_PORT:-3000}:3000`, never `3000:3000`. Reaching it from another
  machine is an ssh tunnel; the tailnet is a later decision.
- **Nothing leaves the machine:** update checks, usage reporting, the news feed and plugin pre-install (which
  downloads at start) are switched off. No anonymous access, no sign-up.
- **No change to `init.sql`, `app/`, `packs/` or the page.** The role is created and dropped by the CLI.
- `.env.example` is the authority for defaults: a new key there means `python3 tools/gen_defaults.py` rewrites
  `data/env_defaults.yml` in the same commit, and `docs/site/configuration.md` documents it.
- In `bin/planetai`, keep every command on one line in the dispatch `case` as the others are.
- Commit messages end with a blank line and `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Files

| file | what changes |
|---|---|
| `docker-compose.yml` | the `grafana` service and its volume |
| `.env.example`, `data/env_defaults.yml` | `GRAFANA_PORT`, `GRAFANA_DB_PASSWORD`, `GRAFANA_ADMIN_PASSWORD` |
| `config/grafana/provisioning/datasources/planetai.yml` (new) | the Postgres datasource, as `planetai_grafana` |
| `config/grafana/provisioning/dashboards/planetai.yml` (new) | where the dashboards are read from |
| `config/grafana/dashboards/readings.json` (new) | readings per station and metric |
| `config/grafana/dashboards/events.json` (new) | the alert events and their messages |
| `bin/planetai` | `profiles_rm`, `cmd_grafana`, the dispatch line and the usage line |
| `docs/site/cli.md`, `docs/site/configuration.md`, `docs/site/dashboard.md`, `CHANGELOG.md` | the command, the keys, a section |
| `tools/check_docs.py` | remove `config/grafana/` and `grafana` from the spec's `PROPOSED` entry |

---

### Task 1: the service and its keys

**Files:**
- Modify: `docker-compose.yml` (after the `reticulum` service, and `volumes:`)
- Modify: `.env.example`, `data/env_defaults.yml` (generated), `docs/site/configuration.md`

- [ ] **Step 1: Write the failing check.** Run it from the worktree root. It is the whole contract of this task:

```bash
python3 - <<'EOF'
import yaml
c = yaml.safe_load(open("docker-compose.yml"))
g = c["services"]["grafana"]
assert g["image"] == "grafana/grafana:13.2.3", g["image"]
assert g["profiles"] == ["grafana"] and "env_file" not in g
assert g["ports"] == ["127.0.0.1:${GRAFANA_PORT:-3000}:3000"], g["ports"]
e = g["environment"]
for k, v in {"GF_ANALYTICS_REPORTING_ENABLED": "false", "GF_ANALYTICS_CHECK_FOR_UPDATES": "false",
             "GF_ANALYTICS_CHECK_FOR_PLUGIN_UPDATES": "false", "GF_NEWS_NEWS_FEED_ENABLED": "false",
             "GF_PLUGINS_PREINSTALL_DISABLED": "true", "GF_AUTH_ANONYMOUS_ENABLED": "false",
             "GF_USERS_ALLOW_SIGN_UP": "false"}.items():
    assert str(e.get(k)).lower() == v, (k, e.get(k))
assert "grafana" in c["volumes"]
print("grafana: pinned, behind its profile, on this machine only, saying nothing outward")
EOF
```

  Expected now: `KeyError: 'grafana'`.

- [ ] **Step 2: The service.** In `docker-compose.yml`, after the `reticulum` service and before `volumes:`:

```yaml
  # The keeper's view (docs/SPEC_dashboard_figures.md §5): readings over months and the alert events, for somebody
  # debugging a sensor. It is not the household's page and carries none of its provenance rules; each dashboard's
  # title says so. `planetai grafana on` sets it up: the profile, the two passwords, and the read-only login it uses.
  # No env_file (F2 of the 18 September design review): it reads the keys below and nothing else.
  grafana:
    image: grafana/grafana:13.2.3     # pinned 6 Oct 2026; grafana/grafana is the open-source image
    profiles: [grafana]
    restart: unless-stopped
    ports: ["127.0.0.1:${GRAFANA_PORT:-3000}:3000"]   # this machine only; another machine reaches it by ssh tunnel
    environment:
      GF_SECURITY_ADMIN_USER: admin
      GF_SECURITY_ADMIN_PASSWORD: ${GRAFANA_ADMIN_PASSWORD:-}
      GRAFANA_DB_PASSWORD: ${GRAFANA_DB_PASSWORD:-}   # read by provisioning/datasources/planetai.yml
      GF_USERS_ALLOW_SIGN_UP: "false"
      GF_AUTH_ANONYMOUS_ENABLED: "false"
      # Nothing leaves this machine: no update checks, no usage reports, no news feed, and no plugin download at start.
      GF_ANALYTICS_REPORTING_ENABLED: "false"
      GF_ANALYTICS_CHECK_FOR_UPDATES: "false"
      GF_ANALYTICS_CHECK_FOR_PLUGIN_UPDATES: "false"
      GF_NEWS_NEWS_FEED_ENABLED: "false"
      GF_PLUGINS_PREINSTALL_DISABLED: "true"
    volumes:
      - ./config/grafana/provisioning:/etc/grafana/provisioning:ro
      - ./config/grafana/dashboards:/var/lib/grafana/dashboards:ro
      - grafana:/var/lib/grafana       # its own sqlite: users and preferences. Removing it resets the admin password.
    depends_on: [db]
    logging: { driver: json-file, options: { max-size: "5m", max-file: "2" } }
```

  and add `  grafana: {}` to the top-level `volumes:` list.

- [ ] **Step 3: The keys.** In `.env.example`, directly below the `IPFS_PUBLISH=0` block (one blank line above):

```
# Grafana, the keeper's view beside the dashboard (docs/site/dashboard.md). `planetai grafana on` fills the two
# passwords and adds the `grafana` profile; leave them blank by hand. GRAFANA_PORT is the port on this machine only.
GRAFANA_PORT=3000
GRAFANA_DB_PASSWORD=
GRAFANA_ADMIN_PASSWORD=
```

  Then run `python3 tools/gen_defaults.py` to rewrite `data/env_defaults.yml`.

- [ ] **Step 4: Document them.** In `docs/site/configuration.md`:
  - In the `COMPOSE_PROFILES` row, the values become `comma-separated mqtt, agent, ipfs, reticulum, grafana` and the
    sentence "Set by `planetai meshtastic`, `agent local`, `ipfs` and `reticulum`" becomes "Set by `planetai
    meshtastic`, `agent local`, `ipfs`, `reticulum` and `grafana on`".
  - Directly below the `IPFS_PUBLISH` row, three rows:

```
| `GRAFANA_PORT` | `3000` | port | The port Grafana answers on, on this machine only (`127.0.0.1`). Another machine reaches it through an ssh tunnel. | bootstrap |
| `GRAFANA_DB_PASSWORD` | blank; `planetai grafana on` sets it | secret | The password of `planetai_grafana`, the read-only database login Grafana uses (SELECT on every table but `settings`). | bootstrap · secret |
| `GRAFANA_ADMIN_PASSWORD` | blank; `planetai grafana on` sets it | secret | Grafana's own `admin` password. `planetai grafana on` prints it once. | bootstrap · secret |
```

  Match the exact column count and scope words of the rows around them; if `secret` is not a scope word that page
  already uses, use the one the `ADMIN_TOKEN` row uses.

- [ ] **Step 5: Run the check and the gates.**
  Run: the Step 1 check, then `python3 tools/gen_defaults.py --check && python3 tools/check_docs.py && make lint`
  Expected: `grafana: pinned, behind its profile, on this machine only, saying nothing outward`, then no `x`, lint `ok`.

- [ ] **Step 6: Commit.**

```bash
git add docker-compose.yml .env.example data/env_defaults.yml docs/site/configuration.md
git commit -m "compose: a grafana profile for the keeper, on this machine only, saying nothing outward

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: the datasource and the two dashboards

**Files:**
- Create: `config/grafana/provisioning/datasources/planetai.yml`
- Create: `config/grafana/provisioning/dashboards/planetai.yml`
- Create: `config/grafana/dashboards/readings.json`, `config/grafana/dashboards/events.json`

- [ ] **Step 1: Write the failing check.**

```bash
python3 - <<'EOF'
import json, yaml
ds = yaml.safe_load(open("config/grafana/provisioning/datasources/planetai.yml"))["datasources"][0]
assert ds["type"] == "grafana-postgresql-datasource" and ds["user"] == "planetai_grafana" and ds["url"] == "db:5432"
assert ds["secureJsonData"]["password"] == "$GRAFANA_DB_PASSWORD" and ds["editable"] is False
prov = yaml.safe_load(open("config/grafana/provisioning/dashboards/planetai.yml"))["providers"][0]
assert prov["options"]["path"] == "/var/lib/grafana/dashboards" and prov["allowUiUpdates"] is False
for f in ("readings", "events"):
    d = json.load(open(f"config/grafana/dashboards/{f}.json"))
    assert d["title"].endswith("keeper's view · no provenance"), d["title"]
    assert d["uid"] == f"planetai-{f}"
r = json.load(open("config/grafana/dashboards/readings.json"))
c = r["panels"][0]["fieldConfig"]["defaults"]["custom"]
assert c["spanNulls"] is False and c["insertNulls"] == 3600000, "a silent hour must be a gap, not a line drawn across it"
assert any(a["name"] == "events" for a in r["annotations"]["list"])
print("grafana provisioning: read-only login, two dashboards that say what they are, gaps kept")
EOF
```

  Expected now: `FileNotFoundError`.

- [ ] **Step 2: The datasource.** `config/grafana/provisioning/datasources/planetai.yml`:

```yaml
# The node's Postgres, as planetai_grafana: a member of planetai_ro, so SELECT on every table but `settings`
# (init.sql). `planetai grafana on` creates that login with GRAFANA_DB_PASSWORD; Grafana expands the variable here.
apiVersion: 1
datasources:
  - name: planetai
    uid: planetai-pg
    type: grafana-postgresql-datasource
    access: proxy
    url: db:5432
    user: planetai_grafana
    isDefault: true
    editable: false
    jsonData:
      database: planetai
      sslmode: disable
      postgresVersion: 1600
      timescaledb: false
      timeInterval: 1h
    secureJsonData:
      password: $GRAFANA_DB_PASSWORD
```

- [ ] **Step 3: The provider.** `config/grafana/provisioning/dashboards/planetai.yml`:

```yaml
# The two dashboards ship with the node and are read from disk on every start. Editing them in Grafana does not
# stick (allowUiUpdates: false): change the JSON in config/grafana/dashboards/ instead, so every node has the same view.
apiVersion: 1
providers:
  - name: planetai
    folder: PLANETAI
    type: file
    disableDeletion: true
    allowUiUpdates: false
    options:
      path: /var/lib/grafana/dashboards
```

- [ ] **Step 4: The readings dashboard.** `config/grafana/dashboards/readings.json`:

```json
{
  "uid": "planetai-readings",
  "title": "Readings · keeper's view · no provenance",
  "description": "Hourly means per station and metric, from readings_1h. Not the household's page: nothing here carries the node's provenance words, and a model, a relay and a kit in a room are drawn alike. A silent hour is a gap.",
  "tags": ["planetai"],
  "timezone": "browser",
  "schemaVersion": 39,
  "editable": false,
  "time": { "from": "now-30d", "to": "now" },
  "timepicker": { "refresh_intervals": ["5m", "15m", "1h"] },
  "templating": {
    "list": [
      {
        "name": "metric", "label": "metric", "type": "query",
        "datasource": { "type": "grafana-postgresql-datasource", "uid": "planetai-pg" },
        "query": "SELECT DISTINCT metric FROM readings WHERE ts > now() - interval '7 days' ORDER BY 1",
        "current": { "text": "pm25", "value": "pm25" },
        "refresh": 1
      },
      {
        "name": "station", "label": "station", "type": "query", "multi": true, "includeAll": true,
        "datasource": { "type": "grafana-postgresql-datasource", "uid": "planetai-pg" },
        "query": "SELECT s.name AS __text, s.sensor_id AS __value FROM sensors s WHERE s.kind = 'sensor' AND EXISTS (SELECT 1 FROM readings r WHERE r.sensor_id = s.sensor_id AND r.metric = '$metric' AND r.ts > now() - interval '90 days') ORDER BY s.local DESC, s.name",
        "current": { "text": "All", "value": "$__all" },
        "refresh": 2
      }
    ]
  },
  "annotations": {
    "list": [
      {
        "name": "events", "enable": true, "iconColor": "rgba(230, 32, 56, 0.6)",
        "datasource": { "type": "grafana-postgresql-datasource", "uid": "planetai-pg" },
        "rawQuery": "SELECT opened_at AS time, COALESCE(cleared_at, now()) AS timeend, issue || ' · ' || kind AS text FROM alert_events WHERE $__timeFilter(opened_at) ORDER BY 1"
      }
    ]
  },
  "panels": [
    {
      "type": "timeseries",
      "title": "$metric, hourly mean per station",
      "gridPos": { "x": 0, "y": 0, "w": 24, "h": 14 },
      "datasource": { "type": "grafana-postgresql-datasource", "uid": "planetai-pg" },
      "targets": [
        {
          "refId": "A", "format": "time_series", "rawQuery": true, "editorMode": "code",
          "rawSql": "SELECT r.bucket AS time, s.name AS metric, r.mean AS value FROM readings_1h r JOIN sensors s USING (sensor_id) WHERE $__timeFilter(r.bucket) AND r.metric = '$metric' AND r.sensor_id IN ($station) ORDER BY 1"
        }
      ],
      "fieldConfig": {
        "defaults": {
          "custom": { "drawStyle": "line", "lineWidth": 1, "spanNulls": false, "insertNulls": 3600000, "showPoints": "never" }
        },
        "overrides": []
      },
      "options": { "legend": { "displayMode": "table", "placement": "right", "calcs": ["min", "max", "mean"] }, "tooltip": { "mode": "multi" } }
    },
    {
      "type": "table",
      "title": "When each station was last heard",
      "gridPos": { "x": 0, "y": 14, "w": 24, "h": 9 },
      "datasource": { "type": "grafana-postgresql-datasource", "uid": "planetai-pg" },
      "targets": [
        {
          "refId": "A", "format": "table", "rawQuery": true, "editorMode": "code",
          "rawSql": "SELECT s.name, s.sensor_id, s.local, s.indoor, max(r.ts) AS last_heard, now() - max(r.ts) AS silent_for FROM sensors s JOIN readings r USING (sensor_id) WHERE s.kind = 'sensor' AND r.ts > now() - interval '90 days' GROUP BY 1, 2, 3, 4 ORDER BY last_heard"
        }
      ]
    }
  ]
}
```

- [ ] **Step 5: The events dashboard.** `config/grafana/dashboards/events.json`:

```json
{
  "uid": "planetai-events",
  "title": "Alert events · keeper's view · no provenance",
  "description": "Every alert event and every message the engine decided, sent or held (alert_events, event_messages). In ALERT_ENGINE=shadow nothing was sent, and the sent column says so.",
  "tags": ["planetai"],
  "timezone": "browser",
  "schemaVersion": 39,
  "editable": false,
  "time": { "from": "now-30d", "to": "now" },
  "panels": [
    {
      "type": "table",
      "title": "Events",
      "gridPos": { "x": 0, "y": 0, "w": 24, "h": 10 },
      "datasource": { "type": "grafana-postgresql-datasource", "uid": "planetai-pg" },
      "targets": [
        {
          "refId": "A", "format": "table", "rawQuery": true, "editorMode": "code",
          "rawSql": "SELECT id, issue, kind, level, opened_at, cleared_at, cleared_at - opened_at AS lasted, peak, array_to_string(rooms, ', ') AS rooms, action_id FROM alert_events WHERE $__timeFilter(opened_at) ORDER BY opened_at DESC"
        }
      ]
    },
    {
      "type": "table",
      "title": "Messages, sent or held",
      "gridPos": { "x": 0, "y": 10, "w": 24, "h": 12 },
      "datasource": { "type": "grafana-postgresql-datasource", "uid": "planetai-pg" },
      "targets": [
        {
          "refId": "A", "format": "table", "rawQuery": true, "editorMode": "code",
          "rawSql": "SELECT m.ts, e.issue, e.kind, m.sent, m.text FROM event_messages m JOIN alert_events e ON e.id = m.event_id WHERE $__timeFilter(m.ts) ORDER BY m.ts DESC"
        }
      ]
    }
  ]
}
```

- [ ] **Step 6: Check the column names against the schema.** The queries name `alert_events.(id, issue, kind, level,
  opened_at, cleared_at, peak, rooms, action_id)`, `event_messages.(event_id, ts, sent, text)`,
  `readings.(sensor_id, metric, ts)`, `readings_1h.(bucket, sensor_id, metric, mean)` and
  `sensors.(sensor_id, name, kind, local, indoor)`.
  Run: `grep -nE "CREATE TABLE IF NOT EXISTS (alert_events|event_messages)|CREATE VIEW readings_1h" -A14 init.sql`
  Expected: every named column appears. If one does not, fix the query, not the schema.

- [ ] **Step 7: Run the Step 1 check.** Expected: `grafana provisioning: read-only login, two dashboards that say what
  they are, gaps kept`.

- [ ] **Step 8: Commit.**

```bash
git add config/grafana
git commit -m "grafana: a read-only datasource and two dashboards that say what they are, gaps kept as gaps

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: `planetai grafana on` and `off`

**Files:**
- Modify: `bin/planetai` (`profiles_rm` beside `profiles_add`; `cmd_grafana` after `cmd_ipfs`; the dispatch and the
  usage header)
- Modify: `docs/site/cli.md`, `tools/check_docs.py`

- [ ] **Step 1: Write the failing check.**

```bash
bash -n bin/planetai && grep -q '^cmd_grafana()' bin/planetai && grep -qE '^\s+grafana\) shift; cmd_grafana "\$@";;' bin/planetai \
  && grep -q '^profiles_rm()' bin/planetai && echo "dispatched" || echo "MISSING"
```

  Expected now: `MISSING`.

- [ ] **Step 2: `profiles_rm`.** In `bin/planetai`, directly below the `profiles_add()` line:

```bash
profiles_rm() { local cur; cur="$(envget COMPOSE_PROFILES)"; cur="$(printf ',%s,' "$cur" | sed "s/,$1,/,/g; s/^,//; s/,\$//")"; envset COMPOSE_PROFILES "$cur"; }
```

- [ ] **Step 3: `cmd_grafana`.** Directly after `cmd_ipfs()`'s closing brace:

```bash
# ---------------------------------------------------------------- grafana: the keeper's view, beside the page
# docs/SPEC_dashboard_figures.md §5. The login is created here, not in init.sql, because its password lives in .env
# and init.sql cannot read it. planetai_grafana is a member of planetai_ro: SELECT on every table but settings.
cmd_grafana() {
  case "${1:-on}" in
    on)
      step "Grafana"
      echo "  Readings over months and the alert events, for somebody debugging a sensor. It is the keeper's view,"
      echo "  not the household's page: it carries none of the page's provenance, and each dashboard says so."
      echo
      local dbpw adminpw; dbpw="$(envget GRAFANA_DB_PASSWORD)"; adminpw="$(envget GRAFANA_ADMIN_PASSWORD)"
      [[ -n "$dbpw" ]] || { dbpw="$(openssl rand -hex 16)"; envset GRAFANA_DB_PASSWORD "$dbpw"; }
      [[ -n "$adminpw" ]] || { adminpw="$(openssl rand -hex 12)"; envset GRAFANA_ADMIN_PASSWORD "$adminpw"; }
      docker compose exec -T db psql -v ON_ERROR_STOP=1 -v pw="$dbpw" -U planetai -d planetai >>"$LOG" 2>&1 <<'SQL' \
        || fail "could not create the read-only login; see $LOG"
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'planetai_grafana') THEN CREATE ROLE planetai_grafana LOGIN; END IF;
END $$;
ALTER ROLE planetai_grafana LOGIN PASSWORD :'pw';
GRANT planetai_ro TO planetai_grafana;
SQL
      profiles_add grafana
      docker compose up -d grafana >>"$LOG" 2>&1 || fail "could not start grafana; see $LOG"
      local p; p="$(envget GRAFANA_PORT)"; p="${p:-3000}"
      local ok=""; for i in $(seq 1 30); do curl -sf "localhost:$p/api/health" >/dev/null 2>&1 && { ok=1; break; }; sleep 2; done
      [[ -n "$ok" ]] || fail "grafana did not come up:  planetai logs grafana"
      say "Grafana is at http://127.0.0.1:$p on this machine (user admin, password $adminpw)"
      echo "  From another machine:  ssh -L $p:127.0.0.1:$p <this machine>   then open http://127.0.0.1:$p"
      echo "  The two dashboards are under PLANETAI. They are read from config/grafana/dashboards/ on every start."
      ;;
    off)
      step "Grafana off"
      docker compose rm -sf grafana >>"$LOG" 2>&1 || true
      profiles_rm grafana
      docker compose exec -T db psql -U planetai -d planetai -c "DROP ROLE IF EXISTS planetai_grafana" >>"$LOG" 2>&1 \
        || warn "could not drop the login planetai_grafana; see $LOG"
      envset GRAFANA_DB_PASSWORD ""; envset GRAFANA_ADMIN_PASSWORD ""
      say "stopped; the read-only login is gone. Its own data (users, preferences) stays in the grafana volume."
      ;;
    *) warn "planetai grafana takes on or off (got: $1)"; return 1;;
  esac
}
```

- [ ] **Step 4: Dispatch it.** In the `case` near the end of `bin/planetai`, directly below `  ipfs) cmd_ipfs;;`:
  `  grafana) shift; cmd_grafana "$@";;`. In the usage comment at the top, below the `planetai ipfs` line:
  `#   planetai grafana [on|off] the keeper's view: readings over months and the alert events, on this machine only`.

- [ ] **Step 5: Document it.** In `docs/site/cli.md`, in the table under `## Storage and the commons` (where
  `planetai ipfs` is), add a row in that table's own column shape:
  `| \`planetai grafana [on|off]\` | Starts Grafana (profile \`grafana\`) on this machine only, with a read-only database login and two dashboards: readings per station over 30 and 90 days, and the alert events. Prints the address and the admin password once. \`off\` stops it and drops the login. It is the keeper's view, not the household's page. |`
  (add a third cell if that table has three columns, matching its neighbours). In `tools/check_docs.py`, remove
  `"config/grafana/", "grafana"` from the `docs/SPEC_dashboard_figures.md` entry of `PROPOSED`.

- [ ] **Step 6: Run the check and the gates.**
  Run: the Step 1 check, then `python3 tools/check_docs.py && make lint`
  Expected: `dispatched`, no `x`, lint `ok`.

- [ ] **Step 7: Commit.**

```bash
git add bin/planetai docs/site/cli.md tools/check_docs.py
git commit -m "cli: planetai grafana on/off, with a read-only login created and dropped beside it

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: the page that explains it, the PR, and node #1

**Files:**
- Modify: `docs/site/dashboard.md`, `CHANGELOG.md`

- [ ] **Step 1: `docs/site/dashboard.md`.** Add a section at the end, before any closing links section:

```
## Grafana, for the keeper

The dashboard is the household's page: every number on it carries where it came from, and a silent sensor is drawn
as silent. A keeper debugging a sensor, or reading a month, needs a different view. `planetai grafana on` starts
Grafana on this machine only (`http://127.0.0.1:3000`, the port is `GRAFANA_PORT`), reading the database as
`planetai_grafana`, a login that can read every table but `settings` and write nothing. It comes with two
dashboards under PLANETAI: **Readings**, the hourly mean per station for one metric, with alert events marked and a
silent hour drawn as a gap, and a table of when each station was last heard; and **Alert events**, every event and
every message the engine decided, sent or held. Their titles say "keeper's view · no provenance", because they are:
a model, a relay and a kit in a room are drawn alike. From another machine, open an ssh tunnel
(`ssh -L 3000:127.0.0.1:3000 <the node>`). `planetai grafana off` stops it and drops the login. Grafana is told not
to check for updates, report usage, show its news feed or download plugins, so it sends nothing anywhere.
```

- [ ] **Step 2: `CHANGELOG.md`.** Under `## Unreleased`:

```
- `planetai grafana on` starts Grafana beside the node, on this machine only, with a read-only database login and two
  dashboards: readings per station over months, gaps kept as gaps, and the alert events with every message sent or
  held. It is the keeper's view, not the household's page, and says so. `planetai grafana off` removes it.
```

- [ ] **Step 3: Gates and commit.**
  Run: `python3 tools/check_docs.py && make lint && make test`
  Expected: no `x`, lint `ok`, every suite passes.

```bash
git add docs/site/dashboard.md CHANGELOG.md
git commit -m "docs: Grafana, the keeper's view beside the dashboard

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

- [ ] **Step 4: The pull request.** Push and open it against `main`, milestone `v0.79`, label `needs testing`. The
  body says what a keeper gets, that nothing leaves the machine and nothing changes for a household that does not run
  it, and ends with `🤖 Generated with [Claude Code](https://claude.com/claude-code)`. Do not merge: Tomas merges.

- [ ] **Step 5: After Tomas merges, prove it on node #1** (`docs/WORKFLOW.md` §2):

```bash
ssh mini 'export PATH="/opt/homebrew/bin:/usr/local/bin:$HOME/.local/bin:$PATH"; cd ~/planetai/planetai-node && planetai update && planetai grafana on'
```

  Then, from this machine:
  - `ssh -f -N -L 13000:127.0.0.1:3000 mini` and open `http://127.0.0.1:13000`; log in as `admin` with the password
    `planetai grafana on` printed. Do not paste that password into a PR, an issue or a log.
  - **Readings**, metric `pm25`, last 30 days: every local station is listed, the 6 October morning spike is visible,
    and a stretch with no readings is a gap, not a straight line.
  - **Alert events**: the events of 5 and 6 October are rows, and the shadow-period messages read `sent = false`.
  - The login cannot read `settings`. On node #1, without printing the password:
    `ssh mini 'cd ~/planetai/planetai-node && docker compose exec -T -e PGPASSWORD="$(grep ^GRAFANA_DB_PASSWORD= .env | cut -d= -f2)" db psql -U planetai_grafana -h localhost -d planetai -c "SELECT count(*) FROM settings"'`
    must fail with `permission denied for table settings`, and the same with `FROM readings` must answer a count.
  - `ssh mini 'cd ~/planetai/planetai-node && docker compose logs grafana --since 10m | grep -iE "error|grafana.com|update"'`:
    no outbound update or plugin call.
  Then `planetai grafana off` on node #1 if Tomas does not want it kept running, swap the label to `tested: node 1`,
  and leave one comment saying what you saw.
