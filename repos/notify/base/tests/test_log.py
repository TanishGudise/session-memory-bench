from notify.log import redact


def test_redact():
    assert redact("mail ana@example.com or call +1 415 555 0100") == "mail [email] or call [phone]"
    assert redact({"to": "+14155550100", "n": 3}) == {"to": "[phone]", "n": 3}
