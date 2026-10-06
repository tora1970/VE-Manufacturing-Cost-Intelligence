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
