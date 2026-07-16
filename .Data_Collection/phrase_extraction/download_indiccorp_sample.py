"""
download_indiccorp_sample.py

Downloads a manageable local text sample from AI4Bharat's IndicCorp v2 for
Hindi, Gujarati, and Marathi, without pulling the full 275GB dataset.

Uses streaming=True so it reads records on the fly and stops once it has
written `--max_lines` lines per language, instead of downloading the whole
per-language shard.

NOTE: This needs internet access to huggingface.co. Run it on your own
machine (not in a sandbox with restricted network access).

Install once:
    pip install datasets --break-system-packages    (or without the flag,
    depending on your environment)

Usage:
    python download_indiccorp_sample.py --max_lines 300000 --outdir ./corpus_raw

Output:
    ./corpus_raw/hi.txt
    ./corpus_raw/gu.txt
    ./corpus_raw/mr.txt

These are exactly the files corpus_phrase_extractor.py expects as --input.
"""

import argparse
import os

from datasets import load_dataset

# IndicCorpV2 split names -> our short language codes
LANG_SPLITS = {
    "hi": "hin_Deva",
    "gu": "guj_Gujr",
    "mr": "mar_Deva",
}


def download_language(lang_code: str, split_name: str, max_lines: int, outdir: str):
    print(f"[{lang_code}] streaming IndicCorpV2 split '{split_name}' ...")
    ds = load_dataset(
        "ai4bharat/IndicCorpV2",
        "indiccorp_v2",
        split=split_name,
        streaming=True,
    )

    os.makedirs(outdir, exist_ok=True)
    out_path = os.path.join(outdir, f"{lang_code}.txt")

    count = 0
    with open(out_path, "w", encoding="utf-8") as f:
        for row in ds:
            text = row.get("text", "").strip()
            if not text:
                continue
            f.write(text + "\n")
            count += 1
            if count % 20000 == 0:
                print(f"[{lang_code}] {count} lines written ...")
            if count >= max_lines:
                break

    print(f"[{lang_code}] done: {count} lines -> {out_path}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--max_lines", type=int, default=300000, help="Lines to keep per language")
    parser.add_argument("--outdir", default="./corpus_raw", help="Where to save the text files")
    parser.add_argument(
        "--langs",
        nargs="+",
        default=["hi", "gu", "mr"],
        choices=list(LANG_SPLITS.keys()),
        help="Which languages to download",
    )
    args = parser.parse_args()

    for lang in args.langs:
        download_language(lang, LANG_SPLITS[lang], args.max_lines, args.outdir)


if __name__ == "__main__":
    main()
