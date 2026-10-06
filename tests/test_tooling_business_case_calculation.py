import ast
from pathlib import Path

import pytest

from services.tooling_business_case_calculation import (
    calculate_modelled_tooling_business_case,
)


def test_calculates_positive_annual_savings_and_simple_payback():
    result = calculate_modelled_tooling_business_case(
        2.0, 10_000, 20_000, "verified_eur"
    )

    assert result.annual_modelled_recurring_savings_eur == 20_000
    assert result.annual_modelled_recurring_savings_status == "calculated"
    assert result.simple_payback_volume_pcs == 10_000
    assert result.simple_payback_volume_status == "calculated"
    assert result.simple_payback_years == 1.0
    assert result.simple_payback_years_status == "calculated"


def test_zero_annual_savings_is_calculated_without_payback():
    result = calculate_modelled_tooling_business_case(
        0, 10_000, 20_000, "verified_eur"
    )

    assert result.annual_modelled_recurring_savings_eur == 0
    assert result.annual_modelled_recurring_savings_status == "calculated"
    assert result.simple_payback_volume_status == "not_applicable"
    assert result.simple_payback_years_status == "not_applicable"


def test_negative_annual_savings_are_preserved_without_payback():
    result = calculate_modelled_tooling_business_case(
        -2, 10_000, 20_000, "verified_eur"
    )

    assert result.annual_modelled_recurring_savings_eur == -20_000
    assert (
        result.annual_modelled_recurring_savings_status == "negative_but_valid"
    )
    assert result.simple_payback_volume_status == "not_applicable"
    assert result.simple_payback_years_status == "not_applicable"


@pytest.mark.parametrize("savings", [0, -2])
def test_zero_or_negative_savings_makes_payback_not_applicable(savings):
    result = calculate_modelled_tooling_business_case(
        savings, 10_000, 20_000, "verified_eur"
    )

    assert result.simple_payback_volume_pcs is None
    assert result.simple_payback_volume_status == "not_applicable"
    assert result.simple_payback_years is None
    assert result.simple_payback_years_status == "not_applicable"


def test_zero_capex_makes_payback_not_applicable():
    result = calculate_modelled_tooling_business_case(
        2, 10_000, 0, "verified_eur"
    )

    assert result.annual_modelled_recurring_savings_eur == 20_000
    assert result.simple_payback_volume_status == "not_applicable"
    assert result.simple_payback_years_status == "not_applicable"


@pytest.mark.parametrize(
    ("savings", "volume", "capex"),
    [
        ("invalid", 10_000, 20_000),
        (None, 10_000, 20_000),
        (float("nan"), 10_000, 20_000),
        (float("inf"), 10_000, 20_000),
        (-float("inf"), 10_000, 20_000),
        (2, "invalid", 20_000),
        (2, None, 20_000),
        (2, float("nan"), 20_000),
        (2, float("inf"), 20_000),
        (2, -float("inf"), 20_000),
    ],
)
def test_invalid_required_annual_savings_input_is_unavailable(
    savings, volume, capex
):
    result = calculate_modelled_tooling_business_case(
        savings, volume, capex, "verified_eur"
    )

    assert result.annual_modelled_recurring_savings_eur is None
    assert result.annual_modelled_recurring_savings_status == "unavailable"
    assert result.simple_payback_volume_status == "unavailable"
    assert result.simple_payback_years_status == "unavailable"


def test_non_positive_annual_volume_is_unavailable():
    for volume in (0, -1):
        result = calculate_modelled_tooling_business_case(
            2, volume, 20_000, "verified_eur"
        )
        assert result.annual_modelled_recurring_savings_status == "unavailable"


@pytest.mark.parametrize(
    "capex",
    [
        None,
        "invalid",
        float("nan"),
        float("inf"),
        -float("inf"),
        -1,
    ],
)
def test_invalid_capex_makes_positive_savings_payback_unavailable(capex):
    result = calculate_modelled_tooling_business_case(
        2, 10_000, capex, "verified_eur"
    )

    assert result.annual_modelled_recurring_savings_status == "calculated"
    assert result.simple_payback_volume_status == "unavailable"
    assert result.simple_payback_years_status == "unavailable"


