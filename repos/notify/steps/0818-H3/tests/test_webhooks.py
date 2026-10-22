import pytest

from notify.webhooks import WebhookFailed, deliver


def test_deliver(make_http):
    assert deliver(make_http([200]), "https://p.example/hook", {"a": 1}) == 200


def test_retries_server_errors(make_http):
    sleeps = []
    http = make_http([503, 502, 200])
    assert deliver(http, "https://p.example/hook", {}, sleep=sleeps.append) == 200
    assert len(http.calls) == 3 and sleeps == [2, 2]


def test_gives_up(make_http):
    sleeps = []
    with pytest.raises(WebhookFailed):
        deliver(make_http([503] * 5), "https://p.example/hook", {}, sleep=sleeps.append)
    assert sleeps == [2, 2]
