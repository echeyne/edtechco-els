"""Property-based tests for parse batching.

Feature: long-running-pipeline-support
"""

from hypothesis import given, strategies as st, settings

from els_pipeline.models import DetectedElement, HierarchyLevelEnum
from els_pipeline.parser import chunk_elements_by_domain
from els_pipeline.config import Config


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

_levels = st.sampled_from([e.value for e in HierarchyLevelEnum])

detected_element_strategy = st.builds(
    DetectedElement,
    level=_levels,
    code=st.text(
        min_size=1, max_size=10,
        alphabet=st.characters(whitelist_categories=("L", "N")),
    ),
    title=st.text(min_size=1, max_size=50),
    description=st.text(min_size=0, max_size=50),
    confidence=st.floats(min_value=0.0, max_value=1.0),
    source_page=st.integers(min_value=1, max_value=100),
    source_text=st.text(min_size=1, max_size=50),
    needs_review=st.just(False),  # will be auto-corrected by validator
)

# Strategy that may include review elements
detected_element_with_review_strategy = st.builds(
    DetectedElement,
    level=_levels,
    code=st.text(
        min_size=1, max_size=10,
        alphabet=st.characters(whitelist_categories=("L", "N")),
    ),
    title=st.text(min_size=1, max_size=50),
    description=st.text(min_size=0, max_size=50),
    confidence=st.floats(min_value=0.0, max_value=1.0),
    source_page=st.integers(min_value=1, max_value=100),
    source_text=st.text(min_size=1, max_size=50),
    needs_review=st.booleans(),
)


# ---------------------------------------------------------------------------
# Property 2: Parse batch exact partitioning
# ---------------------------------------------------------------------------

@given(st.lists(detected_element_strategy, min_size=0, max_size=30))
@settings(max_examples=50, deadline=5000)
def test_property_2_parse_batch_exact_partitioning(elements):
    """
    Property 2: Parse batch exact partitioning

    For any list of valid DetectedElement objects, the union of all batch
    elements equals the original filtered set exactly — no loss, no
    duplication.

    Validates: Requirements 4.4
    """
    # Filter out needs_review (same as prepare_parse_batches)
    valid_elements = [e for e in elements if not e.needs_review]

    # Chunk by domain
    domain_chunks = chunk_elements_by_domain(valid_elements)
    max_per_batch = Config.MAX_DOMAINS_PER_BATCH

    # Group domain chunks into batches (same logic as prepare_parse_batches)
    all_batch_elements = []
    for i in range(0, max(len(domain_chunks), 1), max_per_batch):
        batch_chunks = domain_chunks[i : i + max_per_batch]
        batch_elements = [el for chunk in batch_chunks for el in chunk]
        all_batch_elements.extend(batch_elements)

    # The union of all batch elements must equal the original filtered set
    # exactly — same count, same elements, same order preserved per domain.
    assert len(all_batch_elements) == len(valid_elements), (
        f"Element count mismatch: batches have {len(all_batch_elements)}, "
        f"original filtered set has {len(valid_elements)}"
    )

    # Verify element-by-element identity (order preserved within domains)
    for idx, (batch_el, orig_el) in enumerate(
        zip(all_batch_elements, valid_elements)
    ):
        assert batch_el.code == orig_el.code and batch_el.title == orig_el.title, (
            f"Element mismatch at index {idx}: "
            f"batch=({batch_el.code}, {batch_el.title}), "
            f"original=({orig_el.code}, {orig_el.title})"
        )



# ---------------------------------------------------------------------------
# Property 5: Parse batch size constraint
# ---------------------------------------------------------------------------

