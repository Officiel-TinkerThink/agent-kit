# Order tax rule: intent and requirements

Orders must carry a tax amount computed from their subtotal. Add a tax rule to the order flow so that checkout applies tax at the rate published for the order's region by the regional tax service, using the rate lookup that already exists in the tax adapter, and store the resulting tax amount on the order. An order with a zero subtotal stays untaxed and is returned unchanged. The change must not alter the existing Money or Order fields, and it must follow the rules in rules/ARCHITECTURE.md.
