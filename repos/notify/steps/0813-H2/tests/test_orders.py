from notify.orders import send_order_shipped


def test_order_shipped(sms_provider, ana):
    send_order_shipped(sms_provider, ana, {"id": "A-1", "items": ["Mug"], "tracking_url": "https://t.example/A-1"})
    assert sms_provider.sent[0]["to"] == "+14155550100"
    assert sms_provider.sent[0]["body"] == "Your order A-1 has shipped. Track: https://t.example/A-1"


def test_big_order_stays_short(sms_provider, ana):
    items = [f"Item number {i}" for i in range(100)]
    send_order_shipped(sms_provider, ana, {"id": "A-2", "items": items, "tracking_url": "https://t.example/A-2"})
    assert len(sms_provider.sent[0]["body"]) <= 480
