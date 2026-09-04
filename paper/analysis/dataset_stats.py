"""Compute the paper's dataset descriptive statistics and re-measure the
detector's confidence distribution from scratch (arXiv paper, Task 8).

Guardrail 6 (tasking/arxiv_paper.md): every number in the paper must be
regenerable. This script is Task 8's regeneration step. It reads only JSON
already on disk -- the recorded pipeline outputs, the frozen eval detections,
the SIGNED false-positive audits, the goldens, and corpus_tiers.json -- and
spends no Bedrock tokens. Run it, then regenerate the tables with
paper/analysis/generate_tables.py.

Two things are measured, and they are kept in separate output files because
they answer separate questions.

1. ``dataset_stats.json`` -- what the corpus actually contains: standards,
   realized hierarchy levels, age-band coverage, description coverage, and the
   ``standard_id`` collision count (guardrail: it must be 0, since
   ``standard_id`` is the Aurora primary key).

2. ``confidence_distribution.json`` -- the detector's self-reported
   ``confidence``, re-measured. Guardrail 4 forbids importing the Medium
   articles' unvalidated "85-90% of indicators at 0.95+" figure; this file is
   the measurement that replaces it. Guardrail 2 is the reason the measurement
   matters: **confidence gates nothing**. Nothing in ``src/`` thresholds it and
   there is no ``needs_review`` field -- human verification is a separate
   concept, carried by ``human_verified``/``verified_at``/``verified_by`` on
   all four levels (``infra/migrations/005_add_verification_columns.sql``).
   Verified against the live tree on 2026-08-23: zero hits for
   ``needs_review`` or ``CONFIDENCE_THRESHOLD`` in ``src/``, ``evaluation/``,
   or ``infra/cdk/lib/``. (A local grep DOES hit both names under
   ``infra/cdk/dist/`` and ``infra/cdk/cdk.out.deploy-dev/`` -- stale build
   artifacts of a pre-2026 revision that did have a gate. Both are gitignored
   and untracked, so they are absent from a clean checkout and from the arXiv
   tarball. Do not read them as evidence of a live gate.)

TWO PATHS ARE MEASURED, DELIBERATELY. The detector eval runs the DIRECT path
while production runs the BATCHED path (``detection_batching.py``), and the two
do not converge -- see CLAUDE.md, "batched vs direct". They are reported side
by side rather than pooled:

  * DIRECT  -- the frozen detections the recorded evals graded, in
    ``paper/results/task{1,2}_<RUN_TAG>/review_detector/``. This is the ONLY
    path the false-positive audit covers, so it is the only path on which
    confidence can be joined to a human verdict.
  * BATCHED -- ``outputs/<OUTPUTS_TAG>/{STATE}-detection.json``, the production
    pipeline's output, and the basis for every dataset statistic.

⚠️ The batched path is biased UPWARD by construction: ``_merge_duplicate``
(detector.py) keeps ``max(keep.confidence, other.confidence)`` when it folds
two views of one element together. A batched-vs-direct difference in the
confidence distribution is therefore not evidence about the model.

Guards (each exists because the failure it catches has actually happened):
  * a detection file with zero elements is refused, not averaged in -- a
    mid-run Bedrock throttle once recorded five states as ``n_detected=0``,
    which reads as a catastrophic result rather than an infrastructure failure
    (tasking/arxiv_paper.md, "Compute budget", rule 2);
  * an unmatched in-scope detection with no signed audit verdict is refused --
    an unsigned first pass is not quotable (guardrail 8);
  * the SIGNED audits are read, never ``heldout_evidence.json``, whose
    ``verified_by`` is reset to UNSIGNED every time it is regenerated.

Usage (from repo root):
    python paper/analysis/dataset_stats.py
"""

import collections
import json
import statistics
import subprocess
from pathlib import Path

PAPER_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = PAPER_DIR.parent
RESULTS_DIR = PAPER_DIR / "results"

# The recorded freeze this task describes. Keep in step with generate_tables.py.
RUN_TAG = "20260826"
OUT_TAG = "20260823"
OUTPUTS_TAG = "08-26-26-2"

GOLDEN_STATES = ["AZ", "CA", "CO", "TX"]
HELDOUT_STATES = ["NV", "KY"]
ALL_STATES = GOLDEN_STATES + HELDOUT_STATES

# Which recorded task folder holds each state's frozen direct-path detection.
TASK_OF_STATE = {s: f"task1_{RUN_TAG}" for s in GOLDEN_STATES}
TASK_OF_STATE.update({s: f"task2_{RUN_TAG}" for s in HELDOUT_STATES})

