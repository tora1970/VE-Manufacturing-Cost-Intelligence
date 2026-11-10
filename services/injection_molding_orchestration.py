from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum

import pandas as pd

from models.injection_molding import (
    InjectionMoldingBaseProcessInput,
    InjectionMoldingBaseProcessResult,
    InjectionMoldingModel,
)
from models.manufacturing_cost_layers import ManufacturingCostBreakdown
from services.injection_molding_cost_layer_adapter import (
    adapt_injection_molding_cost_layers,
)
from services.machine_rate_resolution import (
    resolve_injection_molding_machine_rate,
)
from services.setup_cost_calculation import SetupCostInput


class OrchestrationStatus(str, Enum):
    COMPLETE = "COMPLETE"
    INCOMPLETE = "INCOMPLETE"
    INVALID = "INVALID"


@dataclass(frozen=True)
class OrchestrationIssue:
    field: str
    code: str
    message: str


@dataclass(frozen=True)
class LabourRateResolution:
    status: str
    rate_eur_h: object | None = None
    currency: str | None = None
    currency_basis_verified: bool = False


@dataclass(frozen=True)
class ProductionOverheadResolution:
    rate: object | None = None
    approved: bool = False


@dataclass(frozen=True)
class ResolvedInputSummary:
    material_id: str
    technology_id: str
    machine_class_id: str
    material_price_eur_kg: float
    machine_rate_eur_h: float
    labour_rate_eur_h: float
    production_overhead_rate: float
    setup_applicable: bool
    currency: str


@dataclass(frozen=True)
class InjectionMoldingOrchestrationResult:
    status: OrchestrationStatus
    issues: tuple[OrchestrationIssue, ...]
    manufacturing_cost_breakdown: ManufacturingCostBreakdown | None = None
    manufacturing_should_cost: float | None = None
    resolved_inputs: ResolvedInputSummary | None = None


@dataclass(frozen=True)
class InjectionMoldingOrchestrationRequest:
    material_id: object | None = None
    part_weight_kg: object | None = None
    cycle_time_s: object | None = None
    cavities: object | None = None
    material_utilization: object | None = None
    oee: object | None = None
    operators: object | None = None
    process_scrap_rate: object | None = None
    setup_applicable: object | None = None
    setup_time_h: object | None = None
    batch_size_good_pcs: object | None = None
    technology_id: object | None = None
    machine_class_id: object | None = None
    currency: object | None = None
    material_table: pd.DataFrame | None = None
    machine_rate_table: pd.DataFrame | None = None
    labour_rate_resolution: LabourRateResolution | None = None
    production_overhead_resolution: ProductionOverheadResolution | None = None


def _is_missing(value: object | None) -> bool:
    return value is None


def _numeric_value(
    value: object | None,
    field: str,
    issues: list[OrchestrationIssue],
    *,
    required: bool = True,
) -> float | None:
    if _is_missing(value):
        if required:
            issues.append(
                OrchestrationIssue(field, "missing_value", f"{field} is required.")
            )
        return None

    if isinstance(value, (bool, str, bytes)):
        issues.append(
            OrchestrationIssue(field, "invalid_type", f"{field} must be numeric.")
        )
        return None

    try:
        numeric_value = float(value)
    except (TypeError, ValueError, OverflowError):
        issues.append(
            OrchestrationIssue(field, "invalid_type", f"{field} must be numeric.")
        )
        return None

    if not math.isfinite(numeric_value):
        issues.append(
            OrchestrationIssue(field, "invalid_value", f"{field} must be finite.")
        )
        return None
    return numeric_value


def _identifier(
    value: object | None, field: str, issues: list[OrchestrationIssue]
) -> str | None:
    if value is None:
        issues.append(
            OrchestrationIssue(field, "missing_value", f"{field} is required.")
        )
        return None
    if not isinstance(value, str) or not value.strip():
        issues.append(
            OrchestrationIssue(
                field, "invalid_value", f"{field} must be a non-empty string."
            )
        )
        return None
    return value


