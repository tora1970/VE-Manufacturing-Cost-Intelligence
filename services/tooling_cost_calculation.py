from __future__ import annotations

import math
from typing import Any, Tuple


def calculate_analytical_tooling_cost(
    tooling_capex_eur: Any,
    tooling_amortization_volume_pcs: Any,
) -> Tuple[float | None, str]:
    """Return analytical tooling cost per part and status."""

    if tooling_capex_eur is None or tooling_amortization_volume_pcs is None:
        return (None, "unavailable")

    try:
        capex = float(tooling_capex_eur)
        volume = float(tooling_amortization_volume_pcs)
    except (TypeError, ValueError, OverflowError):
        return (None, "unavailable")

    if not math.isfinite(capex) or not math.isfinite(volume):
        return (None, "unavailable")

    if capex < 0 or volume <= 0:
        return (None, "unavailable")

    analytical_tooling_cost_per_part_eur = capex / volume

    if not math.isfinite(analytical_tooling_cost_per_part_eur):
        return (None, "unavailable")

    return (float(analytical_tooling_cost_per_part_eur), "calculated")
