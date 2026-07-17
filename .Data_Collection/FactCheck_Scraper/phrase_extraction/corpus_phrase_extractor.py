"""
corpus_phrase_extractor.py

Step 4 of the internship plan:
"Download any available large raw corpus for the corresponding language
and find the most frequent n-grams."

This script does TWO complementary things per language (hi, gu, mr, en):

  1. RAW FREQUENCY N-GRAMS
     Tokenizes text properly (Indic-aware, not naive whitespace split),
     strips stopwords/punctuation, and counts the most frequent
     1/2/3-grams. This is the literal "most frequent n-grams" ask.

  2. YAKE KEYWORD/PHRASE EXTRACTION
     Frequency alone over-ranks generic words ("सरकार", "है", "today").
     YAKE re-ranks phrases using position, casing, co-occurrence, and
     sentence spread, giving you more topic-like phrases -- exactly
     the kind of thing you'd want to feed into the Fact Check API as
     a search seed in step 2.

Output: for each language, a CSV of top-N phrases with both scores,
ready to be used as query seeds for factcheck_scraper.py.

USAGE
-----
    python corpus_phrase_extractor.py --input hi:/path/to/hindi_corpus.txt \
                                       --input gu:/path/to/gujarati_corpus.txt \
                                       --input mr:/path/to/marathi_corpus.txt \
                                       --top 200 \
                                       --outdir ./phrases_output

Each --input is "LANGCODE:path_to_text_file". The text file should be
plain UTF-8 text, one document/sentence per line (this is how corpora
like AI4Bharat IndicCorp, OSCAR, and CC-100 are normally distributed).

WHERE TO GET A RAW CORPUS (do this on your own machine -- this sandbox
can't reach huggingface.co):
  - AI4Bharat IndicCorp v2 (best coverage, has hi/gu/mr separately):
      https://huggingface.co/datasets/ai4bharat/IndicCorpV2
  - OSCAR (Common Crawl based, split by language):
      https://huggingface.co/datasets/oscar-corpus/OSCAR-2301
  - Wikipedia dumps (smaller, cleaner):
      https://dumps.wikimedia.org/  (e.g. hiwiki-latest-pages-articles.xml.bz2)

Install once:
    pip install yake indic-nlp-library
"""

import argparse
import csv
import os
import re
from collections import Counter
from typing import List, Tuple

import yake
from indicnlp.tokenize import indic_tokenize

# ---------------------------------------------------------------------------
# Language configuration
# ---------------------------------------------------------------------------

# indic_nlp language codes
INDIC_LANG_CODE = {
    "hi": "hi",
    "mr": "mr",
    "gu": "gu",
}

