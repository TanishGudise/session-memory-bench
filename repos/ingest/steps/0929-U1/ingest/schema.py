"""The record every feed produces.

source       feed name, e.g. "acme"
external_id  the partner's id for the row
item_code    product code (schema v2, 2026-09-29; was `sku`)
qty          int units
amount       str or None: the partner's exact decimal string ("12.50"); finance reconciles on it, so keep it as received
occurred_at  date (date-only feeds) or timezone-aware datetime in UTC
exported_at  str or None: when the partner exported the file, as received
"""

RECORD_FIELDS = ("source", "external_id", "item_code", "qty", "amount", "occurred_at", "exported_at")


def validate_record(record: dict) -> None:
    missing = [f for f in RECORD_FIELDS if f not in record]
    if missing:
        raise ValueError(f"record missing fields: {missing}")
    if "sku" in record:
        raise ValueError("schema v2: use item_code, not sku")
    if not isinstance(record["qty"], int):
        raise ValueError("qty must be an int")
    if record["amount"] is not None and not isinstance(record["amount"], str):
        raise ValueError("amount must be the partner's decimal string")
