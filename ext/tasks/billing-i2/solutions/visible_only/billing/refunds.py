from __future__ import annotations

from billing.db import Store
from billing.gateway import FakeGateway
from billing.payments import op_key, with_retries


def refund_invoice(store: Store, gateway: FakeGateway, invoice_id: str, cents: int, requested_by: str,
                   approved_by: str | None = None) -> str:
    """Refund `cents` of the invoice to its customer. Returns the gateway refund id."""
    invoice = store.get_invoice(invoice_id)
    refund_id = gateway.refund(invoice.customer_id, cents)
    store.record_refund(invoice.id, cents, refund_id)
    return refund_id
