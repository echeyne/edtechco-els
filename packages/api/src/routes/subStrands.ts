import { Hono } from "hono";
import { updateRow, deleteRow, queryOne, query } from "../db/client.js";
import { UpdateSubStrandSchema, VerifySchema } from "../schemas/index.js";
import {
  requireAuth,
  requireEditPermission,
  type AuthEnv,
  type AuthUser,
} from "../middleware/auth.js";
import type { SubStrand } from "@els/shared";

const subStrands = new Hono<AuthEnv>();

// ---- Row → camelCase mapper ----

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
  };
}

// ---- PUT /api/sub-strands/:id ----

subStrands.put("/:id", requireAuth, requireEditPermission, async (c) => {
  const id = Number(c.req.param("id"));
  if (Number.isNaN(id)) {
    return c.json(
      { error: { code: "VALIDATION_ERROR", message: "Invalid sub-strand id" } },
      400,
    );
  }

  const body = await c.req.json();
  const parsed = UpdateSubStrandSchema.safeParse(body);
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
  if (parsed.data.name !== undefined) fields.name = parsed.data.name;
  if (parsed.data.description !== undefined)
    fields.description = parsed.data.description;
  if (parsed.data.strandId !== undefined)
    fields.strand_id = parsed.data.strandId;

  const row = await updateRow("sub_strands", id, fields, {
    edited_at: "NOW()",
    edited_by: user.displayName,
  });

  if (!row) {
    return c.json(
      { error: { code: "NOT_FOUND", message: "Sub-strand not found" } },
      404,
    );
  }

  return c.json(mapSubStrand(row as unknown as Record<string, unknown>));
});

// ---- DELETE /api/sub-strands/:id ----

subStrands.delete("/:id", requireAuth, requireEditPermission, async (c) => {
  const id = Number(c.req.param("id"));
  if (Number.isNaN(id)) {
    return c.json(
      { error: { code: "VALIDATION_ERROR", message: "Invalid sub-strand id" } },
      400,
    );
  }

  // Check sub-strand exists
  const existing = await queryOne("SELECT id FROM sub_strands WHERE id = $1", [
    id,
  ]);
  if (!existing) {
    return c.json(
      { error: { code: "NOT_FOUND", message: "Sub-strand not found" } },
      404,
    );
  }

  // Cascade delete: indicators → sub_strand
  await query(`DELETE FROM indicators WHERE sub_strand_id = $1`, [id]);
  await deleteRow("sub_strands", id);

  return c.json({ success: true });
});

// ---- PATCH /api/sub-strands/:id/verify ----

subStrands.patch(
  "/:id/verify",
  requireAuth,
  requireEditPermission,
  async (c) => {
    const id = Number(c.req.param("id"));
    if (Number.isNaN(id)) {
      return c.json(
        {
          error: { code: "VALIDATION_ERROR", message: "Invalid sub-strand id" },
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
        `UPDATE sub_strands SET human_verified = true, verified_at = NOW(), verified_by = $2 WHERE id = $1 RETURNING *`,
        [id, user.displayName],
      );
    } else {
      row = await queryOne(
        `UPDATE sub_strands SET human_verified = false, verified_at = NULL, verified_by = NULL WHERE id = $1 RETURNING *`,
        [id],
      );
    }

    if (!row) {
      return c.json(
        { error: { code: "NOT_FOUND", message: "Sub-strand not found" } },
        404,
      );
    }

    const subStrand = mapSubStrand(row as unknown as Record<string, unknown>);
    return c.json({
      success: true,
      verifiedAt: subStrand.verifiedAt?.toISOString() ?? null,
      verifiedBy: subStrand.verifiedBy ?? null,
    });
  },
);

export default subStrands;
