"""Guardrail validation and normalization layer for LLM directive interpretations.

Enforces strict physical bounds, index continuity, time-window constraints,
and safe degradation to prevent ill-conditioned optimization problems.
"""

from __future__ import annotations

import logging
from typing import Any, List, Optional

from app.schemas.contract import (
    BatteryReserveAdjustment,
    DirectiveInterpretation,
    DirectiveType,
    MaxGridAdjustment,
    SolarAdjustment,
    StructuredAdjustment,
    WindowAdjustment,
)

logger = logging.getLogger("gridwise.optimizer.guardrails")


def _sanitize_hours(hours: Any) -> List[int]:
    """Extract, filter, deduplicate, and sort valid hour integers in [0..23]."""
    if not isinstance(hours, (list, tuple, set)):
        return []

    valid_hours = set()
    for h in hours:
        if isinstance(h, int) and 0 <= h <= 23:
            valid_hours.add(h)
        elif isinstance(h, float) and h.is_integer() and 0 <= int(h) <= 23:
            valid_hours.add(int(h))

    return sorted(valid_hours)


def _convert_to_noop(
    note_index: int,
    original: Optional[DirectiveInterpretation],
    reason: str,
) -> DirectiveInterpretation:
    """Safely degrade an unrecoverable directive to a no_op."""
    logger.warning("Directive at index %d degraded to no_op: %s", note_index, reason)
    original_exp = f" Original note context: {original.explanation}" if original else ""
    return DirectiveInterpretation(
        note_index=note_index,
        applies=False,
        directive_type=DirectiveType.NO_OP,
        structured_adjustment=None,
        explanation=f"Safely converted to no_op (guardrail validation: {reason}).{original_exp}",
    )


