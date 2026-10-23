import logging

from notify.webhooks import deliver


class Http:
    def post(self, url, payload):
        return 200


def test_lesson_payload_redacted(caplog):
    caplog.set_level(logging.INFO)
    deliver(Http(), "https://p.example/hook", {"email": "ana@example.com", "phone": "+14155550100"}, sleep=lambda s: None)
    assert caplog.text and "ana@example.com" not in caplog.text and "4155550100" not in caplog.text