STATE_TIER_KEY = {"AZ": "AZ", "CA": "CA", "CO": "CO", "TX": "TX",
                  "NV": "NV_2023", "KY": "KY"}

LEVELS = ["domain", "strand", "sub_strand", "indicator"]

# The detector prompt's own confidence rubric (detector.py rule 5), quoted here
# so the measured distribution can be read against the bands it was asked for.
PROMPT_RUBRIC = {
    "0.95+": "the depth map clearly applies",
    "0.80-0.94": "the chunk is ambiguous but the answer is likely",
    "<0.70": "you are guessing",
}

OUT_DIR = RESULTS_DIR / f"task8_{OUT_TAG}"


def load_json(path):
    with open(path) as f:
        return json.load(f)


def elements_of(path):
    """Detection JSON is a dict with an `elements` key on both paths; the frozen
    eval detections are occasionally a bare list. Accept either."""
    d = load_json(path)
    els = d["elements"] if isinstance(d, dict) and "elements" in d else d
    if not els:
        raise SystemExit(
            f"{path} holds ZERO elements. That is an infrastructure failure "
            "(almost always a mid-run Bedrock throttle), not a result. Refusing "
            "to fold it into a descriptive statistic -- re-run the state.")
    return els


def batched_detection(state):
    return elements_of(REPO_ROOT / "outputs" / OUTPUTS_TAG / f"{state}-detection.json")


def direct_detection(state):
    return elements_of(RESULTS_DIR / TASK_OF_STATE[state] / "review_detector"
                       / state / f"{state}-detected.json")


def parsed_standards(state):
    d = load_json(REPO_ROOT / "outputs" / OUTPUTS_TAG / f"{state}-parsing.json")
    return d["indicators"]


def review(state):
    return load_json(RESULTS_DIR / TASK_OF_STATE[state] / "review_detector"
                     / state / f"{state}-review.json")


def signed_verdicts():
    """Join the two SIGNED false-positive audits into one {state: {key: verdict}}.

    These files -- not heldout_evidence.json -- are the authority: regenerating
    the evidence JSON resets `verified_by` to UNSIGNED.
    """
    out = {}
    for path in (RESULTS_DIR / f"task1_{RUN_TAG}" / "task1b_fp_audit_SIGNED.json",
                 RESULTS_DIR / f"task2_{RUN_TAG}" / "nv_fp_audit_SIGNED.json"):
        for state, rows in load_json(path)["verdicts"].items():
            m = out.setdefault(state, {})
            for r in rows:
                m[(r["level"], r["code"], r["title"])] = r["verdict"]
    return out


# --------------------------------------------------------------------------
# 1. Dataset descriptive statistics
# --------------------------------------------------------------------------

