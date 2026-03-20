import {
  RDSDataClient,
  ExecuteStatementCommand,
  type Field,
} from "@aws-sdk/client-rds-data";
import pg from "pg";

const { Pool } = pg;

// ---- RDS Data API client (lazy singleton) ----

let _rdsClient: RDSDataClient | null = null;

function getRdsClient(): RDSDataClient {
  if (!_rdsClient) _rdsClient = new RDSDataClient({});
  return _rdsClient;
}

/** Allow tests to inject a mock RDS Data client */
export function setRdsClient(client: RDSDataClient | null): void {
  _rdsClient = client;
}

// ---- Helpers ----

/**
 * Convert a JS value to an RDS Data API Field.
 */
function toField(value: unknown): Field {
  if (value === null || value === undefined) return { isNull: true };
  if (typeof value === "boolean") return { booleanValue: value };
  if (typeof value === "number") {
    return Number.isInteger(value)
      ? { longValue: value }
      : { doubleValue: value };
  }
  return { stringValue: String(value) };
}

/**
 * Convert an RDS Data API Field back to a plain JS value.
 */
function fromField(field: Field): unknown {
  if (field.isNull) return null;
  if (field.booleanValue !== undefined) return field.booleanValue;
  if (field.longValue !== undefined) return field.longValue;
  if (field.doubleValue !== undefined) return field.doubleValue;
  if (field.stringValue !== undefined) return field.stringValue;
  if (field.blobValue !== undefined) return field.blobValue;
  return null;
}

/**
 * Execute a parameterised SQL statement via the RDS Data API.
 * Parameters use $1, $2, ... positional syntax (same as pg).
 * Internally they are converted to :p1, :p2, ... for the Data API.
 */
async function executeStatement(
  sql: string,
  params: unknown[] = [],
): Promise<Record<string, unknown>[]> {
  const clusterArn = process.env.DB_CLUSTER_ARN;
  const secretArn = process.env.DB_SECRET_ARN;
  const database = process.env.DB_NAME ?? "els_pipeline";

  if (!clusterArn || !secretArn) {
    throw new Error("DB_CLUSTER_ARN and DB_SECRET_ARN must be set");
  }

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

  const columns = (resp.columnMetadata ?? []).map((c) => c.name ?? "");
  const rows = (resp.records ?? []).map((record) => {
    const row: Record<string, unknown> = {};
    record.forEach((field, i) => {
      row[columns[i]] = fromField(field);
    });
    return row;
  });

  return rows;
}

// ---- Local pg pool (dev only) ----

let _pool: pg.Pool | null = null;

async function getPool(): Promise<pg.Pool> {
  if (_pool) return _pool;
  _pool = new Pool({
    host: process.env.DB_HOST ?? "localhost",
    port: Number(process.env.DB_PORT ?? 5432),
    database: process.env.DB_NAME ?? "els_corpus",
    user: process.env.DB_USER ?? "postgres",
    password: process.env.DB_PASSWORD ?? "",
    max: 20,
    idleTimeoutMillis: 30_000,
    connectionTimeoutMillis: 5_000,
  });
  return _pool;
}

/** Expose pool getter for tests or advanced usage */
export { getPool };

// ---- Public query helpers ----
// These keep the same interface as before so routes don't need to change.
// In production (DB_CLUSTER_ARN set) they use the RDS Data API.
// In local dev they fall back to a direct pg connection.

export async function query<
  T extends Record<string, unknown> = Record<string, unknown>,
>(text: string, params?: unknown[]): Promise<{ rows: T[]; rowCount: number }> {
  if (process.env.DB_CLUSTER_ARN) {
    const rows = await executeStatement(text, params);
    return { rows: rows as T[], rowCount: rows.length };
  }
  const pool = await getPool();
  const result = await pool.query<T>(text, params as never[]);
  return { rows: result.rows, rowCount: result.rowCount ?? 0 };
}

export async function queryOne<
  T extends Record<string, unknown> = Record<string, unknown>,
>(text: string, params?: unknown[]): Promise<T | null> {
  const result = await query<T>(text, params);
  return result.rows[0] ?? null;
}

export async function queryMany<
  T extends Record<string, unknown> = Record<string, unknown>,
>(text: string, params?: unknown[]): Promise<T[]> {
  const result = await query<T>(text, params);
  return result.rows;
}

/**
 * Returns true if the value should be inlined as a SQL expression rather than
 * bound as a parameter. Strings ending with "()" are treated as SQL calls
 * (e.g. "NOW()"), and the literal string "NULL" is treated as SQL NULL.
 */
function isSqlExpression(v: unknown): v is string {
  return typeof v === "string" && (v === "NULL" || /\(\)$/.test(v));
}

export async function updateRow<
  T extends Record<string, unknown> = Record<string, unknown>,
>(
  table: string,
  id: number,
  fields: Record<string, unknown>,
  extraSets?: Record<string, unknown>,
): Promise<T | null> {
  const entries = Object.entries({ ...fields, ...extraSets }).filter(
    ([, v]) => v !== undefined,
  );
  if (entries.length === 0)
    return queryOne<T>(`SELECT * FROM ${table} WHERE id = $1`, [id]);

  // Separate SQL expressions (inlined) from regular values (parameterised)
  let paramIndex = 2; // $1 is reserved for id
  const setClauses: string[] = [];
  const values: unknown[] = [];

  for (const [col, v] of entries) {
    if (isSqlExpression(v)) {
      setClauses.push(`${col} = ${v}`);
    } else {
      setClauses.push(`${col} = $${paramIndex++}`);
      values.push(v);
    }
  }

  const sql = `UPDATE ${table} SET ${setClauses.join(", ")} WHERE id = $1 RETURNING *`;
  return queryOne<T>(sql, [id, ...values]);
}

export async function deleteRow(table: string, id: number): Promise<boolean> {
  const result = await query(`DELETE FROM ${table} WHERE id = $1`, [id]);
  return (result.rowCount ?? 0) > 0;
}

/**
 * Soft-delete a row by setting deleted = true, deleted_at = NOW(), deleted_by.
 */
export async function softDeleteRow(
  table: string,
  id: number,
  deletedBy: string,
): Promise<boolean> {
  const result = await query(
    `UPDATE ${table} SET deleted = true, deleted_at = NOW(), deleted_by = $2 WHERE id = $1 AND deleted = false`,
    [id, deletedBy],
  );
  return (result.rowCount ?? 0) > 0;
}

/**
 * Soft-delete multiple rows matching a WHERE clause.
 */
export async function softDeleteWhere(
  table: string,
  whereClause: string,
  params: unknown[],
  deletedBy: string,
): Promise<number> {
  const paramIdx = params.length + 1;
  const result = await query(
    `UPDATE ${table} SET deleted = true, deleted_at = NOW(), deleted_by = $${paramIdx} WHERE ${whereClause} AND deleted = false`,
    [...params, deletedBy],
  );
  return result.rowCount ?? 0;
}

export async function closePool(): Promise<void> {
  if (_pool) await _pool.end();
}
