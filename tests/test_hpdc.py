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
    assert result.total_cost == pytest.approx(
        round(result.recurring_manufacturing_should_cost, 4)
    )
    assert result.annual_cost == round(
        result.recurring_manufacturing_should_cost * data.annual_volume, 2
    )
    assert result.annual_recurring_manufacturing_cost == result.annual_cost
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


def test_material_overhead_defaults_to_five_percent_of_material_cost():
    result = HPDCModel().calculate(production_input())

    assert production_input().material_overhead_pct == 5.0
    assert result.material_overhead_pct == 5.0
    assert result.material_overhead_cost_eur == pytest.approx(
        round(result.material_cost_per_good_part * 0.05, 4)
    )


def test_material_overhead_override_uses_only_material_and_is_not_in_production_base():
    data = production_input(
        material_overhead_pct=25.0,
        overhead_rate=0.2,
        trim_required=False,
    )
    result = HPDCModel().calculate(data)

    assert result.material_overhead_pct == 25.0
    assert result.material_overhead_cost_eur == pytest.approx(
        round(result.material_cost_per_good_part * 0.25, 4)
    )
    assert result.overhead_base_per_good_part == pytest.approx(
        result.machine_cost_per_good_part + result.labour_cost_per_good_part
    )
    assert result.overhead_cost == pytest.approx(
        round(result.overhead_base_per_good_part * data.overhead_rate, 4)
    )
    assert result.recurring_manufacturing_should_cost == pytest.approx(
        result.material_cost_per_good_part
        + result.material_overhead_cost_eur
        + result.machine_cost_per_good_part
        + result.labour_cost_per_good_part
        + result.overhead_cost,
        abs=3e-5,
    )


def test_zero_material_overhead_adds_no_cost():
    result = HPDCModel().calculate(
        production_input(material_overhead_pct=0.0)
    )

    assert result.material_overhead_pct == 0.0
    assert result.material_overhead_cost_eur == 0.0


@pytest.mark.parametrize(
    "material_overhead_pct",
    [-0.01, 100.0, float("nan"), float("inf"), True],
)
def test_invalid_material_overhead_percent_is_rejected(material_overhead_pct):
    with pytest.raises(ValueError, match="material_overhead_pct"):
        HPDCModel().calculate(
            production_input(material_overhead_pct=material_overhead_pct)
        )


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
    assert result.trim_cycles_per_shot == pytest.approx(1)
    assert result.trim_time_required_per_shot_s == pytest.approx(40 * 0.167)
    assert result.rejected_parts_year == 0


def test_trim_disabled_does_not_change_hpdc_cost_or_takt():
    with_trim = HPDCModel().calculate(production_input())
    without_trim = HPDCModel().calculate(
        production_input(trim_required=False)
    )

    assert without_trim.trim_required is False
    assert without_trim.trim_cycle_time_s is None
    assert without_trim.trim_cycles_per_shot == 0
    assert without_trim.trim_time_required_per_shot_s == 0
    assert without_trim.effective_takt_s == pytest.approx(
        without_trim.hpdc_cycle_time_s
    )
    assert without_trim.trim_bottleneck is False
    assert without_trim.recurring_manufacturing_should_cost == pytest.approx(
        with_trim.recurring_manufacturing_should_cost
    )


def test_trim_cycle_defaults_to_16_7_percent_of_hpdc_cycle():
    result = HPDCModel().calculate(
        production_input(
            cycle_time_predicted_s=60.0,
            number_of_cavities=4,
            cavities=4,
            process_scrap_rate=0.0,
        )
    )

    assert result.hpdc_cycle_time_s == pytest.approx(60)
    assert result.trim_cycle_time_s == pytest.approx(10.02)
    assert "engineering assumption" in result.trim_cycle_time_source.lower()
    assert "not masterdata" in result.trim_cycle_time_source.lower()
    assert result.good_parts_per_shot == pytest.approx(4)
    assert result.trim_cycles_per_shot == pytest.approx(4)
    assert result.trim_time_required_per_shot_s == pytest.approx(40.08)
    assert result.effective_takt_s == pytest.approx(60)
    assert result.trim_bottleneck is False
    assert result.machine_cost_per_good_part == pytest.approx(
        85 * 60 / (3600 * 4)
    )


