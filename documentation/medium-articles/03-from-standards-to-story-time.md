# From Standards to Story Time: Building an AI Planning Assistant Grounded in Real Early Learning Data

_How a conversational agent turns state-specific learning standards into personalized activity plans for families_

---

Early learning standards documents are written for policymakers and program administrators. They describe what children should know and be able to do. What they don't do is tell a parent sitting at the kitchen table what to actually _do_ on a Tuesday evening.

The gap between a published standard and a family's lived experience is real, and it's wide. The Foundation for Child Development's PreK-3rd research found that parent involvement is "currently stressed more in preschool than elementary school" and that when parents "are not given opportunities to engage later, their advocacy and involvement may wane" ([FCD PreK-3rd Policy Briefs](https://www.fcd-us.org/prek-3rd-policy-briefs/)). Making standards actionable for families — not just for educators — is part of bridging that engagement gap. A four-year-old's parent in Arizona has access to a 217-page PDF of the Arizona Early Learning Standards if they know to look for it. Very few do. And even the ones who find it are reading curriculum policy, not a practical guide for supporting their child's development at home.

Closing that gap is the purpose of the planning assistant I built as part of the EdTech Co. platform. This article walks through how it works — architecturally, technically, and in terms of the deliberate design choices that make it both trustworthy and useful.

---

## The Design Constraint That Changed Everything

When I started designing the planning assistant, I made one rule that shaped every subsequent decision:

**The assistant may only reference learning indicators that actually exist in the database for the child's state and age group. No exceptions.**

This sounds obvious. It isn't.

Large language models are extraordinarily good at generating plausible-sounding educational content. Ji et al.'s comprehensive survey of hallucination in natural language generation established that deep learning-based text generation is systematically "prone to hallucinating unintended text" — generating content that is fluent and coherent but factually unfounded ([Ji et al., 2023, "Survey of Hallucination in Natural Language Generation," _ACM Computing Surveys_](https://dl.acm.org/doi/10.1145/3571730)). Ask a general-purpose LLM to create a learning plan for a four-year-old and it will produce something coherent, warm, and developmental-sounding. It will invent indicator codes. It will describe standards that don't exist. It will give activities a veneer of official grounding that isn't real.

For a system used by parents and educators to support real children's development, that's not good enough. The activities in a plan need to be traceable to actual state standards — not because traceability is an engineering goal, but because it's what makes the plan legitimate and useful to practitioners. An educator who sees _"Activity aligned to indicator ATL.1.1.1: The child demonstrates motivation, independence, and responsibility while participating in a range of activities and routines."_ can go verify that indicator, connect it to their program's curriculum, and communicate it to families in the language of their state's official framework.

A hallucinated indicator code can't do that.

---

## Architecture: A Guided Conversational Agent

The planning assistant is built on AWS Bedrock AgentCore — Amazon's runtime for stateful, tool-calling conversational agents. The agent is powered by Claude Sonnet, guided by a structured system prompt that encodes an 11-step workflow, and given access to two sets of tools: one for querying the standards database, and one for managing plans.

```
Parent (WebSocket)
  → planning-api (TypeScript/Hono)
    → AgentCore Runtime
      → agentcore-agent (Python + Strands framework)
        → StandardsQuery tools (getAvailableStates, getAgeRanges, getIndicators)
        → PlanManagement tools (createPlan, updatePlan, getPlan, deletePlan)
          → Aurora PostgreSQL
```

The conversation happens over a WebSocket connection. The parent's frontend connects to a presigned WebSocket URL that routes through AgentCore Runtime to the agent. The agent streams its responses back as text frames — the parent sees the plan being written in real time.

---

## The 11-Step Workflow

One of the more interesting design decisions in this system is encoding a structured workflow inside the agent's instruction prompt rather than implementing it as application state in the API layer.

The instruction prompt defines eleven sequential steps:

1. Collect the child's first name
2. Call `getAvailableStates` and present the options
3. Once a state is selected, call `getAgeRanges` and present the options
4. Handle unsupported state/age combinations gracefully
5. Confirm the child's profile
6. Gather the child's interests (free text, optional)
7. Gather areas of focus or concern (free text, optional)
8. Ask for the plan duration (immediate suggestions / weekly / long-term)
9. Confirm all inputs before generating
10. Call `getIndicators`, then generate the plan using only those indicators
11. Call `createPlan` to persist the result

The agent follows this workflow conversationally — it doesn't present it as a form. The exchange feels like a conversation with a knowledgeable educator, not a bureaucratic intake process. But the underlying structure ensures that the agent never skips the tool calls it needs to make before generating content.

