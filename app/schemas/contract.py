"""Pydantic v2 data contracts and schemas for the GridWise Energy Optimization API.

Conforms strictly to the BUP CSE Fest 2026 specifications.
Defines input payloads, directive interpretations, solver schedules, and response envelopes.
"""

from __future__ import annotations

from enum import Enum
from typing import Annotated, Any, Dict, List, Optional, Union
from typing_extensions import Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)


# ============================================================================
# Enums
# ============================================================================


class DirectiveType(str, Enum):
    """Supported directive types for operator note interpretation."""

    SOLAR_REDUCTION = "solar_reduction"
    MINIMUM_BATTERY_RESERVE = "minimum_battery_reserve"
    NO_CHARGE_WINDOW = "no_charge_window"
    NO_DISCHARGE_WINDOW = "no_discharge_window"
    MAX_GRID_WINDOW = "max_grid_window"
    NO_OP = "no_op"


class BatteryAction(str, Enum):
    """Discrete hourly battery operation actions."""

    CHARGE = "charge"
    DISCHARGE = "discharge"
    IDLE = "idle"


# ============================================================================
# Input Schemas
# ============================================================================


class HourInput(BaseModel):
    """Hourly input parameters representing demand, solar, and grid tariff."""

    model_config = ConfigDict(extra="forbid")

    hour: int = Field(
        ...,
        ge=0,
        le=23,
        description="Hour of the day as an integer between 0 and 23 inclusive.",
        examples=[0],
    )
    demand_kwh: float = Field(
        ...,
        ge=0.0,
        description="Campus energy demand in kilowatt-hours (must be >= 0).",
        examples=[60.0],
    )
    solar_kwh: float = Field(
        ...,
        ge=0.0,
        description="Expected solar generation in kilowatt-hours (must be >= 0).",
        examples=[20.0],
    )
    tariff_bdt_per_kwh: float = Field(
        ...,
        ge=0.0,
        description="Grid electricity tariff in BDT per kWh (must be >= 0).",
        examples=[6.0],
    )


class BatteryInput(BaseModel):
    """Battery storage system configuration and physical operating bounds."""

    model_config = ConfigDict(extra="forbid")

    capacity_kwh: float = Field(
        ...,
        ge=0.0,
        description="Total battery storage capacity in kWh (>= 0).",
        examples=[200.0],
    )
    initial_energy_kwh: float = Field(
        ...,
        ge=0.0,
        description="Initial battery state-of-charge energy at hour 0 in kWh (>= 0).",
        examples=[100.0],
    )
    minimum_energy_kwh: float = Field(
        ...,
        ge=0.0,
        description="Minimum allowable battery reserve energy in kWh (>= 0).",
        examples=[40.0],
    )
    max_charge_kwh_per_hour: float = Field(
        ...,
        ge=0.0,
        description="Maximum charging rate in kWh per hour (>= 0).",
        examples=[50.0],
    )
    max_discharge_kwh_per_hour: float = Field(
        ...,
        ge=0.0,
        description="Maximum discharging rate in kWh per hour (>= 0).",
        examples=[50.0],
    )


# Type alias for non-empty string in operator notes
NonEmptyString = Annotated[str, Field(min_length=1)]


