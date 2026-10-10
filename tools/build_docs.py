#!/usr/bin/env python3
"""Build planetai.fab.city/docs from this repository's markdown.

    python3 tools/build_docs.py --out ../planetai/docs          # the site: one folder per page
    python3 tools/build_docs.py --single /tmp/planetai-docs.html  # everything on one page, for review

Source of truth is the markdown: the pages in docs/site/ written for the site, and a handful of pages in
docs/ and at the repo root taken as they are (NAV below says which). The tokens are copied from
app/static — tokens.css, planetai-theme.css and the fonts — so the docs speak the same language as the
dashboard and cannot drift from it: check_theme.py holds that file byte-identical to the design repo.

Needs Python 3.9+ and the `markdown` package on the machine that builds (never on a node).
"""
import argparse
import datetime as dt
import html
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

try:
    import markdown
    from markdown.extensions.toc import TocExtension
except ImportError:  # pragma: no cover
    markdown = None     # main() says so: --check skips, a build refuses

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "docs" / "site"
THEME = SITE / "_theme"
GITHUB = "https://github.com/fabcity/planetai-node"

# slug · source (relative to repo root) · group. Order is the sidebar's order.
NAV = [
    ("Overview", [
        ("introduction", "docs/site/introduction.md"),
        ("how-it-works", "docs/site/how-it-works.md"),
        ("concepts", "docs/site/concepts.md"),
    ]),
    ("Get started", [
        ("platforms", "docs/PLATFORMS.md"),
        ("install", "docs/site/install.md"),
        ("first-ten-minutes", "docs/site/first-ten-minutes.md"),
        ("revive-a-laptop", "docs/REVIVE_A_LAPTOP.md", "Revive a laptop"),
        ("mac-mini", "docs/MAC_MINI.md", "Mac mini"),
    ]),
    ("Operate", [
        ("cli", "docs/site/cli.md"),
        ("configuration", "docs/site/configuration.md"),
        ("updating", "docs/UPDATING.md"),
        ("storage", "docs/STORAGE.md", "Storage and backups"),
        ("networking", "docs/NETWORKING.md"),
        ("radios", "docs/MESHTASTIC.md"),
        ("troubleshooting", "docs/TROUBLESHOOTING.md", "Troubleshooting"),
    ]),
    ("Sensors and sources", [
        ("sensors", "docs/site/sensors.md"),
        ("sources", "docs/site/sources.md", "The source registry"),
        ("before-a-sensor", "docs/PREFILL.md", "Before a sensor"),
        ("use-cases", "docs/USE_CASES.md", "What node #1 can tell you"),
    ]),
    ("Alerts, reports and ρ", [
        ("alerts", "docs/site/alerts.md"),
        ("channels", "docs/site/channels.md"),
        ("report", "docs/site/report.md"),
        ("rho", "docs/site/rho.md"),
    ]),
    ("Packs", [
        ("packs", "docs/site/packs.md"),
        ("packs-reference", "docs/site/packs-reference.md"),
        ("issues", "docs/DOMAINS.md", "Issues and domains"),
        ("pack-ideas", "docs/PACK_IDEAS.md", "Pack ideas"),
    ]),
    ("Dashboard", [
        ("dashboard", "docs/site/dashboard.md"),
        ("wall", "docs/site/wall.md"),
    ]),
    ("Agents", [
        ("ask", "docs/site/ask.md"),
        ("agents", "docs/site/agents.md"),
        ("mcp", "docs/site/mcp.md"),
        ("bot", "docs/site/bot.md"),
    ]),
    ("Sharing and security", [
        ("sharing", "docs/site/sharing.md"),
    ]),
    ("Design", [
        ("design", "docs/site/design.md"),
    ]),
    ("Reference", [
        ("api", "docs/site/api.md"),
        ("schema", "docs/site/schema.md"),
        ("federation", "docs/site/federation.md"),
        ("coverage", "docs/COVERAGE.md", "Index coverage"),
    ]),
    ("Project", [
        ("architecture", "ARCHITECTURE.md", "Architecture"),
        ("spec", "SPEC.md", "Spec"),
        ("developing", "docs/site/developing.md"),
        ("changelog", "CHANGELOG.md"),
    ]),
]

