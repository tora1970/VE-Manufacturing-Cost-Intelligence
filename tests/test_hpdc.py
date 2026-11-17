import pandas as pd
import pytest

from agents.hpdc_agent import _labour_rate, _material_price
from models.hpdc import HPDCInput, HPDCModel, calculate_cavity_layout
from services.masterdata_service import MasterDataError, MasterDataService


def test_hpdc_calculation_is_positive():
    data = HPDCInput(
        annual_volume=25000,
        part_weight_kg=0.85,
        material_price_eur_kg=2.5,
        casting_yield=0.65,
        cycle_time_s=35,
        cavities=1,
        machine_rate_eur_h=85,
        oee=0.75,
        labour_rate_eur_h=18,
        operators=0.5,
        scrap_rate=0.03,
        tooling_cost_eur=120000,
        tool_life_shots=150000,
        overhead_rate=0.12,
    )
    result = HPDCModel().calculate(data)
    assert result.total_cost > 0
    assert result.annual_cost == round(result.total_cost * data.annual_volume, 2)
    assert result.total_cost >= result.material_cost


def test_invalid_oee_rejected():
    data = HPDCInput(1, 1, 1, 0.5, 1, 1, 1, 0, 1, 1, 0, 0, 1, 0)
    try:
        HPDCModel().calculate(data)
        assert False, "Expected ValueError"
    except ValueError:
        assert True


def production_input(**overrides):
    values = {
        "annual_volume": 100000,
        "part_weight_kg": 0.2,
        "material_price_eur_kg": 2.5,
        "casting_yield": 0.8,
        "cycle_time_s": 40.0,
        "cavities": 2,
        "machine_rate_eur_h": 85.0,
        "oee": 0.75,
        "labour_rate_eur_h": 18.0,
        "operators": 0.5,
        "scrap_rate": 0.03,
        "tooling_cost_eur": 0.0,
        "tool_life_shots": 150000,
        "overhead_rate": 0.0,
        "number_of_cavities": 2,
        "process_scrap_rate": 0.03,
        "net_part_weight_kg": 0.2,
        "part_length_mm": 80.0,
        "part_width_mm": 40.0,
        "part_height_mm": 30.0,
        "metal_yield": 0.8,
        "cycle_time_predicted_s": 40.0,
        "layout_factor": 1.25,
    }
    values.update(overrides)
    return HPDCInput(**values)


def test_one_cavity_with_zero_process_scrap():
    result = HPDCModel().calculate(
        production_input(
            annual_volume=1000,
            cavities=1,
            number_of_cavities=1,
            scrap_rate=0.0,
            process_scrap_rate=0.0,
        )
    )
    assert result.process_yield == 1
    assert result.gross_parts_per_shot == 1
    assert result.good_parts_per_shot == 1
    assert result.rejected_parts_year == 0


def test_reference_production_output_with_multiple_cavities_and_scrap():
    result = HPDCModel().calculate(production_input())
    assert result.shots_per_hour == pytest.approx(90)
    assert result.gross_parts_per_hour == pytest.approx(180)
    assert result.process_yield == pytest.approx(0.97)
    assert result.good_parts_per_hour == pytest.approx(174.6)
    assert result.gross_parts_required_year == pytest.approx(103092.7835)
    assert result.rejected_parts_year == pytest.approx(3092.7835)
    assert result.required_shots_year == pytest.approx(51546.3918)
    assert result.machine_hours_year == pytest.approx(572.7377)
    assert result.machine_cost_per_good_part == pytest.approx(0.486827)


def test_predicted_cycle_time_is_used_without_override():
    result = HPDCModel().calculate(production_input(cycle_time_predicted_s=32.0))
    assert result.cycle_time_predicted_s == 32.0
    assert result.cycle_time_effective_s == 32.0
    assert result.cycle_time_source == "Predicted"
    assert result.cycle_time_warning is None


def test_cycle_time_override_is_used_by_production_and_cost():
    result = HPDCModel().calculate(
        production_input(cycle_time_predicted_s=40.0, cycle_time_override_s=50.0)
    )
    assert result.cycle_time_effective_s == 50.0
    assert result.cycle_time_source == "User Override"
    assert result.shots_per_hour == pytest.approx(72)
    assert result.machine_hours_year == pytest.approx(
        result.required_shots_year * 50 / 3600
    )
    assert result.machine_cost_per_good_part == pytest.approx(
        85 * 50 / (3600 * 2 * 0.97)
    )


def test_cycle_time_warning_requires_more_than_25_percent_deviation():
    at_threshold = HPDCModel().calculate(
        production_input(cycle_time_override_s=50.0)
    )
    over_threshold = HPDCModel().calculate(
        production_input(cycle_time_override_s=50.1)
    )
    assert at_threshold.cycle_time_warning is None
    assert over_threshold.cycle_time_deviation_percent == pytest.approx(25.25)
    assert over_threshold.cycle_time_warning is not None


