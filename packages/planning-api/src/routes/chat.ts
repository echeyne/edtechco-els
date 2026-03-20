import { Hono } from "hono";
import { streamSSE } from "hono/streaming";
import { z } from "zod";
import {
  BedrockAgentRuntimeClient,
  InvokeAgentCommand,
} from "@aws-sdk/client-bedrock-agent-runtime";
import type { AuthEnv } from "../middleware/auth.js";
import { requireAuth } from "../middleware/auth.js";

// ---- Bedrock client (lazy singleton, injectable for tests) ----

let _bedrockClient: BedrockAgentRuntimeClient | null = null;

function getBedrockClient(): BedrockAgentRuntimeClient {
  if (!_bedrockClient) {
    _bedrockClient = new BedrockAgentRuntimeClient({});
  }
  return _bedrockClient;
}

/** Allow tests to inject a mock client */
export function setBedrockClient(
  client: BedrockAgentRuntimeClient | null,
): void {
  _bedrockClient = client;
}

// ---- Request validation ----

const chatRequestSchema = z.object({
  message: z.string().min(1, "message is required"),
  sessionId: z.string().optional(),
  planId: z.string().optional(),
});

// ---- Timeout constant ----

const AGENT_TIMEOUT_MS = 60_000;

// ---- Route ----

const chat = new Hono<AuthEnv>();

chat.use("/*", requireAuth);

chat.post("/", async (c) => {
  const body = await c.req.json().catch(() => null);
  if (!body) {
    return c.json(
      { error: { code: "BAD_REQUEST", message: "Invalid JSON body" } },
      400,
    );
  }

  const parsed = chatRequestSchema.safeParse(body);
  if (!parsed.success) {
    return c.json(
      {
        error: {
          code: "BAD_REQUEST",
          message: parsed.error.issues.map((i) => i.message).join(", "),
        },
      },
      400,
    );
  }

  const { message, sessionId, planId } = parsed.data;
  const userId = c.get("userId");

  const agentId = process.env.BEDROCK_AGENT_ID;
  const agentAliasId = process.env.BEDROCK_AGENT_ALIAS_ID;

  if (!agentId || !agentAliasId) {
    return c.json(
      {
        error: {
          code: "INTERNAL_ERROR",
          message: "Agent configuration is missing",
        },
      },
      500,
    );
  }

  // Use provided sessionId or generate a new one
  const resolvedSessionId = sessionId ?? crypto.randomUUID();

  const sessionAttributes: Record<string, string> = { userId };
  if (planId) {
    sessionAttributes.planId = planId;
  }

  return streamSSE(c, async (stream) => {
    const abortController = new AbortController();
    const timeout = setTimeout(() => {
      abortController.abort();
    }, AGENT_TIMEOUT_MS);

    try {
      const command = new InvokeAgentCommand({
        agentId,
        agentAliasId,
        sessionId: resolvedSessionId,
        inputText: message,
        enableTrace: true,
        sessionState: {
          sessionAttributes,
        },
      });

      const response = await getBedrockClient().send(command, {
        abortSignal: abortController.signal,
      });

      if (!response.completion) {
        await stream.writeSSE({
          event: "error",
          data: JSON.stringify({ message: "No response from agent" }),
        });
        return;
      }

      for await (const event of response.completion) {
        // Text chunk from the agent
        if (event.chunk?.bytes) {
          const text = new TextDecoder().decode(event.chunk.bytes);
          await stream.writeSSE({
            event: "token",
            data: JSON.stringify({
              text,
              sessionId: resolvedSessionId,
            }),
          });
        }

        // Trace events — detect plan creation/update actions
        if (event.trace?.trace?.orchestrationTrace?.observation) {
          const observation = event.trace.trace.orchestrationTrace.observation;
          if (
            observation.type === "ACTION_GROUP" &&
            observation.actionGroupInvocationOutput?.text
          ) {
            try {
              const outputText = observation.actionGroupInvocationOutput.text;
              const parsed = JSON.parse(outputText);
              if (parsed.planId && parsed.action) {
                await stream.writeSSE({
                  event: "plan",
                  data: JSON.stringify({
                    planId: parsed.planId,
                    action: parsed.action,
                  }),
                });
              }
            } catch {
              // Not a plan event — ignore parse errors
            }
          }
        }

        // Detect plan actions from invocation input traces
        if (event.trace?.trace?.orchestrationTrace?.invocationInput) {
          const invInput = event.trace.trace.orchestrationTrace.invocationInput;
          if (
            invInput.invocationType === "ACTION_GROUP" &&
            invInput.actionGroupInvocationInput
          ) {
            const agInput = invInput.actionGroupInvocationInput;
            const apiPath = agInput.apiPath ?? "";
            const verb = agInput.verb ?? "";

            // Detect createPlan or updatePlan calls
            if (
              agInput.actionGroupName === "PlanManagement" &&
              ((verb === "POST" && apiPath.includes("plan")) ||
                (verb === "PUT" && apiPath.includes("plan")))
            ) {
              // Plan action detected — the observation handler above
              // will emit the plan SSE event with the actual planId
            }
          }
        }

        // Handle stream-level errors
        if (event.internalServerException) {
          await stream.writeSSE({
            event: "error",
            data: JSON.stringify({
              message: "Agent encountered an internal error",
            }),
          });
          return;
        }

        if (event.badGatewayException) {
          await stream.writeSSE({
            event: "error",
            data: JSON.stringify({
              message: "Agent service is temporarily unavailable",
            }),
          });
          return;
        }

        if (event.throttlingException) {
          await stream.writeSSE({
            event: "error",
            data: JSON.stringify({
              message: "Too many requests, please try again later",
            }),
          });
          return;
        }
      }

      // Stream completed successfully
      await stream.writeSSE({
        event: "done",
        data: JSON.stringify({}),
      });
    } catch (err: unknown) {
      if (abortController.signal.aborted) {
        await stream.writeSSE({
          event: "error",
          data: JSON.stringify({
            message: "Agent response timed out",
          }),
        });
        return;
      }

      const errorName = err instanceof Error ? err.constructor.name : "Unknown";

      // Map specific AWS SDK errors to appropriate responses
      if (
        errorName === "BadGatewayException" ||
        errorName === "DependencyFailedException"
      ) {
        await stream.writeSSE({
          event: "error",
          data: JSON.stringify({
            message: "Agent service is temporarily unavailable",
          }),
        });
        return;
      }

      await stream.writeSSE({
        event: "error",
        data: JSON.stringify({ message: "Something went wrong" }),
      });
    } finally {
      clearTimeout(timeout);
    }
  });
});

export default chat;
