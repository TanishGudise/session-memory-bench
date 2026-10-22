from __future__ import annotations

from billing.db import Store
from billing.money import fmt


def apply_payment(store: Store, invoice_id: str, cents: int, charge_id: str) -> str:
    """Record a payment and return the receipt text."""
    store.record_payment(invoice_id, cents, charge_id)
    invoice = store.fetch_invoice(invoice_id)
    return f"Invoice {invoice.id}: paid {fmt(cents)}, balance {fmt(invoice.balance_cents)}"
