// Feature: parent-planning-tool, Property 2: Authenticated user ID is forwarded to the agent

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import * as fc from "fast-check";
import { Hono } from "hono";
import type { AuthEnv } from "../../middleware/auth.js";
import { requireAuth, setDescopeClient } from "../../middleware/auth.js";
import { setBedrockClient } from "../chat.js";
import { InvokeAgentCommand } from "@aws-sdk/client-bedrock-agent-runtime";

/**
 * Property 2: Authenticated user ID is forwarded to the agent
 *
 * For any authenticated chat request, the Planning API shall include the
 * authenticated user's Descope userId in the session attributes passed to
 * the Bedrock Agent's invokeAgent call.
 *
 * **Validates: Requirements 2.5**
 */

// ---- Helpers ----

function createMockDescopeClient(userId: string) {
  return {
    validateSession: vi.fn().mockResolvedValue({
      token: { sub: userId },
    }),
  } as unknown as ReturnType<typeof import("@descope/node-sdk").default>;
}

function createMockBedrockClient() {
  const capturedCommands: InvokeAgentCommand[] = [];

  const mockClient = {
    send: vi.fn().mockImplementation((command: InvokeAgentCommand) => {
      capturedCommands.push(command);
      // Return a response with an empty async iterable completion stream
      return Promise.resolve({
        completion: (async function* () {
          // empty stream — just end immediately
        })(),
      });
    }),
  };

  return { mockClient, capturedCommands };
}

describe("Property 2: Authenticated user ID is forwarded to the agent", () => {
  beforeEach(() => {
    process.env.BEDROCK_AGENT_ID = "test-agent-id";
    process.env.BEDROCK_AGENT_ALIAS_ID = "test-alias-id";
  });

  afterEach(() => {
    setDescopeClient(null);
    setBedrockClient(null);
    delete process.env.BEDROCK_AGENT_ID;
    delete process.env.BEDROCK_AGENT_ALIAS_ID;
  });

  it("any random valid user ID is included in the Bedrock Agent session attributes", async () => {
    await fc.assert(
      fc.asyncProperty(fc.uuid(), async (userId: string) => {
        // Set up mocks for this iteration
        setDescopeClient(createMockDescopeClient(userId));
        const { mockClient, capturedCommands } = createMockBedrockClient();
        setBedrockClient(
          mockClient as unknown as import("@aws-sdk/client-bedrock-agent-runtime").BedrockAgentRuntimeClient,
        );

        // Import chat route and build a fresh app
        const chatModule = await import("../chat.js");
        const app = new Hono<AuthEnv>();
        app.route("/api/chat", chatModule.default);

        const res = await app.request("/api/chat", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: "Bearer valid-token",
          },
          body: JSON.stringify({ message: "Hello" }),
        });

        // The endpoint should return 200 (SSE stream)
        expect(res.status).toBe(200);

        // Consume the response body to ensure the stream completes
        await res.text();

        // Assert the InvokeAgentCommand was called with the userId in session attributes
        expect(capturedCommands.length).toBe(1);
        const command = capturedCommands[0];
        expect(command.input.sessionState?.sessionAttributes?.userId).toBe(
          userId,
        );
      }),
      { numRuns: 100 },
    );
  });
});
