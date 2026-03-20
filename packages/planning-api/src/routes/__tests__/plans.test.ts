import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { Hono } from "hono";
import type { AuthEnv } from "../../middleware/auth.js";
import { requireAuth, setDescopeClient } from "../../middleware/auth.js";
import type { PlanDetail, PlanSummary } from "../../types.js";

// Mock the db functions
vi.mock("../../db/plans.js", () => ({
  getPlansByUserId: vi.fn(),
  getPlanById: vi.fn(),
  deletePlan: vi.fn(),
}));

import { getPlansByUserId, getPlanById, deletePlan } from "../../db/plans.js";

const mockedGetPlansByUserId = vi.mocked(getPlansByUserId);
const mockedGetPlanById = vi.mocked(getPlanById);
const mockedDeletePlan = vi.mocked(deletePlan);

// ---- Test constants ----

const TEST_USER_ID = "user-test-abc-123";
const OTHER_USER_ID = "user-other-xyz-789";

const SAMPLE_PLAN_SUMMARY: PlanSummary = {
  id: "plan-001",
  childName: "Alice",
  childAge: "4",
  state: "CA",
  duration: "4-weeks",
  status: "active",
  createdAt: "2024-06-01T00:00:00Z",
  updatedAt: "2024-06-01T00:00:00Z",
};

const SAMPLE_PLAN_DETAIL: PlanDetail = {
  ...SAMPLE_PLAN_SUMMARY,
  interests: "dinosaurs, painting",
  concerns: null,
  content: {
    sections: [
      {
        label: "Week 1",
        activities: [
          {
            title: "Dino Counting",
            description: "Count toy dinosaurs together",
            indicatorCode: "CA.MA.1.1",
            indicatorDescription: "Counts objects to 10",
            domain: "Mathematics",
            strand: "Number Sense",
          },
        ],
      },
    ],
    summary: "A 4-week plan focused on math and art for Alice.",
  },
};

// ---- Helpers ----

function createMockDescopeClient(userId: string) {
  return {
    validateSession: vi.fn().mockResolvedValue({
      token: { sub: userId },
    }),
  } as unknown as ReturnType<typeof import("@descope/node-sdk").default>;
}

function createApp() {
  // Import the plans route dynamically to pick up mocks
  // We build a fresh Hono app that mirrors the real setup
  const app = new Hono<AuthEnv>();
  app.use("/api/plans/*", requireAuth);
  app.use("/api/plans", requireAuth);

  // GET /api/plans — list plans
  app.get("/api/plans", async (c) => {
    const userId = c.get("userId");
    const userPlans = await getPlansByUserId(userId);
    return c.json(userPlans);
  });

  // GET /api/plans/:id — get plan detail
  app.get("/api/plans/:id", async (c) => {
    const userId = c.get("userId");
    const id = c.req.param("id");
    const plan = await getPlanById(id, userId);
    if (!plan) {
      return c.json(
        { error: { code: "NOT_FOUND", message: "Plan not found" } },
        404,
      );
    }
    return c.json(plan);
  });

  // DELETE /api/plans/:id — delete plan
  app.delete("/api/plans/:id", async (c) => {
    const userId = c.get("userId");
    const id = c.req.param("id");
    const deleted = await deletePlan(id, userId);
    if (!deleted) {
      return c.json(
        { error: { code: "NOT_FOUND", message: "Plan not found" } },
        404,
      );
    }
    return c.body(null, 204);
  });

  return app;
}

function authHeaders(token = "valid-token") {
  return { Authorization: `Bearer ${token}` };
}

// ---- Tests ----

