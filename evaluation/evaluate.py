"""Evaluation script for ELS pipeline accuracy.

Compares pipeline output against human-annotated ground truth to compute
precision, recall, and F1 for element detection and hierarchy assignment.

Usage:
    python evaluation/evaluate.py --ground-truth evaluation/ground_truth/TX.json \
                                   --pipeline-output path/to/detection_output.json \
                                   --parsing-output path/to/parsing_output.json
"""

import argparse
import json
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple


@dataclass
class EvalMetrics:
    """Precision / recall / F1 for a single evaluation dimension."""
    true_positives: int = 0
    false_positives: int = 0
    false_negatives: int = 0

    @property
    def precision(self) -> float:
        denom = self.true_positives + self.false_positives
        return self.true_positives / denom if denom else 0.0

    @property
    def recall(self) -> float:
        denom = self.true_positives + self.false_negatives
        return self.true_positives / denom if denom else 0.0

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        return 2 * p * r / (p + r) if (p + r) else 0.0


@dataclass
class EvalReport:
    """Full evaluation report across all dimensions."""
    state: str
    # Element-level: did the pipeline find the right elements?
    element_detection: EvalMetrics = field(default_factory=EvalMetrics)
    # Level classification: did it assign the correct hierarchy level?
    level_classification: EvalMetrics = field(default_factory=EvalMetrics)
    # Per-level breakdown
    per_level: Dict[str, EvalMetrics] = field(default_factory=lambda: defaultdict(EvalMetrics))
    # Hierarchy accuracy: did it assign correct parent-child?
    hierarchy_assignment: EvalMetrics = field(default_factory=EvalMetrics)
    # Code extraction accuracy
    code_extraction: EvalMetrics = field(default_factory=EvalMetrics)
    # Details for error analysis
    missed_elements: List[dict] = field(default_factory=list)
    extra_elements: List[dict] = field(default_factory=list)
    misclassified: List[dict] = field(default_factory=list)

    def summary(self) -> dict:
        result = {
            "state": self.state,
            "element_detection": {
                "precision": round(self.element_detection.precision, 4),
                "recall": round(self.element_detection.recall, 4),
                "f1": round(self.element_detection.f1, 4),
                "tp": self.element_detection.true_positives,
                "fp": self.element_detection.false_positives,
                "fn": self.element_detection.false_negatives,
            },
            "level_classification": {
                "precision": round(self.level_classification.precision, 4),
                "recall": round(self.level_classification.recall, 4),
                "f1": round(self.level_classification.f1, 4),
            },
        }
        for level_name, metrics in sorted(self.per_level.items()):
            result[f"level_{level_name}"] = {
                "precision": round(metrics.precision, 4),
                "recall": round(metrics.recall, 4),
                "f1": round(metrics.f1, 4),
            }
        result["hierarchy_assignment"] = {
            "precision": round(self.hierarchy_assignment.precision, 4),
            "recall": round(self.hierarchy_assignment.recall, 4),
            "f1": round(self.hierarchy_assignment.f1, 4),
        }
        result["code_extraction"] = {
            "precision": round(self.code_extraction.precision, 4),
            "recall": round(self.code_extraction.recall, 4),
            "f1": round(self.code_extraction.f1, 4),
        }
        result["error_analysis"] = {
            "missed_count": len(self.missed_elements),
            "extra_count": len(self.extra_elements),
            "misclassified_count": len(self.misclassified),
        }
        return result


def _normalize_title(title: str) -> str:
    """Normalize a title for fuzzy matching."""
    return " ".join(title.lower().split())


def _element_key(elem: dict) -> str:
    """
    Create a matching key for an element.
    Uses normalized title + source_page as the primary match key,
    since codes can vary between ground truth and pipeline output.
    """
    title = _normalize_title(elem.get("title", ""))
    page = elem.get("source_page", 0)
    return f"{title}|{page}"


def _element_key_by_code(elem: dict) -> str:
    """Alternative key using code + level for code-based matching."""
    code = elem.get("code", "").strip()
    level = elem.get("level", "").strip()
    return f"{level}|{code}"


