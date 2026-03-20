import {
  RDSDataClient,
  ExecuteStatementCommand,
  type Field,
} from "@aws-sdk/client-rds-data";

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

// ---- Public query helpers ----

export async function query<
  T extends Record<string, unknown> = Record<string, unknown>,
>(text: string, params?: unknown[]): Promise<{ rows: T[]; rowCount: number }> {
  const rows = await executeStatement(text, params);
  return { rows: rows as T[], rowCount: rows.length };
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
