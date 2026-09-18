"""Deterministic rule and regex-based operator directive parser.

Provides fail-safe fallback parsing for operator notes when LLMs are unavailable,
timed out, rate-limited (HTTP 429), or unconfigured.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from app.schemas.contract import (
    BatteryReserveAdjustment,
    DirectiveInterpretation,
    DirectiveType,
    MaxGridAdjustment,
    SolarAdjustment,
    WindowAdjustment,
)


def parse_time_window(text: str) -> List[int]:
    """Extract start-inclusive, end-exclusive 24-hour window from natural language string."""
    t = text.lower()
    t = re.sub(r"\bnoon\b", "12 pm", t)
    t = re.sub(r"\bmidnight\b", "12 am", t)

    # Patterns: 'from X (am/pm) until/to Y (am/pm)' or 'between X and Y'
    pattern = r"(?:from|between)\s+(\d{1,2})(?::\d{2})?\s*(am|pm)?\s*(?:until|to|and)\s+(\d{1,2})(?::\d{2})?\s*(am|pm)"
    match = re.search(pattern, t)
    if not match:
        # Check single time pattern like 'after 6 PM'
        after_match = re.search(r"\bafter\s+(\d{1,2})(?::\d{2})?\s*(am|pm)", t)
        if after_match:
            hr, ampm = int(after_match.group(1)), after_match.group(2)
            s24 = hr if ampm == "am" and hr != 12 else (0 if hr == 12 and ampm == "am" else (12 if hr == 12 else hr + 12))
            return list(range(s24, 24))
        return []

    start_hr, start_ampm, end_hr, end_ampm = match.groups()
    start_hr, end_hr = int(start_hr), int(end_hr)
    if not start_ampm:
        start_ampm = end_ampm

    def to_24(hr: int, ampm: str) -> int:
        if ampm == "am":
            return 0 if hr == 12 else hr
        return 12 if hr == 12 else hr + 12

    s24 = to_24(start_hr, start_ampm)
    e24 = to_24(end_hr, end_ampm)
    if s24 < e24:
        return list(range(s24, e24))
    return []


def parse_single_note(
    note: str,
    battery_capacity_kwh: float,
    note_index: int = 0,
) -> DirectiveInterpretation:
    """Parse an individual operator note deterministically into a DirectiveInterpretation."""
    t = note.lower()

    # 1. Distractor noise rejection
    distractors = [
        "sports office",
        "registration deadline",
        "library",
        "book-return",
        "student affairs",
        "club notices",
        "seminar room",
        "cafeteria",
        "parking lot",
        "gardener",
        "flowers",
    ]
    if any(d in t for d in distractors):
        return DirectiveInterpretation(
            note_index=note_index,
            applies=False,
            directive_type=DirectiveType.NO_OP,
            structured_adjustment=None,
            explanation=f"Deterministic parser identified non-operational note: {note[:60]}",
        )

    hours = parse_time_window(note)
    if not hours:
        return DirectiveInterpretation(
            note_index=note_index,
            applies=False,
            directive_type=DirectiveType.NO_OP,
            structured_adjustment=None,
            explanation=f"No valid time window recognized: {note[:60]}",
        )

    # 2. Solar reduction
    if any(w in t for w in ["solar", "sun", "rooftop", "cloud", "wash", "panel"]):
        if "half" in t:
            factor = 0.5
        elif "reduction" in t:
            m_pct = re.search(r"(\d+(?:\.\d+)?)\s*%", t)
            pct = float(m_pct.group(1)) if m_pct else 80.0
            factor = round((100.0 - pct) / 100.0, 4)
        else:
            m_pct = re.search(r"(\d+(?:\.\d+)?)\s*%", t)
            factor = round(float(m_pct.group(1)) / 100.0, 4) if m_pct else 0.25

        return DirectiveInterpretation(
            note_index=note_index,
            applies=True,
            directive_type=DirectiveType.SOLAR_REDUCTION,
            structured_adjustment=SolarAdjustment(hours=hours, factor=factor),
            explanation=f"Solar reduced to factor {factor} for hours {hours}.",
        )

    # 3. No discharge window
    if any(w in t for w in ["not discharge", "no discharge", "do not discharge"]):
        return DirectiveInterpretation(
            note_index=note_index,
            applies=True,
            directive_type=DirectiveType.NO_DISCHARGE_WINDOW,
            structured_adjustment=WindowAdjustment(hours=hours),
            explanation=f"Discharge prevented during hours {hours}.",
        )

    # 4. No charge window
    if any(
        w in t
        for w in [
            "charger will be isolated",
            "charging circuit will be unavailable",
            "charging is disabled",
            "do not charge",
            "not charge",
        ]
    ):
        return DirectiveInterpretation(
            note_index=note_index,
            applies=True,
            directive_type=DirectiveType.NO_CHARGE_WINDOW,
            structured_adjustment=WindowAdjustment(hours=hours),
            explanation=f"Charging prevented during hours {hours}.",
        )

    # 5. Minimum battery reserve
    if any(w in t for w in ["keep at least", "requires at least", "maintain at least", "reserve"]) and (
        "battery" in t or "kwh" in t or "%" in t
    ):
        if "%" in t:
            m_pct = re.search(r"(\d+(?:\.\d+)?)\s*%", t)
            pct = float(m_pct.group(1)) if m_pct else 50.0
            min_kwh = round(battery_capacity_kwh * (pct / 100.0), 4)
        else:
            m_kwh = re.search(r"(\d+(?:\.\d+)?)\s*kwh", t)
            min_kwh = float(m_kwh.group(1)) if m_kwh else 80.0

        return DirectiveInterpretation(
            note_index=note_index,
            applies=True,
            directive_type=DirectiveType.MINIMUM_BATTERY_RESERVE,
            structured_adjustment=BatteryReserveAdjustment(
                hours=hours, minimum_energy_kwh=min_kwh
            ),
            explanation=f"Battery reserve elevated to {min_kwh} kWh for hours {hours}.",
        )

    # 6. Max grid import window
    if any(
        w in t
        for w in [
            "grid import must not exceed",
            "transformer limit is",
            "grid intake must stay",
            "grid limit",
            "grid cap",
        ]
    ):
        m_kwh = re.search(r"(\d+(?:\.\d+)?)\s*kwh", t)
        cap = float(m_kwh.group(1)) if m_kwh else 155.0

        return DirectiveInterpretation(
            note_index=note_index,
            applies=True,
            directive_type=DirectiveType.MAX_GRID_WINDOW,
            structured_adjustment=MaxGridAdjustment(hours=hours, max_grid_kwh=cap),
            explanation=f"Grid intake capped at {cap} kWh for hours {hours}.",
        )

    # Default fallback to no_op
    return DirectiveInterpretation(
        note_index=note_index,
        applies=False,
        directive_type=DirectiveType.NO_OP,
        structured_adjustment=None,
        explanation=f"Note did not match known operational patterns: {note[:60]}",
    )


def extract_directives_deterministically(
    notes: List[str],
    battery_capacity_kwh: float,
) -> List[DirectiveInterpretation]:
    """Parse list of operator notes deterministically."""
    return [
        parse_single_note(note, battery_capacity_kwh, note_index=idx)
        for idx, note in enumerate(notes)
    ]
