from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from numbers import Real


class HPDCCycleTimeError(ValueError):
    """Raised when V1 cycle-time inputs or assumptions are invalid."""


def _finite_number(name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise HPDCCycleTimeError(f"{name} must be a finite number.")
    number = float(value)
    if not math.isfinite(number):
        raise HPDCCycleTimeError(f"{name} must be a finite number.")
    return number


@dataclass(frozen=True)
class HPDCCycleTimeParameters:
    model_name: str
    nominal_wall_thickness_default_mm: float
    nominal_wall_thickness_min_mm: float
    nominal_wall_thickness_max_mm: float
    cooling_coefficient_s_per_mm_n: float
    cooling_exponent: float
    reference_volume_mm3: float
    volume_exponent: float
    minimum_volume_factor: float
    maximum_volume_factor: float
    reference_surface_area_to_volume_per_mm: float
    surface_area_to_volume_exponent: float
    minimum_surface_area_to_volume_factor: float
    maximum_surface_area_to_volume_factor: float
    reference_flow_length_mm: float
    flow_length_exponent: float
    minimum_flow_length_factor: float
    maximum_flow_length_factor: float
    assumed_fill_rate_kg_s: float
    minimum_fill_time_s: float
    maximum_fill_time_s: float
    die_close_time_s: float
    hold_time_s: float
    die_open_time_s: float
    ejection_time_s: float
    spray_handling_time_s: float

    @classmethod
    def from_mapping(
        cls, settings: Mapping[str, object] | None
    ) -> HPDCCycleTimeParameters:
        if not isinstance(settings, Mapping):
            raise HPDCCycleTimeError(
                "The 'hpdc_cycle_time_v1' configuration section is required."
            )

        required = (
            "model_name",
            "nominal_wall_thickness_default_mm",
            "nominal_wall_thickness_min_mm",
            "nominal_wall_thickness_max_mm",
            "cooling_coefficient_s_per_mm_n",
            "cooling_exponent",
            "reference_volume_mm3",
            "volume_exponent",
            "minimum_volume_factor",
            "maximum_volume_factor",
            "reference_surface_area_to_volume_per_mm",
            "surface_area_to_volume_exponent",
            "minimum_surface_area_to_volume_factor",
            "maximum_surface_area_to_volume_factor",
            "reference_flow_length_mm",
            "flow_length_exponent",
            "minimum_flow_length_factor",
            "maximum_flow_length_factor",
            "assumed_fill_rate_kg_s",
            "minimum_fill_time_s",
            "maximum_fill_time_s",
            "die_close_time_s",
            "hold_time_s",
            "die_open_time_s",
            "ejection_time_s",
            "spray_handling_time_s",
        )
        missing = [key for key in required if key not in settings]
        if missing:
            raise HPDCCycleTimeError(
                "Missing HPDC cycle-time V1 configuration values: "
                + ", ".join(missing)
            )

        return cls(**{key: settings[key] for key in required})

    def __post_init__(self) -> None:
        if not isinstance(self.model_name, str) or not self.model_name.strip():
            raise HPDCCycleTimeError("model_name must be a non-empty string.")

        positive_values = (
            "nominal_wall_thickness_default_mm",
            "nominal_wall_thickness_min_mm",
            "nominal_wall_thickness_max_mm",
            "cooling_coefficient_s_per_mm_n",
            "cooling_exponent",
            "assumed_fill_rate_kg_s",
            "minimum_fill_time_s",
            "maximum_fill_time_s",
        )
        for name in positive_values:
            if _finite_number(name, getattr(self, name)) <= 0:
                raise HPDCCycleTimeError(f"{name} must be greater than zero.")

        for name in ("volume_exponent",):
            if _finite_number(name, getattr(self, name)) < 0:
                raise HPDCCycleTimeError(f"{name} cannot be negative.")

        for name, minimum, maximum in (
            (
                "volume",
                self.minimum_volume_factor,
                self.maximum_volume_factor,
            ),
            (
                "surface_area_to_volume",
                self.minimum_surface_area_to_volume_factor,
                self.maximum_surface_area_to_volume_factor,
            ),
            (
                "flow_length",
                self.minimum_flow_length_factor,
                self.maximum_flow_length_factor,
            ),
        ):
            minimum = _finite_number(f"minimum_{name}_factor", minimum)
            maximum = _finite_number(f"maximum_{name}_factor", maximum)
            if minimum <= 0 or maximum < minimum:
                raise HPDCCycleTimeError(
                    f"maximum_{name}_factor must be greater than or equal "
                    f"to a positive minimum_{name}_factor."
                )

        if not (
            self.nominal_wall_thickness_min_mm
            <= self.nominal_wall_thickness_default_mm
            <= self.nominal_wall_thickness_max_mm
        ):
            raise HPDCCycleTimeError(
                "The default nominal wall thickness must be within the supported V1 range."
            )
        if self.maximum_fill_time_s < self.minimum_fill_time_s:
            raise HPDCCycleTimeError(
                "maximum_fill_time_s must be greater than or equal to minimum_fill_time_s."
            )

        nonnegative_times = (
            "die_close_time_s",
            "hold_time_s",
            "die_open_time_s",
            "ejection_time_s",
            "spray_handling_time_s",
        )
        for name in nonnegative_times:
            if _finite_number(name, getattr(self, name)) < 0:
                raise HPDCCycleTimeError(f"{name} cannot be negative.")


@dataclass(frozen=True)
class HPDCCycleTimeInput:
    total_shot_weight_kg: float
    nominal_wall_thickness_mm: float | None
    part_volume_mm3: float | None = None
    surface_area_mm2: float | None = None
    part_length_mm: float | None = None
    part_width_mm: float | None = None
    part_height_mm: float | None = None


@dataclass(frozen=True)
class HPDCCycleTimeResult:
    die_close_time_s: float
    fill_time_s: float
    hold_time_s: float
    cooling_time_s: float
    closed_phase_time_s: float
    die_open_time_s: float
    ejection_time_s: float
    spray_handling_time_s: float
    predicted_cycle_time_s: float
    prediction_method: str
    prediction_version: str
    assumption_notes: tuple[str, ...]
    warnings: tuple[str, ...]
    total_shot_weight_kg: float
    assumed_fill_rate_kg_s: float
    raw_fill_time_s: float
    fill_time_bound_applied: str | None
    nominal_wall_thickness_mm: float
    cooling_coefficient_s_per_mm_n: float
    cooling_exponent: float


@dataclass(frozen=True)
class HPDCCycleTimeCalculator:
    parameters: HPDCCycleTimeParameters

    def calculate(self, data: HPDCCycleTimeInput) -> HPDCCycleTimeResult:
        total_shot_weight = _finite_number(
            "total_shot_weight_kg", data.total_shot_weight_kg
        )
        if total_shot_weight <= 0:
            raise HPDCCycleTimeError("total_shot_weight_kg must be greater than zero.")

        if data.nominal_wall_thickness_mm is None:
            raise HPDCCycleTimeError(
                "nominal_wall_thickness_mm is required for automatic cycle-time prediction."
            )
        wall_thickness = _finite_number(
            "nominal_wall_thickness_mm", data.nominal_wall_thickness_mm
        )
        if not (
            self.parameters.nominal_wall_thickness_min_mm
            <= wall_thickness
            <= self.parameters.nominal_wall_thickness_max_mm
        ):
            raise HPDCCycleTimeError(
                "nominal_wall_thickness_mm must be within "
                f"{self.parameters.nominal_wall_thickness_min_mm:g} to "
                f"{self.parameters.nominal_wall_thickness_max_mm:g} mm."
            )

        volume_factor = 1.0
        surface_area_to_volume_factor = 1.0
        if (data.part_volume_mm3 is None) != (data.surface_area_mm2 is None):
            raise HPDCCycleTimeError(
                "part_volume_mm3 and surface_area_mm2 must be provided together."
            )
        if data.part_volume_mm3 is not None and data.surface_area_mm2 is not None:
            volume = _finite_number("part_volume_mm3", data.part_volume_mm3)
            surface_area = _finite_number("surface_area_mm2", data.surface_area_mm2)
            if volume <= 0 or surface_area <= 0:
                raise HPDCCycleTimeError(
                    "part_volume_mm3 and surface_area_mm2 must be greater than zero."
                )
            volume_factor = min(
                self.parameters.maximum_volume_factor,
                max(
                    self.parameters.minimum_volume_factor,
                    (volume / self.parameters.reference_volume_mm3)
                    ** self.parameters.volume_exponent,
                ),
            )
            surface_area_to_volume_ratio = surface_area / volume
            surface_area_to_volume_factor = min(
                self.parameters.maximum_surface_area_to_volume_factor,
                max(
                    self.parameters.minimum_surface_area_to_volume_factor,
                    (
                        surface_area_to_volume_ratio
                        / self.parameters.reference_surface_area_to_volume_per_mm
                    )
                    ** self.parameters.surface_area_to_volume_exponent,
                ),
            )

        dimensions = (
            data.part_length_mm,
            data.part_width_mm,
            data.part_height_mm,
        )
        flow_length_factor = 1.0
        if any(dimension is not None for dimension in dimensions):
            if any(dimension is None for dimension in dimensions):
                raise HPDCCycleTimeError(
                    "part_length_mm, part_width_mm, and part_height_mm "
                    "must be provided together."
                )
            finite_dimensions = tuple(
                _finite_number(name, dimension)
                for name, dimension in zip(
                    ("part_length_mm", "part_width_mm", "part_height_mm"),
                    dimensions,
                )
            )
            if any(dimension <= 0 for dimension in finite_dimensions):
                raise HPDCCycleTimeError(
                    "Part dimensions must be greater than zero."
                )
            flow_length_factor = min(
                self.parameters.maximum_flow_length_factor,
                max(
                    self.parameters.minimum_flow_length_factor,
                    (
                        max(finite_dimensions)
                        / self.parameters.reference_flow_length_mm
                    )
                    ** self.parameters.flow_length_exponent,
                ),
            )

        raw_fill_time = total_shot_weight / self.parameters.assumed_fill_rate_kg_s
        if not math.isfinite(raw_fill_time):
            raise HPDCCycleTimeError("The raw fill-time calculation is not finite.")
        fill_bound_applied = None
        if raw_fill_time < self.parameters.minimum_fill_time_s:
            fill_time = self.parameters.minimum_fill_time_s
            fill_bound_applied = "minimum"
        elif raw_fill_time > self.parameters.maximum_fill_time_s:
            fill_time = self.parameters.maximum_fill_time_s
            fill_bound_applied = "maximum"
        else:
            fill_time = raw_fill_time

        try:
            cooling_time = (
                self.parameters.cooling_coefficient_s_per_mm_n
                * wall_thickness**self.parameters.cooling_exponent
                * volume_factor
                * surface_area_to_volume_factor
                * flow_length_factor
            )
        except OverflowError as exc:
            raise HPDCCycleTimeError(
                "The V1 cooling-time calculation is not finite."
            ) from exc
        closed_phase_time = self.parameters.hold_time_s + cooling_time
        predicted_cycle_time = (
            self.parameters.die_close_time_s
            + fill_time
            + closed_phase_time
            + self.parameters.die_open_time_s
            + self.parameters.ejection_time_s
            + self.parameters.spray_handling_time_s
        )
        if not math.isfinite(cooling_time) or not math.isfinite(predicted_cycle_time):
            raise HPDCCycleTimeError("The V1 cycle-time calculation is not finite.")

        warnings = ()
        if fill_bound_applied is not None:
            warnings = (
                f"Raw fill time was clamped to the configured {fill_bound_applied} bound.",
            )
        assumption_notes = (
            "Configured phase times and fill rate are V1 engineering assumptions, not measured machine data.",
            (
                "Cooling uses configurable wall-thickness, volume, "
                "surface-area-to-volume, and available flow-length screening "
                "relationships, not a thermal simulation."
            ),
            (
                "Applied cooling multipliers: volume "
                f"{volume_factor:.3f}, surface-area-to-volume "
                f"{surface_area_to_volume_factor:.3f}, and flow length "
                f"{flow_length_factor:.3f}."
            ),
            "Nominal wall thickness is a user engineering input and is not inferred from part dimensions.",
            (
                "Cooling coefficient "
                f"{self.parameters.cooling_coefficient_s_per_mm_n:g} "
                "s/mm^n and exponent "
                f"{self.parameters.cooling_exponent:g} are configured assumptions."
            ),
            (
                f"Fill rate {self.parameters.assumed_fill_rate_kg_s:g} kg/s and "
                f"fill bounds {self.parameters.minimum_fill_time_s:g} to "
                f"{self.parameters.maximum_fill_time_s:g} s are configured assumptions."
            ),
            (
                "Intensification/hold and cooling are modeled as separate "
                "closed-die phases."
            ),
            (
                "Die close, hold, die open, ejection, and spray/handling times "
                "are configured phase assumptions."
            ),
        )
        return HPDCCycleTimeResult(
            die_close_time_s=self.parameters.die_close_time_s,
            fill_time_s=fill_time,
            hold_time_s=self.parameters.hold_time_s,
            cooling_time_s=cooling_time,
            closed_phase_time_s=closed_phase_time,
            die_open_time_s=self.parameters.die_open_time_s,
            ejection_time_s=self.parameters.ejection_time_s,
            spray_handling_time_s=self.parameters.spray_handling_time_s,
            predicted_cycle_time_s=predicted_cycle_time,
            prediction_method=self.parameters.model_name,
            prediction_version="V1",
            assumption_notes=assumption_notes,
            warnings=warnings,
            total_shot_weight_kg=total_shot_weight,
            assumed_fill_rate_kg_s=self.parameters.assumed_fill_rate_kg_s,
            raw_fill_time_s=raw_fill_time,
            fill_time_bound_applied=fill_bound_applied,
            nominal_wall_thickness_mm=wall_thickness,
            cooling_coefficient_s_per_mm_n=(
                self.parameters.cooling_coefficient_s_per_mm_n
            ),
            cooling_exponent=self.parameters.cooling_exponent,
        )