def test_user_entered_trim_cycle_time_and_trim_bottleneck():
    result = HPDCModel().calculate(
        production_input(
            cycle_time_predicted_s=60.0,
            number_of_cavities=4,
            cavities=4,
            process_scrap_rate=0.0,
            trim_cycle_time_s=20.0,
            trim_parts_per_cycle=1,
        )
    )

    assert result.trim_cycle_time_s == pytest.approx(20)
    assert result.trim_cycle_time_source == "User-entered"
    assert result.good_parts_per_shot == pytest.approx(4)
    assert result.trim_cycles_per_shot == pytest.approx(4)
    assert result.trim_time_required_per_shot_s == pytest.approx(80)
    assert result.effective_takt_s == pytest.approx(80)
    assert result.trim_bottleneck is True


def test_trim_parts_per_cycle_reduces_station_load_for_multiple_cavities():
    result = HPDCModel().calculate(
        production_input(
            cycle_time_predicted_s=60.0,
            number_of_cavities=4,
            cavities=4,
            process_scrap_rate=0.0,
            trim_cycle_time_s=10.0,
            trim_parts_per_cycle=2,
        )
    )

    assert result.good_parts_per_shot == pytest.approx(4)
    assert result.trim_cycles_per_shot == pytest.approx(2)
    assert result.trim_time_required_per_shot_s == pytest.approx(20)
    assert result.effective_takt_s == pytest.approx(60)
    assert result.trim_bottleneck is False


def test_trim_machine_cost_is_not_required_when_trim_is_disabled():
    result = HPDCModel().calculate(
        production_input(
            trim_required=False,
            trim_machine_rate_eur_hr=30.0,
        )
    )

    assert result.trim_machine_cost_per_shot_eur == 0
    assert result.trim_machine_cost_eur_per_good_part == 0
    assert result.trim_machine_cost_status == "not_required"
    assert result.recurring_manufacturing_should_cost == pytest.approx(
        result.material_cost_per_good_part
        + result.material_overhead_cost_eur
        + result.machine_cost_per_good_part
        + result.labour_cost_per_good_part
        + result.overhead_cost,
        abs=3e-5,
    )


def test_missing_trim_machine_rate_preserves_time_without_cost():
    result = HPDCModel().calculate(
        production_input(
            trim_cycle_time_s=10.0,
            trim_parts_per_cycle=1,
        )
    )

    assert result.trim_machine_rate_eur_hr is None
    assert result.trim_machine_rate_source == "missing"
    assert result.trim_machine_time_per_shot_s == pytest.approx(19.4)
    assert result.trim_machine_cost_per_shot_eur == 0
    assert result.trim_machine_cost_eur_per_good_part == 0
    assert result.trim_machine_cost_status == "rate_missing"


@pytest.mark.parametrize(
    (
        "trim_parts_per_cycle",
        "expected_trim_cycles",
        "expected_time_per_shot",
        "expected_cost_per_shot",
        "expected_cost_per_good_part",
    ),
    [
        (4, 1, 10, 10 / 3600 * 30, (10 / 3600 * 30) / 4),
        (1, 4, 40, 40 / 3600 * 30, (40 / 3600 * 30) / 4),
        (2, 2, 20, 20 / 3600 * 30, (20 / 3600 * 30) / 4),
    ],
)
def test_trim_machine_cost_uses_existing_trim_cycle_capacity(
    trim_parts_per_cycle,
    expected_trim_cycles,
    expected_time_per_shot,
    expected_cost_per_shot,
    expected_cost_per_good_part,
):
    result = HPDCModel().calculate(
        production_input(
            cycle_time_predicted_s=60.0,
            cavities=4,
            number_of_cavities=4,
            process_scrap_rate=0.0,
            trim_cycle_time_s=10.0,
            trim_parts_per_cycle=trim_parts_per_cycle,
            trim_machine_rate_eur_hr=30.0,
        )
    )

    assert result.good_parts_per_shot == pytest.approx(4)
    assert result.trim_cycles_per_shot == pytest.approx(expected_trim_cycles)
    assert result.trim_machine_rate_eur_hr == pytest.approx(30)
    assert result.trim_machine_rate_source == "user_input"
    assert result.trim_machine_time_per_shot_s == pytest.approx(
        expected_time_per_shot
    )
    assert result.trim_machine_cost_per_shot_eur == pytest.approx(
        expected_cost_per_shot
    )
    assert result.trim_machine_cost_eur_per_good_part == pytest.approx(
        expected_cost_per_good_part
    )
    assert result.trim_machine_cost_status == "calculated"


