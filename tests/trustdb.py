"""Run a trust-pack rule over node #1's own readings, in DuckDB.

The rules are Postgres and `make test` has no Postgres, so DuckDB runs the rule text as it ships: the only edit is
`now()`, replaced with the instant the test wants to stand at, so one series can be swept hour by hour. The schema
comes from init.sql (the `readings_1h` view verbatim), the channel roles from config/channels.yml, and the readings
from tests/data/node1-*.tsv — the real series out of node #1's 7 September dump, not numbers typed into a test.

Needs duckdb, dev only: pip install duckdb. A test that cannot import it says so and skips.

**The session time zone is pinned, and it has to be.** `date_trunc('day', ts)` on a timestamptz
buckets by the SESSION's zone, in Postgres and here alike — so a rule that compares days answers
differently on a laptop in Bali and a runner in UTC. That is right on a node, where a household's
day is its own; it is intolerable in a replay, where the same fixture must give the same answer
everywhere. `season`'s suite found it: its episode began on 31 May in WITA and on 1 June in UTC,
so it passed on the author's machine and failed in CI. Every fixture here is node #1's, so the
zone is node #1's. A suite replaying somewhere else passes its own.
"""
from __future__ import annotations

import datetime as dt
import math
import os
import re

import duckdb
import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UTC = dt.timezone.utc
# the last reading in tests/data/node1-readings.tsv: 7 September 2026, 13:14:22 UTC = 21:14 WITA, three minutes
# before the trust pack sent its three wrong warnings.
FIXTURE_NOW = dt.datetime(2026, 9, 7, 13, 14, 22, tzinfo=UTC)
# node #1 is in Ungasan. WITA, +08, and every day a rule buckets is a day as that house lives it.
NODE_TZ = "Asia/Makassar"


def _schema() -> str:
    """init.sql with its line comments stripped. `-- rolling stats are for sensors only;` sits inside the `stats`
    view and ends in a semicolon, which silently truncated the view to its SELECT list."""
    sql = open(os.path.join(ROOT, "init.sql")).read()
    return "\n".join(re.sub(r"--.*$", "", line) for line in sql.splitlines())


def _init_sql() -> str:
    sql = _schema()
    out = []
    for t in ("sensors", "readings", "channel_roles"):
        m = re.search(rf"CREATE TABLE IF NOT EXISTS {t} \(.*?\n\);", sql, re.S)
        out.append(m.group(0).replace("JSONB", "JSON"))
    out.append(re.search(r"CREATE VIEW readings_1h AS.*?;", sql, re.S).group(0))
    return "\n".join(out)


def _stats_sql() -> str:
    """The `stats` view verbatim from init.sql. It carries its own now(), so it is rebuilt per instant rather
    than created once — a rolling view frozen at import time would answer every replayed hour identically."""
    sql = _schema()
    # DuckDB merges a USING column, so the view's `r.sensor_id` will not bind in its own GROUP BY. An explicit
    # ON join is the same join; nothing else about the view is touched.
    return (re.search(r"CREATE VIEW stats AS.*?;", sql, re.S).group(0)
            .replace("JOIN sensors s USING (sensor_id)", "JOIN sensors s ON s.sensor_id = r.sensor_id"))


def _measures_sql() -> tuple[str, str]:
    """recent_15m and usual_by_hour verbatim from init.sql, for DuckDB. The materialized view becomes a table built
    at the replayed instant (DuckDB has no materialized views), and `WITH NO DATA` goes with it."""
    sql = _schema()
    recent = re.search(r"CREATE VIEW recent_15m AS.*?;", sql, re.S).group(0)
    usual = re.search(r"CREATE MATERIALIZED VIEW usual_by_hour AS(.*?)WITH NO DATA;", sql, re.S).group(1)
    return recent, "CREATE OR REPLACE TABLE usual_by_hour AS" + usual


def rules(pack: str = "trust") -> dict:
    """The pack's rules as shipped, by id."""
    with open(os.path.join(ROOT, "packs", pack, "rules.yml")) as f:
        return {r["id"]: r for r in yaml.safe_load(f)}


def readings(sensor: str | None = None, metric: str | None = None) -> list[tuple]:
    return [r for r in readings_from(os.path.join(ROOT, "tests/data/node1-readings.tsv"))
            if (not sensor or r[1] == sensor) and (not metric or r[2] == metric)]


def sensors() -> list[tuple]:
    """The five kits as node #1 held them. `local` is TRUE for all five: the live node had Ungasan Kit and BAYU NEW
    ENCLOSURE local when it named them at 21:17, though the 21:43 dump has them FALSE — docs/archive/handoffs/HANDOFF_trust.md (c)."""
    return sensors_from(os.path.join(ROOT, "tests/data/node1-sensors.tsv"))


def readings_from(path) -> list[tuple]:
    """readings() from any TSV of the same shape (tools/replay_alerts.py reads a node's dump with it)."""
    rows = []
    with open(path) as f:
        for line in f:
            ts, sid, met, val = line.rstrip("\n").split("\t")
            rows.append((dt.datetime.fromisoformat(ts), sid, met, float(val)))
    return rows


def sensors_from(path) -> list[tuple]:
    """sensors() from any TSV of the same eight columns; an empty lat or lon reads as 0."""
    rows = []
    with open(path) as f:
        for line in f:
            sid, source, name, lat, lon, indoor, local, kind = line.rstrip("\n").split("\t")
            rows.append((sid, source, name, float(lat or 0), float(lon or 0), indoor == "t", local == "t", kind))
    return rows


