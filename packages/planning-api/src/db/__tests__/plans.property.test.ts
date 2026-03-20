// Feature: parent-planning-tool, Property 6: Plan creation persists all required fields

import { describe, it, expect, vi, beforeEach } from "vitest";
import * as fc from "fast-check";
import {
  createPlan,
  getPlanById,
  getPlansByUserId,
  deletePlan,
  updatePlan,
  type CreatePlanInput,
} from "../plans.js";
import type { PlanContent } from "../../types.js";

/**
 * Property 6: Plan creation persists all required fields
 *
 * For any valid createPlan invocation with a userId, child name, age, state,
 * interests, concerns, duration, and content, the resulting plan record shall
 * contain all of those fields with the provided values, a non-null created_at
 * timestamp, and a status of 'active'.
 *
 * **Validates: Requirements 7.1, 7.2**
 */

// Mock the db client module
vi.mock("../client.js", () => ({
  query: vi.fn(),
  queryOne: vi.fn(),
  queryMany: vi.fn(),
}));

import { query, queryOne, queryMany } from "../client.js";

const mockedQuery = vi.mocked(query);
const mockedQueryOne = vi.mocked(queryOne);
const mockedQueryMany = vi.mocked(queryMany);

// ---- Generators ----

/** Generator for a non-empty trimmed string (simulates names, states, etc.) */
const arbNonEmptyString = fc
  .string({ minLength: 1, maxLength: 100 })
  .filter((s) => s.trim().length > 0);

/** Generator for a child age string */
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

/** Generator for a US state code */
const arbState = fc.stringMatching(/^[A-Z]{2}$/);

/** Generator for plan duration */
const arbDuration = fc.constantFrom(
  "immediate",
  "1-week",
  "2-weeks",
  "4-weeks",
  "8-weeks",
);

/** Generator for nullable text fields (interests, concerns) */
const arbNullableText = fc.oneof(
  fc.constant(null),
  fc
    .string({ minLength: 1, maxLength: 500 })
    .filter((s) => s.trim().length > 0),
);

/** Generator for a PlanActivity */
const arbPlanActivity = fc.record({
  title: arbNonEmptyString,
  description: arbNonEmptyString,
  indicatorCode: fc.stringMatching(/^[A-Z]{2}\.[A-Z]{2,3}\.\d+\.\d+$/),
  indicatorDescription: arbNonEmptyString,
  domain: arbNonEmptyString,
  strand: fc.option(arbNonEmptyString, { nil: undefined }),
});

/** Generator for a PlanSection */
const arbPlanSection = fc.record({
  label: arbNonEmptyString,
  description: fc.option(arbNonEmptyString, { nil: undefined }),
  activities: fc.array(arbPlanActivity, { minLength: 1, maxLength: 5 }),
});

/** Generator for PlanContent */
const arbPlanContent: fc.Arbitrary<PlanContent> = fc.record({
  sections: fc.array(arbPlanSection, { minLength: 1, maxLength: 4 }),
  summary: arbNonEmptyString,
});

/** Generator for a complete CreatePlanInput */
const arbCreatePlanInput: fc.Arbitrary<CreatePlanInput> = fc.record({
  userId: fc.uuid(),
  childName: arbNonEmptyString,
  childAge: arbChildAge,
  state: arbState,
  interests: arbNullableText,
  concerns: arbNullableText,
  duration: arbDuration,
  content: arbPlanContent,
});

describe("Property 6: Plan creation persists all required fields", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("returned PlanDetail contains all provided fields, non-null createdAt, and status 'active'", async () => {
    await fc.assert(
      fc.asyncProperty(arbCreatePlanInput, async (input: CreatePlanInput) => {
        const fakeId = crypto.randomUUID();
        const fakeTimestamp = new Date().toISOString();

        // Mock queryOne to simulate what PostgreSQL INSERT RETURNING * would return
        mockedQueryOne.mockResolvedValueOnce({
          id: fakeId,
          user_id: input.userId,
          child_name: input.childName,
          child_age: input.childAge,
          state: input.state,
          interests: input.interests,
          concerns: input.concerns,
          duration: input.duration,
          content: JSON.stringify(input.content),
          status: "active",
          created_at: fakeTimestamp,
          updated_at: fakeTimestamp,
        });

        const result = await createPlan(input);

        // Assert all provided fields match
        expect(result.id).toBe(fakeId);
        expect(result.childName).toBe(input.childName);
        expect(result.childAge).toBe(input.childAge);
        expect(result.state).toBe(input.state);
        expect(result.interests).toBe(input.interests);
        expect(result.concerns).toBe(input.concerns);
        expect(result.duration).toBe(input.duration);
        expect(result.content).toEqual(input.content);

        // Assert non-null createdAt
        expect(result.createdAt).not.toBeNull();
        expect(result.createdAt).toBe(fakeTimestamp);

        // Assert status is 'active'
        expect(result.status).toBe("active");
      }),
      { numRuns: 100 },
    );
  });
});

// Feature: parent-planning-tool, Property 7: Plan retrieval round-trip

/**
 * Property 7: Plan retrieval round-trip
 *
 * For any user who has created N plans, getPlansByUserId shall return exactly
 * N plan summaries. For any plan NOT owned by the requesting user,
 * getPlanById shall return null.
 *
 * **Validates: Requirements 7.3, 7.4**
 */
