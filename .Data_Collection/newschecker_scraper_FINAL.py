"""
regional_edition_scraper.py
============================
Scrapes FULL claim archives (not query-seeded search results) from native
Gujarati / Marathi fact-checking editions, to fix the language imbalance in
Sakshya that the Google Fact Check API keyword-seed approach can't fix.

WHY THIS APPROACH
------------------
The Google Fact Check Tools API only returns claims that match a *query*.
For low-volume languages (Gujarati, Marathi) this always undersamples, no
matter how good the seed keywords are. This script instead walks a site's
own article archive directly, so every claim the outlet has ever published
gets collected -- no query bottleneck.

HOW EXTRACTION WORKS
---------------------
IFCN-verified fact-checkers are required to publish structured ClaimReview
markup (schema.org/ClaimReview) on their articles -- it's the same JSON-LD
block Google's own Fact Check API reads. We look for that first because it's
far more reliable than guessing CSS selectors. If a page doesn't have it, we
fall back to a best-effort HTML scrape (title / date / body paragraph).

IMPORTANT -- PLEASE READ BEFORE RUNNING
-----------------------------------------
Verification status as of Jul 2026 (via a read-only fetch tool, not this
script -- this script itself still could not be test-executed against live
sites from the sandbox this was built in; outbound network there is
restricted to package registries only, not general websites):

  CONFIRMED for newschecker.in/gu (spot-checked one category listing page
  and one article page):
    - category slugs (crime-gu, politics-gu, viral-gu, religion-gu,
      science-and-technology-gu, health-and-wellness-gu, news-gu,
      daily-reads-gujarati, fact-checks-gu) all exist and are live
    - archive_url_template pattern /gu/fact-checks-gu/{category}/{page}
      is correct for listing pages
    - article pages use literal English '## Claim' / '## Fact' /
      '## Verification' headings (even though the surrounding page is in
      Gujarati) and a 'RESULT' label followed by the rating -- the
      html_fallback parser now targets these landmarks directly instead of
      guessing a generic first-paragraph heuristic
    - could NOT confirm whether ClaimReview JSON-LD is present in the raw
      HTML (the fetch tool used strips <script> tags), so the JSON-LD path
      is still unverified -- likely still needed for articles where the
      landmark-based fallback misses

  NOT YET CHECKED: newschecker.in/mr (assumed same theme as gu, not spot
  checked) and both Fact Crescendo editions (structure could differ
  entirely -- inspect a sample page there before trusting the fallback).

Before a full run:
  1. Run with --max-pages 1 --lang gu first, look at the printed counts.
  2. If `articles found on listing page` is 0, the archive URL pattern
     below (ARCHIVE_URL_TEMPLATE) has probably changed -- open the site in
     a browser, find an archive/category page, and update the template.
  3. If `ClaimReview JSON-LD found` is consistently 0 but articles ARE
     being found, check a few `html_fallback` rows for empty claim_text --
     if that happens often, inspect an article's raw HTML and adjust the
     landmark text in parse_html_fallback().

This mirrors the same style as your existing datacoll.py / factcheck_scraper.py:
incremental CSV writes with flush, exponential backoff on failures, and a
polite delay between requests.

USAGE
-----
    pip install requests beautifulsoup4 --break-system-packages
    python regional_edition_scraper.py --site newschecker --lang gu --max-pages 50
    python regional_edition_scraper.py --site newschecker --lang mr --max-pages 50
"""
import argparse
import csv
import json
import re
import sys
import time
import urllib.robotparser
from dataclasses import dataclass, fields
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

USER_AGENT = "SakshyaResearchBot/1.0 (academic fact-check dataset project; contact: cse24044@iiitkalyani.ac.in)"

