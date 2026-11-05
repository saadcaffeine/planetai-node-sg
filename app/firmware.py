"""The firmware the workbench flashes, kept on this node so the workbench flashes with no internet (Tomas, 27 Oct
2026: "The workbench should be able to run offline in the node").

Two folders, copied as their publishers lay them out, so every manifest's relative paths still hold:
  meshtastic  planetai.fab.city/sensors/firmware/meshtastic/, the release the site pins (scripts/fetch_meshtastic.sh
              there checks each binary against the release's own checksums and publishes SHA256SUMS beside them;
              a file here that does not match its line is refused, never kept)
  bayu        Making Sense Bali's flash/firmware/bayu/, rebuilt by its own workflow
A file under a version folder never changes, so one already here is not fetched again. The index files (files.json,
the manifests) are written last, so the page never reads a manifest that names a file not here yet. Then whatever no
index names any more is deleted, so old Bayu builds do not pile up in out/. Served at /static/firmware/ (app/main.py).
"""
import hashlib
import os
from pathlib import Path, PurePosixPath

SOURCES = {"meshtastic": "https://planetai.fab.city/sensors/firmware/meshtastic/",
           "bayu": "https://makingsense.fablabbali.com/flash/firmware/bayu/"}


def _rel(p: str) -> str:
    """A path from someone else's index, refused unless it stays inside its folder."""
    q = PurePosixPath(str(p))
    if not q.parts or q.is_absolute() or ".." in q.parts:
        raise ValueError(f"a firmware index names a path outside its folder: {p!r}")
    return str(q)


def _parts(manifest: dict) -> list[str]:
    return [_rel(p["path"]) for b in manifest.get("builds", []) for p in b.get("parts", [])]


def wanted(name: str, get) -> tuple[dict[str, bytes], list[str], dict[str, str]]:
    """(the index files with their bytes, the files they name, the SHA-256 each must have where the publisher says)
    for one source. `get(url) -> bytes`."""
    import json
    base, idx, files, sums = SOURCES[name], {}, [], {}
    if name == "meshtastic":
        idx["files.json"] = get(base + "files.json")
        f = json.loads(idx["files.json"])
        v = _rel(f["version"])
        idx[f"{v}/SHA256SUMS"] = get(base + f"{v}/SHA256SUMS")
        for line in idx[f"{v}/SHA256SUMS"].decode().splitlines():
            if line.strip():
                h, n = line.split(None, 1)
                sums[_rel(f"{v}/{n.strip().lstrip('*')}")] = h.lower()
        for b in f.get("boards", {}).values():
            if b.get("manifest"):
                m = _rel(b["manifest"])
                idx[m] = get(base + m)
                files += _parts(json.loads(idx[m]))
            files += [_rel(f"{f['version']}/{b[k]}") for k in ("uf2", "ota") if b.get(k)]
    else:
        idx["manifest.json"] = get(base + "manifest.json")
        files += _parts(json.loads(idx["manifest.json"]))
    return idx, files, sums


def _write(path: Path, body: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".part")
    tmp.write_bytes(body)
    os.replace(tmp, path)


def mirror(root: Path, get) -> dict[str, int]:
    """Bring root/<source>/ up to date with each source. A source that fails keeps what it had; the error is raised
    after the other source had its turn, so the loop records it. Returns the files fetched, per source."""
    fetched, errors = {}, []
    for name, base in SOURCES.items():
        dest, n = root / name, 0
        try:
            idx, files, sums = wanted(name, get)
            for rel in files:
                if not (dest / rel).exists():
                    body = get(base + rel)
                    if rel in sums and hashlib.sha256(body).hexdigest() != sums[rel]:
                        raise ValueError(f"{rel} does not match its SHA256SUMS line")
                    _write(dest / rel, body)
                    n += 1
            for rel, body in idx.items():
                _write(dest / rel, body)
        except Exception as e:  # noqa: BLE001 — one publisher down is no reason to skip the other
            errors.append(f"{name}: {type(e).__name__}: {str(e).splitlines()[0] if str(e) else ''}")
            continue
        keep = {dest / r for r in [*files, *idx]}
        for f in sorted(dest.rglob("*"), reverse=True):     # deepest first, so an emptied folder goes too
            if f.is_file() and f not in keep:
                f.unlink()
            elif f.is_dir() and not any(f.iterdir()):
                f.rmdir()
        fetched[name] = n
    if errors:
        raise RuntimeError("firmware not refreshed: " + "; ".join(errors))
    return fetched
