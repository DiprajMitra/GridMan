import type { ReactNode } from 'react';
import type { BatteryConfig } from '../types/energy';
import { Battery, Zap } from 'lucide-react';

interface BatterySettingsCardProps {
  config: BatteryConfig;
  onChange: (config: BatteryConfig) => void;
}

function NumericInput({
  label,
  value,
  onChange,
  unit,
  min = 0,
  max = 1000,
  leadingIcon,
}: {
  label: string;
  value: number;
  onChange: (v: number) => void;
  unit: string;
  min?: number;
  max?: number;
  leadingIcon?: ReactNode;
}) {
  return (
    <div className="min-w-0">
      <label className="block text-xs font-medium text-surface-500 dark:text-surface-400 mb-1 truncate">
        {label}
      </label>
      <div className="relative min-w-0">
        {leadingIcon && (
          <span className="absolute left-2 top-1/2 -translate-y-1/2 text-surface-400 pointer-events-none">
            {leadingIcon}
          </span>
        )}
        <input
          type="number"
          value={value}
          onChange={(e) => onChange(Math.max(min, Math.min(max, Number(e.target.value))))}
          min={min}
          max={max}
          className={`input-field text-right font-mono min-w-0 w-full ${leadingIcon ? 'pl-7' : ''} pr-10`}
        />
        <span className="absolute right-3 top-1/2 -translate-y-1/2 text-xs text-surface-400 pointer-events-none">
          {unit}
        </span>
      </div>
    </div>
  );
}

export default function BatterySettingsCard({
  config,
  onChange,
}: BatterySettingsCardProps) {
  const update = (key: keyof BatteryConfig, value: number) => {
    onChange({ ...config, [key]: value });
  };

  const chargePercent = Math.round(
    (config.initial_energy_kwh / config.capacity_kwh) * 100
  );

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <label className="flex items-center gap-2 text-sm font-semibold text-surface-700 dark:text-surface-300">
          <Battery className="w-4 h-4 text-chart-battery" />
          Battery Configuration
        </label>
        <span className="badge bg-cyan-100 text-cyan-800 dark:bg-cyan-900/40 dark:text-cyan-400">
          {chargePercent}% SoC
        </span>
      </div>

      {/* Visual SoC bar */}
      <div className="h-2 rounded-full bg-surface-200 dark:bg-surface-700 overflow-hidden">
        <div
          className="h-full rounded-full transition-all duration-300"
          style={{
            width: `${chargePercent}%`,
            background: chargePercent > 60
              ? 'var(--color-chart-charge)'
              : chargePercent > 30
              ? 'var(--color-chart-discharge)'
              : 'var(--color-danger)',
          }}
        />
      </div>

      <div className="grid grid-cols-2 gap-3">
        <NumericInput
          label="Capacity"
          value={config.capacity_kwh}
          onChange={(v) => update('capacity_kwh', v)}
          unit="kWh"
        />
        <NumericInput
          label="Initial Energy"
          value={config.initial_energy_kwh}
          onChange={(v) => update('initial_energy_kwh', v)}
          unit="kWh"
        />
        <NumericInput
          label="Minimum Reserve"
          value={config.minimum_energy_kwh}
          onChange={(v) => update('minimum_energy_kwh', v)}
          unit="kWh"
        />
        <div className="col-span-2 grid grid-cols-2 gap-3">
          <NumericInput
            label="Max Charge/hr"
            value={config.max_charge_kwh_per_hour}
            onChange={(v) => update('max_charge_kwh_per_hour', v)}
            unit="kWh"
            leadingIcon={<Zap className="w-3.5 h-3.5 text-chart-charge" />}
          />
          <NumericInput
            label="Max Discharge/hr"
            value={config.max_discharge_kwh_per_hour}
            onChange={(v) => update('max_discharge_kwh_per_hour', v)}
            unit="kWh"
            leadingIcon={<Zap className="w-3.5 h-3.5 text-chart-discharge" />}
          />
        </div>
      </div>
    </div>
  );
}
