import { useState, useCallback, useRef } from "react";

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

/**
 * Parse SSE text into individual events.
 * SSE events are separated by double newlines. Each event has optional
 * `event:` and `data:` lines.
 */
export function parseSSEEvents(raw: string): { event: string; data: string }[] {
  const events: { event: string; data: string }[] = [];
  const blocks = raw.split("\n\n");
  for (const block of blocks) {
    const trimmed = block.trim();
    if (!trimmed) continue;
    let eventType = "message";
    let data = "";
    for (const line of trimmed.split("\n")) {
      if (line.startsWith("event:")) {
        eventType = line.slice("event:".length).trim();
      } else if (line.startsWith("data:")) {
        data = line.slice("data:".length).trim();
      }
    }
    if (data) {
      events.push({ event: eventType, data });
    }
  }
  return events;
}

export function useChat(options: UseChatOptions): UseChatReturn {
  const { token, sessionId: initialSessionId, planId } = options;

  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [planEvents, setPlanEvents] = useState<PlanEvent[]>([]);

  const lastMessageRef = useRef<string | null>(null);
  const sessionIdRef = useRef<string | undefined>(initialSessionId);
  const abortControllerRef = useRef<AbortController | null>(null);

  const processStream = useCallback(
    async (message: string) => {
      if (!token) {
        setError("Not authenticated");
        return;
      }

      setIsStreaming(true);
      setError(null);

      // Add user message
      setMessages((prev) => [...prev, { role: "user", content: message }]);

      // Add empty assistant message that we'll stream into
      setMessages((prev) => [...prev, { role: "assistant", content: "" }]);

      const controller = new AbortController();
      abortControllerRef.current = controller;

      try {
        const response = await fetch("/api/chat", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({
            message,
            sessionId: sessionIdRef.current,
            planId,
          }),
          signal: controller.signal,
        });

        if (!response.ok) {
          const errorText = await response.text().catch(() => "Request failed");
          throw new Error(errorText || `HTTP ${response.status}`);
        }

        const reader = response.body?.getReader();
        if (!reader) {
          throw new Error("No response body");
        }

        const decoder = new TextDecoder();
        let buffer = "";

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });

          // Process complete SSE events (separated by double newline)
          const parts = buffer.split("\n\n");
          // Keep the last part as it may be incomplete
          buffer = parts.pop() ?? "";

          for (const part of parts) {
            const events = parseSSEEvents(part + "\n\n");
            for (const sseEvent of events) {
              handleSSEEvent(sseEvent);
            }
          }
        }

        // Process any remaining buffer
        if (buffer.trim()) {
          const events = parseSSEEvents(buffer + "\n\n");
          for (const sseEvent of events) {
            handleSSEEvent(sseEvent);
          }
        }
      } catch (err: unknown) {
        if ((err as Error).name === "AbortError") return;
        setError(err instanceof Error ? err.message : "Connection failed");
      } finally {
        setIsStreaming(false);
        abortControllerRef.current = null;
      }
    },
    [token, planId],
  );

  function handleSSEEvent(sseEvent: { event: string; data: string }) {
    try {
      const parsed = JSON.parse(sseEvent.data);

      switch (sseEvent.event) {
        case "token": {
          const text = parsed.text as string;
          if (parsed.sessionId) {
            sessionIdRef.current = parsed.sessionId as string;
          }
          // Append token to the last assistant message
          setMessages((prev) => {
            const updated = [...prev];
            const last = updated[updated.length - 1];
            if (last && last.role === "assistant") {
              updated[updated.length - 1] = {
                ...last,
                content: last.content + text,
              };
            }
            return updated;
          });
          break;
        }
        case "plan": {
          setPlanEvents((prev) => [
            ...prev,
            {
              planId: parsed.planId as string,
              action: parsed.action as "created" | "updated",
            },
          ]);
          break;
        }
        case "error": {
          setError(parsed.message as string);
          break;
        }
        case "done":
          // Stream complete — nothing extra to do
          break;
      }
    } catch {
      // Ignore malformed SSE data
    }
  }

  const sendMessage = useCallback(
    (message: string) => {
      if (isStreaming) return;
      lastMessageRef.current = message;
      processStream(message);
    },
    [isStreaming, processStream],
  );

  const retry = useCallback(() => {
    if (isStreaming || !lastMessageRef.current) return;
    // Remove the failed assistant message and the user message for the retry
    setMessages((prev) => {
      const updated = [...prev];
      // Remove trailing assistant message (empty or partial)
      if (
        updated.length > 0 &&
        updated[updated.length - 1].role === "assistant"
      ) {
        updated.pop();
      }
      // Remove the user message that triggered the failed request
      if (updated.length > 0 && updated[updated.length - 1].role === "user") {
        updated.pop();
      }
      return updated;
    });
    setError(null);
    processStream(lastMessageRef.current);
  }, [isStreaming, processStream]);

  return { messages, isStreaming, error, sendMessage, retry, planEvents };
}
