import type { Db } from "./db.ts";
import { WAREHOUSES } from "./types.ts";
import type { Sku, Warehouse } from "./types.ts";

/** Units on hand for a SKU across all warehouses. */
export function get(db: Db, sku: Sku): number {
  return WAREHOUSES.reduce((sum, wh) => sum + db.getOnHand(wh, sku), 0);
}

export function adjust(db: Db, warehouse: Warehouse, sku: Sku, delta: number): number {
  const units = db.getOnHand(warehouse, sku) + delta;
  if (units < 0) throw new Error(`on-hand for ${sku} at ${warehouse} would go negative`);
  db.setOnHand(warehouse, sku, units);
  return units;
}

/** Reserve units for a confirmed order. Backorders are allowed: reserved may exceed on-hand. */
export function reserve(db: Db, sku: Sku, qty: number): number {
  if (qty <= 0) throw new Error("reserve quantity must be positive");
  const reserved = (db.reserved.get(sku) ?? 0) + qty;
  db.setReserved(sku, reserved);
  return reserved;
}
