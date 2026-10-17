# Intent

Intent: Add place_order to the checkout module. It reserves stock for each cart line, then takes payment for the cart total.

Requirements:
- An empty cart, a line with qty below 1, or a line with a unit price that is not positive is rejected before any stock is reserved.
- When every line can be reserved and the payment is approved, the call returns an Order with status "open" that holds the reserved lines.
- When a line cannot be reserved, the call raises OutOfStock and no stock remains reserved from this call.
- When the payment is declined, the call returns None. The caller treats None as "not placed".
- When the order cannot be placed for any reason after stock has been reserved, no stock may remain reserved from this call.
- Cancelling an open order through the existing cancel_order function returns all of its lines to stock.
