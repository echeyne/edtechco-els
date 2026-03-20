import { streamHandle } from "hono/aws-lambda";
import app from "./index.js";

export const handler: (...args: any[]) => any = streamHandle(app);
