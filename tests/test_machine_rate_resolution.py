import pandas as pd
import pytest

from services.machine_rate_resolution import (
    resolve_injection_molding_machine_rate,
    resolve_hpdc_machine,
    resolve_machine_rate,
    technology_name_mapping,
)
from services.config import load_settings
from services.masterdata_service import MasterDataError, MasterDataService


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


def hpdc_machine_data():
    return pd.DataFrame(
        {
            "Process": ["Die Casting", "Die Casting", "Die Casting"],
            "Size": ["Small", "Medium", "Large"],
            "Machine Hour Rate €/h": [70.0, 85.0, 110.0],
            "Max Part Size": ["300 x 200 mm", "500 x 400 mm", "800 x 600 mm"],
            "Max Part Weight": [10.0, 25.0, 60.0],
        }
    )


def test_hpdc_selects_smallest_eligible_machine():
    selection = resolve_hpdc_machine(hpdc_machine_data(), 200, 150, 8)
    assert selection.size == "Small"
    assert selection.machine_hour_rate_eur_hr == 70.0
    assert selection.process == "Die Casting"
    assert selection.selection_method == "Smallest eligible machine class"


@pytest.mark.parametrize(
    ("layout_length", "layout_width", "shot_weight"),
    [
        (350.0, 150.0, 8.0),
        (200.0, 150.0, 11.0),
    ],
)
def test_hpdc_selects_medium_when_small_fails(
    layout_length, layout_width, shot_weight
):
    selection = resolve_hpdc_machine(
        hpdc_machine_data(), layout_length, layout_width, shot_weight
    )
    assert selection.size == "Medium"
    assert selection.machine_hour_rate_eur_hr == 85.0


def test_hpdc_layout_rotation_can_make_a_machine_eligible():
    data = hpdc_machine_data().iloc[[0]].copy()
    data.loc[data.index[0], "Max Part Size"] = "300 x 400 mm"
    selection = resolve_hpdc_machine(data, 350, 250, 8)
    assert selection.size == "Small"
    assert "fits rotated" in selection.selection_reason


def test_hpdc_no_eligible_machine_reports_required_and_available_capacity():
    with pytest.raises(ValueError) as error:
        resolve_hpdc_machine(hpdc_machine_data(), 900, 700, 70)
    message = str(error.value)
    assert "900 x 700 mm" in message
    assert "70 kg" in message
    assert "800 x 600 mm" in message
    assert "60 kg" in message
    assert "layout size and shot weight" in message


def test_hpdc_source_process_alias_does_not_mutate_masterdata():
    data = hpdc_machine_data()
    original = data.copy(deep=True)
    selection = resolve_hpdc_machine(data, 200, 150, 8)
    assert technology_name_mapping["HPDC"] == "Die Casting"
    assert selection.process == "Die Casting"
    pd.testing.assert_frame_equal(data, original)


def test_hpdc_machine_rate_comes_from_masterdata_workbook_path():
    class Loader:
        def __init__(self):
            self.path = None
            self.force_refresh = False

        def load_excel(self, path, force_refresh=False):
            self.path = path
            self.force_refresh = force_refresh
            return hpdc_machine_data()

    loader = Loader()
    settings = load_settings()
    service = MasterDataService(loader, settings["masterdata"])
    selection = resolve_hpdc_machine(
        service.hpdc_machines(force_refresh=True), 200, 150, 8
    )
    assert loader.path == "Masterdata/Machine.xlsx"
    assert "hpdc_machines" not in settings["masterdata"]
    assert loader.force_refresh
    assert selection.machine_hour_rate_eur_hr == 70.0


def test_hpdc_materials_use_the_shared_central_materials_path():
    class Loader:
        def __init__(self):
            self.paths = []

        def load_excel(self, path, force_refresh=False):
            self.paths.append(path)
            return pd.DataFrame(
                {"Material": ["A380"], "Material Price EUR/kg": [2.5]}
            )

    loader = Loader()
    settings = load_settings()
    service = MasterDataService(loader, settings["masterdata"])
    assert service.hpdc_alloys()["Material"].tolist() == ["A380"]
    assert loader.paths == ["Masterdata/Materials.xlsx"]


@pytest.mark.parametrize(
    "size",
    ["not a size", "-300 x 200 mm", "300 x 200 x 100 mm"],
)
def test_hpdc_invalid_machine_size_data_is_rejected(size):
    data = hpdc_machine_data()
    data.loc[0, "Max Part Size"] = size
    with pytest.raises(MasterDataError, match="Max Part Size"):
        resolve_hpdc_machine(data, 200, 150, 8)
