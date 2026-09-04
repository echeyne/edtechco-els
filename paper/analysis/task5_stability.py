#!/usr/bin/env python3
"""Run stability / determinism table for both suites (arXiv paper Task 5).

Reads the per-run aggregate reports and raw per-run outputs of N repeated
evaluation runs of the SAME pipeline against the SAME frozen inputs
(``--no-cache``, so each run is a genuinely independent LLM call), and reports
how much the graded output moves from run to run.

This exists because a previous stability instrument
(``evaluation.eval_detector.measure_stability`` / ``eval_parser.measure_stability``,
before their 2026-08-23 repair) reported a confident ``0.000`` disagreement rate
for an invocation whose graded output carried four malformed primary keys, in
the same run. It did that by combining four independent blind spots. This
script must be provably free of all four -- see ``self_check()`` at the bottom,
which is also runnable with no input files present via ``--self-check``.

  1. A field under test must never be part of the identity key. The retired
     code keyed elements on ``(code, title)`` and compared ``level``, so a
     changed CODE -- the exact defect it existed to catch -- produced a
     different key, failed the membership test, and silently dropped out of
     the comparison instead of counting as instability.

     Here: detector identity is the normalized TITLE only. Parser identity is
     the normalized INDICATOR NAME only. ``standard_id`` and every code
     (including ``indicator.code``) are COMPARED FIELDS, never identity.

  2. Presence and multiplicity are compared, not just matched pairs. An item
     present in one run and absent in another counts as instability rather
     than vanishing into a bare size statistic. A title/name can legitimately
     repeat (some documents reprint headings, or print several age-band /
     proficiency columns under one name), so the COUNT per identity is
     compared across runs, not just set membership.

  3. Denominators and ranges are reported, never a bare rate. "5 runs, 0
     disagreements" and "1 of 6 runs differed in 8 cells" can both be
     summarized as a single number, and only one of those summaries is
     informative. This script always emits observation counts, output-size
     range, identities compared, distinct unstable identities, and how many
     observations differ from the first (run 1).

  4. The headline rate counts DISTINCT unstable identities and is bounded
     [0, 1]. The retired code summed per-dimension counters, so one title
     unstable in level, code, and description counted three times against a
     denominator of one, producing a "rate" of 2.000. Here ``disagreement_rate``
     is ``n_distinct_unstable_identities / n_identities_compared``; the
     per-dimension counts are reported SEPARATELY as
     ``n_dimension_disagreements`` and are explicitly not a rate.

Inputs (see ``--results-dir``, default ``paper/results/task5_20260830``):
  - ``reports/{suite}_run{N}_{STATE}.json`` -- a JSON list with one aggregate
    report dict (as produced by ``eval_detector``/``eval_parser --report-json``).
  - ``review/{suite}_run{N}/{STATE}/{STATE}-detected.json`` (detector) or
    ``{STATE}-parsed.json`` (parser) -- the raw per-run element/standard list
    that element-level comparison actually runs over.

Refusals (loud, matching ``paper/analysis/ablation_stability.py``'s example):
  - A run whose report shows zero detected/parsed items is a run that FAILED
    (throttle or infrastructure error) and was not measured. Averaging it in
    would invent catastrophic instability out of an outage. The script exits
    with a clear message naming the offending file.
  - Two reports for the same state whose ``n_golden`` disagree means the
    golden changed mid-sweep; refused the same way.
  - Files named ``INVALID_*`` are skipped (the convention this repo already
    uses to mark a run as known-bad without deleting the evidence).
  - A state with fewer than 2 usable observations is reported as
    NOT_MEASURABLE, not as stable -- there is nothing to compare yet.
"""
import argparse
import json
import pathlib
import re
import sys
import collections
from collections import defaultdict

# ---------------------------------------------------------------------------
# identity / field normalization
# ---------------------------------------------------------------------------


def norm_identity(s):
    """Identity-key normalization: collapse internal whitespace, strip,
    casefold. Nothing else -- deliberately conservative, since this value
    decides whether two elements from different runs are "the same element".
    Over-normalizing here (e.g. stripping punctuation) would let unrelated
    elements collide; under-normalizing would fail to pair the same element
    across runs on trivial whitespace/case drift."""
    if not s:
        return ""
    return " ".join(str(s).casefold().split())


def norm_field(v):
    """Comparison-value normalization for a COMPARED (non-identity) field:
    fold blank/whitespace-only strings and None together (this schema spells
    absence one way, but the pipeline has historically emitted both -- see
    ``models._blank_to_none`` in the main codebase), and collapse internal
    whitespace so line-wrap/typesetting noise doesn't masquerade as content
    instability. Case is preserved: a code's case is part of its content
    (the abbreviation scheme is upper-case by rule), and a description's
    case obviously matters."""
    if v is None:
        return None
    if isinstance(v, str):
        v2 = " ".join(v.split())
        return v2 if v2 else None
    return v


