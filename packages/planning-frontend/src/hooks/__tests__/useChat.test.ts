import { renderHook, act, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { useChat, parseSSEEvents } from "../useChat";

/* ------------------------------------------------------------------ */
/*  Helpers                                                            */
/* ------------------------------------------------------------------ */

/** Build a ReadableStream that emits the given SSE chunks sequentially. */
function makeSSEStream(chunks: string[]): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder();
  let index = 0;
  return new ReadableStream({
    pull(controller) {
      if (index < chunks.length) {
        controller.enqueue(encoder.encode(chunks[index]));
        index++;
      } else {
        controller.close();
      }
    },
  });
}

/** Create a mock fetch that returns an SSE stream from the given chunks. */
function mockFetchSSE(chunks: string[], status = 200) {
  return vi.fn().mockResolvedValue({
    ok: status >= 200 && status < 300,
    status,
    body: makeSSEStream(chunks),
    text: () => Promise.resolve("error"),
  } as unknown as Response);
}

/* ------------------------------------------------------------------ */
/*  parseSSEEvents unit tests                                          */
/* ------------------------------------------------------------------ */

describe("parseSSEEvents", () => {
  it("parses a single token event", () => {
    const raw = 'event: token\ndata: {"text":"hello","sessionId":"s1"}\n\n';
    const events = parseSSEEvents(raw);
    expect(events).toEqual([
      { event: "token", data: '{"text":"hello","sessionId":"s1"}' },
    ]);
  });

  it("parses multiple events", () => {
    const raw =
      'event: token\ndata: {"text":"a","sessionId":"s1"}\n\n' +
      'event: plan\ndata: {"planId":"p1","action":"created"}\n\n' +
      "event: done\ndata: {}\n\n";
    const events = parseSSEEvents(raw);
    expect(events).toHaveLength(3);
    expect(events[0].event).toBe("token");
    expect(events[1].event).toBe("plan");
    expect(events[2].event).toBe("done");
  });

  it("ignores empty blocks", () => {
    const raw = "\n\n\n\n";
    expect(parseSSEEvents(raw)).toEqual([]);
  });
});

/* ------------------------------------------------------------------ */
/*  useChat hook tests                                                 */
/* ------------------------------------------------------------------ */

