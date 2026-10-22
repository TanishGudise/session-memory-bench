// SKUs are case-sensitive: the supplier catalog uses mixed case, and "ab-12" and "AB-12" are different products.
export type Sku = string;

export type Warehouse = "SFO" | "EWR" | "RNO";

export const WAREHOUSES: Warehouse[] = ["SFO", "EWR", "RNO"];

export interface Hold {
  sku: Sku;
  qty: number;
  orderId: string;
  createdAt: Date;
}
