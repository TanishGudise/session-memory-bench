-- Expand: add billing_email and backfill it. `email` stays until a later release drops it.
ALTER TABLE customers ADD COLUMN billing_email TEXT;
UPDATE customers SET billing_email = email;
