import { queryMany } from "../db/client.js";
import {
  createPlan,
  getPlanById,
  updatePlan,
  deletePlan,
  type CreatePlanInput,
} from "../db/plans.js";
import type { PlanContent } from "../types.js";

// ---- Bedrock Agent Action Group event/response types ----

export interface BedrockAgentActionGroupEvent {
  actionGroup: string;
  apiPath: string;
  httpMethod: string;
  parameters?: Array<{ name: string; value: string }>;
  requestBody?: {
    content: {
      "application/json": {
        properties: Array<{ name: string; value: string }>;
      };
    };
  };
  sessionAttributes?: Record<string, string>;
}

export interface ActionGroupResponse {
  messageVersion: "1.0";
  response: {
    actionGroup: string;
    apiPath: string;
    httpMethod: string;
    httpStatusCode: number;
    responseBody: {
      "application/json": {
        body: string;
      };
    };
  };
}

// ---- Helpers ----

function getParam(
  params: Array<{ name: string; value: string }> | undefined,
  name: string,
): string | undefined {
  return params?.find((p) => p.name === name)?.value;
}

function getBodyProp(
  requestBody: BedrockAgentActionGroupEvent["requestBody"],
  name: string,
): string | undefined {
  const props = requestBody?.content?.["application/json"]?.properties;
  return props?.find((p) => p.name === name)?.value;
}

function buildResponse(
  event: BedrockAgentActionGroupEvent,
  statusCode: number,
  body: unknown,
): ActionGroupResponse {
  return {
    messageVersion: "1.0",
    response: {
      actionGroup: event.actionGroup,
      apiPath: event.apiPath,
      httpMethod: event.httpMethod,
      httpStatusCode: statusCode,
      responseBody: {
        "application/json": {
          body: JSON.stringify(body),
        },
      },
    },
  };
}

function errorResponse(
  event: BedrockAgentActionGroupEvent,
  statusCode: number,
  message: string,
): ActionGroupResponse {
  return buildResponse(event, statusCode, { error: message });
}

// ---- Standards Query handlers ----

interface StateRow extends Record<string, unknown> {
  state: string;
}

interface AgeBandRow extends Record<string, unknown> {
  age_band: string;
}

interface IndicatorRow extends Record<string, unknown> {
  code: string;
  description: string;
  domain_name: string;
  strand_name: string | null;
  sub_strand_name: string | null;
  age_band: string;
}

export async function getAvailableStates(): Promise<string[]> {
  const rows = await queryMany<StateRow>(
    "SELECT DISTINCT state FROM documents ORDER BY state",
  );
  return rows.map((r) => r.state);
}

export async function getAgeBands(state: string): Promise<string[]> {
  const rows = await queryMany<AgeBandRow>(
    `SELECT DISTINCT doc.age_band
     FROM indicators i
     JOIN sub_strands ss ON i.sub_strand_id = ss.id
     JOIN strands s ON ss.strand_id = s.id
     JOIN domains d ON s.domain_id = d.id
     JOIN documents doc ON d.document_id = doc.id
     WHERE doc.state = $1
     ORDER BY doc.age_band`,
    [state],
  );
  return rows.map((r) => r.age_band);
}

export async function getIndicators(
  state: string,
  ageBand: string,
): Promise<IndicatorRow[]> {
  return queryMany<IndicatorRow>(
    `SELECT i.code,
            i.description,
            d.name AS domain_name,
            s.name AS strand_name,
            ss.name AS sub_strand_name,
            doc.age_band
     FROM indicators i
     JOIN sub_strands ss ON i.sub_strand_id = ss.id
     JOIN strands s ON ss.strand_id = s.id
     JOIN domains d ON s.domain_id = d.id
     JOIN documents doc ON d.document_id = doc.id
     WHERE doc.state = $1 AND doc.age_band = $2
     ORDER BY d.name, s.name, i.code`,
    [state, ageBand],
  );
}

async function handleStandardsQuery(
  event: BedrockAgentActionGroupEvent,
  params: BedrockAgentActionGroupEvent["parameters"],
): Promise<ActionGroupResponse> {
  const { apiPath } = event;

  if (apiPath === "/getAvailableStates") {
    const states = await getAvailableStates();
    return buildResponse(event, 200, { states });
  }

  if (apiPath === "/getAgeBands") {
    const state = getParam(params, "state");
    if (!state) {
      return errorResponse(event, 400, "Missing required parameter: state");
    }
    const ageBands = await getAgeBands(state);
    return buildResponse(event, 200, { ageBands });
  }

  if (apiPath === "/getIndicators") {
    const state = getParam(params, "state");
    const ageBand = getParam(params, "ageBand");
    if (!state || !ageBand) {
      return errorResponse(
        event,
        400,
        "Missing required parameters: state, ageBand",
      );
    }
    const indicators = await getIndicators(state, ageBand);
    return buildResponse(event, 200, { indicators });
  }

  return errorResponse(event, 404, `Unknown StandardsQuery path: ${apiPath}`);
}

