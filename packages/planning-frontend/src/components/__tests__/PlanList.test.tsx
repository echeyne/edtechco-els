import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, it, expect, vi, beforeEach } from "vitest";
import PlanList from "../PlanList";
import type { PlanSummary } from "@/types";

// Mock auth context
vi.mock("@/contexts/AuthContext", () => ({
  useAuth: () => ({ token: "test-token" }),
}));

const samplePlans: PlanSummary[] = [
  {
    id: "plan-1",
    childName: "Emma",
    childAge: "4",
    state: "CA",
    duration: "2-weeks",
    status: "active",
    createdAt: "2025-01-15T10:00:00Z",
    updatedAt: "2025-01-15T10:00:00Z",
  },
  {
    id: "plan-2",
    childName: "Liam",
    childAge: "3",
    state: "NY",
    duration: "1-week",
    status: "active",
    createdAt: "2025-01-10T08:00:00Z",
    updatedAt: "2025-01-12T09:00:00Z",
  },
];

function renderPlanList(props: { onStartNew?: () => void } = {}) {
  return render(
    <MemoryRouter>
      <PlanList {...props} />
    </MemoryRouter>,
  );
}

describe("PlanList", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("renders plan summary cards from fetched data", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce({
      ok: true,
      json: async () => samplePlans,
    } as Response);

    renderPlanList();

    await waitFor(() => {
      expect(screen.getAllByTestId("plan-card")).toHaveLength(2);
    });

    expect(screen.getByText("Emma's Plan")).toBeInTheDocument();
    expect(screen.getByText("Liam's Plan")).toBeInTheDocument();
    expect(screen.getByText("CA · Age 4 · 2-weeks")).toBeInTheDocument();
    expect(screen.getByText("NY · Age 3 · 1-week")).toBeInTheDocument();
  });

  it("renders empty state when no plans exist", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce({
      ok: true,
      json: async () => [],
    } as Response);

    renderPlanList();

    await waitFor(() => {
      expect(screen.getByTestId("empty-state")).toBeInTheDocument();
    });

    expect(
      screen.getByText("You don't have any plans yet."),
    ).toBeInTheDocument();
    expect(screen.getByText("Start a new plan")).toBeInTheDocument();
  });

  it("calls onStartNew when CTA button is clicked in empty state", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce({
      ok: true,
      json: async () => [],
    } as Response);

    const onStartNew = vi.fn();
    renderPlanList({ onStartNew });

    await waitFor(() => {
      expect(screen.getByTestId("empty-state")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText("Start a new plan"));
    expect(onStartNew).toHaveBeenCalledOnce();
  });

  it("shows loading state initially", () => {
    // Never-resolving fetch to keep loading state
    vi.spyOn(globalThis, "fetch").mockReturnValueOnce(new Promise(() => {}));

    renderPlanList();

    expect(screen.getByText("Loading plans…")).toBeInTheDocument();
  });

  it("shows error state on fetch failure", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce({
      ok: false,
      status: 500,
      statusText: "Internal Server Error",
      text: () => Promise.resolve("Failed to load plans (500)"),
    } as unknown as Response);

    renderPlanList();

    await waitFor(() => {
      expect(screen.getByRole("alert")).toBeInTheDocument();
    });

    expect(screen.getByText("Failed to load plans (500)")).toBeInTheDocument();
  });

  it("renders plan status badges", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce({
      ok: true,
      json: async () => samplePlans,
    } as Response);

    renderPlanList();

    await waitFor(() => {
      expect(screen.getAllByText("active")).toHaveLength(2);
    });
  });
});
