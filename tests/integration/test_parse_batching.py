"""Unit tests for parse batching (prepare_parse_batches).

Feature: long-running-pipeline-support
"""

import json
import pytest
from moto import mock_aws
import boto3

from els_pipeline.parse_batching import prepare_parse_batches
from els_pipeline.config import Config


def _make_element(
    level="indicator", code="IND.1", title="Test Indicator",
    confidence=0.95, page=1, needs_review=False,
):
    """Helper to create a minimal DetectedElement dict."""
    return {
        "level": level,
        "code": code,
        "title": title,
        "description": "A test element",
        "confidence": confidence,
        "source_page": page,
        "source_text": "sample source text",
        "needs_review": needs_review,
    }


def _base_event(output_artifact="US/CA/2021/intermediate/detection/run-1.json"):
    return {
        "output_artifact": output_artifact,
        "country": "US",
        "state": "CA",
        "version_year": 2021,
        "age_band": "3-5",
        "run_id": "run-1",
    }


@pytest.fixture
def s3_setup():
    """Set up mocked S3 bucket."""
    with mock_aws():
        s3 = boto3.client("s3", region_name=Config.AWS_REGION)
        s3.create_bucket(Bucket=Config.S3_PROCESSED_BUCKET)
        yield s3


def test_prepare_zero_elements(s3_setup):
    """Empty detection output produces at least one batch."""
    s3 = s3_setup
    event = _base_event()
    detection = {"elements": [], "review_count": 0}
    s3.put_object(
        Bucket=Config.S3_PROCESSED_BUCKET,
        Key=event["output_artifact"],
        Body=json.dumps(detection),
    )

    result = prepare_parse_batches(event, None)

    assert result["status"] == "success"
    assert result["batch_count"] == 1
    assert len(result["batch_keys"]) == 1


def test_prepare_single_domain(s3_setup):
    """One domain with a few elements produces exactly one batch."""
    s3 = s3_setup
    event = _base_event()
    elements = [
        _make_element(level="domain", code="D1", title="Domain 1"),
        _make_element(level="strand", code="S1", title="Strand 1"),
        _make_element(level="indicator", code="I1", title="Indicator 1"),
    ]
    detection = {"elements": elements, "review_count": 0}
    s3.put_object(
        Bucket=Config.S3_PROCESSED_BUCKET,
        Key=event["output_artifact"],
        Body=json.dumps(detection),
    )

    result = prepare_parse_batches(event, None)

    assert result["status"] == "success"
    assert result["batch_count"] == 1
    # Verify manifest was saved
    manifest = json.loads(
        s3.get_object(
            Bucket=Config.S3_PROCESSED_BUCKET, Key=result["manifest_key"]
        )["Body"].read()
    )
    assert manifest["total_elements"] == 3
    assert manifest["total_domains"] == 1


def test_prepare_multiple_domains_within_limit(s3_setup):
    """Domains within MAX_DOMAINS_PER_BATCH produce one batch."""
    s3 = s3_setup
    event = _base_event()
    elements = []
    for i in range(Config.MAX_DOMAINS_PER_BATCH):
        elements.append(
            _make_element(level="domain", code=f"D{i}", title=f"Domain {i}")
        )
        elements.append(
            _make_element(level="indicator", code=f"I{i}", title=f"Ind {i}")
        )
    detection = {"elements": elements, "review_count": 0}
    s3.put_object(
        Bucket=Config.S3_PROCESSED_BUCKET,
        Key=event["output_artifact"],
        Body=json.dumps(detection),
    )

    result = prepare_parse_batches(event, None)

    assert result["status"] == "success"
    assert result["batch_count"] == 1


