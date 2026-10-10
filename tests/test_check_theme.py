"""The guard on the guard: tools/check_theme.py must fail on an edited frozen file WITH NO DESIGN
REPO, because that is CI — the one place every pull request is checked.

It did not, from the day it was written until 19 September 2026: absent sibling, one line, exit 0.
Nothing asserted otherwise, which is why nobody noticed. This asserts it. (The checker itself never
reaches a node — bundle.sh excludes tools/check_* — but the tarball carries the files it guards, so
an edit that passes CI is on every screen in the house after the next update.)

Runs against a copy of the real tree, so it tests the file in tools/ rather than a paraphrase.
"""
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
NOWHERE = "/nowhere-there-is-no-design-repo-here"
FROZEN = ["app/static/planetai-theme.css", "app/static/signs.svg", "app/static/kilometre-cells.json"]


def run(cwd, *args, design=NOWHERE):
    return subprocess.run([sys.executable, "tools/check_theme.py", *args], cwd=cwd,
                          capture_output=True, text=True, env={"PATH": "/usr/bin:/bin",
                                                               "PLANETAI_DESIGN_REPO": design})


tmp = tempfile.mkdtemp()
try:
    fx = pathlib.Path(tmp) / "node"
    (fx / "tools").mkdir(parents=True)
    (fx / "data").mkdir()
    (fx / "app" / "static").mkdir(parents=True)
    shutil.copy(ROOT / "tools" / "check_theme.py", fx / "tools" / "check_theme.py")
    shutil.copy(ROOT / "data" / "frozen_layer.txt", fx / "data" / "frozen_layer.txt")
    for rel in FROZEN:
        shutil.copy(ROOT / rel, fx / rel)

    # clean tree, no design repo: passes, and says the comparison did not run
    r = run(fx)
    assert r.returncode == 0, f"a clean tree should pass:\n{r.stdout}{r.stderr}"
    assert "match their pinned hashes" in r.stdout, r.stdout
    assert "comparison did not run" in r.stdout, "it should say the byte comparison was skipped"
    print("  clean tree, no design repo: passes and says what it did not do")

    # THE BUG: one byte changed in a frozen file, still no design repo
    css = fx / "app/static/planetai-theme.css"
    css.write_text(css.read_text().replace("--rings:", "--rings-EDITED:", 1))
    r = run(fx)
    assert r.returncode == 1, f"an edited frozen file must FAIL with no design repo:\n{r.stdout}"
    assert "planetai-theme.css has been edited here" in r.stdout, r.stdout
    print("  edited frozen file, no design repo: fails (this is the regression)")

    # and --update cannot be used to bless it, because the design repo is not there to agree
    r = run(fx, "--update")
    assert r.returncode == 1, f"--update must refuse without the design repo:\n{r.stdout}"
    assert "--update needs" in r.stdout or "has been edited here" in r.stdout, r.stdout
    assert (fx / "data/frozen_layer.txt").read_text() == (ROOT / "data/frozen_layer.txt").read_text(), \
        "--update rewrote the pin when it should have refused"
    print("  --update refuses to bless it, and left the pin alone")

    # --update has to move the pin FORWARD. It checked the copy against the commit currently
    # pinned, which a copy taken from a newer design main differs from by definition — so the
    # first real re-pin (PR #83) could not be made at all: "Copy it again", and copying it again
    # gave the same file and the same refusal. Driven here against a throwaway design repo with
    # two commits, because that is the smallest thing that has a "before" and an "after".
    design = pathlib.Path(tmp) / "design"
    design.mkdir()
    # identity from the environment, not `git config`: a GIT_DIR leaked from a hook beats -C, and a
    # config write under it lands in the real checkout (test_ship_gate.sh did that, 267 commits as t@t)
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update(GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t", GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@t")
    def git(*a):
        return subprocess.run(["git", "-C", str(design), *a], capture_output=True, text=True, env=env)
    git("init", "-q", "-b", "main")
    theme = design / "planetai-theme.css"
    (design / "assets" / "signs").mkdir(parents=True)
    (design / "assets" / "h3").mkdir(parents=True)
    shutil.copy(ROOT / "app/static/signs.svg", design / "assets/signs/signs.svg")
    shutil.copy(ROOT / "app/static/kilometre-cells.json", design / "assets/h3/kilometre-cells.json")
    shutil.copy(ROOT / "app/static/planetai-theme.css", theme)
    git("add", "-A"); git("commit", "-qm", "the layer as it was")
    old_sha = git("rev-parse", "HEAD").stdout.strip()
    theme.write_text(theme.read_text().replace("/* ", "/* moved: ", 1))   # the layer moves
    git("add", "-A"); git("commit", "-qm", "the layer moves")
    new_sha = git("rev-parse", "HEAD").stdout.strip()
    git("branch", "-f", "origin/main", "HEAD")          # what origin/main resolves to, without a remote

    for rel in FROZEN:                                   # start from the OLD pin, cleanly
        shutil.copy(ROOT / rel, fx / rel)
    shutil.copy(ROOT / "data" / "frozen_layer.txt", fx / "data" / "frozen_layer.txt")
    pin = fx / "data/frozen_layer.txt"
    pin.write_text(pin.read_text().replace(
        [l for l in pin.read_text().splitlines() if l.startswith("design_sha=")][0],
        f"design_sha={old_sha}"))
    r = run(fx, design=str(design))
    assert r.returncode == 0, f"a clean tree at the old pin should pass:\n{r.stdout}"

    # now copy the moved file over, as a re-pin does, and update
    (fx / "app/static/planetai-theme.css").write_text(theme.read_text())
    r = run(fx, design=str(design))
    assert r.returncode == 1, "a copy that does not match the pin must fail before --update"
    r = run(fx, "--update", design=str(design))
    assert r.returncode == 0, f"--update must be able to move the pin forward:\n{r.stdout}"
    assert new_sha[:7] in r.stdout, f"--update pinned to the wrong commit:\n{r.stdout}"
    r = run(fx, design=str(design))
    assert r.returncode == 0, f"and the tree is green at the new pin:\n{r.stdout}"
    print("  --update moves the pin forward when the layer has moved")

    # a missing pin is a failure, not a skip: it is the half that runs everywhere
    shutil.copy(ROOT / "app/static/planetai-theme.css", css)
    (fx / "data/frozen_layer.txt").unlink()
    r = run(fx)
    assert r.returncode == 1 and "is missing" in r.stdout, f"a missing pin must fail:\n{r.stdout}"
    print("  a missing pin fails rather than skipping")
finally:
    shutil.rmtree(tmp, ignore_errors=True)

# the pin describes the files that are actually here
import hashlib  # noqa: E402
pin = dict(l.split("=", 1) for l in (ROOT / "data/frozen_layer.txt").read_text().splitlines()
           if "=" in l and not l.startswith("#"))
hashes = {l.split()[1]: l.split()[2] for l in (ROOT / "data/frozen_layer.txt").read_text().splitlines()
          if l.startswith("sha256 ")}
assert len(pin["design_sha"]) == 40, "the pin is not a full commit sha"
assert set(hashes) == set(FROZEN), f"the pin covers {set(hashes)}, the frozen layer is {set(FROZEN)}"
for rel, want in hashes.items():
    got = hashlib.sha256((ROOT / rel).read_bytes()).hexdigest()
    assert got == want, f"{rel}: on disk {got[:12]}, pinned {want[:12]}"
print(f"  the pin covers all {len(hashes)} frozen files at planetai-design@{pin['design_sha'][:7]}")

print("check_theme ok")
