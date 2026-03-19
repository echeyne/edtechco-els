"""Unit tests for merge_parse_results (parse results merger).

Feature: long-running-pipeline-support
Requirements: 6.2, 6.3, 6.4, 6.5, 8.2, 10.4
"""

import json
import pytest
from moto import mock_aws
import boto3

from els_pipeline.parse_batching import merge_parse_results
from els_pipeline.config import Config


def _make_standard(standard_id="US-CA-2021-D1-I1", domain_code="D1", indicator_code="I1"):
    """Helper to create a minimal normalized standard dict."""
    return {
        "standard_id": standard_id,
        "country": "US",
        "state": "CA",
        "version_year": 2021,
        "domain": {"code": domain_code, "name": f"Domain {domain_code}"},
        "indicator": {"code": indicator_code, "name": f"Indicator {indicator_code}"},
        "age_band": "3-5",
        "source_page": 1,
        "source_text": "sample text",
    }


def _base_event(manifest_key="US/CA/2021/intermediate/parsing/manifest/run-1.json"):
    return {
        "manifest_key": manifest_key,
        "country": "US",
        "state": "CA",
        "version_year": 2021,
        "run_id": "run-1",
        "detection_key": "US/CA/2021/intermediate/detection/run-1.json",
    }


def _make_manifest(batches):
    """Build a manifest dict from a list of (batch_index, batch_s3_key) tuples."""
    return {
        "run_id": "run-1",
        "total_elements": 10,
        "total_domains": len(batches),
        "batch_count": len(batches),
        "batches": [
            {
                "batch_index": idx,
                "batch_s3_key": key,
                "domain_count": 1,
                "element_count": 5,
            }
            for idx, key in batches
        ],
        "created_at": "2024-01-01T00:00:00+00:00",
    }


