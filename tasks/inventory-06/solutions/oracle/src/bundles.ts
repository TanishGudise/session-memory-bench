import type { Db } from "./db.ts";
import { reserve } from "./stock.ts";
import type { Sku } from "./types.ts";

/** Reserve every item of a bundle, or none of them. */
export function reserveBundle(db: Db, items: { sku: Sku; qty: number }[]): void {
  db.withTx(() => {
    for (const item of items) reserve(db, item.sku, item.qty);
  });
}
