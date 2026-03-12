import { Hono } from "hono";
import { cors } from "hono/cors";
import documents from "./routes/documents.js";
import filters from "./routes/filters.js";

const app = new Hono();

app.use("/*", cors());

app.get("/api/health", (c) => {
  return c.json({ status: "ok" });
});

app.route("/api/documents", documents);
app.route("/api/filters", filters);

export default app;
