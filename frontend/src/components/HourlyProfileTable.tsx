import type { HourlyProfile } from '../types/energy';
import { TableProperties } from 'lucide-react';

interface HourlyProfileTableProps {
  hours: HourlyProfile[];
  onChange: (hours: HourlyProfile[]) => void;
}

export default function HourlyProfileTable({
  hours,
  onChange,
}: HourlyProfileTableProps) {
  const updateHour = (
    index: number,
    field: keyof HourlyProfile,
    value: number
  ) => {
    const updated = [...hours];
    updated[index] = { ...updated[index], [field]: value };
    onChange(updated);
  };

  const formatHour = (h: number) => {
    const period = h >= 12 ? 'PM' : 'AM';
    const display = h === 0 ? 12 : h > 12 ? h - 12 : h;
    return `${display}${period}`;
  };

  // Sparkline-style mini bars
  const maxDemand = Math.max(...hours.map((h) => h.demand_kwh), 1);
  const maxSolar = Math.max(...hours.map((h) => h.solar_kwh), 1);

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <TableProperties className="w-4 h-4 text-grid-500" />
        <span className="text-sm font-semibold text-surface-700 dark:text-surface-300">
          24-Hour Profile
        </span>
      </div>

      {/* Mini sparkline preview */}
      <div className="flex items-end gap-px h-12 px-1">
        {hours.map((h, i) => (
          <div key={i} className="flex-1 flex flex-col justify-end gap-px" title={`${formatHour(h.hour)}: ${h.demand_kwh} kWh demand, ${h.solar_kwh} kWh solar`}>
            <div
              className="w-full rounded-t-sm"
              style={{
                height: `${(h.demand_kwh / maxDemand) * 100}%`,
                background: 'var(--color-chart-demand)',
                opacity: 0.6,
                minHeight: '1px',
              }}
            />
            <div
              className="w-full rounded-t-sm"
              style={{
                height: `${(h.solar_kwh / maxSolar) * 100}%`,
                background: 'var(--color-chart-solar)',
                opacity: 0.7,
                minHeight: h.solar_kwh > 0 ? '1px' : '0px',
              }}
            />
          </div>
        ))}
      </div>
      <div className="flex justify-between text-[10px] text-surface-400 px-1">
        <span>12AM</span>
        <span>6AM</span>
        <span>12PM</span>
        <span>6PM</span>
        <span>11PM</span>
      </div>

      {/* Scrollable table */}
      <div className="max-h-64 overflow-y-auto rounded-lg border border-surface-200 dark:border-surface-700">
        <table className="w-full text-xs">
          <thead className="sticky top-0 bg-surface-50 dark:bg-surface-800 z-10">
            <tr className="text-surface-500 dark:text-surface-400">
              <th className="px-2 py-1.5 text-left font-medium">Hour</th>
              <th className="px-2 py-1.5 text-right font-medium">
                <span className="text-chart-demand">Demand</span>
              </th>
              <th className="px-2 py-1.5 text-right font-medium">
                <span className="text-chart-solar">Solar</span>
              </th>
              <th className="px-2 py-1.5 text-right font-medium">Tariff</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-surface-100 dark:divide-surface-800">
            {hours.map((h, i) => (
              <tr
                key={h.hour}
                className="hover:bg-surface-50 dark:hover:bg-surface-800/50 transition-colors"
              >
                <td className="px-2 py-1 font-mono text-surface-600 dark:text-surface-400">
                  {formatHour(h.hour)}
                </td>
                <td className="px-1 py-0.5">
                  <input
                    type="number"
                    value={h.demand_kwh}
                    onChange={(e) =>
                      updateHour(i, 'demand_kwh', Number(e.target.value))
                    }
                    className="w-full text-right font-mono bg-transparent border-0 focus:outline-none focus:bg-surface-100 dark:focus:bg-surface-700 rounded px-1 py-0.5"
                    min={0}
                  />
                </td>
                <td className="px-1 py-0.5">
                  <input
                    type="number"
                    value={h.solar_kwh}
                    onChange={(e) =>
                      updateHour(i, 'solar_kwh', Number(e.target.value))
                    }
                    className="w-full text-right font-mono bg-transparent border-0 focus:outline-none focus:bg-surface-100 dark:focus:bg-surface-700 rounded px-1 py-0.5"
                    min={0}
                  />
                </td>
                <td className="px-1 py-0.5">
                  <input
                    type="number"
                    value={h.tariff_bdt_per_kwh}
                    onChange={(e) =>
                      updateHour(i, 'tariff_bdt_per_kwh', Number(e.target.value))
                    }
                    className="w-full text-right font-mono bg-transparent border-0 focus:outline-none focus:bg-surface-100 dark:focus:bg-surface-700 rounded px-1 py-0.5"
                    min={0}
                    step={0.5}
                  />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Legend */}
      <div className="flex gap-4 text-[10px] text-surface-400">
        <span className="flex items-center gap-1">
          <span className="w-2 h-2 rounded-full bg-chart-demand" />
          Demand (kWh)
        </span>
        <span className="flex items-center gap-1">
          <span className="w-2 h-2 rounded-full bg-chart-solar" />
          Solar (kWh)
        </span>
        <span className="flex items-center gap-1">
          <span className="w-2 h-2 rounded-full bg-surface-400" />
          Tariff (BDT)
        </span>
      </div>
    </div>
  );
}