def day(rows: list[tuple], end: dt.datetime = FIXTURE_NOW) -> list[tuple]:
    """The last real 24 hours of a series."""
    return [r for r in rows if r[0] > end - dt.timedelta(hours=24)]


def heat_days(sensors: list[str], at: dt.datetime, days: int = 15, every_min: int = 5) -> list[tuple]:
    """Synthetic indoor temp + humidity, shaped to node #1's measured daily curve as published in docs/SPEC_alerts.md §1
    (apparent ~33 °C at 04:00 local rising to ~36 °C at 17:00; indoor air never above 32 °C). Not readings: the fixture
    holds none for temp or humidity, and a real day would add household data to a public repository.

    Local time is WITA (+08, no DST): temp = 29.4 + 1.7 cos(2π(h-16)/24), humidity = 66 - 4 cos(2π(h-16)/24).
    Deterministic. Rows are (ts_utc, sensor_id, metric, value), one per sensor per metric every `every_min` minutes."""
    wita = dt.timezone(dt.timedelta(hours=8))
    rows = []
    for m in range(0, days * 1440, every_min):
        ts = at - dt.timedelta(minutes=m)
        l = ts.astimezone(wita)
        c = math.cos(2 * math.pi * (l.hour + l.minute / 60 - 16) / 24)
        for sid in sensors:
            rows += [(ts, sid, "temp", 29.4 + 1.7 * c), (ts, sid, "humidity", 66 - 4 * c)]
    return rows


def week(rows: list[tuple], at: dt.datetime, days: int = 8) -> list[tuple]:
    """The series' last real day, replayed over the `days` days before `at`.

    The rules now ask for a week and node #1's kits are two days old, so a real week of any of them does not exist
    yet. Replaying one real day preserves that day's values, hourly means and diurnal shape exactly — every number
    here was measured — and gives the sensor the age and the hourly coverage the rule requires. What is synthetic
    is the calendar, and only the calendar.
    """
    d, shift = day(rows), at - FIXTURE_NOW
    return [(ts + shift - dt.timedelta(days=k), sid, m, v) for k in range(days) for ts, sid, m, v in d]


def flat(sensor: str, metric: str, value: float, hours: int, at: dt.datetime, every_min: int = 5) -> list[tuple]:
    """A synthetic channel stuck on one number for `hours` — the failure channel_dead exists to catch."""
    return [(at - dt.timedelta(minutes=m), sensor, metric, value)
            for m in range(0, hours * 60, every_min)]


class Node:
    """A node holding one set of readings, which a rule can be run against at any instant."""

    def __init__(self, rows: list[tuple], who: list[tuple] | None = None, tz: str = NODE_TZ):
        self.con = duckdb.connect()
        self.con.execute(f"SET TimeZone='{tz}'")   # before the schema: the views carry timestamps too
        self.con.execute(_init_sql())
        self.con.executemany(
            "INSERT INTO sensors (sensor_id, source, name, lat, lon, indoor, local, kind) VALUES (?,?,?,?,?,?,?,?)",
            who if who is not None else sensors())
        seen = set()
        rows = [r for r in rows if not (r[:3] in seen or seen.add(r[:3]))]
        if rows:                                       # a replay starts empty (duckdb refuses an empty executemany)
            self.con.executemany("INSERT INTO readings (ts, sensor_id, metric, value) VALUES (?,?,?,?)", rows)
        with open(os.path.join(ROOT, "config/channels.yml")) as f:
            for c in yaml.safe_load(f):
                self.con.execute(
                    "INSERT INTO channel_roles (source, metric, role, comparable, declared_by) VALUES (?,?,?,?,'core')",
                    (c["source"], c["metric"], c["role"], bool(c.get("comparable", False))))

    def refresh_usual(self, at: dt.datetime) -> None:
        """Rebuild usual_by_hour as it would read at `at` (the app refreshes it hourly)."""
        self.con.execute(_measures_sql()[1].replace("now()", f"TIMESTAMPTZ '{at.isoformat()}'"))

    def recent(self, at: dt.datetime) -> list[tuple]:
        """recent_15m as it would read at `at`."""
        self._recent_at(at)
        # by epoch: handing a TIMESTAMPTZ to Python makes duckdb import pytz, which CI does not install
        return [(dt.datetime.fromtimestamp(e, UTC), s, m, v) for e, s, m, v in self.con.execute(
            "SELECT epoch(bucket), sensor_id, metric, mean FROM recent_15m").fetchall()]

    def _recent_at(self, at: dt.datetime) -> None:
        self.con.execute("DROP VIEW IF EXISTS recent_15m")
        self.con.execute(_measures_sql()[0].replace("now()", f"TIMESTAMPTZ '{at.isoformat()}'"))

    def run(self, rule: dict, at: dt.datetime, lat: float | None = None, lon: float | None = None) -> list[dict]:
        stamp = f"TIMESTAMPTZ '{at.isoformat()}'"
        # `stats` is a 24-hour rolling view over now(), so it has to be rebuilt at the instant being replayed.
        self.con.execute("DROP VIEW IF EXISTS stats")
        self.con.execute(_stats_sql().replace("now()", stamp).replace("CREATE VIEW", "CREATE VIEW"))
        self._recent_at(at)
        sql = rule["sql"].replace("now()", stamp)
        if lat is not None:
            # the node's coordinates reach a rule through Postgres session settings; DuckDB has none.
            sql = (sql.replace("current_setting('planetai.lat')::float", str(lat))
                      .replace("current_setting('planetai.lon')::float", str(lon)))
        cur = self.con.execute(sql)
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]
