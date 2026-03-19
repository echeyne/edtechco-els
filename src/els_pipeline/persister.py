"""Data persistence module for ELS pipeline.

Loads validated canonical records from S3 and persists them
to Aurora PostgreSQL using the db module.
"""

import logging
from typing import Dict, Any, List, Tuple

from botocore.exceptions import ClientError

from .config import Config
from .db import DatabaseConnection, persist_standard
from .models import NormalizedStandard
from .s3_helpers import load_json_from_s3
from .validator import deserialize_record

logger = logging.getLogger(__name__)


def _load_validation_summary(validation_key: str) -> Dict[str, Any]:
    """
    Load validation summary from S3.

    Args:
        validation_key: S3 key for the validation summary

    Returns:
        Validation summary dict

    Raises:
        ClientError: If S3 load fails
    """
    summary = load_json_from_s3(Config.S3_PROCESSED_BUCKET, validation_key)
    logger.info(
        f"Loaded validation summary from S3: {validation_key}, "
        f"{len(summary.get('validated_records', []))} records to persist"
    )
    return summary


def _persist_single_record(record_key: str) -> None:
    """
    Load a canonical JSON record from S3 and persist it to the database.

    The age_band is taken from the parsed indicator data (standard.age_band),
    not from document-level metadata.

    Args:
        record_key: S3 key for the canonical JSON record

    Raises:
        ClientError: If S3 load fails
        Exception: If database persistence fails
    """
    canonical_json = load_json_from_s3(Config.S3_PROCESSED_BUCKET, record_key)
    standard = deserialize_record(canonical_json)

    document_meta = {
        "title": canonical_json["document"]["title"],
        "source_url": canonical_json["document"].get("source_url"),
        "s3_key": canonical_json["document"].get("s3_key"),
        "publishing_agency": canonical_json["document"]["publishing_agency"],
    }

    persist_standard(standard, document_meta)


def _record_pipeline_run(
    event: Dict[str, Any],
    validation_key: str,
    total_keys: int,
    records_persisted: int,
    has_errors: bool,
) -> None:
    """
    Record the pipeline run status in the database.

    Args:
        event: Lambda event dict with run_id, country, state, version_year
        validation_key: S3 key of the validation summary
        total_keys: Total number of validated record keys
        records_persisted: Number of records successfully persisted
        has_errors: Whether any persistence errors occurred
    """
    try:
        with DatabaseConnection.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO pipeline_runs (
                        run_id, document_s3_key, country, state, version_year,
                        status, total_indicators, total_validated, completed_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW())
                    ON CONFLICT (run_id) DO UPDATE
                    SET status = EXCLUDED.status,
                        total_indicators = EXCLUDED.total_indicators,
                        total_validated = EXCLUDED.total_validated,
                        completed_at = NOW()
                """, (
                    event.get("run_id"),
                    validation_key,
                    event["country"],
                    event["state"],
                    event["version_year"],
                    "completed" if not has_errors else "partial",
                    total_keys,
                    records_persisted,
                ))
                conn.commit()
    except Exception as e:
        logger.error(f"Failed to record pipeline run: {str(e)}")


def persist_records(event: Dict[str, Any]) -> Tuple[int, List[Dict[str, Any]]]:
    """
    Load validated records from S3 and persist them to the database.

    Args:
        event: Lambda event containing output_artifact, country, state,
               version_year, and run_id

    Returns:
        Tuple of (records_persisted count, list of error dicts)

    Raises:
        ClientError: If the validation summary cannot be loaded from S3
    """
    validation_key = event["output_artifact"]
    validation_summary = _load_validation_summary(validation_key)
    validated_keys = validation_summary["validated_records"]

    if not validated_keys:
        logger.warning("No validated records to persist")
        return 0, []

    DatabaseConnection.initialize_pool()

    records_persisted = 0
    persist_errors: List[Dict[str, Any]] = []

    try:
        for record_key in validated_keys:
            try:
                _persist_single_record(record_key)
                records_persisted += 1
            except ClientError as e:
                error_msg = f"Failed to load record from S3: {record_key}"
                logger.error(f"{error_msg} - {str(e)}")
                persist_errors.append({"record_key": record_key, "error": error_msg})
            except Exception as e:
                logger.error(f"Failed to persist record {record_key}: {str(e)}")
                persist_errors.append({"record_key": record_key, "error": str(e)})

        _record_pipeline_run(
            event, validation_key, len(validated_keys),
            records_persisted, bool(persist_errors),
        )
    finally:
        DatabaseConnection.close_pool()

    logger.info(
        f"Data persistence completed: "
        f"persisted={records_persisted}, errors={len(persist_errors)}"
    )

    return records_persisted, persist_errors
