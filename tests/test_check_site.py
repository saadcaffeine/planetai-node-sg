"""tools/check_site.py passes on a page that matches, and fails on each kind of drift it exists for."""
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOOL = [sys.executable, str(ROOT / "tools/check_site.py")]
PURPOSE = ("Its purpose is fixed: clean air, water and soil for the people and the other living things "
           "around each node.")
GOOD = f"""export const LINE = 'hyperlocal compute and intelligence for distributed production';
export const PURPOSE = '{PURPOSE}';
export const RHO = {{
  asked: 137, answered: 29, rho: 0.212, medianMinutes: 112,
  window: '30 days', asOf: '{{asof}}', prov: 'cached',
  label: 'share of act-level alerts answered',
}};
export const RELEASE = {{
  tag: 'v0.73', count: 87,
  packs: {{ total: {{packs}}, data: {{data}}, code: {{code}} }}, languages: ['English', 'Bahasa Indonesia', 'Spanish'], docsPages: {{docs}},
}};
"""
sys.path.insert(0, str(ROOT / "tools"))
import check_site  # noqa: E402
import datetime as dt  # noqa: E402

f = check_site.node_facts()
today = dt.date.today().isoformat()


def run(js, *extra, built=("v0.73", "v0.73")):
    d = Path(tempfile.mkdtemp())
    (d / "web/src").mkdir(parents=True)
    (d / "web/src/data.js").write_text(js)
    for sub, tag in zip(("assets/p", "staging/assets"), built):
        (d / sub).mkdir(parents=True)
        if tag:
            (d / sub / "hooks-x.js").write_text(f'Ed={{tag:"{tag}",asOf:"{today}",count:87}}')
    r = subprocess.run(TOOL + ["--site", str(d), *extra], capture_output=True, text=True, cwd=ROOT)
    shutil.rmtree(d)
    return r.returncode, r.stdout + r.stderr


good = GOOD.replace("{asof}", today).replace("{packs}", str(f["packs"])).replace(
    "{data}", str(f["data"])).replace("{code}", str(f["code"])).replace("{docs}", str(f["docs"]))
rc, out = run(good, "--version", "v0.73")
assert rc == 0, out
print("a page that matches passes")
for what, js, extra, needle in [
    ("another release", good, ["--version", "v0.74"], "says v0.73"),
    ("a pack count", good.replace(f"total: {f['packs']}", f"total: {f['packs'] + 1}"), [], "packs"),
    ("a language", good.replace(", 'Spanish'", ""), [], "languages"),
    ("the docs count", good.replace(f"docsPages: {f['docs']}", "docsPages: 40"), [], "documentation pages"),
    ("the purpose", good.replace("clean air, water and soil", "clean air"), [], "PURPOSE"),
    ("the line", good.replace("for distributed production';", "for regenerative local production';"), [], "not inside the lead"),
    ("a stale rho at release", good.replace(today, "2026-01-01"), ["--version", "v0.73"], "days ago"),
    ("rho's name", good.replace("alerts answered", "alerts acted on"), [], "answered"),
]:
    rc, out = run(js, *extra)
    assert rc != 0 and needle in out, f"{what}: expected a failure naming '{needle}', got rc={rc}\n{out}"
    print(f"fails on {what}")
for what, built, needle in [("a landing built before data.js changed", ("v0.72", "v0.73"), "the landing's built bundle"),
                            ("a staging copy built before it", ("v0.73", "v0.72"), "/staging/'s built bundle"),
                            ("no built bundle", (None, "v0.73"), "says no release")]:
    rc, out = run(good, "--version", "v0.73", built=built)
    assert rc != 0 and needle in out and "make root" in out, f"{what}: expected '{needle}', got rc={rc}\n{out}"
    print(f"fails at release on {what}")
rc, out = run(good, built=("v0.72", "v0.72"))
assert "built bundle" not in out, f"between releases a stale build is not lint's business\n{out}"
print("between releases the build is not compared")
rc, out = run("export const X = 1;")
assert rc != 0 and "could not find" in out, out
print("a page whose shape changed is reported, not guessed")