# YAKE has a bundled Hindi stopword list, but NOT Gujarati or Marathi.
# For those we supply a curated stopword set so frequency counts aren't
# dominated by function words (postpositions, pronouns, copulas).
# Stopword lists sourced from stopwords-iso (github.com/stopwords-iso), a
# widely-used, community-maintained collection -- NOT hand-guessed. Each
# list is supplemented with common passive/auxiliary verb inflections
# (e.g. Gujarati "કરવામાં"/"હતો", Marathi "યાંની"/"करण्यात") that were
# confirmed, by inspecting real IndicCorpV2 output, to otherwise dominate
# the top of the frequency/YAKE rankings without adding topical meaning.
GUJARATI_STOPWORDS = {'ઘણું', 'સૌથી', 'કરવું', 'એવી', 'કોણે', 'મૂક્યા', 'મળ્યો', 'મળ્યું', 'જી', 'બે', 'મી', 'આર', 'કરી', 'તારું', 'રૂ.', 'તો', 'નો', 'જણાવ્યું', 'ઊભું', 'હશો', 'તારામાં', 'આપી', 'ગયો', 'કરીએ', 'જોઈએ', 'તે', 'લેતા', 'એનો', 'જેટલું', 'પર', 'મા', 'જો', 'અને', 'જ', 'એને', 'થતાં', 'બહુ', 'એન', 'હતું', 'છું', 'એની', 'બાદ', 'કરાઈ', 'કરે', 'થાય', 'દરેક', 'રહ્યો', 'તમારા', 'માટે', 'કરવામાં', 'મૂકી', 'કોઈક', 'નહિ', 'થયું', 'કંઈક', 'છેક', 'કરાયા', 'હતી', 'પાસે', 'તને', 'આથી', 'પરંતુ', 'ને', 'પછી', 'કર્યું', 'છે', 'હતાં', 'આનું', 'એ', 'અહીં', 'થતી', 'રહે', 'હોવા', 'જેવી', 'તમે', 'માં', 'શું', 'તમને', 'કોણ', 'તેથી', 'તેના', 'રહ્યા', 'દ્વારા', 'કઈ', 'આપણને', 'ન', 'કયો', 'રીતે', 'ઝાઝું', 'રહ્યાં', 'ખૂબ', 'તેં', 'થતા', 'લેતું', 'હશે', 'છતાં', 'નહીં', 'આવી', 'જેવો', 'ઓછું', 'થવું', 'કરાયો', 'હતા', 'અમને', 'એમ', 'હોઈ', 'આપણું', 'તેનું', 'ફરીથી', 'થઇ', 'ક્યાં', 'ગયું', 'કાંઈ', 'ત્યાં', 'કરેલું', 'કે', 'અંદર', 'નહી', 'માત્ર', 'સુધી', 'કરતાં', 'છો', 'જ્યારે', 'તેમને', 'રહ્યું', 'બધા', 'થાઉં', 'રહેવું', 'આપણે', 'ફરી', 'એનાં', 'કોને', 'તમારું', 'જણાવ્યુ', 'રહી', 'થોડું', 'સરખું', 'શા', 'શકે', 'મને', 'મૂકવું', 'વગેરે', 'કર્યા', 'ગઈ', 'જાય', 'થયાં', 'નું', 'બહાર', 'પ્રત્યેક', 'નં', 'કર્યાં', 'હોઈશું', 'એવા', 'થઈએ', 'ની', 'હવે', 'અમારું', 'એવાં', 'હું', 'ક્યારે', 'તેને', 'થયા', 'આવે', 'કેવું', 'જ્યાં', 'નીચે', 'મારું', 'મેં', 'થતો', 'હતો', 'કયું', 'પાછળ', 'થયેલું', 'એવું', 'થતું', 'મૂક્યાં', 'હોય', 'જેવું', 'નથી', 'થી', 'ઊંચે', 'એનું', 'તેની', 'જેમ', 'ત્યારે', 'અંગે', 'વધુ', 'કર્યો', 'ગયા', 'અપાઈ', 'પોતાનું', 'બંને', 'આ', 'અથવા', 'થઈ', 'ઉભા', 'એના', 'સામે', 'તેણે', 'હો', 'થાઓ', 'આજે', 'તા', 'તેમ', 'ઉપર', 'લેવા', 'કોઈ', 'એવો', 'કેમ', 'જે', 'તેઓ', 'તેવું', 'જેને', 'તારાથી', 'અપાયું', 'પહેલાં', 'મૂક્યું', 'કરું', 'આગળ', 'આને', 'કેટલું', 'છ', 'છીએ', 'તેમનું', 'નં.', 'ફક્ત', 'બધું', 'કેવી', 'તું', 'હા', 'પણ', 'બની', 'તેવી', 'ગયાં', 'એક', 'થયો', 'ના', 'હોઈશ', 'કરાયું', 'અમે', 'રૂા'}

MARATHI_STOPWORDS = {'अनेक', 'केले', 'म्हणून', 'लाख', 'एका', 'आता', 'व्यकत', 'केली', 'हजार', 'होणार', 'ते', 'त्याना', 'डॉ', 'येथे', 'ता', 'होते', 'म्हणाले', 'येणार', 'त्यानी', 'व', 'म्हणजे', 'हा', 'करून', 'यानी', 'दिली', 'नाही', 'तरी', 'होत', 'सुरू', 'करण्यात', 'दिले', 'येत', 'जाणार', 'तर', 'का', 'राहील', 'काही', 'परयतन', 'आणि', 'आला', 'पण', 'येथील', 'तो', 'या', 'असे', 'गेल्या', 'असून', 'सागित्ले', 'आहे', 'तीन', 'असलयाचे', 'ही', 'याची', 'आले', 'याच्या', 'होती', 'मात्र', 'त्याची', 'घेऊन', 'सांगितले', 'त्या', 'टा', 'सांगितली', 'झाली', 'झालेल्या', 'अधिक', 'काय', 'निर्ण्य', 'असलेल्या', 'आली', 'त्याचा', 'व्यक्त', 'आहेत', 'म', 'मुबी', 'किवा', 'हे', 'न', 'कमी', 'अशी', 'जात', 'करणयात', 'की', 'आपल्या', 'झाले', 'एक', 'त्री', 'पम', 'पाटील', 'याना', 'होता', 'मी', 'झाला', 'यांनी', 'ती', 'दोन', 'काम', 'केला', 'त्यामुळे', 'म्हणाल्या', 'कोटी', 'त्याच्या', 'माहिती', 'सर्व', 'असा', 'याचा', 'आज', 'तसेच'}

