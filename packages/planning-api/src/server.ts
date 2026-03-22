import { serve } from "@hono/node-server";
import app from "./index.js";

const port = Number(process.env.PORT ?? 3001);

console.log(`Planning API listening on http://localhost:${port}`);
serve({ fetch: app.fetch, port });
