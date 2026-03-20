import { describe, it, expect, vi, beforeEach } from "vitest";
import * as fc from "fast-check";
import { Hono } from "hono";

/**
 * Property 7: Verification State Round-Trip
 *
 * For any record, setting human_verified to true SHALL result in
 * human_verified=true, verified_at set to current timestamp, and
 * verified_by set to the user's identifier; subsequently setting
 * human_verified to false SHALL result in human_verified=false
 * (verified_at and verified_by cleared).
 *
 * Validates: Requirements 5.2, 5.3
 */

// ---- Mocks ----

vi.mock("../../db/client.js", () => ({
  updateRow: vi.fn(),
  deleteRow: vi.fn(),
  queryOne: vi.fn(),
  query: vi.fn(),
}));

vi.mock("../../middleware/auth.js", () => {
  let _email = "editor@test.com";
  return {
    __setMockEmail: (email: string) => {
      _email = email;
    },
    requireAuth: vi.fn(async (_c: unknown, next: () => Promise<void>) => {
      const c = _c as { set: (key: string, value: unknown) => void };
      c.set("authUser", {
        userId: "user-123",
        email: _email,
        canEdit: true,
      });
      await next();
    }),
    requireEditPermission: vi.fn(
      async (_c: unknown, next: () => Promise<void>) => {
        await next();
      },
    ),
  };
});

import domains from "../domains.js";
import strands from "../strands.js";
import subStrands from "../subStrands.js";
import indicators from "../indicators.js";
import { queryOne } from "../../db/client.js";

const mockedQueryOne = vi.mocked(queryOne);

// Access the mock email setter
const authMock = await import("../../middleware/auth.js");
const setMockEmail = (
  authMock as unknown as { __setMockEmail: (e: string) => void }
).__setMockEmail;

function createApp() {
  const app = new Hono();
  app.route("/api/domains", domains);
  app.route("/api/strands", strands);
  app.route("/api/sub-strands", subStrands);
  app.route("/api/indicators", indicators);
  return app;
}

// ---- Entity config ----

interface EntityConfig {
  entityType: string;
  path: string;
  table: string;
  makeVerifiedRow: (id: number, email: string) => Record<string, unknown>;
  makeUnverifiedRow: (id: number) => Record<string, unknown>;
}

const entityConfigs: EntityConfig[] = [
  {
    entityType: "domain",
    path: "/api/domains",
    table: "domains",
    makeVerifiedRow: (id, email) => ({
      id,
      document_id: 1,
      code: "D1",
      name: "Domain",
      description: null,
      human_verified: true,
      verified_at: "2024-06-15T12:00:00Z",
      verified_by: email,
      edited_at: null,
      edited_by: null,
    }),
    makeUnverifiedRow: (id) => ({
      id,
      document_id: 1,
      code: "D1",
      name: "Domain",
      description: null,
      human_verified: false,
      verified_at: null,
      verified_by: null,
      edited_at: null,
      edited_by: null,
    }),
  },
  {
    entityType: "strand",
    path: "/api/strands",
    table: "strands",
    makeVerifiedRow: (id, email) => ({
      id,
      domain_id: 1,
      code: "S1",
      name: "Strand",
      description: null,
      human_verified: true,
      verified_at: "2024-06-15T12:00:00Z",
      verified_by: email,
      edited_at: null,
      edited_by: null,
    }),
    makeUnverifiedRow: (id) => ({
      id,
      domain_id: 1,
      code: "S1",
      name: "Strand",
      description: null,
      human_verified: false,
      verified_at: null,
      verified_by: null,
      edited_at: null,
      edited_by: null,
    }),
  },
  {
    entityType: "sub_strand",
    path: "/api/sub-strands",
    table: "sub_strands",
    makeVerifiedRow: (id, email) => ({
      id,
      strand_id: 1,
      code: "SS1",
      name: "SubStrand",
      description: null,
      human_verified: true,
      verified_at: "2024-06-15T12:00:00Z",
      verified_by: email,
      edited_at: null,
      edited_by: null,
    }),
    makeUnverifiedRow: (id) => ({
      id,
      strand_id: 1,
      code: "SS1",
      name: "SubStrand",
      description: null,
      human_verified: false,
      verified_at: null,
      verified_by: null,
      edited_at: null,
      edited_by: null,
    }),
  },
  {
    entityType: "indicator",
    path: "/api/indicators",
    table: "indicators",
    makeVerifiedRow: (id, email) => ({
      id,
      standard_id: "STD-1",
      domain_id: 1,
      strand_id: 1,
      sub_strand_id: 1,
      code: "I1",
      title: "Indicator",
      description: "Desc",
      age_band: null,
      source_page: null,
      source_text: null,
      human_verified: true,
      verified_at: "2024-06-15T12:00:00Z",
      verified_by: email,
      edited_at: null,
      edited_by: null,
      last_verified: null,
      created_at: "2024-01-01T00:00:00Z",
    }),
    makeUnverifiedRow: (id) => ({
      id,
      standard_id: "STD-1",
      domain_id: 1,
      strand_id: 1,
      sub_strand_id: 1,
      code: "I1",
      title: "Indicator",
      description: "Desc",
      age_band: null,
      source_page: null,
      source_text: null,
      human_verified: false,
      verified_at: null,
      verified_by: null,
      edited_at: null,
      edited_by: null,
      last_verified: null,
      created_at: "2024-01-01T00:00:00Z",
    }),
  },
];

