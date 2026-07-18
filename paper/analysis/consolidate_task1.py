"""Consolidate Task 1 headline eval results into paper/results/task1_summary.json.

Reads the raw suite reports produced by:
  AWS_PROFILE=kinder-readiness-dev-cli python -m evaluation.eval_detector \
      --extraction-dir outputs/07-17-26 --no-cache \
      --report-json paper/results/task1_detector_golden4.json \
      --output-dir paper/results/task1_review_detector
  AWS_PROFILE=kinder-readiness-dev-cli python -m evaluation.eval_parser \
      --detection-dir outputs/07-17-26 --no-cache \
      --report-json paper/results/task1_parser_golden4.json \
      --output-dir paper/results/task1_review_parser

and adds paper-facing context the raw reports omit:

1. Normalizes level names (a fresh detector run serializes enum members as
   "HierarchyLevelEnum.STRAND"; a cached run yields plain "strand").
2. Annotation-coverage context for precision: the detector goldens are
   partial spot-checks (5-25 elements), so every unmatched detection inside
   an annotated domain counts as a false positive even when it is correct
   document content. We record n_detected_in_annotated_domains and the
   ceiling precision = n_golden / n_in_scope so no table can present the
   raw "precision" as a hallucination rate.
3. A level-agnostic confusion analysis: the suite's built-in confusion
   matrix includes `level` in the match key, so off-diagonal entries are
   structurally impossible. Here we re-pair missing goldens with unmatched
   in-scope detections on (title, age_band) alone and tabulate level pairs,
   which is what "level confusion" actually means.

Usage (from repo root):
    python paper/analysis/consolidate_task1.py

Report/review paths are overridable so a re-run can be consolidated without
clobbering the previous session's files:
    python paper/analysis/consolidate_task1.py \
        --detector-report paper/results/task1_detector_golden4_v2.json \
        --parser-report   paper/results/task1_parser_golden4_v2.json \
        --detector-review-dir paper/results/task1_review_detector_v2 \
        --out paper/results/task1_summary_v2.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
RESULTS = ROOT / "paper" / "results"
sys.path.insert(0, str(ROOT))

from evaluation.eval_common import _norm, _norm_age_band  # noqa: E402

STATES = ["AZ", "CA", "CO", "TX"]

_ENUM_RE = re.compile(r"^HierarchyLevelEnum\.([A-Z_]+)$")


def norm_level(v: str) -> str:
    m = _ENUM_RE.match(str(v))
    return m.group(1).lower() if m else str(v)


def in_scope_counts(state: str, review_dir: Path) -> dict:
    """Replicate the suite's own domain scoping over the graded detection
    output to expose how much in-annotated-domain content the golden does
    not annotate."""
    golden = json.loads(
        (ROOT / "evaluation" / "ground_truth_detector" / f"{state}.json").read_text()
    )["elements"]
    detected = json.loads(
        (review_dir / state / f"{state}-detected.json").read_text()
    )
    ann = {_norm(e["title"]) for e in golden if norm_level(e.get("level", "")) == "domain"}
    cur, n_in = None, 0
    for e in detected:
        if norm_level(e.get("level", "")) == "domain":
            cur = _norm(e.get("title", ""))
        if cur in ann:
            n_in += 1
    return {
        "n_golden": len(golden),
        "n_detected_total": len(detected),
        "n_detected_in_annotated_domains": n_in,
        "precision_ceiling_from_annotation_coverage": round(len(golden) / n_in, 4) if n_in else None,
    }


def level_agnostic_confusion(state: str, review_dir: Path) -> dict:
    """Pair unmatched goldens with unmatched in-scope detections on
    (title, age_band), ignoring level, and report level pairs."""
    review = json.loads(
        (review_dir / state / f"{state}-review.json").read_text()
    )
    pairs: Counter = Counter()
    for m in review["matched"]:
        g, d = m["golden"], m["detected"]
        pairs[(norm_level(g["level"]), norm_level(d["level"]))] += 1

    extras = {
        (_norm(d.get("title", "")), _norm_age_band(d.get("age_band"))): d
        for d in review["extra_in_detected"]
    }
    unresolved_missing = []
    for g in review["missing_from_detected"]:
        key = (_norm(g.get("title", "")), _norm_age_band(g.get("age_band")))
        d = extras.pop(key, None)
        if d is not None:
            pairs[(norm_level(g["level"]), norm_level(d["level"]))] += 1
        else:
            unresolved_missing.append(g.get("test_case_id"))
    out = defaultdict(dict)
    for (gl, dl), n in sorted(pairs.items()):
        out[gl][dl] = n
    off_diag = sum(n for (gl, dl), n in pairs.items() if gl != dl)
    return {
        "golden_to_detected": dict(out),
        "off_diagonal_total": off_diag,
        "missing_with_no_title_match_at_any_level": unresolved_missing,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--detector-report", type=Path,
                    default=RESULTS / "task1_detector_golden4.json")
    ap.add_argument("--parser-report", type=Path,
                    default=RESULTS / "task1_parser_golden4.json")
    ap.add_argument("--detector-review-dir", type=Path,
                    default=RESULTS / "task1_review_detector")
    ap.add_argument("--out", type=Path, default=RESULTS / "task1_summary.json")
    args = ap.parse_args()

    det = {r["state"]: r for r in json.loads(args.detector_report.read_text())}
    par = {r["state"]: r for r in json.loads(args.parser_report.read_text())}
    review_dir = args.detector_review_dir

    summary = {"detector": {}, "parser": {}}
    for st in STATES:
        r = det[st]
        summary["detector"][st] = {
            "precision_raw": round(r["precision"], 4),
            "recall": round(r["recall"], 4),
            "f1_raw": round(r["f1"], 4),
            "matched": r["matched"],
            "annotation_coverage": in_scope_counts(st, review_dir),
            "per_level": {
                norm_level(k): v for k, v in r["per_level"].items()
            },
            "level_confusion_level_agnostic": level_agnostic_confusion(st, review_dir),
            "age_band_drops": r["age_band_drops"],
            "missing_test_cases": r["missing_test_cases"],
            "depth_map_passed": r["depth_map_passed"],
            "depth_map_detail": r["depth_map_detail"],
            "regressions": r["regressions"],
        }
        p = par[st]
        summary["parser"][st] = {
            "coverage": round(p["coverage"], 4),
            "field_accuracy": round(p["field_accuracy"], 4),
            "matched": p["matched"],
            "n_golden": p["n_golden"],
            "n_parsed": p["n_parsed"],
            "fully_correct": p["fully_correct"],
            "dropped": p["dropped"],
            "duplicated": p["duplicated"],
            "id_collisions": p["id_collisions"],
            "per_field_accuracy": {
                k: round(v["ok"] / v["total"], 4)
                for k, v in p["field_stats"].items()
                if v["total"]
            },
            "n_field_mismatches": len(p["mismatches"]),
            "regressions": p["regressions"],
        }

    args.out.write_text(json.dumps(summary, indent=2))
    print(f"Wrote {args.out}")


if __name__ == "__main__":
    main()
