"""Vinted-bevakning: kollar vinted.se efter nya annonser och skickar push via ntfy."""
import json
import os
import sys
import time

import requests

# ---- Inställningar -------------------------------------------------------
SEARCHES = [
    {"keyword": "Gucci", "max_price": 800},
    {"keyword": "Balenciaga", "max_price": 800},
    {"keyword": "Prada", "max_price": 800},
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
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "sv-SE,sv;q=0.9,en;q=0.8",
}


def load_seen():
    try:
        with open(SEEN_FILE) as f:
            return json.load(f)
    except FileNotFoundError:
        return None


def save_seen(ids):
    with open(SEEN_FILE, "w") as f:
        json.dump(ids[-MAX_SEEN:], f)


def get_session():
    s = requests.Session()
    s.headers.update(HEADERS)
    s.get(BASE, timeout=20)  # hämtar sessionscookie
    return s


def search(s, keyword, max_price):
    params = {
        "search_text": keyword,
        "price_to": max_price,
        "currency": "SEK",
        "order": "newest_first",
        "per_page": 30,
        "page": 1,
    }
    r = s.get(f"{BASE}/api/v2/catalog/items", params=params, timeout=20)
    r.raise_for_status()
    items = r.json().get("items", [])
    kw = keyword.lower()
    # behåll bara annonser där märket eller titeln faktiskt matchar
    return [
        it for it in items
        if kw in (it.get("brand_title") or "").lower()
        or kw in (it.get("title") or "").lower()
    ]


def price_text(it):
    p = it.get("price")
    if isinstance(p, dict):
        return f"{p.get('amount')} {p.get('currency_code', 'SEK')}"
    return f"{p} SEK"


def notify(it, keyword):
    if not NTFY_TOPIC:
        print("NTFY_TOPIC saknas, hoppar över notis")
        return
    photo = (it.get("photo") or {}).get("url")
    url = it.get("url") or f"{BASE}/items/{it['id']}"
    payload = {
        "topic": NTFY_TOPIC,
        "title": f"{keyword}: {price_text(it)}",
        "message": f"{it.get('title', '')}\nStorlek: {it.get('size_title') or '–'}",
        "click": url,
        "tags": ["shopping"],
    }
    if photo:
        payload["attach"] = photo
    requests.post("https://ntfy.sh", json=payload, timeout=15)


def main():
    test_mode = "--test" in sys.argv
    seen = load_seen()
    first_run = seen is None
    seen = seen or []
    seen_set = set(seen)

    s = get_session()
    new_count = 0
    for cfg in SEARCHES:
        try:
            items = search(s, cfg["keyword"], cfg["max_price"])
        except Exception as e:
            print(f"Fel vid sökning på {cfg['keyword']}: {e}")
            continue
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

    save_seen(seen)
    print("Första körningen: sparade befintliga annonser utan notiser."
          if first_run else f"Skickade {new_count} notiser.")


if __name__ == "__main__":
    main()
