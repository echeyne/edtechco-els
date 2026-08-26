"""An abbreviation longer than the cap must still be recomputed.

`_resolve_code` decides whether a code the model emitted came from the document
(keep it) or from rule 4's abbreviation branch (recompute it deterministically).
Its shape guard used to be `^[A-Z]{1,DERIVED_CODE_MAX_LEN}$`, which excluded an
OVER-LONG abbreviation from consideration entirely — the one shape rule 4,
executed correctly, cannot produce.

Measured on KY run 043: the model emitted `ICOPPPTM` (8 chars) for "Identifies
or chooses an object or person by pointing…". The shape guard did not match, so
`_resolve_code` read it as a printed document code and left it, and
`US-KY-2021-LEL.2.1.ICOPPPTM` reached Aurora against the golden's
`US-KY-2021-LEL.2.1.ICOPP`. It is sampling variance — the full-document run of
the same document capped correctly — so the prompt lowers the rate and only the
Python floor reaches zero.

Widening the shape hands the decision to `_is_code_grounded` rather than
pre-empting it. Blast radius before enabling: 5 elements in 12,387 across every
detection file in `outputs/` (0.04%), and BOTH distinct cases move toward the
goldens — KY `ICOPPPTM`→`ICOPP` and AZ `LANGLIT`→`LL`, which are the golden
values.

`test_a_grounded_overlong_code_is_kept` is the canary: if it fails, the widened
guard has started overwriting codes the document actually prints.
"""

from els_pipeline.detector import (
    DERIVED_CODE_MAX_LEN,
    _DERIVABLE_CODE_RE,
    _resolve_code,
    derive_code_from_title,
)

_TITLE = "Identifies or chooses an object or person by pointing, physically moving toward it"
_SOURCE = "Identifies or chooses an object or person by pointing, physically moving toward it"


class TestOverlongAbbreviationIsRecomputed:
    def test_the_ky_case(self):
        assert _resolve_code("ICOPPPTM", _TITLE, _SOURCE) == "ICOPP"

    def test_it_agrees_with_rule_4_executed_directly(self):
        """The repair must defer to `derive_code_from_title`, never reimplement
        the abbreviation, so the connector list cannot drift."""
        assert _resolve_code("ICOPPPTM", _TITLE, _SOURCE) == derive_code_from_title(_TITLE)

    def test_the_az_domain_case(self):
        assert _resolve_code("LANGLIT", "Language and Literacy", "Language and Literacy") == "LL"

    def test_a_grounded_overlong_code_is_kept(self):
        """THE CANARY. A long all-caps code that appears in the element's own
        source_text was read off the page and is authoritative."""
        assert _resolve_code("ICOPPPTM", _TITLE, f"ICOPPPTM. {_SOURCE}") == "ICOPPPTM"


class TestNothingWithinTheCapChanged:
    def test_a_correct_length_abbreviation_still_recomputes(self):
        assert _resolve_code("WRONG", _TITLE, _SOURCE) == "ICOPP"

    def test_a_dotted_document_code_is_untouched(self):
        assert _resolve_code("SS.CI.PK3", _TITLE, _SOURCE) == "SS.CI.PK3"

    def test_a_lettered_leaf_is_untouched(self):
        """Rule 4's other branch: the list letter IS the code. Lowercase fails
        the shape guard, which is what protects it."""
        assert _resolve_code("a", _TITLE, _SOURCE) == "a"

    def test_a_labelled_id_is_untouched(self):
        assert _resolve_code("Benchmark 1.1", _TITLE, _SOURCE) == "Benchmark 1.1"

    def test_a_numeric_code_is_untouched(self):
        assert _resolve_code("1.0", _TITLE, _SOURCE) == "1.0"

    def test_every_length_up_to_the_cap_still_matches_the_shape(self):
        for n in range(1, DERIVED_CODE_MAX_LEN + 1):
            assert _DERIVABLE_CODE_RE.match("A" * n)

    def test_lengths_past_the_cap_now_match_too(self):
        assert _DERIVABLE_CODE_RE.match("A" * (DERIVED_CODE_MAX_LEN + 3))

    def test_mixed_case_and_separators_never_match(self):
        for bad in ("Science", "PK3.I", "a", "1.0", "Benchmark 1.1", "AB-CD", ""):
            assert not _DERIVABLE_CODE_RE.match(bad), bad
