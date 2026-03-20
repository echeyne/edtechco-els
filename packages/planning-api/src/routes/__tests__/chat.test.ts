import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { Hono } from "hono";
import type { AuthEnv } from "../../middleware/auth.js";
import { setDescopeClient } from "../../middleware/auth.js";
import { setBedrockClient } from "../chat.js";
import chat from "../chat.js";
import type { InvokeAgentCommand } from "@aws-sdk/client-bedrock-agent-runtime";

// ---- Helpers ----

const TEST_USER_ID = "user-unit-test-123";

function createMockDescopeClient(userId = TEST_USER_ID) {
  return {
    validateSession: vi.fn().mockResolvedValue({
      token: { sub: userId },
    }),
  } as unknown as ReturnType<typeof import("@descope/node-sdk").default>;
}

function createMockBedrockClient(
  handler: (command: InvokeAgentCommand) => Promise<unknown>,
) {
  return {
    send: vi.fn().mockImplementation(handler),
  } as unknown as import("@aws-sdk/client-bedrock-agent-runtime").BedrockAgentRuntimeClient;
}

function createApp() {
  const app = new Hono<AuthEnv>();
  app.route("/api/chat", chat);
  return app;
}

function authHeaders() {
  return {
    "Content-Type": "application/json",
    Authorization: "Bearer valid-token",
  };
}

/**
 * Parse SSE text into an array of { event, data } objects.
 */
function parseSSE(text: string): Array<{ event: string; data: unknown }> {
  const events: Array<{ event: string; data: unknown }> = [];
  const blocks = text.split("\n\n").filter((b) => b.trim().length > 0);
  for (const block of blocks) {
    const lines = block.split("\n");
    let event = "";
    let data = "";
    for (const line of lines) {
      if (line.startsWith("event:")) {
        event = line.slice("event:".length).trim();
      } else if (line.startsWith("data:")) {
        data = line.slice("data:".length).trim();
      }
    }
    if (event && data) {
      try {
        events.push({ event, data: JSON.parse(data) });
      } catch {
        events.push({ event, data });
      }
    }
  }
  return events;
}

// ---- Tests ----

