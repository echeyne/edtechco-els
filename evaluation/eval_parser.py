"""ELS parser evaluation suite.

Runs the parser (`parse_hierarchy`) against one or more frozen detector outputs
(`{STATE}-detection.json`) and grades the resulting `NormalizedStandard`s
against a hand-verified parser golden set (`evaluation/ground_truth_parser/`).

Unlike the detector golden (a flat element list), the parser produces fully
resolved, NESTED `NormalizedStandard` objects, so each golden entry mirrors that
whole object and we grade EVERY field of it: standard_id, country/state/
version_year, the nested domain/strand/sub_strand/indicator (code + name +
description each), age_band, source_page. (source_text is excluded — it's
verbatim multi-line prose that's impractical to hand-author.)

The headline goal is consistency + correctness across runs — the parser isn't
emitting random hierarchy codes/names each time.

Metrics per state:
  - Coverage: how many golden standards the parser produced (recall) / dropped.
  - Field accuracy: per-field exact-match across the entire NormalizedStandard,
    aggregated and broken out per dotted field path (e.g. sub_strand.code).
  - standard_id uniqueness across the whole output (collision detector).
  - Parser regression cases via `regression_checks.lookup_parser`.
  - Optional N-run stability: rerun the parser N times on the same frozen
    detection input and report the per-standard field-disagreement rate.

Parser input is a FROZEN detection.json fixture, so runs are deterministic
except for the parser LLM itself; the parser output is cached in
``evaluation/.cache/`` keyed by (state, detection-hash, code-hash, suffix). The
code hash covers ``detector.py`` and ``parser.py`` (see
``eval_common.code_version_hash``), so editing a prompt invalidates the cache by
itself — a cached run can never replay pre-edit output as a pass.

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
import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from evaluation.eval_common import (
    CACHE_DIR,
    _hash_blocks,
    as_plain_json,
    code_version_hash,
    _norm,
    _norm_age_band,
    run_regressions,
)
from els_pipeline.parser import parse_hierarchy
from els_pipeline.models import DetectedElement
from evaluation import regression_checks

logger = logging.getLogger("eval_parser")

# Every field of NormalizedStandard we grade, expressed as dotted paths. Nested
# HierarchyLevel objects expand to <level>.<code|name|description>. This is the
# whole object the parser returns (minus nothing) — change here if the model
# gains/loses a field.
# NOTE: source_text is deliberately NOT graded — it's verbatim multi-line prose
# that's impractical to hand-author in the golden, so it's neither expected nor
# compared.
SCALAR_FIELDS = [
    "standard_id", "country", "state", "version_year",
    "age_band", "source_page",
]
LEVELS = ["domain", "strand", "sub_strand", "indicator"]
LEVEL_SUBFIELDS = ["code", "name", "description"]


def _all_field_paths() -> List[str]:
    paths = list(SCALAR_FIELDS)
    for lvl in LEVELS:
        for sub in LEVEL_SUBFIELDS:
            paths.append(f"{lvl}.{sub}")
    return paths


FIELD_PATHS = _all_field_paths()


def _get_path(obj: dict, path: str) -> Any:
    """Read a dotted path from a standard dict. A null nested level (e.g. no
    sub_strand) yields None for all its subfields."""
    if "." not in path:
        return obj.get(path)
    head, sub = path.split(".", 1)
    level = obj.get(head)
    if not isinstance(level, dict):
        return None
    return level.get(sub)


def _norm_val(v: Any) -> Any:
    """Normalize a field value for comparison: treat ''/None alike, and compare
    strings whitespace-insensitively so newline/spacing quirks don't dominate."""
    if v is None:
        return None
    if isinstance(v, str):
        return " ".join(v.split()) or None
    return v


# ---------- parser runner with cache ----------

def run_parser_cached(
    state: str,
    detection_path: Path,
    country: str,
    version_year: int,
    default_age_band: str,
    use_cache: bool = True,
    cache_suffix: str = "",
) -> List[dict]:
    """Run the parser once on a frozen detection.json. Cache by
    (state, detection-hash, code-hash, suffix). Returns ParseResult.indicators
    (the serialized NormalizedStandard list). The code hash is what makes a
    prompt edit invalidate the cache rather than silently replay the previous
    run's output — see ``eval_common.code_version_hash``."""
    detection = json.loads(detection_path.read_text())
    # A detection file is either {"elements": [...]} (pipeline output) or a bare
    # element list (e.g. the detector eval's *-detected.json). Handle both.
    elements_data = detection if isinstance(detection, list) else detection.get("elements", [])

    cache_key = (
        f"parser-{state}-{_hash_blocks(elements_data, text_key='source_text')}-"
        f"{code_version_hash()}-{cache_suffix}.json"
    )
    cache_path = CACHE_DIR / cache_key
    if use_cache and cache_path.exists():
        logger.info(f"  [cache hit] {cache_path.name}")
        return json.loads(cache_path.read_text())

    elements = [DetectedElement(**e) for e in elements_data]
    logger.info(f"  [parser] running on {len(elements)} detected elements…")
    result = parse_hierarchy(
        elements=elements,
        country=country,
        state=state,
        version_year=version_year,
        age_band=default_age_band,
    )
    indicators = result.indicators
    logger.info(
        f"  [parser] produced {len(indicators)} standards (status={result.status}"
        + (f", error={result.error}" if result.error else "") + ")"
    )
    cache_path.write_text(json.dumps(indicators, indent=2, default=str, ensure_ascii=False))
    # Return the same shape a cache hit would (see eval_common.as_plain_json).
    return as_plain_json(indicators)


