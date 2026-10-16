# Order intake events: intent and requirements

Intent: accepted orders must reach the loyalty service as order_paid events, survive broker outages, and not double-credit loyalty points on redelivery.

- R1 Accepting an order persists it and emits exactly one order_paid event for that order.
- R2 An order_paid event must not be lost when the broker fails after the order is committed.
- R3 Consumers must tolerate redelivery: a message with an already processed message_id must not change the loyalty balance again.
- R4 Retries must be bounded in total time and spread with jitter so that workers do not retry in lockstep.
