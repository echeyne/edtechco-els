"""Shared RDS Data API helper for AgentCore agent tools."""

import os
from typing import Any

import boto3

_rds_client = None


def _get_client():
    """Return the RDS Data API client, creating it lazily on first call."""
    global _rds_client
    if _rds_client is None:
        _rds_client = boto3.client("rds-data")
    return _rds_client


def _get_db_params() -> dict[str, str]:
    cluster_arn = os.environ.get("DB_CLUSTER_ARN", "")
    secret_arn = os.environ.get("DB_SECRET_ARN", "")
    database = os.environ.get("DB_NAME", "els_pipeline")

    if not cluster_arn or not secret_arn:
        raise RuntimeError("DB_CLUSTER_ARN and DB_SECRET_ARN must be set")

    return {
        "resourceArn": cluster_arn,
        "secretArn": secret_arn,
        "database": database,
    }


def execute(sql: str, parameters: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    """Execute a SQL statement via the RDS Data API and return rows as dicts."""
    db = _get_db_params()
    params: dict[str, Any] = {
        **db,
        "sql": sql,
        "includeResultMetadata": True,
    }
    if parameters:
        params["parameters"] = parameters

    response = _get_client().execute_statement(**params)

    columns = [col["name"] for col in response.get("columnMetadata", [])]
    rows: list[dict[str, Any]] = []
    for record in response.get("records", []):
        row: dict[str, Any] = {}
        for i, field in enumerate(record):
            if "stringValue" in field:
                row[columns[i]] = field["stringValue"]
            elif "longValue" in field:
                row[columns[i]] = field["longValue"]
            elif "doubleValue" in field:
                row[columns[i]] = field["doubleValue"]
            elif "booleanValue" in field:
                row[columns[i]] = field["booleanValue"]
            elif "isNull" in field and field["isNull"]:
                row[columns[i]] = None
            else:
                row[columns[i]] = None
        rows.append(row)
    return rows


def execute_raw(sql: str, parameters: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Execute a SQL statement and return the raw RDS Data API response."""
    db = _get_db_params()
    params: dict[str, Any] = {
        **db,
        "sql": sql,
    }
    if parameters:
        params["parameters"] = parameters

    return _get_client().execute_statement(**params)
