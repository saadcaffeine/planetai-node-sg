#!/usr/bin/env python3
"""Hold the node's copy of the frozen layer to the design repo it was copied from.

    python3 tools/check_theme.py                 # in `make lint`, and it FAILS
    python3 tools/check_theme.py --update        # after copying new files from planetai-design

Three files under `app/static/` are not this repo's to edit: `planetai-theme.css` is generated from
planetai-design/references/planetai-layer.md, and `signs.svg` and `kilometre-cells.json` are that
repo's assets. They were copied here because a node serves its dashboard on a LAN that may have no
route out, and a copy with no guard drifts — a colour edited on this side reaches every screen in
the house on the next reload with nothing having said what moved. This is the guard.

**It used to read a sibling checkout, and so answered nowhere that mattered.** This runs where
`make lint` runs — a dev machine and CI — and `planetai-design` is checked out on neither by default.
There it printed one line and exited 0, so an edit to a frozen file passed **every automated check a
pull request gets**, and the tarball carried it to every node on the next update. The same hole
`tools/check_sources.py` had, found the same way (19 Sep 2026). So the question is now asked of
something that is always here: `data/frozen_layer.txt` records the sha256 of each file and the
planetai-design commit they were copied from, and the hashes are checked on every lint, everywhere.

That is not a weaker guard than the byte comparison, because it does not replace it. Where the design
repo IS checked out, both run — and the comparison now reads the **pinned commit** rather than
whatever branch that checkout is sitting on. It was sitting on `dashboard-directions-2026-09` the day
this was written, and a gate whose answer depends on a neighbour's branch is not a gate.

`--update` rewrites the pin, and REFUSES to do it unless the design repo is present and the files
match it. You cannot bless a local edit by re-running it; you can only record a copy that was really
made. That is the whole reason the two halves are kept.

**One line is allowed to differ, and it is named.** `planetai-theme.css` declares the mono at
`fonts/jetbrains-mono-latin.woff2`. `GET /static/{name}` takes a NAME and not a path, deliberately,
on a port that answers a household LAN, so that request 404'd on every page until 14 October 2026, when
`main.static_mono` began answering that one fixed path (still no path parameter). `tokens.css` — this
repo's file, where the other three faces already live — declares the same family at the flat name
the node does serve, which is the declaration that resolves. This said `dashboard.css` until
21 September 2026, and NO file declared it at all: the mono was the fourth of four faces and the
only one never brought over, so every number on the page had been in a fallback since the layer
arrived. So a `src:` line whose two sides name the same FILE by different paths is reported and
forgiven. Anything else — a second such line, a different file, a changed token, a moved brace —
fails, and the fix is to copy the file again rather than to widen this.

Point the design repo somewhere else with PLANETAI_DESIGN_REPO.
"""
from __future__ import annotations

import datetime
import difflib
import hashlib
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DESIGN = Path(os.environ.get("PLANETAI_DESIGN_REPO", ROOT.parent / "planetai-design"))
PIN = ROOT / "data" / "frozen_layer.txt"

# node copy -> its original in the design repo. Copied verbatim; neither side is edited here.
FROZEN = {
    "app/static/planetai-theme.css": "planetai-theme.css",
    "app/static/signs.svg": "assets/signs/signs.svg",
    "app/static/kilometre-cells.json": "assets/h3/kilometre-cells.json",
}

SRC_LINE = re.compile(r"^(\s*src:\s*url\(['\"]?)([^'\")]+)(.*)$")


def forgiven(ours: str, theirs: str) -> str | None:
    """The one difference this project has decided to live with, or None.

    Both sides must be a `src: url(...)` naming the same file by a different path, and nothing else
    on the line may move. A basename comparison is the normalisation: `fonts/x.woff2` and `x.woff2`
    are the same file reached two ways, `x.woff2` and `y.woff2` are two files.
    """
    a, b = SRC_LINE.match(ours), SRC_LINE.match(theirs)
    if not (a and b):
        return None
    if (a.group(1), a.group(3)) != (b.group(1), b.group(3)):
        return None
    if a.group(2) == b.group(2) or a.group(2).rsplit("/", 1)[-1] != b.group(2).rsplit("/", 1)[-1]:
        return None
    return f"{b.group(2)} -> {a.group(2)}"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_pin() -> dict:
    """{design_repo, design_sha, copied, sha256: {rel: hex}} — or {} when the file is not there."""
    if not PIN.is_file():
        return {}
    out: dict = {"sha256": {}}
    for line in PIN.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("sha256 "):
            _, rel, hexd = line.split()
            out["sha256"][rel] = hexd
        elif "=" in line:
            k, v = line.split("=", 1)
            out[k] = v
    return out


