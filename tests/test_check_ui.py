"""Proof that the dashboard's design gates fail when they should.

A gate nobody has watched fail is a gate that passes for the wrong reason — a regex that never matched, a file
read from the wrong path. Every rule in tools/check_ui.py's visual-language section exists because that thing
shipped to real households, so each one gets broken here on purpose against a copy of the real index.html.

Run: python3 tests/test_check_ui.py
"""
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def run(tmp):
    r = subprocess.run([sys.executable, str(ROOT / "tools" / "check_ui.py")],
                       cwd=tmp, capture_output=True, text=True)
    return r.returncode, r.stdout + r.stderr


def tree():
    """A throwaway copy of the files check_ui.py reads. The page is three of them now."""
    tmp = Path(tempfile.mkdtemp(prefix="planetai-ui-"))
    (tmp / "app" / "static").mkdir(parents=True)
    # The two drawings the node serves as documents of their own go too: no stylesheet on the page
    # can reach inside them, so the SMIL rule has to be checked against the files themselves.
    for f in ("index.html", "dashboard.js", "dashboard.css", "learn.json",
              "signs.svg", "node-ground.svg"):
        shutil.copy(ROOT / "app" / "static" / f, tmp / "app" / "static" / f)
    shutil.copy(ROOT / "app" / "main.py", tmp / "app" / "main.py")
    shutil.copy(ROOT / "app" / "ask.py", tmp / "app" / "ask.py")
    (tmp / "app" / "issues").mkdir(parents=True, exist_ok=True)
    shutil.copy(ROOT / "app" / "issues" / "api.py", tmp / "app" / "issues" / "api.py")
    shutil.copy(ROOT / "init.sql", tmp / "init.sql")
    return tmp


