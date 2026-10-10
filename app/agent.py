"""The node as a set of tools for an AI agent, over MCP.

Mounted on the API at /mcp (streamable HTTP). A remote Claude reaches it over Tailscale; a local model on the same
machine reaches it on localhost. Reads are what the API already gives; writes need the admin token and record which
agent did them (the X-Agent header, default "agent").

What an agent can do here: read the node, act on an alert, change runtime settings, enable packs, run a pack's
scripts, get one day as open data. What it cannot do from here: anything that needs Docker or git on the host
(update, backup, restart). For those, `maintenance` returns the exact command to run on the node; an agent with a
shell runs it, an agent without one tells the person.
"""
from __future__ import annotations

import json
import os
import subprocess
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import httpx
from mcp.server.mcpserver import MCPServer

import settings
from packs import PACKS_DIR, agent_scripts
from tool_classes import PLACEHOLDER_NOTES, TOOL_CLASS  # noqa: F401 — re-exported; `planetai agent` and the loop read them

API = f"http://127.0.0.1:{os.getenv('PORT', '8080')}"
NODE = os.getenv("NODE_NAME", "node")

mcp = MCPServer(
    "planetai-node",
    instructions=(
        f"You are operating PLANETAI node '{NODE}': a small computer that connects everything measuring one place, from "
        "sensors on the wall to satellites overhead, decides where it stands, and tells the people there what to do. Raw readings never leave it. Your job is to keep it "
        "healthy and useful: read status, check alerts, record actions people took (that is how the node measures "
        "itself), adjust settings when asked, and report plainly. Never expose tokens. Prefer one clear sentence to a list."
    ),
)


def _get(path: str):
    r = httpx.get(API + path, timeout=30)
    r.raise_for_status()
    return r.json()


def _admin_headers(agent: str) -> dict:
    return {"Authorization": f"Bearer {os.getenv('ADMIN_TOKEN', '')}", "X-Agent": agent}


@mcp.tool()
def status() -> dict:
    """Is the node alive, what has it read, what fired, and its rho (share of act-level alerts somebody answered within 24 h)."""
    h = _get("/health"); rho = _get("/rho")
    backups = Path("/app/backups")
    last_ok = (backups / "LAST_OK").read_text().strip() if (backups / "LAST_OK").exists() else None
    return {"node": h.get("node"), "version": h.get("version"), "schema": h.get("schema"), "uptime_s": h.get("uptime_s"),
            "last_poll": h.get("last_poll"), "readings": h.get("ingested"), "polls": h.get("polls"),
            "errors": h.get("errors") or {}, "mesh": h.get("mesh"), "rho": rho, "last_backup_ok": last_ok}


@mcp.tool()
def health_check() -> dict:
    """Checks with the fix named next to each failure: polling recent, sources without errors, a backup in the last two days,
    the database reachable, the mesh alive if configured."""
    h = _get("/health"); checks = []
    def chk(name, ok, fix): checks.append({"check": name, "ok": bool(ok), "fix": None if ok else fix})
    age = None
    if h.get("last_poll"):
        age = (datetime.now(timezone.utc) - datetime.fromisoformat(h["last_poll"])).total_seconds() / 60
    chk("polled in the last 15 min", age is not None and age < 15, "the poll loop is stuck or the node just started; check `planetai logs`")
    chk("no source errors", not h.get("last_error") and not (h.get("errors") or {}), f"errors: {h.get('last_error') or h.get('errors')}")
    backups = Path("/app/backups")
    dumps = sorted(backups.glob("*.sql.gz"), key=lambda p: p.stat().st_mtime) if backups.exists() else []
    fresh = dumps and (datetime.now(timezone.utc) - datetime.fromtimestamp(dumps[-1].stat().st_mtime, timezone.utc)) < timedelta(days=2)
    chk("a backup in the last 2 days", fresh, "run `planetai backup` on the node and check `crontab -l | grep backup`")
    # judge each local sensor by whether its ambient channels are still moving, not by its timestamp: a dead
    # channel's kit keeps stamping fresh times over the same frozen value (see packs/trust/rules.yml, channel_dead)
    try:
        trust = _get("/trust")
    except Exception as e:  # noqa: BLE001 — this check's own fetch must not take down every other check below it
        chk("no local sensor's ambient channel is frozen", False, f"/trust did not respond ({e}); check `planetai logs`")
    else:
        frozen = sorted({r["name"] or r["sensor_id"] for r in trust if r["frozen_channels"] > 0})
        chk("no local sensor's ambient channel is frozen", not frozen,
            f"{', '.join(frozen)} {'has' if len(frozen) == 1 else 'have'} a channel stuck on the same number for hours while the kit itself "
            f"still reports. What this means: any reading or alert built from that channel is wrong; the rest of the kit and the rest of the "
            f"node are unaffected. Most often one sensor inside the kit has died: power-cycle it. If the number stays frozen, replace that "
            f"sensor — nothing it has recorded since it froze can be trusted.")
    if os.getenv("MQTT_HOST"):
        # judge the radios by their readings, not by in-memory packet counters that reset on every restart
        mesh = [r for r in _get("/stats") if r["sensor_id"].startswith("msh-")]
        quiet = sorted({r["sensor_id"] for r in mesh if r["silent_minutes"] > 60})
        heard = sorted({r["sensor_id"] for r in mesh if r["silent_minutes"] <= 60})
        chk("LoRa radios heard in the last hour", bool(heard) or not mesh,
            f"radio(s) {', '.join(quiet)} have been silent for hours. What this means: readings and alerts that travel over LoRa have "
            f"stopped; everything else (the WiFi sensors, Telegram, the dashboard) is unaffected. Most often the gateway radio (the XIAO) "
            f"lost WiFi or its MQTT session: check its power light, open its web page at its IP, or power-cycle it. `planetai logs mosquitto` shows whether the broker hears it.")
    return {"ok": all(c["ok"] for c in checks), "checks": checks}


