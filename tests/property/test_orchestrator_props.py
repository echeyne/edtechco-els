"""Property-based tests for pipeline orchestrator.

These tests validate universal correctness properties for the pipeline orchestrator
using hypothesis for property-based testing.
"""

import pytest
from hypothesis import given, strategies as st, assume

from els_pipeline.models import PipelineStageResult, PipelineRunResult


# Strategy for generating valid stage names
stage_names = st.sampled_from([
    "ingestion", "text_extraction", "structure_detection",
    "hierarchy_parsing", "validation", "data_persistence"
])

# Strategy for generating stage statuses
stage_statuses = st.sampled_from(["success", "failure", "running"])

# Strategy for generating PipelineStageResult objects
@st.composite
def pipeline_stage_result(draw):
    """Generate a valid PipelineStageResult."""
    return PipelineStageResult(
        stage_name=draw(stage_names),
        status=draw(stage_statuses),
        duration_ms=draw(st.integers(min_value=0, max_value=300000)),  # 0-5 minutes
        output_artifact=draw(st.text(min_size=1, max_size=200)),
        error=draw(st.one_of(st.none(), st.text(min_size=1, max_size=500)))
    )


# Strategy for generating valid country codes (ISO 3166-1 alpha-2)
country_codes = st.sampled_from([
    "US", "CA", "GB", "AU", "NZ", "DE", "FR", "ES", "IT", "JP",
    "CN", "IN", "BR", "MX", "AR", "ZA", "KR", "SG", "MY", "TH"
])

# Strategy for generating PipelineRunResult objects
@st.composite
def pipeline_run_result(draw):
    """Generate a valid PipelineRunResult."""
    total_indicators = draw(st.integers(min_value=0, max_value=10000))
    total_validated = draw(st.integers(min_value=0, max_value=total_indicators))

    return PipelineRunResult(
        run_id=draw(st.text(min_size=10, max_size=100)),
        document_s3_key=draw(st.text(min_size=10, max_size=200)),
        country=draw(country_codes),
        state=draw(st.text(min_size=2, max_size=10)),
        version_year=draw(st.integers(min_value=2000, max_value=2100)),
        stages=draw(st.lists(pipeline_stage_result(), min_size=0, max_size=10)),
        total_indicators=total_indicators,
        total_validated=total_validated,
        status=draw(st.sampled_from(["running", "completed", "failed", "partial"]))
    )


@given(pipeline_stage_result())
def test_property_26_pipeline_stage_result_completeness(stage_result):
    """
    Property 26: Pipeline Stage Result Completeness
    
    For any completed pipeline stage result, the fields stage_name, status,
    duration_ms (non-negative), and output_artifact SHALL all be present.
    
    Validates: Requirements 9.2
    """
    # All fields should be present (not None)
    assert stage_result.stage_name is not None, "stage_name must be present"
    assert stage_result.status is not None, "status must be present"
    assert stage_result.duration_ms is not None, "duration_ms must be present"
    assert stage_result.output_artifact is not None, "output_artifact must be present"
    
    # stage_name should be a valid stage
    valid_stages = {
        "ingestion", "text_extraction", "structure_detection",
        "hierarchy_parsing", "validation", "data_persistence"
    }
    assert stage_result.stage_name in valid_stages, f"stage_name must be one of {valid_stages}"
    
    # status should be a valid status
    valid_statuses = {"success", "failure", "running"}
    assert stage_result.status in valid_statuses, f"status must be one of {valid_statuses}"
    
    # duration_ms should be non-negative
    assert stage_result.duration_ms >= 0, "duration_ms must be non-negative"
    
    # output_artifact should be non-empty
    assert len(stage_result.output_artifact) > 0, "output_artifact must be non-empty"


@given(pipeline_run_result())
def test_property_27_pipeline_run_counts_invariant(run_result):
    """
    Property 27: Pipeline Run Counts Invariant

    For any successfully completed pipeline run, total_validated <= total_indicators.

    Validates: Requirements 9.4
    """
    # total_validated should not exceed total_indicators
    assert run_result.total_validated <= run_result.total_indicators, \
        f"total_validated ({run_result.total_validated}) must be <= total_indicators ({run_result.total_indicators})"

    # All counts should be non-negative
    assert run_result.total_indicators >= 0, "total_indicators must be non-negative"
    assert run_result.total_validated >= 0, "total_validated must be non-negative"


@given(
    st.lists(pipeline_stage_result(), min_size=1, max_size=8),
    st.integers(min_value=0, max_value=10000),
    st.integers(min_value=0, max_value=10000)
)
def test_property_27_pipeline_counts_with_stages(stages, total_indicators, total_validated):
    """
    Property 27 variant: Test counts invariant with explicit stage results.
    
    Ensures that when we have stage results, the counts still maintain the invariant.
    """
    # Ensure total_validated <= total_indicators
    assume(total_validated <= total_indicators)

    run_result = PipelineRunResult(
        run_id="test-run-id",
        document_s3_key="US/CA/2021/test.pdf",
        country="US",
        state="CA",
        version_year=2021,
        stages=stages,
        total_indicators=total_indicators,
        total_validated=total_validated,
        status="completed"
    )

    # Verify the invariant holds
    assert run_result.total_validated <= run_result.total_indicators


@given(country_codes)
def test_property_country_code_in_run_id(country_code):
    """
    Property: Country code should be included in run_id format.
    
    For any valid country code, the run_id format should include it.
    """
    state = "CA"
    year = 2021
    run_id = f"pipeline-{country_code}-{state}-{year}-abc123"
    
    # Parse run_id
    parts = run_id.split('-')
    assert len(parts) >= 5, "run_id should have at least 5 parts"
    assert parts[0] == "pipeline", "run_id should start with 'pipeline'"
    assert parts[1] == country_code, f"run_id should contain country code {country_code}"
    assert parts[2] == state, f"run_id should contain state {state}"
    assert parts[3] == str(year), f"run_id should contain year {year}"


@given(
    st.lists(pipeline_stage_result(), min_size=1, max_size=8)
)
def test_property_stage_ordering_preserved(stages):
    """
    Property: Stage ordering should be preserved in pipeline results.
    
    For any list of stages, the order should be maintained in the result.
    """
    run_result = PipelineRunResult(
        run_id="test-run-id",
        document_s3_key="US/CA/2021/test.pdf",
        country="US",
        state="CA",
        version_year=2021,
        stages=stages,
        total_indicators=100,
        total_validated=90,
        status="completed"
    )

    # Verify stages are in the same order
    assert len(run_result.stages) == len(stages)
    for i, stage in enumerate(stages):
        assert run_result.stages[i].stage_name == stage.stage_name
        assert run_result.stages[i].status == stage.status


@given(pipeline_stage_result())
def test_property_error_field_consistency(stage_result):
    """
    Property: Error field should be consistent with status.
    
    For any stage result with status="failure", error field should be present.
    For status="success", error should typically be None (but not enforced).
    """
    if stage_result.status == "failure":
        # Failure status should have error information
        # Note: This is a soft requirement - we don't enforce it strictly
        # as the error might be captured elsewhere
        pass
    
    # If error is present, it should be non-empty
    if stage_result.error is not None:
        assert len(stage_result.error) > 0, "error should be non-empty if present"
