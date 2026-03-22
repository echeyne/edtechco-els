import { Hono } from "hono";
import { defaultProvider } from "@aws-sdk/credential-provider-node";
import type { AwsCredentialIdentity, Provider } from "@smithy/types";
import type { AuthEnv } from "../middleware/auth.js";
import { requireAuth } from "../middleware/auth.js";
import { generatePresignedUrl } from "../lib/presign.js";

let _credentials: Provider<AwsCredentialIdentity> | null = null;

function getCredentials(): Provider<AwsCredentialIdentity> {
  if (!_credentials) {
    _credentials = defaultProvider();
  }
  return _credentials;
}

export function setCredentials(creds: Provider<AwsCredentialIdentity> | null) {
  _credentials = creds;
}

let _generatePresignedUrl = generatePresignedUrl;

export function setPresignedUrlGenerator(
  fn: typeof generatePresignedUrl | null,
) {
  _generatePresignedUrl = fn ?? generatePresignedUrl;
}

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

  // Custom context must use the Runtime-Custom-* query names and be allowlisted
  // on the runtime. See runtime-header-allowlist in the AgentCore dev guide.
  const queryParams: Record<string, string> = {
    "X-Amzn-Bedrock-AgentCore-Runtime-Custom-UserId": c.get("userId"),
  };

  if (planId) {
    queryParams["X-Amzn-Bedrock-AgentCore-Runtime-Custom-PlanId"] = planId;
  }

  try {
    const url = await _generatePresignedUrl({
      runtimeArn,
      sessionId,
      region,
      credentials: getCredentials(),
      queryParams,
      expires,
    });

    if (!url.startsWith("wss://")) {
      console.error("Invalid presigned URL (not wss):", url);
      throw new Error("Invalid protocol");
    }

    return c.json({
      url,
      sessionId,
      expiresAt: Math.floor(Date.now() / 1000) + expires,
    });
  } catch (err) {
    console.error("Presign error:", err);

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
});

export default chat;