# ---------------------------------------------------------------------------
# Site configuration -- add new outlets here.
# `archive_url_template` must accept {page} and produce a listing page whose
# HTML contains links to individual fact-check articles.
# `article_link_pattern` filters which <a href> values on that listing page
# count as article links (avoids picking up nav/footer links).
# ---------------------------------------------------------------------------
SITE_CONFIGS = {
    "newschecker": {
        "gu": {
            "base_url": "https://newschecker.in",
            # Confirmed live pattern for category-page pagination, e.g.:
            #   https://newschecker.in/gu/fact-checks-gu/crime-gu/1
            # We rotate through the known category slugs seen on the site.
            "categories": [
                "fact-checks-gu", "crime-gu", "news-gu", "politics-gu",
                "religion-gu", "science-and-technology-gu", "viral-gu",
                "health-and-wellness-gu", "daily-reads-gujarati",
            ],
            "archive_url_template": "https://newschecker.in/gu/fact-checks-gu/{category}/{page}",
            "article_link_pattern": re.compile(r"/gu/fact-checks-gu/"),
        },
        "mr": {
            "base_url": "https://newschecker.in",
            "categories": [
                "fact-checks-mr", "crime-mr", "news-mr", "politics-mr",
                "religion-mr", "science-and-technology-mr", "viral-mr",
                "health-and-wellness-mr",
            ],
            "archive_url_template": "https://newschecker.in/mr/fact-checks-mr/{category}/{page}",
            "article_link_pattern": re.compile(r"/mr/fact-checks-mr/"),
        },
    },
    "factcrescendo": {
        "mr": {
            "base_url": "https://marathi.factcrescendo.com",
            "categories": ["factcheck"],
            "archive_url_template": "https://marathi.factcrescendo.com/factcheck/page/{page}/",
            "article_link_pattern": re.compile(r"marathi\.factcrescendo\.com/"),
        },
        "gu": {
            # UNCONFIRMED subdomain -- verify this resolves before using;
            # marathi.factcrescendo.com is confirmed, gujarati.factcrescendo.com
            # is inferred from the same naming pattern but was not directly checked.
            "base_url": "https://gujarati.factcrescendo.com",
            "categories": ["factcheck"],
            "archive_url_template": "https://gujarati.factcrescendo.com/factcheck/page/{page}/",
            "article_link_pattern": re.compile(r"gujarati\.factcrescendo\.com/"),
        },
    },
}

LANG_NAMES = {"gu": "Gujarati", "mr": "Marathi"}


@dataclass
class Claim:
    claim_text: str = ""
    claimant: str = ""
    claim_date: str = ""
    review_date: str = ""
    rating: str = ""
    publisher_domain: str = ""
    review_title: str = ""
    review_url: str = ""
    language: str = ""
    language_name: str = ""
    data_source: str = ""
    extraction_method: str = ""  # "claimreview_jsonld" or "html_fallback"


CSV_FIELDS = [f.name for f in fields(Claim)]


# ---------------------------------------------------------------------------
# Networking helpers
# ---------------------------------------------------------------------------
def check_robots_allowed(base_url, timeout=10):
    """Fetch and parse robots.txt with an explicit timeout. NOTE: the
    original version used urllib.robotparser's rp.read(), which has NO
    timeout -- if that request hangs (slow network, proxy/firewall), the
    whole script blocks silently forever with zero output. This version
    fetches the text via requests (which respects `timeout`) and feeds it
    to RobotFileParser manually."""
    robots_url = urljoin(base_url, "/robots.txt")
    rp = urllib.robotparser.RobotFileParser()
    try:
        resp = requests.get(robots_url, headers={"User-Agent": USER_AGENT}, timeout=timeout)
        if resp.status_code == 200:
            rp.parse(resp.text.splitlines())
        else:
            print(f"robots.txt returned {resp.status_code} for {base_url}; proceeding cautiously.")
            return True
        allowed = rp.can_fetch(USER_AGENT, base_url + "/")
        print(f"robots.txt check for {base_url}: {'ALLOWED' if allowed else 'DISALLOWED'}")
        return allowed
    except requests.RequestException as e:
        print(f"Could not read robots.txt for {base_url} ({e}); proceeding cautiously.")
        return True


