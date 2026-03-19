"""Unit tests for merge_detection_results (detection results merger).

Feature: long-running-pipeline-support
Requirements: 3.2, 3.4, 3.5, 3.6, 8.1, 10.4
"""

import json
import pytest
from moto import mock_aws
import boto3

from els_pipeline.detection_batching import merge_detection_results
from els_pipeline.config import Config


def _make_element(code="ELA.1.1", title="Reading", source_page=1, confidence=0.9):
    """Helper to create a minimal detected element dict."""
    return {
        "level": "indicator",
        "code": code,
        "title": title,
        "description": "desc",
        "confidence": confidence,
        "source_page": source_page,
        "source_text": "sample",
        "needs_review": confidence < Config.CONFIDENCE_THRESHOLD,
    }


def _base_event(manifest_key="US/CA/2021/intermediate/detection/manifest/run-1.json"):
    return {
        "manifest_key": manifest_key,
        "country": "US",
        "state": "CA",
        "version_year": 2021,
        "run_id": "run-1",
        "extraction_key": "US/CA/2021/intermediate/extraction/run-1.json",
    }


def _make_manifest(batches):
    """Build a manifest dict from a list of (batch_index, batch_s3_key) tuples."""
    return {
        "run_id": "run-1",
        "total_blocks": 10,
        "total_chunks": len(batches),
        "batch_count": len(batches),
        "batches": [
            {
                "batch_index": idx,
                "batch_s3_key": key,
                "chunk_count": 1,
                "block_count": 5,
            }
            for idx, key in batches
        ],
        "created_at": "2024-01-01T00:00:00+00:00",
    }


def _make_batch_result(batch_index, elements, errors=None, status="success"):
    """Build a batch result dict."""
    return {
        "batch_index": batch_index,
        "elements": elements,
        "errors": errors or [],
        "status": status,
    }


def _put_json(s3, key, data):
    s3.put_object(
        Bucket=Config.S3_PROCESSED_BUCKET,
        Key=key,
        Body=json.dumps(data),
    )


@pytest.fixture
def s3_setup():
    """Set up mocked S3 bucket."""
    with mock_aws():
        s3 = boto3.client("s3", region_name=Config.AWS_REGION)
        s3.create_bucket(Bucket=Config.S3_PROCESSED_BUCKET)
        yield s3


def test_merge_overlapping_elements(s3_setup):
    """Overlapping elements across batches are deduplicated."""
    s3 = s3_setup
    event = _base_event()

    batch0_key = "US/CA/2021/intermediate/detection/batch-0/run-1.json"
    batch1_key = "US/CA/2021/intermediate/detection/batch-1/run-1.json"
    result0_key = batch0_key.replace("/batch-", "/result-")
    result1_key = batch1_key.replace("/batch-", "/result-")

    manifest = _make_manifest([(0, batch0_key), (1, batch1_key)])
    _put_json(s3, event["manifest_key"], manifest)

    # Both batches contain the same element (overlap)
    shared = _make_element(code="ELA.1.1", title="Reading", source_page=1)
    unique_b0 = _make_element(code="ELA.1.2", title="Writing", source_page=2)
    unique_b1 = _make_element(code="ELA.1.3", title="Listening", source_page=3)

    _put_json(s3, result0_key, _make_batch_result(0, [shared, unique_b0]))
    _put_json(s3, result1_key, _make_batch_result(1, [shared, unique_b1]))

    result = merge_detection_results(event, None)

    assert result["status"] == "success"
    assert result["total_elements"] == 3  # shared deduped, 2 unique
    assert result["error"] is None

    # Verify saved output
    saved = json.loads(
        s3.get_object(
            Bucket=Config.S3_PROCESSED_BUCKET, Key=result["output_artifact"]
        )["Body"].read()
    )
    assert len(saved["elements"]) == 3
    assert "detection_timestamp" in saved
    assert "source_extraction_key" in saved


def test_merge_all_success(s3_setup):
    """All batches success → overall status 'success'."""
    s3 = s3_setup
    event = _base_event()

    batch0_key = "US/CA/2021/intermediate/detection/batch-0/run-1.json"
    result0_key = batch0_key.replace("/batch-", "/result-")

    manifest = _make_manifest([(0, batch0_key)])
    _put_json(s3, event["manifest_key"], manifest)
    _put_json(s3, result0_key, _make_batch_result(0, [_make_element()]))

    result = merge_detection_results(event, None)

    assert result["status"] == "success"
    assert result["error"] is None


