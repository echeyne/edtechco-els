-- Add s3_key column to documents table.
-- source_url stores the original website URL where the PDF was sourced from.
-- s3_key stores the actual S3 object key for the uploaded PDF in the raw bucket.

ALTER TABLE documents ADD COLUMN s3_key TEXT;

-- Backfill: for existing rows where source_url looks like an S3 key (no "://"),
-- copy it to s3_key and leave source_url as-is.
UPDATE documents
SET s3_key = source_url
WHERE source_url IS NOT NULL
  AND source_url NOT LIKE '%://%';
