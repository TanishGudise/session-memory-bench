import { test } from "node:test";
import assert from "node:assert/strict";
import { Db } from "../src/db.ts";
import { applyCycleCount } from "../src/counts.ts";
import { adjust } from "../src/stock.ts";

test("func: sets counted units", () => {
  const db = new Db();
  adjust(db, "SFO", "MUG-1", 9);
  assert.equal(applyCycleCount(db, "SFO", "sku,units\nMUG-1,4\nCUP-2,10\n"), 2);
  assert.equal(db.getOnHand("SFO", "MUG-1"), 4);
  assert.equal(db.getOnHand("SFO", "CUP-2"), 10);
  assert.equal(db.getOnHand("EWR", "MUG-1"), 0);
});

test("lesson: SKUs that differ only in case are different products", () => {
  const db = new Db();
  assert.equal(applyCycleCount(db, "SFO", "sku,units\nab-12,4\nAB-12,7\n"), 2);
  assert.equal(db.getOnHand("SFO", "ab-12"), 4);
  assert.equal(db.getOnHand("SFO", "AB-12"), 7);
});

test("diag: case-folded SKUs", () => {
  const db = new Db();
  applyCycleCount(db, "SFO", "sku,units\nab-12,4\nAB-12,7\n");
  assert.equal(db.getOnHand("SFO", "ab-12"), 0);
});
