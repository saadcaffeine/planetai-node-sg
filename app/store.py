"""How a reading gets into `readings`. One rule lives here: a newer model run replaces an older one.

A forecast is stored at its valid time, so a later run writes the same (sensor, metric, ts) again, usually with
a different number. DO NOTHING kept the first run forever. The rule overwrites only a forecast metric (`fc_`) whose
hour has not happened yet: a measured reading with a future clock is never touched, and neither is a past hour,
which stays as it was when it last was the future. Only the poll and `planetai run forecast fetch` use it; MQTT,
/readings and bootstrap keep DO NOTHING.

`%%` is one literal % to psycopg, which reads every % in a query as a placeholder once it has parameters.
"""

READINGS_SQL = """INSERT INTO readings (ts, sensor_id, metric, value) VALUES (%s,%s,%s,%s)
ON CONFLICT (sensor_id, metric, ts) DO UPDATE SET value = EXCLUDED.value
WHERE EXCLUDED.metric LIKE 'fc\\_%%' AND EXCLUDED.ts > now()"""


def insert_readings(cur, rows: list[tuple]) -> int:
    """Write (ts, sensor_id, metric, value) rows; returns what Postgres says it wrote or updated."""
    cur.executemany(READINGS_SQL, rows)
    return max(cur.rowcount or 0, 0)