HINDI_STOPWORDS = {'अपनी', 'मानो', 'उनको', 'तिन्हें', 'सारा', 'अपनि', 'वहिं', 'हुआ', 'अत', 'वगेरह', 'जिंहें', 'किस', 'दूसरे', 'गए', 'जेसा', 'गया', 'निचे', 'वर्ग', 'सकते', 'इसी', 'फिर', 'आप', 'करता', 'करते', 'उसी', 'ना', 'जहां', 'होने', 'किन्हें', 'सभी', 'होते', 'व', 'में', 'बाला', 'इसके', 'वहाँ', 'अंदर', 'इस', 'कौन', 'बनी', 'दुसरा', 'उनके', 'संग', 'आदि', 'एस', 'हो', 'तिन्हों', 'किंहों', 'रहा', 'लिये', 'वे', 'जहाँ', 'करने', 'जिन्हों', 'बिलकुल', 'उन्हीं', 'अपने', 'कोन', 'साथ', 'मगर', 'किसी', 'जिंहों', 'वुह', 'ऱ्वासा', 'जब', 'थि', 'कुल', 'का', 'दबारा', 'से', 'द्वारा', 'दिया', 'वहां', 'हुई', 'भि', 'कि', 'कोई', 'नीचे', 'इसे', 'इसका', 'साबुत', 'थी', 'तो', 'यहां', 'या', 'उनकी', 'उन्हों', 'किर', 'उसे', 'उनकि', 'रही', 'उसके', 'हें', 'जिधर', 'जा', 'गई', 'किया', 'वह', 'ही', 'कोनसा', 'इंहों', 'काफि', 'वहीं', 'ने', 'कौनसा', 'होती', 'दवारा', 'उस', 'उनका', 'हि', 'घर', 'जिन्हें', 'किन्हों', 'यदि', 'वरग', 'जिन', 'इनका', 'उसि', 'दो', 'होना', 'के', 'उंहें', 'सबसे', 'इसकी', 'यिह', 'अप', 'इन्हें', 'इत्यादि', 'किंहें', 'नहीं', 'एसे', 'करना', 'काफ़ी', 'तिन', 'उंहिं', 'उंहों', 'भी', 'अभी', 'पहले', 'रवासा', 'तक', 'सकता', 'कर', 'को', 'कइ', 'तब', 'हैं', 'जीधर', 'रखें', 'इंहिं', 'दुसरे', 'रहे', 'पुरा', 'पे', 'लिए', 'और', 'बहि', 'मे', 'न', 'उन', 'हुअ', 'हे', 'कई', 'अभि', 'था', 'भीतर', 'इसि', 'जो', 'निहायत', 'अदि', 'कहते', 'जेसे', 'बनि', 'इसमें', 'ऐसे', 'इन्हों', 'ओर', 'एवं', 'जैसा', 'की', 'इंहें', 'अपना', 'तिसे', 'जिस', 'इतयादि', 'पूरा', 'एक', 'कितना', 'होति', 'इन', 'है', 'तिस', 'बताया', 'हुइ', 'होता', 'इसकि', 'तिंहें', 'नहिं', 'कुछ', 'जैसे', 'भितर', 'बही', 'यह', 'इन्हीं', 'जिसे', 'किसे', 'ये', 'पर', 'करें', 'बाद', 'उन्हें', 'यही', 'यहि', 'साभ', 'वाले', 'तरह', 'बहुत', 'कहा', 'किसि', 'वग़ैरह', 'जितना', 'सो', 'कोइ', 'हुए', 'यहाँ', 'लेकिन', 'तिंहों', 'थे', 'सभि'}

