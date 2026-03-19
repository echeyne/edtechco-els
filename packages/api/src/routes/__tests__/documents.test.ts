import { describe, it, expect, vi, beforeEach } from "vitest";
import { Hono } from "hono";

// Mock the db client before importing the route module
vi.mock("../../db/client.js", () => ({
  queryMany: vi.fn(),
  queryOne: vi.fn(),
}));

// Mock the S3 presigner
vi.mock("@aws-sdk/s3-request-presigner", () => ({
  getSignedUrl: vi.fn(),
}));

vi.mock("@aws-sdk/client-s3", () => ({
  S3Client: vi.fn(),
  GetObjectCommand: vi.fn(),
}));

import documents from "../documents.js";
import { queryMany, queryOne } from "../../db/client.js";
import { getSignedUrl } from "@aws-sdk/s3-request-presigner";

const mockedQueryMany = vi.mocked(queryMany);
const mockedQueryOne = vi.mocked(queryOne);
const mockedGetSignedUrl = vi.mocked(getSignedUrl);

function createApp() {
  const app = new Hono();
  app.route("/api/documents", documents);
  return app;
}

describe("GET /api/documents", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("returns all documents when no filters provided", async () => {
    mockedQueryMany.mockResolvedValue([
      {
        id: 1,
        country: "US",
        state: "CA",
        title: "California ELS",
        version_year: 2023,
        source_url: "US/CA/2023/doc.pdf",
        age_band: "0-5",
        publishing_agency: "CDE",
        created_at: "2024-01-01T00:00:00Z",
      },
    ]);

    const app = createApp();
    const res = await app.request("/api/documents");
    expect(res.status).toBe(200);

    const body = await res.json();
    expect(body).toHaveLength(1);
    expect(body[0].country).toBe("US");
    expect(body[0].versionYear).toBe(2023);
    expect(body[0].sourceUrl).toBe("US/CA/2023/doc.pdf");
  });

  it("filters by country", async () => {
    mockedQueryMany.mockResolvedValue([]);

    const app = createApp();
    const res = await app.request("/api/documents?country=US");
    expect(res.status).toBe(200);

    const sql = mockedQueryMany.mock.calls[0][0];
    expect(sql).toContain("country = $1");
    expect(mockedQueryMany.mock.calls[0][1]).toEqual(["US"]);
  });

  it("filters by country and state", async () => {
    mockedQueryMany.mockResolvedValue([]);

    const app = createApp();
    const res = await app.request("/api/documents?country=US&state=CA");
    expect(res.status).toBe(200);

    const sql = mockedQueryMany.mock.calls[0][0];
    expect(sql).toContain("country = $1");
    expect(sql).toContain("state = $2");
    expect(mockedQueryMany.mock.calls[0][1]).toEqual(["US", "CA"]);
  });

  it("rejects invalid country filter", async () => {
    const app = createApp();
    const res = await app.request("/api/documents?country=TOOLONG");
    expect(res.status).toBe(400);

    const body = await res.json();
    expect(body.error.code).toBe("VALIDATION_ERROR");
  });
});

describe("GET /api/documents/:id/hierarchy", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("returns 404 for non-existent document", async () => {
    mockedQueryOne.mockResolvedValue(null);

    const app = createApp();
    const res = await app.request("/api/documents/999/hierarchy");
    expect(res.status).toBe(404);

    const body = await res.json();
    expect(body.error.code).toBe("NOT_FOUND");
  });

  it("returns 400 for invalid id", async () => {
    const app = createApp();
    const res = await app.request("/api/documents/abc/hierarchy");
    expect(res.status).toBe(400);
  });

  it("returns nested hierarchy for a document", async () => {
    mockedQueryOne.mockResolvedValue({
      id: 1,
      country: "US",
      state: "CA",
      title: "Test Doc",
      version_year: 2023,
      source_url: null,
      age_band: "0-5",
      publishing_agency: "Agency",
      created_at: "2024-01-01T00:00:00Z",
    });

    // domains, strands, sub_strands, indicators
    mockedQueryMany
      .mockResolvedValueOnce([
        {
          id: 10,
          document_id: 1,
          code: "D1",
          name: "Domain 1",
          description: null,
          human_verified: false,
          verified_at: null,
          verified_by: null,
          edited_at: null,
          edited_by: null,
        },
      ])
      .mockResolvedValueOnce([
        {
          id: 20,
          domain_id: 10,
          code: "S1",
          name: "Strand 1",
          description: null,
          human_verified: false,
          verified_at: null,
          verified_by: null,
          edited_at: null,
          edited_by: null,
        },
      ])
      .mockResolvedValueOnce([
        {
          id: 30,
          strand_id: 20,
          code: "SS1",
          name: "SubStrand 1",
          description: null,
          human_verified: false,
          verified_at: null,
          verified_by: null,
          edited_at: null,
          edited_by: null,
        },
      ])
      .mockResolvedValueOnce([
        {
          id: 40,
          standard_id: "STD-001",
          domain_id: 10,
          strand_id: 20,
          sub_strand_id: 30,
          code: "I1",
          title: "Indicator 1",
          description: "Desc",
          age_band: "3-5",
          source_page: 5,
          source_text: "text",
          human_verified: true,
          verified_at: "2024-01-01T00:00:00Z",
          verified_by: "user@test.com",
          edited_at: null,
          edited_by: null,
          last_verified: null,
          created_at: "2024-01-01T00:00:00Z",
        },
      ]);

    const app = createApp();
    const res = await app.request("/api/documents/1/hierarchy");
    expect(res.status).toBe(200);

    const body = await res.json();
    expect(body.document.id).toBe(1);
    expect(body.domains).toHaveLength(1);
    expect(body.domains[0].strands).toHaveLength(1);
    expect(body.domains[0].strands[0].subStrands).toHaveLength(1);
    expect(body.domains[0].strands[0].subStrands[0].indicators).toHaveLength(1);
    expect(
      body.domains[0].strands[0].subStrands[0].indicators[0].standardId,
    ).toBe("STD-001");
    expect(
      body.domains[0].strands[0].subStrands[0].indicators[0].humanVerified,
    ).toBe(true);
  });

  it("returns empty domains for document with no children", async () => {
    mockedQueryOne.mockResolvedValue({
      id: 2,
      country: "UK",
      state: "EN",
      title: "Empty Doc",
      version_year: 2024,
      source_url: null,
      age_band: "",
      publishing_agency: "",
      created_at: "2024-01-01T00:00:00Z",
    });

    mockedQueryMany
      .mockResolvedValueOnce([]) // domains
      .mockResolvedValueOnce([]) // strands
      .mockResolvedValueOnce([]) // sub_strands
      .mockResolvedValueOnce([]); // indicators

    const app = createApp();
    const res = await app.request("/api/documents/2/hierarchy");
    expect(res.status).toBe(200);

    const body = await res.json();
    expect(body.document.id).toBe(2);
    expect(body.domains).toHaveLength(0);
  });
});

