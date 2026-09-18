"""Mathematical optimization engine for 24-hour campus energy dispatch.

Uses scipy.optimize.linprog with the HiGHS linear programming solver to determine
the cost-optimal dispatch schedule subject to physical and directive constraints.
"""

from __future__ import annotations

import logging
from typing import List, Optional, Tuple

import numpy as np
from scipy.optimize import linprog, OptimizeResult

from app.schemas.contract import (
    BatteryAction,
    BatteryReserveAdjustment,
    DirectiveInterpretation,
    DirectiveType,
    HourlyPlanEntry,
    MaxGridAdjustment,
    OptimizeEnergyRequest,
    OptimizeEnergyResponse,
    SolarAdjustment,
    WindowAdjustment,
)

logger = logging.getLogger("gridwise.optimizer.solver")

HOURS_HORIZON: int = 24
BALANCE_TOLERANCE: float = 0.01
ACTION_THRESHOLD: float = 1e-3


def _extract_bounds_and_profiles(
    request: OptimizeEnergyRequest,
    sanitized_directives: List[DirectiveInterpretation],
) -> Tuple[
    np.ndarray,  # effective_solar (24,)
    np.ndarray,  # max_grid_cap (24,)
    np.ndarray,  # max_charge_rate (24,)
    np.ndarray,  # max_discharge_rate (24,)
    np.ndarray,  # min_reserve_level (24,)
]:
    """Compute hourly operational boundaries modulated by sanitized directives."""
    n = HOURS_HORIZON
    battery = request.battery

    # Base operational limits
    effective_solar = np.array([h.solar_kwh for h in request.hours], dtype=np.float64)
    max_grid_cap = np.full(n, np.inf, dtype=np.float64)
    max_charge_rate = np.full(n, battery.max_charge_kwh_per_hour, dtype=np.float64)
    max_discharge_rate = np.full(n, battery.max_discharge_kwh_per_hour, dtype=np.float64)
    min_reserve_level = np.full(n, battery.minimum_energy_kwh, dtype=np.float64)

    # Accumulate active directive adjustments
    for directive in sanitized_directives:
        if not directive.applies or directive.structured_adjustment is None:
            continue

        adj = directive.structured_adjustment
        dtype = directive.directive_type

        if dtype == DirectiveType.SOLAR_REDUCTION and isinstance(adj, SolarAdjustment):
            for h in adj.hours:
                if 0 <= h < n:
                    # Apply remaining fraction to base solar
                    effective_solar[h] = min(effective_solar[h], request.hours[h].solar_kwh * adj.factor)

        elif dtype == DirectiveType.MINIMUM_BATTERY_RESERVE and isinstance(adj, BatteryReserveAdjustment):
            for h in adj.hours:
                if 0 <= h < n:
                    min_reserve_level[h] = max(min_reserve_level[h], adj.minimum_energy_kwh)

        elif dtype == DirectiveType.NO_CHARGE_WINDOW and isinstance(adj, WindowAdjustment):
            for h in adj.hours:
                if 0 <= h < n:
                    max_charge_rate[h] = 0.0

        elif dtype == DirectiveType.NO_DISCHARGE_WINDOW and isinstance(adj, WindowAdjustment):
            for h in adj.hours:
                if 0 <= h < n:
                    max_discharge_rate[h] = 0.0

        elif dtype == DirectiveType.MAX_GRID_WINDOW and isinstance(adj, MaxGridAdjustment):
            for h in adj.hours:
                if 0 <= h < n:
                    max_grid_cap[h] = min(max_grid_cap[h], adj.max_grid_kwh)

    return (
        effective_solar,
        max_grid_cap,
        max_charge_rate,
        max_discharge_rate,
        min_reserve_level,
    )


