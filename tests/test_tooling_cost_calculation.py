import ast
import math
from pathlib import Path

import pytest

from services.tooling_cost_calculation import (
    calculate_analytical_tooling_cost,
)


@pytest.mark.parametrize(
    ("capex", "volume", "expected"),
    [
        (25_000, 500_000, 0.05),
        (40_000, 500_000, 0.08),
    ],
)
def test_calculates_analytical_tooling_cost(capex, volume, expected):
    assert calculate_analytical_tooling_cost(capex, volume) == (
        expected,
        "calculated",
    )


def test_accepts_float_capex():
    assert calculate_analytical_tooling_cost(25_000.0, 500_000) == (
        0.05,
        "calculated",
    )


def test_accepts_float_amortization_volume():
    assert calculate_analytical_tooling_cost(25_000, 500_000.0) == (
        0.05,
        "calculated",
    )


def test_accepts_numeric_string_inputs():
    assert calculate_analytical_tooling_cost("25000", "500000") == (
        0.05,
        "calculated",
    )


def test_zero_capex_with_positive_volume_is_calculated():
    assert calculate_analytical_tooling_cost(0.0, 500_000) == (
        0.0,
        "calculated",
    )


@pytest.mark.parametrize(
    ("capex", "volume"),
    [
        (None, 500_000),
        (-1, 500_000),
        ("not numeric", 500_000),
        (math.nan, 500_000),
        (math.inf, 500_000),
        (-math.inf, 500_000),
    ],
)
def test_unavailable_capex_returns_unavailable(capex, volume):
    assert calculate_analytical_tooling_cost(capex, volume) == (
        None,
        "unavailable",
    )


@pytest.mark.parametrize(
    ("capex", "volume"),
    [
        (25_000, None),
        (25_000, 0),
        (25_000, -1),
        (25_000, "not numeric"),
        (25_000, math.nan),
        (25_000, math.inf),
        (25_000, -math.inf),
    ],
)
def test_unavailable_amortization_volume_returns_unavailable(capex, volume):
    assert calculate_analytical_tooling_cost(capex, volume) == (
        None,
        "unavailable",
    )


def test_missing_inputs_do_not_default_to_zero_or_one():
    assert calculate_analytical_tooling_cost(None, None) == (
        None,
        "unavailable",
    )
    assert calculate_analytical_tooling_cost(None, 1) == (
        None,
        "unavailable",
    )
    assert calculate_analytical_tooling_cost(0, None) == (
        None,
        "unavailable",
    )


def test_calculation_is_not_rounded_internally():
    result, status = calculate_analytical_tooling_cost(1, 3)

    assert status == "calculated"
    assert result == 1 / 3
    assert result != 0.33


def test_non_finite_calculation_result_is_unavailable():
    assert calculate_analytical_tooling_cost(
        float.fromhex("0x1.fffffffffffffp+1023"),
        float.fromhex("0x0.0000000000001p-1022"),
    ) == (None, "unavailable")


def _app_source():
    app_path = Path(__file__).resolve().parents[1] / "app.py"
    return app_path.read_text(encoding="utf-8")


def _app_tree():
    return ast.parse(_app_source())


def _cost_breakdown_assignments(tree):
    return [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Subscript)
            and isinstance(target.value, ast.Name)
            and target.value.id == "cost_breakdown"
            for target in node.targets
        )
    ]


def test_tooling_cost_remains_zero_in_recurring_cost_breakdown():
    cost_breakdown = next(
        node.value
        for node in ast.walk(_app_tree())
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "cost_breakdown"
            for target in node.targets
        )
    )
    assert isinstance(cost_breakdown, ast.Dict)
    entries = {
        key.value: value
        for key, value in zip(cost_breakdown.keys, cost_breakdown.values)
        if isinstance(key, ast.Constant) and key.value == "tooling_cost"
    }
    assert ast.literal_eval(entries["tooling_cost"]) == 0.0


def test_tooling_capex_is_not_assigned_into_cost_breakdown():
    for assignment in _cost_breakdown_assignments(_app_tree()):
        assigned_names = {
            node.id
            for node in ast.walk(assignment.value)
            if isinstance(node, ast.Name)
        }
        assert "tooling_capex_eur" not in assigned_names


def test_analytical_tooling_cost_is_not_assigned_into_cost_breakdown():
    for assignment in _cost_breakdown_assignments(_app_tree()):
        assigned_names = {
            node.id
            for node in ast.walk(assignment.value)
            if isinstance(node, ast.Name)
        }
        assert "analytical_tooling_cost_per_part_eur" not in assigned_names


def test_recurring_savings_uses_current_price_minus_total_should_cost():
    savings_assignments = [
        node.value
        for node in ast.walk(_app_tree())
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "savings_eur"
            for target in node.targets
        )
    ]

    assert any(
        ast.unparse(expression) == "current_price_value - total_should_cost"
        for expression in savings_assignments
    )


def test_analytical_fully_loaded_cost_adds_tooling_to_recurring_total():
    assignments = [
        node
        for node in ast.walk(_app_tree())
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name)
            and target.id == "analytical_fully_loaded_cost_per_part_eur"
            for target in node.targets
        )
    ]

    assert any(
        isinstance(node.value, ast.BinOp)
        and isinstance(node.value.op, ast.Add)
        and ast.unparse(node.value)
        == "total_should_cost + analytical_tooling_cost_per_part_eur"
        for node in assignments
    )


def test_analytical_tooling_calculator_is_called_exactly_once():
    calls = [
        node
        for node in ast.walk(_app_tree())
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "calculate_analytical_tooling_cost"
    ]

    assert len(calls) == 1


def test_app_has_no_payback_calculation():
    names = {
        node.id.lower()
        for node in ast.walk(_app_tree())
        if isinstance(node, ast.Name)
    }
    assert "payback" not in names


def test_app_has_no_roi_irr_or_npv_calculation():
    names = {
        node.id.lower()
        for node in ast.walk(_app_tree())
        if isinstance(node, ast.Name)
    }
    assert names.isdisjoint({"roi", "irr", "npv"})
