"""Unit tests for cross-domain code-prefix anchoring in the parser.

Separate domains may legitimately share a strand/sub_strand TITLE (e.g. CA's
"Foundational Language Development" (FLD) and "English Language Development"
(ELD) domains both have a "Vocabulary" sub_strand under a "Listening and
Speaking" strand). The LLM occasionally borrows a sibling domain's prefix for
such a shared title — emitting sub_strand ``ELD.1.0.VOCA`` for an indicator
correctly coded ``FLD.1.0.VOCA.1.1``. ``_anchor_parent_code`` re-anchors every
parent code to its indicator code (the ground truth for the parent chain), and
``parse_llm_response`` applies it so the bleed never reaches the output.
"""

import json

from els_pipeline.parser import _anchor_parent_code, parse_llm_response


class TestAnchorParentCode:
    def test_reanchors_bled_sibling_domain_prefix(self):
        # FLD indicator wrongly given an ELD sub_strand code.
        assert (
            _anchor_parent_code("ELD.1.0.VOCA", "FLD.1.0.VOCA.1.1.36-54")
            == "FLD.1.0.VOCA"
        )

    def test_reanchors_strand_and_domain_levels(self):
        ind = "FLD.1.0.VOCA.1.1.36-54"
        assert _anchor_parent_code("ELD.1.0", ind) == "FLD.1.0"
        assert _anchor_parent_code("ELD", ind) == "FLD"

    def test_idempotent_when_already_correct_prefix(self):
        ind = "FLD.1.0.VOCA.1.1.36-54"
        assert _anchor_parent_code("FLD.1.0.VOCA", ind) == "FLD.1.0.VOCA"
        assert _anchor_parent_code("FLD.1.0", ind) == "FLD.1.0"
        assert _anchor_parent_code("FLD", ind) == "FLD"

    def test_preserves_dotted_numeric_segments(self):
        # A dotted id like "2.0" contributes two tokens to BOTH the parent and the
        # indicator, so depth counting stays aligned and the trailing proficiency
        # disambiguator (".DISC") is excluded automatically.
        assert (
            _anchor_parent_code("ELD.2.0.PA", "ELD.2.0.PA.2.3.DISC") == "ELD.2.0.PA"
        )
        assert (
            _anchor_parent_code("FLD.2.0.PA", "ELD.2.0.PA.2.3.DISC") == "ELD.2.0.PA"
        )

    def test_none_and_empty_pass_through(self):
        assert _anchor_parent_code(None, "FLD.1.0.VOCA.1.1") is None
        assert _anchor_parent_code("", "FLD.1.0.VOCA.1.1") == ""
        assert _anchor_parent_code("FLD.1.0", "") == "FLD.1.0"

    def test_parent_not_shallower_left_untouched(self):
        # Parent depth >= indicator depth cannot be a proper prefix — leave as-is
        # rather than fabricate one.
        assert _anchor_parent_code("ELD.1.0.VOCA.1.1", "FLD") == "ELD.1.0.VOCA.1.1"

    def test_bare_letter_suffix_indicator_preserved(self):
        # CO pattern: an indicator appends a bare LETTER to its sub_strand number
        # with NO dot separator ("SED.2.3a" under sub_strand "SED.2.3"). The two
        # codes have equal ``.``-split depth, so the guard must NOT rewrite the
        # sub_strand — doing so would collide it with the indicator code.
        assert _anchor_parent_code("SED.2.3", "SED.2.3a") == "SED.2.3"
        assert _anchor_parent_code("SED.3.1", "SED.3.1d") == "SED.3.1"


class TestParseLlmResponseAnchoring:
    def test_fld_indicator_keeps_fld_parents_despite_eld_bleed(self):
        """An FLD indicator whose LLM-emitted parents bled to ELD codes is
        repaired so the whole chain stays under FLD."""
        response = json.dumps(
            [
                {
                    "domain_code": "FLD",
                    "domain_name": "Foundational Language Development",
                    "strand_code": "ELD.1.0",
                    "strand_name": "Listening and Speaking",
                    "sub_strand_code": "ELD.1.0.VOCA",
                    "sub_strand_name": "Vocabulary",
                    "indicator_code": "FLD.1.0.VOCA.1.1.36-54",
                    "indicator_name": "Understanding and Using Vocabulary",
                    "indicator_description": "Understand and use a range of words.",
                    "age_band": "36-54",
                    "source_page": 6,
                    "source_text": "...",
                }
            ]
        )

        standards = parse_llm_response(response, "US", "CA", 2021, "PK")

        assert len(standards) == 1
        s = standards[0]
        assert s.domain.code == "FLD"
        assert s.strand.code == "FLD.1.0"
        assert s.sub_strand.code == "FLD.1.0.VOCA"
        assert s.indicator.code == "FLD.1.0.VOCA.1.1.36-54"
        # Names are untouched — only the code prefix was wrong.
        assert s.sub_strand.name == "Vocabulary"
        # standard_id derives from the (correct) indicator code.
        assert s.standard_id == "US-CA-2021-FLD.1.0.VOCA.1.1.36-54"

    def test_sibling_eld_indicator_unaffected(self):
        """The genuine ELD copy keeps its ELD parents — the fix doesn't merge the
        two same-titled sub_strands."""
        response = json.dumps(
            [
                {
                    "domain_code": "ELD",
                    "domain_name": "English Language Development",
                    "strand_code": "ELD.1.0",
                    "strand_name": "Listening and Speaking",
                    "sub_strand_code": "ELD.1.0.VOCA",
                    "sub_strand_name": "Vocabulary",
                    "indicator_code": "ELD.1.0.VOCA.1.1.DISC",
                    "indicator_name": "Understanding Words",
                    "indicator_description": "Discovering: understand words.",
                    "age_band": None,
                    "column_label": "Discovering",
                    "source_page": 9,
                    "source_text": "...",
                }
            ]
        )

        standards = parse_llm_response(response, "US", "CA", 2021, "PK")

        s = standards[0]
        assert s.domain.code == "ELD"
        assert s.strand.code == "ELD.1.0"
        assert s.sub_strand.code == "ELD.1.0.VOCA"
        assert s.indicator.code == "ELD.1.0.VOCA.1.1.DISC"
