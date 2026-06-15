"""
application_parser.py  —  Application (US-PGPUB / APPXML) full-text extraction.

Reuses the shared extraction logic from grant_parser.py.
Differences:
  * record root tag: us-patent-application
  * 11-digit doc-number (e.g. 20260157254), kind=A1
  * no us-references-cited -> empty array allowed (no error)
  * no assignee -> us-applicants fallback (handled in shared extract_patent)

Input:  logs/unmatched_appxml_pending.csv  (application metadata)
        USPTO_BULK_Application_XML/ipa{YYMMDD}.xml  (matches currently held files)
Output (output/, integrated with Grant later):
  - patents_full_application.jsonl
  - abstracts_for_lda_application.csv
  - citations_application.csv
Output (logs/):
  - unmatched_application.csv
"""
import re, sys, json, csv, statistics
from pathlib import Path
from collections import defaultdict, Counter
import pandas as pd
from lxml import etree
from tqdm import tqdm

sys.path.insert(0, str(Path(__file__).resolve().parent))
from normalization import normalize_docnum
from grant_parser import extract_patent, _DTD

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

BASE   = Path(r"D:\Construction_TopicModeling")
XMLDIR = BASE / "USPTO_BULK_Application_XML"
LOGS   = BASE / "logs"
OUTPUT = BASE / "output"
META   = LOGS / "unmatched_appxml_pending.csv"
OUTPUT.mkdir(exist_ok=True); LOGS.mkdir(exist_ok=True)

def app_target(date_published, have):
    s = str(date_published).strip()
    if len(s) < 10: return None
    yy = s[2:4] + s[5:7] + s[8:10]
    return f"ipa{yy}.xml" if yy in have else None

