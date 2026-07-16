# API Reference

## Standards Explorer API

**Package:** `@els/api` (`packages/els-explorer-api/`)
**Framework:** Hono
**Runtime:** Lambda behind API Gateway
**Auth:** Descope JWT

Base URL: `https://{cloudfront-domain}/api` or `https://{api-gateway-url}/api`

### Authorization model

Reads are **public**. Every write (create, update, delete, verify, reorder) passes through two middlewares in `src/middleware/auth.ts`:

1. `requireAuth` — validates the Descope JWT from `Authorization: Bearer <token>`. Missing or invalid → `401 UNAUTHORIZED`.
2. `requireEditPermission` — checks the `canEdit` claim on the validated token. Authenticated but without it → `403 FORBIDDEN`.

### Health Check

```
GET /api/health
```

Returns `{ "status": "ok" }`.

### Documents

```
GET /api/documents
GET /api/documents/:id/hierarchy
GET /api/documents/:id/pdf-url
```

- `GET /api/documents` — List documents. Filterable:

  | Query Param | Description                         |
  | ----------- | ----------------------------------- |
  | `country`   | Filter by country code (e.g., `US`) |
  | `state`     | Filter by state code (e.g., `CA`)   |

- `GET /api/documents/:id/hierarchy` — Full nested hierarchy for one document (domains → strands → sub-strands → indicators). Returns `HierarchyResponse`.
- `GET /api/documents/:id/pdf-url` — Presigned S3 URL for the document's source PDF, so the frontend can show the original page alongside the parsed element.

There are no create/update/delete routes for documents — they are written by the pipeline's persistence stage, not the API.

### Filters

```
GET /api/filters
```

Returns available filter values (distinct countries, states) for the document list.

### Domains

```
POST   /api/domains            (auth + canEdit)
PUT    /api/domains/reorder    (auth + canEdit)
GET    /api/domains/:id
PUT    /api/domains/:id        (auth + canEdit)
DELETE /api/domains/:id        (auth + canEdit)
PATCH  /api/domains/:id/verify (auth + canEdit)
```

- `POST` — Create a domain (`CreateDomainRequest`: documentId, code, name, description)
- `PUT /reorder` — Persist a user-defined domain ordering (`ReorderDomainsRequest`). Backed by the nullable `order` column added in migration 010; when unset, domains fall back to `ORDER BY code`. Declared before `/:id` so `reorder` is not swallowed as an ID.
- `GET` — Get a domain by ID
- `PUT` — Update domain fields (code, name, description, documentId)
- `DELETE` — Soft-delete a domain (sets `deleted`/`deleted_at`/`deleted_by`; the row is retained)
- `PATCH /verify` — Set human verification status (`VerifyRequest`)

### Strands

```
POST   /api/strands            (auth + canEdit)
GET    /api/strands/:id
PUT    /api/strands/:id        (auth + canEdit)
DELETE /api/strands/:id        (auth + canEdit)
PATCH  /api/strands/:id/verify (auth + canEdit)
```

Same pattern as domains. Create/update fields: code, name, description, domainId.

### Sub-Strands

```
POST   /api/sub-strands            (auth + canEdit)
GET    /api/sub-strands/:id
PUT    /api/sub-strands/:id        (auth + canEdit)
DELETE /api/sub-strands/:id        (auth + canEdit)
PATCH  /api/sub-strands/:id/verify (auth + canEdit)
```

Same pattern. Create/update fields: code, name, description, strandId.

### Indicators

```
POST   /api/indicators            (auth + canEdit)
GET    /api/indicators/:id
PUT    /api/indicators/:id        (auth + canEdit)
DELETE /api/indicators/:id        (auth + canEdit)
PATCH  /api/indicators/:id/verify (auth + canEdit)
```

Create/update fields: code, title, description, ageBand, sourcePage, sourceText, subStrandId.

### Request/Response Types

All types are defined in `packages/shared/src/types.ts` (the TS mirror of the Pydantic models in `src/els_pipeline/models.py` — keep the two in sync). Key types:

