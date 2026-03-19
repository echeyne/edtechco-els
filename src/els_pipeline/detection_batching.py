"""Detection batching module for the ELS pipeline.

Splits extracted text blocks into bounded batches for parallel processing
via Step Functions Map states, eliminating Lambda timeout issues for large documents.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List

from .config import Config
from .detector import (
    chunk_text_blocks,
    build_detection_prompt,
    call_bedrock_llm,
    parse_llm_response,
    MAX_PARSE_RETRIES,
)
from .models import (
    TextBlock,
    DetectionBatchInfo,
    DetectionBatchManifest,
    DetectionBatchResult,
)
from .s3_helpers import load_json_from_s3, save_json_to_s3, construct_intermediate_key

logger = logging.getLogger(__name__)


def prepare_detection_batches(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Split extracted text blocks into bounded detection batches.

    Loads extraction output from S3, chunks text blocks by token count,
    groups chunks into batches of <= MAX_CHUNKS_PER_BATCH, saves each
    batch to S3, and returns a manifest describing the split.

    Args:
        event: Lambda event containing output_artifact, country, state,
               version_year, and run_id.
        context: Lambda context (unused).

    Returns:
        Dict with status, batch_count, manifest_key, batch_keys, and
        passthrough fields (country, state, version_year, run_id).
    """
    run_id = event.get("run_id", "unknown")
    country = event.get("country", "")
    state = event.get("state", "")
    version_year = event.get("version_year", 0)

    logger.info(f"Preparing detection batches: run_id={run_id}")

    # Load extraction output from S3
    try:
        extraction_output = load_json_from_s3(
            Config.S3_PROCESSED_BUCKET, event["output_artifact"]
        )
        blocks_data = extraction_output.get("blocks", [])
        logger.info(f"Loaded {len(blocks_data)} blocks from S3")
    except Exception as e:
        error_msg = f"Failed to load extraction output from S3: {e}"
        logger.error(error_msg)
        return {
            "status": "error",
            "error": error_msg,
            "country": country,
            "state": state,
            "version_year": version_year,
            "run_id": run_id,
        }

    # Convert to TextBlock instances
    blocks = [TextBlock(**b) for b in blocks_data]

    # Chunk text blocks using existing function
    chunks = chunk_text_blocks(blocks)
    max_per_batch = Config.MAX_CHUNKS_PER_BATCH

    # Group chunks into batches
    batches: List[DetectionBatchInfo] = []
    batch_keys: List[Dict[str, Any]] = []

    if not chunks:
        # Handle empty input: produce one batch with empty blocks
        batch_key = construct_intermediate_key(
            country, state, version_year,
            "detection/batch-0", run_id,
        )
        save_json_to_s3({"blocks": []}, Config.S3_PROCESSED_BUCKET, batch_key)
        batches.append(
            DetectionBatchInfo(
                batch_index=0, batch_s3_key=batch_key,
                chunk_count=0, block_count=0,
            )
        )
        batch_keys.append({
            "batch_key": batch_key,
            "batch_index": 0,
            "country": country,
            "state": state,
            "version_year": version_year,
            "run_id": run_id,
        })
    else:
        for i in range(0, len(chunks), max_per_batch):
            batch_chunks = chunks[i : i + max_per_batch]
            batch_blocks = [block for chunk in batch_chunks for block in chunk]
            idx = len(batches)
            batch_key = construct_intermediate_key(
                country, state, version_year,
                f"detection/batch-{idx}", run_id,
            )
            save_json_to_s3(
                {"blocks": [b.model_dump() for b in batch_blocks]},
                Config.S3_PROCESSED_BUCKET,
                batch_key,
            )
            batches.append(
                DetectionBatchInfo(
                    batch_index=idx,
                    batch_s3_key=batch_key,
                    chunk_count=len(batch_chunks),
                    block_count=len(batch_blocks),
                )
            )
            batch_keys.append({
                "batch_key": batch_key,
                "batch_index": idx,
                "country": country,
                "state": state,
                "version_year": version_year,
                "run_id": run_id,
            })

    # Build and save manifest
    manifest = DetectionBatchManifest(
        run_id=run_id,
        total_blocks=len(blocks),
        total_chunks=len(chunks),
        batch_count=len(batches),
        batches=batches,
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    manifest_key = construct_intermediate_key(
        country, state, version_year, "detection/manifest", run_id,
    )
    save_json_to_s3(manifest.model_dump(), Config.S3_PROCESSED_BUCKET, manifest_key)

    logger.info(
        f"Detection batch preparation complete: "
        f"batch_count={len(batches)}, total_chunks={len(chunks)}"
    )

    return {
        "status": "success",
        "batch_count": len(batches),
        "manifest_key": manifest_key,
        "batch_keys": batch_keys,
        "country": country,
        "state": state,
        "version_year": version_year,
        "run_id": run_id,
    }

def detect_batch(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Process a single detection batch through Bedrock LLM.

    Loads batch text blocks from S3, re-chunks them, and runs each chunk
    through the detection prompt/LLM/parse pipeline with retry logic.

    Args:
        event: Lambda event containing batch_key, batch_index, country,
               state, version_year, and run_id.
        context: Lambda context (unused).

    Returns:
        Dict with batch_index, elements_count, result_key, and status.
    """
    batch_index = event.get("batch_index", 0)
    run_id = event.get("run_id", "unknown")

    logger.info(f"Processing detection batch {batch_index}: run_id={run_id}")

    # Load batch text blocks from S3
    batch_data = load_json_from_s3(Config.S3_PROCESSED_BUCKET, event["batch_key"])
    blocks = [TextBlock(**b) for b in batch_data.get("blocks", [])]

    # Re-chunk the batch blocks
    chunks = chunk_text_blocks(blocks)

    all_elements = []
    errors = []

    for chunk_idx, chunk in enumerate(chunks):
        prompt = build_detection_prompt(chunk)
        success = False
        for attempt in range(MAX_PARSE_RETRIES + 1):
            try:
                response_text = call_bedrock_llm(prompt)
                elements = parse_llm_response(response_text, chunk)
                all_elements.extend(elements)
                success = True
                break
            except (ValueError, json.JSONDecodeError) as e:
                if attempt == MAX_PARSE_RETRIES:
                    error_msg = f"Chunk {chunk_idx} failed after {MAX_PARSE_RETRIES + 1} attempts: {e}"
                    logger.error(error_msg)
                    errors.append(error_msg)
                else:
                    logger.warning(
                        f"Chunk {chunk_idx} parse attempt {attempt + 1}/{MAX_PARSE_RETRIES + 1} failed: {e}"
                    )

    # Determine status
    if not errors:
        status = "success"
    elif all_elements:
        status = "partial"
    else:
        status = "error"

    # Save result to S3
    result_key = event["batch_key"].replace("/batch-", "/result-")
    batch_result = DetectionBatchResult(
        batch_index=batch_index,
        elements=[e.model_dump() for e in all_elements],
        errors=errors,
        status=status,
    )
    save_json_to_s3(batch_result.model_dump(), Config.S3_PROCESSED_BUCKET, result_key)

    logger.info(
        f"Detection batch {batch_index} complete: "
        f"elements={len(all_elements)}, errors={len(errors)}, status={status}"
    )

    return {
        "batch_index": batch_index,
        "elements_count": len(all_elements),
        "result_key": result_key,
        "status": status,
    }


def merge_detection_results(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Merge all partial detection batch results into a single output.

    Loads the batch manifest and all partial result files from S3,
    merges and deduplicates elements using (code, title, source_page),
    counts elements needing review, determines overall status, and
    saves the final detection output in the same format as the
    existing detection_handler.

    Args:
        event: Lambda event containing manifest_key, country, state,
               version_year, run_id, and optionally extraction_key.
        context: Lambda context (unused).

    Returns:
        Dict with status, stage_name, output_artifact, review_count,
        total_elements, country, state, version_year, run_id, error.
    """
    run_id = event.get("run_id", "unknown")
    country = event.get("country", "")
    state = event.get("state", "")
    version_year = event.get("version_year", 0)

    logger.info(f"Merging detection results: run_id={run_id}")

    # Load batch manifest from S3
    try:
        manifest = load_json_from_s3(
            Config.S3_PROCESSED_BUCKET, event["manifest_key"]
        )
    except Exception as e:
        error_msg = f"Failed to load batch manifest from S3: {e}"
        logger.error(error_msg)
        return {
            "status": "error",
            "stage_name": "structure_detection",
            "output_artifact": None,
            "review_count": 0,
            "total_elements": 0,
            "country": country,
            "state": state,
            "version_year": version_year,
            "run_id": run_id,
            "error": error_msg,
        }

    all_elements: List[Dict[str, Any]] = []
    all_errors: List[str] = []
    missing_batches: List[int] = []

    # Load all partial result files
    for batch_info in manifest["batches"]:
        result_key = batch_info["batch_s3_key"].replace("/batch-", "/result-")
        try:
            batch_result = load_json_from_s3(
                Config.S3_PROCESSED_BUCKET, result_key
            )
            all_elements.extend(batch_result.get("elements", []))
            all_errors.extend(batch_result.get("errors", []))
        except Exception as e:
            missing_batches.append(batch_info["batch_index"])
            logger.error(
                f"Failed to load batch result {batch_info['batch_index']} "
                f"from {result_key}: {e}"
            )

    # Handle missing batch results
    if missing_batches:
        error_msg = f"Missing batch results for batches: {missing_batches}"
        logger.error(error_msg)
        return {
            "status": "error",
            "stage_name": "structure_detection",
            "output_artifact": None,
            "review_count": 0,
            "total_elements": 0,
            "country": country,
            "state": state,
            "version_year": version_year,
            "run_id": run_id,
            "error": error_msg,
        }

    # Deduplicate elements using (code, title, source_page) tuple
    seen: set = set()
    unique_elements: List[Dict[str, Any]] = []
    for elem in all_elements:
        key = (elem["code"], elem["title"], elem.get("source_page", 0))
        if key not in seen:
            seen.add(key)
            unique_elements.append(elem)

    # Count elements needing review
    review_count = sum(
        1 for e in unique_elements
        if e.get("confidence", 1.0) < Config.CONFIDENCE_THRESHOLD
    )

    # Determine overall status
    if all_errors and unique_elements:
        status = "partial"
    elif all_errors and not unique_elements:
        status = "error"
    else:
        status = "success"

    # Save final detection output in same format as detection_handler
    output = {
        "elements": unique_elements,
        "review_count": review_count,
        "detection_timestamp": datetime.now(timezone.utc).isoformat(),
        "source_extraction_key": event.get("extraction_key", ""),
    }
    output_key = construct_intermediate_key(
        country, state, version_year, "detection", run_id,
    )
    save_json_to_s3(output, Config.S3_PROCESSED_BUCKET, output_key)

    logger.info(
        f"Detection merge complete: total_elements={len(unique_elements)}, "
        f"review_count={review_count}, status={status}"
    )

    return {
        "status": status,
        "stage_name": "structure_detection",
        "output_artifact": output_key,
        "review_count": review_count,
        "total_elements": len(unique_elements),
        "country": country,
        "state": state,
        "version_year": version_year,
        "run_id": run_id,
        "error": "; ".join(all_errors) if all_errors else None,
    }

