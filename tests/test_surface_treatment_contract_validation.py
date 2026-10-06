import ast
import copy
import json
from pathlib import Path

from jsonschema import Draft202012Validator

from services.surface_treatment_contract_validation import (
    validate_surface_treatment_contract,
)


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "schemas" / "surface_treatment_contract.schema.json"


def _payload():
    return {
        "input": {
            "surface_treatment": "None",
            "surface_area_m2": 0,
            "surface_treatment_addon_eur_per_part": 0,
        },
        "context": {
            "selected_region": "Denmark",
            "calculation_currency": "EUR",
        },
        "rates": [],
    }


def _valid_rate():
    return {
        "treatment": "Anodizing",
        "region": "Denmark",
        "rate_eur_m2": 1.25,
        "status": "Active",
        "source": "Approved rate list",
    }


def _valid_calculated_result():
    return {
        "surface_treatment_cost_eur_per_part": 2.5,
        "surface_treatment_cost_status": "calculated",
        "surface_treatment_rate_eur_m2": 1.25,
        "surface_treatment_rate_source": "Approved rate list",
    }


def _assert_invalid(payload):
    result = validate_surface_treatment_contract(payload)
    assert result["valid"] is False
    assert result["errors"]
    assert all(set(error) == {"path", "message"} for error in result["errors"])
    return result


def test_schema_is_valid_draft_2020_12():
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    Draft202012Validator.check_schema(schema)


def test_valid_none_treatment():
    assert validate_surface_treatment_contract(_payload()) == {
        "valid": True,
        "errors": [],
    }


def test_valid_selected_treatment_and_rate():
    payload = _payload()
    payload["input"] = {
        "surface_treatment": "Anodizing",
        "surface_area_m2": 2.0,
        "surface_treatment_addon_eur_per_part": 0.0,
    }
    payload["rates"] = [_valid_rate()]
    assert validate_surface_treatment_contract(payload)["valid"] is True


def test_valid_calculated_result():
    payload = _payload()
    payload["input"] = {
        "surface_treatment": "Anodizing",
        "surface_area_m2": 2.0,
        "surface_treatment_addon_eur_per_part": 0.0,
    }
    payload["rates"] = [_valid_rate()]
    payload["result"] = _valid_calculated_result()
    assert validate_surface_treatment_contract(payload)["valid"] is True


def test_missing_required_field_is_invalid():
    payload = _payload()
    del payload["input"]["surface_area_m2"]
    result = _assert_invalid(payload)
    assert any(error["path"] == "input" for error in result["errors"])


def test_unknown_treatment_is_invalid():
    payload = _payload()
    payload["input"]["surface_treatment"] = "Chrome"
    _assert_invalid(payload)


def test_none_treatment_rejects_positive_area():
    payload = _payload()
    payload["input"]["surface_area_m2"] = 1
    _assert_invalid(payload)


def test_none_treatment_rejects_positive_addon():
    payload = _payload()
    payload["input"]["surface_treatment_addon_eur_per_part"] = 1
    _assert_invalid(payload)


def test_selected_treatment_rejects_zero_area():
    payload = _payload()
    payload["input"]["surface_treatment"] = "PVD"
    _assert_invalid(payload)


def test_negative_area_or_addon_is_invalid():
    payload = _payload()
    payload["input"]["surface_area_m2"] = -1
    area_result = _assert_invalid(payload)
    assert any(
        error["path"] == "input.surface_area_m2"
        for error in area_result["errors"]
    )

    payload = _payload()
    payload["input"]["surface_treatment_addon_eur_per_part"] = -1
    addon_result = _assert_invalid(payload)
    assert any(
        error["path"] == "input.surface_treatment_addon_eur_per_part"
        for error in addon_result["errors"]
    )


def test_non_eur_calculation_currency_is_invalid():
    payload = _payload()
    payload["context"]["calculation_currency"] = "DKK"
    result = _assert_invalid(payload)
    assert any(
        error["path"] == "context.calculation_currency"
        for error in result["errors"]
    )


def test_empty_region_is_invalid():
    payload = _payload()
    payload["context"]["selected_region"] = ""
    _assert_invalid(payload)


def test_rate_must_be_positive():
    for rate in (0, -1):
        payload = _payload()
        payload["rates"] = [_valid_rate() | {"rate_eur_m2": rate}]
        result = _assert_invalid(payload)
        assert any(
            error["path"] == "rates.0.rate_eur_m2"
            for error in result["errors"]
        )


def test_inactive_rate_is_structurally_valid():
    payload = _payload()
    payload["rates"] = [_valid_rate() | {"status": "Inactive"}]
    assert validate_surface_treatment_contract(payload)["valid"] is True


def test_empty_rate_source_is_invalid():
    payload = _payload()
    payload["rates"] = [_valid_rate() | {"source": ""}]
    _assert_invalid(payload)


def test_invalid_rate_status_is_rejected():
    payload = _payload()
    payload["rates"] = [_valid_rate() | {"status": "Pending"}]
    _assert_invalid(payload)


def test_not_required_result_requires_zero_cost_and_null_rate_source():
    payload = _payload()
    payload["result"] = {
        "surface_treatment_cost_eur_per_part": 1,
        "surface_treatment_cost_status": "not_required",
        "surface_treatment_rate_eur_m2": None,
        "surface_treatment_rate_source": None,
    }
    _assert_invalid(payload)


def test_calculated_result_rejects_null_rate():
    payload = _payload()
    payload["result"] = _valid_calculated_result() | {
        "surface_treatment_rate_eur_m2": None
    }
    _assert_invalid(payload)


def test_incomplete_result_requires_null_cost():
    payload = _payload()
    payload["result"] = {
        "surface_treatment_cost_eur_per_part": 1,
        "surface_treatment_cost_status": "incomplete",
        "surface_treatment_rate_eur_m2": None,
        "surface_treatment_rate_source": None,
    }
    _assert_invalid(payload)


def test_additional_unexpected_property_is_invalid():
    payload = _payload()
    payload["unexpected"] = True
    _assert_invalid(payload)


def test_validation_does_not_mutate_payload():
    payload = _payload()
    payload["rates"] = [_valid_rate()]
    payload["input"]["surface_treatment"] = "Anodizing"
    payload["input"]["surface_area_m2"] = 2
    before = copy.deepcopy(payload)

    validate_surface_treatment_contract(payload)

    assert payload == before


def test_error_paths_are_clear_and_deterministic():
    payload = _payload()
    payload["input"]["surface_area_m2"] = -1
    payload["rates"] = [_valid_rate() | {"rate_eur_m2": 0}]
    first = validate_surface_treatment_contract(payload)
    second = validate_surface_treatment_contract(payload)

    assert first == second
    paths = {error["path"] for error in first["errors"]}
    assert "input.surface_area_m2" in paths
    assert "rates.0.rate_eur_m2" in paths


def test_validation_service_has_no_cost_formula_or_rate_resolver():
    source_path = (
        ROOT / "services" / "surface_treatment_contract_validation.py"
    )
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    imported_modules = {
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    imported_modules.update(
        node.module.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    )
    assert "streamlit" not in imported_modules
    assert "openpyxl" not in imported_modules
    assert not any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and ("calculate" in node.func.id or "resolve" in node.func.id)
        for node in ast.walk(tree)
    )
