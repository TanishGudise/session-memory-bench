import pytest

from notify.webhooks import WebhookFailed, deliver


def test_deliver(make_http):
    http = make_http([200])
    assert deliver(http, "https://p.example/hook", {"a": 1}) == 200


def test_deliver_server_error(make_http):
    with pytest.raises(WebhookFailed):
        deliver(make_http([503]), "https://p.example/hook", {})
