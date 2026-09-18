import { useState } from 'react';
import { ChevronDown, ChevronUp, Table2 } from 'lucide-react';
import type { HourlyPlan, BatteryAction } from '../types/energy';

interface DispatchTableProps {
  plan: HourlyPlan[];
}

const ACTION_STYLES: Record<BatteryAction, { bg: string; text: string; label: string }> = {
  charge: {
    bg: 'bg-emerald-50 dark:bg-emerald-950/20',
    text: 'text-emerald-700 dark:text-emerald-400',
    label: '⚡ Charge',
  },
  discharge: {
    bg: 'bg-amber-50 dark:bg-amber-950/20',
    text: 'text-amber-700 dark:text-amber-400',
    label: '🔋 Discharge',
  },
  idle: {
    bg: 'bg-surface-50 dark:bg-surface-800/30',
    text: 'text-surface-500 dark:text-surface-400',
    label: '— Idle',
  },
};

function formatHour(h: number): string {
  const period = h >= 12 ? 'PM' : 'AM';
  const display = h === 0 ? 12 : h > 12 ? h - 12 : h;
  return `${display}:00 ${period}`;
}

export default function DispatchTable({ plan }: DispatchTableProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const displayPlan = isExpanded ? plan : plan.slice(0, 6);

  if (!plan.length) {
    return null;
  }

  return (
    <div className="card">
      <div className="card-header">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold text-surface-700 dark:text-surface-300 flex items-center gap-2">
            <Table2 className="w-4 h-4 text-grid-500" />
            Hourly Dispatch Table
          </h3>
          <button
            onClick={() => setIsExpanded(!isExpanded)}
            className="btn-secondary text-xs py-1 px-2"
          >
            {isExpanded ? (
              <>
                <ChevronUp className="w-3 h-3" /> Collapse
              </>
            ) : (
              <>
                <ChevronDown className="w-3 h-3" /> Show All 24h
              </>
            )}
          </button>
        </div>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-surface-50 dark:bg-surface-800 text-surface-500 dark:text-surface-400 text-xs">
              <th className="px-4 py-2.5 text-left font-medium whitespace-nowrap">Hour</th>
              <th className="px-4 py-2.5 text-right font-medium whitespace-nowrap">Grid (kWh)</th>
              <th className="px-4 py-2.5 text-right font-medium whitespace-nowrap">Solar (kWh)</th>
              <th className="px-4 py-2.5 text-center font-medium whitespace-nowrap">Battery Action</th>
              <th className="px-4 py-2.5 text-right font-medium whitespace-nowrap">Battery (kWh)</th>
              <th className="px-4 py-2.5 text-right font-medium whitespace-nowrap">SoC After (kWh)</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-surface-100 dark:divide-surface-800">
            {displayPlan.map((p) => {
              const style = ACTION_STYLES[p.battery_action];
              return (
                <tr
                  key={p.hour}
                  className={`transition-colors ${style.bg}`}
                >
                  <td className="px-4 py-2 font-mono text-surface-600 dark:text-surface-300 whitespace-nowrap">
                    {formatHour(p.hour)}
                  </td>
                  <td className="px-4 py-2 text-right font-mono text-chart-grid whitespace-nowrap">
                    {p.grid_kwh.toFixed(1)}
                  </td>
                  <td className="px-4 py-2 text-right font-mono text-chart-solar whitespace-nowrap">
                    {p.solar_used_kwh.toFixed(1)}
                  </td>
                  <td className="px-4 py-2 text-center">
                    <span className={`badge ${style.text} font-medium whitespace-nowrap inline-flex`}>
                      {style.label}
                    </span>
                  </td>
                  <td className="px-4 py-2 text-right font-mono text-surface-600 dark:text-surface-300 whitespace-nowrap">
                    {p.battery_kwh.toFixed(1)}
                  </td>
                  <td className="px-4 py-2 text-right font-mono text-chart-battery font-semibold whitespace-nowrap">
                    {p.battery_energy_after_kwh.toFixed(1)}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      {!isExpanded && plan.length > 6 && (
        <div className="text-center py-2 text-xs text-surface-400">
          Showing 6 of {plan.length} hours
        </div>
      )}
    </div>
  );
}
