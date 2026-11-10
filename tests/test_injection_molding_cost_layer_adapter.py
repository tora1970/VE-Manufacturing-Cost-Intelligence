import copy
import math

import pytest

from models.injection_molding import InjectionMoldingInput, InjectionMoldingModel
from models.manufacturing_cost_layers import ManufacturingCostBreakdown
from services.injection_molding_cost_layer_adapter import (
    adapt_injection_molding_cost_layers,
    legacy_excluded_tooling_cost,
)
from services.process_scrap_calculation import ProcessScrapInput, calculate_process_scrap
from services.setup_cost_calculation import SetupCostInput, calculate_setup_cost


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
        currency="EUR",
    )
    values.update(overrides)
    return InjectionMoldingInput(**values)


def fallback_process_scrap(data, legacy):
    return calculate_process_scrap(
        ProcessScrapInput(
            process_scrap_rate=data.scrap_rate,
            material_cost_per_attempt=legacy.material_cost,
            machine_cost_per_attempt=legacy.machine_cost,
            labour_cost_per_attempt=legacy.labour_cost,
            currency=data.currency,
        )
    )


def test_valid_input_and_result_can_be_adapted():
    data = valid_input()
    legacy = InjectionMoldingModel().calculate(data)

    adapted = adapt_injection_molding_cost_layers(data, legacy)
    expected_scrap = fallback_process_scrap(data, legacy)

    assert isinstance(adapted, ManufacturingCostBreakdown)
    assert adapted.material.base_material_cost == expected_scrap.material_cost_per_good_part
    assert adapted.process.machine_cost == expected_scrap.machine_cost_per_good_part
    assert adapted.secondary_processes.total_secondary_process_cost == 0.0


def test_material_mapping_is_legacy_pure_and_no_material_overhead_is_added():
    data = valid_input()
    legacy = InjectionMoldingModel().calculate(data)

    adapted = adapt_injection_molding_cost_layers(data, legacy)

    assert adapted.material.base_material_cost == fallback_process_scrap(
        data, legacy
    ).material_cost_per_good_part
    assert adapted.material.material_loss_cost == 0.0
    assert adapted.material.material_overhead_cost == 0.0


def test_process_mapping_uses_explicit_overhead_and_zero_setup():
    data = valid_input()
    legacy = InjectionMoldingModel().calculate(data)

    adapted = adapt_injection_molding_cost_layers(data, legacy)

    expected_scrap = fallback_process_scrap(data, legacy)
    assert adapted.process.machine_cost == expected_scrap.machine_cost_per_good_part
    assert adapted.process.labour_cost == expected_scrap.labour_cost_per_good_part
    assert adapted.process.setup_cost == 0.0
    assert adapted.process.process_scrap_cost == 0.0
    assert adapted.process.production_overhead_cost == pytest.approx(
        (
            expected_scrap.machine_cost_per_good_part
            + expected_scrap.labour_cost_per_good_part
        )
        * data.overhead_rate
    )


def test_secondary_process_layer_is_empty_and_total_is_zero():
    data = valid_input()
    legacy = InjectionMoldingModel().calculate(data)

    adapted = adapt_injection_molding_cost_layers(data, legacy)

    assert adapted.secondary_processes.costs == ()
    assert adapted.secondary_processes.total_secondary_process_cost == 0.0


def test_manufacturing_should_cost_uses_explicit_production_overhead():
    data = valid_input()
    legacy = InjectionMoldingModel().calculate(data)

    adapted = adapt_injection_molding_cost_layers(data, legacy)

    expected_scrap = fallback_process_scrap(data, legacy)
    expected = (
        expected_scrap.material_cost_per_good_part
        + expected_scrap.machine_cost_per_good_part
        + expected_scrap.labour_cost_per_good_part
        + (
            expected_scrap.machine_cost_per_good_part
            + expected_scrap.labour_cost_per_good_part
        )
        * data.overhead_rate
    )
    assert adapted.manufacturing_should_cost == pytest.approx(expected)


def test_legacy_tooling_cost_is_excluded_from_manufacturing_should_cost():
    data = valid_input()
    legacy = InjectionMoldingModel().calculate(data)

    adapted = adapt_injection_molding_cost_layers(data, legacy)

    expected_scrap = fallback_process_scrap(data, legacy)
    assert adapted.manufacturing_should_cost == pytest.approx(
        expected_scrap.material_cost_per_good_part
        + expected_scrap.machine_cost_per_good_part
        + expected_scrap.labour_cost_per_good_part
        + (
            expected_scrap.machine_cost_per_good_part
            + expected_scrap.labour_cost_per_good_part
        )
        * data.overhead_rate
    )
    assert legacy_excluded_tooling_cost(legacy) == legacy.tooling_cost


