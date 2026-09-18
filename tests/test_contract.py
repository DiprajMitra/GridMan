"""Unit tests for app/schemas/contract.py."""

import pytest
from pydantic import ValidationError

from app.schemas.contract import (
    BatteryAction,
    BatteryConfig,
    BatteryInput,
    BatteryReserveAdjustment,
    DirectiveInterpretation,
    DirectiveType,
    HourInput,
    HourlyPlan,
    HourlyPlanEntry,
    HourlyProfile,
    MaxGridAdjustment,
    OptimizationRequest,
    OptimizationResponse,
    OptimizeEnergyRequest,
    OptimizeEnergyResponse,
    SolarAdjustment,
    WindowAdjustment,
)


def create_sample_hours(count: int = 24) -> list[HourInput]:
    """Helper to generate a list of HourInput entries."""
    return [
        HourInput(
            hour=i,
            demand_kwh=50.0 + i,
            solar_kwh=max(0.0, 100.0 - (i - 12) ** 2),
            tariff_bdt_per_kwh=6.0 if i < 17 else 10.0,
        )
        for i in range(count)
    ]


def create_sample_battery() -> BatteryInput:
    """Helper to generate a valid BatteryInput."""
    return BatteryInput(
        capacity_kwh=200.0,
        initial_energy_kwh=100.0,
        minimum_energy_kwh=40.0,
        max_charge_kwh_per_hour=50.0,
        max_discharge_kwh_per_hour=50.0,
    )


class TestHourInput:
    """Test validations on HourInput."""

    def test_valid_hour_input(self):
        h = HourInput(hour=0, demand_kwh=10.0, solar_kwh=5.0, tariff_bdt_per_kwh=6.5)
        assert h.hour == 0
        assert h.demand_kwh == 10.0
        assert h.solar_kwh == 5.0
        assert h.tariff_bdt_per_kwh == 6.5

    def test_hour_boundary(self):
        HourInput(hour=0, demand_kwh=0, solar_kwh=0, tariff_bdt_per_kwh=0)
        HourInput(hour=23, demand_kwh=0, solar_kwh=0, tariff_bdt_per_kwh=0)

        with pytest.raises(ValidationError):
            HourInput(hour=-1, demand_kwh=0, solar_kwh=0, tariff_bdt_per_kwh=0)

        with pytest.raises(ValidationError):
            HourInput(hour=24, demand_kwh=0, solar_kwh=0, tariff_bdt_per_kwh=0)

    def test_negative_values_rejected(self):
        with pytest.raises(ValidationError):
            HourInput(hour=5, demand_kwh=-1.0, solar_kwh=0, tariff_bdt_per_kwh=5)

        with pytest.raises(ValidationError):
            HourInput(hour=5, demand_kwh=10, solar_kwh=-0.1, tariff_bdt_per_kwh=5)

        with pytest.raises(ValidationError):
            HourInput(hour=5, demand_kwh=10, solar_kwh=0, tariff_bdt_per_kwh=-0.5)


class TestBatteryInput:
    """Test validations on BatteryInput."""

    def test_valid_battery(self):
        b = create_sample_battery()
        assert b.capacity_kwh == 200.0

    @pytest.mark.parametrize(
        "field_name",
        [
            "capacity_kwh",
            "initial_energy_kwh",
            "minimum_energy_kwh",
            "max_charge_kwh_per_hour",
            "max_discharge_kwh_per_hour",
        ],
    )
    def test_negative_battery_fields_rejected(self, field_name):
        kwargs = {
            "capacity_kwh": 200.0,
            "initial_energy_kwh": 100.0,
            "minimum_energy_kwh": 40.0,
            "max_charge_kwh_per_hour": 50.0,
            "max_discharge_kwh_per_hour": 50.0,
        }
        kwargs[field_name] = -5.0
        with pytest.raises(ValidationError):
            BatteryInput(**kwargs)


