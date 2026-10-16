from dataclasses import dataclass

MG_PER_G = 1000.0


@dataclass(frozen=True)
class DoseOrder:
    patient_id: str
    amount_mg: float
    step_mg: float
    max_dose_mg: float


def round_dose(amount_mg, step_mg, max_dose_mg):
    """Round a dose to the nearest step and cap it at the maximum dose."""
    if amount_mg < 0:
        raise ValueError("amount_mg must be non-negative")
    if max_dose_mg <= 0:
        raise ValueError("max_dose_mg must be positive")
    steps = round(amount_mg / step_mg)
    rounded = steps * step_mg
    if rounded > max_dose_mg:
        rounded = max_dose_mg
    return round(rounded, 4)


def round_order(order):
    """Return the rounded dose for a DoseOrder."""
    return round_dose(order.amount_mg, order.step_mg, order.max_dose_mg)


def dose_in_grams(amount_mg):
    """Return the dose expressed in grams, unrounded."""
    return amount_mg / MG_PER_G


if __name__ == "__main__":
    order = DoseOrder("P-001", 12.5, 5.0, 20.0)
    print(round_order(order))
    print(dose_in_grams(round_dose(1500.0, 250.0, 1000.0)))
