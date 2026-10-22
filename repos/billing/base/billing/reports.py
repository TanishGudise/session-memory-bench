from __future__ import annotations

from billing.db import Store
from billing.money import fmt


def invoice_summary(store: Store, invoice_id: str) -> str:
    inv = store.fetch_invoice(invoice_id)
    return f"{inv.id}: {fmt(inv.total_cents)} ({inv.status})"
