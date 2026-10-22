import pytest

from notify.webhooks import WebhookFailed, deliver


def test_deliver(make_http):
    assert deliver(make_http([200]), "https://p.example/hook", {"a": 1}) == 200


def test_retries_with_backoff(make_http):
    sleeps = []
    http = make_http([503, 502, 500, 200])
    assert deliver(http, "https://p.example/hook", {}, sleep=sleeps.append) == 200
    assert len(http.calls) == 4 and sleeps == [1, 2, 4]


def test_gives_up_after_five(make_http):
    sleeps = []
    http = make_http([503] * 6)
    with pytest.raises(WebhookFailed):
        deliver(http, "https://p.example/hook", {}, sleep=sleeps.append)
    assert len(http.calls) == 5 and sleeps == [1, 2, 4, 8]
