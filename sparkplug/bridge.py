"""Sparkplug B bridge: reads the UNS topics from the gateway and republishes them as a Sparkplug edge node.

  fabrik/hall1/maskin3/{temperatur,status,antal,gateway}  ->  spBv1.0/fabrik/{NBIRTH,DBIRTH,DDATA,DDEATH,NDEATH}/...
  spBv1.0/fabrik/{NCMD,DCMD}/...                          ->  fabrik/hall1/maskin3/kommando
"""
import sys
from pathlib import Path

import paho.mqtt.client as mqtt

sys.path.insert(0, str(Path(__file__).parent.parent / "gateway"))
from mqtt_config import mqtt_settings  # noqa: E402
from sparkplug_node import Node  # noqa: E402

GROUP, NODE, DEVICE = "fabrik", "hall1", "maskin3"


class Bridge:
    def __init__(self):
        self.cfg = mqtt_settings()
        self.node = Node(GROUP, NODE, DEVICE)
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="sparkplug-bridge")
        self.client.tls_set(ca_certs=self.cfg.ca, certfile=self.cfg.cert, keyfile=self.cfg.key)
        self.client.on_connect = self.on_connect
        self.client.on_disconnect = self.on_disconnect
        self.client.on_message = self.on_message
        self.client.reconnect_delay_set(1, 10)
        self.arm_will()

    def arm_will(self):
        # Every connection gets a new bdSeq, and the broker must hold the NDEATH that matches it.
        self.node.new_session()
        topic, payload = self.node.will()
        self.client.will_set(topic, payload, qos=1, retain=False)

    def publish(self, messages):
        for topic, payload, retain in messages:
            self.client.publish(topic, payload, qos=0, retain=retain)

    def on_connect(self, client, userdata, flags, reason, props):
        print(f"MQTT connected ({reason})")
        self.publish(self.node.node_birth())
        base = f"fabrik/{NODE}/{DEVICE}"
        client.subscribe([(f"{base}/temperatur", 1), (f"{base}/status", 1), (f"{base}/antal", 1)])
        # Separate and last: retained values arrive first, so the DBIRTH carries them.
        client.subscribe(f"{base}/gateway", qos=1)
        client.subscribe([(f"spBv1.0/{GROUP}/NCMD/{NODE}", 0), (f"spBv1.0/{GROUP}/DCMD/{NODE}/{DEVICE}", 0)])

    def on_disconnect(self, client, userdata, flags, reason, props):
        print(f"MQTT disconnected ({reason})")
        self.arm_will()

    def on_message(self, client, userdata, msg):
        if msg.topic.startswith("spBv1.0/"):
            self.publish(self.node.on_command(msg.topic, msg.payload))
        else:
            self.publish(self.node.on_uns(msg.topic.rsplit("/", 1)[1], msg.payload.decode()))

    def run(self):
        self.client.connect(self.cfg.host, self.cfg.port, keepalive=10)
        self.client.loop_forever()


if __name__ == "__main__":
    try:
        Bridge().run()
    except KeyboardInterrupt:
        pass
