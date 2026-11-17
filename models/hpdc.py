from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Any


def calculate_cavity_layout(
    number_of_cavities: int,
    part_length_mm: float,
    part_width_mm: float,
    layout_factor: float = 1.25,
    tool_layout_length_mm: float | None = None,
    tool_layout_width_mm: float | None = None,
) -> tuple[float, float, str]:
    if (tool_layout_length_mm is None) != (tool_layout_width_mm is None):
        raise ValueError(
            "Both tool_layout_length_mm and tool_layout_width_mm are required "
            "when providing an explicit tool layout."
        )
    if tool_layout_length_mm is not None and tool_layout_width_mm is not None:
        dimensions = (tool_layout_length_mm, tool_layout_width_mm)
        if any(not math.isfinite(value) or value <= 0 for value in dimensions):
            raise ValueError("Explicit tool layout dimensions must be finite and greater than zero.")
        return tool_layout_length_mm, tool_layout_width_mm, "Explicit tool layout"

    columns = math.ceil(math.sqrt(number_of_cavities))
    rows = math.ceil(number_of_cavities / columns)
    return (
        columns * part_length_mm * layout_factor,
        rows * part_width_mm * layout_factor,
        "Estimated cavity layout",
    )


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
    number_of_cavities: int | None = None
    process_scrap_rate: float | None = None
    net_part_weight_kg: float | None = None
    part_length_mm: float | None = None
    part_width_mm: float | None = None
    part_height_mm: float | None = None
    metal_yield: float | None = None
    cycle_time_predicted_s: float | None = None
    cycle_time_override_s: float | None = None
    layout_factor: float = 1.25
    tool_layout_length_mm: float | None = None
    tool_layout_width_mm: float | None = None
    machine_rate_source: str | None = None
    selected_machine_process: str | None = None
    selected_machine_size: str | None = None
    machine_selection_method: str | None = None
    machine_selection_reason: str | None = None
    selected_machine_max_part_size: str | None = None
    selected_machine_max_part_weight_kg: float | None = None
    limiting_constraint: str | None = None

    @property
    def effective_cavities(self) -> int:
        return self.number_of_cavities if self.number_of_cavities is not None else self.cavities

    @property
    def effective_process_scrap_rate(self) -> float:
        return self.process_scrap_rate if self.process_scrap_rate is not None else self.scrap_rate

    @property
    def effective_net_part_weight_kg(self) -> float:
        return self.net_part_weight_kg if self.net_part_weight_kg is not None else self.part_weight_kg

    @property
    def effective_metal_yield(self) -> float:
        return self.metal_yield if self.metal_yield is not None else self.casting_yield

    @property
    def predicted_cycle_time_s(self) -> float:
        return self.cycle_time_predicted_s if self.cycle_time_predicted_s is not None else self.cycle_time_s

    @property
    def effective_cycle_time_s(self) -> float:
        return self.cycle_time_override_s if self.cycle_time_override_s is not None else self.predicted_cycle_time_s

    def validate(self) -> None:
        finite_values = {
            "annual_volume": self.annual_volume,
            "part_weight_kg": self.effective_net_part_weight_kg,
            "material_price_eur_kg": self.material_price_eur_kg,
            "metal_yield": self.effective_metal_yield,
            "cycle_time_predicted_s": self.predicted_cycle_time_s,
            "cycle_time_effective_s": self.effective_cycle_time_s,
            "machine_rate_eur_h": self.machine_rate_eur_h,
            "oee": self.oee,
            "labour_rate_eur_h": self.labour_rate_eur_h,
            "operators": self.operators,
            "process_scrap_rate": self.effective_process_scrap_rate,
            "tooling_cost_eur": self.tooling_cost_eur,
            "tool_life_shots": self.tool_life_shots,
            "overhead_rate": self.overhead_rate,
            "layout_factor": self.layout_factor,
        }
        for name, value in finite_values.items():
            if not math.isfinite(value):
                raise ValueError(f"{name} must be finite.")

        cavity_count = self.effective_cavities
        if isinstance(cavity_count, bool) or not isinstance(cavity_count, int) or cavity_count < 1:
            raise ValueError("number_of_cavities must be an integer greater than or equal to 1.")
        if isinstance(self.annual_volume, bool) or not isinstance(self.annual_volume, int) or self.annual_volume <= 0:
            raise ValueError("annual_volume must be an integer greater than zero.")

        positive = {
            "net_part_weight_kg": self.effective_net_part_weight_kg,
            "material_price_eur_kg": self.material_price_eur_kg,
            "cycle_time_predicted_s": self.predicted_cycle_time_s,
            "cycle_time_effective_s": self.effective_cycle_time_s,
            "machine_rate_eur_h": self.machine_rate_eur_h,
            "oee": self.oee,
            "tool_life_shots": self.tool_life_shots,
            "layout_factor": self.layout_factor,
        }
        invalid = [name for name, value in positive.items() if value <= 0]
        if invalid:
            raise ValueError(f"Values must be greater than zero: {', '.join(invalid)}")

        if not 0 < self.effective_metal_yield <= 1:
            raise ValueError("metal_yield must be greater than 0 and less than or equal to 1.")
        process_scrap_rate = self.effective_process_scrap_rate
        if not 0 <= process_scrap_rate < 1:
            raise ValueError("process_scrap_rate must be at least 0 and less than 1.")
        process_yield = 1 - process_scrap_rate
        if process_yield <= 0:
            raise ValueError("process_yield must be greater than zero.")
        if not 0 < self.oee <= 1:
            raise ValueError("oee must be between 0 and 1.")

        if self.cycle_time_override_s is not None and (
            not math.isfinite(self.cycle_time_override_s) or self.cycle_time_override_s <= 0
        ):
            raise ValueError("cycle_time_override_s must be finite and greater than zero.")

        if (
            self.labour_rate_eur_h < 0
            or self.operators < 0
            or self.tooling_cost_eur < 0
            or self.overhead_rate < 0
        ):
            raise ValueError("Labour and tooling values cannot be negative.")
        if self.overhead_rate >= 1:
            raise ValueError("overhead_rate must be at least 0 and less than 1.")
        if self.selected_machine_max_part_weight_kg is not None and (
            not math.isfinite(self.selected_machine_max_part_weight_kg)
            or self.selected_machine_max_part_weight_kg <= 0
        ):
            raise ValueError("selected_machine_max_part_weight_kg must be greater than zero.")

        has_new_layout_inputs = any(
            value is not None
            for value in (
                self.number_of_cavities,
                self.process_scrap_rate,
                self.net_part_weight_kg,
                self.part_length_mm,
                self.part_width_mm,
                self.part_height_mm,
                self.metal_yield,
                self.cycle_time_predicted_s,
                self.cycle_time_override_s,
                self.tool_layout_length_mm,
                self.tool_layout_width_mm,
            )
        )
        dimensions = {
            "part_length_mm": self.part_length_mm,
            "part_width_mm": self.part_width_mm,
            "part_height_mm": self.part_height_mm,
        }
        if has_new_layout_inputs:
            missing = [name for name, value in dimensions.items() if value is None]
            if missing:
                raise ValueError(f"Required part dimensions are missing: {', '.join(missing)}.")
        for name, value in dimensions.items():
            if value is not None and (not math.isfinite(value) or value <= 0):
                raise ValueError(f"{name} must be finite and greater than zero.")
        if (self.tool_layout_length_mm is None) != (self.tool_layout_width_mm is None):
            raise ValueError("Both explicit tool layout dimensions must be provided together.")


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
    selected_machine_process: str | None = None
    selected_machine_size: str | None = None
    machine_rate_eur_hr: float | None = None
    machine_rate_source: str | None = None
    machine_selection_method: str | None = None
    machine_selection_reason: str | None = None
    selected_machine_max_part_size: str | None = None
    selected_machine_max_part_weight_kg: float | None = None
    limiting_constraint: str | None = None
    cycle_time_predicted_s: float | None = None
    cycle_time_override_s: float | None = None
    cycle_time_effective_s: float | None = None
    cycle_time_source: str = "Predicted"
    cycle_time_deviation_percent: float | None = None
    cycle_time_warning: str | None = None
    net_part_weight_per_shot_kg: float | None = None
    total_shot_weight_kg: float | None = None
    required_layout_length_mm: float | None = None
    required_layout_width_mm: float | None = None
    cavity_layout_method: str | None = None
    size_constraint_passed: bool | None = None
    weight_constraint_passed: bool | None = None
    shots_per_hour: float | None = None
    gross_parts_per_shot: int | None = None
    gross_parts_per_hour: float | None = None
    process_yield: float | None = None
    good_parts_per_shot: float | None = None
    good_parts_per_hour: float | None = None
    gross_parts_required_year: float | None = None
    rejected_parts_year: float | None = None
    required_shots_year: float | None = None
    machine_hours_year: float | None = None
    machine_cost_per_gross_part: float | None = None
    machine_cost_per_good_part: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class HPDCModel:
    technology = "HPDC"

    def calculate(self, data: HPDCInput) -> CostBreakdown:
        data.validate()
        cavities = data.effective_cavities
        process_yield = 1 - data.effective_process_scrap_rate
        cycle_time = data.effective_cycle_time_s
        predicted_cycle_time = data.predicted_cycle_time_s
        net_part_weight = data.effective_net_part_weight_kg
        metal_yield = data.effective_metal_yield

        layout_length, layout_width, layout_method = calculate_cavity_layout(
            cavities,
            data.part_length_mm or 1.0,
            data.part_width_mm or 1.0,
            data.layout_factor,
            data.tool_layout_length_mm,
            data.tool_layout_width_mm,
        )
        net_part_weight_per_shot = net_part_weight * cavities
        total_shot_weight = net_part_weight_per_shot / metal_yield
        shots_per_hour = 3600 / cycle_time
        gross_parts_per_hour = shots_per_hour * cavities
        good_parts_per_shot = cavities * process_yield
        good_parts_per_hour = gross_parts_per_hour * process_yield
        gross_parts_required_year = data.annual_volume / process_yield
        rejected_parts_year = gross_parts_required_year - data.annual_volume
        required_shots_year = gross_parts_required_year / cavities
        machine_hours_year = required_shots_year * cycle_time / 3600

        machine_cost_per_gross_part = data.machine_rate_eur_h * cycle_time / (3600 * cavities)
        machine_cost_per_good_part = machine_cost_per_gross_part / process_yield
        material_cost = net_part_weight / metal_yield * data.material_price_eur_kg
        effective_cycle_h = cycle_time / 3600 / data.oee
        labour_cost = effective_cycle_h * data.labour_rate_eur_h * data.operators / cavities
        tooling_cost = data.tooling_cost_eur / (data.tool_life_shots * cavities)
        scrap_cost = (material_cost + labour_cost + tooling_cost) * (
            1 / process_yield - 1
        )
        direct_cost = (
            material_cost
            + machine_cost_per_good_part
            + labour_cost
            + tooling_cost
            + scrap_cost
        )
        overhead_cost = direct_cost * data.overhead_rate
        total_cost = direct_cost + overhead_cost
        rounded_total_cost = round(total_cost, 4)

        cycle_time_deviation = None
        cycle_time_warning = None
        cycle_time_source = "Predicted"
        if data.cycle_time_override_s is not None:
            cycle_time_source = "User Override"
            cycle_time_deviation = (
                (data.cycle_time_override_s - predicted_cycle_time)
                / predicted_cycle_time
                * 100
            )
            if abs(cycle_time_deviation) > 25:
                cycle_time_warning = (
                    "Cycle-time override differs from the prediction by more than 25%."
                )

        return CostBreakdown(
            material_cost=round(material_cost, 4),
            machine_cost=round(machine_cost_per_good_part, 4),
            labour_cost=round(labour_cost, 4),
            tooling_cost=round(tooling_cost, 4),
            scrap_cost=round(scrap_cost, 4),
            overhead_cost=round(overhead_cost, 4),
            total_cost=rounded_total_cost,
            annual_cost=round(rounded_total_cost * data.annual_volume, 2),
            currency=data.currency,
            selected_machine_process=data.selected_machine_process,
            selected_machine_size=data.selected_machine_size,
            machine_rate_eur_hr=data.machine_rate_eur_h,
            machine_rate_source=data.machine_rate_source,
            machine_selection_method=data.machine_selection_method,
            machine_selection_reason=data.machine_selection_reason,
            selected_machine_max_part_size=data.selected_machine_max_part_size,
            selected_machine_max_part_weight_kg=data.selected_machine_max_part_weight_kg,
            limiting_constraint=data.limiting_constraint,
            cycle_time_predicted_s=predicted_cycle_time,
            cycle_time_override_s=data.cycle_time_override_s,
            cycle_time_effective_s=cycle_time,
            cycle_time_source=cycle_time_source,
            cycle_time_deviation_percent=cycle_time_deviation,
            cycle_time_warning=cycle_time_warning,
            net_part_weight_per_shot_kg=net_part_weight_per_shot,
            total_shot_weight_kg=total_shot_weight,
            required_layout_length_mm=layout_length,
            required_layout_width_mm=layout_width,
            cavity_layout_method=layout_method,
            size_constraint_passed=True if data.selected_machine_size else None,
            weight_constraint_passed=True if data.selected_machine_size else None,
            shots_per_hour=shots_per_hour,
            gross_parts_per_shot=cavities,
            gross_parts_per_hour=gross_parts_per_hour,
            process_yield=process_yield,
            good_parts_per_shot=good_parts_per_shot,
            good_parts_per_hour=good_parts_per_hour,
            gross_parts_required_year=gross_parts_required_year,
            rejected_parts_year=rejected_parts_year,
            required_shots_year=required_shots_year,
            machine_hours_year=machine_hours_year,
            machine_cost_per_gross_part=machine_cost_per_gross_part,
            machine_cost_per_good_part=machine_cost_per_good_part,
        )
