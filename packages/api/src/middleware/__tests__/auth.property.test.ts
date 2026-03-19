import { describe, it, expect, afterEach } from "vitest";
import * as fc from "fast-check";
import { Hono } from "hono";
import {
  requireAuth,
  requireEditPermission,
  setDescopeClient,
  type AuthEnv,
} from "../auth.js";
import type { AuthenticationInfo } from "@descope/node-sdk";

/**
 * Property 4: Authorization Enforcement
 *
 * For any write operation attempted without a valid authentication token or
 * without the canEdit permission, the API SHALL reject the request with an
 * appropriate error status (401 for unauthenticated, 403 for unauthorized)
 * and SHALL NOT modify any data.
 *
 * Validates: Requirements 2.1, 3.1, 3.4, 10.3, 10.6
 */

// ---- Test helpers ----

/** Arbitrary that produces numeric-string resource IDs */
const arbId = fc.nat({ max: 999999 }).map(String);

/** Build a minimal mock Descope client */
function createMockDescopeClient(
  behavior: "valid" | "invalid",
  tokenClaims: Record<string, unknown> = {},
) {
  return {
    validateSession: async (
      _sessionToken: string,
    ): Promise<AuthenticationInfo> => {
      if (behavior === "invalid") {
        throw new Error("Invalid token");
      }
      return {
        jwt: "mock-jwt",
        token: {
          sub: "user-123",
          exp: Math.floor(Date.now() / 1000) + 3600,
          iss: "descope",
          email: "test@example.com",
          ...tokenClaims,
        },
      };
    },
  } as unknown as ReturnType<typeof import("@descope/node-sdk").default>;
}

/** Create a test Hono app with auth-protected routes */
function createTestApp() {
  const app = new Hono<AuthEnv>();

  // Protected write endpoint requiring auth + edit permission
  app.put(
    "/api/test-resource/:id",
    requireAuth,
    requireEditPermission,
    async (c) => {
      const user = c.get("authUser");
      return c.json({ success: true, editedBy: user.displayName });
    },
  );

  // Auth-only endpoint (no edit permission required)
  app.get("/api/test-resource/:id", requireAuth, async (c) => {
    const user = c.get("authUser");
    return c.json({ success: true, userId: user.userId });
  });

  return app;
}

