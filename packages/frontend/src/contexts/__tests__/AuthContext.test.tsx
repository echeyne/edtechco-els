import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { useAuth, AuthContextProvider } from "../AuthContext";

// Mock @descope/react-sdk so we never hit real Descope
vi.mock("@descope/react-sdk", () => ({
  AuthProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  useSession: () => ({ isAuthenticated: false, isSessionLoading: false, sessionToken: null }),
  useUser: () => ({ user: null }),
  useDescope: () => ({ logout: vi.fn() }),
}));

// Helper component that exposes auth values
function AuthConsumer() {
  const auth = useAuth();
  return (
    <div>
      <span data-testid="isAuthenticated">{String(auth.isAuthenticated)}</span>
      <span data-testid="hasEditPermission">{String(auth.hasEditPermission)}</span>
      <span data-testid="user">{auth.user ? auth.user.email : "null"}</span>
      <span data-testid="token">{auth.token ?? "null"}</span>
    </div>
  );
}

describe("AuthContext", () => {
  beforeEach(() => {
    vi.stubEnv("VITE_DESCOPE_PROJECT_ID", "");
  });

  it("provides unauthenticated fallback when no DESCOPE_PROJECT_ID is set", () => {
    render(
      <AuthContextProvider>
        <AuthConsumer />
      </AuthContextProvider>,
    );

    expect(screen.getByTestId("isAuthenticated")).toHaveTextContent("false");
    expect(screen.getByTestId("hasEditPermission")).toHaveTextContent("false");
    expect(screen.getByTestId("user")).toHaveTextContent("null");
    expect(screen.getByTestId("token")).toHaveTextContent("null");
  });

  it("useAuth returns correct default values", () => {
    render(
      <AuthContextProvider>
        <AuthConsumer />
      </AuthContextProvider>,
    );

    expect(screen.getByTestId("isAuthenticated")).toHaveTextContent("false");
    expect(screen.getByTestId("hasEditPermission")).toHaveTextContent("false");
    expect(screen.getByTestId("token")).toHaveTextContent("null");
  });

  it("hasEditPermission is false by default", () => {
    render(
      <AuthContextProvider>
        <AuthConsumer />
      </AuthContextProvider>,
    );

    expect(screen.getByTestId("hasEditPermission")).toHaveTextContent("false");
  });
});