def git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(DESIGN), *args], capture_output=True, text=True, timeout=10)


def original(sha: str, sub: str) -> tuple[str | None, str]:
    """The design repo's copy of `sub` at the pinned commit, and a word saying where it came from.

    Falls back to the working tree when that commit is not in the checkout — a shallow clone, or a
    pin newer than the last fetch — because a comparison against something is worth more than none,
    as long as the output says which it was.
    """
    r = git("show", f"{sha}:{sub}")
    if r.returncode == 0:
        return r.stdout, f"{sha[:7]}"
    p = DESIGN / sub
    return (p.read_text() if p.is_file() else None), "working tree"


def compare(rel: str, ours: list[str], theirs_text: str, where: str,
            errs: list[str], notes: list[str]) -> None:
    theirs = theirs_text.splitlines()
    if len(ours) != len(theirs):
        errs.append(f"{rel}: {len(ours)} lines here, {len(theirs)} in planetai-design@{where}. Copy it again.")
        return
    bad = []
    for i, (o, t) in enumerate(zip(ours, theirs), 1):
        if o == t:
            continue
        note = forgiven(o, t)
        if note:
            notes.append(f"{rel}:{i} the mono, flattened by decision: {note}")
        else:
            bad.append(i)
    if bad:
        errs.append(f"{rel}: {len(bad)} line(s) differ from planetai-design@{where}, at "
                    f"{', '.join(map(str, bad))}:\n"
                    + "".join(difflib.unified_diff([ours[i - 1] + "\n" for i in bad],
                                                   [theirs[i - 1] + "\n" for i in bad],
                                                   fromfile=rel, tofile=f"planetai-design@{where}",
                                                   n=0)).rstrip())


def write_pin(sha: str, repo: str) -> None:
    lines = [
        "# The frozen layer: three files under app/static/ that this repository does not own, and the",
        "# planetai-design commit they were copied from. tools/check_theme.py holds the files to these",
        "# hashes on EVERY lint — including CI, where the design repo is not checked out and the byte",
        "# comparison cannot run. Do not edit this by hand: copy the file from planetai-design,",
        "# then run `python3 tools/check_theme.py --update`, which refuses unless the copy really matches.",
        "#",
        "# The hashes are of the files as they are HERE. Where a line differs from the original by",
        "# decision (the mono's path — see tools/check_theme.py), this records what this repo serves.",
        f"design_repo={repo}",
        f"design_sha={sha}",
        f"copied={datetime.date.today().isoformat()}",
    ]
    lines += [f"sha256 {rel} {sha256(ROOT / rel)}" for rel in FROZEN]
    PIN.write_text("\n".join(lines) + "\n")


