import ast
from pathlib import Path

import pytest

from services.tooling_capex_status import classify_tooling_capex_status


def test_positive_capex_and_volume_are_ready_for_analysis():
    assert classify_tooling_capex_status(25000, 500000) == "ready_for_analysis"


def test_zero_capex_and_volume_are_not_provided():
    assert classify_tooling_capex_status(0, 0) == "not_provided"


def test_positive_capex_without_volume_is_incomplete():
    assert classify_tooling_capex_status(25000, 0) == "incomplete"


def test_volume_without_positive_capex_is_incomplete():
    assert classify_tooling_capex_status(0, 500000) == "incomplete"


@pytest.mark.parametrize("capex, volume", [(-1, 1), (1, -1), (-1, -1)])
def test_negative_inputs_are_rejected(capex, volume):
    with pytest.raises(ValueError):
        classify_tooling_capex_status(capex, volume)


@pytest.mark.parametrize(
    "capex, volume",
    [("not numeric", 1), (1, "not numeric"), (None, 1), (1, None)],
)
def test_non_numeric_inputs_are_unavailable(capex, volume):
    assert classify_tooling_capex_status(capex, volume) == "unavailable"


def test_status_helper_returns_only_a_status_and_does_not_allocate_cost():
    result = classify_tooling_capex_status(25000, 500000)
    assert result == "ready_for_analysis"
    assert not isinstance(result, tuple)
    assert "cost_per_part" not in result


def _app_tree():
    app_path = Path(__file__).resolve().parents[1] / "app.py"
    return ast.parse(app_path.read_text(encoding="utf-8"))


def test_tooling_capex_is_not_added_to_cost_breakdown():
    tree = _app_tree()
    cost_breakdown = next(
        node.value
        for node in ast.walk(tree)
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
        if isinstance(key, ast.Constant) and isinstance(key.value, str)
    }
    assert "tooling_capex_eur" not in entries
    assert ast.literal_eval(entries["tooling_cost"]) == 0.0


def test_recurring_total_sum_expression_remains_unchanged():
    tree = _app_tree()
    total_assignment = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "total_should_cost"
            for target in node.targets
        )
        and isinstance(node.value, ast.Call)
    )
    assert ast.unparse(total_assignment.value) == "sum(cost_breakdown.values())"


def test_recurring_savings_formulas_remain_unchanged():
    tree = _app_tree()
    assignments = {
        target.id: []
        for node in ast.walk(tree)
        if isinstance(node, ast.Assign)
        for target in node.targets
        if isinstance(target, ast.Name)
        and target.id in {"savings_eur", "savings_pct"}
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in assignments:
                    assignments[target.id].append(ast.unparse(node.value))

    assert "current_price_value - total_should_cost" in assignments["savings_eur"]
    assert "savings_eur / current_price_value * 100" in assignments["savings_pct"]
