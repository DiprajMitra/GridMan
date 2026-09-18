"""Unit tests for app/optimizer/solver.py."""

import pytest

from app.optimizer.solver import solve_schedule
from app.schemas.contract import (
    BatteryAction,
    BatteryInput,
    BatteryReserveAdjustment,
    DirectiveInterpretation,
    DirectiveType,
    HourInput,
    MaxGridAdjustment,
    OptimizeEnergyRequest,
    SolarAdjustment,
    WindowAdjustment,
)


def create_baseline_scenario() -> OptimizeEnergyRequest:
    """Create standard 24-hour test request."""
    # Peak tariffs at hours 12-16 (11-15 BDT), cheap tariffs off-peak (5-6 BDT)
    hours = [
        HourInput(
            hour=h,
            demand_kwh=60.0 + (30.0 if 8 <= h <= 18 else 0.0),
            solar_kwh=max(0.0, 120.0 - abs(h - 12) * 20.0),
            tariff_bdt_per_kwh=12.0 if 12 <= h <= 16 else 6.0,
        )
        for h in range(24)
    ]
    battery = BatteryInput(
        capacity_kwh=200.0,
        initial_energy_kwh=100.0,
        minimum_energy_kwh=40.0,
        max_charge_kwh_per_hour=50.0,
        max_discharge_kwh_per_hour=50.0,
    )
    return OptimizeEnergyRequest(
        scenario_id="TEST-SOLVER-01",
        operator_notes=["Baseline test note"],
        hours=hours,
        battery=battery,
    )


class TestSolver:
    """Test solver dispatch optimization, physical constraints, and directive compliance."""

    def test_baseline_energy_balance_and_neutrality(self):
        req = create_baseline_scenario()
        resp = solve_schedule(req, [])

        assert resp.scenario_id == req.scenario_id
        assert len(resp.hourly_plan) == 24

        # 1. Energy balance replay check
        for entry in resp.hourly_plan:
            h = entry.hour
            demand = req.hours[h].demand_kwh
            grid = entry.grid_kwh
            solar = entry.solar_used_kwh
            b_act = entry.battery_action
            b_kwh = entry.battery_kwh

            if b_act == BatteryAction.CHARGE:
                net_batt = -b_kwh
            elif b_act == BatteryAction.DISCHARGE:
                net_batt = b_kwh
            else:
                net_batt = 0.0

            assert abs((grid + solar + net_batt) - demand) < 0.01

        # 2. Battery neutrality check (E[23] == E_init)
        final_energy = resp.hourly_plan[-1].battery_energy_after_kwh
        assert abs(final_energy - req.battery.initial_energy_kwh) < 0.01

        # 3. Battery bounds check
        for entry in resp.hourly_plan:
            assert entry.battery_energy_after_kwh >= req.battery.minimum_energy_kwh - 0.01
            assert entry.battery_energy_after_kwh <= req.battery.capacity_kwh + 0.01

        # 4. Direct recalculations match
        calc_grid = round(sum(p.grid_kwh for p in resp.hourly_plan), 4)
        calc_cost = round(sum(p.grid_kwh * req.hours[p.hour].tariff_bdt_per_kwh for p in resp.hourly_plan), 4)
        calc_peak = round(max(p.grid_kwh for p in resp.hourly_plan), 4)

        assert abs(resp.total_grid_kwh - calc_grid) < 1e-4
        assert abs(resp.total_cost_bdt - calc_cost) < 1e-4
        assert abs(resp.peak_grid_kwh - calc_peak) < 1e-4

    def test_solar_reduction_directive(self):
        req = create_baseline_scenario()
        # Reduce solar to 10% during peak sun hours 12 and 13
        reduced_hours = [12, 13]
        directives = [
            DirectiveInterpretation(
                note_index=0,
                applies=True,
                directive_type=DirectiveType.SOLAR_REDUCTION,
                structured_adjustment=SolarAdjustment(hours=reduced_hours, factor=0.1),
                explanation="Severe cloud cover",
            )
        ]
        resp = solve_schedule(req, directives)

        for entry in resp.hourly_plan:
            if entry.hour in reduced_hours:
                max_allowed_solar = req.hours[entry.hour].solar_kwh * 0.1
                assert entry.solar_used_kwh <= max_allowed_solar + 0.01

    def test_no_charge_window_directive(self):
        req = create_baseline_scenario()
        no_charge_hours = [10, 11, 12]
        directives = [
            DirectiveInterpretation(
                note_index=0,
                applies=True,
                directive_type=DirectiveType.NO_CHARGE_WINDOW,
                structured_adjustment=WindowAdjustment(hours=no_charge_hours),
                explanation="No charge window",
            )
        ]
        resp = solve_schedule(req, directives)

        for entry in resp.hourly_plan:
            if entry.hour in no_charge_hours:
                assert entry.battery_action != BatteryAction.CHARGE

    def test_no_discharge_window_directive(self):
        req = create_baseline_scenario()
        no_discharge_hours = [13, 14, 15]
        directives = [
            DirectiveInterpretation(
                note_index=0,
                applies=True,
                directive_type=DirectiveType.NO_DISCHARGE_WINDOW,
                structured_adjustment=WindowAdjustment(hours=no_discharge_hours),
                explanation="Preserve battery for later",
            )
        ]
        resp = solve_schedule(req, directives)

        for entry in resp.hourly_plan:
            if entry.hour in no_discharge_hours:
                assert entry.battery_action != BatteryAction.DISCHARGE

    def test_minimum_battery_reserve_directive(self):
        req = create_baseline_scenario()
        reserve_hours = [18, 19, 20, 21]
        mandatory_reserve = 120.0  # Higher than baseline minimum (40.0)
        directives = [
            DirectiveInterpretation(
                note_index=0,
                applies=True,
                directive_type=DirectiveType.MINIMUM_BATTERY_RESERVE,
                structured_adjustment=BatteryReserveAdjustment(
                    hours=reserve_hours, minimum_energy_kwh=mandatory_reserve
                ),
                explanation="Emergency reserve",
            )
        ]
        resp = solve_schedule(req, directives)

        for entry in resp.hourly_plan:
            if entry.hour in reserve_hours:
                assert entry.battery_energy_after_kwh >= mandatory_reserve - 0.01

    def test_max_grid_window_directive(self):
        req = create_baseline_scenario()
        grid_cap_hours = [13, 14]
        max_cap = 20.0
        directives = [
            DirectiveInterpretation(
                note_index=0,
                applies=True,
                directive_type=DirectiveType.MAX_GRID_WINDOW,
                structured_adjustment=MaxGridAdjustment(
                    hours=grid_cap_hours, max_grid_kwh=max_cap
                ),
                explanation="Grid capacity limitation",
            )
        ]
        resp = solve_schedule(req, directives)

        for entry in resp.hourly_plan:
            if entry.hour in grid_cap_hours:
                assert entry.grid_kwh <= max_cap + 0.01
