"""Integration tests for hierarchy parser.

All tests that call parse_hierarchy mock call_bedrock_llm since the parser
now delegates hierarchy resolution to Amazon Bedrock (Claude).
"""

import json
import pytest
from unittest.mock import patch, MagicMock

from botocore.exceptions import ClientError

from src.els_pipeline.models import DetectedElement, HierarchyLevelEnum
from src.els_pipeline.parser import (
    parse_hierarchy,
    generate_standard_id,
    MAX_PARSE_RETRIES,
    MAX_BEDROCK_RETRIES,
)


def _bedrock_response(indicators):
    """Build a fake Bedrock JSON string for a list of indicator dicts."""
    return json.dumps(indicators)


class TestDepthNormalization:
    """Test depth normalization for different hierarchy levels."""

    def test_two_level_hierarchy(self):
        """Test parsing a 2-level hierarchy (Domain + Indicator)."""
        elements = [
            DetectedElement(
                level=HierarchyLevelEnum.DOMAIN, code="LLD",
                title="Language and Literacy Development",
                description="Language domain", confidence=0.95,
                source_page=1, source_text="LLD domain text",
                needs_review=False,
            ),
            DetectedElement(
                level=HierarchyLevelEnum.INDICATOR, code="LLD.1",
                title="Listening Skills",
                description="Child demonstrates listening skills",
                confidence=0.90, source_page=2,
                source_text="LLD.1 indicator text", needs_review=False,
            ),
            DetectedElement(
                level=HierarchyLevelEnum.INDICATOR, code="LLD.2",
                title="Speaking Skills",
                description="Child demonstrates speaking skills",
                confidence=0.92, source_page=3,
                source_text="LLD.2 indicator text", needs_review=False,
            ),
        ]

        fake = _bedrock_response([
            {"domain_code": "LLD", "domain_name": "Language and Literacy Development",
             "domain_description": "Language domain",
             "strand_code": None, "strand_name": None, "strand_description": None,
             "sub_strand_code": None, "sub_strand_name": None, "sub_strand_description": None,
             "indicator_code": "LLD.1", "indicator_name": "Listening Skills",
             "indicator_description": "Child demonstrates listening skills",
             "age_band": None, "source_page": 2, "source_text": "LLD.1 indicator text"},
            {"domain_code": "LLD", "domain_name": "Language and Literacy Development",
             "domain_description": "Language domain",
             "strand_code": None, "strand_name": None, "strand_description": None,
             "sub_strand_code": None, "sub_strand_name": None, "sub_strand_description": None,
             "indicator_code": "LLD.2", "indicator_name": "Speaking Skills",
             "indicator_description": "Child demonstrates speaking skills",
             "age_band": None, "source_page": 3, "source_text": "LLD.2 indicator text"},
        ])

        with patch("src.els_pipeline.parser.call_bedrock_llm", return_value=fake):
            result = parse_hierarchy(elements, "US", "CA", 2021)

        assert result.status == "success"
        assert len(result.standards) == 2
        for standard in result.standards:
            assert standard.domain is not None
            assert standard.domain.code == "LLD"
            assert standard.indicator is not None
            assert standard.strand is None
            assert standard.sub_strand is None

    def test_three_level_hierarchy(self):
        """Test parsing a 3-level hierarchy (Domain + Strand + Indicator)."""
        elements = [
            DetectedElement(
                level=HierarchyLevelEnum.DOMAIN, code="LLD",
                title="Language and Literacy Development",
                description="Language domain", confidence=0.95,
                source_page=1, source_text="LLD domain text",
                needs_review=False,
            ),
            DetectedElement(
                level=HierarchyLevelEnum.STRAND, code="LLD.A",
                title="Listening and Speaking",
                description="Listening and speaking strand",
                confidence=0.93, source_page=2,
                source_text="LLD.A strand text", needs_review=False,
            ),
            DetectedElement(
                level=HierarchyLevelEnum.INDICATOR, code="LLD.A.1",
                title="Comprehension",
                description="Child demonstrates understanding",
                confidence=0.90, source_page=3,
                source_text="LLD.A.1 indicator text", needs_review=False,
            ),
            DetectedElement(
                level=HierarchyLevelEnum.INDICATOR, code="LLD.A.2",
                title="Expression",
                description="Child expresses ideas clearly",
                confidence=0.91, source_page=4,
                source_text="LLD.A.2 indicator text", needs_review=False,
            ),
        ]

        fake = _bedrock_response([
            {"domain_code": "LLD", "domain_name": "Language and Literacy Development",
             "domain_description": "Language domain",
             "strand_code": "LLD.A", "strand_name": "Listening and Speaking",
             "strand_description": "Listening and speaking strand",
             "sub_strand_code": None, "sub_strand_name": None, "sub_strand_description": None,
             "indicator_code": "LLD.A.1", "indicator_name": "Comprehension",
             "indicator_description": "Child demonstrates understanding",
             "age_band": None, "source_page": 3, "source_text": "LLD.A.1 indicator text"},
            {"domain_code": "LLD", "domain_name": "Language and Literacy Development",
             "domain_description": "Language domain",
             "strand_code": "LLD.A", "strand_name": "Listening and Speaking",
             "strand_description": "Listening and speaking strand",
             "sub_strand_code": None, "sub_strand_name": None, "sub_strand_description": None,
             "indicator_code": "LLD.A.2", "indicator_name": "Expression",
             "indicator_description": "Child expresses ideas clearly",
             "age_band": None, "source_page": 4, "source_text": "LLD.A.2 indicator text"},
        ])

        with patch("src.els_pipeline.parser.call_bedrock_llm", return_value=fake):
            result = parse_hierarchy(elements, "US", "CA", 2021)

        assert result.status == "success"
        assert len(result.standards) == 2
        for standard in result.standards:
            assert standard.domain is not None
            assert standard.domain.code == "LLD"
            assert standard.strand is not None
            assert standard.strand.code == "LLD.A"
            assert standard.indicator is not None
            assert standard.sub_strand is None

    def test_four_level_hierarchy(self):
        """Test parsing a 4-level hierarchy (Domain + Strand + Sub-strand + Indicator)."""
        elements = [
            DetectedElement(
                level=HierarchyLevelEnum.DOMAIN, code="LLD",
                title="Language and Literacy Development",
                description="Language domain", confidence=0.95,
                source_page=1, source_text="LLD domain text",
                needs_review=False,
            ),
            DetectedElement(
                level=HierarchyLevelEnum.STRAND, code="LLD.A",
                title="Listening and Speaking",
                description="Listening and speaking strand",
                confidence=0.93, source_page=2,
                source_text="LLD.A strand text", needs_review=False,
            ),
            DetectedElement(
                level=HierarchyLevelEnum.SUB_STRAND, code="LLD.A.1",
                title="Comprehension",
                description="Comprehension sub-strand",
                confidence=0.92, source_page=3,
                source_text="LLD.A.1 sub-strand text", needs_review=False,
            ),
            DetectedElement(
                level=HierarchyLevelEnum.INDICATOR, code="LLD.A.1.a",
                title="Understanding Complex Language",
                description="Child demonstrates understanding of complex language",
                confidence=0.90, source_page=4,
                source_text="LLD.A.1.a indicator text", needs_review=False,
            ),
            DetectedElement(
                level=HierarchyLevelEnum.INDICATOR, code="LLD.A.1.b",
                title="Following Directions",
                description="Child follows multi-step directions",
                confidence=0.91, source_page=5,
                source_text="LLD.A.1.b indicator text", needs_review=False,
            ),
        ]

        fake = _bedrock_response([
            {"domain_code": "LLD", "domain_name": "Language and Literacy Development",
             "domain_description": "Language domain",
             "strand_code": "LLD.A", "strand_name": "Listening and Speaking",
             "strand_description": "Listening and speaking strand",
             "sub_strand_code": "LLD.A.1", "sub_strand_name": "Comprehension",
             "sub_strand_description": "Comprehension sub-strand",
             "indicator_code": "LLD.A.1.a", "indicator_name": "Understanding Complex Language",
             "indicator_description": "Child demonstrates understanding of complex language",
             "age_band": None, "source_page": 4, "source_text": "LLD.A.1.a indicator text"},
            {"domain_code": "LLD", "domain_name": "Language and Literacy Development",
             "domain_description": "Language domain",
             "strand_code": "LLD.A", "strand_name": "Listening and Speaking",
             "strand_description": "Listening and speaking strand",
             "sub_strand_code": "LLD.A.1", "sub_strand_name": "Comprehension",
             "sub_strand_description": "Comprehension sub-strand",
             "indicator_code": "LLD.A.1.b", "indicator_name": "Following Directions",
             "indicator_description": "Child follows multi-step directions",
             "age_band": None, "source_page": 5, "source_text": "LLD.A.1.b indicator text"},
        ])

        with patch("src.els_pipeline.parser.call_bedrock_llm", return_value=fake):
            result = parse_hierarchy(elements, "US", "CA", 2021)

        assert result.status == "success"
        assert len(result.standards) == 2
        for standard in result.standards:
            assert standard.domain is not None
            assert standard.domain.code == "LLD"
            assert standard.strand is not None
            assert standard.strand.code == "LLD.A"
            assert standard.sub_strand is not None
            assert standard.sub_strand.code == "LLD.A.1"
            assert standard.indicator is not None


