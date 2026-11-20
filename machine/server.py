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
