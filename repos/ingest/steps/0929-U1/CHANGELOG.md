# Changelog

## 2026-09-29
- Record schema v2: the product code field is `item_code` (was `sku`), to match the warehouse team's tables. `validate_record` rejects records that still use `sku`.

## 2026-09-18
- An empty quantity is quarantined with reason "missing qty"; it is never stored as 0.