```typescript
// Document with full hierarchy — GET /api/documents/:id/hierarchy
interface HierarchyResponse {
  document: Document;
  domains: DomainWithChildren[];
}

// Create requests — CreateDomainRequest, CreateStrandRequest,
// CreateSubStrandRequest, CreateIndicatorRequest.
// Note: an indicator anchors to a domain, with strand/sub-strand optional —
// 3-level documents (e.g. CO) have no sub_strand layer at all.
interface CreateIndicatorRequest {
  domainId: number;
  strandId?: number | null;
  subStrandId?: number | null;
  code: string;
  title?: string | null;
  description: string;
  ageBand?: string | null;
  sourcePage?: number | null;
  sourceText?: string | null;
}

// Update requests (all fields optional) — UpdateDomainRequest,
// UpdateStrandRequest, UpdateSubStrandRequest, UpdateIndicatorRequest
interface UpdateIndicatorRequest {
  code?: string;
  title?: string | null;
  description?: string;
  ageBand?: string | null;
  sourcePage?: number | null;
  sourceText?: string | null;
  subStrandId?: number | null;
}

// Domain ordering — PUT /api/domains/reorder
interface ReorderDomainsRequest {
  domainIds: number[];
}

// Verification toggle — PATCH /:id/verify
interface VerifyRequest {
  humanVerified: boolean;
}

// Error response
interface ApiError {
  error: {
    code: string;
    message: string;
    details?: Record<string, unknown>;
  };
}
```

---

## Planning API

**Package:** `@els/planning-api` (`packages/planning-api/`)
**Framework:** Hono
**Runtime:** Lambda behind API Gateway
**Auth:** Descope JWT

Base URL: `https://{cloudfront-domain}/api` or `https://{api-gateway-url}/api`

### Health Check

```
GET /api/health
```

Returns `{ "status": "ok" }`.

All endpoints require a valid Descope JWT in the `Authorization: Bearer <token>` header. Plans are scoped to the authenticated user.

### Plans

```
GET    /api/plans
GET    /api/plans/:id
DELETE /api/plans/:id
```

Read and delete learning plans for the authenticated user.

There is deliberately **no `POST` or `PUT` here**. Plans are created and updated by the *agent*, through its `createPlan` / `updatePlan` tools, during a chat session — not by the frontend posting a plan body. The REST surface is read/delete only.

### Chat (WebSocket handshake)

```
POST /api/chat/session
```

The API does **not** proxy the chat stream. It mints a short-lived presigned URL and the browser connects to Bedrock AgentCore directly:

1. Validates the Descope JWT (`requireAuth`).
2. Calls `generatePresignedUrl` (`src/lib/presign.ts`) to SigV4-sign a `wss://` URL for the AgentCore Runtime (`AGENTCORE_RUNTIME_ARN`), valid for **300 seconds**.
3. Embeds the user's raw Descope JWT — and the optional `planId` — as `X-Amzn-Bedrock-AgentCore-Runtime-Custom-*` **query params**, not headers. (AgentCore's `Authorization` header allowlist would require a custom JWT authorizer; the token is still Descope-signed and is re-validated by the agent, so it cannot be forged.)
4. Returns the URL to the browser, which opens the WebSocket itself.

Request body (all optional): `{ "sessionId"?: string, "planId"?: string }`. A `sessionId` is generated if omitted.

Response:

```json
{
  "url": "wss://...",
  "sessionId": "...",
  "userId": "...",
  "expiresAt": 1710000000
}
```

Over that WebSocket, the agent streams JSON frames:

| Frame Type                                                 | Description         |
| ---------------------------------------------------------- | ------------------- |
| `{ "type": "text", "text": "..." }`                        | Streamed text chunk |
| `{ "type": "plan", "planId": "...", "action": "created" }` | Plan mutation event |
| `{ "type": "error", "message": "..." }`                    | Error message       |
| `{ "type": "done" }`                                       | End of response     |

### Agent Tools

The planning agent (`packages/agentcore-agent/`) has these tools available:

| Tool                              | Description                                       |
| --------------------------------- | ------------------------------------------------- |
| `getAvailableStates`              | List US states with standards data                |
| `getAgeRanges(state)`             | Get age ranges for a state                        |
| `getIndicators(state, age_range)` | Get learning indicators for a state and age range |
| `createPlan(...)`                 | Create a new learning plan                        |
| `updatePlan(plan_id, content)`    | Update an existing plan                           |
| `getPlan(plan_id)`                | Retrieve a plan                                   |
| `deletePlan(plan_id)`             | Delete a plan                                     |

The tools split into two groups in `app.py`:

- **Stateless** (`getAvailableStates`, `getAgeRanges`, `getIndicators`) are plain module-level `@tool` functions — they read public standards data and need no user context.
- **Session-scoped** (`createPlan`, `updatePlan`, `getPlan`, `deletePlan`) are built per-connection by `build_session_tools(user_id)`, which closes over the `user_id` extracted from the validated Descope token.

`user_id` is therefore **not a tool parameter** — the LLM cannot pass, guess, or override it, and cannot reach another user's plans. Preserve this closure pattern when adding plan tools.
