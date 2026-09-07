"""Grade fresh KY trimmed runs against the VERIFIED trimmed goldens (Task 13).

Why this exists
---------------
`evaluation/ground_truth_{detector,parser}/KY_trimmed.json` were seeded from the
run of 2026-08-29 and then checked against the PDF. Grading THAT run against
them measures self-consistency and nothing else. Grading a *different* run makes
both metrics mean something:

  * **recall** — an element the annotator verified as present, that this run
    does not emit, is a real miss;
  * **precision** — an element this run emits that the golden does not carry is
    either a false positive or a golden gap, and the grounding check separates
    hallucinated text from grounded text.

⚠️ **Recall here has a ceiling and it is not 1.000-means-perfect.** The golden's
own coverage is bounded by what the seeding run emitted, so an element that
NEITHER run produces is missing from both and invisible to this measurement.
Report recall as *against a verified reference set of N elements*, never as
recall against the document. Closing that gap needs a cold read of the pages,
which is a separate exercise.

Everything is graded by the same `eval_detector.grade_elements` /
`eval_parser.grade_parser` as every other number in this paper.

Usage:
    python -m paper.analysis.grade_ky_trimmed \
        --run outputs/ky-3runs-09-07-26/run1 \
        --run outputs/ky-3runs-09-07-26/run2 \
        --run outputs/ky-3runs-09-07-26/run3 \
        --out paper/results/task13_YYYYMMDD
"""
from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from evaluation.eval_common import code_version_hash  # noqa: E402
from evaluation.eval_detector import (  # noqa: E402
    _title_key, grade_elements, report_to_dict,
)
from evaluation.eval_parser import grade_parser  # noqa: E402
from paper.analysis.scale_grade import (  # noqa: E402
    _extraction_index, adjudicate_unmatched, duplicate_analysis,
    recall_decomposition,
)

DET_GOLDEN = REPO / "evaluation" / "ground_truth_detector" / "KY_trimmed.json"
PAR_GOLDEN = REPO / "evaluation" / "ground_truth_parser" / "KY_trimmed.json"


def _fabricated_keys(standards: List[dict]) -> dict:
    """Standards separated only by the resolver's numeric `.N` fallback.

    ⚠️ `standard_id` uniqueness cannot detect these: the resolver runs first and
    makes them distinct by construction. Key on parents + indicator name.
    """
    groups: Dict[tuple, List[dict]] = defaultdict(list)
    for s in standards:
        groups[(
            (s.get("domain") or {}).get("code"),
            (s.get("strand") or {}).get("code"),
            (s.get("sub_strand") or {}).get("code"),
            " ".join(((s.get("indicator") or {}).get("name") or "").split()).lower().rstrip("."),
        )].append(s)
    dupes = {k: v for k, v in groups.items() if len(v) > 1}
    suffixed = [s for s in standards
                if re.search(r"\.\d+$", ((s.get("indicator") or {}).get("code") or ""))
                and not re.search(r"\.\d+\.\d+$", ((s.get("indicator") or {}).get("code") or ""))]
    return {
        "duplicate_standard_groups": len(dupes),
        "surplus_standards": sum(len(v) - 1 for v in dupes.values()),
        "examples": [
            {"ids": [x["standard_id"] for x in v],
             "page": v[0].get("source_page"),
             "bands": [x.get("age_band") for x in v],
             "name": k[3][:70]}
            for k, v in list(dupes.items())[:8]
        ],
        "_note": ("`standard_id` uniqueness reports zero collisions by construction — "
                  "disambiguate_colliding_standards renames them before the check runs. "
                  f"{len(suffixed)} standard(s) carry a bare numeric suffix."),
    }


