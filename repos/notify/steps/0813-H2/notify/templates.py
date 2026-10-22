"""Message templates by (name, locale). Rendering falls back to English when a locale has no template."""

from __future__ import annotations

TEMPLATES: dict[tuple[str, str], str] = {
    ("welcome", "en"): "Welcome to Larkspur, {name}!",
    ("welcome", "de"): "Willkommen bei Larkspur, {name}!",
    ("welcome", "de-formal"): "Willkommen bei Larkspur, {name}!",
    ("order_shipped", "en"): "Your order {order_id} has shipped. Track: {url}",
    ("order_shipped", "de"): "Deine Bestellung {order_id} ist unterwegs. Verfolgen: {url}",
    ("order_shipped", "de-formal"): "Ihre Bestellung {order_id} ist unterwegs. Sendungsverfolgung: {url}",
    ("weekly_digest", "en"): "Hi {name}, here is your week: {summary}",
    ("weekly_digest", "de"): "Hallo {name}, hier ist deine Woche: {summary}",
    ("weekly_digest", "de-formal"): "Guten Tag {name}, hier ist Ihre Woche: {summary}",
    ("password_reset", "en"): "Reset your Larkspur password: {link}",
    ("password_reset", "de"): "Setz dein Larkspur-Passwort zurück: {link}",
    ("password_reset", "de-formal"): "Setzen Sie Ihr Larkspur-Passwort zurück: {link}",
    ("password_reset", "fr"): "Réinitialisez votre mot de passe Larkspur : {link}",
}


class TemplateMissing(KeyError):
    pass


def render(name: str, locale: str, ctx: dict) -> str:
    text = TEMPLATES.get((name, locale)) or TEMPLATES.get((name, "en"))
    if text is None:
        raise TemplateMissing(name)
    return text.format(**ctx)
