import { useState, useRef, useEffect, type FormEvent } from "react";
import { useChat, type ChatMessage } from "@/hooks/useChat";
import { useAuth } from "@/contexts/AuthContext";

/* ------------------------------------------------------------------ */
/*  MessageBubble                                                      */
/* ------------------------------------------------------------------ */

function MessageBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === "user";
  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"} mb-3`}>
      <div
        className={`max-w-[80%] rounded-lg px-4 py-2 text-sm whitespace-pre-wrap ${
          isUser
            ? "bg-primary text-primary-foreground"
            : "bg-muted text-foreground"
        }`}
      >
        {message.content}
        {!isUser && message.content === "" && (
          <span className="inline-block animate-pulse">▍</span>
        )}
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  MessageList                                                        */
/* ------------------------------------------------------------------ */

function MessageList({ messages }: { messages: ChatMessage[] }) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  if (messages.length === 0) {
    return (
      <div className="flex-1 flex items-center justify-center text-muted-foreground text-sm">
        Start a conversation to create a learning plan.
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto p-4">
      {messages.map((msg, i) => (
        <MessageBubble key={i} message={msg} />
      ))}
      <div ref={bottomRef} />
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  MessageInput                                                       */
/* ------------------------------------------------------------------ */

function MessageInput({
  onSend,
  disabled,
}: {
  onSend: (message: string) => void;
  disabled: boolean;
}) {
  const [text, setText] = useState("");

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    const trimmed = text.trim();
    if (!trimmed || disabled) return;
    onSend(trimmed);
    setText("");
  };

  return (
    <form onSubmit={handleSubmit} className="flex gap-2 border-t p-4">
      <input
        type="text"
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder="Type your message…"
        disabled={disabled}
        className="flex-1 rounded-md border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary disabled:opacity-50"
        aria-label="Chat message"
      />
      <button
        type="submit"
        disabled={disabled || !text.trim()}
        className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
      >
        Send
      </button>
    </form>
  );
}

/* ------------------------------------------------------------------ */
/*  ChatPanel                                                          */
/* ------------------------------------------------------------------ */

export interface ChatPanelProps {
  sessionId?: string;
  planId?: string;
  onPlanEvent?: (planId: string, action: "created" | "updated") => void;
}

export default function ChatPanel({
  sessionId,
  planId,
  onPlanEvent,
}: ChatPanelProps) {
  const { token } = useAuth();
  const { messages, isStreaming, error, sendMessage, retry, planEvents } =
    useChat({ token, sessionId, planId });

  // Notify parent of plan events
  const lastNotifiedRef = useRef(0);
  useEffect(() => {
    const newEvents = planEvents.slice(lastNotifiedRef.current);
    for (const evt of newEvents) {
      onPlanEvent?.(evt.planId, evt.action);
    }
    lastNotifiedRef.current = planEvents.length;
  }, [planEvents, onPlanEvent]);

  return (
    <div className="flex flex-col h-full border rounded-lg bg-white">
      <MessageList messages={messages} />

      {error && (
        <div
          role="alert"
          className="mx-4 mb-2 flex items-center justify-between rounded-md bg-destructive/10 px-4 py-2 text-sm text-destructive"
        >
          <span>{error}</span>
          <button
            onClick={retry}
            className="ml-3 rounded-md bg-destructive px-3 py-1 text-xs font-medium text-destructive-foreground hover:bg-destructive/90"
          >
            Retry
          </button>
        </div>
      )}

      <MessageInput onSend={sendMessage} disabled={isStreaming} />
    </div>
  );
}
