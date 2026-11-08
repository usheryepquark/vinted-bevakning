import sys, re, json, time
sys.path.insert(0, ".")
import vinted_watch as v
s = v.get_session()
items = v.fetch(s, "925 silver", 250)
print("items", len(items))
it = items[0]
print("user field:", json.dumps(it.get("user"))[:200])
r = s.get(v.BASE + it["url"], timeout=30)
fl = v._flight(r.text)
for k in ["country", "countryCode", "country_code", "country_iso_code", "countryIsoCode", "countryTitle", "country_title", "city", "location", "countryId", "country_id"]:
    for m in list(re.finditer(re.escape('"'+k+'"') + r'\s*:\s*("?[^,}\]]{1,40})', fl))[:2]:
        print("item page", k, "=>", m.group(1))
for m in list(re.finditer(r'(Sverige|Polen|Polska|Sweden|Poland)[^<"]{0,30}', fl))[:5]:
    print("text:", m.group(0))
uid = it["user"]["id"]
for path in [f"/member/{uid}", f"/api/v2/users/{uid}"]:
    rr = s.get(v.BASE + path, timeout=30)
    t = v._flight(rr.text) + rr.text
    c = re.search(r'"(country_iso_code|countryIsoCode|country_code|countryCode|country_title|countryTitle)"\s*:\s*"([^"]+)"', t)
    print(path, rr.status_code, c.group(0) if c else None)
