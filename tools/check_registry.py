#!/usr/bin/env python3
"""Hold the vendored source registry to its pin, and every pack's `sources:` id to an entry in it.

    python3 tools/check_registry.py          # in `make lint`

`data/sources/` is a snapshot of `awesome-fabcity-data` at one commit (tools/sync_registry.sh). Nine
things have to stay true about it, and one is only a warning.

  · REGISTRY_VERSION is there and parses — without it nothing downstream can say what it is serving.
  · Its `entries` count, the YAML file count and index.json's length are the same number. They come
    apart when a sync is interrupted, and the symptom is a node quietly serving a short list.
  · index.json is exactly what the YAML folds to. Nothing here edits a source entry: the registry's
    source of truth is upstream, and a hand edit that survives is a fork nobody declared.
  · Every entry sits in the directory its own `pillar`/`scale` name, because `slug` and `cell` are
    both derived from the path and a mismatch makes them lie.
  · Every `sources:` id in every packs/*/pack.yaml resolves to an entry.
  · Every entry a pack reads names an `adapter`, and every `adapter` resolves here: `pack:<id>` to a
    folder under packs/, `core:<fn>` to a function in app/sources.py or app/bootstrap.py.
  · Every review under reviews/ names an `entry` that is one of the vendored entries. A review of a
    source this pin does not carry is evidence about nothing, and it would fold onto no row.
  · Every cells/<file>.yaml is named for its own `cell` key. Both are no-ops on a pin taken before
    those trees existed upstream, which is every pin before 2026-09-22.

**The `adapter` check was the registry's own (scripts/wired.py there) until 24 Oct 2026.** It read this
repository's live main, so its green expired when the node shipped, with no commit to the registry, and
every move of a reader out of the core left it red until a registry PR and a re-pin caught up. Here it
reads the pin and this tree, the two things that ship together, so a move and its re-pin are one PR.

**This replaced tools/check_sources.py, which asked the last question of a sibling checkout of the
registry — and so answered it only on a laptop that had one.** In CI and on a node it printed a line
and exited 0, which meant a pack could name a slug that does not exist and the build stayed green all
the way to a tarball. It also let a pack name a slug that is on upstream main but not in the pin,
which 404s on every node that installs it. The snapshot is here, so now the check is too.

`synced` older than 180 days WARNS and does not fail — the convention data/platform_floors.yml set.
A stale pin is a conversation about a sync, not a broken build.
"""
from __future__ import annotations

import datetime
import json
import re
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_registry_index import build, render  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SOURCES = ROOT / "data" / "sources"
STALE_DAYS = 180

ID = re.compile(r"^([a-z]+)/([a-z]+)/([a-z0-9-]+)$")


def declared() -> list[tuple[Path, str]]:
    """Every (pack.yaml, id) pair. Parsed with a regex rather than yaml, because a pack.yaml that does
    not parse is already somebody else's failure in this same lint."""
    out = []
    for p in sorted(ROOT.glob("packs/*/pack.yaml")):
        m = re.search(r"^sources:\s*\[(.*?)\]", p.read_text(), re.M | re.S)
        if m:
            out += [(p, s.strip()) for s in m.group(1).split(",") if s.strip()]
    return out


