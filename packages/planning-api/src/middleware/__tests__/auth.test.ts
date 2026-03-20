import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { Hono } from "hono";
import { requireAuth, setDescopeClient } from "../auth.js";
import type { AuthEnv } from "../auth.js";

function createMockDescopeClient(
  overrides: {
    validateSession?: (token: string) => Promise<unknown>;
  } = {},
) {
  return {
    validateSession: overrides.validateSession ?? vi.fn(),
  } as unknown as ReturnType<typeof import("@descope/node-sdk").default>;
}

function createApp() {
  const app = new Hono<AuthEnv>();
  app.use("/protected/*", requireAuth);
  app.get("/protected/test", (c) => {
    const userId = c.get("userId");
    return c.json({ userId });
  });
  return app;
}

describe("requireAuth middleware", () => {
  afterEach(() => {
    setDescopeClient(null);
  });

  it("returns 401 when Authorization header is missing", async () => {
    const mockClient = createMockDescopeClient();
    setDescopeClient(mockClient);
    const app = createApp();

    const res = await app.request("/protected/test");
    expect(res.status).toBe(401);
    const body = await res.json();
    expect(body).toEqual({
      error: {
        code: "UNAUTHORIZED",
        message: "Missing authentication token",
      },
    });
  });

  it("returns 401 when Authorization header has wrong scheme", async () => {
    const mockClient = createMockDescopeClient();
    setDescopeClient(mockClient);
    const app = createApp();

    const res = await app.request("/protected/test", {
      headers: { Authorization: "Basic abc123" },
    });
    expect(res.status).toBe(401);
    const body = await res.json();
    expect(body.error.code).toBe("UNAUTHORIZED");
    expect(body.error.message).toBe("Missing authentication token");
  });

  it("returns 401 when Bearer token is malformed (no token value)", async () => {
    const mockClient = createMockDescopeClient();
    setDescopeClient(mockClient);
    const app = createApp();

    const res = await app.request("/protected/test", {
      headers: { Authorization: "Bearer" },
    });
    expect(res.status).toBe(401);
    const body = await res.json();
    expect(body.error.code).toBe("UNAUTHORIZED");
  });

  it("returns 401 when Descope rejects the token (expired/invalid)", async () => {
    const mockClient = createMockDescopeClient({
      validateSession: vi.fn().mockRejectedValue(new Error("Token expired")),
    });
    setDescopeClient(mockClient);
    const app = createApp();

    const res = await app.request("/protected/test", {
      headers: { Authorization: "Bearer expired-token" },
    });
    expect(res.status).toBe(401);
    const body = await res.json();
    expect(body).toEqual({
      error: {
        code: "UNAUTHORIZED",
        message: "Invalid or expired authentication token",
      },
    });
  });

  it("sets userId on context when token is valid", async () => {
    const mockClient = createMockDescopeClient({
      validateSession: vi.fn().mockResolvedValue({
        token: { sub: "user-abc-123" },
      }),
    });
    setDescopeClient(mockClient);
    const app = createApp();

    const res = await app.request("/protected/test", {
      headers: { Authorization: "Bearer valid-token" },
    });
    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.userId).toBe("user-abc-123");
  });

  it("sets userId to 'unknown' when token.sub is missing", async () => {
    const mockClient = createMockDescopeClient({
      validateSession: vi.fn().mockResolvedValue({
        token: {},
      }),
    });
    setDescopeClient(mockClient);
    const app = createApp();

    const res = await app.request("/protected/test", {
      headers: { Authorization: "Bearer valid-token-no-sub" },
    });
    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.userId).toBe("unknown");
  });

  it("returns 401 when Bearer has extra parts", async () => {
    const mockClient = createMockDescopeClient();
    setDescopeClient(mockClient);
    const app = createApp();

    const res = await app.request("/protected/test", {
      headers: { Authorization: "Bearer token extra" },
    });
    expect(res.status).toBe(401);
    const body = await res.json();
    expect(body.error.code).toBe("UNAUTHORIZED");
  });
});
