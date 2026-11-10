from __future__ import annotations

from dataclasses import replace

import pandas as pd
import pytest

import services.injection_molding_orchestration as orchestration
from models.injection_molding import (
    InjectionMoldingBaseProcessInput,
    InjectionMoldingModel,
)
from services.injection_molding_cost_layer_adapter import (
    adapt_injection_molding_cost_layers,
)
from services.injection_molding_orchestration import (
    InjectionMoldingOrchestrationRequest,
    LabourRateResolution,
    OrchestrationStatus,
    ProductionOverheadResolution,
    orchestrate_injection_molding_cost,
)
from services.setup_cost_calculation import SetupCostInput


@pytest.fixture
def request_data() -> InjectionMoldingOrchestrationRequest:
    return InjectionMoldingOrchestrationRequest(
        material_id="MAT-1",
        part_weight_kg=0.25,
        cycle_time_s=30.0,
        cavities=2,
        material_utilization=0.8,
        oee=0.85,
        operators=0.5,
        process_scrap_rate=0.05,
        setup_applicable=True,
        setup_time_h=2.0,
        batch_size_good_pcs=1000,
        technology_id="IM",
        machine_class_id="CLASS-A",
        currency="EUR",
        material_table=pd.DataFrame(
            {"Material_ID": ["MAT-1"], "Default_Price_EUR_kg": [3.2]}
        ),
        machine_rate_table=pd.DataFrame(
            {
                "Technology_ID": ["IM"],
                "Machine_Class_ID": ["CLASS-A"],
                "Machine_Rate_EUR_hr": [80.0],
            }
        ),
        labour_rate_resolution=LabourRateResolution(
            status="resolved",
            rate_eur_h=24.0,
            currency="EUR",
            currency_basis_verified=True,
        ),
        production_overhead_resolution=ProductionOverheadResolution(
            rate=0.2, approved=True
        ),
    )


def _direct_layered_result(request: InjectionMoldingOrchestrationRequest):
    base = InjectionMoldingBaseProcessInput(
        part_weight_kg=request.part_weight_kg,
        material_price_eur_kg=3.2,
        material_utilization=request.material_utilization,
        cycle_time_s=request.cycle_time_s,
        cavities=request.cavities,
        machine_rate_eur_h=80.0,
        oee=request.oee,
        labour_rate_eur_h=24.0,
        operators=request.operators,
        scrap_rate=request.process_scrap_rate,
        overhead_rate=0.2,
        currency="EUR",
    )
    base_result = InjectionMoldingModel().calculate_base_process(base)
    setup = SetupCostInput(
        setup_time_h=request.setup_time_h,
        machine_rate_eur_h=80.0,
        labour_rate_eur_h=24.0,
        operators=request.operators,
        batch_size_pcs=request.batch_size_good_pcs,
    )
    return adapt_injection_molding_cost_layers(base, base_result, setup=setup)


def test_complete_case_matches_direct_layered_backend(request_data):
    result = orchestrate_injection_molding_cost(request_data)

    assert result.status is OrchestrationStatus.COMPLETE
    assert result.manufacturing_cost_breakdown == _direct_layered_result(request_data)
    assert (
        result.manufacturing_should_cost
        == result.manufacturing_cost_breakdown.manufacturing_should_cost
    )
    assert result.issues == ()
    assert result.resolved_inputs is not None
    assert result.resolved_inputs.currency == "EUR"


@pytest.mark.parametrize(
    "field",
    [
        "material_id",
        "part_weight_kg",
        "cycle_time_s",
        "cavities",
        "material_utilization",
        "oee",
        "operators",
        "process_scrap_rate",
        "setup_applicable",
        "technology_id",
        "machine_class_id",
        "currency",
    ],
)
def test_missing_required_request_fields_are_incomplete(request_data, field):
    result = orchestrate_injection_molding_cost(replace(request_data, **{field: None}))

    assert result.status is OrchestrationStatus.INCOMPLETE
    assert result.manufacturing_cost_breakdown is None
    assert result.manufacturing_should_cost is None
    assert any(issue.field == field for issue in result.issues)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("part_weight_kg", 0),
        ("part_weight_kg", float("nan")),
        ("cycle_time_s", -1),
        ("cavities", 0),
        ("cavities", 1.5),
        ("material_utilization", 0),
        ("material_utilization", 1.1),
        ("oee", 0),
        ("oee", float("inf")),
        ("operators", -0.1),
        ("process_scrap_rate", 1),
        ("setup_time_h", -1),
        ("batch_size_good_pcs", 0),
        ("batch_size_good_pcs", 1.5),
        ("setup_applicable", "yes"),
        ("currency", "USD"),
    ],
)
def test_invalid_supplied_values_are_invalid(request_data, field, value):
    result = orchestrate_injection_molding_cost(replace(request_data, **{field: value}))

    assert result.status is OrchestrationStatus.INVALID
    assert result.manufacturing_cost_breakdown is None
    assert result.manufacturing_should_cost is None
    assert any(issue.field == field for issue in result.issues)


