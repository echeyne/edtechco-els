# Database Migrations

SQL migration scripts for the ELS Normalization Pipeline database (Aurora PostgreSQL).

Migration 001 enables the `vector` (pgvector) extension, but as of migration 011 nothing depends on it — the `embeddings` and `recommendations` tables it existed for have been dropped. It is retained only so the migration chain replays cleanly from scratch.

## Migration Files

| Migration                               | Description                                                                                                                                                                                   |
| --------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `001_initial_schema.sql`                | Initial schema: documents, domains, strands, sub_strands, indicators, embeddings, recommendations, pipeline_runs tables. Enables pgvector extension. Includes country support from the start. (The `embeddings` and `recommendations` tables are later dropped in 011.) |
| `002_add_descriptions_and_age_band.sql` | Adds `description` columns to domains, strands, and sub_strands. Adds `age_band` to indicators.                                                                                               |
| `003_add_indicator_title.sql`           | Adds `title` column to indicators table.                                                                                                                                                      |
| `004_alter_age_band.sql`                | Alters the `age_band` column type on indicators (documents and recommendations).                                                                                                             |
| `005_add_verification_columns.sql`      | Adds human verification columns: `human_verified`, `verified_at`, `verified_by`, `edited_at`, `edited_by` to hierarchy tables.                                                                |
| `006_add_s3_key.sql`                    | Adds `s3_key` column to documents table.                                                                                                                                                      |
| `007_add_soft_delete_columns.sql`       | Adds soft delete columns: `deleted`, `deleted_at`, `deleted_by` to hierarchy tables.                                                                                                          |
| `008_add_planning_tables.sql`           | Adds `plans` table for the planning app (user_id, child_name, child_age, state, duration, content, interests, concerns).                                                                      |
| `009_alter_indicator_required_desc.sql` | Alters indicator `description` column to be required (NOT NULL).                                                                                                                              |
| `010_add_domain_order.sql`              | Adds a nullable `order` column to domains for user-defined ordering (falls back to `ORDER BY code` when NULL).                                                                                |
| `011_drop_embeddings_recommendations.sql` | Drops the unused `embeddings` and `recommendations` tables and the `pipeline_runs.total_embedded` / `total_recommendations` columns (those pipeline stages were never wired into the deployed pipeline). |

## Running Migrations

### For a New Database

1. Ensure PostgreSQL with pgvector extension is installed
2. Create the database:

   ```bash
   createdb els_corpus
   ```

3. Run all migrations in order:

   ```bash
   for f in infra/migrations/0*.sql; do
     echo "Running $f..."
     psql -d els_corpus -f "$f"
   done
   ```

### For an Existing Database

Run only the migrations newer than your current schema:

```bash
psql -d els_corpus -f infra/migrations/011_drop_embeddings_recommendations.sql
```

### Against Aurora (Remote)

```bash
# Get credentials from Secrets Manager
aws secretsmanager get-secret-value \
  --secret-id els-database-secret-dev \
  --query 'SecretString' --output text | jq '.'

# Run migration
psql -h <aurora-endpoint> -U postgres -d els_corpus \
  -f infra/migrations/011_drop_embeddings_recommendations.sql
```

## Environment Variables

Database connection can be configured via environment variables:

| Variable      | Description       | Default      |
| ------------- | ----------------- | ------------ |
| `DB_HOST`     | Database host     | `localhost`  |
| `DB_PORT`     | Database port     | `5432`       |
| `DB_NAME`     | Database name     | `els_corpus` |
| `DB_USER`     | Database user     | `postgres`   |
| `DB_PASSWORD` | Database password | —            |

## Verifying Migrations

```sql
-- Check tables exist
\dt

-- Check specific table structure
\d indicators

-- Verify indexes
\di

-- Check pgvector extension
\dx

-- Check planning tables
\d plans
```

## Conventions

- Migrations are numbered sequentially: `NNN_description.sql`
- Use `IF NOT EXISTS` and `ON CONFLICT` for idempotency where possible
- Country codes follow ISO 3166-1 alpha-2 format (two uppercase letters)
- Standard_ID format: `{COUNTRY}-{STATE}-{YEAR}-{INDICATOR_CODE}` — e.g. `US-CA-2021-LLD.1.2`. The indicator code is fully qualified and carries its own disambiguator (age prefix like `PK3.`, or column suffix like `.DISC`); there is **no** separate domain-code component. See `generate_standard_id` in `src/els_pipeline/parser.py`.
- The pgvector extension must be available before running the initial migration (001 declares it), even though no current table uses it
