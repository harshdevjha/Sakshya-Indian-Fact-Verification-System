# Sakshya — Indian Fact Verification System

Sakshya is a data collection framework for building a multilingual Indic
fact-checking dataset covering **Hindi, Gujarati, Marathi, and English**.
The end goal is a claim-verification dataset that isn't skewed toward
English/Hindi the way most existing Indic misinformation datasets are —
Gujarati and Marathi are first-class targets here, not an afterthought.

This README documents every file in the repo, how the pieces fit together,
and the exact commands to reproduce the pipeline end to end.

---

## Why this repo looks the way it does

There are **two independent collection strategies**, because they fail in
different ways for different languages:

1. **Query-seeded API search** (`FactCheck_Scraper/`) — search Google's
   Fact Check Tools API with a list of query terms. Fast and broad, but
   fundamentally bottlenecked by the query list: if a query is
   English/Hindi-biased, the results will be too, no matter how many
   queries you run. This is why Gujarati and Marathi came back
   under-represented early on.
2. **Full-archive scraping** (`Regional_edition_scraper/`) — walk a
   Gujarati/Marathi fact-checking outlet's own article archive directly,
   claim by claim, with no query bottleneck at all. Slower and more
   fragile (HTML layouts change, sites differ), but it's what actually
   closed the language gap — see [Current dataset size](#current-dataset-size-what-actually-worked)
   below.

A third stage (`Merged_Dataset_X-Fact/`) combines both of the above with an
existing external dataset (X-Fact 2021) and de-duplicates everything into
one final file per language.

---

## Repository structure

```
Sakshya-Indian-Fact-Verification-System/
├── README.md
├── .gitignore
└── .Data_Collection/
    ├── FactCheck_Scraper/
    │   ├── factcheck_scraper.py
    │   ├── datacoll.py                      (legacy duplicate — see notes)
    │   ├── data_filter.py
    │   ├── filter.ipynb
    │   ├── factcheck_claims_final.csv        
    │   ├── hindi_claims(1).csv
    │   ├── gujarati_claims.csv
    │   ├── marathi_claims.csv
    │   └── phrase_extraction/
    │       ├── download_indiccorp_sample.py
    │       ├── corpus_phrase_extractor.py
    │       └── phrases_output/
    │           ├── hi_frequent_ngrams.csv / hi_yake_phrases.csv
    │           ├── gu_frequent_ngrams.csv / gu_yake_phrases.csv
    │           └── mr_frequent_ngrams.csv / mr_yake_phrases.csv
    ├── Regional_edition_scraper/
    │   ├── regional_edition_scraper.py
    │   ├── debug_inspect_article.py
    │   ├── qc_filter_scraped_claims.py
    │   ├── newschecker_gu_claims_v1.csv
    │   └── newschecker_mr_claims_v1.csv
    └── Merged_Dataset_X-Fact/
        ├── hindi_claims_merged.csv
        ├── gujarati_claims_merged.csv
        ├── marathi_claims_merged.csv
        └── merge_summary_v2.csv
```

---

## File-by-file reference

### `FactCheck_Scraper/` — query-seeded Google Fact Check API collection

**`factcheck_scraper.py`** — the main, current collector. Queries the
[Google Fact Check Tools API](https://factchecktools.googleapis.com) using
two combined query sources:
- a large hardcoded list of seed terms (schemes, festivals, public
  figures, states, scams, etc., in Hindi/Gujarati/Marathi/English)
- phrases pulled from `phrase_extraction/phrases_output/*.csv` (see
  below), which are extracted directly from real Hindi/Gujarati/Marathi
  corpus text rather than hand-picked — this is what corrects the
  English/Hindi bias in the hardcoded list alone.

  Reads the API key from the `FACTCHECK_API_KEY` environment variable
  (never hardcode it), retries on 429/5xx with exponential backoff,
  writes rows incrementally with `flush()` so a crash mid-run doesn't
  lose data, and resumes safely if you rerun it against an existing
  output file (skips URLs already collected).

  ```bash
  set FACTCHECK_API_KEY=your-key-here      # Windows
  export FACTCHECK_API_KEY=your-key-here   # macOS/Linux
  python factcheck_scraper.py --top-per-file 100 --output factcheck_claims_final.csv
  ```

  Output columns: `claim_text, claimant, claim_date, publisher_name,
  publisher_site, review_title, review_url, review_date, rating,
  language, matched_query`.

**`datacoll.py`** — an older, byte-for-byte-earlier version of the
scraper: hardcoded API key placeholder, no retry/backoff, no incremental
writes, no corpus-derived queries. Kept in the repo but superseded by
`factcheck_scraper.py`. Safe to delete once you've confirmed you don't
need to diff against it.

**`data_filter.py`** — run *after* `factcheck_scraper.py`. Splits its
output CSV into three separate per-language files (`hindi_claims1.csv`,
`gujarati_claims1.csv`, `marathi_claims1.csv`), renaming `matched_query`
→ `query` and dropping every row whose `language` isn't `hi`/`gu`/`mr`.

  ```bash
  python data_filter.py --input factcheck_claims_final.csv
  ```

**`filter.ipynb`** — a minimal, ad-hoc notebook: loads
`hindi_claims(1).csv` with pandas and drops rows with any missing
values (`df.dropna()`). Useful as a quick sanity-check scratchpad, not a
pipeline stage.

**`factcheck_claims_final.csv`, `hindi_claims(1).csv`,
`gujarati_claims.csv`, `marathi_claims.csv`** — data outputs from the
scraper + splitter. See [Known Issues](#known-issues) — the combined file
has a real corruption bug.

**`phrase_extraction/download_indiccorp_sample.py`** — streams a sample
(default 300k lines/language) from
[AI4Bharat's IndicCorpV2](https://huggingface.co/datasets/ai4bharat/IndicCorpV2)
for Hindi (`hin_Deva`), Gujarati (`guj_Gujr`), and Marathi (`mar_Deva`)
without downloading the full ~275GB dataset. Needs internet access to
huggingface.co — run on your own machine, not a sandboxed environment.

  ```bash
  pip install datasets --break-system-packages
  python download_indiccorp_sample.py --max_lines 300000 --outdir ./corpus_raw --langs hi gu mr
  ```

**`phrase_extraction/corpus_phrase_extractor.py`** — takes the corpus
text from the step above and produces two ranked phrase lists per
language:
- `{lang}_frequent_ngrams.csv` — raw 1/2/3-gram frequency counts, using
  proper Indic-aware tokenization (`indic-nlp-library`) and
  language-specific stopword lists (sourced from stopwords-iso, extended
  with inflections observed to dominate real output).
- `{lang}_yake_phrases.csv` — [YAKE](https://github.com/LIAAD/yake)
  keyword extraction (position/casing/co-occurrence-aware), sampled and
  batched since YAKE isn't built for corpus-scale input.

  ```bash
  pip install yake indic-nlp-library --break-system-packages
  python corpus_phrase_extractor.py \
      --input hi:./corpus_raw/hi.txt --input gu:./corpus_raw/gu.txt --input mr:./corpus_raw/mr.txt \
      --top 200 --outdir ./phrases_output
  ```

  **Note:** the top-ranked rows in both outputs skew toward short function
  words that survived the stopword filters (e.g. Gujarati "સાથે"/with).
  `factcheck_scraper.py` compensates by preferring multi-word phrases over
  short single tokens when building its query list.

**`phrase_extraction/phrases_output/*.csv`** — the generated phrase
lists, ~200 rows each, already checked into the repo (already used by
`factcheck_scraper.py` by default).

---

### `Regional_edition_scraper/` — full-archive scraping (the part that actually fixed the imbalance)

**`regional_edition_scraper.py`** — walks a fact-checking outlet's own
article archive directly (currently configured for Newschecker's
Gujarati/Marathi editions, plus an unverified Fact Crescendo config), so
every claim the outlet has ever published gets collected — no query
bottleneck. For each article it first looks for structured
`schema.org/ClaimReview` JSON-LD (the same markup Google's own API reads);
if that's absent, it falls back to a landmark-based HTML parser that
targets two known article templates directly rather than guessing CSS
classes:
- **Template A** — a colored "Claim / Fact" box with a `RESULT` label
- **Template B** — inline `<strong>Claim –</strong>` / `<strong>Fact
  –</strong>` labels inside one paragraph, and a fused `Result:` heading

  Includes a `robots.txt` check before crawling (with an explicit
  timeout — the stdlib's own robots parser has none and can hang
  forever), exponential backoff on 429/503, incremental writes, and a
  polite delay between requests.

  ```bash
  pip install requests beautifulsoup4 --break-system-packages
  python regional_edition_scraper.py --site newschecker --lang gu --max-pages 50
  python regional_edition_scraper.py --site newschecker --lang mr --max-pages 50
  ```

  **Verification status (as of the last update to this script):** the
  Newschecker Gujarati config was spot-checked against a real article and
  confirmed live; the Fact Crescendo Gujarati subdomain in
  `SITE_CONFIGS` is inferred from a naming pattern, not directly
  confirmed — verify it resolves before relying on it. In practice, every
  row collected so far came through `html_fallback`, not the JSON-LD path
  — see `extraction_method` in the output files.

**`debug_inspect_article.py`** — a one-off diagnostic: fetches a single
article URL, prints any JSON-LD blocks found, and shows the HTML
structure around "Claim"/"Fact"/"RESULT"/"Verification" landmark text.
Use this against a new site/template before extending
`regional_edition_scraper.py`'s parsers.

  ```bash
  python debug_inspect_article.py
  ```

**`qc_filter_scraped_claims.py`** — run after a scraper pass to catch
rows where extraction fell back to page boilerplate ("Newschecker.in is
an independent fact-checking initiative...") instead of a real claim —
this happens on article types that don't use the standard single
claim/verdict template (round-ups, explainers). Flags and drops those
rows, writes a `_clean.csv` copy, and prints the flagged URLs so you can
check whether any of them are genuine misses that need their own
template handling.

  ```bash
  python qc_filter_scraped_claims.py newschecker_gu_claims.csv
  ```

**`newschecker_gu_claims_v1.csv` / `newschecker_mr_claims_v1.csv`** —
real output from a completed scraper run: **1,347 Gujarati claims** and
**1,381 Marathi claims**, all via `html_fallback` extraction. This single
run collected roughly **6–7× more Gujarati/Marathi claims than the entire
query-seeded API approach**, which is the strongest evidence in the repo
that the full-archive strategy was the right call for these two
languages.

---

### `Merged_Dataset_X-Fact/` — final merged datasets

**`hindi_claims_merged.csv`, `gujarati_claims_merged.csv`,
`marathi_claims_merged.csv`** — the final per-language files, each
combining an existing dataset (labeled `xfact_2021` in `data_source`)
with the Google Fact Check API scrape output, de-duplicated by
`review_url`. Schema (22 columns): the raw API fields plus derived ones —
`claim_date_parsed`, `claim_year`, `claim_month`, `publisher_domain`,
`rating_clean`, `language_name`, `claim_char_len`, `claim_word_len`,
`detected_script`, `has_claimant`, `data_source`.

  > Note: these files do **not** yet include the `Regional_edition_scraper`
  > output (`newschecker_gu/mr_claims_v1.csv`). Re-running the merge with
  > those included should substantially grow the Gujarati/Marathi totals
  > below.

**`merge_summary_v2.csv`** — the merge's own accounting of what changed:

| language | existing_rows (X-Fact) | api_rows_added | duplicates_removed | final_rows | growth |
|---|---|---|---|---|---|
| Hindi | 4,090 | 8,624 | 2,259 | 10,455 | +155.6% |
| Gujarati | 146 | 10 | 0 | 156 | +6.8% |
| Marathi | 161 | 273 | 62 | 372 | +131.1% |

This table is exactly why the regional-edition scraper exists: the API
only added **10** new Gujarati rows on top of the existing 146. The
Newschecker archive scrape alone (1,347 rows) dwarfs that.

---

### `filter_dataset_final.csv` (repo root, under `.Data_Collection/`)

A quality-control-filtered snapshot of `factcheck_claims_final.csv`
(2,619 unique rows, same 12-column schema, missing the `query_lang`
column). It's a subset produced at some earlier filtering pass — not the
authoritative final dataset (that's `Merged_Dataset_X-Fact/`).

---

## Known issues

**1. `FactCheck_Scraper/factcheck_claims_final.csv` has a real column-shift
bug — 74.6% of its rows are corrupted.**
124,413 of its 166,696 rows were written using an older 11-column schema
(no `query_lang` field) but are being read back against the current
12-column header. Every field after `query` lands one column left of
where it should, and the `language` column comes back empty for every
affected row. This is mechanically detectable (`language is None` after
CSV parsing flags it with certainty, not a guess) and repairable by
shifting those rows back into place before using this file for anything.
**Do not merge or train on this file as-is.**

**2. `.gitignore` doesn't actually exclude the large scraper output
anymore.** It lists `.Data_Collection/factcheck_claims_final.csv`, but the
file now lives at `.Data_Collection/FactCheck_Scraper/factcheck_claims_final.csv`
after the folder reorganization — the path no longer matches, so the
85MB+ file is being committed. Update the `.gitignore` entry to
`.Data_Collection/FactCheck_Scraper/factcheck_claims_final.csv` (or a
wildcard) if you don't want it tracked.

**3. `datacoll.py` is dead weight.** It's an earlier, superseded version
of `factcheck_scraper.py` (hardcoded API key placeholder, no retries, no
resume support). Safe to remove unless you specifically want the diff
history.

**4. Regional scraper site configs are partially unverified.** Per
`regional_edition_scraper.py`'s own docstring, the Fact Crescendo
Gujarati subdomain is inferred, not confirmed, and Fact Crescendo/Newschecker-Marathi
weren't spot-checked before the first run (though the Marathi run above
did succeed). Run with `--max-pages 1` first against any new site/lang
combination before a full crawl.

---

## Current dataset size (what actually worked)

| Source | Hindi | Gujarati | Marathi |
|---|---|---|---|
| Query-seeded Fact Check API (`gujarati_claims.csv` etc., current scraper run) | 12,978 | 201 | 431 |
| Full-archive scrape (`Regional_edition_scraper`) | — | 1,347 | 1,381 |
| Merged with X-Fact 2021 (`Merged_Dataset_X-Fact`, **excludes** regional scrape) | 10,455 | 156 | 372 |

The clear takeaway: for Gujarati and Marathi, the archive-walking
approach outperforms query-seeded API search by roughly an order of
magnitude. The next merge pass should fold `newschecker_gu/mr_claims_v1.csv`
into `Merged_Dataset_X-Fact/`.

---

## End-to-end pipeline

```bash
# 1. Corpus-derived query seeds (one-time, or re-run periodically)
cd .Data_Collection/FactCheck_Scraper/phrase_extraction
pip install datasets yake indic-nlp-library --break-system-packages
python download_indiccorp_sample.py --max_lines 300000 --outdir ./corpus_raw --langs hi gu mr
python corpus_phrase_extractor.py \
    --input hi:./corpus_raw/hi.txt --input gu:./corpus_raw/gu.txt --input mr:./corpus_raw/mr.txt \
    --top 200 --outdir ./phrases_output

# 2. Query-seeded API collection
cd ..
pip install requests pandas --break-system-packages
set FACTCHECK_API_KEY=your-key-here
python factcheck_scraper.py --top-per-file 100 --output factcheck_claims_final.csv
python data_filter.py --input factcheck_claims_final.csv

# 3. Full-archive scraping (Gujarati/Marathi)
cd ../Regional_edition_scraper
pip install requests beautifulsoup4 --break-system-packages
python regional_edition_scraper.py --site newschecker --lang gu --max-pages 50
python regional_edition_scraper.py --site newschecker --lang mr --max-pages 50
python qc_filter_scraped_claims.py newschecker_gu_claims_v1.csv
python qc_filter_scraped_claims.py newschecker_mr_claims_v1.csv

# 4. Merge everything into the final per-language datasets
#    (merge script not yet in this repo — combines Merged_Dataset_X-Fact's
#    existing merge with the Regional_edition_scraper output)
```

## Setup

1. Python 3.10+ recommended (Windows users hitting SSL errors on the
   IndicCorpV2 download: use a fresh conda env on 3.10, or patch
   `ssl.py`'s certificate loading).
2. `pip install requests pandas beautifulsoup4 datasets yake indic-nlp-library --break-system-packages`
3. Set `FACTCHECK_API_KEY` before running `factcheck_scraper.py` — never
   hardcode it in the script or commit it.
