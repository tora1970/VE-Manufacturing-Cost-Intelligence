import math

import pytest
from dataclasses import FrozenInstanceError

from models.manufacturing_cost_layers import (
    MaterialCostLayer,
    ManufacturingCostBreakdown,
    ProcessCostLayer,
    SecondaryProcessCost,
    SecondaryProcessCostLayer,
)


def test_material_layer_total_calculation():
    layer = MaterialCostLayer(10.0, 2.5, 3.5)
    assert layer.total_material_cost == 16.0


def test_process_layer_total_calculation():
    layer = ProcessCostLayer(25.0, 12.5, 4.0, 3.0, 5.5)
    assert layer.total_process_cost == 50.0


def test_empty_secondary_process_collection_totals_zero():
    layer = SecondaryProcessCostLayer(())
    assert layer.total_secondary_process_cost == 0.0


def test_single_secondary_process():
    layer = SecondaryProcessCostLayer((SecondaryProcessCost("Anodizing", 1.25),))
    assert layer.total_secondary_process_cost == 1.25


def test_multiple_secondary_processes_sum_correctly():
    layer = SecondaryProcessCostLayer(
        (
            SecondaryProcessCost("Anodizing", 1.25),
            SecondaryProcessCost("Packaging", 0.75),
            SecondaryProcessCost("OQC", 0.5),
        )
    )
    assert layer.total_secondary_process_cost == 2.5


def test_manufacturing_should_cost_sums_the_three_layers_correctly():
    material = MaterialCostLayer(10.0, 2.0, 1.0)
    process = ProcessCostLayer(20.0, 8.0, 2.0, 3.0, 4.0)
    secondary = SecondaryProcessCostLayer(
        (
            SecondaryProcessCost("Anodizing", 1.5),
            SecondaryProcessCost("Packaging", 0.5),
        )
    )
    breakdown = ManufacturingCostBreakdown(material, process, secondary)

    assert breakdown.manufacturing_should_cost == 52.0


def test_zero_cost_layers_are_valid():
    material = MaterialCostLayer(0.0, 0.0, 0.0)
    process = ProcessCostLayer(0.0, 0.0, 0.0, 0.0, 0.0)
    secondary = SecondaryProcessCostLayer(())

    breakdown = ManufacturingCostBreakdown(material, process, secondary)
    assert breakdown.manufacturing_should_cost == 0.0


@pytest.mark.parametrize(
    "factory",
    [
        lambda: MaterialCostLayer(-0.01, 0.0, 0.0),
        lambda: MaterialCostLayer(0.0, -0.01, 0.0),
        lambda: MaterialCostLayer(0.0, 0.0, -0.01),
        lambda: ProcessCostLayer(-0.01, 0.0, 0.0, 0.0, 0.0),
        lambda: ProcessCostLayer(0.0, -0.01, 0.0, 0.0, 0.0),
        lambda: ProcessCostLayer(0.0, 0.0, -0.01, 0.0, 0.0),
        lambda: ProcessCostLayer(0.0, 0.0, 0.0, -0.01, 0.0),
        lambda: ProcessCostLayer(0.0, 0.0, 0.0, 0.0, -0.01),
        lambda: SecondaryProcessCost("Anodizing", -0.01),
    ],
)
def test_negative_values_are_rejected(factory):
    with pytest.raises(ValueError):
        factory()


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_non_finite_values_are_rejected(value):
    with pytest.raises(ValueError):
        MaterialCostLayer(value, 0.0, 0.0)
    with pytest.raises(ValueError):
        ProcessCostLayer(0.0, value, 0.0, 0.0, 0.0)
    with pytest.raises(ValueError):
        SecondaryProcessCost("Anodizing", value)


@pytest.mark.parametrize("name", ["", "   "])
def test_empty_secondary_process_name_rejected(name):
    with pytest.raises(ValueError):
        SecondaryProcessCost(name, 1.0)


def test_duplicate_secondary_process_names_rejected():
    with pytest.raises(ValueError):
        SecondaryProcessCostLayer(
            (
                SecondaryProcessCost("Anodizing", 1.0),
                SecondaryProcessCost("Anodizing", 2.0),
            )
        )


def test_contract_contains_no_tooling_field():
    field_names = set().union(
        MaterialCostLayer.__dataclass_fields__.keys(),
        ProcessCostLayer.__dataclass_fields__.keys(),
        SecondaryProcessCost.__dataclass_fields__.keys(),
        SecondaryProcessCostLayer.__dataclass_fields__.keys(),
        ManufacturingCostBreakdown.__dataclass_fields__.keys(),
    )
    assert "tooling_cost" not in field_names
    assert "tooling_capex" not in field_names
    assert "tooling_amortization" not in field_names
    assert "logistics_cost" not in field_names
    assert "commercial_overhead" not in field_names
    assert "supplier_margin" not in field_names
    assert "supplier_profit" not in field_names


def test_manufacturing_should_cost_excludes_tooling_by_design():
    breakdown = ManufacturingCostBreakdown(
        MaterialCostLayer(10.0, 0.0, 0.0),
        ProcessCostLayer(5.0, 2.0, 0.0, 0.0, 0.0),
        SecondaryProcessCostLayer((SecondaryProcessCost("Packaging", 1.0),)),
    )
    assert breakdown.manufacturing_should_cost == 18.0
    assert isinstance(breakdown.manufacturing_should_cost, float)


def test_objects_are_immutable_frozen():
    material = MaterialCostLayer(1.0, 2.0, 3.0)
    process = ProcessCostLayer(4.0, 5.0, 6.0, 7.0, 8.0)
    secondary = SecondaryProcessCostLayer((SecondaryProcessCost("Packaging", 1.0),))

    with pytest.raises(FrozenInstanceError):
        material.base_material_cost = 9.0
    with pytest.raises(FrozenInstanceError):
        process.machine_cost = 9.0
    with pytest.raises(FrozenInstanceError):
        secondary.costs = ()


@pytest.mark.parametrize(
    "factory",
    [
        lambda: MaterialCostLayer(1.0, 2.0, 3.0),
        lambda: ProcessCostLayer(1.0, 2.0, 3.0, 4.0, 5.0),
        lambda: SecondaryProcessCost("Packaging", 1.0),
    ],
)
def test_no_negative_infinite_or_nan_after_validation(factory):
    value = factory()
    assert value is not None
