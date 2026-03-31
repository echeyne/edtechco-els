"""AgentCore Planning Agent application.

Handles WebSocket connections from the frontend, processes user messages
with a Strands agent, and streams text/plan/done/error frames back.

Key design:
- The base agent (model + stateless tools) is lazily initialized once.
- Plan-management tools are built per-session with the authenticated user_id
  bound via closure, so the LLM never controls which user's data is accessed.
- user_id is sourced exclusively from the AgentCore Runtime custom headers
  (set by the Planning API after validating the Descope token). It is NOT
  accepted from the WebSocket message payload.
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

logging.getLogger("strands").setLevel(logging.INFO)
logging.getLogger("bedrock_agentcore").setLevel(logging.INFO)

app = BedrockAgentCoreApp(debug=True)

# Plan-mutating tools whose results should emit a plan event frame
PLAN_MUTATION_TOOLS = {"createPlan", "updatePlan"}


# ---- Stateless @tool wrappers (no user context needed) ----

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
    logger.info("Tool called: getAgeRanges(state=%s)", state)
    from tools.standards_query import get_age_ranges
    try:
        result = get_age_ranges(state)
        logger.info("getAgeRanges returned %d ranges", len(result))
        return {"status": "success", "content": [{"text": json.dumps(result)}]}
    except Exception:
        logger.exception("getAgeRanges failed for state=%s", state)
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


STATELESS_TOOLS = [getAvailableStates, getAgeRanges, getIndicators]


# ---- Per-session tool factory ----
# user_id is bound from the authenticated session — the LLM never supplies it.

def build_session_tools(user_id: str) -> list:
    """Return plan-management tools with user_id bound from the authenticated session."""

    @tool
    def createPlan(
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
    def updatePlan(plan_id: str, content: dict) -> dict:
        """Update an existing plan's content. Only operates on plans owned by the current user."""
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
    def getPlan(plan_id: str) -> dict:
        """Retrieve a plan by ID. Only returns plans owned by the current user."""
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
    def deletePlan(plan_id: str) -> dict:
        """Delete a plan by ID. Only deletes plans owned by the current user."""
        logger.info("Tool called: deletePlan(plan_id=%s, user_id=%s)", plan_id, user_id)
        from tools.plan_management import delete_plan
        try:
            result = delete_plan(plan_id=plan_id, user_id=user_id)
            logger.info("deletePlan succeeded for plan_id=%s", plan_id)
            return {"status": "success", "content": [{"text": json.dumps(result)}]}
        except Exception:
            logger.exception("deletePlan failed for plan_id=%s", plan_id)
            raise

    return [createPlan, updatePlan, getPlan, deletePlan]


# ---- Agent initialization ----

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


def _build_model() -> BedrockModel:
    """Create the BedrockModel (shared across sessions)."""
    system_prompt, model_id = _load_instruction_prompt()

    guardrail_id = os.environ.get("GUARDRAIL_ID", "")
    guardrail_version = os.environ.get("GUARDRAIL_VERSION", "")

    model_kwargs: dict = {"model_id": model_id, "max_tokens": 16384}
    if guardrail_id and guardrail_version:
        model_kwargs["guardrail_id"] = guardrail_id
        model_kwargs["guardrail_version"] = guardrail_version
        logger.info("Guardrails enabled: id=%s version=%s", guardrail_id, guardrail_version)

    logger.info("Building BedrockModel with model=%s", model_id)
    return BedrockModel(**model_kwargs), system_prompt


# Lazy-initialized shared model and system prompt
_model: BedrockModel | None = None
_system_prompt: str = ""


def _get_model() -> tuple[BedrockModel, str]:
    global _model, _system_prompt
    if _model is None:
        _model, _system_prompt = _build_model()
    return _model, _system_prompt


def _build_session_agent(user_id: str) -> Agent:
    """Build a per-session agent with user_id bound into plan tools."""
    model, system_prompt = _get_model()
    tools = STATELESS_TOOLS + build_session_tools(user_id)
    logger.info("Building session agent for user_id=%s", user_id)
    return Agent(
        model=model,
        system_prompt=system_prompt,
        tools=tools,
        callback_handler=None,
    )