def grade_run(run_dir: Path, det_golden: dict, par_golden: dict, index) -> dict:
    det = json.loads((run_dir / "KY-detection.json").read_text())["elements"]
    par = json.loads((run_dir / "KY-parsing.json").read_text())["indicators"]
    g_els = det_golden.get("elements", [])

    rep = grade_elements(g_els, list(det))
    rep.state = "KY"
    d = report_to_dict(rep)
    d["recall_decomposition"] = recall_decomposition(g_els, det)
    d["duplicates"] = duplicate_analysis(det)
    d["unmatched_adjudication"] = adjudicate_unmatched(g_els, det, index)
    d["age_band_emitted"] = sum(1 for e in det if e.get("age_band"))
    d["n_detected"] = len(det)

    prep = grade_parser(par_golden, par)
    p = {
        "n_golden": prep.n_golden, "n_parsed": prep.n_parsed,
        "matched": prep.matched, "coverage": round(prep.coverage, 4),
        "field_accuracy": round(prep.field_accuracy, 4),
        "standards_all_fields_ok": prep.standards_all_fields_ok,
        "dropped": prep.dropped, "duplicated": prep.duplicated,
        "id_collisions": prep.id_collisions,
        "mismatches_by_field": dict(Counter(m["field"] for m in prep.mismatches)),
        "mismatches": prep.mismatches[:40],
        "fabricated_keys": _fabricated_keys(par),
    }
    return {"run": run_dir.name, "detector": d, "parser": p}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--run", action="append", required=True,
                    help="directory holding KY-detection.json / KY-parsing.json")
    ap.add_argument("--extraction", default="outputs/scale-08-29-26/KY-extraction.json",
                    help="document extraction, for the grounding check")
    ap.add_argument("--out")
    args = ap.parse_args()

    det_golden = json.loads(DET_GOLDEN.read_text())
    par_golden = json.loads(PAR_GOLDEN.read_text())
    index = _extraction_index(Path(args.extraction))

    arms = [grade_run(Path(r), det_golden, par_golden, index) for r in args.run]

    print(f"{'run':8s} {'elems':>6s} {'banded':>7s} {'recall':>7s} {'r|noAB':>7s} "
          f"{'absent':>7s} {'dupes':>6s} {'halluc':>7s} {'cov':>6s} {'fieldacc':>9s} {'fabkeys':>8s}")
    for a in arms:
        d, p = a["detector"], a["parser"]
        rd = d["recall_decomposition"]
        print(f"{a['run']:8s} {d['n_detected']:6d} {d['age_band_emitted']:7d} "
              f"{d['recall']:7.3f} {rd['recall_ignoring_age_band']:7.3f} "
              f"{len(rd['absent_from_window']):7d} {d['duplicates']['surplus_detections']:6d} "
              f"{d['unmatched_adjudication']['n_ungrounded']:7d} "
              f"{p['coverage']:6.3f} {p['field_accuracy']:9.4f} "
              f"{p['fabricated_keys']['surplus_standards']:8d}")

    def spread(vals):
        return {"per_run": vals, "mean": round(statistics.fmean(vals), 4),
                "min": min(vals), "max": max(vals),
                "stdev": round(statistics.stdev(vals), 4) if len(vals) > 1 else 0.0}

    summary = {
        "runs": [a["run"] for a in arms],
        "code_version_hash": code_version_hash(),
        "golden": {"detector": str(DET_GOLDEN), "parser": str(PAR_GOLDEN),
                   "n_elements": len(det_golden["elements"]),
                   "n_standards": len(par_golden["standards"])},
        "⚠️_recall_ceiling": (
            "These goldens were seeded from the 2026-08-29 run and verified against the "
            "PDF. Recall is therefore measured AGAINST A VERIFIED REFERENCE SET, not "
            "against the document: an element no run emits is missing from the golden "
            "too and cannot be detected here. Report it as such."),
        "detector": {
            "elements": spread([a["detector"]["n_detected"] for a in arms]),
            "age_band_emitted": spread([a["detector"]["age_band_emitted"] for a in arms]),
            "recall_strict": spread([a["detector"]["recall"] for a in arms]),
            "recall_ignoring_age_band": spread(
                [a["detector"]["recall_decomposition"]["recall_ignoring_age_band"] for a in arms]),
            "absent": spread([len(a["detector"]["recall_decomposition"]["absent_from_window"]) for a in arms]),
            "surplus_duplicates": spread([a["detector"]["duplicates"]["surplus_detections"] for a in arms]),
            "hallucination_candidates": spread(
                [a["detector"]["unmatched_adjudication"]["n_ungrounded"] for a in arms]),
        },
        "parser": {
            "coverage": spread([a["parser"]["coverage"] for a in arms]),
            "field_accuracy": spread([a["parser"]["field_accuracy"] for a in arms]),
            "fabricated_keys": spread([a["parser"]["fabricated_keys"]["surplus_standards"] for a in arms]),
            "id_collisions": spread([len(a["parser"]["id_collisions"]) for a in arms]),
        },
        "arms": arms,
    }
    print("\n=== across arms ===")
    for stage in ("detector", "parser"):
        for k, v in summary[stage].items():
            print(f"  {stage}.{k:26s} {v['per_run']}  mean {v['mean']}  stdev {v['stdev']}")

    if args.out:
        o = Path(args.out); o.mkdir(parents=True, exist_ok=True)
        (o / "ky_trimmed_3runs.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False))
        print(f"\nwrote {o/'ky_trimmed_3runs.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