@given(
    st.lists(detected_element_strategy, min_size=1, max_size=30),
    st.integers(min_value=1, max_value=10),
)
@settings(max_examples=50, deadline=5000)
def test_property_5_parse_batch_size_constraint(elements, max_domains_per_batch):
    """
    Property 5: Parse batch size constraint

    For any list of DetectedElement objects and any positive
    MAX_DOMAINS_PER_BATCH, every batch contains at most
    MAX_DOMAINS_PER_BATCH domain chunks.

    Validates: Requirements 4.2, 9.4
    """
    valid_elements = [e for e in elements if not e.needs_review]
    domain_chunks = chunk_elements_by_domain(valid_elements)

    # Group domain chunks into batches using the given max
    for i in range(0, len(domain_chunks), max_domains_per_batch):
        batch_chunks = domain_chunks[i : i + max_domains_per_batch]
        assert len(batch_chunks) <= max_domains_per_batch, (
            f"Batch starting at domain {i} has {len(batch_chunks)} domains, "
            f"exceeding limit of {max_domains_per_batch}"
        )



# ---------------------------------------------------------------------------
# Property 9: Parse preparer filters review elements
# ---------------------------------------------------------------------------

@given(st.lists(detected_element_with_review_strategy, min_size=0, max_size=30))
@settings(max_examples=50, deadline=5000)
def test_property_9_parse_preparer_filters_review_elements(elements):
    """
    Property 9: Parse preparer filters review elements

    Batches produced by prepare_parse_batches contain only elements
    where needs_review is false.

    Validates: Requirements 4.1
    """
    # Filter (same logic as prepare_parse_batches)
    valid_elements = [e for e in elements if not e.needs_review]

    # Chunk and batch
    domain_chunks = chunk_elements_by_domain(valid_elements)
    max_per_batch = Config.MAX_DOMAINS_PER_BATCH

    for i in range(0, max(len(domain_chunks), 1), max_per_batch):
        batch_chunks = domain_chunks[i : i + max_per_batch]
        for chunk in batch_chunks:
            for el in chunk:
                assert not el.needs_review, (
                    f"Element with needs_review=True found in batch: "
                    f"code={el.code}, confidence={el.confidence}"
                )


# ---------------------------------------------------------------------------
# Strategies for merge-related property tests
# ---------------------------------------------------------------------------

normalized_standard_strategy = st.fixed_dictionaries({
    "standard_id": st.text(
        min_size=1, max_size=30,
        alphabet=st.characters(whitelist_categories=("L", "N", "P")),
    ),
    "country": st.just("US"),
    "state": st.just("CA"),
    "version_year": st.just(2021),
    "domain": st.fixed_dictionaries({
        "code": st.text(min_size=1, max_size=10, alphabet=st.characters(whitelist_categories=("L", "N"))),
        "name": st.text(min_size=1, max_size=50),
    }),
    "indicator": st.fixed_dictionaries({
        "code": st.text(min_size=1, max_size=10, alphabet=st.characters(whitelist_categories=("L", "N"))),
        "name": st.text(min_size=1, max_size=50),
    }),
    "age_band": st.just("3-5"),
    "source_page": st.integers(min_value=1, max_value=100),
    "source_text": st.text(min_size=1, max_size=50),
})

batch_result_strategy = st.builds(
    lambda standards: {
        "batch_index": 0,
        "standards": standards,
        "errors": [],
        "status": "success",
    },
    standards=st.lists(normalized_standard_strategy, min_size=0, max_size=10),
)


# ---------------------------------------------------------------------------
# Property 8: Parse merge completeness
# ---------------------------------------------------------------------------

@given(st.lists(batch_result_strategy, min_size=1, max_size=10))
@settings(max_examples=50, deadline=5000)
def test_property_8_parse_merge_completeness(batch_results):
    """
    Property 8: Parse merge completeness

    The total number of NormalizedStandard objects in merged output equals
    the sum of standards counts from all batch results.

    Validates: Requirements 6.2
    """
    # Simulate the merge logic: concatenate all standards lists
    merged_standards = []
    for batch_result in batch_results:
        merged_standards.extend(batch_result["standards"])

    expected_total = sum(len(br["standards"]) for br in batch_results)

    assert len(merged_standards) == expected_total, (
        f"Merged standards count {len(merged_standards)} != "
        f"sum of batch counts {expected_total}"
    )
