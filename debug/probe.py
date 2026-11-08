import sys
sys.path.insert(0, ".")
import vinted_watch as v
s = v.get_session()
cfg = [c for c in v.SEARCHES if c["label"] == "925 silver"][0]
items = [it for it in v.fetch(s, cfg["query"], 250) if v.keep(it, cfg, 250)]
print("kvar efter filter:", len(items))
from collections import Counter
c = Counter()
for it in items[:25]:
    cc = v.seller_country(s, it); c[cc] += 1
    if cc == "SE":
        print(f"   SE {v.price_text(it):>7} | {it['title'][:60]}")
print("länder bland 25 första:", dict(c))