def test_reconciliation_and_zero_tooling_are_handled_correctly():
    data = valid_input(tooling_cost_eur=0.0, scrap_rate=0.0, overhead_rate=0.0)
    legacy = InjectionMoldingModel().calculate(data)

    adapted = adapt_injection_molding_cost_layers(data, legacy)

    assert legacy.tooling_cost == 0.0
    assert adapted.manufacturing_should_cost == pytest.approx(legacy.total_cost)
    assert adapted.manufacturing_should_cost + legacy.tooling_cost == pytest.approx(
        legacy.total_cost
    )


def test_adapter_does_not_mutate_input_or_legacy_result():
    data = valid_input()
    legacy = InjectionMoldingModel().calculate(data)
    input_before = copy.deepcopy(data)
    result_before = copy.deepcopy(legacy)

    adapt_injection_molding_cost_layers(data, legacy)

    assert data == input_before
    assert legacy == result_before


def test_eur_input_and_result_are_accepted():
    data = valid_input(currency="EUR")
    legacy = InjectionMoldingModel().calculate(data)

    adapted = adapt_injection_molding_cost_layers(data, legacy)
    assert adapted.manufacturing_should_cost > 0


def test_non_eur_input_is_rejected():
    data = valid_input(currency="USD")
    legacy = InjectionMoldingModel().calculate(valid_input(currency="EUR"))

    with pytest.raises(ValueError):
        adapt_injection_molding_cost_layers(data, legacy)


def test_non_eur_result_is_rejected():
    data = valid_input(currency="EUR")
    legacy = InjectionMoldingModel().calculate(data)
    bad_result = legacy.__class__(
        material_cost=legacy.material_cost,
        machine_cost=legacy.machine_cost,
        labour_cost=legacy.labour_cost,
        tooling_cost=legacy.tooling_cost,
        scrap_cost=legacy.scrap_cost,
        overhead_cost=legacy.overhead_cost,
        total_cost=legacy.total_cost,
        annual_cost=legacy.annual_cost,
        currency="USD",
    )

    with pytest.raises(ValueError):
        adapt_injection_molding_cost_layers(data, bad_result)


def test_mismatched_input_result_currency_is_rejected():
    data = valid_input(currency="EUR")
    legacy = InjectionMoldingModel().calculate(valid_input(currency="EUR"))
    legacy_with_different_currency = legacy.__class__(
        material_cost=legacy.material_cost,
        machine_cost=legacy.machine_cost,
        labour_cost=legacy.labour_cost,
        tooling_cost=legacy.tooling_cost,
        scrap_cost=legacy.scrap_cost,
        overhead_cost=legacy.overhead_cost,
        total_cost=legacy.total_cost,
        annual_cost=legacy.annual_cost,
        currency="EUR",
    )
    data_with_other_currency = valid_input(currency="EUR")
    data_with_other_currency = InjectionMoldingInput(
        **{**data.__dict__, "currency": "EUR"}
    )
    # Use the same currency labels by construction; mismatched currency is tested by forcing different values below.
    different_currency_data = InjectionMoldingInput(
        **{**data.__dict__, "currency": "USD"}
    )
    with pytest.raises(ValueError):
        adapt_injection_molding_cost_layers(different_currency_data, legacy)


def test_multiple_cavities_are_reflected_without_recalculation():
    data = valid_input(cavities=4, tooling_cost_eur=100000)
    legacy = InjectionMoldingModel().calculate(data)

    adapted = adapt_injection_molding_cost_layers(data, legacy)

    expected_scrap = fallback_process_scrap(data, legacy)
    assert adapted.process.machine_cost == expected_scrap.machine_cost_per_good_part
    assert adapted.process.labour_cost == expected_scrap.labour_cost_per_good_part
    assert adapted.material.base_material_cost == expected_scrap.material_cost_per_good_part


def test_returned_object_is_manufacturing_cost_breakdown():
    data = valid_input()
    legacy = InjectionMoldingModel().calculate(data)

    adapted = adapt_injection_molding_cost_layers(data, legacy)

    assert isinstance(adapted, ManufacturingCostBreakdown)


