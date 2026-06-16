"""
C3-revised: combined paper+patent LDA on a single forced-K topic space (Mejia & Kajikawa).
Enables cross-domain comparison and per-topic science->technology lag.

Outputs (tables/):
  topics_combined.csv         topic_id, top_15_words, n_papers, n_patents
  doc_topics_combined.csv      doc_id, domain(paper/patent), year, dominant_topic, max_prob
  lda_coherence_combined.csv
"""
import json
import pandas as pd
from common import EXTRACTED, TABLES, MODELS, log


def main():
    pat = pd.read_csv(EXTRACTED / "patents_processed.csv", dtype=str, keep_default_na=False)
    pap = pd.read_csv(EXTRACTED / "scopus_processed.csv", dtype=str, keep_default_na=False)

    docs = []
    for _, r in pat.iterrows():
        docs.append(("patent", r["pub_number"], r.get("filing_year") or r.get("year"),
                     (r["tokens"] or "").split()))
    for _, r in pap.iterrows():
        docs.append(("paper", r["doc_id"], r["year"], (r["tokens"] or "").split()))
    texts = [d[3] for d in docs]
    log(f"C3-combined: {len(docs)} docs ({sum(d[0]=='patent' for d in docs)} patents + "
        f"{sum(d[0]=='paper' for d in docs)} papers)")

    from gensim import corpora
    from gensim.models import LdaModel, CoherenceModel
    dic = corpora.Dictionary(texts)
    dic.filter_extremes(no_below=3, no_above=0.5)
    corpus = [dic.doc2bow(t) for t in texts]

    scores = []
    for K in [10, 15, 20, 25, 30, 35, 40]:
        try:
            m = LdaModel(corpus=corpus, num_topics=K, id2word=dic, passes=5,
                         iterations=100, random_state=42, chunksize=1000)
            c = CoherenceModel(model=m, texts=texts, dictionary=dic,
                               coherence="c_v", processes=1).get_coherence()
            scores.append((K, c)); log(f"C3-combined K={K} c_v={c:.4f}")
        except Exception as e:
            log(f"C3-combined K={K} FAILED: {e!r}")
    if not scores:
        log("C3-combined: all K failed -> abort"); return
    pd.DataFrame(scores, columns=["K", "coherence_cv"]).to_csv(
        TABLES / "lda_coherence_combined.csv", index=False, encoding="utf-8-sig")
    best_K = max(scores, key=lambda x: x[1])[0]
    log(f"C3-combined best K={best_K}")

    final = LdaModel(corpus=corpus, num_topics=best_K, id2word=dic, passes=15,
                     iterations=200, random_state=42, chunksize=1000)
    final.save(str(MODELS / "lda_model_combined.gensim"))

    # doc topics
    drows = []
    for (domain, did, year, _), bow in zip(docs, corpus):
        dist = final.get_document_topics(bow, minimum_probability=0.0)
        dom, p = (max(dist, key=lambda x: x[1]) if dist else (-1, 0.0))
        drows.append({"doc_id": did, "domain": domain, "year": year,
                      "dominant_topic": dom, "max_prob": round(float(p), 4)})
    dt = pd.DataFrame(drows)
    dt.to_csv(TABLES / "doc_topics_combined.csv", index=False, encoding="utf-8-sig")

    # topics + domain mix
    trows = []
    for tid in range(best_K):
        words = [w for w, _ in final.show_topic(tid, topn=15)]
        sub = dt[dt["dominant_topic"] == tid]
        trows.append({"topic_id": tid, "top_15_words": ", ".join(words),
                      "n_papers": int((sub["domain"] == "paper").sum()),
                      "n_patents": int((sub["domain"] == "patent").sum())})
    pd.DataFrame(trows).to_csv(TABLES / "topics_combined.csv", index=False, encoding="utf-8-sig")
    log(f"C3-combined: topics_combined.csv ({best_K}) + doc_topics_combined.csv ({len(dt)}) saved")


if __name__ == "__main__":
    main()