def test_merge_mixed_status(s3_setup):
    """Some batches error, some success → overall status 'partial'."""
    s3 = s3_setup
    event = _base_event()

    batch0_key = "US/CA/2021/intermediate/detection/batch-0/run-1.json"
    batch1_key = "US/CA/2021/intermediate/detection/batch-1/run-1.json"
    result0_key = batch0_key.replace("/batch-", "/result-")
    result1_key = batch1_key.replace("/batch-", "/result-")

    manifest = _make_manifest([(0, batch0_key), (1, batch1_key)])
    _put_json(s3, event["manifest_key"], manifest)

    _put_json(s3, result0_key, _make_batch_result(
        0, [_make_element()], status="success"
    ))
    _put_json(s3, result1_key, _make_batch_result(
        1, [], errors=["Chunk 0 failed"], status="error"
    ))

    result = merge_detection_results(event, None)

    assert result["status"] == "partial"
    assert result["error"] is not None
    assert "Chunk 0 failed" in result["error"]


def test_merge_all_error(s3_setup):
    """All batches error with no elements → overall status 'error'."""
    s3 = s3_setup
    event = _base_event()

    batch0_key = "US/CA/2021/intermediate/detection/batch-0/run-1.json"
    result0_key = batch0_key.replace("/batch-", "/result-")

    manifest = _make_manifest([(0, batch0_key)])
    _put_json(s3, event["manifest_key"], manifest)
    _put_json(s3, result0_key, _make_batch_result(
        0, [], errors=["All chunks failed"], status="error"
    ))

    result = merge_detection_results(event, None)

    assert result["status"] == "error"
    assert result["total_elements"] == 0
    assert "All chunks failed" in result["error"]


def test_merge_missing_batch_result(s3_setup):
    """Missing batch result → error status with missing batch info."""
    s3 = s3_setup
    event = _base_event()

    batch0_key = "US/CA/2021/intermediate/detection/batch-0/run-1.json"
    batch1_key = "US/CA/2021/intermediate/detection/batch-1/run-1.json"
    result0_key = batch0_key.replace("/batch-", "/result-")
    # result1 intentionally NOT uploaded

    manifest = _make_manifest([(0, batch0_key), (1, batch1_key)])
    _put_json(s3, event["manifest_key"], manifest)
    _put_json(s3, result0_key, _make_batch_result(0, [_make_element()]))

    result = merge_detection_results(event, None)

    assert result["status"] == "error"
    assert "Missing batch results" in result["error"]
    assert "1" in result["error"]


def test_merge_review_count(s3_setup):
    """Review count reflects elements below confidence threshold."""
    s3 = s3_setup
    event = _base_event()

    batch0_key = "US/CA/2021/intermediate/detection/batch-0/run-1.json"
    result0_key = batch0_key.replace("/batch-", "/result-")

    manifest = _make_manifest([(0, batch0_key)])
    _put_json(s3, event["manifest_key"], manifest)

    elements = [
        _make_element(code="A", title="High", source_page=1, confidence=0.9),
        _make_element(code="B", title="Low", source_page=2, confidence=0.3),
        _make_element(code="C", title="Border", source_page=3, confidence=0.5),
    ]
    _put_json(s3, result0_key, _make_batch_result(0, elements))

    result = merge_detection_results(event, None)

    assert result["status"] == "success"
    # Elements with confidence < 0.7: 0.3 and 0.5
    assert result["review_count"] == 2


def test_merge_output_format_matches_detection_handler(s3_setup):
    """Output saved to S3 matches the detection_handler format (Req 8.1)."""
    s3 = s3_setup
    event = _base_event()

    batch0_key = "US/CA/2021/intermediate/detection/batch-0/run-1.json"
    result0_key = batch0_key.replace("/batch-", "/result-")

    manifest = _make_manifest([(0, batch0_key)])
    _put_json(s3, event["manifest_key"], manifest)
    _put_json(s3, result0_key, _make_batch_result(0, [_make_element()]))

    result = merge_detection_results(event, None)

    saved = json.loads(
        s3.get_object(
            Bucket=Config.S3_PROCESSED_BUCKET, Key=result["output_artifact"]
        )["Body"].read()
    )

    # Must have same keys as detection_handler output
    assert "elements" in saved
    assert "review_count" in saved
    assert "detection_timestamp" in saved
    assert "source_extraction_key" in saved
    assert isinstance(saved["elements"], list)
    assert isinstance(saved["review_count"], int)
