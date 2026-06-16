"""Run the Scopus-enabled cross-domain phases: B2 -> combined LDA -> per-topic lag -> report."""
import sys, time, subprocess
from pathlib import Path
from common import BASE, log

ANALYSIS = BASE / "analysis"


def run(tag, script, timeout=2 * 3600):
    log(f">>> {tag}: start")
    t0 = time.time()
    try:
        p = subprocess.run([sys.executable, str(ANALYSIS / script)], cwd=str(ANALYSIS),
                           capture_output=True, text=True, timeout=timeout,
                           encoding="utf-8", errors="replace")
        ok = p.returncode == 0
        log(f"<<< {tag}: {'OK' if ok else 'FAIL rc=%d' % p.returncode} in {time.time()-t0:.0f}s")
        if not ok:
            log(f"    {tag} stderr: {(p.stderr or '')[-700:]}")
    except Exception as e:
        log(f"<<< {tag}: ERROR {e!r}")


def main():
    log("=" * 60); log("CROSS-DOMAIN PIPELINE START (Scopus enabled)")
    run("B2_scopus_preprocess", "scopus_preprocess.py")
    run("C3_combined_lda", "rq1_combined_lda.py")
    run("E1_combined_lag", "rq3_combined_lag.py")
    run("G_report", "make_report.py")
    log("CROSS-DOMAIN PIPELINE DONE"); log("=" * 60)


if __name__ == "__main__":
    main()
