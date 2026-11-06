import copy
import math

import pytest

from models.injection_molding import InjectionMoldingInput, InjectionMoldingModel
from models.manufacturing_cost_layers import ManufacturingCostBreakdown
from services.injection_molding_cost_layer_adapter import (
    adapt_injection_molding_cost_layers,
    legacy_excluded_tooling_cost,
)
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


def test_valid_input_and_result_can_be_adapted():
    data = valid_input()
    legacy = InjectionMoldingModel().calculate(data)

    adapted = adapt_injection_molding_cost_layers(data, legacy)

    assert isinstance(adapted, ManufacturingCostBreakdown)
    assert adapted.material.base_material_cost == legacy.material_cost
    assert adapted.process.machine_cost == legacy.machine_cost
    assert adapted.secondary_processes.total_secondary_process_cost == 0.0


def test_material_mapping_is_legacy_pure_and_no_material_overhead_is_added():
    data = valid_input()
    legacy = InjectionMoldingModel().calculate(data)

    adapted = adapt_injection_molding_cost_layers(data, legacy)

    assert adapted.material.base_material_cost == legacy.material_cost
    assert adapted.material.material_loss_cost == 0.0
    assert adapted.material.material_overhead_cost == 0.0


def test_process_mapping_preserves_legacy_values_and_zero_setup():
    data = valid_input()
    legacy = InjectionMoldingModel().calculate(data)

    adapted = adapt_injection_molding_cost_layers(data, legacy)

    assert adapted.process.machine_cost == legacy.machine_cost
    assert adapted.process.labour_cost == legacy.labour_cost
    assert adapted.process.setup_cost == 0.0
    assert adapted.process.process_scrap_cost == legacy.scrap_cost
    assert adapted.process.production_overhead_cost == legacy.overhead_cost


def test_secondary_process_layer_is_empty_and_total_is_zero():
    data = valid_input()
    legacy = InjectionMoldingModel().calculate(data)

    adapted = adapt_injection_molding_cost_layers(data, legacy)

    assert adapted.secondary_processes.costs == ()
    assert adapted.secondary_processes.total_secondary_process_cost == 0.0


def test_manufacturing_should_cost_matches_legacy_material_machine_labour_scrap_and_overhead():
    data = valid_input()
    legacy = InjectionMoldingModel().calculate(data)

    adapted = adapt_injection_molding_cost_layers(data, legacy)

    expected = (
        legacy.material_cost
        + legacy.machine_cost
        + legacy.labour_cost
        + legacy.scrap_cost
        + legacy.overhead_cost
    )
    assert adapted.manufacturing_should_cost == pytest.approx(expected)


def test_legacy_tooling_cost_is_excluded_from_manufacturing_should_cost():
    data = valid_input()
    legacy = InjectionMoldingModel().calculate(data)

    adapted = adapt_injection_molding_cost_layers(data, legacy)

    assert adapted.manufacturing_should_cost + legacy.tooling_cost == pytest.approx(
        legacy.total_cost, rel=1e-9
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

    assert adapted.process.machine_cost == legacy.machine_cost
    assert adapted.process.labour_cost == legacy.labour_cost
    assert adapted.material.base_material_cost == legacy.material_cost


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


def test_adapter_keeps_existing_no_setup_call_unchanged():
    data = valid_input()
    legacy = InjectionMoldingModel().calculate(data)

    adapted = adapt_injection_molding_cost_layers(data, legacy)

    assert adapted.process.setup_cost == 0.0
    assert adapted.process.total_process_cost == pytest.approx(
        legacy.machine_cost + legacy.labour_cost + legacy.scrap_cost + legacy.overhead_cost
    )


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
    assert adapted.process.machine_cost == legacy.machine_cost
    assert adapted.process.labour_cost == legacy.labour_cost
    assert adapted.process.process_scrap_cost == legacy.scrap_cost
    assert adapted.process.production_overhead_cost == legacy.overhead_cost


def test_adapter_increases_manufacturing_should_cost_exactly_by_setup_cost():
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

    assert adapted.manufacturing_should_cost == pytest.approx(
        legacy.material_cost + legacy.machine_cost + legacy.labour_cost + legacy.scrap_cost + legacy.overhead_cost + setup.setup_cost_per_part
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
    assert adapted.manufacturing_should_cost + legacy.tooling_cost == pytest.approx(
        legacy.total_cost + setup.setup_cost_per_part
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
