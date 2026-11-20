import os
from dataclasses import dataclass


@dataclass(frozen=True)
class MqttSettings:
    host: str
    port: int
    ca: str
    cert: str
    key: str


def mqtt_settings(env=os.environ):
    for key in ("MQTT_CA", "MQTT_CERT", "MQTT_KEY"):
        if not env.get(key):
            raise ValueError(f"{key} måste vara satt (TLS och klientcertifikat är obligatoriskt)")
    return MqttSettings(
        host=env.get("MQTT_HOST", "localhost"),
        port=int(env.get("MQTT_PORT", "8883")),
        ca=env["MQTT_CA"],
        cert=env["MQTT_CERT"],
        key=env["MQTT_KEY"],
    )
