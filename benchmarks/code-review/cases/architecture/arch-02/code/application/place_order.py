"""Use case: place an order and publish an OrderPlaced event."""

from __future__ import annotations

import json
from dataclasses import dataclass

from kafka import KafkaProducer

from application.ports import EventPublisher

ORDER_EVENTS_TOPIC = "orders.events"
EVENT_TYPE = "OrderPlaced"


@dataclass(frozen=True)
class OrderRequest:
    order_id: str
    sku: str
    quantity: int


class PlaceOrder:
    def __init__(self, publisher: EventPublisher) -> None:
        self._publisher = publisher

    def execute(self, request: OrderRequest) -> None:
        if request.quantity <= 0:
            raise ValueError("quantity must be positive")
        event = {
            "type": EVENT_TYPE,
            "order_id": request.order_id,
            "sku": request.sku,
            "quantity": request.quantity,
        }
        payload = json.dumps(event).encode("utf-8")
        producer = KafkaProducer(bootstrap_servers="localhost:9092")
        producer.send(ORDER_EVENTS_TOPIC, value=payload)
        producer.flush()
