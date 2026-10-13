from dataclasses import fields
import math

import pandas as pd
import pytest

from services.surface_treatment_contract_validation import (
    validate_surface_treatment_contract,
)
from services.surface_treatment_cost import (
    SurfaceTreatmentCostResult,
    calculate_surface_treatment_cost,
)


@pytest.fixture
def rates():
    return pd.DataFrame(
        [
            {
                "Treatment": "Anodizing",
                "Region": "Denmark",
                "Rate_EUR_m2": 12.5,
                "Source": "Synthetic regional test rate",
                "Active": True,
            },
            {
                "Treatment": "Anodizing",
                "Region": "Global",
                "Rate_EUR_m2": 20.0,
                "Source": "Synthetic global test rate",
                "Active": True,
            },
        ]
    )


def _calculate(
    rates,
    *,
    treatment="Anodizing",
    area=2,
    addon=0,
    region="Denmark",
):
    return calculate_surface_treatment_cost(
        treatment,
        area,
        addon,
        region,
        rates,
    )


def test_calculates_area_times_regional_rate_with_zero_addon(rates):
    result = _calculate(rates)

    assert result.surface_treatment_cost_eur_per_part == 25.0
    assert result.surface_treatment_cost_status == "calculated"


def test_calculates_area_times_rate_plus_positive_addon(rates):
    result = _calculate(rates, area=2, addon=3.75)

    assert result.surface_treatment_cost_eur_per_part == 28.75
    assert result.surface_treatment_cost_status == "calculated"


def test_uses_global_fallback_through_existing_resolver(rates):
    result = _calculate(rates, region="Sweden")

    assert result.surface_treatment_cost_eur_per_part == 40.0
    assert result.surface_treatment_rate_eur_m2 == 20.0
    assert result.surface_treatment_rate_source == "Synthetic global test rate"


def test_calculated_result_preserves_resolved_rate_and_source(rates):
    result = _calculate(rates)

    assert result.surface_treatment_rate_eur_m2 == 12.5
    assert result.surface_treatment_rate_source == "Synthetic regional test rate"


def test_none_treatment_returns_not_required_without_rate_data():
    result = calculate_surface_treatment_cost("None", 0, 0, None, None)

    assert result == SurfaceTreatmentCostResult(0.0, "not_required", None, None)


@pytest.mark.parametrize(
    ("area", "addon"),
    [(1, 0), (0, 1), (None, 0), (0, None), ("invalid", 0), (0, "invalid")],
)
def test_none_requires_zero_area_and_addon(area, addon):
    result = calculate_surface_treatment_cost("None", area, addon, None, None)

    assert result.surface_treatment_cost_eur_per_part is None
    assert result.surface_treatment_cost_status == "incomplete"
    assert result.surface_treatment_rate_eur_m2 is None
    assert result.surface_treatment_rate_source is None


@pytest.mark.parametrize(
    "area",
    [None, 0, -1, "invalid", math.nan, math.inf, -math.inf],
)
def test_invalid_area_is_incomplete_without_rate_lookup(rates, monkeypatch, area):
    import services.surface_treatment_cost as cost_service

    def fail_if_resolved(*args, **kwargs):
        raise AssertionError("Resolver must not run for invalid calculation inputs")

    monkeypatch.setattr(cost_service, "resolve_surface_treatment_rate", fail_if_resolved)
    result = _calculate(rates, area=area)

    assert result.surface_treatment_cost_eur_per_part is None
    assert result.surface_treatment_cost_status == "incomplete"


@pytest.mark.parametrize(
    "addon",
    [None, -1, "invalid", math.nan, math.inf, -math.inf],
)
def test_invalid_addon_is_incomplete_without_rate_lookup(rates, monkeypatch, addon):
    import services.surface_treatment_cost as cost_service

    def fail_if_resolved(*args, **kwargs):
        raise AssertionError("Resolver must not run for invalid calculation inputs")

    monkeypatch.setattr(cost_service, "resolve_surface_treatment_rate", fail_if_resolved)
    result = _calculate(rates, addon=addon)

    assert result.surface_treatment_cost_eur_per_part is None
    assert result.surface_treatment_cost_status == "incomplete"


