import asyncio
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest
from asyncua import Client, ua
from asyncua.ua.uaerrors import BadCertificateRevoked, BadCertificateUntrusted

sys.path.insert(0, str(Path(__file__).parent.parent / "gateway"))
import opcua_config  # noqa: E402
from opcua_config import OpcUaSettings  # noqa: E402

HERE = Path(__file__).parent
ROOT = HERE.parent
PORT = 14840
URL = f"opc.tcp://localhost:{PORT}/iot-lab/"
TEMPERATURE = ["2:Fabrik", "2:Hall1", "2:Maskin3", "2:Temperatur"]


def make_pki(path):
    subprocess.run([str(HERE / "setup.sh"), str(path)], check=True, capture_output=True)
    return path


def start_machine(pki, port=PORT):
    env = {
        **os.environ,
        "OPCUA_PORT": str(port),
        "OPCUA_CERT": str(pki / "opcua" / "machine.crt"),
        "OPCUA_KEY": str(pki / "opcua" / "machine.key"),
        "OPCUA_TRUST": str(pki / "opcua" / "trust"),
        "OPCUA_CRL": str(pki / "opcua" / "crl"),
    }
    proc = subprocess.Popen([sys.executable, str(ROOT / "machine" / "server.py")], env=env, stderr=subprocess.PIPE)
    for _ in range(100):
        if proc.poll() is not None:
            raise RuntimeError(proc.stderr.read().decode())
        with socket.socket() as s:
            if s.connect_ex(("127.0.0.1", port)) == 0:
                return proc
        time.sleep(0.1)
    raise RuntimeError("machine did not start")


def stop(proc):
    proc.terminate()
    proc.wait()


@pytest.fixture(scope="module")
def plant(tmp_path_factory):
    pki = make_pki(tmp_path_factory.mktemp("opcua"))
    proc = start_machine(pki)
    yield pki
    stop(proc)


async def secure_client(pki, device="gateway-py", client_pki=None, url=URL):
    src = client_pki or pki
    settings = OpcUaSettings(
        url=url,
        app=device,
        cert=str(src / "opcua" / f"{device}.crt"),
        key=str(src / "opcua" / f"{device}.key"),
        trust=str(pki / "opcua" / "trust"),
        crl=str(pki / "opcua" / "crl"),
    )
    return await opcua_config.secure_client(settings)


async def read_temperature(client):
    async with client:
        node = await client.nodes.objects.get_child(TEMPERATURE)
        return await node.read_value()


def test_trusted_client_reads_over_encrypted_channel(plant):
    async def go():
        return await read_temperature(await secure_client(plant))

    assert isinstance(asyncio.run(go()), float)


def test_every_gateway_has_an_opcua_identity(plant):
    for device in ("gateway-py", "gateway-cs"):
        assert (plant / "opcua" / f"{device}.crt").exists()
        assert (plant / "opcua" / f"{device}.key").exists()


def test_unsecured_connection_is_refused(plant):
    async def go():
        async with Client(URL) as client:
            await client.nodes.objects.get_child(TEMPERATURE)

    with pytest.raises(ua.UaError, match="No matching endpoints"):
        asyncio.run(go())


def test_client_from_foreign_ca_is_refused(plant, tmp_path):
    foreign = make_pki(tmp_path / "foreign")

    async def go():
        client = await secure_client(plant, client_pki=foreign)
        await read_temperature(client)

    with pytest.raises(BadCertificateUntrusted):
        asyncio.run(go())


def test_revoked_client_is_refused(tmp_path):
    pki = make_pki(tmp_path / "pki")
    subprocess.run([str(HERE / "revoke.sh"), str(pki), "opcua/gateway-cs"], check=True, capture_output=True)
    proc = start_machine(pki, port=PORT + 1)
    try:
        async def go():
            client = await secure_client(pki, device="gateway-cs", url=URL.replace(str(PORT), str(PORT + 1)))
            await read_temperature(client)

        with pytest.raises(BadCertificateRevoked):
            asyncio.run(go())
    finally:
        stop(proc)