def broken(name, mutate, expect, where="dashboard.css"):
    """Apply one violation to the real page and require check_ui.py to name it.

    `where` because the page is three files now. The visual-language rules are about the
    stylesheet, so that is the default; a rule about the markup or the script names its own.
    """
    tmp = tree()
    try:
        p = tmp / "app" / "static" / where
        before = p.read_text()
        after = mutate(before)
        assert after != before, f"{name}: the mutation changed nothing — this test is not testing anything"
        p.write_text(after)
        rc, out = run(tmp)
        assert rc == 1, f"{name}: check_ui.py passed a page that breaks the rule\n{out}"
        assert re.search(expect, out, re.I), f"{name}: it failed, but not about this\nwanted /{expect}/\ngot:\n{out}"
        print(f"  · {name}: caught — {out.strip().splitlines()[0].strip()[:96]}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def sub(old, new):
    def f(s):
        assert s.count(old) >= 1, f"anchor not found in the file under test: {old[:60]!r}"
        return s.replace(old, new, 1)
    return f


def prepend_js(line):
    """A violation at the top of the script. Same reasoning as prepend() below."""
    return lambda s: line + "\n" + s


def prepend(css):
    """Most of these violations are `add a rule that breaks one`. Where in the file does not
    matter, so they go at the top rather than hunting an anchor that may be renamed."""
    return lambda s: css + "\n" + s


# The page as it ships must pass, or every assertion below proves nothing.
tmp = tree()
rc, out = run(tmp)
assert rc == 0, f"the shipped page does not pass its own gates:\n{out}"
shutil.rmtree(tmp, ignore_errors=True)
print("  · the shipped page passes")

# 1. a regular hexagon as decoration — the .bighex that shipped, near enough verbatim
broken("hexagon", prepend(
    ".bighex{position:absolute;right:-8%;width:min(60%,420px);"
    "clip-path:polygon(50% 0,100% 25%,100% 75%,50% 100%,0 75%,0 25%);background:var(--ink)}"),
    r"six-sided clip-path")

# ...but a small glyph is a bullet, not wallpaper, and must still pass
tmp = tree()
q = tmp / "app" / "static" / "dashboard.css"
q.write_text(".hexbullet{width:24px;clip-path:polygon(50% 0,100% 25%,100% 75%,50% 100%,0 75%,0 25%)}\n"
             + q.read_text())
rc, out = run(tmp)
assert rc == 0, f"a 24px hexagon bullet should pass; the gate is too wide:\n{out}"
shutil.rmtree(tmp, ignore_errors=True)
print("  · a 24px hexagon bullet still passes")

# 2. the website palette
broken("web-green", prepend(".x{color:#7AC943}"), r"#7AC943.*web-green")
broken("web-blue", prepend(".x{stroke:#3FA9F5}"), r"#3FA9F5.*web-blue")

# 3. gradients and glows
broken("radial-gradient", prepend(
    ".glow{position:fixed;background:radial-gradient(circle,rgba(32,56,141,.35),transparent 60%)}"),
    r"radial-gradient\(\) is in the stylesheet")

# 4. radius, on a selector that is not on the legacy list
broken("pill control", prepend(".newbtn{border-radius:999px;padding:6px 14px;width:40px}"),
       r"rounds a control to 999px")
broken("round card", prepend(".panel{border-radius:26px}"), r"rounds a card to 26px")

# 5. provenance carrying a verdict — the layer's role tokens, which is what the page uses now
broken("prov colour", prepend(".prov{color:var(--rings)}"), r"prov.*carries a colour")
broken("prov inline colour",
       # #page is no longer empty — it carries the "asking the node…" header until boot() answers —
       # so the mutation goes on its opening tag rather than on a literal empty div.
       sub('<div id="page">', '<div id="page" class="prov" style="color:#00A057">'),
       r"prov in its class or id carries an inline colour", where="index.html")

# 6. orange away from the satellite, in both registers' oranges
broken("orange act button", prepend(".btn.act{background:var(--satellite-only)}"),
       r"paints with orange away from the satellite")
broken("paper orange astray", prepend(".chip{color:#DB7200}"),
       r"paints with orange away from the satellite")

# 7. the dark register's blue. The page declares no register in its markup — render() sets
#    data-theme on <html> for the Wall — so the lifted blue must not be in the stylesheet at all.
broken("lifted blue on paper", prepend(".x{color:#7FA5E8}"),
       r"#7FA5E8.*(outside the dark register|does not declare)")

# 8. an asset the node does not serve, and one that is not under static/ at all
# These used to break a src the RENDERER wrote — the hero's ground, at `static/node-ground.svg`. The
# modular page has no literal asset reference in dashboard.js at all: its one companion is the sign
# sprite, written as `static/signs.svg#sign-${id}`, and a reference carrying a template expression is
# excluded by rule 8's own character class because those are routes and not assets. So both cases
# break the document's own three links instead, which is where every asset this page loads now is.
broken("unserved asset", sub('href="static/tokens.css"', 'href="tokens.css"'),
       r"loads tokens\.css, which is not under static/", where="index.html")
broken("asset off the allowlist", sub('href="static/tokens.css"', 'href="static/tokens2.css"'),
       r"COMPANIONS allowlist does not serve", where="index.html")
broken("stylesheet off the allowlist",
       sub('href="static/dashboard.css"', 'href="static/theme2.css"'),
       r"COMPANIONS allowlist does not serve", where="index.html")

# 8b. the page computes no H3: neither h3-js nor deck.gl's own hexagon layer, which computes the ring in the browser
broken("h3-js on the page", prepend_js("window.x = new deck.H3HexagonLayer({ getHexagon: d => d.id });"),
       r"computes H3 itself \(H3HexagonLayer\)", where="dashboard.js")
broken("an h3 call on the page", prepend_js("const r = h3.cellToBoundary('8888');"),
       r"computes H3 itself \(h3\.cellToBoundary\)", where="dashboard.js")
broken("a vendored library off the allowlist", prepend_js("const L = { src: 'static/leaflet.js' };"),
       r"loads static/leaflet\.js, which app/main\.py's COMPANIONS allowlist does not serve", where="dashboard.js")

# 9. the stylesheets: a font nothing serves, and a CDN
broken("font off the allowlist", prepend('@font-face{font-family:"Z";src:url("Nope.ttf")}'),
       r"loads Nope\.ttf, which app/main\.py's COMPANIONS allowlist does not serve")
broken("a CDN in a stylesheet", prepend("@import url('https://fonts.googleapis.com/css2?family=X');"),
       r"from the network")

# 10. the node's own words, shouted into a different unit
# `text-transform:uppercase` on one character is a translation: `µ` uppercases to `M`, so the hero and the wall
# drew "17 MG/M³" where the node had written "17 µg/m³" — milligrams for micrograms — two lines above a sentence
# that had the unit right. Both prose sites must stay inside .said, and a new uppercasing rule must be looked at
# by a person rather than discovered on a shelf screen.
broken("the kicker's reason unwrapped",
       sub('<span class="said">\u00b7 ${esc(d.reason_text[LOC])}</span>',
           '<span>\u00b7 ${esc(d.reason_text[LOC])}</span>'),
       r"kicker's reason.*no longer wrapped in \.said", where="dashboard.js")
broken("a readout's title unwrapped",
       sub('<div class="lab"><span class="said">${esc(o.title)}</span>',
           '<div class="lab">${esc(o.title)}'),
       r"readout's title.*no longer wrapped in \.said", where="dashboard.js")
broken("a new uppercasing rule nobody looked at",
       prepend(".newshout{text-transform:uppercase}"),
       r"is a new text-transform:uppercase rule")

# 11. a box that fills the screen, inside another one
# `.wall` sets min-height:100vh and a padding, and index.html carried it on the section and on the mount inside
# it. Both applied, so the wall was one viewport plus two paddings — 1208px on a 1080px screen. A wall does not
# scroll, so the footer carrying `As of HH:MM` and the word `stale` was off the bottom of it at 1440.
broken("a viewport-height class on an element and its own ancestor",
       sub('<div class="wrap"><p class="note">Asking',
           '<div class="wallbox"><div class="wallbox"></div></div><div class="wrap"><p class="note">Asking'),
       r"\.wallbox sets a viewport height and is on <div>.*inside <div>", where="index.html")

# 12. a learn mark with nothing behind it, and an entry nothing draws
# Both are silent: the page renders either way and the only way to find out is to be the tester who
# presses a question mark and gets nothing. So they are counted at build time instead.
broken("a mark the layer does not have",
       sub("learn: ['cards', 'raw', 'figure']", "learn: ['cards', 'raw', 'figure', 'weather']"),
       r"draws a learn mark 'weather' that app/static/learn\.json does not have", where="dashboard.js")
broken("an entry nothing on the page draws",
       sub("learn: ['rho', 'refusals']", "learn: ['rho']"),
       r"learn\.json carries 'refusals' and nothing on the page draws it", where="dashboard.js")

# 13. SVG SMIL, which reduced motion cannot reach
# The netmap shipped an <animate> and it was rewritten in CSS for exactly this reason. Nothing
# stopped the next drawing reaching for it again; this does. Prose about SMIL is not a violation —
# the page's own note explains why the wires are not drawn that way — so the rule wants an attribute.
broken("an SVG <animate> in the script",
       prepend_js('const SMIL = \'<animate attributeName="opacity" dur="2s"/>\';'),
       r"dashboard\.js writes an SVG <animate>.*reduced motion cannot reach smil", where="dashboard.js")
broken("an <animateTransform> inside a drawing the node serves",
       sub("</svg>", '<animateTransform attributeName="transform" dur="3s"/></svg>'),
       r"node-ground\.svg carries an SVG <animateTransform>", where="node-ground.svg")
# and the other half: the page already TALKS about SMIL, in a note a reader sees and in this repo's
# own comments. A rule that cannot tell the two apart would have been red the day it was written.
tmp = tree()
p = tmp / "app" / "static" / "dashboard.js"
p.write_text("/* the netmap once used <animate> and does not any more */\n" + p.read_text())
rc, out = run(tmp)
assert rc == 0, f"prose mentioning <animate> was read as a violation:\n{out}"
shutil.rmtree(tmp, ignore_errors=True)
print("  · prose mentioning <animate> is left alone: the rule wants an attribute")

# The routes a band prints beside its kicker. A section with no `reads:` is a band nobody can trace
# back to the node; a route app/main.py does not define is a citation that answers 404.
broken("a section with no reads",
       sub("  reads: ['/effect'],\n", ""),
       r"section 'effect' declares no `reads:`", where="dashboard.js")
broken("a section that reads a route the node does not have",
       sub("  reads: ['/effect'],", "  reads: ['/effects'],"),
       r"section 'effect' reads /effects, which app/main\.py does not define", where="dashboard.js")

print("check_ui: every visual-language gate fails when the page breaks its rule")
