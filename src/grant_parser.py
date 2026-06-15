"""
grant_parser.py  —  Grant (PTGRXML) full-text extraction.

Input:  logs/matchable_grants_index.csv  (norm_number, Date Published, target_xml ...)
        USPTO_BULK_XML/ipg{YYMMDD}.xml    (concatenated us-patent-grant records)
Output (output/):
  - patents_full.jsonl     one patent per line (abstract/claims/description/refs ...)
  - citations.csv          one citation relation per line (Originality Index input)
  - abstracts_for_lda.csv  slim LDA input
Output (logs/):
  - parse_error_log.csv    extraction failures/anomalies (does not halt the run)

Run:
  python src/grant_parser.py            # full set
  python src/grant_parser.py 50         # 50-record year-stratified validation sample
"""
import re, sys, json, csv, statistics
from pathlib import Path
from collections import defaultdict, Counter
from lxml import etree
from tqdm import tqdm

sys.path.insert(0, str(Path(__file__).resolve().parent))
from normalization import normalize_docnum

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

BASE   = Path(r"D:\Construction_TopicModeling")
XMLDIR = BASE / "USPTO_BULK_XML"
LOGS   = BASE / "logs"
OUTPUT = BASE / "output"
INDEX  = LOGS / "matchable_grants_index.csv"
OUTPUT.mkdir(exist_ok=True); LOGS.mkdir(exist_ok=True)

# ----------------------------------------------------------- 헬퍼
def L(el):  # local-name (네임스페이스/주석 안전)
    return etree.QName(el.tag).localname if isinstance(el.tag, str) else "#"

def text_of(node):
    return re.sub(r"\s+", " ", " ".join(node.itertext())).strip() if node is not None else ""

def clas_symbol(c):
    """classification-cpc / classification-ipcr 엘리먼트 -> 'A01B69/008'."""
    g = {L(x): (x.text or "").strip() for x in c}
    sec, cls, sub = g.get("section",""), g.get("class",""), g.get("subclass","")
    mg, sg = g.get("main-group",""), g.get("subgroup","")
    if not (sec and cls): return ""
    return f"{sec}{cls}{sub}{mg}/{sg}" if mg else f"{sec}{cls}{sub}"

# 설명 섹션 분류용 헤딩 키워드
def section_of(heading):
    h = heading.upper()
    if "BACKGROUND" in h: return "background"
    if "SUMMARY"    in h: return "summary"
    if ("DETAILED DESCRIPTION" in h or "DESCRIPTION OF EMBODIMENT" in h
        or "DESCRIPTION OF THE PREFERRED" in h or "DETAILED DESCRIPTION OF" in h):
        return "detailed"
    return None

