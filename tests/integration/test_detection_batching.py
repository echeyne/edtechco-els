"""Unit tests for detection batching (prepare_detection_batches).

Feature: long-running-pipeline-support
"""

import json
import pytest
from moto import mock_aws
import boto3

from els_pipeline.detection_batching import prepare_detection_batches
from els_pipeline.config import Config


def _make_block(text="Sample text", page=1):
    """Helper to create a minimal TextBlock dict."""
    return {
        "text": text,
        "page_number": page,
        "block_type": "LINE",
        "confidence": 0.95,
        "geometry": {"BoundingBox": {"Top": 0.1, "Left": 0.1}},
    }


def _base_event(output_artifact="US/CA/2021/intermediate/extraction/run-1.json"):
    return {
        "output_artifact": output_artifact,
        "country": "US",
        "state": "CA",
        "version_year": 2021,
        "run_id": "run-1",
    }


@pytest.fixture
def s3_setup():
    """Set up mocked S3 bucket."""
    with mock_aws():
        s3 = boto3.client("s3", region_name=Config.AWS_REGION)
        s3.create_bucket(Bucket=Config.S3_PROCESSED_BUCKET)
        yield s3


def test_prepare_zero_blocks(s3_setup):
    """Empty extraction produces at least one batch."""
    s3 = s3_setup
    event = _base_event()
    extraction = {"blocks": [], "total_pages": 1}
    s3.put_object(
        Bucket=Config.S3_PROCESSED_BUCKET,
        Key=event["output_artifact"],
        Body=json.dumps(extraction),
    )

    result = prepare_detection_batches(event, None)

    assert result["status"] == "success"
    assert result["batch_count"] == 1
    assert len(result["batch_keys"]) == 1


def test_prepare_single_block(s3_setup):
    """One block produces exactly one batch."""
    s3 = s3_setup
    event = _base_event()
    extraction = {"blocks": [_make_block()], "total_pages": 1}
    s3.put_object(
        Bucket=Config.S3_PROCESSED_BUCKET,
        Key=event["output_artifact"],
        Body=json.dumps(extraction),
    )

    result = prepare_detection_batches(event, None)

    assert result["status"] == "success"
    assert result["batch_count"] >= 1
    # Verify manifest was saved
    manifest = json.loads(
        s3.get_object(
            Bucket=Config.S3_PROCESSED_BUCKET, Key=result["manifest_key"]
        )["Body"].read()
    )
    assert manifest["total_blocks"] == 1


def test_prepare_exactly_max_chunks(s3_setup):
    """Blocks that produce exactly MAX_CHUNKS_PER_BATCH chunks → one batch."""
    s3 = s3_setup
    event = _base_event()
    # Create enough blocks so chunking produces exactly MAX_CHUNKS_PER_BATCH chunks.
    # Each chunk targets ~2000 tokens (~8000 chars). We create blocks that each
    # form their own chunk by making them large enough.
    big_text = "x" * 8000  # ~2000 tokens each
    blocks = [_make_block(text=big_text, page=i + 1) for i in range(Config.MAX_CHUNKS_PER_BATCH)]
    extraction = {"blocks": blocks, "total_pages": len(blocks)}
    s3.put_object(
        Bucket=Config.S3_PROCESSED_BUCKET,
        Key=event["output_artifact"],
        Body=json.dumps(extraction),
    )

    result = prepare_detection_batches(event, None)

    assert result["status"] == "success"
    assert result["batch_count"] == 1


def test_prepare_exceeding_max_chunks(s3_setup):
    """Blocks producing more than MAX_CHUNKS_PER_BATCH chunks → multiple batches."""
    s3 = s3_setup
    event = _base_event()
    big_text = "x" * 8000
    num_blocks = Config.MAX_CHUNKS_PER_BATCH + 2
    blocks = [_make_block(text=big_text, page=i + 1) for i in range(num_blocks)]
    extraction = {"blocks": blocks, "total_pages": num_blocks}
    s3.put_object(
        Bucket=Config.S3_PROCESSED_BUCKET,
        Key=event["output_artifact"],
        Body=json.dumps(extraction),
    )

    result = prepare_detection_batches(event, None)

    assert result["status"] == "success"
    assert result["batch_count"] >= 2
    # Verify each batch key is present
    assert len(result["batch_keys"]) == result["batch_count"]


def test_prepare_s3_load_failure(s3_setup):
    """S3 load failure returns error status."""
    event = _base_event(output_artifact="nonexistent/key.json")

    result = prepare_detection_batches(event, None)

    assert result["status"] == "error"
    assert "error" in result
    assert result["run_id"] == "run-1"


def test_prepare_passthrough_fields(s3_setup):
    """Country, state, version_year, run_id are passed through."""
    s3 = s3_setup
    event = _base_event()
    extraction = {"blocks": [_make_block()], "total_pages": 1}
    s3.put_object(
        Bucket=Config.S3_PROCESSED_BUCKET,
        Key=event["output_artifact"],
        Body=json.dumps(extraction),
    )

    result = prepare_detection_batches(event, None)

    assert result["country"] == "US"
    assert result["state"] == "CA"
    assert result["version_year"] == 2021
    assert result["run_id"] == "run-1"
