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
from typing import Callable, Dict, List, Optional, Tuple

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

def check_az_no_examples_header_as_element(elements: List[dict]) -> Tuple[bool, str]:
    needle = "Indicators and Examples in the Context"
    bad = [e for e in elements if needle in (e.get("title") or "")]
    if bad:
        return False, f"{len(bad)} 'Indicators and Examples' section headers emitted as elements"
    return True, "no examples-section headers emitted"


def check_az_four_level_hierarchy(elements: List[dict]) -> Tuple[bool, str]:
    return check_ca_four_level_hierarchy(elements)


# ------- KY -------

def check_ky_benchmark_is_sub_strand(elements: List[dict]) -> Tuple[bool, str]:
    """`Benchmark N.N` is KY's third level: it must land on sub_strand.

    Two halves: (1) every element whose source_text starts with `Benchmark `
    is a sub_strand, and (2) no element at any other level carries a code
    starting with `Benchmark `.
    """
    src_pat = re.compile(r"^\s*Benchmark\s")
    code_pat = re.compile(r"^\s*Benchmark\s")

    from_src = [e for e in elements
                if src_pat.match(e.get("source_text") or "")
                and e.get("level") != "sub_strand"]
    from_code = [e for e in elements
                 if code_pat.match(e.get("code") or "")
                 and e.get("level") != "sub_strand"]

    seen_ids = {id(e) for e in from_src}
    bad = from_src + [e for e in from_code if id(e) not in seen_ids]
    total = len([e for e in elements
                 if src_pat.match(e.get("source_text") or "")
                 or code_pat.match(e.get("code") or "")])
    if bad:
        ex = bad[0]
        return False, (
            f"{len(bad)}/{total} Benchmark elements are not sub_strand "
            f"(e.g. level={ex.get('level')!r}, code={ex.get('code')!r}, "
            f"title={(ex.get('title') or '')[:60]!r})"
        )
    return True, f"all {total} Benchmark elements classified as sub_strand"


def check_ky_four_level_hierarchy(elements: List[dict]) -> Tuple[bool, str]:
    return check_ca_four_level_hierarchy(elements)


# Prompt rule 4's first case: a `<Label words> <numeral>: <Title>` heading whose
# label-and-id IS the code. Anchored on the numeral so it can't swallow a
# title:description colon (CO's `1. Health, Safety and Nutrition: The
# maintenance of ...`) — those have no numeral immediately before the colon and
# are simply out of scope here.
_LABELLED_HEADING_RE = re.compile(r"^([A-Za-z][^:\n]{0,70}?\s\d+(?:\.\d+)*)\s*:\s")


def check_ky_strand_code_keeps_full_label(elements: List[dict]) -> Tuple[bool, str]:
    """A labelled heading's code is the WHOLE label, not a truncation of it.

    KY spells every strand as `<Domain Name> Standard N:`. The code is that
    entire span; dropping the leading words yields a bare `Standard 2` that no
    longer identifies which domain's Standard 2 it is, and collides with the
    other domains' as soon as two of them truncate in the same run. Observed on
    2026-08-13: 4 of 5 KY strands kept the full label and the fifth did not,
    from one temperature-0 run — so this is a determinism guard, not a
    correctness-in-principle one.

    Compared case-insensitively: a document that shouts its heading (AZ's
    `STRAND 1`) is not a truncation, and the detector is right to title-case it.
    """
    checked, bad = 0, []
    for e in elements:
        m = _LABELLED_HEADING_RE.match((e.get("source_text") or "").strip())
        if not m:
            continue
        checked += 1
        label = m.group(1).strip()
        code = (e.get("code") or "").strip()
        if code.casefold() != label.casefold():
            bad.append((e.get("level"), code, label))
    if not checked:
        return False, "no '<Label> N:' headings found to check"
    if bad:
        lvl, code, label = bad[0]
        return False, (
            f"{len(bad)}/{checked} labelled heading(s) lost part of their label, e.g. "
            f"{lvl} code={code!r} should be {label!r}"
        )
    return True, f"all {checked} labelled headings keep their full label as the code"


# ------- NV -------

