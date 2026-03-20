import { useRef, useEffect } from "react";
import Markdown from "react-markdown";
import {
  MainContainer,
  ChatContainer,
  MessageList,
  Message,
  MessageInput,
  TypingIndicator,
} from "@chatscope/chat-ui-kit-react";
import "@chatscope/chat-ui-kit-styles/dist/default/styles.min.css";
import { useChat } from "@/hooks/useChat";
import { useAuth } from "@/contexts/AuthContext";

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

  const handleSend = (_innerHTML: string, textContent: string) => {
    const trimmed = textContent.trim();
    if (trimmed) {
      sendMessage(trimmed);
    }
  };

  return (
    <div style={{ height: "100%", position: "relative" }}>
      <MainContainer>
        <ChatContainer>
          <MessageList
            typingIndicator={
              isStreaming ? (
                <TypingIndicator content="Assistant is typing" />
              ) : undefined
            }
          >
            {messages.map((msg, i) => (
              <Message
                key={i}
                model={{
                  message: msg.role === "user" ? msg.content : "",
                  direction: msg.role === "user" ? "outgoing" : "incoming",
                  position: "single",
                }}
              >
                {msg.role === "assistant" && (
                  <Message.CustomContent>
                    <Markdown>{msg.content}</Markdown>
                  </Message.CustomContent>
                )}
              </Message>
            ))}
          </MessageList>

          <MessageInput
            placeholder="Type your message…"
            onSend={handleSend}
            disabled={isStreaming}
            attachButton={false}
          />
        </ChatContainer>
      </MainContainer>

      {error && (
        <div
          role="alert"
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            padding: "8px 16px",
            backgroundColor: "#fef2f2",
            color: "#dc2626",
            fontSize: "0.875rem",
            borderTop: "1px solid #fecaca",
          }}
        >
          <span>{error}</span>
          <button
            onClick={retry}
            style={{
              marginLeft: "12px",
              padding: "4px 12px",
              backgroundColor: "#dc2626",
              color: "#fff",
              border: "none",
              borderRadius: "4px",
              fontSize: "0.75rem",
              fontWeight: 500,
              cursor: "pointer",
            }}
          >
            Retry
          </button>
        </div>
      )}
    </div>
  );
}
