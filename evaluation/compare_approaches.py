"""Compare LLM-based detection vs baseline regex detection.

Runs both approaches against the same ground truth and produces
a side-by-side comparison table for the paper.

Usage:
    python evaluation/compare_approaches.py \
        --ground-truth evaluation/ground_truth/TX.json \
        --llm-output path/to/llm_detection.json \
        --baseline-output path/to/baseline_detection.json
"""

import argparse
import json
from pathlib import Path

from evaluate import evaluate_detection


def compare(
    ground_truth_path: str,
    llm_output_path: str,
    baseline_output_path: str,
) -> dict:
    """Run evaluation for both approaches and produce comparison."""
    gt_data = json.loads(Path(ground_truth_path).read_text())
    llm_data = json.loads(Path(llm_output_path).read_text())
    baseline_data = json.loads(Path(baseline_output_path).read_text())

    gt_elements = gt_data["elements"]
    llm_elements = llm_data.get("elements", [])
    baseline_elements = baseline_data.get("elements", [])

    llm_report = evaluate_detection(gt_elements, llm_elements)
    llm_report.state = gt_data.get("state", "unknown")

    baseline_report = evaluate_detection(gt_elements, baseline_elements)
    baseline_report.state = gt_data.get("state", "unknown")

    comparison = {
        "state": gt_data.get("state"),
        "ground_truth_count": len(gt_elements),
        "llm": llm_report.summary(),
        "baseline": baseline_report.summary(),
        "improvement": {
            "element_f1_delta": round(
                llm_report.element_detection.f1 - baseline_report.element_detection.f1, 4
            ),
            "level_f1_delta": round(
                llm_report.level_classification.f1 - baseline_report.level_classification.f1, 4
            ),
            "code_f1_delta": round(
                llm_report.code_extraction.f1 - baseline_report.code_extraction.f1, 4
            ),
        },
    }

    # Print comparison table
    print(f"\n{'='*60}")
    print(f"  Comparison: {gt_data.get('state', 'unknown')}")
    print(f"  Ground truth elements: {len(gt_elements)}")
    print(f"{'='*60}\n")

    headers = ["Metric", "LLM", "Baseline", "Delta"]
    rows = [
        [
            "Element Detection P",
            f"{llm_report.element_detection.precision:.3f}",
            f"{baseline_report.element_detection.precision:.3f}",
            f"{llm_report.element_detection.precision - baseline_report.element_detection.precision:+.3f}",
        ],
        [
            "Element Detection R",
            f"{llm_report.element_detection.recall:.3f}",
            f"{baseline_report.element_detection.recall:.3f}",
            f"{llm_report.element_detection.recall - baseline_report.element_detection.recall:+.3f}",
        ],
        [
            "Element Detection F1",
            f"{llm_report.element_detection.f1:.3f}",
            f"{baseline_report.element_detection.f1:.3f}",
            f"{llm_report.element_detection.f1 - baseline_report.element_detection.f1:+.3f}",
        ],
        [
            "Level Classification F1",
            f"{llm_report.level_classification.f1:.3f}",
            f"{baseline_report.level_classification.f1:.3f}",
            f"{llm_report.level_classification.f1 - baseline_report.level_classification.f1:+.3f}",
        ],
        [
            "Code Extraction F1",
            f"{llm_report.code_extraction.f1:.3f}",
            f"{baseline_report.code_extraction.f1:.3f}",
            f"{llm_report.code_extraction.f1 - baseline_report.code_extraction.f1:+.3f}",
        ],
    ]

    col_widths = [max(len(row[i]) for row in [headers] + rows) for i in range(4)]
    fmt = "  ".join(f"{{:<{w}}}" for w in col_widths)

    print(fmt.format(*headers))
    print("-" * sum(col_widths + [6]))
    for row in rows:
        print(fmt.format(*row))

    print(f"\n{'='*60}\n")
    return comparison


def main():
    parser = argparse.ArgumentParser(description="Compare LLM vs baseline detection")
    parser.add_argument("--ground-truth", required=True)
    parser.add_argument("--llm-output", required=True)
    parser.add_argument("--baseline-output", required=True)
    parser.add_argument("--output", help="Path to write comparison JSON")

    args = parser.parse_args()
    result = compare(args.ground_truth, args.llm_output, args.baseline_output)

    if args.output:
        Path(args.output).write_text(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
