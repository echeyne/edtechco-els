// Feature: parent-planning-tool, Property 1: Protected endpoints reject invalid tokens

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import * as fc from "fast-check";
import { Hono } from "hono";
import { requireAuth, setDescopeClient } from "../auth.js";
import type { AuthEnv } from "../auth.js";

/**
 * Property 1: Protected endpoints reject invalid tokens
 *
 * For any protected Planning API endpoint and for any request with a missing,
 * malformed, or expired Bearer token, the API shall return a 401 Unauthorized
 * response and shall not forward the request to the Bedrock Agent or database.
 *
 * **Validates: Requirements 2.3, 2.4**
 */

// Spy to detect if any downstream handler is reached
const downstreamSpy = vi.fn();

function createMockDescopeClient(
  overrides: {
    validateSession?: (token: string) => Promise<unknown>;
  } = {},
) {
  return {
    validateSession:
      overrides.validateSession ??
      vi.fn().mockRejectedValue(new Error("Invalid token")),
  } as unknown as ReturnType<typeof import("@descope/node-sdk").default>;
}

function createApp() {
  const app = new Hono<AuthEnv>();
  app.use("/*", requireAuth);

  // Plan list endpoint
  app.get("/api/plans", (c) => {
    downstreamSpy();
    return c.json({ plans: [] });
  });

  // Plan detail endpoint
  app.get("/api/plans/:id", (c) => {
    downstreamSpy();
    return c.json({ plan: {} });
  });

  // Plan delete endpoint
  app.delete("/api/plans/:id", (c) => {
    downstreamSpy();
    return c.json({ deleted: true });
  });

  return app;
}

describe("Property 1: Protected endpoints reject invalid tokens", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    setDescopeClient(null);
  });

  it("any random invalid token string is rejected with 401 on all protected endpoints", async () => {
    // Mock Descope client to always reject tokens
    const mockClient = createMockDescopeClient({
      validateSession: vi.fn().mockRejectedValue(new Error("Invalid token")),
    });
    setDescopeClient(mockClient);
    const app = createApp();

    await fc.assert(
      fc.asyncProperty(
        fc.string(),
        fc.constantFrom("/api/plans", "/api/plans/some-uuid"),
        async (token: string, endpoint: string) => {
          downstreamSpy.mockClear();

          const headers: Record<string, string> = {};
          if (token.length > 0) {
            headers["Authorization"] = `Bearer ${token}`;
          }

          const res = await app.request(endpoint, { headers });

          // All responses must be 401
          expect(res.status).toBe(401);

          // No downstream handler should have been called
          expect(downstreamSpy).not.toHaveBeenCalled();

          // Response body should contain UNAUTHORIZED error code
          const body = await res.json();
          expect(body.error.code).toBe("UNAUTHORIZED");
        },
      ),
      { numRuns: 100 },
    );
  });
});
