"""Vinted-bevakning: kollar vinted.se efter nya annonser och skickar push via ntfy."""
import json
import os
import re
import sys
import time

import requests

# =========================================================================
#  INSTÄLLNINGAR
#
#  Ord i listorna nedan:
#    - utan *  måste stå som eget ord ("bok" fångar "bok" men inte "bokmärke")
#    - med *   räcker som början på ett ord ("kosmetyczk*" fångar kosmetyczka)
# =========================================================================

MAX_PRICE = 800  # kr, gäller alla sökningar om inget annat anges

# --- Gäller ALLA sökningar: titel eller märke ----------------------------
EXCLUDE = [
    # Sminkväskor och necessärer
    "sminkväsk*", "necessär*", "toalettväsk*", "kosmetikväsk*", "sminkpåse*",    # sv
    "makeuptask*", "make-up task*", "toilettask*", "kosmetiktask*", "necessær*",  # da
    "makeup bag*", "make-up bag*", "make up bag*", "cosmetic bag*", "cosmetics bag*",
    "toiletry bag*", "wash bag*", "washbag*", "vanity case*", "necessaire*",      # en
    "kosmetyczk*",                                                                # pl
    "meikkipussi*", "meikkilaukku*", "kosmetiikkalaukku*", "toilettilaukku*",     # fi

    # Parfym
    "parfym*", "parfum*", "doft",                                                 # sv
    "parfume*", "duft",                                                           # da
    "perfum*", "fragrance*", "eau de", "cologne", "edt", "edp",                   # en + pl
    "zapach*", "woda toaletowa", "woda perfumowana",                              # pl
    "hajuvesi*", "hajuvede*", "tuoksu",                                           # fi
    "paradoxe", "guilty",                                                         # namn

    # Böcker
    "bok", "boken", "böcker*",                                                    # sv
    "bog", "bogen", "bøger*",                                                     # da
    "book", "books", "coffee table",                                              # en
    "książk*", "ksiazk*",                                                         # pl
    "kirja", "kirjat", "kirjan",                                                  # fi

    # Märken
    "h&m", "h & m", "hennes & mauritz", "primark*", "shein*",

    # Kopior och "inspirerat av"
    "inspired*", "inspirerad*", "inspireret*", "inspiracj*", "inspiroitu*",
    "a'la", "a’la", "à la", "dupe*", "replica*", "replika*", "fake",
]

# --- Används av vissa sökningar ------------------------------------------
COSMETICS = [
    # sv
    "kosmetik*", "smink*", "läppstift*", "läppglans*", "mascara*", "foundation*",
    "puder*", "concealer*", "ögonskugg*", "eyeliner*", "nagellack*", "highlighter*",
    "primer*", "hudvård*", "ansiktskräm*", "kräm", "serum*", "duschgel*", "duschkräm*",
    "bodylotion*", "rouge dior", "rouge pur",
    # da
    "makeup*", "make-up*", "make up", "læbestift*", "neglelak*", "pudder*",
    "hudpleje*", "bronzer*", "blush*",
    # en
    "cosmetic*", "lipstick*", "lip gloss*", "lip glow*", "lip oil*", "lip balm*",
    "lip maximizer*", "balm", "eyeshadow*", "eye shadow*", "palette*", "powder",
    "cushion*", "skincare*", "skin care", "moisturi*", "cleanser*", "shower gel*",
    "body lotion*", "nail polish*", "nail", "beauty*", "sample*", "tester*",
    "travel size", "miniature*", "gift set*", "presentset*", "gaveæske*",
    "zestaw prezentowy", "lahjapakkaus*",
    # pl
    "kosmetyk*", "makijaż*", "pomadk*", "szmink*", "błyszczyk*", "tusz do rzęs",
    "podkład*", "róż do policzków", "cienie do powiek", "rozświetlacz*", "krem",
    "kremy", "żel pod prysznic", "balsam*", "lakier do paznokci", "próbk*",
    "miniatur*",
    # fi
    "kosmetiikka*", "meikki*", "huulipuna*", "ripsiväri*", "meikkivoide*",
    "puuteri*", "poskipuna*", "luomiväri*", "kynsilakka*", "voide*",
    "ihonhoito*", "suihkugeeli*",
    # produktnamn
    "diorshow*", "backstage", "addict", "capture totale", "forever skin",
    "dior prestige", "sauvage", "j'adore", "jadore", "miss dior",
    "hypnotic poison", "libre", "black opium", "mon paris", "touche éclat",
    "touche eclat", "all hours",
]

