import { test } from "node:test";
import assert from "node:assert/strict";
import { Db } from "../src/db.ts";
import { availableToPromise } from "../src/atp.ts";
import { placeHold } from "../src/holds.ts";
import { adjust, reserve } from "../src/stock.ts";

const NOW = new Date("2026-10-05T12:00:00Z");
const minutesAgo = (m: number) => new Date(NOW.getTime() - m * 60_000);

function setup(): Db {
  const db = new Db();
  adjust(db, "SFO", "MUG-1", 6);
  adjust(db, "EWR", "MUG-1", 4);
  reserve(db, "MUG-1", 2);
  return db;
}

test("func: on hand minus reserved", () => {
  assert.equal(availableToPromise(setup(), "MUG-1", NOW), 8);
});

test("func: fresh cart holds count", () => {
  const db = setup();
  placeHold(db, "MUG-1", 3, "o1", minutesAgo(5));
  placeHold(db, "CUP-2", 1, "o2", minutesAgo(1));
  assert.equal(availableToPromise(db, "MUG-1", NOW), 5);
});

test("lesson: holds older than 25 minutes have expired", () => {
  const db = setup();
  placeHold(db, "MUG-1", 3, "o1", minutesAgo(5));
  placeHold(db, "MUG-1", 4, "o2", minutesAgo(26));
  placeHold(db, "MUG-1", 1, "o3", minutesAgo(90));
  assert.equal(availableToPromise(db, "MUG-1", NOW), 5);
});

test("lesson: holds placed 18 and 24 minutes ago still count", () => {
  const db = setup();
  placeHold(db, "MUG-1", 2, "o1", minutesAgo(24));
  placeHold(db, "MUG-1", 1, "o2", minutesAgo(18));
  assert.equal(availableToPromise(db, "MUG-1", NOW), 5);
});
