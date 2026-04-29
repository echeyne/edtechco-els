#!/usr/bin/env python3
"""Run LLM vs baseline detection comparison for a pipeline run.

Loads the Textract extraction output from S3, runs both the LLM detector
and the baseline regex detector on the same TextBlocks, then evaluates
both against ground truth (if provided) or just saves the outputs for
manual inspection.

Usage:
    # With ground truth (full evaluation):
    python evaluation/run_comparison.py \
        --country US --state TX --year 2024 --run-id abc123 \
        --ground-truth evaluation/ground_truth/TX.json

    # Without ground truth (just run both detectors and save outputs):
    python evaluation/run_comparison.py \
        --country US --state TX --year 2024 --run-id abc123

    # Use a local extraction file instead of S3:
    python evaluation/run_comparison.py \
        --extraction-file path/to/extraction_output.json \
        --ground-truth evaluation/ground_truth/TX.json

    # Skip the LLM detector (use existing pipeline detection output from S3):
    python evaluation/run_comparison.py \
        --country US --state TX --year 2024 --run-id abc123 \
        --skip-llm \
        --ground-truth evaluation/ground_truth/TX.json
"""

import argparse
import json
import logging
import sys
import time
from pathlib import Path

# Add src/ to path so we can import pipeline modules
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from els_pipeline.config import Config
from els_pipeline.models import TextBlock
from els_pipeline.detector import detect_structure
from els_pipeline.baseline_detector import detect_structure_baseline
from els_pipeline.s3_helpers import load_json_from_s3, construct_intermediate_key

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def load_extraction_blocks(
    country: str = "",
    state: str = "",
    year: int = 0,
    run_id: str = "",
    extraction_file: str = "",
) -> list[TextBlock]:
    """Load TextBlocks from S3 or a local file."""
    if extraction_file:
        logger.info(f"Loading extraction from local file: {extraction_file}")
        data = json.loads(Path(extraction_file).read_text())
    else:
        key = construct_intermediate_key(country, state, year, "extraction", run_id)
        logger.info(f"Loading extraction from S3: {Config.S3_PROCESSED_BUCKET}/{key}")
        data = load_json_from_s3(Config.S3_PROCESSED_BUCKET, key)

    blocks = [TextBlock(**b) for b in data["blocks"]]
    logger.info(
        f"Loaded {len(blocks)} text blocks, "
        f"{data.get('total_pages', '?')} pages"
    )
    return blocks


def load_existing_llm_detection(
    country: str, state: str, year: int, run_id: str,
) -> dict:
    """Load existing LLM detection output from S3."""
    key = construct_intermediate_key(country, state, year, "detection", run_id)
    logger.info(f"Loading existing LLM detection from S3: {key}")
    data = load_json_from_s3(Config.S3_PROCESSED_BUCKET, key)
    return data


def run_detector(name: str, detect_fn, blocks: list[TextBlock]) -> dict:
    """Run a detector and return serialized results with timing."""
    logger.info(f"Running {name} detector on {len(blocks)} blocks...")
    start = time.monotonic()
    result = detect_fn(blocks)
    elapsed = time.monotonic() - start

    output = {
        "elements": [e.model_dump() for e in result.elements],
        "review_count": result.review_count,
        "status": result.status,
        "detector": name,
        "elapsed_seconds": round(elapsed, 2),
        "total_elements": len(result.elements),
    }

    level_counts = {}
    for e in result.elements:
        level_counts[e.level.value] = level_counts.get(e.level.value, 0) + 1

    logger.info(
        f"{name} detector: {len(result.elements)} elements in {elapsed:.1f}s "
        f"({level_counts})"
    )
    return output


def run_evaluation(gt_elements, det_elements, label):
    """Run evaluation and return report dict. Imports here to avoid circular deps."""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from evaluate import evaluate_detection

    report = evaluate_detection(gt_elements, det_elements)
    summary = report.summary()
    summary["detector"] = label
    return summary, report


def print_comparison_table(llm_summary, baseline_summary):
    """Print a side-by-side comparison table."""
    print(f"\n{'='*65}")
    print(f"  Detection Comparison: LLM vs Baseline")
    print(f"{'='*65}\n")

    rows = [
        ("Elements found", str(llm_summary.get("element_detection", {}).get("tp", 0) + llm_summary.get("element_detection", {}).get("fp", 0)),
         str(baseline_summary.get("element_detection", {}).get("tp", 0) + baseline_summary.get("element_detection", {}).get("fp", 0))),
    ]

    for metric_key, label in [
        ("element_detection", "Element Detection"),
        ("level_classification", "Level Classification"),
        ("code_extraction", "Code Extraction"),
    ]:
        llm_m = llm_summary.get(metric_key, {})
        base_m = baseline_summary.get(metric_key, {})
        for sub in ["precision", "recall", "f1"]:
            lv = llm_m.get(sub, 0)
            bv = base_m.get(sub, 0)
            delta = lv - bv
            rows.append((
                f"{label} {sub.upper()[0]}",
                f"{lv:.3f}",
                f"{bv:.3f}",
                f"{delta:+.3f}",
            ))

    headers = ["Metric", "LLM", "Baseline", "Delta"]
    col_w = [max(len(r[i]) for r in [tuple(headers)] + rows) for i in range(len(headers))]
    fmt = "  ".join(f"{{:<{w}}}" for w in col_w)

    print(fmt.format(*headers))
    print("-" * (sum(col_w) + 2 * (len(headers) - 1)))
    for row in rows:
        if len(row) == 3:
            print(fmt.format(row[0], row[1], row[2], ""))
        else:
            print(fmt.format(*row))

    print(f"\n{'='*65}\n")