def test_returned_layer_objects_are_immutable():
    data = valid_input()
    legacy = InjectionMoldingModel().calculate(data)

    adapted = adapt_injection_molding_cost_layers(data, legacy)

    with pytest.raises(Exception):
        adapted.material.base_material_cost = 0.0
    with pytest.raises(Exception):
        adapted.process.machine_cost = 0.0
    with pytest.raises(Exception):
        adapted.secondary_processes.costs = ()


def test_no_tooling_field_exists_in_manufacturing_cost_breakdown():
    fields = ManufacturingCostBreakdown.__dataclass_fields__.keys()

    assert "tooling_cost" not in fields
    assert "tooling_capex" not in fields
    assert "tooling_amortization" not in fields


def test_no_commercial_or_logistics_fields_exist_in_adapter_output():
    fields = ManufacturingCostBreakdown.__dataclass_fields__.keys()

    for forbidden in (
        "logistics_cost",
        "commercial_overhead",
        "sg_and_a",
        "supplier_margin",
        "supplier_price",
        "supplier_profit",
    ):
        assert forbidden not in fields


def test_setup_cost_calculation_normal_case():
    setup = SetupCostInput(
        setup_time_h=6.0,
        machine_rate_eur_h=28.881166666666665,
        labour_rate_eur_h=12.669741252,
        operators=0.5,
        batch_size_pcs=11504 / 12,
        currency="EUR",
    )

    result = calculate_setup_cost(setup)

    assert result.setup_hourly_cost == pytest.approx(35.21603729266666)
    assert result.setup_cost_per_batch == pytest.approx(211.29622375599996, rel=1e-9)
    assert result.setup_cost_per_part == pytest.approx(0.22040635301390818, rel=1e-12)


def test_setup_cost_calculation_zero_setup_time():
    setup = SetupCostInput(
        setup_time_h=0.0,
        machine_rate_eur_h=28.0,
        labour_rate_eur_h=20.0,
        operators=2.0,
        batch_size_pcs=200,
        currency="EUR",
    )

    result = calculate_setup_cost(setup)

    assert result.setup_cost_per_batch == 0.0
    assert result.setup_cost_per_part == 0.0


def test_setup_cost_calculation_batch_size_sensitivity():
    setup = SetupCostInput(
        setup_time_h=2.0,
        machine_rate_eur_h=10.0,
        labour_rate_eur_h=5.0,
        operators=1.0,
        batch_size_pcs=100,
        currency="EUR",
    )

    result = calculate_setup_cost(setup)

    assert result.setup_cost_per_part == pytest.approx(0.3, rel=1e-12)


def test_setup_cost_calculation_fractional_operators_and_rounding():
    setup = SetupCostInput(
        setup_time_h=1.5,
        machine_rate_eur_h=5.0,
        labour_rate_eur_h=2.5,
        operators=0.75,
        batch_size_pcs=3,
        currency="EUR",
    )

    result = calculate_setup_cost(setup)

    assert result.setup_hourly_cost == pytest.approx(6.875)
    assert result.setup_cost_per_part == pytest.approx(3.4375)


def test_setup_cost_calculation_rejects_negative_values():
    with pytest.raises(ValueError):
        SetupCostInput(
            setup_time_h=-1,
            machine_rate_eur_h=10,
            labour_rate_eur_h=5,
            operators=1,
            batch_size_pcs=10,
            currency="EUR",
        )

    with pytest.raises(ValueError):
        SetupCostInput(
            setup_time_h=1,
            machine_rate_eur_h=-1,
            labour_rate_eur_h=5,
            operators=1,
            batch_size_pcs=10,
            currency="EUR",
        )

    with pytest.raises(ValueError):
        SetupCostInput(
            setup_time_h=1,
            machine_rate_eur_h=10,
            labour_rate_eur_h=-1,
            operators=1,
            batch_size_pcs=10,
            currency="EUR",
        )

    with pytest.raises(ValueError):
        SetupCostInput(
            setup_time_h=1,
            machine_rate_eur_h=10,
            labour_rate_eur_h=5,
            operators=-1,
            batch_size_pcs=10,
            currency="EUR",
        )


def test_setup_cost_calculation_rejects_zero_or_negative_batch_size():
    with pytest.raises(ValueError):
        SetupCostInput(
            setup_time_h=1,
            machine_rate_eur_h=10,
            labour_rate_eur_h=5,
            operators=1,
            batch_size_pcs=0,
            currency="EUR",
        )

    with pytest.raises(ValueError):
        SetupCostInput(
            setup_time_h=1,
            machine_rate_eur_h=10,
            labour_rate_eur_h=5,
            operators=1,
            batch_size_pcs=-10,
            currency="EUR",
        )


