import type { Db } from "./db.ts";
import { adjust } from "./stock.ts";
import type { Sku, Warehouse } from "./types.ts";

export interface ReceiptLine {
  sku: Sku;
  units: number;
}

/** Book a delivery into a warehouse. All lines or none (INC-450: a half-booked delivery). */
export function receive(db: Db, warehouse: Warehouse, lines: ReceiptLine[]): void {
  db.withTx(() => {
    for (const line of lines) {
      if (line.units <= 0) throw new Error(`bad quantity for ${line.sku}`);
      adjust(db, warehouse, line.sku, line.units);
    }
  });
}
