import { describe, it, expect, vi, beforeAll, afterAll, afterEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import type { ReactNode } from "react";

// ---- Mock @descope/react-sdk ----

let mockAuthState = {
  isAuthenticated: false,
  isSessionLoading: false,
  sessionToken: null as string | null,
  user: null as {
    userId: string;
    email: string;
    customAttributes?: Record<string, unknown>;
  } | null,
};

vi.mock("@descope/react-sdk", () => ({
  AuthProvider: ({ children }: { children: ReactNode }) => <>{children}</>,
  useSession: () => ({
    isAuthenticated: mockAuthState.isAuthenticated,
    isSessionLoading: mockAuthState.isSessionLoading,
    sessionToken: mockAuthState.sessionToken,
  }),
  useUser: () => ({ user: mockAuthState.user }),
  useDescope: () => ({
    logout: vi.fn(),
  }),
}));

// ---- Mock data ----

const mockDocuments = [
  {
    id: 1,
    country: "US",
    state: "CA",
    title: "California ELS",
    versionYear: 2023,
    sourceUrl: null,
    ageBand: "0-5",
    publishingAgency: "CA Dept of Ed",
    createdAt: "2024-01-01T00:00:00.000Z",
  },
];

const mockHierarchy = {
  document: mockDocuments[0],
  domains: [
    {
      id: 10,
      documentId: 1,
      code: "D1",
      name: "Language",
      description: null,
      humanVerified: false,
      verifiedAt: null,
      verifiedBy: null,
      editedAt: null,
      editedBy: null,
      strands: [],
    },
  ],
};

const mockFilters = { countries: ["US"], states: ["CA"] };

// ---- MSW server ----

const handlers = [
  http.get("*/api/documents", () => HttpResponse.json(mockDocuments)),
  http.get("*/api/documents/:id/hierarchy", () =>
    HttpResponse.json(mockHierarchy),
  ),
  http.get("*/api/filters", () => HttpResponse.json(mockFilters)),
];

const server = setupServer(...handlers);

beforeAll(() => server.listen());
afterEach(() => {
  server.resetHandlers();
  mockAuthState = {
    isAuthenticated: false,
    isSessionLoading: false,
    sessionToken: null,
    user: null,
  };
});
afterAll(() => server.close());

// Set VITE_DESCOPE_PROJECT_ID so AuthContextProvider doesn't short-circuit
// to the unauthenticated fallback. Must be set before AuthContext module loads.
import.meta.env.VITE_DESCOPE_PROJECT_ID = "test-project-id";

// ---- Lazy imports (after mocks) ----

async function importHomePage() {
  const mod = await import("@/pages/HomePage");
  return mod.default;
}

async function importAuthContextProvider() {
  const mod = await import("@/contexts/AuthContext");
  return mod.AuthContextProvider;
}

// Helper: render HomePage, wait for data, expand document row to show domains
async function renderAndExpand(authState: typeof mockAuthState) {
  mockAuthState = authState;

  const HomePage = await importHomePage();
  const AuthContextProvider = await importAuthContextProvider();

  render(
    <MemoryRouter>
      <AuthContextProvider>
        <HomePage />
      </AuthContextProvider>
    </MemoryRouter>,
  );

  // Wait for the document title to appear (data loaded)
  const docTitle = await screen.findByText("California ELS", {}, { timeout: 3000 });
  expect(docTitle).toBeInTheDocument();

  // Expand the document row to reveal domain rows with edit controls
  const expandBtn = screen.getByLabelText("Expand");
  fireEvent.click(expandBtn);

  // Domain "Language" should now be visible
  expect(await screen.findByText("Language")).toBeInTheDocument();
}

describe("Auth flow integration", () => {
  it("unauthenticated user sees no edit controls", async () => {
    await renderAndExpand({
      isAuthenticated: false,
      isSessionLoading: false,
      sessionToken: null,
      user: null,
    });

    // No Actions column header, no edit/delete buttons
    expect(screen.queryByText("Actions")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Edit")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Delete")).not.toBeInTheDocument();
  });

  it("authenticated user with canEdit sees edit controls", async () => {
    await renderAndExpand({
      isAuthenticated: true,
      isSessionLoading: false,
      sessionToken: "valid-token",
      user: {
        userId: "u1",
        email: "editor@test.com",
        customAttributes: { canEdit: true },
      },
    });

    // Actions column and edit/delete buttons should be present
    expect(screen.getByText("Actions")).toBeInTheDocument();
    expect(screen.getAllByLabelText("Edit").length).toBeGreaterThan(0);
    expect(screen.getAllByLabelText("Delete").length).toBeGreaterThan(0);
  });

  it("authenticated user without canEdit sees read-only mode", async () => {
    await renderAndExpand({
      isAuthenticated: true,
      isSessionLoading: false,
      sessionToken: "valid-token",
      user: {
        userId: "u2",
        email: "viewer@test.com",
        customAttributes: { canEdit: false },
      },
    });

    // No edit or delete buttons
    expect(screen.queryByText("Actions")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Edit")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Delete")).not.toBeInTheDocument();
  });

  it("token is included in API requests when authenticated", async () => {
    let capturedAuthHeader: string | null = null;

    server.use(
      http.put("*/api/domains/:id", ({ request }) => {
        capturedAuthHeader = request.headers.get("Authorization");
        return HttpResponse.json({
          id: 10, documentId: 1, code: "D1", name: "Updated",
          description: null, humanVerified: false, verifiedAt: null,
          verifiedBy: null, editedAt: null, editedBy: null,
        });
      }),
    );

    // Directly test the API client includes the token
    const { updateDomain } = await import("@/lib/api");
    await updateDomain(10, { name: "Updated" }, "my-auth-token");

    expect(capturedAuthHeader).toBe("Bearer my-auth-token");
  });
});
