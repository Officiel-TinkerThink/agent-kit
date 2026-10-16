"""Unit tests for billing tax helpers."""

import unittest
from decimal import ROUND_HALF_UP, Decimal

from billing import tax

FIXTURE_RATE = 0.075
FIXTURE_CUSTOMER = "CUST-0001"


class LineTaxTests(unittest.TestCase):
    """Rounding and range checks for line tax in cents."""

    def test_half_up_rounding_on_exact_half(self):
        self.assertEqual(tax.line_tax_cents(5, 5000), 3)

    def test_rounds_down_below_half(self):
        self.assertEqual(tax.line_tax_cents(4, 5000), 2)

    def test_zero_rate_yields_zero_tax(self):
        self.assertEqual(tax.line_tax_cents(9999, 0), 0)

    def test_rate_above_maximum_is_rejected(self):
        with self.assertRaises(Exception):
            tax.line_tax_cents(100, tax.MAX_RATE_BP + 1)

    def test_fixture_rate_expressed_in_percent(self):
        self.assertAlmostEqual(FIXTURE_RATE * 100, 7.5)

    def test_describe_rate_formats_percentage(self):
        self.assertEqual(tax.describe_rate(2000), "20.00%")

    def test_describe_rate_rejects_negative_rate(self):
        with self.assertRaises(Exception):
            tax.describe_rate(-1)


class TaxBreakdownTests(unittest.TestCase):
    """Grouping of tax by product group."""

    def test_reduced_group_uses_reduced_rate(self):
        self.assertEqual(tax.tax_breakdown([("DIAG", 1000)]), {"DIAG": 50})

    def test_standard_group_uses_standard_rate(self):
        self.assertEqual(tax.tax_breakdown([("CHEM", 1000)]), {"CHEM": 200})


class DecimalRoundingTests(unittest.TestCase):
    """Reference rounding for test expectations."""

    def test_reference_half_up_quantize(self):
        value = Decimal("2.675").quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        self.assertEqual(value, Decimal("2.68"))

    def test_customer_rate_lookup(self):
        self.assertEqual(tax.rate_for_customer(FIXTURE_CUSTOMER), tax.STANDARD_RATE_BP)


if __name__ == "__main__":
    unittest.main()
