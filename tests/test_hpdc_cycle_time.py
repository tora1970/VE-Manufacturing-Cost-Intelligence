from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
import yaml

from models.hpdc import HPDCInput, HPDCModel, calculate_total_shot_weight_kg
from services.hpdc_cycle_time import (
    HPDCCycleTimeCalculator,
    HPDCCycleTimeError,
    HPDCCycleTimeInput,
    HPDCCycleTimeParameters,
)


@pytest.fixture
def settings():
    settings_path = Path(__file__).parents[1] / "config" / "settings.yaml"
    with settings_path.open(encoding="utf-8") as settings_file:
        return yaml.safe_load(settings_file)


@pytest.fixture
def calculator(settings):
    parameters = HPDCCycleTimeParameters.from_mapping(
        settings.get("hpdc_cycle_time_v1")
    )
    return HPDCCycleTimeCalculator(parameters)


def test_v1_configuration_replaces_the_fixed_cycle_time_default(settings):
    assert "cycle_time_s" not in settings["hpdc_defaults"]
    assert settings["hpdc_cycle_time_v1"]["model_name"] == "Engineering Estimate V1"


def test_reference_case_reports_cycle_phases_and_assumptions(
    calculator, settings
):
    defaults = settings["hpdc_defaults"]
    shot_weight = calculate_total_shot_weight_kg(
        defaults["part_weight_kg"],
        defaults["cavities"],
        defaults["casting_yield"],
    )

    estimate = calculator.calculate(
        HPDCCycleTimeInput(
            total_shot_weight_kg=shot_weight,
            nominal_wall_thickness_mm=3.0,
        )
    )

    assert shot_weight == pytest.approx(0.85 / 0.65)
    assert estimate.raw_fill_time_s == pytest.approx(shot_weight / 1.5)
    assert estimate.fill_time_s == pytest.approx(shot_weight / 1.5)
    assert estimate.cooling_time_s == pytest.approx(22.5)
    assert estimate.closed_phase_time_s == pytest.approx(22.5)
    assert estimate.predicted_cycle_time_s == pytest.approx(31.5717948718)
    assert estimate.prediction_method == "Engineering Estimate V1"
    assert estimate.prediction_version == "V1"
    assert any("configured assumptions" in note for note in estimate.assumption_notes)
    assert any("overlap" in note for note in estimate.assumption_notes)


def test_cooling_increases_with_wall_thickness_and_uses_configured_exponent(
    calculator,
):
    thin_wall = calculator.calculate(
        HPDCCycleTimeInput(0.9, nominal_wall_thickness_mm=2.0)
    )
    thick_wall = calculator.calculate(
        HPDCCycleTimeInput(0.9, nominal_wall_thickness_mm=4.0)
    )

    assert thick_wall.cooling_time_s > thin_wall.cooling_time_s
    assert thick_wall.cooling_time_s / thin_wall.cooling_time_s == pytest.approx(4.0)


def test_fill_time_changes_with_shot_weight_and_is_bounded(calculator):
    smaller_shot = calculator.calculate(
        HPDCCycleTimeInput(0.3, nominal_wall_thickness_mm=3.0)
    )
    larger_shot = calculator.calculate(
        HPDCCycleTimeInput(0.6, nominal_wall_thickness_mm=3.0)
    )
    below_minimum = calculator.calculate(
        HPDCCycleTimeInput(0.1, nominal_wall_thickness_mm=3.0)
    )
    above_maximum = calculator.calculate(
        HPDCCycleTimeInput(10.0, nominal_wall_thickness_mm=3.0)
    )

    assert smaller_shot.fill_time_s == pytest.approx(0.2)
    assert larger_shot.fill_time_s == pytest.approx(0.4)
    assert below_minimum.fill_time_s == pytest.approx(0.2)
    assert below_minimum.fill_time_bound_applied == "minimum"
    assert below_minimum.warnings
    assert above_maximum.fill_time_s == pytest.approx(3.0)
    assert above_maximum.fill_time_bound_applied == "maximum"
    assert above_maximum.warnings