# NV's indicator tables carry two prose columns and a page footnote, none of
# which are structural. The indicator-group caption `Indicators (SS.ID)` is a
# code label, not a heading, so it must not surface as an element title either.
_NV_NON_STRUCTURAL_TITLE_RE = re.compile(
    r"^\s*(Examples:|Supportive Practices:|Indicators\s*\(|This symbol indicates)"
)


def check_nv_no_column_header_as_element(elements: List[dict]) -> Tuple[bool, str]:
    """Neither prose column, nor the `Indicators (XX.YY)` caption, nor the
    cross-curricular footnote is a standard — and NV has no age columns at all,
    so nothing may carry an age_band."""
    titled = [e for e in elements
              if _NV_NON_STRUCTURAL_TITLE_RE.match(e.get("title") or "")]
    banded = [e for e in elements if e.get("age_band") is not None]
    if titled or banded:
        parts = []
        if titled:
            parts.append(
                f"{len(titled)} non-structural column/caption element(s), e.g. "
                f"{(titled[0].get('title') or '')[:60]!r}"
            )
        if banded:
            parts.append(
                f"{len(banded)} element(s) carry an age_band on a document with no age "
                f"columns, e.g. {banded[0].get('age_band')!r} on "
                f"{(banded[0].get('title') or '')[:50]!r}"
            )
        return False, "; ".join(parts)
    return True, (
        f"{len(elements)} elements: no column headers, captions or footnotes emitted, "
        f"no age_band set"
    )


# The document's own indicator namespace: a 1-2 letter domain root, a dot, and a
# 2-letter group token — `SS.ID`, `S.EO`, `T.CT`. Matched by SHAPE, not by any
# specific NV token, so this reads as "the sub_strand kept the printed code"
# rather than "the sub_strand equals one of seven hard-coded strings".
_NV_SUB_STRAND_CODE_RE = re.compile(r"^[A-Z]{1,2}\.[A-Z]{2}$")


def check_nv_sub_strand_code_from_document(elements: List[dict]) -> Tuple[bool, str]:
    """Each indicator group is captioned with its own code (`Indicators (SS.ID)`).

    That token is the group's document-local code and must win over an invented
    title abbreviation. Two halves: (1) every sub_strand code has the document's
    `XX.YY` shape, and (2) it is a proper dotted prefix of the indicator codes
    beneath it — which is also what guarantees `SS.ID` never collides with
    `SS.ID.PK1`.
    """
    subs = [e for e in elements if e.get("level") == "sub_strand"]
    if not subs:
        return False, "no sub_strand elements detected"

    wrong_shape = [(e.get("code"), (e.get("title") or "")[:40])
                   for e in subs if not _NV_SUB_STRAND_CODE_RE.match(e.get("code") or "")]

    # A sub_strand "owns" an indicator when the indicator's code extends it.
    # With no shape-valid sub_strand codes there is nothing to parent against,
    # so the prefix half only runs on the ones that passed.
    valid = [e.get("code") for e in subs if _NV_SUB_STRAND_CODE_RE.match(e.get("code") or "")]
    orphan_indicators = []
    for e in elements:
        if e.get("level") != "indicator":
            continue
        code = e.get("code") or ""
        root = code.rsplit(".", 1)[0] if "." in code else ""
        if _NV_SUB_STRAND_CODE_RE.match(root) and root not in valid:
            orphan_indicators.append(code)

    if wrong_shape or orphan_indicators:
        parts = []
        if wrong_shape:
            parts.append(
                f"{len(wrong_shape)}/{len(subs)} sub_strand code(s) are invented "
                f"abbreviations rather than the document's caption, e.g. {wrong_shape[0]}"
            )
        if orphan_indicators:
            parts.append(
                f"{len(orphan_indicators)} indicator code(s) have no matching sub_strand, "
                f"e.g. {orphan_indicators[0]!r}"
            )
        return False, "; ".join(parts)
    return True, (
        f"all {len(subs)} sub_strands use the document's XX.YY caption code and prefix "
        f"their indicators"
    )


def check_nv_four_level_hierarchy(elements: List[dict]) -> Tuple[bool, str]:
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


