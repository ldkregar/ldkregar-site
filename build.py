#!/usr/bin/env python3
"""Build ldkregar.com.

Pulls Lori's publications from Europe PMC (by ORCID, plus a title watch for the
upcoming bioRxiv preprint), merges hand-entered items from data/manual.json,
optionally pulls the latest Substack posts, and renders template.html into
dist/index.html.

  python3 build.py            # live build (used by the nightly GitHub Action)
  python3 build.py --offline  # no network: uses data/seed.json instead

If Europe PMC can't be reached the live build exits with an error, so the
previously deployed site stays up rather than being replaced by an empty list.
"""
import datetime as dt
import html
import json
import re
import shutil
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DIST = ROOT / "dist"
CFG = json.loads((ROOT / "config.json").read_text())
EPMC = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
UA = {"User-Agent": "ldkregar.com site builder (+https://ldkregar.com)"}
OFFLINE = "--offline" in sys.argv


# ---------------------------------------------------------------- fetching
def get(url, timeout=30):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def epmc_search(query):
    results, cursor = [], "*"
    while True:
        params = urllib.parse.urlencode({
            "query": query, "format": "json", "resultType": "core",
            "pageSize": 100, "cursorMark": cursor,
        })
        data = json.loads(get(f"{EPMC}?{params}"))
        page = data.get("resultList", {}).get("result", [])
        results += page
        nxt = data.get("nextCursorMark")
        if not page or not nxt or nxt == cursor:
            return results
        cursor = nxt


def from_epmc(r):
    src = r.get("source")
    journal = r.get("journalInfo") or {}
    venue = (r.get("journalTitle")
             or (journal.get("journal") or {}).get("title")
             or (r.get("bookOrReportDetails") or {}).get("publisher")
             or ("Preprint" if src == "PPR" else ""))
    doi = r.get("doi")
    return {
        "title": (r.get("title") or "").strip().rstrip("."),
        "authors": (r.get("authorString") or "").strip().rstrip("."),
        "venue": venue,
        "year": str(r.get("pubYear") or ""),
        "date": r.get("firstPublicationDate") or str(r.get("pubYear") or ""),
        "doi": doi,
        "url": f"https://doi.org/{doi}" if doi
               else f"https://europepmc.org/article/{src}/{r.get('id')}",
        "kind": "preprint" if src == "PPR" else "article",
        "volume": journal.get("volume"),
        "pages": r.get("pageInfo"),
    }


def key(p):
    if p.get("doi"):
        return p["doi"].lower()
    return re.sub(r"[^a-z0-9]", "", p["title"].lower())


def load_publications():
    pubs = json.loads((ROOT / "data" / "manual.json").read_text())
    if OFFLINE:
        pubs += json.loads((ROOT / "data" / "seed.json").read_text())
    else:
        found = epmc_search(f'AUTHORID:"{CFG["orcid"]}"')
        watch = CFG["featured"]["title"].replace('"', "")
        found += epmc_search(f'TITLE:"{watch}"')
        for doi in CFG.get("watch_dois", []):   # listed even if missing from the ORCID record
            found += epmc_search(f'DOI:"{doi}"')
        pubs += [from_epmc(r) for r in found]
    unique = {}
    for p in pubs:
        unique.setdefault(key(p), p)
    return sorted(unique.values(), key=lambda p: p.get("date", ""), reverse=True)


def load_posts():
    url = CFG.get("substack_url", "").rstrip("/")
    if not url or OFFLINE:
        return []
    try:
        root = ET.fromstring(get(f"{url}/feed", timeout=20))
    except Exception as e:  # a feed hiccup shouldn't block the papers
        print(f"Substack feed skipped: {e}", file=sys.stderr)
        return []
    posts = []
    for item in root.iter("item"):
        date = item.findtext("pubDate") or ""
        try:
            date = dt.datetime.strptime(date[:16], "%a, %d %b %Y").strftime("%d %b %Y")
        except ValueError:
            pass
        posts.append({"title": item.findtext("title") or "",
                      "url": item.findtext("link") or url, "date": date})
    return posts[:3]


# ---------------------------------------------------------------- rendering
e = html.escape


def fmt_authors(authors):
    me = CFG["surname"].lower()
    names = [n.strip() for n in authors.split(",") if n.strip()]
    etal = bool(names) and names[-1].lower() in ("et al", "et al.")
    if etal:
        names = names[:-1]
    mark = lambda n: f"<strong>{e(n)}</strong>" if me in n.lower() else e(n)
    if len(names) <= 6:
        return ", ".join(map(mark, names)) + (", et al." if etal else "")
    idx = next((i for i, n in enumerate(names) if me in n.lower()), None)
    parts = [mark(n) for n in names[:3]]
    if idx is not None and idx >= 3:
        parts += ["…", mark(names[idx])]
    return ", ".join(parts) + ", et al."


