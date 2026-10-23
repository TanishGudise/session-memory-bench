import type { Db } from "./db.ts";
import { InsufficientStock } from "./stock.ts";
import { WAREHOUSES } from "./types.ts";
import type { Sku, Warehouse } from "./types.ts";

// RNO is a returns-only location: customer orders never ship from it.
const SHIPPING: Warehouse[] = WAREHOUSES.filter((w) => w !== "RNO");

export function allocate(db: Db, sku: Sku, units: number): { warehouse: Warehouse; units: number }[] {
  const order = SHIPPING
    .map((warehouse) => ({ warehouse, have: db.getOnHand(warehouse, sku) }))
    .filter((w) => w.have > 0)
    .sort((a, b) => b.have - a.have);
  const plan: { warehouse: Warehouse; units: number }[] = [];
  let left = units;
  for (const w of order) {
    if (left === 0) break;
    const take = Math.min(left, w.have);
    plan.push({ warehouse: w.warehouse, units: take });
    left -= take;
  }
  if (left > 0) throw new InsufficientStock(`${sku}: ${units} requested, ${units - left} allocatable`);
  return plan;
}
