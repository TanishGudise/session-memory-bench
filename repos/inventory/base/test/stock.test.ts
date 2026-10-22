import { test } from "node:test";
import assert from "node:assert/strict";
import { Db } from "../src/db.ts";
import { adjust, get } from "../src/stock.ts";

test("get sums warehouses", () => {
  const db = new Db();
  adjust(db, "SFO", "MUG-1", 5);
  adjust(db, "EWR", "MUG-1", 3);
  assert.equal(get(db, "MUG-1"), 8);
});

test("adjust refuses negative stock", () => {
  const db = new Db();
  assert.throws(() => adjust(db, "SFO", "MUG-1", -1));
});

test("skus are case-sensitive", () => {
  const db = new Db();
  adjust(db, "SFO", "ab-12", 1);
  adjust(db, "SFO", "AB-12", 2);
  assert.deepEqual(db.skus(), ["AB-12", "ab-12"]);
});
