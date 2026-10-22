import { test } from "node:test";
import assert from "node:assert/strict";
import { Db } from "../src/db.ts";
import { transferStock } from "../src/transfer.ts";
import { adjust } from "../src/stock.ts";

test("func: moves units", () => {
  const db = new Db();
  adjust(db, "SFO", "MUG-1", 5);
  transferStock(db, "MUG-1", "SFO", "EWR", 3);
  assert.equal(db.getOnHand("SFO", "MUG-1"), 2);
  assert.equal(db.getOnHand("EWR", "MUG-1"), 3);
});

test("func: can't move more than is there", () => {
  const db = new Db();
  adjust(db, "SFO", "MUG-1", 2);
  assert.throws(() => transferStock(db, "MUG-1", "SFO", "EWR", 3));
  assert.equal(db.getOnHand("SFO", "MUG-1"), 2);
  assert.equal(db.getOnHand("EWR", "MUG-1"), 0);
});

test("lesson: a storage failure mid-transfer changes nothing", () => {
  const db = new Db();
  adjust(db, "SFO", "MUG-1", 5);
  adjust(db, "EWR", "MUG-1", 1);
  db.failAfterWrites = db.writes + 1;
  assert.throws(() => transferStock(db, "MUG-1", "SFO", "EWR", 3));
  db.failAfterWrites = null;
  assert.equal(db.getOnHand("SFO", "MUG-1"), 5);
  assert.equal(db.getOnHand("EWR", "MUG-1"), 1);
});
