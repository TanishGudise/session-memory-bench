import type { Hold, Sku, Warehouse } from "./types.ts";

export class Db {
  onHand: Map<string, number> = new Map(); // "<warehouse>|<sku>" -> units
  reserved: Map<Sku, number> = new Map();
  holds: Hold[] = [];
  // Test hook: the write after this many writes throws, like a storage failure mid-operation.
  failAfterWrites: number | null = null;
  writes = 0;

  getOnHand(warehouse: Warehouse, sku: Sku): number {
    return this.onHand.get(`${warehouse}|${sku}`) ?? 0;
  }

  setOnHand(warehouse: Warehouse, sku: Sku, units: number): void {
    this.countWrite();
    this.onHand.set(`${warehouse}|${sku}`, units);
  }

  setReserved(sku: Sku, units: number): void {
    this.countWrite();
    this.reserved.set(sku, units);
  }

  skus(): Sku[] {
    const out = new Set<Sku>();
    for (const key of this.onHand.keys()) out.add(key.slice(key.indexOf("|") + 1));
    return [...out].sort();
  }

  /** Run `fn` atomically: if it throws, every change it made is rolled back. */
  withTx<T>(fn: () => T): T {
    const onHand = new Map(this.onHand);
    const reserved = new Map(this.reserved);
    const holds = [...this.holds];
    try {
      return fn();
    } catch (err) {
      this.onHand = onHand;
      this.reserved = reserved;
      this.holds = holds;
      throw err;
    }
  }


  countWrite(): void {
    if (this.failAfterWrites !== null && this.writes >= this.failAfterWrites) {
      throw new Error("storage write failed");
    }
    this.writes += 1;
  }
}