# Håraccessoarer (gäller alla sökningar).
HAIR = [
    "hårspänn*", "hårklämm*", "hårklips*", "hårsnodd*", "hårband*", "hårnål*",
    "hårsmycke*", "håraccessoar*", "diadem*", "tiara*", "scrunchie*", "pannband*",  # sv
    "hårspænde*", "hårklemme*", "hårbånd*", "hårelastik*", "hårpynt*",             # da
    "hair clip*", "hairclip*", "hair claw*", "claw clip*", "hair pin*", "hairpin*",
    "bobby pin*", "hair tie*", "hair band*", "hairband*", "headband*", "head band*",
    "barrette*", "hair accessor*", "hair slide*", "hair bow*", "snap clip*",       # en
    "spinka*", "spinki", "klamra do włosów", "klamerka do włosów", "gumka do włosów",
    "gumki do włosów", "opaska", "opaska do włosów", "wsuwk*", "frotk*",
    "akcesoria do włosów", "ozdoba do włosów",                                     # pl
    "hiuspinni*", "hiussolki*", "hiuspanta*", "hiusklipsi*", "hiuslenkki*",
    "hiuskoru*", "hiusasuste*", "panta",                                           # fi
]

# Slipsar och flugor (gäller alla sökningar). Ordet "tie" ensamt är medvetet
# utelämnat (tie-dye, tie front), se TIE_RE längre ner.
TIES = [
    "slips*", "fluga", "flugor", "flugan",                                         # sv/da
    "necktie*", "neck tie*", "bow tie*", "bowtie*", "silk tie*", "ties",           # en
    "krawat*", "muszka",                                                           # pl
    "solmio*", "rusetti*",                                                         # fi
]

# Kepsar (gäller alla sökningar). Ordet "cap" ensamt hanteras i CAP_RE längre ner
# (så att "cap sleeve" och "cap toe" får vara kvar).
CAPS = [
    "keps", "kepsar", "kepsen", "basebollkeps*", "snapback*", "trucker cap*",
    "trucker hat*", "baseball cap*", "baseballcap*", "dad hat*", "dad cap*",          # sv/en
    "kasket*", "baseballkasket*",                                                      # da
    "czapka z daszkiem", "czapki z daszkiem", "czapeczka z daszkiem", "bejsbolówk*",  # pl
    "lippis*", "lippalakki*",                                                          # fi
]

# Fler skönhetsord och skönhetsmärken (läggs till kosmetikfiltret).
BEAUTY_EXTRA = [
    "sephora*", "douglas", "lyko", "kicks beauty", "fenty beauty", "charlotte tilbury",
    "mac cosmetics", "nyx", "maybelline", "l'oréal", "l'oreal", "loreal", "clinique",
    "estée lauder", "estee lauder", "lancôme", "lancome", "benefit cosmetics",
    "rare beauty", "huda beauty", "too faced", "urban decay", "nars", "kiko",
    "rimmel", "the ordinary", "la roche-posay", "glossier", "rituals",
    "kylie cosmetics", "anastasia beverly hills", "bobbi brown", "armani beauty",
    "eyebrow*", "brow gel*", "brow pencil*", "ögonbryn*", "lashes", "lösfrans*",
    "ögonfrans*", "fransar", "lash serum*", "kohl", "contour*", "setting spray*",
    "bb cream*", "cc cream*", "lip liner*", "lipliner*", "lip pencil*", "läppenn*",
    "läppbalsam*", "korektor*", "baza pod makijaż", "kredka do oczu", "kredka do brwi",
    "kulmakynä*", "huulikiilto*", "huulirasva*", "øjenbryn*", "vipper", "mascara",
    "foundation", "läppstift",
]

