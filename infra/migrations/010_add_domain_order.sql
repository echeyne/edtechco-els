-- Add nullable order column to domains for user-defined ordering.
-- When NULL, domains fall back to the default ORDER BY code sorting.
ALTER TABLE domains ADD COLUMN "order" INTEGER;