@pytest.mark.parametrize("currency_status", ["unavailable", "unverified", None])
def test_unverified_currency_blocks_all_calculations(currency_status):
    result = calculate_modelled_tooling_business_case(
        2, 10_000, 20_000, currency_status
    )

    assert result.annual_modelled_recurring_savings_status == "unavailable"
    assert result.simple_payback_volume_status == "unavailable"
    assert result.simple_payback_years_status == "unavailable"


def test_calculations_are_not_rounded_internally():
    result = calculate_modelled_tooling_business_case(
        1 / 3, 1, 1, "verified_eur"
    )

    assert result.annual_modelled_recurring_savings_eur == 1 / 3
    assert result.annual_modelled_recurring_savings_eur != 0.33
    assert result.simple_payback_volume_pcs == 3
    assert result.simple_payback_years == 3


def test_non_finite_derived_values_are_unavailable():
    result = calculate_modelled_tooling_business_case(
        float.fromhex("0x1.fffffffffffffp+1023"),
        2,
        20_000,
        "verified_eur",
    )

    assert result.annual_modelled_recurring_savings_eur is None
    assert result.annual_modelled_recurring_savings_status == "unavailable"


def test_overflowing_payback_is_unavailable_without_losing_annual_savings():
    result = calculate_modelled_tooling_business_case(
        float.fromhex("0x0.0000000000001p-1022"),
        1,
        float.fromhex("0x1.fffffffffffffp+1023"),
        "verified_eur",
    )

    assert result.annual_modelled_recurring_savings_status == "calculated"
    assert result.simple_payback_volume_pcs is None
    assert result.simple_payback_volume_status == "unavailable"
    assert result.simple_payback_years is None
    assert result.simple_payback_years_status == "unavailable"


def _app_tree():
    app_path = Path(__file__).resolve().parents[1] / "app.py"
    return ast.parse(app_path.read_text(encoding="utf-8"))


def _assignment_values(tree, name):
    return [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == name
            for target in node.targets
        )
    ]


def test_existing_recurring_savings_formulas_remain_unchanged():
    tree = _app_tree()
    savings_values = _assignment_values(tree, "savings_eur")
    percentage_values = _assignment_values(tree, "savings_pct")

    assert any(
        ast.unparse(value) == "current_price_value - total_should_cost"
        for value in savings_values
    )
    assert any(
        ast.unparse(value) == "savings_eur / current_price_value * 100"
        for value in percentage_values
    )


def test_capex_does_not_enter_recurring_cost_breakdown_or_total():
    tree = _app_tree()
    breakdown = next(
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "cost_breakdown"
            for target in node.targets
        )
    )
    assert isinstance(breakdown, ast.Dict)
    entries = {
        key.value: value
        for key, value in zip(breakdown.keys, breakdown.values)
        if isinstance(key, ast.Constant) and isinstance(key.value, str)
    }
    assert ast.literal_eval(entries["tooling_cost"]) == 0.0

    total_values = _assignment_values(tree, "total_should_cost")
    assert any(
        ast.unparse(value) == "sum(cost_breakdown.values())"
        for value in total_values
    )


def test_business_case_service_is_called_exactly_once():
    calls = [
        node
        for node in ast.walk(_app_tree())
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "calculate_modelled_tooling_business_case"
    ]

    assert len(calls) == 1
    assert [ast.unparse(arg) for arg in calls[0].args] == [
        "savings_eur",
        "annual_volume",
        "tooling_capex_eur",
        "currency_status",
    ]


def test_no_first_year_roi_irr_npv_or_realized_savings_calculation_exists():
    names = {
        node.id.lower()
        for node in ast.walk(_app_tree())
        if isinstance(node, ast.Name)
    }
    forbidden_fragments = (
        "first_year_net_benefit",
        "realized_savings",
        "roi",
        "irr",
        "npv",
    )
    assert not any(
        fragment in name
        for name in names
        for fragment in forbidden_fragments
    )
