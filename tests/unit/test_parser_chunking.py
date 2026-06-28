"""Unit tests for domain-scoped code normalization and parent-context carry-over
when splitting oversized parse chunks.

Both guard against cross-domain contamination in documents (like CA) where two
SEPARATE domains share strand/sub_strand/indicator TITLES:

* ``normalize_element_codes`` must NOT reconcile a "Sharing Explanations"
  indicator across the FLD and ELD domains (which would renumber one to match
  the other). It scopes reconciliation by the owning domain.
* ``_split_oversized_chunk`` must carry the most recent sub_strand (not just the
  strand) into a new sub-chunk, so indicators split off from their sub_strand
  header still resolve under it instead of orphaning to ``sub_strand=None``.
"""

from els_pipeline.models import DetectedElement, HierarchyLevelEnum
from els_pipeline.parser import (
    normalize_element_codes,
    _split_oversized_chunk,
)


def _el(level, code, title, page=1, age_band=None):
    return DetectedElement(
        level=level,
        code=code,
        title=title,
        description="",
        confidence=0.95,
        source_page=page,
        source_text=title,
        needs_review=False,
        age_band=age_band,
    )


D = HierarchyLevelEnum.DOMAIN
S = HierarchyLevelEnum.STRAND
SS = HierarchyLevelEnum.SUB_STRAND
I = HierarchyLevelEnum.INDICATOR


class TestNormalizeElementCodesDomainScope:
    def test_same_indicator_title_in_two_domains_keeps_distinct_codes(self):
        # FLD "Asking Questions" is 1.5; ELD "Asking Questions" is 1.7. They are
        # different indicators in different domains and must NOT be reconciled.
        elements = [
            _el(D, "FLD", "Foundational Language Development"),
            _el(S, "1.0", "Listening and Speaking"),
            _el(I, "1.5", "Asking Questions"),
            _el(D, "ELD", "English Language Development"),
            _el(S, "1.0", "Listening and Speaking"),
            _el(I, "1.7", "Asking Questions"),
        ]
        out = normalize_element_codes(elements)
        by_dom = {}
        cur = None
        for e in out:
            if e.level == D:
                cur = e.code
            elif e.level == I:
                by_dom[cur] = e.code
        assert by_dom["FLD"] == "1.5"
        assert by_dom["ELD"] == "1.7"

    def test_within_domain_code_drift_still_reconciles(self):
        # A single domain detected with code variants across overlapping chunks
        # ("PHD" vs "PhysicalDevelopment") must still collapse to one code.
        elements = [
            _el(D, "PHD", "Physical Development"),
            _el(I, "PHD.1", "Gross Motor"),
            _el(D, "PhysicalDevelopment", "Physical Development"),
            _el(I, "PHD.1", "Gross Motor"),
        ]
        out = normalize_element_codes(elements)
        domain_codes = {e.code for e in out if e.level == D}
        assert domain_codes == {"PHD"}  # slug variant reconciled away

    def test_sub_strand_code_avoids_collision_with_foundation_number(self):
        # "Grammar" is detected twice: as the flat foundation number "1.4" (shared
        # with foundation 1.4) and as the title abbreviation "GRAM". The canonical
        # code must be "GRAM" so it stays stable across chunks and never collides
        # with foundation 1.4.
        elements = [
            _el(D, "FLD", "Foundational Language Development"),
            _el(S, "1.0", "Listening and Speaking"),
            _el(SS, "1.4", "Grammar"),
            _el(SS, "GRAM", "Grammar"),
            _el(I, "1.4", "Using Grammatical Features"),
            _el(I, "1.5", "Asking Questions"),
            _el(I, "1.8", "Participating in Conversations"),
        ]
        out = normalize_element_codes(elements)
        grammar_codes = {e.code for e in out if e.level == SS and e.title == "Grammar"}
        assert grammar_codes == {"GRAM"}  # "1.4" rejected as colliding

    def test_numeric_sub_strand_with_no_alternative_is_kept(self):
        # ATL-style: a sub_strand detected ONLY as a numeric code (no abbreviation
        # alternative) keeps it — the in-prompt rule 174 resolves the collision.
        elements = [
            _el(D, "ATL", "Approaches to Learning"),
            _el(S, "1.0", "Motivation to Learn"),
            _el(SS, "1.1", "Curiosity and Interest"),
            _el(I, "1.1", "Curiosity and Interest"),
        ]
        out = normalize_element_codes(elements)
        ss = [e.code for e in out if e.level == SS]
        assert ss == ["1.1"]

    def test_sub_strand_title_shared_across_domains_not_merged(self):
        elements = [
            _el(D, "FLD", "Foundational Language Development"),
            _el(S, "1.0", "Listening and Speaking"),
            _el(SS, "VOCA", "Vocabulary"),
            _el(D, "ELD", "English Language Development"),
            _el(S, "1.0", "Listening and Speaking"),
            _el(SS, "VOCA", "Vocabulary"),
        ]
        # Both already share the code "VOCA" — the point is the function must not
        # crash and must leave each domain's sub_strand independently scoped.
        out = normalize_element_codes(elements)
        assert [e.code for e in out if e.level == SS] == ["VOCA", "VOCA"]


class TestSplitOversizedChunkCarriesSubStrand:
    def test_sub_strand_carried_into_following_subchunk(self):
        # One strand, one sub_strand, many indicators — forces a split mid-PA.
        chunk = [_el(D, "ELD", "English Language Development"),
                 _el(S, "2.0", "Foundational Literacy Skills"),
                 _el(SS, "PA", "Phonological Awareness")]
        for n in range(1, 16):
            chunk.append(_el(I, f"2.{n}", f"Indicator {n}"))

        subs = _split_oversized_chunk(chunk, max_indicators=12)
        assert len(subs) > 1
        # Every sub-chunk that contains indicators must carry both the strand and
        # the PA sub_strand header so nothing orphans.
        for sub in subs:
            if any(e.level == I for e in sub):
                assert any(e.level == S and e.code == "2.0" for e in sub)
                assert any(e.level == SS and e.code == "PA" for e in sub)

    def test_new_strand_resets_carried_sub_strand(self):
        # After a new strand begins, the previous strand's sub_strand must NOT be
        # carried into a later split under the new strand.
        chunk = [_el(D, "ELD", "English Language Development"),
                 _el(S, "1.0", "Listening and Speaking"),
                 _el(SS, "VOCA", "Vocabulary")]
        for n in range(1, 9):
            chunk.append(_el(I, f"1.{n}", f"LS Indicator {n}"))
        chunk.append(_el(S, "2.0", "Foundational Literacy Skills"))
        for n in range(1, 9):
            chunk.append(_el(I, f"2.{n}", f"FLS Indicator {n}"))

        subs = _split_oversized_chunk(chunk, max_indicators=12)
        for sub in subs:
            strand_codes = {e.code for e in sub if e.level == S}
            ss_codes = {e.code for e in sub if e.level == SS}
            # VOCA (under strand 1.0) must never appear in a sub-chunk whose only
            # strand is 2.0.
            if strand_codes == {"2.0"}:
                assert "VOCA" not in ss_codes
