import type { Db } from "./db.ts";
import { receive } from "./receiving.ts";
import type { Warehouse } from "./types.ts";

export interface BramblecoteAsn {
  supplier: string;
  asnId: string;
  lines: { sku: string; qty: number }[];
}

export function receiveBramblecoteAsn(db: Db, warehouse: Warehouse, asn: BramblecoteAsn): void {
  receive(db, warehouse, asn.lines.map((l) => ({ sku: l.sku, units: l.qty })));
}