KIND_LABEL = {"article": "Journal article", "preprint": "Preprint", "thesis": "Thesis"}


def render_pub(p):
    detail = e(p["venue"])
    if p.get("volume"):
        detail += f" {e(p['volume'])}"
        if p.get("pages"):
            detail += f", {e(p['pages'])}"
    doi = f'<span class="pub-doi">doi:{e(p["doi"])}</span>' if p.get("doi") else ""
    return f"""
      <li class="pub">
        <span class="pub-year">{e(p['year'])}</span>
        <div class="pub-body">
          <a class="pub-title" href="{e(p['url'])}" target="_blank" rel="noopener">{e(p['title'])}</a>
          <p class="pub-authors">{fmt_authors(p['authors'])}</p>
          <p class="pub-meta"><span class="tag tag-{e(p['kind'])}">{KIND_LABEL.get(p['kind'], 'Output')}</span> <em>{detail}</em> {doi}</p>
        </div>
      </li>"""


def render_featured(pubs):
    f = CFG["featured"]
    target = re.sub(r"[^a-z0-9]", "", f["title"].lower())
    hit = next((p for p in pubs if re.sub(r"[^a-z0-9]", "", p["title"].lower()) == target), None)
    if hit:
        status = f'{e(hit["venue"])} · {e(hit["year"])}'
        action = f'<a class="btn btn-solid" href="{e(hit["url"])}" target="_blank" rel="noopener">Read the paper</a>'
        authors = fmt_authors(hit["authors"])
    else:
        status = "Coming soon to bioRxiv"
        action = '<span class="btn btn-ghost" aria-disabled="true">Link appears here on release</span>'
        authors = fmt_authors(f["authors"])
    return f"""
      <article class="featured">
        <p class="eyebrow"><span class="dot-live" aria-hidden="true"></span>New preprint · {status}</p>
        <h3 class="featured-title">{e(f['title'])}</h3>
        <p class="pub-authors">{authors}</p>
        <p class="featured-summary">{e(f['summary'])}</p>
        <div class="actions">{action}</div>
      </article>"""


def render_writing(posts):
    url = CFG.get("substack_url", "")
    if not url:
        return """
        <p class="writing-lede">Notes on epigenetics, disease risk and turning research into products.</p>"""
    items = "".join(
        f'<li><a href="{e(p["url"])}" target="_blank" rel="noopener">{e(p["title"])}</a><span>{e(p["date"])}</span></li>'
        for p in posts)
    body = f'<ul class="posts">{items}</ul>' if items else \
        '<p class="writing-lede">Notes on epigenetics, disease risk and turning research into products.</p>'
    return body + f'\n        <div class="actions"><a class="btn btn-solid" href="{e(url)}" target="_blank" rel="noopener">Subscribe on Substack</a></div>'


def main():
    try:
        pubs = load_publications()
    except Exception as err:
        sys.exit(f"Europe PMC lookup failed, not deploying: {err}")
    posts = load_posts()
    feat = re.sub(r"[^a-z0-9]", "", CFG["featured"]["title"].lower())
    listed = [p for p in pubs if re.sub(r"[^a-z0-9]", "", p["title"].lower()) != feat]

    sub = CFG.get("substack_url", "")
    nav_sub = (f'<a class="btn btn-ghost" href="{e(sub)}" target="_blank" rel="noopener">Substack</a>'
               if sub else "")
    page = (ROOT / "template.html").read_text()
    for k, v in {
        "{{FEATURED}}": render_featured(pubs),
        "{{PUBLICATIONS}}": "".join(map(render_pub, listed)),
        "{{WRITING}}": render_writing(posts),
        "{{SUBSTACK_BUTTON}}": nav_sub,
        "{{UPDATED}}": dt.date.today().strftime("%d %B %Y"),
        "{{YEAR}}": str(dt.date.today().year),
        "{{ORCID}}": CFG["orcid"],
        "{{EMAIL}}": CFG["email"],
    }.items():
        page = page.replace(k, v)

    if DIST.exists():
        shutil.rmtree(DIST)
    DIST.mkdir()
    (DIST / "index.html").write_text(page)
    (DIST / "CNAME").write_text("ldkregar.com\n")
    print(f"Built dist/index.html with {len(pubs)} publications, {len(posts)} posts.")


if __name__ == "__main__":
    main()