@pytest.mark.parametrize(
    "table",
    [
        None,
        pd.DataFrame(
            {
                "Technology_ID": ["OTHER"],
                "Machine_Class_ID": ["CLASS-A"],
                "Machine_Rate_EUR_hr": [80.0],
            }
        ),
        pd.DataFrame(
            {
                "Technology_ID": ["IM", "IM"],
                "Machine_Class_ID": ["CLASS-A", "CLASS-A"],
                "Machine_Rate_EUR_hr": [80.0, 81.0],
            }
        ),
        *[
            pd.DataFrame(
                {
                    "Technology_ID": ["IM"],
                    "Machine_Class_ID": ["CLASS-A"],
                    "Machine_Rate_EUR_hr": [rate],
                }
            )
            for rate in (
                "malformed",
                0.0,
                -1.0,
                float("nan"),
                float("inf"),
                float("-inf"),
            )
        ],
    ],
)
def test_unavailable_machine_rates_are_incomplete(
    request_data, table
):
    result = orchestrate_injection_molding_cost(
        replace(request_data, machine_rate_table=table)
    )

    assert result.status is OrchestrationStatus.INCOMPLETE
    assert any(issue.field == "machine_rate" for issue in result.issues)


@pytest.mark.parametrize(
    "table",
    [
        None,
        pd.DataFrame({"Material_ID": [], "Default_Price_EUR_kg": []}),
        pd.DataFrame(
            {
                "Material_ID": ["MAT-1", "MAT-1"],
                "Default_Price_EUR_kg": [3.2, 3.3],
            }
        ),
    ],
)
def test_missing_or_duplicate_material_rows_are_incomplete(request_data, table):
    result = orchestrate_injection_molding_cost(
        replace(request_data, material_table=table)
    )

    assert result.status is OrchestrationStatus.INCOMPLETE
    assert result.manufacturing_cost_breakdown is None


@pytest.mark.parametrize("price", [0, -1, float("nan"), "not-a-price"])
def test_invalid_material_price_is_invalid(request_data, price):
    table = pd.DataFrame(
        {"Material_ID": ["MAT-1"], "Default_Price_EUR_kg": [price]}
    )

    result = orchestrate_injection_molding_cost(
        replace(request_data, material_table=table)
    )

    assert result.status is OrchestrationStatus.INVALID
    assert any(issue.field == "material_price_eur_kg" for issue in result.issues)


def test_missing_material_price_is_incomplete(request_data):
    table = pd.DataFrame(
        {"Material_ID": ["MAT-1"], "Default_Price_EUR_kg": [None]}
    )

    result = orchestrate_injection_molding_cost(
        replace(request_data, material_table=table)
    )

    assert result.status is OrchestrationStatus.INCOMPLETE


@pytest.mark.parametrize(
    "resolution",
    [
        None,
        LabourRateResolution(status="unavailable"),
        LabourRateResolution(status="ambiguous"),
        LabourRateResolution(
            status="resolved",
            rate_eur_h=24.0,
            currency="EUR",
            currency_basis_verified=False,
        ),
        LabourRateResolution(
            status="resolved",
            rate_eur_h=24.0,
            currency="USD",
            currency_basis_verified=True,
        ),
    ],
)
def test_missing_unavailable_or_unverified_labour_rate_is_incomplete(
    request_data, resolution
):
    result = orchestrate_injection_molding_cost(
        replace(request_data, labour_rate_resolution=resolution)
    )

    assert result.status is OrchestrationStatus.INCOMPLETE
    assert any(issue.field == "labour_rate" for issue in result.issues)


def test_explicit_verified_zero_labour_rate_is_valid(request_data):
    resolution = LabourRateResolution(
        status="resolved",
        rate_eur_h=0,
        currency="EUR",
        currency_basis_verified=True,
    )

    result = orchestrate_injection_molding_cost(
        replace(request_data, labour_rate_resolution=resolution)
    )

    assert result.status is OrchestrationStatus.COMPLETE
    assert result.resolved_inputs.labour_rate_eur_h == 0


@pytest.mark.parametrize(
    "resolution",
    [
        None,
        ProductionOverheadResolution(rate=0.2, approved=False),
        ProductionOverheadResolution(rate=None, approved=True),
    ],
)
def test_missing_or_unapproved_overhead_is_incomplete(request_data, resolution):
    result = orchestrate_injection_molding_cost(
        replace(request_data, production_overhead_resolution=resolution)
    )

    assert result.status is OrchestrationStatus.INCOMPLETE
    assert any(issue.field == "production_overhead_rate" for issue in result.issues)


