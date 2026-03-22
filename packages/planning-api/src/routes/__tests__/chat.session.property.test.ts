// Feature: agentcore-planning-agent, Property 1: Session endpoint returns valid presigned URL with correct session handling

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import * as fc from "fast-check";
import app from "../../index.js";
import { setPresignedUrlGenerator, setCredentials } from "../chat.js";
import { setDescopeClient } from "../../middleware/auth.js";
import type { PresignOptions } from "../../lib/presign.js";

/**
 * Property 1: Session endpoint returns valid presigned URL with correct session handling
 *
 * For any authenticated request to POST /api/chat/session with an optional
 * sessionId and optional planId, the response SHALL contain:
 * (a) a non-empty url string starting with wss://,
 * (b) a sessionId matching the provided value or a valid UUID if none was provided,
 * (c) an expiresAt timestamp within 300 seconds of the current time, and
 * (d) the planId (if provided) SHALL have been forwarded as a Runtime-Custom
 *     query parameter to the presigned URL generation call.
 *
 * **Validates: Requirements 1.2, 1.3, 1.4, 1.5, 1.6**
 */

const UUID_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

const RUNTIME_ARN =
  "arn:aws:bedrock-agentcore:us-east-1:123456789012:runtime/test-runtime";
const MOCK_URL = "wss://agentcore.example.com/session/presigned";

function createMockDescopeClient() {
  return {
    validateSession: vi.fn().mockResolvedValue({
      token: { sub: "test-user-id" },
    }),
  } as unknown as ReturnType<typeof import("@descope/node-sdk").default>;
}

describe("Property 1: Session endpoint returns valid presigned URL with correct session handling", () => {
  let capturedCalls: PresignOptions[];

  beforeEach(() => {
    capturedCalls = [];
    process.env.AGENTCORE_RUNTIME_ARN = RUNTIME_ARN;
    setDescopeClient(createMockDescopeClient());
    setCredentials(async () => ({
      accessKeyId: "AKID",
      secretAccessKey: "SECRET",
    }));
    setPresignedUrlGenerator(async (opts) => {
      capturedCalls.push(opts);
      return MOCK_URL;
    });
  });

  afterEach(() => {
    delete process.env.AGENTCORE_RUNTIME_ARN;
    setDescopeClient(null);
    setCredentials(null);
    setPresignedUrlGenerator(null);
  });

  // Arbitrary for optional sessionId (UUID string or undefined)
  const sessionIdArb = fc.option(fc.uuid(), { nil: undefined });

  // Arbitrary for optional planId (non-empty alphanumeric string or undefined)
  const planIdArb = fc.option(fc.stringMatching(/^[a-zA-Z0-9-]{1,50}$/), {
    nil: undefined,
  });

  it("returns valid wss:// URL, correct sessionId, valid expiresAt, and forwards planId", async () => {
    await fc.assert(
      fc.asyncProperty(sessionIdArb, planIdArb, async (sessionId, planId) => {
        const body: Record<string, string> = {};
        if (sessionId !== undefined) body.sessionId = sessionId;
        if (planId !== undefined) body.planId = planId;

        const nowBefore = Math.floor(Date.now() / 1000);

        const res = await app.request("/api/chat/session", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: "Bearer valid-test-token",
          },
          body: JSON.stringify(body),
        });

        const nowAfter = Math.floor(Date.now() / 1000);

        expect(res.status).toBe(200);
        const json = (await res.json()) as {
          url: string;
          sessionId: string;
          expiresAt: number;
        };

        // (a) URL starts with wss://
        expect(json.url).toMatch(/^wss:\/\//);

        // (b) sessionId matches provided value or is a valid UUID
        if (sessionId !== undefined) {
          expect(json.sessionId).toBe(sessionId);
        } else {
          expect(json.sessionId).toMatch(UUID_RE);
        }

        // (c) expiresAt is within 300 seconds of current time
        expect(json.expiresAt).toBeGreaterThanOrEqual(nowBefore + 300);
        expect(json.expiresAt).toBeLessThanOrEqual(nowAfter + 300);

        // (d) planId forwarded as allowlisted Runtime-Custom query param
        const lastCall = capturedCalls[capturedCalls.length - 1];
        if (planId !== undefined) {
          expect(lastCall.queryParams).toHaveProperty(
            "X-Amzn-Bedrock-AgentCore-Runtime-Custom-PlanId",
            planId,
          );
        } else {
          expect(lastCall.queryParams).not.toHaveProperty(
            "X-Amzn-Bedrock-AgentCore-Runtime-Custom-PlanId",
          );
        }

        expect(lastCall.queryParams).toHaveProperty(
          "X-Amzn-Bedrock-AgentCore-Runtime-Custom-UserId",
          "test-user-id",
        );
      }),
      { numRuns: 20 },
    );
  });
});
