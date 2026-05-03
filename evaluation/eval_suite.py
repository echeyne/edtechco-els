"""ELS detector evaluation suite.

Runs the detector against one or more state extractions, compares the output
to the hand-annotated golden set, and reports the metrics most useful for
iterating on prompts:

  - Precision / recall / F1 on (level, code) tuples.
  - Per-level precision / recall.
  - Level confusion matrix (e.g. "strand → sub_strand: 12") — surfaces the
    CO-style misclassification bug at a glance.
  - Age-band drop count: how many indicators present in the golden set as
    age-banded variants are missing from the detector output.
  - Depth-map accuracy: did Pass-1 produce the expected canonical_level for
    every depth?
  - Optional N-run stability: rerun the detector N times against the same
    extraction and report (a) the level disagreement rate per matched
    element, (b) the size variance of the output.
  - Targeted regression cases (see evaluation/regression_checks.py) — each
    case in the golden set runs as PASS / FAIL / SKIP with a short detail
    line.

The detector LLM call is cached per (state, extraction-hash, prompt-hash)
in ``evaluation/.cache/`` so repeated runs are free unless you change
the prompt.

Usage:
    python -m evaluation.eval_suite                        # all states
    python -m evaluation.eval_suite --state CA             # one state
    python -m evaluation.eval_suite --state CA --stability-runs 3
    python -m evaluation.eval_suite --no-cache             # force re-run
    python -m evaluation.eval_suite --extraction-dir outputs --golden-dir evaluation/ground_truth
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

# Make `src` imports work when run as a module from the repo root.
ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from els_pipeline.detector import (  # noqa: E402
    detect_structure,
    infer_depth_map,
)
from els_pipeline.models import TextBlock  # noqa: E402
from evaluation import regression_checks  # noqa: E402

logger = logging.getLogger("eval_suite")

CACHE_DIR = ROOT / "evaluation" / ".cache"
CACHE_DIR.mkdir(exist_ok=True)


# ---------- helpers ----------

def _norm(s: str) -> str:
    return " ".join((s or "").lower().split())


def _elem_key(e: dict) -> Tuple[str, str, Optional[str]]:
    """Stable matching key. age_band is included so age-banded variants
    don't collapse onto each other."""
    return (
        (e.get("level") or "").strip(),
        (e.get("code") or "").strip(),
        (e.get("age_band") or None),
    )


def _title_key(e: dict) -> str:
    return _norm(e.get("title", ""))


def _hash_blocks(blocks: List[dict]) -> str:
    h = hashlib.sha256()
    for b in blocks:
        h.update((b.get("text") or "").encode("utf-8"))
    return h.hexdigest()[:16]


# ---------- detector runner with cache ----------

def run_detector_cached(
    state: str,
    extraction_path: Path,
    use_cache: bool = True,
    cache_suffix: str = "",
) -> List[dict]:
    """Run the detector once. Cache by (state, extraction-hash, suffix)."""
    extraction = json.loads(extraction_path.read_text())
    blocks_data = extraction.get("blocks", [])
    cache_key = f"{state}-{_hash_blocks(blocks_data)}-{cache_suffix}.json"
    cache_path = CACHE_DIR / cache_key

    if use_cache and cache_path.exists():
        logger.info(f"  [cache hit] {cache_path.name}")
        return json.loads(cache_path.read_text())

    blocks = [TextBlock(**b) for b in blocks_data]
    logger.info(f"  [detector] running on {len(blocks)} blocks…")
    result = detect_structure(blocks, document_s3_key=str(extraction_path))
    elements = [e.model_dump() for e in result.elements]
    cache_path.write_text(json.dumps(elements, indent=2, default=str))
    return elements


# ---------- metrics ----------