# Hårvård och övrig skönhet (läggs till kosmetiklistan, som nu gäller alla sökningar).
HAIRCARE = [
    "schampo*", "shampoo*", "schampoo*", "balsam", "conditioner*", "hårvård*",
    "hårolja*", "hair oil*", "hair mask*", "hårinpackning*", "hair serum*",
    "plattång*", "locktång*", "hårfön*", "hair dryer*", "straightener*",
    "curling iron*", "szampon*", "odżywka do włosów", "hoitoaine*", "sampoo*",
    "hiusöljy*", "skönhet*", "skönhetsprodukt*", "hudkräm*", "ansiktsmask*",
    "face mask*", "sheet mask*", "deodorant*", "deo",
]

# Sneakers (gäller alla sökningar).
SNEAKERS = [
    "sneaker*", "trainer", "trainers", "gympaskor*", "sportskor*", "löparskor*",
    "sneakersy", "trampki*", "buty sportowe", "adidasy", "tennarit", "lenkkarit",
    "b22", "b23", "b27", "b30", "b33", "b57", "walk'n'dior", "walk n dior",          # Dior
    "tennisskor*", "sportsko*", "løbesko*", "joggesko*", "tennissko*",           # sv/da
    "tennis shoe*", "running shoe*", "runner", "runners", "high top*", "high-top*",
    "hi top*", "low top*", "low-top*", "chuck*", "converse",                     # en
    "buty do biegania", "juoksukengät*", "urheilukengät*",                       # pl/fi
    "triple s", "speed", "defender*", "3xl", "10xl", "x-pander", "track led",    # Balenciaga
    "geobasket*", "ramones", "dunks", "jumbo lace*", "turbodrk*", "geth runner*",  # Rick Owens
    "rhyton", "screener", "cloudbust*", "america's cup", "americas cup",          # Gucci/Prada
    "b-court", "unicorn",                                                         # Balmain
]

# Barnkläder (gäller alla sökningar, plus barnstorlekar som "3 år" och "12 mån").
# Medvetet utan "kid" (kid leather) och "baby*" (babydoll).
KIDS = [
    "barn", "barnen", "barnkläder*", "barnstorlek*", "baby", "babykläder*",
    "bebis*", "kids", "child*", "junior*", "toddler*",
    "flicka", "flickor", "pojke", "pojkar", "girls", "boys",                      # sv/en
    "børn*", "børne*", "pige", "piger", "dreng*",                                 # da
    "dziecięc*", "dziecko", "dzieci", "dziewczyn*", "dziewczęc*", "chłopięc*",
    "dla chłopca", "niemowl*",                                                    # pl
    "lasten", "vauva*", "tyttö*", "poika*",                                       # fi
]

# Förpackningar och presentpåsar (gäller alla sökningar).
# Medvetet utan "box" och "dustbag", eftersom skor och väskor ofta säljs "med box".
PACKAGING = [
    "presentask*", "presentpåse*", "papperspåse*", "shoppingpåse*", "tom kartong",
    "tom låda", "tom ask", "tomma kartong*", "kartong", "kartongen",               # sv
    "gaveæske*", "gavepose*", "papirpose*", "tom æske", "emballage",              # da
    "gift box*", "gift bag*", "paper bag*", "paper shopping bag*", "shopping bag",
    "empty box*", "box only", "only box", "packaging", "ribbon*",                 # en
    "pudełko", "pudełka", "torebka papierowa", "torba papierowa",
    "torebka prezentowa", "torba prezentowa", "opakowanie", "wstążk*",            # pl
    "lahjapussi*", "lahjarasia*", "paperikassi*", "tyhjä laatikko", "pakkaus",    # fi
]

# --- Sökningarna ---------------------------------------------------------
#  query:          vad som skrivs i Vinteds sökruta
#  match:          minst ett av orden måste finnas i titel eller märke
#  exclude:        extra ord som sorterar bort annonsen (titel eller märke)
#  exclude_brands: annonsen sorteras bort om märket är något av dessa
#  require:        minst ett av orden måste stå i titeln (t.ex. modellnamn)
#  max_price:      eget maxpris för just den sökningen
#  country:        bara säljare från detta land, t.ex. "SE" (kollas på säljarens profil)
#  brand_required: False = märket behöver inte stämma, räcker att titeln matchar
RICK = {
    "match": ["rick owens", "drkshdw", "drk shdw", "lilies"],
    "exclude_brands": ["avant garde", "japan style"],
}
SAINT_LAURENT = {
    "match": ["saint laurent", "yves saint laurent", "ysl"],
    "exclude": COSMETICS,
}

