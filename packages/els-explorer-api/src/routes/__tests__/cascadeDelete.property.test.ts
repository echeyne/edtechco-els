import { describe, it, expect, vi, beforeEach } from "vitest";
import * as fc from "fast-check";
import { Hono } from "hono";

/**
 * Property 6: Cascade Delete Completeness
 *
 * For any delete operation on a parent record, all dependent child records
 * SHALL also be deleted—deleting a domain removes its strands, sub_strands,
 * and indicators; deleting a strand removes its sub_strands and indicators;
 * deleting a sub_strand removes its indicators.
 *
 * **Validates: Requirements 4.2**
 */

// ---- Mocks ----

vi.mock("../../db/client.js", () => ({
  updateRow: vi.fn(),
  deleteRow: vi.fn(),
  queryOne: vi.fn(),
  query: vi.fn(),
}));

vi.mock("../../middleware/auth.js", () => ({
  requireAuth: vi.fn(async (_c: unknown, next: () => Promise<void>) => {
    const c = _c as { set: (key: string, value: unknown) => void };
    c.set("authUser", {
      userId: "user-123",
      email: "editor@test.com",
      canEdit: true,
    });
    await next();
  }),
  requireEditPermission: vi.fn(
    async (_c: unknown, next: () => Promise<void>) => {
      await next();
    },
  ),
}));

import domains from "../domains.js";
import strands from "../strands.js";
import subStrands from "../subStrands.js";
import indicators from "../indicators.js";
import { deleteRow, queryOne, query } from "../../db/client.js";

const mockedDeleteRow = vi.mocked(deleteRow);
const mockedQueryOne = vi.mocked(queryOne);
const mockedQuery = vi.mocked(query);

function createApp() {
  const app = new Hono();
  app.route("/api/domains", domains);
  app.route("/api/strands", strands);
  app.route("/api/sub-strands", subStrands);
  app.route("/api/indicators", indicators);
  return app;
}

// ---- Entity type definitions for cascade verification ----

type EntityType = "domain" | "strand" | "sub_strand" | "indicator";

interface CascadeExpectation {
  entityType: EntityType;
  path: string;
  expectedQueryCount: number;
  /** Substrings that must appear in the cascade query calls, in order */
  expectedQueryPatterns: string[];
  /** The table name passed to deleteRow */
  deleteTable: string;
}

function getCascadeExpectation(
  entityType: EntityType,
  id: number,
): CascadeExpectation {
  switch (entityType) {
    case "domain":
      return {
        entityType,
        path: `/api/domains/${id}`,
        expectedQueryCount: 3,
        expectedQueryPatterns: [
          "DELETE FROM indicators WHERE domain_id",
          "DELETE FROM sub_strands WHERE strand_id IN",
          "DELETE FROM strands WHERE domain_id",
        ],
        deleteTable: "domains",
      };
    case "strand":
      return {
        entityType,
        path: `/api/strands/${id}`,
        expectedQueryCount: 2,
        expectedQueryPatterns: [
          "DELETE FROM indicators WHERE strand_id",
          "DELETE FROM sub_strands WHERE strand_id",
        ],
        deleteTable: "strands",
      };
    case "sub_strand":
      return {
        entityType,
        path: `/api/sub-strands/${id}`,
        expectedQueryCount: 1,
        expectedQueryPatterns: ["DELETE FROM indicators WHERE sub_strand_id"],
        deleteTable: "sub_strands",
      };
    case "indicator":
      return {
        entityType,
        path: `/api/indicators/${id}`,
        expectedQueryCount: 0,
        expectedQueryPatterns: [],
        deleteTable: "indicators",
      };
  }
}

// ---- Arbitraries ----

const arbId = fc.integer({ min: 1, max: 99999 });

const arbEntityType = fc.constantFrom<EntityType>(
  "domain",
  "strand",
  "sub_strand",
  "indicator",
);

// ---- Tests ----

describe("Property 6: Cascade Delete Completeness", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("deleting any entity type issues the correct cascade queries in the right order", async () => {
    const app = createApp();

    await fc.assert(
      fc.asyncProperty(arbEntityType, arbId, async (entityType, id) => {
        vi.clearAllMocks();

        // Mock: entity exists
        mockedQueryOne.mockResolvedValue({ id } as never);
        // Mock: cascade queries succeed
        mockedQuery.mockResolvedValue({ rows: [], rowCount: 0 } as never);
        // Mock: deleteRow succeeds
        mockedDeleteRow.mockResolvedValue(true);

        const expectation = getCascadeExpectation(entityType, id);

        const res = await app.request(expectation.path, { method: "DELETE" });

        expect(res.status).toBe(200);
        const body = await res.json();
        expect(body.success).toBe(true);

        // Verify the correct number of cascade query calls
        expect(mockedQuery).toHaveBeenCalledTimes(
          expectation.expectedQueryCount,
        );

        // Verify each cascade query contains the expected pattern in order
        for (let i = 0; i < expectation.expectedQueryCount; i++) {
          const sql = mockedQuery.mock.calls[i][0] as string;
          expect(sql).toContain(expectation.expectedQueryPatterns[i]);
          // Verify the id parameter was passed
          const params = mockedQuery.mock.calls[i][1] as unknown[];
          expect(params).toContain(id);
        }

        // Verify deleteRow was called with the correct table and id
        expect(mockedDeleteRow).toHaveBeenCalledTimes(1);
        expect(mockedDeleteRow).toHaveBeenCalledWith(
          expectation.deleteTable,
          id,
        );
      }),
      { numRuns: 100 },
    );
  });

  it("domain delete always issues exactly 3 cascade queries + 1 deleteRow", async () => {
    const app = createApp();

    await fc.assert(
      fc.asyncProperty(arbId, async (id) => {
        vi.clearAllMocks();

        mockedQueryOne.mockResolvedValue({ id } as never);
        mockedQuery.mockResolvedValue({ rows: [], rowCount: 0 } as never);
        mockedDeleteRow.mockResolvedValue(true);

        const res = await app.request(`/api/domains/${id}`, {
          method: "DELETE",
        });

        expect(res.status).toBe(200);

        // 3 cascade queries: indicators, sub_strands, strands
        expect(mockedQuery).toHaveBeenCalledTimes(3);
        expect(mockedQuery.mock.calls[0][0] as string).toContain(
          "DELETE FROM indicators",
        );
        expect(mockedQuery.mock.calls[1][0] as string).toContain(
          "DELETE FROM sub_strands",
        );
        expect(mockedQuery.mock.calls[2][0] as string).toContain(
          "DELETE FROM strands",
        );

        // 1 deleteRow for the domain itself
        expect(mockedDeleteRow).toHaveBeenCalledTimes(1);
        expect(mockedDeleteRow).toHaveBeenCalledWith("domains", id);
      }),
      { numRuns: 100 },
    );
  });

  it("indicator delete issues 0 cascade queries, only deleteRow", async () => {
    const app = createApp();

    await fc.assert(
      fc.asyncProperty(arbId, async (id) => {
        vi.clearAllMocks();

        mockedQueryOne.mockResolvedValue({ id } as never);
        mockedDeleteRow.mockResolvedValue(true);

        const res = await app.request(`/api/indicators/${id}`, {
          method: "DELETE",
        });

        expect(res.status).toBe(200);

        // No cascade queries for indicators
        expect(mockedQuery).toHaveBeenCalledTimes(0);

        // Only deleteRow
        expect(mockedDeleteRow).toHaveBeenCalledTimes(1);
        expect(mockedDeleteRow).toHaveBeenCalledWith("indicators", id);
      }),
      { numRuns: 100 },
    );
  });
});