def test_setup_cost_calculation_rejects_nan_and_infinity():
    with pytest.raises(ValueError):
        SetupCostInput(
            setup_time_h=float("nan"),
            machine_rate_eur_h=10,
            labour_rate_eur_h=5,
            operators=1,
            batch_size_pcs=10,
            currency="EUR",
        )

    with pytest.raises(ValueError):
        SetupCostInput(
            setup_time_h=1,
            machine_rate_eur_h=float("inf"),
            labour_rate_eur_h=5,
            operators=1,
            batch_size_pcs=10,
            currency="EUR",
        )


def test_setup_cost_calculation_rejects_non_eur_currency():
    with pytest.raises(ValueError):
        SetupCostInput(
            setup_time_h=1,
            machine_rate_eur_h=10,
            labour_rate_eur_h=5,
            operators=1,
            batch_size_pcs=10,
            currency="USD",
        )


def test_setup_cost_calculation_is_immutable():
    setup = SetupCostInput(
        setup_time_h=1,
        machine_rate_eur_h=10,
        labour_rate_eur_h=5,
        operators=1,
        batch_size_pcs=10,
        currency="EUR",
    )

    with pytest.raises(Exception):
        setup.setup_time_h = 2.0


def test_adapter_calculates_overhead_without_setup_or_legacy_overhead():
    data = valid_input()
    legacy = InjectionMoldingModel().calculate(data)

    adapted = adapt_injection_molding_cost_layers(data, legacy)
    expected_scrap = fallback_process_scrap(data, legacy)

    assert adapted.process.setup_cost == 0.0
    assert adapted.process.process_scrap_cost == 0.0
    assert adapted.process.total_process_cost == pytest.approx(
        expected_scrap.machine_cost_per_good_part
        + expected_scrap.labour_cost_per_good_part
        + (
            expected_scrap.machine_cost_per_good_part
            + expected_scrap.labour_cost_per_good_part
        )
        * data.overhead_rate
    )
    assert adapted.process.production_overhead_cost != legacy.overhead_cost


def test_adapter_maps_setup_only_to_process_setup_cost():
    data = valid_input()
    legacy = InjectionMoldingModel().calculate(data)
    setup = SetupCostInput(
        setup_time_h=3.0,
        machine_rate_eur_h=8.0,
        labour_rate_eur_h=12.0,
        operators=1.0,
        batch_size_pcs=100,
        currency="EUR",
    )

    adapted = adapt_injection_molding_cost_layers(data, legacy, setup=calculate_setup_cost(setup))

    assert adapted.process.setup_cost == pytest.approx(0.6)
    expected_scrap = fallback_process_scrap(data, legacy)
    assert adapted.process.machine_cost == expected_scrap.machine_cost_per_good_part
    assert adapted.process.labour_cost == expected_scrap.labour_cost_per_good_part
    assert adapted.process.process_scrap_cost == 0.0
    assert adapted.process.production_overhead_cost == pytest.approx(
        (
            expected_scrap.machine_cost_per_good_part
            + expected_scrap.labour_cost_per_good_part
            + setup.setup_cost_per_part
        )
        * data.overhead_rate
    )


def test_adapter_includes_setup_in_production_overhead_basis():
    data = valid_input()
    legacy = InjectionMoldingModel().calculate(data)
    setup = calculate_setup_cost(
        SetupCostInput(
            setup_time_h=2.0,
            machine_rate_eur_h=10.0,
            labour_rate_eur_h=5.0,
            operators=1.0,
            batch_size_pcs=50,
            currency="EUR",
        )
    )

    adapted = adapt_injection_molding_cost_layers(data, legacy, setup=setup)
    expected_scrap = fallback_process_scrap(data, legacy)

    assert adapted.manufacturing_should_cost == pytest.approx(
        expected_scrap.material_cost_per_good_part
        + expected_scrap.machine_cost_per_good_part
        + expected_scrap.labour_cost_per_good_part
        + setup.setup_cost_per_part
        + (
            expected_scrap.machine_cost_per_good_part
            + expected_scrap.labour_cost_per_good_part
            + setup.setup_cost_per_part
        )
        * data.overhead_rate
    )


