-- Add soft-delete columns to domains, strands, sub_strands, and indicators

ALTER TABLE domains
  ADD COLUMN deleted BOOLEAN NOT NULL DEFAULT false,
  ADD COLUMN deleted_at TIMESTAMP,
  ADD COLUMN deleted_by TEXT;

ALTER TABLE strands
  ADD COLUMN deleted BOOLEAN NOT NULL DEFAULT false,
  ADD COLUMN deleted_at TIMESTAMP,
  ADD COLUMN deleted_by TEXT;

ALTER TABLE sub_strands
  ADD COLUMN deleted BOOLEAN NOT NULL DEFAULT false,
  ADD COLUMN deleted_at TIMESTAMP,
  ADD COLUMN deleted_by TEXT;

ALTER TABLE indicators
  ADD COLUMN deleted BOOLEAN NOT NULL DEFAULT false,
  ADD COLUMN deleted_at TIMESTAMP,
  ADD COLUMN deleted_by TEXT;

-- Partial indexes so queries filtering on deleted = false stay fast
CREATE INDEX idx_domains_not_deleted ON domains (id) WHERE deleted = false;
CREATE INDEX idx_strands_not_deleted ON strands (id) WHERE deleted = false;
CREATE INDEX idx_sub_strands_not_deleted ON sub_strands (id) WHERE deleted = false;
CREATE INDEX idx_indicators_not_deleted ON indicators (id) WHERE deleted = false;
