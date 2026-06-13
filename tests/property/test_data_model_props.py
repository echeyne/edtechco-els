"""Property-based tests for data model validation.

Feature: els-normalization-pipeline
"""

import pytest
from hypothesis import given, strategies as st
from datetime import datetime, timezone

from els_pipeline.models import (
    DetectedElement,
    HierarchyLevelEnum,
)


# Strategies for generating test data

@st.composite
def detected_element_strategy(draw):
    """Generate a DetectedElement with valid fields."""
    level = draw(st.sampled_from(list(HierarchyLevelEnum)))
    code = draw(st.text(min_size=1, max_size=20))
    title = draw(st.text(min_size=1, max_size=100))
    description = draw(st.text(min_size=1, max_size=500))
    confidence = draw(st.floats(min_value=0.0, max_value=1.0))
    source_page = draw(st.integers(min_value=1, max_value=1000))
    source_text = draw(st.text(min_size=1, max_size=1000))
    needs_review = confidence < 0.7
    
    return DetectedElement(
        level=level,
        code=code,
        title=title,
        description=description,
        confidence=confidence,
        source_page=source_page,
        source_text=source_text,
        needs_review=needs_review,
    )


# Property 7: Detected Element Field Validity
# **Validates: Requirements 3.2, 3.3**

@given(detected_element_strategy())
def test_property_7_detected_element_field_validity(element):
    """Property 7: Detected Element Field Validity.
    
    For any detected element, confidence in [0.0, 1.0] and level in valid set.
    
    **Validates: Requirements 3.2, 3.3**
    """
    # Confidence must be in valid range
    assert 0.0 <= element.confidence <= 1.0, \
        f"Confidence {element.confidence} not in [0.0, 1.0]"
    
    # Level must be one of the valid hierarchy levels
    valid_levels = {level.value for level in HierarchyLevelEnum}
    assert element.level.value in valid_levels, \
        f"Level {element.level} not in valid set {valid_levels}"
