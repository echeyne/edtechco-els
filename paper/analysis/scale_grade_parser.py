"""Grade the PARSER goldens inside a larger-tier run (arXiv Task 9b).

The detector counterpart is ``scale_grade.py``; read its docstring first. This
file does the same thing one stage later, and differs in three ways that follow
from how ``eval_parser`` works.

**1. No page window is needed for matching.** ``eval_parser._match_key`` is
``(indicator name, age_band)``, not a page. A golden standard either finds its
match somewhere in the parsed output or it does not, so the whole run is
searched and coverage means "did this standard survive at scale".

**2. ``source_page`` MUST be translated, or every standard reports a false
mismatch.** ``source_page`` is one of the graded fields, the golden records it
in `_only_subset` numbering, and the run records it in the target tier's. Left
alone this reports a mismatch on essentially every matched standard: on the
2026-08-29 runs it accounted for 6 of Kentucky's 8 field mismatches and 9 of
Colorado's 14, and it drove Colorado's "all fields correct" count to **0 of
9** — a number that looks like total failure and is entirely an artifact of
comparing two different page numberings. The golden is therefore copied and its
``source_page`` rewritten into target-tier numbering before grading, using the
same recorded map ``scale_grade.py`` uses. Both figures are reported: corrected
(the real one) and uncorrected (so the size of the artifact is visible rather
than silently removed).

**3. Identifier uniqueness is checked over the WHOLE run, and this is the part
that needs no annotation at all.** ``grade_parser`` already scans every parsed
standard for a duplicate ``standard_id``. At the `_only_subset` tier that
scans tens of standards; at the trimmed tier it scans hundreds. The paper's
collision-free-identifier claim is one of its two headline contributions, and
this is the cheapest way to test it at scale — no golden is consulted, so the
result is as strong as the run is large.

⚠️ **Precision is not reported and cannot be.** ``grade_parser`` measures
coverage and per-field accuracy over matched pairs; a parser golden of 26
standards against a run of 214 says nothing about the other 188. Do not read
coverage as precision.

Usage:
    python -m paper.analysis.scale_grade_parser --state KY --state CO \
        --parsing-dir outputs/scale-08-29-26 --out paper/results/task9_20260905
"""
from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from evaluation.eval_common import code_version_hash  # noqa: E402
from evaluation.eval_parser import grade_parser  # noqa: E402
from paper.analysis.scale_grade import PAGE_RANGES, build_page_map  # noqa: E402


def _load_standards(path: Path) -> List[dict]:
    """The parsing stage writes its output under ``indicators``.

    ⚠️ Not ``standards`` — reading the wrong key returns an empty list, and an
    empty list grades as coverage 0.000 with no error raised anywhere. That is
    a silent total failure that looks like a catastrophic quality result, so
    the key is asserted rather than defaulted.
    """
    doc = json.loads(path.read_text())
    if isinstance(doc, list):
        return doc
    if "indicators" not in doc:
        raise SystemExit(
            f"{path}: no 'indicators' key (found {sorted(doc)[:6]}). "
            "Refusing to grade an empty list as coverage 0.000."
        )
    return doc["indicators"]


def _translate_pages(golden: dict, page_map: Dict[int, int]) -> tuple[dict, int]:
    """Copy the golden with ``source_page`` rewritten into target-tier numbers."""
    out = copy.deepcopy(golden)
    n = 0
    for std in out.get("standards", []):
        exp = std.get("expected") or {}
        p = exp.get("source_page")
        try:
            p = int(p)
        except (TypeError, ValueError):
            continue
        if p in page_map:
            exp["source_page"] = page_map[p]
            n += 1
    return out, n


def grade_state(state: str, golden_path: Path, parsing_path: Path, ranges: dict,
                source_tier: str, target_tier: str) -> dict:
    golden = json.loads(golden_path.read_text())
    standards = _load_standards(parsing_path)
    page_map, unmappable = build_page_map(state, ranges, source_tier, target_tier)
    translated, n_translated = _translate_pages(golden, page_map)

    rep = grade_parser(translated, standards)
    raw = grade_parser(golden, standards)   # uncorrected, to size the artifact

    def _pack(r, label):
        return {
            "_arm": label,
            "n_golden": r.n_golden,
            "n_parsed_in_run": r.n_parsed,
            "matched": r.matched,
            "coverage": round(r.coverage, 4),
            "field_accuracy": round(r.field_accuracy, 4),
            "standards_all_fields_ok": r.standards_all_fields_ok,
            "dropped": r.dropped,
            "duplicated": r.duplicated,
            "mismatches_by_field": _by_field(r.mismatches),
            "mismatches": r.mismatches,
        }

    return {
        "state": state,
        "source_tier": source_tier,
        "target_tier": target_tier,
        "golden_file": str(golden_path),
        "parsing_file": str(parsing_path),
        "code_version_hash": code_version_hash(),
        "page_translation": {
            "standards_translated": n_translated,
            "map_source_to_target": {str(k): v for k, v in sorted(page_map.items())},
            "unmappable_source_pages": unmappable,
            "_why": (
                "source_page is a GRADED field recorded in _only_subset numbering "
                "in the golden and in target-tier numbering in the run. Without "
                "this translation every matched standard reports a false "
                "source_page mismatch."
            ),
        },
        "corrected": _pack(rep, "source_page translated — THIS IS THE REAL FIGURE"),
        "coverage_decomposition": coverage_decomposition(
            translated, standards, rep.dropped),
        "uncorrected": _pack(raw, "source_page NOT translated — artifact size only"),
        "identifier_uniqueness_over_whole_run": {
            "n_standards": len(standards),
            "n_distinct_standard_ids": len({s.get("standard_id") for s in standards}),
            "collisions": rep.id_collisions,
            "_why_this_matters": (
                "Consults NO golden, so it is as strong as the run is large. The "
                "paper's collision-free identifier claim is measured over tens of "
                "standards at the _only_subset tier; this measures it over "
                f"{len(standards)}."
            ),
        },
        "⚠️_precision_not_reported": (
            "grade_parser measures coverage and per-field accuracy over matched "
            f"pairs. A golden of {rep.n_golden} against a run of {len(standards)} "
            "says nothing about the other "
            f"{len(standards) - rep.n_golden}. Coverage is NOT precision."
        ),
    }


