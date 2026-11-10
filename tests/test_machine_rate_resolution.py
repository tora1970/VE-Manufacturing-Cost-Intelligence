import pandas as pd
import pytest

from services.machine_rate_resolution import (
    resolve_injection_molding_machine_rate,
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


@pytest.fixture
def injection_molding_rate_table():
    return pd.DataFrame(
        {
            "Technology_ID": ["IM", "IM", "HPDC"],
            "Machine_Class_ID": ["CLASS_A", "CLASS_B", "CLASS_A"],
            "Machine_Rate_EUR_hr": [101.0, 202.0, 303.0],
        }
    )


def test_injection_molding_resolves_exact_technology_and_class(
    injection_molding_rate_table,
):
    assert resolve_injection_molding_machine_rate(
        "IM", "CLASS_B", injection_molding_rate_table
    ) == (202.0, "resolved")


def test_injection_molding_resolves_class_among_multiple_classes(
    injection_molding_rate_table,
):
    assert resolve_injection_molding_machine_rate(
        "IM", "CLASS_A", injection_molding_rate_table
    ) == (101.0, "resolved")


def test_injection_molding_resolves_technology_among_multiple_technologies(
    injection_molding_rate_table,
):
    assert resolve_injection_molding_machine_rate(
        "HPDC", "CLASS_A", injection_molding_rate_table
    ) == (303.0, "resolved")


@pytest.mark.parametrize(
    ("technology_id", "machine_class_id"),
    [
        ("UNKNOWN", "CLASS_A"),
        ("IM", "UNKNOWN"),
    ],
)
def test_injection_molding_wrong_technology_or_class_is_unavailable(
    injection_molding_rate_table, technology_id, machine_class_id
):
    assert resolve_injection_molding_machine_rate(
        technology_id, machine_class_id, injection_molding_rate_table
    ) == (None, "unavailable")


def test_injection_molding_missing_identifiers_are_unavailable(
    injection_molding_rate_table,
):
    for technology_id, machine_class_id in [
        (None, "CLASS_A"),
        ("", "CLASS_A"),
        ("IM", None),
        ("IM", ""),
    ]:
        assert resolve_injection_molding_machine_rate(
            technology_id, machine_class_id, injection_molding_rate_table
        ) == (None, "unavailable")


def test_injection_molding_missing_rate_table_is_unavailable():
    assert resolve_injection_molding_machine_rate("IM", "CLASS_A", None) == (
        None,
        "unavailable",
    )


def test_injection_molding_duplicate_match_is_unavailable():
    table = pd.DataFrame(
        {
            "Technology_ID": ["IM", "IM"],
            "Machine_Class_ID": ["CLASS_A", "CLASS_A"],
            "Machine_Rate_EUR_hr": [101.0, 102.0],
        }
    )
    assert resolve_injection_molding_machine_rate("IM", "CLASS_A", table) == (
        None,
        "unavailable",
    )


@pytest.mark.parametrize(
    "columns",
    [
        {"Machine_Class_ID": ["CLASS_A"], "Machine_Rate_EUR_hr": [101.0]},
        {"Technology_ID": ["IM"], "Machine_Rate_EUR_hr": [101.0]},
        {"Technology_ID": ["IM"], "Machine_Class_ID": ["CLASS_A"]},
    ],
)
def test_injection_molding_missing_required_column_is_unavailable(columns):
    assert resolve_injection_molding_machine_rate(
        "IM", "CLASS_A", pd.DataFrame(columns)
    ) == (None, "unavailable")


@pytest.mark.parametrize(
    "rate",
    [
        "not a rate",
        float("nan"),
        float("inf"),
        float("-inf"),
        0.0,
        -1.0,
    ],
)
def test_injection_molding_invalid_rate_is_unavailable(rate):
    table = pd.DataFrame(
        {
            "Technology_ID": ["IM"],
            "Machine_Class_ID": ["CLASS_A"],
            "Machine_Rate_EUR_hr": [rate],
        }
    )
    assert resolve_injection_molding_machine_rate("IM", "CLASS_A", table) == (
        None,
        "unavailable",
    )
