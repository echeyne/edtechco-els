"""AgentCore Planning Agent application.

Handles WebSocket connections from the frontend, processes user messages
with a Strands agent, and streams text/plan/done/error frames back.
"""

import json
import logging
import os

from bedrock_agentcore.runtime import BedrockAgentCoreApp
from strands import Agent, tool
from strands.models.bedrock import BedrockModel

from tools.standards_query import get_available_states, get_age_bands, get_indicators
from tools.plan_management import create_plan, update_plan, get_plan, delete_plan

logger = logging.getLogger(__name__)

app = BedrockAgentCoreApp()

# Plan-mutating tools whose results should emit a plan event frame
PLAN_MUTATION_TOOLS = {"createPlan", "updatePlan"}


# ---- Strands @tool wrappers ----
# Each wrapper delegates to the existing tool implementation while providing
# the typed signature and docstring that Strands uses to generate the tool
# spec for the model.


@tool
def getAvailableStates() -> dict:
    """Return the list of distinct US states that have early learning standards data.

    Returns:
        A dict with a ``states`` key containing the list of state records.
    """
    result = get_available_states()
    return {"status": "success", "content": [{"text": json.dumps(result)}]}


@tool
def getAgeBands(state: str) -> dict:
    """Return the available age bands for a given state's early learning standards.

    Args:
        state: The state code to retrieve age bands for.

    Returns:
        A dict with an ``ageBands`` key containing the list of age band records.
    """
    result = get_age_bands(state)
    return {"status": "success", "content": [{"text": json.dumps(result)}]}


@tool
def getIndicators(state: str, age_band: str) -> dict:
    """Return learning indicators for a given state and age band.

    Args:
        state: The state code to filter indicators by.
        age_band: The age band to filter indicators by.

    Returns:
        A dict with an ``indicators`` key containing indicator records with
        code, description, domain, strand, and sub-strand.
    """
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
    """Create a new learning plan for a child and persist it to the database.

    Args:
        user_id: The authenticated user's ID (from session attributes).
        child_name: The child's first name.
        child_age: The child's age or age band.
        state: The state code for the learning standards.
        duration: The plan duration (e.g. "1 week", "4 weeks").
        content: The structured plan content as a JSON object.
        interests: The child's interests (optional).
        concerns: The parent's areas of concern (optional).

    Returns:
        The created plan with its ID and action.
    """
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
    """Update an existing plan's content. Only the plan owner can update it.

    Args:
        plan_id: The ID of the plan to update.
        user_id: The authenticated user's ID (from session attributes).
        content: The updated plan content as a JSON object.

    Returns:
        The updated plan with its ID and action.
    """
    result = update_plan(plan_id=plan_id, user_id=user_id, content=content)
    return {"status": "success", "content": [{"text": json.dumps(result, default=str)}]}


@tool
def getPlan(plan_id: str, user_id: str) -> dict:
    """Retrieve a plan by ID. Only the plan owner can access it.

    Args:
        plan_id: The ID of the plan to retrieve.
        user_id: The authenticated user's ID (from session attributes).

    Returns:
        The plan detail.
    """
    result = get_plan(plan_id=plan_id, user_id=user_id)
    return {"status": "success", "content": [{"text": json.dumps(result, default=str)}]}


@tool
def deletePlan(plan_id: str, user_id: str) -> dict:
    """Delete a plan by ID. Only the plan owner can delete it.

    Args:
        plan_id: The ID of the plan to delete.
        user_id: The authenticated user's ID (from session attributes).

    Returns:
        A success confirmation.
    """
    result = delete_plan(plan_id=plan_id, user_id=user_id)
    return {"status": "success", "content": [{"text": json.dumps(result)}]}


# ---- Load instruction prompt and build the Strands agent ----

TOOLS = [
    getAvailableStates,
    getAgeBands,
    getIndicators,
    createPlan,
    updatePlan,
    getPlan,
    deletePlan,
]


def _load_instruction_prompt() -> str:
    """Load the agent instruction prompt from config or file."""
    config_path = os.path.join(os.path.dirname(__file__), "config.yaml")
    prompt_file = None
    model_id = "anthropic.claude-3-5-sonnet-20241022-v2:0"

    try:
        import yaml

        with open(config_path) as f:
            config = yaml.safe_load(f)
        agent_cfg = config.get("agent", {})
        prompt_file = agent_cfg.get("instruction_prompt_file")
        model_id_cfg = agent_cfg.get("model")
        if model_id_cfg:
            model_id = model_id_cfg
    except Exception:
        logger.warning("Could not load config.yaml, using defaults")

    prompt = ""
    if prompt_file:
        prompt_path = os.path.join(os.path.dirname(__file__), prompt_file)
        try:
            with open(prompt_path) as f:
                prompt = f.read()
        except FileNotFoundError:
            logger.warning("Instruction prompt file not found: %s", prompt_path)

    return prompt, model_id


def _build_agent(system_prompt: str, model_id: str) -> Agent:
    """Create a Strands Agent with Bedrock model and guardrails."""
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


_system_prompt, _model_id = _load_instruction_prompt()
agent = _build_agent(_system_prompt, _model_id)


# ---- WebSocket handler ----

@app.websocket
async def handle_ws(websocket, context):
    """Handle WebSocket connections from the frontend.

    Accepts connections, iterates over incoming JSON messages,
    processes them with the Strands agent, and streams response frames back.

    Message protocol:
      Client -> Agent: { "text": "..." }
      Agent -> Client: { "type": "text", "text": "..." }
                       { "type": "plan", "planId": "...", "action": "created"|"updated" }
                       { "type": "done" }
                       { "type": "error", "message": "..." }
    """
    await websocket.accept()

    # Extract userId and planId from the WebSocket connection's query
    # parameters or custom headers embedded in the presigned URL.
    query_params = dict(websocket.query_params) if hasattr(websocket, "query_params") else {}
    headers = context.request_headers or {}
    user_id = (
        query_params.get("X-UserId")
        or headers.get("X-UserId")
        or headers.get("x-amzn-bedrock-agentcore-custom-x-userid")
        or ""
    )
    plan_id = (
        query_params.get("X-PlanId")
        or headers.get("X-PlanId")
        or headers.get("x-amzn-bedrock-agentcore-custom-x-planid")
    )

    async for message in websocket.iter_json():
        try:
            user_text = message.get("text", "")

            # Inject session context into the user message so the agent
            # (and its tools) can access userId and planId.
            context_prefix = f"[Session context: userId={user_id}"
            if plan_id:
                context_prefix += f", planId={plan_id}"
            context_prefix += "]\n\n"

            enriched_prompt = context_prefix + user_text

            async for event in agent.stream_async(enriched_prompt):
                # Stream text chunks to the client
                if "data" in event:
                    await websocket.send_json({"type": "text", "text": event["data"]})

                # Detect tool results for plan mutation events
                if "current_tool_use" in event:
                    tool_use = event["current_tool_use"]
                    tool_name = tool_use.get("name", "")
                    tool_result = tool_use.get("result")

                    if tool_name in PLAN_MUTATION_TOOLS and tool_result:
                        try:
                            # The tool result content is a list with a text entry
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
                            logger.warning(
                                "Failed to parse plan event from tool result: %s",
                                tool_name,
                            )

            await websocket.send_json({"type": "done"})
        except Exception as e:
            logger.exception("Error processing message")
            try:
                await websocket.send_json({"type": "error", "message": str(e)})
                await websocket.send_json({"type": "done"})
            except Exception:
                break