// ---- Arbitraries ----

const arbId = fc.integer({ min: 1, max: 99999 });
const arbEmail = fc.emailAddress();
const arbEntityIndex = fc.integer({ min: 0, max: entityConfigs.length - 1 });

// ---- Tests ----

describe("Property 7: Verification State Round-Trip", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("setting humanVerified=true results in SQL with human_verified=true, verified_at=NOW(), verified_by=$2 and response has verifiedAt/verifiedBy", async () => {
    const app = createApp();

    await fc.assert(
      fc.asyncProperty(
        arbEntityIndex,
        arbId,
        arbEmail,
        async (entityIdx, id, email) => {
          vi.clearAllMocks();
          setMockEmail(email);

          const config = entityConfigs[entityIdx];
          mockedQueryOne.mockResolvedValue(
            config.makeVerifiedRow(id, email) as never,
          );

          const res = await app.request(`${config.path}/${id}/verify`, {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ humanVerified: true }),
          });

          expect(res.status).toBe(200);
          const body = await res.json();
          expect(body.success).toBe(true);
          expect(body.verifiedAt).not.toBeNull();
          expect(body.verifiedBy).toBe(email);

          // Verify the SQL used
          expect(mockedQueryOne).toHaveBeenCalledTimes(1);
          const [sql, params] = mockedQueryOne.mock.calls[0];
          expect(sql).toContain("human_verified = true");
          expect(sql).toContain("verified_at = NOW()");
          expect(sql).toContain("verified_by = $2");
          expect(params).toEqual([id, email]);
        },
      ),
      { numRuns: 100 },
    );
  });

  it("setting humanVerified=false results in SQL with human_verified=false, verified_at=NULL, verified_by=NULL and response clears fields", async () => {
    const app = createApp();

    await fc.assert(
      fc.asyncProperty(
        arbEntityIndex,
        arbId,
        arbEmail,
        async (entityIdx, id, email) => {
          vi.clearAllMocks();
          setMockEmail(email);

          const config = entityConfigs[entityIdx];
          mockedQueryOne.mockResolvedValue(
            config.makeUnverifiedRow(id) as never,
          );

          const res = await app.request(`${config.path}/${id}/verify`, {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ humanVerified: false }),
          });

          expect(res.status).toBe(200);
          const body = await res.json();
          expect(body.success).toBe(true);
          expect(body.verifiedAt).toBeNull();
          expect(body.verifiedBy).toBeNull();

          // Verify the SQL used
          expect(mockedQueryOne).toHaveBeenCalledTimes(1);
          const [sql] = mockedQueryOne.mock.calls[0];
          expect(sql).toContain("human_verified = false");
          expect(sql).toContain("verified_at = NULL");
          expect(sql).toContain("verified_by = NULL");
        },
      ),
      { numRuns: 100 },
    );
  });

  it("round-trip: verify then unverify the same record transitions state correctly", async () => {
    const app = createApp();

    await fc.assert(
      fc.asyncProperty(
        arbEntityIndex,
        arbId,
        arbEmail,
        async (entityIdx, id, email) => {
          vi.clearAllMocks();
          setMockEmail(email);

          const config = entityConfigs[entityIdx];

          // Step 1: Verify (humanVerified = true)
          mockedQueryOne.mockResolvedValueOnce(
            config.makeVerifiedRow(id, email) as never,
          );

          const res1 = await app.request(`${config.path}/${id}/verify`, {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ humanVerified: true }),
          });

          expect(res1.status).toBe(200);
          const body1 = await res1.json();
          expect(body1.success).toBe(true);
          expect(body1.verifiedAt).not.toBeNull();
          expect(body1.verifiedBy).toBe(email);

          // Step 2: Unverify (humanVerified = false)
          mockedQueryOne.mockResolvedValueOnce(
            config.makeUnverifiedRow(id) as never,
          );

          const res2 = await app.request(`${config.path}/${id}/verify`, {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ humanVerified: false }),
          });

          expect(res2.status).toBe(200);
          const body2 = await res2.json();
          expect(body2.success).toBe(true);
          expect(body2.verifiedAt).toBeNull();
          expect(body2.verifiedBy).toBeNull();
        },
      ),
      { numRuns: 100 },
    );
  });
});
