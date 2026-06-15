"""
build_matching_index.py  —  metadata load + normalization + matching index.

Input:  uspto/SearchResults20260614151206.csv  (metadata, 1,334 records)
Output (logs/):
  - normalization_log.csv          before/after normalization table (audit trail)
  - matchable_grants_index.csv      Grant 2014-2026 match targets + target XML file
  - unmatched_appxml_pending.csv    US-PGPUB metadata (process once APPXML arrives)
  - unmatched_pre2014.csv           pre-2014 Grant metadata (out of current range)

doc-number normalization rules are the single source of truth in src/normalization.py.
"""
import re
import sys
import pandas as pd
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from normalization import normalize_docnum

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

BASE = Path(r"D:\Construction_TopicModeling")
CSV  = BASE / "uspto" / "SearchResults20260614151206.csv"
XMLDIR = BASE / "USPTO_BULK_XML"
LOGS = BASE / "logs"
LOGS.mkdir(exist_ok=True)

# 이 CSV에는 Source/Kind Code/Patent Number 컬럼이 없고 "Document ID"만 있다.
#   예) "US 12651200 B2"   -> number=12651200, kind=B2  -> Grant(USPAT)
#       "US 20260161801 A1" -> number=20260161801, kind=A1 -> Application(US-PGPUB)
#       "US RE49864 E"      -> number=RE49864,  kind=E   -> Grant(USPAT, reissue)
# 분류 규칙: kind 가 'A' + 숫자 (A1/A2/A9 ...) 이면 사전공개(Application=US-PGPUB),
#            그 외(A 단독, B1/B2/E/S*/P* ...)는 등록(Grant=USPAT).
_APPKIND = re.compile(r"^A[0-9]")
def parse_document_id(docid: str):
    toks = str(docid).strip().split()
    if not toks:
        return ("", "", "")
    country = toks[0] if toks[0].isalpha() and len(toks[0]) <= 3 else ""
    kind = toks[-1]
    mid = toks[1:-1] if country else toks[:-1]
    number = "".join(mid) if mid else ""
    source = "US-PGPUB" if _APPKIND.match(kind) else "USPAT"
    return (number, kind, source)

# ---------------------------------------------------------------- 로드
df = pd.read_csv(CSV, dtype=str, keep_default_na=False)
df["__row"] = range(len(df))
n = len(df)

# Document ID -> (Patent Number, Kind Code, Source) 재구성
parsed = df["Document ID"].map(parse_document_id)
df["Patent Number"] = parsed.map(lambda t: t[0])
df["Kind Code"]     = parsed.map(lambda t: t[1])
df["Source"]        = parsed.map(lambda t: t[2])

# 재구성 검증: 알려진 분포(Grant 551 / App 783, kind A1:783 B2:418 B1:90 A:42 E:1)와 대조
print("[재구성 검증] Source:", df["Source"].value_counts().to_dict())
print("[재구성 검증] Kind  :", df["Kind Code"].value_counts().to_dict())

# 정규화
df["norm_number"] = df["Patent Number"].map(normalize_docnum)

# 정규화 로그 저장
norm_log = df[["__row", "Source", "Kind Code", "Document ID", "Patent Number",
               "norm_number", "Date Published", "Filing Date"]].rename(
    columns={"Patent Number": "raw_number"})
norm_log.to_csv(LOGS / "normalization_log.csv", index=False, encoding="utf-8-sig")

# ---------------------------------------------------------------- 분기
is_grant = df["Source"].str.strip().eq("USPAT")
grants = df[is_grant].copy()
apps   = df[~is_grant].copy()

# 발행연도
def pub_year(s):
    s = str(s).strip()
    return int(s[:4]) if s[:4].isdigit() else 0
grants["pub_year"] = grants["Date Published"].map(pub_year)

# 사용 가능한 ipg 파일의 날짜(YYMMDD) 집합 (revision 포함, base와 동일 날짜)
ipg_dates = set()
for p in XMLDIR.glob("ipg*.xml"):
    m = re.match(r"ipg(\d{6})", p.name)
    if m:
        ipg_dates.add(m.group(1))

def target_xml(date_published: str):
    """Date Published(YYYY-MM-DD) -> ipg 주간 XML 파일명 (정확 일치)."""
    s = str(date_published).strip()
    if len(s) < 10:
        return None
    yymmdd = s[2:4] + s[5:7] + s[8:10]
    return f"ipg{yymmdd}.xml" if yymmdd in ipg_dates else None

in_range = grants["pub_year"].between(2014, 2026)
grants_inrange = grants[in_range].copy()
grants_pre2014 = grants[grants["pub_year"] < 2014].copy()

grants_inrange["target_xml"] = grants_inrange["Date Published"].map(target_xml)

