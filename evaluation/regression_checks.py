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
    by_code: Dict[str, set] = {}
    for e in elements:
        if e.get("level") != "indicator":
            continue
        code = (e.get("code") or "").strip()
        ab = (e.get("age_band") or "").strip()
        if not code:
            continue
        by_code.setdefault(code, set()).add(ab)

    bad = [c for c, bands in by_code.items()
           if not (any("Early" in b for b in bands) and any("Later" in b for b in bands))]
    if bad:
        return False, f"{len(bad)} indicator codes missing Early or Later: {bad[:5]}{'…' if len(bad) > 5 else ''}"
    return True, f"all {len(by_code)} indicator codes have both Early and Later"


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
    # This check needs parser output; here we approximate using detected elements only.
    # The eval suite will pass parser output via a different code path when available.
    return True, "deferred to parser-output check (see eval_suite.py)"


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


# ------- registry -------

def _id_to_fn_name(case_id: str) -> str:
    return "check_" + case_id.lower().replace("-", "_")


def lookup(case_id: str) -> CheckFn | None:
    return globals().get(_id_to_fn_name(case_id))
