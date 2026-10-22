"""Provider clients. Tests use the fakes, which record what we sent."""

from __future__ import annotations


class ProviderUnavailable(Exception):
    pass


class FakeEmailProvider:
    def __init__(self):
        self.sent: list[dict] = []

    def send(self, to: str, body: str, headers: dict | None = None) -> str:
        msg_id = f"em_{len(self.sent) + 1:04d}"
        self.sent.append({"id": msg_id, "to": to, "body": body, "headers": dict(headers or {})})
        return msg_id


class FakeSMSProvider:
    def __init__(self):
        self.sent: list[dict] = []
        self.fail_next = 0  # the next N sends raise ProviderUnavailable

    def send(self, to: str, body: str) -> str:
        if self.fail_next > 0:
            self.fail_next -= 1
            raise ProviderUnavailable("sms provider unavailable")
        msg_id = f"sm_{len(self.sent) + 1:04d}"
        self.sent.append({"id": msg_id, "to": to, "body": body})
        return msg_id