# ---------- matching ----------

def _indicator_name(std: dict) -> str:
    ind = std.get("indicator")
    return _norm((ind or {}).get("name") if isinstance(ind, dict) else None)


# A proficiency-column disambiguator is an ALL-CAPS trailing code segment
# (e.g. DISC/DEVE/BROA from Discovering/Developing/Broadening). Scoped to
# uppercase ≥2-letter tokens so it does NOT fire on lettered indicators
# ("…1.1.a") or junk codes ("C3a") — those stay distinguished by name.
_VARIANT_SUFFIX_RE = re.compile(r"^[A-Z]{2,}$")


def _variant_suffix(std: dict) -> Optional[str]:
    """Trailing code segment that separates side-by-side column variants which
    share a name AND age_band — i.e. proficiency levels like
    ELD.1.0.VOC.1.1.DISC vs .DEVE vs .BROA (all "Understanding Words", all
    36-66). Returns the suffix only when it's an all-caps label; age-distinguished
    variants (Early/Later) are already separated by age_band, so their numeric
    "…36-54" suffix is intentionally ignored here.

    TIE-BREAKER ONLY — never part of `_match_key`. See that docstring for why."""
    ind = std.get("indicator")
    code = (ind or {}).get("code") if isinstance(ind, dict) else None
    if not code or "." not in code:
        return None
    last = code.rsplit(".", 1)[-1]
    return last if _VARIANT_SUFFIX_RE.match(last) else None


def _match_key(std: dict) -> Tuple[str, Optional[str]]:
    """Identity of a standard for matching: (normalized indicator name,
    canonicalized age_band).

    The age band is folded via `_norm_age_band` so the unicode-'½' vs ASCII-'1/2'
    glyph split documented in eval_common can't turn a produced standard into a
    spurious "dropped" — which would otherwise hide EVERY other field comparison
    for that standard. This is identity/pairing only; the graded fields are still
    compared strictly via `_norm_val` below.

    ⚠️ THE IDENTITY MUST NOT BE DERIVED FROM THE CODE (repaired 2026-08-16,
    arXiv paper Task 2). `_variant_suffix` used to be a third key component, so a
    standard whose code came out MALFORMED could not pair with its golden at all
    and reported as `dropped` — which silently removes it from `field_stats`, and
    therefore from `field_accuracy`, instead of grading it as the wrong code it
    is. Kentucky is the live case: the parser emitted bare `TCPHS` / `IHFC` /
    `PARTO` / `PSGPB` where the golden has `HMW.1.1.TCPHS` etc., so the golden
    side keyed on suffix 'TCPHS' and the parsed side on None. The suite reported
    coverage 0.846 with field accuracy **1.000** — a perfect score that existed
    only because the four malformed rows had been excluded from the denominator.
    A metric must never be able to hide a defect by failing to pair.

    The suffix still does its job (separating CA/TX proficiency columns that
    share a name AND an age_band), but as a TIE-BREAKER inside `grade_parser`,
    applied only when more than one candidate shares this key — which is the
    condition its own docstring describes. `measure_stability` keys on this too,
    and gains the same property: a run-to-run code change now counts as a field
    disagreement (`_sig` covers `indicator.code` and `standard_id`) rather than
    dropping the element out of the comparison unseen."""
    return (
        _indicator_name(std),
        _norm_age_band(std.get("age_band")),
    )


def _index_standards(standards: List[dict]) -> Dict[Tuple[str, Optional[str]], List[dict]]:
    idx: Dict[Tuple[str, Optional[str]], List[dict]] = defaultdict(list)
    for s in standards:
        idx[_match_key(s)].append(s)
    return idx


# ---------- metrics ----------