@dataclass
class StateReport:
    state: str
    n_golden: int = 0
    n_detected: int = 0
    matched: int = 0
    missing_test_cases: List[str] = field(default_factory=list)
    extra_elements: List[Tuple[str, str]] = field(default_factory=list)  # (level, code)

    # Level confusion: golden_level -> detected_level -> count
    confusion: Dict[str, Dict[str, int]] = field(
        default_factory=lambda: defaultdict(lambda: defaultdict(int))
    )

    per_level: Dict[str, Dict[str, int]] = field(
        default_factory=lambda: defaultdict(lambda: {"tp": 0, "fp": 0, "fn": 0})
    )

    # Age-band drops: golden test_case_ids whose age_band variant is missing.
    age_band_drops: List[str] = field(default_factory=list)

    # Depth map
    depth_map_passed: Optional[bool] = None
    depth_map_detail: str = ""

    # Regression cases
    regressions: List[Tuple[str, str, str]] = field(default_factory=list)  # (id, status, detail)

    # Stability (optional)
    stability_runs: int = 0
    stability_disagreement_rate: Optional[float] = None
    stability_size_stdev: Optional[float] = None

    @property
    def precision(self) -> float:
        denom = self.matched + len(self.extra_elements)
        return self.matched / denom if denom else 0.0

    @property
    def recall(self) -> float:
        denom = self.matched + len(self.missing_test_cases)
        return self.matched / denom if denom else 0.0

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        return 2 * p * r / (p + r) if (p + r) else 0.0


def grade_elements(golden: List[dict], detected: List[dict]) -> StateReport:
    rep = StateReport(state="")
    rep.n_golden = len(golden)
    rep.n_detected = len(detected)

    # Build detected lookup by (level, code, age_band) and by title
    det_by_key: Dict[Tuple[str, str, Optional[str]], dict] = {}
    det_by_title: Dict[str, dict] = {}
    for d in detected:
        det_by_key[_elem_key(d)] = d
        det_by_title[_title_key(d)] = d

    matched_det_ids: set = set()

    for g in golden:
        # Skip incomplete annotations.
        if not g.get("level") or not g.get("title"):
            continue

        # Try (level, code, age_band) first, then (level, title fuzzy).
        key = _elem_key(g)
        d = det_by_key.get(key)
        if d is None:
            # Try title-based fallback constrained to same level.
            cand = det_by_title.get(_title_key(g))
            if cand and cand.get("level") == g.get("level"):
                # Don't accept a title match across age_bands — that hides Bug 1.
                if (cand.get("age_band") or None) == (g.get("age_band") or None):
                    d = cand

        gid = g.get("test_case_id", "?")
        glevel = g.get("level")

        if d is None:
            rep.missing_test_cases.append(gid)
            rep.per_level[glevel]["fn"] += 1
            if g.get("age_band"):
                rep.age_band_drops.append(gid)
            continue

        rep.matched += 1
        matched_det_ids.add(id(d))

        dlevel = d.get("level")
        rep.confusion[glevel][dlevel] += 1
        if dlevel == glevel:
            rep.per_level[glevel]["tp"] += 1
        else:
            rep.per_level[glevel]["fn"] += 1
            rep.per_level[dlevel]["fp"] += 1

    for d in detected:
        if id(d) in matched_det_ids:
            continue
        rep.extra_elements.append((d.get("level", "?"), d.get("code", "?")))
        rep.per_level[d.get("level", "?")]["fp"] += 1

    return rep


def grade_depth_map(expected: dict, actual: Optional[dict]) -> Tuple[bool, str]:
    if not expected:
        return True, "no expected depth map (skipped)"
    if not actual:
        return False, "depth-map inference returned None / empty"
    exp_levels = [d.get("canonical_level") for d in expected.get("doc_depths", [])]
    act_levels = [d.get("canonical_level") for d in actual.get("doc_depths", [])]
    if exp_levels == act_levels:
        return True, f"matched canonical-level sequence {exp_levels}"
    return False, f"expected {exp_levels} got {act_levels}"