class OptimizeEnergyRequest(BaseModel):
    """Root request payload for 24-hour campus energy optimization."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    scenario_id: str = Field(
        ...,
        min_length=1,
        description="Unique identifier for the optimization scenario.",
        examples=["GRID-101"],
    )
    operator_notes: List[NonEmptyString] = Field(
        ...,
        min_length=1,
        max_length=3,
        description="List of 1 to 3 non-empty operator directive notes.",
        examples=[
            "Solar output will drop to about 20% from 1 PM to 3 PM due to panel cleaning.",
            "Do not charge the battery between 2 PM and 4 PM.",
        ],
    )
    hours: List[HourInput] = Field(
        ...,
        min_length=24,
        max_length=24,
        description="Hourly input profiles for exactly 24 hours (hours 0 to 23).",
    )
    battery: BatteryInput = Field(
        ...,
        description="Battery specifications and operational parameters.",
    )

    @field_validator("operator_notes")
    @classmethod
    def validate_operator_notes(cls, notes: List[str]) -> List[str]:
        """Validate operator notes list bounds and content non-emptiness."""
        if not (1 <= len(notes) <= 3):
            raise ValueError("operator_notes must contain between 1 and 3 items.")
        for idx, note in enumerate(notes):
            if not isinstance(note, str) or not note.strip():
                raise ValueError(
                    f"operator_notes[{idx}] must be a non-empty string."
                )
        return notes

    @field_validator("hours")
    @classmethod
    def validate_hours_length(cls, hours: List[HourInput]) -> List[HourInput]:
        """Validate that exactly 24 hourly entries are provided."""
        if len(hours) != 24:
            raise ValueError(f"hours must contain exactly 24 items, got {len(hours)}.")
        return hours


# ============================================================================
# Directive Interpretation Schemas
# ============================================================================


class BaseAdjustment(BaseModel):
    """Base model for structured directive adjustments with hour validation."""

    model_config = ConfigDict(extra="forbid")

    hours: List[int] = Field(
        ...,
        description="Target hours of the day (each in 0..23) affected by the directive.",
        examples=[[13, 14, 15]],
    )

    @field_validator("hours")
    @classmethod
    def validate_hours_range(cls, hours: List[int]) -> List[int]:
        """Ensure all specified hours are valid integers between 0 and 23."""
        for h in hours:
            if not (0 <= h <= 23):
                raise ValueError(f"Hour {h} must be an integer between 0 and 23.")
        # Return unique hours preserving order
        return list(dict.fromkeys(hours))


class SolarAdjustment(BaseAdjustment):
    """Structured adjustment for solar reduction directives."""

    factor: float = Field(
        ...,
        ge=0.0,
        description="Multiplicative factor applied to solar generation (e.g. 0.2 for 20%).",
        examples=[0.2],
    )


class BatteryReserveAdjustment(BaseAdjustment):
    """Structured adjustment for emergency or elevated battery reserve requirements."""

    minimum_energy_kwh: float = Field(
        ...,
        ge=0.0,
        description="Required minimum reserve energy level in kWh during specified hours.",
        examples=[80.0],
    )


class WindowAdjustment(BaseAdjustment):
    """Structured adjustment defining restricted operation windows (no-charge or no-discharge)."""

    pass


class MaxGridAdjustment(BaseAdjustment):
    """Structured adjustment capping maximum allowable grid import during specified hours."""

    max_grid_kwh: float = Field(
        ...,
        ge=0.0,
        description="Maximum allowed grid import in kWh during specified hours.",
        examples=[0.0],
    )


# Union of all structured adjustments or None
StructuredAdjustment = Union[
    SolarAdjustment,
    BatteryReserveAdjustment,
    WindowAdjustment,
    MaxGridAdjustment,
]


class DirectiveInterpretation(BaseModel):
    """Interpretation result for an individual operator note directive."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    note_index: int = Field(
        ...,
        ge=0,
        description="Zero-based index of the operator note being interpreted.",
        examples=[0],
    )
    applies: bool = Field(
        ...,
        description="Indicates if the directive applies as an active operational constraint.",
        examples=[True],
    )
    directive_type: DirectiveType = Field(
        ...,
        description="Identified directive category.",
        examples=[DirectiveType.SOLAR_REDUCTION],
    )
    structured_adjustment: Optional[StructuredAdjustment] = Field(
        default=None,
        description="Structured constraint payload when applicable, or None.",
        examples=[{"hours": [13, 14, 15], "factor": 0.2}],
    )
    explanation: str = Field(
        ...,
        description="Clear rationale explaining the extraction or why the note was ignored.",
        examples=["Solar output reduced to 20% between 1 PM and 3 PM."],
    )

    @model_validator(mode="after")
    def validate_directive_consistency(self) -> Self:
        """Enforce strict consistency between applies, directive_type, and structured_adjustment.

        Validation rules:
        - When applies is False: directive_type must be 'no_op' and structured_adjustment must be None.
        - When applies is True: directive_type must NOT be 'no_op'.
        - When applies is True and structured_adjustment is provided: the adjustment model type
          must correspond to the directive_type.
        """
        if not self.applies:
            if self.directive_type != DirectiveType.NO_OP:
                raise ValueError(
                    f'When "applies" is False, "directive_type" must be "no_op", got "{self.directive_type.value}".'
                )
            if self.structured_adjustment is not None:
                raise ValueError(
                    'When "applies" is False, "structured_adjustment" must be None.'
                )
        else:
            if self.directive_type == DirectiveType.NO_OP:
                raise ValueError(
                    'When "applies" is True, "directive_type" must not be "no_op".'
                )
            if self.structured_adjustment is not None:
                expected_type_map = {
                    DirectiveType.SOLAR_REDUCTION: SolarAdjustment,
                    DirectiveType.MINIMUM_BATTERY_RESERVE: BatteryReserveAdjustment,
                    DirectiveType.NO_CHARGE_WINDOW: WindowAdjustment,
                    DirectiveType.NO_DISCHARGE_WINDOW: WindowAdjustment,
                    DirectiveType.MAX_GRID_WINDOW: MaxGridAdjustment,
                }
                expected_cls = expected_type_map.get(self.directive_type)
                if expected_cls and not isinstance(self.structured_adjustment, expected_cls):
                    raise ValueError(
                        f'For directive_type "{self.directive_type.value}", structured_adjustment '
                        f'must be of type {expected_cls.__name__}, got {type(self.structured_adjustment).__name__}.'
                    )
        return self


