from __future__ import annotations

import math
from typing import Any


def calculate_machine_cost(
    cycle_time_sec: Any,
    machine_rate_eur_hr: Any,
) -> tuple[float | None, str]:
    if cycle_time_sec is None or machine_rate_eur_hr is None:
        return None, "unavailable"

    try:
        cycle_time = float(cycle_time_sec)
        machine_rate = float(machine_rate_eur_hr)
    except (TypeError, ValueError, OverflowError):
        return None, "unavailable"

    if (
        not math.isfinite(cycle_time)
        or cycle_time <= 0
        or not math.isfinite(machine_rate)
        or machine_rate < 0
    ):
        return None, "unavailable"

    machine_cost = (cycle_time / 3600) * machine_rate
    if not math.isfinite(machine_cost):
        return None, "unavailable"

    return machine_cost, "calculated"
