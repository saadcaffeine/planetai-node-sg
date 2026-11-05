"""Packs — the extension point. Core packs ship in packs/ with the release; wild packs are added by whoever runs
the node (`planetai packs add`, docs/decisions/2026-10-01-packs.md).

A pack is a folder in packs/ with a pack.yaml and any of:
    rules.yml    extra alert rules (SQL + message)      DATA — no code, safe to merge from anyone
    cells.yml    extra Index cells (SQL → fci-cells-v0) DATA — no code
    adapter.py   a source adapter (Python function)     CODE — runs with the node's privileges
    hooks.py     on_readings / on_alert, called by emit()  CODE — the same

Data packs are the default and the point: most useful contributions are a rule and a threshold that
someone learned the hard way in their city. Code packs need review — see docs/PACKS.md.

Loading is deliberately dumb: scan the directory, parse the YAML, import the module. No registry service,
no dependency resolution, no lifecycle hooks. If a pack is broken the node logs it and carries on.
"""
from __future__ import annotations

import copy
import importlib.util
import logging
import os
import re
import time
from pathlib import Path

import yaml

log = logging.getLogger("planetai.packs")
PACKS_DIR = Path(os.getenv("PACKS_DIR", "/app/packs"))
CORE_CHANNELS = Path(os.getenv("CHANNELS_PATH", "/app/config/channels.yml"))

# Every pack.yaml, rules.yml, cells.yml, channels.yml and issue.yml, parsed once per change of the file. GET /issues
# parsed them 223 times a request with the pure-Python loader, about 3 of its 6.5 s on node #1 (24 Oct 2026).
_YAML: dict = {}
_LOADER = getattr(yaml, "CSafeLoader", yaml.SafeLoader)


def read_yaml(f: Path):
    """`yaml.safe_load(f.read_text())`, cached on the file's mtime and size, with libyaml when the image has it. A
    copy each time: every caller sets keys on what it gets (a rule's namespaced id, a cell's pack). A file that is
    missing or does not parse raises exactly as before, and is parsed again on the next call."""
    st = f.stat()
    stamp = (st.st_mtime_ns, st.st_size)
    hit = _YAML.get(f)
    if hit is None or hit[0] != stamp:
        hit = _YAML[f] = (stamp, yaml.load(f.read_text(), Loader=_LOADER))  # noqa: S506 — a safe loader
    return copy.deepcopy(hit[1])


def _allow_code() -> bool:
    import settings
    return settings.get("PACKS_ALLOW_CODE", "0") == "1"


# Packs this node will not load because their `requires:` rules it out, and why: what `planetai packs` reads back.
REFUSED: dict[str, str] = {}


def _enabled() -> list[Path]:
    if not PACKS_DIR.is_dir():
        return []
    import requires
    import settings
    only = {p for p in settings.get("PACKS_ENABLED", "").replace(" ", "").split(",") if p}
    here = os.getenv("NODE_VERSION", "")
    out = []
    for d in sorted(PACKS_DIR.iterdir()):
        if not (d / "pack.yaml").is_file():
            continue
        if only and d.name not in only:
            continue
        # A pack written for a newer node may read a column, a route or a setting this one does not have. It is
        # refused whole, rules and adapter alike, with one line in the log, and not half-loaded.
        try:
            spec = ((read_yaml(d / "pack.yaml") or {}).get("requires") or {}).get("node")
        except Exception:  # noqa: BLE001 — a pack.yaml that does not parse is reported where it is read
            spec = None
        why = requires.check(spec, here)
        if why:
            if REFUSED.get(d.name) != why:
                log.warning("pack %s not loaded: %s", d.name, why)
            REFUSED[d.name] = why
            continue
        REFUSED.pop(d.name, None)
        out.append(d)
    return out


def manifests() -> list[dict]:
    out = []
    for d in _enabled():
        try:
            m = read_yaml(d / "pack.yaml") or {}
        except Exception as e:  # noqa: BLE001
            log.warning("pack %s: bad pack.yaml (%s)", d.name, e); continue
        m["id"] = m.get("id", d.name)
        m["path"] = str(d)
        m["kind"] = "code" if any(d.glob("*.py")) else "data"    # nearby and season run scripts: code, though no adapter
        out.append(m)
    return out


