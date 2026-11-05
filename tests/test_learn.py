"""The learn layer quotes the documentation, so this proves it still is a quote.

Every panel in learn mode puts words in front of a household and says they are the node's own
documentation. The only thing standing between that claim and a paraphrase is tools/build_learn.py,
and the only thing standing between the claim and rot is its --check. So:

  · every quote in app/static/learn.json is a verbatim substring of the docs/site page it cites,
    right now, against the real tree (the invariant itself, asserted directly and not through the
    tool that maintains it), and it carries that page's own `# Title`, which is what the panel cites;
  · every section dashboard.js registers carries at least one mark, and every key a section names
    is one tools/build_learn.py has, so no part of the page is left unexplained and no question
    mark opens nothing;
  · editing a quote out of its page fails the build, naming the mark;
  · a quote that grows past sixty words fails the build rather than being drawn and cut off;
  · --check fails when the committed file is not what the docs say, and passes again after a
    rebuild. Both directions, because a gate that only ever passes is not a gate.

Run: python3 tests/test_learn.py
"""
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LEARN = ROOT / "app" / "static" / "learn.json"
sys.path.insert(0, str(ROOT / "tools"))
import build_learn  # noqa: E402  the MARKS table itself, not the file it writes


def edit(page, old, new):
    """Change one span of a docs page, and prove the change landed. A mutation that matched nothing
    leaves the tree clean, the gate passes, and the test says the gate works. It is the failure this
    whole file exists to catch, so it may not be the failure this file has."""
    before = page.read_text(encoding="utf-8")
    assert before.count(old) == 1, f"{page.name}: the anchor is not there once: {old[:60]!r}"
    page.write_text(before.replace(old, new), encoding="utf-8")
    return before


def run(cwd, *args):
    r = subprocess.run([sys.executable, "tools/build_learn.py", *args],
                       cwd=cwd, capture_output=True, text=True)
    return r.returncode, r.stdout + r.stderr


def tree():
    """A throwaway copy of the four things build_learn.py touches."""
    tmp = Path(tempfile.mkdtemp(prefix="planetai-learn-"))
    (tmp / "tools").mkdir()
    (tmp / "app" / "static").mkdir(parents=True)
    (tmp / "data").mkdir()
    shutil.copy(ROOT / "tools" / "build_learn.py", tmp / "tools" / "build_learn.py")
    shutil.copytree(ROOT / "docs" / "site", tmp / "docs" / "site")
    shutil.copy(LEARN, tmp / "app" / "static" / "learn.json")
    shutil.copy(ROOT / "data" / "docs_site.json", tmp / "data" / "docs_site.json")
    return tmp


# --- the invariant, against the tree that ships ---------------------------------------------------
built = json.loads(LEARN.read_text(encoding="utf-8"))
assert built["order"], "learn.json has no marks"
assert set(built["order"]) == set(built["marks"]), "the walk order and the marks disagree"
for key in built["order"]:
    m = built["marks"][key]
    page = (ROOT / "docs" / "site" / m["page"]).read_text(encoding="utf-8")
    assert m["quote"] in page, (
        f"the {key} panel quotes docs/site/{m['page']} and those words are not in that page. "
        f"A panel that says 'the words above are from' and then paraphrases is the one thing this "
        f"layer may not do.")
    n = len(m["quote"].split())
    assert n <= 60, f"{key}: {n} words, over the sixty the panel holds"
    assert m["more"], f"{key}: no line of the page's own"
    assert m["url"].startswith("https://planetai.fab.city/docs/"), f"{key}: {m['url']}"
    assert m["url"].startswith(f"https://planetai.fab.city/docs/{m['page'][:-3]}/"), (
        f"{key}: the URL scheme is /docs/<stem>/#<anchor>, and this one is {m['url']}")
    title = re.match(r"# (.+)", page)
    assert title and m.get("page_title") == title.group(1).strip(), (
        f"{key}: the panel cites the page by its title, and learn.json says "
        f"{m.get('page_title')!r} where docs/site/{m['page']} says {title and title.group(1)!r}")
