# Why I Built a Human Verification Layer on Top of My AI Pipeline

_AI can extract early learning standards at scale. But production data quality requires human oversight — and the engineering to make that oversight fast enough to actually happen._

---

There's a tempting narrative in AI engineering that goes something like: the model extracts the data, we validate the output, we ship it. Done.

In practice, that story falls apart the moment your output is consumed by people who need to trust it. An extracted learning indicator with a slightly wrong hierarchy assignment — a strand misclassified as a sub-strand, an illustrative example erroneously extracted as a separate indicator — isn't just a data quality issue. It's a trust issue. If a curriculum specialist finds one error in the data, they question all of it.

The ELS Pipeline I built processes early learning standards documents from multiple states through an AI-powered extraction and normalization flow. In my previous articles, I covered the problem space and how the detection and parsing stages work. This article covers what happens after the AI does its job: the human verification layer that turns AI output into production-quality data.

---

## The Quality Model

Every record the AI extracts — every domain, strand, sub-strand, and indicator — enters the database with a `humanVerified` flag set to `false`. Nothing is rejected. Nothing is auto-approved. The data is immediately available for browsing and plan generation, but it's explicitly marked as unverified until a human specialist reviews it.

This is a deliberate quality model — not "AI is correct until proven wrong," but "AI provides a first draft that accelerates human review."

The approach aligns with what Mosqueira-Rey et al. call "machine teaching" — a human-in-the-loop paradigm where domain experts retain control of the learning process and the system is designed around their judgment, not the model's autonomy ([Mosqueira-Rey et al., 2023, "Human-in-the-loop machine learning: a state of the art," _Artificial Intelligence Review_](https://link.springer.com/article/10.1007/s10462-022-10246-w)). Monarch's practical framework for HITL-ML similarly emphasizes that the design of the annotation interface — how fast and intuitive it is for the human reviewer — is often more important to system quality than the model's raw accuracy ([Monarch, 2021, _Human-in-the-Loop Machine Learning_, Manning](https://www.manning.com/books/human-in-the-loop-machine-learning)).

---

## What the Verification Interface Actually Looks Like

The ELS Explorer is a React application built with a `HierarchyTable` component that presents the extracted standards as an expandable, sortable, filterable table. A curriculum specialist opens the home page and sees every loaded document. Expanding a document reveals its domains; expanding a domain reveals its strands; expanding a strand reveals its sub-strands and indicators. The hierarchy supports flexible nesting — indicators can attach directly to a domain, a strand, or a sub-strand, depending on how the source document is structured.

Each row in the table shows:

- The element's code (in a monospace badge) and name, linked to a detail page
- Its verification status — a clickable `VerifiedBadge` component that renders a green shield icon with "Verified" or a muted "Unverified" label
- Action buttons (Edit and Delete), visible only to users with edit permission

The filter bar at the top lets specialists narrow the view by country, state, verification status (all / verified / unverified), and a free-text search that matches against codes, names, titles, and descriptions. Sorting works on code, name, or verification status, and the entire UI state — expanded nodes, scroll position, sort order, filters — is persisted to `sessionStorage` so that navigating to a detail page and pressing back restores exactly where you were.

For each element, a specialist can:

1. **Verify it** — click the badge to toggle `humanVerified`. This fires a `PATCH` request to `/api/{entity-type}/:id/verify` with `{ humanVerified: true }`. The API sets `human_verified = true`, `verified_at = NOW()`, and `verified_by` to the user's display name. Unverifying clears all three fields. The frontend applies the change optimistically and reverts on failure.

2. **Edit it** — click the pencil icon to open an `EditModal` dialog. The modal presents form fields appropriate to the record type: code and name for domains/strands/sub-strands; code, title, description, age band, source page, and source text for indicators. Every record type also gets a parent selector dropdown, so a specialist can re-parent a strand to a different domain or an indicator to a different sub-strand. A "Human Verified" checkbox defaults to checked on open, so saving an edit implicitly verifies the record — the common workflow of "correct and confirm" in a single action.

3. **Delete it** — click the trash icon, which triggers a `window.confirm` dialog and then a `DELETE` request. The frontend optimistically removes the node from the hierarchy tree. On failure, it re-fetches the full document hierarchy to restore state.