def fetch(url, session, max_retries=4, base_delay=2.0):
    """GET with exponential backoff, same pattern as your existing scraper."""
    for attempt in range(max_retries):
        try:
            resp = session.get(url, headers={"User-Agent": USER_AGENT}, timeout=20)
            if resp.status_code == 200:
                return resp
            if resp.status_code in (429, 503):
                wait = base_delay * (2 ** attempt)
                print(f"  [{resp.status_code}] retrying {url} in {wait:.0f}s...")
                time.sleep(wait)
                continue
            print(f"  [{resp.status_code}] giving up on {url}")
            return None
        except requests.RequestException as e:
            wait = base_delay * (2 ** attempt)
            print(f"  [error: {e}] retrying {url} in {wait:.0f}s...")
            time.sleep(wait)
    return None


# ---------------------------------------------------------------------------
# Listing page -> article URLs
# ---------------------------------------------------------------------------
def extract_article_links(html, base_url, pattern):
    soup = BeautifulSoup(html, "html.parser")
    links = set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        full = urljoin(base_url, href)
        if pattern.search(full):
            # crude filter: skip category/pagination links themselves
            if not re.search(r"/\d+/?$", full):
                links.add(full.split("?")[0].split("#")[0])
    return links


# ---------------------------------------------------------------------------
# Article page -> Claim
# ---------------------------------------------------------------------------
def extract_claimreview_jsonld(soup):
    """Look for schema.org/ClaimReview JSON-LD. Returns dict or None."""
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string)
        except (TypeError, json.JSONDecodeError):
            continue
        candidates = data if isinstance(data, list) else [data]
        # Some sites nest it inside "@graph"
        expanded = []
        for c in candidates:
            if isinstance(c, dict) and "@graph" in c:
                expanded.extend(c["@graph"])
            else:
                expanded.append(c)
        for item in expanded:
            if isinstance(item, dict) and item.get("@type") == "ClaimReview":
                return item
    return None


def parse_claimreview(cr, url):
    claim_text = cr.get("claimReviewed", "")
    item_reviewed = cr.get("itemReviewed", {}) or {}
    author = item_reviewed.get("author", {}) or {}
    claimant = author.get("name", "") if isinstance(author, dict) else ""

    rating_obj = cr.get("reviewRating", {}) or {}
    rating = rating_obj.get("alternateName") or rating_obj.get("ratingValue") or ""

    claim_date = item_reviewed.get("datePublished", "") or ""
    review_date = cr.get("datePublished", "") or ""

    return Claim(
        claim_text=claim_text,
        claimant=claimant,
        claim_date=claim_date,
        review_date=review_date,
        rating=str(rating),
        review_url=url,
        extraction_method="claimreview_jsonld",
    )


def _find_labeled_paragraph(soup, label):
    """CONFIRMED against real raw HTML (Jul 2026): 'Claim' and 'Fact' each
    live as the sole text content of an <h2> (inside a colored div wrapper),
    immediately followed by an <img> icon then a <p class="parsed ..."> that
    holds the actual claim/fact text. We match on the exact text NODE
    (not tag.get_text(), which can silently fail to match if the tag has
    any other nested content) and then take the first <p> sibling after it."""
    for node in soup.find_all(string=re.compile(rf"^\s*{re.escape(label)}\s*$")):
        heading = node.parent
        if heading is None:
            continue
        for sib in heading.find_next_siblings():
            if sib.name == "p":
                text = sib.get_text(strip=True)
                if text:
                    return text
    return ""


def _find_rating_near_result_label(soup):
    """CONFIRMED against real raw HTML (Jul 2026): the verdict text (e.g.
    'Altered Photo/Video') lives in a sibling <div> immediately after a
    <span> whose sole text content is 'RESULT'. This is TEMPLATE A (the
    colored-box article layout) only -- see _find_rating_inline_result_heading
    for TEMPLATE B."""
    for node in soup.find_all(string=re.compile(r"^\s*RESULT\s*$")):
        parent = node.parent
        if parent is None:
            continue
        for sib in parent.find_next_siblings():
            text = sib.get_text(strip=True)
            if text:
                return text
    return ""


BOILERPLATE_MARKERS = [
    "Newchecker.in is an independent fact-checking initiative",
    "We welcome our readers to send us claims",
]


def _is_boilerplate_text(text):
    return any(marker in text for marker in BOILERPLATE_MARKERS)


