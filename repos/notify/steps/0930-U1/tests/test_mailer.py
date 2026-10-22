from notify.mailer import dispatch
from notify.models import User


def test_transactional(email_provider, ana):
    dispatch(email_provider, ana, "welcome", {})
    assert email_provider.sent[0]["headers"] == {}


def test_marketing_has_unsubscribe_headers(email_provider, ana):
    dispatch(email_provider, ana, "newsletter", {"body": "News"}, category="marketing")
    assert email_provider.sent[0]["headers"]["List-Unsubscribe"] == "<https://larkspur.example/u/u1/marketing>"


def test_marketing_skips_opted_out(email_provider):
    user = User(id="u9", email="x@example.com", marketing_opt_out=True)
    assert dispatch(email_provider, user, "newsletter", {"body": "News"}, category="marketing") is None
    assert email_provider.sent == []
