"""Make doc_topics.csv (canonical patent clustering) from combined-LDA assignments,
so RQ2/RQ4/originality/2x2 all use the SAME (Mejia combined) topic space."""
import pandas as pd
from common import TABLES, log

def main():
    dtc = pd.read_csv(TABLES / "doc_topics_combined.csv", dtype={"doc_id": str})
    pat = dtc[dtc["domain"] == "patent"].copy()
    out = pat.rename(columns={"doc_id": "pub_number"})[["pub_number", "dominant_topic", "max_prob"]]
    out.to_csv(TABLES / "doc_topics.csv", index=False, encoding="utf-8-sig")
    log(f"derive_doc_topics: doc_topics.csv <- combined ({len(out)} patents, "
        f"{out['dominant_topic'].nunique()} topics)")

if __name__ == "__main__":
    main()