# Balenciagas klassiska motorcycle bag (City, Part Time, Work, First, Velo, Town ...).
# Märket måste vara Balenciaga och modellen måste stå i titeln.
# Alla sorters skor (används för Balenciaga). Medvetet utan "arena" och "hourglass",
# som också är Balenciaga-väskor.
SHOES = [
    "sko", "skor", "skorna", "stövl*", "boots", "kängor*", "känga", "sandal*",
    "loafer*", "pumps", "klackskor*", "högklack*", "slides", "slide", "tofflor*",
    "mules", "espadrill*", "ballerinaskor*", "träskor*",                         # sv
    "støvle*", "hæle*", "sandaler", "klipklapper*",                               # da
    "shoes", "shoe", "heels", "heel", "flats", "sandals", "footwear", "slingback*",
    "slip-on*", "slip on*", "flip flop*", "clogs", "crocs",                       # en
    "buty", "but", "botki", "kozaki", "sandały*", "szpilki", "klapki", "mokasyny",
    "trzewiki", "czółenka", "obuwie", "glany", "kalosze",                         # pl
    "kengät*", "kenkä*", "saappaat*", "nilkkurit*", "sandaalit*", "korkokengät*",
    "tossut*",                                                                    # fi
    "arenas", "knife", "tyrex", "bulldozer", "rhino", "cargo sneaker*",
    "pool slide*", "stretch boot*", "army boot*",                                 # modeller
]

BALENCIAGA_MOTO = {
    "match": ["balenciaga"],
    "require": [
        "city", "le city", "part time", "parttime", "motorcycle*", "motorbike*", "moto",
        "giant*", "classic", "first", "velo", "town", "work", "twiggy", "weekender",
        "arena", "lariat",
    ],
    "exclude": [
        "nyckelring*", "keychain*", "key ring*", "keyring*", "nøglering*", "breloczek*",
        "brelok*", "avaimenperä*", "bag charm*", "charm", "plånbok*", "wallet*",
        "portfel*", "lompakko*", "pung", "card holder*", "korthållare*",
    ] + SHOES,
    "max_price": 2000,
}

SEARCHES = [
    {"label": "925 silver", "query": "925 silver", "max_price": 250, "country": "SE",
     "brand_required": False,
     # försilvrat och silverfärgat är inte äkta silver (guldpläterat 925 är det, så det får vara kvar)
     "exclude": ["silverpläter*", "försilvr*", "silverfärg*", "silver plated*", "silver-plated*",
                 "silverplated*", "silver tone*", "silver-tone*", "silver color*", "silver colour*",
                 "posrebrz*", "forsølv*", "sølvbelagt*", "hopeoitu*", "hopeanvärinen*"],
     "match": ["925", "sterling*", "sterlingsilver*", "äkta silver*", "silver 925",
               "srebro 925", "sølv 925", "hopea 925"]},
    {"label": "Gucci", "query": "Gucci", "match": ["gucci"], "exclude": ["ace"]},
    {"label": "Balenciaga", "query": "Balenciaga", "match": ["balenciaga"], "exclude": SHOES},
    {"label": "Prada", "query": "Prada", "match": ["prada"]},
    {"label": "Rick Owens", "query": "Rick Owens", **RICK},
    {"label": "DRKSHDW", "query": "DRKSHDW", **RICK},
    {"label": "Rick Owens Lilies", "query": "Rick Owens Lilies", **RICK},
    {"label": "Saint Laurent", "query": "Saint Laurent", **SAINT_LAURENT},
    {"label": "YSL", "query": "YSL", **SAINT_LAURENT},
    {"label": "Ann Demeulemeester", "query": "Ann Demeulemeester",
     "match": ["ann demeulemeester", "demeulemeester"]},
    {"label": "Balenciaga City", "query": "Balenciaga City", **BALENCIAGA_MOTO},
    {"label": "Balenciaga Part Time", "query": "Balenciaga Part Time", **BALENCIAGA_MOTO},
    {"label": "Balenciaga moto", "query": "Balenciaga motorcycle bag", **BALENCIAGA_MOTO},
    {"label": "Balenciaga Giant", "query": "Balenciaga giant", **BALENCIAGA_MOTO},
    {"label": "Dior", "query": "Dior", "match": ["dior"],
     "exclude": COSMETICS},
    {"label": "Givenchy", "query": "Givenchy", "match": ["givenchy"], "exclude": COSMETICS},
    {"label": "Balmain", "query": "Balmain", "match": ["balmain"], "exclude": COSMETICS},
    {"label": "Pierre Balmain", "query": "Pierre Balmain", "match": ["balmain"],
     "exclude": COSMETICS},
]

