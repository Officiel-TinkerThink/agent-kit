# Invoice summary line: intent

Billing staff see invoices in a portal list, where each row needs a one-line summary of the invoice. The change adds a summary method on the invoice that returns the invoice id and its total, formatted the same way as the totals in the full billing report, so that the portal row and the printed report show the same amount and currency. The summary must accept the same optional report style as the full report and fall back to the default style when none is given. The invoice data types, the report rendering and the use cases keep their current behaviour.
