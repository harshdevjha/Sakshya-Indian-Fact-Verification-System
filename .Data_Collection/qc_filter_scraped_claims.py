"""
qc_filter_scraped_claims.py
============================
Run this AFTER a scraper run (e.g. newschecker_gu_claims.csv exists) to catch
rows where extraction fell back to page boilerplate instead of a real claim
-- most likely on article types that don't use the single Claim/Fact verdict
card (e.g. "Weekly Wrap" round-ups, "Explainer" pieces).

Usage:
    python qc_filter_scraped_claims.py newschecker_gu_claims.csv
"""
import sys
import pandas as pd

BOILERPLATE_MARKERS = [
    "Newchecker.in is an independent fact-checking initiative",
    "We welcome our readers to send us claims",
]

def is_boilerplate(text):
    if not isinstance(text, str):
        return True
    return any(marker in text for marker in BOILERPLATE_MARKERS)

def main(path):
    df = pd.read_csv(path)
    print(f"Loaded {len(df)} rows from {path}")

    bad_mask = df["claim_text"].apply(is_boilerplate)
    n_bad = bad_mask.sum()
    print(f"\nFlagged {n_bad} boilerplate rows ({n_bad/len(df)*100:.1f}%)")

    if n_bad > 0:
        print("\nURLs that fell back to boilerplate (inspect these article "
              "types -- likely round-ups/explainers, not single-claim posts):")
        for url in df.loc[bad_mask, "review_url"]:
            print(f"  {url}")

    clean = df.loc[~bad_mask].copy()
    out_path = path.replace(".csv", "_clean.csv")
    clean.to_csv(out_path, index=False, encoding="utf-8-sig")
    print(f"\nWrote {len(clean)} clean rows to {out_path}")
    print(f"(Removed {n_bad} boilerplate rows -- review the flagged URLs "
          f"above; if they're all round-up/explainer articles, dropping them "
          f"is correct. If any are real fact-checks, the layout for that "
          f"template needs its own selector.)")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python qc_filter_scraped_claims.py <scraped_claims.csv>")
        sys.exit(1)
    main(sys.argv[1])