def parse_file(xml_path, targets, errors):
    dtd="unknown"; buf=[]; started=False
    with open(xml_path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            ls = line.lstrip()
            if "us-patent-application-v" in ls:
                m=_DTD.search(line.replace("application","grant"))  # 동일 vNN 캡처
                m2=re.search(r"us-patent-application-(v\d+)", line)
                if m2: dtd=m2.group(1)
            if ls.startswith("<us-patent-application"):
                started=True; buf=[line]
            elif started:
                buf.append(line)
                if "</us-patent-application>" in line:
                    started=False
                    try:
                        rec=etree.fromstring("".join(buf).encode("utf-8"))
                    except Exception:
                        continue
                    dn=rec.xpath(".//publication-reference//doc-number/text()")
                    if not dn: continue
                    nz=normalize_docnum(dn[0])
                    if nz in targets:
                        try:
                            yield extract_patent(rec, xml_path.name, dtd)
                        except Exception as e:
                            errors.append({"norm_number":nz,"source_file":xml_path.name,"error":repr(e)})

def main():
    have=set()
    for p in XMLDIR.glob("ipa*.xml"):
        m=re.match(r"ipa(\d{6})",p.name)
        if m: have.add(m.group(1))

    df=pd.read_csv(META, dtype=str, keep_default_na=False)
    # Document ID -> norm_number 재구성 (이 CSV엔 Patent Number 컬럼 없음)
    def docnum_from_id(d):
        t=str(d).strip().split()
        if not t: return ""
        mid=t[1:-1] if (t[0].isalpha() and len(t[0])<=3) else t[:-1]
        return "".join(mid)
    df["norm_number"]=df["Document ID"].map(lambda d: normalize_docnum(docnum_from_id(d)))
    df["target_xml"]=df["Date Published"].map(lambda s: app_target(s, have))

    matchable=df[df["target_xml"].notna()].copy()
    nofile  =df[df["target_xml"].isna()].copy()
    print(f"Application 메타데이터 {len(df)} | 현재 매칭가능 {len(matchable)} | 파일없음 {len(nofile)}")

    by_file=defaultdict(dict)
    for _,row in matchable.iterrows():
        by_file[row["target_xml"]][row["norm_number"]]=row.to_dict()

    out_jsonl=OUTPUT/"patents_full_application.jsonl"
    out_cit  =OUTPUT/"citations_application.csv"
    out_lda  =OUTPUT/"abstracts_for_lda_application.csv"
    out_unm  =LOGS/"unmatched_application.csv"

    errors=[]; extracted=[]; found=set()
    cf=open(out_cit,"w",newline="",encoding="utf-8-sig"); cw=csv.writer(cf)
    cw.writerow(["citing_pub","cited_pub","cited_pub_normalized","cited_pub_country","cited_ipc",
                 "cited_cpc","cited_national_class","category","citation_type","cited_npl_text"])
    lf=open(out_lda,"w",newline="",encoding="utf-8-sig"); lw=csv.writer(lf)
    lw.writerow(["pub_number","title","abstract","publication_date","ipc_primary"])

    with open(out_jsonl,"w",encoding="utf-8") as jf:
        for fname in tqdm(sorted(by_file), desc="ipa files", unit="file"):
            xmlp=XMLDIR/fname
            if not xmlp.exists():
                for nz in by_file[fname]: errors.append({"norm_number":nz,"source_file":fname,"error":"file_missing"})
                continue
            for p in parse_file(xmlp, by_file[fname], errors):
                jf.write(json.dumps(p,ensure_ascii=False)+"\n")
                extracted.append(p); found.add(p["publication_number"])
                for rf in p["references_cited"]:
                    cw.writerow([p["publication_number"],rf["cited_doc"],rf["cited_norm"],rf["cited_country"],
                                 rf["cited_ipc"],rf["cited_cpc"],rf["cited_national_class"],
                                 rf["category"],rf["type"],rf["npl_text"]])
                lw.writerow([p["publication_number"],p["title"],p["abstract"],p["publication_date"],
                             p["ipc"][0] if p["ipc"] else ""])
    cf.close(); lf.close()

    # 미매칭(타깃이나 못 찾음) + 파일없음 -> unmatched_application.csv
    miss_rows=[]
    for fname,tg in by_file.items():
        for nz in tg:
            if nz not in found:
                row=dict(tg[nz]); row["reason"]="not_found_in_file"; miss_rows.append(row)
    for _,row in nofile.iterrows():
        d=row.to_dict(); d["reason"]="no_file_in_range"; miss_rows.append(d)
    if miss_rows:
        pd.DataFrame(miss_rows).to_csv(out_unm,index=False,encoding="utf-8-sig")

    # 통계
    n=len(extracted)
    print("\n"+"="*60); print(f"Application 추출 완료: {n}/{len(matchable)} (에러 {len(errors)})"); print("="*60)
    if n:
        ab=[len(p['abstract']) for p in extracted]; ncl=[len(p['claims']) for p in extracted]
        ab_empty=sum(1 for p in extracted if not p['abstract'].strip())
        sec={k:sum(1 for p in extracted if p['description'][k].strip()) for k in ('background','summary','detailed','other')}
        ncit=[len(p['references_cited']) for p in extracted]
        print(f"Abstract: 평균 {sum(ab)/n:.0f}/중앙 {statistics.median(ab):.0f}, 빈 건 {ab_empty}/{n}")
        print(f"Claims: 평균 {sum(ncl)/n:.1f}")
        print(f"description 섹션: {sec}")
        print(f"Citations: 평균 {sum(ncit)/n:.2f} (총 {sum(ncit)})  ← Application은 낮음 정상")
        print(f"IPC 보유 {sum(1 for p in extracted if p['ipc'])}/{n} | CPC 보유 {sum(1 for p in extracted if p['cpc'])}/{n}")
        print(f"Assignee/Applicant 보유 {sum(1 for p in extracted if p['assignee'])}/{n} | Inventors {sum(1 for p in extracted if p['inventors'])}/{n}")
        print(f"DTD 분포: {dict(Counter(p['dtd_version'] for p in extracted))}")
        print(f"kind 분포: {dict(Counter(p['kind'] for p in extracted))}")
    print(f"\n출력: {out_jsonl.name}/{out_lda.name}/{out_cit.name}" + (f"/{out_unm.name}" if miss_rows else ""))

if __name__=="__main__":
    main()