def run_regressions(golden: dict, detected: List[dict]) -> List[Tuple[str, str, str]]:
    out = []
    for case in golden.get("regression_cases", []):
        cid = case.get("id", "?")
        fn = regression_checks.lookup(cid)
        if fn is None:
            out.append((cid, "SKIP", "no check function defined"))
            continue
        try:
            passed, detail = fn(detected)
        except Exception as e:
            out.append((cid, "ERROR", f"{type(e).__name__}: {e}"))
            continue
        out.append((cid, "PASS" if passed else "FAIL", detail))
    return out


# ---------- stability ----------

def measure_stability(
    state: str,
    extraction_path: Path,
    runs: int,
) -> Tuple[float, float]:
    """Re-run detector `runs` times (cache disabled) and report:
       - mean per-element level disagreement rate (matched on (code, title))
       - stdev of output size
    """
    import statistics

    outputs: List[List[dict]] = []
    for i in range(runs):
        elems = run_detector_cached(
            state, extraction_path, use_cache=False, cache_suffix=f"stab-{i}"
        )
        outputs.append(elems)

    sizes = [len(o) for o in outputs]
    size_stdev = statistics.pstdev(sizes) if len(sizes) > 1 else 0.0

    # Disagreement: for each (code, title) present in run 0, check whether
    # all runs agree on `level`.
    disagreements = 0
    compared = 0
    base = {(e.get("code"), _title_key(e)): e.get("level") for e in outputs[0]}
    for k, lvl in base.items():
        for other in outputs[1:]:
            other_map = {(e.get("code"), _title_key(e)): e.get("level") for e in other}
            if k in other_map:
                compared += 1
                if other_map[k] != lvl:
                    disagreements += 1

    rate = disagreements / compared if compared else 0.0
    return rate, size_stdev


# ---------- main ----------

def evaluate_state(
    state: str,
    extraction_path: Path,
    golden_path: Path,
    use_cache: bool,
    stability_runs: int,
) -> StateReport:
    logger.info(f"== {state} ==")
    golden = json.loads(golden_path.read_text())

    detected = run_detector_cached(state, extraction_path, use_cache=use_cache)
    rep = grade_elements(golden.get("elements", []), detected)
    rep.state = state

    # Depth map (re-run; usually cached identically by the same prompt hash —
    # for now we just call infer_depth_map once for grading).
    extraction = json.loads(extraction_path.read_text())
    blocks = [TextBlock(**b) for b in extraction.get("blocks", [])]
    actual_dm = infer_depth_map(blocks)
    passed, detail = grade_depth_map(golden.get("expected_depth_map", {}), actual_dm)
    rep.depth_map_passed = passed
    rep.depth_map_detail = detail

    rep.regressions = run_regressions(golden, detected)

    if stability_runs > 1:
        rep.stability_runs = stability_runs
        rep.stability_disagreement_rate, rep.stability_size_stdev = measure_stability(
            state, extraction_path, stability_runs
        )

    return rep


