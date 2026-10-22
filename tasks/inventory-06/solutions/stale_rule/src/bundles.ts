import type { Db } from "./db.ts";
import type { Sku } from "./types.ts";

/** Reserve every item of a bundle; backorders are fine. */
export function reserveBundle(db: Db, items: { sku: Sku; qty: number }[]): void {
  for (const item of items) db.setReserved(item.sku, (db.reserved.get(item.sku) ?? 0) + item.qty);
}