describe("useChat", () => {
  const originalFetch = globalThis.fetch;

  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
    vi.useRealTimers();
  });

  it("accumulates messages from token events", async () => {
    const chunks = [
      'event: token\ndata: {"text":"Hello ","sessionId":"s1"}\n\n',
      'event: token\ndata: {"text":"world","sessionId":"s1"}\n\n',
      "event: done\ndata: {}\n\n",
    ];
    globalThis.fetch = mockFetchSSE(chunks);

    const { result } = renderHook(() => useChat({ token: "test-token" }));

    act(() => {
      result.current.sendMessage("Hi");
    });

    await waitFor(() => {
      expect(result.current.isStreaming).toBe(false);
    });

    // Should have user message + assistant message
    expect(result.current.messages).toHaveLength(2);
    expect(result.current.messages[0]).toEqual({
      role: "user",
      content: "Hi",
    });
    expect(result.current.messages[1]).toEqual({
      role: "assistant",
      content: "Hello world",
    });
  });

  it("tracks plan events", async () => {
    const chunks = [
      'event: token\ndata: {"text":"Done","sessionId":"s1"}\n\n',
      'event: plan\ndata: {"planId":"plan-1","action":"created"}\n\n',
      "event: done\ndata: {}\n\n",
    ];
    globalThis.fetch = mockFetchSSE(chunks);

    const { result } = renderHook(() => useChat({ token: "test-token" }));

    act(() => {
      result.current.sendMessage("Create a plan");
    });

    await waitFor(() => {
      expect(result.current.isStreaming).toBe(false);
    });

    expect(result.current.planEvents).toEqual([
      { planId: "plan-1", action: "created" },
    ]);
  });

  it("sets error on SSE error event", async () => {
    const chunks = [
      'event: error\ndata: {"message":"Something went wrong"}\n\n',
    ];
    globalThis.fetch = mockFetchSSE(chunks);

    const { result } = renderHook(() => useChat({ token: "test-token" }));

    act(() => {
      result.current.sendMessage("Hi");
    });

    await waitFor(() => {
      expect(result.current.error).toBe("Something went wrong");
    });
  });

  it("sets error on HTTP failure", async () => {
    globalThis.fetch = mockFetchSSE([], 500);

    const { result } = renderHook(() => useChat({ token: "test-token" }));

    act(() => {
      result.current.sendMessage("Hi");
    });

    await waitFor(() => {
      expect(result.current.error).toBe("error");
      expect(result.current.isStreaming).toBe(false);
    });
  });

  it("sets error when token is null", async () => {
    const { result } = renderHook(() => useChat({ token: null }));

    act(() => {
      result.current.sendMessage("Hi");
    });

    await waitFor(() => {
      expect(result.current.error).toBe("Not authenticated");
    });
  });

  it("retry resends the last message", async () => {
    // First call fails
    let callCount = 0;
    globalThis.fetch = vi.fn().mockImplementation(() => {
      callCount++;
      if (callCount === 1) {
        return Promise.resolve({
          ok: false,
          status: 500,
          body: null,
          text: () => Promise.resolve("Server error"),
        });
      }
      // Second call succeeds
      const chunks = [
        'event: token\ndata: {"text":"Recovered","sessionId":"s1"}\n\n',
        "event: done\ndata: {}\n\n",
      ];
      return Promise.resolve({
        ok: true,
        status: 200,
        body: makeSSEStream(chunks),
        text: () => Promise.resolve(""),
      });
    });

    const { result } = renderHook(() => useChat({ token: "test-token" }));

    // Send initial message — will fail
    act(() => {
      result.current.sendMessage("Hello");
    });

    await waitFor(() => {
      expect(result.current.error).toBe("Server error");
      expect(result.current.isStreaming).toBe(false);
    });

    // Retry
    act(() => {
      result.current.retry();
    });

    await waitFor(() => {
      expect(result.current.isStreaming).toBe(false);
      expect(result.current.error).toBeNull();
    });

    // After retry, should have user + assistant messages
    expect(result.current.messages).toHaveLength(2);
    expect(result.current.messages[0]).toEqual({
      role: "user",
      content: "Hello",
    });
    expect(result.current.messages[1]).toEqual({
      role: "assistant",
      content: "Recovered",
    });

    // fetch was called twice
    expect(globalThis.fetch).toHaveBeenCalledTimes(2);
  });

  it("sends correct request body with sessionId and planId", async () => {
    const chunks = ["event: done\ndata: {}\n\n"];
    globalThis.fetch = mockFetchSSE(chunks);

    const { result } = renderHook(() =>
      useChat({ token: "tok", sessionId: "sess-1", planId: "plan-1" }),
    );

    act(() => {
      result.current.sendMessage("Refine plan");
    });

    await waitFor(() => {
      expect(result.current.isStreaming).toBe(false);
    });

    expect(globalThis.fetch).toHaveBeenCalledWith(
      "/api/chat",
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({
          Authorization: "Bearer tok",
          "Content-Type": "application/json",
        }),
        body: JSON.stringify({
          message: "Refine plan",
          sessionId: "sess-1",
          planId: "plan-1",
        }),
      }),
    );
  });

  it("does not send when already streaming", async () => {
    // Create a stream that never completes
    const neverEndingStream = new ReadableStream<Uint8Array>({
      start() {
        // intentionally never close
      },
    });
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      body: neverEndingStream,
      text: () => Promise.resolve(""),
    });

    const { result } = renderHook(() => useChat({ token: "test-token" }));

    act(() => {
      result.current.sendMessage("First");
    });

    // Should be streaming now
    await waitFor(() => {
      expect(result.current.isStreaming).toBe(true);
    });

    // Try to send another message — should be ignored
    act(() => {
      result.current.sendMessage("Second");
    });

    // fetch should only have been called once
    expect(globalThis.fetch).toHaveBeenCalledTimes(1);
  });
});
