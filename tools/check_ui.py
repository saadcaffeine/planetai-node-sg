"""The GUI is one HTML file with no build step, so nothing catches a typo until someone opens it. This does:
  · the script parses (node, if present)
  · every element id the script references exists in the markup
  · every API path the page calls exists in app/main.py
  · every field it reads off /stats rows is a column of the stats view
  · anything the script hides with .hidden is not un-hidden by a display rule
Run: python3 tools/check_ui.py"""
import json
import pathlib
import re
import shutil
import subprocess
import sys

h = open("app/static/index.html").read()
# The page is three files: a skeleton, a renderer and a stylesheet. It used to be one, and every
# rule below was written against that one — so this is where they are told where to look now.
js = open("app/static/dashboard.js").read() if "src=\"static/dashboard.js\"" in h \
    else h[h.rindex("<script>") + 8: h.rindex("</script>")]
errs = []

if shutil.which("node"):
    r = subprocess.run(["node", "-e", "new Function(require('fs').readFileSync(0,'utf8'))"], input=js, capture_output=True, text=True)
    if r.returncode:
        errs.append("script does not parse: " + r.stderr.strip().splitlines()[-1][:120])

used = set(re.findall(r"\$\('#([a-zA-Z0-9_-]+)'\)", js)) | set(re.findall(r"getElementById\('([^']+)'\)", js))
have = set(re.findall(r'\bid="([a-zA-Z0-9_-]+)"', h))
for i in sorted(used - have):
    errs.append(f"script references #{i}, which is not in the markup")

main = open("app/main.py").read()
routes = set(re.findall(r'@app\.(?:get|post|put)\("(/[a-z_./{}-]*)"', main))   # paths may nest: /place/geojson
# app/issues/api.py is an APIRouter mounted with include_router, and this FastAPI version defers
# that — app.routes holds an _IncludedRouter with no .path, so nothing here can see /issues by
# importing. Read its decorators and put the router's own prefix back on the front.
_api = open("app/issues/api.py").read()
_prefix = (re.search(r'APIRouter\(prefix="([^"]+)"', _api) or [None, ""])[1]
routes |= {(_prefix + p) or "/" for p in re.findall(r'@router\.(?:get|post|put)\("([^"]*)"', _api)}
# app/ask.py is a router with no prefix: GET /ask/status, POST /ask, GET /docs/search.
routes |= set(re.findall(r'@router\.(?:get|post|put)\("(/[^"]*)"', open("app/ask.py").read()))
# `fetch('/x')`, and `get('/x')` — snapshot()'s own helper, which is how most of them are called
_called = set(re.findall(r"(?:api|fetch|get)\('(/[a-z_/.-]+)", js))
_called |= set(re.findall(r"[\"'`](/(?:earth|issues|actions|settings|packs|health|alerts|rho|report|ask|docs)[a-z_/.-]*)", js))
for p in sorted({x.rstrip("/") or "/" for x in _called}):
    if p not in routes:
        errs.append(f"page calls {p}, which app/main.py does not define")

# Every section names the routes its band's data comes from (`reads:`), and the shell prints them
# beside the kicker as links. A section with none is a band a reader cannot trace to the node, and a
# route that is not in app/main.py is a link to a 404 printed as a citation.
_heads = re.findall(r"^window\.PAI\.register\(\{(.*?)\n  (?:render|lead|controls|wall|notes)\b", js,
                    re.S | re.M)
if len(_heads) != len(re.findall(r"^window\.PAI\.register\(\{", js, re.M)):
    errs.append("a section registration has no render, lead, controls, wall or notes, so its declared "
                "fields cannot be read for `reads:`")
for _head in _heads:
    _sid = (re.search(r"\bid:\s*'([^']+)'", _head) or [None, "?"])[1]
    _arr = re.search(r"\breads:\s*\[([^\]]*)\]", _head)
    _got = re.findall(r"'([^']+)'", _arr.group(1)) if _arr else []
    if not _got:
        errs.append(f"section '{_sid}' declares no `reads:`, so its band does not say which route it drew")
    for _r in _got:
        if _r.split("?")[0] not in routes:
            errs.append(f"section '{_sid}' reads {_r}, which app/main.py does not define")

