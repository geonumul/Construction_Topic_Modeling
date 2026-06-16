"""2x2 novelty x growth promising matrix on the canonical (combined) patent clusters."""
import pandas as pd
from common import EXTRACTED, TABLES, FIGURES, log, read_jsonl
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def main():
    pats = {r["publication_number"]: int((r.get("publication_date") or "0")[:4] or 0)
            for r in read_jsonl(EXTRACTED / "patents_full.jsonl")}
    dt = pd.read_csv(TABLES / "doc_topics.csv", dtype={"pub_number": str})
    dt["year"] = dt["pub_number"].map(pats)
    dt = dt[(dt["dominant_topic"] >= 0) & dt["year"].between(2000, 2026)]

    rows = []
    for tid, g in dt.groupby("dominant_topic"):
        yrs = g["year"]; n = len(g)
        novelty = (yrs >= 2021).mean()
        recent = yrs[(yrs >= 2021) & (yrs <= 2025)]
        cby = recent.value_counts().sort_index()
        if len(cby) >= 2 and cby.iloc[0] > 0:
            span = cby.index[-1] - cby.index[0]
            cagr = (cby.iloc[-1] / cby.iloc[0]) ** (1 / max(span, 1)) - 1
        else:
            cagr = 0.0
        rows.append({"cluster_id": int(tid), "n_patents": n,
                     "novelty": round(float(novelty), 4), "growth": round(float(cagr), 4)})
    m = pd.DataFrame(rows)
    if m.empty:
        log("2x2: empty -> skip"); return
    nm, gm = m["novelty"].median(), m["growth"].median()
    m["quadrant"] = m.apply(lambda r: ("Promising" if r.novelty >= nm and r.growth >= gm else
                                       "Emerging" if r.novelty >= nm else
                                       "Established" if r.growth >= gm else "Declining"), axis=1)
    m.to_csv(TABLES / "clusters_2x2.csv", index=False, encoding="utf-8-sig")
    log(f"2x2: {len(m)} clusters | Promising={int((m.quadrant=='Promising').sum())} "
        f"(medians nov={nm:.3f} growth={gm:.3f})")
    try:
        plt.figure(figsize=(8, 6))
        col = {"Promising": "#d62728", "Emerging": "#1f77b4", "Established": "#2ca02c", "Declining": "#7f7f7f"}
        for q, gg in m.groupby("quadrant"):
            plt.scatter(gg.novelty, gg.growth, s=gg.n_patents * 6, alpha=0.7, label=q, color=col.get(q, "gray"))
            for _, r in gg.iterrows():
                plt.annotate(str(r.cluster_id), (r.novelty, r.growth), fontsize=8)
        plt.axvline(nm, ls="--", c="gray", lw=0.8); plt.axhline(gm, ls="--", c="gray", lw=0.8)
        plt.xlabel("Novelty (share 2021-2026)"); plt.ylabel("Growth (CAGR 2021-2025)")
        plt.title("RQ1 — cluster 2x2 (combined topics)"); plt.legend(); plt.tight_layout()
        plt.savefig(FIGURES / "2x2_matrix.png", dpi=130); plt.close()
        log("2x2: figure saved")
    except Exception as e:
        log(f"2x2 figure FAILED: {e!r}")


if __name__ == "__main__":
    main()
