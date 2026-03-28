import { Hono } from "hono";
import { S3Client, GetObjectCommand } from "@aws-sdk/client-s3";
import { getSignedUrl } from "@aws-sdk/s3-request-presigner";
import { queryMany, queryOne } from "../db/client.js";
import { FilterQuerySchema } from "../schemas/index.js";
import type {
  Document,
  Domain,
  Strand,
  SubStrand,
  Indicator,
  DomainWithChildren,
  StrandWithChildren,
  SubStrandWithChildren,
  HierarchyResponse,
} from "@els/shared";

const documents = new Hono();

// Lazy S3 client singleton
let _s3: S3Client | null = null;
function getS3Client(): S3Client {
  if (!_s3) {
    _s3 = new S3Client({});
  }
  return _s3;
}

/** Allow tests to inject a mock S3 client */
export function setS3Client(client: S3Client | null): void {
  _s3 = client;
}

// ---- Row → camelCase mappers ----

function mapDocument(row: Record<string, unknown>): Document {
  return {
    id: row.id as number,
    country: row.country as string,
    state: row.state as string,
    title: row.title as string,
    versionYear: row.version_year as number,
    sourceUrl: (row.source_url as string) ?? null,
    s3Key: (row.s3_key as string) ?? null,
    ageBand: (row.age_band as string) ?? "",
    publishingAgency: (row.publishing_agency as string) ?? "",
    createdAt: new Date(row.created_at as string),
  };
}

function mapDomain(row: Record<string, unknown>): Domain {
  return {
    id: row.id as number,
    documentId: row.document_id as number,
    code: row.code as string,
    name: row.name as string,
    description: (row.description as string) ?? null,
    humanVerified: (row.human_verified as boolean) ?? false,
    verifiedAt: row.verified_at ? new Date(row.verified_at as string) : null,
    verifiedBy: (row.verified_by as string) ?? null,
    editedAt: row.edited_at ? new Date(row.edited_at as string) : null,
    editedBy: (row.edited_by as string) ?? null,
    deleted: (row.deleted as boolean) ?? false,
    deletedAt: row.deleted_at ? new Date(row.deleted_at as string) : null,
    deletedBy: (row.deleted_by as string) ?? null,
  };
}

function mapStrand(row: Record<string, unknown>): Strand {
  return {
    id: row.id as number,
    domainId: row.domain_id as number,
    code: row.code as string,
    name: row.name as string,
    description: (row.description as string) ?? null,
    humanVerified: (row.human_verified as boolean) ?? false,
    verifiedAt: row.verified_at ? new Date(row.verified_at as string) : null,
    verifiedBy: (row.verified_by as string) ?? null,
    editedAt: row.edited_at ? new Date(row.edited_at as string) : null,
    editedBy: (row.edited_by as string) ?? null,
    deleted: (row.deleted as boolean) ?? false,
    deletedAt: row.deleted_at ? new Date(row.deleted_at as string) : null,
    deletedBy: (row.deleted_by as string) ?? null,
  };
}

function mapSubStrand(row: Record<string, unknown>): SubStrand {
  return {
    id: row.id as number,
    strandId: row.strand_id as number,
    code: row.code as string,
    name: row.name as string,
    description: (row.description as string) ?? null,
    humanVerified: (row.human_verified as boolean) ?? false,
    verifiedAt: row.verified_at ? new Date(row.verified_at as string) : null,
    verifiedBy: (row.verified_by as string) ?? null,
    editedAt: row.edited_at ? new Date(row.edited_at as string) : null,
    editedBy: (row.edited_by as string) ?? null,
    deleted: (row.deleted as boolean) ?? false,
    deletedAt: row.deleted_at ? new Date(row.deleted_at as string) : null,
    deletedBy: (row.deleted_by as string) ?? null,
  };
}

