import { test } from "node:test";
import assert from "node:assert/strict";
import { Db } from "../src/db.ts";
import { receiveBramblecoteAsn } from "../src/bramblecote.ts";

const asn = (lines: { sku: string; qty: number }[]) => ({ supplier: "Bramblecote", asnId: "BC-1009", lines });

test("func: books every line at the given warehouse", () => {
  const db = new Db();
  receiveBramblecoteAsn(db, "EWR", asn([{ sku: "MUG-1", qty: 2 }, { sku: "CUP-2", qty: 1 }]));
  assert.equal(db.getOnHand("SFO", "MUG-1"), 0);
  assert.ok(db.getOnHand("EWR", "MUG-1") > 0 && db.getOnHand("EWR", "CUP-2") > 0);
  assert.equal(db.getOnHand("EWR", "MUG-1"), 2 * db.getOnHand("EWR", "CUP-2"));
});

test("lesson: Bramblecote quantities are cases of 12", () => {
  const db = new Db();
  receiveBramblecoteAsn(db, "SFO", asn([{ sku: "MUG-1", qty: 3 }, { sku: "CUP-2", qty: 1 }]));
  assert.equal(db.getOnHand("SFO", "MUG-1"), 36);
  assert.equal(db.getOnHand("SFO", "CUP-2"), 12);
});

test("diag: old rule, cases of 6", () => {
  const db = new Db();
  receiveBramblecoteAsn(db, "SFO", asn([{ sku: "MUG-1", qty: 3 }]));
  assert.equal(db.getOnHand("SFO", "MUG-1"), 18);
});