def test_scrap_is_not_applied_to_machine_cost_twice():
    result = HPDCModel().calculate(
        production_input(
            oee=1.0,
            labour_rate_eur_h=0.0,
            operators=0.0,
            tooling_cost_eur=0.0,
            process_scrap_rate=0.1,
            scrap_rate=0.1,
        )
    )
    material_gross_cost = 0.2 / 0.8 * 2.5
    assert result.machine_cost_per_good_part == pytest.approx(
        85 * 40 / (3600 * 2 * 0.9)
    )
    assert result.scrap_cost == pytest.approx(
        material_gross_cost * (1 / 0.9 - 1), abs=0.00005
    )
    assert result.total_cost == pytest.approx(
        material_gross_cost + result.machine_cost_per_good_part + result.scrap_cost,
        abs=0.0001,
    )


def test_metal_yield_and_process_scrap_are_separate():
    result = HPDCModel().calculate(
        production_input(
            net_part_weight_kg=0.2,
            metal_yield=0.8,
            process_scrap_rate=0.1,
        )
    )
    assert result.net_part_weight_per_shot_kg == pytest.approx(0.4)
    assert result.total_shot_weight_kg == pytest.approx(0.5)
    assert result.process_yield == pytest.approx(0.9)


def test_hpdc_lookups_accept_central_masterdata_columns():
    material_data = pd.DataFrame(
        {
            "Material_ID": ["A380", "ADC12"],
            "Material_Name": ["A380", "ADC12"],
            "Material_Group": ["Aluminium", "Aluminium"],
            "Density": [2740, 2750],
            "Default_Price_EUR_kg": [2.9, 2.8],
        }
    )

    class Loader:
        def load_excel(self, path, force_refresh=False):
            assert path == "Masterdata/Materials.xlsx"
            return material_data

    service = MasterDataService(Loader(), {"materials": "Masterdata/Materials.xlsx"})
    assert _material_price(service, "A380") == pytest.approx(2.9)
    assert _material_price(service, "ADC12") == pytest.approx(2.8)

    class RegionService:
        def regions(self):
            return pd.DataFrame(
                {
                    "Region Name": ["Austria"],
                    "Labour Rate EUR hr": [27.6],
                }
            )

    assert _labour_rate(RegionService(), "Austria") == pytest.approx(27.6)


def test_hpdc_material_cost_uses_the_selected_masterdata_price():
    class Service:
        def __init__(self):
            self.materials = pd.DataFrame(
                {
                    "Material_Name": ["A380", "ADC12"],
                    "Default_Price_EUR_kg": [2.9, 2.8],
                }
            )

        def material_record(self, name):
            return self.materials.loc[
                self.materials["Material_Name"] == name
            ].iloc[0]

    service = Service()
    a380 = HPDCModel().calculate(
        production_input(material_price_eur_kg=_material_price(service, "A380"))
    )
    adc12 = HPDCModel().calculate(
        production_input(material_price_eur_kg=_material_price(service, "ADC12"))
    )
    assert a380.material_cost == pytest.approx(0.2 / 0.8 * 2.9)
    assert adc12.material_cost == pytest.approx(0.2 / 0.8 * 2.8)
    assert a380.material_cost != adc12.material_cost


def test_missing_hpdc_material_is_a_controlled_masterdata_error():
    class Loader:
        def load_excel(self, path, force_refresh=False):
            return pd.DataFrame(
                {"Material_Name": ["A380"], "Default_Price_EUR_kg": [2.9]}
            )

    service = MasterDataService(Loader(), {"materials": "Masterdata/Materials.xlsx"})
    with pytest.raises(MasterDataError, match="was not found"):
        _material_price(service, "Unknown alloy")


def test_missing_hpdc_material_price_is_a_controlled_masterdata_error():
    class Service:
        def material_record(self, name):
            return pd.Series({"Material_Name": name, "Density": 2740})

    with pytest.raises(MasterDataError, match="expected columns"):
        _material_price(Service(), "A380")


def test_preliminary_layout_estimate_uses_configurable_factor():
    assert calculate_cavity_layout(5, 100, 50, 1.25) == (
        375.0,
        125.0,
        "Estimated cavity layout",
    )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("number_of_cavities", 0),
        ("number_of_cavities", 1.5),
        ("process_scrap_rate", 1.0),
        ("net_part_weight_kg", 0.0),
        ("metal_yield", 0.0),
        ("part_length_mm", 0.0),
        ("cycle_time_predicted_s", 0.0),
        ("cycle_time_override_s", 0.0),
    ],
)
def test_invalid_production_inputs_are_rejected(field, value):
    with pytest.raises(ValueError):
        HPDCModel().calculate(production_input(**{field: value}))