NAV = [(g, [(i[0], i[1], (i[2] if len(i) > 2 else None)) for i in items]) for g, items in NAV]
PAGES = [(slug, src, group) for group, items in NAV for slug, src, _ in items]
SHORT = {slug: short for _, items in NAV for slug, _, short in items if short}
BY_SRC = {src: slug for slug, src, _ in PAGES}
BY_SLUG = {slug: (src, group) for slug, src, group in PAGES}
ORDER = [slug for slug, _, _ in PAGES]

# The dashboard's own copies are the source of truth for the tokens and fonts (check_theme.py).
ASSETS = [
    ("app/static/tokens.css", "tokens.css"),
    ("app/static/planetai-theme.css", "planetai-theme.css"),
    ("app/static/fonts/FunnelSans-VariableFont_wght.ttf", "FunnelSans-VariableFont_wght.ttf"),
    ("app/static/fonts/Figtree-VariableFont_wght.ttf", "Figtree-VariableFont_wght.ttf"),
    ("app/static/fonts/Figtree-Italic-VariableFont_wght.ttf", "Figtree-Italic-VariableFont_wght.ttf"),
    ("app/static/fonts/jetbrains-mono-latin.woff2", "fonts/jetbrains-mono-latin.woff2"),
    ("app/static/signs.svg", "signs.svg"),
]


