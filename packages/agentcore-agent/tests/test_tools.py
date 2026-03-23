"""Property-based tests for AgentCore agent tools.

Uses hypothesis to verify correctness properties of the planning tools.
"""

# Feature: agentcore-planning-agent, Property 7: Plan management tool round-trip

import json
from unittest.mock import MagicMock, patch

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from tools.plan_management import create_plan, get_plan

# ---------------------------------------------------------------------------
# Hypothesis strategies for valid plan inputs
# ---------------------------------------------------------------------------

# Non-empty printable strings (no null bytes) for text fields
_non_empty_text = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N", "P", "Z"), blacklist_characters="\x00"),
    min_size=1,
    max_size=50,
).filter(lambda s: s.strip())

_user_id = _non_empty_text
_child_name = _non_empty_text
_child_age = st.sampled_from(["0-1", "1-2", "2-3", "3-4", "4-5", "5-6"])
_state = st.sampled_from(["OH", "CA", "TX", "NY", "FL", "IL", "PA", "WA"])
_duration = st.sampled_from(["1 week", "2 weeks", "1 month", "3 months", "6 months"])

_content = st.fixed_dictionaries(
    {
        "sections": st.lists(
            st.fixed_dictionaries(
                {
                    "title": _non_empty_text,
                    "body": _non_empty_text,
                }
            ),
            min_size=1,
            max_size=3,
        ),
        "summary": _non_empty_text,
    }
)

# Column order returned by "SELECT * FROM plans"
PLAN_COLUMNS = [
    "id",
    "user_id",
    "child_name",
    "child_age",
    "state",
    "interests",
    "concerns",
    "duration",
    "content",
    "status",
    "created_at",
    "updated_at",
]

COLUMN_METADATA = [{"name": col} for col in PLAN_COLUMNS]


def _make_rds_record(
    plan_id: str,
    user_id: str,
    child_name: str,
    child_age: str,
    state: str,
    interests: str | None,
    concerns: str | None,
    duration: str,
    content: dict,
    status: str = "active",
    created_at: str = "2025-01-01T00:00:00Z",
    updated_at: str = "2025-01-01T00:00:00Z",
) -> list[dict]:
    """Build a single RDS Data API record (list of field dicts) for a plan row."""
    def _field(value: str | None) -> dict:
        if value is None:
            return {"isNull": True}
        return {"stringValue": value}

    return [
        _field(plan_id),
        _field(user_id),
        _field(child_name),
        _field(child_age),
        _field(state),
        _field(interests),
        _field(concerns),
        _field(duration),
        _field(json.dumps(content)),
        _field(status),
        _field(created_at),
        _field(updated_at),
    ]


# ---------------------------------------------------------------------------
# Property 7: Plan management tool round-trip
# ---------------------------------------------------------------------------