function mapIndicator(row: Record<string, unknown>): Indicator {
  return {
    id: row.id as number,
    standardId: row.standard_id as string,
    domainId: row.domain_id as number,
    strandId: (row.strand_id as number) ?? null,
    subStrandId: (row.sub_strand_id as number) ?? null,
    code: row.code as string,
    title: (row.title as string) ?? null,
    description: row.description as string,
    ageBand: (row.age_band as string) ?? null,
    sourcePage: (row.source_page as number) ?? null,
    sourceText: (row.source_text as string) ?? null,
    humanVerified: (row.human_verified as boolean) ?? false,
    verifiedAt: row.verified_at ? new Date(row.verified_at as string) : null,
    verifiedBy: (row.verified_by as string) ?? null,
    editedAt: row.edited_at ? new Date(row.edited_at as string) : null,
    editedBy: (row.edited_by as string) ?? null,
    lastVerified: row.last_verified
      ? new Date(row.last_verified as string)
      : null,
    createdAt: new Date(row.created_at as string),
    deleted: (row.deleted as boolean) ?? false,
    deletedAt: row.deleted_at ? new Date(row.deleted_at as string) : null,
    deletedBy: (row.deleted_by as string) ?? null,
  };
}

// ---- GET /api/documents ----

documents.get("/", async (c) => {
  const parsed = FilterQuerySchema.safeParse(c.req.query());
  if (!parsed.success) {
    return c.json(
      {
        error: {
          code: "VALIDATION_ERROR",
          message: "Invalid query parameters",
          details: parsed.error.flatten(),
        },
      },
      400,
    );
  }

  const { country, state } = parsed.data;
  const conditions: string[] = [];
  const params: unknown[] = [];

  if (country) {
    params.push(country);
    conditions.push(`country = $${params.length}`);
  }
  if (state) {
    params.push(state);
    conditions.push(`state = $${params.length}`);
  }

  const where =
    conditions.length > 0 ? `WHERE ${conditions.join(" AND ")}` : "";
  const sql = `SELECT * FROM documents ${where} ORDER BY country, state, title`;

  const rows = await queryMany(sql, params);
  const docs = rows.map((r) =>
    mapDocument(r as unknown as Record<string, unknown>),
  );
  return c.json(docs);
});

// ---- GET /api/documents/:id/hierarchy ----

