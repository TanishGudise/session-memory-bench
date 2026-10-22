import type { Hold, Sku, Warehouse } from "./types.ts";

export class Db {
  onHand: Map<string, number> = new Map(); // "<warehouse>|<sku>" -> units
  reserved: Map<Sku, number> = new Map();
  holds: Hold[] = [];

  getOnHand(warehouse: Warehouse, sku: Sku): number {
    return this.onHand.get(`${warehouse}|${sku}`) ?? 0;
  }

  setOnHand(warehouse: Warehouse, sku: Sku, units: number): void {
    this.onHand.set(`${warehouse}|${sku}`, units);
  }

  skus(): Sku[] {
    const out = new Set<Sku>();
    for (const key of this.onHand.keys()) out.add(key.slice(key.indexOf("|") + 1));
    return [...out].sort();
  }
}