def check_parser_ky_four_level_resolved(indicators: List[dict]) -> Tuple[bool, str]:
    """KY is a full 4-level document: every standard must carry both a strand
    and a sub_strand (the parser-side twin of KY-FOUR-LEVEL-HIERARCHY)."""
    bad = [i for i in indicators
           if i.get("strand") is None or i.get("sub_strand") is None]
    if bad:
        ex = bad[0]
        return False, (
            f"{len(bad)}/{len(indicators)} standards flattened "
            f"(e.g. {ex.get('standard_id')!r}: strand={_code(ex.get('strand'))!r}, "
            f"sub_strand={_code(ex.get('sub_strand'))!r})"
        )
    return True, f"all {len(indicators)} standards have both a strand and a sub_strand"


_LABEL_IN_CODE_RE = re.compile(r"\b(standard|benchmark)\b", re.IGNORECASE)


def check_parser_ky_benchmark_code_normalized(indicators: List[dict]) -> Tuple[bool, str]:
    """Structural labels never leak into a code, and codes are dotted paths.

    Two halves, applied to every level of every standard:
    (1) no code contains the word `Standard` or `Benchmark`;
    (2) each of strand / sub_strand / indicator is prefixed by its nearest
        non-null ancestor's code plus a dot. A level that is None is skipped
        for the prefix half (the next level down is then checked against the
        nearest ancestor that does exist).
    """
    label_leaks, prefix_breaks = [], []
    checked_prefixes = 0
    for ind in indicators:
        chain = [
            ("domain", ind.get("domain")),
            ("strand", ind.get("strand")),
            ("sub_strand", ind.get("sub_strand")),
            ("indicator", ind.get("indicator")),
        ]
        parent_code = None
        for name, level in chain:
            if level is None:
                continue
            code = _code(level) or ""
            if _LABEL_IN_CODE_RE.search(code):
                label_leaks.append((ind.get("standard_id"), name, code))
            if name != "domain":
                if parent_code:
                    checked_prefixes += 1
                    if not code.startswith(parent_code + "."):
                        prefix_breaks.append((ind.get("standard_id"), name, code, parent_code))
            parent_code = code

    if label_leaks or prefix_breaks:
        parts = []
        if label_leaks:
            parts.append(
                f"{len(label_leaks)} code(s) carry a structural label, e.g. "
                f"{label_leaks[0][1]}={label_leaks[0][2]!r} on {label_leaks[0][0]!r}"
            )
        if prefix_breaks:
            b = prefix_breaks[0]
            parts.append(
                f"{len(prefix_breaks)}/{checked_prefixes} code(s) not prefixed by parent, e.g. "
                f"{b[1]}={b[2]!r} under parent {b[3]!r} on {b[0]!r}"
            )
        return False, "; ".join(parts)
    return True, (
        f"{len(indicators)} standards: no label text in any code, "
        f"all {checked_prefixes} child codes prefixed by their parent"
    )


def check_parser_ky_sub_strand_not_indicator_code(indicators: List[dict]) -> Tuple[bool, str]:
    """A sub_strand and the indicator beneath it are distinct levels: their
    codes must differ, and the indicator's code must extend the sub_strand's
    (`<sub_strand>.<segment>`). Standards with no sub_strand are out of scope
    here — KY-FOUR-LEVEL-RESOLVED covers those."""
    same, not_nested, missing = [], [], 0
    for ind in indicators:
        ss, i = _code(ind.get("sub_strand")), _code(ind.get("indicator"))
        if not ss or not i:
            missing += 1
            continue
        if ss == i:
            same.append((ind.get("standard_id"), ss))
        elif not i.startswith(ss + "."):
            not_nested.append((ind.get("standard_id"), ss, i))

    if same or not_nested:
        parts = []
        if same:
            parts.append(f"{len(same)} sub_strand/indicator code collision(s), e.g. {same[0]}")
        if not_nested:
            parts.append(
                f"{len(not_nested)} indicator code(s) not nested under their sub_strand, "
                f"e.g. {not_nested[0]}"
            )
        return False, "; ".join(parts)
    checked = len(indicators) - missing
    detail = f"all {checked} standards keep sub_strand and indicator codes distinct and nested"
    if missing:
        detail += f" ({missing} skipped: no sub_strand)"
    return True, detail