def _build_lp_matrices(
    request: OptimizeEnergyRequest,
    effective_solar: np.ndarray,
    max_grid_cap: np.ndarray,
    max_charge_rate: np.ndarray,
    max_discharge_rate: np.ndarray,
    min_reserve_level: np.ndarray,
    enforce_strict_neutrality: bool = True,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, List[Tuple[float, Optional[float]]]]:
    """Formulate the standard LP matrices (c, A_eq, b_eq, bounds).

    Decision Variables indexing (120 variables):
    - G[h]: Grid import kWh, indices [0 .. 23]
    - S[h]: Solar consumed kWh, indices [24 .. 47]
    - C[h]: Battery charge kWh, indices [48 .. 71]
    - D[h]: Battery discharge kWh, indices [72 .. 95]
    - E[h]: Battery state-of-charge after hour h kWh, indices [96 .. 119]
    """
    n = HOURS_HORIZON
    n_vars = 5 * n
    battery = request.battery

    idx_G = 0
    idx_S = n
    idx_C = 2 * n
    idx_D = 3 * n
    idx_E = 4 * n

    # Objective: Minimize cost of grid electricity purchased + micro-penalties on battery cycling
    c = np.zeros(n_vars, dtype=np.float64)
    for h in range(n):
        c[idx_G + h] = request.hours[h].tariff_bdt_per_kwh
        # Micro tie-breaker to prevent degenerate simultaneous charge and discharge
        c[idx_C + h] = 1e-6
        c[idx_D + h] = 1e-6

    A_eq_list: List[np.ndarray] = []
    b_eq_list: List[float] = []

    # 1. Energy Balance: G[h] + S[h] + D[h] - C[h] == demand[h]
    for h in range(n):
        row = np.zeros(n_vars, dtype=np.float64)
        row[idx_G + h] = 1.0
        row[idx_S + h] = 1.0
        row[idx_D + h] = 1.0
        row[idx_C + h] = -1.0
        A_eq_list.append(row)
        b_eq_list.append(float(request.hours[h].demand_kwh))

    # 2. Battery State Transition:
    # E[0] - C[0] + D[0] == initial_energy_kwh
    # E[h] - E[h-1] - C[h] + D[h] == 0  for h in 1..23
    for h in range(n):
        row = np.zeros(n_vars, dtype=np.float64)
        row[idx_E + h] = 1.0
        row[idx_C + h] = -1.0
        row[idx_D + h] = 1.0
        if h == 0:
            b_eq_list.append(float(battery.initial_energy_kwh))
        else:
            row[idx_E + (h - 1)] = -1.0
            b_eq_list.append(0.0)
        A_eq_list.append(row)

    # 3. Battery Neutrality: E[23] == initial_energy_kwh
    if enforce_strict_neutrality:
        row = np.zeros(n_vars, dtype=np.float64)
        row[idx_E + (n - 1)] = 1.0
        A_eq_list.append(row)
        b_eq_list.append(float(battery.initial_energy_kwh))

    A_eq = np.array(A_eq_list, dtype=np.float64)
    b_eq = np.array(b_eq_list, dtype=np.float64)

    # Variable bounds
    bounds: List[Tuple[float, Optional[float]]] = []

    # G bounds: [0, max_grid_cap[h]]
    for h in range(n):
        upper_g = None if np.isinf(max_grid_cap[h]) else float(max_grid_cap[h])
        bounds.append((0.0, upper_g))

    # S bounds: [0, effective_solar[h]]
    for h in range(n):
        bounds.append((0.0, float(effective_solar[h])))

    # C bounds: [0, max_charge_rate[h]]
    for h in range(n):
        bounds.append((0.0, float(max_charge_rate[h])))

    # D bounds: [0, max_discharge_rate[h]]
    for h in range(n):
        bounds.append((0.0, float(max_discharge_rate[h])))

    # E bounds: [min_reserve_level[h], capacity_kwh]
    for h in range(n):
        lower_e = float(min_reserve_level[h])
        upper_e = float(battery.capacity_kwh)
        bounds.append((lower_e, upper_e))

    return c, A_eq, b_eq, bounds


def _reconstruct_and_audit_plan(
    x: np.ndarray,
    request: OptimizeEnergyRequest,
) -> Tuple[List[HourlyPlanEntry], float, float, float]:
    """Reconstruct hourly entries from optimal decision vector and perform replay audit."""
    n = HOURS_HORIZON
    idx_G = 0
    idx_S = n
    idx_C = 2 * n
    idx_D = 3 * n
    idx_E = 4 * n

    hourly_plan: List[HourlyPlanEntry] = []

    for h in range(n):
        g = float(x[idx_G + h])
        s = float(x[idx_S + h])
        c = float(x[idx_C + h])
        d = float(x[idx_D + h])
        e = float(x[idx_E + h])

        # Numerical cleanup
        if g < 1e-6:
            g = 0.0
        if s < 1e-6:
            s = 0.0

        # Action classification
        if c > ACTION_THRESHOLD:
            action = BatteryAction.CHARGE
            battery_kwh = c
        elif d > ACTION_THRESHOLD:
            action = BatteryAction.DISCHARGE
            battery_kwh = d
        else:
            action = BatteryAction.IDLE
            battery_kwh = 0.0

        # Energy balance replay check
        net_battery = battery_kwh if action == BatteryAction.DISCHARGE else (-battery_kwh if action == BatteryAction.CHARGE else 0.0)
        supply = g + s + net_battery
        demand = request.hours[h].demand_kwh
        discrepancy = abs(supply - demand)
        if discrepancy > BALANCE_TOLERANCE:
            logger.warning(
                "Hour %d energy balance discrepancy of %.4f kWh exceeds tolerance (supply=%.3f, demand=%.3f)",
                h, discrepancy, supply, demand,
            )

        entry = HourlyPlanEntry(
            hour=h,
            grid_kwh=round(g, 4),
            solar_used_kwh=round(s, 4),
            battery_action=action,
            battery_kwh=round(battery_kwh, 4),
            battery_energy_after_kwh=round(e, 4),
        )
        hourly_plan.append(entry)

    # Neutrality replay check
    neutrality_discrepancy = abs(hourly_plan[-1].battery_energy_after_kwh - request.battery.initial_energy_kwh)
    if neutrality_discrepancy > BALANCE_TOLERANCE:
        logger.warning(
            "End-of-day neutrality discrepancy of %.4f kWh (E[23]=%.3f, initial=%.3f)",
            neutrality_discrepancy,
            hourly_plan[-1].battery_energy_after_kwh,
            request.battery.initial_energy_kwh,
        )

    # Recalculate totals directly from the generated plan
    total_grid = round(float(sum(p.grid_kwh for p in hourly_plan)), 4)
    total_cost = round(float(sum(p.grid_kwh * request.hours[p.hour].tariff_bdt_per_kwh for p in hourly_plan)), 4)
    peak_grid = round(float(max(p.grid_kwh for p in hourly_plan)), 4)

    return hourly_plan, total_grid, total_cost, peak_grid


