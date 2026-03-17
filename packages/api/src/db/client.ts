import pg from "pg";
import {
  SecretsManagerClient,
  GetSecretValueCommand,
} from "@aws-sdk/client-secrets-manager";

const { Pool } = pg;

// --- Secrets Manager integration ---

interface DbSecret {
  host: string;
  port: number;
  dbname: string;
  username: string;
  password: string;
}

let _secretCache: DbSecret | null = null;

async function getDbSecret(): Promise<DbSecret> {
  if (_secretCache) return _secretCache;

  const secretArn = process.env.DB_SECRET_ARN;
  if (!secretArn) {
    throw new Error("DB_SECRET_ARN is not set");
  }

  const client = new SecretsManagerClient({});
  const resp = await client.send(
    new GetSecretValueCommand({ SecretId: secretArn }),
  );

  if (!resp.SecretString) {
    throw new Error("Database secret has no SecretString");
  }

  _secretCache = JSON.parse(resp.SecretString) as DbSecret;
  return _secretCache;
}

// --- Pool initialisation ---

let _pool: pg.Pool | null = null;

async function getPool(): Promise<pg.Pool> {
  if (_pool) return _pool;

  if (process.env.DB_SECRET_ARN) {
    const secret = await getDbSecret();
    _pool = new Pool({
      host: secret.host,
      port: secret.port,
      database: secret.dbname ?? "els_pipeline",
      user: secret.username,
      password: secret.password,
      max: 5, // Lambda-friendly pool size
      idleTimeoutMillis: 30_000,
      connectionTimeoutMillis: 5_000,
    });
  } else {
    // Local development — use env vars directly
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
  }

  return _pool;
}

// --- Low-level helpers ---

export async function query<T extends pg.QueryResultRow = pg.QueryResultRow>(
  text: string,
  params?: unknown[],
): Promise<pg.QueryResult<T>> {
  const pool = await getPool();
  return pool.query<T>(text, params);
}

export async function queryOne<T extends pg.QueryResultRow = pg.QueryResultRow>(
  text: string,
  params?: unknown[],
): Promise<T | null> {
  const pool = await getPool();
  const result = await pool.query<T>(text, params);
  return result.rows[0] ?? null;
}

export async function queryMany<
  T extends pg.QueryResultRow = pg.QueryResultRow,
>(text: string, params?: unknown[]): Promise<T[]> {
  const pool = await getPool();
  const result = await pool.query<T>(text, params);
  return result.rows;
}

// --- CRUD helpers ---

/**
 * Build and execute a dynamic UPDATE statement.
 * Only columns present in `fields` are updated.
 * Returns the updated row or null if not found.
 */
export async function updateRow<
  T extends pg.QueryResultRow = pg.QueryResultRow,
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

  const setClauses = entries.map(([col], i) => `${col} = $${i + 2}`);
  const values = entries.map(([, v]) => v);

  const sql = `UPDATE ${table} SET ${setClauses.join(", ")} WHERE id = $1 RETURNING *`;
  return queryOne<T>(sql, [id, ...values]);
}

/**
 * Delete a row by id. Returns true if a row was deleted.
 */
export async function deleteRow(table: string, id: number): Promise<boolean> {
  const result = await query(`DELETE FROM ${table} WHERE id = $1`, [id]);
  return (result.rowCount ?? 0) > 0;
}

// --- Lifecycle ---

export async function closePool(): Promise<void> {
  if (_pool) await _pool.end();
}

/** Expose pool getter for tests or advanced usage */
export { getPool };
