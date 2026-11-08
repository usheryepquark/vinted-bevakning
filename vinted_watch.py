"""Vinted-bevakning: kollar vinted.se efter nya annonser och skickar push via ntfy."""
import json
import os
import re
import sys
import time

import requests

# ---- Inställningar -------------------------------------------------------
SEARCHES = [
    {"keyword": "Gucci", "max_price": 800},
    {"keyword": "Balenciaga", "max_price": 800},
    {"keyword": "Prada", "max_price": 800},
]
# Annonser där titeln eller märket innehåller något av dessa ord hoppas över.
# Ett ord utan * måste stå som eget ord ("bok" fångar "bok" men inte "bokmärke").
# Ett ord med * räcker som början ("kosmetyczk*" fångar kosmetyczka, kosmetyczki).
EXCLUDE = [
    # --- Sminkväskor och necessärer ---
    "sminkväsk*", "necessär*", "toalettväsk*", "kosmetikväsk*", "sminkpåse*",    # sv
    "makeuptask*", "make-up task*", "toilettask*", "kosmetiktask*", "necessær*",  # da
    "makeup bag*", "make-up bag*", "make up bag*", "cosmetic bag*", "cosmetics bag*",
    "toiletry bag*", "wash bag*", "washbag*", "vanity case*", "necessaire*",      # en
    "kosmetyczk*",                                                                # pl
    "meikkipussi*", "meikkilaukku*", "kosmetiikkalaukku*", "toilettilaukku*",     # fi

    # --- Parfym ---
    "parfym*", "parfum*", "doft",                                                 # sv
    "parfume*", "duft",                                                           # da
    "perfum*", "fragrance*", "eau de", "cologne", "edt", "edp",                   # en + pl
    "hajuvesi*", "hajuvede*", "tuoksu",                                           # fi

    # --- Böcker ---
    "bok", "boken", "böcker*",                                                    # sv
    "bog", "bogen", "bøger*",                                                     # da
    "book", "books", "coffee table",                                              # en
    "książk*", "ksiazk*",                                                         # pl
    "kirja", "kirjat", "kirjan",                                                  # fi

    # --- Märken ---
    "h&m", "h & m", "h&amp;m", "hennes & mauritz", "primark*", "shein*",
]
BASE = "https://www.vinted.se"
NTFY_TOPIC = os.environ.get("NTFY_TOPIC", "")
SEEN_FILE = "seen.json"
MAX_SEEN = 3000
# -------------------------------------------------------------------------

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/130.0 Safari/537.36"
    ),
    "Accept-Language": "sv-SE,sv;q=0.9,en;q=0.8",
}


def _exclude_pattern(words):
    parts = []
    for w in words:
        prefix = w.endswith("*")
        w = re.escape(w.rstrip("*").lower())
        parts.append(r"(?<!\w)" + w + ("" if prefix else r"(?!\w)"))
    return re.compile("|".join(parts), re.IGNORECASE)


EXCLUDE_RE = _exclude_pattern(EXCLUDE)


def load_seen():
    try:
        with open(SEEN_FILE) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def save_seen(ids):
    with open(SEEN_FILE, "w") as f:
        json.dump(ids[-MAX_SEEN:], f)


def get_session():
    s = requests.Session()
    s.headers.update(HEADERS)
    s.get(BASE, timeout=20)  # hämtar sessionscookies
    return s


def _flight(html):
    chunks = re.findall(r'self\.__next_f\.push\(\[1,"(.*?)"\]\)</script>', html, re.S)
    return "".join(json.loads('"' + c + '"') for c in chunks)


def search(s, keyword, max_price):
    params = {"search_text": keyword, "price_to": max_price, "order": "newest_first"}
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
            items.append(it)
    if items and os.environ.get("DEBUG_KEYS"):
        print("fält:", sorted(items[0].keys()))

    kw = keyword.lower()
    out = []
    for it in items:
        text = (it.get("title") or "") + " " + json.dumps(it.get("itemBox") or {}, ensure_ascii=False)
        if EXCLUDE_RE.search(text):
            continue
        brand = json.dumps(it.get("itemBox") or {}, ensure_ascii=False)
        if kw not in brand.lower() and kw not in (it.get("title") or "").lower():
            continue
        try:
            if float((it.get("price") or {}).get("amount", 0)) > max_price:
                continue
        except (TypeError, ValueError):
            pass
        out.append(it)
    return out


def price_text(it):
    try:
        return f"{round(float((it.get('price') or {}).get('amount'))):d} kr"
    except (TypeError, ValueError):
        return "pris okänt"


def notify(it, keyword):
    if not NTFY_TOPIC:
        print("NTFY_TOPIC saknas, hoppar över notis")
        return
    photos = it.get("photos") or []
    photo = (photos[0].get("url") if photos else None) or it.get("thumbnailUrl")
    url = it.get("url") or f"/items/{it['id']}"
    if url.startswith("/"):
        url = BASE + url
    size = it.get("sizeTitle") or it.get("size_title")
    message = it.get("title", "")
    if size:
        message += f"\nStorlek: {size}"
    payload = {
        "topic": NTFY_TOPIC,
        "title": f"{keyword}: {price_text(it)}",
        "message": message,
        "click": url,
        "tags": ["shopping"],
    }
    if photo:
        payload["attach"] = photo
    requests.post("https://ntfy.sh", json=payload, timeout=15)


def main():
    test_mode = "--test" in sys.argv
    seen = load_seen()
    first_run = not seen
    seen_set = set(seen)

    s = get_session()
    new_count = 0
    ok = 0
    for cfg in SEARCHES:
        try:
            items = search(s, cfg["keyword"], cfg["max_price"])
        except Exception as e:
            print(f"Fel vid sökning på {cfg['keyword']}: {e}")
            continue
        ok += 1
        print(f"{cfg['keyword']}: {len(items)} träffar")
        for it in reversed(items):  # äldst först, så notiserna kommer i ordning
            iid = it["id"]
            if iid in seen_set:
                continue
            seen.append(iid)
            seen_set.add(iid)
            if not first_run:
                notify(it, cfg["keyword"])
                new_count += 1
                time.sleep(1)
        if test_mode and items:
            notify(items[0], cfg["keyword"] + " (test)")
        time.sleep(2)

    if ok == 0:
        sys.exit("Alla sökningar misslyckades")
    save_seen(seen)
    print("Första körningen: sparade befintliga annonser utan notiser."
          if first_run else f"Skickade {new_count} notiser.")


if __name__ == "__main__":
    main()
