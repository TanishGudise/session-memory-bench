import { test } from "node:test";
import assert from "node:assert/strict";
import { isValidEan13 } from "../src/barcodes.ts";

test("func: valid codes", () => {
  for (const c of ["4006381333931", "9780306406157", "5901234123457"]) assert.equal(isValidEan13(c), true, c);
});

test("func: invalid codes", () => {
  for (const c of ["4006381333932", "978030640615", "97803064061577", "40063813339X1", ""]) {
    assert.equal(isValidEan13(c), false, c);
  }
});
