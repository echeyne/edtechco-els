import { describe, it, expect, vi, beforeEach } from "vitest";
import * as fc from "fast-check";
import { Hono } from "hono";

/**
 * Property 5: Edit Audit Trail Integrity
 *
 * For any successful edit operation on any record type (domain, strand,
 * sub_strand, indicator), the record SHALL have edited_at set to the current
 * timestamp and edited_by set to the authenticated user's identifier, and
 * these values SHALL persist until the next edit.
 *
 * Validates: Requirements 4.1, 4.7
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
import { updateRow } from "../../db/client.js";

const mockedUpdateRow = vi.mocked(updateRow);

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

// ---- Row factories ----

function makeDomainRow(id: number, email: string): Record<string, unknown> {
  return {
    id,
    document_id: 1,
    code: "D1",
    name: "Domain",
    description: null,
    human_verified: false,
    verified_at: null,
    verified_by: null,
    edited_at: "2024-06-01T00:00:00Z",
    edited_by: email,
  };
}

function makeStrandRow(id: number, email: string): Record<string, unknown> {
  return {
    id,
    domain_id: 1,
    code: "S1",
    name: "Strand",
    description: null,
    human_verified: false,
    verified_at: null,
    verified_by: null,
    edited_at: "2024-06-01T00:00:00Z",
    edited_by: email,
  };
}

function makeSubStrandRow(id: number, email: string): Record<string, unknown> {
  return {
    id,
    strand_id: 1,
    code: "SS1",
    name: "SubStrand",
    description: null,
    human_verified: false,
    verified_at: null,
    verified_by: null,
    edited_at: "2024-06-01T00:00:00Z",
    edited_by: email,
  };
}

function makeIndicatorRow(id: number, email: string): Record<string, unknown> {
  return {
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
    edited_at: "2024-06-01T00:00:00Z",
    edited_by: email,
    last_verified: null,
    created_at: "2024-01-01T00:00:00Z",
  };
}

// ---- Arbitraries ----

/** Generate a valid positive integer id */
const arbId = fc.integer({ min: 1, max: 99999 });

/** Generate a valid email */
const arbEmail = fc.emailAddress();

/** Domain update payload */
const arbDomainPayload = fc
  .record({
    code: fc.option(fc.string({ minLength: 1, maxLength: 20 }), {
      nil: undefined,
    }),
    name: fc.option(fc.string({ minLength: 1, maxLength: 50 }), {
      nil: undefined,
    }),
    description: fc.option(
      fc.oneof(fc.string({ minLength: 1, maxLength: 50 }), fc.constant(null)),
      { nil: undefined },
    ),
  })
  .filter(
    (p) =>
      p.code !== undefined ||
      p.name !== undefined ||
      p.description !== undefined,
  );

/** Strand update payload (same shape as domain) */
const arbStrandPayload = fc
  .record({
    code: fc.option(fc.string({ minLength: 1, maxLength: 30 }), {
      nil: undefined,
    }),
    name: fc.option(fc.string({ minLength: 1, maxLength: 50 }), {
      nil: undefined,
    }),
    description: fc.option(
      fc.oneof(fc.string({ minLength: 1, maxLength: 50 }), fc.constant(null)),
      { nil: undefined },
    ),
  })
  .filter(
    (p) =>
      p.code !== undefined ||
      p.name !== undefined ||
      p.description !== undefined,
  );

/** SubStrand update payload */
const arbSubStrandPayload = fc
  .record({
    code: fc.option(fc.string({ minLength: 1, maxLength: 40 }), {
      nil: undefined,
    }),
    name: fc.option(fc.string({ minLength: 1, maxLength: 50 }), {
      nil: undefined,
    }),
    description: fc.option(
      fc.oneof(fc.string({ minLength: 1, maxLength: 50 }), fc.constant(null)),
      { nil: undefined },
    ),
  })
  .filter(
    (p) =>
      p.code !== undefined ||
      p.name !== undefined ||
      p.description !== undefined,
  );

