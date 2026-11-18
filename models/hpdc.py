from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from numbers import Real
from typing import Any

from services.machine_cost_calculation import calculate_machine_cost


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


def calculate_total_shot_weight_kg(
    net_part_weight_kg: float,
    number_of_cavities: int,
    metal_yield: float,
) -> float:
    if isinstance(number_of_cavities, bool) or not isinstance(number_of_cavities, int):
        raise ValueError("number_of_cavities must be an integer greater than or equal to 1.")
    if number_of_cavities < 1:
        raise ValueError("number_of_cavities must be an integer greater than or equal to 1.")
    if not math.isfinite(net_part_weight_kg) or net_part_weight_kg <= 0:
        raise ValueError("net_part_weight_kg must be finite and greater than zero.")
    if not math.isfinite(metal_yield) or not 0 < metal_yield <= 1:
        raise ValueError("metal_yield must be greater than 0 and less than or equal to 1.")
    total_shot_weight = net_part_weight_kg * number_of_cavities / metal_yield
    if not math.isfinite(total_shot_weight):
        raise ValueError("total shot weight must be finite.")
    return total_shot_weight


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
    nominal_wall_thickness_mm: float | None = None
    cycle_time_prediction_method: str | None = None
    trim_required: bool = True
    trim_cycle_time_s: float | None = None
    trim_parts_per_cycle: int | None = None
    trim_machine_rate_eur_hr: float | None = None

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

        if not isinstance(self.trim_required, bool):
            raise ValueError("trim_required must be a boolean.")
        if self.trim_cycle_time_s is not None:
            if (
                isinstance(self.trim_cycle_time_s, bool)
                or not isinstance(self.trim_cycle_time_s, Real)
                or not math.isfinite(self.trim_cycle_time_s)
                or self.trim_cycle_time_s <= 0
            ):
                raise ValueError(
                    "trim_cycle_time_s must be finite and greater than zero."
                )
        if self.trim_parts_per_cycle is not None and (
            isinstance(self.trim_parts_per_cycle, bool)
            or not isinstance(self.trim_parts_per_cycle, int)
            or self.trim_parts_per_cycle < 1
        ):
            raise ValueError(
                "trim_parts_per_cycle must be an integer greater than or equal to 1."
            )
        if self.trim_machine_rate_eur_hr is not None and (
            isinstance(self.trim_machine_rate_eur_hr, bool)
            or not isinstance(self.trim_machine_rate_eur_hr, Real)
            or not math.isfinite(self.trim_machine_rate_eur_hr)
            or self.trim_machine_rate_eur_hr < 0
        ):
            raise ValueError(
                "trim_machine_rate_eur_hr must be finite and greater than "
                "or equal to zero."
            )

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
    tooling_cost: float  # Deprecated compatibility field; always zero.
    scrap_cost: float  # Deprecated compatibility field; always zero.
    overhead_cost: float
    total_cost: float
    annual_cost: float
    currency: str
    process_yield: float
    material_cost_per_gross_part: float
    material_cost_per_good_part: float
    machine_cost_per_gross_part: float
    machine_cost_per_good_part: float
    labour_cost_per_gross_part: float
    labour_cost_per_good_part: float
    overhead_base_per_good_part: float
    recurring_manufacturing_should_cost: float
    annual_recurring_manufacturing_cost: float
    tooling_investment_eur: float
    tool_life_shots: int
    number_of_cavities: int
    tool_life_gross_parts: int
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
    good_parts_per_shot: float | None = None
    good_parts_per_hour: float | None = None
    gross_parts_required_year: float | None = None
    rejected_parts_year: float | None = None
    required_shots_year: float | None = None
    machine_hours_year: float | None = None
    hpdc_cycle_time_s: float | None = None
    trim_required: bool = True
    trim_cycle_time_s: float | None = None
    trim_cycle_time_source: str | None = None
    trim_parts_per_cycle: int | None = None
    trim_cycles_per_shot: float = 0.0
    trim_time_required_per_shot_s: float = 0.0
    effective_takt_s: float | None = None
    trim_bottleneck: bool = False
    trim_machine_rate_eur_hr: float | None = None
    trim_machine_rate_source: str = "missing"
    trim_machine_time_per_shot_s: float = 0.0
    trim_machine_cost_per_shot_eur: float = 0.0
    trim_machine_cost_eur_per_good_part: float = 0.0
    trim_machine_cost_status: str = "rate_missing"

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
        total_shot_weight = calculate_total_shot_weight_kg(
            net_part_weight,
            cavities,
            metal_yield,
        )
        shots_per_hour = 3600 / cycle_time
        gross_parts_per_hour = shots_per_hour * cavities
        good_parts_per_shot = cavities * process_yield
        trim_cycle_time = None
        trim_cycle_time_source = None
        trim_parts_per_cycle = None
        trim_cycles_per_shot = 0.0
        trim_time_required_per_shot = 0.0
        trim_bottleneck = False
        if data.trim_required:
            if data.trim_cycle_time_s is None:
                trim_cycle_time = cycle_time * 0.167
                trim_cycle_time_source = (
                    "Default engineering assumption: 16.7% of HPDC cycle "
                    "(not masterdata)"
                )
            else:
                trim_cycle_time = float(data.trim_cycle_time_s)
                trim_cycle_time_source = "User-entered"
            trim_parts_per_cycle = data.trim_parts_per_cycle or 1
            trim_cycles_per_shot = (
                good_parts_per_shot / trim_parts_per_cycle
            )
            trim_time_required_per_shot = (
                trim_cycles_per_shot * trim_cycle_time
            )
            trim_bottleneck = trim_time_required_per_shot > cycle_time
        effective_takt = max(cycle_time, trim_time_required_per_shot)
        trim_machine_time_per_shot = (
            trim_time_required_per_shot if data.trim_required else 0.0
        )
        trim_machine_rate_source = (
            "user_input"
            if data.trim_machine_rate_eur_hr is not None
            else "missing"
        )
        trim_machine_cost_per_shot = 0.0
        trim_machine_cost_per_good_part = 0.0
        if not data.trim_required:
            trim_machine_cost_status = "not_required"
        elif data.trim_machine_rate_eur_hr is None:
            trim_machine_cost_status = "rate_missing"
        else:
            if good_parts_per_shot <= 0:
                raise ValueError(
                    "good_parts_per_shot must be greater than zero to "
                    "calculate trim-machine cost."
                )
            if (
                not math.isfinite(trim_cycles_per_shot)
                or trim_cycles_per_shot < 0
                or not math.isfinite(trim_machine_time_per_shot)
                or trim_machine_time_per_shot < 0
            ):
                raise ValueError(
                    "Trim-machine time and cycles per shot must be finite "
                    "and non-negative."
                )
            calculated_trim_machine_cost, trim_machine_cost_status = (
                calculate_machine_cost(
                    trim_machine_time_per_shot,
                    data.trim_machine_rate_eur_hr,
                )
            )
            if (
                trim_machine_cost_status != "calculated"
                or calculated_trim_machine_cost is None
            ):
                raise ValueError("Trim-machine cost calculation is not finite.")
            trim_machine_cost_per_shot = calculated_trim_machine_cost
            trim_machine_cost_per_good_part = (
                trim_machine_cost_per_shot / good_parts_per_shot
            )
            if not math.isfinite(trim_machine_cost_per_good_part):
                raise ValueError(
                    "Trim-machine cost per good part must be finite."
                )
        good_parts_per_hour = gross_parts_per_hour * process_yield
        gross_parts_required_year = data.annual_volume / process_yield
        rejected_parts_year = gross_parts_required_year - data.annual_volume
        required_shots_year = gross_parts_required_year / cavities
        machine_hours_year = required_shots_year * cycle_time / 3600

        machine_cost_per_gross_part = (
            data.machine_rate_eur_h * cycle_time / (3600 * cavities)
        )
        machine_cost_per_good_part = machine_cost_per_gross_part / process_yield
        material_cost_per_gross_part = (
            net_part_weight / metal_yield * data.material_price_eur_kg
        )
        material_cost_per_good_part = material_cost_per_gross_part / process_yield
        effective_cycle_h = cycle_time / 3600 / data.oee
        labour_cost_per_gross_part = (
            effective_cycle_h * data.labour_rate_eur_h * data.operators / cavities
        )
        labour_cost_per_good_part = labour_cost_per_gross_part / process_yield
        overhead_base_per_good_part = (
            machine_cost_per_good_part + labour_cost_per_good_part
        )
        overhead_cost = overhead_base_per_good_part * data.overhead_rate
        recurring_manufacturing_should_cost = (
            material_cost_per_good_part
            + machine_cost_per_good_part
            + labour_cost_per_good_part
            + overhead_cost
            + trim_machine_cost_per_good_part
        )
        annual_recurring_manufacturing_cost = (
            recurring_manufacturing_should_cost * data.annual_volume
        )
        rounded_total_cost = round(recurring_manufacturing_should_cost, 4)

        cycle_time_deviation = None
        cycle_time_warning = None
        cycle_time_source = data.cycle_time_prediction_method or "Predicted"
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
            material_cost=round(material_cost_per_good_part, 4),
            machine_cost=round(machine_cost_per_good_part, 4),
            labour_cost=round(labour_cost_per_good_part, 4),
            tooling_cost=0.0,
            scrap_cost=0.0,
            overhead_cost=round(overhead_cost, 4),
            total_cost=rounded_total_cost,
            annual_cost=round(annual_recurring_manufacturing_cost, 2),
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
            hpdc_cycle_time_s=cycle_time,
            trim_required=data.trim_required,
            trim_cycle_time_s=trim_cycle_time,
            trim_cycle_time_source=trim_cycle_time_source,
            trim_parts_per_cycle=trim_parts_per_cycle,
            trim_cycles_per_shot=trim_cycles_per_shot,
            trim_time_required_per_shot_s=trim_time_required_per_shot,
            effective_takt_s=effective_takt,
            trim_bottleneck=trim_bottleneck,
            trim_machine_rate_eur_hr=data.trim_machine_rate_eur_hr,
            trim_machine_rate_source=trim_machine_rate_source,
            trim_machine_time_per_shot_s=trim_machine_time_per_shot,
            trim_machine_cost_per_shot_eur=trim_machine_cost_per_shot,
            trim_machine_cost_eur_per_good_part=(
                trim_machine_cost_per_good_part
            ),
            trim_machine_cost_status=trim_machine_cost_status,
            material_cost_per_gross_part=material_cost_per_gross_part,
            material_cost_per_good_part=material_cost_per_good_part,
            machine_cost_per_gross_part=machine_cost_per_gross_part,
            machine_cost_per_good_part=machine_cost_per_good_part,
            labour_cost_per_gross_part=labour_cost_per_gross_part,
            labour_cost_per_good_part=labour_cost_per_good_part,
            overhead_base_per_good_part=overhead_base_per_good_part,
            recurring_manufacturing_should_cost=(
                recurring_manufacturing_should_cost
            ),
            annual_recurring_manufacturing_cost=round(
                annual_recurring_manufacturing_cost, 2
            ),
            tooling_investment_eur=data.tooling_cost_eur,
            tool_life_shots=data.tool_life_shots,
            number_of_cavities=cavities,
            tool_life_gross_parts=data.tool_life_shots * cavities,
        )
