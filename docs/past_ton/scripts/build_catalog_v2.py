#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build corrected TON 2025-2026 catalog v2.
Primary: Crossref NEW e-ISSN 2998-4157 (journal renamed to 'IEEE Transactions on Networking' from Vol 33/2025).
Cross-check: OpenAlex source S5407042750 (abstracts+OA) + DBLP XML (ton33/ton34).
No fabricated dates. A volume plus a real page range is treated as a formally
paginated article; missing issue metadata alone is not Early Access evidence."""
import json, os, re, csv, html, urllib.parse

BASE = "/home/xuzy/Plum-for-award/Plum/docs/past_ton"
CACHE = os.path.join(BASE, "cache")
NEW_ISSN = "2998-4157"; OLD_ISSN = "1063-6692"
JOURNAL_TITLE = "IEEE Transactions on Networking"
DATE_FROM = (2025,1,1); DATE_TO = (2026,12,31)  # by formal/online year

def load_crossref():
    return json.load(open(os.path.join(CACHE,"crossref_ton_all.json"))) if os.path.exists(os.path.join(CACHE,"crossref_ton_all.json")) else []
# NOTE: crossref_ton_all.json is OLD-issn (5144). Use new-issn cache:
def load_crossref_new():
    p = os.path.join(CACHE,"crossref_newissn_all.json")
    return json.load(open(p))

def load_openalex():
    p = os.path.join(CACHE,"openalex_newton_all.json")
    return json.load(open(p)) if os.path.exists(p) else []

def load_dblp():
    """Return dict doi->{year,volume,number,pages,issue_label,key,authors,title} from cached XML."""
    out = {}
    for v in ["33","34"]:
        p = os.path.join(CACHE,"dblp_ton%s.xml"%v)
        if not os.path.exists(p): continue
        xml = open(p,encoding="utf-8",errors="replace").read()
        for m in re.finditer(r'<article key="([^"]+)"[^>]*>(.*?)</article>', xml, re.S):
            key=m.group(1); body=m.group(2)
            def g(tag):
                mm=re.search(r'<%s>(.*?)</%s>'%(tag,tag), body, re.S)
                return html.unescape(re.sub(r'\s+',' ',mm.group(1)).strip()) if mm else ""
            authors=re.findall(r'<author[^>]*>(.*?)</author>', body, re.S)
            authors=[html.unescape(re.sub(r'\s+',' ',a).strip()) for a in authors]
            ee=g("ee"); doi=""
            mm=re.search(r'doi\.org/(10\.[^"&\s]+)', ee, re.I) or re.search(r'(10\.\d{4,9}/[^\s"&]+)', ee)
            if mm: doi=mm.group(1).rstrip('.').lower()
            out[doi]={"dblp_key":key,"year":g("year"),"volume":g("volume"),"number":g("number"),
                      "pages":g("pages"),"authors":authors,"title":g("title"),"dblp_vol":v}
    return out

def date_parts(d):
    if not d: return None
    dp=d.get("date-parts")
    if not dp or not dp[0]: return None
    return tuple(dp[0][:3])

def fmt_date(dt):
    if not dt: return ""
    return "-".join("%02d"%x for x in dt)

def date_year(dt):
    return dt[0] if dt else None

def load_existing_ids():
    """Keep established sequence ids stable so tonNNNN citation keys do not drift."""
    p=os.path.join(BASE,"ton_2025_2026_catalog_v2.csv")
    if not os.path.exists(p): return {}
    try:
        return {r["doi"].lower():int(r["sequence_id"])
                for r in csv.DictReader(open(p,encoding="utf-8"))
                if r.get("doi") and r.get("sequence_id")}
    except Exception:
        return {}

def load_pdf_index():
    """Index already downloaded PDFs by DOI without redownloading them."""
    out={}
    root=os.path.join(BASE,"pdfs")
    if not os.path.isdir(root): return out
    for chunk in sorted(os.listdir(root)):
        idx=os.path.join(root,chunk,"index.csv")
        if not os.path.isfile(idx): continue
        for r in csv.DictReader(open(idx,encoding="utf-8")):
            if r.get("status")!="ok" or not r.get("doi"): continue
            out[r["doi"].lower()]={
                "path":os.path.relpath(os.path.join(root,chunk,r["filename"]),BASE),
                "sha256":r.get("sha256","")}
    return out

def abstract_from_inv(idx):
    if not idx: return ""
    pos={}
    for w,ls in idx.items():
        for p in ls: pos[p]=w
    return " ".join(pos[i] for i in sorted(pos))

def clean_abs(s):
    if not s: return ""
    s=re.sub(r'<[^>]+>',' ',s); s=re.sub(r'\s+',' ',s).strip()
    return s

def first_author(authors_cr, authors_oa, authors_dblp):
    for src in (authors_cr, authors_dblp, []):
        if src:
            a=src[0]
            if isinstance(a,dict):
                g=(a.get("given") or "").strip(); f=(a.get("family") or "").strip()
                return (f or g) and ("%s %s"%(g,f) if g and f else (g or f))
            return a
    if authors_oa:
        nm=(authors_oa[0].get("author") or {}).get("display_name")
        if nm: return nm
    return ""

def non_research(title, cr_type):
    t=(title or "").lower()
    if "table of contents" in t: return "toc"
    if "notice of violation" in t: return "notice_of_violation"
    if any(k in t for k in ["errata","erratum","corrigendum","correction to"]): return "erratum"
    if any(k in t for k in ["editorial","guest editorial","preface","society information","publication information","information for author","reviewer"]): return "front_matter"
    if cr_type and cr_type not in ("journal-article","article"): return cr_type
    return ""

def relevance_auto(title, abstract):
    txt=(title+" "+abstract).lower()
    strong=["half-duplex","half duplex","bidirectional bandwidth","bidirectional rate","video conferenc","webrtc","sfu",
            "adaptive bitrate","bandwidth prediction","throughput prediction","qoe","wifi","wlan",
            "bandwidth allocation","rate allocation","congestion control","energy-aware","energy aware",
            "power consumption","thermal","throttl","battery","soc","rate control","mobile device","overheating",
            "multi-objective","fairness","bitrate","abr"]
    hits=[k for k in strong if k in txt]
    # Automatic matching only creates review candidates. R1/R2 require a
    # human DOI-level decision; keywords such as WiFi or half-duplex are noisy.
    if len(hits)>=1: return "R3"
    return "R4"

def build():
    existing_ids=load_existing_ids()
    cr = load_crossref_new()
    oa = load_openalex()
    dblp = load_dblp()
    # index openalex by doi
    oa_by_doi={}
    for r in oa:
        d=(r.get("doi") or "").replace("https://doi.org/","").lower().strip()
        if d: oa_by_doi[d]=r
    print("crossref new-issn:",len(cr),"| openalex:",len(oa),"| dblp:",len(dblp), flush=True)
    # Build from Crossref (primary). Only journal-article type.
    records=[]
    for it in cr:
        doi=(it.get("DOI") or "").lower().strip()
        if not doi: continue
        if it.get("type") and it["type"] not in ("journal-article",): continue
        title=(it.get("title") or [""])[0].strip()
        pp=date_parts(it.get("published-print"))
        po=date_parts(it.get("published-online"))
        created=date_parts(it.get("created"))
        vol=it.get("volume") or ""
        issue=it.get("issue") or ""
        pages=it.get("page") or ""
        oa_rec = oa_by_doi.get(doi, {})
        effective_vol=vol or dblp.get(doi,{}).get("volume","") or (oa_rec.get("biblio") or {}).get("volume","") or ""
        effective_issue=issue or dblp.get(doi,{}).get("number","") or (oa_rec.get("biblio") or {}).get("issue","") or ""
        effective_pages=pages or dblp.get(doi,{}).get("pages","") or ""
        # publication_status. IEEE's current continuous pagination often omits
        # issue in Crossref; real volume pages are stronger evidence than issue.
        nr=non_research(title, it.get("type"))
        if nr:
            pub_status="non_research_item"
        else:
            has_volume = bool(effective_vol)
            has_issue = bool(effective_issue)
            has_real_pages = bool(effective_pages) and effective_pages!="1-1"
            if has_issue or (has_volume and has_real_pages):
                pub_status="formal_volume_article"
            elif not has_volume and not has_real_pages:
                pub_status="early_access"
            else:
                pub_status="uncertain"
        # anomaly
        if "ton.10723154" in doi and not pp:
            pub_status="uncertain"
        # dates
        first_online = po or created  # DOI deposit date is only a fallback
        ea_date = first_online if pub_status=="early_access" else ""
        # in scope if any supplied formal/online/deposit date is in 2025-2026
        years={date_year(x) for x in (pp,po,created) if x}
        if not years.intersection({2025,2026}): continue
        # merge openalex
        in_oa = bool(oa_rec)
        in_dblp = doi in dblp
        abs_oa = clean_abs(abstract_from_inv(oa_rec.get("abstract_inverted_index")))
        abs_cr = clean_abs(it.get("abstract") or "")
        abstract = abs_cr or abs_oa
        boal = oa_rec.get("best_oa_location") or {}
        oa_pdf = boal.get("pdf_url") or boal.get("oa_url") or ""
        oa_status = (oa_rec.get("open_access") or {}).get("oa_status","")
        authors_cr = it.get("author") or []
        authors_oa = oa_rec.get("authorships") or []
        authors_d = dblp.get(doi,{}).get("authors") or []
        fa = first_author(authors_cr, authors_oa, authors_d)
        rec = {
            "doi":doi,"title":title,"authors_cr":authors_cr,"authors_oa":authors_oa,"authors_dblp":authors_d,
            "first_author":fa,
            "volume":effective_vol,"issue":effective_issue,"pages":effective_pages,
            "doi_year":(re.search(r'ton\.(\d{4})\.',doi) or [None,None])[1] if re.search(r'ton\.(\d{4})\.',doi) else "",
            "first_online_date":fmt_date(first_online),
            "early_access_date":fmt_date(ea_date) if ea_date else "",
            "formal_publication_date":fmt_date(pp) if (pub_status=="formal_volume_article" and pp) else "",
            "dblp_year":dblp.get(doi,{}).get("year",""),
            "publication_status":pub_status,
            "abstract":abstract,
            "keywords":";".join(k.get("keyword","") for k in (oa_rec.get("keywords") or []) if k.get("keyword")),
            "oa_pdf":oa_pdf,"oa_status":oa_status,
            "metadata_sources":"crossref"+("+openalex" if in_oa else "")+("+dblp" if in_dblp else ""),
            "conflict_notes":"",
        }
        records.append(rec)
    # dedup by doi (should already be unique from crossref, but safety)
    seen={};
    for r in records: seen[r["doi"]]=r
    records=list(seen.values())
    # Preserve ids already referenced by draft/report. New records, if any, are
    # appended deterministically rather than renumbering the whole catalog.
    def sk(r):
        fd=r["formal_publication_date"] or r["first_online_date"]
        return (0 if r["publication_status"]=="formal_volume_article" else 1, fd, r["doi"])
    if existing_ids:
        next_id=max(existing_ids.values(),default=0)+1
        for r in records:
            r["sequence_id"]=existing_ids.get(r["doi"])
            if r["sequence_id"] is None:
                r["sequence_id"]=next_id; next_id+=1
        records.sort(key=lambda r:r["sequence_id"])
    else:
        records.sort(key=sk)
        for i,r in enumerate(records,1): r["sequence_id"]=i
    return records

def main():
    recs=build()
    pdf_index=load_pdf_index()
    # relevance auto
    for r in recs:
        r["relevance_level"]=relevance_auto(r["title"], r["abstract"])
        r["relevance_reason"]=""
        r["manually_verified"]="False"
    # write catalog v2
    cols=["sequence_id","title","authors","doi","journal_title","issn","volume","issue","pages_or_article_number",
          "doi_year","first_online_date","early_access_date","formal_publication_date","dblp_year",
          "publication_status","metadata_sources","source_urls","abstract","keywords",
          "relevance_level","relevance_reason","fulltext_status","local_pdf_path","pdf_sha256",
          "conflict_notes","manually_verified","first_author"]
    path=os.path.join(BASE,"ton_2025_2026_catalog_v2.csv")
    with open(path,"w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=cols); w.writeheader()
        for r in recs:
            authors="; ".join([("%s %s"%((a.get("given") or "").strip(),(a.get("family") or "").strip())).strip() for a in r["authors_cr"]]) or "; ".join(r["authors_dblp"])
            if not authors:
                authors="; ".join((a.get("author") or {}).get("display_name","") for a in r["authors_oa"] if (a.get("author") or {}).get("display_name"))
            w.writerow({
                "sequence_id":r["sequence_id"],"title":r["title"],"authors":authors,"doi":r["doi"],
                "journal_title":JOURNAL_TITLE,"issn":NEW_ISSN,"volume":r["volume"],"issue":r["issue"],
                "pages_or_article_number":r["pages"],"doi_year":r["doi_year"],
                "first_online_date":r["first_online_date"],"early_access_date":r["early_access_date"],
                "formal_publication_date":r["formal_publication_date"],"dblp_year":r["dblp_year"],
                "publication_status":r["publication_status"],"metadata_sources":r["metadata_sources"],
                "source_urls":"https://doi.org/"+r["doi"],
                "abstract":r["abstract"],"keywords":r["keywords"],
                "relevance_level":r["relevance_level"],"relevance_reason":r["relevance_reason"],
                "fulltext_status":("downloaded" if r["doi"] in pdf_index else ("oa_available" if r["oa_pdf"] else ("closed" if r["oa_status"]=="closed" else "no_oa_info"))),
                "local_pdf_path":pdf_index.get(r["doi"],{}).get("path",""),
                "pdf_sha256":pdf_index.get(r["doi"],{}).get("sha256",""),"conflict_notes":r["conflict_notes"],
                "manually_verified":"False","first_author":r["first_author"],
            })
    print("catalog_v2 written:",path,"rows:",len(recs),flush=True)
    # references.bib v2 (research only)
    bib=os.path.join(BASE,"ton_2025_2026_references_v2.bib")
    with open(bib,"w",encoding="utf-8") as f:
        for r in recs:
            if r["publication_status"]=="non_research_item":
                continue
            key="ton%04d"%r["sequence_id"]
            au=" and ".join([("%s, %s"%((a.get("family") or "").strip(),(a.get("given") or "").strip())).strip(", ") for a in r["authors_cr"] if (a.get("family"))])
            if not au: au=" and ".join(r["authors_dblp"])
            yr=r["formal_publication_date"][:4] if r["formal_publication_date"] else (r["early_access_date"][:4] if r["early_access_date"] else r["doi_year"])
            f.write("@article{%s,\n  title = {%s},\n  author = {%s},\n  journal = {IEEE Trans. Netw.},\n  year = {%s},\n  volume = {%s},\n  number = {%s},\n  pages = {%s},\n  doi = {%s},\n}\n\n"%(
                key,r["title"].replace("{","").replace("}","").strip(),au,yr,r["volume"],r["issue"],r["pages"],r["doi"]))
    print("bib v2 written:",bib,flush=True)
    # download_manifest v2 (OA only, sorted by relevance then date)
    man=os.path.join(BASE,"download_manifest_v2.csv")
    cols2=["sequence_id","doi","title","relevance_level","oa_pdf","download_status","local_pdf_path","pdf_sha256","priority"]
    with open(man,"w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=cols2); w.writeheader()
        # Manifest is the union of currently discoverable OA candidates and
        # already downloaded files whose OA URL may have disappeared/changed.
        oa_recs=[r for r in recs if r["oa_pdf"] or r["doi"] in pdf_index]
        prio={"R1":1,"R2":2,"R3":3,"R4":4}
        oa_recs.sort(key=lambda r:(prio.get(r["relevance_level"],5), r["sequence_id"]))
        for r in oa_recs:
            dl=pdf_index.get(r["doi"],{})
            w.writerow({"sequence_id":r["sequence_id"],"doi":r["doi"],"title":r["title"][:80],
                "relevance_level":r["relevance_level"],"oa_pdf":r["oa_pdf"],
                "download_status":("downloaded" if dl else "pending"),
                "local_pdf_path":dl.get("path",""),"pdf_sha256":dl.get("sha256",""),
                "priority":prio.get(r["relevance_level"],5)})
    print("manifest v2 written:",man,"OA items:",len(oa_recs),flush=True)
    # summary
    from collections import Counter
    sc=Counter(r["publication_status"] for r in recs)
    vc=Counter(r["volume"] for r in recs)
    rc=Counter(r["relevance_level"] for r in recs)
    yc=Counter((r["formal_publication_date"] or r["first_online_date"])[:4] for r in recs)
    abs_n=sum(1 for r in recs if r["abstract"])
    oa_n=sum(1 for r in recs if r["oa_pdf"])
    sm={"total":len(recs),"by_status":dict(sc),"by_volume":dict(sorted(vc.items())),
        "by_relevance_auto":dict(rc),"by_year":dict(sorted(yc.items())),
        "with_abstract":abs_n,"with_oa":oa_n}
    json.dump(sm, open(os.path.join(CACHE,"catalog_v2_summary.json"),"w"), indent=2)
    print("=== SUMMARY ===",flush=True)
    for k,v in sm.items(): print(" ",k,":",v,flush=True)

if __name__=="__main__":
    main()
