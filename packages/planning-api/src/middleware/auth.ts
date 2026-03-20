import { createMiddleware } from "hono/factory";
import type { Context, Next } from "hono";
import DescopeClient from "@descope/node-sdk";
import type { AuthenticationInfo } from "@descope/node-sdk";

// ---- Types exposed to route handlers ----

export interface AuthUser {
  userId: string;
}

/**
 * Hono variables set by the auth middleware.
 * Access via `c.get("userId")` in route handlers.
 */
export interface AuthEnv {
  Variables: {
    userId: string;
  };
}

// ---- Descope client (lazy singleton) ----

let _client: ReturnType<typeof DescopeClient> | null = null;

function getDescopeClient(): ReturnType<typeof DescopeClient> {
  if (!_client) {
    const projectId = process.env.DESCOPE_PROJECT_ID;
    if (!projectId) {
      throw new Error("DESCOPE_PROJECT_ID environment variable is required");
    }
    _client = DescopeClient({ projectId });
  }
  return _client;
}

/** Allow tests to inject a mock client */
export function setDescopeClient(
  client: ReturnType<typeof DescopeClient> | null,
): void {
  _client = client;
}

// ---- Helpers ----

function extractBearerToken(c: Context): string | null {
  const header = c.req.header("Authorization");
  if (!header) return null;
  const parts = header.split(" ");
  if (parts.length !== 2 || parts[0] !== "Bearer") return null;
  return parts[1];
}

// ---- Middleware ----

/**
 * Requires a valid Descope session token.
 * Returns 401 if missing/invalid.
 * Sets `userId` on the context for downstream handlers.
 */
export const requireAuth = createMiddleware<AuthEnv>(
  async (c: Context, next: Next) => {
    const sessionToken = extractBearerToken(c);
    if (!sessionToken) {
      return c.json(
        {
          error: {
            code: "UNAUTHORIZED",
            message: "Missing authentication token",
          },
        },
        401,
      );
    }

    let authInfo: AuthenticationInfo;
    try {
      authInfo = await getDescopeClient().validateSession(sessionToken);
    } catch {
      return c.json(
        {
          error: {
            code: "UNAUTHORIZED",
            message: "Invalid or expired authentication token",
          },
        },
        401,
      );
    }

    c.set("userId" as never, authInfo.token.sub ?? "unknown");
    await next();
  },
);