# ----------------------------------------------------------- 단일 레코드 추출
def extract_patent(r, source_file, dtd_version):
    pubref = r.xpath(".//publication-reference")[0]
    docnum = "".join(pubref.xpath(".//doc-number/text()"))
    kind   = "".join(pubref.xpath(".//kind/text()"))
    country= "".join(pubref.xpath(".//country/text()")) or "US"
    pdate  = "".join(pubref.xpath(".//date/text()"))
    appref = r.xpath(".//application-reference")
    fdate  = "".join(appref[0].xpath(".//date/text()")) if appref else ""

    # description 섹션 분류
    desc_nodes = r.xpath(".//description")
    sections = {"background":[], "summary":[], "detailed":[], "other":[]}
    if desc_nodes:
        cur = "other"
        for child in desc_nodes[0]:
            ln = L(child)
            if ln == "heading":
                sec = section_of("".join(child.itertext()))
                if sec: cur = sec
                continue
            if ln in ("p", "description-of-drawings"):
                t = text_of(child)
                if t: sections[cur].append(t)
    description = {k: "\n".join(v) for k, v in sections.items()}

    # claims
    claims = []
    for cl in r.xpath(".//claims/claim"):
        t = text_of(cl)
        if t: claims.append(t)

    # IPC / CPC (이 특허 자신)
    ipc = sorted({clas_symbol(c) for c in r.xpath(".//classifications-ipcr//classification-ipcr")} - {""})
    cpc = sorted({clas_symbol(c) for c in
                  r.xpath(".//classifications-cpc//main-cpc/classification-cpc | "
                          ".//classifications-cpc//further-cpc/classification-cpc")} - {""})

    # assignee (Grant) / 없으면 applicant (Application) 폴백
    assignees = []
    cand = r.xpath(".//assignees/assignee | .//assignee")
    if not cand:
        cand = r.xpath(".//us-applicants/us-applicant | .//applicants/applicant")
    for a in cand:
        org = "".join(a.xpath(".//orgname/text()"))
        if not org:
            ln_ = "".join(a.xpath(".//last-name/text()")); fn_ = "".join(a.xpath(".//first-name/text()"))
            org = (ln_ + " " + fn_).strip()
        cty = "".join(a.xpath(".//country/text()"))
        if org or cty: assignees.append({"name": org, "country": cty})

    # inventors
    inventors = []
    for iv in r.xpath(".//inventors/inventor"):
        ln_ = "".join(iv.xpath(".//last-name/text()")); fn_ = "".join(iv.xpath(".//first-name/text()"))
        cty = "".join(iv.xpath(".//country/text()"))
        nm = (fn_ + " " + ln_).strip()
        if nm: inventors.append({"name": nm, "country": cty})

    # references cited
    refs = []
    for cit in r.xpath(".//us-references-cited//us-citation | .//references-cited//citation"):
        category = "".join(cit.xpath(".//category/text()")).strip()
        nat = "".join(cit.xpath(".//classification-national//main-classification/text()")).strip()
        cpc_in = [clas_symbol(c) for c in cit.xpath(".//classification-cpc")]
        ipc_in = [clas_symbol(c) for c in cit.xpath(".//classification-ipcr")]
        pat = cit.xpath(".//patcit")
        if pat:
            cdoc = "".join(pat[0].xpath(".//doc-number/text()"))
            ccty = "".join(pat[0].xpath(".//country/text()"))
            refs.append({"type":"patcit", "cited_doc":cdoc, "cited_norm":normalize_docnum(cdoc),
                         "cited_country":ccty, "category":category,
                         "cited_ipc":";".join(sorted(set(ipc_in)-{''})),
                         "cited_cpc":";".join(sorted(set(cpc_in)-{''})),
                         "cited_national_class":nat, "npl_text":""})
        else:
            npl = "".join(cit.xpath(".//othercit//text()")) or text_of(cit.xpath(".//nplcit")[0]) if cit.xpath(".//nplcit") else ""
            refs.append({"type":"nplcit", "cited_doc":"", "cited_norm":"", "cited_country":"",
                         "category":category, "cited_ipc":"", "cited_cpc":"",
                         "cited_national_class":"", "npl_text":re.sub(r"\s+"," ",npl).strip()})

    return {
        "publication_number": normalize_docnum(docnum),
        "publication_number_raw": f"{country}{docnum}{kind}",
        "kind": kind,
        "publication_date": pdate,
        "filing_date": fdate,
        "title": "".join(r.xpath(".//invention-title//text()")).strip(),
        "abstract": text_of(r.xpath(".//abstract")[0]) if r.xpath(".//abstract") else "",
        "claims": claims,
        "description": description,
        "references_cited": refs,
        "assignee": assignees,
        "inventors": inventors,
        "ipc": ipc,
        "cpc": cpc,
        "dtd_version": dtd_version,
        "source_file": source_file,
    }

