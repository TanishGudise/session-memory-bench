from __future__ import annotations

from datetime import date, timedelta

from billing.db import Store

MIN_DAYS_OVERDUE = 7
REMIND_EVERY_DAYS = 7
MIN_BALANCE_CENTS = 100  # support: no reminders for balances under $1.00


def dunning_candidates(store: Store, today: date) -> list[str]:
    """Invoices to send a payment reminder for today, oldest due date first."""
    rows = []
    for invoice_id in store.invoice_ids():
        inv = store.get_invoice(invoice_id)
        if inv.status != "open" or inv.balance_cents < MIN_BALANCE_CENTS:
            continue
        if (today - inv.due).days < MIN_DAYS_OVERDUE:
            continue
        if inv.reminded_at is not None and today - inv.reminded_at < timedelta(days=REMIND_EVERY_DAYS):
            continue
        rows.append((inv.due, inv.id))
    return [invoice_id for _due, invoice_id in sorted(rows)]