def main(argv: list[str]) -> int:
    update = "--update" in argv
    errs: list[str] = []
    notes: list[str] = []
    warns: list[str] = []

    for rel in FROZEN:
        if not (ROOT / rel).is_file():
            errs.append(f"{rel} is missing — the dashboard will not render without it")

    # ---- the half that runs everywhere: the files are the bytes the pin says they are.
    pin = read_pin()
    if not pin and not update:
        print(f"  x {PIN.relative_to(ROOT)} is missing, so nothing holds the frozen layer where the")
        print("    design repo is not checked out — which is CI and every node. Recreate it beside a")
        print("    planetai-design checkout: python3 tools/check_theme.py --update")
        return 1
    # --update skips this: it is the thing --update rewrites, so requiring it to pass first would
    # mean a pin that is wrong — hand-edited, or a half-finished update — could never be repaired.
    # What --update is held to is the comparison below, against the design repo itself — at
    # origin/main, not at the pin it is about to replace.
    if pin and not update and not errs:
        for rel in FROZEN:
            want = pin["sha256"].get(rel)
            got = sha256(ROOT / rel)
            if want is None:
                errs.append(f"{rel}: no sha256 for it in {PIN.relative_to(ROOT)}")
            elif want != got:
                errs.append(f"{rel} has been edited here: sha256 {got[:12]}…, pinned {want[:12]}…. "
                            f"This file belongs to planetai-design. Change it there, copy it back, "
                            f"then --update.")

    # ---- the half that needs the sibling: what the pinned commit actually says, line by line.
    compared: set[str] = set()
    if DESIGN.exists() and not errs:
        head = git("rev-parse", "origin/main").stdout.strip()
        # A plain run is held to the PIN: that is the commit these bytes were copied from, and the
        # neighbour's branch is not evidence about it. `--update` is held to the design repo as it is
        # NOW, because the copy being recorded came from now — measuring a new copy against the old
        # pin is the one comparison that cannot pass whenever there is something to update, and that
        # is what this line said until 19 September 2026. It made --update work only when the files
        # already matched the pin, which is exactly when there is nothing to update.
        sha = (head or "") if update else (pin.get("design_sha", "") if pin else "")
        for rel, sub in FROZEN.items():
            text, where = original(sha, sub) if sha else (
                (DESIGN / sub).read_text() if (DESIGN / sub).is_file() else None, "working tree")
            if text is None:
                errs.append(f"{rel}: {sub} is missing from planetai-design — nothing to hold it to")
                continue
            compare(rel, (ROOT / rel).read_text().splitlines(), text, where, errs, notes)
            compared.add(where)
        # Say what was actually read. The first cut of this printed the pinned sha whatever happened,
        # so a pin that is not in the checkout — a shallow clone, or a sha nobody fetched — read as a
        # comparison made against it. It had not been: original() had fallen back to the working tree,
        # which is the neighbour's branch, which is the thing this gate was fixed to stop trusting.
        if "working tree" in compared and sha:
            warns.append(f"{sha[:7]} is not in the {DESIGN.name} checkout, so the comparison read its "
                         f"WORKING TREE instead — whatever branch it is on. git -C {DESIGN} fetch, "
                         f"then run this again.")
        elif head and sha and head != sha and not update:
            behind = git("rev-list", "--count", f"{sha}..origin/main").stdout.strip() or "some"
            warns.append(f"planetai-design is {behind} commit(s) past the pin ({sha[:7]}). If the layer "
                         f"moved, copy the files and --update; if it did not, nothing to do.")
    elif not DESIGN.exists():
        warns.append(f"{DESIGN.name} is not checked out here, so the line-by-line comparison did not run "
                     f"— the hashes above did. It is a sibling checkout, not a dependency.")

    for n in notes:
        print(f"  ~ {n}")
    if errs:
        print("\n".join(f"  x {e}" for e in errs))
        print("\n  The frozen layer belongs to planetai-design. Change it there, then copy it here —\n"
              "  and if a second line has to differ, it needs a decision, not an exception in this file.")
        return 1

    if update:
        if not DESIGN.exists() or not compared:
            print(f"  x --update needs {DESIGN.name} checked out beside this repo: the pin is only")
            print("    allowed to move when the files here really match the ones they were copied from.")
            return 1
        sha = git("rev-parse", "origin/main").stdout.strip()
        if not sha:
            print(f"  x could not read origin/main in {DESIGN} — fetch it, then --update.")
            return 1
        repo = (git("config", "--get", "remote.origin.url").stdout.strip()
                or "https://github.com/fabcity/planetai-design")
        write_pin(sha, repo)
        print(f"  pinned {len(FROZEN)} frozen files to planetai-design@{sha[:7]}")
        return 0

    print(f"  {len(FROZEN)} frozen files match their pinned hashes"
          + (f" and planetai-design@{'/'.join(sorted(compared))}" if compared else "")
          + (f", with {len(notes)} line forgiven by decision" if notes else ""))
    for w in warns:
        print(f"  ! {w}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
