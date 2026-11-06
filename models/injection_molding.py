from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class InjectionMoldingInput:
    annual_volume: int
    part_weight_kg: float
    material_price_eur_kg: float
    material_utilization: float
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

        invalid = [
            name
            for name, value in positive.items()
            if value <= 0
        ]

        if invalid:
            raise ValueError(
                f"Values must be greater than zero: {', '.join(invalid)}"
            )

        for name, value in {
            "material_utilization": self.material_utilization,
            "oee": self.oee,
        }.items():
            if not 0 < value <= 1:
                raise ValueError(
                    f"{name} must be between 0 and 1."
                )

        for name, value in {
            "scrap_rate": self.scrap_rate,
            "overhead_rate": self.overhead_rate,
        }.items():
            if not 0 <= value < 1:
                raise ValueError(
                    f"{name} must be at least 0 and less than 1."
                )

        if (
            self.operators < 0
            or self.labour_rate_eur_h < 0
            or self.tooling_cost_eur < 0
        ):
            raise ValueError(
                "Labour and tooling values cannot be negative."
            )
