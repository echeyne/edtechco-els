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
   document content. I record n_detected_in_annotated_domains and the
   ceiling precision = n_golden / n_in_scope so no table can present the
   raw "precision" as a hallucination rate.
3. A level-agnostic confusion analysis: the suite's built-in confusion
   matrix includes `level` in the match key, so off-diagonal entries are
   structurally impossible. Here we re-pair missing goldens with unmatched
   in-scope detections on (title, age_band) alone and tabulate level pairs,
   which is what "level confusion" actually means.
4. A match-path audit: `grade_elements` tries a domain-scoped key first and
   silently falls back to a domain-agnostic one, so a state whose goldens
   all matched can still have matched them WITHOUT the domain scoping doing
   any work — and a same-titled pair under two domains (CA's FLD/ELD
   Vocabulary and Grammar) can pair cross-domain via that fallback. We
   replay the suite's own matcher (importing its key functions so the two
   cannot drift) and record, per state, how many goldens matched scoped vs.
   via fallback, and how many fallback matches crossed a domain boundary.
5. A parser field-accuracy decomposition: `field_accuracy` averages over
   every graded cell including the ones whose GOLDEN is null (a 3-level
   document contributes three null `sub_strand.*` cells per standard — 22%
   of CO's cells). Those cells are not free (a spuriously invented
   sub_strand is caught there, which is how the depth-map regression
   surfaced), but they are a different measurement from "did the parser get
   the annotated value right". We split each state's cells into
   non-null-correct / null-correct / wrong-value / spurious-value and report
   a non-trivial field accuracy over the cells whose golden asserts a value.

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
from evaluation.eval_detector import _match_key, _tag_domains  # noqa: E402
from evaluation.eval_parser import FIELD_PATHS, _get_path, _norm_val  # noqa: E402

STATES = ["AZ", "CA", "CO", "TX"]  # default: Task 1's golden four. Override with --state.

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


def match_path_audit(state: str, review_dir: Path) -> dict:
    """Replay `grade_elements`' two-tier lookup and record which tier matched.

    The suite prefers a domain-scoped key and falls back to a domain-agnostic
    one without recording which fired, so "recall 1.000" alone cannot tell you
    whether the domain scoping did any work or whether a golden paired with a
    same-titled element under a DIFFERENT domain. Both key functions are
    imported from the suite rather than reimplemented, so this audit cannot
    drift from what was actually graded."""
    golden = json.loads(
        (ROOT / "evaluation" / "ground_truth_detector" / f"{state}.json").read_text()
    )["elements"]
    detected = json.loads(
        (review_dir / state / f"{state}-detected.json").read_text()
    )
    for e in golden + detected:
        e["level"] = norm_level(e.get("level", ""))
    _tag_domains(golden)
    _tag_domains(detected)

    scoped: dict = defaultdict(list)
    agnostic: dict = defaultdict(list)
    for d in detected:
        scoped[_match_key(d)].append(d)
        agnostic[_match_key(d)[1:]].append(d)

    taken: set = set()

    def first_free(cands):
        for c in cands:
            if id(c) not in taken:
                return c
        return None

    out = {
        "matched_domain_scoped": 0,
        "matched_via_fallback": 0,
        "fallback_crossed_domain": [],
        "unmatched": [],
    }
    for g in golden:
        if not g.get("level") or not g.get("title"):
            continue
        d = first_free(scoped.get(_match_key(g), []))
        if d is not None:
            out["matched_domain_scoped"] += 1
            taken.add(id(d))
            continue
        d = first_free(agnostic.get(_match_key(g)[1:], []))
        if d is None:
            out["unmatched"].append(g.get("test_case_id"))
            continue
        out["matched_via_fallback"] += 1
        taken.add(id(d))
        if g.get("_domain") != d.get("_domain"):
            out["fallback_crossed_domain"].append({
                "test_case_id": g.get("test_case_id"),
                "level": g.get("level"),
                "title": g.get("title"),
                "golden_domain": g.get("_domain"),
                "detected_domain": d.get("_domain"),
            })
    for e in golden + detected:
        e.pop("_domain", None)
    return out


def parser_field_decomposition(state: str, review_dir: Path) -> dict:
    """Split the parser's graded cells by what the golden asserts.

    `field_accuracy` is one number over every cell of every matched standard,
    and a sizeable share of those cells are ones whose GOLDEN is null — three
    `sub_strand.*` cells per standard on a 3-level document. Those cells still
    carry signal (a spuriously invented sub_strand fails there, which is how
    the depth-map regression showed itself), so they are not removed from the
    headline; they are reported separately so a reader can see how much of the
    headline is 'correctly emitted nothing'."""
    review = json.loads((review_dir / state / f"{state}-review.json").read_text())
    buckets = Counter()
    for m in review["matched"]:
        exp, got = m["golden"].get("expected") or {}, m["parsed"]
        for path in FIELD_PATHS:
            e, g = _norm_val(_get_path(exp, path)), _norm_val(_get_path(got, path))
            if e is None and g is None:
                buckets["null_correct"] += 1
            elif e is None:
                buckets["spurious_value"] += 1
            elif e == g:
                buckets["value_correct"] += 1
            else:
                buckets["value_wrong"] += 1
    asserted = buckets["value_correct"] + buckets["value_wrong"]
    total = sum(buckets.values())
    return {
        **buckets,
        "total_cells": total,
        "share_of_cells_whose_golden_is_null": (
            round((buckets["null_correct"] + buckets["spurious_value"]) / total, 4)
            if total else None
        ),
        "field_accuracy_over_asserted_cells_only": (
            round(buckets["value_correct"] / asserted, 4) if asserted else None
        ),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--detector-report", type=Path,
                    default=RESULTS / "task1_detector_golden4.json")
    ap.add_argument("--parser-report", type=Path,
                    default=RESULTS / "task1_parser_golden4.json")
    ap.add_argument("--detector-review-dir", type=Path,
                    default=RESULTS / "task1_review_detector")
    ap.add_argument("--parser-review-dir", type=Path,
                    default=RESULTS / "task1_review_parser")
    ap.add_argument("--out", type=Path, default=RESULTS / "task1_summary.json")
    ap.add_argument("--state", action="append", metavar="ST",
                    help="Limit to specific state(s); repeatable. Defaults to "
                         f"{STATES}. Task 2 consolidates its held-out states "
                         "(NV, KY) through this same entry point on purpose: "
                         "the generalization table must be computed by the "
                         "identical code path as the golden-state table.")
    args = ap.parse_args()
    states = args.state or STATES

    det = {r["state"]: r for r in json.loads(args.detector_report.read_text())}
    par = {r["state"]: r for r in json.loads(args.parser_report.read_text())}
    review_dir = args.detector_review_dir
    parser_review_dir = args.parser_review_dir

    summary = {"detector": {}, "parser": {}}
    for st in states:
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
            "match_path": match_path_audit(st, review_dir),
            "code_accuracy": r.get("code_accuracy"),
            "code_matches": r.get("code_matches"),
            "code_total": r.get("code_total"),
            "code_mismatches": r.get("code_mismatches", []),
            "description_accuracy": r.get("description_accuracy"),
            "description_matches": r.get("description_matches"),
            "description_total": r.get("description_total"),
            "description_truncations": r.get("description_truncations"),
            "description_mismatches": r.get("description_mismatches", []),
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
            "field_decomposition": parser_field_decomposition(st, parser_review_dir),
            "regressions": p["regressions"],
        }

    args.out.write_text(json.dumps(summary, indent=2))
    print(f"Wrote {args.out}")


if __name__ == "__main__":
    main()