This approach has a real advantage over implementing the workflow as API state: the agent handles variation gracefully. If a parent says _"actually, he's more interested in dinosaurs than trucks — can we change that?"_ after they've already confirmed their interests, the agent can accommodate that without needing explicit back-navigation logic in the API. The language model understands the intent and updates its internal context.

---

## How Grounding Actually Works

The grounding constraint — "only use indicators returned by `getIndicators`" — is enforced through a combination of prompt instruction and tool design.

The instruction prompt's critical rules section is explicit:

> _"You MUST use ONLY indicator codes, descriptions, domain names, and strand names that are returned by the `StandardsQuery.getIndicators` action group call. NEVER fabricate, invent, or guess indicator codes or descriptions. Every activity in the plan MUST reference a real indicator code that was returned by `getIndicators`."_

The `getIndicators` tool returns a structured list of indicators for a given state and age range. Each indicator includes its code, title, description, domain name, and strand name — exactly the fields the agent needs to populate the plan's activity structure.

The plan content follows a strict schema:

```json
{
  "sections": [
    {
      "label": "Week 1",
      "activities": [
        {
          "title": "Activity title",
          "description": "Detailed description",
          "indicatorCode": "VA.SE.2.3",
          "indicatorDescription": "The child demonstrates motivation, independence, and responsibility while participating in a range of activities and routines.",
          "domain": "Approaches to Learning",
          "strand": "Initiative and Curiosity",
          "subStrand": "Initiative"
        }
      ]
    }
  ],
  "summary": "Plan overview"
}
```

Every activity must have an `indicatorCode` and `indicatorDescription`. Those values must come from the `getIndicators` response. The database layer enforces this further by validating indicator codes on write — a plan referencing a non-existent indicator code fails at persistence, not silently.

---

## The Authorization Problem

Conversational agents introduce a security challenge that doesn't exist in traditional REST APIs: the user's identity has to flow through a system that includes a language model in the middle.

In a standard API, a user authenticates with a JWT, the API validates the token, and the user's ID is extracted server-side. The user can't provide their own user ID — it comes from the validated token.