def get_path(obj, path):
    """Read a dotted path (``"domain.code"``) or a flat key (``"level"``)
    from a dict. A null/missing nested level yields None for its subfields."""
    if "." not in path:
        return obj.get(path)
    head, sub = path.split(".", 1)
    level = obj.get(head)
    if not isinstance(level, dict):
        return None
    return level.get(sub)


# ---------------------------------------------------------------------------
# suite-specific identity / compared-field / sort-key definitions
# ---------------------------------------------------------------------------

DETECTOR_COMPARED_FIELDS = ["level", "code", "description", "age_band", "source_page"]

PARSER_SCALAR_FIELDS = [
    "standard_id", "country", "state", "version_year", "age_band", "source_page",
]
PARSER_LEVELS = ["domain", "strand", "sub_strand", "indicator"]
PARSER_LEVEL_SUBFIELDS = ["code", "name", "description"]
PARSER_COMPARED_FIELDS = list(PARSER_SCALAR_FIELDS) + [
    f"{lvl}.{sub}" for lvl in PARSER_LEVELS for sub in PARSER_LEVEL_SUBFIELDS
]


def detector_identity(e):
    return norm_identity(e.get("title"))


def detector_getter(e, field):
    return norm_field(e.get(field))


def detector_sort_key(e):
    """Deterministic within-identity ordering so that when a title legitimately
    repeats (N occurrences in every run), occurrence i in run A is compared
    against occurrence i in run B by something more meaningful than raw list
    order, which is an accident of chunk/batch scheduling rather than
    document structure.

    ⚠️ FIXED 2026-08-30 on review. This previously sorted by ``level`` and
    ``code`` -- both COMPARED FIELDS. That is the identity-key bug this whole
    script exists to avoid, displaced one level down: if a repeated title's
    code changes between runs, sorting by code REORDERS the occurrences, and
    occurrence i in run A is then compared against a different physical element
    in run B. That can mask a real disagreement and manufacture a spurious one
    at the same time. ``parser_sort_key``'s docstring already argued exactly
    this; the detector key contradicted it.

    Sort only on facts READ OFF THE PAGE, never on a classification decision.
    ``source_text`` is the verbatim span the element was extracted from and
    ``source_page`` is where it sits; neither is a pipeline judgement. This
    also happens to fix the CA domain-scoping gap noted at review time: ELD and
    FLD share strand/sub_strand TITLES, so they collide under a title-only
    identity, but they carry different source_text and different pages, so they
    order deterministically and pair correctly."""
    sp = e.get("source_page")
    return (norm_field(e.get("source_text")) or "",
            sp if isinstance(sp, (int, float)) else -1)


def parser_identity(s):
    ind = s.get("indicator")
    name = (ind or {}).get("name") if isinstance(ind, dict) else None
    return norm_identity(name)


def parser_getter(s, field):
    return norm_field(get_path(s, field))


def parser_sort_key(s):
    """Same rationale as ``detector_sort_key``. Deliberately does NOT use
    ``indicator.code`` or ``standard_id`` as the primary sort key even though
    they are usually distinguishing, precisely because they are the fields
    most under test here -- sorting by the thing you are measuring for
    stability would rearrange occurrences differently across an unstable run,
    which is a second-order version of the same identity-key bug this script
    exists to avoid. age_band and source_page are page-layout facts, not
    pipeline output, so they are safe to sort by."""
    sp = s.get("source_page")
    return (
        str(norm_field(s.get("age_band"))),
        sp if isinstance(sp, (int, float)) else -1,
        str(get_path(s, "indicator.code")),
    )


# ---------------------------------------------------------------------------
# core comparison (suite-agnostic)
# ---------------------------------------------------------------------------


