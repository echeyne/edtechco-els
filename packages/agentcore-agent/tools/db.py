"""Shared RDS Data API helper for AgentCore agent tools."""

import os
from typing import Any

import boto3

_rds_client = boto3.client("rds-data")

DB_CLUSTER_ARN = os.environ.get("DB_CLUSTER_ARN", "")
DB_SECRET_ARN = os.environ.get("DB_SECRET_ARN", "")
DB_NAME = os.environ.get("DB_NAME", "")


def execute(sql: str, parameters: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    """Execute a SQL statement via the RDS Data API and return rows as dicts."""
    params: dict[str, Any] = {
        "resourceArn": DB_CLUSTER_ARN,
        "secretArn": DB_SECRET_ARN,
        "database": DB_NAME,
        "sql": sql,
        "includeResultMetadata": True,
    }
    if parameters:
        params["parameters"] = parameters

    response = _rds_client.execute_statement(**params)

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
    """Execute a SQL statement and return the raw RDS Data API response.

    Useful for DELETE/UPDATE statements where ``numberOfRecordsUpdated`` is needed.
    """
    params: dict[str, Any] = {
        "resourceArn": DB_CLUSTER_ARN,
        "secretArn": DB_SECRET_ARN,
        "database": DB_NAME,
        "sql": sql,
    }
    if parameters:
        params["parameters"] = parameters

    return _rds_client.execute_statement(**params)
