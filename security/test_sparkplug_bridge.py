import json
import os
import subprocess
import sys
import time
from pathlib import Path

import paho.mqtt.client as mqtt
import pytest

from test_broker_security import client, start_broker, stop_broker

HERE = Path(__file__).parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "sparkplug"))
from sparkplug_payload import BOOLEAN, decode, encode  # noqa: E402

PORT = 18885
UNS = "fabrik/hall1/maskin3"
SP = "spBv1.0/fabrik"


def connect(out, device):
    c = client(out, device)
    c.connect("127.0.0.1", PORT)
    c.loop_start()
    return c


def publish(c, topic, payload, retain=False):
    c.publish(topic, payload, qos=1, retain=retain).wait_for_publish(2)


def spy_on(out, device, topic):
    seen = []
    c = client(out, device)
    c.on_message = lambda cl, ud, msg: seen.append((msg.topic, msg.payload))
    c.on_connect = lambda cl, ud, flags, reason, props: cl.subscribe(topic, qos=1)
    c.connect("127.0.0.1", PORT)
    c.loop_start()
    return c, seen


def wait_for(seen, topic, timeout=8, after=0):
    end = time.time() + timeout
    while time.time() < end:
        for i, (t, payload) in enumerate(list(seen)[after:], start=after):
            if t == topic:
                return i, payload
        time.sleep(0.05)
    raise AssertionError(f"no message on {topic}; saw {[t for t, _ in seen]}")


def metrics(payload):
    return {m["name"]: m["value"] for m in decode(payload)["metrics"]}


@pytest.fixture(scope="module")
def stack(tmp_path_factory):
    out = tmp_path_factory.mktemp("sparkplug")
    subprocess.run([str(HERE / "setup.sh"), str(out)], check=True, capture_output=True)
    broker = start_broker(out, PORT)
    gateway = connect(out, "gateway-py")
    publish(gateway, f"{UNS}/status", json.dumps({"value": "Stopped"}), retain=True)
    publish(gateway, f"{UNS}/antal", json.dumps({"value": 3}), retain=True)
    publish(gateway, f"{UNS}/temperatur", json.dumps({"avg": 20.5}))
    publish(gateway, f"{UNS}/gateway", "online", retain=True)
    host, seen = spy_on(out, "monitor", "spBv1.0/#")
    time.sleep(0.5)
    env = {**os.environ, "MQTT_HOST": "127.0.0.1", "MQTT_PORT": str(PORT), "MQTT_CA": str(out / "ca.crt"),
           "MQTT_CERT": str(out / "devices" / "sparkplug-bridge.crt"), "MQTT_KEY": str(out / "devices" / "sparkplug-bridge.key")}
    bridge = subprocess.Popen([sys.executable, str(ROOT / "sparkplug" / "bridge.py")], env=env, stderr=subprocess.PIPE)
    yield out, gateway, host, seen, bridge
    bridge.kill()
    bridge.wait()
    for c in (gateway, host):
        c.loop_stop()
    stop_broker(broker)


def test_bridge_announces_node_then_device_with_current_values(stack):
    out, gateway, host, seen, bridge = stack
    i, nbirth = wait_for(seen, f"{SP}/NBIRTH/hall1")
    assert decode(nbirth)["seq"] == 0 and metrics(nbirth)["bdSeq"] == 0
    _, dbirth = wait_for(seen, f"{SP}/DBIRTH/hall1/maskin3", after=i)
    assert metrics(dbirth) == {"Temperatur": None, "Status": "Stopped", "Antal": 3, "Kor": False}


def test_uns_changes_become_ddata(stack):
    out, gateway, host, seen, bridge = stack
    wait_for(seen, f"{SP}/DBIRTH/hall1/maskin3")
    before = len(seen)
    publish(gateway, f"{UNS}/temperatur", json.dumps({"avg": 23.75}))
    _, ddata = wait_for(seen, f"{SP}/DDATA/hall1/maskin3", after=before)
    assert metrics(ddata) == {"Temperatur": 23.75}


def test_dcmd_from_the_host_becomes_a_uns_command(stack):
    out, gateway, host, seen, bridge = stack
    spy, commands = spy_on(out, "gateway-py", f"{UNS}/kommando")
    time.sleep(0.5)
    payload = encode({"metrics": [{"name": "Kor", "datatype": BOOLEAN, "value": True}]})
    publish(host, f"{SP}/DCMD/hall1/maskin3", payload)
    _, command = wait_for(commands, f"{UNS}/kommando")
    assert command == b"start"
    spy.loop_stop()


def test_rebirth_request_makes_the_node_announce_again(stack):
    out, gateway, host, seen, bridge = stack
    before = len(seen)
    payload = encode({"metrics": [{"name": "Node Control/Rebirth", "datatype": BOOLEAN, "value": True}]})
    publish(host, f"{SP}/NCMD/hall1", payload)
    i, _ = wait_for(seen, f"{SP}/NBIRTH/hall1", after=before)
    wait_for(seen, f"{SP}/DBIRTH/hall1/maskin3", after=i)


def test_the_bridge_may_not_publish_uns_telemetry(stack):
    out, gateway, host, seen, bridge = stack
    spy, got = spy_on(out, "monitor", f"{UNS}/temperatur")
    time.sleep(0.5)
    rogue = connect(out, "sparkplug-bridge")
    publish(rogue, f"{UNS}/temperatur", json.dumps({"avg": 99.0}))
    publish(gateway, f"{UNS}/temperatur", json.dumps({"avg": 77.0}))  # control: the gateway may publish it
    wait_for(got, f"{UNS}/temperatur")
    time.sleep(0.5)
    averages = [json.loads(p)["avg"] for _, p in got]
    assert averages == [77.0]
    rogue.loop_stop()
    spy.loop_stop()


def test_killing_the_bridge_makes_the_broker_publish_ndeath(stack):
    out, gateway, host, seen, bridge = stack
    before = len(seen)
    bridge.kill()
    _, ndeath = wait_for(seen, f"{SP}/NDEATH/hall1", after=before)
    assert metrics(ndeath) == {"bdSeq": 0}
