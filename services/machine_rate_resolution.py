from __future__ import annotations

import math
from typing import Mapping

import pandas as pd


technology_name_mapping = {
    "HPDC": "Die Casting",
    "CNC Machining": "CNC Machining",
    "HP Multi Jet Fusion": "HP Multi Jet Fusion",
}


def resolve_machine_rate(
    technology: str,
    name_mapping: Mapping[str, str],
    technology_cost_library: pd.DataFrame | None,
) -> tuple[float | None, str]:
    technology_name = name_mapping.get(technology)
    if technology_name is None or technology_cost_library is None:
        return None, "unavailable"

    required_columns = {"Technology_Name", "Machine_Rate_EUR_hr"}
    if not required_columns.issubset(technology_cost_library.columns):
        return None, "unavailable"

    matching_rows = technology_cost_library[
        technology_cost_library["Technology_Name"].eq(technology_name)
    ]
    if len(matching_rows) != 1:
        return None, "unavailable"

    raw_rate = matching_rows.iloc[0]["Machine_Rate_EUR_hr"]
    try:
        rate = float(raw_rate)
    except (TypeError, ValueError, OverflowError):
        return None, "unavailable"

    if not math.isfinite(rate) or rate < 0:
        return None, "unavailable"

    return rate, "resolved"


def resolve_injection_molding_machine_rate(
    technology_id: str,
    machine_class_id: str,
    rate_table: pd.DataFrame | None,
) -> tuple[float | None, str]:
    if (
        not isinstance(technology_id, str)
        or not technology_id.strip()
        or not isinstance(machine_class_id, str)
        or not machine_class_id.strip()
        or not isinstance(rate_table, pd.DataFrame)
    ):
        return None, "unavailable"

    required_columns = {
        "Technology_ID",
        "Machine_Class_ID",
        "Machine_Rate_EUR_hr",
    }
    if (
        not required_columns.issubset(rate_table.columns)
        or any(list(rate_table.columns).count(column) != 1 for column in required_columns)
    ):
        return None, "unavailable"

    matching_rows = rate_table.loc[
        rate_table["Technology_ID"].eq(technology_id)
        & rate_table["Machine_Class_ID"].eq(machine_class_id)
    ]
    if len(matching_rows) != 1:
        return None, "unavailable"

    try:
        rate = float(matching_rows.iloc[0]["Machine_Rate_EUR_hr"])
    except (TypeError, ValueError, OverflowError):
        return None, "unavailable"

    if not math.isfinite(rate) or rate <= 0:
        return None, "unavailable"

    return rate, "resolved"