def compute_stability(observations, labels, identity_fn, compared_fields, getter,
                       sort_key, max_examples=20):
    """Compare N observations (each a list of item-dicts) of the same frozen
    input under the same pipeline, and report how much they disagree.

    Returns a dict. See the module docstring for the four properties this is
    designed to guarantee: field-not-in-key, presence/multiplicity compared,
    denominators reported, and a bounded [0,1] rate over DISTINCT identities.
    """
    assert len(observations) == len(labels) and len(observations) >= 1

    sizes = [len(o) for o in observations]

    per_run_groups = []
    for obs in observations:
        g = defaultdict(list)
        for item in obs:
            g[identity_fn(item)].append(item)
        for k in g:
            g[k].sort(key=sort_key)
        per_run_groups.append(g)

    all_ids = sorted({k for g in per_run_groups for k in g})
    field_disagreements = {f: 0 for f in compared_fields}
    presence_or_multiplicity = 0
    unstable_ids = set()
    examples = []

    def _add_example(ident, dimension, detail, occurrence_index=None):
        if len(examples) >= max_examples:
            return
        ex = {"identity": ident[:120], "dimension": dimension, "detail": detail}
        if occurrence_index is not None:
            ex["occurrence_index"] = occurrence_index
        examples.append(ex)

    for ident in all_ids:
        present = [ident in g for g in per_run_groups]
        if not all(present):
            presence_or_multiplicity += 1
            unstable_ids.add(ident)
            _add_example(ident, "presence",
                         {labels[i]: ("present" if p else "MISSING") for i, p in enumerate(present)})
            continue

        counts = [len(g[ident]) for g in per_run_groups]
        if len(set(counts)) > 1:
            presence_or_multiplicity += 1
            unstable_ids.add(ident)
            _add_example(ident, "multiplicity",
                         {labels[i]: c for i, c in enumerate(counts)})
            continue

        # ⚠️ MULTISET, not positional. Changed 2026-08-30 on review.
        #
        # An identity can legitimately occur more than once, and when it does,
        # the occurrences frequently cannot be told apart by ANY document fact.
        # Measured on the real CA parser output: 94 standards collapse to 33
        # distinct indicator names, and 32 occurrences are separated by no
        # combination of age_band, source_page and source_text -- CA prints the
        # same foundation once per proficiency column, so the columns differ
        # ONLY in indicator.code, which is the field under test.
        #
        # Pairing occurrence i to occurrence i after sorting therefore requires
        # sorting by a field under test. That does not MASK a change (a drift
        # still shows up) but it INFLATES one: if a code drifts across the sort
        # boundary the occurrences swap, so one changed code reports as two code
        # disagreements plus spurious description/standard_id ones. The paper
        # quotes magnitudes, and CA is 94 of the corpus's 262 standards, so the
        # inflation is not negligible.
        #
        # Comparing the MULTISET of each field's values across the group is
        # order-insensitive, needs no tie-break, and is exactly equivalent to
        # direct comparison when multiplicity is 1. A pure reordering (chunk
        # scheduling noise) correctly counts as zero; a genuinely changed value
        # correctly counts as one.
        item_unstable = False
        for f in compared_fields:
            per_run_counter = [
                collections.Counter(str(getter(it, f)) for it in g[ident])
                for g in per_run_groups
            ]
            base = per_run_counter[0]
            if any(c != base for c in per_run_counter[1:]):
                # number of occurrences whose value changed, not the number of
                # distinct values involved: {A,B} -> {B,Z} is ONE change.
                worst = 0
                for other in per_run_counter[1:]:
                    keys = set(base) | set(other)
                    delta = sum(abs(base.get(k, 0) - other.get(k, 0)) for k in keys) // 2
                    worst = max(worst, delta)
                field_disagreements[f] += worst
                item_unstable = True
                _add_example(ident, f,
                             {labels[i]: sorted(c.elements())
                              for i, c in enumerate(per_run_counter)})
        if item_unstable:
            unstable_ids.add(ident)

    n_ids = len(all_ids)
    n_unstable = len(unstable_ids)  # DISTINCT identities -> rate is bounded [0, 1]
    rate = (n_unstable / n_ids) if n_ids else 0.0

    runs_differing_from_run1 = None
    if len(observations) > 1:
        base = per_run_groups[0]
        runs_differing_from_run1 = 0
        for other in per_run_groups[1:]:
            differs = set(base) != set(other)
            if not differs:
                for k in base:
                    if len(base[k]) != len(other[k]):
                        differs = True
                        break
                    for f in compared_fields:
                        if (collections.Counter(str(getter(it, f)) for it in base[k])
                                != collections.Counter(str(getter(it, f)) for it in other[k])):
                            differs = True
                            break
                    if differs:
                        break
            if differs:
                runs_differing_from_run1 += 1

    return {
        "n_observations": len(observations),
        "observation_labels": list(labels),
        "size_by_observation": sizes,
        "size_range": [min(sizes), max(sizes)] if sizes else None,
        "n_identities_compared": n_ids,
        "n_distinct_unstable_identities": n_unstable,
        "disagreement_rate": round(rate, 6),
        "n_dimension_disagreements": {
            "presence_or_multiplicity": presence_or_multiplicity,
            **field_disagreements,
        },
        "n_observations_differing_from_run1": runs_differing_from_run1,
        "examples": examples,
    }


