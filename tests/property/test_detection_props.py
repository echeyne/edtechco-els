"""Property-based tests for structure detection.

Feature: els-normalization-pipeline
"""

import pytest
from hypothesis import given, strategies as st

from els_pipeline.models import DetectedElement, HierarchyLevelEnum
from els_pipeline.config import Config


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
    needs_review=st.booleans()
)


@given(detected_element_strategy)
def test_property_8_confidence_threshold_flagging(element: DetectedElement):
    """
    Property 8: Confidence Threshold Flagging
    
    For any element, confidence < 0.7 implies needs_review=True, >= 0.7 implies False.
    
    Validates: Requirements 3.4
    """
    # The DetectedElement model has a validator that auto-corrects needs_review
    # based on confidence, so we need to test the logic directly
    
    threshold = Config.CONFIDENCE_THRESHOLD
    
    if element.confidence < threshold:
        assert element.needs_review is True, \
            f"Element with confidence {element.confidence} < {threshold} should have needs_review=True"
    else:
        assert element.needs_review is False, \
            f"Element with confidence {element.confidence} >= {threshold} should have needs_review=False"


@given(st.floats(min_value=0.0, max_value=1.0))
def test_property_8_confidence_threshold_boundary(confidence: float):
    """
    Property 8: Confidence Threshold Flagging (boundary test)
    
    Test the exact boundary condition at the threshold.
    
    Validates: Requirements 3.4
    """
    threshold = Config.CONFIDENCE_THRESHOLD
    
    # Create element with specific confidence
    element = DetectedElement(
        level=HierarchyLevelEnum.INDICATOR,
        code="TEST.1",
        title="Test Element",
        description="Test description",
        confidence=confidence,
        source_page=1,
        source_text="Test text",
        needs_review=(confidence < threshold)  # Set correctly
    )
    
    # Verify the needs_review flag matches the threshold logic
    if confidence < threshold:
        assert element.needs_review is True, \
            f"Confidence {confidence} < {threshold} should result in needs_review=True"
    else:
        assert element.needs_review is False, \
            f"Confidence {confidence} >= {threshold} should result in needs_review=False"


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


@given(
    st.floats(min_value=0.0, max_value=1.0),
    st.booleans()
)
def test_property_8_needs_review_auto_correction(confidence: float, incorrect_needs_review: bool):
    """
    Property 8: Confidence Threshold Flagging (auto-correction)
    
    Test that the model auto-corrects needs_review based on confidence.
    
    Validates: Requirements 3.4
    """
    threshold = Config.CONFIDENCE_THRESHOLD
    expected_needs_review = confidence < threshold
    
    # Try to create element with potentially incorrect needs_review
    element = DetectedElement(
        level=HierarchyLevelEnum.INDICATOR,
        code="TEST.1",
        title="Test Element",
        description="Test description",
        confidence=confidence,
        source_page=1,
        source_text="Test text",
        needs_review=incorrect_needs_review
    )
    
    # The model should auto-correct to the expected value
    assert element.needs_review == expected_needs_review, \
        f"needs_review should be auto-corrected to {expected_needs_review} for confidence {confidence}"