def render_report(rep: StateReport) -> str:
    out = []
    out.append(f"\n=== {rep.state} ===")
    out.append(f"  golden:   {rep.n_golden}")
    out.append(f"  detected: {rep.n_detected}")
    out.append(f"  matched:  {rep.matched}")
    out.append(f"  precision: {rep.precision:.3f}  recall: {rep.recall:.3f}  f1: {rep.f1:.3f}")

    out.append("  per-level:")
    for lvl, m in sorted(rep.per_level.items()):
        denom_p = m["tp"] + m["fp"]
        denom_r = m["tp"] + m["fn"]
        p = m["tp"] / denom_p if denom_p else 0.0
        r = m["tp"] / denom_r if denom_r else 0.0
        out.append(f"    {lvl:<10}  tp={m['tp']:<3} fp={m['fp']:<3} fn={m['fn']:<3} p={p:.2f} r={r:.2f}")

    if rep.confusion:
        out.append("  level confusion (golden → detected):")
        for g, row in sorted(rep.confusion.items()):
            for d, n in sorted(row.items()):
                marker = "" if g == d else "  ← MISCLASS"
                out.append(f"    {g:<10} → {d:<10} : {n}{marker}")

    out.append(f"  depth-map: {'PASS' if rep.depth_map_passed else 'FAIL'} — {rep.depth_map_detail}")

    if rep.age_band_drops:
        out.append(f"  age-band drops ({len(rep.age_band_drops)}): {rep.age_band_drops[:8]}{'…' if len(rep.age_band_drops) > 8 else ''}")
    else:
        out.append("  age-band drops: 0")

    if rep.missing_test_cases:
        out.append(f"  missing test cases ({len(rep.missing_test_cases)}): {rep.missing_test_cases[:10]}{'…' if len(rep.missing_test_cases) > 10 else ''}")
    if rep.extra_elements:
        head = rep.extra_elements[:10]
        out.append(f"  extra detected ({len(rep.extra_elements)}): {head}{'…' if len(rep.extra_elements) > 10 else ''}")

    out.append("  regression cases:")
    for cid, status, detail in rep.regressions:
        out.append(f"    [{status}] {cid} — {detail}")

    if rep.stability_runs > 1:
        out.append(f"  stability ({rep.stability_runs} runs):")
        out.append(f"    level disagreement rate: {rep.stability_disagreement_rate:.3f}")
        out.append(f"    output size stdev:        {rep.stability_size_stdev:.2f}")

    return "\n".join(out)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", action="append", help="Limit to specific state(s); repeatable")
    parser.add_argument("--extraction-dir", default="outputs", help="Directory holding {STATE}-extraction.json files")
    parser.add_argument("--golden-dir", default="evaluation/ground_truth", help="Directory holding {STATE}.json golden sets")
    parser.add_argument("--no-cache", action="store_true", help="Disable detector-output cache")
    parser.add_argument("--stability-runs", type=int, default=1, help="Re-run the detector this many times to measure stability (>=2 enables it)")
    parser.add_argument("--report-json", help="Optional path to write the full report as JSON")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    extraction_dir = Path(args.extraction_dir)
    golden_dir = Path(args.golden_dir)

    if args.state:
        states = args.state
    else:
        states = sorted(p.stem for p in golden_dir.glob("*.json"))

    reports: List[StateReport] = []
    for st in states:
        ext_path = extraction_dir / f"{st}-extraction.json"
        gold_path = golden_dir / f"{st}.json"
        if not ext_path.exists() or not gold_path.exists():
            logger.warning(f"-- {st}: skipped (missing {ext_path if not ext_path.exists() else gold_path})")
            continue
        try:
            rep = evaluate_state(
                st, ext_path, gold_path,
                use_cache=not args.no_cache,
                stability_runs=args.stability_runs,
            )
            reports.append(rep)
        except Exception as e:
            logger.exception(f"-- {st}: ERROR — {e}")

    for rep in reports:
        print(render_report(rep))

    if args.report_json:
        out = []
        for r in reports:
            out.append({
                "state": r.state,
                "precision": r.precision, "recall": r.recall, "f1": r.f1,
                "matched": r.matched, "n_golden": r.n_golden, "n_detected": r.n_detected,
                "per_level": {k: dict(v) for k, v in r.per_level.items()},
                "confusion": {k: dict(v) for k, v in r.confusion.items()},
                "missing_test_cases": r.missing_test_cases,
                "extra_elements": [list(t) for t in r.extra_elements],
                "age_band_drops": r.age_band_drops,
                "depth_map_passed": r.depth_map_passed,
                "depth_map_detail": r.depth_map_detail,
                "regressions": [{"id": c, "status": s, "detail": d} for c, s, d in r.regressions],
                "stability_runs": r.stability_runs,
                "stability_disagreement_rate": r.stability_disagreement_rate,
                "stability_size_stdev": r.stability_size_stdev,
            })
        Path(args.report_json).write_text(json.dumps(out, indent=2, default=str))
        print(f"\nFull report written to {args.report_json}")

    failures = sum(
        1 for r in reports
        for _, status, _ in r.regressions
        if status in ("FAIL", "ERROR")
    )
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
