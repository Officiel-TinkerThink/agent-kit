"""Customer repository mapping between SQL rows and domain objects."""

from domain.loyalty import Customer
from infrastructure.models import CustomerRow


def to_domain_customer(row: CustomerRow) -> Customer:
    """Map a persisted row to the domain Customer dataclass."""
    return Customer(
        customer_id=row.id,
        name=row.name,
        tier_code=row.tier_code,
        lifetime_spend_cents=row.lifetime_spend_cents,
    )


def load_customer(session, customer_id: int) -> Customer:
    """Load one customer by id and return it as a domain object."""
    row = session.get(CustomerRow, customer_id)
    if row is None:
        raise LookupError(f"customer {customer_id} not found")
    return to_domain_customer(row)
