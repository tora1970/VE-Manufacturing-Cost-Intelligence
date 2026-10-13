from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

import pandas as pd

from services.surface_treatment_rate_resolution import (
    SUPPORTED_TREATMENTS,
    resolve_surface_treatment_rate,
)


@dataclass(frozen=True)
class SurfaceTreatmentCostResult:
    surface_treatment_cost_eur_per_part: float | None
    surface_treatment_cost_status: Literal[
        "not_required",
        "calculated",
        "incomplete",
        "rate_unavailable",
    ]
    surface_treatment_rate_eur_m2: float | None
    surface_treatment_rate_source: str | None


def _finite_number(value: object) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if math.isfinite(number) else None


def _incomplete_result(
    rate: float | None = None,
    source: str | None = None,
) -> SurfaceTreatmentCostResult:
    return SurfaceTreatmentCostResult(None, "incomplete", rate, source)


def calculate_surface_treatment_cost(
    surface_treatment: str | None,
    surface_area_m2: object,
    surface_treatment_addon_eur_per_part: object,
    selected_region: str | None,
    surface_treatment_rates: pd.DataFrame | None,
) -> SurfaceTreatmentCostResult:
    if surface_treatment == "None":
        area = _finite_number(surface_area_m2)
        addon = _finite_number(surface_treatment_addon_eur_per_part)
        if area != 0 or addon != 0:
            return _incomplete_result()
        return SurfaceTreatmentCostResult(0.0, "not_required", None, None)

    if (
        not isinstance(surface_treatment, str)
        or surface_treatment not in SUPPORTED_TREATMENTS
        or not isinstance(selected_region, str)
        or not selected_region.strip()
    ):
        return _incomplete_result()

    area = _finite_number(surface_area_m2)
    addon = _finite_number(surface_treatment_addon_eur_per_part)
    if area is None or area <= 0 or addon is None or addon < 0:
        return _incomplete_result()

    resolution = resolve_surface_treatment_rate(
        surface_treatment,
        selected_region,
        surface_treatment_rates,
    )
    if resolution.status == "rate_unavailable":
        return SurfaceTreatmentCostResult(
            None,
            "rate_unavailable",
            resolution.rate,
            resolution.source,
        )
    if resolution.status != "rate_resolved":
        return _incomplete_result(resolution.rate, resolution.source)

    rate = _finite_number(resolution.rate)
    if rate is None or rate <= 0:
        return _incomplete_result(resolution.rate, resolution.source)

    base_cost = area * rate
    total_cost = base_cost + addon
    if not math.isfinite(base_cost) or not math.isfinite(total_cost) or total_cost < 0:
        return _incomplete_result(resolution.rate, resolution.source)

    return SurfaceTreatmentCostResult(
        total_cost,
        "calculated",
        resolution.rate,
        resolution.source,
    )
