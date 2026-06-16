"""
D3 (optional, heavy): Trajtenberg originality index per cluster.

Bulk citation blocks lack the cited patent's IPC, so we recover it by a single pass
over the grant corpus (USPTO_BULK_XML), but ONLY for documents that appear as cited
patents in our citations.csv (bounded target set). A wall-clock cap keeps it safe; on
timeout we proceed with the partial index and log coverage.

Originality(cluster) = mean over citing patents of [1 - sum_i (share of cited IPC-3 i)^2].
"""
import re, sys, time, json
import pandas as pd
from collections import defaultdict, Counter
from lxml import etree
from common import BASE, EXTRACTED, TABLES, log

sys.path.insert(0, str(BASE / "src"))
from normalization import normalize_docnum

XMLDIR = BASE / "USPTO_BULK_XML"
MAX_MINUTES = float(sys.argv[1]) if len(sys.argv) > 1 else 150.0
_DOCNUM = re.compile(r"<doc-number>([^<]+)</doc-number>")


def ipc3_of(rec):
    out = set()
    for c in rec.xpath(".//classifications-ipcr//classification-ipcr"):
        g = {etree.QName(x.tag).localname: (x.text or "").strip()
             for x in c if isinstance(x.tag, str)}
        s = g.get("section", ""); cl = g.get("class", "")
        if s and cl:
            out.add(f"{s}{cl}")
    return out


def build_ipc_index(targets, deadline):
    """one streaming pass over grant corpus; record IPC-3 set for cited docs in `targets`."""
    found = {}
    files = sorted(p for p in XMLDIR.glob("ipg*.xml") if "_r" not in p.name)
    for i, path in enumerate(files):
        if time.time() > deadline:
            log(f"D3: time cap hit at file {i}/{len(files)} -> partial index"); break
        if i % 25 == 0:
            log(f"D3 index scan {i}/{len(files)} found={len(found)}/{len(targets)}")
        buf = []; st = False
        with open(path, encoding="utf-8", errors="replace") as f:
            for line in f:
                ls = line.lstrip()
                if ls.startswith("<us-patent-grant"):
                    st = True; buf = [line]
                elif st:
                    buf.append(line)
                    if "</us-patent-grant>" in line:
                        st = False
                        blob = "".join(buf)
                        # cheap prefilter: first <doc-number> = publication number.
                        # only full-parse records whose pub number is a target.
                        m = _DOCNUM.search(blob)
                        if not m:
                            continue
                        nz = normalize_docnum(m.group(1))
                        if nz in targets and nz not in found:
                            try:
                                rec = etree.fromstring(blob.encode("utf-8"))
                            except Exception:
                                continue
                            found[nz] = ipc3_of(rec)
        if len(found) >= len(targets):
            log("D3: all targets found early"); break
    return found


def main():
    try:
        cit = pd.read_csv(EXTRACTED / "citations.csv", dtype=str, keep_default_na=False)
        dt = pd.read_csv(TABLES / "doc_topics.csv", dtype={"pub_number": str})
    except Exception as e:
        log(f"D3: prerequisite missing ({e}) -> skip"); return
    topic = dict(zip(dt["pub_number"], dt["dominant_topic"]))

    patcit = cit[(cit["citation_type"] == "patcit") & (cit["cited_pub_country"] == "US")]
    targets = set(patcit["cited_pub_normalized"]) - {""}
    log(f"D3: unique US cited patents to resolve = {len(targets)}")

    deadline = time.time() + MAX_MINUTES * 60
    ipc_index = build_ipc_index(targets, deadline)
    cov = len(ipc_index) / max(len(targets), 1)
    log(f"D3: IPC index coverage {len(ipc_index)}/{len(targets)} ({cov*100:.1f}%)")
    # persist enriched citations
    patcit = patcit.copy()
    patcit["cited_ipc3"] = patcit["cited_pub_normalized"].map(
        lambda x: ";".join(sorted(ipc_index.get(x, []))))
    patcit.to_csv(EXTRACTED / "citations_enriched.csv", index=False, encoding="utf-8-sig")

    # originality per cluster
    rows = []
    for tid in sorted(set(t for t in topic.values() if t >= 0)):
        cluster_pubs = {p for p, t in topic.items() if t == tid}
        vals = []
        for pub in cluster_pubs:
            sub = patcit[patcit["citing_pub"] == pub]
            ipc_counter = Counter()
            for _, r in sub.iterrows():
                for code in (r["cited_ipc3"].split(";") if r["cited_ipc3"] else []):
                    if code:
                        ipc_counter[code] += 1
            tot = sum(ipc_counter.values())
            if tot >= 3:  # need enough classified citations to be meaningful
                orig = 1 - sum((c / tot) ** 2 for c in ipc_counter.values())
                vals.append(orig)
        if vals:
            rows.append({"cluster_id": int(tid), "n_patents_with_orig": len(vals),
                         "originality_index": round(sum(vals) / len(vals), 4)})
    if rows:
        pd.DataFrame(rows).to_csv(TABLES / "cluster_originality.csv", index=False, encoding="utf-8-sig")
        log(f"D3: cluster_originality.csv saved ({len(rows)} clusters)")
    else:
        log("D3: insufficient classified citations -> cluster_originality.csv not written")


if __name__ == "__main__":
    main()
