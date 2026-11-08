import requests
H={"User-Agent":"Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36","Accept":"application/json, text/plain, */*","Accept-Language":"sv-SE,sv;q=0.9"}
for base in ["https://www.vinted.se","https://www.vinted.fr"]:
    s=requests.Session(); s.headers.update(H)
    r=s.get(base,timeout=20)
    print(base,"home",r.status_code,r.url,"cookies:",list(s.cookies.keys()))
    for path in ["/api/v2/catalog/items?search_text=Gucci&per_page=5","/api/v2/catalog/items?search_text=Gucci&per_page=5&order=newest_first","/web/api/core/catalog/items?search_text=Gucci&per_page=5","/api/v2/items?search_text=Gucci&per_page=5"]:
        try:
            r=s.get(base+path,timeout=20)
            print(" ",path,r.status_code,r.headers.get("content-type"),r.text[:150].replace("\n"," "))
        except Exception as e: print(" ",path,"ERR",e)
