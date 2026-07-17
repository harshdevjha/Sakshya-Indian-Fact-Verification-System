## First code to fetch data from Google Fact Check API and save it to a CSV file.

import requests
import pandas as pd
import time

API_KEY = "Add Your API Key Here"  # Replace with your actual API key

BASE_URL = "https://factchecktools.googleapis.com/v1alpha1/claims:search"

queries = queries = [
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

all_claims = []
seen_urls = set()

for query in queries:
    print(f"Fetching claims for: {query}")

    next_page_token = None

    while True:
        params = {
            "query": query,
            "pageSize": 100,
            "key": API_KEY
        }

        if next_page_token:
            params["pageToken"] = next_page_token

        response = requests.get(BASE_URL, params=params)

        if response.status_code != 200:
            print("Error:", response.text)
            break

        data = response.json()

        claims = data.get("claims", [])

        for claim in claims:

            claim_text = claim.get("text", "")
            claimant = claim.get("claimant", "")
            claim_date = claim.get("claimDate", "")

            reviews = claim.get("claimReview", [])

            for review in reviews:

                url = review.get("url", "")

                if url in seen_urls:
                    continue

                seen_urls.add(url)

                all_claims.append({
                    "claim_text": claim_text,
                    "claimant": claimant,
                    "claim_date": claim_date,

                    "publisher_name": review.get("publisher", {}).get("name", ""),
                    "publisher_site": review.get("publisher", {}).get("site", ""),

                    "review_title": review.get("title", ""),
                    "review_url": url,
                    "review_date": review.get("reviewDate", ""),

                    "rating": review.get("textualRating", ""),
                    "language": review.get("languageCode", "")
                })

        next_page_token = data.get("nextPageToken")

        if not next_page_token:
            break

        time.sleep(1)

df = pd.DataFrame(all_claims)

print("Total claims collected:", len(df))

df.to_csv("factcheck_claims_final.csv", index=False)


print("Saved to factcheck_final.csv")