print(f"  · all {len(built['order'])} quotes are verbatim spans of the page they name, under 60 words, "
      f"cited by the page's own title")

# --- every section explains itself, and every key it names exists --------------------------------
# A registration is `window.PAI.register({` up to its first method: the fields a section declares
# about itself sit at the top of the object, and a `learn:` further down, after the render code, is
# one nobody reading the registration would see.
JS = (ROOT / "app" / "static" / "dashboard.js").read_text(encoding="utf-8")
KEYS = {m[0] for m in build_learn.MARKS}
assert len(KEYS) == len(build_learn.MARKS), "two MARKS entries share a key"
heads = re.findall(r"^window\.PAI\.register\(\{(.*?)\n  (?:render|lead|controls|wall|notes)\b", JS,
                   re.S | re.M)
assert heads and len(heads) == len(re.findall(r"^window\.PAI\.register\(\{", JS, re.M)), (
    "a registration with no render, lead, controls, wall or notes: the test cannot find where its "
    "declared fields end")
ids = []
for head in heads:
    sid = re.search(r"\bid:\s*'([^']+)'", head)
    assert sid, f"a registration with no id: {head[:80]!r}"
    ids.append(sid.group(1))
    arr = re.search(r"\blearn:\s*\[([^\]]*)\]", head)
    assert arr, f"section '{sid.group(1)}' declares no `learn:` array, so in learn mode it is the one part of the page with no question mark"
    keys = re.findall(r"'([a-z]+)'", arr.group(1))
    assert keys, f"section '{sid.group(1)}' has an empty `learn:` array"
    for k in keys:
        assert k in KEYS, f"section '{sid.group(1)}' names the mark '{k}', which is not in MARKS in tools/build_learn.py"
assert len(ids) == len(set(ids)), f"a section id is registered twice: {ids}"
print(f"  · all {len(ids)} registered sections carry a mark, and every key they name is in MARKS")

# The walk follows the page: Back and Next and "Walk the page" read the marks this view drew, in
# document order, and fall back to learn.json's order only for a key this view does not carry.
assert "function learnWalk()" in JS and "'#page .q[data-learn], #foot .q[data-learn]'" in JS, \
    "the walk no longer reads the marks in the order the view drew them"
assert "data-learn-walk" in JS and "learnWalk()[0] || LEARN.order[0]" in JS, \
    "Walk the page no longer starts at the first mark on this view"
# Every view that has a foot carries the purpose: the foot draws it, and the foot is on every view
# but the wall.
foot = JS[JS.index("function foot(S)"):]
foot = foot[:foot.index("\n}\n")]
for k in ("production", "purpose"):
    assert f"mark('{k}'" in foot, f"the foot no longer carries the '{k}' mark"
print("  · the walk follows the page, and the foot carries the node's purpose on every view")

# --- the doors: every part names a mark written for the doors -------------------------------------
# The doors (`/`) mark their parts in the markup and learnList() in doors-core.js lists them. A classic mark
# describes the classic page (the ladder, Network's resolution line), so on the doors it said the wrong thing;
# a doors part names a door-prefixed mark, cut from the section of dashboard.md or wall.md about that part,
# or one of the few classic marks whose quote describes the doors part as well.
REUSED = {"figure", "earth", "settings"}
DOORS_SRC = {p.name: p.read_text(encoding="utf-8") for p in sorted((ROOT / "app" / "static").glob("doors*.*"))}
dkeys = {}
for name, src in DOORS_SRC.items():
    for k in re.findall(r'data-learn="([a-z-]+)"', src):
        dkeys.setdefault(k, name)
    for expr in re.findall(r"dataset\.learn\s*=\s*([^;]+);", src):
        for k in re.findall(r"(?:^|[?:])\s*'([a-z-]+)'", expr.strip()):
            dkeys.setdefault(k, name)
