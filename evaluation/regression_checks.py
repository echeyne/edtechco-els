"""Regression check functions referenced by golden_set `regression_cases`.

Each function name == the `id` field on a regression case (lowercased,
hyphens → underscores). Each takes the live detector output (list of
element dicts) and returns (passed: bool, detail: str).

Add a new check by:
1. Adding the case to the golden-set JSON.
2. Defining a function named `check_<lower_snake_id>` here.
The eval suite logs SKIP if a case has no matching function.
"""

from __future__ import annotations

import re
from typing import Callable, Dict, List, Tuple

CheckFn = Callable[[List[dict]], Tuple[bool, str]]


# ------- CA -------

def check_ca_age_columns_emitted(elements: List[dict]) -> Tuple[bool, str]:
    # Only the Early/Later age-band scheme is in scope here. CA's ELD domain
    # uses a different 3-way column scheme (Discovering/Developing/Broadening),
    # so foundations carrying only those bands are not Early/Later foundations
    # and must not be flagged. The bug this guards is collapsing a foundation's
    # Early and Later columns into one indicator.
    by_code: Dict[str, set] = {}
    for e in elements:
        if e.get("level") != "indicator":
            continue
        code = (e.get("code") or "").strip()
        ab = (e.get("age_band") or "").strip()
        if not code:
            continue
        by_code.setdefault(code, set()).add(ab)

    in_scope = 0
    bad = []
    for c, bands in by_code.items():
        has_early = any("Early" in b for b in bands)
        has_later = any("Later" in b for b in bands)
        if not (has_early or has_later):
            continue  # different column scheme — not this check's concern
        in_scope += 1
        if not (has_early and has_later):
            bad.append(c)
    if bad:
        return False, f"{len(bad)} Early/Later foundations missing a column: {bad[:5]}{'…' if len(bad) > 5 else ''}"
    return True, f"all {in_scope} Early/Later foundations emit both columns"


def check_ca_age_label_not_in_title(elements: List[dict]) -> Tuple[bool, str]:
    leak = [e for e in elements
            if e.get("level") == "indicator"
            and re.search(r"\b(Early|Later)\s*\(", e.get("title", ""))]
    if leak:
        return False, f"{len(leak)} indicator titles contain age-band label, e.g. {leak[0].get('title')!r}"
    return True, "no age-band labels in titles"


def check_ca_no_lettered_examples_as_indicators(elements: List[dict]) -> Tuple[bool, str]:
    pat = re.compile(r"^\s*[a-z]\.\s")
    leak = [e for e in elements
            if e.get("level") == "indicator"
            and pat.match(e.get("source_text", ""))]
    if leak:
        return False, f"{len(leak)} lettered examples emitted as indicators, e.g. {leak[0].get('source_text', '')[:80]!r}"
    return True, "no lettered examples emitted as indicators"


def check_ca_four_level_hierarchy(elements: List[dict]) -> Tuple[bool, str]:
    levels = {e.get("level") for e in elements}
    expected = {"domain", "strand", "sub_strand", "indicator"}
    missing = expected - levels
    if missing:
        return False, f"missing levels: {missing}"
    return True, "all four levels present"


# ------- CO -------

def check_co_no_sub_strand(elements: List[dict]) -> Tuple[bool, str]:
    bad = [e for e in elements if e.get("level") == "sub_strand"]
    if bad:
        sample = [(e.get("code"), e.get("title")) for e in bad[:5]]
        return False, f"{len(bad)} unexpected sub_strands present: {sample}"
    return True, "no sub_strands (correct for CO)"


def check_co_numeric_strands(elements: List[dict]) -> Tuple[bool, str]:
    pat = re.compile(r"^\s*\d+\.\s+[A-Z].*:")
    misclassified = [e for e in elements
                     if pat.match(e.get("source_text", ""))
                     and e.get("level") != "strand"]
    if misclassified:
        sample = [(e.get("level"), e.get("code"), e.get("title")) for e in misclassified[:5]]
        return False, f"{len(misclassified)} numeric-prefixed sections classified as non-strand: {sample}"
    return True, "all numeric-prefixed sections correctly classified as strand"


def check_co_indicator_parent_is_strand(elements: List[dict]) -> Tuple[bool, str]:
    # This check needs parser output; the detector eval has no parentage info.
    # The real check is check_parser_co_indicator_parent_is_strand, run by
    # eval_parser.py. Here (detector context) it is a no-op.
    return True, "deferred to parser-output check (see eval_parser.py)"


# ------- TX -------

def check_tx_pk3_pk4_distinct(elements: List[dict]) -> Tuple[bool, str]:
    pk3 = [e for e in elements
           if e.get("level") == "indicator" and (e.get("code") or "").startswith("PK3.")]
    pk4 = [e for e in elements
           if e.get("level") == "indicator" and (e.get("code") or "").startswith("PK4.")]
    if not pk3 or not pk4:
        return False, f"PK3 count={len(pk3)}, PK4 count={len(pk4)} (both should be > 0)"
    return True, f"PK3 count={len(pk3)}, PK4 count={len(pk4)}"


def check_tx_age_band_set(elements: List[dict]) -> Tuple[bool, str]:
    inds = [e for e in elements if e.get("level") == "indicator"]
    bad = [e for e in inds if e.get("age_band") not in ("PK3", "PK4")]
    if bad:
        return False, f"{len(bad)}/{len(inds)} indicators have age_band != PK3/PK4 (e.g. {bad[0].get('age_band')!r})"
    return True, f"all {len(inds)} indicators have a valid age_band"


