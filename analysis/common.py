"""Shared utilities for the overnight RQ1-4 analysis pipeline."""
import re, sys, json, time
from pathlib import Path
from datetime import datetime

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

BASE      = Path(r"D:\Construction_TopicModeling")
OUTPUT    = BASE / "output"
EXTRACTED = BASE / "extracted"
RESULTS   = EXTRACTED / "analysis_results"
TABLES    = RESULTS / "tables"
FIGURES   = RESULTS / "figures"
MODELS    = RESULTS / "models"
LOG       = BASE / "overnight_run.log"
for d in (EXTRACTED, RESULTS, TABLES, FIGURES, MODELS):
    d.mkdir(parents=True, exist_ok=True)


def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


# ---------------------------------------------------------------- text cleaning
_DOMAIN_STOP = {
    "construction", "safety", "system", "systems", "method", "methods", "device",
    "devices", "apparatus", "invention", "embodiment", "embodiments", "present",
    "disclosed", "disclosure", "claim", "claims", "comprising", "including",
    "comprises", "wherein", "thereof", "first", "second", "third", "plurality",
    "configured", "based", "least", "one", "may", "also", "include", "includes",
    "use", "used", "using", "provide", "provided", "providing", "via", "said",
    "data", "information", "process", "result", "results", "approach", "paper",
    "study", "propose", "proposed", "model", "based", "able",
}

_token_re = re.compile(r"[a-z]+")
_lemmatizer = None
_stop = None


def _ensure_nltk():
    global _lemmatizer, _stop
    if _lemmatizer is not None:
        return
    try:
        from nltk.corpus import stopwords
        from nltk.stem import WordNetLemmatizer
        _lemmatizer = WordNetLemmatizer()
        _stop = set(stopwords.words("english")) | _DOMAIN_STOP
    except Exception:
        # fallback: no lemmatization, minimal stopword list
        _lemmatizer = False
        _stop = _DOMAIN_STOP | {
            "the", "and", "for", "are", "with", "that", "this", "from", "have",
            "was", "were", "which", "their", "they", "such", "been", "has", "can",
            "into", "more", "than", "other", "between", "each", "when", "where",
        }


def clean_text(text):
    """lowercase -> tokens -> drop stopwords -> lemmatize -> keep len>=3."""
    _ensure_nltk()
    toks = _token_re.findall(str(text).lower())
    out = []
    for t in toks:
        if len(t) < 3 or t in _stop:
            continue
        if _lemmatizer:
            t = _lemmatizer.lemmatize(t)
            if len(t) < 3 or t in _stop:
                continue
        out.append(t)
    return out


def read_jsonl(path):
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)