# `hidden` is an attribute the UA styles as display:none, and ANY display rule of our own beats it. This has
# shipped twice: an empty orange act strip on every node with nothing to act on (.actstrip sets display:grid),
# and a broken-image box with its alt text on every node that had not fetched satellite data yet (#earth-img
# sets display:block). Both times the script had set .hidden correctly and the CSS quietly ignored it.
CSS = h[: h.index("</style>")] if "</style>" in h else open("app/static/dashboard.css").read()
ids = dict(re.findall(r"const\s+(\w+)\s*=\s*\$\('#([a-zA-Z0-9_-]+)'\)", js))
ids.update(dict(re.findall(r"(\w+)\s*=\s*\$\('#([a-zA-Z0-9_-]+)'\)", js)))
hidden_ids = {ids[v] for v in re.findall(r"(\w+)\.hidden\s*=", js) if v in ids}
hidden_ids |= set(re.findall(r"\$\('#([a-zA-Z0-9_-]+)'\)\.hidden\s*=", js))
# …and the way the renderer actually writes it. The rule was blind to `getElementById('x').hidden =`,
# which is every hide in dashboard.js, so it passed a stylesheet that gave #arrbar `display:flex` and
# un-hid the Arrange bar on every view — the exact failure this check exists for, shipped past it.
hidden_ids |= set(re.findall(r"getElementById\('([a-zA-Z0-9_-]+)'\)\.hidden\s*=", js))
for i in sorted(hidden_ids):
    tag = re.search(rf'<(\w+)([^>]*\bid="{re.escape(i)}"[^>]*)>', h)
    if not tag:
        continue
    classes = re.findall(r"[\w-]+", (re.search(r'class="([^"]*)"', tag.group(2)) or re.match("", "")).group(1)) \
        if re.search(r'class="([^"]*)"', tag.group(2)) else []
    # selectors that could give this element a display, and the guards that would cancel it
    setters = [sel for sel in [f"#{i}"] + [f".{c}" for c in classes]
               if re.search(rf"(^|[,}}\s]){re.escape(sel)}\s*(,[^{{]*)?\{{[^}}]*display\s*:", CSS, re.M)]
    guarded = re.search(rf"(^|[,}}\s])#{re.escape(i)}\[hidden\]", CSS, re.M) or any(
        re.search(rf"(^|[,}}\s])\.{re.escape(c)}\[hidden\]", CSS, re.M) for c in classes)
    if setters and not guarded:
        errs.append(f"script hides #{i}, but {' and '.join(setters)} sets display: and nothing "
                    f"cancels it — add #{i}[hidden]{{display:none}}")

sql = open("init.sql").read()
# strip line comments first: `-- rolling stats are for sensors only;` sits inside the view and ends in a
# semicolon, which cut the view off at its SELECT list and would silently reject any column added below it.
sql = "\n".join(re.sub(r"--.*$", "", line) for line in sql.splitlines())
stats = sql[sql.index("CREATE VIEW stats"):]
stats = stats[: stats.index(";")]
cols = set(re.findall(r"\bAS (\w+)", stats)) | {"sensor_id", "metric", "name", "local", "indoor", "kind", "scale", "lat", "lon"}
# `r` is a stats row inside .filter(r=>...) / .map(r=>...) callbacks; elsewhere it is a fetch Response
row_ctx = " ".join(re.findall(r"(?:filter|map|forEach|reduce)\(r=>[^;]{0,200}", js))
for f in sorted(set(re.findall(r"\br\.([a-z_0-9]+)", row_ctx))):
    if f not in cols and f not in ("key", "value", "label", "help", "secret", "set", "source", "group", "id", "cell", "state", "unit", "ts", "level", "text", "rule_id", "acted_at", "pack", "description", "name",
                                    "coverage_7d", "frozen_channels", "age_hours",   # /trust
                                    "km", "network", "pm25", "reporting", "silent_minutes", "last_ts"):  # /nearby  (indoor is a stats column)
        errs.append(f"page reads r.{f}, which is not a column of the stats view")


# ---------------------------------------------------------------------------------------------------------------
# The visual language. Six of these shipped to real households and were found by looking, not by a check
# (planetai-design/decisions/design-log.md, 7 Sep 2026). Each rule below is one of them, so each one now costs a
# lint failure instead of a design round. Break one on purpose before you trust it.
#
#   colour is a role, never decoration:  green = a response, a loop closed, an act taken · red = a signal that got
#   worse or crossed a line · blue = data, identity, a selected cell · orange = what only the satellite knows.
#   Anything else on this page is ink.

def strip_comments(text):
    """Colours and radii inside /* */ and // comments are documentation, not paint."""
    text = re.sub(r"/\*.*?\*/", " ", text, flags=re.S)
    return re.sub(r"(?m)^\s*//.*$", " ", text)

CSS_SRC = strip_comments(CSS)
JS_SRC = strip_comments(js)
# the markup. It used to be "whatever follows the inline <style>"; the skeleton has no inline
# style at all, and an empty BODY silently switched off every rule that reads the markup.
BODY = strip_comments(h[h.index("</style>"):] if "</style>" in h else h)
RULES = [(m.group(1).strip(), m.group(2)) for m in re.finditer(r"([^{}]+)\{([^{}]*)\}", CSS_SRC)]

def rule_width(body):
    m = re.search(r"(?<!max-)(?<!min-)\bwidth\s*:\s*(\d+(?:\.\d+)?)px", body)
    return float(m.group(1)) if m else None

