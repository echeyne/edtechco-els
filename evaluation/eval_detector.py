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

The detector LLM call is cached per (state, extraction-hash, suffix)
in ``evaluation/.cache/`` so repeated runs are free unless the input changes.

Shared helpers live in ``evaluation/eval_common.py``; the parser counterpart is
``evaluation/eval_parser.py``.

Usage:
    python -m evaluation.eval_detector                        # all states
    python -m evaluation.eval_detector --state CA             # one state
    python -m evaluation.eval_detector --state CA --stability-runs 3
    python -m evaluation.eval_detector --no-cache             # force re-run
    python -m evaluation.eval_detector --extraction-dir outputs --golden-dir evaluation/ground_truth
    python -m evaluation.eval_detector --output-dir evaluation/review
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from evaluation.eval_common import (
    CACHE_DIR,
    _hash_blocks,
    _norm,
    _norm_age_band,
    run_regressions,
)
from els_pipeline.detector import (  # noqa: E402
    detect_structure,
    infer_depth_map,
)
from els_pipeline.models import TextBlock  # noqa: E402
from evaluation import regression_checks  # noqa: E402

logger = logging.getLogger("eval_detector")


# ---------- helpers ----------

def _title_key(e: dict) -> str:
    return _norm(e.get("title", ""))


def _tag_domains(elements: List[dict]) -> List[dict]:
    """Walk a flat, document-ordered element list and tag each element with
    its enclosing domain (the normalized title of the most-recent domain).

    The detector emits a flat list with no parent links; golden sets are
    authored in document order. This single pass gives us a domain context
    that disambiguates same-titled strands under different domains (e.g. CA's
    'Listening and Speaking' under both FLD and ELD) and lets precision be
    scoped to the domains the golden set actually annotates.

    Mutates and returns the list (adds the private '_domain' key)."""
    current: Optional[str] = None
    for e in elements:
        if (e.get("level") or "").strip() == "domain":
            current = _title_key(e)
        e["_domain"] = current
    return elements


def _match_key(e: dict) -> Tuple[Optional[str], str, str, Optional[str]]:
    """Domain-scoped, code-agnostic matching key: (enclosing domain, level,
    normalized title, normalized age_band). Codes are deliberately excluded —
    the detector emits document-local codes (e.g. '1.2') and invents
    sub_strand codes ('CI', 'WM'), neither of which the golden can mirror."""
    return (
        e.get("_domain"),
        (e.get("level") or "").strip(),
        _title_key(e),
        _norm_age_band(e.get("age_band")),
    )


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
    cache_key = f"detection-{state}-{_hash_blocks(blocks_data)}-{cache_suffix}.json"
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
    # Detected elements outside any golden-annotated domain — neither TP nor FP.
    ignored_out_of_scope: int = 0

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

    # Full element detail for review output
    extra_elements_full: List[dict] = field(default_factory=list)
    missing_golden_full: List[dict] = field(default_factory=list)
    matched_pairs: List[Tuple[dict, dict]] = field(default_factory=list)  # (golden, detected)

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

    # Tag both lists with their enclosing domain (in document order) so we can
    # match domain-scoped and scope false positives to annotated domains.
    _tag_domains(golden)
    _tag_domains(detected)

    # Domains the golden set actually annotates. A detected element only counts
    # toward precision if it falls inside one of these.
    annotated_domains = {
        _title_key(g) for g in golden
        if (g.get("level") or "").strip() == "domain"
    }

    # Index detected two ways. Use lists so age-banded duplicates (and
    # chunk-overlap repeats) don't overwrite each other.
    #   - domain-scoped: (domain, level, title, age_band) — disambiguates
    #     same-titled elements under different domains (CA's FLD/ELD).
    #   - domain-agnostic: (level, title, age_band) — fallback for documents
    #     that front-load all domain headers (AZ), where the last-seen-domain
    #     heuristic mis-assigns body content.
    det_index: Dict[Tuple, List[dict]] = defaultdict(list)
    det_index_no_dom: Dict[Tuple, List[dict]] = defaultdict(list)
    for d in detected:
        det_index[_match_key(d)].append(d)
        det_index_no_dom[_match_key(d)[1:]].append(d)

    matched_det_ids: set = set()

    def _first_unmatched(candidates: List[dict]) -> Optional[dict]:
        for cand in candidates:
            if id(cand) not in matched_det_ids:
                return cand
        return None

    for g in golden:
        # Skip incomplete annotations.
        if not g.get("level") or not g.get("title"):
            continue

        gid = g.get("test_case_id", "?")
        glevel = g.get("level")

        # Prefer a domain-scoped match; fall back to domain-agnostic.
        d = _first_unmatched(det_index.get(_match_key(g), []))
        if d is None:
            d = _first_unmatched(det_index_no_dom.get(_match_key(g)[1:], []))

        if d is None:
            rep.missing_test_cases.append(gid)
            rep.missing_golden_full.append(g)
            rep.per_level[glevel]["fn"] += 1
            if g.get("age_band"):
                rep.age_band_drops.append(gid)
            continue

        rep.matched += 1
        rep.matched_pairs.append((g, d))
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
        # Domain-scoped precision: only an unmatched detection inside an
        # annotated domain is a false positive. Everything else is real output
        # the golden subset simply doesn't cover — ignore it.
        if d.get("_domain") not in annotated_domains:
            rep.ignored_out_of_scope += 1
            continue
        rep.extra_elements.append((d.get("level", "?"), d.get("code", "?")))
        rep.extra_elements_full.append(d)
        rep.per_level[d.get("level", "?")]["fp"] += 1

    # Drop the private domain tag so it doesn't leak into serialized output.
    for e in detected:
        e.pop("_domain", None)
    for e in golden:
        e.pop("_domain", None)

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
) -> Tuple[StateReport, List[dict]]:
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

    rep.regressions = run_regressions(golden, detected, regression_checks.lookup)

    if stability_runs > 1:
        rep.stability_runs = stability_runs
        rep.stability_disagreement_rate, rep.stability_size_stdev = measure_stability(
            state, extraction_path, stability_runs
        )

    return rep, detected


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
        out.append(f"  extra detected (in-scope FPs) ({len(rep.extra_elements)}): {head}{'…' if len(rep.extra_elements) > 10 else ''}")
    out.append(f"  ignored (out-of-scope domains): {rep.ignored_out_of_scope}")

    out.append("  regression cases:")
    for cid, status, detail in rep.regressions:
        out.append(f"    [{status}] {cid} — {detail}")

    if rep.stability_runs > 1:
        out.append(f"  stability ({rep.stability_runs} runs):")
        out.append(f"    level disagreement rate: {rep.stability_disagreement_rate:.3f}")
        out.append(f"    output size stdev:        {rep.stability_size_stdev:.2f}")

    return "\n".join(out)


