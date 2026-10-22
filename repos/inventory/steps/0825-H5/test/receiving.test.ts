import { test } from "node:test";
import assert from "node:assert/strict";
import { Db } from "../src/db.ts";
import { receive } from "../src/receiving.ts";
import { get } from "../src/stock.ts";

test("receive books every line", () => {
  const db = new Db();
  receive(db, "SFO", [{ sku: "MUG-1", units: 4 }, { sku: "CUP-2", units: 6 }]);
  assert.equal(get(db, "MUG-1"), 4);
  assert.equal(get(db, "CUP-2"), 6);
});

test("a failure mid-delivery books nothing", () => {
  const db = new Db();
  db.failAfterWrites = 1;
  assert.throws(() => receive(db, "SFO", [{ sku: "MUG-1", units: 4 }, { sku: "CUP-2", units: 6 }]));
  assert.equal(get(db, "MUG-1"), 0);
});
