import sys, re, json
sys.path.insert(0, ".")
import vinted_watch as v
s = v.get_session()
items = v.fetch(s, "Gucci", 800)
it = max(items, key=lambda x: x["id"])
url = v.BASE + it["url"]
r = s.get(url, timeout=30)
print("status", r.status_code, url)
d = v._flight(r.text) + r.text
for k in ["created_at_ts", "createdAt", "created_at", "updated_at_ts", "uploadedAt", "last_push_up_at", "pushedUpAt", "timestamp"]:
    for m in list(re.finditer(re.escape('"' + k + '"') + r'\s*:\s*("?[^,}]{1,40})', d))[:3]:
        print(k, "=>", m.group(1))
for m in list(re.finditer(r'(Uppladdad|Uppladdat|uploaded)[^<"]{0,60}', d, re.I))[:5]:
    print("text:", m.group(0))
print("ids newest:", sorted([x["id"] for x in items], reverse=True)[:5])
