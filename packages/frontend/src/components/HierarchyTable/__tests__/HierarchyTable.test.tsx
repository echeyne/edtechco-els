import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { HierarchyTable, type FilterState } from "../index";
import type { Document, HierarchyResponse } from "@els/shared";

// ---- Mocks ----

const mockGetDocuments = vi.fn();
const mockGetHierarchy = vi.fn();
const mockGetFilters = vi.fn();

vi.mock("@/lib/api", () => ({
  getDocuments: (...args: unknown[]) => mockGetDocuments(...args),
  getHierarchy: (...args: unknown[]) => mockGetHierarchy(...args),
  getFilters: (...args: unknown[]) => mockGetFilters(...args),
}));

let mockHasEditPermission = false;

vi.mock("@/contexts/AuthContext", () => ({
  useAuth: () => ({
    isAuthenticated: false,
    user: null,
    hasEditPermission: mockHasEditPermission,
    login: vi.fn(),
    logout: vi.fn(),
    token: null,
  }),
}));

// ---- Test data ----

const mockDocument: Document = {
  id: 1,
  country: "US",
  state: "CA",
  title: "California ELS",
  versionYear: 2024,
  sourceUrl: null,
  s3Key: '',
  ageBand: "0-5",
  publishingAgency: "CA Dept of Ed",
  createdAt: new Date(),
};

const mockHierarchy: HierarchyResponse = {
  document: mockDocument,
  domains: [
    {
      id: 10,
      documentId: 1,
      code: "D1",
      name: "Language Development",
      description: "Language skills",
      humanVerified: true,
      verifiedAt: null,
      verifiedBy: null,
      editedAt: null,
      editedBy: null,
      strands: [
        {
          id: 20,
          domainId: 10,
          code: "S1",
          name: "Listening",
          deleted: false,
          description: null,
          humanVerified: false,
          verifiedAt: null,
          verifiedBy: null,
          editedAt: null,
          editedBy: null,
          subStrands: [],
          indicators: [],
          deletedAt: null,
          deletedBy: null
        },
      ],
      indicators: [],
      deleted: false,
      deletedAt: null,
      deletedBy: null
    },
  ],
};

// ---- Helpers ----

function renderTable(
  overrides?: Partial<{
    filters: FilterState;
    onFilterChange: (f: FilterState) => void;
    onEdit: (record: unknown, type: string) => void;
    onDelete: (id: number, type: string) => void;
  }>,
) {
  const defaultFilters: FilterState = {};
  return render(
    <HierarchyTable
      filters={overrides?.filters ?? defaultFilters}
      onFilterChange={overrides?.onFilterChange ?? vi.fn()}
      onEdit={overrides?.onEdit as never}
      onDelete={overrides?.onDelete as never}
    />,
  );
}

// ---- Tests ----

