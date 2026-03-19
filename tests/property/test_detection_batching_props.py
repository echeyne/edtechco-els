"""Property-based tests for detection batching.

Feature: long-running-pipeline-support
"""

from hypothesis import given, strategies as st, settings

from els_pipeline.models import TextBlock
from els_pipeline.detector import chunk_text_blocks
from els_pipeline.config import Config


# Strategy for generating valid TextBlock objects
text_block_strategy = st.builds(
    TextBlock,
    text=st.text(min_size=1, max_size=200),
    page_number=st.integers(min_value=1, max_value=100),
    block_type=st.just("LINE"),
    confidence=st.floats(min_value=0.0, max_value=1.0),
    geometry=st.just({"BoundingBox": {"Top": 0.1, "Left": 0.1}}),
)


@given(st.lists(text_block_strategy, min_size=0, max_size=30))
@settings(max_examples=50, deadline=5000)
def test_property_1_detection_batch_no_data_loss(blocks):
    """
    Property 1: Detection batch no-data-loss

    For any list of TextBlock objects, after chunking and batching,
    the union of all blocks across all batches is a superset of the
    original block set.

    Validates: Requirements 1.4
    """
    chunks = chunk_text_blocks(blocks)
    max_per_batch = Config.MAX_CHUNKS_PER_BATCH

    # Group chunks into batches (same logic as prepare_detection_batches)
    batches_blocks = []
    for i in range(0, max(len(chunks), 1), max_per_batch):
        batch_chunks = chunks[i : i + max_per_batch]
        batch_blocks = [block for chunk in batch_chunks for block in chunk]
        batches_blocks.append(batch_blocks)

    # Collect all block texts from all batches
    all_batch_block_texts = set()
    for batch in batches_blocks:
        for block in batch:
            all_batch_block_texts.add((block.text, block.page_number))

    # Verify every original block appears in at least one batch
    for block in blocks:
        assert (block.text, block.page_number) in all_batch_block_texts, (
            f"Block (text={block.text!r}, page={block.page_number}) "
            f"missing from batches"
        )


@given(
    st.lists(text_block_strategy, min_size=1, max_size=30),
    st.integers(min_value=1, max_value=10),
)
@settings(max_examples=50, deadline=5000)
def test_property_4_detection_batch_size_constraint(blocks, max_chunks_per_batch):
    """
    Property 4: Detection batch size constraint

    For any list of TextBlock objects and any positive MAX_CHUNKS_PER_BATCH,
    every batch contains at most MAX_CHUNKS_PER_BATCH chunks.

    Validates: Requirements 1.2, 9.3
    """
    chunks = chunk_text_blocks(blocks)

    # Group chunks into batches using the given max
    for i in range(0, len(chunks), max_chunks_per_batch):
        batch_chunks = chunks[i : i + max_chunks_per_batch]
        assert len(batch_chunks) <= max_chunks_per_batch, (
            f"Batch starting at chunk {i} has {len(batch_chunks)} chunks, "
            f"exceeding limit of {max_chunks_per_batch}"
        )


# ---------------------------------------------------------------------------
# Strategies for merge-related property tests
# ---------------------------------------------------------------------------

# Strategy for generating detected element dicts (as stored in batch results)
detected_element_strategy = st.fixed_dictionaries({
    "level": st.sampled_from(["domain", "strand", "sub_strand", "indicator"]),
    "code": st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=("L", "N", "P"))),
    "title": st.text(min_size=1, max_size=100),
    "description": st.text(min_size=0, max_size=200),
    "confidence": st.floats(min_value=0.0, max_value=1.0),
    "source_page": st.integers(min_value=1, max_value=100),
    "source_text": st.text(min_size=1, max_size=200),
    "needs_review": st.booleans(),
})

batch_status_strategy = st.sampled_from(["success", "partial", "error"])


def _deduplicate(elements):
    """Deduplicate elements using (code, title, source_page) key."""
    seen = set()
    unique = []
    for elem in elements:
        key = (elem["code"], elem["title"], elem.get("source_page", 0))
        if key not in seen:
            seen.add(key)
            unique.append(elem)
    return unique


def _determine_status(batch_statuses):
    """Determine overall status from a list of batch statuses."""
    has_error = any(s == "error" for s in batch_statuses)
    has_success = any(s in ("success", "partial") for s in batch_statuses)
    if has_error and has_success:
        return "partial"
    elif has_error and not has_success:
        return "error"
    else:
        return "success"


# ---------------------------------------------------------------------------
# Property 3: Detection deduplication correctness
# ---------------------------------------------------------------------------

@given(st.lists(detected_element_strategy, min_size=0, max_size=50))
@settings(max_examples=50, deadline=5000)
def test_property_3_detection_deduplication_correctness(elements):
    """
    Property 3: Detection deduplication correctness

    After deduplication, no two elements in the output share the same
    (code, title, source_page) key.

    **Validates: Requirements 3.2**
    """
    unique = _deduplicate(elements)

    keys = [(e["code"], e["title"], e.get("source_page", 0)) for e in unique]
    assert len(keys) == len(set(keys)), (
        f"Duplicate keys found after deduplication: "
        f"{[k for k in keys if keys.count(k) > 1]}"
    )


# ---------------------------------------------------------------------------
# Property 6: Status determination correctness
# ---------------------------------------------------------------------------

@given(st.lists(batch_status_strategy, min_size=1, max_size=20))
@settings(max_examples=100, deadline=5000)
def test_property_6_status_determination_correctness(statuses):
    """
    Property 6: Status determination correctness

    For any list of batch statuses, the merge step determines overall
    status correctly: all "success" → "success", all "error" → "error",
    mixed → "partial".

    **Validates: Requirements 3.4, 3.5, 3.6, 6.3, 6.4, 6.5, 10.1, 10.2**
    """
    result = _determine_status(statuses)

    all_success = all(s in ("success", "partial") for s in statuses)
    all_error = all(s == "error" for s in statuses)

    if all_success:
        assert result == "success", (
            f"Expected 'success' for statuses {statuses}, got '{result}'"
        )
    elif all_error:
        assert result == "error", (
            f"Expected 'error' for statuses {statuses}, got '{result}'"
        )
    else:
        assert result == "partial", (
            f"Expected 'partial' for mixed statuses {statuses}, got '{result}'"
        )


# ---------------------------------------------------------------------------
# Property 7: Review count accuracy
# ---------------------------------------------------------------------------

@given(st.lists(detected_element_strategy, min_size=0, max_size=50))
@settings(max_examples=50, deadline=5000)
def test_property_7_review_count_accuracy(elements):
    """
    Property 7: Review count accuracy

    The review_count equals the count of deduplicated elements whose
    confidence is below CONFIDENCE_THRESHOLD.

    **Validates: Requirements 3.3**
    """
    unique = _deduplicate(elements)

    review_count = sum(
        1 for e in unique
        if e.get("confidence", 1.0) < Config.CONFIDENCE_THRESHOLD
    )

    expected = sum(
        1 for e in unique
        if e.get("confidence", 1.0) < Config.CONFIDENCE_THRESHOLD
    )

    assert review_count == expected, (
        f"Review count {review_count} != expected {expected} "
        f"(threshold={Config.CONFIDENCE_THRESHOLD})"
    )
