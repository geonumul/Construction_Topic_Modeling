"""
RQ3: science -> technology time-lag (Momeni & Rost 2016), adapted to available data.

NOTE (logged limitation): Scopus per-paper abstracts/clusters are unavailable; only a
year-aggregate paper count table exists. So:
 E1/E3 aggregate science(paper-year) vs technology(patent filing-year) distributions.
 E2 compares patent filing-year timing between high- vs low-convergence clusters
    (Mann-Whitney U) as a patent-internal proxy for emergence timing.
"""
import re
import numpy as np
import pandas as pd
from common import BASE, EXTRACTED, TABLES, FIGURES, log, read_jsonl
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def load_paper_years():
    p = BASE / "scopus" / "Scopus-10-Analyze-Year (1).csv"
    counts = {}
    if p.exists():
        for line in open(p, encoding="utf-8-sig"):
            m = re.match(r'^"?(\d{4})"?,"?(\d+)"?', line.strip())
            if m:
                counts[int(m.group(1))] = int(m.group(2))
    return counts


def cum_lag(paper_counts, patent_counts):
    """cumulative-quantile lag of technology behind science."""
    def cum_year(counts, q):
        yrs = sorted(counts)
        tot = sum(counts.values())
        run = 0
        for y in yrs:
            run += counts[y]
            if run / tot >= q:
                return y
        return yrs[-1] if yrs else None
    out = {}
    for q in (0.0, 0.25, 0.5):
        py = min(paper_counts) if q == 0 else cum_year(paper_counts, q)
        ty = min(patent_counts) if q == 0 else cum_year(patent_counts, q)
        if py is not None and ty is not None:
            out[q] = ty - py
    return out


def main():
    papers = load_paper_years()
    pats = list(read_jsonl(EXTRACTED / "patents_full.jsonl"))
    filing = pd.Series([int((r.get("filing_date") or "0")[:4] or 0) for r in pats])
    filing = filing[filing > 1990]
    patent_counts = filing.value_counts().to_dict()
    log(f"RQ3: paper-years={len(papers)} (total {sum(papers.values())}) | "
        f"patent filing-years span {filing.min()}-{filing.max()}")

    # E1 aggregate lag
    lag = cum_lag(papers, patent_counts)
    e1 = pd.DataFrame([{"quantile": f"{int(q*100)}%", "paper_year": None, "lag_years": v}
                       for q, v in lag.items()])
    e1.to_csv(TABLES / "cluster_time_lag.csv", index=False, encoding="utf-8-sig")
    med_paper = np.median(np.repeat(list(papers.keys()), list(papers.values()))) if papers else None
    med_patent = filing.median()
    log(f"RQ3 E1 aggregate lag (tech behind science): {lag} | median paper {med_paper} "
        f"vs median patent-filing {med_patent} -> ~{med_patent-med_paper:.1f}y" if med_paper else "RQ3 E1: no paper years")

    # E2 cluster timing high vs low convergence
    try:
        from scipy.stats import mannwhitneyu
        conv = pd.read_csv(TABLES / "cluster_convergence_scores.csv")
        dt = pd.read_csv(TABLES / "doc_topics.csv", dtype={"pub_number": str})
        fy = {r["publication_number"]: int((r.get("filing_date") or "0")[:4] or 0) for r in pats}
        dt["fy"] = dt["pub_number"].map(fy)
        med = conv["convergence_score"].median()
        hi = set(conv[conv["convergence_score"] >= med]["cluster_id"])
        hi_years = dt[dt["dominant_topic"].isin(hi) & (dt["fy"] > 1990)]["fy"]
        lo_years = dt[~dt["dominant_topic"].isin(hi) & (dt["fy"] > 1990)]["fy"]
        if len(hi_years) > 5 and len(lo_years) > 5:
            u, pval = mannwhitneyu(hi_years, lo_years, alternative="two-sided")
            cmp = pd.DataFrame([{"group": "high_convergence", "n": len(hi_years),
                                 "median_filing_year": hi_years.median()},
                                {"group": "low_convergence", "n": len(lo_years),
                                 "median_filing_year": lo_years.median()},
                                {"group": "MannWhitneyU", "n": "", "median_filing_year": "",
                                 "U": u, "p_value": round(pval, 4)}])
            cmp.to_csv(TABLES / "lag_comparison.csv", index=False, encoding="utf-8-sig")
            log(f"RQ3 E2: high-conv median filing {hi_years.median()} vs low {lo_years.median()} "
                f"| MWU p={pval:.4f}")
            # boxplot
            plt.figure(figsize=(6, 5))
            plt.boxplot([lo_years, hi_years], labels=["Low conv.", "High conv."])
            plt.ylabel("Patent filing year"); plt.title("RQ3 E2 — emergence timing by convergence")
            plt.tight_layout(); plt.savefig(FIGURES / "time_lag_boxplot.png", dpi=130); plt.close()
        else:
            log("RQ3 E2: too few patents per group -> skip MWU")
    except Exception as e:
        log(f"RQ3 E2 FAILED: {e!r}")

    # E3 yearly trend papers vs patents
    try:
        yrs = sorted(set(list(papers.keys()) + list(patent_counts.keys())))
        yrs = [y for y in yrs if 2005 <= y <= 2026]
        tr = pd.DataFrame({"year": yrs,
                           "papers": [papers.get(y, 0) for y in yrs],
                           "patents_filed": [patent_counts.get(y, 0) for y in yrs]})
        tr.to_csv(TABLES / "yearly_trend.csv", index=False, encoding="utf-8-sig")
        fig, ax1 = plt.subplots(figsize=(9, 5))
        ax1.plot(tr["year"], tr["papers"], "-o", color="#1f77b4", label="Papers (Scopus)")
        ax1.set_ylabel("Papers", color="#1f77b4")
        ax2 = ax1.twinx()
        ax2.plot(tr["year"], tr["patents_filed"], "-s", color="#d62728", label="Patents filed")
        ax2.set_ylabel("Patents filed", color="#d62728")
        ax1.set_xlabel("Year"); plt.title("RQ3 E3 — yearly science vs technology output")
        fig.tight_layout(); plt.savefig(FIGURES / "yearly_trend.png", dpi=130); plt.close()
        log(f"RQ3 E3: yearly_trend.csv + figure saved ({len(tr)} years)")
    except Exception as e:
        log(f"RQ3 E3 FAILED: {e!r}")


if __name__ == "__main__":
    main()