def _validate_range(
    value: float | None,
    field: str,
    issues: list[OrchestrationIssue],
    *,
    minimum: float | None = None,
    maximum: float | None = None,
    minimum_exclusive: bool = False,
    maximum_inclusive: bool = True,
) -> None:
    if value is None:
        return
    below_minimum = (
        value <= minimum if minimum_exclusive else value < minimum
    ) if minimum is not None else False
    above_maximum = (
        value > maximum if maximum_inclusive else value >= maximum
    ) if maximum is not None else False
    if below_minimum or above_maximum:
        issues.append(
            OrchestrationIssue(field, "invalid_value", f"{field} is out of range.")
        )


def _resolve_material_price(
    material_id: str | None,
    table: pd.DataFrame | None,
    issues: list[OrchestrationIssue],
) -> float | None:
    if material_id is None:
        return None
    if not isinstance(table, pd.DataFrame):
        issues.append(
            OrchestrationIssue(
                "material_price",
                "unavailable_source",
                "Material price table is unavailable.",
            )
        )
        return None
    required_columns = {"Material_ID", "Default_Price_EUR_kg"}
    if (
        not required_columns.issubset(table.columns)
        or any(list(table.columns).count(column) != 1 for column in required_columns)
    ):
        issues.append(
            OrchestrationIssue(
                "material_price",
                "unavailable_source",
                "Material price table lacks a unique required column.",
            )
        )
        return None

    matches = table.loc[table["Material_ID"].eq(material_id)]
    if matches.empty:
        issues.append(
            OrchestrationIssue(
                "material_id",
                "not_found",
                f"No material row matches {material_id!r}.",
            )
        )
        return None
    if len(matches) != 1:
        issues.append(
            OrchestrationIssue(
                "material_id",
                "ambiguous_match",
                f"Multiple material rows match {material_id!r}.",
            )
        )
        return None

    raw_price = matches.iloc[0]["Default_Price_EUR_kg"]
    if raw_price is None or raw_price is pd.NA:
        issues.append(
            OrchestrationIssue(
                "material_price_eur_kg",
                "missing_value",
                "The matched material row has no EUR/kg price.",
            )
        )
        return None
    price = _numeric_value(raw_price, "material_price_eur_kg", issues)
    _validate_range(price, "material_price_eur_kg", issues, minimum=0, minimum_exclusive=True)
    return price


def _resolve_machine_rate(
    technology_id: str | None,
    machine_class_id: str | None,
    table: pd.DataFrame | None,
    issues: list[OrchestrationIssue],
) -> float | None:
    if technology_id is None or machine_class_id is None:
        return None
    rate, resolution = resolve_injection_molding_machine_rate(
        technology_id, machine_class_id, table
    )
    if resolution != "resolved":
        code = "ambiguous_resolution" if resolution == "ambiguous" else "unavailable_resolution"
        issues.append(
            OrchestrationIssue(
                "machine_rate",
                code,
                "Machine rate could not be resolved uniquely.",
            )
        )
        return None
    return rate


def _resolve_labour_rate(
    resolution: LabourRateResolution | None,
    issues: list[OrchestrationIssue],
) -> float | None:
    if resolution is None:
        issues.append(
            OrchestrationIssue(
                "labour_rate",
                "unavailable_resolution",
                "Labour rate resolution is required.",
            )
        )
        return None
    if not isinstance(resolution, LabourRateResolution):
        issues.append(
            OrchestrationIssue(
                "labour_rate",
                "invalid_resolution",
                "Labour rate outcome is malformed.",
            )
        )
        return None
    if not isinstance(resolution.status, str) or resolution.status not in {
        "resolved",
        "unavailable",
        "ambiguous",
    }:
        issues.append(
            OrchestrationIssue(
                "labour_rate",
                "invalid_resolution",
                "Labour rate outcome has an unknown status.",
            )
        )
        return None
    if resolution.status != "resolved":
        code = (
            "ambiguous_resolution"
            if resolution.status == "ambiguous"
            else "unavailable_resolution"
        )
        issues.append(
            OrchestrationIssue(
                "labour_rate",
                code,
                "Labour rate is unavailable or ambiguous.",
            )
        )
        return None
    if (
        resolution.currency_basis_verified is not True
        or resolution.currency != "EUR"
    ):
        if not isinstance(resolution.currency_basis_verified, bool):
            issues.append(
                OrchestrationIssue(
                    "labour_rate",
                    "invalid_resolution",
                    "Labour currency verification must be boolean.",
                )
            )
            return None
        issues.append(
            OrchestrationIssue(
                "labour_rate",
                "unknown_currency_basis",
                "Labour rate must have a verified EUR basis.",
            )
        )
        return None
    rate = _numeric_value(resolution.rate_eur_h, "labour_rate_eur_h", issues)
    _validate_range(rate, "labour_rate_eur_h", issues, minimum=0)
    return rate


