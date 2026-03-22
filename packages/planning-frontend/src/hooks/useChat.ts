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

export function useChat(options: UseChatOptions) {
  const { token, sessionId: initialSessionId, planId } = options;

  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [planEvents, setPlanEvents] = useState<PlanEvent[]>([]);

  const sessionIdRef = useRef<string | undefined>(initialSessionId);
  const sessionUrlRef = useRef<string | null>(null);
  const sessionExpiresAtRef = useRef<number>(0);
  const wsRef = useRef<WebSocket | null>(null);
  const lastMessageRef = useRef<string | null>(null);
  /** Mirrors isStreaming for WebSocket handlers (connect closes over stale render state). */
  const streamingRef = useRef(false);

  const ensureSessionUrl = useCallback(async () => {
    if (!token) throw new Error("Missing auth token");

    const now = Math.floor(Date.now() / 1000);

    if (sessionUrlRef.current && sessionExpiresAtRef.current > now) {
      return sessionUrlRef.current;
    }

    const resp = await getSessionUrl(
      {
        sessionId: sessionIdRef.current,
        planId,
      },
      token,
    );

    sessionUrlRef.current = resp.url;
    sessionIdRef.current = resp.sessionId;
    sessionExpiresAtRef.current = resp.expiresAt;

    return resp.url;
  }, [token, planId]);

  const connect = useCallback(async () => {
    const url = decodeURIComponent(await ensureSessionUrl());

    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onmessage = (event) => {
      try {
        const frame = JSON.parse(event.data);
        console.log(frame);

        switch (frame.type) {
          case "text":
            setMessages((prev) => {
              const updated = [...prev];
              const last = updated[updated.length - 1];

              if (last?.role === "assistant") {
                last.content += frame.text ?? "";
              }

              return updated;
            });
            break;

          case "plan":
            if (frame.planId && frame.action) {
              setPlanEvents((prev) => [
                ...prev,
                { planId: frame.planId, action: frame.action },
              ]);
            }
            break;

          case "error":
            setError(frame.message ?? "Unknown error");
            streamingRef.current = false;
            setIsStreaming(false);
            ws.close();
            break;

          case "done":
            streamingRef.current = false;
            setIsStreaming(false);
            break;
        }
      } catch {
        // ignore bad frames
      }
    };

    ws.onclose = () => {
      sessionUrlRef.current = null;
      wsRef.current = null;

      if (streamingRef.current) {
        setError("Connection lost");
        streamingRef.current = false;
        setIsStreaming(false);
      }
    };

    await new Promise<void>((resolve, reject) => {
      ws.onopen = () => resolve();
      // ws.onopen = () => ws.send(JSON.stringify({ inputText: "Hello!" }));
      ws.onerror = () => reject(new Error("Connection error"));
    });

    ws.onerror = () => {
      setError("Connection error");
      streamingRef.current = false;
      setIsStreaming(false);
    };

    return ws;
  }, [ensureSessionUrl]);

  const sendMessage = useCallback(
    async (message: string) => {
      if (!token) {
        setError("Not authenticated");
        return;
      }
      console.log("hi");

      if (isStreaming) return;

      lastMessageRef.current = message;

      setMessages((prev) => [
        ...prev,
        { role: "user", content: message },
        { role: "assistant", content: "" },
      ]);

      setIsStreaming(true);
      streamingRef.current = true;
      setError(null);

      try {
        const ws = await connect();
        console.log("about to send");
        ws.send(
          JSON.stringify({
            inputText: message,
          }),
        );
      } catch (err: any) {
        setError(err?.message ?? "Connection failed");
        streamingRef.current = false;
        setIsStreaming(false);
      }
    },
    [token, isStreaming, connect],
  );

  const retry = useCallback(() => {
    if (!lastMessageRef.current || isStreaming) return;

    setMessages((prev) => prev.slice(0, -2));
    setError(null);

    sendMessage(lastMessageRef.current);
  }, [sendMessage, isStreaming]);

  useEffect(() => {
    return () => {
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, []);

  return {
    messages,
    isStreaming,
    error,
    sendMessage,
    retry,
    planEvents,
  };
}