@pytest.mark.parametrize("rate", [-0.01, 1.0, float("nan")])
def test_invalid_approved_overhead_rate_is_invalid(request_data, rate):
    result = orchestrate_injection_molding_cost(
        replace(
            request_data,
            production_overhead_resolution=ProductionOverheadResolution(
                rate=rate, approved=True
            ),
        )
    )

    assert result.status is OrchestrationStatus.INVALID


def test_explicit_approved_zero_overhead_is_valid(request_data):
    result = orchestrate_injection_molding_cost(
        replace(
            request_data,
            production_overhead_resolution=ProductionOverheadResolution(
                rate=0, approved=True
            ),
        )
    )

    assert result.status is OrchestrationStatus.COMPLETE
    assert result.resolved_inputs.production_overhead_rate == 0
    assert result.manufacturing_cost_breakdown.process.production_overhead_cost == 0


def test_setup_true_calculates_setup_cost(request_data):
    result = orchestrate_injection_molding_cost(request_data)

    assert result.status is OrchestrationStatus.COMPLETE
    assert result.manufacturing_cost_breakdown.process.setup_cost > 0


@pytest.mark.parametrize("field", ["setup_time_h", "batch_size_good_pcs"])
def test_setup_true_requires_setup_values(request_data, field):
    result = orchestrate_injection_molding_cost(
        replace(request_data, **{field: None})
    )

    assert result.status is OrchestrationStatus.INCOMPLETE
    assert any(issue.field == field for issue in result.issues)


def test_setup_false_uses_explicit_zero_setup_and_needs_no_setup_values(request_data):
    result = orchestrate_injection_molding_cost(
        replace(
            request_data,
            setup_applicable=False,
            setup_time_h=None,
            batch_size_good_pcs=None,
        )
    )

    assert result.status is OrchestrationStatus.COMPLETE
    assert result.manufacturing_cost_breakdown.process.setup_cost == 0
    assert result.resolved_inputs.setup_applicable is False


def test_noncomplete_cases_never_invoke_model_or_adapter(request_data, monkeypatch):
    calls = {"model": 0, "adapter": 0}

    def forbidden_model(self, data):
        calls["model"] += 1
        raise AssertionError("model must not run for incomplete inputs")

    def forbidden_adapter(*_args, **_kwargs):
        calls["adapter"] += 1
        raise AssertionError("adapter must not run for incomplete inputs")

    monkeypatch.setattr(InjectionMoldingModel, "calculate_base_process", forbidden_model)
    monkeypatch.setattr(orchestration, "adapt_injection_molding_cost_layers", forbidden_adapter)

    for changed in (
        replace(request_data, part_weight_kg=None),
        replace(request_data, part_weight_kg=-1),
    ):
        result = orchestrate_injection_molding_cost(changed)
        assert result.status in {
            OrchestrationStatus.INCOMPLETE,
            OrchestrationStatus.INVALID,
        }

    assert calls == {"model": 0, "adapter": 0}


def test_no_missing_values_are_substituted_with_zero(request_data, monkeypatch):
    monkeypatch.setattr(
        orchestration,
        "adapt_injection_molding_cost_layers",
        lambda *_args, **_kwargs: pytest.fail("adapter was called"),
    )

    result = orchestrate_injection_molding_cost(
        replace(request_data, labour_rate_resolution=None)
    )

    assert result.status is OrchestrationStatus.INCOMPLETE
    assert result.manufacturing_cost_breakdown is None
    assert result.manufacturing_should_cost is None


def test_request_and_result_have_no_tooling_or_legacy_total_fields(request_data):
    result = orchestrate_injection_molding_cost(request_data)

    assert "tooling_cost" not in request_data.__dataclass_fields__
    assert "tooling_cost" not in result.__dataclass_fields__
    assert "total_cost" not in result.__dataclass_fields__
    assert not hasattr(result, "legacy_total_cost")


def test_adapter_is_called_once_without_a_second_process_scrap(monkeypatch, request_data):
    calls = []

    def record_adapter(data, result, **kwargs):
        calls.append((data, result, kwargs))
        return adapt_injection_molding_cost_layers(data, result, **kwargs)

    monkeypatch.setattr(
        orchestration, "adapt_injection_molding_cost_layers", record_adapter
    )

    result = orchestrate_injection_molding_cost(request_data)

    assert result.status is OrchestrationStatus.COMPLETE
    assert len(calls) == 1
    assert "process_scrap" not in calls[0][2]
    assert calls[0][0].scrap_rate == request_data.process_scrap_rate


def test_malformed_resolution_is_invalid(request_data):
    result = orchestrate_injection_molding_cost(
        replace(
            request_data,
            labour_rate_resolution=object(),
        )
    )

    assert result.status is OrchestrationStatus.INVALID
