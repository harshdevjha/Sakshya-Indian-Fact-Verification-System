"""
split_scraper_output_by_language.py

Run this AFTER factcheck_scraper.py. Takes its output CSV
(factcheck_claims_final.csv by default) and splits it into three
separate files -- one per language -- matching this schema:

    query, claim_text, claimant, claim_date,
    publisher_name, publisher_site, review_title, review_url,
    review_date, rating, language

Note on column mapping: factcheck_scraper.py's own output columns are
    claim_text, claimant, claim_date, publisher_name, publisher_site,
    review_title, review_url, review_date, rating, language, matched_query
(no separate query column -- just matched_query). This script renames
matched_query -> query. (query_lang was dropped -- it was always blank
since the scraper doesn't track which source a query came from.)

Usage:
    python split_scraper_output_by_language.py --input factcheck_claims_final.csv
"""

import argparse
import csv

TARGET_SCHEMA = [
    "query", "claim_text", "claimant", "claim_date",
    "publisher_name", "publisher_site", "review_title", "review_url",
    "review_date", "rating", "language",
]

LANG_TO_FILENAME = {
    "hi": "hindi_claims1.csv",
    "gu": "gujarati_claims1.csv",
    "mr": "marathi_claims1.csv",
}


def project_to_target_schema(row: dict) -> dict:
    return {
        "query": row.get("matched_query", ""),
        "claim_text": row.get("claim_text", ""),
        "claimant": row.get("claimant", ""),
        "claim_date": row.get("claim_date", ""),
        "publisher_name": row.get("publisher_name", ""),
        "publisher_site": row.get("publisher_site", ""),
        "review_title": row.get("review_title", ""),
        "review_url": row.get("review_url", ""),
        "review_date": row.get("review_date", ""),
        "rating": row.get("rating", ""),
        "language": row.get("language", ""),
    }


def split(input_path: str, outdir: str):
    writers = {}
    files = {}
    counts = {lang: 0 for lang in LANG_TO_FILENAME}
    total_in = 0
    total_kept = 0

    try:
        for lang, filename in LANG_TO_FILENAME.items():
            path = f"{outdir.rstrip('/')}/{filename}" if outdir else filename
            f = open(path, "w", newline="", encoding="utf-8")
            files[lang] = f
            writers[lang] = csv.DictWriter(f, fieldnames=TARGET_SCHEMA)
            writers[lang].writeheader()

        with open(input_path, "r", encoding="utf-8", newline="") as in_f:
            reader = csv.DictReader(in_f)
            for row in reader:
                total_in += 1
                lang = row.get("language", "")
                if lang not in writers:
                    continue
                writers[lang].writerow(project_to_target_schema(row))
                counts[lang] += 1
                total_kept += 1

    finally:
        for f in files.values():
            f.close()

    print(f"Read {total_in} rows from {input_path}")
    print(f"Kept {total_kept} rows across hi/gu/mr, dropped {total_in - total_kept} other-language rows\n")
    for lang, filename in LANG_TO_FILENAME.items():
        print(f"  {filename}: {counts[lang]} rows")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--input", default="factcheck_claims_final.csv",
                         help="Path to factcheck_scraper.py's output CSV")
    parser.add_argument("--outdir", default=".",
                         help="Where to write hindi_claims.csv / gujarati_claims.csv / marathi_claims.csv")
    args = parser.parse_args()
    split(args.input, args.outdir)


if __name__ == "__main__":
    main()