# What a `contributes:` rule may contribute to. A rule with one of these is not an alert: it has no message, it
# is never sent, and its SQL is run where the thing it contributes to is built.
CONTRIBUTES = ("report",)


CORE_RULES = Path(os.getenv("RULES_PATH", "/app/config/rules.yml"))


def load_rules() -> list[dict]:
    """Every rule this node evaluates, core plus packs. Lives here rather than in main because two callers need it and
    they must not disagree: main runs them, and index asks which rule ids are still alive when it derives whether an
    alert's condition stopped being true. A rule that has been renamed or deleted can never fire again, so counting
    its silence as a cleared condition would turn every retired rule into a success."""
    try:
        core = read_yaml(CORE_RULES) or []
    except FileNotFoundError:
        core = []
    return core + alerts()            # a pack rule with `contributes:` is part of the report, not an alert


def module(pack: str, name: str = "adapter", on_only: bool = True):
    """A pack's own module, imported from PACKS_DIR, or None if it is not on this node.

    `packs` in app/ is this LOADER, not a package: the pack directories live under PACKS_DIR and
    `import packs.make.adapter` fails with "packs is not a package". Two callers worked around that
    by inserting a path and importing bare — `app/issues/engine.py::_where_to_go` and
    `app/report.py` — and both defaulted PACKS_DIR to "../packs", which is not where a node keeps
    them. It is /app/packs in the image, and PACKS_DIR is unset there, so both imports failed on
    every node: `asks.where` was null with the pack on and a lab 3.3 km away, and the report's
    `make` line never appeared. Neither said anything, because both swallow the failure by design.

    One place knows this path, and it is the one that already reads every pack. This also stops
    mutating sys.path on each call, which the two workarounds did once per request.

    A pack this node does not load (left out of PACKS_ENABLED, or refused by `requires:`) has no module either: the
    report and /issues worded the nearest fab lab with packs/make's code on a node that had switched make off.

    `on_only=False` is for one official pack borrowing another's pure function, whatever this node loads: AirGradient
    and PurpleAir take the EPA 2021 correction from packs/air-quality, and a node with that pack off still needs it."""
    if on_only and pack not in {d.name for d in _enabled()}:
        return None
    d = PACKS_DIR / pack
    f = d / f"{name}.py"
    if not f.is_file():
        return None
    try:
        spec = importlib.util.spec_from_file_location(f"pai_pack_{pack}_{name}", f)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    except Exception as e:  # noqa: BLE001 — a broken pack must not break the caller
        log.warning("pack %s: %s.py did not import (%s)", pack, name, e)
        return None


def rules() -> list[dict]:
    """Every rule a pack ships, alerts and contributors alike. Rule ids are namespaced <pack>/<id>."""
    out = []
    for d in _enabled():
        f = d / "rules.yml"
        if not f.is_file():
            continue
        try:
            for r in read_yaml(f) or []:
                r["id"] = f"{d.name}/{r['id']}"
                out.append(r)
        except Exception as e:  # noqa: BLE001
            log.warning("pack %s: bad rules.yml (%s)", d.name, e)
    return out


def alerts() -> list[dict]:
    """The rules that can reach a household. A rule with `contributes:` is not one: it has nothing to say on its
    own, and sending a rule with no message once printed the raw template, braces and all."""
    return [r for r in rules() if not r.get("contributes")]


def contributors(to: str = "report") -> list[dict]:
    """The rules whose SQL is run where `to` is built, rather than sent. See docs/PACKS.md."""
    return [r for r in rules() if r.get("contributes") == to]


def cells() -> list[dict]:
    """Extra Index cell definitions: {cell, unit, sql, state}. The SQL must return one row with a `value` column."""
    out = []
    for d in _enabled():
        f = d / "cells.yml"
        if not f.is_file():
            continue
        try:
            for c in read_yaml(f) or []:
                c["pack"] = d.name
                out.append(c)
        except Exception as e:  # noqa: BLE001
            log.warning("pack %s: bad cells.yml (%s)", d.name, e)
    return out


