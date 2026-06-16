"""A3: integrate Grant + Application extraction into extracted/ unified dataset."""
import csv, json, shutil
import pandas as pd
from common import OUTPUT, EXTRACTED, TABLES, log, read_jsonl

def main():
    g = OUTPUT / "patents_full.jsonl"
    a = OUTPUT / "patents_full_application.jsonl"
    recs = []
    n_g = n_a = 0
    if g.exists():
        for r in read_jsonl(g): recs.append(r); n_g += 1
    if a.exists():
        for r in read_jsonl(a): recs.append(r); n_a += 1
    log(f"A3 integrate: grants={n_g} apps={n_a} total={len(recs)}")

    # dedup by publication_number (keep grant over application if collision)
    seen = {}
    for r in recs:
        k = r["publication_number"]
        if k not in seen:
            seen[k] = r
        else:
            # prefer grant (has citations) over application
            if not seen[k].get("references_cited") and r.get("references_cited"):
                seen[k] = r
    uniq = list(seen.values())
    if len(uniq) != len(recs):
        log(f"A3 dedup: {len(recs)} -> {len(uniq)} (removed {len(recs)-len(uniq)} dup pub numbers)")

    # write unified jsonl
    out_jsonl = EXTRACTED / "patents_full.jsonl"
    with open(out_jsonl, "w", encoding="utf-8") as f:
        for r in uniq:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    # abstracts_for_lda (combined)
    with open(EXTRACTED / "abstracts_for_lda.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f); w.writerow(["pub_number","title","abstract","publication_date","ipc_primary","kind"])
        for r in uniq:
            w.writerow([r["publication_number"], r["title"], r["abstract"],
                        r["publication_date"], r["ipc"][0] if r["ipc"] else "", r["kind"]])

    # citations (grant citations only; append application if any)
    out_cit = EXTRACTED / "citations.csv"
    src_cit = OUTPUT / "citations.csv"
    if src_cit.exists():
        shutil.copyfile(src_cit, out_cit)
        # append application citations if non-trivial
        app_cit = OUTPUT / "citations_application.csv"
        if app_cit.exists():
            with open(app_cit, encoding="utf-8-sig") as af:
                rows = af.readlines()[1:]  # skip header
            if rows:
                with open(out_cit, "a", encoding="utf-8-sig") as of:
                    of.writelines(rows)
    n_cit = sum(1 for _ in open(out_cit, encoding="utf-8-sig")) - 1 if out_cit.exists() else 0
    log(f"A3 outputs: patents_full.jsonl={len(uniq)} citations.csv={n_cit} abstracts_for_lda.csv={len(uniq)}")

    # join verification vs metadata
    try:
        meta = pd.read_csv(BASE_uspto(), dtype=str, keep_default_na=False)
        log(f"A3 join check: metadata rows={len(meta)} extracted={len(uniq)} coverage={len(uniq)/len(meta)*100:.1f}%")
    except Exception as e:
        log(f"A3 join check skipped: {e}")
    return len(uniq)

def BASE_uspto():
    from common import BASE
    return BASE / "uspto" / "SearchResults20260614151206.csv"

if __name__ == "__main__":
    main()