def validate_and_sanitize_directives(
    raw_interpretations: List[DirectiveInterpretation],
    battery_capacity: float,
) -> List[DirectiveInterpretation]:
    """Validate, sanitize, and normalize directive interpretations before optimization.

    Enforces the following invariant rules:
    1. Note indices are contiguous from 0 to len(raw_interpretations) - 1, sorted by note_index.
    2. All directive time windows have deduplicated, sorted hours within 0..23.
    3. Solar reduction factor is clamped strictly within [0.0, 1.0].
    4. Minimum battery reserve is clamped within [0.0, battery_capacity].
    5. Max grid import cap is clamped to >= 0.0.
    6. If applies=False or directive_type is no_op, enforces applies=False, directive_type='no_op',
       and structured_adjustment=None.
    7. Safe failure: Any directive with unrecoverable structures or missing hours is converted to no_op.

    Parameters
    ----------
    raw_interpretations : list[DirectiveInterpretation]
        Raw directives extracted by the LLM or upstream pipeline.
    battery_capacity : float
        Total battery capacity in kWh used for reserve ceiling clamping.

    Returns
    -------
    list[DirectiveInterpretation]
        Sanitized, validated, and contiguous list of directives.
    """
    if not raw_interpretations:
        return []

    capacity_cap = max(0.0, float(battery_capacity))

    # Sort items primarily by existing note_index, preserving stable tie-breakers
    sorted_raw = sorted(
        raw_interpretations,
        key=lambda item: item.note_index if hasattr(item, "note_index") else 0,
    )

    sanitized_results: List[DirectiveInterpretation] = []

    for target_idx, raw_item in enumerate(sorted_raw):
        try:
            # Rule: If item is marked no_op or does not apply, normalize cleanly
            if not raw_item.applies or raw_item.directive_type == DirectiveType.NO_OP:
                sanitized_results.append(
                    DirectiveInterpretation(
                        note_index=target_idx,
                        applies=False,
                        directive_type=DirectiveType.NO_OP,
                        structured_adjustment=None,
                        explanation=raw_item.explanation or "Ignored non-actionable note.",
                    )
                )
                continue

            raw_adj = raw_item.structured_adjustment
            if raw_adj is None:
                sanitized_results.append(
                    _convert_to_noop(
                        target_idx,
                        raw_item,
                        "Directive marked active but structured_adjustment is None.",
                    )
                )
                continue

            # Extract hours from the adjustment
            hours_attr = getattr(raw_adj, "hours", None)
            if hours_attr is None and isinstance(raw_adj, dict):
                hours_attr = raw_adj.get("hours")

            sanitized_hours = _sanitize_hours(hours_attr)
            if not sanitized_hours:
                sanitized_results.append(
                    _convert_to_noop(
                        target_idx,
                        raw_item,
                        "Directive contains no valid hours in range [0..23].",
                    )
                )
                continue

            # Route by directive type and enforce domain bounds
            sanitized_adj: Optional[StructuredAdjustment] = None

            if raw_item.directive_type == DirectiveType.SOLAR_REDUCTION:
                raw_factor = getattr(raw_adj, "factor", None)
                if raw_factor is None and isinstance(raw_adj, dict):
                    raw_factor = raw_adj.get("factor")

                if raw_factor is None:
                    sanitized_results.append(
                        _convert_to_noop(
                            target_idx,
                            raw_item,
                            "Missing 'factor' in solar_reduction adjustment.",
                        )
                    )
                    continue

                # Clamp factor strictly between 0.0 and 1.0
                clamped_factor = round(max(0.0, min(1.0, float(raw_factor))), 4)
                sanitized_adj = SolarAdjustment(hours=sanitized_hours, factor=clamped_factor)

            elif raw_item.directive_type == DirectiveType.MINIMUM_BATTERY_RESERVE:
                raw_min = getattr(raw_adj, "minimum_energy_kwh", None)
                if raw_min is None and isinstance(raw_adj, dict):
                    raw_min = raw_adj.get("minimum_energy_kwh")

                if raw_min is None:
                    sanitized_results.append(
                        _convert_to_noop(
                            target_idx,
                            raw_item,
                            "Missing 'minimum_energy_kwh' in battery reserve adjustment.",
                        )
                    )
                    continue

                # Clamp reserve energy strictly between 0.0 and battery_capacity
                clamped_min = round(max(0.0, min(capacity_cap, float(raw_min))), 4)
                sanitized_adj = BatteryReserveAdjustment(
                    hours=sanitized_hours, minimum_energy_kwh=clamped_min
                )

            elif raw_item.directive_type in (
                DirectiveType.NO_CHARGE_WINDOW,
                DirectiveType.NO_DISCHARGE_WINDOW,
            ):
                sanitized_adj = WindowAdjustment(hours=sanitized_hours)

            elif raw_item.directive_type == DirectiveType.MAX_GRID_WINDOW:
                raw_cap = getattr(raw_adj, "max_grid_kwh", None)
                if raw_cap is None and isinstance(raw_adj, dict):
                    raw_cap = raw_adj.get("max_grid_kwh")

                if raw_cap is None:
                    sanitized_results.append(
                        _convert_to_noop(
                            target_idx,
                            raw_item,
                            "Missing 'max_grid_kwh' in max_grid_window adjustment.",
                        )
                    )
                    continue

                # Clamp grid cap to >= 0.0
                clamped_cap = round(max(0.0, float(raw_cap)), 4)
                sanitized_adj = MaxGridAdjustment(
                    hours=sanitized_hours, max_grid_kwh=clamped_cap
                )

            else:
                sanitized_results.append(
                    _convert_to_noop(
                        target_idx,
                        raw_item,
                        f"Unrecognized directive_type: '{raw_item.directive_type}'.",
                    )
                )
                continue

            # Successfully validated and sanitized
            sanitized_results.append(
                DirectiveInterpretation(
                    note_index=target_idx,
                    applies=True,
                    directive_type=raw_item.directive_type,
                    structured_adjustment=sanitized_adj,
                    explanation=raw_item.explanation,
                )
            )

        except Exception as err:
            sanitized_results.append(
                _convert_to_noop(
                    target_idx,
                    raw_item,
                    f"Unexpected validation error: {type(err).__name__} ({err})",
                )
            )

    return sanitized_results


__all__ = [
    "validate_and_sanitize_directives",
]