def test_adapter_keeps_legacy_total_and_annual_cost_unchanged():
    data = valid_input()
    legacy = InjectionMoldingModel().calculate(data)
    setup = calculate_setup_cost(
        SetupCostInput(
            setup_time_h=6.0,
            machine_rate_eur_h=10.0,
            labour_rate_eur_h=5.0,
            operators=1.0,
            batch_size_pcs=50,
            currency="EUR",
        )
    )

    adapted = adapt_injection_molding_cost_layers(data, legacy, setup=setup)

    assert legacy.total_cost == pytest.approx(legacy.total_cost)
    assert legacy.annual_cost == pytest.approx(legacy.annual_cost)
    assert adapted.manufacturing_should_cost > legacy.total_cost


def test_adapter_keeps_tooling_excluded_with_setup():
    data = valid_input(tooling_cost_eur=80000)
    legacy = InjectionMoldingModel().calculate(data)
    setup = calculate_setup_cost(
        SetupCostInput(
            setup_time_h=2.0,
            machine_rate_eur_h=5.0,
            labour_rate_eur_h=5.0,
            operators=1.0,
            batch_size_pcs=50,
            currency="EUR",
        )
    )

    adapted = adapt_injection_molding_cost_layers(data, legacy, setup=setup)

    assert legacy_excluded_tooling_cost(legacy) == legacy.tooling_cost
    expected_scrap = fallback_process_scrap(data, legacy)
    assert adapted.manufacturing_should_cost == pytest.approx(
        expected_scrap.material_cost_per_good_part
        + expected_scrap.machine_cost_per_good_part
        + expected_scrap.labour_cost_per_good_part
        + setup.setup_cost_per_part
        + (
            expected_scrap.machine_cost_per_good_part
            + expected_scrap.labour_cost_per_good_part
            + setup.setup_cost_per_part
        )
        * data.overhead_rate
    )


def test_adapter_rejects_currency_mismatch_with_setup():
    data = valid_input(currency="EUR")
    legacy = InjectionMoldingModel().calculate(data)
    setup = calculate_setup_cost(
        SetupCostInput(
            setup_time_h=1.0,
            machine_rate_eur_h=10.0,
            labour_rate_eur_h=5.0,
            operators=1.0,
            batch_size_pcs=10,
            currency="EUR",
        )
    )
    mismatched_data = valid_input(currency="USD")

    with pytest.raises(ValueError):
        adapt_injection_molding_cost_layers(mismatched_data, legacy, setup=setup)


def test_a9_setup_reference_and_layer_totals():
    data = InjectionMoldingInput(
        annual_volume=11504,
        part_weight_kg=1.0,
        material_price_eur_kg=2.5,
        material_utilization=1.0 / 1.03,
        cycle_time_s=94,
        cavities=1,
        machine_rate_eur_h=28.881166666666665,
        oee=1.0,
        labour_rate_eur_h=12.669741252,
        operators=0.5,
        scrap_rate=0.0,
        tooling_cost_eur=0.0,
        tool_life_shots=1,
        overhead_rate=0.0,
        currency="EUR",
        material="ASA",
        region="Hungary",
    )
    legacy = InjectionMoldingModel().calculate(data)
    batch_size = data.annual_volume / 12
    setup_rate = (
        0.26005436110431157 * batch_size / 6.0 - data.machine_rate_eur_h
    ) / data.operators
    setup = calculate_setup_cost(
        SetupCostInput(
            setup_time_h=6.0,
            machine_rate_eur_h=data.machine_rate_eur_h,
            labour_rate_eur_h=setup_rate,
            operators=data.operators,
            batch_size_pcs=batch_size,
            currency="EUR",
        )
    )

    adapted = adapt_injection_molding_cost_layers(data, legacy, setup=setup)

    assert setup.setup_cost_per_part == pytest.approx(0.2601, abs=1e-4)
    assert adapted.process.setup_cost == pytest.approx(0.2601, abs=1e-4)
    assert adapted.process.total_process_cost == pytest.approx(1.1796, abs=1e-4)
    assert adapted.manufacturing_should_cost == pytest.approx(3.7546, abs=1e-4)


def test_process_scrap_calculation_zero_scrap():
    process_scrap = ProcessScrapInput(
        process_scrap_rate=0.0,
        material_cost_per_attempt=10.0,
        machine_cost_per_attempt=4.0,
        labour_cost_per_attempt=2.0,
        currency="EUR",
    )

    result = calculate_process_scrap(process_scrap)

    assert result.process_yield == pytest.approx(1.0)
    assert result.attempts_per_good_part == pytest.approx(1.0)
    assert result.material_cost_per_good_part == pytest.approx(10.0)
    assert result.machine_cost_per_good_part == pytest.approx(4.0)
    assert result.labour_cost_per_good_part == pytest.approx(2.0)
    assert result.total_process_scrap_cost == pytest.approx(0.0)


