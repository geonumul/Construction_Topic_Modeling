"""
Recompute Trajtenberg originality per cluster from the persisted citations_enriched.csv
(cited IPC-3 already resolved by the D3 corpus scan) — no corpus rescan needed.
Originality(cluster) = mean over citing patents of [1 - sum_i (share of cited IPC-3 i)^2].
"""
import pandas as pd
from collections import Counter
from common import EXTRACTED, TABLES, log


def main():
    try:
        en = pd.read_csv(EXTRACTED / "citations_enriched.csv", dtype=str, keep_default_na=False)
        dt = pd.read_csv(TABLES / "doc_topics.csv", dtype={"pub_number": str})
    except Exception as e:
        log(f"originality_from_enriched: missing input ({e}) -> skip"); return
    topic = dict(zip(dt["pub_number"], dt["dominant_topic"]))
    # group enriched citations by citing patent
    en = en[en["cited_ipc3"] != ""]
    by_citing = {pub: g for pub, g in en.groupby("citing_pub")}

    rows = []
    for tid in sorted(set(int(t) for t in topic.values() if int(t) >= 0)):
        pubs = [p for p, t in topic.items() if int(t) == tid]
        vals = []
        for pub in pubs:
            g = by_citing.get(pub)
            if g is None:
                continue
            ipc = Counter()
            for codes in g["cited_ipc3"]:
                for c in codes.split(";"):
                    if c:
                        ipc[c] += 1
            tot = sum(ipc.values())
            if tot >= 3:
                vals.append(1 - sum((c / tot) ** 2 for c in ipc.values()))
        if vals:
            rows.append({"cluster_id": tid, "n_patents_with_orig": len(vals),
                         "originality_index": round(sum(vals) / len(vals), 4)})
    if rows:
        pd.DataFrame(rows).to_csv(TABLES / "cluster_originality.csv", index=False, encoding="utf-8-sig")
        log(f"originality_from_enriched: cluster_originality.csv ({len(rows)} clusters) "
            f"from {len(en)} classified citations")
    else:
        log("originality_from_enriched: insufficient classified citations -> not written")


if __name__ == "__main__":
    main()