def test_trim_masterdata_selection_and_rate_source_are_exposed_in_result():
    result = HPDCModel().calculate(
        production_input(
            trim_cycle_time_s=10.0,
            trim_parts_per_cycle=1,
            trim_machine="Trim / Medium",
            trim_machine_rate_eur_hr=30.0,
            trim_machine_rate_source="Masterdata/Machine.xlsx",
        )
    )

    assert result.trim_machine == "Trim / Medium"
    assert result.trim_machine_rate_eur_hr == 30.0
    assert result.trim_machine_rate_source == "Masterdata/Machine.xlsx"
    assert result.trim_machine_cost_eur_per_good_part == pytest.approx(
        result.trim_machine_time_per_shot_s
        / 3600
        * result.trim_machine_rate_eur_hr
        / result.good_parts_per_shot
    )


def test_fractional_trim_cycles_are_used_without_rounding_for_cost():
    result = HPDCModel().calculate(
        production_input(
            process_scrap_rate=0.1,
            trim_cycle_time_s=10.0,
            trim_parts_per_cycle=1,
            trim_machine_rate_eur_hr=30.0,
        )
    )

    assert result.trim_cycles_per_shot == pytest.approx(1.8)
    assert result.trim_machine_time_per_shot_s == pytest.approx(18)
    assert result.trim_machine_cost_per_shot_eur == pytest.approx(
        18 / 3600 * 30
    )
    assert result.trim_machine_cost_eur_per_good_part == pytest.approx(
        (18 / 3600 * 30) / 1.8
    )


def test_zero_good_parts_is_rejected_before_trim_cost_division():
    with pytest.raises(ValueError, match="process_scrap_rate"):
        HPDCModel().calculate(
            production_input(
                process_scrap_rate=1.0,
                trim_machine_rate_eur_hr=30.0,
            )
        )


@pytest.mark.parametrize(
    "rate",
    [-1.0, float("nan"), float("inf"), float("-inf"), "not numeric", True],
)
def test_invalid_trim_machine_rates_are_rejected(rate):
    with pytest.raises(ValueError, match="trim_machine_rate_eur_hr"):
        HPDCModel().calculate(
            production_input(trim_machine_rate_eur_hr=rate)
        )


def test_zero_trim_machine_rate_is_valid_but_distinct_from_missing():
    result = HPDCModel().calculate(
        production_input(trim_machine_rate_eur_hr=0.0)
    )

    assert result.trim_machine_cost_status == "calculated"
    assert result.trim_machine_rate_source == "user_input"
    assert result.trim_machine_cost_per_shot_eur == 0
    assert result.trim_machine_cost_eur_per_good_part == 0


def test_trim_machine_cost_is_added_once_without_changing_hpdc_cost_or_capacity():
    without_rate = HPDCModel().calculate(
        production_input(
            cycle_time_predicted_s=60.0,
            cavities=4,
            number_of_cavities=4,
            process_scrap_rate=0.0,
            trim_cycle_time_s=10.0,
            trim_parts_per_cycle=4,
        )
    )
    with_rate = HPDCModel().calculate(
        production_input(
            cycle_time_predicted_s=60.0,
            cavities=4,
            number_of_cavities=4,
            process_scrap_rate=0.0,
            trim_cycle_time_s=10.0,
            trim_parts_per_cycle=4,
            trim_machine_rate_eur_hr=30.0,
        )
    )

    assert with_rate.recurring_manufacturing_should_cost == pytest.approx(
        without_rate.recurring_manufacturing_should_cost
        + with_rate.trim_machine_cost_eur_per_good_part
    )
    assert with_rate.annual_recurring_manufacturing_cost == pytest.approx(
        with_rate.recurring_manufacturing_should_cost * 100000
    )
    assert with_rate.machine_cost_per_good_part == pytest.approx(
        without_rate.machine_cost_per_good_part
    )
    assert with_rate.hpdc_cycle_time_s == pytest.approx(
        without_rate.hpdc_cycle_time_s
    )
    assert with_rate.effective_takt_s == pytest.approx(
        without_rate.effective_takt_s
    )
    assert with_rate.trim_bottleneck == without_rate.trim_bottleneck
    assert with_rate.trim_cycles_per_shot == without_rate.trim_cycles_per_shot


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


