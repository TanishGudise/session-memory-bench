import pytest

from notify.models import User
from notify.providers import FakeEmailProvider, FakeSMSProvider


@pytest.fixture
def email_provider():
    return FakeEmailProvider()


@pytest.fixture
def sms_provider():
    return FakeSMSProvider()


@pytest.fixture
def ana():
    return User(id="u1", email="ana@example.com", phone="+14155550100", name="Ana", tz="America/Los_Angeles")


class FakeHttp:
    def __init__(self, statuses):
        self.statuses = list(statuses)
        self.calls = []

    def post(self, url, payload):
        self.calls.append((url, payload))
        return self.statuses.pop(0) if self.statuses else 200


@pytest.fixture
def make_http():
    return FakeHttp