# ----------------------------------------------------------- 파일 스트리밍
_DTD = re.compile(r"us-patent-grant-(v\d+)")
def parse_file(xml_path, targets, errors):
    """targets: {norm_number: meta_row}. 매칭된 레코드 dict yield."""
    dtd = "unknown"; buf=[]; started=False
    with open(xml_path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            ls = line.lstrip()
            if ls.startswith("<!DOCTYPE") or "us-patent-grant-v" in ls:
                m = _DTD.search(line)
                if m: dtd = m.group(1)
            if ls.startswith("<us-patent-grant"):
                started=True; buf=[line]
            elif started:
                buf.append(line)
                if "</us-patent-grant>" in line:
                    started=False
                    try:
                        rec = etree.fromstring("".join(buf).encode("utf-8"))
                    except Exception as e:
                        continue
                    dn = rec.xpath(".//publication-reference//doc-number/text()")
                    if not dn: continue
                    nz = normalize_docnum(dn[0])
                    if nz in targets:
                        try:
                            yield extract_patent(rec, xml_path.name, dtd)
                        except Exception as e:
                            errors.append({"norm_number":nz, "source_file":xml_path.name,
                                           "error":repr(e)})

# ----------------------------------------------------------- main
def main():
    sample_n = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    import pandas as pd
    idx = pd.read_csv(INDEX, dtype=str, keep_default_na=False)

    if sample_n:
        # 연도 층화 샘플
        idx["yr"] = idx["Date Published"].str[:4]
        idx = (idx.groupby("yr", group_keys=False)
                  .apply(lambda g: g.head(max(1, sample_n*len(g)//len(idx)+1)))
                  .head(sample_n))
        suffix = f".sample{sample_n}"
    else:
        suffix = ""

    # 파일별 그룹핑
    by_file = defaultdict(dict)
    for _, row in idx.iterrows():
        by_file[row["target_xml"]][row["norm_number"]] = row.to_dict()
    total_targets = sum(len(v) for v in by_file.values())

    out_jsonl = OUTPUT / f"patents_full{suffix}.jsonl"
    out_cit   = OUTPUT / f"citations{suffix}.csv"
    out_lda   = OUTPUT / f"abstracts_for_lda{suffix}.csv"
    out_err   = LOGS   / f"parse_error_log{suffix}.csv"

    errors=[]; extracted=[]; found_norms=set()
    cit_f = open(out_cit, "w", newline="", encoding="utf-8-sig")
    cit_w = csv.writer(cit_f)
    cit_w.writerow(["citing_pub","cited_pub","cited_pub_normalized","cited_pub_country",
                    "cited_ipc","cited_cpc","cited_national_class",
                    "category","citation_type","cited_npl_text"])
    lda_f = open(out_lda, "w", newline="", encoding="utf-8-sig")
    lda_w = csv.writer(lda_f)
    lda_w.writerow(["pub_number","title","abstract","publication_date","ipc_primary"])

    with open(out_jsonl, "w", encoding="utf-8") as jf:
        for fname in tqdm(sorted(by_file), desc="files", unit="file"):
            xmlp = XMLDIR / fname
            if not xmlp.exists():
                for nz in by_file[fname]:
                    errors.append({"norm_number":nz,"source_file":fname,"error":"file_missing"})
                continue
            for p in parse_file(xmlp, by_file[fname], errors):
                jf.write(json.dumps(p, ensure_ascii=False) + "\n")
                extracted.append(p); found_norms.add(p["publication_number"])
                for rf in p["references_cited"]:
                    cit_w.writerow([p["publication_number"], rf["cited_doc"], rf["cited_norm"],
                                    rf["cited_country"], rf["cited_ipc"], rf["cited_cpc"],
                                    rf["cited_national_class"], rf["category"], rf["type"],
                                    rf["npl_text"]])
                lda_w.writerow([p["publication_number"], p["title"], p["abstract"],
                                p["publication_date"], p["ipc"][0] if p["ipc"] else ""])
    cit_f.close(); lda_f.close()

    # 매칭 실패(타깃에 있으나 파일에서 못 찾음)
    for fname, tg in by_file.items():
        for nz in tg:
            if nz not in found_norms and not any(e["norm_number"]==nz for e in errors):
                errors.append({"norm_number":nz,"source_file":fname,"error":"not_found_in_file"})
    if errors:
        with open(out_err,"w",newline="",encoding="utf-8-sig") as ef:
            w=csv.DictWriter(ef, fieldnames=["norm_number","source_file","error"]); w.writeheader()
            w.writerows(errors)

    # ----------------------- 통계
    print("\n"+"="*64); print(f"추출 완료 (target {total_targets})"); print("="*64)
    print(f"성공: {len(extracted)}  |  실패/이상: {len(errors)}")
    if extracted:
        utils = [p for p in extracted if not p["publication_number"][0:1].isalpha()
                 and p["kind"] not in ("S1","S","P2","P3")]
        ab_len = [len(p["abstract"]) for p in extracted]
        ab_empty_util = sum(1 for p in utils if not p["abstract"])
        ncit = [len(p["references_cited"]) for p in extracted]
        cit_ipc = sum(1 for p in extracted for rf in p["references_cited"] if rf["cited_ipc"] or rf["cited_cpc"])
        cit_total = sum(ncit)
        cats = Counter(rf["category"] for p in extracted for rf in p["references_cited"])
        types = Counter(rf["type"] for p in extracted for rf in p["references_cited"])
        sec_ok = sum(1 for p in extracted if p["description"]["detailed"])
        def med(x): return statistics.median(x) if x else 0
        print(f"\nAbstract 길이  평균 {sum(ab_len)/len(ab_len):.0f} / 중앙 {med(ab_len):.0f} chars")
        print(f"  utility 중 abstract 빈 비율: {ab_empty_util}/{len(utils)}")
        print(f"Citations/특허 평균 {sum(ncit)/len(ncit):.1f} / 중앙 {med(ncit):.0f}  (총 {cit_total})")
        print(f"  인용 중 IPC/CPC 분류 보유: {cit_ipc}/{cit_total} ({cit_ipc/max(cit_total,1)*100:.1f}%)")
        print(f"  category 분포: {dict(cats)}")
        print(f"  type 분포: {dict(types)}")
        print(f"description 'detailed' 섹션 추출 성공: {sec_ok}/{len(extracted)}")
        print(f"DTD 버전 분포: {dict(Counter(p['dtd_version'] for p in extracted))}")
        print(f"\n출력: {out_jsonl.name} / {out_cit.name} / {out_lda.name}"
              + (f" / {out_err.name}" if errors else ""))

if __name__ == "__main__":
    main()
