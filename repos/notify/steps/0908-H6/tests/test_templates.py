import pytest

from notify.templates import TemplateMissing, render


def test_render_locale():
    assert render("welcome", "de", {"name": "Jan"}) == "Willkommen bei Larkspur, Jan!"


def test_render_falls_back_to_english():
    assert render("welcome", "pt", {"name": "Rui"}) == "Welcome to Larkspur, Rui!"


def test_missing_template():
    with pytest.raises(TemplateMissing):
        render("nope", "en", {})


def test_default_value():
    assert render("welcome", "en", {"name": ""}) == "Welcome to Larkspur, there!"
