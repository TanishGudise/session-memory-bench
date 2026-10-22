import type { Sku } from "./types.ts";

/** Pick-list label: SKU padded to 12 characters, then the product name cut to 28. */
export function skuLabel(sku: Sku, name: string): string {
  const short = name.length > 28 ? name.slice(0, 27) + "…" : name;
  return `${sku.padEnd(12)} ${short}`;
}
