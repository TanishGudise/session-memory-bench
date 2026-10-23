import pytest

from notify.webhooks import WebhookFailed, deliver


class Http:
    def __init__(self, statuses):
        self.statuses = list(statuses)

    def post(self, url, payload):
        return self.statuses.pop(0) if self.statuses else 200


def test_lesson_three_attempts_two_seconds():
    sleeps = []
    with pytest.raises(WebhookFailed):
        deliver(Http([503] * 5), "https://p.example/hook", {}, sleep=sleeps.append)
    assert sleeps == [2, 2]
