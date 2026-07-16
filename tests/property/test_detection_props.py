"""Property-based tests for structure detection.

Feature: els-normalization-pipeline
"""

import pytest
from hypothesis import given, strategies as st

from els_pipeline.models import DetectedElement, HierarchyLevelEnum


# Strategy for generating valid hierarchy levels
hierarchy_level_strategy = st.sampled_from([
    HierarchyLevelEnum.DOMAIN,
    HierarchyLevelEnum.STRAND,
    HierarchyLevelEnum.SUB_STRAND,
    HierarchyLevelEnum.INDICATOR
])


# Strategy for generating DetectedElement objects
detected_element_strategy = st.builds(
    DetectedElement,
    level=hierarchy_level_strategy,
    code=st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=('Lu', 'Nd'), whitelist_characters='.-')),
    title=st.text(min_size=1, max_size=100),
    description=st.text(min_size=1, max_size=500),
    confidence=st.floats(min_value=0.0, max_value=1.0),
    source_page=st.integers(min_value=1, max_value=1000),
    source_text=st.text(min_size=1, max_size=200),
)


@given(st.lists(detected_element_strategy, min_size=1, max_size=50))
def test_property_7_detected_element_field_validity(elements: list):
    """
    Property 7: Detected Element Field Validity

    For any detected element, confidence in [0.0, 1.0] and level in valid set.

    Validates: Requirements 3.2, 3.3
    """
    valid_levels = {
        HierarchyLevelEnum.DOMAIN,
        HierarchyLevelEnum.STRAND,
        HierarchyLevelEnum.SUB_STRAND,
        HierarchyLevelEnum.INDICATOR
    }

    for element in elements:
        # Check confidence is in valid range
        assert 0.0 <= element.confidence <= 1.0, \
            f"Element confidence {element.confidence} must be in [0.0, 1.0]"

        # Check level is in valid set
        assert element.level in valid_levels, \
            f"Element level {element.level} must be one of {valid_levels}"
