"""Simulerad maskin med OPC UA-server, som en PLC på fabriksgolvet.

Adressrymd:
  Objects/Fabrik/Hall1/Maskin3
    Temperatur (Double, °C)   stiger när maskinen går, sjunker när den står
    Varvtal    (Int32, rpm)
    Status     (String)       "Running" / "Stopped"
    Antal      (Int64)        tillverkade detaljer
    Start(), Stop()           metoder klienten kan anropa
"""
import asyncio
import logging
import os
import random
from pathlib import Path

from asyncua import Server, ua
from asyncua.common.methods import uamethod
from asyncua.crypto.truststore import TrustStore
from asyncua.crypto.validator import CertificateValidator, CertificateValidatorOptions

NAMESPACE = "urn:iot-lab:fabrik"
APPLICATION_URI = "urn:iot-lab:machine"


def security_env(env=os.environ):
    for key in ("OPCUA_CERT", "OPCUA_KEY", "OPCUA_TRUST", "OPCUA_CRL"):
        if not env.get(key):
            raise ValueError(f"{key} must be set (encrypted OPC UA with client certificates is mandatory)")
    return {k: Path(env[k]) for k in ("OPCUA_CERT", "OPCUA_KEY", "OPCUA_TRUST", "OPCUA_CRL")}


async def secure(server, paths):
    await server.set_application_uri(APPLICATION_URI)
    await server.load_certificate(paths["OPCUA_CERT"], "pem")
    await server.load_private_key(paths["OPCUA_KEY"], format="pem")
    server.set_security_policy([ua.SecurityPolicyType.Basic256Sha256_SignAndEncrypt])
    store = TrustStore([paths["OPCUA_TRUST"]], [paths["OPCUA_CRL"]])
    await store.load()
    options = CertificateValidatorOptions.TRUSTED_VALIDATION | CertificateValidatorOptions.PEER_CLIENT
    server.set_certificate_validator(CertificateValidator(options, store).validate)


async def main():
    paths = security_env()
    server = Server()
    await server.init()
    server.set_endpoint(f"opc.tcp://0.0.0.0:{os.environ.get('OPCUA_PORT', '4840')}/iot-lab/")
    server.set_server_name("IoT-labb Maskin3")
    await secure(server, paths)

    ns = await server.register_namespace(NAMESPACE)
    fabrik = await server.nodes.objects.add_folder(ns, "Fabrik")
    hall = await fabrik.add_folder(ns, "Hall1")
    maskin = await hall.add_object(ns, "Maskin3")

    temperatur = await maskin.add_variable(ns, "Temperatur", 20.0)
    varvtal = await maskin.add_variable(ns, "Varvtal", 0, ua.VariantType.Int32)
    status = await maskin.add_variable(ns, "Status", "Stopped")
    antal = await maskin.add_variable(ns, "Antal", 0, ua.VariantType.Int64)
    borvarde = await maskin.add_variable(ns, "Borvarde", 1500, ua.VariantType.Int32)
    await borvarde.set_writable()
    kor = await maskin.add_variable(ns, "Kor", False)
    await kor.set_writable()  # clients write tags, they can't call methods

    state = {"cmd": None}

    @uamethod
    def start(parent):
        state["cmd"] = True
        return "startad"

    @uamethod
    def stop(parent):
        state["cmd"] = False
        return "stoppad"

    await maskin.add_method(ns, "Start", start, [], [ua.VariantType.String])
    await maskin.add_method(ns, "Stop", stop, [], [ua.VariantType.String])

    print("OPC UA-server: opc.tcp://localhost:4840/iot-lab/  (Ctrl+C stoppar)")
    async with server:
        while True:
            await asyncio.sleep(0.5)
            if state["cmd"] is not None:
                await kor.write_value(state["cmd"])
                state["cmd"] = None
            running = await kor.read_value()
            t = await temperatur.read_value()
            if running:
                sp = await borvarde.read_value()
                t += random.uniform(0.0, 0.8) * sp / 1500  # higher speed, more heat
                rpm = sp + random.randint(-40, 40)
                await antal.write_value(await antal.read_value() + 1)
            else:
                t += (20.0 - t) * 0.05  # svalnar mot rumstemperatur
                rpm = 0
            t += random.uniform(-0.1, 0.1)  # brus
            await temperatur.write_value(round(t, 2))
            await varvtal.write_value(rpm, ua.VariantType.Int32)
            await status.write_value("Running" if running else "Stopped")


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    asyncio.run(main())
