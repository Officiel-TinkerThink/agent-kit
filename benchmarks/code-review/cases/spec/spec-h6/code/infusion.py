"""Infusion program construction for volumetric pump plans."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from decimal import Decimal

from dose_calc import DoseError, round_half_up, to_decimal

log = logging.getLogger("infusion")

MIN_RATE_ML_MIN = Decimal("0.05")
MAX_RATE_ML_MIN = Decimal("50")
MAX_VOLUME_ML = Decimal("1000")
RATE_QUANTUM = Decimal("0.001")


class InfusionError(DoseError):
    """The infusion program is outside the pump limits."""


@dataclass(frozen=True)
class InfusionProgram:
    """Validated infusion program ready for the pump controller."""

    drug_id: str
    volume_ml: Decimal
    rate_ml_min: Decimal
    duration_min: Decimal

    def as_record(self) -> dict:
        """Serialise for the plan store with fixed precision."""
        return {
            "drug_id": self.drug_id,
            "volume_ml": str(round_half_up(self.volume_ml)),
            "rate_ml_min": str(round_half_up(self.rate_ml_min, RATE_QUANTUM)),
            "duration_min": str(round_half_up(self.duration_min)),
        }


def check_limits(rate_ml_min: Decimal, volume_ml: Decimal) -> None:
    """Reject flow or volume outside the pump limits."""
    if not (MIN_RATE_ML_MIN <= rate_ml_min <= MAX_RATE_ML_MIN):
        raise InfusionError(f"rate {rate_ml_min} mL/min outside pump limits")
    if volume_ml <= 0 or volume_ml > MAX_VOLUME_ML:
        raise InfusionError(f"volume {volume_ml} mL outside pump limits")


def start_infusion(drug_id: str, rate, volume_ml) -> InfusionProgram:
    """Build an infusion program. Rate is the pump flow in mL/min."""
    flow = to_decimal(rate)
    volume = to_decimal(volume_ml)
    check_limits(flow, volume)
    duration = volume / flow
    log.info("infusion %s: %s mL at %s mL/min", drug_id, volume, flow)
    return InfusionProgram(drug_id, volume, flow, duration)


def total_volume(programs: list[InfusionProgram]) -> Decimal:
    """Sum of volumes for a multi-line infusion plan."""
    total = Decimal("0")
    for program in programs:
        total += program.volume_ml
    return total


def program_summary(program: InfusionProgram) -> str:
    """One-line text for the operator confirmation dialog."""
    return (
        f"{program.drug_id}: {round_half_up(program.volume_ml)} mL "
        f"over {round_half_up(program.duration_min)} min"
    )