ROLES = ("ambient", "enclosure", "device_health", "derived", "index", "private")


def public_sql(alias: str = "r") -> str:
    """SQL: this row of readings (or readings_1h, or the stats view) is not `private`. The one predicate every road
    out of the house is written with (docs/decisions/2026-10-03-pack-design.md, point 2 (A)): a private reading is
    used here by readouts, sections, rules and cells, and is left out of the daily export, the aggregates a parent
    receives, the report bundle, and every read an agent or a reader without the admin token makes."""
    return (f"NOT EXISTS (SELECT 1 FROM sensors ps JOIN channel_roles pc ON pc.source = ps.source "
            f"WHERE ps.sensor_id = {alias}.sensor_id AND pc.metric = {alias}.metric AND pc.role = 'private')")


def channels() -> list[dict]:
    """Channel role declarations: core's own, then every enabled pack's. A pack may not redeclare a pair core has
    already claimed; the first declaration wins and the duplicate is logged, so a merged pack cannot quietly
    relabel PM2.5 as a vendor index."""
    out, seen = [], set()
    files = [(CORE_CHANNELS, "core")] + [(d / "channels.yml", d.name) for d in _enabled()]
    for f, who in files:
        if not f.exists():
            continue
        try:
            decls = read_yaml(f) or []
        except Exception as e:  # noqa: BLE001
            log.warning("channels.yml in %s did not parse: %s", who, e); continue
        for c in decls:
            key = (c.get("source"), c.get("metric"))
            if not all(key) or c.get("role") not in ROLES:
                log.warning("%s: skipping channel declaration %r", who, c); continue
            if key in seen:
                log.warning("%s: %s/%s is already declared; keeping the first", who, *key); continue
            seen.add(key)
            out.append({"source": key[0], "metric": key[1], "role": c["role"],
                        "comparable": bool(c.get("comparable", False)), "unit": c.get("unit"),
                        "reference": c.get("reference"), "declared_by": who})
    return out


_loaded: dict = {}   # pack name -> (adapter.py mtime, module). Adapters keep pacing state (what is next due, tokens) in
                     # module globals; executing the file afresh on every poll threw that away, so the NEA pack asked for
                     # its first four feeds every time and never reached wind or rain.


def agent_scripts() -> list[str]:
    """`<pack>/<script>` for every pack script an agent may run through `run_pack_script`. A core pack's scripts are
    all reachable, as they always were. A wild pack's are reachable only when its pack.yaml names them under
    `agent_scripts:`, because a wild script can print what its pack keeps off the readings (a camera pack's motion
    log, a photo of the home) and the node's own terminal is the only place that should see it. `planetai run`
    still runs every script."""
    out = []
    for f in sorted(f for d in _enabled() for f in d.glob("*.py")):          # a pack this node does not load runs nothing
        d, name = f.parent, f.stem
        if name in ("adapter", "hooks", "routes"):                             # the node calls these; nobody runs them
            continue
        # ponytail: wild means `.wild` beside pack.yaml, written by `planetai packs add`; a pack copied in by hand
        # counts as core. A list of core ids shipped with the release would close that, if hand-copied packs spread.
        if (d / ".wild").is_file():
            try:
                listed = (read_yaml(d / "pack.yaml") or {}).get("agent_scripts")
            except Exception:  # noqa: BLE001 — a pack.yaml that does not parse lists nothing
                listed = None
            if not (isinstance(listed, list) and name in listed):
                continue
        out.append(f"{d.name}/{name}")
    return out


def _manifest(d: Path) -> dict:
    try:
        return read_yaml(d / "pack.yaml") or {}
    except Exception:  # noqa: BLE001 — a pack.yaml that does not parse is reported where manifests() reads it
        return {}


