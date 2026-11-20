"""Sparkplug edge node logic; methods return the messages to publish as (topic, payload, retain)."""
import json
import time

from sparkplug_payload import BOOLEAN, DOUBLE, INT64, STRING, decode, encode

NAMESPACE = "spBv1.0"
REBIRTH = "Node Control/Rebirth"
METRICS = {"Temperatur": DOUBLE, "Status": STRING, "Antal": INT64, "Kor": BOOLEAN}


class Node:
    def __init__(self, group, node, device, clock=time.time):
        self.group, self.node, self.device, self.clock = group, node, device, clock
        self.uns_base = f"fabrik/{node}/{device}"
        self.values = {name: None for name in METRICS}
        self.sessions = 0
        self.seq = 0
        self.online = False

    @property
    def bd_seq(self):
        return (self.sessions - 1) % 256

    def new_session(self):
        self.sessions += 1
        self.online = False

    def _topic(self, kind, device=False):
        suffix = f"/{self.device}" if device else ""
        return f"{NAMESPACE}/{self.group}/{kind}/{self.node}{suffix}"

    def _ms(self):
        return int(self.clock() * 1000)

    def _message(self, kind, metrics, device=True):
        payload = {"timestamp": self._ms(), "metrics": metrics, "seq": self.seq}
        self.seq = (self.seq + 1) % 256
        return (self._topic(kind, device), encode(payload), False)

    def _metric(self, name):
        return {"name": name, "timestamp": self._ms(), "datatype": METRICS[name], "value": self.values[name]}

    def will(self):
        metrics = [{"name": "bdSeq", "datatype": INT64, "value": self.bd_seq}]
        return self._topic("NDEATH"), encode({"metrics": metrics})

    def node_birth(self):
        self.seq = 0
        metrics = [
            {"name": "bdSeq", "datatype": INT64, "value": self.bd_seq},
            {"name": REBIRTH, "datatype": BOOLEAN, "value": False},
        ]
        return [self._message("NBIRTH", metrics, device=False)]

    def _device_birth(self):
        self.online = True
        return [self._message("DBIRTH", [self._metric(name) for name in METRICS])]

    def _device_data(self, names):
        return [self._message("DDATA", [self._metric(name) for name in names])] if self.online else []

    def on_uns(self, subtopic, text):
        if subtopic == "gateway":
            if text == "online":
                return self._device_birth()
            self.online = False
            return [self._message("DDEATH", [])]
        data = json.loads(text)
        if subtopic == "temperatur":
            self.values["Temperatur"] = data["avg"]
            return self._device_data(["Temperatur"])
        if subtopic == "status":
            self.values["Status"] = data["value"]
            self.values["Kor"] = data["value"] == "Running"
            return self._device_data(["Status", "Kor"])
        if subtopic == "antal":
            self.values["Antal"] = data["value"]
            return self._device_data(["Antal"])
        return []

    def on_command(self, topic, payload):
        metrics = {m["name"]: m["value"] for m in decode(payload)["metrics"]}
        if topic == self._topic("NCMD"):
            if metrics.get(REBIRTH):
                return self.node_birth() + (self._device_birth() if self.online else [])
        elif topic == self._topic("DCMD", device=True) and "Kor" in metrics:
            return [(f"{self.uns_base}/kommando", b"start" if metrics["Kor"] else b"stop", False)]
        return []
