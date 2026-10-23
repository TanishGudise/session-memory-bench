from __future__ import annotations

from billing.db import Store
from billing.gateway import FakeGateway
from billing.payments import op_key, with_retries

SECOND_APPROVER_OVER_CENTS = 50000


def refund_invoice(store: Store, gateway: FakeGateway, invoice_id: str, cents: int, requested_by: str,
                   approved_by: str | None = None) -> str:
    """Refund `cents` of the invoice to its customer. Returns the gateway refund id."""
    if cents > SECOND_APPROVER_OVER_CENTS and (approved_by is None or approved_by == requested_by):
        raise PermissionError("refunds over $500.00 need a second approver who is not the requester")
    invoice = store.get_invoice(invoice_id)
    key = op_key(invoice.id, "refund", len(store.refunds(invoice.id)) + 1)
    refund_id = with_retries(lambda: gateway.refund(invoice.customer_id, cents, idempotency_key=key))
    store.record_refund(invoice.id, cents, refund_id)
    return refund_id
