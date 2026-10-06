import pytest

from services.machine_cost_calculation import calculate_machine_cost


def test_calculates_machine_cost_for_45_seconds():
    assert calculate_machine_cost(45, 80) == (1.0, "calculated")


def test_calculates_one_hour_of_machine_time():
    assert calculate_machine_cost(3600, 125) == (125.0, "calculated")


def test_accepts_float_cycle_time():
    cost, status = calculate_machine_cost(22.5, 80)
    assert cost == 0.5
    assert status == "calculated"


def test_accepts_numeric_string_inputs():
    assert calculate_machine_cost("45", "80") == (1.0, "calculated")


def test_zero_machine_rate_is_a_valid_calculation():
    assert calculate_machine_cost(45, 0) == (0.0, "calculated")


@pytest.mark.parametrize(
    "cycle_time",
    [
        None,
        0,
        -1,
        "not numeric",
        float("nan"),
        float("inf"),
        float("-inf"),
    ],
)
def test_invalid_cycle_time_is_unavailable(cycle_time):
    assert calculate_machine_cost(cycle_time, 80) == (None, "unavailable")


@pytest.mark.parametrize(
    "machine_rate",
    [
        None,
        -1,
        "not numeric",
        float("nan"),
        float("inf"),
        float("-inf"),
    ],
)
def test_invalid_machine_rate_is_unavailable(machine_rate):
    assert calculate_machine_cost(45, machine_rate) == (None, "unavailable")


def test_missing_machine_rate_does_not_become_zero():
    cost, status = calculate_machine_cost(45, None)
    assert cost is None
    assert cost != 0.0
    assert status == "unavailable"


def test_calculation_is_not_rounded_internally():
    cost, status = calculate_machine_cost(1, 1)
    assert status == "calculated"
    assert cost == 1 / 3600
    assert cost != round(cost, 2)


def test_overflowing_result_is_unavailable():
    assert calculate_machine_cost(
        float.fromhex("0x1.fffffffffffffp+1023"),
        float.fromhex("0x1.fffffffffffffp+1023"),
    ) == (None, "unavailable")
