"""RQ4: actor analysis — countries and organizations (overall + per cluster)."""
import re
import pandas as pd
from collections import Counter
from common import EXTRACTED, TABLES, FIGURES, log, read_jsonl
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

CONSTRUCTION_KW = ["construction", "engineering", "build", "infrastructure", "civil",
                   "contractor", "concrete", "cement"]


def norm_org(name):
    n = (name or "").upper().strip()
    n = re.sub(r"[.,]", "", n)
    n = re.sub(r"\b(CO|LTD|INC|LLC|CORP|CORPORATION|GMBH|KK|PLC|LP|HOLDINGS|GROUP|LIMITED|COMPANY)\b",
               "", n)
    return re.sub(r"\s+", " ", n).strip()


def is_construction(name):
    n = (name or "").lower()
    return any(k in n for k in CONSTRUCTION_KW)


def norm_country(cty):
    """collapse doubled ISO codes ('USUS'->'US') / take alpha-2."""
    c = (cty or "").strip().upper()
    if len(c) == 4 and c[:2] == c[2:]:
        return c[:2]
    return c[:2] if len(c) > 2 else c


def main():
    pats = list(read_jsonl(EXTRACTED / "patents_full.jsonl"))
    try:
        dt = pd.read_csv(TABLES / "doc_topics.csv", dtype={"pub_number": str})
        topic = dict(zip(dt["pub_number"], dt["dominant_topic"]))
    except Exception:
        topic = {}

    country_all = Counter()
    org_all = Counter()
    org_constr = Counter()
    cluster_country = Counter()  # (cluster, country)
    for r in pats:
        tid = topic.get(r["publication_number"], -1)
        a_list = r.get("assignee", [])
        for a in a_list:
            cty = norm_country(a.get("country"))
            if not cty:
                # fallback to inventor country
                inv = r.get("inventors", [])
                cty = norm_country(inv[0].get("country") if inv else "")
            if cty:
                country_all[cty] += 1
                cluster_country[(tid, cty)] += 1
            nm = norm_org(a.get("name", ""))
            if nm:
                org_all[nm] += 1
                org_constr[is_construction(a.get("name", ""))] += 1

    # F1 country
    c1 = pd.DataFrame(country_all.most_common(), columns=["country", "n_assignees"])
    c1.to_csv(TABLES / "country_analysis.csv", index=False, encoding="utf-8-sig")
    log(f"F1 country: {len(c1)} countries | top: {country_all.most_common(5)}")

    # F2 org
    o1 = pd.DataFrame(org_all.most_common(20), columns=["organization", "n_patents"])
    o1["is_construction"] = o1["organization"].map(lambda x: is_construction(x))
    o1.to_csv(TABLES / "organization_analysis.csv", index=False, encoding="utf-8-sig")
    tot = sum(org_constr.values())
    log(f"F2 org: {len(org_all)} unique orgs | top: {org_all.most_common(5)} | "
        f"construction-assignee share {org_constr.get(True,0)}/{tot}")

    # F3 figures
    try:
        top_c = c1.head(10)
        plt.figure(figsize=(8, 5)); plt.bar(top_c["country"], top_c["n_assignees"], color="#1f77b4")
        plt.ylabel("Assignees"); plt.title("RQ4 — Top countries"); plt.tight_layout()
        plt.savefig(FIGURES / "country_bar.png", dpi=130); plt.close()

        top_o = o1.head(15)
        plt.figure(figsize=(9, 6))
        plt.barh(top_o["organization"][::-1], top_o["n_patents"][::-1], color="#2ca02c")
        plt.xlabel("Patents"); plt.title("RQ4 — Top organizations"); plt.tight_layout()
        plt.savefig(FIGURES / "organization_bar.png", dpi=130); plt.close()

        # cluster x country heatmap (top clusters x top countries)
        if topic:
            top_countries = [c for c, _ in country_all.most_common(8)]
            clusters = sorted(set(t for t in topic.values() if t >= 0))
            mat = pd.DataFrame(0, index=clusters, columns=top_countries)
            for (cl, cty), n in cluster_country.items():
                if cl in clusters and cty in top_countries:
                    mat.loc[cl, cty] = n
            if not mat.empty:
                import seaborn as sns
                plt.figure(figsize=(9, max(4, len(clusters) * 0.4)))
                sns.heatmap(mat, annot=True, fmt="d", cmap="YlOrRd")
                plt.xlabel("Country"); plt.ylabel("Cluster (LDA topic)")
                plt.title("RQ4 — Cluster x Country"); plt.tight_layout()
                plt.savefig(FIGURES / "cluster_country_heatmap.png", dpi=130); plt.close()
        log("F3: country_bar / organization_bar / cluster_country_heatmap saved")
    except Exception as e:
        log(f"F3 figures FAILED: {e!r}")


if __name__ == "__main__":
    main()