def test_prepare_exceeding_max_domains(s3_setup):
    """More domains than MAX_DOMAINS_PER_BATCH produces multiple batches."""
    s3 = s3_setup
    event = _base_event()
    num_domains = Config.MAX_DOMAINS_PER_BATCH + 2
    elements = []
    for i in range(num_domains):
        elements.append(
            _make_element(level="domain", code=f"D{i}", title=f"Domain {i}")
        )
        elements.append(
            _make_element(level="indicator", code=f"I{i}", title=f"Ind {i}")
        )
    detection = {"elements": elements, "review_count": 0}
    s3.put_object(
        Bucket=Config.S3_PROCESSED_BUCKET,
        Key=event["output_artifact"],
        Body=json.dumps(detection),
    )

    result = prepare_parse_batches(event, None)

    assert result["status"] == "success"
    assert result["batch_count"] >= 2
    assert len(result["batch_keys"]) == result["batch_count"]


def test_prepare_filters_needs_review(s3_setup):
    """Elements with needs_review=True are filtered out."""
    s3 = s3_setup
    event = _base_event()
    elements = [
        _make_element(level="domain", code="D1", title="Domain 1", confidence=0.95),
        _make_element(
            level="indicator", code="I1", title="Review Me",
            confidence=0.3, needs_review=True,
        ),
        _make_element(level="indicator", code="I2", title="Good One", confidence=0.9),
    ]
    detection = {"elements": elements, "review_count": 1}
    s3.put_object(
        Bucket=Config.S3_PROCESSED_BUCKET,
        Key=event["output_artifact"],
        Body=json.dumps(detection),
    )

    result = prepare_parse_batches(event, None)

    assert result["status"] == "success"
    manifest = json.loads(
        s3.get_object(
            Bucket=Config.S3_PROCESSED_BUCKET, Key=result["manifest_key"]
        )["Body"].read()
    )
    # The review element should be filtered out
    assert manifest["total_elements"] == 2


def test_prepare_s3_load_failure(s3_setup):
    """S3 load failure returns error status."""
    event = _base_event(output_artifact="nonexistent/key.json")

    result = prepare_parse_batches(event, None)

    assert result["status"] == "error"
    assert "error" in result
    assert result["run_id"] == "run-1"


def test_prepare_passthrough_fields(s3_setup):
    """Country, state, version_year, age_band, run_id are passed through."""
    s3 = s3_setup
    event = _base_event()
    detection = {"elements": [], "review_count": 0}
    s3.put_object(
        Bucket=Config.S3_PROCESSED_BUCKET,
        Key=event["output_artifact"],
        Body=json.dumps(detection),
    )

    result = prepare_parse_batches(event, None)

    assert result["country"] == "US"
    assert result["state"] == "CA"
    assert result["version_year"] == 2021
    assert result["age_band"] == "3-5"
    assert result["run_id"] == "run-1"


# ---------------------------------------------------------------------------
# Tests for parse_batch (parse batch processor)
# Requirements: 5.3, 5.4, 5.5
# ---------------------------------------------------------------------------

from unittest.mock import patch
from els_pipeline.parse_batching import parse_batch
from els_pipeline.parser import MAX_PARSE_RETRIES
from els_pipeline.models import NormalizedStandard, HierarchyLevel


def _batch_event(batch_key="US/CA/2021/intermediate/parsing/batch-0/run-1.json"):
    return {
        "batch_key": batch_key,
        "batch_index": 0,
        "country": "US",
        "state": "CA",
        "version_year": 2021,
        "age_band": "3-5",
        "run_id": "run-1",
    }


def _put_parse_batch(s3, key, elements):
    """Upload a parse batch payload to mocked S3."""
    s3.put_object(
        Bucket=Config.S3_PROCESSED_BUCKET,
        Key=key,
        Body=json.dumps({"elements": elements}),
    )


def _mock_standard():
    """Return a NormalizedStandard instance for mocking parse_llm_response."""
    return NormalizedStandard(
        standard_id="US-CA-2021-D1-I1",
        country="US",
        state="CA",
        version_year=2021,
        domain=HierarchyLevel(code="D1", name="Domain 1"),
        indicator=HierarchyLevel(code="I1", name="Indicator 1"),
        age_band="3-5",
        source_page=1,
        source_text="sample text",
    )


