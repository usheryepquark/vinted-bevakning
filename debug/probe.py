import json, sys
sys.path.insert(0, ".")
import vinted_watch as v
s = v.get_session()
for q in ["rick owens", "dior"]:
    r = s.get(f"{v.BASE}/catalog", params={"search_text": q, "price_to": 800, "order": "newest_first"}, timeout=30)
    d = v._flight(r.text); m='"items":{"items":'
    raw, _ = json.JSONDecoder().raw_decode(d, d.find(m)+len(m))
    print("==", q, len(raw))
    for row in raw[:12]:
        it = row["productItem"]
        print(json.dumps({"t": it["title"], "box": it.get("itemBox")}, ensure_ascii=False)[:400])