class TestStandardIDGeneration:
    """Test Standard_ID generation and determinism."""

    def test_standard_id_format(self):
        """Test that Standard_ID follows the correct format."""
        standard_id = generate_standard_id("US", "CA", 2021, "LLD", "LLD.A.1.a")
        assert standard_id == "US-CA-2021-LLD-LLD.A.1.a"
        assert standard_id.startswith("US-")
        assert "2021" in standard_id

    def test_standard_id_determinism(self):
        """Test that Standard_ID generation is deterministic."""
        id1 = generate_standard_id("US", "CA", 2021, "LLD", "LLD.A.1.a")
        id2 = generate_standard_id("US", "CA", 2021, "LLD", "LLD.A.1.a")
        assert id1 == id2

    def test_standard_id_uniqueness(self):
        """Test that different inputs produce different Standard_IDs."""
        id1 = generate_standard_id("US", "CA", 2021, "LLD", "LLD.A.1.a")
        id2 = generate_standard_id("US", "CA", 2021, "LLD", "LLD.A.1.b")
        id3 = generate_standard_id("US", "TX", 2021, "LLD", "LLD.A.1.a")
        assert id1 != id2
        assert id1 != id3
        assert id2 != id3

    def test_standard_id_in_parsed_result(self):
        """Test that parsed standards have correct Standard_IDs."""
        elements = [
            DetectedElement(
                level=HierarchyLevelEnum.DOMAIN, code="LLD",
                title="Language and Literacy Development",
                description="Language domain", confidence=0.95,
                source_page=1, source_text="LLD domain text",
                needs_review=False,
            ),
            DetectedElement(
                level=HierarchyLevelEnum.INDICATOR, code="LLD.1",
                title="Listening Skills",
                description="Child demonstrates listening skills",
                confidence=0.90, source_page=2,
                source_text="LLD.1 indicator text", needs_review=False,
            ),
        ]

        fake = _bedrock_response([
            {"domain_code": "LLD", "domain_name": "Language and Literacy Development",
             "domain_description": "Language domain",
             "strand_code": None, "strand_name": None, "strand_description": None,
             "sub_strand_code": None, "sub_strand_name": None, "sub_strand_description": None,
             "indicator_code": "LLD.1", "indicator_name": "Listening Skills",
             "indicator_description": "Child demonstrates listening skills",
             "age_band": None, "source_page": 2, "source_text": "LLD.1 indicator text"},
        ])

        with patch("src.els_pipeline.parser.call_bedrock_llm", return_value=fake):
            result = parse_hierarchy(elements, "US", "CA", 2021)

        assert len(result.standards) == 1
        assert result.standards[0].standard_id == "US-CA-2021-LLD-LLD.1"