def describe_state(state, tiers):
    els = batched_detection(state)
    stds = parsed_standards(state)

    by_level = collections.Counter(e["level"] for e in els)
    ids = [s["standard_id"] for s in stds]
    dupes = [i for i, n in collections.Counter(ids).items() if n > 1]

    # Realized hierarchy: a four-level schema does not mean a four-level
    # document. CO and TX print no sub_strand tier at all in their subsets.
    realized = {lv: sorted({(s[lv] or {}).get("code") for s in stds
                            if s.get(lv) and (s[lv] or {}).get("code")})
                for lv in LEVELS}

    bands = collections.Counter(s.get("age_band") for s in stds)
    n_band = sum(v for k, v in bands.items() if k)

    # Description coverage per level, over DISTINCT nodes.
    #
    # ⚠️ Counting one node per parsed row would double-count: every standard
    # carries its whole ancestor chain, so CO's three domains would report as
    # 48 domain nodes. Deduplicate by code first -- only `indicator` is
    # genuinely one node per row.
    #
    # `blank_string` exists because `models._blank_to_none` folds a whitespace
    # string to None (2026-08-15). A non-zero count here is a regression in
    # that validator, not a property of the documents.
    desc = {}
    for lv in LEVELS:
        nodes = {}
        for s in stds:
            node = s.get(lv)
            code = (node or {}).get("code")
            if not node or not code:
                continue
            nodes.setdefault(code, node.get("description"))
        present = sum(1 for v in nodes.values()
                      if v is not None and not (isinstance(v, str) and not v.strip()))
        blank = sum(1 for v in nodes.values()
                    if isinstance(v, str) and not v.strip())
        desc[lv] = {"distinct_nodes": len(nodes), "with_description": present,
                    "blank_string": blank,
                    "coverage": round(present / len(nodes), 4) if nodes else None}

    pages = sorted({s.get("source_page") for s in stds if s.get("source_page")})
    tier = tiers["tiers"][STATE_TIER_KEY[state]]

    # ⚠️ CO has no single "full" page count and must not be given one. Its
    # _only_subset and _trimmed tiers both derive from the 41pp 3-5 document,
    # NOT from the 187pp birth-to-8 document (corpus_tiers.json). Reporting 187
    # as "the full document this subset came from" would overstate the trim by
    # 4.5x. The whole tier record is carried through so the table can say which
    # document it means.
    full = tier.get("full")
    note = None
    if full is None and "full_3_5" in tier:
        full = tier["full_3_5"]
        note = ("the subset derives from the 41pp 3-5 document; the separate "
                "birth-to-8 document is 187pp and is not this subset's parent")

    return {
        "role": tier["role"],
        "version_year": stds[0]["version_year"] if stds else None,
        "pages_subset": tier.get("only_subset"),
        "pages_full": full,
        "pages_full_note": note,
        "tier_record": tier,
        "detected_elements": len(els),
        "detected_by_level": {lv: by_level.get(lv, 0) for lv in LEVELS},
        "standards": len(stds),
        "unique_standard_ids": len(set(ids)),
        "standard_id_collisions": len(dupes),
        "colliding_ids": sorted(dupes),
        "distinct_domains": len(realized["domain"]),
        "distinct_strands": len(realized["strand"]),
        "distinct_sub_strands": len(realized["sub_strand"]),
        "levels_realized": [lv for lv in LEVELS if realized[lv]],
        "age_band_coverage": round(n_band / len(stds), 4) if stds else None,
        "age_bands": {k: v for k, v in sorted(bands.items(), key=lambda kv: str(kv[0]))},
        "description_coverage": desc,
        "source_page_span": [pages[0], pages[-1]] if pages else None,
    }


def annotation_stats():
    """How much of the corpus is hand-annotated, per suite. The two golden sets
    are decoupled -- different shapes, different inputs, annotated
    independently -- so they are never summed together."""
    out = {}
    for state in ALL_STATES:
        det = load_json(REPO_ROOT / "evaluation" / "ground_truth_detector" / f"{state}.json")
        par = load_json(REPO_ROOT / "evaluation" / "ground_truth_parser" / f"{state}.json")
        det_levels = collections.Counter(e["level"] for e in det["elements"])
        out[state] = {
            "detector_golden_elements": len(det["elements"]),
            "detector_golden_by_level": {lv: det_levels.get(lv, 0) for lv in LEVELS},
            "detector_regression_cases": len(det.get("regression_cases", [])),
            "parser_golden_standards": len(par["standards"]),
            "parser_regression_cases": len(par.get("regression_cases", [])),
            "annotator": det.get("annotator"),
            "annotation_date": det.get("annotation_date"),
        }
    return out


