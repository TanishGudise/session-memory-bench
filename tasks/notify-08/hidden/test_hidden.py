from notify.stats import bounce_rate


def test_func_rate():
    events = [{"type": "delivered"}] * 5 + [{"type": "bounced"}] * 2 + [{"type": "complaint"}] * 3
    assert bounce_rate(events) == round(2 / 7, 4)


def test_func_empty():
    assert bounce_rate([]) == 0.0
    assert bounce_rate([{"type": "complaint"}]) == 0.0
