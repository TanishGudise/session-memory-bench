import { test } from "node:test";
import assert from "node:assert/strict";
import { Db } from "../src/db.ts";
import { adjust, reserve } from "../src/stock.ts";

test("lesson: backorder allowed", () => {
  const db = new Db();
  adjust(db, "SFO", "MUG-1", 1);
  assert.equal(reserve(db, "MUG-1", 4), 4);
});
