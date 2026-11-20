from edge import Aggregator, Buffer


def test_aggregator_summarizes_values_and_resets():
    agg = Aggregator()
    for v in [20.0, 22.0, 24.0]:
        agg.add(v)

    assert agg.summary() == {"min": 20.0, "max": 24.0, "avg": 22.0, "n": 3}
    assert agg.summary() is None  # tömd efter summering


def test_aggregator_without_values_gives_none():
    assert Aggregator().summary() is None


def test_buffer_sends_in_order_while_connection_works():
    sent = []
    buf = Buffer(maxlen=10)
    buf.push("a")
    buf.push("b")

    buf.drain(lambda m: sent.append(m) or True)

    assert sent == ["a", "b"]
    assert len(buf) == 0


def test_buffer_keeps_messages_when_send_fails():
    buf = Buffer(maxlen=10)
    buf.push("a")
    buf.push("b")

    buf.drain(lambda m: False)

    assert len(buf) == 2  # inget tappat, skickas när nätet är tillbaka


def test_buffer_drops_oldest_when_full():
    buf = Buffer(maxlen=2)
    for m in ["a", "b", "c"]:
        buf.push(m)
    sent = []

    buf.drain(lambda m: sent.append(m) or True)

    assert sent == ["b", "c"]
