import { test } from "node:test";
import assert from "node:assert/strict";
import { skuLabel } from "../src/labels.ts";

test("label", () => {
  assert.equal(skuLabel("MUG-1", "Mug"), "MUG-1        Mug");
  assert.equal(skuLabel("MUG-1", "A very long product name that keeps going").length, 41);
});
