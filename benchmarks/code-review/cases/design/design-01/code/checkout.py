import logging
import time

from payments import PaymentGateway
from inventory import InventoryClient
from orders import OrderRepository

logger = logging.getLogger(__name__)

RETRY_DELAY_SECONDS = 2
_recent_orders = {}


class CheckoutService:
    def __init__(self, gateway=None, inventory=None, repo=None):
        self.gateway = gateway or PaymentGateway()
        self.inventory = inventory or InventoryClient()
        self.repo = repo or OrderRepository()

    def place_order(self, cart):
        global _recent_orders
        if _recent_orders.get(cart.customer_id) == cart.cart_id:
            return None
        total = sum(item.price * item.qty for item in cart.items)
        self.inventory.reserve(cart.items)
        try:
            charge_id = self.gateway.charge(cart.customer_id, total)
        except Exception:
            logger.warning("payment failed for %s", cart.customer_id)
            return None
        order = self.repo.save(cart, charge_id)
        _recent_orders[cart.customer_id] = cart.cart_id
        return order

    def charge_with_retry(self, cart, attempts=3):
        for attempt in range(attempts):
            try:
                return self.gateway.charge(cart.customer_id, cart.total())
            except TimeoutError:
                logger.info("timeout on attempt %d", attempt + 1)
                time.sleep(RETRY_DELAY_SECONDS)
        raise RuntimeError("charge failed after retries")
