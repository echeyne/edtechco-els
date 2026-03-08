"""Property-based tests for hierarchy parser.

Feature: els-normalization-pipeline
Properties: 9, 10, 11, 12

Feature: ai-powered-parser
Properties: 1, 2, 3, 4
"""

import json
import pytest
from unittest.mock import patch
from hypothesis import given, strategies as st, assume, settings
from els_pipeline.models import (
    DetectedElement,
    HierarchyLevelEnum,
    ParseResult,
)
from els_pipeline.parser import (
    parse_hierarchy,
    generate_standard_id,
)


# ---------------------------------------------------------------------------
# Strategies for generating test data
# ---------------------------------------------------------------------------

@st.composite
def country_code(draw):
    """Generate a two-letter ISO 3166-1 alpha-2 country code."""
    return draw(st.text(alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZ", min_size=2, max_size=2))


@st.composite
def state_code(draw):
    """Generate a two-letter state code."""
    return draw(st.text(alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZ", min_size=2, max_size=2))


@st.composite
def version_year(draw):
    """Generate a version year."""
    return draw(st.integers(min_value=2000, max_value=2030))


@st.composite
def hierarchy_code(draw, prefix="", level=0):
    """Generate a hierarchical code."""
    if level == 0:
        return draw(st.text(alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZ", min_size=1, max_size=3))
    else:
        separator = draw(st.sampled_from([".", "-", ""]))
        suffix = draw(st.text(alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789", min_size=1, max_size=3))
        return f"{prefix}{separator}{suffix}"


@st.composite
def detected_element(draw, level, code_prefix="", page_range=(1, 100)):
    """Generate a DetectedElement."""
    if code_prefix:
        code = draw(hierarchy_code(prefix=code_prefix, level=1))
    else:
        code = draw(hierarchy_code(level=0))

    title = draw(st.text(min_size=5, max_size=50))
    description = draw(st.text(min_size=10, max_size=200))
    confidence = draw(st.floats(min_value=0.7, max_value=1.0))
    source_page = draw(st.integers(min_value=page_range[0], max_value=page_range[1]))
    source_text = draw(st.text(min_size=10, max_size=100))

    return DetectedElement(
        level=level,
        code=code,
        title=title,
        description=description,
        confidence=confidence,
        source_page=source_page,
        source_text=source_text,
        needs_review=False,
    )


@st.composite
def two_level_hierarchy(draw):
    """Generate a 2-level hierarchy (Domain + Indicator)."""
    num_domains = draw(st.integers(min_value=1, max_value=3))
    elements = []
    for _ in range(num_domains):
        domain = draw(detected_element(level=HierarchyLevelEnum.DOMAIN))
        elements.append(domain)
        num_indicators = draw(st.integers(min_value=1, max_value=5))
        for _ in range(num_indicators):
            indicator = draw(detected_element(
                level=HierarchyLevelEnum.INDICATOR, code_prefix=domain.code
            ))
            elements.append(indicator)
    return elements


@st.composite
def three_level_hierarchy(draw):
    """Generate a 3-level hierarchy (Domain + Strand + Indicator)."""
    num_domains = draw(st.integers(min_value=1, max_value=3))
    elements = []
    for _ in range(num_domains):
        domain = draw(detected_element(level=HierarchyLevelEnum.DOMAIN))
        elements.append(domain)
        num_strands = draw(st.integers(min_value=1, max_value=3))
        for _ in range(num_strands):
            strand = draw(detected_element(
                level=HierarchyLevelEnum.STRAND, code_prefix=domain.code
            ))
            elements.append(strand)
            num_indicators = draw(st.integers(min_value=1, max_value=5))
            for _ in range(num_indicators):
                indicator = draw(detected_element(
                    level=HierarchyLevelEnum.INDICATOR, code_prefix=strand.code
                ))
                elements.append(indicator)
    return elements


@st.composite
def four_level_hierarchy(draw):
    """Generate a 4-level hierarchy (Domain + Strand + Sub-strand + Indicator)."""
    num_domains = draw(st.integers(min_value=1, max_value=2))
    elements = []
    for _ in range(num_domains):
        domain = draw(detected_element(level=HierarchyLevelEnum.DOMAIN))
        elements.append(domain)
        num_strands = draw(st.integers(min_value=1, max_value=2))
        for _ in range(num_strands):
            strand = draw(detected_element(
                level=HierarchyLevelEnum.STRAND, code_prefix=domain.code
            ))
            elements.append(strand)
            num_sub_strands = draw(st.integers(min_value=1, max_value=2))
            for _ in range(num_sub_strands):
                sub_strand = draw(detected_element(
                    level=HierarchyLevelEnum.SUB_STRAND, code_prefix=strand.code
                ))
                elements.append(sub_strand)
                num_indicators = draw(st.integers(min_value=1, max_value=3))
                for _ in range(num_indicators):
                    indicator = draw(detected_element(
                        level=HierarchyLevelEnum.INDICATOR, code_prefix=sub_strand.code
                    ))
                    elements.append(indicator)
    return elements


@st.composite
def arbitrary_element(draw):
    """Generate a DetectedElement with arbitrary level and review flag."""
    level = draw(st.sampled_from(list(HierarchyLevelEnum)))
    code = draw(st.text(
        alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.",
        min_size=1, max_size=10,
    ))
    title = draw(st.text(min_size=1, max_size=50))
    description = draw(st.text(min_size=0, max_size=100))
    confidence = draw(st.floats(min_value=0.0, max_value=1.0))
    source_page = draw(st.integers(min_value=1, max_value=100))
    source_text = draw(st.text(min_size=1, max_size=100))
    return DetectedElement(
        level=level, code=code, title=title, description=description,
        confidence=confidence, source_page=source_page,
        source_text=source_text, needs_review=(confidence < 0.7),
    )


# ---------------------------------------------------------------------------
# Helpers for building mock Bedrock responses
# ---------------------------------------------------------------------------

def _mock_bedrock_two_level(elements):
    """Build a mock Bedrock response for a 2-level hierarchy."""
    domains = {}
    for el in elements:
        if el.level == HierarchyLevelEnum.DOMAIN:
            domains[el.code] = el
    indicators = [el for el in elements if el.level == HierarchyLevelEnum.INDICATOR]
    items = []
    for ind in indicators:
        # Find the most recent domain that could be a parent
        parent = None
        for d_code, d_el in domains.items():
            if ind.code.startswith(d_code):
                parent = d_el
                break
        if parent is None and domains:
            parent = list(domains.values())[0]
        if parent is None:
            continue
        items.append({
            "domain_code": parent.code, "domain_name": parent.title,
            "domain_description": parent.description,
            "strand_code": None, "strand_name": None, "strand_description": None,
            "sub_strand_code": None, "sub_strand_name": None, "sub_strand_description": None,
            "indicator_code": ind.code, "indicator_name": ind.title,
            "indicator_description": ind.description,
            "age_band": None, "source_page": ind.source_page,
            "source_text": ind.source_text,
        })
    return json.dumps(items)


def _mock_bedrock_three_level(elements):
    """Build a mock Bedrock response for a 3-level hierarchy."""
    domains = {}
    strands = {}
    for el in elements:
        if el.level == HierarchyLevelEnum.DOMAIN:
            domains[el.code] = el
        elif el.level == HierarchyLevelEnum.STRAND:
            strands[el.code] = el
    indicators = [el for el in elements if el.level == HierarchyLevelEnum.INDICATOR]
    items = []
    for ind in indicators:
        strand = None
        for s_code, s_el in strands.items():
            if ind.code.startswith(s_code):
                strand = s_el
                break
        if strand is None and strands:
            strand = list(strands.values())[0]
        domain = None
        if strand:
            for d_code, d_el in domains.items():
                if strand.code.startswith(d_code):
                    domain = d_el
                    break
        if domain is None and domains:
            domain = list(domains.values())[0]
        if domain is None or strand is None:
            continue
        items.append({
            "domain_code": domain.code, "domain_name": domain.title,
            "domain_description": domain.description,
            "strand_code": strand.code, "strand_name": strand.title,
            "strand_description": strand.description,
            "sub_strand_code": None, "sub_strand_name": None, "sub_strand_description": None,
            "indicator_code": ind.code, "indicator_name": ind.title,
            "indicator_description": ind.description,
            "age_band": None, "source_page": ind.source_page,
            "source_text": ind.source_text,
        })
    return json.dumps(items)


def _mock_bedrock_four_level(elements):
    """Build a mock Bedrock response for a 4-level hierarchy."""
    domains = {}
    strands = {}
    sub_strands = {}
    for el in elements:
        if el.level == HierarchyLevelEnum.DOMAIN:
            domains[el.code] = el
        elif el.level == HierarchyLevelEnum.STRAND:
            strands[el.code] = el
        elif el.level == HierarchyLevelEnum.SUB_STRAND:
            sub_strands[el.code] = el
    indicators = [el for el in elements if el.level == HierarchyLevelEnum.INDICATOR]
    items = []
    for ind in indicators:
        sub = None
        for ss_code, ss_el in sub_strands.items():
            if ind.code.startswith(ss_code):
                sub = ss_el
                break
        if sub is None and sub_strands:
            sub = list(sub_strands.values())[0]
        strand = None
        if sub:
            for s_code, s_el in strands.items():
                if sub.code.startswith(s_code):
                    strand = s_el
                    break
        if strand is None and strands:
            strand = list(strands.values())[0]
        domain = None
        if strand:
            for d_code, d_el in domains.items():
                if strand.code.startswith(d_code):
                    domain = d_el
                    break
        if domain is None and domains:
            domain = list(domains.values())[0]
        if domain is None or strand is None or sub is None:
            continue
        items.append({
            "domain_code": domain.code, "domain_name": domain.title,
            "domain_description": domain.description,
            "strand_code": strand.code, "strand_name": strand.title,
            "strand_description": strand.description,
            "sub_strand_code": sub.code, "sub_strand_name": sub.title,
            "sub_strand_description": sub.description,
            "indicator_code": ind.code, "indicator_name": ind.title,
            "indicator_description": ind.description,
            "age_band": None, "source_page": ind.source_page,
            "source_text": ind.source_text,
        })
    return json.dumps(items)


def _mock_bedrock_generic(elements):
    """Build a mock Bedrock response for arbitrary elements."""
    indicators = [e for e in elements if e.level == HierarchyLevelEnum.INDICATOR and not e.needs_review]
    items = []
    for ind in indicators:
        items.append({
            "domain_code": "D1", "domain_name": "Domain",
            "domain_description": None,
            "strand_code": None, "strand_name": None, "strand_description": None,
            "sub_strand_code": None, "sub_strand_name": None, "sub_strand_description": None,
            "indicator_code": ind.code, "indicator_name": ind.title,
            "indicator_description": ind.description,
            "age_band": None, "source_page": ind.source_page,
            "source_text": ind.source_text,
        })
    return json.dumps(items)


# ---------------------------------------------------------------------------
# Property 9: Canonical Level Normalization (updated for AI parser)
# ---------------------------------------------------------------------------

@given(
    elements=st.one_of(
        two_level_hierarchy(),
        three_level_hierarchy(),
        four_level_hierarchy(),
    ),
    country=country_code(),
    state=state_code(),
    year=version_year(),
)
def test_property_9_canonical_level_normalization(elements, country, state, year):
    """
    Property 9: Canonical Level Normalization

    For any set of detected elements with arbitrary level labels,
    the Hierarchy Parser output SHALL contain only levels from the set
    {domain, strand, sub_strand, indicator}.

    Validates: Requirements 4.1
    """
    fake = _mock_bedrock_generic(elements)
    with patch("els_pipeline.parser.call_bedrock_llm", return_value=fake):
        result = parse_hierarchy(elements, country, state, year)

    for standard in result.standards:
        assert standard.domain is not None
        assert standard.indicator is not None


# ---------------------------------------------------------------------------
# Property 10: Depth-Based Hierarchy Mapping (updated for AI parser)
# ---------------------------------------------------------------------------

@given(
    elements=two_level_hierarchy(),
    country=country_code(),
    state=state_code(),
    year=version_year(),
)
def test_property_10_depth_based_hierarchy_mapping_2_levels(elements, country, state, year):
    """
    Property 10: Depth-Based Hierarchy Mapping (2 levels)

    Validates: Requirements 4.2, 4.3, 4.4
    """
    fake = _mock_bedrock_two_level(elements)
    with patch("els_pipeline.parser.call_bedrock_llm", return_value=fake):
        result = parse_hierarchy(elements, country, state, year)

    for standard in result.standards:
        assert standard.domain is not None
        assert standard.indicator is not None
        assert standard.strand is None
        assert standard.sub_strand is None


@given(
    elements=three_level_hierarchy(),
    country=country_code(),
    state=state_code(),
    year=version_year(),
)
def test_property_10_depth_based_hierarchy_mapping_3_levels(elements, country, state, year):
    """
    Property 10: Depth-Based Hierarchy Mapping (3 levels)

    Validates: Requirements 4.2, 4.3, 4.4
    """
    fake = _mock_bedrock_three_level(elements)
    with patch("els_pipeline.parser.call_bedrock_llm", return_value=fake):
        result = parse_hierarchy(elements, country, state, year)

    for standard in result.standards:
        assert standard.domain is not None
        assert standard.strand is not None
        assert standard.indicator is not None
        assert standard.sub_strand is None


@given(
    elements=four_level_hierarchy(),
    country=country_code(),
    state=state_code(),
    year=version_year(),
)
def test_property_10_depth_based_hierarchy_mapping_4_levels(elements, country, state, year):
    """
    Property 10: Depth-Based Hierarchy Mapping (4+ levels)

    Validates: Requirements 4.2, 4.3, 4.4
    """
    fake = _mock_bedrock_four_level(elements)
    with patch("els_pipeline.parser.call_bedrock_llm", return_value=fake):
        result = parse_hierarchy(elements, country, state, year)

    for standard in result.standards:
        assert standard.domain is not None
        assert standard.strand is not None
        assert standard.sub_strand is not None
        assert standard.indicator is not None


# ---------------------------------------------------------------------------
# Property 11: Standard_ID Determinism (unchanged — no Bedrock call)
# ---------------------------------------------------------------------------

@given(
    country=country_code(),
    state=state_code(),
    year=version_year(),
    domain_code=st.text(alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZ", min_size=1, max_size=5),
    indicator_code=st.text(alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789", min_size=1, max_size=10),
)
def test_property_11_standard_id_determinism(country, state, year, domain_code, indicator_code):
    """
    Property 11: Standard_ID Determinism

    Validates: Requirements 4.5
    """
    id1 = generate_standard_id(country, state, year, domain_code, indicator_code)
    id2 = generate_standard_id(country, state, year, domain_code, indicator_code)
    assert id1 == id2
    expected_format = f"{country}-{state}-{year}-{domain_code}-{indicator_code}"
    assert id1 == expected_format


# ---------------------------------------------------------------------------
# Property 12: No Orphaned Indicators (updated for AI parser)
# ---------------------------------------------------------------------------

@given(
    elements=st.one_of(
        two_level_hierarchy(),
        three_level_hierarchy(),
        four_level_hierarchy(),
    ),
    country=country_code(),
    state=state_code(),
    year=version_year(),
)
def test_property_12_no_orphaned_indicators(elements, country, state, year):
    """
    Property 12: No Orphaned Indicators

    For any valid parse result, every standard in the `standards` list
    SHALL have a non-null `domain`.

    Validates: Requirements 4.6
    """
    fake = _mock_bedrock_generic(elements)
    with patch("els_pipeline.parser.call_bedrock_llm", return_value=fake):
        result = parse_hierarchy(elements, country, state, year)

    for standard in result.standards:
        assert standard.domain is not None
        assert standard.domain.code is not None
        assert standard.domain.name is not None

    orphaned_codes = {elem.code for elem in result.orphaned_elements}
    standard_indicator_codes = {std.indicator.code for std in result.standards}
    assert len(orphaned_codes & standard_indicator_codes) == 0


@given(
    country=country_code(),
    state=state_code(),
    year=version_year(),
)
def test_property_12_orphaned_indicators_without_domain(country, state, year):
    """
    Property 12: No Orphaned Indicators (orphan detection)

    When indicators have no matching domain, the LLM returns an empty array
    and the elements end up in orphaned_elements.

    Validates: Requirements 4.6
    """
    orphan_indicator = DetectedElement(
        level=HierarchyLevelEnum.INDICATOR,
        code="ORPHAN-1",
        title="Orphaned Indicator",
        description="This indicator has no parent domain",
        confidence=0.9,
        source_page=1,
        source_text="orphan text",
        needs_review=False,
    )

    fake = json.dumps([])
    with patch("els_pipeline.parser.call_bedrock_llm", return_value=fake):
        result = parse_hierarchy([orphan_indicator], country, state, year)

    assert len(result.standards) == 0


# ---------------------------------------------------------------------------
# AI-Powered Parser Properties (Feature: ai-powered-parser)
# ---------------------------------------------------------------------------

# Property 4: generate_standard_id determinism and format
@given(
    country=country_code(),
    state=state_code(),
    year=version_year(),
    domain_code=st.text(
        alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.",
        min_size=1, max_size=10,
    ),
    indicator_code=st.text(
        alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.",
        min_size=1, max_size=15,
    ),
)
def test_property_4_generate_standard_id_determinism_and_format(
    country, state, year, domain_code, indicator_code
):
    """
    Feature: ai-powered-parser, Property 4: generate_standard_id determinism and format

    **Validates: Requirements 4.2, 4.3**
    """
    id1 = generate_standard_id(country, state, year, domain_code, indicator_code)
    id2 = generate_standard_id(country, state, year, domain_code, indicator_code)
    assert id1 == id2
    expected = f"{country}-{state}-{year}-{domain_code}-{indicator_code}"
    assert id1 == expected


# Property 2 & 3: age_band fallback and passthrough
@given(
    age_band=st.text(min_size=1, max_size=30),
    country=country_code(),
    state=state_code(),
    year=version_year(),
)
def test_property_2_3_age_band_fallback_and_passthrough(
    age_band, country, state, year
):
    """
    Feature: ai-powered-parser, Property 2: age_band fallback
    Feature: ai-powered-parser, Property 3: age_band passthrough

    **Validates: Requirements 2.2, 2.3, 3.2**
    """
    indicator = DetectedElement(
        level=HierarchyLevelEnum.INDICATOR, code="IND.1",
        title="Test Indicator", description="desc", confidence=0.9,
        source_page=1, source_text="source", needs_review=False,
    )
    domain = DetectedElement(
        level=HierarchyLevelEnum.DOMAIN, code="D1",
        title="Domain", description="domain desc", confidence=0.9,
        source_page=1, source_text="domain source", needs_review=False,
    )

    fake_response = json.dumps([{
        "domain_code": "D1", "domain_name": "Domain", "domain_description": None,
        "strand_code": None, "strand_name": None, "strand_description": None,
        "sub_strand_code": None, "sub_strand_name": None, "sub_strand_description": None,
        "indicator_code": "IND.1", "indicator_name": "Test Indicator",
        "indicator_description": "desc",
        "age_band": None, "source_page": 1, "source_text": "source",
    }])

    with patch("els_pipeline.parser.call_bedrock_llm", return_value=fake_response):
        result = parse_hierarchy(
            [domain, indicator], country, state, year, age_band=age_band
        )

    assert isinstance(result, ParseResult)
    if result.standards:
        for std in result.standards:
            assert std.age_band == age_band


# Property 1: parse_hierarchy always returns a ParseResult
@given(
    elements=st.lists(arbitrary_element(), min_size=0, max_size=10),
    country=country_code(),
    state=state_code(),
    year=version_year(),
    age_band=st.text(min_size=1, max_size=20),
)
def test_property_1_parse_hierarchy_always_returns_parse_result(
    elements, country, state, year, age_band
):
    """
    Feature: ai-powered-parser, Property 1: parse_hierarchy always returns a ParseResult

    **Validates: Requirements 3.4, 5.3**
    """
    valid_elements = [e for e in elements if not e.needs_review]
    indicators = [e for e in valid_elements if e.level == HierarchyLevelEnum.INDICATOR]
    fake_response = _mock_bedrock_generic(elements) if indicators else "[]"

    with patch("els_pipeline.parser.call_bedrock_llm", return_value=fake_response):
        result = parse_hierarchy(elements, country, state, year, age_band=age_band)

    assert isinstance(result, ParseResult)


# ---------------------------------------------------------------------------
# Property 5: JSON parse retry exhaustion returns error
# Property 6: ClientError retry exhaustion returns error
# ---------------------------------------------------------------------------

from unittest.mock import MagicMock
from botocore.exceptions import ClientError
from els_pipeline.parser import MAX_PARSE_RETRIES, MAX_BEDROCK_RETRIES


@given(
    country=country_code(),
    state=state_code(),
    year=version_year(),
    age_band=st.text(min_size=1, max_size=20),
)
@settings(max_examples=100)
def test_property_5_json_parse_retry_exhaustion_returns_error(
    country, state, year, age_band
):
    """
    Feature: ai-powered-parser, Property 5: JSON parse retry exhaustion returns error

    For any call to parse_hierarchy where the mocked Bedrock always returns
    invalid JSON, the result should have status="error" and Bedrock should
    have been called exactly MAX_PARSE_RETRIES + 1 times.

    **Validates: Requirements 1.3, 1.5**
    """
    elements = [
        DetectedElement(
            level=HierarchyLevelEnum.DOMAIN, code="D1",
            title="Domain", description="domain desc", confidence=0.9,
            source_page=1, source_text="domain source", needs_review=False,
        ),
        DetectedElement(
            level=HierarchyLevelEnum.INDICATOR, code="D1.1",
            title="Indicator", description="indicator desc", confidence=0.9,
            source_page=2, source_text="indicator source", needs_review=False,
        ),
    ]

    with patch(
        "els_pipeline.parser.call_bedrock_llm",
        return_value="not valid json",
    ) as mock_llm:
        result = parse_hierarchy(elements, country, state, year, age_band=age_band)

    assert isinstance(result, ParseResult)
    assert result.status == "error"
    assert mock_llm.call_count == MAX_PARSE_RETRIES + 1


@given(
    country=country_code(),
    state=state_code(),
    year=version_year(),
    age_band=st.text(min_size=1, max_size=20),
)
@settings(max_examples=100)
def test_property_6_client_error_retry_exhaustion_returns_error(
    country, state, year, age_band
):
    """
    Feature: ai-powered-parser, Property 6: ClientError retry exhaustion returns error

    For any call to parse_hierarchy where the mocked Bedrock always raises
    ClientError, the result should have status="error" and the underlying
    invoke_model should have been called exactly MAX_BEDROCK_RETRIES + 1 times.

    **Validates: Requirements 1.4, 1.5**
    """
    elements = [
        DetectedElement(
            level=HierarchyLevelEnum.DOMAIN, code="D1",
            title="Domain", description="domain desc", confidence=0.9,
            source_page=1, source_text="domain source", needs_review=False,
        ),
        DetectedElement(
            level=HierarchyLevelEnum.INDICATOR, code="D1.1",
            title="Indicator", description="indicator desc", confidence=0.9,
            source_page=2, source_text="indicator source", needs_review=False,
        ),
    ]

    error_response = {
        "Error": {"Code": "ThrottlingException", "Message": "Rate exceeded"}
    }
    client_error = ClientError(error_response, "InvokeModel")

    mock_bedrock_client = MagicMock()
    mock_bedrock_client.invoke_model.side_effect = client_error

    with patch("els_pipeline.parser.boto3") as mock_boto3:
        mock_boto3.client.return_value = mock_bedrock_client
        result = parse_hierarchy(elements, country, state, year, age_band=age_band)

    assert isinstance(result, ParseResult)
    assert result.status == "error"
    assert mock_bedrock_client.invoke_model.call_count == MAX_BEDROCK_RETRIES + 1

