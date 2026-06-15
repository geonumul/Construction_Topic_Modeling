# Data dictionary

## `output/patents_full.jsonl` — one JSON object per line

| Field | Type | Description |
|-------|------|-------------|
| `publication_number` | string | normalized publication number (matching key) |
| `publication_number_raw` | string | country + doc-number + kind as in the XML (e.g. `US08866606B1`) |
| `kind` | string | kind code (`B1`, `B2`, `A1`, ...) |
| `publication_date` | string | `YYYYMMDD` |
| `filing_date` | string | `YYYYMMDD` |
| `title` | string | invention title |
| `abstract` | string | abstract text |
| `claims` | string[] | one entry per claim |
| `description` | object | `{ background, summary, detailed, other }` section text |
| `references_cited` | object[] | cited references (see below) |
| `assignee` | object[] | `{ name, country }` (applicant used as fallback for applications) |
| `inventors` | object[] | `{ name, country }` |
| `ipc` | string[] | IPC symbols of this patent |
| `cpc` | string[] | CPC symbols of this patent |
| `dtd_version` | string | source DTD version (`v44`–`v47`) |
| `source_file` | string | originating weekly XML file |

### `references_cited[]` element

| Field | Description |
|-------|-------------|
| `type` | `patcit` (patent) or `nplcit` (non-patent literature) |
| `cited_doc` | cited document number as written |
| `cited_norm` | normalized cited document number (join key) |
| `cited_country` | cited document country |
| `category` | `cited by examiner` or `cited by applicant` |
| `cited_ipc` / `cited_cpc` | cited classifications when present (usually empty in bulk data) |
| `cited_national_class` | US national classification when present |
| `npl_text` | non-patent-literature citation text (for `nplcit`) |

## `output/citations.csv` — one citation relation per line

`citing_pub, cited_pub, cited_pub_normalized, cited_pub_country, cited_ipc, cited_cpc,
cited_national_class, category, citation_type, cited_npl_text`

## `output/abstracts_for_lda.csv` — topic-modeling input

`pub_number, title, abstract, publication_date, ipc_primary`

## `logs/` tables

| File | Description |
|------|-------------|
| `normalization_log.csv` | before/after normalization for every metadata record |
| `matchable_grants_index.csv` | grant records with a resolved target weekly file |
| `unmatched_appxml_pending.csv` | application records awaiting APPXML |
| `unmatched_pre2014.csv` | grant records published before the held range |
| `unmatched_missing_file.csv` | records whose target weekly file is absent |
| `unmatched_application.csv` | application records not found / out of range |