class TestPlanManagementRoundTrip:
    """**Validates: Requirements 4.2**

    For any valid plan input, creating a plan via create_plan and then
    retrieving it via get_plan with the same planId and userId SHALL
    return a plan with matching field values.
    """

    @given(
        user_id=_user_id,
        child_name=_child_name,
        child_age=_child_age,
        state=_state,
        duration=_duration,
        content=_content,
    )
    @settings(max_examples=20)
    def test_create_then_get_returns_matching_fields(
        self,
        user_id: str,
        child_name: str,
        child_age: str,
        state: str,
        duration: str,
        content: dict,
    ) -> None:
        """Create a plan and retrieve it; all fields must match."""
        fake_plan_id = "plan-00000000-0000-0000-0000-000000000001"

        # Build the RDS record that the INSERT RETURNING * would produce
        insert_record = _make_rds_record(
            plan_id=fake_plan_id,
            user_id=user_id,
            child_name=child_name,
            child_age=child_age,
            state=state,
            interests=None,
            concerns=None,
            duration=duration,
            content=content,
        )

        # The same record is returned by the SELECT in get_plan
        select_record = list(insert_record)  # shallow copy

        mock_client = MagicMock()

        # First call: INSERT (create_plan), second call: SELECT (get_plan)
        mock_client.execute_statement.side_effect = [
            {
                "columnMetadata": COLUMN_METADATA,
                "records": [insert_record],
            },
            {
                "columnMetadata": COLUMN_METADATA,
                "records": [select_record],
            },
        ]

        with patch("tools.db._rds_client", mock_client):
            create_result = create_plan(
                user_id=user_id,
                child_name=child_name,
                child_age=child_age,
                state=state,
                duration=duration,
                content=content,
            )

            get_result = get_plan(
                plan_id=create_result["planId"],
                user_id=user_id,
            )

        created_plan = create_result["plan"]
        retrieved_plan = get_result["plan"]

        # Verify round-trip field equality
        assert created_plan["id"] == retrieved_plan["id"]
        assert created_plan["childName"] == retrieved_plan["childName"]
        assert created_plan["childAge"] == retrieved_plan["childAge"]
        assert created_plan["state"] == retrieved_plan["state"]
        assert created_plan["duration"] == retrieved_plan["duration"]
        assert created_plan["content"] == retrieved_plan["content"]
        assert created_plan["interests"] == retrieved_plan["interests"]
        assert created_plan["concerns"] == retrieved_plan["concerns"]
        assert created_plan["status"] == retrieved_plan["status"]

        # Verify the created plan matches the original inputs
        assert created_plan["childName"] == child_name
        assert created_plan["childAge"] == child_age
        assert created_plan["state"] == state
        assert created_plan["duration"] == duration
        assert created_plan["content"] == content

        # Verify create_plan returns correct action metadata
        assert create_result["action"] == "created"
        assert create_result["planId"] == fake_plan_id


# Feature: agentcore-planning-agent, Property 8: Plan mutation events appear in WebSocket stream

from tools.plan_management import update_plan


class TestPlanMutationEvents:
    """**Validates: Requirements 4.4**

    For any plan creation or update performed by the AgentCore agent's tools,
    the returned result SHALL contain the correct ``planId`` and ``action``
    (``"created"`` for create_plan, ``"updated"`` for update_plan) so that
    the WebSocket handler can emit the corresponding plan event frame.
    """

    @given(
        user_id=_user_id,
        child_name=_child_name,
        child_age=_child_age,
        state=_state,
        duration=_duration,
        content=_content,
    )
    @settings(max_examples=20)
    def test_create_plan_returns_created_action_with_plan_id(
        self,
        user_id: str,
        child_name: str,
        child_age: str,
        state: str,
        duration: str,
        content: dict,
    ) -> None:
        """create_plan result contains action='created' and a non-empty planId."""
        fake_plan_id = "plan-aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"

        insert_record = _make_rds_record(
            plan_id=fake_plan_id,
            user_id=user_id,
            child_name=child_name,
            child_age=child_age,
            state=state,
            interests=None,
            concerns=None,
            duration=duration,
            content=content,
        )

        mock_client = MagicMock()
        mock_client.execute_statement.return_value = {
            "columnMetadata": COLUMN_METADATA,
            "records": [insert_record],
        }

        with patch("tools.db._rds_client", mock_client):
            result = create_plan(
                user_id=user_id,
                child_name=child_name,
                child_age=child_age,
                state=state,
                duration=duration,
                content=content,
            )

        assert result["action"] == "created"
        assert result["planId"] == fake_plan_id
        assert result["planId"]  # non-empty

    @given(
        plan_id=_non_empty_text,
        user_id=_user_id,
        content=_content,
    )
    @settings(max_examples=20)
    def test_update_plan_returns_updated_action_with_correct_plan_id(
        self,
        plan_id: str,
        user_id: str,
        content: dict,
    ) -> None:
        """update_plan result contains action='updated' and the correct planId."""
        update_record = _make_rds_record(
            plan_id=plan_id,
            user_id=user_id,
            child_name="Test Child",
            child_age="3-4",
            state="OH",
            interests=None,
            concerns=None,
            duration="1 month",
            content=content,
        )

        mock_client = MagicMock()
        mock_client.execute_statement.return_value = {
            "columnMetadata": COLUMN_METADATA,
            "records": [update_record],
        }

        with patch("tools.db._rds_client", mock_client):
            result = update_plan(
                plan_id=plan_id,
                user_id=user_id,
                content=content,
            )

        assert result["action"] == "updated"
        assert result["planId"] == plan_id


