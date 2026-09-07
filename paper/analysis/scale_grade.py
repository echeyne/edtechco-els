"""Grade a detection-exhaustive golden INSIDE a larger-tier run (arXiv Task 9).

The problem this solves
-----------------------
Every quality number in the paper is computed at the ``_only_subset`` tier.
The obvious objection is that subset-tier quality may not survive at scale:
a larger run chunks further, and chunk boundaries are exactly where a detector
can duplicate an element or lose one. The paper says so itself, and names this
as the cheapest measurement that would answer it.

No new annotation is needed. A golden that is **detection-exhaustive over its
subset pages** stays exhaustive over the SAME pages when those pages are re-run
as part of a larger document -- the pages did not change, only their
neighbourhood did. So:

  * **Recall** is graded exactly as at subset tier: every golden element must
    still be found.
  * **Precision is meaningful**, which it is not elsewhere in this paper,
    because inside the in-scope window the golden annotates everything. An
    unmatched detection there is a genuine false positive, not an artifact of
    partial annotation.
  * **Cross-boundary duplication shows up as a precision drop**, which is the
    specific failure the objection is about.

How the page window is derived
------------------------------
The golden's ``source_page`` values are ``_only_subset`` PDF page numbers; the
run's are the larger tier's. ``paper/results/corpus_page_ranges.json`` records,
per state per tier, the PUBLISHED page each tier page came from. Composing the
subset map with the inverse of the target-tier map translates one to the other
deterministically -- no model call, no annotation, no guesswork. A subset page
that has no counterpart in the target tier is reported, never silently dropped.

What is NOT claimed
-------------------
This measures the subset pages *inside* a bigger run. It is not a full-document
quality number, and the out-of-window elements of the larger run remain
unannotated and ungraded -- they are counted and reported, not scored. A state
whose golden is not detection-exhaustive (everything except Kentucky) gets
recall and an explicitly-labelled coverage-artifact precision; the file refuses
to present that as a quality figure. Colorado is deliberately in that category
and is staying there (2026-09-06): its seven-element spot-check golden is not
being extended, so it contributes recall and duplication evidence only.

Usage
-----
    python -m paper.analysis.scale_grade --state KY \
        --detection outputs/scale-08-29-26/KY-detection.json
    python -m paper.analysis.scale_grade --state KY --state CO \
        --detection-dir outputs/scale-08-29-26 --out paper/results/task9_YYYYMMDD
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from evaluation.eval_common import _norm_age_band, code_version_hash  # noqa: E402
from evaluation.eval_detector import (  # noqa: E402
    _match_key,
    _tag_domains,
    _title_key,
    grade_elements,
    report_to_dict,
)

PAGE_RANGES = REPO / "paper" / "results" / "corpus_page_ranges.json"

# Which goldens may have their PRECISION read as a quality figure. A golden is
# detection-exhaustive when it annotates every element the detector should emit
# on its pages -- not merely every element the document prints. Kentucky is the
# only one; Nevada's is content-exhaustive, which is a different property (it
# annotates every DISTINCT structural element, so legitimate repeats of one
# element across pages are unannotated and would score as false positives).
# See sections/discussion_limitations.tex.
DETECTION_EXHAUSTIVE = {"KY"}


# ---------------------------------------------------------------- page mapping

def _tier_to_published(state: str, tier: str, ranges: dict) -> Dict[int, int]:
    """1-indexed tier page -> published page, from the recorded ranges."""
    try:
        entry = ranges["states"][state]["tiers"][tier]
    except KeyError as exc:  # pragma: no cover - operator error
        raise SystemExit(
            f"{state}: no '{tier}' tier recorded in {PAGE_RANGES.name}"
        ) from exc
    pages = entry["published_pages_in_tier_order"]
    unmatched = entry.get("unmatched_tier_pages") or []
    if unmatched:
        print(
            f"  ! {state}/{tier}: {len(unmatched)} tier page(s) matched no "
            f"published page and are excluded: {unmatched}"
        )
    return {i + 1: p for i, p in enumerate(pages)}


def build_page_map(
    state: str, ranges: dict, source_tier: str, target_tier: str
) -> Tuple[Dict[int, int], List[int]]:
    """Map source-tier page numbers onto target-tier page numbers.

    Returns ``(mapping, unmappable_source_pages)``. A source page whose
    published page does not appear in the target tier is UNMAPPABLE and is
    returned rather than dropped: it would otherwise silently shrink the graded
    window and inflate recall.
    """
    src = _tier_to_published(state, source_tier, ranges)
    tgt = _tier_to_published(state, target_tier, ranges)
    # Invert the target map. A published page duplicated in the target tier is
    # a real possibility (a running section header reprinted); take the first.
    pub_to_tgt: Dict[int, int] = {}
    for tier_page, pub in sorted(tgt.items()):
        pub_to_tgt.setdefault(pub, tier_page)

    mapping: Dict[int, int] = {}
    unmappable: List[int] = []
    for src_page, pub in sorted(src.items()):
        if pub in pub_to_tgt:
            mapping[src_page] = pub_to_tgt[pub]
        else:
            unmappable.append(src_page)
    return mapping, unmappable


# ------------------------------------------------------------------- filtering

def slice_to_window(
    detected: List[dict], window: set, tolerance: int = 0
) -> List[dict]:
    """Detections whose ``source_page`` falls in the target-tier window.

    ``tolerance`` widens the window by N pages on each side. It exists as a
    SENSITIVITY CHECK, not as a default: an element straddling a page break can
    be attributed to either side, so a strict window can manufacture a false
    negative. Results are reported at tolerance 0 and 1 so the reader can see
    whether any conclusion depends on the choice.
    """
    if tolerance:
        window = {p + d for p in window for d in range(-tolerance, tolerance + 1)}
    return [d for d in detected if d.get("source_page") in window]


def recall_decomposition(golden: List[dict], in_window: List[dict]) -> dict:
    """Localize a recall miss: absent element, or age-band attribution drift?

    ``_match_key`` is ``(domain, level, title, age_band)``. A run that finds an
    element but stamps a different ``age_band`` on it fails that key exactly as
    a run that never emitted it does -- and at scale those two have completely
    different causes and completely different fixes. This reports both, so a
    headline recall number can never be read as "the detector lost elements"
    when what actually moved was age-band attribution.

    This does NOT loosen the matcher. The graded recall stays the strict
    ``_match_key``; this is a diagnostic beside it, in the same spirit as
    ``compare_description`` separating ``truncated`` from ``mismatch``.
    """
    by_title: Dict[tuple, List[dict]] = defaultdict(list)
    for d in in_window:
        by_title[((d.get("level") or "").strip(), _title_key(d))].append(d)

    # Same level, title starts with the golden's title -- the element was
    # found, but extra text (typically the description that follows a colon)
    # was folded into `title`. That is composition drift, not a lost element,
    # and it is the leaf-level counterpart of compare_description's
    # `truncated` classification.
    by_level: Dict[str, List[dict]] = defaultdict(list)
    for d in in_window:
        by_level[(d.get("level") or "").strip()].append(d)

    absent, age_band_drift, title_drift = [], [], []
    for g in golden:
        key = ((g.get("level") or "").strip(), _title_key(g))
        hits = by_title.get(key, [])
        if not hits:
            gt = _title_key(g)
            near = [
                d for d in by_level[(g.get("level") or "").strip()]
                if gt and len(gt) >= 8 and _title_key(d).startswith(gt)
            ]
            if near:
                title_drift.append({
                    "test_case_id": g.get("test_case_id"),
                    "level": g.get("level"),
                    "golden_title": (g.get("title") or "")[:70],
                    "run_title": (near[0].get("title") or "")[:140],
                    "target_tier_page": near[0].get("source_page"),
                })
                continue
            absent.append({
                "test_case_id": g.get("test_case_id"),
                "level": g.get("level"),
                "source_page": g.get("source_page"),
                "title": (g.get("title") or "")[:90],
            })
            continue
        golden_ab = _norm_age_band(g.get("age_band"))
        run_abs = {_norm_age_band(h.get("age_band")) for h in hits}
        if golden_ab not in run_abs:
            age_band_drift.append({
                "test_case_id": g.get("test_case_id"),
                "level": g.get("level"),
                "title": (g.get("title") or "")[:60],
                "golden_age_band": golden_ab,
                "run_age_band": sorted(x for x in run_abs if x is not None),
                "target_tier_pages": [h.get("source_page") for h in hits],
            })
    return {
        "found_by_level_and_title": len(golden) - len(absent) - len(title_drift),
        "n_golden": len(golden),
        "recall_ignoring_age_band": round(
            (len(golden) - len(absent) - len(title_drift)) / len(golden), 4)
        if golden else None,
        "recall_ignoring_age_band_and_title_composition": round(
            (len(golden) - len(absent)) / len(golden), 4) if golden else None,
        "absent_from_window": absent,
        "age_band_attribution_drift": age_band_drift,
        "title_composition_drift": title_drift,
        "_reading": (
            "`absent_from_window` is detection loss at scale -- the failure the "
            "scale objection is about. `age_band_attribution_drift` is an "
            "element that WAS found, carrying a different age_band than the "
            "golden annotates; it fails the strict key but is not a lost "
            "element, and the fix is an annotation or canonicalization "
            "question, not a detection one. `title_composition_drift` is an "
            "element found at the right level whose `title` swallowed trailing "
            "text -- also found, also not lost."
        ),
    }


def age_band_consistency(in_window: List[dict]) -> dict:
    """How consistently the run stamps age_band, per page.

    A page whose elements split between a banded and a null value is emitting
    two spellings of one fact about that page, which is the shape of the
    problem rather than a property of any element on it.
    """
    per_page: Dict[int, Counter] = defaultdict(Counter)
    for d in in_window:
        per_page[d.get("source_page")][_norm_age_band(d.get("age_band"))] += 1
    split = {p: dict(c) for p, c in per_page.items() if len(c) > 1}
    return {
        "distinct_values_in_window": dict(
            Counter(_norm_age_band(d.get("age_band")) for d in in_window)
        ),
        "pages_emitting_more_than_one_value": {str(k): v for k, v in sorted(
            split.items(), key=lambda kv: (kv[0] is None, kv[0]))},
        "n_pages_split": len(split),
    }


_WORD_RE = re.compile(r"[a-z0-9]+")

# A title counts as present on the page when this fraction of its DISTINCT
# words is, and it must carry at least this many distinct words for the test to
# mean anything. Both are deliberately loose: the question here is "is this
# content on the page at all", not "is this a byte-exact quotation".
GROUNDING_COVERAGE = 0.9
GROUNDING_MIN_WORDS = 4


def _extraction_index(extraction_path: Optional[Path]) -> Optional[dict]:
    """Text of a source-tier extraction, in the two forms grounding needs.

    ⚠️ Contiguous-substring grounding CANNOT work on a multi-column document.
    Extraction flattens a page into one reading order, so a sentence in the
    left column is interleaved with the right column's lines: Colorado's
    "Complete personal care tasks, such" and its continuation "as dressing,
    brushing teeth, toileting," are two blocks apart with other-column text
    between them. Grading that as an ungrounded detection would manufacture 39
    hallucinations out of a layout property, in the state whose layout the
    paper elsewhere identifies as the hard case.

    So two forms are kept: the joined string (an exact hit is the strongest
    evidence and is labelled as such) and the word multiset (which is immune to
    reading order). Neither reads any document's vocabulary -- both are the
    same class of shape-only check the pipeline's own helpers use.
    """
    if not extraction_path or not extraction_path.exists():
        return None
    doc = json.loads(extraction_path.read_text())
    joined = " ".join(
        " ".join((b.get("text") or "").split()) for b in doc.get("blocks", [])
    ).lower()
    return {"joined": joined, "words": set(_WORD_RE.findall(joined))}


def _grounding(probe: Optional[str], index: dict) -> Tuple[bool, str, float]:
    """Is ``probe`` present in the extraction? Returns (grounded, how, coverage)."""
    text = " ".join((probe or "").split()).lower().rstrip(".")
    if len(text) < 12:
        return False, "probe too short to test", 0.0
    if text in index["joined"]:
        return True, "exact", 1.0
    words = set(_WORD_RE.findall(text))
    if len(words) < GROUNDING_MIN_WORDS:
        return False, "too few distinct words to test", 0.0
    coverage = len(words & index["words"]) / len(words)
    if coverage >= GROUNDING_COVERAGE:
        return True, "token coverage", round(coverage, 3)
    return False, "not found", round(coverage, 3)


def adjudicate_unmatched(
    golden: List[dict], in_window: List[dict], index: Optional[dict]
) -> dict:
    """Classify every in-window detection the golden does not account for.

    ⚠️ This is the check that decides what a precision number MEANS, and it is
    the reason precision at scale must not be read off the headline alone.

    "Detection-exhaustive" as this corpus uses it means the golden accounts for
    every element THAT RUN emitted -- Kentucky's 44 against the subset run's 44.
    It does not mean the golden annotates every element the PAGE contains. A
    larger run over the same pages can therefore emit real, correctly-grounded
    content the golden simply never had occasion to cover, and that content
    scores as a false positive while being nothing of the kind.

    So each unmatched detection is split by whether its own words are present
    in the SOURCE-TIER extraction:

      * ``grounded_unannotated`` -- the text is on the page. This is not a
        hallucination. It is either real content the subset run missed, or a
        mis-levelled duplicate of something the golden does annotate; only an
        annotator can say which, so it is emitted as a worklist rather than
        scored either way.
      * ``ungrounded`` -- the text is not in the extraction at all. This is the
        genuine false-positive candidate, and the only bucket a hallucination
        can hide in.

    With no source extraction supplied every unmatched detection is
    ``unadjudicated`` and the precision reading says so.
    """
    gkeys: Counter = Counter(
        ((g.get("level") or "").strip(), _title_key(g)) for g in golden
    )
    used: Counter = Counter()
    unmatched: List[dict] = []
    for d in in_window:
        k = ((d.get("level") or "").strip(), _title_key(d))
        if used[k] < gkeys.get(k, 0):
            used[k] += 1
        else:
            unmatched.append(d)

    grounded, ungrounded, unadjudicated = [], [], []
    for d in unmatched:
        row = {
            "level": d.get("level"),
            "code": d.get("code"),
            "title": (d.get("title") or "")[:120],
            "target_tier_page": d.get("source_page"),
            "age_band": d.get("age_band"),
        }
        if index is None:
            unadjudicated.append(row)
            continue
        ok, how, cov = _grounding(d.get("title"), index)
        if not ok:
            ok2, how2, cov2 = _grounding(d.get("source_text"), index)
            if ok2:
                ok, how, cov = ok2, how2 + " (source_text)", cov2
        row["grounding"] = how
        row["grounding_coverage"] = cov
        (grounded if ok else ungrounded).append(row)

    n_in = len(in_window)
    return {
        "n_in_window": n_in,
        "n_accounted_for_by_golden": n_in - len(unmatched),
        "precision_ignoring_age_band": round((n_in - len(unmatched)) / n_in, 4) if n_in else None,
        "n_grounded_unannotated": len(grounded),
        "n_ungrounded": len(ungrounded),
        "n_unadjudicated": len(unadjudicated),
        "hallucination_candidates": ungrounded,
        "annotation_worklist": grounded,
        "unadjudicated": unadjudicated,
        "_reading": (
            "`hallucination_candidates` is the only bucket that can contain a "
            "false positive in the quality sense. `annotation_worklist` is real "
            "page content the golden does not cover; it BOUNDS how far that "
            "golden is from page-exhaustive, and a precision figure must not be "
            "published from a state where it is non-empty. It is a diagnostic, "
            "not a work queue: a golden is extended by annotating the document, "
            "never by accepting rows this system emitted."
        ),
    }


def _dupe_groups(in_window: List[dict], key) -> dict:
    groups: Dict[tuple, List[dict]] = defaultdict(list)
    for d in in_window:
        groups[key(d)].append(d)
    dupes = {k: v for k, v in groups.items() if len(v) > 1}
    return {
        "duplicate_groups": len(dupes),
        "surplus_detections": sum(len(v) - 1 for v in dupes.values()),
        "by_level": dict(Counter(
            (v[0].get("level") or "").strip()
            for v in dupes.values() for _ in range(len(v) - 1))),
        "examples": [
            {
                "level": (v[0].get("level") or "").strip(),
                "title": (v[0].get("title") or "")[:80],
                "n": len(v),
                "pages": [d.get("source_page") for d in v],
                "codes": [d.get("code") for d in v],
                "age_bands": [d.get("age_band") for d in v],
            }
            for v in sorted(dupes.values(), key=lambda g: -len(g))[:12]
        ],
    }


def duplicate_analysis(in_window: List[dict]) -> dict:
    """Detections of ONE element emitted more than once in the graded window.

    This is the specific failure the scale objection predicts: a larger run
    chunks further, and an element on a chunk boundary can be emitted twice.
    ``_dedup_elements`` is supposed to merge those; anything surviving lands as
    a false positive against an exhaustive golden.

    ⚠️ **Do not key this on ``_match_key``.** That was the first implementation
    and it reported ZERO duplicates on Kentucky while eleven were sitting in the
    window. ``_match_key`` ends in ``age_band``, and the duplicates differ in
    exactly that field -- the same element emitted once banded and once null.
    Keying the duplicate check on the field the duplicates disagree about hides
    every one of them, and it hides them in the direction that flatters the
    system. It is the same defect one level up as the merge's own: whatever key
    ``_dedup_elements`` uses, a duplicate check must be keyed more loosely than
    the merge it is auditing, or it can only ever confirm the merge's own
    opinion of itself.

    So the headline is keyed on ``(level, title)``. The strict figure is kept
    beside it to show the gap, because that gap IS the finding.
    """
    loose = _dupe_groups(
        in_window, lambda d: ((d.get("level") or "").strip(), _title_key(d)))
    strict = _dupe_groups(in_window, _match_key)
    loose["_key"] = "(level, title) — a duplicate is one element emitted twice"
    strict["_key"] = "(domain, level, title, age_band) — the grader's own key"
    return {
        **loose,
        "strict_key_for_comparison": strict,
        "hidden_by_age_band": (
            loose["surplus_detections"] - strict["surplus_detections"]),
        "_reading": (
            "`surplus_detections` is the number of extra copies surviving the "
            "merge. `hidden_by_age_band` is how many of them the grader's own "
            "key cannot see, because the copies disagree on age_band -- which "
            "is also why _dedup_elements did not merge them."
        ),
    }


# -------------------------------------------------------------------- grading

def grade_state(
    state: str,
    golden_path: Path,
    detection_path: Path,
    ranges: dict,
    source_tier: str,
    target_tier: str,
    source_extraction: Optional[Path] = None,
    graded_input_out: Optional[Path] = None,
) -> dict:
    golden_doc = json.loads(golden_path.read_text())
    golden = golden_doc.get("elements", [])
    run = json.loads(detection_path.read_text())
    detected_all = run.get("elements", [])
    src_index = _extraction_index(source_extraction)

    page_map, unmappable = build_page_map(state, ranges, source_tier, target_tier)
    golden_pages = sorted({g.get("source_page") for g in golden} - {None})
    # The graded window is EVERY source-tier page, not only the pages that
    # happen to carry a golden element. Under exhaustive semantics an annotated
    # page with no golden elements asserts that the detector should emit none
    # there, so a detection on it is a real false positive and must be graded.
    window_src = sorted(page_map)
    window_tgt = {page_map[p] for p in window_src}

    orphan_golden_pages = [p for p in golden_pages if p not in page_map]

    # Tag the FULL run in document order first: a page-filtered slice cannot
    # recover its own enclosing domain (see grade_elements(detected_pretagged)).
    _tag_domains(detected_all)

    out: dict = {
        "state": state,
        "source_tier": source_tier,
        "target_tier": target_tier,
        "detection_file": str(detection_path),
        "golden_file": str(golden_path),
        "golden_is_detection_exhaustive": state in DETECTION_EXHAUSTIVE,
        "page_window": {
            "source_tier_pages": window_src,
            "target_tier_pages": sorted(window_tgt),
            "mapping_source_to_target": {str(k): v for k, v in sorted(page_map.items())},
            "unmappable_source_pages": unmappable,
            "golden_pages_outside_the_map": orphan_golden_pages,
        },
        "run_totals": {
            "elements_in_whole_run": len(detected_all),
            "pages_in_run": len({d.get("source_page") for d in detected_all} - {None}),
        },
        "arms": {},
    }

    for tol in (0, 1):
        in_window = slice_to_window(detected_all, window_tgt, tolerance=tol)
        # grade_elements pops the private tag; re-tag from the full run each
        # time so successive arms see the same context.
        by_id = {id(d): d.get("_domain") for d in detected_all}
        for d in in_window:
            d["_domain"] = by_id[id(d)]
        rep = grade_elements(golden, list(in_window), detected_pretagged=True)
        rep.state = state
        d = report_to_dict(rep)
        d["in_scope_elements_at_scale"] = len(in_window)
        d["duplicates"] = duplicate_analysis(in_window)
        d["recall_decomposition"] = recall_decomposition(golden, in_window)
        d["unmatched_adjudication"] = adjudicate_unmatched(golden, in_window, src_index)
        d["age_band_consistency"] = age_band_consistency(in_window)
        out["arms"][f"page_tolerance_{tol}"] = d

        # Persist the EXACT pair of lists that was just graded. Without this
        # the graded input exists only in memory, and a reader auditing a row
        # has to re-derive the page window and the domain tagging by hand
        # before they can even see what the grader saw. Written at every
        # tolerance, because which arm a number came from is part of the
        # number.
        if graded_input_out is not None:
            graded_input_out.mkdir(parents=True, exist_ok=True)
            (graded_input_out / f"{state}_graded_input_tol{tol}.json").write_text(
                json.dumps({
                    "_what_this_is": (
                        "The two lists handed to eval_detector.grade_elements, "
                        "verbatim and in the order they were passed. `golden` is "
                        "the annotation file's `elements` unchanged; `detected` is "
                        "the target-tier run filtered to the page window, carrying "
                        "the `_domain` tag it was graded with (assigned by walking "
                        "the FULL run in document order, not this slice). Grading "
                        "reads nothing else."
                    ),
                    "state": state,
                    "⚠️_what_this_file_may_be_used_for": (
                        "Backs the recall, duplication and hallucination "
                        "findings for this state. It may ALSO be used to "
                        "recompute precision, because its golden is "
                        "detection-exhaustive over this window."
                        if state in DETECTION_EXHAUSTIVE else
                        "Backs the RECALL, DUPLICATION and HALLUCINATION "
                        "findings for this state, and NOTHING ELSE. This "
                        "state's golden is not detection-exhaustive, so most "
                        "of the detections below are simply content it never "
                        "annotated. A precision figure computed from this file "
                        "would measure annotation coverage, not quality. "
                        "Colorado in particular is NOT being annotated "
                        "exhaustively (decided 2026-09-06) and its golden is "
                        "not going to change, so this is a permanent property "
                        "of the file rather than a gap awaiting work."
                    ),
                    "page_tolerance": tol,
                    "_why_two_tolerances": (
                        "Recall conclusions must be identical at tolerance 0 "
                        "and 1; that they are is the sensitivity check. "
                        "Grounding is NOT meaningful at tolerance 1, which "
                        "admits target-tier pages the source tier never "
                        "contained."
                    ),
                    "code_version_hash": code_version_hash(),
                    "provenance": {
                        "golden_file": str(golden_path),
                        "detection_file": str(detection_path),
                        "source_extraction": str(source_extraction) if source_extraction else None,
                        "source_tier": source_tier,
                        "target_tier": target_tier,
                        "target_tier_pages_in_window": sorted(window_tgt),
                        "page_map_source_to_target": {
                            str(k): v for k, v in sorted(page_map.items())},
                    },
                    "counts": {
                        "golden": len(golden),
                        "detected_in_window": len(in_window),
                        "detected_in_whole_run": len(detected_all),
                    },
                    "golden": golden,
                    "detected": in_window,
                }, indent=2, ensure_ascii=False)
            )

        # restore tags for the next arm
        for e in detected_all:
            e["_domain"] = by_id[id(e)]

    strict = out["arms"]["page_tolerance_0"]
    out["headline"] = {
        "recall": strict["recall"],
        "precision": strict["precision"],
        "matched": strict["matched"],
        "n_golden": strict["n_golden"],
        "in_scope_elements_at_scale": strict["in_scope_elements_at_scale"],
        "false_positives": len(strict.get("extra_elements") or []),
        "ignored_out_of_annotated_domain": strict.get("ignored_out_of_scope"),
        "surplus_duplicate_detections": strict["duplicates"]["surplus_detections"],
        "recall_ignoring_age_band": strict["recall_decomposition"]["recall_ignoring_age_band"],
        "elements_absent_at_scale": len(strict["recall_decomposition"]["absent_from_window"]),
        "elements_lost_to_title_composition_drift": len(
            strict["recall_decomposition"]["title_composition_drift"]),
        "elements_lost_to_age_band_drift": len(
            strict["recall_decomposition"]["age_band_attribution_drift"]),
        "precision_ignoring_age_band": strict["unmatched_adjudication"]["precision_ignoring_age_band"],
        "hallucination_candidates": strict["unmatched_adjudication"]["n_ungrounded"],
        "grounded_but_unannotated": strict["unmatched_adjudication"]["n_grounded_unannotated"],
        "source_extraction_supplied": src_index is not None,
        "precision_reading": (
            "quality figure -- golden is detection-exhaustive over this window"
            if state in DETECTION_EXHAUSTIVE
            else "COVERAGE ARTIFACT, not a quality figure -- this golden is not "
            "detection-exhaustive, so an unmatched detection is more likely "
            "unannotated content than a false positive"
        ),
    }
    for e in detected_all:
        e.pop("_domain", None)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--state", action="append", required=True,
                    help="state code; repeatable")
    ap.add_argument("--detection", help="detection JSON (single --state only)")
    ap.add_argument("--detection-dir", help="dir holding <STATE>-detection.json")
    ap.add_argument("--golden-dir", default="evaluation/ground_truth_detector")
    ap.add_argument("--source-tier", default="only_subset",
                    help="tier the golden's source_page values belong to")
    ap.add_argument("--target-tier", default="trimmed",
                    help="tier the detection run processed")
    ap.add_argument("--source-extraction-dir",
                    help="dir holding <STATE>-extraction.json for the SOURCE tier. "
                         "Required to adjudicate unmatched detections as grounded "
                         "page content vs hallucination candidates; without it "
                         "no precision figure from this script is publishable.")
    ap.add_argument("--out",
                    help="directory to write <STATE>_scale_grade.json into. Also "
                         "writes graded_input/<STATE>_graded_input_tol<N>.json — "
                         "the exact golden/detection pair handed to the grader, "
                         "so a row can be audited without re-deriving the window.")
    args = ap.parse_args()

    ranges = json.loads(PAGE_RANGES.read_text())
    results = {}
    for state in args.state:
        if args.detection and len(args.state) == 1:
            det = Path(args.detection)
        elif args.detection_dir:
            det = Path(args.detection_dir) / f"{state}-detection.json"
        else:
            raise SystemExit("pass --detection (one state) or --detection-dir")
        golden = Path(args.golden_dir) / f"{state}.json"
        print(f"\n=== {state}: {args.source_tier} golden inside {args.target_tier} run ===")
        src_ex = Path(args.source_extraction_dir) / f"{state}-extraction.json" \
            if args.source_extraction_dir else None
        res = grade_state(state, golden, det, ranges,
                          args.source_tier, args.target_tier,
                          source_extraction=src_ex,
                          graded_input_out=Path(args.out) / "graded_input"
                          if args.out else None)
        results[state] = res
        h = res["headline"]
        print(f"  window (target tier pages): {res['page_window']['target_tier_pages']}")
        print(f"  run holds {res['run_totals']['elements_in_whole_run']} elements; "
              f"{h['in_scope_elements_at_scale']} fall inside the window")
        print(f"  recall    {h['recall']:.3f}  ({h['matched']}/{h['n_golden']})")
        print(f"  precision {h['precision']:.3f}  "
              f"({h['false_positives']} FP, {h['ignored_out_of_annotated_domain']} "
              f"outside an annotated domain)")
        print(f"  recall ignoring age_band: {h['recall_ignoring_age_band']:.3f}  "
              f"({h['elements_absent_at_scale']} absent, "
              f"{h['elements_lost_to_age_band_drift']} age-band drift, "
              f"{h['elements_lost_to_title_composition_drift']} title drift)")
        print(f"  precision ignoring age_band: {h['precision_ignoring_age_band']:.3f}  "
              f"({h['grounded_but_unannotated']} grounded-but-unannotated, "
              f"{h['hallucination_candidates']} hallucination candidates)")
        print(f"  duplicates surviving the merge: {h['surplus_duplicate_detections']}")
        print(f"  precision reading: {h['precision_reading']}")

    if args.out:
        outdir = Path(args.out)
        outdir.mkdir(parents=True, exist_ok=True)
        for state, res in results.items():
            res["code_version_hash"] = code_version_hash()
            (outdir / f"{state}_scale_grade.json").write_text(
                json.dumps(res, indent=2, ensure_ascii=False)
            )
        print(f"\nwrote {len(results)} file(s) to {outdir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