def git(*args):
    try:
        return subprocess.check_output(["git", *args], cwd=ROOT, text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        return ""


def version():
    v = git("describe", "--tags", "--always")
    if not v and (ROOT / "VERSION").exists():
        v = (ROOT / "VERSION").read_text().strip()
    return v or "dev"


def read_page(src):
    text = (ROOT / src).read_text(encoding="utf-8")
    m = re.search(r"^# (.+)$", text, re.M)
    title = m.group(1).strip() if m else Path(src).stem
    body = text[m.end():] if m else text
    # README-style HTML banners and badge rows have no place on a docs page.
    body = re.sub(r"<p align=\"center\">.*?</p>\s*", "", body, flags=re.S)
    # The release stamp (`<!-- checked: vX -->`, held to the newest release by check_docs.py) is for the gate, not the reader.
    body = re.sub(r"^<!-- checked: v[0-9.]+ -->\n?", "", body, flags=re.M)
    return title, body


def slugify_for(prefix):
    def slugify(value, sep):
        s = re.sub(r"[^\w\s-]", "", value.lower(), flags=re.U).strip()
        s = re.sub(r"[\s_-]+", sep, s) or "section"
        return f"{prefix}--{s}" if prefix else s
    return slugify


def render_md(body, id_prefix=""):
    md = markdown.Markdown(extensions=[
        "tables", "fenced_code", "attr_list", "md_in_html",
        TocExtension(slugify=slugify_for(id_prefix), toc_depth="2-3", permalink=False),
    ])
    out = md.convert(body)
    return out, md.toc_tokens


def page_url(slug, mode, base, from_slug=None):
    if mode == "single":
        return f"#{slug}"
    return f"{base}{slug}/"


def resolve_link(href, src, mode, base, commit):
    """Turn a markdown link into a site link, a GitHub link, or leave it alone."""
    if re.match(r"^(https?:|mailto:|#)", href):
        return href
    target, _, frag = href.partition("#")
    if not target:
        return href
    here = (ROOT / src).parent
    path = (here / target).resolve()
    try:
        rel = path.relative_to(ROOT).as_posix()
    except ValueError:
        return href
    if rel in BY_SRC:
        target_slug = BY_SRC[rel]
        if not frag:
            return page_url(target_slug, mode, base)
        return f"#{target_slug}--{frag}" if mode == "single" else f"{page_url(target_slug, mode, base)}#{frag}"
    if path.exists():
        kind = "tree" if path.is_dir() else "blob"
        return f"{GITHUB}/{kind}/{commit}/{rel}" + (f"#{frag}" if frag else "")
    # A page whose SOURCE is outside docs/site — Architecture, Spec, the changelog, the platform
    # pages — is still linked by its file name, because that is what STYLE.md tells an author to
    # write and the sidebar slug is the same word. Resolving relative to docs/site/ looks for
    # docs/site/architecture.md, which does not exist, so `[Architecture](architecture.md)` came out
    # of the renderer untouched and shipped as a dead link on three pages for as long as it has
    # existed. The slug is the last thing to try, after the real paths.
    stem = target[:-3] if target.endswith(".md") else target.rstrip("/")
    if stem in BY_SLUG:
        if not frag:
            return page_url(stem, mode, base)
        return f"#{stem}--{frag}" if mode == "single" else f"{page_url(stem, mode, base)}#{frag}"
    return href


DEAD_LINK = re.compile(r'href="([^"]*\.md(?:#[^"]*)?)"')


def dead_links(html_body, slug):
    """Any `.md` a link still points at after resolve_link has had its turn.

    An unresolved markdown link is not a broken build, it is a dead link on a published page: the
    renderer leaves the href alone and the site serves it. That is how `architecture.md` reached
    three pages. Collected per page and raised together, so one run names all of them.

    A resolved link may legitimately END in .md — a GitHub blob URL for a repository file, or an
    outside link to somebody else's README. What is dead is a href the renderer did not touch, and
    that is exactly the RELATIVE ones: everything it resolves comes back absolute."""
    return [m.group(1) for m in DEAD_LINK.finditer(html_body)
            if not m.group(1).startswith(("http:", "https:", "mailto:", "#", "/"))]


def postprocess(html_body, src, slug, mode, base, commit):
    # links
    def fix_href(m):
        return f'href="{html.escape(resolve_link(html.unescape(m.group(1)), src, mode, base, commit))}"'
    html_body = re.sub(r'href="([^"]+)"', fix_href, html_body)
    if mode == "single":
        # in-page anchors written by authors get the page's prefix
        html_body = re.sub(r'href="#(?!%s--)([\w-]+)"' % re.escape(slug),
                           lambda m: f'href="#{slug}--{m.group(1)}"', html_body)
    # external links open elsewhere
    html_body = re.sub(r'<a href="(https?://[^"]+)"', r'<a href="\1" rel="noopener"', html_body)
    # endpoint headings: <h3 id=..>GET /health</h3>
    html_body = re.sub(
        r'(<h3 id="[^"]+">)(GET|POST|PUT|DELETE|PATCH) (/[^<]*)(</h3>)',
        r'\1<span class="method">\2</span> <code class="path">\3</code>\4', html_body)
    # Access: lines → chips
    def access(m):
        words = html.unescape(re.sub(r"<[^>]+>", "", m.group(1))).strip()
        chips = " ".join(
            f'<span class="chip access-{re.sub(r"[^a-z]", "", w.lower())}">{html.escape(w)}</span>'
            for w in re.split(r"\s*(?:·|,|\bor\b)\s*", words) if w.strip())
        return f'<p class="access"><span class="k">access</span> {chips}</p>'
    html_body = re.sub(r"<p>Access:\s*(.+?)</p>", access, html_body)
    # notes: blockquote whose first strong word names its kind
    def note(m):
        word = m.group(1).lower()
        kind = "careful" if word.startswith("careful") else "gap" if word.startswith("gap") else "note"
        return f'<blockquote class="note {kind}"><p><strong>{m.group(1)}</strong>'
    html_body = re.sub(r"<blockquote>\s*<p><strong>([^<]+)</strong>", note, html_body)
    # tables scroll on a phone instead of breaking the page
    html_body = html_body.replace("<table>", '<div class="tablewrap"><table>').replace("</table>", "</table></div>")
    return html_body


def toc_html(tokens, depth=0):
    if not tokens:
        return ""
    items = []
    for t in tokens:
        if t["level"] > 3:
            continue
        items.append(f'<li class="l{t["level"]}"><a href="#{t["id"]}">{html.escape(t["name"])}</a>{toc_html(t.get("children"))}</li>')
    return f"<ul>{''.join(items)}</ul>" if items else ""


def sidebar_html(current, mode, base):
    groups = []
    for group, items in NAV:
        lis = []
        for slug, src, _ in items:
            title, _ = TITLES[slug]
            cls = ' class="here"' if slug == current else ""
            lis.append(f'<li{cls}><a href="{page_url(slug, mode, base)}" data-slug="{slug}">{html.escape(title)}</a></li>')
        label = html.escape(group).replace("ρ", '<span class="said">ρ</span>')  # uppercase turns ρ into Ρ, which reads as P
        groups.append(f'<section class="group"><h2 class="k">{label}</h2><ul>{"".join(lis)}</ul></section>')
    return "".join(groups)


def prev_next(slug, mode, base):
    i = ORDER.index(slug)
    parts = []
    if i > 0:
        p = ORDER[i - 1]
        parts.append(f'<a class="prev" href="{page_url(p, mode, base)}"><span class="k">previous</span>{html.escape(TITLES[p][0])}</a>')
    else:
        parts.append("<span></span>")
    if i < len(ORDER) - 1:
        n = ORDER[i + 1]
        parts.append(f'<a class="next" href="{page_url(n, mode, base)}"><span class="k">next</span>{html.escape(TITLES[n][0])}</a>')
    return f'<nav class="prevnext">{"".join(parts)}</nav>'


TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} · PLANETAI node docs</title>
<meta name="description" content="{description}">
<link rel="stylesheet" href="{assets}tokens.css">
<link rel="stylesheet" href="{assets}planetai-theme.css">
<link rel="stylesheet" href="{assets}docs.css">
<script>
(function(){{try{{var t=localStorage.getItem('planetai_docs_theme');if(!t)t=matchMedia('(prefers-color-scheme: dark)').matches?'dark':'paper';if(t==='dark')document.documentElement.setAttribute('data-theme','dark');}}catch(e){{}}}})();
</script>
</head>
<body class="{bodyclass}">
<a class="skip" href="#content">Skip to content</a>
<header class="top">
  <button class="menu" aria-label="Menu" aria-expanded="false">Menu</button>
  <a class="brand" href="{home}"><span class="wordmark">PLANETAI</span><span class="docs">node docs</span></a>
  <span class="chip version" title="built {built} from {commit}">{version}</span>
  <div class="search"><input id="q" type="search" placeholder="Search the docs" aria-label="Search the docs" autocomplete="off"><kbd>/</kbd><div id="results" hidden></div></div>
  <nav class="links">
    <a href="https://planetai.fab.city/node0/">node0</a>
    <a href="{github}" rel="noopener">GitHub</a>
    <button class="theme" aria-label="Switch register">Dark</button>
  </nav>