# ---------------------------------------------------------------------------
# Unit tests for AgentCore agent tools (Task 3.7)
# ---------------------------------------------------------------------------

import os
import re

from tools.standards_query import get_available_states, get_age_ranges, get_indicators


class TestToolUnitTests:
    """Unit tests for AgentCore agent tools.

    Validates: Requirements 3.4, 4.1, 4.2
    """

    def test_get_available_states_returns_state_list(self) -> None:
        """get_available_states returns a list of dicts with state codes."""
        mock_client = MagicMock()
        mock_client.execute_statement.return_value = {
            "columnMetadata": [{"name": "state"}],
            "records": [
                [{"stringValue": "CA"}],
                [{"stringValue": "OH"}],
                [{"stringValue": "TX"}],
            ],
        }

        with patch("tools.db._rds_client", mock_client):
            result = get_available_states()

        assert result == [
            {"state": "CA"},
            {"state": "OH"},
            {"state": "TX"},
        ]

    def test_get_age_bands_invalid_state_returns_empty(self) -> None:
        """get_age_bands with an invalid state returns an empty list."""
        mock_client = MagicMock()
        mock_client.execute_statement.return_value = {
            "columnMetadata": [{"name": "age_band"}],
            "records": [],
        }

        with patch("tools.db._rds_client", mock_client):
            result = get_age_ranges("INVALID")

        assert result == []

    def test_get_indicators_returns_matching_indicators(self) -> None:
        """get_indicators returns indicator dicts with expected keys."""
        mock_client = MagicMock()
        mock_client.execute_statement.return_value = {
            "columnMetadata": [
                {"name": "code"},
                {"name": "description"},
                {"name": "domain_name"},
                {"name": "strand_name"},
                {"name": "sub_strand_name"},
                {"name": "age_band"},
            ],
            "records": [
                [
                    {"stringValue": "SE.1.1"},
                    {"stringValue": "Shows awareness of self"},
                    {"stringValue": "Social-Emotional"},
                    {"stringValue": "Self-Awareness"},
                    {"stringValue": "Identity"},
                    {"stringValue": "3-4"},
                ],
                [
                    {"stringValue": "SE.1.2"},
                    {"stringValue": "Expresses emotions"},
                    {"stringValue": "Social-Emotional"},
                    {"stringValue": "Self-Awareness"},
                    {"stringValue": "Emotional Literacy"},
                    {"stringValue": "3-4"},
                ],
            ],
        }

        with patch("tools.db._rds_client", mock_client):
            result = get_indicators("OH", "3-4")

        assert len(result) == 2
        assert result[0] == {
            "code": "SE.1.1",
            "description": "Shows awareness of self",
            "domain_name": "Social-Emotional",
            "strand_name": "Self-Awareness",
            "sub_strand_name": "Identity",
            "age_band": "3-4",
        }
        assert result[1] == {
            "code": "SE.1.2",
            "description": "Expresses emotions",
            "domain_name": "Social-Emotional",
            "strand_name": "Self-Awareness",
            "sub_strand_name": "Emotional Literacy",
            "age_band": "3-4",
        }

    def test_create_plan_missing_required_fields_raises(self) -> None:
        """create_plan with empty required fields raises ValueError."""
        with pytest.raises(ValueError):
            create_plan(
                user_id="",
                child_name="",
                child_age="",
                state="",
                duration="",
                content={},
            )

    def test_agent_instruction_prompt_matches_expected(self) -> None:
        """Agent config references instruction prompt that starts with expected text."""
        config_path = os.path.join(
            os.path.dirname(__file__), "..", "config.yaml"
        )
        with open(config_path) as f:
            config_text = f.read()

        # Extract instruction_prompt_file from YAML without pyyaml
        match = re.search(r"instruction_prompt_file:\s*(.+)", config_text)
        assert match, "instruction_prompt_file not found in config.yaml"
        prompt_rel_path = match.group(1).strip()

        # Resolve relative to config.yaml's directory
        prompt_path = os.path.normpath(
            os.path.join(os.path.dirname(config_path), prompt_rel_path)
        )

        with open(prompt_path) as f:
            prompt_text = f.read()

        expected_first_line = (
            "You are a friendly, supportive early learning planning assistant"
        )
        assert prompt_text.startswith(expected_first_line)