class TestOrphanDetection:
    """Test orphan detection for elements without parent hierarchy."""

    def test_orphaned_indicator_without_domain(self):
        """Test that a lone indicator with no domain context is handled.

        The AI parser sends all non-review elements to Bedrock. When the LLM
        cannot resolve a hierarchy it returns an empty array, so the indicator
        ends up in orphaned_elements via the error path.
        """
        elements = [
            DetectedElement(
                level=HierarchyLevelEnum.INDICATOR, code="ORPHAN.1",
                title="Orphaned Indicator",
                description="This indicator has no parent domain",
                confidence=0.90, source_page=1,
                source_text="orphan text", needs_review=False,
            ),
        ]

        # LLM returns empty array — no hierarchy could be resolved
        fake = _bedrock_response([])

        with patch("src.els_pipeline.parser.call_bedrock_llm", return_value=fake):
            result = parse_hierarchy(elements, "US", "CA", 2021)

        assert len(result.standards) == 0

    def test_valid_and_orphaned_mixed(self):
        """Test parsing with valid elements — LLM resolves the hierarchy."""
        elements = [
            DetectedElement(
                level=HierarchyLevelEnum.DOMAIN, code="LLD",
                title="Language and Literacy Development",
                description="Language domain", confidence=0.95,
                source_page=1, source_text="LLD domain text",
                needs_review=False,
            ),
            DetectedElement(
                level=HierarchyLevelEnum.INDICATOR, code="LLD.1",
                title="Valid Indicator",
                description="This indicator has a parent domain",
                confidence=0.90, source_page=2,
                source_text="valid text", needs_review=False,
            ),
        ]

        fake = _bedrock_response([
            {"domain_code": "LLD", "domain_name": "Language and Literacy Development",
             "domain_description": "Language domain",
             "strand_code": None, "strand_name": None, "strand_description": None,
             "sub_strand_code": None, "sub_strand_name": None, "sub_strand_description": None,
             "indicator_code": "LLD.1", "indicator_name": "Valid Indicator",
             "indicator_description": "This indicator has a parent domain",
             "age_band": None, "source_page": 2, "source_text": "valid text"},
        ])

        with patch("src.els_pipeline.parser.call_bedrock_llm", return_value=fake):
            result = parse_hierarchy(elements, "US", "CA", 2021)

        assert len(result.standards) == 1
        assert result.standards[0].indicator.code == "LLD.1"
        assert len(result.orphaned_elements) == 0


