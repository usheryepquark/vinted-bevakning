import requests, re, json
H={"User-Agent":"Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36","Accept-Language":"sv-SE,sv;q=0.9"}
s=requests.Session(); s.headers.update(H)
s.get("https://www.vinted.se",timeout=20)
t=s.get("https://www.vinted.se/catalog",params={"search_text":"Gucci","price_to":800,"order":"newest_first"},timeout=20).text
chunks=re.findall(r'self\.__next_f\.push\(\[1,"(.*?)"\]\)</script>',t,re.S)
flight="".join(json.loads('"'+c+'"') for c in chunks)
print("flight len",len(flight))
ids=re.findall(r'/items/(\d+)-',t)
iid=ids[0]
for m in list(re.finditer(r'"id":'+iid+r'\b',flight))[:2]:
    print("CTX>>>",flight[m.start()-200:m.start()+1800].replace("\n"," "))
print("order of first 8 ids in html:",ids[:8])
for k in ["catalogItems","\"items\":[","\"price\":{","\"brand_title\"","\"total_item_price\"","\"is_promoted\"","\"user\":{"]:
    print(k, flight.count(k))