# Devanagari / Gujarati sentence terminators that YAKE's segmenter
# (built for European languages) doesn't recognize. Left un-normalized,
# YAKE merges phrases across sentence boundaries -- silently wrong output.
SENTENCE_TERMINATORS = re.compile(r"[।॥]")


def normalize_text(text: str) -> str:
    """Fix sentence boundaries so YAKE's segmenter behaves correctly."""
    text = SENTENCE_TERMINATORS.sub(".", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def get_yake_extractor(lang: str, top: int, ngram_max: int = 3) -> yake.KeywordExtractor:
    # Use our own curated stopword lists for every language (sourced from
    # stopwords-iso + observed-noise supplements) rather than YAKE's own
    # built-in lists, which are inconsistent in coverage across languages
    # and were confirmed (via real IndicCorpV2 output) to under-filter
    # aux-verb inflections, especially for Hindi.
    if lang == "hi":
        return yake.KeywordExtractor(
            lan="hi", n=ngram_max, top=top, dedup_lim=0.85, stopwords=HINDI_STOPWORDS
        )
    if lang == "gu":
        return yake.KeywordExtractor(
            lan="gu", n=ngram_max, top=top, dedup_lim=0.85, stopwords=GUJARATI_STOPWORDS
        )
    if lang == "mr":
        return yake.KeywordExtractor(
            lan="mr", n=ngram_max, top=top, dedup_lim=0.85, stopwords=MARATHI_STOPWORDS
        )
    # default / english
    return yake.KeywordExtractor(lan="en", n=ngram_max, top=top, dedup_lim=0.85)


def get_stopwords(lang: str) -> set:
    if lang == "gu":
        return GUJARATI_STOPWORDS
    if lang == "mr":
        return MARATHI_STOPWORDS
    if lang == "hi":
        return HINDI_STOPWORDS
    return set()


def tokenize(text: str, lang: str) -> List[str]:
    if lang in INDIC_LANG_CODE:
        tokens = list(indic_tokenize.trivial_tokenize(text, lang=INDIC_LANG_CODE[lang]))
    else:
        tokens = text.split()
    # drop pure punctuation tokens
    return [t for t in tokens if re.search(r"\w", t, re.UNICODE)]


def frequent_ngrams_streaming(
    filepath: str, lang: str, n_max: int = 3, top: int = 200,
    prune_every_lines: int = 30000, min_keep: int = 2,
) -> List[Tuple[str, int]]:
    """Raw frequency n-grams (1..n_max), memory-bounded.

    On large real-world corpora, the number of UNIQUE 2/3-grams can reach
    tens of millions -- storing them all in a plain Counter runs out of
    RAM and gets the process killed (confirmed by testing at this scale).

    Fix: process the file line-by-line (never load the whole file into
    memory as one string), and periodically drop n-grams seen only once
    ("lossy counting" -- a standard technique for frequent-item counting
    on large streams). This keeps memory bounded while still finding the
    genuinely frequent phrases, at the cost of a small approximation on
    the long tail of rare n-grams, which you don't care about anyway
    since you only want the TOP phrases.
    """
    stopwords = get_stopwords(lang)
    counters = {n: Counter() for n in range(1, n_max + 1)}

    with open(filepath, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            tokens = [t for t in tokenize(line, lang) if t not in stopwords]
            for n in range(1, n_max + 1):
                for i in range(len(tokens) - n + 1):
                    counters[n][" ".join(tokens[i : i + n])] += 1

            if line_num % 20000 == 0:
                sizes = {n: len(counters[n]) for n in counters}
                print(f"[{lang}] freq-count: {line_num} lines processed, unique n-grams so far {sizes}")

            if line_num % prune_every_lines == 0:
                for n in range(2, n_max + 1):  # unigrams rarely need pruning
                    before = len(counters[n])
                    if before > 500000:  # only bother pruning once it's actually large
                        counters[n] = Counter({k: v for k, v in counters[n].items() if v >= min_keep})
                        print(f"[{lang}] pruned n={n}: {before} -> {len(counters[n])} unique entries (memory safety)")

    combined = Counter()
    for n in counters:
        combined.update(counters[n])

    return combined.most_common(top)


def yake_phrases_streaming(
    filepath: str, lang: str, top: int = 200, n_max: int = 3,
    sample_lines: int = 30000, batch_size: int = 300,
) -> List[Tuple[str, float]]:
    """YAKE phrase extraction, batched and sampled.

    YAKE is built to score keywords within a single document, not a
    200MB corpus -- feeding it the whole file at once is unusably slow
    (and was the second cause of the "stuck" run). Instead: take a
    sample of the corpus (default first 30k lines -- IndicCorp isn't
    ordered by topic, so this is a fair a representative slice), run
    YAKE on small batches of lines, and aggregate: a phrase that shows
    up as a top keyword across many batches, with a good average score,
    is a genuinely frequent, meaningful phrase -- which is exactly what
    you want as a search-query seed.
    """
    extractor = get_yake_extractor(lang, top=30, ngram_max=n_max)  # top-30 per small batch is plenty

    phrase_scores: dict = {}   # phrase -> list of scores seen across batches
    batch_lines: List[str] = []
    batches_done = 0

    def process_batch(lines: List[str]):
        nonlocal batches_done
        chunk = normalize_text(" ".join(lines))
        if not chunk.strip():
            return
        try:
            for phrase, score in extractor.extract_keywords(chunk):
                phrase_scores.setdefault(phrase, []).append(score)
        except Exception as e:
            print(f"[{lang}] YAKE batch skipped due to error: {e}")
        batches_done += 1

    with open(filepath, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            if line_num > sample_lines:
                break
            batch_lines.append(line)
            if len(batch_lines) >= batch_size:
                process_batch(batch_lines)
                batch_lines = []
                if batches_done % 20 == 0:
                    print(f"[{lang}] YAKE: {batches_done} batches processed ({line_num} lines sampled)")

        if batch_lines:
            process_batch(batch_lines)

    # rank by: how many batches it appeared as a top phrase in (descending),
    # then by average score (ascending -- lower YAKE score = better)
    ranked = sorted(
        phrase_scores.items(),
        key=lambda kv: (-len(kv[1]), sum(kv[1]) / len(kv[1])),
    )
    return [(phrase, round(sum(scores) / len(scores), 4)) for phrase, scores in ranked[:top]]


def process_language(lang: str, filepath: str, top: int, outdir: str) -> None:
    if os.path.getsize(filepath) == 0:
        print(f"[{lang}] WARNING: file is empty, skipping.")
        return

    print(f"[{lang}] running frequency n-gram count (streaming, memory-safe) ...")
    freq_results = frequent_ngrams_streaming(filepath, lang, n_max=3, top=top)

    print(f"[{lang}] running YAKE phrase extraction (sampled + batched) ...")
    yake_results = yake_phrases_streaming(filepath, lang, top=top, n_max=3)

    os.makedirs(outdir, exist_ok=True)

    freq_path = os.path.join(outdir, f"{lang}_frequent_ngrams.csv")
    with open(freq_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["phrase", "frequency"])
        writer.writerows(freq_results)

    yake_path = os.path.join(outdir, f"{lang}_yake_phrases.csv")
    with open(yake_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["phrase", "yake_score_lower_is_better"])
        writer.writerows(yake_results)

    print(f"[{lang}] wrote {freq_path} ({len(freq_results)} rows)")
    print(f"[{lang}] wrote {yake_path} ({len(yake_results)} rows)")


def parse_input_arg(value: str) -> Tuple[str, str]:
    if ":" not in value:
        raise argparse.ArgumentTypeError(
            f"--input must be LANGCODE:path, got '{value}'"
        )
    lang, path = value.split(":", 1)
    lang = lang.strip().lower()
    if lang not in {"hi", "gu", "mr", "en"}:
        raise argparse.ArgumentTypeError(
            f"unsupported language code '{lang}' (use hi, gu, mr, en)"
        )
    return lang, path


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--input",
        action="append",
        type=parse_input_arg,
        required=True,
        help="LANGCODE:path_to_corpus_text_file (repeatable, one per language)",
    )
    parser.add_argument("--top", type=int, default=200, help="Top-N phrases per language (default 200)")
    parser.add_argument("--outdir", default="./phrases_output", help="Output directory")
    args = parser.parse_args()

    for lang, path in args.input:
        if not os.path.exists(path):
            print(f"[{lang}] ERROR: file not found: {path}")
            continue
        process_language(lang, path, args.top, args.outdir)


if __name__ == "__main__":
    main()
