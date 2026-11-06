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


def _require_rate(value: float, field_name: str) -> float:
    numeric_value = _require_finite_non_negative(value, field_name)
    if not 0 <= numeric_value < 1:
        raise ValueError(f"{field_name} must satisfy 0 <= value < 1.")
    return numeric_value


def _require_yield(value: float, field_name: str) -> float:
    numeric_value = _require_finite_non_negative(value, field_name)
    if not 0 < numeric_value <= 1:
        raise ValueError(f"{field_name} must satisfy 0 < value <= 1.")
    return numeric_value


@dataclass(frozen=True)
class ProcessScrapInput:
    process_scrap_rate: float
    material_cost_per_attempt: float
    machine_cost_per_attempt: float
    labour_cost_per_attempt: float
    currency: str = "EUR"

    def __post_init__(self) -> None:
        object.__setattr__(self, "process_scrap_rate", _require_rate(self.process_scrap_rate, "process_scrap_rate"))
        object.__setattr__(self, "material_cost_per_attempt", _require_finite_non_negative(self.material_cost_per_attempt, "material_cost_per_attempt"))
        object.__setattr__(self, "machine_cost_per_attempt", _require_finite_non_negative(self.machine_cost_per_attempt, "machine_cost_per_attempt"))
        object.__setattr__(self, "labour_cost_per_attempt", _require_finite_non_negative(self.labour_cost_per_attempt, "labour_cost_per_attempt"))
        if self.currency != "EUR":
            raise ValueError("Currency must be 'EUR'.")

    @property
    def process_yield(self) -> float:
        return 1.0 - self.process_scrap_rate

    @property
    def attempts_per_good_part(self) -> float:
        return 1.0 / self.process_yield

    @property
    def material_cost_per_good_part(self) -> float:
        return self.material_cost_per_attempt * self.attempts_per_good_part

    @property
    def machine_cost_per_good_part(self) -> float:
        return self.machine_cost_per_attempt * self.attempts_per_good_part

    @property
    def labour_cost_per_good_part(self) -> float:
        return self.labour_cost_per_attempt * self.attempts_per_good_part

    @property
    def material_scrap_cost(self) -> float:
        return self.material_cost_per_good_part - self.material_cost_per_attempt

    @property
    def machine_scrap_cost(self) -> float:
        return self.machine_cost_per_good_part - self.machine_cost_per_attempt

    @property
    def labour_scrap_cost(self) -> float:
        return self.labour_cost_per_good_part - self.labour_cost_per_attempt

    @property
    def total_process_scrap_cost(self) -> float:
        return (
            self.material_scrap_cost
            + self.machine_scrap_cost
            + self.labour_scrap_cost
        )


@dataclass(frozen=True)
class ProcessScrapResult:
    process_scrap_rate: float
    process_yield: float
    attempts_per_good_part: float
    material_cost_per_attempt: float
    material_cost_per_good_part: float
    machine_cost_per_attempt: float
    machine_cost_per_good_part: float
    labour_cost_per_attempt: float
    labour_cost_per_good_part: float
    material_scrap_cost: float
    machine_scrap_cost: float
    labour_scrap_cost: float
    total_process_scrap_cost: float
    currency: str = "EUR"

    def __post_init__(self) -> None:
        object.__setattr__(self, "process_scrap_rate", _require_rate(self.process_scrap_rate, "process_scrap_rate"))
        object.__setattr__(self, "process_yield", _require_yield(self.process_yield, "process_yield"))
        object.__setattr__(self, "attempts_per_good_part", _require_finite_non_negative(self.attempts_per_good_part, "attempts_per_good_part"))
        object.__setattr__(self, "material_cost_per_attempt", _require_finite_non_negative(self.material_cost_per_attempt, "material_cost_per_attempt"))
        object.__setattr__(self, "material_cost_per_good_part", _require_finite_non_negative(self.material_cost_per_good_part, "material_cost_per_good_part"))
        object.__setattr__(self, "machine_cost_per_attempt", _require_finite_non_negative(self.machine_cost_per_attempt, "machine_cost_per_attempt"))
        object.__setattr__(self, "machine_cost_per_good_part", _require_finite_non_negative(self.machine_cost_per_good_part, "machine_cost_per_good_part"))
        object.__setattr__(self, "labour_cost_per_attempt", _require_finite_non_negative(self.labour_cost_per_attempt, "labour_cost_per_attempt"))
        object.__setattr__(self, "labour_cost_per_good_part", _require_finite_non_negative(self.labour_cost_per_good_part, "labour_cost_per_good_part"))
        object.__setattr__(self, "material_scrap_cost", _require_finite_non_negative(self.material_scrap_cost, "material_scrap_cost"))
        object.__setattr__(self, "machine_scrap_cost", _require_finite_non_negative(self.machine_scrap_cost, "machine_scrap_cost"))
        object.__setattr__(self, "labour_scrap_cost", _require_finite_non_negative(self.labour_scrap_cost, "labour_scrap_cost"))
        object.__setattr__(self, "total_process_scrap_cost", _require_finite_non_negative(self.total_process_scrap_cost, "total_process_scrap_cost"))
        if self.currency != "EUR":
            raise ValueError("Currency must be 'EUR'.")


ProcessScrapCalculation = ProcessScrapResult


def calculate_process_scrap(process_scrap: ProcessScrapInput | None = None, **kwargs: float | str) -> ProcessScrapResult:
    if process_scrap is None:
        input_data = ProcessScrapInput(**kwargs)
    else:
        input_data = process_scrap

    if not isinstance(input_data, ProcessScrapInput):
        raise TypeError("process_scrap must be a ProcessScrapInput instance.")

    process_yield = input_data.process_yield
    attempts_per_good_part = input_data.attempts_per_good_part
    material_cost_per_good_part = input_data.material_cost_per_good_part
    machine_cost_per_good_part = input_data.machine_cost_per_good_part
    labour_cost_per_good_part = input_data.labour_cost_per_good_part

    material_scrap_cost = input_data.material_scrap_cost
    machine_scrap_cost = input_data.machine_scrap_cost
    labour_scrap_cost = input_data.labour_scrap_cost
    total_process_scrap_cost = input_data.total_process_scrap_cost

    return ProcessScrapResult(
        process_scrap_rate=input_data.process_scrap_rate,
        process_yield=process_yield,
        attempts_per_good_part=attempts_per_good_part,
        material_cost_per_attempt=input_data.material_cost_per_attempt,
        material_cost_per_good_part=material_cost_per_good_part,
        machine_cost_per_attempt=input_data.machine_cost_per_attempt,
        machine_cost_per_good_part=machine_cost_per_good_part,
        labour_cost_per_attempt=input_data.labour_cost_per_attempt,
        labour_cost_per_good_part=labour_cost_per_good_part,
        material_scrap_cost=material_scrap_cost,
        machine_scrap_cost=machine_scrap_cost,
        labour_scrap_cost=labour_scrap_cost,
        total_process_scrap_cost=total_process_scrap_cost,
        currency=input_data.currency,
    )


compute_process_scrap = calculate_process_scrap


__all__ = [
    "ProcessScrapInput",
    "ProcessScrapResult",
    "ProcessScrapCalculation",
    "calculate_process_scrap",
    "compute_process_scrap",
]