@mcp.tool()
def sensors() -> list:
    """Every sensor the node knows: yours (local) and public references, indoor or outdoor, with the latest 15-minute mean of
    every metric it reports (pm25, temp, humidity, pressure, noise, light, eco2...) and how long since each spoke.
    For the sea, weather, satellites and land, use `context` instead."""
    stats = _get("/stats"); by = {}
    for r in stats:
        by.setdefault(r["sensor_id"], {"sensor_id": r["sensor_id"], "name": r["name"], "local": r["local"], "indoor": r["indoor"], "kind": r["kind"]})
        by[r["sensor_id"]][r["metric"]] = r["mean_15m"]
        by[r["sensor_id"]]["silent_minutes"] = round(r["silent_minutes"])
    return sorted(by.values(), key=lambda s: (not s["local"], s["sensor_id"]))


from report import LABELS      # one copy, in the module the report is written from


@mcp.tool()
def context() -> dict:
    """What the node knows about the place beyond its sensors: the sea (waves, swell, period, direction, temperature), the
    weather, the satellite air-quality model for the district, the land within a kilometre from satellites (built, trees,
    greenness, change), and the place from the map (buildings, shops, warungs, schools, clinics, roads, green, walking
    distances). Use this for any question about the sea, weather, UV, the land, or what is around here. A zero on the map
    often means unmapped, not absent. Values carry a plain label and a timestamp."""
    out: dict = {}
    for o in _get("/observations"):
        group, labels = LABELS.get(o["sensor_id"], (o["sensor_id"], {}))
        out.setdefault(group, {})[o["metric"]] = {"value": o["value"], "means": labels.get(o["metric"], o["metric"]), "at": o["ts"]}
    return out or {"note": "no model or satellite data yet; the first poll fills this"}


@mcp.tool()
def readings(sensor_id: str, metric: str, hours: int = 24) -> dict:
    """Hourly means of one metric from one sensor over the last N hours, for a specific question ('what did the kitchen do
    overnight'). Sensor ids come from `sensors`; metrics include pm25, pm10, pm1, temp, humidity, pressure, noise, light, eco2, tvoc."""
    rows = _get(f"/sparks?metric={metric}&hours={min(hours, 168)}")
    vals = rows.get(sensor_id)
    if vals is None:
        return {"error": f"no {metric} from {sensor_id} in that window", "sensors_with_it": sorted(rows)}
    return {"sensor_id": sensor_id, "metric": metric, "hours": hours, "hourly_means_oldest_first": vals}


@mcp.tool()
def report_latest() -> dict:
    """The last report the node wrote: its text, when, how many hours it covered, whether quiet hours held it, and who
    wrote it (`rung` is `node` for the node's own). The same words the household read on Telegram."""
    return _get("/report/latest")


@mcp.tool()
def report_now(agent: str = "agent") -> dict:
    """Write and send a report right now, whatever the hour. Use it when someone asks how things are going and wants
    the report rather than an answer. It does not take the next scheduled report's place."""
    r = httpx.post(API + "/report/now", headers=_admin_headers(agent), timeout=180)
    r.raise_for_status()
    return r.json()


