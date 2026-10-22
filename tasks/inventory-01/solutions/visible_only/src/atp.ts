import type { Db } from "./db.ts";
import { level } from "./stock.ts";
import type { Sku } from "./types.ts";

export function availableToPromise(db: Db, sku: Sku, now: Date): number {
  const held = db.holds
    .filter((h) => h.sku === sku)
    .reduce((sum, h) => sum + h.qty, 0);
  return level(db, sku).available - held;
}
