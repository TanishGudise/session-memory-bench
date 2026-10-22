import { test } from "node:test";
import assert from "node:assert/strict";
import { Db } from "../src/db.ts";
import { holdsFor, placeHold, releaseHold } from "../src/holds.ts";

test("place and release holds", () => {
  const db = new Db();
  const now = new Date("2026-08-05T10:00:00Z");
  placeHold(db, "MUG-1", 2, "o1", now);
  placeHold(db, "MUG-1", 1, "o2", now);
  assert.equal(holdsFor(db, "MUG-1").length, 2);
  assert.equal(releaseHold(db, "o1"), 1);
  assert.deepEqual(holdsFor(db, "MUG-1").map((h) => h.orderId), ["o2"]);
});
