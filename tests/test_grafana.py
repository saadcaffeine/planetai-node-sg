"""The grafana profile (docs/site/grafana.md): the keeper's own panels over this node's readings, beside the dashboard.

What has to stay true for it to be safe to ship: it is off unless asked for, it reaches the database only as a
read-only login that cannot see settings, it is not handed the node's secrets, and the starter dashboard does not
draw tomorrow's forecast as a measurement or bridge a sensor's silence with a line. Proven against a copy of node
#1's database on 24 Oct 2026; this holds the files to what was proven.

    python3 tests/test_grafana.py
"""
import json
import re
import sys

import yaml

fails = []


def check(ok, msg):
    print(("  ok   " if ok else "  FAIL ") + msg)
    if not ok:
        fails.append(msg)


compose = yaml.safe_load(open("docker-compose.yml"))
svc = compose["services"]
role, graf = svc.get("grafana-role", {}), svc.get("grafana", {})

print("compose: off unless asked for, and handed nothing it does not read")
check(role.get("profiles") == ["grafana"] and graf.get("profiles") == ["grafana"], "both services are in the grafana profile only")
check("env_file" not in role and "env_file" not in graf, "neither is handed the whole .env")
check(set(role.get("environment", {})) == {"PGHOST", "PGUSER", "PGDATABASE", "PGPASSWORD", "NODE_TZ"},
      "grafana-role reads exactly the five keys it needs")
check(not any("POSTGRES" in k or "TOKEN" in k for k in graf.get("environment", {})), "grafana holds no database password or node token")
check(graf.get("ports") == ["${GRAFANA_BIND:-127.0.0.1}:${GRAFANA_PORT:-3000}:3000"], "grafana listens on loopback unless GRAFANA_BIND says otherwise")
check(re.fullmatch(r"grafana/grafana-oss:\d+\.\d+\.\d+", graf.get("image", "")) is not None, "the grafana image is pinned to a release")
check(graf.get("depends_on", {}).get("grafana-role", {}).get("condition") == "service_completed_successfully",
      "grafana waits for its login to exist")
check({"grafana", "grafana-secret"} <= set(compose.get("volumes", {})), "its two volumes are declared")
check(any(v.endswith(":/secret:ro") for v in graf.get("volumes", [])), "grafana reads the password volume read-only")

print("role.sh: a member of planetai_ro, and less")
sh = open("config/grafana/role.sh").read()
check("GRANT planetai_ro TO planetai_grafana;" in sh, "planetai_grafana inherits planetai_ro, which init.sql keeps off settings")
check("default_transaction_read_only = on" in sh, "every session it opens is read-only")
check("statement_timeout = '30s'" in sh, "a query stops at 30 s")
check("CONNECTION LIMIT 4" in sh, "four connections at most")
check(not re.search(r"\bGRANT\s+(SELECT|ALL|INSERT|UPDATE|DELETE)\b|SUPERUSER|CREATEROLE|\bsettings\b", sh.split("set -eu", 1)[1]),
      "it grants nothing of its own")
check(":'pw'" in sh and "<<'SQL'" in sh, "the password reaches psql as a variable, never through the shell")

print("provisioning: the node's database, as that login")
ds = yaml.safe_load(open("config/grafana/provisioning/datasources/node.yml"))["datasources"][0]
check(ds["uid"] == "planetai-node" and ds["user"] == "planetai_grafana", "the datasource logs in as planetai_grafana")
check(ds["secureJsonData"]["password"] == "$__file{/secret/db_password}", "its password comes from the volume, not from .env")
check(ds.get("editable") is False, "it cannot be edited into another login from the UI")
prov = yaml.safe_load(open("config/grafana/provisioning/dashboards/node.yml"))["providers"][0]
check(prov["allowUiUpdates"] is False and prov["options"]["path"] == "/etc/grafana/dashboards",
      "the starter is replaced on update, so a keeper's edits go to their own copy")

print("starter dashboard: honest by default, and nobody's house but this one")
raw = open("config/grafana/dashboards/node.json").read()
dash = json.loads(raw)
panels = dash["panels"]
check(len({p["id"] for p in panels}) == len(panels), "panel ids are unique")
queries = [(p["title"], t["rawSql"]) for p in panels for t in p["targets"]] + [(v["name"], v["query"]) for v in dash["templating"]["list"]]
check(all(t["datasource"]["uid"] == "planetai-node" for p in panels for t in p["targets"]), "every panel reads the node's datasource")
# The forecast pack stores each hour at the time it is FOR, days ahead (packs/forecast/adapter.py). A picker set past
# now must not draw that as measured.
future = [n for n, q in queries if "readings" in q and "ts <= now()" not in q]
check(not future, "every query that reads readings stops at now()" + (f": {future}" if future else ""))
check(all("$__timeFilter(r.ts)" in t["rawSql"] for p in panels for t in p["targets"]), "every panel follows the time picker")
lines = [p["title"] for p in panels if p["type"] == "timeseries" and not p["fieldConfig"]["defaults"].get("custom", {}).get("insertNulls")]
check(not lines, "every line breaks at a silence instead of drawing across it" + (f": {lines}" if lines else ""))
node1 = [w for w in ("Kids", "Backyard", "Studio", "Living Room", "msh-", "sc-1", "Asia/Makassar", "bayu") if w in raw]
check(not node1, "nothing in it names node #1's rooms, sensors or timezone" + (f": {node1}" if node1 else ""))
check(dash["title"].endswith("no provenance"), "its title says it carries none of the page's rules")
check(all("opened_at <= now()" in a["target"]["rawSql"] for a in dash["annotations"]["list"]), "the alert annotations stop at now() too")
check("current_setting('TimeZone')" in raw, "hour of day is the session's, which role.sh sets to NODE_TZ")

print("cli: planetai grafana, and remove knows its volumes")
cli = open("bin/planetai").read()
check("cmd_grafana()" in cli and 'grafana) shift; cmd_grafana "$@";;' in cli and "profiles_add grafana" in cli, "planetai grafana turns the profile on")
check("DROP ROLE IF EXISTS planetai_grafana" in cli and "grep -vx grafana" in cli, "planetai grafana off takes the profile out and drops the login")
check("ipfsdata grafana grafana-secret; do" in cli and "ipfsdata|grafana|grafana-secret)$" in cli, "planetai remove names both volumes")

print(f"grafana: {'every check passed' if not fails else str(len(fails)) + ' failed'}")
sys.exit(1 if fails else 0)
