Checkout service places an order: it reserves stock, charges the customer through the payment gateway, and persists the order.
A repeated submission of the same cart for the same customer is rejected without a second charge.
Transient gateway timeouts are retried before a charge is reported as failed.
