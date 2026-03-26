import { describe, it, expect, beforeAll, afterAll, afterEach } from "vitest";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import {
  getDocuments,
  getHierarchy,
  getPdfUrl,
  getFilters,
  updateDomain,
  deleteDomain,
  verifyDomain,
} from "../api";

// ---- Mock data ----

const mockDocuments = [
  {
    id: 1,
    country: "US",
    state: "CA",
    title: "California ELS",
    versionYear: 2023,
    sourceUrl: null,
    ageBand: "0-5",
    publishingAgency: "CA Dept of Ed",
    createdAt: "2024-01-01T00:00:00.000Z",
  },
  {
    id: 2,
    country: "US",
    state: "NY",
    title: "New York ELS",
    versionYear: 2022,
    sourceUrl: null,
    ageBand: "3-5",
    publishingAgency: "NY Dept of Ed",
    createdAt: "2024-01-01T00:00:00.000Z",
  },
];

const mockHierarchy = {
  document: mockDocuments[0],
  domains: [
    {
      id: 10,
      documentId: 1,
      code: "D1",
      name: "Language",
      description: null,
      humanVerified: false,
      verifiedAt: null,
      verifiedBy: null,
      editedAt: null,
      editedBy: null,
      strands: [],
    },
  ],
};

const mockPdfUrl = {
  url: "https://s3.amazonaws.com/bucket/doc.pdf?signed=abc",
  expiresAt: "2024-12-31T23:59:59.000Z",
};

const mockFilters = {
  countries: ["US", "UK"],
  states: ["CA", "NY", "TX"],
};

const mockUpdatedDomain = {
  id: 10,
  documentId: 1,
  code: "D1-updated",
  name: "Updated Language",
  description: "Updated desc",
  humanVerified: false,
  verifiedAt: null,
  verifiedBy: null,
  editedAt: "2024-06-01T00:00:00.000Z",
  editedBy: "user@test.com",
};

// ---- MSW handlers (use wildcard * to match any base URL) ----

const handlers = [
  http.get("*/api/documents", ({ request }) => {
    const url = new URL(request.url);
    const country = url.searchParams.get("country");
    if (country) {
      const filtered = mockDocuments.filter((d) => d.country === country);
      return HttpResponse.json(filtered);
    }
    return HttpResponse.json(mockDocuments);
  }),

  http.get("*/api/documents/:id/hierarchy", ({ params }) => {
    if (params.id === "1") {
      return HttpResponse.json(mockHierarchy);
    }
    return HttpResponse.json(
      { error: { code: "NOT_FOUND", message: "Not found" } },
      { status: 404 },
    );
  }),

  http.get("*/api/documents/:id/pdf-url", () => {
    return HttpResponse.json(mockPdfUrl);
  }),

  http.get("*/api/filters", () => {
    return HttpResponse.json(mockFilters);
  }),

  http.put("*/api/domains/:id", async ({ request, params }) => {
    const auth = request.headers.get("Authorization");
    if (!auth) {
      return HttpResponse.json(
        { error: { code: "UNAUTHORIZED", message: "Missing token" } },
        { status: 401 },
      );
    }
    return HttpResponse.json({ ...mockUpdatedDomain, id: Number(params.id) });
  }),

  http.delete("*/api/domains/:id", ({ request }) => {
    const auth = request.headers.get("Authorization");
    if (!auth) {
      return HttpResponse.json(
        { error: { code: "UNAUTHORIZED", message: "Missing token" } },
        { status: 401 },
      );
    }
    return HttpResponse.json({ success: true });
  }),

  http.patch("*/api/domains/:id/verify", async ({ request }) => {
    const auth = request.headers.get("Authorization");
    if (!auth) {
      return HttpResponse.json(
        { error: { code: "UNAUTHORIZED", message: "Missing token" } },
        { status: 401 },
      );
    }
    return HttpResponse.json({
      success: true,
      verifiedAt: "2024-06-01T00:00:00.000Z",
      verifiedBy: "user@test.com",
    });
  }),
];

const server = setupServer(...handlers);

beforeAll(() => server.listen());
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

describe("API client integration tests", () => {
  // -- Read endpoints --

  it("getDocuments fetches documents list", async () => {
    const docs = await getDocuments();
    expect(docs).toHaveLength(2);
    expect(docs[0].title).toBe("California ELS");
    expect(docs[1].state).toBe("NY");
  });

  it("getDocuments sends correct query params for country filter", async () => {
    const docs = await getDocuments({ country: "US" });
    expect(docs).toHaveLength(2);
    docs.forEach((d) => expect(d.country).toBe("US"));
  });

  it("getHierarchy fetches hierarchy for a document", async () => {
    const hierarchy = await getHierarchy(1);
    expect(hierarchy.document.id).toBe(1);
    expect(hierarchy.domains).toHaveLength(1);
    expect(hierarchy.domains[0].code).toBe("D1");
  });

  it("getPdfUrl returns pre-signed URL", async () => {
    const result = await getPdfUrl(1);
    expect(result.url).toContain("s3.amazonaws.com");
    expect(result.expiresAt).toBeDefined();
  });

  it("getFilters returns available filters", async () => {
    const filters = await getFilters();
    expect(filters.countries).toContain("US");
    expect(filters.states).toContain("CA");
  });

  // -- Write endpoints --

  it("updateDomain sends PUT with auth header", async () => {
    const result = await updateDomain(
      10,
      { code: "D1-updated", name: "Updated Language" },
      "my-token",
    );
    expect(result.id).toBe(10);
    expect(result.code).toBe("D1-updated");
  });

  it("deleteDomain sends DELETE with auth header", async () => {
    const result = await deleteDomain(10, "my-token");
    expect(result.success).toBe(true);
  });

  it("verifyDomain sends PATCH with auth header", async () => {
    const result = await verifyDomain(10, { humanVerified: true }, "my-token");
    expect(result.success).toBe(true);
    expect(result.verifiedAt).toBeDefined();
    expect(result.verifiedBy).toBe("user@test.com");
  });

  // -- Error handling --

  it("throws error with status code on non-OK response", async () => {
    server.use(
      http.get("*/api/documents", () => {
        return HttpResponse.json(
          { error: { code: "INTERNAL_ERROR", message: "Something broke" } },
          { status: 500 },
        );
      }),
    );

    try {
      await getDocuments();
      expect.fail("Should have thrown");
    } catch (err: unknown) {
      const error = err as Error & { status: number };
      expect(error.status).toBe(500);
    }
  });

  it("includes error message from response body", async () => {
    server.use(
      http.get("*/api/filters", () => {
        return HttpResponse.json(
          {
            error: { code: "INTERNAL_ERROR", message: "DB connection failed" },
          },
          { status: 503 },
        );
      }),
    );

    try {
      await getFilters();
      expect.fail("Should have thrown");
    } catch (err: unknown) {
      const error = err as Error & { status: number; body: unknown };
      expect(error.message).toBe("DB connection failed");
      expect(error.status).toBe(503);
    }
  });
});
