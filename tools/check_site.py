#!/usr/bin/env python3
"""Hold the programme page to the node it describes.

    python3 tools/check_site.py                  # against ../planetai (or PLANETAI_SITE_REPO)
    python3 tools/check_site.py --version v0.73  # and the release about to be cut (tools/release.sh)

The programme page (planetai.fab.city, `web/src/data.js` in the site repo) states facts about this
repository: the release, how many packs, which languages, how many documentation pages, node #1's ρ.
On 23 September 2026 it was eight releases behind while every gate in both repos was green, because
no gate compared the two (R25). This is that gate. `tools/release.sh` runs it before tagging, so a
release cannot be cut while the page describes another one.

It also holds the purpose to one wording. `docs/site/introduction.md` is the canonical statement; the
programme page, the README, `llms.txt`, `AGENTS.md`, the dashboard's foot and the node's own /llms.txt
quote it, and a copy that drifts fails here rather than on a reader.

It reads the site's source with regular expressions, not a JavaScript engine: `data.js` is a file of
literals, and a fact this cannot find is reported as missing rather than guessed. A site repo that is
not checked out beside this one is skipped with a warning, because a node's CI has no site repo.
"""
import argparse
import datetime as dt
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PURPOSE = ("Its purpose is fixed: clean air, water and soil for the people and the other living things "
           "around each node.")
# 26 Sep 2026 (R31b): the lead follows the programme page. The site's LINE is its h1, and it sits inside LEAD word
# for word; before this, LEAD said "the … layer for" and LINE did not, and nothing compared them.
LEAD = "PLANETAI is hyperlocal compute and intelligence for distributed production"
RHO_MAX_AGE_DAYS = 30

# Words the node retired on 23 Sep 2026 for the programme page's (docs/site/concepts.md, "Words").
# Checked in docs/site prose, where a person reads them; the Words table itself names them on purpose.
RETIRED = [r"\bwall outside\b", r"\bgrain rail\b", r"\basks answered\b", r"\bthe rail\b"]
RETIRED_OK = {"concepts.md"}


def flat(s):
    return " ".join(s.split())


def pack_kinds(ref=None):
    """kind: per pack.yaml, in the working tree, or at a git ref (the release the page describes)."""
    if ref is None:
        texts = [p.read_text(encoding="utf-8") for p in sorted((ROOT / "packs").glob("*/pack.yaml"))]
    else:
        git = lambda *a: subprocess.run(["git", "-C", str(ROOT), *a], capture_output=True, text=True)
        names = git("ls-tree", "--name-only", ref, "packs/")
        if names.returncode:
            return None
        texts = [t.stdout for t in (git("show", f"{ref}:{d}/pack.yaml") for d in names.stdout.split()) if t.returncode == 0]
    kinds = {}
    for t in texts:
        m = re.search(r"^kind:\s*(\w+)", t, re.M)
        kinds[m.group(1) if m else "?"] = kinds.get(m.group(1) if m else "?", 0) + 1
    return kinds


