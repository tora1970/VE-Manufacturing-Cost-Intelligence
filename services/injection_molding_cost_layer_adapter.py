from __future__ import annotations

"""Compatibility adapter for the legacy Injection Molding cost result.

This adapter translates the existing Injection Molding result into the shared
ManufacturingCostBreakdown contract. Production overhead is recalculated from
machine, labour, and setup costs; the legacy overhead amount is not carried over.
Existing tooling_cost remains deliberately excluded because tooling is treated as
project CAPEX / project cost rather than manufacturing should-cost.
"""

from models.injection_molding import (
    InjectionMoldingBaseProcessInput,
    InjectionMoldingBaseProcessResult,
    InjectionMoldingCostBreakdown,
    InjectionMoldingInput,
)
from models.manufacturing_cost_layers import (
    ManufacturingCostBreakdown,
    MaterialCostLayer,
    ProcessCostLayer,
    SecondaryProcessCostLayer,
)
from services.process_scrap_calculation import (
    ProcessScrapInput,
    ProcessScrapResult,
    calculate_process_scrap,
)
from services.production_overhead_calculation import (
    ProductionOverheadInput,
    calculate_production_overhead,
)
from services.setup_cost_calculation import (
    SetupCostInput,
    SetupCostResult,
    calculate_setup_cost,
)


def legacy_excluded_tooling_cost(result: InjectionMoldingCostBreakdown) -> float:
    """Return the legacy tooling cost that is intentionally excluded from manufacturing should-cost."""
    return float(result.tooling_cost)


def adapt_injection_molding_cost_layers(
    data: InjectionMoldingInput | InjectionMoldingBaseProcessInput,
    result: InjectionMoldingCostBreakdown | InjectionMoldingBaseProcessResult,
    *,
    setup: SetupCostInput | SetupCostResult | None = None,
    process_scrap: ProcessScrapInput | ProcessScrapResult | None = None,
) -> ManufacturingCostBreakdown:
    """Translate the legacy Injection Molding result into the shared cost-layer contract.

    Legacy tooling and overhead are excluded; production overhead is calculated
    from machine, labour, and setup costs only.
    """
    if not isinstance(data, (InjectionMoldingInput, InjectionMoldingBaseProcessInput)):
        raise TypeError(
            "data must be an InjectionMoldingInput or "
            "InjectionMoldingBaseProcessInput."
        )
    if not isinstance(
        result, (InjectionMoldingCostBreakdown, InjectionMoldingBaseProcessResult)
    ):
        raise TypeError(
            "result must be an InjectionMoldingCostBreakdown or "
            "InjectionMoldingBaseProcessResult."
        )
    if not (
        isinstance(data, InjectionMoldingInput)
        and isinstance(result, InjectionMoldingCostBreakdown)
        or isinstance(data, InjectionMoldingBaseProcessInput)
        and isinstance(result, InjectionMoldingBaseProcessResult)
    ):
        raise TypeError(
            "data and result must be a matching Injection Molding input/result pair."
        )

    if data.currency != "EUR":
        raise ValueError("InjectionMoldingInput currency must be 'EUR'.")
    if result.currency != "EUR":
        raise ValueError("InjectionMoldingCostBreakdown currency must be 'EUR'.")
    if data.currency != result.currency:
        raise ValueError("Input and result currency labels must match.")

    resolved_setup = None
    if setup is not None:
        if isinstance(setup, SetupCostInput):
            resolved_setup = calculate_setup_cost(setup)
        elif isinstance(setup, SetupCostResult):
            resolved_setup = setup
        else:
            raise TypeError("setup must be a SetupCostInput or SetupCostResult.")

        if resolved_setup.currency != "EUR":
            raise ValueError("Setup cost currency must be 'EUR'.")
        if data.currency != resolved_setup.currency:
            raise ValueError("Input and setup currency labels must match.")
        if result.currency != resolved_setup.currency:
            raise ValueError("Result and setup currency labels must match.")

    if isinstance(result, InjectionMoldingCostBreakdown):
        material_cost_per_attempt = result.material_cost
        machine_cost_per_attempt = result.machine_cost
        labour_cost_per_attempt = result.labour_cost
    else:
        material_cost_per_attempt = result.material_cost_per_attempt
        machine_cost_per_attempt = result.machine_cost_per_attempt
        labour_cost_per_attempt = result.labour_cost_per_attempt

    if process_scrap is None:
        resolved_scarp = calculate_process_scrap(
            ProcessScrapInput(
                process_scrap_rate=data.scrap_rate,
                material_cost_per_attempt=material_cost_per_attempt,
                machine_cost_per_attempt=machine_cost_per_attempt,
                labour_cost_per_attempt=labour_cost_per_attempt,
                currency=data.currency,
            )
        )
    else:
        if isinstance(process_scrap, ProcessScrapInput):
            resolved_scarp = calculate_process_scrap(process_scrap)
        elif isinstance(process_scrap, ProcessScrapResult):
            resolved_scarp = process_scrap
        else:
            raise TypeError("process_scrap must be a ProcessScrapInput or ProcessScrapResult.")

        if resolved_scarp.currency != "EUR":
            raise ValueError("Process scrap currency must be 'EUR'.")
        if data.currency != resolved_scarp.currency:
            raise ValueError("Input and process scrap currency labels must match.")
        if result.currency != resolved_scarp.currency:
            raise ValueError("Result and process scrap currency labels must match.")

    process_setup_cost = resolved_setup.setup_cost_per_part if resolved_setup is not None else 0.0

    material = MaterialCostLayer(
        base_material_cost=resolved_scarp.material_cost_per_good_part,
        material_loss_cost=0.0,
        material_overhead_cost=0.0,
    )
    machine_cost = resolved_scarp.machine_cost_per_good_part
    labour_cost = resolved_scarp.labour_cost_per_good_part
    process_scrap_cost = 0.0

    production_overhead = calculate_production_overhead(
        ProductionOverheadInput(
            machine_cost_per_good_part=machine_cost,
            labour_cost_per_good_part=labour_cost,
            setup_cost_per_good_part=process_setup_cost,
            production_overhead_rate=data.overhead_rate,
            currency=data.currency,
        )
    )

    process = ProcessCostLayer(
        machine_cost=machine_cost,
        labour_cost=labour_cost,
        setup_cost=process_setup_cost,
        process_scrap_cost=process_scrap_cost,
        production_overhead_cost=(
            production_overhead.production_overhead_cost_per_good_part
        ),
    )
    secondary_processes = SecondaryProcessCostLayer(())

    return ManufacturingCostBreakdown(
        material=material,
        process=process,
        secondary_processes=secondary_processes,
    )