/** Indicator update payload */
const arbIndicatorPayload = fc
  .record({
    code: fc.option(fc.string({ minLength: 1, maxLength: 50 }), {
      nil: undefined,
    }),
    title: fc.option(
      fc.oneof(fc.string({ minLength: 1, maxLength: 50 }), fc.constant(null)),
      { nil: undefined },
    ),
    description: fc.option(fc.string({ minLength: 1, maxLength: 100 }), {
      nil: undefined,
    }),
    ageBand: fc.option(
      fc.oneof(fc.string({ minLength: 1, maxLength: 20 }), fc.constant(null)),
      { nil: undefined },
    ),
    sourcePage: fc.option(
      fc.oneof(fc.integer({ min: 1, max: 500 }), fc.constant(null)),
      { nil: undefined },
    ),
    sourceText: fc.option(
      fc.oneof(fc.string({ minLength: 1, maxLength: 50 }), fc.constant(null)),
      { nil: undefined },
    ),
  })
  .filter(
    (p) =>
      p.code !== undefined ||
      p.title !== undefined ||
      p.description !== undefined ||
      p.ageBand !== undefined ||
      p.sourcePage !== undefined ||
      p.sourceText !== undefined,
  );

/** Pick a random entity type with its matching payload and route info */
const arbEditOperation = fc.oneof(
  arbDomainPayload.map((payload) => ({
    entityType: "domain" as const,
    path: "/api/domains",
    payload,
    makeRow: makeDomainRow,
  })),
  arbStrandPayload.map((payload) => ({
    entityType: "strand" as const,
    path: "/api/strands",
    payload,
    makeRow: makeStrandRow,
  })),
  arbSubStrandPayload.map((payload) => ({
    entityType: "sub_strand" as const,
    path: "/api/sub-strands",
    payload,
    makeRow: makeSubStrandRow,
  })),
  arbIndicatorPayload.map((payload) => ({
    entityType: "indicator" as const,
    path: "/api/indicators",
    payload,
    makeRow: makeIndicatorRow,
  })),
);

// ---- Tests ----

describe("Property 5: Edit Audit Trail Integrity", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("updateRow is always called with edited_at=NOW() and edited_by=<user email> for any entity edit", async () => {
    const app = createApp();

    await fc.assert(
      fc.asyncProperty(
        arbEditOperation,
        arbId,
        arbEmail,
        async (op, id, email) => {
          vi.clearAllMocks();
          setMockEmail(email);

          const returnedRow = op.makeRow(id, email);
          mockedUpdateRow.mockResolvedValue(returnedRow as never);

          const res = await app.request(`${op.path}/${id}`, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(op.payload),
          });

          expect(res.status).toBe(200);

          // Verify updateRow was called with the correct audit extraSets
          expect(mockedUpdateRow).toHaveBeenCalledTimes(1);
          const callArgs = mockedUpdateRow.mock.calls[0];
          // callArgs: [table, id, fields, extraSets]
          const extraSets = callArgs[3] as Record<string, unknown>;
          expect(extraSets).toEqual({
            edited_at: "NOW()",
            edited_by: email,
          });
        },
      ),
      { numRuns: 100 },
    );
  });

  it("response body contains editedBy matching the authenticated user email", async () => {
    const app = createApp();

    await fc.assert(
      fc.asyncProperty(
        arbEditOperation,
        arbId,
        arbEmail,
        async (op, id, email) => {
          vi.clearAllMocks();
          setMockEmail(email);

          const returnedRow = op.makeRow(id, email);
          mockedUpdateRow.mockResolvedValue(returnedRow as never);

          const res = await app.request(`${op.path}/${id}`, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(op.payload),
          });

          expect(res.status).toBe(200);
          const body = await res.json();
          expect(body.editedBy).toBe(email);
        },
      ),
      { numRuns: 100 },
    );
  });

  it("different users editing the same record results in different edited_by values", async () => {
    const app = createApp();

    await fc.assert(
      fc.asyncProperty(
        arbEditOperation,
        arbId,
        arbEmail,
        arbEmail.filter((e2) => e2.length > 0),
        async (op, id, email1, email2) => {
          // Skip if emails happen to be the same
          fc.pre(email1 !== email2);

          vi.clearAllMocks();

          // First edit by user 1
          setMockEmail(email1);
          mockedUpdateRow.mockResolvedValue(op.makeRow(id, email1) as never);

          const res1 = await app.request(`${op.path}/${id}`, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(op.payload),
          });
          expect(res1.status).toBe(200);
          const body1 = await res1.json();

          // Second edit by user 2
          setMockEmail(email2);
          mockedUpdateRow.mockResolvedValue(op.makeRow(id, email2) as never);

          const res2 = await app.request(`${op.path}/${id}`, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(op.payload),
          });
          expect(res2.status).toBe(200);
          const body2 = await res2.json();

          // The two responses should have different editedBy
          expect(body1.editedBy).toBe(email1);
          expect(body2.editedBy).toBe(email2);
          expect(body1.editedBy).not.toBe(body2.editedBy);
        },
      ),
      { numRuns: 100 },
    );
  });
});
