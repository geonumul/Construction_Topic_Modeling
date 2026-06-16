"""G: assemble final_report.md and overnight_summary.md from result tables (robust to gaps)."""
import json
from datetime import datetime
import pandas as pd
from common import BASE, EXTRACTED, TABLES, FIGURES, MODELS, log


def rd(name):
    p = TABLES / name
    try:
        return pd.read_csv(p)
    except Exception:
        return None


def main():
    n_pat = sum(1 for _ in open(EXTRACTED / "patents_full.jsonl", encoding="utf-8")) \
        if (EXTRACTED / "patents_full.jsonl").exists() else 0
    topics = rd("topics.csv"); coh = rd("lda_coherence.csv"); m2 = rd("clusters_2x2.csv")
    conv = rd("cluster_convergence_scores.csv"); lag = rd("cluster_time_lag.csv")
    cmp_ = rd("lag_comparison.csv"); country = rd("country_analysis.csv")
    org = rd("organization_analysis.csv"); orig = rd("cluster_originality.csv")

    best_K = len(topics) if topics is not None else None
    promising = int((m2["quadrant"] == "Promising").sum()) if m2 is not None else 0
    top_countries = country.head(3)["country"].tolist() if country is not None else []
    top_orgs = org.head(3)["organization"].tolist() if org is not None else []

    L = []
    L.append("# Construction Safety Robot — Patent Analysis (RQ1–RQ4)\n")
    L.append(f"_Generated {datetime.now():%Y-%m-%d %H:%M}_\n")
    L.append("## 1. Data overview")
    L.append(f"- Patents analyzed: **{n_pat}** (USPTO grant + application full text)")
    L.append("- Scopus papers: year-aggregate only (3,672 total, 2005–2026); per-paper "
             "abstracts unavailable this run, so cross-domain LDA and per-cluster lag are limited.\n")

    L.append("## 2. RQ1 — Technology clusters")
    if best_K:
        L.append(f"- LDA optimal K (max c_v coherence): **{best_K} topics**")
        if coh is not None:
            best = coh.loc[coh['coherence_cv'].idxmax()]
            L.append(f"- Best coherence c_v = {best['coherence_cv']:.3f} at K={int(best['K'])}")
        L.append(f"- Promising clusters (high novelty + high growth): **{promising}**")
        if topics is not None:
            L.append("\n| Topic | Top words |\n|---|---|")
            for _, r in topics.iterrows():
                L.append(f"| {int(r['topic_id'])} | {r['top_15_words']} |")
    else:
        L.append("- LDA did not complete (see log).")
    if m2 is not None:
        L.append("\n2×2 promising matrix: `figures/2x2_matrix.png`")

    L.append("\n## 3. RQ2 — Multi-dimensional convergence")
    if conv is not None:
        L.append("Top external-convergence clusters:")
        L.append("\n| Cluster | conv. score | " +
                 " | ".join(c for c in conv.columns if c not in ("cluster_id", "convergence_score")) + " |")
        L.append("|" + "---|" * (len(conv.columns)))
        for _, r in conv.head(5).iterrows():
            extra = " | ".join(f"{r[c]}" for c in conv.columns if c not in ("cluster_id", "convergence_score"))
            L.append(f"| {int(r['cluster_id'])} | {r['convergence_score']} | {extra} |")
    else:
        L.append("- convergence scores unavailable (see log).")
    if orig is not None:
        L.append(f"\nOriginality computed for {len(orig)} clusters (`cluster_originality.csv`).")
    else:
        L.append("\nOriginality (D3) not completed this run.")

    L.append("\n## 4. RQ3 — Science→technology lag")
    if lag is not None:
        L.append("Aggregate lag (technology behind science):")
        L.append("\n| Quantile | lag (years) |\n|---|---|")
        for _, r in lag.iterrows():
            L.append(f"| {r['quantile']} | {r['lag_years']} |")
    if cmp_ is not None:
        L.append("\nEmergence timing high- vs low-convergence: `lag_comparison.csv`, "
                 "`figures/time_lag_boxplot.png`")

    L.append("\n## 5. RQ4 — Actors")
    if top_countries:
        L.append(f"- Top countries: {', '.join(top_countries)}")
    if top_orgs:
        L.append(f"- Top organizations: {', '.join(str(o) for o in top_orgs)}")
    L.append("- Figures: `country_bar.png`, `organization_bar.png`, `cluster_country_heatmap.png`")

    L.append("\n## 6. Key findings")
    L.append(f"1. {n_pat} construction-safety-robotics patents extracted and analyzed.")
    if best_K:
        L.append(f"2. {best_K} latent technology topics; {promising} flagged promising (novel + growing).")
    if top_countries:
        L.append(f"3. Activity concentrated in {', '.join(top_countries)}.")
    L.append("4. Cross-domain (paper↔patent) lag requires Scopus abstracts — recommended next data pull.")

    # cross-domain (papers + patents) — present only if combined LDA ran
    tc = rd("topics_combined.csv"); lagc = rd("cluster_time_lag_combined.csv")
    if tc is not None:
        n_pap = int(tc["n_papers"].sum()); n_pt = int(tc["n_patents"].sum())
        L.append("\n## 7. Cross-domain analysis (papers + patents, combined LDA)")
        L.append(f"- Unified topic space over {n_pap} papers + {n_pt} patents, {len(tc)} topics.")
        if lagc is not None and len(lagc):
            ov = lagc["lag_median_years"].median()
            L.append(f"- Per-topic science→technology lag (Momeni & Rost): overall median "
                     f"**{ov:.1f} years** (technology behind science); "
                     f"range {lagc['lag_median_years'].min():.0f}…{lagc['lag_median_years'].max():.0f}y.")
            L.append("- Figure: `figures/cluster_time_lag.png`. Table: `cluster_time_lag_combined.csv`.")
            L.append("\n| Topic | papers | patents | median lag (y) |\n|---|---|---|---|")
            for _, r in lagc.sort_values("lag_median_years", ascending=False).head(8).iterrows():
                L.append(f"| {int(r['topic_id'])} | {int(r['n_papers'])} | {int(r['n_patents'])} "
                         f"| {r['lag_median_years']:.1f} |")

    L.append("\n## 8. Next steps")
    L.append("- Obtain Scopus per-paper abstracts to enable cross-domain LDA and per-cluster lag.")
    L.append("- Complete originality (D3) corpus scan if not finished.")
    L.append("- Acquire pre-2014 grant + remaining APPXML to raise coverage toward 92%.")

    (BASE / "final_report.md").write_text("\n".join(L), encoding="utf-8")
    log("G: final_report.md written")
    return dict(n_pat=n_pat, best_K=best_K, promising=promising,
                top_countries=top_countries, top_orgs=top_orgs,
                has_conv=conv is not None, has_orig=orig is not None,
                has_lag=lag is not None)


if __name__ == "__main__":
    main()