def evaluate_detection(
    ground_truth: List[dict],
    pipeline_output: List[dict],
) -> EvalReport:
    """
    Evaluate pipeline detection output against ground truth.

    Matching strategy:
    1. Try exact match on (normalized_title, source_page)
    2. Fall back to (level, code) matching
    3. Unmatched ground truth elements = false negatives
    4. Unmatched pipeline elements = false positives

    Args:
        ground_truth: List of annotated elements from ground truth file
        pipeline_output: List of detected elements from pipeline

    Returns:
        EvalReport with all metrics computed
    """
    report = EvalReport(state="")

    # Build lookup maps
    gt_by_title = {}
    gt_by_code = {}
    for elem in ground_truth:
        gt_by_title[_element_key(elem)] = elem
        gt_by_code[_element_key_by_code(elem)] = elem

    matched_gt_keys: Set[str] = set()

    for pred in pipeline_output:
        pred_title_key = _element_key(pred)
        pred_code_key = _element_key_by_code(pred)

        # Try title-based match first, then code-based
        gt_elem = gt_by_title.get(pred_title_key) or gt_by_code.get(pred_code_key)

        if gt_elem:
            match_key = pred_title_key if pred_title_key in gt_by_title else pred_code_key
            matched_gt_keys.add(match_key)

            # Element detection: true positive
            report.element_detection.true_positives += 1

            # Level classification
            if pred.get("level") == gt_elem.get("level"):
                report.level_classification.true_positives += 1
                level = pred.get("level", "unknown")
                report.per_level[level].true_positives += 1
            else:
                report.level_classification.false_positives += 1
                report.misclassified.append({
                    "title": pred.get("title"),
                    "predicted_level": pred.get("level"),
                    "expected_level": gt_elem.get("level"),
                })

            # Code extraction
            if pred.get("code", "").strip() == gt_elem.get("code", "").strip():
                report.code_extraction.true_positives += 1
            else:
                report.code_extraction.false_positives += 1
        else:
            # False positive: pipeline found something not in ground truth
            report.element_detection.false_positives += 1
            report.extra_elements.append(pred)

    # False negatives: ground truth elements not matched
    all_gt_keys = set(gt_by_title.keys()) | set(gt_by_code.keys())
    for key in all_gt_keys:
        if key not in matched_gt_keys:
            gt_elem = gt_by_title.get(key) or gt_by_code.get(key)
            if gt_elem:
                report.element_detection.false_negatives += 1
                report.missed_elements.append(gt_elem)
                level = gt_elem.get("level", "unknown")
                report.per_level[level].false_negatives += 1

    # Code extraction false negatives = missed elements
    report.code_extraction.false_negatives = report.element_detection.false_negatives
    report.level_classification.false_negatives = report.element_detection.false_negatives

    return report


def evaluate_hierarchy(
    ground_truth: List[dict],
    parsing_output: List[dict],
) -> EvalMetrics:
    """
    Evaluate hierarchy assignment accuracy from parsing output.

    For each indicator in the parsing output, check if the assigned
    domain_code, strand_code, and sub_strand_code match ground truth.

    Args:
        ground_truth: Annotated elements with parent_code fields
        parsing_output: Parsed indicators with hierarchy fields

    Returns:
        EvalMetrics for hierarchy assignment
    """
    metrics = EvalMetrics()

    # Build ground truth lookup: indicator_code -> parent chain
    gt_hierarchy = {}
    for elem in ground_truth:
        if elem.get("level") == "indicator":
            code = elem.get("code", "").strip()
            gt_hierarchy[code] = {
                "domain_code": elem.get("domain_code", ""),
                "strand_code": elem.get("strand_code"),
                "sub_strand_code": elem.get("sub_strand_code"),
            }

    for pred in parsing_output:
        pred_code = pred.get("indicator_code", "").strip()
        gt = gt_hierarchy.get(pred_code)

        if gt is None:
            metrics.false_positives += 1
            continue

        # Check if the full parent chain matches
        domain_match = pred.get("domain_code", "").strip() == gt["domain_code"]
        strand_match = (pred.get("strand_code") or "") == (gt["strand_code"] or "")
        sub_match = (pred.get("sub_strand_code") or "") == (gt["sub_strand_code"] or "")

        if domain_match and strand_match and sub_match:
            metrics.true_positives += 1
        else:
            metrics.false_positives += 1

    # Indicators in ground truth not found in output
    pred_codes = {p.get("indicator_code", "").strip() for p in parsing_output}
    for code in gt_hierarchy:
        if code not in pred_codes:
            metrics.false_negatives += 1

    return metrics


def run_evaluation(
    ground_truth_path: str,
    detection_output_path: str,
    parsing_output_path: Optional[str] = None,
) -> dict:
    """
    Run full evaluation and return summary report.

    Args:
        ground_truth_path: Path to ground truth JSON file
        detection_output_path: Path to pipeline detection output JSON
        parsing_output_path: Optional path to parsing output JSON

    Returns:
        Summary dict with all metrics
    """
    gt_data = json.loads(Path(ground_truth_path).read_text())
    det_data = json.loads(Path(detection_output_path).read_text())

    gt_elements = gt_data["elements"]
    det_elements = det_data.get("elements", det_data if isinstance(det_data, list) else [])

    report = evaluate_detection(gt_elements, det_elements)
    report.state = gt_data.get("state", "unknown")

    if parsing_output_path:
        parse_data = json.loads(Path(parsing_output_path).read_text())
        parse_indicators = parse_data.get("indicators", parse_data if isinstance(parse_data, list) else [])
        report.hierarchy_assignment = evaluate_hierarchy(gt_elements, parse_indicators)

    summary = report.summary()

    # Print results
    print(json.dumps(summary, indent=2))
    return summary


def main():
    parser = argparse.ArgumentParser(description="Evaluate ELS pipeline against ground truth")
    parser.add_argument("--ground-truth", required=True, help="Path to ground truth JSON")
    parser.add_argument("--pipeline-output", required=True, help="Path to detection output JSON")
    parser.add_argument("--parsing-output", help="Path to parsing output JSON (optional)")
    parser.add_argument("--output", help="Path to write evaluation report JSON")

    args = parser.parse_args()
    summary = run_evaluation(args.ground_truth, args.pipeline_output, args.parsing_output)

    if args.output:
        Path(args.output).write_text(json.dumps(summary, indent=2))
        print(f"\nReport written to {args.output}")


if __name__ == "__main__":
    main()
