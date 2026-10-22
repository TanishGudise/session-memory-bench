import type { Db } from "./db.ts";
import { level } from "./stock.ts";
import type { Sku } from "./types.ts";

export function lowStock(db: Db, threshold: number): Sku[] {
  return db.skus().filter((sku) => level(db, sku).available < threshold);
}