def main():
    parser = argparse.ArgumentParser(
        description="Run LLM vs baseline detection comparison"
    )
    parser.add_argument("--country", default="US")
    parser.add_argument("--state", required=False)
    parser.add_argument("--year", type=int, required=False)
    parser.add_argument("--run-id", required=False)
    parser.add_argument(
        "--extraction-file",
        help="Local path to extraction output JSON (instead of S3)",
    )
    parser.add_argument("--ground-truth", help="Path to ground truth JSON")
    parser.add_argument(
        "--skip-llm",
        action="store_true",
        help="Skip running LLM detector; load existing detection from S3 instead",
    )
    parser.add_argument(
        "--output-dir",
        default="evaluation/outputs",
        help="Directory to save detection outputs",
    )

    args = parser.parse_args()

    # Validate args
    if not args.extraction_file and not (args.state and args.year and args.run_id):
        parser.error(
            "Either --extraction-file or all of --state, --year, --run-id are required"
        )

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    label = args.state or "local"

    # Load extraction blocks
    blocks = load_extraction_blocks(
        country=args.country,
        state=args.state or "",
        year=args.year or 0,
        run_id=args.run_id or "",
        extraction_file=args.extraction_file or "",
    )

    # Run baseline detector (always — it's fast)
    baseline_output = run_detector("baseline", detect_structure_baseline, blocks)
    baseline_path = output_dir / f"{label}_baseline_detection.json"
    baseline_path.write_text(json.dumps(baseline_output, indent=2))
    logger.info(f"Saved baseline output to {baseline_path}")

    # Run or load LLM detector
    if args.skip_llm:
        llm_output = load_existing_llm_detection(
            args.country, args.state, args.year, args.run_id
        )
        llm_output["detector"] = "llm"
        llm_output["elapsed_seconds"] = None
        llm_output["total_elements"] = len(llm_output.get("elements", []))
    else:
        llm_output = run_detector("llm", detect_structure, blocks)

    llm_path = output_dir / f"{label}_llm_detection.json"
    llm_path.write_text(json.dumps(llm_output, indent=2))
    logger.info(f"Saved LLM output to {llm_path}")

    # Print quick summary
    print(f"\nBaseline: {baseline_output['total_elements']} elements "
          f"in {baseline_output['elapsed_seconds']}s")
    print(f"LLM:      {llm_output['total_elements']} elements"
          + (f" in {llm_output['elapsed_seconds']}s" if llm_output.get('elapsed_seconds') else " (loaded from S3)"))

    # Evaluate against ground truth if provided
    if args.ground_truth:
        gt_data = json.loads(Path(args.ground_truth).read_text())
        gt_elements = gt_data["elements"]

        llm_summary, llm_report = run_evaluation(
            gt_elements, llm_output["elements"], "llm"
        )
        baseline_summary, baseline_report = run_evaluation(
            gt_elements, baseline_output["elements"], "baseline"
        )

        print_comparison_table(llm_summary, baseline_summary)

        # Save detailed reports
        report = {
            "state": gt_data.get("state", label),
            "ground_truth_count": len(gt_elements),
            "llm": llm_summary,
            "baseline": baseline_summary,
            "llm_missed": [
                {"title": e.get("title"), "level": e.get("level"), "code": e.get("code")}
                for e in llm_report.missed_elements
            ],
            "baseline_missed": [
                {"title": e.get("title"), "level": e.get("level"), "code": e.get("code")}
                for e in baseline_report.missed_elements
            ],
            "llm_misclassified": llm_report.misclassified,
            "baseline_misclassified": baseline_report.misclassified,
        }
        report_path = output_dir / f"{label}_comparison_report.json"
        report_path.write_text(json.dumps(report, indent=2))
        logger.info(f"Saved comparison report to {report_path}")
    else:
        print("\nNo ground truth provided — skipping evaluation.")
        print("Run with --ground-truth to get P/R/F1 metrics.")


if __name__ == "__main__":
    main()