# --- 1. regular hexagons as decoration --------------------------------------------------------------------------
# The one shape this language does not permit. A hexagon glyph small enough to be a bullet still carries meaning
# (an alert's level, a sensor's state) and is kept; the design kit's own hexagon check skips small cells for the
# same reason. Above this it is wallpaper — .bighex, .bighex2 and .wall .halo all were.
HEX_GLYPH_MAX_PX = 24
for sel, body in RULES:
    for pts in re.findall(r"clip-path\s*:\s*polygon\(([^)]*)\)", body):
        if len(pts.split(",")) != 6:
            continue
        widths = [rule_width(b) for s2, b in RULES if s2 == sel or s2.endswith(" " + sel.lstrip(".").join(["."] * 0) + sel) or re.search(rf"(^|[\s,]){re.escape(sel)}(\s|,|$)", s2)]
        widths = [w for w in widths if w is not None]
        relative = any(re.search(r"(?<!max-)(?<!min-)\bwidth\s*:[^;}]*(%|vw|vmin|vh|min\(|max\(|clamp\()", b)
                       for s2, b in RULES if re.search(rf"(^|[\s,]){re.escape(sel)}(\s|,|$)", s2))
        biggest = max(widths) if widths else None
        if relative or (biggest is not None and biggest > HEX_GLYPH_MAX_PX):
            errs.append(f"{sel} is a six-sided clip-path wider than {HEX_GLYPH_MAX_PX}px — a regular hexagon as "
                        f"decoration. The ground is static/node-ground.svg, which is computed geometry.")
        elif biggest is None:
            errs.append(f"{sel} is a six-sided clip-path and no rule gives it a width, so nothing here can tell a "
                        f"bullet from wallpaper — give it a width under {HEX_GLYPH_MAX_PX}px or delete it")

# --- 2. the website palette --------------------------------------------------------------------------------------
# fab.city's palette, not the master brand's. --hue:#7AC943 as a general accent was violation 3.
WEBSITE_PALETTE = {
    "#7AC943": "web-green",
    "#3FA9F5": "web-blue",
    "#E8873A": "the old web-orange (the satellite layer uses #FF931E)",
}
PALETTE_EXCEPTIONS = {}       # {"#XXXXXX": "why, and who decided"} — empty on purpose. Add a reason, not a colour.
for hexv, name in WEBSITE_PALETTE.items():
    if hexv in PALETTE_EXCEPTIONS:
        continue
    for src, where in ((CSS_SRC, "the stylesheet"), (JS_SRC, "the script"), (BODY, "the markup")):
        if re.search(hexv, src, re.I):
            errs.append(f"{hexv} ({name}) is in {where}. This page uses roles, not the website palette: "
                        f"green a response, red a line crossed, blue data, orange satellite-only, else ink.")

# --- 3. gradients and glows ---------------------------------------------------------------------------------------
# The rule was written against .glow.a and .glow.b — two drifting radial-gradients behind the whole page, decoration
# pretending to be atmosphere. It is not written against a DOT SCREEN, which is the only way CSS draws one and which
# is how the grain rail says "this cell may leave the machine" without spending the cells blue on a second meaning.
# A texture that encodes a datum is an instrument; a gradient behind everything is a mood.
#
# Recorded verbatim and exactly, the way PROSE_IN_A_SHOUT and RADIUS_LEGACY are: this is the one expression allowed,
# not the one function. Anything else with a gradient in it still fails. Added 21 September 2026 with the rail.
TEXTURE_KNOWN = (
    "radial-gradient(circle, var(--ink) .8px, transparent 1px)",     # the rail's may-leave zone, and its key swatch
)
for fn in ("linear-gradient", "radial-gradient", "conic-gradient"):
    for src, where in ((CSS_SRC, "the stylesheet"), (JS_SRC, "the script"), (BODY, "the markup")):
        probe = src
        for _tex in TEXTURE_KNOWN:
            probe = probe.replace(_tex, "")
        if fn + "(" in probe:
            errs.append(f"{fn}() is in {where}. No gradients and no glows: .glow.a and .glow.b were two "
                        f"drifting radial-gradients behind the whole page. A dot screen that encodes a "
                        f"datum goes in TEXTURE_KNOWN, verbatim, with a reason.")

# --- 4. radius -----------------------------------------------------------------------------------------------------
# A control is at most 8px and a card at most 18px. The dashboard predates the rule and its pills and 30px cards
# are recorded below with the date they were counted. The list may shrink. It may not grow: a selector that is not
# on it and breaks the limit fails, which is what stops the next .prov being born.
CONTROL = re.compile(r"button|input|select|btn|chip|tag|prov|switch|nav|toast|arr|exit|tip|pill|\ba:")
RADIUS_LEGACY = {           # counted 2026-09-07, at v0.35. 16 controls, 5 cards.
    "nav.views", "nav.views button", ".chip", ".earthctl button", ".btn", ".plan-legend button", ".tabs button",
    ".field input,.field select", ".switch .tr", ".gate input", ".tag", ".wall .exit", ".arr button", ".arrbar",
    ".arrbar select", ".toast", ".card", ".r1", ".r2", ".r3", ".r4",
}
for sel, body in RULES:
    m = re.search(r"border-radius\s*:\s*([^;}]+)", body)
    if not m:
        continue
    vals, w = m.group(1), rule_width(body)
    if "%" in vals:
        if w is None or w <= 24:      # a dot or a ring, not a pill
            continue
        biggest = 999.0
    else:
        px = [float(x) for x in re.findall(r"(\d+(?:\.\d+)?)px", vals)]
        if not px:
            continue
        biggest = max(px)
    kind, limit = ("a control", 8) if CONTROL.search(sel) else ("a card", 18)
    key = re.sub(r"\s*,\s*", ",", " ".join(sel.split()))
    if biggest > limit and key not in RADIUS_LEGACY:
        errs.append(f"{sel} rounds {kind} to {biggest:g}px; the limit is {limit}px. If this is deliberate and old, "
                    f"it belongs in RADIUS_LEGACY with today's date — but that list is meant to shrink.")