class TestOptimizeEnergyRequest:
    """Test validations on OptimizeEnergyRequest."""

    def test_valid_request(self):
        req = OptimizeEnergyRequest(
            scenario_id="GRID-101",
            operator_notes=["Solar output drops by 80%", "Do not charge"],
            hours=create_sample_hours(24),
            battery=create_sample_battery(),
        )
        assert req.scenario_id == "GRID-101"
        assert len(req.operator_notes) == 2
        assert len(req.hours) == 24

    def test_operator_notes_count(self):
        hours = create_sample_hours(24)
        battery = create_sample_battery()

        # 0 notes -> Error
        with pytest.raises(ValidationError):
            OptimizeEnergyRequest(
                scenario_id="S1",
                operator_notes=[],
                hours=hours,
                battery=battery,
            )

        # 4 notes -> Error
        with pytest.raises(ValidationError):
            OptimizeEnergyRequest(
                scenario_id="S1",
                operator_notes=["N1", "N2", "N3", "N4"],
                hours=hours,
                battery=battery,
            )

        # 1 note -> Valid
        req1 = OptimizeEnergyRequest(
            scenario_id="S1",
            operator_notes=["Single note"],
            hours=hours,
            battery=battery,
        )
        assert len(req1.operator_notes) == 1

        # 3 notes -> Valid
        req3 = OptimizeEnergyRequest(
            scenario_id="S1",
            operator_notes=["N1", "N2", "N3"],
            hours=hours,
            battery=battery,
        )
        assert len(req3.operator_notes) == 3

    def test_operator_notes_non_empty(self):
        hours = create_sample_hours(24)
        battery = create_sample_battery()

        with pytest.raises(ValidationError):
            OptimizeEnergyRequest(
                scenario_id="S1",
                operator_notes=[""],
                hours=hours,
                battery=battery,
            )

        with pytest.raises(ValidationError):
            OptimizeEnergyRequest(
                scenario_id="S1",
                operator_notes=["     "],
                hours=hours,
                battery=battery,
            )

    def test_hours_length_must_be_24(self):
        battery = create_sample_battery()

        # 23 items -> Error
        with pytest.raises(ValidationError):
            OptimizeEnergyRequest(
                scenario_id="S1",
                operator_notes=["N1"],
                hours=create_sample_hours(23),
                battery=battery,
            )

        # 25 items -> Error
        with pytest.raises(ValidationError):
            OptimizeEnergyRequest(
                scenario_id="S1",
                operator_notes=["N1"],
                hours=create_sample_hours(25),
                battery=battery,
            )


