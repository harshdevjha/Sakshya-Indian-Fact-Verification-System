"""
factcheck_scraper.py

Collects claims from Google's Fact Check Tools API using TWO query sources
combined together:

  1. HARDCODED_QUERIES -- the hand-picked seed terms (schemes, festivals,
     public figures, states, etc). Kept as-is: broad "always relevant"
     topics you already know matter, in Hindi/Gujarati/Marathi/English.

  2. CORPUS_QUERIES -- per-language phrases pulled straight out of real
     corpus text (IndicCorpV2), produced by
     phrase_extraction/corpus_phrase_extractor.py and stored in
     phrase_extraction/phrases_output/*.csv.

Why both: the hardcoded list on its own is why Gujarati/Marathi are
under-represented -- most of the hand-picked terms were chosen with an
English/Hindi-first mindset, so the API naturally returns more Hindi/
English claims. The corpus-extracted phrases are pulled from Gujarati and
Marathi text itself, so they surface claims a hand-picked list would miss.

Setup (matches README):
    set FACTCHECK_API_KEY=your-key-here
    python .Data_Collection/factcheck_scraper.py

Optional flags:
    python factcheck_scraper.py --top-per-file 100 --output claims.csv
"""

import argparse
import csv
import os
import sys
import time

import requests

BASE_URL = "https://factchecktools.googleapis.com/v1alpha1/claims:search"