describe("GET /api/documents/:id/pdf-url", () => {
  const originalEnv = process.env;

  beforeEach(() => {
    vi.clearAllMocks();
    process.env = { ...originalEnv, ELS_RAW_BUCKET: "test-bucket" };
  });

  it("returns 404 for non-existent document", async () => {
    mockedQueryOne.mockResolvedValue(null);

    const app = createApp();
    const res = await app.request("/api/documents/999/pdf-url");
    expect(res.status).toBe(404);
  });

  it("returns 404 when document has no source_url", async () => {
    mockedQueryOne.mockResolvedValue({
      id: 1,
      country: "US",
      state: "CA",
      title: "No PDF",
      version_year: 2023,
      source_url: null,
      s3_key: null,
      age_band: "",
      publishing_agency: "",
      created_at: "2024-01-01T00:00:00Z",
    });

    const app = createApp();
    const res = await app.request("/api/documents/1/pdf-url");
    expect(res.status).toBe(404);

    const body = await res.json();
    expect(body.error.message).toContain("no source PDF");
  });

  it("returns pre-signed URL with expiry", async () => {
    mockedQueryOne.mockResolvedValue({
      id: 1,
      country: "US",
      state: "CA",
      title: "Test Doc",
      version_year: 2023,
      source_url: "https://www.cde.ca.gov/doc.pdf",
      s3_key: "US/CA/2023/doc.pdf",
      age_band: "0-5",
      publishing_agency: "CDE",
      created_at: "2024-01-01T00:00:00Z",
    });

    mockedGetSignedUrl.mockResolvedValue("https://s3.example.com/signed-url");

    const app = createApp();
    const res = await app.request("/api/documents/1/pdf-url");
    expect(res.status).toBe(200);

    const body = await res.json();
    expect(body.url).toBe("https://s3.example.com/signed-url");
    expect(body.expiresAt).toBeDefined();
    // Verify expiresAt is roughly 1 hour from now
    const expiresAt = new Date(body.expiresAt).getTime();
    const now = Date.now();
    expect(expiresAt - now).toBeGreaterThan(3500 * 1000);
    expect(expiresAt - now).toBeLessThan(3700 * 1000);
  });

  it("returns 400 for invalid id", async () => {
    const app = createApp();
    const res = await app.request("/api/documents/abc/pdf-url");
    expect(res.status).toBe(400);
  });

  it("returns 500 when S3 bucket not configured", async () => {
    delete process.env.ELS_RAW_BUCKET;

    mockedQueryOne.mockResolvedValue({
      id: 1,
      country: "US",
      state: "CA",
      title: "Test Doc",
      version_year: 2023,
      source_url: "https://www.cde.ca.gov/doc.pdf",
      s3_key: "US/CA/2023/doc.pdf",
      age_band: "0-5",
      publishing_agency: "CDE",
      created_at: "2024-01-01T00:00:00Z",
    });

    const app = createApp();
    const res = await app.request("/api/documents/1/pdf-url");
    expect(res.status).toBe(500);

    const body = await res.json();
    expect(body.error.code).toBe("INTERNAL_ERROR");
  });
});
