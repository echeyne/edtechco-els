// Unit tests for session endpoint edge cases (Task 1.4)

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import app from "../../index.js";
import { setPresignedUrlGenerator, setCredentials } from "../chat.js";
import { setDescopeClient } from "../../middleware/auth.js";

const UUID_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

function createMockDescopeClient() {
  return {
    validateSession: vi.fn().mockResolvedValue({
      token: { sub: "test-user-id" },
    }),
  } as unknown as ReturnType<typeof import("@descope/node-sdk").default>;
}

const MOCK_URL = "wss://agentcore.example.com/session/presigned";

describe("Session endpoint edge cases", () => {
  let capturedCalls: Array<unknown>;

  beforeEach(() => {
    capturedCalls = [];
    process.env.AGENTCORE_RUNTIME_ARN =
      "arn:aws:bedrock-agentcore:us-east-1:123456789012:runtime/test-runtime";
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

  it("returns 500 when AGENTCORE_RUNTIME_ARN is missing", async () => {
    delete process.env.AGENTCORE_RUNTIME_ARN;

    const res = await app.request("/api/chat/session", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: "Bearer valid-test-token",
      },
      body: JSON.stringify({}),
    });

    expect(res.status).toBe(500);
    const json = await res.json();
    expect(json.error.code).toBe("INTERNAL_ERROR");
    expect(json.error.message).toBe("Agent configuration is missing");
  });

  it("returns 401 for unauthenticated request", async () => {
    const res = await app.request("/api/chat/session", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({}),
    });

    expect(res.status).toBe(401);
    const json = await res.json();
    expect(json.error.code).toBe("UNAUTHORIZED");
  });

  it("returns 500 when presigned URL generation fails", async () => {
    setPresignedUrlGenerator(async () => {
      throw new Error("SDK service unavailable");
    });

    const res = await app.request("/api/chat/session", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: "Bearer valid-test-token",
      },
      body: JSON.stringify({}),
    });

    expect(res.status).toBe(500);
  });

  it("uses defaults when no body is sent", async () => {
    const res = await app.request("/api/chat/session", {
      method: "POST",
      headers: {
        Authorization: "Bearer valid-test-token",
      },
    });

    expect(res.status).toBe(200);
    const json = await res.json();

    // sessionId should be a valid UUID (auto-generated)
    expect(json.sessionId).toMatch(UUID_RE);
    expect(json.url).toBe(MOCK_URL);
    expect(json.expiresAt).toBeGreaterThan(0);
  });

  it("does not include planId in customHeaders when no body is sent", async () => {
    const res = await app.request("/api/chat/session", {
      method: "POST",
      headers: {
        Authorization: "Bearer valid-test-token",
      },
    });

    expect(res.status).toBe(200);
    expect(capturedCalls).toHaveLength(1);
    const opts = capturedCalls[0] as Record<string, unknown>;
    const customHeaders = opts.customHeaders as
      | Record<string, string>
      | undefined;
    expect(customHeaders).not.toHaveProperty("X-PlanId");
    expect(customHeaders).toHaveProperty("X-UserId", "test-user-id");
  });
});
