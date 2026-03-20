// Feature: parent-planning-tool, Property 10: PDF data includes all required plan fields

import { describe, it, expect } from "vitest";
import * as fc from "fast-check";
import { preparePdfData } from "../PlanPdfDownload";
import type { PlanDetail, PlanActivity, PlanSection } from "@/types";

/**
 * Property 10: PDF data includes all required plan fields
 *
 * For any valid PlanDetail object, the PDF data preparation function shall
 * produce output containing the child's first name, age, state, plan duration,
 * every activity description from every section, and every associated indicator
 * code and description.
 *
 * **Validates: Requirements 9.2**
 */

// ---- Generators ----

/** Non-empty trimmed string */
const arbNonEmptyString = fc
  .string({ minLength: 1, maxLength: 80 })
  .filter((s) => s.trim().length > 0);

/** Child age string */
const arbChildAge = fc.constantFrom(
  "0-1",
  "1-2",
  "2-3",
  "3",
  "4",
  "4-5",
  "5",
  "infant",
  "toddler",
  "preschool",
);

/** US state code */
const arbState = fc.stringMatching(/^[A-Z]{2}$/);

/** Plan duration */
const arbDuration = fc.constantFrom(
  "immediate",
  "1-week",
  "2-weeks",
  "4-weeks",
  "8-weeks",
);

/** Indicator code like "MA.PK.1.2" */
const arbIndicatorCode = fc.stringMatching(/^[A-Z]{2}\.[A-Z]{2,3}\.\d+\.\d+$/);

/** PlanActivity */
const arbPlanActivity: fc.Arbitrary<PlanActivity> = fc.record({
  title: arbNonEmptyString,
  description: arbNonEmptyString,
  indicatorCode: arbIndicatorCode,
  indicatorDescription: arbNonEmptyString,
  domain: arbNonEmptyString,
  strand: fc.option(arbNonEmptyString, { nil: undefined }),
});

/** PlanSection */
const arbPlanSection: fc.Arbitrary<PlanSection> = fc.record({
  label: arbNonEmptyString,
  description: fc.option(arbNonEmptyString, { nil: undefined }),
  activities: fc.array(arbPlanActivity, { minLength: 1, maxLength: 5 }),
});

/** Full PlanDetail object */
const arbPlanDetail: fc.Arbitrary<PlanDetail> = fc.record({
  id: fc.uuid(),
  childName: arbNonEmptyString,
  childAge: arbChildAge,
  state: arbState,
  duration: arbDuration,
  status: fc.constant("active"),
  createdAt: fc.constant(new Date().toISOString()),
  updatedAt: fc.constant(new Date().toISOString()),
  interests: fc.option(arbNonEmptyString, { nil: null }),
  concerns: fc.option(arbNonEmptyString, { nil: null }),
  content: fc.record({
    sections: fc.array(arbPlanSection, { minLength: 1, maxLength: 4 }),
    summary: arbNonEmptyString,
  }),
});

describe("Property 10: PDF data includes all required plan fields", () => {
  it("preparePdfData output contains child name, age, state, duration, all activity descriptions, and all indicator codes/descriptions", () => {
    fc.assert(
      fc.property(arbPlanDetail, (plan: PlanDetail) => {
        const pdfData = preparePdfData(plan);

        // Child profile fields
        expect(pdfData.childName).toBe(plan.childName);
        expect(pdfData.childAge).toBe(plan.childAge);
        expect(pdfData.state).toBe(plan.state);
        expect(pdfData.duration).toBe(plan.duration);

        // Collect all activities from the source plan
        const allSourceActivities = plan.content.sections.flatMap(
          (s) => s.activities,
        );

        // PDF data must contain every activity
        expect(pdfData.activities).toHaveLength(allSourceActivities.length);

        // Every activity description, indicator code, and indicator description must be present
        for (const sourceActivity of allSourceActivities) {
          const match = pdfData.activities.find(
            (a) =>
              a.description === sourceActivity.description &&
              a.indicatorCode === sourceActivity.indicatorCode &&
              a.indicatorDescription === sourceActivity.indicatorDescription,
          );
          expect(match).toBeDefined();
        }
      }),
      { numRuns: 100 },
    );
  });
});
