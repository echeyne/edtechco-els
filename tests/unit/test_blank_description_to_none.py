"""Unit tests for blank-string -> None normalization on optional free-text fields.

Absence has exactly one spelling in this schema: ``None``. The pipeline used to
produce two. ``detector._create_detected_element`` coerced a missing description
to ``""`` (``.get('description') or ""``), so every description-less detected
element carried an empty string.

Which spelling a row got was decided by LLM sampling, so a prompt rule alone
cannot make it reconcilable. ``models._blank_to_none`` folds the output
deterministically, applied as a ``mode="before"`` field validator so it covers
EVERY construction path rather than one call site. These tests pin the four
inputs that matter (``""``, whitespace-only, ``None``, real prose) at the model
layer and then through each real construction path.
"""

import json

from els_pipeline.models import (
    DetectedElement,
    HierarchyLevel,
    HierarchyNode,
    NormalizedStandard,
    _blank_to_none,
)
from els_pipeline.parser import parse_llm_response
from els_pipeline.validator import deserialize_record, serialize_record


REAL = "Children develop a sense of self.\nThey show growing independence."


def _hl(description):
    return HierarchyLevel(code="AL", name="Approaches to Learning", description=description)


def _de(description="x", **kw):
    kw.setdefault("level", "domain")
    kw.setdefault("code", "AL")
    kw.setdefault("title", "Approaches to Learning")
    kw.setdefault("confidence", 0.95)
    kw.setdefault("source_page", 2)
    kw.setdefault("source_text", "Approaches to Learning")
    return DetectedElement(description=description, **kw)


class TestBlankToNoneHelper:
    def test_empty_string(self):
        assert _blank_to_none("") is None

    def test_whitespace_only(self):
        assert _blank_to_none("   ") is None
        assert _blank_to_none("\n\t  \r\n") is None

    def test_none_passes_through(self):
        assert _blank_to_none(None) is None

    def test_real_text_untouched(self):
        assert _blank_to_none(REAL) == REAL

    def test_real_text_is_not_stripped(self):
        # Descriptions are verbatim prose transcribed from a PDF — surrounding
        # whitespace is content we must not silently edit. Only a value that is
        # ENTIRELY blank is an absence.
        assert _blank_to_none("  padded  ") == "  padded  "

    def test_non_string_passes_through(self):
        # The helper reads the SHAPE of a string; anything else is left for
        # normal type validation to reject or accept.
        assert _blank_to_none(0) == 0
        assert _blank_to_none(False) is False


class TestHierarchyLevelDescription:
    def test_empty_string_becomes_none(self):
        assert _hl("").description is None

    def test_whitespace_only_becomes_none(self):
        assert _hl("   \n ").description is None

    def test_none_stays_none(self):
        assert _hl(None).description is None

    def test_omitted_defaults_to_none(self):
        assert HierarchyLevel(code="AL", name="Approaches to Learning").description is None

    def test_real_description_passes_through_unchanged(self):
        assert _hl(REAL).description == REAL

    def test_serializes_as_null(self):
        # The stored artifact and the Aurora write both read this dump — an ""
        # here is what reached the DB's nullable description column.
        assert _hl("").model_dump()["description"] is None

    def test_code_and_name_are_not_affected(self):
        # The normalization is scoped to the optional free-text field. Required
        # identity fields keep whatever they were given.
        level = HierarchyLevel(code="", name="", description="")
        assert level.code == ""
        assert level.name == ""
        assert level.description is None


class TestHierarchyNodeDescription:
    def test_empty_string_becomes_none(self):
        node = HierarchyNode(level="domain", code="AL", name="ATL", description="")
        assert node.description is None

    def test_whitespace_only_becomes_none(self):
        node = HierarchyNode(level="domain", code="AL", name="ATL", description="  ")
        assert node.description is None

    def test_none_stays_none(self):
        node = HierarchyNode(level="domain", code="AL", name="ATL", description=None)
        assert node.description is None

    def test_real_description_passes_through_unchanged(self):
        node = HierarchyNode(level="domain", code="AL", name="ATL", description=REAL)
        assert node.description == REAL


class TestDetectedElementDescription:
    """The root cause: the detector manufactured "" for every element that owns
    no prose, and that value reached the parser prompt as `"description": ""`."""

    def test_empty_string_becomes_none(self):
        assert _de("").description is None

    def test_whitespace_only_becomes_none(self):
        assert _de("  \n ").description is None

    def test_none_stays_none(self):
        assert _de(None).description is None

    def test_omitted_defaults_to_none(self):
        el = DetectedElement(
            level="domain", code="AL", title="Approaches to Learning",
            confidence=0.95, source_page=2, source_text="Approaches to Learning",
        )
        assert el.description is None

    def test_real_description_passes_through_unchanged(self):
        assert _de(REAL).description == REAL

    def test_blank_age_band_becomes_none(self):
        # Same shape, same remedy: an age_band column label that arrives blank is
        # an absent band, and downstream code branches on `age_band is None`.
        assert _de(age_band="").age_band is None
        assert _de(age_band="   ").age_band is None

    def test_real_age_band_passes_through_unchanged(self):
        assert _de(age_band="Early (3 to 4 ½ Years)").age_band == "Early (3 to 4 ½ Years)"

    def test_round_trips_from_stored_detection_json(self):
        # eval_parser and parse_batching both rebuild elements from a stored
        # detection artifact, which may still hold the old "" spelling. Reading
        # one back normalizes it, so old artifacts and new runs agree.
        stored = {
            "level": "strand", "code": "AL.1", "title": "Sustains attention",
            "description": "", "confidence": 0.97, "source_page": 2,
            "source_text": "Approaches to Learning Standard 1: Sustains attention",
            "age_band": None,
        }
        assert DetectedElement(**stored).description is None