documents.get("/:id/hierarchy", async (c) => {
  const id = Number(c.req.param("id"));
  if (Number.isNaN(id)) {
    return c.json(
      { error: { code: "VALIDATION_ERROR", message: "Invalid document id" } },
      400,
    );
  }

  // Fetch document
  const docRow = await queryOne("SELECT * FROM documents WHERE id = $1", [id]);
  if (!docRow) {
    return c.json(
      { error: { code: "NOT_FOUND", message: "Document not found" } },
      404,
    );
  }
  const document = mapDocument(docRow as unknown as Record<string, unknown>);

  // Fetch all children in parallel (exclude soft-deleted)
  const [domainRows, strandRows, subStrandRows, indicatorRows] =
    await Promise.all([
      queryMany(
        "SELECT * FROM domains WHERE document_id = $1 AND deleted = false ORDER BY code",
        [id],
      ),
      queryMany(
        `SELECT s.* FROM strands s
         JOIN domains d ON s.domain_id = d.id
         WHERE d.document_id = $1 AND s.deleted = false AND d.deleted = false
         ORDER BY s.code`,
        [id],
      ),
      queryMany(
        `SELECT ss.* FROM sub_strands ss
         JOIN strands s ON ss.strand_id = s.id
         JOIN domains d ON s.domain_id = d.id
         WHERE d.document_id = $1 AND ss.deleted = false AND s.deleted = false AND d.deleted = false
         ORDER BY ss.code`,
        [id],
      ),
      queryMany(
        `SELECT i.* FROM indicators i
         JOIN domains d ON i.domain_id = d.id
         WHERE d.document_id = $1 AND i.deleted = false AND d.deleted = false
         ORDER BY i.code`,
        [id],
      ),
    ]);

  const domains = domainRows.map((r) =>
    mapDomain(r as unknown as Record<string, unknown>),
  );
  const strands = strandRows.map((r) =>
    mapStrand(r as unknown as Record<string, unknown>),
  );
  const subStrands = subStrandRows.map((r) =>
    mapSubStrand(r as unknown as Record<string, unknown>),
  );
  const indicators = indicatorRows.map((r) =>
    mapIndicator(r as unknown as Record<string, unknown>),
  );

  // Build nested hierarchy
  const subStrandMap = new Map<number, SubStrandWithChildren>();
  for (const ss of subStrands) {
    subStrandMap.set(ss.id, { ...ss, indicators: [] });
  }

  const strandMap = new Map<number, StrandWithChildren>();
  for (const s of strands) {
    strandMap.set(s.id, { ...s, subStrands: [], indicators: [] });
  }

  const domainMap = new Map<number, DomainWithChildren>();
  for (const d of domains) {
    domainMap.set(d.id, { ...d, strands: [], indicators: [] });
  }

  // Attach indicators to the appropriate level based on their foreign keys
  for (const ind of indicators) {
    if (ind.subStrandId && subStrandMap.has(ind.subStrandId)) {
      // domain -> strand -> sub_strand -> indicator
      subStrandMap.get(ind.subStrandId)!.indicators.push(ind);
    } else if (ind.strandId && strandMap.has(ind.strandId)) {
      // domain -> strand -> indicator (no sub_strand)
      strandMap.get(ind.strandId)!.indicators.push(ind);
    } else if (ind.domainId && domainMap.has(ind.domainId)) {
      // domain -> indicator (no strand or sub_strand)
      domainMap.get(ind.domainId)!.indicators.push(ind);
    }
  }

  // Attach sub_strands to strands
  for (const [, ss] of subStrandMap) {
    if (strandMap.has(ss.strandId)) {
      strandMap.get(ss.strandId)!.subStrands.push(ss);
    }
  }

  // Attach strands to domains
  for (const [, s] of strandMap) {
    if (domainMap.has(s.domainId)) {
      domainMap.get(s.domainId)!.strands.push(s);
    }
  }

  const hierarchy: HierarchyResponse = {
    document,
    domains: Array.from(domainMap.values()),
  };

  return c.json(hierarchy);
});

// ---- GET /api/documents/:id/pdf-url ----

documents.get("/:id/pdf-url", async (c) => {
  const id = Number(c.req.param("id"));
  if (Number.isNaN(id)) {
    return c.json(
      { error: { code: "VALIDATION_ERROR", message: "Invalid document id" } },
      400,
    );
  }

  const docRow = await queryOne("SELECT * FROM documents WHERE id = $1", [id]);
  if (!docRow) {
    return c.json(
      { error: { code: "NOT_FOUND", message: "Document not found" } },
      404,
    );
  }

  const doc = mapDocument(docRow as unknown as Record<string, unknown>);

  // s3Key must exist and must not be an external URL (e.g. source_url
  // accidentally stored in the s3_key column).
  const hasValidS3Key = doc.s3Key && !doc.s3Key.includes("://");

  if (!hasValidS3Key) {
    return c.json(
      {
        error: {
          code: "NOT_FOUND",
          message: "Document has no source PDF in S3",
          sourceUrl: doc.sourceUrl ?? undefined,
        },
      },
      404,
    );
  }

  const bucket = process.env.ELS_RAW_BUCKET;
  if (!bucket) {
    return c.json(
      {
        error: {
          code: "INTERNAL_ERROR",
          message: "S3 bucket not configured",
        },
      },
      500,
    );
  }

  const command = new GetObjectCommand({
    Bucket: bucket,
    Key: doc.s3Key!,
    ResponseContentType: "application/pdf",
    ResponseContentDisposition: "inline",
  });

  const expiresIn = 3600; // 1 hour
  const url = await getSignedUrl(getS3Client(), command, { expiresIn });
  const expiresAt = new Date(Date.now() + expiresIn * 1000).toISOString();

  return c.json({ url, expiresAt });
});

export default documents;
