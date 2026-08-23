#!/usr/bin/env python3
"""Compare the rule-based baseline against the LLM detector (arXiv paper Task 4).

The LLM arm is NOT re-run: it is the frozen Task 1 + Task 2 detector reports.
The baseline arm comes from `evaluation.baselines.eval_baseline`, which grades
through `eval_detector`'s own `evaluate_state` / `grade_elements`, so both arms
are products of the same matcher against the same goldens.

Refuses to emit a comparison for any state whose baseline arm has
n_detected == 0 (nothing ran) or a non-null depth_map_passed (the baseline has
no Pass-1 and must record the third state). Both are marked `INVALID` and
excluded from every aggregate, the posture compare_ablation.py takes toward the
throttle signature.

## ⚠️ Why this script does not compare "verified precision"

The Task 4 handoff warned against comparing the LLM's *verified* precision to
the baseline's *raw* precision. The real hazard is sharper and points the other
way. `heldout_evidence.fp_audit` decides its verdicts by asking whether a
detected title appears in the extraction -- a test built for a generator whose
failure mode is INVENTION. A rule-based extractor copies block text verbatim and
therefore cannot invent, so essentially every one of its extras classifies as
`real_unannotated` and its verified precision comes out at or near 1.000. A
table reading "baseline 1.000, LLM 0.9966" would be arithmetically correct and
substantively backwards.

So this script reports, and the paper should report:

  * **raw precision for BOTH arms**, side by side, each carrying guardrail 8's
    caveat that on a spot-check golden it measures annotation coverage. Same
    definition, same denominators, so the comparison is at least valid.
  * **`level_accuracy_given_title_found`** -- of the golden elements whose title
    the arm produced ANYWHERE, what fraction did it place at the right level.
    This is the dimension that actually separates the two systems, because it
    holds "found the text" fixed and asks only about classification. It is
    derived from the same graded artifacts, not from a second grader.
  * the baseline's own FP audit is still run (`--baseline-review-dir`), because
    the claim above should be measured rather than asserted.

## The brittleness probe

`--probe-brittleness` re-runs the baseline with two of its patterns widened --
multi-letter numbering segments, and label words recognized mid-line -- and
reports the recall delta. Both widenings are motivated ONLY by held-out
documents, so they are NOT adopted; the probe exists to quantify how much of the
held-out collapse is a single unseen token shape, and to answer the reviewer who
suspects the baseline's regexes were merely under-specified.

Usage:
    python paper/analysis/compare_baseline.py \
        --llm-report paper/results/task1_20260822/detector_golden4.json \
        --llm-report paper/results/task2_20260822/detector_heldout2.json \
        --baseline-report paper/results/task4_20260823/detector_baseline.json \
        --baseline-review-dir paper/results/task4_20260823/review_baseline \
        --outputs-dir outputs/08-22-26-4 \
        --probe-brittleness \
        --out paper/results/task4_20260823/baseline_comparison.json
"""
from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "src"))

from evaluation.eval_common import _norm, _norm_age_band  # noqa: E402
from paper.analysis.heldout_evidence import fp_audit  # noqa: E402

LEVELS = ("domain", "strand", "sub_strand", "indicator")
ALL_STATES = ("AZ", "CA", "CO", "TX", "NV", "KY")


def load_reports(paths):
    out = {}
    for p in paths:
        for rep in json.loads(Path(p).read_text()):
            out[rep["state"]] = rep
    return out


def level_rates(rep):
    d = {}
    for lv in LEVELS:
        pl = rep.get("per_level", {}).get(lv)
        if not pl:
            continue
        tp, fp, fn = pl["tp"], pl["fp"], pl["fn"]
        d[lv] = {
            "tp": tp, "fp": fp, "fn": fn,
            "recall": round(tp / (tp + fn), 4) if (tp + fn) else None,
            "precision": round(tp / (tp + fp), 4) if (tp + fp) else None,
        }
    return d


def regr(rep):
    rs = rep.get("regressions", [])
    return {
        "passed": sum(1 for r in rs if r["status"] == "PASS"),
        "total": len(rs),
        "failed_ids": [r["id"] for r in rs if r["status"] != "PASS"],
    }


def validate(state, rep):
    """Reasons this state's baseline arm cannot be compared."""
    problems = []
    if rep is None:
        problems.append("no baseline report row")
        return problems
    if rep.get("n_detected", 0) == 0:
        problems.append("n_detected == 0 — the arm produced nothing")
    if rep.get("depth_map_passed") is not None:
        problems.append(
            "depth_map_passed is not null — the baseline has no Pass-1 and must "
            "record the third (ABLATED) state; a pass/fail here means the wrong "
            "detector was graded"
        )
    return problems


