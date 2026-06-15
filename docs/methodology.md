# Methodology

## 1. Search queries

> Record the exact queries used to assemble the datasets here so the study is reproducible.

- **USPTO Patent Public Search** — `<insert exact query / filters / date run>` → 1,334 records.
- **Scopus** — `<insert exact query / filters / date run>`.

## 2. doc-number normalization

Patent numbers in the metadata export and in the bulk XML differ in formatting
(commas, leading zeros, country prefixes, kind codes). Both sides are normalized with
one shared function (`src/normalization.py`) before matching:

| Rule | Action | Example |
|------|--------|---------|
| R1 | strip whitespace, uppercase | |
| R2 | drop leading `US` country prefix | `US 12651200` → `12651200` |
| R3 | remove comma / space / hyphen / slash | `12,635,592` → `12635592` |
| R4 | split alpha prefix (`D`, `RE`, `PP`, ...) from numeric core | |
| R5 | strip leading zeros from numeric core | `D0696836` → `D696836` |
| R6 | recombine prefix + cleaned core | `RE049864` → `RE49864` |

A before/after table is written to `logs/normalization_log.csv` for auditing.

## 3. Metadata classification

The metadata export carries a `Document ID` (e.g. `US 12651200 B2`, `US 20260161801 A1`).
Records are split by kind code:

- kind `A` followed by a digit (`A1`, `A2`, ...) → pre-grant publication (**US-PGPUB**, application set).
- otherwise (`A`, `B1`, `B2`, `E`, `S*`, `P*`) → granted patent (**USPAT**, grant set).

Grants are matched against PTGRXML, applications against APPXML.

## 4. Matching

Each record's publication date maps deterministically to a weekly bulk file:

- Grant publication date `YYYY-MM-DD` → `ipg{YYMMDD}.xml`.
- Application publication date `YYYY-MM-DD` → `ipa{YYMMDD}.xml`.

Records whose target weekly file is outside the locally held date range are written to
`logs/unmatched_*.csv` with the reason, rather than dropped silently.

## 5. XML parsing

Weekly bulk files are concatenations of many `<us-patent-grant>` /
`<us-patent-application>` records, each with its own XML declaration and DTD. Files are
streamed line by line; each record is isolated and parsed individually (memory-bounded).

The DTD version varies over time (`v44`, `v45`, `v46`, `v47`); the tags used for
extraction (`publication-reference`, `abstract`, `claims`, `description`,
`us-references-cited`, `classifications-cpc`, `classifications-ipcr`) are stable across
all observed versions, so a single parser handles every year. The DTD version is recorded
per record for traceability.

## 6. Revision files

USPTO re-issues corrected weekly files (`ipg{YYMMDD}_r1`, `_r2`, ...). When a record's
publication date matches a revised week, the latest revision (`_r2` > `_r1` > base) is
preferred so the most recent corrected text is used.

## 7. Citations

Each cited reference is captured with: cited document number (raw + normalized), cited
country, citation category (`cited by examiner` vs `cited by applicant`), and citation
type (`patcit` patent literature vs `nplcit` non-patent literature).

Bulk citation blocks do **not** carry the cited patent's IPC/CPC classification. Computing
an originality index over cited technology classes therefore requires a separate join of
each cited document number back to its own classification (a later enrichment step). The
normalized cited number and cited country are stored to support that join.