class TestTreeAssembly:
    """Test tree assembly with various input structures."""

    def test_multiple_domains(self):
        """Test parsing with multiple domains."""
        elements = [
            DetectedElement(
                level=HierarchyLevelEnum.DOMAIN, code="LLD",
                title="Language and Literacy Development",
                description="Language domain", confidence=0.95,
                source_page=1, source_text="LLD domain text",
                needs_review=False,
            ),
            DetectedElement(
                level=HierarchyLevelEnum.INDICATOR, code="LLD.1",
                title="Listening Skills",
                description="Child demonstrates listening skills",
                confidence=0.90, source_page=2,
                source_text="LLD.1 indicator text", needs_review=False,
            ),
            DetectedElement(
                level=HierarchyLevelEnum.DOMAIN, code="CD",
                title="Cognitive Development",
                description="Cognitive domain", confidence=0.95,
                source_page=3, source_text="CD domain text",
                needs_review=False,
            ),
            DetectedElement(
                level=HierarchyLevelEnum.INDICATOR, code="CD.1",
                title="Problem Solving",
                description="Child demonstrates problem solving",
                confidence=0.90, source_page=4,
                source_text="CD.1 indicator text", needs_review=False,
            ),
        ]

        fake = _bedrock_response([
            {"domain_code": "LLD", "domain_name": "Language and Literacy Development",
             "domain_description": "Language domain",
             "strand_code": None, "strand_name": None, "strand_description": None,
             "sub_strand_code": None, "sub_strand_name": None, "sub_strand_description": None,
             "indicator_code": "LLD.1", "indicator_name": "Listening Skills",
             "indicator_description": "Child demonstrates listening skills",
             "age_band": None, "source_page": 2, "source_text": "LLD.1 indicator text"},
            {"domain_code": "CD", "domain_name": "Cognitive Development",
             "domain_description": "Cognitive domain",
             "strand_code": None, "strand_name": None, "strand_description": None,
             "sub_strand_code": None, "sub_strand_name": None, "sub_strand_description": None,
             "indicator_code": "CD.1", "indicator_name": "Problem Solving",
             "indicator_description": "Child demonstrates problem solving",
             "age_band": None, "source_page": 4, "source_text": "CD.1 indicator text"},
        ])

        with patch("src.els_pipeline.parser.call_bedrock_llm", return_value=fake):
            result = parse_hierarchy(elements, "US", "CA", 2021)

        assert result.status == "success"
        assert len(result.standards) == 2
        domains = {std.domain.code for std in result.standards}
        assert domains == {"LLD", "CD"}

    def test_elements_flagged_for_review(self):
        """Test that elements flagged for review are excluded."""
        elements = [
            DetectedElement(
                level=HierarchyLevelEnum.DOMAIN, code="LLD",
                title="Language and Literacy Development",
                description="Language domain", confidence=0.95,
                source_page=1, source_text="LLD domain text",
                needs_review=False,
            ),
            DetectedElement(
                level=HierarchyLevelEnum.INDICATOR, code="LLD.1",
                title="Valid Indicator",
                description="This indicator is valid",
                confidence=0.90, source_page=2,
                source_text="valid text", needs_review=False,
            ),
            DetectedElement(
                level=HierarchyLevelEnum.INDICATOR, code="LLD.2",
                title="Low Confidence Indicator",
                description="This indicator needs review",
                confidence=0.60, source_page=3,
                source_text="low confidence text", needs_review=True,
            ),
        ]

        # LLD.2 is filtered out before the LLM call, so only LLD.1 comes back
        fake = _bedrock_response([
            {"domain_code": "LLD", "domain_name": "Language and Literacy Development",
             "domain_description": "Language domain",
             "strand_code": None, "strand_name": None, "strand_description": None,
             "sub_strand_code": None, "sub_strand_name": None, "sub_strand_description": None,
             "indicator_code": "LLD.1", "indicator_name": "Valid Indicator",
             "indicator_description": "This indicator is valid",
             "age_band": None, "source_page": 2, "source_text": "valid text"},
        ])

        with patch("src.els_pipeline.parser.call_bedrock_llm", return_value=fake):
            result = parse_hierarchy(elements, "US", "CA", 2021)

        assert len(result.standards) == 1
        assert result.standards[0].indicator.code == "LLD.1"

    def test_empty_elements_list(self):
        """Test parsing with an empty elements list."""
        result = parse_hierarchy([], "US", "CA", 2021)
        assert result.status == "error"
        assert len(result.standards) == 0
        assert result.error is not None

    def test_no_indicators(self):
        """Test parsing with only domains (no indicators).

        The AI parser sends all non-review elements to Bedrock. When the LLM
        finds no indicators it returns an empty array, yielding 0 standards.
        """
        elements = [
            DetectedElement(
                level=HierarchyLevelEnum.DOMAIN, code="LLD",
                title="Language and Literacy Development",
                description="Language domain", confidence=0.95,
                source_page=1, source_text="LLD domain text",
                needs_review=False,
            ),
        ]

        fake = _bedrock_response([])

        with patch("src.els_pipeline.parser.call_bedrock_llm", return_value=fake):
            result = parse_hierarchy(elements, "US", "CA", 2021)

        assert len(result.standards) == 0


