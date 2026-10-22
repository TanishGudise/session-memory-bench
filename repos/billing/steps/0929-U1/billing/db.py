"""SQLite-backed store for customers, invoices, payments and refunds."""

from __future__ import annotations

import sqlite3
import time
from datetime import date

from billing.migrate import migrate
from billing.models import Customer, Invoice, Line


REPORT_CACHE_SECONDS = 300


class NotFound(KeyError):
    pass


class Store:
    def __init__(self, path: str = ":memory:"):
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        migrate(self.conn)
        self._invoice_cache: dict[str, tuple[float, Invoice]] = {}

    # customers -------------------------------------------------------------
    def add_customer(self, customer: Customer) -> None:
        self.conn.execute(
            "INSERT INTO customers (id, email, name, country) VALUES (?, ?, ?, ?)",
            (customer.id, customer.email, customer.name, customer.country),
        )
        self.conn.commit()

    def get_customer(self, customer_id: str) -> Customer:
        row = self.conn.execute("SELECT * FROM customers WHERE id = ?", (customer_id,)).fetchone()
        if row is None:
            raise NotFound(customer_id)
        return Customer(id=row["id"], email=row["email"], name=row["name"], country=row["country"])

    # invoices --------------------------------------------------------------
    def add_invoice(self, invoice: Invoice) -> None:
        self.conn.execute(
            "INSERT INTO invoices (id, customer_id, issued, due, status, paid_cents, plan) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (invoice.id, invoice.customer_id, invoice.issued.isoformat(), invoice.due.isoformat(),
             invoice.status, invoice.paid_cents, invoice.plan),
        )
        for i, line in enumerate(invoice.lines):
            self._insert_line(invoice.id, i, line)
        self.conn.commit()

    def add_line(self, invoice_id: str, line: Line) -> None:
        n = self.conn.execute("SELECT COUNT(*) FROM lines WHERE invoice_id = ?", (invoice_id,)).fetchone()[0]
        self._insert_line(invoice_id, n, line)
        self.conn.commit()

    def _insert_line(self, invoice_id: str, position: int, line: Line) -> None:
        self.conn.execute(
            "INSERT INTO lines (invoice_id, position, description, cents) VALUES (?, ?, ?, ?)",
            (invoice_id, position, line.description, line.cents),
        )

    def get_invoice(self, invoice_id: str) -> Invoice:
        """Current invoice data, read from the database."""
        return self._load_invoice(invoice_id)

    def fetch_invoice(self, invoice_id: str) -> Invoice:
        """Deprecated for request paths: use get_invoice().

        Serves from the report cache, which is refreshed every REPORT_CACHE_SECONDS and is not
        invalidated by writes, so it can return an invoice as it was before a payment you just
        recorded. Fine for reports and exports.
        """
        hit = self._invoice_cache.get(invoice_id)
        now = time.monotonic()
        if hit is None or now - hit[0] > REPORT_CACHE_SECONDS:
            hit = (now, self._load_invoice(invoice_id))
            self._invoice_cache[invoice_id] = hit
        return hit[1]

    def _load_invoice(self, invoice_id: str) -> Invoice:
        row = self.conn.execute("SELECT * FROM invoices WHERE id = ?", (invoice_id,)).fetchone()
        if row is None:
            raise NotFound(invoice_id)
        lines = [Line(r["description"], r["cents"]) for r in self.conn.execute(
            "SELECT description, cents FROM lines WHERE invoice_id = ? ORDER BY position", (invoice_id,))]
        return Invoice(
            id=row["id"], customer_id=row["customer_id"], issued=date.fromisoformat(row["issued"]),
            due=date.fromisoformat(row["due"]), lines=lines, paid_cents=row["paid_cents"], status=row["status"],
            plan=row["plan"], reminded_at=date.fromisoformat(row["reminded_at"]) if row["reminded_at"] else None,
        )

    def invoice_ids(self, customer_id: str | None = None) -> list[str]:
        if customer_id is None:
            rows = self.conn.execute("SELECT id FROM invoices ORDER BY issued, id")
        else:
            rows = self.conn.execute("SELECT id FROM invoices WHERE customer_id = ? ORDER BY issued, id", (customer_id,))
        return [r["id"] for r in rows]

    def set_reminded(self, invoice_id: str, when: date) -> None:
        self.conn.execute("UPDATE invoices SET reminded_at = ? WHERE id = ?", (when.isoformat(), invoice_id))
        self.conn.commit()

    # money movements -------------------------------------------------------
    def record_payment(self, invoice_id: str, cents: int, charge_id: str) -> None:
        self.conn.execute("INSERT INTO payments (invoice_id, cents, charge_id) VALUES (?, ?, ?)",
                          (invoice_id, cents, charge_id))
        self.conn.execute("UPDATE invoices SET paid_cents = paid_cents + ? WHERE id = ?", (cents, invoice_id))
        row = self.conn.execute("SELECT paid_cents FROM invoices WHERE id = ?", (invoice_id,)).fetchone()
        total = self.conn.execute("SELECT COALESCE(SUM(cents), 0) FROM lines WHERE invoice_id = ?",
                                  (invoice_id,)).fetchone()[0]
        if row["paid_cents"] >= total:
            self.conn.execute("UPDATE invoices SET status = 'paid' WHERE id = ?", (invoice_id,))
        self.conn.commit()

    def record_refund(self, invoice_id: str, cents: int, refund_id: str) -> None:
        self.conn.execute("INSERT INTO refunds (invoice_id, cents, refund_id) VALUES (?, ?, ?)",
                          (invoice_id, cents, refund_id))
        self.conn.commit()

    def payments(self, invoice_id: str) -> list[dict]:
        return [dict(r) for r in self.conn.execute(
            "SELECT cents, charge_id FROM payments WHERE invoice_id = ? ORDER BY rowid", (invoice_id,))]

    def refunds(self, invoice_id: str) -> list[dict]:
        return [dict(r) for r in self.conn.execute(
            "SELECT cents, refund_id FROM refunds WHERE invoice_id = ? ORDER BY rowid", (invoice_id,))]
