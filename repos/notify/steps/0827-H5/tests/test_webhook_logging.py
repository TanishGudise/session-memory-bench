import logging

from notify.webhooks import deliver


def test_attempts_are_logged_without_pii(make_http, caplog):
    caplog.set_level(logging.INFO)
    deliver(make_http([503, 200]), "https://p.example/hook", {"email": "ana@example.com"}, sleep=lambda s: None)
    assert caplog.text.count("webhook_attempt") == 2
    assert "ana@example.com" not in caplog.text
