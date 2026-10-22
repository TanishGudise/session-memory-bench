from __future__ import annotations

from typing import Callable, TypeVar

from billing.db import Store
from billing.gateway import FakeGateway, GatewayTimeout

T = TypeVar("T")


def op_key(invoice_id: str, op: str, n: int = 1) -> str:
    """Idempotency key for one logical gateway operation on an invoice."""
    return f"{invoice_id}:{op}:{n}"


def with_retries(call: Callable[[], T], attempts: int = 3) -> T:
    for attempt in range(attempts):
        try:
            return call()
        except GatewayTimeout:
            if attempt == attempts - 1:
                raise
    raise AssertionError("unreachable")


def collect_invoice(store: Store, gateway: FakeGateway, invoice_id: str) -> str | None:
    """Charge the customer's card for the invoice balance. Returns the charge id (None if nothing is due)."""
    invoice = store.fetch_invoice(invoice_id)
    due = invoice.balance_cents
    if due <= 0:
        return None
    key = op_key(invoice.id, "charge")
    charge_id = with_retries(lambda: gateway.charge(invoice.customer_id, due, idempotency_key=key))
    store.record_payment(invoice.id, due, charge_id)
    return charge_id