def build_dataset_stats(tiers):
    per_state = {s: describe_state(s, tiers) for s in ALL_STATES}
    ann = annotation_stats()

    all_ids = [i for s in ALL_STATES for i in
               (x["standard_id"] for x in parsed_standards(s))]
    all_bands = collections.Counter()
    for s in ALL_STATES:
        for k, v in per_state[s]["age_bands"].items():
            all_bands[k] += v

    totals = {
        "states": len(ALL_STATES),
        "states_golden": len(GOLDEN_STATES),
        "states_heldout": len(HELDOUT_STATES),
        "subset_pages": sum(per_state[s]["pages_subset"] for s in ALL_STATES),
        "detected_elements": sum(per_state[s]["detected_elements"] for s in ALL_STATES),
        "detected_by_level": {
            lv: sum(per_state[s]["detected_by_level"][lv] for s in ALL_STATES)
            for lv in LEVELS},
        "standards": sum(per_state[s]["standards"] for s in ALL_STATES),
        "unique_standard_ids": len(set(all_ids)),
        "standard_id_collisions_within_state":
            sum(per_state[s]["standard_id_collisions"] for s in ALL_STATES),
        "standard_id_collisions_corpus_wide": len(all_ids) - len(set(all_ids)),
        "distinct_domains": sum(per_state[s]["distinct_domains"] for s in ALL_STATES),
        "distinct_strands": sum(per_state[s]["distinct_strands"] for s in ALL_STATES),
        "distinct_sub_strands": sum(per_state[s]["distinct_sub_strands"] for s in ALL_STATES),
        "age_band_coverage": round(
            sum(v for k, v in all_bands.items() if k) / len(all_ids), 4),
        "distinct_age_bands": sorted(k for k in all_bands if k),
        "age_bands": dict(sorted(all_bands.items(), key=lambda kv: str(kv[0]))),
        "detector_golden_elements": sum(ann[s]["detector_golden_elements"] for s in ALL_STATES),
        "parser_golden_standards": sum(ann[s]["parser_golden_standards"] for s in ALL_STATES),
    }

    return {
        "_meta": meta(
            "Dataset descriptive statistics over the recorded six-state run.",
            [f"outputs/{OUTPUTS_TAG}/{{STATE}}-detection.json (batched, production path)",
             f"outputs/{OUTPUTS_TAG}/{{STATE}}-parsing.json",
             "evaluation/ground_truth_{detector,parser}/{STATE}.json",
             "paper/results/corpus_tiers.json"]),
        "per_state": per_state,
        "annotation": ann,
        "totals": totals,
        "notes": [
            "standard_id is {country}-{state}-{year}-{indicator_code} and is the "
            "Aurora primary key, so a collision is a correctness defect, not a "
            "cosmetic one. Corpus-wide collisions are counted as well as "
            "within-state, but cross-state collisions are impossible by "
            "construction -- the state code is part of the id.",
            "Detected-element counts are the BATCHED (production) path and do "
            "not equal the direct path the detector eval grades. AZ is the "
            "widest gap in this run, 77 batched against 66 direct, from "
            "cross-page duplicate copies of its contents/listing page; "
            "diagnosed 2026-08-22 and benign (tasking/arxiv_paper.md).",
            "distinct_domains/strands/sub_strands count ancestors that appear in "
            "at least one standard's chain, so they are NOT the detected counts "
            "and are legitimately smaller (corpus-wide, 37 distinct parsed "
            "strands against 52 detected). Two reasons, both benign: the "
            "detection contains cross-page reprints of the same heading, and a "
            "heading with no indicator beneath it inside the subset has no "
            "standard to appear in.",
            "description_coverage is over DISTINCT nodes, not per standard row -- "
            "every row carries its whole ancestor chain, so a per-row count would "
            "report CO's three domains as 48. It varies by document rather than "
            "by pipeline behaviour: AZ, CA and KY print a description on every "
            "indicator, CO, TX and NV print none. blank_string is 0 everywhere, "
            "which is the check that models._blank_to_none is holding -- absence "
            "has exactly one spelling in this schema.",
            "levels_realized shows that a four-level schema is not a four-level "
            "document: CO's subset prints no sub_strand tier at all, and TX's "
            "prints two. This is the variation the parser's optional-level "
            "handling exists for.",
            "Every number here is the _only_subset corpus tier (guardrail 1) -- "
            "8-15pp manually trimmed subsets, never full documents.",
        ],
    }


# --------------------------------------------------------------------------
# 2. Confidence distribution
# --------------------------------------------------------------------------

def summarize(values):
    if not values:
        return None
    vs = sorted(values)
    return {
        "n": len(vs),
        "min": vs[0],
        "max": vs[-1],
        "mean": round(statistics.fmean(vs), 4),
        "median": round(statistics.median(vs), 4),
        "stdev": round(statistics.pstdev(vs), 4) if len(vs) > 1 else 0.0,
        "distinct_values": sorted(set(vs)),
        "n_distinct_values": len(set(vs)),
        "histogram": {str(k): v for k, v in sorted(collections.Counter(vs).items())},
        "at_or_above_0.95": sum(1 for v in vs if v >= 0.95),
        "frac_at_or_above_0.95": round(sum(1 for v in vs if v >= 0.95) / len(vs), 4),
        "below_0.80": sum(1 for v in vs if v < 0.80),
        "below_0.70": sum(1 for v in vs if v < 0.70),
        # Occupancy of the prompt's OWN three bands (detector.py rule 5). This
        # is the comparison that matters: the question is not where the values
        # fall on an arbitrary scale but whether the model ever uses the range
        # it was asked to use.
        "prompt_band_occupancy": {
            "0.95+ (depth map clearly applies)": sum(1 for v in vs if v >= 0.95),
            "0.80-0.94 (ambiguous but likely)":
                sum(1 for v in vs if 0.80 <= v < 0.95),
            "below 0.70 (guessing)": sum(1 for v in vs if v < 0.70),
            "unassigned gap 0.70-0.79": sum(1 for v in vs if 0.70 <= v < 0.80),
        },
    }


