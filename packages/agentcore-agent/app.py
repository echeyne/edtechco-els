"""AgentCore Planning Agent application.

Handles WebSocket connections from the frontend, processes user messages
with a Strands agent, and streams text/plan/done/error frames back.

Key design: the Strands agent is lazily initialized on first request,
NOT at module import time. This avoids cold-start failures when the
BedrockModel or config files are unavailable during module loading.
"""

import json
import logging
import os

from bedrock_agentcore.runtime import BedrockAgentCoreApp
from strands import Agent, tool
from strands.models.bedrock import BedrockModel

logger = logging.getLogger(__name__)

app = BedrockAgentCoreApp()

# Plan-mutating tools whose results should emit a plan event frame
PLAN_MUTATION_TOOLS = {"createPlan", "updatePlan"}

# Lazy-initialized agent singleton
_agent: Agent | None = None


# ---- Strands @tool wrappers ----
# Imports are deferred inside each tool body so module-level import
# of app.py does NOT trigger boto3 client creation or DB connections.


@tool
def getAvailableStates() -> dict:
    """Return the list of distinct US states that have early learning standards data."""
    from tools.standards_query import get_available_states
    result = get_available_states()
    return {"status": "success", "content": [{"text": json.dumps(result)}]}


@tool
def getAgeBands(state: str) -> dict:
    """Return the available age bands for a given state's early learning standards."""
    from tools.standards_query import get_age_bands
    result = get_age_bands(state)
    return {"status": "success", "content": [{"text": json.dumps(result)}]}


@tool
def getIndicators(state: str, age_band: str) -> dict:
    """Return learning indicators for a given state and age band."""
    from tools.standards_query import get_indicators
    result = get_indicators(state, age_band)
    return {"status": "success", "content": [{"text": json.dumps(result)}]}


@tool
def createPlan(
    user_id: str,
    child_name: str,
    child_age: str,
    state: str,
    duration: str,
    content: dict,
    interests: str = "",
    concerns: str = "",
) -> dict:
    """Create a new learning plan for a child and persist it to the database."""
    from tools.plan_management import create_plan
    result = create_plan(
        user_id=user_id,
        child_name=child_name,
        child_age=child_age,
        state=state,
        duration=duration,
        content=content,
        interests=interests or None,
        concerns=concerns or None,
    )
    return {"status": "success", "content": [{"text": json.dumps(result, default=str)}]}


@tool
def updatePlan(plan_id: str, user_id: str, content: dict) -> dict:
    """Update an existing plan's content. Only the plan owner can update it."""
    from tools.plan_management import update_plan
    result = update_plan(plan_id=plan_id, user_id=user_id, content=content)
    return {"status": "success", "content": [{"text": json.dumps(result, default=str)}]}


@tool
def getPlan(plan_id: str, user_id: str) -> dict:
    """Retrieve a plan by ID. Only the plan owner can access it."""
    from tools.plan_management import get_plan
    result = get_plan(plan_id=plan_id, user_id=user_id)
    return {"status": "success", "content": [{"text": json.dumps(result, default=str)}]}


@tool
def deletePlan(plan_id: str, user_id: str) -> dict:
    """Delete a plan by ID. Only the plan owner can delete it."""
    from tools.plan_management import delete_plan
    result = delete_plan(plan_id=plan_id, user_id=user_id)
    return {"status": "success", "content": [{"text": json.dumps(result)}]}


# ---- Lazy agent initialization ----

TOOLS = [
    getAvailableStates,
    getAgeBands,
    getIndicators,
    createPlan,
    updatePlan,
    getPlan,
    deletePlan,
]


def _get_agent() -> Agent:
    """Return the Strands agent, creating it on first call."""
    global _agent
    if _agent is not None:
        return _agent

    system_prompt, model_id = _load_instruction_prompt()
    _agent = _build_agent(system_prompt, model_id)
    return _agent