@patch("els_pipeline.parse_batching.parse_llm_response")
@patch("els_pipeline.parse_batching.call_bedrock_llm")
@patch("els_pipeline.parse_batching.build_parsing_prompt")
def test_parse_batch_success(mock_prompt, mock_llm, mock_parse, s3_setup):
    """Successful processing: all domain chunks succeed → status 'success'."""
    s3 = s3_setup
    event = _batch_event()
    elements = [
        _make_element(level="domain", code="D1", title="Domain 1"),
        _make_element(level="indicator", code="I1", title="Indicator 1"),
    ]
    _put_parse_batch(s3, event["batch_key"], elements)

    std = _mock_standard()
    mock_prompt.return_value = "prompt"
    mock_llm.return_value = '[{"domain_code":"D1"}]'
    mock_parse.return_value = [std]

    result = parse_batch(event, None)

    assert result["status"] == "success"
    assert result["batch_index"] == 0
    assert result["standards_count"] >= 1
    assert "result_key" in result

    # Verify result was saved to S3
    saved = json.loads(
        s3.get_object(
            Bucket=Config.S3_PROCESSED_BUCKET, Key=result["result_key"]
        )["Body"].read()
    )
    assert saved["status"] == "success"
    assert len(saved["errors"]) == 0


@patch("els_pipeline.parse_batching.parse_llm_response")
@patch("els_pipeline.parse_batching.call_bedrock_llm")
@patch("els_pipeline.parse_batching.build_parsing_prompt")
def test_parse_batch_partial_failure(mock_prompt, mock_llm, mock_parse, s3_setup):
    """Some domain chunks fail, others succeed → status 'partial'."""
    s3 = s3_setup
    event = _batch_event()
    # Create elements across two domains so chunk_elements_by_domain produces 2 chunks
    elements = [
        _make_element(level="domain", code="D1", title="Domain 1"),
        _make_element(level="indicator", code="I1", title="Ind 1"),
        _make_element(level="domain", code="D2", title="Domain 2"),
        _make_element(level="indicator", code="I2", title="Ind 2"),
    ]
    _put_parse_batch(s3, event["batch_key"], elements)

    std = _mock_standard()
    mock_prompt.return_value = "prompt"
    mock_llm.return_value = '[{"domain_code":"D1"}]'

    call_count = 0

    def side_effect(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        # Fail all retry attempts for the first domain chunk,
        # succeed for the second
        if call_count <= MAX_PARSE_RETRIES + 1:
            raise ValueError("Bad JSON")
        return [std]

    mock_parse.side_effect = side_effect

    result = parse_batch(event, None)

    assert result["status"] == "partial"
    assert result["standards_count"] >= 1

    saved = json.loads(
        s3.get_object(
            Bucket=Config.S3_PROCESSED_BUCKET, Key=result["result_key"]
        )["Body"].read()
    )
    assert saved["status"] == "partial"
    assert len(saved["errors"]) >= 1
    assert len(saved["standards"]) >= 1


@patch("els_pipeline.parse_batching.parse_llm_response")
@patch("els_pipeline.parse_batching.call_bedrock_llm")
@patch("els_pipeline.parse_batching.build_parsing_prompt")
def test_parse_batch_all_fail(mock_prompt, mock_llm, mock_parse, s3_setup):
    """All domain chunks fail → status 'error', empty standards."""
    s3 = s3_setup
    event = _batch_event()
    elements = [
        _make_element(level="domain", code="D1", title="Domain 1"),
        _make_element(level="indicator", code="I1", title="Ind 1"),
    ]
    _put_parse_batch(s3, event["batch_key"], elements)

    mock_prompt.return_value = "prompt"
    mock_llm.return_value = "not json"
    mock_parse.side_effect = ValueError("Invalid JSON response")

    result = parse_batch(event, None)

    assert result["status"] == "error"
    assert result["standards_count"] == 0

    saved = json.loads(
        s3.get_object(
            Bucket=Config.S3_PROCESSED_BUCKET, Key=result["result_key"]
        )["Body"].read()
    )
    assert saved["status"] == "error"
    assert len(saved["standards"]) == 0
    assert len(saved["errors"]) >= 1
