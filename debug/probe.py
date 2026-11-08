import sys, re, json, time
sys.path.insert(0, ".")
import vinted_watch as v
s = v.get_session()
r = s.get(v.BASE + "/catalog", params={"order": "newest_first"}, timeout=30)
d = v._flight(r.text); m = '"items":{"items":'
raw, _ = json.JSONDecoder().raw_decode(d, d.find(m) + len(m))
ids = sorted([x["productItem"]["id"] for x in raw], reverse=True)
print("global newest ids:", ids[:3], "now", int(time.time()))
it = raw[0]["productItem"]
r = s.get(v.BASE + it["url"], timeout=30)
page = r.text; fl = v._flight(page)
print("item", it["url"], r.status_code)
keys = sorted(set(re.findall(r'"([A-Za-z_]*(?:_at|At|_ts|Ts|[Tt]ime|[Dd]ate)[A-Za-z_]*)"\s*:', fl)))
print("time-like keys:", keys[:60])
for k in keys[:60]:
    mm = re.search(re.escape('"'+k+'"') + r'\s*:\s*("?[^,}\]]{1,40})', fl)
    if mm: print("  ", k, "=>", mm.group(1))
for mm in list(re.finditer(r'[^>"]{0,40}(sedan|minut|timm)[^<"]{0,40}', fl+page))[:8]:
    print("text:", mm.group(0))
time.sleep(60)
r = s.get(v.BASE + "/catalog", params={"order": "newest_first"}, timeout=30)
d = v._flight(r.text)
raw, _ = json.JSONDecoder().raw_decode(d, d.find(m) + len(m))
ids2 = sorted([x["productItem"]["id"] for x in raw], reverse=True)
print("after 60s newest:", ids2[:3], "delta per min:", ids2[0] - ids[0])