def _load_instruction_prompt() -> tuple[str, str]:
    """Load the agent instruction prompt and model ID from config.yaml."""
    model_id = "us.anthropic.claude-sonnet-4-6"
    prompt = ""

    try:
        import yaml
        config_path = os.path.join(os.path.dirname(__file__), "config.yaml")
        with open(config_path) as f:
            config = yaml.safe_load(f)
        agent_cfg = config.get("agent", {})
        if agent_cfg.get("model"):
            model_id = agent_cfg["model"]
        if agent_cfg.get("instruction_prompt"):
            prompt = agent_cfg["instruction_prompt"]
    except Exception:
        logger.warning("Could not load config.yaml, using defaults", exc_info=True)

    return prompt, model_id


def _build_agent(system_prompt: str, model_id: str) -> Agent:
    """Create a Strands Agent with Bedrock model and optional guardrails."""
    guardrail_id = os.environ.get("GUARDRAIL_ID", "")
    guardrail_version = os.environ.get("GUARDRAIL_VERSION", "")

    model_kwargs = {"model_id": model_id, "max_tokens": 4096}
    if guardrail_id and guardrail_version:
        model_kwargs["guardrail_id"] = guardrail_id
        model_kwargs["guardrail_version"] = guardrail_version

    model = BedrockModel(**model_kwargs)
    return Agent(
        model=model,
        system_prompt=system_prompt,
        tools=TOOLS,
        callback_handler=None,
    )


# ---- WebSocket handler ----

@app.websocket
async def handle_ws(websocket, context):
    """Handle WebSocket connections from the frontend."""
    await websocket.accept()

    query_params = dict(websocket.query_params) if hasattr(websocket, "query_params") else {}
    headers = context.request_headers or {}

    def _hdr(name_lower: str) -> str | None:
        for k, v in headers.items():
            if k.lower() == name_lower:
                return v
        return None

    user_id = (
        query_params.get("X-Amzn-Bedrock-AgentCore-Runtime-Custom-UserId")
        or query_params.get("X-UserId")
        or _hdr("x-amzn-bedrock-agentcore-runtime-custom-userid")
        or _hdr("x-amzn-bedrock-agentcore-custom-x-userid")
        or _hdr("x-userid")
        or ""
    )
    plan_id = (
        query_params.get("X-Amzn-Bedrock-AgentCore-Runtime-Custom-PlanId")
        or query_params.get("X-PlanId")
        or _hdr("x-amzn-bedrock-agentcore-runtime-custom-planid")
        or _hdr("x-amzn-bedrock-agentcore-custom-x-planid")
        or _hdr("x-planid")
    )

    # Lazy-init the agent on first connection
    try:
        agent = _get_agent()
    except Exception as e:
        logger.exception("Failed to initialize agent")
        await websocket.send_json({"type": "error", "message": f"Agent init failed: {e}"})
        await websocket.send_json({"type": "done"})
        return

    async for message in websocket.iter_json():
        try:
            user_text = (message.get("inputText") or message.get("text") or "").strip()

            context_prefix = f"[Session context: userId={user_id}"
            if plan_id:
                context_prefix += f", planId={plan_id}"
            context_prefix += "]\n\n"

            enriched_prompt = context_prefix + user_text

            async for event in agent.stream_async(enriched_prompt):
                if "data" in event:
                    await websocket.send_json({"type": "text", "text": event["data"]})

                if "current_tool_use" in event:
                    tool_use = event["current_tool_use"]
                    tool_name = tool_use.get("name", "")
                    tool_result = tool_use.get("result")

                    if tool_name in PLAN_MUTATION_TOOLS and tool_result:
                        try:
                            result_content = tool_result.get("content", [])
                            for item in result_content:
                                if "text" in item:
                                    parsed = json.loads(item["text"])
                                    if "planId" in parsed and "action" in parsed:
                                        await websocket.send_json({
                                            "type": "plan",
                                            "planId": parsed["planId"],
                                            "action": parsed["action"],
                                        })
                        except (json.JSONDecodeError, KeyError, TypeError, AttributeError):
                            logger.warning("Failed to parse plan event from %s", tool_name)

            await websocket.send_json({"type": "done"})
        except Exception as e:
            logger.exception("Error processing message")
            try:
                await websocket.send_json({"type": "error", "message": str(e)})
                await websocket.send_json({"type": "done"})
            except Exception:
                break


if __name__ == "__main__":
    app.run()
