"""Grade the whole-document single-prompt arm with the SAME suite (Task 10).

Mirrors ``evaluation.baselines.eval_baseline`` exactly, and for the same
reason: the number is only worth having if it comes out of the same
``grade_elements``, the same ``_match_key`` and the same goldens as the full
method's number. A second grader would make the two incomparable.

Two differences from the LLM detector's own driver, both deliberate:

  * ``grade_depth_map_pass=False`` -- this arm has no Pass-1, so grading a
    depth map would report FAIL, which reads as a quality failure rather than
    as an absent stage. It records the third state (ABLATED) instead, exactly
    as the rule-based baseline does.
  * ``stability_runs`` defaults to 1. This arm is a single nondeterministic
    call per state, so it is MORE exposed to sampling than the chunked method,
    not less; ``--stability-runs N`` is available and a published comparison
    should use it rather than a single draw.

Usage:
    python -m evaluation.baselines.eval_whole_document \
        --extraction-dir outputs/08-26-26 \
        --report-json paper/results/task10_YYYYMMDD/whole_document.json
"""
from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from pathlib import Path
from typing import List

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from evaluation.baselines.whole_document import run_whole_document  # noqa: E402
from evaluation.eval_common import code_version_hash  # noqa: E402
from evaluation.eval_detector import (  # noqa: E402
    StateReport,
    evaluate_state,
    render_report,
    report_to_dict,
    write_review_dir,
)

logger = logging.getLogger(__name__)

DEPTH_MAP_DETAIL = (
    "ABLATED — the whole-document single-prompt arm has no Pass-1 stage to grade"
)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--state", action="append",
                   help="Limit to specific state(s); repeatable")
    p.add_argument("--extraction-dir", default="outputs/08-26-26",
                   help="Directory holding {STATE}-extraction.json files")
    p.add_argument("--golden-dir", default="evaluation/ground_truth_detector")
    p.add_argument("--stability-runs", type=int, default=1,
                   help="Repeat the single call N times per state and report "
                        "disagreement. A published comparison should use N>1: "
                        "one prompt per document makes this arm MORE exposed to "
                        "sampling than the chunked method, not less.")
    p.add_argument("--no-cache", action="store_true",
                   help="Force fresh Bedrock calls (costs money; see the module "
                        "docstring's cost note)")
    p.add_argument("--report-json", help="Write the full report as JSON")
    p.add_argument("--output-dir", help="Per-state review files")
    args = p.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    extraction_dir = Path(args.extraction_dir)
    golden_dir = Path(args.golden_dir)
    # ⚠️ Only a bare two-letter state code names a state. The golden directories
    # also hold tier-scoped goldens (KY_trimmed.json), their _provenance siblings,
    # and any work-in-progress draft; enumerating those sends the suite hunting for
    # a nonexistent "<name>-extraction.json", and it is the same glob that once
    # silently broke the prompt-provenance scan. So the rule is shape-based rather
    # than a list of names to exclude. Tier-scoped goldens are graded by
    # paper/analysis/scale_grade*.py, which take explicit paths.
    states = args.state or sorted(q.stem for q in golden_dir.glob("*.json")
                                  if re.fullmatch(r"[A-Z]{2}", q.stem))
    output_dir = Path(args.output_dir) if args.output_dir else None

    def _runner(state, extraction_path, use_cache):
        return run_whole_document(state, extraction_path,
                                  use_cache=not args.no_cache)

    reports: List[StateReport] = []
    for st in states:
        ext_path = extraction_dir / f"{st}-extraction.json"
        gold_path = golden_dir / f"{st}.json"
        if not ext_path.exists() or not gold_path.exists():
            missing = ext_path if not ext_path.exists() else gold_path
            logger.warning(f"-- {st}: skipped (missing {missing})")
            continue
        try:
            rep, detected = evaluate_state(
                st, ext_path, gold_path,
                use_cache=not args.no_cache,
                stability_runs=args.stability_runs,
                detect_fn=_runner,
                grade_depth_map_pass=False,
                depth_map_skip_detail=DEPTH_MAP_DETAIL,
            )
            reports.append(rep)
            if output_dir:
                write_review_dir(rep, detected, output_dir / st)
        except Exception as e:  # noqa: BLE001 — mirror eval_baseline's posture
            logger.exception(f"-- {st}: ERROR — {e}")

    for rep in reports:
        print(render_report(rep))

    if args.report_json:
        out = Path(args.report_json)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps({
            "arm": "whole-document single prompt: one call per document, no "
                   "Pass-1 depth map, no chunking, no deterministic repairs",
            "graded_by": "evaluation.eval_detector.evaluate_state — the same "
                         "grader, matcher and goldens as the full method",
            "code_version_hash": code_version_hash(),
            "extraction_dir": str(extraction_dir),
            "stability_runs": args.stability_runs,
            "⚠️_scope": "Every state's subset extraction is 3.7K-7.9K tokens and "
                        "fits in one prompt. A result here therefore speaks to "
                        "the _only_subset tier ONLY; it says nothing about the "
                        "trimmed or full tiers, where the document does not fit "
                        "and chunking is not optional.",
            "states": {r.state: report_to_dict(r) for r in reports},
        }, indent=2, ensure_ascii=False))
        print(f"\nwrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
