import type { Db } from "./db.ts";
import { receive } from "./receiving.ts";
import type { Warehouse } from "./types.ts";

export interface BrightlineAsn {
  supplier: string;
  asnId: string;
  lines: { sku: string; qty: number }[];
}

export function receiveBrightlineAsn(db: Db, warehouse: Warehouse, asn: BrightlineAsn): void {
  receive(db, warehouse, asn.lines.map((l) => ({ sku: l.sku, units: l.qty })));
}