INTERPRETATION_WARNING = (
    "A disagreement_rate of 0.000 at small N is NOT evidence of determinism. "
    "A defect that fires in a minority of runs (the malformed-code defect this "
    "instrument was built to catch fired in roughly 1 of 6 KY parser runs in "
    "earlier evidence) can easily produce several clean observations in a row. "
    "This measurement is a LOWER BOUND on true run-to-run variance, not an "
    "estimate of it -- read the denominators (n_identities_compared, "
    "n_observations) alongside the rate, never the rate alone."
)

# ---------------------------------------------------------------------------
# loading real report / raw files
# ---------------------------------------------------------------------------

REPORT_RE = re.compile(r"^(detector|parser)_run(\d+)_([A-Za-z0-9]+)\.json$")
N_KEY = {"detector": "n_detected", "parser": "n_parsed"}
RAW_SUFFIX = {"detector": "detected", "parser": "parsed"}


def _refuse(msg):
    raise SystemExit(f"REFUSING: {msg}")


def _pick_report_entry(reports_list, state, report_path):
    if not reports_list:
        _refuse(f"{report_path} contains an empty JSON list.")
    matches = [r for r in reports_list if r.get("state") == state]
    if len(matches) == 1:
        return matches[0]
    if not matches and len(reports_list) == 1:
        return reports_list[0]
    _refuse(
        f"{report_path}: expected exactly one report entry for state {state!r}, "
        f"found {len(matches)} matching of {len(reports_list)} total. Ambiguous -- "
        "cannot tell which entry this run graded."
    )


def load_frozen_parser(paths, review_dirs):
    """Fold an ALREADY-RECORDED parser arm in as observation 0.

    The Task 1/2 re-records of 2026-08-29 ran the parser at the SAME
    code_version_hash (14374dba), on the SAME frozen detections
    (outputs/08-26-26-2), with --no-cache, across all six states. They are
    therefore observations of exactly the configuration this sweep measures,
    and they cost nothing -- those runs already happened. This is the same
    argument that repaired eval_detector.measure_stability, whose central
    defect was excluding the run it had actually graded.

    They also land on a DIFFERENT DAY from this sweep, which is what Task 5's
    blocker 2 asks for: July's finding was that same-session runs agree while a
    24h-separated run differs.

    ⚠️ PARSER ONLY. The detector arms of those same recordings were produced at
    7da92182, a different hash, so folding them into detector stability would
    silently compare two code versions and report a code change as run-to-run
    variance. Do not add a --frozen-detector option.
    """
    obs = collections.defaultdict(list)
    for rpt_path, review_dir in zip(paths, review_dirs):
        rpt_path, review_dir = pathlib.Path(rpt_path), pathlib.Path(review_dir)
        for entry in json.loads(rpt_path.read_text()):
            state = entry.get("state")
            raw = review_dir / state / f"{state}-parsed.json"
            if not raw.exists():
                print(f"  frozen: no raw output at {raw}; skipping {state}.", file=sys.stderr)
                continue
            items = json.loads(raw.read_text())
            if not items:
                _refuse(f"{raw} is empty. A zero-item run was not measured.")
            obs[state].append({"run": 0, "label": f"frozen({rpt_path.parent.name})",
                               "n_golden": entry.get("n_golden"), "items": items})
    return obs