def _find_claim_fact_inline(soup):
    """TEMPLATE B (older WordPress-style articles -- confirmed Jul 2026 via
    a real article, e.g. fact-check-ritu-raj-hacked-google-and-got-3-cr-job):
    'Claim' and 'Fact' are NOT separate headings/boxes like template A. They
    are inline <strong> labels sharing a single
    <p class="is-style-info wp-block-paragraph"> tag, separated by a <br>,
    e.g.:
        <p class="is-style-info wp-block-paragraph">
          <strong>Claim &#8211;</strong> <the claim text><br>
          <strong>Fact &#8211; </strong> <the fact/verdict text>
        </p>
    The old _find_labeled_paragraph() can never match this because 'Claim'
    is never the sole text of a node (it's 'Claim \u2013' inside <strong>,
    inline with surrounding text) -- that mismatch is exactly what caused
    real fact-checks using this template to fall through to the boilerplate
    last-resort fallback and get collected as garbage."""
    for p in soup.find_all("p", class_="is-style-info"):
        for strong in p.find_all("strong"):
            label = strong.get_text(strip=True).rstrip("\u2013-: ").strip().lower()
            if label != "claim":
                continue
            parts = []
            for sib in strong.next_siblings:
                if getattr(sib, "name", None) in ("br", "strong"):
                    break
                parts.append(sib if isinstance(sib, str) else sib.get_text())
            claim_text = "".join(parts).strip()
            if claim_text:
                return claim_text
    return ""


def _find_rating_inline_result_heading(soup):
    """TEMPLATE B: the verdict is fused into the same <h2> as the word
    'Result', e.g. <h2><strong>Result: </strong>Partly False</h2> -- there's
    no separate sibling element to look at like template A's <span>RESULT
    </span> landmark, so this matches the heading's full text directly."""
    for h2 in soup.find_all("h2"):
        text = h2.get_text(strip=True)
        m = re.match(r"^Result\s*:?\s*(.+)$", text, re.IGNORECASE)
        if m and m.group(1).strip():
            return m.group(1).strip()
    return ""


def _find_date_near_top(soup):
    """Article pages show a plain 'Mon DD, YYYY' date near the top of the
    body (e.g. 'Aug 12, 2025'), outside any <time> tag. IMPORTANT:
    soup.get_text() with no separator glues adjacent block elements
    together with zero whitespace (e.g. 'PoliticsAug 12, 2025Claim'),
    which breaks \\b word-boundary matching -- must pass separator=' '."""
    text = soup.get_text(separator=" ")
    m = re.search(r"\b[A-Z][a-z]{2} \d{1,2}, \d{4}\b", text)
    return m.group(0) if m else ""


def parse_html_fallback(soup, url):
    """This site has NO ClaimReview JSON-LD at all (confirmed absent on a
    real article, Jul 2026), so this is the ONLY extraction path, not a
    true fallback. Targets the site's real 'Claim'/'Fact'/'RESULT' text
    landmarks (confirmed via raw HTML inspection) rather than guessed CSS
    classes, which change across theme updates more often than plain
    landmark text does. NOT yet verified against Marathi Newschecker or
    either Fact Crescendo edition -- if claim_text comes back empty there,
    run debug_inspect_article.py against a sample page from that site."""
    title_tag = soup.find("h1")
    title = title_tag.get_text(strip=True) if title_tag else ""

    date = ""
    time_tag = soup.find("time")
    if time_tag and time_tag.has_attr("datetime"):
        date = time_tag["datetime"]
    else:
        meta_date = soup.find("meta", {"property": "article:published_time"})
        if meta_date:
            date = meta_date.get("content", "")
    if not date:
        date = _find_date_near_top(soup)

    # TEMPLATE A first (colored Claim/Fact box), then TEMPLATE B (inline
    # <strong>Claim -</strong> label in a single paragraph). Only after
    # BOTH known templates miss do we fall back to a generic guess -- and
    # that guess now explicitly skips the boilerplate "About Us" paragraph,
    # which is what was silently getting collected as claim_text before.
    claim_text = _find_labeled_paragraph(soup, "Claim")
    if not claim_text:
        claim_text = _find_claim_fact_inline(soup)
    if not claim_text:
        for p in soup.find_all("p"):
            text = p.get_text(strip=True)
            if len(text) > 40 and not _is_boilerplate_text(text):
                claim_text = text
                break

    rating = _find_rating_near_result_label(soup)
    if not rating:
        rating = _find_rating_inline_result_heading(soup)

    return Claim(
        claim_text=claim_text,
        review_title=title,
        review_date=date,
        rating=rating,
        review_url=url,
        extraction_method="html_fallback",
    )