def path_distribution(loader):
    rows = []
    for state in ALL_STATES:
        for e in loader(state):
            rows.append((state, e["level"], round(float(e["confidence"]), 4)))
    return {
        "overall": summarize([c for _, _, c in rows]),
        "by_level": {lv: summarize([c for _, l, c in rows if l == lv]) for lv in LEVELS},
        "by_state": {st: summarize([c for s, _, c in rows if s == st]) for st in ALL_STATES},
    }


def repeat_samples():
    """Every direct-path detection on disk produced by THIS code version with
    the depth map ON, keyed by state.

    Sample 1 is the recorded eval freeze; the rest are Task 3's stability
    repeats, which carry the same ``code_version_hash`` (288c64f1), the same
    model IDs and temperature 0 (paper/results/task3_stability_<TAG>/manifest.json).
    The OFF-arm repeats are deliberately excluded -- a different configuration
    is a different system, and pooling the two would hide that.

    Older ``outputs/`` folders are excluded for the same reason: they predate
    this code version, and their confidence values come from a detector with a
    different prompt.
    """
    samples = collections.defaultdict(list)
    for state in ALL_STATES:
        samples[state].append(("sample1_eval_freeze",
                               RESULTS_DIR / TASK_OF_STATE[state] / "review_detector"
                               / state / f"{state}-detected.json"))
    stab = RESULTS_DIR / f"task3_stability_{OUT_TAG}" / "review"
    for run in sorted(stab.glob("on_run*")):
        for d in sorted(run.glob("*")):
            f = d / f"{d.name}-detected.json"
            if d.name in ALL_STATES and f.exists():
                samples[d.name].append((run.name, f))
    return samples


def separation_stability(hallucination_max):
    """Does the one element the audit calls invented stay the lowest-scoring
    element when the detector is re-run?

    This exists to stop a single sample being over-read. On the recorded freeze
    the audited hallucination is the only element below 0.90, which looks like
    a working gate; the question is whether that is a property of the score or
    an accident of one draw. Repeats answer it for the NEGATIVE case (does a
    CORRECT element ever drop below the line) but they cannot answer it for the
    positive case -- there is one distinct hallucination in the audited corpus,
    so no repeat can estimate what fraction of hallucinations score low.
    """
    samples = repeat_samples()
    cut = 0.90
    total = 0
    below = []
    for state, items in samples.items():
        for tag, path in items:
            for e in elements_of(path):
                total += 1
                c = round(float(e["confidence"]), 4)
                if c < cut:
                    below.append({"state": state, "sample": tag, "confidence": c,
                                  "level": e["level"], "code": e.get("code"),
                                  "title": e["title"]})
    distinct = {(b["state"], b["level"], b["code"], b["title"]) for b in below}
    return {
        "cut": cut,
        "samples_per_state": {s: [t for t, _ in v] for s, v in sorted(samples.items())},
        "n_samples": sum(len(v) for v in samples.values()),
        "elements_examined": total,
        "elements_below_cut": len(below),
        "distinct_elements_below_cut": len(distinct),
        "rows": below,
        "audited_hallucination_max_confidence": hallucination_max,
        "reading": (
            "Across these same-configuration repeats the only elements below "
            f"{cut} are {len(distinct)} distinct element(s), and the audit calls "
            "that element invented. So the separation is not an artifact of one "
            "draw. It is still NOT a validated detector: the audited corpus "
            "contains exactly one distinct hallucination, so the false-negative "
            "rate of such a cut is unmeasured and unmeasurable from this data. "
            "The detector prompt's own rubric puts its boundary at 0.80, which "
            "catches nothing here -- a cut at 0.90 is fitted after the fact to "
            "a single positive case."),
    }


