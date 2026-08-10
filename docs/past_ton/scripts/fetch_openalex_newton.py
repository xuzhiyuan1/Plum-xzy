import json,urllib.request,time
UA="Mozilla/5.0"; SRC="S5407042750"
all_items=[]
page=0
sel="id,doi,title,publication_date,publication_year,authorships,primary_location,best_oa_location,open_access,type,biblio,abstract_inverted_index,keywords,cited_by_count"
while True:
    page+=1
    url="https://api.openalex.org/works?filter=primary_location.source.id:%s&per-page=200&page=%d&select=%s"%(SRC,page,sel)
    req=urllib.request.Request(url,headers={"User-Agent":UA})
    d=json.load(urllib.request.urlopen(req,timeout=60))
    res=d.get("results",[])
    all_items.extend(res)
    print("page",page,"items",len(res),"cum",len(all_items),"count",d.get("meta",{}).get("count"),flush=True)
    if len(res)<200 or len(all_items)>=int(d.get("meta",{}).get("count",0)): break
    time.sleep(0.8)
json.dump(all_items,open("/home/xuzy/Plum-for-award/Plum/docs/past_ton/cache/openalex_newton_all.json","w"))
print("DONE total",len(all_items),flush=True)
