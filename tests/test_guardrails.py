"""Unit tests for app/optimizer/guardrails.py."""

from unittest.mock import MagicMock

import pytest

from app.optimizer.guardrails import validate_and_sanitize_directives
from app.schemas.contract import (
    BatteryReserveAdjustment,
    DirectiveInterpretation,
    DirectiveType,
    MaxGridAdjustment,
    SolarAdjustment,
    WindowAdjustment,
)


class TestGuardrails:
    """Test guardrail validation, bounds clamping, and safe degradation."""

    def test_empty_directives(self):
        assert validate_and_sanitize_directives([], battery_capacity=200.0) == []

    def test_note_index_sorting_and_continuity(self):
        raw = [
            DirectiveInterpretation(
                note_index=2,
                applies=False,
                directive_type=DirectiveType.NO_OP,
                structured_adjustment=None,
                explanation="Third note",
            ),
            DirectiveInterpretation(
                note_index=0,
                applies=False,
                directive_type=DirectiveType.NO_OP,
                structured_adjustment=None,
                explanation="First note",
            ),
            DirectiveInterpretation(
                note_index=1,
                applies=False,
                directive_type=DirectiveType.NO_OP,
                structured_adjustment=None,
                explanation="Second note",
            ),
        ]
        sanitized = validate_and_sanitize_directives(raw, battery_capacity=200.0)
        assert len(sanitized) == 3
        assert [d.note_index for d in sanitized] == [0, 1, 2]
        assert sanitized[0].explanation == "First note"
        assert sanitized[1].explanation == "Second note"
        assert sanitized[2].explanation == "Third note"

    def test_hours_deduplication_filtering_and_sorting(self):
        raw = [
            DirectiveInterpretation(
                note_index=0,
                applies=True,
                directive_type=DirectiveType.NO_CHARGE_WINDOW,
                structured_adjustment=WindowAdjustment(hours=[16, 14, 15, 14, 16]),
                explanation="Messy hours",
            )
        ]
        sanitized = validate_and_sanitize_directives(raw, battery_capacity=200.0)
        assert len(sanitized) == 1
        assert sanitized[0].applies is True
        assert isinstance(sanitized[0].structured_adjustment, WindowAdjustment)
        assert sanitized[0].structured_adjustment.hours == [14, 15, 16]

    def test_solar_reduction_factor_clamping(self):
        # Factor above 1.0 clamped to 1.0
        # Factor below 0.0 clamped to 0.0
        raw_upper = DirectiveInterpretation(
            note_index=0,
            applies=True,
            directive_type=DirectiveType.SOLAR_REDUCTION,
            structured_adjustment=SolarAdjustment(hours=[12, 13], factor=1.5),
            explanation="Over 100%",
        )
        sanitized_upper = validate_and_sanitize_directives([raw_upper], battery_capacity=200.0)
        assert sanitized_upper[0].structured_adjustment.factor == 1.0

        # With mock/dict to test negative factor clamping
        mock_raw = MagicMock()
        mock_raw.note_index = 0
        mock_raw.applies = True
        mock_raw.directive_type = DirectiveType.SOLAR_REDUCTION
        mock_raw.structured_adjustment = MagicMock()
        mock_raw.structured_adjustment.hours = [10, 11]
        mock_raw.structured_adjustment.factor = -0.5
        mock_raw.explanation = "Negative factor"

        sanitized_lower = validate_and_sanitize_directives([mock_raw], battery_capacity=200.0)
        assert sanitized_lower[0].applies is True
        assert sanitized_lower[0].structured_adjustment.factor == 0.0

    def test_battery_reserve_clamping(self):
        battery_cap = 200.0

        # Minimum energy greater than battery capacity
        raw_exceed = DirectiveInterpretation(
            note_index=0,
            applies=True,
            directive_type=DirectiveType.MINIMUM_BATTERY_RESERVE,
            structured_adjustment=BatteryReserveAdjustment(
                hours=[18, 19], minimum_energy_kwh=350.0
            ),
            explanation="Exceeds capacity",
        )
        sanitized = validate_and_sanitize_directives([raw_exceed], battery_capacity=battery_cap)
        assert sanitized[0].structured_adjustment.minimum_energy_kwh == 200.0

        # Normal reserve within bounds
        raw_normal = DirectiveInterpretation(
            note_index=0,
            applies=True,
            directive_type=DirectiveType.MINIMUM_BATTERY_RESERVE,
            structured_adjustment=BatteryReserveAdjustment(
                hours=[18, 19], minimum_energy_kwh=80.0
            ),
            explanation="Normal reserve",
        )
        sanitized_normal = validate_and_sanitize_directives([raw_normal], battery_capacity=battery_cap)
        assert sanitized_normal[0].structured_adjustment.minimum_energy_kwh == 80.0

    def test_max_grid_window_clamping(self):
        raw_normal = DirectiveInterpretation(
            note_index=0,
            applies=True,
            directive_type=DirectiveType.MAX_GRID_WINDOW,
            structured_adjustment=MaxGridAdjustment(hours=[2, 3, 4], max_grid_kwh=0.0),
            explanation="Grid outage",
        )
        sanitized = validate_and_sanitize_directives([raw_normal], battery_capacity=200.0)
        assert sanitized[0].structured_adjustment.max_grid_kwh == 0.0

    def test_no_op_normalization(self):
        # If raw item applies=False, guardrail guarantees no_op and structured_adjustment=None
        raw_noop = DirectiveInterpretation(
            note_index=0,
            applies=False,
            directive_type=DirectiveType.NO_OP,
            structured_adjustment=None,
            explanation="Cafeteria menu changed",
        )
        sanitized = validate_and_sanitize_directives([raw_noop], battery_capacity=200.0)
        assert sanitized[0].applies is False
        assert sanitized[0].directive_type == DirectiveType.NO_OP
        assert sanitized[0].structured_adjustment is None

    def test_safe_degradation_on_empty_hours(self):
        # If adjustment has empty hours (e.g. hours = [])
        mock_raw = MagicMock()
        mock_raw.note_index = 0
        mock_raw.applies = True
        mock_raw.directive_type = DirectiveType.NO_CHARGE_WINDOW
        mock_raw.structured_adjustment = MagicMock()
        mock_raw.structured_adjustment.hours = [-1, 24, 99]  # All invalid hours
        mock_raw.explanation = "Invalid hours"

        sanitized = validate_and_sanitize_directives([mock_raw], battery_capacity=200.0)
        assert len(sanitized) == 1
        assert sanitized[0].applies is False
        assert sanitized[0].directive_type == DirectiveType.NO_OP
        assert sanitized[0].structured_adjustment is None
        assert "no valid hours" in sanitized[0].explanation.lower()

    def test_safe_degradation_on_missing_adjustment(self):
        mock_raw = MagicMock()
        mock_raw.note_index = 0
        mock_raw.applies = True
        mock_raw.directive_type = DirectiveType.SOLAR_REDUCTION
        mock_raw.structured_adjustment = None
        mock_raw.explanation = "Missing adjustment"

        sanitized = validate_and_sanitize_directives([mock_raw], battery_capacity=200.0)
        assert len(sanitized) == 1
        assert sanitized[0].applies is False
        assert sanitized[0].directive_type == DirectiveType.NO_OP
        assert sanitized[0].structured_adjustment is None
        assert "structured_adjustment is none" in sanitized[0].explanation.lower()

    def test_safe_degradation_on_unexpected_exception(self):
        mock_raw = MagicMock()
        mock_raw.note_index = 0
        mock_raw.applies = True
        mock_raw.directive_type = DirectiveType.SOLAR_REDUCTION
        mock_raw.structured_adjustment = MagicMock()
        # Raise unexpected error when accessing hours
        mock_hours_property = MagicMock(side_effect=TypeError("Unexpected mock failure"))
        type(mock_raw.structured_adjustment).hours = mock_hours_property
        mock_raw.explanation = "Crash test"

        sanitized = validate_and_sanitize_directives([mock_raw], battery_capacity=200.0)
        assert len(sanitized) == 1
        assert sanitized[0].applies is False
        assert sanitized[0].directive_type == DirectiveType.NO_OP
        assert sanitized[0].structured_adjustment is None
