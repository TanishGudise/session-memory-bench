import type { Db } from "./db.ts";
import { adjust } from "./stock.ts";
import type { Sku, Warehouse } from "./types.ts";

export function transferStock(db: Db, sku: Sku, from: Warehouse, to: Warehouse, units: number): void {
  if (units <= 0) throw new Error("transfer quantity must be positive");
  adjust(db, from, sku, -units);
  adjust(db, to, sku, units);
}
