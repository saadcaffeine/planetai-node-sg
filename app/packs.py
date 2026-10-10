"""Packs — the extension point. Core packs ship in packs/ with the release; wild packs are added by whoever runs
the node (`planetai packs add`, docs/decisions/2026-10-01-packs.md).

A pack is a folder in packs/ with a pack.yaml and any of:
    rules.yml    extra alert rules (SQL + message)      DATA — no code, safe to merge from anyone
    cells.yml    extra Index cells (SQL → fci-cells-v0) DATA — no code
    adapter.py   a source adapter (Python function)     CODE — runs with the node's privileges

Data packs are the default and the point: most useful contributions are a rule and a threshold that
someone learned the hard way in their city. Code packs need review — see docs/PACKS.md.

Loading is deliberately dumb: scan the directory, parse the YAML, import the module. No registry service,
no dependency resolution, no lifecycle hooks. If a pack is broken the node logs it and carries on.
"""
from __future__ import annotations

import importlib.util
import logging
import os
from pathlib import Path

import yaml

log = logging.getLogger("planetai.packs")
PACKS_DIR = Path(os.getenv("PACKS_DIR", "/app/packs"))
CORE_CHANNELS = Path(os.getenv("CHANNELS_PATH", "/app/config/channels.yml"))


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
            spec = ((yaml.safe_load((d / "pack.yaml").read_text()) or {}).get("requires") or {}).get("node")
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
            m = yaml.safe_load((d / "pack.yaml").read_text()) or {}
        except Exception as e:  # noqa: BLE001
            log.warning("pack %s: bad pack.yaml (%s)", d.name, e); continue
        m["id"] = m.get("id", d.name)
        m["path"] = str(d)
        m["kind"] = "code" if (d / "adapter.py").is_file() else "data"
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
        core = yaml.safe_load(CORE_RULES.read_text()) or []
    except FileNotFoundError:
        core = []
    return core + alerts()            # a pack rule with `contributes:` is part of the report, not an alert


def module(pack: str, name: str = "adapter"):
    """A pack's own module, imported from PACKS_DIR, or None if it is not on this node.

    `packs` in app/ is this LOADER, not a package: the pack directories live under PACKS_DIR and
    `import packs.make.adapter` fails with "packs is not a package". Two callers worked around that
    by inserting a path and importing bare — `app/issues/engine.py::_where_to_go` and
    `app/report.py` — and both defaulted PACKS_DIR to "../packs", which is not where a node keeps
    them. It is /app/packs in the image, and PACKS_DIR is unset there, so both imports failed on
    every node: `asks.where` was null with the pack on and a lab 3.3 km away, and the report's
    `make` line never appeared. Neither said anything, because both swallow the failure by design.

    One place knows this path, and it is the one that already reads every pack. This also stops
    mutating sys.path on each call, which the two workarounds did once per request."""
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
            for r in yaml.safe_load(f.read_text()) or []:
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
            for c in yaml.safe_load(f.read_text()) or []:
                c["pack"] = d.name
                out.append(c)
        except Exception as e:  # noqa: BLE001
            log.warning("pack %s: bad cells.yml (%s)", d.name, e)
    return out


ROLES = ("ambient", "enclosure", "device_health", "derived", "index")


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
            decls = yaml.safe_load(f.read_text()) or []
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
    for f in sorted(PACKS_DIR.glob("*/*.py")):
        d, name = f.parent, f.stem
        if name == "adapter" or not (d / "pack.yaml").is_file():
            continue
        # ponytail: wild means `.wild` beside pack.yaml, written by `planetai packs add`; a pack copied in by hand
        # counts as core. A list of core ids shipped with the release would close that, if hand-copied packs spread.
        if (d / ".wild").is_file():
            try:
                listed = (yaml.safe_load((d / "pack.yaml").read_text()) or {}).get("agent_scripts")
            except Exception:  # noqa: BLE001 — a pack.yaml that does not parse lists nothing
                listed = None
            if not (isinstance(listed, list) and name in listed):
                continue
        out.append(f"{d.name}/{name}")
    return out


def adapters(hc):
    """Source adapters from code packs. Off unless PACKS_ALLOW_CODE=1 — a pack's adapter.py runs with this
    node's privileges and network access. Read it before you enable it."""
    out = []
    for d in _enabled():
        f = d / "adapter.py"
        if not f.is_file():
            continue
        if not _allow_code():
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
