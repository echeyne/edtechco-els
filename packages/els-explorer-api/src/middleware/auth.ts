import { createMiddleware } from "hono/factory";
import type { Context, Next } from "hono";
import DescopeClient from "@descope/node-sdk";
import type { AuthenticationInfo } from "@descope/node-sdk";

// ---- Types exposed to route handlers ----

export interface AuthUser {
  userId: string;
  displayName: string;
  canEdit: boolean;
}

/**
 * Hono variables set by the auth middlewares.
 * Access via `c.get("authUser")` in route handlers.
 */
export interface AuthEnv {
  Variables: {
    authUser: AuthUser;
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

function extractCanEdit(token: AuthenticationInfo["token"]): boolean {
  // Descope stores custom attributes under `customAttributes` or directly
  // on the token. We check both locations.
  const custom = token.customAttributes as Record<string, unknown> | undefined;
  if (custom && typeof custom.canEdit === "boolean") return custom.canEdit;
  if (typeof token.canEdit === "boolean") return token.canEdit as boolean;
  return false;
}

function extractName(token: AuthenticationInfo["token"]): string {
  if (typeof token.displayName === "string") return token.displayName;
  if (typeof token.sub === "string") return token.sub;
  return "unknown";
}

// ---- Middlewares ----

/**
 * Requires a valid Descope session token.
 * Returns 401 if missing/invalid.
 * Sets `authUser` on the context for downstream handlers.
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

    const user: AuthUser = {
      userId: authInfo.token.sub ?? "unknown",
      displayName: extractName(authInfo.token),
      canEdit: extractCanEdit(authInfo.token),
    };

    c.set("authUser" as never, user);
    await next();
  },
);

/**
 * Must be placed after `requireAuth`.
 * Returns 403 if the authenticated user lacks the `canEdit` permission.
 */
export const requireEditPermission = createMiddleware<AuthEnv>(
  async (c: Context, next: Next) => {
    const user = c.get("authUser" as never) as AuthUser | undefined;
    if (!user) {
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

    if (!user.canEdit) {
      return c.json(
        {
          error: {
            code: "FORBIDDEN",
            message: "You do not have edit permissions",
          },
        },
        403,
      );
    }

    await next();
  },
);