# ---------------------------------------------------------------------------
# 1. Hand-picked seed queries (unchanged from before -- keep whatever you
#    already had here). Trimmed to a representative slice for readability;
#    paste your full existing list back in place of this one.
# ---------------------------------------------------------------------------
HARDCODED_QUERIES = [
    "जन धन योजना", "उज्ज्वला योजना", "आयुष्मान भारत",
    "पीएम किसान", "मनरेगा", "फ्री राशन", "पेंशन",
    "लाडली बहना", "स्कॉलरशिप", "छात्रवृत्ति",

    "જનધન યોજના", "ઉજ્જ્વલા યોજના", "આયુષ્માન ભારત",
    "પીએમ કિસાન", "મફત રાશન",

    "जनधन योजना", "आयुष्मान भारत", "पीएम किसान",
    "मोफत रेशन", "शिष्यवृत्ती",

    "NEET", "JEE", "UPSC", "SSC", "CUET",
    "परीक्षा", "रिजल्ट", "भर्ती", "नौकरी",
    "सरकारी नौकरी",

    "नीट", "जेईई", "यूपीएससी",
    "પરીક્ષા", "ભરતી",
    "परीक्षा", "भरती",

    "RBI", "SBI", "HDFC", "ICICI",
    "ATM", "loan", "credit card",
    "bank account", "KYC",
    "UPI", "NPCI", "Paytm",
    "PhonePe", "Google Pay",

    "केवाईसी", "लोन", "बैंक खाता",
    "केवायसी", "बँक खाते",
    "કેવાયસી", "લોન",

    "WhatsApp", "Facebook", "Instagram", "Telegram",
    "Twitter", "X", "YouTube", "reel",
    "viral video", "viral image",

    "व्हाट्सएप", "वायरल वीडियो",
    "व्हॉट्सअॅप", "व्हायरल व्हिडिओ",
    "વોટ્સએપ", "વાયરલ વિડિયો",

    "ChatGPT", "AI", "deepfake", "artificial intelligence",
    "robot", "Google", "Microsoft", "OpenAI",

    "डीपफेक", "ડીપફેક",

    "राम", "कृष्ण", "शिव",
    "हनुमान", "अल्लाह",
    "कुरान", "गीता",
    "चर्च", "गुरुद्वारा",

    "રામ", "કૃષ્ણ", "અલ્લાહ",

    "Indian Army", "Indian Air Force", "Indian Navy",
    "DRDO", "ISRO", "missile", "fighter jet",

    "इसरो", "मिसाइल", "इस्त्रो",
    "ઇસરો", "મિસાઈલ",

    "Russia", "Ukraine", "Israel", "Palestine",
    "USA", "China", "Pakistan",

    "रूस", "यूक्रेन", "इजरायल",
    "रशिया", "युक्रेन",
    "રશિયા", "યુક્રેન",

    "Shah Rukh Khan", "Salman Khan", "Virat Kohli",
    "Rohit Sharma", "MS Dhoni", "Sachin Tendulkar",

    "शाहरुख खान", "विराट कोहली", "रोहित शर्मा",

    "cricket", "IPL", "World Cup", "Olympics", "BCCI",

    "क्रिकेट", "आईपीएल", "विश्व कप",
    "ક્રિકેટ", "આઈપીએલ",

    "heatwave", "rainfall", "flood", "earthquake",
    "cyclone", "landslide",

    "बाढ़", "भूकंप", "चक्रवात",
    "પૂર", "ભૂકંપ", "વાવાઝોડું",

    "murder", "kidnapping", "rape", "fraud", "scam", "arrest",

    "हत्या", "अपहरण", "धोखाधड़ी",
    "ખૂન", "અપહરણ", "ઠગાઈ",

    "heart attack", "blood pressure", "cancer",
    "diabetes", "dengue", "malaria", "tuberculosis",

    "हृदय रोग", "डेंगू", "मलेरिया",
    "ડેન્ગ્યુ", "મેલેરિયા",

    "fake", "fact check", "misleading", "false",
    "hoax", "viral claim", "rumour", "rumor",

    "फर्जी", "झूठ", "अफवाह",
    "ખોટું", "અફવા", "ફેક",

    "ગુજરાત", "ગુજરાત સરકાર", "અમદાવાદ", "સુરત", "વડોદરા",
    "રાજકોટ", "ભાવનગર", "જૂનાગઢ", "જામનગર", "ભરૂચ",
    "કચ્છ", "ગાંધીનગર", "ભાજપ", "કોંગ્રેસ", "આમ આદમી પાર્ટી",
    "ભૂપેન્દ્ર પટેલ", "હાર્દિક પટેલ", "અમિત શાહ", "નરેન્દ્ર મોદી",
    "ચૂંટણી", "મતદાન", "વિધાનસભા", "લોકસભા", "મુખ્યમંત્રી",
    "કલેક્ટર", "જિલ્લા પંચાયત", "નગરપાલિકા", "પંચાયત",
    "સરકારી યોજના", "સરકારી સહાય", "GPSC", "GSEB",
    "ધોરણ ૧૦", "ધોરણ ૧૨", "બોર્ડ પરીક્ષા", "પેપર લીક",
    "શિક્ષક ભરતી", "પોલીસ ભરતી", "સ્કોલરશિપ", "કોરોના",
    "રસી", "હોસ્પિટલ", "ડોક્ટર", "દવા", "આયુષ્માન કાર્ડ",
    "નવરાત્રી", "ઉત્તરાયણ", "રથયાત્રા", "જન્માષ્ટમી",
    "દિવાળી", "હોળી", "ખેડૂત", "ખેડૂત યોજના", "ખાતર",
    "પાક વીમો", "કપાસ", "મગફળી", "જીરૂ", "ડુંગળી",
    "સાયબર ફ્રોડ", "બેંક ફ્રોડ", "ફેક મેસેજ", "ફેક્ટ ચેક",
    "તથ્ય તપાસ", "ફેક્ટચેક", "વાયરલ પોસ્ટ", "વાયરલ ફોટો",
    "વાયરલ વીડિયો", "વાયરલ દાવો", "ખરું છે?", "ખોટું છે?",
    "ફોરવર્ડ",
    "Fact Crescendo Gujarati", "Vishvas News Gujarati",
    "Newschecker Gujarati", "BOOM Gujarati", "Alt News Gujarati",

    "महाराष्ट्र", "महाराष्ट्र सरकार", "मुंबई", "पुणे", "नागपूर",
    "ठाणे", "नाशिक", "औरंगाबाद", "कोल्हापूर", "सांगली",
    "सोलापूर", "सातारा", "रत्नागिरी", "रायगड", "भाजप",
    "काँग्रेस", "शिवसेना", "राष्ट्रवादी काँग्रेस",
    "महाविकास आघाडी", "मनसे", "एकनाथ शिंदे", "देवेंद्र फडणवीस",
    "अजित पवार", "उद्धव ठाकरे", "राज ठाकरे", "शरद पवार",
    "निवडणूक", "महापालिका", "ग्रामपंचायत", "रेशन कार्ड",
    "MPSC", "SSC Board", "HSC Board", "पेपर फुटला",
    "शिक्षक भरती", "पोलीस भरती", "भरती", "शिष्यवृत्ती",
    "लस", "रुग्णालय", "औषध", "गणेशोत्सव", "आषाढी एकादशी",
    "दहीहंडी", "गुढी पाडवा", "शेतकरी", "पीक विमा",
    "कर्जमाफी", "कापूस", "सोयाबीन", "कांदा", "खत",
    "सायबर फसवणूक", "बँक फसवणूक", "UPI फसवणूक",
    "फॅक्ट चेक", "तथ्य पडताळणी", "फॅक्टचेक", "व्हायरल पोस्ट",
    "व्हायरल फोटो", "व्हायरल व्हिडिओ", "व्हायरल दावा",
    "खरं आहे का", "खोटं आहे का", "फॉरवर्ड",
    "Fact Crescendo Marathi", "Boom Marathi",
    "Newschecker Marathi", "PTI Fact Check Marathi",
    "विश्वास न्यूज",

    "Gujarat", "Maharashtra", "Ahmedabad", "Surat", "Vadodara",
    "Rajkot", "Mumbai", "Pune", "Nagpur", "Nashik", "Kolhapur",
    "Gujarati fact check", "Marathi fact check",
    "Gujarati fake news", "Marathi fake news",
    "Gujarati misinformation", "Marathi misinformation",
    "Gujarati viral", "Marathi viral",
    "Gujarati hoax", "Marathi hoax",
    "Gujarati rumor", "Marathi rumor",
    "Gujarati viral claim", "Marathi viral claim",
    "fact check Gujarat", "fact check Maharashtra",
    "viral Gujarat", "viral Maharashtra",
    "fake news Gujarat", "fake news Maharashtra",
    "misinformation Gujarat", "misinformation Maharashtra",

    "વિધાનસભા ચૂંટણી", "લોકસભા ચૂંટણી", "ચૂંટણી પરિણામ",
    "મતગણતરી", "EVM", "VVPAT", "ચૂંટણી પંચ", "ECI",
    "આચાર સંહિતા", "મતદાર યાદી", "બૂથ", "પ્રચાર",
    "ચૂંટણી રેલી", "ઉમેદવાર", "રાજકારણ", "રાજકીય પક્ષ",
    "વિધાયક", "સાંસદ", "મંત્રી", "પ્રધાનમંત્રી", "ગૃહમંત્રી",
    "મોદી", "રાહુલ ગાંધી", "અરવિંદ કેજરીવાલ", "CM", "PM",

    "विधानसभा निवडणूक", "लोकसभा निवडणूक", "मतमोजणी",
    "निवडणूक आयोग", "आचारसंहिता", "मतदार यादी",
    "मतदान केंद्र", "प्रचार सभा", "उमेदवार", "राजकारण",
    "आमदार", "खासदार", "मुख्यमंत्री", "पंतप्रधान",
    "गृहमंत्री", "मोदी", "राहुल गांधी", "केजरीवाल",

    "PM Awas", "PMAY", "PMJDY", "Ayushman Card", "Aadhaar",
    "PAN card", "ration card", "eShram", "ABHA",
    "Digilocker", "cow scheme", "farmer scheme",
    "government subsidy", "scholarship portal", "DBT",

    "આધાર કાર્ડ", "પાન કાર્ડ", "રેશન કાર્ડ", "ઈ-શ્રમ",
    "ડિજિલોકર",

    "आधार कार्ड", "पॅन कार्ड", "ई-श्रम", "डिजिलॉकर",
    "सरकारी अनुदान",

    "OTP", "bank fraud", "QR code", "KYC update",
    "Aadhaar update", "SIM swap", "reward points",
    "free recharge", "gift voucher", "lottery",
    "income tax refund", "income tax notice",
    "electricity bill", "FASTag", "FASTag KYC",
    "UPI fraud", "PhonePe scam", "Paytm scam",
    "Google Pay scam", "WhatsApp scam",

    "QR કોડ", "બેંક છેતરપિંડી", "ફ્રી રિચાર્જ",
    "લોટરી", "વીજળી બિલ",

    "QR कोड", "मोफत रिचार्ज", "लॉटरी", "वीज बिल",

    "દશેરા", "ઈદ", "બકરી ઈદ", "મહાશિવરાત્રી",
    "રક્ષાબંધન", "રામ નવમી", "છઠ્ઠ", "મકરસંક્રાંતિ",

    "दसरा", "ईद", "बकरी ईद", "महाशिवरात्री",
    "रक्षाबंधन", "राम नवमी", "छठ", "मकरसंक्रांत",

    "covid vaccine", "covid booster", "bird flu",
    "monkeypox", "HMPV", "nipah", "swine flu",
    "cholera", "measles", "polio", "rabies", "covid",

    "કોરોના", "મંકીપોક્સ", "બર્ડ ફ્લૂ", "હોલેરા", "પોલિયો",

    "कोरोना", "मंकीपॉक्स", "बर्ड फ्लू", "हैजा", "पोलिओ",

    "IMD", "weather alert", "heavy rain", "cloudburst",
    "red alert", "orange alert", "yellow alert",
    "storm", "lightning", "temperature",

    "child kidnapping", "organ trafficking",
    "human trafficking", "gold scam", "online scam",
    "cyber crime", "cyber attack", "terrorist",
    "bomb", "explosion", "police",

    "સાયબર ક્રાઈમ", "આતંકવાદી", "બોમ્બ", "વિસ્ફોટ",
    "सायबर गुन्हा", "दहशतवादी", "बॉम्ब", "स्फोट",

    "Amitabh Bachchan", "Aamir Khan", "Akshay Kumar",
    "Deepika Padukone", "Alia Bhatt", "Ranbir Kapoor",
    "Kareena Kapoor", "Kangana Ranaut", "Allu Arjun",
    "Prabhas", "Yash", "Rajinikanth", "NTR", "Ram Charan",
    "Pawan Kalyan",

    "ICC", "Asia Cup", "Champions Trophy", "T20 World Cup",
    "WPL", "Kabaddi", "Pro Kabaddi", "Hockey",
    "Olympic medal", "Asian Games",

    "WhatsApp update", "Instagram update", "Facebook update",
    "Meta AI", "Gemini AI", "Grok AI", "DeepSeek",
    "ChatGPT Plus",

    "temple", "mosque", "church", "gurudwara",
    "Hindu", "Muslim", "Christian", "Sikh",
    "Buddhist", "Jain",

    "Delhi", "UP", "Bihar", "Punjab", "Haryana",
    "Tamil Nadu", "Karnataka", "Kerala", "Assam",
    "Rajasthan", "West Bengal", "Odisha", "Jharkhand",
    "Chhattisgarh",

    "Indore", "Bhopal", "Jaipur", "Lucknow", "Noida",
    "Gurgaon", "Bengaluru", "Hyderabad", "Chennai", "Kolkata",

    "factcheck", "fact-check", "viral post",
    "disinformation", "false claim", "fake image",
    "fake video", "edited video", "AI image", "CGI",
    "morphed photo",

    "વાયરલ દાવો", "વાયરલ ફોટો", "વાયરલ વિડિયો", "ફેક્ટ ચેક",
    "ખોટો દાવો",

    "व्हायरल दावा", "व्हायरल फोटो", "व्हायरल व्हिडिओ",
    "फॅक्ट चेक", "खोटा दावा",

    "Gujarati", "Marathi", "Gujarati news", "Marathi news",
    "Gujarati politics", "Marathi politics",
    "Gujarati election", "Marathi election",
]