def check_tx_no_column_header_as_indicator(elements: List[dict]) -> Tuple[bool, str]:
    bad_titles = {"PK3 Outcome", "PK4 Outcome", "PK3", "PK4"}
    bad = [e for e in elements
           if e.get("level") == "indicator" and (e.get("title") or "").strip() in bad_titles]
    if bad:
        return False, f"{len(bad)} column headers emitted as indicators"
    return True, "no column headers emitted as indicators"


# ------- AZ -------

def check_az_no_lettered_examples(elements: List[dict]) -> Tuple[bool, str]:
    pat = re.compile(r"^\s*[a-z]\.\s")
    bad = [e for e in elements
           if e.get("level") == "indicator" and pat.match(e.get("source_text", ""))]
    if bad:
        return False, f"{len(bad)} lettered examples emitted as indicators"
    return True, "no lettered examples emitted as indicators"


def check_az_no_examples_header_as_element(elements: List[dict]) -> Tuple[bool, str]:
    needle = "Indicators and Examples in the Context"
    bad = [e for e in elements if needle in (e.get("title") or "")]
    if bad:
        return False, f"{len(bad)} 'Indicators and Examples' section headers emitted as elements"
    return True, "no examples-section headers emitted"


def check_az_four_level_hierarchy(elements: List[dict]) -> Tuple[bool, str]:
    return check_ca_four_level_hierarchy(elements)


# ======================================================================
# PARSER checks
#
# These take the parser output (list of serialized NormalizedStandard dicts,
# i.e. ParseResult.indicators) rather than detector elements. Each is keyed by
# `check_parser_<lower_snake_id>` and looked up via `lookup_parser` so a case id
# can mean different things in detector vs parser context (e.g.
# CO-INDICATOR-PARENT-IS-STRAND is a no-op for the detector but a real check
# here).
#
# Shape of each item: {standard_id, domain:{code,name}, strand:{...}|None,
#                      sub_strand:{...}|None, indicator:{code,name}, age_band, ...}
# ======================================================================

def _code(level: Optional[dict]) -> Optional[str]:
    return (level or {}).get("code") if isinstance(level, dict) else None


def _distinct_within_code_groups(indicators: List[dict]) -> Tuple[bool, str]:
    """For every group of standards sharing the same (domain_code, indicator
    code), assert their standard_ids and age_bands are all distinct — i.e.
    age-band variants of one indicator survived parsing as separate standards
    instead of collapsing onto one id."""
    groups: Dict[Tuple[Optional[str], Optional[str]], List[dict]] = {}
    for ind in indicators:
        key = (_code(ind.get("domain")), _code(ind.get("indicator")))
        groups.setdefault(key, []).append(ind)

    bad = []
    multi = 0
    for key, members in groups.items():
        if len(members) < 2:
            continue
        multi += 1
        ids = [m.get("standard_id") for m in members]
        bands = [m.get("age_band") for m in members]
        if len(set(ids)) != len(ids) or len(set(bands)) != len(bands):
            bad.append((key, ids))
    if bad:
        return False, f"{len(bad)} multi-variant indicator code(s) collapsed/duplicated, e.g. {bad[0]}"
    return True, f"{multi} multi-variant indicator code(s) all kept distinct ids+bands"


def check_parser_co_indicator_parent_is_strand(indicators: List[dict]) -> Tuple[bool, str]:
    """Every CO indicator's parent is a strand: sub_strand is null and strand
    is non-null (CO is a 3-level document with no sub_strands)."""
    bad = [
        i for i in indicators
        if i.get("sub_strand") is not None or i.get("strand") is None
    ]
    if bad:
        ex = bad[0]
        return False, (
            f"{len(bad)}/{len(indicators)} indicators have wrong parent "
            f"(e.g. {_code(ex.get('indicator'))!r}: strand={_code(ex.get('strand'))!r}, "
            f"sub_strand={_code(ex.get('sub_strand'))!r})"
        )
    return True, f"all {len(indicators)} indicators have a strand parent and null sub_strand"


def check_parser_ca_early_later_distinct_ids(indicators: List[dict]) -> Tuple[bool, str]:
    """CA Foundations with Early/Later columns must survive as separate
    standards with distinct standard_ids (and distinct age_bands)."""
    return _distinct_within_code_groups(indicators)


def check_parser_tx_pk3_pk4_distinct_ids(indicators: List[dict]) -> Tuple[bool, str]:
    """TX PK3/PK4 variants of an outcome must survive as separate standards
    with distinct standard_ids (and distinct age_bands)."""
    return _distinct_within_code_groups(indicators)


def check_parser_no_id_collision(indicators: List[dict]) -> Tuple[bool, str]:
    """Every standard_id is unique across the whole parser output."""
    ids = [i.get("standard_id") for i in indicators]
    seen, dupes = set(), []
    for sid in ids:
        if sid in seen:
            dupes.append(sid)
        seen.add(sid)
    if dupes:
        uniq = sorted(set(dupes))
        return False, f"{len(dupes)} colliding standard_id(s): {uniq[:5]}{'…' if len(uniq) > 5 else ''}"
    return True, f"all {len(ids)} standard_ids unique"


# ------- registry -------

def _id_to_fn_name(case_id: str) -> str:
    return "check_" + case_id.lower().replace("-", "_")


def lookup(case_id: str) -> CheckFn | None:
    """Detector-stage check for a case id (check_<id>)."""
    return globals().get(_id_to_fn_name(case_id))


def lookup_parser(case_id: str) -> CheckFn | None:
    """Parser-stage check for a case id (check_parser_<id>)."""
    return globals().get("check_parser_" + case_id.lower().replace("-", "_"))
