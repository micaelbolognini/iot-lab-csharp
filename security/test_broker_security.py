import shutil
import socket
import subprocess
import threading
import time
from pathlib import Path

import paho.mqtt.client as mqtt
import pytest

HERE = Path(__file__).parent
MOSQUITTO = shutil.which("mosquitto")
TOPIC_TEMP = "fabrik/hall1/maskin3/temperatur"
TOPIC_CMD = "fabrik/hall1/maskin3/kommando"
DEVICES = ["gateway-py", "gateway-cs", "monitor"]


def start_broker(out, port):
    if MOSQUITTO is None:
        pytest.skip("mosquitto is not on PATH")
    conf = out / f"mosquitto.{port}.conf"
    conf.write_text((out / "mosquitto.conf").read_text().replace("8883", str(port)))
    proc = subprocess.Popen([MOSQUITTO, "-c", str(conf)], stderr=subprocess.PIPE)
    for _ in range(50):
        with socket.socket() as s:
            if s.connect_ex(("127.0.0.1", port)) == 0:
                return proc
        time.sleep(0.1)
    raise RuntimeError("broker did not start")


def stop_broker(proc):
    proc.terminate()
    proc.wait()


@pytest.fixture(scope="module")
def broker(tmp_path_factory):
    out = tmp_path_factory.mktemp("sec")
    subprocess.run([str(HERE / "setup.sh"), str(out)], check=True, capture_output=True)
    proc = start_broker(out, 18883)
    yield out, 18883
    stop_broker(proc)


def client(out, device=None, ca=True):
    c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    if ca:
        kwargs = {"ca_certs": str(out / "ca.crt")}
        if device:
            kwargs["certfile"] = str(out / "devices" / f"{device}.crt")
            kwargs["keyfile"] = str(out / "devices" / f"{device}.key")
        c.tls_set(**kwargs)
    return c


def connect_rc(c, port):
    result = {}
    done = threading.Event()

    def on_connect(cl, ud, flags, reason, props):
        result["rc"] = reason
        done.set()

    c.on_connect = on_connect
    c.connect("127.0.0.1", port)
    c.loop_start()
    ok = done.wait(3)
    c.loop_stop()
    c.disconnect()
    return result.get("rc") if ok else None


def refused(c, port):
    try:
        rc = connect_rc(c, port)
    except Exception:
        return True
    return rc is None or rc.is_failure


def test_plaintext_connection_is_refused(broker):
    out, port = broker
    assert refused(client(out, ca=False), port)


def test_tls_without_client_certificate_is_refused(broker):
    out, port = broker
    assert refused(client(out), port)


@pytest.mark.parametrize("device", DEVICES)
def test_each_device_certificate_connects(broker, device):
    out, port = broker
    rc = connect_rc(client(out, device), port)
    assert rc is not None and not rc.is_failure


def test_certificate_from_another_ca_is_refused(broker, tmp_path):
    out, port = broker
    other = tmp_path / "other"
    subprocess.run([str(HERE / "setup.sh"), str(other)], check=True, capture_output=True)
    c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    c.tls_set(
        ca_certs=str(out / "ca.crt"),
        certfile=str(other / "devices" / "gateway-py.crt"),
        keyfile=str(other / "devices" / "gateway-py.key"),
    )
    assert refused(c, port)


def test_server_with_untrusted_ca_is_refused(broker, tmp_path):
    out, port = broker
    other = tmp_path / "other"
    subprocess.run([str(HERE / "setup.sh"), str(other)], check=True, capture_output=True)
    c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    c.tls_set(
        ca_certs=str(other / "ca.crt"),
        certfile=str(out / "devices" / "gateway-py.crt"),
        keyfile=str(out / "devices" / "gateway-py.key"),
    )
    assert refused(c, port)


def collect(out, port, device, topic):
    got = []
    c = client(out, device)
    c.on_message = lambda cl, ud, msg: got.append(msg.payload.decode())
    c.on_connect = lambda cl, ud, f, r, p: cl.subscribe(topic, qos=1)
    c.connect("127.0.0.1", port)
    c.loop_start()
    time.sleep(0.5)
    return c, got


def publish_as(out, port, device, topic, payload):
    c = client(out, device)
    c.connect("127.0.0.1", port)
    c.loop_start()
    c.publish(topic, payload, qos=1).wait_for_publish(2)
    c.loop_stop()
    c.disconnect()


@pytest.mark.parametrize("gateway", ["gateway-py", "gateway-cs"])
def test_gateway_may_publish_telemetry_monitor_receives(broker, gateway):
    out, port = broker
    sub, got = collect(out, port, "monitor", "fabrik/#")
    publish_as(out, port, gateway, TOPIC_TEMP, f"21.5-{gateway}")
    time.sleep(0.5)
    sub.loop_stop()
    assert f"21.5-{gateway}" in got


@pytest.mark.parametrize("gateway", ["gateway-py", "gateway-cs"])
def test_gateway_may_not_publish_commands(broker, gateway):
    out, port = broker
    sub, got = collect(out, port, "monitor", "fabrik/#")
    publish_as(out, port, gateway, TOPIC_CMD, f"stop-{gateway}")
    time.sleep(0.5)
    sub.loop_stop()
    assert f"stop-{gateway}" not in got


def test_monitor_may_publish_commands_gateway_receives(broker):
    out, port = broker
    sub, got = collect(out, port, "gateway-py", TOPIC_CMD)
    publish_as(out, port, "monitor", TOPIC_CMD, "stop")
    time.sleep(0.5)
    sub.loop_stop()
    assert "stop" in got


def test_monitor_may_not_publish_telemetry(broker):
    out, port = broker
    sub, got = collect(out, port, "monitor", "fabrik/#")
    publish_as(out, port, "monitor", TOPIC_TEMP, "99")
    time.sleep(0.5)
    sub.loop_stop()
    assert "99" not in got


def test_revoked_certificate_is_refused_while_others_still_connect(tmp_path):
    out = tmp_path / "sec"
    subprocess.run([str(HERE / "setup.sh"), str(out)], check=True, capture_output=True)
    subprocess.run([str(HERE / "revoke.sh"), str(out), "gateway-cs"], check=True, capture_output=True)
    proc = start_broker(out, 18884)
    try:
        assert refused(client(out, "gateway-cs"), 18884)
        for device in ["gateway-py", "monitor"]:
            rc = connect_rc(client(out, device), 18884)
            assert rc is not None and not rc.is_failure
    finally:
        stop_broker(proc)


def test_revoking_unknown_device_fails(tmp_path):
    out = tmp_path / "sec"
    subprocess.run([str(HERE / "setup.sh"), str(out)], check=True, capture_output=True)
    result = subprocess.run([str(HERE / "revoke.sh"), str(out), "finns-inte"], capture_output=True)
    assert result.returncode != 0


def test_config_requires_client_certificates_and_has_no_passwords_or_plaintext(broker):
    out, port = broker
    conf = (out / "mosquitto.conf").read_text()
    assert "1883" not in conf
    assert "allow_anonymous false" in conf
    assert "require_certificate true" in conf
    assert "use_identity_as_username true" in conf
    assert "crlfile" in conf
    assert "password_file" not in conf
    assert not (out / "passwd").exists()
    assert not (out / "secrets.env").exists()


def test_private_keys_are_only_readable_by_owner(broker):
    out, port = broker
    keys = [out / "ca.key", out / "server.key", *(out / "devices").glob("*.key")]
    assert len(keys) == 2 + len(DEVICES)
    for key in keys:
        assert key.stat().st_mode & 0o077 == 0, key
