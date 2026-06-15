"""
normalization.py — patent document-number normalization (single source of truth).

doc-number normalization rules (applied identically to metadata CSV and XML):
  R1. strip surrounding whitespace, uppercase
  R2. drop leading "US" country prefix      (e.g. "US 12651200" -> "12651200")
  R3. remove comma/space/hyphen/slash        (e.g. "12,635,592" -> "12635592")
  R4. split alpha prefix (D, RE, PP, T, H ...) from the numeric core
  R5. strip leading zeros from the numeric core (e.g. "D0696836" -> "D696836")
  R6. recombine prefix + cleaned numeric core
"""
import re

_ALPHA = re.compile(r"^([A-Z]+)")


def normalize_docnum(raw) -> str:
    if raw is None:
        return ""
    s = str(raw).strip().upper()          # R1
    if s.startswith("US"):                 # R2
        s = s[2:].strip()
    s = re.sub(r"[,\s\-/]", "", s)         # R3
    m = _ALPHA.match(s)                    # R4
    prefix = m.group(1) if m else ""
    num = s[len(prefix):].lstrip("0") or "0"   # R5
    return prefix + num                    # R6
