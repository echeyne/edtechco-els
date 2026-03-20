import { describe, it, expect, vi, beforeEach } from "vitest";
import * as fc from "fast-check";
import { Hono } from "hono";

/**
 * Property 2: Filter Correctness
 *
 * For ANY filter combination of country and state, all records returned by
 * the API SHALL match the specified filter criteria exactly — no records
 * outside the filter should be returned, and no matching records should be
 * omitted.
 *
 * Validates: Requirements 1.4, 5.5, 10.4
 */

// Mock the db client before importing the route module
vi.mock("../../db/client.js", () => ({
  queryMany: vi.fn(),
  queryOne: vi.fn(),
}));

// Mock S3 (imported by documents.ts)
vi.mock("@aws-sdk/s3-request-presigner", () => ({
  getSignedUrl: vi.fn(),
}));
vi.mock("@aws-sdk/client-s3", () => ({
  S3Client: vi.fn(),
  GetObjectCommand: vi.fn(),
}));

import documents from "../documents.js";
import { queryMany } from "../../db/client.js";

const mockedQueryMany = vi.mocked(queryMany);

function createApp() {
  const app = new Hono();
  app.route("/api/documents", documents);
  return app;
}

// ---- Arbitraries ----

/** Generate a 2-character uppercase country code */
const arbCountry = fc.stringMatching(/^[A-Z]{2}$/);

/** Generate a state string (1-10 chars, alphanumeric) */
const arbState = fc.stringMatching(/^[A-Za-z0-9]{1,10}$/);

/** Generate a document DB row with a given country and state */
function arbDocumentRow(country: string, state: string) {
  return fc.record({
    id: fc.nat({ max: 100000 }),
    country: fc.constant(country),
    state: fc.constant(state),
    title: fc.string({ minLength: 1, maxLength: 50 }),
    version_year: fc.integer({ min: 2000, max: 2030 }),
    source_url: fc.oneof(
      fc.constant(null),
      fc.string({ minLength: 5, maxLength: 30 }),
    ),
    age_band: fc.string({ minLength: 0, maxLength: 10 }),
    publishing_agency: fc.string({ minLength: 0, maxLength: 30 }),
    created_at: fc.constant("2024-01-01T00:00:00Z"),
  });
}

/** Generate a pool of countries and states, then a dataset of document rows */
const arbDatasetAndFilter = fc
  .record({
    countries: fc.uniqueArray(arbCountry, { minLength: 1, maxLength: 5 }),
    states: fc.uniqueArray(arbState, { minLength: 1, maxLength: 5 }),
  })
  .chain(({ countries, states }) => {
    // Generate 1-15 document rows with random country/state from the pools
    const arbRow = fc
      .record({
        countryIdx: fc.nat({ max: countries.length - 1 }),
        stateIdx: fc.nat({ max: states.length - 1 }),
      })
      .chain(({ countryIdx, stateIdx }) =>
        arbDocumentRow(countries[countryIdx], states[stateIdx]),
      );

    return fc
      .record({
        rows: fc.array(arbRow, { minLength: 1, maxLength: 15 }),
        filterCountry: fc.oneof(
          fc.constant(undefined as string | undefined),
          fc.constantFrom(...countries),
        ),
        filterState: fc.oneof(
          fc.constant(undefined as string | undefined),
          fc.constantFrom(...states),
        ),
      })
      .map(({ rows, filterCountry, filterState }) => ({
        rows,
        filterCountry,
        filterState,
        countries,
        states,
      }));
  });

describe("Property 2: Filter Correctness", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("all returned records match filter criteria and no matching records are omitted", async () => {
    const app = createApp();

    await fc.assert(
      fc.asyncProperty(
        arbDatasetAndFilter,
        async ({ rows, filterCountry, filterState }) => {
          vi.clearAllMocks();

          // Compute expected results: simulate DB filtering
          const expected = rows.filter((row) => {
            if (filterCountry && row.country !== filterCountry) return false;
            if (filterState && row.state !== filterState) return false;
            return true;
          });

          // Mock queryMany to return only the matching rows (simulating DB behavior)
          mockedQueryMany.mockResolvedValueOnce(expected as never);

          // Build the request URL
          const params = new URLSearchParams();
          if (filterCountry) params.set("country", filterCountry);
          if (filterState) params.set("state", filterState);
          const qs = params.toString();
          const url = qs ? `/api/documents?${qs}` : "/api/documents";

          const res = await app.request(url);
          expect(res.status).toBe(200);

          const body = (await res.json()) as Array<{
            country: string;
            state: string;
          }>;

          // Verify: every returned record matches the filter criteria
          for (const doc of body) {
            if (filterCountry) {
              expect(doc.country).toBe(filterCountry);
            }
            if (filterState) {
              expect(doc.state).toBe(filterState);
            }
          }

          // Verify: the count matches expected (no omissions, no extras)
          expect(body.length).toBe(expected.length);

          // Verify: the SQL query was built correctly
          const sql = mockedQueryMany.mock.calls[0][0] as string;
          const sqlParams = mockedQueryMany.mock.calls[0][1] as unknown[];

          if (filterCountry && filterState) {
            expect(sql).toContain("WHERE");
            expect(sql).toContain("country = $1");
            expect(sql).toContain("state = $2");
            expect(sqlParams).toEqual([filterCountry, filterState]);
          } else if (filterCountry) {
            expect(sql).toContain("WHERE");
            expect(sql).toContain("country = $1");
            expect(sql).not.toContain("state =");
            expect(sqlParams).toEqual([filterCountry]);
          } else if (filterState) {
            expect(sql).toContain("WHERE");
            expect(sql).toContain("state = $1");
            expect(sql).not.toContain("country =");
            expect(sqlParams).toEqual([filterState]);
          } else {
            expect(sql).not.toContain("WHERE");
            expect(sqlParams).toEqual([]);
          }

          // Verify: ORDER BY is always present
          expect(sql).toContain("ORDER BY country, state, title");
        },
      ),
      { numRuns: 100 },
    );
  });

  it("rejects invalid filter values with 400", async () => {
    const app = createApp();

    await fc.assert(
      fc.asyncProperty(
        fc.oneof(
          // Country too long (>2 chars)
          fc.string({ minLength: 3, maxLength: 10 }).map((c) => ({
            country: c,
            state: undefined as string | undefined,
          })),
          // Country too short (1 char)
          fc.string({ minLength: 1, maxLength: 1 }).map((c) => ({
            country: c,
            state: undefined as string | undefined,
          })),
          // State too long (>10 chars)
          fc.string({ minLength: 11, maxLength: 20 }).map((s) => ({
            country: undefined as string | undefined,
            state: s,
          })),
        ),
        async ({ country, state }) => {
          const params = new URLSearchParams();
          if (country) params.set("country", country);
          if (state) params.set("state", state);
          const url = `/api/documents?${params.toString()}`;

          const res = await app.request(url);
          expect(res.status).toBe(400);

          const body = await res.json();
          expect(body.error.code).toBe("VALIDATION_ERROR");
        },
      ),
      { numRuns: 100 },
    );
  });
});
