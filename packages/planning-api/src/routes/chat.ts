import { Hono } from "hono";
import { defaultProvider } from "@aws-sdk/credential-provider-node";
import type { AwsCredentialIdentity, Provider } from "@smithy/types";
import type { AuthEnv } from "../middleware/auth.js";
import { requireAuth } from "../middleware/auth.js";
import { generatePresignedUrl } from "../lib/presign.js";

// ---- Credentials provider (lazy singleton, injectable for tests) ----

let _credentials: Provider<AwsCredentialIdentity> | null = null;

function getCredentials(): Provider<AwsCredentialIdentity> {
  if (!_credentials) {
    _credentials = defaultProvider();
  }
  return _credentials;
}

/** Allow tests to inject mock credentials */
export function setCredentials(
  creds: Provider<AwsCredentialIdentity> | null,
): void {
  _credentials = creds;
}

// ---- Presigned URL generator (injectable for tests) ----

let _generatePresignedUrl = generatePresignedUrl;

/** Allow tests to inject a mock presigned URL generator */
export function setPresignedUrlGenerator(
  fn: typeof generatePresignedUrl | null,
): void {
  _generatePresignedUrl = fn ?? generatePresignedUrl;
}

// ---- Route ----

const chat = new Hono<AuthEnv>();

chat.use("/*", requireAuth);

chat.post("/session", async (c) => {
  const body = await c.req.json().catch(() => null);
  const sessionId = body?.sessionId ?? crypto.randomUUID();
  const planId = body?.planId;

  const runtimeArn = process.env.AGENTCORE_RUNTIME_ARN;
  const region = process.env.AWS_REGION ?? "us-east-1";

  if (!runtimeArn) {
    return c.json(
      {
        error: {
          code: "INTERNAL_ERROR",
          message: "Agent configuration is missing",
        },
      },
      500,
    );
  }

  const expires = 300;

  // Pass userId and optional planId as custom query params so the agent
  // can read them from the WebSocket connection context.
  const customHeaders: Record<string, string> = {
    "X-UserId": c.get("userId"),
  };
  if (planId) {
    customHeaders["X-PlanId"] = planId;
  }

  let url: string;
  try {
    url = await _generatePresignedUrl({
      runtimeArn,
      sessionId,
      region,
      credentials: getCredentials(),
      customHeaders,
      expires,
    });
  } catch {
    return c.json(
      {
        error: {
          code: "INTERNAL_ERROR",
          message: "Failed to generate session URL",
        },
      },
      500,
    );
  }

  return c.json({
    url,
    sessionId,
    expiresAt: Math.floor(Date.now() / 1000) + expires,
  });
});

export default chat;
