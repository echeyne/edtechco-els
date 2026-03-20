import { describe, it, expect, vi, beforeEach } from "vitest";
import type { BedrockAgentActionGroupEvent } from "../handler.js";

// Mock the db client
vi.mock("../../db/client.js", () => ({
  query: vi.fn(),
  queryOne: vi.fn(),
  queryMany: vi.fn(),
}));

// Mock the plans module
vi.mock("../../db/plans.js", () => ({
  createPlan: vi.fn(),
  getPlanById: vi.fn(),
  updatePlan: vi.fn(),
  deletePlan: vi.fn(),
}));

import { handler } from "../handler.js";
import { queryMany } from "../../db/client.js";
import {
  createPlan,
  getPlanById,
  updatePlan,
  deletePlan,
} from "../../db/plans.js";

const mockedQueryMany = vi.mocked(queryMany);
const mockedCreatePlan = vi.mocked(createPlan);
const mockedGetPlanById = vi.mocked(getPlanById);
const mockedUpdatePlan = vi.mocked(updatePlan);
const mockedDeletePlan = vi.mocked(deletePlan);

function makeEvent(
  overrides: Partial<BedrockAgentActionGroupEvent>,
): BedrockAgentActionGroupEvent {
  return {
    actionGroup: "StandardsQuery",
    apiPath: "/getAvailableStates",
    httpMethod: "GET",
    ...overrides,
  };
}

