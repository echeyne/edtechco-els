import { describe, it, expect, vi, beforeEach } from "vitest";
import { Hono } from "hono";

// Mock the db client before importing the route module
vi.mock("../../db/client.js", () => ({
  queryMany: vi.fn(),
}));

import filters from "../filters.js";
import { queryMany } from "../../db/client.js";

const mockedQueryMany = vi.mocked(queryMany);

function createApp() {
  const app = new Hono();
  app.route("/api/filters", filters);
  return app;
}

describe("GET /api/filters", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("returns countries and states from the database", async () => {
    mockedQueryMany
      .mockResolvedValueOnce([{ country: "AU" }, { country: "US" }])
      .mockResolvedValueOnce([
        { state: "CA" },
        { state: "NSW" },
        { state: "TX" },
      ]);

    const app = createApp();
    const res = await app.request("/api/filters");
    expect(res.status).toBe(200);

    const body = await res.json();
    expect(body).toEqual({
      countries: ["AU", "US"],
      states: ["CA", "NSW", "TX"],
    });
  });

  it("returns empty arrays when no documents exist", async () => {
    mockedQueryMany.mockResolvedValueOnce([]).mockResolvedValueOnce([]);

    const app = createApp();
    const res = await app.request("/api/filters");
    expect(res.status).toBe(200);

    const body = await res.json();
    expect(body).toEqual({ countries: [], states: [] });
  });

  it("queries distinct countries ordered alphabetically", async () => {
    mockedQueryMany.mockResolvedValueOnce([]).mockResolvedValueOnce([]);

    const app = createApp();
    await app.request("/api/filters");

    const countrySql = mockedQueryMany.mock.calls[0][0];
    expect(countrySql).toContain("DISTINCT country");
    expect(countrySql).toContain("ORDER BY country");
  });

  it("queries distinct states ordered alphabetically", async () => {
    mockedQueryMany.mockResolvedValueOnce([]).mockResolvedValueOnce([]);

    const app = createApp();
    await app.request("/api/filters");

    const stateSql = mockedQueryMany.mock.calls[1][0];
    expect(stateSql).toContain("DISTINCT state");
    expect(stateSql).toContain("ORDER BY state");
  });
});
