"""Unit tests for detect_batch (detection batch processor).

Feature: long-running-pipeline-support
Requirements: 2.3, 2.4, 2.5
"""

import json
import pytest
from unittest.mock import patch, MagicMock
from moto import mock_aws
import boto3

from els_pipeline.detection_batching import detect_batch
from els_pipeline.config import Config
from els_pipeline.detector import MAX_PARSE_RETRIES
from els_pipeline.models import DetectedElement


def _make_block(text="Sample text for detection", page=1):
    """Helper to create a minimal TextBlock dict."""
    return {
        "text": text,
        "page_number": page,
        "block_type": "LINE",
        "confidence": 0.95,
        "geometry": {"BoundingBox": {"Top": 0.1, "Left": 0.1}},
    }


def _batch_event(batch_key="US/CA/2021/intermediate/detection/batch-0/run-1.json"):
    return {
        "batch_key": batch_key,
        "batch_index": 0,
        "country": "US",
        "state": "CA",
        "version_year": 2021,
        "run_id": "run-1",
    }


def _mock_detected_element():
    """Return a DetectedElement instance for mocking parse_llm_response."""
    return DetectedElement(
        level="indicator",
        code="ELA.1.1",
        title="Reading Comprehension",
        description="Student reads grade-level text",
        confidence=0.9,
        source_page=1,
        source_text="Sample text for detection",
        needs_review=False,
    )


@pytest.fixture
def s3_setup():
    """Set up mocked S3 bucket."""
    with mock_aws():
        s3 = boto3.client("s3", region_name=Config.AWS_REGION)
        s3.create_bucket(Bucket=Config.S3_PROCESSED_BUCKET)
        yield s3


def _put_batch(s3, key, blocks):
    """Upload a batch payload to mocked S3."""
    s3.put_object(
        Bucket=Config.S3_PROCESSED_BUCKET,
        Key=key,
        Body=json.dumps({"blocks": blocks}),
    )


@patch("els_pipeline.detection_batching.parse_llm_response")
@patch("els_pipeline.detection_batching.call_bedrock_llm")
@patch("els_pipeline.detection_batching.build_detection_prompt")
def test_detect_batch_success(mock_prompt, mock_llm, mock_parse, s3_setup):
    """Successful processing: all chunks succeed → status 'success'."""
    s3 = s3_setup
    event = _batch_event()
    blocks = [_make_block(page=i + 1) for i in range(3)]
    _put_batch(s3, event["batch_key"], blocks)

    elem = _mock_detected_element()
    mock_prompt.return_value = "prompt"
    mock_llm.return_value = '{"elements": []}'
    mock_parse.return_value = [elem]

    result = detect_batch(event, None)

    assert result["status"] == "success"
    assert result["batch_index"] == 0
    assert result["elements_count"] >= 1
    assert "result_key" in result

    # Verify result was saved to S3
    saved = json.loads(
        s3.get_object(
            Bucket=Config.S3_PROCESSED_BUCKET, Key=result["result_key"]
        )["Body"].read()
    )
    assert saved["status"] == "success"
    assert len(saved["errors"]) == 0


@patch("els_pipeline.detection_batching.parse_llm_response")
@patch("els_pipeline.detection_batching.call_bedrock_llm")
@patch("els_pipeline.detection_batching.build_detection_prompt")
def test_detect_batch_partial_failure(mock_prompt, mock_llm, mock_parse, s3_setup):
    """Some chunks fail, others succeed → status 'partial'."""
    s3 = s3_setup
    event = _batch_event()
    # Create blocks large enough to produce multiple chunks
    big_text = "x" * 8000
    blocks = [_make_block(text=big_text, page=i + 1) for i in range(3)]
    _put_batch(s3, event["batch_key"], blocks)

    elem = _mock_detected_element()
    mock_prompt.return_value = "prompt"
    mock_llm.return_value = '{"elements": []}'

    call_count = 0

    def side_effect(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        # Fail on every call for the first chunk (all retry attempts),
        # succeed for subsequent chunks
        if call_count <= MAX_PARSE_RETRIES + 1:
            raise ValueError("Bad JSON")
        return [elem]

    mock_parse.side_effect = side_effect

    result = detect_batch(event, None)

    assert result["status"] == "partial"
    assert result["elements_count"] >= 1

    saved = json.loads(
        s3.get_object(
            Bucket=Config.S3_PROCESSED_BUCKET, Key=result["result_key"]
        )["Body"].read()
    )
    assert saved["status"] == "partial"
    assert len(saved["errors"]) >= 1
    assert len(saved["elements"]) >= 1


@patch("els_pipeline.detection_batching.parse_llm_response")
@patch("els_pipeline.detection_batching.call_bedrock_llm")
@patch("els_pipeline.detection_batching.build_detection_prompt")
def test_detect_batch_all_fail(mock_prompt, mock_llm, mock_parse, s3_setup):
    """All chunks fail → status 'error', empty elements."""
    s3 = s3_setup
    event = _batch_event()
    blocks = [_make_block(page=i + 1) for i in range(2)]
    _put_batch(s3, event["batch_key"], blocks)

    mock_prompt.return_value = "prompt"
    mock_llm.return_value = "not json"
    mock_parse.side_effect = ValueError("Invalid JSON response")

    result = detect_batch(event, None)

    assert result["status"] == "error"
    assert result["elements_count"] == 0

    saved = json.loads(
        s3.get_object(
            Bucket=Config.S3_PROCESSED_BUCKET, Key=result["result_key"]
        )["Body"].read()
    )
    assert saved["status"] == "error"
    assert len(saved["elements"]) == 0
    assert len(saved["errors"]) >= 1


@patch("els_pipeline.detection_batching.parse_llm_response")
@patch("els_pipeline.detection_batching.call_bedrock_llm")
@patch("els_pipeline.detection_batching.build_detection_prompt")
def test_detect_batch_retry_then_succeed(mock_prompt, mock_llm, mock_parse, s3_setup):
    """Chunk fails on first attempt but succeeds on retry → status 'success'."""
    s3 = s3_setup
    event = _batch_event()
    blocks = [_make_block()]
    _put_batch(s3, event["batch_key"], blocks)

    elem = _mock_detected_element()
    mock_prompt.return_value = "prompt"
    mock_llm.return_value = '{"elements": []}'

    attempt = 0

    def side_effect(*args, **kwargs):
        nonlocal attempt
        attempt += 1
        if attempt == 1:
            raise json.JSONDecodeError("bad", "", 0)
        return [elem]

    mock_parse.side_effect = side_effect

    result = detect_batch(event, None)

    assert result["status"] == "success"
    assert result["elements_count"] == 1
    assert attempt == 2  # first failed, second succeeded