# --------------------------------------------------------------------------
# The dimension that actually discriminates
# --------------------------------------------------------------------------

def level_accuracy_given_title_found(golden_path: Path, detected: list) -> dict:
    """Split "did it find the text?" from "did it classify the text?".

    `_match_key` carries the level, so an element found at the wrong level
    scores as a miss and is indistinguishable in the headline from an element
    not found at all. Those are very different failures, and they are exactly
    where a rule-based extractor and an LLM diverge: rules copy text reliably
    and classify it badly.

    `title_recall` is level-agnostic and age-band-agnostic: did ANY detected
    element carry this golden title? `level_accuracy` then asks, of those, how
    many had at least one detection at the right level.
    """
    golden = json.loads(golden_path.read_text()).get("elements", [])
    by_title = {}
    for d in detected:
        by_title.setdefault(_norm(d.get("title", "")), set()).add(
            (d.get("level") or "").strip()
        )

    n_golden = found = correct_level = 0
    misclassified = []
    for g in golden:
        if not g.get("level") or not g.get("title"):
            continue
        n_golden += 1
        levels = by_title.get(_norm(g["title"]))
        if not levels:
            continue
        found += 1
        if g["level"] in levels:
            correct_level += 1
        else:
            misclassified.append({
                "test_case_id": g.get("test_case_id"),
                "title": g["title"][:80],
                "golden_level": g["level"],
                "detected_levels": sorted(levels),
            })
    return {
        "n_golden": n_golden,
        "titles_found": found,
        "title_recall": round(found / n_golden, 4) if n_golden else None,
        "correct_level_among_found": correct_level,
        "level_accuracy_given_title_found":
            round(correct_level / found, 4) if found else None,
        "misclassified": misclassified,
    }


def failure_decomposition(rep: dict, lvl: dict) -> dict:
    """Split every golden miss into the three reasons it can happen.

    ``level_accuracy_given_title_found`` is deliberately age-band-agnostic
    while ``_match_key`` is not, so the two disagree by exactly the elements
    found at the right level under the wrong (or no) age band. Naming that
    third bucket is what makes the decomposition add up — without it CA reads
    as "level accuracy 1.000" beside "recall 0.640", which looks contradictory.
    """
    if not lvl:
        return {}
    n = lvl["n_golden"]
    found = lvl["titles_found"]
    right_level = lvl["correct_level_among_found"]
    matched = rep["matched"]
    return {
        "n_golden": n,
        "title_not_found": n - found,
        "found_but_wrong_level": found - right_level,
        "right_level_but_age_band_differs": right_level - matched,
        "fully_matched": matched,
        "note": (
            "title_not_found + found_but_wrong_level + "
            "right_level_but_age_band_differs + fully_matched == n_golden"
        ),
    }


# --------------------------------------------------------------------------
# Brittleness probe (measured, NOT adopted)
# --------------------------------------------------------------------------

WIDENED_NUMBER_PATH = re.compile(
    r"^\s*("
    r"(?:[A-Z]{1,4}\d{1,2}\.)?"
    r"(?:\d{1,3}|[A-Z]{1,5})"                     # widened: multi-letter segment
    r"(?:\.(?:\d{1,3}|[A-Za-z]{1,5}\d{0,2}))*"    # widened: multi-letter + PK1
    r")"
    r"([.):]?)\s+(?=\S)"
)


