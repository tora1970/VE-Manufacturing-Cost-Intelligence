from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

import pandas as pd


SUPPORTED_TREATMENTS = frozenset(
    {"Anodizing", "Powder Coating", "Wet Painting", "PVD", "Other"}
)
REQUIRED_COLUMNS = frozenset(
    {"Treatment", "Region", "Rate_EUR_m2", "Source", "Active"}
)


@dataclass(frozen=True)
class SurfaceTreatmentRateResolution:
    rate: float | None
    source: str | None
    status: Literal["rate_resolved", "rate_unavailable", "not_required"]


def _is_active(value: object) -> bool:
    if isinstance(value, str):
        return value.strip().casefold() in {"active", "true", "yes", "1"}
    if pd.isna(value):
        return False
    return value == 1


def _resolution_for_matches(
    matches: pd.DataFrame,
) -> SurfaceTreatmentRateResolution:
    if len(matches) != 1:
        return SurfaceTreatmentRateResolution(None, None, "rate_unavailable")

    row = matches.iloc[0]
    try:
        rate = float(row["Rate_EUR_m2"])
    except (TypeError, ValueError, OverflowError):
        return SurfaceTreatmentRateResolution(None, None, "rate_unavailable")

    source = row["Source"]
    if not math.isfinite(rate) or rate <= 0 or not isinstance(source, str) or not source.strip():
        return SurfaceTreatmentRateResolution(None, None, "rate_unavailable")

    return SurfaceTreatmentRateResolution(rate, source, "rate_resolved")


def resolve_surface_treatment_rate(
    treatment: str | None,
    selected_region: str | None,
    rates: pd.DataFrame | None,
) -> SurfaceTreatmentRateResolution:
    if treatment == "None":
        return SurfaceTreatmentRateResolution(None, None, "not_required")

    unavailable = SurfaceTreatmentRateResolution(None, None, "rate_unavailable")
    if (
        not isinstance(treatment, str)
        or treatment not in SUPPORTED_TREATMENTS
        or not isinstance(selected_region, str)
        or not selected_region
        or not isinstance(rates, pd.DataFrame)
        or not REQUIRED_COLUMNS.issubset(rates.columns)
        or any(list(rates.columns).count(column) != 1 for column in REQUIRED_COLUMNS)
    ):
        return unavailable

    active_rates = rates.loc[rates["Active"].map(_is_active)]
    regional_matches = active_rates.loc[
        active_rates["Treatment"].eq(treatment)
        & active_rates["Region"].eq(selected_region)
    ]
    if not regional_matches.empty:
        return _resolution_for_matches(regional_matches)

    global_matches = active_rates.loc[
        active_rates["Treatment"].eq(treatment)
        & active_rates["Region"].eq("Global")
    ]
    return _resolution_for_matches(global_matches)
