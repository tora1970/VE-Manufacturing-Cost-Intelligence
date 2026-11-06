from __future__ import annotations

import math
from dataclasses import dataclass


def _require_finite_non_negative(value: float, field_name: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{field_name} must be a finite number >= 0.")
    try:
        numeric_value = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{field_name} must be a finite number >= 0.") from None

    if not math.isfinite(numeric_value) or numeric_value < 0:
        raise ValueError(f"{field_name} must be a finite number >= 0.")

    return numeric_value


def _require_positive(value: float, field_name: str) -> float:
    numeric_value = _require_finite_non_negative(value, field_name)
    if numeric_value <= 0:
        raise ValueError(f"{field_name} must be greater than 0.")
    return numeric_value


@dataclass(frozen=True)
class SetupCostInput:
    setup_time_h: float
    machine_rate_eur_h: float
    labour_rate_eur_h: float
    operators: float
    batch_size_pcs: float
    currency: str = "EUR"

    def __post_init__(self) -> None:
        object.__setattr__(self, "setup_time_h", _require_finite_non_negative(self.setup_time_h, "setup_time_h"))
        object.__setattr__(self, "machine_rate_eur_h", _require_finite_non_negative(self.machine_rate_eur_h, "machine_rate_eur_h"))
        object.__setattr__(self, "labour_rate_eur_h", _require_finite_non_negative(self.labour_rate_eur_h, "labour_rate_eur_h"))
        object.__setattr__(self, "operators", _require_finite_non_negative(self.operators, "operators"))
        object.__setattr__(self, "batch_size_pcs", _require_positive(self.batch_size_pcs, "batch_size_pcs"))

        if self.currency != "EUR":
            raise ValueError("Currency must be 'EUR'.")

    @property
    def setup_hourly_cost(self) -> float:
        return self.machine_rate_eur_h + self.labour_rate_eur_h * self.operators

    @property
    def setup_cost_per_batch(self) -> float:
        return self.setup_time_h * self.setup_hourly_cost

    @property
    def setup_cost_per_part(self) -> float:
        return self.setup_cost_per_batch / self.batch_size_pcs


@dataclass(frozen=True)
class SetupCostResult:
    setup_hourly_cost: float
    setup_cost_per_batch: float
    setup_cost_per_part: float
    currency: str = "EUR"

    def __post_init__(self) -> None:
        object.__setattr__(self, "setup_hourly_cost", _require_finite_non_negative(self.setup_hourly_cost, "setup_hourly_cost"))
        object.__setattr__(self, "setup_cost_per_batch", _require_finite_non_negative(self.setup_cost_per_batch, "setup_cost_per_batch"))
        object.__setattr__(self, "setup_cost_per_part", _require_finite_non_negative(self.setup_cost_per_part, "setup_cost_per_part"))
        if self.currency != "EUR":
            raise ValueError("Currency must be 'EUR'.")


SetupCostCalculation = SetupCostResult


def calculate_setup_cost(setup: SetupCostInput | None = None, **kwargs: float | str) -> SetupCostResult:
    if setup is None:
        input_data = SetupCostInput(**kwargs)
    else:
        input_data = setup

    if not isinstance(input_data, SetupCostInput):
        raise TypeError("setup must be a SetupCostInput instance.")

    return SetupCostResult(
        setup_hourly_cost=input_data.setup_hourly_cost,
        setup_cost_per_batch=input_data.setup_cost_per_batch,
        setup_cost_per_part=input_data.setup_cost_per_part,
        currency=input_data.currency,
    )


compute_setup_cost = calculate_setup_cost


__all__ = [
    "SetupCostInput",
    "SetupCostResult",
    "SetupCostCalculation",
    "calculate_setup_cost",
    "compute_setup_cost",
]
