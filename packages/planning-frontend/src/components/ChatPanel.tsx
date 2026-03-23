import { useRef, useEffect, useState } from "react";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Send } from "lucide-react";
import { useChat } from "@/hooks/useChat";
import { useAuth } from "@/contexts/AuthContext";

export interface ChatPanelProps {
  sessionId?: string;
  planId?: string;
  onPlanEvent?: (planId: string, action: "created" | "updated") => void;
}

const SUGGESTIONS = [
  "What can you do?",
  "I want to create a plan",
  "I want to edit an existing plan",
];

export default function ChatPanel({
  sessionId,
  planId,
  onPlanEvent,
}: ChatPanelProps) {
  const { token } = useAuth();
  const { messages, isStreaming, error, sendMessage, retry, planEvents } =
    useChat({ token, sessionId, planId });

  const [input, setInput] = useState("");
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Notify parent of plan events
  const lastNotifiedRef = useRef(0);
  useEffect(() => {
    const newEvents = planEvents.slice(lastNotifiedRef.current);
    for (const evt of newEvents) {
      onPlanEvent?.(evt.planId, evt.action);
    }
    lastNotifiedRef.current = planEvents.length;
  }, [planEvents, onPlanEvent]);

  // Scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSend = (text: string) => {
    const trimmed = text.trim();
    if (!trimmed || isStreaming) return;
    setInput("");
    sendMessage(trimmed);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend(input);
    }
  };

  // Visible messages: skip the trailing empty assistant placeholder while streaming
  const visibleMessages = messages.filter(
    (msg, i) =>
      !(
        msg.role === "assistant" &&
        msg.content === "" &&
        i === messages.length - 1 &&
        isStreaming
      ),
  );

  const showSuggestions = messages.length === 0 && !isStreaming;

  /** Normalise agent markdown so it renders with proper spacing. */
  const formatContent = (raw: string) => raw.replace(/\.([A-Z])/g, ". $1");

  return (
    <div className="flex flex-col h-full min-h-0 rounded-xl border border-slate-200 bg-white shadow-sm overflow-hidden">
      {/* Message area */}
      <div className="flex-1 overflow-y-auto px-4 py-4 space-y-3 min-h-0 flex flex-col">
        {showSuggestions && (
          <div className="flex flex-col items-center justify-center flex-1 gap-4 py-8">
            <p className="text-sm text-slate-400">How can I help you today?</p>
            <div className="flex flex-wrap gap-2 justify-center">
              {SUGGESTIONS.map((s) => (
                <button
                  key={s}
                  onClick={() => handleSend(s)}
                  className="rounded-full border border-slate-200 bg-slate-50 px-4 py-2 text-sm text-slate-600 hover:bg-primary/10 hover:border-primary/30 hover:text-primary transition-colors"
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}

        {visibleMessages.map((msg, i) => (
          <div
            key={i}
            className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
          >
            <div
              className={`max-w-[75%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed ${
                msg.role === "user"
                  ? "bg-primary text-primary-foreground rounded-br-sm"
                  : "bg-slate-100 text-slate-800 rounded-bl-sm"
              }`}
            >
              {msg.role === "assistant" ? (
                <div className="prose prose-sm max-w-none prose-ul:my-3 prose-ol:my-3 prose-li:my-1 prose-headings:mt-5 prose-headings:mb-2 prose-hr:my-6 [&>*:first-child]:mt-0 [&>*:last-child]:mb-0">
                  <Markdown
                    remarkPlugins={[remarkGfm]}
                    components={{
                      p: ({ children }) => <p className="py-2">{children}</p>,
                    }}
                  >
                    {formatContent(msg.content)}
                  </Markdown>
                </div>
              ) : (
                msg.content
              )}
            </div>
          </div>
        ))}

        {isStreaming && (
          <div className="flex justify-start">
            <div className="bg-slate-100 rounded-2xl rounded-bl-sm px-4 py-3">
              <span className="flex gap-1 items-center">
                <span className="w-1.5 h-1.5 rounded-full bg-slate-400 animate-bounce [animation-delay:0ms]" />
                <span className="w-1.5 h-1.5 rounded-full bg-slate-400 animate-bounce [animation-delay:150ms]" />
                <span className="w-1.5 h-1.5 rounded-full bg-slate-400 animate-bounce [animation-delay:300ms]" />
              </span>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Error bar */}
      {error && (
        <div className="flex items-center justify-between px-4 py-2 bg-red-50 border-t border-red-200 text-red-600 text-sm">
          <span>{error}</span>
          <button
            onClick={retry}
            className="ml-3 px-3 py-1 bg-red-600 text-white rounded text-xs font-medium hover:bg-red-700 transition-colors"
          >
            Retry
          </button>
        </div>
      )}

      {/* Input area */}
      <div className="border-t border-slate-200 bg-slate-50 px-3 py-3">
        <div className="flex items-center gap-2 rounded-xl border border-slate-300 bg-white px-3 py-2 focus-within:border-primary focus-within:ring-1 focus-within:ring-primary/30 transition-all">
          <textarea
            ref={textareaRef}
            rows={1}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={isStreaming}
            placeholder="Ask me anything…"
            className="flex-1 resize-none bg-transparent text-sm text-slate-800 placeholder:text-slate-400 outline-none max-h-32 leading-relaxed disabled:opacity-50"
            style={{ fieldSizing: "content" } as React.CSSProperties}
          />
          <button
            onClick={() => handleSend(input)}
            disabled={!input.trim() || isStreaming}
            className="flex-shrink-0 rounded-lg bg-primary p-1.5 text-primary-foreground disabled:opacity-40 hover:bg-primary/90 transition-colors"
            aria-label="Send message"
          >
            <Send className="h-4 w-4" />
          </button>
        </div>
        <p className="mt-1.5 text-center text-xs text-slate-400">
          Press Enter to send · Shift+Enter for new line
        </p>
      </div>
    </div>
  );
}