def _official_on(d: Path) -> bool:
    """An official pack (shipped and signed with the release, so no `.wild`) that names its own `switch:` runs its
    code when that switch is 1, without PACKS_ALLOW_CODE: decision A of the sensors spec (PR #262), for the packs that
    can be switched off by themselves. An official pack without a switch still waits for the flag, because turning
    the flag's meaning over for all of them at once would start forecast, place and surface-heat on every node.

    `switch:` may also be a list of keys, on when any of them is set and not 0: packs/smartcitizen runs whenever a kit
    is configured or a broker is set (SC_USER, SC_DEVICES or MQTT_HOST), as it did in the core, so no node needs a new
    key to keep its kits."""
    import settings
    sw = _manifest(d).get("switch")
    if (d / ".wild").is_file():
        return False
    if isinstance(sw, str):
        return settings.get(sw, "0") == "1"
    if isinstance(sw, list):
        return any((settings.get(k, "") or "").strip() not in ("", "0") for k in sw if isinstance(k, str))
    return False


# Each official pack's routes.py as routers() mounted it, by pack id.
ROUTES: dict = {}


def routers() -> list:
    """Every official pack's `routes.py` router, for main to mount when it is imported (docs/PACKS.md, "Routes").

    Found by file, because main is imported before any setting is read (no database opens at import, which
    tests/test_wire.py holds). So every official pack with routes is mounted, and each route checks on every request
    that this node loads its pack, answering 404 when it does not: PACKS_ENABLED can change in Set up without a
    restart. A wild pack's routes are not mounted at all. ponytail: when one needs to, it is the same gate plus
    PACKS_ALLOW_CODE."""
    from fastapi import APIRouter, Depends, HTTPException  # noqa: PLC0415 — the loader works without FastAPI

    def gate(pack: str):
        def on():
            if pack not in {d.name for d in _enabled()}:
                raise HTTPException(404, f"the {pack} pack is off on this node")
        return on

    out = []
    for f in sorted(PACKS_DIR.glob("*/routes.py")):
        d = f.parent
        if (d / ".wild").is_file() or not (d / "pack.yaml").is_file():
            continue
        try:
            spec = importlib.util.spec_from_file_location(f"planetai_pack_{d.name}_routes", f)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)  # type: ignore[union-attr]
        except Exception as e:  # noqa: BLE001 — a broken pack costs its own routes, never the node
            log.warning("pack %s: routes.py failed to load (%s)", d.name, e)
            continue
        if getattr(mod, "router", None) is not None:
            ROUTES[d.name] = mod         # the module that serves them: what a test patches
            r = APIRouter(dependencies=[Depends(gate(d.name))])
            r.include_router(mod.router)
            out.append(r)
    return out


def shared(level: str = "open") -> set[str]:
    """The paths official packs put on a share list (pack.yaml `share: {open: [...], off: [...]}`), read by app/auth.py
    when it is imported. `off` is every level, so a path on it is on `open` too. A wild pack cannot widen what a
    household shares."""
    out = set()
    for d in sorted(PACKS_DIR.iterdir()) if PACKS_DIR.is_dir() else []:
        if (d / "pack.yaml").is_file() and not (d / ".wild").is_file():
            share = _manifest(d).get("share") or {}
            for lv in (("off",) if level == "off" else ("off", "open")):
                # a bare `off:` is YAML for false, so that key is read too
                got = share.get(lv) or (share.get(False) if lv == "off" else None) or []
                out |= {p for p in got if isinstance(p, str) and p.startswith("/")}
    return out


def shared_open() -> set[str]:
    return shared("open")


def footprints() -> list[dict]:
    """Where each enabled pack's word reaches (pack.yaml `footprint:`), each with its pack id: what the page draws as
    a claim (app/issues/geometry.py::claims), so the core names no pack's radius."""
    return [{**m["footprint"], "pack": m["id"]} for m in manifests() if isinstance(m.get("footprint"), dict)]