def write_review_dir(rep: StateReport, detected: List[dict], output_dir: Path) -> None:
    """Write per-state review files into output_dir for offline inspection."""
    output_dir.mkdir(parents=True, exist_ok=True)
    state = rep.state

    # Full untruncated text report
    (output_dir / f"{state}-report.txt").write_text(render_report(rep))

    # All detected elements (full JSON)
    (output_dir / f"{state}-detected.json").write_text(
        json.dumps(detected, indent=2, default=str)
    )

    # Side-by-side review: matched pairs, missing golden, extra detected
    review = {
        "state": state,
        "summary": {
            "golden": rep.n_golden,
            "detected": rep.n_detected,
            "matched": rep.matched,
            "ignored_out_of_scope": rep.ignored_out_of_scope,
            "precision": round(rep.precision, 4),
            "recall": round(rep.recall, 4),
            "f1": round(rep.f1, 4),
        },
        "matched": [
            {"golden": g, "detected": d}
            for g, d in rep.matched_pairs
        ],
        "missing_from_detected": rep.missing_golden_full,
        "extra_in_detected": rep.extra_elements_full,
        "regressions": [
            {"id": cid, "status": status, "detail": detail}
            for cid, status, detail in rep.regressions
        ],
    }
    (output_dir / f"{state}-review.json").write_text(
        json.dumps(review, indent=2, default=str)
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", action="append", help="Limit to specific state(s); repeatable")
    parser.add_argument("--extraction-dir", default="outputs", help="Directory holding {STATE}-extraction.json files")
    parser.add_argument("--golden-dir", default="evaluation/ground_truth_detector", help="Directory holding {STATE}.json golden sets")
    parser.add_argument("--no-cache", action="store_true", help="Disable detector-output cache")
    parser.add_argument("--stability-runs", type=int, default=1, help="Re-run the detector this many times to measure stability (>=2 enables it)")
    parser.add_argument("--report-json", help="Optional path to write the full report as JSON")
    parser.add_argument("--output-dir", help="Directory to write per-state review files ({STATE}-report.txt, {STATE}-detected.json, {STATE}-review.json)")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    extraction_dir = Path(args.extraction_dir)
    golden_dir = Path(args.golden_dir)

    if args.state:
        states = args.state
    else:
        states = sorted(p.stem for p in golden_dir.glob("*.json"))

    output_dir = Path(args.output_dir) if args.output_dir else None

    reports: List[StateReport] = []
    for st in states:
        ext_path = extraction_dir / f"{st}-extraction.json"
        gold_path = golden_dir / f"{st}.json"
        if not ext_path.exists() or not gold_path.exists():
            logger.warning(f"-- {st}: skipped (missing {ext_path if not ext_path.exists() else gold_path})")
            continue
        try:
            rep, detected = evaluate_state(
                st, ext_path, gold_path,
                use_cache=not args.no_cache,
                stability_runs=args.stability_runs,
            )
            reports.append(rep)
            if output_dir:
                write_review_dir(rep, detected, output_dir / st)
        except Exception as e:
            logger.exception(f"-- {st}: ERROR — {e}")

    for rep in reports:
        print(render_report(rep))

    if output_dir:
        print(f"\nReview files written to {output_dir}/")

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
                "ignored_out_of_scope": r.ignored_out_of_scope,
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
