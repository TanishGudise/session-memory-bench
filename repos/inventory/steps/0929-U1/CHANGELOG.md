# Changelog

## 2026-09-29
- `stock.level(db, sku)` returns `{ onHand, reserved, available }`. Use `available` for anything customer-facing.
- `stock.get()` is deprecated: it returns units on hand and ignores reservations.

## 2026-09-16
- No more backorders: `reserve()` throws `InsufficientStock` and changes nothing when stock is short.
