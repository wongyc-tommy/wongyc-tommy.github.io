#!/usr/bin/env python3
"""
Build the static site from content.md.

    python3 build.py

Every "# Heading" in content.md becomes its own page:

    # About        ->  /index.html          (the first tab is the homepage)
    # Research     ->  /research/index.html
    # Publications ->  /publications/index.html

"# Profile" is special and becomes the sidebar on every page.

Each page is fully rendered HTML — no JavaScript, no #hash routing — so
search engines, Google Scholar and link previews see real content.

Optional, per section: a line of the form

    <!-- description: one sentence for search results -->

sets that page's meta description. Without it, the first paragraph is used.
"""

import html
import re
import shutil
import sys
from pathlib import Path

try:
    import markdown
except ImportError:
    sys.exit("Missing dependency. Run:  python3 -m pip install --user markdown")

# ---------------------------------------------------------------------------
# Set this to where the site is published. Used for canonical URLs, the
# sitemap, and link previews. No trailing slash.
SITE_URL = "https://wongyc-tommy.github.io"

AUTHOR = "Tommy YC Wong"
AUTHOR_ZH = "黃昱翔"
ORCID = "https://orcid.org/0009-0008-2769-3536"
AFFILIATION = "Hong Kong Baptist University"
FOOTER = "© 2026 Tommy YC Wong · Last updated July 2026"

ROOT = Path(__file__).parent
SOURCE = ROOT / "content.md"
CSS_VERSION = "6"

MD = markdown.Markdown(extensions=["nl2br", "sane_lists", "md_in_html"])


def separate_quotes(md_text):
    """Keep consecutive '>' blocks as separate cards.

    Markdown would otherwise fuse two quote blocks separated by one blank
    line into a single blockquote, running two publications together.
    """
    out, prev_quoted = [], False
    for line in md_text.split("\n"):
        quoted = line.startswith(">")
        if quoted and prev_quoted and out and not out[-1].strip():
            out.insert(len(out) - 1, "<!-- -->")
        if line.strip():
            prev_quoted = quoted
        out.append(line)
    return "\n".join(out)


def render(md_text):
    MD.reset()
    html_out = MD.convert(separate_quotes(md_text))
    html_out = html_out.replace("<!-- -->\n", "").replace("<!-- -->", "")
    # A lone <img> must stay a direct child of its container: the mobile
    # sidebar places img.portrait as a grid item, and a <p> wrapper would
    # take that slot instead and collide with the name.
    return re.sub(r"<p>\s*(<img\b[^>]*>)\s*</p>", r"\1", html_out)


def slugify(title):
    return re.sub(r"^-|-$", "", re.sub(r"[^a-z0-9]+", "-", title.lower()))


def parse(text):
    """Split content.md into sections at each top-level '# Heading'."""
    sections, current = [], None
    for line in text.split("\n"):
        m = re.match(r"^# (.+)$", line)
        if m:
            current = {"title": m.group(1).strip(), "lines": []}
            sections.append(current)
        elif current is not None:
            current["lines"].append(line)
    for s in sections:
        body = "\n".join(s["lines"])
        m = re.search(r"<!--\s*description:\s*(.+?)\s*-->", body)
        s["description"] = m.group(1) if m else None
        s["body"] = re.sub(r"<!--\s*description:.*?-->\s*", "", body, flags=re.S)
    return sections


def first_paragraph(html_text, limit=160):
    """Fall back to the first real sentence of the page for meta description."""
    for para in re.findall(r"<p>(.*?)</p>", html_text, flags=re.S):
        plain = html.unescape(re.sub(r"<[^>]+>", "", para)).strip()
        plain = re.sub(r"\s+", " ", plain)
        if len(plain) > 40:
            if len(plain) <= limit:
                return plain
            return plain[:limit].rsplit(" ", 1)[0] + "…"
    return ""


def reroot(html_text, prefix):
    """Rewrite relative asset links so they resolve from a subdirectory."""
    if not prefix:
        return html_text

    def fix(m):
        attr, url = m.group(1), m.group(2)
        if re.match(r"^(https?:|mailto:|#|/|data:)", url):
            return m.group(0)
        return f'{attr}="{prefix}{url}"'

    return re.sub(r'\b(href|src)="([^"]*)"', fix, html_text)


def externalise(html_text):
    """Open off-site links in a new tab, as the old JS viewer did."""

    def fix(m):
        if re.match(r'^href="https?:', m.group(0)):
            return m.group(0) + ' target="_blank" rel="noopener noreferrer"'
        return m.group(0)

    return re.sub(r'href="[^"]*"', fix, html_text)


PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title}</title>
  <meta name="description" content="{description}">
  <meta name="author" content="{author}">
  <link rel="canonical" href="{canonical}">
  <meta property="og:type" content="{og_type}">
  <meta property="og:title" content="{title}">
  <meta property="og:description" content="{description}">
  <meta property="og:url" content="{canonical}">
  <meta property="og:image" content="{site}/images/profile.jpg">
  <meta name="twitter:card" content="summary">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Source+Serif+4:ital,opsz,wght@0,8..60,400..700;1,8..60,400..700&family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="{up}css/style.css?v={cssv}">
  <link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><rect width='100' height='100' rx='14' fill='%231f4e6e'/><text x='50' y='68' font-size='52' font-family='Georgia,serif' fill='white' text-anchor='middle'>W</text></svg>">
{extra_head}</head>
<body>

<header>
  <div class="container header-inner">
    <nav><ul>
{nav}
    </ul></nav>
  </div>
</header>

<main>
  <div class="container layout">
    <aside id="profile">
{profile}
    </aside>
    <div id="content">
{content}
    </div>
  </div>
</main>

<footer>
  <div class="container">
    {footer}
  </div>
</footer>

</body>
</html>
"""

JSONLD = """  <script type="application/ld+json">
  {{
    "@context": "https://schema.org",
    "@type": "Person",
    "name": "{author}",
    "alternateName": "{author_zh}",
    "url": "{site}/",
    "image": "{site}/images/profile.jpg",
    "jobTitle": "PhD Student in Linguistics",
    "affiliation": {{"@type": "Organization", "name": "{affiliation}"}},
    "identifier": "{orcid}",
    "sameAs": ["{orcid}"]
  }}
  </script>
"""


def main():
    if not SOURCE.exists():
        sys.exit(f"content.md not found at {SOURCE}")

    sections = parse(SOURCE.read_text(encoding="utf-8"))
    if not sections:
        sys.exit('content.md has no "# Heading" sections.')

    profile_md = ""
    for i, s in enumerate(sections):
        if s["title"].lower() == "profile":
            profile_md = sections.pop(i)["body"]
            break
    if not sections:
        sys.exit("content.md only has a Profile section — add some tabs.")

    # First tab is the homepage; the rest get their own directory.
    for i, s in enumerate(sections):
        s["slug"] = "" if i == 0 else slugify(s["title"])
        s["path"] = "/" if i == 0 else f"/{s['slug']}/"
        s["up"] = "" if i == 0 else "../"
        s["out"] = ROOT / ("index.html" if i == 0 else f"{s['slug']}/index.html")

    profile_html = externalise(render(profile_md))

    # Remove stale page directories from a previous build.
    keep = {s["slug"] for s in sections if s["slug"]}
    for old in ROOT.glob("*/index.html"):
        d = old.parent
        if d.name not in keep and d.name not in {"css", "files", "images", ".git"}:
            shutil.rmtree(d)

    urls = []
    for s in sections:
        body_html = externalise(render(s["body"]))
        description = s["description"] or first_paragraph(body_html)
        canonical = SITE_URL + s["path"]
        is_home = s["slug"] == ""

        nav = "\n".join(
            '      <li><a href="{href}"{cls}>{label}</a></li>'.format(
                href=s["up"] + (t["slug"] + "/" if t["slug"] else "") or "./",
                cls=' class="active"' if t is s else "",
                label=html.escape(t["title"]),
            )
            for t in sections
        )

        page = PAGE.format(
            title=(
                f"{AUTHOR} — Linguistics, {AFFILIATION}"
                if is_home
                else f"{html.escape(s['title'])} — {AUTHOR}"
            ),
            description=html.escape(description, quote=True),
            author=AUTHOR,
            canonical=canonical,
            site=SITE_URL,
            og_type="profile" if is_home else "article",
            up=s["up"],
            cssv=CSS_VERSION,
            extra_head=(
                JSONLD.format(
                    author=AUTHOR,
                    author_zh=AUTHOR_ZH,
                    site=SITE_URL,
                    affiliation=AFFILIATION,
                    orcid=ORCID,
                )
                if is_home
                else ""
            ),
            nav=nav,
            profile=reroot(profile_html, s["up"]),
            content=reroot(body_html, s["up"]),
            footer=FOOTER,
        )

        s["out"].parent.mkdir(parents=True, exist_ok=True)
        s["out"].write_text(page, encoding="utf-8")
        urls.append(canonical)
        print(f"  {s['out'].relative_to(ROOT)}")

    (ROOT / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "".join(f"  <url><loc>{u}</loc></url>\n" for u in urls)
        + "</urlset>\n",
        encoding="utf-8",
    )
    (ROOT / "robots.txt").write_text(
        f"User-agent: *\nAllow: /\n\nSitemap: {SITE_URL}/sitemap.xml\n", encoding="utf-8"
    )
    print(f"  sitemap.xml\n  robots.txt\n\nBuilt {len(urls)} pages.")

    if "wongyc.github.io" in SITE_URL:
        print(
            "\nNote: SITE_URL in build.py is still the placeholder. Set it to your\n"
            "real address so canonical URLs, the sitemap and link previews are right."
        )


if __name__ == "__main__":
    main()
