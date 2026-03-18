import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { EditModal, type EditModalProps } from "../index";
import type { Domain, Indicator } from "@els/shared";

// ---- Mocks ----

const mockUpdateDomain = vi.fn();
const mockUpdateIndicator = vi.fn();
const mockVerifyDomain = vi.fn();
const mockVerifyIndicator = vi.fn();

vi.mock("@/lib/api", () => ({
  updateDomain: (...args: unknown[]) => mockUpdateDomain(...args),
  updateStrand: vi.fn(),
  updateSubStrand: vi.fn(),
  updateIndicator: (...args: unknown[]) => mockUpdateIndicator(...args),
  verifyDomain: (...args: unknown[]) => mockVerifyDomain(...args),
  verifyStrand: vi.fn(),
  verifySubStrand: vi.fn(),
  verifyIndicator: (...args: unknown[]) => mockVerifyIndicator(...args),
}));

vi.mock("@/contexts/AuthContext", () => ({
  useAuth: () => ({
    isAuthenticated: true,
    user: { id: "u1", email: "test@example.com", canEdit: true },
    hasEditPermission: true,
    login: vi.fn(),
    logout: vi.fn(),
    token: "test-token",
  }),
}));

// ---- Test data ----

const mockDomain: Domain = {
  id: 10,
  documentId: 1,
  code: "D1",
  name: "Language Development",
  description: "Language skills",
  humanVerified: false,
  verifiedAt: null,
  verifiedBy: null,
  editedAt: null,
  editedBy: null,
};

const mockIndicator: Indicator = {
  id: 100,
  standardId: "STD-1",
  domainId: 10,
  strandId: 20,
  subStrandId: 30,
  code: "I1",
  title: "Indicator Title",
  description: "Indicator description",
  ageBand: "3-5",
  sourcePage: 42,
  sourceText: "Source text here",
  humanVerified: false,
  verifiedAt: null,
  verifiedBy: null,
  editedAt: null,
  editedBy: null,
  lastVerified: null,
  createdAt: new Date(),
};

// ---- Helpers ----

function renderModal(overrides?: Partial<EditModalProps>) {
  const defaults: EditModalProps = {
    open: true,
    onOpenChange: vi.fn(),
    record: mockDomain,
    recordType: "domain",
    onSave: vi.fn(),
  };
  return render(<EditModal {...defaults} {...overrides} />);
}

// ---- Tests ----

describe("EditModal", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders correct fields for domain type (code, name, description)", () => {
    renderModal({ record: mockDomain, recordType: "domain" });

    expect(screen.getByLabelText("Code")).toBeInTheDocument();
    expect(screen.getByLabelText("Name")).toBeInTheDocument();
    expect(screen.getByLabelText("Description")).toBeInTheDocument();

    // Indicator-only fields should NOT be present
    expect(screen.queryByLabelText("Title")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Age Band")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Source Page")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Source Text")).not.toBeInTheDocument();
  });

  it("renders correct fields for indicator type", () => {
    renderModal({ record: mockIndicator, recordType: "indicator" });

    expect(screen.getByLabelText("Code")).toBeInTheDocument();
    expect(screen.getByLabelText("Title")).toBeInTheDocument();
    expect(screen.getByLabelText("Description")).toBeInTheDocument();
    expect(screen.getByLabelText("Age Band")).toBeInTheDocument();
    expect(screen.getByLabelText("Source Page")).toBeInTheDocument();
    expect(screen.getByLabelText("Source Text")).toBeInTheDocument();

    // Domain-only field should NOT be present
    expect(screen.queryByLabelText("Name")).not.toBeInTheDocument();
  });

  it("populates form fields with record values", () => {
    renderModal({ record: mockDomain, recordType: "domain" });

    expect(screen.getByLabelText("Code")).toHaveValue("D1");
    expect(screen.getByLabelText("Name")).toHaveValue("Language Development");
    expect(screen.getByLabelText("Description")).toHaveValue("Language skills");
  });

  it("human verified checkbox is present", () => {
    renderModal({ record: mockDomain, recordType: "domain" });

    expect(screen.getByLabelText("Human Verified")).toBeInTheDocument();
  });

  it("save button calls the appropriate API update function for domain", async () => {
    const updatedDomain = { ...mockDomain, name: "Updated Name" };
    mockUpdateDomain.mockResolvedValue(updatedDomain);
    const onSave = vi.fn();

    renderModal({ record: mockDomain, recordType: "domain", onSave });

    // Click save
    fireEvent.click(screen.getByRole("button", { name: /save/i }));

    await waitFor(() => {
      expect(mockUpdateDomain).toHaveBeenCalledWith(
        10,
        {
          code: "D1",
          name: "Language Development",
          description: "Language skills",
          documentId: 1,
        },
        "test-token",
      );
    });

    await waitFor(() => {
      expect(onSave).toHaveBeenCalledWith(updatedDomain);
    });
  });

  it("save button calls the appropriate API update function for indicator", async () => {
    const updatedIndicator = { ...mockIndicator, title: "Updated Title" };
    mockUpdateIndicator.mockResolvedValue(updatedIndicator);
    const onSave = vi.fn();

    renderModal({ record: mockIndicator, recordType: "indicator", onSave });

    fireEvent.click(screen.getByRole("button", { name: /save/i }));

    await waitFor(() => {
      expect(mockUpdateIndicator).toHaveBeenCalledWith(
        100,
        {
          code: "I1",
          title: "Indicator Title",
          description: "Indicator description",
          ageBand: "3-5",
          sourcePage: 42,
          sourceText: "Source text here",
          subStrandId: 30,
        },
        "test-token",
      );
    });

    await waitFor(() => {
      expect(onSave).toHaveBeenCalledWith(updatedIndicator);
    });
  });

  it("cancel button closes the modal", () => {
    const onOpenChange = vi.fn();
    renderModal({ onOpenChange });

    fireEvent.click(screen.getByRole("button", { name: /cancel/i }));

    expect(onOpenChange).toHaveBeenCalledWith(false);
  });

  it("error message displays on save failure", async () => {
    mockUpdateDomain.mockRejectedValue(new Error("Server error"));
    renderModal({ record: mockDomain, recordType: "domain" });

    fireEvent.click(screen.getByRole("button", { name: /save/i }));

    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent("Server error");
    });
  });
});