BASE = "https://www.vinted.se"
NTFY_TOPIC = os.environ.get("NTFY_TOPIC", "")
SEEN_FILE = "seen.json"
MAX_SEEN = 20000
# =========================================================================

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/130.0 Safari/537.36"
    ),
    "Accept-Language": "sv-SE,sv;q=0.9,en;q=0.8",
}

KIDS_SIZE_RE = re.compile(r"(?<!\w)(år|mån\w*|months?|years?)(?!\w)", re.IGNORECASE)
VOLUME_RE = re.compile(r"\d\s?ml(?!\w)", re.IGNORECASE)  # "100ml", "50 ml" = parfym/kosmetik


def word_pattern(words):
    if not words:
        return None
    parts = []
    for w in words:
        prefix = w.endswith("*")
        w = re.escape(w.rstrip("*").lower())
        parts.append(r"(?<!\w)" + w + ("" if prefix else r"(?!\w)"))
    return re.compile("|".join(parts), re.IGNORECASE)


EXCLUDE_RE = word_pattern(EXCLUDE + KIDS + PACKAGING + SNEAKERS + HAIR + TIES
                          + COSMETICS + HAIRCARE + CAPS + BEAUTY_EXTRA)
# "Gucci cap", "caps" osv, men inte "cap sleeve" eller "cap toe".
CAP_RE = re.compile(r"(?<!\w)caps?(?![\w-])(?!\s+(sleeve|toe|d'))", re.IGNORECASE)
# "Gucci tie", "Dior silk tie" osv, men inte "tie-dye" eller "tie front".
TIE_RE = re.compile(
    r"(?<!\w)(gucci|dior|prada|ysl|saint laurent|givenchy|balmain|balenciaga|"
    r"rick owens|ann demeulemeester|silk|siden|jedwabny)\s+ties?(?![\w-])"
    r"(?!\s+(front|waist|up|back|side|detail|belt|knot|neck|blouse|top|dress))",
    re.IGNORECASE)
for cfg in SEARCHES:
    cfg["_match"] = word_pattern(cfg.get("match") or [cfg["query"]])
    cfg["_exclude"] = word_pattern(cfg.get("exclude"))
    cfg["_require"] = word_pattern(cfg.get("require"))
    cfg["_bad_brands"] = [b.lower() for b in cfg.get("exclude_brands", [])]


def load_state():
    try:
        with open(SEEN_FILE) as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return [], []
    if isinstance(data, list):  # gammalt format: bara id:n för de tre första märkena
        return data, (["Gucci", "Balenciaga", "Prada"] if data else [])
    return data.get("ids", []), data.get("seeded", [])


def save_state(ids, seeded):
    with open(SEEN_FILE, "w") as f:
        json.dump({"seeded": sorted(seeded), "ids": ids[-MAX_SEEN:]}, f)


def get_session():
    s = requests.Session()
    s.headers.update(HEADERS)
    s.get(BASE, timeout=20)  # hämtar sessionscookies
    return s


def _flight(html):
    chunks = re.findall(r'self\.__next_f\.push\(\[1,"(.*?)"\]\)</script>', html, re.S)
    return "".join(json.loads('"' + c + '"') for c in chunks)


