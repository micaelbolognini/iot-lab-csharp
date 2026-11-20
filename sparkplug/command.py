"""Acts as a Sparkplug host: sends a command to the node. Usage: command.py start|stop|rebirth"""
import sys
from pathlib import Path

import paho.mqtt.client as mqtt

sys.path.insert(0, str(Path(__file__).parent.parent / "gateway"))
from mqtt_config import mqtt_settings  # noqa: E402
from sparkplug_payload import BOOLEAN, encode  # noqa: E402

COMMANDS = {
    "start": ("spBv1.0/fabrik/DCMD/hall1/maskin3", "Kor", True),
    "stop": ("spBv1.0/fabrik/DCMD/hall1/maskin3", "Kor", False),
    "rebirth": ("spBv1.0/fabrik/NCMD/hall1", "Node Control/Rebirth", True),
}


def main(argv):
    if len(argv) != 2 or argv[1] not in COMMANDS:
        sys.exit(f"usage: {argv[0]} {'|'.join(COMMANDS)}")
    topic, metric, value = COMMANDS[argv[1]]
    cfg = mqtt_settings()
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="sparkplug-host")
    client.tls_set(ca_certs=cfg.ca, certfile=cfg.cert, keyfile=cfg.key)
    client.connect(cfg.host, cfg.port)
    client.loop_start()
    client.publish(topic, encode({"metrics": [{"name": metric, "datatype": BOOLEAN, "value": value}]}), qos=1).wait_for_publish(3)
    client.loop_stop()


if __name__ == "__main__":
    main(sys.argv)
