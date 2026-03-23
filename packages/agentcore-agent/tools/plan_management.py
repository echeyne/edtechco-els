"""PlanManagement tools for managing plans in RDS.

Uses the RDS Data API (boto3 execute_statement) to manage plans.
SQL queries are ported from packages/planning-api/src/db/plans.ts
and packages/planning-api/src/action-group/handler.ts.
"""

import json
import logging
from typing import Any

from tools.db import execute, execute_raw

logger = logging.getLogger(__name__)


def _parse_plan_row(row: dict[str, Any]) -> dict[str, Any]:
    """Convert a raw plan row into a plan detail dict.

    Parses the ``content`` field from JSON string to dict if needed,
    and converts snake_case column names to camelCase for the API response.
    """
    content = row.get("content")
    if isinstance(content, str):
        content = json.loads(content)

    return {
        "id": row.get("id"),
        "childName": row.get("child_name"),
        "childAge": row.get("child_age"),
        "state": row.get("state"),
        "interests": row.get("interests"),
        "concerns": row.get("concerns"),
        "duration": row.get("duration"),
        "content": content,
        "status": row.get("status"),
        "createdAt": row.get("created_at"),
        "updatedAt": row.get("updated_at"),
    }


def create_plan(
    user_id: str,
    child_name: str,
    child_age: str,
    state: str,
    duration: str,
    content: dict[str, Any],
    interests: str | None = None,
    concerns: str | None = None,
) -> dict[str, Any]:
    """Insert a new plan and return the created record.

    Args:
        user_id: The owning user's ID.
        child_name: The child's name.
        child_age: The child's age.
        state: The state code.
        duration: The plan duration.
        content: The plan content as a dict (stored as JSONB).
        interests: Optional child interests.
        concerns: Optional parent concerns.

    Returns:
        Dict with ``plan`` (plan detail), ``planId``, and ``action`` ("created")
        for WebSocket plan event emission.

    Raises:
        ValueError: If any required field is missing or empty.
    """
    if not user_id:
        raise ValueError("user_id is required")
    if not child_name:
        raise ValueError("child_name is required")
    if not child_age:
        raise ValueError("child_age is required")
    if not state:
        raise ValueError("state is required")
    if not duration:
        raise ValueError("duration is required")
    if not content:
        raise ValueError("content is required")

    logger.info("Creating plan for user_id=%s, child=%s, state=%s", user_id, child_name, state)
    sql = (
        "INSERT INTO plans (user_id, child_name, child_age, state, interests, concerns, duration, content) "
        "VALUES (:user_id, :child_name, :child_age, :state, :interests, :concerns, :duration, :content) "
        "RETURNING *"
    )
    parameters = [
        {"name": "user_id", "value": {"stringValue": user_id}},
        {"name": "child_name", "value": {"stringValue": child_name}},
        {"name": "child_age", "value": {"stringValue": child_age}},
        {"name": "state", "value": {"stringValue": state}},
        {"name": "interests", "value": {"stringValue": interests} if interests else {"isNull": True}},
        {"name": "concerns", "value": {"stringValue": concerns} if concerns else {"isNull": True}},
        {"name": "duration", "value": {"stringValue": duration}},
        {"name": "content", "typeHint": "JSON", "value": {"stringValue": json.dumps(content)}},
    ]

    rows = execute(sql, parameters)
    if not rows:
        raise RuntimeError("Failed to create plan")

    plan = _parse_plan_row(rows[0])
    logger.info("Plan created: planId=%s", plan["id"])
    return {"plan": plan, "planId": plan["id"], "action": "created"}


def update_plan(
    plan_id: str,
    user_id: str,
    content: dict[str, Any],
) -> dict[str, Any]:
    """Update a plan's content and return the updated record."""
    logger.info("Updating plan=%s for user_id=%s", plan_id, user_id)
    sql = (
        "UPDATE plans SET content = :content, updated_at = NOW() "
        "WHERE id = :id AND user_id = :user_id "
        "RETURNING *"
    )
    parameters = [
        {"name": "content", "typeHint": "JSON", "value": {"stringValue": json.dumps(content)}},
        {"name": "id", "value": {"stringValue": plan_id}},
        {"name": "user_id", "value": {"stringValue": user_id}},
    ]

    rows = execute(sql, parameters)
    if not rows:
        raise ValueError("Plan not found or not owned by user")

    plan = _parse_plan_row(rows[0])
    logger.info("Plan updated: planId=%s", plan["id"])
    return {"plan": plan, "planId": plan["id"], "action": "updated"}


def get_plan(plan_id: str, user_id: str) -> dict[str, Any]:
    """Fetch a single plan by ID, scoped to the owning user."""
    logger.info("Fetching plan=%s for user_id=%s", plan_id, user_id)
    sql = "SELECT * FROM plans WHERE id = :id AND user_id = :user_id"
    parameters = [
        {"name": "id", "value": {"stringValue": plan_id}},
        {"name": "user_id", "value": {"stringValue": user_id}},
    ]

    rows = execute(sql, parameters)
    if not rows:
        raise ValueError("Plan not found or not owned by user")

    return {"plan": _parse_plan_row(rows[0])}


def delete_plan(plan_id: str, user_id: str) -> dict[str, Any]:
    """Delete a plan by ID, scoped to the owning user."""
    logger.info("Deleting plan=%s for user_id=%s", plan_id, user_id)
    sql = "DELETE FROM plans WHERE id = :id AND user_id = :user_id"
    parameters = [
        {"name": "id", "value": {"stringValue": plan_id}},
        {"name": "user_id", "value": {"stringValue": user_id}},
    ]

    response = execute_raw(sql, parameters)

    if response.get("numberOfRecordsUpdated", 0) == 0:
        raise ValueError("Plan not found or not owned by user")

    return {"success": True}
