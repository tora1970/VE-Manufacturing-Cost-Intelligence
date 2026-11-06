from __future__ import annotations

import copy
from dataclasses import fields

import pytest

from models.injection_molding import InjectionMoldingInput, InjectionMoldingModel
from models.manufacturing_cost_layers import ManufacturingCostBreakdown
from services.injection_molding_cost_layer_adapter import (
    adapt_injection_molding_cost_layers,
    legacy_excluded_tooling_cost,
)
from services.process_scrap_calculation import (
    ProcessScrapInput,
    ProcessScrapResult,
    calculate_process_scrap,
)
from services.setup_cost_calculation import (
    SetupCostInput,
    SetupCostResult,
    calculate_setup_cost,
)


_A9_SETUP_COST_PER_GOOD_PART = 0.26005436110431157


@pytest.fixture
def a9_layered_result():
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
        scrap_rate=0.03,
        tooling_cost_eur=100000.0,
        tool_life_shots=100000,
        overhead_rate=0.0,
        currency="EUR",
        material="ASA",
        region="Hungary",
    )
    legacy_result = InjectionMoldingModel().calculate(data)

    process_scrap_input = ProcessScrapInput(
        process_scrap_rate=0.10,
        material_cost_per_attempt=legacy_result.material_cost,
        machine_cost_per_attempt=legacy_result.machine_cost,
        labour_cost_per_attempt=legacy_result.labour_cost,
        currency="EUR",
    )
    process_scrap_result = calculate_process_scrap(process_scrap_input)

    batch_size_pcs = data.annual_volume / 12
    setup_time_h = 6.0
    # This test-only rate is derived from the verified setup cost reference;
    # the separate A9 setup-resource rate is not independently verified.
    setup_hourly_cost = (
        _A9_SETUP_COST_PER_GOOD_PART * batch_size_pcs / setup_time_h
    )
    inferred_setup_labour_rate_eur_h = (
        setup_hourly_cost - data.machine_rate_eur_h
    ) / data.operators
    setup_input = SetupCostInput(
        setup_time_h=setup_time_h,
        machine_rate_eur_h=data.machine_rate_eur_h,
        labour_rate_eur_h=inferred_setup_labour_rate_eur_h,
        operators=data.operators,
        batch_size_pcs=batch_size_pcs,
        currency="EUR",
    )
    setup_result = calculate_setup_cost(setup_input)

    breakdown = adapt_injection_molding_cost_layers(
        data,
        legacy_result,
        setup=setup_result,
        process_scrap=process_scrap_result,
    )
    return {
        "data": data,
        "legacy": legacy_result,
        "process_scrap_input": process_scrap_input,
        "process_scrap": process_scrap_result,
        "setup_input": setup_input,
        "setup": setup_result,
        "breakdown": breakdown,
    }


def _reconciliation(breakdown: ManufacturingCostBreakdown) -> dict[str, float]:
    return {
        "material": breakdown.material.total_material_cost,
        "machine": breakdown.process.machine_cost,
        "labour": breakdown.process.labour_cost,
        "setup": breakdown.process.setup_cost,
        "secondary": breakdown.secondary_processes.total_secondary_process_cost,
        "overhead": breakdown.process.production_overhead_cost,
        "manufacturing_should_cost": breakdown.manufacturing_should_cost,
    }


def test_a9_end_to_end_calculation_completes(a9_layered_result):
    assert isinstance(a9_layered_result["breakdown"], ManufacturingCostBreakdown)


def test_a9_material_cost_per_good_part(a9_layered_result):
    legacy = a9_layered_result["legacy"]
    breakdown = a9_layered_result["breakdown"]

    assert legacy.material_cost == pytest.approx(2.5750)
    assert breakdown.material.base_material_cost == pytest.approx(
        legacy.material_cost / 0.90
    )
    assert breakdown.material.total_material_cost == pytest.approx(2.8611, abs=1e-4)


def test_a9_machine_cost_per_good_part(a9_layered_result):
    breakdown = a9_layered_result["breakdown"]

    assert breakdown.process.machine_cost == pytest.approx(0.8379, abs=1e-4)


def test_a9_labour_cost_per_good_part(a9_layered_result):
    breakdown = a9_layered_result["breakdown"]

    assert breakdown.process.labour_cost == pytest.approx(0.1838, abs=1e-4)


def test_a9_setup_cost_per_good_part(a9_layered_result):
    setup = a9_layered_result["setup"]
    breakdown = a9_layered_result["breakdown"]

    assert isinstance(setup, SetupCostResult)
    assert setup.setup_cost_per_part == pytest.approx(
        _A9_SETUP_COST_PER_GOOD_PART
    )
    assert breakdown.process.setup_cost == pytest.approx(
        _A9_SETUP_COST_PER_GOOD_PART
    )


def test_a9_process_layer_reconciles_once(a9_layered_result):
    breakdown = a9_layered_result["breakdown"]

    assert breakdown.process.total_process_cost == pytest.approx(
        breakdown.process.machine_cost
        + breakdown.process.labour_cost
        + breakdown.process.setup_cost
    )
    assert breakdown.process.total_process_cost == pytest.approx(
        1.2817, abs=1e-4
    )


def test_a9_manufacturing_should_cost_matches_normalized_reference(
    a9_layered_result,
):
    breakdown = a9_layered_result["breakdown"]

    assert breakdown.manufacturing_should_cost == pytest.approx(
        4.1429, abs=1e-4
    )


