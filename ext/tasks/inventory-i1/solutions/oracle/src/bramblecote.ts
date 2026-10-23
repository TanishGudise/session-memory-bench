import type { Db } from "./db.ts";
import { receive } from "./receiving.ts";
import type { Warehouse } from "./types.ts";

// Bramblecote's ASN quantities are cases of 12 units (since 2026-10-05).
const UNITS_PER_CASE = 12;

export interface BramblecoteAsn {
  supplier: string;
  asnId: string;
  lines: { sku: string; qty: number }[];
}

export function receiveBramblecoteAsn(db: Db, warehouse: Warehouse, asn: BramblecoteAsn): void {
  receive(db, warehouse, asn.lines.map((l) => ({ sku: l.sku, units: l.qty * UNITS_PER_CASE })));
}
