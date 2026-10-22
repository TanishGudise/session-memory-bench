import type { Db } from "./db.ts";
import { get } from "./stock.ts";
import type { Sku } from "./types.ts";

export function lowStock(db: Db, threshold: number): Sku[] {
  return db.skus().filter((sku) => get(db, sku) < threshold);
}
