"""Shared utilities for the ELS evaluation harnesses.

Both `eval_detector.py` (grades `detect_structure`) and `eval_parser.py`
(grades `parse_hierarchy`) build on these target-agnostic helpers: the `src`
import bootstrap, the on-disk run cache, small string/age-band normalizers, a
content hasher for cache keys, and a generic regression-case runner.

Anything specific to one stage (the detector's domain-scoped element matching,
the parser's hierarchy grading, etc.) lives in that stage's own module.
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path
from typing import Callable, List, Optional, Tuple

# Make `src` imports work when run as a module from the repo root.
ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

# Shared run cache. Detector and parser outputs are cached here keyed by
# (state, input-hash, suffix) so repeated grading runs are free.
CACHE_DIR = ROOT / "evaluation" / ".cache"
CACHE_DIR.mkdir(exist_ok=True)


# ---------- string / age-band normalization ----------

def _norm(s: Optional[str]) -> str:
    """Lowercase + collapse whitespace. Used for title/name matching."""
    return " ".join((s or "").lower().split())


def _norm_age_band(ab: Optional[str]) -> Optional[str]:
    """Canonicalize an age-band string for comparison. The detector (and the
    source PDFs) spell the half-year glyph inconsistently — unicode '½' vs
    ASCII '1/2' — so fold both to a single form and collapse whitespace/case.
    Returns None for empty/missing bands."""
    if not ab:
        return None
    s = ab.replace("½", "1/2")
    s = " ".join(s.lower().split())
    return s or None


# ---------- cache key hashing ----------

def _hash_blocks(items: List[dict], text_key: str = "text") -> str:
    """Stable short hash of a list of dicts by one text field — used to key the
    run cache so a changed input invalidates it. Works for detector input
    (TextBlocks, ``text``) and parser input (detected elements, ``source_text``)."""
    h = hashlib.sha256()
    for b in items:
        h.update((b.get(text_key) or "").encode("utf-8"))
    return h.hexdigest()[:16]


# ---------- regression runner ----------

def run_regressions(
    golden: dict,
    data: List[dict],
    lookup_fn: Callable[[str], Optional[Callable]],
) -> List[Tuple[str, str, str]]:
    """Run each `regression_cases` entry in the golden set against `data`.

    `lookup_fn` maps a case id to a check function (e.g.
    ``regression_checks.lookup`` for detector checks or
    ``regression_checks.lookup_parser`` for parser checks). A case with no
    matching function for this stage is reported SKIP, so detector-only and
    parser-only cases can coexist in the same golden file.
    """
    out: List[Tuple[str, str, str]] = []
    for case in golden.get("regression_cases", []):
        cid = case.get("id", "?")
        fn = lookup_fn(cid)
        if fn is None:
            out.append((cid, "SKIP", "no check function for this stage"))
            continue
        try:
            passed, detail = fn(data)
        except Exception as e:
            out.append((cid, "ERROR", f"{type(e).__name__}: {e}"))
            continue
        out.append((cid, "PASS" if passed else "FAIL", detail))
    return out
