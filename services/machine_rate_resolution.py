from __future__ import annotations

import math
import re
from dataclasses import dataclass, replace
from typing import Mapping

import pandas as pd

from services.masterdata_service import MasterDataError, find_column


technology_name_mapping = {
    "HPDC": "Die Casting",
    "CNC Machining": "CNC Machining",
    "HP Multi Jet Fusion": "HP Multi Jet Fusion",
}

_HPDC_MACHINE_SIZE_ORDER = {"small": 0, "medium": 1, "large": 2}


@dataclass(frozen=True)
class HPDCMachineSelection:
    process: str
    size: str
    machine_hour_rate_eur_hr: float
    max_part_length_mm: float
    max_part_width_mm: float
    max_part_weight_kg: float
    selection_method: str
    selection_reason: str

    @property
    def max_part_size(self) -> str:
        return f"{self.max_part_length_mm:g} x {self.max_part_width_mm:g} mm"


def _parse_max_part_size(value: object, machine_size: str) -> tuple[float, float]:
    if not isinstance(value, str):
        raise MasterDataError(
            f"Max Part Size for {machine_size} must contain two dimensions."
        )
    match = re.fullmatch(
        r"\s*(\d+(?:[.,]\d+)?)\s*(?:mm)?\s*[xX×*]\s*"
        r"(\d+(?:[.,]\d+)?)\s*(?:mm)?\s*",
        value,
        flags=re.IGNORECASE,
    )
    if match is None:
        raise MasterDataError(
            f"Max Part Size for {machine_size} must contain exactly two dimensions; "
            f"received {value!r}."
        )
    try:
        length, width = (
            float(number.replace(",", ".")) for number in match.groups()
        )
    except (TypeError, ValueError, OverflowError) as exc:
        raise MasterDataError(
            f"Max Part Size for {machine_size} could not be parsed: {value!r}."
        ) from exc
    if not math.isfinite(length) or not math.isfinite(width) or length <= 0 or width <= 0:
        raise MasterDataError(
            f"Max Part Size for {machine_size} must contain finite, positive dimensions."
        )
    return length, width


def _parse_positive_number(value: object, column: str, machine_size: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise MasterDataError(
            f"{column} for {machine_size} must be a positive number; received {value!r}."
        ) from exc
    if not math.isfinite(number) or number <= 0:
        raise MasterDataError(
            f"{column} for {machine_size} must be a finite, positive number."
        )
    return number


def _layout_fits(
    required_length_mm: float,
    required_width_mm: float,
    max_length_mm: float,
    max_width_mm: float,
) -> bool:
    normal_fit = (
        required_length_mm <= max_length_mm
        and required_width_mm <= max_width_mm
    )
    rotated_fit = (
        required_width_mm <= max_length_mm
        and required_length_mm <= max_width_mm
    )
    return normal_fit or rotated_fit


def resolve_hpdc_machine(
    machine_data: pd.DataFrame,
    required_layout_length_mm: float,
    required_layout_width_mm: float,
    total_shot_weight_kg: float,
) -> HPDCMachineSelection:
    if not isinstance(machine_data, pd.DataFrame) or machine_data.empty:
        raise MasterDataError("HPDC machine masterdata is empty or unavailable.")
    for label, value in {
        "required_layout_length_mm": required_layout_length_mm,
        "required_layout_width_mm": required_layout_width_mm,
        "total_shot_weight_kg": total_shot_weight_kg,
    }.items():
        if not math.isfinite(value) or value <= 0:
            raise ValueError(f"{label} must be finite and greater than zero.")

    process_column = find_column(machine_data, ["Process"])
    size_column = find_column(machine_data, ["Size"])
    rate_column = find_column(machine_data, ["Machine Hour Rate €/h"])
    max_size_column = find_column(machine_data, ["Max Part Size"])
    max_weight_column = find_column(machine_data, ["Max Part Weight"])

    source_process = technology_name_mapping["HPDC"]
    process_rows = machine_data[
        machine_data[process_column]
        .astype(str)
        .str.strip()
        .str.casefold()
        .eq(source_process.casefold())
    ]
    if process_rows.empty:
        raise MasterDataError(
            f"No HPDC machine rows were found for Process={source_process!r}."
        )

    candidates: list[HPDCMachineSelection] = []
    for _, row in process_rows.iterrows():
        raw_size = str(row[size_column]).strip()
        size_key = raw_size.casefold()
        if size_key not in _HPDC_MACHINE_SIZE_ORDER:
            raise MasterDataError(
                f"Unsupported HPDC machine Size {raw_size!r}; expected Small, Medium, or Large."
            )
        length, width = _parse_max_part_size(row[max_size_column], raw_size)
        max_weight = _parse_positive_number(
            row[max_weight_column], max_weight_column, raw_size
        )
        rate = _parse_positive_number(row[rate_column], rate_column, raw_size)
        candidates.append(
            HPDCMachineSelection(
                process=source_process,
                size=raw_size,
                machine_hour_rate_eur_hr=rate,
                max_part_length_mm=length,
                max_part_width_mm=width,
                max_part_weight_kg=max_weight,
                selection_method="Smallest eligible machine class",
                selection_reason="",
            )
        )

    candidates.sort(key=lambda machine: _HPDC_MACHINE_SIZE_ORDER[machine.size.casefold()])
    largest_class = _HPDC_MACHINE_SIZE_ORDER[
        max(candidates, key=lambda machine: _HPDC_MACHINE_SIZE_ORDER[machine.size.casefold()])
        .size.casefold()
    ]
    largest_candidates = [
        machine
        for machine in candidates
        if _HPDC_MACHINE_SIZE_ORDER[machine.size.casefold()] == largest_class
    ]

    for machine in candidates:
        size_passed = _layout_fits(
            required_layout_length_mm,
            required_layout_width_mm,
            machine.max_part_length_mm,
            machine.max_part_width_mm,
        )
        weight_passed = total_shot_weight_kg <= machine.max_part_weight_kg
        if size_passed and weight_passed:
            orientation = (
                "rotated"
                if required_layout_width_mm <= machine.max_part_length_mm
                and required_layout_length_mm <= machine.max_part_width_mm
                and not (
                    required_layout_length_mm <= machine.max_part_length_mm
                    and required_layout_width_mm <= machine.max_part_width_mm
                )
                else "normal"
            )
            reason = (
                f"{machine.size} is the smallest eligible class: the required "
                f"{required_layout_length_mm:g} x {required_layout_width_mm:g} mm "
                f"layout fits {orientation}, and the {total_shot_weight_kg:g} kg "
                f"shot is within its {machine.max_part_weight_kg:g} kg limit."
            )
            return replace(machine, selection_reason=reason)

    largest = largest_candidates[0]
    largest_size_passed = _layout_fits(
        required_layout_length_mm,
        required_layout_width_mm,
        largest.max_part_length_mm,
        largest.max_part_width_mm,
    )
    largest_weight_passed = total_shot_weight_kg <= largest.max_part_weight_kg
    failed_constraints = []
    if not largest_size_passed:
        failed_constraints.append("layout size")
    if not largest_weight_passed:
        failed_constraints.append("shot weight")
    raise ValueError(
        "No eligible HPDC machine was found. "
        f"Required layout size: {required_layout_length_mm:g} x "
        f"{required_layout_width_mm:g} mm (normal or rotated); required shot "
        f"weight: {total_shot_weight_kg:g} kg. Largest available machine "
        f"capacity ({largest.size}): {largest.max_part_size} and "
        f"{largest.max_part_weight_kg:g} kg. Failed constraints: "
        f"{' and '.join(failed_constraints)}."
    )


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
