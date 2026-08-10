import json,csv,os
from collections import Counter
BASE="/home/xuzy/Plum-for-award/Plum/docs/past_ton"
recs=list(csv.DictReader(open(os.path.join(BASE,"ton_2025_2026_catalog_v2.csv"),encoding="utf-8")))
sc=Counter(r["publication_status"] for r in recs)
vc=Counter(r["volume"] or "(none)" for r in recs)
yc=Counter((r["formal_publication_date"] or r["first_online_date"])[:4] for r in recs)
rc=Counter(r["relevance_level"] for r in recs)
abs_n=sum(1 for r in recs if r["abstract"])
fc=Counter(r["fulltext_status"] for r in recs)
print("total:",len(recs))
print("by_status:",dict(sc))
print("by_volume:",dict(sorted(vc.items())))
print("by_year:",dict(sorted(yc.items())))
print("by_relevance:",dict(rc))
print("with_abstract:",abs_n,"/%d"%len(recs))
print("fulltext_status:",dict(fc))
# sample rows
print("--- formal sample ---")
for r in recs:
    if r["publication_status"]=="formal_volume_article":
        print(" ",r["sequence_id"],r["doi_year"],r["volume"],"iss",r["issue"],"formal:",r["formal_publication_date"],"online:",r["first_online_date"],"|",r["title"][:45])
        break
print("--- EA sample ---")
for r in recs:
    if r["publication_status"]=="early_access":
        print(" ",r["sequence_id"],"doiyr",r["doi_year"],"vol",r["volume"],"iss",r["issue"],"formal:",r["formal_publication_date"],"online:",r["first_online_date"],"|",r["title"][:45])
        break
print("--- uncertain sample ---")
for r in recs:
    if r["publication_status"]=="uncertain":
        print(" ",r["doi"],r["formal_publication_date"],r["first_online_date"])