def load_suite(suite, results_dir):
    """Returns observations[state] -> list of {"run": int, "label": str,
    "n_golden": int, "items": [dict, ...]} sorted by run number, having
    already refused on zero-item runs and cross-run n_golden mismatches."""
    reports_dir = results_dir / "reports"
    review_dir = results_dir / "review"
    n_key = N_KEY[suite]
    raw_suffix = RAW_SUFFIX[suite]

    by_state = defaultdict(list)
    n_golden_by_state = {}

    if not reports_dir.is_dir():
        return by_state

    for f in sorted(reports_dir.iterdir()):
        if f.name.startswith("INVALID_"):
            print(f"  [skip] {f.name} (INVALID_ prefix)", file=sys.stderr)
            continue
        m = REPORT_RE.match(f.name)
        if not m or m.group(1) != suite:
            continue
        run_n, state = int(m.group(2)), m.group(3)

        try:
            reports_list = json.loads(f.read_text())
        except json.JSONDecodeError as e:
            _refuse(f"{f} is not valid JSON ({e}).")
        entry = _pick_report_entry(reports_list, state, f)

        n_items_reported = entry.get(n_key, 0)
        if not n_items_reported:
            _refuse(
                f"{f} (state {state}, run {run_n}) has {n_key}=={n_items_reported!r}. "
                "That run FAILED (throttle or error) and was not measured. Averaging "
                "it in would invent catastrophic instability out of an infrastructure "
                "failure. Rename it INVALID_* or delete it, then re-run."
            )

        n_golden = entry.get("n_golden")
        if state in n_golden_by_state and n_golden_by_state[state] != n_golden:
            _refuse(
                f"{f} (state {state}, run {run_n}) reports n_golden={n_golden!r}, but "
                f"an earlier run for {state} reported n_golden={n_golden_by_state[state]!r}. "
                "The golden set changed mid-sweep -- these runs are not comparable."
            )
        n_golden_by_state[state] = n_golden

        raw_path = review_dir / f"{suite}_run{run_n}" / state / f"{state}-{raw_suffix}.json"
        if not raw_path.is_file():
            print(
                f"  [skip] {f}: report exists but raw file {raw_path} is missing "
                "(run likely still in flight) -- excluding this run from element-level comparison.",
                file=sys.stderr,
            )
            continue
        try:
            items = json.loads(raw_path.read_text())
        except json.JSONDecodeError as e:
            _refuse(f"{raw_path} is not valid JSON ({e}).")
        if not isinstance(items, list):
            items = items.get("elements") or items.get("indicators") or []
        if not items:
            _refuse(
                f"{raw_path} (state {state}, run {run_n}) contains zero items, but its "
                f"report ({f}) claims {n_key}={n_items_reported}. Inconsistent and unsafe "
                "to trust either number for this run."
            )
        if len(items) != n_items_reported:
            print(
                f"  [warn] {raw_path}: {len(items)} raw items vs report's "
                f"{n_key}={n_items_reported} for {state} run {run_n} -- using the raw count.",
                file=sys.stderr,
            )

        by_state[state].append({
            "run": run_n, "label": f"run{run_n}", "n_golden": n_golden, "items": items,
        })

    for state in by_state:
        by_state[state].sort(key=lambda r: r["run"])

    return by_state


# ---------------------------------------------------------------------------
# orchestration
# ---------------------------------------------------------------------------


def summarize_suite(suite, by_state, max_examples):
    identity_fn, compared_fields, getter, sort_key = {
        "detector": (detector_identity, DETECTOR_COMPARED_FIELDS, detector_getter, detector_sort_key),
        "parser": (parser_identity, PARSER_COMPARED_FIELDS, parser_getter, parser_sort_key),
    }[suite]

    per_state = {}
    pooled_compared = pooled_unstable = 0
    pooled_dims = defaultdict(int)

    for state in sorted(by_state):
        obs_records = by_state[state]
        n_obs = len(obs_records)
        if n_obs < 2:
            per_state[state] = {
                "status": "NOT_MEASURABLE",
                "reason": f"only {n_obs} usable observation(s); need >= 2 to compare.",
                "n_observations": n_obs,
                "run_labels": [r["label"] for r in obs_records],
                "size_by_observation": [len(r["items"]) for r in obs_records],
            }
            continue

        result = compute_stability(
            observations=[r["items"] for r in obs_records],
            labels=[r["label"] for r in obs_records],
            identity_fn=identity_fn,
            compared_fields=compared_fields,
            getter=getter,
            sort_key=sort_key,
            max_examples=max_examples,
        )
        result["status"] = "MEASURED"
        result["interpretation_warning"] = INTERPRETATION_WARNING
        per_state[state] = result

        pooled_compared += result["n_identities_compared"]
        pooled_unstable += result["n_distinct_unstable_identities"]
        for k, v in result["n_dimension_disagreements"].items():
            pooled_dims[k] += v

    measured_states = [s for s, r in per_state.items() if r["status"] == "MEASURED"]
    pooled = {
        "n_states_measured": len(measured_states),
        "n_states_not_measurable": len(per_state) - len(measured_states),
        "states_measured": sorted(measured_states),
        "states_not_measurable": sorted(s for s in per_state if s not in measured_states),
        "n_identities_compared": pooled_compared,
        "n_distinct_unstable_identities": pooled_unstable,
        "disagreement_rate": round(pooled_unstable / pooled_compared, 6) if pooled_compared else None,
        "n_dimension_disagreements": dict(pooled_dims),
        "interpretation_warning": INTERPRETATION_WARNING,
    }

    return {"per_state": per_state, "corpus": pooled}


