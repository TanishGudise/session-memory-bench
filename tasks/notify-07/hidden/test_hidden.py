from notify.phones import format_phone


def test_func_north_american():
    assert format_phone("+14155550100") == "+1 (415) 555-0100"
    assert format_phone("+12125550199") == "+1 (212) 555-0199"


def test_func_other_numbers_unchanged():
    for n in ["+442071838750", "+1415555010", "+141555501000", "4155550100", ""]:
        assert format_phone(n) == n
