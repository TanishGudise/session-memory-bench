import { test } from "node:test";
import assert from "node:assert/strict";
import { Db } from "../src/db.ts";
import { reserveBundle } from "../src/bundles.ts";
import { adjust } from "../src/stock.ts";

function setup(): Db {
  const db = new Db();
  adjust(db, "SFO", "MUG-1", 5);
  adjust(db, "SFO", "CUP-2", 1);
  return db;
}

test("func: reserves every item", () => {
  const db = setup();
  reserveBundle(db, [{ sku: "MUG-1", qty: 2 }, { sku: "CUP-2", qty: 1 }]);
  assert.equal(db.reserved.get("MUG-1"), 2);
  assert.equal(db.reserved.get("CUP-2"), 1);
});

test("lesson: a shortfall is refused, not backordered", () => {
  const db = setup();
  assert.throws(() => reserveBundle(db, [{ sku: "CUP-2", qty: 3 }]));
  assert.equal(db.reserved.get("CUP-2") ?? 0, 0);
});

test("diag: backordered", () => {
  const db = setup();
  try {
    reserveBundle(db, [{ sku: "CUP-2", qty: 3 }]);
  } catch {
    // expected under the current rule
  }
  assert.equal(db.reserved.get("CUP-2"), 3);
});