def check_parser_nv_strand_parent_by_heading(indicators: List[dict]) -> Tuple[bool, str]:
    """An indicator group belongs to exactly one strand.

    NV repeats the `<Domain> Standard N:` heading above continued group content
    on the next page (p5 and p6 both carry Standard 2 above SS.CI rows) and
    opens a new strand partway down a page (Standard 3 below the tail of
    Standard 2 on p6). Page position alone therefore can't pick the parent. The
    observable consequence of getting it wrong is that one group's indicators
    fan out across two strands, so that is what this asserts — without naming
    any NV group, so it reads as "a group has one parent".

    Identity here is the group's printed TITLE, scoped by domain name — not its
    code. A mis-parented group tends to be handed a code derived from the wrong
    strand, so grouping by code would split the group in two and let the very
    failure this guards against report as a pass.
    """
    groups: Dict[Tuple[str, str], set] = {}
    for ind in indicators:
        sub, strand = ind.get("sub_strand"), ind.get("strand")
        if not isinstance(sub, dict) or not isinstance(strand, dict):
            continue
        name, dom = sub.get("name"), (ind.get("domain") or {}).get("name")
        if name and strand.get("name"):
            groups.setdefault((dom or "", name), set()).add(strand["name"])
    if not groups:
        return False, "no standard carries both a named sub_strand and a named strand"

    split = {g: sorted(s) for g, s in groups.items() if len(s) > 1}
    if split:
        (dom, name), strands = next(iter(split.items()))
        return False, (
            f"{len(split)}/{len(groups)} indicator group(s) split across strands, e.g. "
            f"{name!r} ({dom}) parented by {len(strands)}: {[s[:45] for s in strands]}"
        )
    return True, f"all {len(groups)} indicator groups resolve to a single strand"


# NV's printed indicator token: <domain root>.<group>.PK<n>, e.g. `SS.ID.PK1`,
# `S.EO.PK4`. Shape-matched so the check states the document's code convention
# rather than enumerating NV's seven groups.
_NV_INDICATOR_CODE_RE = re.compile(r"^([A-Z]{1,2})\.([A-Z]{2})\.PK\d+$")


def check_parser_nv_document_code_preserved(indicators: List[dict]) -> Tuple[bool, str]:
    """The code printed on the page survives into the resolved standard.

    NV prints a complete identifier for every indicator, so the parser should
    never have to invent one: `standard_id` is that token verbatim, and the two
    levels above it are its dotted prefixes. Anything else means a title
    abbreviation displaced a real document code.
    """
    bad_shape, bad_sid, bad_prefix = [], [], []
    for ind in indicators:
        code = _code(ind.get("indicator")) or ""
        m = _NV_INDICATOR_CODE_RE.match(code)
        if not m:
            bad_shape.append(code)
            continue
        root, group = m.group(1), m.group(2)
        sid = ind.get("standard_id")
        if sid != f"US-NV-2023-{code}":
            bad_sid.append((sid, code))
        if _code(ind.get("sub_strand")) != f"{root}.{group}":
            bad_prefix.append(("sub_strand", _code(ind.get("sub_strand")), f"{root}.{group}"))
        elif _code(ind.get("domain")) != root:
            bad_prefix.append(("domain", _code(ind.get("domain")), root))

    if bad_shape or bad_sid or bad_prefix:
        parts = []
        if bad_shape:
            parts.append(
                f"{len(bad_shape)}/{len(indicators)} indicator code(s) are not the document's "
                f"XX.YY.PKn token, e.g. {bad_shape[0]!r}"
            )
        if bad_sid:
            parts.append(
                f"{len(bad_sid)} standard_id(s) not derived from the printed code, e.g. "
                f"{bad_sid[0][0]!r} for code {bad_sid[0][1]!r}"
            )
        if bad_prefix:
            lvl, got, want = bad_prefix[0]
            parts.append(
                f"{len(bad_prefix)} ancestor code(s) are not the printed prefix, e.g. "
                f"{lvl}={got!r} should be {want!r}"
            )
        return False, "; ".join(parts)
    return True, (
        f"all {len(indicators)} standards keep the document's printed code at indicator, "
        f"sub_strand and domain"
    )


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
