"""Nevada Pass-1 sampler A/B at n=5 per arm (arXiv paper Task 11).

Why this is being repeated
--------------------------
``paper/analysis/nv_attribution_ab.py`` established, at **n=1 per arm**, that
Nevada's two domain-code failures are caused by the Pass-1 SAMPLER rather than
by rule 4's ``code is REQUIRED`` prompt clarification. The paper reports that
attribution as *suggested* rather than *established*, and correctly so: the
detector is nondeterministic, one draw per arm cannot separate a real effect
from a lucky sample, and this paper has already recorded one headline of its
own that failed to reproduce.

Five draws per arm either establishes the attribution or retires it. Either is
a cleaner sentence than the hedge, and the cost is ten detector calls on one
15-page document.

The design
----------
Everything is held constant except which blocks Pass-1 sees:

  * **Arm A** -- the layout-stratified sampler (``_sample_blocks_for_depth_map``
    as shipped).
  * **Arm B** -- the pre-99b853cc stride sampler, monkeypatched in. This is the
    same patch ``nv_attribution_ab.py`` used, reproduced here rather than
    imported so the two files can be diffed against each other.

Same code version, same prompts, same frozen extraction, same grader,
``--no-cache`` on every draw so no run replays another's output. Rule 4's
prompt clarification is present in BOTH arms, which is what exonerates it.

⚠️ The cache MUST be bypassed and the arms MUST NOT share a key. ``use_cache``
is False on every call here. See ``eval_detector.run_detector_cached``'s warning
about ablation arms colliding on one cache key -- the failure mode is a
fabricated null result, which is the one outcome this script cannot afford.

Reading the result
------------------
The two DOMAIN mismatches (NV-DOM-02 ``S``, NV-DOM-03 ``T``) are the stable
signal the n=1 A/B turned on; a third, ``NV-SUB-06``, appeared in one arm-B
draw and was called ordinary sampling variance. With five draws that call is
testable rather than asserted, so per-test-case frequencies are reported, not
just the arm means.

Usage:
    python -m paper.analysis.nv_sampler_ab_n5 --runs 5 \
        --out paper/results/task11_YYYYMMDD/nv_sampler_ab_n5.json
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import Counter
from pathlib import Path
from typing import Callable, Dict, List

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

import els_pipeline.detector as D  # noqa: E402
from evaluation.eval_common import code_version_hash  # noqa: E402
from evaluation.eval_detector import evaluate_state  # noqa: E402

DEFAULT_EXTRACTION = REPO / "outputs" / "08-26-26-2" / "NV-extraction.json"
GOLDEN = REPO / "evaluation" / "ground_truth_detector" / "NV.json"

_NEW_SAMPLER = D._sample_blocks_for_depth_map


def old_stride_sampler(blocks, target_tokens=D.DEPTH_MAP_SAMPLE_TOKENS):
    """The pre-99b853cc sampler: every Nth block until the budget fills.

    Reproduced verbatim from ``nv_attribution_ab.py``. It keeps a line with
    probability 1/stride regardless of how load-bearing that line is, which is
    the property the layout-stratified sampler replaced -- and it stops as soon
    as the budget fills, so the document's tail is never sampled at all.
    """
    if not blocks:
        return []
    total = sum(D.estimate_tokens(b.text) for b in blocks)
    if total <= target_tokens:
        return blocks
    stride = max(1, total // target_tokens)
    out, tok = [], 0
    for i, b in enumerate(blocks):
        if i % stride == 0:
            out.append(b)
            tok += D.estimate_tokens(b.text)
            if tok >= target_tokens:
                break
    return out


def _draw(extraction: Path) -> dict:
    rep, _ = evaluate_state(
        state="NV",
        extraction_path=extraction,
        golden_path=GOLDEN,
        use_cache=False,          # never share a key between arms
        stability_runs=0,
    )
    return {
        "n_detected": rep.n_detected,
        "matched": rep.matched,
        "n_golden": rep.n_golden,
        "recall": rep.recall,
        "precision": rep.precision,
        "code_matches": rep.code_matches,
        "code_total": rep.code_total,
        "code_accuracy": rep.code_accuracy,
        "code_mismatch_ids": [m[0] for m in rep.code_mismatches],
        "code_mismatches": rep.code_mismatches,
        "description_matches": rep.description_matches,
        "description_total": rep.description_total,
        "depth_map_passed": rep.depth_map_passed,
        "depth_map_detail": rep.depth_map_detail,
    }


def _summarize(draws: List[dict]) -> dict:
    accs = [d["code_accuracy"] for d in draws if d["code_accuracy"] is not None]
    mism = Counter(i for d in draws for i in set(d["code_mismatch_ids"]))
    return {
        "n_draws": len(draws),
        "code_accuracy_mean": round(statistics.fmean(accs), 4) if accs else None,
        "code_accuracy_min": min(accs) if accs else None,
        "code_accuracy_max": max(accs) if accs else None,
        "code_accuracy_stdev": (
            round(statistics.stdev(accs), 4) if len(accs) > 1 else 0.0),
        "code_matches_per_draw": [f"{d['code_matches']}/{d['code_total']}" for d in draws],
        "recall_per_draw": [d["recall"] for d in draws],
        "description_per_draw": [
            f"{d['description_matches']}/{d['description_total']}" for d in draws],
        "mismatch_frequency": {k: f"{v}/{len(draws)}" for k, v in mism.most_common()},
        "depth_map_passed_per_draw": [d["depth_map_passed"] for d in draws],
    }


def _verdict(a: dict, b: dict, n: int) -> dict:
    """Is the attribution established, or retired?

    The test is not the arm means -- it is whether the two DOMAIN mismatches
    appear in every arm-B draw and no arm-A draw. That is the claim the paper
    would be making, so that is what gets checked.
    """
    domain_cases = {"NV-DOM-02", "NV-DOM-03"}
    def freq(summary, case):
        raw = summary["mismatch_frequency"].get(case, f"0/{n}")
        return int(raw.split("/")[0])
    a_hits = {c: freq(a, c) for c in domain_cases}
    b_hits = {c: freq(b, c) for c in domain_cases}
    clean = all(v == 0 for v in a_hits.values()) and all(v == n for v in b_hits.values())
    return {
        "domain_mismatches_in_arm_A": a_hits,
        "domain_mismatches_in_arm_B": b_hits,
        "established": clean,
        "reading": (
            "ESTABLISHED — both domain mismatches appear in every arm-B draw "
            "and no arm-A draw. The sampler is the cause; the paper may drop "
            "'suggested'."
            if clean else
            "NOT ESTABLISHED at this n — the mismatches do not separate the "
            "arms cleanly. Report the per-draw frequencies and keep the hedge, "
            "or state the effect as a rate rather than as a cause."
        ),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--runs", type=int, default=5, help="draws PER ARM")
    ap.add_argument("--extraction", default=str(DEFAULT_EXTRACTION),
                    help="frozen NV extraction — must be the SAME file for both arms")
    ap.add_argument("--out", help="path to write the result JSON")
    args = ap.parse_args()

    extraction = Path(args.extraction)
    if not extraction.exists():
        raise SystemExit(f"extraction not found: {extraction}")

    arms: Dict[str, List[dict]] = {}
    for name, sampler in (
        ("A_new_layout_sampler", _NEW_SAMPLER),
        ("B_old_stride_sampler", old_stride_sampler),
    ):
        D._sample_blocks_for_depth_map = sampler
        print(f"\n=== arm {name} ({args.runs} draws) ===")
        draws = []
        for i in range(args.runs):
            print(f"  draw {i + 1}/{args.runs}…")
            draws.append(_draw(extraction))
            d = draws[-1]
            print(f"    code {d['code_matches']}/{d['code_total']}  "
                  f"desc {d['description_matches']}/{d['description_total']}  "
                  f"recall {d['recall']:.3f}  mismatches {d['code_mismatch_ids']}")
        arms[name] = draws
    D._sample_blocks_for_depth_map = _NEW_SAMPLER  # restore

    summaries = {k: _summarize(v) for k, v in arms.items()}
    out = {
        "question": "Does the Pass-1 layout-stratified sampler CAUSE Nevada's "
                    "two domain-code fixes, at n>1 per arm?",
        "supersedes": "paper/results/task2_20260826/nv_attribution_ab.json (n=1 per arm)",
        "code_version_hash": code_version_hash(),
        "extraction": str(extraction),
        "golden": str(GOLDEN),
        "runs_per_arm": args.runs,
        "method": (
            "Two arms on ONE frozen extraction, same code version, same prompts, "
            "same grader, use_cache=False on every draw. The ONLY difference is "
            "which blocks Pass-1 sees: arm B monkeypatches "
            "detector._sample_blocks_for_depth_map back to the pre-99b853cc "
            "stride implementation. Rule 4's 'code is REQUIRED' clarification is "
            "present in BOTH arms, which is what exonerates it."
        ),
        "summary": summaries,
        "verdict": _verdict(summaries["A_new_layout_sampler"],
                            summaries["B_old_stride_sampler"], args.runs),
        "draws": arms,
    }

    print("\n=== summary ===")
    for k, v in summaries.items():
        print(f"  {k}: code {v['code_matches_per_draw']}  "
              f"mean {v['code_accuracy_mean']}  stdev {v['code_accuracy_stdev']}")
        print(f"    mismatch frequency: {v['mismatch_frequency']}")
    print(f"\n  VERDICT: {out['verdict']['reading']}")

    if args.out:
        p = Path(args.out)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(out, indent=2, ensure_ascii=False))
        print(f"\nwrote {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