The PDF viewer is a separate page. Each document has a `/documents/:id/view` route that renders a `PDFViewer` component. The component fetches a time-limited pre-signed S3 URL via `GET /api/documents/:id/pdf-url`, renders the PDF in an iframe with page navigation controls, and monitors the URL's expiration — showing a "Refresh link" button when the signed URL expires. If the document doesn't have an S3-hosted PDF, the viewer falls back to linking to the original `sourceUrl`. A specialist reviewing an indicator can open the PDF viewer in a separate tab and navigate to the `sourcePage` recorded on the indicator to cross-reference the extraction.

---

## The Audit Trail: Two Separate Concepts

The shared TypeScript types define the same audit fields on every entity in the hierarchy — `Domain`, `Strand`, `SubStrand`, and `Indicator` all carry identical tracking fields:

**Verification** answers the question: "Has a human confirmed that this AI-extracted record is correct?"

- `humanVerified` (boolean) — the flag
- `verifiedAt` (Date | null) — when the verification happened
- `verifiedBy` (string | null) — the display name of the specialist who verified it

**Editing** answers a different question: "Has a human changed the content of this record?"

- `editedAt` (Date | null) — when the edit happened
- `editedBy` (string | null) — who made the edit

These are intentionally separate because they represent different quality assurance events. A specialist might verify an indicator without editing it (the AI got it right). They might edit an indicator's description and then verify it (corrected and confirmed). They might edit an indicator's parent assignment without verifying the overall record (fixed one field, still reviewing others).

The `editedAt` and `editedBy` fields are set automatically by the `updateRow` helper whenever a `PUT` request modifies a record. The route handler passes `{ edited_at: "NOW()", edited_by: user.displayName }` as extra SET clauses, and the database client inlines `NOW()` as a SQL expression rather than binding it as a parameter. The specialist never manually sets these fields — they're a side effect of any content change.

The separation lets you measure pipeline quality precisely. If 90% of indicators are verified without edits, the AI detection is performing well. If 40% require description edits before verification, the description extraction needs improvement. These metrics guide prompt iteration — they tell you exactly which failure modes to address in the next version of the detection prompt.

---

## Soft Deletes and Cascade Logic

When a specialist deletes an element — say, a domain that was erroneously extracted from a page header — they're removing a node from a tree. That node has children: strands, sub-strands, and indicators beneath it.

Hard deletes would lose the audit trail and make it impossible to review what the AI originally extracted. The system uses soft deletes: every record carries `deleted`, `deletedAt`, and `deletedBy` fields. A "deleted" record is excluded from all normal queries (every `SELECT` includes `AND deleted = false`) but remains in the database for auditing and analytics.

The database client provides two helpers that implement this:

```typescript
// Soft-delete a single row by primary key
export async function softDeleteRow(
  table: string,
  id: number,
  deletedBy: string,
): Promise<boolean> {
  const result = await query(
    `UPDATE ${table} SET deleted = true, deleted_at = NOW(), deleted_by = $2
     WHERE id = $1 AND deleted = false`,
    [id, deletedBy],
  );
  return (result.rowCount ?? 0) > 0;
}

// Soft-delete multiple rows matching a WHERE clause
export async function softDeleteWhere(
  table: string,
  whereClause: string,
  params: unknown[],
  deletedBy: string,
): Promise<number> {
  const paramIdx = params.length + 1;
  const result = await query(
    `UPDATE ${table} SET deleted = true, deleted_at = NOW(), deleted_by = $${paramIdx}
     WHERE ${whereClause} AND deleted = false`,
    [...params, deletedBy],
  );
  return result.rowCount ?? 0;
}
```

Cascade deletion follows the hierarchy. Here's the actual domain delete handler:

```typescript
// Cascade soft-delete: indicators → sub_strands → strands → domain
await softDeleteWhere("indicators", "domain_id = $1", [id], deletedBy);
await query(
  `UPDATE sub_strands SET deleted = true, deleted_at = NOW(), deleted_by = $2
   WHERE strand_id IN (SELECT id FROM strands WHERE domain_id = $1)
   AND deleted = false`,
  [id, deletedBy],
);
await softDeleteWhere("strands", "domain_id = $1", [id], deletedBy);
await softDeleteRow("domains", id, deletedBy);
```

Children are soft-deleted before parents. The sub-strand cascade requires a subquery because sub-strands don't have a direct `domain_id` foreign key — they belong to strands, which belong to domains. The same pattern scales down the hierarchy: deleting a strand cascades to its sub-strands and indicators via `softDeleteWhere`; deleting a sub-strand cascades to its indicators; deleting an indicator is the simple case with no cascade.

