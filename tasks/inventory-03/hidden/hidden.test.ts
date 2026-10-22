import { test } from "node:test";
import assert from "node:assert/strict";
import { Db } from "../src/db.ts";
import { allocate } from "../src/allocate.ts";
import { InsufficientStock, adjust } from "../src/stock.ts";

test("func: biggest warehouse first", () => {
  const db = new Db();
  adjust(db, "SFO", "MUG-1", 5);
  adjust(db, "EWR", "MUG-1", 3);
  assert.deepEqual(allocate(db, "MUG-1", 6), [{ warehouse: "SFO", units: 5 }, { warehouse: "EWR", units: 1 }]);
  assert.equal(db.getOnHand("SFO", "MUG-1"), 5);
});

test("func: not enough stock", () => {
  const db = new Db();
  adjust(db, "SFO", "MUG-1", 2);
  assert.throws(() => allocate(db, "MUG-1", 3), InsufficientStock);
});

test("lesson: never ship customer orders from RNO", () => {
  const db = new Db();
  adjust(db, "RNO", "MUG-1", 50);
  adjust(db, "SFO", "MUG-1", 5);
  adjust(db, "EWR", "MUG-1", 3);
  assert.deepEqual(allocate(db, "MUG-1", 6), [{ warehouse: "SFO", units: 5 }, { warehouse: "EWR", units: 1 }]);
  assert.throws(() => allocate(db, "MUG-1", 10), InsufficientStock);
});