# ---- WebSocket handler ----

def _extract_user_id(websocket, context) -> str:
    """Validate the Descope JWT and return the user ID.

    The Planning API forwards the user's original Descope token via the
    custom AgentCore query param X-Amzn-Bedrock-AgentCore-Runtime-Custom-Token.
    We validate it here with the Descope SDK — the token is cryptographically
    signed by Descope and cannot be forged.
    """
    import os
    query_params = dict(websocket.query_params) if hasattr(websocket, "query_params") else {}
    ws_headers = dict(websocket.headers) if hasattr(websocket, "headers") else {}
    ctx_headers = context.request_headers if context and hasattr(context, "request_headers") else {}

    # Primary: custom query param forwarded by the Planning API Lambda
    token = query_params.get("X-Amzn-Bedrock-AgentCore-Runtime-Custom-Token", "").strip()

    # Fallback: Authorization header (for local dev / direct invocation)
    if not token:
        auth_header = (ctx_headers or {}).get("authorization") or ws_headers.get("authorization") or ""
        if auth_header.lower().startswith("bearer "):
            token = auth_header[7:].strip()

    if not token:
        logger.warning("No token found in custom query param or Authorization header")
        return ""

    project_id = os.environ.get("DESCOPE_PROJECT_ID", "")
    if not project_id:
        logger.error("DESCOPE_PROJECT_ID not set — cannot validate token")
        return ""

    try:
        import descope
        client = descope.DescopeClient(project_id=project_id)
        claims = client.validate_session(session_token=token)
        user_id = claims.get("sub") or claims.get("userId") or ""
        if not user_id:
            logger.warning("Descope token valid but no sub/userId claim found")
        else:
            logger.info("Descope token validated, user_id=%s", user_id)
        return user_id
    except Exception:
        logger.exception("Descope token validation failed")
        return ""


def _extract_plan_id(websocket, context) -> str:
    """Extract plan_id from AgentCore Runtime custom headers.

    plan_id is not sensitive — it's just a session hint. Ownership is always
    enforced in the DB query (WHERE id = :id AND user_id = :user_id).
    """
    query_params = dict(websocket.query_params) if hasattr(websocket, "query_params") else {}
    ws_headers = dict(websocket.headers) if hasattr(websocket, "headers") else {}
    ctx_headers = context.request_headers if context and hasattr(context, "request_headers") else {}

    for source in [ctx_headers or {}, ws_headers, query_params]:
        for key, value in source.items():
            if "planid" in key.lower() and "custom" in key.lower():
                return value

    return ""


@app.websocket
async def handle_ws(websocket, context):
    """Handle WebSocket connections from the frontend."""
    await websocket.accept()

    user_id = _extract_user_id(websocket, context)

    if not user_id:
        logger.warning("Rejected WebSocket connection: no authenticated user_id in headers")
        await websocket.send_json({
            "type": "error",
            "message": "Not authenticated. Please log in to continue.",
        })
        await websocket.send_json({"type": "done"})
        return

    plan_id = _extract_plan_id(websocket, context)

    logger.info("Authenticated WebSocket session: user_id=%s, plan_id=%s", user_id, plan_id or "(none)")

    try:
        agent = _build_session_agent(user_id)
    except Exception as e:
        logger.exception("Failed to initialize agent for user_id=%s", user_id)
        await websocket.send_json({"type": "error", "message": f"Agent init failed: {e}"})
        await websocket.send_json({"type": "done"})
        return

    async for message in websocket.iter_json():
        try:
            user_text = (message.get("inputText") or message.get("text") or "").strip()

            if not user_text:
                continue

            context_prefix = f"[Session context: planId={plan_id}]\n\n" if plan_id else ""
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
            logger.exception("Error processing message for user_id=%s", user_id)
            try:
                await websocket.send_json({"type": "error", "message": str(e)})
                await websocket.send_json({"type": "done"})
            except Exception:
                break


if __name__ == "__main__":
    app.run()
