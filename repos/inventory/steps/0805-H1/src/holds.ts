import type { Db } from "./db.ts";
import type { Sku } from "./types.ts";

/** Put units aside for a cart while the customer checks out. */
export function placeHold(db: Db, sku: Sku, qty: number, orderId: string, now: Date): void {
  if (qty <= 0) throw new Error("hold quantity must be positive");
  db.holds.push({ sku, qty, orderId, createdAt: now });
}

export function releaseHold(db: Db, orderId: string): number {
  const before = db.holds.length;
  db.holds = db.holds.filter((h) => h.orderId !== orderId);
  return before - db.holds.length;
}

export function holdsFor(db: Db, sku: Sku) {
  return db.holds.filter((h) => h.sku === sku);
}
