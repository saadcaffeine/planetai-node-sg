"""The machine this node runs on and the room it takes: GET /machine and GET /storage.

A module of its own since 24 Oct 2026, moved unchanged out of app/main.py (review item 15). Both are private: what
the machine holds is the keeper's, not the network's.
"""
from __future__ import annotations

import os
from pathlib import Path

from fastapi import APIRouter

from db import db

OUT = Path(os.getenv("PACK_OUT", "/app/out"))      # the one writable mount, as app/main.py's OUT

router = APIRouter()


@router.get("/machine")
def machine():
    """The machine this node runs on, as the node's container sees it: processor, load, memory, temperature, how long
    it has been up, its system, and the database engine. Read from /proc and /sys, so on Linux (a Pi, a mini PC) it is
    the machine; on macOS it is the container engine's virtual machine, and says so in `seen_as`. A value the system
    does not give (no thermal sensor, no cgroup limit) is null, never a guess. Private like /storage."""
    import platform, time as _t
    def read(p):
        try:
            return Path(p).read_text()
        except OSError:
            return None
    mem = {}
    for line in (read("/proc/meminfo") or "").splitlines():
        k, _, v = line.partition(":")
        if k in ("MemTotal", "MemAvailable", "SwapTotal", "SwapFree") and v.split():
            mem[k] = int(v.split()[0]) * 1024
    def cpu_times():
        f = (read("/proc/stat") or "").splitlines()
        nums = [int(x) for x in f[0].split()[1:]] if f and f[0].startswith("cpu ") else []
        return (sum(nums), nums[3] + (nums[4] if len(nums) > 4 else 0)) if nums else None
    a = cpu_times(); _t.sleep(0.25); b = cpu_times()
    busy = round(100 * (1 - (b[1] - a[1]) / (b[0] - a[0])), 1) if a and b and b[0] > a[0] else None
    temps = []
    for z in sorted(Path("/sys/class/thermal").glob("thermal_zone*")):
        t = read(z / "temp")
        if t and t.strip().lstrip("-").isdigit():
            temps.append({"zone": (read(z / "type") or z.name).strip(), "celsius": round(int(t) / 1000, 1)})
    up = read("/proc/uptime")
    cg_max, cg_cur = read("/sys/fs/cgroup/memory.max"), read("/sys/fs/cgroup/memory.current")
    with db() as con, con.cursor() as cur:
        cur.execute("SELECT split_part(version(), ' on ', 1) AS v, pg_postmaster_start_time() AS since,"
                    " (SELECT count(*) FROM pg_stat_activity) AS conns")
        pg = cur.fetchone()
    return {
        "seen_as": "the Linux system the node's containers run on: the machine itself on Linux, the container engine's virtual machine on macOS",
        "arch": platform.machine(), "system": f"{platform.system()} {platform.release()}", "cores": os.cpu_count(),
        "load": [float(x) for x in (read("/proc/loadavg") or "").split()[:3]] or None, "cpu_busy_pct": busy,
        "memory": {"total_bytes": mem.get("MemTotal"), "available_bytes": mem.get("MemAvailable"),
                   "swap_total_bytes": mem.get("SwapTotal"), "swap_free_bytes": mem.get("SwapFree")},
        "container_memory": {"limit_bytes": int(cg_max) if cg_max and cg_max.strip().isdigit() else None,
                             "used_bytes": int(cg_cur) if cg_cur and cg_cur.strip().isdigit() else None},
        "temperatures": temps, "uptime_s": round(float(up.split()[0])) if up else None,
        "python": platform.python_version(),
        "database": {"version": pg["v"], "since": pg["since"].isoformat() if pg["since"] else None, "connections": pg["conns"]},
    }


@router.get("/storage")
def storage():
    """How much room this node takes, how much is left, and how long that lasts at the rate it has been growing.

    The node computes it so no page has to: the database's own size (Postgres), the files it keeps beside it (out/,
    the backups, the open exports), and the free space on the disk those files live on, as this container sees it.
    The rate is the readings written in the last seven days times what a reading row costs on disk, indexes and all,
    which is where nearly all of the growth is; nothing is ever pruned. The backups are counted as they will be once
    BACKUP_KEEP days of dumps sit there. `days_left` is null when the rate is zero or not yet known.

    The database's own disk is the container engine's: on Linux it is this disk unless DATA_DIR moves it; on macOS
    it is the engine's virtual disk, which this container cannot see. `planetai doctor` checks the host's.
    Private like /version: what the machine holds is the keeper's, not the network's."""
    import shutil
    def du(p: Path) -> int:
        try:
            return sum(f.stat().st_size for f in p.rglob("*") if f.is_file())
        except OSError:
            return 0
    with db() as con, con.cursor() as cur:
        cur.execute("SELECT pg_database_size(current_database()) AS db, pg_total_relation_size('readings') AS r,"
                    " (SELECT reltuples FROM pg_class WHERE relname = 'readings') AS n,"
                    " (SELECT count(*) FROM readings WHERE ts > now() - interval '7 days') AS week")
        row = cur.fetchone()
    per_row = (row["r"] / row["n"]) if row["n"] and row["n"] > 0 else None
    per_day = round(per_row * row["week"] / 7) if per_row else None
    backups = Path("/app/backups")
    dumps = sorted(backups.glob("*.sql.gz"), key=lambda f: f.stat().st_mtime) if backups.exists() else []
    keep = int(os.getenv("BACKUP_KEEP", "30") or 30)
    b_now = sum(f.stat().st_size for f in dumps)
    b_full = (dumps[-1].stat().st_size * keep) if dumps else 0
    disk = shutil.disk_usage(OUT) if OUT.exists() else None
    free = disk.free if disk else None
    room = (free - max(0, b_full - b_now)) if free is not None else None
    return {
        "database_bytes": row["db"], "readings": int(row["n"] or 0), "readings_last_7_days": row["week"],
        "bytes_per_reading": round(per_row) if per_row else None, "growth_bytes_per_day": per_day,
        "out_bytes": du(OUT), "exports_bytes": du(Path("/app/exports")),
        "backups": {"bytes": b_now, "dumps": len(dumps), "keep_days": keep, "bytes_when_full": b_full},
        "disk": ({"path": str(OUT), "total_bytes": disk.total, "used_bytes": disk.used, "free_bytes": disk.free} if disk else None),
        "days_left": (int(room / per_day) if room is not None and per_day else None),
        "rate": "readings written in the last 7 days x bytes per reading row; backups counted at BACKUP_KEEP dumps",
    }
