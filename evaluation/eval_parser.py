"""ELS parser evaluation suite.

Runs the parser (`parse_hierarchy`) against one or more frozen detector outputs
(`{STATE}-detection.json`) and grades the resulting `NormalizedStandard`s
against each golden element's `parser_expected` block. The headline goal is
**consistency + correctness of codes and names across runs** — i.e. the parser
isn't emitting random hierarchy codes/names each time.

Metrics per state:
  - Coverage: how many annotated golden indicators the parser produced
    (recall); which were dropped; which matched more than one standard.
  - Field accuracy: per-field exact-match vs `parser_expected` for
    domain/strand/sub_strand/indicator code+name, age_band_months, standard_id.
  - standard_id uniqueness across the whole output (collision detector).
  - Targeted regression cases via `regression_checks.lookup_parser`
    (check_parser_<id>); a case with no parser check is SKIPped.
  - Optional N-run stability: rerun the parser N times on the same frozen
    detection input and report the per-indicator field-disagreement rate.

Parser input is a FROZEN detection.json fixture, so runs are deterministic
except for the parser LLM itself; the parser output is cached in
``evaluation/.cache/`` keyed by (state, detection-hash, suffix).

NOTE: parser.py is a work in progress — failing checks here are diagnostic
(they pinpoint what to fix), not blockers.

Usage:
    python -m evaluation.eval_parser --detection-dir outputs/05-31-26
    python -m evaluation.eval_parser --state CA --detection-dir outputs/05-31-26
    python -m evaluation.eval_parser --state CA --stability-runs 3 --no-cache
    python -m evaluation.eval_parser --detection-dir outputs/05-31-26 --output-dir evaluation/review_parser
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

from evaluation.eval_common import (
    CACHE_DIR,
    _hash_blocks,
    _norm,
    run_regressions,
)
from els_pipeline.parser import parse_hierarchy
from els_pipeline.models import DetectedElement
from evaluation import regression_checks

logger = logging.getLogger("eval_parser")


# Fields graded against parser_expected, paired with how to read them from a
# parser output indicator (serialized NormalizedStandard).
def _code(level: Optional[dict]) -> Optional[str]:
    return (level or {}).get("code") if isinstance(level, dict) else None


def _name(level: Optional[dict]) -> Optional[str]:
    return (level or {}).get("name") if isinstance(level, dict) else None


GRADED_FIELDS: List[Tuple[str, Callable[[dict], Optional[str]]]] = [
    ("domain_code", lambda i: _code(i.get("domain"))),
    ("domain_name", lambda i: _name(i.get("domain"))),
    ("strand_code", lambda i: _code(i.get("strand"))),
    ("strand_name", lambda i: _name(i.get("strand"))),
    ("sub_strand_code", lambda i: _code(i.get("sub_strand"))),
    ("sub_strand_name", lambda i: _name(i.get("sub_strand"))),
    ("indicator_code", lambda i: _code(i.get("indicator"))),
    ("indicator_name", lambda i: _name(i.get("indicator"))),
    ("age_band_months", lambda i: i.get("age_band")),
    ("standard_id", lambda i: i.get("standard_id")),
]


# ---------- parser runner with cache ----------

def run_parser_cached(
    state: str,
    detection_path: Path,
    golden: dict,
    default_age_band: str,
    use_cache: bool = True,
    cache_suffix: str = "",
) -> List[dict]:
    """Run the parser once on a frozen detection.json. Cache by
    (state, detection-hash, suffix). Returns ParseResult.indicators."""
    detection = json.loads(detection_path.read_text())
    elements_data = detection.get("elements", detection if isinstance(detection, list) else [])

    cache_key = f"parser-{state}-{_hash_blocks(elements_data, text_key='source_text')}-{cache_suffix}.json"
    cache_path = CACHE_DIR / cache_key
    if use_cache and cache_path.exists():
        logger.info(f"  [cache hit] {cache_path.name}")
        return json.loads(cache_path.read_text())

    elements = [DetectedElement(**e) for e in elements_data]
    logger.info(f"  [parser] running on {len(elements)} detected elements…")
    result = parse_hierarchy(
        elements=elements,
        country=golden.get("country", "US"),
        state=golden.get("state", state),
        version_year=golden.get("version_year", 0),
        age_band=default_age_band,
    )
    indicators = result.indicators
    cache_path.write_text(json.dumps(indicators, indent=2, default=str, ensure_ascii=False))
    return indicators


# ---------- matching ----------

def _desc_overlap(a: Optional[str], b: Optional[str]) -> float:
    sa, sb = set(_norm(a).split()), set(_norm(b).split())
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def _index_by_name(indicators: List[dict]) -> Dict[str, List[dict]]:
    idx: Dict[str, List[dict]] = defaultdict(list)
    for ind in indicators:
        idx[_norm(_name(ind.get("indicator")))].append(ind)
    return idx


def _match_one(golden_ind: dict, by_name: Dict[str, List[dict]], matched_ids: set) -> Optional[dict]:
    """Match a golden indicator to a parser output indicator by normalized name,
    disambiguating same-named age-band variants by description overlap."""
    title = _norm(golden_ind.get("title"))
    cands = [c for c in by_name.get(title, []) if id(c) not in matched_ids]
    if not cands:
        return None
    if len(cands) == 1:
        return cands[0]
    gdesc = golden_ind.get("description") or ""
    return max(cands, key=lambda c: _desc_overlap(gdesc, (c.get("indicator") or {}).get("description")))


# ---------- metrics ----------

@dataclass
class ParserStateReport:
    state: str
    n_golden_indicators: int = 0
    n_parsed: int = 0
    matched: int = 0

    dropped: List[str] = field(default_factory=list)            # golden test_case_ids
    ungraded: List[str] = field(default_factory=list)           # matched but no parser_expected
    id_collisions: List[str] = field(default_factory=list)      # duplicate standard_ids

    # field -> {"ok": n, "total": n}
    field_stats: Dict[str, Dict[str, int]] = field(
        default_factory=lambda: defaultdict(lambda: {"ok": 0, "total": 0})
    )
    mismatches: List[dict] = field(default_factory=list)        # {test_case_id, field, expected, got}

    regressions: List[Tuple[str, str, str]] = field(default_factory=list)

    matched_pairs: List[Tuple[dict, dict]] = field(default_factory=list)  # (golden, parsed)
    dropped_full: List[dict] = field(default_factory=list)

    stability_runs: int = 0
    stability_disagreement_rate: Optional[float] = None
    stability_size_stdev: Optional[float] = None

    @property
    def coverage(self) -> float:
        return self.matched / self.n_golden_indicators if self.n_golden_indicators else 0.0

    @property
    def field_accuracy(self) -> float:
        ok = sum(s["ok"] for s in self.field_stats.values())
        total = sum(s["total"] for s in self.field_stats.values())
        return ok / total if total else 0.0


def grade_parser(golden: dict, indicators: List[dict]) -> ParserStateReport:
    rep = ParserStateReport(state=golden.get("state", ""))
    golden_inds = [g for g in golden.get("elements", []) if g.get("level") == "indicator"]
    rep.n_golden_indicators = len(golden_inds)
    rep.n_parsed = len(indicators)

    by_name = _index_by_name(indicators)
    matched_ids: set = set()

    for g in golden_inds:
        gid = g.get("test_case_id", "?")
        d = _match_one(g, by_name, matched_ids)
        if d is None:
            rep.dropped.append(gid)
            rep.dropped_full.append(g)
            continue

        matched_ids.add(id(d))
        rep.matched += 1
        rep.matched_pairs.append((g, d))

        expected = g.get("parser_expected")
        if not expected:
            rep.ungraded.append(gid)
            continue

        for fname, getter in GRADED_FIELDS:
            if fname not in expected:
                continue
            exp = expected.get(fname)
            got = getter(d)
            rep.field_stats[fname]["total"] += 1
            if (exp or None) == (got or None):
                rep.field_stats[fname]["ok"] += 1
            else:
                rep.mismatches.append(
                    {"test_case_id": gid, "field": fname, "expected": exp, "got": got}
                )

    # Global standard_id uniqueness across the whole parser output.
    seen: set = set()
    for ind in indicators:
        sid = ind.get("standard_id")
        if sid in seen:
            rep.id_collisions.append(sid)
        seen.add(sid)

    return rep


# ---------- stability ----------

def measure_stability(
    state: str,
    detection_path: Path,
    golden: dict,
    default_age_band: str,
    runs: int,
) -> Tuple[float, float]:
    """Rerun the parser `runs` times on the same frozen detection input; report
    the per-indicator field-disagreement rate and output-size stdev. An indicator
    identity is (normalized name, age_band); the compared signature is the tuple
    of hierarchy codes + names + standard_id."""
    import statistics

    def _sig(ind: dict) -> Tuple:
        return (
            _code(ind.get("domain")), _name(ind.get("domain")),
            _code(ind.get("strand")), _name(ind.get("strand")),
            _code(ind.get("sub_strand")), _name(ind.get("sub_strand")),
            _code(ind.get("indicator")), _name(ind.get("indicator")),
            ind.get("standard_id"),
        )

    def _key(ind: dict) -> Tuple:
        return (_norm(_name(ind.get("indicator"))), ind.get("age_band"))

    outputs: List[List[dict]] = []
    for i in range(runs):
        outputs.append(
            run_parser_cached(
                state, detection_path, golden, default_age_band,
                use_cache=False, cache_suffix=f"stab-{i}",
            )
        )

    sizes = [len(o) for o in outputs]
    size_stdev = statistics.pstdev(sizes) if len(sizes) > 1 else 0.0

    base = {_key(e): _sig(e) for e in outputs[0]}
    disagreements = compared = 0
    for other in outputs[1:]:
        omap = {_key(e): _sig(e) for e in other}
        for k, sig in base.items():
            if k in omap:
                compared += 1
                if omap[k] != sig:
                    disagreements += 1
    rate = disagreements / compared if compared else 0.0
    return rate, size_stdev


# ---------- orchestration ----------

def evaluate_state(
    state: str,
    detection_path: Path,
    golden_path: Path,
    default_age_band: str,
    use_cache: bool,
    stability_runs: int,
) -> Tuple[ParserStateReport, List[dict]]:
    logger.info(f"== {state} ==")
    golden = json.loads(golden_path.read_text())

    indicators = run_parser_cached(
        state, detection_path, golden, default_age_band, use_cache=use_cache
    )
    rep = grade_parser(golden, indicators)
    rep.state = state
    rep.regressions = run_regressions(golden, indicators, regression_checks.lookup_parser)

    if stability_runs > 1:
        rep.stability_runs = stability_runs
        rep.stability_disagreement_rate, rep.stability_size_stdev = measure_stability(
            state, detection_path, golden, default_age_band, stability_runs
        )

    return rep, indicators


def render_report(rep: ParserStateReport) -> str:
    out = []
    out.append(f"\n=== {rep.state} ===")
    out.append(f"  golden indicators: {rep.n_golden_indicators}")
    out.append(f"  parsed:            {rep.n_parsed}")
    out.append(f"  matched:           {rep.matched}  (coverage {rep.coverage:.3f})")
    out.append(f"  field accuracy:    {rep.field_accuracy:.3f}")

    out.append("  per-field (ok/total):")
    for fname, _ in GRADED_FIELDS:
        s = rep.field_stats.get(fname)
        if not s or s["total"] == 0:
            continue
        acc = s["ok"] / s["total"]
        flag = "" if s["ok"] == s["total"] else "  ← MISMATCH"
        out.append(f"    {fname:<18} {s['ok']:>3}/{s['total']:<3} ({acc:.2f}){flag}")

    if rep.dropped:
        out.append(f"  dropped ({len(rep.dropped)}): {rep.dropped[:10]}{'…' if len(rep.dropped) > 10 else ''}")
    else:
        out.append("  dropped: 0")
    if rep.ungraded:
        out.append(f"  ungraded — no parser_expected ({len(rep.ungraded)}): {rep.ungraded[:10]}{'…' if len(rep.ungraded) > 10 else ''}")
    if rep.id_collisions:
        uniq = sorted(set(rep.id_collisions))
        out.append(f"  standard_id collisions ({len(rep.id_collisions)}): {uniq[:5]}{'…' if len(uniq) > 5 else ''}")
    else:
        out.append("  standard_id collisions: 0")

    if rep.mismatches:
        out.append(f"  field mismatches ({len(rep.mismatches)}):")
        for m in rep.mismatches[:12]:
            out.append(f"    {m['test_case_id']} {m['field']}: expected {m['expected']!r} got {m['got']!r}")
        if len(rep.mismatches) > 12:
            out.append(f"    … and {len(rep.mismatches) - 12} more")

    out.append("  regression cases:")
    for cid, status, detail in rep.regressions:
        out.append(f"    [{status}] {cid} — {detail}")

    if rep.stability_runs > 1:
        out.append(f"  stability ({rep.stability_runs} runs):")
        out.append(f"    field disagreement rate: {rep.stability_disagreement_rate:.3f}")
        out.append(f"    output size stdev:       {rep.stability_size_stdev:.2f}")

    return "\n".join(out)


def write_review_dir(rep: ParserStateReport, indicators: List[dict], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    state = rep.state

    (output_dir / f"{state}-report.txt").write_text(render_report(rep))
    (output_dir / f"{state}-parsed.json").write_text(
        json.dumps(indicators, indent=2, default=str, ensure_ascii=False)
    )

    review = {
        "state": state,
        "summary": {
            "golden_indicators": rep.n_golden_indicators,
            "parsed": rep.n_parsed,
            "matched": rep.matched,
            "coverage": round(rep.coverage, 4),
            "field_accuracy": round(rep.field_accuracy, 4),
            "dropped": len(rep.dropped),
            "ungraded": len(rep.ungraded),
            "id_collisions": len(rep.id_collisions),
        },
        "matched": [{"golden": g, "parsed": d} for g, d in rep.matched_pairs],
        "dropped_from_parsed": rep.dropped_full,
        "field_mismatches": rep.mismatches,
        "regressions": [
            {"id": cid, "status": status, "detail": detail}
            for cid, status, detail in rep.regressions
        ],
    }
    (output_dir / f"{state}-review.json").write_text(
        json.dumps(review, indent=2, default=str, ensure_ascii=False)
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", action="append", help="Limit to specific state(s); repeatable")
    parser.add_argument("--detection-dir", default="outputs", help="Directory holding {STATE}-detection.json files (parser input)")
    parser.add_argument("--golden-dir", default="evaluation/ground_truth", help="Directory holding {STATE}.json golden sets")
    parser.add_argument("--default-age-band", default="", help="Fallback age_band passed to parse_hierarchy when the LLM returns null")
    parser.add_argument("--no-cache", action="store_true", help="Disable parser-output cache")
    parser.add_argument("--stability-runs", type=int, default=1, help="Re-run the parser this many times to measure stability (>=2 enables it)")
    parser.add_argument("--report-json", help="Optional path to write the full report as JSON")
    parser.add_argument("--output-dir", help="Directory to write per-state review files")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    detection_dir = Path(args.detection_dir)
    golden_dir = Path(args.golden_dir)
    states = args.state or sorted(p.stem for p in golden_dir.glob("*.json"))
    output_dir = Path(args.output_dir) if args.output_dir else None

    reports: List[ParserStateReport] = []
    for st in states:
        det_path = detection_dir / f"{st}-detection.json"
        gold_path = golden_dir / f"{st}.json"
        if not det_path.exists() or not gold_path.exists():
            logger.warning(f"-- {st}: skipped (missing {det_path if not det_path.exists() else gold_path})")
            continue
        try:
            rep, indicators = evaluate_state(
                st, det_path, gold_path,
                default_age_band=args.default_age_band,
                use_cache=not args.no_cache,
                stability_runs=args.stability_runs,
            )
            reports.append(rep)
            if output_dir:
                write_review_dir(rep, indicators, output_dir / st)
        except Exception as e:
            logger.exception(f"-- {st}: ERROR — {e}")

    for rep in reports:
        print(render_report(rep))

    if output_dir:
        print(f"\nReview files written to {output_dir}/")

    if args.report_json:
        out = []
        for r in reports:
            out.append({
                "state": r.state,
                "coverage": r.coverage,
                "field_accuracy": r.field_accuracy,
                "matched": r.matched,
                "n_golden_indicators": r.n_golden_indicators,
                "n_parsed": r.n_parsed,
                "dropped": r.dropped,
                "ungraded": r.ungraded,
                "id_collisions": sorted(set(r.id_collisions)),
                "field_stats": {k: dict(v) for k, v in r.field_stats.items()},
                "mismatches": r.mismatches,
                "regressions": [{"id": c, "status": s, "detail": d} for c, s, d in r.regressions],
                "stability_runs": r.stability_runs,
                "stability_disagreement_rate": r.stability_disagreement_rate,
                "stability_size_stdev": r.stability_size_stdev,
            })
        Path(args.report_json).write_text(json.dumps(out, indent=2, default=str, ensure_ascii=False))
        print(f"\nFull report written to {args.report_json}")

    failures = sum(
        1 for r in reports
        for _, status, _ in r.regressions
        if status in ("FAIL", "ERROR")
    )
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
