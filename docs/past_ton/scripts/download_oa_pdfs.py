#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Download OA PDFs per manifest. Resumable: skips status=ok; validates %PDF/file/pdfinfo.
Chunk = 50 papers. Filename: NNNN_first-author_short-title.pdf"""
import csv, os, re, sys, time, subprocess, hashlib, urllib.request, urllib.error

BASE = "/home/xuzy/Plum-for-award/Plum/docs/past_ton"
PDFS = os.path.join(BASE, "pdfs")
MAN = os.path.join(BASE, "download_manifest.csv")
CAT = os.path.join(BASE, "ton_2025_2026_catalog.csv")
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
os.makedirs(PDFS, exist_ok=True)

def read_manifest():
    with open(MAN, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    return rows

def write_manifest(rows):
    cols = list(rows[0].keys()) if rows else []
    with open(MAN, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols); w.writeheader()
        for r in rows: w.writerow(r)

def slug(s, n=30):
    s = re.sub(r'[^a-zA-Z0-9]+','-', (s or "").lower()).strip('-')
    return s[:n].strip('-')

def first_author(authors):
    if not authors: return "anon"
    a = authors.split(';')[0].strip()
    last = a.split()[-1] if a.split() else a
    return re.sub(r'[^a-zA-Z]','', last).lower() or "anon"

def sha256(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for chunk in iter(lambda: f.read(1<<20), b''): h.update(chunk)
    return h.hexdigest()

def pdfinfo_pages(path):
    try:
        out = subprocess.run(["pdfinfo", path], capture_output=True, text=True, timeout=30).stdout
        for line in out.splitlines():
            if line.startswith("Pages:"):
                return line.split(":",1)[1].strip()
    except Exception: pass
    return ""

def is_valid_pdf(path):
    try:
        with open(path,'rb') as f: head=f.read(5)
        if head != b'%PDF-': return False, "not %PDF header"
        r = subprocess.run(["file","-b",path], capture_output=True, text=True).stdout
        if "PDF" not in r: return False, "file says: %s" % r.strip()
        pages = pdfinfo_pages(path)
        if not pages: return False, "pdfinfo failed"
        sz = os.path.getsize(path)
        if sz < 20000: return False, "too small %d" % sz
        return True, pages
    except Exception as e:
        return False, str(e)

def download_one(url, dest_part, timeout=90, retries=2):
    for attempt in range(retries+1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept":"application/pdf,*/*"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                data = r.read()
            with open(dest_part,"wb") as f: f.write(data)
            return True, 200
        except urllib.error.HTTPError as e:
            return False, e.code
        except Exception as e:
            time.sleep(2+attempt*2)
    return False, "timeout/err"

def main():
    rows = read_manifest()
    # load catalog for authors/title by seq
    cat = {}
    with open(CAT, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            cat[r["sequence_id"]] = r
    # assign chunks: process OA-rows; chunk by order
    oa_idx = 0
    stats = {"ok":0,"fail":0,"skip":0}
    for row in rows:
        if row["download_status"] == "ok":
            stats["skip"]+=1; oa_idx+=1; continue
        if not row["pdf_source_url"]:
            continue
        oa_idx+=1
        chunk_n = (oa_idx-1)//50 + 1
        chunk_id = "chunk_%03d" % chunk_n
        chunk_dir = os.path.join(PDFS, chunk_id)
        os.makedirs(chunk_dir, exist_ok=True)
        seq = int(row["sequence_id"])
        c = cat.get(str(seq), {})
        author = first_author(c.get("authors",""))
        title_slug = slug(c.get("title",""))
        fname = "%04d_%s_%s.pdf" % (seq, author, title_slug)
        final = os.path.join(chunk_dir, fname)
        if os.path.exists(final) and os.path.getsize(final) > 20000:
            ok, pages = is_valid_pdf(final)
            if ok:
                row["download_status"]="ok"; row["local_path"]=final; row["chunk_id"]=chunk_id
                row["file_size"]=str(os.path.getsize(final)); row["page_count"]=pages
                row["sha256"]=sha256(final); row["downloaded_at"]=time.strftime("%Y-%m-%dT%H:%M:%S")
                stats["ok"]+=1; continue
        part = final + ".part"
        ok, code = download_one(row["pdf_source_url"], part)
        if not ok:
            row["download_status"]="failed"; row["http_status"]=str(code)
            row["retry_count"]=str(int(row.get("retry_count","0") or 0)+1)
            row["failure_reason"]=str(code); stats["fail"]+=1
            if os.path.exists(part): os.remove(part)
            print("[FAIL] seq %d %s : %s" % (seq, code, row["pdf_source_url"][:60]), flush=True)
            continue
        ok2, pages = is_valid_pdf(part)
        if not ok2:
            row["download_status"]="failed"; row["failure_reason"]="invalid pdf: %s"%pages
            row["retry_count"]=str(int(row.get("retry_count","0") or 0)+1); stats["fail"]+=1
            os.remove(part); continue
        os.rename(part, final)
        row["download_status"]="ok"; row["local_path"]=final; row["chunk_id"]=chunk_id
        row["file_size"]=str(os.path.getsize(final)); row["page_count"]=pages
        row["sha256"]=sha256(final); row["downloaded_at"]=time.strftime("%Y-%m-%dT%H:%M:%S")
        row["http_status"]="200"; stats["ok"]+=1
        print("[OK] seq %d -> %s/%s (%s pages)" % (seq, chunk_id, fname, pages), flush=True)
        write_manifest(rows)  # checkpoint after each success
    write_manifest(rows)
    # write per-chunk index.csv
    chunks = {}
    for row in rows:
        if row.get("chunk_id"):
            chunks.setdefault(row["chunk_id"], []).append(row)
    for cid, crows in chunks.items():
        cdir = os.path.join(PDFS, cid)
        os.makedirs(cdir, exist_ok=True)
        with open(os.path.join(cdir,"index.csv"),"w",newline="",encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=["sequence_id","doi","title","filename","sha256","page_count","file_size","status"])
            w.writeheader()
            for r in crows:
                w.writerow({"sequence_id":r["sequence_id"],"doi":r["doi"],"title":r["title"],
                    "filename": os.path.basename(r.get("local_path","")),"sha256":r.get("sha256",""),
                    "page_count":r.get("page_count",""),"file_size":r.get("file_size",""),
                    "status":r.get("download_status","")})
    print("=== DOWNLOAD DONE === ok=%d fail=%d skip(already)=%d" % (stats["ok"],stats["fail"],stats["skip"]), flush=True)

if __name__=="__main__":
    main()
