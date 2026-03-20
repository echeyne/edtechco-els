import { useState, useCallback, useRef, useEffect } from "react";
import { getSessionUrl } from "@/lib/api";

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

export interface PlanEvent {
  planId: string;
  action: "created" | "updated";
}

export interface UseChatOptions {
  token: string | null;
  sessionId?: string;
  planId?: string;
}

export interface UseChatReturn {
  messages: ChatMessage[];
  isStreaming: boolean;
  error: string | null;
  sendMessage: (message: string) => void;
  retry: () => void;
  planEvents: PlanEvent[];
}

export function useChat(options: UseChatOptions): UseChatReturn {
  const { token, sessionId: initialSessionId, planId } = options;

  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [planEvents, setPlanEvents] = useState<PlanEvent[]>([]);

  const lastMessageRef = useRef<string | null>(null);
  const sessionIdRef = useRef<string | undefined>(initialSessionId);
  const sessionUrlRef = useRef<string | null>(null);
  const sessionExpiresAtRef = useRef<number>(0);
  const wsRef = useRef<WebSocket | null>(null);

  // Clean up WebSocket on unmount
  useEffect(() => {
    return () => {
      if (wsRef.current) {
        wsRef.current.onclose = null;
        wsRef.current.onerror = null;
        wsRef.current.onmessage = null;
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, []);

  const ensureSessionUrl = useCallback(async (): Promise<string> => {
    const now = Math.floor(Date.now() / 1000);
    if (sessionUrlRef.current && sessionExpiresAtRef.current > now) {
      return sessionUrlRef.current;
    }

    const resp = await getSessionUrl(
      {
        sessionId: sessionIdRef.current,
        planId,
      },
      token!,
    );

    sessionUrlRef.current = resp.url;
    sessionIdRef.current = resp.sessionId;
    sessionExpiresAtRef.current = resp.expiresAt;
    return resp.url;
  }, [token, planId]);

  const openWebSocketAndSend = useCallback(
    async (message: string) => {
      if (!token) {
        setError("Not authenticated");
        return;
      }

      setIsStreaming(true);
      setError(null);

      // Add user message
      setMessages((prev) => [...prev, { role: "user", content: message }]);
      // Add empty assistant message to stream into
      setMessages((prev) => [...prev, { role: "assistant", content: "" }]);

      let url: string;
      try {
        url = await ensureSessionUrl();
      } catch (err: unknown) {
        setError(err instanceof Error ? err.message : "Failed to get session");
        setIsStreaming(false);
        return;
      }

      const ws = new WebSocket(url);
      wsRef.current = ws;

      ws.onopen = () => {
        ws.send(
          JSON.stringify({
            text: message,
          }),
        );
      };

      // Track whether we initiated the close (done/error frame) to avoid
      // spurious "Connection lost" errors from the onclose handler.
      let closedByProtocol = false;

      ws.onmessage = (event: MessageEvent) => {
        try {
          const frame = JSON.parse(event.data as string) as {
            type: string;
            text?: string;
            planId?: string;
            action?: "created" | "updated";
            message?: string;
          };

          switch (frame.type) {
            case "text": {
              setMessages((prev) => {
                const updated = [...prev];
                const last = updated[updated.length - 1];
                if (last && last.role === "assistant") {
                  updated[updated.length - 1] = {
                    ...last,
                    content: last.content + (frame.text ?? ""),
                  };
                }
                return updated;
              });
              break;
            }
            case "plan": {
              if (frame.planId && frame.action) {
                setPlanEvents((prev) => [
                  ...prev,
                  { planId: frame.planId!, action: frame.action! },
                ]);
              }
              break;
            }
            case "error": {
              closedByProtocol = true;
              setError(frame.message ?? "Unknown error");
              setIsStreaming(false);
              ws.close();
              break;
            }
            case "done": {
              closedByProtocol = true;
              setIsStreaming(false);
              ws.close();
              break;
            }
          }
        } catch {
          // Ignore malformed frames
        }
      };

      ws.onerror = () => {
        closedByProtocol = true;
        setError("Connection error");
        setIsStreaming(false);
      };

      ws.onclose = () => {
        if (!closedByProtocol) {
          setError("Connection lost");
          setIsStreaming(false);
        }
        wsRef.current = null;
      };
    },
    [token, planId, ensureSessionUrl],
  );

  const sendMessage = useCallback(
    (message: string) => {
      if (isStreaming) return;
      lastMessageRef.current = message;
      openWebSocketAndSend(message);
    },
    [isStreaming, openWebSocketAndSend],
  );

  const retry = useCallback(() => {
    if (isStreaming || !lastMessageRef.current) return;

    // Close existing WebSocket if open
    if (wsRef.current) {
      wsRef.current.onclose = null;
      wsRef.current.onerror = null;
      wsRef.current.onmessage = null;
      wsRef.current.close();
      wsRef.current = null;
    }

    // Remove the failed assistant message and the user message
    setMessages((prev) => {
      const updated = [...prev];
      if (
        updated.length > 0 &&
        updated[updated.length - 1].role === "assistant"
      ) {
        updated.pop();
      }
      if (updated.length > 0 && updated[updated.length - 1].role === "user") {
        updated.pop();
      }
      return updated;
    });

    setError(null);

    // Invalidate session URL so a fresh one is fetched if expired
    const now = Math.floor(Date.now() / 1000);
    if (sessionExpiresAtRef.current <= now) {
      sessionUrlRef.current = null;
    }

    openWebSocketAndSend(lastMessageRef.current);
  }, [isStreaming, openWebSocketAndSend]);

  return { messages, isStreaming, error, sendMessage, retry, planEvents };
}