# 타깃 ipg 파일 존재 여부로 다시 분리
has_file_mask = grants_inrange["target_xml"].notna()
grants_matchable = grants_inrange[has_file_mask].copy()      # 파일 존재 -> 실제 매칭 대상
grants_nofile    = grants_inrange[~has_file_mask].copy()      # 파일 공백(컷오프/누락주)

# ---------------------------------------------------------------- 저장
keep_meta = [c for c in df.columns if not c.startswith("__")]

idx_cols = ["norm_number", "Patent Number", "Kind Code",
            "Date Published", "Filing Date", "target_xml"]
grants_matchable[idx_cols].to_csv(
    LOGS / "matchable_grants_index.csv", index=False, encoding="utf-8-sig")

apps[keep_meta].to_csv(LOGS / "unmatched_appxml_pending.csv", index=False, encoding="utf-8-sig")
grants_pre2014[keep_meta].to_csv(LOGS / "unmatched_pre2014.csv", index=False, encoding="utf-8-sig")
grants_nofile[keep_meta + ["norm_number"]].to_csv(
    LOGS / "unmatched_missing_file.csv", index=False, encoding="utf-8-sig")

# ---------------------------------------------------------------- 검증 리포트
print("="*64)
print("Step 2 매칭 인덱스 구축 — 분포 검증")
print("="*64)
print(f"전체 메타데이터               : {n}")
print(f"  Grant (USPAT)              : {len(grants)}")
print(f"    ├ 2014-2026 (매칭 대상)   : {len(grants_inrange)}")
print(f"    └ pre-2014 (현재 제외)    : {len(grants_pre2014)}")
print(f"  Application (US-PGPUB 대기) : {len(apps)}")
s = len(grants_inrange) + len(grants_pre2014) + len(apps)
print(f"합계 검증                     : {s}  ({'OK' if s==n else '!!MISMATCH'})")

# 타깃 XML 매핑 성공 여부 (날짜->파일 존재)
print(f"\n매칭 대상 448건 세부:")
print(f"  실제 매칭 가능(파일 존재)   : {len(grants_matchable)}")
print(f"  파일 공백(컷오프/누락주)    : {len(grants_nofile)}")
if len(grants_nofile):
    print("  [파일 공백 상세]")
    print(grants_nofile[["norm_number", "Date Published", "target_xml"]]
          .assign(target_xml=grants_nofile["Date Published"].map(
              lambda s: "ipg"+s[2:4]+s[5:7]+s[8:10]+".xml"))
          .to_string(index=False))

print(f"\nipg 파일 보유 날짜 수(개별)   : {len(ipg_dates)}")
print("저장 완료: normalization_log.csv / matchable_grants_index.csv /")
print("           unmatched_appxml_pending.csv / unmatched_pre2014.csv /")
print("           unmatched_missing_file.csv")

# ---------------------------------------------------------------- 샘플 매칭 테스트
print("\n" + "="*64)
print("샘플 매칭 테스트 (연도/형식 다양하게 5건)")
print("="*64)
from lxml import etree

def stream_find(xml_path, targets):
    """주간 XML 스트리밍하며 targets(정규화 docnum 집합) 매칭 레코드 반환."""
    found = {}
    buf=[]; started=False
    with open(xml_path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            if line.lstrip().startswith("<us-patent-grant"):
                started=True; buf=[line]
            elif started:
                buf.append(line)
                if "</us-patent-grant>" in line:
                    started=False
                    try:
                        r=etree.fromstring("".join(buf).encode("utf-8"))
                    except Exception:
                        continue
                    dn=r.xpath(".//publication-reference//doc-number/text()")
                    if dn:
                        nz=normalize_docnum(dn[0])
                        if nz in targets and nz not in found:
                            found[nz]=r
                            if len(found)==len(targets):
                                break
    return found

# 연도 다양하게 픽: 각 대표 연도에서 1건씩
sample_rows=[]
for yr in [2014, 2017, 2020, 2023, 2026]:
    sub=grants_matchable[grants_matchable["pub_year"]==yr]
    if len(sub):
        sample_rows.append(sub.iloc[0])
import pandas as _pd
sample=_pd.DataFrame(sample_rows)

for _, row in sample.iterrows():
    xmlf = XMLDIR / row["target_xml"]
    found = stream_find(xmlf, {row["norm_number"]})
    if row["norm_number"] in found:
        r=found[row["norm_number"]]
        title="".join(r.xpath(".//invention-title//text()"))[:55]
        ncite=len(r.xpath('.//us-references-cited//us-citation'))
        hasab=bool(r.xpath(".//abstract"))
        print(f"  [OK] {row['norm_number']:>10} ({row['Date Published']}, {row['Kind Code']}) "
              f"in {row['target_xml']} | abstract={hasab} cites={ncite} | {title}")
    else:
        print(f"  [FAIL] {row['norm_number']} not found in {row['target_xml']}")
