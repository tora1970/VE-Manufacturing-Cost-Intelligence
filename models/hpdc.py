from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class HPDCInput:
    annual_volume: int
    part_weight_kg: float
    material_price_eur_kg: float
    casting_yield: float
    cycle_time_s: float
    cavities: int
    machine_rate_eur_h: float
    oee: float
    labour_rate_eur_h: float
    operators: float
    scrap_rate: float
    tooling_cost_eur: float
    tool_life_shots: int
    overhead_rate: float
    currency: str = "EUR"
    material: str = ""
    region: str = ""
    machine: str = ""

    def validate(self) -> None:
        positive = {
            "annual_volume": self.annual_volume,
            "part_weight_kg": self.part_weight_kg,
            "material_price_eur_kg": self.material_price_eur_kg,
            "cycle_time_s": self.cycle_time_s,
            "cavities": self.cavities,
            "machine_rate_eur_h": self.machine_rate_eur_h,
            "oee": self.oee,
            "tool_life_shots": self.tool_life_shots,
        }
        invalid = [name for name, value in positive.items() if value <= 0]
        if invalid:
            raise ValueError(f"Values must be greater than zero: {', '.join(invalid)}")
        for name, value in {
            "casting_yield": self.casting_yield,
            "oee": self.oee,
        }.items():
            if not 0 < value <= 1:
                raise ValueError(f"{name} must be between 0 and 1.")
        for name, value in {
            "scrap_rate": self.scrap_rate,
            "overhead_rate": self.overhead_rate,
        }.items():
            if not 0 <= value < 1:
                raise ValueError(f"{name} must be at least 0 and less than 1.")
        if self.operators < 0 or self.labour_rate_eur_h < 0 or self.tooling_cost_eur < 0:
            raise ValueError("Labour and tooling values cannot be negative.")


@dataclass(frozen=True)
class CostBreakdown:
    material_cost: float
    machine_cost: float
    labour_cost: float
    tooling_cost: float
    scrap_cost: float
    overhead_cost: float
    total_cost: float
    annual_cost: float
    currency: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class HPDCModel:
    technology = "HPDC"

    def calculate(self, data: HPDCInput) -> CostBreakdown:
        data.validate()
        gross_weight_kg = data.part_weight_kg / data.casting_yield
        material_cost = gross_weight_kg * data.material_price_eur_kg
        effective_cycle_h = data.cycle_time_s / 3600 / data.oee
        machine_cost = effective_cycle_h * data.machine_rate_eur_h / data.cavities
        labour_cost = effective_cycle_h * data.labour_rate_eur_h * data.operators / data.cavities
        tooling_cost = data.tooling_cost_eur / (data.tool_life_shots * data.cavities)
        direct_cost = material_cost + machine_cost + labour_cost + tooling_cost
        scrap_cost = direct_cost * data.scrap_rate / (1 - data.scrap_rate) if data.scrap_rate else 0.0
        overhead_cost = (direct_cost + scrap_cost) * data.overhead_rate
        total_cost = direct_cost + scrap_cost + overhead_cost
        rounded_total_cost = round(total_cost, 4)
        return CostBreakdown(
            material_cost=round(material_cost, 4),
            machine_cost=round(machine_cost, 4),
            labour_cost=round(labour_cost, 4),
            tooling_cost=round(tooling_cost, 4),
            scrap_cost=round(scrap_cost, 4),
            overhead_cost=round(overhead_cost, 4),
            total_cost=rounded_total_cost,
            annual_cost=round(rounded_total_cost * data.annual_volume, 2),
            currency=data.currency,
        )
