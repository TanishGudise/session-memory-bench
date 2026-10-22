import logging

from notify.email import send_email


def test_send_email(email_provider, ana, caplog):
    caplog.set_level(logging.INFO)
    msg_id = send_email(email_provider, ana, "welcome", {})
    assert email_provider.sent == [{"id": msg_id, "to": "ana@example.com", "body": "Welcome to Larkspur, Ana!", "headers": {}}]
    assert "ana@example.com" not in caplog.text