def _make_batch_result(batch_index, standards, errors=None, status="success"):
    """Build a batch result dict."""
    return {
        "batch_index": batch_index,
        "standards": standards,
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


def test_merge_multiple_batch_results(s3_setup):
    """Standards from multiple batches are concatenated correctly (Req 6.2)."""
    s3 = s3_setup
    event = _base_event()

    batch0_key = "US/CA/2021/intermediate/parsing/batch-0/run-1.json"
    batch1_key = "US/CA/2021/intermediate/parsing/batch-1/run-1.json"
    result0_key = batch0_key.replace("/batch-", "/result-")
    result1_key = batch1_key.replace("/batch-", "/result-")

    manifest = _make_manifest([(0, batch0_key), (1, batch1_key)])
    _put_json(s3, event["manifest_key"], manifest)

    std_a = _make_standard(standard_id="A", domain_code="D1", indicator_code="I1")
    std_b = _make_standard(standard_id="B", domain_code="D2", indicator_code="I2")
    std_c = _make_standard(standard_id="C", domain_code="D3", indicator_code="I3")

    _put_json(s3, result0_key, _make_batch_result(0, [std_a, std_b]))
    _put_json(s3, result1_key, _make_batch_result(1, [std_c]))

    result = merge_parse_results(event, None)

    assert result["status"] == "success"
    assert result["total_indicators"] == 3
    assert result["error"] is None
    assert result["stage_name"] == "hierarchy_parsing"

    # Verify saved output
    saved = json.loads(
        s3.get_object(
            Bucket=Config.S3_PROCESSED_BUCKET, Key=result["output_artifact"]
        )["Body"].read()
    )
    assert len(saved["indicators"]) == 3
    assert saved["total_indicators"] == 3


def test_merge_all_success(s3_setup):
    """All batches success → overall status 'success' (Req 6.3)."""
    s3 = s3_setup
    event = _base_event()

    batch0_key = "US/CA/2021/intermediate/parsing/batch-0/run-1.json"
    result0_key = batch0_key.replace("/batch-", "/result-")

    manifest = _make_manifest([(0, batch0_key)])
    _put_json(s3, event["manifest_key"], manifest)
    _put_json(s3, result0_key, _make_batch_result(0, [_make_standard()]))

    result = merge_parse_results(event, None)

    assert result["status"] == "success"
    assert result["error"] is None


def test_merge_mixed_status(s3_setup):
    """Some batches error, some success → overall status 'partial' (Req 6.4)."""
    s3 = s3_setup
    event = _base_event()

    batch0_key = "US/CA/2021/intermediate/parsing/batch-0/run-1.json"
    batch1_key = "US/CA/2021/intermediate/parsing/batch-1/run-1.json"
    result0_key = batch0_key.replace("/batch-", "/result-")
    result1_key = batch1_key.replace("/batch-", "/result-")

    manifest = _make_manifest([(0, batch0_key), (1, batch1_key)])
    _put_json(s3, event["manifest_key"], manifest)

    _put_json(s3, result0_key, _make_batch_result(
        0, [_make_standard()], status="success"
    ))
    _put_json(s3, result1_key, _make_batch_result(
        1, [], errors=["Chunk 0 failed"], status="error"
    ))

    result = merge_parse_results(event, None)

    assert result["status"] == "partial"
    assert result["error"] is not None
    assert "Chunk 0 failed" in result["error"]


def test_merge_all_error(s3_setup):
    """All batches error with no standards → overall status 'error' (Req 6.5)."""
    s3 = s3_setup
    event = _base_event()

    batch0_key = "US/CA/2021/intermediate/parsing/batch-0/run-1.json"
    result0_key = batch0_key.replace("/batch-", "/result-")

    manifest = _make_manifest([(0, batch0_key)])
    _put_json(s3, event["manifest_key"], manifest)
    _put_json(s3, result0_key, _make_batch_result(
        0, [], errors=["All chunks failed"], status="error"
    ))

    result = merge_parse_results(event, None)

    assert result["status"] == "error"
    assert result["total_indicators"] == 0
    assert "All chunks failed" in result["error"]


def test_merge_missing_batch_result(s3_setup):
    """Missing batch result → error status with missing batch info (Req 10.4)."""
    s3 = s3_setup
    event = _base_event()

    batch0_key = "US/CA/2021/intermediate/parsing/batch-0/run-1.json"
    batch1_key = "US/CA/2021/intermediate/parsing/batch-1/run-1.json"
    result0_key = batch0_key.replace("/batch-", "/result-")
    # result1 intentionally NOT uploaded

    manifest = _make_manifest([(0, batch0_key), (1, batch1_key)])
    _put_json(s3, event["manifest_key"], manifest)
    _put_json(s3, result0_key, _make_batch_result(0, [_make_standard()]))

    result = merge_parse_results(event, None)

    assert result["status"] == "error"
    assert "Missing batch results" in result["error"]
    assert "1" in result["error"]


def test_merge_output_format_matches_parsing_handler(s3_setup):
    """Output saved to S3 matches the parsing_handler format (Req 8.2)."""
    s3 = s3_setup
    event = _base_event()

    batch0_key = "US/CA/2021/intermediate/parsing/batch-0/run-1.json"
    result0_key = batch0_key.replace("/batch-", "/result-")

    manifest = _make_manifest([(0, batch0_key)])
    _put_json(s3, event["manifest_key"], manifest)
    _put_json(s3, result0_key, _make_batch_result(0, [_make_standard()]))

    result = merge_parse_results(event, None)

    saved = json.loads(
        s3.get_object(
            Bucket=Config.S3_PROCESSED_BUCKET, Key=result["output_artifact"]
        )["Body"].read()
    )

    # Must have same keys as parsing_handler output
    assert "indicators" in saved
    assert "total_indicators" in saved
    assert "parsing_timestamp" in saved
    assert "source_detection_key" in saved
    assert isinstance(saved["indicators"], list)
    assert isinstance(saved["total_indicators"], int)


def test_merge_passthrough_fields(s3_setup):
    """Country, state, version_year, run_id are passed through."""
    s3 = s3_setup
    event = _base_event()

    batch0_key = "US/CA/2021/intermediate/parsing/batch-0/run-1.json"
    result0_key = batch0_key.replace("/batch-", "/result-")

    manifest = _make_manifest([(0, batch0_key)])
    _put_json(s3, event["manifest_key"], manifest)
    _put_json(s3, result0_key, _make_batch_result(0, [_make_standard()]))

    result = merge_parse_results(event, None)

    assert result["country"] == "US"
    assert result["state"] == "CA"
    assert result["version_year"] == 2021
    assert result["run_id"] == "run-1"
