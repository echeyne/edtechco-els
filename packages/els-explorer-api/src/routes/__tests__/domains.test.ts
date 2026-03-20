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

import domains from "../domains.js";
import { updateRow, deleteRow, queryOne, query } from "../../db/client.js";

const mockedUpdateRow = vi.mocked(updateRow);
const mockedDeleteRow = vi.mocked(deleteRow);
const mockedQueryOne = vi.mocked(queryOne);
const mockedQuery = vi.mocked(query);

function createApp() {
  const app = new Hono();
  app.route("/api/domains", domains);
  return app;
}

const sampleDomainRow = {
  id: 10,
  document_id: 1,
  code: "D1",
  name: "Domain 1",
  description: "A domain",
  human_verified: false,
  verified_at: null,
  verified_by: null,
  edited_at: "2024-06-01T00:00:00Z",
  edited_by: "editor@test.com",
};

describe("PUT /api/domains/:id", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("updates a domain and returns the mapped result", async () => {
    mockedUpdateRow.mockResolvedValue(sampleDomainRow as never);

    const app = createApp();
    const res = await app.request("/api/domains/10", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: "Updated Domain", code: "D1-U" }),
    });

    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.id).toBe(10);
    expect(body.documentId).toBe(1);
    expect(body.editedBy).toBe("editor@test.com");

    // Verify updateRow was called with snake_case fields and audit extras
    expect(mockedUpdateRow).toHaveBeenCalledWith(
      "domains",
      10,
      { name: "Updated Domain", code: "D1-U" },
      { edited_at: "NOW()", edited_by: "editor@test.com" },
    );
  });

  it("returns 404 when domain not found", async () => {
    mockedUpdateRow.mockResolvedValue(null);

    const app = createApp();
    const res = await app.request("/api/domains/999", {
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
    const res = await app.request("/api/domains/abc", {
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
    const res = await app.request("/api/domains/10", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ code: "A".repeat(21) }),
    });

    expect(res.status).toBe(400);
    const body = await res.json();
    expect(body.error.code).toBe("VALIDATION_ERROR");
  });

  it("passes only provided fields to updateRow", async () => {
    mockedUpdateRow.mockResolvedValue(sampleDomainRow as never);

    const app = createApp();
    await app.request("/api/domains/10", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ description: null }),
    });

    expect(mockedUpdateRow).toHaveBeenCalledWith(
      "domains",
      10,
      { description: null },
      { edited_at: "NOW()", edited_by: "editor@test.com" },
    );
  });
});

describe("DELETE /api/domains/:id", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("cascade deletes domain and all children", async () => {
    mockedQueryOne.mockResolvedValue({ id: 10 } as never);
    mockedQuery.mockResolvedValue({ rows: [], rowCount: 0 } as never);
    mockedDeleteRow.mockResolvedValue(true);

    const app = createApp();
    const res = await app.request("/api/domains/10", { method: "DELETE" });

    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.success).toBe(true);

    // Verify cascade order: indicators, sub_strands, strands, then domain
    expect(mockedQuery).toHaveBeenCalledTimes(3);
    expect(mockedQuery.mock.calls[0][0]).toContain("DELETE FROM indicators");
    expect(mockedQuery.mock.calls[1][0]).toContain("DELETE FROM sub_strands");
    expect(mockedQuery.mock.calls[2][0]).toContain("DELETE FROM strands");
    expect(mockedDeleteRow).toHaveBeenCalledWith("domains", 10);
  });

  it("returns 404 when domain not found", async () => {
    mockedQueryOne.mockResolvedValue(null);

    const app = createApp();
    const res = await app.request("/api/domains/999", { method: "DELETE" });

    expect(res.status).toBe(404);
    const body = await res.json();
    expect(body.error.code).toBe("NOT_FOUND");
  });

  it("returns 400 for invalid id", async () => {
    const app = createApp();
    const res = await app.request("/api/domains/abc", { method: "DELETE" });

    expect(res.status).toBe(400);
    const body = await res.json();
    expect(body.error.code).toBe("VALIDATION_ERROR");
  });
});

describe("PATCH /api/domains/:id/verify", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("sets verification to true with timestamp and user", async () => {
    mockedQueryOne.mockResolvedValue({
      ...sampleDomainRow,
      human_verified: true,
      verified_at: "2024-06-15T12:00:00Z",
      verified_by: "editor@test.com",
    } as never);

    const app = createApp();
    const res = await app.request("/api/domains/10/verify", {
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
      ...sampleDomainRow,
      human_verified: false,
      verified_at: null,
      verified_by: null,
    } as never);

    const app = createApp();
    const res = await app.request("/api/domains/10/verify", {
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

  it("returns 404 when domain not found", async () => {
    mockedQueryOne.mockResolvedValue(null);

    const app = createApp();
    const res = await app.request("/api/domains/999/verify", {
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
    const res = await app.request("/api/domains/10/verify", {
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
    const res = await app.request("/api/domains/abc/verify", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ humanVerified: true }),
    });

    expect(res.status).toBe(400);
    const body = await res.json();
    expect(body.error.code).toBe("VALIDATION_ERROR");
  });
});
