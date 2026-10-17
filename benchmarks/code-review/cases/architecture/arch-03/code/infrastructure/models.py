"""SQL persistence models for customers.

Owned by the infrastructure layer. Nothing outside infrastructure imports
these classes; other layers receive domain types from the mapper.
"""


class Base:
    """Minimal declarative base stub used by the persistence models."""

    __tablename__ = ""


class CustomerRow(Base):
    """Row of the customers table."""

    __tablename__ = "customers"

    def __init__(self, id, name, tier_code, lifetime_spend_cents):
        self.id = id
        self.name = name
        self.tier_code = tier_code
        self.lifetime_spend_cents = lifetime_spend_cents