def main() -> int:
    errs: list[str] = []
    warns: list[str] = []
    ver_path = SOURCES / "REGISTRY_VERSION"
    if not ver_path.is_file():
        print(f"  x {ver_path.relative_to(ROOT)} is missing — the node ships no registry.")
        print("    Vendor one:  tools/sync_registry.sh <commit sha of awesome-fabcity-data>")
        return 1

    ver = dict(l.split("=", 1) for l in ver_path.read_text().split() if "=" in l)
    for k in ("sha", "short", "synced", "entries", "source"):
        if not ver.get(k):
            errs.append(f"REGISTRY_VERSION has no `{k}=` line")
    if errs:
        print(f"  x {ver_path.relative_to(ROOT)} does not parse: " + "; ".join(errs))
        return 1

    try:
        entries = build()
    except Exception as e:  # noqa: BLE001
        print(f"  x the vendored YAML does not fold: {e}")
        return 1
    yaml_n = len(list((SOURCES / "data").rglob("*.yaml")))
    index_path = SOURCES / "index.json"
    index = json.loads(index_path.read_text()) if index_path.is_file() else []

    if not (int(ver["entries"]) == yaml_n == len(index)):
        errs.append(f"REGISTRY_VERSION says {ver['entries']} entries, the YAML has {yaml_n}, "
                    f"index.json has {len(index)} — a sync stopped half-way")

    if index_path.is_file() and index_path.read_text() != render(entries):
        errs.append("index.json is not what the YAML folds to: it was hand-edited, or a sync was left "
                    "half-done. It is generated — regenerate it: python3 tools/build_registry_index.py")

    for e in entries:
        pillar, scale, _ = e["slug"].split("/")
        if e.get("pillar") != pillar or e.get("scale") != scale:
            errs.append(f"{e['slug']}: filed under {pillar}/{scale} but says "
                        f"{e.get('pillar')}/{e.get('scale')} — `slug` and `cell` come off the path")

    ids = {e["slug"] for e in entries}
    pairs = declared()
    for path, sid in pairs:
        if not ID.match(sid):
            errs.append(f"{path.relative_to(ROOT)}: `{sid}` is not a <pillar>/<scale>/<slug> id")
        elif sid not in ids:
            slug = sid.rsplit("/", 1)[1]
            near = sorted(i for i in ids if slug in i or i.rsplit("/", 1)[1] in slug)
            hint = f"did you mean `{near[0]}`?" if near else "no entry in the registry"
            errs.append(f"{path.relative_to(ROOT)}: `{sid}` does not resolve — {hint}")

    # `adapter` is a pointer, and a pointer is only worth having if it is dereferenced: both directions.
    pack_dirs = {p.parent.name for p in ROOT.glob("packs/*/pack.yaml")}
    funcs = {f for mod in ("app/sources.py", "app/bootstrap.py")
             if (ROOT / mod).is_file() for f in re.findall(r"^def ([a-z][a-z_]*)\(", (ROOT / mod).read_text(), re.M)}
    named = {e["slug"]: e["adapter"] for e in entries if e.get("adapter")}
    for sid in sorted({sid for _, sid in pairs if sid in ids} - set(named)):
        errs.append(f"`{sid}` is read by a pack and its entry names no `adapter` — PR `adapter: pack:<id>` "
                    f"to it upstream")
    for slug, a in sorted(named.items()):
        kind, _, name = a.partition(":")
        if name not in (pack_dirs if kind == "pack" else funcs):
            where = "no such folder under packs/" if kind == "pack" else "no such function in app/sources.py or app/bootstrap.py"
            errs.append(f"`{slug}`: adapter `{a}` names nothing here ({where}) — PR the new one upstream")

    # reviews/ and cells/ arrived upstream 2026-09-22. Absent is fine and silent: a pin from before
    # then simply has neither tree, and `rglob` over a directory that is not there yields nothing.
    for rp in sorted((SOURCES / "reviews").rglob("*.yaml")) if (SOURCES / "reviews").is_dir() else []:
        try:
            r = yaml.safe_load(rp.read_text()) or {}
        except yaml.YAMLError as e:  # noqa: PERF203
            errs.append(f"{rp.relative_to(ROOT)}: does not parse — {e}")
            continue
        entry = r.get("entry") if isinstance(r, dict) else None
        if not entry:
            errs.append(f"{rp.relative_to(ROOT)}: no `entry:` — a review has to say what it reviewed")
        elif entry not in ids:
            errs.append(f"{rp.relative_to(ROOT)}: reviews `{entry}`, which this pin does not carry — "
                        f"a review of a source that is not here folds onto no row")

    for cp in sorted((SOURCES / "cells").glob("*.yaml")) if (SOURCES / "cells").is_dir() else []:
        try:
            c = yaml.safe_load(cp.read_text()) or {}
        except yaml.YAMLError as e:  # noqa: PERF203
            errs.append(f"{cp.relative_to(ROOT)}: does not parse — {e}")
            continue
        key = c.get("cell") if isinstance(c, dict) else None
        if not key or "|" not in str(key):
            errs.append(f"{cp.relative_to(ROOT)}: no `cell:` key of the form Pillar|Scale")
        else:
            pillar, _, scale = str(key).partition("|")
            want = f"{pillar.lower()}-{scale.lower()}.yaml"
            if cp.name != want:
                errs.append(f"{cp.relative_to(ROOT)}: cell is {key!r}, so the file must be named "
                            f"{want} — the name and the key are two spellings of one cell")

    try:
        age = (datetime.date.today() - datetime.date.fromisoformat(ver["synced"])).days
        if age > STALE_DAYS:
            warns.append(f"the pin is {age} days old (synced {ver['synced']}, limit {STALE_DAYS}): "
                         f"tools/sync_registry.sh <sha> to catch up")
    except ValueError:
        errs.append(f"REGISTRY_VERSION: `synced={ver['synced']}` is not an ISO date")

    if errs:
        print(f"  x the vendored registry does not hold ({len(errs)}):")
        for e in errs:
            print(f"      {e}")
        print("    A source entry is upstream's to change, not this repo's: PR it to "
              f"{ver['source']}, then re-pin with tools/sync_registry.sh <merge sha>.")
        return 1

    print(f"  {len(index)} registry entries @ {ver['short']}, {len(pairs)} pack source ids resolve, "
          f"{len(named)} adapters name something here")
    for w in warns:
        print(f"  ! {w}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
