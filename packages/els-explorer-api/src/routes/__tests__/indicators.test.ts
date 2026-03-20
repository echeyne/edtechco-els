import { describe, it, expect, vi, beforeEach } from "vitest";
import { Hono } from "hono";

// Mock the db client before importing the route module
vi.mock("../../db/client.js", () => ({
  updateRow: vi.fn(),
  deleteRow: vi.fn(),
  queryOne: vi.fn(),
  query: vi.fn(),
}));

// Mock the auth middleware
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

import indicators from "../indicators.js";
import { updateRow, deleteRow, queryOne } from "../../db/client.js";

const mockedUpdateRow = vi.mocked(updateRow);
const mockedDeleteRow = vi.mocked(deleteRow);
const mockedQueryOne = vi.mocked(queryOne);

function createApp() {
  const app = new Hono();
  app.route("/api/indicators", indicators);
  return app;
}

const sampleIndicatorRow = {
  id: 50,
  standard_id: "STD-001",
  domain_id: 10,
  strand_id: 20,
  sub_strand_id: 30,
  code: "I1",
  title: "Indicator 1",
  description: "An indicator",
  age_band: "3-5",
  source_page: 12,
  source_text: "Some source text",
  human_verified: false,
  verified_at: null,
  verified_by: null,
  edited_at: "2024-06-01T00:00:00Z",
  edited_by: "editor@test.com",
  last_verified: null,
  created_at: "2024-01-01T00:00:00Z",
};

describe("PUT /api/indicators/:id", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("updates an indicator and returns the mapped result", async () => {
    mockedUpdateRow.mockResolvedValue(sampleIndicatorRow as never);

    const app = createApp();
    const res = await app.request("/api/indicators/50", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title: "Updated Indicator", code: "I1-U" }),
    });

    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.id).toBe(50);
    expect(body.standardId).toBe("STD-001");
    expect(body.domainId).toBe(10);
    expect(body.strandId).toBe(20);
    expect(body.subStrandId).toBe(30);
    expect(body.ageBand).toBe("3-5");
    expect(body.sourcePage).toBe(12);
    expect(body.sourceText).toBe("Some source text");
    expect(body.editedBy).toBe("editor@test.com");

    expect(mockedUpdateRow).toHaveBeenCalledWith(
      "indicators",
      50,
      { title: "Updated Indicator", code: "I1-U" },
      { edited_at: "NOW()", edited_by: "editor@test.com" },
    );
  });

  it("maps ageBand, sourcePage, sourceText to snake_case", async () => {
    mockedUpdateRow.mockResolvedValue(sampleIndicatorRow as never);

    const app = createApp();
    await app.request("/api/indicators/50", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        ageBand: "0-3",
        sourcePage: 5,
        sourceText: "new text",
      }),
    });

    expect(mockedUpdateRow).toHaveBeenCalledWith(
      "indicators",
      50,
      { age_band: "0-3", source_page: 5, source_text: "new text" },
      { edited_at: "NOW()", edited_by: "editor@test.com" },
    );
  });

  it("returns 404 when indicator not found", async () => {
    mockedUpdateRow.mockResolvedValue(null);

    const app = createApp();
    const res = await app.request("/api/indicators/999", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title: "Nope" }),
    });

    expect(res.status).toBe(404);
    const body = await res.json();
    expect(body.error.code).toBe("NOT_FOUND");
  });

  it("returns 400 for invalid id", async () => {
    const app = createApp();
    const res = await app.request("/api/indicators/abc", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title: "Test" }),
    });

    expect(res.status).toBe(400);
    const body = await res.json();
    expect(body.error.code).toBe("VALIDATION_ERROR");
  });

  it("returns 400 for invalid body (code too long)", async () => {
    const app = createApp();
    const res = await app.request("/api/indicators/50", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ code: "A".repeat(51) }),
    });

    expect(res.status).toBe(400);
    const body = await res.json();
    expect(body.error.code).toBe("VALIDATION_ERROR");
  });

  it("passes only provided fields to updateRow", async () => {
    mockedUpdateRow.mockResolvedValue(sampleIndicatorRow as never);

    const app = createApp();
    await app.request("/api/indicators/50", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ description: "updated desc" }),
    });

    expect(mockedUpdateRow).toHaveBeenCalledWith(
      "indicators",
      50,
      { description: "updated desc" },
      { edited_at: "NOW()", edited_by: "editor@test.com" },
    );
  });
});

