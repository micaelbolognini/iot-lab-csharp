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
import random

from asyncua import Server, ua
from asyncua.common.methods import uamethod

NAMESPACE = "urn:iot-lab:fabrik"


async def main():
    server = Server()
    await server.init()
    server.set_endpoint("opc.tcp://0.0.0.0:4840/iot-lab/")
    server.set_server_name("IoT-labb Maskin3")
    # Labb: ingen kryptering. I produktion: Basic256Sha256 + certifikat.
    server.set_security_policy([ua.SecurityPolicyType.NoSecurity])

    ns = await server.register_namespace(NAMESPACE)
    fabrik = await server.nodes.objects.add_folder(ns, "Fabrik")
    hall = await fabrik.add_folder(ns, "Hall1")
    maskin = await hall.add_object(ns, "Maskin3")

    temperatur = await maskin.add_variable(ns, "Temperatur", 20.0)
    varvtal = await maskin.add_variable(ns, "Varvtal", 0, ua.VariantType.Int32)
    status = await maskin.add_variable(ns, "Status", "Stopped")
    antal = await maskin.add_variable(ns, "Antal", 0, ua.VariantType.Int64)
    await varvtal.set_writable()  # klienter får skriva börvärde

    state = {"running": False}

    @uamethod
    def start(parent):
        state["running"] = True
        return "startad"

    @uamethod
    def stop(parent):
        state["running"] = False
        return "stoppad"

    await maskin.add_method(ns, "Start", start, [], [ua.VariantType.String])
    await maskin.add_method(ns, "Stop", stop, [], [ua.VariantType.String])

    print("OPC UA-server: opc.tcp://localhost:4840/iot-lab/  (Ctrl+C stoppar)")
    async with server:
        while True:
            await asyncio.sleep(0.5)
            t = await temperatur.read_value()
            if state["running"]:
                t += random.uniform(0.0, 0.8)  # värms upp
                rpm = 1500 + random.randint(-40, 40)
                await antal.write_value(await antal.read_value() + 1)
            else:
                t += (20.0 - t) * 0.05  # svalnar mot rumstemperatur
                rpm = 0
            t += random.uniform(-0.1, 0.1)  # brus
            await temperatur.write_value(round(t, 2))
            await varvtal.write_value(rpm, ua.VariantType.Int32)
            await status.write_value("Running" if state["running"] else "Stopped")


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    asyncio.run(main())
