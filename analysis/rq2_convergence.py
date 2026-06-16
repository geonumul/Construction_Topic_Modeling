"""
RQ2: multi-dimensional convergence assessment per cluster (LDA topic = cluster unit).
 D1 CPC mixing (Caviggioli 2016): subclass Shannon entropy + construction vs external ratio
 D2 Assignee industry (Sick 2019): external (non-construction) assignee share
 D4 Convergence score: z-standardized mean of the dimensions (+ originality if available)
D3 (originality) is produced by the separate, heavier rq2_originality.py.
"""
import math
import numpy as np
import pandas as pd
from collections import Counter
from common import EXTRACTED, TABLES, log, read_jsonl

CONSTRUCTION_CPC = {"E01", "E02", "E03", "E04", "E05", "E21", "B66", "B28"}
IND_KEYWORDS = {
    "construction": ["construction", "engineering", "build", "infrastructure",
                     "civil", "contractor", "concrete", "cement"],
    "mobility":     ["auto", "motor", "vehicle", "mobility", "robot", "drone",
                     "aerial", "aviation"],
    "tech_ai":      ["tech", "electronic", "samsung", "google", "ibm", "microsoft",
                     "intel", "qualcomm", "sony", "nvidia", "software", "digital",
                     "semiconductor", "huawei", "lg ", "amazon", "meta"],
    "finance":      ["insurance", "bank", "financial", "capital", "holdings"],
}


def classify_industry(name):
    n = (name or "").lower()
    for ind, kws in IND_KEYWORDS.items():
        if any(k in n for k in kws):
            return ind
    return "other"


def shannon(counter):
    tot = sum(counter.values())
    if tot == 0:
        return 0.0
    return -sum((c / tot) * math.log(c / tot, 2) for c in counter.values() if c)


def main():
    patents = {r["publication_number"]: r for r in read_jsonl(EXTRACTED / "patents_full.jsonl")}
    try:
        dt = pd.read_csv(TABLES / "doc_topics.csv", dtype={"pub_number": str})
    except Exception as e:
        log(f"RQ2: doc_topics.csv missing ({e}) -> cannot define clusters, abort"); return
    topic = dict(zip(dt["pub_number"], dt["dominant_topic"]))

    rows = []
    for tid in sorted(set(t for t in topic.values() if t >= 0)):
        pubs = [p for p, t in topic.items() if t == tid and p in patents]
        cpc_sub = Counter()
        constr = ext = 0
        ind_counter = Counter()
        for p in pubs:
            r = patents[p]
            for c in r.get("cpc", []):
                sub = c[:3]
                cpc_sub[sub] += 1
                if sub in CONSTRUCTION_CPC:
                    constr += 1
                else:
                    ext += 1
            for a in r.get("assignee", []):
                ind_counter[classify_industry(a.get("name", ""))] += 1
        tot_cpc = constr + ext
        tot_assignee = sum(ind_counter.values())
        ext_assignee = tot_assignee - ind_counter.get("construction", 0)
        rows.append({
            "cluster_id": int(tid),
            "n_patents": len(pubs),
            "cpc_subclass_entropy": round(shannon(cpc_sub), 4),
            "n_cpc_subclasses": len(cpc_sub),
            "construction_cpc_ratio": round(constr / tot_cpc, 4) if tot_cpc else 0.0,
            "external_cpc_ratio": round(ext / tot_cpc, 4) if tot_cpc else 0.0,
            "assignee_external_ratio": round(ext_assignee / tot_assignee, 4) if tot_assignee else 0.0,
            "industry_mix": dict(ind_counter),
        })
    d = pd.DataFrame(rows)
    if d.empty:
        log("RQ2: no clusters -> abort"); return
    d.to_csv(TABLES / "cluster_cpc_diversity.csv",
             columns=["cluster_id", "n_patents", "cpc_subclass_entropy", "n_cpc_subclasses",
                      "construction_cpc_ratio", "external_cpc_ratio"],
             index=False, encoding="utf-8-sig")
    d[["cluster_id", "n_patents", "assignee_external_ratio", "industry_mix"]].to_csv(
        TABLES / "cluster_assignee_industry.csv", index=False, encoding="utf-8-sig")
    log(f"D1/D2: cluster_cpc_diversity.csv + cluster_assignee_industry.csv ({len(d)} clusters)")

    # D4 convergence score (z-mean of available dimensions)
    dims = ["cpc_subclass_entropy", "external_cpc_ratio", "assignee_external_ratio"]
    # optional originality
    try:
        orig = pd.read_csv(TABLES / "cluster_originality.csv")
        d = d.merge(orig[["cluster_id", "originality_index"]], on="cluster_id", how="left")
        dims.append("originality_index")
        log("D4: originality_index merged in")
    except Exception:
        log("D4: cluster_originality.csv not present -> convergence from 3 dims")

    def z(s):
        s = s.astype(float)
        return (s - s.mean()) / (s.std(ddof=0) or 1.0)
    zsum = sum(z(d[c].fillna(d[c].mean())) for c in dims)
    d["convergence_score"] = (zsum / len(dims)).round(4)
    d = d.sort_values("convergence_score", ascending=False)
    d[["cluster_id", "n_patents"] + [c for c in dims if c in d] + ["convergence_score"]].to_csv(
        TABLES / "cluster_convergence_scores.csv", index=False, encoding="utf-8-sig")
    top = d.head(3)["cluster_id"].tolist()
    log(f"D4: cluster_convergence_scores.csv saved | top-3 external-convergence clusters={top}")


if __name__ == "__main__":
    main()
