from __future__ import annotations

"""Compatibility adapter for the legacy Injection Molding cost result.

This adapter translates the existing Injection Molding result into the shared
ManufacturingCostBreakdown contract without recalculating manufacturing costs.
Existing tooling_cost remains deliberately excluded because tooling is treated as
project CAPEX / project cost rather than manufacturing should-cost.
"""

from models.injection_molding import InjectionMoldingCostBreakdown, InjectionMoldingInput
from models.manufacturing_cost_layers import (
    ManufacturingCostBreakdown,
    MaterialCostLayer,
    ProcessCostLayer,
    SecondaryProcessCostLayer,
)


def legacy_excluded_tooling_cost(result: InjectionMoldingCostBreakdown) -> float:
    """Return the legacy tooling cost that is intentionally excluded from manufacturing should-cost."""
    return float(result.tooling_cost)


def adapt_injection_molding_cost_layers(
    data: InjectionMoldingInput,
    result: InjectionMoldingCostBreakdown,
) -> ManufacturingCostBreakdown:
    """Translate the legacy Injection Molding result into the shared cost-layer contract.

    The adapter preserves the existing monetary outputs and does not recalculate
    the underlying manufacturing equation. Tooling is excluded on purpose.
    """
    if data.currency != "EUR":
        raise ValueError("InjectionMoldingInput currency must be 'EUR'.")
    if result.currency != "EUR":
        raise ValueError("InjectionMoldingCostBreakdown currency must be 'EUR'.")
    if data.currency != result.currency:
        raise ValueError("Input and result currency labels must match.")

    material = MaterialCostLayer(
        base_material_cost=result.material_cost,
        material_loss_cost=0.0,
        material_overhead_cost=0.0,
    )
    process = ProcessCostLayer(
        machine_cost=result.machine_cost,
        labour_cost=result.labour_cost,
        setup_cost=0.0,
        process_scrap_cost=result.scrap_cost,
        production_overhead_cost=result.overhead_cost,
    )
    secondary_processes = SecondaryProcessCostLayer(())

    return ManufacturingCostBreakdown(
        material=material,
        process=process,
        secondary_processes=secondary_processes,
    )
