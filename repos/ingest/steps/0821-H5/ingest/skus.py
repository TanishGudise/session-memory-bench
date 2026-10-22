def normalize_sku(raw: str) -> str:
    """Partner systems disagree on case and whitespace: compare and store SKUs trimmed and upper-case."""
    return raw.strip().upper()
