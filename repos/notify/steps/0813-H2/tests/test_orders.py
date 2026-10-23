from notify.orders import send_order_shipped


def test_order_shipped(sms_provider, ana):
    send_order_shipped(sms_provider, ana, {"id": "A-1", "items": ["Mug"], "tracking_url": "https://t.example/A-1"})
    assert sms_provider.sent[0]["to"] == "+14155550100"
    assert sms_provider.sent[0]["body"] == "Your order A-1 has shipped. Track: https://t.example/A-1"

