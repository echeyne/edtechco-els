import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { getPlans, getPlan, deletePlan, getSessionUrl, ApiError } from "../api";
import type { PlanSummary, PlanDetail } from "@/types";

/* ------------------------------------------------------------------ */
/*  Helpers                                                            */
/* ------------------------------------------------------------------ */

const sampleSummary: PlanSummary = {
  id: "plan-1",
  childName: "Alice",
  childAge: "4",
  state: "CA",
  duration: "4-weeks",
  status: "active",
  createdAt: "2025-01-01T00:00:00Z",
  updatedAt: "2025-01-01T00:00:00Z",
};

const sampleDetail: PlanDetail = {
  ...sampleSummary,
  interests: "dinosaurs",
  concerns: null,
  content: {
    summary: "A fun plan",
    sections: [
      {
        label: "Week 1",
        activities: [
          {
            title: "Dino counting",
            description: "Count toy dinosaurs",
            indicatorCode: "MA.PK.1.1",
            indicatorDescription: "Counts objects",
            domain: "Mathematics",
          },
        ],
      },
    ],
  },
};

function mockFetchJson(data: unknown, status = 200) {
  return vi.fn().mockResolvedValue({
    ok: status >= 200 && status < 300,
    status,
    statusText: "OK",
    json: () => Promise.resolve(data),
    text: () => Promise.resolve(JSON.stringify(data)),
  } as unknown as Response);
}

function mockFetchError(message: string, status: number) {
  return vi.fn().mockResolvedValue({
    ok: false,
    status,
    statusText: "Error",
    json: () => Promise.reject(new Error("not json")),
    text: () => Promise.resolve(message),
  } as unknown as Response);
}

/* ------------------------------------------------------------------ */
/*  Tests                                                              */
/* ------------------------------------------------------------------ */

describe("api helpers", () => {
  const originalFetch = globalThis.fetch;

  afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  // ---- getPlans ----

  describe("getPlans", () => {
    it("returns plan summaries with Bearer token", async () => {
      globalThis.fetch = mockFetchJson([sampleSummary]);

      const plans = await getPlans("my-token");

      expect(plans).toEqual([sampleSummary]);
      expect(globalThis.fetch).toHaveBeenCalledWith(
        "/api/plans",
        expect.objectContaining({
          headers: expect.objectContaining({
            Authorization: "Bearer my-token",
          }),
        }),
      );
    });

    it("throws ApiError on failure", async () => {
      globalThis.fetch = mockFetchError("Unauthorized", 401);

      await expect(getPlans("bad-token")).rejects.toThrow(ApiError);
      await expect(getPlans("bad-token")).rejects.toMatchObject({
        status: 401,
      });
    });
  });

  // ---- getPlan ----

  describe("getPlan", () => {
    it("returns plan detail with Bearer token", async () => {
      globalThis.fetch = mockFetchJson(sampleDetail);

      const plan = await getPlan("plan-1", "my-token");

      expect(plan).toEqual(sampleDetail);
      expect(globalThis.fetch).toHaveBeenCalledWith(
        "/api/plans/plan-1",
        expect.objectContaining({
          headers: expect.objectContaining({
            Authorization: "Bearer my-token",
          }),
        }),
      );
    });

    it("throws ApiError on 404", async () => {
      globalThis.fetch = mockFetchError("Not found", 404);

      await expect(getPlan("missing", "my-token")).rejects.toThrow(ApiError);
      await expect(getPlan("missing", "my-token")).rejects.toMatchObject({
        status: 404,
      });
    });

    it("encodes the plan id in the URL", async () => {
      globalThis.fetch = mockFetchJson(sampleDetail);

      await getPlan("id/with/slashes", "tok");

      expect(globalThis.fetch).toHaveBeenCalledWith(
        "/api/plans/id%2Fwith%2Fslashes",
        expect.anything(),
      );
    });
  });

  // ---- deletePlan ----

  describe("deletePlan", () => {
    it("sends DELETE with Bearer token", async () => {
      globalThis.fetch = mockFetchJson({ success: true });

      const result = await deletePlan("plan-1", "my-token");

      expect(result).toEqual({ success: true });
      expect(globalThis.fetch).toHaveBeenCalledWith(
        "/api/plans/plan-1",
        expect.objectContaining({
          method: "DELETE",
          headers: expect.objectContaining({
            Authorization: "Bearer my-token",
          }),
        }),
      );
    });

    it("throws ApiError on 403", async () => {
      globalThis.fetch = mockFetchError("Forbidden", 403);

      await expect(deletePlan("plan-1", "bad")).rejects.toThrow(ApiError);
      await expect(deletePlan("plan-1", "bad")).rejects.toMatchObject({
        status: 403,
      });
    });
  });

  // ---- getSessionUrl ----

  describe("getSessionUrl", () => {
    it("sends POST to /api/chat/session with Bearer token and returns session data", async () => {
      const sessionData = {
        url: "wss://example.com/ws",
        sessionId: "s1",
        expiresAt: 1700000000,
      };
      globalThis.fetch = mockFetchJson(sessionData);

      const result = await getSessionUrl(
        { sessionId: "s1", planId: "p1" },
        "my-token",
      );

      expect(result).toEqual(sessionData);
      expect(globalThis.fetch).toHaveBeenCalledWith(
        "/api/chat/session",
        expect.objectContaining({
          method: "POST",
          headers: expect.objectContaining({
            Authorization: "Bearer my-token",
            "Content-Type": "application/json",
          }),
          body: JSON.stringify({ sessionId: "s1", planId: "p1" }),
        }),
      );
    });

    it("works with empty body", async () => {
      const sessionData = {
        url: "wss://example.com/ws",
        sessionId: "new-id",
        expiresAt: 1700000000,
      };
      globalThis.fetch = mockFetchJson(sessionData);

      const result = await getSessionUrl({}, "my-token");

      expect(result).toEqual(sessionData);
      expect(globalThis.fetch).toHaveBeenCalledWith(
        "/api/chat/session",
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify({}),
        }),
      );
    });

    it("throws ApiError on failure", async () => {
      globalThis.fetch = mockFetchError("Unauthorized", 401);

      await expect(getSessionUrl({}, "bad-token")).rejects.toThrow(ApiError);
      await expect(getSessionUrl({}, "bad-token")).rejects.toMatchObject({
        status: 401,
      });
    });
  });
});