PREFIX = ("now-", "place-", "node-", "data-", "wall-", "setup-")
for k, name in sorted(dkeys.items()):
    assert k in KEYS, f"{name} marks a part '{k}', which is not in MARKS in tools/build_learn.py"
    assert k.startswith(PREFIX) or k in REUSED | {"bar", "foot"}, (
        f"{name} marks a part with the classic mark '{k}'. Give it a door mark cut from the docs section that "
        f"describes that part, or add it to REUSED here only if its quote describes the doors part too.")
for door in ("now", "place", "node", "data", "wall", "setup"):
    assert any(k.startswith(door + "-") for k in dkeys), f"the {door} door marks none of its parts"
for k in ("place-orbit", "place-image", "wall-narration", "setup-save", "bar", "foot"):
    assert k in dkeys, f"no doors part names '{k}'"
# the list says what the docs say: the quote is the main text, then the page's line, the reads and the docs link
core = DOORS_SRC["doors-core.js"]
ll = core[core.index("function learnList()"):]
ll = ll[:ll.index("\n}\n")]
for need in ("m.quote", "m.more", "m.url", "m.section", "dataset.reads", "dataset.stage", "getClientRects"):
    assert need in ll, f"learnList() no longer draws {need}"
assert ll.index("m.quote") < ll.index("m.more"), "the docs quote is the main text, before the page's own line"
print(f"  · all {len(dkeys)} marks the doors name are in MARKS, and each was written for the doors part it marks")

# --- the gate fails when the documentation moves --------------------------------------------------
tmp = tree()
try:
    rc, out = run(tmp, "--check")
    assert rc == 0, f"a clean tree should pass --check:\n{out}"
    print("  · a clean tree passes --check")

    # 1. the quote is edited out of its page entirely
    page = tmp / "docs" / "site" / "rho.md"
    before = edit(page, "ρ (rho) is the share of the node's act-level asks",
                  "ρ is roughly how often somebody did something")
    rc, out = run(tmp)
    assert rc != 0, f"the build accepted a quote that is no longer in its page:\n{out}"
    assert "rho:" in out, f"it failed, but did not name the mark:\n{out}"
    print("  · a quote edited out of its page fails the build, and the build names the mark")
    page.write_text(before, encoding="utf-8")

    # 2. the paragraph grows past what the panel holds
    page = tmp / "docs" / "site" / "alerts.md"
    before = edit(page, "`ALERT_LEVEL` (default `act`) is the floor for interrupting a person,",
                  "`ALERT_LEVEL` (default `act`) is the floor for interrupting a person, "
                  + "and so on " * 30)
    rc, out = run(tmp)
    assert rc != 0, f"the build accepted a quote past the word ceiling:\n{out}"
    assert "levels:" in out and "over the 60" in out, f"wrong failure:\n{out}"
    print("  · a span that grows past sixty words fails the build rather than being drawn and cut")
    page.write_text(before, encoding="utf-8")

    # 3. the prose moves but the span still resolves: --check fails, a rebuild fixes it, --check passes
    page = tmp / "docs" / "site" / "how-it-works.md"
    edit(page, "No agent dispatches without a human row in `actions`.",
         "No agent ever dispatches without a human row in `actions`.")
    rc, out = run(tmp, "--check")
    assert rc != 0, f"--check passed a learn.json that is not what the docs say:\n{out}"
    assert "not what docs/site says" in out, out
    print("  · --check fails when the committed file and the documentation have drifted apart")
    rc, out = run(tmp)
    assert rc == 0, out
    rc, out = run(tmp, "--check")
    assert rc == 0, f"--check still fails after a rebuild:\n{out}"
    assert "No agent ever dispatches" in json.loads((tmp / "app" / "static" / "learn.json")
                                                    .read_text(encoding="utf-8"))["marks"]["refusals"]["quote"]
    print("  · a rebuild takes the new words, and --check passes again")
finally:
    shutil.rmtree(tmp, ignore_errors=True)

print("learn: the panels quote the documentation, and the build fails when they stop")
