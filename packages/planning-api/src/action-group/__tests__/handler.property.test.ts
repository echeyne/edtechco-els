// Feature: parent-planning-tool, Property 3: Available states reflect database contents

import { describe, it, expect, vi, beforeEach } from "vitest";
import * as fc from "fast-check";

// Mock the db client module
vi.mock("../../db/client.js", () => ({
  query: vi.fn(),
  queryOne: vi.fn(),
  queryMany: vi.fn(),
}));

// Mock the plans module (needed because handler.ts imports it)
vi.mock("../../db/plans.js", () => ({
  createPlan: vi.fn(),
  getPlanById: vi.fn(),
  updatePlan: vi.fn(),
  deletePlan: vi.fn(),
}));

import { getAvailableStates, getIndicators } from "../handler.js";
import { queryMany } from "../../db/client.js";

const mockedQueryMany = vi.mocked(queryMany);

/**
 * Property 3: Available states reflect database contents
 *
 * For any call to the getAvailableStates action group function, every returned
 * state string must correspond to at least one document in the documents table,
 * and every state that has at least one document must appear in the result.
 *
 * **Validates: Requirements 3.2**
 */
describe("Property 3: Available states reflect database contents", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("returns exactly the distinct set of states present in the database (sorted)", async () => {
    await fc.assert(
      fc.asyncProperty(
        fc.array(fc.stringMatching(/^[A-Z]{2}$/)),
        async (stateCodes: string[]) => {
          // Compute the expected distinct sorted states
          const expectedStates = [...new Set(stateCodes)].sort();

          // The DB query uses SELECT DISTINCT ... ORDER BY state,
          // so mock queryMany to return one row per distinct state (sorted)
          mockedQueryMany.mockResolvedValueOnce(
            expectedStates.map((state) => ({ state })),
          );

          const result = await getAvailableStates();

          // The result should be exactly the distinct set of input states, sorted
          expect(result).toEqual(expectedStates);
        },
      ),
      { numRuns: 100 },
    );
  });
});

// Feature: parent-planning-tool, Property 4: Indicator queries return only matching records

/**
 * Property 4: Indicator queries return only matching records
 *
 * For any state and age band combination, calling getIndicators(state, ageBand)
 * shall return only indicators whose associated document matches that state and
 * whose age_band matches the requested age band. If no indicators match, the
 * result shall be an empty array.
 *
 * **Validates: Requirements 3.4, 6.1**
 */

/** Generator for a two-letter uppercase state code */
const arbStateCode = fc.stringMatching(/^[A-Z]{2}$/);

/** Generator for an age band string */
const arbAgeBand = fc.constantFrom("0-1", "1-2", "2-3", "3-4", "4-5", "5-6");

/** Generator for a single indicator record */
const arbIndicatorRecord = fc.record({
  code: fc.stringMatching(/^[A-Z]{2}\.[A-Z]{2,3}\.\d+\.\d+$/),
  description: fc
    .string({ minLength: 1, maxLength: 100 })
    .filter((s) => s.trim().length > 0),
  domain_name: fc
    .string({ minLength: 1, maxLength: 50 })
    .filter((s) => s.trim().length > 0),
  strand_name: fc.oneof(
    fc
      .string({ minLength: 1, maxLength: 50 })
      .filter((s) => s.trim().length > 0),
    fc.constant(null),
  ),
  sub_strand_name: fc.oneof(
    fc
      .string({ minLength: 1, maxLength: 50 })
      .filter((s) => s.trim().length > 0),
    fc.constant(null),
  ),
  age_band: arbAgeBand,
  state: arbStateCode,
});

describe("Property 4: Indicator queries return only matching records", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("all returned indicators match the requested state and ageBand", async () => {
    await fc.assert(
      fc.asyncProperty(
        fc.array(arbIndicatorRecord, { minLength: 0, maxLength: 20 }),
        arbStateCode,
        arbAgeBand,
        async (allRecords, queryState, queryAgeBand) => {
          // Filter to only records matching the requested state and ageBand
          // (simulating what the DB WHERE clause would return)
          const matchingRecords = allRecords.filter(
            (r) => r.state === queryState && r.age_band === queryAgeBand,
          );

          // Mock queryMany to return only the matching records (without the state field,
          // since the real SQL query doesn't SELECT state — it selects age_band from doc)
          mockedQueryMany.mockResolvedValueOnce(
            matchingRecords.map(({ state: _state, ...rest }) => rest),
          );

          const result = await getIndicators(queryState, queryAgeBand);

          // Assert the count matches
          expect(result).toHaveLength(matchingRecords.length);

          // Assert every returned record has the correct age_band
          for (const indicator of result) {
            expect(indicator.age_band).toBe(queryAgeBand);
          }

          // Assert all expected codes are present
          const expectedCodes = matchingRecords.map((r) => r.code);
          const resultCodes = result.map((r) => r.code);
          expect(resultCodes).toEqual(expectedCodes);
        },
      ),
      { numRuns: 100 },
    );
  });
});