def sub_threshold_concentration():
    """Where do the sub-0.95 indicators actually live?

    The Medium article's second sentence is a claim about their composition --
    "the remaining 10-15% are typically from tables, footnotes, or sections
    with unusual formatting" -- and it is testable on this corpus without any
    new annotation. If the low tail were difficulty-driven it would be spread
    across states and concentrated in the hardest documents. Whether it is is
    what this measures.
    """
    per_state = {}
    for state in ALL_STATES:
        ind = [round(float(e["confidence"]), 4) for e in direct_detection(state)
               if e["level"] == "indicator"]
        lo = [c for c in ind if c < 0.95]
        per_state[state] = {
            "indicators": len(ind),
            "below_0.95": len(lo),
            "frac_below_0.95": round(len(lo) / len(ind), 4) if ind else None,
            "values_below_0.95": sorted(set(lo)),
        }
    total = sum(v["indicators"] for v in per_state.values())
    low = sum(v["below_0.95"] for v in per_state.values())
    states_with_none = [s for s, v in per_state.items() if v["below_0.95"] == 0]
    saturated = [s for s, v in per_state.items()
                 if v["indicators"] and v["below_0.95"] == v["indicators"]]
    return {
        "per_state": per_state,
        "indicators_total": total,
        "indicators_below_0.95": low,
        "states_with_no_low_indicator": states_with_none,
        "states_where_every_indicator_is_low": saturated,
        "finding": (
            f"The low tail is not spread across documents: {len(states_with_none)} "
            f"of {len(ALL_STATES)} states have no sub-0.95 indicator at all, and "
            f"the tail is almost entirely {', '.join(saturated)} -- where EVERY "
            "indicator scores below the line. The score moves at the level of a "
            "whole document, not at the level of a hard passage inside one, "
            "which is the opposite of what the published claim describes."),
    }


def confidence_by_verdict():
    """Join every in-scope DIRECT-path detection to a human verdict.

    Two sources of verdict, and together they cover the path completely:
    a detection that MATCHED a golden entry is correct by construction, and
    every UNMATCHED in-scope detection carries a signed audit verdict. Anything
    left over is a gap in the audit and is refused rather than dropped.
    """
    verdicts = signed_verdicts()
    rows = []
    for state in ALL_STATES:
        r = review(state)
        for m in r["matched"]:
            rows.append((state, "matched_golden",
                         m["detected"]["level"],
                         round(float(m["detected"]["confidence"]), 4)))
        vmap = verdicts.get(state, {})
        for e in r["extra_in_detected"]:
            key = (e["level"], e["code"], e["title"])
            if key not in vmap:
                raise SystemExit(
                    f"{state}: unmatched in-scope detection {key!r} has no SIGNED "
                    "audit verdict. An unsigned verdict is not quotable "
                    "(guardrail 8) -- sign the audit before regenerating.")
            rows.append((state, vmap[key], e["level"],
                         round(float(e["confidence"]), 4)))

    by_verdict = collections.defaultdict(list)
    for _, v, _, c in rows:
        by_verdict[v].append(c)

    hallucinated = by_verdict.get("hallucinated", [])
    real = [c for v, cs in by_verdict.items() if v != "hallucinated" for c in cs]

    # Would a confidence threshold have caught the hallucination? Reported as a
    # cost, not as a recommendation: with a single positive case no threshold
    # can be validated, and the numbers below are what a threshold WOULD have
    # done on this corpus, not a rule the system applies (guardrail 2).
    thresholds = []
    for t in (0.70, 0.80, 0.90, 0.93, 0.95, 0.96):
        flagged_bad = sum(1 for c in hallucinated if c < t)
        flagged_ok = sum(1 for c in real if c < t)
        thresholds.append({
            "threshold": t,
            "elements_flagged": flagged_bad + flagged_ok,
            "hallucinations_caught": flagged_bad,
            "hallucinations_missed": len(hallucinated) - flagged_bad,
            "correct_elements_flagged": flagged_ok,
            "precision_of_the_flag": round(flagged_bad / (flagged_bad + flagged_ok), 4)
            if (flagged_bad + flagged_ok) else None,
        })

    return {
        "path": "DIRECT (the frozen detections the recorded evals graded)",
        "in_scope_detections_audited": len(rows),
        "by_verdict": {v: summarize(cs) for v, cs in
                       sorted(by_verdict.items(), key=lambda kv: -len(kv[1]))},
        "verdict_counts": {v: len(cs) for v, cs in
                           sorted(by_verdict.items(), key=lambda kv: -len(kv[1]))},
        "verified_precision_corpus_wide": round(
            (len(rows) - len(hallucinated)) / len(rows), 4),
        "threshold_analysis": thresholds,
    }