def solve_schedule(
    request: OptimizeEnergyRequest,
    sanitized_directives: List[DirectiveInterpretation],
) -> OptimizeEnergyResponse:
    """Solve the 24-hour campus energy dispatch linear program with HiGHS.

    Parameters
    ----------
    request : OptimizeEnergyRequest
        Complete optimization request with hourly demand, solar, tariffs, and battery bounds.
    sanitized_directives : list[DirectiveInterpretation]
        Cleaned and bounded directives passed through the guardrail layer.

    Returns
    -------
    OptimizeEnergyResponse
        Optimal dispatch plan, summary statistics, and replay-verified metrics.
    """
    effective_solar, max_grid_cap, max_charge_rate, max_discharge_rate, min_reserve_level = (
        _extract_bounds_and_profiles(request, sanitized_directives)
    )

    # Attempt 1: Strict neutrality formulation
    c, A_eq, b_eq, bounds = _build_lp_matrices(
        request,
        effective_solar,
        max_grid_cap,
        max_charge_rate,
        max_discharge_rate,
        min_reserve_level,
        enforce_strict_neutrality=True,
    )

    res: OptimizeResult = linprog(
        c=c,
        A_eq=A_eq,
        b_eq=b_eq,
        bounds=bounds,
        method="highs",
    )

    used_neutrality_relaxation = False

    # Attempt 2: Relax end-of-day neutrality if over-constrained
    if not res.success:
        logger.warning(
            "Strict neutrality LP infeasible (%s). Retrying with relaxed neutrality...",
            res.message,
        )
        c, A_eq, b_eq, bounds = _build_lp_matrices(
            request,
            effective_solar,
            max_grid_cap,
            max_charge_rate,
            max_discharge_rate,
            min_reserve_level,
            enforce_strict_neutrality=False,
        )
        res = linprog(
            c=c,
            A_eq=A_eq,
            b_eq=b_eq,
            bounds=bounds,
            method="highs",
        )
        if res.success:
            used_neutrality_relaxation = True

    if not res.success:
        # Fallback: All-grid heuristic if constraints completely conflict
        logger.error("Linear program could not find feasible solution: %s", res.message)
        raise RuntimeError(f"Optimizer failed to find feasible dispatch schedule: {res.message}")

    hourly_plan, total_grid, total_cost, peak_grid = _reconstruct_and_audit_plan(res.x, request)

    # Build informative executive plan summary
    neutrality_note = (
        "Strict end-of-day neutrality preserved."
        if not used_neutrality_relaxation
        else "End-of-day neutrality relaxed due to severe grid import or reserve constraints."
    )
    plan_summary = (
        f"Optimization completed successfully for scenario '{request.scenario_id}'. "
        f"Total grid import: {total_grid:.2f} kWh, Total cost: {total_cost:.2f} BDT, "
        f"Peak grid demand: {peak_grid:.2f} kWh across 24 hours. {neutrality_note}"
    )

    return OptimizeEnergyResponse(
        scenario_id=request.scenario_id,
        directive_interpretation=sanitized_directives,
        hourly_plan=hourly_plan,
        total_grid_kwh=total_grid,
        total_cost_bdt=total_cost,
        peak_grid_kwh=peak_grid,
        plan_summary=plan_summary,
    )


__all__ = [
    "solve_schedule",
]
