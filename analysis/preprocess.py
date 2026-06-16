"""B3: preprocess patent text (abstract + claims) into cleaned tokens for LDA."""
import pandas as pd
from common import EXTRACTED, log, read_jsonl, clean_text

def main():
    src = EXTRACTED / "patents_full.jsonl"
    rows = []
    for r in read_jsonl(src):
        # combine abstract + claims for a richer LDA document
        claims_txt = " ".join(r.get("claims", []))
        raw = (r.get("abstract", "") + " " + claims_txt).strip()
        toks = clean_text(raw)
        rows.append({
            "pub_number": r["publication_number"],
            "year": (r.get("publication_date", "") or "")[:4],
            "filing_year": (r.get("filing_date", "") or "")[:4],
            "kind": r.get("kind", ""),
            "ipc_primary": r["ipc"][0] if r.get("ipc") else "",
            "n_tokens": len(toks),
            "tokens": " ".join(toks),
        })
    df = pd.DataFrame(rows)
    out = EXTRACTED / "patents_processed.csv"
    df.to_csv(out, index=False, encoding="utf-8-sig")
    empty = (df["n_tokens"] == 0).sum()
    log(f"B3 preprocess: {len(df)} patents -> {out.name} | mean tokens {df['n_tokens'].mean():.0f} | empty {empty}")
    return df

if __name__ == "__main__":
    main()