@pytest.mark.parametrize("region", [None, "", "   "])
def test_missing_or_empty_region_is_incomplete(rates, monkeypatch, region):
    import services.surface_treatment_cost as cost_service

    def fail_if_resolved(*args, **kwargs):
        raise AssertionError("Resolver must not run for invalid calculation inputs")

    monkeypatch.setattr(cost_service, "resolve_surface_treatment_rate", fail_if_resolved)
    result = _calculate(rates, region=region)

    assert result.surface_treatment_cost_status == "incomplete"


@pytest.mark.parametrize("treatment", [None, "Chrome", ""])
def test_unsupported_treatment_is_incomplete(rates, monkeypatch, treatment):
    import services.surface_treatment_cost as cost_service

    def fail_if_resolved(*args, **kwargs):
        raise AssertionError("Resolver must not run for invalid calculation inputs")

    monkeypatch.setattr(cost_service, "resolve_surface_treatment_rate", fail_if_resolved)
    result = _calculate(rates, treatment=treatment)

    assert result.surface_treatment_cost_status == "incomplete"


def test_unresolved_rate_returns_rate_unavailable():
    result = _calculate(None)

    assert result.surface_treatment_cost_eur_per_part is None
    assert result.surface_treatment_cost_status == "rate_unavailable"
    assert result.surface_treatment_rate_eur_m2 is None
    assert result.surface_treatment_rate_source is None


def test_duplicate_regional_rates_return_rate_unavailable(rates):
    duplicate = rates.loc[rates["Region"].eq("Denmark")]
    rates = pd.concat([rates, duplicate], ignore_index=True)

    result = _calculate(rates)

    assert result.surface_treatment_cost_eur_per_part is None
    assert result.surface_treatment_cost_status == "rate_unavailable"


def test_duplicate_global_rates_return_rate_unavailable(rates):
    duplicate = rates.loc[rates["Region"].eq("Global")]
    rates = pd.concat([rates, duplicate], ignore_index=True)

    result = _calculate(rates, region="Sweden")

    assert result.surface_treatment_cost_eur_per_part is None
    assert result.surface_treatment_cost_status == "rate_unavailable"


def test_calculation_is_not_rounded_internally(rates):
    rates.loc[rates["Region"].eq("Denmark"), "Rate_EUR_m2"] = 1
    result = _calculate(rates, area=1 / 3, addon=0)

    assert result.surface_treatment_cost_eur_per_part == 1 / 3
    assert result.surface_treatment_cost_eur_per_part != round(1 / 3, 2)


def test_non_finite_final_cost_is_not_calculated(rates):
    rates.loc[rates["Region"].eq("Denmark"), "Rate_EUR_m2"] = 1e308
    result = _calculate(rates, area=1e308)

    assert result.surface_treatment_cost_eur_per_part is None
    assert result.surface_treatment_cost_status == "incomplete"
    assert result.surface_treatment_rate_eur_m2 == 1e308


def test_result_fields_and_statuses_match_contract():
    assert [field.name for field in fields(SurfaceTreatmentCostResult)] == [
        "surface_treatment_cost_eur_per_part",
        "surface_treatment_cost_status",
        "surface_treatment_rate_eur_m2",
        "surface_treatment_rate_source",
    ]

    payload = {
        "input": {
            "surface_treatment": "None",
            "surface_area_m2": 0,
            "surface_treatment_addon_eur_per_part": 0,
        },
        "context": {
            "selected_region": "Denmark",
            "calculation_currency": "EUR",
        },
        "rates": [],
        "result": {
            "surface_treatment_cost_eur_per_part": 0.0,
            "surface_treatment_cost_status": "not_required",
            "surface_treatment_rate_eur_m2": None,
            "surface_treatment_rate_source": None,
        },
    }

    assert validate_surface_treatment_contract(payload) == {
        "valid": True,
        "errors": [],
    }