class TestDirectiveInterpretation:
    """Test DirectiveInterpretation validation rules."""

    def test_applies_false_valid(self):
        d = DirectiveInterpretation(
            note_index=0,
            applies=False,
            directive_type=DirectiveType.NO_OP,
            structured_adjustment=None,
            explanation="Irrelevant gardening note.",
        )
        assert not d.applies
        assert d.directive_type == DirectiveType.NO_OP
        assert d.structured_adjustment is None

    def test_applies_false_invalid_directive_type(self):
        with pytest.raises(ValidationError):
            DirectiveInterpretation(
                note_index=0,
                applies=False,
                directive_type=DirectiveType.SOLAR_REDUCTION,
                structured_adjustment=None,
                explanation="Should fail because applies is False but directive_type is not no_op",
            )

    def test_applies_false_with_structured_adjustment_rejected(self):
        with pytest.raises(ValidationError):
            DirectiveInterpretation(
                note_index=0,
                applies=False,
                directive_type=DirectiveType.NO_OP,
                structured_adjustment=SolarAdjustment(hours=[12], factor=0.5),
                explanation="Should fail because structured_adjustment must be None",
            )

    def test_applies_true_invalid_noop(self):
        with pytest.raises(ValidationError):
            DirectiveInterpretation(
                note_index=0,
                applies=True,
                directive_type=DirectiveType.NO_OP,
                structured_adjustment=None,
                explanation="Should fail because applies is True but directive_type is no_op",
            )

    def test_applies_true_solar_reduction(self):
        d = DirectiveInterpretation(
            note_index=0,
            applies=True,
            directive_type=DirectiveType.SOLAR_REDUCTION,
            structured_adjustment=SolarAdjustment(hours=[13, 14, 15], factor=0.2),
            explanation="Solar output reduced by 80%.",
        )
        assert d.applies
        assert isinstance(d.structured_adjustment, SolarAdjustment)
        assert d.structured_adjustment.factor == 0.2

    def test_applies_true_battery_reserve(self):
        d = DirectiveInterpretation(
            note_index=1,
            applies=True,
            directive_type=DirectiveType.MINIMUM_BATTERY_RESERVE,
            structured_adjustment=BatteryReserveAdjustment(
                hours=[18, 19, 20, 21, 22, 23], minimum_energy_kwh=80.0
            ),
            explanation="Keep 80 kWh reserve.",
        )
        assert d.applies
        assert isinstance(d.structured_adjustment, BatteryReserveAdjustment)
        assert d.structured_adjustment.minimum_energy_kwh == 80.0

    def test_applies_true_windows(self):
        d_charge = DirectiveInterpretation(
            note_index=0,
            applies=True,
            directive_type=DirectiveType.NO_CHARGE_WINDOW,
            structured_adjustment=WindowAdjustment(hours=[14, 15]),
            explanation="No charge window.",
        )
        assert d_charge.directive_type == DirectiveType.NO_CHARGE_WINDOW

        d_discharge = DirectiveInterpretation(
            note_index=1,
            applies=True,
            directive_type=DirectiveType.NO_DISCHARGE_WINDOW,
            structured_adjustment=WindowAdjustment(hours=[10, 11, 12]),
            explanation="No discharge window.",
        )
        assert d_discharge.directive_type == DirectiveType.NO_DISCHARGE_WINDOW

    def test_applies_true_max_grid(self):
        d = DirectiveInterpretation(
            note_index=0,
            applies=True,
            directive_type=DirectiveType.MAX_GRID_WINDOW,
            structured_adjustment=MaxGridAdjustment(hours=[2, 3, 4], max_grid_kwh=0.0),
            explanation="Grid outage window.",
        )
        assert d.applies
        assert isinstance(d.structured_adjustment, MaxGridAdjustment)
        assert d.structured_adjustment.max_grid_kwh == 0.0

    def test_structured_adjustment_type_mismatch_rejected(self):
        with pytest.raises(ValidationError):
            DirectiveInterpretation(
                note_index=0,
                applies=True,
                directive_type=DirectiveType.SOLAR_REDUCTION,
                structured_adjustment=WindowAdjustment(hours=[12, 13]),
                explanation="Type mismatch",
            )


class TestResponseSchema:
    """Test OptimizeEnergyResponse validations and serialization."""

    def test_valid_response(self):
        plan = [
            HourlyPlanEntry(
                hour=i,
                grid_kwh=50.0,
                solar_used_kwh=20.0,
                battery_action=BatteryAction.IDLE,
                battery_kwh=0.0,
                battery_energy_after_kwh=100.0,
            )
            for i in range(24)
        ]
        resp = OptimizeEnergyResponse(
            scenario_id="GRID-101",
            directive_interpretation=[
                DirectiveInterpretation(
                    note_index=0,
                    applies=True,
                    directive_type=DirectiveType.SOLAR_REDUCTION,
                    structured_adjustment=SolarAdjustment(hours=[13], factor=0.2),
                    explanation="Reduced solar",
                )
            ],
            hourly_plan=plan,
            total_grid_kwh=1200.0,
            total_cost_bdt=8400.0,
            peak_grid_kwh=65.0,
            plan_summary="Optimal 24h dispatch plan.",
        )
        assert resp.scenario_id == "GRID-101"
        data = resp.model_dump(mode="json")
        assert data["total_cost_bdt"] == 8400.0
        assert len(data["hourly_plan"]) == 24


class TestAliases:
    """Ensure aliases point to canonical schemas."""

    def test_aliases(self):
        assert HourlyProfile is HourInput
        assert BatteryConfig is BatteryInput
        assert OptimizationRequest is OptimizeEnergyRequest
        assert HourlyPlan is HourlyPlanEntry
        assert OptimizationResponse is OptimizeEnergyResponse
