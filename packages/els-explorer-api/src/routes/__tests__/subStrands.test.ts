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

import subStrands from "../subStrands.js";
import { updateRow, deleteRow, queryOne, query } from "../../db/client.js";

const mockedUpdateRow = vi.mocked(updateRow);
const mockedDeleteRow = vi.mocked(deleteRow);
const mockedQueryOne = vi.mocked(queryOne);
const mockedQuery = vi.mocked(query);

function createApp() {
  const app = new Hono();
  app.route("/api/sub-strands", subStrands);
  return app;
}

const sampleSubStrandRow = {
  id: 30,
  strand_id: 20,
  code: "SS1",
  name: "Sub-Strand 1",
  description: "A sub-strand",
  human_verified: false,
  verified_at: null,
  verified_by: null,
  edited_at: "2024-06-01T00:00:00Z",
  edited_by: "editor@test.com",
};

describe("PUT /api/sub-strands/:id", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("updates a sub-strand and returns the mapped result", async () => {
    mockedUpdateRow.mockResolvedValue(sampleSubStrandRow as never);

    const app = createApp();
    const res = await app.request("/api/sub-strands/30", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: "Updated Sub-Strand", code: "SS1-U" }),
    });

    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.id).toBe(30);
    expect(body.strandId).toBe(20);
    expect(body.editedBy).toBe("editor@test.com");

    expect(mockedUpdateRow).toHaveBeenCalledWith(
      "sub_strands",
      30,
      { name: "Updated Sub-Strand", code: "SS1-U" },
      { edited_at: "NOW()", edited_by: "editor@test.com" },
    );
  });

  it("returns 404 when sub-strand not found", async () => {
    mockedUpdateRow.mockResolvedValue(null);

    const app = createApp();
    const res = await app.request("/api/sub-strands/999", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: "Nope" }),
    });

    expect(res.status).toBe(404);
    const body = await res.json();
    expect(body.error.code).toBe("NOT_FOUND");
  });

  it("returns 400 for invalid id", async () => {
    const app = createApp();
    const res = await app.request("/api/sub-strands/abc", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: "Test" }),
    });

    expect(res.status).toBe(400);
    const body = await res.json();
    expect(body.error.code).toBe("VALIDATION_ERROR");
  });

  it("returns 400 for invalid body (code too long)", async () => {
    const app = createApp();
    const res = await app.request("/api/sub-strands/30", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ code: "A".repeat(41) }),
    });

    expect(res.status).toBe(400);
    const body = await res.json();
    expect(body.error.code).toBe("VALIDATION_ERROR");
  });

  it("passes only provided fields to updateRow", async () => {
    mockedUpdateRow.mockResolvedValue(sampleSubStrandRow as never);

    const app = createApp();
    await app.request("/api/sub-strands/30", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ description: null }),
    });

    expect(mockedUpdateRow).toHaveBeenCalledWith(
      "sub_strands",
      30,
      { description: null },
      { edited_at: "NOW()", edited_by: "editor@test.com" },
    );
  });
});

describe("DELETE /api/sub-strands/:id", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("cascade deletes sub-strand and its indicators", async () => {
    mockedQueryOne.mockResolvedValue({ id: 30 } as never);
    mockedQuery.mockResolvedValue({ rows: [], rowCount: 0 } as never);
    mockedDeleteRow.mockResolvedValue(true);

    const app = createApp();
    const res = await app.request("/api/sub-strands/30", { method: "DELETE" });

    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.success).toBe(true);

    // Verify cascade: indicators deleted, then sub_strand
    expect(mockedQuery).toHaveBeenCalledTimes(1);
    expect(mockedQuery.mock.calls[0][0]).toContain("DELETE FROM indicators");
    expect(mockedQuery.mock.calls[0][0]).toContain("sub_strand_id");
    expect(mockedDeleteRow).toHaveBeenCalledWith("sub_strands", 30);
  });

  it("returns 404 when sub-strand not found", async () => {
    mockedQueryOne.mockResolvedValue(null);

    const app = createApp();
    const res = await app.request("/api/sub-strands/999", { method: "DELETE" });

    expect(res.status).toBe(404);
    const body = await res.json();
    expect(body.error.code).toBe("NOT_FOUND");
  });

  it("returns 400 for invalid id", async () => {
    const app = createApp();
    const res = await app.request("/api/sub-strands/abc", { method: "DELETE" });

    expect(res.status).toBe(400);
    const body = await res.json();
    expect(body.error.code).toBe("VALIDATION_ERROR");
  });
});

describe("PATCH /api/sub-strands/:id/verify", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("sets verification to true with timestamp and user", async () => {
    mockedQueryOne.mockResolvedValue({
      ...sampleSubStrandRow,
      human_verified: true,
      verified_at: "2024-06-15T12:00:00Z",
      verified_by: "editor@test.com",
    } as never);

    const app = createApp();
    const res = await app.request("/api/sub-strands/30/verify", {
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
      ...sampleSubStrandRow,
      human_verified: false,
      verified_at: null,
      verified_by: null,
    } as never);

    const app = createApp();
    const res = await app.request("/api/sub-strands/30/verify", {
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

  it("returns 404 when sub-strand not found", async () => {
    mockedQueryOne.mockResolvedValue(null);

    const app = createApp();
    const res = await app.request("/api/sub-strands/999/verify", {
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
    const res = await app.request("/api/sub-strands/30/verify", {
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
    const res = await app.request("/api/sub-strands/abc/verify", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ humanVerified: true }),
    });

    expect(res.status).toBe(400);
    const body = await res.json();
    expect(body.error.code).toBe("VALIDATION_ERROR");
  });
});