def probe_brittleness(extraction_dir: Path, golden_dir: Path, states) -> dict:
    """Re-measure recall with two patterns widened. NOT a result to adopt.

    Both widenings are motivated only by held-out documents -- Nevada codes its
    leaves `SS.ID.PK1` (multi-letter segments, a shape no development state
    printed) and Kentucky prints its strand label mid-line
    ("Approaches to Learning Standard 1:") rather than at line start. Adopting
    either after seeing them would be tuning on the held-out set, which is the
    one thing the held-out set exists to prevent.

    Measuring them is not tuning. The delta is the quantity a reviewer wants:
    how much of the collapse is a genuinely hard document versus a regex that
    had never seen a token shape.
    """
    import evaluation.baselines.rule_based as rb
    from evaluation.baselines.eval_baseline import run_baseline
    from evaluation.eval_detector import evaluate_state, report_to_dict

    original_number = rb.NUMBER_PATH_RE
    original_label = rb.LABEL_HEADING_RE
    # Same alternation, allowed to appear anywhere in the line rather than only
    # at its start. ⚠️ `_heading_signal` calls `.match()`, which anchors at
    # position 0 whatever the pattern says, so the widened pattern has to
    # CONSUME the prefix itself — replacing the anchor with an alternation is
    # silently inert and reports "no effect" for a rule that never ran.
    widened_label = re.compile(
        original_label.pattern.replace(r"^\s*", r"^.*?(?:^|(?<=[\s(]))", 1),
        original_label.flags,
    )

    out = {}
    for arm, number_re, label_re in (
        ("as_recorded", original_number, original_label),
        ("widened_numbering", WIDENED_NUMBER_PATH, original_label),
        ("widened_numbering_and_midline_labels", WIDENED_NUMBER_PATH, widened_label),
    ):
        rb.NUMBER_PATH_RE = number_re
        rb.LABEL_HEADING_RE = label_re
        for st in states:
            ext = extraction_dir / f"{st}-extraction.json"
            gold = golden_dir / f"{st}.json"
            if not ext.exists() or not gold.exists():
                continue
            rep, _ = evaluate_state(
                st, ext, gold, use_cache=False, stability_runs=1,
                detect_fn=run_baseline, grade_depth_map_pass=False,
            )
            r = report_to_dict(rep)
            out.setdefault(st, {})[arm] = {
                "recall": r["recall"], "matched": r["matched"],
                "n_detected": r["n_detected"], "n_golden": r["n_golden"],
            }
    rb.NUMBER_PATH_RE = original_number
    rb.LABEL_HEADING_RE = original_label

    return {
        "status": "MEASURED BUT NOT ADOPTED",
        "why_not_adopted": (
            "Both widenings were motivated by inspecting the held-out states "
            "AFTER the recorded run. Adopting them would make NV and KY "
            "development data and void the generalization claim they support."
        ),
        "per_state": out,
    }


