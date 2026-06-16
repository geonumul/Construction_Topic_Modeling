# Construction Safety Robot — Patent Topic Modeling

## 개요

건설 현장의 안전을 위한 로봇·드론·센서·인공지능 기술이 지난 10여 년간 어떻게 발전했는지를
미국 특허 1,117건과 학술 논문 3,675건으로 분석한 프로젝트다. 문서를 토픽 모델링으로 15개
기술 주제로 분류하고, 주제별로 (1) 최근 활발도, (2) 여러 산업이 섞인 융합도, (3) 연구와
특허 사이의 시차, (4) 주도 국가·조직을 분석했다.

가장 뚜렷한 결과는 이 분야 특허를 보유한 조직 1,150곳 중 건설회사가 16곳뿐이고 나머지가
IBM·삼성·보험사·보잉 등 타 산업 대기업이었다는 점이다. 즉 건설안전 기술이 외부 산업에서
유입되어 융합되고 있다. 전문 용어는 보고서 본문에서 풀어 설명하고 끝에 용어 사전을 둔다.

- 결과 보고서(용어 풀이 포함): [`final_report.md`](final_report.md)
- 요약: [`overnight_summary.md`](overnight_summary.md)

아래는 데이터 추출·분석 코드 파이프라인에 대한 기술 설명이다.

---

Full-text extraction pipeline for analyzing patents related to construction safety
robotics. Patent metadata from a patent search is matched against USPTO bulk
full-text XML to extract abstracts, claims, descriptions, and cited references for
downstream topic modeling (LDA) and citation-network analysis.

## Data sources

- **USPTO Patent Grant Full-Text Data (PTGRXML)** — weekly `ipg{YYMMDD}.xml` files.
- **USPTO Patent Application Full-Text Data (APPXML)** — weekly `ipa{YYMMDD}.xml` files.
- **Patent metadata** — export from USPTO Patent Public Search (1,334 records).
- **Bibliometric metadata** — Scopus search export.

> Raw bulk XML (hundreds of GB), the metadata exports, and generated outputs are
> **not** tracked in this repository (see `.gitignore`). The Scopus export is subject
> to its license and is not redistributed here.
>
> Search queries used to build the patent and bibliometric sets are recorded in
> `docs/methodology.md`.

## Repository layout

```
.
├── src/
│   ├── normalization.py        # doc-number normalization (single source of truth)
│   ├── grant_parser.py         # PTGRXML (grant) full-text extraction
│   └── application_parser.py   # APPXML (application) full-text extraction
├── scripts/
│   └── build_matching_index.py # metadata -> normalized matching index
├── docs/
│   ├── methodology.md          # extraction methodology and design decisions
│   └── data_dictionary.md      # output schema (jsonl / csv fields)
├── requirements.txt
└── .gitignore
```

Local-only (git-ignored) working directories expected alongside the code:

```
USPTO_BULK_XML/               # grant weekly XML
USPTO_BULK_Application_XML/   # application weekly XML
uspto/  scopus/               # metadata inputs
logs/                         # matching index, normalization log, unmatched lists
output/                       # extracted datasets
```

## Pipeline

```bash
pip install -r requirements.txt

# 1) Build the matching index from metadata (writes to logs/)
python scripts/build_matching_index.py

# 2) Extract grant full text (writes to output/)
python src/grant_parser.py            # full set
python src/grant_parser.py 50         # 50-record stratified validation sample

# 3) Extract application full text (writes to output/)
python src/application_parser.py
```

### Outputs (`output/`)

| File | Description |
|------|-------------|
| `patents_full.jsonl` | one patent per line: title, abstract, claims, description, references, classifications |
| `citations.csv` | one citation relation per line (for citation-network / originality analysis) |
| `abstracts_for_lda.csv` | slim abstract table for topic modeling |

See `docs/data_dictionary.md` for the full field schema.

## Notes

- Paths are configured at the top of each script (`BASE = D:\Construction_TopicModeling`).
  Adjust them to your local data location before running.
- The grant and application parsers share `extract_patent` and the normalization rules,
  so both datasets use an identical, auditable matching procedure.

## Author

geonumul