def render_text_summary(out):
    lines = []
    for suite in ("detector", "parser"):
        if suite not in out["suites"]:
            continue
        s = out["suites"][suite]
        lines.append(f"\n=== {suite.upper()} ===")
        for state, r in sorted(s["per_state"].items()):
            if r["status"] == "NOT_MEASURABLE":
                lines.append(
                    f"  {state}: NOT MEASURABLE ({r['reason']})"
                )
                continue
            lines.append(
                f"  {state}: n_observations={r['n_observations']} "
                f"(runs {r['observation_labels']}), "
                f"size_by_observation={r['size_by_observation']} range={r['size_range']}, "
                f"n_identities_compared={r['n_identities_compared']}, "
                f"n_distinct_unstable={r['n_distinct_unstable_identities']}, "
                f"disagreement_rate={r['disagreement_rate']:.4f}, "
                f"observations_differing_from_run1={r['n_observations_differing_from_run1']}"
            )
            nonzero_dims = {k: v for k, v in r["n_dimension_disagreements"].items() if v}
            if nonzero_dims:
                lines.append(f"      per-dimension disagreements: {nonzero_dims}")
        c = s["corpus"]
        lines.append(
            f"  CORPUS: states measured={c['n_states_measured']} "
            f"({c['states_measured']}), not measurable={c['states_not_measurable']}, "
            f"n_identities_compared={c['n_identities_compared']}, "
            f"n_distinct_unstable={c['n_distinct_unstable_identities']}, "
            f"disagreement_rate={c['disagreement_rate']}"
        )
        if c["n_dimension_disagreements"]:
            nonzero = {k: v for k, v in c["n_dimension_disagreements"].items() if v}
            lines.append(f"      pooled per-dimension disagreements: {nonzero}")
    lines.append(f"\n{out['interpretation_warning']}")
    return "\n".join(lines)


def main_real(args):
    results_dir = pathlib.Path(args.results_dir)
    out = {
        "results_dir": str(results_dir),
        "suites": {},
        "interpretation_warning": INTERPRETATION_WARNING,
    }
    for suite in ("detector", "parser"):
        print(f"Loading {suite} runs from {results_dir} ...", file=sys.stderr)
        by_state = load_suite(suite, results_dir)
        if suite == "parser" and args.frozen_parser:
            frozen = load_frozen_parser(args.frozen_parser, args.frozen_parser_review)
            for st, obs in frozen.items():
                by_state.setdefault(st, []).extend(obs)
            for st in by_state:
                by_state[st].sort(key=lambda r: r["run"])
        if not by_state:
            print(f"  no {suite} report files found.", file=sys.stderr)
            continue
        out["suites"][suite] = summarize_suite(suite, by_state, args.max_examples)

    text = render_text_summary(out)
    print(text)

    if args.out:
        args.out.write_text(json.dumps(out, indent=2, default=str))
        print(f"\nWrote {args.out}")
    return out


# ---------------------------------------------------------------------------
# self-check: proves the four blind spots are absent, no input files needed
# ---------------------------------------------------------------------------