describe("Plan CRUD endpoints", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    setDescopeClient(createMockDescopeClient(TEST_USER_ID));
  });

  afterEach(() => {
    setDescopeClient(null);
  });

  // --- GET /api/plans ---

  describe("GET /api/plans", () => {
    it("returns a list of plans for the authenticated user", async () => {
      const plans: PlanSummary[] = [
        SAMPLE_PLAN_SUMMARY,
        { ...SAMPLE_PLAN_SUMMARY, id: "plan-002", childName: "Bob" },
      ];
      mockedGetPlansByUserId.mockResolvedValueOnce(plans);
      const app = createApp();

      const res = await app.request("/api/plans", {
        headers: authHeaders(),
      });

      expect(res.status).toBe(200);
      const body = await res.json();
      expect(body).toHaveLength(2);
      expect(body[0].id).toBe("plan-001");
      expect(body[1].childName).toBe("Bob");
      expect(mockedGetPlansByUserId).toHaveBeenCalledWith(TEST_USER_ID);
    });

    it("returns an empty array when user has no plans", async () => {
      mockedGetPlansByUserId.mockResolvedValueOnce([]);
      const app = createApp();

      const res = await app.request("/api/plans", {
        headers: authHeaders(),
      });

      expect(res.status).toBe(200);
      const body = await res.json();
      expect(body).toEqual([]);
    });
  });

  // --- GET /api/plans/:id ---

  describe("GET /api/plans/:id", () => {
    it("returns full plan detail for a plan owned by the user", async () => {
      mockedGetPlanById.mockResolvedValueOnce(SAMPLE_PLAN_DETAIL);
      const app = createApp();

      const res = await app.request("/api/plans/plan-001", {
        headers: authHeaders(),
      });

      expect(res.status).toBe(200);
      const body = await res.json();
      expect(body.id).toBe("plan-001");
      expect(body.childName).toBe("Alice");
      expect(body.content.sections).toHaveLength(1);
      expect(body.content.sections[0].activities[0].indicatorCode).toBe(
        "CA.MA.1.1",
      );
      expect(mockedGetPlanById).toHaveBeenCalledWith("plan-001", TEST_USER_ID);
    });

    it("returns 404 when plan is not found", async () => {
      mockedGetPlanById.mockResolvedValueOnce(null);
      const app = createApp();

      const res = await app.request("/api/plans/nonexistent-id", {
        headers: authHeaders(),
      });

      expect(res.status).toBe(404);
      const body = await res.json();
      expect(body.error.code).toBe("NOT_FOUND");
      expect(body.error.message).toBe("Plan not found");
    });

    it("returns 404 when plan belongs to another user (ownership rejection)", async () => {
      // getPlanById scoped to userId returns null for plans not owned by user
      mockedGetPlanById.mockResolvedValueOnce(null);
      const app = createApp();

      const res = await app.request("/api/plans/plan-owned-by-other", {
        headers: authHeaders(),
      });

      expect(res.status).toBe(404);
      const body = await res.json();
      expect(body.error.code).toBe("NOT_FOUND");
    });
  });

  // --- DELETE /api/plans/:id ---

  describe("DELETE /api/plans/:id", () => {
    it("deletes a plan owned by the user and returns 204", async () => {
      mockedDeletePlan.mockResolvedValueOnce(true);
      const app = createApp();

      const res = await app.request("/api/plans/plan-001", {
        method: "DELETE",
        headers: authHeaders(),
      });

      expect(res.status).toBe(204);
      expect(mockedDeletePlan).toHaveBeenCalledWith("plan-001", TEST_USER_ID);
    });

    it("returns 404 when trying to delete a non-existent plan", async () => {
      mockedDeletePlan.mockResolvedValueOnce(false);
      const app = createApp();

      const res = await app.request("/api/plans/nonexistent-id", {
        method: "DELETE",
        headers: authHeaders(),
      });

      expect(res.status).toBe(404);
      const body = await res.json();
      expect(body.error.code).toBe("NOT_FOUND");
    });

    it("returns 404 when trying to delete a plan owned by another user", async () => {
      // deletePlan scoped to userId returns false for plans not owned by user
      mockedDeletePlan.mockResolvedValueOnce(false);
      const app = createApp();

      const res = await app.request("/api/plans/plan-owned-by-other", {
        method: "DELETE",
        headers: authHeaders(),
      });

      expect(res.status).toBe(404);
      const body = await res.json();
      expect(body.error.code).toBe("NOT_FOUND");
    });
  });

  // --- Auth rejection ---

  describe("Authentication required", () => {
    it("returns 401 when no auth token is provided", async () => {
      const app = createApp();

      const res = await app.request("/api/plans");

      expect(res.status).toBe(401);
      const body = await res.json();
      expect(body.error.code).toBe("UNAUTHORIZED");
    });
  });
});