@mcp.tool()
def report_bundle(hours: int = 6) -> dict:
    """Every number the node has about the last N hours, as one document: each sensor and metric with its min, max,
    mean, trend and how unusual it is against the same hours of the previous week; where everything stands now; the
    sea, weather, satellite air, map and land; the alerts and which are unanswered; the quiet sensors; rho; the Index
    cells. This is what a report is written from — use it to answer a question about a stretch of time rather than a
    moment, and never write a number that is not in it."""
    r = httpx.get(API + f"/report/bundle?hours={min(max(int(hours), 1), 168)}",
                  headers={"Authorization": f"Bearer {os.getenv('ADMIN_TOKEN', '')}"}, timeout=120)
    r.raise_for_status()
    return r.json()


@mcp.tool()
def history(sensor_id: str, metric: str) -> list:
    """Every reading of a slow series, oldest first: e.g. sensor_id='place-point', metric='sat_buildings_yearly' for how
    many buildings stood within a kilometre each year 2016-2023, or 'sat_height_m_yearly' for their mean height."""
    return _get(f"/history?sensor_id={sensor_id}&metric={metric}")


@mcp.tool()
def alerts(limit: int = 10, since_hours: int = 0) -> dict | list:
    """Recent alerts, newest first, each with its id, level (info/warn/act) and whether anyone acted on it.

    For "how many in the last day", pass since_hours=24: that returns {since_hours, count, alerts}, where `count` is
    every alert in the window and `alerts` the newest `limit` of them with their text shortened. Answer a count from
    `count`, never by counting a list."""
    if not since_hours:
        return _get(f"/alerts?limit={min(limit, 100)}")
    rows = _get(f"/alerts?since_hours={int(since_hours)}&limit=1000")
    return {"since_hours": since_hours, "count": len(rows),
            "alerts": [{**r, "text": (r.get("text") or "")[:160]} for r in rows[:min(limit, 100)]]}


@mcp.tool()
def act(alert_id: int, note: str, agent: str = "agent") -> dict:
    """Record that a PERSON acted on an alert, in their own words. `note` is required and must be what they said.

    rho — the share of act-level alerts that led to an action — is the one number this project has that nobody can
    measure from orbit, and this tool is how it is written. Do not call this because an alert looked handled, or
    because you suggested something sensible. Call it when somebody told you they did a thing, and put what they
    told you in `note`. If you do not have their words, ask for them."""
    if not (note or "").strip() or (note or "").strip().lower() in PLACEHOLDER_NOTES:
        raise ValueError(
            "act() needs the person's own words in `note`, not a placeholder. rho is the share of alerts a HUMAN "
            "answered; a row written without anything a human said is a model measuring itself. Ask them what they "
            "did and call this again with their answer.")
    r = httpx.post(API + "/actions", json={"alert_id": alert_id, "stage": "acted", "actor": agent, "note": note}, timeout=30)
    r.raise_for_status()
    return {"recorded": True, "alert_id": alert_id, "by": agent}


@mcp.tool()
def settings_get() -> dict:
    """Every runtime setting with its group, help and current value. Secrets are masked. Bootstrap settings (ports, database)
    are shown read-only; they change only in .env on the node."""
    return settings.describe(unlocked=True)      # every MCP call is already behind the admin token


@mcp.tool()
def settings_set(changes: dict, agent: str = "agent") -> dict:
    """Change runtime settings, e.g. {"SC_USER": "tomasdiez", "MESH_ALERTS": "1"}. Live within ~20 s, no restart. Blank returns a
    key to its .env value. Only keys listed by settings_get under `runtime` are allowed."""
    r = httpx.put(API + "/settings", json=changes, headers=_admin_headers(agent), timeout=30)
    r.raise_for_status()
    return r.json()


@mcp.tool()
def packs() -> list:
    """The packs loaded on this node: id, kind (data/code), description. Enable or disable with settings_set PACKS_ENABLED."""
    return _get("/packs")


@mcp.tool()
def cells() -> list:
    """The Fab City Index cells this node computes, with value, unit and provenance state (live = measured here, partial = derived
    or modelled)."""
    return _get("/cells")