def self_check():
    failures = []

    def check(name, cond):
        status = "PASS" if cond else "FAIL"
        print(f"  [{status}] {name}")
        if not cond:
            failures.append(name)

    # (a) a CODE change between runs is counted as unstable, not silently
    #     dropped because the identity key changed with it.
    run1 = [{"title": "Foo", "level": "indicator", "code": "ABC", "description": "d",
             "age_band": "36-60", "source_page": 1}]
    run2 = [{"title": "Foo", "level": "indicator", "code": "XYZ", "description": "d",
             "age_band": "36-60", "source_page": 1}]
    r = compute_stability([run1, run2], ["run1", "run2"], detector_identity,
                           DETECTOR_COMPARED_FIELDS, detector_getter, detector_sort_key)
    check("(a) code-change: identity pairs across runs (n_identities_compared==1)",
          r["n_identities_compared"] == 1)
    check("(a) code-change: counted as a code disagreement",
          r["n_dimension_disagreements"]["code"] == 1)
    check("(a) code-change: identity counted as distinctly unstable",
          r["n_distinct_unstable_identities"] == 1)
    check("(a) code-change: disagreement_rate == 1.0", r["disagreement_rate"] == 1.0)

    # (b) an element present in run 1 and ABSENT in run 2 counts as unstable
    #     (not silently invisible, only visible in a size stdev).
    run1b = [{"title": "Alpha", "level": "domain", "code": "A"},
             {"title": "Bravo", "level": "domain", "code": "B"}]
    run2b = [{"title": "Alpha", "level": "domain", "code": "A"}]
    rb = compute_stability([run1b, run2b], ["run1", "run2"], detector_identity,
                            DETECTOR_COMPARED_FIELDS, detector_getter, detector_sort_key)
    check("(b) presence: 2 identities compared", rb["n_identities_compared"] == 2)
    check("(b) presence: missing element counted as distinctly unstable",
          rb["n_distinct_unstable_identities"] == 1)
    check("(b) presence: missing element flagged under presence_or_multiplicity",
          rb["n_dimension_disagreements"]["presence_or_multiplicity"] == 1)
    presence_examples = [e for e in rb["examples"] if e["dimension"] == "presence"]
    check("(b) presence: an example is recorded showing which run lost it",
          len(presence_examples) == 1 and presence_examples[0]["detail"] == {"run1": "present", "run2": "MISSING"})

    # (c) an identity unstable in THREE dimensions (level, code, description)
    #     contributes 1 to n_distinct_unstable_identities, not 3, and the rate
    #     never exceeds 1.0 even when summed per-dimension counts would.
    run1c = [
        {"title": "Stable", "level": "indicator", "code": "AAA", "description": "same", "age_band": None, "source_page": 1},
        {"title": "Chaotic", "level": "indicator", "code": "BBB", "description": "before", "age_band": None, "source_page": 2},
    ]
    run2c = [
        {"title": "Stable", "level": "indicator", "code": "AAA", "description": "same", "age_band": None, "source_page": 1},
        {"title": "Chaotic", "level": "domain", "code": "ZZZ", "description": "after", "age_band": None, "source_page": 2},
    ]
    rc = compute_stability([run1c, run2c], ["run1", "run2"], detector_identity,
                            DETECTOR_COMPARED_FIELDS, detector_getter, detector_sort_key)
    check("(c) 2 identities compared", rc["n_identities_compared"] == 2)
    check("(c) exactly ONE distinct unstable identity (not 3)",
          rc["n_distinct_unstable_identities"] == 1)
    check("(c) all three dimensions individually recorded as 1 each",
          rc["n_dimension_disagreements"]["level"] == 1
          and rc["n_dimension_disagreements"]["code"] == 1
          and rc["n_dimension_disagreements"]["description"] == 1)
    check("(c) sum of per-dimension counts (3) EXCEEDS n_distinct_unstable (1) "
          "-- proving the rate is not computed by summing them",
          sum(v for k, v in rc["n_dimension_disagreements"].items()
              if k != "presence_or_multiplicity") == 3
          and rc["n_distinct_unstable_identities"] == 1)
    check("(c) disagreement_rate == 0.5 (1 of 2), not 1.5", rc["disagreement_rate"] == 0.5)
    check("(c) disagreement_rate never exceeds 1.0", 0.0 <= rc["disagreement_rate"] <= 1.0)

    # a maximally-unstable case as an extra bound check: every identity
    # unstable in every field must still cap the rate at 1.0.
    run1d = [{"title": "X", "level": "indicator", "code": "A", "description": "a", "age_band": "1", "source_page": 1}]
    run2d = [{"title": "X", "level": "domain", "code": "B", "description": "b", "age_band": "2", "source_page": 2}]
    rd = compute_stability([run1d, run2d], ["run1", "run2"], detector_identity,
                            DETECTOR_COMPARED_FIELDS, detector_getter, detector_sort_key)
    check("(c-bound) fully-unstable single identity still yields rate == 1.0, not 5.0",
          rd["disagreement_rate"] == 1.0 and rd["n_distinct_unstable_identities"] == 1)

    # (d) a run with zero items triggers the loud refusal, not a silent
    #     "everything agrees" result.
    tmp_root = None
    try:
        import tempfile
        tmp_root = pathlib.Path(tempfile.mkdtemp(prefix="task5_selfcheck_"))
        reports_dir = tmp_root / "reports"
        review_dir = tmp_root / "review"
        reports_dir.mkdir(parents=True)
        (review_dir / "detector_run1" / "ZZ").mkdir(parents=True)
        (review_dir / "detector_run2" / "ZZ").mkdir(parents=True)

        good_items = [{"title": "T", "level": "domain", "code": "A", "description": None,
                       "age_band": None, "source_page": 1}]
        (review_dir / "detector_run1" / "ZZ" / "ZZ-detected.json").write_text(json.dumps(good_items))
        (review_dir / "detector_run2" / "ZZ" / "ZZ-detected.json").write_text(json.dumps([]))

        (reports_dir / "detector_run1_ZZ.json").write_text(
            json.dumps([{"state": "ZZ", "n_golden": 1, "n_detected": 1}]))
        (reports_dir / "detector_run2_ZZ.json").write_text(
            json.dumps([{"state": "ZZ", "n_golden": 1, "n_detected": 0}]))

        raised = False
        try:
            load_suite("detector", tmp_root)
        except SystemExit as e:
            raised = "REFUSING" in str(e) and "n_detected" in str(e)
        check("(d) a run reporting n_detected==0 raises SystemExit (\"REFUSING...\")", raised)

        # sanity: the same fixture with a nonzero second run does NOT refuse.
        (review_dir / "detector_run2" / "ZZ" / "ZZ-detected.json").write_text(json.dumps(good_items))
        (reports_dir / "detector_run2_ZZ.json").write_text(
            json.dumps([{"state": "ZZ", "n_golden": 1, "n_detected": 1}]))
        by_state = load_suite("detector", tmp_root)
        check("(d) sanity: a healthy 2-run fixture loads without refusing",
              len(by_state.get("ZZ", [])) == 2)

        # sanity: inconsistent n_golden across runs for the same state refuses.
        (reports_dir / "detector_run2_ZZ.json").write_text(
            json.dumps([{"state": "ZZ", "n_golden": 2, "n_detected": 1}]))
        raised_golden = False
        try:
            load_suite("detector", tmp_root)
        except SystemExit as e:
            raised_golden = "n_golden" in str(e)
        check("(d) inconsistent n_golden across runs for one state raises SystemExit",
              raised_golden)
    finally:
        if tmp_root is not None:
            import shutil
            shutil.rmtree(tmp_root, ignore_errors=True)

    # a state with exactly 1 observation is NOT_MEASURABLE, not "stable".
    single = summarize_suite(
        "detector", {"ZZ": [{"run": 1, "label": "run1", "n_golden": 1, "items": good_items}]},
        max_examples=20,
    )
    check("(e) a single-observation state reports NOT_MEASURABLE rather than a rate",
          single["per_state"]["ZZ"]["status"] == "NOT_MEASURABLE")

    # (f) REGRESSION PIN, added 2026-08-30 after review found the original
    # detector_sort_key sorting by `level` and `code` -- both fields under test.
    # A repeated title whose code changes must still pair occurrence-to-
    # occurrence by page position, so the change registers as exactly ONE code
    # disagreement. If the sort key ever goes back to ordering by a compared
    # field, the two occurrences swap between runs and this reports two
    # disagreements (code AND description) instead of one.
    rep_a = [
        {"title": "Vocabulary", "level": "sub_strand", "code": "ELD.1.0.VOCA",
         "description": "eld one", "age_band": None, "source_page": 11,
         "source_text": "ELD strand text"},
        {"title": "Vocabulary", "level": "sub_strand", "code": "FLD.1.0.VOCA",
         "description": "fld two", "age_band": None, "source_page": 42,
         "source_text": "FLD strand text"},
    ]
    rep_b = [
        # same two elements, emitted in the opposite list order, and the FLD
        # one's code has drifted. Nothing else changed.
        # The ELD occurrence's code drifts to a value that sorts AFTER the FLD
        # one. Under a code-based sort that SWAPS the two occurrences between
        # runs, so run1[0] (ELD) gets compared against run2[0] (FLD) and the
        # descriptions spuriously disagree too. Under a page-based sort they
        # stay paired and only `code` moves. The drift must cross the sort
        # boundary or the fixture proves nothing.
        {"title": "Vocabulary", "level": "sub_strand", "code": "FLD.1.0.VOCA",
         "description": "fld two", "age_band": None, "source_page": 42,
         "source_text": "FLD strand text"},
        {"title": "Vocabulary", "level": "sub_strand", "code": "ZZZ.9.9.ZZZZ",
         "description": "eld one", "age_band": None, "source_page": 11,
         "source_text": "ELD strand text"},
    ]
    rep = compute_stability([rep_a, rep_b], ["run1", "run2"], detector_identity,
                            DETECTOR_COMPARED_FIELDS, detector_getter,
                            detector_sort_key)
    check("(f) a repeated title pairs by page, so a code drift is 1 disagreement not 2",
          rep["n_dimension_disagreements"]["code"] == 1
          and rep["n_dimension_disagreements"]["description"] == 0
          and rep["n_distinct_unstable_identities"] == 1)

    print()
    if failures:
        print(f"SELF-CHECK FAILED: {len(failures)} check(s) failed: {failures}")
        return False
    print("SELF-CHECK PASSED: all blind-spot checks hold.")
    return True


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--results-dir", default="paper/results/task5_20260830",
                     help="Directory containing reports/ and review/ subfolders.")
    ap.add_argument("--out", type=pathlib.Path, default=None,
                     help="Write the full JSON result here.")
    ap.add_argument("--max-examples", type=int, default=20)
    ap.add_argument("--frozen-parser", nargs="*", default=[],
                    help="Already-recorded parser report JSONs to fold in as observation 0. "
                         "Only legitimate if they share this sweep's code_version_hash, "
                         "detection input and --no-cache setting. PARSER ONLY -- see "
                         "load_frozen_parser.")
    ap.add_argument("--frozen-parser-review", nargs="*", default=[],
                    help="Review directories matching --frozen-parser, positionally.")
    ap.add_argument("--self-check", action="store_true",
                     help="Run synthetic assertions proving the four blind spots are "
                          "absent, then exit. Needs no input files.")
    args = ap.parse_args()

    if args.self_check:
        ok = self_check()
        sys.exit(0 if ok else 1)

    main_real(args)


if __name__ == "__main__":
    main()
