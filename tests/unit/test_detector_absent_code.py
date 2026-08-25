"""An element the model left uncoded must not cost us its whole chunk.

`DetectedElement.code` is a required `str`, and the detector LLM intermittently
answers `"code": null` for an element the document leaves uncoded — despite rule
4, whose abbreviation branch exists precisely for that case. Three things then
compounded, and all three are covered here:

  1. `_resolve_code` folded `None` to `""`, which fails `_DERIVABLE_CODE_RE`, so
     it returned the `None` untouched and `derive_code_from_title` never ran.
  2. `DetectedElement(...)` was constructed outside any `try`, and pydantic's
     `ValidationError` subclasses `ValueError`, so the rejection escaped the
     per-element loop in `parse_llm_response` — discarding every VALID sibling
     already accumulated for that chunk.
  3. `detection_batching.detect_batch` caught it as a `ValueError` and retried
     3x against an identical prompt at temperature 0. Deterministic input, so
     all three attempts failed identically and the chunk was dropped.

Measured on the KY full-document run of 2026-08-24
(`pipeline-US-KY-2021-full08242026`): one `"code": null` element apiece cost 12
of 18 chunks, 31 of 52 pages ended with zero surviving coverage, ~233 element
detections were discarded against 116 kept, and the execution still reported
SUCCEEDED.
"""

import json

from els_pipeline.models import TextBlock
from els_pipeline.detector import _resolve_code, derive_code_from_title, parse_llm_response


def _blocks():
    return [TextBlock(
        text="Standard 1: Health", page_number=1, block_type="LINE", confidence=0.99,
        geometry={"BoundingBox": {"Left": 0.1, "Top": 0.1, "Width": 0.5, "Height": 0.02}},
    )]


def _resp(*elements):
    return json.dumps([
        {"level": lv, "code": c, "title": t, "confidence": 0.9,
         "source_page": 1, "source_text": src}
        for lv, c, t, src in elements
    ])


class TestAbsentCodeDerives:
    """An absent code IS rule 4's "otherwise" case, so derive rather than fail."""

    def test_null_code_derives_from_title(self):
        assert _resolve_code(None, "Nutrition", "Nutrition") == "NUTR"

    def test_empty_string_code_derives_from_title(self):
        assert _resolve_code("", "Concepts About Print", "Concepts About Print") == "CP"

    def test_whitespace_only_code_derives_from_title(self):
        assert _resolve_code("   ", "Approaches to Learning", "Approaches to Learning") == "AL"

    def test_derivation_matches_the_documented_rule_4_procedure(self):
        # Not a second implementation of the abbreviation: it defers to the one
        # helper, so the connector list and the ≤5-char cap cannot drift apart.
        for title in ("Nutrition", "Concepts About Print", "Social & Emotional Development",
                      "Engages in an activity for a sustained period of time"):
            assert _resolve_code(None, title, "irrelevant") == derive_code_from_title(title)

    def test_underivable_code_stays_absent_rather_than_being_invented(self):
        # No title to work from: return the absent code and let the element be
        # skipped. Inventing a placeholder would put a junk primary key in Aurora.
        assert _resolve_code(None, "", "x") is None


class TestDocumentCodeStillWins:
    """The regression guard: a printed code is authoritative and never touched.

    `_resolve_code`'s two existing guards — shape (`_DERIVABLE_CODE_RE`) and
    grounding (`_is_code_grounded`) — must be unaffected by the absent-code
    branch, which runs before them and only ever fires on nothing at all.
    """

    def test_printed_codes_of_every_shape_survive(self):
        for code, src in [
            ("a", "a. Uses words to communicate"),         # AZ lettered leaf
            ("1.0", "1.0 Health"),                          # CO numeric
            ("Benchmark 1.1", "Benchmark 1.1 Text"),        # KY labelled id
            ("I.A.2", "I.A.2 Text"),                        # TX dotted path
            ("SS.ID", "SS.ID caption"),                     # NV caption code
        ]:
            assert _resolve_code(code, "Uses words to communicate", src) == code, code


class TestChunkSurvivesOneBadElement:
    """Blast radius: a malformed element is contained to ITSELF."""

    def test_the_kentucky_case_keeps_every_sibling(self):
        elements = parse_llm_response(_resp(
            ("domain", "HW.1", "Health", "HW.1 Health"),
            ("strand", None, "Nutrition", "Nutrition"),
            ("strand", "HW.2", "Safety", "Safety"),
        ), _blocks())
        # Previously: 0. The null in the middle took both valid siblings with it.
        assert len(elements) == 3
        assert [e.code for e in elements] == ["HW.1", "NUTR", "HW.2"]

    def test_an_unsalvageable_element_skips_alone(self):
        # Null code AND no title to derive from — nothing can rescue this one,
        # but it must still leave its siblings standing.
        elements = parse_llm_response(_resp(
            ("domain", "HW.1", "Health", "HW.1 Health"),
            ("strand", None, "", "x"),
            ("strand", "HW.2", "Safety", "Safety"),
        ), _blocks())
        assert [e.code for e in elements] == ["HW.1", "HW.2"]

    def test_parse_llm_response_does_not_raise_on_a_null_code(self):
        # The escape route into detect_batch's `except ValueError` retry loop.
        # If this raises, 3 futile temperature-0 Bedrock calls follow and the
        # chunk is lost.
        parse_llm_response(_resp(("strand", None, "Nutrition", "Nutrition")), _blocks())

    def test_a_json_number_code_is_coerced_not_dropped(self):
        elements = parse_llm_response(_resp(("strand", 1, "Health", "1 Health")), _blocks())
        assert [e.code for e in elements] == ["1"]