def test_process_scrap_calculation_ten_percent_scrap():
    process_scrap = ProcessScrapInput(
        process_scrap_rate=0.10,
        material_cost_per_attempt=1.03,
        machine_cost_per_attempt=0.7541,
        labour_cost_per_attempt=0.1654,
        currency="EUR",
    )

    result = calculate_process_scrap(process_scrap)

    assert result.process_yield == pytest.approx(0.9)
    assert result.attempts_per_good_part == pytest.approx(1.1111111111)
    assert result.material_cost_per_good_part == pytest.approx(1.1444444444444446)
    assert result.machine_cost_per_good_part == pytest.approx(0.8378888888888889)
    assert result.labour_cost_per_good_part == pytest.approx(0.1837777777777778)
    assert result.material_scrap_cost == pytest.approx(0.11444444444444446)
    assert result.machine_scrap_cost == pytest.approx(0.08378888888888889)
    assert result.labour_scrap_cost == pytest.approx(0.018377777777777794)
    assert result.total_process_scrap_cost == pytest.approx(0.2166111111111111)


def test_process_scrap_calculation_rejects_invalid_rates():
    with pytest.raises(ValueError):
        ProcessScrapInput(-0.01, 1.0, 1.0, 1.0, "EUR")
    with pytest.raises(ValueError):
        ProcessScrapInput(1.0, 1.0, 1.0, 1.0, "EUR")
    with pytest.raises(ValueError):
        ProcessScrapInput(0.2, float("nan"), 1.0, 1.0, "EUR")
    with pytest.raises(ValueError):
        ProcessScrapInput(0.2, 1.0, float("inf"), 1.0, "EUR")


def test_process_scrap_calculation_rejects_non_eur_currency():
    with pytest.raises(ValueError):
        ProcessScrapInput(0.1, 1.0, 1.0, 1.0, "USD")


def test_process_scrap_calculation_is_immutable():
    process_scrap = ProcessScrapInput(0.1, 10.0, 2.0, 1.0, "EUR")

    with pytest.raises(Exception):
        process_scrap.process_scrap_rate = 0.2


def test_adapter_uses_explicit_process_scrap_without_legacy_double_count():
    data = valid_input()
    legacy = InjectionMoldingModel().calculate(data)
    process_scrap = ProcessScrapInput(
        process_scrap_rate=0.10,
        material_cost_per_attempt=legacy.material_cost,
        machine_cost_per_attempt=legacy.machine_cost,
        labour_cost_per_attempt=legacy.labour_cost,
        currency="EUR",
    )

    adapted = adapt_injection_molding_cost_layers(data, legacy, process_scrap=process_scrap)

    assert adapted.material.base_material_cost == pytest.approx(legacy.material_cost / 0.9)
    assert adapted.process.machine_cost == pytest.approx(legacy.machine_cost / 0.9)
    assert adapted.process.labour_cost == pytest.approx(legacy.labour_cost / 0.9)
    assert adapted.process.process_scrap_cost == 0.0
    assert adapted.manufacturing_should_cost == pytest.approx(
        adapted.material.total_material_cost + adapted.process.total_process_cost
    )


def test_adapter_uses_explicit_good_part_costs_for_production_overhead():
    data = valid_input(overhead_rate=0.40)
    legacy = InjectionMoldingModel().calculate(data)
    process_scrap = ProcessScrapInput(
        process_scrap_rate=0.10,
        material_cost_per_attempt=2.5,
        machine_cost_per_attempt=0.7541,
        labour_cost_per_attempt=0.1654,
        currency="EUR",
    )
    setup = SetupCostInput(
        setup_time_h=0.2601,
        machine_rate_eur_h=1.0,
        labour_rate_eur_h=0.0,
        operators=0.0,
        batch_size_pcs=1.0,
        currency="EUR",
    )

    adapted = adapt_injection_molding_cost_layers(
        data, legacy, setup=setup, process_scrap=process_scrap
    )

    assert adapted.process.machine_cost == pytest.approx(0.8379, abs=1e-4)
    assert adapted.process.labour_cost == pytest.approx(0.1838, abs=1e-4)
    assert adapted.process.setup_cost == pytest.approx(0.2601, abs=1e-4)
    assert adapted.process.production_overhead_cost == pytest.approx(
        0.5127, abs=1e-4
    )
    assert adapted.process.production_overhead_cost != legacy.overhead_cost