describe("Action Group Handler", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe("routing", () => {
    it("returns error for unknown action group", async () => {
      const event = makeEvent({ actionGroup: "Unknown" });
      const result = await handler(event);

      expect(result.messageVersion).toBe("1.0");
      expect(result.response.httpStatusCode).toBe(400);
      expect(
        JSON.parse(result.response.responseBody["application/json"].body),
      ).toEqual({
        error: "Unknown action group: Unknown",
      });
    });
  });

  describe("StandardsQuery - getAvailableStates", () => {
    it("returns distinct states from documents", async () => {
      mockedQueryMany.mockResolvedValueOnce([
        { state: "CA" },
        { state: "NY" },
        { state: "TX" },
      ]);

      const event = makeEvent({
        actionGroup: "StandardsQuery",
        apiPath: "/getAvailableStates",
        httpMethod: "GET",
      });

      const result = await handler(event);
      expect(result.response.httpStatusCode).toBe(200);

      const body = JSON.parse(
        result.response.responseBody["application/json"].body,
      );
      expect(body.states).toEqual(["CA", "NY", "TX"]);
    });
  });

  describe("StandardsQuery - getAgeBands", () => {
    it("returns age bands for a given state", async () => {
      mockedQueryMany.mockResolvedValueOnce([
        { age_band: "0-1" },
        { age_band: "3-4" },
      ]);

      const event = makeEvent({
        actionGroup: "StandardsQuery",
        apiPath: "/getAgeBands",
        httpMethod: "GET",
        parameters: [{ name: "state", value: "CA" }],
      });

      const result = await handler(event);
      expect(result.response.httpStatusCode).toBe(200);

      const body = JSON.parse(
        result.response.responseBody["application/json"].body,
      );
      expect(body.ageBands).toEqual(["0-1", "3-4"]);
    });

    it("returns 400 when state parameter is missing", async () => {
      const event = makeEvent({
        actionGroup: "StandardsQuery",
        apiPath: "/getAgeBands",
        httpMethod: "GET",
        parameters: [],
      });

      const result = await handler(event);
      expect(result.response.httpStatusCode).toBe(400);
    });
  });

  describe("StandardsQuery - getIndicators", () => {
    it("returns indicators for state and ageBand", async () => {
      mockedQueryMany.mockResolvedValueOnce([
        {
          code: "MA.PK.1.1",
          description: "Counts to 10",
          domain_name: "Mathematics",
          strand_name: "Number Sense",
          sub_strand_name: "Counting",
          age_band: "3-4",
        },
      ]);

      const event = makeEvent({
        actionGroup: "StandardsQuery",
        apiPath: "/getIndicators",
        httpMethod: "GET",
        parameters: [
          { name: "state", value: "CA" },
          { name: "ageBand", value: "3-4" },
        ],
      });

      const result = await handler(event);
      expect(result.response.httpStatusCode).toBe(200);

      const body = JSON.parse(
        result.response.responseBody["application/json"].body,
      );
      expect(body.indicators).toHaveLength(1);
      expect(body.indicators[0].code).toBe("MA.PK.1.1");
    });

    it("returns 400 when parameters are missing", async () => {
      const event = makeEvent({
        actionGroup: "StandardsQuery",
        apiPath: "/getIndicators",
        httpMethod: "GET",
        parameters: [{ name: "state", value: "CA" }],
      });

      const result = await handler(event);
      expect(result.response.httpStatusCode).toBe(400);
    });

    it("returns 404 for unknown StandardsQuery path", async () => {
      const event = makeEvent({
        actionGroup: "StandardsQuery",
        apiPath: "/unknownPath",
        httpMethod: "GET",
      });

      const result = await handler(event);
      expect(result.response.httpStatusCode).toBe(404);
    });
  });

  describe("PlanManagement - createPlan", () => {
    it("creates a plan from request body properties", async () => {
      const fakePlan = {
        id: "plan-123",
        childName: "Alice",
        childAge: "3",
        state: "CA",
        interests: "dinosaurs",
        concerns: null,
        duration: "1-week",
        content: { sections: [], summary: "test" },
        status: "active",
        createdAt: "2024-01-01T00:00:00Z",
        updatedAt: "2024-01-01T00:00:00Z",
      };
      mockedCreatePlan.mockResolvedValueOnce(fakePlan);

      const event = makeEvent({
        actionGroup: "PlanManagement",
        apiPath: "/createPlan",
        httpMethod: "POST",
        requestBody: {
          content: {
            "application/json": {
              properties: [
                { name: "userId", value: "user-1" },
                { name: "childName", value: "Alice" },
                { name: "childAge", value: "3" },
                { name: "state", value: "CA" },
                { name: "interests", value: "dinosaurs" },
                { name: "duration", value: "1-week" },
                {
                  name: "content",
                  value: JSON.stringify({ sections: [], summary: "test" }),
                },
              ],
            },
          },
        },
      });

      const result = await handler(event);
      expect(result.response.httpStatusCode).toBe(201);

      const body = JSON.parse(
        result.response.responseBody["application/json"].body,
      );
      expect(body.plan.id).toBe("plan-123");
      expect(mockedCreatePlan).toHaveBeenCalledOnce();
    });

    it("returns 400 when required fields are missing", async () => {
      const event = makeEvent({
        actionGroup: "PlanManagement",
        apiPath: "/createPlan",
        httpMethod: "POST",
        requestBody: {
          content: {
            "application/json": {
              properties: [{ name: "userId", value: "user-1" }],
            },
          },
        },
      });

      const result = await handler(event);
      expect(result.response.httpStatusCode).toBe(400);
    });

    it("returns 400 for invalid JSON in content", async () => {
      const event = makeEvent({
        actionGroup: "PlanManagement",
        apiPath: "/createPlan",
        httpMethod: "POST",
        requestBody: {
          content: {
            "application/json": {
              properties: [
                { name: "userId", value: "user-1" },
                { name: "childName", value: "Alice" },
                { name: "childAge", value: "3" },
                { name: "state", value: "CA" },
                { name: "duration", value: "1-week" },
                { name: "content", value: "not-json{" },
              ],
            },
          },
        },
      });

      const result = await handler(event);
      expect(result.response.httpStatusCode).toBe(400);
      const body = JSON.parse(
        result.response.responseBody["application/json"].body,
      );
      expect(body.error).toContain("Invalid JSON");
    });
  });

  describe("PlanManagement - getPlan", () => {
    it("returns a plan by ID and userId", async () => {
      const fakePlan = {
        id: "plan-123",
        childName: "Bob",
        childAge: "4",
        state: "NY",
        interests: null,
        concerns: null,
        duration: "2-weeks",
        content: { sections: [], summary: "s" },
        status: "active",
        createdAt: "2024-01-01T00:00:00Z",
        updatedAt: "2024-01-01T00:00:00Z",
      };
      mockedGetPlanById.mockResolvedValueOnce(fakePlan);

      const event = makeEvent({
        actionGroup: "PlanManagement",
        apiPath: "/getPlan",
        httpMethod: "GET",
        parameters: [
          { name: "planId", value: "plan-123" },
          { name: "userId", value: "user-1" },
        ],
      });

      const result = await handler(event);
      expect(result.response.httpStatusCode).toBe(200);

      const body = JSON.parse(
        result.response.responseBody["application/json"].body,
      );
      expect(body.plan.id).toBe("plan-123");
    });

    it("returns 404 when plan not found", async () => {
      mockedGetPlanById.mockResolvedValueOnce(null);

      const event = makeEvent({
        actionGroup: "PlanManagement",
        apiPath: "/getPlan",
        httpMethod: "GET",
        parameters: [
          { name: "planId", value: "nonexistent" },
          { name: "userId", value: "user-1" },
        ],
      });

      const result = await handler(event);
      expect(result.response.httpStatusCode).toBe(404);
    });
  });

  describe("PlanManagement - updatePlan", () => {
    it("updates plan content", async () => {
      const updatedPlan = {
        id: "plan-123",
        childName: "Alice",
        childAge: "3",
        state: "CA",
        interests: null,
        concerns: null,
        duration: "1-week",
        content: { sections: [], summary: "updated" },
        status: "active",
        createdAt: "2024-01-01T00:00:00Z",
        updatedAt: "2024-06-01T00:00:00Z",
      };
      mockedUpdatePlan.mockResolvedValueOnce(updatedPlan);

      const event = makeEvent({
        actionGroup: "PlanManagement",
        apiPath: "/updatePlan",
        httpMethod: "PUT",
        requestBody: {
          content: {
            "application/json": {
              properties: [
                { name: "planId", value: "plan-123" },
                { name: "userId", value: "user-1" },
                {
                  name: "content",
                  value: JSON.stringify({ sections: [], summary: "updated" }),
                },
              ],
            },
          },
        },
      });

      const result = await handler(event);
      expect(result.response.httpStatusCode).toBe(200);
      expect(mockedUpdatePlan).toHaveBeenCalledOnce();
    });

    it("returns 404 when plan not found for update", async () => {
      mockedUpdatePlan.mockResolvedValueOnce(null);

      const event = makeEvent({
        actionGroup: "PlanManagement",
        apiPath: "/updatePlan",
        httpMethod: "PUT",
        requestBody: {
          content: {
            "application/json": {
              properties: [
                { name: "planId", value: "nonexistent" },
                { name: "userId", value: "user-1" },
                {
                  name: "content",
                  value: JSON.stringify({ sections: [], summary: "x" }),
                },
              ],
            },
          },
        },
      });

      const result = await handler(event);
      expect(result.response.httpStatusCode).toBe(404);
    });
  });

  describe("PlanManagement - deletePlan", () => {
    it("deletes a plan successfully", async () => {
      mockedDeletePlan.mockResolvedValueOnce(true);

      const event = makeEvent({
        actionGroup: "PlanManagement",
        apiPath: "/deletePlan",
        httpMethod: "DELETE",
        parameters: [
          { name: "planId", value: "plan-123" },
          { name: "userId", value: "user-1" },
        ],
      });

      const result = await handler(event);
      expect(result.response.httpStatusCode).toBe(200);

      const body = JSON.parse(
        result.response.responseBody["application/json"].body,
      );
      expect(body.success).toBe(true);
    });

    it("returns 404 when plan not found for deletion", async () => {
      mockedDeletePlan.mockResolvedValueOnce(false);

      const event = makeEvent({
        actionGroup: "PlanManagement",
        apiPath: "/deletePlan",
        httpMethod: "DELETE",
        parameters: [
          { name: "planId", value: "nonexistent" },
          { name: "userId", value: "user-1" },
        ],
      });

      const result = await handler(event);
      expect(result.response.httpStatusCode).toBe(404);
    });
  });

  describe("PlanManagement - unknown path", () => {
    it("returns 404 for unknown PlanManagement path", async () => {
      const event = makeEvent({
        actionGroup: "PlanManagement",
        apiPath: "/unknownPath",
        httpMethod: "GET",
      });

      const result = await handler(event);
      expect(result.response.httpStatusCode).toBe(404);
    });
  });

  describe("error handling", () => {
    it("catches thrown errors and returns 500", async () => {
      mockedQueryMany.mockRejectedValueOnce(new Error("DB connection failed"));

      const event = makeEvent({
        actionGroup: "StandardsQuery",
        apiPath: "/getAvailableStates",
        httpMethod: "GET",
      });

      const result = await handler(event);
      expect(result.response.httpStatusCode).toBe(500);

      const body = JSON.parse(
        result.response.responseBody["application/json"].body,
      );
      expect(body.error).toBe("DB connection failed");
    });
  });

  describe("response format", () => {
    it("always returns correct Bedrock Agent response structure", async () => {
      mockedQueryMany.mockResolvedValueOnce([{ state: "CA" }]);

      const event = makeEvent({
        actionGroup: "StandardsQuery",
        apiPath: "/getAvailableStates",
        httpMethod: "GET",
      });

      const result = await handler(event);

      expect(result.messageVersion).toBe("1.0");
      expect(result.response.actionGroup).toBe("StandardsQuery");
      expect(result.response.apiPath).toBe("/getAvailableStates");
      expect(result.response.httpMethod).toBe("GET");
      expect(typeof result.response.httpStatusCode).toBe("number");
      expect(typeof result.response.responseBody["application/json"].body).toBe(
        "string",
      );
    });
  });
});