def stations() -> list[dict]:
    """The enabled packs that read public stations around the node (pack.yaml `stations:`), each with its pack id,
    name, `switch` and whether that switch is on. What "Air stations nearby", GET /nearby and the ring's footprint
    read, so none of them names a network."""
    import settings
    out = []
    for m in manifests():
        s, sw = m.get("stations"), m.get("switch")
        if isinstance(s, dict) and s.get("source"):
            out.append({**s, "pack": m["id"], "name": m.get("name") or m["id"], "switch": sw,
                        "on": isinstance(sw, str) and settings.get(sw, "0") == "1"})
    return out


# `ahead:` in a pack.yaml adds one line to Next days (docs/PACKS.md, "A line in Next days"). Checked on every read, said
# once per process, like a section: a mistake costs the pack its line and nothing else.
AHEAD_LOCALES = ("en", "es", "id")
AHEAD_CHARS = 160
_AHEAD_SAID: set = set()


def _ahead_problems(a) -> list[str]:
    if not isinstance(a, dict):
        return ["ahead must be a mapping"]
    p = []
    if not isinstance(a.get("id"), str) or not re.fullmatch(r"[a-z0-9][a-z0-9-]*", a["id"]):
        p.append("its id must be lowercase letters, digits and hyphens")
    if not isinstance(a.get("sensor"), str) or not a["sensor"]:
        p.append("it needs the sensor whose meta holds the text")
    t = a.get("title")
    if not (isinstance(t, dict) and all(isinstance(t.get(loc), str) and t[loc] for loc in AHEAD_LOCALES)):
        p.append("it needs a title in en, es and id")
    d = a.get("days")
    if not (isinstance(d, list) and len(d) == 2 and all(isinstance(k, str) and "_" in k.strip("_") for k in d)):
        p.append("days must be exactly two meta keys, written without a locale (ahead_d1)")
    return p


def _sensor_meta(sid: str) -> dict | None:
    from db import q  # noqa: PLC0415 — packs is imported before any database is configured
    rows = q("SELECT meta FROM sensors WHERE sensor_id = %s", sid)
    return (rows[0]["meta"] or {}) if rows else None


def ahead_lines(now, tz: str) -> list[dict]:
    """The `lines` of GET /forecast: each loaded pack's `ahead:` text for tomorrow and the day after, in en, es and id.
    The node adds the locale to the pack's keys (`ahead_d1` is read as `ahead_en_d1`), cuts each text at 160 characters,
    and serves a line only while its sensor's meta `fetched` is today in `tz`, so `_d1` is always tomorrow."""
    from datetime import date as _date, datetime, timedelta, timezone  # noqa: PLC0415
    from zoneinfo import ZoneInfo  # noqa: PLC0415
    zone = ZoneInfo(tz)
    today = now.astimezone(zone).date()
    dates = [(today + timedelta(days=k)).isoformat() for k in (1, 2)]
    out = []
    for m in manifests():
        a = m.get("ahead")
        if a is None:
            continue
        bad = _ahead_problems(a)
        if bad:
            text = f"pack {m.get('id', '?')}: ahead: {'; '.join(bad)}; leaving its line out"
            if text not in _AHEAD_SAID:
                _AHEAD_SAID.add(text)
                log.warning(text)
            continue
        try:
            meta = _sensor_meta(a["sensor"]) or {}
            fetched = None
            if meta.get("fetched"):
                f = str(meta["fetched"])
                if re.fullmatch(r"\d{4}-\d{2}-\d{2}", f):
                    fetched = _date.fromisoformat(f)   # a date alone is the local date the pack meant, never UTC midnight
                else:
                    t = datetime.fromisoformat(f)
                    fetched = (t if t.tzinfo else t.replace(tzinfo=timezone.utc)).astimezone(zone).date()   # no zone is UTC, as learn._aware
        except Exception as e:  # noqa: BLE001 — no database, a stamp that is not a date: no line
            log.warning("pack %s: ahead: could not read %s (%s)", m.get("id", "?"), a["sensor"], e)
            continue
        if fetched != today:
            continue
        days = {}
        for date, key in zip(dates, a["days"]):
            head, _, tail = key.rpartition("_")
            texts = {loc: str(meta[f"{head}_{loc}_{tail}"]).strip()[:AHEAD_CHARS] for loc in AHEAD_LOCALES
                     if isinstance(meta.get(f"{head}_{loc}_{tail}"), str) and meta[f"{head}_{loc}_{tail}"].strip()}
            if texts:
                days[date] = texts
        if days:
            out.append({"pack": m.get("id", "?"), "id": a["id"], "title": a["title"], "days": days})
    return out


