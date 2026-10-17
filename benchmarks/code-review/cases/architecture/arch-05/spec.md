# Order cancellation and refunds: intent and requirements

Cancelling an order records a refund only when money was already captured: cancelling a paid order creates exactly one pending refund for its full amount, cancelling a new order that was never paid creates none, and an order that is already cancelled is rejected without touching its refund record, so a refund is never recorded twice for the same order.
