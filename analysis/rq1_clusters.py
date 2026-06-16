"""
RQ1: technology cluster identification.
 C1 direct-citation network, C2 Louvain communities,
 C3 LDA topic modeling (patents only; Scopus abstracts unavailable),
 C4 2x2 novelty x growth promising-cluster matrix.

Robust: each sub-phase wrapped; failures are logged and the pipeline continues.
"""
import json
import numpy as np
import pandas as pd
from collections import Counter
from common import EXTRACTED, TABLES, FIGURES, MODELS, log, read_jsonl

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def load_patents():
    return {r["publication_number"]: r for r in read_jsonl(EXTRACTED / "patents_full.jsonl")}


# ---------------------------------------------------------------- C1 + C2
def citation_clusters(patents):
    import networkx as nx
    import community as community_louvain
    cit = pd.read_csv(EXTRACTED / "citations.csv", dtype=str, keep_default_na=False)
    ours = set(patents)
    internal = cit[(cit["citing_pub"].isin(ours)) & (cit["cited_pub_normalized"].isin(ours))]
    log(f"C1 citation net: total citations={len(cit)} internal(both in set)={len(internal)}")
    G = nx.Graph()
    G.add_nodes_from(ours)
    for _, r in internal.iterrows():
        if r["citing_pub"] != r["cited_pub_normalized"]:
            G.add_edge(r["citing_pub"], r["cited_pub_normalized"])
    nedge = G.number_of_edges()
    log(f"C1 graph: nodes={G.number_of_nodes()} edges={nedge} "
        f"connected_components={nx.number_connected_components(G)}")

    rows = []
    if nedge > 0:
        part = community_louvain.best_partition(G, resolution=1.0, random_state=42)
        sizes = Counter(part.values())
        # relabel small (<10) communities as 'other' (-1)
        big = {c for c, s in sizes.items() if s >= 10}
        for pub in ours:
            c = part.get(pub, -1)
            cl = c if c in big else -1
            rows.append({"pub_number": pub, "cluster_id": cl,
                         "in_citation_net": pub in part})
        log(f"C2 louvain: raw communities={len(sizes)} >=10 communities={len(big)} "
            f"sizes(top)={sizes.most_common(8)}")
    else:
        for pub in ours:
            rows.append({"pub_number": pub, "cluster_id": -1, "in_citation_net": False})
        log("C2 louvain: citation network has no internal edges -> all isolated "
            "(expected: our set is a thin slice; LDA topics used as primary cluster unit)")
    df = pd.DataFrame(rows)
    df.to_csv(TABLES / "patents_clusters.csv", index=False, encoding="utf-8-sig")
    return df


# ---------------------------------------------------------------- C3 LDA
def lda_topics(patents):
    from gensim import corpora
    from gensim.models import LdaModel, CoherenceModel
    proc = pd.read_csv(EXTRACTED / "patents_processed.csv", dtype=str, keep_default_na=False)
    proc = proc.set_index("pub_number")
    texts = [t.split() for t in proc["tokens"].fillna("")]
    texts = [t for t in texts]
    dictionary = corpora.Dictionary(texts)
    dictionary.filter_extremes(no_below=2, no_above=0.5)
    corpus = [dictionary.doc2bow(t) for t in texts]

    candidates = [10, 15, 20, 25, 30, 35, 40]
    scores = []
    for K in candidates:
        try:
            m = LdaModel(corpus=corpus, num_topics=K, id2word=dictionary,
                         passes=5, iterations=100, random_state=42, chunksize=500)
            cm = CoherenceModel(model=m, texts=texts, dictionary=dictionary,
                                coherence="c_v", processes=1)
            c = cm.get_coherence()
            scores.append((K, c))
            log(f"C3 LDA K={K} coherence_cv={c:.4f}")
        except Exception as e:
            log(f"C3 LDA K={K} FAILED: {e!r}")
    if not scores:
        log("C3 LDA: all K failed -> abort LDA")
        return None
    pd.DataFrame(scores, columns=["K", "coherence_cv"]).to_csv(
        TABLES / "lda_coherence.csv", index=False, encoding="utf-8-sig")
    best_K = max(scores, key=lambda x: x[1])[0]
    log(f"C3 LDA best K={best_K} (max c_v)")

    final = LdaModel(corpus=corpus, num_topics=best_K, id2word=dictionary,
                     passes=15, iterations=200, random_state=42, chunksize=500)
    final.save(str(MODELS / "lda_model.gensim"))

    # topics.csv
    trows = []
    for tid in range(best_K):
        words = [w for w, _ in final.show_topic(tid, topn=15)]
        trows.append({"topic_id": tid, "top_15_words": ", ".join(words)})
    pd.DataFrame(trows).to_csv(TABLES / "topics.csv", index=False, encoding="utf-8-sig")

    # doc_topics.csv
    drows = []
    pubs = list(proc.index)
    for pub, bow in zip(pubs, corpus):
        dist = final.get_document_topics(bow, minimum_probability=0.0)
        if dist:
            dom, p = max(dist, key=lambda x: x[1])
        else:
            dom, p = -1, 0.0
        drows.append({"pub_number": pub, "dominant_topic": dom, "max_prob": round(float(p), 4),
                      "topic_probs": json.dumps([round(float(x), 4) for _, x in dist])})
    dt = pd.DataFrame(drows)
    dt.to_csv(TABLES / "doc_topics.csv", index=False, encoding="utf-8-sig")
    log(f"C3 LDA: topics.csv ({best_K}) + doc_topics.csv ({len(dt)}) saved")
    return dt


