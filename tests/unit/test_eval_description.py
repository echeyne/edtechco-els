"""Unit tests for the detector eval's description dimension.

``evaluation/eval_detector.compare_description`` grades verbatim prose, which
makes it the one comparison in the harness where "how much do we normalize?" is
a load-bearing decision:

* it must fold whitespace, because a description is transcribed from a PDF
  whose line breaks are typesetting artifacts — the detector emitting '\\n'
  where the golden holds ' ' is transcription noise, not a defect; and
* it must fold NOTHING else, because every other difference is real. A test
  here that passes after swapping ``_norm_ws`` for ``_norm`` (which lowercases)
  would mean the matcher had been loosened.
"""

import pytest

from evaluation.eval_common import _norm_ws
from evaluation.eval_detector import compare_description


class TestNormWs:
    def test_collapses_newlines_and_runs_but_preserves_case(self):
        assert _norm_ws("Children  develop\nand   learn\n") == "Children develop and learn"

    def test_none_and_blank_fold_to_empty(self):
        assert _norm_ws(None) == ""
        assert _norm_ws("   \n\t ") == ""


class TestCompareDescription:
    def test_exact_match(self):
        status, detail = compare_description("Children develop.", "Children develop.")
        assert status == "match"
        assert "17" in detail

    def test_newline_vs_space_is_not_a_defect(self):
        """All four AZ 'differences' were exactly this: the golden holding ' '
        where the detector emits '\\n', at identical length."""
        golden = "Children develop skills in listening and speaking with peers."
        produced = "Children develop skills in listening\nand speaking with peers."
        assert compare_description(golden, produced)[0] == "match"

    def test_leading_and_trailing_whitespace_is_not_a_defect(self):
        assert compare_description("Children develop.", "\n  Children develop.  \n")[0] == "match"

    def test_strict_prefix_is_a_truncation_and_reports_both_lengths(self):
        """The NV Science shape: the produced prose stops partway through."""
        golden = "A" * 3500
        produced = "A" * 2410
        status, detail = compare_description(golden, produced)
        assert status == "truncated"
        assert detail == "truncated: 2410/3500 chars"

    def test_truncation_is_judged_after_whitespace_normalization(self):
        golden = "Children develop skills in listening and speaking."
        produced = "Children\ndevelop skills in"
        assert compare_description(golden, produced)[0] == "truncated"

    def test_different_text_is_a_mismatch_not_a_truncation(self):
        """CA's age-column bug hands the 'Later' indicator the 'Early' column's
        text — different prose, so it must never read as a truncation."""
        golden = "Use a variety of English grammatical forms, with some inaccuracies."
        produced = "Use a few formulaic English sentence structures to communicate."
        status, detail = compare_description(golden, produced)
        assert status == "mismatch"
        assert "golden" in detail and "detected" in detail

    def test_produced_longer_than_golden_is_a_mismatch(self):
        """Truncation is one-directional: only a SHORTER produced description is
        one. Extra text on the end (CA's trailing period) is a plain mismatch."""
        golden = "and seeking solutions to problems"
        status, _ = compare_description(golden, golden + ".")
        assert status == "mismatch"

    def test_mismatch_excerpt_is_anchored_at_the_divergence(self):
        """A head excerpt would render both sides identically when the sides
        agree for longer than the excerpt window — which is exactly the CA
        trailing-period case."""
        golden = "x" * 200 + "problems"
        produced = "x" * 200 + "problems."
        _, detail = compare_description(golden, produced)
        assert "diverges at char 208" in detail
        assert "'…'" in detail and "'….'" in detail

    def test_case_difference_is_a_mismatch(self):
        """Guards the normalizer: swapping in a case-folding one breaks this."""
        assert compare_description("Children Develop.", "children develop.")[0] == "mismatch"

    @pytest.mark.parametrize("golden", [None, "", "   \n  "])
    def test_golden_without_a_description_is_skipped(self, golden):
        """Most goldens annotate few descriptions (AZ 4, CA 14, NV 3). An
        unannotated element asserts nothing, so it is neither pass nor fail and
        must stay out of the denominator."""
        status, _ = compare_description(golden, "anything at all")
        assert status == "skip"

    @pytest.mark.parametrize("produced", [None, "", "  \n "])
    def test_produced_empty_against_annotated_golden_is_missing(self, produced):
        """Reported as its own status rather than as 'truncated: 0/N' — an
        absent description is a different defect from one cut short."""
        status, detail = compare_description("Children develop and learn.", produced)
        assert status == "missing"
        assert "27" in detail
