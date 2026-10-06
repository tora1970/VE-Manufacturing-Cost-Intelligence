from __future__ import annotations

import math
from typing import Any


def classify_tooling_capex_status(
    tooling_capex_eur: Any,
    tooling_amortization_volume_pcs: Any,
) -> str:
    try:
        capex = float(tooling_capex_eur)
        volume = float(tooling_amortization_volume_pcs)
    except (TypeError, ValueError, OverflowError):
        return "unavailable"

    if not math.isfinite(capex) or not math.isfinite(volume):
        return "unavailable"
    if capex < 0 or volume < 0:
        raise ValueError("Tooling CAPEX and amortization volume cannot be negative.")

    if capex > 0 and volume > 0:
        return "ready_for_analysis"
    if capex == 0 and volume == 0:
        return "not_provided"
    return "incomplete"
