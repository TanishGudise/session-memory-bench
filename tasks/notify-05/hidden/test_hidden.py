from notify.models import User
from notify.newsletter import send_newsletter
from notify.providers import FakeEmailProvider

BODY = "October: new mugs are in."


def test_func_sends_to_users_with_email():
    p = FakeEmailProvider()
    users = [User(id="a", email="a@example.com"), User(id="b", email="b@example.com"), User(id="c")]
    assert send_newsletter(p, users, BODY) == ["a", "b"]
    assert [m["to"] for m in p.sent] == ["a@example.com", "b@example.com"]
    assert all(m["body"].startswith(BODY) for m in p.sent)


def test_lesson_skips_opted_out_users():
    p = FakeEmailProvider()
    users = [User(id="a", email="a@example.com", marketing_opt_out=True), User(id="b", email="b@example.com")]
    assert send_newsletter(p, users, BODY) == ["b"]
    assert [m["to"] for m in p.sent] == ["b@example.com"]


def test_lesson_has_list_unsubscribe_header():
    p = FakeEmailProvider()
    send_newsletter(p, [User(id="b", email="b@example.com")], BODY)
    assert p.sent[0]["headers"].get("List-Unsubscribe") == "<https://larkspur.example/u/b/marketing>"


def test_diag_sent_without_unsubscribe_header():
    p = FakeEmailProvider()
    send_newsletter(p, [User(id="b", email="b@example.com")], BODY)
    assert p.sent and "List-Unsubscribe" not in p.sent[0]["headers"]