</header>
<div class="frame">
  <aside class="side" id="side"><nav aria-label="Pages">{sidebar}</nav></aside>
  <main id="content">
    {articles}
  </main>
  <aside class="toc" id="toc"><h2 class="k">On this page</h2>{toc}</aside>
</div>
<footer class="foot"><span class="mono">planetai-node {version} · built {built} from {commit}</span><span class="mono">docs CC BY 4.0 · code Apache-2.0 · Fab City</span></footer>
<script src="{assets}docs.js" defer></script>
</body>
</html>
"""


def article_html(slug, body_html, toc, mode, base, commit, src, lead_class=""):
    title, _ = TITLES[slug]
    crumb = html.escape(BY_SLUG[slug][1]).replace("ρ", '<span class="said">ρ</span>')
    edit = f"{GITHUB}/edit/main/{src}"
    where = "" if mode == "multi" else f' id="{slug}"'
    return (f'<article class="page{lead_class}"{where} data-slug="{slug}">'
            f'<p class="crumbs k">{crumb}</p>'
            f'<h1>{html.escape(title)}</h1>'
            f'{body_html}'
            f'{prev_next(slug, mode, base)}'
            f'<p class="edit mono"><a href="{edit}" rel="noopener">Edit this page on GitHub</a> · source <code>{src}</code></p>'
            f'</article>')


def first_paragraph(body_html):
    m = re.search(r"<p>(.*?)</p>", body_html, re.S)
    text = re.sub(r"<[^>]+>", "", m.group(1)) if m else ""
    return html.escape(html.unescape(text))[:200]


def search_index(rendered, mode, base):
    out = []
    for slug, (body_html, toc) in rendered.items():
        title, _ = TITLES[slug]
        sections = []
        # split on headings
        parts = re.split(r'(<h[23] id="[^"]+">.*?</h[23]>)', body_html)
        head, text = None, parts[0]
        def push(hid, hname, t):
            plain = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", t))).strip()
            if plain or hname:
                sections.append({"id": hid, "h": hname, "t": plain[:600]})
        push("", "", text)
        for i in range(1, len(parts), 2):
            hm = re.match(r'<h[23] id="([^"]+)">(.*?)</h[23]>', parts[i], re.S)
            push(hm.group(1), html.unescape(re.sub(r"<[^>]+>", "", hm.group(2))), parts[i + 1] if i + 1 < len(parts) else "")
        out.append({"slug": slug, "title": title, "url": page_url(slug, mode, base), "group": BY_SLUG[slug][1], "s": sections})
    return out


TITLES = {}


A_HREF = re.compile(r'<a [^>]*?href="([^"]+)"')
ANCHOR = re.compile(r'\sid="([^"]+)"')


def check():
    """What `make lint` asks of the site: the map is whole, and every link on it lands.

    The site fell fifteen releases behind the node while every gate stayed green, because no gate
    read docs/site/. tools/check_docs.py now reads its pages for commands, settings, paths and
    endpoints; this reads them as a site. Every NAV source exists; every page in docs/site/ is in
    NAV (a page nobody can reach is a page nobody corrects); every link the renderer produces
    resolves to a page, and every `#anchor` to a heading that page actually has. Writes nothing.
    Needs `markdown`; without it the check says so and passes, the way the rule check does
    without sqlglot, because a node never installs it."""
    if markdown is None:
        print("  - docs site check skipped (pip install markdown to enable)")
        return 0
    errs = []
    for slug, src, _ in PAGES:
        if not (ROOT / src).exists():
            errs.append(f"NAV names {src} for /{slug}/, which does not exist")
    in_nav = {src for _, src, _ in PAGES}
    for f in sorted(SITE.glob("*.md")):
        rel = f.relative_to(ROOT).as_posix()
        if f.name != "STYLE.md" and rel not in in_nav:
            errs.append(f"{rel} is not in NAV, so no page links to it and the site does not build it")
    if errs:
        print("\n".join(f"  x {e}" for e in errs))
        return 1
    base, commit = "/docs/", "HEAD"
    rendered, ids = {}, {}
    for slug, src, _ in PAGES:
        title, body = read_page(src)
        TITLES[slug] = (SHORT.get(slug, title), src)
        body_html, _toc = render_md(body, "")
        body_html = postprocess(body_html, src, slug, "multi", base, commit)
        rendered[slug] = body_html
        ids[slug] = set(ANCHOR.findall(body_html))
        for href in dead_links(body_html, slug):
            errs.append(f"{src}: links to {href}, which resolved to no page")
    for slug, body_html in rendered.items():
        src = BY_SLUG[slug][0]
        for href in set(A_HREF.findall(body_html)):
            href = html.unescape(href)
            if href.startswith("#"):
                if href[1:] and href[1:] not in ids[slug]:
                    errs.append(f"{src}: links to {href}, which is no heading on this page")
                continue
            if not href.startswith(base):
                continue
            path, _, frag = href[len(base):].partition("#")
            target = path.strip("/")
            if target == "" or target.startswith("assets"):
                continue
            if target not in rendered:
                errs.append(f"{src}: links to {href}, which is no page")
            elif frag and frag not in ids[target]:
                errs.append(f"{src}: links to {href}, and {BY_SLUG[target][0]} has no heading #{frag}")
    print("\n".join(f"  x {e}" for e in errs) or f"  docs site: {len(PAGES)} pages, every link and anchor lands")
    return 1 if errs else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", help="output folder for the multi-page site (e.g. ../planetai/docs)")
    ap.add_argument("--single", help="write everything into one HTML file at this path")
    ap.add_argument("--base", default="/docs/", help="URL prefix the site is served under (multi-page)")
    ap.add_argument("--bare", action="store_true", help="with --single: no html/head/body skeleton (for a host that adds its own)")
    ap.add_argument("--check", action="store_true", help="render every page, write nothing, fail on a broken map, link or anchor (make lint)")
    args = ap.parse_args()
    if args.check:
        sys.exit(check())
    if not args.out and not args.single:
        ap.error("--out DIR or --single FILE")
    if markdown is None:
        sys.exit("pip install markdown   (the build needs it; a node never does)")

    ver = version()
    commit = git("rev-parse", "--short", "HEAD") or "unknown"
    built = dt.date.today().isoformat()

    # titles first: the sidebar needs every page's title before any page renders
    sources = {}
    for slug, src, _ in PAGES:
        title, body = read_page(src)
        TITLES[slug] = (SHORT.get(slug, title), src)
        sources[slug] = body

    for mode in (["multi"] if args.out else []) + (["single"] if args.single else []):
        base = args.base if mode == "multi" else ""
        rendered = {}
        dead = []
        for slug, src, _ in PAGES:
            prefix = slug if mode == "single" else ""
            body_html, toc = render_md(sources[slug], prefix)
            body_html = postprocess(body_html, src, slug, mode, base, commit)
            rendered[slug] = (body_html, toc)
            for href in dead_links(body_html, slug):
                dead.append(f"{slug} ({src}) links to {href}, which resolved to nothing")

        if dead:
            sys.exit("dead markdown links — the renderer left these as they were written, so the "
                     "site would serve them:\n  " + "\n  ".join(dead)
                     + "\n\nLink a page by its sidebar slug (see docs/site/STYLE.md), or a "
                       "repository file by its path from the repo root.")

        if mode == "multi":
            out = Path(args.out).resolve()
            assets_dir = out / "assets"
            assets_dir.mkdir(parents=True, exist_ok=True)
            (assets_dir / "fonts").mkdir(exist_ok=True)
            for src, dst in ASSETS:
                shutil.copy(ROOT / src, assets_dir / dst)
            shutil.copy(THEME / "docs.css", assets_dir / "docs.css")
            shutil.copy(THEME / "docs.js", assets_dir / "docs.js")
            (assets_dir / "search.json").write_text(json.dumps(search_index(rendered, mode, base), ensure_ascii=False))
            for slug, src, _ in PAGES:
                body_html, toc = rendered[slug]
                page = TEMPLATE.format(
                    title=html.escape(TITLES[slug][0]), description=first_paragraph(body_html),
                    assets=f"{base}assets/", home=f"{base}", github=GITHUB, version=ver, built=built, commit=commit,
                    bodyclass="multi", sidebar=sidebar_html(slug, mode, base),
                    articles=article_html(slug, body_html, toc, mode, base, commit, src),
                    toc=toc_html(toc))
                d = out / slug
                d.mkdir(exist_ok=True)
                (d / "index.html").write_text(page, encoding="utf-8")
            # /docs/ itself is the introduction
            shutil.copy(out / ORDER[0] / "index.html", out / "index.html")
            # a plain-text index for agents, beside llms.txt's spirit
            (out / "llms.txt").write_text("# PLANETAI node docs\n\n" + "\n".join(
                f"- [{TITLES[s][0]}](https://planetai.fab.city{base}{s}/)" for s in ORDER) + "\n")
            print(f"  {len(PAGES)} pages → {out}  ({ver}, {commit})")
        else:
            single = Path(args.single).resolve()
            single.parent.mkdir(parents=True, exist_ok=True)
            adir = single.parent / (single.stem + "_assets")
            adir.mkdir(exist_ok=True)
            (adir / "fonts").mkdir(exist_ok=True)
            for src, dst in ASSETS:
                shutil.copy(ROOT / src, adir / dst)
            shutil.copy(THEME / "docs.css", adir / "docs.css")
            shutil.copy(THEME / "docs.js", adir / "docs.js")
            (adir / "search.json").write_text(json.dumps(search_index(rendered, mode, base), ensure_ascii=False))
            articles = "".join(article_html(s, rendered[s][0], rendered[s][1], mode, base, commit, TITLES[s][1])
                               for s in ORDER)
            page = TEMPLATE.format(
                title="PLANETAI node documentation", description="Everything the node is, on one page.",
                assets=f"{adir.name}/", home="#" + ORDER[0], github=GITHUB, version=ver, built=built, commit=commit,
                bodyclass="single", sidebar=sidebar_html(None, mode, base), articles=articles,
                toc="")
            if args.bare:
                # a host that wraps the file in its own skeleton: keep the title, the links and the body's content
                head = re.search(r"<head>(.*?)</head>", page, re.S).group(1)
                head = re.sub(r"<meta [^>]*>\s*", "", head)
                body = re.search(r"<body[^>]*>(.*)</body>", page, re.S).group(1)
                head = re.sub(r"<title>.*?</title>", "<title>PLANETAI node docs</title>", head, flags=re.S)
                body = f"<script>document.body.className='{'single' if mode == 'single' else 'multi'}';</script>" + body
                page = head.strip() + "\n" + body
            single.write_text(page, encoding="utf-8")
            print(f"  {len(PAGES)} pages → {single}  ({ver}, {commit})")


if __name__ == "__main__":
    main()
