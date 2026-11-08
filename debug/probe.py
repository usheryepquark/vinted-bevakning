import sys, time
sys.path.insert(0, ".")
import vinted_watch as v
s = v.get_session()
for cfg in v.SEARCHES[3:]:
    items = v.fetch(s, cfg["query"], 800)
    kept = [it for it in items if v.keep(it, cfg, 800)]
    print(f"== {cfg['label']}: {len(kept)} av {len(items)} kvar")
    for it in kept[:10]:
        print(f"   KVAR {v.price_text(it):>7} | {it['_brand'][:22]:22} | {it['_size'][:12]:12} | {it['title'][:60]}")
    time.sleep(2)