// ---- Plan Management handlers ----

async function handlePlanManagement(
  event: BedrockAgentActionGroupEvent,
  httpMethod: string,
  params: BedrockAgentActionGroupEvent["parameters"],
  requestBody: BedrockAgentActionGroupEvent["requestBody"],
): Promise<ActionGroupResponse> {
  const { apiPath } = event;

  if (apiPath === "/createPlan" && httpMethod === "POST") {
    const userId = getBodyProp(requestBody, "userId");
    const childName = getBodyProp(requestBody, "childName");
    const childAge = getBodyProp(requestBody, "childAge");
    const state = getBodyProp(requestBody, "state");
    const interests = getBodyProp(requestBody, "interests") ?? null;
    const concerns = getBodyProp(requestBody, "concerns") ?? null;
    const duration = getBodyProp(requestBody, "duration");
    const contentStr = getBodyProp(requestBody, "content");

    if (
      !userId ||
      !childName ||
      !childAge ||
      !state ||
      !duration ||
      !contentStr
    ) {
      return errorResponse(
        event,
        400,
        "Missing required fields: userId, childName, childAge, state, duration, content",
      );
    }

    let content: PlanContent;
    try {
      content = JSON.parse(contentStr) as PlanContent;
    } catch {
      return errorResponse(event, 400, "Invalid JSON in content field");
    }

    const input: CreatePlanInput = {
      userId,
      childName,
      childAge,
      state,
      interests,
      concerns,
      duration,
      content,
    };

    const plan = await createPlan(input);
    return buildResponse(event, 201, { plan });
  }

  if (apiPath === "/updatePlan" && httpMethod === "PUT") {
    const planId =
      getParam(params, "planId") ?? getBodyProp(requestBody, "planId");
    const userId =
      getParam(params, "userId") ?? getBodyProp(requestBody, "userId");
    const contentStr =
      getParam(params, "content") ?? getBodyProp(requestBody, "content");

    if (!planId || !userId || !contentStr) {
      return errorResponse(
        event,
        400,
        "Missing required fields: planId, userId, content",
      );
    }

    let content: PlanContent;
    try {
      content = JSON.parse(contentStr) as PlanContent;
    } catch {
      return errorResponse(event, 400, "Invalid JSON in content field");
    }

    const plan = await updatePlan(planId, userId, content);
    if (!plan) {
      return errorResponse(event, 404, "Plan not found or not owned by user");
    }
    return buildResponse(event, 200, { plan });
  }

  if (apiPath === "/getPlan" && httpMethod === "GET") {
    const planId = getParam(params, "planId");
    const userId = getParam(params, "userId");

    if (!planId || !userId) {
      return errorResponse(
        event,
        400,
        "Missing required parameters: planId, userId",
      );
    }

    const plan = await getPlanById(planId, userId);
    if (!plan) {
      return errorResponse(event, 404, "Plan not found or not owned by user");
    }
    return buildResponse(event, 200, { plan });
  }

  if (apiPath === "/deletePlan" && httpMethod === "DELETE") {
    const planId = getParam(params, "planId");
    const userId = getParam(params, "userId");

    if (!planId || !userId) {
      return errorResponse(
        event,
        400,
        "Missing required parameters: planId, userId",
      );
    }

    const deleted = await deletePlan(planId, userId);
    if (!deleted) {
      return errorResponse(event, 404, "Plan not found or not owned by user");
    }
    return buildResponse(event, 200, { success: true });
  }

  return errorResponse(
    event,
    404,
    `Unknown PlanManagement path: ${apiPath} ${httpMethod}`,
  );
}

// ---- Main handler ----

export async function handler(
  event: BedrockAgentActionGroupEvent,
): Promise<ActionGroupResponse> {
  const { actionGroup, httpMethod, parameters, requestBody } = event;

  try {
    switch (actionGroup) {
      case "StandardsQuery":
        return await handleStandardsQuery(event, parameters);
      case "PlanManagement":
        return await handlePlanManagement(
          event,
          httpMethod,
          parameters,
          requestBody,
        );
      default:
        return errorResponse(
          event,
          400,
          `Unknown action group: ${actionGroup}`,
        );
    }
  } catch (err) {
    const message =
      err instanceof Error ? err.message : "Internal server error";
    return errorResponse(event, 500, message);
  }
}
