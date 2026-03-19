import { Hono } from "hono";
import { updateRow, deleteRow, queryOne, query } from "../db/client.js";
import { UpdateStrandSchema, VerifySchema } from "../schemas/index.js";
import {
  requireAuth,
  requireEditPermission,
  type AuthEnv,
  type AuthUser,
} from "../middleware/auth.js";
import type { Strand } from "@els/shared";

const strands = new Hono<AuthEnv>();

// ---- Row → camelCase mapper ----

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
  };
}

// ---- PUT /api/strands/:id ----

strands.put("/:id", requireAuth, requireEditPermission, async (c) => {
  const id = Number(c.req.param("id"));
  if (Number.isNaN(id)) {
    return c.json(
      { error: { code: "VALIDATION_ERROR", message: "Invalid strand id" } },
      400,
    );
  }

  const body = await c.req.json();
  const parsed = UpdateStrandSchema.safeParse(body);
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
  if (parsed.data.domainId !== undefined)
    fields.domain_id = parsed.data.domainId;

  const row = await updateRow("strands", id, fields, {
    edited_at: "NOW()",
    edited_by: user.displayName,
  });

  if (!row) {
    return c.json(
      { error: { code: "NOT_FOUND", message: "Strand not found" } },
      404,
    );
  }

  return c.json(mapStrand(row as unknown as Record<string, unknown>));
});

// ---- DELETE /api/strands/:id ----

strands.delete("/:id", requireAuth, requireEditPermission, async (c) => {
  const id = Number(c.req.param("id"));
  if (Number.isNaN(id)) {
    return c.json(
      { error: { code: "VALIDATION_ERROR", message: "Invalid strand id" } },
      400,
    );
  }

  // Check strand exists
  const existing = await queryOne("SELECT id FROM strands WHERE id = $1", [id]);
  if (!existing) {
    return c.json(
      { error: { code: "NOT_FOUND", message: "Strand not found" } },
      404,
    );
  }

  // Cascade delete: indicators → sub_strands → strand
  await query(`DELETE FROM indicators WHERE strand_id = $1`, [id]);
  await query(`DELETE FROM sub_strands WHERE strand_id = $1`, [id]);
  await deleteRow("strands", id);

  return c.json({ success: true });
});

// ---- PATCH /api/strands/:id/verify ----

strands.patch("/:id/verify", requireAuth, requireEditPermission, async (c) => {
  const id = Number(c.req.param("id"));
  if (Number.isNaN(id)) {
    return c.json(
      { error: { code: "VALIDATION_ERROR", message: "Invalid strand id" } },
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
      `UPDATE strands SET human_verified = true, verified_at = NOW(), verified_by = $2 WHERE id = $1 RETURNING *`,
      [id, user.displayName],
    );
  } else {
    row = await queryOne(
      `UPDATE strands SET human_verified = false, verified_at = NULL, verified_by = NULL WHERE id = $1 RETURNING *`,
      [id],
    );
  }

  if (!row) {
    return c.json(
      { error: { code: "NOT_FOUND", message: "Strand not found" } },
      404,
    );
  }

  const strand = mapStrand(row as unknown as Record<string, unknown>);
  return c.json({
    success: true,
    verifiedAt: strand.verifiedAt?.toISOString() ?? null,
    verifiedBy: strand.verifiedBy ?? null,
  });
});

export default strands;