@dataclass
class ParserStateReport:
    state: str
    n_golden: int = 0
    n_parsed: int = 0
    matched: int = 0

    dropped: List[str] = field(default_factory=list)        # golden test_case_ids
    duplicated: List[str] = field(default_factory=list)     # golden id matching >1 standard
    id_collisions: List[str] = field(default_factory=list)  # duplicate standard_ids in output

    # dotted field path -> {"ok": n, "total": n}
    field_stats: Dict[str, Dict[str, int]] = field(
        default_factory=lambda: defaultdict(lambda: {"ok": 0, "total": 0})
    )
    mismatches: List[dict] = field(default_factory=list)    # {test_case_id, field, expected, got}

    regressions: List[Tuple[str, str, str]] = field(default_factory=list)

    matched_pairs: List[Tuple[dict, dict]] = field(default_factory=list)  # (golden_entry, parsed)
    dropped_full: List[dict] = field(default_factory=list)

    stability_runs: int = 0
    stability_disagreement_rate: Optional[float] = None
    stability_size_stdev: Optional[float] = None

    @property
    def coverage(self) -> float:
        return self.matched / self.n_golden if self.n_golden else 0.0

    @property
    def field_accuracy(self) -> float:
        ok = sum(s["ok"] for s in self.field_stats.values())
        total = sum(s["total"] for s in self.field_stats.values())
        return ok / total if total else 0.0

    @property
    def standards_all_fields_ok(self) -> int:
        """Matched standards with zero field mismatches."""
        bad = {m["test_case_id"] for m in self.mismatches}
        return sum(1 for g, _ in self.matched_pairs if g.get("test_case_id") not in bad)


def grade_parser(golden: dict, standards: List[dict]) -> ParserStateReport:
    rep = ParserStateReport(state=golden.get("state", ""))
    golden_stds = golden.get("standards", [])
    rep.n_golden = len(golden_stds)
    rep.n_parsed = len(standards)

    index = _index_standards(standards)
    matched_ids: set = set()

    for g in golden_stds:
        gid = g.get("test_case_id", "?")
        expected = g.get("expected") or {}
        # Reuse _match_key so the golden side and the parsed side can never drift.
        key = _match_key(expected)
        cands = [c for c in index.get(key, []) if id(c) not in matched_ids]

        # Proficiency-column tie-break. Only meaningful when several candidates
        # share (name, age_band) — the exact condition `_variant_suffix`
        # describes. Narrowing here rather than in the key means a MALFORMED code
        # can no longer stop a standard from pairing (see `_match_key`): if no
        # candidate carries the golden's suffix we keep them all and let the
        # field comparison report the wrong code, which is the honest outcome.
        if len(cands) > 1:
            want = _variant_suffix(expected)
            exact = [c for c in cands if _variant_suffix(c) == want]
            if exact:
                cands = exact

        if not cands:
            rep.dropped.append(gid)
            rep.dropped_full.append(g)
            continue
        if len(cands) > 1:
            rep.duplicated.append(gid)
        d = cands[0]
        matched_ids.add(id(d))
        rep.matched += 1
        rep.matched_pairs.append((g, d))

        # Grade every field of the NormalizedStandard.
        for path in FIELD_PATHS:
            exp = _norm_val(_get_path(expected, path))
            got = _norm_val(_get_path(d, path))
            rep.field_stats[path]["total"] += 1
            if exp == got:
                rep.field_stats[path]["ok"] += 1
            else:
                rep.mismatches.append(
                    {"test_case_id": gid, "field": path, "expected": exp, "got": got}
                )

    # Global standard_id uniqueness across the whole parser output.
    seen: set = set()
    for s in standards:
        sid = s.get("standard_id")
        if sid in seen:
            rep.id_collisions.append(sid)
        seen.add(sid)

    return rep


# ---------- stability ----------

def measure_stability(
    state: str,
    detection_path: Path,
    country: str,
    version_year: int,
    default_age_band: str,
    runs: int,
) -> Tuple[float, float]:
    """Rerun the parser `runs` times on the same frozen detection input; report
    the per-standard field-disagreement rate and output-size stdev. A standard's
    identity is (indicator name, age_band); the compared signature is every
    graded field."""
    import statistics

    def _sig(s: dict) -> Tuple:
        return tuple(_norm_val(_get_path(s, p)) for p in FIELD_PATHS)

    outputs: List[List[dict]] = []
    for i in range(runs):
        outputs.append(
            run_parser_cached(
                state, detection_path, country, version_year, default_age_band,
                use_cache=False, cache_suffix=f"stab-{i}",
            )
        )

    sizes = [len(o) for o in outputs]
    size_stdev = statistics.pstdev(sizes) if len(sizes) > 1 else 0.0

    base = {_match_key(s): _sig(s) for s in outputs[0]}
    disagreements = compared = 0
    for other in outputs[1:]:
        omap = {_match_key(s): _sig(s) for s in other}
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
    country = golden.get("country", "US")
    version_year = golden.get("version_year", 0)
    # The document-wide age band is production metadata supplied to the parser
    # (handlers.py passes event["age_band"]). For docs whose indicators carry no
    # per-indicator age band (e.g. AZ/CO preschool, 36-60), the golden records it
    # as `default_age_band` so the eval feeds the parser the same value production
    # would. A CLI --default-age-band still acts as the cross-state fallback.
    default_age_band = golden.get("default_age_band", default_age_band)

    standards = run_parser_cached(
        state, detection_path, country, version_year, default_age_band, use_cache=use_cache
    )
    rep = grade_parser(golden, standards)
    rep.state = state
    rep.regressions = run_regressions(golden, standards, regression_checks.lookup_parser)

    if stability_runs > 1:
        rep.stability_runs = stability_runs
        rep.stability_disagreement_rate, rep.stability_size_stdev = measure_stability(
            state, detection_path, country, version_year, default_age_band, stability_runs
        )

    return rep, standards


