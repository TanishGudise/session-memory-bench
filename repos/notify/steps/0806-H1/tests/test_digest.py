from notify.digest import send_weekly_digest


def test_digest(email_provider, ana):
    send_weekly_digest(email_provider, ana, ["3 orders shipped", "1 refund"])
    assert email_provider.sent[0]["body"] == "Hi Ana, here is your week: 3 orders shipped; 1 refund"


def test_empty_week(email_provider, ana):
    assert send_weekly_digest(email_provider, ana, []) is None
    assert email_provider.sent == []