# ---------------------------------------------------------------------------
# 2. Corpus-extracted phrases
# ---------------------------------------------------------------------------

# Languages the corpus pipeline covers. Add "en" if you extracted English too.
CORPUS_LANGS = ["hi", "gu", "mr"]

# Both files produced per language by corpus_phrase_extractor.py.
CORPUS_FILE_KINDS = ["frequent_ngrams", "yake_phrases"]

MIN_SINGLE_TOKEN_CHARS = 4  # drop very short single-word entries (usually leftover function words)


def load_corpus_queries(phrases_dir: str, top_per_file: int = 100) -> list:
    """Read phrases_output/*.csv and turn them into query strings.

    Prefers multi-word phrases over single tokens: looking at the actual
    output, the highest-frequency single words are still mostly function
    words (postpositions, copulas) that slipped past the stopword filter
    in corpus_phrase_extractor.py -- they're common, but not useful search
    seeds. Multi-word phrases are far more likely to be topical.
    """
    queries = []
    seen = set()

    for lang in CORPUS_LANGS:
        lang_added = 0
        for kind in CORPUS_FILE_KINDS:
            path = os.path.join(phrases_dir, f"{lang}_{kind}.csv")
            if not os.path.exists(path):
                print(f"[warn] missing {path} -- run corpus_phrase_extractor.py for '{lang}' first, skipping")
                continue

            with open(path, "r", encoding="utf-8", newline="") as f:
                reader = csv.DictReader(f)
                taken = 0
                for row in reader:
                    if taken >= top_per_file:
                        break
                    phrase = (row.get("phrase") or "").strip()
                    if not phrase:
                        continue

                    is_multiword = " " in phrase
                    if not is_multiword and len(phrase) < MIN_SINGLE_TOKEN_CHARS:
                        continue  # likely a leftover function word, not a topical seed

                    if phrase in seen:
                        continue

                    seen.add(phrase)
                    queries.append(phrase)
                    taken += 1
                    lang_added += 1

        print(f"[{lang}] added {lang_added} corpus-derived queries")

    return queries


