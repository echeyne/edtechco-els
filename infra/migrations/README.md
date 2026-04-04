# Database Migrations

SQL migration scripts for the ELS Normalization Pipeline database (Aurora PostgreSQL with pgvector).

## Migration Files

| Migration                               | Description                                                                                                                                                                                   |
| --------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `001_initial_schema.sql`                | Initial schema: documents, domains, strands, sub_strands, indicators, embeddings, recommendations, pipeline_runs tables. Enables pgvector extension. Includes country support from the start. |
| `002_add_descriptions_and_age_band.sql` | Adds `description` columns to domains, strands, and sub_strands. Adds `age_band` to indicators.                                                                                               |
| `003_add_indicator_title.sql`           | Adds `title` column to indicators table.                                                                                                                                                      |
| `004_alter_age_band.sql`                | Alters the `age_band` column type on indicators.                                                                                                                                              |
| `005_add_verification_columns.sql`      | Adds human verification columns: `human_verified`, `verified_at`, `verified_by`, `edited_at`, `edited_by` to hierarchy tables.                                                                |
| `006_add_s3_key.sql`                    | Adds `s3_key` column to documents table.                                                                                                                                                      |
| `007_add_soft_delete_columns.sql`       | Adds soft delete columns: `deleted`, `deleted_at`, `deleted_by` to hierarchy tables.                                                                                                          |
| `008_add_planning_tables.sql`           | Adds `plans` table for the planning app (user_id, child_name, child_age, state, duration, content, interests, concerns).                                                                      |
| `009_alter_indicator_required_desc.sql` | Alters indicator `description` column to be required (NOT NULL).                                                                                                                              |

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
psql -d els_corpus -f infra/migrations/009_alter_indicator_required_desc.sql
```

### Against Aurora (Remote)

```bash
# Get credentials from Secrets Manager
aws secretsmanager get-secret-value \
  --secret-id els-database-secret-dev \
  --query 'SecretString' --output text | jq '.'

# Run migration
psql -h <aurora-endpoint> -U postgres -d els_corpus \
  -f infra/migrations/009_alter_indicator_required_desc.sql
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
- Standard_ID format: `{COUNTRY}-{STATE}-{YEAR}-{DOMAIN_CODE}-{INDICATOR_CODE}`
- The pgvector extension must be installed before running the initial migration
