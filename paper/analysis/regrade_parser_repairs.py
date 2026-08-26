"""Re-grade a recorded parser arm after a repair, without re-running Bedrock.

The deterministic code repairs in `parser.py` are post-processing over what the
parser LLM emitted. When one is added, the recorded parser numbers go stale —
but re-running the eval would draw a NEW LLM sample, confounding the repair's
effect with sampling. That is the wrong experiment: the defects these repairs
target are themselves intermittent, so a fresh run can come back clean (or fail
somewhere else) regardless of whether the repair works.

This script replays the current repair chain over the parsed standards a
recording already saved (`review_parser/<ST>/<ST>-parsed.json`) and re-grades
them with `eval_parser.grade_parser` — the identical function the original
recording used, so the two numbers are computed by the same code path and are
directly comparable.

    python paper/analysis/regrade_parser_repairs.py \\
        --results-dir paper/results/task1_20260826 \\
        --state AZ --state CA --state CO --state TX \\
        --out paper/results/task1_20260826/parser_regraded.json

⚠️ APPROXIMATION, and it matters. In `parse_llm_response` the repairs run on the
LLM's RAW emitted codes and `_anchor_parent_chain` runs AFTER them. The saved
`*-parsed.json` holds POST-anchoring output, so this replay applies the repairs
to codes that have already been anchored, then re-anchors. For the shapes these
repairs target the outcome is the same — a label-form or bare code survives
anchoring unchanged, because anchoring can only slice a well-formed indicator
code — but this is a replay, not a re-execution. Treat the result as strong
evidence for the repair's effect on THAT sample, not as a substitute for a live
recording at the new hash.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from evaluation.eval_parser import grade_parser  # noqa: E402
from els_pipeline.parser import (  # noqa: E402
    _anchor_parent_chain,
    _collapse_duplicated_indicator_segment,
    _collapse_duplicated_parent_segment,
    _delabel_parent_code,
    _qualify_bare_indicator_code,
    generate_standard_id,
)

GOLDEN_DIR = REPO / "evaluation" / "ground_truth_parser"


def _code(std: dict, level: str):
    node = std.get(level)
    return node.get("code") if isinstance(node, dict) else None


def repair_standard(std: dict) -> dict:
    """Apply the current repair chain, in the order `parse_llm_response` uses."""
    out = json.loads(json.dumps(std))
    domain = _code(out, "domain")
    strand = _delabel_parent_code(_code(out, "strand"), domain)
    sub = _delabel_parent_code(_code(out, "sub_strand"), domain)
    indicator = _code(out, "indicator") or ""

    sub, indicator = _collapse_duplicated_parent_segment(strand, sub, indicator)
    indicator = _collapse_duplicated_indicator_segment(strand, sub, indicator)
    indicator = _qualify_bare_indicator_code(domain, strand, sub, indicator)

    anchored_domain, anchored_strand, anchored_sub = _anchor_parent_chain(
        domain, strand, sub, indicator
    )
    for level, code in (
        ("domain", anchored_domain),
        ("strand", anchored_strand),
        ("sub_strand", anchored_sub),
        ("indicator", indicator),
    ):
        if isinstance(out.get(level), dict) and code is not None:
            out[level]["code"] = code

    out["standard_id"] = generate_standard_id(
        out.get("country", ""), out.get("state", ""), out.get("version_year", 0), indicator
    )
    return out


def _metrics(rep) -> dict:
    return {
        "coverage": rep.coverage,
        "field_accuracy": rep.field_accuracy,
        "fully_correct": rep.standards_all_fields_ok,
        "n_golden": rep.n_golden,
        "n_parsed": rep.n_parsed,
        "matched": rep.matched,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--results-dir", type=Path, required=True)
    ap.add_argument("--state", action="append", required=True, metavar="ST")
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    result = {
        "note": (
            "Replay of the current parser repair chain over the parsed standards this "
            "recording saved, re-graded with eval_parser.grade_parser. No Bedrock calls. "
            "See the module docstring for the anchoring approximation."
        ),
        "results_dir": str(args.results_dir),
        "states": {},
    }

    for state in args.state:
        parsed_path = args.results_dir / "review_parser" / state / f"{state}-parsed.json"
        golden_path = GOLDEN_DIR / f"{state}.json"
        if not parsed_path.exists():
            print(f"  {state}: SKIP — no {parsed_path}")
            continue
        standards = json.loads(parsed_path.read_text())
        golden = json.loads(golden_path.read_text())

        before = _metrics(grade_parser(golden, standards))
        after = _metrics(grade_parser(golden, [repair_standard(s) for s in standards]))
        changed = sum(1 for s in standards if repair_standard(s) != s)

        result["states"][state] = {
            "before": before,
            "after": after,
            "rows_changed_by_repairs": changed,
        }
        print(
            f"  {state}: fully_correct {before['fully_correct']}/{before['n_golden']}"
            f" -> {after['fully_correct']}/{after['n_golden']}"
            f"   field_accuracy {before['field_accuracy']:.4f} -> {after['field_accuracy']:.4f}"
            f"   rows changed by repairs: {changed}"
        )

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2) + "\n")
    print(f"Wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
