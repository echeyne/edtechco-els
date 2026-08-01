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
    assert "detection_timestamp" in saved
    assert "source_extraction_key" in saved
    assert isinstance(saved["elements"], list)


def _make_typed_element(level, code, title, source_page):
    """A detected element at an arbitrary hierarchy level."""
    return {
        "level": level,
        "code": code,
        "title": title,
        "description": "desc",
        "confidence": 0.9,
        "source_page": source_page,
        "source_text": f"[Page {source_page}] {title}",
    }


def test_merge_collapses_overlap_twins_displaced_past_a_later_domain(s3_setup):
    """Overlap twins re-emitted AFTER a later domain heading still collapse.

    This is the batched-path counterpart of the CO duplicate-indicator bug, and
    it is deliberately tested HERE rather than through the detector eval: the
    eval exercises the direct path (``detect_structure``), which chunks and
    samples differently from the batched path production runs
    (``detection_batching`` calls the LLM with ``prefill='['``, the direct path
    does not). CO's three duplicate Gross Motor indicators appear only in the
    batched artifact, so a green CO detector eval is a FALSE NEGATIVE for them.

    Shape reproduced from ``outputs/07-24-26/CO-detection.json``: batch 0 ends
    with the page-4 Gross Motor indicators; batch 1's overlap re-emits those
    same three rows, but only after it has already emitted the page-5 SED
    domain heading. A position-derived domain scope therefore disagrees between
    the two copies (PDH vs SED) and keeps both. Identity must come from the
    element's OWN code instead (``parser.code_domain_scopes``), which both
    copies agree on, so the twins collapse.
    """
    s3 = s3_setup
    event = _base_event()

    batch0_key = "US/CA/2021/intermediate/detection/batch-0/run-1.json"
    batch1_key = "US/CA/2021/intermediate/detection/batch-1/run-1.json"
    result0_key = batch0_key.replace("/batch-", "/result-")
    result1_key = batch1_key.replace("/batch-", "/result-")

    manifest = _make_manifest([(0, batch0_key), (1, batch1_key)])
    _put_json(s3, event["manifest_key"], manifest)

    # The three page-4 indicators that the chunk overlap re-emits.
    twins = [
        _make_typed_element(
            "indicator", "1", "Develop motor control and balance", 4
        ),
        _make_typed_element(
            "indicator", "2", "Develop motor coordination and skill", 4
        ),
        _make_typed_element("indicator", "3", "Understand movement concepts", 4),
    ]

    batch0 = [
        _make_typed_element("domain", "PDH", "Physical Development & Health", 2),
        _make_typed_element("strand", "2", "Gross Motor Skills", 4),
        *twins,
    ]
    # Batch 1 opens past the overlap boundary: the later domain heading is
    # emitted BEFORE the re-emitted twins, so document order puts them under
    # the wrong domain.
    batch1 = [
        _make_typed_element("domain", "SED", "Social & Emotional Development", 5),
        _make_typed_element("strand", "1", "Relationships with Adults and Peers", 6),
        *twins,
        _make_typed_element("indicator", "1", "Recognize self as a unique individual", 7),
    ]

    _put_json(s3, result0_key, _make_batch_result(0, batch0))
    _put_json(s3, result1_key, _make_batch_result(1, batch1))

    result = merge_detection_results(event, None)
    assert result["status"] == "success"

    saved = json.loads(
        s3.get_object(
            Bucket=Config.S3_PROCESSED_BUCKET, Key=result["output_artifact"]
        )["Body"].read()
    )
    elements = saved["elements"]

    # The three twins must survive exactly once each.
    for title in (
        "Develop motor control and balance",
        "Develop motor coordination and skill",
        "Understand movement concepts",
    ):
        matches = [e for e in elements if e["title"] == title]
        assert len(matches) == 1, (
            f"{title!r} survived {len(matches)}x; overlap twins displaced past "
            f"a later domain heading were not collapsed"
        )

    # 2 domains + 2 strands + 3 collapsed twins + 1 unique = 8
    assert result["total_elements"] == 8
    assert len(elements) == 8

    # And the surviving copy must keep its FIRST position — before the later
    # domain heading — or the parser reparents it by document order.
    idx = {e["title"]: i for i, e in enumerate(elements)}
    assert idx["Develop motor control and balance"] < idx["Social & Emotional Development"]
