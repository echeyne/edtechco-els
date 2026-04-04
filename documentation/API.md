# API Reference

## Standards Explorer API

**Package:** `@els/api` (`packages/els-explorer-api/`)
**Framework:** Hono
**Runtime:** Lambda behind API Gateway
**Auth:** Descope JWT

Base URL: `https://{cloudfront-domain}/api` or `https://{api-gateway-url}/api`

### Health Check

```
GET /api/health
```

Returns `{ "status": "ok" }`.

### Documents

```
GET /api/documents
```

List all documents. Supports filtering:

| Query Param | Description                         |
| ----------- | ----------------------------------- |
| `country`   | Filter by country code (e.g., `US`) |
| `state`     | Filter by state code (e.g., `CA`)   |

```
GET /api/documents/:id
```

Get a single document by ID, including its full hierarchy (domains → strands → sub-strands → indicators).

### Filters

```
GET /api/filters
```

Returns available filter values (distinct countries, states) for the document list.

### Domains

```
GET    /api/domains/:id
PUT    /api/domains/:id
DELETE /api/domains/:id
POST   /api/domains/:id/verify
```

- `GET` — Get a domain by ID
- `PUT` — Update domain fields (code, name, description, documentId)
- `DELETE` — Soft-delete a domain
- `POST /verify` — Toggle human verification status

### Strands

```
GET    /api/strands/:id
PUT    /api/strands/:id
DELETE /api/strands/:id
POST   /api/strands/:id/verify
```

Same pattern as domains. Update fields: code, name, description, domainId.

### Sub-Strands

```
GET    /api/sub-strands/:id
PUT    /api/sub-strands/:id
DELETE /api/sub-strands/:id
POST   /api/sub-strands/:id/verify
```

Same pattern. Update fields: code, name, description, strandId.

### Indicators

```
GET    /api/indicators/:id
PUT    /api/indicators/:id
DELETE /api/indicators/:id
POST   /api/indicators/:id/verify
```

Update fields: code, title, description, ageBand, sourcePage, sourceText, subStrandId.

### Request/Response Types

All types are defined in `packages/shared/src/types.ts`. Key types:

```typescript
// Document with full hierarchy
interface HierarchyResponse {
  document: Document;
  domains: DomainWithChildren[];
}

// Update requests (all fields optional)
interface UpdateIndicatorRequest {
  code?: string;
  title?: string | null;
  description?: string;
  ageBand?: string | null;
  sourcePage?: number | null;
  sourceText?: string | null;
  subStrandId?: number | null;
}

// Verification toggle
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

### Plans

```
GET    /api/plans
GET    /api/plans/:id
POST   /api/plans
PUT    /api/plans/:id
DELETE /api/plans/:id
```

CRUD operations for learning plans. All endpoints require a valid Descope JWT in the `Authorization: Bearer <token>` header. Plans are scoped to the authenticated user.

### Chat (WebSocket)

```
POST /api/chat
```

Initiates a WebSocket connection to the Bedrock AgentCore Runtime. The API:

1. Validates the Descope JWT
2. Opens a SigV4-signed WebSocket to AgentCore
3. Forwards the user's token via custom AgentCore headers
4. Proxies messages between the frontend and the agent

The agent streams responses as JSON frames:

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

Plan-management tools have `user_id` bound from the authenticated session — the LLM never controls which user's data is accessed.
