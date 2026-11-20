import json

from sparkplug_node import Node
from sparkplug_payload import BOOLEAN, DOUBLE, INT64, STRING, decode, encode

NOW = 1700000000.0


def node():
    return Node(group="fabrik", node="hall1", device="maskin3", clock=lambda: NOW)


def parsed(messages):
    return [(topic, decode(payload)) for topic, payload, _ in messages]


def metrics(payload):
    return {m["name"]: m["value"] for m in payload["metrics"]}


def online(n):
    n.on_uns("status", json.dumps({"value": "Stopped"}))
    n.on_uns("antal", json.dumps({"value": 3}))
    n.on_uns("temperatur", json.dumps({"avg": 20.5}))
    return n.on_uns("gateway", "online")


def test_will_is_an_ndeath_carrying_the_bdseq_of_the_session():
    n = node()
    n.new_session()
    topic, payload = n.will()
    assert topic == "spBv1.0/fabrik/NDEATH/hall1"
    assert metrics(decode(payload)) == {"bdSeq": 0}
    assert "seq" not in decode(payload)


def test_bdseq_increases_each_session_and_wraps_at_256():
    n = node()
    for _ in range(257):
        n.new_session()
    assert metrics(decode(n.will()[1])) == {"bdSeq": 0}


def test_nbirth_starts_at_seq_0_with_the_same_bdseq_as_the_will():
    n = node()
    n.new_session()
    [(topic, payload)] = parsed(n.node_birth())
    assert topic == "spBv1.0/fabrik/NBIRTH/hall1"
    assert payload["seq"] == 0
    assert metrics(payload) == {"bdSeq": 0, "Node Control/Rebirth": False}
    assert payload["timestamp"] == 1700000000000


def test_dbirth_lists_every_metric_with_current_values_when_the_gateway_comes_online():
    n = node()
    n.new_session()
    n.node_birth()
    [(topic, payload)] = parsed(online(n))
    assert topic == "spBv1.0/fabrik/DBIRTH/hall1/maskin3"
    assert payload["seq"] == 1
    assert metrics(payload) == {"Temperatur": 20.5, "Status": "Stopped", "Antal": 3, "Kor": False}
    types = {m["name"]: m["datatype"] for m in payload["metrics"]}
    assert types == {"Temperatur": DOUBLE, "Status": STRING, "Antal": INT64, "Kor": BOOLEAN}


def test_unknown_values_are_born_as_null():
    n = node()
    n.new_session()
    n.node_birth()
    [(_, payload)] = parsed(n.on_uns("gateway", "online"))
    assert metrics(payload) == {"Temperatur": None, "Status": None, "Antal": None, "Kor": None}


def test_ddata_only_after_birth_and_carries_just_the_changed_metrics():
    n = node()
    n.new_session()
    n.node_birth()
    assert n.on_uns("temperatur", json.dumps({"avg": 21.0})) == []
    online(n)
    [(topic, payload)] = parsed(n.on_uns("temperatur", json.dumps({"avg": 22.25})))
    assert topic == "spBv1.0/fabrik/DDATA/hall1/maskin3"
    assert metrics(payload) == {"Temperatur": 22.25}


def test_status_change_updates_status_and_kor_together():
    n = node()
    n.new_session()
    n.node_birth()
    online(n)
    [(_, payload)] = parsed(n.on_uns("status", json.dumps({"value": "Running"})))
    assert metrics(payload) == {"Status": "Running", "Kor": True}


def test_seq_counts_up_across_messages_and_wraps_at_256():
    n = node()
    n.new_session()
    n.node_birth()
    online(n)
    seqs = []
    for i in range(300):
        [(_, p)] = parsed(n.on_uns("antal", json.dumps({"value": i})))
        seqs.append(p["seq"])
    assert seqs[0] == 2 and seqs[253] == 255 and seqs[254] == 0


def test_gateway_offline_gives_ddeath_and_data_stops():
    n = node()
    n.new_session()
    n.node_birth()
    online(n)
    [(topic, payload)] = parsed(n.on_uns("gateway", "offline"))
    assert topic == "spBv1.0/fabrik/DDEATH/hall1/maskin3"
    assert n.on_uns("antal", json.dumps({"value": 9})) == []


def test_dcmd_kor_becomes_a_start_or_stop_command_on_the_uns():
    n = node()
    cmd = lambda value: encode({"metrics": [{"name": "Kor", "datatype": BOOLEAN, "value": value}]})
    assert n.on_command("spBv1.0/fabrik/DCMD/hall1/maskin3", cmd(True)) == [("fabrik/hall1/maskin3/kommando", b"start", False)]
    assert n.on_command("spBv1.0/fabrik/DCMD/hall1/maskin3", cmd(False)) == [("fabrik/hall1/maskin3/kommando", b"stop", False)]


def test_dcmd_for_another_device_or_metric_is_ignored():
    n = node()
    other = encode({"metrics": [{"name": "Kor", "datatype": BOOLEAN, "value": True}]})
    assert n.on_command("spBv1.0/fabrik/DCMD/hall1/maskin9", other) == []
    wrong = encode({"metrics": [{"name": "Temperatur", "datatype": DOUBLE, "value": 1.0}]})
    assert n.on_command("spBv1.0/fabrik/DCMD/hall1/maskin3", wrong) == []


def test_ncmd_rebirth_resends_nbirth_and_dbirth_with_seq_restarting():
    n = node()
    n.new_session()
    n.node_birth()
    online(n)
    n.on_uns("antal", json.dumps({"value": 1}))
    rebirth = encode({"metrics": [{"name": "Node Control/Rebirth", "datatype": BOOLEAN, "value": True}]})
    out = parsed(n.on_command("spBv1.0/fabrik/NCMD/hall1", rebirth))
    assert [t for t, _ in out] == ["spBv1.0/fabrik/NBIRTH/hall1", "spBv1.0/fabrik/DBIRTH/hall1/maskin3"]
    assert [p["seq"] for _, p in out] == [0, 1]
    assert metrics(out[0][1])["bdSeq"] == 0
