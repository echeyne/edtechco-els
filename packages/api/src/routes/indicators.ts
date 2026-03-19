import { Hono } from "hono";
import { updateRow, queryOne, softDeleteRow } from "../db/client.js";
import { UpdateIndicatorSchema, VerifySchema } from "../schemas/index.js";
import {
  requireAuth,
  requireEditPermission,
  type AuthEnv,
  type AuthUser,
} from "../middleware/auth.js";
import type { Indicator, SubStrand, Strand, Domain } from "@els/shared";

const indicators = new Hono<AuthEnv>();

// ---- Row → camelCase mapper ----

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

// ---- GET /api/indicators/:id ----

indicators.get("/:id", async (c) => {
  const id = Number(c.req.param("id"));
  if (Number.isNaN(id)) {
    return c.json(
      { error: { code: "VALIDATION_ERROR", message: "Invalid indicator id" } },
      400,
    );
  }

  const row = await queryOne(
    "SELECT * FROM indicators WHERE id = $1 AND deleted = false",
    [id],
  );
  if (!row) {
    return c.json(
      { error: { code: "NOT_FOUND", message: "Indicator not found" } },
      404,
    );
  }

  const indicator = mapIndicator(row as unknown as Record<string, unknown>);

  // Fetch parent sub-strand (if any)
  let subStrand = null;
  if (indicator.subStrandId) {
    const ssRow = await queryOne(
      "SELECT * FROM sub_strands WHERE id = $1 AND deleted = false",
      [indicator.subStrandId],
    );
    subStrand = ssRow
      ? mapSubStrand(ssRow as unknown as Record<string, unknown>)
      : null;
  }

  // Fetch parent strand (if any)
  let strand = null;
  if (indicator.strandId) {
    const sRow = await queryOne(
      "SELECT * FROM strands WHERE id = $1 AND deleted = false",
      [indicator.strandId],
    );
    strand = sRow
      ? mapStrand(sRow as unknown as Record<string, unknown>)
      : null;
  } else if (subStrand) {
    const sRow = await queryOne(
      "SELECT * FROM strands WHERE id = $1 AND deleted = false",
      [subStrand.strandId],
    );
    strand = sRow
      ? mapStrand(sRow as unknown as Record<string, unknown>)
      : null;
  }

  // Fetch parent domain
  let domain = null;
  if (indicator.domainId) {
    const dRow = await queryOne(
      "SELECT * FROM domains WHERE id = $1 AND deleted = false",
      [indicator.domainId],
    );
    domain = dRow
      ? mapDomain(dRow as unknown as Record<string, unknown>)
      : null;
  }

  return c.json({ ...indicator, subStrand, strand, domain });
});

// ---- PUT /api/indicators/:id ----

indicators.put("/:id", requireAuth, requireEditPermission, async (c) => {
  const id = Number(c.req.param("id"));
  if (Number.isNaN(id)) {
    return c.json(
      { error: { code: "VALIDATION_ERROR", message: "Invalid indicator id" } },
      400,
    );
  }

  const body = await c.req.json();
  const parsed = UpdateIndicatorSchema.safeParse(body);
  if (!parsed.success) {
    return c.json(
      {
        error: {
          code: "VALIDATION_ERROR",
          message: "Invalid request body",
          details: parsed.error.flatten(),
        },
      },
      400,
    );
  }

  const user = c.get("authUser") as AuthUser;

  // Map camelCase body fields to snake_case column names
  const fields: Record<string, unknown> = {};
  if (parsed.data.code !== undefined) fields.code = parsed.data.code;
  if (parsed.data.title !== undefined) fields.title = parsed.data.title;
  if (parsed.data.description !== undefined)
    fields.description = parsed.data.description;
  if (parsed.data.ageBand !== undefined) fields.age_band = parsed.data.ageBand;
  if (parsed.data.sourcePage !== undefined)
    fields.source_page = parsed.data.sourcePage;
  if (parsed.data.sourceText !== undefined)
    fields.source_text = parsed.data.sourceText;
  if (parsed.data.subStrandId !== undefined)
    fields.sub_strand_id = parsed.data.subStrandId;

  const row = await updateRow("indicators", id, fields, {
    edited_at: "NOW()",
    edited_by: user.displayName,
  });

  if (!row) {
    return c.json(
      { error: { code: "NOT_FOUND", message: "Indicator not found" } },
      404,
    );
  }

  return c.json(mapIndicator(row as unknown as Record<string, unknown>));
});

// ---- DELETE /api/indicators/:id ----

indicators.delete("/:id", requireAuth, requireEditPermission, async (c) => {
  const id = Number(c.req.param("id"));
  if (Number.isNaN(id)) {
    return c.json(
      { error: { code: "VALIDATION_ERROR", message: "Invalid indicator id" } },
      400,
    );
  }

  // Check indicator exists and is not already deleted
  const existing = await queryOne(
    "SELECT id FROM indicators WHERE id = $1 AND deleted = false",
    [id],
  );
  if (!existing) {
    return c.json(
      { error: { code: "NOT_FOUND", message: "Indicator not found" } },
      404,
    );
  }

  const user = c.get("authUser") as AuthUser;
  await softDeleteRow("indicators", id, user.displayName);

  return c.json({ success: true });
});

// ---- PATCH /api/indicators/:id/verify ----

indicators.patch(
  "/:id/verify",
  requireAuth,
  requireEditPermission,
  async (c) => {
    const id = Number(c.req.param("id"));
    if (Number.isNaN(id)) {
      return c.json(
        {
          error: { code: "VALIDATION_ERROR", message: "Invalid indicator id" },
        },
        400,
      );
    }

    const body = await c.req.json();
    const parsed = VerifySchema.safeParse(body);
    if (!parsed.success) {
      return c.json(
        {
          error: {
            code: "VALIDATION_ERROR",
            message: "Invalid request body",
            details: parsed.error.flatten(),
          },
        },
        400,
      );
    }

    const user = c.get("authUser") as AuthUser;
    const { humanVerified } = parsed.data;

    let row: Record<string, unknown> | null;

    if (humanVerified) {
      row = await queryOne(
        `UPDATE indicators SET human_verified = true, verified_at = NOW(), verified_by = $2 WHERE id = $1 RETURNING *`,
        [id, user.displayName],
      );
    } else {
      row = await queryOne(
        `UPDATE indicators SET human_verified = false, verified_at = NULL, verified_by = NULL WHERE id = $1 RETURNING *`,
        [id],
      );
    }

    if (!row) {
      return c.json(
        { error: { code: "NOT_FOUND", message: "Indicator not found" } },
        404,
      );
    }

    const indicator = mapIndicator(row as unknown as Record<string, unknown>);
    return c.json({
      success: true,
      verifiedAt: indicator.verifiedAt?.toISOString() ?? null,
      verifiedBy: indicator.verifiedBy ?? null,
    });
  },
);

export default indicators;