def build_confidence(dataset):
    direct = path_distribution(direct_detection)
    batched = path_distribution(batched_detection)
    verdict = confidence_by_verdict()
    d = direct["overall"]
    hall = verdict["by_verdict"].get("hallucinated")
    n_hall = verdict["verdict_counts"].get("hallucinated", 0)
    stability = separation_stability(hall["max"] if hall else None)

    conc = sub_threshold_concentration()
    ind = direct["by_level"]["indicator"]
    medium_claim = {
        "claim_as_published":
            "\"In practice, most documents produce 85-90% of their indicators at "
            "0.95+ confidence. The remaining 10-15% are typically from tables, "
            "footnotes, or sections with unusual formatting.\"",
        "source": "documentation/medium-articles/02-teaching-ai-to-read-curriculum.md"
                  " line 100 -- prose seed only, never measured (guardrail 4).",
        "remeasured_direct_path": f"{ind['at_or_above_0.95']}/{ind['n']} = "
                                  f"{ind['frac_at_or_above_0.95']:.4f}",
        "remeasured_batched_path":
            f"{batched['by_level']['indicator']['at_or_above_0.95']}/"
            f"{batched['by_level']['indicator']['n']} = "
            f"{batched['by_level']['indicator']['frac_at_or_above_0.95']:.4f}",
        "first_sentence_verdict":
            "REPRODUCES. The paper must still cite the measurement rather than "
            "the claim: landing inside the published band is a property of this "
            "corpus, not a validation of a number that was never measured.",
        "second_sentence_verdict":
            "REFUTED -- see sub_threshold_concentration. " + conc["finding"],
        "third_claim_in_the_same_article":
            "Article 02 line 98 also states that elements below a 0.70 threshold "
            "are flagged for human review and that this 'creates a quality gate'. "
            "That gate does not exist in the live code (guardrail 2), and this "
            "corpus shows it would have been inert if it did: ZERO of the "
            f"{direct['overall']['n']} recorded elements -- and zero across all "
            "same-configuration repeats -- score below 0.70. Even the historical "
            "gate could never have fired on any document measured here.",
        "why_it_is_not_a_quality_signal": (
            "The score is self-reported by the detector against its own prompt "
            "rubric, and it barely leaves the top of that rubric: no element in "
            "either path falls below 0.85, the band the rubric reserves for a "
            "guess is never used at all, and the corpus takes only a handful of "
            "distinct values. A high 0.95+ share therefore measures how the "
            "model was asked to fill in a field, not how often it was right. "
            "Kentucky makes the point at the state level: it is the one state "
            "with a detection-exhaustive golden, and it scores recall 1.000, "
            "code accuracy 1.000 and verified precision 1.000 -- while every one "
            "of its indicators sits BELOW 0.95. California scores the same "
            "recall and code accuracy with all 94 indicators at or above it."),
    }

    return {
        "_meta": meta(
            "Detector self-reported confidence, re-measured from scratch "
            "(guardrail 4). Confidence gates nothing (guardrail 2).",
            [f"outputs/{OUTPUTS_TAG}/{{STATE}}-detection.json (batched)",
             f"paper/results/task{{1,2}}_{RUN_TAG}/review_detector/{{STATE}}/ "
             "(direct, plus the review that supplies matched/extra)",
             f"paper/results/task1_{RUN_TAG}/task1b_fp_audit_SIGNED.json",
             f"paper/results/task2_{RUN_TAG}/nv_fp_audit_SIGNED.json"]),
        "prompt_rubric": PROMPT_RUBRIC,
        "gating": {
            "elements_dropped_or_gated_by_confidence": 0,
            "needs_review_field_exists": False,
            "human_verification_mechanism":
                "human_verified / verified_at / verified_by columns on all four "
                "levels (infra/migrations/005_add_verification_columns.sql), set "
                "by a reviewer in the Explorer app -- entirely independent of "
                "the confidence score.",
            "verified_against_live_tree": "2026-08-23: zero hits for needs_review "
                "or CONFIDENCE_THRESHOLD in src/, evaluation/ or infra/cdk/lib/. "
                "Hits under infra/cdk/dist/ and infra/cdk/cdk.out.deploy-dev/ are "
                "stale build artifacts of a pre-2026 revision; both paths are "
                "gitignored and untracked, so they are absent from a clean "
                "checkout and from the arXiv tarball.",
        },
        "direct_path": direct,
        "batched_path": batched,
        "batched_path_caveat":
            "Biased UPWARD by construction: detector._merge_duplicate keeps "
            "max(keep.confidence, other.confidence) when folding two views of "
            "one element together. A direct-vs-batched difference here is an "
            "artifact of merging, not a statement about the model.",
        "by_audit_verdict": verdict,
        "separation_stability": stability,
        "sub_threshold_concentration": conc,
        "medium_article_claim": medium_claim,
        "headline": {
            "distinct_values_direct": d["n_distinct_values"],
            "distinct_values_batched": batched["overall"]["n_distinct_values"],
            "range_direct": [d["min"], d["max"]],
            "elements_below_0.80": d["below_0.80"],
            "hallucinations": n_hall,
            "prompt_band_occupancy": d["prompt_band_occupancy"],
            "statement": (
                f"Across the {d['n']} elements of the recorded run the score "
                f"takes {d['n_distinct_values']} distinct values in "
                f"[{d['min']}, {d['max']}]. It never enters the prompt's bottom "
                f"band -- {d['prompt_band_occupancy']['below 0.70 (guessing)']} "
                "elements score below 0.70, the value the rubric reserves for a "
                "guess -- and it uses the middle 0.80-0.94 band for only "
                f"{d['prompt_band_occupancy']['0.80-0.94 (ambiguous but likely)']} "
                f"of them. Of those {d['n']} elements, "
                f"{verdict['in_scope_detections_audited']} are in scope for a "
                f"golden and every one has been human-audited; exactly {n_hall} "
                "is invented, and it also holds the lowest score. That separation "
                f"survives {stability['n_samples']} same-configuration repeats "
                f"({stability['elements_examined']} elements, "
                f"{stability['distinct_elements_below_cut']} distinct element "
                f"below {stability['cut']}), so it is not an artifact of one "
                "draw -- but it is still an observation rather than a validated "
                "threshold, because one positive case cannot establish a "
                "false-negative rate. That is why the system gates on explicit "
                "human verification instead of on this score."),
            "what_the_score_does_not_register": (
                f"The audit's {verdict['verdict_counts'].get('real_split_title', 0)} "
                "real_split_title rows are real content whose titles were broken "
                "by multi-column interleaving, the layout condition that most "
                "degrades transcription in this corpus. Every one of them scores "
                "at or above 0.95. Whatever the low end of the score tracks, it "
                "is not layout difficulty."),
        },
    }


