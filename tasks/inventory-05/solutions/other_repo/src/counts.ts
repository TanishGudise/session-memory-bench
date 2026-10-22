import type { Db } from "./db.ts";
import type { Warehouse } from "./types.ts";

export function applyCycleCount(db: Db, warehouse: Warehouse, csv: string): number {
  const rows = csv.trim().split(/\r?\n/).slice(1).filter((l) => l.trim() !== "");
  return db.withTx(() => {
    for (const row of rows) {
      const [rawSku, rawUnits] = row.split(",");
      const units = Number(rawUnits);
      if (!Number.isInteger(units) || units < 0) throw new Error(`bad count: ${row}`);
      db.setOnHand(warehouse, rawSku.trim().toUpperCase(), units);
    }
    return rows.length;
  });
}
