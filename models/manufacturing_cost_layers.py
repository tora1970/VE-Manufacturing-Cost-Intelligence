from __future__ import annotations

import math
from dataclasses import dataclass


"""Shared manufacturing cost-layer contract.

Tooling is treated as project CAPEX / project cost and is intentionally excluded
from Manufacturing Should Cost.

All values in this contract are normalized EUR amounts; no currency conversion or
commercial pricing logic is implemented here.
"""


def _require_non_negative_finite(value: float, field_name: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{field_name} must be a finite number >= 0.")
    try:
        numeric_value = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{field_name} must be a finite number >= 0.") from None

    if not math.isfinite(numeric_value) or numeric_value < 0:
        raise ValueError(f"{field_name} must be a finite number >= 0.")

    return numeric_value


def _require_non_empty_name(name: str, field_name: str) -> str:
    if not isinstance(name, str):
        raise ValueError(f"{field_name} must be a non-empty string.")
    normalized = name.strip()
    if not normalized:
        raise ValueError(f"{field_name} must be a non-empty string.")
    return normalized


@dataclass(frozen=True)
class MaterialCostLayer:
    base_material_cost: float
    material_loss_cost: float
    material_overhead_cost: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "base_material_cost", _require_non_negative_finite(self.base_material_cost, "base_material_cost"))
        object.__setattr__(self, "material_loss_cost", _require_non_negative_finite(self.material_loss_cost, "material_loss_cost"))
        object.__setattr__(self, "material_overhead_cost", _require_non_negative_finite(self.material_overhead_cost, "material_overhead_cost"))

    @property
    def total_material_cost(self) -> float:
        return (
            self.base_material_cost
            + self.material_loss_cost
            + self.material_overhead_cost
        )


@dataclass(frozen=True)
class ProcessCostLayer:
    machine_cost: float
    labour_cost: float
    setup_cost: float
    process_scrap_cost: float
    production_overhead_cost: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "machine_cost", _require_non_negative_finite(self.machine_cost, "machine_cost"))
        object.__setattr__(self, "labour_cost", _require_non_negative_finite(self.labour_cost, "labour_cost"))
        object.__setattr__(self, "setup_cost", _require_non_negative_finite(self.setup_cost, "setup_cost"))
        object.__setattr__(self, "process_scrap_cost", _require_non_negative_finite(self.process_scrap_cost, "process_scrap_cost"))
        object.__setattr__(self, "production_overhead_cost", _require_non_negative_finite(self.production_overhead_cost, "production_overhead_cost"))

    @property
    def total_process_cost(self) -> float:
        return (
            self.machine_cost
            + self.labour_cost
            + self.setup_cost
            + self.process_scrap_cost
            + self.production_overhead_cost
        )


@dataclass(frozen=True)
class SecondaryProcessCost:
    name: str
    cost_per_part: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "name", _require_non_empty_name(self.name, "name"))
        object.__setattr__(self, "cost_per_part", _require_non_negative_finite(self.cost_per_part, "cost_per_part"))


@dataclass(frozen=True)
class SecondaryProcessCostLayer:
    costs: tuple[SecondaryProcessCost, ...]

    def __post_init__(self) -> None:
        normalized_costs = tuple(self.costs)
        seen_names: set[str] = set()
        for cost in normalized_costs:
            if not isinstance(cost, SecondaryProcessCost):
                raise TypeError("costs must contain SecondaryProcessCost values.")
            if cost.name in seen_names:
                raise ValueError("Duplicate secondary-process names are not allowed.")
            seen_names.add(cost.name)
        object.__setattr__(self, "costs", normalized_costs)

    @property
    def total_secondary_process_cost(self) -> float:
        return sum(cost.cost_per_part for cost in self.costs)


@dataclass(frozen=True)
class ManufacturingCostBreakdown:
    material: MaterialCostLayer
    process: ProcessCostLayer
    secondary_processes: SecondaryProcessCostLayer

    def __post_init__(self) -> None:
        if not isinstance(self.material, MaterialCostLayer):
            raise TypeError("material must be a MaterialCostLayer.")
        if not isinstance(self.process, ProcessCostLayer):
            raise TypeError("process must be a ProcessCostLayer.")
        if not isinstance(self.secondary_processes, SecondaryProcessCostLayer):
            raise TypeError("secondary_processes must be a SecondaryProcessCostLayer.")

    @property
    def manufacturing_should_cost(self) -> float:
        return (
            self.material.total_material_cost
            + self.process.total_process_cost
            + self.secondary_processes.total_secondary_process_cost
        )
