import sys, json, re
sys.path.insert(0, ".")
import vinted_watch as v
s = v.get_session()
def get(params):
    r = s.get(v.BASE + "/catalog", params=params, timeout=30)
    d = v._flight(r.text); m='"items":{"items":'
    p = d.find(m)
    if p < 0: return r.status_code, []
    raw,_ = json.JSONDecoder().raw_decode(d, p+len(m))
    return r.status_code, [x["productItem"] for x in raw if x.get("productItem")]
base = {"search_text":"Gucci","price_to":800,"order":"newest_first"}
for extra in [{}, {"catalog[]":1904}, {"catalog_ids":1904}]:
    code, items = get({**base, **extra})
    men = [it["title"] for it in items if re.search(r"herr|men'?s|męsk|miesten|\bman\b", it["title"], re.I)]
    print(extra, code, len(items), "herr-titlar:", len(men), men[:3])
    print("   ", [it["title"][:30] for it in items[:6]])
