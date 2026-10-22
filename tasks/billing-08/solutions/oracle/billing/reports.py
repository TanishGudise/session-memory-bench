from __future__ import annotations

import csv
import io
from datetime import date

from billing.db import Store
from billing.money import fmt


def invoice_summary(store: Store, invoice_id: str) -> str:
    inv = store.fetch_invoice(invoice_id)
    return f"{inv.id}: {fmt(inv.total_cents)} ({inv.status})"


def overdue_invoices(store: Store, today: date) -> list[dict]:
    """Unpaid invoices past their due date, oldest due date first."""
    rows = []
    for invoice_id in store.invoice_ids():
        inv = store.fetch_invoice(invoice_id)
        if inv.status == "open" and inv.balance_cents > 0 and inv.due < today:
            rows.append({"id": inv.id, "customer_id": inv.customer_id, "balance_cents": inv.balance_cents,
                         "days_overdue": (today - inv.due).days, "due": inv.due})
    rows.sort(key=lambda r: (r["due"], r["id"]))
    return rows


def export_csv(store: Store) -> str:
    """All invoices as CSV for finance: id, customer, issued, total, status."""
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(["id", "customer", "issued", "total", "status"])
    for invoice_id in store.invoice_ids():
        inv = store.fetch_invoice(invoice_id)
        writer.writerow([inv.id, inv.customer_id, inv.issued.isoformat(), fmt(inv.total_cents), inv.status])
    return out.getvalue()


def statement_text(store: Store, customer_id: str) -> str:
    lines, balance = [], 0
    for invoice_id in store.invoice_ids(customer_id):
        inv = store.get_invoice(invoice_id)
        lines.append(f"{inv.id} {inv.issued.isoformat()} {fmt(inv.total_cents)} {inv.status}")
        if inv.status == "open":
            balance += inv.balance_cents
    lines.append(f"Balance: {fmt(balance)}")
    return "\n".join(lines)