describe("POST /api/chat", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    process.env.BEDROCK_AGENT_ID = "test-agent-id";
    process.env.BEDROCK_AGENT_ALIAS_ID = "test-alias-id";
    setDescopeClient(createMockDescopeClient());
  });

  afterEach(() => {
    setDescopeClient(null);
    setBedrockClient(null);
    delete process.env.BEDROCK_AGENT_ID;
    delete process.env.BEDROCK_AGENT_ALIAS_ID;
  });

  // --- SSE format with mocked agent responses ---

  describe("SSE format", () => {
    it("streams token events from agent response chunks and ends with done", async () => {
      const mockClient = createMockBedrockClient(async () => ({
        completion: (async function* () {
          yield {
            chunk: {
              bytes: new TextEncoder().encode("Hello "),
            },
          };
          yield {
            chunk: {
              bytes: new TextEncoder().encode("world!"),
            },
          };
        })(),
      }));
      setBedrockClient(mockClient);
      const app = createApp();

      const res = await app.request("/api/chat", {
        method: "POST",
        headers: authHeaders(),
        body: JSON.stringify({ message: "Hi there" }),
      });

      expect(res.status).toBe(200);
      expect(res.headers.get("content-type")).toContain("text/event-stream");

      const text = await res.text();
      const events = parseSSE(text);

      // Should have 2 token events and 1 done event
      const tokenEvents = events.filter((e) => e.event === "token");
      const doneEvents = events.filter((e) => e.event === "done");

      expect(tokenEvents).toHaveLength(2);
      expect((tokenEvents[0].data as { text: string }).text).toBe("Hello ");
      expect((tokenEvents[1].data as { text: string }).text).toBe("world!");
      expect(doneEvents).toHaveLength(1);
    });

    it("includes sessionId in token events", async () => {
      const mockClient = createMockBedrockClient(async () => ({
        completion: (async function* () {
          yield {
            chunk: {
              bytes: new TextEncoder().encode("test"),
            },
          };
        })(),
      }));
      setBedrockClient(mockClient);
      const app = createApp();

      const res = await app.request("/api/chat", {
        method: "POST",
        headers: authHeaders(),
        body: JSON.stringify({ message: "Hi", sessionId: "my-session" }),
      });

      const text = await res.text();
      const events = parseSSE(text);
      const tokenEvent = events.find((e) => e.event === "token");

      expect(tokenEvent).toBeDefined();
      expect((tokenEvent!.data as { sessionId: string }).sessionId).toBe(
        "my-session",
      );
    });
  });

  // --- Error handling ---

  describe("Error handling", () => {
    it("returns 400 for invalid request body (missing message)", async () => {
      const app = createApp();

      const res = await app.request("/api/chat", {
        method: "POST",
        headers: authHeaders(),
        body: JSON.stringify({}),
      });

      expect(res.status).toBe(400);
      const body = await res.json();
      expect(body.error.code).toBe("BAD_REQUEST");
    });

    it("returns 400 for non-JSON body", async () => {
      const app = createApp();

      const res = await app.request("/api/chat", {
        method: "POST",
        headers: {
          ...authHeaders(),
          "Content-Type": "text/plain",
        },
        body: "not json",
      });

      expect(res.status).toBe(400);
      const body = await res.json();
      expect(body.error.code).toBe("BAD_REQUEST");
      expect(body.error.message).toBe("Invalid JSON body");
    });

    it("returns 400 for empty message string", async () => {
      const app = createApp();

      const res = await app.request("/api/chat", {
        method: "POST",
        headers: authHeaders(),
        body: JSON.stringify({ message: "" }),
      });

      expect(res.status).toBe(400);
      const body = await res.json();
      expect(body.error.code).toBe("BAD_REQUEST");
    });

    it("emits SSE error event when agent throws (502 scenario)", async () => {
      const mockClient = createMockBedrockClient(async () => {
        const err = new Error("Service unavailable");
        err.constructor = { name: "BadGatewayException" } as never;
        Object.defineProperty(err, "constructor", {
          value: { name: "BadGatewayException" },
        });
        throw err;
      });
      setBedrockClient(mockClient);
      const app = createApp();

      const res = await app.request("/api/chat", {
        method: "POST",
        headers: authHeaders(),
        body: JSON.stringify({ message: "Hello" }),
      });

      expect(res.status).toBe(200); // SSE stream starts with 200
      const text = await res.text();
      const events = parseSSE(text);

      const errorEvents = events.filter((e) => e.event === "error");
      expect(errorEvents.length).toBeGreaterThanOrEqual(1);
    });

    it("emits SSE error event on agent timeout (504 scenario)", async () => {
      // Simulate an abort error by making send reject with AbortError
      const mockClient = createMockBedrockClient(
        async (_cmd, options?: { abortSignal?: AbortSignal }) => {
          // Simulate a timeout by returning a stream that takes too long
          // We'll trigger the abort signal manually
          return {
            completion: (async function* () {
              // Simulate the abort controller aborting
              throw new DOMException("The operation was aborted", "AbortError");
            })(),
          };
        },
      );
      setBedrockClient(mockClient);
      const app = createApp();

      const res = await app.request("/api/chat", {
        method: "POST",
        headers: authHeaders(),
        body: JSON.stringify({ message: "Hello" }),
      });

      expect(res.status).toBe(200);
      const text = await res.text();
      const events = parseSSE(text);

      // Should have an error event (either timeout or generic error)
      const errorEvents = events.filter((e) => e.event === "error");
      expect(errorEvents.length).toBeGreaterThanOrEqual(1);
    });

    it("emits SSE error event on mid-stream error", async () => {
      const mockClient = createMockBedrockClient(async () => ({
        completion: (async function* () {
          // Emit one good chunk first
          yield {
            chunk: {
              bytes: new TextEncoder().encode("Starting..."),
            },
          };
          // Then emit an internal server exception
          yield {
            internalServerException: {
              message: "Something broke mid-stream",
            },
          };
        })(),
      }));
      setBedrockClient(mockClient);
      const app = createApp();

      const res = await app.request("/api/chat", {
        method: "POST",
        headers: authHeaders(),
        body: JSON.stringify({ message: "Hello" }),
      });

      expect(res.status).toBe(200);
      const text = await res.text();
      const events = parseSSE(text);

      // Should have at least one token event and one error event
      const tokenEvents = events.filter((e) => e.event === "token");
      const errorEvents = events.filter((e) => e.event === "error");

      expect(tokenEvents.length).toBeGreaterThanOrEqual(1);
      expect(errorEvents.length).toBeGreaterThanOrEqual(1);
      expect((errorEvents[0].data as { message: string }).message).toBe(
        "Agent encountered an internal error",
      );
    });

    it("emits SSE error event when completion is null", async () => {
      const mockClient = createMockBedrockClient(async () => ({
        completion: undefined,
      }));
      setBedrockClient(mockClient);
      const app = createApp();

      const res = await app.request("/api/chat", {
        method: "POST",
        headers: authHeaders(),
        body: JSON.stringify({ message: "Hello" }),
      });

      expect(res.status).toBe(200);
      const text = await res.text();
      const events = parseSSE(text);

      const errorEvents = events.filter((e) => e.event === "error");
      expect(errorEvents.length).toBeGreaterThanOrEqual(1);
      expect((errorEvents[0].data as { message: string }).message).toBe(
        "No response from agent",
      );
    });
  });

  // --- Auth ---

  describe("Authentication", () => {
    it("returns 401 when no auth token is provided", async () => {
      const app = createApp();

      const res = await app.request("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: "Hello" }),
      });

      expect(res.status).toBe(401);
    });
  });
});
