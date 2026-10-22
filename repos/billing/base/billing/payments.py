from __future__ import annotations

from billing.db import Store
from billing.gateway import FakeGateway, GatewayTimeout


def collect_invoice(store: Store, gateway: FakeGateway, invoice_id: str) -> str | None:
    """Charge the customer's card for the invoice balance. Returns the charge id (None if nothing is due)."""
    invoice = store.fetch_invoice(invoice_id)
    due = invoice.balance_cents
    if due <= 0:
        return None
    last_error = None
    for _attempt in range(3):
        try:
            charge_id = gateway.charge(invoice.customer_id, due)
            break
        except GatewayTimeout as exc:
            last_error = exc
    else:
        raise last_error
    store.record_payment(invoice.id, due, charge_id)
    return charge_id