# --- 5. provenance is ink -------------------------------------------------------------------------------------------
# A pill in a role colour reads as a verdict on the number beside it. Provenance says where a number came from and
# nothing about whether it is good. Ink family and currentColor only.
# The layer's names (planetai-design/references/planetai-layer.md). The page used to call these
# --red/--green/--blue/--orange; those four no longer exist, so a rule written against them could
# never fire again. Both sets are listed: a fork still on the old names is still checked.
ROLE_TOKENS = ("--signal-worse", "--rings", "--loop-closed", "--cells", "--satellite-only",
               "--red", "--green", "--blue", "--orange")
PAINT = re.compile(r"#[0-9a-fA-F]{3,8}\b|rgba?\(|hsla?\(|" + "|".join(re.escape(t) for t in ROLE_TOKENS))
for sel, body in RULES:
    if "prov" in sel and PAINT.search(body):
        errs.append(f"{sel} carries a colour ({PAINT.search(body).group(0)}). Provenance is ink only — glyph, "
                    f"then one of live / partial / model / cached / example. A pill must never look like a verdict.")
for tag in re.finditer(r"<[^>]*\b(?:class|id)=\"[^\"]*prov[^\"]*\"[^>]*>", BODY):
    style = re.search(r"style=\"([^\"]*)\"", tag.group(0))
    if style and PAINT.search(style.group(1)):
        errs.append(f"an element with prov in its class or id carries an inline colour: {style.group(1)[:60]}")

# --- 6. orange is the satellite and nothing else -----------------------------------------------------------------
# "What only the satellite knows." It was the act button (violation 6), every link hover and the arrange bar.
# #DB7200 is the paper register's satellite orange (3.02:1 on paper); #FF931E is the dark
# register's. Neither may appear away from the satellite layer, and neither may cross registers —
# that last part is planetai-theme.css's own guard, checked by tools/check_theme.py.
ORANGE_DEF = re.compile(r"--(?:orange|satellite-only)\s*:\s*#(?:FF931E|DB7200)|ORANGE\s*=\s*'#FF931E'")
SATELLITE = re.compile(r"satellite|\bsat\b|only the satellite", re.I)
for i, line in enumerate(strip_comments(h + "\n" + CSS_SRC + "\n" + JS_SRC).splitlines(), 1):
    if not re.search(r"--orange|--satellite-only|#FF931E|#DB7200|rgba\(255,\s*147,\s*30|\bORANGE\b", line):
        continue
    # The exemption is "this line is about the satellite layer". The TOKEN is called
    # --satellite-only, so it contains that word itself and would exempt every use of it — the rule
    # would pass anything as long as it used the token, which is exactly what it is guarding.
    # Test the line with the token's own name taken out of it.
    context = line.replace("--satellite-only", "").replace("satellite-only", "")
    if ORANGE_DEF.search(line) or SATELLITE.search(context):
        continue
    errs.append(f"line {i} paints with orange away from the satellite layer: {line.strip()[:80]}")

# --- 7. the dark register --------------------------------------------------------------------------------------
# Fab Blue #20388D on ink #171717 measures 1.72:1 and is invisible; the dark register uses #7FA5E8 at 7.21:1,
# which on paper #F9F5F2 is 2.29:1 and may never appear there. Measured, not assumed — design-log A5.
DARK_DOC = re.search(r"<html[^>]*data-theme=\"dark\"", h) is not None
dark_sel = re.compile(r"\[data-theme=[\"']dark[\"']\]|\.variant-dark")
for sel, body in RULES:
    in_dark = DARK_DOC or bool(dark_sel.search(sel))
    if in_dark and re.search(r"#20388D", body, re.I):
        errs.append(f"{sel} uses Fab Blue #20388D in the dark register, where it measures 1.72:1 on ink and "
                    f"cannot be seen. The dark register's blue is #7FA5E8.")
    if not in_dark and re.search(r"#7FA5E8", body, re.I):
        errs.append(f"{sel} uses the lifted blue #7FA5E8 outside the dark register. On paper it is 2.29:1.")
if not DARK_DOC:
    for src, where in ((CSS_SRC, "the stylesheet"), (JS_SRC, "the script"), (BODY, "the markup")):
        if re.search(r"#7FA5E8", src, re.I):
            errs.append(f"#7FA5E8 is in {where}, but <html> does not declare data-variant=\"dark\", so nothing "
                        f"says this page is the dark register.")
elif re.search(r"#20388D", CSS_SRC + JS_SRC + BODY, re.I):
    errs.append("#20388D is in this page, which declares itself the dark register. Use #7FA5E8.")