# ============================================================================
# Output Schemas
# ============================================================================


class HourlyPlanEntry(BaseModel):
    """Energy dispatch plan entry for a single hour."""

    model_config = ConfigDict(extra="forbid")

    hour: int = Field(
        ...,
        ge=0,
        le=23,
        description="Hour of the day as an integer between 0 and 23 inclusive.",
        examples=[0],
    )
    grid_kwh: float = Field(
        ...,
        ge=0.0,
        description="Grid electricity import during this hour in kWh (>= 0).",
        examples=[60.0],
    )
    solar_used_kwh: float = Field(
        ...,
        ge=0.0,
        description="Solar energy consumed or stored during this hour in kWh (>= 0).",
        examples=[0.0],
    )
    battery_action: BatteryAction = Field(
        ...,
        description="Battery action: 'charge', 'discharge', or 'idle'.",
        examples=[BatteryAction.IDLE],
    )
    battery_kwh: float = Field(
        ...,
        ge=0.0,
        description="Magnitude of energy charged or discharged by the battery in kWh (>= 0).",
        examples=[0.0],
    )
    battery_energy_after_kwh: float = Field(
        ...,
        ge=0.0,
        description="Battery state-of-charge remaining at the end of this hour in kWh (>= 0).",
        examples=[100.0],
    )


class OptimizeEnergyResponse(BaseModel):
    """Complete response payload for the 24-hour energy dispatch optimization."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    scenario_id: str = Field(
        ...,
        min_length=1,
        description="Scenario identifier matching the request.",
        examples=["GRID-101"],
    )
    directive_interpretation: List[DirectiveInterpretation] = Field(
        ...,
        description="List of interpreted operator directive notes with active or ignored status.",
    )
    hourly_plan: List[HourlyPlanEntry] = Field(
        ...,
        description="24-hour energy dispatch schedule and battery profile.",
    )
    total_grid_kwh: float = Field(
        ...,
        ge=0.0,
        description="Total cumulative energy imported from the grid across the 24-hour horizon in kWh.",
        examples=[2540.0],
    )
    total_cost_bdt: float = Field(
        ...,
        ge=0.0,
        description="Total financial cost in BDT across the 24-hour horizon.",
        examples=[18450.0],
    )
    peak_grid_kwh: float = Field(
        ...,
        ge=0.0,
        description="Peak grid import in any single hour in kWh.",
        examples=[185.0],
    )
    plan_summary: str = Field(
        ...,
        description="Human-readable executive summary of the dispatch schedule and cost drivers.",
        examples=["Optimal schedule minimizes grid import during peak tariff windows."],
    )


class HealthResponse(BaseModel):
    """API service health check response."""

    status: str = Field(default="ok", description="Service health status indicator.")


# ============================================================================
# Aliases for broad compatibility
# ============================================================================

HourlyProfile = HourInput
BatteryConfig = BatteryInput
OptimizationRequest = OptimizeEnergyRequest
HourlyPlan = HourlyPlanEntry
OptimizationResponse = OptimizeEnergyResponse

__all__ = [
    # Enums
    "DirectiveType",
    "BatteryAction",
    # Input Schemas
    "HourInput",
    "BatteryInput",
    "OptimizeEnergyRequest",
    # Directive Interpretation Schemas
    "BaseAdjustment",
    "SolarAdjustment",
    "BatteryReserveAdjustment",
    "WindowAdjustment",
    "MaxGridAdjustment",
    "StructuredAdjustment",
    "DirectiveInterpretation",
    # Output Schemas
    "HourlyPlanEntry",
    "OptimizeEnergyResponse",
    "HealthResponse",
    # Compatibility Aliases
    "HourlyProfile",
    "BatteryConfig",
    "OptimizationRequest",
    "HourlyPlan",
    "OptimizationResponse",
]
