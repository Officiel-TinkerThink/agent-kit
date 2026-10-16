"""Infusion program construction for volumetric pump plans."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from decimal import Decimal

from dose_calc import DoseError, round_half_up, to_decimal

log = logging.getLogger("infusion")

MIN_RATE_ML_H = Decimal("3")
MAX_RATE_ML_H = Decimal("3000")
MAX_VOLUME_ML = Decimal("1000")
RATE_QUANTUM = Decimal("0.01")


class InfusionError(DoseError):
    """The infusion program is outside the pump limits."""


@dataclass(frozen=True)
class InfusionProgram:
    """Validated infusion program ready for the pump controller."""

    drug_id: str
    volume_ml: Decimal
    rate_ml_h: Decimal
    duration_min: Decimal

    def as_record(self) -> dict:
        """Serialise for the plan store with fixed precision."""
        return {
            "drug_id": self.drug_id,
            "volume_ml": str(round_half_up(self.volume_ml)),
            "rate_ml_h": str(round_half_up(self.rate_ml_h, RATE_QUANTUM)),
            "duration_min": str(round_half_up(self.duration_min)),
        }


def check_limits(rate_ml_h: Decimal, volume_ml: Decimal) -> None:
    """Reject flow or volume outside the pump limits."""
    if not (MIN_RATE_ML_H <= rate_ml_h <= MAX_RATE_ML_H):
        raise InfusionError(f"rate {rate_ml_h} mL/h outside pump limits")
    if volume_ml <= 0 or volume_ml > MAX_VOLUME_ML:
        raise InfusionError(f"volume {volume_ml} mL outside pump limits")


def start_infusion(drug_id: str, rate_ml_h, volume_ml) -> InfusionProgram:
    """Build an infusion program from the pump flow in mL/h."""
    rate = to_decimal(rate_ml_h)
    volume = to_decimal(volume_ml)
    check_limits(rate, volume)
    duration = volume * Decimal(60) / rate
    log.info("infusion %s: %s mL at %s mL/h", drug_id, volume, rate)
    return InfusionProgram(drug_id, volume, rate, duration)


def total_volume(programs: list[InfusionProgram]) -> Decimal:
    """Sum of volumes for a multi-line infusion plan."""
    total = Decimal("0")
    for program in programs:
        total += program.volume_ml
    return total
