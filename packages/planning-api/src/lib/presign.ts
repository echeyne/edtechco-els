/**
 * Generate presigned WebSocket URLs for AgentCore Runtime.
 *
 * Mirrors the Python SDK's `AgentCoreRuntimeClient.generate_presigned_url()`
 * using SigV4 query-string signing so the frontend can open a WebSocket
 * to `wss://bedrock-agentcore.<region>.amazonaws.com/runtimes/<arn>/ws`.
 */

import { SignatureV4 } from "@smithy/signature-v4";
import { HttpRequest } from "@smithy/protocol-http";
import { Sha256 } from "@aws-crypto/sha256-js";
import type { AwsCredentialIdentity, Provider } from "@smithy/types";

/** Must match SigV4 signing name for the Bedrock AgentCore data plane (see @aws-sdk/client-bedrock-agentcore). */
const SERVICE = "bedrock-agentcore";
const MAX_EXPIRES = 300;

export interface PresignOptions {
  runtimeArn: string;
  sessionId: string;
  region: string;
  credentials: AwsCredentialIdentity | Provider<AwsCredentialIdentity>;
  queryParams?: Record<string, string>;
  expires?: number;
}

/** WebSocket endpoint host per https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-get-started-websocket.html */
function getDataPlaneHost(region: string): string {
  return `bedrock-agentcore.${region}.amazonaws.com`;
}

function parseRuntimeArn(arn: string) {
  const match = arn.match(
    /^arn:(aws[a-zA-Z-]*)?:bedrock-agentcore:([a-z0-9-]+):(\d{12}):runtime\/([A-Za-z0-9_-]+)$/,
  );

  if (!match) {
    throw new Error(`Invalid runtime ARN format: ${arn}`);
  }

  return {
    partition: match[1] ?? "aws",
    region: match[2],
    accountId: match[3],
    runtimeId: match[4],
  };
}
/**
 * Generate a presigned `wss://` URL for connecting to an AgentCore Runtime agent.
 *
 * The URL includes SigV4 authentication in query parameters, allowing
 * browser clients to connect without AWS credentials.
 */
export async function generatePresignedUrl(
  opts: PresignOptions,
): Promise<string> {
  const expires = opts.expires ?? MAX_EXPIRES;

  if (expires > MAX_EXPIRES) {
    throw new Error(`expires cannot exceed ${MAX_EXPIRES} seconds`);
  }

  parseRuntimeArn(opts.runtimeArn);

  const host = getDataPlaneHost(opts.region);

  // Use the raw (unencoded) ARN for the HttpRequest path.  The default
  // uriEscapePath=true in SignatureV4 will encode colons (%3A) while
  // leaving slashes as-is when computing the canonical path — exactly
  // matching botocore's SigV4QueryAuth behaviour.
  const rawPath = `/runtimes/${opts.runtimeArn}/ws`;

  // For the final URL we need the ARN percent-encoded so the server
  // can distinguish ARN-internal slashes from path separators.
  const encodedArn = encodeURIComponent(opts.runtimeArn);
  const wirePath = `/runtimes/${encodedArn}/ws`;

  const query: Record<string, string> = {
    "X-Amzn-Bedrock-AgentCore-Runtime-Session-Id": opts.sessionId,
    ...(opts.queryParams ?? {}),
  };

  const request = new HttpRequest({
    method: "GET",
    protocol: "https:",
    hostname: host,
    path: rawPath,
    query,
    headers: {
      host,
    },
  });

  const signer = new SignatureV4({
    service: SERVICE,
    region: opts.region,
    credentials: opts.credentials,
    sha256: Sha256,
  });

  const signed = await signer.presign(request, {
    expiresIn: expires,
  });

  const qs = Object.entries(signed.query ?? {})
    .map(
      ([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(String(v))}`,
    )
    .join("&");

  return `wss://${host}${wirePath}?${qs}`;
}
