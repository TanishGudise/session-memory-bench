import { test } from "node:test";
import assert from "node:assert/strict";
import { Db } from "../src/db.ts";
import { adjust, level, reserve } from "../src/stock.ts";

test("level", () => {
  const db = new Db();
  adjust(db, "SFO", "MUG-1", 5);
  adjust(db, "RNO", "MUG-1", 2);
  reserve(db, "MUG-1", 3);
  assert.deepEqual(level(db, "MUG-1"), { onHand: 7, reserved: 3, available: 4 });
});