@mcp.tool()
def issues(issue: str | None = None) -> dict:
    """What this place is better or worse at right now, named the way the household names it.

    One entry per issue the keeper watches (air, heat, land, coast — the order is theirs, set as
    NODE_ISSUES). Each carries: its state (act = something needs doing now · notable = something
    changed today · quiet = nothing to say · context = it informs and never asks · none = not
    watched or no source) and why; the same quantity at four distances (room, yard, ring, region)
    with a source and a provenance word for each; the line it is judged against and where that line
    comes from; the open alerts, and whether each is still true; and one sentence in English, Bahasa
    and Spanish.

    `headline` is the issue to lead with: the highest state present, ties going to the keeper's
    order. Prefer this tool over `stats` or `readings` for any question about how the place is
    doing — it is the same vocabulary the household's own screen uses, so you and they will not
    describe the same evening in two different ways. Pass `issue` for one of them.
    """
    out = _get("/issues")
    if not issue:
        return out
    one = (out.get("issues") or {}).get(issue)
    if one is None:
        return {"error": f"this node does not declare {issue!r}", "declares": out.get("order", []),
                "also_knows": out.get("undeclared", [])}
    return {"issue": issue, "as_of": out.get("as_of"), "labels": out.get("labels"), **one}


@mcp.tool()
def series(metric: str = "pm25", hours: int = 24) -> dict:
    """Hourly means for the last N hours: indoor (yours), outdoor (yours and references), and the model, as aligned arrays."""
    return _get(f"/series?metric={metric}&hours={min(hours, 168)}")


@mcp.tool()
def export_day(day: str | None = None) -> dict:
    """One day as open data: hourly means per sensor, cells, alerts, rho. Default yesterday. What a parent node or a researcher receives."""
    day = day or (date.today() - timedelta(days=1)).isoformat()
    return _get(f"/export?day={day}")


@mcp.tool()
def run_pack_script(pack: str, script: str, args: list[str] | None = None, agent: str = "agent") -> dict:
    """Run a script a pack ships (e.g. earth-engine verify, earth-engine timelapse). Runs in the app container; output files land in out/.
    Returns stdout/stderr and the exit code."""
    pack, script = Path(pack).name, Path(script).name
    p = PACKS_DIR / pack / (script + ".py")
    reachable = agent_scripts()
    if f"{pack}/{script}" not in reachable:
        why = (f"{pack}/{script} is in a wild pack that does not list it under agent_scripts:, so only the node's own "
               f"terminal runs it: planetai run {pack} {script}") if p.is_file() and (p.parent / ".wild").is_file() \
            else f"no such script: {pack}/{script}"
        return {"error": why, "available": reachable}
    r = subprocess.run(["python", str(p), *(args or [])], capture_output=True, text=True, timeout=900, env={**os.environ, "PACK_OUT": "/app/out"})
    return {"exit": r.returncode, "stdout": r.stdout[-6000:], "stderr": r.stderr[-2000:], "by": agent}


@mcp.tool()
def maintenance(task: str) -> dict:
    """Host-side tasks this server cannot run itself because they need Docker or git on the node's machine: update, backup, restore,
    restart, logs, doctor, storage, ui, telegram. Returns the exact command and what it does, so an agent with a shell on the node runs
    it, and an agent without one tells the person."""
    cmds = {
        "update": ("planetai update", "backs up, fetches the current version, migrates the database, rebuilds, verifies"),
        "backup": ("planetai backup", "dumps the database now, writes the daily export, copies off-machine if configured"),
        "restore": ("planetai restore <backups/file.sql.gz>", "replaces the live database with a dump; takes a safety backup first"),
        "restart": ("planetai restart", "restarts the containers; needed after editing .env"),
        "logs": ("planetai logs", "follows the app log; `planetai logs mosquitto` for the broker"),
        "doctor": ("planetai doctor --json", "every check with the fix named for each failure, as JSON"),
        "storage": ("planetai storage", "database size, backup destination and freshness, remote, exports, IPFS, the NAS token"),
        "ui": ("planetai ui", "dashboard URLs and the admin token"),
        "telegram": ("planetai telegram", "connects the Telegram bot"),
    }
    if task not in cmds:
        return {"error": f"unknown task; one of {sorted(cmds)}"}
    c, what = cmds[task]
    return {"run_on_the_node": c, "does": what, "where": "a shell on the node's machine (ssh, or the local agent). Not from here."}


def tool_names() -> set:
    """Every tool the server registers, for the test that TOOL_CLASS has not drifted from it."""
    return {t.name for t in mcp._tool_manager.list_tools()} if hasattr(mcp, "_tool_manager") else set()


def http_routes():
    """Routes serving MCP at exactly /mcp, to append to the main app. The caller runs session_manager in its lifespan.
    DNS-rebinding protection is off: the node is reached by many names (LAN IP, .local, the tailnet name) and the
    admin token, not the Host header, is the access control."""
    from mcp.server.transport_security import TransportSecuritySettings
    inner = mcp.streamable_http_app(streamable_http_path="/mcp",
                                    transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False))
    return inner.routes