describe("Property 4: Authorization Enforcement", () => {
  afterEach(() => {
    setDescopeClient(null);
  });

  // ---- Property: Requests without a token are always rejected with 401 ----

  it("rejects requests with no Authorization header (401)", async () => {
    const app = createTestApp();
    setDescopeClient(createMockDescopeClient("valid"));

    await fc.assert(
      fc.asyncProperty(
        arbId,
        fc.constantFrom("GET", "PUT") as fc.Arbitrary<string>,
        async (id, method) => {
          const req = new Request(`http://localhost/api/test-resource/${id}`, {
            method,
          });
          const res = await app.request(req);
          expect(res.status).toBe(401);
          const body = await res.json();
          expect(body.error.code).toBe("UNAUTHORIZED");
        },
      ),
      { numRuns: 100 },
    );
  });

  // ---- Property: Requests with invalid tokens are always rejected with 401 ----

  it("rejects requests with invalid tokens (401)", async () => {
    const app = createTestApp();
    setDescopeClient(createMockDescopeClient("invalid"));

    await fc.assert(
      fc.asyncProperty(
        arbId,
        fc.string({ minLength: 1, maxLength: 500 }),
        fc.constantFrom("GET", "PUT") as fc.Arbitrary<string>,
        async (id, token, method) => {
          const req = new Request(`http://localhost/api/test-resource/${id}`, {
            method,
            headers: { Authorization: `Bearer ${token}` },
          });
          const res = await app.request(req);
          expect(res.status).toBe(401);
          const body = await res.json();
          expect(body.error.code).toBe("UNAUTHORIZED");
        },
      ),
      { numRuns: 100 },
    );
  });

  // ---- Property: Malformed Authorization headers are rejected with 401 ----

  it("rejects requests with malformed Authorization headers (401)", async () => {
    const app = createTestApp();
    setDescopeClient(createMockDescopeClient("valid"));

    await fc.assert(
      fc.asyncProperty(
        arbId,
        fc.oneof(
          fc.constant("Basic abc123"),
          fc.constant("Token abc123"),
          fc.constant("Bearer"),
          fc.constant("bearer valid-token"),
          fc
            .string({ minLength: 1, maxLength: 100 })
            .filter((s) => !s.startsWith("Bearer ")),
        ),
        async (id, header) => {
          const req = new Request(`http://localhost/api/test-resource/${id}`, {
            method: "PUT",
            headers: { Authorization: header },
          });
          const res = await app.request(req);
          expect(res.status).toBe(401);
        },
      ),
      { numRuns: 100 },
    );
  });

  // ---- Property: Valid token WITHOUT canEdit → 403 on write endpoints ----

  it("rejects write requests from users without canEdit permission (403)", async () => {
    const app = createTestApp();

    await fc.assert(
      fc.asyncProperty(
        arbId,
        fc.emailAddress(),
        fc.uuid(),
        async (id, email, userId) => {
          setDescopeClient(
            createMockDescopeClient("valid", {
              sub: userId,
              email,
              canEdit: false,
            }),
          );

          const req = new Request(`http://localhost/api/test-resource/${id}`, {
            method: "PUT",
            headers: { Authorization: "Bearer valid-token" },
          });
          const res = await app.request(req);
          expect(res.status).toBe(403);
          const body = await res.json();
          expect(body.error.code).toBe("FORBIDDEN");
        },
      ),
      { numRuns: 100 },
    );
  });

  // ---- Property: Valid token WITHOUT canEdit → 200 on read endpoints ----

  it("allows read requests from authenticated users without canEdit (200)", async () => {
    const app = createTestApp();

    await fc.assert(
      fc.asyncProperty(
        arbId,
        fc.emailAddress(),
        fc.uuid(),
        async (id, email, userId) => {
          setDescopeClient(
            createMockDescopeClient("valid", {
              sub: userId,
              email,
              canEdit: false,
            }),
          );

          const req = new Request(`http://localhost/api/test-resource/${id}`, {
            method: "GET",
            headers: { Authorization: "Bearer valid-token" },
          });
          const res = await app.request(req);
          expect(res.status).toBe(200);
          const body = await res.json();
          expect(body.success).toBe(true);
          expect(body.userId).toBe(userId);
        },
      ),
      { numRuns: 100 },
    );
  });

  // ---- Property: Valid token WITH canEdit → 200 on write endpoints ----

  it("allows write requests from users with canEdit permission (200)", async () => {
    const app = createTestApp();

    await fc.assert(
      fc.asyncProperty(
        arbId,
        fc.emailAddress(),
        fc.uuid(),
        async (id, email, userId) => {
          setDescopeClient(
            createMockDescopeClient("valid", {
              sub: userId,
              email,
              canEdit: true,
            }),
          );

          const req = new Request(`http://localhost/api/test-resource/${id}`, {
            method: "PUT",
            headers: { Authorization: "Bearer valid-token" },
          });
          const res = await app.request(req);
          expect(res.status).toBe(200);
          const body = await res.json();
          expect(body.success).toBe(true);
          expect(body.editedBy).toBe(email);
        },
      ),
      { numRuns: 100 },
    );
  });

  // ---- Property: canEdit via customAttributes is also recognized ----

  it("recognizes canEdit from customAttributes claim", async () => {
    const app = createTestApp();

    await fc.assert(
      fc.asyncProperty(
        arbId,
        fc.emailAddress(),
        fc.boolean(),
        async (id, email, canEdit) => {
          setDescopeClient(
            createMockDescopeClient("valid", {
              email,
              customAttributes: { canEdit },
            }),
          );

          const req = new Request(`http://localhost/api/test-resource/${id}`, {
            method: "PUT",
            headers: { Authorization: "Bearer valid-token" },
          });
          const res = await app.request(req);

          if (canEdit) {
            expect(res.status).toBe(200);
          } else {
            expect(res.status).toBe(403);
          }
        },
      ),
      { numRuns: 100 },
    );
  });

  // ---- Property: No data mutation on rejected requests ----

  it("does not reach the handler on unauthorized requests", async () => {
    let handlerCalled = false;

    const app = new Hono<AuthEnv>();
    app.put(
      "/api/resource/:id",
      requireAuth,
      requireEditPermission,
      async (c) => {
        handlerCalled = true;
        return c.json({ success: true });
      },
    );

    await fc.assert(
      fc.asyncProperty(
        fc.constantFrom(
          "none",
          "invalid",
          "no-permission",
        ) as fc.Arbitrary<string>,
        async (scenario) => {
          handlerCalled = false;

          const headers: Record<string, string> = {};

          if (scenario === "none") {
            setDescopeClient(createMockDescopeClient("valid"));
            // No Authorization header
          } else if (scenario === "invalid") {
            setDescopeClient(createMockDescopeClient("invalid"));
            headers["Authorization"] = "Bearer bad-token";
          } else {
            setDescopeClient(
              createMockDescopeClient("valid", { canEdit: false }),
            );
            headers["Authorization"] = "Bearer valid-token";
          }

          const req = new Request("http://localhost/api/resource/1", {
            method: "PUT",
            headers,
          });
          await app.request(req);
          expect(handlerCalled).toBe(false);
        },
      ),
      { numRuns: 100 },
    );
  });
});
