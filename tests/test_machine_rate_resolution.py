import pandas as pd
import pytest

from services.machine_rate_resolution import (
    resolve_machine_rate,
    technology_name_mapping,
)


@pytest.fixture
def technology_cost_library():
    return pd.DataFrame(
        {
            "Technology_Name": [
                "CNC Machining",
                "Die Casting",
                "HP Multi Jet Fusion",
            ],
            "Machine_Rate_EUR_hr": [60, 80, 35],
        }
    )


def test_hpdc_mapping_matches_verified_library_name(technology_cost_library):
    assert technology_name_mapping["HPDC"] == "Die Casting"
    assert resolve_machine_rate(
        "HPDC", technology_name_mapping, technology_cost_library
    ) == (80.0, "resolved")


def test_exact_technology_name_match(technology_cost_library):
    rate, status = resolve_machine_rate(
        "CNC Machining", technology_name_mapping, technology_cost_library
    )
    assert rate == 60.0
    assert status == "resolved"


def test_technology_name_match_is_exact(technology_cost_library):
    mapping = {"CNC Machining": "CNC Machining "}
    assert resolve_machine_rate(
        "CNC Machining", mapping, technology_cost_library
    ) == (None, "unavailable")


def test_missing_technology_mapping_is_unavailable(technology_cost_library):
    assert resolve_machine_rate(
        "Injection Molding", technology_name_mapping, technology_cost_library
    ) == (None, "unavailable")


def test_no_matching_library_row_is_unavailable():
    library = pd.DataFrame(
        {"Technology_Name": ["Die Casting"], "Machine_Rate_EUR_hr": [80]}
    )
    assert resolve_machine_rate(
        "CNC Machining", technology_name_mapping, library
    ) == (None, "unavailable")


def test_duplicate_matching_rows_are_unavailable():
    library = pd.DataFrame(
        {
            "Technology_Name": ["Die Casting", "Die Casting"],
            "Machine_Rate_EUR_hr": [80, 80],
        }
    )
    assert resolve_machine_rate(
        "HPDC", technology_name_mapping, library
    ) == (None, "unavailable")


@pytest.mark.parametrize("rate", ["", None, float("nan")])
def test_empty_rate_is_unavailable(rate):
    library = pd.DataFrame(
        {"Technology_Name": ["Die Casting"], "Machine_Rate_EUR_hr": [rate]}
    )
    assert resolve_machine_rate(
        "HPDC", technology_name_mapping, library
    ) == (None, "unavailable")


def test_non_numeric_rate_is_unavailable():
    library = pd.DataFrame(
        {
            "Technology_Name": ["Die Casting"],
            "Machine_Rate_EUR_hr": ["not a rate"],
        }
    )
    assert resolve_machine_rate(
        "HPDC", technology_name_mapping, library
    ) == (None, "unavailable")


def test_negative_rate_is_unavailable():
    library = pd.DataFrame(
        {"Technology_Name": ["Die Casting"], "Machine_Rate_EUR_hr": [-1]}
    )
    assert resolve_machine_rate(
        "HPDC", technology_name_mapping, library
    ) == (None, "unavailable")


def test_unresolved_rate_does_not_fall_back_to_zero():
    rate, status = resolve_machine_rate(
        "Sand Casting", technology_name_mapping, pd.DataFrame()
    )
    assert rate is None
    assert status == "unavailable"