def brand_and_size(it):
    label = ((it.get("itemBox") or {}).get("accessibilityLabel")) or ""
    b = re.search(r"Varumärke: (.*?)(?:, Skick:|, Storlek:|$)", label)
    sz = re.search(r"Storlek: (.*?), \d", label)
    return (b.group(1).strip() if b else ""), (sz.group(1).strip() if sz else "")


def fetch(s, query, max_price, page=1):
    params = {"search_text": query, "price_to": max_price, "order": "newest_first"}
    if page > 1:
        params["page"] = page
    r = s.get(f"{BASE}/catalog", params=params, timeout=30)
    r.raise_for_status()
    data = _flight(r.text)
    marker = '"items":{"items":'
    pos = data.find(marker)
    if pos < 0:
        raise RuntimeError("hittade inga annonser i sidan (formatet kan ha ändrats)")
    raw, _ = json.JSONDecoder().raw_decode(data, pos + len(marker))
    items = []
    for row in raw:
        it = row.get("productItem") if isinstance(row, dict) else None
        if isinstance(it, dict) and "id" in it:
            it["_brand"], it["_size"] = brand_and_size(it)
            items.append(it)
    return items


def keep(it, cfg, max_price):
    title = it.get("title") or ""
    brand = it["_brand"]
    text = f"{title} {brand}"
    if EXCLUDE_RE.search(text) or VOLUME_RE.search(title) or TIE_RE.search(title) \
            or CAP_RE.search(title):
        return False
    if cfg["_exclude"] and cfg["_exclude"].search(text):
        return False
    if any(b in brand.lower() for b in cfg["_bad_brands"]):
        return False
    if cfg["_require"] and not cfg["_require"].search(title):
        return False
    if KIDS_SIZE_RE.search(it["_size"]):
        return False
    if cfg.get("brand_required", True):
        if brand:
            # har annonsen ett märke måste det vara rätt märke ("Gucci-stil" från Zara åker bort)
            if not cfg["_match"].search(brand):
                return False
        elif not cfg["_match"].search(title):
            return False
    elif not cfg["_match"].search(text):
        return False
    try:
        if float((it.get("price") or {}).get("amount", 0)) > max_price:
            return False
    except (TypeError, ValueError):
        pass
    return True


def signature(it):
    """Samma säljare + samma titel + samma pris = samma sak, även om annonsen
    lagts upp på nytt med nytt nummer."""
    uid = (it.get("user") or {}).get("id")
    price = (it.get("price") or {}).get("amount")
    return f"{uid}|{(it.get('title') or '').strip().lower()}|{price}"


_COUNTRY_CACHE = {}


def seller_country(s, it):
    """Säljarens landskod (t.ex. "SE", "PL") från profilsidan."""
    uid = (it.get("user") or {}).get("id")
    if not uid:
        return None
    if uid not in _COUNTRY_CACHE:
        try:
            r = s.get(f"{BASE}/member/{uid}", timeout=30)
            m = re.search(r'"country_code"\s*:\s*"([A-Z]{2})"', _flight(r.text) + r.text)
            _COUNTRY_CACHE[uid] = m.group(1) if m else None
        except Exception:
            _COUNTRY_CACHE[uid] = None
        time.sleep(1)
    return _COUNTRY_CACHE[uid]


def country_ok(s, it, cfg):
    want = cfg.get("country")
    return not want or seller_country(s, it) == want


def price_text(it):
    try:
        return f"{round(float((it.get('price') or {}).get('amount'))):d} kr"
    except (TypeError, ValueError):
        return "pris okänt"


def notify(it, label):
    if not NTFY_TOPIC:
        print("NTFY_TOPIC saknas, hoppar över notis")
        return
    photos = it.get("photos") or []
    photo = (photos[0].get("url") if photos else None) or it.get("thumbnailUrl")
    url = it.get("url") or f"/items/{it['id']}"
    if url.startswith("/"):
        url = BASE + url
    lines = [it.get("title", "")]
    details = " · ".join(x for x in (it["_brand"], it["_size"]) if x)
    if details:
        lines.append(details)
    payload = {
        "topic": NTFY_TOPIC,
        "title": f"{label}: {price_text(it)}",
        "message": "\n".join(lines),
        "click": url,
        "tags": ["shopping"],
    }
    if photo:
        payload["attach"] = photo
    requests.post("https://ntfy.sh", json=payload, timeout=15)


