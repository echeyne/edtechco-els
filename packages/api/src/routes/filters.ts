import { Hono } from "hono";
import { queryMany } from "../db/client.js";

const filters = new Hono();

// ---- GET /api/filters ----

filters.get("/", async (c) => {
  const [countryRows, stateRows] = await Promise.all([
    queryMany<{ country: string }>(
      "SELECT DISTINCT country FROM documents ORDER BY country",
    ),
    queryMany<{ state: string }>(
      "SELECT DISTINCT state FROM documents ORDER BY state",
    ),
  ]);

  return c.json({
    countries: countryRows.map((r) => r.country),
    states: stateRows.map((r) => r.state),
  });
});

export default filters;
