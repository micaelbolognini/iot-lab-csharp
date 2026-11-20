import pytest

from opcua_config import opcua_settings

ENV = {
    "OPCUA_CERT": "/x/gw.crt",
    "OPCUA_KEY": "/x/gw.key",
    "OPCUA_TRUST": "/x/trust",
    "OPCUA_CRL": "/x/crl",
}


def test_defaults_to_local_machine_and_python_gateway_identity():
    s = opcua_settings(ENV)
    assert s.url == "opc.tcp://localhost:4840/iot-lab/"
    assert s.app == "gateway-py"
    assert (s.cert, s.key, s.trust, s.crl) == ("/x/gw.crt", "/x/gw.key", "/x/trust", "/x/crl")


def test_url_and_app_can_be_overridden():
    s = opcua_settings({**ENV, "OPCUA_URL": "opc.tcp://plc:4840/x/", "OPCUA_APP": "gateway-x"})
    assert (s.url, s.app) == ("opc.tcp://plc:4840/x/", "gateway-x")


@pytest.mark.parametrize("missing", sorted(ENV))
def test_refuses_to_run_without_opcua_certificates(missing):
    env = {k: v for k, v in ENV.items() if k != missing}
    with pytest.raises(ValueError, match=missing):
        opcua_settings(env)