---

## Property-Based Testing: Proving Correctness at Scale

Cascade deletion is the kind of logic that unit tests cover poorly. A unit test that deletes a domain with two strands, each containing three indicators, verifies one specific topology. But the real question is: does cascade deletion work for _any_ hierarchy shape?

The ELS Explorer API uses property-based testing with fast-check to answer that question. Property-based testing originates from Claessen and Hughes' QuickCheck, which introduced the idea of defining properties desired of functions and automatically generating random tests to verify or falsify them ([Claessen & Hughes, 2000, "QuickCheck: A Lightweight Tool for Random Testing of Haskell Programs," _ICFP_](https://dl.acm.org/doi/10.1145/351240.351266)). The approach has since been ported to over 40 languages — fast-check is the JavaScript/TypeScript implementation. Instead of writing individual test cases, you define invariants — properties that must hold for all possible inputs — and let the framework generate thousands of random test cases.

The test suite defines five property-based test files covering the verification layer:

**Property 1 — Hierarchy Response Structure Completeness.** Given a randomly generated hierarchy — 0 to 3 domains, 0 to 2 strands per domain, 0 to 2 sub-strands per strand, 0 to 2 indicators per sub-strand — the `/api/documents/:id/hierarchy` endpoint must return a nested structure that exactly matches the input data. Every `humanVerified` flag must be present as a boolean on every domain, strand, sub-strand, and indicator. No records may be lost or duplicated. The test generates the full hierarchy as mock database rows with consistent foreign keys and unique IDs, then asserts structural completeness at every nesting level.

**Property 5 — Edit Audit Trail Integrity.** For any entity type and any randomly generated email address, a successful `PUT` request must result in `editedAt` and `editedBy` being set on the returned record. The test generates random positive integer IDs and random email addresses, invokes the update handler, and verifies that the `updateRow` mock received the correct `edited_at: "NOW()"` and `edited_by` parameters.

**Property 6 — Cascade Delete Completeness.** For any entity type and any randomly generated ID, a `DELETE` request must trigger the correct number of cascade queries with the correct SQL patterns:

- Deleting a **domain** → 3 cascade queries (indicators, sub_strands, strands) + 1 soft-delete of the domain
- Deleting a **strand** → 2 cascade queries (indicators, sub_strands) + 1 soft-delete
- Deleting a **sub-strand** → 1 cascade query (indicators) + 1 soft-delete
- Deleting an **indicator** → 0 cascade queries + 1 soft-delete

The test verifies both the count and the ordering of cascade queries — indicators are always deleted before sub-strands, sub-strands before strands.

**Property 7 — Verification State Round-Trip.** For any entity type, verifying a record must set `human_verified = true`, `verified_at` to a timestamp, and `verified_by` to the user's identifier. Unverifying that same record must clear all three fields. This must hold identically for all four entity types. The test generates random IDs and random email addresses, performs the verify → unverify cycle, and asserts the correct SQL was issued in each direction.

These tests each run with 100 iterations. Over the course of the suite, they exercise thousands of distinct hierarchy topologies, edge cases, and state transitions that would be prohibitively tedious to write by hand.

---

## Authorization: Who Can Edit What

Not every authenticated user can modify records. The ELS Explorer implements a two-tier permission model using Descope for identity management.

**Read access** — any visitor can browse documents, view hierarchies, and inspect individual records. The hierarchy endpoint and document list require no authentication at all.

**Edit access** — only users with the `canEdit` custom attribute in their Descope token can modify, verify, or delete records.

The backend implements this as two stacked Hono middlewares:

```typescript
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

    c.set("authUser", user);
    await next();
  },
);

export const requireEditPermission = createMiddleware<AuthEnv>(
  async (c: Context, next: Next) => {
    const user = c.get("authUser") as AuthUser | undefined;
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
```

Read endpoints have no auth middleware. Write endpoints stack both: `requireAuth` validates the Descope session and extracts the user, then `requireEditPermission` checks the `canEdit` flag. A valid session without edit permission gets a 403, not a 401 — the system distinguishes "who are you?" from "are you allowed to do this?"

On the frontend, the `AuthContext` mirrors this separation. The `useAuth` hook exposes `hasEditPermission`, which the `HomePage` uses to conditionally pass `onEdit`, `onDelete`, and `onVerify` callbacks to the `HierarchyTable`. When `hasEditPermission` is false, those props are `undefined`, and the action buttons and clickable verification badges simply don't render. The permission check happens at both layers — the UI hides the controls, and the API enforces the boundary.

