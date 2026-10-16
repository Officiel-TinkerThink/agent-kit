# Project rules

## Money
- Money amounts are decimal.Decimal. Never use float for money.
- The money rule does not apply under tests\.

## Lint suppression
- A lint suppression must name a ticket, in the form `# noqa: <code>  TICKET-<n>` (two spaces before the ticket).
- A bare `# noqa` is not allowed.

## Line length
- Lines are at most 88 characters (lint code E501).
