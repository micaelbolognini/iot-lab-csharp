"""Ren logik för edge-gatewayn, utan nätverk, så att den går att testa."""
from collections import deque


class Aggregator:
    """Samlar mätvärden och ger min/max/medel. Skickar sammanfattningar i stället för varje värde."""

    def __init__(self):
        self.values = []

    def add(self, value):
        self.values.append(float(value))

    def summary(self):
        if not self.values:
            return None
        v, self.values = self.values, []
        return {"min": min(v), "max": max(v), "avg": round(sum(v) / len(v), 2), "n": len(v)}


class Buffer:
    """Store-and-forward: meddelanden ligger kvar tills de gått att skicka. Fullt = äldsta försvinner."""

    def __init__(self, maxlen=1000):
        self.queue = deque(maxlen=maxlen)

    def push(self, message):
        self.queue.append(message)

    def drain(self, send):
        while self.queue:
            if not send(self.queue[0]):
                return
            self.queue.popleft()

    def __len__(self):
        return len(self.queue)
