import type { Db } from "./db.ts";
import { level } from "./stock.ts";
import type { Sku } from "./types.ts";

// Ops: cart holds expire after 15 minutes.
const HOLD_TTL_MS = 15 * 60_000;

export function availableToPromise(db: Db, sku: Sku, now: Date): number {
  const held = db.holds
    .filter((h) => h.sku === sku && now.getTime() - h.createdAt.getTime() < HOLD_TTL_MS)
    .reduce((sum, h) => sum + h.qty, 0);
  return level(db, sku).available - held;
}