def node_facts():
    kinds = pack_kinds()
    loc = re.search(r"^LOCALES\s*=\s*\(([^)]*)\)", (ROOT / "app/issues/__init__.py").read_text(), re.M)
    locales = re.findall(r'"(\w+)"', loc.group(1)) if loc else []
    sys.path.insert(0, str(ROOT / "tools"))
    import build_docs  # noqa: E402 — the NAV is the page list; importing it renders nothing
    return {"packs": sum(kinds.values()), "data": kinds.get("data", 0), "code": kinds.get("code", 0),
            "languages": len(locales), "docs": len(build_docs.PAGES)}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--version", help="the release about to be cut, e.g. v0.73 (default: not compared)")
    ap.add_argument("--site", default=os.getenv("PLANETAI_SITE_REPO", str(ROOT.parent / "planetai")))
    a = ap.parse_args()
    errs = []

    # The purpose, in this repository.
    intro = flat((ROOT / "docs/site/introduction.md").read_text(encoding="utf-8"))
    if LEAD not in intro or PURPOSE not in intro:
        errs.append("docs/site/introduction.md no longer carries the canonical lead and purpose sentence; "
                    "if the wording changed on purpose, change it here and in every copy together")
    for rel in ("README.md", "llms.txt", "AGENTS.md", "app/static/dashboard.js", "app/main.py"):
        txt = flat(re.sub(r"['\"]\s*\+\s*['\"]|['\"]\s*\n\s*['\"]", "", (ROOT / rel).read_text(encoding="utf-8")))
        txt = flat(txt.replace("> ", " "))
        if "clean air, water and soil for the people and the other living things around" not in txt:
            errs.append(f"{rel} does not quote the purpose (clean air, water and soil …)")

    # Retired words in the documentation.
    for p in sorted((ROOT / "docs/site").glob("*.md")):
        if p.name in RETIRED_OK:
            continue
        body = re.sub(r"```.*?```", "", p.read_text(encoding="utf-8"), flags=re.S)
        for pat in RETIRED:
            for m in re.finditer(pat, body, re.I):
                line = body[:m.start()].count("\n") + 1
                errs.append(f"docs/site/{p.name}:{line}: '{m.group(0)}' is a retired word (concepts.md, Words)")

    site = Path(a.site)
    data = site / "web/src/data.js"
    if not data.exists():
        print(f"  ! no site checkout at {site}; the programme page was not compared (set PLANETAI_SITE_REPO)")
        if errs:
            sys.exit("\n".join(f"  x {e}" for e in errs))
        print("  purpose: one wording in the docs, README, llms.txt, AGENTS.md, the dashboard and /llms.txt")
        return
    js = data.read_text(encoding="utf-8")
    facts = node_facts()

    def grab(pat, what):
        m = re.search(pat, js, re.S)
        if not m:
            errs.append(f"web/src/data.js: could not find {what}; the page's shape changed, update this check")
        return m

    # The release is compared only when one is named: `make lint` runs between releases, when the page
    # may already say the version about to be cut. `tools/release.sh` names it.
    want = a.version
    m = grab(r"export const RELEASE = \{.*?tag:\s*'([^']+)'", "RELEASE.tag")
    if m and want and m.group(1) != want:
        errs.append(f"the programme page says {m.group(1)}; this release is {want}")
    # The page counts the packs of the release it names. Between releases main may add or move a pack (#173 moved
    # xiaomi-air out after v0.76), and comparing the page to main then failed every commit on a page that was
    # right. So: at release time against the tree being tagged, between releases against the tag the page names.
    page_tag = (re.search(r"export const RELEASE = \{.*?tag:\s*'([^']+)'", js, re.S) or [None, None])[1]
    at = None if want else page_tag
    kinds = pack_kinds(at) if at else pack_kinds()
    if kinds is None:
        kinds, at = pack_kinds(), None   # the tag is not in this clone: fall back to the tree, and say so below
    have = (sum(kinds.values()), kinds.get("data", 0), kinds.get("code", 0))
    m = grab(r"packs:\s*\{\s*total:\s*(\d+),\s*data:\s*(\d+),\s*code:\s*(\d+)", "RELEASE.packs")
    if m and (int(m.group(1)), int(m.group(2)), int(m.group(3))) != have:
        errs.append(f"the page counts {m.group(1)} packs ({m.group(2)} data, {m.group(3)} code); "
                    f"packs/*/pack.yaml {'at ' + at if at else 'in this tree'} has {have[0]} ({have[1]} data, {have[2]} code)")
    m = grab(r"languages:\s*\[([^\]]*)\]", "RELEASE.languages")
    if m and len(re.findall(r"'[^']+'", m.group(1))) != facts["languages"]:
        errs.append(f"the page names {len(re.findall(chr(39) + '[^' + chr(39) + ']+' + chr(39), m.group(1)))} "
                    f"languages; app/issues LOCALES has {facts['languages']}")
    m = grab(r"docsPages:\s*(\d+)", "RELEASE.docsPages")
    if m and int(m.group(1)) != facts["docs"]:
        errs.append(f"the page says {m.group(1)} documentation pages; tools/build_docs.py NAV has {facts['docs']}")
    m = grab(r"export const LINE\s*=\s*'([^']+)'", "LINE")
    if m and m.group(1) not in LEAD:
        errs.append(f"the programme page's LINE ('{m.group(1)}') is not inside the lead ('{LEAD}'); the two are one sentence")
    m = grab(r"export const PURPOSE\s*=\s*'([^']+)'", "PURPOSE")
    if m and m.group(1) != PURPOSE:
        errs.append("the programme page's PURPOSE is not the canonical sentence in docs/site/introduction.md")
    m = grab(r"export const RHO = \{.*?asOf:\s*'(\d{4}-\d{2}-\d{2})'", "RHO.asOf")
    if m and want:          # at release time only: between releases a stale figure is a chore, not a break
        age = (dt.date.today() - dt.date.fromisoformat(m.group(1))).days
        if age > RHO_MAX_AGE_DAYS:
            errs.append(f"node #1's ρ on the page was read {age} days ago ({m.group(1)}); read /rho again "
                        f"and update RHO, or the page publishes a stale headline")
    # And what is deployed: the page is a Vite bundle built from data.js (`make root`, `make staging` in the site
    # repo), and release.sh deploys whatever is built. v0.77 and v0.78 updated data.js, passed above, and went
    # live saying v0.76 (6 Oct 2026). At release time, read the release out of each built bundle too.
    if want:
        for where, d in (("the landing", site / "assets/p"), ("/staging/", site / "staging/assets")):
            tags = {t for f in sorted(d.glob("*.js")) for t in re.findall(r'\{tag:"(v[^"]+)",asOf:"', f.read_text(encoding="utf-8"))}
            if tags != {want}:
                errs.append(f"{where}'s built bundle ({d.relative_to(site)}) says {', '.join(sorted(tags)) or 'no release'}; "
                            f"this release is {want}. Run `make root` and `make staging` in the site repo and commit")
    m = grab(r"export const RHO = \{.*?label:\s*'([^']+)'", "RHO.label")
    if m and "answered" not in m.group(1):
        errs.append(f"the page labels ρ '{m.group(1)}'; ρ is the share of act-level alerts answered (app/index.py)")

    if errs:
        sys.exit("programme page and node disagree:\n" + "\n".join(f"  x {e}" for e in errs))
    print(f"  programme page matches the node: {want or 'untagged'}, {facts['packs']} packs "
          f"({facts['data']} data, {facts['code']} code), {facts['languages']} languages, "
          f"{facts['docs']} docs pages, one lead, one purpose" + (f", ρ read within {RHO_MAX_AGE_DAYS} days" if want else ""))


if __name__ == "__main__":
    main()
