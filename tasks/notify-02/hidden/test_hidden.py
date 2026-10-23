from notify.models import User
from notify.orders import send_delivery_window_sms
from notify.providers import FakeSMSProvider

USER = User(id="u1", phone="+14155550100")
URL = "https://track.larkspur.example/A-77?ref=sms"


def test_func_short_order():
    p = FakeSMSProvider()
    msg_id = send_delivery_window_sms(p, USER, {"id": "A-77", "window": "tomorrow 9-11am", "items": ["Mug", "Kettle"],
                                                "tracking_url": URL})
    assert p.sent == [{"id": msg_id, "to": "+14155550100",
                       "body": f"Your order A-77 arrives tomorrow 9-11am: Mug, Kettle. Track: {URL}"}]


def test_func_medium_order_sent_whole():
    p = FakeSMSProvider()
    items = [f"Stoneware mug in colour no. {i}" for i in range(8)]  # about 330 characters in total
    send_delivery_window_sms(p, USER, {"id": "A-78", "window": "Friday 2-4pm", "items": items, "tracking_url": URL})
    body = p.sent[0]["body"]
    assert 300 < len(body) <= 480
    assert body == f"Your order A-78 arrives Friday 2-4pm: {', '.join(items)}. Track: {URL}"


def test_lesson_long_order_fits_and_keeps_link():
    p = FakeSMSProvider()
    items = [f"Ceramic espresso cup no. {i}" for i in range(60)]
    send_delivery_window_sms(p, USER, {"id": "A-77", "window": "tomorrow 9-11am", "items": items, "tracking_url": URL})
    assert len(p.sent) == 1
    body = p.sent[0]["body"]
    assert len(body) <= 480
    assert body.startswith("Your order A-77 arrives tomorrow 9-11am: Ceramic espresso cup no. 0")
    assert body.endswith(URL)