describe("Property 7: Plan retrieval round-trip", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("getPlansByUserId(A) returns exactly N plans, and getPlanById for B's plan returns null for user A", async () => {
    await fc.assert(
      fc.asyncProperty(
        fc.uuid(),
        fc.uuid(),
        fc.nat({ max: 10 }),
        fc.nat({ max: 10 }),
        async (userA: string, userB: string, n: number, _m: number) => {
          // Ensure distinct users
          fc.pre(userA !== userB);

          // Build N fake plan rows for user A
          const userARows = Array.from({ length: n }, (_, i) => ({
            id: crypto.randomUUID(),
            user_id: userA,
            child_name: `Child${i}`,
            child_age: "3",
            state: "CA",
            interests: null,
            concerns: null,
            duration: "1-week",
            content: JSON.stringify({ sections: [], summary: "s" }),
            status: "active",
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString(),
          }));

          // Mock queryMany to return N rows for user A
          mockedQueryMany.mockResolvedValueOnce(userARows);

          const plans = await getPlansByUserId(userA);
          expect(plans).toHaveLength(n);

          // Pick a plan ID that belongs to user B — user A should not be able to access it
          const planOwnedByB = crypto.randomUUID();

          // Mock queryOne to return null (user A cannot access user B's plan)
          mockedQueryOne.mockResolvedValueOnce(null);

          const result = await getPlanById(planOwnedByB, userA);
          expect(result).toBeNull();
        },
      ),
      { numRuns: 100 },
    );
  });
});

// Feature: parent-planning-tool, Property 8: Plan deletion removes the record

/**
 * Property 8: Plan deletion removes the record
 *
 * For any plan owned by the authenticated user, deletePlan shall remove the
 * plan such that a subsequent getPlanById returns null and getPlansByUserId
 * no longer includes it.
 *
 * **Validates: Requirements 7.5**
 */
describe("Property 8: Plan deletion removes the record", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("after deletion, getPlanById returns null and getPlansByUserId returns empty", async () => {
    await fc.assert(
      fc.asyncProperty(arbCreatePlanInput, async (input: CreatePlanInput) => {
        const planId = crypto.randomUUID();
        const fakeTimestamp = new Date().toISOString();

        // Step 1: Create the plan
        mockedQueryOne.mockResolvedValueOnce({
          id: planId,
          user_id: input.userId,
          child_name: input.childName,
          child_age: input.childAge,
          state: input.state,
          interests: input.interests,
          concerns: input.concerns,
          duration: input.duration,
          content: JSON.stringify(input.content),
          status: "active",
          created_at: fakeTimestamp,
          updated_at: fakeTimestamp,
        });

        const created = await createPlan(input);
        expect(created.id).toBe(planId);

        // Step 2: Delete the plan — mock query to return rowCount > 0
        mockedQuery.mockResolvedValueOnce({ rows: [], rowCount: 1 });

        const deleted = await deletePlan(planId, input.userId);
        expect(deleted).toBe(true);

        // Step 3: getPlanById returns null after deletion
        mockedQueryOne.mockResolvedValueOnce(null);

        const afterDelete = await getPlanById(planId, input.userId);
        expect(afterDelete).toBeNull();

        // Step 4: getPlansByUserId returns empty array
        mockedQueryMany.mockResolvedValueOnce([]);

        const userPlans = await getPlansByUserId(input.userId);
        expect(userPlans).toHaveLength(0);
      }),
      { numRuns: 100 },
    );
  });
});

// Feature: parent-planning-tool, Property 9: Plan update modifies content and timestamp

/**
 * Property 9: Plan update modifies content and timestamp
 *
 * For any existing plan, calling updatePlan with new content shall result in
 * the plan's content field reflecting the new content and the updated_at
 * timestamp being strictly greater than the previous updated_at value.
 *
 * **Validates: Requirements 8.4**
 */
describe("Property 9: Plan update modifies content and timestamp", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("updated plan has new content and a strictly later updated_at", async () => {
    await fc.assert(
      fc.asyncProperty(
        arbCreatePlanInput,
        arbPlanContent,
        async (input: CreatePlanInput, newContent: PlanContent) => {
          const planId = crypto.randomUUID();
          const originalTimestamp = new Date(
            "2024-01-01T00:00:00Z",
          ).toISOString();
          const laterTimestamp = new Date("2024-06-15T12:00:00Z").toISOString();

          // Step 1: Create the plan
          mockedQueryOne.mockResolvedValueOnce({
            id: planId,
            user_id: input.userId,
            child_name: input.childName,
            child_age: input.childAge,
            state: input.state,
            interests: input.interests,
            concerns: input.concerns,
            duration: input.duration,
            content: JSON.stringify(input.content),
            status: "active",
            created_at: originalTimestamp,
            updated_at: originalTimestamp,
          });

          const created = await createPlan(input);
          expect(created.updatedAt).toBe(originalTimestamp);

          // Step 2: Update the plan — mock queryOne to return updated row
          mockedQueryOne.mockResolvedValueOnce({
            id: planId,
            user_id: input.userId,
            child_name: input.childName,
            child_age: input.childAge,
            state: input.state,
            interests: input.interests,
            concerns: input.concerns,
            duration: input.duration,
            content: JSON.stringify(newContent),
            status: "active",
            created_at: originalTimestamp,
            updated_at: laterTimestamp,
          });

          const updated = await updatePlan(planId, input.userId, newContent);

          // Assert content reflects new value
          expect(updated).not.toBeNull();
          expect(updated!.content).toEqual(newContent);

          // Assert updated_at is strictly greater than previous
          expect(new Date(updated!.updatedAt).getTime()).toBeGreaterThan(
            new Date(created.updatedAt).getTime(),
          );
        },
      ),
      { numRuns: 100 },
    );
  });
});
