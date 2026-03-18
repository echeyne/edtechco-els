import { Hono } from "hono";
import { updateRow, deleteRow, queryOne, query } from "../db/client.js";
import { UpdateDomainSchema, VerifySchema } from "../schemas/index.js";
import {
  requireAuth,
  requireEditPermission,
  type AuthEnv,
  type AuthUser,
} from "../middleware/auth.js";
import type { Domain } from "@els/shared";

const domains = new Hono<AuthEnv>();

// ---- Row → camelCase mapper ----

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
  };
}

// ---- PUT /api/domains/:id ----

domains.put("/:id", requireAuth, requireEditPermission, async (c) => {
  const id = Number(c.req.param("id"));
  if (Number.isNaN(id)) {
    return c.json(
      { error: { code: "VALIDATION_ERROR", message: "Invalid domain id" } },
      400,
    );
  }

  const body = await c.req.json();
  const parsed = UpdateDomainSchema.safeParse(body);
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
  if (parsed.data.documentId !== undefined)
    fields.document_id = parsed.data.documentId;

  const row = await updateRow("domains", id, fields, {
    edited_at: "NOW()",
    edited_by: user.email,
  });

  if (!row) {
    return c.json(
      { error: { code: "NOT_FOUND", message: "Domain not found" } },
      404,
    );
  }

  return c.json(mapDomain(row as unknown as Record<string, unknown>));
});

// ---- DELETE /api/domains/:id ----

domains.delete("/:id", requireAuth, requireEditPermission, async (c) => {
  const id = Number(c.req.param("id"));
  if (Number.isNaN(id)) {
    return c.json(
      { error: { code: "VALIDATION_ERROR", message: "Invalid domain id" } },
      400,
    );
  }

  // Check domain exists
  const existing = await queryOne("SELECT id FROM domains WHERE id = $1", [id]);
  if (!existing) {
    return c.json(
      { error: { code: "NOT_FOUND", message: "Domain not found" } },
      404,
    );
  }

  // Cascade delete: indicators → sub_strands → strands → domain
  await query(`DELETE FROM indicators WHERE domain_id = $1`, [id]);
  await query(
    `DELETE FROM sub_strands WHERE strand_id IN (SELECT id FROM strands WHERE domain_id = $1)`,
    [id],
  );
  await query(`DELETE FROM strands WHERE domain_id = $1`, [id]);
  await deleteRow("domains", id);

  return c.json({ success: true });
});

// ---- PATCH /api/domains/:id/verify ----

domains.patch("/:id/verify", requireAuth, requireEditPermission, async (c) => {
  const id = Number(c.req.param("id"));
  if (Number.isNaN(id)) {
    return c.json(
      { error: { code: "VALIDATION_ERROR", message: "Invalid domain id" } },
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
      `UPDATE domains SET human_verified = true, verified_at = NOW(), verified_by = $2 WHERE id = $1 RETURNING *`,
      [id, user.email],
    );
  } else {
    row = await queryOne(
      `UPDATE domains SET human_verified = false, verified_at = NULL, verified_by = NULL WHERE id = $1 RETURNING *`,
      [id],
    );
  }

  if (!row) {
    return c.json(
      { error: { code: "NOT_FOUND", message: "Domain not found" } },
      404,
    );
  }

  const domain = mapDomain(row as unknown as Record<string, unknown>);
  return c.json({
    success: true,
    verifiedAt: domain.verifiedAt?.toISOString() ?? null,
    verifiedBy: domain.verifiedBy ?? null,
  });
});

export default domains;
