from notify.account import send_password_reset
from notify.models import User
from notify.providers import FakeEmailProvider

LINK = "https://larkspur.example/reset/abc"


def _send(locale):
    p = FakeEmailProvider()
    send_password_reset(p, User(id="u1", email="u1@example.com", locale=locale), LINK)
    assert len(p.sent) == 1 and p.sent[0]["to"] == "u1@example.com"
    return p.sent[0]["body"]


def test_func_english_and_french():
    assert _send("en") == f"Reset your Larkspur password: {LINK}"
    assert _send("fr") == f"Réinitialisez votre mot de passe Larkspur : {LINK}"


def test_func_fallback_to_english():
    assert _send("pt") == f"Reset your Larkspur password: {LINK}"


def test_lesson_german_users_get_formal_template():
    assert _send("de") == f"Setzen Sie Ihr Larkspur-Passwort zurück: {LINK}"