def test_process_scrap_is_applied_once_to_each_recurring_cost_component():
    result = HPDCModel().calculate(
        production_input(
            oee=1.0,
            labour_rate_eur_h=18.0,
            operators=0.5,
            tooling_cost_eur=0.0,
            process_scrap_rate=0.1,
            scrap_rate=0.1,
        )
    )
    material_gross_cost = 0.2 / 0.8 * 2.5
    labour_gross_cost = 40 / 3600 * 18 * 0.5 / 2
    assert result.machine_cost_per_good_part == pytest.approx(
        85 * 40 / (3600 * 2 * 0.9)
    )
    assert result.material_cost_per_gross_part == pytest.approx(material_gross_cost)
    assert result.material_cost_per_good_part == pytest.approx(
        material_gross_cost / 0.9
    )
    assert result.labour_cost_per_gross_part == pytest.approx(labour_gross_cost)
    assert result.labour_cost_per_good_part == pytest.approx(labour_gross_cost / 0.9)
    assert result.process_yield == pytest.approx(0.9)
    assert result.scrap_cost == 0.0
    assert result.tooling_cost == 0.0
    assert result.recurring_manufacturing_should_cost == pytest.approx(
        result.material_cost_per_good_part
        + result.material_overhead_cost_eur
        + result.machine_cost_per_good_part
        + result.labour_cost_per_good_part
        + result.overhead_cost,
        abs=3e-5,
    )


def test_reference_case_separates_recurring_cost_from_tooling_capex():
    result = HPDCModel().calculate(
        production_input(
            annual_volume=10000,
            part_weight_kg=0.85,
            net_part_weight_kg=0.85,
            material_price_eur_kg=2.9,
            metal_yield=0.65,
            casting_yield=0.65,
            cycle_time_s=31.57179487179487,
            cycle_time_predicted_s=31.57179487179487,
            cavities=1,
            number_of_cavities=1,
            machine_rate_eur_h=70,
            oee=0.75,
            labour_rate_eur_h=14.98,
            operators=0.5,
            tooling_cost_eur=120000,
            tool_life_shots=150000,
            process_scrap_rate=0.03,
            scrap_rate=0.03,
            overhead_rate=0.12,
        )
    )

    assert result.material_cost_per_gross_part == pytest.approx(
        3.792307692307692
    )
    assert result.material_cost_per_good_part == pytest.approx(
        3.909595559080095
    )
    assert result.machine_cost_per_gross_part == pytest.approx(
        0.6138960113960115
    )
    assert result.machine_cost_per_good_part == pytest.approx(
        0.6328824859752695
    )
    assert result.labour_cost_per_gross_part == pytest.approx(
        0.08758249762583097
    )
    assert result.labour_cost_per_good_part == pytest.approx(
        0.09029123466580512
    )
    assert result.overhead_base_per_good_part == pytest.approx(
        0.7231737206410747
    )
    assert result.overhead_cost == pytest.approx(0.08678084647692895, abs=0.00005)
    assert result.material_overhead_cost_eur == pytest.approx(
        result.material_cost_per_good_part * 0.05, abs=0.00005
    )
    assert result.recurring_manufacturing_should_cost == pytest.approx(
        4.915029904152102
    )
    assert result.annual_recurring_manufacturing_cost == pytest.approx(
        49150.30
    )
    assert result.tooling_investment_eur == 120000
    assert result.tool_life_shots == 150000
    assert result.number_of_cavities == 1
    assert result.tool_life_gross_parts == 150000
    assert result.tooling_cost == 0
    assert result.scrap_cost == 0
    serialized = result.to_dict()
    assert serialized["tooling_cost"] == 0
    assert serialized["scrap_cost"] == 0
    assert serialized["tooling_investment_eur"] == 120000
    assert serialized["tool_life_gross_parts"] == 150000


