"""
Full re-analysis on the COMPLETE dataset (445 grants + recovered apps + 3,675 papers).
Reuses citations_enriched.csv from the D3 scan (no corpus rescan). Combined LDA topics
are the single cluster definition across RQ1/RQ2/RQ3/RQ4.
"""
import sys, time, subprocess
from pathlib import Path
from common import BASE, EXTRACTED, TABLES, FIGURES, log

ANALYSIS = BASE / "analysis"
START = time.time()
STATUS = {}


def run(tag, script, timeout=2 * 3600):
    log(f">>> {tag}: start")
    t0 = time.time()
    try:
        p = subprocess.run([sys.executable, str(ANALYSIS / script)], cwd=str(ANALYSIS),
                           capture_output=True, text=True, timeout=timeout,
                           encoding="utf-8", errors="replace")
        STATUS[tag] = "ok" if p.returncode == 0 else "fail"
        log(f"<<< {tag}: {'OK' if p.returncode==0 else 'FAIL rc=%d'%p.returncode} in {time.time()-t0:.0f}s")
        if p.returncode != 0:
            log(f"    {tag} stderr: {(p.stderr or '')[-700:]}")
    except Exception as e:
        STATUS[tag] = "error"; log(f"<<< {tag}: ERROR {e!r}")


def main():
    log("=" * 60); log("FULL RE-ANALYSIS START (complete dataset, combined topics)")
    run("integrate", "integrate.py")
    run("preprocess", "preprocess.py")
    run("combined_lda", "rq1_combined_lda.py")
    run("derive_doc_topics", "derive_doc_topics.py")
    run("rq1_2x2", "rq1_2x2.py")
    run("rq2_convergence", "rq2_convergence.py")
    run("rq4_actors", "rq4_actors.py")
    run("rq3_lag", "rq3_combined_lag.py")
    run("originality", "originality_from_enriched.py")
    run("rq2_convergence_2", "rq2_convergence.py")   # fold originality into score
    run("report", "make_report.py")
    log(f"FULL RE-ANALYSIS DONE in {(time.time()-START)/60:.0f} min | status={STATUS}")
    log("=" * 60)


if __name__ == "__main__":
    main()
