import { query, queryOne, queryMany } from "./client.js";
import type { PlanContent, PlanDetail, PlanSummary } from "../types.js";

export interface CreatePlanInput {
  userId: string;
  childName: string;
  childAge: string;
  state: string;
  interests: string | null;
  concerns: string | null;
  duration: string;
  content: PlanContent;
}

/** Row shape returned from the plans table. */
interface PlanRow extends Record<string, unknown> {
  id: string;
  user_id: string;
  child_name: string;
  child_age: string;
  state: string;
  interests: string | null;
  concerns: string | null;
  duration: string;
  content: string; // JSONB comes back as a string from RDS Data API
  status: string;
  created_at: string;
  updated_at: string;
}

function toPlanDetail(row: PlanRow): PlanDetail {
  const content =
    typeof row.content === "string"
      ? (JSON.parse(row.content) as PlanContent)
      : (row.content as unknown as PlanContent);

  return {
    id: row.id,
    childName: row.child_name,
    childAge: row.child_age,
    state: row.state,
    interests: row.interests,
    concerns: row.concerns,
    duration: row.duration,
    content,
    status: row.status,
    createdAt: row.created_at,
    updatedAt: row.updated_at,
  };
}

function toPlanSummary(row: PlanRow): PlanSummary {
  return {
    id: row.id,
    childName: row.child_name,
    childAge: row.child_age,
    state: row.state,
    duration: row.duration,
    status: row.status,
    createdAt: row.created_at,
    updatedAt: row.updated_at,
  };
}

/**
 * Insert a new plan and return the created record.
 */
export async function createPlan(input: CreatePlanInput): Promise<PlanDetail> {
  const row = await queryOne<PlanRow>(
    `INSERT INTO plans (user_id, child_name, child_age, state, interests, concerns, duration, content)
     VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
     RETURNING *`,
    [
      input.userId,
      input.childName,
      input.childAge,
      input.state,
      input.interests,
      input.concerns,
      input.duration,
      JSON.stringify(input.content),
    ],
  );

  if (!row) {
    throw new Error("Failed to create plan");
  }

  return toPlanDetail(row);
}

/**
 * Fetch a single plan by ID, scoped to the owning user.
 * Returns null if the plan does not exist or does not belong to the user.
 */
export async function getPlanById(
  id: string,
  userId: string,
): Promise<PlanDetail | null> {
  const row = await queryOne<PlanRow>(
    `SELECT * FROM plans WHERE id = $1 AND user_id = $2`,
    [id, userId],
  );

  return row ? toPlanDetail(row) : null;
}

/**
 * Fetch all plans for a user, ordered by most recently created first.
 */
export async function getPlansByUserId(userId: string): Promise<PlanSummary[]> {
  const rows = await queryMany<PlanRow>(
    `SELECT * FROM plans WHERE user_id = $1 ORDER BY created_at DESC`,
    [userId],
  );

  return rows.map(toPlanSummary);
}

/**
 * Update a plan's content and updated_at timestamp.
 * Returns null if the plan does not exist or does not belong to the user.
 */
export async function updatePlan(
  id: string,
  userId: string,
  content: PlanContent,
): Promise<PlanDetail | null> {
  const row = await queryOne<PlanRow>(
    `UPDATE plans
     SET content = $1, updated_at = NOW()
     WHERE id = $2 AND user_id = $3
     RETURNING *`,
    [JSON.stringify(content), id, userId],
  );

  return row ? toPlanDetail(row) : null;
}

/**
 * Delete a plan by ID, scoped to the owning user.
 * Returns true if a row was deleted, false otherwise.
 */
export async function deletePlan(id: string, userId: string): Promise<boolean> {
  const result = await query(
    `DELETE FROM plans WHERE id = $1 AND user_id = $2`,
    [id, userId],
  );

  return result.rowCount > 0;
}
