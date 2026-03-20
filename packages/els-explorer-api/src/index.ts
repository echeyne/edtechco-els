import { Hono } from "hono";
import { cors } from "hono/cors";
import documents from "./routes/documents.js";
import filters from "./routes/filters.js";
import domains from "./routes/domains.js";
import strands from "./routes/strands.js";
import subStrands from "./routes/subStrands.js";
import indicators from "./routes/indicators.js";

const app = new Hono();

app.use("/*", cors());

app.get("/api/health", (c) => {
  return c.json({ status: "ok" });
});

app.route("/api/documents", documents);
app.route("/api/filters", filters);
app.route("/api/domains", domains);
app.route("/api/strands", strands);
app.route("/api/sub-strands", subStrands);
app.route("/api/indicators", indicators);

export default app;