# ---------------------------------------------------------------- C4 2x2
def matrix_2x2(patents, doc_topics):
    if doc_topics is None or doc_topics.empty:
        log("C4 2x2: no doc_topics -> skip")
        return
    pat = pd.DataFrame([{"pub_number": k, "year": int((v.get("publication_date") or "0")[:4] or 0)}
                        for k, v in patents.items()])
    dt = doc_topics.merge(pat, on="pub_number", how="left")
    dt = dt[dt["dominant_topic"] >= 0]

    rows = []
    for tid, g in dt.groupby("dominant_topic"):
        yrs = g["year"]
        n = len(g)
        novelty = (yrs >= 2021).mean()  # share in last ~5y
        # growth: CAGR of yearly counts over last 5 windows (2021->2025)
        recent = yrs[(yrs >= 2021) & (yrs <= 2025)]
        c_by_year = recent.value_counts().sort_index()
        if len(c_by_year) >= 2 and c_by_year.iloc[0] > 0:
            yrs_span = c_by_year.index[-1] - c_by_year.index[0]
            cagr = (c_by_year.iloc[-1] / c_by_year.iloc[0]) ** (1 / max(yrs_span, 1)) - 1
        else:
            cagr = 0.0
        rows.append({"cluster_id": int(tid), "n_patents": n,
                     "novelty": round(float(novelty), 4), "growth": round(float(cagr), 4)})
    m = pd.DataFrame(rows)
    if m.empty:
        log("C4 2x2: empty -> skip"); return
    nov_med = m["novelty"].median(); gro_med = m["growth"].median()

    def quad(r):
        hn = r["novelty"] >= nov_med; hg = r["growth"] >= gro_med
        return ("Promising" if hn and hg else "Emerging" if hn else
                "Established" if hg else "Declining")
    m["quadrant"] = m.apply(quad, axis=1)
    m.to_csv(TABLES / "clusters_2x2.csv", index=False, encoding="utf-8-sig")
    log(f"C4 2x2: {len(m)} clusters | Promising={int((m['quadrant']=='Promising').sum())} "
        f"| medians nov={nov_med:.3f} growth={gro_med:.3f}")

    # scatter
    try:
        plt.figure(figsize=(8, 6))
        colors = {"Promising": "#d62728", "Emerging": "#1f77b4",
                  "Established": "#2ca02c", "Declining": "#7f7f7f"}
        for q, gg in m.groupby("quadrant"):
            plt.scatter(gg["novelty"], gg["growth"], s=gg["n_patents"]*8,
                        alpha=0.7, label=q, color=colors.get(q, "gray"))
            for _, r in gg.iterrows():
                plt.annotate(str(r["cluster_id"]), (r["novelty"], r["growth"]), fontsize=8)
        plt.axvline(nov_med, ls="--", c="gray", lw=0.8); plt.axhline(gro_med, ls="--", c="gray", lw=0.8)
        plt.xlabel("Novelty (share published 2021-2026)")
        plt.ylabel("Growth (CAGR 2021-2025)")
        plt.title("RQ1 — Technology cluster 2x2 (Mejia & Kajikawa)")
        plt.legend(); plt.tight_layout()
        plt.savefig(FIGURES / "2x2_matrix.png", dpi=130); plt.close()
        log("C4 2x2: figure 2x2_matrix.png saved")
    except Exception as e:
        log(f"C4 2x2 figure FAILED: {e!r}")


def main():
    patents = load_patents()
    log(f"RQ1 start: {len(patents)} patents loaded")
    try:
        citation_clusters(patents)
    except Exception as e:
        log(f"C1/C2 FAILED: {e!r}")
    dt = None
    try:
        dt = lda_topics(patents)
    except Exception as e:
        log(f"C3 LDA FAILED: {e!r}")
    try:
        matrix_2x2(patents, dt)
    except Exception as e:
        log(f"C4 FAILED: {e!r}")
    log("RQ1 done")


if __name__ == "__main__":
    main()
