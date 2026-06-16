"""
Master orchestrator for the overnight run (everything AFTER the application extraction).
Runs each phase as an isolated subprocess; a phase failure is logged and the run continues.
Writes overnight_summary.md at the end.
"""
import sys, time, subprocess
from datetime import datetime
from pathlib import Path
from common import BASE, EXTRACTED, TABLES, FIGURES, log

ANALYSIS = BASE / "analysis"
START = time.time()
STATUS = {}


def run(tag, script, args=None, timeout=4 * 3600):
    args = args or []
    log(f">>> {tag}: start ({script} {' '.join(args)})")
    t0 = time.time()
    try:
        p = subprocess.run([sys.executable, str(ANALYSIS / script), *args],
                           cwd=str(ANALYSIS), capture_output=True, text=True,
                           timeout=timeout, encoding="utf-8", errors="replace")
        out = (p.stdout or "")[-2000:]
        err = (p.stderr or "")[-1500:]
        ok = p.returncode == 0
        STATUS[tag] = "ok" if ok else "fail"
        log(f"<<< {tag}: {'OK' if ok else 'FAIL rc=%d' % p.returncode} in {time.time()-t0:.0f}s")
        if err.strip() and not ok:
            log(f"    {tag} stderr tail: {err.strip()[-600:]}")
    except subprocess.TimeoutExpired:
        STATUS[tag] = "timeout"
        log(f"<<< {tag}: TIMEOUT after {timeout}s -> continue")
    except Exception as e:
        STATUS[tag] = "error"
        log(f"<<< {tag}: ERROR {e!r}")


def main():
    log("=" * 60); log("PIPELINE START (post-extraction phases A2->G)")
    run("A2_revisions", "revisions_update.py", timeout=40 * 60)
    run("A3_integrate", "integrate.py")
    run("B_preprocess", "preprocess.py")
    run("C_rq1_clusters", "rq1_clusters.py", timeout=2 * 3600)
    run("D_rq2_convergence", "rq2_convergence.py")
    run("F_rq4_actors", "rq4_actors.py")
    run("E_rq3_lag", "rq3_lag.py")

    # D3 originality (heavy/optional) — only with remaining time budget
    elapsed_min = (time.time() - START) / 60
    budget = max(20, 360 - elapsed_min)   # leave room; cap below
    cap = min(150, budget)
    if cap >= 25:
        run("D3_originality", "rq2_originality.py", args=[str(int(cap))], timeout=int(cap * 60) + 600)
        if STATUS.get("D3_originality") == "ok":
            run("D_rq2_convergence_2", "rq2_convergence.py")  # fold originality into score
    else:
        STATUS["D3_originality"] = "skipped_no_time"
        log("D3 originality skipped: insufficient time budget")

    run("G_report", "make_report.py")
    write_summary()
    log("PIPELINE DONE"); log("=" * 60)


def write_summary():
    dur = time.time() - START
    h, m = divmod(int(dur // 60), 60)

    def st(tag):
        s = STATUS.get(tag, "not_run")
        return "x" if s == "ok" else "✗" if s in ("fail", "error", "timeout") else "-"

    def count(name):
        p = TABLES / name
        try:
            import pandas as pd
            return len(pd.read_csv(p))
        except Exception:
            return "?"

    n_pat = sum(1 for _ in open(EXTRACTED / "patents_full.jsonl", encoding="utf-8")) \
        if (EXTRACTED / "patents_full.jsonl").exists() else 0
    figs = len(list(FIGURES.glob("*.png")))
    lines = [
        "# Overnight Run Summary",
        f"**Ended**: {datetime.now():%Y-%m-%d %H:%M}  |  **Duration**: {h:02d}:{m:02d}",
        "",
        "## Phase status",
        f"- [{st('A2_revisions')}] A2 revisions   [{st('A3_integrate')}] A3 integrate",
        f"- [{st('B_preprocess')}] B preprocess",
        f"- [{st('C_rq1_clusters')}] C RQ1 clusters (LDA + 2x2)",
        f"- [{st('D_rq2_convergence')}] D RQ2 convergence",
        f"- [{st('D3_originality')}] D3 originality (heavy/optional)",
        f"- [{st('E_rq3_lag')}] E RQ3 lag    [{st('F_rq4_actors')}] F RQ4 actors",
        f"- [{st('G_report')}] G report",
        "",
        "## Key numbers",
        f"- Patents analyzed: {n_pat}",
        f"- LDA topics (topics.csv): {count('topics.csv')}",
        f"- 2x2 clusters (clusters_2x2.csv): {count('clusters_2x2.csv')}",
        f"- Convergence-scored clusters: {count('cluster_convergence_scores.csv')}",
        f"- Figures generated: {figs}",
        "",
        "## Notes / known limitations",
        "- Scopus per-paper abstracts unavailable -> LDA on patents only; RQ3 lag is aggregate.",
        "- See overnight_run.log for any phase failures.",
        "",
        "## Morning checklist",
        "1. Read final_report.md",
        "2. View extracted/analysis_results/figures/2x2_matrix.png",
        "3. Check overnight_run.log for ✗ phases",
        "",
        "## Recommended next",
        "- Pull Scopus abstracts for cross-domain LDA + per-cluster lag.",
        "- Finish D3 originality scan if it timed out.",
    ]
    (BASE / "overnight_summary.md").write_text("\n".join(lines), encoding="utf-8")
    log("overnight_summary.md written")


if __name__ == "__main__":
    main()
