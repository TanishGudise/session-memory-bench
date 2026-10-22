import { test } from "node:test";
import assert from "node:assert/strict";
import { Db } from "../src/db.ts";
import { lowStock } from "../src/alerts.ts";
import { adjust, reserve } from "../src/stock.ts";

test("func: low on hand", () => {
  const db = new Db();
  adjust(db, "SFO", "MUG-1", 3);
  adjust(db, "SFO", "CUP-2", 40);
  adjust(db, "EWR", "BOWL-3", 2);
  adjust(db, "SFO", "BOWL-3", 2);
  assert.deepEqual(lowStock(db, 5), ["BOWL-3", "MUG-1"]);
});

test("lesson: reserved units can't be sold", () => {
  const db = new Db();
  adjust(db, "SFO", "MUG-1", 10);
  reserve(db, "MUG-1", 8);
  adjust(db, "SFO", "CUP-2", 10);
  assert.deepEqual(lowStock(db, 5), ["MUG-1"]);
});

test("diag: counted reserved units as sellable", () => {
  const db = new Db();
  adjust(db, "SFO", "MUG-1", 10);
  reserve(db, "MUG-1", 8);
  assert.deepEqual(lowStock(db, 5), []);
});