def build_query_list(phrases_dir: str, top_per_file: int) -> list:
    corpus_queries = load_corpus_queries(phrases_dir, top_per_file)

    combined = []
    seen = set()
    for q in HARDCODED_QUERIES + corpus_queries:
        if q not in seen:
            seen.add(q)
            combined.append(q)

    print(f"Total queries: {len(combined)} "
          f"({len(HARDCODED_QUERIES)} hardcoded + {len(corpus_queries)} corpus-derived, "
          f"{len(HARDCODED_QUERIES) + len(corpus_queries) - len(combined)} duplicates removed)")
    return combined


# ---------------------------------------------------------------------------
# API fetching, with retry/backoff and incremental writes
# ---------------------------------------------------------------------------

def fetch_with_retry(params: dict, max_retries: int = 5) -> dict | None:
    """GET the Fact Check API with exponential backoff on 429/5xx errors."""
    delay = 2
    for attempt in range(1, max_retries + 1):
        try:
            response = requests.get(BASE_URL, params=params, timeout=30)
        except requests.RequestException as e:
            print(f"  [retry {attempt}/{max_retries}] network error: {e}")
            time.sleep(delay)
            delay *= 2
            continue

        if response.status_code == 200:
            return response.json()

        if response.status_code in (429, 500, 502, 503, 504):
            print(f"  [retry {attempt}/{max_retries}] HTTP {response.status_code}, "
                  f"backing off {delay}s: {response.text[:200]}")
            time.sleep(delay)
            delay *= 2
            continue

        # Non-retryable error (400/401/403 etc) -- no point retrying
        print(f"  Error {response.status_code}: {response.text[:300]}")
        return None

    print("  Giving up after max retries.")
    return None


