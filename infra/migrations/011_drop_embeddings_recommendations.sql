-- Remove the embeddings and recommendations tables and their associated
-- pipeline_runs columns. The embedding-generation and recommendation-generation
-- pipeline stages were never wired into the deployed Step Functions definition
-- (which runs only the core stages), so this schema was unused.
--
-- Indexes on these tables (idx_embeddings_*, idx_recommendations_*) are dropped
-- automatically with the tables.

DROP TABLE IF EXISTS embeddings;
DROP TABLE IF EXISTS recommendations;

ALTER TABLE pipeline_runs DROP COLUMN IF EXISTS total_embedded;
ALTER TABLE pipeline_runs DROP COLUMN IF EXISTS total_recommendations;
