import re

_NANP = re.compile(r"\+1(\d{3})(\d{3})(\d{4})")


def format_phone(e164: str) -> str:
    m = _NANP.fullmatch(e164)
    return f"+1 ({m.group(1)}) {m.group(2)}-{m.group(3)}" if m else e164