def render_report(rep: ParserStateReport) -> str:
    out = []
    out.append(f"\n=== {rep.state} ===")
    out.append(f"  golden standards: {rep.n_golden}")
    out.append(f"  parsed:           {rep.n_parsed}")
    out.append(f"  matched:          {rep.matched}  (coverage {rep.coverage:.3f})")
    out.append(f"  fully correct:    {rep.standards_all_fields_ok}/{rep.matched}")
    out.append(f"  field accuracy:   {rep.field_accuracy:.3f}")

    out.append("  per-field (ok/total) — only fields with a mismatch shown:")
    any_mismatch = False
    for path in FIELD_PATHS:
        s = rep.field_stats.get(path)
        if not s or s["total"] == 0:
            continue
        if s["ok"] == s["total"]:
            continue
        any_mismatch = True
        acc = s["ok"] / s["total"]
        out.append(f"    {path:<22} {s['ok']:>3}/{s['total']:<3} ({acc:.2f})  ← MISMATCH")
    if not any_mismatch:
        out.append("    (all graded fields matched)")

    if rep.dropped:
        out.append(f"  dropped ({len(rep.dropped)}): {rep.dropped[:10]}{'…' if len(rep.dropped) > 10 else ''}")
    else:
        out.append("  dropped: 0")
    if rep.duplicated:
        out.append(f"  duplicated ({len(rep.duplicated)}): {rep.duplicated[:10]}")
    if rep.id_collisions:
        uniq = sorted(set(rep.id_collisions))
        out.append(f"  standard_id collisions ({len(rep.id_collisions)}): {uniq[:5]}{'…' if len(uniq) > 5 else ''}")
    else:
        out.append("  standard_id collisions: 0")

    if rep.mismatches:
        out.append(f"  field mismatches ({len(rep.mismatches)}):")
        for m in rep.mismatches[:15]:
            out.append(f"    {m['test_case_id']} {m['field']}: expected {m['expected']!r} got {m['got']!r}")
        if len(rep.mismatches) > 15:
            out.append(f"    … and {len(rep.mismatches) - 15} more")

    out.append("  regression cases:")
    for cid, status, detail in rep.regressions:
        out.append(f"    [{status}] {cid} — {detail}")

    if rep.stability_runs > 1:
        out.append(f"  stability ({rep.stability_runs} runs):")
        out.append(f"    field disagreement rate: {rep.stability_disagreement_rate:.3f}")
        out.append(f"    output size stdev:       {rep.stability_size_stdev:.2f}")

    return "\n".join(out)


def write_review_dir(rep: ParserStateReport, standards: List[dict], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    state = rep.state

    (output_dir / f"{state}-report.txt").write_text(render_report(rep))
    (output_dir / f"{state}-parsed.json").write_text(
        json.dumps(standards, indent=2, default=str, ensure_ascii=False)
    )

    review = {
        "state": state,
        "summary": {
            "golden_standards": rep.n_golden,
            "parsed": rep.n_parsed,
            "matched": rep.matched,
            "fully_correct": rep.standards_all_fields_ok,
            "coverage": round(rep.coverage, 4),
            "field_accuracy": round(rep.field_accuracy, 4),
            "dropped": len(rep.dropped),
            "duplicated": len(rep.duplicated),
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
    parser.add_argument("--golden-dir", default="evaluation/ground_truth_parser", help="Directory holding {STATE}.json parser golden sets")
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
            rep, standards = evaluate_state(
                st, det_path, gold_path,
                default_age_band=args.default_age_band,
                use_cache=not args.no_cache,
                stability_runs=args.stability_runs,
            )
            reports.append(rep)
            if output_dir:
                write_review_dir(rep, standards, output_dir / st)
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
                "fully_correct": r.standards_all_fields_ok,
                "n_golden": r.n_golden,
                "n_parsed": r.n_parsed,
                "dropped": r.dropped,
                "duplicated": r.duplicated,
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
