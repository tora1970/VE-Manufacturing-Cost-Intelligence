from dataclasses import FrozenInstanceError

import pytest

from services.production_overhead_calculation import (
    ProductionOverheadInput,
    calculate_production_overhead,
)


def test_production_overhead_reference_calculation():
    result = calculate_production_overhead(
        ProductionOverheadInput(
            machine_cost_per_good_part=0.8379,
            labour_cost_per_good_part=0.1838,
            setup_cost_per_good_part=0.2601,
            production_overhead_rate=0.40,
        )
    )

    assert result.overhead_basis_per_good_part == pytest.approx(1.2818)
    assert result.production_overhead_cost_per_good_part == pytest.approx(0.51272)
    assert result.currency == "EUR"


def test_production_overhead_zero_rate_has_zero_cost():
    result = calculate_production_overhead(
        ProductionOverheadInput(1.0, 2.0, 3.0, 0.0)
    )

    assert result.overhead_basis_per_good_part == 6.0
    assert result.production_overhead_cost_per_good_part == 0.0


@pytest.mark.parametrize(
    "field",
    [
        "machine_cost_per_good_part",
        "labour_cost_per_good_part",
        "setup_cost_per_good_part",
        "production_overhead_rate",
    ],
)
@pytest.mark.parametrize("value", [-0.01, float("nan"), float("inf"), True])
def test_production_overhead_rejects_invalid_values(field, value):
    values = {
        "machine_cost_per_good_part": 1.0,
        "labour_cost_per_good_part": 1.0,
        "setup_cost_per_good_part": 1.0,
        "production_overhead_rate": 0.4,
    }
    values[field] = value

    with pytest.raises(ValueError):
        ProductionOverheadInput(**values)


def test_production_overhead_rejects_non_eur_currency():
    with pytest.raises(ValueError, match="Currency must be 'EUR'"):
        ProductionOverheadInput(1.0, 1.0, 1.0, 0.4, currency="USD")


def test_production_overhead_rejects_non_finite_calculation():
    with pytest.raises(ValueError, match="basis must be finite"):
        calculate_production_overhead(
            ProductionOverheadInput(1e308, 1e308, 0.0, 0.4)
        )


def test_production_overhead_input_is_immutable():
    overhead = ProductionOverheadInput(1.0, 2.0, 3.0, 0.4)

    with pytest.raises(FrozenInstanceError):
        overhead.production_overhead_rate = 0.5
