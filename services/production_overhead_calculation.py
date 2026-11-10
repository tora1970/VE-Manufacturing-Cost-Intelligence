from __future__ import annotations

import math
from dataclasses import dataclass


def _require_finite_non_negative(value: float, field_name: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{field_name} must be a finite number >= 0.")
    try:
        numeric_value = float(value)
    except (TypeError, ValueError, OverflowError):
        raise ValueError(f"{field_name} must be a finite number >= 0.") from None

    if not math.isfinite(numeric_value) or numeric_value < 0:
        raise ValueError(f"{field_name} must be a finite number >= 0.")

    return numeric_value


@dataclass(frozen=True)
class ProductionOverheadInput:
    machine_cost_per_good_part: float
    labour_cost_per_good_part: float
    setup_cost_per_good_part: float
    production_overhead_rate: float
    currency: str = "EUR"

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "machine_cost_per_good_part",
            _require_finite_non_negative(
                self.machine_cost_per_good_part, "machine_cost_per_good_part"
            ),
        )
        object.__setattr__(
            self,
            "labour_cost_per_good_part",
            _require_finite_non_negative(
                self.labour_cost_per_good_part, "labour_cost_per_good_part"
            ),
        )
        object.__setattr__(
            self,
            "setup_cost_per_good_part",
            _require_finite_non_negative(
                self.setup_cost_per_good_part, "setup_cost_per_good_part"
            ),
        )
        object.__setattr__(
            self,
            "production_overhead_rate",
            _require_finite_non_negative(
                self.production_overhead_rate, "production_overhead_rate"
            ),
        )
        if self.currency != "EUR":
            raise ValueError("Currency must be 'EUR'.")

    @property
    def overhead_basis_per_good_part(self) -> float:
        basis = (
            self.machine_cost_per_good_part
            + self.labour_cost_per_good_part
            + self.setup_cost_per_good_part
        )
        if not math.isfinite(basis):
            raise ValueError("Production overhead basis must be finite.")
        return basis

    @property
    def production_overhead_cost_per_good_part(self) -> float:
        overhead = self.overhead_basis_per_good_part * self.production_overhead_rate
        if not math.isfinite(overhead):
            raise ValueError("Production overhead cost must be finite.")
        return overhead


@dataclass(frozen=True)
class ProductionOverheadResult:
    overhead_basis_per_good_part: float
    production_overhead_rate: float
    production_overhead_cost_per_good_part: float
    currency: str = "EUR"

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "overhead_basis_per_good_part",
            _require_finite_non_negative(
                self.overhead_basis_per_good_part, "overhead_basis_per_good_part"
            ),
        )
        object.__setattr__(
            self,
            "production_overhead_rate",
            _require_finite_non_negative(
                self.production_overhead_rate, "production_overhead_rate"
            ),
        )
        object.__setattr__(
            self,
            "production_overhead_cost_per_good_part",
            _require_finite_non_negative(
                self.production_overhead_cost_per_good_part,
                "production_overhead_cost_per_good_part",
            ),
        )
        if self.currency != "EUR":
            raise ValueError("Currency must be 'EUR'.")


def calculate_production_overhead(
    overhead: ProductionOverheadInput,
) -> ProductionOverheadResult:
    if not isinstance(overhead, ProductionOverheadInput):
        raise TypeError("overhead must be a ProductionOverheadInput instance.")

    return ProductionOverheadResult(
        overhead_basis_per_good_part=overhead.overhead_basis_per_good_part,
        production_overhead_rate=overhead.production_overhead_rate,
        production_overhead_cost_per_good_part=(
            overhead.production_overhead_cost_per_good_part
        ),
        currency=overhead.currency,
    )


__all__ = [
    "ProductionOverheadInput",
    "ProductionOverheadResult",
    "calculate_production_overhead",
]