def test_hold_and_cooling_overlap_instead_of_being_added(calculator):
    parameters = replace(calculator.parameters, hold_time_s=30.0)
    result = HPDCCycleTimeCalculator(parameters).calculate(
        HPDCCycleTimeInput(0.9, nominal_wall_thickness_mm=3.0)
    )

    assert result.closed_phase_time_s == pytest.approx(30.0)
    assert result.predicted_cycle_time_s == pytest.approx(
        result.die_close_time_s
        + result.fill_time_s
        + 30.0
        + result.die_open_time_s
        + result.ejection_time_s
        + result.spray_handling_time_s
    )


@pytest.mark.parametrize(
    ("shot_weight", "wall_thickness"),
    [
        (0.0, 3.0),
        (float("nan"), 3.0),
        (0.9, None),
        (0.9, float("nan")),
        (0.9, 0.0),
        (0.9, 0.4),
        (0.9, 20.1),
    ],
)
def test_invalid_cycle_time_inputs_are_rejected(
    calculator, shot_weight, wall_thickness
):
    with pytest.raises(HPDCCycleTimeError):
        calculator.calculate(
            HPDCCycleTimeInput(
                total_shot_weight_kg=shot_weight,
                nominal_wall_thickness_mm=wall_thickness,
            )
        )


def test_missing_or_invalid_v1_configuration_is_reported():
    with pytest.raises(HPDCCycleTimeError, match="section is required"):
        HPDCCycleTimeParameters.from_mapping(None)
    with pytest.raises(HPDCCycleTimeError, match="Missing"):
        HPDCCycleTimeParameters.from_mapping({})

    settings = {
        "model_name": "Engineering Estimate V1",
        "nominal_wall_thickness_default_mm": 3.0,
        "nominal_wall_thickness_min_mm": 0.5,
        "nominal_wall_thickness_max_mm": 20.0,
        "cooling_coefficient_s_per_mm_n": 2.5,
        "cooling_exponent": 2.0,
        "assumed_fill_rate_kg_s": 1.5,
        "minimum_fill_time_s": 3.0,
        "maximum_fill_time_s": 0.2,
        "die_close_time_s": 2.0,
        "hold_time_s": 2.0,
        "die_open_time_s": 2.0,
        "ejection_time_s": 1.2,
        "spray_handling_time_s": 3.0,
    }
    with pytest.raises(HPDCCycleTimeError, match="maximum_fill_time_s"):
        HPDCCycleTimeParameters.from_mapping(settings)


def test_predicted_and_overridden_cycle_times_flow_into_existing_hpdc_costs(
    calculator,
):
    estimate = calculator.calculate(
        HPDCCycleTimeInput(0.5, nominal_wall_thickness_mm=3.0)
    )
    data = HPDCInput(
        annual_volume=10000,
        part_weight_kg=0.2,
        material_price_eur_kg=2.5,
        casting_yield=0.8,
        cycle_time_s=estimate.predicted_cycle_time_s,
        cavities=2,
        machine_rate_eur_h=85.0,
        oee=0.75,
        labour_rate_eur_h=18.0,
        operators=0.5,
        scrap_rate=0.03,
        tooling_cost_eur=0.0,
        tool_life_shots=150000,
        overhead_rate=0.0,
        number_of_cavities=2,
        process_scrap_rate=0.03,
        net_part_weight_kg=0.2,
        part_length_mm=80.0,
        part_width_mm=40.0,
        part_height_mm=30.0,
        metal_yield=0.8,
        cycle_time_predicted_s=estimate.predicted_cycle_time_s,
        cycle_time_prediction_method=estimate.prediction_method,
    )
    predicted = HPDCModel().calculate(data)

    assert predicted.cycle_time_predicted_s == pytest.approx(
        estimate.predicted_cycle_time_s
    )
    assert predicted.cycle_time_effective_s == pytest.approx(
        estimate.predicted_cycle_time_s
    )
    assert predicted.cycle_time_source == "Engineering Estimate V1"
    assert predicted.machine_cost_per_good_part == pytest.approx(
        85
        * estimate.predicted_cycle_time_s
        / (3600 * 2 * (1 - 0.03))
    )

    overridden = HPDCModel().calculate(
        replace(data, cycle_time_override_s=40.0)
    )
    assert overridden.cycle_time_predicted_s == pytest.approx(
        estimate.predicted_cycle_time_s
    )
    assert overridden.cycle_time_effective_s == pytest.approx(40.0)
    assert overridden.cycle_time_source == "User Override"
    assert overridden.machine_cost_per_good_part == pytest.approx(
        85 * 40 / (3600 * 2 * (1 - 0.03))
    )
