"""StandardsQuery tools for querying early learning standards from RDS.

Uses the RDS Data API (boto3 execute_statement) to query the standards
database. SQL queries are ported from packages/planning-api/src/action-group/handler.ts.
"""

from typing import Any

from tools.db import execute


def get_available_states() -> list[dict[str, str]]:
    """Return distinct states from the documents table.

    Returns:
        List of dicts, each with a ``state`` key.
    """
    sql = "SELECT DISTINCT state FROM documents ORDER BY state"
    return execute(sql)


def get_age_bands(state: str) -> list[dict[str, str]]:
    """Return distinct age bands for a given state.

    Args:
        state: The state code to filter by.

    Returns:
        List of dicts, each with an ``age_band`` key.
    """
    sql = (
        "SELECT DISTINCT doc.age_band "
        "FROM indicators i "
        "JOIN sub_strands ss ON i.sub_strand_id = ss.id "
        "JOIN strands s ON ss.strand_id = s.id "
        "JOIN domains d ON s.domain_id = d.id "
        "JOIN documents doc ON d.document_id = doc.id "
        "WHERE doc.state = :state "
        "ORDER BY doc.age_band"
    )
    parameters = [{"name": "state", "value": {"stringValue": state}}]
    return execute(sql, parameters)


def get_indicators(state: str, age_band: str) -> list[dict[str, Any]]:
    """Return indicators for a given state and age band.

    Args:
        state: The state code to filter by.
        age_band: The age band to filter by.

    Returns:
        List of dicts with keys: ``code``, ``description``, ``domain_name``,
        ``strand_name``, ``sub_strand_name``, ``age_band``.
    """
    sql = (
        "SELECT i.code, "
        "       i.description, "
        "       d.name AS domain_name, "
        "       s.name AS strand_name, "
        "       ss.name AS sub_strand_name, "
        "       doc.age_band "
        "FROM indicators i "
        "JOIN sub_strands ss ON i.sub_strand_id = ss.id "
        "JOIN strands s ON ss.strand_id = s.id "
        "JOIN domains d ON s.domain_id = d.id "
        "JOIN documents doc ON d.document_id = doc.id "
        "WHERE doc.state = :state AND doc.age_band = :age_band "
        "ORDER BY d.name, s.name, i.code"
    )
    parameters = [
        {"name": "state", "value": {"stringValue": state}},
        {"name": "age_band", "value": {"stringValue": age_band}},
    ]
    return execute(sql, parameters)