# --- 8. what index.html asks the node for --------------------------------------------------------------------------
# The page is one HTML file, and the two companions it does reference (the H3 ground, the mono) are served by an
# allowlist in app/main.py. A src the node does not serve is a silent 404 and a missing ground on every node.
served = set(re.findall(r'"([a-zA-Z0-9._-]+)":\s*\(', main[main.find("COMPANIONS = {"):] if "COMPANIONS = {" in main else ""))
# Everything the DOCUMENT asks for, and everything the RENDERER writes into the document. Both are
# relative to "/", so both must say static/<name>. A url() inside app/static/*.css is relative to
# /static/ already, where a bare name is the correct form — those are rule 9's.
#
# The renderer half matters: the hero's ground, the sign sprite and every satellite frame are
# written by dashboard.js, so scanning only index.html checked almost nothing.
_refs = set(re.findall(r'src="(?!https?:|data:|#)([^"]+)"', h))
_refs |= set(re.findall(r'<link[^>]+href="(?!https?:|data:|#)([^"]+)"', h))
# Any literal src/href the renderer writes — NOT only the ones already under static/, or a
# reference that drops the prefix drops out of the check with it, which is the mistake this line
# was written with. Template expressions (src="${...}") are the satellite frames and are routes,
# not assets; they are excluded by the character class.
_refs |= set(re.findall(r'src="([^"${}]+)"', js))
_refs |= {m.split("#")[0] for m in re.findall(r'href="([^"${}]+)"', js) if "/" in m}
# A src whose PATH is literal and whose query is a template: the ground asks for its register with
# `?variant=${ctx.register}`. Without this the whole reference drops out of the check, because the
# character class above excludes `${}` — which is the same way a reference dropping its prefix
# dropped out, two comments up. The asset is the path; the query is not part of the allowlist.
_refs |= set(re.findall(r'src="([^"${}?]+)\?[^"]*"', js))
# The map ground (UI_GROUND=map) loads its libraries by building the element in script, as
# `{ src: 'static/maplibre-gl.js' }`, so the attribute forms above never see them.
_refs |= set(re.findall(r"(?:src|href):\s*'(static/[^'${}]+)'", js))
for ref in sorted(_refs):
    ref = ref.strip("'\"").split("?")[0]
    # A link OUT (the documentation, the programme) or to one of this node's own routes (the foot's
    # GET /health and /llms.txt) is not an asset the page loads; the route half is checked above.
    if ref.startswith(("https://", "http://")) or ref in routes:
        continue
    if not ref.startswith("static/"):
        errs.append(f"the page loads {ref}, which is not under static/ — app/main.py serves nothing else")
    elif ref[len("static/"):] not in served:
        errs.append(f"the page loads {ref}, which app/main.py's COMPANIONS allowlist does not serve")

# --- 8b. the page computes no H3 ---------------------------------------------------------------------------------
# The node computes, the page draws: every cell ring the page draws arrives as `cells_ll` in /issues' geometry. A
# browser that imports h3-js, or hands deck.gl an H3 id to turn into a hexagon, is computing a boundary the node
# did not send — and at a resolution the node may have refused to publish. deck.gl's bundle carries the H3 layers;
# the page must not reach for them.
_h3 = re.findall(r"h3-js|H3HexagonLayer|H3ClusterLayer|\bh3\.(?:latLngToCell|cellToBoundary|cellToLatLng|gridDisk|"
                 r"polygonToCells|cellToParent|cellToChildren|compactCells|geoToH3|h3ToGeoBoundary|kRing)\b",
                 strip_comments(js))
if _h3:
    errs.append(f"the page computes H3 itself ({', '.join(sorted(set(_h3)))}). The node sends every ring it may "
                f"draw as cells_ll; draw those with PolygonLayer, and add a route to app/main.py if one is missing.")

# --- 9. the stylesheets the page loads ------------------------------------------------------------
# Everything under app/static/*.css is served to a household LAN by the COMPANIONS allowlist in
# app/main.py, and a node may have no route out at all. Two ways that goes wrong silently: a url()
# naming a file nothing serves (no typography, no error), and an @import to a CDN (works on the
# laptop it was written on, dead in the house). tokens.css arrived with both.
import glob as _glob
# The one dead reference this project has decided to live with, named exactly, in exactly one file.
# planetai-theme.css is generated from planetai-design/references/planetai-layer.md and is copied
# here byte-for-byte — tools/check_theme.py holds it to the design repo. Its @font-face names
# `fonts/jetbrains-mono-latin.woff2`, a NESTED path, and /static/<name> takes a name and not a path
# on purpose, on a port that answers a household LAN. So that one request 404s. It costs nothing
# but the request: dashboard.css declares the same family at the flat name the node does serve.
# Making it resolve means a path parameter reaching the filesystem, which is the trade that was
# weighed and refused. Do not widen this to a pattern.
DEAD_BY_DECISION = {("planetai-theme.css", "fonts/jetbrains-mono-latin.woff2")}
for css_path in sorted(_glob.glob("app/static/*.css")):
    body = strip_comments(open(css_path).read())
    name = css_path.split("/")[-1]
    for ref in re.findall(r"url\(\s*['\"]?([^'\")]+)", body):
        ref = ref.strip()
        if ref.startswith("data:"):
            continue
        if ref.startswith(("http://", "https://", "//")):
            errs.append(f"{name} loads {ref[:60]} from the network. A node serves this page on a LAN "
                        f"that may have no route out; bundle it and put it in COMPANIONS.")
        elif ref not in served and (name, ref) not in DEAD_BY_DECISION:
            errs.append(f"{name} loads {ref}, which app/main.py's COMPANIONS allowlist does not serve")
    for imp in re.findall(r"@import\s+(?:url\()?\s*['\"]([^'\"]+)", body):
        if imp.startswith(("http://", "https://", "//")):
            errs.append(f"{name} @imports {imp[:60]} from the network — same reason.")
        elif imp not in served:
            errs.append(f"{name} @imports {imp}, which COMPANIONS does not serve")

