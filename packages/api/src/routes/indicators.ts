import { Hono } from "hono";
import { updateRow, deleteRow, queryOne } from "../db/client.js";
import { UpdateIndicatorSchema, VerifySchema } from "../schemas/index.js";
import {
  requireAuth,
  requireEditPermission,
  type AuthEnv,
  type AuthUser,
} from "../middleware/auth.js";
import type { Indicator } from "@els/shared";

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
  };
}

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

  // Check indicator exists
  const existing = await queryOne("SELECT id FROM indicators WHERE id = $1", [
    id,
  ]);
  if (!existing) {
    return c.json(
      { error: { code: "NOT_FOUND", message: "Indicator not found" } },
      404,
    );
  }

  await deleteRow("indicators", id);

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
