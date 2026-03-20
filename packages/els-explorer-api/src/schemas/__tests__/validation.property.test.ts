import { describe, it, expect } from "vitest";
import * as fc from "fast-check";
import {
  UpdateDomainSchema,
  UpdateStrandSchema,
  UpdateSubStrandSchema,
  UpdateIndicatorSchema,
  VerifySchema,
  FilterQuerySchema,
} from "../index.js";

/**
 * Property 8: Request Validation Enforcement
 *
 * For any request with an invalid payload (missing required fields, wrong types,
 * values outside constraints), the API SHALL reject the request with a validation
 * error and SHALL NOT modify any data.
 *
 * Validates: Requirements 10.7
 */

describe("Property 8: Request Validation Enforcement", () => {
  // --- UpdateDomainSchema ---

  it("rejects domain updates where code exceeds max length", () => {
    fc.assert(
      fc.property(fc.string({ minLength: 21, maxLength: 200 }), (code) => {
        const result = UpdateDomainSchema.safeParse({ code });
        expect(result.success).toBe(false);
      }),
      { numRuns: 100 },
    );
  });

  it("rejects domain updates with non-string code", () => {
    fc.assert(
      fc.property(
        fc.oneof(fc.integer(), fc.boolean(), fc.constant([]), fc.object()),
        (code) => {
          const result = UpdateDomainSchema.safeParse({ code });
          expect(result.success).toBe(false);
        },
      ),
      { numRuns: 100 },
    );
  });

  it("accepts valid domain updates", () => {
    fc.assert(
      fc.property(
        fc.record({
          code: fc.string({ minLength: 1, maxLength: 20 }),
          name: fc.string({ minLength: 1 }),
          description: fc.oneof(fc.string(), fc.constant(null)),
        }),
        (payload) => {
          const result = UpdateDomainSchema.safeParse(payload);
          expect(result.success).toBe(true);
        },
      ),
      { numRuns: 100 },
    );
  });

  // --- UpdateStrandSchema ---

  it("rejects strand updates where code exceeds max length", () => {
    fc.assert(
      fc.property(fc.string({ minLength: 31, maxLength: 200 }), (code) => {
        const result = UpdateStrandSchema.safeParse({ code });
        expect(result.success).toBe(false);
      }),
      { numRuns: 100 },
    );
  });

  // --- UpdateSubStrandSchema ---

  it("rejects sub-strand updates where code exceeds max length", () => {
    fc.assert(
      fc.property(fc.string({ minLength: 41, maxLength: 200 }), (code) => {
        const result = UpdateSubStrandSchema.safeParse({ code });
        expect(result.success).toBe(false);
      }),
      { numRuns: 100 },
    );
  });

  // --- UpdateIndicatorSchema ---

  it("rejects indicator updates where code exceeds max length", () => {
    fc.assert(
      fc.property(fc.string({ minLength: 51, maxLength: 200 }), (code) => {
        const result = UpdateIndicatorSchema.safeParse({ code });
        expect(result.success).toBe(false);
      }),
      { numRuns: 100 },
    );
  });

  it("rejects indicator updates with non-positive sourcePage", () => {
    fc.assert(
      fc.property(fc.integer({ max: 0 }), (sourcePage) => {
        const result = UpdateIndicatorSchema.safeParse({ sourcePage });
        expect(result.success).toBe(false);
      }),
      { numRuns: 100 },
    );
  });

  it("rejects indicator updates with non-integer sourcePage", () => {
    fc.assert(
      fc.property(
        fc.oneof(fc.string(), fc.boolean(), fc.constant([])),
        (sourcePage) => {
          const result = UpdateIndicatorSchema.safeParse({ sourcePage });
          expect(result.success).toBe(false);
        },
      ),
      { numRuns: 100 },
    );
  });

  it("rejects indicator updates where ageBand exceeds max length", () => {
    fc.assert(
      fc.property(fc.string({ minLength: 21, maxLength: 200 }), (ageBand) => {
        const result = UpdateIndicatorSchema.safeParse({ ageBand });
        expect(result.success).toBe(false);
      }),
      { numRuns: 100 },
    );
  });

  it("accepts valid indicator updates", () => {
    fc.assert(
      fc.property(
        fc.record({
          code: fc.string({ minLength: 1, maxLength: 50 }),
          title: fc.oneof(fc.string(), fc.constant(null)),
          description: fc.string({ minLength: 1 }),
          ageBand: fc.oneof(
            fc.string({ minLength: 1, maxLength: 20 }),
            fc.constant(null),
          ),
          sourcePage: fc.oneof(
            fc.integer({ min: 1, max: 10000 }),
            fc.constant(null),
          ),
          sourceText: fc.oneof(fc.string(), fc.constant(null)),
        }),
        (payload) => {
          const result = UpdateIndicatorSchema.safeParse(payload);
          expect(result.success).toBe(true);
        },
      ),
      { numRuns: 100 },
    );
  });

  // --- VerifySchema ---

  it("rejects verify requests with non-boolean humanVerified", () => {
    fc.assert(
      fc.property(
        fc.oneof(
          fc.string(),
          fc.integer(),
          fc.constant(null),
          fc.constant(undefined),
        ),
        (humanVerified) => {
          const result = VerifySchema.safeParse({ humanVerified });
          expect(result.success).toBe(false);
        },
      ),
      { numRuns: 100 },
    );
  });

  it("rejects verify requests with missing humanVerified", () => {
    const result = VerifySchema.safeParse({});
    expect(result.success).toBe(false);
  });

  it("accepts valid verify requests", () => {
    fc.assert(
      fc.property(fc.boolean(), (humanVerified) => {
        const result = VerifySchema.safeParse({ humanVerified });
        expect(result.success).toBe(true);
      }),
      { numRuns: 100 },
    );
  });

  // --- FilterQuerySchema ---

  it("rejects filter queries where country is not exactly 2 characters", () => {
    fc.assert(
      fc.property(
        fc
          .string({ minLength: 1, maxLength: 100 })
          .filter((s) => s.length !== 2),
        (country) => {
          const result = FilterQuerySchema.safeParse({ country });
          expect(result.success).toBe(false);
        },
      ),
      { numRuns: 100 },
    );
  });

  it("rejects filter queries where state exceeds max length", () => {
    fc.assert(
      fc.property(fc.string({ minLength: 11, maxLength: 200 }), (state) => {
        const result = FilterQuerySchema.safeParse({ state });
        expect(result.success).toBe(false);
      }),
      { numRuns: 100 },
    );
  });

  it("accepts valid filter queries", () => {
    fc.assert(
      fc.property(
        fc.record({
          country: fc.string({ minLength: 2, maxLength: 2 }),
          state: fc.string({ minLength: 1, maxLength: 10 }),
        }),
        (payload) => {
          const result = FilterQuerySchema.safeParse(payload);
          expect(result.success).toBe(true);
        },
      ),
      { numRuns: 100 },
    );
  });

  // --- Cross-schema: arbitrary invalid types at top level ---

  it("rejects non-object payloads for all update schemas", () => {
    const schemas = [
      UpdateDomainSchema,
      UpdateStrandSchema,
      UpdateSubStrandSchema,
      UpdateIndicatorSchema,
      VerifySchema,
      FilterQuerySchema,
    ];

    fc.assert(
      fc.property(
        fc.oneof(fc.string(), fc.integer(), fc.boolean(), fc.constant(null)),
        (payload) => {
          for (const schema of schemas) {
            const result = schema.safeParse(payload);
            expect(result.success).toBe(false);
          }
        },
      ),
      { numRuns: 100 },
    );
  });
});