# --------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--llm-report", action="append", required=True,
                    help="frozen eval_detector report(s) for the LLM arm; repeatable")
    ap.add_argument("--baseline-report", action="append", required=True,
                    help="eval_baseline report(s); repeatable")
    ap.add_argument("--baseline-review-dir",
                    help="review dir from eval_baseline --output-dir, for the FP audit")
    ap.add_argument("--llm-review-dir", action="append", default=[],
                    help="review dir(s) from the frozen LLM run, for its raw FP counts")
    ap.add_argument("--outputs-dir", default="outputs/08-22-26-4")
    ap.add_argument("--golden-dir", default="evaluation/ground_truth_detector")
    ap.add_argument("--probe-brittleness", action="store_true")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    logging.disable(logging.CRITICAL)

    llm = load_reports(args.llm_report)
    base = load_reports(args.baseline_report)
    golden_dir = Path(args.golden_dir)
    outputs_dir = Path(args.outputs_dir)

    per_state, invalid = {}, []
    for st in ALL_STATES:
        b, l = base.get(st), llm.get(st)
        if l is None:
            continue
        problems = validate(st, b)
        if problems:
            invalid.append(st)
            per_state[st] = {"status": "INVALID", "problems": problems}
            continue

        detected_path = Path(args.baseline_review_dir or "") / st / f"{st}-detected.json"
        lvl_acc = (
            level_accuracy_given_title_found(
                golden_dir / f"{st}.json", json.loads(detected_path.read_text())
            ) if detected_path.exists() else None
        )
        llm_detected = None
        for d in args.llm_review_dir:
            p = Path(d) / st / f"{st}-detected.json"
            if p.exists():
                llm_detected = json.loads(p.read_text())
                break
        llm_lvl_acc = (
            level_accuracy_given_title_found(golden_dir / f"{st}.json", llm_detected)
            if llm_detected else None
        )

        per_state[st] = {
            "status": "OK",
            "n_golden": l["n_golden"],
            "llm": {
                "recall": l["recall"],
                "raw_precision": l["precision"],
                "n_detected": l["n_detected"],
                "in_scope_detections": l["n_detected"] - l["ignored_out_of_scope"],
                "matched": l["matched"],
                "code_accuracy": l["code_accuracy"],
                "code_matches": l["code_matches"], "code_total": l["code_total"],
                "description_accuracy": l["description_accuracy"],
                "description_matches": l["description_matches"],
                "description_total": l["description_total"],
                "depth_map_passed": l["depth_map_passed"],
                "per_level": level_rates(l),
                "regressions": regr(l),
                "level_accuracy": llm_lvl_acc,
            },
            "baseline": {
                "recall": b["recall"],
                "raw_precision": b["precision"],
                "n_detected": b["n_detected"],
                "in_scope_detections": b["n_detected"] - b["ignored_out_of_scope"],
                "matched": b["matched"],
                "code_accuracy": b["code_accuracy"],
                "code_matches": b["code_matches"], "code_total": b["code_total"],
                "description_accuracy": b["description_accuracy"],
                "description_matches": b["description_matches"],
                "description_total": b["description_total"],
                "depth_map_passed": b["depth_map_passed"],
                "per_level": level_rates(b),
                "regressions": regr(b),
                "level_accuracy": lvl_acc,
                "failure_decomposition": failure_decomposition(b, lvl_acc),
            },
            "recall_delta": round(l["recall"] - b["recall"], 4),
        }

    ok = [s for s, v in per_state.items() if v["status"] == "OK"]
    pooled = {}
    for lv in LEVELS:
        acc = {"llm_tp": 0, "llm_fn": 0, "base_tp": 0, "base_fn": 0}
        for s in ok:
            for arm, pre in (("llm", "llm"), ("baseline", "base")):
                d = per_state[s][arm]["per_level"].get(lv)
                if d:
                    acc[f"{pre}_tp"] += d["tp"]
                    acc[f"{pre}_fn"] += d["fn"]
        lt, ln_ = acc["llm_tp"] + acc["llm_fn"], acc["base_tp"] + acc["base_fn"]
        if lt or ln_:
            pooled[lv] = {
                "llm_recall": round(acc["llm_tp"] / lt, 4) if lt else None,
                "baseline_recall": round(acc["base_tp"] / ln_, 4) if ln_ else None,
                "llm_tp": acc["llm_tp"], "llm_fn": acc["llm_fn"],
                "baseline_tp": acc["base_tp"], "baseline_fn": acc["base_fn"],
            }

    result = {
        "task": "Task 4 — rule-based baseline vs LLM detector",
        "corpus_tier": (
            "_only_subset (manually trimmed subset PDFs, NOT full documents). "
            "AZ 15pp, CA 13pp, CO 10pp, TX 9pp, NV 15pp of 98, KY 8pp of 120."
        ),
        "grading": (
            "Both arms graded by evaluation/eval_detector.grade_elements against "
            "evaluation/ground_truth_detector/{STATE}.json. The baseline arm runs "
            "through eval_detector.evaluate_state with detect_fn injected; no "
            "second grader exists."
        ),
        "precision_caveat": (
            "RAW precision is reported for BOTH arms and is NOT detector quality "
            "(guardrail 8) except for KY, whose golden is detection-exhaustive. "
            "Verified precision is deliberately NOT compared: fp_audit's verdicts "
            "turn on whether a title appears in the extraction, and a rule-based "
            "extractor copies text verbatim and so cannot hallucinate by "
            "construction. Its verified precision is therefore ~1.000 and means "
            "nothing about its quality."
        ),
        "invalid_states": invalid,
        "per_state": per_state,
        "aggregate": {
            "states_compared": ok,
            "pooled_by_level": pooled,
            "mean_recall_llm": round(
                sum(per_state[s]["llm"]["recall"] for s in ok) / len(ok), 4) if ok else None,
            "mean_recall_baseline": round(
                sum(per_state[s]["baseline"]["recall"] for s in ok) / len(ok), 4) if ok else None,
        },
    }

    if args.baseline_review_dir:
        audits = {}
        for st in ok:
            try:
                a = fp_audit(st, Path(args.baseline_review_dir), outputs_dir)
                audits[st] = {k: v for k, v in a.items() if k != "verdicts"}
                audits[st]["verdicts"] = a["verdicts"]
            except Exception as e:  # noqa: BLE001
                audits[st] = {"error": f"{type(e).__name__}: {e}"}
        result["baseline_fp_audit"] = {
            "note": (
                "Run so the claim above is measured rather than asserted. A near-1.000 "
                "verified precision here is the EXPECTED and UNINFORMATIVE result — it "
                "reflects that rules copy text rather than invent it, not that the "
                "baseline is accurate. Do not put it in a table beside the LLM's."
            ),
            "verified_by": "claude-first-pass-UNSIGNED",
            "per_state": audits,
        }

    if args.probe_brittleness:
        result["brittleness_probe"] = probe_brittleness(outputs_dir, golden_dir, ok)

    Path(args.out).write_text(json.dumps(result, indent=2, default=str))
    print(f"wrote {args.out}")
    print(f"  states compared: {ok}")
    print(f"  invalid/excluded: {invalid or 'none'}")
    if ok:
        print(f"  mean recall  LLM {result['aggregate']['mean_recall_llm']}  "
              f"baseline {result['aggregate']['mean_recall_baseline']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
