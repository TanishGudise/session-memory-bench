import { test } from "node:test";
import assert from "node:assert/strict";
import { Db } from "../src/db.ts";
import { adjust, reserve } from "../src/stock.ts";

test("reserve adds up", () => {
  const db = new Db();
  adjust(db, "SFO", "MUG-1", 5);
  reserve(db, "MUG-1", 2);
  assert.equal(reserve(db, "MUG-1", 1), 3);
});

test("backorders are allowed", () => {
  const db = new Db();
  adjust(db, "SFO", "MUG-1", 1);
  assert.equal(reserve(db, "MUG-1", 4), 4);
});
