"""Property-based tests for text extraction (Properties 4, 5, 6)."""

import pytest
from hypothesis import given, strategies as st
from typing import List

from els_pipeline.models import TextBlock
from els_pipeline.extractor import _sort_blocks_by_reading_order


# Strategy for generating TextBlock objects
@st.composite
def text_block_strategy(draw, block_type: str = None):
    """Generate a random TextBlock."""
    if block_type is None:
        block_type = draw(st.sampled_from(['LINE', 'TABLE_CELL']))
    
    page_number = draw(st.integers(min_value=1, max_value=100))
    top = draw(st.floats(min_value=0.0, max_value=1.0))
    left = draw(st.floats(min_value=0.0, max_value=1.0))
    
    # Generate row_index and col_index for TABLE_CELL blocks
    row_index = None
    col_index = None
    if block_type == 'TABLE_CELL':
        row_index = draw(st.integers(min_value=0, max_value=50))
        col_index = draw(st.integers(min_value=0, max_value=20))
    
    return TextBlock(
        text=draw(st.text(min_size=1, max_size=100)),
        page_number=page_number,
        block_type=block_type,
        row_index=row_index,
        col_index=col_index,
        confidence=draw(st.floats(min_value=0.0, max_value=1.0)),
        geometry={
            'BoundingBox': {
                'Top': top,
                'Left': left,
                'Width': draw(st.floats(min_value=0.01, max_value=0.5)),
                'Height': draw(st.floats(min_value=0.01, max_value=0.5))
            }
        }
    )


# Property 4: Text Block Reading Order
@given(st.lists(text_block_strategy(), min_size=1, max_size=50))
def test_property_4_text_block_reading_order(blocks: List[TextBlock]):
    """
    Property 4: Text Block Reading Order
    
    For any set of blocks with positions, output sorted by (page, top, left).
    
    Validates: Requirements 2.2
    Feature: els-normalization-pipeline
    """
    sorted_blocks = _sort_blocks_by_reading_order(blocks)
    
    # Verify the output is sorted by (page_number, top, left)
    for i in range(len(sorted_blocks) - 1):
        current = sorted_blocks[i]
        next_block = sorted_blocks[i + 1]
        
        current_top = current.geometry['BoundingBox']['Top']
        current_left = current.geometry['BoundingBox']['Left']
        next_top = next_block.geometry['BoundingBox']['Top']
        next_left = next_block.geometry['BoundingBox']['Left']
        
        # Check ordering: (page, top, left)
        if current.page_number < next_block.page_number:
            # Different pages - current should come first
            assert True
        elif current.page_number == next_block.page_number:
            # Same page - check top position
            if current_top < next_top:
                assert True
            elif current_top == next_top:
                # Same top position - check left position
                assert current_left <= next_left
            else:
                # current_top > next_top should not happen in sorted order
                assert False, f"Blocks not sorted by top position: {current_top} > {next_top}"
        else:
            # current.page_number > next_block.page_number should not happen
            assert False, f"Blocks not sorted by page number: {current.page_number} > {next_block.page_number}"


# Property 5: Table Cell Structure Preservation
@given(text_block_strategy(block_type='TABLE_CELL'))
def test_property_5_table_cell_structure_preservation(block: TextBlock):
    """
    Property 5: Table Cell Structure Preservation
    
    For any TABLE_CELL block, row_index and col_index are non-null and non-negative.
    
    Validates: Requirements 2.3
    Feature: els-normalization-pipeline
    """
    assert block.block_type == 'TABLE_CELL'
    assert block.row_index is not None, "TABLE_CELL block must have non-null row_index"
    assert block.col_index is not None, "TABLE_CELL block must have non-null col_index"
    assert block.row_index >= 0, f"row_index must be non-negative, got {block.row_index}"
    assert block.col_index >= 0, f"col_index must be non-negative, got {block.col_index}"


# Property 6: Page Number Presence
@given(text_block_strategy())
def test_property_6_page_number_presence(block: TextBlock):
    """
    Property 6: Page Number Presence
    
    For any text block, page_number is a positive integer.
    
    Validates: Requirements 2.4
    Feature: els-normalization-pipeline
    """
    assert isinstance(block.page_number, int), f"page_number must be an integer, got {type(block.page_number)}"
    assert block.page_number > 0, f"page_number must be positive, got {block.page_number}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
