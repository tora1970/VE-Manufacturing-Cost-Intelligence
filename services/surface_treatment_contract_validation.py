from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator


_SCHEMA_PATH = (
    Path(__file__).resolve().parents[1]
    / "schemas"
    / "surface_treatment_contract.schema.json"
)


def validate_surface_treatment_contract(payload: Any) -> dict[str, Any]:
    with _SCHEMA_PATH.open(encoding="utf-8") as schema_file:
        schema = json.load(schema_file)

    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    errors = []
    for error in validator.iter_errors(payload):
        path = ".".join(str(part) for part in error.absolute_path) or "$"
        errors.append({"path": path, "message": error.message})

    errors.sort(key=lambda item: (item["path"], item["message"]))
    return {"valid": not errors, "errors": errors}
