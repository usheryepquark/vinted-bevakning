import requests, re, json
H={"User-Agent":"Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36","Accept-Language":"sv-SE,sv;q=0.9"}
s=requests.Session(); s.headers.update(H)
s.get("https://www.vinted.se",timeout=20)
r=s.get("https://www.vinted.se/catalog",params={"search_text":"Gucci","price_to":800,"order":"newest_first"},timeout=20)
t=r.text
print("catalog",r.status_code,len(t))
print("item links:",len(set(re.findall(r'/items/(\d+)-',t))), list(set(re.findall(r'/items/\d+-[a-z0-9-]+',t)))[:3])
for m in sorted(set(re.findall(r'["\'](/(?:api|web/api)[^"\'\s?]{3,80})',t)))[:40]: print("path",m)
print("next_data" , "__NEXT_DATA__" in t, "self.__next_f" in t)
i=t.find('"catalog_items"'); print("catalog_items ctx", t[i:i+300] if i>=0 else None)
i=t.find('"price"'); print("price ctx", t[max(0,i-300):i+200] if i>=0 else None)
js=set(re.findall(r'src="(https://[^"]+\.js)"',t)); print("scripts",len(js))
found=set()
for u in list(js)[:60]:
    try:
        c=requests.get(u,timeout=15).text
        found|=set(re.findall(r'["`](/?(?:api/v\d|web/api)[^"`]{2,80})',c))
    except Exception: pass
for f in sorted(found):
    if "catalog" in f or "item" in f or "search" in f: print("js",f)
