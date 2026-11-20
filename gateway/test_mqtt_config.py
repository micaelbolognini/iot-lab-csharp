import pytest

from mqtt_config import mqtt_settings

ENV = {"MQTT_CA": "/x/ca.crt", "MQTT_CERT": "/x/gw.crt", "MQTT_KEY": "/x/gw.key"}


def test_defaults_to_tls_port_on_localhost():
    s = mqtt_settings(ENV)
    assert (s.host, s.port) == ("localhost", 8883)
    assert (s.ca, s.cert, s.key) == ("/x/ca.crt", "/x/gw.crt", "/x/gw.key")


def test_host_and_port_can_be_overridden():
    s = mqtt_settings({**ENV, "MQTT_HOST": "gizmo", "MQTT_PORT": "9000"})
    assert (s.host, s.port) == ("gizmo", 9000)


@pytest.mark.parametrize("missing", ["MQTT_CA", "MQTT_CERT", "MQTT_KEY"])
def test_refuses_to_run_without_tls_and_client_certificate(missing):
    env = {k: v for k, v in ENV.items() if k != missing}
    with pytest.raises(ValueError, match=missing):
        mqtt_settings(env)
