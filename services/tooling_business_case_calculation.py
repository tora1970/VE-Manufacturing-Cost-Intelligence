from __future__ import annotations

import math
from typing import Any, NamedTuple


class ModelledToolingBusinessCase(NamedTuple):
    annual_modelled_recurring_savings_eur: float | None
    annual_modelled_recurring_savings_status: str
    simple_payback_volume_pcs: float | None
    simple_payback_volume_status: str
    simple_payback_years: float | None
    simple_payback_years_status: str


def calculate_modelled_tooling_business_case(
    recurring_savings_per_part_eur: Any,
    annual_modelled_volume_pcs: Any,
    tooling_capex_eur: Any,
    currency_status: str,
) -> ModelledToolingBusinessCase:
    unavailable = ModelledToolingBusinessCase(
        None,
        "unavailable",
        None,
        "unavailable",
        None,
        "unavailable",
    )
    if currency_status != "verified_eur":
        return unavailable

    if recurring_savings_per_part_eur is None or annual_modelled_volume_pcs is None:
        return unavailable

    try:
        savings_per_part = float(recurring_savings_per_part_eur)
        annual_volume = float(annual_modelled_volume_pcs)
    except (TypeError, ValueError, OverflowError):
        return unavailable

    if (
        not math.isfinite(savings_per_part)
        or not math.isfinite(annual_volume)
        or annual_volume <= 0
    ):
        return unavailable

    annual_savings = savings_per_part * annual_volume
    if not math.isfinite(annual_savings):
        return unavailable

    annual_savings_status = (
        "negative_but_valid" if annual_savings < 0 else "calculated"
    )
    if savings_per_part <= 0:
        return ModelledToolingBusinessCase(
            annual_savings,
            annual_savings_status,
            None,
            "not_applicable",
            None,
            "not_applicable",
        )

    if tooling_capex_eur is None:
        return ModelledToolingBusinessCase(
            annual_savings,
            annual_savings_status,
            None,
            "unavailable",
            None,
            "unavailable",
        )

    try:
        capex = float(tooling_capex_eur)
    except (TypeError, ValueError, OverflowError):
        return ModelledToolingBusinessCase(
            annual_savings,
            annual_savings_status,
            None,
            "unavailable",
            None,
            "unavailable",
        )

    if not math.isfinite(capex) or capex < 0:
        return ModelledToolingBusinessCase(
            annual_savings,
            annual_savings_status,
            None,
            "unavailable",
            None,
            "unavailable",
        )

    if capex == 0:
        return ModelledToolingBusinessCase(
            annual_savings,
            annual_savings_status,
            None,
            "not_applicable",
            None,
            "not_applicable",
        )

    payback_volume = capex / savings_per_part
    payback_volume_status = (
        "calculated" if math.isfinite(payback_volume) else "unavailable"
    )
    if payback_volume_status != "calculated":
        payback_volume = None

    if annual_savings > 0:
        payback_years = capex / annual_savings
        payback_years_status = (
            "calculated" if math.isfinite(payback_years) else "unavailable"
        )
        if payback_years_status != "calculated":
            payback_years = None
    else:
        payback_years = None
        payback_years_status = "unavailable"

    return ModelledToolingBusinessCase(
        annual_savings,
        annual_savings_status,
        payback_volume,
        payback_volume_status,
        payback_years,
        payback_years_status,
    )