# Hooks: a code pack's `hooks.py` hears what the node does. `on_readings(sensors, readings)` after every batch the node
# stores (a poll, an MQTT message), and `on_alert(level, text, alert_id)` with every alert it sends. A pack that reads
# its own devices off the node's broker names their topics in MQTT_TOPICS, [(topic, qos)]; the node subscribes to them
# when it connects and hands each message to `on_mqtt(topic, payload)`, which returns (sensors, readings) to store or
# None. `status()` returns keys to merge into /health (packs/smartcitizen: `direct`).
# Gated like an adapter: PACKS_ALLOW_CODE, or an official pack's own switch. Each pack's module is loaded once per
# process, so what it keeps (packs/home-assistant: the entities it has announced) lasts; which packs are on is read
# again every minute, because emit runs on every MQTT message.
_HOOKS: dict = {"at": 0.0, "on": []}
_HOOK_MODULES: dict = {}


def _hook_modules() -> list:
    if time.time() - _HOOKS["at"] < 60:
        return _HOOKS["on"]
    on = []
    for d in _enabled():
        f = d / "hooks.py"
        if not f.is_file() or not (_allow_code() or _official_on(d)):
            continue
        if f not in _HOOK_MODULES:
            try:
                spec = importlib.util.spec_from_file_location(f"planetai_pack_{d.name}_hooks", f)
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)  # type: ignore[union-attr]
                _HOOK_MODULES[f] = mod
            except Exception as e:  # noqa: BLE001
                log.warning("pack %s: hooks.py failed to load (%s)", d.name, e)
                continue
        on.append((d.name, _HOOK_MODULES[f]))
    _HOOKS.update(at=time.time(), on=on)
    return on


def collect(name: str, *args) -> list:
    """Call `name` in every pack that has it and keep what each returns, less None. A pack that fails is logged and
    never stops the node's own work."""
    out = []
    for pack, mod in _hook_modules():
        fn = getattr(mod, name, None)
        if callable(fn):
            try:
                got = fn(*args)
            except Exception as e:  # noqa: BLE001
                log.warning("pack %s: %s failed (%s)", pack, name, type(e).__name__)
                continue
            if got is not None:
                out.append(got)
    return out


def emit(name: str, *args) -> None:
    collect(name, *args)


def mqtt_topics() -> list[tuple[str, int]]:
    """The broker topics the packs that are on read their devices from. Read when the node connects, so a pack
    switched on later is subscribed at the next reconnect or restart."""
    return [tuple(t) for _, mod in _hook_modules() for t in getattr(mod, "MQTT_TOPICS", [])]


def adapters(hc):
    """Source adapters from code packs. Off unless PACKS_ALLOW_CODE=1, or an official pack's own switch is on — a
    pack's adapter.py runs with this node's privileges and network access. Read it before you enable it."""
    out = []
    for d in _enabled():
        f = d / "adapter.py"
        if not f.is_file():
            continue
        if not (_allow_code() or _official_on(d)):
            log.warning("pack %s ships code; set PACKS_ALLOW_CODE=1 to run it (read %s first)", d.name, f)
            continue
        try:
            stamp = f.stat().st_mtime
            if d.name in _loaded and _loaded[d.name][0] == stamp:
                mod = _loaded[d.name][1]
            else:
                spec = importlib.util.spec_from_file_location(f"planetai_pack_{d.name}", f)
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)  # type: ignore[union-attr]
                _loaded[d.name] = (stamp, mod)
            out.append((d.name, lambda m=mod: m.fetch(hc)))
        except Exception as e:  # noqa: BLE001
            log.warning("pack %s: adapter failed to load (%s)", d.name, e)
    return out
