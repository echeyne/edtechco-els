import { Hono } from "hono";
import type { AuthEnv } from "../middleware/auth.js";
import { requireAuth } from "../middleware/auth.js";
import { getPlansByUserId, getPlanById, deletePlan } from "../db/plans.js";

const plans = new Hono<AuthEnv>();

// Apply auth middleware to all plan routes
plans.use("/*", requireAuth);

// GET /api/plans — list plans for the authenticated user
plans.get("/", async (c) => {
  const userId = c.get("userId");
  const userPlans = await getPlansByUserId(userId);
  return c.json(userPlans);
});

// GET /api/plans/:id — get a single plan (ownership-checked)
plans.get("/:id", async (c) => {
  const userId = c.get("userId");
  const id = c.req.param("id");
  const plan = await getPlanById(id, userId);

  if (!plan) {
    return c.json(
      { error: { code: "NOT_FOUND", message: "Plan not found" } },
      404,
    );
  }

  return c.json(plan);
});

// DELETE /api/plans/:id — delete a plan (ownership-checked)
plans.delete("/:id", async (c) => {
  const userId = c.get("userId");
  const id = c.req.param("id");
  const deleted = await deletePlan(id, userId);

  if (!deleted) {
    return c.json(
      { error: { code: "NOT_FOUND", message: "Plan not found" } },
      404,
    );
  }

  return c.body(null, 204);
});

export default plans;
