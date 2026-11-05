#!/bin/sh
# Grafana's login to this node's database (docker-compose.yml, profile grafana). planetai_grafana is a member of
# planetai_ro, which init.sql grants SELECT on every table but settings, captures, things, learnings, digests and
# household, and nothing else; on top of that every
# session it opens is read-only, a query stops at 30 s so a month-wide panel cannot starve the node, and it holds
# four connections at most. The session timezone is the node's, as app/main.py::db() sets it, so a panel's hour
# of day is the household's hour. Run on every start; the password is made once and kept in the volume.
set -eu
[ -s /secret/db_password ] || tr -dc 'a-f0-9' </dev/urandom | head -c 40 >/secret/db_password
chmod 644 /secret/db_password   # grafana runs as uid 472
psql -q -v ON_ERROR_STOP=1 -v pw="$(cat /secret/db_password)" -v tz="$NODE_TZ" <<'SQL'
SET client_min_messages = warning;   -- a second start re-grants, and says so
SELECT 'CREATE ROLE planetai_grafana' WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'planetai_grafana') \gexec
ALTER ROLE planetai_grafana LOGIN PASSWORD :'pw' CONNECTION LIMIT 4;
GRANT planetai_ro TO planetai_grafana;
ALTER ROLE planetai_grafana SET default_transaction_read_only = on;
ALTER ROLE planetai_grafana SET statement_timeout = '30s';
ALTER ROLE planetai_grafana SET timezone = :'tz';
SQL
echo "planetai_grafana ready"