The `canEdit` flag is extracted from the Descope token's `customAttributes` object. The `extractCanEdit` helper checks both `token.customAttributes.canEdit` and `token.canEdit` directly, since Descope can surface custom attributes at either location depending on configuration. The `verifiedBy` and `editedBy` fields record the user's `displayName` (extracted from the token, falling back to `sub`), not their internal user ID — so the audit trail shows human-readable names.

---

## The Serverless Database Layer

The API runs on AWS Lambda. Lambda functions are stateless and ephemeral — they don't maintain persistent database connections. Traditional PostgreSQL connection pooling doesn't work well in this model because Lambda instances spin up and down unpredictably.

The solution is AWS RDS Data API — a REST-based interface to Aurora PostgreSQL that handles connection management server-side. The API sends SQL statements over HTTPS; RDS manages the actual database connections.

The trade-off is ergonomics. The RDS Data API uses named parameter syntax (`:p1`, `:p2`) rather than PostgreSQL's positional syntax (`$1`, `$2`). Every query in the codebase would need to use the non-standard syntax, making the SQL harder to read and impossible to test against a local PostgreSQL instance.

The database client wraps this with an `executeStatement` function that converts transparently:

```typescript
async function executeStatement(
  sql: string,
  params: unknown[] = [],
): Promise<Record<string, unknown>[]> {
  // Replace $1, $2, ... with :p1, :p2, ...
  const convertedSql = sql.replace(/\$(\d+)/g, ":p$1");

  const parameters = params.map((v, i) => ({
    name: `p${i + 1}`,
    value: toField(v),
  }));

  const resp = await getRdsClient().send(
    new ExecuteStatementCommand({
      resourceArn: clusterArn,
      secretArn,
      database,
      sql: convertedSql,
      parameters,
      includeResultMetadata: true,
    }),
  );

  // Convert column metadata + records into plain objects
  const columns = (resp.columnMetadata ?? []).map((c) => c.name ?? "");
  return (resp.records ?? []).map((record) => {
    const row: Record<string, unknown> = {};
    record.forEach((field, i) => {
      row[columns[i]] = fromField(field);
    });
    return row;
  });
}
```

The `toField` and `fromField` helpers handle type conversion between JavaScript values and the RDS Data API's `Field` union type — booleans, integers, doubles, strings, and nulls each map to a specific field variant.

The public `query`, `queryOne`, and `queryMany` helpers implement a dual-mode pattern: when `DB_CLUSTER_ARN` is set (production), they route through `executeStatement` and the RDS Data API. When it's not set (local development), they fall back to a direct `pg.Pool` connection:

```typescript
export async function query<T>(text: string, params?: unknown[]) {
  if (process.env.DB_CLUSTER_ARN) {
    const rows = await executeStatement(text, params);
    return { rows: rows as T[], rowCount: rows.length };
  }
  const pool = await getPool();
  const result = await pool.query<T>(text, params);
  return { rows: result.rows, rowCount: result.rowCount ?? 0 };
}
```

The same SQL runs in both modes. The same test suite validates both code paths. Route handlers never know or care which database backend they're talking to.

The `updateRow` helper adds one more layer of abstraction: it distinguishes between regular parameter values (bound as `$N`) and SQL expressions (inlined directly). Any string value ending with `()` — like `"NOW()"` — is treated as a SQL function call and written into the SET clause verbatim rather than parameterized. This is how `edited_at = NOW()` works without the route handler needing to know anything about the database client's internals.

---

## What This Engineering Buys You

The human verification layer is, on one level, a straightforward CRUD application. But the design choices — separate audit concepts, soft cascade deletes, property-based correctness proofs, dual-mode database access, tiered authorization — exist because this system's output is consumed by practitioners making decisions about children's learning.

A domain that was incorrectly extracted and never cleaned up doesn't just sit in a database. It appears in a parent's learning plan. It gets cited in a curriculum alignment report. It informs a state education agency's assessment of program quality.

The verification layer is how you get from "AI-extracted data" to "data that professionals can cite." And building it well — proving its correctness, auditing every change, making human review fast enough to actually happen — is the engineering work that makes the AI pipeline useful in production, not just in a demo.

---

_EdTech Co. is a mission-driven engineering initiative focused on building open infrastructure for early childhood education. This is the fourth article in a series on the technical architecture behind the ELS Platform._
