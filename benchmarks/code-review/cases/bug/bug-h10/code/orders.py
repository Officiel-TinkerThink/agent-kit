"""Order record created by checkout."""

from dataclasses import dataclass, field


@dataclass
class Order:
    order_id: str
    lines: list = field(default_factory=list)
    status: str = "open"
