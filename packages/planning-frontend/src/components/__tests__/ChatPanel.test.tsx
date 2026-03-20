import { render, screen, fireEvent } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

// Mock auth context
vi.mock("@/contexts/AuthContext", () => ({
  useAuth: () => ({ token: "test-token" }),
}));

// Mock useChat with controllable return value
const mockUseChat = vi.fn();
vi.mock("@/hooks/useChat", () => ({
  useChat: (...args: unknown[]) => mockUseChat(...args),
}));

// Mock react-markdown to avoid complex rendering
vi.mock("react-markdown", () => ({
  default: ({ children }: { children: string }) => (
    <div data-testid="markdown">{children}</div>
  ),
}));

import ChatPanel from "../ChatPanel";

const defaultUseChatReturn = {
  messages: [],
  isStreaming: false,
  error: null,
  sendMessage: vi.fn(),
  retry: vi.fn(),
  planEvents: [],
};

describe("ChatPanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseChat.mockReturnValue({ ...defaultUseChatReturn });
  });

  it("renders typing indicator when isStreaming is true", () => {
    mockUseChat.mockReturnValue({
      ...defaultUseChatReturn,
      isStreaming: true,
    });

    render(<ChatPanel />);

    expect(screen.getByText("Assistant is typing")).toBeInTheDocument();
  });

  it("disables message input when isStreaming is true", () => {
    mockUseChat.mockReturnValue({
      ...defaultUseChatReturn,
      isStreaming: true,
    });

    const { container } = render(<ChatPanel />);

    // chatscope MessageInput uses a contenteditable div, not a native input
    // When disabled, it sets contenteditable="false" and adds --disabled class
    const editor = container.querySelector(".cs-message-input__content-editor");
    expect(editor).toBeInTheDocument();
    expect(editor).toHaveAttribute("contenteditable", "false");
  });

  it("displays inline error message when error state is set", () => {
    mockUseChat.mockReturnValue({
      ...defaultUseChatReturn,
      error: "Connection lost",
    });

    render(<ChatPanel />);

    const alert = screen.getByRole("alert");
    expect(alert).toBeInTheDocument();
    expect(alert).toHaveTextContent("Connection lost");
  });

  it("shows retry button when error state is set and clicking it calls retry", () => {
    const retryFn = vi.fn();
    mockUseChat.mockReturnValue({
      ...defaultUseChatReturn,
      error: "Connection error",
      retry: retryFn,
    });

    render(<ChatPanel />);

    const retryButton = screen.getByRole("button", { name: /retry/i });
    expect(retryButton).toBeInTheDocument();

    fireEvent.click(retryButton);
    expect(retryFn).toHaveBeenCalledOnce();
  });

  it("forwards planId prop to useChat call", () => {
    render(<ChatPanel planId="plan-123" />);

    expect(mockUseChat).toHaveBeenCalledWith({
      token: "test-token",
      sessionId: undefined,
      planId: "plan-123",
    });
  });

  it("renders markdown content in assistant messages", () => {
    mockUseChat.mockReturnValue({
      ...defaultUseChatReturn,
      messages: [{ role: "assistant", content: "**bold text**" }],
    });

    render(<ChatPanel />);

    const markdown = screen.getByTestId("markdown");
    expect(markdown).toHaveTextContent("**bold text**");
  });

  it("user messages have outgoing direction and assistant messages have incoming direction", () => {
    mockUseChat.mockReturnValue({
      ...defaultUseChatReturn,
      messages: [
        { role: "user", content: "Hello" },
        { role: "assistant", content: "Hi there" },
      ],
    });

    const { container } = render(<ChatPanel />);

    // chatscope renders direction as data attributes or CSS classes
    // outgoing messages get class containing "outgoing", incoming get "incoming"
    const outgoing = container.querySelectorAll('[class*="outgoing"]');
    const incoming = container.querySelectorAll('[class*="incoming"]');

    expect(outgoing.length).toBeGreaterThan(0);
    expect(incoming.length).toBeGreaterThan(0);
  });
});
