"""Prints every Sparkplug message on the broker as readable JSON (the payloads are binary protobuf)."""
import json
import sys
from pathlib import Path

import paho.mqtt.client as mqtt

sys.path.insert(0, str(Path(__file__).parent.parent / "gateway"))
from mqtt_config import mqtt_settings  # noqa: E402
from sparkplug_payload import decode  # noqa: E402


def main():
    cfg = mqtt_settings()
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="sparkplug-dump")
    client.tls_set(ca_certs=cfg.ca, certfile=cfg.cert, keyfile=cfg.key)
    client.on_connect = lambda c, ud, flags, reason, props: c.subscribe("spBv1.0/#", qos=0)
    client.on_message = lambda c, ud, msg: print(msg.topic, json.dumps(decode(msg.payload)), flush=True)
    client.connect(cfg.host, cfg.port, keepalive=30)
    try:
        client.loop_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
