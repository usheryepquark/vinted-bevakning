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

SNEAKERS = [
    "sneaker*", "trainer", "trainers", "gympaskor*", "sportskor*", "löparskor*",
    "sneakersy", "trampki*", "buty sportowe", "adidasy", "tennarit", "lenkkarit",
    "b22", "b23", "b27", "b30", "b33", "b57", "walk'n'dior", "walk n dior",
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
RICK = {
    "match": ["rick owens", "drkshdw", "drk shdw", "lilies"],
    "exclude_brands": ["avant garde", "japan style"],
}
SAINT_LAURENT = {
    "match": ["saint laurent", "yves saint laurent", "ysl"],
    "exclude": COSMETICS,
}

SEARCHES = [
    {"label": "Gucci", "query": "Gucci", "match": ["gucci"]},
    {"label": "Balenciaga", "query": "Balenciaga", "match": ["balenciaga"]},
    {"label": "Prada", "query": "Prada", "match": ["prada"]},
    {"label": "Rick Owens", "query": "Rick Owens", **RICK},
    {"label": "DRKSHDW", "query": "DRKSHDW", **RICK},
    {"label": "Rick Owens Lilies", "query": "Rick Owens Lilies", **RICK},
    {"label": "Saint Laurent", "query": "Saint Laurent", **SAINT_LAURENT},
    {"label": "YSL", "query": "YSL", **SAINT_LAURENT},
    {"label": "Ann Demeulemeester", "query": "Ann Demeulemeester",
     "match": ["ann demeulemeester", "demeulemeester"]},
    {"label": "Dior", "query": "Dior", "match": ["dior"],
     "exclude": COSMETICS + SNEAKERS},
]

BASE = "https://www.vinted.se"
NTFY_TOPIC = os.environ.get("NTFY_TOPIC", "")
SEEN_FILE = "seen.json"
MAX_SEEN = 6000
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


EXCLUDE_RE = word_pattern(EXCLUDE + KIDS + PACKAGING)
for cfg in SEARCHES:
    cfg["_match"] = word_pattern(cfg.get("match") or [cfg["query"]])
    cfg["_exclude"] = word_pattern(cfg.get("exclude"))
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


def fetch(s, query, max_price):
    params = {"search_text": query, "price_to": max_price, "order": "newest_first"}
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
    if EXCLUDE_RE.search(text) or VOLUME_RE.search(title):
        return False
    if cfg["_exclude"] and cfg["_exclude"].search(text):
        return False
    if any(b in brand.lower() for b in cfg["_bad_brands"]):
        return False
    if KIDS_SIZE_RE.search(it["_size"]):
        return False
    if brand:
        # har annonsen ett märke måste det vara rätt märke ("Gucci-stil" från Zara åker bort)
        if not cfg["_match"].search(brand):
            return False
    elif not cfg["_match"].search(title):
        return False
    try:
        if float((it.get("price") or {}).get("amount", 0)) > max_price:
            return False
    except (TypeError, ValueError):
        pass
    return True


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


def _find_ts(obj, depth=0):
    if depth > 4:
        return None
    if isinstance(obj, dict):
        for k, val in obj.items():
            if k in ("timestamp", "createdAt", "created_at_ts") and isinstance(val, (int, float)):
                return val / 1000 if val > 1e12 else val
            r = _find_ts(val, depth + 1)
            if r:
                return r
    elif isinstance(obj, list):
        for val in obj[:2]:
            r = _find_ts(val, depth + 1)
            if r:
                return r
    return None


def item_time(it):
    """Uppladdningstid (unix-sekunder) om Vinted skickar med den, annars None."""
    return _find_ts(it.get("photos")) or _find_ts({k: it.get(k) for k in ("createdAt", "created_at_ts")})


def send_recent(minutes):
    """Skickar notiser för annonser som klarar filtren och laddats upp senaste X minuterna.
    Rör inte listan över sedda annonser."""
    cutoff = time.time() - minutes * 60
    s = get_session()
    sent, sent_ids, unknown = 0, set(), 0
    for cfg in SEARCHES:
        max_price = cfg.get("max_price", MAX_PRICE)
        try:
            items = [it for it in fetch(s, cfg["query"], max_price) if keep(it, cfg, max_price)]
        except Exception as e:
            print(f"Fel vid sökning på {cfg['label']}: {e}")
            continue
        if items and sent == 0 and unknown == 0:
            print("fotofält:", sorted((items[0].get("photos") or [{}])[0].keys()))
        hits = 0
        for it in items:
            ts = item_time(it)
            if ts is None:
                unknown += 1
                continue
            if ts >= cutoff and it["id"] not in sent_ids:
                sent_ids.add(it["id"])
                notify(it, cfg["label"])
                sent += 1
                hits += 1
                time.sleep(1)
        print(f"{cfg['label']}: {hits} senaste {minutes} min")
        time.sleep(2)
    print(f"Skickade {sent} notiser. Annonser utan tidsstämpel: {unknown}")


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
            if it["id"] in seen_set:
                continue
            seen.append(it["id"])
            seen_set.add(it["id"])
            if not first_time:
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
