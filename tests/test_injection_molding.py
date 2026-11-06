import pytest

from models.injection_molding import InjectionMoldingInput


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


def test_valid_input_is_accepted():
    valid_input().validate()


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