describe("HierarchyTable", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockHasEditPermission = false;
    mockGetFilters.mockResolvedValue({ countries: ["US"], states: ["CA", "NY"] });
  });

  it("renders loading state initially", () => {
    // Never resolve the documents call so it stays loading
    mockGetDocuments.mockReturnValue(new Promise(() => {}));
    renderTable();

    expect(screen.getByText(/loading hierarchy data/i)).toBeInTheDocument();
  });

  it("renders error state with retry button", async () => {
    mockGetDocuments.mockRejectedValueOnce(new Error("Network error"));
    renderTable();

    await waitFor(() => {
      expect(screen.getByText("Network error")).toBeInTheDocument();
    });
    expect(screen.getByRole("button", { name: /retry/i })).toBeInTheDocument();
  });

  it("renders 'No data found' when filters match nothing", async () => {
    mockGetDocuments.mockResolvedValue([]);
    renderTable();

    await waitFor(() => {
      expect(
        screen.getByText(/no data found matching the current filters/i),
      ).toBeInTheDocument();
    });
  });

  it("renders document rows when data loads", async () => {
    mockGetDocuments.mockResolvedValue([mockDocument]);
    mockGetHierarchy.mockResolvedValue(mockHierarchy);
    renderTable();

    await waitFor(() => {
      expect(screen.getByText("California ELS")).toBeInTheDocument();
    });
  });

  it("expand/collapse toggle works", async () => {
    mockGetDocuments.mockResolvedValue([mockDocument]);
    mockGetHierarchy.mockResolvedValue(mockHierarchy);
    renderTable();

    await waitFor(() => {
      expect(screen.getByText("California ELS")).toBeInTheDocument();
    });

    // Domain should not be visible yet (collapsed)
    expect(screen.queryByText("Language Development")).not.toBeInTheDocument();

    // Click expand on the document row
    const expandBtn = screen.getByLabelText("Expand");
    fireEvent.click(expandBtn);

    // Domain should now be visible
    await waitFor(() => {
      expect(screen.getByText("Language Development")).toBeInTheDocument();
    });

    // Click collapse
    const collapseBtn = screen.getByLabelText("Collapse");
    fireEvent.click(collapseBtn);

    await waitFor(() => {
      expect(screen.queryByText("Language Development")).not.toBeInTheDocument();
    });
  });

  it("filter bar renders with country/state/verification selects", async () => {
    mockGetDocuments.mockResolvedValue([]);
    renderTable();

    await waitFor(() => {
      expect(screen.getByPlaceholderText("Search standards...")).toBeInTheDocument();
    });

    // The select triggers should be present
    expect(screen.getByText("All Countries")).toBeInTheDocument();
    expect(screen.getByText("All States")).toBeInTheDocument();
    expect(screen.getByText("All Status")).toBeInTheDocument();
  });

  it("Edit/Delete buttons only show when hasEditPermission is true", async () => {
    mockGetDocuments.mockResolvedValue([mockDocument]);
    mockGetHierarchy.mockResolvedValue(mockHierarchy);

    // Without permission
    mockHasEditPermission = false;
    const { unmount } = renderTable();

    await waitFor(() => {
      expect(screen.getByText("California ELS")).toBeInTheDocument();
    });

    // Expand to see domain row
    fireEvent.click(screen.getByLabelText("Expand"));
    await waitFor(() => {
      expect(screen.getByText("Language Development")).toBeInTheDocument();
    });

    // No edit/delete buttons
    expect(screen.queryByLabelText("Edit")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Delete")).not.toBeInTheDocument();

    unmount();

    // With permission
    mockHasEditPermission = true;
    renderTable({
      onEdit: vi.fn(),
      onDelete: vi.fn(),
    });

    await waitFor(() => {
      expect(screen.getByText("California ELS")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByLabelText("Expand"));
    await waitFor(() => {
      expect(screen.getByText("Language Development")).toBeInTheDocument();
    });

    // Edit/Delete buttons should be present
    expect(screen.getByLabelText("Edit")).toBeInTheDocument();
    expect(screen.getByLabelText("Delete")).toBeInTheDocument();
  });

  it("Verified/Unverified badges display correctly", async () => {
    mockGetDocuments.mockResolvedValue([mockDocument]);
    mockGetHierarchy.mockResolvedValue(mockHierarchy);
    renderTable();

    await waitFor(() => {
      expect(screen.getByText("California ELS")).toBeInTheDocument();
    });

    // Expand document
    fireEvent.click(screen.getByLabelText("Expand"));
    await waitFor(() => {
      expect(screen.getByText("Language Development")).toBeInTheDocument();
    });

    // Domain is verified
    expect(screen.getByText("Verified")).toBeInTheDocument();

    // Expand domain to see strand
    const expandBtns = screen.getAllByLabelText("Expand");
    fireEvent.click(expandBtns[0]);
    await waitFor(() => {
      expect(screen.getByText("Listening")).toBeInTheDocument();
    });

    // Strand is unverified
    expect(screen.getByText("Unverified")).toBeInTheDocument();
  });

  it("retry button re-fetches data", async () => {
    mockGetDocuments.mockRejectedValueOnce(new Error("Network error"));
    renderTable();

    await waitFor(() => {
      expect(screen.getByText("Network error")).toBeInTheDocument();
    });

    // Now make it succeed
    mockGetDocuments.mockResolvedValue([mockDocument]);
    mockGetHierarchy.mockResolvedValue(mockHierarchy);

    fireEvent.click(screen.getByRole("button", { name: /retry/i }));

    await waitFor(() => {
      expect(screen.getByText("California ELS")).toBeInTheDocument();
    });
  });
});
