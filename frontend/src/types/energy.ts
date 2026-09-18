// ============ Input Types ============

export interface HourlyProfile {
  hour: number;
  demand_kwh: number;
  solar_kwh: number;
  tariff_bdt_per_kwh: number;
}

export interface BatteryConfig {
  capacity_kwh: number;
  initial_energy_kwh: number;
  minimum_energy_kwh: number;
  max_charge_kwh_per_hour: number;
  max_discharge_kwh_per_hour: number;
}

export interface OptimizationRequest {
  scenario_id: string;
  operator_notes: string[];
  hours: HourlyProfile[];
  battery: BatteryConfig;
}

// ============ Output Types ============

export type DirectiveType =
  | 'solar_reduction'
  | 'no_charge_window'
  | 'minimum_battery_reserve'
  | 'max_grid_window'
  | 'no_op';

export interface DirectiveInterpretation {
  note_index: number;
  applies: boolean;
  directive_type: DirectiveType;
  structured_adjustment: Record<string, unknown> | null;
  explanation: string;
}

export type BatteryAction = 'charge' | 'discharge' | 'idle';

export interface HourlyPlan {
  hour: number;
  grid_kwh: number;
  solar_used_kwh: number;
  battery_action: BatteryAction;
  battery_kwh: number;
  battery_energy_after_kwh: number;
}

export interface OptimizationResponse {
  scenario_id: string;
  directive_interpretation: DirectiveInterpretation[];
  hourly_plan: HourlyPlan[];
  total_grid_kwh: number;
  total_cost_bdt: number;
  peak_grid_kwh: number;
  plan_summary: string;
}

export interface HealthResponse {
  status: string;
}

// ============ UI State Types ============

export type AppTheme = 'light' | 'dark';

export interface ScenarioPreset {
  id: string;
  name: string;
  data: OptimizationRequest;
}