class TestNormalizedStandardAgeBand:
    def _std(self, age_band):
        return NormalizedStandard(
            standard_id="US-KY-2021-AL.1.1.EASPT",
            country="US", state="KY", version_year=2021,
            domain=_hl(""),
            indicator=HierarchyLevel(code="AL.1.1.EASPT", name="Engages", description=REAL),
            age_band=age_band, source_page=2, source_text="…",
        )

    def test_blank_age_band_becomes_none(self):
        assert self._std("").age_band is None
        assert self._std("  ").age_band is None

    def test_real_age_band_passes_through_unchanged(self):
        assert self._std("36-60").age_band == "36-60"


class TestParserConstructionPath:
    """The reported symptom: parser.parse_llm_response is where the LLM's ""
    descriptions entered NormalizedStandard objects."""

    def _response(self, description):
        return json.dumps([{
            "domain_code": "AL",
            "domain_name": "Approaches to Learning",
            "domain_description": description,
            "strand_code": "AL.1",
            "strand_name": "Sustains attention and persists",
            "strand_description": description,
            "sub_strand_code": "AL.1.1",
            "sub_strand_name": "Maintains focus",
            "sub_strand_description": description,
            "indicator_code": "AL.1.1.EASPT",
            "indicator_name": "Engages in an activity for a sustained period of time",
            "indicator_description": REAL,
            "age_band": None,
            "source_page": 2,
            "source_text": "…",
        }])

    def test_empty_string_descriptions_become_none(self):
        s = parse_llm_response(self._response(""), "US", "KY", 2021, "36-60")[0]
        assert s.domain.description is None
        assert s.strand.description is None
        assert s.sub_strand.description is None
        # The indicator's real description is untouched.
        assert s.indicator.description == REAL

    def test_whitespace_only_descriptions_become_none(self):
        s = parse_llm_response(self._response("   \n"), "US", "KY", 2021, "36-60")[0]
        assert s.domain.description is None
        assert s.strand.description is None
        assert s.sub_strand.description is None

    def test_null_descriptions_stay_none(self):
        s = parse_llm_response(self._response(None), "US", "KY", 2021, "36-60")[0]
        assert s.domain.description is None
        assert s.strand.description is None
        assert s.sub_strand.description is None

    def test_real_descriptions_pass_through_unchanged(self):
        s = parse_llm_response(self._response(REAL), "US", "KY", 2021, "36-60")[0]
        assert s.domain.description == REAL
        assert s.strand.description == REAL
        assert s.sub_strand.description == REAL

    def test_serialized_indicators_carry_null_not_empty_string(self):
        # ParseResult.indicators is the artifact written to S3 and graded by
        # eval_parser — the shape the 9/26 KY mismatch was measured on.
        s = parse_llm_response(self._response(""), "US", "KY", 2021, "36-60")[0]
        dumped = s.model_dump()
        for level in ("domain", "strand", "sub_strand"):
            assert dumped[level]["description"] is None

    def test_a_present_level_is_not_dropped_by_a_blank_description(self):
        # Folding the description must not make the LEVEL itself vanish — the
        # strand/sub_strand are still real entities with a code and a name.
        s = parse_llm_response(self._response(""), "US", "KY", 2021, "36-60")[0]
        assert s.strand is not None and s.strand.code == "AL.1"
        assert s.sub_strand is not None and s.sub_strand.name == "Maintains focus"


class TestValidatorConstructionPath:
    """validator.deserialize_record is the second construction path for
    HierarchyLevel — a call-site fix in parser.py would have missed it."""

    def _canonical(self, description):
        return {
            "country": "US",
            "state": "KY",
            "document": {
                "title": "KY Early Learning Standards", "version_year": 2021,
                "source_url": "", "s3_key": "", "age_band": "36-60",
                "publishing_agency": "",
            },
            "standard": {
                "standard_id": "US-KY-2021-AL.1.1.EASPT",
                "domain": {"code": "AL", "name": "Approaches to Learning",
                           "description": description},
                "strand": {"code": "AL.1", "name": "Sustains attention",
                           "description": description},
                "sub_strand": {"code": "AL.1.1", "name": "Maintains focus",
                               "description": description},
                "indicator": {"code": "AL.1.1.EASPT", "name": "Engages",
                              "description": REAL},
            },
            "metadata": {"source_page": 2, "source_text": "…"},
        }

    def test_empty_string_descriptions_become_none(self):
        std = deserialize_record(self._canonical(""))
        assert std.domain.description is None
        assert std.strand.description is None
        assert std.sub_strand.description is None

    def test_whitespace_only_descriptions_become_none(self):
        std = deserialize_record(self._canonical("  \t "))
        assert std.domain.description is None

    def test_none_stays_none(self):
        std = deserialize_record(self._canonical(None))
        assert std.domain.description is None

    def test_real_descriptions_pass_through_unchanged(self):
        std = deserialize_record(self._canonical(REAL))
        assert std.domain.description == REAL
        assert std.indicator.description == REAL

    def test_canonical_round_trip_keeps_null(self):
        std = deserialize_record(self._canonical(""))
        canonical = serialize_record(std, {
            "title": "KY Early Learning Standards", "source_url": "",
            "age_band": "36-60", "publishing_agency": "",
        })
        assert canonical["standard"]["domain"]["description"] is None
        assert deserialize_record(canonical).domain.description is None