def test_a9_explicit_process_scrap_is_counted_exactly_once(a9_layered_result):
    legacy = a9_layered_result["legacy"]
    process_scrap = a9_layered_result["process_scrap"]
    breakdown = a9_layered_result["breakdown"]

    assert isinstance(process_scrap, ProcessScrapResult)
    assert legacy.scrap_cost > 0.0
    assert breakdown.process.process_scrap_cost == 0.0
    assert breakdown.material.base_material_cost == pytest.approx(
        process_scrap.material_cost_per_good_part
    )
    assert breakdown.process.machine_cost == pytest.approx(
        process_scrap.machine_cost_per_good_part
    )
    assert breakdown.process.labour_cost == pytest.approx(
        process_scrap.labour_cost_per_good_part
    )
    assert breakdown.manufacturing_should_cost == pytest.approx(
        breakdown.material.total_material_cost
        + breakdown.process.machine_cost
        + breakdown.process.labour_cost
        + breakdown.process.setup_cost
    )


def test_a9_material_loss_is_included_exactly_once(a9_layered_result):
    legacy = a9_layered_result["legacy"]
    breakdown = a9_layered_result["breakdown"]

    assert legacy.material_cost == pytest.approx(1.03 * 2.50)
    assert breakdown.material.base_material_cost == pytest.approx(
        1.03 * 2.50 / 0.90
    )
    assert breakdown.material.material_loss_cost == 0.0
    assert breakdown.material.material_overhead_cost == 0.0


def test_a9_setup_is_counted_once_without_process_yield_scaling(
    a9_layered_result,
):
    setup = a9_layered_result["setup"]
    breakdown = a9_layered_result["breakdown"]

    assert breakdown.process.setup_cost == pytest.approx(
        setup.setup_cost_per_part
    )
    assert breakdown.process.setup_cost != pytest.approx(
        setup.setup_cost_per_part / 0.90
    )


def test_a9_tooling_is_excluded_and_not_scrap_scaled(a9_layered_result):
    legacy = a9_layered_result["legacy"]
    breakdown = a9_layered_result["breakdown"]

    assert legacy.tooling_cost > 0.0
    assert legacy_excluded_tooling_cost(legacy) == legacy.tooling_cost
    assert breakdown.manufacturing_should_cost == pytest.approx(
        breakdown.material.total_material_cost
        + breakdown.process.total_process_cost
        + breakdown.secondary_processes.total_secondary_process_cost
    )
    assert breakdown.manufacturing_should_cost != pytest.approx(
        breakdown.manufacturing_should_cost + legacy.tooling_cost
    )


def test_a9_secondary_processes_remain_zero(a9_layered_result):
    breakdown = a9_layered_result["breakdown"]

    assert breakdown.secondary_processes.costs == ()
    assert breakdown.secondary_processes.total_secondary_process_cost == 0.0


def test_manufacturing_breakdown_has_no_commercial_cost_fields():
    field_names = {field.name for field in fields(ManufacturingCostBreakdown)}

    assert field_names == {"material", "process", "secondary_processes"}
    assert not field_names.intersection(
        {
            "tooling",
            "tooling_cost",
            "capex",
            "project_cost",
            "packaging",
            "oqc",
            "logistics",
            "sga",
            "supplier_margin",
            "commercial_overhead",
            "supplier_price",
        }
    )


def test_a9_eur_basis_is_explicit(a9_layered_result):
    assert a9_layered_result["data"].currency == "EUR"
    assert a9_layered_result["legacy"].currency == "EUR"
    assert a9_layered_result["process_scrap"].currency == "EUR"
    assert a9_layered_result["setup"].currency == "EUR"
    assert isinstance(a9_layered_result["breakdown"], ManufacturingCostBreakdown)


def test_a9_adapter_does_not_mutate_legacy_result(a9_layered_result):
    legacy = a9_layered_result["legacy"]
    legacy_before = copy.deepcopy(legacy)

    adapt_injection_molding_cost_layers(
        a9_layered_result["data"],
        legacy,
        setup=a9_layered_result["setup"],
        process_scrap=a9_layered_result["process_scrap"],
    )

    assert legacy == legacy_before


def test_a9_adapter_does_not_mutate_setup_result(a9_layered_result):
    setup = a9_layered_result["setup"]
    setup_before = copy.deepcopy(setup)

    adapt_injection_molding_cost_layers(
        a9_layered_result["data"],
        a9_layered_result["legacy"],
        setup=setup,
        process_scrap=a9_layered_result["process_scrap"],
    )

    assert setup == setup_before


def test_a9_adapter_does_not_mutate_process_scrap_result(a9_layered_result):
    process_scrap = a9_layered_result["process_scrap"]
    process_scrap_before = copy.deepcopy(process_scrap)

    adapt_injection_molding_cost_layers(
        a9_layered_result["data"],
        a9_layered_result["legacy"],
        setup=a9_layered_result["setup"],
        process_scrap=process_scrap,
    )

    assert process_scrap == process_scrap_before


def test_a9_reconciliation_excludes_overhead_and_commercial_costs(
    a9_layered_result,
):
    reconciliation = _reconciliation(a9_layered_result["breakdown"])

    assert reconciliation["material"] == pytest.approx(2.8611, abs=1e-4)
    assert reconciliation["machine"] == pytest.approx(0.8379, abs=1e-4)
    assert reconciliation["labour"] == pytest.approx(0.1838, abs=1e-4)
    assert reconciliation["setup"] == pytest.approx(0.2601, abs=1e-4)
    assert reconciliation["secondary"] == 0.0
    assert reconciliation["overhead"] == 0.0
    assert reconciliation["manufacturing_should_cost"] == pytest.approx(
        4.1429, abs=1e-4
    )