# --- the page may shout its own words, never the node's ------------------------------------------------------------
# `text-transform:uppercase` is a rendering, and on one character it is a translation: `µ` uppercases to `M`, so a
# reason the node wrote as "the day's high was 17 µg/m³" was drawn as "17 MG/M³" — milligrams for micrograms, a
# thousandfold, on the hero and on the wall, two lines above a sentence that had the unit right. A household cannot
# tell which of the two numbers to believe and nothing on the page says.
#
# So: every interpolation of the node's own prose — a reason, a sentence, a stack cell's source — must sit inside
# `.said`, which sets text-transform:none, whenever its element is one the stylesheet shouts.
# The two places the node's prose is drawn inside a shouted label, each of which must carry .said. These are
# asserted by shape rather than by walking the markup: template literals are not a DOM, and the first version of
# this rule proved it — looking backwards from the prose it found a SIBLING's class="state" and passed the exact
# markup that put MG/M3 on the wall, and looking forwards it read one component's prose as the next one's. A
# parser here would be a bigger thing than the bug. The tripwire below is what covers the sites not listed here.
# Repointed 15 September 2026: both patterns named markup that only the page before the modular
# rewrite had — the hero chips and its own `why` local are gone with it. The rule is unchanged and
# so is what it guards; these are the two sites on the page that draws today where the node's or a
# pack's own prose lands inside an element the stylesheet shouts.
PROSE_IN_A_SHOUT = [
    (r'class="said">·\s*\$\{esc\(d\.reason_text\[LOC\]\)\}',
     "the kicker's reason, which the node writes (.k uppercases it)"),
    (r'<div class="lab"><span class="said">\$\{esc\(o\.title\)\}',
     "a readout's title, which a pack may supply ([data-kind=\"readout\"] .lab uppercases it)"),
]
for _pat, _what in PROSE_IN_A_SHOUT:
    if not re.search(_pat, JS_SRC):
        errs.append(f"{_what} is no longer wrapped in .said, so the page prints MG/M3 where the node wrote ug/m3")

# --- a box that fills the screen may not contain another one -----------------------------------------------------
# `.wall` sets min-height:100vh and a padding, and index.html carried it on the section AND on the mount inside it.
# Both applied, so the wall was one viewport plus two paddings: 1208px on a 1080px screen, 1167 on a 900px one. A
# wall does not scroll, so at 1440 the node's name, `As of HH:MM` and the word `stale` were not on the screen at
# all — a household read a number and was never shown the word saying it was old.
#
# The check is structural and index.html is small enough to walk: no class whose rule sets min-height (or height)
# in viewport units may sit on an element and on one of its own ancestors.
VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}
_fills = {sel.strip().lstrip(".") for sel, body in RULES
          if re.fullmatch(r"\.[A-Za-z0-9_-]+", sel.strip())
          and re.search(r"\b(?:min-)?height\s*:\s*\d+(?:\.\d+)?(?:d|s|l)?vh\b", body)}
if _fills:
    _stack, _line = [], 1
    for _m in re.finditer(r"<(/?)([a-zA-Z][a-zA-Z0-9-]*)([^>]*?)(/?)>", BODY):
        _line = BODY.count("\n", 0, _m.start()) + 1
        _close, _tag, _attrs, _self = _m.group(1), _m.group(2).lower(), _m.group(3), _m.group(4)
        if _close:
            while _stack and _stack.pop()[0] != _tag:
                pass
            continue
        _cls = re.search(r'class="([^"]*)"', _attrs)
        _cls = set(_cls.group(1).split()) if _cls else set()
        for _c in sorted(_cls & _fills):
            for _atag, _acls, _aline in _stack:
                if _c in _acls:
                    errs.append(f".{_c} sets a viewport height and is on <{_tag}> at index.html line {_line} inside "
                                f"<{_atag}> at line {_aline}, which also carries it. The height and the padding "
                                f"both apply twice and the page is taller than the screen it is for.")
        if _tag not in VOID and not _self:
            _stack.append((_tag, _cls, _line))

