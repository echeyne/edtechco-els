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
import json
import sys
from pathlib import Path
from typing import Any, Callable, List, Optional, Tuple

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

# Source files whose contents decide what a cached artifact contains. The run
# cache stores POST-PROCESSED stage output, so anything in these files can
# change the answer: a prompt edit most obviously, but equally a change to the
# JSON extraction, the overlap de-duplication, or the cross-chunk code
# reconciliation. ``parser.py`` counts for the DETECTOR cache too — the
# detector's ``_dedup_elements`` reuses ``normalize_element_codes`` and
# ``assign_domain_scopes`` from it.
#
# Hashing the source into the cache key makes any such edit invalidate the
# cache on its own. Without it a cached run after a prompt edit silently
# replays the OLD output and reports it as a pass — a failure mode that is
# invisible precisely when it matters most, right after a change you are
# trying to validate. Coarse on purpose: a comment-only edit also busts the
# cache, which costs one re-run and never costs a wrong answer.
_CODE_SOURCES = (
    SRC / "els_pipeline" / "detector.py",
    SRC / "els_pipeline" / "parser.py",
)


def code_version_hash() -> str:
    """Short hash of the pipeline source the cached stage output depends on."""
    h = hashlib.sha256()
    for path in sorted(_CODE_SOURCES):
        h.update(path.read_bytes())
    return h.hexdigest()[:8]


def as_plain_json(obj: Any) -> Any:
    """Round-trip a freshly-computed result through JSON.

    A cache HIT returns whatever ``json.loads`` produces; a cache MISS returns
    the live objects. Without this the two paths differ in shape — most
    visibly ``level``, which is a ``HierarchyLevelEnum`` on the live path and a
    plain string on the cached one. Matching survives that (the enum subclasses
    ``str``), but reports render the enum's repr, and any future comparison
    that is not str-based would silently behave differently depending on
    whether the cache happened to be warm. Normalizing here makes a cached run
    and an uncached run indistinguishable to everything downstream."""
    return json.loads(json.dumps(obj, default=str, ensure_ascii=False))


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
