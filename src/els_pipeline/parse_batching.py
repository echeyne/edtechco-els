"""Parse batching for the ELS pipeline.

Splits detected elements into bounded batches of domain chunks,
processes each batch through Bedrock, and merges partial results.

Feature: long-running-pipeline-support
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List

import json

from botocore.exceptions import ClientError, ReadTimeoutError

from .config import Config
from .models import (
    DetectedElement,
    ParseBatchInfo,
    ParseBatchManifest,
    ParseBatchResult,
)
from .parser import (
    MAX_PARSE_RETRIES,
    build_parsing_prompt,
    call_bedrock_llm,
    chunk_elements_by_domain,
    parse_llm_response,
)
from .s3_helpers import construct_intermediate_key, load_json_from_s3, save_json_to_s3

logger = logging.getLogger(__name__)


def prepare_parse_batches(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Split detected elements into bounded parse batches by domain.

    Loads detection output from S3, filters out elements needing review,
    groups elements by domain using chunk_elements_by_domain, then groups
    domain chunks into batches of <= MAX_DOMAINS_PER_BATCH. Each batch is
    saved to S3 and a manifest is produced.

    Args:
        event: Lambda event containing output_artifact, country, state,
               version_year, age_band, and run_id.
        context: Lambda context (unused).

    Returns:
        Dict with status, batch_count, manifest_key, batch_keys, and
        passthrough fields (country, state, version_year, age_band, run_id).
    """
    run_id = event.get("run_id", "unknown")
    country = event.get("country", "")
    state = event.get("state", "")
    version_year = event.get("version_year", 0)
    age_band = event.get("age_band", "")

    logger.info(f"Preparing parse batches: run_id={run_id}")

    # Load detection output from S3
    try:
        detection_output = load_json_from_s3(
            Config.S3_PROCESSED_BUCKET, event["output_artifact"]
        )
        elements_data = detection_output.get("elements", [])
        logger.info(f"Loaded {len(elements_data)} elements from S3")
    except Exception as e:
        error_msg = f"Failed to load detection output from S3: {e}"
        logger.error(error_msg)
        return {
            "status": "error",
            "error": error_msg,
            "country": country,
            "state": state,
            "version_year": version_year,
            "age_band": age_band,
            "run_id": run_id,
        }

    # Convert to DetectedElement instances and filter out needs_review
    elements = [DetectedElement(**e) for e in elements_data]
    valid_elements = [e for e in elements if not e.needs_review]
    logger.info(
        f"Filtered elements: {len(valid_elements)} valid out of {len(elements)} total"
    )

    # Group by domain using existing function
    domain_chunks = chunk_elements_by_domain(valid_elements)
    max_per_batch = Config.MAX_DOMAINS_PER_BATCH

    # Group domain chunks into batches
    batches: List[ParseBatchInfo] = []
    batch_keys: List[Dict[str, Any]] = []

    if not domain_chunks:
        # Handle empty input: produce one batch with empty elements
        batch_key = construct_intermediate_key(
            country, state, version_year,
            "parsing/batch-0", run_id,
        )
        save_json_to_s3({"elements": []}, Config.S3_PROCESSED_BUCKET, batch_key)
        batches.append(
            ParseBatchInfo(
                batch_index=0, batch_s3_key=batch_key,
                domain_count=0, element_count=0,
            )
        )
        batch_keys.append({
            "batch_key": batch_key,
            "batch_index": 0,
            "country": country,
            "state": state,
            "version_year": version_year,
            "age_band": age_band,
            "run_id": run_id,
        })
    else:
        for i in range(0, len(domain_chunks), max_per_batch):
            batch_domain_chunks = domain_chunks[i : i + max_per_batch]
            batch_elements = [el for chunk in batch_domain_chunks for el in chunk]
            idx = len(batches)
            batch_key = construct_intermediate_key(
                country, state, version_year,
                f"parsing/batch-{idx}", run_id,
            )
            save_json_to_s3(
                {"elements": [e.model_dump() for e in batch_elements]},
                Config.S3_PROCESSED_BUCKET,
                batch_key,
            )
            batches.append(
                ParseBatchInfo(
                    batch_index=idx,
                    batch_s3_key=batch_key,
                    domain_count=len(batch_domain_chunks),
                    element_count=len(batch_elements),
                )
            )
            batch_keys.append({
                "batch_key": batch_key,
                "batch_index": idx,
                "country": country,
                "state": state,
                "version_year": version_year,
                "age_band": age_band,
                "run_id": run_id,
            })

    # Build and save manifest
    manifest = ParseBatchManifest(
        run_id=run_id,
        total_elements=len(valid_elements),
        total_domains=len(domain_chunks),
        batch_count=len(batches),
        batches=batches,
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    manifest_key = construct_intermediate_key(
        country, state, version_year, "parsing/manifest", run_id,
    )
    save_json_to_s3(manifest.model_dump(), Config.S3_PROCESSED_BUCKET, manifest_key)

    logger.info(
        f"Parse batch preparation complete: "
        f"batch_count={len(batches)}, total_domains={len(domain_chunks)}"
    )

    return {
        "status": "success",
        "batch_count": len(batches),
        "manifest_key": manifest_key,
        "batch_keys": batch_keys,
        "country": country,
        "state": state,
        "version_year": version_year,
        "age_band": age_band,
        "run_id": run_id,
    }


def parse_batch(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Process a single parse batch through Bedrock LLM.

    Loads batch elements from S3, re-groups them by domain, and runs each
    domain chunk through the parsing prompt/LLM/parse pipeline with retry
    logic.

    Args:
        event: Lambda event containing batch_key, batch_index, country,
               state, version_year, age_band, and run_id.
        context: Lambda context (unused).

    Returns:
        Dict with batch_index, standards_count, result_key, and status.
    """
    batch_index = event.get("batch_index", 0)
    run_id = event.get("run_id", "unknown")
    country = event.get("country", "")
    state = event.get("state", "")
    version_year = event.get("version_year", 0)
    age_band = event.get("age_band", "")

    logger.info(f"Processing parse batch {batch_index}: run_id={run_id}")

    # Load batch elements from S3
    batch_data = load_json_from_s3(Config.S3_PROCESSED_BUCKET, event["batch_key"])
    elements = [DetectedElement(**e) for e in batch_data.get("elements", [])]

    # Re-group by domain
    domain_chunks = chunk_elements_by_domain(elements)

    all_standards = []
    errors = []

    for chunk_idx, chunk in enumerate(domain_chunks):
        prompt = build_parsing_prompt(chunk, country, state, version_year, age_band)
        success = False
        for attempt in range(MAX_PARSE_RETRIES + 1):
            try:
                response_text = call_bedrock_llm(prompt)
                standards = parse_llm_response(
                    response_text, country, state, version_year, age_band,
                )
                all_standards.extend(standards)
                success = True
                break
            except (ValueError, json.JSONDecodeError, ClientError, ReadTimeoutError) as e:
                if attempt == MAX_PARSE_RETRIES:
                    error_msg = (
                        f"Chunk {chunk_idx} failed after "
                        f"{MAX_PARSE_RETRIES + 1} attempts: {e}"
                    )
                    logger.error(error_msg)
                    errors.append(error_msg)
                else:
                    logger.warning(
                        f"Chunk {chunk_idx} parse attempt "
                        f"{attempt + 1}/{MAX_PARSE_RETRIES + 1} failed: {e}"
                    )

    # Determine status
    if not errors:
        status = "success"
    elif all_standards:
        status = "partial"
    else:
        status = "error"

    # Save result to S3
    result_key = event["batch_key"].replace("/batch-", "/result-")
    batch_result = ParseBatchResult(
        batch_index=batch_index,
        standards=[s.model_dump() for s in all_standards],
        errors=errors,
        status=status,
    )
    save_json_to_s3(batch_result.model_dump(), Config.S3_PROCESSED_BUCKET, result_key)

    logger.info(
        f"Parse batch {batch_index} complete: "
        f"standards={len(all_standards)}, errors={len(errors)}, status={status}"
    )

    return {
        "batch_index": batch_index,
        "standards_count": len(all_standards),
        "result_key": result_key,
        "status": status,
    }

def merge_parse_results(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Merge all partial parse batch results into a single output.

    Loads the batch manifest and all partial result files from S3,
    concatenates standards lists, aggregates errors, determines overall
    status, and saves the final parsing output in the same format as
    the existing parsing_handler.

    Args:
        event: Lambda event containing manifest_key, country, state,
               version_year, run_id, and optionally detection_key.
        context: Lambda context (unused).

    Returns:
        Dict with status, stage_name, output_artifact, total_indicators,
        country, state, version_year, run_id, error.
    """
    run_id = event.get("run_id", "unknown")
    country = event.get("country", "")
    state = event.get("state", "")
    version_year = event.get("version_year", 0)

    logger.info(f"Merging parse results: run_id={run_id}")

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
            "stage_name": "hierarchy_parsing",
            "output_artifact": None,
            "total_indicators": 0,
            "country": country,
            "state": state,
            "version_year": version_year,
            "run_id": run_id,
            "error": error_msg,
        }

    all_standards: List[Dict[str, Any]] = []
    all_errors: List[str] = []
    missing_batches: List[int] = []

    # Load all partial result files
    for batch_info in manifest["batches"]:
        result_key = batch_info["batch_s3_key"].replace("/batch-", "/result-")
        try:
            batch_result = load_json_from_s3(
                Config.S3_PROCESSED_BUCKET, result_key
            )
            all_standards.extend(batch_result.get("standards", []))
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
            "stage_name": "hierarchy_parsing",
            "output_artifact": None,
            "total_indicators": 0,
            "country": country,
            "state": state,
            "version_year": version_year,
            "run_id": run_id,
            "error": error_msg,
        }

    # Determine overall status
    if all_errors and all_standards:
        status = "partial"
    elif all_errors and not all_standards:
        status = "error"
    else:
        status = "success"

    # Save final parsing output in same format as parsing_handler
    output = {
        "indicators": all_standards,
        "total_indicators": len(all_standards),
        "parsing_timestamp": datetime.now(timezone.utc).isoformat(),
        "source_detection_key": event.get("detection_key", ""),
    }
    output_key = construct_intermediate_key(
        country, state, version_year, "parsing", run_id,
    )
    save_json_to_s3(output, Config.S3_PROCESSED_BUCKET, output_key)

    logger.info(
        f"Parse merge complete: total_indicators={len(all_standards)}, "
        f"status={status}"
    )

    return {
        "status": status,
        "stage_name": "hierarchy_parsing",
        "output_artifact": output_key,
        "total_indicators": len(all_standards),
        "country": country,
        "state": state,
        "version_year": version_year,
        "run_id": run_id,
        "error": "; ".join(all_errors) if all_errors else None,
    }

