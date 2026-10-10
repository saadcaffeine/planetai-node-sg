#!/usr/bin/env bash
# Node #1's last 31 days, read-only, for tools/replay_alerts.py. Household data: write it outside the repository.
#   tools/fetch_replay.sh /some/scratch/dir
# Every query runs in a read-only transaction. Nothing on the node is written, restarted or imported.
# readings.tsv and sensors.tsv are what tests/trustdb.py readings_from/sensors_from parse: tab-separated, UTC
# timestamps as tz-aware ISO 8601, booleans t/f. alerts.tsv is node #1's own alert history for the same window,
# to calibrate the replayed old engine against; channel_roles.tsv is the node's, to compare with config/channels.yml.
set -euo pipefail
out="${1:?usage: tools/fetch_replay.sh DIR}"; mkdir -p "$out"
user=$(ssh mini 'export PATH="/opt/homebrew/bin:/usr/local/bin:$HOME/.local/bin:$PATH"; docker exec planetai-db-1 printenv POSTGRES_USER')
dbname=$(ssh mini 'export PATH="/opt/homebrew/bin:/usr/local/bin:$HOME/.local/bin:$PATH"; docker exec planetai-db-1 printenv POSTGRES_DB')
remote="export PATH=\"/opt/homebrew/bin:/usr/local/bin:\$HOME/.local/bin:\$PATH\";
  docker exec -i planetai-db-1 psql -U $user -d $dbname -Atq -v ON_ERROR_STOP=1"
iso="'YYYY-MM-DD\"T\"HH24:MI:SS.US\"+00:00\"'"
q() {
  local sql=${1//$'\n'/ }    # \copy takes one line
  ssh mini "$remote" <<SQL
SET default_transaction_read_only = on;
\copy ($sql) TO STDOUT
SQL
}
q "SELECT to_char(r.ts AT TIME ZONE 'UTC', $iso), r.sensor_id, r.metric, r.value FROM readings r JOIN sensors s USING (sensor_id)
   WHERE r.ts > now() - interval '31 days' AND s.kind = 'sensor' AND r.metric IN ('temp','humidity','pm25')
     AND r.value IS NOT NULL ORDER BY r.ts" > "$out/readings.tsv"
q "SELECT sensor_id, source, coalesce(name, ''), coalesce(lat, 0), coalesce(lon, 0), indoor, local, kind
   FROM sensors WHERE kind = 'sensor'" > "$out/sensors.tsv"
q "SELECT to_char(ts AT TIME ZONE 'UTC', $iso), rule_id, coalesce(sensor_id, ''), coalesce(level, '')
   FROM alerts WHERE ts > now() - interval '31 days' ORDER BY ts" > "$out/alerts.tsv"
q "SELECT source, metric, role FROM channel_roles ORDER BY 1, 2" > "$out/channel_roles.tsv"
wc -l "$out"/*.tsv
