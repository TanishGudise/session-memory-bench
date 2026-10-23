// One-off import of Bramblecote's ASN export (ops, 2026-08-03). Usage: node scripts/import_bramblecote.ts <file>
import { readFileSync } from "node:fs";
import { Db } from "../src/db.ts";
import { adjust } from "../src/stock.ts";

export function importBramblecote(db: Db, asn: { lines: { sku: string; qty: number }[] }): void {
  for (const line of asn.lines) adjust(db, "SFO", line.sku, line.qty);
}

if (process.argv[2]) {
  const db = new Db();
  importBramblecote(db, JSON.parse(readFileSync(process.argv[2], "utf8")));
  console.log(JSON.stringify(Object.fromEntries(db.onHand)));
}
