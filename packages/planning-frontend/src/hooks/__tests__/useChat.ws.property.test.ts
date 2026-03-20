import { renderHook, act, waitFor, cleanup } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import fc from "fast-check";
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

/** Simulate the WebSocket opening and delivering frames. */
function deliverFrames(ws: MockWebSocket, frames: object[]) {
  ws.onopen?.({});
  for (const frame of frames) {
    ws.onmessage?.({ data: JSON.stringify(frame) } as MessageEvent);
  }
}

function freshSession(overrides: Record<string, unknown> = {}) {
  return {
    url: "wss://example.com/ws",
    sessionId: "sess-1",
    expiresAt: Math.floor(Date.now() / 1000) + 300,
    ...overrides,
  };
}

/* ================================================================== */
/*  Property Tests                                                     */
/* ================================================================== */

describe("useChat WebSocket property tests", () => {
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    lastWs = null;
    mockGetSessionUrl.mockReset();
    mockGetSessionUrl.mockResolvedValue(freshSession());
    (globalThis as unknown as Record<string, unknown>).WebSocket =
      FakeWebSocket;
  });

  afterEach(() => {
    cleanup();
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  /* ---------------------------------------------------------------- */
  // Feature: agentcore-planning-agent, Property 2: WebSocket text chunks accumulate into assistant message
  /* ---------------------------------------------------------------- */
  describe("Property 2: WebSocket text chunks accumulate into assistant message", () => {
    it("assistant message content equals concatenation of all text chunks in order", async () => {
      // **Validates: Requirements 5.3**
      await fc.assert(
        fc.asyncProperty(
          fc.array(fc.string({ minLength: 1 }), {
            minLength: 1,
            maxLength: 20,
          }),
          async (chunks: string[]) => {
            cleanup();
            lastWs = null;
            mockGetSessionUrl.mockResolvedValue(freshSession());

            const { result, unmount } = renderHook(() =>
              useChat({ token: "test-token" }),
            );

            try {
              act(() => {
                result.current.sendMessage("hello");
              });

              await waitFor(() => expect(lastWs).not.toBeNull());

              const frames = [
                ...chunks.map((text) => ({ type: "text", text })),
                { type: "done" },
              ];

              act(() => {
                deliverFrames(lastWs!, frames);
              });

              await waitFor(() => {
                expect(result.current.isStreaming).toBe(false);
              });

              const assistantMsg = result.current.messages.find(
                (m) => m.role === "assistant",
              );
              expect(assistantMsg).toBeDefined();
              expect(assistantMsg!.content).toBe(chunks.join(""));
            } finally {
              unmount();
            }
          },
        ),
        { numRuns: 20 },
      );
    }, 30_000);
  });

  /* ---------------------------------------------------------------- */
  // Feature: agentcore-planning-agent, Property 3: WebSocket plan events accumulate into planEvents array
  /* ---------------------------------------------------------------- */
  describe("Property 3: WebSocket plan events accumulate into planEvents array", () => {
    it("planEvents contains all received plan events in order", async () => {
      // **Validates: Requirements 5.4, 11.1, 11.2**
      await fc.assert(
        fc.asyncProperty(
          fc.array(
            fc.record({
              planId: fc.string({ minLength: 1, maxLength: 30 }),
              action: fc.constantFrom("created" as const, "updated" as const),
            }),
            { minLength: 1, maxLength: 10 },
          ),
          async (events) => {
            cleanup();
            lastWs = null;
            mockGetSessionUrl.mockResolvedValue(freshSession());

            const { result, unmount } = renderHook(() =>
              useChat({ token: "test-token" }),
            );

            try {
              act(() => {
                result.current.sendMessage("create plans");
              });

              await waitFor(() => expect(lastWs).not.toBeNull());

              const frames = [
                ...events.map((e) => ({
                  type: "plan",
                  planId: e.planId,
                  action: e.action,
                })),
                { type: "done" },
              ];

              act(() => {
                deliverFrames(lastWs!, frames);
              });

              await waitFor(() => {
                expect(result.current.isStreaming).toBe(false);
              });

              expect(result.current.planEvents).toHaveLength(events.length);
              for (let i = 0; i < events.length; i++) {
                expect(result.current.planEvents[i]).toEqual({
                  planId: events[i].planId,
                  action: events[i].action,
                });
              }
            } finally {
              unmount();
            }
          },
        ),
        { numRuns: 20 },
      );
    }, 30_000);
  });

  /* ---------------------------------------------------------------- */
  // Feature: agentcore-planning-agent, Property 4: WebSocket errors set error state
  /* ---------------------------------------------------------------- */
  describe("Property 4: WebSocket errors set error state", () => {
    it("error is set and isStreaming is false for any error scenario", async () => {
      // **Validates: Requirements 5.5, 6.1**
      const errorScenario = fc.oneof(
        fc.constant({ kind: "onerror" as const }),
        fc.integer({ min: 1001, max: 4999 }).map((code) => ({
          kind: "onclose" as const,
          code,
        })),
        fc.string({ minLength: 1, maxLength: 50 }).map((msg) => ({
          kind: "error_frame" as const,
          message: msg,
        })),
      );

      await fc.assert(
        fc.asyncProperty(errorScenario, async (scenario) => {
          cleanup();
          lastWs = null;
          mockGetSessionUrl.mockResolvedValue(freshSession());

          const { result, unmount } = renderHook(() =>
            useChat({ token: "test-token" }),
          );

          try {
            act(() => {
              result.current.sendMessage("hi");
            });

            await waitFor(() => expect(lastWs).not.toBeNull());

            act(() => {
              lastWs!.onopen?.({});

              if (scenario.kind === "onerror") {
                lastWs!.onerror?.({});
              } else if (scenario.kind === "onclose") {
                lastWs!.onclose?.({ code: scenario.code } as CloseEvent);
              } else if (scenario.kind === "error_frame") {
                lastWs!.onmessage?.({
                  data: JSON.stringify({
                    type: "error",
                    message: scenario.message,
                  }),
                } as MessageEvent);
              }
            });

            await waitFor(() => {
              expect(result.current.error).not.toBeNull();
              expect(result.current.isStreaming).toBe(false);
            });
          } finally {
            unmount();
          }
        }),
        { numRuns: 20 },
      );
    }, 30_000);
  });

  /* ---------------------------------------------------------------- */
  // Feature: agentcore-planning-agent, Property 5: Retry removes failed messages and resends
  /* ---------------------------------------------------------------- */
  describe("Property 5: Retry removes failed messages and resends", () => {
    it("retry removes failed messages and resends the last user message", async () => {
      // **Validates: Requirements 6.3**
      await fc.assert(
        fc.asyncProperty(
          fc.array(
            fc.record({
              userMsg: fc.string({ minLength: 1, maxLength: 30 }),
              assistantReply: fc.string({ minLength: 1, maxLength: 30 }),
            }),
            { minLength: 0, maxLength: 3 },
          ),
          fc.string({ minLength: 1, maxLength: 30 }),
          async (history, failedMsg) => {
            cleanup();
            lastWs = null;
            mockGetSessionUrl.mockResolvedValue(freshSession());

            const { result, unmount } = renderHook(() =>
              useChat({ token: "test-token" }),
            );

            try {
              // Build up successful history
              for (const exchange of history) {
                act(() => {
                  result.current.sendMessage(exchange.userMsg);
                });

                await waitFor(() => expect(lastWs).not.toBeNull());

                act(() => {
                  deliverFrames(lastWs!, [
                    { type: "text", text: exchange.assistantReply },
                    { type: "done" },
                  ]);
                });

                await waitFor(() => {
                  expect(result.current.isStreaming).toBe(false);
                });

                lastWs = null;
              }

              const historyLenBefore = history.length * 2;

              // Send the message that will fail
              act(() => {
                result.current.sendMessage(failedMsg);
              });

              await waitFor(() => expect(lastWs).not.toBeNull());

              // Simulate error
              act(() => {
                lastWs!.onopen?.({});
                lastWs!.onerror?.({});
              });

              await waitFor(() => {
                expect(result.current.error).not.toBeNull();
                expect(result.current.isStreaming).toBe(false);
              });

              lastWs = null;

              // Now retry
              act(() => {
                result.current.retry();
              });

              await waitFor(() => expect(lastWs).not.toBeNull());

              // The failed user+assistant messages should be removed, then re-added
              expect(result.current.messages).toHaveLength(
                historyLenBefore + 2,
              );
              expect(result.current.messages[historyLenBefore].role).toBe(
                "user",
              );
              expect(result.current.messages[historyLenBefore].content).toBe(
                failedMsg,
              );

              // Complete the retry
              act(() => {
                deliverFrames(lastWs!, [
                  { type: "text", text: "recovered" },
                  { type: "done" },
                ]);
              });

              await waitFor(() => {
                expect(result.current.isStreaming).toBe(false);
                expect(result.current.error).toBeNull();
              });
            } finally {
              unmount();
            }
          },
        ),
        { numRuns: 10 },
      );
    }, 60_000);
  });

  /* ---------------------------------------------------------------- */
  // Feature: agentcore-planning-agent, Property 6: Presigned URL auto-renewal on expiry
  /* ---------------------------------------------------------------- */
  describe("Property 6: Presigned URL auto-renewal on expiry", () => {
    it("getSessionUrl is called twice when the first URL is expired", async () => {
      // **Validates: Requirements 6.4**
      await fc.assert(
        fc.asyncProperty(
          fc.integer({ min: 1, max: 3600 }),
          async (secondsAgo) => {
            cleanup();
            lastWs = null;
            mockGetSessionUrl.mockReset();

            const expiredAt = Math.floor(Date.now() / 1000) - secondsAgo;

            // First call returns an already-expired session
            mockGetSessionUrl.mockResolvedValueOnce(
              freshSession({
                url: "wss://example.com/ws-old",
                expiresAt: expiredAt,
              }),
            );

            // Second call returns a fresh session
            mockGetSessionUrl.mockResolvedValueOnce(
              freshSession({
                url: "wss://example.com/ws-new",
              }),
            );

            const { result, unmount } = renderHook(() =>
              useChat({ token: "test-token" }),
            );

            try {
              // First message — gets expired URL
              act(() => {
                result.current.sendMessage("first");
              });

              await waitFor(() => expect(lastWs).not.toBeNull());

              act(() => {
                deliverFrames(lastWs!, [
                  { type: "text", text: "reply1" },
                  { type: "done" },
                ]);
              });

              await waitFor(() => {
                expect(result.current.isStreaming).toBe(false);
              });

              lastWs = null;

              // Second message — URL is expired, should request a new one
              act(() => {
                result.current.sendMessage("second");
              });

              await waitFor(() => expect(lastWs).not.toBeNull());

              expect(mockGetSessionUrl).toHaveBeenCalledTimes(2);

              // Clean up streaming state
              act(() => {
                deliverFrames(lastWs!, [
                  { type: "text", text: "reply2" },
                  { type: "done" },
                ]);
              });

              await waitFor(() => {
                expect(result.current.isStreaming).toBe(false);
              });
            } finally {
              unmount();
            }
          },
        ),
        { numRuns: 20 },
      );
    }, 30_000);
  });

  /* ---------------------------------------------------------------- */
  // Feature: agentcore-planning-agent, Property 9: sendMessage obtains session URL and sends over WebSocket
  /* ---------------------------------------------------------------- */
  describe("Property 9: sendMessage obtains session URL and sends over WebSocket", () => {
    it("sendMessage calls getSessionUrl, opens WebSocket, and sends the message", async () => {
      // **Validates: Requirements 5.1, 5.2**
      await fc.assert(
        fc.asyncProperty(
          fc.string({ minLength: 1, maxLength: 50 }),
          async (message) => {
            cleanup();
            lastWs = null;
            mockGetSessionUrl.mockReset();
            mockGetSessionUrl.mockResolvedValue(freshSession());

            const { result, unmount } = renderHook(() =>
              useChat({ token: "test-token" }),
            );

            try {
              act(() => {
                result.current.sendMessage(message);
              });

              // getSessionUrl should have been called
              await waitFor(() => {
                expect(mockGetSessionUrl).toHaveBeenCalledTimes(1);
              });

              // WebSocket should have been created
              await waitFor(() => expect(lastWs).not.toBeNull());
              expect(lastWs!.url).toBe("wss://example.com/ws");

              // Trigger onopen to send the message
              act(() => {
                lastWs!.onopen?.({});
              });

              // Verify the message was sent as JSON
              expect(lastWs!.send).toHaveBeenCalledTimes(1);
              const sentPayload = JSON.parse(
                lastWs!.send.mock.calls[0][0] as string,
              );
              expect(sentPayload.text).toBe(message);
              // sessionAttributes are no longer sent over WebSocket;
              // they are embedded in the presigned URL query params.

              // Clean up: deliver done to reset streaming state
              act(() => {
                lastWs!.onmessage?.({
                  data: JSON.stringify({ type: "done" }),
                } as MessageEvent);
              });

              await waitFor(() => {
                expect(result.current.isStreaming).toBe(false);
              });
            } finally {
              unmount();
            }
          },
        ),
        { numRuns: 20 },
      );
    }, 60_000);
  });
});
