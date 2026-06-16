"""A2: apply latest grant revision (_r2 > _r1 > base) to output/patents_full.jsonl."""
import re, json, sys
from pathlib import Path
from collections import defaultdict
from lxml import etree
import pandas as pd
from common import BASE, OUTPUT, log

sys.path.insert(0, str(BASE / "src"))
from normalization import normalize_docnum
from grant_parser import extract_patent, _DTD

XMLDIR = BASE / "USPTO_BULK_XML"


def stream(path, targets):
    out = {}; buf = []; st = False; dtd = "unknown"
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            ls = line.lstrip()
            if "us-patent-grant-v" in ls:
                m = _DTD.search(line)
                if m: dtd = m.group(1)
            if ls.startswith("<us-patent-grant"):
                st = True; buf = [line]
            elif st:
                buf.append(line)
                if "</us-patent-grant>" in line:
                    st = False
                    try:
                        rec = etree.fromstring("".join(buf).encode("utf-8"))
                    except Exception:
                        continue
                    dn = rec.xpath(".//publication-reference//doc-number/text()")
                    if dn and normalize_docnum(dn[0]) in targets:
                        out[normalize_docnum(dn[0])] = extract_patent(rec, path.name, dtd)
    return out


def main():
    revfiles = {}
    for p in XMLDIR.glob("ipg*_r*.xml"):
        m = re.match(r"ipg(\d{6})_r(\d+)", p.name)
        if not m: continue
        d, rn = m.group(1), int(m.group(2))
        if d not in revfiles or rn > revfiles[d][1]:
            revfiles[d] = (p, rn)
    idx = pd.read_csv(BASE / "logs" / "matchable_grants_index.csv", dtype=str, keep_default_na=False)
    idx["yy"] = idx["Date Published"].map(lambda s: s[2:4] + s[5:7] + s[8:10])
    tg = defaultdict(set)
    for _, r in idx.iterrows():
        if r["yy"] in revfiles:
            tg[r["yy"]].add(r["norm_number"])

    updated = {}
    for d, norms in tg.items():
        p, rn = revfiles[d]
        found = stream(p, norms)
        updated.update(found)
    log(f"A2 revisions: {len(updated)} grant records found in revision files")

    jf = OUTPUT / "patents_full.jsonl"
    if not jf.exists():
        log("A2: output/patents_full.jsonl missing -> skip"); return
    recs = [json.loads(l) for l in open(jf, encoding="utf-8")]
    byn = {r["publication_number"]: i for i, r in enumerate(recs)}
    changed = 0
    for nz, newr in updated.items():
        if nz in byn:
            old = recs[byn[nz]]
            if (len(old["abstract"]) != len(newr["abstract"]) or
                    len(old["claims"]) != len(newr["claims"]) or
                    len(old["references_cited"]) != len(newr["references_cited"])):
                changed += 1
            newr["source_file"] = newr["source_file"]
            recs[byn[nz]] = newr
    with open(jf, "w", encoding="utf-8") as f:
        for r in recs:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    log(f"A2 revisions: applied {len(updated)} (content-changed {changed}) -> patents_full.jsonl")


if __name__ == "__main__":
    main()