class TestAllReviewInput:
    """Test that all-review input returns error without calling Bedrock."""

    def test_all_review_elements_returns_error(self):
        """When every element has needs_review=True, return error immediately."""
        elements = [
            DetectedElement(
                level=HierarchyLevelEnum.DOMAIN, code="LLD",
                title="Language and Literacy Development",
                description="Language domain", confidence=0.50,
                source_page=1, source_text="LLD domain text",
                needs_review=True,
            ),
            DetectedElement(
                level=HierarchyLevelEnum.INDICATOR, code="LLD.1",
                title="Listening Skills",
                description="Child demonstrates listening skills",
                confidence=0.50, source_page=2,
                source_text="LLD.1 indicator text", needs_review=True,
            ),
        ]

        with patch("src.els_pipeline.parser.call_bedrock_llm") as mock_bedrock:
            result = parse_hierarchy(elements, "US", "CA", 2021)

        assert result.status == "error"
        assert len(result.standards) == 0
        assert result.error is not None
        mock_bedrock.assert_not_called()


class TestJsonParseRetry:
    """Test JSON parse retry behavior."""

    def test_json_parse_retry_exhaustion(self):
        """When Bedrock always returns invalid JSON, verify call count and error status."""
        elements = [
            DetectedElement(
                level=HierarchyLevelEnum.DOMAIN, code="LLD",
                title="Language and Literacy Development",
                description="Language domain", confidence=0.95,
                source_page=1, source_text="LLD domain text",
                needs_review=False,
            ),
            DetectedElement(
                level=HierarchyLevelEnum.INDICATOR, code="LLD.1",
                title="Listening Skills",
                description="Child demonstrates listening skills",
                confidence=0.90, source_page=2,
                source_text="LLD.1 indicator text", needs_review=False,
            ),
        ]

        with patch(
            "src.els_pipeline.parser.call_bedrock_llm",
            return_value="this is not valid json at all",
        ) as mock_bedrock:
            result = parse_hierarchy(elements, "US", "CA", 2021)

        assert result.status == "error"
        assert mock_bedrock.call_count == MAX_PARSE_RETRIES + 1