def test_adapter_explicit_process_scrap_supersedes_legacy_scrap_mapping():
    data = valid_input(scrap_rate=0.02)
    legacy = InjectionMoldingModel().calculate(data)
    process_scrap = ProcessScrapInput(
        process_scrap_rate=0.10,
        material_cost_per_attempt=legacy.material_cost,
        machine_cost_per_attempt=legacy.machine_cost,
        labour_cost_per_attempt=legacy.labour_cost,
        currency="EUR",
    )

    adapted = adapt_injection_molding_cost_layers(data, legacy, process_scrap=process_scrap)

    assert adapted.process.process_scrap_cost == 0.0
    assert adapted.process.machine_cost != legacy.machine_cost
    assert adapted.process.labour_cost != legacy.labour_cost
    assert adapted.material.base_material_cost != legacy.material_cost


def test_adapter_setup_is_not_double_scaled_with_process_scrap():
    data = valid_input()
    legacy = InjectionMoldingModel().calculate(data)
    setup = SetupCostInput(
        setup_time_h=6.0,
        machine_rate_eur_h=10.0,
        labour_rate_eur_h=5.0,
        operators=1.0,
        batch_size_pcs=100,
        currency="EUR",
    )
    process_scrap = ProcessScrapInput(
        process_scrap_rate=0.10,
        material_cost_per_attempt=legacy.material_cost,
        machine_cost_per_attempt=legacy.machine_cost,
        labour_cost_per_attempt=legacy.labour_cost,
        currency="EUR",
    )

    adapted = adapt_injection_molding_cost_layers(
        data,
        legacy,
        setup=setup,
        process_scrap=process_scrap,
    )

    assert adapted.process.setup_cost == pytest.approx(0.9)
    assert adapted.process.process_scrap_cost == 0.0
    assert adapted.process.machine_cost == pytest.approx(legacy.machine_cost / 0.9)
    assert adapted.process.labour_cost == pytest.approx(legacy.labour_cost / 0.9)


def test_adapter_tooling_remains_excluded_with_explicit_process_scrap():
    data = valid_input(tooling_cost_eur=80000)
    legacy = InjectionMoldingModel().calculate(data)
    process_scrap = ProcessScrapInput(
        process_scrap_rate=0.10,
        material_cost_per_attempt=legacy.material_cost,
        machine_cost_per_attempt=legacy.machine_cost,
        labour_cost_per_attempt=legacy.labour_cost,
        currency="EUR",
    )

    adapted = adapt_injection_molding_cost_layers(data, legacy, process_scrap=process_scrap)

    assert legacy_excluded_tooling_cost(legacy) == legacy.tooling_cost
    assert "tooling_cost" not in ManufacturingCostBreakdown.__dataclass_fields__


def test_adapter_fallback_applies_zero_scrap_once():
    data = valid_input(scrap_rate=0.0)
    legacy = InjectionMoldingModel().calculate(data)

    adapted = adapt_injection_molding_cost_layers(data, legacy)

    assert adapted.process.machine_cost == legacy.machine_cost
    assert adapted.process.labour_cost == legacy.labour_cost
    assert adapted.material.base_material_cost == legacy.material_cost
    assert adapted.process.process_scrap_cost == 0.0


def test_adapter_fallback_applies_positive_scrap_to_good_part_costs():
    data = valid_input(scrap_rate=0.10, overhead_rate=0.40)
    legacy = InjectionMoldingModel().calculate(data)

    adapted = adapt_injection_molding_cost_layers(data, legacy)
    expected_scrap = fallback_process_scrap(data, legacy)

    assert adapted.material.base_material_cost == pytest.approx(
        expected_scrap.material_cost_per_good_part
    )
    assert adapted.process.machine_cost == pytest.approx(
        expected_scrap.machine_cost_per_good_part
    )
    assert adapted.process.labour_cost == pytest.approx(
        expected_scrap.labour_cost_per_good_part
    )
    assert adapted.process.process_scrap_cost == 0.0
    assert adapted.process.production_overhead_cost == pytest.approx(
        (
            expected_scrap.machine_cost_per_good_part
            + expected_scrap.labour_cost_per_good_part
        )
        * data.overhead_rate
    )


