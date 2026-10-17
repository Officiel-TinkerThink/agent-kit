# VAT for cart subtotals: intent

A shopper's cart must show the VAT owed on its subtotal for the shopper's country. Add a tax calculation to the shop: given a country code, look up the VAT rate for that country from the tax rate service; given a subtotal in cents and a rate, return the VAT amount in whole cents, with 0.2 as the default rate. The tax computation must return a VAT amount in whole cents for each subtotal and rate it is given. The same subtotal and country must always produce the same VAT.
