import pandas as pd
import pytest

from services.masterdata_loader import MasterDataLoader
from services.surface_treatment_rate_resolution import (
    resolve_surface_treatment_rate,
)


@pytest.fixture
def rates():
    return pd.DataFrame(
        [
            {
                "Treatment": "Anodizing",
                "Region": "Denmark",
                "Rate_EUR_m2": 12.5,
                "Source": "Test regional source",
                "Active": True,
            },
            {
                "Treatment": "Anodizing",
                "Region": "Global",
                "Rate_EUR_m2": 20.0,
                "Source": "Test global source",
                "Active": True,
            },
        ]
    )


def _resolved(result, rate, source):
    assert result.rate == rate
    assert result.source == source
    assert result.status == "rate_resolved"


def test_exact_treatment_and_region_match(rates):
    _resolved(
        resolve_surface_treatment_rate("Anodizing", "Denmark", rates),
        12.5,
        "Test regional source",
    )


def test_regional_match_is_preferred_over_global(rates):
    result = resolve_surface_treatment_rate("Anodizing", "Denmark", rates)

    assert result.rate != 20.0
    assert result.source == "Test regional source"


def test_global_fallback_when_region_is_missing(rates):
    _resolved(
        resolve_surface_treatment_rate("Anodizing", "Sweden", rates),
        20.0,
        "Test global source",
    )


def test_inactive_regional_row_is_ignored(rates):
    rates.loc[rates["Region"].eq("Denmark"), "Active"] = False

    _resolved(
        resolve_surface_treatment_rate("Anodizing", "Denmark", rates),
        20.0,
        "Test global source",
    )


def test_inactive_global_row_is_ignored(rates):
    rates.loc[rates["Region"].eq("Global"), "Active"] = False

    result = resolve_surface_treatment_rate("Anodizing", "Sweden", rates)

    assert result.rate is None
    assert result.source is None
    assert result.status == "rate_unavailable"


def test_missing_rate_is_unavailable():
    rates = pd.DataFrame(
        columns=["Treatment", "Region", "Rate_EUR_m2", "Source", "Active"]
    )

    result = resolve_surface_treatment_rate("PVD", "Denmark", rates)

    assert result.rate is None
    assert result.source is None
    assert result.status == "rate_unavailable"


def test_duplicate_active_regional_rows_are_unavailable(rates):
    duplicate = rates.loc[rates["Region"].eq("Denmark")]
    rates = pd.concat([rates, duplicate], ignore_index=True)

    result = resolve_surface_treatment_rate("Anodizing", "Denmark", rates)

    assert result.rate is None
    assert result.source is None
    assert result.status == "rate_unavailable"


def test_duplicate_active_global_rows_are_unavailable(rates):
    duplicate = rates.loc[rates["Region"].eq("Global")]
    rates = pd.concat([rates, duplicate], ignore_index=True)

    result = resolve_surface_treatment_rate("Anodizing", "Sweden", rates)

    assert result.rate is None
    assert result.source is None
    assert result.status == "rate_unavailable"


def test_none_treatment_does_not_require_rate_data():
    result = resolve_surface_treatment_rate("None", "", None)

    assert result.rate is None
    assert result.source is None
    assert result.status == "not_required"


@pytest.mark.parametrize(
    ("treatment", "region", "rate_data"),
    [
        ("Chrome", "Denmark", pd.DataFrame()),
        ("PVD", "", pd.DataFrame()),
        (None, "Denmark", pd.DataFrame()),
        ("PVD", "Denmark", None),
        ("PVD", "Denmark", pd.DataFrame({"Treatment": ["PVD"]})),
    ],
)
def test_unsupported_or_invalid_inputs_are_unavailable(
    treatment, region, rate_data
):
    result = resolve_surface_treatment_rate(treatment, region, rate_data)

    assert result.rate is None
    assert result.source is None
    assert result.status == "rate_unavailable"


def test_loader_exposes_empty_surface_treatment_rate_library():
    masterdata = MasterDataLoader()

    assert masterdata.load_all() is True
    assert list(masterdata.surface_treatment_rates.columns) == [
        "Treatment",
        "Region",
        "Rate_EUR_m2",
        "Source",
        "Active",
    ]
    assert masterdata.surface_treatment_rates.empty
