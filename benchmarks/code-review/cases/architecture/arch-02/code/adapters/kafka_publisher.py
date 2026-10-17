"""Adapter: implements the EventPublisher port on Kafka."""

from __future__ import annotations

from kafka import KafkaProducer


class KafkaEventPublisher:
    def __init__(self, bootstrap_servers: str) -> None:
        self._producer = KafkaProducer(bootstrap_servers=bootstrap_servers)

    def publish(self, topic: str, key: str, payload: bytes) -> None:
        self._producer.send(topic, key=key.encode("utf-8"), value=payload)
        self._producer.flush()