def _resolve_overhead_rate(
    resolution: ProductionOverheadResolution | None,
    issues: list[OrchestrationIssue],
) -> float | None:
    if resolution is None:
        issues.append(
            OrchestrationIssue(
                "production_overhead_rate",
                "unavailable_resolution",
                "An approved Production OH outcome is required.",
            )
        )
        return None
    if not isinstance(resolution, ProductionOverheadResolution):
        issues.append(
            OrchestrationIssue(
                "production_overhead_rate",
                "invalid_resolution",
                "Production OH outcome is malformed.",
            )
        )
        return None
    if not isinstance(resolution.approved, bool):
        issues.append(
            OrchestrationIssue(
                "production_overhead_rate",
                "invalid_resolution",
                "Production OH approval must be explicit.",
            )
        )
        return None
    if resolution.approved is not True or resolution.rate is None:
        issues.append(
            OrchestrationIssue(
                "production_overhead_rate",
                "unapproved_resolution",
                "Production OH rate is missing or unapproved.",
            )
        )
        return None
    rate = _numeric_value(resolution.rate, "production_overhead_rate", issues)
    _validate_range(
        rate,
        "production_overhead_rate",
        issues,
        minimum=0,
        maximum=1,
        maximum_inclusive=False,
    )
    return rate


def orchestrate_injection_molding_cost(
    request: InjectionMoldingOrchestrationRequest,
    *,
    model: InjectionMoldingModel | None = None,
) -> InjectionMoldingOrchestrationResult:
    """Validate and resolve one case before invoking the existing IM cost layers."""
    if not isinstance(request, InjectionMoldingOrchestrationRequest):
        raise TypeError("request must be an InjectionMoldingOrchestrationRequest.")

    issues: list[OrchestrationIssue] = []
    material_id = _identifier(request.material_id, "material_id", issues)
    technology_id = _identifier(request.technology_id, "technology_id", issues)
    machine_class_id = _identifier(
        request.machine_class_id, "machine_class_id", issues
    )

    numeric_fields = {
        "part_weight_kg": request.part_weight_kg,
        "cycle_time_s": request.cycle_time_s,
        "cavities": request.cavities,
        "material_utilization": request.material_utilization,
        "oee": request.oee,
        "operators": request.operators,
        "process_scrap_rate": request.process_scrap_rate,
    }
    values = {
        name: _numeric_value(value, name, issues)
        for name, value in numeric_fields.items()
    }
    _validate_range(values["part_weight_kg"], "part_weight_kg", issues, minimum=0, minimum_exclusive=True)
    _validate_range(values["cycle_time_s"], "cycle_time_s", issues, minimum=0, minimum_exclusive=True)
    _validate_range(values["cavities"], "cavities", issues, minimum=0, minimum_exclusive=True)
    if values["cavities"] is not None and not values["cavities"].is_integer():
        issues.append(
            OrchestrationIssue("cavities", "invalid_value", "cavities must be an integer.")
        )
    _validate_range(
        values["material_utilization"],
        "material_utilization",
        issues,
        minimum=0,
        maximum=1,
        minimum_exclusive=True,
    )
    _validate_range(values["oee"], "oee", issues, minimum=0, maximum=1, minimum_exclusive=True)
    _validate_range(values["operators"], "operators", issues, minimum=0)
    _validate_range(
        values["process_scrap_rate"],
        "process_scrap_rate",
        issues,
        minimum=0,
        maximum=1,
        maximum_inclusive=False,
    )

    if request.currency is None:
        issues.append(
            OrchestrationIssue("currency", "missing_value", "currency is required.")
        )
    elif request.currency != "EUR":
        issues.append(
            OrchestrationIssue(
                "currency", "invalid_value", "Calculation currency must be EUR."
            )
        )

    if request.setup_applicable is None:
        issues.append(
            OrchestrationIssue(
                "setup_applicable",
                "missing_value",
                "Setup applicability must be explicit.",
            )
        )
        setup_applicable = None
    elif not isinstance(request.setup_applicable, bool):
        issues.append(
            OrchestrationIssue(
                "setup_applicable",
                "invalid_type",
                "setup_applicable must be a boolean.",
            )
        )
        setup_applicable = None
    else:
        setup_applicable = request.setup_applicable

    setup_time_h = _numeric_value(
        request.setup_time_h,
        "setup_time_h",
        issues,
        required=setup_applicable is True,
    )
    batch_size_good_pcs = _numeric_value(
        request.batch_size_good_pcs,
        "batch_size_good_pcs",
        issues,
        required=setup_applicable is True,
    )
    _validate_range(setup_time_h, "setup_time_h", issues, minimum=0)
    _validate_range(
        batch_size_good_pcs,
        "batch_size_good_pcs",
        issues,
        minimum=0,
        minimum_exclusive=True,
    )
    if (
        batch_size_good_pcs is not None
        and not batch_size_good_pcs.is_integer()
    ):
        issues.append(
            OrchestrationIssue(
                "batch_size_good_pcs",
                "invalid_value",
                "batch_size_good_pcs must be an integer.",
            )
        )

    material_price = _resolve_material_price(
        material_id, request.material_table, issues
    )
    machine_rate = _resolve_machine_rate(
        technology_id, machine_class_id, request.machine_rate_table, issues
    )
    labour_rate = _resolve_labour_rate(request.labour_rate_resolution, issues)
    overhead_rate = _resolve_overhead_rate(
        request.production_overhead_resolution, issues
    )

    if issues:
        status = (
            OrchestrationStatus.INVALID
            if any(issue.code in {"invalid_type", "invalid_value", "invalid_resolution"} for issue in issues)
            else OrchestrationStatus.INCOMPLETE
        )
        return InjectionMoldingOrchestrationResult(status, tuple(issues))

    assert material_id is not None
    assert technology_id is not None
    assert machine_class_id is not None
    assert material_price is not None
    assert machine_rate is not None
    assert labour_rate is not None
    assert overhead_rate is not None
    assert setup_applicable is not None
    assert request.currency == "EUR"

    base_input = InjectionMoldingBaseProcessInput(
        part_weight_kg=values["part_weight_kg"],
        material_price_eur_kg=material_price,
        material_utilization=values["material_utilization"],
        cycle_time_s=values["cycle_time_s"],
        cavities=int(values["cavities"]),
        machine_rate_eur_h=machine_rate,
        oee=values["oee"],
        labour_rate_eur_h=labour_rate,
        operators=values["operators"],
        scrap_rate=values["process_scrap_rate"],
        overhead_rate=overhead_rate,
        currency="EUR",
    )

    calculation_model = model if model is not None else InjectionMoldingModel()
    base_result: InjectionMoldingBaseProcessResult = (
        calculation_model.calculate_base_process(base_input)
    )
    setup_input = (
        SetupCostInput(
            setup_time_h=setup_time_h,
            machine_rate_eur_h=machine_rate,
            labour_rate_eur_h=labour_rate,
            operators=values["operators"],
            batch_size_pcs=batch_size_good_pcs,
            currency="EUR",
        )
        if setup_applicable
        else None
    )
    breakdown = adapt_injection_molding_cost_layers(
        base_input, base_result, setup=setup_input
    )
    summary = ResolvedInputSummary(
        material_id=material_id,
        technology_id=technology_id,
        machine_class_id=machine_class_id,
        material_price_eur_kg=material_price,
        machine_rate_eur_h=machine_rate,
        labour_rate_eur_h=labour_rate,
        production_overhead_rate=overhead_rate,
        setup_applicable=setup_applicable,
        currency="EUR",
    )
    return InjectionMoldingOrchestrationResult(
        status=OrchestrationStatus.COMPLETE,
        issues=(),
        manufacturing_cost_breakdown=breakdown,
        manufacturing_should_cost=breakdown.manufacturing_should_cost,
        resolved_inputs=summary,
    )


__all__ = [
    "InjectionMoldingOrchestrationRequest",
    "InjectionMoldingOrchestrationResult",
    "LabourRateResolution",
    "OrchestrationIssue",
    "OrchestrationStatus",
    "ProductionOverheadResolution",
    "ResolvedInputSummary",
    "orchestrate_injection_molding_cost",
]
