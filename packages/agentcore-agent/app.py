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

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    force=True,
)
logger = logging.getLogger(__name__)

# Also ensure strands and boto loggers are at INFO so we see model/tool activity
logging.getLogger("strands").setLevel(logging.INFO)
logging.getLogger("bedrock_agentcore").setLevel(logging.INFO)

app = BedrockAgentCoreApp(debug=True)

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
    logger.info("Tool called: getAvailableStates")
    from tools.standards_query import get_available_states
    try:
        result = get_available_states()
        logger.info("getAvailableStates returned %d states", len(result))
        return {"status": "success", "content": [{"text": json.dumps(result)}]}
    except Exception:
        logger.exception("getAvailableStates failed")
        raise


@tool
def getAgeRanges(state: str) -> dict:
    """Return the available age ranges for a given state's early learning standards."""
    logger.info("Tool called: getAgeBands(state=%s)", state)
    from tools.standards_query import get_age_ranges
    try:
        result = get_age_ranges(state)
        logger.info("getAgeBands returned %d bands", len(result))
        return {"status": "success", "content": [{"text": json.dumps(result)}]}
    except Exception:
        logger.exception("getAgeBands failed for state=%s", state)
        raise


@tool
def getIndicators(state: str, age_range: str) -> dict:
    """Return learning indicators for a given state and age range."""
    logger.info("Tool called: getIndicators(state=%s, age_range=%s)", state, age_range)
    from tools.standards_query import get_indicators
    try:
        result = get_indicators(state, age_range)
        logger.info("getIndicators returned %d indicators", len(result))
        return {"status": "success", "content": [{"text": json.dumps(result)}]}
    except Exception:
        logger.exception("getIndicators failed for state=%s, age_range=%s", state, age_range)
        raise


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
    logger.info("Tool called: createPlan(user_id=%s, child=%s, state=%s)", user_id, child_name, state)
    from tools.plan_management import create_plan
    try:
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
        logger.info("createPlan succeeded: planId=%s", result.get("planId"))
        return {"status": "success", "content": [{"text": json.dumps(result, default=str)}]}
    except Exception:
        logger.exception("createPlan failed")
        raise


@tool
def updatePlan(plan_id: str, user_id: str, content: dict) -> dict:
    """Update an existing plan's content. Only the plan owner can update it."""
    logger.info("Tool called: updatePlan(plan_id=%s, user_id=%s)", plan_id, user_id)
    from tools.plan_management import update_plan
    try:
        result = update_plan(plan_id=plan_id, user_id=user_id, content=content)
        logger.info("updatePlan succeeded: planId=%s", result.get("planId"))
        return {"status": "success", "content": [{"text": json.dumps(result, default=str)}]}
    except Exception:
        logger.exception("updatePlan failed for plan_id=%s", plan_id)
        raise


@tool
def getPlan(plan_id: str, user_id: str) -> dict:
    """Retrieve a plan by ID. Only the plan owner can access it."""
    logger.info("Tool called: getPlan(plan_id=%s, user_id=%s)", plan_id, user_id)
    from tools.plan_management import get_plan
    try:
        result = get_plan(plan_id=plan_id, user_id=user_id)
        logger.info("getPlan succeeded for plan_id=%s", plan_id)
        return {"status": "success", "content": [{"text": json.dumps(result, default=str)}]}
    except Exception:
        logger.exception("getPlan failed for plan_id=%s", plan_id)
        raise


@tool
def deletePlan(plan_id: str, user_id: str) -> dict:
    """Delete a plan by ID. Only the plan owner can delete it."""
    logger.info("Tool called: deletePlan(plan_id=%s, user_id=%s)", plan_id, user_id)
    from tools.plan_management import delete_plan
    try:
        result = delete_plan(plan_id=plan_id, user_id=user_id)
        logger.info("deletePlan succeeded for plan_id=%s", plan_id)
        return {"status": "success", "content": [{"text": json.dumps(result)}]}
    except Exception:
        logger.exception("deletePlan failed for plan_id=%s", plan_id)
        raise


# ---- Lazy agent initialization ----

TOOLS = [
    getAvailableStates,
    getAgeRanges,
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

    model_kwargs = {"model_id": model_id, "max_tokens": 16384}
    if guardrail_id and guardrail_version:
        model_kwargs["guardrail_id"] = guardrail_id
        model_kwargs["guardrail_version"] = guardrail_version
        logger.info("Guardrails enabled: id=%s version=%s", guardrail_id, guardrail_version)

    logger.info("Building Strands agent with model=%s", model_id)
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

    # --- Debug: log everything available so we can find the user ID ---
    query_params = dict(websocket.query_params) if hasattr(websocket, "query_params") else {}
    ws_headers = dict(websocket.headers) if hasattr(websocket, "headers") else {}
    ctx_headers = context.request_headers if context and hasattr(context, "request_headers") else {}
    logger.info("WS query_params: %s", query_params)
    logger.info("WS headers: %s", ws_headers)
    logger.info("Context request_headers: %s", ctx_headers)
    logger.info("Context fields: %s", {k: getattr(context, k, None) for k in dir(context) if not k.startswith("_")})

    # Try every possible source for the custom user ID
    user_id = ""
    for source_name, source in [("ctx_headers", ctx_headers or {}), ("ws_headers", ws_headers), ("query_params", query_params)]:
        for key, value in source.items():
            if "userid" in key.lower() and "custom" in key.lower():
                logger.info("Found user_id in %s[%s] = %s", source_name, key, value)
                if not user_id:
                    user_id = value

    if not user_id:
        logger.info("No user_id from headers/query params; will check first message payload")

    plan_id = ""
    for source_name, source in [("ctx_headers", ctx_headers or {}), ("ws_headers", ws_headers), ("query_params", query_params)]:
        for key, value in source.items():
            if "planid" in key.lower() and "custom" in key.lower():
                if not plan_id:
                    plan_id = value

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

            # Accept user_id from the message payload (sent by the frontend)
            # as the primary source, since the AgentCore Runtime proxy strips
            # custom query params before they reach the handler.
            if not user_id:
                msg_uid = message.get("userId", "")
                if msg_uid:
                    user_id = msg_uid
                    logger.info("Got user_id from message payload: %s", user_id)

            if not user_id:
                logger.warning("No user_id found in any source")
                await websocket.send_json({
                    "type": "error",
                    "message": "Not authenticated. Please log in to continue.",
                })
                await websocket.send_json({"type": "done"})
                return

            context_prefix = f"[Session context: userId={user_id}"
            if plan_id:
                context_prefix += f", planId={plan_id}"
            context_prefix += "]\n\n"

            enriched_prompt = context_prefix + user_text
            logger.info("Processing message from user_id=%s, text_length=%d", user_id, len(user_text))

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
