"""B2: preprocess Scopus paper abstracts -> cleaned tokens (for combined LDA)."""
import re, glob
import pandas as pd
from common import BASE, EXTRACTED, log, clean_text

COPYRIGHT = re.compile(r"©.*$|\bcopyright\b.*$", re.I)


def main():
    files = glob.glob(str(BASE / "scopus" / "scopus_export*.csv"))
    if not files:
        log("B2: no scopus_export*.csv found -> skip"); return None
    src = max(files)  # newest
    df = pd.read_csv(src, dtype=str, keep_default_na=False)
    log(f"B2: loaded {len(df)} papers from {src.split(chr(92))[-1]}")
    abcol = "Abstract" if "Abstract" in df.columns else None
    if abcol is None:
        log("B2: no Abstract column -> skip"); return None

    rows = []
    for i, r in df.iterrows():
        ab = r.get(abcol, "")
        if not ab or ab.strip().lower().startswith("[no abstract"):
            ab = ""
        ab = COPYRIGHT.sub("", ab)
        title = r.get("Title", "")
        toks = clean_text(title + " " + ab)
        rows.append({
            "doc_id": f"PAP{i}",
            "year": (r.get("Year", "") or "")[:4],
            "title": title[:200],
            "doi": r.get("DOI", ""),
            "n_tokens": len(toks),
            "tokens": " ".join(toks),
        })
    out = pd.DataFrame(rows)
    out.to_csv(EXTRACTED / "scopus_processed.csv", index=False, encoding="utf-8-sig")
    nonempty = (out["n_tokens"] > 0).sum()
    log(f"B2: {len(out)} papers -> scopus_processed.csv | non-empty {nonempty} | "
        f"mean tokens {out['n_tokens'].mean():.0f}")
    return out


if __name__ == "__main__":
    main()
