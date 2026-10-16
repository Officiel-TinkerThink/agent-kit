# Lab consumable order pricing: service layer cleanup

Intent: cleanup of the pricing service layer. Shared money and quantity rules move into helpers, tax results may be memoised, and the service exposes line counts and an average line amount.

R1. An order is a list of lines. Each line is a dict with `sku` (text) and `qty` (integer, greater than zero).
R2. A `qty` that is missing, not an integer, a boolean, or less than or equal to zero raises InvalidQuantityError.
R3. A SKU that is not in the price table raises UnknownSkuError. No KeyError may escape the service.
R4. Line total equals unit price multiplied by qty, computed with Decimal and rounded half-up to cents.
R5. Subtotal is the sum of line totals. Tax is subtotal multiplied by the region rate, rounded half-up to cents. Total is subtotal plus tax.
R6. A region that is not listed in the region file raises TaxRegionError before any line is priced.
R7. Tax results may be memoised per process. A memo hit returns the same value as a fresh computation for the same amount and region.
R8. format_amount renders any Decimal amount as text with exactly two decimal places, rounded half-up.
R9. line_count is the number of lines. average_line is the mean of line totals rounded half-up to cents, or 0.00 for an empty order.
R10. Every failure is a PricingError subclass that carries a stable `code` attribute.
