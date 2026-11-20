"""Edge-gateway: läser maskinen via OPC UA, skickar uppåt via MQTT.

  OPC UA (golvet)  ->  aggregera / buffra  ->  MQTT (broker/moln)
                   <-  kommandon           <-

Topics (Unified Namespace-stil: fabrik/hall/maskin/...):
  fabrik/hall1/maskin3/temperatur   sammanfattning var 5:e sekund (min/max/avg)
  fabrik/hall1/maskin3/status       retained: senaste status direkt till nya prenumeranter
  fabrik/hall1/maskin3/antal        retained
  fabrik/hall1/maskin3/gateway      "online"/"offline" (Last Will om gatewayn dör)
  fabrik/hall1/maskin3/kommando     prenumererar: "start" / "stop"
"""
import asyncio
import json
import time

import paho.mqtt.client as mqtt
from asyncua import Client

from edge import Aggregator, Buffer
from mqtt_config import mqtt_settings

OPC_URL = "opc.tcp://localhost:4840/iot-lab/"
NAMESPACE = "urn:iot-lab:fabrik"
BASE = "fabrik/hall1/maskin3"
INTERVAL = 5


class Gateway:
    def __init__(self, loop):
        self.loop = loop
        self.temperatur = Aggregator()
        self.buffer = Buffer(maxlen=500)
        self.maskin = None

        self.cfg = mqtt_settings()
        self.mqtt = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="gateway-maskin3")
        self.mqtt.tls_set(ca_certs=self.cfg.ca, certfile=self.cfg.cert, keyfile=self.cfg.key)
        # Last Will: brokern publicerar detta om vi försvinner utan att säga hejdå.
        self.mqtt.will_set(f"{BASE}/gateway", "offline", qos=1, retain=True)
        self.mqtt.on_connect = self.on_connect
        self.mqtt.on_message = self.on_message
        self.mqtt.reconnect_delay_set(1, 10)

    # ---- MQTT ----
    def on_connect(self, client, userdata, flags, reason, props):
        print(f"MQTT ansluten ({reason})")
        client.publish(f"{BASE}/gateway", "online", qos=1, retain=True)
        client.subscribe(f"{BASE}/kommando", qos=1)

    def on_message(self, client, userdata, msg):
        # Körs i paho:s tråd, OPC UA-anropet måste in i asyncio-loopen.
        cmd = msg.payload.decode().strip().lower()
        if cmd in ("start", "stop"):
            asyncio.run_coroutine_threadsafe(self.call(cmd), self.loop)
        else:
            print(f"Okänt kommando: {cmd!r}")

    def send(self, item):
        topic, payload, retain = item
        if not self.mqtt.is_connected():
            return False
        return self.mqtt.publish(topic, payload, qos=1, retain=retain).rc == mqtt.MQTT_ERR_SUCCESS

    def publish(self, topic, payload, retain=False):
        self.buffer.push((f"{BASE}/{topic}", json.dumps(payload), retain))
        self.buffer.drain(self.send)
        if len(self.buffer):
            print(f"Broker nere, {len(self.buffer)} meddelanden buffrade")

    # ---- OPC UA ----
    async def call(self, cmd):
        method = await self.maskin.get_child(f"{self.ns}:{cmd.capitalize()}")
        result = await self.maskin.call_method(method)
        print(f"Kommando {cmd} -> {result}")

    def datachange_notification(self, node, value, data):
        # OPC UA-subscription: servern meddelar när ett värde ändras, ingen pollning.
        name = self.names[node.nodeid]
        if name == "Temperatur":
            self.temperatur.add(value)
        elif name in ("Status", "Antal"):
            self.publish(name.lower(), {"value": value, "ts": time.time()}, retain=True)

    async def run(self):
        self.mqtt.connect_async(self.cfg.host, self.cfg.port, keepalive=10)
        self.mqtt.loop_start()

        async with Client(OPC_URL) as opc:
            self.ns = await opc.get_namespace_index(NAMESPACE)
            self.maskin = await opc.nodes.objects.get_child(
                [f"{self.ns}:Fabrik", f"{self.ns}:Hall1", f"{self.ns}:Maskin3"])
            nodes = {n: await self.maskin.get_child(f"{self.ns}:{n}") for n in ("Temperatur", "Status", "Antal")}
            self.names = {node.nodeid: name for name, node in nodes.items()}

            sub = await opc.create_subscription(500, self)
            await sub.subscribe_data_change(list(nodes.values()))
            print(f"OPC UA ansluten, skickar temperatur var {INTERVAL}:e sekund")

            while True:
                await asyncio.sleep(INTERVAL)
                summary = self.temperatur.summary()
                if summary:
                    self.publish("temperatur", {**summary, "unit": "C", "ts": time.time()})


async def main():
    await Gateway(asyncio.get_running_loop()).run()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
