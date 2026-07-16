"""
Quick diagnostic: fetches ONE real article page and prints the raw HTML
around any element whose text is exactly "Claim", "Fact", "RESULT", etc.,
plus checks for ClaimReview JSON-LD. Run this locally and paste the output
back so the real tag/class structure can be matched precisely instead of
guessed.

Usage:
    python debug_inspect_article.py
"""
import re
import requests
from bs4 import BeautifulSoup

URL = "https://newschecker.in/gu/fact-checks-gu/fact-checks-gu/fact-check-ritu-raj-hacked-google-and-got-3-cr-job"
USER_AGENT = "SakshyaResearchBot/1.0 (academic fact-check dataset project; contact: cse24044@iiitkalyani.ac.in)"

resp = requests.get(URL, headers={"User-Agent": USER_AGENT}, timeout=20)
print(f"status: {resp.status_code}, length: {len(resp.text)} chars\n")

soup = BeautifulSoup(resp.text, "html.parser")

# 1. Check for ClaimReview JSON-LD
scripts = soup.find_all("script", type="application/ld+json")
print(f"Found {len(scripts)} JSON-LD <script> blocks")
for i, s in enumerate(scripts):
    snippet = (s.string or "")[:300]
    print(f"  [{i}] {snippet!r}\n")

# 2. Find elements whose exact text is "Claim", "Fact", "RESULT", "Verification"
print("=" * 70)
print("Elements matching landmark text (showing tag + up to 2 parents + next 3 siblings):")
for label in ["Claim", "Fact", "RESULT", "Verification", "Conlcusion", "Conclusion"]:
    matches = soup.find_all(string=re.compile(rf"^\s*{re.escape(label)}\s*$"))
    print(f"\n--- '{label}': {len(matches)} exact text matches ---")
    for m in matches[:2]:
        parent = m.parent
        print(f"  parent tag: <{parent.name} class={parent.get('class')}>")
        grandparent = parent.parent
        if grandparent:
            print(f"  grandparent tag: <{grandparent.name} class={grandparent.get('class')}>")
        # show next 3 sibling elements after the parent
        sib_count = 0
        for sib in parent.find_next_siblings():
            if sib_count >= 3:
                break
            text_preview = sib.get_text(strip=True)[:80]
            print(f"    next sibling: <{sib.name} class={sib.get('class')}> text={text_preview!r}")
            sib_count += 1

print("\n" + "=" * 70)
print("Full <body> saved to article_raw.html for manual inspection")
with open("article_raw.html", "w", encoding="utf-8") as f:
    f.write(resp.text)
