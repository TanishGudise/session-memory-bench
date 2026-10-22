def bounce_rate(events: list[dict]) -> float:
    delivered = sum(1 for e in events if e.get("type") == "delivered")
    bounced = sum(1 for e in events if e.get("type") == "bounced")
    return round(bounced / (delivered + bounced), 4) if delivered + bounced else 0.0
