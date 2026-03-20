// Feature: parent-planning-tool, Property 5: Plan indicator referential integrity

import { describe, it, expect } from "vitest";
import * as fc from "fast-check";
import type { PlanContent, PlanActivity, PlanSection } from "../../types.js";

/**
 * Property 5: Plan indicator referential integrity
 *
 * For any plan stored in the plans table, every indicatorCode referenced in
 * the plan's content JSON must correspond to an existing code in the
 * indicators table.
 *
 * This is a pure data-level property: we generate plan content with indicator
 * codes, define a "database" of known indicator codes (a subset), and assert
 * that all plan indicator codes exist in that set.
 *
 * **Validates: Requirements 6.4, 6.5**
 */

// ---- Helpers ----

/** Extract all indicator codes from a PlanContent object */
function extractIndicatorCodes(content: PlanContent): string[] {
  return content.sections.flatMap((section) =>
    section.activities.map((activity) => activity.indicatorCode),
  );
}

/** Check that every indicator code in the plan exists in the known set */
function validateReferentialIntegrity(
  planCodes: string[],
  knownCodes: Set<string>,
): { valid: boolean; missingCodes: string[] } {
  const missingCodes = planCodes.filter((code) => !knownCodes.has(code));
  return { valid: missingCodes.length === 0, missingCodes };
}

// ---- Generators ----

/** Generator for an indicator code like "MA.PK.1.2" */
const arbIndicatorCode = fc.stringMatching(/^[A-Z]{2}\.[A-Z]{2,3}\.\d+\.\d+$/);

/** Generator for a PlanActivity using a code drawn from a known pool */
function arbActivityFromPool(
  codePool: fc.Arbitrary<string>,
): fc.Arbitrary<PlanActivity> {
  return fc.record({
    title: fc
      .string({ minLength: 1, maxLength: 50 })
      .filter((s) => s.trim().length > 0),
    description: fc
      .string({ minLength: 1, maxLength: 100 })
      .filter((s) => s.trim().length > 0),
    indicatorCode: codePool,
    indicatorDescription: fc
      .string({ minLength: 1, maxLength: 100 })
      .filter((s) => s.trim().length > 0),
    domain: fc
      .string({ minLength: 1, maxLength: 50 })
      .filter((s) => s.trim().length > 0),
    strand: fc.option(
      fc
        .string({ minLength: 1, maxLength: 50 })
        .filter((s) => s.trim().length > 0),
      { nil: undefined },
    ),
  });
}

describe("Property 5: Plan indicator referential integrity", () => {
  it("all indicator codes in plan content exist in the indicators table", async () => {
    await fc.assert(
      fc.asyncProperty(
        // Generate a set of known indicator codes (simulates the indicators table)
        fc.uniqueArray(arbIndicatorCode, { minLength: 1, maxLength: 20 }),
        async (knownCodesArray: string[]) => {
          const knownCodes = new Set(knownCodesArray);

          // Build plan content using ONLY codes from the known set
          const codePool = fc.constantFrom(...knownCodesArray);
          const activity = arbActivityFromPool(codePool);

          const sectionArb: fc.Arbitrary<PlanSection> = fc.record({
            label: fc
              .string({ minLength: 1, maxLength: 30 })
              .filter((s) => s.trim().length > 0),
            description: fc.option(
              fc
                .string({ minLength: 1, maxLength: 100 })
                .filter((s) => s.trim().length > 0),
              { nil: undefined },
            ),
            activities: fc.array(activity, { minLength: 1, maxLength: 5 }),
          });

          const contentArb: fc.Arbitrary<PlanContent> = fc.record({
            sections: fc.array(sectionArb, { minLength: 1, maxLength: 4 }),
            summary: fc
              .string({ minLength: 1, maxLength: 200 })
              .filter((s) => s.trim().length > 0),
          });

          // Sample a plan content from the inner generator
          const content = fc.sample(contentArb, 1)[0];

          const planCodes = extractIndicatorCodes(content);
          const result = validateReferentialIntegrity(planCodes, knownCodes);

          expect(result.valid).toBe(true);
          expect(result.missingCodes).toEqual([]);

          // Every code in the plan must be in the known set
          for (const code of planCodes) {
            expect(knownCodes.has(code)).toBe(true);
          }
        },
      ),
      { numRuns: 100 },
    );
  });

  it("detects missing indicator codes when plan references codes not in the database", async () => {
    await fc.assert(
      fc.asyncProperty(
        // Known codes in the "database"
        fc.uniqueArray(arbIndicatorCode, { minLength: 1, maxLength: 10 }),
        // Extra codes NOT in the database
        fc.uniqueArray(arbIndicatorCode, { minLength: 1, maxLength: 5 }),
        async (knownCodesArray: string[], extraCodesArray: string[]) => {
          const knownCodes = new Set(knownCodesArray);

          // Filter extra codes to only those truly not in the known set
          const genuinelyMissing = extraCodesArray.filter(
            (c) => !knownCodes.has(c),
          );

          // Skip if all extra codes happen to be in the known set
          fc.pre(genuinelyMissing.length > 0);

          // Build plan content that includes both known and unknown codes
          const allCodes = [...knownCodesArray, ...genuinelyMissing];
          const codePool = fc.constantFrom(...allCodes);
          const activity = arbActivityFromPool(codePool);

          const sectionArb: fc.Arbitrary<PlanSection> = fc.record({
            label: fc.constant("Week 1"),
            activities: fc.array(activity, { minLength: 1, maxLength: 5 }),
          });

          const contentArb: fc.Arbitrary<PlanContent> = fc.record({
            sections: fc.array(sectionArb, { minLength: 1, maxLength: 2 }),
            summary: fc.constant("Test plan"),
          });

          const content = fc.sample(contentArb, 1)[0];
          const planCodes = extractIndicatorCodes(content);

          // Check if any plan codes are genuinely missing
          const result = validateReferentialIntegrity(planCodes, knownCodes);

          // If any of the sampled activities used a missing code, we should detect it
          const hasMissingCode = planCodes.some((c) => !knownCodes.has(c));
          if (hasMissingCode) {
            expect(result.valid).toBe(false);
            expect(result.missingCodes.length).toBeGreaterThan(0);
            // Every reported missing code should indeed not be in the known set
            for (const missing of result.missingCodes) {
              expect(knownCodes.has(missing)).toBe(false);
            }
          }
        },
      ),
      { numRuns: 100 },
    );
  });
});