describe("DELETE /api/indicators/:id", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("deletes an indicator (no cascade needed)", async () => {
    mockedQueryOne.mockResolvedValue({ id: 50 } as never);
    mockedDeleteRow.mockResolvedValue(true);

    const app = createApp();
    const res = await app.request("/api/indicators/50", { method: "DELETE" });

    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.success).toBe(true);

    expect(mockedDeleteRow).toHaveBeenCalledWith("indicators", 50);
  });

  it("returns 404 when indicator not found", async () => {
    mockedQueryOne.mockResolvedValue(null);

    const app = createApp();
    const res = await app.request("/api/indicators/999", { method: "DELETE" });

    expect(res.status).toBe(404);
    const body = await res.json();
    expect(body.error.code).toBe("NOT_FOUND");
  });

  it("returns 400 for invalid id", async () => {
    const app = createApp();
    const res = await app.request("/api/indicators/abc", { method: "DELETE" });

    expect(res.status).toBe(400);
    const body = await res.json();
    expect(body.error.code).toBe("VALIDATION_ERROR");
  });
});

describe("PATCH /api/indicators/:id/verify", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("sets verification to true with timestamp and user", async () => {
    mockedQueryOne.mockResolvedValue({
      ...sampleIndicatorRow,
      human_verified: true,
      verified_at: "2024-06-15T12:00:00Z",
      verified_by: "editor@test.com",
    } as never);

    const app = createApp();
    const res = await app.request("/api/indicators/50/verify", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ humanVerified: true }),
    });

    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.success).toBe(true);
    expect(body.verifiedAt).toBeDefined();
    expect(body.verifiedBy).toBe("editor@test.com");

    const sql = mockedQueryOne.mock.calls[0][0];
    expect(sql).toContain("human_verified = true");
    expect(sql).toContain("verified_at = NOW()");
    expect(sql).toContain("verified_by = $2");
  });

  it("clears verification when set to false", async () => {
    mockedQueryOne.mockResolvedValue({
      ...sampleIndicatorRow,
      human_verified: false,
      verified_at: null,
      verified_by: null,
    } as never);

    const app = createApp();
    const res = await app.request("/api/indicators/50/verify", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ humanVerified: false }),
    });

    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.success).toBe(true);
    expect(body.verifiedAt).toBeNull();
    expect(body.verifiedBy).toBeNull();

    const sql = mockedQueryOne.mock.calls[0][0];
    expect(sql).toContain("human_verified = false");
    expect(sql).toContain("verified_at = NULL");
    expect(sql).toContain("verified_by = NULL");
  });

  it("returns 404 when indicator not found", async () => {
    mockedQueryOne.mockResolvedValue(null);

    const app = createApp();
    const res = await app.request("/api/indicators/999/verify", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ humanVerified: true }),
    });

    expect(res.status).toBe(404);
    const body = await res.json();
    expect(body.error.code).toBe("NOT_FOUND");
  });

  it("returns 400 for invalid body", async () => {
    const app = createApp();
    const res = await app.request("/api/indicators/50/verify", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ humanVerified: "yes" }),
    });

    expect(res.status).toBe(400);
    const body = await res.json();
    expect(body.error.code).toBe("VALIDATION_ERROR");
  });

  it("returns 400 for invalid id", async () => {
    const app = createApp();
    const res = await app.request("/api/indicators/abc/verify", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ humanVerified: true }),
    });

    expect(res.status).toBe(400);
    const body = await res.json();
    expect(body.error.code).toBe("VALIDATION_ERROR");
  });
});