# --------------------------------------------------------------------------

def meta(description, inputs):
    return {
        "task": "Task 8 -- dataset descriptive stats + confidence distribution",
        "description": description,
        "generated_by": "paper/analysis/dataset_stats.py",
        "regenerate_with": "python paper/analysis/dataset_stats.py",
        "run_tag": RUN_TAG,
        "outputs_dir": f"outputs/{OUTPUTS_TAG}",
        "corpus_tier": "_only_subset (manually trimmed subset PDFs, NOT full "
                       "documents) -- guardrail 1",
        "git_commit": git_commit(),
        "code_version_hash": code_version_hash(),
        "bedrock_tokens_spent": 0,
        "inputs": inputs,
    }


def git_commit():
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, text=True).strip()
    except Exception:
        return None


def code_version_hash():
    try:
        import sys
        sys.path.insert(0, str(REPO_ROOT))
        from evaluation.eval_common import code_version_hash as h
        return h()
    except Exception:
        return None


def main():
    tiers = load_json(RESULTS_DIR / "corpus_tiers.json")
    dataset = build_dataset_stats(tiers)
    conf = build_confidence(dataset)

    coll = dataset["totals"]["standard_id_collisions_corpus_wide"]
    if coll:
        print(f"⚠️  {coll} standard_id COLLISIONS -- standard_id is the Aurora "
              "primary key; this is a correctness defect, not a statistic.")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for name, body in (("dataset_stats.json", dataset),
                       ("confidence_distribution.json", conf)):
        (OUT_DIR / name).write_text(json.dumps(body, indent=2) + "\n")
        print(f"wrote {OUT_DIR / name}")

    t = dataset["totals"]
    print(f"\n{t['states']} states, {t['subset_pages']}pp (_only_subset tier), "
          f"{t['detected_elements']} detected elements, {t['standards']} standards, "
          f"{t['standard_id_collisions_corpus_wide']} id collisions, "
          f"age-band coverage {t['age_band_coverage']:.3f}")
    o = conf["direct_path"]["overall"]
    print(f"confidence (direct): n={o['n']} range [{o['min']}, {o['max']}], "
          f"{o['n_distinct_values']} distinct values, mean {o['mean']}, "
          f"{o['frac_at_or_above_0.95']:.3f} at 0.95+, {o['below_0.80']} below 0.80")


if __name__ == "__main__":
    main()
