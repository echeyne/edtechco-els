import { Hono } from "hono";
import { cors } from "hono/cors";
import plans from "./routes/plans.js";
import chat from "./routes/chat.js";

const app = new Hono();

app.use("/*", cors());

app.get("/api/health", (c) => {
  return c.json({ status: "ok" });
});

app.route("/api/plans", plans);
app.route("/api/chat", chat);

export default app;