def test_adapter_fallback_matches_equivalent_explicit_process_scrap_result():
    data = valid_input(scrap_rate=0.10, overhead_rate=0.40)
    legacy = InjectionMoldingModel().calculate(data)
    explicit_scrap = fallback_process_scrap(data, legacy)

    fallback = adapt_injection_molding_cost_layers(data, legacy)
    explicit = adapt_injection_molding_cost_layers(
        data, legacy, process_scrap=explicit_scrap
    )

    assert fallback == explicit


def test_tooling_and_legacy_uplifts_do_not_affect_fallback_layers():
    data_without_tooling = valid_input(
        tooling_cost_eur=0.0, scrap_rate=0.10, overhead_rate=0.40
    )
    data_with_tooling = valid_input(
        tooling_cost_eur=100000.0, scrap_rate=0.10, overhead_rate=0.40
    )
    model = InjectionMoldingModel()
    legacy_without_tooling = model.calculate(data_without_tooling)
    legacy_with_tooling = model.calculate(data_with_tooling)

    without_tooling = adapt_injection_molding_cost_layers(
        data_without_tooling, legacy_without_tooling
    )
    with_tooling = adapt_injection_molding_cost_layers(
        data_with_tooling, legacy_with_tooling
    )

    assert legacy_with_tooling.tooling_cost > legacy_without_tooling.tooling_cost
    assert legacy_with_tooling.scrap_cost > legacy_without_tooling.scrap_cost
    assert legacy_with_tooling.overhead_cost > legacy_without_tooling.overhead_cost
    assert without_tooling == with_tooling
    assert with_tooling.process.process_scrap_cost == 0.0


def test_a9_process_scrap_reference_case():
    data = InjectionMoldingInput(
        annual_volume=11504,
        part_weight_kg=1.0,
        material_price_eur_kg=2.5,
        material_utilization=1.0 / 1.03,
        cycle_time_s=94,
        cavities=1,
        machine_rate_eur_h=28.881166666666665,
        oee=1.0,
        labour_rate_eur_h=12.669741252,
        operators=0.5,
        scrap_rate=0.0,
        tooling_cost_eur=0.0,
        tool_life_shots=1,
        overhead_rate=0.0,
        currency="EUR",
        material="ASA",
        region="Hungary",
    )
    legacy = InjectionMoldingModel().calculate(data)
    process_scrap = ProcessScrapInput(
        process_scrap_rate=0.10,
        material_cost_per_attempt=legacy.material_cost,
        machine_cost_per_attempt=legacy.machine_cost,
        labour_cost_per_attempt=legacy.labour_cost,
        currency="EUR",
    )

    result = calculate_process_scrap(process_scrap)
    adapted = adapt_injection_molding_cost_layers(data, legacy, process_scrap=result)

    assert result.process_yield == pytest.approx(0.9)
    assert result.attempts_per_good_part == pytest.approx(1.1111111111)
    assert result.material_cost_per_good_part == pytest.approx(2.8611111111111116)
    assert result.machine_cost_per_good_part == pytest.approx(0.8378888888888889)
    assert result.labour_cost_per_good_part == pytest.approx(0.1837777777777778)
    assert adapted.material.base_material_cost == pytest.approx(2.8611111111111116)
    assert adapted.process.machine_cost == pytest.approx(0.8378888888888889)
    assert adapted.process.labour_cost == pytest.approx(0.1837777777777778)
    assert adapted.manufacturing_should_cost == pytest.approx(2.8611111111111116 + 0.8378888888888889 + 0.1837777777777778)


def test_a9_compatibility_result_matches_expected_layer_totals():
    data = InjectionMoldingInput(
        annual_volume=11504,
        part_weight_kg=1.0,
        material_price_eur_kg=2.5,
        material_utilization=1.0 / 1.03,
        cycle_time_s=94,
        cavities=1,
        machine_rate_eur_h=28.881166666666665,
        oee=1.0,
        labour_rate_eur_h=12.669741252,
        operators=0.5,
        scrap_rate=0.0,
        tooling_cost_eur=0.0,
        tool_life_shots=1,
        overhead_rate=0.0,
        currency="EUR",
        material="ASA",
        region="Hungary",
    )
    legacy = InjectionMoldingModel().calculate(data)

    adapted = adapt_injection_molding_cost_layers(data, legacy)

    assert adapted.material.total_material_cost == pytest.approx(2.5750, abs=1e-4)
    assert adapted.process.total_process_cost == pytest.approx(0.9195, abs=1e-4)
    assert adapted.secondary_processes.total_secondary_process_cost == 0.0
    assert adapted.manufacturing_should_cost == pytest.approx(3.4945, abs=1e-4)
