import pytest

from models.injection_molding import (
    InjectionMoldingBaseProcessInput,
    InjectionMoldingInput,
    InjectionMoldingModel,
)
from services.cost_engine import CostEngine


def valid_input(**overrides):
    values = dict(
        annual_volume=25000,
        part_weight_kg=0.1,
        material_price_eur_kg=3.0,
        material_utilization=0.90,
        cycle_time_s=30,
        cavities=2,
        machine_rate_eur_h=75,
        oee=0.80,
        labour_rate_eur_h=18,
        operators=0.5,
        scrap_rate=0.02,
        tooling_cost_eur=80000,
        tool_life_shots=500000,
        overhead_rate=0.10,
    )
    values.update(overrides)
    return InjectionMoldingInput(**values)


def base_process_input(**overrides):
    values = dict(
        part_weight_kg=0.1,
        material_price_eur_kg=3.0,
        material_utilization=0.90,
        cycle_time_s=30,
        cavities=2,
        machine_rate_eur_h=75,
        oee=0.80,
        labour_rate_eur_h=18,
        operators=0.5,
        scrap_rate=0.02,
        overhead_rate=0.10,
        currency="EUR",
    )
    values.update(overrides)
    return InjectionMoldingBaseProcessInput(**values)


def test_valid_input_is_accepted():
    valid_input().validate()


def test_base_process_input_validates_without_tooling_fields():
    data = base_process_input()

    data.validate()
    result = InjectionMoldingModel().calculate_base_process(data)

    assert result.currency == data.currency
    assert not hasattr(data, "tooling_cost_eur")
    assert not hasattr(data, "tool_life_shots")


def test_base_process_attempt_costs_match_legacy_result():
    legacy_data = valid_input()
    base_data = base_process_input()

    legacy_result = InjectionMoldingModel().calculate(legacy_data)
    base_result = InjectionMoldingModel().calculate_base_process(base_data)

    assert base_result.material_cost_per_attempt == legacy_result.material_cost
    assert base_result.machine_cost_per_attempt == legacy_result.machine_cost
    assert base_result.labour_cost_per_attempt == legacy_result.labour_cost


def test_valid_input_has_deterministic_cost_breakdown():
    result = InjectionMoldingModel().calculate(valid_input())

    assert result.material_cost == 0.3333
    assert result.machine_cost == 0.3906
    assert result.labour_cost == 0.0469
    assert result.tooling_cost == 0.08
    assert result.scrap_cost == 0.0174
    assert result.overhead_cost == 0.0868
    assert result.total_cost == 0.955
    assert result.total_cost > 0


def test_annual_cost_uses_rounded_total_cost():
    data = valid_input()

    result = InjectionMoldingModel().calculate(data)

    assert result.annual_cost == 23875.0
    assert result.annual_cost == round(result.total_cost * data.annual_volume, 2)


def test_material_cost_uses_material_utilization():
    result = InjectionMoldingModel().calculate(valid_input())

    assert result.material_cost == 0.3333


def test_machine_cost_is_amortized_across_cavities():
    result = InjectionMoldingModel().calculate(valid_input(cavities=4))

    assert result.machine_cost == 0.1953


def test_tooling_cost_is_amortized_across_cavities():
    result = InjectionMoldingModel().calculate(valid_input(cavities=4))

    assert result.tooling_cost == 0.04


def test_lower_oee_increases_machine_and_labour_costs():
    model = InjectionMoldingModel()
    baseline = model.calculate(valid_input())
    lower_oee = model.calculate(valid_input(oee=0.4))

    assert lower_oee.machine_cost == 0.7812
    assert lower_oee.labour_cost == 0.0938
    assert lower_oee.machine_cost > baseline.machine_cost
    assert lower_oee.labour_cost > baseline.labour_cost


def test_zero_scrap_rate_has_no_scrap_cost():
    result = InjectionMoldingModel().calculate(valid_input(scrap_rate=0))

    assert result.scrap_cost == 0


def test_positive_scrap_rate_adds_scrap_cost():
    result = InjectionMoldingModel().calculate(valid_input(scrap_rate=0.02))

    assert result.scrap_cost == 0.0174


def test_zero_overhead_rate_has_no_overhead_cost():
    result = InjectionMoldingModel().calculate(valid_input(overhead_rate=0))

    assert result.overhead_cost == 0


def test_cost_engine_calculates_injection_molding_cost():
    data = valid_input()

    result = CostEngine().calculate(InjectionMoldingModel(), data)

    assert result.total_cost == 0.955


def test_currency_is_propagated_to_cost_breakdown():
    result = InjectionMoldingModel().calculate(valid_input(currency="USD"))

    assert result.currency == "USD"


@pytest.mark.parametrize(
    "field,value",
    [
        ("annual_volume", 0),
        ("part_weight_kg", 0),
        ("material_price_eur_kg", 0),
        ("cycle_time_s", 0),
        ("cavities", 0),
        ("machine_rate_eur_h", 0),
        ("oee", 0),
        ("tool_life_shots", 0),
    ],
)
def test_positive_values_are_required(field, value):
    data = valid_input(**{field: value})

    with pytest.raises(ValueError):
        data.validate()


@pytest.mark.parametrize(
    "value",
    [0, -0.1, 1.01],
)
def test_invalid_material_utilization_rejected(value):
    with pytest.raises(ValueError):
        valid_input(
            material_utilization=value
        ).validate()


@pytest.mark.parametrize(
    "field,value",
    [
        ("scrap_rate", -0.01),
        ("scrap_rate", 1.0),
        ("overhead_rate", -0.01),
        ("overhead_rate", 1.0),
    ],
)
def test_invalid_rates_rejected(field, value):
    with pytest.raises(ValueError):
        valid_input(**{field: value}).validate()


@pytest.mark.parametrize(
    "field",
    [
        "operators",
        "labour_rate_eur_h",
        "tooling_cost_eur",
    ],
)
def test_negative_cost_inputs_rejected(field):
    with pytest.raises(ValueError):
        valid_input(**{field: -1}).validate()
