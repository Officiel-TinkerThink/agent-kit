class StockTransferService:
    def __init__(self, repo, audit):
        self.repo = repo
        self.audit = audit

    def _validate_qty(self, qty):
        if qty is None or qty <= 0:
            raise ValueError("quantity must be positive")
        return int(qty)

    def transfer(self, src, dst, sku, qty, dry_run=False, priority=None):
        qty = self._validate_qty(qty)
        available = self.repo.on_hand(src, sku)
        if available < qty:
            raise ValueError("insufficient stock at source")
        self.repo.debit(src, sku, qty)
        self.repo.commit()
        self.repo.credit(dst, sku, qty)
        self.repo.commit()
        self.audit.record("transfer", src, dst, sku, qty)
        return qty

    def adjust(self, location, sku, qty, reason):
        if qty is None or qty == 0:
            raise ValueError("quantity must be non-zero")
        if not reason:
            raise ValueError("reason is required")
        self.repo.apply_delta(location, sku, int(qty))
        self.repo.commit()
        self.audit.record("adjust", location, None, sku, qty, reason)
        return qty

    def on_hand(self, location, sku):
        return self.repo.on_hand(location, sku)

    def history(self, sku, limit=50):
        return self.audit.recent(sku, limit)


__all__ = ["StockTransferService"]
