"""Composition root: wires adapters into use cases."""

from __future__ import annotations

from adapters.kafka_publisher import KafkaEventPublisher
from application.place_order import OrderRequest, PlaceOrder

BOOTSTRAP_SERVERS = "localhost:9092"


def build_place_order() -> PlaceOrder:
    return PlaceOrder(KafkaEventPublisher(BOOTSTRAP_SERVERS))


def main() -> None:
    place_order = build_place_order()
    place_order.execute(OrderRequest(order_id="ord-1001", sku="SKU-1", quantity=2))


if __name__ == "__main__":
    main()
