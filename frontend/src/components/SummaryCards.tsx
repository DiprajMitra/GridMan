import { Zap, TrendingUp, DollarSign, BatteryFull, ArrowRight } from 'lucide-react';
import type { OptimizationResponse } from '../types/energy';

interface SummaryCardsProps {
  result: OptimizationResponse | null;
  initialEnergy: number;
  isLoading: boolean;
}

function KpiSkeleton() {
  return (
    <div className="kpi-card">
      <div className="skeleton h-3 w-20 mb-2" />
      <div className="skeleton h-7 w-24" />
      <div className="skeleton h-2 w-16 mt-1" />
    </div>
  );
}

export default function SummaryCards({
  result,
  initialEnergy,
  isLoading,
}: SummaryCardsProps) {
  if (isLoading) {
    return (
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <KpiSkeleton />
        <KpiSkeleton />
        <KpiSkeleton />
        <KpiSkeleton />
      </div>
    );
  }

  if (!result) {
    return (
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        {[
          { icon: Zap, label: 'Total Grid Import', color: 'text-chart-grid' },
          { icon: TrendingUp, label: 'Peak Demand', color: 'text-chart-demand' },
          { icon: DollarSign, label: 'Total Cost', color: 'text-chart-solar' },
          { icon: BatteryFull, label: 'Battery Neutrality', color: 'text-chart-battery' },
        ].map(({ icon: Icon, label, color }) => (
          <div key={label} className="kpi-card opacity-60">
            <div className="flex items-center gap-2">
              <Icon className={`w-4 h-4 ${color}`} />
              <span className="text-xs font-medium text-surface-400">{label}</span>
            </div>
            <span className="text-xl font-bold text-surface-300 dark:text-surface-600 font-mono">
              —
            </span>
          </div>
        ))}
      </div>
    );
  }

  const finalEnergy =
    result.hourly_plan[result.hourly_plan.length - 1]?.battery_energy_after_kwh ?? 0;
  const isNeutral = Math.abs(finalEnergy - initialEnergy) < 1;

  const kpis = [
    {
      icon: Zap,
      label: 'Total Grid Import',
      value: `${result.total_grid_kwh.toLocaleString()} kWh`,
      color: 'text-chart-grid',
      sub: `Across 24 hours`,
    },
    {
      icon: TrendingUp,
      label: 'Peak Grid Demand',
      value: `${result.peak_grid_kwh.toLocaleString()} kWh`,
      color: 'text-chart-demand',
      sub: 'Single-hour max',
    },
    {
      icon: DollarSign,
      label: 'Total Cost',
      value: `৳${result.total_cost_bdt.toLocaleString()}`,
      color: 'text-chart-solar',
      sub: 'BDT (Taka)',
    },
    {
      icon: BatteryFull,
      label: 'Battery Neutrality',
      value: isNeutral ? 'Neutral ✓' : `Δ ${(finalEnergy - initialEnergy).toFixed(1)} kWh`,
      color: isNeutral ? 'text-grid-500' : 'text-volt-500',
      sub: (
        <span className="flex items-center gap-1 font-mono">
          E₀={initialEnergy} <ArrowRight className="w-3 h-3" /> E₂₃={finalEnergy}
        </span>
      ),
    },
  ];

  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
      {kpis.map(({ icon: Icon, label, value, color, sub }) => (
        <div key={label} className="kpi-card animate-slide-up">
          <div className="flex items-center gap-2">
            <Icon className={`w-4 h-4 ${color}`} />
            <span className="text-xs font-medium text-surface-500 dark:text-surface-400">
              {label}
            </span>
          </div>
          <span className={`text-xl font-bold font-mono ${color}`}>
            {value}
          </span>
          <span className="text-[10px] text-surface-400">{sub}</span>
        </div>
      ))}
    </div>
  );
}
