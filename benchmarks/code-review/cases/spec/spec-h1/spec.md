# Billing statement specification

Scope: pricing.py, periods.py and statement.py in the billing package.

R1. Totals use exact decimal arithmetic. Each line net amount is rounded half up to cents once, at the end of the line calculation.
R2. Tax is 8.25 percent of the line net amount, rounded half up to cents.
R3. A billing period is [start, end], inclusive of both calendar days, in UTC. A usage record belongs to the period when its UTC calendar date is within the period.
R4. A late fee of 1.5 percent of the open balance applies only when the invoice is more than 30 days past due. Day 30 past due has no fee; day 31 and later has the fee.
R5. Invoices are numbered with the pricing table version chosen by version-aware comparison, so "2.10" is newer than "2.9".
R6. A discount of 0 percent is a valid discount and must be applied as given. Only a missing discount defaults to the customer tier discount.
R7. Statement lines are sorted by UTC usage date ascending, then by line id ascending.
