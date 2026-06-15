# Construction Safety Robot — Patent Topic Modeling

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
