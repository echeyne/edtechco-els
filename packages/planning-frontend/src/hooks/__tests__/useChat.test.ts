import { renderHook, act, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { useChat } from "../useChat";

/* ------------------------------------------------------------------ */
/*  Mock getSessionUrl                                                 */
/* ------------------------------------------------------------------ */

const mockGetSessionUrl = vi.fn();

vi.mock("@/lib/api", () => ({
  getSessionUrl: (...args: unknown[]) => mockGetSessionUrl(...args),
}));

/* ------------------------------------------------------------------ */
/*  Mock WebSocket                                                     */
/* ------------------------------------------------------------------ */

type WSHandler = ((event: unknown) => void) | null;

interface MockWebSocket {
  onopen: WSHandler;
  onmessage: WSHandler;
  onerror: WSHandler;
  onclose: WSHandler;
  send: ReturnType<typeof vi.fn>;
  close: ReturnType<typeof vi.fn>;
  readyState: number;
  url: string;
}

let lastWs: MockWebSocket | null = null;

class FakeWebSocket implements MockWebSocket {
  onopen: WSHandler = null;
  onmessage: WSHandler = null;
  onerror: WSHandler = null;
  onclose: WSHandler = null;
  send = vi.fn();
  close = vi.fn();
  readyState = 0;
  url: string;

  constructor(url: string) {
    this.url = url;
    lastWs = this;
  }
}

/* ------------------------------------------------------------------ */
/*  Helpers                                                            */
/* ------------------------------------------------------------------ */

/** Simulate the WebSocket opening and delivering frames, then done. */
function deliverFrames(ws: MockWebSocket, frames: object[]) {
  // Fire onopen
  ws.onopen?.({});

  // Deliver each frame
  for (const frame of frames) {
    ws.onmessage?.({ data: JSON.stringify(frame) } as MessageEvent);
  }
}

const DEFAULT_SESSION = {
  url: "wss://example.com/ws",
  sessionId: "sess-1",
  expiresAt: Math.floor(Date.now() / 1000) + 300,
};

/* ------------------------------------------------------------------ */
/*  Tests                                                              */
/* ------------------------------------------------------------------ */

describe("useChat (WebSocket)", () => {
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    lastWs = null;
    mockGetSessionUrl.mockResolvedValue({ ...DEFAULT_SESSION });
    (globalThis as unknown as Record<string, unknown>).WebSocket =
      FakeWebSocket;
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it("accumulates messages from text frames", async () => {
    const { result } = renderHook(() => useChat({ token: "test-token" }));

    act(() => {
      result.current.sendMessage("Hi");
    });

    await waitFor(() => expect(lastWs).not.toBeNull());

    act(() => {
      deliverFrames(lastWs!, [
        { type: "text", text: "Hello " },
        { type: "text", text: "world" },
        { type: "done" },
      ]);
    });

    await waitFor(() => {
      expect(result.current.isStreaming).toBe(false);
    });

    expect(result.current.messages).toHaveLength(2);
    expect(result.current.messages[0]).toEqual({ role: "user", content: "Hi" });
    expect(result.current.messages[1]).toEqual({
      role: "assistant",
      content: "Hello world",
    });
  });

  it("tracks plan events", async () => {
    const { result } = renderHook(() => useChat({ token: "test-token" }));

    act(() => {
      result.current.sendMessage("Create a plan");
    });

    await waitFor(() => expect(lastWs).not.toBeNull());

    act(() => {
      deliverFrames(lastWs!, [
        { type: "text", text: "Done" },
        { type: "plan", planId: "plan-1", action: "created" },
        { type: "done" },
      ]);
    });

    await waitFor(() => {
      expect(result.current.isStreaming).toBe(false);
    });

    expect(result.current.planEvents).toEqual([
      { planId: "plan-1", action: "created" },
    ]);
  });

  it("sets error on error frame", async () => {
    const { result } = renderHook(() => useChat({ token: "test-token" }));

    act(() => {
      result.current.sendMessage("Hi");
    });

    await waitFor(() => expect(lastWs).not.toBeNull());

    act(() => {
      deliverFrames(lastWs!, [
        { type: "error", message: "Something went wrong" },
      ]);
    });

    await waitFor(() => {
      expect(result.current.error).toBe("Something went wrong");
      expect(result.current.isStreaming).toBe(false);
    });
  });

  it("sets error on getSessionUrl failure", async () => {
    mockGetSessionUrl.mockRejectedValueOnce(new Error("Network error"));

    const { result } = renderHook(() => useChat({ token: "test-token" }));

    act(() => {
      result.current.sendMessage("Hi");
    });

    await waitFor(() => {
      expect(result.current.error).toBe("Network error");
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

  it("sets error on WebSocket onerror", async () => {
    const { result } = renderHook(() => useChat({ token: "test-token" }));

    act(() => {
      result.current.sendMessage("Hi");
    });

    await waitFor(() => expect(lastWs).not.toBeNull());

    act(() => {
      lastWs!.onerror?.({});
    });

    await waitFor(() => {
      expect(result.current.error).toBe("Connection error");
      expect(result.current.isStreaming).toBe(false);
    });
  });

  it("sets error on WebSocket onclose with non-1000 code", async () => {
    const { result } = renderHook(() => useChat({ token: "test-token" }));

    act(() => {
      result.current.sendMessage("Hi");
    });

    await waitFor(() => expect(lastWs).not.toBeNull());

    act(() => {
      lastWs!.onclose?.({ code: 1006 } as CloseEvent);
    });

    await waitFor(() => {
      expect(result.current.error).toBe("Connection lost");
      expect(result.current.isStreaming).toBe(false);
    });
  });

  it("does not set error on normal close (code 1000)", async () => {
    const { result } = renderHook(() => useChat({ token: "test-token" }));

    act(() => {
      result.current.sendMessage("Hi");
    });

    await waitFor(() => expect(lastWs).not.toBeNull());

    act(() => {
      deliverFrames(lastWs!, [
        { type: "text", text: "Hello" },
        { type: "done" },
      ]);
    });

    await waitFor(() => {
      expect(result.current.isStreaming).toBe(false);
    });

    // Simulate normal close after done
    act(() => {
      lastWs!.onclose?.({ code: 1000 } as CloseEvent);
    });

    expect(result.current.error).toBeNull();
  });

  it("retry resends the last message", async () => {
    mockGetSessionUrl.mockRejectedValueOnce(new Error("Server error"));

    const { result } = renderHook(() => useChat({ token: "test-token" }));

    // Send initial message — will fail at session URL fetch
    act(() => {
      result.current.sendMessage("Hello");
    });

    await waitFor(() => {
      expect(result.current.error).toBe("Server error");
      expect(result.current.isStreaming).toBe(false);
    });

    // Reset mock for retry
    mockGetSessionUrl.mockResolvedValue({ ...DEFAULT_SESSION });

    // Retry
    act(() => {
      result.current.retry();
    });

    await waitFor(() => expect(lastWs).not.toBeNull());

    act(() => {
      deliverFrames(lastWs!, [
        { type: "text", text: "Recovered" },
        { type: "done" },
      ]);
    });

    await waitFor(() => {
      expect(result.current.isStreaming).toBe(false);
      expect(result.current.error).toBeNull();
    });

    expect(result.current.messages).toHaveLength(2);
    expect(result.current.messages[0]).toEqual({
      role: "user",
      content: "Hello",
    });
    expect(result.current.messages[1]).toEqual({
      role: "assistant",
      content: "Recovered",
    });
  });

  it("sends correct JSON payload over WebSocket", async () => {
    const { result } = renderHook(() =>
      useChat({ token: "tok", sessionId: "sess-1", planId: "plan-1" }),
    );

    act(() => {
      result.current.sendMessage("Refine plan");
    });

    await waitFor(() => expect(lastWs).not.toBeNull());

    // Trigger onopen to send the message
    act(() => {
      lastWs!.onopen?.({});
    });

    await waitFor(() => {
      expect(lastWs!.send).toHaveBeenCalledTimes(1);
    });
    expect(lastWs!.send).toHaveBeenCalledWith(
      JSON.stringify({
        inputText: "Refine plan",
      }),
    );
  });

  it("does not send when already streaming", async () => {
    const { result } = renderHook(() => useChat({ token: "test-token" }));

    act(() => {
      result.current.sendMessage("First");
    });

    await waitFor(() => expect(lastWs).not.toBeNull());

    // Should be streaming now
    expect(result.current.isStreaming).toBe(true);

    // Try to send another message — should be ignored
    act(() => {
      result.current.sendMessage("Second");
    });

    // getSessionUrl should only have been called once
    expect(mockGetSessionUrl).toHaveBeenCalledTimes(1);
  });

  it("reuses session URL if not expired", async () => {
    const { result } = renderHook(() => useChat({ token: "test-token" }));

    // First message
    act(() => {
      result.current.sendMessage("First");
    });

    await waitFor(() => expect(lastWs).not.toBeNull());

    act(() => {
      deliverFrames(lastWs!, [
        { type: "text", text: "Reply 1" },
        { type: "done" },
      ]);
    });

    await waitFor(() => {
      expect(result.current.isStreaming).toBe(false);
    });

    // Second message — should reuse session URL
    act(() => {
      result.current.sendMessage("Second");
    });

    await waitFor(() => {
      expect(result.current.messages).toHaveLength(4);
    });

    // getSessionUrl should only have been called once (reused)
    expect(mockGetSessionUrl).toHaveBeenCalledTimes(1);
  });

  it("requests new session URL when expired", async () => {
    // Return an already-expired session
    mockGetSessionUrl.mockResolvedValueOnce({
      url: "wss://example.com/ws-old",
      sessionId: "sess-1",
      expiresAt: Math.floor(Date.now() / 1000) - 10, // expired
    });

    const { result } = renderHook(() => useChat({ token: "test-token" }));

    // First message
    act(() => {
      result.current.sendMessage("First");
    });

    await waitFor(() => expect(lastWs).not.toBeNull());

    act(() => {
      deliverFrames(lastWs!, [
        { type: "text", text: "Reply 1" },
        { type: "done" },
      ]);
    });

    await waitFor(() => {
      expect(result.current.isStreaming).toBe(false);
    });

    // Reset mock for second call with fresh URL
    mockGetSessionUrl.mockResolvedValueOnce({
      ...DEFAULT_SESSION,
      url: "wss://example.com/ws-new",
    });

    // Second message — URL is expired, should request new one
    act(() => {
      result.current.sendMessage("Second");
    });

    await waitFor(() => {
      expect(mockGetSessionUrl).toHaveBeenCalledTimes(2);
    });
  });

  it("calls getSessionUrl with sessionId and planId", async () => {
    renderHook(() =>
      useChat({ token: "tok", sessionId: "my-sess", planId: "my-plan" }),
    );

    const { result } = renderHook(() =>
      useChat({ token: "tok", sessionId: "my-sess", planId: "my-plan" }),
    );

    act(() => {
      result.current.sendMessage("Hello");
    });

    await waitFor(() => expect(lastWs).not.toBeNull());

    expect(mockGetSessionUrl).toHaveBeenCalledWith(
      { sessionId: "my-sess", planId: "my-plan" },
      "tok",
    );
  });
});