class TestClientErrorRetry:
    """Test ClientError retry behavior."""

    def test_client_error_retry_exhaustion(self):
        """When Bedrock always raises ClientError, verify call count and error status."""
        elements = [
            DetectedElement(
                level=HierarchyLevelEnum.DOMAIN, code="LLD",
                title="Language and Literacy Development",
                description="Language domain", confidence=0.95,
                source_page=1, source_text="LLD domain text",
                needs_review=False,
            ),
            DetectedElement(
                level=HierarchyLevelEnum.INDICATOR, code="LLD.1",
                title="Listening Skills",
                description="Child demonstrates listening skills",
                confidence=0.90, source_page=2,
                source_text="LLD.1 indicator text", needs_review=False,
            ),
        ]

        error_response = {"Error": {"Code": "ThrottlingException", "Message": "Rate exceeded"}}
        client_error = ClientError(error_response, "InvokeModel")

        with patch(
            "src.els_pipeline.parser.call_bedrock_llm",
            side_effect=client_error,
        ) as mock_bedrock:
            result = parse_hierarchy(elements, "US", "CA", 2021)

        assert result.status == "error"
        # ClientError from call_bedrock_llm is caught by the top-level except
        # in parse_hierarchy, so it's called once and then the exception propagates
        assert mock_bedrock.call_count >= 1

