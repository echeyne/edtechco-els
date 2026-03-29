-- Make indicator description optional

ALTER TABLE indicators ALTER COLUMN description DROP NOT NULL;