def test_tooling_inputs_do_not_change_recurring_cost_or_overhead():
    baseline = HPDCModel().calculate(production_input(tooling_cost_eur=0))
    changed_capex = HPDCModel().calculate(
        production_input(tooling_cost_eur=500000, tool_life_shots=250000)
    )

    assert changed_capex.recurring_manufacturing_should_cost == pytest.approx(
        baseline.recurring_manufacturing_should_cost
    )
    assert changed_capex.annual_recurring_manufacturing_cost == pytest.approx(
        baseline.annual_recurring_manufacturing_cost
    )
    assert changed_capex.overhead_cost == pytest.approx(baseline.overhead_cost)
    assert changed_capex.scrap_cost == baseline.scrap_cost == 0
    assert changed_capex.tooling_cost == baseline.tooling_cost == 0
    assert changed_capex.tooling_investment_eur == 500000
    assert changed_capex.tool_life_shots == 250000
    assert changed_capex.tool_life_gross_parts == 500000


def test_overhead_basis_excludes_material_tooling_and_scrap():
    baseline = HPDCModel().calculate(production_input())
    changed_excluded_costs = HPDCModel().calculate(
        production_input(
            material_price_eur_kg=100,
            tooling_cost_eur=500000,
            process_scrap_rate=0.03,
            scrap_rate=0.03,
        )
    )

    assert baseline.overhead_base_per_good_part == pytest.approx(
        baseline.machine_cost_per_good_part
        + baseline.labour_cost_per_good_part
    )
    assert changed_excluded_costs.overhead_base_per_good_part == pytest.approx(
        baseline.overhead_base_per_good_part
    )
    assert changed_excluded_costs.overhead_cost == pytest.approx(
        baseline.overhead_cost
    )


def test_increasing_process_scrap_increases_each_good_part_cost_once():
    no_scrap = HPDCModel().calculate(
        production_input(process_scrap_rate=0.0, scrap_rate=0.0)
    )
    with_scrap = HPDCModel().calculate(
        production_input(process_scrap_rate=0.1, scrap_rate=0.1)
    )

    assert with_scrap.process_yield == pytest.approx(0.9)
    assert with_scrap.material_cost_per_good_part == pytest.approx(
        no_scrap.material_cost_per_good_part / 0.9
    )
    assert with_scrap.machine_cost_per_good_part == pytest.approx(
        no_scrap.machine_cost_per_good_part / 0.9
    )
    assert with_scrap.labour_cost_per_good_part == pytest.approx(
        no_scrap.labour_cost_per_good_part / 0.9
    )
    assert with_scrap.tooling_investment_eur == no_scrap.tooling_investment_eur
    assert with_scrap.tool_life_gross_parts == no_scrap.tool_life_gross_parts
    assert with_scrap.scrap_cost == 0


def test_tool_life_gross_parts_and_machine_productivity_scale_with_cavities():
    result = HPDCModel().calculate(
        production_input(
            cavities=4,
            number_of_cavities=4,
            tooling_cost_eur=120000,
            tool_life_shots=150000,
        )
    )

    assert result.tool_life_gross_parts == 600000
    assert result.number_of_cavities == 4
    assert result.gross_parts_per_hour == pytest.approx(
        result.shots_per_hour * 4
    )
    assert result.machine_cost_per_good_part == pytest.approx(
        85 * 40 / (3600 * 4 * (1 - 0.03))
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
    assert result.material_cost_per_gross_part == pytest.approx(0.2 / 0.8 * 2.5)
    assert result.material_cost_per_good_part == pytest.approx(
        (0.2 / 0.8 * 2.5) / 0.9
    )


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
    assert a380.material_cost_per_good_part == pytest.approx(
        (0.2 / 0.8 * 2.9) / 0.97
    )
    assert adc12.material_cost_per_good_part == pytest.approx(
        (0.2 / 0.8 * 2.8) / 0.97
    )
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
        ("trim_cycle_time_s", 0.0),
        ("trim_parts_per_cycle", 0),
        ("trim_parts_per_cycle", 1.5),
        ("trim_required", 1),
    ],
)
def test_invalid_production_inputs_are_rejected(field, value):
    with pytest.raises(ValueError):
        HPDCModel().calculate(production_input(**{field: value}))