In an agent-based system, the LLM calls tools on behalf of the user. If the user's ID were passed as a parameter through the conversation, the LLM could theoretically be manipulated — through prompt injection in user input or adversarial content in retrieved data — into calling tools with a different user's ID. This is a specific instance of the broader hallucination and manipulation risks documented in the NLG hallucination literature ([Ji et al., 2023](https://dl.acm.org/doi/10.1145/3571730)), applied to tool-calling agents where the consequences are data access violations rather than just factual errors.

The solution in this system is defense in depth: the JWT is validated twice, the user ID is bound at tool construction time, and every database query enforces ownership.

When a parent opens a chat session, the planning API's auth middleware validates their Descope JWT and extracts the `sub` claim as their user ID. The API then generates a presigned WebSocket URL for AgentCore Runtime, embedding the original JWT as a custom query parameter:

```typescript
const queryParams: Record<string, string> = {
  "X-Amzn-Bedrock-AgentCore-Runtime-Custom-Token": rawToken,
};
```

AgentCore Runtime delivers custom query parameters as lowercased headers to the agent process. When the WebSocket connection arrives, the agent validates the Descope JWT a second time — independently, using the Descope SDK — and extracts the user ID from the token's claims. This means the agent never trusts the planning API's assertion of who the user is. It verifies the cryptographically signed token itself. If validation fails or no token is present, the connection is rejected before any agent is constructed:

```python
user_id = _extract_user_id(websocket, context)

if not user_id:
    await websocket.send_json({
        "type": "error",
        "message": "Not authenticated. Please log in to continue.",
    })
    await websocket.send_json({"type": "done"})
    return
```

Only after successful validation does the agent build its plan management tools, using a factory function that closes over the authenticated user ID:

```python
def build_session_tools(user_id: str) -> list:
    @tool
    def createPlan(child_name: str, child_age: str, state: str,
                   duration: str, content: dict, ...) -> dict:
        # user_id is captured by closure — the LLM cannot supply or override it
        return create_plan(user_id=user_id, ...)

    @tool
    def updatePlan(plan_id: str, content: dict) -> dict:
        return update_plan(plan_id=plan_id, user_id=user_id, content=content)

    return [createPlan, updatePlan, getPlan, deletePlan]
```

The LLM can call `createPlan` with any `child_name`, `state`, or `content` it wants. It cannot influence the `user_id` argument. That value is fixed at session construction time and is invisible to the model.

The final layer is the database itself. Every plan query includes the user ID in its `WHERE` clause — not just for reads, but for writes and deletes too:

```sql
UPDATE plans SET content = :content, updated_at = NOW()
WHERE id = :id AND user_id = :user_id
RETURNING *
```

If a row isn't returned, the operation fails with "Plan not found or not owned by user." Even if every other layer were somehow bypassed, the database would refuse to return or modify another user's data.

A prompt injection attack that somehow convinced the agent to call `createPlan` for a different user would simply create a plan owned by the authenticated user. An attempt to read or modify another user's plan by guessing a plan ID would hit the ownership check in the SQL query and fail. No single layer carries the full burden — the system doesn't need to be perfect at any one point because it's enforced at every point.

---

## Privacy by Design

Early childhood applications collect data about children. That requires deliberate restraint.

The planning assistant collects only the child's first name. The instruction prompt is explicit about what is not collected:

> _"Do not ask for or store last names, birthdates, addresses, email addresses, phone numbers, or any other personally identifiable information."_

This is enforced at the prompt level, at the API schema level (the `createPlan` function doesn't accept a last name field), and at the database schema level (the plans table has no last name column).

Age is collected as a range — _"36 to 48 months"_ — not as a precise date of birth. This is both a privacy choice and a practical one: early learning standards are organized by age bands, not precise ages, so a range is the appropriate granularity.

---

## The Plan Refinement Flow

A first planning session creates a plan. Subsequent sessions refine it.

When a parent returns to work on an existing plan, the WebSocket request includes the plan's ID as a custom session attribute. The agent loads the existing plan using `getPlan`, reviews its current content, and greets the parent by the child's name with a brief summary of what's already in the plan.

From there, the parent can ask for modifications: _"Can you add two more weeks of activities?"_, _"I want more focus on fine motor skills,"_, _"He's gotten really into music recently — can you add some music-based activities?"_

The agent calls `getIndicators` again if it needs to find indicators for the new focus area, generates the additional content, merges it with the existing plan, and calls `updatePlan` with the revised content. The parent doesn't need to re-enter their state or the child's age — that context is preserved in the existing plan.

---

## What This Looks Like in Practice

A parent using the assistant for the first time might have a conversation that goes something like this:

**Assistant:** Hi there! I'm here to help you create a personalized learning plan for your child. What's your child's first name?

**Parent:** Her name is Sofia.

**Assistant:** Great to meet Sofia's parent! I have early learning standards available for the following states: Virginia, Texas, New Jersey, Oregon, and Florida. Which state would you like to use for Sofia's learning plan?

[The parent selects Virginia. The assistant queries age ranges for Virginia and presents them.]

**Assistant:** For Virginia, I have standards for these age ranges: 24–36 months, 36–48 months, and 48–60 months. Which range matches Sofia best?

[The conversation continues through interests, concerns, and duration. After confirmation, the assistant calls `getIndicators` for Virginia / 48–60 months, receives real indicators from the database, and generates a structured weekly plan.]

**Assistant:** Here's Sofia's four-week learning plan, based on Virginia's early learning standards for children ages 48–60 months...

_Week 1, Activity 1: The Feelings Museum_
Create a "museum" at home where Sofia can place drawings or photos representing different emotions. Talk about each one: what makes her feel that way, what she does when she feels that way.

**Standard:** VA.SE.1.2 — _The child identifies and describes a range of emotions and their causes._
**Domain:** Social-Emotional Development | **Strand:** Emotional Knowledge

---

The plan continues across weeks, with each activity tied to a real indicator code that a teacher or family support specialist could look up in Virginia's official standards document.

---

## The Bigger Picture

The planning assistant is the part of this system that families actually touch. The pipeline, the normalization work, the database schema — none of that is visible to a parent creating a plan for their four-year-old. What they see is a tool that knows their state's standards, asks thoughtful questions about their child, and produces something genuinely useful.

But the quality of that output is entirely dependent on the quality of the data underneath it. A plan grounded in accurately extracted, human-verified standards from a normalized knowledge base is categorically different from one generated by a model with no connection to official frameworks.

That's the point of the whole system. The engineering rigor at the pipeline level is what makes the family-facing experience trustworthy.

---

_EdTech Co. is a mission-driven engineering initiative focused on building open infrastructure for early childhood education. This is the third article in a series on the technical architecture behind the ELS Platform._

---

_I work for Bezos Academy, a national provider of early-childhood education, but this research is my own and is in no way supported by Bezos Academy nor reflects the vision or mission of the organization._
