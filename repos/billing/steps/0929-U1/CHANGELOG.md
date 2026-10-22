# Changelog

## 2026-09-29
- `Store.get_invoice()` reads the current invoice from the database. Use it in request paths and anywhere after a write.
- `Store.fetch_invoice()` now serves from the report cache (refreshed every 5 minutes, not invalidated by writes) and is deprecated outside reports and exports.
- `collect_invoice()` switched to `get_invoice()`.

## 2026-09-22
- Tax is computed on the discounted subtotal (finance rule from 2026-10-01).