def newest_id(s):
    """Högsta annons-id just nu på hela vinted.se (id:n delas ut i ordning)."""
    r = s.get(f"{BASE}/catalog", params={"order": "newest_first"}, timeout=30)
    d = _flight(r.text)
    marker = '"items":{"items":'
    raw, _ = json.JSONDecoder().raw_decode(d, d.find(marker) + len(marker))
    return max(row["productItem"]["id"] for row in raw if isinstance(row, dict) and row.get("productItem"))


def send_recent(minutes):
    """Skickar notiser för annonser som klarar filtren och är från ungefär de senaste
    X minuterna. Vinted visar ingen uppladdningstid, så åldern räknas ut från id:t.
    Rör inte listan över sedda annonser."""
    s = get_session()
    start_id, start_t = newest_id(s), time.time()
    rough_cutoff = start_id - minutes * 15000  # generös gräns för hur långt bak vi bläddrar
    found = {}
    for cfg in SEARCHES:
        max_price = cfg.get("max_price", MAX_PRICE)
        for page in range(1, 6):  # upp till 5 sidor bakåt
            try:
                raw = fetch(s, cfg["query"], max_price, page)
            except Exception as e:
                print(f"Fel vid sökning på {cfg['label']} sida {page}: {e}")
                break
            for it in raw:
                if keep(it, cfg, max_price):
                    found.setdefault(it["id"], (it, cfg["label"]))
            time.sleep(2)
            if not raw or min(it["id"] for it in raw) < rough_cutoff:
                break
    end_id, end_t = newest_id(s), time.time()
    per_min = max((end_id - start_id) / max(end_t - start_t, 1) * 60, 3000)
    cutoff = start_id - minutes * per_min
    print(f"~{per_min:.0f} nya annonser/min på Vinted, gräns id {cutoff:.0f}")
    recent = sorted((v for k, v in found.items() if k >= cutoff), key=lambda x: x[0]["id"])
    cfg_by_label = {c["label"]: c for c in SEARCHES}
    recent = [(it, label) for it, label in recent if country_ok(s, it, cfg_by_label[label])]
    for it, label in recent:
        notify(it, label)
        print(f"  skickad: {label} | {it['title'][:60]}")
        time.sleep(1)
    print(f"Skickade {len(recent)} notiser.")


def main():
    if "--recent" in sys.argv:
        send_recent(int(sys.argv[sys.argv.index("--recent") + 1]))
        return
    test_mode = "--test" in sys.argv
    seen, seeded = load_state()
    seen_set, seeded = set(seen), set(seeded)

    s = get_session()
    new_count = 0
    ok = 0
    for cfg in SEARCHES:
        max_price = cfg.get("max_price", MAX_PRICE)
        try:
            items = [it for it in fetch(s, cfg["query"], max_price) if keep(it, cfg, max_price)]
        except Exception as e:
            print(f"Fel vid sökning på {cfg['label']}: {e}")
            continue
        ok += 1
        first_time = cfg["query"] not in seeded  # ny sökning: spara utan notiser
        print(f"{cfg['label']}: {len(items)} träffar" + (" (första gången, inga notiser)" if first_time else ""))
        for it in reversed(items):  # äldst först, så notiserna kommer i ordning
            sig = signature(it)
            if it["id"] in seen_set or sig in seen_set:
                continue
            seen += [it["id"], sig]
            seen_set.update((it["id"], sig))
            if not first_time and country_ok(s, it, cfg):
                notify(it, cfg["label"])
                new_count += 1
                time.sleep(1)
        seeded.add(cfg["query"])
        if test_mode and items:
            notify(items[0], cfg["label"] + " (test)")
        time.sleep(2)

    if ok == 0:
        sys.exit("Alla sökningar misslyckades")
    save_state(seen, seeded)
    print(f"Skickade {new_count} notiser.")


if __name__ == "__main__":
    main()
