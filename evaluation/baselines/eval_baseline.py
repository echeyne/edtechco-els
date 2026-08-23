"""Grade the rule-based baseline with the LLM detector's own eval suite.

⚠️ THE POINT OF THIS FILE IS THAT IT CONTAINS NO GRADING LOGIC. Every metric
comes from ``evaluation.eval_detector`` — the same ``grade_elements``, the same
``_match_key``, the same per-level tp/fp/fn, the same code and description
accuracy, the same regression cases, the same ``--report-json`` shape. If a
number here were computed by a second grader it would not be comparable to the
LLM's, and the comparison is the entire deliverable of Task 4.

Two things differ from the LLM path, both deliberate and both recorded:

  1. **No Bedrock, no cache.** ``detect_structure_baseline`` is pure Python and
     deterministic, so a cache would buy nothing and a stale entry could only
     mislead. ``--no-cache`` is implied and there is no cache key to collide
     with the LLM's.
  2. **No depth map.** The baseline has no Pass-1, so the depth map is recorded
     as the third state (ABLATED) rather than graded — the mechanism
     ``eval_detector`` already uses for Task 3's off-arm. Grading it would print
     FAIL, which reads as a quality result rather than as an absent stage.

Usage:
    python -m evaluation.baselines.eval_baseline --extraction-dir outputs/08-22-26-4
    python -m evaluation.baselines.eval_baseline --extraction-dir outputs/08-22-26-4 \
        --state CA --output-dir paper/results/task4_.../review_baseline
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import List

from els_pipeline.models import TextBlock
from evaluation.baselines.rule_based import detect_structure_baseline
from evaluation.eval_common import as_plain_json
from evaluation.eval_detector import (
    StateReport,
    evaluate_state,
    render_report,
    report_to_dict,
    write_review_dir,
)

logger = logging.getLogger("eval_baseline")

DEPTH_MAP_DETAIL = (
    "N/A — the rule-based baseline has no Pass-1 depth-map stage to grade"
)


def run_baseline(state: str, extraction_path: Path, use_cache: bool = False) -> List[dict]:
    """A ``eval_detector.DetectFn`` over the rule-based extractor.

    ``use_cache`` is accepted for signature parity and ignored: the extractor is
    deterministic, so re-running it costs milliseconds and can never disagree
    with a cached copy.
    """
    extraction = json.loads(extraction_path.read_text())
    blocks = [TextBlock(**b) for b in extraction.get("blocks", [])]
    logger.info(f"  [baseline] running on {len(blocks)} blocks…")
    result = detect_structure_baseline(blocks, document_s3_key=str(extraction_path))
    return as_plain_json([e.model_dump() for e in result.elements])


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--state", action="append", help="Limit to specific state(s); repeatable")
    p.add_argument("--extraction-dir", default="outputs",
                   help="Directory holding {STATE}-extraction.json files")
    p.add_argument("--golden-dir", default="evaluation/ground_truth_detector",
                   help="Directory holding {STATE}.json golden sets")
    p.add_argument("--report-json", help="Path to write the full report as JSON "
                                         "(same shape as eval_detector's)")
    p.add_argument("--output-dir", help="Directory to write per-state review files")
    args = p.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    extraction_dir = Path(args.extraction_dir)
    golden_dir = Path(args.golden_dir)
    states = args.state or sorted(q.stem for q in golden_dir.glob("*.json"))
    output_dir = Path(args.output_dir) if args.output_dir else None

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
                use_cache=False,
                stability_runs=1,
                detect_fn=run_baseline,
                grade_depth_map_pass=False,
                depth_map_skip_detail=DEPTH_MAP_DETAIL,
            )
            reports.append(rep)
            if output_dir:
                write_review_dir(rep, detected, output_dir / st)
        except Exception as e:  # noqa: BLE001 — mirror eval_detector's posture
            logger.exception(f"-- {st}: ERROR — {e}")

    for rep in reports:
        print(render_report(rep))

    if output_dir:
        print(f"\nReview files written to {output_dir}/")

    if args.report_json:
        Path(args.report_json).write_text(
            json.dumps([report_to_dict(r) for r in reports], indent=2, default=str)
        )
        print(f"\nFull report written to {args.report_json}")

    # Unlike eval_detector, a failing regression case is the EXPECTED outcome
    # here and must not read as a crash, so the exit code reflects only whether
    # any state was gradeable at all.
    return 0 if reports else 1


if __name__ == "__main__":
    sys.exit(main())