def coverage_decomposition(golden: dict, standards: List[dict],
                           dropped_ids: List[str]) -> dict:
    """Split a coverage miss: standard absent, or age_band drift?

    ``eval_parser._match_key`` is ``(indicator name, age_band)``, so a standard
    the run produced correctly -- right ``standard_id``, right chain, right
    name -- reads as DROPPED if its age band differs. At the `_only_subset`
    tier that almost never fires; at scale it is the dominant cause, and
    reporting it as "7 standards lost" would be simply wrong.

    Same posture as ``scale_grade.recall_decomposition``: the graded coverage
    stays the strict key, and this sits beside it to say what the miss was.
    """
    by_name = {}
    for s_ in standards:
        nm = ((s_.get("indicator") or {}).get("name") or "").strip().lower()
        by_name.setdefault(nm, []).append(s_)

    gm = {g.get("test_case_id"): (g.get("expected") or {})
          for g in golden.get("standards", [])}
    absent, drift = [], []
    for tid in dropped_ids:
        exp = gm.get(tid, {})
        nm = ((exp.get("indicator") or {}).get("name") or "").strip().lower()
        hits = by_name.get(nm, [])
        if not hits:
            absent.append({"test_case_id": tid,
                           "standard_id": exp.get("standard_id"),
                           "name": ((exp.get("indicator") or {}).get("name") or "")[:80]})
            continue
        drift.append({
            "test_case_id": tid,
            "golden_standard_id": exp.get("standard_id"),
            "run_standard_id": hits[0].get("standard_id"),
            "standard_id_matches": exp.get("standard_id") == hits[0].get("standard_id"),
            "golden_age_band": exp.get("age_band"),
            "run_age_band": sorted({h.get("age_band") for h in hits}),
            "name": ((exp.get("indicator") or {}).get("name") or "")[:80],
        })
    n = len(golden.get("standards", []))
    return {
        "n_absent": len(absent),
        "n_age_band_drift": len(drift),
        "coverage_ignoring_age_band": round((n - len(absent)) / n, 4) if n else None,
        "absent": absent,
        "age_band_drift": drift,
        "_reading": (
            "`absent` is a standard the parser genuinely failed to produce at "
            "scale. `age_band_drift` is one it produced -- check "
            "`standard_id_matches` -- that fails the (name, age_band) match key "
            "on its band alone. Only the first is a parsing loss."
        ),
    }


def _by_field(mismatches: List[dict]) -> dict:
    out: Dict[str, int] = {}
    for m in mismatches:
        out[m["field"]] = out.get(m["field"], 0) + 1
    return dict(sorted(out.items(), key=lambda kv: -kv[1]))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--state", action="append", required=True)
    ap.add_argument("--parsing-dir", required=True,
                    help="dir holding <STATE>-parsing.json")
    ap.add_argument("--golden-dir", default="evaluation/ground_truth_parser")
    ap.add_argument("--source-tier", default="only_subset")
    ap.add_argument("--target-tier", default="trimmed")
    ap.add_argument("--out")
    args = ap.parse_args()

    ranges = json.loads(PAGE_RANGES.read_text())
    results = {}
    for state in args.state:
        res = grade_state(
            state,
            Path(args.golden_dir) / f"{state}.json",
            Path(args.parsing_dir) / f"{state}-parsing.json",
            ranges, args.source_tier, args.target_tier,
        )
        results[state] = res
        c, u = res["corrected"], res["uncorrected"]
        idu = res["identifier_uniqueness_over_whole_run"]
        print(f"\n=== {state}: parser golden inside {args.target_tier} run ===")
        print(f"  run holds {c['n_parsed_in_run']} standards; "
              f"golden annotates {c['n_golden']}")
        print(f"  coverage       {c['matched']}/{c['n_golden']} = {c['coverage']:.3f}")
        print(f"  field accuracy {c['field_accuracy']:.4f}  "
              f"(uncorrected {u['field_accuracy']:.4f})")
        print(f"  all fields ok  {c['standards_all_fields_ok']}/{c['matched']}  "
              f"(uncorrected {u['standards_all_fields_ok']}/{u['matched']})")
        cd = res["coverage_decomposition"]
        print(f"  dropped        {c['dropped']}")
        print(f"  coverage ignoring age_band: {cd['coverage_ignoring_age_band']:.3f} "
              f"({cd['n_absent']} absent, {cd['n_age_band_drift']} age-band drift)")
        print(f"  mismatches     {c['mismatches_by_field']}")
        print(f"  ID UNIQUENESS  {idu['n_distinct_standard_ids']}/{idu['n_standards']} "
              f"distinct, {len(idu['collisions'])} collisions")

    if args.out:
        outdir = Path(args.out)
        outdir.mkdir(parents=True, exist_ok=True)
        for state, res in results.items():
            (outdir / f"{state}_scale_grade_parser.json").write_text(
                json.dumps(res, indent=2, ensure_ascii=False))
        print(f"\nwrote {len(results)} file(s) to {outdir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