# And if a new uppercasing rule appears, somebody has to look at it against the check above rather than find out on
# a wall. This list is the recorded set, dated 14 September 2026; it may shrink and it may not grow silently.
UPPERCASE_KNOWN = {".asking .brand",               # "PLANETAI loading", the page's own two words (28 Sep 2026)
                   ".k", ".chip", ".unit .lab", ".index .state", ".ledger .iss", "table.figs th", ".field .src",
                   ".tag", ".netnode .note", ".wall .wi .st", ".wall .exit",
                   # Added 15 September 2026 with the modular page. Each one was read against the rule
                   # above: every one of these carries the PAGE's own words, or a fixed vocabulary of
                   # the node's that is a word and not prose, and the two places where prose does
                   # reach a shouted element are in .said and are PROSE_IN_A_SHOUT's two patterns.
                   ".claim .fact .k",            # "covers", "cells at resolution N", "its own grain"
                   ".funnel .m2 .h",             # "the reading came back", "answered"
                   ".mv .cap",                   # "out", "in"
                   ".navbar .across .cap",       # "across"
                   ".row.station .silent",       # the literal word "silent", written by the page
                   ".state",                     # the node's five state words — act, notable, quiet,
                                                 # context, none — a closed vocabulary, never a sentence
                   ".wf .cap",                   # the wireframe's captions and a pack's own id
                   '[data-kind="readout"] .lab',  # guarded: the title itself is in .said
                   "details.fold > summary",     # "All eleven grains, and what each is worth"
                   "table.tbl th",               # the grain table's column headings
                   # Added 16 September 2026 with the station list's display cap.
                   ".stations .more a",          # "show all" and "show N" — the page's own two words
                   # Added 18 September 2026 with the year player.
                   ".satplay .satctl button",    # "Play", "Pause", "Motion off", "one year"
                   # Added 22 September 2026 with the Decide card. Four fixed labels this page
                   # writes: "what was seen", "what this node suggests", "who is deciding", "what
                   # will be done". The node's own sentence and the household's are both in the
                   # elements under them, neither of which is shouted.
                   ".decide .k",
                   ".decide form.decided label span",
                   # Added 22 September 2026 with the act form. Two field labels the PAGE writes,
                   # "Who" and "What you did". The keeper's own sentence goes in the input, which is
                   # not shouted and never could be.
                   ".ask form.did label span",
                   # Added 22 September 2026 with the rail's fold. Both carry the PAGE's own
                   # words and nothing else: a heading the page composes around a resolution number,
                   # which uppercasing cannot change, and the literal word "Close".
                   ".railfold .rh h2",
                   ".railfold .rh a",
                   # Added 21 September 2026 with the header's segmented controls. The register is
                   # "Paper" and "Dark"; the mode is "Simple", "Advanced" and "Learn". Five words,
                   # all written by this page. The node's own words cannot reach either control.
                   ".seg button",
                   # Added 21 September 2026 with the lead's bracket meters and its stamp line.
                   # `.stack.meters .col .k` carries LABEL_WORDS — room, wall outside, street, model
                   # — which is an engine constant published verbatim as /issues.labels. A pack can
                   # rename where a reading IS (`where:` overrides WHERE_WORDS and NOUN_WORDS); it
                   # cannot reach these four. Closed vocabulary, four words, never a sentence, and
                   # none of them can contain a mu. `.askref` is this page's own words and a count.
                   ".stack.meters .col .k", ".askref",
                   # Added 22 September 2026 with learn mode. Four rules, all of them chrome the
                   # page writes for itself: "Walk the page", "Close", "Back", "Next", "This page:",
                   # the mark's key (an identifier — `dial`, `share` — not a word of anybody's), and
                   # "n of N". The two places a learn panel carries prose are the quote and the
                   # `more` line, and neither is shouted: `.lpanel .qt` and `.lpanel .more` are set
                   # in the body face at their own case, because one is the documentation's sentence
                   # and the other is this page's.
                   ".learnbar .walk", "#askpane .card.mark .ch",
                   # Added 22 September 2026 with the loading state. Its heading is one of three
                   # sentences this file writes — "Asking the node", "Asking the node again", "The
                   # node stopped answering. Asking again" — and a count. The endpoint paths beside
                   # it are NOT in here and are not shouted: /issues is a route, and a route that has
                   # been uppercased is a route a reader cannot type back.
                   ".asking .hd",
                   # Added 22 September 2026 with the wall's top bar. `.who` is the node's name, its
                   # city, "#wall", the share level and the dial's cadence — NODE_NAME is lowercase
                   # with dashes and a city key is a word, so no unit and no mu can reach it. The
                   # variable and its unit are the other half of that bar and are deliberately NOT
                   # in here: `.wallbox .wtop .what` is left in its own case because µg/m³ shouted
                   # is MG/M³. `.wnoask` is this page's one sentence, "Answer on Telegram, not here."
                   ".wallbox .wtop .who", ".wallbox .wnoask"}
_shouting = {sel.strip() for sel, body in RULES if re.search(r"text-transform\s*:\s*uppercase", body)}
for _new in sorted(_shouting - UPPERCASE_KNOWN):
    errs.append(f"{_new} is a new text-transform:uppercase rule. If the node's own words can reach it, they need "
                f".said — see PROSE_IN_A_SHOUT in this file. Then add it to UPPERCASE_KNOWN.")

# --- and the letter that started all of this -----------------------------------------------------------------
# `µ` uppercases to `M`. Not to a bigger µ: to the letter M, so `µg/m³` is printed `MG/M³` and a household reads
# milligrams where the node said micrograms — a thousandfold error, in the unit, on a wall, silently. It was found
# on the wall foot in September, fixed at the two sites PROSE_IN_A_SHOUT names, and then drawn again on the
# September sketch's wall foot by somebody who had not been told. So it gets a rule rather than a memory.
#
# Two halves, both static, because `make lint` has no browser: a mu authored into the stylesheet, and a mu
# authored into the page's own markup outside a `.said` wrapper. A mu arriving from the NODE is a different
# problem and is already covered — that is what .said and PROSE_IN_A_SHOUT are for.
MU = ("\u00b5", "\u03bc")          # MICRO SIGN and GREEK SMALL LETTER MU; they look identical and both do this
# A mu in the STYLESHEET is always wrong here, whatever the selector: units are the node's words and
# arrive over the wire, so a `content: "µg/m³"` is the page inventing a unit — and one uppercase rule
# anywhere above it turns that into MG/M³. No allowlist, because there is no good case for one.
for _sel, _body in RULES:
    if any(m in _body for m in MU):
        errs.append(f"{_sel.strip()} writes a mu into the stylesheet. Units come from the node, not from "
                    f"CSS, and an uppercase rule turns µg/m³ into MG/M³ — a thousandfold error, on a wall.")