def scrape_article(url, session, lang, data_source):
    resp = fetch(url, session)
    if resp is None:
        return None
    soup = BeautifulSoup(resp.text, "html.parser")

    cr = extract_claimreview_jsonld(soup)
    claim = parse_claimreview(cr, url) if cr else parse_html_fallback(soup, url)

    claim.language = lang
    claim.language_name = LANG_NAMES[lang]
    claim.publisher_domain = urlparse(url).netloc
    claim.data_source = data_source
    return claim


# ---------------------------------------------------------------------------
# Main crawl loop
# ---------------------------------------------------------------------------
SCRIPT_VERSION = "TEMPLATE_B_FIX_2026-07-16"


def run(site, lang, max_pages, delay, out_path):
    print(f"### SCRIPT_VERSION = {SCRIPT_VERSION} ### "
          f"(if you don't see this exact string, you're running the wrong "
          f"file -- stop and re-check)")
    config = SITE_CONFIGS[site][lang]
    base_url = config["base_url"]

    if not check_robots_allowed(base_url):
        print("robots.txt disallows this bot for this site -- stopping. "
              "Consider contacting the outlet directly for a data-sharing "
              "arrangement instead.")
        return

    session = requests.Session()
    seen_articles = set()
    rows_written = 0

    write_header = True
    with open(out_path, "a", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        if write_header and f.tell() == 0:
            writer.writeheader()

        for category in config["categories"]:
            print(f"\n=== Category: {category} ===")
            empty_pages_in_a_row = 0

            for page in range(1, max_pages + 1):
                listing_url = config["archive_url_template"].format(category=category, page=page)
                resp = fetch(listing_url, session)
                if resp is None:
                    print(f"  page {page}: fetch failed, skipping rest of this category")
                    break

                links = extract_article_links(resp.text, base_url, config["article_link_pattern"])
                new_links = links - seen_articles
                print(f"  page {page}: {len(links)} article links found on listing page "
                      f"({len(new_links)} new)")

                if len(links) == 0:
                    empty_pages_in_a_row += 1
                    if empty_pages_in_a_row >= 2:
                        print("  two empty pages in a row -- assuming end of category, moving on")
                        break
                else:
                    empty_pages_in_a_row = 0

                for article_url in sorted(new_links):
                    seen_articles.add(article_url)
                    claim = scrape_article(article_url, session, lang, data_source=f"{site}_scrape")
                    if claim and claim.claim_text:
                        writer.writerow(claim.__dict__)
                        f.flush()
                        rows_written += 1
                        method = claim.extraction_method
                        print(f"    + [{method}] {claim.claim_text[:70]!r}")
                    time.sleep(delay)

                time.sleep(delay)

    print(f"\nDone. {rows_written} claims written to {out_path}")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--site", choices=SITE_CONFIGS.keys(), required=True)
    parser.add_argument("--lang", choices=["gu", "mr"], required=True)
    parser.add_argument("--max-pages", type=int, default=20, help="Max pages per category to walk")
    parser.add_argument("--delay", type=float, default=1.5, help="Seconds between requests (be polite)")
    parser.add_argument("--out", default=None, help="Output CSV path")
    args = parser.parse_args()

    if args.lang not in SITE_CONFIGS[args.site]:
        print(f"Site '{args.site}' has no config for language '{args.lang}' in this script yet.")
        sys.exit(1)

    out_path = args.out or f"{args.site}_{args.lang}_claims.csv"
    run(args.site, args.lang, args.max_pages, args.delay, out_path)


if __name__ == "__main__":
    main()