"""
E1-revised (Momeni & Rost): per-topic science->technology time lag using the combined
LDA topic space. For each topic: compare paper publication years vs patent filing years.
lag = (patent quantile year) - (paper quantile year); positive => technology lags science.
"""
import numpy as np
import pandas as pd
from common import TABLES, FIGURES, log
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def qyear(years, q):
    ys = sorted(years)
    if not ys:
        return None
    if q == 0:
        return ys[0]
    idx = int(np.ceil(q * len(ys))) - 1
    return ys[max(0, min(idx, len(ys) - 1))]


def main():
    dt = pd.read_csv(TABLES / "doc_topics_combined.csv")
    dt["year"] = pd.to_numeric(dt["year"], errors="coerce")
    dt = dt[(dt["dominant_topic"] >= 0) & dt["year"].between(1990, 2026)]

    rows = []
    for tid, g in dt.groupby("dominant_topic"):
        pap = g[g["domain"] == "paper"]["year"].tolist()
        pat = g[g["domain"] == "patent"]["year"].tolist()
        if len(pap) < 3 or len(pat) < 3:
            continue
        rec = {"topic_id": int(tid), "n_papers": len(pap), "n_patents": len(pat),
               "paper_median": float(np.median(pap)), "patent_median": float(np.median(pat))}
        for q, lbl in [(0, "first"), (0.25, "q25"), (0.5, "median")]:
            py, ty = qyear(pap, q), qyear(pat, q)
            rec[f"lag_{lbl}"] = (ty - py) if (py is not None and ty is not None) else None
        rec["lag_median_years"] = rec["patent_median"] - rec["paper_median"]
        rows.append(rec)

    if not rows:
        log("E1-revised: no topics with both papers and patents (>=3 each) -> skip"); return
    d = pd.DataFrame(rows).sort_values("lag_median_years")
    d.to_csv(TABLES / "cluster_time_lag_combined.csv", index=False, encoding="utf-8-sig")
    overall = d["lag_median_years"].median()
    log(f"E1-revised: {len(d)} topics with both domains | overall median lag "
        f"(tech behind science) = {overall:.1f} years")
    log(f"E1-revised: per-topic lag range {d['lag_median_years'].min():.0f} .. "
        f"{d['lag_median_years'].max():.0f} years")

    # figure
    try:
        plt.figure(figsize=(9, max(4, len(d) * 0.4)))
        colors = ["#d62728" if v > 0 else "#1f77b4" for v in d["lag_median_years"]]
        plt.barh([f"T{t}" for t in d["topic_id"]], d["lag_median_years"], color=colors)
        plt.axvline(0, color="gray", lw=0.8)
        plt.xlabel("Median lag: patent filing − paper year (years)")
        plt.title("RQ3 — per-topic science→technology lag (Momeni & Rost)")
        plt.tight_layout(); plt.savefig(FIGURES / "cluster_time_lag.png", dpi=130); plt.close()
        log("E1-revised: figure cluster_time_lag.png saved")
    except Exception as e:
        log(f"E1-revised figure FAILED: {e!r}")


if __name__ == "__main__":
    main()
