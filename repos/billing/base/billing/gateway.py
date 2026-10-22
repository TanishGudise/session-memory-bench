"""Client for the card gateway. Tests use FakeGateway, which behaves like production for the cases we model."""

from __future__ import annotations


class GatewayError(Exception):
    pass


class GatewayTimeout(GatewayError):
    """We stopped waiting. The gateway may or may not have processed the request."""


class FakeGateway:
    def __init__(self):
        self.charges: dict[str, dict] = {}
        self.refunds: dict[str, dict] = {}
        self._by_key: dict[str, str] = {}
        self._n = 0
        # The next N writes are processed by the gateway but our client times out before the answer arrives.
        self.timeout_after_commit = 0

    def _write(self, table: dict, prefix: str, payload: dict, idempotency_key: str | None) -> str:
        if idempotency_key is not None and idempotency_key in self._by_key:
            result = self._by_key[idempotency_key]
        else:
            self._n += 1
            result = f"{prefix}_{self._n:05d}"
            table[result] = {"id": result, **payload}
            if idempotency_key is not None:
                self._by_key[idempotency_key] = result
        if self.timeout_after_commit > 0:
            self.timeout_after_commit -= 1
            raise GatewayTimeout(f"no response from gateway for {prefix}")
        return result

    def charge(self, customer_id: str, cents: int, idempotency_key: str | None = None) -> str:
        if cents <= 0:
            raise GatewayError("amount must be positive")
        return self._write(self.charges, "ch", {"customer_id": customer_id, "cents": cents}, idempotency_key)

    def refund(self, customer_id: str, cents: int, idempotency_key: str | None = None) -> str:
        if cents <= 0:
            raise GatewayError("amount must be positive")
        return self._write(self.refunds, "re", {"customer_id": customer_id, "cents": cents}, idempotency_key)