FIELDNAMES = [
    "claim_text", "claimant", "claim_date",
    "publisher_name", "publisher_site",
    "review_title", "review_url", "review_date",
    "rating", "language", "matched_query",
]


def load_existing_urls(output_path: str) -> set:
    """Resume support: if the output CSV already exists, don't re-fetch dupes."""
    if not os.path.exists(output_path):
        return set()
    seen = set()
    with open(output_path, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("review_url"):
                seen.add(row["review_url"])
    print(f"Resuming: {len(seen)} claims already in {output_path}")
    return seen


def run(api_key: str, queries: list, output_path: str) -> None:
    seen_urls = load_existing_urls(output_path)
    file_exists = os.path.exists(output_path)

    # Incremental write: open once, flush after every claim, so a crash
    # partway through a long run doesn't lose everything collected so far.
    with open(output_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        if not file_exists:
            writer.writeheader()
            f.flush()

        for qi, query in enumerate(queries, 1):
            print(f"[{qi}/{len(queries)}] Fetching claims for: {query}")
            next_page_token = None

            while True:
                params = {"query": query, "pageSize": 100, "key": api_key}
                if next_page_token:
                    params["pageToken"] = next_page_token

                data = fetch_with_retry(params)
                if data is None:
                    break  # move to next query rather than killing the whole run

                for claim in data.get("claims", []):
                    claim_text = claim.get("text", "")
                    claimant = claim.get("claimant", "")
                    claim_date = claim.get("claimDate", "")

                    for review in claim.get("claimReview", []):
                        url = review.get("url", "")
                        if not url or url in seen_urls:
                            continue
                        seen_urls.add(url)

                        writer.writerow({
                            "claim_text": claim_text,
                            "claimant": claimant,
                            "claim_date": claim_date,
                            "publisher_name": review.get("publisher", {}).get("name", ""),
                            "publisher_site": review.get("publisher", {}).get("site", ""),
                            "review_title": review.get("title", ""),
                            "review_url": url,
                            "review_date": review.get("reviewDate", ""),
                            "rating": review.get("textualRating", ""),
                            "language": review.get("languageCode", ""),
                            "matched_query": query,
                        })
                        f.flush()  # persist immediately, don't wait for buffer/EOF

                next_page_token = data.get("nextPageToken")
                if not next_page_token:
                    break
                time.sleep(1)

    print(f"Done. Total unique claims in {output_path}: {len(seen_urls)}")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--phrases-dir",
        default=os.path.join("phrase_extraction", "phrases_output"),
        help="Directory containing {lang}_frequent_ngrams.csv / {lang}_yake_phrases.csv",
    )
    parser.add_argument("--top-per-file", type=int, default=100,
                         help="Top-N phrases to take from each corpus CSV, per language (default 100)")
    parser.add_argument("--output", default="factcheck_claims_final.csv",
                         help="Output CSV path (appended to; safe to resume)")
    args = parser.parse_args()

    api_key = os.environ.get("FACTCHECK_API_KEY")
    if not api_key:
        print("ERROR: FACTCHECK_API_KEY environment variable is not set.")
        print("  Windows:  set FACTCHECK_API_KEY=your-key-here")
        print("  macOS/Linux: export FACTCHECK_API_KEY=your-key-here")
        sys.exit(1)

    queries = build_query_list(args.phrases_dir, args.top_per_file)
    run(api_key, queries, args.output)


if __name__ == "__main__":
    main()