for _i, _line in enumerate(JS_SRC.splitlines(), 1):
    _code = _line.split("//")[0] if not _line.lstrip().startswith(("*", "/*")) else ""
    if any(m in _code for m in MU) and "said" not in _code:
        errs.append(f"dashboard.js:{_i} writes a mu into the page outside .said. If a rule above it ever "
                    f"uppercases, that becomes MG/M³ and the household reads milligrams. Wrap it in .said.")

# --- the learn layer: a mark the page draws and a mark the build wrote are the same set ------------------
# A `.q` with no entry behind it is a question mark that opens nothing; an entry nothing draws is a
# quote maintained against a docs page for no reader. Both are silent — the page renders either way —
# so they are counted here rather than discovered by a tester. build_learn.py's own --check holds the
# other half: that each of those quotes is still a verbatim span of the page it cites.
_learn = pathlib.Path("app/static/learn.json")
if _learn.exists():
    _have = set(json.loads(_learn.read_text())["marks"])
    _drawn = set()
    for _arr in re.findall(r"\blearn:\s*\[([^\]]*)\]", js):
        _drawn |= set(re.findall(r"'([a-z]+)'", _arr))
    _drawn |= set(re.findall(r"\bmark\('([a-z]+)'", js))
    for _k in sorted(_drawn - _have):
        errs.append(f"the page draws a learn mark '{_k}' that app/static/learn.json does not have. "
                    f"Add it to MARKS in tools/build_learn.py, or stop drawing it.")
    for _k in sorted(_have - _drawn):
        errs.append(f"learn.json carries '{_k}' and nothing on the page draws it. Give it to a section "
                    f"(`learn: ['{_k}']`) or to the shell, or take it out of tools/build_learn.py.")

# --- every note names its own subject -----------------------------------------------------------------
# The notes band prints a term beside each note. It used to print the SECTION's title for every note
# in the fold, so a fold of five was five rows reading "What the satellite says" beside five
# paragraphs about five different things — the fold's own heading, said again, five times, telling a
# reader scanning for one of them nothing. `label` fixed that, and the fallback to the section title
# is still there for a note that has none, which is exactly how the repeat would come back: silently,
# one note at a time, with the page rendering perfectly either way. So a note without a label is a
# lint error rather than something somebody notices at the bottom of a long page.
# A note is the only shape on this page whose `id` is followed by `text:` — a row carries `left`,
# `line` and `qty`, never prose — so that pair is what this looks for, and `label:` has to be
# between them.
for _m in re.finditer(r"\{\s*id:\s*[`'\"]([A-Za-z0-9_.-]+)[`'\"]\s*,([^{}]{0,80}?)text\s*:", js):
    if "label:" not in _m.group(2):
        errs.append(f"the note '{_m.group(1)}' has no `label:`, so the notes band prints its section's "
                    f"title beside it \u2014 the same words every other note in that fold prints. Give it a "
                    f"few words naming what THIS note is about.")

# --- SMIL: the one kind of motion this page may not use --------------------------------------------------
# `@media (prefers-reduced-motion: reduce)` reaches CSS animations and nothing else. An SVG <animate>
# keeps running when a household has asked the whole machine for stillness, and there is no way to
# switch it off from a stylesheet. The netmap shipped one and it was rewritten in CSS for exactly
# this; nothing has stopped the next drawing from reaching for it again. This does.
#
# The pattern wants an ATTRIBUTE, so prose about SMIL — the page's own note explaining why the wires
# are not drawn that way, and the comments in this repo — is not a false positive. A real SMIL
# element always carries one.
SMIL = re.compile(r"<(animate|animateTransform|animateMotion|set)\b[^>]*\b"
                  r"(attributeName|dur|values|from|to|begin|repeatCount)\s*=")
for _name, _text in (("index.html", h), ("dashboard.js", js), ("dashboard.css", open("app/static/dashboard.css").read())):
    _m = SMIL.search(_text)
    if _m:
        errs.append(f"{_name} writes an SVG <{_m.group(1)}>. Reduced motion cannot reach SMIL: it keeps "
                    f"moving after a household has asked the machine to stop. Use a CSS animation on a "
                    f"--motion- token, which the one reduce block in planetai-theme.css turns off.")
for _svg in sorted(pathlib.Path("app/static").glob("*.svg")):
    _m = SMIL.search(_svg.read_text())
    if _m:
        errs.append(f"{_svg.name} carries an SVG <{_m.group(1)}>, which reduced motion cannot reach. "
                    f"It is served as a document of its own, so no stylesheet on the page can stop it.")

print("\n".join(f"  x {e}" for e in errs) or
      "  GUI: script parses; every id, endpoint, field and asset resolves; nothing hidden is un-hidden by CSS;\n"
      "       no decorative hexagon, no website palette, no gradient, no rounded verdict, orange only on the\n"
      "       satellite, and the dark register's blue is the one that can be seen")
sys.exit(1 if errs else 0)
