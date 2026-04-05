"""StandardsQuery tools for querying early learning standards from RDS.

Uses the RDS Data API (boto3 execute_statement) to query the standards
database. SQL queries are ported from packages/planning-api/src/action-group/handler.ts.
"""

import logging
from typing import Any

from tools.db import execute

logger = logging.getLogger(__name__)


def get_available_states() -> list[str]:
    """Return distinct states from the documents table."""
    logger.info("Fetching available states")
    sql = "SELECT DISTINCT state FROM documents ORDER BY state"
    rows = execute(sql)
    logger.info("Found %d states", len(rows))
    return [row["state"] for row in rows]


def get_age_ranges(state: str) -> list[str]:
    """Return distinct age ranges for a given state."""
    logger.info("Fetching age ranges for state=%s", state)
    sql = (
        "SELECT DISTINCT doc.age_band as age_range "
        "FROM documents doc "
        "WHERE doc.state = :state "
        "ORDER BY doc.age_band"
    )
    parameters = [{"name": "state", "value": {"stringValue": state}}]
    rows = execute(sql, parameters)
    logger.info("Found %d age ranges for state=%s", len(rows), state)
    return [row["age_range"] for row in rows]


def get_indicators(state: str, age_range: str) -> list[dict[str, Any]]:
    """Return indicators for a given state and age band."""
    logger.info("Fetching indicators for state=%s, age_range=%s", state, age_range)
    sql = (
        "SELECT i.code, "
        "       i.description, "
        "       d.name AS domain_name, "
        "       s.name AS strand_name, "
        "       ss.name AS sub_strand_name, "
        "       doc.age_band as age_range "
        "FROM indicators i "
        "JOIN sub_strands ss ON i.sub_strand_id = ss.id "
        "JOIN strands s ON ss.strand_id = s.id "
        "JOIN domains d ON s.domain_id = d.id "
        "JOIN documents doc ON d.document_id = doc.id "
        "WHERE doc.state = :state AND doc.age_band = :age_range "
        "ORDER BY d.name, s.name, i.code"
    )
    parameters = [
        {"name": "state", "value": {"stringValue": state}},
        {"name": "age_range", "value": {"stringValue": age_range}},
    ]
    return execute(sql, parameters)